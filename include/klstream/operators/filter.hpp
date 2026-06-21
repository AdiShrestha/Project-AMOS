#pragma once
// FilterOperator<T>: forwards Event<T> only when the predicate returns true.

#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include <functional>

namespace klstream {

template <typename T>
class FilterOperator : public IOperator {
public:
    using Predicate = std::function<bool(const T&)>;
    using Queue     = SPSCQueue<Event<T>>;

    FilterOperator(std::string name, Queue* input, Queue* output, Predicate pred)
        : IOperator(std::move(name))
        , input_(input), output_(output), pred_(std::move(pred)) {}

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

        Event<T> ev;
        if (!input_->try_pop(&ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        if (!pred_(ev.data)) {
            // Dropped — still counts as Processed (we consumed an event)
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }

        if (output_->try_push(ev)) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }
        pending_     = ev;
        has_pending_ = true;
        if (metrics_) metrics_->events_blocked.increment();
        return OpStatus::Blocked;
    }

private:
    Queue*          input_;
    Queue*          output_;
    Predicate       pred_;
    Event<T>        pending_{};
    bool            has_pending_{false};
    OperatorMetrics* metrics_{nullptr};
};

} // namespace klstream
