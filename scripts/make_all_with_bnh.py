"""make_all_with_bnh.py — Regenerer ALLE 3D og 2D plots MED B&H baseline.

Tilføjer:
- 3D plots: gennemsigtig B&H reference-plan (grøn=højere-bedre, rød=lavere-bedre)
- 2D heatmaps: tekst-boks med B&H værdi
- Alle plots: "Better than B&H" / "Worse than B&H" annotation

For hver metric, for hver ticker, vises B&H baseline som reference.
Brugeren kan dermed se om Archer-specifikt delay er bedre eller værre end
bare at holde aktien.
"""
import sys
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import load_one
from src.archer_engine import (
    backtest_arrows, buy_and_hold,
)

warnings.filterwarnings('ignore')

OUT_DIR = Path('results/plots/3d')
OUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = Path('results/3d_metrics')
DATA_DIR.mkdir(parents=True, exist_ok=True)

N_MU_GRID = [1, 3, 5, 8, 12, 18, 25, 35, 50]
X_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]
BEAR_ALLOC_GRID = [0.0, 0.5, 1.0]
EMA_PAIRS = [(9, 21), (12, 26)]
TICKERS = ['SPY', 'QQQ', 'IWM', 'AAPL', 'GOOGL', 'BTC-USD', 'ETH-USD', 'GLD', 'SLV']

# (metric_name, label, fmt, cmap, higher_better)
METRICS = [
    ('sharpe', 'Sharpe Ratio', '{:.2f}', 'RdYlGn', True),
    ('sortino', 'Sortino Ratio', '{:.2f}', 'RdYlGn', True),
    ('std_returns', 'Std of Returns (annualized)', '{:.2f}', 'RdYlBu_r', False),
    ('std_wins', 'Std of Wins', '{:.4f}', 'Blues', False),
    ('std_losses', 'Std of Losses', '{:.4f}', 'Reds', False),
    ('win_rate', 'Win Rate', '{:.2f}', 'RdYlGn', True),
    ('profit_factor', 'Profit Factor', '{:.2f}', 'RdYlGn', True),
    ('calmar', 'Calmar Ratio', '{:.2f}', 'RdYlGn', True),
    ('recovery', 'Recovery Factor', '{:.2f}', 'RdYlGn', True),
    ('payoff_ratio', 'Avg Win / |Avg Loss|', '{:.2f}', 'RdYlGn', True),
    ('skewness', 'Skewness of Returns', '{:.2f}', 'RdBu', None),
    ('kurtosis', 'Kurtosis of Returns', '{:.2f}', 'RdBu', None),
]


def compute_bnh_baseline(ticker):
    """Compute B&H baseline metrics for a ticker."""
    df = load_one(ticker, '1d')
    prices = np.asarray(df['close'].values, dtype=np.float64)
    bh = buy_and_hold(prices)
    eq = pd.Series(bh.equity)

    total_return = bh.total_return
    rets = eq.pct_change().dropna()
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else np.nan
    downside = rets[rets < 0]
    sortino = rets.mean() / downside.std() * np.sqrt(252) if len(downside) > 1 and downside.std() > 0 else np.nan
    std_returns = rets.std() * np.sqrt(252)
    std_wins = rets[rets > 0].std() if (rets > 0).sum() > 1 else np.nan
    std_losses = rets[rets < 0].std() if (rets < 0).sum() > 1 else np.nan
    win_rate = (rets > 0).sum() / len(rets) if len(rets) > 0 else np.nan
    gross_win = rets[rets > 0].sum()
    gross_loss = abs(rets[rets < 0].sum())
    profit_factor = gross_win / gross_loss if gross_loss > 0 else np.nan
    running_max = eq.cummax()
    max_dd = float((eq / running_max - 1.0).min())
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (252.0 / len(eq)) - 1.0 if eq.iloc[0] > 0 and eq.iloc[-1] > 0 else np.nan
    calmar = cagr / abs(max_dd) if not np.isnan(cagr) and max_dd < 0 else np.nan
    recovery = total_return / abs(max_dd) if max_dd < 0 else np.nan
    avg_win = rets[rets > 0].mean() if (rets > 0).sum() > 0 else np.nan
    avg_loss = rets[rets < 0].mean() if (rets < 0).sum() > 0 else np.nan
    payoff_ratio = avg_win / abs(avg_loss) if not np.isnan(avg_win) and not np.isnan(avg_loss) and avg_loss != 0 else np.nan
    skewness = float(stats.skew(rets)) if len(rets) > 3 else np.nan
    kurtosis = float(stats.kurtosis(rets)) if len(rets) > 3 else np.nan

    return {
        'total_return': total_return,
        'sharpe': sharpe,
        'sortino': sortino,
        'std_returns': std_returns,
        'std_wins': std_wins,
        'std_losses': std_losses,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_dd': max_dd,
        'cagr': cagr,
        'calmar': calmar,
        'recovery': recovery,
        'payoff_ratio': payoff_ratio,
        'skewness': skewness,
        'kurtosis': kurtosis,
        'n_bars': len(eq),
    }


