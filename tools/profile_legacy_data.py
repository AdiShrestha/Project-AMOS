#!/usr/bin/env python3
"""Full streamed profiles of candidate raw and legacy replay files; no claims."""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path


def profile_taobao(path):
    behaviors, users = Counter(), set()
    count, malformed, last_user, previous_ts, regressions = 0, 0, None, None, 0
    minimum, maximum, max_category = None, None, 0
    with path.open(newline="") as stream:
        for row in csv.reader(stream):
            count += 1
            try:
                if len(row) != 5:
                    raise ValueError("width")
                uid, item, category = map(int, row[:3])
                behavior, ts = row[3], int(row[4])
                if min(uid, item, category, ts) < 0 or behavior not in {"pv", "cart", "fav", "buy"}:
                    raise ValueError("domain")
                users.add(uid)
                behaviors[behavior] += 1
                max_category = max(max_category, category)
                minimum = ts if minimum is None else min(minimum, ts)
                maximum = ts if maximum is None else max(maximum, ts)
                if uid == last_user and previous_ts is not None and ts < previous_ts:
                    regressions += 1
                last_user, previous_ts = uid, ts
            except ValueError:
                malformed += 1
            if count % 10000000 == 0:
                print("raw rows profiled", count, flush=True)
    return {"path": str(path), "rows": count, "unique_users": len(users), "behavior_counts": dict(behaviors),
            "invalid_rows": malformed, "min_timestamp_seconds": minimum, "max_timestamp_seconds": maximum,
            "max_category_id": max_category, "adjacent_same_user_time_regressions": regressions,
            "limits": "Schema/distribution profile; no provider authenticity or duplicate validation."}


def profile_replay(path):
    count, previous_seq, previous_ts, seq_bad, global_backwards = 0, None, None, 0, 0
    users, labels, last_per_key = set(), Counter(), {}
    key_backwards, category_overflow = 0, 0
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            count += 1
            seq, ts, key = int(row["seq"]), int(row["timestamp_ns"]), int(row["user_id"])
            if previous_seq is not None and seq <= previous_seq:
                seq_bad += 1
            if previous_ts is not None and ts < previous_ts:
                global_backwards += 1
            if key in last_per_key and ts < last_per_key[key]:
                key_backwards += 1
            category_overflow += int(int(row["category_id"]) > 65535)
            previous_seq, previous_ts, last_per_key[key] = seq, ts, ts
            users.add(key)
            labels[(row["label"], row["label_valid"])] += 1
    return {"path": str(path), "rows": count, "users": len(users), "label_valid_counts": {str(k): v for k, v in labels.items()},
            "nonincreasing_seq": seq_bad, "global_time_regressions": global_backwards,
            "per_key_time_regressions": key_backwards, "category_uint16_overflow_rows": category_overflow}


def profile_ulb(path):
    labels, n, invalid = Counter(), 0, 0
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            n += 1
            try:
                numbers = [float(v) for v in row.values()]
                if not all(math.isfinite(v) for v in numbers) or row["Class"] not in {"0", "1"}:
                    raise ValueError("domain")
                labels[row["Class"]] += 1
            except (ValueError, TypeError):
                invalid += 1
    return {"path": str(path), "rows": n, "label_counts": dict(labels), "invalid_numeric_rows": invalid,
            "limits": "Numeric/domain profile only; anonymous rows do not establish entity IDs."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.root
    results = {"taobao_raw": profile_taobao(root / "data/raw/UserBehavior.csv"),
               "ulb_raw": profile_ulb(root / "data/raw/creditcard.csv"),
               "replays": [profile_replay(p) for p in sorted((root / "data/replay").glob("replay_*.csv"))]}
    args.output.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
