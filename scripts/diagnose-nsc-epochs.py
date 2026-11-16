#!/usr/bin/env python3
"""Audit known-object detections at independent Horizons W84 exposure midpoints."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import subprocess
import sys

from astropy.time import Time
from astropy.wcs import WCS
import fitsio
import numpy as np

from legacy_tno.catalog import cp_mask, fitsio_header_to_astropy
from legacy_tno.geometry import ARCSEC, unit
from legacy_tno.pipeline import write_json
from legacy_tno.profile import companions
from legacy_tno.select import evaluate_footprint
from legacy_tno.static import link_mask


def nearest(table, vec):
    if not len(table):
        return None, None
    offsets = np.linalg.norm(unit(table["ra_deg"], table["dec_deg"])-vec, axis=1)*ARCSEC
    i = int(np.argmin(offsets))
    return i, float(offsets[i])


def footprint(row, image_root, ra, dec):
    image = image_root / str(row["image_filename"]).strip()
    hdu = int(row["image_hdu"])
    with fitsio.FITS(image) as handle:
        height, width = handle[hdu].get_dims()
        wcs = WCS(fitsio_header_to_astropy(handle[hdu].read_header()), relax=True)
    x, y = map(float, wcs.all_world2pix(ra, dec, 0, quiet=True))
    if not (0 <= x < width and 0 <= y < height):
        return None
    xx, yy = min(width-1, round(x)), min(height-1, round(y))
    _, weight, dq = companions(image)
    window = (slice(max(0, yy-4), min(height, yy+5)), slice(max(0, xx-4), min(width, xx+5)))
    with fitsio.FITS(weight) as handle:
        weight_patch = handle[hdu][window]
    with fitsio.FITS(dq) as handle:
        dq_patch = handle[hdu][window]
        version = handle[0].read_header()["PLVER"]
    mask = cp_mask(dq_patch, weight_patch, weight_patch, version)
    j, i = yy-window[0].start, xx-window[1].start
    return dict(x=x, y=y, dq_code=int(dq_patch[j, i]), center_usable=not bool(mask[j, i]),
                usable_fraction_9pix=float(np.mean(~mask)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--targets", required=True, nargs="+")
    args = parser.parse_args()
    out = args.run
    manifest = json.loads((out/"run_manifest.json").read_text())
    config = manifest["config"]
    if not (out/"blind_candidates.json").is_file():
        raise ValueError("The blind search must write its candidate file before scoring")
    exposures = np.load(out/"exposures.npy", allow_pickle=False)
    by_ccd = {(r["expnum"], r["ccdname"]): r for r in json.loads((out/"ccd_audit.json").read_text())}
    raw = np.load(out/"raw.npy", mmap_mode="r", allow_pickle=False)
    with np.load(out/"classified.npz", allow_pickle=False) as data:
        table, reasons = data["detections"], data["reasons"]
    linkable = link_mask(table, reasons, config)
    mid = exposures["mjd_obs"]+exposures["exptime"]/(2*86400)
    epochs, inverse = np.unique(mid, return_inverse=True)
    epochs_file = out/"horizons_epochs.csv"
    with epochs_file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["utc"])
        writer.writerows([[s] for s in Time(epochs, format="mjd", scale="utc", precision=6).isot])
    results = []
    for name in args.targets:
        cache = out/f"horizons-{name.replace(' ', '_')}.json"
        if not cache.is_file():
            subprocess.run([sys.executable, str(Path(__file__).with_name("cache-horizons.py")),
                            name, str(epochs_file), str(cache)], check=True)
        response = json.loads(cache.read_text())
        coords = np.asarray(response["jd_ra_dec"])
        if len(coords) != len(epochs) or np.any(abs(coords[:, 0]-2400000.5-epochs)*86400 > .01):
            raise ValueError(f"Horizons epochs do not match input for {name}")
        vectors = unit(coords[:, 1], coords[:, 2])
        near = np.flatnonzero(evaluate_footprint(exposures, (coords[inverse, 1], coords[inverse, 2]), pad_px=32))
        records = []
        for i in near:
            row, k = exposures[i], inverse[i]
            exp, ccd = int(row["expnum"]), str(row["ccdname"]).strip()
            geom = footprint(row, Path(config["image_root"]), *coords[k, 1:])
            if geom is None:
                continue
            r = raw[(raw["expnum"] == exp) & (raw["ccdname"] == ccd)]
            indices = np.flatnonzero((table["expnum"] == exp) & (table["ccdname"] == ccd))
            j, raw_sep = nearest(r, vectors[k])
            m, clean_sep = nearest(table[indices], vectors[k])
            cal = None if m is None else indices[m]
            qc = by_ccd[(exp, ccd)]
            radius = config["validation"]["truth_match_arcsec"]
            matched = raw_sep is not None and raw_sep <= radius
            calibrated = clean_sep is not None and clean_sep <= radius
            if qc.get("error") or not geom["center_usable"]:
                status = "no_usable_product_at_position"
            elif not matched:
                status = "no_independent_detection_within_radius"
            elif not calibrated or not linkable[cal]:
                status = "detected_excluded"
            else:
                status = "search_input"
            records.append(dict(expnum=exp, ccdname=ccd, band=str(row["filter"]).strip(),
                                midpoint_utc_mjd=epochs[k], status=status, mask=geom,
                                product_error=qc.get("error"), gaia_exclusion=qc.get("astrometry", {}).get("exclusion"),
                                nearest_raw_arcsec=raw_sep, nearest_raw_snr=None if j is None else float(r["snr"][j]),
                                nearest_classified_arcsec=clean_sep, classified_reason=reasons[cal] if calibrated else None,
                                raw_match=matched, classified_match=calibrated))
        results.append(dict(target=name, retrieved_utc=response["retrieved_utc"], api=response["api_signature"],
                            epoch_status_counts=dict(Counter(row["status"] for row in records)), ccd_epochs=records))
    write_json(args.output, dict(reference="JPL Horizons W84 astrometric ICRF at CP midpoint UTC",
                                 run_id=manifest["run_id"], targets=results))


if __name__ == "__main__":
    main()
