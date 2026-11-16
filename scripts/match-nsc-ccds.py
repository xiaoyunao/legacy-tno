#!/usr/bin/env python3
"""Map NSC chip numbers to Legacy CCDs using headers in the matching CP exposures."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import fitsio


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("legacy_audit", type=Path)
    parser.add_argument("nsc_inventory", type=Path)
    parser.add_argument("--image-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    fields = json.loads(args.legacy_audit.read_text())["results"]
    inventory = json.loads(args.nsc_inventory.read_text())["legacy_matches"]
    result = {}
    summaries = {}
    for name, rows in fields.items():
        exposure_matches = {row["expnum"]: row for row in inventory[name]}
        per_image = defaultdict(list)
        for row in rows:
            per_image[row["image_filename"]].append(row)
        selected = []
        for image, ccds in per_image.items():
            if all(exposure_matches[r["expnum"]]["status"] != "matched" for r in ccds):
                selected.extend({**row, "nsc_chip_status": exposure_matches[row["expnum"]]["status"]}
                                for row in ccds)
                continue

            with fitsio.FITS(args.image_root / image) as handle:
                for row in ccds:
                    match = exposure_matches[row["expnum"]]
                    if match["status"] != "matched":
                        selected.append({**row, "nsc_chip_status": match["status"]})
                        continue
                    header = handle[row["image_hdu"]].read_header()
                    if str(header["EXTNAME"]).strip() != row["ccdname"]:
                        raise ValueError(f"CCD identity mismatch for {image}, HDU {row['image_hdu']}")
                    ccdnum = int(header["CCDNUM"])
                    status = "chip_listed" if ccdnum in match["nsc_ccdnums"] else "chip_not_listed"
                    exposure = next(item["exposure"] for item in match["matches"] if item["metadata_match"])
                    selected.append({**row, "nsc_chip_status": status, "nsc_exposure": exposure,
                                     "nsc_ccdnum": ccdnum})
        result[name] = selected
        summaries[name] = dict(Counter(row["nsc_chip_status"] for row in selected))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"fields": summaries, "detail_path": str(args.output.absolute())}, indent=2))


if __name__ == "__main__":
    main()
