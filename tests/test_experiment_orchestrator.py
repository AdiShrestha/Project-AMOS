#!/usr/bin/env python3
"""Unit tests for ExperimentOrchestrator."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.orchestrator import ExperimentOrchestrator, OrchestrationError


class TestExperimentOrchestrator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.matrix_file = Path(self.temp_dir) / "test_matrix.yaml"
        self.out_dir = Path(self.temp_dir) / "runs"
        
        matrix_content = """schema_id: bpfeat.pilot_matrix.v1
matrix_version: 1.0.0
runs:
  - run_id: "test_run_fixed_s42"
    architecture_id: "fixed_window_v1"
    seed: 42
    repetition_type: "deterministic_seed"
    repetition_index: 0
    w_events: 32
    events: 100
  - run_id: "test_run_bp_s42"
    architecture_id: "backpressure_only_v1"
    seed: 42
    repetition_type: "deterministic_seed"
    repetition_index: 0
    w_events: 32
    events: 100
"""
        self.matrix_file.write_text(matrix_content, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_run_all_and_idempotent_resume(self):
        orc = ExperimentOrchestrator(self.matrix_file, self.out_dir)
        results1 = orc.run_all()
        self.assertEqual(len(results1), 2)
        self.assertEqual(results1[0]["status"], "COMPLETED")
        self.assertEqual(results1[1]["status"], "COMPLETED")

        # Second run should resume/skip
        results2 = orc.run_all()
        self.assertEqual(len(results2), 2)
        self.assertEqual(results2[0]["status"], "RESUMED")
        self.assertEqual(results2[1]["status"], "RESUMED")

    def test_unknown_architecture_fail_closed(self):
        bad_matrix = Path(self.temp_dir) / "bad_matrix.yaml"
        bad_matrix.write_text("""schema_id: bpfeat.pilot_matrix.v1
runs:
  - run_id: "bad_run"
    architecture_id: "unregistered_v99"
    seed: 42
    repetition_type: "deterministic_seed"
    repetition_index: 0
""", encoding="utf-8")
        orc = ExperimentOrchestrator(bad_matrix, self.out_dir)
        with self.assertRaises(OrchestrationError):
            orc.run_all()

    def test_corrupted_file_detection(self):
        orc = ExperimentOrchestrator(self.matrix_file, self.out_dir)
        orc.run_all()
        
        # Tamper with results CSV
        res_file = self.out_dir / "test_run_fixed_s42_results.csv"
        res_file.write_text("corrupted_content", encoding="utf-8")
        
        self.assertFalse(orc.is_run_completed("test_run_fixed_s42"))


if __name__ == "__main__":
    unittest.main()
