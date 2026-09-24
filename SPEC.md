# SPEC.md — Archer-Crossover Experiment

**Status:** Draft v0.1 — 2026-09-24
**Owner:** Omar Jennane (s214473, DTU)
**AI:** Hermes (MiniMax-M3)
**Repo:** github.com/IkkeOmar/archer-crossover
**Compute target:** DTU HPC (LSF 10)

---

## 1. Motivation

Archers, when shooting consciously, tend to tense muscles and miss. Professionals solve this with a randomized trigger delay — the conscious decision fires, then a stochastic wait before the finger actually moves.

**Hypothesis:** A delayed-decay EMA crossover strategy (where entry is delayed by a Gaussian-distributed number of candles after the cross, with a flat probability of zero delay) may exhibit different risk-adjusted return characteristics compared to immediate-cross strategies.

This experiment is exploratory and quantitative. We will sweep parameter space and use Monte Carlo to test robustness.

---

## 2. Strategy Definition

### 2.1 Entry Rule

When the fast EMA crosses the slow EMA (cross-up = bullish, cross-down = bearish):

1. **Sample delay** `n ~ max(0, round(|N(μ_n, σ_n)|))` for each candle
2. **Zero-delay probability:** with probability `x%`, `n = 0` (immediate entry)
3. **After delay:** verify that the original cross direction is still valid (i.e. fast EMA is still on the same side of slow EMA as the original cross). If not → skip this signal.
4. **If valid:** enter position per timeframe rule.

### 2.2 Position Rule per Timeframe

| Timeframe | Bullish (verify passed) | Bearish (verify passed) |
|---|---|---|
| **1D** | +100% long | sweep over {0%, 50%, 75%, 100% long} — never short |
| **1h, 4h, 15m, 5m, 3m, 2m, 1m** | +100% long | −100% short |

**Rationale:** daily market is asymmetric upward — full shorting has poor risk-adjusted properties historically. Lower timeframes allow full short because mean-reversion is more symmetric.

### 2.3 Exit Rule

Hold position until the next valid cross (after delay + verify). No stop-loss, no take-profit in Phase 1. Position reverses per the table above.

### 2.4 Cost Model

- Default: 0.05% per trade (slippage + commission realistic estimate for liquid US equities)
- Parameter `cost_bps` can be swept

### 2.5 Warmup

Hold cash during warmup (= 3× longest EMA period) to avoid look-ahead bias.

### 2.6 Initial Capital

$100,000 USD per backtest.

---

## 3. Parameter Space (4D)

| Symbol | Description | Default Range | Type |
|---|---|---|---|
| `n_mu` | Delay distribution mean (candles) | [1, 50] | int, step 1 |
| `x` | P(zero-delay) | [0%, 100%] step 5% | float |
| `bear_alloc_1d` | Bearish allocation on 1D only | {0, 0.5, 0.75, 1.0} | categorical |
| `ema_pair` | (fast, slow) EMA periods | {(9,21), (12,26), (20,50)} | categorical |

**Default grid (Phase 1):**
- `n_mu`: 1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50 → 11 values
- `x`: 0%, 25%, 50%, 75%, 100% → 5 values
- `bear_alloc_1d`: 0, 0.5, 0.75, 1.0 → 4 values
- `ema_pair`: 3 values

→ Per ticker per timeframe: **11 × 5 × 4 × 3 = 660 backtests**
→ Plus reduced grid for non-1D (no bear_alloc): 11 × 5 × 3 = 165 per timeframe
→ Total Phase 1: 11 tickers × (660 daily + 7 × 165 sub-daily) = 11 × (660 + 1155) = **19,965 backtests**

If 660 takes ~5 min serial / ~30s parallel (numpy vectorized), then full Phase 1 ≈ **15-20 min parallelized**.

### 3.1 Gaussian Delay Sampling

```
n = 0                       with probability x
n = max(1, round(|N(μ_n, σ_n)|))   with probability 1-x
```

Default `σ_n = μ_n / 2`. Can be swept in Phase 3.

---

## 4. Tickers (11)

| Ticker | Asset class | Source |
|---|---|---|
| SPY | Broad US (S&P 500 ETF) | yfinance |
| QQQ | NASDAQ-100 ETF | yfinance |
| IWM | Small-cap ETF | yfinance |
| AAPL | Mega-cap single stock | yfinance |
| GOOGL | Mega-cap single stock | yfinance |
| BTC-USD | Crypto | yfinance (daily) + ccxt (sub-daily) |
| ETH-USD | Crypto | yfinance (daily) + ccxt (sub-daily) |
| GLD | Gold ETF | yfinance |
| SLV | Silver ETF | yfinance |

