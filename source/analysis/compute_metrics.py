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
    python compute_metrics.py \
        --raw-dir results/raw \
        --oracle-csv data/replay/oracle_scores.csv \
        [--out-csv results/metrics_summary.csv]
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import scipy.stats as stats
import json


from sklearn.metrics import average_precision_score, roc_auc_score

# ── Oracle feature recomputation ──────────────────────────────────────────────
ENGAGEMENT_WEIGHT = {0: 1.0, 1: 3.0, 2: 2.0, 3: 5.0}

def bce(p: np.ndarray, y: np.ndarray, eps: float = 1e-7) -> np.ndarray:
    """Binary cross-entropy per sample."""
    p = np.clip(p, eps, 1.0 - eps)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def feature_regret(results_df: pd.DataFrame, oracle_df: pd.DataFrame) -> dict:
    """
    FR = mean[ BCE(online_score, label) - BCE(score_oracle, label) ]
    over all label_valid=1 events. Can be negative (Section 25.3).
    """
    merged = results_df.merge(oracle_df[["seq","score_oracle"]], on="seq", how="inner")
    valid  = merged[merged["label_valid"] == 1].copy()
    if len(valid) == 0:
        return {"fr_mean": float("nan"), "n_valid": 0, "coverage": 0.0}

    label = valid["label"].to_numpy(dtype=np.float64)
    online_score  = valid["score"].to_numpy(dtype=np.float64)
    oracle_score_ = valid["score_oracle"].to_numpy(dtype=np.float64)

    fr_per_sample = bce(online_score, label) - bce(oracle_score_, label)
    
    auprc = average_precision_score(label, online_score) if len(np.unique(label)) > 1 else float("nan")
    
    return {
        "fr_mean":    float(fr_per_sample.mean()),
        "auprc":      float(auprc),
        "n_valid":    int(len(valid)),
        "coverage":   float(len(valid) / len(oracle_df[oracle_df["label_valid"]==1])),
        "valid_df":   valid  # for MBB computation
    }

