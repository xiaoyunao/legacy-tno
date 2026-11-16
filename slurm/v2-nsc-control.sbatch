#!/bin/bash
#SBATCH --job-name=legacy-tno-v2-nsc
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=30G
set -euo pipefail
cd "$1"
work="$2"
control="$3"
revision="$4"
log="$5"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
export PYTHONPATH="$PWD/src" LEGACY_TNO_WORKERS=4 LEGACY_TNO_LINK_WORKERS=10
python="$work/smoke-venv/bin/python"
"$python" -m legacy_tno.cli run --work "$work" --config "configs/v2-nsc-$control.json" \
    --fields "configs/v2-nsc-$control-field.json" --field validation --commit "$revision" --resume
if [[ "$control" == of201 ]]; then
    run=$(sed -n 's/^RUN_PATH=.*\///p' "$log" | head -1)
    test -n "$run"
    "$python" scripts/identify-of201.py "$work" "$run"
fi
