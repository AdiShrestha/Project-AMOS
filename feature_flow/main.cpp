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
#include "klstream/feature/backpressure_publisher_op.hpp"
#include "klstream/feature/ralf_window_op.hpp"
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
enum class Architecture { Fixed, DriftAdaptive, RateThrottle, Adaptive, AOnly, BOnly, Ralf };

struct Config {
    Architecture arch    = Architecture::Adaptive;
    DatasetMode  dataset = DatasetMode::Taobao;
    std::string replay_path  = "data/replay/replay_taobao_10k.csv";
    std::string model_path   = "models/classifier_weights.txt";
    std::string out_path     = "results/raw/run.csv";
    double      speed_factor = 1.0;
    bool        use_synthetic = false;
    std::uint32_t synthetic_users = 500;
    std::uint64_t scoring_delay_us = 0;
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
            else if (v == "aonly")    cfg.arch = Architecture::AOnly;
            else if (v == "bonly")    cfg.arch = Architecture::BOnly;
            else if (v == "ralf")     cfg.arch = Architecture::Ralf;
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
        else if (a == "--scoring-delay-us" && i+1 < argc) {
            cfg.scoring_delay_us = std::stoull(argv[++i]);
        }
    }
    return cfg;
}

// ── Admission-control wrapper for RateThrottle baseline (Section 16) ──────────
// Returns a BehaviorSource generator that throttles emission rate based on
// the occupancy of q_raw (Section 16's EMAOccupancyTracker + TokenBucketRateLimiter).
static auto make_throttled_generator(BehaviorSource& src, bool& source_done,
                                     SPSCQueue<Event<RawBehaviorEvent>>& q_raw) {
    static EMAOccupancyTracker<SPSCQueue<Event<RawBehaviorEvent>>> tracker(q_raw, 0.10);
    static TokenBucketRateLimiter limiter(100000.0, 5000.0);

    return [&src, &q_raw, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq) -> bool {
        tracker.update();
        if (tracker.soft_pressure()) {
            limiter.set_rate(std::max(1000.0, limiter.rate() * 0.85));
        } else if (tracker.ema() < 0.30) {
            limiter.set_rate(std::min(100000.0, limiter.rate() * 1.05));
        }
        if (!limiter.try_consume()) return true; // skip this tick (not done, just throttled)
        bool ok = src(out, seq); if(!ok) source_done=true; return ok;
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

    ReplayMode rmode = cfg.use_synthetic ? ReplayMode::PreserveTiming : ReplayMode::MaxRate;
    BehaviorSource behavior_src(rows, rmode, cfg.speed_factor);

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
            case Architecture::AOnly:        return "aonly";
            case Architecture::BOnly:        return "bonly";
            case Architecture::Ralf:         return "ralf";
        }
        return "unknown";
    }();
    std::cout << "[main] Architecture: " << arch_name << "\n";
    std::cout << "[main] Output → " << cfg.out_path << "\n";

    Runtime rt;
    rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
    bool source_done = false;

    // ── Metrics objects (one per operator) ───────────────────────────────────
    OperatorMetrics m_src("source"), m_ext("extract"),
                    m_win("window"), m_score("scorer"), m_sink("sink");

    // ── Fixed baseline ─────────────────────────────────────────────────────────
    if (cfg.arch == Architecture::Fixed) {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&behavior_src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){
                bool ok = behavior_src(out, seq); if(!ok) source_done=true; return ok; });
        source.attach_metrics(&m_src);

        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
            [&](std::uint64_t s){return behavior_src.label_for_seq(s);}, nullptr, 0.10f);
        extract.attach_metrics(&m_ext);

        auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
            FeatureBatch fb{};
            fb.occupancy_at_window_start = 0.0f;
            for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data,buf[i].seq);
            return fb;
        };
        TumblingCountWindow<FeatureSnapshot,FeatureBatch> window(
            "fixed_window", &q_feat, &q_batch, 128, aggr);
        window.attach_metrics(&m_win);

        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, cfg.scoring_delay_us);
        scorer.attach_metrics(&m_score);

        ResultSink sink("sink", &q_scored, cfg.out_path);
        sink.attach_metrics(&m_sink);

        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 1); rt.register_op(&scorer, 2); rt.register_op(&sink, 3);
        rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        int drain_checks = 0;
        while (drain_checks < 10) {
            if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) {
                drain_checks++;
            } else {
                drain_checks = 0;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        printf("[drain] Final occupancy: raw=%.3f, feat=%.3f, batch=%.3f, scored=%.3f\n", q_raw.occupancy(), q_feat.occupancy(), q_batch.occupancy(), q_scored.occupancy());
        rt.stop();
    }

    // ── DriftAdaptive baseline ────────────────────────────────────────────────
    else if (cfg.arch == Architecture::DriftAdaptive) {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&behavior_src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){
                bool ok = behavior_src(out, seq); if(!ok) source_done=true; return ok; });
        source.attach_metrics(&m_src);

        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
            [&](std::uint64_t s){return behavior_src.label_for_seq(s);}, nullptr, 0.10f);
        extract.attach_metrics(&m_ext);

        DriftAdaptiveWindowOp window("drift_window", &q_feat, &q_batch);
        window.attach_metrics(&m_win);

        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, cfg.scoring_delay_us);
        scorer.attach_metrics(&m_score);

        ResultSink sink("sink", &q_scored, cfg.out_path);
        sink.attach_metrics(&m_sink);

        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 1); rt.register_op(&scorer, 2); rt.register_op(&sink, 3);
        rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        int drain_checks = 0;
        while (drain_checks < 10) {
            if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) {
                drain_checks++;
            } else {
                drain_checks = 0;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        printf("[drain] Final occupancy: raw=%.3f, feat=%.3f, batch=%.3f, scored=%.3f\n", q_raw.occupancy(), q_feat.occupancy(), q_batch.occupancy(), q_scored.occupancy());
        rt.stop();
        std::cout << "[main] drift direction_changes=" << window.direction_changes() << "\n";
    }

    // ── RateThrottle baseline ─────────────────────────────────────────────────
    else if (cfg.arch == Architecture::RateThrottle) {
        auto throttled_gen = make_throttled_generator(behavior_src, source_done, q_raw);
        SourceOperator<RawBehaviorEvent> source("source", &q_raw, throttled_gen);
        source.attach_metrics(&m_src);

        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, [&](std::uint64_t s){return behavior_src.label_for_seq(s);}, nullptr, 0.10f);
        extract.attach_metrics(&m_ext);

        auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
            FeatureBatch fb{};
            fb.occupancy_at_window_start = 0.0f;
            for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data,buf[i].seq);
            return fb;
        };
        TumblingCountWindow<FeatureSnapshot,FeatureBatch> window(
            "fixed_window_throttled", &q_feat, &q_batch, 128, aggr);
        window.attach_metrics(&m_win);

        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, cfg.scoring_delay_us);
        scorer.attach_metrics(&m_score);

        ResultSink sink("sink", &q_scored, cfg.out_path);
        sink.attach_metrics(&m_sink);

        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 1); rt.register_op(&scorer, 2); rt.register_op(&sink, 3);
        rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        int drain_checks = 0;
        while (drain_checks < 10) {
            if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) {
                drain_checks++;
            } else {
                drain_checks = 0;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        printf("[drain] Final occupancy: raw=%.3f, feat=%.3f, batch=%.3f, scored=%.3f\n", q_raw.occupancy(), q_feat.occupancy(), q_batch.occupancy(), q_scored.occupancy());
        rt.stop();
    }

    // ── AOnly ablation (Adaptive W + fixed α) ─────────────────────────────────
    else if (cfg.arch == Architecture::AOnly) {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&behavior_src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){
                bool ok = behavior_src(out, seq); if(!ok) source_done=true; return ok; });
        source.attach_metrics(&m_src);

        // signal=nullptr forces fixed α=0.02 (α_min equivalent)
        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, [&](std::uint64_t s){return behavior_src.label_for_seq(s);}, nullptr, 0.02f);
        extract.attach_metrics(&m_ext);

        AdaptiveFeatureWindowOp window("adaptive_window", &q_feat, &q_batch, &signal);
        window.attach_metrics(&m_win);

        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, cfg.scoring_delay_us);
        scorer.attach_metrics(&m_score);

        ResultSink sink("sink", &q_scored, cfg.out_path);
        sink.attach_metrics(&m_sink);

        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 1); rt.register_op(&scorer, 2); rt.register_op(&sink, 3);
        rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        int drain_checks = 0;
        while (drain_checks < 10) {
            if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) {
                drain_checks++;
            } else {
                drain_checks = 0;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        printf("[drain] Final occupancy: raw=%.3f, feat=%.3f, batch=%.3f, scored=%.3f\n", q_raw.occupancy(), q_feat.occupancy(), q_batch.occupancy(), q_scored.occupancy());
        rt.stop();

        std::cout << "[main] final W=" << window.controller().current()
                  << " direction_changes=" << window.controller().direction_changes()
                  << " final alpha=" << extract.last_alpha() << "\n";
    }

    // ── BOnly ablation (fixed W + adaptive α) ─────────────────────────────────
    else if (cfg.arch == Architecture::BOnly) {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&behavior_src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){
                bool ok = behavior_src(out, seq); if(!ok) source_done=true; return ok; });
        source.attach_metrics(&m_src);

        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, [&](std::uint64_t s){return behavior_src.label_for_seq(s);}, &signal);
        extract.attach_metrics(&m_ext);

        auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
            FeatureBatch fb{};
            fb.occupancy_at_window_start = 0.0f; // actually handled by BOnly publisher, but initialized here
            for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data,buf[i].seq);
            return fb;
        };
        TumblingCountWindow<FeatureSnapshot,FeatureBatch> window(
            "fixed_window", &q_feat, &q_batch, 128, aggr);
        window.attach_metrics(&m_win);

        BackpressurePublisherOp<SPSCQueue<Event<FeatureBatch>>> bp_pub("bp_pub", &q_batch, &signal);

        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, cfg.scoring_delay_us);
        scorer.attach_metrics(&m_score);

        ResultSink sink("sink", &q_scored, cfg.out_path);
        sink.attach_metrics(&m_sink);

        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 1); rt.register_op(&bp_pub, 1); rt.register_op(&scorer, 2); rt.register_op(&sink, 3);
        rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        int drain_checks = 0;
        while (drain_checks < 10) {
            if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) {
                drain_checks++;
            } else {
                drain_checks = 0;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        printf("[drain] Final occupancy: raw=%.3f, feat=%.3f, batch=%.3f, scored=%.3f\n", q_raw.occupancy(), q_feat.occupancy(), q_batch.occupancy(), q_scored.occupancy());
        rt.stop();

        std::cout << "[main] final W=128 direction_changes=0 final alpha=" << extract.last_alpha() << "\n";
    }

    // ── RALF surrogate baseline ───────────────────────────────────────────────
    else if (cfg.arch == Architecture::Ralf) {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&behavior_src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){
                bool ok = behavior_src(out, seq); if(!ok) source_done=true; return ok; });
        source.attach_metrics(&m_src);

        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, [&](std::uint64_t s){return behavior_src.label_for_seq(s);}, nullptr, 0.10f);
        extract.attach_metrics(&m_ext);

        RALFWindowOp window("ralf_window", &q_feat, &q_batch);
        window.attach_metrics(&m_win);

        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, cfg.scoring_delay_us);
        scorer.attach_metrics(&m_score);

        ResultSink sink("sink", &q_scored, cfg.out_path);
        sink.attach_metrics(&m_sink);

        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 1); rt.register_op(&scorer, 2); rt.register_op(&sink, 3);
        rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        int drain_checks = 0;
        while (drain_checks < 10) {
            if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) {
                drain_checks++;
            } else {
                drain_checks = 0;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        printf("[drain] Final occupancy: raw=%.3f, feat=%.3f, batch=%.3f, scored=%.3f\n", q_raw.occupancy(), q_feat.occupancy(), q_batch.occupancy(), q_scored.occupancy());
        rt.stop();
    }

    // ── Adaptive contribution ─────────────────────────────────────────────────
    else {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&behavior_src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){
                bool ok = behavior_src(out, seq); if(!ok) source_done=true; return ok; });
        source.attach_metrics(&m_src);

        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, [&](std::uint64_t s){return behavior_src.label_for_seq(s);}, &signal);
        extract.attach_metrics(&m_ext);

        AdaptiveFeatureWindowOp window("adaptive_window", &q_feat, &q_batch, &signal);
        window.attach_metrics(&m_win);

        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, cfg.scoring_delay_us);
        scorer.attach_metrics(&m_score);

        ResultSink sink("sink", &q_scored, cfg.out_path);
        sink.attach_metrics(&m_sink);

        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 1); rt.register_op(&scorer, 2); rt.register_op(&sink, 3);
        rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        int drain_checks = 0;
        while (drain_checks < 10) {
            if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) {
                drain_checks++;
            } else {
                drain_checks = 0;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        printf("[drain] Final occupancy: raw=%.3f, feat=%.3f, batch=%.3f, scored=%.3f\n", q_raw.occupancy(), q_feat.occupancy(), q_batch.occupancy(), q_scored.occupancy());
        rt.stop();

        std::cout << "[main] final W=" << window.controller().current()
                  << " direction_changes=" << window.controller().direction_changes()
                  << " final alpha=" << extract.last_alpha() << "\n";
    }

    // ── Print summary metrics ─────────────────────────────────────────────────
    std::cout << "\n=== Operator Metrics ===\n";
    // Removed metrics print loop as real KLStream handles it via MetricsReporter

    return 0;
}
