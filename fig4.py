import pandas as pd, glob
import matplotlib.pyplot as plt
import numpy as np

archs_to_plot = ['fixed', 'bonly', 'adaptive', 'ralf']
colors = {'fixed': '#4C72B0', 'bonly': '#CCB974', 'adaptive': '#64B5CD', 'ralf': '#FF7F0E'}
labels = {'fixed': 'Fixed', 'bonly': 'B-only', 'adaptive': 'Adaptive (BPFeat)', 'ralf': 'RALF'}

fig, ax = plt.subplots(figsize=(9, 5))
x = np.arange(4)  # 4 quartiles
width = 0.2

for i, arch in enumerate(archs_to_plot):
    files = sorted(glob.glob(f'results/raw/results_{arch}_seed*.csv'))
    if not files:
        print(f'WARNING: no files for {arch}')
        continue
    
    # Aggregate across seeds
    all_dfs = [pd.read_csv(f) for f in files]
    df = pd.concat(all_dfs, ignore_index=True)
    
    if 'user_id' not in df.columns or 'staleness_sec' not in df.columns:
        print(f'WARNING: missing columns for {arch}')
        continue
    
    user_staleness = df.groupby('user_id')['staleness_sec'].mean()
    user_event_count = df.groupby('user_id').size()
    
    # Compute quartile mean staleness
    try:
        q_labels = pd.qcut(user_event_count, q=4, labels=False, duplicates='drop')
        quartile_means = []
        for q in range(4):
            users_in_q = user_event_count[q_labels == q].index
            if len(users_in_q) > 0:
                quartile_means.append(user_staleness[users_in_q].mean() / 3600)  # hours
            else:
                quartile_means.append(0)
        ax.bar(x + i*width, quartile_means, width, label=labels[arch],
               color=colors[arch], alpha=0.85, edgecolor='black', linewidth=0.5)
    except Exception as e:
        print(f'WARNING: quartile computation failed for {arch}: {e}')

ax.set_xlabel('User Activity Quartile (Q1=least active, Q4=most active)')
ax.set_ylabel('Mean Feature Staleness (hours)')
ax.set_title('Feature Staleness Fairness by User Activity Quartile\nTaobao UserBehavior, 5 seeds')
ax.set_xticks(x + width * 1.5)
ax.set_xticklabels(['Q1\n(sparse)', 'Q2', 'Q3', 'Q4\n(power users)'])
ax.legend()
fig.tight_layout()
fig.savefig('results/figures/fig_staleness_fairness.png', dpi=150)
print('Saved results/figures/fig_staleness_fairness.png')
