# 01-RESEARCH-LOG: Python Vectorized Backtesting Libraries

**Date:** 2026-09-24
**Task:** Evaluate backtesting libraries for ~20,000 param combinations × 11 tickers × 8 timeframes

---

## TL;DR — Recommendation

**Use vectorbt (OSS) + your own indicator layer.**
For 20,000+ parameter sweeps, vectorbt is the only library built for this scale.
Backtrader is loop-based (slow for sweeps). Zipline-reloaded is event-driven and not designed for massive parameter grids.

---

## 1. vectorbt

| Dimension | Details |
|-----------|---------|
| **Speed** | 10,000 param combinations in seconds. Single SMA crossover: ~200ms vs Backtrader's ~12s (60× faster). Processes millions of orders in ~70–100ms on M1. Uses NumPy arrays + Numba JIT for native vectorization of parameter grids — no looping. |
| **Custom Stochastic Logic** | ✅ Full flexibility via `vectorbt.indicators` with custom `indicator_config` + Numba-compiled close. Supports `vbt.IndicatorFactory` for fully custom logic in Python/Numba. Stochastic (slow %K, slow %D) can be implemented from scratch or via `ta` library. |
| **Maintenance** | Active (polakowo/vectorbt, ~8.4k stars). Last commit Sep 2026. PRO version adds parallelization, pattern recognition, portfolio optimization. OSS version is production-stable. |
| **Data Input** | Native pandas DataFrame/Series, CSV, Parquet, SQL. Built-in `Data` class that aligns multi-symbol data. Accepts `pd.DataFrame` with OHLCV columns directly. |
| **HPC Cluster** | ✅ No GUI deps. Pure Python + Numba. PRO adds parallel/distributed execution (chunking + `ChunkedMap`). OSS is single-threaded but scales vertically. Slurm-friendly — just `pip install` + Python script. |

**Key advantage for your use case:** Parameter sweep across 11 tickers × 8 timeframes is a first-class use case — done natively in NumPy, not a nested loop.

---

## 2. backtrader (cloudQuant fork)

| Dimension | Details |
|-----------|---------|
| **Speed** | Loop-based event engine. Simple SMA cross on AAPL daily (2020–2024): ~12 seconds. Parameter optimization uses `cerebro.run()` with `optstrategy` but parallelizes via `maxcpus=N`. The fork claims 45%+ faster than upstream via Cython optimizations. |
| **Custom Stochastic Logic** | ✅ Fully customizable via `bt.Indicator` abstract base. Can implement custom stochastic, delay logic, same-side verification as a Python class. Widely used, extensive examples. |
| **Maintenance** | CloudQuant fork is **actively developed** (1,212 commits, last 2026). Upstream (backtrader2) is dormant — community fork only. The fork adds AI-native workflow, MCP server, tick-to-daily strategies. |
| **Data Input** | CSV (GenericCSVData, YahooFinance), pandas DataFrame (PandasData), many built-in feeds. Very flexible. |
| **HPC Cluster** | ✅ No GUI deps. Headless Python. `cerebro.run(maxcpus=N)` for multi-process optimization. Slurm-friendly. |

**Caveat:** Parameter sweep across 20,000 combinations is not what it was designed for — it will loop through each combination. Expect hours, not seconds.

---

## 3. zipline-reloaded (stefan-jansen)

| Dimension | Details |
|-----------|---------|
| **Speed** | Event-driven (bar-by-bar), not vectorized. Designed for single-strategy evaluation, not parameter sweeps. Performance is slow per backtest; no native parallel parameter sweep. |
| **Custom Stochastic Logic** | ✅ Can implement any logic in `def handle_data(self, context, data):`. Custom stochastic delay + same-side verification straightforward. Full Python control. |
| **Maintenance** | **Active** — Stefan-Jansen's fork is the maintained version (~3k stars). Updated for Python 3.11+, has conda-forge support, activeDiscourse community. Quantopian's original zipline is dead. |
| **Data Input** | Uses `zipline.data.load_from_yahoo` (requires API key) or custom CSVs via `pandas_datareader`. Has a strict data format (OHLCV with datetime index). More ceremony to ingest CSV. |
| **HPC Cluster** | ✅ No GUI deps. CLI-based `zipline run`. Slurm-friendly. But not designed for massive param sweeps — you'd script the sweep loop yourself. |

