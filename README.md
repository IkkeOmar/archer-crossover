# archer-crossover

**Vectorized EMA-crossover backtest with Gaussian-distributed delay.**

A quantitative experiment to test whether stochastic delay (inspired by competitive archery technique) improves risk-adjusted returns of an EMA-crossover strategy.

## Project state

See `SPEC.md` for the full design specification.
See `notes/00-PROJECT-STATE.md` for durable project state.
See `notes/01-RESEARCH-LOG.md` for research findings.

## Status

**Phase 0 — Research + skeleton.** Currently setting up:
- Project structure
- Research on data sources (yfinance, ccxt, alternatives)
- Research on reference implementations (QuantGuild, vectorbt, backtrader)
- LSF job script design for DTU HPC

## Compute target

DTU HPC, LSF 10 scheduler. Login: `login1.hpc.dtu.dk` (user `s214473`).

## Phases

1. **Phase 1** — data + engine + 4D sweep + heatmaps/3D + baselines
2. **Phase 2** — Monte Carlo robustness on top zones
3. **Phase 3** — synthetic-market validation + options-hedge underdriver
4. **Phase 4** — LaTeX report

## Tickers (11)

SPY, QQQ, IWM, AAPL, GOOGL, BTC-USD, ETH-USD, GLD, SLV

## Timeframes

1D (full grid), 1h/4h (reduced grid), 15m/5m/3m/2m/1m (crypto only)

---

## Quick start (after Phase 1)

```bash
# 1. Install dependencies (laptop)
pip install -r requirements.txt

# 2. Download data (laptop, one-time)
python3 -m src.data_loader --tickers SPY,QQQ,IWM,AAPL,GOOGL,BTC-USD,ETH-USD,GLD,SLV \
                            --timeframes 1d,1h,15m \
                            --start 2015-01-01

# 3. Test locally on small grid
python3 -m src.sweep --ticker SPY --timeframe 1d --grid-mode tiny

# 4. Upload to DTU HPC
scp -r archer-crossover/ s214473@login1.hpc.dtu.dk:~/

# 5. Submit jobs
ssh s214473@login1.hpc.dtu.dk
cd ~/archer-crossover
bsub < scripts/submit_array.sh

# 6. Aggregate results
python3 -m src.report --in results/ --out paper/
```
