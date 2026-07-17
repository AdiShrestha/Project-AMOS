# Roadmap — BPFeat

**Project:** BPFeat — Backpressure-Driven Elastic Feature Windows for Real-Time ML Pipelines
**Factory Version:** 1.0.1
**Created:** 2026-07-17
**Owner:** Claude (Architect)

---

## Chunk 01: Factory Bootstrap & Gatekeeper [COMPLETE]

**Objective:** Initialize the Factory for the BPFeat project — create all required project documents, seed the Gatekeeper with v1 checks mapped to confirmed prior failures, seed the first Dynamic Rule (D-001), and pass the Project Approval Gate.

**Deliverables:**
- `project/project_description.md` — complete
- `project/architecture.md` — complete
- `project/project_knowledge.md` — complete
- `project/invariants.md` — complete
- `project/roadmap.md` — complete (this file)
- `factory/gatekeeper.py` v1 — complete
- `factory/dynamic_rules.md` updated with D-001 — complete
- `project/evolution/decision_log.md` with D-EVOL-001 — complete
- Gatekeeper smoke test passing on `required_project_artifacts` — complete

**Dependencies:** None (first chunk)

**Estimated Complexity:** Low — primarily document generation, no implementation code

**Success Criteria:**
- All five project documents exist and are non-empty
- Gatekeeper v1 runs and produces a valid report
- D-001 is appended to `dynamic_rules.md` in the correct format
- D-EVOL-001 is logged in `decision_log.md`
- Project Approval Gate checklist passes
- Human approves all artifacts

---

## Chunk 02: KLStream Runtime Core [COMPLETE]

**Objective:** Implement the foundational KLStream runtime components: event types, SPSC/MPMC queues, operator base class, backpressure infrastructure (EMAOccupancyTracker, TokenBucketRateLimiter), worker scheduling, and the runtime coordinator — with the INV-001 termination fix (exact emitted==written event-count matching) built in from first implementation, not retrofitted.

**Deliverables:**
- `source/include/klstream/core/config.hpp` — runtime configuration
- `source/include/klstream/core/event.hpp` — templated Event type
- `source/include/klstream/core/spsc_queue.hpp` — lock-free single-producer single-consumer queue
- `source/include/klstream/core/mpmc_queue.hpp` — multi-producer multi-consumer queue
- `source/include/klstream/core/operator.hpp` — operator base class with `tick()` interface
- `source/include/klstream/core/backpressure.hpp` — EMAOccupancyTracker, TokenBucketRateLimiter, BackpressureSignal
- `source/include/klstream/core/worker.hpp` — cooperative scheduler
- `source/include/klstream/core/runtime.hpp` — runtime coordinator with exact-count termination
- `source/include/klstream/core/metrics.hpp` — runtime metrics collection
- Unit tests for each component
- CMakeLists.txt for the core library

**Dependencies:** Chunk 01 (Factory Bootstrap)

**Estimated Complexity:** High — lock-free queue implementation requires careful attention to memory ordering; termination handshake is the critical INV-001 path

**Success Criteria:**
- All core types compile and pass unit tests
- SPSC/MPMC queues pass concurrent stress tests
- Termination handshake demonstrates exact event-count matching across 3 repeated runs
- No data races detected by ThreadSanitizer

---

## Chunk 03: BPFeat Feature Pipeline Operators

**Objective:** Implement all five BPFeat-specific operator classes (KeyedFeatureExtractOp, AdaptiveFeatureWindowOp, FixedWindowOp, DriftAdaptiveWindowOp, ScoringFlushOp) plus BehaviorSource and ResultSink, with INV-004 baseline-parity structure designed in from the start.

**Deliverables:**
- `source/include/klstream/feature/types.hpp` — RawBehaviorEvent, FeatureSnapshot, FeatureBatch, ScoredResult, EMAFeatureState
- `source/operators/behavior_source.hpp` — CSV replay source with Taobao/ULB mode selection
- `source/operators/keyed_feature_extract_op.hpp` — per-key EMA feature extraction with Mechanism B
- `source/operators/adaptive_feature_window_op.hpp` — dual-actuator window with Mechanism A
- `source/operators/drift_adaptive_window_op.hpp` — two-EMA crossover drift detector
- `source/operators/scoring_flush_op.hpp` — native logistic regression scoring with O(W) cost
- `source/operators/result_sink.hpp` — CSV output with exact row-count matching
- Unit tests for each operator
- Integration test: end-to-end pipeline with a small synthetic dataset

**Dependencies:** Chunk 02 (KLStream Runtime Core)

