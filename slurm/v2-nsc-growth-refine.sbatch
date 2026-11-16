#!/bin/bash
#SBATCH --job-name=legacy-tno-v2-refine
#SBATCH --time=00:20:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
set -euo pipefail
cd "$1"
work="$2"
export PYTHONPATH="$PWD/src"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
python="$work/smoke-venv/bin/python"
for key in of201 tv158; do
    target="2017 OF201"
    [[ "$key" != tv158 ]] || target="2013 TV158"
    trial="$work/v2/nsc-grow-$key-scored-detail.json"
    selection="$work/v2/nsc-grow-$key-refined-private.json"
    "$python" scripts/refine-nsc-growth.py "$work" "$trial" --output "$selection"
    "$python" scripts/score-nsc-growth.py "$trial" "$target" \
        "$work/v2/nsc-grow-$key-refined-summary.json" --anonymous-selection "$selection"
done
