// feature_flow/main.cpp — Full four-architecture pipeline wiring (Section 23).
// Compile-time architecture selection via --arch flag.
//
// Usage:
//   ./feature_flow_main \\
//       --arch [fixed|drift|throttle|adaptive] \\
//       --dataset [taobao|ulb] \\
//       --replay <path> \\
//       --model <weights_path> \\
//       --out <result_csv> \\
//       [--speed 1.0]   (replay speed multiplier for PreserveTiming mode)

#include "klstream/core/runtime.hpp"
#include "klstream/core/spsc_queue.hpp"
#include "klstream/operators/source.hpp"
#include "klstream/operators/window.hpp"
#include "klstream/feature/types.hpp"
#include "klstream/feature/keyed_feature_extract_op.hpp"
#include "klstream/feature/adaptive_feature_window_op.hpp"
#include "klstream/feature/drift_adaptive_window_op.hpp"
#include "klstream/feature/scoring_flush_op.hpp"
#include "klstream/feature/behavior_source.hpp"
#include "klstream/feature/result_sink.hpp"
#include "klstream/model/logistic_model.hpp"
#include "klstream/core/backpressure.hpp"
#include "klstream/core/metrics.hpp"

#include <algorithm>
#include <chrono>
#include <cstring>
#include <iostream>
#include <string>
#include <stdexcept>

using namespace klstream;

// ── CLI parsing ───────────────────────────────────────────────────────────────
enum class Architecture { Fixed, DriftAdaptive, RateThrottle, Adaptive };

struct Config {
    Architecture arch    = Architecture::Adaptive;
    DatasetMode  dataset = DatasetMode::Taobao;
    std::string replay_path  = "data/replay/replay_taobao_10k.csv";
    std::string model_path   = "models/classifier_weights.txt";
    std::string out_path     = "results/raw/run.csv";
    double      speed_factor = 1.0;
    bool        use_synthetic = false;
    std::uint32_t synthetic_users = 500;
};

static Config parse_args(int argc, char** argv) {
    Config cfg;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--arch" && i+1 < argc) {
            std::string v = argv[++i];
            if      (v == "fixed")    cfg.arch = Architecture::Fixed;
            else if (v == "drift")    cfg.arch = Architecture::DriftAdaptive;
            else if (v == "throttle") cfg.arch = Architecture::RateThrottle;
            else if (v == "adaptive") cfg.arch = Architecture::Adaptive;
            else throw std::invalid_argument("unknown --arch: " + v);
        } else if (a == "--dataset" && i+1 < argc) {
            std::string v = argv[++i];
            if      (v == "taobao") cfg.dataset = DatasetMode::Taobao;
            else if (v == "ulb")    cfg.dataset = DatasetMode::ULB;
            else throw std::invalid_argument("unknown --dataset: " + v);
        } else if (a == "--replay" && i+1 < argc)  { cfg.replay_path  = argv[++i]; }
        else if (a == "--model"   && i+1 < argc)    { cfg.model_path   = argv[++i]; }
        else if (a == "--out"     && i+1 < argc)    { cfg.out_path     = argv[++i]; }
        else if (a == "--speed"   && i+1 < argc)    { cfg.speed_factor = std::stod(argv[++i]); }
        else if (a == "--synthetic")                 { cfg.use_synthetic = true; }
        else if (a == "--synthetic-users" && i+1 < argc) {
            cfg.synthetic_users = static_cast<std::uint32_t>(std::stoul(argv[++i]));
        }
    }
    return cfg;
}

