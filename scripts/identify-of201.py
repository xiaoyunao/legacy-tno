#!/usr/bin/env python3
"""Post-search identification of the optional four-night validation target."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from legacy_tno.geometry import night_id, sky
from legacy_tno.link import search
from legacy_tno.orbit import Dynamics, observatory
from legacy_tno.pipeline import write_json
from legacy_tno.plot import plot
from legacy_tno.select import evaluate_footprint
from legacy_tno.validate import leave_night_out, matches


def main():
    p=argparse.ArgumentParser()
    p.add_argument("work",type=Path)
    p.add_argument("run")
    args=p.parse_args()
    out=args.work/"runs"/args.run
    manifest=json.loads((out/"run_manifest.json").read_text())
    config,field=manifest["config"],manifest["field"]
    if not (out/"blind_candidates.json").exists():
        raise RuntimeError("Blind processing must finish before loading the truth orbit")
    blind=json.loads((out/"blind_candidates.json").read_text())
    recovered=json.loads((out/"candidate_summary.json").read_text())
    truth=json.loads((args.work/"inputs"/"of201-state.json").read_text())["result"]
    text=truth.split("$$SOE")[1].split("$$EOE")[0].strip()
    data=next(csv.reader([text]))
    epoch=float(data[0])-2400000.5
    state=np.asarray(data[2:8],dtype=float)
    with np.load(out/"classified.npz",allow_pickle=False) as npz:
        table,reasons,t,o=(npz[k] for k in ("detections","reasons","tdb","observer"))
    exposures=np.load(out/"exposures.npy",allow_pickle=False)
    qc=json.loads((out/"ccd_audit.json").read_text())
    use={(r["expnum"],r["ccdname"]) for r in qc if "astrometry" in r and "exclusion" not in r["astrometry"]}
    exposures=exposures[[(int(r["expnum"]),str(r["ccdname"]).strip()) in use for r in exposures]]
    utc=exposures["mjd_obs"]+exposures["exptime"]/(2*86400)
    dates,first,index=np.unique(utc,return_index=True,return_inverse=True)
    kernel=str(args.work/"inputs"/"de440s.bsp")
    tt,oo=observatory(dates,kernel)
    model=Dynamics(min(t.min(),epoch),max(t.max(),epoch),kernel)
    expected=model.apparent(state,epoch,tt,oo)
    in_footprint=evaluate_footprint(exposures,sky(expected[index]),pad_px=-8)
    valid=np.unique(index[in_footprint])
    exp=exposures["expnum"][first[valid]]
    raw=np.load(out/"raw.npy",mmap_mode="r",allow_pickle=False)
    B=matches(raw,expected[valid],exp,2.25)
    calibrated=matches(table,expected[valid],exp,1.25)
    clean=calibrated[reasons[calibrated]=="transient_clean"]
    linked=search(table[clean],t[clean],o[clean],field,config["link"])
    known=set(calibrated)
    matches_pure=[]
    plot_members=json.loads((out/"blind_known_plot_data.json").read_text())
    summary={row["candidate_id"]:row for row in recovered}
    for result in blind:
        members=np.asarray(result["members"],dtype=int)
        overlap=len(known.intersection(members))
        if overlap!=len(members) or overlap<4:
            continue
        result["members"]=members
        result["initial_state"]=np.asarray(result["initial_state"])
        holds=leave_night_out(result,table,t,o,model)
        matches_pure.append(result["candidate_id"])
        candidate=summary[result["candidate_id"]]
        candidate.update(status="known_recovered_blind", catalog_association="2017 OF201",
                         identity_reference="Horizons SSB ICRF vector", matched_detections=overlap,
                         matched_nights=len(np.unique(table["night"][members])),held_nights=holds)
        pr,pd=sky(np.asarray(result["fitted_directions"]))
        plot_members.append(dict(candidate_id=result["candidate_id"],target="2017 OF201",mjd_tdb=t[members],
            ra_deg=table["ra_deg"][members],dec_deg=table["dec_deg"][members],predicted_ra=pr,predicted_dec=pd,
            magnitude=table["mag_ab"][members],band=table["band"][members],mag_err=table["mag_err"][members],
            sigma_arcsec=table["sigma_arcsec"][members],offsets_arcsec=result["offsets_arcsec"],held_nights=holds))
    write_json(out/"candidate_summary.json",recovered)
    write_json(out/"blind_known_plot_data.json",plot_members)
    write_json(out/"stress_recovery_summary.json",dict(target="2017 OF201",reference="JPL Horizons vector",
        A_geometry_exposures=len(valid),A_geometry_nights=len(np.unique(night_id(dates[valid]))),
        B_raw_detections=len(B),C_clean_detections=len(clean),C_calibrated_detections=len(calibrated),
        D_linkable=bool(linked.chains),E_blind=bool(matches_pure),pure_chains=matches_pure,
        E_geometry_caveat="TAN footprints tested, pixel completeness unmeasured"))
    print(f"OF201: {len(valid)} geometric, {len(B)} raw, {len(clean)} clean, {len(matches_pure)} pure blind chains")
    if matches_pure:
        plot(out)


if __name__=="__main__":
    main()
