# Clean-Checkout Reproduction Guide

**Project**: BPFeat / Project AMOS  
**Scope**: Independent Third-Party Evaluator Walkthrough  
**Document**: `docs/research/REPRODUCTION.md`

---

## 1. Overview & Trust Model

This document provides a deterministic, self-contained reproduction walkthrough for Project AMOS. It enables an independent peer evaluator to clone the public repository, verify input dataset provenance, build native engine binaries from source, execute test suites, replay confirmatory empirical measurements, and verify reproduction metrics within $\le 10^{-5}$ numerical tolerance.

### 1.1 Local Trust Model & Assurance Boundaries
- **Operating Environment**: Assumes a standard POSIX developer workstation (macOS or Linux).
- **Process Isolation**: All evaluation scripts run strictly within the repository workspace. No network egress is initiated during evaluation replay.
- **Dataset Provenance**: Evaluation records originate from the author-declared e-commerce stream dataset ([Tianchi User Behavior](https://tianchi.aliyun.com/dataset/dataDetail?dataId=649)). Data files and model checkpoints are cryptographically bound via SHA-256 digests.
- **Licensing & Terms**: Evaluators must adhere to the author-declared academic terms disclosed in `docs/research/`.

---

## 2. System Prerequisites

The following software packages are required:
- **Operating System**: macOS (ARM64 / x86_64) or Linux (x86_64 / aarch64).
- **C++ Compiler**: Apple Clang $\ge 14.0$ or GCC / Clang supporting C++20 standard.
- **Build System**: CMake $\ge 3.20$ and Make or Ninja.
- **Python**: Python $\ge 3.10$ (Python 3.12 recommended).
- **Python Dependencies**:
  - `pytest`
  - Standard library modules (`argparse`, `csv`, `datetime`, `hashlib`, `json`, `math`, `pathlib`, `subprocess`).

---

## 3. Step-by-Step Reproduction Instructions

### Step 3.1: Clone the Repository
```bash
git clone https://github.com/AdiShrestha/Project-AMOS.git
cd Project-AMOS
```

### Step 3.2: Verify Dataset & Model Integrity
Before executing any benchmarks, verify that all input datasets and model weights match their authentic cryptographic digests:
```bash
python3 -c "
import hashlib
from pathlib import Path

expected = {
    'data/cohort.csv': '09604868b0fbc0811b75b68db56949c6d001080c360ff5b5d412ba5f36c4e68a',
    'data/models/logistic_model.txt': 'f58bf67831f048d20fe70d6cea0a9055bf93e995e27852fb28712f9d1818510f',
}

for path, digest in expected.items():
    p = Path(path)
    if not p.exists():
        print(f'[MISSING] {path}')
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == digest, f'Hash mismatch on {path}: got {h}'
    print(f'[VERIFIED] {path} -> {h[:16]}...')
"
```

### Step 3.3: Build Native Engine Targets
Configure and compile native C++ targets under Debug or Release profiles:
```bash
cmake -B build/debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build/debug --parallel
```

Run native engine counterexample and verification checks:
```bash
ctest --test-dir build/debug --output-on-failure
```
*Expected Result*: `100% tests passed out of 2`.

### Step 3.4: Execute the Python Regression Test Suite
Run the full test suite including canonicalization, causal labeling, streaming adapters, baselines, and robustness checks:
```bash
PYTHONPATH=. pytest tests/ -v
```
*Expected Result*: All tests pass (100% passing).

### Step 3.5: Execute the Standalone Reproduction Verifier
Run the standalone metric verifier to independently recalculate all 12 primary headline metrics, hypothesis test contrasts, and lineage items:
```bash
python3 -B tools/reproduction_verifier.py \
  --cohort data/cohort.csv \
  --confirmatory-results docs/research/confirmatory_results.json \
  --robustness-results docs/research/robustness_analysis.json \
  --output-manifest docs/research/reproduction_manifest.json \
  --output-per-number docs/research/per_number_manifest.json \
  --tolerance 1e-05
```

*Expected JSON Output*:
```json
{
  "status": "PASS",
  "cohort_integrity": "VERIFIED",
  "cohort_sha256": "09604868b0fbc0811b75b68db56949c6d001080c360ff5b5d412ba5f36c4e68a",
  "model_sha256": "f58bf67831f048d20fe70d6cea0a9055bf93e995e27852fb28712f9d1818510f",
  "reproduction_manifest": "docs/research/reproduction_manifest.json",
  "per_number_manifest": "docs/research/per_number_manifest.json",
  "metrics_verified": 12,
  "lineage_items_cataloged": 13,
  "tolerance": 1e-05
}
```

---

## 4. Key Reproducibility Deliverables

1. **`docs/research/reproduction_manifest.json`**:
   - Contains pairwise `original` and `replay` values across all 12 headline metrics.
   - Strict numerical equality holds within the declared tolerance of $10^{-5}$.
2. **`docs/research/per_number_manifest.json`**:
   - Itemized catalogue mapping every reported number in tables, text claims, and failure analyses to its exact mathematical formulation, source artifact, raw prediction file, and CLI reproduction command.
3. **`scripts/reproduce_all.sh`**:
   - Automated end-to-end bash script that executes build, tests, and verifier replay in a single command.

---

## 5. Automated One-Command Reproduction

For fully unattended verification, run:
```bash
bash scripts/reproduce_all.sh
```
This script executes configuration, native compilation, native tests, pytest regression checks, and metric verification sequentially. It exits with code 0 upon total success.
