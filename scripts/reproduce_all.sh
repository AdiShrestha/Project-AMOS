#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# reproduce_all.sh: Automated Clean-Checkout End-to-End Reproduction Pipeline
# Project: BPFeat / Project AMOS
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

echo "======================================================================"
echo " Starting Full End-to-End Reproduction for BPFeat"
echo " Workspace: ${ROOT_DIR}"
echo "======================================================================"

# Step 1: Verify input datasets and model digests
echo ""
echo "[Step 1/5] Verifying dataset and model cryptographic digests..."
python3 -c "
import hashlib
from pathlib import Path
import sys

expected = {
    'data/cohort.csv': '09604868b0fbc0811b75b68db56949c6d001080c360ff5b5d412ba5f36c4e68a',
    'data/models/logistic_model.txt': 'f58bf67831f048d20fe70d6cea0a9055bf93e995e27852fb28712f9d1818510f',
}

for path, digest in expected.items():
    p = Path(path)
    if not p.exists():
        print(f'[ERROR] Missing required file: {path}', file=sys.stderr)
        sys.exit(1)
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if h != digest:
        print(f'[ERROR] Digest mismatch on {path}: got {h}, expected {digest}', file=sys.stderr)
        sys.exit(1)
    print(f'  [PASS] {path} matches digest {h[:16]}...')
"

# Step 2: Build native C++ targets
echo ""
echo "[Step 2/5] Building native C++ engine targets..."
cmake -B build/debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build/debug --parallel

# Step 3: Run native engine checks
echo ""
echo "[Step 3/5] Running native engine ctest suite..."
ctest --test-dir build/debug --output-on-failure

# Step 4: Run full Python pytest test suite
echo ""
echo "[Step 4/5] Executing full test suite..."
PYTHONPATH=. pytest tests/ -v

# Step 5: Execute standalone reproduction verifier
echo ""
echo "[Step 5/5] Replaying confirmatory metrics and checking tolerance..."
python3 -B tools/reproduction_verifier.py \
  --cohort data/cohort.csv \
  --confirmatory-results docs/research/confirmatory_results.json \
  --robustness-results docs/research/robustness_analysis.json \
  --output-manifest docs/research/reproduction_manifest.json \
  --output-per-number docs/research/per_number_manifest.json \
  --tolerance 1e-05

echo ""
echo "======================================================================"
echo " REPRODUCTION PIPELINE COMPLETE: ALL CHECKS PASSED (STATUS: SUCCESS)"
echo "======================================================================"
