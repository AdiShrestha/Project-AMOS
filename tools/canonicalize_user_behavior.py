#!/usr/bin/env python3
"""Bounded-memory canonicalization and external sorting pipeline for Taobao UserBehavior events.

Enforces 64-bit integer domains, eliminates uint16 category narrowing (Finding F12),
filters timestamp anomalies and out-of-campaign calendar outliers (Finding F14),
deduplicates exact 5-tuple records, enforces deterministic multi-key tie-breaking,
and emits strictly increasing monotonic 64-bit sequence IDs.
"""

import argparse
import csv
import heapq
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Campaign window: 2017-11-25 00:00:00 to 2017-12-03 23:59:59 China Standard Time (UTC+8)
DEFAULT_CAMPAIGN_START = 1511539200
DEFAULT_CAMPAIGN_END = 1512316799

# Behavior mapping to engine codes (source/README.md)
# pv=0, cart=1, fav=2, buy=3
BEHAVIOR_TO_CODE = {
    "pv": 0,
    "cart": 1,
    "fav": 2,
    "buy": 3,
}

# Tie-breaking order (Contract AMOS-03 Section 2.3):
# pv (0) < fav (1) < cart (2) < buy (3)
BEHAVIOR_SORT_ORDER = {
    "pv": 0,
    "fav": 1,
    "cart": 2,
    "buy": 3,
}


def parse_and_validate_row(row_str, line_idx=None):
    """Parse and validate a raw CSV line.
    
    Returns (user_id, item_id, category_id, behavior_str, timestamp) or raises ValueError.
    Ensures 64-bit representation without narrowing.
    """
    parts = row_str.rstrip("\r\n").split(",")
    if len(parts) != 5:
        raise ValueError(f"Line {line_idx}: expected 5 fields, got {len(parts)}")
    
    u_str, i_str, c_str, b_str, t_str = parts
    if not (u_str and i_str and c_str and b_str and t_str):
        raise ValueError(f"Line {line_idx}: empty field encountered")
    
    try:
        user_id = int(u_str)
        item_id = int(i_str)
        category_id = int(c_str)
        timestamp = int(t_str)
    except ValueError as e:
        raise ValueError(f"Line {line_idx}: non-integer numerical token: {e}")
    
    if user_id < 0 or item_id < 0 or category_id < 0:
        raise ValueError(f"Line {line_idx}: negative identifier encountered")
    
    if b_str not in BEHAVIOR_TO_CODE:
        raise ValueError(f"Line {line_idx}: unrecognized behavior '{b_str}'")
        
    return user_id, item_id, category_id, b_str, timestamp


