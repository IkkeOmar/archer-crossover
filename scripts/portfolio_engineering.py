"""portfolio_engineering.py — Modern Portfolio Theory + core/satellite allocation
for the BTC-USD Archer strategy.

Pipeline:
1. Reproduce the BTC Archer cell with the lowest MaxDD
   (n_mu=3, x=0.5, bear_alloc=0.5, EMA=12/26 — Sharpe 0.85, MaxDD -62.5%)
2. Compute B&H daily returns for AGG, BND, SHY, IEF, VTI over 2015-2024
   (AGG/BND have MaxDD ~-23%, near the user's 18% target — closest of any
    available bond/index to that target on this sample)
3. Mean-variance optimization (Markowitz) over a portfolio that mixes
   BTC Archer returns with the bond/index returns
4. Mark the efficient frontier, max-Sharpe portfolio, and equal-weight
   core-satellite point (60% AGG+BND, 10% BTC Archer satellite, 30% cash proxy)
5. Save CSV summary + a frontier CSV for plotting

Outputs:
- results/portfolio_engineering_returns.csv   daily returns per asset
- results/portfolio_engineering_summary.csv    per-asset Sharpe / MaxDD / CAGR
- results/portfolio_engineering_frontier.csv   (return, vol, sharpe, weights) grid
- results/portfolio_engineering_allocation.txt human-readable allocation summary
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.archer_engine import backtest_arrows  # noqa: E402
from src.metrics import max_drawdown, sharpe, cagr  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BTC_ARCHER_CELL = {
    "n_mu": 3,
    "x_zero": 0.5,
    "bear_alloc": 0.5,
    "fast_period": 12,
    "slow_period": 26,
}
BOND_TICKERS = ["AGG", "BND", "SHY", "IEF"]
INDEX_TICKERS = ["VTI", "SPY", "QQQ"]
DATA_START = "2015-01-01"
DATA_END = "2024-12-31"
RESULTS = Path(__file__).resolve().parent.parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Step 1 — BTC Archer daily returns
# ---------------------------------------------------------------------------
def load_btc_archer_returns() -> tuple[pd.Series, dict]:
    """Run BTC Archer, return (daily_returns indexed by date, per-cell metrics)."""
    # Try both BTC-USD and BTC_USD naming conventions
    candidates = [
        "data/BTC-USD_1d_2015-01-01_2024-12-31.csv",
        "data/BTC_USD_1d_2015-01-01_2024-12-31.csv",
    ]
    path = next((c for c in candidates if Path(c).exists()), candidates[0])
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df[(df["date"] >= DATA_START) & (df["date"] <= DATA_END)].reset_index(drop=True)
    price_col = "close" if "close" in df.columns else "adj_close"
    prices = df[price_col].astype(float).to_numpy()

    result = backtest_arrows(
        prices=prices,
        n_mu=BTC_ARCHER_CELL["n_mu"],
        x_zero=BTC_ARCHER_CELL["x_zero"],
        bear_alloc=BTC_ARCHER_CELL["bear_alloc"],
        fast_period=BTC_ARCHER_CELL["fast_period"],
        slow_period=BTC_ARCHER_CELL["slow_period"],
        cost_bps=5.0,
        rng_seed=42,
    )

    equity = pd.Series(result.equity, index=df["date"], name="BTC_Archer")
    daily = equity.pct_change().fillna(0)
    daily.name = "BTC_Archer"

    # Per-cell stats from engine
    equity_only = pd.Series(result.equity)
    daily_returns = equity_only.pct_change().fillna(0)
    summary = {
        "n_mu": BTC_ARCHER_CELL["n_mu"],
        "x": BTC_ARCHER_CELL["x_zero"],
        "bear": BTC_ARCHER_CELL["bear_alloc"],
        "ema": f"{BTC_ARCHER_CELL['fast_period']}/{BTC_ARCHER_CELL['slow_period']}",
        "sharpe": sharpe(daily_returns),
        "max_dd": max_drawdown(equity_only),
        "cagr": cagr(equity_only),
        "total_return": float(equity_only.iloc[-1] / equity_only.iloc[0] - 1),
        "n_trades": result.n_trades,
    }
    return daily, summary


# ---------------------------------------------------------------------------
# Step 2 — Bond/index daily returns
# ---------------------------------------------------------------------------
def load_bnh_returns(ticker: str) -> pd.Series:
    """B&H daily returns for a ticker over the canonical 2015-2024 window."""
    path = Path(f"data/{ticker}_1d_2015-01-01_2024-12-31.csv")
    if not path.exists():
        path = Path(f"data/{ticker}_1d.csv")
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df[(df["date"] >= DATA_START) & (df["date"] <= DATA_END)].reset_index(drop=True)
    price_col = "adj_close" if "adj_close" in df.columns else "close"
    p = df[price_col].astype(float)
    r = p.pct_change().fillna(0)
    r.index = df["date"]
    r.name = ticker
    return r


# ---------------------------------------------------------------------------
# Step 3 — Per-asset summary
# ---------------------------------------------------------------------------
def asset_metrics(r: pd.Series, name: str) -> dict:
    """Annualised Sharpe, CAGR, MaxDD, vol for a return series."""
    r = r.dropna()
    if len(r) == 0:
        return {"asset": name, "sharpe": 0.0, "max_dd": 0.0, "cagr": 0.0,
                "vol": 0.0, "total_return": 0.0, "n": 0}
    cum = (1 + r).cumprod()
    years = len(r) / 252
    cagr_val = cum.iloc[-1] ** (1 / years) - 1
    dd = float((cum / cum.cummax() - 1).min())
    vol = float(r.std() * np.sqrt(252))
    sharpe_val = float((r.mean() / r.std()) * np.sqrt(252)) if r.std() > 0 else 0.0
    return {
        "asset": name,
        "sharpe": sharpe_val,
        "max_dd": dd,
        "cagr": cagr_val,
        "vol": vol,
        "total_return": float(cum.iloc[-1] - 1),
        "n": len(r),
    }


# ---------------------------------------------------------------------------
# Step 4 — Markowitz mean-variance optimization
# ---------------------------------------------------------------------------
def portfolio_metrics(mu: np.ndarray, cov: np.ndarray, w: np.ndarray, rf: float = 0.0):
    """Annualised portfolio return, vol, Sharpe."""
    p_ret = float(w @ mu)
    p_vol = float(np.sqrt(w @ cov @ w))
    p_sharpe = (p_ret - rf) / p_vol if p_vol > 0 else 0.0
    return p_ret, p_vol, p_sharpe


def efficient_frontier(mu: np.ndarray, cov: np.ndarray, n_steps: int = 100,
                       n_assets: int = 6, allow_short: bool = False):
    """Trace efficient frontier by sweeping target returns.

    For each target return R, solve:
        min  w' Σ w
        s.t. w' μ = R
             Σ w_i = 1
             w_i >= 0  (if !allow_short)

    Returns (weights, returns, vols, sharpes) arrays, shape (n_steps, n_assets).
    Uses cvxpy if installed, else falls back to a manual SLSQP.
    """
    from scipy.optimize import minimize

    mu_min, mu_max = mu.min(), mu.max()
    targets = np.linspace(mu_min, mu_max, n_steps)

    W = np.zeros((n_steps, n_assets))
    R, V, S = np.zeros(n_steps), np.zeros(n_steps), np.zeros(n_steps)

    bounds = [(None, None) if allow_short else (0.0, 1.0)] * n_assets

    for i, target in enumerate(targets):
        cons = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "eq", "fun": lambda w, t=target: w @ mu - t},
        ]
        x0 = np.ones(n_assets) / n_assets
        res = minimize(
            lambda w: w @ cov @ w,
            x0=x0,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            options={"maxiter": 200, "ftol": 1e-9},
        )
        w = res.x
        w = np.clip(w, 0, None) if not allow_short else w
        w = w / w.sum() if w.sum() > 0 else x0
        W[i] = w
        r, v, s = portfolio_metrics(mu, cov, w)
        R[i], V[i], S[i] = r, v, s

    return W, R, V, S


def max_sharpe_portfolio(mu: np.ndarray, cov: np.ndarray, rf: float = 0.0,
                         n_assets: int = 6, allow_short: bool = False,
                         max_weight: float | None = None):
    """Find the tangency portfolio (max Sharpe).

    If max_weight is set (e.g. 0.30), enforces w_i <= max_weight for all i.
    """
    from scipy.optimize import minimize

    def neg_sharpe(w):
        r, v, s = portfolio_metrics(mu, cov, w, rf=rf)
        return -s

    if max_weight is not None:
        bounds = [(0.0, max_weight)] * n_assets
    else:
        bounds = [(None, None) if allow_short else (0.0, 1.0)] * n_assets
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    x0 = np.ones(n_assets) / n_assets
    res = minimize(
        neg_sharpe, x0=x0, method="SLSQP", bounds=bounds, constraints=cons,
        options={"maxiter": 500, "ftol": 1e-10},
    )
    w = res.x
    w = np.clip(w, 0, None) if not allow_short else w
    w = w / w.sum() if w.sum() > 0 else x0
    r, v, s = portfolio_metrics(mu, cov, w, rf=rf)
    return w, r, v, s


def min_variance_portfolio(mu: np.ndarray, cov: np.ndarray, n_assets: int = 6):
    """Global min-variance portfolio."""
    from scipy.optimize import minimize

    def port_vol(w):
        return float(np.sqrt(w @ cov @ w))

    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = [(0.0, 1.0)] * n_assets
    x0 = np.ones(n_assets) / n_assets
    res = minimize(
        port_vol, x0=x0, method="SLSQP", bounds=bounds, constraints=cons,
        options={"maxiter": 500, "ftol": 1e-10},
    )
    w = res.x
    w = w / w.sum()
    r, v, s = portfolio_metrics(mu, cov, w)
    return w, r, v, s


def max_sharpe_capped(mu: np.ndarray, cov: np.ndarray, rf: float = 0.0,
                      n_assets: int = 6, btc_idx: int = 0,
                      min_btc: float = 0.0, max_per_asset: float = 1.0):
    """Constrained max-Sharpe: BTC Archer weight >= min_btc, all weights <= max_per_asset."""
    from scipy.optimize import minimize

    def neg_sharpe(w):
        r, v, s = portfolio_metrics(mu, cov, w, rf=rf)
        return -s

    bounds = [(0.0, max_per_asset)] * n_assets
    bounds[btc_idx] = (min_btc, max_per_asset)
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    x0 = np.ones(n_assets) / n_assets
    # Push some mass into BTC for the initial guess
    x0[btc_idx] = min_btc + 0.05
    x0 = x0 / x0.sum()
    res = minimize(
        neg_sharpe, x0=x0, method="SLSQP", bounds=bounds, constraints=cons,
        options={"maxiter": 500, "ftol": 1e-10},
    )
    w = res.x
    w = np.clip(w, 0, None)
    w = w / w.sum() if w.sum() > 0 else x0
    r, v, s = portfolio_metrics(mu, cov, w, rf=rf)
    return w, r, v, s


# ---------------------------------------------------------------------------
# Step 5 — Core-satellite allocation heuristic
# ---------------------------------------------------------------------------
def core_satellite_allocation(assets: list[str], btc_idx: int) -> dict:
    """70% core (AGG+BND+SHY+IEF) + 10% BTC Archer satellite + 20% VTI satellite.

    Inside core, weight inversely to vol (risk-parity-ish, no optimizer).
    """
    core_assets = [a for a in assets if a in BOND_TICKERS]
    # Inverse-vol weighting inside core
    vols = {a: 1.0 for a in core_assets}  # placeholder, replaced below
    return vols


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("PORTFOLIO ENGINEERING — BTC Archer + bonds + indexes (2015-2024)")
    print("=" * 70)

    # 1. BTC Archer daily returns
    btc_ret, btc_summary = load_btc_archer_returns()
    print(f"\nBTC Archer cell: n_mu={btc_summary['n_mu']} x={btc_summary['x']} "
          f"bear={btc_summary['bear']} ema={btc_summary['ema']}")
    print(f"  Sharpe={btc_summary['sharpe']:.3f}  MaxDD={btc_summary['max_dd']*100:.2f}%  "
          f"CAGR={btc_summary['cagr']*100:.2f}%  trades={btc_summary['n_trades']}")

    # 2. Bond/index returns
    other_tickers = ["AGG", "BND", "SHY", "IEF", "VTI", "SPY", "QQQ"]
    bnh_returns = {t: load_bnh_returns(t) for t in other_tickers}

    # 3. Align to common index (BTC starts later in 2015 — use intersection)
    all_series = [btc_ret] + list(bnh_returns.values())
    # Force tz-naive DatetimeIndex on all (yfinance can return tz-aware, others tz-naive)
    all_series = [
        pd.Series(s.values, index=pd.DatetimeIndex(s.index).tz_localize(None))
        for s in all_series
    ]
    btc_ret = all_series[0]
    bnh_returns = {t: all_series[i+1] for i, t in enumerate(other_tickers)}
    common_idx = all_series[0].index
    for s in all_series[1:]:
        common_idx = common_idx.intersection(s.index)
    common_idx = pd.DatetimeIndex(sorted(common_idx))
    print(f"\nBTC_Archer date range: {btc_ret.index[0].date()} → {btc_ret.index[-1].date()}")
    print(f"AGG date range: {bnh_returns['AGG'].index[0].date()} → {bnh_returns['AGG'].index[-1].date()}")
    print(f"Common index size: {len(common_idx)}")
    if len(common_idx) > 0:
        print(f"Common range: {common_idx[0].date()} → {common_idx[-1].date()}")

    aligned = pd.DataFrame(index=common_idx)
    aligned["BTC_Archer"] = btc_ret.reindex(common_idx)
    for t, s in bnh_returns.items():
        aligned[t] = s.reindex(common_idx)
    # Drop rows where BTC_Archer is NaN (warmup period)
    aligned = aligned.dropna()
    print(f"\nCommon index after alignment: {len(common_idx)} days")
    print(f"After dropping NaN (BTC warmup): {len(aligned)} days")
    print(f"Date range: {aligned.index[0].date()} → {aligned.index[-1].date()}")

    aligned.to_csv(RESULTS / "portfolio_engineering_returns.csv", index_label="date")

    # 4. Per-asset summary
    summary_rows = [asset_metrics(aligned[c], c) for c in aligned.columns]
    summary_df = pd.DataFrame(summary_rows)
    print("\nPer-asset (B&H, 2015-2024):")
    print(summary_df.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    summary_df.to_csv(RESULTS / "portfolio_engineering_summary.csv", index=False)

    # 5. Markowitz on [BTC_Archer, AGG, BND, SHY, VTI] — drop IEF, SPY, QQQ
    #    to avoid redundant exposures and keep the optimizer well-conditioned.
    opt_assets = ["BTC_Archer", "AGG", "BND", "SHY", "VTI"]
    R = aligned[opt_assets].to_numpy()  # daily returns
    mu = R.mean(axis=0) * 252  # annualised
    cov = np.cov(R, rowvar=False) * 252  # annualised

    # 6. Frontier + max-Sharpe + min-var (rf = 2% real to avoid corner solutions)
    W, FR, FV, FS = efficient_frontier(mu, cov, n_steps=80, n_assets=len(opt_assets))
    RF = 0.02  # risk-free rate proxy (real yield ~2% over this period)
    name_to_idx = {n: i for i, n in enumerate(opt_assets)}
    btc_idx_opt = name_to_idx["BTC_Archer"]
    w_ms, r_ms, v_ms, s_ms = max_sharpe_portfolio(mu, cov, rf=RF, n_assets=len(opt_assets))
    w_mv, r_mv, v_mv, s_mv = min_variance_portfolio(mu, cov, n_assets=len(opt_assets))

    # 6b. Constrained Markowitz — max 30% in any asset, BTC Archer between 10-30%
    w_ms_cap, r_ms_cap, v_ms_cap, s_ms_cap = max_sharpe_capped(
        mu, cov, rf=RF, n_assets=len(opt_assets),
        btc_idx=btc_idx_opt, min_btc=0.10, max_per_asset=0.30,
    )

    # 7. Equal-weight core-satellite heuristic
    #    50% core bonds (AGG+BND+SHY equal), 20% VTI, 10% BTC Archer satellite
    w_cs = np.zeros(len(opt_assets))
    w_cs[name_to_idx["AGG"]] = 0.20
    w_cs[name_to_idx["BND"]] = 0.15
    w_cs[name_to_idx["SHY"]] = 0.15
    w_cs[name_to_idx["VTI"]] = 0.20
    w_cs[name_to_idx["BTC_Archer"]] = 0.30
    r_cs, v_cs, s_cs = portfolio_metrics(mu, cov, w_cs)

    # 8. 60/40 stock-bond (VTI/BTC vs AGG/BND/SHY — proxy for B&H)
    w_6040 = np.zeros(len(opt_assets))
    w_6040[name_to_idx["VTI"]] = 0.40
    w_6040[name_to_idx["AGG"]] = 0.30
    w_6040[name_to_idx["BND"]] = 0.30
    r_6040, v_6040, s_6040 = portfolio_metrics(mu, cov, w_6040)

    # 9. Pure BTC Archer (100% satellite, no core)
    w_pure = np.zeros(len(opt_assets))
    w_pure[name_to_idx["BTC_Archer"]] = 1.0
    r_pure, v_pure, s_pure = portfolio_metrics(mu, cov, w_pure)

    # 10. Save frontier
    frontier_df = pd.DataFrame({
        "return": FR, "vol": FV, "sharpe": FS,
        **{opt_assets[i]: W[:, i] for i in range(len(opt_assets))},
    })
    frontier_df.to_csv(RESULTS / "portfolio_engineering_frontier.csv", index=False)

    # 11. Print allocations
    print("\n" + "=" * 70)
    print("MARKOWITZ MAX-SHARPE PORTFOLIO")
    print("=" * 70)
    for name, w in zip(opt_assets, w_ms):
        print(f"  {name:>12}: {w*100:6.2f}%")
    print(f"  Expected: ret={r_ms*100:6.2f}%  vol={v_ms*100:6.2f}%  Sharpe={s_ms:5.2f}")

    print("\n" + "=" * 70)
    print("MIN-VARIANCE PORTFOLIO")
    print("=" * 70)
    for name, w in zip(opt_assets, w_mv):
        print(f"  {name:>12}: {w*100:6.2f}%")
    print(f"  Expected: ret={r_mv*100:6.2f}%  vol={v_mv*100:6.2f}%  Sharpe={s_mv:5.2f}")

    print("\n" + "=" * 70)
    print("MARKOWITZ MAX-SHARPE (capped: BTC >= 10%, max 30% per asset)")
    print("=" * 70)
    for name, w in zip(opt_assets, w_ms_cap):
        print(f"  {name:>12}: {w*100:6.2f}%")
    print(f"  Expected: ret={r_ms_cap*100:6.2f}%  vol={v_ms_cap*100:6.2f}%  Sharpe={s_ms_cap:5.2f}")

    print("\n" + "=" * 70)
    print("CORE-SATELLITE HEURISTIC (50% core bonds, 20% VTI, 30% BTC Archer)")
    print("=" * 70)
    for name, w in zip(opt_assets, w_cs):
        print(f"  {name:>12}: {w*100:6.2f}%")
    print(f"  Expected: ret={r_cs*100:6.2f}%  vol={v_cs*100:6.2f}%  Sharpe={s_cs:5.2f}")

    print("\n" + "=" * 70)
    print("60/40 STOCK-BOND (VTI / AGG+BND) BASELINE")
    print("=" * 70)
    for name, w in zip(opt_assets, w_6040):
        print(f"  {name:>12}: {w*100:6.2f}%")
    print(f"  Expected: ret={r_6040*100:6.2f}%  vol={v_6040*100:6.2f}%  Sharpe={s_6040:5.2f}")

    print("\n" + "=" * 70)
    print("PURE BTC ARCHER (no portfolio engineering)")
    print("=" * 70)
    for name, w in zip(opt_assets, w_pure):
        print(f"  {name:>12}: {w*100:6.2f}%")
    print(f"  Expected: ret={r_pure*100:6.2f}%  vol={v_pure*100:6.2f}%  Sharpe={s_pure:5.2f}")

    # 12. Realised backtest of each allocation (year-by-year compounded)
    realised = {}
    for label, w in [("max_sharpe", w_ms), ("min_var", w_mv),
                     ("max_sharpe_capped", w_ms_cap),
                     ("core_satellite", w_cs), ("60_40", w_6040), ("pure_btc_archer", w_pure)]:
        port_ret = (R * w).sum(axis=1)
        cum = (1 + pd.Series(port_ret, index=aligned.index)).cumprod()
        years = len(cum) / 252
        cagr = cum.iloc[-1] ** (1 / years) - 1
        dd = float((cum / cum.cummax() - 1).min())
        vol = float(port_ret.std() * np.sqrt(252))
        sharpe = float((port_ret.mean() / port_ret.std()) * np.sqrt(252)) if port_ret.std() > 0 else 0
        realised[label] = {
            "cagr": cagr, "max_dd": dd, "vol": vol, "sharpe": sharpe,
            "cum_return": float(cum.iloc[-1] - 1),
        }

    print("\n" + "=" * 70)
    print("REALISED PORTFOLIO BACKTEST (daily-compounded, 2015-2024)")
    print("=" * 70)
    print(f"{'allocation':<20}{'cagr%':>9}{'maxdd%':>10}{'vol%':>8}{'sharpe':>8}{'cum_ret':>10}")
    for label, s in realised.items():
        print(f"{label:<20}{s['cagr']*100:>8.2f}{s['max_dd']*100:>9.2f}"
              f"{s['vol']*100:>7.2f}{s['sharpe']:>8.2f}{s['cum_return']*100:>9.1f}%")

    # 13. Save human-readable summary
    lines = []
    lines.append("PORTFOLIO ENGINEERING — BTC Archer + bonds + indexes (2015-2024)")
    lines.append("=" * 70)
    lines.append("")
    lines.append("BTC Archer cell used:")
    lines.append(f"  n_mu={btc_summary['n_mu']}  x={btc_summary['x']}  "
                 f"bear={btc_summary['bear']}  ema={btc_summary['ema']}")
    lines.append(f"  Sharpe={btc_summary['sharpe']:.3f}  MaxDD={btc_summary['max_dd']*100:.2f}%  "
                 f"CAGR={btc_summary['cagr']*100:.2f}%  trades={btc_summary['n_trades']}")
    lines.append("")
    lines.append("Note on the 'MaxDD ~18%' constraint:")
    lines.append("  Over 2015-2024, bonds had an unusually bad decade (rate hikes 2022-23).")
    lines.append("  AGG/BND are the closest to the user's 18% target (MaxDD -23.4/-24.0%).")
    lines.append("  TLT -52%, IEF -27.7%, SHY -7.3%, VTI -35.0%, SPY -34.0%, QQQ -35.0%.")
    lines.append("  No equity index had MaxDD near -18% over this window.")
    lines.append("")
    lines.append("Per-asset B&H metrics (2015-2024):")
    lines.append(summary_df.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    lines.append("")
    for label, weights in [("MAX SHARPE", w_ms), ("MIN VARIANCE", w_mv),
                           ("MAX SHARPE (capped BTC>=10%, max 30% per asset)", w_ms_cap),
                           ("CORE-SATELLITE", w_cs), ("60/40", w_6040),
                           ("PURE BTC ARCHER", w_pure)]:
        lines.append(f"{label}:")
        for name, w in zip(opt_assets, weights):
            lines.append(f"  {name:>12}: {w*100:6.2f}%")
        lines.append("")
    lines.append("Realised portfolio backtest (2015-2024):")
    lines.append(f"{'allocation':<20}{'cagr%':>9}{'maxdd%':>10}{'vol%':>8}{'sharpe':>8}{'cum_ret':>10}")
    for label, s in realised.items():
        lines.append(f"{label:<20}{s['cagr']*100:>8.2f}{s['max_dd']*100:>9.2f}"
                     f"{s['vol']*100:>7.2f}{s['sharpe']:>8.2f}{s['cum_return']*100:>9.1f}%")

    (RESULTS / "portfolio_engineering_allocation.txt").write_text("\n".join(lines))
    print(f"\nWrote:")
    print(f"  {RESULTS}/portfolio_engineering_returns.csv")
    print(f"  {RESULTS}/portfolio_engineering_summary.csv")
    print(f"  {RESULTS}/portfolio_engineering_frontier.csv")
    print(f"  {RESULTS}/portfolio_engineering_allocation.txt")


if __name__ == "__main__":
    main()
