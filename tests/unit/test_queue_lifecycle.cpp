#include <atomic>
#include <cassert>
#include <cstdint>
#include <mutex>
#include <thread>
#include <vector>
#include <iostream>
#include <string>
#include <limits>

#include "klstream/core/spsc_queue.hpp"
#include "klstream/core/mpmc_queue.hpp"
#include "klstream/feature/backpressure_signal.hpp"
#include "klstream/core/metrics.hpp"

using namespace klstream;

static void spsc_boundaries() {
    SPSCQueue<std::uint64_t> q(8);
    for (std::uint64_t i = 0; i < 7; ++i) assert(q.try_push(i));
    assert(!q.try_push(7));
    for (std::uint64_t i = 0; i < 7; ++i) { std::uint64_t x = 0; assert(q.try_pop(&x)); assert(x == i); }
    assert(q.empty());
    assert(q.close());
    assert(!q.close());
    assert(!q.try_push(9));
    std::uint64_t x = 0;
    assert(!q.try_pop(&x));
    assert(q.closed_and_empty());
    assert(q.producer_count() == 1 && q.consumer_count() == 1);
    assert(q.usable_capacity() == 7);
}

static void mpmc_concurrency() {
    MPMCQueue<std::uint64_t> q(1024);
    constexpr std::uint64_t per_producer = 1000;
    constexpr std::uint64_t producer_count = 2;
    constexpr std::uint64_t total = per_producer * producer_count;
    std::vector<std::atomic<bool>> seen(total);
    for (auto& bit : seen) bit.store(false);
    std::atomic<std::uint64_t> consumed{0};
    std::vector<std::thread> producers;
    for (std::uint64_t p = 0; p < producer_count; ++p) {
        producers.emplace_back([&, p] {
            for (std::uint64_t i = 0; i < per_producer; ++i) {
                const auto value = p * per_producer + i;
                while (!q.try_push(value)) std::this_thread::yield();
            }
        });
    }
    std::vector<std::thread> consumers;
    for (int c = 0; c < 2; ++c) {
        consumers.emplace_back([&] {
            while (consumed.load() < total) {
                std::uint64_t value = 0;
                if (q.try_pop(&value)) {
                    assert(value < total);
                    assert(!seen[value].exchange(true));
                    consumed.fetch_add(1);
                } else std::this_thread::yield();
            }
        });
    }
    for (auto& t : producers) t.join();
    for (auto& t : consumers) t.join();
    q.close();
    assert(consumed == total);
    for (const auto& bit : seen) assert(bit.load());
    assert(q.closed_and_empty());
    assert(std::string(q.cardinality()) == "MPMC");
}

static void pressure_and_metrics_snapshot() {
    BackpressureSignal signal;
    std::atomic<bool> bad{false};
    std::thread writer([&] { for (std::uint64_t i = 1; i <= 10000; ++i) signal.store((i % 101) / 100.0); });
    std::thread reader([&] { for (int i = 0; i < 10000; ++i) { const double x = signal.load(); if (x < 0.0 || x > 1.0) bad.store(true); } });
    writer.join(); reader.join();
    assert(!bad.load());
    assert(signal.version() > 0);
    const auto version_before_invalid = signal.version();
    signal.store(-3.0);
    assert(signal.load() == 0.0);
    signal.store(3.0);
    assert(signal.load() == 1.0);
    const auto version_before_nan = signal.version();
    signal.store(std::numeric_limits<double>::quiet_NaN());
    assert(signal.version() == version_before_nan);
    assert(signal.version() >= version_before_invalid);
    MetricsReporter reporter;
    OperatorMetrics metrics("queue-test");
    reporter.add(&metrics);
    reporter.start(); reporter.start(); reporter.stop(); reporter.stop();
}

int main() {
    spsc_boundaries();
    mpmc_concurrency();
    pressure_and_metrics_snapshot();
    std::cout << "queue_lifecycle=PASS\n";
    return 0;
}
