#!/usr/bin/env python3
"""Audit a finite list of Legacy CCDs using the DR11.1.0 SE naming rule."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath


def se_path(image_filename, ccdname):
    image = PurePosixPath(image_filename)
    if image.is_absolute() or ".." in image.parts:
        raise ValueError("image_filename must be relative to the Legacy images root")
    basename = image.name.split(".")[0]
    ccd = ccdname.strip()
    calname = f"{basename}-{ccd}" if ccd else basename
    return Path("calib", "se", image.parent, basename, f"{calname}-se.fits")


def inspect(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {"status": "missing"}
    except OSError as error:
        return {"status": "inaccessible", "error": str(error)}
    if not os.access(path, os.R_OK):
        return {"status": "inaccessible"}
    import fitsio

    try:
        with fitsio.FITS(path) as fits:
            tables = [
                {"hdu": i, "columns": hdu.get_colnames(), "rows": hdu.get_nrows()}
                for i, hdu in enumerate(fits) if hdu.has_data() and hdu.get_exttype() == "BINARY_TBL"
            ]
        return {"status": "inspected", "bytes": stat.st_size, "tables": tables}
    except (OSError, ValueError, RuntimeError) as error:
        return {"status": "unreadable_fits", "error": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("v1_sample", type=Path)
    parser.add_argument("--image-root", required=True, type=Path)
    parser.add_argument("--survey-root", action="append", required=True, type=Path)
    args = parser.parse_args()
    source = json.loads(args.v1_sample.read_text())
    results = []
    for row in source["product_samples"]:
        image = Path(row["products"][0]["path"]).relative_to(args.image_root)
        suffix = se_path(image.as_posix(), row["ccdname"])
        results.append({"expnum": row["expnum"], "ccdname": row["ccdname"],
                        "image_filename": image.as_posix(), "mjd": row["mjd"],
                        "paths": [{"path": str(root / suffix), **inspect(root / suffix)}
                                  for root in args.survey_root]})
    print(json.dumps({"naming_rule": "legacypipe DR11.1.0 set_calib_filenames",
                      "sample": "v1 CP product audit", "results": results}, indent=2))


if __name__ == "__main__":
    main()
