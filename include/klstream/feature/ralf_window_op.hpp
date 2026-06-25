// include/klstream/feature/ralf_window_op.hpp
// RALF Surrogate Baseline (Variant 7 / "ralf" architecture)
// Implements RALF's Regret-Proportional scheduling policy in the
// streaming feature pipeline context. Selects the top-K users by
// estimated cumulative regret per window (K = budget_fraction * W_max).
// Reference: Wooders et al., VLDB 2024, "RALF: Accuracy-Aware Scheduling
// for Feature Store Maintenance"
#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "types.hpp"
#include <algorithm>
#include <cmath>
#include <unordered_map>
#include <vector>

namespace klstream {

class RALFWindowOp : public IOperator {
public:
    using InQueue  = SPSCQueue<Event<FeatureSnapshot>>;
    using OutQueue = SPSCQueue<Event<FeatureBatch>>;

    // budget_fraction: fraction of MAX_FEATURE_BATCH slots to publish per window.
    // Default 0.5 matches RALF's intent of 50% compute saving under load.
    RALFWindowOp(std::string name, InQueue* input, OutQueue* output,
                 std::uint32_t window_collect_size = 256,
                 double budget_fraction = 0.50)
        : IOperator(std::move(name)), input_(input), output_(output)
        , window_collect_size_(window_collect_size)
        , budget_k_(static_cast<std::uint32_t>(window_collect_size * budget_fraction))
    {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }

    OpStatus tick() override {
        if (has_pending_idx_ < pending_batch_.count) {
            return flush_from(has_pending_idx_);
        }

        Event<FeatureSnapshot> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        // Accumulate regret for this user since last time we saw their snapshot
        std::uint32_t uid = in_ev.data.user_id;
        auto& state = regret_map_[uid];
        double drift = std::fabs(static_cast<double>(in_ev.data.x[0]) - state.last_ema);
        double staleness = (state.last_publish_ns > 0)
            ? static_cast<double>(in_ev.timestamp_ns - state.last_publish_ns) / 1e9
            : 0.0;
        state.cumulative_regret += drift * (staleness + 1.0);
        state.snapshot = in_ev.data;
        state.seq = in_ev.seq;
        state.last_ema = in_ev.data.x[0];
        collected_keys_.push_back(uid);
        collected_count_++;

        if (collected_count_ < window_collect_size_) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }

        // Window full — select top-K by cumulative regret
        std::vector<std::pair<double, std::uint32_t>> ranked;
        for (std::uint32_t k : collected_keys_) {
            ranked.push_back({regret_map_[k].cumulative_regret, k});
        }
        std::partial_sort(ranked.begin(),
                          ranked.begin() + std::min((std::size_t)budget_k_, ranked.size()),
                          ranked.end(),
                          [](const auto& a, const auto& b){ return a.first > b.first; });

        pending_batch_ = FeatureBatch{};
        std::uint32_t to_publish = std::min(budget_k_, (std::uint32_t)ranked.size());
        for (std::uint32_t i = 0; i < to_publish; ++i) {
            std::uint32_t k = ranked[i].second;
            auto& st = regret_map_[k];
            pending_batch_.push_back(st.snapshot, st.seq);
            st.last_publish_ns = in_ev.timestamp_ns;
            st.cumulative_regret = 0.0;  // reset after publishing
        }

        collected_keys_.clear();
        collected_count_ = 0;
        last_event_ts_ = in_ev.timestamp_ns;
        return flush_from(0);
    }

private:
    OpStatus flush_from(std::uint32_t start) {
        for (std::uint32_t i = start; i < pending_batch_.count; ++i) {
            const FeatureSnapshot& fs = pending_batch_.items[i];
            Event<FeatureBatch> out_ev;
            out_ev.timestamp_ns = last_event_ts_;
            out_ev.key = 0; out_ev.seq = pending_batch_.first_seq + i;
            // Emit one-item batch per published key (ScoringFlushOp handles this)
            FeatureBatch single{};
            single.occupancy_at_window_start = 0.0f;
            single.push_back(fs, pending_batch_.first_seq + i);
            out_ev.data = single;
            if (!output_->try_push(out_ev)) {
                has_pending_idx_ = i;
                return OpStatus::Blocked;
            }
        }
        has_pending_idx_ = pending_batch_.count;
        if (metrics_) metrics_->events_processed.increment();
        return OpStatus::Processed;
    }

    struct UserRegretState {
        double cumulative_regret = 0.0;
        double last_ema = 0.0;
        std::uint64_t last_publish_ns = 0;
        FeatureSnapshot snapshot{};
        std::uint64_t seq = 0;
    };

    InQueue* input_;
    OutQueue* output_;
    std::uint32_t window_collect_size_;
    std::uint32_t budget_k_;
    std::unordered_map<std::uint32_t, UserRegretState> regret_map_;
    std::vector<std::uint32_t> collected_keys_;
    std::uint32_t collected_count_{0};
    FeatureBatch pending_batch_{};
    std::uint32_t has_pending_idx_{0};
    std::uint64_t last_event_ts_{0};
    OperatorMetrics* metrics_{nullptr};
};

} // namespace klstream
