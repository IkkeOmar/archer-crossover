# archer-crossover

Vectorized EMA-crossover backtest with Gaussian-distributed stochastic delay.

A quantitative experiment to test whether stochastic delay (inspired by competitive archery technique) improves risk-adjusted returns of an EMA-crossover strategy.

## What is this?

When the fast EMA crosses the slow EMA:
1. Sample a delay `n ~ mixture(delta_0 with prob x) + |N(mu_n, sigma_n)| with prob 1-x`
2. After waiting `n` candles, verify the cross direction is still valid
3. If valid, enter position per the timeframe's allocation rule

We sweep a 4D parameter space: `(n_mu, x, bear_alloc_1d, ema_pair)` and compare to buy-and-hold and vanilla immediate-cross baselines.

## Project status

- [x] Phase 0 — Research + project skeleton
- [x] Phase 1 — Core implementation (engine, sweep, plots, baselines, report, LSF script)
- [ ] Phase 1 — Test on real data
- [ ] Phase 2 — Monte Carlo robustness
- [ ] Phase 3 — Synthetic-market validation
- [ ] Phase 4 — LaTeX report

## Project layout

See [notes/02-FOLDER-MAP.md](notes/02-FOLDER-MAP.md) for a complete visual breakdown.

```
archer-crossover/
  SPEC.md             -- Full design specification
  README.md           -- This file
  requirements.txt    -- Python dependencies
  configs/            -- YAML configs (default.yaml)
  notes/              -- Project state, research log, decisions
  src/                -- Python package (data_loader, archer_engine, sweep, plots, report)
  scripts/            -- Shell scripts (fetch_data, submit_array, tar_and_upload)
  data/               -- Cached OHLCV (NOT committed)
  results/            -- Sweep outputs (NOT committed)
  paper/              -- LaTeX report (Phase 4)
```

## Quick start (local, no cluster)

```bash
# 1. Install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Fetch data (one-time)
python3 -m src.data_loader --tickers SPY,QQQ,AAPL --timeframes 1d,1h --start 2015-01-01

# 3. Run a tiny test sweep
python3 -m src.sweep --ticker SPY --timeframe 1d --grid-mode tiny

# 4. Generate plots from the sweep
python3 -m src.plots results/csv/SPY_1d.csv --npz results/npz/SPY_1d_raw.npz --ticker SPY --timeframe 1d
```

## Cluster use (DTU HPC, LSF)

```bash
# 1. Package locally (excludes data/ and results/)
bash scripts/tar_and_upload.sh

# 2. Upload to cluster (run with your DTU password)
scp archer-crossover.tar.gz s214473@login1.hpc.dtu.dk:~/

# 3. On cluster
ssh s214473@login1.hpc.dtu.dk
tar xzf archer-crossover.tar.gz
cd archer-crossover
bash scripts/fetch_data.sh      # one-time
bash scripts/submit_array.sh    # submits ~21 jobs
bjobs                            # monitor

# 4. Aggregate results (after all jobs complete)
python3 -m src.report
```

## Tickers

- **Broad ETFs**: SPY, QQQ, IWM
- **Single stocks**: AAPL, GOOGL
- **Crypto**: BTC-USD, ETH-USD (via yfinance) + Binance (ccxt for sub-15m)
- **Metals**: GLD, SLV

## Timeframes

- **1d** — full grid (daily history for all tickers)
- **1h** — full grid (max 730 days history)
- **15m, 5m, 3m, 2m, 1m** — crypto only (Phase 1.5+)

## See also

- [SPEC.md](SPEC.md) — Full design contract
- [notes/00-PROJECT-STATE.md](notes/00-PROJECT-STATE.md) — Project brain
- [notes/01-RESEARCH-LOG.md](notes/01-RESEARCH-LOG.md) — Research findings
- [notes/04-DECISIONS.md](notes/04-DECISIONS.md) — Design decisions
