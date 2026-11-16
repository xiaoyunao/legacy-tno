#!/usr/bin/env python3
"""Export Gaia, usable CCD and source-quality aggregates without source records."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from legacy_tno.pipeline import write_json


def quantile(values):
    return np.quantile(values, [.1, .5, .9], axis=0).tolist() if len(values) else None


def summarize(run):
    stats = json.loads((run/"ccd_audit.json").read_text())
    config = json.loads((run/"run_manifest.json").read_text())
    valid = [r for r in stats if "astrometry" in r and "exclusion" not in r["astrometry"]]
    reasons = Counter()
    sources = Counter()
    for row in stats:
        status = row.get("error") or row.get("astrometry", {}).get("exclusion") or "usable"
        reasons[status] += 1
        sources[row.get("source_backend", "undetermined")] += 1
    physical = []
    for band in sorted({r["band"] for r in valid}):
        obs = [r for r in valid if r["band"] == band]
        physical.append(dict(band=band, ccds=len(obs), exposures=len({r["expnum"] for r in obs}),
                             raw_rows=sum(r["extracted"] for r in obs),
                             retained_rows=sum(r["retained"] for r in obs),
                             gaia_reference_count=quantile([r["astrometry"]["n_gaia"] for r in obs]),
                             offset_arcsec=quantile([r["astrometry"]["offset_arcsec"] for r in obs]),
                             centered_mad_arcsec=quantile([r["astrometry"]["mad_arcsec"] for r in obs]),
                             usable_cp_fraction=quantile([r["usable_fraction"] for r in obs if "usable_fraction" in r]),
                             cp_wcs_minus_nsc_pixel=quantile(
                                 [r["median_cp_vs_nsc_pix"] for r in obs if r.get("median_cp_vs_nsc_pix") is not None]),
                             fatal_extractor_flags=sum(r.get("fatal_extractor_flags", 0) for r in obs)))
    return dict(run_id=config["run_id"], slurm_job=config["slurm_job"], ccds=len(stats),
                source_products=sources, ccd_states=reasons, percentiles=[10,50,90],
                astrometric_components=["east", "north"], by_band=physical)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    write_json(args.output, [summarize(run) for run in args.runs])


if __name__ == "__main__":
    main()
