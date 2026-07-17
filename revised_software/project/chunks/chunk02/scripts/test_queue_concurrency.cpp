#include "klstream/core/spsc_queue.hpp"
#include "klstream/core/mpmc_queue.hpp"
#include <iostream>
#include <cassert>
#include <thread>
#include <vector>
#include <numeric>
#include <atomic>

using namespace klstream;

void test_spsc() {
    SPSCQueue<std::uint64_t> queue(1024);
    const std::uint64_t count = 1000000;

    std::thread producer([&]() {
        for (std::uint64_t i = 0; i < count; ++i) {
            while (!queue.try_push(i)) {
                std::this_thread::yield();
            }
        }
    });

    std::thread consumer([&]() {
        for (std::uint64_t i = 0; i < count; ++i) {
            std::uint64_t val = 0;
            while (!queue.try_pop(&val)) {
                std::this_thread::yield();
            }
            assert(val == i);
        }
    });

    producer.join();
    consumer.join();
    std::cout << "SPSC concurrency test passed!" << std::endl;
}

void test_mpmc() {
    MPMCQueue<std::uint64_t> queue(1024);
    const std::uint64_t count = 1000000;
    const int num_producers = 4;
    const int num_consumers = 4;
    std::atomic<std::uint64_t> pushed_sum{0};
    std::atomic<std::uint64_t> popped_sum{0};
    std::atomic<std::uint64_t> items_to_push{count};
    std::atomic<std::uint64_t> items_to_pop{count};

    std::vector<std::thread> producers;
    for (int i = 0; i < num_producers; ++i) {
        producers.emplace_back([&]() {
            for (;;) {
                std::uint64_t remaining = items_to_push.load(std::memory_order_relaxed);
                if (remaining == 0) break;
                if (items_to_push.compare_exchange_weak(remaining, remaining - 1, std::memory_order_relaxed)) {
                    std::uint64_t val = remaining;
                    while (!queue.try_push(val)) {
                        std::this_thread::yield();
                    }
                    pushed_sum.fetch_add(val, std::memory_order_relaxed);
                }
            }
        });
    }

    std::vector<std::thread> consumers;
    for (int i = 0; i < num_consumers; ++i) {
        consumers.emplace_back([&]() {
            for (;;) {
                std::uint64_t remaining = items_to_pop.load(std::memory_order_relaxed);
                if (remaining == 0) break;
                std::uint64_t val = 0;
                if (queue.try_pop(&val)) {
                    popped_sum.fetch_add(val, std::memory_order_relaxed);
                    items_to_pop.fetch_sub(1, std::memory_order_relaxed);
                } else {
                    std::this_thread::yield();
                }
            }
        });
    }

    for (auto& t : producers) t.join();
    for (auto& t : consumers) t.join();

    assert(pushed_sum.load() == popped_sum.load());
    std::cout << "MPMC concurrency test passed!" << std::endl;
}

int main() {
    test_spsc();
    test_mpmc();
    return 0;
}
