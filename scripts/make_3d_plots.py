"""make_3d_plots.py — 3D Sharpe surfaces + cross-ticker comparison.

Builds:
1. Per-ticker 3D surfaces (n_mu, x, bear_alloc) for each ticker
2. Cross-ticker overlay: median Sharpe per (n_mu, x, bear_alloc) across all tickers
3. 3D bar chart: Sharpe per (ticker, n_mu, x) for top combinations
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import load_one
from src.archer_engine import sweep_arrows

OUT_DIR = Path('results/plots/3d')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Big-ish grid for 3D exploration
N_MU_GRID = [1, 3, 5, 8, 12, 18, 25, 35, 50]
X_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]
BEAR_ALLOC_GRID = [0.0, 0.5, 0.75, 1.0]
EMA_PAIRS = [(9, 21), (12, 26)]

TICKERS = ['SPY', 'QQQ', 'IWM', 'AAPL', 'GOOGL', 'BTC-USD', 'ETH-USD', 'GLD', 'SLV']

# Per-ticker 3D surface: Sharpe over (n_mu, x) averaged across bear_alloc & ema_pair
print('Computing per-ticker 3D surfaces...')
all_data = []

for tk in TICKERS:
    print(f'  {tk}...')
    df = load_one(tk, '1d')
    if len(df) < 100:
        continue
    prices = np.asarray(df['close'].values, dtype=np.float64)

    sweep = sweep_arrows(
        prices,
        n_mu_grid=np.array(N_MU_GRID),
        x_grid=np.array(X_GRID),
        bear_alloc_grid=np.array(BEAR_ALLOC_GRID),
        ema_pairs=EMA_PAIRS,
        cost_bps=5.0,
    )

    # Shape: (n_mu, x, bear_alloc, ema_pair)
    # Average across bear_alloc and ema_pair for the 3D plot
    sharpe_avg = np.nanmean(sweep['sharpe'], axis=(2, 3))  # (n_mu, x)
    total_ret_avg = np.nanmean(sweep['total_return'], axis=(2, 3))

    for i, n_mu in enumerate(N_MU_GRID):
        for j, x in enumerate(X_GRID):
            all_data.append({
                'ticker': tk,
                'n_mu': n_mu,
                'x': x,
                'sharpe': float(sharpe_avg[i, j]),
                'total_return': float(total_ret_avg[i, j]),
            })

    # Per-ticker 3D surface plot
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    X, Y = np.meshgrid(np.arange(len(X_GRID)), np.arange(len(N_MU_GRID)))
    Z = sharpe_avg
    surf = ax.plot_surface(X, Y, Z, cmap='viridis', alpha=0.85, edgecolor='k', linewidth=0.3)
    ax.set_xticks(np.arange(len(X_GRID)))
    ax.set_xticklabels([f'{x}' for x in X_GRID])
    ax.set_yticks(np.arange(len(N_MU_GRID)))
    ax.set_yticklabels([f'{nm}' for nm in N_MU_GRID])
    ax.set_xlabel('x (zero-delay probability)')
    ax.set_ylabel('n_mu (mean delay)')
    ax.set_zlabel('Avg Sharpe')
    ax.set_title(f'{tk} 1d 3D Sharpe Surface\n(mean over bear_alloc & ema_pair)')
    fig.colorbar(surf, ax=ax, shrink=0.5, label='Sharpe')
    plt.tight_layout()
    out = OUT_DIR / f'surface_3d_{tk}.png'
    plt.savefig(out, dpi=120)
    plt.close()
    print(f'    Saved: {out}')

# Cross-ticker median surface
print('\nComputing cross-ticker median...')
df_all = pd.DataFrame(all_data)
df_median = df_all.groupby(['n_mu', 'x'])['sharpe'].median().reset_index()
df_median_pivot = df_median.pivot(index='n_mu', columns='x', values='sharpe')

fig, ax = plt.subplots(figsize=(10, 7))
im = ax.imshow(df_median_pivot.values, cmap='viridis', aspect='auto')
ax.set_xticks(np.arange(len(X_GRID)))
ax.set_xticklabels([f'{x}' for x in X_GRID])
ax.set_yticks(np.arange(len(N_MU_GRID)))
ax.set_yticklabels([f'{nm}' for nm in N_MU_GRID])
ax.set_xlabel('x (zero-delay probability)')
ax.set_ylabel('n_mu (mean delay)')
ax.set_title('Cross-Ticker Median Sharpe (9 tickers 1d)\nHigher = better across all tickers')
for i in range(len(N_MU_GRID)):
    for j in range(len(X_GRID)):
        v = df_median_pivot.values[i, j]
        color = 'white' if v < df_median_pivot.values.mean() else 'black'
        ax.text(j, i, f'{v:.2f}', ha='center', va='center', color=color, fontsize=8)
fig.colorbar(im, ax=ax, label='Median Sharpe')
plt.tight_layout()
out = OUT_DIR / 'cross_ticker_median.png'
plt.savefig(out, dpi=120)
plt.close()
print(f'Saved: {out}')

# 3D cross-ticker comparison: per-ticker 3D bar chart of best zone
print('\nComputing per-ticker best (n_mu, x) zones...')
best_zones = []
for tk in TICKERS:
    sub = df_all[df_all['ticker'] == tk]
    if len(sub) == 0:
        continue
    best_idx = sub['sharpe'].idxmax()
    best = sub.loc[best_idx]
    best_zones.append({
        'ticker': tk,
        'best_n_mu': int(best['n_mu']),
        'best_x': float(best['x']),
        'best_sharpe': float(best['sharpe']),
        'best_return': float(best['total_return']),
    })
df_best = pd.DataFrame(best_zones)
df_best.to_csv('results/best_zones_per_ticker.csv', index=False)
print(df_best.to_string(index=False))

# 3D scatter: best (n_mu, x, sharpe) per ticker
fig = plt.figure(figsize=(11, 8))
ax = fig.add_subplot(111, projection='3d')
colors = plt.cm.tab10(np.arange(len(df_best)))
for i, row in df_best.iterrows():
    ax.scatter(row['best_x'], row['best_n_mu'], row['best_sharpe'],
               s=200, color=colors[i], edgecolor='k', linewidth=1, label=row['ticker'])
    ax.text(row['best_x'], row['best_n_mu'], row['best_sharpe'],
            f"  {row['ticker']}", fontsize=8)
ax.set_xlabel('x (zero-delay prob)')
ax.set_ylabel('n_mu (mean delay)')
ax.set_zlabel('Best Sharpe')
ax.set_title('Best (n_mu, x) zone per ticker — 3D scatter\nHigher z = better Sharpe at that ticker\'s sweet spot')
plt.tight_layout()
out = OUT_DIR / 'best_zones_3d_scatter.png'
plt.savefig(out, dpi=120)
plt.close()
print(f'Saved: {out}')

# Comparison: how do tickers cluster in (n_mu, x) space?
print('\n=== Best-zone clustering ===')
print(f"  Most common n_mu: {df_best['best_n_mu'].mode()[0]}")
print(f"  Most common x:    {df_best['best_x'].mode()[0]}")
print(f"  n_mu range:       {df_best['best_n_mu'].min()}-{df_best['best_n_mu'].max()}")
print(f"  x range:          {df_best['best_x'].min():.2f}-{df_best['best_x'].max():.2f}")
print(f"  Mean best Sharpe: {df_best['best_sharpe'].mean():.2f}")
