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

---

## D11: Custom numpy engine (not vectorbt)

**Decision:** Build backtest in pure numpy/pandas, not adopt vectorbt.

**Considered:** vectorbt (recommended by research as fastest for param sweeps, ~10k combos in seconds).

**Why not:** Our sweep is ~540 combos × ~2500 candles ≈ 1.4M candle-evaluations, ~30 sec per combo with pure numpy — well within budget for parallel cluster execution. vectorbt's main value (Numba-vectorized param sweep) gives us less benefit than its complexity cost (Numba dependency, custom-indicator boilerplate, less control over stochastic delay logic). Our verify-still-same-side logic + delay sampling is custom and would need a custom IndicatorFactory anyway.

**Future option:** If Phase 2 reveals we need >50k combos, revisit vectorbt PRO for chunked parallel execution.

---

## D12: QuantGuild validation framework (from research)

**Decision:** Adopt three QuantGuild techniques from Lecture 97 into Phase 2:

1. **Walk-forward validation** — split data into rolling train/test windows; only count parameterizations that work across multiple windows as "robust."
2. **Out-of-sample split** — reserve last 20% of data for honest evaluation; never tune on it.
3. **Look-ahead bias audit** — explicit checklist for each strategy step confirming only-t information is used.

**Rationale:** These are the standard defenses against overfitting in quantitative finance. Our existing Monte Carlo (random reseeds of delay sampling) tests signal stability but not parameter robustness across time regimes. Walk-forward closes that gap.

**Source:** QuantGuild Lecture 97 — "3 Backtesting Pitfalls That Ruin Your Strategy" — research logged 2026-09-24 in `notes/01-RESEARCH-LOG.md` section 6.

---

## D13: LSF native job arrays (not looped bsub)

**Decision:** Use LSF native job arrays via `bsub -J "sweep[1-N]"` with a TSV parameter table.

**Considered:** Simple shell loop `for combo in combos: bsub ...`.

**Why:** Native arrays group jobs in the scheduler, allow `bjobs -J "sweep[*]"`, support `bsub -w "done(sweep)"` wait dependencies, and use a single `-J` index to look up the row in a `params.tsv`. Reduces scheduler overhead and gives clean aggregation.

**Implementation:** `submit_array.sh` will be rewritten to use this pattern.

**Note:** Research reported LSF 9.3.1 on DTU HPC; our earlier DTU docs read said 10. Both versions support job arrays — syntax identical.

---

## D14: Use arxiv 2602.10785 walk-forward methodology (from simple-test research)

**Source:** Sub-agent research 2026-09-24 → `notes/06-SIMPLE-TEST-RESEARCH.md`.

**Key findings from arxiv paper:**
- Tested EMA crossover across 1min–60min on BTC/ETH/BNB with 0.1% fees.
- Below 30min, all strategies lost to costs. Break-even ~0.4%/trade.
- Walk-forward window size has a LARGE effect on Sharpe — must fix before sweeping delay.
- Their primary ranking metric is Robust Sharpe Ratio (deflated Sharpe).
- Block-bootstrap null control: strategy must beat randomly-generated EMA params.

**Decision:** Adopt in Phase 2:
- Walk-forward with FIXED window size (don't sweep over windows).
- Robust Sharpe Ratio as primary ranking metric (not raw Sharpe).
- Block bootstrap null control in Phase 3 (compare to random EMA param sets).

---

## D15: Report all ticker/timeframe combos, not just winners

**Source:** OpenAlgo tutorial warning + sub-agent research.

**Key principle:** "Finding the single highest-scoring parameter combination is easy and almost always a trap. The real skill is finding a *region* of settings that all work."

**Decision:** Every sweep result goes into the per-combo CSV. Reports show:
- Top-N by Sharpe (with full params)
- Median Sharpe across all combos (to see typical outcome)
- Cross-ticker consistency: same parameter zone works on multiple tickers? (this is the real signal)
- Bottom-N (to see worst cases for tail risk)

**Avoid:** Reporting only the single best ticker/timeframe. With 27+ combos to choose from, the "winner" is almost certainly lucky.

---

## D16: Multi-ticker default sweep uses bear_alloc=1.0 only

**Source:** Sub-agent research 2026-09-24, Section (c): "100% allocation is the right default for sanity tests."

**Decision:** In Phase 1 default sweep, fix `bear_alloc_1d = 1.0` (full long/short) for all tickers. Sweep only `(n_mu, x, ema_pair)`.

**Rationale:** Bear allocation is a position-sizing concern that should be explored AFTER signal quality is established. Mixing it with delay parameters creates confounding.

**Note:** SPEC.md Section 2.2 retains the bear_alloc_1d grid as a Phase 3 dimension, but Phase 1 holds it fixed to isolate the delay signal's edge.

---

## D17: Phase 2 walk-forward window size = 252 days (1 year)

**Source:** arxiv 2602.10785 methodology + standard quant practice.

**Decision:** Walk-forward with 252-day training window and 63-day (1 quarter) testing window. Roll forward by 63 days at each step. Use 2015-2024 data → ~28 walk-forward steps.

**Rationale:** 252/63 ratio matches the conventional "train 1 year, test 1 quarter" pattern. Fixed before sweeping over delay parameters.
