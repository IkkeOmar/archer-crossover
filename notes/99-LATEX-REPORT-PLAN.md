# 99-LATEX-REPORT-PLAN.md — Structure for the final Archer-Crossover report

**Status:** Active — 2026-09-24
**Owner:** Omar Jennane
**Compute target:** DTU HPC (LSF 10)

## Final deliverable

A 15-25 page LaTeX paper suitable for:
- arXiv submission (q-fin.TR or q-fin.GN)
- Internal DTU project report
- GitHub README.md summary

## Required sections

### Frontmatter
- [ ] Title page (title, author, repo URL, date)
- [ ] Abstract (250 words, 1 paragraph)
- [ ] Acknowledgements (QuantGuild, arxiv 2602.10785, durebel/crypto-backtester)

### 1. Introduction (~2 pages)
- Motivation: stochastic delay in archer trigger analogy
- Hypothesis
- Related work
- Contribution summary

### 2. Method (~3 pages)
- 2.1 Strategy definition (with math)
- 2.2 Parameter space (n_mu, x, sigma_n, bear_alloc, EMA pair)
- 2.3 Backtest engine (long/short accounting)
- 2.4 Metrics (Sharpe, return, MDD)
- 2.5 Validation framework (Monte Carlo, walk-forward, synthetic)

### 3. Phase 1: Sweep Results (~3 pages)
- 3.1 Default-grid sweep (4860 combos, 9 tickers)
- 3.2 Per-ticker heatmaps (9 figures)
- 3.3 Cross-ticker consistency plot
- 3.4 Best parameters per ticker

### 4. Phase 2: Robustness (~4 pages)
- 4.1 Equity curves (4 figures: SPY, QQQ, BTC, GLD)
- 4.2 Monte Carlo Robust Sharpe (1 figure)
- 4.3 Walk-forward validation (2 figures)
- 4.4 Per-ticker walk-forward summary

### 5. Phase 3: Synthetic Market Null Controls (~3 pages)
- 5.1 GBM, trending, OU, regime-switching, block bootstrap
- 5.2 Bar chart summary
- 5.3 Interpretation (specialization vs general edge)

### 6. Phase 4: Multi-Timeframe Analysis (~3 pages)
- 6.1 BTC/ETH 1d vs 1h comparison
- 6.2 100% long/short position distribution
- 6.3 Per-trade winrate by side (long vs short)
- 6.4 Hedge decomposition

### 7. Discussion (~3 pages)
- 7.1 Why vanilla wins Sharpe but Archer adds robustness
- 7.2 When delay helps (regime-switching markets)
- 7.3 Hedge reality check (shorts add limited value)
- 7.4 Limitations (1h data via CDD, no borrow fees, no margin)

### 8. Conclusion (~1 page)
- Bullet summary of headline results

### Appendices
- A. Data sources (yfinance, ccxt, CDD)
- B. Engine unit tests
- C. Walk-forward window detail
- D. Full sweep CSV files

## Required figures (already generated)

- 9 per-ticker heatmaps (heatmap_AAPL_1d.png ... heatmap_SLV_1d.png)
- 1 cross-ticker median heatmap
- 1 consistency plot
- 4 equity curves (linear)
- 4 equity curves (log scale)
- 1 Monte Carlo Robust Sharpe
- 2 walk-forward plots (summary + SPY per-window)
- 1 synthetic null control (bar chart)
- 1 market exposure plot (long/short over time)
- 3 MaxDD comparison plots (bars, scatter, ratio)
- 1 multi-timeframe comparison (1h vs 1d)

## Required tables

- T1: Default-grid sweep summary (best/median/worst Sharpe)
- T2: Walk-forward per ticker
- T3: Synthetic market null control
- T4: Multi-timeframe comparison
- T5: Per-trade winrate (long vs short)

## Status check (2026-09-24)

| Section | Status | Notes |
|---------|--------|-------|
| 1 Introduction | DONE | First draft written |
| 2 Method | DONE | Engine spec + parameter space |
| 3 Phase 1 | DONE | 4860 combos, 11s |
| 4 Phase 2 | DONE | MC + walk-forward |
| 5 Phase 3 | DONE | 6 market types |
| 6 Phase 4 | IN PROGRESS | Multi-timeframe sweep running |
| 7 Discussion | PARTIAL | Need hedge-reality-check section |
| 8 Conclusion | DONE | Bullet summary |

## Cluster pipeline (LSF 10)

The multi-timeframe sweep at full grid (9 tickers × 4 timeframes × 540 combos = 19440 backtests) requires HPC.

LSF submission: `scripts/submit_array.sh`
- Splits sweep into N job-array tasks
- Each task: 1 ticker × 1 timeframe
- Output: CSV per (ticker, timeframe)

## GitHub release

After local + cluster runs complete:
1. `tar -czf archer-crossover-v1.0.tar.gz src/ scripts/ notes/ SPEC.md requirements.txt results/`
2. `gh release create v1.0 archer-crossover-v1.0.tar.gz --repo IkkeOmar/archer-crossover --public`
3. Upload paper PDF as release asset
