# BPFeat — Hardening Pass for IEEE Conference Submission
## Complete Fix & Extension Prompt (for Copilot / coding agent)

---

## 0. How to Read This Prompt

This is a hardening pass — not a new project. The existing codebase (described in
`bpfeat_build_prompt.md`) is architecturally sound and compiles cleanly. The gaps
below were identified by a two-pass literature review (Gemini deep research +
independent cross-checking) and represent exactly the set of issues that would
cause rejection at IEEE venues. Work through every section in order; each section
states what file to change, what to add, and why it matters for the paper.

**Do not touch** `klstream/core/`, `klstream/operators/`, or any file that already
passes the 6/6 unit tests unless a section below explicitly says to. The core
runtime is not the problem.

At the very end of every experiment run, print the diagnostic block described in
Section 10. This is mandatory — it produces the output the paper author needs to
inspect, cite, and paste back for judgment before writing up results.

---

## 1. Venue and Timeline — Critical Corrections

**IT4D is NOT the right venue for this paper.** Research confirmed that IT4D
(Kathmandu) publishes in the Indian Journal of Science and Technology or Springer
volumes, NOT in the IEEE Xplore main track. A full systems paper on lock-free C++
backpressure mechanisms would receive an immediate desk rejection there as out of
scope. Do NOT update code for IT4D. Write all paper documentation and experiment
framing for the following real targets:

- **Primary target — IEEE BigData 2026**: Deadline **August 21, 2026** (approx.
  8 weeks from now). Phoenix, AZ, December 14-17, 2026. Full IEEE Xplore-indexed.
  10-page limit (including references). 17-18% acceptance rate. This is the
  IMMEDIATE deadline — all experiments must be completed and the draft must be
  ready in time.
- **Secondary target — IEEE ICDE 2027**: Round 1 deadline approximately June 2026
  (already past for 2026 cycle; target 2027 cycle). 12-page limit. The ideal home
  for this paper given its data-engineering focus, but requires more lead time.
- **Tertiary target — IEEE ICDCS 2027**: December 2026 deadline. 11-page limit.
  Right for the backpressure/distributed-control framing.

Update `paper/draft.md` and `README.md` to reflect these venues.

---

## 2. New Architectures — Ablation Study (CRITICAL for ICDE/BigData Acceptance)

IEEE reviewers require a factorial ablation when a paper claims the combination
of two mechanisms is better than either alone. Currently, BPFeat has 4 variants
(Fixed, DriftAdaptive, RateThrottle, Adaptive). Two new variants are REQUIRED:

**Variant 5 — "A-only" (AdaptiveW + fixed α)**
- Uses `AdaptiveFeatureWindowOp` (Mechanism A, AIMD W control) exactly as-is.
- `KeyedFeatureExtractOp` receives `signal=nullptr` → alpha fixed at α_min = 0.02.
- This tests: does the discrete window actuator alone, without the IIR-pole
  actuator, achieve the same Pareto-optimal result? If yes, Mechanism B adds no
  value and the paper's dual-actuator claim collapses.

**Variant 6 — "B-only" (fixed W=128 + adaptive α)**
- Uses `FixedWindowOp` (W=128, unmodified).
- Introduces a new `AdaptiveAlphaOnlyOp` operator that reads queue occupancy from
  the fixed window's output queue and publishes only the BackpressureSignal (no W
  adaptation) — or alternatively, `KeyedFeatureExtractOp` can read from a
  standalone `EMAOccupancyTracker` watching `q_batch` directly.
- `KeyedFeatureExtractOp` receives `signal=&signal` as normal (Mechanism B active).
- This tests: does the continuous IIR-pole actuator alone, without the window
  actuator, preserve model accuracy under load?

### Implementation — Add to `feature_flow/main.cpp` and `feature_flow/harness.cpp`

Add `"aonly"` and `"bonly"` to the arch enum and switch statement. The B-only
variant's signal ownership pattern: create a thin `BackpressurePublisherOp` class
that wraps `EMAOccupancyTracker<OutQueue>` and publishes to a `BackpressureSignal`
once per tick, registered as a lightweight worker alongside `FixedWindowOp` on
the same worker thread:

```cpp
// include/klstream/feature/backpressure_publisher_op.hpp
#pragma once
#include "../core/operator.hpp"
#include "../core/backpressure.hpp"
#include "types.hpp"

namespace klstream {
// Thin adapter: reads occupancy of a FeatureBatch queue, publishes to
// BackpressureSignal so KeyedFeatureExtractOp's AlphaController can read it.
// Used by the B-only ablation architecture (fixed W, adaptive alpha).
template <typename Queue>
class BackpressurePublisherOp : public IOperator {
public:
    BackpressurePublisherOp(std::string name, Queue* watched_queue,
                             BackpressureSignal* signal)
        : IOperator(std::move(name)), tracker_(*watched_queue), signal_(signal) {}

    OpStatus tick() override {
        tracker_.update();
        signal_->ema_occupancy.store(tracker_.ema(), std::memory_order_relaxed);
        return OpStatus::Idle;  // never pops a queue; always yields
    }
private:
    EMAOccupancyTracker<Queue> tracker_;
    BackpressureSignal* signal_;
};
} // namespace klstream
```

