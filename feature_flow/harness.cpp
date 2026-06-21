// feature_flow/harness.cpp — Multi-run experiment harness (Section 27).
// Runs all four architectures against the same replay, multiple seeds,
// with controller-trace logging and automated metric aggregation stubs.
//
// Usage:
//   ./feature_flow_harness \\
//       --replay data/replay/replay_taobao_10k.csv \\
//       --model  models/classifier_weights.txt \\
//       --out-dir results/raw \\
//       --seeds 5

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
#include "klstream/core/config.hpp"

#include <chrono>
#include <cstdint>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using namespace klstream;

// ── Run one architecture, one seed ───────────────────────────────────────────
struct RunResult {
    std::string arch_name;
    std::uint32_t seed;
    std::uint64_t events_processed;
    double wall_time_ms;
    std::uint64_t direction_changes;
    float final_alpha;
    std::uint32_t final_w;
};

static RunResult run_architecture(
        const std::string& arch_name,
        const std::vector<BehaviorRow>& rows,
        const LogisticModel& model,
        const std::string& out_dir,
        std::uint32_t seed,
        bool log_trace = false) {

    // Re-construct BehaviorSource for this run (same rows, MaxRate replay)
    BehaviorSource src(rows, ReplayMode::MaxRate, 1.0);

    SPSCQueue<Event<RawBehaviorEvent>> q_raw(4096);
    SPSCQueue<Event<FeatureSnapshot>>  q_feat(4096);
    SPSCQueue<Event<FeatureBatch>>     q_batch(64);
    SPSCQueue<Event<ScoredResult>>     q_scored(4096);
    BackpressureSignal signal;

    std::string run_tag = arch_name + "_seed" + std::to_string(seed);
    std::string result_csv = out_dir + "/results_" + run_tag + ".csv";
    std::string trace_csv  = out_dir + "/trace_"   + run_tag + ".csv";

    OperatorMetrics m_src("source"), m_ext("extract"),
                    m_win("window"), m_score("scorer"), m_sink("sink");

    auto t0 = std::chrono::steady_clock::now();
    RunResult res{arch_name, seed, 0, 0.0, 0, 0.0f, 0};

    Runtime rt;
    rt.add_worker();
    bool source_done = false;

    if (arch_name == "fixed" || arch_name == "throttle") {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out, seq); if(!ok) source_done=true; return ok; });
        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, nullptr, 0.10f);
        auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
            FeatureBatch fb{}; for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data,i); return fb;
        };
        TumblingCountWindow<FeatureSnapshot,FeatureBatch> window("win",&q_feat,&q_batch,128,aggr);
        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model);
        ResultSink sink("sink", &q_scored, result_csv);
        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 0); rt.register_op(&scorer, 0); rt.register_op(&sink, 0);
        rt.add_worker();
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        rt.stop();
        res.direction_changes = 0;

    } else if (arch_name == "drift") {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out, seq); if(!ok) source_done=true; return ok; });
        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, nullptr, 0.10f);
        DriftAdaptiveWindowOp window("drift_win",&q_feat,&q_batch);
        ScoringFlushOp scorer("scorer",&q_batch,&q_scored,&model);
        ResultSink sink("sink",&q_scored,result_csv);
        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 0); rt.register_op(&scorer, 0); rt.register_op(&sink, 0);
        rt.add_worker();
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        rt.stop();
        res.direction_changes = window.direction_changes();

    } else { // adaptive
        std::ofstream trace_out;
        if (log_trace) {
            trace_out.open(trace_csv);
            init_controller_trace(trace_out);
        }
        SourceOperator<RawBehaviorEvent> source("source",&q_raw,
            [&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out,seq); if(!ok) source_done=true; return ok; });
        KeyedFeatureExtractOp extract("extract",&q_raw,&q_feat,&signal);
        AdaptiveFeatureWindowOp window("adaptive_win",&q_feat,&q_batch,&signal);
        ScoringFlushOp scorer("scorer",&q_batch,&q_scored,&model);
        ResultSink sink("sink",&q_scored,result_csv);
        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 0); rt.register_op(&scorer, 0); rt.register_op(&sink, 0);
        rt.add_worker();
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        rt.stop();
        res.direction_changes = window.controller().direction_changes();
        res.final_w     = window.controller().current();
        res.final_alpha = extract.last_alpha();
    }

    auto t1 = std::chrono::steady_clock::now();
    res.wall_time_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    res.events_processed = rows.size();
    return res;
}

int main(int argc, char** argv) {
    std::string replay_path = "data/replay/replay_taobao_10k.csv";
    std::string model_path  = "models/classifier_weights.txt";
    std::string out_dir     = "results/raw";
    int n_seeds = 5;
    bool synthetic = false;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--replay"   && i+1 < argc) replay_path = argv[++i];
        if (a == "--model"    && i+1 < argc) model_path  = argv[++i];
        if (a == "--out-dir"  && i+1 < argc) out_dir     = argv[++i];
        if (a == "--seeds"    && i+1 < argc) n_seeds     = std::stoi(argv[++i]);
        if (a == "--synthetic")              synthetic   = true;
    }

    fs::create_directories(out_dir);

    std::vector<BehaviorRow> rows;
    if (synthetic) {
        rows = BehaviorSource::generate_synthetic(300);
        std::cout << "[harness] Using synthetic data: " << rows.size() << " events\n";
    } else {
        rows = load_replay_csv(replay_path, DatasetMode::Taobao);
        std::cout << "[harness] Loaded " << rows.size() << " events from " << replay_path << "\n";
    }

    LogisticModel model;
    try { model = LogisticModel::load(model_path); }
    catch (...) {
        std::cerr << "[harness] WARNING: using zero model\n";
        model = LogisticModel::zero();
    }

    const std::vector<std::string> archs = {"fixed", "drift", "throttle", "adaptive"};

    std::string summary_path = out_dir + "/harness_summary.csv";
    std::ofstream summary(summary_path);
    summary << "arch,seed,events,wall_time_ms,direction_changes,final_w,final_alpha\n";

    for (int seed = 0; seed < n_seeds; ++seed) {
        for (const auto& arch : archs) {
            bool log_trace = (arch == "adaptive" && seed == 0);
            std::cout << "[harness] Running arch=" << arch << " seed=" << seed << " ...\n";
            RunResult r = run_architecture(arch, rows, model, out_dir,
                                           static_cast<std::uint32_t>(seed), log_trace);
            summary << r.arch_name   << ','
                    << r.seed        << ','
                    << r.events_processed << ','
                    << std::fixed << std::setprecision(2) << r.wall_time_ms << ','
                    << r.direction_changes << ','
                    << r.final_w    << ','
                    << r.final_alpha << '\n';
            summary.flush();
            std::cout << "  done: " << r.wall_time_ms << " ms\n";
        }
    }
    std::cout << "[harness] Summary → " << summary_path << "\n";
    return 0;
}