// ── Admission-control wrapper for RateThrottle baseline (Section 16) ──────────
// Returns a BehaviorSource generator that throttles emission rate based on
// the occupancy of q_raw (Section 16's EMAOccupancyTracker + TokenBucketRateLimiter).
static auto make_throttled_generator(BehaviorSource& src,
                                     SPSCQueue<Event<RawBehaviorEvent>>& q_raw) {
    static EMAOccupancyTracker<SPSCQueue<Event<RawBehaviorEvent>>> tracker(q_raw, 0.10);
    static TokenBucketRateLimiter limiter(100000.0, 5000.0);

    return [&src, &q_raw](Event<RawBehaviorEvent>& out, std::uint64_t seq) -> bool {
        tracker.update();
        if (tracker.soft_pressure()) {
            limiter.set_rate(std::max(1000.0, limiter.rate() * 0.85));
        } else if (tracker.low_pressure()) {
            limiter.set_rate(std::min(100000.0, limiter.rate() * 1.05));
        }
        if (!limiter.try_consume()) return true; // skip this tick (not done, just throttled)
        return src(out, seq);
    };
}

// ── Queue sizes (Section 23's note on FeatureBatch memory budget) ─────────────
static constexpr std::size_t Q_RAW_CAP    = 4096;
static constexpr std::size_t Q_FEAT_CAP   = 4096;
static constexpr std::size_t Q_BATCH_CAP  = 64;   // FeatureBatch ~4KB/slot → keep small
static constexpr std::size_t Q_SCORED_CAP = 4096;