Wire B-only in `main.cpp`'s switch:
```cpp
case Architecture::BOnly: {
    BackpressureSignal signal;
    BackpressurePublisherOp<SPSCQueue<Event<FeatureBatch>>> bp_pub(
        "bp_pub", &q_batch, &signal);
    KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, &signal);
    // FixedWindowOp w=128 as usual
    // ... register bp_pub on worker 1 alongside window op
    break;
}
```

---

## 3. RALF Surrogate Baseline — Fifth Architecture (REQUIRED for ICDE)

The RALF paper (Wooders et al., VLDB 2024) uses a "Regret-Proportional" policy:
each key accumulates regret = sum of model-error-since-last-update, and the
scheduler prioritizes keys with the highest cumulative regret. For BPFeat's
context, the faithful C++ surrogate is: instead of publishing ALL keys' features
in a fixed window, publish only the TOP-K keys by estimated cumulative regret
per window, where K is determined by a fixed compute budget (analogous to RALF's
budget parameter).

**Key distinction to preserve in the paper:** RALF uses an *endogenous* signal
(actual model error tracking). For a streaming comparison where we do not know
true labels at scoring time, we estimate regret as:
`estimated_regret[user] = alpha_max × |ema_engagement - last_published_ema| × staleness_sec`

This approximates "how much has this user's feature drifted since we last
published it" — a staleness-weighted drift detector, not a true model-error
tracker, but faithful to RALF's scheduling intent within the streaming constraint.

### New file: `include/klstream/feature/ralf_window_op.hpp`

```cpp
// include/klstream/feature/ralf_window_op.hpp
// RALF Surrogate Baseline (Variant 7 / "ralf" architecture)
// Implements RALF's Regret-Proportional scheduling policy in the
// streaming feature pipeline context. Selects the top-K users by
// estimated cumulative regret per window (K = budget_fraction * W_max).
// Reference: Wooders et al., VLDB 2024, "RALF: Accuracy-Aware Scheduling
// for Feature Store Maintenance"
#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "types.hpp"
#include <algorithm>
#include <cmath>
#include <unordered_map>
#include <vector>

namespace klstream {

class RALFWindowOp : public IOperator {
public:
    using InQueue  = SPSCQueue<Event<FeatureSnapshot>>;
    using OutQueue = SPSCQueue<Event<FeatureBatch>>;

    // budget_fraction: fraction of MAX_FEATURE_BATCH slots to publish per window.
    // Default 0.5 matches RALF's intent of 50% compute saving under load.
    RALFWindowOp(std::string name, InQueue* input, OutQueue* output,
                 std::uint32_t window_collect_size = 256,
                 double budget_fraction = 0.50)
        : IOperator(std::move(name)), input_(input), output_(output)
        , window_collect_size_(window_collect_size)
        , budget_k_(static_cast<std::uint32_t>(window_collect_size * budget_fraction))
    {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }

    OpStatus tick() override {
        if (has_pending_idx_ < pending_batch_.count) {
            return flush_from(has_pending_idx_);
        }

        Event<FeatureSnapshot> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        // Accumulate regret for this user since last time we saw their snapshot
        std::uint32_t uid = in_ev.data.user_id;
        auto& state = regret_map_[uid];
        double drift = std::fabs(static_cast<double>(in_ev.data.x[0]) - state.last_ema);
        double staleness = (state.last_publish_ns > 0)
            ? static_cast<double>(in_ev.timestamp_ns - state.last_publish_ns) / 1e9
            : 0.0;
        state.cumulative_regret += drift * (staleness + 1.0);
        state.snapshot = in_ev.data;
        state.seq = in_ev.seq;
        state.last_ema = in_ev.data.x[0];
        collected_keys_.push_back(uid);
        collected_count_++;

        if (collected_count_ < window_collect_size_) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }

        // Window full — select top-K by cumulative regret
        std::vector<std::pair<double, std::uint32_t>> ranked;
        for (std::uint32_t k : collected_keys_) {
            ranked.push_back({regret_map_[k].cumulative_regret, k});
        }
        std::partial_sort(ranked.begin(),
                          ranked.begin() + std::min((std::size_t)budget_k_, ranked.size()),
                          ranked.end(),
                          [](const auto& a, const auto& b){ return a.first > b.first; });

        pending_batch_ = FeatureBatch{};
        std::uint32_t to_publish = std::min(budget_k_, (std::uint32_t)ranked.size());
        for (std::uint32_t i = 0; i < to_publish; ++i) {
            std::uint32_t k = ranked[i].second;
            auto& st = regret_map_[k];
            pending_batch_.push_back(st.snapshot, st.seq);
            st.last_publish_ns = in_ev.timestamp_ns;
            st.cumulative_regret = 0.0;  // reset after publishing
        }

        collected_keys_.clear();
        collected_count_ = 0;
        last_event_ts_ = in_ev.timestamp_ns;
        return flush_from(0);
    }

private:
    OpStatus flush_from(std::uint32_t start) {
        for (std::uint32_t i = start; i < pending_batch_.count; ++i) {
            const FeatureSnapshot& fs = pending_batch_.items[i];
            Event<FeatureBatch> out_ev;
            out_ev.timestamp_ns = last_event_ts_;
            out_ev.key = 0; out_ev.seq = pending_batch_.first_seq + i;
            // Emit one-item batch per published key (ScoringFlushOp handles this)
            FeatureBatch single{};
            single.push_back(fs, pending_batch_.first_seq + i);
            out_ev.data = single;
            if (!output_->try_push(out_ev)) {
                has_pending_idx_ = i;
                return OpStatus::Blocked;
            }
        }
        has_pending_idx_ = pending_batch_.count;
        if (metrics_) metrics_->events_processed.increment();
        return OpStatus::Processed;
    }

    struct UserRegretState {
        double cumulative_regret = 0.0;
        double last_ema = 0.0;
        std::uint64_t last_publish_ns = 0;
        FeatureSnapshot snapshot{};
        std::uint64_t seq = 0;
    };

    InQueue* input_;
    OutQueue* output_;
    std::uint32_t window_collect_size_;
    std::uint32_t budget_k_;
    std::unordered_map<std::uint32_t, UserRegretState> regret_map_;
    std::vector<std::uint32_t> collected_keys_;
    std::uint32_t collected_count_{0};
    FeatureBatch pending_batch_{};
    std::uint32_t has_pending_idx_{0};
    std::uint64_t last_event_ts_{0};
    OperatorMetrics* metrics_{nullptr};
};

} // namespace klstream
```

