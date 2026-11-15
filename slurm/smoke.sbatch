#!/bin/bash
#SBATCH --job-name=legacy-tno-smoke
#SBATCH --time=00:12:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=22G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
project="$1"
work="$2"
cd "$project"
mkdir -p "$work/smoke"
python="$work/smoke-venv/bin/python"
if ! test -x "$python"; then
    "$HOME/miniconda3/envs/asteroid/bin/python" -m venv "$work/smoke-venv"
fi
"$python" -m pip install --disable-pip-version-check --timeout 20 -r configs/requirements.txt
export PYTHONPATH="$project/src"
"$python" -m legacy_tno.profile "$work/smoke" --quick
