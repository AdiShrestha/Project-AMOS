"""
preprocessing/lineage.py - Deterministic Preprocessing and Raw-to-Replay Lineage DAG.

Schema: bpfeat.lineage.v1
Specification: project/chunks/chunk04/contracts/C04-04_contract.md
"""

from __future__ import annotations
import hashlib
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

def compute_sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def compute_sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

@dataclass(frozen=True)
class LineageRecord:
    source_row_id: int
    seq: int
    event_ts_ns: int
    entity_id: Optional[int]
    item_id: Optional[int]
    category_id: Optional[int]
    behavior_code: int
    amount: float
    label: Optional[int]
    label_valid: int
    censored: int
    status: str  # ACCEPTED, REJECTED, DUPLICATE, CENSORED
    rejection_reason: Optional[str] = None

@dataclass
class StageManifest:
    stage_name: str
    parent_manifest_sha256: Optional[str]
    input_artifact_sha256: str
    config_hash: str
    row_accounting: Dict[str, int]
    output_artifact_sha256: str
    output_path: str

class PreprocessingLineageDAG:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.config_hash = compute_sha256_bytes(json.dumps(config, sort_keys=True).encode("utf-8"))

    def process_fixture_rows(self, raw_rows: List[Dict[str, Any]], parent_manifest_sha256: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes deterministic stages and verifies row conservation.
        """
        input_bytes = json.dumps(raw_rows, sort_keys=True).encode("utf-8")
        input_hash = compute_sha256_bytes(input_bytes)
        
        accepted = 0
        rejected = 0
        duplicates = 0
        censored = 0
        
        seen_keys = set()
        canonical_rows: List[LineageRecord] = []
        
        for idx, row in enumerate(raw_rows):
            # Validation
            if "event_ts_ns" not in row or row["event_ts_ns"] is None:
                rejected += 1
                canonical_rows.append(LineageRecord(
                    source_row_id=idx,
                    seq=-1,
                    event_ts_ns=0,
                    entity_id=row.get("user_id"),
                    item_id=row.get("item_id"),
                    category_id=row.get("category_id"),
                    behavior_code=-1,
                    amount=0.0,
                    label=None,
                    label_valid=0,
                    censored=0,
                    status="REJECTED",
                    rejection_reason="MISSING_TIMESTAMP"
                ))
                continue
            
            # Duplicate check
            key = (row.get("user_id"), row["event_ts_ns"], row.get("behavior_code"))
            if key in seen_keys:
                duplicates += 1
                canonical_rows.append(LineageRecord(
                    source_row_id=idx,
                    seq=-1,
                    event_ts_ns=row["event_ts_ns"],
                    entity_id=row.get("user_id"),
                    item_id=row.get("item_id"),
                    category_id=row.get("category_id"),
                    behavior_code=row.get("behavior_code", 0),
                    amount=float(row.get("amount", 0.0)),
                    label=row.get("label"),
                    label_valid=0,
                    censored=0,
                    status="DUPLICATE",
                    rejection_reason="DUPLICATE_KEY"
                ))
                continue
            
            seen_keys.add(key)
            
            # Censoring check
            is_censored = row.get("censored", 0)
            if is_censored:
                censored += 1
                canonical_rows.append(LineageRecord(
                    source_row_id=idx,
                    seq=len(canonical_rows),
                    event_ts_ns=row["event_ts_ns"],
                    entity_id=row.get("user_id"),
                    item_id=row.get("item_id"),
                    category_id=row.get("category_id"),
                    behavior_code=row.get("behavior_code", 0),
                    amount=float(row.get("amount", 0.0)),
                    label=row.get("label"),
                    label_valid=0,
                    censored=1,
                    status="CENSORED",
                    rejection_reason=None
                ))
                continue
            
            # Accepted
            accepted += 1
            canonical_rows.append(LineageRecord(
                source_row_id=idx,
                seq=len(canonical_rows),
                event_ts_ns=row["event_ts_ns"],
                entity_id=row.get("user_id"),
                item_id=row.get("item_id"),
                category_id=row.get("category_id"),
                behavior_code=row.get("behavior_code", 0),
                amount=float(row.get("amount", 0.0)),
                label=row.get("label"),
                label_valid=row.get("label_valid", 1),
                censored=0,
                status="ACCEPTED",
                rejection_reason=None
            ))
            
        total_accounted = accepted + rejected + duplicates + censored
        assert total_accounted == len(raw_rows), f"Conservation violation: {total_accounted} != {len(raw_rows)}"
        
        output_data = [asdict(r) for r in canonical_rows if r.status in ("ACCEPTED", "CENSORED")]
        output_bytes = json.dumps(output_data, sort_keys=True).encode("utf-8")
        output_hash = compute_sha256_bytes(output_bytes)
        
        manifest = StageManifest(
            stage_name="replay_generation",
            parent_manifest_sha256=parent_manifest_sha256,
            input_artifact_sha256=input_hash,
            config_hash=self.config_hash,
            row_accounting={
                "input_rows": len(raw_rows),
                "accepted": accepted,
                "rejected": rejected,
                "duplicates": duplicates,
                "censored": censored
            },
            output_artifact_sha256=output_hash,
            output_path="canonical_replay.json"
        )
        
        return {
            "manifest": asdict(manifest),
            "rows": output_data
        }