Add `"ralf"` to the architecture enum and switch in `main.cpp` and `harness.cpp`.
Wire it identically to `FixedWindowOp` (signal=nullptr, fixed alpha=0.10,
same queues, same worker topology).

---

## 4. Label Formulation Fix — Switch to Time-Window (IMPORTANT)

The current build prompt uses `H=5 events` as the label horizon. Research
confirms the standard formulation in the streaming systems literature for
Taobao purchase propensity is a **time-window**: "did this user make a purchase
within the next T hours?" The event-count formulation is non-standard and will
draw reviewer questions.

### Change in `preprocessing/preprocess_taobao.py`

Replace `compute_forward_label` with:

```python
def compute_forward_label(df: pd.DataFrame, horizon_hours: float = 2.0) -> tuple:
    """
    Time-window formulation (standard in streaming systems literature):
    label[i] = 1 if user makes a 'buy' within `horizon_hours` of event i's timestamp.
    
    This is more standard than the event-count H=5 formulation (Section 10.1 of
    the original build prompt). Time-window labels are used in:
    - Standard Taobao purchase prediction literature (CMC 2026 layered feature paper)
    - Streaming feature serving papers (RALF uses time-based staleness)
    """
    labels = np.zeros(len(df), dtype=np.uint8)
    valid = np.ones(len(df), dtype=bool)
    horizon_ns = int(horizon_hours * 3600 * 1_000_000_000)
    
    for uid, g in df.groupby("user_id"):
        idx = g.index.tolist()
        ts = g["timestamp_ns"].to_numpy()
        is_buy = (g["behavior_type"] == "buy").to_numpy()
        
        for i_pos, i in enumerate(idx):
            t_i = ts[i_pos]
            t_cutoff = t_i + horizon_ns
            # Check if any future buy event falls within horizon
            future_in_window = (ts[i_pos+1:] <= t_cutoff) & (is_buy[i_pos+1:])
            if i_pos + 1 >= len(idx):
                valid[i] = False
                continue
            # Mark trailing events where future window would extend beyond dataset
            max_future_ts = ts[-1]
            if max_future_ts < t_cutoff:
                valid[i] = False
                continue
            labels[i] = int(future_in_window.any())
    
    return pd.Series(labels, index=df.index), pd.Series(valid, index=df.index)
```

Also update `--horizon` CLI argument to `--horizon-hours` (default 2.0) and
update `train_classifier.py` to use the same time-window formulation when
computing oracle features offline.

---

## 5. Feature Enrichment — Improve Oracle AUC Above 0.60 Baseline

Research on the Taobao dataset confirms that basic 4-feature logistic regression
yields oracle AUROC ~0.60-0.64 (CMC 2026 layered feature paper: basic tier LR
F1=0.613). If oracle AUC is this low, regret differences between architectures
may be statistically indistinguishable — a fatal problem for the evaluation.

Add THREE additional features to `FeatureSnapshot` (expand `kDim` from 4 to 7)
and update all downstream code accordingly:

```cpp
// Updated FeatureSnapshot in include/klstream/feature/types.hpp
struct FeatureSnapshot {
    std::uint32_t user_id;
    float x[7];      // kDim = 7 — SEE ORDER BELOW, order matters for model
    float alpha_used;
    std::uint8_t label;
    std::uint8_t label_valid;
    static constexpr std::size_t kDim = 7;
};
```

Feature order (document this clearly in types.hpp):
```
x[0] = ema_engagement          // α-controlled (Mechanism B output)
x[1] = log1p(raw_pv_count)    // exact lifetime page-view counter
x[2] = log1p(raw_cart+fav)    // exact lifetime intent counter
x[3] = recency_norm            // normalized time-since-previous-event
x[4] = buy_rate_ratio          // NEW: raw_buy_count / max(1, raw_pv_count+raw_cart+raw_fav+raw_buy)
x[5] = log1p(raw_buy_count)   // NEW: exact lifetime purchase counter (only x[0] is approximated)
x[6] = ema_recency             // NEW: EMA of inter-event gaps (reactivity to session intensity)
```

