"""synthetic.py — synthetic market generators for Phase 3 validation.

Tests whether the strategy exploits real market structure or just fits noise.

Generators:
- gbm: Geometric Brownian Motion (baseline random walk)
- block_bootstrap: resample blocks of historical returns (preserves volatility clustering)
- trending: constant drift + GBM
- mean_reverting: Ornstein-Uhlenbeck-style mean-reverting log-prices
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def gbm(
    n: int,
    mu: float = 0.0,
    sigma: float = 0.02,
    s0: float = 100.0,
    periods_per_year: float = 252.0,
    seed: int | None = None,
) -> pd.Series:
    """Geometric Brownian Motion: dS/S = mu*dt + sigma*dW.

    Args:
        n: number of periods to generate.
        mu: per-period drift (annualized = mu * sqrt(periods_per_year)? — no, raw per-period here).
        sigma: per-period volatility.
        s0: starting price.
        periods_per_year: for time-indexing.
        seed: numpy random seed.

    Returns:
        pd.Series of synthetic prices, indexed by business-day timestamps.
    """
    rng = np.random.default_rng(seed)
    returns = rng.normal(loc=mu, scale=sigma, size=n)
    prices = s0 * np.exp(np.cumsum(returns))
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(prices, index=idx, name="close")


def block_bootstrap(
    historical_returns: pd.Series,
    n: int,
    block_size: int = 20,
    seed: int | None = None,
) -> pd.Series:
    """Resample blocks of historical returns to create synthetic series.

    Preserves volatility clustering (which GBM does not).

    Args:
        historical_returns: pd.Series of log returns (or simple returns) from real data.
        n: number of periods to generate.
        block_size: number of consecutive returns per block (typical: 5-50).
        seed: numpy seed.

    Returns:
        pd.Series of synthetic prices starting at 100.
    """
    rng = np.random.default_rng(seed)
    returns = historical_returns.values
    out = []
    while len(out) < n:
        start = rng.integers(0, max(1, len(returns) - block_size))
        block = returns[start : start + block_size]
        out.extend(block)
    out = np.array(out[:n])
    prices = 100.0 * np.exp(np.cumsum(out))
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(prices, index=idx, name="close")


def trending(
    n: int,
    annual_drift: float = 0.08,
    annual_vol: float = 0.20,
    s0: float = 100.0,
    periods_per_year: float = 252.0,
    seed: int | None = None,
) -> pd.Series:
    """Constant positive drift + GBM noise. Tests if strategies do well on pure trends."""
    dt = 1.0 / periods_per_year
    mu = annual_drift * dt
    sigma = annual_vol * np.sqrt(dt)
    return gbm(n, mu=mu, sigma=sigma, s0=s0, seed=seed)


def mean_reverting(
    n: int,
    target_level: float = 100.0,
    speed: float = 0.05,
    sigma: float = 0.02,
    s0: float = 100.0,
    seed: int | None = None,
) -> pd.Series:
    """Ornstein-Uhlenbeck-style mean-reverting log-prices.

    dS = speed * (target - S) * dt + sigma * dW  (approximately)
    """
    rng = np.random.default_rng(seed)
    s = np.zeros(n)
    s[0] = s0
    for t in range(1, n):
        ds = speed * (target_level - s[t - 1]) + sigma * rng.normal()
        s[t] = s[t - 1] + ds
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(s, index=idx, name="close")


def regime_switching(
    n: int,
    regimes: list[dict] | None = None,
    transition_prob: float = 0.02,
    s0: float = 100.0,
    seed: int | None = None,
) -> pd.Series:
    """Markov-switching regime generator.

    Each regime has its own (mu, sigma). Switches with given probability per period.

    Args:
        regimes: list of dicts with keys 'mu', 'sigma'. Defaults to bull/bear/crash.
        transition_prob: per-period probability of switching to next regime.
    """
    if regimes is None:
        regimes = [
            {"mu": 0.001, "sigma": 0.010},  # bull: low vol, positive drift
            {"mu": -0.001, "sigma": 0.025},  # bear: high vol, negative drift
            {"mu": -0.005, "sigma": 0.040},  # crash: very high vol, strong negative
        ]
    rng = np.random.default_rng(seed)
    returns = np.zeros(n)
    current_regime = 0
    for t in range(n):
        if rng.random() < transition_prob:
            current_regime = (current_regime + 1) % len(regimes)
        r = regimes[current_regime]
        returns[t] = rng.normal(r["mu"], r["sigma"])
    prices = s0 * np.exp(np.cumsum(returns))
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(prices, index=idx, name="close")
