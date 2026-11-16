#!/usr/bin/env python3
"""Score candidate growth against Horizons only after anonymous association."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from astropy.time import Time
import numpy as np

from legacy_tno.geometry import angular_residual, unit
from legacy_tno.pipeline import write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("growth", type=Path)
    p.add_argument("target")
    p.add_argument("output", type=Path)
    p.add_argument("--anonymous-selection", type=Path)
    args = p.parse_args()
    trial = json.loads(args.growth.read_text())
    selection = json.loads(args.anonymous_selection.read_text()) if args.anonymous_selection else None
    if selection is not None and selection["run_id"] != trial["run_id"]:
        raise ValueError("Anonymous selection is from a different run")
    measurements = (trial["supporting_measurements"] if selection is None
                    else selection.pop("selected", []))
    checks = {}
    signature = None
    if measurements:
        mjd, index = np.unique([row["mjd_mid_utc"] for row in measurements], return_inverse=True)
        with tempfile.TemporaryDirectory(dir=args.growth.parent) as location:
            work = Path(location)
            with (work/"epochs.csv").open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["utc"])
                writer.writerows([x] for x in Time(mjd, format="mjd", scale="utc", precision=6).isot)
            subprocess.run([sys.executable, str(Path(__file__).with_name("cache-horizons.py")),
                            args.target, str(work/"epochs.csv"), str(work/"horizons.json")], check=True)
            reply = json.loads((work/"horizons.json").read_text())
        signature = reply["api_signature"]
        predicted = np.asarray(reply["jd_ra_dec"])
        if np.any(np.abs(predicted[:,0]-2400000.5-mjd)*86400 > .01):
            raise ValueError("Horizons scoring epochs do not match")
        positions = unit(predicted[:,1], predicted[:,2])
        for row, j in zip(measurements, index, strict=True):
            delta = angular_residual(positions[j], unit(row["ra_deg"], row["dec_deg"]))
            checks[row["det_id"]] = dict(expnum=row["expnum"], night=row["night"],
                ccdname=row["ccdname"], mjd_mid_utc=row["mjd_mid_utc"], snr=row["snr"],
                mask_fraction=row["mask_fraction"], residual_arcsec=delta,
                matched=bool(np.linalg.norm(delta) <= 1.25))
    accepted = []
    for start in trial["growth"] if selection is None else []:
        hit = checks[start["added_detection_id"]]
        for item in start["independent_predictions"]:
            test = checks[item["detection_id"]]
            accepted.append(dict(first=hit, independent=test,
                                 both_match_horizons=hit["matched"] and test["matched"],
                                 refit_rms_arcsec=item["two_night_refit_rms_arcsec"],
                                 independent_prediction_arcsec=item["predicted_residual_arcsec"],
                                 heliocentric=item["heliocentric"]))
    summary = {key: trial[key] for key in (
        "run_id", "candidate_id", "window_days", "season_gap_days", "initial_sky_gate_deg",
        "footprint_count", "attempted_ccds", "attempted_subset", "family_count", "training_arc_days",
        "training_distance_range_au", "checks", "source_matches", "single_epoch_refits",
        "independent_night_prediction_pairs", "scope")}
    if selection is not None:
        summary["anonymous_refinement"] = selection
        summary["selected_epoch_scores"] = list(checks.values())
    write_json(args.output, dict(**summary, target=args.target, scorer=signature,
        candidates_in_scoring=len(checks), horizon_matches=sum(x["matched"] for x in checks.values()),
        confirmed_unique_nights=len({v["night"] for v in checks.values() if v["matched"]}),
        independently_reproduced_pairs=accepted))


if __name__ == "__main__":
    main()
