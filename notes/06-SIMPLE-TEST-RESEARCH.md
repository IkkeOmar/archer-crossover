# 06 — SIMPLE-TEST RESEARCH: EMA-Crossover Sanity Test Patterns

## Context
Verify the Archer-Crossover engine works on real data before the full 4D HPC sweep.
Simple test: sweep over `(n_mu, x)` with 100% allocation in signal direction, on 9 tickers,
~2–3 timeframes.

---

## (a) Grid Structure

### Small grids (~3×3 to 5×5) — sanity / exploratory
Used in early-stage testing to verify the engine runs correctly.

- **OpenAlgo / vectorbt tutorial** uses a 4×4 EMA fast/slow grid as the *first sweep*
  before escalating to larger grids. Example: `fast_lengths = [5, 10, 15, 20]`,
  `slow_lengths = [30, 40, 50, 60]` → 16 valid combos after filtering `fast < slow`.
  Source: https://openalgo.in/python/optimization

- **fastquant blog** (3-line grid search) shows a minimal 2-parameter grid as the
  canonical first step — confirm the engine works, then expand.
  Source: https://enzoampil.github.io/fastquant-blog/grid+search/backtest/2020/04/20/backtest_with_grid_search.html

- **durebel/crypto-backtester** (GitHub) ships an `ema_crossover` demo strategy with
  a parameter sweep that outputs a full heatmap — standard pattern is to start with
  a coarse grid (5–10 combos) as a sanity check before the full grid.
  Source: https://github.com/durebel/crypto-backtester

### Large grids (~20×20 to 50×50) — production optimization
- **vectorbt PRO** and **marketcalls vectorbt-backtesting-skills** show broadcasting
  across thousands of combos simultaneously (the killer feature). A 50×50 grid =
  2,500 combos is unremarkable for vectorized execution.
  Source: https://github.com/marketcalls/vectorbt-backtesting-skills

- **Recommended practice (OpenAlgo):** Keep grids small initially. Each extra value
  multiplies work AND the chance of cherry-picking a lucky winner. Expand only after
  confirming the engine is sound.

### Archer-specific recommendation
For the simple sanity test:
- `n_mu`: coarse sweep — `[1, 5, 10, 25, 50]` (5 values) → 5×5 = 25 combos
- `x`: `[0, 25, 50, 75, 100]` (5 values)
- This is a **5×5 = 25-combo grid per ticker per timeframe** — trivial to run,
  fast enough to iterate, large enough to see a landscape.

---

## (b) Timeframes Used for Sanity Tests

Commonly in published backtest tutorials and academic papers:

| Timeframe | Use case | Source |
|---|---|---|
| **1D** | Standard sanity test; 10+ years of data; cheapest to run | yfinance default |
| **4h** | Reduced grid; 2 years of data; captures intraday structure | SPEC.md + arxiv study |
| **1h** | Walk-forward validation; 2 years | arxiv:2602.10785 used 1h–60min |
| **15m** | Crypto/short-term; limited history (60 days yfinance); BTC/ETH has 5+ yrs via ccxt | SPEC.md |

**The arxiv paper (2026)** — "A novel approach to trading strategy parameter optimization using
double out-of-sample and walk-forward" — tested EMA crossover across **six intraday
frequencies from 1 min to 60 min** on BTC, ETH, BNB. Key finding: with 0.1% fees,
only intervals **above 30 minutes** were profitable; below 30 min failed to overcome costs.
Break-even was ~0.4%/trade.
Source: https://arxiv.org/html/2602.10785v1

**Recommendation for Archer simple test:**
- 1D (full history, all 9 tickers) + 1h (2 years, all 9 tickers) + 15m (BTC/ETH only, via ccxt)
- 3 timeframes total keeps the sanity check fast while covering the main regimes.

---

## (c) Why 100% Allocation Is the Right Default for the Sanity Test

**Reasoning from published patterns:**

1. **Simplicity — no confounding variables.** The `durebel/crypto-backtester` README explicitly
   warns: validate the strategy *net of costs* before adding any position-sizing complexity.
   Starting with 100% allocation isolates whether the *signal* has edge; scaling introduces a
   new variable that can mask signal quality.

2. **Standard practice in tutorials.** VectorBT and backtesting.py tutorials almost universally
   use `size=1.0` (100% of available capital) for the first pass. Position sizing is a
   second-order concern after signal quality is established.

3. **Archer's own design.** SPEC.md Section 2.2 shows the position rule is *already*
   timeframe-dependent (1D can do partial allocation; sub-daily uses full long/short).
   Adding `bear_alloc` as a third/fourth dimension in the sanity test defeats the purpose:
   you're testing whether the engine runs correctly, not whether bear_alloc=0.5 beats 0.75.

4. **Cost sensitivity comes AFTER.** The arxiv paper included a cost sensitivity analysis as a
   *post-hoc sanity check*, not as part of the initial sweep. Start clean, then add complexity.

**Bottom line:** 100% allocation (always enter when signal fires, full position) is the
correct default because it asks one question at a time: *does the (n_mu, x) signal have edge?*
Once that is established, position sizing (bear_alloc, Kelly fraction, etc.) can be explored
as a separate dimension.

