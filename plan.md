# AMOS / BPFeat: forensic findings and a submission-readiness execution plan

**Audit started: 30 September 2026; handoff completed: 1 October 2026 (Asia/Kathmandu). Current state: corrected engine foundation, no admitted research results, no validated publication claim.** This document is the handoff for an Architect and an Implementor who have access only to this new folder. It is deliberately more demanding than reproducing the old plots. The objective is a coherent, independently checkable research system whose conclusions may be positive, negative, mixed or inconclusive. No performance target in this plan is permission to manufacture observations.

The supplied software factory was v3.3.0. The active local integrity patch is **3.3.1-amos.1**; its changes, compatibility limits and same-session repair contract are recorded in `factory/CHANGELOG.md` and `docs/audit/reaudit_2026_10_01/`. The original baseline remains recoverable in history and its original test log is preserved. This plan maps research work to the factory's actual capabilities and specifies the remaining reviewed adapters required before scientific release. A factory PASS is a bounded integrity check, not proof of acquisition authenticity, causal identification, novelty or publication readiness.

## 0. Current re-audit amendment: read before using the original findings

**1 October 2026: the migrated tree had additional defects and has now been repaired within a bounded software scope. It cannot be certified as free of all mathematical, methodological or implementation errors.** The supplied `BPfeat.md` is preserved exactly in `docs/research/BPfeat_deep_research_supplied.md`; its advice is critically reviewed in `docs/research/deep_research_review.md`. Treat it as an untrusted research lead. Its unresolved citation numbers, dataset permission assumptions, example margins and proposed outcomes never become project authority or evidence.

The full new findings R01–R20, counterexamples, same-session repair contract and actual validation logs are in `docs/audit/reaudit_2026_10_01/`. They supplement F01–F56 rather than rehabilitate legacy evidence. The original migration manifest and original 18/276-test logs remain historical snapshots; their hashes do not identify current changed files. Use the current file inventory and validation manifest for this repair. The current source is a tested foundation, with no admitted dataset, trained research model, prospective experiment or confirmed hypothesis.

### 0.1 Mathematical and integrity repairs that affect future agents

The factory's exact paired sign-flip calculation used an absolute `1e-14` tail allowance. Five identical positive differences gave p=.0625 at ordinary scale and p=1 at `1e-16`. This was a real unit-dependent mathematical error. The repaired tail comparisons use exact integers representing the actual finite binary floats. Opposite-sign extreme quantile interpolation no longer overflows a finite midpoint; overflowing paired differences and invalid settings fail. Exact rational enumeration, tiny/large rescalings, pairwise AUROC and independently grouped average precision check the repaired operators. These algorithms still cannot prove sign-exchangeability, independence, bootstrap coverage or power for the proposed study.

The EMA reference now rejects an unrepresentable infinite variance-equivalent span and preserves generator gain histories for exact weights. The label reference rejects globally reversed cross-key time, blank/padded identities and invalid domains. It assumes an already admitted canonically ordered cohort and complete declared capture coverage. Do not infer coverage from a user's last action, an outlier maximum time or future activity. Unknown outcomes remain unknown. The reference deliberately retains censored positives as unknown under its complete-window cohort convention so outcome availability does not silently change the denominator.

Native diagnostics now preserve item/category/behavior, coherent pressure sample/load times, batch controller observations and actual target/count/tail identities. Receipt v3 records actual configuration/model coefficients, not learned provenance. Success is published after both output closes and a pending-receipt close; failure retains partial artifacts and phase/error diagnostics when possible. Invalid queue configuration is rejected before creating the attempt. Numeric parsing/formatting use full-token finite decimal/classic-locale rules. `tools/verify_engine_diagnostics.py` independently replays these records against explicit inputs and refuses mismatched membership, identities, clock envelopes, gain histories, arithmetic and counters. Its result is `DIAGNOSTIC_REPLAY_PASSED`, with `research_evidence=false`. It is an in-memory small-cohort reference, not a production evaluator or evidence-admission runner.

The native receipt still does not bind authoritative executed input/model/binary bytes or enforce a hard process deadline. Hashing supplied files after a run does not close that gap. Emitted pressure can be arithmetically replayed without proving the queue sensor observed truth. The timing interval begins after input parsing and ends at scoring, excluding completed write/client response. No publication/query service or hardware measurement was added by this repair. Those limitations remain real contract dependencies.

The local factory patch corrects false CPU/memory fields to unknown, validates actual signed receipt bindings on the audit path, caps assurance at structural validation, creates a framed full-hash binary Merkle snapshot and indexes attempts to catch missing folders/nonces. It verifies supported worker-runtime identity and rejects unsupported controls. Hardware arithmetic now separates training from inference energy and names service-time rates precisely. Standalone verification supports real nested receipts. Plausibility no longer fabricates universal F1/accuracy chance values or treats `NOT_SUPPORTED` as a positive verdict; typed p/CI/counts and unresolved investigations fail appropriately. The complete runner now includes five previously omitted function fixtures. Details and interface/version consequences are in the local changelog.

Signing, snapshots and an attempt index provide cooperative local integrity. Same-user workers can access keys/state; a network-disabled declaration is not OS isolation. HMAC verification bytes are secret even if named `.pub`; do not release them as a public key. A review file's existence does not establish reviewer independence. Native/streaming adapters and independent scholarly review remain unimplemented. Existing v3 plan declarations are accepted, but earlier snapshot roots require their original versioned verifier or a new epoch; never rewrite old receipts to fit the repaired algorithm.

### 0.2 Corrections to the supplied research assessment

The assessment's proposed elapsed-time update `alpha*x + (1-alpha**delta)*previous` is not normalized: alpha=.5, delta=2 and constant input/state 1 yield 1.25. A candidate elapsed-time smoother instead uses `rho=exp(-delta/tau)` and `rho*previous+(1-rho)*x`, with compatible units, initialization and an explicit sampling/hold model. Another intended quantity, such as decaying event intensity, needs its own definition. Do not silently change current event-count features to rescue an interpretation.

Constant-gain mean age is `(1-alpha)/alpha` in updates, not seconds; variance-equivalent span is `(2-alpha)/alpha=2*mean_age+1` under independent equal-variance stationary noise. Publication timing, event timing and whether observations are skipped affect physical-time behavior. A prescribed gain history is linear time-varying; input/state-dependent feedback can make the complete system nonlinear. Different external trajectories alone do not prove failure of superposition for the same fixed operator. The current MIMD law already has distinct low/high thresholds; this is hysteresis, not a stability proof. TCP AIMD results do not automatically apply to a CPU service queue.

Post-event features are lawful for a strict-future target excluding all purchases at t. A pre-event/contemporaneous task is a separate contract. Splitting only on event timestamps fails to purge label windows; causal warm evaluation may use earlier observed unlabeled test history. A user's last event is not proof observation ended; requiring later activity may select users using the future. Preserve actual task prevalence rather than forcing a balanced evaluation cohort. No universal <1% positive-rate claim follows from ULB's fraud prevalence.

Share the offered query schedule and account for every method's losses. Do not copy adaptive dropped queries to the baseline or evaluate only a favorable returned intersection. Freeze resource envelopes before test observations; do not post-hoc throttle controls to match an adaptive method's measured use. Equal nominal optimizer steps do not establish adequate convergence. Future-label scores are trivial label access, not an attainable causal oracle. Per-user/day AUC can be undefined and shared horizons cause dependence. A point gap below an example 1% margin does not establish equivalence. An AUROC>.5 advancement rule would suppress valid weak/harmful results. Seeds need genuine stochastic roles; a <2-hour run limit is a resource design choice requiring measurement, not a scientific gate.

The primary RALF paper is about streaming feature-maintenance scheduling using downstream prediction error, not a static cache without feedback. Its simplified error-feedback availability must not become instantaneous two-hour future labels in AMOS. Clipper establishes adaptive batching prior work; its benchmark maxima do not guarantee an AMOS gain or SLO. ADWIN's cited paper is SDM 2007. Biathlon's approximation work does not justify treating a coefficient change in an O(1) EMA as saved aggregation work. Primary links and checked-source limitations are in the review and Section 14. No dataset license or venue suitability is inferred from the report.

### 0.3 Current acceptance and what remains blocked

Native CTest passed 2/2 groups in Debug, Release, ASan/UBSan and ThreadSanitizer configurations. Release-bound Python passed 27 tests without skips. The complete local factory passed 307 tests, including independent numeric references and actual execution-path mutations. CTest's Python group overlaps the 27 checks; these counts are not independent experiments. Failed repair attempts remain logged. Release uses explicit native checks rather than removable assertions. No sanitizer/test log is a performance study or a research certificate.

Read the sequential contracts in Section 13. AMOS-01–05 still require scope, authentic acquisition/terms, production lineage, causal task/splits and trained/calibrated policy-bound models. AMOS-06–12 still require a genuine work mechanism, query/publication and load contracts, fair baselines, independent streaming analysis, supervised native receipts, reviewed adapters and actual hardware instruments. AMOS-13–18 require a real prospective protocol, complete trials, scoped negative/positive/inconclusive analysis, reproduction and final scholarly review. The current empty `project/research_plan.json` remains unfrozen. Software correctness does not authorize filling any of these missing scientific fields.

## 1. Decisions that govern all subsequent work

1. Retire all legacy results, figures, fitted weights, "oracle" score files and historical PASS reports as evidence for the new study. Preserve them in history and in the audit inventory; do not salvage numerical claims by rewriting the explanation around them.
2. Preserve candidate raw bytes locally, under quarantine. Admit them only after source, terms, schema, time-domain and lineage checks. Matching a local hash is necessary for identity and insufficient for authenticity.
3. Use the corrected engine in `source/` as a tested foundation. It currently computes features and scores **every accepted event**. It has no publication cache or separate query stream. Its batch size is not a feature publication interval.
4. Resolve the scientific object before developing more controllers: either study the actual batching pipeline under its correct name, or implement and evaluate a genuine feature publication/query system. The latter is the recommended main research direction, conditional on a demonstrable work-saving mechanism and meaningful workloads.
5. Never silently reverse an actuator, change the loss, invent entities, relabel a baseline, select favorable seeds, lower a quality floor or move a test split to rescue the hypothesis. Amend a prospective protocol visibly; previously inspected outcomes remain exploratory.
6. Distinguish a valid negative result from an invalid experiment. Incorrect identities, leaked targets or fabricated measurements cannot support a negative result either. A well-powered null estimate can be informative; a wide interval establishes uncertainty.
7. Keep all research computations reproducible from admitted sources, a frozen protocol and actual execution receipts. Every manuscript number must lead to a metric artifact, prediction/query identities, model/training scope, source lineage and a recorded attempt.
8. This plan does not promise acceptance at any venue. The current novelty and external validity are unresolved. Select a venue after the contribution is established, not by importing the legacy deadline or by declaring the system "elite-venue ready."

## 2. What was inspected, and what the inspection establishes

The legacy tree contained **1,325 regular files, totaling 13,248,276,431 bytes**, excluding Git internals. Every regular file in that inventory was hashed in full. A replay-score symlink was recorded as a symlink rather than followed as an independent data source. Counts include generated build products and caches: 50 files under `source/`, 30 under `tests/`, 321 under `project/`, 658 under `results/`, nine under `data/`, and 23 under the old `factory/`. These are inventory categories, not counts of independently validated studies.

The audit combined full byte inventory, bounded CSV inspection, full text pattern indexing, manual semantic examination of the research-critical C++/Python paths and governance documents, complete streamed raw/replay profiles, complete historical result CSV profiles, clean legacy builds/tests, and targeted counterexamples. It did **not** establish provider authenticity, inspect every historical row by hand, reproduce the old scientific experiments, authenticate purported human reviews, formally verify concurrent code, or validate every possible mathematical property. Full file coverage and semantic proof are different things. Future agents must preserve this distinction.

