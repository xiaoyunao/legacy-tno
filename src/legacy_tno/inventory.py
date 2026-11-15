"""Finish the full CCD metadata audit using an on-disk FITS staging file."""
from pathlib import Path
import json
import sys

import fitsio
import numpy as np

from .pipeline import write_json
from .profile import ROOT, IMAGE_ROOT
from .select import DEPTH_BITS


def finish(out, profile_log):
    rows = np.load(out/"inventory.npy",mmap_mode="r",allow_pickle=False)
    products = []
    for line in profile_log.read_text(errors="replace").splitlines():
        if line.startswith('{"expnum":'):
            value = json.loads(line)
            if "products" in value:
                products.append(value)
    write_json(out/"catalog_audit.json",
               dict(source="DR11 DECam CP",
                    product_samples=products, independent_se_table_found=any(
                        any(sample["se_paths"].values()) for sample in products),
                    cp_extraction_smoke=json.loads((out/"smoke_catalogs.json").read_text())))
    retained = ROOT/"ccds-annotated-decam-dr11.fits.gz"
    with fitsio.FITS(out/"annotated-stage.fits") as handle:
        cols = handle[1].get_colnames()
        choose = [key for key in cols if key.lower() in {
            "camera","expnum","ccdname","psfdepth","galdepth","sig1","meansky","ccd_cuts"}]
        data = handle[1].read(columns=choose,lower=True)
    np.save(out/"annotated.npy",data,allow_pickle=False)
    files = [ROOT/"survey-ccds-decam-dr11.fits.gz",retained]
    checksums = {}
    with (ROOT/"legacysurvey_dr11.sha256sum").open() as checksum_file:
        for line in checksum_file:
            items=line.split()
            if len(items)>1 and Path(items[1]).name in {p.name for p in files}:
                checksums[Path(items[1]).name]=items[0]
    cuts=rows["ccd_cuts"]
    depth_only=(cuts != 0) & ((cuts&~DEPTH_BITS)==0)
    bands, counts=np.unique(rows["filter"],return_counts=True)
    summary=dict(survey_rows=len(rows), annotated_rows=len(data), distinct_expnum=len(np.unique(rows["expnum"])),
                 bands=dict(zip(bands,counts)), min_mjd=np.min(rows["mjd_obs"]),max_mjd=np.max(rows["mjd_obs"]),
                 total_depth_only=np.count_nonzero(depth_only), total_passes=np.count_nonzero(cuts==0),
                 cut_bit_counts={i:np.count_nonzero(cuts&(1<<i)) for i in range(24)},
                 input_files=[dict(path=str(p), bytes=p.stat().st_size,
                                   provider_sha256=checksums.get(p.name)) for p in files],
                 inventory_dtype=rows.dtype.descr, annotated_dtype=data.dtype.descr)
    write_json(out/"inventory_summary.json",summary)
    print(json.dumps({"survey_rows":len(rows),"annotated_rows":len(data),
                      "distinct_expnum":summary["distinct_expnum"]}), flush=True)


if __name__=="__main__":
    finish(Path(sys.argv[1]),Path(sys.argv[2]))