def compute_full_metrics(prices, params):
    """Compute all metrics for one (ticker, params) combination."""
    res = backtest_arrows(
        prices,
        n_mu=params['n_mu'],
        x_zero=params['x'],
        fast_period=params['fast_period'],
        slow_period=params['slow_period'],
        bear_alloc=params['bear_alloc'],
        cost_bps=5.0,
    )
    eq = np.asarray(res.equity, dtype=np.float64)
    out = {}

    if len(eq) > 1:
        rets = np.diff(eq) / eq[:-1]
        rets = rets[np.isfinite(rets)]
    else:
        rets = np.array([])

    if len(eq) > 1:
        running_max = np.maximum.accumulate(eq)
        dd = eq / running_max - 1.0
        max_dd = float(dd.min())
    else:
        max_dd = 0.0

    if eq[0] > 0 and eq[-1] > 0 and len(eq) > 1:
        years = len(eq) / 252.0
        if years > 0 and eq[-1] / eq[0] > 0:
            cagr = (eq[-1] / eq[0]) ** (1.0 / years) - 1.0
        else:
            cagr = np.nan
    else:
        cagr = np.nan

    total_return = res.total_return

    if len(rets) > 1 and rets.std() > 0:
        out['sharpe'] = rets.mean() / rets.std() * np.sqrt(252)
    else:
        out['sharpe'] = np.nan

    if len(rets) > 1:
        downside = rets[rets < 0]
        if len(downside) > 1 and downside.std() > 0:
            out['sortino'] = rets.mean() / downside.std() * np.sqrt(252)
        else:
            out['sortino'] = np.nan
    else:
        out['sortino'] = np.nan

    out['std_returns'] = rets.std() * np.sqrt(252) if len(rets) > 1 else np.nan

    wins = rets[rets > 0]
    losses = rets[rets < 0]
    out['std_wins'] = wins.std() if len(wins) > 1 else np.nan
    out['std_losses'] = losses.std() if len(losses) > 1 else np.nan
    out['win_rate'] = len(wins) / len(rets) if len(rets) > 0 else np.nan

    if len(losses) > 0 and losses.sum() < 0:
        out['profit_factor'] = wins.sum() / abs(losses.sum()) if len(wins) > 0 else 0.0
    else:
        out['profit_factor'] = np.nan

    if not np.isnan(cagr) and max_dd < 0:
        out['calmar'] = cagr / abs(max_dd)
    else:
        out['calmar'] = np.nan

    if max_dd < 0:
        out['recovery'] = total_return / abs(max_dd)
    else:
        out['recovery'] = np.nan

    out['avg_win'] = wins.mean() if len(wins) > 0 else np.nan
    out['avg_loss'] = losses.mean() if len(losses) > 0 else np.nan
    if len(wins) > 0 and len(losses) > 0 and losses.mean() != 0:
        out['payoff_ratio'] = wins.mean() / abs(losses.mean())
    else:
        out['payoff_ratio'] = np.nan

    out['expected_payoff'] = rets.mean() if len(rets) > 0 else np.nan
    out['skewness'] = float(stats.skew(rets)) if len(rets) > 3 else np.nan
    out['kurtosis'] = float(stats.kurtosis(rets)) if len(rets) > 3 else np.nan
    out['n_trades'] = res.n_trades
    out['total_return'] = total_return
    out['max_dd'] = max_dd
    out['cagr'] = cagr

    return out


