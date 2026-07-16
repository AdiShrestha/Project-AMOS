# BPFeat — Context Summary for Future Agent Sessions

## Project State & Progress
This document captures the progress made on the BPFeat IEEE Conference Submission Hardening Pass. All major code bugs identified in the hardening phase have been resolved, and the pipeline has been successfully wired to run on real Taobao data.

### Solved Bugs & Fixes
1. **Label Alignment Bug (`preprocess_taobao.py`)**: Fixed a critical pandas index alignment bug where assigning labels via numpy arrays misaligned the generated labels across users. The fix explicitly converts labels to a `pd.Series` aligned to the target dataframe's indices.
2. **Oracle Signal Verified**: After the label fix, the pipeline processes 980K events from 10K users, producing a healthy positive label rate of `11.95%` and a true Oracle AUROC of `0.6555`. We decided to proceed with this 0.6555 AUROC instead of adding new features (like rolling-24h-buy-count) to preserve the paper's original framing (evaluating a simple 7-feature logistic regression).
3. **Synthetic Generator (`generate_synthetic.py`)**: Fixed the random burst generator to reliably produce a calm-burst-calm pattern (bursting specifically in the middle third of the timeline) to successfully trigger both "grow" and "shrink" window size adaptations (`direction_changes > 0`).
4. **Pipeline Stability (`compute_metrics.py`)**: Added missing `roc_auc_score` imports and fixed column name mismatches (`score_oracle`).
5. **Trace Overwrite Bug (`harness.cpp`)**: Discovered that the harness was overwriting the full time-series trace logs (e.g., `trace_adaptive_seed0.csv`) with a one-line summary at the end of the run. This prevented `zdomain_feature_analysis.py` from finding the `alpha` series. The `harness.cpp` was patched via `sed` to output the summary to a different prefix (`harness_summary_`) and recompiled.

### Current Blocker / Known Issue
- **Out of Memory / CPU Lockup in `compute_metrics.py`**: A full experiment run (7 architectures × 5 seeds = 35 runs) generates over 34.3 million events. The Python evaluation script performs a Moving Block Bootstrap (MBB) for confidence intervals with `num_bootstrap=1000`. Running 1,000 resamples over arrays containing millions of elements caused a massive CPU and RAM explosion that crashed the local MacBook. 

### Next Steps for the New Agent
When resuming the project, the new agent should:
1. **Reduce Bootstrap Iterations**: Edit `analysis/compute_metrics.py` to lower `NUM_BOOTSTRAP` from `1000` to a safer number like `50` or `100` for local execution (or help the user run it on a high-RAM cloud instance).
2. **Re-Run the Harness**: Execute the C++ harness on the Taobao dataset. (The compiled binary is already fixed to not overwrite the trace data).
   ```bash
   ./build/feature_flow/feature_flow_harness --replay data/replay/replay_taobao_10k.csv --seeds 5 --out-dir results/raw/
   ```
3. **Compute Metrics**: Run the updated `compute_metrics.py` and output the required Section 15 diagnostic blocks.
   ```bash
   python3 analysis/compute_metrics.py --raw-dir results/raw/ --oracle-csv data/replay/oracle_scores.csv
   ```
4. **Generate Z-Domain Figure**: Run the z-domain feature analysis to produce the `passband_narrowing.png` heatmap required for the paper using the preserved trace.
   ```bash
   python3 analysis/zdomain_feature_analysis.py --trace results/raw/trace_adaptive_seed0.csv --out-heatmap results/figures/passband_narrowing.png
   ```

## MIRACLE UPDATE: The Output Successfully Finished!
Even though your local UI crashed, the background terminal process actually survived and successfully finished computing the bootstrap after ~15 minutes! The outputs perfectly validate the paper's claims. 

### Key Findings from the Log:
* **Adaptive Controller works:** `direction_changes: 7.8` (It successfully shrinks and grows!)
* **Fairness Claim validated:** `adaptive` achieves a Jain Fairness Index of **0.2130** — which is *double* `bonly` (0.1153) and `aonly` (0.0893).
* **Regret Claim validated:** `adaptive` maintains near-zero feature regret (`-0.00147`), vastly outperforming `aonly` (`-0.09959`) and `throttle` (`-0.01833`).

I have saved the raw output blocks to `results_block_final.txt` so the new agent has access to the exact numbers for Section 15 of the paper!
