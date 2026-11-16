"""Independent post-search evaluation and control trials."""
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from .geometry import ARCSEC, angular_residual, basis, night_id, project, sky, unit
from .link import initial_linear, search
from .orbit import GM, LIGHT_SPEED, fit, heliocentric_elements, observatory
from .pipeline import fit_chains, write_json
from .select import DES_EPOCH_TDB, des_orbits, evaluate_footprint, possible_arc
from .static import gaia_field, sweep_field, classify, link_mask


def time_map(mjd, kernel):
    dates, inverse = np.unique(mjd, return_inverse=True)
    t, o = observatory(dates, kernel)
    return t[inverse], o[inverse]


def matches(table, positions, exposure, radius):
    if not len(table):
        return np.empty(0, dtype=int)
    vectors = unit(table["ra_deg"], table["dec_deg"])
    found = []
    for exp, predicted in zip(exposure, positions):
        idx = np.flatnonzero(table["expnum"] == exp)
        if not len(idx):
            continue
        offsets = np.linalg.norm(vectors[idx]-predicted, axis=1)*ARCSEC
        j = np.argmin(offsets)
        if offsets[j] <= radius:
            found.append(idx[j])
    return np.asarray(found, dtype=int)


def training_arc_fits(table, tdb, obs, model, cfg):
    """Initialize each orbit solely from the training positions and their observing geometry."""
    directions = unit(table["ra_deg"], table["dec_deg"])
    axes = basis(*sky(directions.mean(axis=0)))
    angles = project(directions, axes)
    epoch = float(np.median(tdb))
    sigma = table["sigma_arcsec"]
    edges = np.geomspace(cfg["min_distance_au"], cfg["max_distance_au"], 9)
    fits = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        radial_limit = np.sqrt(2*GM["sun"]/(lo-2)) * cfg["escape_padding"]
        seed = initial_linear(angles, obs @ axes.T, tdb-epoch, (lo, hi), radial_limit, sigma)
        state = np.r_[seed[:3] @ axes, seed[3:] @ axes]
        state[:3] += state[3:] * np.linalg.norm(state[:3]) / LIGHT_SPEED
        try:
            result = fit(model, state, epoch, tdb, obs, directions, sigma)
            elements = heliocentric_elements(model, result.state, epoch)
        except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError):
            continue
        if result.convergence and edges[0] <= elements["r_au"] <= edges[-1] and elements["bound"]:
            fits.append(result)
    return sorted(fits, key=lambda result: result.chi2)


def leave_night_out(candidate, table, tdb, obs, model, *, config=None):
    all_members = candidate["members"]
    direction = unit(table["ra_deg"], table["dec_deg"])
    results = []
    for night in np.unique(table["night"][all_members]):
        keep = table["night"][all_members] != night
        train, test = all_members[keep], all_members[~keep]
        independent = config is not None and config["validation"].get("training_only_initialization", False)
        if len(train) < (3 if independent else 4) or len(np.unique(table["night"][train])) < 3:
            results.append(dict(night=night, status="insufficient_training_data"))
            continue
        if independent:
            fits = training_arc_fits(table[train], tdb[train], obs[train], model, config["link"])
            if not fits:
                results.append(dict(night=night, status="no_training_only_orbit",
                                    n_train=len(train), n_test=len(test), training_starts=8))
                continue
            fit_result = fits[0]
        else:
            fit_result = fit(model, candidate["initial_state"], candidate["epoch_tdb_mjd"],
                             tdb[train], obs[train], direction[train], table["sigma_arcsec"][train])
        direction_predicted = model.apparent(fit_result.state, fit_result.epoch, tdb[test], obs[test])
        offsets = angular_residual(direction_predicted, direction[test])
        results.append(dict(night=night, status="converged" if fit_result.convergence else "fit_failed",
                            n_train=len(train), n_test=len(test), mjd=tdb[test],
                            initialization="training_only" if independent else "full_chain_seed",
                            training_dof=fit_result.dof, training_rms_arcsec=fit_result.rms,
                            training_starts=8 if independent else 1,
                            acceptable_training_fits=len(fits) if independent else int(fit_result.convergence),
                            offsets_arcsec=offsets, rms_arcsec=np.sqrt(np.mean(offsets**2))))
    return results


