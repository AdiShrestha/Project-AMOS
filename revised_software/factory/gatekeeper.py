#!/usr/bin/env python3
"""
Factory Gatekeeper v1 -- deterministic validation only.
No AI reasoning. Every check returns a boolean backed by inspectable evidence.
Per gatekeeper_spec.md: PASS or FAIL only, no partial credit.
"""
import sys, json, hashlib, subprocess
from pathlib import Path


def check_repository_clean():
    result = subprocess.run(['git', 'status', '--porcelain'],
                             capture_output=True, text=True)
    clean = len(result.stdout.strip()) == 0
    return clean, result.stdout if not clean else "clean"


def check_frozen_file_hashes(frozen_manifest_path='revised_software/project/frozen_hashes.json'):
    """
    Verifies no Frozen File has been silently modified.
    Per Constitution C23 / Factory Spec Frozen File Validation.
    """
    p = Path(frozen_manifest_path)
    if not p.exists():
        return True, "no frozen-file manifest yet (expected before Chunk 01)"
    manifest = json.loads(p.read_text())
    mismatches = []
    for filepath, expected_hash in manifest.items():
        fp = Path(filepath)
        if not fp.exists():
            mismatches.append(f"{filepath}: MISSING")
            continue
        actual = hashlib.sha256(fp.read_bytes()).hexdigest()
        if actual != expected_hash:
            mismatches.append(f"{filepath}: hash mismatch "
                               f"(expected {expected_hash[:12]}..., got {actual[:12]}...)")
    return len(mismatches) == 0, mismatches or "all frozen files intact"


def check_no_stub_placeholder_returns(source_dirs=('revised_software/source',)):
    """
    Heuristic deterministic scan directly motivated by INV-007
    (a real, previously-confirmed bug: a per-seed metrics function silently
    returned 0.0 for every seed and every architecture instead of computing
    a real value, and this was presented as genuine output in a report).
    This is a heuristic candidate-flagging gate for Claude-level review,
    not a claim of full static-analysis correctness.
    """
    suspicious = []
    patterns = ['return 0.0  #', 'return 0  #', 'pass  # stub', 'NotImplementedError']
    for d in source_dirs:
        for f in Path(d).rglob('*.py'):
            text = f.read_text(errors='ignore')
            for pat in patterns:
                if pat in text:
                    suspicious.append(f"{f}: contains '{pat}'")
    return len(suspicious) == 0, suspicious or "no stub patterns detected"


def check_verdict_evidence_adjacency(report_paths):
    """
    Direct automation of the single most costly lesson from this project's
    audit history, observed independently across two separate audit
    reports: a stated Verdict (PASS/FAIL) with no adjacent quoted raw
    evidence justifying it, in the same document. This check does NOT
    verify a verdict is correct -- only that it is not floating disconnected
    from any evidence block at all, which was the exact, repeated failure
    mode that let fabricated verdicts pass undetected the first time.
    This is Dynamic Rule D-001 (see dynamic_rules.md) encoded as enforcement.
    """
    orphaned = []
    for report_path in report_paths:
        p = Path(report_path)
        if not p.exists():
            continue
        lines = p.read_text(errors='ignore').splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('**Verdict:**') or stripped.startswith('Verdict:'):
                window = lines[max(0, i - 15):i]
                if not any('output' in w.lower() or 'evidence' in w.lower()
                           or 'log file' in w.lower() for w in window):
                    orphaned.append(f"{report_path}:{i+1}: '{stripped}' "
                                     f"has no evidence/output block within 15 lines above it")
    return len(orphaned) == 0, orphaned or "no orphaned verdicts found"


def check_required_artifacts_exist(required):
    missing = [r for r in required if not Path(r).exists()]
    return len(missing) == 0, missing or "all required artifacts present"


def run_all_checks():
    # Find all report paths
    report_paths = []
    for p in Path('revised_software/project/chunks').glob('**/reports/*.md'):
        report_paths.append(str(p))

    checks = [
        ("repository_clean", check_repository_clean()),
        ("frozen_file_hashes", check_frozen_file_hashes()),
        ("no_stub_placeholder_returns", check_no_stub_placeholder_returns()),
        ("required_project_artifacts", check_required_artifacts_exist([
            'revised_software/project/project_description.md',
            'revised_software/project/architecture.md',
            'revised_software/project/project_knowledge.md',
            'revised_software/project/invariants.md',
            'revised_software/project/roadmap.md',
        ])),
        ("verdict_evidence_adjacency", check_verdict_evidence_adjacency(report_paths)),
    ]
    return checks


def main():
    checks = run_all_checks()
    lines = ["# Gatekeeper Report", "", "Factory Version: 1.0.1", ""]
    all_pass = True
    for name, (ok, evidence) in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        lines.append(f"## {name}: {status}")
        lines.append(f"Evidence: {evidence}")
        lines.append("")
    lines.append(f"## FINAL: {'PASS' if all_pass else 'FAIL'}")
    report = "\n".join(str(l) for l in lines)
    Path("revised_software/factory/gatekeeper_report.md").write_text(report)
    print(report)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
