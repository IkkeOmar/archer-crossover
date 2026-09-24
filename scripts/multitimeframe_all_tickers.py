"""Multi-timeframe sweep for ALL 9 tickers (1d + 1h)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import load_one
from src.archer_engine import backtest_arrows, sweep_arrows

# All 9 tickers
TICKERS = ['SPY', 'QQQ', 'IWM', 'AAPL', 'GOOGL', 'BTC-USD', 'ETH-USD', 'GLD', 'SLV']

# Timeframes we have data for
TIMEFRAMES = ['1d', '1h']  # 15m, 4h not yet fetched

# Period aligned to 1d: 2015-2024 for non-crypto, 2018-2024 for crypto
START_NONCRYPTO = '2015-01-01'
END = '2024-12-31'

# Smaller grid for speed
ARCHER_GRID = {
    'n_mu': [1, 3, 5, 8, 12],
    'x': [0.25, 0.5, 0.75, 1.0],
}

CRYPTO_TICKERS = {'BTC-USD', 'ETH-USD'}

results = []
print(f'Running multi-timeframe sweep: {len(TICKERS)} tickers x {len(TIMEFRAMES)} timeframes')
print(f'Grid: {len(ARCHER_GRID["n_mu"])} x {len(ARCHER_GRID["x"])} x 1 ema_pair = {len(ARCHER_GRID["n_mu"])*len(ARCHER_GRID["x"])} combos\n')

t_start = time.time()
for tk in TICKERS:
    start = '2018-01-01' if tk in CRYPTO_TICKERS else START_NONCRYPTO
    for tf in TIMEFRAMES:
        try:
            if tf == '1h' and tk not in CRYPTO_TICKERS:
                # Use 730d file directly
                import pandas as pd
                safe_tk = tk.replace('-', '_')
                cache_path = Path('data') / f'{safe_tk}_1h_730d.csv'
                if cache_path.exists():
                    df = pd.read_csv(cache_path, parse_dates=['date'], index_col='date')
                else:
                    print(f'  {tk} {tf}: SKIP (no 1h cache)')
                    continue
            else:
                df = load_one(tk, tf)
            # Strip timezone for comparison
            if df.index.tz is not None:
                df = df.copy()
                df.index = df.index.tz_localize(None)
            df = df[(df.index >= start) & (df.index <= END)]
            if len(df) < 50:
                print(f'  {tk} {tf}: SKIP (only {len(df)} candles)')
                continue
            prices = np.asarray(df['close'].values, dtype=np.float64)

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

            # Archer ref (n=3, x=0.75)
            arch_ref_idx = (1, 2)  # n_mu index 1, x index 2
            arch_ref_sharpe = sharpe_grid[arch_ref_idx]
            arch_ref_return = sweep['total_return'][arch_ref_idx[0], arch_ref_idx[1], 0, 0]

            results.append({
                'ticker': tk,
                'timeframe': tf,
                'period': f'{start[:4]}-{END[:4]}',
                'n_candles': len(prices),
                'best_n_mu': int(best_n_mu),
                'best_x': float(best_x),
                'best_sharpe': float(best_sharpe),
                'best_total_return': float(best_return),
                'best_max_drawdown': float(best_dd),
                'archer_ref_n3_x075_sharpe': float(arch_ref_sharpe),
                'archer_ref_n3_x075_return': float(arch_ref_return),
                'runtime_s': elapsed,
            })
            print(f'  {tk:8s} {tf}: {len(prices):6d} candles, best Sharpe={best_sharpe:.2f} (n={best_n_mu}, x={best_x}), ref(3,0.75)={arch_ref_sharpe:.2f}, {elapsed:.2f}s')
        except Exception as e:
            print(f'  {tk} {tf}: FAIL ({e})')

total_time = time.time() - t_start
print(f'\nTotal runtime: {total_time:.1f}s')

df_results = pd.DataFrame(results)
df_results.to_csv('results/multitimeframe_all_tickers.csv', index=False)
print(f'\nSaved: results/multitimeframe_all_tickers.csv')

# Summary
print('\n=== SUMMARY ===')
for tf in TIMEFRAMES:
    sub = df_results[df_results['timeframe'] == tf]
    print(f'\n{tf}:')
    print(f'  Mean best Sharpe: {sub["best_sharpe"].mean():.2f}')
    print(f'  Median best Sharpe: {sub["best_sharpe"].median():.2f}')
    print(f'  Min best Sharpe: {sub["best_sharpe"].min():.2f}')
    print(f'  Max best Sharpe: {sub["best_sharpe"].max():.2f}')
    print(f'  All positive Sharpe: {(sub["best_sharpe"] > 0).all()}')
