# LSF job submission for DTU HPC

```bash
bsub < submit_array.sh
```

Submits one LSF job per (ticker, timeframe) combination. Each job runs `src/sweep.py` for that combo. Results aggregate into `results/`.

Status: STUB. To be implemented after data_loader + engine are ready.
