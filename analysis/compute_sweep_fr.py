import argparse
import pandas as pd
import numpy as np
from pathlib import Path

def bce(p: np.ndarray, y: np.ndarray, eps: float = 1e-7) -> np.ndarray:
    p = np.clip(p, eps, 1.0 - eps)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--oracle", required=True)
    args = ap.parse_args()

    results_df = pd.read_csv(args.results)
    oracle_df = pd.read_csv(args.oracle)

    merged = results_df.merge(oracle_df[["seq","score_oracle"]], on="seq", how="inner")
    valid  = merged[merged["label_valid"] == 1].copy()
    
    if len(valid) == 0:
        print("FR: NaN (no valid labels)")
        return

    label = valid["label"].to_numpy(dtype=np.float64)
    online_score  = valid["score"].to_numpy(dtype=np.float64)
    oracle_score_ = valid["score_oracle"].to_numpy(dtype=np.float64)

    fr_per_sample = bce(online_score, label) - bce(oracle_score_, label)
    fr_mean = float(fr_per_sample.mean())
    print(f"FR: {fr_mean:.5f}")

if __name__ == "__main__":
    main()
