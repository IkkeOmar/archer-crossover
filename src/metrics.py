"""metrics.py — risk-adjusted performance metrics.

Pure functions over pandas Series (equity curves). No I/O, no randomness.
All metrics handle empty arrays gracefully (return NaN).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def total_return(equity: pd.Series) -> float:
    """Total cumulative return: equity[-1] / equity[0] - 1.

    Args:
        equity: pd.Series indexed by time, values monotonically non-decreasing.

    Returns:
        Total return as fraction (e.g. 0.45 for 45% gain).
    """
    if len(equity) < 2 or equity.iloc[0] == 0:
        return float("nan")
    return float(equity.iloc[-1] / equity.iloc[0] - 1.0)


def cagr(equity: pd.Series, periods_per_year: float = 252.0) -> float:
    """Compound Annual Growth Rate.

    Args:
        equity: equity curve.
        periods_per_year: 252 for daily, 252*7 for 4h market hours, etc.

    Returns:
        CAGR as fraction.
    """
    if len(equity) < 2 or equity.iloc[0] <= 0 or equity.iloc[-1] <= 0:
        return float("nan")
    n_periods = len(equity)
    years = n_periods / periods_per_year
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)


def max_drawdown(equity: pd.Series) -> float:
    """Maximum peak-to-trough drawdown.

    Returns:
        Max DD as a negative fraction (e.g. -0.35 for 35% drawdown).
    """
    if len(equity) < 2:
        return float("nan")
    running_max = equity.cummax()
    drawdowns = equity / running_max - 1.0
    return float(drawdowns.min())


def sharpe(returns: pd.Series, rf_per_period: float = 0.0, periods_per_year: float = 252.0) -> float:
    """Annualized Sharpe ratio (no risk-free rate by default).

    Args:
        returns: per-period returns (not cumulative).
        rf_per_period: risk-free per period. Set to daily risk-free (~0.0001 for 2.5%/yr).
        periods_per_year: number of periods per year for annualization.

    Returns:
        Annualized Sharpe.
    """
    if len(returns) < 2:
        return float("nan")
    excess = returns - rf_per_period
    std = excess.std(ddof=1)
    if std == 0 or np.isnan(std):
        return float("nan")
    return float(excess.mean() / std * math.sqrt(periods_per_year))


def sortino(returns: pd.Series, rf_per_period: float = 0.0, periods_per_year: float = 252.0) -> float:
    """Annualized Sortino ratio (downside deviation only).

    Returns:
        Annualized Sortino, or NaN if no downside variation.
    """
    if len(returns) < 2:
        return float("nan")
    excess = returns - rf_per_period
    downside = excess[excess < 0]
    if len(downside) < 2:
        return float("nan")
    downside_std = downside.std(ddof=1)
    if downside_std == 0:
        return float("nan")
    return float(excess.mean() / downside_std * math.sqrt(periods_per_year))


def calmar(cagr_val: float, max_dd_val: float) -> float:
    """Calmar ratio: CAGR / |max DD|.

    Returns:
        Calmar ratio. NaN if max DD is 0 or NaN.
    """
    if max_dd_val is None or np.isnan(max_dd_val) or max_dd_val == 0:
        return float("nan")
    if cagr_val is None or np.isnan(cagr_val):
        return float("nan")
    return float(cagr_val / abs(max_dd_val))


def win_rate(trade_returns: pd.Series) -> float:
    """Fraction of trades with positive return.

    Args:
        trade_returns: per-trade P&L as a fraction (e.g. +0.02 = +2%).

    Returns:
        Win rate in [0, 1].
    """
    if len(trade_returns) == 0:
        return float("nan")
    return float((trade_returns > 0).sum() / len(trade_returns))


def num_trades(position_changes: pd.Series) -> int:
    """Count number of position changes (entries + exits).

    Args:
        position_changes: pd.Series of position sizes (-1, 0, +1 typically).

    Returns:
        Count of nonzero changes.
    """
    if len(position_changes) < 2:
        return 0
    diff = position_changes.diff().fillna(0)
    return int((diff != 0).sum())


def all_metrics(
    equity: pd.Series,
    returns: pd.Series,
    position: pd.Series,
    periods_per_year: float = 252.0,
) -> dict:
    """Compute full metrics dict for one backtest.

    Args:
        equity: equity curve over time.
        returns: per-period returns (equity.pct_change().dropna() or similar).
        position: position sizes over time.
        periods_per_year: for annualization.

    Returns:
        Dict with keys: total_return, cagr, sharpe, sortino, max_drawdown, calmar, win_rate, num_trades.
    """
    eq_ret = total_return(equity)
    cagr_val = cagr(equity, periods_per_year)
    mdd = max_drawdown(equity)
    return {
        "total_return": eq_ret,
        "cagr": cagr_val,
        "sharpe": sharpe(returns, periods_per_year=periods_per_year),
        "sortino": sortino(returns, periods_per_year=periods_per_year),
        "max_drawdown": mdd,
        "calmar": calmar(cagr_val, mdd),
        "num_trades": num_trades(position),
        "n_periods": len(equity),
    }


def periods_per_year_for_timeframe(timeframe: str) -> float:
    """Map timeframe string to periods per year.

    Args:
        timeframe: '1d', '4h', '1h', '15m', '5m', '3m', '2m', '1m'.

    Returns:
        Approximate periods per year. Crypto = 24/7, stocks ~6.5h trading day.
    """
    tf = timeframe.lower()
    if tf == "1d":
        return 252.0  # US trading days
    if tf == "1wk":
        return 52.0
    if tf == "4h":
        return 252.0 * 6.5 / 4  # ~410 for stocks, ~2190 for crypto 24/7
    if tf == "1h":
        return 252.0 * 6.5  # ~1638 for stocks, ~8760 for crypto
    if tf == "15m":
        return 252.0 * 6.5 * 4  # ~6552 stocks, 35040 crypto
    if tf == "5m":
        return 252.0 * 6.5 * 12
    if tf == "3m":
        return 252.0 * 6.5 * 20
    if tf == "2m":
        return 252.0 * 6.5 * 30
    if tf == "1m":
        return 252.0 * 6.5 * 60
    raise ValueError(f"Unknown timeframe: {timeframe}")


def is_crypto(ticker: str) -> bool:
    """Return True if ticker is crypto (24/7 market)."""
    return ticker.upper().endswith("-USD") or "/" in ticker


def adjusted_periods_per_year(timeframe: str, ticker: str) -> float:
    """Periods per year, accounting for 24/7 vs. trading hours."""
    base = periods_per_year_for_timeframe(timeframe)
    if is_crypto(ticker):
        # 24/7 markets: scale up
        crypto_per_year = {
            "1d": 365.0,
            "4h": 365.0 * 6,
            "1h": 365.0 * 24,
            "15m": 365.0 * 24 * 4,
            "5m": 365.0 * 24 * 12,
            "3m": 365.0 * 24 * 20,
            "2m": 365.0 * 24 * 30,
            "1m": 365.0 * 24 * 60,
        }
        return crypto_per_year.get(timeframe.lower(), base)
    return base