---

## 5. Timeframes

| Timeframe | Coverage (yfinance) | Coverage (ccxt) | History |
|---|---|---|---|
| 1D | All tickers | All tickers | 10+ years |
| 4h | All tickers (max 730 days) | All tickers | 2 years |
| 1h | All tickers (max 730 days) | All tickers | 2 years |
| 15m | All tickers (max 60 days) | BTC, ETH (5+ years) | varies |
| 5m | All tickers (max 60 days) | BTC, ETH (5+ years) | varies |
| 3m | not available | BTC, ETH | varies |
| 2m | not available | BTC, ETH | varies |
| 1m | All tickers (max 7 days) | BTC, ETH | very limited |

**Practical split:** 1D = full grid. 1h/4h = reduced grid. 15m/5m/3m/2m/1m = BTC/ETH only.

---

## 6. Monte Carlo Robustness (Phase 2)

For each (ticker, timeframe) pair, identify top-3 (n_mu, x) zones from Phase 1 heatmap by Sharpe ratio. Then:

- Run 1000 backtests per zone, each with different random seed for delay sampling
- Compute distribution of Sharpe, CAGR, max DD
- Robustness metric: P(Sharpe > 0) and P(Sharpe > Phase 1 zone median)

---

## 7. Comparison Baselines

For each (ticker, timeframe):
1. **Buy-and-hold** — passive position from start
2. **Vanilla EMA-cross** — same EMA pairs but delay = 0, no Gaussian, always enter

Compare Archer vs. both baselines on:
- Sharpe ratio
- CAGR
- Max drawdown
- Calmar ratio
- Total return

---

## 8. Synthetic-Market Test (Phase 3, QuantGuild-inspired)

Generate synthetic price series with:
- **GBM** (geometric Brownian motion, baseline randomness)
- **Block bootstrap** (resample historical return blocks — preserves volatility clustering)
- **Trending series** (constant drift)
- **Mean-reverting** (Ornstein-Uhlenbeck)

Run Archer + baselines on each. If Archer outperforms on real markets but underperforms on synthetic → evidence of market structure being exploited. If similar performance → evidence of data snooping.

---

## 9. Output Specification

Per (ticker, timeframe) combination:
1. **Heatmap** — Sharpe ratio over (n_mu, x), 2D
2. **3D surface** — Sharpe over (n_mu, x, bear_alloc_1d), 3D, for 1D only
3. **Equity curves** — log-scale, Archer best zone vs. baselines, overlay
4. **Metrics CSV** — Sharpe, CAGR, max DD, Calmar, total return, win rate, # trades

Plus global summary:
5. **Cross-ticker comparison** — heatmap of best (n_mu, x) per ticker per timeframe
6. **LaTeX report** — final deliverable with all plots and explanations

---

## 10. Compute Plan (DTU HPC)

- One LSF job per (ticker, timeframe) combination → 11 × 8 = 88 jobs max, typically ~40 (skip unavailable combinations)
- Each job: `-n 8 cores`, `-W 02:00`, `-R "rusage[mem=4GB]"`
- Submission via `submit_array.sh` wrapper
- Results: each job writes to `results/<ticker>_<timeframe>.csv` and `.npz`
- Aggregation script combines into final summary

---

## 11. Phases

- **Phase 1** (this PR): data + engine + sweep + heatmaps/3D + comparison
- **Phase 2** (after Phase 1 inspected): Monte Carlo robustness on top zones
- **Phase 3** (after Phase 2): synthetic-market validation + options-hedge under-driver model
- **Phase 4** (final): LaTeX report with all findings

---

## 12. Open Questions

- [x] QuantGuild relevance — researched 2026-09-24; educational reference only, no turnkey backtest library. Lecture 97 (3 Backtesting Pitfalls) is directly relevant for our strategy-vs-noise framework. QuantGuild techniques to adopt: walk-forward validation, out-of-sample split, economic interpretability check.
- [ ] Options-hedge modeling — deferred to Phase 3, conservative 15% drag on gains when hedging
- [ ] σ_n sensitivity — default μ_n/2, sweep in Phase 3
- [ ] Should we add more EMA pairs? — TBD after Phase 1 results
- [ ] Slippage realism — 0.05% default, may need to adjust per asset class
- [ ] Walk-forward validation + OOS split — add to Phase 2 (from QuantGuild finding)

---

## 13. Versioning

- v0.1 — initial spec, 2026-09-24
- (future) v0.2 after Phase 1 results inform Phase 2 design
- (future) v0.3 after Phase 2 informs Phase 3 design
- v1.0 — final LaTeX report
