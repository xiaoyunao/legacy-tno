#!/bin/bash
#SBATCH --job-name=legacy-tno-replay
#SBATCH --time=00:26:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=18G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
export LEGACY_TNO_LINK_WORKERS=10 LEGACY_TNO_WORKERS=12
cd "$1"
work="$2"
field="$3"
parent="$4"
config="$5"
fields="$6"
commit="$7"
post="${8:-aggregate}"
export PYTHONPATH="$PWD/src"
python="$work/smoke-venv/bin/python"
log="$work/replay-$SLURM_JOB_ID.log"
"$python" -m legacy_tno.cli run --work "$work" --field "$field" --catalog-parent "$parent" \
   --config "$config" --fields "$fields" --commit "$commit" --resume | tee "$log"
run=$(sed -n 's/^RUN_PATH=.*\///p' "$log" | head -1)
test -n "$run"
if test "$post" = of201; then
    "$python" scripts/identify-of201.py "$work" "$run"
fi
"$python" scripts/aggregate-pilot.py "$work/runs/$run" --work "$work"
