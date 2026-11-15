#!/bin/bash
#SBATCH --job-name=legacy-tno-deep
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=24G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1 LEGACY_TNO_WORKERS=12
cd "$1"
w="$2"
export PYTHONPATH="$PWD/src"
python="$w/smoke-venv/bin/python"
"$python" scripts/select-deep-validation.py "$w"
"$python" -m legacy_tno.cli run --work "$w" --config configs/deep.json \
  --fields "$w/inputs/selected-deep-validation.json" --field validation --commit "$3" --resume
