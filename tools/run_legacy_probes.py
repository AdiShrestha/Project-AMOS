#!/usr/bin/env python3
"""Reproduce legacy counterexamples in temporary directories. No paper output."""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    root = Path(sys.argv[1]).resolve()
    here = Path(__file__).resolve().parents[1]
    output = here / "docs/audit/legacy_probe_results.json"
    with tempfile.TemporaryDirectory(prefix="bpfeat-audit-probes-") as temp:
        temp = Path(temp)
        command = ["clang++", "-std=c++17", "-pthread", "-I", str(root / "source/include"),
                   str(here / "docs/audit/probes/legacy_engine_probe.cpp"), "-o", str(temp / "probe")]
        compiled = subprocess.run(command, capture_output=True, text=True, check=True)
        native = subprocess.run([str(temp / "probe"), str(temp / "partial.txt")], capture_output=True,
                                text=True, check=True, timeout=10)
        spec = importlib.util.spec_from_file_location("legacy_orchestrator", root / "scripts/orchestrator.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        matrix = temp / "matrix.json"
        matrix.write_text(json.dumps({"runs": [{"run_id": "diagnostic_only", "architecture_id": "fixed_window_v1",
                                              "seed": 42, "repetition_type": "diagnostic", "repetition_index": 0,
                                              "events": 3}]}))
        orchestrator = module.ExperimentOrchestrator(matrix, temp / "runs", binary_path=temp / "does_not_exist")
        result = orchestrator.run_all()
        manifest = json.loads((temp / "runs/diagnostic_only_manifest.json").read_text())
        report = {"purpose": "legacy correctness counterexamples, not research results", "native_stdout": native.stdout,
                  "compiler_stderr": compiled.stderr, "orchestrator_with_missing_binary": result,
                  "orchestrator_manifest_environment": manifest["environment"],
                  "orchestrator_wall_time_ms": manifest["counters"]["wall_time_ms"],
                  "orchestrator_rows": (temp / "runs/diagnostic_only_results.csv").read_text()}
        # Exercise the legacy preprocessing implementation on an explicit fixture.
        spec = importlib.util.spec_from_file_location("legacy_preprocess", root / "source/preprocessing/preprocess_taobao.py")
        prep = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prep)
        import pandas as pd
        frame = pd.DataFrame({"user_id": [1, 1, 2, 2], "timestamp_ns": [0, 10**12, 0, 10**13],
                              "behavior_code": [3, 0, 0, 0]})
        report["self_buy_label_fixture"] = prep.compute_labels(frame).to_dict(orient="records")
        bins = pd.DataFrame({"timestamp_ns": [0, 0, 0, 60 * 10**9, 120 * 10**9]})
        report["burst_window_ignored"] = bool(prep.tag_burst_periods(bins, window_minutes=1).equals(
                                               prep.tag_burst_periods(bins, window_minutes=30)))
        output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