| Artifact in this folder | Scope and limitation |
|---|---|
| `docs/audit/legacy/inventory.json` | Full-file hashes, sizes, physical line counts and schema inspection. Source sample values removed from the public inventory. |
| `docs/audit/legacy/summary.json` | Coverage counts, sizes and explicit exclusions. |
| `docs/audit/legacy/content_index.json` | Whole-text pattern triage for readable bounded-size files, including historical governance. Pattern matches are pointers, not verdicts. |
| `docs/audit/legacy/file_disposition.csv` | One disposition for every inventoried path. It records exclusion/reference/replacement decisions, not a claim that every line received a formal proof. |
| `docs/audit/legacy/data_profiles.json` | Every row of both raw candidates and all three legacy replay CSVs streamed for the stated checks. |
| `docs/audit/legacy/result_profiles.json` | All 641 historical result CSVs, 125,902,365 logical rows, checked for numeric/schema issues and duplicate sequence IDs. |
| `docs/audit/legacy_probe_results.json` | Reproduced software counterexamples and a missing-binary orchestration probe. Fixtures are not research results. |
| `docs/audit/probes/legacy_engine_probe.cpp` | Native counterexample source. Requires the legacy headers to rerun; it is not active engine code. |
| `docs/audit/legacy_cpp_tests.log` | Clean legacy C++ test run: 20 tests passed despite the counterexamples. |
| `docs/audit/legacy_python_tests.log` | Legacy Python tests: 16 passed. Several validate fixtures/status structure rather than execution truth. |
| `docs/audit/factory_self_tests.log` | Supplied v3.3 factory: 276 tests passed after allowing its local Unix-socket tests in the execution environment. |
| `docs/audit/engine_*` | Corrected engine Debug/Release, address/undefined-behavior and ThreadSanitizer checks. Passing tests do not make it a complete research system. |
| `docs/audit/environment.json` | Actual audit OS/compiler/Python observations, package versions and separately identified user-supplied machine specification. |

The result scan found 23 header-only CSVs, 23 CSVs with duplicated `seq` values, and 141 with nonnumeric/nonfinite cells. Interpret the last count carefully: 138 are controller-summary files containing `N/A` for inapplicable fields, which is not itself fabrication. Other missing/corrupt values and undefined aggregate metrics need their own accounting. There are 214 score-bearing CSVs. All are archival; the scan does not authenticate their source linkage or execution provenance. The machine-readable file-level report allows a reviewer to inspect each case without relying on an aggregate alarm count.

The raw Taobao candidate has 100,150,807 rows, 987,994 observed users, 89,715,946 `pv`, 2,888,258 `fav`, 2,015,839 `buy`, and 5,530,446 `cart` records. The profile flags 318 invalid-domain rows under its stated nonnegative-integer/domain checks. Observed nonnegative timestamps range from 259 to 2,122,867,355 seconds, so matching the familiar row count does not mean all records lie in the intended observation period. The largest category ID is 5,162,429. The invalid records and time outliers require explicit admission decisions with row identities and reasons; do not quietly clean them away.

The raw ULB candidate has 284,807 rows, with 284,315 class-zero and 492 class-one labels and no nonfinite numeric cells under the profile. That establishes a local numeric profile, not permission to redistribute the data or proof of download origin. The existing ULB replay assigns all rows to one key; the raw data does not supply cardholder identity, so fabricating many keys would be worse than acknowledging this limitation.

The legacy Taobao replay has 980,885 rows and 9,711 users. It has 9,710 global timestamp regressions, no detected per-key timestamp regressions, and 976,984 category values above 65,535. Its sequence is globally increasing only because it was assigned after a user-major reorder. There are 863,704 labeled negatives, 117,170 labeled positives and only 11 invalid labels. Those target counts are not accepted: label construction and censoring are defective. The causal-demo replay has 36,000 rows and 100 keys and is synthetic. The ULB replay has 284,807 rows and one key. Neither becomes representative evidence merely by being reproducible.

The supplied new-folder documents `docs/FORENSIC_AUDIT.md`, `docs/v26_forensic_results.json` and `docs/audit_tools/audit_v26_project.py` concern a **different v2.6 factory example**. They were supplied with v3.3 and retained as factory material. Their 50-run counts and metric findings must never be attributed to AMOS. AMOS audit evidence lives under `docs/audit/legacy/`.

## 3. Preservation, migration and repository boundaries

The old published main commit observed during the audit was `37c85a6ba1905eb5029d24bd9dba26f928c8f06b`. The legacy working tree differed substantially from that commit, including untracked rehabilitation code and governance. A tag of published HEAD alone would therefore omit relevant work. Preserve two annotated legacy references: a published-head tag and a code/governance workspace snapshot tag. The workspace snapshot excludes raw datasets, bulk results, caches and builds; full byte identity of those excluded files remains in the inventory and their local originals remain in the old folder.

The main branch should contain the supplied new factory, this plan, corrected engine, tests, audit reports and current planning metadata. Replace its old tracked contents by an ordinary descendant commit; preserve history and tags. Do not force-push, delete tags, erase the old local directory or remove candidate raw bytes. "Clear legacy" means retire its contents from the active main tree, with recovery references retained. Record the actual tag names, commit IDs and remote verification in `docs/audit/git_migration.json` after execution.

The Git repository is `https://github.com/AdiShrestha/Project-AMOS`. Raw candidates are local ignored files under `data/quarantine/raw/`; public manifests are in `project/candidate_data.json`. Their two local SHA-256 values are:

```text
UserBehavior.csv
46fdd7d389c1ddc7922eb7d9014af5573a4a3075da28c6c46197636873d8f1a9
creditcard.csv
76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89
```

Keep raw/derived bulk data, run outputs, private signing keys, local factory state, compiled binaries and caches out of ordinary Git commits. Keep the factory specifications and source, project methodology, plan, test code, small manifests and audit reports tracked so future agents have the governing context. The legacy repository policy that forbids tracking `factory/` and `project/` is incompatible with this handoff and is not migrated. The existing proprietary root license is retained, not silently changed. It currently restricts third-party execution/reuse; artifact availability may require a separately authorized license or evaluation permission. Dataset terms are a separate question.

A future session with only the new folder has enough code and evidence to continue. It does not need the old runtime as a dependency. Historical sources can be inspected through the preserved workspace tag. Candidate raw files are present locally but absent from a Git clone; a clone requires documented acquisition after terms review. No model or research-ready replay is bundled.

## 4. Findings: evidence, consequence and disposition

Priority P0 blocks scientific evidence; P1 blocks defensible evaluation or important implementation claims; P2 affects reproducibility, interpretation or scope. "Replaced" means the defective path is excluded and a smaller corrected path now exists. It does not mean the full old system was repaired. References below are **legacy repository paths**, available in the archive tag; current replacement paths are identified separately.

### 4.1 Fabrication and evidence provenance

**F01 — P0, executed probe: orchestration fabricates successful runs.** `scripts/orchestrator.py:111` writes three literal predictions, including score .45, latency 150 and a fixed timestamp. The configured binary is never executed. The probe supplied a nonexistent binary and still received `COMPLETED`. Lines around 137 and 154 write Apple M1 Max/compiler/OS/commit metadata and a 25 ms wall time as constants. This cannot support performance, completion, provenance or predictive accuracy. **Disposition:** excluded. Replace with real subprocess execution, exit/signal/timeout handling, complete stdout/stderr preservation, input/model/binary hashes and supervisor-bound attempt IDs in AMOS-10/11. A schema-valid manifest generated by this file is invalid evidence.

**F02 — P0, source-confirmed risk: synthetic generation can overwrite a real-named replay.** `source/analysis/generate_synthetic.py` draws unseeded values, explicitly adds strong label signal, and writes the Taobao replay filename. This proves a dangerous generator exists; it does not prove that the current raw Taobao file was fabricated. Hashes, counts and the large real-domain categories point to distinct local bytes, but acquisition remains unresolved. **Disposition:** generator and all legacy derived replays excluded. Future simulations require distinct paths, declared seeds, distributions, identities, labels, limitations and a visible simulation-only evidence role.

**F03 — P0, source-confirmed: figures and summaries contain literal results.** `source/analysis/fig2.py:12` embeds feature-regret estimates and intervals; its title embeds oracle AUROC .6557. `collect_all_results.py:42,73,167` and surrounding lines print fixed oracle, correlation and fairness conclusions. Some text prints `fairness_gap` under a Jain label. A graph cannot become evidence because it visually resembles an expected result. **Disposition:** not migrated. New figures must read verified analysis artifacts, validate units/cohort/method identities and emit a number-to-source manifest. Changing the inputs must change the figure or fail validation.

**F04 — P0, source/governance-confirmed: historical approvals conflict and do not establish acquisition.** The chunk04 acquisition documents contain ADMITTED-style decisions and text claiming human approval, while chunk05 reports remain blocked on human checks and include empty records/measurement lists. Agent-authored descriptions of a human decision are not independent evidence of that decision. Local bytes matching a manifest do not prove the provider supplied them. **Disposition:** candidate status is UNVERIFIED/BLOCKED; no legacy approval carried forward. Preserve discrepancies in the audit index and obtain actual provider terms/acquisition records under AMOS-02.

**F05 — P0: no reliable chain links historical outputs to immutable attempts.** Historical CSVs and summaries lack a complete, uniformly bound chain of frozen protocol, binary, input/model hashes, actual command/environment and terminal accounting. The result scan identifies duplicate IDs and missing values in some files. File names such as `corrected`, `primary` or `5seed` do not repair this chain. **Disposition:** all results archival, including apparently plausible ones. No post-hoc receipt creation is allowed.

**F06 — P1: resume and output collision rules are inadequate.** The old orchestrator's completion check does not bind all relevant configuration/input/binary/environment state; output reuse and repeated runs can collide. The harness sweep writes architecture/seed names that can overwrite several parameter settings. **Disposition:** current CLI refuses an existing output directory; full attempt state machine remains AMOS-10. Resume is permitted only for verified identical completed attempts or explicit continuation protocols, never by discovering a same-named CSV.

### 4.2 Data, causality, targets and model training

**F07 — P0: purchase labels include the event being predicted.** `source/preprocessing/preprocess_taobao.py:57–85` tests for a buy in an inclusive interval starting at the current timestamp. The feature extractor already includes the current behavior and purchase counts. The probe reproduces a current buy labeled positive. For a future-purchase task, this is target leakage. **Disposition:** replaced by a strict-future reference `(t,t+H]` in `source/preprocessing/labels.py`, including same-time exclusions and witnesses. Production label generation and scientific horizon remain AMOS-03/04. A contemporaneous task would instead require pre-event features and a different protocol.

**F08 — P0: global order is destroyed after initially sorting by time.** The same preprocessing script sorts by `(user_id,timestamp)` inside `compute_labels`, then assigns `seq` without restoring global order. Complete replay scanning confirms 9,710 regressions. This changes offered load, feedback dynamics and any interpretation of event-time phases. **Disposition:** current engine rejects regressing global timestamps. Produce a stable global `(event_time,source_id)` order only after preserving label alignment and lineage; never repair labels by arbitrary positional reassignment.

**F09 — P0: censoring and observation horizon require reconstruction.** Using the maximum timestamp of a sampled/corrupt corpus as observation end can declare a near-tail negative valid because an unrelated outlier extends the maximum. Global end also needs a documented assumption about individual observation coverage. Only 11 invalid targets in the old sampled replay are an audit clue, not proof that almost every row has full two-hour follow-up. **Disposition:** censored targets are unknown, not zero; the new reference emits `label=None`. Production admission must establish the observation calendar and per-source/entity follow-up assumptions before labeling.

**F10 — P1: burst binning ignores its stated duration.** `preprocess_taobao.py:41–52` accepts `window_minutes` but bins in single minutes. The probe confirms changing that argument does not change the tagging. Median density excludes absent bins; burst thresholds derived from the evaluation trace can also define outcome-conditioned stress settings. **Disposition:** excluded. Define a complete fixed-bin calendar, include zero bins, separate descriptive workload characterization from a prospective exogenous load schedule, and never feed evaluation-only burst labels into the controller.

**F11 — P1: sampling granularity and memory behavior differ from the advertised dataset.** The 100-bucket user sampler cannot choose an arbitrary exact small cohort and selected 9,711 rather than 10,000 users. Loading the 100-million-row CSV into pandas at once creates several large representations on a 16 GB machine. **Disposition:** no old replay admitted. Use bounded streaming/two-pass stable hash ranking or a declared sampling threshold; record the actual selected count, inclusion rule, seed and source-ID set. Fit resource envelopes empirically.

