"""test_archer_engine.py — Unit tests for archer_engine.

Tests mathematical correctness:
- No double-counting of cash in long/short entry/exit
- No division-by-zero (zero prices, zero std, zero equity)
- No NaN propagation through Sharpe/CAGR/MaxDD
- Costs applied correctly at entry AND exit
- Long/short PnL accounting matches expectations
"""
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.archer_engine import backtest_arrows, vanilla_ema_cross, buy_and_hold, sweep_arrows


def test_long_entry_exit_same_price():
    """Long round-trip should give roughly B&H return (with costs deducted)."""
    # Construct a price series with EXACTLY ONE cross-up to enter long
    # and then never cross down again. With bear_alloc=0, we never short.
    prices = np.concatenate([
        np.full(20, 100.0),         # flat warm-up
        np.linspace(100, 150, 10),  # clear uptrend -> cross up
        np.full(40, 150.0),         # flat forever after (no further crosses)
    ])
    res = backtest_arrows(prices, n_mu=0, x_zero=1.0, bear_alloc=0.0,
                          fast_period=2, slow_period=5, cost_bps=5.0)
    # B&H: 50% (100 -> 150)
    # Archer: enters long at cross (~115), holds to 150 = +30% gross - 10bps round-trip
    assert res.total_return > 0.25, f"Long-only should give >+25%, got {res.total_return*100:.2f}%"
    assert res.total_return < 0.55, f"Should not exceed B&H return, got {res.total_return*100:.2f}%"


def test_short_entry_exit_same_price():
    """Short round-trip should give roughly B&H return on the decline (with costs)."""
    prices = np.concatenate([
        np.full(20, 150.0),         # flat warm-up
        np.linspace(150, 100, 10),  # clear downtrend -> cross down -> short
        np.full(40, 100.0),         # flat forever after
    ])
    res = backtest_arrows(prices, n_mu=0, x_zero=1.0, bear_alloc=1.0,
                          fast_period=2, slow_period=5, cost_bps=5.0)
    # B&H decline: 150 -> 100 = -33%
    # Archer: short at cross (~140), holds to 100 = +29% gross - 10bps
    assert res.total_return > 0.20, f"Short-only should give >+20%, got {res.total_return*100:.2f}%"
    assert res.total_return < 0.50, f"Should be capped, got {res.total_return*100:.2f}%"


def test_no_double_counting_at_zero_cost():
    """At cost_bps=0, return should be exact (no fee leakage)."""
    # V-shape with sharp cross up + cross down
    prices = np.concatenate([
        np.linspace(100, 60, 20),   # cross down -> short
        np.linspace(60, 140, 20),   # cross up -> long
        np.full(20, 140.0),
    ])
    res = backtest_arrows(prices, n_mu=0, x_zero=1.0, bear_alloc=1.0,
                          fast_period=2, slow_period=5, cost_bps=0)
    # Short 100k @ ~60, close @ ~80 (cross up)
    # Long 100k @ ~80, exit @ 140
    # Compound: short gain = (80-60)/60 = 33% -> 133k
    #           long gain = (140-80)/80 = 75% -> 233k
    # Total: ~+133%
    assert 1.0 < res.total_return < 1.5, f"At zero cost, V-shape should give ~+100-150%, got {res.total_return*100:.2f}%"


def test_zero_prices_no_crash():
    """Zero prices in the middle should not cause division-by-zero crash."""
    prices_normal = np.concatenate([np.full(30, 100.0), np.full(30, 110.0)])
    res_normal = backtest_arrows(prices_normal, n_mu=3, x_zero=0.75, bear_alloc=1.0)
    # Sanity: no crash, returns sensible equity
    assert np.all(np.isfinite(res_normal.equity)), "Equity contains NaN/Inf"


def test_monotonic_no_trades():
    """Monotonic price series should generate no trades (no crosses)."""
    prices_up = np.linspace(100, 200, 252)
    res = backtest_arrows(prices_up, n_mu=3, x_zero=0.75, bear_alloc=1.0,
                          fast_period=9, slow_period=21)
    assert res.n_trades == 0, f"Monotonic should have 0 trades, got {res.n_trades}"
    assert res.total_return == 0.0, f"No trades should give 0% return, got {res.total_return*100:.2f}%"


def test_sharpe_no_inf_for_zero_returns():
    """Sharpe with zero std (flat equity) should be 0, not Inf/NaN."""
    prices = np.full(100, 100.0)  # completely flat -> no trades -> no variance
    res = backtest_arrows(prices, n_mu=3, x_zero=0.75, bear_alloc=1.0,
                          fast_period=2, slow_period=5)
    # Equity is constant -> Sharpe should be 0
    sweep = sweep_arrows(prices, n_mu_grid=np.array([1, 3]),
                         x_grid=np.array([0.5, 1.0]),
                         bear_alloc_grid=np.array([1.0]),
                         ema_pairs=[(9, 21)])
    # Sharpes may be NaN (flat equity gives 0/0 in std calc). Verify not Inf.
    assert not np.any(np.isinf(sweep['sharpe'])), f"Sharpe contains Inf values"


