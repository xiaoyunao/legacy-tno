#!/usr/bin/env python3
"""Plot measured association efficiency for the frozen catalog injection cells."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recovery", type=Path)
    parser.add_argument("figure", type=Path)
    args = parser.parse_args()
    report = json.loads(args.recovery.read_text())
    distance = sorted({tuple(row["distance_au"]) for row in report["cells"]})
    magnitude = sorted({tuple(row["mag_r"]) for row in report["cells"]})
    count = np.zeros((len(magnitude), len(distance)), dtype=int)
    good = np.zeros_like(count)
    passed = np.zeros_like(count)
    epochs = np.zeros_like(count)
    for row in report["objects"]:
        if row["truncated"]:
            continue
        j = next(i for i, (lo, hi) in enumerate(distance) if lo <= row["distance_au"] < hi)
        i = next(i for i, (lo, hi) in enumerate(magnitude) if lo <= row["mag_r"] < hi)
        count[i,j] += 1
        good[i,j] += row["recovered"]
        passed[i,j] += row["survived"]
        epochs[i,j] += row["usable_geometry_exposures"]
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.3), layout="constrained")
    for ax, yes, total, title in zip(axes, [passed, good], [epochs, count],
                                    ["Measurements entering association", "Pure tracks recovered"], strict=True):
        fraction = np.divide(yes, total, out=np.full_like(yes, np.nan, dtype=float), where=total>0)
        image = ax.imshow(fraction, vmin=0, vmax=1, cmap="Blues", aspect="auto")
        for i, j in np.ndindex(fraction.shape):
            if total[i,j]:
                ax.text(j, i, f"{yes[i,j]}/{total[i,j]}", ha="center", va="center",
                        color="white" if fraction[i,j]>.65 else "#162f4c", fontsize=13)
        ax.set(xticks=range(len(distance)), xticklabels=[f"{lo}–{hi}" for lo, hi in distance],
               yticks=range(len(magnitude)), yticklabels=[f"{lo:g}–{hi:g}" for lo, hi in magnitude],
               xlabel="Heliocentric injection distance (au)", ylabel="Injected r magnitude (AB)", title=title)
    fig.colorbar(image, ax=axes, label="Conditional fraction", shrink=.86)
    fig.savefig(args.figure, dpi=180, bbox_inches="tight")


if __name__ == "__main__":
    main()