def build_metric_grid(metric_name, ticker):
    """Build (n_mu, x) grid for one metric and ticker."""
    df = load_one(ticker, '1d')
    if len(df) < 100:
        return None
    prices = np.asarray(df['close'].values, dtype=np.float64)
    grid = np.full((len(N_MU_GRID), len(X_GRID)), np.nan)
    for i, n_mu in enumerate(N_MU_GRID):
        for j, x in enumerate(X_GRID):
            values = []
            for bear_alloc in BEAR_ALLOC_GRID:
                for fast, slow in EMA_PAIRS:
                    try:
                        m = compute_full_metrics(prices, {
                            'n_mu': n_mu, 'x': x,
                            'fast_period': fast, 'slow_period': slow,
                            'bear_alloc': bear_alloc,
                        })
                        v = m.get(metric_name, np.nan)
                        if not np.isnan(v):
                            values.append(v)
                    except Exception:
                        pass
            if values:
                grid[i, j] = np.mean(values)
    return grid


def plot_3d_with_bnh(grid, n_mu_values, x_values, bnh_value, ticker, metric_label,
                     out_path, higher_better, n_tickers=9):
    """3D surface with B&H reference plane + annotation."""
    n_nmu, n_x = grid.shape
    fig = plt.figure(figsize=(11, 8))
    ax = fig.add_subplot(111, projection='3d')
    # grid is indexed [n_mu, x], so Xi indexes n_mu, Yi indexes x
    Xi_idx, Yi_idx = np.meshgrid(np.arange(n_nmu), np.arange(n_x), indexing='ij')
    Xl = np.array(n_mu_values)[:n_nmu][Xi_idx]
    Yl = np.array(x_values)[:n_x][Yi_idx]
    Z = np.where(np.isnan(grid), 0, grid)
    surf = ax.plot_surface(Xl, Yl, Z, cmap='viridis', alpha=0.7, edgecolor='k', linewidth=0.3)

    # B&H reference plane
    if not np.isnan(bnh_value):
        Z_bnh = np.full_like(grid, bnh_value)
        if higher_better is True:
            bnh_color, edge_color, label_suffix = 'lightgreen', 'darkgreen', 'better ABOVE plane'
        elif higher_better is False:
            bnh_color, edge_color, label_suffix = 'salmon', 'darkred', 'better BELOW plane'
        else:
            bnh_color, edge_color, label_suffix = 'lightgray', 'gray', 'closer to 0 = better'
        ax.plot_surface(Xl, Yl, Z_bnh, color=bnh_color, alpha=0.4,
                        edgecolor=edge_color, linewidth=1.5)

    # Annotation box with B&H baseline
    if not np.isnan(bnh_value):
        textstr = (f'B&H Baseline ({ticker}):\n'
                   f'  {metric_label}: {bnh_value:.3f}\n'
                   f'  ({label_suffix})')
    else:
        textstr = f'B&H baseline: N/A'
    ax.text2D(0.02, 0.95, textstr, transform=ax.transAxes,
              fontsize=10, fontweight='bold', family='monospace',
              bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow',
                        edgecolor='black', alpha=0.9))

    ax.set_xlabel('n_mu (mean delay)')
    ax.set_ylabel('x (zero-delay prob)')
    ax.set_zlabel(metric_label)
    ax.set_title(f'{ticker} 1d: {metric_label}\n(plane = B&H baseline)')
    fig.colorbar(surf, ax=ax, shrink=0.5, label=metric_label)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def plot_heatmap_with_bnh(grid, n_mu_values, x_values, bnh_mean, n_tickers,
                          title, out_path, fmt, cmap, higher_better):
    """2D heatmap with cross-ticker B&H mean annotation."""
    fig, ax = plt.subplots(figsize=(11, 7))
    vmin, vmax = (np.nanmin(grid), np.nanmax(grid))
    im = ax.imshow(grid, cmap=cmap, aspect='auto', vmin=vmin, vmax=vmax)
    ax.set_xticks(np.arange(len(X_GRID)))
    ax.set_xticklabels([f'{x}' for x in X_GRID])
    ax.set_yticks(np.arange(len(N_MU_GRID)))
    ax.set_yticklabels([f'{nm}' for nm in N_MU_GRID])
    ax.set_xlabel('x (zero-delay prob)')
    ax.set_ylabel('n_mu (mean delay)')

    # Cell annotations
    for i in range(len(N_MU_GRID)):
        for j in range(len(X_GRID)):
            v = grid[i, j]
            if not np.isnan(v):
                color = 'white' if abs(v - vmin) > abs(vmax - vmin) * 0.5 else 'black'
                ax.text(j, i, fmt.format(v), ha='center', va='center',
                        color=color, fontsize=7)

    # B&H annotation
    if higher_better is True:
        bnh_text = f'B&H baseline: {bnh_mean:.3f}  (better ABOVE)'
    elif higher_better is False:
        bnh_text = f'B&H baseline: {bnh_mean:.3f}  (better BELOW)'
    else:
        bnh_text = f'B&H baseline: {bnh_mean:.3f}  (closer to 0 = better)'

    ax.set_title(f'{title}\n{bnh_text}\n(aggregated across {n_tickers} tickers)')
    fig.colorbar(im, ax=ax)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def plot_worst_heatmap_with_bnh(grid, n_mu_values, x_values, bnh_min, n_tickers,
                                title, out_path, fmt, cmap, higher_better):
    """2D worst-case heatmap with B&H worst annotation."""
    fig, ax = plt.subplots(figsize=(11, 7))
    vmin, vmax = (np.nanmin(grid), np.nanmax(grid))
    im = ax.imshow(grid, cmap=cmap, aspect='auto', vmin=vmin, vmax=vmax)
    ax.set_xticks(np.arange(len(X_GRID)))
    ax.set_xticklabels([f'{x}' for x in X_GRID])
    ax.set_yticks(np.arange(len(N_MU_GRID)))
    ax.set_yticklabels([f'{nm}' for nm in N_MU_GRID])
    ax.set_xlabel('x (zero-delay prob)')
    ax.set_ylabel('n_mu (mean delay)')

    for i in range(len(N_MU_GRID)):
        for j in range(len(X_GRID)):
            v = grid[i, j]
            if not np.isnan(v):
                color = 'white' if abs(v - vmin) > abs(vmax - vmin) * 0.5 else 'black'
                ax.text(j, i, fmt.format(v), ha='center', va='center',
                        color=color, fontsize=7)

    if higher_better is True:
        bnh_text = f'B&H worst across {n_tickers} tickers: {bnh_min:.3f}'
    else:
        bnh_text = f'B&H worst across {n_tickers} tickers: {bnh_min:.3f}'

    ax.set_title(f'{title}\n{bnh_text}')
    fig.colorbar(im, ax=ax)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


