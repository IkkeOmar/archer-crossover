"""Better hedge decomposition: track long-only and short-only equity separately.

For each bar:
- long_equity += pos[t-1] * ret[t]   (when pos>0, capture the up move)
- short_equity += (-pos[t-1]) * ret[t]  (when pos<0, capture -ret)

At end, we have:
- total equity = combined
- long_only equity = hypothetical if we had only taken long signals (cash otherwise)
- short_only equity = hypothetical if we had only taken short signals
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import load_one
from src.archer_engine import backtest_arrows

def hedge_decomposition_v2(prices, result):
    """Track long-only and short-only PnL separately.

    Returns dict with total_return, long_only_return, short_only_return,
    short_pnl_when_short (PnL during short-only periods).
    """
    pos = np.asarray(result.position, dtype=np.float64)
    p = np.asarray(prices, dtype=np.float64)
    n = len(p)

    rets = np.zeros(n)
    rets[1:] = (p[1:] - p[:-1]) / p[:-1]

    # Long-only equity: only enter long when pos=+1, cash otherwise (returns 0)
    long_signal = (pos[:-1] > 0).astype(float)
    long_rets = long_signal * rets[1:]
    long_only_total_return = float(np.prod(1 + long_rets) - 1)

    # Short-only equity: only enter short when pos=-1, cash otherwise
    short_signal = (pos[:-1] < 0).astype(float)
    short_rets = -short_signal * rets[1:]
    short_only_total_return = float(np.prod(1 + short_rets) - 1)

    # Combined: actual strategy
    combined_rets = pos[:-1] * rets[1:]
    combined_total_return = float(np.prod(1 + combined_rets) - 1)

    return {
        'combined': combined_total_return,
        'long_only': long_only_total_return,
        'short_only': short_only_total_return,
    }

ARCHER = {'n_mu': 3, 'x_zero': 0.75, 'fast_period': 9, 'slow_period': 21, 'bear_alloc': 1.0}

print('=== Hedge decomposition v2: Archer n=3,x=0.75 ===\n')

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

    decomp = hedge_decomposition_v2(prices, arch)

    pos = pd.Series(arch.position)
    long_pct = (pos > 0).mean() * 100
    short_pct = (pos < 0).mean() * 100

    records.append({
        'ticker': tk,
        'combined_return': decomp['combined'],
        'long_only_return': decomp['long_only'],
        'short_only_return': decomp['short_only'],
        'long_pct_time': long_pct,
        'short_pct_time': short_pct,
    })
    print(f'{tk:8s}:')
    print(f'  Combined:    {decomp["combined"]*100:+7.1f}%')
    print(f'  Long-only:   {decomp["long_only"]*100:+7.1f}%  (what if we only took long signals)')
    print(f'  Short-only:  {decomp["short_only"]*100:+7.1f}%  (what if we only took short signals)')
    print(f'  Time: {long_pct:.0f}% long, {short_pct:.0f}% short')
    print()

df_hedge = pd.DataFrame(records)
df_hedge.to_csv('results/hedge_decomposition_v2.csv', index=False)
print(f'Saved: results/hedge_decomposition_v2.csv')

# Insight: short_only tells us how much value the short signals add vs long-only baseline
print('\n=== Key insight ===')
print('If short_only > 0, the short signals captured real bear-market downside.')
print('If short_only < 0, the short signals lost money and were a drag.')
print()
for _, r in df_hedge.iterrows():
    short_valuable = r['short_only_return'] > 0
    print(f"  {r['ticker']:8s}: short signals {'ADDED VALUE' if short_valuable else 'DRAGGED DOWN'} "
          f"(short-only return = {r['short_only_return']*100:+.1f}%)")
