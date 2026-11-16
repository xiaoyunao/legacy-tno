#!/bin/bash
#SBATCH --job-name=legacy-tno-v2-pilot
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=24G
set -euo pipefail
cd "$1"
work="$2"
revision="$3"
sample=pilot-38-10
fields=configs/v2-nsc-pilot-field.json
python="$work/smoke-venv/bin/python"
export PYTHONPATH="$PWD/src" LEGACY_TNO_WORKERS=4 LEGACY_TNO_LINK_WORKERS=10
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
mkdir -p "$work/v2/$sample"
if [[ ! -f "$work/v2/prepared-pilot/manifest.json" ]]; then
    "$python" - "$work" "$sample" "$fields" <<'PY'
import json
from pathlib import Path
import sys

import numpy as np

from legacy_tno.select import eligible, select_rows

work, sample, field_file = sys.argv[1:]
work = Path(work)
[field] = json.loads(Path(field_file).read_text())["fields"]
inventory = np.load(work/"smoke/inventory.npy", mmap_mode="r", allow_pickle=False)
rows = eligible(select_rows(inventory, field))
if not len(rows):
    raise ValueError("Frozen pilot contains no eligible Legacy observations")
np.save(work/"v2"/sample/"exposures.npy", rows, allow_pickle=False)
PY
    root=/global/cfs/cdirs/cosmo
    "$python" scripts/audit-legacy-se.py "$work/v2/$sample/exposures.npy" --image-root "$root/staging" \
        --survey-root "$root/data/legacysurvey/dr11" --survey-root "$root/work/legacysurvey/dr11" \
        --output "$work/v2/pilot-legacy-ledger.json"
    "$python" scripts/inventory-nsc.py "$work/v2/pilot-legacy-ledger.json" "$work/v2/pilot-nsc-inventory.json"
    "$python" scripts/match-nsc-ccds.py "$work/v2/pilot-legacy-ledger.json" "$work/v2/pilot-nsc-inventory.json" \
        --image-root "$root/staging" --output "$work/v2/pilot-nsc-ccds.json"
    bash slurm/v2-nsc-prepare.sbatch "$PWD" "$work" "$work/v2/pilot-nsc-ccds.json" "$sample" pilot --fields "$fields"
fi
"$python" -m legacy_tno.cli run --work "$work" --config configs/v2-nsc-pilot.json \
    --fields "$fields" --field exploration --commit "$revision" --resume
