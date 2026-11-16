#!/bin/bash
#SBATCH --job-name=legacy-tno-v2-review
#SBATCH --time=00:20:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --mem=24G
set -euo pipefail
cd "$1"
work="$2"
vendor="$3"
export PYTHONPATH="$PWD/src"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
python="$work/smoke-venv/bin/python"
catalog="$work/v2/mpcorb"
"$python" scripts/diagnose-nsc-epochs.py "$work/runs/validation-fdd2c34bae73f8" \
    --output "$work/v2/nsc-horizons-original-misses.json" --targets "2013 RD124" "2013 RQ157"
"$python" scripts/review-candidates.py "$work" validation-ef4655b225ac2a --all
"$python" scripts/review-candidates.py "$work" validation-7185aa85687161 --candidate C0004
make -C "$vendor" -j "$SLURM_CPUS_PER_TASK" astcheck mpc2sof
if [[ ! -s "$catalog/orbit-count.txt" ]]; then
    (
        cd "$catalog"
        gzip -dc MPCORB.DAT.gz > MPCORB.DAT
        "$vendor/mpc2sof" MPCORB.DAT i
        wc -l < mpcorb.sof | awk '{print $1 - 1}' > orbit-count.txt
    )
fi
for run in validation-2757671f191346 validation-ef4655b225ac2a; do
    "$python" scripts/match-mpcorb.py "$work/runs/$run" --astcheck "$vendor/astcheck" \
        --catalog "$catalog" --output "$work/v2/mpcorb-$run.json"
done
