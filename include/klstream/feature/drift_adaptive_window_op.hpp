#pragma once
// DriftAdaptiveWindowOp — Literature-style data-driven baseline (Section 15.2).
// Decision 6: simplified two-timescale EMA crossover detector, NOT full ADWIN.
// Driven entirely by input data statistics (FeatureSnapshot.x[0] == ema_engagement);
// reads NO queue-occupancy signal. This is the one property that must hold for
// it to be a fair "signal-driven, not load-driven" baseline — confirmed by the
// unit test in test_drift_adaptive_window_op.cpp.

#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "types.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace klstream {

class DriftAdaptiveWindowOp : public IOperator {
public:
    using InQueue  = SPSCQueue<Event<FeatureSnapshot>>;
    using OutQueue = SPSCQueue<Event<FeatureBatch>>;

    DriftAdaptiveWindowOp(std::string name, InQueue* input, OutQueue* output,
                          std::uint32_t w_min = 8,
                          std::uint32_t w_max = MAX_FEATURE_BATCH,
                          double alpha_fast = 0.30,
                          double alpha_slow = 0.02,
                          double drift_threshold = 0.50,
                          double shrink_factor = 0.70,
                          double grow_factor   = 1.15)
        : IOperator(std::move(name))
        , input_(input), output_(output)
        , w_min_(w_min), w_max_(w_max)
        , alpha_fast_(alpha_fast), alpha_slow_(alpha_slow)
        , drift_threshold_(drift_threshold)
        , shrink_factor_(shrink_factor), grow_factor_(grow_factor)
        , target_w_(w_max)
    {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }
    [[nodiscard]] std::uint64_t direction_changes() const noexcept { return direction_changes_; }
    [[nodiscard]] std::uint32_t current_w() const noexcept { return target_w_; }

    OpStatus tick() override {
        if (has_pending_) {
            if (output_->try_push(pending_)) {
                has_pending_ = false;
                if (metrics_) metrics_->events_processed.increment();
                return OpStatus::Processed;
            }
            if (metrics_) metrics_->events_blocked.increment();
            return OpStatus::Blocked;
        }

        Event<FeatureSnapshot> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        // Drift statistic: ema_engagement (x[0]) — already computed by
        // KeyedFeatureExtractOp; no dependency on RawBehaviorEvent.
        float sample = in_ev.data.x[0];
        fast_ema_ = static_cast<float>(alpha_fast_) * sample
                  + static_cast<float>(1.0 - alpha_fast_) * fast_ema_;
        slow_ema_ = static_cast<float>(alpha_slow_) * sample
                  + static_cast<float>(1.0 - alpha_slow_) * slow_ema_;

        // Window sizing decision at the START of each window only.
        if (buffer_.count == 0) {
            double denom  = std::max(1e-6, static_cast<double>(std::abs(slow_ema_)));
            double rel_gap = std::abs(static_cast<double>(fast_ema_)
                                    - static_cast<double>(slow_ema_)) / denom;
            int dir = 0;
            if (rel_gap > drift_threshold_) {
                target_w_ = std::max(w_min_,
                    static_cast<std::uint32_t>(target_w_ * shrink_factor_));
                dir = -1;
            } else {
                target_w_ = std::min(w_max_,
                    static_cast<std::uint32_t>(target_w_ * grow_factor_));
                dir = 1;
            }
            if (last_dir_ != 0 && dir != last_dir_) ++direction_changes_;
            last_dir_ = dir;
            buffer_.occupancy_at_window_start = 0.0f;
        }

        buffer_.push_back(in_ev.data, in_ev.seq);
        if (!buffer_.full(target_w_)) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }

        Event<FeatureBatch> out_ev{in_ev.timestamp_ns, 0, in_ev.seq, buffer_};
        buffer_ = FeatureBatch{};

        if (output_->try_push(out_ev)) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }
        pending_     = out_ev;
        has_pending_ = true;
        if (metrics_) metrics_->events_blocked.increment();
        return OpStatus::Blocked;
    }

private:
    InQueue*      input_;
    OutQueue*     output_;
    std::uint32_t w_min_, w_max_;
    double        alpha_fast_, alpha_slow_, drift_threshold_;
    double        shrink_factor_, grow_factor_;
    float         fast_ema_{0.0f}, slow_ema_{0.0f};
    std::uint32_t target_w_;
    FeatureBatch  buffer_{};
    std::uint64_t direction_changes_{0};
    int           last_dir_{0};
    Event<FeatureBatch> pending_{};
    bool          has_pending_{false};
    OperatorMetrics* metrics_{nullptr};
};

} // namespace klstream
