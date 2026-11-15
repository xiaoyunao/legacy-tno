"""Rank validation fields against DES ephemerides and exploration fields by cadence."""
from collections import Counter
from pathlib import Path

import fitsio
import numpy as np
from scipy.spatial import cKDTree

from .geometry import night_id, sky, unit
from .orbit import Dynamics, observatory

DEPTH_BITS = (1 << 14) | (1 << 18)
DES = "2012B-0001"
DES_EPOCH_TDB = 57388.0


def evaluate_footprint(rows, angles, pad_px=0):
    """TAN approximation for metadata selection. CP TPV is applied after extraction."""
    ra, dec = np.deg2rad(angles)
    ra0 = np.deg2rad(rows["crval1"])
    dec0 = np.deg2rad(rows["crval2"])
    scale = np.sin(dec)*np.sin(dec0) + np.cos(dec)*np.cos(dec0)*np.cos(ra-ra0)
    a = np.rad2deg((np.cos(dec)*np.sin(ra-ra0)) / scale)
    b = np.rad2deg((np.sin(dec)*np.cos(dec0)-np.cos(dec)*np.sin(dec0)*np.cos(ra-ra0)) / scale)
    cd = [rows[name] for name in ("cd1_1","cd1_2","cd2_1","cd2_2")]
    det = cd[0]*cd[3]-cd[1]*cd[2]
    x = (cd[3]*a - cd[1]*b)/det + rows["crpix1"] - 1
    y = (-cd[2]*a + cd[0]*b)/det + rows["crpix2"] - 1
    return ((scale > 0) & (x >= -pad_px) & (y >= -pad_px) &
            (x < rows["width"] + pad_px) & (y < rows["height"] + pad_px))


def eligible(table):
    broad = np.isin(np.char.strip(table["filter"].astype(str)), ["g","r","i","z"])
    # Initial sample admits CCDs which pass quality and depth-only removals.
    use = table[broad & ((table["ccd_cuts"] & ~DEPTH_BITS) == 0) & (table["ccdzpt"] > 0)]
    _, detector = np.unique(use["ccdname"], return_inverse=True)
    physical = use["expnum"] * 128 + detector
    _, indices = np.unique(physical, return_index=True)
    return use[indices]


def possible_arc(nights, dates, min_nights, min_arc_days, window):
    nights = np.asarray(nights)
    dates = np.asarray(dates)
    return (len(np.unique(nights)) >= min_nights and np.ptp(dates) >= min_arc_days
            and np.max(np.diff(np.unique(dates)), initial=0) <= window)


def des_orbits(path):
    data = fitsio.read(path, lower=True)
    for row in data:
        state = np.array([row[k] for k in ("x","y","z","vx","vy","vz")], dtype=float)
        state[3:] /= 365.25
        yield str(row["mpc"]).strip(), state, float(row["m_r"])


def positions_for_selection(rows, work, parameters):
    """Evaluate DES ephemerides and return per-object CCD intersections."""
    inputs = work / "inputs"
    kernel = str(inputs / "de440s.bsp")
    dt = rows["mjd_obs"] + rows["exptime"]/(2*86400)
    _, unique, exp_index = np.unique(rows["expnum"], return_index=True, return_inverse=True)
    mjd = dt[unique]
    tdb, observer = observatory(mjd, kernel)
    dynamics = Dynamics(min(tdb.min(), DES_EPOCH_TDB), max(tdb.max(), DES_EPOCH_TDB), kernel)
    anchors = np.sort(np.unique(np.r_[np.arange(np.floor(tdb.min())-3, np.ceil(tdb.max())+1, 4), tdb.max()+2]))
    coords = unit(rows["ra"], rows["dec"])
    slab = np.floor(dt / 7).astype(int)
    order = np.argsort(slab, kind="stable")
    groups = np.split(order, np.flatnonzero(np.diff(slab[order])) + 1)
    cells = [(slab[i[0]]*7 + 3.5, i, cKDTree(coords[i])) for i in groups]
    week = np.array([c[0] for c in cells])
    near_time = np.searchsorted(tdb[np.argsort(tdb)], week)
    time_index = np.argsort(tdb)[np.minimum(len(tdb)-1, near_time)]
    for target, state, mag in des_orbits(inputs / "des-y6-tno.fits"):
        if mag > parameters["selection_magnitude_max"] or np.linalg.norm(state[:3]) < 28:
            continue
        propagated = dynamics.propagate(state, DES_EPOCH_TDB, anchors)[:, :3]
        rough = np.column_stack([np.interp(tdb, anchors, propagated[:, dim]) for dim in range(3)]) - observer
        rough /= np.linalg.norm(rough, axis=1)[:, None]
        found = [indices[np.asarray(tree.query_ball_point(direction, .021),dtype=int)]
                 for (_, indices, tree), direction in zip(cells, rough[time_index])]
        near = np.concatenate(found)
        near = near[np.linalg.norm(coords[near] - rough[exp_index[near]], axis=1) < .012]
        if not len(near):
            continue
        exposures, idx = np.unique(exp_index[near], return_inverse=True)
        exact = dynamics.apparent(state, DES_EPOCH_TDB, tdb[exposures], observer[exposures])
        ra, dec = sky(exact[idx])
        good = evaluate_footprint(rows[near], (ra, dec), pad_px=30)
        if good.any():
            yield target, mag, near[good], ra[good], dec[good]


