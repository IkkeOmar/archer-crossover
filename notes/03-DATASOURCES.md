# 03-DATASOURCES.md

**Purpose:** Evaluated data sources for OHLCV (and later options) data. Each source: coverage, cost, ease-of-use, gotchas.

---

## yfinance

- **What:** Yahoo Finance unofficial Python wrapper
- **Coverage:** Stocks (US + global), ETFs, indices, crypto (BTC-USD, ETH-USD), some FX
- **Timeframes:** 1m (7d), 2m (60d), 5m (60d), 15m (60d), 1h (730d), 1d (10y+), 1wk, 1mo
- **Cost:** Free, no API key
- **License:** Yahoo ToS prohibits redistribution of bulk downloads — keep data local, do not republish
- **Reliability:** Unofficial, occasionally breaks when Yahoo changes their internal API. Pin a known-working version.
- **Gotchas:**
  - Sub-daily data has gaps for non-US stocks (e.g. European ETFs may have weird hours)
  - Adjusted close is default — make sure we're consistent with raw close if we want to model dividends explicitly
  - Rate limits can hit on large parallel downloads — stagger requests
- **Verdict:** PRIMARY source for daily + 1h + 15m on all tickers

## ccxt

- **What:** Unified crypto exchange API (Python wrapper)
- **Coverage:** BTC, ETH, and 100+ other crypto pairs on 100+ exchanges
- **Timeframes:** 1m through 1M (varies by exchange)
- **Cost:** Free for public market data (no API key needed for read-only)
- **Reliability:** Official wrappers, well-maintained
- **Gotchas:**
  - Exchange-specific quirks (Binance has deepest history; Coinbase Pro removed in 2022)
  - Rate limits per exchange
- **Verdict:** PRIMARY source for sub-15m crypto data

## Alpha Vantage

- **What:** Freemium stock/forex/crypto data
- **Coverage:** US stocks, ETFs, FX, crypto
- **Free tier:** 25 requests/day, 5 requests/min — VERY LIMITED for backfills
- **Cost:** $49.99/mo for premium tier
- **Verdict:** Backup if yfinance breaks, but free tier too small for our use

## Polygon.io

- **What:** Premium market data provider
- **Coverage:** US stocks, options, forex, crypto
- **Free tier:** 5 calls/min — limited
- **Paid tier:** $29/mo starter, $79/mo for options data
- **Verdict:** Best for options data (Phase 3), but paid. Skip for now.

## Tiingo

- **What:** EOD historical data + fundamentals
- **Coverage:** US + international stocks, ETFs, crypto
- **Free tier:** 500 symbols, 1000 requests/day — workable
- **Cost:** $10/mo for full features
- **Verdict:** Possible backup, especially for international stocks

## Datahub.io / Kaggle datasets

- **What:** Pre-downloaded CSV bundles of historical OHLCV
- **Use case:** When API rate limits are too strict, fall back to bulk CSV downloads
- **Verdict:** Last resort

## CBOE / OCC (options chains)

- **What:** Official US options data
- **Coverage:** All US listed options
- **Cost:** Paid, $$$$
- **Verdict:** Defer to Phase 3 — we'll simulate hedge with 15% drag, no real options data needed in Phase 1

---

## Decision matrix (Phase 1)

| Asset | Timeframe | Source |
|---|---|---|
| Stocks/ETFs | 1d, 1h, 15m, 5m | yfinance |
| Stocks/ETFs | 1m | SKIP (Yahoo 7d limit not enough) |
| Crypto | 1d, 4h, 1h, 15m, 5m | yfinance |
| Crypto | 3m, 2m, 1m | ccxt (Binance) |
