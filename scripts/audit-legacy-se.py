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


def input_rows(path, image_root):
    if path.suffix == ".npy":
        import numpy as np

        for row in np.load(path, mmap_mode="r", allow_pickle=False):
            yield {"camera": str(row["camera"]).strip(), "expnum": int(row["expnum"]),
                   "ccdname": str(row["ccdname"]).strip(), "image_filename": str(row["image_filename"]).strip(),
                   "mjd": float(row["mjd_obs"]), "exptime": float(row["exptime"]),
                   "band": str(row["filter"]).strip(), "image_hdu": int(row["image_hdu"])}
    else:
        for row in json.loads(path.read_text())["product_samples"]:
            image = Path(row["products"][0]["path"]).relative_to(image_root)
            yield {**{name: row[name] for name in ("expnum", "ccdname", "mjd", "exptime", "band", "image_hdu")},
                   "camera": "decam", "image_filename": image.as_posix()}


def main():
    from collections import Counter

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--image-root", required=True, type=Path)
    parser.add_argument("--survey-root", action="append", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="Store path-by-path detail here and print only the aggregate")
    args = parser.parse_args()
    checked = {}
    results = {}
    summary = []
    for source in args.inputs:
        label = source.parent.name if source.suffix == ".npy" else source.stem
        rows = list(input_rows(source, args.image_root))
        for row in rows:
            suffix = se_path(row["image_filename"], row["ccdname"])
            hits = []
            for root in args.survey_root:
                path = root / suffix
                if path not in checked:
                    checked[path] = inspect(path)
                hits.append({"path": str(path), **checked[path]})
            row["paths"] = hits
        results[label] = rows
        summary.append(dict(sample=label, ccd_rows=len(rows),
                            exposures=len({(row["camera"], row["expnum"]) for row in rows}),
                            mjd_min=min(row["mjd"] for row in rows),
                            mjd_max=max(row["mjd"] for row in rows),
                            status_counts=dict(Counter(p["status"] for r in rows for p in r["paths"]))))
    metadata = {"naming_rule": "legacypipe DR11.1.0 set_calib_filenames",
                "survey_roots": [str(root) for root in args.survey_root],
                "unique_paths_checked": len(checked), "samples": summary}
    if args.output:
        args.output.write_text(json.dumps({**metadata, "results": results}, indent=2) + "\n")
        metadata["detail_path"] = str(args.output.absolute())
    else:
        metadata["results"] = results
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
