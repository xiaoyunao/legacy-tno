#!/usr/bin/env python3
"""Refit one completed control's astrometry independently with local Find_Orb."""
import argparse
from hashlib import file_digest
import json
from pathlib import Path
import subprocess

from legacy_tno.mpc import export_mpc
from legacy_tno.pipeline import write_json


def digest(path):
    with path.open("rb") as handle:
        return file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plot_data", type=Path)
    parser.add_argument("target")
    parser.add_argument("--fo", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--de440", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    [track] = [r for r in json.loads(args.plot_data.read_text()) if r["target"] == args.target]
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    obs = work/"anonymous.mpc"
    obs.write_text(export_mpc(track, "LTNO001"))
    result_file = work/"total.json"
    if result_file.exists():
        result_file.unlink()
    command = [str(args.fo.resolve()), str(obs), "-x", str(args.config_dir.resolve())+"/",
               "-O", str(work)+"/", "-C", "W84", "-i", "EPHEM_STEPS=0",
               f"LINUX_JPL_FILENAME={args.de440.resolve()}"]
    with (work/"find-orb.log").open("w") as handle:
        subprocess.run(command, cwd=work, stdout=handle, stderr=subprocess.STDOUT,
                       stdin=subprocess.DEVNULL, check=True)
    log = (work/"find-orb.log").read_text()
    if "don't currently have JPL planetary ephemerides set up" in log:
        raise ValueError("Find_Orb did not read the requested JPL ephemeris")
    [result] = json.loads(result_file.read_text())["objects"].values()
    source = args.plot_data.parent/"run_manifest.json"
    run_id = json.loads(source.read_text())["run_id"] if source.is_file() else None
    summary = dict(target=args.target, run_id=run_id, candidate_id=track["candidate_id"],
                   input_sha256=digest(obs), find_orb_version=result["Find_Orb_version_iso"],
                   ephemeris="JPL DE440 Linux binary", ephemeris_sha256=digest(args.de440),
                   count=result["observations"]["count"], used=result["observations"]["used"],
                   fit_elements=result["elements"],
                   weighting="Find_Orb defaults; MPC 80-column observations do not convey per-source errors",
                   time="UTC reception at W84, rounded to 1e-6 day",
                   astrometry="ICRS RA to 0.001 h-second and Dec to 0.01 arcsec",
                   identity_supplied_to_fitter=False)
    write_json(args.output, summary)


if __name__ == "__main__":
    main()
