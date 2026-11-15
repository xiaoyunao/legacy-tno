"""Blind two-night pairs, bounded depth triplets, and four-night growth."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from dataclasses import dataclass
from itertools import combinations
import os

import numpy as np
from scipy.optimize import lsq_linear
from scipy.spatial import cKDTree

from .geometry import ARCSEC, basis, project, unit
from .orbit import GM, LIGHT_SPEED


@dataclass
class SearchResult:
    chains: dict
    counts: Counter
    truncated: list


def depth_bins(inner, outer, fraction):
    edges = [1 / outer]
    step = (1 + fraction) / (1 - fraction)
    while edges[-1] < 1 / inner:
        edges.append(min(1 / inner, edges[-1] * step))
    return [(1 / upper, 1 / lower) for lower, upper in zip(edges, edges[1:])]


def season_labels(night, gap_days):
    nights, index = np.unique(night, return_inverse=True)
    groups = np.cumsum(np.r_[0, np.diff(nights) > gap_days])
    return groups[index]


def initial_linear(angles, obs, time, depth_range, radial_limit, sigma):
    # Barycentric coordinates satisfy x - theta_x z = obs_x - theta_x obs_z.
    # Scale velocities to AU per 100 d for the bounded solve.
    dt = time / 100
    design = np.zeros((len(dt), 2, 6))
    design[:, 0, 0] = 1
    design[:, 1, 1] = 1
    design[:, 0, 3] = dt
    design[:, 1, 4] = dt
    design[:, :, 2] = -angles
    design[:, :, 5] = -angles * dt[:, None]
    rhs = obs[:, :2] - angles * obs[:, 2:3]
    m = (design / sigma[:, None, None]).reshape(-1, 6)
    y = (rhs / sigma[:, None]).ravel()
    x = np.linalg.lstsq(m, y, rcond=None)[0]
    if not (depth_range[0] <= x[2] <= depth_range[1] and abs(x[5]) <= radial_limit * 100):
        lo = [-np.inf, -np.inf, depth_range[0], -np.inf, -np.inf, -radial_limit*100]
        hi = [np.inf, np.inf, depth_range[1], np.inf, np.inf, radial_limit*100]
        x = lsq_linear(m, y, bounds=(lo, hi), method="bvls").x
    x[3:] /= 100
    return x


def line_prediction(state, time, observer):
    displacement = state[:3] + time * state[3:] - observer
    return displacement[:2] / displacement[2]


def endpoint_envelope(theta_first, theta_last, observers, times, depths, escape):
    first, last, predicted = times
    t = (predicted - first) / (last - first)
    region = []
    for depth in depths:
        for vz in (-escape, escape):
            z1 = depth - observers[0, 2]
            z2 = depth + vz * (last-first) - observers[1, 2]
            x1 = observers[0, :2] + theta_first*z1
            x2 = observers[1, :2] + theta_last*z2
            z3 = depth + vz * (predicted-first) - observers[2, 2]
            region.append(((1-t)*x1 + t*x2 - observers[2, :2]) / z3)
    corners = np.stack(region)
    center = (corners.max(axis=0) + corners.min(axis=0)) / 2
    radius = np.max(np.linalg.norm(corners - center, axis=-1), axis=0)
    return center, radius


def search(table, time, observer, field, cfg):
    counts = Counter()
    chains, truncated = {}, []
    if len(table) == 0:
        return SearchResult(chains, counts, truncated)
    axes = basis(field["ra_deg"], field["dec_deg"])
    directions = unit(table["ra_deg"], table["dec_deg"])
    theta = project(directions, axes)
    observ = observer @ axes.T
    sigma = table["sigma_arcsec"]
    membership = season_labels(table["night"], cfg["season_gap_days"])
    field_chord = 2*np.sin(np.deg2rad(field["core_radius_deg"])/2)
    in_core = np.linalg.norm(directions - axes[2], axis=-1) <= field_chord
    workers = int(os.getenv("LEGACY_TNO_LINK_WORKERS","1"))
    executor = ProcessPoolExecutor(max_workers=workers) if workers > 1 else nullcontext()
    with executor as pool:
        for season in np.unique(membership):
            nights = np.unique(table["night"][membership == season])
            if len(nights) < cfg["min_nights"]:
                counts["no_seed_seasons"] += 1
                continue
            exposures = [np.flatnonzero((table["expnum"] == exp) & (membership == season))
                         for exp in np.unique(table["expnum"][membership == season])]
            exposures = [idx for idx in exposures if idx.size]
            exposures.sort(key=lambda idx: time[idx[0]])
            ix = np.array([i[0] for i in exposures])
            trees = [cKDTree(theta[idx]) for idx in exposures]
            bins = depth_bins(cfg["min_distance_au"], cfg["max_distance_au"], cfg["bin_half_fraction"])
            jobs = [(table["night"][ix], time, theta, observ, sigma, in_core, ix, exposures,
                     trees, axes, bounds, cfg) for bounds in bins]
            results = (pool.map(search_distance_bin, jobs) if pool else map(search_distance_bin, jobs))
            for bin_number, (found, bin_counts, reason) in enumerate(results):
                counts.update(bin_counts)
                for key, value in found.items():
                    chains.setdefault(key, value)
                if reason:
                    bounds = bins[bin_number]
                    truncated.append(dict(season=int(season), distance_bin=bin_number,
                                          z_min=bounds[0], z_max=bounds[1], reason=reason))
    return SearchResult(chains, counts, truncated)


class SearchLimit(Exception):
    """An explicit bound prevents reporting a partially searched bin as complete."""


def search_distance_bin(args):
    counts, chains = Counter(), {}
    reason = None
    try:
        search_bin(*args, counts, chains)
    except SearchLimit as exc:
        reason = str(exc)
    return chains, counts, reason


def search_bin(night, time, theta, observ, sigma, in_core, ix, exposures, trees, axes,
               bounds, cfg, counts, chains):
    low, high = bounds
    escape = np.sqrt(2*GM["sun"]/(low-2)) * cfg["escape_padding"]
    acceleration = GM["sun"] / (low-2)**2
    midpoint = (low + high)/2
    window = cfg["far_window_days"] if low >= 50 else cfg["window_days"]
    mjd = time[ix]
    n_pair = n_triplet = n_chains = 0
    for k, l in combinations(range(len(exposures)), 2):
        span = mjd[l] - mjd[k]
        if night[k] == night[l] or span < cfg["min_arc_days"] or span > 2*window:
            continue
        middle = np.flatnonzero((night > night[k]) & (night < night[l]) &
                                (mjd - mjd[k] <= window) & (mjd[l] - mjd <= window))
        if not middle.size:
            continue
        p, q = ix[k], ix[l]
        first, last = exposures[k], exposures[l]
        correction = (observ[p, :2] - observ[q, :2]) / midpoint
        pad = np.linalg.norm(observ[p] - observ[q]) * (1/low - 1/high) + escape*span/(low-2)
        pad += cfg["envelope_pad_arcsec"] / ARCSEC
        matches = trees[l].query_ball_point(theta[first] + correction, pad)
        rows = np.repeat(first, [len(i) for i in matches])
        cols = last[np.fromiter((i for group in matches for i in group), dtype=int)]
        n_pair += len(rows)
        counts["pairs"] += len(rows)
        if n_pair > cfg["max_pairs_per_bin"]:
            raise SearchLimit("pair budget exceeded")
        if not len(rows):
            continue
        for m in middle:
            r = ix[m]
            center, radius = endpoint_envelope(theta[rows], theta[cols], observ[[p, q, r]],
                                              mjd[[k, l, m]], bounds, escape)
            # Bound neglected constant acceleration term between pair endpoints.
            sag = acceleration * (mjd[m]-mjd[k])*(mjd[l]-mjd[m]) / (2*(low-2))
            hits = trees[m].query_ball_point(center, radius + sag + cfg["envelope_pad_arcsec"]/ARCSEC)
            found = sum(map(len, hits))
            n_triplet += found
            counts["triplets"] += found
            if n_triplet > cfg["max_triplets_per_bin"]:
                raise SearchLimit("triplet budget exceeded")
            for a, b, matches_m in zip(rows, cols, hits):
                for c in exposures[m][matches_m]:
                    members = [a, c, b]
                    epoch = time[a]
                    approx = initial_linear(theta[members], observ[members], time[members]-epoch,
                                            bounds, escape, sigma[members])
                    if np.linalg.norm(approx[3:]) > escape:
                        continue
                    errs = [np.linalg.norm(line_prediction(approx, time[j]-epoch, observ[j]) - theta[j])
                            for j in members]
                    if max(errs) > (sag*2 + cfg["envelope_pad_arcsec"]/ARCSEC):
                        continue
                    grow = []
                    for exp, idx in enumerate(ix):
                        dt = time[idx] - epoch
                        if exp in (k, l, m) or abs(dt) > cfg["grow_window_days"]:
                            continue
                        prediction = line_prediction(approx, dt, observ[idx])
                        curvature_error = acceleration * abs(dt * (dt - span)) / (low-2)
                        radius = cfg["growth_radius_arcsec"] / ARCSEC + curvature_error
                        matches_exp = trees[exp].query_ball_point(prediction, radius)
                        if len(matches_exp):
                            grow.append((exp, exposures[exp][matches_exp]))
                    qualifying = [(exp, hits) for exp, hits in grow if night[exp] not in night[[k,l,m]]]
                    for exp, hits in qualifying:
                        for fourth in hits:
                            seed = sorted([*members, fourth])
                            depth_state = initial_linear(theta[seed], observ[seed], time[seed]-epoch,
                                                         bounds, escape, sigma[seed])
                            if np.linalg.norm(depth_state[3:]) > escape:
                                continue
                            selected = set(seed)
                            for another_exp, possible in grow:
                                if another_exp == exp:
                                    continue
                                a_time = time[ix[another_exp]] - epoch
                                predicted = line_prediction(depth_state, a_time, observ[ix[another_exp]])
                                offsets = np.linalg.norm(theta[possible]-predicted, axis=1)
                                best = int(np.argmin(offsets))
                                if offsets[best] <= cfg["growth_radius_arcsec"]/ARCSEC:
                                    selected.add(possible[best])
                            idx = tuple(sorted(selected))
                            if len(idx) < cfg["min_detections"] or not in_core[idx[0]]:
                                continue
                            if idx in chains:
                                continue
                            scores = [np.linalg.norm(line_prediction(depth_state, time[j]-epoch,
                                                     observ[j]) - theta[j]) for j in idx]
                            if max(scores)*ARCSEC > cfg["seed_residual_arcsec"]:
                                continue
                            state = np.r_[depth_state[:3] @ axes, depth_state[3:] @ axes]
                            state[:3] += state[3:] * np.linalg.norm(state[:3]) / LIGHT_SPEED
                            chains[idx] = (float(epoch), state)
                            n_chains += 1
                            counts["chains"] += 1
                            if n_chains >= cfg["max_chains_per_bin"]:
                                raise SearchLimit("chain budget exceeded")
