#pragma once
// Per-operator metrics counters — all atomics so the main thread can read
// them safely while the worker thread increments them, without locking.
// These mirror Project 2's OperatorMetrics exactly.

#include <atomic>
#include <cstdint>
#include <string>

namespace klstream {

struct AtomicCounter {
    std::atomic<std::uint64_t> value{0};
    void increment() noexcept { value.fetch_add(1, std::memory_order_relaxed); }
    void add(std::uint64_t n) noexcept { value.fetch_add(n, std::memory_order_relaxed); }
    [[nodiscard]] std::uint64_t load() const noexcept {
        return value.load(std::memory_order_relaxed);
    }
    void reset() noexcept { value.store(0, std::memory_order_relaxed); }
};

struct OperatorMetrics {
    std::string op_name;
    AtomicCounter events_processed;   // tick() returned Processed
    AtomicCounter events_idle;        // tick() returned Idle
    AtomicCounter events_blocked;     // tick() returned Blocked

    explicit OperatorMetrics(std::string name) : op_name(std::move(name)) {}

    [[nodiscard]] std::uint64_t total_ticks() const noexcept {
        return events_processed.load() + events_idle.load() + events_blocked.load();
    }

    void print(std::ostream& os) const;
};

} // namespace klstream

// ── Implementation (header-only) ─────────────────────────────────────────────
#include <ostream>

namespace klstream {
inline void OperatorMetrics::print(std::ostream& os) const {
    os << "[" << op_name << "] "
       << "processed=" << events_processed.load()
       << " idle=" << events_idle.load()
       << " blocked=" << events_blocked.load()
       << " total=" << total_ticks()
       << "\n";
}
} // namespace klstream
