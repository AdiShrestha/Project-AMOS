# BPFeat — IEEE Submission Audit Guide

**Purpose:** A static, code-level verification protocol. This document defines
PASS/FAIL gates only — running the checks below does not modify any code,
data, or results. Every finding is either a verified PASS, a verified FAIL, or
a CONDITIONAL (passes today but requires an explicit disclosure or a
remediation step before submission). No item in this guide is decorative;
every checklist entry maps to a concrete command whose output determines the
verdict.

**How to use this guide:** Run every code snippet in the section against the
actual repository. Record the literal output next to each checklist item.
A section is not "done" until every item has a recorded PASS/FAIL/CONDITIONAL
with evidence, not an assumption.

---

## Structural Framework

| # | Section | Scope |
|---|---|---|
| 1 | Reproducibility & Environment Determinism Audit | Seeds, concurrency non-determinism, hardware dependence, dependency pinning, data acquisition friction |
| 2 | Data Integrity, Provenance, & Anti-Fabrication Audit | Raw data provenance, lineage chain-of-custody, oracle contamination, look-ahead bias, online/offline parity |
| 3 | Evaluation Rigor, Baseline Comparisons, & Bias Audit | Overfitting detection, baseline strength, statistical significance requirements |
| 4 | Code Integrity & Licensing Audit | Borrowed-code attribution, license compatibility, hardcoded-shortcut detection |
| 5 | Ethical AI Utilization & Transparency Disclosure | AI-tool usage documentation, IEEE-compliant disclosure template |

*(A Section 6 "Master Audit Verdict Matrix" aggregating every PASS/FAIL/CONDITIONAL
across Sections 1–5 into one sign-off table will be appended once Section 5 is
complete.)*

This document is written specifically against BPFeat's actual architecture: a
lock-free multi-threaded C++17 stream runtime (not a GPU training loop), a
Python preprocessing/analysis layer (pandas, scikit-learn, Moving Block
Bootstrap), and two real datasets (Taobao UserBehavior, ULB Credit Card
Fraud) acquired through non-anonymous, credentialed downloads. Generic
ML-paper audit templates (seed-check-for-PyTorch, standard k-fold CV)
under-cover the risks that actually exist in this codebase — chief among them,
concurrency-induced non-determinism in the runtime and a subtle oracle
train/test contamination issue identified below in 2.3. Both are treated with
the same rigor as the standard checks.

---

## 1. Reproducibility & Environment Determinism Audit

### 1.1 Randomness & Seed Control (Python Layer)

**Risk:** Any unseeded call to `numpy.random`, `random`, `sklearn`'s stochastic
solvers, or the Moving Block Bootstrap resampler makes headline numbers
non-reproducible run-to-run, even on identical input data.

**Checklist**
- [ ] Every `np.random.*` call site is preceded by an explicit, fixed seed or
      uses a seeded `np.random.default_rng(seed)` instance passed explicitly.
- [ ] `sklearn.model_selection.train_test_split` calls specify `random_state=`.
- [ ] `sklearn.linear_model.LogisticRegression` specifies `random_state=` (the
      `lbfgs` solver is deterministic given fixed data, but `class_weight=
      'balanced'` combined with certain solvers can still introduce
      convergence-order sensitivity across BLAS backends — seed regardless).
- [ ] The `arch.bootstrap.MovingBlockBootstrap` / `IIDBootstrap` instantiation
      sets a fixed `state` / `random_state`, or `.seed()` is called before
      every `.apply()` invocation used to produce a reported CI.
- [ ] `preprocess_taobao.py`'s user-subsampling and burst-tagging RNG calls
      use a documented, fixed seed (not a bare default).
- [ ] The synthetic/fallback data generator (`generate_synthetic.py`) is
      seeded identically on every invocation used for any *reported* number
      (not just smoke tests).

**Audit command:**
```bash
grep -rn "np\.random\|random\.random\|random\.seed\|default_rng\|train_test_split\|MovingBlockBootstrap\|IIDBootstrap\|LogisticRegression(" \
    --include="*.py" . | grep -v "random_state=\|seed=\|\.seed("
```
**PASS:** command returns zero lines (every stochastic call site already
carries an explicit seed argument on the same line or is provably seeded via
a preceding, traceable call).
**FAIL:** any line is returned — that call site has no visible seed binding
and must be treated as non-reproducible until fixed.

### 1.2 Concurrency-Induced Non-Determinism (C++ Runtime) — Highest-Risk Item

**Risk:** KLStream is a lock-free, multi-threaded, cooperatively-scheduled
runtime (4 worker threads: source+extract, window, scorer, sink). OS thread
scheduling is not deterministic across runs. Floating-point addition is not
associative — if the exact interleaving of `EMAOccupancyTracker::update()`
reads, `AlphaController::update()` calls, or queue-drain order varies by even
one event between two runs of the *identical binary on the identical input*,
the least-significant bits of `alpha[n]`, `W[n]`, and downstream scores can
differ. At the aggregate level this is usually harmless; at the level of "does
this experiment reproduce," it must be characterized, not assumed away.

**Checklist**
- [ ] Row **count** of `results/raw/results_<arch>_seed<N>.csv` is identical
      across 3 repeated runs of the same architecture/seed/replay file
      (any variance here indicates a dropped-event race condition, not benign
      floating-point jitter — this is a hard FAIL, not a rounding footnote).
- [ ] Aggregate metrics (FR mean, PATR, WOR, staleness mean) across 3 repeated
      runs of the same seed fall within the *reported* MBB 95% CI half-width.
      If run-to-run variance on a **fixed seed** exceeds the reported CI, the
      CI is not capturing true variance and every confidence interval in the
      paper is invalid.
