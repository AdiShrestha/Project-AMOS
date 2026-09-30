# BPFeat / Project AMOS Rehabilitation Plan

**Plan status:** Proposed rehabilitation and publication-readiness programme  
**Plan version:** 1.0  
**Prepared:** 2026-08-28  
**Project:** BPFeat, currently stored as Project AMOS  
**Factory reference:** Software Factory v2.2.0, supplied read-only at `/Users/adi/Downloads/factory_v2_2_0`  
**Execution starting point:** the existing Project AMOS repository, not a rewrite and not an empty scaffold

---

## 0. Purpose, scope, and the central decision

This document is the complete plan for rehabilitating the existing BPFeat research repository into a project that is structurally, procedurally, scientifically, and evidentially indistinguishable from a project that had been governed by Software Factory v2.2 from its beginning. It is intentionally a plan, not an assertion that the rehabilitation has already happened.

Only the existing BPFeat repository is to be rehabilitated. The useful implementation, tests, experiments, and research reasoning already present are inputs to the process. They are not to be discarded merely because they predate the factory. At the same time, no legacy file, result, claim, or earlier PASS verdict receives automatic trust. Every retained item must earn its place through provenance, inspection, testing, or recomputation.

The central decision is:

> Adopt Software Factory v2.2 around the existing repository, start the first implementation chunk with an evidence-preserving intake and canonicalization of that repository, and then revalidate the system from runtime semantics through data, statistics, experiments, manuscript, and release.

The desired end state is not a cosmetically rearranged repository. It is a publication-ready research artifact for which a reviewer can answer all of the following without relying on the authors' memory:

1. What exact claim is made?
2. Which immutable inputs, source revision, configuration, model, and command produced its evidence?
3. Which tests establish that the implementation measures the intended phenomenon?
4. Which statistical procedure supports the claim, and what are its limitations?
5. Can an independent person reproduce the result from a clean checkout?
6. Which parts are raw data, derived data, generated evidence, development debris, or release artifacts?
7. Which Software Factory contracts and gates were actually satisfied?

The plan is deliberately conservative. The current implementation appears valuable and several unit-level checks pass, but the current experimental evidence cannot safely support publication claims until the issues recorded below are resolved and all reported numbers are regenerated.

---

## 1. What was studied

This plan is based on direct inspection of both supplied folders, not only their README files.

### 1.1 Existing BPFeat / Project AMOS material inspected

The review covered:

- the Git status, branch, remote, commit history, tracked-file inventory, ignored-but-tracked files, and repository object size;
- the root build system and nested CMake files;
- the C++ runtime, queues, operators, feature windows, backpressure components, model code, harness, and executable entry points;
- all current C++ tests and the existing compiled test suite;
- Python preprocessing, oracle construction, classifier training, analysis, result collection, and synthetic-data generation;
- datasets, replay artifacts, model weights, run outputs, trace files, summaries, figures, and paper inputs;
- the manuscript draft and publication-facing README;
- old audit reports, prompts, notes, patches, archived material, and duplicated implementations;
- the embedded `revised_software` tree, including its Factory v1.0.1 metadata, founding documents, Chunk 01 and Chunk 02 records, and duplicated source tree.

At the time of inspection, the repository was clean on `main` at commit `37c85a6`, matching `origin/main`. The compiled test suite reported nine of nine tests passing. Python source files inspected for syntax also compiled successfully. These are useful baseline facts, but they are not publication certification.

### 1.2 Software Factory v2.2 material inspected

The review covered:

- the factory overview, version, bootstrap manifest, bootstrap scripts, and existing-project behavior;
- the constitution and its preservation, evidence, role, contract, snapshot, and certification rules;
- Architect and Implementor specifications;
- Gatekeeper behavior and its actual command surface;
- scientific-validity and domain checklists;
- chunk, contract, report, evidence, recomputation, and release templates;
- claim tiers, Methodology Adversarial Review, Reality Gate, evidence checks, report stamping, tier checks, and release certification;
- the v2.2 change log and differences relevant to the older v1.0.1 attempt inside Project AMOS.

The supplied factory folder is a reference distribution, not the project workspace, and is to remain read-only. Its version is 2.2.0. The rehabilitation must use an explicitly recorded, checksummed copy or pinned upstream revision; it must not silently download an unpinned `main` branch and call that v2.2.

### 1.3 Limits of this inspection

The inspection establishes concrete defects and inconsistencies in the current tree and defines how to resolve them. It does not by itself prove that every suspected scientific issue changes the final conclusion. Some findings, such as the exact effect of timestamp precision or duplicate RALF keys on published metrics, require controlled experiments. Until those experiments are complete, the correct status is **unvalidated**, not harmless and not conclusively fatal.

---

## 2. Executive diagnosis

### 2.1 What is worth preserving

BPFeat is not an empty or failed project. It already contains:

- a coherent research direction around backpressure-aware streaming feature computation;
- a C++17/pthreads implementation with multiple architecture variants;
- a nontrivial queue/runtime/operator design;
- real-data and synthetic-data preprocessing attempts;
- existing unit and integration tests;
- analysis code, experiment outputs, and a manuscript outline;
- an earlier effort to introduce formal invariants and chunked delivery.

This is enough to justify rehabilitation rather than a ground-up rewrite. The existing code supplies implementation hypotheses, known failure modes, and regression fixtures. Rewriting it wholesale would erase information and create fresh defects.

### 2.2 Why it is not publication-ready

The repository currently mixes five different kinds of material at the same level: source code, raw/derived data, generated experiments, historical development records, and publication artifacts. More importantly, several end-to-end assumptions are contradicted by the implementation or by the artifacts presently on disk.

The most consequential findings are:

- shutdown is inferred from source completion and momentary queue emptiness rather than an exact completion protocol; partial windows are not demonstrably flushed;
- the harness creates more workers than its described topology and contains a non-atomic cross-thread completion flag;
- the nominal rate-throttle baseline is not distinctly enabled in the main harness path;
- the command-line seed labels repeated runs but is not used as an algorithmic seed in the architecture execution path;
- result summaries can report input row count rather than verified sink output count;
- model-load failure can fall back to a zero model and allow an invalid experiment to continue;
- controller trace output is not wired to the adaptive operator, while a later script reconstructs a trace from result output and describes it as perfectly reconstructed;
- C++ and Python feature semantics are not proven equivalent and visibly disagree in important areas, including the ULB behavior mapping;
- epoch-scale timestamps are represented in a way that can lose relevant time-gap precision in the online path;
- classifier selection and scoring do not implement a fully out-of-fold, fold-manifested oracle pipeline;
- label construction may include the current purchase event in both features and the positive label, creating a prediction-time ambiguity and potential leakage;
- statistical resampling collapses runs before bootstrap and does not clearly implement the moving-block procedure claimed by its name;
- confidence-interval overlap is treated as evidence of equivalence, which it is not;
- several secondary analyses use only a single seed or a partial run set without making that limitation a hard failure;
- the final-results collector contains hard-coded values, broad exception suppression, and inconsistent fairness fields;
- the standalone synthetic generator can overwrite a replay path used for real Taobao data;
- the manuscript contains incomplete references and results whose provenance conflicts with the current filesystem;
- the repository tracks very large generated outputs, including invalid or superseded runs, while the directory described as authoritative is locally ignored and untracked;
- the existing `.gitignore` does not remove already tracked files from the index;
- there is no complete environment specification, CI system, public license, citation metadata, data acquisition manifest, reproducibility guide, or release certificate.

### 2.3 Immediate publication verdict

All numerical and comparative claims in the current README, manuscript, final-data notes, tables, and plots must enter **claim quarantine**. They may be used as historical expectations or regression clues, but not as paper evidence. In particular, the following must not be repeated as validated results until regenerated:

- the stated number of runs or seeds;
- exact processed-event counts;
- any assertion that adaptive and B-only variants are statistically indistinguishable;
- the reported controller-correlation value;
- burst, refresh, fairness, latency, throughput, AUROC, or accuracy improvements;
- oracle ceiling values;
- RALF comparisons;
- overhead percentages;
- any assertion that traces were recorded online;
- any claim of exact-once or loss-free termination.

Quarantine is not deletion. The old values should remain in a clearly labeled historical evidence archive with hashes and their known limitations so that the rehabilitation can detect and explain changes.

### 2.4 Meaning of “factory-made from the beginning”

The end product should have:

- the canonical factory governance boundary;
- clean founding documents that accurately describe the rehabilitated project;
- an ordered, reviewable chunk and contract history;
- a canonical source and artifact layout;
- evidence adjacent to verdicts;
- mechanically verifiable claim tiers and release checks;
- a clean publication export.

It must not pretend that the historical work was originally performed under Factory v2.2. The existing Git history should be preserved in the internal repository. If a pristine public repository is desired, it should be produced as a traceable release export from a certified internal commit, with the source commit and migration history recorded. Fabricating commits, authorship, dates, reviews, or past factory verdicts is prohibited.

---

## 3. Baseline evidence snapshot

The following snapshot should be copied into the first factory intake records and then refreshed mechanically. Sizes are approximate observations from the 2026-08-28 inspection.

| Area | Observed baseline | Rehabilitation implication |
|---|---|---|
| Git | Clean `main`, commit `37c85a6`, matching `origin/main`; no tags | Create an immutable migration baseline tag and bundle before moving files |
| Tracked files | Approximately 339 files | Every file needs an explicit disposition class |
| Git objects | About 1.07 GiB unpacked | Removing files from the current index will not shrink history; public-export strategy is separate |
| Raw data | About 3.7 GiB under `data` | Raw and restricted data must be externalized and checksummed |
| Results | About 8.6 GiB under `results` | Runs must move to immutable external artifact storage; only certified compact outputs belong in Git |
| Tracked results | Approximately 198 files, including large and superseded run CSVs | Current evidence authority is inverted and must be corrected |
| Factory attempt | `revised_software` uses Factory v1.0.1 | Preserve as migration evidence; do not treat its PASS reports as v2.2 certification |
| Build | CMake/C++17; build succeeds in existing environment | Capture exact toolchain; add clean presets and portable profiles |
| Tests | Nine of nine compiled tests pass | Retain as regression baseline; strengthen from permissive assertions to exact scientific contracts |
| Python environment | Scripts parse, but no locked dependency specification | Create deterministic environment and dependency/license inventory |
| CI | None found | Add build/test/sanitizer/reproducibility workflows |
| Data provenance | No complete checksummed acquisition manifest | Reality Gate cannot pass yet |
| Analysis evidence | Mixed generated, reconstructed, hard-coded, and partially suppressed results | Rebuild as fail-closed, schema-validated evidence pipeline |
| Paper | Incomplete outline and references; claims not fully traceable | Rewrite only after certified pilot and full run |
| Licensing | “All rights reserved pending paper submission” in README; no license file | Make an explicit code, data, model, and artifact licensing decision before public release |

### 3.1 Current artifact-authority inversion

One of the first migration facts to record is that `.gitignore` currently excludes broad result paths, but many files beneath those paths are already tracked. Consequently:

