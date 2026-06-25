#pragma once
// ScoringFlushOp: pops ONE Event<FeatureBatch> per tick(), scores each
// FeatureSnapshot inside it with the native logistic regression, and pushes
// one Event<ScoredResult> per snapshot. Total per-tick cost: O(W·d) where
// W is the batch size and d = FeatureSnapshot::kDim (constant).
//
// The O(W) cost is the LOAD-BEARING CAUSAL MECHANISM (Section 8.2 steps 1-4):
// when W is large, one tick() takes proportionally longer in wall-clock time,
// leaving ScoringFlushOp's input queue (the window operator's output queue)
// to fill up — which the EMAOccupancyTracker detects and acts on.
//
// Important: the Blocked-recovery pattern here differs from every other
// operator in the codebase (Section 17 note): instead of one pending Event,
// we track has_pending_idx_ (which snapshot index we stopped at in mid-batch
// flush). This is intentional and is the single highest-risk new control flow
// in the project; it has its own dedicated unit test (test_scoring_flush_op).

#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "../model/logistic_model.hpp"
#include "types.hpp"
#include <iomanip>
#include <unordered_map>
#include <chrono>
#include <thread>

namespace klstream {

class ScoringFlushOp : public IOperator {
public:
    using InQueue  = SPSCQueue<Event<FeatureBatch>>;
    using OutQueue = SPSCQueue<Event<ScoredResult>>;

    ScoringFlushOp(std::string name, InQueue* input, OutQueue* output,
                   const LogisticModel* model,
                   std::uint64_t delay_per_item_us = 0)
        : IOperator(std::move(name))
        , input_(input), output_(output), model_(model)
        , delay_per_item_us_(delay_per_item_us)
    {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }

    OpStatus tick() override {
        // Resume a partially-flushed batch first.
        if (has_pending_idx_ < pending_batch_.count) {
            return flush_from(has_pending_idx_);
        }

        Event<FeatureBatch> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        last_batch_window_size_ = in_ev.data.count;
        last_batch_timestamp_   = in_ev.timestamp_ns;
        pending_batch_ = in_ev.data;
        return flush_from(0);
    }

private:
    // The O(W) hot loop — Section 8.2's causal mechanism.
    OpStatus flush_from(std::uint32_t start_idx) {
        for (std::uint32_t i = start_idx; i < pending_batch_.count; ++i) {
            const FeatureSnapshot& fs = pending_batch_.items[i];
            double score = model_->score(fs.x);

            // Staleness: time since this user's feature was last published.
            float staleness = 0.0f;
            auto it = last_publish_ts_.find(fs.user_id);
            if (it != last_publish_ts_.end()) {
                staleness = static_cast<float>(
                    static_cast<double>(fs.event_ts_ns - it->second) / 1e9);
            }
            last_publish_ts_[fs.user_id] = fs.event_ts_ns;

            if (delay_per_item_us_ > 0 && fs.is_burst_period) {
                std::this_thread::sleep_for(
                    std::chrono::microseconds(delay_per_item_us_));
            }

            ScoredResult res{
                fs.user_id,
                score,
                fs.label,
                fs.label_valid,
                last_batch_window_size_,
                fs.alpha_used,
                staleness,
                pending_batch_.occupancy_at_window_start,
                fs.is_burst_period
            };

            Event<ScoredResult> out_ev{last_batch_timestamp_, fs.user_id, pending_batch_.first_seq + i, res};

            if (!output_->try_push(out_ev)) {
                has_pending_idx_ = i;  // remember where we stopped
                if (metrics_) metrics_->events_blocked.increment();
                return OpStatus::Blocked;
            }
        }
        // Full batch flushed.
        has_pending_idx_ = pending_batch_.count;
        if (metrics_) metrics_->events_processed.increment();
        return OpStatus::Processed;
    }

    InQueue*             input_;
    OutQueue*            output_;
    const LogisticModel* model_;
    FeatureBatch         pending_batch_{};
    std::uint32_t        has_pending_idx_{0};
    std::uint32_t        last_batch_window_size_{0};
    std::uint64_t        last_batch_timestamp_{0};
    std::unordered_map<std::uint32_t, std::uint64_t> last_publish_ts_;
    std::uint64_t        delay_per_item_us_{0};
    OperatorMetrics*     metrics_{nullptr};
};

} // namespace klstream
