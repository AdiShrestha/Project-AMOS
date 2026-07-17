# Architecture — BPFeat

**Project:** BPFeat — Backpressure-Driven Elastic Feature Windows for Real-Time ML Pipelines
**Factory Version:** 1.0.1
**Created:** 2026-07-17
**Owner:** Claude (Architect)
**Provenance:** Reverse-engineered from `bpfeat_build_prompt.md` Sections 8, 12–23

---

## System Overview

BPFeat is a five-stage streaming ML feature pipeline built inside the KLStream runtime:

```
BehaviorSource → KeyedFeatureExtractOp → [WindowOp variant] → ScoringFlushOp → ResultSink
```

Four interchangeable window-stage implementations, swapped via a command-line flag, all producing the same `Event<FeatureBatch>` type so `ScoringFlushOp` and everything downstream is completely unaware which window strategy is active.

| Variant | Implementation | Sizing Logic | Represents |
|---|---|---|---|
| Fixed | `FixedWindowOp` (reused from KLStream) | constant W=128 | static configuration (current practice) |
| DriftAdaptive | `DriftAdaptiveWindowOp` (new) | two-EMA crossover on engagement rate | literature-style data-driven adaptation (ADWIN lineage) |
| RateThrottle | `FixedWindowOp` + `RateThrottleSource` (reused) | constant W=128, throttled admission rate | current industry practice (Spark/Flink-style) |
| Adaptive | `AdaptiveFeatureWindowOp` (new) | EMA of own output queue occupancy → W and α | the contribution |

Three additional ablation variants are produced by selectively disabling one actuator:
- **A-only**: adaptive W, fixed α=0.10 (no Mechanism B)
- **B-only**: fixed W=128, adaptive α (no Mechanism A)
- **RALF-surrogate**: priority-weighted per-key refresh scheduling under fixed compute budget

---

## Architectural Principles

