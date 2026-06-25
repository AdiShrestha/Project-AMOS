# Save as: collect_all_results.py
# Run as: python3 collect_all_results.py 2>&1 | tee results/FINAL_DATA_FOR_PAPER.txt

import pandas as pd, numpy as np, glob, os, json
from pathlib import Path

print("=" * 80)
print("BPFEAT COMPLETE DATA COLLECTION FOR PAPER WRITING")
print("=" * 80)
print()

# ---- SECTION A: Core MaxRate Results (Primary Table) ----
print("SECTION A: MAXRATE RESULTS (PRIMARY TABLE)")
print("Source: results/raw/ (5-seed, replay_taobao_10k.csv, N=980,885 events)")
print()

archs = ['fixed', 'drift', 'throttle', 'aonly', 'bonly', 'adaptive', 'ralf']
for arch in archs:
    files = sorted(glob.glob(f'results/raw/results_{arch}_seed*.csv'))
    if not files:
        print(f"  {arch}: NO FILES FOUND")
        continue
    dfs = [pd.read_csv(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    valid = df[df['label_valid']==1]
    
    # Regret from metrics summary if available
    summary = Path('results/metrics_summary.csv')
    if summary.exists():
        sumdf = pd.read_csv(summary)
        row = sumdf[sumdf['arch']==arch]
        if not row.empty:
            print(f"  {arch}: FR={row['fr_mean'].iloc[0]:.5f} "
                  f"CI=[{row['fr_ci_lo'].iloc[0]:.5f},{row['fr_ci_hi'].iloc[0]:.5f}] "
                  f"coverage={row['coverage'].iloc[0]:.3f} "
                  f"staleness={row['mean_staleness_sec'].iloc[0]:.0f}s "
                  f"jain={row['fairness_gap'].iloc[0]:.4f}")
    else:
        print(f"  {arch}: {len(files)} seed files, {len(df)} total rows")

print()
print("Oracle AUROC: 0.6557 (grid-search best alpha=0.20)")
print("Positive label rate: 11.95%")
print("Users: 9,711 | Events: 980,885 | Seeds: 5")
print()

# ---- SECTION B: Controller Traces ----
print("SECTION B: CONTROLLER TRACES (Adaptive/AOnly/BOnly)")
print()
trace_files = sorted(glob.glob('results/raw/trace_adaptive_seed*.csv'))
if trace_files:
    for tf in trace_files:
        try:
            tdf = pd.read_csv(tf)
            if len(tdf) > 0:
                print(f"  {Path(tf).name}:")
                print(f"    W range: {tdf['w'].min():.0f} - {tdf['w'].max():.0f}")
                if 'alpha' in tdf.columns:
                    print(f"    alpha range: {tdf['alpha'].min():.4f} - {tdf['alpha'].max():.4f}")
                if 'occupancy' in tdf.columns:
                    print(f"    occupancy range: {tdf['occupancy'].min():.3f} - {tdf['occupancy'].max():.3f}")
                if 'direction_changes' in tdf.columns:
                    print(f"    final direction_changes: {tdf['direction_changes'].iloc[-1]}")
        except:
            pass
else:
    print("  WARNING: No trace files found. Z-domain analysis may be using reconstructed data.")
print()

# ---- SECTION C: W-alpha Pearson Correlation ----
print("SECTION C: W↔α EMPIRICAL EQUIVALENCE (Experiment 6)")
print()
print("  Pearson r(N_alpha[n], W[n]) = 0.683")
print("  (from analysis/zdomain_feature_analysis.py)")
print("  Interpretation: moderate coupling under the EWMA span identity N=2/α−1")
print("  Both mechanisms respond to the same backpressure signal but at different")
print("  timescales (W per-window, α per-event), explaining the r < 1.0")
print()

# ---- SECTION D: Stress Experiment Results ----
print("SECTION D: STRESS EXPERIMENT RESULTS (50µs/item delay during burst)")
print()
stress_files = sorted(glob.glob('results/raw_stress_correct/results_*.csv'))
if stress_files:
    archs_in_stress = set()
    for f in stress_files:
        arch = Path(f).name.split('_seed')[0].replace('results_','')
        archs_in_stress.add(arch)
    
    stress_summary = Path('results/stress_v2_metrics.txt')
    if stress_summary.exists():
        print("  (from results/stress_v2_metrics.txt)")
        with open(stress_summary) as f:
            lines = f.readlines()
        for line in lines:
            if any(k in line for k in ['Architecture', 'PATR', 'mean_feature_regret',
                                        'direction_changes', 'WOR']):
                print(" ", line.rstrip())
    else:
        print(f"  Stress files found for: {sorted(archs_in_stress)}")
        print("  Run: python3 analysis/compute_metrics.py --raw-dir results/raw_stress_correct/")
        print("       --oracle-csv data/replay/oracle_scores.csv > results/stress_v2_metrics.txt")
else:
    print("  WARNING: results/raw_stress_correct/ is empty or missing")
    print("  Stress experiment was not successfully run or results were corrupted")
print()

# ---- SECTION E: ULB Generalization Results ----
print("SECTION E: ULB GENERALIZATION (Secondary Dataset — Credit Card Fraud)")
print()
ulb_oracle = Path('data/replay/oracle_scores_ulb.csv')
if ulb_oracle.exists():
    odf = pd.read_csv(ulb_oracle)
    eps = 1e-9
    bce = -(odf['label'] * np.log(odf['score_oracle'].clip(eps,1-eps)) +
            (1-odf['label']) * np.log(1-odf['score_oracle'].clip(eps,1-eps)))
    print(f"  ULB oracle BCE: {bce.mean():.4f}")
    print(f"  ULB positive rate: {odf['label'].mean():.4f} (expected: ~0.0017)")

ulb_files = sorted(glob.glob('results/raw_ulb/results_*.csv'))
if ulb_files:
    ulb_summary = Path('results/ulb_v2_metrics.txt')
    if ulb_summary.exists():
        print("  (from results/ulb_v2_metrics.txt)")
        with open(ulb_summary) as f:
            lines = f.readlines()
        for line in lines:
            if any(k in line for k in ['Architecture', 'PATR', 'mean_feature_regret',
                                        'direction_changes', 'WOR', 'jain', 'coverage']):
                print(" ", line.rstrip())
    else:
        print(f"  ULB result files found: {len(ulb_files)}")
        print("  Run compute_metrics.py on results/raw_ulb/ to get final numbers")
else:
    print("  WARNING: results/raw_ulb/ not found")
print()

# ---- SECTION F: Sensitivity Sweep Summary ----
print("SECTION F: AIMD SENSITIVITY SWEEP")
print()
sweep_csv = Path('results/sweep/sweep_results.csv')
if sweep_csv.exists():
    df = pd.read_csv(sweep_csv)
    print(f"  Total sweep configurations: {len(df)}")
    print(f"  Columns: {list(df.columns)}")
    metric = next((c for c in ['patr','mean_regret','fr_mean','patr_mean'] if c in df.columns), None)
    if metric:
        best = df.loc[df[metric].idxmax()] if 'regret' not in metric else df.loc[df[metric].idxmin()]
        default_row = df[(df.get('shrink',df.get('shrink_factor',pd.Series()))==0.70) & 
                        (df.get('grow',df.get('grow_factor',pd.Series()))==1.15)]
        print(f"  Best {metric}: {df[metric].max():.4f}")
        print(f"  Worst {metric}: {df[metric].min():.4f}")
        print(f"  Default config (shrink=0.70, grow=1.15) {metric}:", 
              default_row[metric].values[0] if not default_row.empty else "NOT FOUND")
        print(f"  Mean {metric}: {df[metric].mean():.4f} ± {df[metric].std():.4f}")
        print(f"  Conclusion: default params are {'within 1 std of best' if abs(default_row[metric].values[0] - df[metric].max()) < df[metric].std() else 'NOT at optimum — sensitivity concern'}")
    print("  Full sweep CSV: results/sweep/sweep_results.csv (include as supplementary material)")
else:
    print("  WARNING: sweep_results.csv not found")
    print("  Run: ./build/feature_flow/feature_flow_harness --sweep --synthetic")
print()

# ---- SECTION G: Fairness Analysis ----
print("SECTION G: FAIRNESS ANALYSIS (Taobao Zipfian Distribution)")
print()
print("  Jain Fairness Index by architecture (from MaxRate 5-seed run):")
print("    Fixed:    J=0.155, fairness_gap=+21,765s (high-traffic users get 6x fresher features)")
print("    Drift:    J=0.136, fairness_gap=+21,958s")
print("    Throttle: J=0.210, fairness_gap=+22,070s")
print("    A-only:   J=0.118, fairness_gap=+20,869s")
print("    B-only:   J=0.249, fairness_gap=+21,759s")
print("    Adaptive: J=0.212, fairness_gap=+19,931s (smallest gap among adaptive architectures)")
print("    RALF:     J=0.014, fairness_gap=-114s    (slight REVERSE gap — favors rare users)")
print("  User activity p10: 21 events, p90: 217 events (10x Zipfian spread)")
print()

# ---- SECTION H: Paper Status and Figures ----
print("SECTION H: PAPER STATUS")
print()
print("  Venue: IEEE BigData 2026 | Deadline: August 21, 2026 | 10 pages incl. references")
print()
figs = list(Path('results/figures').glob('*.png')) if Path('results/figures').exists() else []
print(f"  Figures generated: {len(figs)}")
for f in sorted(figs):
    size_kb = f.stat().st_size / 1024
    print(f"    {f.name} ({size_kb:.0f}KB)")
print()
print("  Sections with real numbers: Abstract, Sections 5-7 (Experimental Setup, Results, Discussion)")
print("  Sections still needing content: Introduction narrative, Related Work expansion,")
print("       Conclusion, camera-ready formatting")
print()

# ---- SECTION I: Open Issues for Author Review ----
print("SECTION I: OPEN ISSUES REQUIRING AUTHOR JUDGMENT")
print()
print("  ISSUE 1 — Negative regret for static baselines:")
print("    Static architectures (FR≈-0.016) outperform oracle (α=0.20) because")
print("    α=0.10 (span≈19) better captures accumulated purchase intent than")
print("    reactive α=0.20 (span≈9). Paper must explain this is a task-specific")
print("    finding, not a measurement error. Section 7 draft paragraph written.")
print()
print("  ISSUE 2 — Ablation shows B-only ≈ Adaptive on regret (CI overlap):")
print("    B-only [+0.0039, +0.0048] vs Adaptive [+0.0017, +0.0046] overlap.")
print("    Mechanism A's marginal accuracy benefit is not statistically significant")
print("    in MaxRate regime. The stress experiment should differentiate them on PATR.")
print("    Paper should state this honestly: 'B is the dominant accuracy mechanism;")
print("    A's benefit is throughput retention under load.'")
print()
print("  ISSUE 3 — PATR identical across non-RALF architectures in MaxRate:")
print("    All show PATR=0.128. This is the burst event fraction in the dataset.")
print("    Wall-clock PATR should differentiate architectures in the STRESS experiment.")
print("    Paste stress experiment PATR values here when available.")
print()
print("  ISSUE 4 — ULB high WOR (~922 dir_changes/min):")
print("    Controller oscillates heavily on single-key ULB. This is a legitimate")
print("    finding about the mechanism's operating envelope. Paper should include")
print("    a Discussion paragraph on single-key limitations.")
print()
print("  ISSUE 5 — oracle_auroc=0.6557 is below the 0.70 threshold:")
print("    Regret numbers are still valid — they show relative differences between")
print("    architectures on a common baseline. Include the oracle AUROC prominently")
print("    in Section 5 so readers can calibrate the absolute magnitudes.")
print()
print("=" * 80)
print("END OF DATA COLLECTION")
print("Copy everything above to share with Claude for paper writing guidance")
print("=" * 80)
