"""make_3d_from_cluster.py — Regenerate 3D plots from cluster_local CSVs.

Reads all CSVs in results/cluster_local/ (one per ticker,timeframe pair)
and produces 3D surface plots + heatmaps for key metrics, mirroring the
structure of make_3d_full_metrics.py / make_3d_maxdd.py but using the
MC-validated sweep output.
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

warnings.filterwarnings('ignore')

OUT_DIR = Path('results/plots/3d_cluster')
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_DIR = Path('results/cluster_local')

# Metrics available in cluster CSVs
METRICS = {
    'in_sample_sharpe': 'Sharpe (in-sample)',
    'mc_sharpe_mean':   'Sharpe (MC mean, 20 seeds)',
    'wf_mean_sharpe':   'Sharpe (WF mean, 20 windows)',
    'wf_pos_sharpe_frac': 'WF positive Sharpe fraction',
    'mc_robust_sharpe': 'Robust Sharpe (mean/std)',
    'in_sample_return': 'Total return (in-sample)',
    'wf_worst_return':  'WF worst return',
}

def load_all():
    files = sorted(CSV_DIR.glob('*.csv'))
    if not files:
        print(f'ERROR: no CSVs found in {CSV_DIR}/')
        sys.exit(1)
    frames = []
    for f in files:
        df = pd.read_csv(f)
        # Ticker is in the CSV but filename also encodes ticker_timeframe.
        # Use ticker from CSV for safety (BTC-USD vs BTC_USD etc.).
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def pivot_metric(df, metric, agg='mean'):
    """Pivot df into a (n_mu, x_zero) grid, aggregating over bear_alloc & ema_pair."""
    return df.pivot_table(
        index='n_mu', columns='x_zero', values=metric, aggfunc=agg
    )


def plot_3d_surface(grid, title, out_path, zlabel=''):
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    n_mu_vals = grid.index.values
    x_vals = grid.columns.values
    X, Y = np.meshgrid(x_vals, n_mu_vals)
    Z = grid.values
    Zmasked = np.where(np.isnan(Z), np.nan, Z)
    surf = ax.plot_surface(X, Y, Zmasked, cmap='viridis', alpha=0.85,
                           edgecolor='k', linewidth=0.3)
    ax.set_xlabel('x (zero-delay prob)')
    ax.set_ylabel('n_mu (mean delay)')
    ax.set_zlabel(zlabel)
    ax.set_title(title)
    fig.colorbar(surf, ax=ax, shrink=0.5, label=zlabel)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def plot_heatmap(grid, title, out_path, fmt='{:.2f}', cmap='RdYlGn'):
    fig, ax = plt.subplots(figsize=(10, 7))
    vmin, vmax = (np.nanmin(grid.values), np.nanmax(grid.values))
    im = ax.imshow(grid.values, cmap=cmap, aspect='auto', vmin=vmin, vmax=vmax)
    ax.set_xticks(np.arange(len(grid.columns)))
    ax.set_xticklabels([f'{c}' for c in grid.columns])
    ax.set_yticks(np.arange(len(grid.index)))
    ax.set_yticklabels([f'{i}' for i in grid.index])
    ax.set_xlabel('x (zero-delay prob)')
    ax.set_ylabel('n_mu (mean delay)')
    ax.set_title(title)
    for i in range(len(grid.index)):
        for j in range(len(grid.columns)):
            v = grid.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, fmt.format(v), ha='center', va='center',
                        color='white' if abs(v - vmin) > abs(vmax - vmin) * 0.5 else 'black',
                        fontsize=7)
    fig.colorbar(im, ax=ax)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def main():
    df_all = load_all()
    print(f'Loaded {len(df_all)} rows from {df_all["ticker"].nunique()} tickers '
          f'× {df_all["timeframe"].nunique()} timeframes')

    # ---------- Per (ticker, timeframe) surfaces ----------
    for (tk, tf), grp in df_all.groupby(['ticker', 'timeframe']):
        tk_safe = tk.replace('-', '_')
        print(f'  {tk} {tf}: {len(grp)} rows')
        for metric, label in METRICS.items():
            if metric not in grp.columns:
                continue
            grid = pivot_metric(grp, metric, agg='mean')
            if grid.empty:
                continue
            plot_3d_surface(
                grid, f'{tk} {tf} — {label}',
                OUT_DIR / f'surface_{metric}_{tk_safe}_{tf}.png',
                zlabel=label,
            )
            plot_heatmap(
                grid, f'{tk} {tf} — {label} (heatmap)',
                OUT_DIR / f'heatmap_{metric}_{tk_safe}_{tf}.png',
            )

    # ---------- Cross-ticker median (1d only) ----------
    print('\nCross-ticker medians (1d only)...')
    df_1d = df_all[df_all['timeframe'] == '1d']
    for metric, label in METRICS.items():
        if metric not in df_1d.columns:
            continue
        cross = df_1d.groupby(['n_mu', 'x_zero'])[metric].median().unstack()
        cross.to_csv(OUT_DIR / f'cross_median_{metric}.csv')
        plot_heatmap(
            cross, f'1d CROSS-TICKER MEDIAN — {label}',
            OUT_DIR / f'cross_median_{metric}.png',
            cmap='RdYlGn',
        )

    # ---------- Cross-ticker worst (1d only) ----------
    print('Cross-ticker worst (1d only)...')
    for metric, label in METRICS.items():
        if metric not in df_1d.columns:
            continue
        # "worst" = minimum across tickers per (n_mu, x) — penalises parameters that fail anywhere
        cross = df_1d.groupby(['n_mu', 'x_zero'])[metric].min().unstack()
        plot_heatmap(
            cross, f'1d CROSS-TICKER WORST — {label}',
            OUT_DIR / f'cross_worst_{metric}.png',
            cmap='RdYlGn_r',
        )

    # Metrics where higher is better
    HIGHER_IS_BETTER = {
        'in_sample_sharpe', 'mc_sharpe_mean', 'wf_mean_sharpe',
        'wf_pos_sharpe_frac', 'mc_robust_sharpe', 'in_sample_return',
    }
    # Metrics where higher (less negative) is better
    NEGATIVE_BETTER = {'wf_worst_return'}  # want closest to 0 (i.e. least negative)

    # ---------- Sweet spots per metric (1d) ----------
    print('\nSweet spots per metric (1d)...')
    rows = []
    for metric, label in METRICS.items():
        if metric not in df_1d.columns:
            continue
        # Per-ticker best (n_mu, x_zero) by mean metric across bear_alloc & ema_pair
        agg = (
            df_1d.groupby(['ticker', 'n_mu', 'x_zero'])[metric].mean()
            .reset_index()
        )
        # For each ticker, find the (n_mu, x_zero) with highest metric
        # (or highest for negative metrics since -0.05 > -0.5)
        ascending = metric not in HIGHER_IS_BETTER and metric not in NEGATIVE_BETTER
        # Actually for NEGATIVE_BETTER we want highest (least negative), same as HIGHER
        agg = agg.sort_values(['ticker', metric], ascending=[True, ascending])
        first = agg.groupby('ticker').head(1)
        for _, r in first.iterrows():
            rows.append({
                'metric': metric, 'ticker': r['ticker'],
                'best_n_mu': r['n_mu'], 'best_x_zero': r['x_zero'],
                'value': r[metric],
            })
    sweet = pd.DataFrame(rows)
    sweet.to_csv(OUT_DIR / 'sweet_spots_per_metric.csv', index=False)
    print(f'  -> {OUT_DIR}/sweet_spots_per_metric.csv ({len(sweet)} rows)')

    # ---------- Sweet spot counts (vanilla check) ----------
    vanilla = sweet[(sweet['best_n_mu'] == 1) & (sweet['best_x_zero'] == 1.0)]
    print(f'\nVANILLA (n_mu=1, x=1.0) is sweet spot for '
          f'{vanilla["ticker"].nunique()}/{df_1d["ticker"].nunique()} tickers')
    print('Tickers preferring vanilla per metric:')
    for metric, label in METRICS.items():
        sub = vanilla[vanilla['metric'] == metric]
        if len(sub):
            print(f'  {label}: {", ".join(sorted(sub["ticker"].unique()))}')

    print(f'\nAll plots written to {OUT_DIR}/')


if __name__ == '__main__':
    main()