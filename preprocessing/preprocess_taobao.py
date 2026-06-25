"""
preprocess_taobao.py — Taobao UserBehavior dataset preprocessor (Section 11).

Reads the raw UserBehavior.csv (Alibaba Tianchi, ~100M rows), subsamples
N_USERS users by hash-bucket (not row order to avoid ordering artifacts),
retains all events for those users across the full 9-day window, tags burst
periods from the natural arrival-rate time series, and writes a replay CSV
in the schema expected by BehaviorSource::load_replay_csv().

Usage:
    python preprocess_taobao.py \\
        --raw data/raw/UserBehavior.csv \\
        --out data/replay/replay_taobao_10k.csv \\
        --n-users 10000 \\
        --seed 42

Output schema:
    seq, timestamp_ns, user_id, item_id, category_id, behavior_code,
    label, label_valid, is_burst_period
"""

import argparse
import hashlib
import sys
import numpy as np
import pandas as pd
from pathlib import Path

# behavior_type string → behavior_code integer
BEHAVIOR_MAP = {"pv": 0, "cart": 1, "fav": 2, "buy": 3}
# Reverse for logging
BEHAVIOR_NAMES = {v: k for k, v in BEHAVIOR_MAP.items()}


def hash_bucket(user_id: int, n_buckets: int, seed: int) -> int:
    """Deterministic hash-bucket assignment so subsampling is reproducible."""
    h = int(hashlib.sha256(f"{seed}:{user_id}".encode()).hexdigest(), 16)
    return h % n_buckets


def tag_burst_periods(df: pd.DataFrame, window_minutes: int = 30,
                      burst_multiplier: float = 2.0) -> pd.Series:
    """
    Tag rows whose time window has event density > burst_multiplier × median.
    Uses a rolling count of events in a sliding 30-minute window over the
    full dataset timestamp range. Returns a boolean Series aligned with df.index.
    """
    # Bin timestamps into window_minutes-wide bins
    ts_min = df["timestamp_ns"] // int(60e9)  # minutes since epoch
    bin_counts = ts_min.value_counts()
    median_rate = bin_counts.median()
    threshold = burst_multiplier * median_rate
    burst_bins = set(bin_counts[bin_counts > threshold].index.tolist())
    return ts_min.isin(burst_bins).astype(np.uint8)


def compute_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Label assignment (Section 10):
    A user's events are labeled label=1 (purchase propensity) if there is a 'buy'
    event within 2 hours after the current event, 0 otherwise. label_valid=1 for 
    all events where the forward 2-hour window is fully within the dataset time range.
    """
    df = df.sort_values(["user_id", "timestamp_ns"]).copy()
    labels = np.zeros(len(df), dtype=np.uint8)
    label_valid = np.zeros(len(df), dtype=np.uint8)

    window_ns = 2 * 60 * 60 * int(1e9)  # 2 hours
    max_ts = df["timestamp_ns"].max()

    for uid, g in df.groupby("user_id", sort=False):
        idx = g.index.tolist()
        ts  = g["timestamp_ns"].values
        bc  = g["behavior_code"].values

        buy_indices = np.where(bc == 3)[0]
        for i, ix in enumerate(idx):
            label_valid[ix] = 1 if (max_ts - ts[i]) >= window_ns else 0
            
            has_buy = False
            for bi in buy_indices:
                if ts[i] <= ts[bi] <= ts[i] + window_ns:
                    has_buy = True
                    break
            labels[ix] = 1 if has_buy else 0

    df["label"]       = pd.Series(labels, index=np.arange(len(df)))
    df["label_valid"] = pd.Series(label_valid, index=np.arange(len(df)))
    return df


def main():
    ap = argparse.ArgumentParser(description="Preprocess Taobao UserBehavior CSV")
    ap.add_argument("--raw",     required=True, help="Path to raw UserBehavior.csv")
    ap.add_argument("--out",     required=True, help="Output replay CSV path")
    ap.add_argument("--n-users", type=int, default=10000, help="Number of users to subsample")
    ap.add_argument("--seed",    type=int, default=42, help="Hash-bucket seed")
    ap.add_argument("--burst-multiplier", type=float, default=2.0,
                    help="Burst threshold as a multiple of median event density")
    args = ap.parse_args()

    print(f"[preprocess_taobao] Reading {args.raw} ...")
    # Raw file has no header; columns: user_id, item_id, category_id, behavior_type, timestamp
    raw = pd.read_csv(args.raw, header=None,
                      names=["user_id","item_id","category_id","behavior_type","timestamp"],
                      dtype={"user_id":np.int32,"item_id":np.int32,
                             "category_id":np.int32,"behavior_type":str,"timestamp":np.int64})
    print(f"[preprocess_taobao] Loaded {len(raw):,} rows, {raw['user_id'].nunique():,} users")

    # Subsample users by hash bucket
    n_buckets = 100  # divide users into 100 buckets, keep buckets [0, n_buckets * frac)
    n_full    = raw["user_id"].nunique()
    frac      = args.n_users / n_full
    target_buckets = max(1, int(n_buckets * frac))
    all_users = raw["user_id"].unique()
    selected  = {u for u in all_users if hash_bucket(u, n_buckets, args.seed) < target_buckets}
    df = raw[raw["user_id"].isin(selected)].copy()
    print(f"[preprocess_taobao] Subsampled to {len(df):,} rows, {df['user_id'].nunique():,} users")

    # Encode behavior_type
    df["behavior_code"] = df["behavior_type"].map(BEHAVIOR_MAP).fillna(0).astype(np.uint8)

    # timestamp in seconds → nanoseconds
    df["timestamp_ns"] = df["timestamp"].astype(np.int64) * 1_000_000_000

    # Assign item_id, category_id as uint32
    df["item_id"]     = df["item_id"].astype(np.int32)
    df["category_id"] = df["category_id"].astype(np.int32)

    # Sort globally by timestamp
    df = df.sort_values("timestamp_ns").reset_index(drop=True)

    # Label assignment
    print("[preprocess_taobao] Computing purchase-propensity labels ...")
    df = compute_labels(df)

    # Burst tagging
    print("[preprocess_taobao] Tagging burst periods ...")
    df["is_burst_period"] = tag_burst_periods(df, burst_multiplier=args.burst_multiplier)

    # Sequential seq column
    df["seq"] = np.arange(len(df), dtype=np.uint64)

    # Write output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_cols = ["seq","timestamp_ns","user_id","item_id","category_id",
                "behavior_code","label","label_valid","is_burst_period"]
    df[out_cols].to_csv(args.out, index=False)
    print(f"[preprocess_taobao] Wrote {len(df):,} rows → {args.out}")
    print(f"  buy-label rate: {df[df['label_valid']==1]['label'].mean():.4f}")
    print(f"  burst fraction: {df['is_burst_period'].mean():.4f}")


if __name__ == "__main__":
    main()
