#!/usr/bin/env python3
"""Rank small non-DES fields by real cadence, depth proxy and NSC coverage."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from scipy.spatial import cKDTree

from legacy_tno.geometry import night_id, unit
from legacy_tno.nsc import query_exposures
from legacy_tno.pipeline import write_json
from legacy_tno.select import DES, eligible, evaluate_footprint

CORE_DEG = .20
READ_DEG = .96
WINDOW_DAYS = 17
MAX_CCDS = 275


def summarize_core(rows, ra, dec):
    axis = np.linspace(-CORE_DEG, CORE_DEG, 5)
    x, y = np.meshgrid(axis, axis)
    use = np.hypot(x, y) <= CORE_DEG
    footprints = []
    for a, b in zip(ra + x[use]/np.cos(np.deg2rad(dec)), dec + y[use]):
        visible = rows[evaluate_footprint(rows, (a, b), pad_px=-16)]
        nights = night_id(visible["mjd_obs"])
        if len(nights):
            footprints.append((len(np.unique(nights)), len(np.unique(visible["expnum"])),
                               float(np.ptp(visible["mjd_obs"]))))
        else:
            footprints.append((0, 0, 0))
    return sum(n >= 4 and e >= 6 and span >= 7 for n, e, span in footprints)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--controls", nargs="+", type=Path, required=True)
    args = parser.parse_args()
    source = np.load(args.inventory, mmap_mode="r", allow_pickle=False)
    date = source["mjd_obs"]
    scope = (date >= 57754) & (date < 58804)
    rows = eligible(source[scope])
    del source, scope
    rows = rows[np.char.strip(rows["propid"].astype(str)) != DES]
    nights = night_id(rows["mjd_obs"])
    ra, dec = np.meshgrid(np.arange(0, 360, 2), np.arange(-26, 32, 2))
    points = SkyCoord(ra.ravel()*u.deg, dec.ravel()*u.deg)
    use = (abs(points.barycentrictrueecliptic.lat.deg) < 24) & (abs(points.galactic.b.deg) > 25)
    grid = np.c_[points.ra.deg[use], points.dec.deg[use]]
    controls = [json.loads(path.read_text())["fields"][0] for path in args.controls]
    vectors = unit(grid[:, 0], grid[:, 1])
    keep = np.ones(len(grid), dtype=bool)
    for prior in controls:
        dist = np.linalg.norm(vectors - unit(prior["ra_deg"], prior["dec_deg"]), axis=1)
        keep &= dist > 2*np.sin(np.deg2rad(prior["read_radius_deg"]+READ_DEG+1)/2)
    tree = cKDTree(unit(rows["ra"], rows["dec"]))
    neighborhoods = tree.query_ball_point(vectors[keep], 2*np.sin(np.deg2rad(READ_DEG+.18)/2))
    prelim = []
    for (a, b), indices in zip(grid[keep], neighborhoods):
        indices = np.asarray(indices, dtype=int)
        if len(indices) < 6:
            continue
        for start in np.unique(nights[indices]):
            window = indices[(nights[indices] >= start) & (nights[indices] < start+WINDOW_DAYS)]
            if not 6 <= len(window) <= MAX_CCDS:
                continue
            exposures = np.unique(rows["expnum"][window])
            independent_nights = np.unique(nights[window])
            days = rows["mjd_obs"][window]
            if len(exposures) < 6 or len(independent_nights) < 4 or np.ptp(days) < 7:
                continue
            core = summarize_core(rows[window], a, b)
            if core >= 7:
                prelim.append((core, len(independent_nights), len(exposures), -len(window), a, b, window))
    prelim.sort(key=lambda row: row[:6], reverse=True)
    shortlist, seen = [], set()
    for _, _, _, _, a, b, window in prelim:
        if (a, b) in seen:
            continue
        seen.add((a, b))
        shortlist.append((a, b, window))
        if len(shortlist) == 10:
            break
    cache = args.work / "v2/nsc_query_cache"
    ranked = []
    for a, b, window in shortlist:
        selected = rows[window]
        ids, first = np.unique(selected["expnum"], return_index=True)
        offered = defaultdict(list)
        for start in range(0, len(ids), 24):
            for row in query_exposures(ids[start:start+24].tolist(), cache):
                offered[int(row["expnum"])].append(row)
        matched = {}
        for i in first:
            item = selected[i]
            options = [row for row in offered[int(item["expnum"])]
                       if row["filter"].strip().lower() == str(item["filter"]).strip().lower()
                       and abs(float(row["mjd"])-item["mjd_obs"])*86400 < 2
                       and abs(float(row["exptime"])-item["exptime"]) <= .1]
            if len(options) == 1:
                matched[int(item["expnum"])] = int(options[0]["nmeas"])
        use = selected[np.isin(selected["expnum"], list(matched))]
        core = summarize_core(use, a, b)
        dates = selected["mjd_obs"]
        field = dict(id="exploration", ra_deg=float(a), dec_deg=float(b),
                     core_radius_deg=CORE_DEG, read_radius_deg=READ_DEG,
                     mjd_min=float(dates.min()-.001), mjd_max=float(dates.max()+.001), exclude_des=True)
        ranked.append(dict(field=field, viable_grid_points=core, matched_exposures=len(matched),
                           legacy_exposures=len(ids), legacy_ccds=len(selected), nscexp_ccds=len(use),
                           nsc_nights=len(np.unique(night_id(use["mjd_obs"]))),
                           estimated_nscexp_density=float(np.median(list(matched.values()))) if matched else None,
                           fwhm_median_pix=float(np.median(selected["fwhm"])),
                           zpt_median=float(np.median(selected["ccdzpt"])),
                           proposal_ids=sorted(set(np.char.strip(selected["propid"].astype(str)))), cross_season_ccds=int(sum(
                               (abs(rows["mjd_obs"][tree.query_ball_point(unit(a,b), .018)]-np.mean(dates)) > 120)))))
    ranked = [item for item in ranked if item["viable_grid_points"] >= 7]
    if not ranked:
        raise RuntimeError("No candidate reached the NSC exposure and geometric cadence minimum")
    ranked.sort(key=lambda item: (-item["viable_grid_points"], -item["nsc_nights"],
                                 item["estimated_nscexp_density"], item["legacy_ccds"]))
    report = dict(fields=[ranked[0]["field"]], ranking=ranked, grid_candidates=len(prelim),
                  selection="cadence, NSC metadata and field-level density; no moving-source candidates read")
    write_json(args.work / "v2/pilot-selection.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