**Caveat:** The event-driven model is fundamentally incompatible with massive parallel parameter sweeps. 20,000 combos would take days.

---

## 4. Others Worth Knowing

| Library | Notes |
|---------|-------|
| **NautilusTrader** | Rust/Python, event-driven, professional-grade. Very fast in live mode, but backtesting is event-based (not vectorized). Designed for live execution, not parameter sweeps. |
| **backtesting.py (kernc)** | Simple, interactive HTML plots. Not designed for large-scale parameter sweeps. Good for prototyping. |
| **PyPortfolioOpt / quantstats** | Portfolio optimization and performance attribution, not backtesting engines. Complementary. |

---

## 5. Indicator Computation Libraries (for your EMA + Stochastic)

| Library | Pros | Cons |
|---------|------|------|
| **pandas_ta** | Pure Python, 130+ indicators, DataFrame extension (`df.ta.ema()`), no C dependencies, very active. Fast enough for most use cases. | Slower than TA-Lib for huge datasets. |
| **TA-Lib** | C implementation, 200+ functions, fastest possible. Industry standard. | Requires separate C library install (`pip install TA-Lib` is a wrapper). Can be tricky on some HPC systems (needs system-level install). |
| **finta** | Simple, pandas-native, ~50 indicators. No C deps. | Less maintained than pandas_ta; smaller community. |

**Recommendation:** Use **pandas_ta** — pure Python, no system-level deps to install on HPC, reasonable speed (NumPy-backed), easy to pip install in a venv on the cluster.

---

## Summary Table

| Feature | vectorbt | backtrader (cloudQuant) | zipline-reloaded |
|---------|----------|-------------------------|-------------------|
| **Param sweep speed** | ⚡⚡⚡ Seconds (vectorized) | 🐢 Hours (loop, multi-core helps) | 🐢 Days (event-driven) |
| **Custom stochastic** | ✅ Numba/Python | ✅ Python class | ✅ Python |
| **Maintenance** | Active (OSS + PRO) | Active fork (2026) | Active (Stefan-Jansen) |
| **Data input** | pd.DataFrame, CSV, Parquet | pd.DataFrame, CSV, feeds | CSV, Yahoo API |
| **HPC-ready** | ✅ (PRO: parallel) | ✅ (multi-process) | ✅ (CLI) |
| **GUI plotting** | Interactive (Jupyter) | Optional (matplotlib) | None |
| **Your use case fit** | ⭐⭐⭐ Ideal | ⭐ OK (slow for sweeps) | ⭐ Poor (arch. mismatch) |

---

## Actionable Next Steps

1. **Use vectorbt** as the backtest engine — its native param sweep is exactly your 20,000-combo use case.
2. **Use pandas_ta** for EMA + Stochastic indicators (or compute manually in pure NumPy for max speed).
3. **Batch your sweep** across 11 tickers × 8 timeframes as a single vectorbt call per param combo (all tickers at once).
4. **PRO consideration:** If the sweep is still too slow, vectorbt PRO's parallel/chunked execution would cut cluster time significantly.

---

## 6. QuantGuild GitHub Research — EMA-Crossover, Monte Carlo, Synthetic Markets

**Org repos:** `https://github.com/Quant-Guild` (6 small repos) + `https://github.com/romanmichaelpaolucci/Quant-Guild-Library` (main educational repo, 120+ video lectures with Jupyter notebooks)

---

### (a) EMA-Crossover Backtesting

- **Direct reference:** Lecture 97 notebook (`qebp.ipynb`) — "3 Backtesting Pitfalls" uses **moving average crossovers** as a running example (tested 3/5 vs 7/12 parameter sets).
- **Key finding from QuantGuild:** The 7/12 crossover had a decent Sharpe in-sample but went negative live — demonstrates exactly how EMA-crossover strategies fail from overfitting.
- **No dedicated EMA-crossover framework repo** exists here; the educational content explains the failure modes rather than providing a backtesting library.
- **Verdict:** Usable as pedagogical reference for building your own; not a ready-made backtesting tool.

