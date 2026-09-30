#pragma once
// include/klstream/core/registry_harness.hpp
// Registry-driven experiment harness: topology construction, execution, counter tracking, and atomic result finalization.

#include "experiment_config.hpp"
#include "runtime.hpp"
#include "spsc_queue.hpp"
#include "metrics.hpp"
#include "../operators/source.hpp"
#include "../operators/window.hpp"
#include "../feature/types.hpp"
#include "../feature/keyed_feature_extract_op.hpp"
#include "../feature/adaptive_feature_window_op.hpp"
#include "../feature/scoring_flush_op.hpp"
#include "../feature/behavior_source.hpp"
#include "../feature/result_sink.hpp"
#include "../model/logistic_model.hpp"
#include "../feature/backpressure_publisher_op.hpp"
#include "../feature/ralf_window_op.hpp"

#include <chrono>
#include <atomic>
#include <cstdint>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <memory>
#include <string>
#include <vector>
#include <thread>

namespace fs = std::filesystem;

namespace klstream {

// ── Harness Counters ────────────────────────────────────────────────────────
struct HarnessCounters {
    std::uint64_t events_read{0};
    std::uint64_t events_extracted{0};
    std::uint64_t windows_emitted{0};
    std::uint64_t events_scored{0};
    std::uint64_t events_sunk{0};
    std::uint64_t direction_changes{0};
    std::uint32_t final_w{0};
    float final_alpha{0.0f};
    double wall_time_ms{0.0};
};

// ── Run Identity & Execution Report ─────────────────────────────────────────
struct RunIdentity {
    std::string run_id;
    std::string architecture_id;
    std::string data_artifact_id;
    std::string model_artifact_id;
    std::uint32_t seed{0};
    std::string status{"NOT_STARTED"};
    HarnessCounters counters{};
    std::string result_file;
    std::string trace_file;
};

// ── Registry-Driven Harness ─────────────────────────────────────────────────
class RegistryHarness {
public:
    explicit RegistryHarness(const ExperimentConfig& cfg) : cfg_(cfg) {
        validate_experiment_config(cfg_);
    }

    void load_artifacts(const std::vector<BehaviorRow>& rows, const LogisticModel& model) {
        if (rows.empty()) {
            throw ArtifactLoadError("Behavior dataset is empty");
        }
        rows_ = rows;
        model_ = &model;
        artifacts_loaded_ = true;
    }

    RunIdentity execute(bool log_trace = false) {
        if (!artifacts_loaded_ || model_ == nullptr) {
            throw ExecutionError("Cannot execute harness without loading valid artifacts");
        }

        RunIdentity ident;
        ident.architecture_id = cfg_.architecture_id;
        ident.data_artifact_id = cfg_.data_artifact_id;
        ident.model_artifact_id = cfg_.model_artifact_id;
        ident.seed = cfg_.seed;
        ident.run_id = cfg_.architecture_id + "_s" + std::to_string(cfg_.seed);

        fs::path out_dir(cfg_.out_dir);
        fs::create_directories(out_dir);

        std::string res_tmp = (out_dir / ("tmp_results_" + ident.run_id + ".csv")).string();
        std::string res_final = (out_dir / ("results_" + ident.run_id + ".csv")).string();
        std::string tr_tmp = (out_dir / ("tmp_trace_" + ident.run_id + ".csv")).string();
        std::string tr_final = (out_dir / ("trace_" + ident.run_id + ".csv")).string();

        ident.result_file = res_final;
        ident.trace_file = tr_final;

        ArchitectureType arch = parse_architecture_id(cfg_.architecture_id);
        BehaviorSource src(rows_, ReplayMode::MaxRate, 1.0);

        std::size_t q_cap = cfg_.resource_budget.queue_capacity;
        SPSCQueue<Event<RawBehaviorEvent>> q_raw(q_cap);
        SPSCQueue<Event<FeatureSnapshot>>  q_feat(q_cap);
        SPSCQueue<Event<FeatureBatch>>     q_batch(64);
        SPSCQueue<Event<ScoredResult>>     q_scored(q_cap);
        BackpressureSignal signal;

        OperatorMetrics m_src("source"), m_ext("extract"),
                        m_win("window"), m_score("scorer"), m_sink("sink");

        std::atomic<bool> source_done{false};
        std::atomic<std::uint64_t> read_count{0};

        auto t0 = std::chrono::steady_clock::now();
        Runtime rt;
        for (int i = 0; i < cfg_.resource_budget.workers; ++i) {
            rt.add_worker(CoreAffinity::Performance);
        }

        if (arch == ArchitectureType::FixedWindow) {
            SourceOperator<RawBehaviorEvent> source("source", &q_raw,
                [&src, &source_done, &read_count](Event<RawBehaviorEvent>& out, std::uint64_t seq) {
                    bool ok = src(out, seq);
                    if (!ok) source_done = true;
                    else read_count++;
                    return ok;
                });
            source.attach_metrics(&m_src);

            KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
                [&src](std::uint64_t s) { return src.label_for_seq(s); },
                nullptr, 0.10f, 0.02f, 0.30f, 0.01f, cfg_.ulb_max_amount, cfg_.dataset_mode);
            extract.attach_metrics(&m_ext);

            auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
                FeatureBatch fb{};
                fb.occupancy_at_window_start = 0.0f;
                for (std::size_t i = 0; i < buf.size(); ++i) fb.push_back(buf[i].data, buf[i].seq);
                return fb;
            };
            TumblingCountWindow<FeatureSnapshot, FeatureBatch> window("win", &q_feat, &q_batch, cfg_.w_events, aggr);
            window.attach_metrics(&m_win);

