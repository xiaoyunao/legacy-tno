#!/usr/bin/env python3
"""Fit independently published astrometry anonymously, with whole-night holdouts."""
import argparse
import json
from pathlib import Path

import numpy as np
from astropy.time import Time

from legacy_tno.geometry import angular_residual, basis, night_id, project, unit
from legacy_tno.link import initial_linear
from legacy_tno.orbit import Dynamics, GM, fit, heliocentric_elements, observatory
from legacy_tno.pipeline import write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    work = args.work
    data = np.genfromtxt(work/"inputs"/"published-decam-w84.csv", delimiter=",", names=True,
                         dtype=None, encoding="ascii")
    utc = Time(data["utc"], format="isot", scale="utc").mjd
    direction = unit(data["ra_deg"], data["dec_deg"])
    sigma = np.hypot(data["sigma_ra"], data["sigma_dec"])/np.sqrt(2)
    kernel = str(work/"inputs"/"de440s.bsp")
    t, o = observatory(utc,kernel)
    model = Dynamics(t.min(),t.max(),kernel)
    axes = basis(np.mean(data["ra_deg"]),np.mean(data["dec_deg"]))
    epoch = float(np.mean(t))
    solutions = []
    for lo, hi in [(30,65),(60,110),(100,180),(160,300)]:
        plane = initial_linear(project(direction,axes), o@axes.T, t-epoch, (lo,hi),
                                np.sqrt(2*GM["sun"]/lo), sigma)
        initial = np.r_[plane[:3]@axes,plane[3:]@axes]
        solution = fit(model,initial,epoch,t,o,direction,sigma)
        solutions.append((solution,initial))
    result, initial = min(solutions,key=lambda pair:pair[0].chi2)
    held = []
    for night in np.unique(night_id(utc)):
        take = night_id(utc)!=night
        refit = fit(model,initial,epoch,t[take],o[take],direction[take],sigma[take])
        predicted = model.apparent(refit.state,epoch,t[~take],o[~take])
        residual = angular_residual(predicted,direction[~take])
        held.append(dict(night=night,n_points=len(residual),rms_arcsec=np.sqrt(np.mean(residual**2)),
                         success=refit.convergence))
    output = dict(source="Cheng, Li & Yang, arXiv:2505.15806v2, Table 2 DECam (W84)",
                  proof="published astrometry selected externally, not a blind catalog recovery",
                  n_observations=len(t), n_nights=len(held), n_days=np.ptp(t),
                  rms_arcsec=result.rms, chi2=result.chi2, dof=result.dof, success=result.convergence,
                  returned_chi2=[r.chi2 for r,_ in solutions], reduced_chi2=result.reduced_chi2(),
                  epoch_tdb_mjd=epoch, heliocentric=heliocentric_elements(model,result.state,epoch),
                  rms_arcsec_held_night=np.sqrt(np.mean([h["rms_arcsec"]**2 for h in held])),
                  held_nights=held, utc_start=float(min(utc)), utc_end=float(max(utc)))
    cached=work/"inputs"/"horizons-of201.json"
    if cached.exists():
        ephemeris=json.loads(cached.read_text())
        horizons=np.array(ephemeris["jd_ra_dec"])
        search_times=utc[np.argsort(utc)]+2400000.5
        if not np.allclose(np.sort(horizons[:,0]),search_times,rtol=0,atol=1e-7):
            raise ValueError("Horizons Julian dates disagree with observing epochs")
        order=np.argsort(utc)
        rows=horizons[np.argsort(horizons[:,0])]
        controlled=model.apparent(result.state,result.epoch,t[order],o[order])
        offsets=angular_residual(controlled, unit(rows[:,1],rows[:,2]))
        output["horizons"]=dict(max_separation_arcsec=np.max(np.linalg.norm(offsets,axis=1)),
                                rms_arcsec=np.sqrt(np.mean(offsets**2)),
                                api=ephemeris["api_signature"], retrieved_utc=ephemeris["retrieved_utc"],
                                center="W84", product="astrometric ICRF RA/Dec")
    write_json(work/"smoke"/"anonymous_orbit_benchmark.json",output)
    print(f"Anonymous IOD benchmark: {len(t)} W84 observations, RMS {result.rms:.3f} arcsec", flush=True)
    if not result.convergence or result.reduced_chi2() > 5:
        raise SystemExit("Anonymous fit did not meet benchmark convergence / residual criterion")


if __name__=="__main__":
    main()
