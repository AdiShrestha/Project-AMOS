#pragma once
// BPFeat domain types — all trivially copyable so they can transit SPSC queues.
// static_assert enforcements match the implementation guide's mandate exactly.

#include "../core/config.hpp"
#include <cstdint>
#include <cstddef>
#include <type_traits>

namespace klstream {

// ── RawBehaviorEvent ─────────────────────────────────────────────────────────
// The type that crosses the BehaviorSource → KeyedFeatureExtractOp queue.
// Intentionally does NOT carry label/label_valid — those are evaluation-only
// fields that must not widen the hot-path payload (Section 13.3).
struct RawBehaviorEvent {
    std::uint32_t user_id;
    std::uint32_t item_id;
    std::uint16_t category_id;
    std::uint8_t  behavior_code;   // 0=pv, 1=cart, 2=fav, 3=buy (Taobao)
                                    // 0=transaction (ULB)
    float         amount;          // 0.0 for Taobao; transaction amount for ULB
};
static_assert(std::is_trivially_copyable_v<RawBehaviorEvent>);

// ── FeatureSnapshot ──────────────────────────────────────────────────────────
// The type that crosses KeyedFeatureExtractOp → [WindowOp] queue.
// Holds the feature vector for ONE user at ONE moment in time.
struct FeatureSnapshot {
    static constexpr std::size_t kDim = 4;  // ema_engagement, log_pv, log_cart_fav, recency

    std::uint32_t user_id;
    float x[kDim];          // feature vector in the order above
    float alpha_used;       // α[n] that was active when this snapshot was computed
    std::uint8_t  label;
    std::uint8_t  label_valid;
    std::uint8_t  is_burst_period;
    std::uint8_t  _pad{0};  // alignment padding
};
static_assert(std::is_trivially_copyable_v<FeatureSnapshot>);

// ── FeatureBatch ─────────────────────────────────────────────────────────────
// The type that crosses [WindowOp] → ScoringFlushOp queue.
// Holds up to MAX_FEATURE_BATCH FeatureSnapshots — a fixed-size array so
// the struct stays trivially copyable (no std::vector on the hot path).
struct FeatureBatch {
    FeatureSnapshot items[MAX_FEATURE_BATCH];
    std::uint32_t   count{0};
    std::uint64_t   first_seq{0};
    float           occupancy_at_window_start{0.0f};  // logged for Adaptive only

    void push_back(const FeatureSnapshot& s, std::uint64_t seq) noexcept {
        if (count == 0) first_seq = seq;
        if (count < MAX_FEATURE_BATCH) items[count++] = s;
    }
    [[nodiscard]] bool full(std::uint32_t target) const noexcept { return count >= target; }
};
static_assert(std::is_trivially_copyable_v<FeatureBatch>);

// ── ScoredResult ─────────────────────────────────────────────────────────────
// The type that crosses ScoringFlushOp → ResultSink queue.
struct ScoredResult {
    std::uint32_t user_id;
    double        score;           // logistic regression P(buy)
    std::uint8_t  label;
    std::uint8_t  label_valid;
    std::uint32_t window_size_used;
    float         alpha_used;
    float         staleness_sec;
    float         occupancy_at_decision;
};
static_assert(std::is_trivially_copyable_v<ScoredResult>);

} // namespace klstream
