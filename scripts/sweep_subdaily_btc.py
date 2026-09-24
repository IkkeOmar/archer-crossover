"""Dedikeret sub-daily sweep: BTC 1h 2020-2024 (43793 candles)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.archer_engine import backtest_arrows, vanilla_ema_cross, buy_and_hold, sweep_arrows

GRID_FULL = {
    'n_mu': [1, 3, 5, 8, 12, 18],
    'x': [0.0, 0.25, 0.5, 0.75, 1.0],
    'bear_alloc_1d': [1.0],   # sub-daily uses full long/short
    'ema_pairs': [(9, 21), (12, 26)],
}

# Load BTC 1h 2020-2024
from src.data_loader import load_one
df = load_one('BTC-USD', '1h')
df = df[(df.index >= '2020-01-01') & (df.index <= '2024-12-31')]
prices = df['close'].values
print(f'BTC 1h 2020-2024: {len(prices)} candles')

n_mu_grid = np.array(GRID_FULL['n_mu'])
x_grid = np.array(GRID_FULL['x'])
ema_pairs = GRID_FULL['ema_pairs']

# Run sweep per EMA pair
all_results = []
for fast, slow in ema_pairs:
    print(f'\nRunning sweep EMA {fast}/{slow}...')
    t0 = time.time()
    results = sweep_arrows(
        prices,
        n_mu_grid=n_mu_grid,
        x_grid=x_grid,
        bear_alloc_grid=np.array([1.0]),
        ema_pairs=[(fast, slow)],
        cost_bps=5.0,
    )
    elapsed = time.time() - t0
    print(f'  Done in {elapsed:.2f}s')

    sharpe = results['sharpe'][:, :, 0, 0]
    total_ret = results['total_return'][:, :, 0, 0]
    max_dd = results['max_drawdown'][:, :, 0, 0]
    n_trades = results['num_trades'][:, :, 0, 0]

    for i, n_mu in enumerate(n_mu_grid):
        for j, x in enumerate(x_grid):
            all_results.append({
                'ticker': 'BTC-USD',
                'timeframe': '1h',
                'n_mu': int(n_mu),
                'x': float(x),
                'ema_pair': f'{fast}/{slow}',
                'sharpe': float(sharpe[i, j]),
                'total_return': float(total_ret[i, j]),
                'max_drawdown': float(max_dd[i, j]),
                'num_trades': int(n_trades[i, j]),
            })

df_sweep = pd.DataFrame(all_results)
df_sweep.to_csv('results/sweep_BTC-USD_1h.csv', index=False)
print(f'\nSaved: results/sweep_BTC-USD_1h.csv ({len(df_sweep)} rows)')

# Print top 10
print('\nTop 10 by Sharpe:')
top10 = df_sweep.nlargest(10, 'sharpe')[['n_mu','x','ema_pair','sharpe','total_return','max_drawdown','num_trades']]
print(top10.to_string(index=False))

# Summary
print('\nSummary:')
print(f'  Best Sharpe: {df_sweep["sharpe"].max():.2f}')
print(f'  Median Sharpe: {df_sweep["sharpe"].median():.2f}')
print(f'  Worst Sharpe: {df_sweep["sharpe"].min():.2f}')
print(f'  Mean total_return: {df_sweep["total_return"].mean()*100:.1f}%')
