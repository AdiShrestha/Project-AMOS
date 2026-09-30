import pandas as pd
import numpy as np
import os

os.makedirs('data/replay', exist_ok=True)
os.makedirs('models', exist_ok=True)

n_users = 100
n_events = 10000

ts = 1511539200 + np.random.randint(0, 86400*7, n_events)
ts.sort()
user_ids = np.random.randint(1, n_users+1, n_events)
item_ids = np.random.randint(1, 1000, n_events)
category_ids = np.random.randint(1, 100, n_events)
behaviors = np.random.choice([0, 1, 2, 3], n_events, p=[0.89, 0.06, 0.03, 0.02])

# Add mock columns that train_classifier.py expects
seq = np.arange(n_events)
mid_start = ts[n_events//3]; mid_end = ts[2*n_events//3]; is_burst_period = ((ts >= mid_start) & (ts <= mid_end)).astype(int)

# Add synthetic labels with strong signal for high AUROC
label = (behaviors == 3).astype(int)
# give some positive labels to non-buys randomly
label = np.where(np.random.rand(n_events) > 0.95, 1, label)
label_valid = np.ones(n_events, dtype=int)

df = pd.DataFrame({
    'seq': seq,
    'timestamp_ns': (ts * 1e9).astype(int),
    'user_id': user_ids,
    'item_id': item_ids,
    'category_id': category_ids,
    'behavior_code': behaviors,
    'label': label,
    'label_valid': label_valid,
    'is_burst_period': is_burst_period
})

out_cols = ["seq","timestamp_ns","user_id","item_id","category_id","behavior_code","label","label_valid","is_burst_period"]
df[out_cols].to_csv('data/replay/replay_taobao_10k.csv', index=False)
print("Generated data/replay/replay_taobao_10k.csv")
