"""sweep.py — parameter sweep runner.

Usage:
    python3 -m src.sweep --ticker SPY --timeframe 1d --grid-mode default --cost-bps 5

Loads data from data/<ticker>_<timeframe>.csv, runs the 4D parameter sweep,
saves metrics CSV + equity curves to results/csv/ and results/npz/.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import archer_engine as ae
from .metrics import adjusted_periods_per_year

RESULTS_CSV = Path(__file__).resolve().parent.parent / "results" / "csv"
RESULTS_NPZ = Path(__file__).resolve().parent.parent / "results" / "npz"
RESULTS_CSV.mkdir(parents=True, exist_ok=True)
RESULTS_NPZ.mkdir(parents=True, exist_ok=True)


# Default parameter grids
GRID_DEFAULT = {
    "n_mu": [1, 3, 5, 8, 12, 18, 25, 35, 50],
    "x": [0.0, 0.25, 0.5, 0.75, 1.0],
    "bear_alloc_1d": [0.0, 0.5, 0.75, 1.0],
    "ema_pairs": [(9, 21), (12, 26), (20, 50)],
}

GRID_TINY = {
    "n_mu": [5, 15, 30],
    "x": [0.0, 0.5, 1.0],
    "bear_alloc_1d": [0.5, 1.0],
    "ema_pairs": [(9, 21)],
}


def load_prices(ticker: str, timeframe: str) -> pd.DataFrame:
    """Load cached OHLCV. Expects data/<sanitized_ticker>_<timeframe>.csv."""
    import re

    from .data_loader import DATA_DIR, _sanitize_ticker

    safe = _sanitize_ticker(ticker)
    candidates = sorted((DATA_DIR).glob(f"{safe}_{timeframe}*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"No cached data for {ticker} {timeframe}. Run: python3 -m src.data_loader"
        )
    # Prefer the file with no start-date suffix (full history)
    candidates_no_suffix = [c for c in candidates if c.stem == f"{safe}_{timeframe}"]
    path = candidates_no_suffix[0] if candidates_no_suffix else candidates[-1]
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    return df


def run_sweep_one(
    ticker: str,
    timeframe: str,
    grid: dict,
    cost_bps: float = 5.0,
    rng_seed: int = 42,
) -> dict:
    """Run the 4D sweep for one (ticker, timeframe) combination."""
    df = load_prices(ticker, timeframe)
    prices = np.asarray(df["close"].values, dtype=np.float64)
    n = len(prices)
    print(f"[{ticker} {timeframe}] {n} candles from {df.index[0]} to {df.index[-1]}")

    # bear_alloc only relevant for 1d
    is_daily = timeframe.lower() in ("1d", "1wk")
    bear_grid = grid["bear_alloc_1d"] if is_daily else [1.0]

    t0 = time.time()
    results = ae.sweep_arrows(
        prices,
        n_mu_grid=np.array(grid["n_mu"]),
        x_grid=np.array(grid["x"]),
        bear_alloc_grid=np.array(bear_grid),
        ema_pairs=grid["ema_pairs"],
        cost_bps=cost_bps,
        rng_seed=rng_seed,
    )
    elapsed = time.time() - t0
    print(f"[{ticker} {timeframe}] sweep done in {elapsed:.2f}s")

    # Build flat results DataFrame
    n_mu_arr = np.array(grid["n_mu"])
    x_arr = np.array(grid["x"])
    bear_arr = np.array(bear_grid)
    ema_arr = [f"{f}/{s}" for f, s in grid["ema_pairs"]]

    rows = []
    for i, n_mu in enumerate(n_mu_arr):
        for j, x in enumerate(x_arr):
            for k, ba in enumerate(bear_arr):
                for l, ema in enumerate(ema_arr):
                    rows.append({
                        "ticker": ticker,
                        "timeframe": timeframe,
                        "n_mu": int(n_mu),
                        "x": float(x),
                        "bear_alloc_1d": float(ba),
                        "ema_pair": ema,
                        "sharpe": float(results["sharpe"][i, j, k, l]),
                        "cagr": float(results["cagr"][i, j, k, l]),
                        "max_drawdown": float(results["max_drawdown"][i, j, k, l]),
                        "total_return": float(results["total_return"][i, j, k, l]),
                        "num_trades": int(results["num_trades"][i, j, k, l]),
                        "n_skipped": int(results["n_skipped"][i, j, k, l]),
                    })
    out_df = pd.DataFrame(rows)

    # Compute baselines for the best EMA pair
    ppy = adjusted_periods_per_year(timeframe, ticker)
    best_ema = grid["ema_pairs"][0]
    bh = ae.buy_and_hold(prices)
    bnh_metrics = {
        "sharpe": (bh.equity[-1] / bh.equity[0] - 1.0) / 1.0,  # placeholder, see below
        "cagr": ((bh.equity[-1] / bh.equity[0]) ** (ppy / n) - 1.0),
        "total_return": bh.total_return,
    }
    rets = np.diff(bh.equity) / bh.equity[:-1]
    bnh_metrics["sharpe"] = (
        rets.mean() / rets.std() * np.sqrt(ppy) if rets.std() > 0 else 0.0
    )

    ve = ae.vanilla_ema_cross(prices, fast_period=best_ema[0], slow_period=best_ema[1], cost_bps=cost_bps)
    rets_v = np.diff(ve.equity) / ve.equity[:-1]
    vanilla_metrics = {
        "sharpe": (rets_v.mean() / rets_v.std() * np.sqrt(ppy)) if rets_v.std() > 0 else 0.0,
        "cagr": ((ve.equity[-1] / ve.equity[0]) ** (ppy / n) - 1.0),
        "total_return": ve.total_return,
    }

    summary = {
        "ticker": ticker,
        "timeframe": timeframe,
        "n_candles": n,
        "periods_per_year": ppy,
        "elapsed_s": elapsed,
        "cost_bps": cost_bps,
        "grid": grid,
        "baselines": {
            "buy_and_hold": bnh_metrics,
            "vanilla_ema_cross": {**vanilla_metrics, "ema_pair": f"{best_ema[0]}/{best_ema[1]}"},
        },
        "best_in_sweep": {
            "sharpe": float(out_df["sharpe"].max()),
            "sharpe_params": out_df.loc[out_df["sharpe"].idxmax(), ["n_mu", "x", "bear_alloc_1d", "ema_pair"]].to_dict(),
        },
    }

    return {"df": out_df, "summary": summary, "raw": results, "prices": prices}


def save_results(ticker: str, timeframe: str, results: dict, basename: str | None = None):
    """Save CSV + summary JSON + npz of raw metrics."""
    name = basename or f"{ticker}_{timeframe}".replace("/", "_").replace("-", "_")
    csv_path = RESULTS_CSV / f"{name}.csv"
    results["df"].to_csv(csv_path, index=False)
    summary_path = RESULTS_CSV / f"{name}_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results["summary"], f, indent=2, default=str)
    raw = results["raw"]
    npz_path = RESULTS_NPZ / f"{name}_raw.npz"
    np.savez_compressed(
        npz_path,
        sharpe=raw["sharpe"],
        cagr=raw["cagr"],
        max_drawdown=raw["max_drawdown"],
        total_return=raw["total_return"],
        num_trades=raw["num_trades"],
        n_skipped=raw["n_skipped"],
        prices=results["prices"],
    )
    return {"csv": str(csv_path), "summary": str(summary_path), "npz": str(npz_path)}


def main():
    parser = argparse.ArgumentParser(description="Run archer-crossover parameter sweep")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument(
        "--grid-mode",
        choices=["default", "tiny"],
        default="default",
    )
    parser.add_argument("--cost-bps", type=float, default=5.0)
    parser.add_argument("--rng-seed", type=int, default=42)
    args = parser.parse_args()
    grid = GRID_TINY if args.grid_mode == "tiny" else GRID_DEFAULT
    print(f"Grid mode: {args.grid_mode} ({sum([len(v) if hasattr(v, '__len__') else 1 for v in grid.values()])} params)")
    results = run_sweep_one(
        args.ticker,
        args.timeframe,
        grid,
        cost_bps=args.cost_bps,
        rng_seed=args.rng_seed,
    )
    paths = save_results(args.ticker, args.timeframe, results)
    print(f"Saved: {paths}")
    print(f"Best Sharpe in sweep: {results['summary']['best_in_sweep']['sharpe']:.3f}")
    print(f"Buy-and-hold Sharpe: {results['summary']['baselines']['buy_and_hold']['sharpe']:.3f}")
    print(f"Vanilla EMA-cross Sharpe: {results['summary']['baselines']['vanilla_ema_cross']['sharpe']:.3f}")


if __name__ == "__main__":
    main()
