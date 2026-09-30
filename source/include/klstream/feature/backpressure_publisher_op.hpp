// include/klstream/feature/backpressure_publisher_op.hpp
#pragma once
#include "../core/operator.hpp"
#include "../core/backpressure.hpp"
#include "types.hpp"
#include "backpressure_signal.hpp"

namespace klstream {
// Thin adapter: reads occupancy of a FeatureBatch queue, publishes to
// BackpressureSignal so KeyedFeatureExtractOp's AlphaController can read it.
// Used by the B-only ablation architecture (fixed W, adaptive alpha).
template <typename Queue>
class BackpressurePublisherOp : public IOperator {
public:
    BackpressurePublisherOp(std::string name, Queue* watched_queue,
                             BackpressureSignal* signal)
        : IOperator(std::move(name)), tracker_(*watched_queue), queue_(watched_queue), signal_(signal) {}

    OpStatus tick() override {
        if (is_complete()) return OpStatus::Closed;
        tracker_.update();
        signal_->store(tracker_.ema());
        if (watched_closed_and_empty()) {
            mark_complete();
            return OpStatus::Closed;
        }
        return OpStatus::Idle;  // never pops a queue; always yields
    }

    void on_cancel() noexcept override { mark_cancelled(); }

private:
    bool watched_closed_and_empty() const noexcept { return queue_->closed_and_empty(); }
    EMAOccupancyTracker<Queue> tracker_;
    Queue* queue_;
    BackpressureSignal* signal_;
};
} // namespace klstream
