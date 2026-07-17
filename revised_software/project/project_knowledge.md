# Project Knowledge — BPFeat

**Project:** BPFeat — Backpressure-Driven Elastic Feature Windows for Real-Time ML Pipelines
**Factory Version:** 1.0.1
**Created:** 2026-07-17
**Owner:** Claude (Architect)

---

## Glossary

### Feature Regret
The gap between a downstream ML model's loss when scored using the system's actual (possibly stale or approximated) features versus an oracle's loss using maximally fresh, unbatched features. Adopted directly from RALF (Russo et al., VLDB 2024). This is the headline accuracy metric for BPFeat — not detection F1 (which would be a category error, since BPFeat serves continuous-valued features to a classifier, not discrete event detections).

### Staleness
The wall-clock time elapsed between the most recent event that updated a user's feature state and the moment that feature snapshot is published downstream for scoring. Measured in seconds. Logged by `ScoringFlushOp` alongside every `ScoredResult`. Used purely for evaluation — deliberately NOT included as a model input feature, since feeding "how stale am I" into the classifier itself would be an unusual and confounding design choice that RALF's own evaluation does not make.

### EWMA (Exponential Weighted Moving Average)
A recursive filter `y[n] = α·x[n] + (1−α)·y[n−1]` where α ∈ (0,1] is the smoothing coefficient. The standard identity relating α to an equivalent simple-moving-average "span" N is `α = 2/(N+1)`, or equivalently `N = 2/α − 1`. This identity is the formal bridge between Mechanism A (discrete window size W) and Mechanism B (continuous pole α) — see Section 7.3 of the build prompt.

### EWMA Span Identity
`α = 2/(N+1)` ⟺ `N = 2/α − 1`. At calm (α=0.02): N_α = 99 events of effective memory. At full stress (α=0.30): N_α ≈ 5.67 events. This identity is the content behind the "mapping IIR poles to elastic sliding windows" claim, and Experiment 6 tests whether the trajectories (not just the static endpoints) track each other empirically.

### AIMD (Additive Increase, Multiplicative Decrease)
The control strategy used for Mechanism A's window size W. Under low queue occupancy, W grows multiplicatively by `grow_factor=1.15`; under high occupancy, W shrinks multiplicatively by `shrink_factor=0.70`. This mirrors TCP's congestion control philosophy — the asymmetry (slow growth, fast shrink) prevents oscillation and ensures the system converges to a stable operating point rather than hunting.

### Mechanism A (Discrete Actuator)
Controls the publish-cadence window size W. AIMD-governed: shrink W when queue occupancy exceeds `occ_high=0.70`, grow W when occupancy drops below `occ_low=0.30`, hold otherwise. W is captured once at window start and held fixed for the in-progress window — never changed mid-window.

### Mechanism B (Continuous Actuator)
Controls the IIR smoothing coefficient α of the per-key EMA feature. Driven by the same `EMAOccupancyTracker` reading as Mechanism A. Control law: `α[n] = α_min + (α_max − α_min) · L[n]`, slew-rate bounded by `|α[n]−α[n−1]| ≤ Δα_max`. Direction is opposite to Project 1: rising backpressure RAISES α (narrows memory), because under load, features published rarely need to reflect recent events, not long-term averages.

### MBB (Moving Block Bootstrap)
A bootstrap method for time-series data that preserves temporal dependence structure by resampling contiguous blocks rather than individual observations. Used for computing confidence intervals on Feature Regret and other metrics, because standard i.i.d. bootstrap would underestimate variance due to autocorrelation in the event stream.

### Out-of-Fold Prediction
A prediction made by a model that was never trained on the data point being predicted. In k-fold cross-validation, each fold's model produces predictions only for events in that fold's held-out set. This prevents train/test contamination — the specific bug that INV-002 exists to prevent.

---

## Datasets

### Taobao UserBehavior (Primary)
- **Source:** Alibaba Tianchi (`https://tianchi.aliyun.com/dataset/649`)
- **Access:** Free but requires credentialed Tianchi account registration. There is no anonymous direct-download link.
- **Format:** CSV, comma-separated, no header row: `user_id, item_id, category_id, behavior_type, timestamp`
- **Scale:** ~1 million users, ~100 million behavior records, November 25–December 3, 2017
- **Behavior types:** `pv` (page view), `cart` (add to cart), `fav` (favorite), `buy` (purchase)
- **Subsampling:** 10,000 users selected by `user_id` hash bucket (not row order), yielding ≈980,000 events
- **Label:** Forward-looking binary: `label[i] = 1` if the user's next `buy` occurs within H=5 of the user's own future events
- **Burst periods:** Identified from natural arrival-rate time series (90th percentile of per-minute event counts)
- **Why primary:** Has a genuine entity key (`user_id`) and a genuine downstream-relevant label (purchase propensity), making it a faithful realization of the keyed streaming-feature scenario

### ULB Credit Card Fraud (Secondary)
- **Source:** Kaggle, `mlg-ulb/creditcardfraud` (also hosted via ULB Machine Learning Group)
- **Access:** Kaggle account required
- **Format:** CSV with header: `Time, V1–V28, Amount, Class`
- **Scale:** 284,807 transactions over 2 days, 492 fraudulent (0.172% positive rate)
- **Critical limitation:** There is NO card, account, or merchant identifier in this dataset — every feature except `Time` and `Amount` is an anonymized PCA component (`V1`–`V28`). A per-entity keyed rolling feature literally cannot be computed from this data.
- **Usage:** ONLY for a global (non-keyed) variant of the pipeline — single rolling count and rolling sum/EMA of `Amount` across the entire transaction stream (effectively `user_id = 0` for every event, a degenerate single-key case)
- **Known limitation:** In this single-key mode, the controller's AIMD loop can exhibit pathological oscillation because there is no key diversity to smooth out burst patterns. This is a known, disclosed limitation — not a bug to re-fix. Document in the paper as an honest result.
- **Why secondary:** Tests whether the mechanism generalizes to a structurally different cost profile (global, non-keyed aggregation instead of per-key)