- invalid or superseded experiment sets such as broken/corrected stress runs are versioned;
- large result CSVs remain in Git despite ignore rules;
- a directory described as the authoritative five-seed primary run is ignored and untracked;
- an ignored run index is not guaranteed to accompany a clone;
- generated traces have schema and content differences between runs;
- a symlink selects one oracle-score version while nearby documentation and defaults refer to another.

This must be fixed through an index migration and artifact manifest. Editing `.gitignore` alone is not a solution.

---

## 4. Rehabilitation principles and governing invariants

The Factory v2.2 constitution remains authoritative. The project-specific founding documents should add the following invariants. Their identifiers should remain stable once accepted.

### 4.1 Repository and history invariants

**BP-INV-001 — One canonical implementation.** There is exactly one publication-bearing implementation of each runtime, operator, feature function, preprocessing rule, and analysis statistic. Historical duplicates may exist only in a labeled migration archive outside the publication build.

**BP-INV-002 — History is preserved honestly.** The internal Git history, migration baseline, and original artifacts are retained. A public clean export may omit historical debris, but it must identify its certified source revision and must not impersonate an original Factory history.

**BP-INV-003 — Generated and restricted material is not accidentally tracked.** Raw licensed data, local environments, build output, full experimental runs, caches, logs, temporary models, and manuscript intermediates are ignored and checked by a tracked-file policy test.

**BP-INV-004 — Every release artifact has provenance.** A committed table, figure, compact result, or model must identify its generator, source commit, configuration, input artifact IDs, schema version, and cryptographic checksum.

### 4.2 Runtime invariants

**BP-INV-005 — Accepted events terminate exactly.** For a successful run, every accepted event is either represented in a defined output or accounted for by an explicit, tested policy. Source completion, operator completion, queue draining, in-flight work, and tail-window flushing are separate lifecycle states.

**BP-INV-006 — No data races in supported configurations.** Cross-thread state uses defined synchronization. The debug and sanitizer profiles must detect no race, address, or undefined-behavior violation in their supported test workloads.

**BP-INV-007 — Declared architecture equals instantiated architecture.** Worker count, queue graph, operator placement, controller signal source, and scheduling mode are described by machine-readable configuration and checked against runtime metadata.

**BP-INV-008 — Failure is fail-closed.** Missing or invalid data, models, configuration, output paths, or required columns terminate the experiment with a nonzero status. No silent zero-model fallback, partial-seed continuation, broad exception suppression, or unknown-category coercion is permitted in publication runs.

**BP-INV-009 — Replication terminology is precise.** A seed changes a documented stochastic process. Identical deterministic repetitions are called repetitions, not seeds. Machine, thread, process, and trial identifiers are recorded independently.

### 4.3 Feature and oracle invariants

**BP-INV-010 — Online/offline feature parity.** Given the same ordered event fixture and precision policy, the C++ online path and the independent Python/reference path agree within a declared tolerance for every feature and emitted window.

**BP-INV-011 — Prediction time is explicit.** The event horizon, whether the current event is included, label window, censoring rule, per-user coverage rule, and ordering of tied timestamps are specified before preprocessing and enforced in tests.

**BP-INV-012 — Oracle scores are out of fold.** Any score called an oracle or used as a per-event target is produced without training, hyperparameter selection, scaling, or calibration on the scored observation or its prohibited temporal/user neighborhood. Fold assignments and fitted-model IDs are artifacts.

**BP-INV-013 — Dataset semantics are configuration, not filenames.** Dataset type, schema mapping, time unit, behavior encoding, label policy, feature definitions, and splits are explicit versioned configuration. Unknown values fail validation unless a declared mapping handles them.

**BP-INV-014 — Synthetic and real data cannot collide.** Synthetic fixtures have distinct directories, artifact IDs, metadata, and output paths. A generator cannot overwrite or masquerade as an acquired real-data replay.

### 4.4 Experimental and statistical invariants

**BP-INV-015 — Baselines receive symmetric treatment.** Each baseline has a faithful implementation, comparable resource budget, equivalent configuration search, identical data/split opportunities, and a recorded rationale. A surrogate is labeled as a surrogate and cannot be presented as the original system.

**BP-INV-016 — Evidence sets are complete or rejected.** Missing seeds, malformed rows, schema drift, NaNs, truncated traces, inconsistent source revisions, or incomplete run manifests cause the aggregation step to fail rather than skip.

**BP-INV-017 — The resampling unit matches dependence.** Statistical tests preserve the relevant dependence across time, users, runs, and paired architectures. Unit choice, block selection, estimand, multiplicity control, and power are preregistered.

**BP-INV-018 — Absence of significance is not equivalence.** Equivalence or non-inferiority claims require a prespecified practical margin and an appropriate interval/test. Confidence-interval overlap is never used as a substitute.

**BP-INV-019 — Every manuscript number is generated.** No result-bearing Markdown, LaTeX, CSV, or figure source contains manually copied or hard-coded final values. The manuscript imports certified generated macros/tables or is checked against them.

**BP-INV-020 — Claims stop when their gate fails.** A failed Reality Gate, correctness test, claim-tier check, Stop Condition, acquisition audit, or recomputation check blocks downstream publication use even if the numbers look favorable.

### 4.5 Research-claim tier

The likely headline BPFeat claim is comparative and potentially causal/robust: adaptive backpressure-guided feature allocation improves a defined quality/latency/throughput objective under workload stress. Under Factory v2.2, this should be treated as **T-CAUSAL** unless the manuscript is deliberately narrowed to descriptive observation. That means the programme must include at least three credible baselines, adversarial property testing, preregistered Stop Conditions, mechanical evidence and recomputation gates, and a tier check. Subsidiary implementation observations can remain T-DESC; comparative table rows are at least T-COMP.

---

## 5. Factory v2.2 adoption without destroying the existing project

### 5.1 Target governance boundary

The adopted workspace should use the Factory v2.2 boundary:

```text
Project AMOS/
├── bootstrap.sh                  # factory bootstrap entry point
├── factory/                      # exact pinned Factory v2.2 distribution; outer-Git ignored
├── project/                      # independent nested governance Git repository; outer-Git ignored
├── DROP_HERE/                    # role handoff inbox; ignored
├── TAKE_THIS/                    # role handoff outbox; ignored
├── source/                       # canonical publication-bearing implementation
├── tests/
├── configs/
├── scripts/
├── data/
├── models/
├── artifacts/
├── paper/
├── docs/
├── CMakeLists.txt
├── README.md
└── publication metadata
```

The outer repository contains the software and publication artifact. The nested `project/` repository contains the governance record: founding documents, chunks, contracts, reports, evidence references, decisions, and release certification. Factory machinery and governance internals are deliberately absent from the public outer index, while still existing locally and in the separately preserved governance repository.

### 5.2 How to source the factory

The read-only folder `/Users/adi/Downloads/factory_v2_2_0` is the immediate reference. Adoption must:

1. record its `VERSION` as 2.2.0;
2. compute a manifest and SHA-256 checksum for each copied factory file;
3. compare the copied paths to the supplied bootstrap manifest;
4. record whether the distribution corresponds to an upstream tag/commit, if that identity can be independently established;
5. copy only through a reviewed, idempotent adoption script;
6. prove that rerunning adoption fills missing factory files but never overwrites project-owned files;
7. keep the supplied download untouched.

The default bootstrap script's ability to clone a remote is not permission to use an unpinned network branch. If an upstream tag or release archive is later chosen, its digest must be pinned and the local distribution compared before replacement.

### 5.3 Status of the old Factory v1 attempt

`revised_software` is not the new canonical Factory workspace. It is a historical migration source containing:

- Factory v1.0.1 files;
- earlier project founding documents;
- Chunk 01 and Chunk 02 contracts and PASS reports;
- a duplicated `source/include/klstream/core` tree;
- useful proposed runtime behavior, including an exact-match wait facility absent from the current live root implementation.

The correct treatment is:

- hash and inventory it;
- compare every duplicated source file to the live root;
- extract decisions, invariants, tests, and patches as candidates;
- mark every old verdict as **legacy, non-transitive, and not v2.2-certified**;
- preserve the unmodified legacy records under a migration evidence area in the nested governance repository or an immutable external archive;
- port useful changes into the canonical source only through new v2.2 contracts and fresh verification;
- remove `revised_software` from the outer publication tree after preservation is verified.

The old documents' claims that the science was validated must not be carried forward. Their invariants are useful inputs, not evidence of satisfaction.

### 5.4 Founding documents before Chunk 1

Factory initialization and scientific review occur before the first implementation chunk. This is called the **Adoption Gate**, not Chunk 0, so that Chunk 1 genuinely begins with the existing project.

The nested `project/` repository must contain newly reviewed v2.2 versions of:

- `project_description.md` — problem, users, scientific question, artifact scope, non-goals;
- `architecture.md` — current architecture and target architecture, including known mismatches;
- `roadmap.md` — this plan expressed as factory chunks and decision gates;
- `project_knowledge.md` — terminology, datasets, metrics, algorithms, operational facts;
- `invariants.md` — the accepted BP invariants above plus Factory invariants;
- `venue_requirements.md` — verified current venue rules and deadlines;
- `key_facts.md` — compact facts with sources and confidence;
- `methodology_adversarial_review.md` — the pre-Chunk-1 scientific challenge.

Legacy founding documents may be cited and diffed, but must not simply be copied because several premises no longer match the live tree.

### 5.5 Methodology Adversarial Review gate

Before the Architect authors Chunk 1, the review must resolve or explicitly fail:

- authenticity and legal usability of each dataset;
- prediction target and time horizon;
- whether the headline contribution is sufficiently novel and venue-relevant;
- at least three defensible baselines and the cost of implementing them faithfully;
- statistical unit, feasible sample size, minimum detectable effect, and run budget;
- title-to-evidence alignment;
- assumption stress cases and adversarial workloads;
- negative-result contingency;
- feasibility of clean reproduction within resource constraints;
- comparison to at least three recent, relevant papers found through a documented literature search.

Any FAIL blocks Chunk 1 until the scope is narrowed or the method corrected. This is particularly important because the current paper outline and deadlines could otherwise encourage polishing invalid evidence.

### 5.6 Roles and workflow

Use only the v2.2 standing roles:

- **Architect:** owns founding truth, snapshots, contract boundaries, acceptance criteria, risk tier, claim tier, and verdict review;
- **Implementor:** modifies only allowed files, runs required verification, reports evidence and deviations, and does not self-expand scope;
- **Gatekeeper:** the provided script performs only its implemented mechanical checks. It is not a human reviewer and does not certify scientific truth.

For every contract:

1. Architect snapshots the repository and active chunk.
2. Architect writes a narrow contract with allowed files and executable acceptance criteria.
3. Implementor works only inside the contract scope.
4. Implementor records commands, return codes, inputs, outputs, checksums, and limitations.
5. Gatekeeper verifies/lints the contract and evidence where applicable.
6. Architect independently checks the diff and evidence and issues PASS, FAIL, or BLOCKED.
7. Reports are stamped only after the required recomputation declaration and tier checks.
8. The next contract starts only after the prior verdict is resolved.

Do not create all detailed future chunk contracts on day one. Factory practice should keep the long-range roadmap stable while authoring only the active chunk and its immediate contract in full detail. Later chunks must incorporate evidence learned earlier.

