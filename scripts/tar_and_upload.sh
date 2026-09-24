#!/usr/bin/env bash
# tar_and_upload.sh — package the project for upload to DTU HPC.
#
# Run from project root: bash scripts/tar_and_upload.sh
#
# Produces archer-crossover.tar.gz in project root, excludes data/ and results/.
# Then prints the scp command for you to run (since we don't have your DTU password here).

set -euo pipefail

cd "$(dirname "$0")/.."

OUT="archer-crossover.tar.gz"
echo "Creating $OUT ..."
tar czf "$OUT" \
  --exclude='data/*.csv' \
  --exclude='results/csv/*.csv' \
  --exclude='results/csv/*.json' \
  --exclude='results/npz/*.npz' \
  --exclude='results/plots/**/*.png' \
  --exclude='__pycache__' \
  --exclude='.git' \
  .

echo "Tarball ready: $OUT"
ls -lh "$OUT"

USER="${DTU_USER:-s214473}"
HOST="${DTU_HOST:-login1.hpc.dtu.dk}"
echo
echo "Upload command (run this yourself with your DTU password):"
echo "    scp $OUT ${USER}@${HOST}:~/"
echo
echo "Then on the cluster:"
echo "    ssh ${USER}@${HOST}"
echo "    cd ~"
echo "    tar xzf archer-crossover.tar.gz"
echo "    cd archer-crossover"
echo "    bash scripts/fetch_data.sh    # download data (one-time)"
echo "    bash scripts/submit_array.sh  # submit sweep jobs"
