#include "klstream/core/runtime.hpp"
#include "klstream/core/spsc_queue.hpp"
#include <iostream>
#include <cassert>
#include <atomic>

using namespace klstream;

const std::uint64_t TARGET_COUNT = 10000;
std::atomic<std::uint64_t> emitted_count{0};
std::atomic<std::uint64_t> processed_count{0};

// Source operator that emits a fixed count of events and increments counter
class MockSource : public IOperator {
public:
    MockSource(std::string name, SPSCQueue<int>& out_q)
        : IOperator(std::move(name)), out_q_(out_q) {}

    OpStatus tick() override {
        if (emitted_count.load(std::memory_order_relaxed) >= TARGET_COUNT) {
            return OpStatus::Idle;
        }
        if (out_q_.try_push(1)) {
            emitted_count.fetch_add(1, std::memory_order_relaxed);
            return OpStatus::Processed;
        }
        return OpStatus::Blocked;
    }

private:
    SPSCQueue<int>& out_q_;
};

// Sink operator that processes events and increments counter
class MockSink : public IOperator {
public:
    MockSink(std::string name, SPSCQueue<int>& in_q)
        : IOperator(std::move(name)), in_q_(in_q) {}

    OpStatus tick() override {
        int val = 0;
        if (in_q_.try_pop(&val)) {
            processed_count.fetch_add(1, std::memory_order_relaxed);
            return OpStatus::Processed;
        }
        return OpStatus::Idle;
    }

private:
    SPSCQueue<int>& in_q_;
};

int main() {
    Runtime rt;
    rt.add_worker(CoreAffinity::Performance);
    rt.add_worker(CoreAffinity::Efficiency);

    SPSCQueue<int> queue(1024);

    MockSource source("source", queue);
    MockSink sink("sink", queue);

    rt.register_op(&source, 0);
    rt.register_op(&sink, 1);

    rt.start();

    // Block wait until match occurs (INV-001)
    bool matched = rt.wait_until_matched(emitted_count, processed_count,
                                         std::chrono::milliseconds(2),
                                         std::chrono::seconds(5));

    rt.stop();

    std::cout << "Matched status: " << (matched ? "TRUE" : "FALSE") << std::endl;
    std::cout << "Emitted: " << emitted_count.load() << std::endl;
    std::cout << "Processed: " << processed_count.load() << std::endl;

    assert(matched);
    assert(emitted_count.load() == TARGET_COUNT);
    assert(processed_count.load() == TARGET_COUNT);

    std::cout << "Exact termination handshake tests passed!" << std::endl;
    return 0;
}
