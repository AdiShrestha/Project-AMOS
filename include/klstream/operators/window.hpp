#pragma once
// TumblingCountWindow<T, Out>: collects window_size_ Event<T>s, then applies
// an aggregation function and emits one Event<Out>. This is the FixedWindowOp
// reused by Baseline 1 (Section 15.1 of the build prompt).
//
// The window size is fixed at construction time (no runtime mutation needed
// for this baseline variant). AdaptiveFeatureWindowOp (Section 14) has its
// own internal buffer management with a runtime-variable target_w_.

#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include <cstdint>
#include <functional>
#include <vector>

namespace klstream {

template <typename T, typename Out>
class TumblingCountWindow : public IOperator {
public:
    using AggFn    = std::function<Out(const std::vector<T>&)>;
    using InQueue  = SPSCQueue<Event<T>>;
    using OutQueue = SPSCQueue<Event<Out>>;

    TumblingCountWindow(std::string name, InQueue* input, OutQueue* output,
                        std::uint32_t window_size, AggFn agg)
        : IOperator(std::move(name))
        , input_(input), output_(output)
        , window_size_(window_size), agg_(std::move(agg))
    {
        buffer_.reserve(window_size_);
    }

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }
    [[nodiscard]] std::uint32_t window_size() const noexcept { return window_size_; }

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

        Event<T> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        buffer_.push_back(in_ev.data);
        last_in_ev_ = in_ev;

        if (static_cast<std::uint32_t>(buffer_.size()) < window_size_) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }

        // Window full — emit.
        Event<Out> out_ev;
        out_ev.timestamp_ns = last_in_ev_.timestamp_ns;
        out_ev.key          = 0;
        out_ev.seq          = last_in_ev_.seq;
        out_ev.data         = agg_(buffer_);
        out_ev.stamp_ingress(last_in_ev_.ingress_ns());

        buffer_.clear();

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
    InQueue*          input_;
    OutQueue*         output_;
    std::uint32_t     window_size_;
    AggFn             agg_;
    std::vector<T>    buffer_;
    Event<T>          last_in_ev_{};
    Event<Out>        pending_{};
    bool              has_pending_{false};
    OperatorMetrics*  metrics_{nullptr};
};

} // namespace klstream
