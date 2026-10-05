#!/usr/bin/env python3
"""Scalable causal label generation utility for Project AMOS / BPFeat.

Calculates strict future-purchase labels for horizon H (default: 7200 seconds / 2 hours)
operating on canonically ordered event streams (seq, event_ts_ns, key/user_id, item_id, category_id, behavior_code).

Key Invariants:
1. Strict Future Window: Y_i = 1 iff user u_i makes >= 1 purchase (behavior_code == 3) in (t_i, t_i + H].
2. Zero Contemporaneous Leakage: Purchases at t_j = t_i do NOT cause Y_i = 1.
3. Right-Censoring: Events with t_i > T_end - H (final 2 hours of campaign) are marked censored = 1,
   label_valid = 0, and label = None. Never imputed as negative.
4. Positive Witness Tracking: For every Y_i = 1, records positive_witness_seq pointing to the
   exact sequence ID of the earliest triggering future purchase event.
"""

import argparse
from bisect import bisect_right
from collections import defaultdict
import csv
import json
import os
from pathlib import Path
import sys
import time

DEFAULT_HORIZON_SEC = 7200
DEFAULT_CAMPAIGN_START_SEC = 1511539200
DEFAULT_CAMPAIGN_END_SEC = 1512316799
BUY_BEHAVIOR_CODE = 3


def generate_causal_labels_from_events(events, horizon_ns, observation_end_ns):
    """In-memory causal label generator matching source/preprocessing/labels.py.
    
    Accepts an iterable of event dicts with keys:
      source_id (or seq), event_ts_ns, key (or user_id), behavior_code
    
    Returns a list of records with keys:
      seq, event_ts_ns, user_id, label, label_valid, censored, positive_witness_seq
    """
    if type(horizon_ns) is not int or horizon_ns <= 0:
        raise ValueError("positive integer horizon required")
    if type(observation_end_ns) is not int or not 0 <= observation_end_ns <= 2**64 - 1:
        raise ValueError("uint64 observation end required")

    events = list(events)
    buys = defaultdict(list)
    previous_time = None
    seen_ids = set()

    for event in events:
        identifier = str(event.get("seq", event.get("source_id", "")))
        timestamp = event["event_ts_ns"]
        key = event.get("user_id", event.get("key"))
        behavior = event["behavior_code"]

        if not identifier.strip() or identifier in seen_ids:
            raise ValueError("missing or duplicate source identity")
        if type(timestamp) is not int or not 0 <= timestamp <= observation_end_ns:
            raise ValueError("invalid event timestamp")
        if type(key) is not int or not 0 <= key <= 2**64 - 1 or type(behavior) is not int or behavior not in range(4):
            raise ValueError("invalid key/behavior")
        if previous_time is not None and timestamp < previous_time:
            raise ValueError("global event time regression")

        seen_ids.add(identifier)
        previous_time = timestamp
        if behavior == BUY_BEHAVIOR_CODE:
            buys[key].append((timestamp, int(identifier) if identifier.isdigit() else identifier))

    times = {key: [ts for ts, _ in records] for key, records in buys.items()}
    result = []
    censor_threshold_ns = observation_end_ns - horizon_ns

    for event in events:
        identifier = str(event.get("seq", event.get("source_id", "")))
        seq_val = int(identifier) if identifier.isdigit() else identifier
        t = event["event_ts_ns"]
        key = event.get("user_id", event.get("key"))
        end = t + horizon_ns

        record = {
            "seq": seq_val,
            "event_ts_ns": t,
            "user_id": key,
            "label": None,
            "label_valid": 0,
            "censored": 1,
            "positive_witness_seq": None,
        }

        if t <= censor_threshold_ns:
            user_times = times.get(key, [])
            index = bisect_right(user_times, t)
            positive = index < len(buys[key]) and buys[key][index][0] <= end
            record.update(
                label=int(positive),
                label_valid=1,
                censored=0,
                positive_witness_seq=buys[key][index][1] if positive else None,
            )

        result.append(record)

    return result