---

## Assumptions Inherited from Prior Projects

### AIMD Constants
- `shrink_factor = 0.70`, `grow_factor = 1.15`
- `occ_low = 0.30`, `occ_high = 0.70`

These are reused **unmodified** from the KLStream AdaptiveWindowOp project (Project 2), which itself validated them empirically. They are deliberately kept identical to maintain cross-project comparability of the backpressure control dynamics. This is a design decision, not an oversight, and should not be "improved" without new evidence per Constitution C45 (Workflow Changes Require Evidence).

### IIR Constants
- `α_min = 0.02`, `α_max = 0.30`
- `Δα_max = 0.01` per raw event

These are reused **unmodified** from the load-adaptive-iir project (Project 1). Same rationale: cross-project comparability is more valuable than local optimization.

---

## Condensed Narrative of the Eleven Original Findings

### Finding 1 — Dropped-Event Race Condition (→ INV-001)
The harness termination logic used queue-occupancy polling to determine when all events had been processed. Under certain timing conditions, the harness would declare "done" while events were still in flight between operators, causing the final output CSV to contain fewer rows than were emitted by the source. This was confirmed by observing that three repeated runs of the identical seed/architecture produced different row counts — a result that should be impossible for a deterministic pipeline. The fix is exact emitted==written event-count matching at termination, with zero tolerance.

### Finding 2 — Oracle Train/Test Contamination (→ INV-002)
The oracle scoring model was trained on an 80/20 split but then scored against 100% of events — including its own training data. This inflates the oracle's apparent accuracy and compresses the Feature Regret metric (since the oracle "knows" its training events perfectly, the gap between system and oracle shrinks artificially). The fix is k-fold cross-validated, out-of-fold-only predictions with a committed fold-assignment manifest proving every scored event was held out of its scoring model's training set.

### Finding 3 — Missing requirements.txt (→ INV-003)
The project had no `requirements.txt`. A fresh venv install failed on `numpy` (not listed as a dependency), and separately on `arch` (a specialized time-series library used for one optional analysis). This meant the project was not reproducibly buildable from a fresh clone — a direct violation of the reproducibility principle.

### Finding 4 — Unverified Baseline Parity (→ INV-004)
It was assumed, but never structurally verified, that all architecture variants shared identical queue capacities, worker topology, model weights, and replay data. If any of these differed silently between architectures, the controlled-experiment property (only the window operator varies) would be violated, and all comparative results would be confounded.

### Finding 5 — Duplicate/Ambiguous Data Files (→ INV-005)
During cleanup, files with overlapping apparent purpose were discovered: `replay_taobao_10k.csv` vs `replay_taobao_10k_real.csv`, and `oracle_scores.csv` vs `oracle_scores_real.csv`. In one case the files were identical (the `_real` suffix was a leftover from a prior naming scheme); in the other they differed. The ambiguity meant it was unclear which file was actually fed to which experiment run — a provenance failure.

### Finding 6 — Cross-Experiment Number Mixing (→ INV-006)
A Feature Regret value from a stress-experiment run was silently transcribed into the MaxRate results table in the paper draft — a different experiment's number appearing as if it belonged to the primary results. This was a bookkeeping error in how results get transcribed between runs and reports, not a pipeline bug, but it had the same effect: a published number that did not match its claimed source.

### Finding 7 — Fabricated All-Zero Per-Seed FR Stub (→ INV-007)
A per-seed Feature Regret computation function silently returned 0.0 for every seed and every architecture instead of computing a real value. This stub was not marked as such — it was presented as genuine output in a report. The fix is that no analysis function may ever return a stub/default value silently.

### Finding 8 — Verdict-Evidence-Adjacency Failure (→ INV-008)
In two independent audit passes, report sections presented Verdicts (PASS/FAIL) that were either directly contradicted by adjacent evidence or had no adjacent evidence at all. The fix is Dynamic Rule D-001, now encoded in `gatekeeper.py` as an automatic check.

### Finding 9 — RALF's Unexplained Inflated AUROC (→ INV-009)
The RALF-surrogate baseline's absolute AUROC exceeded the oracle's in some configurations — a result that should be impossible by construction (the oracle, by definition, uses maximally fresh features). This was accepted without investigation until flagged during auditing. The fix is that any anomalous result must be investigated with a stated hypothesis and direct test before acceptance.

### Finding 10 — Missing Golden Parity Test (→ INV-010)
The build prompt specified that a golden parity test (independent Python recomputation of the C++ feature formulas, diffed against live C++ output) should exist as a named component of the test architecture. It was never actually built. The fix is that this test is a first-class deliverable from the start, not an afterthought.

### Finding 11 — RALF Tuning Asymmetry (→ INV-011)
The RALF-surrogate baseline was run in a single, un-tuned configuration and compared against the primary contribution, which had been swept across multiple parameter configurations. An untuned single-configuration baseline compared against a swept contribution is not a valid comparison — it systematically disadvantages the baseline. The fix is that baseline comparison effort must be symmetric.
