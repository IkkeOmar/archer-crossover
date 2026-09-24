# 00-PROJECT-STATE.md

**Purpose:** This file is the durable state of the project. It survives context compactions. Always read this first when resuming work on archer-crossover.

**Last updated:** 2026-09-24

---

## What this project is

We are testing whether adding a randomized Gaussian-distributed delay (with zero-delay probability) to a standard EMA crossover strategy produces different risk-adjusted returns than the immediate-cross baseline.

The motivation comes from competitive archery, where a random delay between conscious decision and trigger action reduces muscle-tension-induced aiming errors.

## Why this matters

A naive parameter sweep over delay parameters will almost certainly find some "good" combination by chance (multiple comparisons / data snooping bias). To claim real signal, we must:
1. Sweep a 4D parameter space
2. Test robustness via Monte Carlo (does the "good" zone survive random reseeds?)
3. Compare against buy-and-hold and immediate-cross baselines
4. Test on synthetic markets — if it only works on real data, there's structure being exploited

## Key files

- `/home/omar/2026-09-24/archer-crossover/SPEC.md` — full design specification (source of truth)
- `/home/omar/2026-09-24/archer-crossover/notes/` — research and decision logs
- `/home/omar/2026-09-24/archer-crossover/src/` — Python implementation
- `/home/omar/2026-09-24/archer-crossover/results/` — sweep outputs (CSV + plots)
- `/home/omar/2026-09-24/archer-crossover/data/` — cached OHLCV data
- `/home/omar/2026-09-24/archer-crossover/scripts/` — job-submission and orchestration
- `/home/omar/2026-09-24/archer-crossover/paper/` — LaTeX report (Phase 4)

## Compute plan

DTU HPC (LSF 10), student user `s214473`. Login: `login1.hpc.dtu.dk`. Standard queue `hpc`, max 72h walltime, 100 cores per user. We will submit one LSF job per (ticker, timeframe) combination for parallel execution.

## Phases

- **Phase 0** (current): research + skeleton (this file)
- **Phase 1**: implement data_loader, archer_engine, sweep, plots, run on full 4D grid
- **Phase 2**: Monte Carlo robustness on top zones
- **Phase 3**: synthetic-market validation + options-hedge underdriver
- **Phase 4**: LaTeX report

## Key decisions made (and why)

- **4D parameter space:** (n_mu, x, bear_alloc_1d, ema_pair). Bear_alloc only on 1D. This avoids the "too many degrees of freedom" problem Omar flagged.
- **Phased approach:** start with focused Phase 1 grid, only expand if results justify it.
- **Position sizing:** 1D never goes short (asymmetric upward market); sub-daily timeframes allow full short.
- **Synthetic-market test:** block bootstrap + GBM + trending + mean-reverting. Tests if the strategy exploits structure or just fits noise.
- **No options in Phase 1:** we simulate hedge as a 15% drag on gains when hedging would have applied. Conservative.
- **Cost model:** 0.05% per trade default. Adjust if Phase 1 results are too good.

## Known open questions

- QuantGuild relevance — research before Phase 3
- σ_n sensitivity — default μ_n/2, sweep in Phase 3
- Should we add more EMA pairs? — TBD after Phase 1
- Slippage realism per asset class — TBD after Phase 1
