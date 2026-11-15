#!/usr/bin/env python3
"""Download only enumerated regular files smaller than the transfer budget."""
import argparse
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess

TABLES = (
    "run_manifest.json", "exposure_summary.json", "astrometry_photometry_qc.json",
    "static_filter_summary.json", "search_domain_summary.json",
    "known_recovery_summary.json", "candidate_summary.json", "blind_known_plot_data.json",
    "null_test_summary.json", "injection_recovery_summary.json",
    "stage_counts.json", "performance_summary.json", "plot_data.json",
    "known_miss_diagnostic.json", "stress_recovery_summary.json", "identity_revision.json", "candidate_review.json", "bound_fit_sensitivity.json",
)
AUDIT = ("catalog_audit.json", "inventory_summary.json", "smoke_catalogs.json", "selected-fields.json", "anonymous_orbit_benchmark.json", "selected-deep-validation.json")
FIGURES = ("coverage_nights", "cadence", "catalog_diagnostics", "gaia_residuals",
           "static_classification", "known_recovery", "injection_and_null",
           "candidates_and_association", "coverage_depth_seasons", "catalog_depth")
FILE_BUDGET = 4*1024**2
TOTAL_BUDGET = 32*1024**2


def permitted_file(path):
    p = PurePosixPath(path)
    if len(p.parts)==1:
        return p.name in TABLES or p.name in AUDIT
    if len(p.parts)!=2 or p.parts[0]!="figures" or p.suffix not in (".png",".pdf"):
        return False
    return p.stem in FIGURES or re.fullmatch(r"(known_(track|residuals)|candidate_stamps)_C\d{4}",p.stem) is not None


def run():
    parser=argparse.ArgumentParser()
    parser.add_argument("--host",default="yunao@perlmutter.nersc.gov")
    parser.add_argument("--remote",required=True)
    parser.add_argument("--target",type=Path,required=True)
    args=parser.parse_args()
    root=PurePosixPath(args.remote)
    if ".." in root.parts or not re.fullmatch(r"/pscratch/sd/y/yunao/legacy-tno/(?:smoke|inputs|runs/[a-z]+-[0-9a-f]{14})",
                                               str(root)):
        parser.error("Remote directory must be a specific approved Legacy TNO work directory")
    script=r'''set -eu
root="$1"
test -d "$root" && test ! -L "$root" || exit 2
test "$(realpath -e "$root")" = "$root" || exit 2
for file in "$root"/*.json "$root"/figures/*.png "$root"/figures/*.pdf; do
    test -f "$file" && test ! -L "$file" || continue
    if test "$(realpath -e "$file")" = "$file"; then
        printf '%s\t%s\n' "$(stat -c %s "$file")" "${file#"$root"/}"
    fi
done'''
    cmd="bash -s -- "+shlex.quote(str(root))
    listing=subprocess.run(["ssh","-o","BatchMode=yes",args.host,cmd],
                           input=script,text=True,stdout=subprocess.PIPE,check=True).stdout
    files=[]
    for line in listing.splitlines():
        size, name=line.split("\t",1)
        if permitted_file(name) and int(size)<=FILE_BUDGET:
            files.append((name,int(size)))
    total=sum(size for _,size in files)
    if total>TOTAL_BUDGET:
        raise SystemExit(f"Allowed results require {total:,} bytes, above transfer limit")
    args.target.mkdir(parents=True,exist_ok=True)
    print("\n".join(f"{size:>10,} {name}" for name,size in files),flush=True)
    print(f"{len(files)} whitelisted files, {total:,} bytes",flush=True)
    if not files:
        return
    subprocess.run(["rsync","-az","--files-from=-","-e","ssh -o BatchMode=yes",
                    f"{args.host}:{root}/",str(args.target)+"/"],
                   input="".join(name+"\n" for name,_ in files),text=True,check=True)


if __name__=="__main__":
    run()
