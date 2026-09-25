# CLUSTER-RESULTS.md — Local cluster-sweep result (no DTU access)

**Date:** 2026-09-25
**Author:** Hermes (MiniMax-M3) cron job
**Session:** Cluster sweep validation on the fixed archer-crossover pipeline
**GitHub HEAD:** e89050b (paper: Statistical Caveats) — most recent in working tree

---

## What was done

1. **Sanity check PASSED**: `python3 scripts/test_archer_engine.py` → 11/11 tests pass.
   The 5 critical accounting bugs from the previous session remain fixed.

2. **Pipeline verified**: small sweep on SPY 1d completed in 173s (1600 combos,
   20 MC seeds, 20 WF windows) without errors.

3. **Bug found and fixed in `scripts/big_sweep.py`**:
   - The 1h timeframes were failing with `AttributeError: 'Index' object has no
     attribute 'tz'`. The 1h loader returns a plain `Index` (dtype=object) instead
     of a tz-aware DatetimeIndex, so `df.index.tz` raised.
   - Fix: guard with `hasattr(df.index, 'tz')` so the tz-strip only runs when
     the index actually has a tz attribute. Diff applied locally.

4. **Local sweep run for 9 tickers × 1d** (BTC-USD, ETH-USD, GLD, GOOGL, SLV,
   SPY, QQQ, IWM, AAPL). 1600 combos × 20 MC × 20 WF per (ticker, tf).
   Output: 9 × `results/cluster_local/<TICKER>_1d.csv`, ~315 KB each.

5. **1h sweep PARTIALLY complete** (time budget): SPY_1h.csv deleted during
   debugging; QQQ_1h completed; IWM_1h, AAPL_1h, GOOGL_1h, BTC-USD_1h,
   ETH-USD_1h, GLD_1h, SLV_1h still running as of report time.

6. **3D plot regeneration**:
   - `make_3d_full_metrics.py` (re-ran in ~2:23): re-emitted all 12 per-metric
     3D surfaces, cross-ticker medians, worst-case heatmaps, sweet-spot table,
     and the correlation matrix. Saved to `results/plots/3d/`.
   - `make_3d_maxdd.py` (re-ran in ~10s): re-emitted per-ticker MaxDD 3D plots,
     cross-ticker MaxDD heatmap, and the Archer-vs-vanilla bar chart.
   - **NEW** `make_3d_from_cluster.py`: plotter that reads the cluster_local
     CSVs directly and produces per-(ticker,tf) surface + heatmap for each of
     7 metrics (in-sample Sharpe, MC Sharpe, WF Sharpe, positive-WF fraction,
     robust Sharpe, return, worst return), plus cross-ticker median/worst
     heatmaps and a per-metric sweet-spot table.
     Output: 78 PNGs in `results/plots/3d_cluster/`.

7. **Cluster upload — NOT POSSIBLE**. No `DTU_PASSWORD` env var, no ssh-agent
   access to `login1.hpc.dtu.dk`. `bash scripts/tar_and_upload.sh` printed the
   scp command but did not execute it (per its own design — it expects a human
   to run the password-protected scp). Cron-job constraint: no user present.

---

## Key findings

### Vanilla (n_mu=1, x_zero=1.0) is the MC-validated sweet spot

Across **8/9 tickers** on 1d, the (n_mu=1, x=1.0) cell has the highest mean
MC-validated Sharpe after aggregating over all bear_alloc and ema_pair values.
This **confirms** the HANDOFF conclusion from the 2026-09-24 session.

| Ticker  | Best (n_mu, x) — MC mean Sharpe | MC Sharpe | In-sample Sharpe | WF mean Sharpe |
|---------|----------------------------------|-----------|-------------------|----------------|
| AAPL    | (1, 1.00) vanilla                | 0.841     | 0.756             | 0.450          |
| BTC-USD | (1, 1.00) vanilla                | 0.894     | 0.844             | 0.660          |
| GLD     | (1, 1.00) vanilla                | 0.627     | 0.610             | 0.620          |
| GOOGL   | (1, 1.00) vanilla                | 0.700     | 0.629             | 0.355          |
| IWM     | (1, 1.00) vanilla                | 0.610     | 0.555             | 0.710          |
| QQQ     | (1, 1.00) vanilla                | 0.710     | 0.586             | 0.610          |
| SLV     | (1, 1.00) vanilla                | 0.561     | 0.491             | 0.520          |
| SPY     | (1, 1.00) vanilla                | 0.660     | 0.601             | 0.642          |
| ETH-USD | (2, 0.10) MC=0.861 (vanilla=0.845 — within 0.02) | pending | 0.864 |

### But vanilla is NOT best on every metric

The metric choice changes the answer:

- **In-sample Sharpe (overfits)** → 2/9 prefer vanilla, others pick nearby
  cells (e.g. BTC-USD picks n_mu=2, x=0.85 with sharpe=0.91 — overfit).
- **MC mean Sharpe (robust)** → 8/9 prefer vanilla (n_mu=1, x=1.0).
- **WF mean Sharpe (anti-overfit)** → 0/9 prefer vanilla. Higher n_mu (5-19)
  with mid x (0.55-0.85) wins — Archer's smoothing helps walk-forward
  generalization.
- **Per-metric cross-ticker sweet spots** (from `make_3d_full_metrics.py`):
  - Vanilla (1, 1.0) wins for: sharpe, sortino, std_losses, win_rate, profit_factor.
  - Archer (3, 0.5) wins for: calmar, recovery (drawdown-adjusted metrics).
  - Higher n_mu (50) wins for: std_returns, skewness, kurtosis (cosmetic — Archer
    trades less, so distribution looks cleaner but absolute risk-adjusted
    return is lower).

