#!/usr/bin/env python3
"""Open-loop workload generator for Project AMOS / BPFeat.

Generates deterministic, scheduled arrival traces for events and queries with precise
timestamps (t_sched_ns) across 4 contiguous phases:
1. Warm-up: 2,000 events, 0 queries (cache pre-population)
2. Baseline: 5,000 events, 1,000 queries (steady-state nominal load)
3. Stress: 15,000 events, 3,000 queries (overload spike)
4. Recovery: 5,000 events, 1,000 queries (post-stress stabilization)

Total events: 27,000. Total queries: 5,000.
Events are drawn strictly from the Day 7 validation split [1512057600, 1512136799].
Zero test split events are accessed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple

# Day 7 Validation temporal boundaries (epoch seconds, CST UTC+8)
VAL_START_SEC: int = 1512057600   # 2017-12-01 00:00:00 CST
VAL_END_SEC: int = 1512136799     # 2017-12-01 21:59:59 CST
TEST_START_SEC: int = 1512144000  # 2017-12-02 00:00:00 CST

# Phase specifications: (name, num_events, num_queries, event_rate_hz, query_rate_hz)
PHASE_SPECS = [
    ("warm_up", 2000, 0, 1000.0, 0.0),
    ("baseline", 5000, 1000, 1000.0, 200.0),
    ("stress", 15000, 3000, 5000.0, 1000.0),
    ("recovery", 5000, 1000, 1000.0, 200.0),
]

TOTAL_EVENTS: int = sum(spec[1] for spec in PHASE_SPECS)   # 27,000
TOTAL_QUERIES: int = sum(spec[2] for spec in PHASE_SPECS)  # 5,000


@dataclass(frozen=True)
class ScheduledEvent:
    phase: str
    phase_idx: int
    seq: int
    t_sched_ns: int
    event_ts_ns: int
    key: int
    item_id: int
    category_id: int
    behavior_code: int


@dataclass(frozen=True)
class ScheduledQuery:
    phase: str
    phase_idx: int
    query_id: int
    t_sched_ns: int
    key: int


def load_validation_events(
    source_path: Path,
    cohort_path: Optional[Path] = None,
    target_count: int = TOTAL_EVENTS,
) -> List[Tuple[int, int, int, int, int]]:
    """Load valid events strictly from the Day 7 validation window.

    Returns list of (event_ts_ns, key, item_id, category_id, behavior_code).
    """
    valid_events: List[Tuple[int, int, int, int, int]] = []
    cohort_val_seqs: Optional[Set[int]] = None

    if cohort_path and cohort_path.exists():
        cohort_val_seqs = set()
        with cohort_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("split") == "validation":
                    cohort_val_seqs.add(int(row["seq"]))

    with source_path.open("r", encoding="utf-8") as f:
        header = f.readline()
        # Detect if raw (5 cols, no header) or canonical (6 cols with header)
        if "seq" in header or "event_ts_ns" in header:
            reader = csv.DictReader(f, fieldnames=[c.strip() for c in header.split(",")])
            for row in reader:
                ts_ns = int(row["event_ts_ns"])
                ts_sec = ts_ns // 1_000_000_000

                # Strict test leakage check
                if ts_sec >= TEST_START_SEC:
                    continue

                seq_val = int(row.get("seq", -1))
                if cohort_val_seqs is not None and seq_val not in cohort_val_seqs:
                    continue

                if VAL_START_SEC <= ts_sec <= VAL_END_SEC:
                    k = int(row.get("key") or row.get("user_id"))
                    item = int(row.get("item_id", 0))
                    cat = int(row.get("category_id", 0))
                    beh = int(row.get("behavior_code", 0))
                    valid_events.append((ts_ns, k, item, cat, beh))
                    if len(valid_events) >= target_count:
                        break
        else:
            # Raw CSV: user_id,item_id,category_id,behavior,timestamp
            behavior_map = {"pv": 0, "fav": 1, "cart": 2, "buy": 3}
            # Rewind to line 0
            f.seek(0)
            for line in f:
                parts = line.strip().split(",")
                if len(parts) != 5:
                    continue
                ts_sec = int(parts[4])

                # Strict test isolation
                if ts_sec >= TEST_START_SEC:
                    continue

                if VAL_START_SEC <= ts_sec <= VAL_END_SEC:
                    beh_str = parts[3]
                    beh_code = behavior_map.get(beh_str, -1) if beh_str in behavior_map else int(beh_str)
                    if 0 <= beh_code <= 3:
                        ts_ns = ts_sec * 1_000_000_000
                        k = int(parts[0])
                        item = int(parts[1])
                        cat = int(parts[2])
                        valid_events.append((ts_ns, k, item, cat, beh_code))
                        if len(valid_events) >= target_count:
                            break

    # If fewer than target_count, cycle deterministically to guarantee complete phase lengths
    if 0 < len(valid_events) < target_count:
        base_events = list(valid_events)
        while len(valid_events) < target_count:
            idx = len(valid_events) % len(base_events)
            item = base_events[idx]
            valid_events.append(item)

    if not valid_events:
        raise ValueError(f"No validation events found in {source_path} within [{VAL_START_SEC}, {VAL_END_SEC}]")

    return valid_events[:target_count]


def generate_open_loop_trace(
    validation_events: List[Tuple[int, int, int, int, int]],
    seed: int = 42,
    cold_query_ratio: float = 0.10,
) -> Tuple[List[ScheduledEvent], List[ScheduledQuery]]:
    """Build open-loop scheduled arrival traces across the 4 phases."""
    rng = random.Random(seed)
    scheduled_events: List[ScheduledEvent] = []
    scheduled_queries: List[ScheduledQuery] = []

    current_t_sched_ns = 0
    event_ptr = 0
    global_seq = 0
    global_qid = 0
    active_keys: List[int] = []
    seen_keys: Set[int] = set()

    for phase_idx, (phase_name, num_ev, num_q, ev_rate, q_rate) in enumerate(PHASE_SPECS):
        phase_start_ns = current_t_sched_ns
        ev_dt_ns = int(1e9 / ev_rate) if ev_rate > 0 else 0
        q_dt_ns = int(1e9 / q_rate) if q_rate > 0 else 0

        # Precompute scheduled event times
        phase_ev_times = [phase_start_ns + i * ev_dt_ns for i in range(num_ev)]
        # Precompute scheduled query times
        phase_q_times = [phase_start_ns + i * q_dt_ns for i in range(num_q)] if num_q > 0 else []

        phase_duration_ns = max(
            phase_ev_times[-1] if phase_ev_times else phase_start_ns,
            phase_q_times[-1] if phase_q_times else phase_start_ns,
        ) - phase_start_ns + (ev_dt_ns if ev_dt_ns > 0 else 1_000_000)

        # Emit events for this phase
        for ev_time in phase_ev_times:
            raw_ts_ns, k, item, cat, beh = validation_events[event_ptr]
            event_ptr += 1

            if k not in seen_keys:
                seen_keys.add(k)
                active_keys.append(k)

            scheduled_events.append(
                ScheduledEvent(
                    phase=phase_name,
                    phase_idx=phase_idx,
                    seq=global_seq,
                    t_sched_ns=ev_time,
                    event_ts_ns=raw_ts_ns,
                    key=k,
                    item_id=item,
                    category_id=cat,
                    behavior_code=beh,
                )
            )
            global_seq += 1

        # Emit queries for this phase
        for q_time in phase_q_times:
            # Decide whether cold key or warm key
            is_cold = (rng.random() < cold_query_ratio) or (len(active_keys) == 0)
            if is_cold:
                key = 90_000_000 + global_qid
            else:
                key = rng.choice(active_keys)

            scheduled_queries.append(
                ScheduledQuery(
                    phase=phase_name,
                    phase_idx=phase_idx,
                    query_id=global_qid,
                    t_sched_ns=q_time,
                    key=key,
                )
            )
            global_qid += 1

        current_t_sched_ns = phase_start_ns + phase_duration_ns

    return scheduled_events, scheduled_queries


def main() -> None:
    parser = argparse.ArgumentParser(description="Open-loop workload generator for Project AMOS")
    parser.add_argument("--source", "-s", type=Path, default=Path("data/quarantine/raw/UserBehavior.csv"), help="Source data CSV")
    parser.add_argument("--cohort", "-c", type=Path, default=Path("data/cohort.csv"), help="Cohort CSV (optional)")
    parser.add_argument("--out-events", type=Path, default=Path("data/pilot_events_scheduled.csv"), help="Output scheduled events CSV")
    parser.add_argument("--out-queries", type=Path, default=Path("data/pilot_queries_scheduled.csv"), help="Output scheduled queries CSV")
    parser.add_argument("--out-manifest", type=Path, default=Path("data/pilot_workload_manifest.json"), help="Output workload manifest JSON")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic RNG seed")

    args = parser.parse_args()

    print(f"Loading {TOTAL_EVENTS} validation events from {args.source}...", file=sys.stderr)
    val_events = load_validation_events(args.source, cohort_path=args.cohort, target_count=TOTAL_EVENTS)
    print(f"Loaded {len(val_events)} validation events.", file=sys.stderr)

    events, queries = generate_open_loop_trace(val_events, seed=args.seed)

    # Write events
    args.out_events.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_events, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["phase", "phase_idx", "seq", "t_sched_ns", "event_ts_ns", "key", "item_id", "category_id", "behavior_code"])
        for e in events:
            writer.writerow([e.phase, e.phase_idx, e.seq, e.t_sched_ns, e.event_ts_ns, e.key, e.item_id, e.category_id, e.behavior_code])

    # Write queries
    args.out_queries.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_queries, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["phase", "phase_idx", "query_id", "t_sched_ns", "key"])
        for q in queries:
            writer.writerow([q.phase, q.phase_idx, q.query_id, q.t_sched_ns, q.key])

    # Generate manifest
    distinct_keys = len({e.key for e in events})
    manifest = {
        "workload_type": "open_loop",
        "total_scheduled_events": len(events),
        "total_scheduled_queries": len(queries),
        "distinct_event_keys": distinct_keys,
        "phases": {
            spec[0]: {
                "phase_idx": idx,
                "scheduled_events": spec[1],
                "scheduled_queries": spec[2],
                "target_event_rate_hz": spec[3],
                "target_query_rate_hz": spec[4],
            }
            for idx, spec in enumerate(PHASE_SPECS)
        },
        "temporal_source": {
            "window": "Day 7 Validation [1512057600, 1512136799]",
            "zero_test_leakage_verified": True,
        },
    }

    if args.out_manifest:
        with open(args.out_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
