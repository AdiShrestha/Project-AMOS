#!/usr/bin/env python3
"""Read-only byte inventory and bounded content inspection of a legacy tree.

Every regular file outside .git is hashed in full. CSV row counts are physical
line counts; sampled cells are not a full row-level validation. No source is run.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PATTERNS = {
    "synthetic_or_fixture": r"synthetic|fixture|mock|fabricat|placeholder",
    "fallback": r"fallback|except\s*:|catch\s*\(\.\.\.\)|zero model",
    "claim_or_status": r"ADMITTED|BLOCKED_HUMAN|PASS|COMPLETE|CERTIF|confirmed|significant|equivalen",
    "selection_or_leakage": r"train_test_split|grid.search|stratif|oracle|holdout|oof|censor",
    "hardware_or_literal": r"M1 Max|25\.0|1700000000000000000|0\.683|0\.6557|0\.70 for",
}


def digest_file(path):
    h = hashlib.sha256()
    lines = 0
    last = b""
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
            lines += chunk.count(b"\n")
            last = chunk[-1:]
    return h.hexdigest(), lines + int(bool(last) and last != b"\n")


def reject_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def inspect_csv(path, include_samples=False):
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader, [])
        rows = []
        for _, row in zip(range(32), reader):
            rows.append(row)
    result = {"inspection": "first record plus first 32 subsequent records only; source values omitted by default"}
    if path.name == "UserBehavior.csv":
        result["first_record"] = ["user_id", "item_id", "category_id", "behavior", "timestamp_seconds"]
        result["first_record_is_source_header"] = False
    else:
        result["first_record"] = header
    if include_samples:
        result["sample_records"] = rows
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--include-samples", action="store_true", help="private local diagnostics only")
    args = parser.parse_args()
    root = args.root.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    records, content = [], []
    by_top, sizes = Counter(), Counter()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        if path.is_symlink():
            records.append({"path": str(relative), "type": "symlink", "target": str(path.readlink())})
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        record = {"path": str(relative), "type": "regular", "size_bytes": size}
        try:
            record["sha256"], record["physical_lines"] = digest_file(path)
            record["coverage"] = "complete byte hash"
            if path.suffix.lower() == ".csv":
                record["csv"] = inspect_csv(path, args.include_samples)
            elif size <= 3 * 1024 * 1024 and "__pycache__" not in relative.parts:
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeError:
                    record["content_kind"] = "binary"
                else:
                    record["content_kind"] = "utf8"
                    findings = []
                    for line_no, line in enumerate(text.splitlines(), 1):
                        keys = [key for key, pattern in PATTERNS.items() if re.search(pattern, line, re.I)]
                        if keys:
                            findings.append({"line": line_no, "categories": keys, "text": line[:500]})
                    item = {"path": str(relative), "headings": re.findall(r"(?m)^#{1,6} .+$", text),
                            "matches": findings}
                    if path.suffix == ".json":
                        try:
                            parsed = json.loads(text, object_pairs_hook=reject_pairs,
                                                parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                            item["json_type"] = type(parsed).__name__
                            if isinstance(parsed, dict):
                                item["top_keys"] = list(parsed)
                                item["status_fields"] = {k: v for k, v in parsed.items()
                                                         if k in ("status", "outcome", "execution_status", "gate", "verdict")}
                        except ValueError as exc:
                            item["json_error"] = str(exc)
                    content.append(item)
        except OSError as exc:
            record["error"] = str(exc)
        records.append(record)
        by_top[relative.parts[0]] += 1
        sizes[relative.parts[0]] += size
        if len(records) % 200 == 0:
            print("inventoried", len(records), "files", flush=True)
    summary = {"schema": "bpfeat.audit.inventory.v1", "root_at_audit": str(root),
               "created_at_utc": datetime.now(timezone.utc).isoformat(),
               "regular_file_count": sum(r["type"] == "regular" for r in records),
               "bytes": sum(r.get("size_bytes", 0) for r in records),
               "counts_by_top": dict(by_top), "bytes_by_top": dict(sizes),
               "errors": [r for r in records if "error" in r],
               "limits": ["Git internals excluded; Git commit/ref inventory is separate.",
                          "CSV physical lines are not logical row validation.",
                          "CSV inspection is bounded; text pattern matches are triage, not semantic proof.",
                          "Hashes and metadata cannot establish provider authenticity."]}
    for name, obj in [("inventory.json", records), ("content_index.json", content), ("summary.json", summary)]:
        (args.output / name).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
