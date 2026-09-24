"""Generate heatmap and consistency plots from sweep results."""
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

csv_dir = Path('results/csv')
plots_dir = Path('results/plots')
plots_dir.mkdir(parents=True, exist_ok=True)

# Load Archer-only sweep
all_df = pd.read_csv('results/all_tickers_1d_archer.csv')

print('Generating per-ticker heatmaps...')
for tk, df_tk in all_df.groupby('ticker'):
    best_combo = df_tk.loc[df_tk['sharpe'].idxmax()]
    ema = best_combo['ema_pair']
    ba = best_combo['bear_alloc_1d']

    df_2d = df_tk[(df_tk['ema_pair'] == ema) & (df_tk['bear_alloc_1d'] == ba)]
    pivot = df_2d.pivot(index='n_mu', columns='x', values='sharpe')

    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(pivot.values, aspect='auto', cmap='RdYlGn', origin='lower')
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f'{c:.2f}' for c in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel('x (prob of zero delay)')
    ax.set_ylabel('n_mu (mean delay candles)')
    ax.set_title(f'{tk} 1d -- Sharpe heatmap\nEMA {ema}, bear_alloc={ba}')
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f'{v:.2f}', ha='center', va='center', fontsize=8,
                        color='white' if v < pivot.values.mean() else 'black')
    plt.colorbar(im, ax=ax, label='Sharpe')
    plt.tight_layout()
    out = plots_dir / f'heatmap_{tk}_1d.png'
    plt.savefig(out, dpi=130)
    plt.close()
    print(f'  {out}')

print('\nGenerating global cross-ticker heatmap...')
median_per_combo = all_df.groupby(['n_mu', 'x', 'ema_pair', 'bear_alloc_1d'])['sharpe'].median().reset_index()
best_global = median_per_combo.loc[median_per_combo['sharpe'].idxmax()]
ema = best_global['ema_pair']
ba = best_global['bear_alloc_1d']
df_2d = median_per_combo[(median_per_combo['ema_pair'] == ema) & (median_per_combo['bear_alloc_1d'] == ba)]
pivot = df_2d.pivot(index='n_mu', columns='x', values='sharpe')

fig, ax = plt.subplots(figsize=(7, 5))
im = ax.imshow(pivot.values, aspect='auto', cmap='RdYlGn', origin='lower')
ax.set_xticks(range(len(pivot.columns)))
ax.set_xticklabels([f'{c:.2f}' for c in pivot.columns])
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels(pivot.index)
ax.set_xlabel('x (prob of zero delay)')
ax.set_ylabel('n_mu (mean delay candles)')
ax.set_title(f'Cross-ticker median Sharpe -- 9 tickers, 1d\nEMA {ema}, bear_alloc={ba}')
for i in range(pivot.shape[0]):
    for j in range(pivot.shape[1]):
        v = pivot.values[i, j]
        if not np.isnan(v):
            ax.text(j, i, f'{v:.2f}', ha='center', va='center', fontsize=8,
                    color='white' if v < pivot.values.mean() else 'black')
plt.colorbar(im, ax=ax, label='Median Sharpe')
plt.tight_layout()
out = plots_dir / 'heatmap_cross_ticker_median.png'
plt.savefig(out, dpi=130)
plt.close()
print(f'  {out}')

print('\nGenerating cross-ticker consistency plot...')
count_strong = all_df[all_df['sharpe'] > 0.7].groupby(['n_mu', 'x']).size().reset_index(name='n_tickers')
pivot_count = count_strong.pivot(index='n_mu', columns='x', values='n_tickers').fillna(0)

fig, ax = plt.subplots(figsize=(7, 5))
im = ax.imshow(pivot_count.values, aspect='auto', cmap='YlGnBu', origin='lower')
ax.set_xticks(range(len(pivot_count.columns)))
ax.set_xticklabels([f'{c:.2f}' for c in pivot_count.columns])
ax.set_yticks(range(len(pivot_count.index)))
ax.set_yticklabels(pivot_count.index)
ax.set_xlabel('x (prob of zero delay)')
ax.set_ylabel('n_mu (mean delay candles)')
ax.set_title('Cross-ticker consistency: # tickers with Sharpe > 0.7\n(max 9)')
for i in range(pivot_count.shape[0]):
    for j in range(pivot_count.shape[1]):
        v = pivot_count.values[i, j]
        ax.text(j, i, f'{int(v)}', ha='center', va='center', fontsize=9,
                color='white' if v < pivot_count.values.max() * 0.5 else 'black')
plt.colorbar(im, ax=ax, label='# tickers w/ Sharpe > 0.7')
plt.tight_layout()
out = plots_dir / 'consistency_count_sharpe_gt_07.png'
plt.savefig(out, dpi=130)
plt.close()
print(f'  {out}')

print(f'\nAll plots in {plots_dir}/')
