# 05-LSF-NOTES.md — DTU HPC LSF submission patterns

**Purpose:** Persistent notes on LSF (IBM Spectrum LSF) at DTU HPC. Reference when building/modifying submit scripts.

---

## LSF version on DTU HPC

- Per hpc.dtu.dk docs (read 2026-09-24): **LSF 10** family.
- Per sub-agent research: **LSF 9.3.1** reported via URL structure.
- **Conclusion:** Both support the same job array syntax. Use conservative directives that work on both.

## Job arrays (native)

```bash
# Submit an array of 21 jobs (one per (ticker, timeframe))
bsub -J "sweep[1-21]" -o "out_%I.log" -e "err_%I.log" <<EOF
#!/bin/sh
# Read row $LSB_JOBINDEX from params.tsv
ROW=\$(sed -n "\${LSB_JOBINDEX}p" params.tsv)
TICKER=\$(echo \$ROW | cut -f1)
TIMEFRAME=\$(echo \$ROW | cut -f2)
python3 -m src.sweep --ticker \$TICKER --timeframe \$TIMEFRAME
EOF

# List all jobs in the array
bjobs -J "sweep[*]"

# Wait for all jobs in array to finish
bsub -w "done(sweep)" ...post_processing.sh

# Wait for specific subset
bsub -w "ended(sweep[1-10])" ...
```

**Source:** IBM Spectrum LSF 10.1.0 docs + sub-agent research 2026-09-24.

---

## Resource directives

```bash
#BSUB -q hpc              # queue
#BSUB -J sweep[1-21]      # job name + array
#BSUB -n 4                # total cores for the job
#BSUB -R "span[hosts=1]"  # all cores on one node (critical for numpy/OMP)
#BSUB -R "rusage[mem=4194304]"  # memory per process in KB (4 GB)
#BSUB -M 8388608          # hard memory limit per process (KB), triggers kill if exceeded
#BSUB -W 02:00            # walltime HH:MM (max 72:00 on DTU hpc queue)
#BSUB -o out_%J_%I.out    # %J = job ID, %I = array index
#BSUB -e err_%J_%I.err
```

**Notes:**
- `-R "span[hosts=1]"` is critical for NumPy/OMP performance — avoids inter-node NUMA latency.
- LSF multiplies `-M` by `-n` for total job memory in some checks; we set 8GB per core (= 8388608 KB) to be safe.
- For vectorized numpy with BLAS: `export OMP_NUM_THREADS=$N_CORES; export MKL_NUM_THREADS=$N_CORES; export OPENBLAS_NUM_THREADS=$N_CORES` in the script body.

---

## DTU HPC specific

- **Login:** `login1.hpc.dtu.dk`, `login2.hpc.dtu.dk` (VPN required from outside)
- **Queue:** `hpc` is the general queue. Others: `gbar`, `gpua100`, etc.
- **Max walltime (hpc):** 72 hours per job
- **Max cores per user in queue:** 100-120
- **Module system:** `module load python3` or `module load anaconda3` — must be in script
- **Home dir:** `/home/s214473/` (NFS-mounted, backup tape, quota-limited)
- **Scratch:** `/scratch/$USER/` on compute nodes — fast local I/O for intermediate files
- **Status:** `bjobs`, `bhosts`, `nodestat`, `bstat`, `bhist`, `bpeek`, `showstart`
- **No GPU** needed for our sweep (numpy-vectorized, CPU-bound but fast)

---

## Aggregation patterns

- **File naming:** Always include `%J` (job ID) and `%I` (array index) in output files so jobs don't clobber each other.
- **Completion markers:** Defensive — each job should `touch results/.done_${LSB_JOBINDEX}` on success so post-process scripts can `wait` for the file count.
- **Post-processing:** Submit a final job with `-w "ended(sweep[*])"` that aggregates results and runs `python3 -m src.report`.
