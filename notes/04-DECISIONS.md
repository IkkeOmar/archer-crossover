# 04-DECISIONS.md

**Purpose:** Record design decisions with rationale. Future-me will read this to remember WHY we chose something, not just WHAT.

---

## D1: 4D parameter space (not 5D+)

**Decision:** Sweep only (n_mu, x, bear_alloc_1d, ema_pair). Other parameters fixed.

**Considered:** Sweeping σ_n (delay std), cost_bps, EMA smooth type, position-size rules.

**Why not:** Multiple comparisons / data snooping. With 5D we'd have ~50k+ backtests per ticker, almost guaranteeing spurious "good" zones. 4D is the maximum that lets us credibly search the space. Anything else goes in Phase 3 if results warrant.

---

## D2: Bear-allocation only on 1D

**Decision:** Daily timeframe can be 0/50/75/100% long on bearish; sub-daily timeframes are full short (-100%).

**Rationale:** Daily US equity market has historically asymmetric upward drift (~+8%/year real return). Full shorting on 1D has poor Sharpe historically. Sub-daily timeframes are more mean-reverting and benefit from full short on bearish signals.

**Source:** Common knowledge in quant finance. To be verified against our own data in Phase 1.

---

## D3: No options in Phase 1

**Decision:** Simulate hedge as a 15% drag on gains when we "would have hedged."

**Rationale:** Options data is expensive (Polygon/CBOE) and adds significant complexity (expiry, strike selection, IV modeling). We can answer the core question — does stochastic delay help? — without modeling options. Hedge-underdriver is a conservative approximation.

**Reconsider:** Phase 3, if results show promise.

---

## D4: Phased approach

**Decision:** Four phases (0=research, 1=core sweep, 2=robustness, 3=synthetic, 4=report).

**Rationale:** Each phase has a clear go/no-go decision based on previous results. Phase 2 only makes sense if Phase 1 shows something interesting. Phase 3 only if Phase 2 holds up. Phase 4 only if Phases 1-3 produce findings worth reporting.

---

## D5: LSF submission (not SLURM)

**Decision:** Use `#BSUB` directives, one job per (ticker, timeframe).

**Rationale:** DTU HPC runs LSF 10 (verified from hpc.dtu.dk docs). Parallel-by-ticker gives us 8-11 simultaneous jobs, each with 4-8 cores internal parallelism.

---

## D6: Vectorize, don't loop

**Decision:** Backtest engine must be pure-numpy vectorized across the parameter grid. Single Python loop = 5min/job. Vectorized = 30s/job.

**Rationale:** With ~20k backtests in Phase 1, vectorization is the difference between 30 minutes and 8 hours.

---

## D7: Cost model = 0.05% per trade

**Decision:** Default transaction cost = 0.05% per round trip (0.025% entry + 0.025% exit).

**Rationale:** Realistic for liquid US equities. May need to adjust higher for crypto (0.10-0.20%) or lower for indices. Parameter `cost_bps` allows override.

---

## D8: 100k starting capital

**Decision:** All backtests start at $100,000.

**Rationale:** Round number, scales cleanly with Sharpe/CAGR metrics (no weird unit issues).

---

## D9: yfinance + ccxt as primary data

**Decision:** yfinance for all tickers/timeframes it can serve. ccxt for crypto sub-15m.

**Rationale:** Free, no API keys, good coverage for our Phase 1 needs. Other sources (Polygon, Alpha Vantage) are paid or have stricter rate limits.

---

## D10: No look-ahead bias — warmup period in cash

**Decision:** During warmup (= 3 × longest EMA period = 150 candles), hold cash.

**Rationale:** Otherwise EMA values at t depend on future prices via the EMA formula's history. Holding cash during warmup ensures no look-ahead.

---

## Pending decisions

- σ_n default (μ_n/2 vs. fixed value vs. swept) — defer to Phase 3
- Slippage realism per asset class — defer until Phase 1 results inspected
- More EMA pairs? — defer until Phase 1 results inspected
- Block size for block-bootstrap — defer to Phase 3
