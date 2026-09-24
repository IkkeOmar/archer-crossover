"""Multi-timeframe sweep: 1h vs 1d for BTC and ETH.
Compare Archer performance across timeframes."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import load_one
from src.archer_engine import backtest_arrows, sweep_arrows

# Period: 2020-2024 (5 years) for fair comparison
START = '2020-01-01'
END = '2024-12-31'

ARCHER_GRID = {
    'n_mu': [1, 3, 5, 8, 12],
    'x': [0.25, 0.5, 0.75, 1.0],
}

results = []
for tk in ['BTC-USD', 'ETH-USD']:
    for tf in ['1h', '1d']:
        df = load_one(tk, tf)
        df = df[(df.index >= START) & (df.index <= END)]
        prices = df['close'].values

        # Archer n=3,x=0.75 reference
        arch_ref = backtest_arrows(prices, n_mu=3, x_zero=0.75, fast_period=9, slow_period=21, bear_alloc=1.0)

        # Compute max DD from equity
        eq = pd.Series(arch_ref.equity)
        if len(eq) > 1:
            arch_ref_mdd = float(((eq - eq.cummax()) / eq.cummax()).min())
        else:
            arch_ref_mdd = 0.0

        # Tiny sweep
        t0 = time.time()
        sweep = sweep_arrows(
            prices,
            n_mu_grid=np.array(ARCHER_GRID['n_mu']),
            x_grid=np.array(ARCHER_GRID['x']),
            bear_alloc_grid=np.array([1.0]),
            ema_pairs=[(9, 21)],
            cost_bps=5.0,
        )
        elapsed = time.time() - t0

        sharpe_grid = sweep['sharpe'][:, :, 0, 0]
        best_idx = np.unravel_index(np.nanargmax(sharpe_grid), sharpe_grid.shape)
        best_n_mu = ARCHER_GRID['n_mu'][best_idx[0]]
        best_x = ARCHER_GRID['x'][best_idx[1]]
        best_sharpe = sharpe_grid[best_idx]
        best_return = sweep['total_return'][best_idx[0], best_idx[1], 0, 0]
        best_dd = sweep['max_drawdown'][best_idx[0], best_idx[1], 0, 0]

        pos = pd.Series(arch_ref.position)
        long_pct = (pos > 0).mean() * 100
        short_pct = (pos < 0).mean() * 100
        cash_pct = (pos == 0).mean() * 100

        print(f'{tk} {tf}: {len(prices)} candles, sweep {elapsed:.2f}s')
        print(f'  Best: n_mu={best_n_mu}, x={best_x}, Sharpe={best_sharpe:.2f}, ret={best_return*100:+.1f}%, mdd={best_dd*100:.1f}%')
        print(f'  Archer ref (n=3,x=0.75): ret={arch_ref.total_return*100:+.1f}%, mdd={arch_ref.max_drawdown*100:.1f}%')
        print(f'  Position: {long_pct:.0f}% long, {short_pct:.0f}% short, {cash_pct:.0f}% cash')

        results.append({
            'ticker': tk,
            'timeframe': tf,
            'n_candles': len(prices),
            'best_n_mu': best_n_mu,
            'best_x': best_x,
            'best_sharpe': float(best_sharpe),
            'best_total_return': float(best_return),
            'best_max_drawdown': float(best_dd),
            'archer_ref_return': arch_ref.total_return,
            'archer_ref_sharpe': float(sweep['sharpe'][1, 2, 0, 0]),  # n_mu=3, x=0.75
            'long_pct_time': long_pct,
            'short_pct_time': short_pct,
            'cash_pct_time': cash_pct,
            'sweep_runtime_s': elapsed,
        })
        print()

df_results = pd.DataFrame(results)
df_results.to_csv('results/multitimeframe_comparison.csv', index=False)
print(f'Saved: results/multitimeframe_comparison.csv')

# Summary
print('=== MULTI-TIMEFRAME SUMMARY (2020-2024) ===\n')
for _, r in df_results.iterrows():
    print(f"{r['ticker']} {r['timeframe']}: best Sharpe={r['best_sharpe']:.2f} (n={r['best_n_mu']}, x={r['best_x']})")
    print(f"  Archer ref: ret={r['archer_ref_return']*100:+.1f}%")
    print(f"  {r['long_pct_time']:.0f}% long, {r['short_pct_time']:.0f}% short, {r['cash_pct_time']:.0f}% cash")
    print()
