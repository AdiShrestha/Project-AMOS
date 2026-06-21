#pragma once
#include <atomic>

namespace klstream {

// ── BackpressureSignal ───────────────────────────────────────────────────────
// Shared state between AdaptiveFeatureWindowOp (writer) and KeyedFeatureExtractOp (reader).
// Uses relaxed atomics; one tick of propagation delay is acceptable.
class BackpressureSignal {
public:
    void store(double load) noexcept { load_.store(load, std::memory_order_relaxed); }
    double load() const noexcept { return load_.load(std::memory_order_relaxed); }
private:
    std::atomic<double> load_{0.0};
};

} // namespace klstream