Add `raw_buy_count` and `ema_recency` to `EMAUserState` in `user_state.hpp`.
Update `KeyedFeatureExtractOp::tick()` to compute all 7 features.
Update `LogisticModel` to use `kDim = FeatureSnapshot::kDim` (already templated
on this, should require no change if done correctly).
Update `train_classifier.py` to compute all 7 oracle features.

**Target oracle AUROC: above 0.70.** If oracle AUROC after adding these features
is still below 0.70, add a rolling 24h activity count feature and note in the
paper's experimental setup that a 7-feature logistic regression was used,
deliberately kept simple (not state-of-the-art) so that any accuracy degradation
observed is attributable to the pipeline's approximation, not to model complexity.

---

## 6. Statistical Rigor — Replace t-tests with Moving Block Bootstrap (CRITICAL)

Standard paired t-tests are **statistically invalid** on autocorrelated streaming
data. Adjacent events in the replay are highly correlated (queue state at t
depends on state at t-1). Using t-tests systematically underestimates variance
and inflates significance — a Type I error that reviewers at data engineering
venues will catch immediately.

### Replace `analysis/compute_metrics.py` statistical tests

Install `arch` (Kevin Sheppard's econometrics library, which has a clean MBB
implementation) or `recombinator`. Use `arch` — it is available via pip and has
no obscure dependencies:

```bash
pip install arch --break-system-packages
```

Replace ALL confidence interval computations in `compute_metrics.py` with:

```python
from arch.bootstrap import IIDBootstrap, MovingBlockBootstrap
import numpy as np

def moving_block_bootstrap_ci(data: np.ndarray, statistic_fn,
                               n_boot: int = 1000,
                               confidence: float = 0.95) -> tuple:
    """
    Moving Block Bootstrap confidence interval for autocorrelated streaming data.
    
    Block length choice: Hall et al. (1995) recommend block_length = n^0.25.
    For n=100K events this gives ~18; for n=10K gives ~10. Use max(10, int(n**0.25)).
    
    This replaces ALL standard t-tests throughout this file. See:
    Künsch (1989) "The jackknife and the bootstrap for general stationary
    observations." Annals of Statistics.
    Gemini deep research report: "Reviewers at data engineering venues will
    heavily scrutinize claims of statistical significance if temporal
    dependence is ignored."
    """
    n = len(data)
    block_length = max(10, int(n ** 0.25))
    bs = MovingBlockBootstrap(block_length, data)
    results = bs.apply(statistic_fn, n_boot)
    alpha = 1.0 - confidence
    lower = float(np.percentile(results, 100 * alpha / 2))
    upper = float(np.percentile(results, 100 * (1 - alpha / 2)))
    return lower, upper

def compute_feature_regret_with_mbb(run_csv: str, oracle_csv: str,
                                     n_boot: int = 1000) -> dict:
    """
    Computes Feature Regret (Section 25.3 of build prompt) with MBB CIs.
    run_csv: ResultSink output from one architecture run.
    oracle_csv: Oracle scores computed by compute_oracle_scores() below.
    Returns dict with mean_regret, ci_lower, ci_upper, coverage_fraction.
    """
    run_df = pd.read_csv(run_csv)
    oracle_df = pd.read_csv(oracle_csv)
    merged = run_df.merge(oracle_df, on='seq', suffixes=('_run', '_oracle'))
    valid = merged[merged['label_valid_run'] == 1].copy()
    
    eps = 1e-9
    def bce(score, label):
        s = np.clip(score, eps, 1-eps)
        return -(label * np.log(s) + (1-label) * np.log(1-s))
    
    regret_per_event = (bce(valid['score_run'].values, valid['label_run'].values)
                        - bce(valid['score_oracle'].values, valid['label_run'].values))
    
    mean_regret = float(np.mean(regret_per_event))
    ci_l, ci_u = moving_block_bootstrap_ci(
        regret_per_event, lambda x: np.mean(x), n_boot)
    
    # Coverage: fraction of all valid labeled events that got scored
    # (architectures publishing less often have lower coverage)
    total_valid = oracle_df[oracle_df['label_valid'] == 1].shape[0]
    coverage = len(valid) / max(1, total_valid)
    
    return {
        'mean_regret': mean_regret,
        'ci_lower': ci_l,
        'ci_upper': ci_u,
        'coverage_fraction': coverage,
        'n_scored': len(valid),
        'n_total_valid': total_valid,
        'block_length_used': max(10, int(len(regret_per_event) ** 0.25))
    }
```

Also add a `compute_oracle_scores()` function that replays the oracle model
(fixed alpha_max, W=1 in Python) and writes `data/replay/oracle_scores.csv` with
columns `seq, score_oracle, label, label_valid` — this is the reference against
which all architectures' regret is measured.

---

## 7. Jain's Fairness Index — Per-User Staleness Analysis

Add to `analysis/compute_metrics.py`:

