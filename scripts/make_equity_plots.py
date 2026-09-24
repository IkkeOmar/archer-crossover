"""Generate equity-curve comparison plots: Archer best vs. vanilla vs. buy-and-hold."""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import fetch_yfinance
from src.archer_engine import backtest_arrows, vanilla_ema_cross, buy_and_hold
from src.metrics import all_metrics, periods_per_year_for_timeframe

plots_dir = Path('results/plots/equity')
plots_dir.mkdir(parents=True, exist_ok=True)

TICKERS = {
    'SPY': ('2015-01-01', '2024-12-31'),
    'QQQ': ('2015-01-01', '2024-12-31'),
    'BTC-USD': ('2018-01-01', '2024-12-31'),
    'GLD': ('2015-01-01', '2024-12-31'),
}

# Best Archer params (from sweep): n_mu=3, x=0.75, bear_alloc=1.0, ema 9/21
ARCHER_PARAMS = {'n_mu': 3, 'x_zero': 0.75, 'fast_period': 9, 'slow_period': 21, 'bear_alloc': 1.0}

for tk, (start, end) in TICKERS.items():
    df = fetch_yfinance(tk, '1d', start=start, end=end)
    prices = np.asarray(df['close'].values, dtype=np.float64)

    bh = buy_and_hold(prices)
    van = vanilla_ema_cross(prices, fast_period=9, slow_period=21)
    arch = backtest_arrows(prices, **ARCHER_PARAMS)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(bh.equity, label=f'Buy & Hold (ret={bh.total_return*100:.0f}%)', linewidth=2, alpha=0.7)
    ax.plot(van.equity, label=f'Vanilla 9/21 (ret={van.total_return*100:.0f}%)', linewidth=2, alpha=0.7)
    ax.plot(arch.equity, label=f'Archer n=3,x=0.75 (ret={arch.total_return*100:.0f}%)', linewidth=2, alpha=0.7)
    ax.set_title(f'{tk} 1d equity curves -- {start[:4]} to {end[:4]}')
    ax.set_ylabel('Equity ($)')
    ax.set_xlabel('Trading days')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    out = plots_dir / f'equity_{tk}_1d.png'
    plt.savefig(out, dpi=130)
    plt.close()
    print(f'  {out}')

print('Done.')
