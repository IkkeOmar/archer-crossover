#!/bin/bash
# run_local_sweep_1h.sh — re-run 1h sweep after fixing tz bug
set -u
cd /home/omar/2026-09-24/archer-crossover
OUT=results/cluster_local

PAIRS=(
  "SPY:1h" "QQQ:1h" "IWM:1h" "AAPL:1h" "GOOGL:1h"
  "BTC-USD:1h" "ETH-USD:1h" "GLD:1h" "SLV:1h"
)

for p in "${PAIRS[@]}"; do
  T="${p%%:*}"
  TF="${p##*:}"
  T_SAN="${T//-/_}"
  CSV="$OUT/${T_SAN}_${TF}.csv"
  if [ -f "$CSV" ] && [ "$(wc -l < "$CSV")" -gt 100 ]; then
    echo "[skip] $T $TF -> $CSV already exists"
    continue
  fi
  echo "[run]  $T $TF starting at $(date +%H:%M:%S)"
  python3 scripts/big_sweep.py \
    --ticker "$T" --timeframe "$TF" \
    --n-mc-seeds 20 --n-wf-windows 20 --limit-combos 8 \
    --out-dir "$OUT" 2>&1 | tail -3
  echo "[done] $T $TF at $(date +%H:%M:%S)"
done

echo "1H ALL DONE at $(date)"
ls -la "$OUT" | grep _1h