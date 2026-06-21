#pragma once
// Backpressure primitives.
//
//   EMAOccupancyTracker<Queue>  — wraps any Queue with .occupancy() → double,
//                                 maintains an EMA of recent occupancy readings.
//                                 Reused UNMODIFIED across Project 2's
//                                 AdaptiveWindowOp and Project 3's
//                                 AdaptiveFeatureWindowOp.
//
//   BackpressureSignal          — atomic shared state published by
//                                 AdaptiveFeatureWindowOp (owner/writer) and
//                                 read by KeyedFeatureExtractOp (reader).
//                                 Single-writer / multi-reader; writer uses
//                                 relaxed stores, readers use relaxed loads —
//                                 the worst that can happen is one tick of lag,
//                                 which is acceptable and documented.
//
//   TokenBucketRateLimiter      — for the RateThrottleSource baseline (Section 16).

#include "config.hpp"
#include <atomic>
#include <chrono>
#include <cstdint>

namespace klstream {

// ── EMAOccupancyTracker ───────────────────────────────────────────────────────
template <typename Queue>
class EMAOccupancyTracker {
public:
    explicit EMAOccupancyTracker(const Queue& q, double alpha = EMA_ALPHA_DEFAULT)
        : queue_(q), alpha_(alpha) {}

    // Call once per tick() of the owning operator to refresh the EMA.
    void update() noexcept {
        double occ = queue_.occupancy();
        ema_ = alpha_ * occ + (1.0 - alpha_) * ema_;
    }

    [[nodiscard]] double ema() const noexcept { return ema_; }
    [[nodiscard]] bool soft_pressure() const noexcept { return ema_ >= BP_SOFT_THRESHOLD; }
    [[nodiscard]] bool low_pressure()  const noexcept { return ema_ <  BP_LOW_THRESHOLD; }

private:
    const Queue& queue_;
    double alpha_;
    double ema_{0.0};
};

// ── BackpressureSignal ────────────────────────────────────────────────────────
// Shared between AdaptiveFeatureWindowOp (writer) and KeyedFeatureExtractOp
// (reader). Plain struct; pointer shared via main()'s lifetime.
struct BackpressureSignal {
    std::atomic<double> ema_occupancy{0.0};  // written by AdaptiveFeatureWindowOp

    [[nodiscard]] double load() const noexcept {
        return ema_occupancy.load(std::memory_order_relaxed);
    }
};

// ── TokenBucketRateLimiter ────────────────────────────────────────────────────
// Used by RateThrottleSource (Baseline 3, Section 16). Thread-safe only when
// accessed by a single source thread.
class TokenBucketRateLimiter {
public:
    TokenBucketRateLimiter(double tokens_per_sec, double max_burst)
        : rate_(tokens_per_sec), tokens_(max_burst), max_burst_(max_burst)
        , last_(std::chrono::steady_clock::now()) {}

    // Returns true if a token was consumed (may proceed), false if bucket empty.
    [[nodiscard]] bool try_consume() noexcept {
        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - last_).count();
        last_ = now;
        tokens_ = std::min(max_burst_, tokens_ + elapsed * rate_);
        if (tokens_ >= 1.0) { tokens_ -= 1.0; return true; }
        return false;
    }

    void set_rate(double r) noexcept { rate_ = r; }
    [[nodiscard]] double rate() const noexcept { return rate_; }

private:
    double rate_;
    double tokens_;
    double max_burst_;
    std::chrono::steady_clock::time_point last_;
};

} // namespace klstream