**Estimated Complexity:** High — KeyedFeatureExtractOp's bounded hash map and Mechanism B integration; AdaptiveFeatureWindowOp's dual-actuator control loop; ScoringFlushOp's native model loading

**Success Criteria:**
- All operators compile, pass unit tests, and integrate into a working pipeline
- INV-004 verified: all architectures share identical configuration except window operator
- Mechanism B's α control law matches the specification in architecture.md
- Integration test produces non-trivial scored output

---

## Chunk 04: Offline Preprocessing & K-Fold Oracle Pipeline

**Objective:** Implement the Python offline preprocessing scripts (Taobao and ULB) and the k-fold cross-validated oracle training pipeline, producing the replay CSV, oracle scores CSV, fold assignments CSV, and model weights JSON — all per INV-002 (no train/test contamination).

**Deliverables:**
- `preprocessing/preprocess_taobao.py` — Taobao UserBehavior subsampling, label computation, burst tagging
- `preprocessing/preprocess_ulb.py` — ULB Credit Card Fraud single-key preprocessing
- `preprocessing/train_oracle.py` — k-fold cross-validated logistic regression with α grid search
- `data/replay/replay_taobao_10k.csv` — preprocessed replay data
- `data/replay/oracle_scores.csv` — out-of-fold oracle predictions
- `data/replay/fold_assignments.csv` — fold assignment manifest (INV-002)
- `models/oracle_weights.json` — exported model weights for C++ native scoring
- Verification script proving 100% coverage with zero train/test overlap
- `requirements.txt` — pinned Python dependencies (INV-003)

**Dependencies:** Chunk 01 (project documents define the oracle methodology)

**Estimated Complexity:** Medium — the k-fold oracle with fold manifest is straightforward but must be done correctly to satisfy INV-002; the Taobao preprocessing requires handling the large raw file efficiently

**Success Criteria:**
- INV-002 verified: fold-assignment manifest proves 100% coverage, zero overlap
- INV-003 verified: fresh venv + `pip install -r requirements.txt` succeeds
- Oracle AUROC reported per fold and overall
- Replay CSV row counts match expected subsampled size
- SC-002 and SC-003 satisfied

---

## Chunk 05: Seven-Architecture Wiring & Harness

**Objective:** Implement `main.cpp` and `harness.cpp` that wire all operators, queues, and workers for each of the seven architecture configurations (Fixed, Drift, Throttle, A-only, B-only, Adaptive, RALF-surrogate), selectable via command-line flags.

**Deliverables:**
- `source/main.cpp` — entry point with CLI argument parsing
- `source/harness.cpp` / `source/harness.hpp` — pipeline wiring per architecture
- `source/ralf_surrogate.hpp` — RALF-style priority-weighted refresh scheduler
- Configuration logging at startup (for INV-004 post-hoc verification)
- Shell script for running all architectures × all seeds
- `requirements.txt` updated if any new Python dependencies are introduced
- `CMakeLists.txt` updated for the harness target

**Dependencies:** Chunk 02 (runtime core), Chunk 03 (operators), Chunk 04 (replay data and model weights)

**Estimated Complexity:** Medium — the wiring itself is mechanical, but the RALF-surrogate requires careful implementation of the priority-weighted refresh scheduling logic

**Success Criteria:**
- All seven architectures build, run, and produce valid output CSVs
- INV-001 verified: three repeated runs per architecture produce identical row counts
- INV-004 verified: configuration logs show identical parameters across architectures (except window operator)
- SC-001 and SC-004 satisfied

---

## Chunk 06: Statistical Analysis Pipeline

**Objective:** Implement the Python analysis pipeline that computes Feature Regret with MBB confidence intervals, burst-stratified staleness, Jain fairness index, per-seed FR (INV-007, no stubs), absolute AUROC reporting (INV-009, anomaly flagging), and paired-difference tests across seeds.

**Deliverables:**
- `analysis/compute_metrics.py` — main analysis entry point
- `analysis/feature_regret.py` — per-seed and pooled FR computation with MBB CIs
- `analysis/staleness_analysis.py` — burst-stratified staleness metrics
- `analysis/fairness.py` — Jain fairness index and fairness gap computation
- `analysis/statistical_tests.py` — paired-difference tests, sensitivity analysis
- `results/metrics_summary.csv` — summary output with provenance header
- Block-length sensitivity analysis for MBB

**Dependencies:** Chunk 05 (harness output CSVs), Chunk 04 (oracle scores for regret computation)