**F12 — P0: real category domains exceed the C++ representation.** Legacy `behavior_source.hpp` and event structures use 16-bit category IDs. Strict parsing rejects most real rows; older cast-based paths could narrow them. Full scanning reports 976,984 affected replay rows. **Disposition:** corrected `RawEvent` uses uint64 identities/categories and tests a category value in the millions. Source identity and feature schema now differ from the old version; never reuse its model by assuming binary compatibility.

**F13 — P0/P1: ULB feature semantics differ between Python and C++.** Python's ULB feature construction counts positive amount in a purchase-like feature; the C++ behavior-zero path increments view counts. The seven-vector interpretation therefore differs across training and runtime. All transactions share a fabricated placeholder key in the old replay, and original V1–V28 variables are discarded. **Disposition:** ULB execution/model files are excluded from the corrected Taobao engine. ULB can be a separately defined tabular-model workload, not evidence of keyed-user fairness. Add a distinct adapter/schema with exact differential tests if retained.

**F14 — P0: normalization and artificial time metadata leak or misrepresent scope.** Legacy ULB max-amount normalization uses the entire corpus rather than the training scope. The replay introduces an arbitrary absolute time origin, although source `Time` is elapsed time. **Disposition:** fit transforms on training only; store their coefficients, scope and hash. Preserve relative time as relative, record any replay origin as a workload mapping, and never present it as acquisition time.

**F15 — P0: random row splits are unsuitable for this forecasting estimand.** `train_classifier.py:158,214` performs stratified random row splits on overlapping per-key histories and future windows. Shared entities, nearby outcomes and future horizons invalidate ordinary independent-held-out forecasting interpretation. **Disposition:** no legacy weights/reference scores transferred. Choose a purged temporal warm-start protocol and a distinct cold-entity test, or another explicitly justified design. Record feature and label dependencies separately; see Section 7.

**F16 — P0: hyperparameter selection and final evaluation scopes overlap.** The alpha grid search partitions the same full corpus differently from the final split. Rows inspected for alpha validation can later enter final test, while precomputed feature trajectories traverse the full history. **Disposition:** define outer untouched test blocks before all selection. Training, calibration, controller selection and validation share no test outcome access. If expanding data after a pilot, document how held-out periods were protected.

**F17 — P0/P1: reference scores include training rows and are mislabeled an oracle.** `train_classifier.py:235` predicts all rows, including training observations. A fixed selected-alpha logistic model is not a Bayes-optimal or best-feasible online oracle. Class-balanced logistic probabilities are not automatically calibrated population probabilities. Negative online-minus-reference loss is possible without a contradiction. **Disposition:** rename the estimand `reference_loss_gap`; use untouched out-of-sample paired scores and calibrated probability models for proper losses. Keep a declared matched-model reference distinct from stronger policy-specific retrained models and diagnostic hindsight upper bounds.

**F18 — P1: some algebra is valid, but provenance is absent.** Folding a fitted StandardScaler into linear logistic weights is mathematically valid when `w_raw=w_scaled/scale` and `b_raw=b_scaled−sum(w_scaled*mean/scale)`. Preserve that idea only after independently testing predictions and exact precision. It does not repair split leakage, semantic mismatch, class-weight calibration or missing convergence/training history. **Disposition:** new trainer must save transform/model artifacts and full-precision weights under AMOS-05.

**F19 — P1: fixture-only lineage can discard legitimate different events.** `preprocessing/lineage.py:56` exposes `process_fixture_rows`; its duplicate key is `(user,time,behavior)`, omitting item/category. Two different same-time actions can be treated as duplicates. Its conservation uses `assert`, which Python `-O` can remove. A populated manifest with zero hashes or empty real measurements cannot substitute for production lineage. **Disposition:** not migrated. Define raw source identities first, then separately classify exact duplicates and simultaneous distinct events, with explicit exceptions and non-assert accounting.

**F20 — P1: model-manifest checks are narrower than their name suggests.** `preprocessing/model_manifest.py` checks required keys, a small role set, dimension and weight-file digest. It does not fully bind fitting rows, task timing, feature semantics, calibration, training sufficiency or permitted deployment policies. **Disposition:** excluded from active use. Implement a strict typed model/policy manifest and independent training-scope checks; a syntactically valid weight file remains only numeric input today.

### 4.3 Runtime, controllers, accounting and mathematical meaning

**F21 — P0: batches invent source IDs.** `scoring_flush_op.hpp:149` emits `first_seq+i`. RALF selection/reordering or any input gaps break that assumption. The native probe expects second ID 30 but gets 11. Complete output profiles find duplicated IDs in 23 RALF CSVs. **Disposition:** corrected snapshots carry and emit each actual source ID. Publication/query extensions must retain independent identities and enforce one-to-one joins.

**F22 — P0/P1: retries modify scientific state before output acceptance.** `scoring_flush_op.hpp:124–149` updates the last-publish timestamp before a successful push. A blocked retry recomputes the gap as zero; the probe expects four seconds and obtains zero. Scoring delay/side effects can repeat, while batch timing may count only the final retry segment. **Disposition:** excluded. Current pipeline copies immutable snapshots through retries and writes each score once on its successful path. Future publication uses prepare/commit state transitions, counted acceptance and retry-idempotent traces.

**F23 — P1: per-item timing is replaced by batch timing.** A single last-batch creation timestamp is emitted for all scored items. Early events consequently lose their waiting time. A captured "staleness" is often the event-time gap between scored events for a key rather than age of the cached feature at a query. **Disposition:** corrected per-item creation/scoring clocks; no feature-age claim. Add the complete clock model in Section 8 before measuring end-to-end latency or publication freshness.

**F24 — P1: trace logs are missing, truncated or reconstructed.** The old `log_trace` path creates headers without substantive controller logging. Batch latency logs cap at 100,000 observations without a universal truncation/admission rule. `generate_trace.py` reconstructs some traces from result columns, which do not establish an original control-time trace. The inventory/profile finds 23 header-only controller CSVs. **Disposition:** current engine writes real nonempty batch-start observations with generations; complete trace coverage and output manifests remain required. Reconstruction must be labeled reconstruction and cannot prove hidden events.

**F25 — P1: control updates depend on idle polling.** `adaptive_feature_window_op.hpp` updates tracker/controller while the buffer is empty before a successful input pop. Repeated idle ticks therefore repeatedly change the controller. Different architectures sample pressure at different cadences. **Disposition:** corrected batching updates once per nonempty batch start; no updates on idle/retry. Research requires either a common independent clock or explicit per-event cadence and tracing, with repeated-poll invariance tests.

**F26 — P1: the law is MIMD, not AIMD, and integer growth can stall.** The legacy shrink/grow factors are multiplicative .70/1.15; calling them AIMD is inaccurate. With a lower window of eight and small growth such as 1.01, integer conversion can leave W at eight forever; reproduced by the probe. Transition counters can count attempted actions at clamps. **Disposition:** corrected validation, integer progress, actual-action/direction counters and naming. Stability, hysteresis and benefit remain hypotheses; no code comment or limit range proves them.

**F27 — P0 for the intended mechanism: W does not skip updates or scoring.** The legacy window accumulates snapshots but sends all of them to a scorer that loops over every item. Changing W changes grouping, queueing and overhead, not the number of predictions or feature updates. Smaller W can increase batch overhead. **Disposition:** current engine accurately calls it batching. Publication cadence U, scoring batch size B and EMA gain alpha must be separate in the target design. Without an actual work-changing actuator, the proposed load/accuracy tradeoff is unsupported.

**F28 — P0 for compute-saving claims: changing alpha keeps EMA work O(1).** Both gains use the same constant number of arithmetic operations. Alpha changes feature semantics and predictor input distribution, not asymptotic per-update cost. Queue-pressure/accuracy correlation is not proof of adaptive computation. **Disposition:** preserve alpha as a feature-dynamics policy only. Measure the proposed work mechanism before a confirmatory benchmark; stop or pivot if it does not exist.

**F29 — P1: full MPMC queues report zero pressure.** `core/mpmc_queue.hpp:105` wraps the producer-consumer distance modulo capacity, so a fully occupied queue reports zero; reproduced exactly. Capacity is asserted rather than robustly validated. Raw storage/object lifetime is questionable in C++17, including atomic slot construction. **Disposition:** MPMC excluded. New bounded SPSC uses constructed typed storage and runtime validation, with full occupancy one. Do not claim MPMC support; add a separately reviewed implementation only when needed.

**F30 — P1: hidden key limits silently drop events.** `keyed_feature_extract_op.hpp:163` has a 100,000-key ceiling and returns after consuming a new key without emitting a feature. Counters/ledger are not enough to reconstruct universal losses; 32-bit state counters can overflow long streams. **Disposition:** explicit configurable key budget, 64-bit counts, fail on exhaustion in the corrected engine. Future eviction requires a registered policy, attributable reset/drop events and complete query coverage, not silent deletion.

**F31 — P1: timestamp/domain edge cases are insufficiently guarded.** Zero is used as an unseen timestamp sentinel; backwards unsigned subtraction can underflow; unknown behaviors can inherit a default engagement value in helper code. **Disposition:** seen flag, integer nanosecond subtraction after monotonicity validation and strict behavior rejection in current features/replay. Same-time events and duplicates must follow the task contract, not incidental file order.

**F32 — P0: malformed or missing models can become a zero predictor.** Legacy `logistic_model.hpp` accepts incomplete files and unspecified fields can remain zero; catch-all loading paths in main/harness continue with a default model. Default text precision loses fitted coefficient accuracy. The partial-model probe succeeds with a missing weight. **Disposition:** new model requires schema/bias/all seven weights once, finite complete values, stable sigmoid and full-precision serialization. Missing models fail before a successful attempt. Provenance binding is still pending.

**F33 — P1: throttle and architecture names do not establish the implemented baseline.** In the legacy harness, fixed/throttle share execution paths; registry-based throttle does not consistently instantiate a limiter. A source callback returns true while not filling `out` when throttled. Static limiter/tracker state can bind to a first run. Backpressure-only paths alter alpha rather than demonstrated admission. Some CLI options and invalid architecture names are ignored or fall back. **Disposition:** all old baseline implementations excluded. Reimplement behavioral contracts with observable signatures: a limiter must alter admission/delay, an alpha-only baseline must hold batch/publication policy fixed, and unknown configuration must fail.

**F34 — P1: declared workers/topology differ from execution.** Registry harness registers the operations on worker zero even when several workers are declared. Extra workers do not make a parallel pipeline. The reported topology does not fully establish real edges or execution placement. On macOS, QoS is not proof of pinning to a specific P/E core. **Disposition:** current engine uses three actual threads and makes no affinity/scalability claim. Future configurable workers must produce observed topology, stage counters and verified execution signatures.

**F35 — P0/P1: empty queues are mistaken for completed processing.** Main/harness wait for source_done and repeated empty-queue observations, then stop. An operator can have pending state, a partial tail or an in-flight final output while its queue is empty. A source failure before EOF can also hang a polling loop. **Disposition:** current success requires worker join, EOF close propagation, terminal empty queues and exact read/extracted/batched/scored/written conservation. Add process kill/timeouts and phase-specific loss accounting for research workloads. A timeout is a failed attempt, never success at the last observed count.

**F36 — P1: generic lifecycle/accounting reports are not end-to-end guarantees.** Legacy ledgers can clamp in-flight counts to zero, hiding double releases; reporter reset paths lose cumulative counters; topology expectations can validate names without complete actual wiring. Some worker shutdown behavior does not match comments about which thread owns it. Passing isolated lifecycle fixtures does not show the ledger is wired into the actual experiment. **Disposition:** generic runtime is not migrated. The small corrected pipeline deliberately exposes its limited ownership model. Future runtime expansion needs integration and mutation tests against real stages.

**F37 — P1: percentile/histogram reporting can understate tail latency.** Legacy rank calculations can produce a zero-valued p99 for one nonzero sample; fixed upper bins cap large latencies. Batch-flush duration, per-event wait, service time and client response are mixed in different paths. **Disposition:** use exact small-vector percentile reference and a declared interpolation/rank convention; retain full tail counts and overflow behavior. Approximate sketches require error/merge validation and must not silently clip overflow.

