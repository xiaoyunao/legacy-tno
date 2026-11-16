#!/usr/bin/env python3
"""Select and refine anonymous multi-night extensions from measured competing pairs."""
import argparse
from itertools import groupby
import json
from pathlib import Path

import numpy as np

from legacy_tno.geometry import angular_residual, unit
from legacy_tno.orbit import Dynamics, GM, fit, heliocentric_elements, observatory
from legacy_tno.pipeline import write_json

MAX_PAIR_SEEDS = 24
MAX_SEPARATION = 1.25
MAX_SIGMA = 4.0


def orbit_metrics(model, result):
    epoch = result.epoch
    r = result.state[:3] - model.planets(epoch)[0]
    v = result.state[3:] - model.planets(epoch, 1)[0]
    distance = np.linalg.norm(r)
    inv_a = 2/distance - v@v/GM["sun"]
    _, sing, vh = np.linalg.svd(result.jacobian, full_matrices=False)
    uncertainty = {}
    if len(sing) == 6 and sing[-1] > 1e-10*sing[0]:
        for name, gradient in (
            ("distance_sigma_au", np.r_[r/distance, np.zeros(3)]),
            ("inverse_a_sigma_per_au", np.r_[-2*r/distance**3, -2*v/GM["sun"]]),
        ):
            uncertainty[name] = float(np.linalg.norm(vh @ gradient / sing))
    return dict(distance_au=distance, inverse_a_per_au=inv_a,
                elements=heliocentric_elements(model, result.state, epoch),
                arc_rms_arcsec=result.rms, chi2=result.chi2, dof=result.dof, **uncertainty)


def pair_seeds(growth, index, dates, nights):
    scores = {}
    for seed in growth:
        i = index[seed["added_detection_id"]]
        for shot in seed["independent_predictions"]:
            j = index[shot["detection_id"]]
            key = tuple(sorted((i, j)))
            rms = shot["two_night_refit_rms_arcsec"]
            scores[key] = min(scores.get(key, np.inf), rms)
    ranked = sorted(scores, key=lambda pair: (-abs(dates[pair[0]]-dates[pair[1]]), scores[pair], pair))
    primary = {}
    for pair in ranked:
        key = tuple(sorted(nights[list(pair)]))
        primary.setdefault(key, pair)
    diverse = list(primary.values())
    used = set(diverse)
    return len(ranked), (diverse + [p for p in ranked if p not in used])[:MAX_PAIR_SEEDS]


def fit_members(model, epoch, state, base, extension, members):
    times, observer, directions, sigma = (np.concatenate((old, new[members]))
                                          for old, new in zip(base, extension, strict=True))
    return fit(model, state, epoch, times, observer, directions, sigma)


def choose_members(model, epoch, state, extension, expnums):
    times, observer, directions, sigma = extension
    residual = np.linalg.norm(angular_residual(model.apparent(state, epoch, times, observer), directions), axis=1)
    normalized = residual / sigma
    hits = sorted(np.flatnonzero((residual <= MAX_SEPARATION) & (normalized <= MAX_SIGMA)),
                  key=lambda i: (expnums[i], normalized[i], i))
    return np.array(sorted(next(group) for _, group in groupby(hits, key=lambda i: expnums[i])), dtype=int)