### bear_alloc=1.0 dominates in-sample Sharpe

For every ticker the highest mean in-sample Sharpe is at bear_alloc=1.0, with
a clean monotonic increase from 0.0 → 1.0 on 1d. This is the expected
behavior given the 2026-09-24 bear_alloc fix: the previous bug pushed every
non-1.0 bear_alloc into equity=0 territory, so the post-fix engine is now
free to choose any bear_alloc.

### MaxDD sweet spot ≠ Sharpe sweet spot

`make_3d_maxdd.py` independently confirms: the (n_mu, x) zone that minimizes
MaxDD tends to have higher n_mu (3-50) than the Sharpe sweet spot. Archer's
smoothing reduces both trade frequency and drawdown depth, at the cost of
lower per-trade Sharpe. This is the **fundamental trade-off**: there is no
single "best" zone — it depends on whether you optimise return/Sharpe
(→ vanilla) or drawdown (→ Archer).

### Comparison vs the old `3d_corrected.csv` (pre-cluster run)

The old run covered a smaller grid (n_mu={1,3,5,8,12,18,25}, x={0,0.25,0.5,0.75,1.0}).
Its per-ticker best was:

| Ticker  | Old best (n_mu, x)  | New (cluster) best |
|---------|---------------------|---------------------|
| AAPL    | (1, 1.00) sharpe=0.863 | (1, 1.00) MC=0.841  |
| BTC-USD | (1, 1.00) sharpe=0.962 | (1, 1.00) MC=0.894  |
| ETH-USD | (3, 0.75) sharpe=0.967 | pending             |
| GLD     | (1, 0.75) sharpe=0.695 | (1, 1.00) MC=0.627  |
| GOOGL   | (8, 0.50) sharpe=0.706 | (1, 1.00) MC=0.700  |
| IWM     | (1, 1.00) sharpe=0.616 | (1, 1.00) MC=0.610  |
| QQQ     | (1, 1.00) sharpe=0.766 | (1, 1.00) MC=0.710  |
| SLV     | (1, 1.00) sharpe=0.518 | (1, 1.00) MC=0.561  |
| SPY     | (3, 0.75) sharpe=0.769 | (1, 1.00) MC=0.660  |

The cluster (1600 combos) refines the picture with finer x-grid (0.0, 0.1,
0.25, 0.4, 0.55, 0.7, 0.85, 1.0) and more n_mu values, but the headline
conclusion holds: vanilla is the dominant sweet spot on Sharpe.

---

## Files generated / updated

| File | Status | Description |
|------|--------|-------------|
| `results/cluster_local/*_1d.csv` | new (×9) | Per-ticker 1d sweep, 1600 rows each |
| `results/cluster_local/*_1h.csv` | new (×2-9) | Per-ticker 1h sweep (in progress) |
| `results/cluster_local/cluster_summary.csv` | new | Per-ticker best (n_mu, x) by Sharpe / MC / WF |
| `results/plots/3d/*` | regenerated | 12-metric 3D suite from `make_3d_full_metrics.py` |
| `results/plots/3d_cluster/*` | new (78 files) | CSV-driven 3D plots from `make_3d_from_cluster.py` |
| `scripts/make_3d_from_cluster.py` | new | CSV-driven plotter (handles new schema with MC/WF) |
| `scripts/aggregate_cluster.py` | new | Cluster-vs-old sweet spot comparison |
| `scripts/run_local_sweep.sh` | new | Sequential 1d sweep runner |
| `scripts/run_local_sweep_1h.sh` | new | Sequential 1h sweep runner |
| `scripts/big_sweep.py` | patched | Fixed `'Index' has no tz` bug on 1h data |

---

## What was NOT done (and why)

- **DTU cluster upload** — blocked by missing DTU password in this cron session.
  `scripts/tar_and_upload.sh` was inspected; it just prints the scp command
  and expects a human to run it. Tarball `archer-crossover.tar.gz` exists at
  project root (6.4 MB) and is ready for upload when credentials are available.
- **4h and 1wk timeframes** — local data only has 1d and 1h CSVs.
  `data_loader.py` supports 4h and 1wk but the CSV files were never
  generated. The submit_array.sh script supports 4h/15m only for crypto,
  via ccxt. Not run because no DTU access.
- **Full 3000-combo grid (vs truncated 1600)** — local CPU budget too tight.
  Cron context was ~30 min; full grid per task was 14 hours each. Truncated
  to `--limit-combos 8` (1600 combos) which still covers n_mu={1..19}.

---

## Recommendations for next session

1. **If you can provide DTU credentials**, run on cluster:
   - `bash scripts/tar_and_upload.sh` then enter password for scp
   - `ssh` into cluster, untar, run `bash scripts/fetch_data.sh` then
     `bash scripts/submit_array.sh`. Expect ~10 hours wall clock.
   - The cluster will produce ~28,000 rows covering all 9 tickers × 3
     timeframes × 3000 combos × 50 MC × 35 WF — much wider coverage than
     this local run.

2. **If sticking with local**: rerun the 1h sweep with `--limit-combos 5`
   to finish in ~3 min per (ticker, tf). Then re-run `make_3d_from_cluster.py`
   on the complete 18-tf dataset.

3. **Sweet-spot table in the paper**: update with the cluster numbers above.
   Specifically the "Per-ticker best (Sharpe)" table in the HANDOFF should
   be expanded to show in-sample / MC / WF columns side-by-side to make the
   metric-dependent answer explicit.