---

### (b) Monte Carlo Simulation / Parameter Sweeps

- **Lecture 73:** "How to Price Options with Monte Carlo Simulation" — Monte Carlo for Black-Scholes option pricing.
- **Lecture 2:** "Control Variates for Variance Reduction" — directly applicable to reducing variance in parameter-sweep MC runs.
- **Lecture 19:** "Monte Carlo Simulation and Black-Scholes for Pricing Options" — MC with Black-Scholes.
- **No parameter-sweep framework** in the QuantGuild repos; the content covers building blocks (variance reduction, MC convergence).
- **Verdict:** Reference material for MC implementation; no turnkey sweep code.

---

### (c) Synthetic Market Generation (Block Bootstrap, GBM, Regime-Switching)

| Topic | Repo / Lecture | File | Description |
|---|---|---|---|
| Correlated GBM | `Quant-Guild/Correlated_Brownian_Motion` | `Simulating Correlated Brownian Motions.ipynb` | Simulates correlated Brownian motions (multi-asset GBM); basic but clean |
| Fractional Brownian Motion | 2025 Lecture 25 | `fbm.ipynb` | Davies-Harte method for fbM (long-memory/rough-vol style processes) |
| Regime Switching | 2025 Lecture 74 | `final_product.py`, `video_code.py` | Markov Chain regime-switching bot with IB integration — **directly relevant** for regime-aware synthetic generation |
| GBM / Bachelier | `Quant-Guild/Bachelier_Model` | `Bachelier Model.ipynb` | Bachelier (normal) model + Monte Carlo verification; arithmetic vs log-normal |
| Synthetic data via MC | `gaussiancookbook.com` (referenced) | — | "Gaussian Cookbook" — recipes for simulating stochastic processes (author's external project) |

- **Block bootstrap is NOT covered** by QuantGuild (search returned unrelated R packages).
- **Verdict:** Code exists for correlated GBM and regime-switching; block bootstrap requires a different source.

---

### Strategy vs. Noise: Key Techniques from QuantGuild

QuantGuild's most directly relevant content is **Lecture 97** — "3 Backtesting Pitfalls That Ruin Your Strategy" (YouTube + `qebp.ipynb`). Techniques for testing whether a strategy exploits **real structure vs. fits noise**:

1. **Walk-forward validation** — roll a window forward instead of picking best param on full history; only use parameterizations robust across splits.
2. **Economic interpretability** — if a parameter set (e.g., 7/12 EMA) has an economic story and beats a mechanically better-looking set (3/5), it is more likely real structure.
3. **Out-of-sample testing** — always hold back a time slice the strategy was not trained on.
4. **Survivorship-bias-free universe** — include delisted/bankrupt firms at each point in time.
5. **Look-ahead bias audit** — ensure all signals and calculations use only information available at time *t* (filtration-adapted).

**Practical recommendation from QuantGuild:** If your EMA-crossover strategy only looks good on one specific parameterization and degrades sharply on nearby ones, that's a signature of fitting noise. Walk-forward + synthetic market testing (regime-switching, GBM with realistic vol regimes) is the recommended validation path.

---

### Quick Links

| Resource | URL |
|---|---|
| Main educational library | https://github.com/romanmichaelpaolucci/Quant-Guild-Library |
| Backtesting pitfalls notebook | `…/2026 Video Lectures/97. 3 Backtesting…/qebp.ipynb` |
| Regime-switching bot | `…/2025 Video Lectures/74. Markov Chain Regime Switching…/final_product.py` |
| Correlated Brownian Motion | https://github.com/Quant-Guild/Correlated_Brownian_Motion |
| Fractional Brownian Motion | `…/2025 Video Lectures/25. How to Simulate Fractional Brownian Motion…/fbm.ipynb` |
| Gaussian Cookbook | https://gaussiancookbook.com |
| Author's SSRN paper list | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5332011 |
