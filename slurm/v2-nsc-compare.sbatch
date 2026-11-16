#!/bin/bash
#SBATCH --job-name=legacy-tno-v2-compare
#SBATCH --time=00:12:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=18G
set -euo pipefail
cd "$1"
work="$2"
upstream="$3"
export PYTHONPATH="$PWD/src"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
python="$work/smoke-venv/bin/python"
v2="$work/v2"
"$python" scripts/verify-legacypipe-sefn.py "$upstream" \
    "$v2/legacy_se_fields.json" "$v2/pilot-legacy-ledger.json" --output "$v2/legacy_se_upstream_verified.json"
"$python" scripts/compare-nsc-sep.py "$work" --ccds-per-control 99 > "$v2/nsc-sep-extended.tmp"
mv "$v2/nsc-sep-extended.tmp" "$v2/nsc-sep-extended.json"
