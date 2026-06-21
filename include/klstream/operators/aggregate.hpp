#pragma once
// AggregateOperator<In, State, Out>: stateful reduction — one State per key,
// updated per event; emits Event<Out> on every event (tumbling aggregate).
// Not used by BPFeat's hot path but included for completeness of the operator suite.

#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include <functional>
#include <unordered_map>

namespace klstream {

template <typename In, typename State, typename Out>
class AggregateOperator : public IOperator {
public:
    using UpdateFn = std::function<void(State&, const In&)>;
    using EmitFn   = std::function<Out(const State&)>;
    using InQueue  = SPSCQueue<Event<In>>;
    using OutQueue = SPSCQueue<Event<Out>>;

    AggregateOperator(std::string name, InQueue* input, OutQueue* output,
                      UpdateFn update, EmitFn emit)
        : IOperator(std::move(name))
        , input_(input), output_(output)
        , update_(std::move(update)), emit_(std::move(emit)) {}

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

        State& s = state_[in_ev.key];
        update_(s, in_ev.data);

        Event<Out> out_ev;
        out_ev.timestamp_ns = in_ev.timestamp_ns;
        out_ev.key          = in_ev.key;
        out_ev.seq          = in_ev.seq;
        out_ev.data         = emit_(s);
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
    InQueue*  input_;
    OutQueue* output_;
    UpdateFn  update_;
    EmitFn    emit_;
    std::unordered_map<std::uint32_t, State> state_;
    Event<Out>      pending_{};
    bool            has_pending_{false};
    OperatorMetrics* metrics_{nullptr};
};

} // namespace klstream