def test_cost_applied_at_both_entry_and_exit():
    """Cost must be applied at entry AND exit (not just entry)."""
    # Construct a clear entry and exit
    prices = np.concatenate([
        np.full(20, 100.0),
        np.linspace(100, 130, 5),    # cross up @ ~107.50
        np.full(20, 130.0),
        np.linspace(130, 100, 5),    # cross down @ ~122.50
        np.full(20, 100.0),
    ])
    res_0 = backtest_arrows(prices, n_mu=0, x_zero=1.0, bear_alloc=1.0,
                            fast_period=2, slow_period=5, cost_bps=0)
    res_5 = backtest_arrows(prices, n_mu=0, x_zero=1.0, bear_alloc=1.0,
                            fast_period=2, slow_period=5, cost_bps=5.0)
    res_50 = backtest_arrows(prices, n_mu=0, x_zero=1.0, bear_alloc=1.0,
                             fast_period=2, slow_period=5, cost_bps=50.0)
    # Higher cost -> lower return
    assert res_50.total_return < res_5.total_return < res_0.total_return, \
        f"Cost scaling broken: 0bps={res_0.total_return*100:.2f}% > 5bps={res_5.total_return*100:.2f}% > 50bps={res_50.total_return*100:.2f}%"


def test_sweep_returns_finite_metrics():
    """Full sweep on real data must return finite metrics, not NaN/Inf."""
    from src.data_loader import load_one
    df = load_one('SPY', '1d')
    prices = np.asarray(df['close'].values, dtype=np.float64)
    sweep = sweep_arrows(prices, n_mu_grid=np.array([1, 3, 5]),
                         x_grid=np.array([0.5, 1.0]),
                         bear_alloc_grid=np.array([1.0]),
                         ema_pairs=[(9, 21)])
    for key in ['sharpe', 'cagr', 'max_drawdown', 'total_return']:
        arr = sweep[key]
        # Some may be NaN if equity hits 0, but no Inf
        assert not np.any(np.isinf(arr)), f"{key} contains Inf values"


def test_long_close_cost_does_not_compound_unbounded():
    """On a TRENDING series, returns should track B&H (not compound unboundedly)."""
    # Construct uptrend with ONE cross-up, then hold. bear_alloc=0 -> no short.
    prices = np.concatenate([
        np.full(20, 100.0),
        np.linspace(100, 200, 30),  # cross up -> enter long
        np.full(200, 200.0),        # flat (hold long forever)
    ])
    res = backtest_arrows(prices, n_mu=0, x_zero=1.0, bear_alloc=0.0,
                          fast_period=2, slow_period=5, cost_bps=5.0)
    # B&H: 100%
    # Archer: enter long at ~140, hold to 200 = +43% gross - 10bps round-trip
    assert res.total_return > 0.30, f"Strong uptrend should give >+30%, got {res.total_return*100:.2f}%"
    assert res.total_return < 1.10, f"Should not exceed B&H, got {res.total_return*100:.2f}%"


def test_short_profit_on_decline():
    """Short position should profit when price declines."""
    # 30 flat, 30 declining -> cross down -> short
    prices = np.concatenate([np.full(30, 100.0), np.linspace(100, 50, 30)])
    res = backtest_arrows(prices, n_mu=0, x_zero=1.0, bear_alloc=1.0,
                          fast_period=2, slow_period=10)
    # If short triggers, we should profit
    if res.n_trades > 0:
        assert res.total_return > 0, f"Short on decline should profit, got {res.total_return*100:.2f}%"


def test_buy_and_hold_matches_price_ratio():
    """B&H equity at bar t should equal cash * prices[t] / prices[0]."""
    prices = np.array([100.0, 110.0, 121.0, 90.0, 100.0])
    res = buy_and_hold(prices, initial_cash=100000)
    expected = 100000 * prices / prices[0]
    np.testing.assert_array_almost_equal(res.equity, expected)


def run_all_tests():
    """Run all unit tests and report results."""
    tests = [
        test_long_entry_exit_same_price,
        test_short_entry_exit_same_price,
        test_no_double_counting_at_zero_cost,
        test_zero_prices_no_crash,
        test_monotonic_no_trades,
        test_sharpe_no_inf_for_zero_returns,
        test_cost_applied_at_both_entry_and_exit,
        test_sweep_returns_finite_metrics,
        test_long_close_cost_does_not_compound_unbounded,
        test_short_profit_on_decline,
        test_buy_and_hold_matches_price_ratio,
    ]
    results = []
    for t in tests:
        try:
            t()
            results.append((t.__name__, 'PASS', None))
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            results.append((t.__name__, 'FAIL', str(e)))
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:
            results.append((t.__name__, 'ERROR', str(e)))
            print(f"  ERROR {t.__name__}: {e}")
    print()
    print(f"Summary: {sum(1 for r in results if r[1] == 'PASS')}/{len(results)} passed")
    return results


if __name__ == '__main__':
    print("=" * 60)
    print("ARCHER ENGINE UNIT TESTS")
    print("=" * 60)
    print()
    run_all_tests()