1. **Single variable under test**: The only thing that changes between architectures is the window/freshness control logic. Runtime, queue capacities, model weights, worker topology, and replay data are identical.
2. **O(1) feature update, O(W) publish cost**: The EMA recursion in `KeyedFeatureExtractOp` is O(1) per event at any α. The scoring cost in `ScoringFlushOp` is O(W·d) per tick. This asymmetry is what creates the backpressure feedback loop.
3. **Same signal, two actuators**: Both Mechanism A (discrete W) and Mechanism B (continuous α) read from the same `EMAOccupancyTracker` — no second, independent tracker.
4. **Downstream-agnostic window stage**: All window variants produce `Event<FeatureBatch>` — `ScoringFlushOp` never knows which strategy is active.

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           KLStream Runtime                              │
│  ┌──────────────┐   ┌──────────────────────┐   ┌──────────────────┐    │
│  │ BehaviorSource│──▶│ KeyedFeatureExtractOp│──▶│ [WindowOp variant]│   │
│  │ (replay CSV)  │   │ (O(1)/event, per-key │   │ (buffers W       │   │
│  │               │   │  EMA state, reads     │   │  FeatureSnapshots│   │
│  └──────────────┘   │  BackpressureSignal   │   │  into batches)   │   │
│                      │  for α via Mech B)    │   └────────┬─────────┘   │
│                      └──────────────────────┘             │             │
│                                                            ▼             │
│                      ┌──────────────────────┐   ┌──────────────────┐    │
│                      │     ResultSink        │◀──│  ScoringFlushOp  │   │
│                      │ (CSV logging, exact   │   │ (native LR dot   │   │
│                      │  row-count matching   │   │  product, O(W·d) │   │
│                      │  at termination)      │   │  per tick)       │   │
│                      └──────────────────────┘   └──────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ BackpressureSignal (shared struct)                               │    │
│  │ • Owner/publisher: AdaptiveFeatureWindowOp                       │    │
│  │ • Reader: KeyedFeatureExtractOp (for Mechanism B's α)            │    │
│  │ • Source: EMAOccupancyTracker on WindowOp's output queue         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Module Responsibilities

### `BehaviorSource` (`source/operators/behavior_source.hpp`)
- Replays preprocessed CSV events (Taobao or ULB format) in timestamp order
- Supports `--dataset {taobao, ulb}` flag for column layout selection
- Optional burst injection via synthetic inter-arrival compression
- Emits `Event<RawBehaviorEvent>` with `key = user_id`
- For RateThrottle variant: wraps with `TokenBucketRateLimiter` from `backpressure.hpp`

### `KeyedFeatureExtractOp` (`source/operators/keyed_feature_extract_op.hpp`)
- Map operator: O(1) per event regardless of α or W
- Maintains per-user `EMAFeatureState` in a bounded hash map (LRU eviction at capacity)
- Reads `BackpressureSignal.ema_occupancy` to compute α[n] via Mechanism B's control law when signal is non-null
- For Fixed/Drift/Throttle architectures: α is a compile-time constant (default 0.10)
- Emits `Event<FeatureSnapshot>` per raw event
- Feature vector: `[ema_engagement, log1p(pv_count), log1p(cart_count+fav_count), clip(recency_sec,0,3600)/3600]`

### `AdaptiveFeatureWindowOp` (`source/operators/adaptive_feature_window_op.hpp`)
- **The core contribution operator**
- Owns an `EMAOccupancyTracker` wrapping its own output queue (ScoringFlushOp's input)
- Publishes `BackpressureSignal` for `KeyedFeatureExtractOp` to read
- Mechanism A: AIMD control of window size W
  - Shrink: `W_next = max(w_min, floor(W_current * shrink_factor))` when `occ > occ_high`
  - Grow: `W_next = min(w_max, ceil(W_current * grow_factor))` when `occ < occ_low`
  - Hold: unchanged otherwise
  - W captured once at window start, held fixed for in-progress window
  - Defaults: `w_min=8, w_max=256, shrink=0.70, grow=1.15, occ_low=0.30, occ_high=0.70`
- Buffers W `FeatureSnapshot`s, emits `Event<FeatureBatch>`

### `FixedWindowOp` (reused from KLStream `operators/window.hpp`)
- Static W=128, no backpressure reading
- Buffers and emits `Event<FeatureBatch>` identically to Adaptive

### `DriftAdaptiveWindowOp` (`source/operators/drift_adaptive_window_op.hpp`)
- Two-timescale EMA crossover drift detector on per-tick engagement rate
- Fast EMA vs slow EMA: shrink W when they diverge past threshold, grow otherwise
- Function of input data only, never of queue state
- **CORRECTED FROM PRIOR IMPLEMENTATION**: Uses AIMD-like control with the same (w_min, w_max) bounds as Adaptive, preventing unconstrained growth → INV-004

### `ScoringFlushOp` (`source/operators/scoring_flush_op.hpp`)
- Pops one `Event<FeatureBatch>` per `tick()` call
- For each of the W `FeatureSnapshot`s: native logistic regression dot product + sigmoid
- Writes `ScoredResult` including predicted probability, label, staleness, feature vector
- **CORRECTED FROM PRIOR IMPLEMENTATION**: Termination uses exact emitted==written event-count matching, not queue-occupancy polling → INV-001

### `ResultSink` (`source/operators/result_sink.hpp`)
- CSV output: every `ScoredResult` with full provenance
- **CORRECTED FROM PRIOR IMPLEMENTATION**: Exact row-count matching with `ScoringFlushOp`'s emitted count at termination → INV-001
- Controller trace logging for Adaptive/AOnly/BOnly variants (W, α, direction changes, occupancy)

### `BackpressureSignal` (`source/types/backpressure_signal.hpp`)
- Small shared struct published by `AdaptiveFeatureWindowOp`, read by `KeyedFeatureExtractOp`
- Contains: `ema_occupancy` (float, 0-1), `current_W` (uint32_t), `current_alpha` (float)
- Null (nullptr) for Fixed/Drift/Throttle architectures — `KeyedFeatureExtractOp` checks null and falls back to constant α

### `Harness` (`source/harness.cpp`)
- Wires operators, queues, workers for a given architecture configuration
- **CORRECTED FROM PRIOR IMPLEMENTATION**: Termination handshake via exact event-count matching, not queue-drain polling → INV-001
- **CORRECTED FROM PRIOR IMPLEMENTATION**: All architectures share identical queue capacities, worker topology, and model path — the only variation is the window operator class and BackpressureSignal null-ness → INV-004

---

## External Dependencies

| Dependency | Purpose | Version Constraint |
|---|---|---|
| C++17 compiler | Runtime | Apple Clang 14+ or GCC 12+ |
| CMake | Build system | 3.16+ |
| Python 3 | Preprocessing, oracle, analysis | 3.10+ |
| scikit-learn | Oracle logistic regression training | Pinned in requirements.txt |
| numpy | Numerical computation | Pinned in requirements.txt |
| pandas | Data manipulation | Pinned in requirements.txt |
| scipy | MBB bootstrap, statistical tests | Pinned in requirements.txt |
| **CORRECTED FROM PRIOR IMPLEMENTATION**: All Python dependencies pinned in a single `requirements.txt` — not discovered at runtime → INV-003 |

---

## Interfaces

### Command-Line Interface (`main.cpp` / `harness`)

```
./harness --arch {fixed|drift|throttle|aonly|bonly|adaptive|ralf}
          --replay <path_to_replay_csv>
          --oracle <path_to_oracle_scores_csv>
          --model <path_to_model_weights>
          --seed <uint32>
          --out-dir <results_directory>
          [--dataset {taobao|ulb}]
          [--delay-per-item-us <uint32>]  # synthetic scoring cost
```

### Oracle Pipeline Interface

```
python3 preprocessing/train_oracle.py \
    --replay data/replay/replay_taobao_10k.csv \
    --n-folds 5 \
    --alpha-grid 0.02,0.05,0.10,0.15,0.20,0.30 \
    --out-scores data/replay/oracle_scores.csv \
    --out-folds data/replay/fold_assignments.csv \
    --out-model models/oracle_weights.json
```

### Analysis Pipeline Interface

```
python3 analysis/compute_metrics.py \
    --raw-dir results/runs/<run_name>/ \
    --oracle-csv data/replay/oracle_scores.csv
```

---

## Data Flow

```
Raw CSV (Taobao/ULB)
    │
    ▼ [Python preprocessing]
Replay CSV (uniform schema)
    │
    ▼ [Python oracle training]
Oracle Scores CSV + Fold Assignments CSV + Model Weights JSON
    │
    ▼ [C++ harness, per seed × per architecture]
Per-seed Results CSV (ScoredResult rows)
    │
    ▼ [Python analysis]
Metrics Summary CSV + Figures + Paper Tables
```

---

## Error Boundaries

1. **Preprocessing errors**: Fail loudly with row-count assertions. Never produce partial output.
2. **Oracle training errors**: Fail if any fold has zero positive labels. Log fold-level AUROC.
3. **Runtime errors**: Operator `tick()` failures propagate via return codes. Queue overflow = operator-level backpressure (blocking push), never silent drop.
4. **Termination errors**: Exact event-count mismatch between emitted and written triggers a hard failure, not a warning → INV-001.
5. **Analysis errors**: Metrics functions that cannot compute a real value must raise an exception, never return 0.0 or a default → INV-007.

---

## Future Extension Points

1. **Additional datasets**: The replay CSV schema is dataset-agnostic; new datasets require only a preprocessing script producing the same column layout.
2. **Additional window variants**: Any operator producing `Event<FeatureBatch>` can be plugged into the pipeline without modifying downstream operators.
3. **Model upgrades**: The model interface is a simple weight-vector dot product; upgrading to a more complex model requires only changing `ScoringFlushOp`'s scoring function.
4. **Distributed deployment**: The mechanism maps directly onto Flink's `KeyedProcessFunction` + `ProcessingTimeTimer` API, as documented in the paper's Discussion section.

---

## Corrected-From-Prior-Implementation Summary

| Correction | Component | Invariant | One-Line Reason |
|---|---|---|---|
| Exact emitted==written event-count matching | ScoringFlushOp, ResultSink, Harness | INV-001 | Queue-occupancy polling caused dropped events in the prior implementation, confirmed via row-count divergence across repeated runs |
| K-fold cross-validated oracle with fold manifest | Oracle pipeline | INV-002 | Prior used 80/20 split scored against 100% of events — train/test contamination |
| Pinned requirements.txt as architectural component | Build system | INV-003 | Prior had no requirements.txt; fresh venv imports failed on numpy, then separately on `arch` |
| Structural baseline parity verification | Harness | INV-004 | Prior never verified that all architectures shared identical queues/model/topology |
| **CORRECTED FROM PRIOR IMPLEMENTATION**: Golden parity test is a named component of the test architecture from the start | Test suite | INV-010 | Prior specified but never built this test — online C++ vs offline Python feature recomputation |
| **CORRECTED FROM PRIOR IMPLEMENTATION**: Per-seed Feature Regret is a fully implemented function from the start | Analysis pipeline | INV-007 | Prior had a stub that silently returned 0.0 for every seed and architecture |
