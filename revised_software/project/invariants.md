# Invariants — BPFeat

**Project:** BPFeat — Backpressure-Driven Elastic Feature Windows for Real-Time ML Pipelines
**Factory Version:** 1.0.1
**Created:** 2026-07-17
**Owner:** Claude (Architect)

---

## INV-001: Termination Event-Count Matching

**Description:** The harness termination handshake uses exact emitted==written event-count matching. `BehaviorSource` emits a known count of events; `ResultSink` writes a known count of scored results. These two counts must match exactly at termination. Three repeated runs of the identical seed and architecture must produce byte-identical row counts. Zero tolerance — any discrepancy is a hard failure, not a warning.

**Reason:** The prior implementation used queue-occupancy polling to determine when processing was complete. Under certain timing conditions, the harness declared "done" while events were still in flight between operators, producing output CSVs with fewer rows than expected. This was confirmed independently in two separate audit passes by observing that three repeated runs of the identical seed/architecture produced different row counts — an outcome that is impossible for a deterministic pipeline operating correctly.

**Verification Method:**
1. Automated: `ScoringFlushOp` maintains an `emitted_count` atomic counter; `ResultSink` maintains a `written_count` atomic counter. At termination, the harness asserts `emitted_count == written_count` and aborts with a non-zero exit code if they differ.
2. Regression: A dedicated test runs the same seed/architecture three times and compares the output CSV row counts — all three must be identical.
3. Gatekeeper: Row-count verification is included in the contract-level verification scripts.

**Failure Impact:** Any mismatch means the experimental results from that run are unreliable — some events were silently dropped, and any metrics computed from the truncated output will be biased in an unknown direction. The specific seed/architecture combination must be re-run, and any analysis that consumed its output must be recomputed.

---

## INV-002: Oracle Out-of-Fold Scoring Integrity

**Description:** The oracle scoring model is never evaluated on any event from its own training fold. The oracle pipeline uses k-fold cross-validation (k≥5). For each fold, a logistic regression model is trained on the remaining k−1 folds and produces predictions only for the held-out fold. A committed fold-assignment manifest (`fold_assignments.csv`) maps every scored event to its fold number, proving 100% coverage with zero train/test overlap.

**Reason:** The prior implementation trained on an 80/20 split but scored against 100% of events — including its own training data. This inflates the oracle's apparent accuracy (the model "knows" its training events perfectly) and compresses the Feature Regret metric artificially. This is a textbook train/test contamination error (Constitution C16: Data Leakage Is A Stop Condition).

**Verification Method:**
1. Automated: The oracle training script produces `fold_assignments.csv` alongside `oracle_scores.csv`. A verification script checks that (a) every `seq` in `oracle_scores.csv` appears in `fold_assignments.csv`, (b) for each fold's model, no scored event's `seq` appears in that model's training set, and (c) coverage is 100% (no event is unscored).
2. Hash: `fold_assignments.csv` is included in the frozen-file manifest after the oracle pipeline is finalized.

**Failure Impact:** If the oracle is contaminated, every Feature Regret number in the paper is invalid — the baseline against which the contribution is measured is itself biased. This is a paper-rejection-level error.

---

## INV-003: Reproducible Build from Fresh Clone

**Description:** A single pinned `requirements.txt` allows a genuinely fresh clone → fresh venv → `pip install -r requirements.txt` → CMake build → full test suite pass with no manual intervention, no undocumented `pip install` commands, and no missing-import errors.

**Reason:** The prior implementation had no `requirements.txt`. A fresh venv install failed on `numpy` (not listed) and separately on `arch` (a specialized time-series library). This meant the project was not reproducibly buildable — a direct violation of Constitution C27 (Reproducibility Before Convenience).

**Verification Method:**
1. Automated: A CI-style script creates a fresh venv, installs from `requirements.txt`, runs `cmake --build`, and executes the full test suite. Any non-zero exit code is a failure.
2. Contract: The `requirements.txt` is a Frozen File after initial creation — changes require a decision-log entry.

**Failure Impact:** If the build is not reproducible, no reviewer or future researcher can verify the results, and the paper's reproducibility claim is false.

---

## INV-004: Structural Baseline Parity

**Description:** All architecture variants share identical: (a) replay file, (b) random seed, (c) model weights (identical `oracle_weights.json`), (d) worker topology (same number of workers, same pinning), (e) queue capacities (same SPSC/MPMC buffer sizes), and (f) scoring cost model (same `delay_per_item_us`). The ONLY permitted variation between architectures is the window-operator class and `BackpressureSignal` null-ness.

