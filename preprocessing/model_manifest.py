"""
preprocessing/model_manifest.py - Typed Model Manifest and Fail-Closed Loader.

Schema: bpfeat.manifest.v1
Specification: project/chunks/chunk04/contracts/C04-06_contract.md
"""

from __future__ import annotations
import hashlib
import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

ALLOWED_ROLES = {"oof_oracle", "runtime_fixed"}
REQUIRED_FIELDS = {
    "model_id", "role", "task_protocol_id", "feature_schema_id",
    "feature_dimension", "fold_id_or_training_scope", "training_seq_hash",
    "preprocessing_artifact_id", "hyperparameter_config_sha256",
    "calibration_id", "binary_or_serialized_model_sha256",
    "build_revision", "dependency_lock_id", "created_at_utc", "load_status"
}

def compute_sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

@dataclass
class ModelManifest:
    model_id: str
    role: str
    task_protocol_id: str
    feature_schema_id: str
    feature_dimension: int
    fold_id_or_training_scope: str
    training_seq_hash: str
    preprocessing_artifact_id: str
    hyperparameter_config_sha256: str
    calibration_id: str
    binary_or_serialized_model_sha256: str
    build_revision: str
    dependency_lock_id: str
    created_at_utc: str
    load_status: str

class ModelManifestLoader:
    @staticmethod
    def load_and_validate(manifest_path: str, model_weights_path: str, expected_dimension: int = 7) -> ModelManifest:
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        if not os.path.exists(model_weights_path):
            raise FileNotFoundError(f"Model weights file not found: {model_weights_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        missing = REQUIRED_FIELDS - set(data.keys())
        if missing:
            raise ValueError(f"Manifest is missing required fields: {sorted(missing)}")

        if data["role"] not in ALLOWED_ROLES:
            raise ValueError(f"Invalid model role: '{data['role']}'. Expected one of {ALLOWED_ROLES}")

        if data["feature_dimension"] != expected_dimension:
            raise ValueError(f"Feature dimension mismatch: expected {expected_dimension}, got {data['feature_dimension']}")

        # Validate weights checksum
        actual_hash = compute_sha256_file(model_weights_path)
        expected_hash = data["binary_or_serialized_model_sha256"]
        if actual_hash != expected_hash:
            raise ValueError(f"Model weights hash mismatch: expected {expected_hash}, calculated {actual_hash}")

        return ModelManifest(**{k: data[k] for k in REQUIRED_FIELDS})