def choose(work, cfg):
    metadata = np.load(work / cfg["inventory_file"], allow_pickle=False, mmap_mode="r")
    selected_columns = ["camera", "ccdname", "expnum", "filter", "propid", "exptime",
                        "mjd_obs", "ccdzpt", "ccd_cuts", "ra", "dec", "width", "height",
                        "crpix1", "crpix2", "crval1", "crval2", "cd1_1", "cd1_2", "cd2_1", "cd2_2"]
    compact = np.empty(len(metadata), dtype=[(key, metadata.dtype[key]) for key in selected_columns])
    for key in selected_columns:
        compact[key] = metadata[key]
    table = eligible(compact)
    del compact
    dates = table["mjd_obs"]
    nights = night_id(dates)
    sky_vectors = unit(table["ra"], table["dec"])
    ranking = []
    max_dates = cfg["selection"]["selection_max_window_days"]
    validation_rows = np.flatnonzero((dates >= 56516) & (dates < 58600))
    for target, mag, idx, ra, dec in positions_for_selection(table[validation_rows], work, cfg["selection"]):
        idx = validation_rows[idx]
        order = np.argsort(dates[idx])
        idx, ra, dec = idx[order], ra[order], dec[order]
        for j in np.unique(nights[idx], return_index=True)[1]:
            select = (dates[idx] >= dates[idx[j]]) & (dates[idx]-dates[idx[j]] <= max_dates)
            scope = idx[select]
            passes = possible_arc(nights[scope], dates[scope], cfg["link"]["min_nights"],
                                  cfg["link"]["min_arc_days"], cfg["link"]["window_days"])
            if not passes or len(np.unique(table["expnum"][scope])) < cfg["link"]["min_detections"]:
                continue
            directions = unit(ra[select], dec[select])
            center = directions.mean(axis=0)
            a, b = (float(x) for x in sky(center))
            ranking.append(dict(target=target, mag_r=mag, ra_deg=a, dec_deg=b,
                                dates=[float(dates[scope].min()), float(dates[scope].max())],
                                nights=len(np.unique(nights[scope])),
                                exposures=len(np.unique(table["expnum"][scope])),
                                max_radius_deg=float(np.rad2deg(np.max(np.arccos(
                                    np.clip(directions @ (center/np.linalg.norm(center)), -1, 1)))))))
    print(f"Scored {len(ranking)} viable DES target windows", flush=True)
    ranking.sort(key=lambda o: (-o["nights"], o["mag_r"], -o["exposures"]))
    fields = []
    for row in ranking:
        if row["max_radius_deg"] > cfg["selection"]["core_radius_deg"]*.9:
            continue
        field = make_field(row["ra_deg"], row["dec_deg"], row["dates"], "validation", cfg)
        ccd = select_rows(table, field)
        if len(ccd) <= cfg["selection"]["max_ccds_validation"]:
            fields.append(field)
            break
    # Score independent non-DES fields with a coarse equal-declination grid.
    potential = (np.char.strip(table["propid"].astype(str)) != DES)
    potential &= dates > cfg["selection"]["exploration_min_mjd"]
    search_rows = np.flatnonzero(potential)
    tree = cKDTree(sky_vectors[potential])
    r = cfg["selection"]["exploration_radius_deg"]
    rankings = []
    for dec in range(-12, 18, 3):
        for ra in range(0, 360, 4):
            if fields and np.linalg.norm(unit(ra,dec) - unit(fields[0]["ra_deg"],fields[0]["dec_deg"])) < .12:
                continue
            near = tree.query_ball_point(unit(ra,dec), 2*np.sin(np.deg2rad(r + .13)/2))
            if not near:
                continue
            pool = search_rows[near]
            ids = np.unique(nights[pool])
            for start in ids:
                scope = pool[(nights[pool] >= start) & (nights[pool] <= start+max_dates)]
                if len(scope) > cfg["selection"]["max_ccds_exploration"]:
                    continue
                n = np.unique(nights[scope])
                if not possible_arc(n, n+.7, cfg["link"]["min_nights"], cfg["link"]["min_arc_days"],
                                    cfg["link"]["window_days"]):
                    continue
                exposures = len(np.unique(table["expnum"][scope]))
                if exposures < cfg["link"]["min_detections"]:
                    continue
                rankings.append(dict(ra_deg=ra, dec_deg=dec, nights=len(n), exposures=exposures,
                                     ccds=len(scope), dates=[float(dates[scope].min()), float(dates[scope].max())]))
    rankings.sort(key=lambda o: (-o["nights"], -o["exposures"], o["ccds"]))
    if rankings:
        row = rankings[0]
        fields.append(make_field(row["ra_deg"], row["dec_deg"], row["dates"], "exploration", cfg))
    return dict(fields=fields, validation_ranking=ranking[:40], exploration_ranking=rankings[:40],
                metadata_rows=len(metadata), usable_rows=len(table),
                proposal_counts=dict(Counter(np.char.strip(table["propid"].astype(str)))))


def make_field(ra, dec, dates, kind, cfg):
    radius = cfg["selection"]["core_radius_deg" if kind == "validation" else "exploration_radius_deg"]
    return dict(id=kind, ra_deg=ra, dec_deg=dec, core_radius_deg=radius,
                read_radius_deg=radius + cfg["selection"]["motion_buffer_deg"],
                mjd_min=dates[0]-.01, mjd_max=dates[1]+.01,
                exclude_des=(kind == "exploration"))


def select_rows(table, field):
    center = unit(field["ra_deg"], field["dec_deg"])
    chord = 2*np.sin(np.deg2rad(field["read_radius_deg"] + .18)/2)
    use = (table["mjd_obs"] >= field["mjd_min"]) & (table["mjd_obs"] <= field["mjd_max"])
    subset = table[use]
    if field["exclude_des"]:
        subset = subset[np.char.strip(subset["propid"].astype(str)) != DES]
    return subset[np.linalg.norm(unit(subset["ra"], subset["dec"]) - center, axis=1) <= chord]
