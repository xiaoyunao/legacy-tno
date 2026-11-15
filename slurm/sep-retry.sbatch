#!/bin/bash
#SBATCH --job-name=legacy-tno-sep
#SBATCH --time=00:15:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=24G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1 LEGACY_TNO_WORKERS=12
cd "$1"
w="$2"
shift 2
export PYTHONPATH="$PWD/src"
echo "SEP pixel stack capacity 1800000 active pixels; all detection thresholds unchanged"
"$w/smoke-venv/bin/python" -c 'import sep; sep.set_extract_pixstack(1800000); from legacy_tno.cli import main; main()' run --work "$w" "$@"
