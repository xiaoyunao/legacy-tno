#!/bin/bash
#SBATCH --job-name=legacy-tno-identity
#SBATCH --time=00:12:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$1"
work="$2"
rev="$3"
shift 3
export PYTHONPATH="$PWD/src"
for run in "$@"; do
    if test -s "$work/runs/$run/blind_candidates.json"; then
        "$work/smoke-venv/bin/python" scripts/reidentify-des.py "$work" "$run" --commit "$rev"
        "$work/smoke-venv/bin/python" scripts/aggregate-pilot.py "$work/runs/$run" --work "$work"
    else
        printf 'Waiting for blind output for %s\n' "$run"
    fi
done
