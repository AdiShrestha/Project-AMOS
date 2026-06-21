# BPFeat: Backpressure-Driven Elastic Feature Windows for Real-Time ML Pipelines

**Paper Draft — IEEE Conference Submission**

---

## Abstract

Real-time ML feature pipelines face a freshness-vs-cost trade-off that current practice treats as a static configuration problem. We treat this as a closed-loop control problem instead. We repurpose a backpressure signal — the EMA-smoothed occupancy of a stream-processing operator's own output queue — to drive two coupled actuators simultaneously: how often a per-key feature snapshot is republished (a discrete, AIMD-controlled window size W), and how reactive that feature's underlying exponential moving average is to recent events (a continuous, slew-rate-bounded IIR pole α). Both mechanisms run inside a real, multi-threaded, lock-free C++17 stream runtime. We compare against three baselines (static window, input-statistics-driven drift-adaptive window, and admission-rate throttling structurally identical to Spark's PIDRateEstimator) and evaluate via downstream model regret — the degradation in a real classifier's predictive quality caused by features being staler or more aggressively smoothed than an oracle's. To our knowledge, no prior systems paper treats feature-pipeline freshness-vs-cost as a closed-loop, queue-state-driven control problem with both a discrete and continuous actuator, formally connects the two via the EWMA span-to-α identity, and validates the connection empirically.

---

## 1. Introduction

[Expand from Section 3 of bpfeat_build_prompt.md — the one-paragraph pitch. Frame the freshness-vs-cost trade-off in current practice (static TTL, static window, static refresh cadence). Motivate the closed-loop framing. State the four research questions.]

### 1.1 Contributions

1. **BPFeat**: a backpressure-driven feature pipeline with two simultaneous actuators (W and α) sharing one EMAOccupancyTracker, implemented and released as an open-source C++17 research system.
2. **Formal W↔α connection**: we derive and empirically test the EWMA span-to-α identity as a bridge between the two control mechanisms (Section 4).
3. **Feature Regret as a rigorous evaluation metric**: we adopt RALF's regret formalization and defend against the analogous evaluation trap to the point-adjustment issue in time-series anomaly detection (Section 8).
4. **Empirical comparison against three baselines** including a literal deployment of Spark's admission-control mechanism as Baseline 3.

---

## 2. Related Work

### 2.1 Feature Stores and Freshness Scheduling

**RALF** (Russo et al., VLDB 2024): the closest prior systems work. Periodically re-prioritizes which keys' features get recomputed under a fixed compute budget using a feature store regret objective. Critically, RALF's scheduler operates in discrete refresh decisions polled against a budget — no continuous feedback loop reacting to a live queue-occupancy signal, no IIR-pole actuator. We adopt RALF's regret formalization directly as our headline accuracy metric.

**Biathlon** (VLDB 2024, arXiv:2405.11191): determines per inference request the degree of statistical approximation to apply to an aggregation feature, with accuracy-bound guarantees. Key distinction: Biathlon's lever is chosen *per request* from an *accuracy-bound target* (endogenous). Ours is chosen at the *operator level, continuously*, from an *exogenous system-state signal* (queue occupancy). Complementary, not competing.

**Feast, Tecton, Hopsworks, Chalk**: industrial feature stores. Freshness governed by configured TTLs and materialization schedules — not adapted online.

### 2.2 Structural Analogs

**ADWISE** (IEEE ICDCS 2018): adapts a streaming graph partitioner's batch window size based on measured assignment latency. Same "elastic window as a latency/quality actuator" idea, but: domain is graph partitioning (not ML feature serving), control signal is a measured latency (not queue-occupancy EMA), no continuous second actuator, no downstream-model-regret evaluation.

**US Patent 9,521,158** (Cisco): closed-loop control of feature-aggregation parameters (time window / sampling rate) feeding an ML classifier, adapted based on measured network congestion. Closest non-academic prior art. Scoped to network telemetry/security; does not formalize a Z-domain/IIR treatment; no discrete+continuous actuator pairing; no regret-based evaluation.

**Dynamic batching** (Clipper, Triton, continuous-batching LLM serving): groups already-arrived independent requests for one forward pass — a pure throughput optimization with no information loss. Our W controls how many raw events are folded into a per-key temporal aggregate before republication — changing what information the feature itself encodes, not just how many independent items are processed per kernel launch.

### 2.3 Active Queue Management

RED (Floyd & Jacobson, 1993), CoDel (Nichols & Jacobson, 2012), PIE: conceptual ancestors. Actuator is always a drop/mark decision on packets, never a downstream computation's window size or smoothing coefficient.

### 2.4 Backpressure in Production Stream Processors

Spark Streaming's `PIDRateEstimator` (legacy DStream API), Flink's credit-based flow control: throttle admission rate in response to downstream load. Neither adapts a window size or smoothing coefficient. Operationalized here as Baseline 3 (`RateThrottleSource`).

### 2.5 Concept-Drift-Adaptive Windowing

ADWIN (Bifet & Gavaldà, SDM 2007) and descendants: adapt window size based on a statistical test for distributional change *in the data*. None respond to *system load*. Operationalized here as Baseline 2 (`DriftAdaptiveWindowOp`) — a two-timescale EMA-crossover approximation of the key property (signal-driven, not load-driven), following Decision 6.

### 2.6 Gap Table

| Prior work | Adapts what | Driven by | Evaluated via | What BPFeat adds |
|---|---|---|---|---|
| RALF (VLDB '24) | refresh schedule per key | regret-weighted budget poll | downstream regret | continuous queue-driven loop; pairs with continuous actuator |
| Biathlon (VLDB '24) | per-feature approximation | per-request accuracy bound | accuracy-bound guarantee | exogenous system-state signal; operator-level not request-level |
| ADWISE (ICDCS '18) | batch window size | measured latency | partition quality | applies to ML feature serving; adds continuous actuator; regret evaluation |
| US Patent 9,521,158 | aggregation window / sample rate | network congestion | (not academically evaluated) | general ML feature-store framing; Z-domain treatment; regret evaluation |
| Dynamic batching | request batch size | queue depth / SLA | throughput, tail latency | lever changes feature information content, not just request grouping |
| ADWIN and descendants | window size | data drift statistic | concept-drift accuracy | exists as DriftAdaptiveWindowOp, the literature-style baseline directly contrasted |
| Spark PIDRateEstimator / Flink credit flow | admission rate | queue signal | throughput stability | exists as RateThrottleSource baseline against a different actuator |
| AQM (RED, CoDel) | packet drop/mark | queue occupancy | throughput, fairness | conceptual ancestor; actuator is computation parameter, not drop decision |

---

## 3. System Design

### 3.1 Pipeline Architecture

```
BehaviorSource → KeyedFeatureExtractOp → [WindowOp variant] → ScoringFlushOp → ResultSink
```

Four interchangeable window-stage implementations, swapped via a CLI flag. All produce the same `Event<FeatureBatch>` type so `ScoringFlushOp` and everything downstream is architecture-unaware.

| Variant | Represents |
|---|---|
| `FixedWindowOp` (W=128) | Static configuration (current default practice) |
| `DriftAdaptiveWindowOp` | Literature-style data-driven adaptation (ADWIN lineage) |
| `FixedWindowOp` + `RateThrottleSource` | Current industry practice (Spark/Flink-style admission control) |
| `AdaptiveFeatureWindowOp` | **The contribution** |

### 3.2 Causal Chain

[Expand Section 8.2 of bpfeat_build_prompt.md into a numbered sequence with a pipeline diagram. This is the load-bearing mechanistic claim of the paper.]

### 3.3 Why Mechanism B Lives in KeyedFeatureExtractOp

[Expand Section 8.3 — α must be applied once per raw event per key, upstream of any batching decision. AdaptiveFeatureWindowOp owns and publishes the signal; KeyedFeatureExtractOp reads it.]

---

## 4. Theoretical Foundation

### 4.1 Mechanism B's Control Law

α[n] = α_min + (α_max − α_min) · L[n]

with |α[n] − α[n−1]| ≤ Δα_max (slew-rate bound). Sign-flipped relative to Project 1 (Section 7.2 of the build prompt) — justified because rising load here increases α (shorter effective memory), the correct response when W is simultaneously growing (publishes becoming less frequent; each publish must count for more, not less).

### 4.2 EWMA Span-to-α Identity

α = 2/(N+1)  ⟺  N = 2/α − 1

Sanity check: at calm (L=0), α=0.02 → N=99 events of memory. At full stress (L=1), α=0.30 → N≈5.67 events. W moves from w_max=256 to w_min=8 over the same range — a 32× contraction vs. a 17.5× contraction. **Static endpoints do not match by design; Experiment 6 tests whether the trajectories track each other empirically.**

### 4.3 Frozen-Time Z-Domain Analysis (Retargeted from Project 1)

H(z) = α / (1 − (1−α)z^{-1}), pole at z = 1−α.

Applied to the real logged α[n] trace from an actual run — not a synthetic signal. This produces the flagship "passband narrowing under real backpressure" visualization: a real burst in the Taobao replay caused real queue occupancy to rise, which moved a real α[n] and W[n], logged from a real C++ run.

---

## 5. Implementation

[Point to the open-source repository. Include 2 key code listings: BPFeatController.update() + AlphaController.update() as the core contribution pair, and the causal-chain diagram (Section 8.2).]

Key implementation notes:
- `ScoringFlushOp` uses a non-standard multi-item Blocked-recovery pattern (`has_pending_idx_`) — the single highest-risk new control flow in the project (Section 17 of the build prompt).
- `BackpressureSignal` uses atomic relaxed stores/loads — one tick of lag is acceptable and documented.
- No external C++ dependencies beyond pthreads (Decision 5).

---

## 6. Experimental Setup

### 6.1 Datasets

**Taobao UserBehavior** (primary): Alibaba Tianchi, 10,000 users, ~2M events, Nov 25–Dec 3 2017. Natural burst periods identified from arrival-rate time series. Purchase propensity label derived from session-based 'buy' event co-occurrence.

**ULB Credit Card Fraud** (secondary, explicitly scoped): 284,807 transactions. All events assigned user_id=0 (degenerate single-key mode). No per-card keyed feature possible (V1–V28 are PCA-anonymized). Used ONLY for global rolling feature generalization check.

### 6.2 Baselines

[Describe all 4 architectures — see Section 8.1 table.]

### 6.3 Oracle Classifier

Logistic regression on oracle features (α=0.30, W=1 — maximally fresh, no smoothing lag). Oracle AUPRC: [FILL IN from train_classifier.py output before submission]. Same weights reused across all four architectures.

### 6.4 Metrics

- **PATR**: throughput during burst / throughput during calm
- **Feature Regret (FR)**: mean[BCE(online_score, label) − BCE(oracle_score, label)] over label_valid=1 events
- **Staleness**: mean seconds since last per-user publish (diagnostic, not headline)
- **Coverage**: fraction of labeled events that received a score
- **WOR**: controller direction changes per minute
- **Fairness gap**: staleness difference between bottom-quartile and top-quartile users by event count

Statistical rigor: 5 independent runs per (architecture, dataset, experiment). Report mean ± 95% CI (t-distribution). Warmup: discard first W_max=256 events per run.

---

## 7. Results

### Experiment 1 — Mechanism Validation (RQ1)
[Describe the injected burst, expected causal chain visualization. Include the shared time-axis plot: arrival rate / queue occupancy / W[n] / α[n].]

### Experiment 2 — Throughput Retention Under Burst (RQ3)
[PATR table across 4 architectures. Note: "retains throughput by dropping admission" (RateThrottle) vs. "retains throughput by cheaper processing" (Adaptive) is a materially different outcome — state explicitly.]

### Experiment 3 — Feature Regret and Fairness (RQ3)
[FR ± CI table across 4 architectures. Staleness. Fairness gap. Coverage. Report honestly — if a genuine trade-off exists, state it as such.]

### Experiment 4 — Sensitivity Sweep
[Parameter sweep results. Confirm qualitative result holds across ±30% of default parameter values.]

### Experiment 5 — ULB Generalization (RQ4)
[Repeat Experiment 3 on ULB. State honestly if the result weakens — a boundary-condition finding is still a legitimate contribution.]

### Experiment 6 — W↔α Empirical Equivalence (RQ2)
[Pearson correlation(N_α[n], W[n]) from the logged traces. The passband narrowing heatmap as the flagship Z-domain figure. Report honestly regardless of correlation magnitude.]

---

## 8. Discussion

### 8.1 Why α Moves in Opposite Directions Across the Two Projects
[Expand Section 2 Decision 3 of the build prompt into a named discussion point.]

### 8.2 The Regret-Attribution Trap
[Expand Section 26 of the build prompt — the analogous pitfall to Project 2's point-adjustment trap. Describe the five mitigations: full coverage reporting, shuffled-features null baseline, reporting regret+staleness+coverage together, multiple seeds with CIs, mandatory fairness check.]

### 8.3 Fairness
[Report the fairness gap finding and discuss.]

### 8.4 Threats to Validity and Limitations
- Single-node simulation vs. production distributed deployment
- ULB's anonymized features limit per-entity keying
- Oracle classifier's modest absolute AUPRC (state the number)
- Global W/α controller may disadvantage low-traffic users (fairness gap)

### 8.5 Mapping to Production Systems
The mechanism validated here maps directly onto Flink's `KeyedProcessFunction` + `ProcessingTimeTimer` API. We built a controlled, single-node analog to isolate causal attribution, consistent with how AQM mechanisms (RED, CoDel) were first validated on single-queue models before wide deployment.

---

## 9. Conclusion

[Brief. Summarize the contribution, the empirical findings, and the open question (RQ2) whose honest answer — whether the two control laws track each other in practice — is itself a contribution regardless of its sign.]

---

## References

[Full reference list — see Section 33 of bpfeat_build_prompt.md. Verify all citations against their published forms before submission.]

---

## Appendix — Numeric Defaults and Justification

| Parameter | Value | Source |
|---|---|---|
| α_min | 0.02 | Project 1 (opposite role) |
| α_max | 0.30 | Project 1 (opposite role) |
| Δα_max | 0.01/event | Project 1 slew-rate bound |
| w_min | 8 | Minimum meaningful batch for ScoringFlushOp |
| w_max | 256 | MAX_FEATURE_BATCH compile-time cap |
| occ_low | 0.30 | Project 2 default (BP_LOW_THRESHOLD) |
| occ_high | 0.70 | Project 2 default (BP_SOFT_THRESHOLD) |
| shrink_factor | 0.70 | Project 2 AIMD default |
| grow_factor | 1.15 | Project 2 AIMD default |
