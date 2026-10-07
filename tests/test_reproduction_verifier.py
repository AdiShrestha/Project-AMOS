#!/usr/bin/env python3
"""Comprehensive unit and integration test suite for reproduction verifier and lineage manifests.

Verifies:
1. End-to-end execution of reproduction_verifier.py.
2. Exact matching between original and replay metrics within tolerance <= 1e-05.
3. Structural validity and completeness of per_number_manifest.json.
4. Input file cryptographic digest integrity checks.
5. Independent mathematical calculation of ranking metrics on known test vectors.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.reproduction_verifier import (
    HEADLINE_METRICS_SPEC,
    build_reproduction_manifest,
    compute_binary_metrics,
    compute_sha256,
    verify_cohort_files,
)


class ReproductionVerifierTests(unittest.TestCase):
    """Test suite for standalone reproduction verifier."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parent.parent
        cls.cohort_path = cls.root / "data" / "cohort.csv"
        cls.model_path = cls.root / "data" / "models" / "logistic_model.txt"
        cls.confirmatory_path = cls.root / "docs" / "research" / "confirmatory_results.json"
        cls.robustness_path = cls.root / "docs" / "research" / "robustness_analysis.json"
        cls.repro_manifest_path = cls.root / "docs" / "research" / "reproduction_manifest.json"
        cls.per_number_path = cls.root / "docs" / "research" / "per_number_manifest.json"

    def test_cohort_and_model_digests(self) -> None:
        """Verify that cohort and model files exist and match authentic digests."""
        integrity = verify_cohort_files(self.cohort_path, self.model_path)
        self.assertTrue(integrity.get("cohort_match"), f"Cohort hash mismatch: {integrity}")
        if self.model_path.exists():
            self.assertTrue(integrity.get("model_match"), f"Model hash mismatch: {integrity}")

    def test_reproduction_manifest_schema_and_tolerance(self) -> None:
        """Verify that reproduction_manifest.json satisfies strict comparison rules within tolerance."""
        self.assertTrue(self.repro_manifest_path.exists(), "reproduction_manifest.json must exist")
        with open(self.repro_manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("original", manifest)
        self.assertIn("replay", manifest)
        self.assertIn("tolerance", manifest)

        orig = manifest["original"]
        rep = manifest["replay"]
        tol = manifest["tolerance"]

        self.assertIsInstance(orig, dict)
        self.assertIsInstance(rep, dict)
        self.assertIsInstance(tol, (int, float))
        self.assertLessEqual(tol, 1e-05)

        # Verify all 12 headline metrics are present in both
        for key in HEADLINE_METRICS_SPEC:
            self.assertIn(key, orig, f"Missing key in original: {key}")
            self.assertIn(key, rep, f"Missing key in replay: {key}")
            diff = abs(float(orig[key]) - float(rep[key]))
            self.assertLessEqual(diff, tol, f"Metric mismatch on {key}: orig={orig[key]}, rep={rep[key]}, diff={diff} > tol={tol}")

    def test_per_number_manifest_lineage(self) -> None:
        """Verify that per_number_manifest.json records complete traceability for all reported numbers."""
        self.assertTrue(self.per_number_path.exists(), "per_number_manifest.json must exist")
        with open(self.per_number_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest.get("schema"), "bpfeat.per_number_manifest.v1")
        items = manifest.get("items", [])
        self.assertGreaterEqual(len(items), 12)

        seen_ids = set()
        for item in items:
            item_id = item.get("item_id")
            self.assertIsInstance(item_id, str)
            self.assertNotIn(item_id, seen_ids, f"Duplicate item_id: {item_id}")
            seen_ids.add(item_id)

            self.assertIn("reported_value", item)
            self.assertIsInstance(item.get("reported_value"), (int, float))

            source_art = item.get("source_artifact", "")
            self.assertTrue(source_art, f"Missing source_artifact for {item_id}")
            art_path = self.root / source_art
            self.assertTrue(art_path.exists(), f"Source artifact does not exist: {art_path}")

            cmd = item.get("reproduction_command", "")
            self.assertTrue(cmd, f"Missing reproduction_command for {item_id}")
            self.assertTrue(cmd.startswith("python3 -B"), f"Invalid command prefix: {cmd}")

    def test_cli_execution_end_to_end(self) -> None:
        """Verify CLI execution of reproduction_verifier.py with custom output paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_manifest = Path(tmpdir) / "test_manifest.json"
            out_per_num = Path(tmpdir) / "test_per_number.json"

            cmd = [
                sys.executable,
                "-B",
                str(self.root / "tools" / "reproduction_verifier.py"),
                "--cohort", str(self.cohort_path),
                "--confirmatory-results", str(self.confirmatory_path),
                "--robustness-results", str(self.robustness_path),
                "--output-manifest", str(out_manifest),
                "--output-per-number", str(out_per_num),
                "--tolerance", "1e-05",
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.root)
            self.assertEqual(res.returncode, 0, f"Verifier CLI failed:\nstdout={res.stdout}\nstderr={res.stderr}")

            self.assertTrue(out_manifest.exists())
            self.assertTrue(out_per_num.exists())

            data = json.loads(res.stdout)
            self.assertEqual(data.get("status"), "PASS")
            self.assertEqual(data.get("cohort_integrity"), "VERIFIED")
            self.assertEqual(data.get("metrics_verified"), 12)

    def test_cli_fast_query_options(self) -> None:
        """Verify fast querying of individual headline metrics and contrasts."""
        # Query specific metric
        cmd_metric = [
            sys.executable,
            "-B",
            str(self.root / "tools" / "reproduction_verifier.py"),
            "--metric", "dynamic_mimd_test_ap",
        ]
        res_m = subprocess.run(cmd_metric, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.root)
        self.assertEqual(res_m.returncode, 0)
        out_m = json.loads(res_m.stdout)
        self.assertAlmostEqual(out_m["dynamic_mimd_test_ap"], 0.141621, places=5)

        # Query specific contrast
        cmd_contrast = [
            sys.executable,
            "-B",
            str(self.root / "tools" / "reproduction_verifier.py"),
            "--contrast", "comp_dynamic_vs_static_ap",
        ]
        res_c = subprocess.run(cmd_contrast, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.root)
        self.assertEqual(res_c.returncode, 0)
        out_c = json.loads(res_c.stdout)
        self.assertAlmostEqual(out_c["effect"], 0.029328, places=5)

    def test_independent_binary_metrics_accuracy(self) -> None:
        """Verify metric calculation functions against textbook ground truth."""
        # Perfect separation
        labels = [0, 0, 1, 1]
        scores = [0.1, 0.2, 0.8, 0.9]
        metrics = compute_binary_metrics(labels, scores)
        self.assertAlmostEqual(metrics["auroc"], 1.0)
        self.assertAlmostEqual(metrics["average_precision"], 1.0)
        self.assertAlmostEqual(metrics["accuracy"], 1.0)

        # Inverted separation
        scores_inv = [0.9, 0.8, 0.2, 0.1]
        metrics_inv = compute_binary_metrics(labels, scores_inv)
        self.assertAlmostEqual(metrics_inv["auroc"], 0.0)


if __name__ == "__main__":
    unittest.main()
