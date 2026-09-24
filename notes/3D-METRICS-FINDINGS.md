# 3D-METRICS-FINDINGS.md — Fund fra fuld 3D metric-analyse

**Dato:** 2026-09-24
**Kontekst:** Efter opdagelse af 4 kritiske accounting-bugs i archer_engine.py, fuld 3D-suite for 12 risk metrics på 9 tickers.

## Metodik

Efter accounting-fixes blev der kørt en 3D sweep over:
- 9 n_mu værdier: 1, 3, 5, 8, 12, 18, 25, 35, 50
- 5 x værdier: 0.0, 0.25, 0.5, 0.75, 1.0
- 3 bear_alloc: 0.0, 0.5, 1.0
- 2 EMA pairs: (9,21), (12,26)
- 9 tickers 1d: SPY, QQQ, IWM, AAPL, GOOGL, BTC-USD, ETH-USD, GLD, SLV

I alt 1890 backtests per ticker × 9 tickers = ~17,000 backtests.

## Metrics analyseret

1. Sharpe ratio
2. Sortino ratio (downside deviation)
3. Std of returns (annualiseret)
4. Std of WINS
5. Std of LOSSES
6. Win rate
7. Profit factor (gross_win / gross_loss)
8. Calmar (CAGR / |MaxDD|)
9. Recovery factor (total_return / |MaxDD|)
10. Payoff ratio (avg_win / |avg_loss|)
11. Skewness
12. Kurtosis

## Sweet spots (cross-ticker median)

| Metric | Best (n_mu, x) | Median value |
|--------|----------------|--------------|
| **Sharpe** | (1, 1.0) — VANILLA | 0.76 |
| **Sortino** | (1, 1.0) — VANILLA | 0.99 |
| **Win rate** | (1, 1.0) — VANILLA | 0.44 |
| **Profit factor** | (1, 1.0) — VANILLA | 1.41 |
| **Skewness** | (1, 1.0) — VANILLA | 2.20 |
| **Kurtosis** | (1, 1.0) — VANILLA | 22.78 |
| **Calmar** | (3, 0.5) — ARCHER | 0.22 |
| **Recovery** | (3, 0.5) — ARCHER | 3.46 |
| **Payoff ratio** | (1, 0.0) — VANILLA | 1.34 |

## Hyppigste sweet spot

| (n_mu, x) | Count | Note |
|-----------|-------|------|
| **(1, 1.0) VANILLA** | **6/9** | sharpe, sortino, win_rate, profit_factor, skewness, kurtosis |
| (50, 0.0) | 3/9 | std_returns, std_wins, std_losses (ofte ingen trades — artefakt) |
| (3, 0.5) ARCHER | 2/9 | calmar, recovery |
| (1, 0.0) | 1/9 | payoff_ratio |

## Correlation matrix (key findings)

| Metric pair | Correlation | Insight |
|-------------|-------------|---------|
| sharpe ↔ sortino | 0.99 | essentially identical |
| sharpe ↔ profit_factor | 0.96 | very high |
| sharpe ↔ calmar | 0.96 | very high |
| sharpe ↔ std_wins | 0.51 | moderate — high std of wins helps sharpe |
| **sharpe ↔ win_rate** | **0.02** | **NEAR ZERO** — winrate alone doesn't drive sharpe |
| sharpe ↔ std_returns | 0.27 | weak — sharpe normaliserer for std |
| **win_rate ↔ std_wins** | **-0.69** | HIGH winrate = LOW std of wins |
| std_returns ↔ std_losses | 0.96 | nearly identical — losses dominate risk |

### Hvad korrelationerne viser

1. **Sharpe er IKKE drevet af winrate** (0.02). Det er payoff ratio + profit factor der driver.
2. **winrate ↔ std_wins = -0.69** — counterintuitive, men logisk: høj winrate kommer ofte fra hurtige små wins, som har lav variabilitet.
3. **std_returns ≈ std_losses** — short-salg eller tabende trades dominerer den samlede risiko.

