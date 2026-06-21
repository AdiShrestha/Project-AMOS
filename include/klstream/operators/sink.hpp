#pragma once
// SinkOperator<T>: terminal operator — pops Event<T> and calls a consumer
// function. Does not push to any output queue.
// For BPFeat, ResultSink (Section 19) is a specialised version that writes CSV;
// this generic base covers simple lambda sinks used in tests.

#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include <functional>

namespace klstream {

template <typename T>
class SinkOperator : public IOperator {
public:
    using Consumer = std::function<void(const Event<T>&)>;
    using InQueue  = SPSCQueue<Event<T>>;

    SinkOperator(std::string name, InQueue* input, Consumer consumer)
        : IOperator(std::move(name))
        , input_(input), consumer_(std::move(consumer)) {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }

    OpStatus tick() override {
        Event<T> ev;
        if (!input_->try_pop(&ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }
        consumer_(ev);
        if (metrics_) metrics_->events_processed.increment();
        return OpStatus::Processed;
    }

private:
    InQueue*        input_;
    Consumer        consumer_;
    OperatorMetrics* metrics_{nullptr};
};

} // namespace klstream
