#!/usr/bin/env bash
set -euo pipefail
host="${1:-yunao@perlmutter.nersc.gov}"
revision="${2:-HEAD}"
git archive "$revision" src configs slurm scripts pyproject.toml |
  ssh -o BatchMode=yes "$host" 'set -eu; cd "$HOME/projects/legacy-tno"; tar -xf -'
