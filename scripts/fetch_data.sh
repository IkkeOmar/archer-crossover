#!/usr/bin/env bash
# fetch_data.sh — wrapper around data_loader for local use.
# Run from project root: bash scripts/fetch_data.sh
#
# Downloads OHLCV for our default ticker set. Adjust the tickers/timeframes
# below for your run.

set -euo pipefail

cd "$(dirname "$0")/.."

TICKERS="${TICKERS:-SPY,QQQ,IWM,AAPL,GOOGL,GLD,SLV}"
TIMEFRAMES="${TIMEFRAMES:-1d,1h}"
START="${START:-2015-01-01}"
INCLUDE_CRYPTO="${INCLUDE_CRYPTO:-1}"

ARGS="--tickers $TICKERS --timeframes $TIMEFRAMES --start $START"
if [[ "$INCLUDE_CRYPTO" == "1" ]]; then
  ARGS="$ARGS --include-crypto"
fi

echo "Fetching data: $ARGS"
python3 -m src.data_loader $ARGS
