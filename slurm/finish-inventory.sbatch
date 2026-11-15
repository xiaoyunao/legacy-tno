#!/bin/bash
#SBATCH --job-name=legacy-tno-inventory
#SBATCH --time=00:25:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=18G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$1"
export PYTHONPATH="$PWD/src"
work="$2"
gzip -dc /global/cfs/cdirs/cosmo/data/legacysurvey/dr11/ccds-annotated-decam-dr11.fits.gz > "$work/smoke/annotated-stage.fits"
"$work/smoke-venv/bin/python" -m legacy_tno.inventory "$work/smoke" "$3"
rm -- "$work/smoke/annotated-stage.fits"
