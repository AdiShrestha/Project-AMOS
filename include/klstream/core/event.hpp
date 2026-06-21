#pragma once
// Event<T>: the fundamental unit of data flowing through KLStream queues.
// Trivially copyable; any payload type T must also be trivially copyable.
// This is the load-bearing constraint that keeps SPSC queue push/pop
// copy-only (no move, no virtual dispatch, no heap allocation on the hot path).

#include <cstdint>
#include <type_traits>

namespace klstream {

template <typename T>
struct Event {
    static_assert(std::is_trivially_copyable_v<T>,
                  "Event<T>: T must be trivially copyable (no heap, no vtable)");

    std::uint64_t timestamp_ns{0};  // wall-clock or logical time (nanoseconds)
    std::uint32_t key{0};           // routing key (user_id, instrument_id, etc.)
    std::uint64_t seq{0};           // monotonic sequence number, assigned at source

    T data{};

    // Latency from creation to now (call this at ResultSink, not mid-pipeline)
    [[nodiscard]] std::uint64_t latency_ns() const noexcept;

private:
    std::uint64_t ingress_ns_{0};   // set by source operator at emission time

public:
    // Source operators call this immediately before pushing to the first queue.
    void stamp_ingress(std::uint64_t now_ns) noexcept { ingress_ns_ = now_ns; }
    [[nodiscard]] std::uint64_t ingress_ns() const noexcept { return ingress_ns_; }
};

// ── Wall-clock helper ─────────────────────────────────────────────────────────
// Prefer CLOCK_MONOTONIC_RAW on Linux; falls back to CLOCK_MONOTONIC on macOS.
inline std::uint64_t now_ns() noexcept {
#if defined(__APPLE__)
    #include <mach/mach_time.h>
    // Use mach_absolute_time converted to ns on Apple platforms
    static mach_timebase_info_data_t tbi = [](){
        mach_timebase_info_data_t t; mach_timebase_info(&t); return t;
    }();
    return mach_absolute_time() * tbi.numer / tbi.denom;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return static_cast<std::uint64_t>(ts.tv_sec) * 1'000'000'000ULL
         + static_cast<std::uint64_t>(ts.tv_nsec);
#endif
}

template <typename T>
std::uint64_t Event<T>::latency_ns() const noexcept {
    auto n = now_ns();
    return (n >= ingress_ns_) ? (n - ingress_ns_) : 0ULL;
}

} // namespace klstream
