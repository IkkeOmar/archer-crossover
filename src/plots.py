"""plots.py — heatmaps, 3D surfaces, equity curves.

Outputs go to results/plots/heatmap/, results/plots/3d/, results/plots/equity/.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for cluster use
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PLOTS_DIR = Path(__file__).resolve().parent.parent / "results" / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
HEATMAP_DIR = PLOTS_DIR / "heatmap"
HEATMAP_DIR.mkdir(exist_ok=True)
SURFACE_DIR = PLOTS_DIR / "3d"
SURFACE_DIR.mkdir(exist_ok=True)
EQUITY_DIR = PLOTS_DIR / "equity"
EQUITY_DIR.mkdir(exist_ok=True)


def heatmap_2d(
    grid: np.ndarray,           # 2D (n_mu, x) array
    n_mu_values: list,
    x_values: list,
    title: str,
    out_path: Path,
    metric_name: str = "Sharpe",
    cmap: str = "RdYlGn",
    center_at_zero: bool = True,
) -> Path:
    """2D heatmap: x-axis = n_mu, y-axis = x (or vice versa — chosen to fit canvas)."""
    fig, ax = plt.subplots(figsize=(8, 6))
    vmin = -2 if center_at_zero else None
    vmax = 2 if center_at_zero else None
    im = ax.imshow(
        grid,
        aspect="auto",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        origin="lower",
    )
    ax.set_xticks(range(len(n_mu_values)))
    ax.set_xticklabels(n_mu_values)
    ax.set_yticks(range(len(x_values)))
    ax.set_yticklabels([f"{x:.2f}" for x in x_values])
    ax.set_xlabel("n_mu (mean delay, candles)")
    ax.set_ylabel("x (zero-delay probability)")
    ax.set_title(title)
    plt.colorbar(im, ax=ax, label=metric_name)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def surface_3d(
    grid: np.ndarray,           # 2D (n_mu, x) array
    n_mu_values: list,
    x_values: list,
    title: str,
    out_path: Path,
    metric_name: str = "Sharpe",
) -> Path:
    """3D surface plot of (n_mu, x, metric)."""
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")
    X, Y = np.meshgrid(range(len(n_mu_values)), range(len(x_values)))
    Xl = np.array(n_mu_values)[X]
    Yl = np.array(x_values)[Y]
    surf = ax.plot_surface(Xl, Yl, grid, cmap="viridis", edgecolor="none")
    ax.set_xlabel("n_mu")
    ax.set_ylabel("x")
    ax.set_zlabel(metric_name)
    ax.set_title(title)
    fig.colorbar(surf, ax=ax, shrink=0.5)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def equity_curves(
    curves: dict[str, np.ndarray],
    title: str,
    out_path: Path,
    log_scale: bool = True,
) -> Path:
    """Overlay multiple equity curves. Use log scale for long horizons."""
    fig, ax = plt.subplots(figsize=(10, 6))
    for label, eq in curves.items():
        if log_scale and np.all(eq > 0):
            ax.plot(eq, label=label)
        else:
            ax.plot(eq, label=label)
    ax.set_xlabel("Candles")
    ax.set_ylabel("Equity ($)")
    ax.set_title(title)
    if log_scale:
        ax.set_yscale("log")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_sweep_results(
    csv_path: str | Path,
    out_dir: Path | None = None,
    ticker: str = "",
    timeframe: str = "",
    metric: str = "sharpe",
) -> list[Path]:
    """Generate all heatmaps + 3D surfaces for one sweep CSV.

    Returns list of output paths.
    """
    df = pd.read_csv(csv_path)
    out_dir = Path(out_dir or HEATMAP_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    # Group by ema_pair + bear_alloc_1d
    for ema_pair in df["ema_pair"].unique():
        for ba in df["bear_alloc_1d"].unique():
            sub = df[(df["ema_pair"] == ema_pair) & (df["bear_alloc_1d"] == ba)]
            if len(sub) == 0:
                continue
            pivot = sub.pivot_table(
                index="x", columns="n_mu", values=metric, aggfunc="first"
            )
            n_mu_vals = list(pivot.columns)
            x_vals = list(pivot.index)
            grid = pivot.values

            base = f"{ticker}_{timeframe}_{ema_pair.replace('/', '-')}_ba{ba}_{metric}"
            title = f"{ticker} {timeframe} | EMA {ema_pair} | bear_alloc={ba} | {metric}"

            p = heatmap_2d(
                grid,
                n_mu_vals,
                x_vals,
                title,
                out_dir / f"{base}_heatmap.png",
                metric_name=metric.upper(),
            )
            paths.append(p)

            p = surface_3d(
                grid,
                n_mu_vals,
                x_vals,
                title,
                out_dir / f"{base}_3d.png",
                metric_name=metric.upper(),
            )
            paths.append(p)
    return paths


def plot_best_vs_baselines(
    csv_path: str | Path,
    npz_path: str | Path,
    ticker: str,
    timeframe: str,
    metric: str = "sharpe",
) -> Path:
    """Plot equity curves: Archer best zone vs buy-and-hold vs vanilla EMA-cross.

    Returns path to plot.
    """
    df = pd.read_csv(csv_path)
    raw = np.load(npz_path)
    prices = np.asarray(raw["prices"], dtype=np.float64)

    # Best Archer params
    best = df.loc[df[metric].idxmax()]
    # Recompute equity for the best combo
    from .archer_engine import backtest_arrows, buy_and_hold, vanilla_ema_cross
    ema_pair = tuple(int(x) for x in best["ema_pair"].split("/"))
    res_archer = backtest_arrows(
        prices,
        n_mu=int(best["n_mu"]),
        x_zero=float(best["x"]),
        bear_alloc=float(best["bear_alloc_1d"]),
        fast_period=ema_pair[0],
        slow_period=ema_pair[1],
    )
    res_bnh = buy_and_hold(prices)
    res_vanilla = vanilla_ema_cross(prices, fast_period=ema_pair[0], slow_period=ema_pair[1])

    out_path = EQUITY_DIR / f"{ticker}_{timeframe}_best_vs_baselines.png"
    return equity_curves(
        {
            f"Archer (n_mu={int(best['n_mu'])}, x={best['x']:.2f}, {metric}={best[metric]:.2f})": res_archer.equity,
            "Buy-and-hold": res_bnh.equity,
            f"Vanilla EMA-cross ({ema_pair[0]}/{ema_pair[1]})": res_vanilla.equity,
        },
        f"{ticker} {timeframe} — Archer best zone vs baselines",
        out_path,
        log_scale=True,
    )


def main():
    """CLI: python3 -m src.plots <csv_path> [--npz npz_path] [--metric sharpe]"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", help="Path to sweep CSV")
    parser.add_argument("--npz", help="Path to sweep NPZ (for equity curves)")
    parser.add_argument("--metric", default="sharpe")
    parser.add_argument("--ticker", default="")
    parser.add_argument("--timeframe", default="")
    args = parser.parse_args()
    paths = plot_sweep_results(args.csv, ticker=args.ticker, timeframe=args.timeframe, metric=args.metric)
    print(f"Generated {len(paths)} heatmaps/surfaces")
    for p in paths:
        print(f"  {p}")
    if args.npz:
        p = plot_best_vs_baselines(args.csv, args.npz, args.ticker, args.timeframe, args.metric)
        print(f"  {p}")


if __name__ == "__main__":
    main()