            ScoringFlushOp scorer("scorer", &q_batch, &q_scored, model_, cfg_.scoring_delay_us);
            scorer.attach_metrics(&m_score);

            ResultSink sink("sink", &q_scored, res_tmp);
            sink.attach_metrics(&m_sink);

            rt.register_op(&source, 0);
            rt.register_op(&extract, 0);
            rt.register_op(&window, 0);
            rt.register_op(&scorer, 0);
            rt.register_op(&sink, 0);

            rt.start();
            while (!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(2)); }
            int drains = 0;
            while (drains < 5) {
                if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) drains++;
                else drains = 0;
                std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            rt.stop();

            ident.counters.events_read = read_count.load();
            ident.counters.events_extracted = m_ext.events_processed.load();
            ident.counters.windows_emitted = m_win.events_processed.load();
            ident.counters.events_scored = m_score.events_processed.load();
            ident.counters.events_sunk = m_sink.events_processed.load();
            ident.counters.direction_changes = 0;
            ident.counters.final_w = cfg_.w_events;
            ident.counters.final_alpha = 0.10f;

        } else if (arch == ArchitectureType::BackpressureOnly) {
            SourceOperator<RawBehaviorEvent> source("source", &q_raw,
                [&src, &source_done, &read_count](Event<RawBehaviorEvent>& out, std::uint64_t seq) {
                    bool ok = src(out, seq);
                    if (!ok) source_done = true;
                    else read_count++;
                    return ok;
                });
            source.attach_metrics(&m_src);

            KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
                [&src](std::uint64_t s) { return src.label_for_seq(s); },
                &signal, 0.10f, 0.02f, 0.30f, 0.01f, cfg_.ulb_max_amount, cfg_.dataset_mode);
            extract.attach_metrics(&m_ext);

            auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
                FeatureBatch fb{};
                fb.occupancy_at_window_start = 0.0f;
                for (std::size_t i = 0; i < buf.size(); ++i) fb.push_back(buf[i].data, buf[i].seq);
                return fb;
            };
            TumblingCountWindow<FeatureSnapshot, FeatureBatch> window("win", &q_feat, &q_batch, cfg_.w_events, aggr);
            window.attach_metrics(&m_win);

            BackpressurePublisherOp<SPSCQueue<Event<FeatureBatch>>> bp_pub("bp_pub", &q_batch, &signal);
            ScoringFlushOp scorer("scorer", &q_batch, &q_scored, model_, cfg_.scoring_delay_us);
            scorer.attach_metrics(&m_score);

            ResultSink sink("sink", &q_scored, res_tmp);
            sink.attach_metrics(&m_sink);

            rt.register_op(&source, 0);
            rt.register_op(&extract, 0);
            rt.register_op(&window, 0);
            rt.register_op(&bp_pub, 0);
            rt.register_op(&scorer, 0);
            rt.register_op(&sink, 0);

            rt.start();
            while (!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(2)); }
            int drains = 0;
            while (drains < 5) {
                if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) drains++;
                else drains = 0;
                std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            rt.stop();

            ident.counters.events_read = read_count.load();
            ident.counters.events_extracted = m_ext.events_processed.load();
            ident.counters.windows_emitted = m_win.events_processed.load();
            ident.counters.events_scored = m_score.events_processed.load();
            ident.counters.events_sunk = m_sink.events_processed.load();
            ident.counters.direction_changes = 0;
            ident.counters.final_w = cfg_.w_events;
            ident.counters.final_alpha = 0.10f;

        } else if (arch == ArchitectureType::RateThrottle) {
            SourceOperator<RawBehaviorEvent> source("source", &q_raw,
                [&src, &source_done, &read_count](Event<RawBehaviorEvent>& out, std::uint64_t seq) {
                    bool ok = src(out, seq);
                    if (!ok) source_done = true;
                    else read_count++;
                    return ok;
                });
            source.attach_metrics(&m_src);

            KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
                [&src](std::uint64_t s) { return src.label_for_seq(s); },
                nullptr, 0.10f, 0.02f, 0.30f, 0.01f, cfg_.ulb_max_amount, cfg_.dataset_mode);
            extract.attach_metrics(&m_ext);

            auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
                FeatureBatch fb{};
                fb.occupancy_at_window_start = 0.0f;
                for (std::size_t i = 0; i < buf.size(); ++i) fb.push_back(buf[i].data, buf[i].seq);
                return fb;
            };
            TumblingCountWindow<FeatureSnapshot, FeatureBatch> window("win", &q_feat, &q_batch, cfg_.w_events, aggr);
            window.attach_metrics(&m_win);

            ScoringFlushOp scorer("scorer", &q_batch, &q_scored, model_, cfg_.scoring_delay_us);
            scorer.attach_metrics(&m_score);

            ResultSink sink("sink", &q_scored, res_tmp);
            sink.attach_metrics(&m_sink);

            rt.register_op(&source, 0);
            rt.register_op(&extract, 0);
            rt.register_op(&window, 0);
            rt.register_op(&scorer, 0);
            rt.register_op(&sink, 0);

            rt.start();
            while (!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(2)); }
            int drains = 0;
            while (drains < 5) {
                if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) drains++;
                else drains = 0;
                std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            rt.stop();

            ident.counters.events_read = read_count.load();
            ident.counters.events_extracted = m_ext.events_processed.load();
            ident.counters.windows_emitted = m_win.events_processed.load();
            ident.counters.events_scored = m_score.events_processed.load();
            ident.counters.events_sunk = m_sink.events_processed.load();
            ident.counters.direction_changes = 0;
            ident.counters.final_w = cfg_.w_events;
            ident.counters.final_alpha = 0.10f;

        } else if (arch == ArchitectureType::BPFeatAdaptive) {
            SourceOperator<RawBehaviorEvent> source("source", &q_raw,
                [&src, &source_done, &read_count](Event<RawBehaviorEvent>& out, std::uint64_t seq) {
                    bool ok = src(out, seq);
                    if (!ok) source_done = true;
                    else read_count++;
                    return ok;
                });
            source.attach_metrics(&m_src);

            KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
                [&src](std::uint64_t s) { return src.label_for_seq(s); },
                &signal, 0.10f, cfg_.alpha_min, cfg_.alpha_max, cfg_.slew_rate, cfg_.ulb_max_amount, cfg_.dataset_mode);
            extract.attach_metrics(&m_ext);

            AdaptiveFeatureWindowOp window("adaptive_win", &q_feat, &q_batch, &signal,
                                           cfg_.w_min, cfg_.w_max, cfg_.occ_low, cfg_.occ_high, cfg_.shrink_factor, cfg_.grow_factor);
            window.attach_metrics(&m_win);

            ScoringFlushOp scorer("scorer", &q_batch, &q_scored, model_, cfg_.scoring_delay_us);
            scorer.attach_metrics(&m_score);

            ResultSink sink("sink", &q_scored, res_tmp);
            sink.attach_metrics(&m_sink);

            rt.register_op(&source, 0);
            rt.register_op(&extract, 0);
            rt.register_op(&window, 0);
            rt.register_op(&scorer, 0);
            rt.register_op(&sink, 0);

            rt.start();
            while (!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(2)); }
            int drains = 0;
            while (drains < 5) {
                if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) drains++;
                else drains = 0;
                std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            rt.stop();

            ident.counters.events_read = read_count.load();
            ident.counters.events_extracted = m_ext.events_processed.load();
            ident.counters.windows_emitted = m_win.events_processed.load();
            ident.counters.events_scored = m_score.events_processed.load();
            ident.counters.events_sunk = m_sink.events_processed.load();
            ident.counters.direction_changes = window.controller().direction_changes();
            ident.counters.final_w = window.controller().current();
            ident.counters.final_alpha = extract.last_alpha();
        }

        auto t1 = std::chrono::steady_clock::now();
        ident.counters.wall_time_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

        // Atomic file finalization
        if (fs::exists(res_tmp)) {
            fs::rename(res_tmp, res_final);
        }
        if (log_trace && fs::exists(tr_tmp)) {
            fs::rename(tr_tmp, tr_final);
        }

        ident.status = "COMPLETED";
        return ident;
    }

    const ExperimentConfig& config() const { return cfg_; }

private:
    ExperimentConfig cfg_;
    std::vector<BehaviorRow> rows_;
    const LogisticModel* model_{nullptr};
    bool artifacts_loaded_{false};
};

} // namespace klstream
