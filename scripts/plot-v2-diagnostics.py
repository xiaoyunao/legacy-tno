#!/usr/bin/env python3
"""Render coverage, same-CCD comparisons and measured distance-bin costs."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot_coverage(rows, output):
    fig = plt.figure(figsize=(12, 4.8), layout="constrained")
    sky = fig.add_subplot(121, projection="mollweide")
    counts = fig.add_subplot(122)
    colors = {"NSC": "#2875a8", "SEP": "#dc873c", "none": "#999999"}
    offsets = []
    totals = []
    for i, row in enumerate(rows, start=1):
        f = row["field"]
        usable = row["total"]["usable_ccds"]
        product = max(colors, key=lambda key: usable.get(key, 0))
        lon = np.deg2rad((180-f["ra_deg"] + 180) % 360 - 180)
        lat = np.deg2rad(f["dec_deg"])
        sky.scatter(lon, lat, facecolors="none", edgecolors=colors[product],
                    linewidth=1.4, s=2.3*row["total"]["legacy_ccds"]**.65)
        offset = {2: (12, 7), 3: (-13, 7), 4: (10, -12), 5: (-16, -12)}.get(i, (5, 7))
        sky.annotate(str(i), (lon, lat), xytext=offset, textcoords="offset points", fontsize=9)
        years = defaultdict(Counter)
        for block in row["breakdown"]:
            years[block["year"]].update(block["usable_ccds"])
        for y, values in sorted(years.items()):
            label = row["label"]
            offsets.append(f"{i} · {label}" if str(y) in label else f"{i} · {label} · {y}")
            totals.append(values)
    sky.set(title="Audited field centers", xlabel="Right ascension", ylabel="Declination")
    sky.grid(alpha=.4)
    sky.set_xticklabels(["330°", "300°", "270°", "240°", "210°", "180°",
                         "150°", "120°", "90°", "60°", "30°"])
    base = np.zeros(len(totals))
    for key, label in (("NSC", "Usable NSC"), ("SEP", "Archived SEP"), ("none", "Unavailable")):
        width = np.array([item.get(key, 0) for item in totals])
        counts.barh(offsets, width, left=base, color=colors[key], label=label)
        base += width
    counts.invert_yaxis()
    counts.set(xlabel="Legacy CCDs in each field/year", title="Run-verified product coverage")
    counts.legend(fontsize=8, loc="upper right")
    counts.grid(axis="x", alpha=.22)
    fig.savefig(output, dpi=170)
    plt.close(fig)


def plot_comparison(data, output):
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.2), layout="constrained")
    for band in sorted({r["band"] for r in data}):
        samples = [row for row in data if row["band"] == band]
        x = [row["median_sep_mag"] for row in samples]
        for ax, key in zip(axes, ("separation_arcsec", "nsc_minus_sep_mag"), strict=True):
            lo, center, hi = np.array([row[key] for row in samples]).T
            line, = ax.plot(x, center, "o-", ms=4, label=band)
            ax.fill_between(x, lo, hi, color=line.get_color(), alpha=.12)
    axes[0].set(ylabel="NSC–SEP separation (arcsec)")
    axes[1].set(ylabel="NSC AUTO − SEP aperture (mag)")
    axes[1].axhline(0, lw=.8, color="0.5", ls=":")
    for ax in axes:
        ax.set(xlabel="SEP aperture magnitude")
        ax.grid(alpha=.25)
        ax.legend(title="Band")
    fig.suptitle("Same-CCD reciprocal matches within 1″ · median and 16–84th percentiles")
    fig.savefig(output, dpi=170)
    plt.close(fig)


def plot_costs(records, output):
    fig, axes = plt.subplots(len(records), 3, figsize=(12, 3.1*len(records)),
                             squeeze=False, layout="constrained", sharex=True)
    for col, title in enumerate(("Pairs counted", "Triplets counted", "Wall seconds per worker")):
        axes[0, col].set_title(title)
    for record, row in zip(records, axes, strict=True):
        main = record["distance_bins"]
        null = record["null"]["controls"][0]["distance_bins"]
        for series, style, label in ((main, "-", "Observed"), (null, "--", "Night permutation")):
            depths = [np.sqrt(bin["z_min"]*bin["z_max"]) for bin in series]
            values = ([bin["counts"].get("pairs", 0) for bin in series],
                      [bin["counts"].get("triplets", 0) for bin in series],
                      [bin["worker_wall_seconds"] for bin in series])
            truncated = [i for i, bin in enumerate(series) if bin["status"] == "truncated"]
            for axis, y in zip(row, values, strict=True):
                line, = axis.plot(depths, y, ls=style, lw=1.5, label=label)
                axis.scatter(np.asarray(depths)[truncated], np.asarray(y)[truncated],
                             s=20, marker="x", color=line.get_color())
        row[0].set_ylabel("Independent pilot" if record["run_id"].startswith("exploration") else "OF201 field")
        for axis in row:
            axis.set_xscale("log")
            axis.grid(alpha=.24)
    for axis in axes[-1, :]:
        axis.set_xlabel("SSB tangent-plane depth (au)")
    axes[0, -1].legend(fontsize=8)
    fig.suptitle("Frozen replay · crosses mark truncated distance bins")
    fig.savefig(output, dpi=170)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("results", type=Path)
    args = p.parse_args()
    root = args.results
    output = root/"figures"
    output.mkdir(exist_ok=True)
    chart = (("nsc-coverage-public.json", "fields", "nsc_coverage.png", plot_coverage),
             ("nsc-sep-by-magnitude.json", "magnitude_statistics", "nsc_sep_comparison.png", plot_comparison),
             ("nsc-link-bin-profiles.json", None, "nsc_bin_costs.png", plot_costs))
    for filename, key, figure, draw in chart:
        data = json.loads((root/filename).read_text())
        draw(data[key] if key else data, output/figure)


if __name__ == "__main__":
    main()
