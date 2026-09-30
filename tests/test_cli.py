"""FABRICATION-DISCLOSURE: all temporary inputs here are explicit fixtures."""
import csv
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class EngineCLITests(unittest.TestCase):
    def setUp(self):
        self.binary = os.environ.get("BPFEAT_ENGINE")
        if not self.binary:
            self.skipTest("CLI verification requires BPFEAT_ENGINE; CTest provides it")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.events = self.root / "fixture.csv"
        self.events.write_text("seq,event_ts_ns,key,item_id,category_id,behavior_code\n"
                               "10,0,1,5,2520377,0\n30,1000000000,1,6,2520377,3\n70,2000000000,2,7,149192,1\n")
        self.model = self.root / "fixture.weights"
        self.model.write_text("schema=bpfeat.taobao.features.v2\nbias=0.2\n"
                              "w0=0.4\nw1=-0.1\nw2=0.3\nw3=0.2\nw4=-0.4\nw5=0.1\nw6=0.01\n")

    def run_engine(self, extra=(), directory="attempt"):
        return subprocess.run([self.binary, "--events", str(self.events), "--model", str(self.model),
                               "--out-dir", str(self.root / directory), "--mode", "fixed", *extra],
                              capture_output=True, text=True, timeout=10)

    def test_raw_predictions_match_independent_feature_and_score_reference(self):
        run = self.run_engine()
        self.assertEqual(run.returncode, 0, run.stderr)
        with (self.root / "attempt/predictions_unlabeled.csv").open() as stream:
            records = list(csv.DictReader(stream))
        self.assertEqual([int(r["seq"]) for r in records], [10, 30, 70])
        # Direct closed-form vectors rather than calling runtime feature code.
        expected = [[0.1, math.log(2), 0, 0, 0, 0, 0],
                    [0.59, math.log(2), 0, 1/3600, 1/2, math.log(2), 0.1],
                    [0.3, 0, math.log(2), 0, 0, 0, 0]]
        weights = [0.4, -0.1, 0.3, 0.2, -0.4, 0.1, 0.01]
        for record, features in zip(records, expected):
            for i, value in enumerate(features):
                self.assertAlmostEqual(float(record[f"x{i}"]), value, places=12)
            z = 0.2 + sum(w*x for w, x in zip(weights, features))
            self.assertAlmostEqual(float(record["score"]), 1 / (1 + math.exp(-z)), places=12)
        receipt = json.loads((self.root / "attempt/engine_receipt.json").read_text())
        self.assertEqual(receipt["written"], 3)
        self.assertIs(receipt["research_evidence"], False)

    def test_missing_model_never_becomes_zero_model(self):
        self.model.unlink()
        self.assertNotEqual(self.run_engine().returncode, 0)
        self.assertFalse((self.root / "attempt").exists())

    def test_partial_duplicate_unknown_and_nan_models_rejected(self):
        original = self.model.read_text()
        variants = [original.replace("w6=0.01\n", ""), original + "bias=0.1\n",
                    original + "unexpected=1\n", original.replace("w0=0.4", "w0=nan")]
        for variant in variants:
            self.model.write_text(variant)
            self.assertNotEqual(self.run_engine().returncode, 0)

    def test_unknown_duplicate_and_invalid_options_rejected(self):
        for extra in (["--fabricated", "1"], ["--mode", "joint"], ["--alpha", "nan"],
                      ["--feature-slots", "3"], ["--batch-max", "257"]):
            self.assertNotEqual(self.run_engine(extra).returncode, 0)

    def test_existing_attempt_is_retained(self):
        self.assertEqual(self.run_engine().returncode, 0)
        original = (self.root / "attempt/predictions_unlabeled.csv").read_bytes()
        self.assertNotEqual(self.run_engine().returncode, 0)
        self.assertEqual((self.root / "attempt/predictions_unlabeled.csv").read_bytes(), original)

    def test_bad_input_has_no_success_receipt(self):
        self.events.write_text(self.events.read_text() + "75,2000000001,3,8,100,9\n")
        self.assertNotEqual(self.run_engine().returncode, 0)
        self.assertFalse((self.root / "attempt/engine_receipt.json").exists())

    def test_labels_and_sequence_duplicates_are_rejected(self):
        original = self.events.read_text()
        self.events.write_text(original.replace("behavior_code\n", "behavior_code,label\n"))
        self.assertNotEqual(self.run_engine().returncode, 0)
        self.events.write_text(original.replace("30,1000000000", "10,1000000000"))
        self.assertNotEqual(self.run_engine(directory="second").returncode, 0)


if __name__ == "__main__":
    unittest.main()
