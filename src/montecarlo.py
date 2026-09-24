"""montecarlo.py -- Monte Carlo over delay sampling seeds.

Purpose: For a fixed parameter combo, run N backtests with different RNG seeds.
If the resulting Sharpe distribution is tight (low std), the strategy's edge is
robust to the random delay sampling. If wide, the edge may be noise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor

from . import archer_engine as ae


def _mc_single(args):
    """Run a single Monte Carlo iteration."""
    prices, params, seed = args
    rng_seed = int(seed)
    return ae.backtest_arrows(
        prices,
        n_mu=params["n_mu"],
        x_zero=params["x_zero"],
        fast_period=params["fast_period"],
        slow_period=params["slow_period"],
        bear_alloc=params.get("bear_alloc", 1.0),
        cost_bps=params.get("cost_bps", 5.0),
        initial_cash=params.get("initial_cash", 100_000.0),
        rng_seed=rng_seed,
    )


def monte_carlo_one(
    prices: np.ndarray,
    params: dict,
    n_sims: int = 100,
    base_seed: int = 42,
    n_jobs: int = 1,
) -> dict:
    """Run n_sims of the same Archer backtest with different RNG seeds.

    Args:
        prices: 1D price array.
        params: dict of fixed params (n_mu, x_zero, fast_period, slow_period, etc.).
        n_sims: number of Monte Carlo iterations.
        base_seed: base seed; sim i uses base_seed + i.
        n_jobs: number of parallel workers (1 = serial).

    Returns:
        Dict with arrays of total_return, sharpe, max_drawdown across sims,
        plus mean/std/min/max.
    """
    args = [(prices, params, base_seed + i) for i in range(n_sims)]

    if n_jobs <= 1:
        results = [_mc_single(a) for a in args]
    else:
        with ProcessPoolExecutor(max_workers=n_jobs) as pool:
            results = list(pool.map(_mc_single, args))

    total_returns = np.array([r.total_return for r in results])
    n_trades = np.array([r.n_trades for r in results])
    n_skipped = np.array([r.n_skipped for r in results])

    # Compute Sharpe for each
    sharpes = []
    max_dds = []
    for r in results:
        eq = pd.Series(r.equity)
        if len(eq) < 2:
            sharpes.append(np.nan)
            max_dds.append(np.nan)
            continue
        rets = eq.pct_change().fillna(0.0)
        ppy = 252.0  # assume daily for now
        if rets.std() > 0:
            sharpe = rets.mean() / rets.std() * np.sqrt(ppy)
        else:
            sharpe = 0.0
        sharpes.append(sharpe)
        cum_max = eq.cummax()
        drawdown = (eq - cum_max) / cum_max
        max_dds.append(float(drawdown.min()))

    sharpes = np.array(sharpes)
    max_dds = np.array(max_dds)

    return {
        "total_returns": total_returns,
        "sharpes": sharpes,
        "max_drawdowns": max_dds,
        "n_trades": n_trades,
        "n_skipped": n_skipped,
        "mean_total_return": float(total_returns.mean()),
        "std_total_return": float(total_returns.std()),
        "mean_sharpe": float(np.nanmean(sharpes)),
        "std_sharpe": float(np.nanstd(sharpes)),
        "median_sharpe": float(np.nanmedian(sharpes)),
        "min_sharpe": float(np.nanmin(sharpes)),
        "max_sharpe": float(np.nanmax(sharpes)),
        "ci95_sharpe": (
            float(np.nanpercentile(sharpes, 2.5)),
            float(np.nanpercentile(sharpes, 97.5)),
        ),
        "robust_sharpe": float(np.nanmean(sharpes) / np.nanstd(sharpes)) if np.nanstd(sharpes) > 0 else 0.0,
    }


def monte_carlo_many(
    prices: np.ndarray,
    params_list: list[dict],
    n_sims: int = 100,
    base_seed: int = 42,
    n_jobs: int = 1,
) -> list[dict]:
    """Run Monte Carlo for a list of parameter dicts."""
    return [
        monte_carlo_one(prices, p, n_sims=n_sims, base_seed=base_seed, n_jobs=n_jobs)
        for p in params_list
    ]
