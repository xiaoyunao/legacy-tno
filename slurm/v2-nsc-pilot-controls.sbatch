#!/bin/bash
#SBATCH --job-name=legacy-tno-v2-controls
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=30G
set -euo pipefail
cd "$1"
work="$2"
revision="$3"
main_run="$4"
phase="$5"
python="$work/smoke-venv/bin/python"
export PYTHONPATH="$PWD/src" LEGACY_TNO_WORKERS=4 LEGACY_TNO_LINK_WORKERS=10
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
if [[ "$phase" == injection ]]; then
    "$python" scripts/inject-nsc-pilot.py "$main_run" --work "$work" --output "$work/v2/pilot-injection.json"
else
    "$python" -m legacy_tno.cli run --work "$work" --config "configs/v2-nsc-pilot-$phase.json" \
        --fields configs/v2-nsc-pilot-field.json --field exploration --commit "$revision" \
        --resume --catalog-parent "$main_run"
fi