```python
def compute_fairness_metrics(run_csv: str, n_quartiles: int = 4) -> dict:
    """
    Computes per-key staleness fairness (Section 25.6 of build prompt).
    
    Jain's Fairness Index on staleness distribution:
    J = (sum_i s_i)^2 / (n * sum_i s_i^2)
    where s_i is mean staleness for user i.
    J=1.0 means perfect fairness; J=1/n means one user gets all freshness.
    
    Also computes fairness_gap: mean staleness of bottom activity quartile
    MINUS mean staleness of top activity quartile. Positive = unfair to
    low-traffic users (expected under global backpressure, especially with
    Taobao's Zipfian distribution — Gemini research finding, Section 6.2).
    """
    df = pd.read_csv(run_csv)
    
    # Per-user mean staleness
    user_staleness = df.groupby('user_id')['staleness_sec'].mean()
    user_event_count = df.groupby('user_id').size()
    
    # Jain's Fairness Index
    s = user_staleness.values
    n = len(s)
    jain_index = (s.sum() ** 2) / (n * (s ** 2).sum()) if n > 0 else 0.0
    
    # Quartile fairness gap
    q_labels = pd.qcut(user_event_count, q=n_quartiles, labels=False, duplicates='drop')
    quartile_staleness = {}
    for q in range(n_quartiles):
        users_in_q = user_event_count[q_labels == q].index
        if len(users_in_q) > 0:
            quartile_staleness[q] = float(user_staleness[users_in_q].mean())
    
    bottom_q_staleness = quartile_staleness.get(0, 0.0)
    top_q_staleness = quartile_staleness.get(n_quartiles - 1, 0.0)
    fairness_gap = bottom_q_staleness - top_q_staleness
    
    return {
        'jain_fairness_index': float(jain_index),
        'fairness_gap_sec': float(fairness_gap),
        'quartile_staleness': quartile_staleness,
        'n_users': int(n),
        'user_activity_p10': float(np.percentile(user_event_count.values, 10)),
        'user_activity_p90': float(np.percentile(user_event_count.values, 90)),
    }
```

---

## 8. AIMD Sensitivity Sweep — Experiment 4 in `harness.cpp`

Add a parameter sweep to `feature_flow/harness.cpp`. The goal is to empirically
prove that the default parameters (shrink=0.70, grow=1.15, occ_low=0.30,
occ_high=0.70) produce a stable, near-optimal result — not a cherry-picked point.

```cpp
// In harness.cpp, add a sensitivity sweep mode triggered by --sweep flag:
struct SweepConfig {
    float shrink;
    float grow;
    float occ_low;
    float occ_high;
};

// Grid: 3×3×2×2 = 36 configurations. Run each once on synthetic calm-burst-calm.
// Report PATR and mean regret for each. Default config must not be the unique
// best-performing point — it should sit in a stable plateau.
std::vector<SweepConfig> make_sweep_grid() {
    std::vector<SweepConfig> grid;
    for (float shrink : {0.50f, 0.70f, 0.85f})
        for (float grow : {1.10f, 1.15f, 1.25f})
            for (float occ_low : {0.20f, 0.30f})
                for (float occ_high : {0.60f, 0.70f})
                    grid.push_back({shrink, grow, occ_low, occ_high});
    return grid;
}
```

Output the sweep as `results/raw/sweep_results.csv` with columns:
`shrink,grow,occ_low,occ_high,patr,mean_regret,wor,direction_changes`

---

## 9. Wall-Clock Throughput Reporting — Add Events/Second to ResultSink

IEEE reviewers expect throughput numbers in events/second (absolute), not just
PATR ratios (relative). Add to `result_sink.hpp` a throughput tracker:

```cpp
// Add to ResultSink class:
std::uint64_t events_since_start_{0};
std::uint64_t run_start_wall_ns_{0};
std::uint64_t last_throughput_report_ns_{0};
static constexpr std::uint64_t THROUGHPUT_REPORT_INTERVAL_NS = 1'000'000'000ULL; // 1s

// In tick(), after successful pop:
if (run_start_wall_ns_ == 0) {
    run_start_wall_ns_ = wall_now_ns();
    last_throughput_report_ns_ = run_start_wall_ns_;
}
++events_since_start_;
std::uint64_t now = wall_now_ns();
if (now - last_throughput_report_ns_ >= THROUGHPUT_REPORT_INTERVAL_NS) {
    throughput_out_ << (now / 1'000'000'000ULL) << ','
                    << static_cast<double>(events_since_start_) /
                       ((now - run_start_wall_ns_) / 1e9) << '\n';
    last_throughput_report_ns_ = now;
}
```

Write throughput trace to `results/raw/<arch>_throughput_trace.csv` with columns
`wall_sec_since_start, events_per_sec`. This produces the time-series throughput
plot for the paper showing throughput drop during burst and recovery.

Also add a `wall_now_ns()` free function to `result_sink.hpp`:
```cpp
static inline std::uint64_t wall_now_ns() {
    using namespace std::chrono;
    return static_cast<std::uint64_t>(
        duration_cast<nanoseconds>(steady_clock::now().time_since_epoch()).count());
}
```

---

## 10. Z-Domain LTV Caveat — Add to Analysis Script and Paper Draft

In `analysis/zdomain_feature_analysis.py`, add this docstring at the top of
`build_time_varying_heatmap()`:

