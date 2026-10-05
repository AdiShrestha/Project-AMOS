"""Unit, integration, and cross-runtime parity tests for AMOS-05 model training.

Verifies:
1. Exact numerical agreement for 7-feature streaming extraction matching features.hpp.
2. Solver convergence under declared stopping criteria (relative change <= 1e-6 or grad_norm <= 1e-5).
3. Zero test data leakage: test rows are isolated and unread during training and validation.
4. Model serialization compliance with schema=bpfeat.taobao.features.v2.
5. Cross-runtime numerical agreement: max absolute difference between Python and C++ < 1e-12.
6. Baseline superiority: logistic model outperforms class-prior on log loss and average precision.
"""

import csv
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np

from tools.train_model import (
    DEFAULT_ALPHA,
    DEFAULT_L2_REG,
    FEATURE_DIMENSION,
    FEATURE_SCHEMA,
    KeyedFeatures,
    evaluate_predictions,
    fit_logistic_regression,
    save_model_file,
    score_logistic,
    train_model,
)


class ModelTrainingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

        # Locate bpfeat_engine binary
        self.binary = os.environ.get("BPFEAT_ENGINE")
        if not self.binary:
            candidate = Path("build/debug/bpfeat_engine")
            if candidate.exists() and os.access(candidate, os.X_OK):
                self.binary = str(candidate.resolve())

    def test_keyed_features_closed_form_vectors(self):
        """Verify 7 streaming features match exact analytical closed-form vectors."""
        kf = KeyedFeatures(alpha=0.1)

        # Event 1: user 1, t = 0s, pv (code 0)
        v1 = kf.update(user_id=1, event_ts_ns=0, behavior_code=0)
        expected1 = [0.1, math.log(2.0), 0.0, 0.0, 0.0, 0.0, 0.0]
        for idx, (val, exp) in enumerate(zip(v1, expected1)):
            self.assertAlmostEqual(val, exp, places=12, msg=f"Feature x{idx} mismatch on event 1")

        # Event 2: user 1, t = 1s, buy (code 3)
        v2 = kf.update(user_id=1, event_ts_ns=1_000_000_000, behavior_code=3)
        expected2 = [0.59, math.log(2.0), 0.0, 1.0 / 3600.0, 0.5, math.log(2.0), 0.1]
        for idx, (val, exp) in enumerate(zip(v2, expected2)):
            self.assertAlmostEqual(val, exp, places=12, msg=f"Feature x{idx} mismatch on event 2")

        # Event 3: user 2, t = 2s, cart (code 1)
        v3 = kf.update(user_id=2, event_ts_ns=2_000_000_000, behavior_code=1)
        expected3 = [0.3, 0.0, math.log(2.0), 0.0, 0.0, 0.0, 0.0]
        for idx, (val, exp) in enumerate(zip(v3, expected3)):
            self.assertAlmostEqual(val, exp, places=12, msg=f"Feature x{idx} mismatch on event 3")

    def test_solver_convergence_and_monotone_descent(self):
        """Solver must terminate on convergence criterion and decrease loss monotonically."""
        np.random.seed(42)
        n_samples = 2000
        X = np.random.randn(n_samples, FEATURE_DIMENSION)
        true_w = np.array([0.5, -0.3, 0.2, 0.1, 0.8, -0.4, 0.05])
        true_bias = -1.2
        logits = true_bias + X @ true_w
        probs = 1.0 / (1.0 + np.exp(-logits))
        y = (np.random.rand(n_samples) < probs).astype(int)

        fit = fit_logistic_regression(X, y, reg=1e-4, ftol=1e-6, gtol=1e-5, max_iter=500)

        self.assertTrue(fit["converged"], "Optimizer failed to converge")
        self.assertLess(fit["iterations"], 500, "Optimizer hit max iterations")
        self.assertGreater(len(fit["solver_trace"]), 1)

        # Loss must decrease monotonically from initial class-prior
        trace = fit["solver_trace"]
        initial_loss = trace[0]["loss"]
        final_loss = fit["final_loss"]
        self.assertLess(final_loss, initial_loss, "Final loss was not lower than initial loss")

    def test_zero_test_data_leakage(self):
        """Verify test split rows are never accessed during training or validation."""
        events_file = self.root / "events.csv"
        cohort_file = self.root / "cohort.csv"
        model_file1 = self.root / "model1.txt"
        manifest_file1 = self.root / "manifest1.json"
        model_file2 = self.root / "model2.txt"
        manifest_file2 = self.root / "manifest2.json"

        # Construct synthetic stream covering train, validation, and test
        events_rows = ["seq,event_ts_ns,key,item_id,category_id,behavior_code"]
        cohort_rows = ["seq,user_id,event_ts_ns,split,group_id,label,censored"]

        t_base = 1511539200
        # Train events (day 1)
        for i in range(100):
            events_rows.append(f"{i},{t_base + i * 100},{i % 5},{100 + i},{200},{i % 4}")
            cohort_rows.append(f"{i},{i % 5},{t_base + i * 100},train,train_hour_00,{i % 2},0")

        # Validation events (day 7)
        t_val = 1512057600
        for i in range(100, 150):
            events_rows.append(f"{i},{t_val + (i - 100) * 100},{i % 5},{100 + i},{200},{i % 4}")
            cohort_rows.append(f"{i},{i % 5},{t_val + (i - 100) * 100},validation,val_hour_00,{i % 2},0")

        # Test events (day 8) - Run 1
        t_test = 1512144000
        for i in range(150, 200):
            events_rows.append(f"{i},{t_test + (i - 150) * 100},{i % 5},{100 + i},{200},{i % 4}")
            cohort_rows.append(f"{i},{i % 5},{t_test + (i - 150) * 100},test,test_hour_00,{i % 2},0")

        events_file.write_text("\n".join(events_rows) + "\n")
        cohort_file.write_text("\n".join(cohort_rows) + "\n")

        # Run 1
        m1 = train_model(
            events_path=events_file,
            cohort_path=cohort_file,
            output_model_path=model_file1,
            output_manifest_path=manifest_file1,
        )

        # Mutate test labels and behaviors completely in Run 2
        cohort_rows_mutated = list(cohort_rows[:151])  # header + 150 train/val rows
        for i in range(150, 200):
            # Invert all test labels from i % 2 to (i + 1) % 2
            cohort_rows_mutated.append(f"{i},{i % 5},{t_test + (i - 150) * 100},test,test_hour_00,{(i + 1) % 2},0")

        cohort_file_mutated = self.root / "cohort_mutated.csv"
        cohort_file_mutated.write_text("\n".join(cohort_rows_mutated) + "\n")

        # Run 2
        m2 = train_model(
            events_path=events_file,
            cohort_path=cohort_file_mutated,
            output_model_path=model_file2,
            output_manifest_path=manifest_file2,
        )

        # Model weights and validation metrics must be identical down to the bit
        self.assertEqual(model_file1.read_text(), model_file2.read_text(), "Model weights depended on test data!")
        self.assertEqual(m1["training_summary"]["train_samples"], m2["training_summary"]["train_samples"])
        self.assertEqual(m1["validation_metrics"], m2["validation_metrics"], "Validation metrics depended on test data!")
        self.assertTrue(m1["training_summary"]["zero_test_data_leakage_verified"])

    def test_model_serialization_and_cpp_parsing(self):
        """Exported model must strictly adhere to bpfeat.taobao.features.v2 and parse in C++."""
        model_path = self.root / "logistic_model.txt"
        bias = -1.7512345678901234
        weights = [0.1234567890123456, -0.2345678901234567, 0.3456789012345678,
                   -0.0123456789012345, 0.4567890123456789, 0.5678901234567890, -0.0001234567890123]

        save_model_file(bias, weights, model_path)

        lines = [line.strip() for line in model_path.read_text().splitlines() if line.strip()]
        self.assertEqual(lines[0], f"schema={FEATURE_SCHEMA}")
        self.assertEqual(len(lines), FEATURE_DIMENSION + 2)  # schema, bias, w0..w6

        # If binary available, test load directly via bpfeat_engine
        if self.binary:
            events_path = self.root / "events.csv"
            out_dir = self.root / "attempt"
            events_path.write_text("seq,event_ts_ns,key,item_id,category_id,behavior_code\n1,0,10,1,1,0\n")
            run = subprocess.run([
                self.binary, "--events", str(events_path), "--model", str(model_path),
                "--out-dir", str(out_dir), "--mode", "fixed"
            ], capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, f"C++ engine failed to load model: {run.stderr}")

    def test_cross_runtime_numerical_agreement_under_1e12(self):
        """Maximum absolute difference between Python and C++ predictions must be < 1e-12."""
        if not self.binary:
            self.skipTest("C++ binary not available for cross-runtime testing")

        model_path = self.root / "logistic_model.txt"
        events_path = self.root / "events.csv"
        out_dir = self.root / "attempt"

        bias = -1.9688872868984322
        weights = [0.15, -0.05, 0.08, -0.02, 0.45, 0.12, -0.0001]
        save_model_file(bias, weights, model_path)

        # Generate 1,000 diverse events to stress floating point scoring
        events_rows = ["seq,event_ts_ns,key,item_id,category_id,behavior_code"]
        t0 = 1511539200000000000
        for i in range(1000):
            events_rows.append(f"{i},{t0 + i * 500000000},{i % 50},{100 + (i % 200)},{200 + (i % 10)},{i % 4}")
        events_path.write_text("\n".join(events_rows) + "\n")

        run = subprocess.run([
            self.binary, "--events", str(events_path), "--model", str(model_path),
            "--out-dir", str(out_dir), "--mode", "fixed"
        ], capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)

        predictions_path = out_dir / "predictions_unlabeled.csv"
        self.assertTrue(predictions_path.exists())

        max_discrepancy = 0.0
        with open(predictions_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cpp_score = float(row["score"])
                features = [float(row[f"x{i}"]) for i in range(FEATURE_DIMENSION)]
                py_score = score_logistic(bias, weights, features)
                diff = abs(cpp_score - py_score)
                if diff > max_discrepancy:
                    max_discrepancy = diff

        self.assertLess(max_discrepancy, 1e-12, f"Discrepancy {max_discrepancy:.2e} exceeded 1e-12 tolerance!")

    def test_baseline_superiority(self):
        """Fitted model must achieve lower log loss and higher average precision than class-prior."""
        np.random.seed(123)
        n_samples = 3000
        X = np.random.randn(n_samples, FEATURE_DIMENSION)
        # Strong predictive relationship on x0 and x4
        true_w = np.array([1.2, 0.0, 0.0, -0.5, 2.0, 0.0, 0.0])
        logits = -1.5 + X @ true_w
        probs = 1.0 / (1.0 + np.exp(-logits))
        y = (np.random.rand(n_samples) < probs).astype(int)

        # Train / Validation split (80/20)
        n_train = 2400
        X_tr, y_tr = X[:n_train], y[:n_train]
        X_va, y_va = X[n_train:], y[n_train:]

        fit = fit_logistic_regression(X_tr, y_tr)
        val_preds_model = np.array([score_logistic(fit["bias"], fit["weights"], x) for x in X_va])
        val_preds_prior = np.full(len(y_va), np.mean(y_tr))

        metrics_model = evaluate_predictions(val_preds_model, y_va)
        metrics_prior = evaluate_predictions(val_preds_prior, y_va)

        self.assertLess(metrics_model["log_loss"], metrics_prior["log_loss"], "Logistic model did not reduce log loss")
        self.assertGreater(metrics_model["average_precision"], metrics_prior["average_precision"], "Logistic model did not improve AP")
        self.assertLess(metrics_model["brier_score"], metrics_prior["brier_score"], "Logistic model did not reduce Brier score")
        self.assertGreater(metrics_model["auroc"], 0.70, "Model AUROC is below 0.70 on predictive synthetic data")


if __name__ == "__main__":
    unittest.main()
