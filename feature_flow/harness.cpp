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
#include "klstream/feature/backpressure_publisher_op.hpp"
#include "klstream/feature/ralf_window_op.hpp"

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

// ── AIMD Sensitivity Sweep ───────────────────────────────────────────────────
struct SweepConfig {
    float shrink;
    float grow;
    float occ_low;
    float occ_high;
};

// Grid: 3×3×2×2 = 36 configurations.
std::vector<SweepConfig> make_sweep_grid() {
    std::vector<SweepConfig> grid;
    for (float shrink : {0.50f, 0.70f, 0.85f})
        for (float grow : {1.10f, 1.15f, 1.25f})
            for (float occ_low : {0.20f, 0.30f})
                for (float occ_high : {0.60f, 0.70f})
                    grid.push_back({shrink, grow, occ_low, occ_high});
    return grid;
}

// ── Run one architecture, one seed ───────────────────────────────────────────
struct RunResult {
    std::string arch_name;
    std::uint32_t seed;
    std::uint64_t events_processed;
    double wall_time_ms;
    std::uint64_t direction_changes;
    float final_alpha;
    std::uint32_t final_w;
    float w_min;
    float w_max;
    float alpha_min;
    float alpha_max;
};

static RunResult run_architecture(
        const std::string& arch_name,
        const std::vector<BehaviorRow>& rows,
        const LogisticModel& model,
        const std::string& out_dir,
        std::uint32_t seed,
        bool log_trace = false,
        const SweepConfig* sweep_cfg = nullptr,
        std::uint64_t scoring_delay_us = 0,
        float ulb_max_amount = 1.0f) {

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
    RunResult res{arch_name, seed, 0, 0.0, 0, 0.0f, 0, -1.0f, -1.0f, -1.0f, -1.0f};

    Runtime rt;
    rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
    bool source_done = false;

    if (arch_name == "fixed" || arch_name == "throttle") {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out, seq); if(!ok) source_done=true; return ok; });
        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, [&](std::uint64_t s){return src.label_for_seq(s);}, nullptr, 0.10f, 0.02f, 0.30f, 0.01f, ulb_max_amount);
        auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
            FeatureBatch fb{};
            fb.occupancy_at_window_start = 0.0f;
            for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data,buf[i].seq); return fb;
        };
        TumblingCountWindow<FeatureSnapshot,FeatureBatch> window("win",&q_feat,&q_batch,128,aggr);
        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, scoring_delay_us);
        ResultSink sink("sink", &q_scored, result_csv);
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
        {
            std::string lat_path = out_dir + "/batch_latency_" + arch_name + "_seed" 
                                   + std::to_string(seed) + ".csv";
            std::ofstream lat_out(lat_path);
            lat_out << "wall_ns,latency_ns,batch_size,is_burst\n";
            for (const auto& entry : scorer.batch_latency_log()) {
                lat_out << entry.wall_ns << ','
                        << entry.latency_ns << ','
                        << entry.batch_size << ','
                        << static_cast<int>(entry.is_burst) << '\n';
            }
        }
        res.direction_changes = 0;

    } else if (arch_name == "drift") {
        SourceOperator<RawBehaviorEvent> source("source", &q_raw,
            [&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out, seq); if(!ok) source_done=true; return ok; });
        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, [&](std::uint64_t s){return src.label_for_seq(s);}, nullptr, 0.10f, 0.02f, 0.30f, 0.01f, ulb_max_amount);
        DriftAdaptiveWindowOp window("drift_win",&q_feat,&q_batch);
        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, scoring_delay_us);
        ResultSink sink("sink",&q_scored,result_csv);
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
        {
            std::string lat_path = out_dir + "/batch_latency_" + arch_name + "_seed" 
                                   + std::to_string(seed) + ".csv";
            std::ofstream lat_out(lat_path);
            lat_out << "wall_ns,latency_ns,batch_size,is_burst\n";
            for (const auto& entry : scorer.batch_latency_log()) {
                lat_out << entry.wall_ns << ','
                        << entry.latency_ns << ','
                        << entry.batch_size << ','
                        << static_cast<int>(entry.is_burst) << '\n';
            }
        }
        res.direction_changes = window.direction_changes();

    } else if (arch_name == "aonly") {
        std::ofstream trace_out;
        if (log_trace) { trace_out.open(trace_csv); init_controller_trace(trace_out); }
        SourceOperator<RawBehaviorEvent> source("source",&q_raw,
            [&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out,seq); if(!ok) source_done=true; return ok; });
        // fixed α=0.02
        KeyedFeatureExtractOp extract("extract",&q_raw,&q_feat,[&](std::uint64_t s){return src.label_for_seq(s);},nullptr,0.02f, 0.02f, 0.30f, 0.01f, ulb_max_amount);
        AdaptiveFeatureWindowOp window("adaptive_win",&q_feat,&q_batch,&signal);
        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, scoring_delay_us);
        ResultSink sink("sink",&q_scored,result_csv);
        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 1); rt.register_op(&scorer, 2); rt.register_op(&sink, 3);
        rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        int drain_checks = 0;
        while (drain_checks < 10) {
            if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) drain_checks++;
            else drain_checks = 0;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        rt.stop();
        {
            std::string lat_path = out_dir + "/batch_latency_" + arch_name + "_seed" 
                                   + std::to_string(seed) + ".csv";
            std::ofstream lat_out(lat_path);
            lat_out << "wall_ns,latency_ns,batch_size,is_burst\n";
            for (const auto& entry : scorer.batch_latency_log()) {
                lat_out << entry.wall_ns << ','
                        << entry.latency_ns << ','
                        << entry.batch_size << ','
                        << static_cast<int>(entry.is_burst) << '\n';
            }
        }
        res.direction_changes = window.controller().direction_changes();
        res.final_w     = window.controller().current();
        res.final_alpha = extract.last_alpha();
        res.w_min = window.controller().min_val();
        res.w_max = window.controller().max_val();
        res.alpha_min = extract.alpha_min();
        res.alpha_max = extract.alpha_max();

    } else if (arch_name == "bonly") {
        std::ofstream trace_out;
        if (log_trace) { trace_out.open(trace_csv); init_controller_trace(trace_out); }
        SourceOperator<RawBehaviorEvent> source("source",&q_raw,
            [&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out,seq); if(!ok) source_done=true; return ok; });
        KeyedFeatureExtractOp extract("extract",&q_raw,&q_feat,[&](std::uint64_t s){return src.label_for_seq(s);},&signal, 0.10f, 0.02f, 0.30f, 0.01f, ulb_max_amount);
        auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
            FeatureBatch fb{}; fb.occupancy_at_window_start = 0.0f;
            for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data,buf[i].seq); return fb;
        };
        TumblingCountWindow<FeatureSnapshot,FeatureBatch> window("win",&q_feat,&q_batch,128,aggr);
        BackpressurePublisherOp<SPSCQueue<Event<FeatureBatch>>> bp_pub("bp_pub", &q_batch, &signal);
        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, scoring_delay_us);
        ResultSink sink("sink",&q_scored,result_csv);
        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 1); rt.register_op(&bp_pub, 1); rt.register_op(&scorer, 2); rt.register_op(&sink, 3);
        rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        int drain_checks = 0;
        while (drain_checks < 10) {
            if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) drain_checks++;
            else drain_checks = 0;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        rt.stop();
        {
            std::string lat_path = out_dir + "/batch_latency_" + arch_name + "_seed" 
                                   + std::to_string(seed) + ".csv";
            std::ofstream lat_out(lat_path);
            lat_out << "wall_ns,latency_ns,batch_size,is_burst\n";
            for (const auto& entry : scorer.batch_latency_log()) {
                lat_out << entry.wall_ns << ','
                        << entry.latency_ns << ','
                        << entry.batch_size << ','
                        << static_cast<int>(entry.is_burst) << '\n';
            }
        }
        res.direction_changes = 0;
        res.final_w     = 128;
        res.final_alpha = extract.last_alpha();
        res.w_min = 128;
        res.w_max = 128;
        res.alpha_min = extract.alpha_min();
        res.alpha_max = extract.alpha_max();

    } else if (arch_name == "ralf") {
        SourceOperator<RawBehaviorEvent> source("source",&q_raw,
            [&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out,seq); if(!ok) source_done=true; return ok; });
        KeyedFeatureExtractOp extract("extract",&q_raw,&q_feat,[&](std::uint64_t s){return src.label_for_seq(s);},nullptr,0.10f, 0.02f, 0.30f, 0.01f, ulb_max_amount);
        RALFWindowOp window("ralf_win",&q_feat,&q_batch);
        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, scoring_delay_us);
        ResultSink sink("sink",&q_scored,result_csv);
        rt.register_op(&source, 0); rt.register_op(&extract, 0);
        rt.register_op(&window, 1); rt.register_op(&scorer, 2); rt.register_op(&sink, 3);
        rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Performance); rt.add_worker(CoreAffinity::Efficiency);
        rt.start();
        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        int drain_checks = 0;
        while (drain_checks < 10) {
            if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) drain_checks++;
            else drain_checks = 0;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        rt.stop();
        {
            std::string lat_path = out_dir + "/batch_latency_" + arch_name + "_seed" 
                                   + std::to_string(seed) + ".csv";
            std::ofstream lat_out(lat_path);
            lat_out << "wall_ns,latency_ns,batch_size,is_burst\n";
            for (const auto& entry : scorer.batch_latency_log()) {
                lat_out << entry.wall_ns << ','
                        << entry.latency_ns << ','
                        << entry.batch_size << ','
                        << static_cast<int>(entry.is_burst) << '\n';
            }
        }
        res.direction_changes = 0;

    } else { // adaptive
        std::ofstream trace_out;
        if (log_trace) {
            trace_out.open(trace_csv);
            init_controller_trace(trace_out);
        }
        SourceOperator<RawBehaviorEvent> source("source",&q_raw,
            [&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out,seq); if(!ok) source_done=true; return ok; });
        KeyedFeatureExtractOp extract("extract",&q_raw,&q_feat,[&](std::uint64_t s){return src.label_for_seq(s);},&signal, 0.10f, 0.02f, 0.30f, 0.01f, ulb_max_amount);
        
        std::uint32_t w_min=8, w_max=MAX_FEATURE_BATCH;
        double occ_l=0.30, occ_h=0.70, shr=0.70, grw=1.15;
        if (sweep_cfg) {
            shr = sweep_cfg->shrink; grw = sweep_cfg->grow;
            occ_l = sweep_cfg->occ_low; occ_h = sweep_cfg->occ_high;
        }
        AdaptiveFeatureWindowOp window("adaptive_win",&q_feat,&q_batch,&signal, w_min, w_max, occ_l, occ_h, shr, grw);
        
        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model, scoring_delay_us);
        ResultSink sink("sink",&q_scored,result_csv);
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
        {
            std::string lat_path = out_dir + "/batch_latency_" + arch_name + "_seed" 
                                   + std::to_string(seed) + ".csv";
            std::ofstream lat_out(lat_path);
            lat_out << "wall_ns,latency_ns,batch_size,is_burst\n";
            for (const auto& entry : scorer.batch_latency_log()) {
                lat_out << entry.wall_ns << ','
                        << entry.latency_ns << ','
                        << entry.batch_size << ','
                        << static_cast<int>(entry.is_burst) << '\n';
            }
        }
        res.direction_changes = window.controller().direction_changes();
        res.final_w     = window.controller().current();
        res.final_alpha = extract.last_alpha();
        res.w_min = window.controller().min_val();
        res.w_max = window.controller().max_val();
        res.alpha_min = extract.alpha_min();
        res.alpha_max = extract.alpha_max();
        // Gap 8: report controller overhead
        printf("[overhead] arch=%s seed=%u  mean_control_overhead=%.1f ns/window-start  calls=%llu\n",
               arch_name.c_str(), seed,
               window.mean_control_overhead_ns(),
               (unsigned long long)window.control_calls());
    }

    // Bug 2 Fix: Write trace summary file
    std::ofstream tr(out_dir + "/harness_summary_" + arch_name + "_seed" + std::to_string(seed) + ".csv");
    tr << "arch,seed,final_W,final_alpha,direction_changes,W_min,W_max,alpha_min,alpha_max\n";
    if (res.w_min >= 0.0f) {
        tr << arch_name << "," << seed << "," << res.final_w << "," << res.final_alpha << ","
           << res.direction_changes << "," << res.w_min << "," << res.w_max << "," 
           << res.alpha_min << "," << res.alpha_max << "\n";
    } else {
        tr << arch_name << "," << seed << ",N/A,N/A,N/A,N/A,N/A,N/A,N/A\n";
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
    bool sweep = false;
    std::uint64_t scoring_delay_us = 0;
    std::string only_arch = "";   // Gap 7: run only this arch if set
    float cli_shrink = -1.0f;     // Gap 6: override shrink_factor
    float cli_grow   = -1.0f;     // Gap 6: override grow_factor

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--replay"        && i+1 < argc) replay_path        = argv[++i];
        if (a == "--model"         && i+1 < argc) model_path         = argv[++i];
        if (a == "--out-dir"       && i+1 < argc) out_dir            = argv[++i];
        if (a == "--seeds"         && i+1 < argc) n_seeds            = std::stoi(argv[++i]);
        if (a == "--synthetic")                   synthetic          = true;
        if (a == "--sweep")                       sweep              = true;
        if (a == "--scoring-delay-us" && i+1 < argc) scoring_delay_us = std::stoull(argv[++i]);
        if (a == "--arch"          && i+1 < argc) only_arch          = argv[++i];
        if (a == "--shrink-factor" && i+1 < argc) cli_shrink         = std::stof(argv[++i]);
        if (a == "--grow-factor"   && i+1 < argc) cli_grow           = std::stof(argv[++i]);
    }

    fs::create_directories(out_dir);

    std::vector<BehaviorRow> rows;
    if (synthetic) {
        rows = BehaviorSource::generate_synthetic(300);
        std::cout << "[harness] Using synthetic data: " << rows.size() << " events\n";
    } else {
        DatasetMode mode = (replay_path.find("ulb") != std::string::npos) ? DatasetMode::ULB : DatasetMode::Taobao;
        rows = load_replay_csv(replay_path, mode);
        std::cout << "[harness] Loaded " << rows.size() << " events from " << replay_path << "\n";
    }

    LogisticModel model;
    try { model = LogisticModel::load(model_path); }
    catch (...) {
        std::cerr << "[harness] WARNING: using zero model\n";
        model = LogisticModel::zero();
    }
    
    float ulb_max_amount = 1.0f;
    std::string norm_path = model_path.substr(0, model_path.find_last_of('.')) + ".norm";
    std::ifstream norm_in(norm_path);
    if (norm_in.is_open()) {
        std::string line;
        while (std::getline(norm_in, line)) {
            if (line.find("max_amount=") == 0) {
                ulb_max_amount = std::stof(line.substr(11));
            }
        }
    }

    // Build CLI sweep config if shrink/grow overrides provided
    SweepConfig cli_sweep_cfg{0.70f, 1.15f, 0.30f, 0.70f};
    bool use_cli_sweep = false;
    if (cli_shrink > 0.0f) { cli_sweep_cfg.shrink = cli_shrink; use_cli_sweep = true; }
    if (cli_grow   > 0.0f) { cli_sweep_cfg.grow   = cli_grow;   use_cli_sweep = true; }

    const std::vector<std::string> all_archs = {"fixed", "drift", "throttle", "aonly", "bonly", "adaptive", "ralf"};
    std::vector<std::string> archs;
    if (!only_arch.empty()) {
        archs = {only_arch};
        std::cout << "[harness] --arch filter: only running " << only_arch << "\n";
    } else {
        archs = all_archs;
    }

    if (sweep) {
        std::cout << "[harness] Running AIMD sensitivity sweep on synthetic data...\n";
        auto grid = make_sweep_grid();
        std::ofstream swp_out(out_dir + "/sweep_results.csv");
        swp_out << "shrink,grow,occ_low,occ_high,events,wall_time_ms,direction_changes,final_w,final_alpha\n";
        
        int idx = 0;
        for (const auto& c : grid) {
            std::cout << "[sweep] " << ++idx << "/" << grid.size() 
                      << " shrink=" << c.shrink << " grow=" << c.grow 
                      << " occ=" << c.occ_low << "-" << c.occ_high << "\n";
            // Run Adaptive architecture with sweep config
            RunResult r = run_architecture("adaptive", rows, model, out_dir, 0, false, &c, scoring_delay_us, ulb_max_amount);
            swp_out << c.shrink << ',' << c.grow << ',' << c.occ_low << ',' << c.occ_high << ','
                    << r.events_processed << ',' << r.wall_time_ms << ','
                    << r.direction_changes << ',' << r.final_w << ',' << r.final_alpha << '\n';
        }
        std::cout << "[harness] Sweep summary → " << out_dir << "/sweep_results.csv\n";
        return 0;
    }

    std::string summary_path = out_dir + "/harness_summary.csv";
    std::ofstream summary(summary_path);
    summary << "arch,seed,events,wall_time_ms,direction_changes,final_w,final_alpha\n";

    for (int seed = 0; seed < n_seeds; ++seed) {
        for (const auto& arch : archs) {
            bool log_trace = (arch == "adaptive" && seed == 0);
            std::cout << "[harness] Running arch=" << arch << " seed=" << seed << " ...\n";
            const SweepConfig* sweep_ptr = (arch == "adaptive" && use_cli_sweep) ? &cli_sweep_cfg : nullptr;
            RunResult r = run_architecture(arch, rows, model, out_dir,
                                           static_cast<std::uint32_t>(seed), log_trace, sweep_ptr, scoring_delay_us, ulb_max_amount);
            summary << r.arch_name   << ','
                    << r.seed        << ','
                    << r.events_processed << ','
                    << std::fixed << std::setprecision(2) << r.wall_time_ms << ','
                    << r.direction_changes << ','
                    << r.final_w    << ','
                    << r.final_alpha << '\n';
            summary.flush(); std::cout << "Done flushing\n";
            std::cout << "  done: " << r.wall_time_ms << " ms\n";
        }
    }
    std::cout << "[harness] Summary → " << summary_path << "\n";
    return 0;
}
