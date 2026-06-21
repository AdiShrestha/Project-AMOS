"""
compute_metrics.py — Offline metric computation (Sections 25–26).

Computes the full set of evaluation metrics from ResultSink's CSV output:
  - PATR    (Pressure-Adaptive Throughput Retention, Section 25.1)
  - WOR     (Window Oscillation Rate, Section 25.2) — from harness summary
  - FR      (Feature Regret, Section 25.3) — requires oracle score recomputation
  - Staleness (Section 25.4)
  - Fairness gap (Section 25.6)
  - Coverage fraction (Section 26, point 1)
  - Shuffled-features null baseline check (Section 26, point 2)

Usage:
    python compute_metrics.py \\
        --results-dir results/raw \\
        --replay data/replay/replay_taobao_10k.csv \\
        --model models/classifier_weights.txt \\
        [--alpha-max 0.30] \\
        [--out-csv results/metrics_summary.csv]
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import scipy.stats as stats
import json


# ── Oracle feature recomputation ──────────────────────────────────────────────
ENGAGEMENT_WEIGHT = {0: 1.0, 1: 3.0, 2: 2.0, 3: 5.0}

def compute_oracle_scores(replay_csv: str, weights_txt: str, alpha_max: float) -> pd.DataFrame:
    """
    Recompute oracle scores for all events using the stored model weights
    and alpha=alpha_max, W=1. Returns a DataFrame keyed by 'seq' with
    columns ['seq', 'oracle_score', 'label', 'label_valid'].
    """
    raw = pd.read_csv(replay_csv)

    # Load weights
    weights = {}
    with open(weights_txt) as f:
        for line in f:
            k, v = line.strip().split("=")
            weights[k] = float(v)
    bias = weights["bias"]
    w = np.array([weights[f"w{i}"] for i in range(4)], dtype=np.float64)

    raw = raw.sort_values(["user_id", "timestamp_ns"]).reset_index(drop=True)
    out_rows = []
    for uid, g in raw.groupby("user_id", sort=False):
        ema = 0.0; pv = 0; cart_fav = 0; prev_ts = 0.0
        for _, row in g.iterrows():
            bc = int(row.get("behavior_code", 0))
            wt = ENGAGEMENT_WEIGHT.get(bc, 1.0)
            ema = alpha_max * wt + (1.0 - alpha_max) * ema
            if bc == 0: pv += 1
            elif bc in (1, 2): cart_fav += 1
            ts_sec = row["timestamp_ns"] / 1e9
            recency = 0.0 if prev_ts == 0.0 else min(ts_sec - prev_ts, 3600.0) / 3600.0
            prev_ts = ts_sec
            x = np.array([ema, np.log1p(pv), np.log1p(cart_fav), recency])
            z = bias + np.dot(w, x)
            oracle_score = 1.0 / (1.0 + np.exp(-z))
            out_rows.append({"seq": row["seq"], "oracle_score": oracle_score,
                              "label": row["label"], "label_valid": row["label_valid"]})
    return pd.DataFrame(out_rows)


def bce(p: np.ndarray, y: np.ndarray, eps: float = 1e-7) -> np.ndarray:
    """Binary cross-entropy per sample."""
    p = np.clip(p, eps, 1.0 - eps)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def feature_regret(results_df: pd.DataFrame, oracle_df: pd.DataFrame) -> dict:
    """
    FR = mean[ BCE(online_score, label) - BCE(oracle_score, label) ]
    over all label_valid=1 events. Can be negative (Section 25.3).
    """
    merged = results_df.merge(oracle_df[["seq","oracle_score"]], on="seq", how="inner")
    valid  = merged[merged["label_valid"] == 1].copy()
    if len(valid) == 0:
        return {"fr_mean": float("nan"), "fr_std": float("nan"), "n_valid": 0}

    label = valid["label"].to_numpy(dtype=np.float64)
    online_score  = valid["score"].to_numpy(dtype=np.float64)
    oracle_score_ = valid["oracle_score"].to_numpy(dtype=np.float64)

    fr_per_sample = bce(online_score, label) - bce(oracle_score_, label)
    return {
        "fr_mean":    float(fr_per_sample.mean()),
        "fr_std":     float(fr_per_sample.std()),
        "n_valid":    int(len(valid)),
        "coverage":   float(len(valid) / len(oracle_df[oracle_df["label_valid"]==1])),
    }


def patr(results_df: pd.DataFrame) -> dict:
    """
    PATR = throughput during burst / throughput during calm.
    Throughput = rows per second computed from result_timestamp_ns.
    """
    if "is_burst_period" not in results_df.columns:
        return {"patr": float("nan")}

    burst = results_df[results_df["is_burst_period"] == 1]
    calm  = results_df[results_df["is_burst_period"] == 0]

    def tput(df):
        if len(df) < 2: return 0.0
        span_sec = (df["result_timestamp_ns"].max()
                  - df["result_timestamp_ns"].min()) / 1e9
        return len(df) / max(span_sec, 1e-6)

    b_rate = tput(burst)
    c_rate = tput(calm)
    return {"patr": b_rate / c_rate if c_rate > 0 else float("nan"),
            "burst_tput": b_rate, "calm_tput": c_rate}


def fairness_gap(results_df: pd.DataFrame) -> float:
    """
    Staleness averaged over bottom-quartile users (by event count)
    minus staleness averaged over top-quartile users.
    """
    by_user = results_df.groupby("user_id").agg(
        count=("seq", "count"), mean_stale=("staleness_sec", "mean")).reset_index()
    if len(by_user) < 4:
        return float("nan")
    q25 = by_user["count"].quantile(0.25)
    q75 = by_user["count"].quantile(0.75)
    low_users  = by_user[by_user["count"] <= q25]["mean_stale"].mean()
    high_users = by_user[by_user["count"] >= q75]["mean_stale"].mean()
    return float(low_users - high_users)


def shuffled_null_baseline(results_df: pd.DataFrame, oracle_df: pd.DataFrame) -> float:
    """
    Section 26 point 2: compute FR after shuffling oracle features.
    Should produce significantly larger FR than any real architecture.
    """
    merged = results_df.merge(oracle_df[["seq","oracle_score"]], on="seq", how="inner")
    valid  = merged[merged["label_valid"] == 1].copy()
    if len(valid) == 0:
        return float("nan")
    shuffled_oracle = valid["oracle_score"].to_numpy().copy()
    rng = np.random.default_rng(0)
    rng.shuffle(shuffled_oracle)
    label = valid["label"].to_numpy(dtype=np.float64)
    online = valid["score"].to_numpy(dtype=np.float64)
    fr_shuffle = (bce(online, label) - bce(shuffled_oracle, label)).mean()
    return float(fr_shuffle)


def mean_ci(values: list, alpha: float = 0.05):
    """Returns (mean, lower, upper) 95% CI using t-distribution."""
    n = len(values)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    m = np.mean(values)
    if n == 1:
        return m, m, m
    se = stats.sem(values)
    ci = stats.t.interval(1 - alpha, df=n-1, loc=m, scale=se)
    return m, ci[0], ci[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--replay",      required=True)
    ap.add_argument("--model",       required=True)
    ap.add_argument("--alpha-max",   type=float, default=0.30)
    ap.add_argument("--out-csv",     default="results/metrics_summary.csv")
    args = ap.parse_args()

    results_dir = Path(args.results_dir)

    print("[compute_metrics] Computing oracle scores ...")
    oracle_df = compute_oracle_scores(args.replay, args.model, args.alpha_max)
    print(f"  {len(oracle_df):,} oracle rows, "
          f"{oracle_df['label_valid'].sum():,} labeled")

    archs = ["fixed", "drift", "throttle", "adaptive"]
    all_metrics = []

    for arch in archs:
        csv_files = sorted(results_dir.glob(f"results_{arch}_seed*.csv"))
        if not csv_files:
            print(f"[compute_metrics] No results found for arch={arch}")
            continue

        fr_list, patr_list, stale_list, fair_list, cov_list = [], [], [], [], []
        for csv_path in csv_files:
            try:
                df = pd.read_csv(csv_path)
            except Exception as e:
                print(f"  skipping {csv_path}: {e}")
                continue

            fr   = feature_regret(df, oracle_df)
            pt   = patr(df)
            fair = fairness_gap(df)

            fr_list.append(fr.get("fr_mean", float("nan")))
            patr_list.append(pt.get("patr", float("nan")))
            stale_list.append(df["staleness_sec"].mean())
            fair_list.append(fair)
            cov_list.append(fr.get("coverage", float("nan")))

        null_fr = float("nan")
        if csv_files:
            df_last = pd.read_csv(csv_files[-1])
            null_fr = shuffled_null_baseline(df_last, oracle_df)

        fr_m, fr_lo, fr_hi     = mean_ci(fr_list)
        patr_m, patr_lo, patr_hi = mean_ci(patr_list)
        stale_m, stale_lo, stale_hi = mean_ci(stale_list)
        fair_m, _, _           = mean_ci(fair_list)
        cov_m, _, _            = mean_ci(cov_list)

        row = {
            "arch": arch, "n_runs": len(fr_list),
            "fr_mean": fr_m, "fr_ci_lo": fr_lo, "fr_ci_hi": fr_hi,
            "patr_mean": patr_m, "patr_ci_lo": patr_lo, "patr_ci_hi": patr_hi,
            "mean_staleness_sec": stale_m,
            "staleness_ci_lo": stale_lo, "staleness_ci_hi": stale_hi,
            "fairness_gap": fair_m,
            "coverage": cov_m,
            "shuffled_null_fr": null_fr,
        }
        all_metrics.append(row)

        print(f"\n[{arch}]")
        print(f"  FR = {fr_m:.5f} [{fr_lo:.5f}, {fr_hi:.5f}]  (null={null_fr:.4f})")
        print(f"  PATR = {patr_m:.3f} [{patr_lo:.3f}, {patr_hi:.3f}]")
        print(f"  Staleness = {stale_m:.3f}s  Coverage = {cov_m:.3f}  Fairness gap = {fair_m:.3f}s")

    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_metrics).to_csv(args.out_csv, index=False)
    print(f"\n[compute_metrics] Summary → {args.out_csv}")


if __name__ == "__main__":
    main()
