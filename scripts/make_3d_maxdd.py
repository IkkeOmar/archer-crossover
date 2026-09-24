"""make_3d_maxdd.py — 3D Max Drawdown surfaces + cross-ticker comparison.

Builds:
1. Per-ticker 3D surfaces for max_drawdown (n_mu, x, mean over bear_alloc & ema_pair)
2. Cross-ticker WORST MaxDD per (n_mu, x)
3. 3D scatter: per-ticker best (lowest MaxDD) zone
4. Comparison vs vanilla EMA-cross
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
from src.archer_engine import sweep_arrows, vanilla_ema_cross, buy_and_hold

OUT_DIR = Path('results/plots/3d')
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_MU_GRID = [1, 3, 5, 8, 12, 18, 25, 35, 50]
X_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]
BEAR_ALLOC_GRID = [0.0, 0.5, 1.0]
EMA_PAIRS = [(9, 21), (12, 26)]
TICKERS = ['SPY', 'QQQ', 'IWM', 'AAPL', 'GOOGL', 'BTC-USD', 'ETH-USD', 'GLD', 'SLV']

# Collect MaxDD data for all tickers
print('Computing 3D MaxDD surfaces for all tickers...')
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

    # MaxDD shape (n_mu, x, bear_alloc, ema_pair) — values are NEGATIVE (e.g. -0.5)
    maxdd_avg = np.nanmean(sweep['max_drawdown'], axis=(2, 3))  # (n_mu, x)
    sharpe_avg = np.nanmean(sweep['sharpe'], axis=(2, 3))

    # Per-ticker 3D MaxDD surface
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    X, Y = np.meshgrid(np.arange(len(X_GRID)), np.arange(len(N_MU_GRID)))
    # MaxDD is negative — invert for visualization (less negative = higher)
    Z = -maxdd_avg  # show absolute drawdown as height
    surf = ax.plot_surface(X, Y, Z, cmap='coolwarm', alpha=0.85, edgecolor='k', linewidth=0.3)
    ax.set_xticks(np.arange(len(X_GRID)))
    ax.set_xticklabels([f'{x}' for x in X_GRID])
    ax.set_yticks(np.arange(len(N_MU_GRID)))
    ax.set_yticklabels([f'{nm}' for nm in N_MU_GRID])
    ax.set_xlabel('x (zero-delay probability)')
    ax.set_ylabel('n_mu (mean delay)')
    ax.set_zlabel('|Max Drawdown|')
    ax.set_title(f'{tk} 1d 3D Max Drawdown\n(mean over bear_alloc & ema_pair; lower Z = worse)')
    fig.colorbar(surf, ax=ax, shrink=0.5, label='|MaxDD|')
    plt.tight_layout()
    out = OUT_DIR / f'maxdd_3d_{tk}.png'
    plt.savefig(out, dpi=120)
    plt.close()
    print(f'    Saved: {out}')

    # Best zone (lowest MaxDD) and corresponding Sharpe
    flat_mdd = maxdd_avg.flatten()
    best_mdd_idx = np.nanargmax(flat_mdd)  # least negative MaxDD (best)
    best_mdd = flat_mdd[best_mdd_idx]
    best_mdd_sharpe = sharpe_avg.flatten()[best_mdd_idx]

    # Vanilla baseline for comparison
    van = vanilla_ema_cross(prices)
    eq_van = pd.Series(van.equity)
    cum_max = eq_van.cummax()
    van_mdd = float((eq_van / cum_max - 1.0).min())

    # B&H baseline
    bh = buy_and_hold(prices)
    eq_bh = pd.Series(bh.equity)
    cum_max_bh = eq_bh.cummax()
    bh_mdd = float((eq_bh / cum_max_bh - 1.0).min())

    for i, n_mu in enumerate(N_MU_GRID):
        for j, x in enumerate(X_GRID):
            all_data.append({
                'ticker': tk,
                'n_mu': n_mu,
                'x': x,
                'max_drawdown': float(maxdd_avg[i, j]),
                'sharpe': float(sharpe_avg[i, j]),
            })

    print(f'    Best MaxDD: {best_mdd*100:.1f}% | Vanilla: {van_mdd*100:.1f}% | B&H: {bh_mdd*100:.1f}%')

# Cross-ticker WORST MaxDD (the worst MaxDD observed across all tickers for each (n_mu, x))
print('\nComputing cross-ticker worst MaxDD...')
df_all = pd.DataFrame(all_data)
df_worst = df_all.groupby(['n_mu', 'x'])['max_drawdown'].min().reset_index()  # min = worst (most negative)
df_worst_pivot = df_worst.pivot(index='n_mu', columns='x', values='max_drawdown')

fig, ax = plt.subplots(figsize=(10, 7))
# Use RdYlGn reversed: green = good (less negative), red = bad (more negative)
vmax = 0
vmin = df_worst_pivot.values.min()
im = ax.imshow(df_worst_pivot.values, cmap='RdYlGn_r', aspect='auto', vmin=vmin, vmax=vmax)
ax.set_xticks(np.arange(len(X_GRID)))
ax.set_xticklabels([f'{x}' for x in X_GRID])
ax.set_yticks(np.arange(len(N_MU_GRID)))
ax.set_yticklabels([f'{nm}' for nm in N_MU_GRID])
ax.set_xlabel('x (zero-delay probability)')
ax.set_ylabel('n_mu (mean delay)')
ax.set_title('Cross-Ticker WORST MaxDD (9 tickers 1d)\nGreen = safe, Red = risky')
for i in range(len(N_MU_GRID)):
    for j in range(len(X_GRID)):
        v = df_worst_pivot.values[i, j]
        color = 'white' if v < df_worst_pivot.values.mean() else 'black'
        ax.text(j, i, f'{v*100:.0f}%', ha='center', va='center', color=color, fontsize=8)
fig.colorbar(im, ax=ax, label='MaxDD (most negative = worst)')
plt.tight_layout()
out = OUT_DIR / 'cross_ticker_worst_maxdd.png'
plt.savefig(out, dpi=120)
plt.close()
print(f'Saved: {out}')

# Cross-ticker MEDIAN MaxDD
df_median_mdd = df_all.groupby(['n_mu', 'x'])['max_drawdown'].median().reset_index()
df_median_mdd_pivot = df_median_mdd.pivot(index='n_mu', columns='x', values='max_drawdown')

fig, ax = plt.subplots(figsize=(10, 7))
im = ax.imshow(df_median_mdd_pivot.values, cmap='RdYlGn_r', aspect='auto', vmin=df_median_mdd_pivot.values.min(), vmax=0)
ax.set_xticks(np.arange(len(X_GRID)))
ax.set_xticklabels([f'{x}' for x in X_GRID])
ax.set_yticks(np.arange(len(N_MU_GRID)))
ax.set_yticklabels([f'{nm}' for nm in N_MU_GRID])
ax.set_xlabel('x (zero-delay probability)')
ax.set_ylabel('n_mu (mean delay)')
ax.set_title('Cross-Ticker MEDIAN MaxDD (9 tickers 1d)')
for i in range(len(N_MU_GRID)):
    for j in range(len(X_GRID)):
        v = df_median_mdd_pivot.values[i, j]
        color = 'white' if v < df_median_mdd_pivot.values.mean() else 'black'
        ax.text(j, i, f'{v*100:.0f}%', ha='center', va='center', color=color, fontsize=8)
fig.colorbar(im, ax=ax, label='MaxDD')
plt.tight_layout()
out = OUT_DIR / 'cross_ticker_median_maxdd.png'
plt.savefig(out, dpi=120)
plt.close()
print(f'Saved: {out}')

# 3D scatter: per-ticker BEST (least negative) MaxDD zone
print('\nComputing per-ticker best (least negative) MaxDD zones...')
best_zones = []
for tk in TICKERS:
    sub = df_all[df_all['ticker'] == tk]
    if len(sub) == 0:
        continue
    best_idx = sub['max_drawdown'].idxmax()  # least negative = best
    best = sub.loc[best_idx]
    best_zones.append({
        'ticker': tk,
        'best_n_mu': int(best['n_mu']),
        'best_x': float(best['x']),
        'best_max_dd': float(best['max_drawdown']),
        'sharpe_at_best_mdd': float(best['sharpe']),
    })
df_best = pd.DataFrame(best_zones)
df_best.to_csv('results/best_zones_min_mdd.csv', index=False)
print(df_best.to_string(index=False))

# 3D scatter of best (lowest MaxDD) zones
fig = plt.figure(figsize=(11, 8))
ax = fig.add_subplot(111, projection='3d')
colors = plt.cm.tab10(np.arange(len(df_best)))
for i, row in df_best.iterrows():
    # Plot |MaxDD| as height (inverted to make lower MaxDD appear lower)
    ax.scatter(row['best_x'], row['best_n_mu'], -row['best_max_dd'],
               s=200, color=colors[i], edgecolor='k', linewidth=1, label=row['ticker'])
    ax.text(row['best_x'], row['best_n_mu'], -row['best_max_dd'],
            f"  {row['ticker']}", fontsize=8)
ax.set_xlabel('x (zero-delay prob)')
ax.set_ylabel('n_mu (mean delay)')
ax.set_zlabel('|MaxDD| (lower = better)')
ax.set_title('Best (lowest MaxDD) zone per ticker — 3D scatter\nLower z = lower drawdown at that ticker\'s safe zone')
plt.tight_layout()
out = OUT_DIR / 'best_zones_min_mdd_3d_scatter.png'
plt.savefig(out, dpi=120)
plt.close()
print(f'Saved: {out}')

# Comparison: Archer vs Vanilla vs B&H (worst-case MaxDD across tickers)
print('\n=== MaxDD Comparison (vanilla vs Archer) ===')
van_mdd_data = []
for tk in TICKERS:
    df = load_one(tk, '1d')
    prices = np.asarray(df['close'].values, dtype=np.float64)
    van = vanilla_ema_cross(prices)
    bh = buy_and_hold(prices)
    eq_van = pd.Series(van.equity)
    eq_bh = pd.Series(bh.equity)
    van_mdd = float((eq_van / eq_van.cummax() - 1.0).min())
    bh_mdd = float((eq_bh / eq_bh.cummax() - 1.0).min())
    # Best Archer MaxDD for this ticker
    sub = df_all[df_all['ticker'] == tk]
    arch_best = sub.loc[sub['max_drawdown'].idxmax()]
    arch_mdd = float(arch_best['max_drawdown'])
    van_mdd_data.append({
        'ticker': tk,
        'archer_mdd': arch_mdd,
        'vanilla_mdd': van_mdd,
        'bnh_mdd': bh_mdd,
        'arch_better_than_vanilla': arch_mdd > van_mdd,  # less negative = better
    })
    print(f'  {tk:8s}: Archer={arch_mdd*100:>6.1f}% | Vanilla={van_mdd*100:>6.1f}% | B&H={bh_mdd*100:>6.1f}% | {"Archer<Vanilla" if arch_mdd > van_mdd else "Archer>Vanilla"}')

df_comp = pd.DataFrame(van_mdd_data)
df_comp.to_csv('results/maxdd_archer_vs_vs.csv', index=False)

# Grouped bar chart
fig, ax = plt.subplots(figsize=(12, 6))
x = np.arange(len(df_comp))
width = 0.27
ax.bar(x - width, df_comp['archer_mdd'] * 100, width, label='Archer (best)', color='#7C5CFC')
ax.bar(x, df_comp['vanilla_mdd'] * 100, width, label='Vanilla EMA-cross', color='#38BDF8')
ax.bar(x + width, df_comp['bnh_mdd'] * 100, width, label='Buy & Hold', color='#F0C419')
ax.set_xticks(x)
ax.set_xticklabels(df_comp['ticker'], rotation=30, ha='right')
ax.set_ylabel('Max Drawdown (%)')
ax.set_title('Max Drawdown: Archer vs Vanilla vs Buy & Hold (9 tickers 1d)\nLess negative = better')
ax.axhline(0, color='black', linewidth=0.5)
ax.legend()
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
out = OUT_DIR / 'maxdd_archer_vs_vanilla_bar.png'
plt.savefig(out, dpi=120)
plt.close()
print(f'Saved: {out}')

print('\n=== Summary ===')
print(f"  Median Archer MaxDD: {df_comp['archer_mdd'].median()*100:.1f}%")
print(f"  Median Vanilla MaxDD: {df_comp['vanilla_mdd'].median()*100:.1f}%")
print(f"  Median B&H MaxDD: {df_comp['bnh_mdd'].median()*100:.1f}%")
print(f"  Tickers where Archer < Vanilla (less negative): {(df_comp['archer_mdd'] > df_comp['vanilla_mdd']).sum()}/{len(df_comp)}")
