#include "klstream/core/operator.hpp"
#include "klstream/core/backpressure.hpp"
#include <iostream>
#include <cassert>
#include <thread>
#include <cmath>

using namespace klstream;

// Mock queue for testing occupancy tracking
struct MockQueue {
    double occ = 0.0;
    double occupancy() const noexcept { return occ; }
};

// Mock operator implementation
class MockOperator : public IOperator {
public:
    explicit MockOperator(std::string name) : IOperator(std::move(name)) {}

    void init() override {
        initialized = true;
    }

    OpStatus tick() override {
        ticks++;
        return OpStatus::Processed;
    }

    void shutdown() override {
        shutdown_called = true;
    }

    bool initialized = false;
    bool shutdown_called = false;
    int ticks = 0;
};

void test_operator_lifecycle() {
    MockOperator op("test_op");
    assert(op.name() == "test_op");
    assert(!op.initialized);
    assert(!op.shutdown_called);
    assert(op.ticks == 0);

    op.init();
    assert(op.initialized);

    OpStatus status = op.tick();
    assert(status == OpStatus::Processed);
    assert(op.ticks == 1);

    op.shutdown();
    assert(op.shutdown_called);
    std::cout << "Operator lifecycle tests passed!" << std::endl;
}

void test_ema_tracker() {
    MockQueue q;
    EMAOccupancyTracker<MockQueue> tracker(q, 0.10);
    assert(tracker.ema() == 0.0);

    q.occ = 0.5;
    tracker.update();
    // ema = 0.1 * 0.5 + 0.9 * 0.0 = 0.05
    assert(std::abs(tracker.ema() - 0.05) < 1e-9);

    q.occ = 0.8;
    tracker.update();
    // ema = 0.1 * 0.8 + 0.9 * 0.05 = 0.125
    assert(std::abs(tracker.ema() - 0.125) < 1e-9);

    assert(!tracker.soft_pressure()); // 0.125 <= 0.70
    assert(!tracker.hard_pressure()); // 0.8 <= 0.95

    q.occ = 0.96;
    assert(tracker.hard_pressure()); // 0.96 > 0.95

    std::cout << "EMA tracker tests passed!" << std::endl;
}

void test_rate_limiter() {
    TokenBucketRateLimiter limiter(100.0); // 100 tokens per sec
    assert(limiter.rate() == 100.0);

    // Consume first token immediately
    assert(limiter.try_consume());

    // Consume multiple tokens
    for (int i = 0; i < 50; ++i) {
        bool ok = limiter.try_consume();
        (void)ok;
    }

    std::cout << "Rate limiter tests passed!" << std::endl;
}

void test_backpressure_signal() {
    BackpressureSignal sig;
    assert(sig.ema_occupancy == 0.0);
    assert(sig.current_W == 0);
    assert(sig.current_alpha == 0.0);

    sig.ema_occupancy = 0.75;
    sig.current_W = 128;
    sig.current_alpha = 0.15;

    assert(sig.ema_occupancy == 0.75);
    assert(sig.current_W == 128);
    assert(sig.current_alpha == 0.15);

    std::cout << "Backpressure signal tests passed!" << std::endl;
}

int main() {
    test_operator_lifecycle();
    test_ema_tracker();
    test_rate_limiter();
    test_backpressure_signal();
    return 0;
}
