"""Track per-trade PnL for long vs short positions.

For each entry/exit pair, compute realized PnL. Group by long vs short.
This tells us: when Archer goes short, does it make money or lose money?
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import load_one
from src.archer_engine import backtest_arrows

def per_trade_pnl(prices, position, cost_bps=5.0):
    """Compute realized PnL per completed trade."""
    pos = np.asarray(position, dtype=np.int64)
    p = np.asarray(prices, dtype=np.float64)
    n = len(p)

    trades = []
    entry_idx = None
    entry_price = None
    direction = None

    cost = cost_bps / 10000.0

    for t in range(n):
        if pos[t] != direction:
            # Direction change
            if entry_idx is not None and direction != 0:
                exit_price = p[t]
                if direction == 1:  # long
                    pnl_pct = (exit_price - entry_price) / entry_price - 2 * cost
                else:  # short
                    pnl_pct = (entry_price - exit_price) / entry_price - 2 * cost
                trades.append({
                    'entry_idx': entry_idx,
                    'exit_idx': t,
                    'direction': 'long' if direction == 1 else 'short',
                    'entry_price': float(entry_price),
                    'exit_price': float(exit_price),
                    'pnl_pct': float(pnl_pct),
                    'bars_held': t - entry_idx,
                })
            if pos[t] != 0:
                entry_idx = t
                entry_price = p[t]
                direction = pos[t]
            else:
                entry_idx = None
                entry_price = None
                direction = None

    return pd.DataFrame(trades)

ARCHER = {'n_mu': 3, 'x_zero': 0.75, 'fast_period': 9, 'slow_period': 21, 'bear_alloc': 1.0}

print('=== Per-trade PnL analysis: Archer n=3,x=0.75 ===\n')

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

    trades = per_trade_pnl(prices, arch.position)
    if len(trades) == 0:
        print(f'{tk}: no trades')
        continue

    long_trades = trades[trades['direction'] == 'long']
    short_trades = trades[trades['direction'] == 'short']

    print(f'{tk} ({len(trades)} total trades):')
    print(f'  LONG trades ({len(long_trades)}):')
    print(f'    Win rate:  {(long_trades["pnl_pct"] > 0).mean()*100:.0f}%')
    print(f'    Mean PnL:  {long_trades["pnl_pct"].mean()*100:+.2f}% per trade')
    print(f'    Sum PnL:   {long_trades["pnl_pct"].sum()*100:+.1f}% cumulative')
    print(f'    Avg hold:  {long_trades["bars_held"].mean():.0f} bars')
    print(f'  SHORT trades ({len(short_trades)}):')
    print(f'    Win rate:  {(short_trades["pnl_pct"] > 0).mean()*100:.0f}%')
    print(f'    Mean PnL:  {short_trades["pnl_pct"].mean()*100:+.2f}% per trade')
    print(f'    Sum PnL:   {short_trades["pnl_pct"].sum()*100:+.1f}% cumulative')
    print(f'    Avg hold:  {short_trades["bars_held"].mean():.0f} bars')
    print()

# Aggregate summary
print('=== AGGREGATE SUMMARY ===')
all_long_winrates = []
all_short_winrates = []
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
    trades = per_trade_pnl(prices, arch.position)
    if len(trades) > 0:
        all_long_winrates.append((trades[trades['direction']=='long']['pnl_pct'] > 0).mean())
        all_short_winrates.append((trades[trades['direction']=='short']['pnl_pct'] > 0).mean())

print(f'Mean long  win rate across 4 tickers:  {np.mean(all_long_winrates)*100:.0f}%')
print(f'Mean short win rate across 4 tickers:  {np.mean(all_short_winrates)*100:.0f}%')