**F38 — P0 for the mathematical claim: group delay has the opposite sign.** `source/analysis/zdomain_feature_analysis.py` returns `p(p−cosω)/(1−2p cosω+p²)`. Correct group delay is `p(cosω−p)/(1−2p cosω+p²)`, where p=1−alpha. At DC and alpha=.1 the correct delay is +9 samples. **Disposition:** corrected independent reference and finite-difference phase tests, including numerically stable small-gain DC checks. Old mathematical plots are withdrawn.

**F39 — P0/P1: span identities and correlation do not prove W–alpha equivalence.** `N=(2−alpha)/alpha` is a constant-gain white-noise variance-equivalent span, not an equality between rectangular batching, publication cadence and an EMA. Both actuators can correlate because they share pressure; scheduling also changes their observations. Raising alpha widens the constant-gain passband, contrary to the legacy narrowed-passband narrative. **Disposition:** replace the interpretation with the exact mathematics in Section 6 and causal ablations. Do not preserve a misleading contribution by adding the adjective "partial."

**F40 — P1: frozen-time responses are not the adaptive closed-loop transfer function.** The EMA conditioned on a fixed alpha history is linear time-varying; when alpha depends on queues whose workload depends on inputs/predictions, the full system can be nonlinear and time-coupled. A heatmap of static response columns is a diagnostic, not a proof of stability or realized frequency response. **Disposition:** exact variable-gain kernels and replay references; any local approximation must state its conditions and error diagnostics. No BIBO-style feature bound proves queue stability.

### 4.4 Evaluation, statistics, baselines and claims

**F41 — P0: inner joins hide missing or duplicated predictions.** `source/analysis/compute_metrics.py:44,228` inner-merges by `seq` without universally enforcing unique IDs, one-to-one cardinality, complete cohort coverage or identical labels. Wrong/sparse RALF IDs can create multiplicities or silently selected subsets. **Disposition:** independent analysis must fail on duplicates/phantoms/mismatch, account for every scheduled query, and explicitly handle missing/late/dropped outcomes. Scores cannot choose their own evaluation cohort.

**F42 — P0/P1: the reported MBB estimates a different object.** Lines around 65–121 average predictions across runs before computing loss, creating an ensemble rather than average run loss. Fixed disjoint chunks with roughly N/50 rows are not automatically a moving-block bootstrap. Dependence length is not justified, and a NaN-cleaning path does not clean the array actually resampled. **Disposition:** per-run paired losses first, then hierarchical/paired inference over declared independent units. Specify a real block scheme, dependence rationale, censoring policy, missingness and precision target prospectively.

**F43 — P1: five seeds and CI overlap do not prove equivalence.** The manuscript uses overlapping CIs and absence of significance as accuracy equivalence. Five repeated executions over one fixed test corpus address a narrow source of runtime variability and do not create independent data populations. With five independent paired units, a two-sided exhaustive sign-flip test has minimum p=2/32=.0625. **Disposition:** separate execution variability from corpus uncertainty, choose an evidence-backed noninferiority/equivalence margin, and make precision/replication plans before outcomes. Do not use more process seeds to disguise one dataset as many.

**F44 — P1: PATR has phase/window confounding.** Burst/calm service throughput is derived from endpoints that can span disjoint phases and gaps; MaxRate eliminates historical arrival gaps and outcome-dependent service conditions can contaminate the denominator. A ratio may then reflect offered load/schedule artifacts rather than pressure adaptation. **Disposition:** retain raw offered/admitted/completed/on-time counts and actual contiguous phase durations. Compute phase throughput only against predeclared clocks. Prefer a latency/quality/coverage frontier to a single unexplained ratio.

**F45 — P1: the RALF baseline does not establish reproduction of RALF.** `ralf_window_op.hpp` uses a gradient-times-staleness heuristic and budget selection with semantics that differ from published downstream-error prioritization. A 50% budget can mean event/update selection rather than half of users, and current code drops scoring queries. Combined with invented output IDs, this is not a fair published-system comparison. **Disposition:** call a retained idea a named heuristic with its own specification; separately implement/validate a paper-grounded RALF-style baseline and cite the exact difference. All methods serve the same query cohort or explicitly account for missing service.

**F46 — P1: activity "fairness" is not established.** Jain's index on staleness can reward equal bad service; all-zero special cases hide empty/undefined support. Groups based on observed output count can depend on dropping decisions. `fig4.py` inserts zero for missing groups. There are no protected-group attributes supporting a social fairness claim. **Disposition:** use service-equity language scoped to predeclared input-activity groups, expose counts and uncertainty, and report high quantiles/coverage as well as means. Missing groups remain missing. Demographic fairness requires a distinct justified dataset and protocol.

**F47 — P1: unsupported manuscript claims and stale schedules survive corrections.** `paper/draft.md` calls the controller AIMD, claims equivalence and mechanistic confirmation, and contains numerical values inconsistent with the hardcoded figure. Reported correlations/dominant-actuator explanations cannot identify causal mechanisms. Deadlines and venue assertions in old prompts are historical text. **Disposition:** manuscript rewritten from the new claim ledger after experiments; no inherited abstract or conclusion. Every retained claim must identify its current evidence and practical limitations.

**F48 — P1: the legacy tests can pass while core claims fail.** The clean 20-test C++ suite and 16 Python tests passed despite fabricated orchestration, partial-model acceptance, ID corruption, pressure error and retry bias. Many assertions are fixture checks, not real execution admission. Release-mode `assert` can remove checks or side-effecting actions. **Disposition:** current tests use active checks in Release and targeted counterexamples. The next testing layer must include complete source-to-output execution and adversarial mutations; increasing test count without changing fault sensitivity is insufficient.

**F49 — P2: patch-history scripts and bootstrap assumptions are not a maintained implementation.** `archive/dev_patch_scripts/` contains ad-hoc source rewriting and multiple historical fix attempts. Legacy bootstrap/configuration paths can assume old include layouts or OS versions. **Disposition:** archived only. The new root CMake builds the current source directly, uses C++17, and avoids forcing optimized Debug builds. Do not execute historical patch scripts against the new engine.

**F50 — P1: hardware claims are not measured.** The old orchestration declares an M1 Max despite the user working on an M3 Air. Affinity comments, estimated counters and literal durations cannot establish power, GPU use, thermal behavior or sustained throughput. **Disposition:** current audit environment separates user-reported specs and directly observed software versions. No energy/affinity/GPU benefit claimed. Hardware study in Section 11 must read real instruments or explicitly leave fields unavailable.

### 4.5 Factory integration limitations

**F51 — P0 for certification: the built-in profile is only binary classification.** `factory/engine/plan.py:26` rejects other profiles, and its metric set is AUROC, average precision, accuracy, F1, Brier and log loss. It does not admit query freshness, deadline utility, publication accounting or work conservation. **Disposition:** a reviewed streaming domain adapter is necessary. Do not stuff latency into AUROC fields or call batching a model to get a certificate.

**F52 — P0/P1: inference-unit restrictions are narrower than the study.** `plan.py:90` permits only `seed_fixed_test` comparison inference. This cannot represent the proposed hierarchical paired temporal/entity-block experiment without an extension. Its five-seed policy is a floor for its current scope, not universal scientific sufficiency. **Disposition:** explicit typed inference-unit/multiplicity/precision contract and independent replay tests under AMOS-09.

**F53 — P0/P1: strict disjointness conflicts with legitimate temporal warm starts.** `factory/engine/audit.py:57–84` rejects any group, source-record or entity overlap across train/validation/test. For an honest same-user forecasting protocol, prior observed history may legitimately initialize later features, while label-outcome sharing must be purged. Renaming the user or source ID would hide this distinction. **Disposition:** retain strict cold-entity checks as one profile; implement a reviewed dependency-aware temporal profile with label horizon separation and feature-history rules. No bypass and no invented identities.

**F54 — P0/P1: native launch is not an existing runtime contract.** `factory/engine/contract.py` only registers `python-cpu-v1`, launched with isolated flags including `-I -P -B -S` on current Python. A project cannot add arbitrary executable paths to the plan and call that supervisor support. Its argument dictionary is sorted and values are appended positionally, not passed as named flags. `plan.py` still requires a legacy `command` list and `{run_dir}`/`{seed}` placeholders even with a structured contract. **Disposition:** implement and review either a native-aware supervisor runtime or a tightly specified Python adapter that verifies and invokes attested native builds. Test actual argument order and both plan/contract checks; no shell wrapper escape.

**F55 — P1: frozen paths and executables need a real build/input contract.** `factory/engine/io.py` rejects symlink evidence and `.pyc/.so/.dylib`-style generated inputs, while the plan freezes the whole `source/`. A binary compiled from mutable current code is not automatically bound to a frozen source Merkle root. Freezing whole `data/` would include the local quarantine. **Disposition:** build outside source, bind compiler/flags/source/dependency/build-output hashes, verify before launch, and freeze accepted data/manifests explicitly. Resolve policy through reviewed factory code, not untracked binaries under alternate names.

**F56 — P1: receipt signing is not a separate scientific trust boundary.** The supervisor protects private files with permissions, but experiment code running as the same OS user is not automatically unable to read those files. A declared `network=disabled` is not equivalent to OS-enforced network isolation in the current runtime. Hashes/signatures help identify artifacts but cannot prove real acquisition or absence of dishonest code. **Disposition:** state this limit, isolate supervision/keys with a tested boundary when making adversarial provenance claims, verify actual snapshot execution, and include attack tests. No need to pretend local development is a secure enclave.

## 5. The corrected engine: what has been implemented now

The migration deliberately replaces the unsafe execution paths with a smaller C++17 system. There is no dependency on legacy training scripts, baselines, synthetic generators, fixture-only lineage or generic runtime. The feature/controller concepts retained are explicitly specified and remain hypotheses where their benefit is unknown.

| Current module | Contract implemented | Still absent |
|---|---|---|
| `source/include/bpfeat/spsc_queue.hpp` | Constructed typed storage; finite bounded capacity; exactly one producer/consumer; close/drain; usable capacity; pressure in [0,1]. | MPMC, concurrent external-close barrier, loss policy, durable queue. |
| `controllers.hpp` | Validated finite bounds, coherent pressure record, occupancy EMA, slew-limited alpha, named MIMD batch law, real transition counts. | Scientific optimality, identified plant, stale-signal policy for a production deployment, proven queue stability. |
| `features.hpp` | Declared Taobao features, uint64 identity/category/counts, valid timestamp zero, key budget failure, exact source IDs and per-item metadata. | Rolling-window features, state eviction/recovery, production source lineage, ULB semantics. |
| `model.hpp` | Strict schema/complete finite weights, stable sigmoid, strict parsing, round-trip precision. | Fitting, calibration, signed provenance, training-policy binding, external reference models. |
| `replay.hpp` | Streaming exact CSV schema, strict integer/domain/order checks, no labels or burst flags. | Raw ingestion/admission, reordering, workload pacing, query generation. |
| `pipeline.hpp` | Three workers; 2×2 batch/alpha modes; real traces; retry-safe snapshots; full EOF tails; cancellation and terminal conservation. | Publication/query cache, open-loop offered load, deadline utility, complete research receipt. |
| `source/apps/engine_main.cpp` | Explicit inputs/model, strict CLI, no output overwrite, nonzero failure, diagnostic-only completion receipt. | Supervisor-bound attempt execution, hashes/manifests, complete research telemetry and certification. |
| `source/reference/filter_math.py` | Correct constant-gain response/group delay, variance-equivalent span, exact variable-gain weights. | Closed-loop model, stability proof, empirically validated approximation error. |
| `source/preprocessing/labels.py` | Strict-future boundary, same-time exclusion, positive witnesses, censored unknowns and ID checks for an already admitted cohort. | Production admission, cohort selection, external sort, efficient large-data storage, splits. |

All modes start from the same configured alpha and batch size. Feedback is sampled at a real nonempty batch start. The initial pressure record is unavailable until sampled; alpha then updates from observed coherent pressure at source-event cadence. The original bounds/gains are declared **design defaults**, not estimated truths. Neither a default .70 occupancy threshold nor the behavior weights `[1,3,2,5]` are fabricated results; both require rationale and sensitivity if they affect conclusions.

