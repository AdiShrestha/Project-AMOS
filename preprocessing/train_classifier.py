"""
train_classifier.py — Offline logistic regression training on oracle features (Section 20).

Oracle features: computed at alpha=alpha_max (most reactive, no smoothing-induced
staleness) and W=1 (every event published immediately). The same fitted weights are
reused across ALL four pipeline architectures; only what the model is scored against
differs at runtime.

Usage:
    python train_classifier.py \\
        --replay data/replay/replay_taobao_10k.csv \\
        --out models/classifier_weights.txt \\
        [--alpha-max 0.30] [--test-size 0.2] [--seed 42]

Output file format expected by LogisticModel::load() (Section 17):
    bias=<float>
    w0=<float>
    w1=<float>
    w2=<float>
    w3=<float>
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Must match engagement.hpp exactly (Decision 5 / Section 13.2)
ENGAGEMENT_WEIGHT = {0: 1.0, 1: 3.0, 2: 2.0, 3: 5.0}


def compute_oracle_features(df: pd.DataFrame, alpha_max: float) -> pd.DataFrame:
    """
    Replicate KeyedFeatureExtractOp's feature computation in pandas,
    with alpha fixed at alpha_max and W=1 (every event is a snapshot).
    Must match the C++ EMAUserState::update() + export_features() logic exactly.
    """
    df = df.sort_values(["user_id", "timestamp_ns"], kind="mergesort").reset_index(drop=True)
    out_rows = []
    for uid, g in df.groupby("user_id", sort=False):
        ema    = 0.0
        pv     = 0
        cart_fav = 0
        raw_buy = 0
        ema_recency = 0.0
        prev_ts_sec = 0.0
        for _, row in g.iterrows():
            bc     = int(row.get("behavior_code", 0))
            weight = ENGAGEMENT_WEIGHT.get(bc, 1.0)
            ema    = alpha_max * weight + (1.0 - alpha_max) * ema
            if bc == 0: pv += 1
            elif bc in (1, 2): cart_fav += 1
            elif bc == 3: raw_buy += 1
            
            ts_sec = row["timestamp_ns"] / 1e9
            recency = 0.0 if prev_ts_sec == 0.0 else min(ts_sec - prev_ts_sec, 3600.0) / 3600.0
            
            gap = 0.0 if prev_ts_sec == 0.0 else ts_sec - prev_ts_sec
            ema_recency = alpha_max * gap + (1.0 - alpha_max) * ema_recency
            
            prev_ts_sec = ts_sec
            
            total_events = pv + cart_fav + raw_buy
            buy_rate_ratio = raw_buy / max(1, total_events)
            
            out_rows.append({
                "seq":            row["seq"],
                "user_id":        uid,
                "ema_engagement": ema,
                "log_pv":         np.log1p(pv),
                "log_cart_fav":   np.log1p(cart_fav),
                "recency":        recency,
                "buy_rate_ratio": buy_rate_ratio,
                "log_buy":        np.log1p(raw_buy),
                "ema_recency":    ema_recency,
                "label":          int(row["label"]),
                "label_valid":    int(row["label_valid"]),
            })
    return pd.DataFrame(out_rows)

def compute_oracle_features_ulb(df: pd.DataFrame, alpha_max: float) -> tuple[pd.DataFrame, float]:
    """
    ULB features: transaction Amount drives ema_engagement (NOT behavior_code).
    behavior_code is always 0 in ULB — it carries no information.
    We normalize ema_engagement by max_amount so C++ inference at runtime
    (which divides raw.amount / ulb_max_amount) uses the same scale.
    Returns (feats_df, max_amount)
    """
    df = df.sort_values(["user_id", "timestamp_ns"], kind="mergesort").reset_index(drop=True)
    # Use the 'amount' column (0-25691 range), NOT behavior_code (always 0)
    max_amount = float(df["amount"].max())
    if max_amount <= 0:
        max_amount = 1.0

    out_rows = []
    for uid, g in df.groupby("user_id", sort=False):
        ema    = 0.0
        pv     = 0
        cart_fav = 0
        raw_buy = 0
        ema_recency = 0.0
        prev_ts_sec = 0.0
        for _, row in g.iterrows():
            amt = float(row.get("amount", 0.0))   # ← use 'amount', not 'behavior_code'
            ema    = alpha_max * (amt / max_amount) + (1.0 - alpha_max) * ema

            if amt > 0: raw_buy += 1
            else: pv += 1

            ts_sec = row["timestamp_ns"] / 1e9
            recency = 0.0 if prev_ts_sec == 0.0 else min(ts_sec - prev_ts_sec, 3600.0) / 3600.0
            gap = 0.0 if prev_ts_sec == 0.0 else ts_sec - prev_ts_sec
            ema_recency = alpha_max * gap + (1.0 - alpha_max) * ema_recency
            prev_ts_sec = ts_sec

            total_events = pv + cart_fav + raw_buy
            buy_rate_ratio = raw_buy / max(1, total_events)

            out_rows.append({
                "seq":            row["seq"],
                "user_id":        uid,
                "ema_engagement": ema,           # already normalized (amt/max_amount)
                "log_pv":         np.log1p(pv),
                "log_cart_fav":   np.log1p(cart_fav),
                "recency":        recency,
                "buy_rate_ratio": buy_rate_ratio,
                "log_buy":        np.log1p(raw_buy),
                "ema_recency":    ema_recency,
                "label":          int(row["label"]),
                "label_valid":    int(row["label_valid"]),
            })
    return pd.DataFrame(out_rows), float(max_amount)

def find_best_oracle_alpha(df, is_ulb=False, alphas=[0.02, 0.05, 0.10, 0.15, 0.20, 0.30]):
    """Find the alpha that maximizes oracle AUROC on a held-out validation split."""
    best_alpha, best_auroc = None, 0.0
    print("[train_classifier] Grid searching for best oracle alpha...")
    for alpha in alphas:
        if is_ulb:
            feats, _ = compute_oracle_features_ulb(df, alpha)
        else:
            feats = compute_oracle_features(df, alpha)
            
        feats_valid = feats[feats['label_valid'] == 1]
        
        feature_cols = ["ema_engagement", "log_pv", "log_cart_fav", "recency", 
                        "buy_rate_ratio", "log_buy", "ema_recency"]
        X = feats_valid[feature_cols].to_numpy(dtype=np.float64)
        y = feats_valid['label'].to_numpy(dtype=np.int32)
        
        X_tr, X_val, y_tr, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y)
            
        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr)
        X_val_s = scaler.transform(X_val)
        
        clf = LogisticRegression(class_weight='balanced', max_iter=2000, solver="lbfgs")
        clf.fit(X_tr_s, y_tr)
        auroc = roc_auc_score(y_val, clf.predict_proba(X_val_s)[:,1])
        print(f"  alpha={alpha:.2f} -> val AUROC={auroc:.4f}")
        
        if auroc > best_auroc:
            best_auroc, best_alpha = auroc, alpha
            
    print(f"Best oracle alpha: {best_alpha} (AUROC={best_auroc:.4f})")
    return best_alpha

def main():
    ap = argparse.ArgumentParser(description="Train oracle logistic regression for BPFeat")
    ap.add_argument("--replay",    required=True, help="Replay CSV (from preprocess_taobao.py)")
    ap.add_argument("--out",       required=True, help="Output weights .txt file")
    ap.add_argument("--alpha-max", type=float, default=0.30,
                    help="Oracle α (most reactive, no smoothing lag). Default: 0.30")
    ap.add_argument("--test-size", type=float, default=0.20)
    ap.add_argument("--seed",      type=int,   default=42)
    ap.add_argument("--grid-search-alpha", action="store_true", help="Perform grid search for best alpha")
    args = ap.parse_args()

    print(f"[train_classifier] Loading {args.replay} ...")
    raw = pd.read_csv(args.replay)
    print(f"[train_classifier] {len(raw):,} rows, {raw['user_id'].nunique():,} users")

    is_ulb = "ulb" in args.replay.lower()
    if args.grid_search_alpha:
        best_alpha = find_best_oracle_alpha(raw, is_ulb=is_ulb)
        args.alpha_max = best_alpha

    print(f"[train_classifier] Computing oracle features (alpha_max={args.alpha_max}) ...")
    max_amount = 1.0
    if is_ulb:
        feats, max_amount = compute_oracle_features_ulb(raw, args.alpha_max)
    else:
        feats = compute_oracle_features(raw, args.alpha_max)

    labeled_feats = feats[feats["label_valid"] == 1].copy()
    print(f"[train_classifier] {len(labeled_feats):,} labeled rows, "
          f"positive rate: {labeled_feats['label'].mean():.4f}")

    feature_cols = ["ema_engagement", "log_pv", "log_cart_fav", "recency", 
                    "buy_rate_ratio", "log_buy", "ema_recency"]
    X_labeled = labeled_feats[feature_cols].to_numpy(dtype=np.float64)
    y_labeled = labeled_feats["label"].to_numpy(dtype=np.int32)

    X_train, X_test, y_train, y_test = train_test_split(
        X_labeled, y_labeled, test_size=args.test_size, random_state=args.seed, stratify=y_labeled)

    # Scale features (stored scaler NOT saved — oracle features are also scaled
    # at runtime by the same mean/std fitted here; we bake the scaling into the
    # weight vector below so the C++ model sees unscaled features).
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    clf = LogisticRegression(class_weight="balanced", max_iter=2000,
                              random_state=args.seed, solver="lbfgs")
    clf.fit(X_train_s, y_train)

    # Evaluate
    p_test = clf.predict_proba(X_test_s)[:, 1]
    auprc  = average_precision_score(y_test, p_test)
    auroc  = roc_auc_score(y_test, p_test)
    print(f"[train_classifier] Oracle AUPRC: {auprc:.4f}  AUROC: {auroc:.4f}")
    print("  (Report these numbers in Section 6/20 of the paper before any regret figures)")

    # Compute oracle scores for all events and save
    print("[train_classifier] Computing oracle scores for all events...")
    X_all = feats[feature_cols].to_numpy(dtype=np.float64)
    X_all_s = scaler.transform(X_all)
    p_all = clf.predict_proba(X_all_s)[:, 1]
    
    # Bug 1 fixes:
    # 1. Output all rows, not just label_valid=1
    # 2. Output seq, user_id, score_oracle, label, label_valid
    oracle_df = pd.DataFrame({
        "seq": feats["seq"].astype(int),
        "user_id": feats["user_id"].astype(int),
        "score_oracle": p_all,
        "label": feats["label"].astype(int),
        "label_valid": feats["label_valid"].astype(int)
    })
    
    print("DEBUG oracle sample:")
    print(oracle_df[['seq','user_id','score_oracle','label','label_valid']].head(10))
    
    # Place oracle_scores.csv in the same directory as replay.csv
    replay_stem = Path(args.replay).stem.replace("replay_", "")
    out_name = f"oracle_scores_{replay_stem}.csv" if "ulb" in replay_stem else "oracle_scores.csv"
    oracle_out_path = Path(args.replay).parent / out_name
    oracle_df.to_csv(oracle_out_path, index=False)
    print(f"[train_classifier] Oracle scores written → {oracle_out_path}")

    # Fold the scaler into the weight vector so LogisticModel::score() in C++
    # receives raw (unscaled) features and still produces correct logits.
    # transformed_x = (x - mean) / std
    # z = w_scaled · transformed_x + bias = (w_scaled/std) · x - (w_scaled·mean/std) + bias
    w_scaled = clf.coef_[0]          # shape (kDim,)
    mean_     = scaler.mean_
    std_      = scaler.scale_

    w_raw  = w_scaled / std_
    bias_  = clf.intercept_[0] - np.dot(w_scaled, mean_ / std_)

    # Write weights
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        f.write(f"bias={bias_:.10f}\n")
        for i, w in enumerate(w_raw):
            f.write(f"w{i}={w:.10f}\n")
    print(f"[train_classifier] Weights written → {args.out}")
    
    if is_ulb:
        norm_path = out_path.with_suffix(".norm")
        with open(norm_path, "w") as f:
            f.write(f"max_amount={max_amount:.6f}\n")
        print(f"[train_classifier] ULB Normalization written → {norm_path}")


if __name__ == "__main__":
    main()