def verify_truth(out, work, exposures, table, reasons, tdb, obs, field, cfg, world, solutions):
    from .orbit import Dynamics

    kernel = str(work/"inputs"/"de440s.bsp")
    dates = exposures["mjd_obs"] + exposures["exptime"]/(2*86400)
    mjd, idx = np.unique(dates,return_inverse=True)
    times, observer = observatory(mjd, kernel)
    planets = Dynamics(min(DES_EPOCH_TDB,times.min()), max(DES_EPOCH_TDB,times.max()), kernel)
    raw = np.load(out/"raw.npy", allow_pickle=False, mmap_mode="r")
    _, row_index = np.unique(dates,return_index=True)
    result = []
    membership = {}
    searchable = link_mask(table, reasons, cfg)
    for name, state, mag in des_orbits(work/"inputs"/"des-y6-tno.fits"):
        dt = np.mean(times)-DES_EPOCH_TDB
        approximate = state[:3] + dt*state[3:] - np.mean(observer,axis=0)
        approximately_near = np.linalg.norm(approximate/np.linalg.norm(approximate) -
                                            unit(field["ra_deg"],field["dec_deg"]))
        # A healthy margin includes years of curved motion over the DES reference interval.
        if approximately_near > .25:
            continue
        predicted = planets.apparent(state, DES_EPOCH_TDB, times, observer)
        p_ra, p_dec = sky(predicted[idx])
        geometric = evaluate_footprint(exposures, (p_ra,p_dec), pad_px=-5)
        if not geometric.any():
            continue
        exposures_here = np.unique(idx[geometric])
        exp = exposures["expnum"][row_index[exposures_here]]
        direct = predicted[exposures_here]
        close = cfg["validation"]["truth_match_arcsec"]
        r = matches(raw, direct, exp, close+1)
        c = matches(table, direct, exp, close)
        cleaned = c[searchable[c]]
        a = len(exposures_here)
        row = dict(target=name, m_r=mag, reference_distance_au=np.linalg.norm(state[:3]),
                   A_geometry_exposures=a, B_raw_detections=len(r),
                   C_clean_detections=len(cleaned), C_any_calibrated=len(c),
                   geometry_nights=len(np.unique(night_id(mjd[exposures_here]))),
                   clean_nights=len(np.unique(table["night"][cleaned])),
                   clean_arc_days=np.ptp(tdb[cleaned]) if len(cleaned) else None,
                   D_linkable=False, E_blind=False, F_guided_only=False)
        membership[name] = set(c)
        if len(cleaned) >= cfg["link"]["min_detections"]:
            truth_search = search(table[cleaned], tdb[cleaned], obs[cleaned], field, cfg["link"])
            row["D_linkable"] = bool(truth_search.chains)
        result.append(row)
    row_by_name = {r["target"]: r for r in result}
    for solution in solutions:
        i = solution["members"]
        scored = sorted(((len(set(i)&members), target) for target,members in membership.items()), reverse=True)
        if not scored or scored[0][0] == 0:
            continue
        n, target = scored[0]
        solution["catalog_association"] = target
        solution["matched_detections"] = n
        solution["matched_nights"] = len(np.unique(table["night"][list(set(i)&membership[target])]))
        if n == len(i) and (len(scored) == 1 or scored[1][0] < n):
            solution["status"] = "known_recovered_blind"
            row_by_name[target]["E_blind"] = True
            solution["held_nights"] = leave_night_out(solution, table, tdb, obs, world, config=cfg)
        else:
            solution["status"] = "contaminated_or_ambiguous"
    for row in result:
        if not row["E_blind"]:
            guided = sorted(membership[row["target"]])
            if len(guided) >= cfg["link"]["min_detections"]:
                guided_search = search(table[guided], tdb[guided], obs[guided], field, cfg["link"])
                fits, _ = fit_chains(table[guided], tdb[guided], obs[guided], world, guided_search, cfg)
                row["F_guided_only"] = bool(fits)
        row["outcome"] = ("blind" if row["E_blind"] else "guided_only" if row["F_guided_only"]
                          else "no_catalog_detection" if not row["B_raw_detections"]
                          else "none_passed_static_quality" if not row["C_clean_detections"]
                          else "no_seed_or_geometry" if not row["D_linkable"] else "link_or_fit_failed")
    aggregate = dict(A=len(result), B=sum(bool(r["B_raw_detections"]) for r in result),
                     C=sum(bool(r["C_clean_detections"]) for r in result),
                     D=sum(r["D_linkable"] for r in result), E=sum(r["E_blind"] for r in result),
                     F_guided_only=sum(r["F_guided_only"] for r in result))
    return dict(catalog="DES Y6 published 814-object validation catalog",
                catalog_commit="8f254ca30fa0e8fc1576a5a9fad7300124d3b3ee",
                geometry="TAN approximation with five-pixel interior margin; not pixel-mask completeness",
                counts=aggregate, objects=result)


