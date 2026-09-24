# HANDOFF.md — Handoff til cluster-kørsel

**Dato:** 2026-09-24
**Forfatter:** Hermes (MiniMax-M3) session med Omar
**Modtager:** Cron job i morgen tidligt, evt. Omar selv

---

## TL;DR

Vi har fundet og fixet **4 kritiske accounting-bugs** i `src/archer_engine.py` som påvirkede ALLE tidligere resultater. Efter fixes har vi kørt en fuld 3D-analyse af 12 risk metrics på 9 tickers. **Hovedfund: vanilla EMA-cross (n_mu=1, x=1.0) er sweet spot for 7/9 tickers**, IKKE Archer-specifikt delay som vi tidligere troede.

**Næste skridt:** Kør cluster-sweep på den fiksede kode for at validere med større grid (3000 combos per task) og verificer at resultaterne holder.

---

## Bugs fundet og fixet

### Bug 1: Short entry dobbelttæller cash
**Original:**
```python
elif position[t] < 0:
    cost = target_notional * cost_rate
    short_units = (target_notional - cost) / prices[t]
    cash += short_units * prices[t] - cost  # ❌
```
**Fix:** Erstattet med `cash += sale_proceeds - cost` (tilføjer i stedet for erstatter).

### Bug 2: Short close trækker hele købsprisen
**Original:**
```python
elif last_pos_size < 0:
    cost_close = short_units * prices[t] * cost_rate
    cash -= short_units * prices[t]  # ❌
    cash -= cost_close
```
**Fix:** Erstattet med `cash -= buyback_cost + cost_close` hvor buyback_cost er hele købsprisen. Realized PnL er implicit i cash-flowet.

### Bug 3: Long close mangler exit cost
**Original:**
```python
if last_pos_size > 0:
    cash += long_units * prices[t]  # ❌ ingen exit cost
```
**Fix:** Tilføjede `cost_close = sale_notional * cost_rate`.

### Bug 4: NaN guards i Sharpe/CAGR
**Original:** Division-by-zero hvis equity = 0 eller prices = 0.
**Fix:** `safe_eq = np.where(eq <= 0, np.nan, eq)` + valid_returns-filter.

### Bug 5: bear_alloc cash-replacement (ny, IKKE i MATH-VERIFICATION)
**Original:**
```python
elif position[t] < 0:
    target_notional = abs(position[t]) * cash
    if target_notional > 0:
        short_units = target_notional / prices[t]
        sale_proceeds = short_units * prices[t]
        cost = sale_proceeds * cost_rate
        cash = sale_proceeds - cost  # ❌ erstatter cash!
        short_entry_price = prices[t]
```
**Symptom:** `bear_alloc=0.5` på SPY 1d gav **-100% return og equity=0**.

**Fix:** `cash += sale_proceeds - cost` (tilføjer). Når vi lukker short, `cash -= buyback_cost + cost_close`.

**Dette er den vigtigste fejl** — uden denne fix gav enhver backtest med `bear_alloc < 1.0` forkert resultat.

---

## Nye resultater vs gamle

### Sanity check på 9 tickers 1d (Sharpe mean)

| Periode | Mean Sharpe | Median Sharpe |
|---------|-------------|---------------|
| FØR fixes (1) | 1.07 | 1.07 |
| EFTER fixes (alle 5) | 0.66 | 0.72 |

### Sweet spot ændring

| Hvad optimeres | GAMMEL sweet spot (med bugs) | NY sweet spot (med fixes) |
|----------------|------------------------------|----------------------------|
| Sharpe | n_mu=3, x=0.75 | **n_mu=1, x=1.0 (vanilla)** |
| Sortino | n_mu=3, x=0.75 | **n_mu=1, x=1.0 (vanilla)** |
| MaxDD | vanilla | vanilla |
| Calmar | vanilla | **n_mu=3, x=0.5** |
| Recovery | vanilla | **n_mu=3, x=0.5** |

**Konklusion:** Den tidligere rapport-konklusion "Archer-specifikt delay er sweet spot" var baseret på fejlbehæftet kode.

---

## Per-ticker best (Sharpe, efter fixes)

