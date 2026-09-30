#pragma once
// EMAUserState: per-user rolling state maintained by KeyedFeatureExtractOp.
// Holds the four feature components computed incrementally (O(1) per event).
// Stored in an unordered_map<uint32_t, EMAUserState> inside KeyedFeatureExtractOp.

#include <cstdint>
#include <cmath>
#include <algorithm>

namespace klstream {

struct EMAUserState {
    // Feature 0: EMA of engagement weight (controlled by α)
    float ema_engagement{0.0f};

    // Feature 1: raw count of pv events (log-transformed on export)
    std::uint32_t pv_count{0};

    // Feature 2: raw count of cart+fav events (log-transformed on export)
    std::uint32_t cart_fav_count{0};

    // New Feature: raw count of buy events
    std::uint32_t raw_buy_count{0};

    // New Feature: EMA of inter-event gaps
    float ema_recency{0.0f};

    // Feature 3: recency = normalized time since last event (clipped to [0,1])
    std::uint64_t last_ts_ns{0};  // epoch nanoseconds; subtraction stays exact

    // Update state for one incoming event.
    // alpha:       current α[n] from AlphaController (Mechanism B)
    // weight:      engagement weight for this event's behavior_code
    // ts_ns:       event timestamp in nanoseconds
    // behavior:    raw behavior_code (0=pv,1=cart,2=fav,3=buy)
    void update(float alpha, float weight, std::uint64_t ts_ns, std::uint8_t behavior, std::uint64_t prev_ts_ns) noexcept {
        ema_engagement = alpha * weight + (1.0f - alpha) * ema_engagement;
        if (behavior == 0)                     ++pv_count;
        else if (behavior == 1 || behavior == 2) ++cart_fav_count;
        else if (behavior == 3)                ++raw_buy_count;
        
        const double gap_sec = (prev_ts_ns > 0 && ts_ns >= prev_ts_ns)
            ? static_cast<double>(ts_ns - prev_ts_ns) / 1e9 : 0.0;
        ema_recency = alpha * static_cast<float>(gap_sec)
                    + (1.0f - alpha) * ema_recency;
        
        last_ts_ns = ts_ns;
    }

    // Export to a flat feature array.
    // recency_prev_sec: timestamp of the PREVIOUS event for this user (seconds),
    //                   or 0.0f if this is the first event.
    void export_features(float x[7], std::uint64_t prev_ts_ns) const noexcept {
        x[0] = ema_engagement;
        x[1] = std::log1p(static_cast<float>(pv_count));
        x[2] = std::log1p(static_cast<float>(cart_fav_count));
        // Recency: time since previous event for this user, clamped to 1hr, normalized.
        const double gap_sec = (prev_ts_ns > 0 && last_ts_ns >= prev_ts_ns)
            ? static_cast<double>(last_ts_ns - prev_ts_ns) / 1e9 : 0.0;
        x[3] = static_cast<float>(std::min(gap_sec, 3600.0) / 3600.0);
        
        std::uint32_t total_events = pv_count + cart_fav_count + raw_buy_count;
        x[4] = static_cast<float>(raw_buy_count) / static_cast<float>(std::max(1u, total_events));
        x[5] = std::log1p(static_cast<float>(raw_buy_count));
        x[6] = ema_recency;
    }
};

} // namespace klstream
