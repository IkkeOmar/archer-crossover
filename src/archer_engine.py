"""archer_engine.py — vectorized EMA-crossover backtest with stochastic delay.

This is the core of the experiment. Two layers:

1. vectorized_backtest(prices, n_mu, x, sigma_n, bear_alloc_1d, ema_pair) -> equity, position, trades
   - Single (n_mu, x, ...) parameter combination
   - Returns the equity curve + position series + trade log

2. vectorized_sweep(prices, n_mu_grid, x_grid, ...) -> 2D/3D array of metrics
   - All parameter combinations at once
   - Uses numpy broadcasting to avoid Python loops

The stochastic delay: when EMA fast crosses slow (direction determined at cross time),
we sample a delay n ~ mixture of (delta at 0 with prob x) and (|N(mu_n, sigma_n)| rounded with prob 1-x).
After waiting n candles, we verify the cross direction is still valid (fast EMA still on same side).
If yes, enter position per timeframe rule. If no, skip the signal.

Position rule (configurable):
- 1d: bullish=+1.0, bearish in {0, -0.5, -0.75, -1.0} (configurable; never below -1)
- sub-daily: bullish=+1.0, bearish=-1.0

Cost: cost_bps per round-trip (entry + exit). Applied at position change.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


# ---------------- helpers ----------------


def ema(series: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average, with first valid value = series[0].

    Uses standard EMA: EMA[t] = alpha*x[t] + (1-alpha)*EMA[t-1]
    where alpha = 2/(period+1).

    Output has same length as input. EMA[0:period-1] are NaN until enough history.
    """
    n = len(series)
    out = np.full(n, np.nan, dtype=np.float64)
    if period <= 0 or period > n:
        return out
    alpha = 2.0 / (period + 1.0)
    # Seed with simple mean of first `period` values
    seed = float(np.mean(series[:period]))
    out[period - 1] = seed
    for i in range(period, n):
        out[i] = alpha * series[i] + (1.0 - alpha) * out[i - 1]
    return out


def ema_vectorized(series: np.ndarray, period: int) -> np.ndarray:
    """Faster EMA using pandas ewm (engine='numba' if available, else plain).

    Returns NaN for indices < period-1.
    """
    if period <= 0:
        return np.full_like(series, np.nan)
    s = pd.Series(series)
    out = s.ewm(span=period, adjust=False).mean().values
    out = np.asarray(out, dtype=np.float64)
    out[: period - 1] = np.nan
    return out


# ---------------- single-combo backtest ----------------


@dataclass
class BacktestResult:
    equity: np.ndarray           # length T, equity curve starting at 1.0
    position: np.ndarray         # length T, position size [-1, 1]
    n_trades: int
    total_return: float
    n_skipped: int               # signals skipped due to verify-fail


def sample_delay(
    rng: np.random.Generator,
    n_signals: int,
    n_mu: int,
    sigma_n: float,
    x_zero: float,
) -> np.ndarray:
    """Sample delay for each signal.

    Returns array of int delays (>= 0). Each signal independently:
    - with probability x_zero -> 0
    - else -> max(1, round(|N(n_mu, sigma_n)|))
    """
    if n_signals == 0:
        return np.zeros(0, dtype=np.int64)
    use_zero = rng.random(n_signals) < x_zero
    gauss = np.abs(rng.normal(n_mu, max(0.01, sigma_n), n_signals))
    sampled = np.maximum(1, np.round(gauss).astype(np.int64))
    return np.where(use_zero, 0, sampled).astype(np.int64)


