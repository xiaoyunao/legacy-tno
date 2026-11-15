#!/bin/bash
#SBATCH --job-name=legacy-tno-profile
#SBATCH --time=00:25:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
project="$1"
work="$2"
cd "$project"
mkdir -p "$work/profile"
python="$work/venv/bin/python"
if ! test -x "$python"; then
    python3 -m venv "$work/venv"
fi
"$python" -m pip install --disable-pip-version-check --timeout 30 -r configs/requirements.txt
export PYTHONPATH="$project/src"
"$python" -m legacy_tno.profile "$work/profile"
