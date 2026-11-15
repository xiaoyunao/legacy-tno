"""Resumable per-field processing for the DECam pilot."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import resource
from time import monotonic

import numpy as np
from scipy.spatial import cKDTree

from .catalog import extract
from .geometry import angular_residual, night_id, sky, unit
from .link import search, season_labels
from .orbit import Dynamics, fit, heliocentric_elements, observatory
from .select import eligible, evaluate_footprint, select_rows
from .static import calibrate, classify, gaia_field, sweep_field


def json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Cannot serialize {type(obj)}")


def write_json(path, payload):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=json_default) + "\n")
    tmp.replace(path)


def save_npz(path, **data):
    tmp = path.with_suffix(".pending.npz")
    np.savez(tmp, **data)
    tmp.replace(path)


def raw_tile(job):
    row, root, cfg, out = job
    path = out / f'decam-{row["expnum"]}-{str(row["ccdname"]).strip()}.npz'
    if path.exists():
        with np.load(path, allow_pickle=False) as data:
            return path, json.loads(str(data["qc"]))
    try:
        table, qc = extract(row, root, cfg)
    except (ValueError, OSError, IndexError, KeyError, RuntimeError) as exc:
        return None, dict(expnum=int(row["expnum"]), ccdname=str(row["ccdname"]),
                          file=str(root/str(row["image_filename"]).strip()), error=str(exc))
    save_npz(path, detections=table, qc=json.dumps(qc, default=json_default))
    return path, qc


def build_catalogs(out, table, field, cfg, kernel):
    tiles = out / "tiles"
    tiles.mkdir(exist_ok=True)
    gaia = gaia_field(cfg["gaia_root"], field)
    raw, aligned, stats, diagnostic = [], [], [], []
    times = table["mjd_obs"] + table["exptime"]/(2*86400)
    uniq, indices = np.unique(times, return_inverse=True)
    tdb, obs = observatory(uniq, kernel)
    jobs = [(row, Path(cfg["image_root"]), cfg["extract"], tiles) for row in table]
    with ProcessPoolExecutor(max_workers=int(os.environ.get("LEGACY_TNO_WORKERS", "4"))) as pool:
        for i, (path, qc) in enumerate(pool.map(raw_tile, jobs, chunksize=2)):
            stats.append(qc)
            if path is not None:
                with np.load(path, allow_pickle=False) as handle:
                    detections = handle["detections"]
                raw.append(detections)
                adjusted, correction, sampled = calibrate(detections, gaia, tdb[indices[i]],
                                                          obs[indices[i]], cfg["filter"])
                qc["astrometry"] = correction
                if adjusted is not None:
                    aligned.append(adjusted)
                    diagnostic.extend(sampled)
            if (i+1) % 25 == 0:
                print(f"catalog and Gaia solution {i+1}/{len(table)}", flush=True)
    write_json(out / "ccd_audit.json", stats)
    if not aligned:
        raise RuntimeError("All extracted CCDs failed extraction or Gaia calibration")
    calibrated = np.concatenate(aligned)
    raw_table = np.concatenate(raw)
    np.save(out / "raw.npy", raw_table, allow_pickle=False)

    t, idx = np.unique(calibrated["mjd_mid_utc"], return_inverse=True)
    date, ref = observatory(t, kernel)
    tdb, obs = date[idx], ref[idx]
    sweep = sweep_field(cfg["sweep_root"], field)
    reasons, masks, gaia_ids, separation, excess = classify(calibrated, gaia, sweep, tdb, obs, cfg["filter"])
    save_npz(out / "classified.npz", detections=calibrated, reasons=reasons, bits=masks,
             gaia_ids=gaia_ids, gaia_sep_arcsec=separation, excess=excess,
             tdb=tdb, observer=obs, gaia_residual=np.asarray(diagnostic))
    return stats


def fit_chains(table, tdb, observer, orbit_model, search_result, cfg):
    counts = Counter()
    fit_output = []
    cap = cfg["fit"]["max_fits"]
    sorted_chains = sorted(search_result.chains, key=lambda x: (-len(x), -np.ptp(tdb[list(x)]), x))
    accepted = []
    for members in sorted_chains:
        candidate = set(members)
        if any(candidate <= previous for previous in accepted):
            counts["duplicate_subsets"] += 1
            continue
        if counts["attempted"] >= cap:
            counts["fit_budget_exhausted"] += 1
            break
        counts["attempted"] += 1
        epoch, initial_state = search_result.chains[members]
        i = np.array(members)
        directions = unit(table["ra_deg"][i], table["dec_deg"][i])
        try:
            orbit = fit(orbit_model, initial_state, epoch, tdb[i], observer[i], directions,
                        table["sigma_arcsec"][i])
            elements = heliocentric_elements(orbit_model, orbit.state, epoch)
        except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError):
            counts["numerical_failure"] += 1
            continue
        if (not orbit.convergence or orbit.dof <= 0 or
                orbit.reduced_chi2() >= cfg["fit"]["reduced_chi2_max"] or
                np.max(np.abs(orbit.offsets / orbit.errors)) >= cfg["fit"]["max_standardized_residual"]):
            counts["residual_rejected"] += 1
            continue
        if not (cfg["link"]["min_distance_au"] <= elements["r_au"] <= cfg["link"]["max_distance_au"]):
            counts["distance_rejected"] += 1
            continue
        accepted.append(candidate)
        counts["accepted"] += 1
        h = orbit.jacobian
        _, singular, _ = np.linalg.svd(h, full_matrices=False)
        covariance = np.linalg.inv(h.T @ h) if singular[-1]/singular[0] > 1e-9 else None
        exp_count = len(np.unique(table["expnum"][i]))
        nights = len(np.unique(table["night"][i]))
        details = dict(candidate_id=f"C{len(fit_output)+1:04d}", det_ids=table["det_id"][i],
                       status="known_status_unresolved", image_validation="pending",
                       n_det=len(i), n_exp=exp_count, n_night=nights,
                       n_season=len(np.unique(season_labels(table["night"][i], cfg["link"]["season_gap_days"]))),
                       arc_days=float(np.ptp(tdb[i])), epoch_tdb_mjd=epoch,
                       frame="SSB ICRS, AU and AU/day", state=orbit.state, initial_state=initial_state,
                       elements=elements, chi2=orbit.chi2, dof=orbit.dof, rms_arcsec=orbit.rms,
                       covariance_local=covariance,
                       orbit_quality="ambiguous_orbit" if (covariance is None or np.ptp(tdb[i])<60 or
                                                            not elements["bound"] or elements["e"]>.9)
                       else "nominal",
                       offsets_arcsec=orbit.offsets, members=i,
                       fitted_directions=orbit_model.apparent(orbit.state, epoch, tdb[i], observer[i]))
        fit_output.append(details)
    return fit_output, dict(counts)


def footprint_summary(rows, field, valid):
    ra0, dec0 = field["ra_deg"], field["dec_deg"]
    step = .025
    size = field["read_radius_deg"] + .45
    spacing = np.arange(-size, size+step, step)
    dx, dy = np.meshgrid(spacing, spacing)
    dx, dy = dx.ravel(), dy.ravel()
    ra = (ra0 + dx/np.cos(np.deg2rad(dec0))) % 360
    dec = dec0 + dy
    tree = cKDTree(unit(ra, dec))
    footprint = np.zeros(len(ra), dtype=bool)
    night_sets = [set() for _ in ra]
    for row in rows:
        key = (int(row["expnum"]), str(row["ccdname"]).strip())
        if key not in valid:
            continue
        selection = tree.query_ball_point(unit(row["ra"],row["dec"]), .004)
        i = np.array(selection, dtype=int)
        use = i[evaluate_footprint(row, (ra[i],dec[i]))]
        footprint[use] = True
        for j in use:
            night_sets[j].add(int(night_id(row["mjd_obs"])))
    area = step**2*np.cos(np.deg2rad(dec))/np.cos(np.deg2rad(dec0))
    core = np.hypot(dx,dy) <= field["core_radius_deg"]
    return dict(read_area_deg2=float(np.sum(area[footprint])),
                core_covered_deg2=float(np.sum(area[footprint & core])),
                core_geometric_deg2=float(np.sum(area[core])),
                core_four_nights_deg2=float(np.sum(area[(np.array([len(n) for n in night_sets])>=4)&core])),
                coverage=np.c_[ra[footprint], dec[footprint], [len(night_sets[j]) for j in np.flatnonzero(footprint)]],
                grid_step_deg=step)


def reuse_catalogs(parent, out, rows, field, cfg):
    original = json.loads((parent / "run_manifest.json").read_text())
    if "extract_and_clean" not in original["stages"]:
        raise ValueError("Catalog cache has no completed extraction stage")
    relevant = ("schema_version", "inventory_file", "image_root", "gaia_root", "sweep_root", "extract", "filter")
    if original["field"] != field or any(original["config"][key] != cfg[key] for key in relevant):
        raise ValueError("Catalog cache field or extraction configuration is different")
    archived = np.load(parent / "exposures.npy", allow_pickle=False)
    if rows.dtype != archived.dtype or rows.shape != archived.shape or rows.tobytes() != archived.tobytes():
        raise ValueError("Catalog cache exposure manifest is different")
    # The first pilot predates per-module signatures. Its archived catalog code
    # was reviewed and remains identical in the replay revision.
    old = original.get("catalog_code_signature")
    if old is None and not original["run_code_commit"].startswith("e56fee4"):
        raise ValueError("Unversioned catalog cache")
    if old is not None and old != catalog_code_signature():
        raise ValueError("Catalog extraction or calibration source changed")
    for filename in ("classified.npz", "raw.npy", "ccd_audit.json"):
        if not (out / filename).exists():
            os.link(parent / filename, out / filename)


def catalog_code_signature():
    h = sha256()
    root = Path(__file__).parent
    for name in ("profile.py", "catalog.py", "geometry.py", "static.py"):
        h.update((root / name).read_bytes())
    return h.hexdigest()


def run(config_path, work, field_path, field_name, run_code_commit, resume, stop_after=None, catalog_parent=None):
    cfg = json.loads(config_path.read_text())
    field = next(field for field in json.loads(field_path.read_text())["fields"] if field["id"] == field_name)
    source = Path(__file__).parent
    h = sha256(config_path.read_bytes() + json.dumps(field, sort_keys=True).encode())
    for p in sorted(source.glob("*.py")):
        h.update(p.read_bytes())
    inventory = work / cfg["inventory_file"]
    kernel = str(work / "inputs" / "de440s.bsp")
    for file in (inventory, Path(kernel)):
        stat = file.stat()
        h.update(f"{file}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    signature = h.hexdigest()
    out = work / "runs" / f"{field_name}-{signature[:14]}"
    out.mkdir(parents=True, exist_ok=True)
    if (out / "run_manifest.json").exists() and not resume:
        raise FileExistsError(f"Use --resume for {out}")
    print(f"RUN_PATH={out}", flush=True)
    manifest = dict(run_id=out.name, configuration_signature=signature, run_code_commit=run_code_commit,
                    utc_start=datetime.now(timezone.utc).isoformat(), slurm_job=os.getenv("SLURM_JOB_ID"),
                    field=field, config=cfg, python=os.sys.version,
                    dependencies={name:version(name) for name in ("numpy","scipy","astropy","fitsio","sep","jplephem")},
                    status="running", path=str(out), stages={},
                    catalog_code_signature=catalog_code_signature(),
                    catalog_parent=str(catalog_parent) if catalog_parent else None)
    write_json(out / "run_manifest.json", manifest)
    start = monotonic()
    stage = "extract_and_clean"
    try:
        all_rows = np.load(inventory, allow_pickle=False, mmap_mode="r")
        rows = eligible(select_rows(all_rows, field))
        if not len(rows):
            raise RuntimeError("No eligible CCDs in field")
        np.save(out / "exposures.npy", rows, allow_pickle=False)
        if catalog_parent and not (out / "classified.npz").exists():
            reuse_catalogs(catalog_parent, out, rows, field, cfg)
        if not (out / "classified.npz").exists():
            stats = build_catalogs(out, rows, field, cfg, kernel)
        else:
            stats = json.loads((out / "ccd_audit.json").read_text())
        valid = {(q["expnum"],q["ccdname"]) for q in stats if "astrometry" in q and "exclusion" not in q["astrometry"]}
        available = np.array([(int(r["expnum"]),str(r["ccdname"]).strip()) in valid for r in rows])
        selected = rows[available]
        cp_summary = [dict(q, wcs=None) for q in stats]
        write_json(out / "astrometry_photometry_qc.json", cp_summary)
        results = dict(field=field, n_ccd_read=len(selected), n_ccd_requested=len(rows),
                       n_exp=len(np.unique(selected["expnum"])), nights=len(np.unique(night_id(selected["mjd_obs"]))),
                       mjd_min=float(selected["mjd_obs"].min()), mjd_max=float(selected["mjd_obs"].max()),
                       bands=dict(Counter(selected["filter"])), propids=dict(Counter(selected["propid"])))
        results.update(footprint_summary(rows, field, valid))
        write_json(out / "exposure_summary.json", results)
        with np.load(out / "classified.npz", allow_pickle=False) as data:
            table, reasons, tdb, obs, Gaia, sep, excess = (data[key] for key in
                ("detections","reasons","tdb","observer","gaia_residual","gaia_sep_arcsec","excess"))
        classes = dict(Counter(reasons))
        manifest["stages"][stage] = dict(n_raw=int(sum(q.get("retained",0) for q in stats)),
                                        n_calibrated=len(table), classes=classes, seconds=monotonic()-start)
        write_json(out / "static_filter_summary.json", classes)
        write_json(out / "run_manifest.json", manifest)
        if stop_after == "catalog":
            manifest["status"] = "partial"
            manifest["stop_reason"] = "catalog profiling requested"
            return out
        stage = "blind_link_and_fit"
        print("Starting anonymous association", flush=True)
        t0 = monotonic()
        minimum = cfg["link"].get("min_catalog_snr", cfg["filter"]["search_snr"])
        disqualified = (reasons == "transient_clean") & (table["snr"] < minimum)
        reasons[disqualified] = "quality_rejected"
        use = reasons == "transient_clean"
        indices = np.flatnonzero(use)
        dynamics = Dynamics(tdb.min(), tdb.max(), kernel)
        search_result = search(table[use], tdb[use], obs[use], field, cfg["link"])
        solutions, fit_counts = fit_chains(table[use], tdb[use], obs[use], dynamics, search_result, cfg)
        for candidate in solutions:
            candidate["members"] = indices[candidate["members"]]
        write_json(out / "blind_candidates.json", solutions)
        domain = dict(truncated=search_result.truncated, pair_counts=dict(search_result.counts), fit_counts=fit_counts,
                      link_input=len(indices), excluded_by_bright_search=int(np.count_nonzero(disqualified)))
        write_json(out / "search_domain_summary.json", domain)
        manifest["stages"][stage] = dict(domain, seconds=monotonic()-t0)
        stage = "identify_and_validate"
        print("Writing post-search identity and controls", flush=True)
        from .validate import validate
        validate(out, work, selected, table, reasons, tdb, obs, field, cfg, dynamics, solutions)
        from .plot import plot
        plot(out)
        manifest["status"] = "partial" if (search_result.truncated or fit_counts.get("fit_budget_exhausted") or
                                          len(selected) != len(rows)) else "completed"
        return out
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["failure"] = dict(stage=stage, type=type(exc).__name__, message=str(exc))
        raise
    finally:
        manifest["wall_seconds"] = monotonic()-start
        manifest["max_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        manifest["utc_end"] = datetime.now(timezone.utc).isoformat()
        write_json(out / "run_manifest.json", manifest)