```python
"""
IMPORTANT MATHEMATICAL CAVEAT (cite in paper, Section 7):
BPFeat's Mechanism B implements a Linear Time-Variant (LTV) filter because
alpha[n] changes per-event. Frozen-time Z-domain analysis (treating alpha
as constant over short windows to compute H(z) = alpha / (1-(1-alpha)z^-1))
is a known APPROXIMATION for LTV systems — the frozen-time transfer function
cannot capture the recursive nature of the LTV difference equation (Park &
Nguyen, UT Austin). This analysis is used strictly as a POST-HOC DIAGNOSTIC
to visualize how the filter's frequency response varies with measured system
load (i.e., does high occupancy correlate with a narrowed passband?). It is
NOT used to design the system or prove stability guarantees. Reviewers with
DSP backgrounds should be directed to this explicit caveat.
Reference: S. Park, "Recursive Synthesis of Linear Time-Variant Digital
Filters via Chebyshev Approximation," UT Austin CVRC.
"""
```

Add the same caveat as a comment block in `paper/draft.md` Section 4 (Theory).

---

## 11. Related Work Additions — New Citations for paper/draft.md

Add the following to the Related Work section of `paper/draft.md`. These were
found during independent research and must be cited to prevent a reviewer
finding them and questioning why they were omitted:

**GOVERNOR (Chen et al., ICAC 2017):** "GOVERNOR: Smoother Stream Processing
Through Smarter Backpressure" — implemented in Spark Streaming, achieves 26%
throughput improvement by factoring checkpointing costs into the backpressure
mechanism. Distinction from BPFeat: GOVERNOR controls the *admission rate* to
smooth checkpointing interruptions; BPFeat controls *window size and IIR
smoothing coefficient* to trade feature information content against downstream
inference cost. Both are "smarter backpressure" systems but actuate on
fundamentally different pipeline parameters.

**Das et al. (SoCC 2014):** "Adaptive Stream Processing Using Dynamic Batch Sizing"
— adapts Spark Streaming's micro-batch size based on processing latency. The
crucial distinction with BPFeat's Mechanism A: Das et al. change how many
*already-arrived requests* are grouped into one processing round (a pure throughput
optimization, no information loss per request). BPFeat changes how many raw
*behavior events* are folded into a per-user temporal aggregate before that
aggregate is published (changing what information the feature encodes, not just
processing granularity). This distinction must be stated in one explicit sentence.

---

## 12. occupancy_at_decision Bug Fix

In `ScoringFlushOp` and the wiring in `main.cpp`, the field `occupancy_at_decision`
is set to 0.0f for ALL non-Adaptive architectures (per an earlier code comment).
This means 5 out of 7 architectures have a structurally incorrect field in their
CSVs, corrupting any cross-architecture join on this column.

Fix: in `FeatureBatch` (types.hpp), add a `float occupancy_at_window_start = 0.0f`
field. Populate it:
- In `AdaptiveFeatureWindowOp::tick()` at the `buffer_.count == 0` point (already
  done).
- In `FixedWindowOp`'s aggregation lambda, `DriftAdaptiveWindowOp::tick()`,
  `RALFWindowOp::tick()`: set to 0.0f explicitly.
- In `BackpressurePublisherOp` (B-only): set to the last published EMA reading.
- In the A-only variant: set to the tracker's EMA reading (same as Adaptive).

This makes the field semantically consistent: 0.0f means "this architecture does
not use occupancy-based window sizing"; any other value means the actual reading
that drove this window's W decision.

---

## 13. Unit Tests — Add for New Architectures

Add to `tests/`:

**`test_ralf_window_op.cpp`:** Confirm that:
1. After collecting `window_collect_size=4` snapshots from 4 different users,
   the RALF op emits only `budget_k = floor(4*0.5) = 2` FeatureBatch events.
2. The 2 emitted events correspond to the 2 users with the highest
   `estimated_regret` (drift * staleness) from the artificial test input.
3. The remaining 2 users' regret accumulates (is NOT reset) for the next window.

**`test_backpressure_publisher_op.cpp`:** Confirm that after pushing events
into `q_batch`, `BackpressurePublisherOp::tick()` always returns `OpStatus::Idle`
(never pops a queue) and that `signal.ema_occupancy` reads a non-zero value after
the queue is partially filled.