# ============================================================
# MAIN
# ============================================================
print('=== Computing B&H baselines for all 9 tickers ===')
bnh_baselines = {}
for tk in TICKERS:
    bnh = compute_bnh_baseline(tk)
    bnh_baselines[tk] = bnh
    print(f'  {tk}: ret={bnh["total_return"]*100:>7.1f}%, sharpe={bnh["sharpe"]:.3f}, maxdd={bnh["max_dd"]*100:.1f}%, CAGR={bnh["cagr"]*100:.1f}%')

# Save B&H baselines
bnh_df = pd.DataFrame(bnh_baselines).T
bnh_df.index.name = 'ticker'
bnh_df.to_csv('results/bnh_baselines.csv')
print('\nB&H baselines saved: results/bnh_baselines.csv')

# Cross-ticker B&H stats (mean for higher-better, min for lower-better)
cross_bnh = {}
for metric_name, _, _, _, higher_better in METRICS:
    vals = [bnh_baselines[tk][metric_name] for tk in TICKERS if metric_name in bnh_baselines[tk]]
    vals = [v for v in vals if not np.isnan(v)]
    if vals:
        cross_bnh[metric_name] = {
            'mean': np.mean(vals),
            'min': np.min(vals),
            'max': np.max(vals),
        }
    else:
        cross_bnh[metric_name] = {'mean': np.nan, 'min': np.nan, 'max': np.nan}

