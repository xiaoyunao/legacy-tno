#!/usr/bin/env python3
"""Replay a frozen NSC search with per-bin timings and report competing chains."""
import argparse
from itertools import combinations
import json
from pathlib import Path
from time import monotonic

import numpy as np

from legacy_tno.geometry import angular_residual, unit
from legacy_tno.link import search
from legacy_tno.orbit import Dynamics
from legacy_tno.pipeline import fit_chains, write_json
from legacy_tno.static import link_mask
from legacy_tno.validate import night_permutations


def plot_tracks(run, table, candidates, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 4, figsize=(12, 6), layout="constrained")
    for ax, candidate in zip(axes.flat, candidates):
        members = np.asarray(candidate["members"])
        order = np.argsort(table["mjd_mid_utc"][members])
        rows = table[members[order]]
        measured = unit(rows["ra_deg"], rows["dec_deg"])
        predicted = np.asarray(candidate["fitted_directions"])[order]
        offsets = angular_residual(measured, measured[0]) / 60
        model_offsets = angular_residual(predicted, measured[0]) / 60
        ax.plot(*model_offsets.T, color="0.6", marker="x", label="Fit at epochs")
        ax.scatter(*offsets.T, facecolors="none", edgecolors="#14568a", label="Detection")
        for number, point in enumerate(offsets, start=1):
            ax.annotate(str(number), point, xytext=(4, 4), textcoords="offset points", fontsize=8)
        ax.set(title=candidate["candidate_id"], xlabel="East (arcmin)", ylabel="North (arcmin)")
    for ax in list(axes.flat)[len(candidates):]:
        ax.set_axis_off()
    if candidates:
        axes.flat[0].legend(fontsize=8)
    fig.suptitle(f"{run.name} · NSC OF201 field · positions relative to first detection")
    fig.savefig(output, dpi=160)
    plt.close(fig)


def profile(run, kernel, revision, figure):
    manifest = json.loads((run/"run_manifest.json").read_text())
    archived = json.loads((run/"search_domain_summary.json").read_text())
    archived_null = json.loads((run/"null_test_summary.json").read_text())
    blind = json.loads((run/"blind_candidates.json").read_text())
    config, field = manifest["config"], manifest["field"]
    with np.load(run/"classified.npz", allow_pickle=False) as data:
        table, reasons, tdb, obs = (data[key] for key in ("detections", "reasons", "tdb", "observer"))

    use = link_mask(table, reasons, config)
    active, times, observers = table[use], tdb[use], obs[use]
    model = Dynamics(tdb.min(), tdb.max(), kernel)
    start = monotonic()
    outcome = search(active, times, observers, field, config["link"])
    fit_start = monotonic()
    candidates, fit_counts = fit_chains(active, times, observers, model, outcome, config)
    null_start = monotonic()
    null = night_permutations(active, field, config, model, kernel)
    if (len(active) != archived["link_input"] or dict(outcome.counts) != archived["pair_counts"]
            or fit_counts != archived["fit_counts"] or outcome.truncated != archived["truncated"]
            or [list(c["det_ids"]) for c in candidates] != [c["det_ids"] for c in blind]):
        raise ValueError(f"Frozen replay disagrees with the archived main search for {run.name}")
    for saved, replayed in zip(archived_null["controls"], null["controls"], strict=True):
        if any(saved[key] != replayed[key] for key in ("candidates", "fit_counts", "truncated")):
            raise ValueError(f"Frozen replay disagrees with the archived null search for {run.name}")
        if not np.array_equal(saved["night_mapping"], replayed["night_mapping"]):
            raise ValueError(f"Frozen replay changed the night permutation for {run.name}")
    competing = []
    for first, second in combinations(blind, 2):
        shared = set(first["members"]) & set(second["members"])
        if shared:
            competing.append(dict(first=first["candidate_id"], second=second["candidate_id"],
                                  shared_detections=len(shared),
                                  shared_nights=len(np.unique(table["night"][sorted(shared)])),
                                  first_measurements=len(first["members"]),
                                  second_measurements=len(second["members"])))
    if figure and blind:
        plot_tracks(run, table, blind, figure)
    return dict(run_id=run.name, replay_revision=revision, link_input=len(active),
                fit_counts=fit_counts, distance_bins=outcome.bins, null=null, competing_chains=competing,
                association_wall_seconds=fit_start-start, fit_wall_seconds=null_start-fit_start,
                null_wall_seconds=monotonic()-null_start)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("work", type=Path)
    p.add_argument("runs", nargs="+")
    p.add_argument("--revision", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--of201-track-figure", type=Path)
    args = p.parse_args()
    kernel = str(args.work/"inputs"/"de440s.bsp")
    records = []
    for run in args.runs:
        figure = args.of201_track_figure if run == "validation-ef4655b225ac2a" else None
        records.append(profile(args.work/"runs"/run, kernel, args.revision, figure))
        write_json(args.output, records)
        print(f"Profiled {run}", flush=True)


if __name__ == "__main__":
    main()