def canonicalize(
    input_path,
    output_path,
    ledger_path=None,
    chunk_size=500000,
    campaign_start=DEFAULT_CAMPAIGN_START,
    campaign_end=DEFAULT_CAMPAIGN_END,
    temp_dir=None,
    max_rows=None,
    verbose=False,
):
    """Stream raw UserBehavior events, filter outliers, sort externally, and emit canonical events.
    
    Returns a dictionary of accounting statistics.
    """
    start_time = time.time()
    input_path = Path(input_path)
    output_path = Path(output_path)
    if ledger_path:
        ledger_path = Path(ledger_path)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    accounting = {
        "raw_rows_read": 0,
        "negative_timestamp_outliers": 0,
        "before_window_outliers": 0,
        "after_window_outliers": 0,
        "total_calendar_outliers": 0,
        "in_window_candidates": 0,
        "deduplicated_duplicates": 0,
        "canonical_valid_emitted": 0,
        "chunks_created": 0,
        "chunk_size": chunk_size,
        "campaign_start": campaign_start,
        "campaign_end": campaign_end,
    }

    temp_files = []
    
    # We use a managed tempdir if not explicitly provided
    tmp_context = tempfile.TemporaryDirectory(dir=temp_dir)
    work_dir = Path(tmp_context.name)

    try:
        # Phase 1: Stream, filter, partition into sorted chunks
        chunk = []
        
        with input_path.open("r", encoding="utf-8", errors="replace") as in_f:
            for line_idx, line in enumerate(in_f, 1):
                if max_rows is not None and accounting["raw_rows_read"] >= max_rows:
                    break
                accounting["raw_rows_read"] += 1
                
                user_id, item_id, category_id, b_str, timestamp = parse_and_validate_row(line, line_idx)
                
                # Check negative timestamps
                if timestamp < 0:
                    accounting["negative_timestamp_outliers"] += 1
                    accounting["total_calendar_outliers"] += 1
                    continue
                
                # Check campaign window
                if timestamp < campaign_start:
                    accounting["before_window_outliers"] += 1
                    accounting["total_calendar_outliers"] += 1
                    continue
                elif timestamp > campaign_end:
                    accounting["after_window_outliers"] += 1
                    accounting["total_calendar_outliers"] += 1
                    continue
                
                accounting["in_window_candidates"] += 1
                
                # In-window candidate: record tuple
                # Sort Key: (timestamp, user_id, item_id, category_id, sort_order)
                sort_order = BEHAVIOR_SORT_ORDER[b_str]
                behavior_code = BEHAVIOR_TO_CODE[b_str]
                
                chunk.append((timestamp, user_id, item_id, category_id, sort_order, behavior_code))
                
                if len(chunk) >= chunk_size:
                    chunk.sort()
                    chunk_file = work_dir / f"chunk_{accounting['chunks_created']:05d}.tsv"
                    with chunk_file.open("w", encoding="utf-8") as cf:
                        for rec in chunk:
                            cf.write(f"{rec[0]}\t{rec[1]}\t{rec[2]}\t{rec[3]}\t{rec[4]}\t{rec[5]}\n")
                    temp_files.append(chunk_file)
                    accounting["chunks_created"] += 1
                    chunk.clear()
                    if verbose and accounting["chunks_created"] % 10 == 0:
                        print(f"Created {accounting['chunks_created']} sorted runs...", file=sys.stderr)

        # Flush final partial chunk
        if chunk:
            chunk.sort()
            chunk_file = work_dir / f"chunk_{accounting['chunks_created']:05d}.tsv"
            with chunk_file.open("w", encoding="utf-8") as cf:
                for rec in chunk:
                    cf.write(f"{rec[0]}\t{rec[1]}\t{rec[2]}\t{rec[3]}\t{rec[4]}\t{rec[5]}\n")
            temp_files.append(chunk_file)
            accounting["chunks_created"] += 1
            chunk.clear()

        # Phase 2: K-way merge, deduplication, monotonic seq assignment, emit CSV
        def iter_chunk(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                for row in f:
                    ts_s, u_s, i_s, c_s, o_s, b_s = row.rstrip("\n").split("\t")
                    yield (int(ts_s), int(u_s), int(i_s), int(c_s), int(o_s), int(b_s))

        chunk_iterators = [iter_chunk(cf) for cf in temp_files]
        merged_stream = heapq.merge(*chunk_iterators, key=lambda r: (r[0], r[1], r[2], r[3], r[4]))

        seq = 0
        prev_key = None
        
        with output_path.open("w", encoding="utf-8", newline="") as out_f:
            # Emit standard AMOS replay header
            out_f.write("seq,event_ts_ns,key,item_id,category_id,behavior_code\n")
            
            for rec in merged_stream:
                ts, user_id, item_id, category_id, sort_order, behavior_code = rec
                # Exact 5-tuple deduplication check
                key = (ts, user_id, item_id, category_id, sort_order)
                if prev_key is not None and key == prev_key:
                    accounting["deduplicated_duplicates"] += 1
                    continue
                
                prev_key = key
                
                # event_ts_ns: seconds to nanoseconds
                event_ts_ns = ts * 1000000000
                out_f.write(f"{seq},{event_ts_ns},{user_id},{item_id},{category_id},{behavior_code}\n")
                seq += 1
                accounting["canonical_valid_emitted"] += 1

        accounting["elapsed_seconds"] = round(time.time() - start_time, 2)
        
        # Verify conservation law:
        # raw_rows = canonical_valid + total_calendar_outliers + deduplicated_duplicates
        expected_total = (
            accounting["canonical_valid_emitted"]
            + accounting["total_calendar_outliers"]
            + accounting["deduplicated_duplicates"]
        )
        accounting["conservation_law_satisfied"] = (accounting["raw_rows_read"] == expected_total)
        
        if ledger_path:
            with ledger_path.open("w", encoding="utf-8") as lf:
                json.dump(accounting, lf, indent=2)

        return accounting

    finally:
        tmp_context.cleanup()


def main():
    parser = argparse.ArgumentParser(
        description="Bounded-memory canonicalization and external sorting pipeline for Taobao UserBehavior."
    )
    parser.add_argument("--input", "-i", type=str, required=True, help="Input raw CSV path")
    parser.add_argument("--output", "-o", type=str, required=True, help="Output canonical CSV path")
    parser.add_argument("--ledger", "-l", type=str, default=None, help="Output exclusion ledger JSON path")
    parser.add_argument("--chunk-size", type=int, default=500000, help="Number of records per external sort chunk")
    parser.add_argument("--temp-dir", type=str, default=None, help="Temporary directory for intermediate runs")
    parser.add_argument("--campaign-start", type=int, default=DEFAULT_CAMPAIGN_START, help="Campaign start epoch seconds")
    parser.add_argument("--campaign-end", type=int, default=DEFAULT_CAMPAIGN_END, help="Campaign end epoch seconds")
    parser.add_argument("--max-rows", type=int, default=None, help="Maximum raw rows to process (for validation)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print progress telemetry")

    args = parser.parse_args()

    results = canonicalize(
        input_path=args.input,
        output_path=args.output,
        ledger_path=args.ledger,
        chunk_size=args.chunk_size,
        campaign_start=args.campaign_start,
        campaign_end=args.campaign_end,
        temp_dir=args.temp_dir,
        max_rows=args.max_rows,
        verbose=args.verbose,
    )

    print(json.dumps(results, indent=2))
    if not results["conservation_law_satisfied"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