def find_crossings(
    fast_ema: np.ndarray, slow_ema: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Find indices where fast EMA crosses slow EMA.

    Returns (cross_up_indices, cross_down_indices).
    A cross-up at t means fast[t-1] <= slow[t-1] AND fast[t] > slow[t].
    """
    # Difference: positive when fast > slow
    diff = fast_ema - slow_ema
    # NaN-safe: shift and check sign change
    prev_diff = np.concatenate(([np.nan], diff[:-1]))
    valid = ~(np.isnan(diff) | np.isnan(prev_diff))
    cross_up = valid & (prev_diff <= 0) & (diff > 0)
    cross_down = valid & (prev_diff >= 0) & (diff < 0)
    return np.where(cross_up)[0], np.where(cross_down)[0]


def backtest_arrows(
    prices: np.ndarray,
    n_mu: int,
    x_zero: float,
    sigma_n: float | None = None,
    bear_alloc: float = 1.0,
    fast_period: int = 9,
    slow_period: int = 21,
    cost_bps: float = 5.0,
    initial_cash: float = 100_000.0,
    warmup_mult: int = 3,
    rng_seed: int = 42,
    max_delay: int | None = None,
) -> BacktestResult:
    """Run a single Archer backtest.

    Args:
        prices: 1D array of close prices.
        n_mu: mean delay (candles).
        x_zero: probability of zero delay.
        sigma_n: std of delay distribution. Defaults to n_mu/2.
        bear_alloc: position size on bearish signal. -1.0 = full short, 0 = cash, +1 = full long.
        fast_period: fast EMA period.
        slow_period: slow EMA period.
        cost_bps: round-trip cost in basis points.
        initial_cash: starting capital.
        warmup_mult: number of slow_periods to skip before trading.
        rng_seed: numpy random seed.
        max_delay: cap on delay to avoid stepping beyond data. Defaults to n_mu*4.

    Returns:
        BacktestResult with equity curve, position series, n_trades, etc.
    """
    prices = np.asarray(prices, dtype=np.float64)
    n = len(prices)
    if n == 0:
        return BacktestResult(
            equity=np.array([]), position=np.array([]), n_trades=0,
            total_return=0.0, n_skipped=0,
        )

    if sigma_n is None:
        sigma_n = max(0.01, n_mu / 2.0)
    if max_delay is None:
        max_delay = max(1, int(n_mu * 4))

    # Compute EMAs
    fast = ema_vectorized(prices, fast_period)
    slow = ema_vectorized(prices, slow_period)

    # Find crosses
    cross_up_idx, cross_down_idx = find_crossings(fast, slow)
    n_up, n_down = len(cross_up_idx), len(cross_down_idx)
    n_signals = n_up + n_down
    if n_signals == 0:
        return BacktestResult(
            equity=np.full(n, initial_cash, dtype=np.float64),
            position=np.zeros(n, dtype=np.float64),
            n_trades=0,
            total_return=0.0,
            n_skipped=0,
        )

    # Sample delays for all signals (interleave up/down)
    rng = np.random.default_rng(rng_seed)
    delays = sample_delay(rng, n_signals, n_mu, sigma_n, x_zero)
    delays = np.minimum(delays, max_delay)

    # Build signal list: each entry = (cross_index, direction, delay, target_index)
    all_crosses = np.concatenate([cross_up_idx, cross_down_idx])
    all_dirs = np.concatenate([np.ones(n_up, dtype=np.int8), -np.ones(n_down, dtype=np.int8)])
    targets = all_crosses + delays

    # Filter out targets beyond data length
    in_bounds = targets < n
    all_crosses = all_crosses[in_bounds]
    all_dirs = all_dirs[in_bounds]
    targets = targets[in_bounds]
    delays = delays[in_bounds]

    # Sort by target index (chronological execution order)
    order = np.argsort(targets)
    all_crosses = all_crosses[order]
    all_dirs = all_dirs[order]
    targets = targets[order]
    delays = delays[order]

    # Verify: at target, fast still on same side of slow as original cross
    valid = np.ones(len(targets), dtype=bool)
    for i, (ci, ti, d) in enumerate(zip(all_crosses, targets, delays)):
        # Original cross direction:
        # up: fast[ci] > slow[ci]; down: fast[ci] < slow[ci]
        # At target ti, check if same direction holds (fast[ti] > slow[ti] vs orig)
        if d == 0:
            ti = ci  # immediate entry, verify trivial at cross point
        if np.isnan(fast[ti]) or np.isnan(slow[ti]):
            valid[i] = False
            continue
        if all_dirs[i] > 0 and not (fast[ti] > slow[ti]):
            valid[i] = False
        elif all_dirs[i] < 0 and not (fast[ti] < slow[ti]):
            valid[i] = False

    n_skipped = int((~valid).sum())
    valid_crosses = all_crosses[valid]
    valid_dirs = all_dirs[valid]
    valid_targets = targets[valid]

    # Convert targets to position timeline:
    # At time t, position = direction of latest valid signal whose target <= t.
    # Build a timeline of (time, new_position) pairs.
    position = np.zeros(n, dtype=np.float64)
    current_pos = 0.0
    last_target = -1
    for ci, di, ti in zip(valid_crosses, valid_dirs, valid_targets):
        if ti <= last_target:
            # Signal superseded by a later valid signal before this one fires
            # We keep the later signal
            continue
        # New position: bullish -> +1, bearish -> bear_alloc (could be negative)
        new_pos = float(di) * (1.0 if di > 0 else bear_alloc)
        # Fill from ti onwards
        position[ti:] = new_pos
        last_target = ti

    # Compute equity curve with transaction costs at position changes.
    #
    # Position accounting:
    #   - Long:  pay cash -> own units -> MTM = units * price. Equity = cash + units * price.
    #   - Short: borrow units, receive cash = units * entry_price. MTM = units * (entry - current).
    #            Equity = cash + short_pnl.
    #   - Cash:  equity = cash.
    #
    # The cost is applied as a fraction of the notional traded at each entry/exit.
    cost_rate = cost_bps / 10000.0  # 5 bps = 0.0005
    equity = np.full(n, initial_cash, dtype=np.float64)
    cash = initial_cash
    long_units = 0.0          # units held when long
    short_entry_price = 0.0   # entry price of current short position
    short_units = 0.0         # units sold short (positive magnitude)
    last_pos_size = 0.0

    for t in range(n):
        if position[t] != last_pos_size:
            # Close existing position at close[t]
            if last_pos_size > 0:
                # Was long: sell long_units at price[t].
                # Pay exit cost on the sold notional.
                sale_notional = long_units * prices[t]
                cost_close = sale_notional * cost_rate
                cash += sale_notional - cost_close
                long_units = 0.0
            elif last_pos_size < 0:
                # Was short: buy back short_units to close.
                # We pay current_price * units, but receive back the borrowed
                # value (units * entry_price). Net cash flow = (entry - current) * units.
                # Plus entry/exit costs (cost already paid at entry; we add exit cost now).
                cost_close = short_units * prices[t] * cost_rate
                # Cash at this moment equals (sale_proceeds - entry_cost).
                # Realized short PnL: (entry_price - current_price) * short_units.
                # Add realized PnL to cash, subtract exit cost.
                realized_pnl = (short_entry_price - prices[t]) * short_units
                cash += realized_pnl - cost_close
                short_units = 0.0
                short_entry_price = 0.0

            # Enter new position at close[t]
            if position[t] > 0:
                # Go long: spend cash, own units
                target_notional = position[t] * cash
                if target_notional > 0:
                    cost = target_notional * cost_rate
                    long_units = (target_notional - cost) / prices[t]
                    cash -= target_notional
            elif position[t] < 0:
                # Go short: borrow units, sell for cash.
                # Accounting model: cash represents the proceeds from selling
                # the borrowed units. When we later buy them back (exit), cash
                # grows by the price difference (or shrinks if price rose).
                # Equity = cash + short_pnl where short_pnl = units * (entry - current).
                target_notional = abs(position[t]) * cash
                if target_notional > 0:
                    short_units = target_notional / prices[t]
                    sale_proceeds = short_units * prices[t]
                    cost = sale_proceeds * cost_rate
                    cash = sale_proceeds - cost  # replace cash with proceeds
                    short_entry_price = prices[t]
            last_pos_size = position[t]

        # Mark-to-market
        long_mtm = long_units * prices[t]
        short_mtm = short_units * (short_entry_price - prices[t])
        equity[t] = cash + long_mtm + short_mtm

    n_trades = int(np.sum(np.diff(position) != 0))
    total_return = float(equity[-1] / initial_cash - 1.0) if initial_cash > 0 else 0.0

    return BacktestResult(
        equity=equity,
        position=position,
        n_trades=n_trades,
        total_return=total_return,
        n_skipped=n_skipped,
    )


# ---------------- vectorized sweep ----------------


def sweep_arrows(
    prices: np.ndarray,
    n_mu_grid: np.ndarray,
    x_grid: np.ndarray,
    ema_pairs: list[tuple[int, int]],
    bear_alloc_grid: np.ndarray | None = None,
    cost_bps: float = 5.0,
    sigma_n: float | None = None,
    rng_seed: int = 42,
    return_equity: bool = False,
) -> dict:
    """Run a 4D parameter sweep.

    Returns dict with arrays of shape (len(n_mu), len(x), len(bear_alloc), len(ema_pairs))
    for each metric. For non-1d timeframes, pass bear_alloc_grid=[1.0] (single value).

    Args:
        prices: 1D price array.
        n_mu_grid: 1D array of n_mu values.
        x_grid: 1D array of x_zero values (probabilities).
        ema_pairs: list of (fast_period, slow_period) tuples.
        bear_alloc_grid: 1D array of bearish allocations. Defaults to [1.0].
        cost_bps: transaction cost.
        sigma_n: delay distribution std. Default n_mu/2.
        rng_seed: random seed.
        return_equity: if True, also return equity curves for best zone (slow, expensive).

    Returns:
        Dict with keys: sharpe, cagr, max_dd, total_return, num_trades, n_skipped.
        Each is a 4D numpy array.
    """
    if bear_alloc_grid is None:
        bear_alloc_grid = np.array([1.0])
    prices = np.asarray(prices, dtype=np.float64)
    n_periods = len(prices)
    periods_per_year = 252.0  # caller can adjust externally

    shape = (len(n_mu_grid), len(x_grid), len(bear_alloc_grid), len(ema_pairs))
    sharpe_out = np.full(shape, np.nan)
    cagr_out = np.full(shape, np.nan)
    max_dd_out = np.full(shape, np.nan)
    total_ret_out = np.full(shape, np.nan)
    n_trades_out = np.zeros(shape, dtype=np.int32)
    n_skipped_out = np.zeros(shape, dtype=np.int32)

    # Per-candle returns: (p[t+1] - p[t]) / p[t]. Guard against zero prices.
    safe_prices = np.where(prices == 0, np.nan, prices)
    returns = np.diff(safe_prices) / safe_prices[:-1]
    returns = np.concatenate(([0.0], returns))  # align length with prices

    for i, n_mu in enumerate(n_mu_grid):
        for j, x in enumerate(x_grid):
            for k, bear_alloc in enumerate(bear_alloc_grid):
                for l, (fast, slow) in enumerate(ema_pairs):
                    result = backtest_arrows(
                        prices,
                        n_mu=int(n_mu),
                        x_zero=float(x),
                        sigma_n=sigma_n,
                        bear_alloc=float(bear_alloc),
                        fast_period=fast,
                        slow_period=slow,
                        cost_bps=cost_bps,
                        rng_seed=rng_seed,
                    )
                    eq = result.equity
                    if len(eq) < 2:
                        continue
                    # Per-bar equity returns. Guard against zero/negative equity
                    # (which would cause division-by-zero or sign flips).
                    safe_eq = np.where(eq <= 0, np.nan, eq)
                    eq_returns = np.diff(safe_eq) / safe_eq[:-1]
                    eq_returns = np.where(np.isnan(eq_returns), 0.0, eq_returns)
                    eq_returns = np.concatenate(([0.0], eq_returns))
                    # Sharpe: requires nonzero std; ignore NaN positions.
                    valid_returns = eq_returns[~np.isnan(eq_returns)]
                    if len(valid_returns) > 1 and valid_returns.std() > 0:
                        sharpe_out[i, j, k, l] = (
                            valid_returns.mean() / valid_returns.std() * math.sqrt(periods_per_year)
                        )
                    # CAGR: requires positive endpoints and years > 0.
                    if eq[0] > 0 and eq[-1] > 0 and n_periods > 0:
                        years = n_periods / periods_per_year
                        if years > 0:
                            ratio = eq[-1] / eq[0]
                            if ratio > 0:
                                cagr_out[i, j, k, l] = ratio ** (1.0 / years) - 1.0
                    # Max DD
                    running_max = np.maximum.accumulate(eq)
                    dd = eq / running_max - 1.0
                    max_dd_out[i, j, k, l] = dd.min()
                    # Total return
                    total_ret_out[i, j, k, l] = result.total_return
                    n_trades_out[i, j, k, l] = result.n_trades
                    n_skipped_out[i, j, k, l] = result.n_skipped

    return {
        "sharpe": sharpe_out,
        "cagr": cagr_out,
        "max_drawdown": max_dd_out,
        "total_return": total_ret_out,
        "num_trades": n_trades_out,
        "n_skipped": n_skipped_out,
    }


# ---------------- baselines ----------------


def buy_and_hold(
    prices: np.ndarray,
    initial_cash: float = 100_000.0,
) -> BacktestResult:
    """Buy at first candle, hold forever. Baseline."""
    prices = np.asarray(prices, dtype=np.float64)
    n = len(prices)
    if n == 0:
        return BacktestResult(
            equity=np.array([]), position=np.array([]), n_trades=0,
            total_return=0.0, n_skipped=0,
        )
    equity = initial_cash * prices / prices[0]
    position = np.ones(n, dtype=np.float64)
    return BacktestResult(
        equity=equity,
        position=position,
        n_trades=1,
        total_return=float(prices[-1] / prices[0] - 1.0),
        n_skipped=0,
    )


def vanilla_ema_cross(
    prices: np.ndarray,
    fast_period: int = 9,
    slow_period: int = 21,
    cost_bps: float = 5.0,
    initial_cash: float = 100_000.0,
    bear_alloc: float = 1.0,
    bullish_alloc: float = 1.0,
) -> BacktestResult:
    """Plain EMA crossover: at every cross, immediately enter bullish=+1 / bearish=bear_alloc.

    No delay, no verify. Same cost model as Archer.
    """
    return backtest_arrows(
        prices,
        n_mu=0,
        x_zero=1.0,           # always zero delay
        sigma_n=1.0,
        bear_alloc=bear_alloc,
        fast_period=fast_period,
        slow_period=slow_period,
        cost_bps=cost_bps,
        initial_cash=initial_cash,
        rng_seed=42,
    )
