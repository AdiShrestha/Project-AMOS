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
        prev_ts_sec = 0.0
        for _, row in g.iterrows():
            bc     = int(row.get("behavior_code", 0))
            weight = ENGAGEMENT_WEIGHT.get(bc, 1.0)
            ema    = alpha_max * weight + (1.0 - alpha_max) * ema
            if bc == 0: pv += 1
            elif bc in (1, 2): cart_fav += 1
            ts_sec = row["timestamp_ns"] / 1e9
            recency = 0.0 if prev_ts_sec == 0.0 else min(ts_sec - prev_ts_sec, 3600.0) / 3600.0
            prev_ts_sec = ts_sec
            out_rows.append({
                "seq":            row["seq"],
                "user_id":        uid,
                "ema_engagement": ema,
                "log_pv":         np.log1p(pv),
                "log_cart_fav":   np.log1p(cart_fav),
                "recency":        recency,
                "label":          int(row["label"]),
                "label_valid":    int(row["label_valid"]),
            })
    return pd.DataFrame(out_rows)


def main():
    ap = argparse.ArgumentParser(description="Train oracle logistic regression for BPFeat")
    ap.add_argument("--replay",    required=True, help="Replay CSV (from preprocess_taobao.py)")
    ap.add_argument("--out",       required=True, help="Output weights .txt file")
    ap.add_argument("--alpha-max", type=float, default=0.30,
                    help="Oracle α (most reactive, no smoothing lag). Default: 0.30")
    ap.add_argument("--test-size", type=float, default=0.20)
    ap.add_argument("--seed",      type=int,   default=42)
    args = ap.parse_args()

    print(f"[train_classifier] Loading {args.replay} ...")
    raw = pd.read_csv(args.replay)
    print(f"[train_classifier] {len(raw):,} rows, {raw['user_id'].nunique():,} users")

    print(f"[train_classifier] Computing oracle features (alpha_max={args.alpha_max}) ...")
    feats = compute_oracle_features(raw, args.alpha_max)

    # Only train on rows with valid labels
    feats = feats[feats["label_valid"] == 1].copy()
    print(f"[train_classifier] {len(feats):,} labeled rows, "
          f"positive rate: {feats['label'].mean():.4f}")

    feature_cols = ["ema_engagement", "log_pv", "log_cart_fav", "recency"]
    X = feats[feature_cols].to_numpy(dtype=np.float64)
    y = feats["label"].to_numpy(dtype=np.int32)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=args.seed, stratify=y)

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


if __name__ == "__main__":
    main()
