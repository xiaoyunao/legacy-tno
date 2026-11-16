#!/bin/bash
#SBATCH --job-name=legacy-tno-v2-delta
#SBATCH --time=00:20:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=10
#SBATCH --mem=24G
set -euo pipefail
cd "$1"
work="$2"
revision="$3"
export PYTHONPATH="$PWD/src" LEGACY_TNO_LINK_WORKERS=8
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
python="$work/smoke-venv/bin/python"
of201=validation-ef4655b225ac2a
catalog="$work/v2/mpcorb"
astcheck="$HOME/projects/legacy-tno/vendor-lunar/astcheck"

review_new() {
    local base="$1" replay="$2" report="$work/v2/candidate-delta-$2.json" names
    names=$("$python" scripts/compare-candidate-memberships.py "$work/runs/$base" "$work/runs/$replay" --output "$report")
    if [[ -n "$names" ]]; then
        local options=()
        while IFS= read -r name; do options+=(--candidate "$name"); done <<< "$names"
        "$python" scripts/review-candidates.py "$work" "$replay" "${options[@]}"
        "$python" scripts/match-mpcorb.py "$work/runs/$replay" --astcheck "$astcheck" \
            --catalog "$catalog" --output "$work/v2/mpcorb-$replay.json"
    fi
}
review_new exploration-74d5a152a0336a exploration-4cbf95aec89763
review_new "$of201" validation-2b067401f24cc8
narrow_log="$work/v2/nsc-of201-narrow-$SLURM_JOB_ID.log"
"$python" -m legacy_tno.cli run --work "$work" --config configs/v2-nsc-of201-narrow.json \
    --fields configs/v2-nsc-of201-field.json --field validation --commit "$revision" \
    --resume --catalog-parent "$work/runs/$of201" | tee "$narrow_log"
narrow=$(sed -n 's|^RUN_PATH=.*/||p' "$narrow_log")
[[ -n "$narrow" ]]
review_new "$of201" "$narrow"
