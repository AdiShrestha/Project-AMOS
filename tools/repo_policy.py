#!/usr/bin/env python3
"""
repo_policy.py - Repository structure and governance policy checker for BPFeat.

Contract: C01-06 (Repaired in C02-01 per fix_package.md)
Factory Version: 2.2.0
"""

import argparse
import json
import os
import re
import subprocess
import sys

DEFAULT_MAX_SIZE_BYTES = 1048576  # 1 MiB

ALLOWED_SCHEMAS_FIXTURES_PREFIXES = [
    "data/schemas/",
    "data/fixtures/",
    "tests/fixtures/",
    "models/schemas/",
    "artifacts/schemas/",
    "artifacts/manifests/",
    "tools/tests/fixtures/"
]

RELEASE_TEXT_EXTENSIONS = {
    ".md", ".txt", ".tex", ".bib", ".json", ".yaml", ".yml", ".cmake", ".cpp", ".hpp", ".h", ".py", ".sh"
}

FORBIDDEN_TRACKED_PATTERNS = [
    r"^factory/",
    r"^project/",
    r"^DROP_HERE/",
    r"^TAKE_THIS/",
    r"^revised_software/factory/",
    r"^revised_software/project/"
]

BUILD_CACHE_PATTERNS = [
    r"^build/",
    r"^build-.*/",
    r"__pycache__/",
    r"\.py[cod]$",
    r"\.(o|a|so|dylib|dll|exe)$",
    r"CMakeCache\.txt$",
    r"CMakeFiles/",
    r"\.DS_Store$"
]

RAW_GENERATED_PATTERNS = [
    r"^data/raw/",
    r"^results/runs/",
    r"^results/archive/",
    r"\.csv\.gz$",
    r"\.joblib$",
    r"^models/.*\.txt$"
]

CLOSED_SET_DISPOSITIONS = {
    "A_CANONICAL_SOURCE",
    "B_PUBLIC_METADATA",
    "C_CERTIFIED_ARTIFACT",
    "D_FIXTURE",
    "E_EXTERNAL_IMMUTABLE",
    "F_GOVERNANCE",
    "G_HISTORICAL_MIGRATION",
    "H_DISPOSABLE_LOCAL",
    "I_RESTRICTED_SECRET"
}

