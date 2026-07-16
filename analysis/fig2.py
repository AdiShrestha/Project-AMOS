import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

data = {
    'fixed':    {'fr': -0.01596, 'lo': -0.01640, 'hi': -0.01561, 'color': '#4C72B0'},
    'drift':    {'fr': -0.01596, 'lo': -0.01640, 'hi': -0.01561, 'color': '#55A868'},
    'throttle': {'fr': -0.01596, 'lo': -0.01640, 'hi': -0.01561, 'color': '#C44E52'},
    'a-only':   {'fr': -0.10311, 'lo': -0.10471, 'hi': -0.10135, 'color': '#8172B2'},
    'b-only':   {'fr':  0.00442, 'lo':  0.00391, 'hi':  0.00479, 'color': '#CCB974'},
    'adaptive': {'fr':  0.00358, 'lo':  0.00255, 'hi':  0.00455, 'color': '#64B5CD'},
    'ralf':     {'fr':  0.03088, 'lo':  0.02444, 'hi':  0.03756, 'color': '#FF7F0E'},
}

archs = list(data.keys())
frs = [data[a]['fr'] for a in archs]
errs_lo = [data[a]['fr'] - data[a]['lo'] for a in archs]
errs_hi = [data[a]['hi'] - data[a]['fr'] for a in archs]
colors = [data[a]['color'] for a in archs]

fig, ax = plt.subplots(figsize=(10, 5))
bars = ax.bar(archs, frs, color=colors, alpha=0.85, edgecolor='black', linewidth=0.5)
ax.errorbar(archs, frs, yerr=[errs_lo, errs_hi], fmt='none', color='black', capsize=5, linewidth=1.5)

ax.axhline(0, color='black', linewidth=0.8, linestyle='--', alpha=0.5)
ax.set_xlabel('Architecture', fontsize=12)
ax.set_ylabel('Feature Regret (BCE gap vs oracle)', fontsize=12)
ax.set_title('Feature Regret by Architecture — Taobao UserBehavior (MaxRate)\n'
             'MBB 95% CI, 5 seeds, N=980K events, oracle AUROC=0.6557', fontsize=11)
ax.tick_params(axis='x', rotation=30)

# Annotate the key comparison
ax.annotate('BPFeat (Adaptive)\nFR=+0.0036', xy=(5, 0.00358),
            xytext=(5.3, 0.015), fontsize=9,
            arrowprops=dict(arrowstyle='->', color='black'))
ax.annotate('RALF\nFR=+0.031\ncoverage=50%', xy=(6, 0.03088),
            xytext=(5.5, 0.028), fontsize=9,
            arrowprops=dict(arrowstyle='->', color='black'))

fig.tight_layout()
fig.savefig('results/figures/fig_feature_regret_comparison.png', dpi=150)
print('Saved results/figures/fig_feature_regret_comparison.png')
