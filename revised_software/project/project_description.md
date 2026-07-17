# Project Description — BPFeat

**Project:** BPFeat — Backpressure-Driven Elastic Feature Windows for Real-Time ML Pipelines
**Factory Version:** 1.0.1
**Created:** 2026-07-17
**Owner:** Claude (Architect)
**Status:** Initialized

---

## Executive Summary

BPFeat repurposes a validated backpressure signal — the EMA-smoothed occupancy of a stream-processing operator's own output queue — to simultaneously drive two coupled actuators in a keyed ML feature pipeline: (1) a discrete, AIMD-controlled publish-cadence window size `W` governing how often per-key feature snapshots are republished to a downstream model, and (2) a continuous, slew-rate-bounded IIR pole `α` governing how reactive each feature's underlying exponential moving average is to recent events. The system is implemented inside KLStream, a bespoke, lock-free, multi-core C++17 stream-processing runtime, and evaluated not via proxy metrics but via the actual downstream cost that matters: the degradation in a real classifier's predictive quality (regret, in RALF's sense) caused by features being staler or more aggressively smoothed than an oracle's.

This is a **reverse-engineering task**. The system was previously designed, built, run against real data, and audited over the course of roughly a month in a prior, non-Factory-governed project. The science is validated and is not being redesigned here. What was missing was engineering discipline: no contracts, no invariants, no deterministic gate, ambiguous file provenance, and — critically — eleven specific, confirmed bugs and methodology gaps that were found by accident during ad hoc auditing rather than prevented structurally. This project formalizes the validated design into proper Factory artifacts and converts every one of those eleven findings into a permanent, checkable invariant.

---

## Motivation

Real-time ML feature pipelines face a freshness-vs-cost trade-off that current practice treats as a static configuration problem: an engineer picks a fixed TTL, a fixed window size, or a fixed refresh cadence, once, by hand, and the system lives with that choice regardless of load. No prior systems paper treats feature-pipeline freshness-vs-cost as a closed-loop, queue-state-driven control problem with both a discrete and a continuous actuator, formally connects the two via the EWMA span-to-α identity, and validates the connection empirically rather than asserting it.

The prior implementation demonstrated the mechanism works but suffered from engineering-discipline failures that a Factory-governed process would have prevented structurally. This re-implementation exists to produce a codebase that is reproducible, auditable, and defensible for publication.

---

## Objectives

1. Faithfully re-implement the BPFeat dual-actuator backpressure-driven feature pipeline as specified in the validated architecture (`architecture.md`), correcting all eleven confirmed bugs and methodology gaps from the prior project.
2. Produce a complete, reproducible experimental pipeline that evaluates all seven architecture variants across two datasets (Taobao UserBehavior primary, ULB Credit Card Fraud secondary) using Feature Regret as the headline metric.
3. Ensure every number in any report or paper table traces to one named, checksummed results directory and the exact command that produced it.
4. Generate publication-ready paper artifacts (tables, figures, statistical analysis) from the validated experimental results.

---

## Scope

### In Scope

- KLStream runtime core: events, queues, operators, backpressure, workers, with the INV-001 termination fix built in from first implementation
- All five BPFeat-specific operator classes: `KeyedFeatureExtractOp`, `AdaptiveFeatureWindowOp`, `FixedWindowOp`, `DriftAdaptiveWindowOp`, `ScoringFlushOp`, plus `BehaviorSource` and `ResultSink`
- Mechanism A (discrete W, AIMD) and Mechanism B (continuous α, slew-rate-bounded)
- Offline preprocessing for Taobao and ULB datasets
- K-fold cross-validated oracle pipeline with fold-assignment manifest (INV-002)
- Seven-architecture wiring via command-line flags
- Statistical analysis pipeline: MBB confidence intervals, paired-difference tests, per-seed Feature Regret
- Test suite including golden parity verification (INV-010)
- Full experimental runs across 5+ seeds per architecture
- Paper artifact generation

### Out of Scope

Re-deriving BPFeat's research questions, theoretical foundation, or experimental design from first principles is explicitly OUT OF SCOPE. That design was already produced and is treated as pre-approved input architecture (see `architecture.md` provenance). This project's scope is faithful, corrected re-implementation.

---

## Functional Requirements

### FR-001: Event Replay Pipeline
The system shall replay preprocessed CSV event streams (Taobao or ULB format) through a configurable multi-operator pipeline, processing events in timestamp order within each user's sequence.

### FR-002: Per-Key Feature Extraction
`KeyedFeatureExtractOp` shall maintain per-user EMA feature state in a bounded hash map, updating incrementally in O(1) per event, with the smoothing coefficient α driven by Mechanism B's control law when a `BackpressureSignal` is present.

### FR-003: Four Interchangeable Window Variants
The pipeline shall support four window-stage implementations (`FixedWindowOp`, `DriftAdaptiveWindowOp`, `RateThrottleSource` + `FixedWindowOp`, `AdaptiveFeatureWindowOp`), all producing identical `Event<FeatureBatch>` output types so downstream operators are completely unaware which strategy is active.

