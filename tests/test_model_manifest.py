"""
tests/test_model_manifest.py - Unit tests for preprocessing/model_manifest.py.
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath("."))
from preprocessing.model_manifest import ModelManifestLoader

class TestModelManifestLoader(unittest.TestCase):
    def test_valid_manifest_load(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".bin") as f_model:
            f_model.write("bias=0.1\nw0=0.5\n")
            model_path = f_model.name

        with open(model_path, "rb") as f_model:
            model_hash = hashlib.sha256(f_model.read()).hexdigest()

        manifest_data = {
            "model_id": "model_test_01",
            "role": "oof_oracle",
            "task_protocol_id": "task_buy_prediction_v1",
            "feature_schema_id": "bpfeat.semantic.v1",
            "feature_dimension": 7,
            "fold_id_or_training_scope": "fold_0",
            "training_seq_hash": "a" * 64,
            "preprocessing_artifact_id": "prep_01",
            "hyperparameter_config_sha256": "b" * 64,
            "calibration_id": "calib_identity",
            "binary_or_serialized_model_sha256": model_hash,
            "build_revision": "git:main:123456",
            "dependency_lock_id": "lock_01",
            "created_at_utc": "2026-08-28T00:00:00Z",
            "load_status": "VALID"
        }

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f_manifest:
            json.dump(manifest_data, f_manifest)
            manifest_path = f_manifest.name

        try:
            m = ModelManifestLoader.load_and_validate(manifest_path, model_path, expected_dimension=7)
            self.assertEqual(m.model_id, "model_test_01")
            self.assertEqual(m.role, "oof_oracle")
        finally:
            os.remove(model_path)
            os.remove(manifest_path)

    def test_checksum_mismatch_fails(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".bin") as f_model:
            f_model.write("bias=0.1\n")
            model_path = f_model.name

        manifest_data = {
            "model_id": "model_test_01",
            "role": "oof_oracle",
            "task_protocol_id": "task_buy_prediction_v1",
            "feature_schema_id": "bpfeat.semantic.v1",
            "feature_dimension": 7,
            "fold_id_or_training_scope": "fold_0",
            "training_seq_hash": "a" * 64,
            "preprocessing_artifact_id": "prep_01",
            "hyperparameter_config_sha256": "b" * 64,
            "calibration_id": "calib_identity",
            "binary_or_serialized_model_sha256": "wrong_hash_" + "0" * 53,
            "build_revision": "git:main:123456",
            "dependency_lock_id": "lock_01",
            "created_at_utc": "2026-08-28T00:00:00Z",
            "load_status": "VALID"
        }

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f_manifest:
            json.dump(manifest_data, f_manifest)
            manifest_path = f_manifest.name

        try:
            with self.assertRaises(ValueError):
                ModelManifestLoader.load_and_validate(manifest_path, model_path, expected_dimension=7)
        finally:
            os.remove(model_path)
            os.remove(manifest_path)

if __name__ == "__main__":
    unittest.main()