---

## (d) Metrics to Report

Standard set from published backtest tools:

| Metric | Where it's reported |
|---|---|
| **Sharpe ratio** | Universal — vectorbt, backtesting.py, OpenAlgo, arxiv paper |
| **Total return (%)** | Universal — all sources |
| **Max drawdown (%)** | Universal — all sources |
| **CAGR (%)** | OpenAlgo, arxiv paper, durebel backtester |
| **Calmar ratio** (CAGR / Max DD) | SPEC.md baselines; vectorbt PRO |
| **Win rate (%)** | fastquant, OpenAlgo, backtesting.py |
| **Number of trades** | fastquant, OpenAlgo, arxiv paper |
| **Profit factor** | backtesting.py, marketcalls skills |

**Consensus minimum for a publishable sanity test:** Sharpe, total return, max drawdown, trade count.

**Per the arxiv paper's methodology:**
- Walk-forward optimization with Robust Sharpe Ratio as the primary ranking metric
- Out-of-sample testing on unseen data (single execution per walk-forward step)
- Cost sensitivity analysis (fees, slippage) as a post-hoc check

**Archer-specific outputs per (ticker, timeframe):**
- Heatmap: Sharpe over (n_mu, x) → 2D surface
- Equity curve overlay: Archer best zone vs. vanilla EMA-cross vs. buy-and-hold
- Metrics CSV: Sharpe, CAGR, max DD, Calmar, total return, win rate, # trades

---

## (e) Common Pitfalls When Sweeping Over Delay Parameters

### 1. Overfitting to delay variance
- **The arxiv paper explicitly warns:** varying training/testing window lengths in walk-forward
  optimization has a *large effect* on Sharpe — this means delay parameters can appear to have
  edge when the real driver is the window size, not the delay. Fix your train/test split
  before sweeping delay.
  Source: https://arxiv.org/html/2602.10785v1

- **OpenAlgo tutorial warning:** "Finding the single highest-scoring parameter combination
  is easy and almost always a trap. The real skill is finding a *region* of settings that
  all work." A single lucky (n_mu, x) pixel in a 50×50 heatmap is noise.
  Source: https://openalgo.in/python/optimization

- **durebel/crypto-backtester** approach: `sweep` always returns the *full* grid
  (not just winners); `stats` provides deflated-Sharpe / PBO / multiple-testing inference
  to account for how many combos were tried.

### 2. Look-ahead bias
- The arxiv paper identifies this as the most common unreported issue in trading strategy
  papers — optimizing on data designated as out-of-sample. Archer's SPEC.md addresses
  this with a warmup period (3× longest EMA) and a planned walk-forward split in Phase 2.

### 3. Ignoring costs in the sweep
- The arxiv paper found break-even at ~0.4%/trade for 60-min BTC; below 30-min all
  strategies lost to costs. Archer's 0.05% default is conservative but realistic for
  liquid US equities — but sub-1h crypto may need higher cost assumptions.

### 4. Cherry-picking the best ticker/timeframe combo
- With 9 tickers × 3 timeframes = 27 combinations, the *best* result is likely a lucky
  draw. Report all combinations, not just the winner. Cross-ticker consistency (same
  parameter zone works across multiple tickers) is the real signal.

### 5. Not running a null control
- The arxiv paper uses block bootstrap to compare the EMA strategy against randomly
  generated EMA parameter sets. If the strategy can't beat random on synthetic data,
  the real-market edge may be data snooping. Archer's Phase 3 (synthetic-market test)
  mirrors this approach.

---

## Practical Checklist for Archer Simple Test

```
Grid:        5 × 5 (n_mu × x)  →  25 combos per ticker per timeframe
Timeframes:  1D  +  1h  +  15m (BTC/ETH only)  →  3 total
Allocation:  100% long on bullish cross (no bear_alloc)
Tickers:     SPY, QQQ, IWM, AAPL, GOOGL, BTC-USD, ETH-USD, GLD, SLV  →  9
Metrics:     Sharpe, total return, max DD, CAGR, Calmar, win rate, # trades
Output:      Heatmap per ticker per timeframe + equity overlay vs. baselines
Pitfall:     Don't report only the best ticker; show all 9. Look for consistent zones.
```

---

## Sources
- OpenAlgo Parameter Optimisation: https://openalgo.in/python/optimization
- fastquant Grid Search: https://enzoampil.github.io/fastquant-blog/grid+search/backtest/2020/04/20/backtest_with_grid_search.html
- durebel/crypto-backtester (EMA crossover + walk-forward validation): https://github.com/durebel/crypto-backtester
- marketcalls/vectorbt-backtesting-skills (parameter optimization patterns): https://github.com/marketcalls/vectorbt-backtesting-skills
- arxiv paper — walk-forward EMA optimization on BTC/ETH intraday (1min–60min): https://arxiv.org/html/2602.10785v1
- vectorbt PRO strategy optimization: https://vectorbt.pro/features/optimization/strategy-optimization/
- backtesting.py (standard metrics): https://kernc.github.io/backtesting.py/
