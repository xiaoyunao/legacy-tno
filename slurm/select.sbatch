#!/bin/bash
#SBATCH --job-name=legacy-tno-select
#SBATCH --time=00:20:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=54G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$1"
work="$2"
export PYTHONPATH="$PWD/src"
python="$work/smoke-venv/bin/python"
"$python" -m pip install --disable-pip-version-check --timeout 20 -r configs/requirements.txt
"$python" - "$work" configs/pilot.json <<'PY'
import json
import sys
from pathlib import Path
from legacy_tno.select import choose
work, config = map(Path, sys.argv[1:])
out = work / "inputs" / "selected-fields.json"
result = choose(work, json.loads(config.read_text()))
out.write_text(json.dumps(result, indent=2, default=int) + "\n")
print(json.dumps(result["fields"], indent=2))
if len(result["fields"]) != 2:
    print("Selection did not yield both requested field types")
PY
