#pragma once
// Engagement weight table (Taobao UserBehavior).
// Maps behavior_code → float weight, used by both the C++ pipeline and
// train_classifier.py (which replicates the same table in Python).
//
// Semantic justification (Section 13.2 of the build prompt):
//   pv (0)  → 1.0  baseline page-view engagement
//   cart(1) → 3.0  active intent signal
//   fav (2) → 2.0  passive intent signal
//   buy (3) → 5.0  conversion — highest weight, drives α-controlled EMA
//
// For ULB Credit Card Fraud (Section 13.4), the amount field replaces the
// table lookup — the calling code checks dataset mode before calling
// engagement_weight().

#include <cstdint>

namespace klstream {

// Table-driven lookup — behavior_code values outside [0,3] return 1.0f.
inline constexpr float ENGAGEMENT_WEIGHTS[4] = { 1.0f, 3.0f, 2.0f, 5.0f };

inline float engagement_weight(std::uint8_t behavior_code) noexcept {
    if (behavior_code < 4) return ENGAGEMENT_WEIGHTS[behavior_code];
    return 1.0f;  // unknown code — treat as baseline pv
}

} // namespace klstream
