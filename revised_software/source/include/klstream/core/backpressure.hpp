// include/klstream/core/backpressure.hpp
#pragma once
#include "config.hpp"
#include <atomic>
#include <chrono>
#include <thread>
#include <cstdint>

namespace klstream {

// ── BackpressureSignal ────────────────────────────────────────────────────
//
// Shared backpressure state published by the window operator and read by
// the keyed feature extraction operator. Members are atomic to allow safe
// concurrent cross-thread reads and writes without locks.
struct BackpressureSignal {
    std::atomic<double>        ema_occupancy{0.0};
    std::atomic<std::uint32_t> current_W{0};
    std::atomic<double>        current_alpha{0.0};
};

// ── EMAOccupancyTracker ───────────────────────────────────────────────────
//
// Wraps any Queue that exposes .occupancy() and tracks an exponential
// moving average of its fill fraction.
//
// The EMA alpha parameter controls smoothing:
//   Small alpha (e.g. 0.05): slow to react, very smooth.
//   Large alpha (e.g. 0.30): reacts quickly — better for bursty workloads.
template <typename Queue>
class EMAOccupancyTracker {
public:
    explicit EMAOccupancyTracker(Queue& queue, double alpha = 0.10)
        : queue_(queue), alpha_(alpha), ema_(0.0) {}

    // Call once per tick() to update the EMA.
    void update() noexcept {
        double occ = queue_.occupancy();
        ema_ = alpha_ * occ + (1.0 - alpha_) * ema_;
    }

    [[nodiscard]] double ema() const noexcept { return ema_; }

    [[nodiscard]] bool soft_pressure() const noexcept {
        return ema_ > BP_SOFT_THRESHOLD;
    }

    [[nodiscard]] bool hard_pressure() const noexcept {
        return queue_.occupancy() > BP_HARD_THRESHOLD;
    }

private:
    Queue&      queue_;
    double      alpha_;
    double      ema_;
};

// ── TokenBucketRateLimiter ────────────────────────────────────────────────
//
// A simple token-bucket used by SourceOperator to smoothly rate-limit event
// generation when adaptive backpressure is enabled.
class TokenBucketRateLimiter {
public:
    explicit TokenBucketRateLimiter(double tokens_per_sec,
                                    double max_burst = 0.0)
        : rate_(tokens_per_sec)
        , tokens_(tokens_per_sec)
        , max_tokens_(max_burst > 0 ? max_burst : tokens_per_sec)
        , last_(std::chrono::steady_clock::now())
    {}

    [[nodiscard]] bool try_consume() noexcept {
        refill();
        if (tokens_ >= 1.0) {
            tokens_ -= 1.0;
            return true;
        }
        return false;
    }

    void set_rate(double tokens_per_sec) noexcept {
        rate_ = tokens_per_sec;
    }

    double rate() const noexcept { return rate_; }

private:
    void refill() noexcept {
        auto now     = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - last_).count();
        last_    = now;
        tokens_ += elapsed * rate_;
        if (tokens_ > max_tokens_) tokens_ = max_tokens_;
    }

    double rate_;
    double tokens_;
    double max_tokens_;
    std::chrono::steady_clock::time_point last_;
};

} // namespace klstream
