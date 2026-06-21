#pragma once
// MapOperator<In, Out>: applies a pure function to each Event<In> and
// emits Event<Out>. The map function receives the payload (In) only;
// the operator preserves timestamp_ns, key, and seq from the input event.

#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include <functional>

namespace klstream {

template <typename In, typename Out>
class MapOperator : public IOperator {
public:
    using Fn       = std::function<Out(const In&)>;
    using InQueue  = SPSCQueue<Event<In>>;
    using OutQueue = SPSCQueue<Event<Out>>;

    MapOperator(std::string name, InQueue* input, OutQueue* output, Fn fn)
        : IOperator(std::move(name))
        , input_(input), output_(output), fn_(std::move(fn)) {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }

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

        Event<In> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        Event<Out> out_ev;
        out_ev.timestamp_ns = in_ev.timestamp_ns;
        out_ev.key          = in_ev.key;
        out_ev.seq          = in_ev.seq;
        out_ev.data         = fn_(in_ev.data);
        out_ev.stamp_ingress(in_ev.ingress_ns());

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
    InQueue*        input_;
    OutQueue*       output_;
    Fn              fn_;
    Event<Out>      pending_{};
    bool            has_pending_{false};
    OperatorMetrics* metrics_{nullptr};
};

} // namespace klstream
