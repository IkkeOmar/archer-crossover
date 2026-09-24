"""make_3d_full_metrics.py — Komplet 3D suite for ALLE risk metrics.

Dækker:
- Sharpe (allerede lavet)
- Sortino (downside deviation)
- Standard deviation of returns
- Std of WINS (kun profitable trades)
- Std of LOSSES (kun tabsgivende trades)
- Win rate
- Profit factor (gross_win / gross_loss)
- Calmar ratio (CAGR / |MaxDD|)
- Recovery factor (total_return / |MaxDD|)
- Avg win / avg loss
- Expected payoff per trade
- Skewness of returns
- Kurtosis of returns

For hver metric:
1. Per-ticker 3D surface (n_mu, x, mean)
2. Cross-ticker median heatmap
3. Cross-ticker worst-case heatmap (hvor det går værst)

Plus correlation matrix mellem metrics (hvilke metrics peger i samme retning?)
"""
import sys
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import load_one
from src.archer_engine import (
    backtest_arrows, sweep_arrows, vanilla_ema_cross, buy_and_hold,
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

N_MU_ARR = np.array(N_MU_GRID)
X_ARR = np.array(X_GRID)


def compute_full_metrics(prices, params):
    """Beregn ALLE metrics for én (ticker, params) kombination.

    Returnerer dict med:
    - sharpe: annualiseret Sharpe (mean/std * sqrt(252))
    - sortino: annualiseret Sortino (downside deviation)
    - std_returns: annualiseret std
    - std_wins: std af profitable trades' returns
    - std_losses: std af tabsgivende trades' returns
    - win_rate: andel profitable trades
    - profit_factor: gross_win / |gross_loss|
    - calmar: CAGR / |MaxDD|
    - recovery: total_return / |MaxDD|
    - avg_win, avg_loss, payoff_ratio
    - expected_payoff: avg return per trade
    - skewness, kurtosis
    - n_trades
    """
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

    # Per-bar returns
    if len(eq) > 1:
        rets = np.diff(eq) / eq[:-1]
        rets = rets[np.isfinite(rets)]
    else:
        rets = np.array([])

    # MaxDD
    if len(eq) > 1:
        running_max = np.maximum.accumulate(eq)
        dd = eq / running_max - 1.0
        max_dd = float(dd.min())
    else:
        max_dd = 0.0

    # CAGR
    if eq[0] > 0 and eq[-1] > 0 and len(eq) > 1:
        years = len(eq) / 252.0
        if years > 0 and eq[-1] / eq[0] > 0:
            cagr = (eq[-1] / eq[0]) ** (1.0 / years) - 1.0
        else:
            cagr = np.nan
    else:
        cagr = np.nan

    total_return = res.total_return

    # Sharpe
    if len(rets) > 1 and rets.std() > 0:
        out['sharpe'] = rets.mean() / rets.std() * np.sqrt(252)
    else:
        out['sharpe'] = np.nan

    # Sortino (downside deviation only)
    if len(rets) > 1:
        downside = rets[rets < 0]
        if len(downside) > 1 and downside.std() > 0:
            out['sortino'] = rets.mean() / downside.std() * np.sqrt(252)
        else:
            out['sortino'] = np.nan
    else:
        out['sortino'] = np.nan

    # Std of returns (annualiseret)
    out['std_returns'] = rets.std() * np.sqrt(252) if len(rets) > 1 else np.nan

    # Per-trade returns (approximation: rets between trade events)
    # Vi har ikke adgang til trade-by-trade PnL, så vi bruger rets som proxy
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    out['std_wins'] = wins.std() if len(wins) > 1 else np.nan
    out['std_losses'] = losses.std() if len(losses) > 1 else np.nan

    # Win rate
    out['win_rate'] = len(wins) / len(rets) if len(rets) > 0 else np.nan

    # Profit factor
    if len(losses) > 0 and losses.sum() < 0:
        out['profit_factor'] = wins.sum() / abs(losses.sum()) if len(wins) > 0 else 0.0
    else:
        out['profit_factor'] = np.nan

    # Calmar
    if not np.isnan(cagr) and max_dd < 0:
        out['calmar'] = cagr / abs(max_dd)
    else:
        out['calmar'] = np.nan

    # Recovery factor
    if max_dd < 0:
        out['recovery'] = total_return / abs(max_dd)
    else:
        out['recovery'] = np.nan

    # Avg win / avg loss
    out['avg_win'] = wins.mean() if len(wins) > 0 else np.nan
    out['avg_loss'] = losses.mean() if len(losses) > 0 else np.nan
    if len(wins) > 0 and len(losses) > 0 and losses.mean() != 0:
        out['payoff_ratio'] = wins.mean() / abs(losses.mean())
    else:
        out['payoff_ratio'] = np.nan

    # Expected payoff
    out['expected_payoff'] = rets.mean() if len(rets) > 0 else np.nan

    # Skewness / kurtosis
    out['skewness'] = float(stats.skew(rets)) if len(rets) > 3 else np.nan
    out['kurtosis'] = float(stats.kurtosis(rets)) if len(rets) > 3 else np.nan

    out['n_trades'] = res.n_trades
    out['total_return'] = total_return
    out['max_dd'] = max_dd
    out['cagr'] = cagr

    return out


def build_metric_grid(metric_name, ticker):
    """Byg (n_mu, x) grid for én metric og ticker."""
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
                    except Exception as e:
                        pass
            if values:
                grid[i, j] = np.mean(values)
    return grid


def plot_3d_surface(grid, title, out_path, metric_name=''):
    """3D surface plot."""
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    X, Y = np.meshgrid(np.arange(len(X_GRID)), np.arange(len(N_MU_GRID)))
    Z = np.where(np.isnan(grid), 0, grid)  # replace NaN with 0 for plotting
    surf = ax.plot_surface(X, Y, Z, cmap='viridis', alpha=0.85, edgecolor='k', linewidth=0.3)
    ax.set_xticks(np.arange(len(X_GRID)))
    ax.set_xticklabels([f'{x}' for x in X_GRID])
    ax.set_yticks(np.arange(len(N_MU_GRID)))
    ax.set_yticklabels([f'{nm}' for nm in N_MU_GRID])
    ax.set_xlabel('x (zero-delay prob)')
    ax.set_ylabel('n_mu (mean delay)')
    ax.set_zlabel(metric_name)
    ax.set_title(title)
    fig.colorbar(surf, ax=ax, shrink=0.5, label=metric_name)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def plot_heatmap(grid, title, out_path, fmt='{:.2f}', cmap='RdYlGn'):
    """2D heatmap."""
    fig, ax = plt.subplots(figsize=(10, 7))
    vmin, vmax = (np.nanmin(grid), np.nanmax(grid))
    im = ax.imshow(grid, cmap=cmap, aspect='auto', vmin=vmin, vmax=vmax)
    ax.set_xticks(np.arange(len(X_GRID)))
    ax.set_xticklabels([f'{x}' for x in X_GRID])
    ax.set_yticks(np.arange(len(N_MU_GRID)))
    ax.set_yticklabels([f'{nm}' for nm in N_MU_GRID])
    ax.set_xlabel('x (zero-delay prob)')
    ax.set_ylabel('n_mu (mean delay)')
    ax.set_title(title)
    for i in range(len(N_MU_GRID)):
        for j in range(len(X_GRID)):
            v = grid[i, j]
            if not np.isnan(v):
                ax.text(j, i, fmt.format(v), ha='center', va='center',
                        color='white' if abs(v - vmin) > abs(vmax - vmin) * 0.5 else 'black',
                        fontsize=7)
    fig.colorbar(im, ax=ax)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


# ============================================================
# Main: beregn alle metrics for alle tickers
# ============================================================
METRICS = [
    ('sharpe', 'Sharpe Ratio', '{:.2f}', 'RdYlGn'),
    ('sortino', 'Sortino Ratio', '{:.2f}', 'RdYlGn'),
    ('std_returns', 'Std of Returns (annualized)', '{:.2f}', 'RdYlBu_r'),
    ('std_wins', 'Std of Wins', '{:.4f}', 'Blues'),
    ('std_losses', 'Std of Losses', '{:.4f}', 'Reds'),
    ('win_rate', 'Win Rate', '{:.2f}', 'RdYlGn'),
    ('profit_factor', 'Profit Factor (gross_win / gross_loss)', '{:.2f}', 'RdYlGn'),
    ('calmar', 'Calmar (CAGR / |MaxDD|)', '{:.2f}', 'RdYlGn'),
    ('recovery', 'Recovery Factor (return / |MaxDD|)', '{:.2f}', 'RdYlGn'),
    ('payoff_ratio', 'Avg Win / |Avg Loss|', '{:.2f}', 'RdYlGn'),
    ('skewness', 'Skewness of Returns', '{:.2f}', 'RdBu'),
    ('kurtosis', 'Kurtosis of Returns', '{:.2f}', 'RdBu'),
]

print('Computing 3D surfaces for all metrics...')
all_grids = {}  # metric_name -> {ticker: grid}

for metric_name, label, fmt, cmap in METRICS:
    print(f'\n=== {label} ===')
    all_grids[metric_name] = {}
    for tk in TICKERS:
        grid = build_metric_grid(metric_name, tk)
        if grid is not None:
            all_grids[metric_name][tk] = grid
            # 3D surface
            out_3d = OUT_DIR / f'metric_3d_{metric_name}_{tk}.png'
            plot_3d_surface(
                grid,
                f'{tk} 1d: {label}',
                out_3d,
                metric_name=label,
            )
            print(f'  {tk}: 3D saved')

    # Cross-ticker median heatmap
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
        # Worst (most extreme) cross-ticker — for metrics where higher=better: min, where lower=better: max
        if metric_name in ('sharpe', 'sortino', 'win_rate', 'profit_factor', 'calmar', 'recovery', 'payoff_ratio'):
            worst_pivot = df_cross.groupby(['n_mu', 'x'])[metric_name].min().reset_index().pivot(
                index='n_mu', columns='x', values=metric_name)
        else:  # std_returns, std_wins, std_losses, skewness, kurtosis — context-dependent
            worst_pivot = df_cross.groupby(['n_mu', 'x'])[metric_name].max().reset_index().pivot(
                index='n_mu', columns='x', values=metric_name)

        # Heatmap median
        out_med = OUT_DIR / f'cross_median_{metric_name}.png'
        plot_heatmap(median_pivot.values, f'Cross-Ticker MEDIAN {label} (9 tickers 1d)', out_med, fmt, cmap)
        print(f'  Median heatmap saved: {out_med}')

        # Heatmap worst
        out_worst = OUT_DIR / f'cross_worst_{metric_name}.png'
        worst_cmap = 'RdYlGn_r' if metric_name in ('sharpe', 'sortino', 'win_rate', 'profit_factor', 'calmar', 'recovery', 'payoff_ratio') else cmap
        plot_heatmap(worst_pivot.values, f'Cross-Ticker WORST {label} (9 tickers 1d)', out_worst, fmt, worst_cmap)
        print(f'  Worst heatmap saved: {out_worst}')


# ============================================================
# Correlation matrix: hvilke metrics korrelerer?
# ============================================================
print('\n=== Correlation matrix between metrics ===')
flat_metrics = []
for tk in TICKERS:
    if tk not in all_grids['sharpe']:
        continue
    for i, n_mu in enumerate(N_MU_GRID):
        for j, x in enumerate(X_GRID):
            row = {'ticker': tk, 'n_mu': n_mu, 'x': x}
            for metric_name, _, _, _ in METRICS:
                if metric_name in all_grids and tk in all_grids[metric_name]:
                    row[metric_name] = all_grids[metric_name][tk][i, j]
            flat_metrics.append(row)
df_flat = pd.DataFrame(flat_metrics)
df_corr = df_flat[METRICS_NAMES := [m[0] for m in METRICS]].corr()

fig, ax = plt.subplots(figsize=(11, 9))
im = ax.imshow(df_corr.values, cmap='RdBu_r', vmin=-1, vmax=1)
ax.set_xticks(np.arange(len(METRICS_NAMES)))
ax.set_yticks(np.arange(len(METRICS_NAMES)))
ax.set_xticklabels(METRICS_NAMES, rotation=45, ha='right')
ax.set_yticklabels(METRICS_NAMES)
for i in range(len(METRICS_NAMES)):
    for j in range(len(METRICS_NAMES)):
        ax.text(j, i, f'{df_corr.values[i, j]:.2f}', ha='center', va='center',
                color='white' if abs(df_corr.values[i, j]) > 0.5 else 'black',
                fontsize=7)
ax.set_title('Correlation Matrix — Risk Metrics (9 tickers × 45 (n_mu,x) combos)')
fig.colorbar(im, ax=ax)
plt.tight_layout()
out_corr = OUT_DIR / 'metrics_correlation_matrix.png'
plt.savefig(out_corr, dpi=120)
plt.close()
print(f'Correlation matrix saved: {out_corr}')
df_corr.to_csv(DATA_DIR / 'metrics_correlation.csv')


# ============================================================
# Per-metric sweet spot summary
# ============================================================
print('\n=== Per-metric sweet spot (cross-ticker median) ===')
sweet_spots = []
for metric_name, label, _, _ in METRICS:
    df_metric = pd.read_csv(DATA_DIR / f'cross_{metric_name}.csv')
    pivot = df_metric.groupby(['n_mu', 'x'])[metric_name].median().reset_index().pivot(
        index='n_mu', columns='x', values=metric_name)
    flat = pivot.values.flatten()
    valid = ~np.isnan(flat)
    if valid.sum() == 0:
        continue
    if metric_name in ('sharpe', 'sortino', 'win_rate', 'profit_factor', 'calmar', 'recovery', 'payoff_ratio'):
        best_flat_idx = np.nanargmax(flat)
    else:
        # For std metrics — lower is better, but median is informative
        best_flat_idx = np.nanargmin(flat) if metric_name in ('std_returns',) else np.nanargmax(flat)
    best_i, best_j = np.unravel_index(best_flat_idx, pivot.values.shape)
    best_n_mu = N_MU_GRID[best_i]
    best_x = X_GRID[best_j]
    best_val = pivot.values[best_i, best_j]
    sweet_spots.append({
        'metric': metric_name,
        'best_n_mu': best_n_mu,
        'best_x': best_x,
        'median_at_best': float(best_val),
    })
    print(f'  {metric_name:15s}: best ({best_n_mu}, {best_x}) -> {best_val:.4f}')

df_sweet = pd.DataFrame(sweet_spots)
df_sweet.to_csv(DATA_DIR / 'sweet_spots_per_metric.csv', index=False)
print(f'\nSweet spots saved: {DATA_DIR}/sweet_spots_per_metric.csv')
print('\nDone.')
