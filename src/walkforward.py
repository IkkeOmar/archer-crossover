"""walkforward.py -- Walk-forward validation across rolling train/test windows.

Method (D17): 252-day training window, 63-day testing window. Roll forward by 63 days.
For each window, run the sweep on the training data, pick the best params, then evaluate
those params on the test data. Aggregate: how often does the training winner generalize?
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import archer_engine as ae


def walk_forward_one(
    prices: np.ndarray,
    train_window: int = 252,
    test_window: int = 63,
    param_grid: list[dict] | None = None,
    cost_bps: float = 5.0,
) -> dict:
    """Run walk-forward validation on a single price series.

    Args:
        prices: 1D price array.
        train_window: training window size in periods.
        test_window: test window size in periods.
        param_grid: list of param dicts. Defaults to a small Archer grid.
        cost_bps: transaction cost.

    Returns:
        Dict with arrays of (window_idx, train_start, train_end, test_start, test_end,
        best_train_params, test_sharpe, test_return, test_max_dd).
    """
    if param_grid is None:
        # Small Archer grid: focus on (n_mu, x) with ema 9/21, bear_alloc=1.0
        param_grid = [
            {'n_mu': nm, 'x_zero': x, 'fast_period': 9, 'slow_period': 21, 'bear_alloc': 1.0}
            for nm in [1, 3, 5, 8, 12]
            for x in [0.25, 0.5, 0.75, 1.0]
        ]

    n = len(prices)
    results = []
    window_idx = 0
    train_start = 0
    while train_start + train_window + test_window <= n:
        train_end = train_start + train_window
        test_start = train_end
        test_end = min(test_start + test_window, n)

        train_prices = prices[train_start:train_end]
        test_prices = prices[test_start:test_end]

        # 1. Find best params on training data
        train_results = []
        for params in param_grid:
            res = ae.backtest_arrows(train_prices, **params, cost_bps=cost_bps)
            train_results.append({'params': params, 'sharpe': res.sharpe if hasattr(res, 'sharpe') else _compute_sharpe(res)})
        best = max(train_results, key=lambda r: r['sharpe'])
        best_params = best['params']
        train_best_sharpe = best['sharpe']

        # 2. Evaluate on test data
        test_res = ae.backtest_arrows(test_prices, **best_params, cost_bps=cost_bps)
        test_sharpe = _compute_sharpe(test_res)
        test_return = test_res.total_return

        # 3. Compute max DD for test window
        eq = pd.Series(test_res.equity)
        if len(eq) > 0:
            cum_max = eq.cummax()
            dd = (eq - cum_max) / cum_max
            test_max_dd = float(dd.min()) if len(dd) > 0 else 0.0
        else:
            test_max_dd = 0.0

        results.append({
            'window_idx': window_idx,
            'train_start': train_start,
            'train_end': train_end,
            'test_start': test_start,
            'test_end': test_end,
            'best_params': best_params,
            'train_sharpe': train_best_sharpe,
            'test_sharpe': test_sharpe,
            'test_return': test_return,
            'test_max_dd': test_max_dd,
            'n_test_periods': len(test_prices),
        })

        train_start += test_window
        window_idx += 1

    if not results:
        return {'results': [], 'summary': {}}

    df = pd.DataFrame(results)

    # Summary: how often does the train winner generalize?
    positive_test_sharpe = (df['test_sharpe'] > 0).mean()
    mean_test_sharpe = df['test_sharpe'].mean()
    mean_test_return = df['test_return'].mean()
    worst_test_return = df['test_return'].min()

    # Stability: how often do top-3 training params agree?
    # (For simplicity, we just track param hash)
    from collections import Counter
    param_counts = Counter(tuple(sorted(p.items())) for p in df['best_params'])
    most_common = param_counts.most_common(1)[0]
    param_consistency = most_common[1] / len(df)

    summary = {
        'n_windows': len(df),
        'positive_test_sharpe_frac': float(positive_test_sharpe),
        'mean_test_sharpe': float(mean_test_sharpe),
        'mean_test_return': float(mean_test_return),
        'worst_test_return': float(worst_test_return),
        'most_common_params': dict(most_common[0]),
        'most_common_params_count': int(most_common[1]),
        'param_consistency': float(param_consistency),
    }

    return {'results': df, 'summary': summary}


def _compute_sharpe(result):
    """Compute Sharpe from a BacktestResult."""
    eq = pd.Series(result.equity)
    if len(eq) < 2:
        return 0.0
    rets = eq.pct_change().fillna(0.0)
    if rets.std() == 0:
        return 0.0
    ppy = 252.0
    return float(rets.mean() / rets.std() * np.sqrt(ppy))
