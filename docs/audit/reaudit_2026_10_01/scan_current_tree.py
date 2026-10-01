"""Byte/line inventory and static triage; does not validate scientific evidence.

Run from the repository root after verification. Outputs exclude themselves
and validation.json to avoid self-referential hashes. No legacy code executes.
"""
import ast
import hashlib
import json
import math
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def finite(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite JSON number")
    return result


def role(name):
    if name.startswith("factory/legacy/"):
        return "archived_factory_not_active"
    if name.startswith(("docs/audit/legacy/", "docs/audit/probes/")):
        return "legacy_audit_record_or_counterexample_not_research"
    if name.startswith("docs/research/BPfeat_deep_research_supplied"):
        return "untrusted_supplied_research_assessment"
    if name.startswith(("tests/", "factory/tests/")):
        return "software_fixture_not_research"
    if name.startswith("source/"):
        return "active_engine_or_reference"
    if name.startswith("factory/"):
        return "active_factory_or_governance"
    if name.startswith("tools/"):
        return "audit_tool_not_research_runner"
    if name.startswith(("docs/FORENSIC", "docs/v26", "docs/audit_tools/")):
        return "supplied_other_project_factory_example_not_amos"
    if name.startswith("docs/audit/"):
        return "dated_audit_artifact_not_research"
    return "planning_document_or_project_configuration"


def main():
    root = Path.cwd()
    output = root / "docs/audit/reaudit_2026_10_01"
    excluded = {str((output / name).relative_to(root)) for name in
                ("current_tree_inventory.json", "current_tree_scan.json", "validation.json")}
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    ).decode("utf-8").split("\0")
    names = sorted(set(names) - excluded - {""})
    patterns = {
        "nonfinite_or_missing_token": re.compile(r"\b(?:nan|infinity|REPLACE_ME|TODO|N/A)\b", re.I),
        "randomness_or_seed": re.compile(r"\b(?:random|seed|synthetic|fixture)\b", re.I),
        "assurance_or_result": re.compile(r"\b(?:PASS|COMPLETED|certif\w*|oracle|confirmed)\b", re.I),
        "assert_or_literal_score": re.compile(r"\bassert\b|(?:score|latency|auroc)\s*[=:]\s*[0-9]", re.I),
    }
    files, problems, counts = [], [], Counter()
    for name in names:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("unexpected nonregular Git-visible path: " + name)
        data = path.read_bytes()
        record = {"path": name, "role": role(name), "bytes": len(data),
                  "sha256": hashlib.sha256(data).hexdigest(),
                  "physical_lines": data.count(b"\n") + int(bool(data) and not data.endswith(b"\n")),
                  "manual_semantic_review_certified": False}
        counts[record["role"]] += 1
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            record["text_scan"] = "binary_byte_inventory_only"
        else:
            record["text_scan"] = "all_physical_lines_pattern_triaged_not_semantically_proven"
            record["pattern_lines"] = {label: [i for i, line in enumerate(text.splitlines(), 1)
                                                if pattern.search(line)]
                                       for label, pattern in patterns.items()}
            try:
                if name.endswith(".py"):
                    ast.parse(text, filename=name)
                    record["syntax_check"] = "PYTHON_AST_VALID_NO_EXECUTION"
                if name.endswith(".json"):
                    json.loads(text, object_pairs_hook=unique, parse_float=finite,
                               parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                    record["syntax_check"] = "STRICT_JSON_VALID_NOT_DOMAIN_ADMISSION"
            except (SyntaxError, ValueError) as error:
                record["syntax_check"] = "FAILED"
                problems.append({"path": name, "error": str(error), "role": role(name)})
        files.append(record)
    stamp = datetime.now(timezone.utc).isoformat()
    inventory = {"schema": "bpfeat.current_audit_inventory.v1", "created_at_utc": stamp,
                 "research_evidence": False, "self_reference_exclusions": sorted(excluded),
                 "other_exclusions": "Git internals, ignored builds/raw data/keys/state/bulk outputs",
                 "files": files}
    summary = {"schema": "bpfeat.current_audit_scan.v1", "created_at_utc": stamp,
               "research_evidence": False, "files": len(files),
               "bytes": sum(record["bytes"] for record in files),
               "physical_lines": sum(record["physical_lines"] for record in files),
               "roles": dict(sorted(counts.items())), "syntax_problems": problems,
               "scope": "full byte hashes/line counts/text pattern triage and static Python/JSON checks; not semantic proof"}
    for name, value in (("current_tree_inventory.json", inventory), ("current_tree_scan.json", summary)):
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summary, indent=2, allow_nan=False))
    if problems:
        raise SystemExit("Static scan found syntax issues; inspect without rewriting archival evidence.")


if __name__ == "__main__":
    main()
