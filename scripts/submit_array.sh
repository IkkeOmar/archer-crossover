#!/usr/bin/env bash
# submit_array.sh — submit LSF job array of archer-crossover sweeps to DTU HPC.
#
# Run from a DTU HPC login node after uploading the project:
#     cd ~/archer-crossover
#     bash scripts/submit_array.sh
#
# Pattern: native LSF job array (bsub -J "name[indexList]") with a params.tsv
# row per (ticker, timeframe) combination. The cluster scheduler groups them
# under one job-name for easy monitoring (bjobs -J "sweep[*]") and supports
# wait dependencies (bsub -w "done(sweep)").
#
# Resource notes (DTU HPC, queue 'hpc'):
#   - 4 cores per job (numpy + BLAS threading)
#   - 8 GB memory per process (LSF: -M 8388608 KB)
#   - 2-hour walltime per job (max 72h on hpc queue)
#   - All cores on one node (span[hosts=1] for NUMA performance)

set -euo pipefail

# ---------------- configuration ----------------

QUEUE="hpc"
N_CORES=4
MEM_PER_PROC_KB=8388608  # 8 GB in KB
WALLTIME="02:00"
JOB_NAME="sweep"

# Module: prefer python3, fall back to anaconda3
if module is-available python3 2>/dev/null; then
  PY_MODULE="python3"
elif module is-available anaconda3 2>/dev/null; then
  PY_MODULE="anaconda3"
else
  echo "ERROR: neither python3 nor anaconda3 module available"
  exit 1
fi

# Per-asset-class timeframe lists.
# yfinance limits: 1m=7d, 2m/5m/15m=60d, 1h=730d, 1d=10y+
# Crypto via ccxt can go further back, but Phase 1 keeps stock/crypto parity.
STOCK_TIMEFRAMES=("1d" "1h")
CRYPTO_TIMEFRAMES=("1d" "1h" "15m")

# ---------------- ensure deps installed once ----------------

mkdir -p results/logs results/csv results/npz
module load "$PY_MODULE" 2>/dev/null || true
echo "Installing dependencies (once) ..."
pip install --quiet --user -r requirements.txt || pip install --quiet -r requirements.txt

# ---------------- build params.tsv ----------------

PARAMS_FILE="results/params.tsv"
echo -e "ticker\ttimeframe" > "$PARAMS_FILE"

N=0
for T in SPY QQQ IWM AAPL GOOGL BTC-USD ETH-USD GLD SLV; do
  if [[ "$T" == *"-USD"* ]]; then
    TIMEFRAMES=("${CRYPTO_TIMEFRAMES[@]}")
  else
    TIMEFRAMES=("${STOCK_TIMEFRAMES[@]}")
  fi
  for TF in "${TIMEFRAMES[@]}"; do
    echo -e "$T\t$TF" >> "$PARAMS_FILE"
    N=$((N + 1))
  done
done

echo "Built $PARAMS_FILE with $N (ticker, timeframe) combinations"
cat "$PARAMS_FILE"

# ---------------- submit job array ----------------

# Each task: one (ticker, timeframe) pair, full big_sweep with all freedoms
# Grid: 8 n_mu x 5 x x 3 bear_alloc x 3 ema_pair = 360 combos per task
# With 50 MC seeds + 35 WF windows = 360 * 50 * 35 = 630,000 backtests per task
# At ~0.0034s per backtest = ~36 min per task on 1 core, ~9 min on 4 cores
# 24 tasks total (9 tickers * 2-3 timeframes) = ~3.5 hours wall clock with parallelism

# Walltime budget: 4 hours per task (max 72h on hpc queue, leaving headroom)

echo
echo "Submitting job array 'sweep[1-$N]' to queue '$QUEUE' (${N_CORES} cores, ${MEM_PER_PROC_KB} KB mem, $WALLTIME walltime)"

bsub -q "$QUEUE" \
  -J "${JOB_NAME}[1-${N}]" \
  -n "$N_CORES" \
  -R "span[hosts=1]" \
  -R "rusage[mem=${MEM_PER_PROC_KB}]" \
  -M "$MEM_PER_PROC_KB" \
  -W "$WALLTIME" \
  -o "results/logs/${JOB_NAME}_%J_%I.out" \
  -e "results/logs/${JOB_NAME}_%I.err" \
  <<EOF
#!/bin/sh
#BSUB -q $QUEUE
#BSUB -J ${JOB_NAME}[\$LSB_JOBINDEX]
#BSUB -n $N_CORES
#BSUB -R "span[hosts=1]"
#BSUB -R "rusage[mem=${MEM_PER_PROC_KB}]"
#BSUB -M $MEM_PER_PROC_KB
#BSUB -W $WALLTIME
#BSUB -o results/logs/${JOB_NAME}_%J_%I.out
#BSUB -e results/logs/${JOB_NAME}_%J_%I.err

module load $PY_MODULE
export OMP_NUM_THREADS=$N_CORES
export MKL_NUM_THREADS=$N_CORES
export OPENBLAS_NUM_THREADS=$N_CORES

cd "\$HOME/archer-crossover"

# Read this job's parameters from params.tsv
ROW=\$(sed -n "\${LSB_JOBINDEX}p" results/params.tsv)
TICKER=\$(echo "\$ROW" | cut -f1)
TIMEFRAME=\$(echo "\$ROW" | cut -f2)

echo "[\$(date)] Job \$LSB_JOBINDEX: ticker=\$TICKER timeframe=\$TIMEFRAME"

# Run big_sweep.py (full freedom-sweep) instead of old src.sweep
python3 scripts/big_sweep.py \\
  --ticker "\$TICKER" \\
  --timeframe "\$TIMEFRAME" \\
  --n-mc-seeds 50 \\
  --n-wf-windows 35 \\
  --out-dir results/big_sweep

# Completion sentinel
touch results/.done_\${LSB_JOBINDEX}
EOF

echo
echo "Done. Monitor: bjobs -J \"${JOB_NAME}[*]\""
echo "Wait for all:  bsub -w \"ended(${JOB_NAME}[*])\" -o results/logs/aggregate.out -e results/logs/aggregate.err 'python3 -m src.report'"