### FR-004: Dual-Actuator Backpressure Control
`AdaptiveFeatureWindowOp` shall read its own output queue's EMA occupancy and drive both Mechanism A (discrete W via AIMD) and Mechanism B (continuous α via slew-rate-bounded control law), using the same `EMAOccupancyTracker` reading for both.

### FR-005: Native Logistic Regression Scoring
`ScoringFlushOp` shall score each `FeatureSnapshot` in a batch using a native C++ logistic regression (dot product + sigmoid) with weights imported from a scikit-learn-trained model, with cost O(W·d) per tick.

### FR-006: Oracle Scoring Pipeline
An offline Python pipeline shall produce k-fold cross-validated oracle scores (out-of-fold predictions) with a committed fold-assignment manifest covering 100% of scored events.

### FR-007: Result Logging and Provenance
`ResultSink` shall log every `ScoredResult` with full provenance (timestamp, user_id, predicted score, label, staleness, architecture, seed, burst period flag) to CSV, with exact row-count matching at termination.

### FR-008: Seven Architecture Configurations
The harness shall support seven architecture configurations via command-line flags: Fixed, Drift, Throttle, A-only (adaptive W, fixed α), B-only (fixed W, adaptive α), Adaptive (both), and RALF-surrogate.

### FR-009: Statistical Analysis Pipeline
The analysis pipeline shall compute Feature Regret with MBB confidence intervals, burst-stratified staleness, Jain fairness index, and paired-difference tests across seeds.

### FR-010: Reproducible Build and Test
A single `requirements.txt` and CMake configuration shall allow a genuinely fresh clone, fresh venv, fresh `pip install`, full C++ build, and all passing tests with no manual intervention.

---

## Non-Functional Requirements

### NFR-001: Deterministic Reproducibility
Given identical seed, architecture configuration, dataset, and model weights, repeated runs shall produce byte-identical output row counts and statistically equivalent metrics.

### NFR-002: Performance
The pipeline shall process the full Taobao 10k-user replay (≈980k events) within a reasonable time on a single-node multi-core system (target: under 5 minutes per seed per architecture).

### NFR-003: Memory Efficiency
Per-user state in the bounded hash map shall not exceed available RAM for the largest supported user count (20,000 users).

### NFR-004: Portability
The C++ code shall build on macOS (Apple Clang) and Linux (GCC 12+) with C++17 support. Hardware acceleration detection (if any) shall be dynamic.

---

## Constraints

- **Language:** C++17 for the runtime and operators; Python 3.10+ for preprocessing, oracle training, and analysis
- **Build system:** CMake 3.16+
- **Runtime:** KLStream — no external stream-processing framework (Kafka, Flink, Spark)
- **Model:** Native logistic regression only — no ONNX, no external serving infrastructure
- **Datasets:** Taobao UserBehavior (credentialed Tianchi download required), ULB Credit Card Fraud (Kaggle)
- **Parameters:** AIMD constants (shrink=0.70, grow=1.15, occ_low=0.30, occ_high=0.70) and IIR constants (α_min=0.02, α_max=0.30) are reused unmodified from validated prior work — not tuned

---

## Success Criteria

### SC-001: Termination Correctness
Harness termination uses exact emitted==written event-count matching. Three repeated runs of the identical seed/architecture produce byte-identical row counts. Zero tolerance.

### SC-002: Oracle Integrity
The oracle scoring model is never evaluated on any event from its own training fold. Verified via a committed fold-assignment manifest covering 100% of scored events.

### SC-003: Reproducible Build
A single pinned requirements.txt allows a genuinely fresh clone, fresh venv, fresh `pip install`, full C++ build, and 9/9 (or current full count) passing tests, with no manual intervention.

### SC-004: Baseline Parity
All architecture variants share identical replay file, seed, model weights, worker topology, and queue capacities; the only permitted variation is the window-operator class and BackpressureSignal null-ness. Verified structurally, not assumed.

### SC-005: No Ambiguous Files
No two files with overlapping apparent purpose exist without either being proven identical and deduplicated, or explicitly named to encode what differs between them.

### SC-006: Number Provenance
Every number in any report or paper table traces to one named, checksummed results directory and the exact command that produced it.

### SC-007: No Stub Returns
No analysis function returns a stub/default value silently, ever.

### SC-008: Verdict Evidence Adjacency
Every report Verdict has adjacent, quoted raw evidence (enforced by Gatekeeper D-001).

### SC-009: Anomalous Results Investigation
Any result that moves sharply in an unexpected direction (e.g., one baseline's absolute accuracy exceeding the oracle's) is investigated with a stated hypothesis and a direct test of that hypothesis before being accepted into any report.

### SC-010: Golden Parity Test
A golden parity test independently verifies that online (C++) feature computation matches an offline (Python) recomputation of the same formulas, before any accuracy metric derived from those features is trusted.

### SC-011: Baseline Tuning Symmetry
Any baseline comparison (e.g., against a RALF-style surrogate) receives sensitivity analysis effort equivalent to what the primary contribution receives — an untuned single-configuration baseline compared against a swept contribution is not accepted as a valid comparison.