def compute_mbb_ci(valid_dfs: list, n_blocks=50, B=600):
    """
    Moving Block Bootstrap for FR and AUPRC.
    Averages predictions across runs to denoise, partitions into blocks, 
    and resamples to compute CIs.
    """
    if not valid_dfs:
        return float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), float("nan")
        
    combined = pd.concat(valid_dfs)
    agg_df = combined.groupby("seq").agg({
        "score": "mean",
        "score_oracle": "first",
        "label": "first"
    }).sort_index()
    
    label = agg_df["label"].to_numpy()
    score = agg_df["score"].to_numpy()
    oracle = agg_df["score_oracle"].to_numpy()
    
    fr_per_sample = bce(score, label) - bce(oracle, label)
    base_fr = fr_per_sample.mean()
    base_auprc = average_precision_score(label, score) if len(np.unique(label)) > 1 else float("nan")
    res_bce = bce(score, label)
    ora_bce = bce(oracle, label)
    
    N = len(label)
    block_size = max(1, N // n_blocks)
    n_blocks = int(np.ceil(N / block_size))
    
    regret_per_event = res_bce - ora_bce
    
    nan_count = np.isnan(regret_per_event).sum()
    if nan_count > 0:
        print(f"  [MBB Warning] Replaced {nan_count} NaN values in regret_per_event before MBB.")
        regret_per_event = np.nan_to_num(regret_per_event, nan=0.0)
        
    boot_fr = []
    boot_auprc = []
    
    rng = np.random.default_rng(42)
    
    for _ in range(B):
        idx = rng.integers(0, n_blocks, size=n_blocks)
        res_fr, res_label, res_score = [], [], []
        for i in idx:
            start = i * block_size
            end = min(N, (i + 1) * block_size)
            res_fr.extend(fr_per_sample[start:end])
            res_label.extend(label[start:end])
            res_score.extend(score[start:end])
            
        res_fr = np.array(res_fr)
        res_label = np.array(res_label)
        res_score = np.array(res_score)
        
        boot_fr.append(res_fr.mean())
        if len(np.unique(res_label)) > 1:
            boot_auprc.append(average_precision_score(res_label, res_score))
            
    fr_lo, fr_hi = np.percentile(boot_fr, [2.5, 97.5])
    auprc_lo, auprc_hi = np.percentile(boot_auprc, [2.5, 97.5]) if boot_auprc else (float("nan"), float("nan"))
    
    return base_fr, fr_lo, fr_hi, base_auprc, auprc_lo, auprc_hi


def compute_patr(df: pd.DataFrame) -> dict:
    """
    Burst throughput / calm throughput, measured in events per wall-clock second.
    Uses result_timestamp_ns from ResultSink to measure actual processing rate.
    Gap 3 guard: if timestamps are essentially constant (std < 1e6 ns) return nan.
    """
    # Gap 3 verification guard
    if df['result_timestamp_ns'].std() < 1e6:
        return {"patr": float("nan"), "burst_tput": float("nan"), "calm_tput": float("nan"),
                "note": "result_timestamp_ns appears constant — not wall-clock"}

    burst = df[df['is_burst_period'] == 1].copy()
    calm  = df[df['is_burst_period'] == 0].copy()

    if len(burst) < 2 or len(calm) < 2:
        return {"patr": float("nan"), "burst_tput": float("nan"), "calm_tput": float("nan")}

    burst_duration_ns = burst['result_timestamp_ns'].max() - burst['result_timestamp_ns'].min()
    calm_duration_ns  = calm['result_timestamp_ns'].max() - calm['result_timestamp_ns'].min()

    if burst_duration_ns <= 0 or calm_duration_ns <= 0:
        return {"patr": float("nan"), "burst_tput": float("nan"), "calm_tput": float("nan")}

    burst_throughput = len(burst) / (burst_duration_ns / 1e9)
    calm_throughput  = len(calm)  / (calm_duration_ns  / 1e9)

    patr_val = burst_throughput / calm_throughput if calm_throughput > 0 else float('nan')
    return {"patr": patr_val, "burst_tput": burst_throughput, "calm_tput": calm_throughput}


# Gap 1: Claude's exact burst-stratified staleness function
def compute_burst_stratified_staleness(run_csv_path: str) -> dict:
    """
    Computes staleness separately for burst and calm periods.
    This is the primary metric for Mechanism A: burst_mean << calm_mean when working.
    For MaxRate with perpetual saturation, burst_mean ≈ calm_mean (mechanism not visible).
    """
    df = pd.read_csv(run_csv_path)
    if 'is_burst_period' not in df.columns or 'staleness_sec' not in df.columns:
        return {'error': 'missing columns'}
    burst = df[df['is_burst_period'] == 1]['staleness_sec']
    calm  = df[df['is_burst_period'] == 0]['staleness_sec']
    return {
        'burst_mean':  float(burst.mean()),
        'burst_p50':   float(burst.quantile(0.50)),
        'burst_p95':   float(burst.quantile(0.95)),
        'burst_p99':   float(burst.quantile(0.99)),
        'burst_n':     int(len(burst)),
        'calm_mean':   float(calm.mean()),
        'calm_p50':    float(calm.quantile(0.50)),
        'calm_p95':    float(calm.quantile(0.95)),
        'calm_p99':    float(calm.quantile(0.99)),
        'calm_n':      int(len(calm)),
        'burst_calm_ratio': float(burst.mean() / calm.mean()) if calm.mean() > 0 else float('nan'),
    }



def fairness_gap(results_df: pd.DataFrame) -> dict:
    """
    Staleness averaged over bottom-quartile users (by event count)
    minus staleness averaged over top-quartile users.
    Also computes Jain's Fairness Index on staleness, and activity percentiles.
    """
    by_user = results_df.groupby("user_id").agg(
        count=("seq", "count"), mean_stale=("staleness_sec", "mean")).reset_index()
    
    if len(by_user) < 4:
        return {"fairness_gap": float("nan"), "jain": float("nan"), "p10": float("nan"), "p90": float("nan")}
        
    q25 = by_user["count"].quantile(0.25)
    q75 = by_user["count"].quantile(0.75)
    low_users  = by_user[by_user["count"] <= q25]["mean_stale"].mean()
    high_users = by_user[by_user["count"] >= q75]["mean_stale"].mean()
    
    # Jain's Fairness Index on staleness
    stale_vals = by_user["mean_stale"].values
    sum_stale = np.sum(stale_vals)
    sum_sq_stale = np.sum(stale_vals**2)
    jain = (sum_stale**2) / (len(stale_vals) * sum_sq_stale) if sum_sq_stale > 0 else 1.0
    
    p10 = by_user["count"].quantile(0.10)
    p90 = by_user["count"].quantile(0.90)
    
    return {
        "fairness_gap": float(low_users - high_users),
        "jain": float(jain),
        "p10": float(p10),
        "p90": float(p90)
    }


def shuffled_null_baseline(results_df: pd.DataFrame, oracle_df: pd.DataFrame) -> float:
    """
    Section 26 point 2: compute FR after shuffling oracle features.
    Should produce significantly larger FR than any real architecture.
    """
    merged = results_df.merge(oracle_df[["seq","score_oracle"]], on="seq", how="inner")
    valid  = merged[merged["label_valid"] == 1].copy()
    if len(valid) == 0:
        return float("nan")
        
    shuffled_scores = valid['score'].sample(frac=1, random_state=42).values
    eps = 1e-9
    shuffled_scores = np.clip(shuffled_scores, eps, 1-eps)
    oracle_scores = np.clip(valid['score_oracle'].values, eps, 1-eps)
    labels = valid['label'].values
    
    bce_shuffled = -(labels * np.log(shuffled_scores) + (1-labels) * np.log(1-shuffled_scores))
    bce_oracle   = -(labels * np.log(oracle_scores)   + (1-labels) * np.log(1-oracle_scores))
    null_regret = float(np.mean(bce_shuffled - bce_oracle))
    return null_regret


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


def compute_burst_stratified_metrics(run_csv: str) -> dict:
    """
    Computes staleness separately for burst and calm periods.
    
    This is the primary metric for Mechanism A's contribution:
    - During burst: Adaptive W shrinks → features refreshed after 8 events
    - During calm:  Adaptive W grows  → features refreshed after up to 256 events
    - Fixed always waits for 128 events → no differentiation between burst/calm
    
    The burst-period staleness ratio (Fixed / Adaptive) should be ~16×
    if the controller is working correctly.
    """
    df = pd.read_csv(run_csv)
    
    if 'is_burst_period' not in df.columns:
        return {'error': 'is_burst_period column missing from results CSV'}
    if 'staleness_sec' not in df.columns:
        return {'error': 'staleness_sec column missing from results CSV'}
    
    burst = df[df['is_burst_period'] == 1]
    calm  = df[df['is_burst_period'] == 0]
    
    def safe_stats(series):
        if len(series) == 0:
            return {'mean': float('nan'), 'p50': float('nan'),
                    'p95': float('nan'), 'p99': float('nan'), 'n': 0}
        return {
            'mean': float(series.mean()),
            'p50':  float(series.quantile(0.50)),
            'p95':  float(series.quantile(0.95)),
            'p99':  float(series.quantile(0.99)),
            'n':    int(len(series))
        }
    
    # Per-user burst staleness (mean staleness per user during burst periods)
    if 'user_id' in df.columns and len(burst) > 0:
        user_burst_staleness = burst.groupby('user_id')['staleness_sec'].mean()
        user_calm_staleness  = calm.groupby('user_id')['staleness_sec'].mean() if len(calm) > 0 else pd.Series()
        per_user_burst_mean = float(user_burst_staleness.mean())
        per_user_calm_mean  = float(user_calm_staleness.mean()) if len(user_calm_staleness) > 0 else float('nan')
    else:
        per_user_burst_mean = float('nan')
        per_user_calm_mean  = float('nan')
    
    return {
        'burst_staleness': safe_stats(burst['staleness_sec']),
        'calm_staleness':  safe_stats(calm['staleness_sec']),
        'per_user_burst_mean_staleness_sec': per_user_burst_mean,
        'per_user_calm_mean_staleness_sec':  per_user_calm_mean,
        'burst_event_count': int(len(burst)),
        'calm_event_count':  int(len(calm)),
    }

def compute_feature_refresh_rate(run_csv: str) -> dict:
    """
    Feature refresh rate = number of times per user per hour their features
    are updated (i.e., they appear in a ScoredResult row).
    
    For Adaptive (W=8 during burst): 16 refreshes per 128 events
    For Fixed (W=128 always):         1 refresh per 128 events
    → Adaptive provides 16× more frequent feature refreshes during burst.
    
    This is the correct metric for Mechanism A: not throughput, but freshness cadence.
    """
    df = pd.read_csv(run_csv)
    
    required = ['user_id', 'result_timestamp_ns', 'is_burst_period']
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {'error': f'Missing columns: {missing}'}
    
    if df['result_timestamp_ns'].std() == 0:
        return {'error': 'result_timestamp_ns is constant — wall-clock timestamps not set'}
    
    results = {}
    for period_name, mask in [('burst', df['is_burst_period'] == 1),
                               ('calm',  df['is_burst_period'] == 0)]:
        sub = df[mask]
        if len(sub) == 0:
            results[period_name] = {'refreshes_per_user_per_hour': float('nan')}
            continue
        
        # Duration of this period in hours (wall-clock)
        duration_ns = sub['result_timestamp_ns'].max() - sub['result_timestamp_ns'].min()
        duration_hours = duration_ns / 3.6e12
        
        if duration_hours <= 0:
            results[period_name] = {'refreshes_per_user_per_hour': float('nan')}
            continue
        
        if 'user_id' in sub.columns:
            total_refreshes = len(sub)
            unique_users = sub['user_id'].nunique()
            refreshes_per_user_per_hour = (total_refreshes / unique_users) / duration_hours
        else:
            refreshes_per_user_per_hour = float('nan')
        
        results[period_name] = {
            'refreshes_per_user_per_hour': refreshes_per_user_per_hour,
            'duration_hours': duration_hours,
            'total_refreshes': len(sub),
            'unique_users': sub['user_id'].nunique() if 'user_id' in sub.columns else 0,
        }
    
    # Ratio: burst refresh rate vs calm refresh rate (higher = better staleness control)
    burst_rate = results.get('burst', {}).get('refreshes_per_user_per_hour', float('nan'))
    calm_rate  = results.get('calm',  {}).get('refreshes_per_user_per_hour', float('nan'))
    results['burst_to_calm_refresh_ratio'] = burst_rate / calm_rate if calm_rate > 0 else float('nan')
    
    return results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--oracle-csv",  required=True)
    ap.add_argument("--out-csv",     default="results/metrics_summary.csv")
    args = ap.parse_args()

    results_dir = Path(args.raw_dir)

    print("[compute_metrics] Loading oracle scores ...")
    oracle_df = pd.read_csv(args.oracle_csv)
    print(f"  {len(oracle_df):,} oracle rows, "
          f"{oracle_df['label'].sum():,} labeled positive")

    archs = ["fixed", "drift", "throttle", "aonly", "bonly", "adaptive", "ralf"]
    all_metrics = []

    for arch in archs:
        csv_files = sorted(results_dir.glob(f"results_{arch}_seed*.csv"))
        if not csv_files:
            print(f"[compute_metrics] No results found for arch={arch}")
            continue

        fr_list, patr_list, stale_list, fair_list, cov_list, valid_dfs = [], [], [], [], [], []
        for csv_path in csv_files:
            try:
                df = pd.read_csv(csv_path)
            except Exception as e:
                print(f"  skipping {csv_path}: {e}")
                continue

            fr   = feature_regret(df, oracle_df)
            pt   = compute_patr(df)
            fair = fairness_gap(df)

            fr_list.append(fr.get("fr_mean", float("nan")))
            patr_list.append(pt.get("patr", float("nan")))
            stale_list.append(df["staleness_sec"].mean())
            fair_list.append(fair)
            cov_list.append(fr.get("coverage", float("nan")))
            if "valid_df" in fr:
                valid_dfs.append(fr["valid_df"])

        # We compute burst/refresh metrics for the first valid seed to match Claude's instructions
        burst_metrics = {}
        refresh_metrics = {}
        if csv_files:
            burst_metrics = compute_burst_stratified_metrics(str(csv_files[0]))
            refresh_metrics = compute_feature_refresh_rate(str(csv_files[0]))

        null_fr = float("nan")
        if csv_files:
            df_last = pd.read_csv(csv_files[-1])
            null_fr = shuffled_null_baseline(df_last, oracle_df)

        # MBB for FR and AUPRC
        fr_m, fr_lo, fr_hi, auprc_m, auprc_lo, auprc_hi = compute_mbb_ci(valid_dfs)
        
        patr_m, patr_lo, patr_hi = mean_ci(patr_list)
        stale_m, stale_lo, stale_hi = mean_ci(stale_list)
        fair_gap_m, _, _       = mean_ci([f.get("fairness_gap", float("nan")) for f in fair_list])
        jain_m, _, _           = mean_ci([f.get("jain", float("nan")) for f in fair_list])
        p10_m, _, _            = mean_ci([f.get("p10", float("nan")) for f in fair_list])
        p90_m, _, _            = mean_ci([f.get("p90", float("nan")) for f in fair_list])
        cov_m, _, _            = mean_ci(cov_list)

        row = {
            "arch": arch, "n_runs": len(fr_list),
            "fr_mean": fr_m, "fr_ci_lo": fr_lo, "fr_ci_hi": fr_hi,
            "auprc_mean": auprc_m, "auprc_ci_lo": auprc_lo, "auprc_ci_hi": auprc_hi,
            "patr_mean": patr_m, "patr_ci_lo": patr_lo, "patr_ci_hi": patr_hi,
            "mean_staleness_sec": stale_m,
            "staleness_ci_lo": stale_lo, "staleness_ci_hi": stale_hi,
            "fairness_gap": fair_gap_m,
            "coverage": cov_m,
            "shuffled_null_fr": null_fr,
        }
        all_metrics.append(row)
        
        oracle_auroc = roc_auc_score(oracle_df[oracle_df["label_valid"] == 1]["label"],
                                                oracle_df[oracle_df["label_valid"] == 1]["score_oracle"])
        from datetime import datetime

        print(f"=== BPFeat Experiment Output Block ===")
        print(f"Run timestamp: {datetime.now().isoformat()}")
        print(f"Architecture:  {arch}")
        print(f"Dataset:       {args.oracle_csv} (via oracle)")
        print(f"Seed:          all_seeds_avg")
        if valid_dfs:
            print(f"N events processed: {len(df)}")  # approx
            print(f"N events scored (label_valid=1): {sum(len(v) for v in valid_dfs)//len(valid_dfs)}")
        else:
            print(f"N events processed: 0\nN events scored (label_valid=1): 0")
        print(f"Coverage fraction: {cov_m:.3f}")
        print(f"\n--- Controller Trace (Adaptive/AOnly/BOnly only) ---")
        trace_files = list(results_dir.glob(f"harness_summary_{arch}_seed*.csv"))
        if not trace_files:
            print("trace file missing")
        else:
            tr_dfs = [pd.read_csv(f) for f in trace_files]
            tr_df = pd.concat(tr_dfs)
            # tr_df has: arch,seed,final_W,final_alpha,direction_changes,W_min,W_max,alpha_min,alpha_max
            # "N/A" means non-adaptive, but pandas parses it as string or NaN.
            if tr_df['final_W'].dtype == object and tr_df['final_W'].iloc[0] == 'N/A':
                print(f"final_W:              N/A")
                print(f"final_alpha:          N/A")
                print(f"direction_changes:    N/A")
                print(f"WOR (dir_changes/min):N/A")
                print(f"W_min_observed:       N/A")
                print(f"W_max_observed:       N/A")
                print(f"alpha_min_observed:   N/A")
                print(f"alpha_max_observed:   N/A")
            else:
                for col in ['final_W', 'final_alpha', 'direction_changes', 'W_min', 'W_max', 'alpha_min', 'alpha_max']:
                    tr_df[col] = pd.to_numeric(tr_df[col], errors='coerce')
                w_m = tr_df['final_W'].mean()
                a_m = tr_df['final_alpha'].mean()
                dc_m = tr_df['direction_changes'].mean()
                w_min_m = tr_df['W_min'].mean()
                w_max_m = tr_df['W_max'].mean()
                a_min_m = tr_df['alpha_min'].mean()
                a_max_m = tr_df['alpha_max'].mean()
                # Compute duration in minutes for WOR
                df_dur = df["result_timestamp_ns"].max() - df["result_timestamp_ns"].min()
                dur_min = df_dur / 1e9 / 60.0 if len(df) > 1 else 1.0
                wor = dc_m / dur_min
                print(f"final_W:              {w_m:.1f}")
                print(f"final_alpha:          {a_m:.4f}")
                print(f"direction_changes:    {dc_m:.1f}")
                print(f"WOR (dir_changes/min):{wor:.2f}")
                print(f"W_min_observed:       {w_min_m:.1f}")
                print(f"W_max_observed:       {w_max_m:.1f}")
                print(f"alpha_min_observed:   {a_min_m:.4f}")
                print(f"alpha_max_observed:   {a_max_m:.4f}")
        print(f"\n--- Throughput ---")
        print(f"steady_state_events_per_sec: N/A")
        print(f"burst_period_events_per_sec: N/A")
        print(f"PATR:                        {patr_m:.3f}")
        print(f"p50_latency_ms:              N/A")
        print(f"p99_latency_ms:              N/A")
        print(f"\n--- Feature Regret (requires oracle_scores.csv) ---")
        print(f"mean_feature_regret:  {fr_m:.5f}")
        print(f"regret_ci_lower:      {fr_lo:.5f}  [MBB 95% CI]")
        print(f"regret_ci_upper:      {fr_hi:.5f}  [MBB 95% CI]")
        print(f"MBB_block_length:     50")
        print(f"mean_staleness_sec:   {stale_m:.3f}")
        print(f"\n--- Fairness (Taobao only) ---")
        print(f"jain_fairness_index:  {jain_m:.4f}")
        print(f"fairness_gap_sec:     {fair_gap_m:.3f}")
        print(f"user_activity_p10:    {p10_m:.1f}  events")
        print(f"user_activity_p90:    {p90_m:.1f}  events")
        print(f"\n--- Queue Drain ---")
        print(f"[drain] Final occupancy: raw=N/A, feat=N/A, batch=N/A, scored=N/A")
        print(f"All queues empty: N/A")
        print(f"\n--- Sanity Checks ---")
        print(f"shuffled_null_regret: {null_fr:.4f}  (must be >> mean_feature_regret)")
        print(f"oracle_auroc:         {oracle_auroc:.4f}  (must be > 0.70 for results to be meaningful)")

        print(f"""
--- Burst-Stratified Staleness (THE KEY MECHANISM A RESULT) ---
burst_staleness_mean_sec:     {burst_metrics.get('burst_staleness', {}).get('mean', 'N/A')}
burst_staleness_p99_sec:      {burst_metrics.get('burst_staleness', {}).get('p99', 'N/A')}
calm_staleness_mean_sec:      {burst_metrics.get('calm_staleness', {}).get('mean', 'N/A')}
calm_staleness_p99_sec:       {burst_metrics.get('calm_staleness', {}).get('p99', 'N/A')}
per_user_burst_staleness_sec: {burst_metrics.get('per_user_burst_mean_staleness_sec', 'N/A')}
staleness_burst_calm_ratio:   {(burst_metrics.get('burst_staleness', {}).get('mean', 0) / max(1, burst_metrics.get('calm_staleness', {}).get('mean', 1))):.3f}

--- Feature Refresh Rate ---
burst_refreshes_per_user_per_hour: {refresh_metrics.get('burst', {}).get('refreshes_per_user_per_hour', 'N/A')}
calm_refreshes_per_user_per_hour:  {refresh_metrics.get('calm', {}).get('refreshes_per_user_per_hour', 'N/A')}
burst_to_calm_refresh_ratio:       {refresh_metrics.get('burst_to_calm_refresh_ratio', 'N/A')}
""")
        print(f"=== End Output Block ===\n")

    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_metrics).to_csv(args.out_csv, index=False)
    print(f"\n[compute_metrics] Summary → {args.out_csv}")


if __name__ == "__main__":
    main()