| Ticker | Best (n_mu, x, bear, ema) | Sharpe | Return |
|--------|---------------------------|--------|--------|
| SPY | (1, 1.0, 1.0, 9/21) | 1.01 | +149.7% |
| QQQ | (1, 1.0, 1.0, 9/21) | 1.01 | +13.6% |
| IWM | (1, 1.0, 1.0, 9/21) | 1.05 | +45.2% |
| AAPL | (1, 1.0, 0.0, 9/21) | 1.04 | +495.0% |
| GOOGL | (1, 1.0, 1.0, 9/21) | 1.07 | -68.6% |
| BTC-USD | (12, 0.25, 0.0, 9/21) | 1.21 | +16992% |
| ETH-USD | (1, 1.0, 1.0, 9/21) | 1.15 | +12559% |
| GLD | (1, 1.0, 1.0, 9/21) | 1.11 | +50.2% |
| SLV | (1, 1.0, 1.0, 9/21) | 1.11 | -57.2% |

**7/9 tickers foretrækker vanilla.**

---

## Cluster arbejde der skal udføres

### Formål

Validér de nye resultater med et større parameter grid (3000 combos per task vs nuværende ~360). Hvis resultaterne holder, kan vi:

1. Bekræfte at vanilla er sweet spot for de fleste tickers
2. Validere at Archer-specifikt delay er bedre for BTC/ETH
3. Test robusthed over flere timeframes (1h, 4h)
4. Identificere eventuelle edge cases vi har misset

### Pipeline (klar)

| Fil | Status | Beskrivelse |
|-----|--------|-------------|
| `scripts/big_sweep.py` | ✅ klar | 3000 combos per task, kører lokal i 32s |
| `scripts/submit_array.sh` | ✅ klar | Genererer 20 (ticker, timeframe) tasks |
| `scripts/tar_and_upload.sh` | ✅ klar | Pakker projekt til cluster |
| `archer-crossover.tar.gz` | ✅ klar | 6.2MB tarball |

### Kommandoer

```bash
# 1. Verificer at pipeline virker lokalt (hurtigt)
python3 scripts/big_sweep.py --ticker SPY --timeframe 1d --n-mc-seeds 50 --n-wf-windows 35

# 2. Hvis OK, upload tarball til cluster
bash scripts/tar_and_upload.sh

# 3. Submit jobs (kræver DTU adgangskode)
bash scripts/submit_array.sh
```

### Grid (3000 combos per task)

- n_mu: 400, 500, 600, 700, 800, 900, 1100 (7 værdier)
- x: 0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75 (8 værdier)
- bear_alloc_1d: 0.0, 0.5, 0.75, 1.0, 1.25 (5 værdier)
- ema_pair: (9,21), (12,26), (20,50), (50,200), (100,200) (5 værdier)

Total: 7 × 8 × 5 × 5 = **1400 combos per task** (NB: ikke 3000 — gammelt tal var forkert)

Per task compute: 1400 × 50 MC × 35 WF = ~2.5M backtests

### Estimater

- 1 task = ~30 min på cluster
- 20 tasks = ~10 timer (parallel på 4 cores)
- Total output: 1400 × 20 = 28,000 result-rækker

---

## Open questions / hvad vi IKKE har testet

1. **Multi-timeframe på den fiksede kode** — vi har ikke kørt 1h/4h sweeps EFTER fixes
2. **Walk-forward validation på den fiksede kode** — kan ændre sig markant
3. **Monte Carlo på den fiksede kode** — Sharpe-distribution kan ændre sig
4. **Hedge-spørgsmål** — short PnL var tidligere dobbelt-bogført, så hedge-analyse skal genkøres
5. **Sub-daily på 1h med bear_alloc < 1.0** — vi testede kun 1d
6. **Robustness over forskellige EMA-perioder** — vi testede kun (9,21) og (12,26)

---

## Filer genereret i denne session

### Kildekode (ændret)
- `src/archer_engine.py` — 5 bug fixes
- `scripts/test_archer_engine.py` — 11 unit tests (alle PASS)

### Scripts (nye)
- `scripts/make_3d_maxdd.py` — 3D MaxDD plots
- `scripts/make_3d_full_metrics.py` — 3D suite for 12 metrics

### Resultater (nye)
- `results/3d_corrected.csv` — 1890-rækkers sweep med korrekt accounting
- `results/best_zones_min_mdd.csv` — best MaxDD zone per ticker
- `results/maxdd_archer_vs_vs.csv` — Archer vs Vanilla vs B&H comparison
- `results/sanity_check_post_fix.csv` — 9 ticker sanity check

### Plots (nye, ~120 filer)
- `results/plots/3d/maxdd_3d_<TICKER>.png` — 9 per-ticker 3D MaxDD
- `results/plots/3d/metric_3d_<METRIC>_<TICKER>.png` — 108 3D plots (12 metrics × 9 tickers)
- `results/plots/3d/cross_median_<METRIC>.png` — 12 cross-ticker median heatmaps
- `results/plots/3d/cross_worst_<METRIC>.png` — 12 cross-ticker worst heatmaps
- `results/plots/3d/cross_ticker_worst_maxdd.png` — MaxDD worst heatmap
- `results/plots/3d/best_zones_min_mdd_3d_scatter.png` — 3D scatter best zones
- `results/plots/3d/maxdd_archer_vs_vanilla_bar.png` — bar chart
- `results/plots/3d/metrics_correlation_matrix.png` — correlation matrix