print('\n=== Generating 3D and 2D plots with B&H baseline ===')
all_grids = {}

for metric_name, label, fmt, cmap, higher_better in METRICS:
    print(f'\n=== {label} ===')
    all_grids[metric_name] = {}

    for tk in TICKERS:
        grid = build_metric_grid(metric_name, tk)
        if grid is not None:
            all_grids[metric_name][tk] = grid
            bnh_val = bnh_baselines[tk].get(metric_name, np.nan)
            out_3d = OUT_DIR / f'metric_3d_{metric_name}_{tk}.png'
            plot_3d_with_bnh(
                grid, N_MU_GRID, X_GRID, bnh_val, tk, label,
                out_3d, higher_better,
            )
            print(f'  {tk}: 3D saved (B&H: {bnh_val:.3f})')

    # Cross-ticker median heatmap with B&H annotation
    cross_data = []
    for tk, grid in all_grids[metric_name].items():
        for i, n_mu in enumerate(N_MU_GRID):
            for j, x in enumerate(X_GRID):
                if not np.isnan(grid[i, j]):
                    cross_data.append({
                        'ticker': tk,
                        'n_mu': n_mu,
                        'x': x,
                        metric_name: grid[i, j],
                    })
    if cross_data:
        df_cross = pd.DataFrame(cross_data)
        df_cross.to_csv(DATA_DIR / f'cross_{metric_name}.csv', index=False)

        median_pivot = df_cross.groupby(['n_mu', 'x'])[metric_name].median().reset_index().pivot(
            index='n_mu', columns='x', values=metric_name)
        # For worst-case: for higher-better take min, for lower-better take max
        if higher_better is True:
            worst_pivot = df_cross.groupby(['n_mu', 'x'])[metric_name].min().reset_index().pivot(
                index='n_mu', columns='x', values=metric_name)
            worst_bnh_value = cross_bnh[metric_name]['min']
        elif higher_better is False:
            worst_pivot = df_cross.groupby(['n_mu', 'x'])[metric_name].max().reset_index().pivot(
                index='n_mu', columns='x', values=metric_name)
            worst_bnh_value = cross_bnh[metric_name]['max']
        else:
            worst_pivot = df_cross.groupby(['n_mu', 'x'])[metric_name].apply(
                lambda x: x.iloc[np.argmax(np.abs(x - np.median(x)))] if len(x) > 0 else np.nan).reset_index().pivot(
                index='n_mu', columns='x', values=metric_name)
            worst_bnh_value = cross_bnh[metric_name]['mean']

        # Median heatmap
        out_med = OUT_DIR / f'cross_median_{metric_name}.png'
        plot_heatmap_with_bnh(
            median_pivot.values, N_MU_GRID, X_GRID,
            cross_bnh[metric_name]['mean'], 9,
            f'Cross-Ticker MEDIAN {label}', out_med, fmt, cmap, higher_better,
        )
        print(f'  Median heatmap saved (B&H cross-mean: {cross_bnh[metric_name]["mean"]:.3f})')

        # Worst heatmap
        out_worst = OUT_DIR / f'cross_worst_{metric_name}.png'
        worst_cmap = cmap
        plot_worst_heatmap_with_bnh(
            worst_pivot.values, N_MU_GRID, X_GRID,
            worst_bnh_value, 9,
            f'Cross-Ticker WORST {label}', out_worst, fmt, worst_cmap, higher_better,
        )
        print(f'  Worst heatmap saved (B&H worst: {worst_bnh_value:.3f})')

print('\n=== Per-ticker comparison table ===')
print(f'{"Ticker":10s} {"B&H return":>12s} {"B&H Sharpe":>11s} {"B&H MaxDD":>11s} {"B&H CAGR":>10s} {"n_bars":>7s}')
for tk in TICKERS:
    b = bnh_baselines[tk]
    print(f'  {tk:8s} {b["total_return"]*100:>10.1f}% {b["sharpe"]:>10.3f} {b["max_dd"]*100:>9.1f}% {b["cagr"]*100:>8.1f}% {b["n_bars"]:>7d}')

print('\nDone — all plots now include B&H baseline.')
