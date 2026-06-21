#pragma once
// KeyedFeatureExtractOp: Map operator that converts RawBehaviorEvent into
// FeatureSnapshot by maintaining per-user EMAUserState in an unordered_map.
//
// Also owns the AlphaController (Mechanism B) — the continuous, slew-rate-
// bounded IIR-pole actuator driven by the shared BackpressureSignal.
// The sign-flip relative to Project 1 is intentional and documented in
// Section 2 Decision 3 of the build prompt: rising occupancy RAISES α
// (shorter effective memory, more reactive), opposite of Project 1 where
// rising load lowers α.
//
// Ownership model (Section 8.3):
//   AdaptiveFeatureWindowOp → OWNS + WRITES BackpressureSignal
//   KeyedFeatureExtractOp  → READS BackpressureSignal (pointer may be nullptr
//                            for non-Adaptive architectures, in which case
//                            fixed_alpha_ is used throughout)

#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "backpressure_signal.hpp"
#include "types.hpp"
#include "user_state.hpp"
#include "engagement.hpp"
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <unordered_map>

namespace klstream {

// ── AlphaController ───────────────────────────────────────────────────────────
// Pure control logic for Mechanism B. Separated from the operator for unit
// testing (Section 29: test_alpha_controller.cpp).
class AlphaController {
public:
    AlphaController(float alpha_min = 0.02f, float alpha_max = 0.30f,
                    float d_alpha_max = 0.01f)
        : alpha_min_(alpha_min), alpha_max_(alpha_max)
        , d_alpha_max_(d_alpha_max)
        , alpha_(alpha_min)   // start calm (long memory)
    {}

    // Called once per raw event. occupancy ∈ [0,1] from BackpressureSignal.
    // α[n] = α_min + (α_max - α_min)*L[n], sign-flipped vs. Project 1.
    // Slew-rate clamp: |Δα| ≤ d_alpha_max per call.
    float update(float occupancy) noexcept {
        float target = alpha_min_ + (alpha_max_ - alpha_min_) * occupancy;
        float delta  = target - alpha_;
        delta = std::clamp(delta, -d_alpha_max_, d_alpha_max_);
        alpha_ = std::clamp(alpha_ + delta, alpha_min_, alpha_max_);
        return alpha_;
    }

    [[nodiscard]] float current() const noexcept { return alpha_; }
    [[nodiscard]] float alpha_min() const noexcept { return alpha_min_; }
    [[nodiscard]] float alpha_max() const noexcept { return alpha_max_; }

private:
    float alpha_min_, alpha_max_, d_alpha_max_;
    float alpha_;
};

// ── KeyedFeatureExtractOp ─────────────────────────────────────────────────────
class KeyedFeatureExtractOp : public IOperator {
public:
    using InQueue  = SPSCQueue<Event<RawBehaviorEvent>>;
    using OutQueue = SPSCQueue<Event<FeatureSnapshot>>;

    // signal: pointer to the shared BackpressureSignal (nullptr → fixed α).
    // fixed_alpha: used when signal == nullptr (non-Adaptive architectures).
    KeyedFeatureExtractOp(std::string name, InQueue* input, OutQueue* output,
                          BackpressureSignal* signal = nullptr,
                          float fixed_alpha = 0.10f,
                          float alpha_min = 0.02f, float alpha_max = 0.30f,
                          float d_alpha_max = 0.01f)
        : IOperator(std::move(name))
        , input_(input), output_(output)
        , signal_(signal)
        , fixed_alpha_(fixed_alpha)
        , alpha_ctrl_(alpha_min, alpha_max, d_alpha_max)
    {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }

    // For controller trace logging (Section 19)
    [[nodiscard]] float last_alpha() const noexcept {
        return signal_ ? alpha_ctrl_.current() : fixed_alpha_;
    }

    // For unit testing: expose current user count
    [[nodiscard]] std::size_t user_count() const noexcept { return users_.size(); }

    OpStatus tick() override {
        if (has_pending_) {
            if (output_->try_push(pending_)) {
                has_pending_ = false;
                if (metrics_) metrics_->events_processed.increment();
                return OpStatus::Processed;
            }
            if (metrics_) metrics_->events_blocked.increment();
            return OpStatus::Blocked;
        }

        Event<RawBehaviorEvent> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        const auto& raw = in_ev.data;

        // ── Mechanism B: update α from shared backpressure signal ──────────
        float alpha;
        if (signal_) {
            float occ = static_cast<float>(signal_->load());
            alpha = alpha_ctrl_.update(occ);
        } else {
            alpha = fixed_alpha_;
        }

        // ── Per-key state update ────────────────────────────────────────────
        if (users_.size() >= MAX_TRACKED_USERS && users_.count(raw.user_id) == 0) {
            // Overflow: drop rather than silently corrupt another user's state.
            // In production this would trigger an alert; here we log and skip.
            if (metrics_) metrics_->events_blocked.increment();
            return OpStatus::Idle;
        }

        auto& state = users_[raw.user_id];
        float prev_ts_sec = state.last_ts_ns;  // last_ts_ns stores seconds (confusing name, fix below)
        float ts_sec = static_cast<float>(raw.event_ts_ns) / 1e9f;

        float weight = (raw.amount > 0.0f)
            ? raw.amount              // ULB mode: use transaction amount
            : engagement_weight(raw.behavior_code);  // Taobao mode

        state.update(alpha, weight, ts_sec, raw.behavior_code);

        // ── Build FeatureSnapshot ───────────────────────────────────────────
        FeatureSnapshot snap{};
        snap.user_id    = raw.user_id;
        snap.alpha_used = alpha;
        state.export_features(snap.x, prev_ts_sec);

        // label / label_valid: looked up via parallel vector in BehaviorSource
        // (Section 13.3). We store the seq so the wiring code can join.
        // For now leave label fields zero — they are populated by BehaviorSource's
        // label_for_seq() call in the wiring code (main.cpp Section 23).
        snap.label       = 0;
        snap.label_valid = 0;
        snap.event_ts_ns = raw.event_ts_ns;

        Event<FeatureSnapshot> out_ev{in_ev.timestamp_ns, in_ev.key, in_ev.seq, snap};

        if (output_->try_push(out_ev)) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }
        pending_     = out_ev;
        has_pending_ = true;
        if (metrics_) metrics_->events_blocked.increment();
        return OpStatus::Blocked;
    }

private:
    InQueue*           input_;
    OutQueue*          output_;
    BackpressureSignal* signal_;   // nullptr for non-Adaptive architectures
    float              fixed_alpha_;
    AlphaController    alpha_ctrl_;

    std::unordered_map<std::uint32_t, EMAUserState> users_;

    Event<FeatureSnapshot> pending_{};
    bool                   has_pending_{false};
    OperatorMetrics*       metrics_{nullptr};
};

} // namespace klstream