---

## 6. Canonical publication-facing repository layout

The following is the proposed end-state. Exact names can be adjusted in Chunk 1, but the separation of concerns is mandatory.

```text
Project AMOS/
├── CMakeLists.txt
├── CMakePresets.json
├── README.md
├── LICENSE
├── CITATION.cff
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── REPRODUCIBILITY.md
├── .gitignore
├── .gitattributes
├── source/
│   ├── include/klstream/
│   │   ├── core/
│   │   ├── operators/
│   │   ├── feature/
│   │   └── model/
│   ├── apps/
│   │   ├── bpfeat_run.cpp
│   │   └── bpfeat_harness.cpp
│   ├── preprocessing/
│   └── analysis/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── scientific/
│   ├── end_to_end/
│   └── fixtures/
├── configs/
│   ├── datasets/
│   ├── experiments/
│   ├── architectures/
│   └── schemas/
├── scripts/
│   ├── configure.sh
│   ├── test.sh
│   ├── acquire_data.sh
│   ├── prepare_data.sh
│   ├── train_oracle.sh
│   ├── run_experiment.sh
│   ├── aggregate.sh
│   └── reproduce_release.sh
├── environments/
│   ├── python lock/environment files
│   └── toolchain metadata
├── data/
│   ├── README.md
│   ├── manifests/
│   ├── schemas/
│   └── fixtures/
├── models/
│   ├── README.md
│   ├── manifests/
│   └── release/               # only small redistributable certified models
├── artifacts/
│   ├── README.md
│   ├── manifests/
│   ├── release/
│   │   ├── metrics/
│   │   ├── tables/
│   │   ├── figures/
│   │   └── logs/
│   └── schemas/
├── paper/
│   ├── manuscript.tex
│   ├── references.bib
│   ├── sections/
│   ├── figures/               # generated or copied from certified release artifacts
│   └── build instructions
└── docs/
    ├── architecture.md
    ├── methodology.md
    ├── datasets.md
    └── artifact_guide.md
```

Factory-local `factory/`, nested `project/`, `DROP_HERE/`, and `TAKE_THIS/` coexist in the working directory but remain ignored by the outer repository.

### 6.1 Layout rules

- `source/` is the only production implementation root. Root `include/`, `feature_flow/`, `analysis/`, and `preprocessing/` cease to be parallel canonical roots after the migration.
- Tests never import code from historical archives.
- Small deterministic fixtures are tracked; real raw datasets are not.
- Full runs are stored outside Git in content-addressed, immutable artifact storage.
- Only certified, compact, manuscript-used outputs are admitted under `artifacts/release/`.
- Paper figures are generated from, or byte-identical to, certified artifacts.
- Configuration is data. Dataset detection by filename is prohibited.
- Every executable supports a version/provenance mode that prints the source revision, build profile, configuration digest, and schema versions.
- Documentation that users need is in the outer repository. Internal prompts, role handoffs, and contract reports are in the nested governance repository.

---

## 7. File disposition and repository hygiene policy

Chunk 1 must assign every current tracked and important ignored file to exactly one of these classes.

| Class | Meaning | Destination |
|---|---|---|
| A — Canonical source | Builds or runs the release system | `source/`, `tests/`, `configs/`, `scripts/` |
| B — Publication metadata | Needed by users/reviewers | root, `docs/`, `paper/` |
| C — Small certified artifact | Direct evidence used by the manuscript | `artifacts/release/` with manifest |
| D — Reproducible fixture | Small test/reproduction input | `tests/fixtures/` or `data/fixtures/` |
| E — External immutable artifact | Raw/derived data, full runs, large models, detailed logs | DOI/object store with manifest and checksums |
| F — Governance record | Contracts, reports, decisions, internal review | nested `project/` repository |
| G — Historical migration evidence | old factory attempt, superseded scripts/results/prompts | nested migration archive or external immutable archive |
| H — Disposable local output | builds, caches, temporary logs, regenerated paper files | ignored; safely regenerable |
| I — Secret/restricted material | credentials, tokens, restricted source data | never committed; documented secure acquisition |

No file is removed from the index until its class, checksum, destination, and restoration method are recorded.

### 7.1 Proposed ignore policy

The final `.gitignore` should be concise, categorized, and paired with an allowlist/forbidden-file check. A likely policy is:

```gitignore
# OS and editors
.DS_Store
Thumbs.db
*.swp
*.swo
*~
.idea/
.vscode/

# Factory-local governance and handoffs
/factory/
/project/
/DROP_HERE/
/TAKE_THIS/

# C/C++ build products
/build*/
/cmake-build-*/
CMakeFiles/
CMakeCache.txt
compile_commands.json
CTestTestfile.cmake
Testing/
*.o
*.a
*.so
*.dylib
*.dll
*.exe

# Python environments and caches
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Local raw and derived data; keep documentation/manifests/fixtures
/data/raw/
/data/interim/
/data/processed/
/data/replay/generated/
!/data/README.md
!/data/manifests/
!/data/manifests/**
!/data/schemas/
!/data/schemas/**
!/data/fixtures/
!/data/fixtures/**

# Full experimental output; admit only certified compact release artifacts
/results/
/runs/
/artifacts/work/
/artifacts/staging/
/logs/
!/artifacts/README.md
!/artifacts/manifests/
!/artifacts/manifests/**
!/artifacts/schemas/
!/artifacts/schemas/**
!/artifacts/release/
!/artifacts/release/**

# Local models and checkpoints; allow explicitly reviewed release models
/models/work/
/models/checkpoints/
*.ckpt
*.pt
*.pth
!/models/README.md
!/models/manifests/
!/models/manifests/**
!/models/release/
!/models/release/**

# Paper intermediates
/paper/build/
/paper/*.aux
/paper/*.bbl
/paper/*.blg
/paper/*.fdb_latexmk
/paper/*.fls
/paper/*.log
/paper/*.out
/paper/*.synctex.gz

# Temporary and local profiling output
*.tmp
*.temp
*.trace.local
*.profraw
*.profdata
```

The exact allowlist order must be tested because Git ignore negation only works when parent directories remain traversable. The policy must not indiscriminately ignore all CSV/JSON files; schemas, fixtures, and compact certified results legitimately use those formats.

### 7.2 Index cleanup

After the disposition manifest is reviewed:

1. create the migration baseline tag and Git bundle;
2. copy or upload all Class E/G material and verify checksums;
3. use `git mv` for canonical source moves so history remains discoverable;
4. use targeted `git rm --cached <explicit-path>` only for files confirmed external/ignored;
5. never use a broad unresolved glob for destructive index changes;
6. run `git ls-files -ci --exclude-standard` and require an empty or explicitly allowlisted result;
7. run a tracked-file policy script that rejects files above a chosen limit, raw-data signatures, secrets, build output, and forbidden directories;
8. clone the migrated commit into a temporary clean directory and prove the build does not depend on ignored local material.

### 7.3 Large-file and history policy

Changing the current index does not remove the approximately gigabyte-scale objects from old Git history. The default plan is:

- preserve the internal repository and its history unchanged except for normal forward migration commits;
- create a clean publication repository/export from the final certified commit;
- include a machine-readable mapping from public release commit to internal certified commit, release tag, artifact manifest, and governance certificate;
- retain an offline Git bundle of the pre-migration repository.

History rewriting with `git filter-repo` is an optional, separately approved operation only if repository hosting constraints make it unavoidable. It requires an RFC, a tested clone, a protected archival bundle, remote-coordination plan, explicit human approval, and post-rewrite checksum verification. It is not part of the default rehabilitation because it is destructive and conflicts with the preservation spirit of the Factory constitution.

### 7.4 Data and run storage

For each large artifact, the manifest should include:

- artifact ID and semantic name;
- role: raw, derived, replay, fold assignment, model, run, trace, aggregate, or release output;
- origin URL/provider and acquisition date;
- license and redistribution status;
- byte size and SHA-256 checksum;
- compression and unpacked checksum where relevant;
- schema and row count;
- generator command and source revision for derived artifacts;
- parent artifact IDs;
- retention location and access procedure;
- whether the artifact is required for minimal tests, full reproduction, or only audit.

Prefer a DOI-bearing archive for release evidence and an institutional/object store for working runs. Never use “latest” as an artifact identifier.

---

## 8. Venue and scope gate

The previous target list is stale and must be replaced with verified requirements.