def stream_causal_labels(
    input_path,
    output_path,
    manifest_path=None,
    horizon_sec=DEFAULT_HORIZON_SEC,
    campaign_end_sec=DEFAULT_CAMPAIGN_END_SEC,
    max_rows=None,
    verbose=False,
):
    """Two-pass streaming causal label generator for large canonical event files.
    
    Pass 1: Collect all purchase events (behavior_code == 3) by user_id.
    Pass 2: Stream all events, perform bisect lookups for future buys, right-censor tail events,
            and emit causal label CSV.
    """
    start_time = time.time()
    input_path = Path(input_path)
    output_path = Path(output_path)
    if manifest_path:
        manifest_path = Path(manifest_path)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    horizon_ns = horizon_sec * 1_000_000_000
    campaign_end_ns = campaign_end_sec * 1_000_000_000
    censor_threshold_ns = campaign_end_ns - horizon_ns

    # Pass 1: Collect purchases
    # user_id -> list of (event_ts_ns, seq)
    buys = defaultdict(list)
    total_raw_events = 0
    total_buys = 0

    if verbose:
        print(f"[Pass 1] Scanning {input_path} for purchase events (behavior={BUY_BEHAVIOR_CODE})...", file=sys.stderr)

    with input_path.open("r", encoding="utf-8") as in_f:
        header_line = in_f.readline()
        if not header_line:
            raise ValueError(f"Empty input file: {input_path}")
        header = [col.strip() for col in header_line.split(",")]
        try:
            seq_idx = header.index("seq")
            ts_idx = header.index("event_ts_ns")
            user_idx = header.index("key") if "key" in header else header.index("user_id")
            beh_idx = header.index("behavior_code")
        except ValueError as e:
            raise ValueError(f"Missing required canonical column: {e}")

        for line in in_f:
            if max_rows is not None and total_raw_events >= max_rows:
                break
            total_raw_events += 1

            # Fast path check for buy behavior
            stripped = line.rstrip("\r\n")
            if not stripped:
                continue

            parts = stripped.split(",")
            try:
                beh = int(parts[beh_idx])
            except (IndexError, ValueError):
                continue

            if beh == BUY_BEHAVIOR_CODE:
                seq_id = int(parts[seq_idx])
                ts_ns = int(parts[ts_idx])
                uid = int(parts[user_idx])
                buys[uid].append((ts_ns, seq_id))
                total_buys += 1

    pass1_duration = time.time() - start_time
    if verbose:
        print(f"[Pass 1 Complete] Indexed {total_buys} purchases across {len(buys)} users in {pass1_duration:.2f}s.", file=sys.stderr)

    # Pre-extract sorted buy timestamps for bisect_right
    buy_times = {uid: [ts for ts, _ in recs] for uid, recs in buys.items()}

    # Pass 2: Stream all events and generate causal labels
    if verbose:
        print(f"[Pass 2] Generating strict-future labels (H={horizon_sec}s, T_end={campaign_end_sec})...", file=sys.stderr)

    accounting = {
        "total_events_processed": 0,
        "evaluated_events": 0,
        "censored_events": 0,
        "positive_labels": 0,
        "negative_labels": 0,
        "positive_rate_evaluated": 0.0,
        "positive_witness_count": 0,
        "zero_contemporaneous_leakage_verified": True,
        "witness_integrity_verified": True,
        "horizon_seconds": horizon_sec,
        "campaign_end_seconds": campaign_end_sec,
        "censor_threshold_seconds": campaign_end_sec - horizon_sec,
    }

    with input_path.open("r", encoding="utf-8") as in_f, output_path.open("w", encoding="utf-8", newline="") as out_f:
        in_f.readline()  # skip input header
        out_f.write("seq,event_ts_ns,user_id,label,label_valid,censored,positive_witness_seq\n")

        row_count = 0
        for line in in_f:
            if max_rows is not None and row_count >= max_rows:
                break
            row_count += 1

            stripped = line.rstrip("\r\n")
            if not stripped:
                continue

            parts = stripped.split(",")
            seq_id = int(parts[seq_idx])
            ts_ns = int(parts[ts_idx])
            uid = int(parts[user_idx])

            accounting["total_events_processed"] += 1

            if ts_ns > censor_threshold_ns:
                # Right-censored tail event
                accounting["censored_events"] += 1
                out_f.write(f"{seq_id},{ts_ns},{uid},,0,1,\n")
            else:
                # Fully observed window: (ts_ns, ts_ns + horizon_ns]
                accounting["evaluated_events"] += 1
                user_timestamps = buy_times.get(uid, [])
                idx = bisect_right(user_timestamps, ts_ns)
                user_buy_records = buys[uid]

                if idx < len(user_buy_records) and user_buy_records[idx][0] <= ts_ns + horizon_ns:
                    # Positive label
                    witness_ts, witness_seq = user_buy_records[idx]
                    # Verify no contemporaneous leakage
                    if witness_ts <= ts_ns:
                        accounting["zero_contemporaneous_leakage_verified"] = False
                    accounting["positive_labels"] += 1
                    accounting["positive_witness_count"] += 1
                    out_f.write(f"{seq_id},{ts_ns},{uid},1,1,0,{witness_seq}\n")
                else:
                    # Negative label
                    accounting["negative_labels"] += 1
                    out_f.write(f"{seq_id},{ts_ns},{uid},0,1,0,\n")

    if accounting["evaluated_events"] > 0:
        accounting["positive_rate_evaluated"] = round(
            accounting["positive_labels"] / accounting["evaluated_events"], 6
        )

    accounting["witness_integrity_verified"] = (
        accounting["positive_labels"] == accounting["positive_witness_count"]
    )
    accounting["elapsed_seconds"] = round(time.time() - start_time, 2)

    if manifest_path:
        with manifest_path.open("w", encoding="utf-8") as mf:
            json.dump(accounting, mf, indent=2)

    if verbose:
        print(f"[Done] Processed {accounting['total_events_processed']} events in {accounting['elapsed_seconds']}s.", file=sys.stderr)

    return accounting


def main():
    parser = argparse.ArgumentParser(
        description="Scalable causal label generation utility with positive witness tracking and right-censoring."
    )
    parser.add_argument("--input", "-i", type=str, required=True, help="Input canonical CSV path")
    parser.add_argument("--output", "-o", type=str, required=True, help="Output causal labels CSV path")
    parser.add_argument("--manifest", "-m", type=str, default=None, help="Output summary manifest JSON path")
    parser.add_argument("--horizon-sec", "-H", type=int, default=DEFAULT_HORIZON_SEC, help="Prediction horizon in seconds")
    parser.add_argument("--campaign-end-sec", type=int, default=DEFAULT_CAMPAIGN_END_SEC, help="Campaign end epoch seconds")
    parser.add_argument("--max-rows", type=int, default=None, help="Max rows to process (for validation/testing)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print telemetry")

    args = parser.parse_args()

    results = stream_causal_labels(
        input_path=args.input,
        output_path=args.output,
        manifest_path=args.manifest,
        horizon_sec=args.horizon_sec,
        campaign_end_sec=args.campaign_end_sec,
        max_rows=args.max_rows,
        verbose=args.verbose,
    )

    print(json.dumps(results, indent=2))
    if not results["zero_contemporaneous_leakage_verified"] or not results["witness_integrity_verified"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
