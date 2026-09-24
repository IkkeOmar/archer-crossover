"""Sub-daily sweep: BTC 1h + ETH 1h med Archer-specifikt delay (2020-2024)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import load_one
from src.archer_engine import backtest_arrows, vanilla_ema_cross, buy_and_hold

# Filter: kun 2020-2024 for at matche 1d BTC test
def filter_dates(df, start='2020-01-01', end='2024-12-31'):
    return df[(df.index >= start) & (df.index <= end)]

df_btc = filter_dates(load_one('BTC-USD', '1h'))
df_eth = filter_dates(load_one('ETH-USD', '1h'))
print(f'BTC 1h (2020-2024): {len(df_btc)} candles')
print(f'ETH 1h (2020-2024): {len(df_eth)} candles')

ARCHER_PARAMS = {'n_mu': 3, 'x_zero': 0.75, 'fast_period': 9, 'slow_period': 21, 'bear_alloc': 1.0}

results = []
for tk, df in [('BTC-USD', df_btc), ('ETH-USD', df_eth)]:
    prices = df['close'].values
    print(f'\n=== {tk} 1h ({len(prices)} candles) ===')

    bh = buy_and_hold(prices)
    van = vanilla_ema_cross(prices, fast_period=9, slow_period=21, bear_alloc=1.0)

    t0 = time.time()
    arch = backtest_arrows(prices, **ARCHER_PARAMS)
    elapsed = time.time() - t0

    def mdd(result):
        eq = pd.Series(result.equity)
        if len(eq) < 2: return 0.0
        cm = eq.cummax()
        return float(((eq - cm) / cm).min())

    pos = pd.Series(arch.position)
    long_pct = (pos > 0).mean() * 100
    short_pct = (pos < 0).mean() * 100
    cash_pct = (pos == 0).mean() * 100

    print(f'  B&H:     ret={bh.total_return*100:+.1f}%, mdd={mdd(bh)*100:.1f}%, n_trades=1')
    print(f'  Vanilla: ret={van.total_return*100:+.1f}%, mdd={mdd(van)*100:.1f}%, n_trades={van.n_trades}')
    print(f'  Archer:  ret={arch.total_return*100:+.1f}%, mdd={mdd(arch)*100:.1f}%, n_trades={arch.n_trades}, time={elapsed:.2f}s')
    print(f'  Archer position: long={long_pct:.0f}%, short={short_pct:.0f}%, cash={cash_pct:.0f}%')

    results.append({
        'ticker': tk,
        'timeframe': '1h',
        'bh_return': bh.total_return,
        'van_return': van.total_return,
        'arch_return': arch.total_return,
        'bh_mdd': mdd(bh),
        'van_mdd': mdd(van),
        'arch_mdd': mdd(arch),
        'arch_long_pct': long_pct,
        'arch_short_pct': short_pct,
        'arch_cash_pct': cash_pct,
        'n_candles': len(prices),
    })

df_results = pd.DataFrame(results)
df_results.to_csv('results/subdaily_comparison.csv', index=False)
print(f'\nSaved: results/subdaily_comparison.csv')

# Tiny grid sweep on BTC 1h
print('\n=== Tiny grid sweep on BTC 1h ===')
from src.sweep import run_sweep_one, GRID_TINY

# Save filtered version to cache so sweep can find it
df_btc.to_csv('data/BTC-USD_1h.csv')
df_eth.to_csv('data/ETH-USD_1h.csv')

t0 = time.time()
sweep = run_sweep_one('BTC-USD', '1h', grid=GRID_TINY)
print(f'  Sweep done in {time.time()-t0:.2f}s')
df_sweep = sweep['df']
top5 = df_sweep.nlargest(5, 'sharpe')[['n_mu','x','bear_alloc_1d','ema_pair','sharpe','total_return','max_drawdown','num_trades']]
print(f'  Top 5:')
print(top5.to_string(index=False))
