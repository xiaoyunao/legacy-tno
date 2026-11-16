#!/usr/bin/env python3
"""Exercise actual SEP fallback only on Legacy CCDs absent from a prepared NSC set."""
import argparse
from collections import Counter
import json
from pathlib import Path
from time import monotonic

import numpy as np

from legacy_tno.pipeline import prepared_catalog, raw_tile, write_json
from legacy_tno.orbit import observatory
from legacy_tno.static import calibrate, gaia_field


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("work", type=Path)
    p.add_argument("run", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    manifest = json.loads((args.run/"run_manifest.json").read_text())
    cfg, field = manifest["config"], manifest["field"]
    prepared, digest, _ = prepared_catalog(args.work, cfg, field)
    if digest != manifest["catalog_product_hash"]:
        raise ValueError("NSC prepared manifest differs from archived run")
    folder, available = prepared
    rows = np.load(args.run/"exposures.npy", allow_pickle=False)
    missing = [r for r in rows if (int(r["expnum"]), str(r["ccdname"]).strip()) not in available]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cache = args.output.parent/"sep-fallback-tiles"
    cache.mkdir(exist_ok=True)
    gaia = gaia_field(cfg["gaia_root"], field)
    records = []
    for row in missing:
        key = (int(row["expnum"]), str(row["ccdname"]).strip())
        job = (row, Path(cfg["image_root"]), cfg["extract"], cache, (folder, None))
        absent, _ = raw_tile((*job, False))
        if absent is not None:
            raise ValueError(f"Missing-NSC fixture unexpectedly returned a product for {key}")
        start = monotonic()
        tile, qc = raw_tile((*job, True))
        record = dict(expnum=key[0], ccdname=key[1], status="unusable", seconds=monotonic()-start,
                      product=qc.get("source_backend"), error=qc.get("error"))
        if tile is not None:
            cached, _ = raw_tile((*job, True))
            if cached != tile or qc["source_backend"] != "SEP":
                raise ValueError(f"Unexpected fallback-cache result for {key}")
            with np.load(tile, allow_pickle=False) as data:
                table = data["detections"]
            mjd = [row["mjd_obs"]+row["exptime"]/(2*86400)]
            tdb, obs = observatory(mjd, str(args.work/"inputs/de440s.bsp"))
            adjusted, correction, _ = calibrate(table, gaia, tdb[0], obs[0], cfg["filter"])
            record.update(rows=len(table), status="gaia_usable" if adjusted is not None else "gaia_excluded",
                          astrometry=correction, cache_hit_verified=True)
        records.append(record)
    write_json(args.output, dict(run_id=manifest["run_id"], expected_missing_ccds=len(missing),
        status_counts=dict(Counter(r["status"] for r in records)), ccds=records,
        scope="Separate fallback validation on the missing physical CCDs only"))


if __name__ == "__main__":
    main()
