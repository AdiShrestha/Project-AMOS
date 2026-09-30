#pragma once
#include <atomic>
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace klstream {

// ── BackpressureSignal ───────────────────────────────────────────────────────
// Shared state between AdaptiveFeatureWindowOp (writer) and KeyedFeatureExtractOp (reader).
// Uses relaxed atomics; one tick of propagation delay is acceptable.
class BackpressureSignal {
public:
    void store(double load) noexcept {
        if (!std::isfinite(load)) return;  // preserve last valid generation
        load = std::clamp(load, 0.0, 1.0);
        sequence_.fetch_add(1, std::memory_order_acq_rel);
        load_.store(load, std::memory_order_relaxed);
        sequence_.fetch_add(1, std::memory_order_release);
    }
    double load() const noexcept {
        for (;;) {
            const auto before = sequence_.load(std::memory_order_acquire);
            if (before & 1u) continue;
            const double value = load_.load(std::memory_order_relaxed);
            const auto after = sequence_.load(std::memory_order_acquire);
            if (before == after) return value;
        }
    }
    [[nodiscard]] std::uint64_t version() const noexcept {
        return sequence_.load(std::memory_order_acquire) / 2u;
    }
private:
    std::atomic<double> load_{0.0};
    std::atomic<std::uint64_t> sequence_{0};
};

} // namespace klstream
