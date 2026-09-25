"""archer_ema_baselines.py — Run Archer sweep on the same EMA ranges as vanilla.

Compares Archer-Crossover at (n_mu=1, x=1.0) — the "data-preferred" vanilla
sweet spot — across the same EMA pairs as the vanilla baseline:

  9/21, 12/26, 20/50, 50/100, 100/200, 200/400, 400/800

For each pair, runs BOTH:
  - vanilla EMA-cross (n_mu=0, x=1.0 in our parameterization; uses bear_alloc=1.0)
  - Archer-Crossover at the data-preferred sweet spot (n_mu=1, x=1.0, bear_alloc=1.0)

Plus a couple of mid-grid Archer cells (n_mu=5, x=0.5) for context.

Output:
  results/archer_vs_vanilla_by_ema.csv — flat comparison table
  results/archer_vs_vanilla_summary.txt — text summary

This answers Omar's question: does Archer's stochastic delay add anything
on top of a 50/100 or 100/200 EMA-cross, or is 9/21 + Archer best because
we never tested the larger ranges with Archer?
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from archer_engine import backtest_arrows, buy_and_hold  # noqa: E402

DATA_DIR = Path('data')

EMA_PAIRS = [
    (9, 21),
    (12, 26),
    (20, 50),
    (50, 100),
    (100, 200),
    (200, 400),
    (400, 800),
]

# Archer sweet-spot + 1 mid cell for context. n_mu=0 with x=1.0 IS vanilla
# (no delay), so we use the same engine for both. We add it explicitly to
# ensure consistent cost model / warmup across pairs.
ARCHER_CELLS = [
    (1, 1.0),     # data-preferred sweet spot (effectively "no delay, immediate enter")
    (5, 0.5),     # mid-cell with some stochastic delay
]

# All default = n_mu=1, x=1.0. We use the same engine. Bear alloc = 1.0 (long-only here,
# since the paper tests bear_alloc=-1.0 elsewhere and we want a clean per-pair comparison).
BEAR_ALLOC = 1.0
COST_BPS = 5.0

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


def load_prices(ticker: str, fname: str) -> np.ndarray:
    path = DATA_DIR / fname
    if not path.exists():
        raise FileNotFoundError(f'No data for {ticker}: {path}')
    df = pd.read_csv(path, parse_dates=['date']).sort_values('date').reset_index(drop=True)
    # Prefer adj_close; fall back to close (used by crypto files)
    col = 'adj_close' if 'adj_close' in df.columns else 'close'
    return df[col].values.astype(np.float64)


def metrics(equity: np.ndarray) -> dict:
    eq = pd.Series(equity)
    rets = eq.pct_change().dropna()
    if len(rets) < 5 or rets.std() == 0 or np.isnan(rets.std()):
        return {'sharpe': np.nan, 'cagr': np.nan, 'max_dd': np.nan,
                'total_return': np.nan, 'num_trades': 0}
    # Annualized Sharpe
    sr = rets.mean() / rets.std(ddof=1) * np.sqrt(252)
    # CAGR
    years = len(eq) / 252
    cagr_v = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan
    # MaxDD
    running_max = eq.cummax()
    dd = (eq / running_max - 1).min()
    # Total return
    tot = eq.iloc[-1] / eq.iloc[0] - 1
    return {'sharpe': sr, 'cagr': cagr_v, 'max_dd': dd,
            'total_return': tot}


def main():
    rows = []
    for ticker, fname in TICKERS:
        try:
            prices = load_prices(ticker, fname)
        except FileNotFoundError as e:
            print(f'  {ticker:10s}: SKIP ({e})')
            continue
        print(f'\n=== {ticker} ({len(prices)} bars) ===')

        # B&H
        bnh = buy_and_hold(prices)
        m = metrics(bnh.equity)
        rows.append({'ticker': ticker, 'strategy': 'B&H', 'ema_pair': '-',
                     'n_mu': 0, 'x': 1.0, **m, 'num_trades': int(bnh.n_trades)})
        print(f'  B&H       : Sharpe={m["sharpe"]:+.3f} CAGR={m["cagr"]:+.2%} '
              f'MaxDD={m["max_dd"]:+.2%}')

        for (f, s) in EMA_PAIRS:
            # Skip pairs whose slow period exceeds available history (warmup = 3 * slow)
            min_bars = f * 3
            if len(prices) < min_bars + 100:  # need some trading after warmup
                print(f'  {f:>3d}/{s:<3d}: SKIP (insufficient history, {len(prices)} bars < {min_bars + 100})')
                continue

            # 1) Vanilla (n_mu=1, x=1.0 in our engine = immediate enter, no delay)
            t0 = time.time()
            bt = backtest_arrows(
                prices,
                n_mu=1, x_zero=1.0, sigma_n=1.0,
                bear_alloc=BEAR_ALLOC,
                fast_period=f, slow_period=s,
                cost_bps=COST_BPS, rng_seed=42,
            )
            eq_vanilla = bt.equity
            n_trades_v = int(bt.n_trades)
            m = metrics(eq_vanilla)
            rows.append({'ticker': ticker, 'strategy': 'EMA-cross', 'ema_pair': f'{f}/{s}',
                         'n_mu': 1, 'x': 1.0, **m, 'num_trades': n_trades_v})
            print(f'  {f:>3d}/{s:<3d} vanilla: Sharpe={m["sharpe"]:+.3f} CAGR={m["cagr"]:+.2%} '
                  f'MaxDD={m["max_dd"]:+.2%} trades={n_trades_v}')

            # 2) Archer at mid-cell (n_mu=5, x=0.5) — gives the strategy some delay
            bt = backtest_arrows(
                prices,
                n_mu=ARCHER_CELLS[1][0], x_zero=ARCHER_CELLS[1][1], sigma_n=2.5,
                bear_alloc=BEAR_ALLOC,
                fast_period=f, slow_period=s,
                cost_bps=COST_BPS, rng_seed=42,
            )
            eq_archer = bt.equity
            n_trades_a = int(bt.n_trades)
            m = metrics(eq_archer)
            rows.append({'ticker': ticker, 'strategy': 'Archer (n=5,x=0.5)', 'ema_pair': f'{f}/{s}',
                         'n_mu': 5, 'x': 0.5, **m, 'num_trades': n_trades_a})
            print(f'  {f:>3d}/{s:<3d} Archer : Sharpe={m["sharpe"]:+.3f} CAGR={m["cagr"]:+.2%} '
                  f'MaxDD={m["max_dd"]:+.2%} trades={n_trades_a} '
                  f'({time.time()-t0:.1f}s)')

    df = pd.DataFrame(rows)
    out = Path('results/archer_vs_vanilla_by_ema.csv')
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f'\nWrote {len(df)} rows to {out}')

    # Summary
    print('\n=== Cross-ticker median Sharpe by EMA-pair × strategy ===')
    pivot = df.groupby(['strategy', 'ema_pair'])['sharpe'].median().unstack('strategy')
    pivot = pivot[['B&H', 'EMA-cross', 'Archer (n=5,x=0.5)']]
    print(pivot.round(3).to_string())

    print('\n=== Per-ticker best EMA pair by strategy (Sharpe) ===')
    for strat in ['EMA-cross', 'Archer (n=5,x=0.5)']:
        print(f'\n  [{strat}]')
        sub = df[df['strategy'] == strat]
        for t in sorted(sub['ticker'].unique()):
            t_sub = sub[sub['ticker'] == t].sort_values('sharpe', ascending=False).head(2)
            line = f'    {t:10s}: '
            for _, r in t_sub.iterrows():
                line += f'{r["ema_pair"]:>9s} Sharpe={r["sharpe"]:+.3f}  '
            print(line)

    # Save summary text
    summary_path = Path('results/archer_vs_vanilla_summary.txt')
    with open(summary_path, 'w') as fh:
        fh.write('Archer vs Vanilla across EMA-pair ranges\n')
        fh.write('=' * 70 + '\n\n')
        fh.write('Cross-ticker median Sharpe:\n')
        fh.write(pivot.round(3).to_string())
        fh.write('\n\nPer-ticker best pair (top-2 by Sharpe):\n')
        for strat in ['EMA-cross', 'Archer (n=5,x=0.5)']:
            fh.write(f'\n[{strat}]\n')
            sub = df[df['strategy'] == strat]
            for t in sorted(sub['ticker'].unique()):
                t_sub = sub[sub['ticker'] == t].sort_values('sharpe', ascending=False).head(2)
                line = f'  {t:10s}: '
                for _, r in t_sub.iterrows():
                    line += f'{r["ema_pair"]:>9s} Sharpe={r["sharpe"]:+.3f}  '
                fh.write(line + '\n')
    print(f'\nWrote summary to {summary_path}')


if __name__ == '__main__':
    main()
