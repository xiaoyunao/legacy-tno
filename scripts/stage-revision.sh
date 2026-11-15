#!/usr/bin/env bash
set -euo pipefail
host="${1:-yunao@perlmutter.nersc.gov}"
rev="$(git rev-parse "${2:-HEAD}^{commit}")"
git archive "$rev" src configs slurm scripts pyproject.toml |
  ssh -o BatchMode=yes "$host" "set -eu; umask 077; d=\"\$HOME/projects/legacy-tno/revisions/$rev\"; mkdir -p \"\$d\"; cd \"\$d\"; tar -xf -; pwd"