## Per-ticker best (Sharpe)

| Ticker | Best (n_mu, x, bear, ema) | Sharpe | Return |
|--------|---------------------------|--------|--------|
| SPY | (1, 1.0, 1.0, 9/21) | 1.01 | +149.7% |
| QQQ | (1, 1.0, 1.0, 9/21) | 1.01 | +13.6% |
| IWM | (1, 1.0, 1.0, 9/21) | 1.05 | +45.2% |
| AAPL | (1, 1.0, 0.0, 9/21) | 1.04 | +495.0% |
| GOOGL | (1, 1.0, 1.0, 9/21) | 1.07 | -68.6% |
| BTC-USD | (12, 0.25, 0.0, 9/21) | 1.21 | +16992.0% |
| ETH-USD | (1, 1.0, 1.0, 9/21) | 1.15 | +12559.3% |
| GLD | (1, 1.0, 1.0, 9/21) | 1.11 | +50.2% |
| SLV | (1, 1.0, 1.0, 9/21) | 1.11 | -57.2% |

**7/9 tickers: vanilla (n_mu=1, x=1.0) er bedst for Sharpe.**

## Implikationer for rapporten

1. **Den tidligere konklusion "Archer-specifikt delay er sweet spot" var forkert.** Den var baseret på
   - Mean over et snævrere parameter grid
   - Accounting-bugs der boostede Archer-specifikt delay

2. **Med korrekt accounting er vanilla (n_mu=1, x=1.0) bedst for de fleste metrics.** Det er et standard
   EMA-cross system uden nogen forsinkelse. Archer-specifikt delay tilføjer IKKE værdi for Sharpe.

3. **Calmar og Recovery peger på (3, 0.5)** — det er ARCHER-specifikt delay. Dette antyder at Archer
   måske forbedrer risk-adjusted return når man tager højde for MaxDD, men forbedrer ikke Sharpe.

4. **Per-ticker variation er stor** — BTC favoriserer Archer-specifikt delay (12, 0.25) mens stocks
   favoriserer vanilla. Det er fordi BTC's lange trends passer godt til Archer's delay-sampling.

## Anbefaling

**Til live trading:** Brug vanilla EMA-cross (n_mu=1, x=1.0, bear_alloc=1.0, ema=9/21).
- Højere Sharpe (median 0.76)
- Højere win_rate (44%)
- Højere profit factor (1.41)
- Tradeable på tværs af de fleste tickers

**Brug Archer-specifikt delay KUN:**
- For BTC (bedste Sharpe 1.21)
- Hvis man vil maksimere Calmar/Recovery frem for Sharpe

## Næste skridt

1. Kør ARCHER-specifikt delay (3, 0.5) som alternativ strategi
2. Verificer vanilla vs Archer på multi-timeframe (1h, 1d)
3. Kør walk-forward validation på begge
4. Sammenlign på tværs af 9 tickers + 4 timeframes

## Filer genereret

- `scripts/make_3d_full_metrics.py` — 3D suite for alle 12 metrics
- `results/plots/3d/metric_3d_<METRIC>_<TICKER>.png` — 9 per-ticker 3D per metric
- `results/plots/3d/cross_median_<METRIC>.png` — cross-ticker median heatmap
- `results/plots/3d/cross_worst_<METRIC>.png` — cross-ticker worst heatmap
- `results/plots/3d/metrics_correlation_matrix.png` — correlation matrix
- `results/3d_metrics/cross_<METRIC>.csv` — raw data per metric
- `results/3d_metrics/sweet_spots_per_metric.csv` — sweet spots
- `results/3d_metrics/sweet_spots_meaningful.csv` — positive-only sweet spots
- `results/3d_metrics/metrics_correlation.csv` — correlation matrix
- `results/3d_corrected.csv` — full 1890-row sweep results

**Alle 11/11 unit tests passerer.**
