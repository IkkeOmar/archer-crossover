# 02-FOLDER-MAP.md

**Purpose:** Persistent mental model of the project structure. When I (Hermes) lose context or come back to this project cold, I read this file first to remember where everything lives and what each piece does.

**Last updated:** 2026-09-24 (Phase 0)

---

## Visual tree

```
archer-crossover/
|
|-- SPEC.md                  # THE SPEC: full design contract. Source of truth.
|                              # Read this BEFORE coding anything.
|
|-- README.md                # Human-readable overview. Quick-start commands.
|                              # Update when commands change.
|
|-- requirements.txt         # Python dependencies (numpy, yfinance, ccxt, ...)
|
|-- .gitignore               # What's NOT committed (cached data, build artifacts)
|
|-- notes/                   # PROJECT BRAIN. Durable state that survives context loss.
|   |
|   |-- 00-PROJECT-STATE.md  # WHAT we're doing + WHY + WHERE we are.
|   |                          # Read this FIRST when resuming work.
|   |
|   |-- 01-RESEARCH-LOG.md   # CHRONOLOGICAL research findings, with URLs.
|   |                          # Append-only. Each entry has date + source + takeaway.
|   |
|   |-- 02-FOLDER-MAP.md     # THIS FILE. Visual + description of every file.
|   |                          # Update when structure changes.
|   |
|   |-- 03-DATASOURCES.md    # Evaluated data sources (yfinance, ccxt, etc.)
|   |                          # With coverage + cost + gotchas + verdict.
|   |
|   |-- 04-DECISIONS.md      # Design decisions with rationale.
|   |                          # Why this approach, not that one.
|   |
|   |-- 05-RESULTS-LOG.md    # (empty until Phase 1) Findings as we run sweeps.
|   |
|   `-- 99-LATEX-REPORT-PLAN.md  # Outline of the final report. Phase 4.
|
|-- src/                     # ACTUAL CODE. Python package.
|   |
|   |-- __init__.py          # Package marker + module list.
|   |
|   |-- data_loader.py       # Fetch OHLCV from yfinance + ccxt. Cache to CSV.
|   |                          # Used: once, locally, BEFORE upload to cluster.
|   |
|   |-- archer_engine.py     # THE CORE. Vectorized EMA-cross backtest.
|   |                          # 4D param support (n_mu, x, bear_alloc, ema_pair).
|   |                          # Stochastic delay + verify-still-same-side rule.
|   |
|   |-- metrics.py           # Sharpe, CAGR, max DD, Calmar, win rate, total return.
|   |                          # Pure functions on equity curve arrays.
|   |
|   |-- sweep.py             # Parameter sweep runner (joblib parallel).
|   |                          # Iterates over (n_mu, x, bear_alloc, ema_pair) grid.
|   |                          # One sweep = one (ticker, timeframe) combo.
|   |
|   |-- montecarlo.py        # Robustness sims on top zones (Phase 2).
|   |                          # 1000 random reseeds of delay sampling per zone.
|   |
|   |-- synthetic.py         # Synthetic markets (Phase 3).
|   |                          # GBM, block-bootstrap, trending, OU.
|   |
|   |-- plots.py             # Heatmaps, 3D surfaces, equity curves (log scale).
|   |                          # matplotlib + seaborn.
|   |
|   `-- report.py            # Aggregate CSVs into LaTeX-ready tables (Phase 4).
|
|-- data/                    # CACHED OHLCV. NOT committed (large, regenerable).
|   `-- *.csv                # One file per (ticker, timeframe).
|                              # e.g. SPY_1d.csv, BTC-USD_1h.csv
|
|-- configs/                 # YAML configs for sweep parameters.
|   `-- default.yaml         # Default grid (Phase 1).
|                              # Read by sweep.py.
|
|-- scripts/                 # Orchestration + cluster submission.
|   |
|   |-- submit_array.sh      # LSF job submission for DTU HPC.
|   |                          # One job per (ticker, timeframe).
|   |
|   |-- fetch_data.sh        # Wrapper around data_loader (run locally first).
|   |
|   `-- tar_and_upload.sh    # Package + scp to DTU.
|
|-- results/                 # SWEEP OUTPUT. NOT committed (regenerable).
|   |
|   |-- csv/                 # Per-combo metrics CSVs.
|   |                          # e.g. SPY_1d.csv with (n_mu, x, bear_alloc, sharpe, ...)
|   |
|   |-- npz/                 # Per-combo equity curves (numpy arrays).
|   |                          # For fast re-plotting.
|   |
|   `-- plots/               # Generated PNG/PDF plots.
|       |-- heatmaps/        # 2D Sharpe over (n_mu, x).
|       |-- 3d/              # 3D Sharpe over (n_mu, x, bear_alloc).
|       `-- equity/          # Best-zone vs. baseline overlay.
|
`-- paper/                   # LATEX REPORT. Phase 4 deliverable.
    |
    |-- main.tex             # The report.
    |-- refs.bib             # Bibliography.
    |-- figs/                # PDF figures (committed, small).
    `-- build.sh             # Compile LaTeX.
```

---

## What lives where (cheat sheet)

| Need to... | Go to... |
|---|---|
| Understand the experiment | `SPEC.md` |
| Resume work after context loss | `notes/00-PROJECT-STATE.md` |
| Find a research finding | `notes/01-RESEARCH-LOG.md` |
| Remember what file does what | `notes/02-FOLDER-MAP.md` (this file) |
| Change data source | `notes/03-DATASOURCES.md` |
| Justify a design choice | `notes/04-DECISIONS.md` |
| See results so far | `notes/05-RESULTS-LOG.md` |
| Write code | `src/` |
| Submit to cluster | `scripts/submit_array.sh` |
| Look at a plot | `results/plots/` |
| Write the final report | `paper/` |

---

## Update protocol

When structure changes (new file, moved file, new module):
1. Update this file
2. Commit with message starting with `docs(folder-map):`

When new research is done:
1. Append to `notes/01-RESEARCH-LOG.md` with date + URL + takeaway
2. Commit

When a design decision is made:
1. Add to `notes/04-DECISIONS.md` with: what, alternatives considered, why this one
2. Commit