def kepler_generator(position, direction_in_plane, eccentricity, true_anomaly, epoch):
    """Analytic ellipse, independent of the numerical integration and seed model."""
    radius = np.linalg.norm(position)
    e, f = eccentricity, true_anomaly
    a = radius * (1 + e*np.cos(f)) / (1-e**2)
    eccentric = 2*np.arctan2(np.sqrt(1-e)*np.sin(f/2), np.sqrt(1+e)*np.cos(f/2))
    mean0 = eccentric-e*np.sin(eccentric)
    n = np.sqrt(GM["sun"]/a**3)
    rhat = position/radius
    p = np.cos(f)*rhat - np.sin(f)*direction_in_plane
    q = np.sin(f)*rhat + np.cos(f)*direction_in_plane

    def evaluate(times):
        m = mean0+n*(times-epoch)
        e_anomaly = np.full_like(m, eccentric)
        for _ in range(16):
            e_anomaly -= (e_anomaly-e*np.sin(e_anomaly)-m)/(1-e*np.cos(e_anomaly))
        return a*((np.cos(e_anomaly)-e)[:,None]*p +
                  (np.sqrt(1-e**2)*np.sin(e_anomaly))[:,None]*q)

    return evaluate


def catalog_injections(exposures, table, reasons, tdb, obs, field, cfg, model, kernel):
    rng = np.random.default_rng(cfg["validation"]["seed"])
    date = exposures["mjd_obs"]+exposures["exptime"]/(2*86400)
    dates, row_id, idx = np.unique(date, return_index=True, return_inverse=True)
    t, observer = observatory(dates,kernel)
    epoch = float(np.mean(t))
    solar = model.planets(t)[:,0]
    axes = basis(field["ra_deg"],field["dec_deg"])
    targets, data = [], []
    compiled = {"geometric": 0, "requested": cfg["validation"]["injection_objects"]}
    for attempt in range(cfg["validation"]["injection_objects"]*12):
        distance = float(np.exp(rng.uniform(np.log(30),np.log(300))))
        ecc, anomaly, angle = rng.uniform(0,.94), rng.uniform(-np.pi,np.pi), rng.uniform(0,2*np.pi)
        p = axes[2] + np.deg2rad(rng.uniform(-.65,.65,2)) @ axes[:2]
        p /= np.linalg.norm(p)
        v = np.cos(angle)*axes[0] + np.sin(angle)*axes[1]
        v -= p*np.dot(p,v)
        v /= np.linalg.norm(v)
        gen = kepler_generator(p*distance,v,ecc,anomaly,epoch)
        emit = t - distance/LIGHT_SPEED
        for _ in range(3):
            predicted = gen(emit)+solar-observer
            norm = np.linalg.norm(predicted,axis=1)
            emit = t-norm/LIGHT_SPEED
        ra, dec = sky(predicted[idx]/norm[idx,None])
        eligible = np.flatnonzero(evaluate_footprint(exposures,(ra,dec),pad_px=-18))
        if not len(eligible):
            continue
        _, choice = np.unique(idx[eligible],return_index=True)
        usable = eligible[choice]
        exp_rows = idx[usable]
        nights = night_id(dates[exp_rows])
        passed = possible_arc(nights,dates[exp_rows],cfg["link"]["min_nights"],
                              cfg["link"]["min_arc_days"],cfg["link"]["window_days"])
        if len(usable)<cfg["link"]["min_detections"] or not passed:
            continue
        simulated = np.zeros(len(usable), dtype=table.dtype)
        mag = rng.uniform(19.5,23.8)
        noisy = bool(len(targets)%2)
        for k,i in enumerate(usable):
            r = exposures[i]
            simulated["det_id"][k] = f"sim-{len(targets):04d}-{k:03d}"
            simulated["camera"][k] = "decam"
            simulated["expnum"][k], simulated["ccdname"][k] = r["expnum"], r["ccdname"]
            simulated["mjd_mid_utc"][k], simulated["night"][k] = dates[idx[i]], night_id(dates[idx[i]])
            simulated["ra_deg"][k], simulated["dec_deg"][k] = ra[i],dec[i]
            band = str(r["filter"]).strip()
            magnitude = mag + {"g":.65,"r":0,"i":-.3,"z":-.45}[band]
            simulated["band"][k], simulated["mag_ab"][k] = band, magnitude
            flux = 10**(-.4*(magnitude-22.5))
            snr = max(5.1, 5*10**(.4*(23-magnitude)))
            simulated["flux"][k], simulated["flux_err"][k], simulated["snr"][k] = flux, flux/snr, snr
            simulated["sigma_arcsec"][k] = np.hypot(.15, float(r["fwhm"])*.262/(2.35482*snr))
            simulated["fwhm_arcsec"][k] = r["fwhm"]*.262
            simulated["a_pix"][k] = simulated["b_pix"][k] = r["fwhm"]/2.355
            simulated["edge_distance_pix"][k] = 18
        if noisy:
            sigma = simulated["sigma_arcsec"]
            simulated["ra_deg"] = (simulated["ra_deg"] + rng.normal(0,sigma) /
                                  (3600*np.cos(np.deg2rad(simulated["dec_deg"])))) % 360
            simulated["dec_deg"] += rng.normal(0,sigma)/3600
            keep = rng.random(len(simulated)) < np.clip(.82-.17*(mag-22), .25,.98)
            simulated = simulated[keep]
        item = dict(sim_id=f"sim-{len(targets):04d}", distance_au=distance, e=ecc, mag_r=mag,
                    group="hypothetical_missingness" if noisy else "all_points_present",
                    geometry_nights=len(np.unique(nights)), geometry_exposures=len(usable),
                    geometry_arc_days=np.ptp(dates[exp_rows]), injected=len(simulated), recovered=False)
        data.append(simulated)
        targets.append(item)
        if len(targets)>=cfg["validation"]["injection_objects"]:
            break
    gaia = gaia_field(cfg["gaia_root"],field)
    sweep = sweep_field(cfg["sweep_root"],field)
    controls = []
    for start in range(0,len(targets),8):
        group = data[start:start+8]
        combined = np.concatenate([*group, table])
        inj_tdb, inj_obs = time_map(combined["mjd_mid_utc"], kernel)
        kinds, *_ = classify(combined, gaia, sweep, inj_tdb, inj_obs, cfg["filter"])
        take = link_mask(combined, kinds, cfg)
        linked = search(combined[take],inj_tdb[take],inj_obs[take],field,cfg["link"])
        fitted, counts = fit_chains(combined[take],inj_tdb[take],inj_obs[take],model,linked,cfg)
        pure = set()
        for fit_result in fitted:
            sim = {str(det_id).rsplit("-",1)[0] for det_id in fit_result["det_ids"]}
            if len(sim)==1 and next(iter(sim)).startswith("sim-"):
                pure.update(sim)
        for record in targets[start:start+8]:
            record["recovered"] = record["sim_id"] in pure
            record["search_truncated"] = bool(linked.truncated or counts.get("fit_budget_exhausted"))
        controls.append(dict(start=start, truncated=linked.truncated, fits=counts))
    compiled["geometric"] = len(targets)
    return dict(counts=compiled, objects=targets, batches=controls,
                model="independent analytic Kepler ellipses, DE440s topocentric light time, hypothetical missingness")