def check_policy(repo_dir, inventory_path=None, max_size_bytes=DEFAULT_MAX_SIZE_BYTES):
    repo_dir = os.path.abspath(repo_dir)
    findings = []

    # 1. Inspect Tracked Files from git ls-files
    try:
        tracked_out = subprocess.check_output(["git", "ls-files", "-z"], cwd=repo_dir)
        tracked_files = [p for p in tracked_out.decode("utf-8", errors="replace").split("\0") if p]
    except Exception as e:
        findings.append({
            "rule_id": "POLICY-ERROR",
            "path": ".",
            "severity": "HARD_VIOLATION",
            "message": f"Failed to execute git ls-files: {e}",
            "remediation": "Ensure repository is a valid Git repository."
        })
        return findings

    for path in tracked_files:
        # POLICY-001: Forbidden tracked Factory/governance/handoff paths
        for pat in FORBIDDEN_TRACKED_PATTERNS:
            if re.search(pat, path):
                findings.append({
                    "rule_id": "POLICY-001",
                    "path": path,
                    "severity": "HARD_VIOLATION",
                    "message": f"Tracked path matches forbidden governance/factory pattern '{pat}'.",
                    "remediation": "Remove path from outer Git index using git rm --cached in C01-04."
                })
                break

        # POLICY-002: Build/cache/bytecode output tracked
        for pat in BUILD_CACHE_PATTERNS:
            if re.search(pat, path):
                findings.append({
                    "rule_id": "POLICY-002",
                    "path": path,
                    "severity": "HARD_VIOLATION",
                    "message": f"Tracked path matches build/cache/bytecode pattern '{pat}'.",
                    "remediation": "Untrack build artifact and ensure ignore pattern is active."
                })
                break

        # POLICY-003: Raw/full generated artifact tracked outside explicit allowlist
        is_allowed_fixture = any(path.startswith(prefix) for prefix in ALLOWED_SCHEMAS_FIXTURES_PREFIXES)
        if not is_allowed_fixture:
            for pat in RAW_GENERATED_PATTERNS:
                if re.search(pat, path):
                    findings.append({
                        "rule_id": "POLICY-003",
                        "path": path,
                        "severity": "HARD_VIOLATION",
                        "message": f"Raw/generated dataset or model artifact tracked without allowlist: '{pat}'.",
                        "remediation": "Externalize artifact to immutable storage and remove from Git index in C01-04."
                    })
                    break

        # POLICY-004: File size check
        full_path = os.path.join(repo_dir, path)
        if os.path.exists(full_path) and not os.path.islink(full_path):
            size = os.path.getsize(full_path)
            if size > max_size_bytes and not is_allowed_fixture:
                findings.append({
                    "rule_id": "POLICY-004",
                    "path": path,
                    "severity": "HARD_VIOLATION",
                    "message": f"File size ({size} bytes) exceeds limit ({max_size_bytes} bytes).",
                    "remediation": "Externalize large file or add explicit exception with checksum."
                })

    # 2. Symlink Auditing (POLICY-005)
    for root, dirs, files in os.walk(repo_dir):
        if ".git" in dirs:
            dirs.remove(".git")
        if "project" in dirs and os.path.isdir(os.path.join(root, "project", ".git")):
            dirs.remove("project")
            
        for name in files + dirs:
            full_p = os.path.join(root, name)
            if os.path.islink(full_p):
                rel_p = os.path.relpath(full_p, repo_dir)
                target = os.readlink(full_p)
                if not target.startswith("/"):
                    target_full = os.path.normpath(os.path.join(root, target))
                else:
                    target_full = target
                if not os.path.exists(target_full):
                    findings.append({
                        "rule_id": "POLICY-005",
                        "path": rel_p,
                        "severity": "HARD_VIOLATION",
                        "message": f"Broken symlink pointing to missing target '{target}'.",
                        "remediation": "Remove broken symlink or restore valid target."
                    })

    # 3. Absolute local path scan in release-facing files (POLICY-006)
    author_path_pattern = re.compile(r"/(Users|home|private)/[a-zA-Z0-9_\-\.]+")
    scan_dirs = ["source", "include", "feature_flow", "paper", "docs", "scripts"]
    files_to_scan = ["README.md", "CMakeLists.txt", "CMakePresets.json"]
    
    for d in scan_dirs:
        full_d = os.path.join(repo_dir, d)
        if os.path.isdir(full_d):
            for root, dirs, files in os.walk(full_d):
                if ".git" in dirs:
                    dirs.remove(".git")
                for fn in files:
                    ext = os.path.splitext(fn)[1]
                    if ext in RELEASE_TEXT_EXTENSIONS or fn in ["CMakeLists.txt"]:
                        files_to_scan.append(os.path.relpath(os.path.join(root, fn), repo_dir))

    for rel_p in set(files_to_scan):
        full_p = os.path.join(repo_dir, rel_p)
        if os.path.isfile(full_p):
            try:
                with open(full_p, "r", encoding="utf-8", errors="replace") as f:
                    for line_no, line in enumerate(f, 1):
                        match = author_path_pattern.search(line)
                        if match:
                            matched_text = match.group(0)
                            findings.append({
                                "rule_id": "POLICY-006",
                                "path": f"{rel_p}:{line_no}",
                                "severity": "HARD_VIOLATION",
                                "message": f"Author-local absolute filesystem path detected: '{matched_text[:12]}...'",
                                "remediation": "Replace author-local absolute path with repo-relative path or environment variable."
                            })
                            break
            except Exception as e:
                findings.append({
                    "rule_id": "POLICY-006-ERROR",
                    "path": rel_p,
                    "severity": "HARD_VIOLATION",
                    "message": f"Failed to read file during absolute path scan: {e}",
                    "remediation": "Check file permissions and readability."
                })

    # 4. Duplicate Implementation Roots (POLICY-007)
    if os.path.isdir(os.path.join(repo_dir, "source", "include", "klstream")) and os.path.isdir(os.path.join(repo_dir, "include", "klstream")):
        findings.append({
            "rule_id": "POLICY-007",
            "path": "include/klstream vs source/include/klstream",
            "severity": "HARD_VIOLATION",
            "message": "Duplicate implementation roots detected between include/klstream and source/include/klstream.",
            "remediation": "Consolidate into canonical source/ root in C01-03."
        })

    # 5. Admitted Compact Artifact Manifest Check (POLICY-008)
    release_dir = os.path.join(repo_dir, "artifacts", "release")
    if os.path.isdir(release_dir):
        for fn in os.listdir(release_dir):
            if fn != "README.md":
                manifest_file = os.path.join(repo_dir, "artifacts", "manifests", f"{fn}.manifest.json")
                if not os.path.isfile(manifest_file):
                    findings.append({
                        "rule_id": "POLICY-008",
                        "path": f"artifacts/release/{fn}",
                        "severity": "HARD_VIOLATION",
                        "message": f"Admitted release artifact missing manifest '{manifest_file}'.",
                        "remediation": "Generate schema-validated manifest before admitting release artifact."
                    })
                else:
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as mf:
                            mdata = json.load(mf)
                        required_fields = ["schema_version", "artifact_path", "sha256", "byte_size", "source_revision"]
                        missing_fields = [rf for rf in required_fields if rf not in mdata]
                        if missing_fields:
                            findings.append({
                                "rule_id": "POLICY-008",
                                "path": f"artifacts/manifests/{fn}.manifest.json",
                                "severity": "HARD_VIOLATION",
                                "message": f"Release manifest missing required fields: {missing_fields}",
                                "remediation": "Populate all required fields in release manifest."
                            })
                    except Exception as e:
                        findings.append({
                            "rule_id": "POLICY-008",
                            "path": f"artifacts/manifests/{fn}.manifest.json",
                            "severity": "HARD_VIOLATION",
                            "message": f"Malformed release manifest JSON: {e}",
                            "remediation": "Fix syntax and structure of release manifest."
                        })

    # 6. Inventory Disposition Check (POLICY-009)
    if inventory_path and os.path.isfile(inventory_path):
        try:
            with open(inventory_path, "r", encoding="utf-8") as f:
                inv = json.load(f)
            for file_rec in inv.get("files", []):
                disp = file_rec.get("disposition_class")
                if not disp or disp not in CLOSED_SET_DISPOSITIONS:
                    findings.append({
                        "rule_id": "POLICY-009",
                        "path": file_rec.get("path", "unknown"),
                        "severity": "HARD_VIOLATION",
                        "message": f"Inventoried file has missing or invalid disposition '{disp}'.",
                        "remediation": "Assign explicit closed-set disposition from C01-01 taxonomy."
                    })
        except Exception as e:
            findings.append({
                "rule_id": "POLICY-009",
                "path": inventory_path,
                "severity": "HARD_VIOLATION",
                "message": f"Failed to parse inventory JSON: {e}",
                "remediation": "Regenerate valid inventory JSON in C01-01."
            })

    return findings