- The official [IEEE BigData 2026 important-dates page](https://bigdataieee.org/BigData2026/important-dates/) lists the main full-paper deadline as **2026-08-21**, which is already past as of this plan. Its [paper call](https://bigdataieee.org/BigData2026/calls/papers/) limits regular papers to ten pages including references and disallows an appendix. The rehabilitation must not be rushed into a closed deadline.
- The official [ICDE 2027 important-dates page](https://icde2027.github.io/important-dates.html) lists Round 2 submissions for **2026-11-11**. The [research-paper call](https://icde2027.github.io/cf-research-papers.html) includes data streams, event processing, benchmarking, and provenance among relevant areas. The [submission guidelines](https://icde2027.github.io/submission-guidelines.html) impose format, artifact, category, and disclosure requirements, including expected supplemental material and mandatory artifacts for the Experiments and Analysis category.
- An official ICDCS 2027 call was not located during this review. Its deadline, categories, page limit, artifact rules, and AI-disclosure rules remain **UNKNOWN** until an official 2027 source exists.

ICDE 2027 Round 2 is only a conditional target. From 2026-08-28 to 2026-11-11 there are roughly seventy-five calendar days. It should be selected only if the Adoption Gate, runtime correctness, data Reality Gate, pilot power analysis, and baseline feasibility all pass early enough to leave time for independent reproduction and writing. Otherwise, choose the next appropriate venue rather than lowering the evidence standard.

The venue decision record must answer:

1. Is BPFeat primarily a research-paper contribution, an experiments-and-analysis contribution, or an artifact/system contribution?
2. Does the evidence support the title and abstract at the selected claim tier?
3. Can the page limit accommodate the mechanism, validation, threats, and statistical design without hiding essential material?
4. Can data and artifacts be supplied under the venue's review and anonymity rules?
5. What AI-assistance disclosure is required for code, text, figures, or review preparation?

---

## 9. Roadmap overview

The programme has an Adoption Gate followed by twelve chunks. Chunk boundaries are evidence boundaries, not calendar sprints.

| Phase | Purpose | Exit gate |
|---|---|---|
| Adoption Gate | Install pinned v2.2 governance around the existing repo; write truthful founding docs and adversarial review | Factory self-check, founding review, MAR PASS |
| Chunk 01 | Existing-project intake, provenance freeze, canonical layout, and Git hygiene | Clean-clone structural parity and complete disposition manifest |
| Chunk 02 | Runtime lifecycle, exact completion, concurrency, and instrumentation correctness | Exact-count/failure/sanitizer contracts pass |
| Chunk 03 | Feature semantics and independent online/offline parity | Golden semantic corpus passes across implementations |
| Chunk 04 | Data acquisition, preprocessing, labels, and out-of-fold oracle | Reality Gate and leakage audit pass |
| Chunk 05 | Architecture registry, faithful baselines, and experiment configuration | Topology/budget/baseline parity audit passes |
| Chunk 06 | Statistical estimands, evidence schemas, and analysis pipeline | Known-answer, resampling, completeness, and tier-evidence tests pass |
| Chunk 07 | Reproducible environments, CI, portability, security, and packaging | Clean-machine matrix and policy checks pass |
| Chunk 08 | Preregistered pilot and falsification campaign | Stop Conditions, variance, power, and feasibility decision |
| Chunk 09 | Frozen full experiment | Immutable complete run manifest and recomputable aggregates |
| Chunk 10 | Manuscript and artifact narrative | Every claim linked to certified evidence; internal red-team PASS |
| Chunk 11 | Independent reproduction and Factory release certification | Independent clean reproduction and scoped release certificate |
| Chunk 12 | Public release export and submission package | Public clone, archive, DOI, metadata, and submission checklist PASS |

Dependencies are strict unless a later contract explicitly proves independence. Full experiments cannot begin before the Reality Gate, semantic parity, baseline parity, and frozen statistical plan. Manuscript prose may be outlined earlier, but numerical claims cannot be filled from quarantined results.

---

## 10. Adoption Gate — prepare Factory v2.2 and challenge the method

### 10.1 Objective

Create a verified, non-destructive Factory v2.2 governance environment around the current repository and determine whether the proposed research question is feasible before spending effort reorganizing or rerunning it.

### 10.2 Required actions

1. Capture the current outer-repository commit, branch, remotes, status, submodules, tags, tracked-file list, ignore status, object statistics, tool versions, file sizes, and checksums of irreplaceable artifacts.
2. Create a signed or annotated migration baseline tag such as `pre-factory-v2.2-adoption-2026-08-28` after confirming the tree is clean.
3. Create and verify a Git bundle of all refs in a location outside the working tree.
4. Build an adoption script from the v2.2 bootstrap manifest that copies the factory reference without modifying the supplied download and without overwriting project files.
5. Initialize the nested `project/` governance repository and ignore Factory-local paths in the outer repository.
6. Import the old v1.0.1 records into a read-only migration evidence directory with a checksum/index; do not import their verdicts as active reports.
7. Write the eight founding/review documents listed in Section 5.4.
8. Conduct the Methodology Adversarial Review with explicit PASS/FAIL for authenticity, leakage, baselines, power, novelty, venue fit, stress assumptions, and negative-result plan.
9. Record a decision on provisional venue and scientific claim tier.
10. Run only the Gatekeeper checks that actually exist and record their precise scope. Do not describe a script self-check as scientific validation.

### 10.3 Required evidence

- Factory distribution checksum manifest;
- outer-repository baseline snapshot;
- verified Git bundle receipt;
- legacy v1 evidence inventory;
- nested governance repository initial commit;
- founding-document review record;
- Methodology Adversarial Review;
- venue decision and claim-tier declaration;
- factory self-check output and limitations.

### 10.4 Stop Conditions

Stop before Chunk 1 if:

- the original repository cannot be restored byte-for-byte from the bundle/tag;
- dataset origin or legal usage is irrecoverably unknown;
- no defensible prediction target can be stated without leakage;
- fewer than three credible baselines can be implemented for the intended T-CAUSAL claim;
- the expected experimental cost cannot support meaningful power;
- the claimed contribution does not fit a plausible venue after literature review;
- adoption would overwrite existing project-owned files.

The response to a Stop Condition is to narrow or reformulate the research question, not to weaken the gate.

---

## 11. Chunk 01 — existing-project intake and canonicalization

### 11.1 Chunk statement

Chunk 1 begins with the existing Project AMOS repository exactly as frozen by the Adoption Gate. Its job is to make the repository structurally factory-native while preserving every useful or evidentially important legacy item. It deliberately avoids changing algorithm semantics except where a minimal build-path adjustment is required by file moves.

**Risk tier:** High, because it moves a large repository and changes evidence authority.  
**Scientific claim tier:** T-DESC only; this chunk makes no performance or correctness claim beyond reproducible inventory and build continuity.

### 11.2 Proposed contracts

#### C01.01 — Baseline and disposition inventory

Produce a machine-readable inventory of every tracked file and every important ignored file. Fields include path, size, hash, Git status, last modifying commit, inferred role, proposed disposition class, destination, license sensitivity, and whether any code or paper references it.

Acceptance criteria:

- every tracked file has exactly one disposition;
- all files over the policy size threshold are reviewed manually;
- symlinks and their targets are recorded;
- the supposed authoritative and superseded result directories are explicitly identified;
- references from README, CMake, scripts, paper, and analysis to moved paths are enumerated;
- no file is deleted or untracked in this contract.

#### C01.02 — Legacy v1 differential archive

Compare `revised_software/source` to the live implementation path by path. Extract unique tests, runtime ideas, exact-completion patches, documents, and reports into an indexed archive. Record whether each difference is candidate, obsolete, contradicted, or already integrated.

Acceptance criteria:

- all duplicate code has a diff classification;
- old Factory PASS verdicts are visibly marked legacy/non-transitive;
- useful exact-completion work is turned into a Chunk 02 input, not silently merged;
- the legacy tree can be restored from the archive checksum;
- no production build includes the archive.

#### C01.03 — Canonical tree migration

Move, primarily with `git mv`, the live implementation into `source/`, tests into typed subdirectories, scripts into their owned domains, and publication documentation into the target structure. Introduce root build compatibility so normal users still configure from the repository root.

Acceptance criteria:

- there is one canonical definition of every compiled class and executable;
- no root build imports `archive/`, `revised_software/`, old prompts, or old audits;
- a clean debug build and the nine baseline tests still pass after moves;
- Python entry points resolve paths through the project root/configuration rather than the caller's current directory;
- README links resolve and no publication documentation depends on an ignored prompt;
- file moves are reviewable and algorithmic diffs are either absent or separately explained.

#### C01.04 — Artifact externalization and index hygiene

Copy full datasets, runs, traces, large models, and historical evidence to their approved immutable storage; verify checksums; add manifests; then remove only the approved paths from the outer Git index. Establish `data/`, `models/`, and `artifacts/` README files and tracked manifest/schema/fixture allowlists.

Acceptance criteria:

- every removed indexed artifact has a verified external copy and restoration command;
- raw licensed data is not in the publication index;
- invalid/superseded runs are not presented as release evidence;
- the current “authoritative” local run is preserved but explicitly remains untrusted historical evidence;
- `git ls-files -ci --exclude-standard` is empty or contains only documented exceptions;
- no tracked file exceeds the chosen limit without an approved exception;
- a secret scan and data-signature scan pass on the index;
- repository size in a new public-style clone is measured and documented.

#### C01.05 — Build, environment, and entry-point baseline

Create the minimum deterministic development setup needed for later chunks: CMake presets, Python environment declaration and lock strategy, standardized commands, version output, and a test fixture path independent of local data.

Acceptance criteria:

- `cmake --preset dev`, build, and `ctest` equivalents work from a fresh clone using documented prerequisites;
- Python dependencies are versioned and installable without reading undeclared global packages;
- the baseline tests use only tracked fixtures;
- an environment report captures compiler, CMake, Python, OS, CPU architecture, and dependency versions;
- release experiments remain disabled until later gates.

#### C01.06 — Structural policy automation

Add checks for forbidden tracked paths, duplicate canonical symbols/files, oversized files, unresolved symlinks, broken documentation links, accidental generated output, and missing artifact manifests.

Acceptance criteria:

- intentionally planted forbidden-file fixtures make the checker fail in its own test;
- checks run locally with one documented command;
- the checker distinguishes source CSV/JSON fixtures from full generated results;
- no broad “ignore all data formats” rule is used.

#### C01.07 — Chunk audit and migration report

Reclone the migrated tree into a temporary clean directory, run all structural checks, build and test it, restore one external artifact by manifest, and compare baseline behavior where semantic changes were not intended.

Acceptance criteria:

- the clean clone does not access old absolute paths;
- the build/test baseline is no worse than at intake;
- all path references and manifests are valid;
- the outer diff, nested-governance diff, and externalization receipts are reviewed;
- the Architect issues an explicit Chunk 01 verdict.

### 11.3 Files to keep out of the public tree

Subject to the disposition manifest, the public tree should not retain:

- `revised_software` as a second implementation/factory;
- archived prompts, chat-like build prompts, ad hoc audit prompts, and patch transcripts;
- compiled build trees;
- raw UserBehavior/credit-card datasets;
- full replay/oracle data too large for a minimal fixture;
- full experiment run CSVs and exploratory traces;
- broken, corrected, superseded, or alternative runs outside a historical artifact archive;
- local classifier weights without a model manifest;
- caches, logs, OS metadata, and temporary paper output.

“Keep out” means preserve appropriately, untrack, and ignore—not erase without evidence.

### 11.4 Chunk 01 exit gate

Chunk 01 passes only when a reviewer can clone the outer repository, see one coherent implementation, install/build/test it using tracked instructions and fixtures, find no unexplained large/generated files, recover external artifacts through manifests, and trace every legacy item to a documented disposition. Passing Chunk 01 does **not** authorize reuse of old performance numbers.

---

## 12. Chunk 02 — runtime lifecycle and concurrency correctness

### 12.1 Objective

Replace heuristic shutdown and ambiguous architecture wiring with a formally specified, testable runtime lifecycle. Establish exact accounting before changing feature science.

**Risk tier:** Critical.  
**Claim tier:** T-DESC for correctness properties; any loss-free/exactness claim requires adversarial property evidence.

### 12.2 Required design decisions

- Define event states: offered, accepted, rejected, queued, in-flight, transformed, buffered in a partial window, emitted, consumed, failed, and cancelled.
- Define the end-of-stream protocol. Preferred options are explicit close propagation plus operator completion futures/barriers, not polling queue emptiness.
- Define tail-window behavior: flush partial, pad, or discard. If discard is scientifically intended, it must be explicit in counts and identical across architectures.
- Define per-operator ownership, worker placement, scheduling policy, and completion state.
- Define what output cardinality each operator promises.
- Define controller sampling frequency and the exact queue/signal that represents downstream pressure.
- Define error propagation and nonzero exit behavior.

### 12.3 Proposed contracts

#### C02.01 — Runtime state machine and accounting contract

Write the lifecycle state machine and conservation equations before code changes. Include window cardinality equations for complete and partial windows.

Required properties include:

```text
accepted = processed + explicitly_failed + explicitly_cancelled
processed inputs -> expected windows under the declared tail policy
successful run -> all operators completed and no in-flight work remains
```

#### C02.02 — Exact completion implementation

Port only the useful idea from the old `wait_until_matched` work after independent review. Implement close/drain/completion semantics across all queues and operators. Remove fixed-duration empty-queue polling as the correctness mechanism.

Tests must include zero events, one event, `W-1`, `W`, `W+1`, multiple windows, slow consumers, full queues, randomized scheduling, and injected operator failure.

#### C02.03 — Concurrency repair

Replace the non-atomic `source_done` communication, audit all cross-thread fields, and ensure object lifetime outlives workers. Add ThreadSanitizer tests on a supported platform and deterministic stress loops.

#### C02.04 — Architecture topology repair

Ensure the harness instantiates exactly the declared workers and queues. Remove idle duplicate worker creation. Emit a topology manifest at runtime and test it against the architecture configuration.

#### C02.05 — Failure and accounting behavior

Make model-load, dataset, configuration, output, and schema failures fatal. Report actual accepted, processed, emitted, and dropped counts; never set “events processed” from input rows without validating the sink.

#### C02.06 — Native trace instrumentation

Wire the adaptive operator's trace sink directly to controller decisions. Version the trace schema. Record monotonic timestamps, input/output occupancy, selected window/action, controller state, and architecture/run IDs. Delete “reconstructed trace” from the evidentiary path; if retained as a diagnostic tool, label its output synthetic/derived and never as observed control behavior.

Instrumentation overhead must be measured by paired enabled/disabled runs and reported separately from controller overhead.

#### C02.07 — Runtime adversarial test suite

Use deterministic and schedule-randomized workloads with queue saturation, delayed consumers, burst transitions, failure injection, and repeated start/stop. Add ASan/UBSan and TSan profiles; record platform limitations where sanitizers cannot be combined.

### 12.4 Required verification

- exact count and exact window count for all seven configured architectures;
- native trace row count and state transition checks;
- no race report in supported TSan jobs;
- no ASan/UBSan finding;
- topology manifest equals configured graph;
- nonzero exit and no result artifact on injected required-input failures;
- 100+ repeated small stress executions without count variability;
- clean teardown with no detached work or post-destruction access.

### 12.5 Stop Conditions

Stop the research pipeline if exact accounting cannot be achieved without materially redefining the architecture, or if the control signal is proven not to represent the downstream bottleneck described in the research claim. In that case, update the architecture and contribution before proceeding.

---

## 13. Chunk 03 — feature semantics and online/offline parity

### 13.1 Objective

Define BPFeat features independently of either implementation, then prove the C++ streaming computation and Python/reference computation implement that definition.

**Risk tier:** Critical.  
**Claim tier:** T-DESC correctness prerequisite.

### 13.2 Semantic specification

For every feature, document:

- name, type, unit, range, missing value, and numerical precision;
- event fields consumed;
- state initialization;
- update equation;
- inclusion of the current event;
- behavior for equal/out-of-order timestamps;
- reset/session/window policy;
- output point and output cardinality;
- dataset-specific mapping, if any;
- tolerances and overflow behavior.

### 13.3 Known issues to resolve

- Do not store epoch-scale nanoseconds in a `float` before deriving sub-minute gaps. Prefer integral nanoseconds or relative `double` seconds with an explicit origin.
- Align Taobao behavior-code mapping across preprocessing, reference code, and C++.
- Align ULB semantics: the current Python offline logic derives buy/pv-like behavior from amount while the live C++ path supplies a single behavior code. Decide whether these features are meaningful for ULB, replace them, or configure them explicitly; do not claim parity while they differ.
- Specify stable ordering for tied timestamps and user interleaving.
- Decide whether partial windows emit features and how their denominators are calculated.
- Treat numerical precision and tolerance as part of the artifact, not an ad hoc test choice.

### 13.4 Proposed contracts

#### C03.01 — Dataset-independent feature specification

Author formulae and examples for every feature. Review them without reference to existing code to avoid blessing accidental behavior.

#### C03.02 — Golden semantic corpus

Create small, hand-auditable fixtures covering first event, repeated events, purchases, non-purchases, same timestamps, large epoch timestamps with small gaps, inactivity, multiple users, out-of-order input, unknown behavior, partial windows, and dataset boundaries. Include expected per-event state and per-window output.

#### C03.03 — Independent reference implementation

Implement a simple correctness-first reference with no shared production feature code. It should prioritize clarity and exact expected behavior over speed.

#### C03.04 — C++ alignment

Change the production feature code to satisfy the specification and golden corpus. Use dataset configuration rather than filename inference.

#### C03.05 — Cross-language differential testing

Generate deterministic valid event sequences and adversarial edge cases; compare C++ and reference output at every emitted point. Minimize failing cases and store them as fixtures.

#### C03.06 — RALF surrogate semantic audit

Investigate duplicate user IDs in collected keys, ranking/emission behavior, coverage/fairness consequences, and budget semantics. Implement an independent small reference. Rename the baseline to `RALF-inspired surrogate` unless fidelity to the cited algorithm is demonstrated.

### 13.5 Exit gate

- all golden cases agree;
- randomized differential cases agree under declared tolerances;
- ULB and Taobao each have explicit schema and behavior mappings;
- unknown categories fail as designed;
- timestamp precision tests preserve relevant gaps;
- any deviation from a cited baseline is named in code, tables, and manuscript.

---

## 14. Chunk 04 — data provenance, preprocessing, labels, and oracle

### 14.1 Objective

Create a legally traceable, deterministic, leakage-resistant pipeline from acquired data to replay events, labels, folds, models, and out-of-fold oracle scores. Pass the Factory Reality Gate before model training is accepted as evidence.

**Risk tier:** Critical.  
**Claim tier:** T-DESC for dataset facts; T-COMP/T-CAUSAL prerequisite for downstream claims.

### 14.2 Acquisition and authenticity

For each dataset:

- identify the original provider and canonical download page;
- record exact acquired filename, size, checksum, and acquisition time;
- record license/terms and whether redistribution is permitted;
- preserve provider documentation and schema citation;
- document any manual steps;
- verify representative rows against provider documentation;
- distinguish raw bytes from every derived representation.

The current local filenames alone are not provenance.

### 14.3 Prediction and label protocol

Before implementing preprocessing, preregister:

- prediction entity and event;
- prediction timestamp;
- whether features include the event at the prediction timestamp;
- future horizon and label condition;
- strict/inclusive time boundaries;
- censoring and dataset-end handling;
- per-user coverage requirements;
- train/validation/test separation unit: time, user, or both;
- treatment of repeated purchases and tied events.

The existing `<=` relationship between feature events and buy timestamps requires special scrutiny. If the current purchase both updates the feature and makes the label positive, either redefine the task transparently or change the boundary so the model predicts genuinely future behavior.

### 14.4 Proposed contracts

#### C04.01 — Acquisition manifest and schema validation

Create `data_manifest.json` and `acquisition_provenance.json` using versioned schemas. Validate checksums, columns, units, domains, row counts, time range, duplicate behavior, and missingness.

#### C04.02 — Reality Gate

Perform the factory-required human spot check after preprocessing logic is drafted and before model training. Randomly select raw records and trace them through normalized events and labels by hand. Record reviewer identity, sample selection method, discrepancies, and verdict.

#### C04.03 — Deterministic preprocessing DAG

Build immutable stages—raw, normalized, ordered, labeled, replay, folds—with parent hashes. Never overwrite an existing artifact ID. Make rerunning the same stage byte-identical or document unavoidable metadata differences separately.

#### C04.04 — Synthetic-data separation

Move synthetic generation to a fixture/workload namespace, require an explicit seed, record generator version/configuration, and prohibit any output under real-data artifact paths. Add a guard test proving that real replay files cannot be overwritten.

#### C04.05 — Split and fold manifest

Define temporal/user leakage boundaries and produce immutable fold assignments. Include reason for exclusions and class balance per fold. All later training consumes these assignments rather than choosing a new random split internally.

#### C04.06 — Out-of-fold oracle training

For each outer fold, fit scaling, feature selection, hyperparameter selection, calibration, and model only on permitted training data. Score held-out observations only. If nested validation is needed, its assignments are recorded. Combine held-out scores in original event order and prove each row was scored by a model that did not train/select on it.

#### C04.07 — Oracle integrity and model manifests

Each model manifest records fold, training data IDs, configuration, dependency versions, coefficients/weights checksum, metrics, and scored row range. Remove ambiguous `classifier_weights.txt` and alpha-named symlink authority in favor of explicit model/oracle artifact IDs.

#### C04.08 — Data quality and leakage tests

Tests include deliberate future leakage, current-event leakage, duplicate-user split leakage, shuffled labels, timestamp perturbation, missing schema values, unknown behaviors, fold overlap, and corrupted artifacts. The pipeline must fail these tests.

### 14.5 Reality Gate exit criteria

- authentic source and legal-use record for every dataset;
- checksummed deterministic derived artifacts;
- hand-checked raw-to-label examples;
- no train/validation/test or time-horizon leakage under the declared task;
- complete fold and model manifests;
- every event score out of fold;
- synthetic and real artifact namespaces mechanically separated;
- baseline prevalence, class balance, and oracle metrics recomputable from manifests.

If the oracle cannot achieve stable, meaningful held-out discrimination, stop and reconsider whether oracle-derived feature quality is a defensible dependent variable.

---

## 15. Chunk 05 — architecture registry, baselines, and experiment harness

### 15.1 Objective

Make every architecture a named, machine-readable, independently testable configuration and prove that comparisons are faithful and resource-symmetric.

**Risk tier:** High.  
**Claim tier:** T-COMP/T-CAUSAL preparation.

### 15.2 Architecture registry

Each architecture configuration must record:

- canonical ID and display name;
- implementation class/strategy;
- worker and queue graph;
- window policy and adaptive actions;
- controller parameters;
- resource budget;
- rate/burst source parameters;
- model and data artifact IDs;
- instrumentation settings;
- stochastic parameters and seed semantics;
- expected invariants;
- baseline citation and fidelity status.

Unknown architecture IDs must fail. The current behavior where an unrecognized value can fall into an adaptive branch must be removed.

### 15.3 Baseline policy

The final comparison set should contain at least three credible baselines selected by the adversarial review. Candidate categories include:

- fixed-window/static allocation;
- backpressure-only without feature adaptation;
- a rate-throttle/load-shedding policy that is actually enabled and tested;
- a faithful literature baseline or transparently named inspired surrogate;
- an oracle/static upper-bound policy where scientifically legitimate.

Fixed and throttle configurations must not execute the same branch unless that equivalence is the explicitly tested null. Rate-throttle initialization and recovery semantics—including the currently unset original rate—must have exact tests.

### 15.4 Proposed contracts

#### C05.01 — Harness decomposition

Separate configuration parsing, data loading, topology construction, execution, measurement, and result writing. Replace filename inference and branch-heavy implicit defaults with schema-validated configuration.

#### C05.02 — Baseline fidelity tests

For every baseline, create a small workload with an expected behavioral signature. Verify throttle activation/recovery, fixed-window constancy, B-only behavior, adaptive action, and surrogate budget/ranking.

#### C05.03 — Resource symmetry

Record and equalize worker count, CPU affinity policy, queue capacity, memory budget, warm-up, measurement interval, input workload, model, and instrumentation. Any deliberate asymmetry must be part of the research question and reported.

#### C05.04 — Seed and repetition semantics

Inventory every source of randomness. Route the explicit seed through all stochastic components. If execution is deterministic but scheduling varies, call trials repetitions and record scheduling/environment metadata. Add a reproducibility test for same-seed behavior and a diversity test where different seeds should differ.

#### C05.05 — Result and trace schemas

Define versioned schemas with mandatory run ID, config hash, source commit, build hash, data/model IDs, trial/seed, host metadata, timing clocks, counts, units, and completion status. Writers use atomic staging/finalization so incomplete runs cannot look complete.

#### C05.06 — Experiment orchestrator

Create a resumable orchestrator that enumerates the frozen run matrix, uses unique content-derived run IDs, captures stdout/stderr/return code, validates output, and refuses to aggregate incompatible versions. It must never overwrite an existing completed run.

### 15.5 Exit gate

- every named architecture produces the expected topology manifest and behavioral signature;
- throttle is demonstrably distinct from fixed;
- baseline search/budget opportunities are symmetric;
- seeds/repetitions are correctly named and recorded;
- results contain actual sink/event/window counts;
- partial or failed runs cannot enter aggregation;
- architecture table can be generated from registry metadata rather than handwritten prose.

---

## 16. Chunk 06 — statistical plan and evidence pipeline

### 16.1 Objective

Define estimands and dependence-aware analyses before new full experiments, implement them as fail-closed code, and make every result mechanically traceable.

**Risk tier:** Critical for publication.  
**Claim tier:** T-COMP/T-CAUSAL.

### 16.2 Statistical design questions

For each research question, preregister:

- population and workload regime;
- treatment/architecture contrast;
- primary outcome and unit;
- direction and practical effect threshold;
- paired structure;
- run/user/time dependence;
- estimator;
- confidence interval or hypothesis/equivalence test;
- block/cluster choice and selection rule;
- number of independent runs and power rationale;
- multiplicity/family definition;
- exclusions and missing-data behavior;
- sensitivity analyses;
- Stop Condition.

### 16.3 Required correction of the current analysis

The current bootstrap implementation must not be retained merely under a new name. It presently averages across runs by sequence before resampling, which can remove between-run variation. Its blocks and reported block length also require semantic review. The new implementation must be validated against known-answer simulations and an independently implemented reference.

Event sequence alone may not be the correct dependence unit when events are clustered by user and time. Candidate designs include paired run-level contrasts with a hierarchical/user-time bootstrap, cluster-robust analysis, or another method justified for the actual sampling process. The method must be chosen after data structure inspection, not because it produces narrow intervals.

### 16.4 Proposed contracts

#### C06.01 — Estimand and analysis specification

Write one analysis card per claim. Distinguish descriptive, superiority, non-inferiority, and equivalence questions. Define the smallest effect of practical interest.

#### C06.02 — Evidence schema and lineage graph

Define schemas for run manifest, per-event/per-window measurement, trace, aggregate, statistical result, table, figure, and claim. A claim record references evidence IDs; evidence references parent IDs and generator code.

#### C06.03 — Completeness validator

Require exact planned run IDs, row counts, schema versions, source/config/data/model hashes, success status, and trace availability. Replace broad `except: pass` patterns with typed failures. Missing seeds or malformed files make the evidence set ineligible.

#### C06.04 — Validated statistical implementation

Implement the selected paired/dependence-aware method. Add deterministic simulations with known null, known effect, autocorrelation, cluster effects, unequal run variance, missing run, and degenerate input. Compare a small case to an independent implementation.

#### C06.05 — Metric definitions

Define throughput, latency percentiles, quality loss, refresh, burst recovery, fairness, controller responsiveness, and overhead precisely. Prevent label confusion such as storing a fairness gap under a Jain index name. State valid ranges and assert them.

#### C06.06 — Equivalence and negative-result logic

If the intended claim is “no meaningful degradation” or “indistinguishable,” define and justify an equivalence margin and use an equivalence/non-inferiority procedure. Record negative results faithfully; do not translate non-significance into sameness.

#### C06.07 — Generated tables, figures, and manuscript macros

Replace the hard-coded final-results collector with schema-driven generation. Every displayed number comes from validated aggregates. Include oracle AUROC and other required audit columns if used. Tables should carry evidence manifest IDs in machine-readable metadata.

#### C06.08 — Factory evidence and recomputation integration

For T-COMP/T-CAUSAL contracts, declare required commands, run contract verification and linting, produce the recomputation declaration, stamp reports, verify stamps, and run the tier check. Record exactly what each Gatekeeper command verifies.

### 16.5 Exit gate

- all primary analyses are preregistered before the pilot decision is interpreted;
- known-answer and sensitivity tests pass;
- planned missing/corrupt input makes aggregation fail;
- metric names, ranges, and units are schema-enforced;
- equivalence language is supported by an equivalence design;
- no final number is hard-coded or manually copied;
- claim-to-run lineage is traversable and recomputable.

---

## 17. Chunk 07 — reproducible build, CI, portability, security, and packaging

### 17.1 Objective

Make correctness and reproduction routine on clean environments rather than properties of one developer machine.

**Risk tier:** High.  
**Claim tier:** T-DESC artifact claims.

### 17.2 Build profiles

Provide explicit CMake presets rather than globally forcing optimization flags:

- `dev-debug` — assertions, warnings, debug symbols;
- `release` — documented optimization and reproducible metadata;
- `asan-ubsan` — address/undefined behavior;
- `tsan` — thread sanitizer where supported;
- optionally `coverage` and `benchmark` with distinct semantics.

Treat warnings as errors in owned code for CI, while isolating external warnings if dependencies are later added. Add install/export/package behavior only if it aids artifact use; do not overengineer a library distribution that the paper does not need.

### 17.3 Portability

Test at least the platforms the artifact claims to support. At minimum, use Linux x86-64 for likely reviewer reproduction and the current macOS/Apple Silicon development host if it remains supported. Audit:

- cache-line assumptions, especially a blanket 128-byte aarch64 choice;
- Apple-specific QoS and non-Apple fallback behavior;
- clock semantics and time units;
- filesystem paths and symlinks;
- compiler-specific atomics and warning flags;
- pthread linkage and affinity capabilities.

Platform-dependent behavior must be explicit in metadata and limitations.

### 17.4 Proposed contracts

#### C07.01 — Dependency and environment lock

Choose a supported Python locking mechanism, record system dependencies, create an SBOM/dependency inventory, and document exact setup. Verify from a clean environment.

#### C07.02 — CI matrix

Run format/lint, policy checks, C++ build/test, Python unit tests, golden parity, ASan/UBSan, TSan where supported, documentation links, artifact schema tests, and a tiny end-to-end reproduction. Cache only performance-neutral dependencies.

#### C07.03 — Test hardening

Replace bare `assert`-only executables where necessary with diagnostics and exact expectations. Expand integration coverage from permissive lower bounds such as “at least 100 outputs” to exact contract counts. Ensure all seven architectures are tested.

#### C07.04 — Security and failure-path review

Run secret scanning, dependency vulnerability review, unsafe path/command review, malformed input tests, output overwrite tests, and resource exhaustion checks. No untrusted configuration should produce arbitrary path traversal.

#### C07.05 — License and citation package

Decide and document code license; audit copied/adapted code; document dataset/model licenses; create `CITATION.cff`, contributor guidance, security policy, and third-party notices. “All rights reserved pending submission” is not a publication artifact license strategy.

#### C07.06 — One-command minimal reproduction

From a clean clone and tracked fixture, produce a small validated result, aggregate, table, and figure using a single documented top-level command. This is not the full paper run but tests the complete DAG.

### 17.5 Exit gate

- clean CI passes on the supported matrix;
- sanitizer findings are zero or explicitly blocked by a documented tool false positive reviewed by the Architect;
- test failures are diagnostic and deterministic;
- setup is reproducible without undeclared global state;
- license and redistribution status are explicit;
- minimal reproduction produces the expected artifact hashes or semantically identical declared outputs.

---

## 18. Chunk 08 — preregistered pilot and falsification campaign

### 18.1 Objective

Use a small, bounded run to test the entire scientific protocol, estimate variance and cost, attack assumptions, and decide whether the full experiment is justified. The pilot is not a convenient source of final numbers unless its inclusion was preregistered and statistically appropriate.

**Risk tier:** Critical.  
**Claim tier:** T-CAUSAL gate.

### 18.2 Freeze before running

Freeze and checksum:

- research questions and claim cards;
- primary and secondary metrics;
- architectures/baselines;
- datasets, folds, models, and workload configs;
- seed/repetition schedule;
- statistical methods and practical margins;
- exclusion rules;
- Stop Conditions;
- maximum run budget and adaptation rule after pilot.

### 18.3 Adversarial workloads

Include at least:

- steady low load;
- steady saturation;
- abrupt burst and recovery;
- repeated bursts;
- slow downstream scorer;
- different queue capacities;
- skewed user/key distribution;
- drift or behavior mix change;
- adversarial ordering/ties where valid;
- configurations where adaptation should provide no benefit;
- configurations where an overly aggressive controller should fail.

### 18.4 Pilot questions

- Do exact counts and completion invariants hold at realistic scale?
- Is the native trace complete and causally ordered?
- Does the control action respond to the configured pressure signal rather than an unrelated queue?
- Is the proposed metric sensitive to the intended mechanism?
- Are baseline behaviors visibly distinct and faithful?
- What is between-run and within-run variance?
- How many independent trials are feasible and required?
- Does instrumentation materially change the outcome?
- Does any dataset or architecture trigger a preregistered Stop Condition?
- Is the effect large enough to justify a T-CAUSAL headline?

### 18.5 Pilot decision outcomes

- **GO:** protocol, effect scale, variance, baselines, and cost support the frozen full experiment.
- **REVISE:** a specified methodological defect requires returning to the responsible earlier chunk. Pilot results remain exploratory and cannot be pooled without a new preregistration.
- **NARROW:** evidence supports a smaller descriptive or comparative claim; update title, tier, baselines, and venue.
- **STOP/NEGATIVE RESULT:** mechanism does not work or oracle target is not meaningful. Preserve and consider a rigorous negative-result paper rather than continuing to tune on the test set.

### 18.6 Exit gate

The pilot report must include complete run manifests, deviations, failures, variance/cost estimates, power implications, adversarial findings, and a signed decision. Favorable plots alone are insufficient.

---

## 19. Chunk 09 — frozen full experiment

### 19.1 Objective

Execute the approved run matrix exactly once as the primary evidentiary campaign, with immutable artifacts and no analysis-driven retuning.

**Risk tier:** Critical.  
**Claim tier:** T-COMP/T-CAUSAL.

### 19.2 Run discipline

1. Tag the source/configuration/analysis preregistration commit.
2. Build a release binary and record its hash, compiler, flags, and dependency metadata.
3. Resolve dataset, replay, fold, oracle, and model artifact IDs by checksum.
4. Generate the full run matrix from configuration and assign content-derived IDs.
5. Randomize or counterbalance architecture run order to reduce time/machine confounding.
6. Record machine load, thermal/power policy where available, hardware, OS, and clock source.
7. Stage each run output; validate schema/count/completion; atomically finalize it.
8. Retry only according to preregistered infrastructure-failure rules. Never silently replace an unfavorable valid run.
9. Freeze the completed raw run manifest before aggregate analysis.
10. Store full evidence in immutable external storage and record checksums/receipts.

### 19.3 Deviations

Every deviation receives an ID, time, affected runs, reason, decision-maker, and consequence. Scientific deviations require either exclusion under a preregistered rule or a new experiment version; they cannot be edited away in the collector.

### 19.4 Required outputs

- complete run matrix and completion report;
- raw per-run evidence, native traces, logs, and environment records;
- failure/deviation ledger;
- validated aggregates and statistical results;
- sensitivity analyses;
- generated paper tables/figures/macros;
- evidence lineage graph;
- recomputation declarations and stamped reports;
- tier-check results.

### 19.5 Exit gate

All planned valid runs are present; every output passes schema, count, and identity checks; no unplanned exclusion remains; aggregates recompute from immutable inputs; the primary outcome is reported regardless of direction; and claims are narrowed wherever their tier evidence fails.

---

## 20. Chunk 10 — manuscript and research artifact

### 20.1 Objective

Write a complete, honest manuscript whose claims exactly match certified evidence and whose artifact is usable by reviewers.

**Risk tier:** High.  
**Claim tier:** Inherits the highest claim stated.

### 20.2 Manuscript reconstruction

The current `paper/draft.md` is an outline and historical claim source, not the final manuscript. Rebuild the paper with:

- a precise problem statement and prediction/streaming setting;
- an explicit contribution list mapped to evidence;
- mechanism and topology diagrams generated from or checked against configuration;
- formal feature/control definitions;
- dataset provenance and label protocol;
- baseline fidelity and resource symmetry;
- statistical estimands, dependence handling, effect sizes, intervals, and practical margins;
- primary results and negative results;
- ablations that answer mechanism questions rather than maximize table size;
- threats to validity: oracle construction, surrogate baseline fidelity, workload representativeness, platform effects, instrumentation, external validity;
- reproducibility and artifact availability statement;
- complete, verified references with no `[FILL IN]` placeholders;
- required AI-assistance disclosure for the selected venue.

### 20.3 Claim-evidence matrix

Maintain a table with one row per abstract/conclusion claim:

| Claim ID | Exact sentence | Tier | Metric/estimand | Evidence IDs | Baselines | Test/interval | Limitations | Status |
|---|---|---|---|---|---|---|---|---|

A sentence cannot enter the abstract or conclusion while its row is UNKNOWN, FAIL, or missing.

### 20.4 Automated manuscript checks

- every result macro exists in the certified artifact bundle;
- no numeric result is manually embedded outside an explicit allowlist for constants/dataset facts;
- table values equal machine-readable outputs;
- figures match checksummed generated files;
- terminology matches registry names;
- page limit and reference rules match current official venue requirements;
- anonymization and artifact links match the review policy;
- all citations resolve and support the relevant statement;
- no CI-overlap language implies equivalence;
- `seed`, `trial`, `repetition`, `event`, `window`, `user`, and `run` are used consistently.

### 20.5 Internal hostile review

Conduct separate reviews for:

- novelty and related work;
- systems/runtime correctness;
- data leakage and oracle validity;
- statistical claims;
- artifact reproducibility;
- venue scope and presentation.

Reviewers should attempt to falsify, not merely proofread, the paper. Every major criticism maps to a response, code/data change, limitation, or claim removal.

### 20.6 Exit gate

The paper is complete, compiled from a clean checkout, free of placeholders, within current venue rules, and every empirical claim resolves to certified evidence. The artifact guide can be followed without access to the author's local filesystem.

---

## 21. Chunk 11 — independent reproduction and Factory release certification

### 21.1 Objective

Have a person or isolated environment that did not produce the primary run reproduce the artifact and then issue a correctly scoped Factory release certificate.

### 21.2 Independent reproduction levels

1. **Smoke reproduction:** build, tests, fixtures, and tiny end-to-end output.
2. **Analysis reproduction:** download the frozen evidence bundle and regenerate all paper aggregates, tables, and figures.
3. **Representative experiment reproduction:** rerun a preregistered subset on clean hardware and compare within declared tolerances.
4. **Full reproduction:** rerun the entire matrix if resources allow or the venue requires it.

The report must distinguish byte reproducibility from semantic/statistical reproducibility.

### 21.3 Factory checks

Run and archive applicable v2.2 checks, including contract verification/linting, evidence checks, recomputation records, report stamps, stamp verification, tier checks, acquisition audit, release checks, and release certification. The exact command set should be taken from the pinned Factory copy at execution time.

The resulting `RELEASE_CERTIFICATION.md` must state only the categories actually checked. It does not certify scientific truth, paper acceptance, legal compliance beyond reviewed inputs, or platforms not tested.

### 21.4 Exit gate

- independent reproducer starts from documented inputs only;
- all manuscript tables/figures regenerate;
- representative outcomes meet prespecified tolerances;
- discrepancies are explained and resolved or disclosed;
- all required contract/tier/evidence stamps verify;
- release certificate names scope, commit, artifact IDs, and residual limitations.

---

## 22. Chunk 12 — clean public release and submission package

### 22.1 Objective

Create the clean, publication-facing repository and archive that convey the “factory-made” quality without exposing internal debris or falsifying project history.

### 22.2 Public export

Generate a new export from the certified outer commit using an allowlist. The export should contain:

- canonical source, tests, configurations, scripts, environment files, and documentation;
- small fixtures and certified compact artifacts;
- paper source if permitted;
- license, citation, changelog, contribution and security files;
- artifact manifest and DOI/download instructions;
- source revision and certificate mapping.

It should not contain Factory internals, nested governance history, handoff folders, raw/restricted data, working runs, legacy prompts, old audits, or duplicated implementations.

### 22.3 Release checks

- clone the public repository into a new empty path;
- search for absolute local paths, credentials, personal metadata beyond intended authorship, and hidden large files;
- run clean setup, build, tests, smoke reproduction, and analysis reproduction;
- validate all links and archive downloads;
- check release archive contents against an allowlist;
- verify tag signatures/checksums where used;
- create a DOI archive and compare its checksum to the release package;
- confirm the README's claims and test count match the release;
- confirm license compatibility and dataset redistribution behavior;
- prepare venue-specific artifact instructions, anonymity, disclosures, and supplemental files.

### 22.4 Release identity

Record:

- internal certified commit and tag;
- nested governance release-certificate commit;
- public repository commit/tag;
- release archive SHA-256;
- external evidence DOI/version;
- paper submission version;
- date and responsible reviewers.

This mapping makes the public tree look deliberately designed without pretending the earlier development did not happen.

---

## 23. Current claim and artifact quarantine matrix

This matrix should be converted into governance records during adoption.

| Current item/claim | Present problem | Required rehabilitation evidence | Earliest release chunk |
|---|---|---|---|
| “Five seeds” | Seed label is not demonstrably consumed by the C++ architecture path | Randomness inventory, seed propagation, run manifests, repetition terminology | 05/08 |
| 35 runs / seven architectures | Authoritative run directory is ignored/untracked; run sets conflict | Frozen matrix and completeness validator | 09 |
| Exact/loss-free processing | Heuristic queue-empty shutdown and partial windows | Lifecycle proof, exact-count adversarial tests | 02 |
| RateThrottle baseline | Fixed and throttle share a harness branch; initialization concern | Behavioral signature and resource-parity audit | 05 |
| Adaptive controller trace | Operator trace sink unused; header-only/reconstructed traces | Native versioned trace with causal ordering | 02/05 |
| Correlation around 0.683 | Value is hard-coded/reconstructed rather than trace-derived | Preregistered trace statistic from complete native traces | 06/09 |
| Online/offline feature correctness | Timestamp and dataset mapping mismatches | Golden corpus and differential parity | 03 |
| ULB feature results | Live C++ behavior coding conflicts with Python logic | Dataset-specific semantic specification and parity | 03/04 |
| Oracle quality/ceiling | Random splits and in-sample prediction risk | Fold manifest and fully out-of-fold scores | 04 |
| Taobao labels | Current-event boundary and censoring ambiguity | Preregistered label protocol and leakage tests | 04 |
| RALF comparison | Surrogate fidelity and duplicate-key behavior unresolved | Independent reference, naming, equal-budget validation | 03/05 |
| MBB confidence intervals | Runs collapsed; block semantics/reporting inconsistent | Dependence-aware validated resampling | 06 |
| “Statistically indistinguishable” | CI overlap is not equivalence | Prespecified margin and equivalence/non-inferiority analysis | 06/09 |
| Burst/refresh results | Some analyses use only first seed | Full planned paired evidence or explicit descriptive limitation | 06/09 |
| Shuffled-null result | Uses partial run set | Preregistered complete null analysis | 06/09 |
| Fairness/Jain values | Collector labels/values conflict and can exceed plausible range | Metric schema, range checks, regenerated output | 06/09 |
| Controller overhead | Measurement boundary includes instrumentation ambiguity | Paired benchmark and overhead decomposition | 02/08/09 |
| Figures/tables | Hard-coded values and inconsistent paths | Generated certified outputs and lineage graph | 06/09 |
| Paper conclusions | Draft incomplete; sources and claims unverified | Claim-evidence matrix and hostile review | 10 |

Nothing in this table should be silently “fixed” by changing prose alone. Either produce the required evidence or remove/narrow the claim.

---

## 24. Verification architecture

The final project needs a layered verification system.

### 24.1 Layer 1 — structural

- clean Git status;
- allowed files only;
- no duplicate implementation roots;
- no broken symlinks or local absolute paths;
- no forbidden large/generated/restricted files;
- manifests and schemas validate;
- documentation links resolve.

### 24.2 Layer 2 — unit and property

- queue semantics and capacity boundaries;
- runtime state transitions;
- feature state updates;
- controller decisions;
- baseline behavioral properties;
- configuration validation;
- statistic known-answer tests;
- artifact hashing and atomic finalization.

### 24.3 Layer 3 — integration

- exact source-to-sink counts for every architecture;
- tail-window policy;
- slow/failing operator propagation;
- native trace completeness;
- data-to-replay-to-feature-to-model flow;
- online/offline parity;
- result schema and run identity.

### 24.4 Layer 4 — dynamic analysis

- ASan/UBSan;
- TSan;
- leak/lifetime checks where supported;
- fuzz/property tests for parsers, event order, and runtime stress;
- repeated schedule-sensitive runs.

### 24.5 Layer 5 — scientific integrity

- acquisition audit and Reality Gate;
- leakage tests;
- fold/model provenance;
- baseline symmetry;
- preregistration and Stop Conditions;
- complete run matrix;
- validated statistical procedure;
- claim-tier evidence and adversarial tests.

### 24.6 Layer 6 — reproducibility and release

- clean-machine smoke run;
- immutable artifact download/checksum;
- analysis reproduction;
- representative experimental reproduction;
- paper build and claim-macro check;
- Factory stamps, tier check, release check, and scoped certification;
- public export clone test.

A green lower layer never waives a higher layer. Nine passing unit tests, for example, do not establish data authenticity or statistical validity.

---

## 25. Evidence and manifest model

Every generated run should have a self-contained `run_manifest.json` conceptually containing:

```json
{
  "schema_version": "bpfeat.run-manifest.v1",
  "run_id": "content-derived-id",
  "status": "complete",
  "source": {"commit": "...", "dirty": false},
  "build": {"binary_sha256": "...", "profile": "release", "toolchain": "..."},
  "configuration": {"id": "...", "sha256": "..."},
  "architecture": {"id": "...", "topology_sha256": "..."},
  "data": {"artifact_id": "...", "sha256": "..."},
  "oracle": {"artifact_id": "...", "fold_manifest_id": "..."},
  "model": {"artifact_id": "...", "sha256": "..."},
  "replication": {"seed": null, "repetition": 1},
  "host": {"os": "...", "cpu": "...", "compiler": "..."},
  "counts": {"offered": 0, "accepted": 0, "processed": 0, "emitted": 0, "dropped": 0},
  "outputs": [{"role": "events", "path": "...", "sha256": "...", "rows": 0}],
  "started_at": "...",
  "completed_at": "..."
}
```

This is illustrative; the schema is to be designed and versioned in its contract. A result file without a complete, validated manifest is working output, not evidence.

For each manuscript claim, the evidence graph should resolve:

```text
claim
  -> statistical result
    -> aggregate
      -> complete set of run manifests
        -> raw run outputs and native traces
          -> binary/config/data/oracle/model/source identities
```

The reverse direction should also work: given a run, identify every aggregate, figure, table, and claim that depends on it.

---

## 26. Documentation and publication metadata backlog

The following publication-facing files should be produced through the relevant chunks:

- `README.md`: concise problem, status, architecture, quick start, supported platforms, data/artifact access, reproduction levels, citation, license;
- `REPRODUCIBILITY.md`: environment, acquisition, preprocessing, oracle, experiment, analysis, expected time/storage, checksums, troubleshooting;
- `LICENSE`: explicit code license;
- `CITATION.cff`: project/paper citation metadata;
- `CHANGELOG.md`: rehabilitation and release changes without fabricated history;
- `CONTRIBUTING.md`: development setup, tests, coding and scientific evidence expectations;
- `SECURITY.md`: reporting and supported release scope;
- `docs/architecture.md`: generated/checked topology and lifecycle;
- `docs/methodology.md`: prediction task, features, controller, baselines, estimands;
- `docs/datasets.md`: sources, licenses, schemas, checksums, non-redistributed material;
- `docs/artifact_guide.md`: smoke, analysis, representative, and full reproduction;
- release notes: exact source/artifact/certificate IDs and known limitations.

Do not expose internal role prompts or factory governance as user documentation. Do not make the README depend on ignored `bpfeat_build_prompt.md` or historical audits.

---

## 27. Risk register

| Risk | Likelihood | Impact | Early signal | Mitigation / decision |
|---|---:|---:|---|---|
| Exact completion changes reported results | High | Critical | output counts differ from old runs | Treat old results as quarantined; rerun all evidence |
| Online/offline parity cannot be achieved without redefining features | Medium-high | Critical | golden corpus mismatch | Choose explicit semantics, update contribution, preserve legacy comparison only as diagnosis |
| Oracle target is leaked or weak | High | Critical | OOF AUROC collapses; leakage tests change labels | Redefine prediction point/target or abandon oracle-quality claim |
| RateThrottle/RALF baselines are not faithful | High | High | behavioral tests fail or literature mismatch | Implement faithfully or rename/narrow claims; add credible alternatives |
| T-CAUSAL evidence is too expensive | Medium | High | pilot variance/power demands excessive trials | Narrow to T-COMP/T-DESC or choose a smaller defensible workload |
| ICDE 2027 timeline is unrealistic | High | Medium-high | early chunks miss decision gates | Move to later venue; never skip validity gates |
| Data redistribution prohibited | Medium | High | license review | Publish acquisition scripts/checksums and permitted fixtures, not raw bytes |
| Large Git history impedes hosting | High | Medium | clone size remains large after index cleanup | Clean certified public export; retain internal bundle/history |
| Sanitizer reveals architectural races | Medium-high | High | TSan failures | Resolve before experiments; reduce supported platform claim if tool limitation only |
| Results depend on host scheduling/thermal behavior | Medium-high | High | high repetition variance | counterbalance, record environment, pin policies where justified, report distribution |
| Statistical method gives unstable conclusions | Medium | High | sensitivity analysis changes direction | report sensitivity, narrow claim, increase sample if preregistered/feasible |
| Factory gates are mistaken for scientific truth | Medium | High | reports say “certified” without scope | state check scope; retain human/method review and independent reproduction |
| Migration accidentally loses evidence | Low if controlled | Critical | checksum/restoration failure | tag, bundle, explicit disposition, copy-verify before untracking |
| Public release leaks secrets/personal paths | Medium | High | scan findings | secret/path scans and allowlist export from clean environment |
| Paper overstates a surrogate or null result | Medium-high | High | hostile review objections | claim-evidence matrix, naming rules, equivalence discipline |

The risk register belongs in `project_knowledge.md` or a linked governance record and should be updated after every chunk.

---

## 28. Human decisions required

These decisions cannot safely be inferred by automation and should be recorded before their dependent chunk:

1. **Scientific task:** What exactly is predicted/optimized, at what moment, and for whom?
2. **Tail policy:** Is a final partial feature window emitted, padded, or deliberately dropped?
3. **Dataset role:** Are Taobao and ULB both primary evidence, or is one only external-validity/supporting evidence?
4. **ULB semantics:** Which user-like/behavior-like features are scientifically meaningful for transaction fraud data?
5. **Baseline set:** Which three or more baselines are faithful, feasible, and venue-credible?
6. **RALF naming:** Faithful reproduction or explicitly inspired surrogate?
7. **Claim tier:** T-CAUSAL headline, T-COMP comparison, or T-DESC systems observation?
8. **Practical margin:** What effect is large enough to matter for quality, latency, throughput, and equivalence?
9. **Resource budget:** Available machines, storage, compute time, and number of independent repetitions.
10. **Venue:** Conditional ICDE 2027 Round 2 versus a later venue after early-gate evidence.
11. **Licensing:** Code license and permitted redistribution for data, models, and result artifacts.
12. **Release history:** Default clean public export or an explicitly approved history rewrite.

The Factory Architect should present these as decision records with consequences, not bury them in implementation reports.

---

## 29. Suggested execution cadence and effort bands

Calendar promises should not override gates, but a realistic planning envelope is useful.

| Work | Typical focused effort | Main uncertainty |
|---|---:|---|
| Adoption Gate | 2–4 days | literature/venue review and data provenance |
| Chunk 01 | 4–7 days | multi-gigabyte artifact classification and externalization |
| Chunk 02 | 1–2 weeks | lifecycle redesign and concurrency failures |
| Chunk 03 | 1–2 weeks | feature-definition changes and cross-language parity |
| Chunk 04 | 1–3 weeks | label redesign, folds, oracle recomputation, data licensing |
| Chunk 05 | 1–2 weeks | faithful baseline implementation |
| Chunk 06 | 1–2 weeks | statistical design and validation |
| Chunk 07 | 4–8 days | platform/CI availability |
| Chunk 08 | 3–7 days plus compute | variance and adversarial failures |
| Chunk 09 | compute-dependent | full matrix cost and infrastructure failures |
| Chunk 10 | 1–3 weeks | paper depth, figures, related work, hostile review |
| Chunk 11 | 3–7 days plus compute | independent environment/access |
| Chunk 12 | 2–4 days | archive, DOI, venue packaging |

These bands make the 2026-11-11 ICDE Round 2 deadline aggressive. A deadline decision should occur after Chunk 04 or earlier if critical gates fail. If the path is not credible, choose a later venue and preserve quality.

Parallel work is allowed only when contracts prove file and evidence independence. Examples: license research may proceed while runtime unit tests are developed; manuscript related-work notes may proceed without inserting results. Full experiments, final statistics, and numerical manuscript claims remain serially gated.

---

## 30. The first execution checklist

When this plan is approved, the first active work should be the Adoption Gate followed immediately by Chunk 01. The concrete order is:

1. Confirm the outer repository is still clean and record any changes since `37c85a6`.
2. Create the migration baseline tag and verified all-refs Git bundle.
3. Hash the supplied Factory v2.2 distribution and record the bootstrap manifest.
4. Create the idempotent local adoption script and prove it does not overwrite existing files.
5. Initialize the nested `project/` governance repository.
6. Copy the legacy v1 attempt into a checksummed migration-evidence inventory without deleting the original yet.
7. Draft and review the founding documents and Methodology Adversarial Review.
8. Decide provisional claim tier, target task, baseline feasibility, and venue gate.
9. Architect snapshots the repo and authors `chunk01.md`, its execution manifest, and only contract C01.01 in full.
10. Implementor produces the read-only disposition inventory—no moves or index changes yet.
11. Architect reviews the inventory and authors C01.02, then proceeds contract by contract.
12. Externalize and checksum large artifacts before any index removal.
13. Move canonical code with history-preserving operations; keep semantic changes separate.
14. Install the structural policy and clean-clone checks.
15. Run the Chunk 01 audit and issue a scoped verdict.

This order makes rollback possible at every step and prevents a tidy directory tree from hiding lost evidence.

---

## 31. Definition of rehabilitation complete

BPFeat is rehabilitated—but not yet necessarily publication-ready—when:

- Factory v2.2 is pinned and operating around the project;
- the nested governance repository contains truthful founding docs and reviewed chunk history;
- the outer repository has one canonical implementation and a clean, understandable layout;
- all legacy files have recorded disposition and recoverable preservation where required;
- raw data, full runs, and generated debris are no longer accidentally tracked;
- a clean clone builds and runs baseline tests using tracked fixtures;
- the old Factory v1 duplicate no longer competes with the canonical source;
- current results are labeled historical/quarantined rather than authoritative.

BPFeat is **publication-ready** only when, in addition:

- runtime exactness, shutdown, topology, concurrency, and tracing pass adversarial tests;
- feature semantics and online/offline parity are proven on golden and generated cases;
- data authenticity, label timing, splits, and fully out-of-fold oracle pass the Reality Gate and leakage audits;
- at least three credible baselines are faithfully implemented and resource-symmetric for a T-CAUSAL claim;
- the statistical plan is preregistered, dependence-aware, power-conscious, and validated;
- a pilot passes its Stop Conditions and a frozen full experiment completes without hidden exclusions;
- all numbers, tables, and figures regenerate from immutable manifests;
- manuscript claims match their tier and evidence, including negative findings and limitations;
- supported clean environments build, test, and reproduce the artifact;
- licenses, citations, data access, security, and venue requirements are resolved;
- independent reproduction succeeds;
- Factory evidence, stamps, tier checks, release checks, and scoped certification pass;
- the public export is clean, compact, mapped to the certified internal revision, and archived immutably.

---

## 32. Final operating rule

The rehabilitation should optimize for one thing: **a reviewer should be able to distrust the project and still reach the same verified facts by following its evidence.**

That requires keeping the good implementation work, preserving the messy history honestly, removing ambiguity from the publication tree, and recomputing the science only after the system measures what the manuscript says it measures. If a favorable old result survives that process, it becomes credible. If it does not, the project must report the corrected or negative result. That is what will make BPFeat look—and behave—like it came from the Software Factory from the first day.