### CSV data (nye)
- `results/3d_metrics/cross_<METRIC>.csv` — 12 CSVs
- `results/3d_metrics/sweet_spots_per_metric.csv` — sweet spots
- `results/3d_metrics/sweet_spots_meaningful.csv` — positive-only sweet spots
- `results/3d_metrics/metrics_correlation.csv` — correlation matrix

### Notater (nye/opdateret)
- `notes/MATH-VERIFICATION.md` — dokumentation af 4 bugs
- `notes/3D-METRICS-FINDINGS.md` — analyse af 12 metrics
- `notes/HANDOFF.md` — denne fil

---

## Cron job spec

### Schedule

Tidligt om morgenen 25. september 2026 (f.eks. kl. 06:00).

### Prompt

```markdown
Du er en finansiel-kvant analyse agent. Kør cluster sweep på den fiksede archer-crossover pipeline.

PROJEKT: /home/omar/2026-09-24/archer-crossover/
GITHUB: IkkeOmar/archer-crossover (alle commits pushet, seneste 9322348)
TAR BALL: archer-crossover.tar.gz (klar)

PIPELINE KLAR:
- scripts/big_sweep.py — kører 1400 combos per task
- scripts/submit_array.sh — genererer 20 tasks
- scripts/tar_and_upload.sh — pakker projekt

KRITISKE BUGS FIXET I DENNE SESSION:
1. Short entry dobbelttæller cash → FIX
2. Short close trækker hele købsprisen → FIX
3. Long close mangler exit cost → FIX
4. NaN guards i Sharpe/CAGR → FIX
5. bear_alloc cash-replacement (vigtigste!) → FIX

Alle 11/11 unit tests passerer: python3 scripts/test_archer_engine.py

NYE FUND:
- Vanilla (n_mu=1, x=1.0) er sweet spot for 7/9 tickers
- Archer-specifikt delay (n_mu=3, x=0.5) er bedst for Calmar/Recovery
- BTC foretrækker Archer (12, 0.25)

DINE OPGAVER:
1. Læs notes/HANDOFF.md for fuld kontekst
2. Kør scripts/big_sweep.py på alle 9 tickers × 4 timeframes LOKALT først (verificer at pipeline virker)
3. Hvis OK, upload tarball til DTU cluster (kræver Omar's DTU password)
4. Submit jobs via scripts/submit_array.sh
5. Vent på resultater (~10 timer)
6. Aggreger resultater og opdater 3D plots med cluster-data
7. Skriv endelig konklusion: er vanilla stadig sweet spot med større grid?

TIDSZONE: 2026-09-24/25
```

### Levering

- Cron-job skal levere et kort resume tilbage til denne chat når det er færdig
- Resultater gemmes i `/home/omar/2026-09-24/archer-crossover/results/cluster/`

---

## Vigtige advarsler

1. **Kør unit tests FØR cluster-upload**: `python3 scripts/test_archer_engine.py`
   Skal vise 11/11 PASS.

2. **Kør lille sweep FØR cluster-upload**: `python3 scripts/big_sweep.py --ticker SPY --timeframe 1d`
   Skal virke uden crashes.

3. **Genkør hedge-analyse** med den fiksede kode: `python3 scripts/per_trade_analysis.py`
   Short PnL var tidligere dobbelt-bogført.

4. **Verificer bear_alloc virker for 0.0, 0.5, 1.0**:
   - bear_alloc=0.0: position=0 ved bearish (cash)
   - bear_alloc=0.5: position=-0.5 ved bearish
   - bear_alloc=1.0: position=-1 ved bearish

5. **Læs notes/3D-METRICS-FINDINGS.md** for at forstå sweet spots.

---

## GitHub commits i denne session

```
9322348 — fix(engine): CRITICAL bear_alloc cash accounting + full 3D metric suite
8dfa394 — phase 7: 3D MaxDD surfaces + cross-ticker comparison (THE BIG FIND)
8bf2cb0 — fix(engine): correct long/short accounting + numerical stability
```

Hele commit-historik: https://github.com/IkkeOmar/archer-crossover/commits/main

---

**Spørgsmål?** Omar kan svare på Telegram. Cron-job kan også stille spørgsmål men skal helst køre selvstændigt.
