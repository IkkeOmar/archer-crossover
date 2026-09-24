"""Hedge decomposition: how much does each side (long/short) contribute to total return?"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import load_one
from src.archer_engine import backtest_arrows

def hedge_decomposition(prices, result):
    """Decompose total return into long-PnL and short-PnL contributions."""
    pos = np.asarray(result.position, dtype=np.float64)
    p = np.asarray(prices, dtype=np.float64)
    n = len(p)

    rets = np.zeros(n)
    rets[1:] = (p[1:] - p[:-1]) / p[:-1]

    long_pnl = np.sum(pos[:-1] * rets[1:])
    short_pnl = np.sum(-pos[:-1] * rets[1:])

    return long_pnl, short_pnl

ARCHER = {'n_mu': 3, 'x_zero': 0.75, 'fast_period': 9, 'slow_period': 21, 'bear_alloc': 1.0}

print('=== Hedge decomposition: Archer n=3,x=0.75 ===\n')

records = []
for tk, start, end in [
    ('SPY', '2015-01-01', '2024-12-31'),
    ('BTC-USD', '2018-01-01', '2024-12-31'),
    ('ETH-USD', '2018-01-01', '2024-12-31'),
    ('GLD', '2015-01-01', '2024-12-31'),
]:
    df = load_one(tk, '1d')
    df = df[(df.index >= start) & (df.index <= end)]
    prices = df['close'].values
    arch = backtest_arrows(prices, **ARCHER)

    long_pnl, short_pnl = hedge_decomposition(prices, arch)

    pos = pd.Series(arch.position)
    long_pct = (pos > 0).mean() * 100
    short_pct = (pos < 0).mean() * 100

    records.append({
        'ticker': tk,
        'arch_total_return': arch.total_return,
        'long_contribution': long_pnl,
        'short_contribution': short_pnl,
        'long_pct_time': long_pct,
        'short_pct_time': short_pct,
    })
    print(f'{tk:8s}: total={arch.total_return*100:+.1f}%  long={long_pnl*100:+.1f}%  short={short_pnl*100:+.1f}%')
    print(f'          long {long_pct:.0f}% of time, short {short_pct:.0f}% of time')

df_hedge = pd.DataFrame(records)
df_hedge['long_pnl_pct'] = df_hedge['long_contribution'] / df_hedge['arch_total_return'] * 100
df_hedge['short_pnl_pct'] = df_hedge['short_contribution'] / df_hedge['arch_total_return'] * 100
df_hedge.to_csv('results/hedge_decomposition.csv', index=False)
print(f'\nSaved: results/hedge_decomposition.csv')

print('\nKey insights:')
for _, r in df_hedge.iterrows():
    print(f"  {r['ticker']:8s}: {r['long_pnl_pct']:+.0f}% from long, {r['short_pnl_pct']:+.0f}% from short")

print(f"\nMean across 4 tickers:")
print(f"  Long contribution: {df_hedge['long_pnl_pct'].mean():+.0f}% of return")
print(f"  Short contribution: {df_hedge['short_pnl_pct'].mean():+.0f}% of return")
