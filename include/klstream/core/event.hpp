#pragma once
// Event<T>: the fundamental unit of data flowing through KLStream queues.
// Trivially copyable; any payload type T must also be trivially copyable.

#include <cstdint>
#include <type_traits>

// Platform clock — included at file scope, never inside a function body.
#if defined(__APPLE__)
#  include <mach/mach_time.h>
#elif defined(__linux__)
#  include <time.h>
#else
#  include <chrono>
#endif

namespace klstream {

// ── now_ns() ─────────────────────────────────────────────────────────────────
inline std::uint64_t now_ns() noexcept {
#if defined(__APPLE__)
    // On macOS, mach_absolute_time() units depend on the hardware bus.
    // We cache the timebase info in a function-local static once.
    static const struct TimescaleCache {
        std::uint64_t numer, denom;
        TimescaleCache() {
            mach_timebase_info_data_t info{};
            mach_timebase_info(&info);
            numer = info.numer;
            denom = info.denom;
        }
    } kScale;
    return mach_absolute_time() * kScale.numer / kScale.denom;
#elif defined(__linux__)
    struct timespec ts{};
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return static_cast<std::uint64_t>(ts.tv_sec) * 1'000'000'000ULL
         + static_cast<std::uint64_t>(ts.tv_nsec);
#else
    using Clock = std::chrono::steady_clock;
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            Clock::now().time_since_epoch()).count());
#endif
}

// ── Event<T> ─────────────────────────────────────────────────────────────────
template <typename T>
struct Event {
    static_assert(std::is_trivially_copyable_v<T>,
                  "Event<T>: T must be trivially copyable (no heap, no vtable)");

    // Default-constructible and trivially copyable.
    Event() = default;

    std::uint64_t timestamp_ns{0};  // wall-clock or logical time (nanoseconds)
    std::uint32_t key{0};           // routing key (user_id, instrument_id, etc.)
    std::uint64_t seq{0};           // monotonic sequence number, assigned at source
    T             data{};

    // Call at ResultSink to measure end-to-end latency.
    [[nodiscard]] std::uint64_t latency_ns() const noexcept {
        std::uint64_t n = now_ns();
        return (n >= ingress_ns_) ? (n - ingress_ns_) : 0ULL;
    }

    // Source operators call this immediately before pushing to the first queue.
    void stamp_ingress(std::uint64_t t) noexcept { ingress_ns_ = t; }
    [[nodiscard]] std::uint64_t ingress_ns() const noexcept { return ingress_ns_; }

private:
    std::uint64_t ingress_ns_{0};
};

} // namespace klstream
