#pragma once
// AdaptiveFeatureWindowOp and BPFeatController — The Core Contribution.
// Section 14 of the build prompt.
//
// BPFeatController: pure AIMD control logic for Mechanism A (discrete
// window size W). Separated from the operator for unit testing.
//
// AdaptiveFeatureWindowOp: collects FeatureSnapshots into a FeatureBatch
// whose target size is determined by BPFeatController. Owns an
// EMAOccupancyTracker on its OWN output queue (the load-bearing line —
// Section 8.2 step 5) and publishes the EMA reading to BackpressureSignal
// for KeyedFeatureExtractOp's AlphaController to read.

#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "../core/backpressure.hpp"
#include "backpressure_signal.hpp"
#include "types.hpp"
#include <algorithm>
#include <cstdint>

namespace klstream {

// ── BPFeatController ─────────────────────────────────────────────────────────
class BPFeatController {
public:
    BPFeatController(std::uint32_t w_min, std::uint32_t w_max,
                     double occ_low, double occ_high,
                     double shrink_factor = 0.70,
                     double grow_factor   = 1.15)
        : w_min_(w_min), w_max_(w_max)
        , occ_low_(occ_low), occ_high_(occ_high)
        , shrink_factor_(shrink_factor), grow_factor_(grow_factor)
        , current_w_(w_max)
    {}

    // Called once per window START (never mid-window — Section 8.2, step 5).
    std::uint32_t update(double ema_occupancy) {
        if (ema_occupancy > occ_high_) {
            current_w_ = std::max(w_min_,
                static_cast<std::uint32_t>(current_w_ * shrink_factor_));
            ++shrink_events_;
        } else if (ema_occupancy < occ_low_) {
            current_w_ = std::min(w_max_,
                static_cast<std::uint32_t>(current_w_ * grow_factor_));
            ++grow_events_;
        }
        track_direction(ema_occupancy);
        return current_w_;
    }

    [[nodiscard]] std::uint32_t current()         const noexcept { return current_w_; }
    [[nodiscard]] std::uint64_t direction_changes() const noexcept { return direction_changes_; }
    [[nodiscard]] std::uint64_t shrink_events()   const noexcept { return shrink_events_; }
    [[nodiscard]] std::uint64_t grow_events()     const noexcept { return grow_events_; }

private:
    void track_direction(double occ) {
        int dir = 0;
        if (occ > occ_high_)      dir = -1;
        else if (occ < occ_low_)  dir =  1;
        else return;
        if (last_dir_ != 0 && dir != last_dir_) ++direction_changes_;
        last_dir_ = dir;
    }

    std::uint32_t w_min_, w_max_;
    double        occ_low_, occ_high_;
    double        shrink_factor_, grow_factor_;
    std::uint32_t current_w_;
    std::uint64_t shrink_events_{0};
    std::uint64_t grow_events_{0};
    std::uint64_t direction_changes_{0};
    int           last_dir_{0};
};

// ── AdaptiveFeatureWindowOp ──────────────────────────────────────────────────
class AdaptiveFeatureWindowOp : public IOperator {
public:
    using InQueue  = SPSCQueue<Event<FeatureSnapshot>>;
    using OutQueue = SPSCQueue<Event<FeatureBatch>>;

    AdaptiveFeatureWindowOp(std::string name, InQueue* input, OutQueue* output,
                            BackpressureSignal* signal,
                            std::uint32_t w_min  = 8,
                            std::uint32_t w_max  = MAX_FEATURE_BATCH,
                            double occ_low  = 0.30,
                            double occ_high = 0.70)
        : IOperator(std::move(name))
        , input_(input), output_(output), signal_(signal)
        , controller_(w_min, w_max, occ_low, occ_high)
        , tracker_(*output)     // ← reads occupancy of ITS OWN output queue
    {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }
    [[nodiscard]] const BPFeatController& controller() const noexcept { return controller_; }

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

        // At window START: capture target W and publish EMA to BackpressureSignal.
        // Both happen from the same tracker_.update() call so both mechanisms
        // always react to the same instant's reading (Section 8.2, step 7).
        if (buffer_.count == 0) {
            tracker_.update();
            double occ = tracker_.ema();
            target_w_  = controller_.update(occ);
            buffer_.occupancy_at_window_start = static_cast<float>(occ);
            if (signal_) {
                signal_->store(occ);
            }
        }

        Event<FeatureSnapshot> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        buffer_.push_back(in_ev.data, in_ev.seq);

        if (!buffer_.full(target_w_)) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }

        Event<FeatureBatch> out_ev{in_ev.timestamp_ns, 0, in_ev.seq, buffer_};
        buffer_ = FeatureBatch{};  // reset for next window

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
    InQueue*                      input_;
    OutQueue*                     output_;
    BackpressureSignal*           signal_;
    BPFeatController              controller_;
    EMAOccupancyTracker<OutQueue> tracker_;
    FeatureBatch                  buffer_{};
    std::uint32_t                 target_w_{0};
    Event<FeatureBatch>           pending_{};
    bool                          has_pending_{false};
    OperatorMetrics*              metrics_{nullptr};
};

} // namespace klstream
