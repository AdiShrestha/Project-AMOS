#include "klstream/core/config.hpp"
#include "klstream/core/event.hpp"
#include "klstream/core/metrics.hpp"
#include "klstream/core/pinning.hpp"
#include <iostream>
#include <cassert>
#include <type_traits>

int main() {
    using namespace klstream;

    // Config checks
    std::cout << "CACHE_LINE_SIZE: " << CACHE_LINE_SIZE << std::endl;
    std::cout << "DEFAULT_QUEUE_CAPACITY: " << DEFAULT_QUEUE_CAPACITY << std::endl;
    assert(DEFAULT_QUEUE_CAPACITY == 4096);
    assert(BP_SOFT_THRESHOLD == 0.70);

    // Event checks
    struct MyPayload {
        int x;
        double y;
    };
    static_assert(std::is_trivially_copyable_v<Event<MyPayload>>, "Event must be trivially copyable");
    auto ev = Event<MyPayload>::make(MyPayload{42, 3.14}, 123, 7);
    assert(ev.key == 123);
    assert(ev.seq == 7);
    assert(ev.data.x == 42);
    assert(ev.data.y == 3.14);
    assert(ev.latency_ns() >= 0);

    // Counter checks
    Counter counter;
    assert(counter.load() == 0);
    counter.increment();
    assert(counter.load() == 1);
    auto old = counter.reset();
    assert(old == 1);
    assert(counter.load() == 0);

    // Pinning checks
    apply_affinity(CoreAffinity::Performance);
    apply_affinity(CoreAffinity::Efficiency);
    apply_affinity(CoreAffinity::Any);

    std::cout << "Core utility tests passed!" << std::endl;
    return 0;
}
