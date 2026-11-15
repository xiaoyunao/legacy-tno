#!/bin/bash
#SBATCH --job-name=legacy-tno-aggregate
#SBATCH --time=00:10:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$1"
work="$2"
shift 2
export PYTHONPATH="$PWD/src"
python="$work/smoke-venv/bin/python"
for run in "$@"; do
  "$python" scripts/aggregate-pilot.py "$work/runs/$run" --work "$work"
done
