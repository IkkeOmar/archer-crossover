"""aggregate_cluster.py — Compare cluster_local sweep with old 3d_corrected.csv.

Outputs:
- For each ticker: best Sharpe (in-sample & MC) with (n_mu, x, bear_alloc, ema_pair)
- Old vs new sweet spot per ticker
- Convergence check: do MC-validated sweet spots match in-sample sweet spots?
"""
import sys
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

OLD_CSV = Path('results/3d_corrected.csv')
NEW_DIR = Path('results/cluster_local')
OUT_DIR = Path('results/cluster_local')


def load_new():
    files = sorted(NEW_DIR.glob('*_1d.csv'))
    if not files:
        return None
    frames = []
    for f in files:
        df = pd.read_csv(f)
        df['timeframe'] = '1d'
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def best_in_sample(df):
    """Per ticker, find the (n_mu, x) with highest mean in-sample Sharpe
    (averaged over bear_alloc & ema_pair)."""
    grid = (
        df.groupby(['ticker', 'n_mu', 'x_zero'])['in_sample_sharpe'].mean()
        .reset_index()
    )
    return grid.loc[grid.groupby('ticker')['in_sample_sharpe'].idxmax()]


def best_mc(df):
    """Per ticker, find (n_mu, x) with highest mean MC Sharpe."""
    grid = (
        df.groupby(['ticker', 'n_mu', 'x_zero'])['mc_sharpe_mean'].mean()
        .reset_index()
    )
    return grid.loc[grid.groupby('ticker')['mc_sharpe_mean'].idxmax()]


def best_wf(df):
    """Per ticker, find (n_mu, x) with highest mean WF Sharpe."""
    grid = (
        df.groupby(['ticker', 'n_mu', 'x_zero'])['wf_mean_sharpe'].mean()
        .reset_index()
    )
    return grid.loc[grid.groupby('ticker')['wf_mean_sharpe'].idxmax()]


def main():
    new = load_new()
    if new is None:
        print('ERROR: no cluster_local CSVs found')
        sys.exit(1)

    print(f'Loaded {len(new)} rows from {new["ticker"].nunique()} tickers × 1d\n')

    # Sanity: bear_alloc dimension per ticker
    print('=== bear_alloc dimension (mean in-sample Sharpe per ticker × bear_alloc) ===')
    ba = (
        new.groupby(['ticker', 'bear_alloc'])['in_sample_sharpe'].mean()
        .unstack()
    )
    print(ba.round(3).to_string())
    print()

    # Sweet spots: 3 ways (in-sample, MC, WF)
    bi = best_in_sample(new)
    bm = best_mc(new)
    bw = best_wf(new)

    print('=== Best per ticker: in-sample Sharpe ===')
    for _, r in bi.iterrows():
        print(f'  {r.ticker:10s}: n_mu={int(r.n_mu):3d}, x={r.x_zero:.2f}, sharpe={r.in_sample_sharpe:.3f}')

    print('\n=== Best per ticker: MC mean Sharpe ===')
    for _, r in bm.iterrows():
        print(f'  {r.ticker:10s}: n_mu={int(r.n_mu):3d}, x={r.x_zero:.2f}, sharpe={r.mc_sharpe_mean:.3f}')

    print('\n=== Best per ticker: WF mean Sharpe ===')
    for _, r in bw.iterrows():
        print(f'  {r.ticker:10s}: n_mu={int(r.n_mu):3d}, x={r.x_zero:.2f}, sharpe={r.wf_mean_sharpe:.3f}')

    # Vanilla count
    def count_vanilla(b):
        return int(((b['n_mu'] == 1) & (b['x_zero'] == 1.0)).sum())

    print(f'\n=== VANILLA (n_mu=1, x=1.0) sweet spot count ===')
    print(f'  in-sample: {count_vanilla(bi)}/{len(bi)}')
    print(f'  MC mean:   {count_vanilla(bm)}/{len(bm)}')
    print(f'  WF mean:   {count_vanilla(bw)}/{len(bw)}')

    # Old comparison
    if OLD_CSV.exists():
        old = pd.read_csv(OLD_CSV)
        old_best = (
            old.groupby(['ticker', 'n_mu', 'x'])['sharpe'].mean()
            .reset_index()
            .loc[lambda d: d.groupby('ticker')['sharpe'].idxmax()]
        )
        print(f'\n=== OLD (pre-cluster, pre-accounting-fix?) best ===')
        for _, r in old_best.iterrows():
            print(f'  {r.ticker:10s}: n_mu={int(r.n_mu):3d}, x={r.x:.2f}, sharpe={r.sharpe:.3f}')

    # Save summary
    summary = bi.rename(columns={'in_sample_sharpe': 'best_in_sample_sharpe'})
    summary = summary.merge(
        bm.rename(columns={'mc_sharpe_mean': 'best_mc_sharpe'}),
        on=['ticker'], suffixes=('', '_mc')
    )
    summary = summary.loc[:, ~summary.columns.duplicated()]
    summary.to_csv(OUT_DIR / 'cluster_summary.csv', index=False)
    print(f'\nSummary saved: {OUT_DIR}/cluster_summary.csv')


if __name__ == '__main__':
    main()