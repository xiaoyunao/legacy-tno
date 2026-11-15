#!/bin/bash
#SBATCH --job-name=legacy-tno-of201-id
#SBATCH --time=00:10:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$1"
work="$2"
log="$3"
run=$(sed -n 's/^RUN_PATH=.*\///p' "$log" | head -1)
test -n "$run"
export PYTHONPATH="$PWD/src"
"$work/smoke-venv/bin/python" scripts/identify-of201.py "$work" "$run"
"$work/smoke-venv/bin/python" scripts/aggregate-pilot.py "$work/runs/$run" --work "$work"
