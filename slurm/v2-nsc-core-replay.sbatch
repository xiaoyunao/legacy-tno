#!/bin/bash
#SBATCH --job-name=legacy-tno-v2-core
#SBATCH --time=00:25:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=10
#SBATCH --mem=20G
set -euo pipefail
cd "$1"
work="$2"
revision="$3"
export PYTHONPATH="$PWD/src" LEGACY_TNO_LINK_WORKERS=8
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
python="$work/smoke-venv/bin/python"
"$python" -m legacy_tno.cli run --work "$work" --config configs/v2-nsc-pilot-clean-core.json \
    --fields configs/v2-nsc-pilot-field.json --field exploration --commit "$revision" \
    --resume --catalog-parent "$work/runs/exploration-b49f1211213970"
"$python" -m legacy_tno.cli run --work "$work" --config configs/v2-nsc-pilot-ambiguity-core.json \
    --fields configs/v2-nsc-pilot-field.json --field exploration --commit "$revision" \
    --resume --catalog-parent "$work/runs/exploration-b49f1211213970"
"$python" -m legacy_tno.cli run --work "$work" --config configs/v2-nsc-of201-core.json \
    --fields configs/v2-nsc-of201-field.json --field validation --commit "$revision" \
    --resume --catalog-parent "$work/runs/validation-ef4655b225ac2a"
