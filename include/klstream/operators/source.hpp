#pragma once
// SourceOperator<T>: wraps a generator function and emits Event<T> into
// an SPSC queue. The generator signature is:
//     bool gen(Event<T>& out, uint64_t seq)  → true = emitted, false = done
// Returns Done once the generator returns false.

#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include <cstdint>
#include <functional>

namespace klstream {

template <typename T>
class SourceOperator : public IOperator {
public:
    using Generator = std::function<bool(Event<T>&, std::uint64_t)>;
    using OutQueue  = SPSCQueue<Event<T>>;

    SourceOperator(std::string name, OutQueue* output, Generator gen)
        : IOperator(std::move(name))
        , output_(output), gen_(std::move(gen)) {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }

    OpStatus tick() override {
        if (done_) return OpStatus::Done;

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
        if (!gen_(ev, seq_)) {
            done_ = true;
            return OpStatus::Done;
        }
        ev.seq = seq_++;
        ev.stamp_ingress(now_ns());

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
    OutQueue*       output_;
    Generator       gen_;
    std::uint64_t   seq_{0};
    Event<T>        pending_{};
    bool            has_pending_{false};
    bool            done_{false};
    OperatorMetrics* metrics_{nullptr};
};

} // namespace klstream
