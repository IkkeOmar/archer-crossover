"""Generate improved equity plots with log-scale option and clear annotations."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import fetch_yfinance
from src.archer_engine import backtest_arrows, vanilla_ema_cross, buy_and_hold

tickers = {
    'SPY': ('2015-01-01', '2024-12-31'),
    'BTC-USD': ('2018-01-01', '2024-12-31'),
}

ARCHER = {'n_mu': 3, 'x_zero': 0.75, 'fast_period': 9, 'slow_period': 21, 'bear_alloc': 1.0}
plots_dir = Path('results/plots/equity')
plots_dir.mkdir(parents=True, exist_ok=True)

for tk, (start, end) in tickers.items():
    df = fetch_yfinance(tk, '1d', start=start, end=end)
    prices = np.asarray(df['close'].values, dtype=np.float64)

    bh = buy_and_hold(prices)
    van = vanilla_ema_cross(prices, fast_period=9, slow_period=21)
    arch = backtest_arrows(prices, **ARCHER)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: linear scale (same as before but with annotations)
    ax = axes[0]
    ax.plot(bh.equity, label=f'Buy & Hold: +{bh.total_return*100:.0f}%', linewidth=2, alpha=0.7)
    ax.plot(van.equity, label=f'Vanilla 9/21: +{van.total_return*100:.0f}%', linewidth=2, alpha=0.7)
    ax.plot(arch.equity, label=f'Archer n=3,x=0.75: +{arch.total_return*100:.0f}%', linewidth=2, alpha=0.7)
    ax.set_title(f'{tk} 1d -- Linear scale ({start[:4]} to {end[:4]})')
    ax.set_ylabel('Equity ($)')
    ax.set_xlabel('Trading days')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3)

    # Right: log scale (more honest comparison when returns vary wildly)
    ax = axes[1]
    # Avoid log(0) by clipping to small positive
    bh_eq = np.maximum(bh.equity, 1)
    van_eq = np.maximum(van.equity, 1)
    arch_eq = np.maximum(arch.equity, 1)
    ax.plot(bh_eq, label=f'Buy & Hold: +{bh.total_return*100:.0f}%', linewidth=2, alpha=0.7)
    ax.plot(van_eq, label=f'Vanilla 9/21: +{van.total_return*100:.0f}%', linewidth=2, alpha=0.7)
    ax.plot(arch_eq, label=f'Archer n=3,x=0.75: +{arch.total_return*100:.0f}%', linewidth=2, alpha=0.7)
    ax.set_yscale('log')
    ax.set_title(f'{tk} 1d -- Log scale (more honest at high returns)')
    ax.set_ylabel('Equity ($) log scale')
    ax.set_xlabel('Trading days')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3, which='both')

    plt.tight_layout()
    out = plots_dir / f'equity_{tk}_1d_log.png'
    plt.savefig(out, dpi=130)
    plt.close()
    print(f'  {out}')

    # Also generate a "fairer" BTC plot: cap at the same scale as B&H
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(bh.equity, label=f'Buy & Hold: +{bh.total_return*100:.0f}%', linewidth=2.5, alpha=0.8)
    ax.plot(arch.equity, label=f'Archer n=3,x=0.75: +{arch.total_return*100:.0f}%', linewidth=2.5, alpha=0.8)
    # Vanilla scaled to B&H's end value for visual comparison of *path*
    van_scaled = bh.equity[-1] * van.equity / van.equity[-1]
    ax.plot(van_scaled, label=f'Vanilla 9/21 (rescaled): shape +{(van.equity[-1]/van.equity[0]-1)*100:.0f}%', linewidth=2.5, alpha=0.5, linestyle='--')
    ax.set_title(f'{tk} 1d Equity -- showing path comparison\nVanilla shown rescaled to B&H endpoint (dashed) for shape comparison')
    ax.set_ylabel('Equity ($)')
    ax.set_xlabel('Trading days')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    out = plots_dir / f'equity_{tk}_1d_rescaled.png'
    plt.savefig(out, dpi=130)
    plt.close()
    print(f'  {out}')

print('\nDone.')
