# 01-RESEARCH-LOG.md

**Purpose:** Chronological log of research findings, with sources. When I look something up, I write it here with URL + key takeaway.

---

## 2026-09-24 — Initial research

### DTU HPC documentation (hpc.dtu.dk)

- **Scheduler:** LSF 10 (IBM Spectrum LSF). Job directives use `#BSUB`, not `#SBATCH`.
- **OS:** Scientific Linux 7.9
- **Login nodes:** `login1.hpc.dtu.dk`, `login2.hpc.dtu.dk` (also `login1.gbar.dtu.dk` etc.)
- **Standard queue:** `hpc`
- **Max walltime:** 72 hours per job
- **Max processes per job:** 100
- **Max processes per node:** 20 or 24 (node-dependent)
- **Max processes per user per queue:** 100-120
- **Default walltime:** 15 minutes (so always set `-W` explicitly)
- **Module system:** `module load python3` or `module load anaconda3` — required in batch script
- **No GPU needed** for our sweep (numpy-vectorized, CPU-bound but fast)
- **Storage:** `/home/s214473/` (backup-tape, quota-limited) — keep data small or use scratch

Source: https://www.hpc.dtu.dk/?page_id=1416, https://www.hpc.dtu.dk/?page_id=3098, https://www.hpc.dtu.dk/?page_id=2501, https://www.hpc.dtu.dk/?page_id=1519

### yfinance capabilities (https://pypi.org/project/yfinance/)

- Free, no API key
- Daily: 10+ years for most US tickers
- Hourly: max 730 days
- 15-min, 5-min: max 60 days
- 1-min: max 7 days
- Sub-minute not available
- OHLCV + dividends + splits + adj close

### ccxt capabilities (https://github.com/ccxt/ccxt)

- Free tier, public data
- Crypto only (BTC, ETH, etc.)
- Timeframes: 1m, 5m, 15m, 1h, 4h, 1d available on most exchanges
- 1m data: 5+ years on Binance
- Multiple exchanges (Binance, Coinbase, Kraken, Bitfinex)

### To research (TODO)

- [ ] Alpha Vantage — alternatives for stocks, free tier limits?
- [ ] Polygon.io — free tier, options data?
- [ ] QuantGuild GitHub — what do they do specifically?
- [ ] vectorbt vs backtrader vs zipline-reborn — which is fastest for vectorized sweeps?
- [ ] Block bootstrap implementations — scipy or custom?
- [ ] DTU HPC `module avail python3` — actual module name?
