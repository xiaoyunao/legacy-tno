#!/usr/bin/env bash
set -euo pipefail
jobs="$1"
case "$jobs" in (*[!0-9,]*|'') exit 2;; esac
ssh -o BatchMode=yes yunao@perlmutter.nersc.gov \
    "sacct -j '$jobs' -P -o JobID,JobName,Account,QOS,State,ExitCode,Submit,Start,End,Elapsed,TotalCPU,MaxRSS,ReqMem,AllocCPUS"