**Estimated Complexity:** Medium-High — MBB implementation requires care with block-length selection; per-seed FR must be a real computation (INV-007), not a stub; anomaly flagging (INV-009) requires defining and implementing the detection heuristic

**Success Criteria:**
- INV-007 verified: no analysis function returns 0.0 or a default silently
- INV-009 verified: RALF AUROC > oracle AUROC flagged as "ANOMALOUS"
- INV-011 verified: analysis reports configuration count per architecture
- MBB block-length sensitivity documented
- SC-006, SC-007, SC-009, SC-011 satisfied

---

## Chunk 07: Test Suite & Golden Parity Verification

**Objective:** Implement the complete test suite including the golden parity test (INV-010) that independently verifies C++ feature computation matches Python recomputation, plus regression tests for all confirmed prior bugs.

**Deliverables:**
- `tests/test_golden_parity.py` — C++ vs Python feature computation comparison
- `tests/test_termination_parity.py` — 3-run row-count identity test (INV-001 regression)
- `tests/test_oracle_integrity.py` — fold-assignment coverage and overlap check (INV-002 regression)
- `tests/test_baseline_parity.py` — configuration identity across architectures (INV-004 regression)
- `tests/test_no_stubs.py` — analysis function non-stub verification (INV-007 regression)
- `tests/test_verdict_adjacency.py` — report verdict-evidence check (INV-008/D-001 regression)
- Integration tests for the full pipeline
- Test runner script and CI configuration

**Dependencies:** Chunk 02–06 (all implementation must exist for testing)

**Estimated Complexity:** Medium — the golden parity test (INV-010) requires a faithful Python reimplementation of the C++ EMA formulas; other tests are straightforward assertions

**Success Criteria:**
- INV-010 verified: golden parity test passes with ≤1e-6 relative error per feature component
- All regression tests pass
- Full test suite runs from `pytest` with zero failures
- SC-003 verified: fresh clone → build → test succeeds end-to-end
- SC-010 satisfied

---

## Chunk 08: Full Experimental Run & Evidence Collection

**Objective:** Execute the full experimental protocol: all seven architectures × 5+ seeds × Taobao primary dataset, plus the ULB secondary dataset generalization runs. Collect all raw output, compute all metrics, investigate any anomalous results (INV-009), and produce the checksummed results directories that paper tables will reference (INV-006).

**Deliverables:**
- `results/runs/primary_7arch_5seed/` — all raw output CSVs, configuration logs, harness summaries
- `results/runs/ulb_generalization/` — ULB secondary dataset runs
- `results/metrics_summary.csv` — complete metrics with provenance headers
- Investigation reports for any anomalous results (INV-009)
- SHA-256 checksums for all results directories
- Run scripts with exact commands for reproducibility

**Dependencies:** Chunk 05 (harness), Chunk 06 (analysis pipeline), Chunk 07 (test suite passes)

**Estimated Complexity:** Medium — execution is mechanical, but anomalous result investigation (INV-009) may require additional diagnostic runs

**Success Criteria:**
- All runs complete without termination errors (INV-001)
- Row counts verified across repeated seeds
- No anomalous results accepted without investigation (INV-009)
- INV-006 verified: every number traces to a named, checksummed directory
- Checksums committed to repository
- SC-001, SC-006, SC-009 satisfied

---

## Chunk 09: Paper Artifact Generation

**Objective:** Generate publication-ready paper artifacts (tables, figures, statistical analysis summaries) from the validated experimental results, with every number provenance-traceable to the checksummed results directories.

**Deliverables:**
- `paper/tables/table1_main_results.tex` — main results table (FR, staleness, fairness, coverage per architecture)
- `paper/tables/table2_ablation.tex` — ablation study (A-only vs B-only vs Adaptive)
- `paper/figures/` — burst-stratified staleness plots, W/α trajectory plots, Z-domain frequency response heatmap
- `paper/tables/table3_ulb_generalization.tex` — secondary dataset results
- `paper/statistics/` — paired-difference test outputs, MBB sensitivity analysis
- `paper/draft.md` — updated paper draft with all tables and figures integrated
- Provenance footnotes in every table referencing source results directory

**Dependencies:** Chunk 08 (experimental results)

**Estimated Complexity:** Low-Medium — primarily formatting and assembly; the statistical content already exists from Chunk 06

**Success Criteria:**
- Every number in every table traces to the checksummed results directory (INV-006)
- No number from a different experiment appears in the wrong table (INV-006)
- INV-008/D-001 satisfied: every verdict in any generated report has adjacent evidence
- Paper draft internally consistent
- SC-006, SC-008 satisfied
