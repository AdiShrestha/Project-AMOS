#!/usr/bin/env python3
"""Cohort splitting and temporal partitioning utility for Project AMOS / BPFeat.

Partitions canonical events into:
1. Train Split [1511539200, 1512050399] (Days 1–6 through 21:59:59 CST, 142 hours)
2. Train-to-Validation Purge / Embargo 1 (1512050399, 1512057599] (Day 6 22:00:00–23:59:59 CST, 2 hours)
3. Validation Split [1512057600, 1512136799] (Day 7 00:00:00–21:59:59 CST, 22 hours)
4. Validation-to-Test Purge / Embargo 2 (1512136799, 1512143999] (Day 7 22:00:00–23:59:59 CST, 2 hours)
5. Test Split [1512144000, 1512309599] (Days 8–9 through 21:59:59 CST, 46 hours)
   - Partitioned into 46 distinct hourly temporal clusters: test_hour_00 to test_hour_45
   - Satisfies min_test_groups >= 30 policy floor
6. Tail Censoring Buffer (1512309599, 1512316799] (Day 9 22:00:00–23:59:59 CST, 2 hours)
   - All events right-censored (censored = 1, label = None)
7. Cold-Entity OOD Split:
   - 10% of distinct user IDs (deterministic SHA-256 hash % 10 == 0) assigned to 'ood'
   - Complete disjointness from train and validation

Outputs schema-compliant cohort CSV:
seq,user_id,event_ts_ns,split,group_id,label,censored
"""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
for _p in (str(_project_root), str(_script_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from tools.generate_causal_labels import (
        DEFAULT_CAMPAIGN_END_SEC,
        DEFAULT_CAMPAIGN_START_SEC,
        DEFAULT_HORIZON_SEC,
        stream_causal_labels,
    )
except ImportError:
    from generate_causal_labels import (
        DEFAULT_CAMPAIGN_END_SEC,
        DEFAULT_CAMPAIGN_START_SEC,
        DEFAULT_HORIZON_SEC,
        stream_causal_labels,
    )

# Temporal boundary constants (epoch seconds, CST UTC+8)
CAMPAIGN_START_SEC = DEFAULT_CAMPAIGN_START_SEC  # 1511539200 (2017-11-25 00:00:00)
TRAIN_END_SEC = 1512050399                       # (2017-11-30 21:59:59, 142h)
EMBARGO_1_END_SEC = 1512057599                   # (2017-11-30 23:59:59, 2h)
VAL_START_SEC = 1512057600                       # (2017-12-01 00:00:00)
VAL_END_SEC = 1512136799                         # (2017-12-01 21:59:59, 22h)
EMBARGO_2_END_SEC = 1512143999                   # (2017-12-01 23:59:59, 2h)
TEST_START_SEC = 1512144000                      # (2017-12-02 00:00:00)
TEST_END_SEC = 1512309599                        # (2017-12-03 21:59:59, 46h)
CAMPAIGN_END_SEC = DEFAULT_CAMPAIGN_END_SEC      # 1512316799 (2017-12-03 23:59:59, 2h tail)


def is_ood_user(user_id: int, modulo: int = 10) -> bool:
    """Deterministic hash assigning ~1/modulo fraction of users to cold OOD split."""
    digest = hashlib.sha256(str(user_id).encode("utf-8")).digest()
    val = int.from_bytes(digest[:4], "big")
    return (val % modulo) == 0


def assign_split_and_group(user_id: int, timestamp_sec: int, ood_modulo: int = 10):
    """Assign an event to its temporal split and group identifier.
    
    Returns (split_name, group_id, is_tail_censored).
    """
    if is_ood_user(user_id, modulo=ood_modulo):
        hour_idx = min(max(0, (timestamp_sec - CAMPAIGN_START_SEC) // 3600), 215)
        is_tail = timestamp_sec > TEST_END_SEC
        return "ood", f"ood_hour_{hour_idx:03d}", is_tail

    if timestamp_sec <= TRAIN_END_SEC:
        hour_idx = min(max(0, (timestamp_sec - CAMPAIGN_START_SEC) // 3600), 141)
        return "train", f"train_hour_{hour_idx:03d}", False
    elif timestamp_sec <= EMBARGO_1_END_SEC:
        hour_idx = min(max(0, (timestamp_sec - (TRAIN_END_SEC + 1)) // 3600), 1)
        return "train_embargo", f"embargo_1_hour_{hour_idx:02d}", False
    elif timestamp_sec <= VAL_END_SEC:
        hour_idx = min(max(0, (timestamp_sec - VAL_START_SEC) // 3600), 21)
        return "validation", f"val_hour_{hour_idx:02d}", False
    elif timestamp_sec <= EMBARGO_2_END_SEC:
        hour_idx = min(max(0, (timestamp_sec - (VAL_END_SEC + 1)) // 3600), 1)
        return "val_embargo", f"embargo_2_hour_{hour_idx:02d}", False
    elif timestamp_sec <= TEST_END_SEC:
        hour_idx = min(max(0, (timestamp_sec - TEST_START_SEC) // 3600), 45)
        return "test", f"test_hour_{hour_idx:02d}", False
    else:
        hour_idx = min(max(0, (timestamp_sec - (TEST_END_SEC + 1)) // 3600), 1)
        return "tail_censored", f"tail_hour_{hour_idx:02d}", True


def generate_cohort_splits(
    canonical_input_path,
    output_cohort_path,
    manifest_path=None,
    labels_csv_path=None,
    evaluated_only=False,
    horizon_sec=DEFAULT_HORIZON_SEC,
    campaign_end_sec=DEFAULT_CAMPAIGN_END_SEC,
    ood_modulo=10,
    max_rows=None,
    verbose=False,
):
    """Generate canonical cohort CSV partitioned into temporal splits with embargoes and OOD.
    
    Returns accounting dictionary and writes split_manifest.json.
    """
    start_time = time.time()
    canonical_input_path = Path(canonical_input_path)
    output_cohort_path = Path(output_cohort_path)
    output_cohort_path.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path:
        manifest_path = Path(manifest_path)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Ensure causal labels are computed
    if labels_csv_path is not None and Path(labels_csv_path).exists():
        temp_labels_path = Path(labels_csv_path)
        cleanup_temp_labels = False
    else:
        temp_labels_path = output_cohort_path.parent / f"_temp_labels_{int(time.time())}.csv"
        cleanup_temp_labels = True
        if verbose:
            print(f"Generating causal labels for {canonical_input_path}...", file=sys.stderr)
        stream_causal_labels(
            input_path=canonical_input_path,
            output_path=temp_labels_path,
            horizon_sec=horizon_sec,
            campaign_end_sec=campaign_end_sec,
            max_rows=max_rows,
            verbose=verbose,
        )

    try:
        if verbose:
            print(f"Generating cohort splits from labels: {temp_labels_path}...", file=sys.stderr)

        split_counts = Counter()
        split_users = defaultdict(set)
        split_label_dist = defaultdict(Counter)
        test_group_counts = Counter()
        test_group_labels = defaultdict(Counter)

        total_rows = 0
        emitted_rows = 0

        with temp_labels_path.open("r", encoding="utf-8") as in_f, output_cohort_path.open(
            "w", encoding="utf-8", newline=""
        ) as out_f:
            header_line = in_f.readline()
            header = [col.strip() for col in header_line.split(",")]
            seq_idx = header.index("seq")
            ts_idx = header.index("event_ts_ns")
            user_idx = header.index("user_id")
            label_idx = header.index("label")
            censored_idx = header.index("censored")

            out_f.write("seq,user_id,event_ts_ns,split,group_id,label,censored\n")

            for line in in_f:
                if max_rows is not None and total_rows >= max_rows:
                    break
                total_rows += 1

                stripped = line.rstrip("\r\n")
                if not stripped:
                    continue

                parts = stripped.split(",")
                seq_id = int(parts[seq_idx])
                ts_ns = int(parts[ts_idx])
                uid = int(parts[user_idx])
                raw_label = parts[label_idx].strip()
                raw_censored = parts[censored_idx].strip()

                ts_sec = ts_ns // 1_000_000_000
                split_name, group_id, is_tail = assign_split_and_group(
                    user_id=uid, timestamp_sec=ts_sec, ood_modulo=ood_modulo
                )

                if evaluated_only and split_name in ("train_embargo", "val_embargo", "tail_censored"):
                    continue

                # Ensure tail censoring invariant
                if is_tail:
                    label_str = ""
                    censored_str = "1"
                else:
                    label_str = raw_label
                    censored_str = raw_censored

                out_f.write(f"{seq_id},{uid},{ts_ns},{split_name},{group_id},{label_str},{censored_str}\n")
                emitted_rows += 1

                split_counts[split_name] += 1
                split_users[split_name].add(uid)
                if label_str in ("0", "1"):
                    split_label_dist[split_name][label_str] += 1

                if split_name == "test":
                    test_group_counts[group_id] += 1
                    if label_str in ("0", "1"):
                        test_group_labels[group_id][label_str] += 1

        # Validation assertions
        ood_users = split_users.get("ood", set())
        train_users = split_users.get("train", set())
        val_users = split_users.get("validation", set())
        test_users = split_users.get("test", set())

        cold_ood_disjoint = len(ood_users & train_users) == 0 and len(ood_users & val_users) == 0
        num_test_groups = len(test_group_counts)

        # Build structured split manifest dictionary
        test_0 = split_label_dist["test"].get("0", 0)
        test_1 = split_label_dist["test"].get("1", 0)

        manifest = {
            "test_label_distribution": {
                "0": test_0,
                "1": test_1,
            },
            "test_group_count": num_test_groups,
            "independent_group_count": num_test_groups,
            "frozen_policy": {
                "min_class_count": 10,
                "min_test_groups": 30,
            },
            "sample_size_justification": f"Prospective evaluation over 46 hourly test clusters with {test_0} negative and {test_1} positive labels.",
            "imbalance_handling": "Label imbalance is handled via prospective AUPRC/average precision estimands and class-weighted / threshold-free ranking metrics without synthetic rebalancing or negative undersampling.",
            "splits_summary": {
                name: {
                    "row_count": split_counts[name],
                    "distinct_users": len(split_users[name]),
                    "pos_count": split_label_dist[name].get("1", 0),
                    "neg_count": split_label_dist[name].get("0", 0),
                    "censored_count": split_counts[name] - sum(split_label_dist[name].values()),
                }
                for name in split_counts
            },
            "acceptance_verifications": {
                "cold_ood_disjointness": cold_ood_disjoint,
                "test_groups_floor_satisfied": num_test_groups >= 30,
                "zero_cross_split_user_leakage_for_ood": len(ood_users & (train_users | val_users)) == 0,
            },
            "elapsed_seconds": round(time.time() - start_time, 2),
            "total_emitted_rows": emitted_rows,
        }

        if manifest_path:
            with manifest_path.open("w", encoding="utf-8") as mf:
                json.dump(manifest, mf, indent=2)

        return manifest

    finally:
        if cleanup_temp_labels and temp_labels_path.exists():
            temp_labels_path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Partition canonical events into purged temporal splits, embargoes, and cold OOD."
    )
    parser.add_argument("--input", "-i", type=str, required=True, help="Input canonical CSV path")
    parser.add_argument("--output", "-o", type=str, default="data/cohort.csv", help="Output cohort CSV path")
    parser.add_argument("--manifest", "-m", type=str, default="data/split_manifest.json", help="Output split manifest JSON")
    parser.add_argument("--labels", "-l", type=str, default=None, help="Precomputed causal labels CSV path (optional)")
    parser.add_argument("--evaluated-only", action="store_true", help="Emit only evaluated splits (train, validation, test, ood)")
    parser.add_argument("--horizon-sec", "-H", type=int, default=DEFAULT_HORIZON_SEC, help="Horizon in seconds")
    parser.add_argument("--campaign-end-sec", type=int, default=DEFAULT_CAMPAIGN_END_SEC, help="Campaign end seconds")
    parser.add_argument("--ood-modulo", type=int, default=10, help="OOD user hash modulo (default: 10 for 10%)")
    parser.add_argument("--max-rows", type=int, default=None, help="Max rows to process (for validation/testing)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print telemetry")

    args = parser.parse_args()

    results = generate_cohort_splits(
        canonical_input_path=args.input,
        output_cohort_path=args.output,
        manifest_path=args.manifest,
        labels_csv_path=args.labels,
        evaluated_only=args.evaluated_only,
        horizon_sec=args.horizon_sec,
        campaign_end_sec=args.campaign_end_sec,
        ood_modulo=args.ood_modulo,
        max_rows=args.max_rows,
        verbose=args.verbose,
    )

    print(json.dumps(results, indent=2))
    if not results["acceptance_verifications"]["cold_ood_disjointness"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
