#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <mutex>
#include <stdexcept>

namespace bpfeat {
inline void require_fraction(double value, const char* field) {
    if (!std::isfinite(value) || value < 0 || value > 1)
        throw std::invalid_argument(field);
}
struct PressureObservation {
    double value{0};
    std::uint64_t generation{0};
    std::uint64_t sampled_ns{0};
    bool available{false};
};
// A mutex makes value, generation and sampling time one coherent observation.
// The pipeline is not described as lock-free; SPSC indices use atomics.
class PressureSignal {
public:
    void store(double value, std::uint64_t sampled_ns) {
        require_fraction(value, "pressure must be finite and in [0,1]");
        std::lock_guard<std::mutex> lock(mu_);
        if (observation_.available && sampled_ns < observation_.sampled_ns)
            throw std::invalid_argument("pressure sample time decreased");
        observation_ = {value, observation_.generation + 1, sampled_ns, true};
    }
    PressureObservation load() const {
        std::lock_guard<std::mutex> lock(mu_);
        return observation_;
    }
private:
    mutable std::mutex mu_;
    PressureObservation observation_;
};

class OccupancyEMA {
public:
    explicit OccupancyEMA(double gain) : gain_(gain) {
        if (!std::isfinite(gain) || gain <= 0 || gain > 1)
            throw std::invalid_argument("occupancy gain must be in (0,1]");
    }
    double update(double value) {
        require_fraction(value, "invalid occupancy");
        value_ += gain_ * (value - value_);
        return value_;
    }
private:
    double gain_, value_{0};
};

class AlphaController {
public:
    AlphaController(double minimum, double maximum, double delta, double initial)
        : minimum_(minimum), maximum_(maximum), delta_(delta), current_(initial) {
        if (!std::isfinite(minimum) || !std::isfinite(maximum) || !std::isfinite(delta) ||
            !std::isfinite(initial) || minimum <= 0 || minimum > maximum || maximum > 1 ||
            delta <= 0 || initial < minimum || initial > maximum)
            throw std::invalid_argument("invalid alpha bounds, slew or initial value");
    }
    double update(double pressure) {
        require_fraction(pressure, "invalid alpha pressure");
        auto target = minimum_ + (maximum_ - minimum_) * pressure;
        current_ = std::clamp(current_ + std::clamp(target - current_, -delta_, delta_), minimum_, maximum_);
        return current_;
    }
    double current() const noexcept { return current_; }
private:
    double minimum_, maximum_, delta_, current_;
};

// The inherited update law is multiplicative decrease / multiplicative
// increase (MIMD), not AIMD. It changes batch size, not publication cadence.
// Its feedback sign is an experimental policy; no stability/benefit is asserted.
class MultiplicativeBatchController {
public:
    MultiplicativeBatchController(std::uint32_t minimum, std::uint32_t maximum,
                                 double low, double high, double shrink, double grow,
                                 std::uint32_t initial)
        : minimum_(minimum), maximum_(maximum), current_(initial), low_(low), high_(high),
          shrink_(shrink), grow_(grow) {
        require_fraction(low, "invalid low threshold");
        require_fraction(high, "invalid high threshold");
        if (!minimum || minimum > maximum || initial < minimum || initial > maximum || low >= high ||
            !std::isfinite(shrink) || shrink <= 0 || shrink >= 1 || !std::isfinite(grow) || grow <= 1)
            throw std::invalid_argument("invalid batch controller parameters");
    }
    std::uint32_t update(double pressure) {
        require_fraction(pressure, "invalid batch pressure");
        auto previous = current_;
        if (pressure > high_ && current_ > minimum_) {
            current_ = std::max(minimum_, static_cast<std::uint32_t>(std::floor(current_ * shrink_)));
        } else if (pressure < low_ && current_ < maximum_) {
            auto grown = std::min<double>(maximum_, std::max<double>(current_ + 1.0, std::floor(current_ * grow_)));
            current_ = static_cast<std::uint32_t>(grown);
        }
        int direction = current_ > previous ? 1 : (current_ < previous ? -1 : 0);
        if (direction) {
            if (last_direction_ && direction != last_direction_) ++direction_changes_;
            last_direction_ = direction;
            ++actions_;
        }
        return current_;
    }
    std::uint64_t actions() const noexcept { return actions_; }
    std::uint64_t direction_changes() const noexcept { return direction_changes_; }
private:
    std::uint32_t minimum_, maximum_, current_;
    double low_, high_, shrink_, grow_;
    int last_direction_{0};
    std::uint64_t actions_{0}, direction_changes_{0};
};
}
