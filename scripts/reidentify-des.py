#!/usr/bin/env python3
"""Refresh only the post-blind DES identity comparison using an audited epoch."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import numpy as np

from legacy_tno.orbit import Dynamics
from legacy_tno.pipeline import write_json
from legacy_tno.plot import plot
from legacy_tno.select import DES_EPOCH_TDB
from legacy_tno.validate import write_identity


def main():
    p=argparse.ArgumentParser()
    p.add_argument("work",type=Path)
    p.add_argument("run")
    p.add_argument("--commit",required=True)
    args=p.parse_args()
    out=args.work/"runs"/args.run
    m=json.loads((out/"run_manifest.json").read_text())
    inputs=args.work/"inputs"
    raw=json.loads((out/"blind_candidates.json").read_text())
    with np.load(out/"classified.npz",allow_pickle=False) as fields:
        table,reasons,t,o=(fields[key] for key in ("detections","reasons","tdb","observer"))
    rows=np.load(out/"exposures.npy",allow_pickle=False)
    qc=json.loads((out/"astrometry_photometry_qc.json").read_text())
    usable={(v["expnum"],v["ccdname"]) for v in qc if "astrometry" in v and "exclusion" not in v["astrometry"]}
    exposures=rows[[(int(r["expnum"]),str(r["ccdname"]).strip()) in usable for r in rows]]
    orbit= Dynamics(t.min(), t.max(), str(inputs/"de440s.bsp"))
    for row in raw:
        for key in ("members","state","initial_state","fitted_directions"):
            row[key]=np.asarray(row[key])
    for file in ("candidate_summary.json","known_recovery_summary.json","blind_known_plot_data.json"):
        prior=out/"identity-v1"
        prior.mkdir(exist_ok=True)
        if (out/file).exists() and not (prior/file).exists():
            shutil.copy2(out/file,prior/file)
    write_identity(out,args.work,exposures,table,reasons,t,o,m["field"],m["config"],orbit,raw)
    plot(out)
    write_json(out/"identity_revision.json",dict(des_epoch_tdb_mjd=DES_EPOCH_TDB, identity_code_commit=args.commit,
                updated_utc=datetime.now(timezone.utc).isoformat(), original_identity="identity-v1/",
                blind_candidate_path="blind_candidates.json"))
    counts=json.loads((out/"known_recovery_summary.json").read_text())["counts"]
    print(f"Updated DES identity for {args.run}: {counts}",flush=True)


if __name__=="__main__":
    main()