The current pipeline has intentionally transparent costs: every event produces a snapshot and score, CSV formatting/output occurs on the scoring worker, and source creation time is recorded after parsing. Its latency is from that creation point to scoring, excluding read/parse, completed write, scheduled-arrival lateness and client response. Do not benchmark this number as online serving p99. Queue pressure is measured in batch slots, not normalized service work; different-sized batches make a work-aware pressure signal a future design requirement.

The engine receipt says `ENGINE_COMPLETED`, with `research_evidence:false`. It checks actual counters but does not contain input/model/binary hashes or admission records. Its success cannot be promoted by copying it into a factory evidence directory. The tests are deterministic fixtures with explicitly disclosed purpose. Native tests cover queue full/drain/concurrency, bounded controls, IDs, large categories, EOF boundaries including tiny queues, cancellation and output failure. Python checks cover CLI failures, independent closed-form feature/score values, label boundaries and censoring, and exact EMA arithmetic. Debug, Release, address/undefined-behavior sanitizer and ThreadSanitizer checks passed. These checks cover the executed fixtures; absence of a reported race is not a formal concurrency proof. Formal verification has not been performed.

## 6. Mathematical specification to carry into the research protocol

### 6.1 Exact feature dynamics and the limited span interpretation

For an observed scalar feature input x_n and a declared gain alpha_n in (0,1], the recursion is

```text
y_n = alpha_n*x_n + (1-alpha_n)*y_(n-1).
```

With a fixed supplied gain history, its exact solution is

```text
y_n = [product_(j=0..n)(1-alpha_j)]*y_(-1)
    + sum_(i=0..n) [alpha_i*product_(j=i+1..n)(1-alpha_j)]*x_i.
```

The initial-state weight plus all input weights is one, up to numerical error. If inputs and the initial state are bounded and gains remain in [0,1], the recursion stays in their convex hull. This is a feature bound, not a queue stability theorem. If gains depend on the system state and that state depends on x, the complete input-to-output map is generally nonlinear. Treating the observed gain history as fixed does not remove that feedback.

For **constant** alpha, p=1−alpha and

```text
H(z) = alpha/(1-p*z^-1)
|H(exp(i*omega))|^2 = alpha^2/(1-2*p*cos(omega)+p^2)
tau_g(omega) = p*(cos(omega)-p)/(1-2*p*cos(omega)+p^2)
tau_g(0) = (1-alpha)/alpha.
```

The constant-gain response has DC gain one. Higher alpha reduces its DC delay and increases responsiveness. A rectangular average of N independent equal-variance white-noise samples has variance sigma²/N; the stationary EMA variance is sigma²*alpha/(2−alpha). Equating those variances gives `N_var=(2−alpha)/alpha`. The same expression is twice the DC delay plus one, but neither identity makes the kernels equal. An EMA has an infinite exponential tail, a rectangular average has finite support, and a batch is not an averaging kernel at all. Event-count span also differs from elapsed-time span when a key has irregular arrivals.

The new independent reference uses numerically stable denominators at small alpha. Require further differential tests if another language/vectorized implementation is added. A static frequency-response heatmap can illustrate the response of constant-gain operators matching each gain value; label it as such. Validate any quasi-static approximation against exact trajectory replay and record its failure regimes. Do not cite an inaccessible or misidentified DSP source to confer rigor on an unsupported claim.

### 6.2 Separate the actual actuators and establish their cost

Use unambiguous symbols in code, manifests and the manuscript:

| Symbol | Meaning | Potential effect |
|---|---|---|
| alpha | Feature EMA gain/dynamics | Semantic memory/reactivity; same O(1) update cost in the present engine. |
| B | Scorer transport/execution batch size | Amortized fixed overhead and waiting/queueing, without reducing number of scores. |
| U | Feature publication period/budget | Can change number of emitted/cache updates if a publication system is actually implemented. |
| lambda_e, lambda_q | Exogenous event/query offered rates | Define offered workload independently of completions. |
| q_slots, q_bytes, q_work | Queue occupancy in entries, memory or estimated remaining work | Distinct signals; their denominators and estimation errors must be recorded. |

For batching, a plausible cost model is `C_total ≈ N*c_item + (N/B)*c_batch + C_IO + C_control`; smaller B may increase fixed overhead while decreasing waiting. For publication, a simplified model is `C_total ≈ N*c_state + N_pub*c_publish + N_query*c_lookup_score + C_control`. Changing U can alter N_pub; it need not alter N or N_query. These are models to measure, not empirical findings. Include cold-key behavior, heterogeneous feature costs and cache synchronization. If publishing a seven-double snapshot costs less than CSV output and scoring, the proposed mechanism may have no practical benefit; report that and consider a better-founded research question.

For a queue, use an explicit admitted-work recurrence rather than a transfer-function analogy:

```text
q_(k+1) = min(capacity, max(0, q_k + admitted_work_k - serviced_work_k))
offered_work_k = admitted_work_k + rejected_work_k + deferred_work_k.
```

The exact discrete timing and units need definition. No bounded-memory controller can make all externally offered work disappear while also guaranteeing complete timely service under arbitrary overload. Admission, deferral, blocking, drops and deadline misses must all be visible. A backpressured file reader regulates offered input as well as admitted input; it is not an independent real-time arrival generator.

Before choosing controller direction, identify which resource it controls. Under publication overload, increasing U may reduce publication work but increase feature age. Under transport batching, increasing B may improve amortization but increase waiting; decreasing B may worsen throughput. Raising alpha is not an overload relief mechanism. Validate response directions with controlled pilots across bottlenecks, then freeze the chosen law and rationale. If the inherited MIMD law is retained as a baseline, call it that and retain its negative behavior when observed.

## 7. Data admission, causal protocol and splitting

### 7.1 Acquisition and raw admission

