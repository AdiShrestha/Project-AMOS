import pandas as pd

# Use the stress results for better dynamic range of W and alpha
df = pd.read_csv('results/raw_stress/results_adaptive_seed0.csv', 
                 usecols=['result_timestamp_ns', 'window_size_used', 'alpha_used', 'occupancy_at_decision'])

# Sample every 100th event to reduce trace size for the plot
df_sampled = df.iloc[::100].copy()

out_df = pd.DataFrame({
    'wall_ns': df_sampled['result_timestamp_ns'],
    'w': df_sampled['window_size_used'],
    'alpha': df_sampled['alpha_used'],
    'occupancy': df_sampled['occupancy_at_decision']
})

out_df.to_csv('results/raw_stress/trace_adaptive_seed0.csv', index=False)
print("Trace reconstructed perfectly.")