**Reason:** The prior implementation assumed but never structurally verified that all architectures were configured identically. If any parameter differed silently — e.g., one architecture accidentally using a different queue capacity or different model weights — the controlled-experiment property would be violated, and all comparative results would be confounded.

**Verification Method:**
1. Automated: The harness logs its full configuration (replay path, seed, model path, queue sizes, worker count, delay_per_item_us, architecture name) at startup. A post-hoc verification script reads all per-seed configuration logs across architectures and asserts that every field except `arch` and `backpressure_signal` is identical.
2. Structural: The harness code is structured so that all shared parameters are set in one place (a `RunConfig` struct) and the only conditional branch is the window-operator instantiation.

**Failure Impact:** If architectures differ in any parameter besides the window operator, the entire experimental comparison is invalid — observed differences could be caused by the confounding parameter, not by the window strategy.

---

## INV-005: No Ambiguous Duplicate Files

**Description:** No two files with overlapping apparent purpose may coexist in the repository without either (a) being proven byte-identical and deduplicated (one removed), or (b) being explicitly named to encode what differs between them (e.g., `replay_taobao_10k_seed42.csv` vs `replay_taobao_10k_seed99.csv`).

**Reason:** During the prior project's cleanup pass, files with overlapping names were discovered: `replay_taobao_10k.csv` vs `replay_taobao_10k_real.csv`, and `oracle_scores.csv` vs `oracle_scores_real.csv`. In one case the files were byte-identical; in the other they differed. The ambiguity made it impossible to determine which file was actually fed to which experiment run — a provenance failure.

**Verification Method:**
1. Automated: Gatekeeper scans `data/` and `results/` for file-name pairs that differ only by a suffix (e.g., `_real`, `_backup`, `_old`, `_v2`) and flags them.
2. Manual: Code review at chunk boundaries checks for file-name collisions.

**Failure Impact:** Ambiguous files mean the provenance chain from "this number in the paper" → "this specific file on disk" → "this specific command that produced it" is broken. Every result whose input file is ambiguous is unreliable.

---

## INV-006: Number Provenance (No Cross-Experiment Mixing)

**Description:** Every number in any report or paper table traces to one named, checksummed results directory and the exact command that produced it. Numbers from different experiments (e.g., stress runs vs MaxRate runs vs ablation runs) are never mixed into the same table without explicit, labeled provenance for each.

**Reason:** In the prior project, a Feature Regret value from a stress-experiment run was silently transcribed into the MaxRate results table — a different experiment's number appearing as if it belonged to the primary results. This was a bookkeeping error, not a pipeline bug, but its effect was identical: a published number that did not match its claimed source.

**Verification Method:**
1. Automated: The analysis pipeline's output includes a provenance header in every generated table, listing the exact `results/runs/<run_name>/` directory and the `compute_metrics.py` command used.
2. Manual: Paper table entries include footnotes or captions referencing the source results directory.

**Failure Impact:** A paper with mislabeled numbers will either be caught by a reviewer (rejection) or not caught (scientific misconduct, even if unintentional).

---

## INV-007: No Stub/Default Returns in Analysis Functions

**Description:** No analysis function may return a stub, placeholder, or default value (e.g., `0.0`, `NaN`, an empty list) silently. If a function cannot compute a real value (due to missing data, division by zero, or any other reason), it must raise an explicit exception with a descriptive message, never return a value that could be mistaken for a genuine result.

**Reason:** In the prior project, a per-seed Feature Regret computation function silently returned `0.0` for every seed and every architecture instead of computing a real value. This stub was not marked as such — it was presented as genuine output in a report. The error was only caught during manual auditing, not by any automated check.

**Verification Method:**
1. Automated: Gatekeeper's `check_no_stub_placeholder_returns()` scans all Python files in `source/` for patterns like `return 0.0  #`, `return 0  #`, `pass  # stub`, `NotImplementedError`.
2. Unit test: A dedicated test calls each analysis function with known inputs and verifies the output matches an independently computed expected value.

**Failure Impact:** A stub return that reaches a report means the report contains fabricated data (Constitution C01: Never Fabricate) — even though the fabrication was unintentional, the effect on readers and reviewers is the same.

---

## INV-008: Verdict-Evidence Adjacency

**Description:** Every stated Verdict (PASS/FAIL/CONDITIONAL) in any generated report must have a quoted, adjacent block of raw evidence (command output, file diff, log excerpt) directly above it in the same document, within 15 lines, that a reader can point to as the specific justification for that verdict.

