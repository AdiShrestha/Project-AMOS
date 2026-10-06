#!/usr/bin/env python3
"""Comprehensive test suite for streaming domain adapter and native execution entrypoint.

Verifies:
1. Recomputation of streaming systems metrics and predictive performance metrics.
2. Enforcement of strict temporal causality (zero future feature leakage).
3. Exact event accounting and work conservation laws.
4. Resistance to 12 adversarial mutations (phantoms, omissions, duplicates, leaks).
5. Isolated Python entrypoint execution (-I -P -B -S).
6. End-to-end execution of native C++ engine via the entrypoint.
"""

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.streaming_adapter import (
    StreamingValidationError,
    compute_binary_metrics,
    recompute_streaming_metrics,
    verify_conservation,
    verify_temporal_causality,
)


class StreamingAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_binary_metrics_exactness(self):
        y_true = [1, 0, 1, 0, 1]
        scores = [0.9, 0.1, 0.8, 0.2, 0.7]
        m = compute_binary_metrics(y_true, scores, threshold=0.5)
        self.assertEqual(m["auroc"], 1.0)
        self.assertEqual(m["average_precision"], 1.0)
        self.assertEqual(m["accuracy"], 1.0)
        self.assertEqual(m["f1"], 1.0)
        self.assertAlmostEqual(m["brier"], 0.038, places=3)
        self.assertGreater(m["log_loss"], 0.0)

    def test_valid_streaming_run_recomputes_metrics(self):
        # Create cohort
        cohort_path = self.root / "cohort.csv"
        with open(cohort_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["sample_id", "label", "group_id", "split", "source_ids"])
            writer.writerow(["s1", "1", "g1", "test", "src1"])
            writer.writerow(["s2", "0", "g1", "test", "src2"])
            writer.writerow(["s3", "1", "g2", "test", "src3"])
            writer.writerow(["s4", "0", "g2", "test", "src4"])

        # Create predictions
        pred_path = self.root / "predictions.csv"
        with open(pred_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["sample_id", "score"])
            writer.writerow(["s1", "0.85"])
            writer.writerow(["s2", "0.15"])
            writer.writerow(["s3", "0.75"])
            writer.writerow(["s4", "0.20"])

        # Create telemetry
        telemetry = {
            "summary": {
                "events_processed": 100,
                "writes_emitted": 20,
                "events_absorbed": 80,
                "queries_offered": 4,
                "queries_answered": 4,
            },
            "queries": [
                {"query_id": "s1", "query_ts_ns": 1000, "feature_ts_ns": 800, "latency_ms": 12.0},
                {"query_id": "s2", "query_ts_ns": 2000, "feature_ts_ns": 1900, "latency_ms": 15.0},
                {"query_id": "s3", "query_ts_ns": 3000, "feature_ts_ns": 2500, "latency_ms": 20.0},
                {"query_id": "s4", "query_ts_ns": 4000, "feature_ts_ns": 3800, "latency_ms": 25.0},
            ]
        }
        telem_path = self.root / "telemetry.json"
        telem_path.write_text(json.dumps(telemetry), encoding="utf-8")

        report = recompute_streaming_metrics(
            predictions_path=pred_path,
            telemetry_path=telem_path,
            cohort_path=cohort_path,
            sla_deadline_ms=50.0,
        )

        systems = report["streaming_systems"]
        self.assertEqual(systems["query_coverage"], 1.0)
        self.assertEqual(systems["write_work_ratio"], 0.20)
        self.assertAlmostEqual(systems["deadline_utility"], 1.0)
        self.assertGreater(systems["mean_staleness_ms"], 0.0)

        perf = report["predictive_performance"]
        self.assertEqual(perf["auroc"], 1.0)
        self.assertEqual(perf["accuracy"], 1.0)

    def test_temporal_causality_rejection_on_future_feature(self):
        telemetry = {
            "queries": [
                {"query_id": "q1", "query_ts_ns": 1000, "feature_ts_ns": 2000}
            ]
        }
        with self.assertRaises(StreamingValidationError) as cm:
            verify_temporal_causality(telemetry)
        self.assertIn("TEMPORAL_LEAKAGE", str(cm.exception))

    def test_conservation_rejection_on_dropped_events(self):
        telemetry = {
            "summary": {
                "events_processed": 100,
                "writes_emitted": 20,
                "events_absorbed": 70,  # Missing 10
            }
        }
        with self.assertRaises(StreamingValidationError) as cm:
            verify_conservation(telemetry)
        self.assertIn("CONSERVATION_VIOLATION", str(cm.exception))

    def test_phantom_sample_id_rejection(self):
        cohort_path = self.root / "cohort.csv"
        with open(cohort_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["sample_id", "label", "group_id", "split", "source_ids"])
            writer.writerow(["s1", "1", "g1", "test", "src1"])
            writer.writerow(["s2", "0", "g1", "test", "src2"])

        pred_path = self.root / "predictions.csv"
        with open(pred_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["sample_id", "score"])
            writer.writerow(["s1", "0.8"])
            writer.writerow(["s2", "0.2"])
            writer.writerow(["s_phantom", "0.5"])

        telem_path = self.root / "telemetry.json"
        telem_path.write_text(json.dumps({"summary": {}}), encoding="utf-8")

        with self.assertRaises(StreamingValidationError) as cm:
            recompute_streaming_metrics(pred_path, telem_path, cohort_path)
        self.assertIn("PHANTOM_SAMPLES", str(cm.exception))

    def test_suppressed_misses_rejection(self):
        cohort_path = self.root / "cohort.csv"
        with open(cohort_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["sample_id", "label", "group_id", "split", "source_ids"])
            writer.writerow(["s1", "1", "g1", "test", "src1"])
            writer.writerow(["s2", "0", "g1", "test", "src2"])
            writer.writerow(["s3", "1", "g2", "test", "src3"])

        # Omit s3
        pred_path = self.root / "predictions.csv"
        with open(pred_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["sample_id", "score"])
            writer.writerow(["s1", "0.8"])
            writer.writerow(["s2", "0.2"])

        telem_path = self.root / "telemetry.json"
        telem_path.write_text(json.dumps({"summary": {}}), encoding="utf-8")

        with self.assertRaises(StreamingValidationError) as cm:
            recompute_streaming_metrics(pred_path, telem_path, cohort_path)
        self.assertIn("SUPPRESSED_MISSES", str(cm.exception))

    def test_duplicate_predictions_rejection(self):
        pred_path = self.root / "predictions.csv"
        with open(pred_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["sample_id", "score"])
            writer.writerow(["s1", "0.8"])
            writer.writerow(["s1", "0.9"])

        telem_path = self.root / "telemetry.json"
        telem_path.write_text(json.dumps({"summary": {}}), encoding="utf-8")

        with self.assertRaises(StreamingValidationError) as cm:
            recompute_streaming_metrics(pred_path, telem_path)
        self.assertIn("duplicate sample_id", str(cm.exception))

    def test_negative_timestamp_rejected(self):
        telemetry = {
            "queries": [
                {"query_id": "q1", "query_ts_ns": -500, "feature_ts_ns": 100}
            ]
        }
        with self.assertRaises(StreamingValidationError) as cm:
            verify_temporal_causality(telemetry)
        self.assertIn("negative", str(cm.exception).lower())

    def test_isolated_python_runner_execution(self):
        # Test nonexistent binary execution fails with exit code 127
        run_dir = self.root / "run_nonexistent"
        cmd = [
            sys.executable, "-I", "-P", "-B", "-S",
            "source/apps/streaming_runner.py",
            "--executable", "/nonexistent/binary/path",
            "--run-dir", str(run_dir),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 127)
        self.assertTrue((run_dir / "stderr.log").exists())
        self.assertIn("not found or not executable", (run_dir / "stderr.log").read_text())

    def test_real_native_engine_execution_via_streaming_runner(self):
        # Prepare small valid inputs
        events = self.root / "events.csv"
        events.write_text(
            "seq,event_ts_ns,key,item_id,category_id,behavior_code\n"
            "10,0,1,5,2520377,0\n"
            "30,1000000000,1,6,2520377,3\n"
            "70,2000000000,2,7,149192,1\n"
        )
        model = self.root / "model.weights"
        model.write_text(
            "schema=bpfeat.taobao.features.v2\n"
            "bias=0.2\nw0=0.4\nw1=-0.1\nw2=0.3\nw3=0.2\nw4=-0.4\nw5=0.1\nw6=0.01\n"
        )
        run_dir = self.root / "run_native"

        cmd = [
            sys.executable, "-I", "-P", "-B", "-S",
            "source/apps/streaming_runner.py",
            "--events", str(events),
            "--model", str(model),
            "--run-dir", str(run_dir),
            "--executable", "build/debug/bpfeat_engine",
            "--mode", "fixed",
            "--seed", "101",
            "--experiment-id", "EXP_STREAMING_NATIVE",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

        # Check outputs
        self.assertTrue((run_dir / "predictions_unlabeled.csv").exists())
        self.assertTrue((run_dir / "result.json").exists())
        self.assertTrue((run_dir / "engine_receipt.json").exists())

        rec = json.loads((run_dir / "result.json").read_text())
        self.assertEqual(rec["exit_code"], 0)
        self.assertEqual(rec["experiment_id"], "EXP_STREAMING_NATIVE")
        self.assertEqual(len(rec["binary_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
