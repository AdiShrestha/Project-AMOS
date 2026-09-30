#pragma once
#include "controllers.hpp"
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <unordered_map>

namespace bpfeat {
inline constexpr std::size_t FEATURE_DIMENSION = 7;
inline constexpr const char* FEATURE_SCHEMA = "bpfeat.taobao.features.v2";
struct RawEvent {
    std::uint64_t seq{0}, event_ts_ns{0}, key{0}, item_id{0}, category_id{0};
    std::uint8_t behavior_code{0};
};
struct FeatureSnapshot {
    RawEvent event;
    std::array<double, FEATURE_DIMENSION> x{};
    double alpha{0};
    PressureObservation pressure_used;
    std::uint64_t created_ns{0};
};
struct UserState {
    double engagement_ema{0}, gap_ema{0};
    std::uint64_t pv{0}, cart_fav{0}, buy{0}, count{0}, last_ns{0};
    bool seen{false};
};
class KeyedFeatures {
public:
    explicit KeyedFeatures(std::size_t max_keys) : max_keys_(max_keys) {
        if (!max_keys) throw std::invalid_argument("max_keys must be positive");
    }
    FeatureSnapshot update(const RawEvent& event, double alpha, std::uint64_t created_ns,
                           PressureObservation observation = {}) {
        if (event.behavior_code > 3) throw std::invalid_argument("unknown Taobao behavior");
        if (!std::isfinite(alpha) || alpha <= 0 || alpha > 1)
            throw std::invalid_argument("feature alpha must be in (0,1]");
        auto it = users_.find(event.key);
        if (it == users_.end()) {
            if (users_.size() >= max_keys_) throw std::runtime_error("key budget exhausted; no silent drop");
            it = users_.emplace(event.key, UserState{}).first;
        }
        auto& state = it->second;
        if (state.seen && event.event_ts_ns < state.last_ns)
            throw std::invalid_argument("event time decreased for key");
        if (state.count == std::numeric_limits<std::uint64_t>::max())
            throw std::overflow_error("feature count overflow");
        const double gap = state.seen ? static_cast<double>(event.event_ts_ns - state.last_ns) / 1e9 : 0;
        // Declared feature-design constants, not fitted results. Sensitivity is
        // required before claims. Same seven Taobao features as legacy.
        constexpr double weights[] = {1, 3, 2, 5};
        state.engagement_ema += alpha * (weights[event.behavior_code] - state.engagement_ema);
        state.gap_ema += alpha * (gap - state.gap_ema);
        ++state.count;
        if (event.behavior_code == 0) ++state.pv;
        else if (event.behavior_code == 3) ++state.buy;
        else ++state.cart_fav;
        state.last_ns = event.event_ts_ns;
        state.seen = true;
        // Features use the current observed event. Future-purchase labels must
        // exclude the current timestamp, or choose pre-event features explicitly.
        return {event, {state.engagement_ema, std::log1p(state.pv), std::log1p(state.cart_fav),
                       std::min(gap, 3600.0) / 3600.0, static_cast<double>(state.buy) / state.count,
                       std::log1p(state.buy), state.gap_ema}, alpha, observation, created_ns};
    }
private:
    std::size_t max_keys_;
    std::unordered_map<std::uint64_t, UserState> users_;
};
}
