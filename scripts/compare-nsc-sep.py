#!/usr/bin/env python3
"""Compare complete NSC and v1 SEP CCD catalogs at the same physical exposure."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from legacy_tno.geometry import ARCSEC as ARCSEC_PER_RADIAN, angular_residual, unit
from legacy_tno.nsc import query_measurements

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
    checks = []
    nsc_indices = np.flatnonzero(good)
    for i in np.flatnonzero(targets):
        source = nsc[nsc_indices[nearest[i]]]
        checks.append(dict(sep_snr=float(sep["snr"][i]), sep_mag_ab=float(sep["mag_ab"][i]),
                           sep_mask_fraction=float(sep["mask_fraction"][i]),
                           nearest_nsc_arcsec=float(forward[i]*ARCSEC_PER_RADIAN),
                           nearest_nsc_flags=int(source["flags"]),
                           reciprocal=bool(reverse[nearest[i]] == i),
                           within_one_arcsec=bool(forward[i] <= MATCH_RADIUS)))
    valid = mutual & np.isfinite(difference) & (auto[good][nearest] < 90)
    residual = angular_residual(a[valid], b[nearest[valid]])
    measures = np.column_stack((sep["mag_ab"][valid], residual, difference[valid]))
    return dict(sep_rows=len(sep), nsc_rows=len(nsc), nsc_finite_positions=int(good.sum()),
                mutual_matches=int(mutual.sum()),
                median_separation_arcsec=float(np.median(forward[mutual]) * ARCSEC_PER_RADIAN) if mutual.any() else None,
                median_auto_minus_sep_aperture_mag=float(np.median(phot)) if len(phot) else None,
                v1_members_seen=int(targets.sum()), v1_members_with_nsc_match=int((targets & mutual).sum()),
                member_diagnostics=checks,
                flags=dict(Counter(row["flags"] for row in nsc))), measures


def magnitude_summary(groups):
    edges = np.arange(16.0, 25.0)
    output = []
    for band, pieces in sorted(groups.items()):
        pairs = np.concatenate(pieces)
        for index, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
            use = ((pairs[:, 0] >= (lo if index else -np.inf)) &
                   (pairs[:, 0] < (hi if index < len(edges) - 2 else np.inf)))
            sample = pairs[use]
            if not len(sample):
                continue
            output.append(dict(
                band=band, sep_mag_lower=float(lo) if index else None,
                sep_mag_upper=float(hi) if index < len(edges) - 2 else None,
                median_sep_mag=float(np.median(sample[:, 0])), matches=len(sample),
                east_arcsec=np.quantile(sample[:, 1], [.16, .5, .84]).tolist(),
                north_arcsec=np.quantile(sample[:, 2], [.16, .5, .84]).tolist(),
                separation_arcsec=np.quantile(np.linalg.norm(sample[:, 1:3], axis=1), [.16, .5, .84]).tolist(),
                nsc_minus_sep_mag=np.quantile(sample[:, 3], [.16, .5, .84]).tolist()))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("--ccds-per-control", type=int, default=3)
    args = parser.parse_args()
    work = args.work
    inventory = json.loads((work / "v2/nsc_ccds.json").read_text())
    summaries = []
    magnitudes = {}
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
            stats, measures = compare(raw[use], nsc, members)
            magnitudes.setdefault(row["band"], []).append(measures)
            summaries.append(dict(target=target, expnum=row["expnum"], ccdname=row["ccdname"],
                                  band=row["band"], nsc_ccdnum=row["nsc_ccdnum"], **stats))
    print(json.dumps(dict(method="same CCD, reciprocal nearest positions within 1 arcsec",
                          sep="v1 raw CP WCS positions and aperture magnitudes",
                          nsc="calibrated NSC positions and AUTO magnitudes",
                          magnitude_statistics=magnitude_summary(magnitudes), results=summaries), indent=2))


if __name__ == "__main__":
    main()
