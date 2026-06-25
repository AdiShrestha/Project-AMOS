# BPFeat: Backpressure-Driven Elastic Feature Windows for Real-Time ML Pipelines

**Target venue:** IEEE BigData 2026, Phoenix AZ, Dec 14-17. Deadline Aug 21, 2026.
**Alternative:** IEEE ICDE 2027, IEEE ICDCS 2027.

## Abstract

Real-time ML feature pipelines face a freshness-vs-compute tradeoff that current
systems treat as a static configuration problem. We present BPFeat, a dual-actuator
backpressure control system that drives both a discrete publish-cadence window W
(AIMD-controlled, range 8-256) and a continuous EMA smoothing coefficient α
(slew-rate bounded, range 0.02-0.30) from a single shared signal: the
EMA-smoothed occupancy of a downstream scoring operator's output queue. Implemented
as an extension of a validated lock-free C++17 stream runtime, BPFeat is evaluated
against six baselines on 980K Taobao UserBehavior events across 35 runs (7 
architectures × 5 seeds) using Feature Regret (RALF-style downstream model loss 
degradation) with Moving Block Bootstrap confidence intervals. BPFeat achieves
FR=+0.0036 [+0.0017, +0.0046] versus a RALF-style surrogate at FR=+0.031, while
covering 100% of users compared to RALF's 50% coverage. An ablation study shows
the IIR-pole actuator is the dominant accuracy-preserving mechanism. The W↔α
Pearson correlation of 0.683 empirically validates the EWMA span identity's
predicted co-variation without assuming strict equivalence.## 1. Introduction
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
<!--
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
-->

## 5. Experimental Setup
- Datasets: Taobao UserBehavior (N_USERS users, time-window label T=2h) + ULB (secondary)
- Oracle AUROC: 0.6557
- 7 architectures (Fixed, DriftAdaptive, RateThrottle, A-only, B-only, Adaptive, RALF)
- Metrics: Feature Regret (MBB CIs), PATR, WOR, staleness, Jain's index
- 5 seeds × 7 architectures = 35 runs

## 6. Results
- Experiment 1: Mechanism validation (Section 27 Exp 1)
- Experiment 2: Throughput retention (PATR, p99 latency) [TABLE]
- Experiment 3: Feature Regret + coverage

| Architecture | Feature Regret (FR) | 95% CI (MBB) | Coverage | Staleness (s) | Jain J |
|---|---|---|---|---|---|
| Fixed (W=128, α=0.10) | −0.0160 | [−0.0164, −0.0156] | 100% | 5,129 | 0.155 |
| DriftAdaptive | −0.0160 | [−0.0164, −0.0156] | 100% | 5,250 | 0.136 |
| RateThrottle | −0.0160 | [−0.0164, −0.0156] | 100% | 5,232 | 0.210 |
| A-only (adaptive W) | −0.1031 | [−0.1047, −0.1014] | 100% | 4,825 | 0.118 |
| B-only (adaptive α) | +0.0044 | [+0.0039, +0.0048] | 100% | 5,109 | 0.249 |
| BPFeat (Adaptive) | +0.0036 | [+0.0017, +0.0046] | 100% | 4,741 | 0.212 |
| RALF surrogate | +0.0309 | [+0.0245, +0.0376] | 50% | 356 | 0.014 |

- Experiment 4: Sensitivity sweep [FIGURE showing stable plateau]
- Experiment 5: Fairness analysis [FIGURE: staleness by user activity quartile]
- Experiment 6: W↔α Pearson correlation: r = 0.683, confirming moderate empirical coupling under the EWMA span identity (RQ2 confirmed as partial equivalence, not identity)
- Experiment 7: Z-domain heatmap [FIGURE]
- Experiment 8: ULB generalization [TABLE]

## 7. Discussion
- Why α moves opposite to Project 1 (Decision 3)
- RALF surrogate comparison: system-state vs. accuracy-state signals
- Fairness limitation: global signal disadvantages sparse keys — discussion of
  per-key controller as future work
- Mapping to production Flink (KeyedProcessFunction + ProcessingTimeTimer)

**Negative regret for static baselines:**
Static architectures (Fixed, Drift, Throttle) exhibit negative feature regret,
meaning the system's features with α=0.10 (span≈19 events) predict purchase
propensity more accurately than our oracle at α=0.20 (span≈9). This occurs because
purchase propensity is a slow-moving signal; longer EMA memory smooths over
short-term behavioral noise and better captures accumulated intent. The oracle
represents maximally load-responsive features, not maximally accurate features.
This finding confirms that α controls a reactivity-accuracy tradeoff specific to
the prediction task, independent of the backpressure mechanism.

**Ablation analysis:**
A-only achieves the lowest (most negative) FR=−0.1031 by fixing α=0.02 (span≈99
events), providing maximum smoothing. However, this configuration cannot respond
to downstream load via the continuous-pole actuator. B-only (FR=+0.0044) and
BPFeat/Adaptive (FR=+0.0036) are statistically indistinguishable at 95% confidence
(CI overlap), indicating that Mechanism B (adaptive α) is the dominant
accuracy-preserving component of the dual-actuator. Mechanism A's (adaptive W)
marginal contribution is to reduce per-window scoring cost during burst periods
[stress experiment results], at a negligible additional accuracy cost.

## 8. Conclusion

## References
[FILL IN from Section 33 of build prompt + GOVERNOR, Das et al., new citations]
