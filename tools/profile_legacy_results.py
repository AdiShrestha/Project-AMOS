#!/usr/bin/env python3
"""Full numeric/schema checks of historical CSVs. Never admits research evidence.

Audit-only dependency: pandas and numpy, recorded in the audit environment.
Scientific source linkage and correctness are not inferred from file names.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd


def profile(path):
    with path.open(newline="") as stream:
        header = next(csv.reader(stream), [])
    result = {"path": str(path), "columns": header, "rows": 0,
              "nonfinite_numeric_cells": {}, "invalid_domains": {}, "duplicate_seq": 0}
    if not header:
        result["empty_file"] = True
        return result
    nonfinite, domains, seen = Counter(), Counter(), set()
    try:
        for chunk in pd.read_csv(path, chunksize=100000):
            result["rows"] += len(chunk)
            for name in header:
                if name in {"arch"}:
                    continue
                numbers = pd.to_numeric(chunk[name], errors="coerce").to_numpy(dtype=float)
                nonfinite[name] += int((~np.isfinite(numbers)).sum())
                if name == "score":
                    domains[name] += int(((numbers < 0) | (numbers > 1)).sum())
                if name in {"label", "label_valid", "is_burst", "is_burst_period"}:
                    domains[name] += int((~np.isin(numbers, [0, 1])).sum())
                if name in {"seq", "user_id", "latency_ns", "staleness_sec", "wall_ns", "result_wall_ns", "result_timestamp_ns"}:
                    domains[name] += int((numbers < 0).sum())
            if "seq" in chunk:
                for sequence in chunk["seq"]:
                    if sequence in seen:
                        result["duplicate_seq"] += 1
                    seen.add(sequence)
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    result["nonfinite_numeric_cells"] = {k: v for k, v in nonfinite.items() if v}
    result["invalid_domains"] = {k: v for k, v in domains.items() if v}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    files = []
    for index, path in enumerate(sorted((args.root / "results").rglob("*.csv")), 1):
        row = profile(path)
        row["path"] = str(path.relative_to(args.root))
        files.append(row)
        if index % 25 == 0:
            print("CSV files fully profiled", index, flush=True)
    report = {"purpose": "historical artifact diagnostics, not research results", "files": files,
              "summary": {"files": len(files), "rows": sum(r["rows"] for r in files),
                          "header_only_files": sum(r["rows"] == 0 and bool(r["columns"]) for r in files),
                          "files_with_errors": sum("error" in r for r in files),
                          "files_with_nonfinite_cells": sum(bool(r["nonfinite_numeric_cells"]) for r in files),
                          "files_with_duplicate_seq": sum(r["duplicate_seq"] > 0 for r in files)},
              "limits": "Numeric checks, not source identity, provenance, outcome correctness, exact timestamp arithmetic or statistical validation."}
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
