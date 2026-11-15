#!/usr/bin/env python3
"""Choose a bounded second validation field using independently released DES orbits."""
import argparse
import json
from pathlib import Path

import numpy as np

from legacy_tno.geometry import night_id, sky, unit
from legacy_tno.orbit import Dynamics, observatory
from legacy_tno.pipeline import write_json
from legacy_tno.select import DES_EPOCH_TDB, des_orbits, eligible, evaluate_footprint, select_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    work = args.work
    original=json.loads((work/"inputs"/"selected-fields.json").read_text())
    designated=next(r for r in original["validation_ranking"] if r["target"]=="2013 TV158")
    source=np.load(work/"smoke"/"inventory.npy",mmap_mode="r",allow_pickle=False)
    search_field=dict(ra_deg=designated["ra_deg"],dec_deg=designated["dec_deg"],
                      mjd_min=designated["dates"][0]-.1,mjd_max=designated["dates"][1]+.1,
                      read_radius_deg=2,exclude_des=False)
    all_rows=eligible(select_rows(source,search_field))
    days=all_rows["mjd_obs"]+all_rows["exptime"]/(2*86400)
    dates,first,inverse=np.unique(days,return_index=True,return_inverse=True)
    k=str(work/"inputs"/"de440s.bsp")
    t,o=observatory(dates,k)
    model=Dynamics(min(t.min(),DES_EPOCH_TDB),max(t.max(),DES_EPOCH_TDB),k)
    name,state,mag=next(r for r in des_orbits(work/"inputs"/"des-y6-tno.fits") if r[0]==designated["target"])
    path=model.apparent(state,DES_EPOCH_TDB,t,o)
    inside=evaluate_footprint(all_rows,sky(path[inverse]),pad_px=-10)
    annotated=np.load(work/"smoke"/"annotated.npy",mmap_mode="r",allow_pickle=False)
    items=annotated[np.isin(annotated["expnum"],np.unique(all_rows["expnum"][inside]))]
    depth={(int(r["expnum"]),r["ccdname"].strip()):r["psfdepth"] for r in items}
    band_delta={"g":.65,"r":0,"i":-.3,"z":-.45}
    limiting=np.array([depth.get((int(r["expnum"]),r["ccdname"].strip()),np.nan)
                       for r in all_rows[inside]])
    mag_expected=mag+np.array([band_delta[str(b).strip()] for b in all_rows["filter"][inside]])
    deep=(limiting > (mag_expected+.30)) & (limiting<30)
    deep_index=np.unique(inverse[inside][deep])
    bands=np.char.strip(all_rows["filter"].astype(str))
    visits=bands[first]
    all_tracks=np.unique(inverse[inside])
    print(f"{name}: {len(all_tracks)} geometric and {len(deep_index)} depth-screened exposures",flush=True)
    nights=night_id(dates)
    ranked=[]
    band_groups=[("r","i","z"),("r","i"),("r","z"),("r",),("i",),("z",)]
    for use_bands in band_groups:
        candidate_ccds=all_rows[np.isin(bands,use_bands)]
        candidate_visits=deep_index[np.isin(visits[deep_index],use_bands)]
        for i in np.unique(nights[candidate_visits],return_index=True)[1]:
            j=candidate_visits[i]
            for width in (9,12,16,21,27,35):
                valid=candidate_visits[(dates[candidate_visits]>=dates[j]-.1)&
                                       (dates[candidate_visits]<=dates[j]+width)]
                if len(valid)<6 or len(np.unique(nights[valid]))<4 or np.ptp(dates[valid])<7:
                    continue
                ra,dec=map(float,sky(path[valid].mean(axis=0)))
                for radius,buffer in ((.84,.24),(.60,.21),(.45,.18),(.33,.16),(.25,.14)):
                    if np.max(np.linalg.norm(path[valid]-unit(ra,dec),axis=1)) > 2*np.sin(np.deg2rad(radius*.88)/2):
                        continue
                    field=dict(id="validation",ra_deg=ra,dec_deg=dec,core_radius_deg=radius,
                               read_radius_deg=radius+buffer,mjd_min=float(dates[valid].min()-.13),
                               mjd_max=float(dates[valid].max()+.11),exclude_des=False)
                    selected=select_rows(candidate_ccds,field)
                    if len(selected)<=950:
                        ranked.append(dict(field=field, exposure_count=len(valid), depth_nights=len(np.unique(nights[valid])),
                                           planned_ccds=len(selected),target=name,expected_mag_r=mag,
                                           bands=use_bands))
    ranked.sort(key=lambda r:(-min(r["depth_nights"],6),-min(r["exposure_count"],20),
                              -r["field"]["core_radius_deg"],r["planned_ccds"]))
    if not ranked:
        raise RuntimeError("No bounded deep comparison field")
    winner=ranked[0]
    rows=select_rows(all_rows[np.isin(bands,winner["bands"])],winner["field"])
    np.save(work/"inputs"/"deep-inventory.npy",rows,allow_pickle=False)
    output=dict(fields=[winner["field"]], ranking=ranked[:20])
    write_json(work/"inputs"/"selected-deep-validation.json",output)
    print(json.dumps(ranked[0],indent=2),flush=True)


if __name__=="__main__":
    main()
