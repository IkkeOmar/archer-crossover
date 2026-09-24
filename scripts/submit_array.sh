#!/usr/bin/env bash
# submit_array.sh — submit one LSF job per (ticker, timeframe) combination to DTU HPC.
#
# Run from a DTU HPC login node (login1.hpc.dtu.dk) after uploading the project:
#     cd ~/archer-crossover
#     bash scripts/submit_array.sh
#
# Each job runs:
#     python3 -m src.sweep --ticker <T> --timeframe <TF> --grid-mode default
# Output goes to:
#     results/csv/<T>_<TF>.csv
#     results/csv/<T>_<TF>_summary.json
#     results/npz/<T>_<TF>_raw.npz
#
# Resource notes (DTU HPC, queue 'hpc'):
#   - 4 cores per job (vectorized numpy uses BLAS threads)
#   - 8 GB memory per job
#   - 2 hour walltime per job
#   - Max 100 concurrent jobs per user in 'hpc' queue

set -euo pipefail

# ---------------- configuration ----------------

# Module: try python3 first, fall back to anaconda3
PY_MODULE="python3"
if ! module is-available python3 2>/dev/null; then
  PY_MODULE="anaconda3"
fi

QUEUE="hpc"
N_CORES=4
MEM_GB=8
WALLTIME="02:00"

TICKERS=(
  "SPY" "QQQ" "IWM" "AAPL" "GOOGL"
  "BTC-USD" "ETH-USD" "GLD" "SLV"
)

# Per-asset-class timeframe lists.
# yfinance limits: 1m=7d, 2m=60d, 5m=60d, 15m=60d, 1h=730d, 1d=10y+
# We'll keep Phase 1 to timeframes that have meaningful history.
STOCK_TIMEFRAMES=("1d" "1h")
CRYPTO_TIMEFRAMES=("1d" "1h" "15m")

# ---------------- ensure deps installed once ----------------

echo "Installing dependencies (once) ..."
module load "$PY_MODULE" 2>/dev/null || true
pip install --quiet --user -r requirements.txt || pip install --quiet -r requirements.txt

# ---------------- submit jobs ----------------

SUBMITTED=0
for T in "${TICKERS[@]}"; do
  if [[ "$T" == *"-USD"* ]]; then
    TIMEFRAMES=("${CRYPTO_TIMEFRAMES[@]}")
  else
    TIMEFRAMES=("${STOCK_TIMEFRAMES[@]}")
  fi
  for TF in "${TIMEFRAMES[@]}"; do
    JOBNAME="archer_${T}_${TF}"
    OUT="results/logs/${JOBNAME}_%J.out"
    ERR="results/logs/${JOBNAME}_%J.err"
    mkdir -p results/logs
    echo "Submitting: ${JOBNAME} (${N_CORES} cores, ${MEM_GB}GB, ${WALLTIME})"
    bsub \
      -q "$QUEUE" \
      -J "$JOBNAME" \
      -n "$N_CORES" \
      -R "span[hosts=1]" \
      -R "rusage[mem=${MEM_GB}GB]" \
      -M "${MEM_GB}GB" \
      -W "$WALLTIME" \
      -o "$OUT" \
      -e "$ERR" \
      <<EOF
#!/bin/sh
module load $PY_MODULE
export OMP_NUM_THREADS=$N_CORES
export MKL_NUM_THREADS=$N_CORES
export OPENBLAS_NUM_THREADS=$N_CORES
cd "\$HOME/archer-crossover"
python3 -m src.sweep --ticker "$T" --timeframe "$TF" --grid-mode default
EOF
    SUBMITTED=$((SUBMITTED + 1))
  done
done

echo
echo "Submitted $SUBMITTED jobs. Monitor with: bjobs"
echo "After all complete, aggregate with: python3 -m src.report --in results/csv --out paper/"
