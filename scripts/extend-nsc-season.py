#!/usr/bin/env python3
"""Search Legacy exposure footprints in other seasons using anonymous orbit families."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import fitsio
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

from legacy_tno.geometry import ARCSEC, angular_residual, basis, sky, unit
from legacy_tno.nsc import query_chip_details, query_exposures, query_measurement_group
from legacy_tno.nsc_adapter import FATAL_EXTRACTOR_FLAGS, normalize
from legacy_tno.orbit import Dynamics, GM, fit, heliocentric_elements, observatory
from legacy_tno.pipeline import write_json
from legacy_tno.select import eligible, evaluate_footprint

MATCH_ARCSEC = 3.0
MAX_DAYS = 760
SEASON_GAP = 120


def orbit_family(model, candidate, dates, observer, tracks):
    epoch = candidate["epoch_tdb_mjd"]
    state = np.asarray(candidate["state"])
    axes = basis(*sky(state[:3]))
    nominal = (state.reshape(2, 3) @ axes.T).ravel()
    covariance = candidate.get("covariance_local")
    sigma_depth = np.sqrt(max(0, axes[2] @ np.asarray(covariance)[:3, :3] @ axes[2])) if covariance else .5
    depths = np.unique(np.clip(nominal[2] + max(.03, sigma_depth)*np.arange(-3, 4), 30, 300))
    velocity_scale = .005
    measured = unit(tracks["ra_deg"], tracks["dec_deg"])
    sigma = tracks["sigma_arcsec"][:, None]
    family = []
    for depth in depths:
        escape = np.sqrt(2*GM["sun"]/(depth-1))
        radial_grid = np.unique(np.r_[np.linspace(-escape, escape, 13), nominal[5]])
        for radial in radial_grid:
            def cartesian(free):
                x, y, dx, dy = free
                return (np.array([[x, y, depth], [dx*velocity_scale, dy*velocity_scale, radial]]) @ axes).ravel()

            def objective(free):
                apparent = model.apparent(cartesian(free), epoch, dates, observer)
                return (angular_residual(apparent, measured)/sigma).ravel()

            initial = nominal[[0,1,3,4]] / [1,1,velocity_scale,velocity_scale]
            sol = least_squares(objective, initial, max_nfev=25)
            state = cartesian(sol.x)
            elements = heliocentric_elements(model, state, epoch)
            if sol.success and elements["bound"] and 30 <= elements["r_au"] <= 300:
                family.append(dict(state=state, chi2=float(sol.fun @ sol.fun), r_au=elements["r_au"],
                                   semimajor_axis_au=elements["a_au"], e=elements["e"]))
    family.sort(key=lambda sample: sample["chi2"])
    if not family:
        raise ValueError("No bound orbit family survived the training arc")
    return [r for r in family if r["chi2"] <= family[0]["chi2"] + 12]


def find_footprints(rows, orbit_directions, exposure_indices):
    vectors = unit(rows["ra"], rows["dec"])
    results = defaultdict(list)
    for k, directions in enumerate(orbit_directions):
        projected = directions[exposure_indices]
        near = np.flatnonzero(np.linalg.norm(vectors-projected, axis=1) < .006)
        within = near[evaluate_footprint(rows[near], sky(projected[near]), pad_px=-10)]
        for j in within:
            results[j].append(k)
    return results


def lookup_exposures(pairs, cache):
    ids = sorted({int(row["expnum"]) for row in pairs})
    names = defaultdict(list)
    for start in range(0, len(ids), 24):
        for row in query_exposures(ids[start:start+24], cache):
            names[int(row["expnum"])].append(row)
    return names


def growth(model, kernel, epoch, family, new_sources, track, old_tdb, old_obs):
    if not new_sources:
        return []
    all_mid = np.asarray([r["detection"]["mjd_mid_utc"] for r in new_sources])
    all_t, all_o = observatory(all_mid, kernel)
    measured = unit(track["ra_deg"], track["dec_deg"])
    solutions = []
    for i, item in enumerate(new_sources):
        candidate = item["detection"]
        append = unit(candidate["ra_deg"], candidate["dec_deg"])
        times, obs = np.r_[old_tdb, all_t[i]], np.vstack([old_obs, all_o[i]])
        direction = np.vstack([measured, append])
        sigmas = np.r_[track["sigma_arcsec"], max(.15, candidate["sigma_arcsec"])]
        initial = family[item["family_index"]]["state"]
        first = fit(model, initial, epoch, times, obs, direction, sigmas)
        if (not first.convergence or first.reduced_chi2() >= 5
                or np.max(np.abs(first.offsets/first.errors)) >= 5):
            continue
        elements = heliocentric_elements(model, first.state, epoch)
        if not elements["bound"] or not 30 <= elements["r_au"] <= 300:
            continue
        sample = dict(added_detection_id=str(candidate["det_id"]),
                      added_expnum=int(candidate["expnum"]), added_night=int(candidate["night"]),
                      single_night_trial_rms_arcsec=first.rms, independent_predictions=[])
        predicted = model.apparent(first.state, epoch, all_t, all_o)
        for k, unseen in enumerate(new_sources):
            jd = unseen["detection"]
            if jd["night"] == candidate["night"]:
                continue
            position = unit(jd["ra_deg"], jd["dec_deg"])
            residual = angular_residual(predicted[k], position)
            if np.linalg.norm(residual) <= MATCH_ARCSEC:
                final = fit(model, first.state, epoch, np.r_[times, all_t[k]], np.vstack([obs, all_o[k]]),
                            np.vstack([direction, position]), np.r_[sigmas, max(.15, jd["sigma_arcsec"])])
                if final.convergence and final.reduced_chi2() < 5:
                    e = heliocentric_elements(model, final.state, epoch)
                    if e["bound"] and 30 <= e["r_au"] <= 300:
                        sample["independent_predictions"].append(dict(detection_id=str(jd["det_id"]),
                            expnum=int(jd["expnum"]),
                            night=int(jd["night"]), predicted_residual_arcsec=residual,
                            two_night_refit_rms_arcsec=final.rms, heliocentric=e))
        solutions.append(sample)
    return solutions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("run")
    parser.add_argument("candidate")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-ccds", type=int, default=140)
    args = parser.parse_args()
    work = args.work
    run = work/"runs"/args.run
    config = json.loads((run/"run_manifest.json").read_text())["config"]
    [candidate] = [r for r in json.loads((run/"blind_candidates.json").read_text()) if r["candidate_id"] == args.candidate]
    members = candidate["members"]
    with np.load(run/"classified.npz", allow_pickle=False) as data:
        tracks, old_tdb, old_obs = (data[k][members] for k in ("detections", "tdb", "observer"))
    t0, t1 = float(tracks["mjd_mid_utc"].min()), float(tracks["mjd_mid_utc"].max())
    kernel = str(work/"inputs/de440s.bsp")
    model = Dynamics(t0-MAX_DAYS-2, t1+MAX_DAYS+2, kernel)
    family = orbit_family(model, candidate, old_tdb, old_obs, tracks)
    print(f"Training-only orbit family: {len(family)} acceptable samples", flush=True)
    inventory = np.load(work/"smoke/inventory.npy", mmap_mode="r", allow_pickle=False)
    mjd = inventory["mjd_obs"]
    date_mask = ((mjd >= t0-MAX_DAYS) & (mjd <= t1+MAX_DAYS)
                 & ((mjd < t0-SEASON_GAP) | (mjd > t1+SEASON_GAP)))
    possible = inventory[date_mask]
    center = unit(tracks["ra_deg"], tracks["dec_deg"]).mean(axis=0)
    separation = np.linalg.norm(unit(possible["ra"], possible["dec"]) - center, axis=1)
    rows = eligible(possible[separation <= 2*np.sin(np.deg2rad(17)/2)])
    del possible, separation
    mid, indices = np.unique(rows["mjd_obs"]+rows["exptime"]/(2*86400), return_inverse=True)
    t, observer = observatory(mid, kernel)
    directions = [model.apparent(item["state"], candidate["epoch_tdb_mjd"], t, observer) for item in family]
    footprint = find_footprints(rows, directions, indices)
    priority = sorted(footprint, key=lambda j: (-len(footprint[j]), abs(rows[j]["mjd_obs"]-(t0+t1)/2), j))
    work_rows = priority[:args.max_ccds]
    print(f"Geometric opportunities: {len(priority)} CCDs, attempting {len(work_rows)}", flush=True)
    cache = work/"v2/nsc_query_cache"
    names = lookup_exposures(rows[work_rows], cache)
    trace, detections = [], {}
    images = Path(config["image_root"])
    for j in work_rows:
        row = rows[j]
        exp, ccd = int(row["expnum"]), str(row["ccdname"]).strip()
        mjd, duration, band = float(row["mjd_obs"]), float(row["exptime"]), str(row["filter"]).strip()
        opts = [item for item in names[exp] if abs(float(item["mjd"])-mjd)*86400 <= 2 and
                abs(float(item["exptime"])-duration) <= .1 and item["filter"].lower() == band.lower()]
        record = dict(expnum=exp, ccdname=ccd, mjd=mjd, family_samples=len(footprint[j]), n_matches=0)
        if len(opts) != 1:
            trace.append(dict(record, status="no_unique_nsc_exposure"))
            continue
        name = opts[0]["exposure"]
        relpath, hdu = str(row["image_filename"]).strip(), int(row["image_hdu"])
        try:
            with fitsio.FITS(images/relpath) as f:
                ccdnum = int(f[hdu].read_header()["CCDNUM"])
            chip = query_chip_details(name, cache).get(ccdnum)
            if chip is None:
                trace.append(dict(record, status="no_nsc_chip"))
                continue
            measured = query_measurement_group(name, [ccdnum], cache)
            if len(measured) != int(chip["nmeas"]):
                raise ValueError("Measurement and chip counts differ")
            table, qc = normalize(measured, chip, dict(image_filename=relpath, image_hdu=hdu,
                ccdname=ccd, expnum=exp, exptime=duration, mjd=mjd, band=band), images, config["extract"])
        except (ValueError, RuntimeError, OverflowError, OSError, KeyError) as error:
            trace.append(dict(record, status="unreadable_product", error=str(error)))
            continue
        if qc["usable_fraction"] < config["extract"]["minimum_good_fraction"]:
            trace.append(dict(record, status="insufficient_usable_cp_pixels"))
            continue
        valid = ((table["snr"] >= 5) & (table["mask_fraction"] <= config["filter"]["max_mask_fraction"])
                 & (table["edge_distance_pix"] >= config["filter"]["min_edge_pix"])
                 & ((table["extractor_flags"] & FATAL_EXTRACTOR_FLAGS) == 0))
        table = table[valid]
        tree = cKDTree(unit(table["ra_deg"], table["dec_deg"]))
        hits = {}
        for member in footprint[j]:
            predicted = directions[member][indices[j]]
            for k in tree.query_ball_point(predicted, MATCH_ARCSEC/ARCSEC):
                distance = np.linalg.norm(angular_residual(predicted, unit(table[k]["ra_deg"], table[k]["dec_deg"])))
                if k not in hits or distance < hits[k][0]:
                    hits[k] = (distance, member)
        for k, (distance, member) in hits.items():
            point = table[k]
            detections[str(point["det_id"])] = dict(detection=point, distance_arcsec=distance, family_index=member)
        trace.append(dict(record, status="catalog_read", n_matches=len(hits), valid_detections=int(valid.sum())))
    extension = growth(model, kernel, candidate["epoch_tdb_mjd"], family, list(detections.values()),
                       tracks, old_tdb, old_obs)
    summary = dict(run_id=args.run, candidate_id=args.candidate, window_days=MAX_DAYS, season_gap_days=SEASON_GAP,
                   initial_sky_gate_deg=17, footprint_count=len(priority), attempted_ccds=len(work_rows),
                   attempted_subset=len(priority) > len(work_rows), match_radius_arcsec=MATCH_ARCSEC,
                   family_count=len(family), training_arc_days=t1-t0,
                   training_distance_range_au=[min(r["r_au"] for r in family), max(r["r_au"] for r in family)],
                   checks=dict(Counter(row["status"] for row in trace)), source_matches=len(detections),
                   single_epoch_refits=len(extension),
                   independent_night_prediction_pairs=sum(len(r["independent_predictions"]) for r in extension),
                   growth=extension, scope="Legacy exposures only, NSC AUTO detections, bound training orbit grid")
    measurements = []
    for item in detections.values():
        point = item["detection"]
        measurements.append({key: point[key] for key in (
            "det_id", "expnum", "ccdname", "night", "mjd_mid_utc", "ra_deg", "dec_deg",
            "mag_ab", "snr", "sigma_arcsec", "extractor_flags", "dq_flags", "mask_fraction")})
    write_json(args.output, dict(**summary, footprint_audit=trace, orbit_family=family,
                                 supporting_measurements=measurements))
    print(json.dumps({k: v for k, v in summary.items() if k != "growth"}), flush=True)


if __name__ == "__main__":
    main()
