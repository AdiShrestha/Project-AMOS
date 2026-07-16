import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

try:
    df = pd.read_csv('results/sweep/sweep_results.csv')
    print('Sweep CSV shape:', df.shape)
    print('Sweep CSV columns:', list(df.columns))
    print('Sweep CSV head:')
    print(df.head(5).to_string())
    
    # Pivot on shrink_factor vs grow_factor, take PATR or FR as metric
    # Use whatever metric columns exist
    metric_col = next((c for c in ['patr', 'mean_regret', 'fr_mean', 'direction_changes'] if c in df.columns), None)
    if metric_col is None:
        print('ERROR: no metric column found in sweep CSV. Columns are:', list(df.columns))
    else:
        pivot_cols = [c for c in ['shrink', 'grow', 'occ_low', 'occ_high'] if c in df.columns]
        if len(pivot_cols) >= 2:
            # Plot shrink vs grow heatmap, fixing occ_low and occ_high at default
            if 'occ_low' in df.columns:
                sub = df[(df['occ_low']==0.30) & (df['occ_high']==0.70)]
            else:
                sub = df
            pivot = sub.pivot_table(index='shrink', columns='grow', values=metric_col)
            fig, ax = plt.subplots(figsize=(7, 5))
            im = ax.imshow(pivot.values, aspect='auto', cmap='RdYlGn')
            ax.set_xticks(range(len(pivot.columns)))
            ax.set_xticklabels([f'{v:.2f}' for v in pivot.columns])
            ax.set_yticks(range(len(pivot.index)))
            ax.set_yticklabels([f'{v:.2f}' for v in pivot.index])
            ax.set_xlabel('grow_factor')
            ax.set_ylabel('shrink_factor')
            ax.set_title(f'AIMD Sensitivity: {metric_col}\n(occ_low=0.30, occ_high=0.70)')
            plt.colorbar(im, ax=ax, label=metric_col)
            # Mark the default parameter
            default_shrink_idx = list(pivot.index).index(0.70) if 0.70 in list(pivot.index) else None
            default_grow_idx = list(pivot.columns).index(1.15) if 1.15 in list(pivot.columns) else None
            if default_shrink_idx is not None and default_grow_idx is not None:
                ax.plot(default_grow_idx, default_shrink_idx, 'r*', markersize=15, label='Default (0.70, 1.15)')
                ax.legend()
            fig.tight_layout()
            fig.savefig('results/figures/fig_sensitivity_sweep.png', dpi=150)
            print('Saved results/figures/fig_sensitivity_sweep.png')
        else:
            print('Not enough pivot columns found:', pivot_cols)
except FileNotFoundError:
    print('ERROR: results/sweep/sweep_results.csv not found')
    print('Run: ./build/feature_flow/feature_flow_harness --sweep --synthetic --out-dir results/sweep/')
