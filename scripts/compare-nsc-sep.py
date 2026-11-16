#!/usr/bin/env python3
"""Compare complete NSC and v1 SEP CCD catalogs at the same physical exposure."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from legacy_tno.geometry import unit
from legacy_tno.nsc import query_measurements

ARCSEC_PER_RADIAN = 180 * 3600 / np.pi
MATCH_RADIUS = 1 / ARCSEC_PER_RADIAN
CONTROLS = {
    "validation-97d3348bc5c4b3": "2013 TV158",
    "validation-7185aa85687161": "2017 OF201",
}


def get_control(run, target):
    summary = json.loads((run / "candidate_summary.json").read_text())
    matched = [r for r in summary if r.get("catalog_association") == target
               and r.get("status") == "known_recovered_blind"]
    if len(matched) != 1:
        raise ValueError(f"Expected one pure v1 blind chain for {target}")
    candidates = json.loads((run / "blind_candidates.json").read_text())
    return next(r for r in candidates if r["candidate_id"] == matched[0]["candidate_id"])


def compare(sep, nsc, expected_ids):
    ra = np.array([float(row["ra"] or "nan") for row in nsc])
    dec = np.array([float(row["dec"] or "nan") for row in nsc])
    auto = np.array([float(row["mag_auto"] or "nan") for row in nsc])
    good = np.isfinite(ra) & np.isfinite(dec)
    if not np.any(good) or not len(sep):
        raise ValueError("Comparison CCD has no finite NSC positions or no SEP detections")
    a = unit(sep["ra_deg"], sep["dec_deg"])
    b = unit(ra[good], dec[good])
    forward, nearest = cKDTree(b).query(a)
    _, reverse = cKDTree(a).query(b)
    mutual = (forward <= MATCH_RADIUS) & (reverse[nearest] == np.arange(len(a)))
    difference = auto[good][nearest] - sep["mag_ab"]
    phot = difference[mutual & np.isfinite(difference) & (auto[good][nearest] < 90)]
    targets = np.isin(sep["det_id"], sorted(expected_ids))
    return dict(sep_rows=len(sep), nsc_rows=len(nsc), nsc_finite_positions=int(good.sum()),
                mutual_matches=int(mutual.sum()),
                median_separation_arcsec=float(np.median(forward[mutual]) * ARCSEC_PER_RADIAN) if mutual.any() else None,
                median_auto_minus_sep_aperture_mag=float(np.median(phot)) if len(phot) else None,
                v1_members_seen=int(targets.sum()), v1_members_with_nsc_match=int((targets & mutual).sum()),
                flags=dict(Counter(row["flags"] for row in nsc)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("--ccds-per-control", type=int, default=3)
    args = parser.parse_args()
    work = args.work
    inventory = json.loads((work / "v2/nsc_ccds.json").read_text())
    summaries = []
    for run_id, target in CONTROLS.items():
        run = work / "runs" / run_id
        candidate = get_control(run, target)
        members = set(candidate["det_ids"])
        member_keys = {(int(value.split(":")[1]), value.split(":")[2]) for value in members}
        rows = sorted((r for r in inventory[run_id] if (r["expnum"], r["ccdname"]) in member_keys
                       and r["nsc_chip_status"] == "chip_listed"), key=lambda r: r["mjd"])
        if not rows:
            raise ValueError(f"No CCD overlap for {target}")
        indexes = np.unique(np.linspace(0, len(rows)-1, min(len(rows), args.ccds_per_control), dtype=int))
        raw = np.load(run / "raw.npy", mmap_mode="r", allow_pickle=False)
        for i in indexes:
            row = rows[i]
            use = (raw["expnum"] == row["expnum"]) & (raw["ccdname"] == row["ccdname"])
            nsc = query_measurements(row["nsc_exposure"], row["nsc_ccdnum"], work / "v2/nsc_query_cache")
            summaries.append(dict(target=target, expnum=row["expnum"], ccdname=row["ccdname"],
                                  nsc_ccdnum=row["nsc_ccdnum"], **compare(raw[use], nsc, members)))
    print(json.dumps(dict(method="same CCD, reciprocal nearest positions within 1 arcsec",
                          sep="v1 raw CP WCS positions and aperture magnitudes",
                          nsc="calibrated NSC positions and AUTO magnitudes", results=summaries), indent=2))


if __name__ == "__main__":
    main()