- [ ] Per-event `score`, `alpha_used`, `window_size_used` columns are either
      bit-identical across repeated runs, or any divergence is bounded and
      documented (e.g., "differs in ≤0.01% of events, never changes which
      AIMD regime — shrink/grow/deadband — a given window falls into").

**Audit command:**
```bash
for i in 1 2 3; do
  ./build/feature_flow/feature_flow_harness \
    --replay data/replay/replay_taobao_10k.csv \
    --seeds 1 --arch adaptive --out-dir /tmp/repro_check_run$i/
done

python3 - << 'EOF'
import pandas as pd
a = pd.read_csv('/tmp/repro_check_run1/results_adaptive_seed0.csv')
b = pd.read_csv('/tmp/repro_check_run2/results_adaptive_seed0.csv')
c = pd.read_csv('/tmp/repro_check_run3/results_adaptive_seed0.csv')
print("row counts:", len(a), len(b), len(c))
print("max abs score diff (run1 vs run2):", (a['score']-b['score']).abs().max())
print("max abs score diff (run1 vs run3):", (a['score']-c['score']).abs().max())
print("window_size_used identical run1==run2:", (a['window_size_used']==b['window_size_used']).all())
print("alpha_used identical run1==run2:", (a['alpha_used']==b['alpha_used']).all())
EOF
```
**PASS:** row counts identical across all 3 runs; any score/alpha/W deltas are
zero or numerically negligible (<1e-9) and never flip a controller regime.
**FAIL:** row counts differ between any two runs (dropped-event race — treat
as a correctness bug, not a documentation footnote), or per-event values
diverge enough to change a controller decision.
**CONDITIONAL:** row counts match and aggregate metrics stay within the
reported CI, but individual scores show small non-zero floating-point
divergence. Acceptable only if explicitly disclosed in the paper's
reproducibility statement as "bit-exact reproduction is not guaranteed under
this runtime's concurrent scheduling; aggregate metrics reproduce within
reported confidence intervals."

### 1.3 Hardware & Platform Dependence

**Risk:** `CoreAffinity::Performance` / `CoreAffinity::Efficiency` is an Apple
Silicon-specific abstraction (P-core/E-core pinning). Most IEEE reviewers and
artifact-evaluation committees run on x86 Linux. If this code does not compile
or silently no-ops on non-Apple hardware, the project is only reproducible on
one vendor's laptops — a real portability gap that must be either fixed or
explicitly disclosed.

**Checklist**
- [ ] Core-pinning code is guarded by a platform check (`#ifdef __APPLE__` or
      equivalent) with a defined, documented fallback behavior on Linux/x86
      (e.g., "falls back to OS-default thread scheduling with a printed
      warning," not a silent no-op with no diagnostic).
- [ ] A clean build on x86_64 Linux (or a Docker container emulating one)
      compiles without modification.
- [ ] The paper/README states plainly that absolute wall-clock latency
      numbers were measured on Apple M3 and are not expected to numerically
      reproduce on other architectures; only relative architecture-to-
      architecture comparisons on the *same* hardware are the reproducible
      claim.

**Audit command:**
```bash
grep -rn "CoreAffinity\|Performance\|Efficiency" include/klstream/core/worker.hpp
grep -n "__APPLE__\|__linux__\|_WIN32" include/klstream/core/*.hpp
# Then attempt a clean build in a non-Apple environment:
docker run --rm -v "$PWD":/src -w /src ubuntu:24.04 bash -c \
  "apt-get update && apt-get install -y cmake g++ && cmake -S . -B /tmp/build && cmake --build /tmp/build -j4"
```
**PASS:** platform guards exist, non-Apple build succeeds (with documented
degraded pinning behavior), and the hardware-dependence disclosure is present
in the paper/README.
**FAIL:** build fails outright on non-Apple hardware, or succeeds silently
with no disclosure that pinning semantics changed.

### 1.4 Dependency Pinning & Build Reproducibility

**Risk:** An unpinned `pip install pandas` today and the same command in six
months can resolve to different major versions with different default
behaviors (this has historically happened with scikit-learn solver defaults
and pandas indexing semantics). A future re-run could silently produce
different oracle weights or different MBB confidence intervals with no code
change at all.

**Checklist**
- [ ] A `requirements.txt` (or `pyproject.toml`/`environment.yml`) exists with
      **exact-pinned** versions (`==`, not `>=`) for: pandas, numpy, scipy,
      scikit-learn, `arch` (MBB library), matplotlib.
- [ ] `CMakeLists.txt` specifies `set(CMAKE_CXX_STANDARD 17)` explicitly and
      the compiler + version used to produce reported numbers is recorded
      (e.g., in the README or a `BUILD_ENV.txt`).
- [ ] A fresh `pip install -r requirements.txt` into a clean virtual
      environment reproduces the exact package set used to generate the
      paper's numbers.

**Audit command:**
```bash
test -f requirements.txt && echo "requirements.txt exists" || echo "FAIL: no lockfile"
python3 -m venv /tmp/audit_venv && source /tmp/audit_venv/bin/activate
pip install -r requirements.txt --break-system-packages 2>&1 | tail -5
pip list --format=freeze > /tmp/current_env.txt
diff /tmp/current_env.txt requirements.txt
deactivate
```
**PASS:** `requirements.txt` exists, is exact-pinned, and the diff is empty.
**FAIL:** no lockfile exists, or any version is unpinned (`pandas` instead of
`pandas==2.2.1`), or the diff shows a resolved version different from what
was pinned.

### 1.5 Wall-Clock-Dependent Results Disclosure

**Risk:** The 16.2× batch-latency figure, PATR values, and the ~30ns
controller-overhead number are wall-clock measurements taken on one specific
machine under whatever background load existed at benchmark time. These are
fundamentally different in kind from a deterministic accuracy metric (Feature
Regret) and must be treated, reported, and disclosed differently.

**Checklist**
- [ ] The paper/README explicitly states that latency/throughput numbers are
      specific to the test environment (exact CPU model, RAM, OS, and whether
      the machine was under exclusive load during benchmarking) and are not
      claimed to reproduce numerically elsewhere — only the qualitative,
      relative pattern is the reproducible claim.
- [ ] The headline batch-latency ratio (16.2×) has been measured across
      **multiple repeated runs** of the identical experiment, with variance
      reported, not asserted from a single run.

**Audit command:**
```bash
for i in 1 2 3 4 5; do
  ./build/feature_flow/feature_flow_harness \
    --replay data/replay/replay_causal_demo.csv \
    --seeds 1 --scoring-delay-us 500 --arch adaptive \
    --out-dir /tmp/latency_repro_$i/
done

python3 - << 'EOF'
import pandas as pd, numpy as np
vals = []
for i in range(1, 6):
    df = pd.read_csv(f'/tmp/latency_repro_{i}/timing_adaptive_seed0.csv')
    df['lat_ms'] = df['latency_ns'] / 1e6
    burst = df[df['is_burst'] == 1]
    vals.append(burst['lat_ms'].quantile(0.5))
print("p50 across 5 repeated identical runs:", vals)
print("relative std:", np.std(vals) / np.mean(vals))
EOF
```
**PASS:** relative std across 5 repeated runs is under ~15%, and the
hardware-dependence disclosure is present in the paper.
**FAIL:** relative std exceeds ~15% (the cited ratio is not a stable, citable
number as a single point estimate — report a trimmed mean with a range
instead), or no hardware-dependence disclosure exists anywhere in the paper.

### 1.6 Data Acquisition Reproducibility

**Risk:** Taobao UserBehavior requires manual Tianchi account registration —
there is no scripted, anonymous, one-command download. ULB via Kaggle is
scriptable but still requires a credentialed account. "Clone and reproduce"
cannot be fully automated for this project's primary dataset, and this must
be stated honestly rather than implied away.

**Checklist**
- [ ] README states plainly, in the reproducibility section (not buried),
      that Taobao acquisition requires manual Tianchi registration, with the
      exact registration URL.
- [ ] README/preprocessing script asserts the downloaded raw file's row count
      falls within the publicly documented range for that dataset, failing
      loudly (not silently proceeding) if it does not — this catches
      corrupted, partial, or wrong-version downloads before they propagate
      into a full experimental run.
- [ ] ULB's expected row count (284,807, publicly documented, exact) is
      hard-asserted, not just informally checked.

**Audit command:**
```bash
grep -n "tianchi\|kaggle\|284807\|284,807" README.md
python3 -c "
import pandas as pd
df = pd.read_csv('data/raw/creditcard.csv')
assert len(df) == 284807, f'FAIL: expected 284807 rows, got {len(df)}'
print('PASS: ULB row count exact match')
"
```
**PASS:** both assertions present, README discloses the manual-registration
friction explicitly.
**FAIL:** README implies one-command reproduction without mentioning this
friction, or no row-count/checksum self-verification exists anywhere in the
pipeline.

### 1.7 End-to-End Fresh-Clone Reproduction Protocol

**The ultimate gate for this entire section.** Everything above is a
component check; this is the integration test.

**Checklist — execute in exact order on a genuinely fresh clone:**
- [ ] `git clone` into a new directory (not a copy of the working directory).
- [ ] Fresh virtual environment; `pip install -r requirements.txt`.
- [ ] `rm -rf build && cmake -S . -B build && cmake --build build -j4` (full
      clean rebuild, not incremental).
- [ ] `ctest --test-dir build --output-on-failure` → must show **9/9 passed**,
      not "6/9 with 3 skipped."
- [ ] Acquire Taobao + ULB data per README §1.6 checks above.
- [ ] Run preprocessing scripts exactly as documented.
- [ ] Run the full 5-seed, 7-architecture harness.
- [ ] Run `compute_metrics.py`.
- [ ] Diff every headline number (FR per architecture, PATR, WOR, staleness,
      Jain's index, oracle AUROC) against the numbers claimed in the paper.

**PASS:** every diffed number falls inside the paper's reported MBB 95% CI.
**FAIL:** any headline number falls outside its own reported CI on a fresh
reproduction — this means the original run was not representative, or the
CI computation itself is broken.

---

## 2. Data Integrity, Provenance, & Anti-Fabrication Audit

### 2.1 Raw Data Provenance Verification

**Risk:** No independently-verifiable proof exists that `data/raw/*.csv` are
the actual, unmodified files from Tianchi/Kaggle rather than hand-edited or
substituted files.

**Checklist**
- [ ] SHA-256 checksums of both raw files are computed at acquisition time
      and committed to a `CHECKSUMS.sha256` manifest (raw files themselves
      should remain gitignored per size/license, but the checksum record
      must be committed).
- [ ] Checksums are re-verified as a mandatory pre-flight step before any
      full experimental run, not just once at download time.
- [ ] ULB row count (284,807, exact, publicly documented) and Taobao's
      documented approximate range (~100M rows) are both asserted.

**Audit command:**
```bash
sha256sum data/raw/UserBehavior.csv data/raw/creditcard.csv > /tmp/current_checksums.sha256
diff /tmp/current_checksums.sha256 data/raw/CHECKSUMS.sha256
```
**PASS:** manifest exists, diff is empty, both row-count assertions pass.
**FAIL:** no manifest exists, or checksums drift from the recorded values
(indicates the raw file was replaced or modified after initial acquisition).

### 2.2 Data Lineage Chain-of-Custody

**Risk:** Every derived artifact (replay CSVs, `oracle_scores.csv`, trained
model weight files) must be traceable to an exact source file, an exact
script invocation, and an exact code version. This project's own history
contains a directly relevant cautionary precedent: an entire "stress
experiment" run was, at one point, accidentally executed against
`oracle_scores.csv` instead of a genuine replay file, producing a fully
self-consistent but entirely invalid results set (zero staleness across every
architecture) that was only caught by manual inspection. A lineage manifest
with automated schema pre-flight validation converts that class of error from
"caught by luck" to "structurally impossible."

**Checklist**
- [ ] Every derived file has an accompanying manifest recording: source
      checksum, generating script path, generating script's git commit hash
      at time of run, exact CLI arguments used, and output checksum.
- [ ] A pre-flight schema check runs automatically before the C++ harness
      accepts any `--replay` argument, refusing to proceed if the file's
      header does not match the expected replay schema.

**Audit command:**
```bash
python3 - << 'EOF'
import sys, pandas as pd
expected_cols = {'seq','timestamp_ns','user_id','item_id','category_id',
                 'behavior_code','label','label_valid','is_burst_period'}
path = 'data/replay/replay_taobao_10k.csv'
cols = set(pd.read_csv(path, nrows=1).columns)
missing = expected_cols - cols
if missing:
    print(f"PRE-FLIGHT FAIL: {path} missing columns {missing}")
    sys.exit(1)
print("PRE-FLIGHT PASS: schema matches expected replay format")
EOF
```
**PASS:** manifest exists per derived file; pre-flight check is wired into
the harness invocation path itself (not just available as a standalone
script that could be skipped).
**FAIL:** any derived file whose exact generation parameters cannot be
reconstructed from committed metadata; pre-flight check exists only as an
optional, disconnected script.

### 2.3 Oracle Train/Test Contamination — Critical, Project-Specific Finding

**This is a real, previously-undiscussed methodological gap, not a
boilerplate checklist item. Treat it as CONDITIONAL FAIL pending
remediation.**

`train_classifier.py` fits the oracle `LogisticRegression` on an 80% train
split and honestly reports AUROC/AUPRC on the held-out 20% test split. But
`oracle_scores.csv` — the file against which every architecture's Feature
Regret is computed — is generated by scoring the **fitted** oracle against
**all** events, including the 80% it was trained on. In-sample loss is a
downward-biased estimate of true generalization loss. This means, for roughly
80% of the events used in every reported Feature Regret computation, the
oracle's BCE term is artificially deflated (the oracle partially memorized
those exact labels), which **inflates** the reported positive FR values for
every non-oracle architecture. This does not fabricate a result out of
nothing, but it does mean the reported FR magnitudes for Adaptive (+0.0036)
and RALF (+0.0309) may be **systematically overstated** relative to what a
genuinely out-of-sample oracle comparison would show. The *relative* ordering
between architectures (Adaptive < RALF) likely survives, since both are
contaminated identically — but the absolute magnitudes, and therefore any
claim like "BPFeat achieves near-oracle accuracy," require verification
against a clean oracle.

**Checklist**
- [ ] The exact `seq` values used in the oracle's train split are saved to a
      committed file (e.g., `models/oracle_train_seqs.csv`) at training time.
- [ ] Verify what fraction of `oracle_scores.csv` rows correspond to
      in-sample (oracle-training-set) events.
- [ ] If contamination is non-zero, either (a) recompute Feature Regret using
      only the held-out 20% test split for every architecture's comparison
      (reducing statistical power but removing the bias), or (b) retrain the
      oracle via k-fold cross-validation so every event's oracle score is
      genuinely out-of-fold, then regenerate `oracle_scores.csv` from the
      out-of-fold predictions.

**Audit command:**
```python
import pandas as pd
train_seqs = pd.read_csv('models/oracle_train_seqs.csv')['seq']  # must exist — if it
                                                                    # doesn't, that alone
                                                                    # is a FAIL: the
                                                                    # train/test boundary
                                                                    # is not auditable.
oracle = pd.read_csv('data/replay/oracle_scores.csv')
contaminated = oracle['seq'].isin(train_seqs).sum()
print(f"Oracle-scored rows also in the oracle's own training set: "
      f"{contaminated} / {len(oracle)} ({contaminated/len(oracle):.1%})")
```
**PASS:** contamination is 0% (regret computed only on genuinely held-out
oracle predictions, either via a dedicated test-split-only regret table or
k-fold out-of-fold scoring).
**FAIL:** `models/oracle_train_seqs.csv` does not exist (train/test boundary
is unverifiable after the fact) — this is an automatic FAIL regardless of the
actual contamination fraction, because the claim cannot be audited at all.
**CONDITIONAL:** contamination is non-zero and quantified — acceptable for
submission only if the paper explicitly discloses "Feature Regret is computed
against an oracle that was partially fit on the same events; relative
architecture ordering is preserved, but absolute regret magnitudes are an
upper bound on true out-of-sample regret" — and this disclosure appears in
the Experimental Setup section, not a footnote.

### 2.4 Look-Ahead Bias in Label & Feature Construction

**Risk:** The label is intentionally forward-looking (a valid supervised
target), but must never be accessible to the *online* feature computation
that produces `ema_engagement`, `pv_count`, etc. Any conditional path where
label influences a computed feature value is a fabrication-adjacent bug: it
would make the system's "predictions" partially see the answer.

**Checklist**
- [ ] `RawBehaviorEvent` (the trivially-copyable payload crossing the hot-path
      SPSC queue) contains **no** label or label_valid field.
- [ ] `KeyedFeatureExtractOp`'s feature computation (`ema_engagement`,
      `pv_count`, `recency_norm`, etc.) never branches on, reads, or is
      influenced by `label`/`label_valid` — those fields exist purely as a
      pass-through for offline evaluation joining.
- [ ] Per-user event timestamps are strictly monotonically non-decreasing as
      processed (no future event's timestamp is ever used to compute a past
      event's feature).

**Audit command:**
```bash
grep -A 15 "struct RawBehaviorEvent" include/klstream/feature/types.hpp
grep -n "label" include/klstream/feature/keyed_feature_extract_op.hpp
```
**PASS:** `RawBehaviorEvent` has zero label-related fields; every `label`
reference inside `keyed_feature_extract_op.hpp` is a straight pass-through
assignment (`fs.label = ...`) never used in a conditional or arithmetic
expression that feeds `ema_engagement`, `pv_count`, or any other x[0..6]
feature value.
**FAIL:** any `if (label == ...)` or arithmetic use of label/label_valid
inside the feature-computation code path.

### 2.5 Synthetic-vs-Real Data Contamination Guard

**Risk:** This project's own development history includes at least one
concrete instance of a synthetic/wrong-file dataset producing a fully
plausible-looking but entirely invalid results set. A permanent structural
guard is required, not just post-hoc vigilance.

**Checklist**
- [ ] Every synthetic or fallback-generator output file is named with an
      unambiguous prefix (`synthetic_*`) — never a name that could be
      confused with a real-data replay file.
- [ ] Every results CSV embeds (as a header comment or companion manifest
      field) the checksum of the input replay file that produced it.
- [ ] `compute_metrics.py` refuses to include a run in any headline table
      unless its source-file checksum matches an explicit allow-list of
      real-data checksums.

**Audit command:**
```bash
find data/ results/ -iname "*synthetic*" -o -iname "*fallback*"
grep -rn "source_checksum\|input_file_hash" analysis/compute_metrics.py
```
**PASS:** naming convention is unambiguous throughout; `compute_metrics.py`
contains an explicit allow-list check before including any run in a headline
table.
**FAIL:** any historical or current ambiguity about which exact file produced
a cited number, or no allow-list/checksum gate exists in the metrics script.

### 2.6 Online/Offline Feature Parity Verification (Golden Test)

**Risk:** Feature Regret is fundamentally a *difference* between the online
(C++) system's score and the offline (Python) oracle's score. If the two
implementations of the same recursive feature formulas ever silently diverge
— which has concretely happened before in this project (a `seq` misalignment
bug and a ULB `behavior_code` vs `amount` mismatch bug both passed initial
review before being caught) — the headline metric is corrupted without any
visible symptom.

**Checklist**
- [ ] A dedicated golden-parity test exists: take the first N (e.g., 500)
      events for one user from a real replay file, recompute `ema_engagement`,
      `log_pv`, `log_cart_fav`, `recency_norm`, `buy_rate_ratio`,
      `log_buy_count`, `ema_recency` by hand in pure Python mirroring the
      exact recursive update formulas in `KeyedFeatureExtractOp`, and diff
      against the C++-produced values.
- [ ] This test runs as part of the standard test suite (`ctest`), not as a
      one-off manual script that could silently stop being run.

**Audit command:**
```python
# tests/golden_feature_parity.py — recommended if not already present
import pandas as pd, numpy as np

ENGAGEMENT_WEIGHT = {0: 1.0, 1: 3.0, 2: 2.0, 3: 5.0}

def recompute_features_python(events_for_one_user, alpha_trace):
    """Mirror KeyedFeatureExtractOp's exact recursion, event by event."""
    ema = 0.0
    pv = cart = fav = buy = 0
    prev_ts = None
    ema_recency = 0.0
    out = []
    for (row, alpha) in zip(events_for_one_user.itertuples(), alpha_trace):
        w = ENGAGEMENT_WEIGHT[row.behavior_code]
        ema = alpha * w + (1 - alpha) * ema
        if row.behavior_code == 0: pv += 1
        elif row.behavior_code == 1: cart += 1
        elif row.behavior_code == 2: fav += 1
        recency = 0.0 if prev_ts is None else min((row.timestamp_ns - prev_ts) / 1e9, 3600.0) / 3600.0
        ema_recency = alpha * recency + (1 - alpha) * ema_recency
        prev_ts = row.timestamp_ns
        out.append({'ema_engagement': ema, 'log_pv': np.log1p(pv),
                    'log_cart_fav': np.log1p(cart + fav), 'recency_norm': recency,
                    'ema_recency': ema_recency})
    return pd.DataFrame(out)

# Compare against the C++-produced FeatureSnapshot values for the same user/events
# (requires a debug build that dumps raw feature vectors, or reuse ResultSink's
# alpha_used/staleness_sec columns as a partial cross-check).
# ASSERT: max absolute difference < 1e-5 for every recomputed column.
```
**PASS:** golden parity test exists, is part of `ctest`, and passes with
divergence under 1e-5 for every feature column.
**FAIL:** no such test exists (this is the single highest-leverage missing
test given this project's specific bug history), or it exists but shows
unexplained divergence.

### 2.7 Manual Data Tampering Detection (Git Forensics)

**Risk:** The single most damaging finding a hostile or rigorous reviewer
could make is evidence that a results CSV was hand-edited rather than
regenerated by a script — the textbook definition of data fabrication.

**Checklist**
- [ ] Full git history of every file under `data/replay/` and `results/` is
      reviewed for commits that touch only a small number of numeric cells
      within an otherwise-unchanged CSV (a classic fabrication signature, as
      opposed to a full-file regeneration which changes byte size/row
      structure wholesale).
- [ ] Every commit touching a results file has a commit message referencing
      the script/command that regenerated it, not a bare "update results" or
      "fix numbers" message with no reproducible provenance.

**Audit command:**
```bash
git log --all --oneline -- 'results/**/*.csv' 'data/replay/*.csv'
# For any commit that looks suspicious (small diff, vague message), inspect directly:
git show <commit_hash> -- path/to/file.csv | head -100
git log --all --follow -p -- 'results/metrics_summary.csv' | grep -B5 -A5 "^[+-][0-9]"
```
**PASS:** every commit touching a results/data CSV corresponds to a full
script/binary regeneration (verifiable by consistent row-count/structure
changes and a commit message naming the exact command run); zero instances of
isolated numeric-cell edits.
**FAIL:** any commit shows a diff touching only a handful of cells in an
otherwise-static file, or any commit message is vague enough to make
provenance unverifiable.

---

## 3. Evaluation Rigor, Baseline Comparisons, & Bias Audit

### 3.1 Overfitting / Researcher Degrees of Freedom Detection

**Risk:** BPFeat's controller has no gradient-descent overfitting risk in the
classical sense, but its numeric constants (`shrink_factor`, `grow_factor`,
`occ_low`, `occ_high`, `alpha_min`, `alpha_max`, `w_min`, `w_max`) function
exactly like hyperparameters. If any were adjusted after observing real
Taobao results, the "default parameters sit in a stable plateau" claim
becomes circular — the plateau was found *because* the defaults were chosen
to sit inside it, not confirmed independently of the results that motivated
the choice.

**Checklist**
- [ ] Git history confirms every AIMD/IIR constant was set once, inherited
      unmodified from the prior validated project, **before** any Taobao
      experimental run — not adjusted iteratively while watching FR/PATR
      results come in.
- [ ] If any constant *was* adjusted after an initial real-data run, the
      exact before/after values and the reason are disclosed explicitly in
      the paper. Silent post-hoc tuning is disqualifying; disclosed tuning
      with a stated rationale is not.
- [ ] No evidence exists of "seed shopping" — running more than the reported
      5 seeds and selectively reporting only the favorable ones.
- [ ] The 90th-percentile burst-tagging threshold was fixed as an a priori
      methodological choice, not adjusted after seeing results to produce a
      more favorable burst/calm split.

**Audit command:**
```bash
git log -p --follow -- include/klstream/feature/adaptive_feature_window_op.hpp \
  include/klstream/feature/keyed_feature_extract_op.hpp | \
  grep -B5 -A2 "shrink_factor\s*=\|grow_factor\s*=\|occ_low\s*=\|occ_high\s*=\|alpha_min\s*=\|alpha_max\s*="

# Seed-shopping check: search every results directory for any seed value
# ever executed outside the reported 0-4 range.
grep -rhoP "seed[=_]?\K\d+" results/ 2>/dev/null | sort -n -u
```
**PASS:** every constant appears at its currently-shipped value across the
entire history, with any edits occurring strictly before the first commit
that added `data/replay/replay_taobao_10k.csv`; only seeds 0–4 appear
anywhere in the results tree.
**FAIL:** a constant is edited in a commit falling chronologically *between*
two experimental-run commits (a visible "run → observe → tune → re-run"
pattern) with no disclosure in the paper; any seed ≥5 appears anywhere in the
results tree without an explicit accounting of why it was excluded.

### 3.2 Baseline Strength — Is the RALF Surrogate Faithful or a Strawman?

**Risk:** RALF is the paper's single most important comparison (the 8.6×
regret ratio is the headline number). `RALFWindowOp` is a from-scratch C++
re-implementation of RALF's scheduling *policy*, not the published RALF
codebase — no publicly runnable RALF implementation exists to test directly
against Taobao. If this surrogate is weaker than a faithful reading of RALF's
actual mechanism, the comparison is "BPFeat vs. a strawman labeled RALF,"
not "BPFeat vs. RALF" — a serious, reviewer-catchable overclaim.

**Checklist**
- [ ] The surrogate's regret-estimation formula
      (`|Δema_engagement| × (staleness+1)`) is checked against RALF's actual
      published formalization (importance-weighted staleness cost) for
      structural fidelity; any simplification is documented explicitly.
- [ ] The surrogate's `budget_fraction` (0.50) was not arbitrarily chosen to
      make RALF look artificially starved — check whether the published RALF
      paper reports a comparable operating budget, and whether 0.50 needs its
      own sensitivity sweep to be defensible as representative.
- [ ] The RALF surrogate received **the same tuning effort** as BPFeat. If
      BPFeat's AIMD constants earned a 9-configuration sensitivity sweep
      before being called "robust," RALF's `budget_fraction` must receive an
      equivalent sweep (e.g., 0.3, 0.5, 0.7) before its single reported number
      is treated as representative of "what RALF can do." Asymmetric tuning
      effort — thorough for the contribution, none for the baseline — is one
      of the most common and most damaging baseline-strength critiques in
      systems-paper review.
- [ ] The paper explicitly labels this as "a RALF-inspired surrogate
      implementing RALF's core regret-proportional scheduling policy within
      our runtime" and does **not** claim to reproduce or outperform the
      published RALF system's own reported numbers on RALF's own benchmarks.

**Audit command:**
```bash
for budget in 0.3 0.5 0.7; do
  ./build/feature_flow/feature_flow_harness \
    --replay data/replay/replay_taobao_10k.csv --seeds 1 \
    --arch ralf --ralf-budget-fraction $budget \
    --out-dir results/ralf_budget_sweep/budget_${budget}/
done
```
**PASS:** a budget-fraction sweep exists showing RALF's FR/coverage tradeoff
across at least 3 settings, applied with the same sweep discipline as
BPFeat's own parameters; explicit "surrogate, not reproduction" disclosure is
present in the paper.
**FAIL:** only a single, untuned RALF configuration exists anywhere in the
evaluation while BPFeat receives a multi-point sweep — this asymmetry alone
is sufficient grounds for a reviewer to discount the comparison.

### 3.3 Baseline Strength — the Best-Possible-Static-Baseline Check

**Risk:** Fixed uses W=128 as "current practice." Under sustained load,
Adaptive converges to W=8. The obvious reviewer question: would a
non-adaptive system simply configured with a smaller static W (16, 32)
achieve comparable staleness/latency benefits with no control loop at all? If
so, the real comparison needed is against the *best* static W, not an
arbitrarily chosen one.

**Checklist**
- [ ] A sweep of Fixed at multiple static W values (8, 16, 32, 64, 128, 256)
      has been run, with FR/staleness/latency reported for each alongside
      Adaptive.
- [ ] Adaptive's calm-period cost (W→256, larger batches, less frequent
      publishing) is compared against the best-performing static-small-W
      baseline's calm-period cost — a small static W might match Adaptive's
      burst-period benefit but at the cost of unnecessary overhead
      year-round. This net tradeoff, not the burst-period comparison alone,
      is the actual test of whether adaptivity earns its complexity.

**Audit command:**
```bash
for w in 8 16 32 64 128 256; do
  ./build/feature_flow/feature_flow_harness \
    --replay data/replay/replay_causal_demo.csv --seeds 1 \
    --scoring-delay-us 500 --arch fixed --fixed-window-size $w \
    --out-dir results/static_w_sweep/w_${w}/
done
```
**PASS:** a static-W sweep exists; Adaptive's burst latency is compared
against the *best* static W in that sweep (not just W=128), and Adaptive's
calm-period cost is compared against that same best-static-W's calm cost,
with the net tradeoff reported honestly regardless of outcome.
**FAIL:** only W=128 is ever tested as "the" static baseline, with no sweep
demonstrating adaptivity's benefit beyond what a well-chosen constant already
achieves.

### 3.4 Baseline Parity Verification

**Checklist**
- [ ] All 7 architectures share: identical replay file, identical seed (per
      matched comparison), identical pretrained downstream model weights,
      identical worker/thread topology, identical queue capacities. The
      *only* variable across architectures is the window operator class and
      whether `KeyedFeatureExtractOp` receives a non-null `BackpressureSignal`.
- [ ] No architecture receives a warm-start or cached-state advantage the
      others do not.

**Audit command:**
```bash
grep -n "LogisticModel::load" feature_flow/main.cpp
# Confirm every architecture branch loads the SAME model-path variable,
# not a hardcoded distinct path per architecture, and that queue
# constructions (SPSCQueue<...>(N)) use identical capacities N across
# every switch-case branch.
```
**PASS:** a single shared model-path variable and identical queue
construction code across every switch-case branch in `main.cpp`/`harness.cpp`.
**FAIL:** any architecture-specific queue sizing, model file, or topology
deviation that is not the deliberate experimental variable itself.

### 3.5 Statistical Significance — Paired vs. Unpaired Comparison Requirement

**Risk:** the project's significance criterion has been "do the 95% MBB CIs
of two architectures overlap?" This is a real but statistically conservative
and imprecise proxy for a formal test. Since every architecture runs against
a near-identical event sequence (same seed, same replay, same burst
schedule), the correct and more powerful test is a **paired** difference:
compute `FR_A[seed_i] − FR_B[seed_i]` per seed (or per matched event window)
and bootstrap the paired difference directly, rather than comparing two
independently-constructed unpaired CIs. Overlapping unpaired CIs do not
straightforwardly imply "no significant difference" — this is a documented
statistical pitfall (Cumming & Finch, 2005, "Inference by Eye").

**Checklist**
- [ ] For every "X significantly outperforms Y" claim (BPFeat vs. RALF,
      BPFeat vs. Fixed), a paired-difference MBB bootstrap has been computed
      on matched per-seed or per-event differences — not an eyeball
      comparison of two separately-reported CIs.
- [ ] The B-only vs. Adaptive "statistically indistinguishable" claim
      (currently justified by CI overlap alone) is re-verified with a paired
      test: confirm the paired-difference CI actually contains zero before
      asserting equivalence — CI overlap is the *weaker* of the two claims.

**Audit command:**
```python
import numpy as np
from arch.bootstrap import MovingBlockBootstrap

def paired_fr_diff_ci(fr_a_per_event, fr_b_per_event, block_length=50, n_boot=1000):
    """Paired difference bootstrap -- the statistically correct comparison
    when both architectures score matched/near-matched events."""
    diff = fr_a_per_event - fr_b_per_event
    bs = MovingBlockBootstrap(block_length, diff)
    boot_means = bs.apply(lambda x: np.mean(x), n_boot)
    lo, hi = np.percentile(boot_means, [2.5, 97.5])
    return float(diff.mean()), float(lo), float(hi)

# PASS only if this is actually computed and reported for every equivalence
# or superiority claim -- not inferred from separately-reported, unpaired CIs.
```
**PASS:** every comparative claim in the paper is backed by an explicit
paired-difference bootstrap CI on matched data.
**FAIL:** comparative claims rest solely on "these two separately-computed
CIs do or don't overlap," with no paired-difference test computed anywhere.

### 3.6 Statistical Significance — MBB Block Length & Resample Count Sensitivity

**Checklist**
- [ ] The Hall et al. (1995) block-length heuristic (`max(10, n**0.25)`,
      giving 50 for n≈980K) is sanity-checked by recomputing the reported
      CIs at half and double that block length (25 and 100). A CI whose
      width or center shifts substantially is an artifact of the specific
      heuristic, not a robust estimate.
- [ ] Bootstrap resample count (B=600, per the project's own logs) meets or
      exceeds standard guidance for stable percentile-based CI edges. Efron &
      Tibshirani generally recommend B≥1000–2000 specifically for 2.5th/97.5th
      percentile estimation (as opposed to B≥200, which suffices only for the
      standard error). B=600 is on the low side for percentile stability.

**Audit command:**
```python
import numpy as np
from arch.bootstrap import MovingBlockBootstrap

for block_len in [25, 50, 100]:
    for B in [600, 1500]:
        bs = MovingBlockBootstrap(block_len, regret_per_event)  # from real data
        boot = bs.apply(lambda x: np.mean(x), B)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        print(f"block_len={block_len} B={B}: CI=[{lo:.5f}, {hi:.5f}] width={hi-lo:.5f}")
```
**PASS:** CI bounds are stable (relative width change <10%) across block
lengths {25, 50, 100} and resample counts {600, 1500}.
**FAIL:** CI bounds shift substantially with either parameter — report the
higher resample count and the widest (most conservative) CI observed across
the sweep in the final paper.

### 3.7 Seed-Level Replication vs. Within-Run Averaging (Pseudo-Replication Check)

**Risk:** MBB correctly handles temporal autocorrelation *within* one run's
980,885 events, but the actual number of independent experimental
replications — different random burst schedules, effectively different
"universes" of the same experiment — is 5 (the seed count). If the reported
"all_seeds_avg" CI pools every seed's events into one MBB resample, it
implicitly treats seeds as exchangeable continuations of one process rather
than as 5 independent draws whose own spread deserves separate reporting.
This risks pseudo-replication: a tight CI driven by 980K autocorrelation-
corrected events that conceals substantial seed-to-seed disagreement in the
underlying point estimate.

**Checklist**
- [ ] For every headline metric, the 5 individual per-seed point estimates
      are reported (not only the pooled mean ± MBB CI), so a reader can see
      the actual seed-to-seed spread directly.
- [ ] If the range across the 5 per-seed FR values for a given architecture
      is wider than the pooled MBB CI width, this is disclosed explicitly —
      it means true replication uncertainty exceeds the reported interval.

**Audit command:**
```python
import pandas as pd, glob

for arch in ['fixed', 'adaptive', 'ralf']:
    per_seed_fr = []
    for seed_file in sorted(glob.glob(f'results/raw/results_{arch}_seed*.csv')):
        per_seed_fr.append(compute_fr_single_seed(seed_file))  # scope FR to one seed only
    print(f"{arch}: per-seed FR = {per_seed_fr}, "
          f"range = {max(per_seed_fr)-min(per_seed_fr):.5f}")
```
**PASS:** per-seed point estimates are disclosed in a supplementary table;
their range is consistent with, not dramatically wider than, the pooled MBB
CI.
**FAIL:** per-seed values are never disclosed anywhere — only the pooled
"all_seeds_avg" number appears, and a reader cannot distinguish genuine
precision from pseudo-replicated confidence.

### 3.8 Absolute Performance Disclosure Requirement

**Risk:** Feature Regret is a *relative* metric (system BCE minus oracle
BCE). Reporting regret alone, without each architecture's *absolute*
AUROC/AUPRC/BCE, makes it impossible to sanity-check whether a favorable
regret number reflects genuinely good absolute performance or a coincidentally
weak oracle (compounding the 2.3 contamination concern).

**Checklist**
- [ ] Each of the 7 architectures' absolute AUROC (or AUPRC, given the class
      imbalance) is reported alongside its Feature Regret — not only the
      oracle's standalone AUROC (0.6557).
- [ ] Any architecture whose absolute AUROC is close to 0.50 despite a
      favorable regret number is flagged explicitly — a favorable *relative*
      regret paired with near-random *absolute* performance indicates the
      oracle itself is weak, not that the system is good.

**Audit command:**
```python
from sklearn.metrics import roc_auc_score
import pandas as pd, glob

for arch in ['fixed','drift','throttle','aonly','bonly','adaptive','ralf']:
    files = sorted(glob.glob(f'results/raw/results_{arch}_seed*.csv'))
    df = pd.concat([pd.read_csv(f) for f in files])
    valid = df[df['label_valid'] == 1]
    auroc = roc_auc_score(valid['label'], valid['score'])
    print(f"{arch}: absolute AUROC = {auroc:.4f}")
```
**PASS:** absolute AUROC is reported per architecture in the paper's results
table; no architecture's favorable regret appears paired with a near-random
absolute AUROC without explicit comment.
**FAIL:** only relative Feature Regret is ever reported, with no absolute
accuracy check available anywhere in the paper.

---

**Section 4 is: Code Integrity & Licensing Audit** — covering borrowed
open-source code attribution, license compatibility with IEEE publishing
policy (MIT/Apache-2.0/GPL/BSD interactions), and structural checks for
hardcoded shortcuts that could bypass genuine algorithmic computation (e.g.,
any code path that could special-case known inputs rather than computing
them honestly). Prompt me to continue when ready.
