"""
preprocess_ulb.py — ULB Credit Card Fraud dataset preprocessor (Section 11).

Limitation stated plainly (Decision 4): the ULB dataset has no per-entity key
(V1-V28 are PCA-anonymized). All events are assigned user_id=0, making this the
"degenerate single-key" case (Section 13.4). Only global rolling features are
computed — no per-card keyed state. The label is the 'Class' column (0=legitimate,
1=fraud). behavior_code is always 0 (no semantic Taobao mapping).

Usage:
    python preprocess_ulb.py \\
        --raw data/raw/creditcard.csv \\
        --out data/replay/replay_ulb.csv \\
        --burst-multiplier 2.5

Output schema:
    seq, timestamp_ns, user_id, item_id, category_id, behavior_code,
    amount, label, label_valid, is_burst_period
"""

import argparse
import sys
from pathlib import Path
import numpy as np
import pandas as pd


def tag_burst_periods(df: pd.DataFrame, window_minutes: int = 5,
                      burst_multiplier: float = 2.5) -> pd.Series:
    """
    Tag rows by transaction density. ULB uses 5-minute bins (finer than
    Taobao) because the dataset spans only 2 days with dense activity.
    """
    ts_min = (df["Time"].astype(np.float64) // 300).astype(np.int64)  # 5-min bins
    bin_counts = ts_min.value_counts()
    threshold  = burst_multiplier * bin_counts.median()
    burst_bins = set(bin_counts[bin_counts > threshold].index.tolist())
    return ts_min.isin(burst_bins).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description="Preprocess ULB Credit Card Fraud CSV")
    ap.add_argument("--raw",     required=True, help="Path to raw creditcard.csv")
    ap.add_argument("--out",     required=True, help="Output replay CSV path")
    ap.add_argument("--burst-multiplier", type=float, default=2.5)
    ap.add_argument("--base-ts-ns", type=int,
                    default=1493596800 * 1_000_000_000,
                    help="Base timestamp for Time=0 (default: 2017-05-01 00:00 UTC)")
    args = ap.parse_args()

    print(f"[preprocess_ulb] Reading {args.raw} ...")
    raw = pd.read_csv(args.raw)
    print(f"[preprocess_ulb] Loaded {len(raw):,} rows")

    # timestamp_ns: base + Time (seconds) * 1e9
    raw["timestamp_ns"] = (args.base_ts_ns
                           + (raw["Time"].astype(np.float64) * 1_000_000_000).astype(np.int64))

    # Sort by time (already sorted in ULB, but make explicit)
    raw = raw.sort_values("Time").reset_index(drop=True)

    # user_id = 0 for all rows (degenerate single-key case — Section 13.4)
    raw["user_id"]      = np.uint32(0)
    raw["item_id"]      = np.uint32(0)
    raw["category_id"]  = np.uint16(0)
    raw["behavior_code"] = np.uint8(0)

    # label = Class column; all rows are label_valid
    raw["label"]       = raw["Class"].astype(np.uint8)
    raw["label_valid"] = np.uint8(1)

    # Burst tagging
    print("[preprocess_ulb] Tagging burst periods ...")
    raw["is_burst_period"] = tag_burst_periods(raw, burst_multiplier=args.burst_multiplier)

    raw["seq"] = np.arange(len(raw), dtype=np.uint64)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_cols = ["seq","timestamp_ns","user_id","item_id","category_id",
                "behavior_code","Amount","label","label_valid","is_burst_period"]
    # Rename Amount to lowercase for consistency with BehaviorSource schema
    raw_out = raw[out_cols].rename(columns={"Amount":"amount"})
    raw_out.to_csv(args.out, index=False)
    print(f"[preprocess_ulb] Wrote {len(raw_out):,} rows → {args.out}")
    print(f"  fraud rate: {raw['label'].mean():.4f}")
    print(f"  burst fraction: {raw['is_burst_period'].mean():.4f}")


if __name__ == "__main__":
    main()