**Reason:** In two independent audit passes on the prior project, report sections presented Verdicts that were either directly contradicted by adjacent evidence or had no adjacent evidence at all. Root cause in the first pass: verdicts were assembled from a pre-written lookup structure independent of live command execution. Root cause in the second pass: fabricated checklist items were silently substituted for real ones.

**Verification Method:**
1. Automated: Gatekeeper's `check_verdict_evidence_adjacency()` scans all report files for Verdict lines and checks for evidence-referencing text within the 15 lines preceding each verdict.
2. This is Dynamic Rule D-001 encoded as enforcement.

**Failure Impact:** A verdict with no adjacent evidence is unfalsifiable by inspection — it can silently diverge from reality with no visible warning sign.

---

## INV-009: Anomalous Result Investigation

**Description:** Any result that moves sharply in an unexpected direction — e.g., a baseline's absolute accuracy exceeding the oracle's, or a metric shifting by more than 50% of its prior point estimate when only minor methodology changes were made — must be investigated with a stated hypothesis and a direct test of that hypothesis before being accepted into any report.

**Reason:** The RALF-surrogate baseline's absolute AUROC exceeded the oracle's in some configurations in the prior project — a result that should be impossible by construction (the oracle uses maximally fresh features). This was accepted without investigation until flagged during auditing. The root cause turned out to be a coverage difference (RALF processed fewer events), not a genuine accuracy advantage — but the failure to investigate it promptly allowed it to persist in reports.

**Verification Method:**
1. Manual: Code review at chunk boundaries. The analysis pipeline flags any architecture whose absolute AUROC exceeds the oracle's as "ANOMALOUS — requires investigation" rather than silently including it in summary tables.
2. Contract: Investigation reports for anomalous results are required deliverables, not optional.

**Failure Impact:** An uninvestigated anomalous result in a published paper will be caught by a reviewer and treated as evidence of either incompetence or dishonesty — even if the underlying cause is benign.

---

## INV-010: Golden Parity Test

**Description:** A golden parity test independently verifies that online (C++) feature computation matches an offline (Python) recomputation of the same formulas. Specifically: given an identical input event stream and identical initial state, the Python implementation of `KeyedFeatureExtractOp`'s EMA update, engagement weighting, and feature vector assembly must produce feature vectors that match the C++ output within floating-point tolerance (≤1e-6 relative error per component). This test must pass before any accuracy metric derived from those features is trusted.

**Reason:** The build prompt specified that this test should exist as a named component of the test architecture. It was never actually built in the prior project. Without it, there is no independent verification that the C++ feature computation — which is the foundation of every downstream metric — is correct.

**Verification Method:**
1. Automated: A test script (`tests/test_golden_parity.py` or equivalent) runs the C++ pipeline on a small deterministic input, captures the feature vectors from the output CSV, runs the Python reimplementation on the same input, and asserts per-component relative error ≤ 1e-6.
2. Contract: This test is a required deliverable in Chunk 07 (Test Suite & Golden Parity Verification).

**Failure Impact:** If C++ and Python feature computations diverge, every metric computed by the Python analysis pipeline from C++ output is measuring something different from what the paper claims — the features the model was scored on are not the features the analysis thinks they are.

---

## INV-011: Baseline Tuning Symmetry

**Description:** Any baseline comparison receives sensitivity analysis effort equivalent to what the primary contribution receives. Specifically: if the primary contribution (Adaptive) is evaluated across a grid of configurations (e.g., different AIMD parameters, different delay settings), then each baseline must also be evaluated across its own analogous configuration grid before comparative claims are made. An untuned single-configuration baseline compared against a swept contribution is not accepted as a valid comparison.

**Reason:** The RALF-surrogate baseline in the prior project was run in a single, un-tuned configuration and compared against the primary contribution, which had been swept across multiple configurations. This systematically disadvantages the baseline — if the baseline's single configuration happened to be suboptimal, the comparison overstates the contribution's advantage.

**Verification Method:**
1. Manual: Code review at the experimental-run chunk boundary. The experiment design document must specify the configuration grid for each architecture, and the grids must be comparable in scope.
2. Automated: The analysis pipeline reports the number of configurations tested per architecture alongside comparative results.

**Failure Impact:** A reviewer who notices tuning asymmetry will (correctly) reject the paper's comparative claims as methodologically unsound, regardless of how large the measured advantage is.