**`test_ablation_architectures.cpp`:** Integration test confirming A-only and
B-only architectures both produce the correct row count on a 200-event synthetic
stream (same check as `test_pipeline_integration.cpp`'s other architectures).

---

## 14. Harness — 7-Architecture Full Experiment Run

Update `feature_flow/harness.cpp` to run all 7 architectures:
`fixed`, `drift`, `throttle`, `aonly`, `bonly`, `adaptive`, `ralf`

For each architecture, run with `--seeds 5` (5 independent seeds, varying only
the burst injection random seed in the synthetic generator, not the replay data).
Produce separate result CSVs for each `(architecture, seed)` combination.

After all runs, call `analysis/compute_metrics.py --all-archs` which:
1. Reads all 35 result CSVs (7 archs × 5 seeds).
2. Computes mean ± MBB 95% CI for Feature Regret, PATR, WOR, staleness, p99 latency.
3. Computes Jain's Fairness Index per architecture.
4. Writes `results/summary_table.csv` (suitable for LaTeX tabular paste).
5. Writes `results/sweep_stability.csv` from the sweep in Section 8.

---

## 15. Required Output Printing (MANDATORY — Do Not Skip)

At the end of every experiment run (whether synthetic or real), print the
following diagnostic block to stdout. This is what the paper author will copy
and paste for evaluation. Format must be exactly as shown:

```
=== BPFeat Experiment Output Block ===
Run timestamp: <ISO8601>
Architecture:  <arch_name>
Dataset:       <taobao|ulb|synthetic>
Seed:          <seed_number>
N events processed: <count>
N events scored (label_valid=1): <count>
Coverage fraction: <0.000>

--- Controller Trace (Adaptive/AOnly/BOnly only) ---
final_W:              <int>
final_alpha:          <float>
direction_changes:    <int>
WOR (dir_changes/min):<float>
W_min_observed:       <int>
W_max_observed:       <int>
alpha_min_observed:   <float>
alpha_max_observed:   <float>

--- Throughput ---
steady_state_events_per_sec: <float>
burst_period_events_per_sec: <float>
PATR:                        <float>
p50_latency_ms:              <float>
p99_latency_ms:              <float>

--- Feature Regret (requires oracle_scores.csv) ---
mean_feature_regret:  <float>
regret_ci_lower:      <float>  [MBB 95% CI]
regret_ci_upper:      <float>  [MBB 95% CI]
MBB_block_length:     <int>
mean_staleness_sec:   <float>

--- Fairness (Taobao only) ---
jain_fairness_index:  <float>
fairness_gap_sec:     <float>
user_activity_p10:    <int>  events
user_activity_p90:    <int>  events

--- Queue Drain ---
[drain] Final occupancy: raw=<f>, feat=<f>, batch=<f>, scored=<f>
All queues empty: <YES/NO>

--- Sanity Checks ---
shuffled_null_regret: <float>  (must be >> mean_feature_regret)
oracle_auroc:         <float>  (must be > 0.70 for results to be meaningful)
=== End Output Block ===
```

Implement `shuffled_null_regret` in `compute_metrics.py`: compute Feature Regret
after randomly permuting the `score` column against labels — this must always be
larger than any architecture's real regret, proving the pipeline is not trivially
broken.

Implement `oracle_auroc` by computing AUROC between `score_oracle` and `label` in
the oracle_scores.csv — if this is below 0.70 after the feature enrichment in
Section 5, add a warning in the output and do NOT submit results for that feature
set.

---

## 16. paper/draft.md — Full IEEE-Style Paper Outline

Rewrite `paper/draft.md` with this full outline (fill in placeholders after
experiments run):

```markdown
# BPFeat: Backpressure-Driven Elastic Feature Windows for Real-Time ML Pipelines

**Target venue:** IEEE BigData 2026, Phoenix AZ, Dec 14-17. Deadline Aug 21, 2026.
**Alternative:** IEEE ICDE 2027, IEEE ICDCS 2027.

## Abstract (150 words — write after results are in)

## 1. Introduction
- Feature freshness vs. compute cost: the static-configuration problem
- The one-paragraph pitch (Section 3 of build prompt)
- Contributions: (1) dual-actuator mechanism, (2) W↔α equivalence test,
  (3) Feature Regret evaluation with MBB CIs across 7 architectures,
  (4) fairness analysis on Zipfian user distribution

## 2. Related Work
- Feature stores (RALF [cite], Feast, Tecton) — endogenous accuracy signals
- Approximate feature computation (Biathlon [cite]) — per-request, endogenous
- Adaptive window sizing (ADWISE [cite], Das et al. SoCC 2014) — different signal
- Smarter backpressure (GOVERNOR [cite], Spark PIDRateEstimator, Flink credit flow)
- Concept-drift windowing (ADWIN [cite])
- Non-academic prior art: US Patent 9,521,158
- Dynamic batching (Clipper, Triton) — grouping vs. information content
- Gap table (Section 4.9 of build prompt, condensed to prose)

## 3. System Design
- Pipeline diagram (Figure 1)
- Causal chain (7 steps, Section 8.2 of build prompt)
- Four baseline + two ablation + one RALF-surrogate architectures

## 4. Theoretical Foundation
- Mechanism A: AIMD controller (Section 7 of build prompt)
- Mechanism B: IIR-pole control law (Section 7.2 — sign flip, justified)
- EWMA span identity N = 2/α − 1 as the formal bridge
- LTV CAVEAT: frozen-time analysis is a post-hoc diagnostic, not a stability proof
- Worked numeric sanity check (Section 7.5 of build prompt)

## 5. Experimental Setup
- Datasets: Taobao UserBehavior (N_USERS users, time-window label T=2h) + ULB (secondary)
- Oracle AUROC: [FILL IN FROM SECTION 15 OUTPUT]
- 7 architectures (Fixed, DriftAdaptive, RateThrottle, A-only, B-only, Adaptive, RALF)
- Metrics: Feature Regret (MBB CIs), PATR, WOR, staleness, Jain's index
- 5 seeds × 7 architectures = 35 runs

## 6. Results
- Experiment 1: Mechanism validation (Section 27 Exp 1)
- Experiment 2: Throughput retention (PATR, p99 latency) [TABLE]
- Experiment 3: Feature Regret + coverage [TABLE WITH MBB CIs]
- Experiment 4: Sensitivity sweep [FIGURE showing stable plateau]
- Experiment 5: Fairness analysis [FIGURE: staleness by user activity quartile]
- Experiment 6: W↔α Pearson correlation [NUMBER]
- Experiment 7: Z-domain heatmap [FIGURE]
- Experiment 8: ULB generalization [TABLE]

## 7. Discussion
- Why α moves opposite to Project 1 (Decision 3)
- RALF surrogate comparison: system-state vs. accuracy-state signals
- Fairness limitation: global signal disadvantages sparse keys — discussion of
  per-key controller as future work
- Mapping to production Flink (KeyedProcessFunction + ProcessingTimeTimer)

## 8. Conclusion

## References
[FILL IN from Section 33 of build prompt + GOVERNOR, Das et al., new citations]
```

---

## Summary of All Files to Create or Modify

**NEW FILES:**
- `include/klstream/feature/backpressure_publisher_op.hpp` (Section 2)
- `include/klstream/feature/ralf_window_op.hpp` (Section 3)
- `tests/test_ralf_window_op.cpp` (Section 13)
- `tests/test_backpressure_publisher_op.cpp` (Section 13)
- `tests/test_ablation_architectures.cpp` (Section 13)

**MODIFIED FILES:**
- `include/klstream/feature/types.hpp` — expand FeatureSnapshot to kDim=7, add
  `occupancy_at_window_start` to FeatureBatch (Sections 5, 12)
- `include/klstream/feature/user_state.hpp` — add raw_buy_count, ema_recency (Section 5)
- `include/klstream/feature/keyed_feature_extract_op.hpp` — compute 7 features (Section 5)
- `include/klstream/feature/result_sink.hpp` — add throughput tracking (Section 9)
- `include/klstream/feature/adaptive_feature_window_op.hpp` — populate
  occupancy_at_window_start in FeatureBatch (Section 12)
- `include/klstream/feature/drift_adaptive_window_op.hpp` — set
  occupancy_at_window_start = 0.0f (Section 12)
- `feature_flow/main.cpp` — add aonly, bonly, ralf arch cases (Sections 2, 3)
- `feature_flow/harness.cpp` — add sweep mode, all 7 archs, output block (Sections 8, 14)
- `preprocessing/preprocess_taobao.py` — time-window label (Section 4)
- `preprocessing/train_classifier.py` — 7-feature oracle, time-window label (Sections 4, 5)
- `analysis/compute_metrics.py` — MBB CIs, Jain index, oracle_auroc check,
  shuffled null, output block (Sections 6, 7, 15)
- `analysis/zdomain_feature_analysis.py` — LTV caveat docstring (Section 10)
- `paper/draft.md` — full IEEE outline (Section 16)
- `README.md` — update venue from IT4D to BigData 2026 / ICDE 2027, document all
  7 architectures, document `--sweep` flag

**DO NOT TOUCH:**
- `include/klstream/core/*` (real KLStream headers, already correct)
- `include/klstream/operators/*` (real KLStream operators, already correct)
- `include/klstream/model/logistic_model.hpp` (assuming it correctly uses kDim
  from FeatureSnapshot — verify it reads `FeatureSnapshot::kDim` at compile time
  and does not hardcode 4)
- All 6 existing passing unit tests (unless a test explicitly breaks due to kDim
  change, in which case update the test's feature-vector construction, not the
  production code)

---

## Build and Verify Sequence

After all changes, run in this order:

```bash
# 1. Build everything
cmake --build build -j4

# 2. Run all 9 unit tests (6 existing + 3 new) — must all pass
ctest --test-dir build --output-on-failure

# 3. Smoke test: synthetic calm-burst-calm, all 7 architectures
for arch in fixed drift throttle aonly bonly adaptive ralf; do
    ./build/feature_flow/feature_flow_main \
        --arch $arch --synthetic --speed 1000 \
        --out results/raw/smoke_${arch}.csv
done

# 4. Verify row counts match (Fixed=99968-ish, others may vary by W)
wc -l results/raw/smoke_*.csv

# 5. Verify occupancy_at_decision is non-zero only for adaptive/aonly
python3 -c "
import pandas as pd, glob
for f in sorted(glob.glob('results/raw/smoke_*.csv')):
    df = pd.read_csv(f)
    print(f.split('/')[-1], 'occ_mean=', df['occupancy_at_decision'].mean())
"

# 6. Run full 7-arch harness (5 seeds each) — save output to a log file
./build/feature_flow/feature_flow_harness --seeds 5 --synthetic \
    2>&1 | tee results/raw/full_harness_run.log

# 7. Compute metrics
python3 analysis/compute_metrics.py --all-archs \
    --result-dir results/raw/ \
    --oracle-csv data/replay/oracle_scores.csv

# 8. Print the Section 15 output block for all 7 architectures
# (this is what to copy and paste back for evaluation)
```

**After completing this sequence, paste the entire contents of
`results/raw/full_harness_run.log` and the output of step 7 here.
Also paste the oracle AUROC printed by train_classifier.py.
These numbers are required before the paper can be written.**