"""ema_baselines.py — Run plain EMA-cross baselines at multiple timeframes.

For each ticker (9) x each EMA pair (9/21, 50/100, 100/200, 200/400, 400/800):
compute the same 12 metrics as the Archer sweep, plus buy-and-hold.

Output: results/ema_baselines.csv + a summary table.
"""
from __future__ import annotations

import sys
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from archer_engine import vanilla_ema_cross, buy_and_hold  # noqa: E402
from metrics import (  # noqa: E402
    sharpe, sortino, calmar, max_drawdown, total_return, cagr,
    win_rate, avg_win_loss, profit_factor, skewness, std_returns, mean_return,
)

DATA_DIR = Path('data')
OUT_CSV = Path('results/ema_baselines.csv')

EMA_PAIRS = [
    (9, 21),
    (50, 100),
    (100, 200),
    (200, 400),
    (400, 800),
]

# Map data file names. Prefer the explicit 2015-2024 daily files; fall back to plain.
TICKERS = [
    ('SPY', 'SPY_1d_2015-01-01_2024-12-31.csv'),
    ('QQQ', 'QQQ_1d_2015-01-01_2024-12-31.csv'),
    ('IWM', 'IWM_1d_2015-01-01_2024-12-31.csv'),
    ('AAPL', 'AAPL_1d_2015-01-01_2024-12-31.csv'),
    ('GOOGL', 'GOOGL_1d_2015-01-01_2024-12-31.csv'),
    ('GLD', 'GLD_1d_2015-01-01_2024-12-31.csv'),
    ('SLV', 'SLV_1d_2015-01-01_2024-12-31.csv'),
    ('BTC-USD', 'BTC_USD_1d_2015-01-01_2024-12-31.csv'),
    ('ETH-USD', 'ETH_USD_1d_2015-01-01_2024-12-31.csv'),
]


def load_prices(ticker: str, fname: str) -> pd.Series:
    path = DATA_DIR / fname
    if not path.exists():
        # Fallback: try alternate naming
        alts = list(DATA_DIR.glob(f'{ticker.replace("-", "_")}*1d*2015*.csv'))
        if alts:
            path = alts[0]
        else:
            raise FileNotFoundError(f'No data for {ticker}')
    df = pd.read_csv(path, parse_dates=['date']).sort_values('date').reset_index(drop=True)
    return df['adj_close']


def metrics_from_equity(equity: np.ndarray) -> dict:
    eq = pd.Series(equity)
    rets = eq.pct_change().dropna()
    if len(rets) < 5 or rets.std() == 0 or np.isnan(rets.std()):
        return {k: float('nan') for k in [
            'sharpe', 'sortino', 'calmar', 'max_dd', 'total_return',
            'cagr', 'win_rate', 'avg_win', 'avg_loss', 'profit_factor',
            'skewness', 'std_returns',
        ]}
    mdd = max_drawdown(eq)
    cagr_v = cagr(eq)
    return {
        'sharpe': sharpe(rets),
        'sortino': sortino(rets),
        'calmar': calmar(cagr_v, mdd),
        'max_dd': mdd,
        'total_return': total_return(eq),
        'cagr': cagr_v,
        'win_rate': win_rate(rets),
        'avg_win': avg_win_loss(rets)[0],
        'avg_loss': avg_win_loss(rets)[1],
        'profit_factor': profit_factor(rets),
        'skewness': skewness(rets),
        'std_returns': std_returns(rets),
    }


def main():
    rows = []
    for ticker, fname in TICKERS:
        prices = load_prices(ticker, fname)
        # B&H
        bnh = buy_and_hold(prices.values)
        bnh_m = metrics_from_equity(bnh.equity)
        bnh_m.update(ticker=ticker, strategy='B&H', ema_pair='-')
        rows.append(bnh_m)

        for (f, s) in EMA_PAIRS:
            # Skip 400/800 for short-history tickers? we have 10y daily data, so 800-period EMA warmup = ~3.2 years.
            # For SPY (2515 bars), 800-period EMA is computable but not meaningful for short trades.
            try:
                bt = vanilla_ema_cross(
                    prices.values,
                    fast_period=f, slow_period=s,
                    cost_bps=5.0, bear_alloc=-1.0,
                )
                m = metrics_from_equity(bt.equity)
                m.update(ticker=ticker, strategy=f'EMA-cross', ema_pair=f'{f}/{s}',
                         n_trades=int(bt.n_trades))
                rows.append(m)
                print(f'  {ticker:10s} {f:>3d}/{s:<3d}: Sharpe={m["sharpe"]:+.3f} '
                      f'CAGR={m["cagr"]:+.2%} MaxDD={m["max_dd"]:+.2%} '
                      f'trades={bt.n_trades}')
            except Exception as e:
                print(f'  {ticker:10s} {f:>3d}/{s:<3d}: ERROR {e}')

    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f'\nWrote {len(df)} rows to {OUT_CSV}')

    # Cross-ticker median summary
    print('\n=== Cross-ticker median by strategy ===')
    cross = df.groupby(['strategy', 'ema_pair'])[['sharpe', 'calmar', 'max_dd', 'total_return', 'cagr']].median()
    print(cross.round(3).to_string())

    print('\n=== Per-ticker best EMA pair (by Sharpe) ===')
    ema_only = df[df['strategy'] == 'EMA-cross'].copy()
    for t in sorted(ema_only['ticker'].unique()):
        sub = ema_only[ema_only['ticker'] == t].sort_values('sharpe', ascending=False).head(3)
        line = f'  {t:10s}: '
        for _, r in sub.iterrows():
            line += f'{r["ema_pair"]:>9s} Sharpe={r["sharpe"]:+.3f}  '
        print(line)


if __name__ == '__main__':
    main()
