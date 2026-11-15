#!/bin/bash
#SBATCH --job-name=legacy-tno-review
#SBATCH --time=00:08:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$1"
work="$2"
run="$3"
export PYTHONPATH="$PWD/src"
python="$work/smoke-venv/bin/python"
"$python" scripts/review-candidates.py "$work" "$run"
"$python" -m legacy_tno.cli plot --work "$work/runs/$run"
"$python" scripts/aggregate-pilot.py "$work/runs/$run" --work "$work"
