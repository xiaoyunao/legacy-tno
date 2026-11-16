#!/usr/bin/env python3
"""Inject low-density, distance/magnitude-stratified trajectories in a frozen NSC pilot."""
import argparse
import json
from pathlib import Path

import numpy as np

from legacy_tno.geometry import ARCSEC, basis, night_id, sky, unit
from legacy_tno.link import search
from legacy_tno.nsc_adapter import PRODUCT
from legacy_tno.orbit import Dynamics, LIGHT_SPEED, observatory
from legacy_tno.pipeline import fit_chains, write_json
from legacy_tno.select import evaluate_footprint, possible_arc
from legacy_tno.static import classify, gaia_field, link_mask, sweep_field
from legacy_tno.validate import kepler_generator, time_map

DISTANCES = ((30, 60), (60, 120), (120, 300))
MAGNITUDES = ((20, 21.8), (21.8, 23.2))
REPLICATES = 2
BATCH_SIZE = 2


def inject(rows, raw, config, field, kernel, seed):
    rng = np.random.default_rng(seed)
    utc = rows["mjd_obs"]+rows["exptime"]/(2*86400)
    dates, index = np.unique(utc, return_inverse=True)
    tdb, observers = observatory(dates, kernel)
    model = Dynamics(tdb.min(), tdb.max(), kernel)
    axes = basis(field["ra_deg"], field["dec_deg"])
    sun = model.planets(tdb)[:, 0]
    ref = observers[0]-sun[0]
    lamp = {}
    for row in rows:
        key = row["expnum"], row["ccdname"]
        lamp[key] = raw[(raw["expnum"] == key[0]) & (raw["ccdname"] == key[1])]
    all_injected, cells = [], []
    for lo, hi in DISTANCES:
        for low, high in MAGNITUDES:
            count = 0
            attempts = 0
            while count < REPLICATES and attempts < 250:
                attempts += 1
                distance = np.exp(rng.uniform(np.log(lo), np.log(hi)))
                mag = rng.uniform(low, high)
                offset = np.deg2rad(rng.uniform(-.6,.6,2)*field["core_radius_deg"])
                sight = axes[2]+offset @ axes[:2]
                sight /= np.linalg.norm(sight)
                delta = sight @ ref
                depth = np.sqrt(delta**2 + distance**2-ref@ref)-delta
                position = ref+sight*depth
                p = position/distance
                angle = rng.uniform(0, 2*np.pi)
                tangent = np.cos(angle)*axes[0] + np.sin(angle)*axes[1]
                tangent -= p*np.dot(tangent,p)
                tangent /= np.linalg.norm(tangent)
                ecc = rng.uniform(0,.85)
                propagate = kepler_generator(position, tangent, ecc,
                                             rng.uniform(-np.pi,np.pi), tdb[0]-depth/LIGHT_SPEED)
                emit = tdb-depth/LIGHT_SPEED
                for _ in range(3):
                    projected = propagate(emit)+sun-observers
                    length = np.linalg.norm(projected, axis=1)
                    emit = tdb-length/LIGHT_SPEED
                directions = projected/length[:, None]
                ra, dec = sky(directions[index])
                locations = np.flatnonzero(evaluate_footprint(rows, (ra, dec), pad_px=-20))
                _, first = np.unique(index[locations], return_index=True)
                selected = locations[first]
                exposure = index[selected]
                nights = night_id(dates[exposure])
                link = config["link"]
                if len(selected) < link["min_detections"] or not possible_arc(
                        nights, dates[exposure], link["min_nights"], link["min_arc_days"], link["window_days"]):
                    continue
                if np.linalg.norm(directions[exposure[0]]-axes[2]) > 2*np.sin(np.deg2rad(field["core_radius_deg"])/2):
                    continue
                sample = np.zeros(len(selected), dtype=raw.dtype)
                object_id = f"sim-{len(all_injected):03d}"
                empirical = 0
                for j, i in enumerate(selected):
                    row = rows[i]
                    key = row["expnum"], row["ccdname"]
                    band = str(row["filter"]).strip()
                    magnitude = mag+{"g":.65, "r":0., "i":-.3, "z":-.45}[band]
                    catalog = lamp[key]
                    analog = np.isfinite(catalog["snr"]) & (abs(catalog["mag_ab"]-magnitude) <= .35)
                    if analog.sum() >= 5:
                        snr = float(np.median(catalog["snr"][analog]))
                        empirical += 1
                    else:
                        snr = 5*10**(.4*(23-magnitude))
                    fwhm = float(row["fwhm"])
                    sigma = np.hypot(.15, fwhm*.262/(2.35482*max(snr,1)))
                    error = rng.normal(0,sigma,2)
                    sample[j]["det_id"] = f"{object_id}-{j:02d}"
                    sample[j]["camera"] = "decam"
                    sample[j]["processing_version"] = PRODUCT
                    sample[j]["expnum"], sample[j]["ccdname"] = key
                    sample[j]["mjd_mid_utc"], sample[j]["night"] = dates[index[i]], nights[j]
                    sample[j]["band"], sample[j]["mag_ab"] = band, magnitude
                    sample[j]["ra_deg"] = (ra[i]+error[0]/(3600*np.cos(np.deg2rad(dec[i])))) % 360
                    sample[j]["dec_deg"] = dec[i]+error[1]/3600
                    sample[j]["sigma_arcsec"], sample[j]["snr"] = sigma, snr
                    sample[j]["mag_err"] = 2.5/np.log(10)/snr
                    sample[j]["flux"] = 10**(.4*(22.5-magnitude))
                    sample[j]["flux_err"] = sample[j]["flux"]/snr
                    sample[j]["fwhm_arcsec"] = fwhm*.262
                    sample[j]["a_pix"] = sample[j]["b_pix"] = fwhm/2.35482
                    sample[j]["edge_distance_pix"] = 20
                span = float(np.ptp(tdb[exposure]))
                angular_rate = np.linalg.norm(directions[exposure[-1]]-directions[exposure[0]])*ARCSEC/span
                all_injected.append((sample, dict(injection_id=object_id, distance_au=distance,
                    mag_r=mag, eccentricity=ecc, apparent_mean_arcsec_per_day=angular_rate,
                    usable_geometry_exposures=len(selected), nights=len(np.unique(nights)), arc_days=span,
                    empirical_snr_epochs=empirical, engineering_snr_epochs=len(sample)-empirical)))
                count += 1
            cells.append(dict(distance_au=[lo,hi], mag_r=[low,high], trials=attempts, injected=count))
    return model, all_injected, cells


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run = args.run
    run_info = json.loads((run/"run_manifest.json").read_text())
    config, field = run_info["config"], run_info["field"]
    if "blind_link_and_fit" not in run_info["stages"]:
        raise ValueError("Complete the frozen blind search before injecting")
    qc = json.loads((run/"ccd_audit.json").read_text())
    ready = {(r["expnum"], r["ccdname"]) for r in qc
             if "astrometry" in r and "exclusion" not in r["astrometry"]}
    rows = np.load(run/"exposures.npy", allow_pickle=False)
    rows = rows[[(int(r["expnum"]), str(r["ccdname"]).strip()) in ready for r in rows]]
    with np.load(run/"classified.npz", allow_pickle=False) as catalog:
        real = catalog["detections"]
    kernel = str(args.work/"inputs/de440s.bsp")
    model, proposals, cells = inject(rows, real, config, field, kernel, config["validation"]["seed"])
    gaia = gaia_field(config["gaia_root"], field)
    sweep = sweep_field(config["sweep_root"], field)
    objects, batches = [], []
    for start in range(0,len(proposals),BATCH_SIZE):
        group = proposals[start:start+BATCH_SIZE]
        merged = np.concatenate([real, *[table for table, _ in group]])
        tdb, obs = time_map(merged["mjd_mid_utc"], kernel)
        reasons, *_ = classify(merged, gaia, sweep, tdb, obs, config["filter"])
        take = link_mask(merged, reasons, config)
        searched = search(merged[take], tdb[take], obs[take], field, config["link"])
        fitted, costs = fit_chains(merged[take], tdb[take], obs[take], model, searched, config)
        for table, record in group:
            ids = set(table["det_id"])
            pure = [fit for fit in fitted if set(fit["det_ids"]) <= ids]
            in_pool = np.isin(merged["det_id"][len(real):], table["det_id"])
            record.update(survived=int(np.count_nonzero(take[len(real):] & in_pool)),
                          recovered=bool(pure), largest_pure_chain=max((f["n_det"] for f in pure), default=0),
                          truncated=bool(searched.truncated or costs.get("fit_budget_exhausted")))
            objects.append(record)
        batches.append(dict(start=start, injected_detections=len(merged)-len(real),
                            real_detections=len(real), fit_counts=costs, truncated=searched.truncated))
        print(f"Processed batch {len(batches)}", flush=True)
    if not objects:
        raise RuntimeError("No trajectory met the pilot's actual coverage constraints")
    write_json(args.output, dict(run_id=run_info["run_id"], seed=config["validation"]["seed"],
                                 cells=cells, objects=objects, batches=batches,
                                 scope="conditional on usable CCD catalogs and TAN geometry; no pixel-level completeness calibration"))


if __name__ == "__main__":
    main()