The named candidate source pages are [Tianchi Taobao dataset 649](https://tianchi.aliyun.com/dataset/649) and the [MLG-ULB dataset page on Kaggle](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud). Their existence does not authenticate the local bytes. The automated audit could reach the landing pages but did not retrieve authoritative full terms or a provider checksum. Consequently neither license nor source authenticity is filled in by inference. Keep status UNVERIFIED until actual acquisition/terms evidence is obtained.

An acquisition record must contain provider/account attribution, exact URL/version, retrieval time if actually known, provider-described schema/calendar, access/terms text or a durable reference, download/archive hash, extracted-file hash, extraction command/tool, actual byte/row counts, local storage location and the evidence supporting the decision. If the old retrieval time cannot be recovered, say unknown; do not choose a plausible date. A new authenticated acquisition can replace the candidate after a documented byte comparison. A mismatch is investigated, not silently adopted.

For Taobao, stream the raw five-column format without loading it wholesale. Preserve raw line identity as `(raw_file_sha256,line_number)` and raw representation for rejected records. Validate widths, encoding, integer range, behavior mapping, event-time calendar and timezone assumptions. Count and categorize all 318 currently flagged invalid-domain records and all time outliers; distinguish provider anomalies from parsing failures. Analyze exact duplicate rows, same-time distinct items and user ordering. A duplicate source row remains a distinct raw line before a reviewed duplicate policy says otherwise.

Perform duplicate analysis with bounded external sorting or a disk-backed index, not a 100-million-tuple Python set. Measure temporary space before choosing the method. Record `raw_total = accepted + rejected + duplicate_excluded` with disjoint categories, while censoring is a property of otherwise accepted task rows, not a reason to lose source-event accounting. Each rejection/duplicate decision needs a reason code and source IDs. Preserve a stable global time ordering with a deterministic source-ID tie break; do not erase the original source line IDs when assigning replay sequence IDs.

For ULB, preserve Time as relative seconds, all original predictor columns, Class as a held-out target and the lack of entity identities. A distinct adapter must bind those semantics and fit normalization only on training. Do not evaluate keyed scheduling/equity on fake cardholder IDs. If the data cannot support the central serving scenario, retire it from the main comparison and explain why; a second dataset is valuable only when its task genuinely supports the question.

### 7.2 Declare the prediction event and target before training

Recommended Taobao starting task: after an observed behavior at time t for key u, predict whether a buy for u occurs in `(t,t+H]`, with H provisionally two hours because that was the old intended task. Two hours is a candidate domain choice, not a validated optimum. Review its meaning and freeze it before looking at test performance. The current event and all same-timestamp buys are excluded from the outcome; post-event features may include the current observation. Preserve a positive outcome witness source ID and complete-window status. Where exact order within a timestamp is unknown, do not infer it from row position.

Alternative contemporaneous classification uses features immediately before the event and predicts that event's behavior; it requires a separate protocol and no access to the current behavior. Alternative query-time future prediction requires an independently specified query process and feature state at query time. The event-time label reference in this migration is not automatically a query-time label generator. Choose one main estimand, document the others as separate studies, and avoid combining their results under one task name.

Labels are unavailable to all runtime controllers, scheduling policies and feature code. Offline evaluation may join them only through stable identities. A controller may use delayed supervised feedback only when the protocol models its actual availability time; instantaneous future targets are prohibited. Likewise burst annotations may be used for stratified reporting but not as privileged control input unless that input genuinely exists at deployment time.

Censor rows whose horizon is not fully observed under the declared calendar/coverage policy. Do not fill unknowns with negative labels. Retain query/event coverage denominators separately from labeled predictive-metric denominators. A sparse-key last event is not automatically an individual observation end; state the observation mechanism and whether absence of events can reasonably mean no purchase.

### 7.3 Temporal and entity generalization are different questions

Create a primary purged temporal warm-start protocol for forecasting existing users, if that is the intended deployment. Define nonoverlapping training, validation/calibration and untouched test time periods. Require each training label window to end before the allowed next-stage information boundary. Purge/embargo outcome dependencies across adjacent periods by source-ID linkage and horizon, not merely by changing a split string. Use only observed prior history to initialize validation/test features; no future events, labels or test-fitted transforms. Document which warm-up events are excluded from scoring but included as legitimate prior state.

Create a separate cold-entity/time-block protocol to test unseen-user behavior. Its users must actually be disjoint, and its feature cold starts must be treated consistently for all methods. It answers a different question from warm-start forecasting. The factory's strict entity disjointness can serve this case, but cannot be used to falsely certify warm starts by inventing entity IDs.

Maintain a dependency table with source event IDs, prediction/query IDs, observation time, feature dependencies, label-window start/end, outcome witnesses, split and genuine entity IDs. Positive witnesses alone are insufficient to prove negative-label leakage safety; store interval/coverage dependencies too. Define whether repeated label windows and shared future buys induce cluster dependence and use that information for uncertainty.

All hyperparameter selection, alpha-policy choices, feature choices, calibration and baseline tuning happen within training/validation scopes. Preserve an untouched outer test schedule. Hash cohorts and split maps before fitting. Validate that replay transformations preserve those identities; tests should deliberately insert a future event, shared label witness, refitted scaler, phantom ID and renamed entity and require rejection where applicable.

## 8. Target architecture and observability

### 8.1 Implement a genuine publication/query experiment if that direction survives pilots

Separate raw events, mutable feature state, publication actions, immutable published versions, queries, model inference and sink/evaluation records. State mutation must not automatically mean publication, and publication must not automatically mean a query. A transport batch B is an implementation choice that can exist independently of the publication budget U and feature dynamics alpha.

Each publication contains key, version ID, complete feature-policy/schema identity, latest included source IDs/offsets, event-time cutoff, scheduling/acceptance/publication clocks, controller decision and snapshot data/hash. Each query contains its own stable ID, key, task origin, scheduled time, accepted time, deadline and outcome-window identity. Each result identifies exactly which published version was used, model hash, completion time and disposition. Unserved queries retain records with reasons; they are never erased from the cohort.

Define per-key U or budget semantics precisely: event-count cadence, elapsed-time cadence, quota or work budget are not interchangeable. Decide what happens for a new key with no published feature, what happens to an updated key with pending publication, and whether multiple updates coalesce. Coalescing is lawful when explicitly counted and intended; silently dropping events or queries is not. Preserve the freshest admissible included-event time and do not relabel old state as newly observed merely because it was copied.

A cache version becomes visible only after a successful commit. Retries reuse a prepared immutable version and do not advance source inclusion, feature-age baselines or version counters prematurely. Thread ownership and memory ordering must cover actual cache readers/writers. Add a single-thread reference simulator independent of the native runtime, and compare version/query identities and features on deterministic small workloads.

### 8.2 Clocks and freshness

Keep these clocks distinct: provider event time; logical workload time after an explicit mapping; scheduled offered arrival; actual admission; processing start/end; publication commit; query lookup; scoring completion; response completion; and durable sink write if claimed. Runtime durations use a monotonic clock; UTC timestamps identify attempts. Never subtract unrelated epochs or call an arbitrary monotonic value an acquisition timestamp.

At a query, event-time feature age is `query_logical_time − latest_included_event_time`, where the mapping and same-time ordering are specified. Processing freshness may instead be age since publication commit. They answer different questions. Feature error can compare a cached version to an independently replayed exact/fresh reference at the query cutoff. Time since the previous event for a key is a workload statistic, not age of its published feature.

Record latency from scheduled arrival through response for the primary service metric. Decompose it into generator lateness, admission wait, queue wait, service and response/sink time. If throughput is measured with an output-disabled sink, report that separate mode and ensure the operational query identities/counters still exist. Measure logging overhead in a controlled ablation; do not selectively disable instrumentation for one architecture.

### 8.3 Conservation and terminal behavior

For each phase/attempt, all counts must reconcile. Examples include:

```text
scheduled_events = offered_events + generator_not_offered_events
offered_events = admitted_events + rejected_events + externally_pending_events
admitted_events = processed_events + failed_events + in_flight_events
processed_state_updates = publication_included_updates + intentionally_coalesced_updates
scheduled_queries = completed_queries + rejected_queries + deadline_expired_queries + pending_queries
completed_queries = on_time_queries + late_queries
```

Define exclusive categories carefully; an expired query that later completes must not be counted twice in an exclusive terminal ledger. Preserve both terminal disposition and milestone timestamps where needed. Explain which events intentionally do not cause publication. Freeze these equations as typed invariants, not prose only. No `max(0,inflight)` repair, no success after timeout, no EOF interpreted from one transient empty queue and no last-line guess of expected row count.

Shutdown must stop admission, propagate EOF, resolve pending prepared work according to policy, drain or explicitly account for queued work, flush the sinks, join workers and verify counters. Cancellation preserves partial logs and a failed attempt record. A supervisor process enforces the hard deadline and terminates a hung child tree; the cooperative engine check is not sufficient for blocking I/O or process crashes.

## 9. Models, baselines and ablations

Begin with a transparent probability model to validate the system, not to claim a state-of-the-art predictor. Define every feature and fit scope. Train on causal training features with an actual stopping/convergence policy, held-out validation, full-precision export, serialized transforms and calibration diagnostics. Record solver status/warnings, iterations/epochs, train/validation curves or optimizer convergence evidence, coefficients/checkpoint hash, preprocessing scope, dependency lock and prediction agreement between Python and C++.

Prefer unweighted logistic training when evaluating population probability loss unless class weighting is a justified design with independent calibration. Rare positives make accuracy alone uninformative. A class-prior predictor and a causal simple rule are required sanity baselines. A stronger admitted tabular predictor can test whether conclusions depend on weak seven-feature logits, but uses the same causal split and comparable scope. A weak model can still support a narrow systems finding; it cannot automatically support generalized feature-quality claims. There is no universal AUROC .70 admission floor.

Use a **matched frozen-model reference** on exact/fresh features to isolate runtime feature error. A policy-specific retrained/calibrated model answers a separate model-plus-policy deployment question. Adaptive gains create distribution shift relative to fixed-alpha training; either bind the allowed policy to training and test its robustness, or declare the mismatch as part of the study. Do not switch between these designs depending on which creates a positive loss gap.

The baseline inventory should include:

| Baseline | Required behavior and matching |
|---|---|
| Exact/fresh per-event feature publication | Actual per-event update/publication, same model/query cohort; establishes a quality reference and its real work cost. |
| Fixed U publication | Several prospectively chosen cadences or work budgets; alpha and B held fixed. |
| Tuned static policy | Best validation-selected fixed configuration, not a weak arbitrary default; tuning budget disclosed. |
| Budget-matched FIFO/round-robin | Equal publication work/resource envelope; no accidental event/query loss. |
| Real admission throttling | Token bucket or stated policy with offered/admitted/deferred/drop clocks; cannot masquerade as fixed mode. |
| Alpha-only | U/B fixed, alpha responds to its declared signal. |
| Publication-only | alpha/B fixed, U/budget responds to its declared signal. |
| Joint alpha/publication | Identical initialization/resources and signal availability; expose interaction rather than assume synergy. |
| Batching-only diagnostic | Actual migrated engine behavior, clearly separate from publication adaptation. |
| Paper-grounded RALF-style baseline | Algorithm/task/resource mapping justified from primary paper and implementation; deviations explicit. |
| Proposed heuristic | Its own name/specification, not a published-baseline label. |

Factorial ablations should estimate the alpha, publication and interaction effects under matched query/task/resource conditions. Keep transport B fixed in the primary 2×2 alpha/publication study, then vary B separately. Match initialization, min/max budgets, model, workers, queue capacity, logging, query order, arrival trace and controller cadence. Changing controller sampling frequency changes the intervention; if unavoidable, report and analyze it explicitly.

Sensitivity covers gain/slew, occupancy smoothing, thresholds/hysteresis, U/B bounds, queue work/slot normalization, state budget, feature weights, horizon, key skew and actual measured stage costs. Keep confirmatory comparisons small and justified. Larger exploratory grids are allowed when labeled exploratory with their full search history and held-out follow-up; not every grid point needs an inflated significance claim.

## 10. Metrics, uncertainty and claim discipline

### 10.1 Independent recomputation

An independent evaluator reads admitted cohort/labels, actual query/results/publication records and frozen configuration. It must not import model training or consume the producer's reported scalar metrics as authoritative. Reject duplicate/phantom IDs, changed labels, incomplete input hashes, unsupported schemas, malformed timestamps, impossible ordering and unaccounted loss. Use a left-join/full reconciliation against the authoritative scheduled cohort; an inner join cannot choose the answerable subset.

Report proper predictive metrics on valid labels: log loss and Brier for calibrated probability quality, AUROC and **average precision** for ranking, plus counts/prevalence and predeclared threshold metrics if meaningful. Average precision and trapezoidal area under a PR curve are distinct definitions; never use ambiguous AUPRC without naming the convention. Clip probabilities only by an explicit common numerical policy for log loss, recording endpoints and sensitivity if influential. Undefined metrics due to absent class support return an explicit unavailable reason, not NaN silently converted to zero.

Define paired reference loss gap on the same valid query IDs:

```text
gap_i = loss(prediction_policy_i, label_i) - loss(prediction_reference_i, label_i).
```

A negative mean is permitted. Call it a reference gap unless the comparator really meets the stated optimal-oracle definition. Compute losses per execution before averaging executions; averaging probabilities first evaluates an ensemble. If missing queries need a primary quality/utility treatment, specify it before outcomes, show coverage separately and avoid comparing high-quality selected outputs against complete baseline coverage.

For service, report offered/admitted/processed/publication/completed/on-time rates, deadline miss and loss counts, full latency distribution, generator lateness, event-time age, publication age, feature error, memory and measured compute work. Rates use actual phase durations. Distinguish total wall time, event processing drain and steady-state measurement windows. Present quality/latency/coverage/work frontiers rather than one cherry-picked composite ratio.

Service equity uses groups formed from **input** activity or other admissible predeclared characteristics, with fixed membership and complete query counts. Report per-group coverage, age/latency tails, paired quality gaps and uncertainty. Equal poor service is not fairness. Do not infer demographic fairness from anonymized user IDs or fabricate missing groups. If Jain's index is included, define its input utility orientation, support and zero-denominator behavior and display the underlying distribution.

### 10.2 Units, dependence and precision

Separate three uncertainties: stochastic fitting/policy randomness; machine/runtime noise; and sampling/generalization uncertainty across users/time/workloads. An engine with no stochastic action is not replicated scientifically by changing a seed that it ignores. Process reruns measure execution variability; a fixed corpus still remains one corpus. Declare genuine independent experimental units and pairing before choosing a test.

Recommended analysis starts with per-execution paired effects on a common query cohort, aggregates within declared time/entity clusters, and uses a justified hierarchical or block resampling design for the target population. Choose moving, stationary or disjoint cluster/block resampling explicitly; do not label every chunk resample MBB. Evaluate autocorrelation and overlap induced by horizons on training/pilot data; freeze the block-length rule, then show declared sensitivity. Time and user clustering can both matter, and cannot be resolved by choosing whichever interval is narrower.

Pair architectures on workload block, split, fitted model, seed where used, rate schedule and machine trial. Randomize/counterbalance architecture order within a block. Recompute nonlinear statistics such as tail quantiles/rate ratios for each resample rather than taking a mean of unrelated per-run quantiles. For rare-event metrics show class support per block and any resampling invalidity rate; do not silently discard resamples until a desirable interval appears.

Specify a primary estimand, direction, practical effect margin, confidence level, multiplicity family, maximum acceptable CI width and sample/precision rationale. Choose a fixed independent-unit count from pilot variability or a prospectively valid sequential design with explicit stopping/alpha control. Do not keep running until p<.05. At least five seeds is a factory floor and not a power calculation. If the feasible dataset has only a few independent periods, disclose that limitation and narrow the claim.

Superiority requires evidence for the stated direction and meaningful effect. Noninferiority/equivalence requires a justified margin and an appropriate interval/test; overlapping marginal CIs are insufficient. A two-sided null result with a CI spanning important gains and harms is inconclusive. A narrow interval excluding important benefit supports a scoped negative finding. Corrections after observing test failures require a new version and clearly identified exploratory versus untouched evaluation data.

### 10.3 Claims and failure analysis

Maintain `project/claim_ledger.json` with claim ID, exact wording, estimand/population/scope, prospective versus exploratory role, experiment IDs, analysis/hash links, effect/CI and limitations. No claim begins "confirmed" before the frozen run and independent analysis exist. Retain failed attempts, negative subgroups, no-benefit regimes and opposite actuator responses. Failure taxonomies must be derived from actual trace/query IDs and counts; a prose-authored list is a proposal, not measured prevalence.

Distinguish mechanisms from correlation. Pressure causes both alpha and U to change under the policy; a correlation between them is expected and not proof of substitutability. Intervene on one actuator while holding the other fixed, compare equal-resource/static controls, inspect measured work and perform controller-disabled signal replay. Causal claims about real deployments remain limited by the replay assumptions and architecture.

## 11. Hardware and experimental design for the M3 Air

The user reports an M3 MacBook Air with eight CPU cores, ten GPU cores, 16 GB unified memory and 512 GB storage. The audit observed arm64 execution, macOS 27.0 and Apple Clang 21.0.0; precise observations are in the environment artifact. GPU use, frequency, power, core placement and thermal state were not measured. The current C++ engine is CPU-based and has no GPU code. Adding GPU activity merely because the machine has a GPU can obscure the question and compete for unified memory; it is not required for a sound study.

Use one substantial experiment at a time. Start with bounded preprocessing chunks and a deterministic small admitted cohort, then scale keys/events until the memory and runtime envelope is known. One million keyed states in the present unordered map may be feasible or costly depending on overhead; measure RSS, allocation behavior and swap rather than deriving feasibility from seven doubles alone. Avoid copying full 100-million-row DataFrames or maintaining several Python tuple/set representations. Prefer streaming, external sorting, columnar artifacts or a documented disk-backed index when justified; pin whichever dependency is actually selected.

Use at most two build jobs initially to leave memory for the OS and keep measurements free of concurrent compiler work. Build Release for performance and run identical correctness cases in Debug/Release. ASan/UBSan are correctness tools and are not performance configurations. Save complete compiler/version/flags, native executable hash and build-source snapshot hash. Do not describe 128-byte padding as a measured cache-line fact or macOS QoS as verified physical-core pinning.

Before each performance block record actual OS/toolchain/power mode, AC/battery state if available, active workload interference, memory pressure/swap, actual start/end wall/monotonic times and any measured thermal instrument. Use a declared cool-down/steady-state protocol appropriate to a fanless laptop; measure sustained degradation rather than extrapolating from a short burst. If energy sensors require unavailable privilege or cannot be calibrated, omit energy claims and mark unavailable. Never estimate joules with an arbitrary multiplier or fill thermal fields from a model name.

The factory's hardware floor of five trials and 30 sustained seconds is not automatically adequate here. Pilot the warm-up/steady-state/drain lengths and then freeze a duration that captures sustained behavior and enough query tail support. Count how many observations support p99/p99.9; a small fixture cannot measure service tails. Record confidence/variability, failed trials and run order. Do not rerun just the slow architecture until its best trial matches the others.

Space budgets must include raw candidates (~3.82 GB decimal), current Git history (~1.1 GB locally), external-sort/index temporary files, accepted derivatives, models and telemetry across repeats. Full legacy results are ~9.26 GB and are not copied into active runs. Set a measured disk reserve and stop a run before silent truncation. Compression/columnar storage is acceptable if schemas, logical row counts, checksums and reader compatibility are validated. Storage pruning must preserve registered evidence and cannot selectively erase unfavorable runs.

### Experiment ladder and stop conditions

| Stage | Workload | Purpose | Advancement condition |
|---|---|---|---|
| E0 correctness | Disclosed deterministic fixtures, empty/tiny/tail/blocked/failure cases | Exact identities, math, lifecycle and reference agreement | All invariants and adversarial mutations behave correctly; no scientific performance claim. |
| E1 raw/data protocol | Full streamed candidate profiles plus admitted bounded cohort | Authenticity, terms, canonicalization, labels and splits | Complete reasoned admission/accounting, independent replay and frozen cohort IDs. |
| E2 mechanism pilot | Admitted training/validation event/query blocks, controlled stage cost/rates | Determine actual work-changing mechanism and response direction | Measured costs/coverage support the proposed architecture; otherwise pivot or stop. |
| E3 pilot frontier | Few honest methods across underload, near-capacity, overload and key-skew regimes | Choose resource envelope and prospective margins/replication | No protocol errors; untouched test preserved; no selecting a mechanism solely from test outcomes. |
| E4 confirmatory | Frozen real-source blocks and exogenous query/load schedules | Estimate preregistered quality/latency/work effects | All planned attempts accounted for, independent analysis complete, precision achieved or uncertainty disclosed. |
| E5 robustness | Unseen time/users, alternate trace/task if suitable, heterogeneous costs, sustained runs | Scope and failure boundaries | Claims narrowed to evidence; external validity limits explicit. |
| E6 reproduction | Clean clone/environment, acquired data, immutable build and standalone verification | Reproduce claimed artifacts and numbers | Another evaluator can follow the recipe without legacy folders or invented metadata. |

Start E3 with three offered-rate regimes relative to a **measured and training/pilot-frozen** reference capacity: underload, near saturation and overload. Numeric rate multipliers are design candidates, not universal constants. Add step/ramp/burst schedules, key skew and query/event ratios only where they test a stated mechanism. Preserve historical relative events through a disclosed pacing transform; replaying real events faster is a controlled workload built from real records, not a capture of production arrival behavior.

Use open-loop scheduling independent of completions for latency/overload claims. Record late offers instead of moving their timestamps to when a backpressured reader is ready. Fixed schedules are shared across methods. Burst/calm windows use the scheduled clock, with complete interval durations and drain attribution. An offline MaxRate run is useful for saturation diagnostics and must be named as such. It cannot establish historical real-time service quality.

Injecting artificial scoring delays or cost distributions can identify a mechanism, but these are controlled simulation/stress parameters, not measured native feature costs. Label them explicitly, apply the same law to every method, exclude outcome-derived burst flags from the injection and include native no-injection workloads. If benefit exists only under a contrived delay, the claim is conditional on that regime.

## 12. Software factory v3.3 integration

### 12.1 Keep the supplied factory authoritative within its real scope

Read `factory/README.md`, `constitution.md`, `factory_spec.md`, `SCIENCE_PROTOCOL.md`, `AGENT_WORKFLOW.md`, `architect_spec.md`, `implementor_spec.md` and the active engine/schema files. `factory/legacy/v2_6_0/` is historical material. The old AMOS chunks/contracts are diagnostic history, not the active registry. Do not duplicate dozens of obsolete status files to create an appearance of progress.

`project/research_plan.json` is intentionally the empty supplied template. It has no experiments/claims and unresolved context; it is not a prospective protocol. `project/planning_state.json` explicitly records the blockers. Replace the template only when the actual task/data/adapters exist. Do not freeze it as a fixture and cite that as research readiness. `project/methodology.md` currently records the same honest starting boundary.

The active gatekeeper supports init, freeze, run, record, audit, certify, status and handoff. `run . all` records and validates supervised outputs in its current supported scope. Before executing a command, consult `python3 factory/gatekeeper.py --help` and the relevant subcommand help; do not invent CLI options from this prose. A typical later supported lifecycle is:

```sh
python3 factory/run_self_tests.py
python3 factory/gatekeeper.py freeze .
python3 factory/gatekeeper.py run . all
python3 factory/gatekeeper.py audit .
python3 factory/gatekeeper.py status .
```

These commands are **not ready to run as an AMOS research pipeline today**. Freeze/run are dependent on completed contracts. Certification additionally requires the applicable coverage/provenance/training/split/plausibility/traceability/reproduction/review/bundle gates. Preserve legitimate fail-closed outcomes. A current factory diagnostic is useful, but cannot substitute for the new streaming checks.

### 12.2 Required adapter contracts

Implement a reviewed `streaming_publication` domain profile, with a versioned name selected in the adapter contract. Its typed plan must declare task and feature-policy IDs, cohort/source/query/publication schemas, logical/physical clocks, arrival mapping, warm-up/measurement/drain rules, loss dispositions, models/training/calibration scopes, controllers/baselines/resources, primary metrics, inference units and precision/multiplicity rules. Unsupported fields fail explicitly; extra metrics cannot be silently ignored.

The independent adapter recomputes prediction metrics using the existing tested oracle where appropriate, and recomputes streaming coverage, conservation, deadlines, ages/work/latency and paired reference gaps from authoritative logs. It validates temporal feature-history legality separately from outcome overlap. Add mutation tests for wrong source/query IDs, duplicate results, swapped labels, future-feature events, shared outcome leakage, suppressed misses, retry double-counts, invented clocks, header-only traces, wrong binaries, phantom hardware and stale reviews.

Review native execution explicitly. One viable design is a supervisor-owned native build/launch runtime that freezes source/manifests, resolves an approved compiler/toolchain, emits a build receipt and launches only the resulting verified binary. Another is a narrow isolated Python entrypoint with approved imports/build/launch behavior and a separately attested native receipt. Decide before implementation which boundary actually prevents mutable or untracked code from affecting outputs. Test isolated Python import resolution under `-I -P -B -S`; ordinary local imports/dependencies may not be available as in a shell run.

Because `contract.resolve_contract` sorts argument keys and appends values, an entrypoint cannot assume named flags magically arrive. Write a checked argument ABI and actual argv golden/counterexample tests. Keep the required legacy `command` list consistent with the structured contract until plan validation is deliberately updated. Do not rely on shell strings, interpreter `-c`, PATH substitutions or renaming a native binary into a `.py` path.

Build outputs are generated artifacts outside `source/`; bind their source snapshot, compiler, flags, link inputs, dependency versions and executable hash. Freeze **accepted** data artifacts/lineage and methodology, not quarantine or mutable run directories. The factory's source-wide freeze should include actual model/runtime/evaluation scripts and scientific constants. Verify execution uses the frozen snapshot or checks the exact immutable input set immediately before launch. Avoid a gap where the receipt names frozen code but a mutable working tree is executed.

For provenance stronger than cooperative local integrity, isolate experiment permissions and signing keys from the experiment OS identity, and test that unauthorized reads/writes/network operations are blocked. Do not claim network isolation merely because a contract says disabled. A local-only integrity implementation may be acceptable if its threat model and remaining trust are disclosed; it should not issue broader assurance than it provides.

### 12.3 Review and factory modification discipline

Preserve the original v3.3 baseline in history and retain its test log; the active factory now contains the documented 3.3.1-amos.1 repairs. Maintain legitimate binary-classification behavior, add positive and adversarial streaming cases, and rerun the full suite after changes. The current complete suite executes 307 tests, including five function fixtures that original unittest discovery omitted. Incorrect assertions claiming sealed evaluation or independent review from file presence were replaced with bounded-assurance checks; numeric and receipt counterexamples must remain detectable. Tests must independently detect bypasses, not merely mirror the producing code. A failed existing check is investigated; do not relax it until the intended replacement guarantees are implemented and reviewed.

The Architect's review must cover method identity, data/leakage, fitting/calibration, statistics, baseline fairness, ablations/sensitivity, failure/generalization, reproduction and claims/venue. An AI-written review may be valuable but must not be labeled human approval. The user's original request authorizes this migration/audit; it does not authenticate datasets or accept future scientific claims in advance. Record actual reviewer identity/role and decision evidence.

## 13. Ordered implementation contracts for future agents

Each contract has one scientific/engineering purpose, dependency IDs, actual input hashes, scoped changes, outputs, targeted tests, failure behavior and a concrete review artifact. The Architect may refine sizes and split large contracts while preserving dependencies/gates. The Implementor may not skip a blocking dependency to create a plausible output. Advance planning metadata only after required outputs exist and checks run; comments and generated PASS prose are not completion evidence.

| ID | Dependencies | Purpose and deliverables | Required acceptance evidence |
|---|---|---|---|
| **AMOS-01: scope and claim retirement** | Audit handoff | Current source map; reviewed research object; retired legacy-claim list; initial falsifiable RQs; document batching versus publication choice. | Every proposed claim has a measurable estimand and explicit current status. No legacy number treated as evidence. |
| **AMOS-02: acquisition and admission** | 01 | Provider terms/acquisition records, candidate comparison, full schema/calendar/duplicate profile, source-ID/rejection tables, storage budget and admission manifest. | Actual source evidence; checksums/accounting; all invalid/outlier categories explained; no guessed license or retrieval date. |
| **AMOS-03: production canonicalization** | 02 | Bounded ingestion/external ordering, stable source-to-seq mapping, exact-width domains, complete lineage DAG and deterministic cohort selection. | Raw-to-output accounting and hashes; chunk-size invariant output; same-time different-item test; malformed/outlier/duplicate dispositions; no 16-bit narrowing. |
| **AMOS-04: task, labels and splits** | 01–03 | Reviewed target/time/coverage protocol, scalable strict-future labels or chosen alternative, witnesses, dependency graph, purged warm-start and distinct cold-entity splits. | Independent small reference; boundary/censor/future/leakage mutation checks; genuine entity IDs; frozen untouched test map. |
| **AMOS-05: model and provenance** | 04 | Honest fitting/calibration, transform export, convergence evidence, policy/model manifest, Python/native prediction agreement; trivial and matched reference models. | Training scopes/locks/hashes actual; no test selection; complete weights; missing/corrupt/schema/policy mismatch fail; held-out calibration diagnostics. |
| **AMOS-06: publication/query core** | 01,03,04 | Versioned cache, independent queries, U/B/alpha separation, cold-key and coalescing semantics, complete clocks/records and single-thread reference. | Exact reference identity/version/feature agreement; retries do not commit early; EOF/cancel/block/key-budget cases conserve counts; no labels in runtime inputs. |
| **AMOS-07: workload and mechanism pilot** | 05,06 | Open-loop generator, offered/admitted/lateness counters, contiguous phases, measured cost model and bottleneck/actuator-sign characterization on non-test data. | Actual work changes demonstrated or a documented stop/pivot; schedule unaffected by completions; native versus injected costs disclosed. |
| **AMOS-08: baselines and controls** | 05–07 | Tuned static, exact/fresh, real throttle, budget-matched schedulers, alpha/publication/joint modes, paper-grounded or explicitly named heuristic baseline. | Behavioral signatures differ as specified; equal query cohort/resource/logging; no fallback architecture; fair validation tuning budget. |
| **AMOS-09: independent analysis and inference** | 04,06–08 | Typed metric definitions, complete-cohort reconciliation, reference gaps, latency/age/work metrics, paired hierarchical/block inference, precision/multiplicity specification. | Golden independent vectors; duplicates/phantoms/missingness/clocks/label swaps fail; no ensemble-loss substitution; justified inferential unit. |
| **AMOS-10: real attempts and native receipts** | 03,05,06 | Real subprocess supervisor, native build binding, strict argument ABI, process deadlines, immutable unique attempts, complete failure logs and safe resume. | Missing executable cannot complete; killed/hung/bad-output attempts fail; changed config/model/input/binary invalidates resume; actual clocks/hashes. |
| **AMOS-11: v3.3 streaming adapter** | 04,09,10 | Reviewed domain/runtime schemas and checks, dependency-aware temporal profile, input freeze scope, receipt/analysis integration, signing trust statement and attack registry extensions. | Current 307-test suite passes with legitimate binary behavior retained; streaming positive/mutation cases; actual argv/snapshot launch verified; no check bypass. |
| **AMOS-12: hardware and measurement pilot** | 07–11 | Measured RSS/disk/swap/steady-state/warm-up/logging overhead; real metadata; pilot variance and sustainable experiment envelope. | Measurements from actual instruments; unavailable energy/core data remains unavailable; no performance values inferred from hardware specs. |
| **AMOS-13: prospective scientific freeze** | 01–12 | Complete non-template research plan/methodology, chosen RQs/baselines/resource scopes, untouched cohorts, experiment matrix, stopping/precision/CI/multiplicity rules and review. | Factory/domain validation passes without waiver; review covers all scientific topics; all numbers are design choices or linked pilot measurements, not test results. |
| **AMOS-14: confirmatory execution** | 13 | Execute planned real-source workloads/trials; record every success/failure, scheduling/order/environment and full telemetry. | No selected seeds/method exclusions after outcomes; all attempts accounted; conservation/admission/supervision checks; frozen inputs remain identical. |
| **AMOS-15: robustness and failure analysis** | 14, with prospective additions if needed | Unseen periods/users, alternate suitable task/trace, cost/skew/resource sensitivities and actual failure taxonomy; distinguish exploratory studies. | Negative/opposite/no-benefit regimes retained; cohorts/units valid; claims revised to demonstrated scope; no fabricated taxonomy prevalence. |
| **AMOS-16: independent reproduction** | 14,15 | Clean-checkout recipe, dependency/runtime acquisition, standalone verifier and per-number/figure manifest; reproduction attempt by separate evaluator where available. | No dependency on old local folder; clean build/run/recompute; signed artifact identity and license/access constraints disclosed. |
| **AMOS-17: manuscript and venue audit** | 09,14–16 | New manuscript/abstract, checked bibliography, claim ledger, methods, limitations, negative-results interpretation, artifact/data statement and selected venue checklist. | Every quantitative statement traceable; no CI-overlap equivalence; baseline names correct; current official venue rules checked; no acceptance guarantee. |
| **AMOS-18: submission release** | 17 and all required gates | Frozen release bundle, exact submitted-source/build/evidence IDs, actual review decisions and reproduction report; archived failed/exploratory evidence references. | Factory certificate only within supported scope; no unresolved blocker for any retained claim; final human scholarly/submission review recorded honestly. |

AMOS-01/02 may involve missing provider information. Continue independent software/protocol work when possible, but do not fabricate an acquisition decision to unlock 03/13. AMOS-06 is contingent on the scope decision; if the project remains a batching study, replace it with an explicit batching/reference architecture contract and remove all publication claims. AMOS-07 has a real stop condition. More code is not automatically the best response to a nonexistent mechanism.

Every contract review should answer: what input authorizes this scientific inference, what observation would falsify the hypothesis, what happens on missing data/failure, and what independent artifact lets another evaluator check it? Administrative completeness cannot replace those answers.

## 14. Suggested research questions and publication routes

The main candidate question is whether queue/work pressure can allocate feature publication work so as to improve a measured latency/quality/coverage frontier over a tuned static and equal-budget baseline, while keeping feature-dynamics adaptation a separate intervention. Candidate secondary questions concern the cost/quality interaction between publication and alpha, when slot pressure fails to represent remaining work, and which workload/key/cost regimes make adaptation harmful or unnecessary. These are questions, not current findings.

A positive systems route requires a novel, justified mechanism plus a working end-to-end implementation, fair strong baselines, realistic workload mapping, robust gains and candid failures. A negative/analysis route requires a reusable, credible benchmark or new explanatory insight: for example, demonstrating precisely when a plausible pressure heuristic is dominated, when batching/publication semantics invalidate supposed gains, or how coupled gains bias evaluation. Merely reporting that a personal prototype has bugs is not by itself a top-tier research contribution.

Prior work to read and reproduce in the appropriate scope includes:

| Primary source | Relation to AMOS and required follow-up |
|---|---|
| [Wooders et al., RALF, PVLDB 17(3), 563–576](https://doi.org/10.14778/3632093.3632116) | Feature maintenance/prioritization using downstream error. Read the algorithm and artifact; specify task/budget/feedback differences before claiming a reproduction. |
| [Chang, Lo and Ye, Biathlon, PVLDB 17(10), 2631–2640, 2024](https://www.vldb.org/pvldb/vol17/p2631-lo.pdf) | Approximate feature computation and prediction uncertainty. Distinguish real aggregation work/guarantees from changing a constant-cost EMA gain. |
| [Crankshaw et al., Clipper, NSDI 2017](https://www.usenix.org/system/files/conference/nsdi17/nsdi17-crankshaw.pdf) | Prediction serving and batching; useful for the actual batching/latency question and tuned serving baselines. |
| [Bifet and Gavaldà, adaptive windowing, SDM 2007](https://epubs.siam.org/doi/10.1137/1.9781611972771.42) | Data-change-driven windowing differs from queue-pressure transport batching. Do not call the existing range heuristic a validated ADWIN implementation. |

Maintain a literature matrix with exact algorithm, workload, resource model, signal/feedback availability, guarantee, evaluation and artifact compatibility. Search more current work before final novelty claims; the four sources above are starting points, not an exhaustive related-work review. Compare what the systems actually do, not their names. Check every citation and remove misidentified or inaccessible references used as mathematical authority.

The [current VLDB 2027 research call](https://vldb.org/2027/call-for-research-track.html) includes regular systems research and Experiment, Analysis & Benchmark papers; the latter requires substantive insight or reusable evaluation/workload artifacts. This is a possible fit for an honest analysis/negative outcome, not a shortcut around novelty and rigor. Recheck the [official submission guidelines](https://www.vldb.org/2027/submission-guidelines.html) when choosing a target. Do not copy old BigData deadlines or choose a category merely to avoid an inadequate evaluation.

For a journal route, choose based on the actual contribution, required evaluation breadth, artifact access and manuscript maturity. Do not list arbitrary prestigious venues as if their acceptance criteria are interchangeable. One laptop supports careful local evidence; broad deployment/scaling claims may need another environment or a narrower claim. If external compute is needed, provide a portable measured experiment recipe and an explicit resource request, not fabricated cluster measurements.

## 15. Submission-readiness gate checklist

| Gate | Evidence required | Current status |
|---|---|---|
| Acquisition/terms | Provider-backed records and permitted access/distribution scope | BLOCKED / unverified candidates |
| Task/causality | Explicit prediction time, target horizon/coverage, feature availability and dependency tests | Reference corrected; protocol pending |
| Production lineage | Full raw-to-cohort identities/accounting with deterministic transforms | Pending |
| Split integrity | Purged temporal dependencies and honest warm/cold scope | Pending |
| Training/calibration | Real fit/convergence, proper scope, policy-bound model and independent prediction agreement | Pending; no migrated model |
| Method identity | Genuine work-saving mechanism, or a correctly scoped batching study | Pending |
| Runtime integrity | Complete queries/publications/clocks/terminal counts/process supervision | Engine foundation passes; full system pending |
| Baselines | Behavioral reproduction, tuning/resource fairness and same cohort | Pending |
| Statistics | Independent metrics, valid units/dependence, prospective precision and multiplicity | Pending |
| Hardware | Actual sustained instrumentation and bounded claims | Audit environment only |
| Factory support | Reviewed native/streaming adapters with mutation and full regressions | Pending; local integrity patch regression passes; native/streaming profile still absent |
| Confirmatory evidence | Frozen prospective runs including failures/negative regimes | None admitted |
| Reproduction | Clean recipe, standalone verification and actual reproduction report | Pending |
| Novelty/venue | Primary literature comparison and current venue fit | Unresolved |
| Release/review | Traceable manuscript/bundle and actual final scholarly review | Not ready |

A submission candidate may legitimately have a negative result, weak benefit or harmful regimes if the method, uncertainty, scope and contribution are sound. It may not have missing source provenance presented as resolved, fake models, incomparable query coverage, leaked labels, unsupported mathematical identities, invented hardware or post-hoc certificates. An unsupported claim can be removed; a missing dependency for a retained claim remains a blocker.

## 16. Session handoff instructions

### Architect starting instruction

> Read plan.md, source/README.md, project/planning_state.json, the AMOS audit artifacts and active factory v3.3 specifications. Treat legacy numerical claims as retired and all candidates as unadmitted. Start AMOS-01/02 by defining the scientific object and acquisition evidence, then issue concrete ordered contracts with dependencies, artifacts, independent acceptance checks and stop conditions. Preserve the distinction between transport batching, publication cadence and feature gain. Resolve factory domain/native/temporal/inference limitations through reviewed extensions. Do not declare scientific success or invent an approval to advance status. Keep negative and inconclusive routes open.

### Implementor starting instruction

> Read the same handoff and the Architect's actual contract. Implement only its supported scientific/engineering scope, starting from the corrected source engine. Preserve source/query identities, causal feature/label timing, failure attempts and exact accounting. Use independent references and targeted adversarial tests that remain active in Release. Record actual commands, hashes, clocks and measured metadata. Missing models/data/outputs fail; fixtures remain fixtures. Report discrepancies and unresolved assumptions with evidence instead of substituting hardcoded results. Do not execute the legacy orchestrator or copy old fitted weights/plots.

### First actions in the new folder

```sh
git status --short
cmake -S . -B build/debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build/debug -j 2
ctest --test-dir build/debug --output-on-failure
python3 factory/run_self_tests.py
python3 factory/gatekeeper.py --help
```

On a restricted environment, the factory's local socket tests may need the environment to allow Unix sockets; report that restriction and rerun the same suite when permitted. Do not infer a factory logic failure from a sandbox-only permission denial, and do not mark unrun tests as passing. CMake discovers a Python interpreter; record the actual path/version because the audit Python and CMake-selected Python may differ.

Read candidate manifests and profiles before attempting raw preprocessing. No current ready-made research CLI/model exists, and running the foundation requires an explicit compatible weight file and canonical unlabeled CSV. Testing with generated tiny inputs is fine when clearly disclosed; fitting fake weights and calling the resulting accuracy research is not.

After each contract, write a short actual completion report with artifact paths/hashes, changes, executed validation, results/failures and remaining limits. Update planning status honestly. Do not fill old Cxx/Dxx status families just to satisfy a historical template. The final manuscript should make it possible to distinguish what was designed, what was measured, what was inferred and what remains unknown without reading this conversation.

## 17. Audit conclusions and unresolved questions

The old project contains useful ideas and partial rehabilitation work, but its current evidence cannot establish the advertised load/accuracy mechanism or publication claims. There are reproduced fabrication/execution defects, identity and timing errors, causal-label/split problems, representation mismatch, statistical estimand errors and mathematical misinterpretations. Clean legacy test results did not detect them. Those facts justify retiring the old evidence and rebuilding the admissible study rather than polishing its plots.

The migrated engine removes the demonstrated unsafe paths within its deliberately narrow boundary. It preserves a real bounded threaded computation, explicit models/configuration, valid IDs/domains, retry-safe event records, terminal conservation and independently tested mathematical/label references. It does not pretend that a research-grade publication/query architecture, data admission, fitting, native factory support or scientific result has already been completed.

Open questions to resolve through the contracts are: whether the candidate raw files can be authenticated under usable terms; which task the events actually support; whether a publication actuator saves meaningful work; whether alpha adaptation helps or harms a properly trained matched model; how pressure should represent heterogeneous service work; what independent units the available observation horizon provides; which failures carry reusable scientific insight; and how far one local machine supports the proposed deployment claims. Answers can change the direction of the project. Their uncertainty is part of honest research and must remain visible until evidence resolves it.