def main():
    parser = argparse.ArgumentParser(description="Repository structure and policy validator.")
    parser.add_argument("--repo", default=".", help="Repository root directory")
    parser.add_argument("--inventory", default=None, help="Path to C01-01 inventory JSON")
    parser.add_argument("--max-size-bytes", type=int, default=DEFAULT_MAX_SIZE_BYTES, help="Maximum allowed file size in bytes")
    parser.add_argument("--json-output", default=None, help="Optional output path for JSON findings")
    args = parser.parse_args()

    repo_dir = os.path.abspath(args.repo)
    print(f"[repo_policy] Running policy checks on {repo_dir} (Max size: {args.max_size_bytes} bytes)...")
    
    findings = check_policy(repo_dir, inventory_path=args.inventory, max_size_bytes=args.max_size_bytes)
    
    hard_violations = [f for f in findings if f["severity"] == "HARD_VIOLATION"]
    warnings = [f for f in findings if f["severity"] == "WARNING"]
    
    print(f"[repo_policy] Findings: {len(hard_violations)} hard violation(s), {len(warnings)} warning(s).")
    for f in findings:
        print(f"  [{f['severity']}] {f['rule_id']} at {f['path']}: {f['message']}")

    if args.json_output:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_output)), exist_ok=True)
        with open(args.json_output, "w", encoding="utf-8") as out_f:
            json.dump({"findings": findings, "hard_count": len(hard_violations), "warning_count": len(warnings)}, out_f, indent=2)

    if hard_violations:
        print("[repo_policy] Result: FAIL (Policy violations detected)")
        sys.exit(1)
    else:
        print("[repo_policy] Result: PASS (Repository clean under checked policies)")
        sys.exit(0)

if __name__ == "__main__":
    main()
