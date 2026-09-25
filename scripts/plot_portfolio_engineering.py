"""plot_portfolio_engineering.py — render efficient frontier + allocation bar.

Reads results/portfolio_engineering_*.csv and writes:
- plots/portfolio_efficient_frontier.png  (return-vol scatter + frontier)
- plots/portfolio_allocations.png         (stacked horizontal bar)
- plots/portfolio_growth_curves.png      (cum wealth 2017-08 → 2024-12)

Run after scripts/portfolio_engineering.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RESULTS = Path(__file__).resolve().parent.parent / "results"
PLOTS = Path(__file__).resolve().parent.parent / "plots"
PLOTS.mkdir(parents=True, exist_ok=True)


def plot_frontier(returns: pd.DataFrame, summary: pd.DataFrame, frontier: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.8))

    # Frontier line (sorted by vol)
    order = frontier.sort_values("vol").reset_index(drop=True)
    ax.plot(order["vol"] * 100, order["return"] * 100,
            color="#7a7a7a", lw=1.2, alpha=0.6, label="Efficient frontier", zorder=1)

    # Compute realised portfolio metrics from the returns file
    R = returns[["BTC_Archer", "AGG", "BND", "SHY", "VTI"]].to_numpy()
    portfolio_weights = {
        "max_sharpe":        [0.128, 0.000, 0.000, 0.000, 0.872],
        "min_var":           [0.0001, 0.0, 0.0, 0.9884, 0.0115],
        "max_sharpe_capped": [0.10, 0.0388, 0.2612, 0.30, 0.30],
        "60_40":             [0.00, 0.30, 0.30, 0.00, 0.40],
        "core_satellite":    [0.30, 0.20, 0.15, 0.15, 0.20],
        "pure_btc_archer":   [1.00, 0.00, 0.00, 0.00, 0.00],
    }
    real = {}
    for label, w in portfolio_weights.items():
        port_ret = (R * np.array(w)).sum(axis=1)
        cum = (1 + pd.Series(port_ret, index=returns.index)).cumprod()
        years = len(cum) / 252
        real[label] = {
            "vol": float(port_ret.std() * np.sqrt(252)) * 100,
            "ret": float(cum.iloc[-1] ** (1 / years) - 1) * 100,
        }

    # Individual asset scatter (no legend entries, just labels)
    asset_colors = {
        "BTC_Archer": "#f7931a",
        "AGG": "#2c5282", "BND": "#3182ce", "SHY": "#63b3ed", "IEF": "#4299e1",
        "VTI": "#22543d", "SPY": "#38a169", "QQQ": "#48bb78",
    }
    label_offsets = {
        # asset -> (dx, dy, fontsize, weight, ha)
        "BTC_Archer": (5, 0.0, 10, "bold", "left"),
        "SHY":        (-0.8, 1.6, 9, "normal", "right"),
        "AGG":        (-2.0, -0.2, 9, "normal", "right"),
        "BND":        (-1.0, -2.0, 9, "normal", "right"),
        "IEF":        (1.0, -2.0, 9, "normal", "left"),
        "VTI":        (1.4, 0.5, 9, "normal", "left"),
        "SPY":        (-2.0, 1.5, 9, "normal", "right"),
        "QQQ":        (1.0, -2.0, 9, "normal", "left"),
    }
    for _, row in summary.iterrows():
        a = row["asset"]
        if a not in asset_colors:
            continue
        x, y = row["vol"] * 100, row["cagr"] * 100
        ax.scatter(x, y, s=120 if a != "BTC_Archer" else 200,
                   c=asset_colors[a], edgecolor="black", linewidth=0.7, zorder=3)
        dx, dy, fs, weight, ha = label_offsets.get(a, (0.5, 0.4, 9, "normal", "left"))
        ax.annotate(a, (x, y), xytext=(x + dx, y + dy), fontsize=fs,
                    fontweight=weight, ha=ha, zorder=4)

    # Portfolio markers
    port_markers = [
        ("max_sharpe",        "Max Sharpe",            "#c53030", "X", 220),
        ("max_sharpe_capped", "Max Sharpe (capped)",   "#dd6b20", "*", 320),
        ("core_satellite",    "Core-Satellite",        "#d69e2e", "P", 200),
        ("60_40",             "60/40 baseline",        "#2b6cb0", "D", 130),
        ("min_var",           "Min Variance",          "#805ad5", "s", 110),
        ("pure_btc_archer",   "Pure BTC Archer",       "#f6ad55", "o", 110),
    ]
    for label, name, color, marker, size in port_markers:
        x, y = real[label]["vol"], real[label]["ret"]
        ax.scatter(x, y, s=size, c=color, edgecolor="black", linewidth=0.8,
                   marker=marker, zorder=5, label=name)

    ax.set_xlabel("Annualised volatility (%)")
    ax.set_ylabel("Annualised return (CAGR, %)")
    ax.set_title("Efficient frontier — BTC Archer + bonds + equity indices (2017-08 → 2024-12)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=8.5)

    fig.tight_layout()
    fig.savefig(PLOTS / "portfolio_efficient_frontier.png", dpi=160)
    plt.close(fig)
    print(f"Wrote {PLOTS / 'portfolio_efficient_frontier.png'}")


def plot_growth(returns: pd.DataFrame) -> None:
    """Cumulative wealth curves for all five allocations."""
    fig, ax = plt.subplots(figsize=(9, 5.5))
    R = returns[["BTC_Archer", "AGG", "BND", "SHY", "VTI"]].to_numpy()

    portfolios = [
        ("max_sharpe",        [0.128, 0.000, 0.000, 0.000, 0.872], "#c53030", "Max Sharpe (uncapped)"),
        ("min_var",           [0.0001, 0.0, 0.0, 0.9884, 0.0115], "#805ad5", "Min Variance"),
        ("max_sharpe_capped", [0.10, 0.0388, 0.2612, 0.30, 0.30], "#dd6b20", "Max Sharpe (BTC≥10%, ≤30% per asset)"),
        ("60_40",             [0.00, 0.30, 0.30, 0.00, 0.40], "#2b6cb0", "60/40 baseline"),
        ("core_satellite",    [0.30, 0.20, 0.15, 0.15, 0.20], "#d69e2e", "Core-Satellite (30% BTC)"),
        ("pure_btc_archer",   [1.00, 0.00, 0.00, 0.00, 0.00], "#f6ad55", "Pure BTC Archer"),
        ("VTI_BH",            [0.00, 0.00, 0.00, 0.00, 1.00], "#22543d", "VTI B&H (reference)"),
    ]
    for label, w, color, name in portfolios:
        port_ret = (R * np.array(w)).sum(axis=1)
        cum = (1 + pd.Series(port_ret, index=returns.index)).cumprod()
        lw = 2.2 if "capped" in label or "core" in label or "60_40" in label else 1.2
        ls = "-" if "capped" in label or "60_40" in label else "--"
        ax.plot(cum.index, cum.values, color=color, lw=lw, linestyle=ls, label=f"{name}")

    ax.set_yscale("log")
    ax.set_ylabel("Cumulative wealth ($, log scale)")
    ax.set_xlabel("Date")
    ax.set_title("Portfolio growth — $1 invested 2017-08-17")
    ax.grid(alpha=0.3, which="both")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PLOTS / "portfolio_growth_curves.png", dpi=160)
    plt.close(fig)
    print(f"Wrote {PLOTS / 'portfolio_growth_curves.png'}")


def plot_allocations() -> None:
    """Stacked horizontal bar of allocation weights."""
    fig, ax = plt.subplots(figsize=(9, 4.5))

    portfolios = [
        ("Pure BTC Archer",        [1.00, 0.00, 0.00, 0.00, 0.00]),
        ("Min Variance",           [0.0001, 0.0, 0.0, 0.9884, 0.0115]),
        ("60/40 baseline",         [0.00, 0.30, 0.30, 0.00, 0.40]),
        ("Max Sharpe (capped)",    [0.10, 0.0388, 0.2612, 0.30, 0.30]),
        ("Max Sharpe (uncapped)",  [0.128, 0.000, 0.000, 0.000, 0.872]),
        ("Core-Satellite",         [0.30, 0.20, 0.15, 0.15, 0.20]),
    ]
    labels = [p[0] for p in portfolios]
    weights = np.array([p[1] for p in portfolios])
    asset_names = ["BTC_Archer", "AGG", "BND", "SHY", "VTI"]
    colors = ["#f7931a", "#2c5282", "#3182ce", "#90cdf4", "#22543d"]

    y = np.arange(len(labels))
    left = np.zeros(len(labels))
    for i, (asset, color) in enumerate(zip(asset_names, colors)):
        ax.barh(y, weights[:, i], left=left, color=color, edgecolor="white",
                label=asset)
        # Label each segment with its %
        for j, w in enumerate(weights[:, i]):
            if w >= 0.05:
                ax.text(left[j] + w / 2, y[j], f"{w*100:.0f}%",
                        ha="center", va="center", fontsize=8,
                        color="white" if asset != "SHY" else "black")
        left += weights[:, i]

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Weight")
    ax.set_xlim(0, 1)
    ax.set_title("Portfolio allocations — six strategies")
    ax.legend(loc="lower right", fontsize=9, ncol=5)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(PLOTS / "portfolio_allocations.png", dpi=160)
    plt.close(fig)
    print(f"Wrote {PLOTS / 'portfolio_allocations.png'}")


def main() -> None:
    returns = pd.read_csv(RESULTS / "portfolio_engineering_returns.csv",
                          parse_dates=["date"], index_col="date")
    summary = pd.read_csv(RESULTS / "portfolio_engineering_summary.csv")
    frontier = pd.read_csv(RESULTS / "portfolio_engineering_frontier.csv")
    plot_allocations()
    plot_growth(returns)
    plot_frontier(returns, summary, frontier)


if __name__ == "__main__":
    main()
