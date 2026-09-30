"""
tests/test_preprocessing_lineage.py - Unit tests for preprocessing/lineage.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))
from preprocessing.lineage import PreprocessingLineageDAG

class TestPreprocessingLineage(unittest.TestCase):
    def setUp(self):
        self.config = {"dataset": "taobao_diagnostic", "version": 1}
        self.dag = PreprocessingLineageDAG(self.config)

    def test_row_accounting_reconciliation(self):
        raw_rows = [
            {"user_id": 1, "event_ts_ns": 1000, "behavior_code": 0},  # accepted
            {"user_id": 1, "event_ts_ns": 2000, "behavior_code": 1},  # accepted
            {"user_id": 2, "event_ts_ns": None, "behavior_code": 0},  # rejected
            {"user_id": 1, "event_ts_ns": 1000, "behavior_code": 0},  # duplicate
            {"user_id": 3, "event_ts_ns": 3000, "behavior_code": 0, "censored": 1},  # censored
        ]
        res = self.dag.process_fixture_rows(raw_rows)
        acc = res["manifest"]["row_accounting"]
        self.assertEqual(acc["input_rows"], 5)
        self.assertEqual(acc["accepted"], 2)
        self.assertEqual(acc["rejected"], 1)
        self.assertEqual(acc["duplicates"], 1)
        self.assertEqual(acc["censored"], 1)
        self.assertEqual(acc["input_rows"], acc["accepted"] + acc["rejected"] + acc["duplicates"] + acc["censored"])

    def test_repeatability(self):
        raw_rows = [
            {"user_id": 1, "event_ts_ns": 1000, "behavior_code": 0},
            {"user_id": 1, "event_ts_ns": 2000, "behavior_code": 1},
        ]
        res1 = self.dag.process_fixture_rows(raw_rows)
        res2 = self.dag.process_fixture_rows(raw_rows)
        self.assertEqual(res1["manifest"]["output_artifact_sha256"], res2["manifest"]["output_artifact_sha256"])

    def test_mutation_changes_hash(self):
        raw_rows1 = [{"user_id": 1, "event_ts_ns": 1000, "behavior_code": 0}]
        raw_rows2 = [{"user_id": 1, "event_ts_ns": 1001, "behavior_code": 0}]
        res1 = self.dag.process_fixture_rows(raw_rows1)
        res2 = self.dag.process_fixture_rows(raw_rows2)
        self.assertNotEqual(res1["manifest"]["output_artifact_sha256"], res2["manifest"]["output_artifact_sha256"])

if __name__ == "__main__":
    unittest.main()
