"""data_loader.py — fetch OHLCV from yfinance + ccxt, cache to CSV.

Sources:
- yfinance: stocks, ETFs, indices, BTC-USD/ETH-USD via Yahoo
- ccxt: BTC, ETH on Binance (sub-15m timeframes)

Output:
- data/<ticker_sanitized>_<timeframe>.csv with columns: date, open, high, low, close, volume

CLI usage:
    python3 -m src.data_loader --tickers SPY,QQQ --timeframes 1d,1h --start 2015-01-01
"""
from __future__ import annotations

import argparse
import os
import re
import time
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_ticker(ticker: str) -> str:
    """BTC-USD -> BTC_USD; BRK.B -> BRK_B; etc."""
    return re.sub(r"[^A-Za-z0-9]", "_", ticker)


def _tf_to_yf_interval(timeframe: str) -> str:
    """Map our timeframe names to yfinance interval strings."""
    mapping = {
        "1m": "1m",
        "2m": "2m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "60m": "60m",
        "1h": "60m",
        "90m": "90m",
        "1d": "1d",
        "5d": "5d",
        "1wk": "1wk",
        "1mo": "1mo",
        "3mo": "3mo",
    }
    return mapping[timeframe]


def fetch_yfinance(
    ticker: str,
    timeframe: str,
    start: str | None = None,
    end: str | None = None,
    period: str | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Download OHLCV from Yahoo Finance.

    Args:
        ticker: Yahoo ticker (e.g. 'SPY', 'BTC-USD', '^GSPC').
        timeframe: one of 1m,2m,5m,15m,30m,1h,90m,1d,5d,1wk,1mo,3mo.
        start: ISO date string. If None, uses period.
        end: ISO date string. If None, defaults to today.
        period: yfinance period string ('max', '10y', '5y', etc.).
        progress: show progress bar.

    Returns:
        DataFrame with columns: open, high, low, close, volume, adj_close. Indexed by date.
    """
    import yfinance as yf

    interval = _tf_to_yf_interval(timeframe)
    if progress:
        print(f"  yfinance: {ticker} {timeframe} (interval={interval})")
    kwargs: dict = {
        "tickers": ticker,
        "interval": interval,
        "progress": progress,
        "auto_adjust": False,
        "actions": False,
    }
    if start is not None:
        kwargs["start"] = start
    if end is not None:
        kwargs["end"] = end
    if period is not None:
        kwargs["period"] = period
    df = yf.download(**kwargs)
    assert df is not None, "yfinance returned None"
    if df.empty:
        raise ValueError(f"No data returned for {ticker} {timeframe}")
    # yfinance returns multi-index columns when given a single ticker via some paths;
    # normalize to flat columns.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    df.index.name = "date"
    return df


def fetch_ccxt(
    symbol: str,
    timeframe: str,
    exchange: str = "binance",
    start: str | None = None,
    end: str | None = None,
    limit: int = 1000,
    progress: bool = False,
) -> pd.DataFrame:
    """Fetch OHLCV from a ccxt exchange. Symbols are CCXT-style: 'BTC/USDT'.

    Args:
        symbol: e.g. 'BTC/USDT'.
        timeframe: 1m, 5m, 15m, 1h, 4h, 1d, etc.
        exchange: exchange id ('binance', 'kraken', 'coinbasepro', etc.).
        start/end: ISO date strings.
        limit: max rows per request (ccxt default 1000).
        progress: print progress.

    Returns:
        DataFrame with columns: date, open, high, low, close, volume.
    """
    import ccxt

    ex_class = getattr(ccxt, exchange)
    ex = ex_class({"enableRateLimit": True})
    tf = _tf_to_ccxt_timeframe(timeframe)
    since = (
        int(pd.Timestamp(start, tz="UTC").timestamp() * 1000) if start else None
    )
    end_ms = (
        int(pd.Timestamp(end, tz="UTC").timestamp() * 1000) if end else None
    )
    all_rows = []
    while True:
        if progress:
            print(f"  ccxt: {exchange} {symbol} {timeframe} (fetching up to {limit} rows)")
        ohlcv = ex.fetch_ohlcv(symbol, tf, since=since, limit=limit)
        if not ohlcv:
            break
        all_rows.extend(ohlcv)
        last_ts = ohlcv[-1][0]
        since = last_ts + 1  # next millisecond
        if end_ms and since >= end_ms:
            break
        if len(ohlcv) < limit:
            break
        time.sleep(ex.rateLimit / 1000.0)
    if not all_rows:
        raise ValueError(f"No data from {exchange} {symbol} {timeframe}")
    rows_df = pd.DataFrame(
        all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df = rows_df.copy()
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("date")[["open", "high", "low", "close", "volume"]]
    df.index.name = "date"
    return df


def _tf_to_ccxt_timeframe(timeframe: str) -> str:
    """Map our timeframe names to ccxt timeframe strings."""
    mapping = {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "6h": "6h",
        "12h": "12h",
        "1d": "1d",
        "1w": "1w",
    }
    if timeframe not in mapping:
        raise ValueError(f"ccxt does not support timeframe {timeframe}")
    return mapping[timeframe]


def _is_crypto_ticker(ticker: str) -> bool:
    return ticker.upper().endswith("-USD") or "/" in ticker


def _yfinance_ticker(ticker: str) -> str:
    """Convert our symbol to yfinance symbol."""
    return ticker  # already yfinance-format by convention


def _ccxt_symbol(ticker: str) -> str:
    """BTC-USD -> BTC/USDT for Binance."""
    if "/" in ticker:
        return ticker
    if ticker.endswith("-USD"):
        base = ticker[:-4]
        return f"{base}/USDT"
    raise ValueError(f"Cannot convert {ticker} to ccxt symbol")


def load_one(
    ticker: str,
    timeframe: str,
    start: str | None = None,
    end: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Load OHLCV for one (ticker, timeframe), using cache if available.

    Cache location: data/<sanitized_ticker>_<timeframe>.csv
    Cache key includes start date so re-requests with different start produce different files.

    Returns:
        DataFrame with columns: open, high, low, close, volume.
    """
    cache_key = f"{_sanitize_ticker(ticker)}_{timeframe}"
    if start:
        cache_key += f"_{start}"
    if end:
        cache_key += f"_{end}"
    cache_path = DATA_DIR / f"{cache_key}.csv"

    if cache_path.exists() and not force_refresh:
        df = pd.read_csv(cache_path, parse_dates=["date"], index_col="date")
        return df

    if _is_crypto_ticker(ticker):
        df = fetch_ccxt(
            _ccxt_symbol(ticker),
            timeframe,
            start=start,
            end=end,
        )
    else:
        df = fetch_yfinance(ticker, timeframe, start=start, end=end)

    df.to_csv(cache_path)
    return df


def load_many(
    tickers: list[str],
    timeframes: list[str],
    start: str | None = None,
    end: str | None = None,
    force_refresh: bool = False,
) -> dict[tuple[str, str], pd.DataFrame]:
    """Load OHLCV for many (ticker, timeframe) pairs. Returns {(ticker, tf): df}."""
    out: dict[tuple[str, str], pd.DataFrame] = {}
    for t in tickers:
        for tf in timeframes:
            try:
                df = load_one(t, tf, start=start, end=end, force_refresh=force_refresh)
                out[(t, tf)] = df
                print(f"  OK: {t} {tf} ({len(df)} rows)")
            except Exception as e:
                print(f"  FAIL: {t} {tf}: {e}")
    return out


def main():
    parser = argparse.ArgumentParser(description="Fetch OHLCV data for archer-crossover")
    parser.add_argument(
        "--tickers",
        default="SPY,QQQ,IWM,AAPL,GOOGL,GLD,SLV",
        help="Comma-separated tickers",
    )
    parser.add_argument(
        "--timeframes",
        default="1d,1h,15m",
        help="Comma-separated timeframes",
    )
    parser.add_argument(
        "--start",
        default="2015-01-01",
        help="Start date (ISO)",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="End date (ISO)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-download even if cache exists",
    )
    parser.add_argument(
        "--include-crypto",
        action="store_true",
        help="Also fetch BTC-USD, ETH-USD via ccxt",
    )
    args = parser.parse_args()
    tickers = [t.strip() for t in args.tickers.split(",")]
    if args.include_crypto:
        tickers += ["BTC-USD", "ETH-USD"]
    timeframes = [t.strip() for t in args.timeframes.split(",")]
    load_many(tickers, timeframes, start=args.start, end=args.end, force_refresh=args.force_refresh)


if __name__ == "__main__":
    main()
