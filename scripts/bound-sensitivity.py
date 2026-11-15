#!/usr/bin/env python3
"""Compare anonymous short-arc fits with and without a solar escape-speed constraint."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from legacy_tno.geometry import angular_residual, unit
from legacy_tno.orbit import Dynamics, GM, heliocentric_elements
from legacy_tno.pipeline import write_json


def main():
    p=argparse.ArgumentParser()
    p.add_argument("work",type=Path)
    p.add_argument("run")
    p.add_argument("candidate")
    args=p.parse_args()
    out=args.work/"runs"/args.run
    rows=json.loads((out/"blind_candidates.json").read_text())
    candidate=next(r for r in rows if r["candidate_id"]==args.candidate)
    i=np.asarray(candidate["members"],dtype=int)
    with np.load(out/"classified.npz",allow_pickle=False) as data:
        detections=data["detections"][i]
        t,o=data["tdb"][i],data["observer"][i]
    epoch=candidate["epoch_tdb_mjd"]
    initial=np.asarray(candidate["state"],dtype=float)
    model=Dynamics(t.min(),t.max(),str(args.work/"inputs"/"de440s.bsp"))
    sun, speed=model.planets(epoch)[0], model.planets(epoch,1)[0]
    sigma=detections["sigma_arcsec"][:,None]
    direction=unit(detections["ra_deg"],detections["dec_deg"])
    vel=initial[3:]-speed
    nominal_v=np.linalg.norm(vel)

    def return_state(x):
        r=x[:3]-sun
        escape=np.sqrt(2*GM["sun"]/np.linalg.norm(r))
        u=x[3:]
        scaled=u/np.sqrt(1+np.dot(u,u))
        return np.r_[x[:3], speed+escape*scaled]

    def residual(x):
        coords=model.apparent(return_state(x),epoch,t,o)
        return (angular_residual(coords,direction)/sigma).ravel()

    trials=[]
    for initial_ratio in (.2,.5,.85):
        start=np.r_[initial[:3], (initial_ratio/np.sqrt(1-initial_ratio**2))*(vel/nominal_v)]
        result=least_squares(residual,start,diff_step=2e-6,max_nfev=80,xtol=2e-8,ftol=1e-8)
        adjusted=return_state(result.x)
        offsets=result.fun.reshape(-1,2)*sigma
        trials.append(dict(converged=result.success, initial_ratio=initial_ratio,
                           rms_arcsec=np.sqrt(np.mean(offsets**2)), chi2=np.sum(result.fun**2),
                           state=adjusted, elements=heliocentric_elements(model,adjusted,epoch)))
    best=min(trials,key=lambda r:r["chi2"])
    summary=dict(candidate_id=args.candidate,run_id=args.run, n_observations=len(i),
                 n_nights=len(np.unique(detections["night"])), epoch_tdb_mjd=epoch,
                 nominal_chi2=candidate["chi2"], nominal_rms_arcsec=candidate["rms_arcsec"],
                 nominal_elements=candidate["elements"], bound_trials=trials, best_bound=best,
                 delta_chi2=best["chi2"]-candidate["chi2"],
                 note="Constrained fit sensitivity, conditional on the same blind measurements")
    write_json(out/"bound_fit_sensitivity.json",summary)
    print(f"{args.run} {args.candidate}: nominal RMS {candidate['rms_arcsec']:.3f}, bound RMS {best['rms_arcsec']:.3f} arcsec")


if __name__=="__main__":
    main()
