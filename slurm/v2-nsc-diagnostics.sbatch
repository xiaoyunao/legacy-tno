#!/bin/bash
#SBATCH --job-name=legacy-tno-v2-diagnostics
#SBATCH --time=00:25:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=10
#SBATCH --mem=18G
set -euo pipefail
cd "$1"
work="$2"
revision="$3"
export PYTHONPATH="$PWD/src" LEGACY_TNO_LINK_WORKERS=8
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
python="$work/smoke-venv/bin/python"
v2="$work/v2"
"$python" scripts/compare-nsc-sep.py "$work" --ccds-per-control 99 > "$v2/nsc-sep-by-magnitude.tmp"
mv "$v2/nsc-sep-by-magnitude.tmp" "$v2/nsc-sep-by-magnitude.json"
"$python" scripts/summarize-nsc-coverage.py "$work" \
    --summary "$v2/nsc-coverage-public.json" --ledger "$v2/nsc-coverage-ledger.json"
"$python" scripts/profile-frozen-search.py "$work" exploration-b49f1211213970 \
    validation-ef4655b225ac2a --revision "$revision" --output "$v2/nsc-link-bin-profiles.json" \
    --of201-track-figure "$v2/nsc-of201-candidate-tracks.png"
