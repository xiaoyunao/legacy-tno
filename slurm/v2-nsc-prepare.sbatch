#!/bin/bash
#SBATCH --job-name=legacy-tno-v2-prep
#SBATCH --time=00:20:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=18G
set -euo pipefail
cd "$1"
work="$2"
inventory="$3"
sample="$4"
control="$5"
shift 5
export PYTHONPATH="$PWD/src"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
python="$work/smoke-venv/bin/python"
fetched="$work/v2/$sample-nsc-fetch.json"
"$python" scripts/fetch-nsc-field.py "$inventory" "$sample" --output "$fetched"
"$python" scripts/prepare-nsc-field.py "$inventory" "$fetched" \
    --image-root /global/cfs/cdirs/cosmo/staging --config configs/deep.json \
    --output "$work/v2/prepared-$control" --workers "$SLURM_CPUS_PER_TASK" "$@"