int main(int argc, char** argv) {
    Config cfg;
    try { cfg = parse_args(argc, argv); }
    catch (const std::exception& e) {
        std::cerr << "arg error: " << e.what() << "\n"; return 1;
    }

    // ── Load data ─────────────────────────────────────────────────────────────
    std::vector<BehaviorRow> rows;
    if (cfg.use_synthetic) {
        std::cout << "[main] Using synthetic dataset (" << cfg.synthetic_users << " users)\n";
        rows = BehaviorSource::generate_synthetic(cfg.synthetic_users);
    } else {
        std::cout << "[main] Loading " << cfg.replay_path << " ...\n";
        rows = load_replay_csv(cfg.replay_path, cfg.dataset);
    }
    std::cout << "[main] " << rows.size() << " events loaded\n";

    BehaviorSource behavior_src(rows, ReplayMode::MaxRate, cfg.speed_factor);

    // ── Load model ─────────────────────────────────────────────────────────────
    LogisticModel model;
    try { model = LogisticModel::load(cfg.model_path); }
    catch (...) {
        std::cerr << "[main] WARNING: could not load model from " << cfg.model_path
                  << " — using zero model for dry run\n";
        model = LogisticModel::zero();
    }

    // ── Queues ─────────────────────────────────────────────────────────────────
    SPSCQueue<Event<RawBehaviorEvent>> q_raw(Q_RAW_CAP);
    SPSCQueue<Event<FeatureSnapshot>>  q_feat(Q_FEAT_CAP);
    SPSCQueue<Event<FeatureBatch>>     q_batch(Q_BATCH_CAP);
    SPSCQueue<Event<ScoredResult>>     q_scored(Q_SCORED_CAP);

    BackpressureSignal signal;  // owned by main(); only written for Adaptive arch

    // ── Architecture-specific pipeline construction ───────────────────────────
    auto arch_name = [&]() -> std::string {
        switch (cfg.arch) {
            case Architecture::Fixed:        return "fixed";
            case Architecture::DriftAdaptive: return "drift";
            case Architecture::RateThrottle: return "throttle";
            case Architecture::Adaptive:     return "adaptive";
        }
        return "unknown";
    }();
    std::cout << "[main] Architecture: " << arch_name << "\n";
    std::cout << "[main] Output → " << cfg.out_path << "\n";

    Runtime rt;

    // ── Metrics objects (one per operator) ───────────────────────────────────
    OperatorMetrics m_src("source"), m_ext("extract"),
                    m_win("window"), m_score("scorer"), m_sink("sink");

    // ── Fixed baseline ─────────────────────────────────────────────────────────
    if (cfg.arch == Architecture::Fixed) {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&behavior_src](Event<RawBehaviorEvent>& out, std::uint64_t seq){
                return behavior_src(out, seq); });
        source.attach_metrics(&m_src);

        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
            /*signal=*/nullptr, /*fixed_alpha=*/0.10f);
        extract.attach_metrics(&m_ext);

        auto aggr = [](const std::vector<FeatureSnapshot>& buf) -> FeatureBatch {
            FeatureBatch fb{}; for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i],i);
            return fb;
        };
        TumblingCountWindow<FeatureSnapshot,FeatureBatch> window(
            "fixed_window", &q_feat, &q_batch, 128, aggr);
        window.attach_metrics(&m_win);

        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model);
        scorer.attach_metrics(&m_score);

        ResultSink sink("sink", &q_scored, cfg.out_path);
        sink.attach_metrics(&m_sink);

        rt.register_op(&source); rt.register_op(&extract);
        rt.register_op(&window); rt.register_op(&scorer); rt.register_op(&sink);
        rt.run_until_source_exhausted();
    }

    // ── DriftAdaptive baseline ────────────────────────────────────────────────
    else if (cfg.arch == Architecture::DriftAdaptive) {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&behavior_src](Event<RawBehaviorEvent>& out, std::uint64_t seq){
                return behavior_src(out, seq); });
        source.attach_metrics(&m_src);

        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
            nullptr, 0.10f);
        extract.attach_metrics(&m_ext);

        DriftAdaptiveWindowOp window("drift_window", &q_feat, &q_batch);
        window.attach_metrics(&m_win);

        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model);
        scorer.attach_metrics(&m_score);

        ResultSink sink("sink", &q_scored, cfg.out_path);
        sink.attach_metrics(&m_sink);

        rt.register_op(&source); rt.register_op(&extract);
        rt.register_op(&window); rt.register_op(&scorer); rt.register_op(&sink);
        rt.run_until_source_exhausted();
        std::cout << "[main] drift direction_changes=" << window.direction_changes() << "\n";
    }

    // ── RateThrottle baseline ─────────────────────────────────────────────────
    else if (cfg.arch == Architecture::RateThrottle) {
        auto throttled_gen = make_throttled_generator(behavior_src, q_raw);
        SourceOperator<RawBehaviorEvent> source("source", &q_raw, throttled_gen);
        source.attach_metrics(&m_src);

        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, nullptr, 0.10f);
        extract.attach_metrics(&m_ext);

        auto aggr = [](const std::vector<FeatureSnapshot>& buf) -> FeatureBatch {
            FeatureBatch fb{}; for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i],i);
            return fb;
        };
        TumblingCountWindow<FeatureSnapshot,FeatureBatch> window(
            "fixed_window_throttled", &q_feat, &q_batch, 128, aggr);
        window.attach_metrics(&m_win);

        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model);
        scorer.attach_metrics(&m_score);

        ResultSink sink("sink", &q_scored, cfg.out_path);
        sink.attach_metrics(&m_sink);

        rt.register_op(&source); rt.register_op(&extract);
        rt.register_op(&window); rt.register_op(&scorer); rt.register_op(&sink);
        rt.run_until_source_exhausted();
    }

    // ── Adaptive contribution ─────────────────────────────────────────────────
    else {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&behavior_src](Event<RawBehaviorEvent>& out, std::uint64_t seq){
                return behavior_src(out, seq); });
        source.attach_metrics(&m_src);

        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, &signal);
        extract.attach_metrics(&m_ext);

        AdaptiveFeatureWindowOp window("adaptive_window", &q_feat, &q_batch, &signal);
        window.attach_metrics(&m_win);

        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model);
        scorer.attach_metrics(&m_score);

        ResultSink sink("sink", &q_scored, cfg.out_path);
        sink.attach_metrics(&m_sink);

        rt.register_op(&source); rt.register_op(&extract);
        rt.register_op(&window); rt.register_op(&scorer); rt.register_op(&sink);
        rt.run_until_source_exhausted();

        std::cout << "[main] final W=" << window.controller().current()
                  << " direction_changes=" << window.controller().direction_changes()
                  << " final alpha=" << extract.last_alpha() << "\n";
    }

    // ── Print summary metrics ─────────────────────────────────────────────────
    std::cout << "\n=== Operator Metrics ===\n";
    for (auto* m : {&m_src, &m_ext, &m_win, &m_score, &m_sink}) m->print(std::cout);

    return 0;
}
