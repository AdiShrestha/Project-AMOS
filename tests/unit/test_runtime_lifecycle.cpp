#include <cassert>
#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <thread>

#include "klstream/core/runtime.hpp"
#include "klstream/operators/source.hpp"
#include "klstream/operators/map.hpp"
#include "klstream/operators/sink.hpp"

using namespace klstream;

namespace {

struct ThrowingOperator final : IOperator {
    ThrowingOperator() : IOperator("thrower") {}
    OpStatus tick() override { throw std::runtime_error("intentional test failure"); }
};

void finite_pipeline_completes() {
    SPSCQueue<Event<int>> q1(16), q2(16);
    int produced = 0;
    int consumed = 0;
    SourceOperator<int> source("source", &q1,
        [&](Event<int>& out, std::uint64_t seq) {
            if (produced == 37) return false;
            out = Event<int>{seq + 1, 0, seq, produced++};
            return true;
        });
    MapOperator<int, int> map("map", &q1, &q2, [](int v) { return v * 2; });
    SinkOperator<int> sink("sink", &q2, [&](const Event<int>& ev) { assert(ev.data % 2 == 0); ++consumed; });

    Runtime runtime;
    const int w0 = runtime.add_worker();
    const int w1 = runtime.add_worker();
    runtime.register_op(&source, w0);
    runtime.register_op(&map, w0);
    runtime.register_op(&sink, w1);
    runtime.start();
    assert(runtime.wait_until_terminal_for(std::chrono::seconds(2)));
    assert(runtime.state() == RuntimeState::Completed);
    assert(produced == 37 && consumed == 37);
    assert(q1.closed_and_empty() && q2.closed_and_empty());
    runtime.stop();
    runtime.stop();
}

void empty_source_completes() {
    SPSCQueue<Event<int>> q(8);
    SourceOperator<int> source("empty", &q,
        [](Event<int>&, std::uint64_t) { return false; });
    Runtime runtime;
    const int worker = runtime.add_worker();
    runtime.register_op(&source, worker);
    runtime.start();
    assert(runtime.wait_until_terminal_for(std::chrono::seconds(1)));
    assert(runtime.state() == RuntimeState::Completed);
    assert(q.closed_and_empty());
}

void failure_is_terminal_and_nonblocking() {
    ThrowingOperator op;
    Runtime runtime;
    const int worker = runtime.add_worker();
    runtime.register_op(&op, worker);
    runtime.start();
    assert(runtime.wait_until_terminal_for(std::chrono::seconds(1)));
    assert(runtime.state() == RuntimeState::Failed);
    assert(runtime.terminal_error() != nullptr);
    runtime.stop();
}

void cancellation_is_distinct_from_failure() {
    SPSCQueue<Event<int>> q(16);
    SourceOperator<int> source("infinite", &q,
        [](Event<int>& out, std::uint64_t seq) {
            out = Event<int>{seq, 0, seq, 1};
            return true;
        });
    Runtime runtime;
    const int worker = runtime.add_worker();
    runtime.register_op(&source, worker);
    runtime.start();
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
    assert(runtime.cancel());
    assert(runtime.wait_until_terminal_for(std::chrono::seconds(1)));
    assert(runtime.state() == RuntimeState::Cancelled);
    assert(runtime.terminal_error() == nullptr);
    runtime.stop();
}

void registration_is_immutable_after_start() {
    SPSCQueue<Event<int>> q(8);
    SourceOperator<int> a("a", &q, [](Event<int>&, std::uint64_t) { return false; });
    SourceOperator<int> b("b", &q, [](Event<int>&, std::uint64_t) { return false; });
    Runtime runtime;
    const int worker = runtime.add_worker();
    runtime.register_op(&a, worker);
    bool threw = false;
    try { runtime.register_op(&a, worker); } catch (const std::logic_error&) { threw = true; }
    assert(threw);
    runtime.register_op(&b, worker);
    runtime.start();
    threw = false;
    try { runtime.add_worker(); } catch (const std::logic_error&) { threw = true; }
    assert(threw);
    runtime.stop();
}

} // namespace

int main() {
    finite_pipeline_completes();
    empty_source_completes();
    failure_is_terminal_and_nonblocking();
    cancellation_is_distinct_from_failure();
    registration_is_immutable_after_start();
    return 0;
}
