#!/bin/bash
#SBATCH --job-name=legacy-tno-pilot
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=24G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1 LEGACY_TNO_WORKERS=12
cd "$1"
work="$2"
shift 2
export PYTHONPATH="$PWD/src"
"$work/smoke-venv/bin/python" -m legacy_tno.cli run --work "$work" --config configs/pilot.json \
    --fields "$work/inputs/selected-fields.json" "$@"