def accepted(model, epoch, fitted):
    return (fitted.convergence and fitted.reduced_chi2() < 5 and
            np.max(np.abs(fitted.offsets/fitted.errors)) < 5 and
            heliocentric_elements(model, fitted.state, epoch)["bound"])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("work", type=Path)
    p.add_argument("trial", type=Path, help="Anonymous *-detail.json from the growth job")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    trial = json.loads(args.trial.read_text())
    run = args.work/"runs"/trial["run_id"]
    [candidate] = [row for row in json.loads((run/"blind_candidates.json").read_text())
                   if row["candidate_id"] == trial["candidate_id"]]
    epoch = candidate["epoch_tdb_mjd"]
    old_members = np.array(candidate["members"])
    new = trial["supporting_measurements"]
    if not new:
        write_json(args.output, dict(run_id=trial["run_id"], status="no_growth_sources"))
        return
    with np.load(run/"classified.npz", allow_pickle=False) as data:
        old = data["detections"][old_members]
        old_times = data["tdb"][old_members]
        base = (old_times, data["observer"][old_members], unit(old["ra_deg"], old["dec_deg"]), old["sigma_arcsec"])
    kernel = str(args.work/"inputs"/"de440s.bsp")
    times, observer = observatory([x["mjd_mid_utc"] for x in new], kernel)
    measured = unit([x["ra_deg"] for x in new], [x["dec_deg"] for x in new])
    sigma = np.maximum(.15, [x["sigma_arcsec"] for x in new])
    nights = np.array([x["night"] for x in new])
    expnums = np.array([x["expnum"] for x in new])
    extension = (times, observer, measured, sigma)
    model = Dynamics(min(times.min(), old_times.min()), max(times.max(), old_times.max()), kernel)
    family = np.asarray([x["state"] for x in trial["orbit_family"]])
    predictions = np.asarray([model.apparent(s, epoch, times, observer) for s in family])
    errors = np.asarray([np.linalg.norm(angular_residual(pred, measured), axis=1) for pred in predictions])
    source_index = {x["det_id"]: i for i, x in enumerate(new)}
    count, seeds = pair_seeds(trial["growth"], source_index, times, nights)
    hypotheses = {}
    for seed in seeds:
        members = np.asarray(seed)
        state = family[np.argmin(np.sum(errors[:, members]**2, axis=1))]
        for _ in range(5):
            result = fit_members(model, epoch, state, base, extension, members)
            if not accepted(model, epoch, result):
                break
            found = choose_members(model, epoch, result.state, extension, expnums)
            if len(np.unique(nights[found])) < 2:
                break
            if np.array_equal(found, members):
                existing = hypotheses.get(tuple(found))
                if existing is None or result.chi2 < existing.chi2:
                    hypotheses[tuple(found)] = result
                break
            state, members = result.state, found
    ranked = sorted(hypotheses, key=lambda m: (-len(set(nights[list(m)])), -len(m), hypotheses[m].chi2, m))
    if not ranked:
        write_json(args.output, dict(run_id=trial["run_id"], status="no_stable_hypothesis",
                                     available_pairs=count, tried_seeds=len(seeds)))
        return
    best = np.array(ranked[0])
    final = hypotheses[ranked[0]]
    holdouts = []
    for night in np.unique(nights[best]):
        train, test = best[nights[best] != night], best[nights[best] == night]
        initial = family[np.argmin(np.sum(errors[:, train]**2, axis=1))]
        independent = fit_members(model, epoch, initial, base, extension, train)
        record = dict(night=night, n_test=len(test), success=bool(independent.convergence))
        if independent.convergence:
            prediction = model.apparent(independent.state, epoch, times[test], observer[test])
            delta = angular_residual(prediction, measured[test])
            record["angular_rms_arcsec"] = float(np.sqrt(np.mean(np.sum(delta**2, axis=1))))
            record["maximum_arcsec"] = float(np.max(np.linalg.norm(delta, axis=1)))
        holdouts.append(record)
    initial_fit = fit(model, np.asarray(candidate["state"]), epoch, *base)
    write_json(args.output, dict(run_id=trial["run_id"], candidate_id=trial["candidate_id"],
        status="anonymous_extension_selected", available_pairs=count, tried_seeds=len(seeds),
        alternatives=[dict(nights=len(set(nights[list(m)])), measurements=len(m),
                           overlap_with_best=len(set(m)&set(best)), chi2=hypotheses[m].chi2)
                      for m in ranked],
        old_measurements=len(old), new_measurements=len(best), old_span_days=np.ptp(old_times),
        new_span_days=np.ptp(np.r_[old_times, times[best]]), epoch_tdb_mjd=epoch,
        before=orbit_metrics(model, initial_fit), after=orbit_metrics(model, final),
        uncertainty="local linearized Jacobian using assigned astrometric errors",
        holdouts=holdouts, selected=[new[i] for i in best]))


if __name__ == "__main__":
    main()
