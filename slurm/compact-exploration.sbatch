#!/bin/bash
#SBATCH --job-name=legacy-tno-compact
#SBATCH --time=00:28:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=24G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
export LEGACY_TNO_LINK_WORKERS=10 LEGACY_TNO_WORKERS=12
cd "$1"
work="$2"
rev="$3"
export PYTHONPATH="$PWD/src"
python="$work/smoke-venv/bin/python"
for old in validation-c36e0a643fc984 validation-97d3348bc5c4b3; do
    if test -s "$work/runs/$old/blind_candidates.json"; then
        echo "Corrected DES identity for $old"
        "$python" scripts/reidentify-des.py "$work" "$old" --commit "$rev"
        "$python" scripts/aggregate-pilot.py "$work/runs/$old" --work "$work"
    fi
done
log="$work/compact-$SLURM_JOB_ID.log"
"$python" -m legacy_tno.cli run --work "$work" --field exploration --config configs/exploration-compact.json \
    --fields configs/exploration-compact-field.json --commit "$rev" --resume | tee "$log"
run=$(sed -n 's/^RUN_PATH=.*\///p' "$log" | head -1)
test -n "$run"
"$python" scripts/aggregate-pilot.py "$work/runs/$run" --work "$work"