def write_identity(out, work, exposures, table, reasons, tdb, obs, field, cfg, model, solutions):
    truth = verify_truth(out, work, exposures, table, reasons, tdb, obs, field, cfg, model, solutions)
    write_json(out/"known_recovery_summary.json", truth)
    summaries = []
    members = []
    for sol in solutions:
        i = sol["members"]
        summaries.append({key:value for key,value in sol.items() if key not in ("members","det_ids",
                            "fitted_directions","offsets_arcsec","initial_state")})
        if sol["status"] == "known_recovered_blind":
            ra, dec = sky(sol["fitted_directions"])
            members.append(dict(candidate_id=sol["candidate_id"], target=sol["catalog_association"],
                                mjd_tdb=tdb[i], ra_deg=table["ra_deg"][i], dec_deg=table["dec_deg"][i],
                                predicted_ra=ra, predicted_dec=dec, magnitude=table["mag_ab"][i],
                                band=table["band"][i], mag_err=table["mag_err"][i], sigma_arcsec=table["sigma_arcsec"][i],
                                offsets_arcsec=sol["offsets_arcsec"], held_nights=sol["held_nights"]))
    write_json(out/"candidate_summary.json", summaries)
    write_json(out/"blind_known_plot_data.json",members)


def validate(out, work, exposures, table, reasons, tdb, obs, field, cfg, model, solutions,
             *, geometry_exposures=None):
    write_identity(out, work, exposures if geometry_exposures is None else geometry_exposures,
                   table, reasons, tdb, obs, field, cfg, model, solutions)
    use = link_mask(table, reasons, cfg)
    t, o = tdb[use],obs[use]
    row = table[use]
    nights = np.unique(row["night"])
    rng = np.random.default_rng(cfg["validation"]["seed"])
    controls = []
    for k in range(cfg["validation"]["null_repeats"]):
        mapped_nights = rng.permutation(nights)
        mapping = np.searchsorted(nights, row["night"])
        scramble = row.copy()
        scramble["night"] = mapped_nights[mapping]
        scramble["mjd_mid_utc"] += scramble["night"] - row["night"]
        ts, os = time_map(scramble["mjd_mid_utc"],str(work/"inputs"/"de440s.bsp"))
        linked = search(scramble,ts,os,field,cfg["link"])
        candidates, counts = fit_chains(scramble,ts,os,model,linked,cfg)
        controls.append(dict(repeat=k,candidates=len(candidates),fit_counts=counts,truncated=linked.truncated,
                             night_mapping=np.c_[nights,mapped_nights]))
    write_json(out/"null_test_summary.json",dict(method="observing-night permutation, intra-night offsets preserved",
                                                 controls=controls))
    kernel = str(work/"inputs"/"de440s.bsp")
    if cfg["validation"]["injection_objects"]:
        injection = catalog_injections(exposures,table,reasons,tdb,obs,field,cfg,model,kernel)
        write_json(out/"injection_recovery_summary.json", injection)
