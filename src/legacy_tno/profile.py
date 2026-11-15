"""Inspect sampled products and inventory all DR11 DECam CCD rows."""
import json
import sys
from pathlib import Path

import fitsio
import numpy as np
from astropy.io import fits

ROOT = Path("/global/cfs/cdirs/cosmo/data/legacysurvey/dr11")
IMAGE_ROOT = Path("/global/cfs/cdirs/cosmo/staging")
WORK_ROOT = Path("/global/cfs/cdirs/cosmo/work/legacysurvey/dr11")
EXPOSURE_FIELDS = (
    "camera", "expnum", "ccdname", "filter", "propid", "exptime", "mjd_obs",
    "ccd_cuts", "ra", "dec", "fwhm", "ccdzpt", "image_filename", "image_hdu",
    "width", "height", "crpix1", "crpix2", "crval1", "crval2",
    "cd1_1", "cd1_2", "cd2_1", "cd2_2", "plver", "procdate", "plprocid",
)
HEADER_KEYS = (
    "MJD-OBS", "DATE-OBS", "EXPTIME", "BUNIT", "PROCTYPE", "PRODTYPE",
    "PLVER", "PLPROCID", "WTTYPE", "EXTNAME", "CHECKSUM", "DATASUM",
    "OBS-LONG", "OBS-LAT", "OBS-ELEV", "CTYPE1", "CTYPE2",
)


def companions(science):
    name = science.name
    if "_ooi_" not in name:
        raise ValueError(f"Cannot derive CP companions for {name}")
    return science, science.with_name(name.replace("_ooi_", "_oow_")), science.with_name(name.replace("_ooi_", "_ood_"))


def inspect_file(path, hdu):
    try:
        with fits.open(path, lazy_load_hdus=True) as handle:
            header = {key: handle[0].header[key] for key in HEADER_KEYS if key in handle[0].header}
            header.update({key: handle[hdu].header[key] for key in HEADER_KEYS if key in handle[hdu].header})
            pixels = handle[hdu].section[100:180, 100:180]
            return dict(path=str(path), size=path.stat().st_size, header=header,
                        dtype=str(pixels.dtype), median=float(np.nanmedian(pixels)),
                        pixel_examples=np.unique(pixels)[:8].tolist(), status="readable")
    except (OSError, IndexError, ValueError) as exc:
        return dict(path=str(path), status=type(exc).__name__, message=str(exc))


def main(out, quick=False):
    out.mkdir(parents=True, exist_ok=True)
    survey = ROOT / "survey-ccds-decam-dr11.fits.gz"
    annotated = ROOT / "ccds-annotated-decam-dr11.fits.gz"
    with fitsio.FITS(survey) as handle:
        columns = handle[1].get_colnames()
        fields = [c for c in columns if c.lower() in EXPOSURE_FIELDS]
        table = handle[1].read(columns=fields, lower=True)
    paths = table["image_filename"].astype(str)
    samples = []
    _, first = np.unique(table["expnum"], return_index=True)
    chronological = first[np.argsort(table["mjd_obs"][first])]
    masks = table["ccd_cuts"]
    for i in chronological[np.linspace(0, len(first)-1, 14, dtype=int)]:
        row = table[i]
        path = IMAGE_ROOT / paths[i].strip()
        exp = f'{row["expnum"]:08d}'
        ccd = str(row["ccdname"]).strip()
        sample = dict(expnum=int(row["expnum"]), ccdname=ccd, band=str(row["filter"]).strip(),
                      mjd=float(row["mjd_obs"]), exptime=float(row["exptime"]),
                      ccdzpt=float(row["ccdzpt"]), image_hdu=int(row["image_hdu"]))
        sample["products"] = [inspect_file(p, sample["image_hdu"]) for p in companions(path)]
        relative = f"calib/decam/se/{exp[:5]}/{exp}/decam-{exp}-{ccd}.fits"
        sample["se_paths"] = {str(root / relative): (root / relative).is_file()
                              for root in (ROOT, WORK_ROOT, ROOT.parent / "dr10", ROOT.parent / "dr9")}
        samples.append(sample)
        print(json.dumps(sample), flush=True)
    inventory_path = out / "inventory.npy"
    np.save(inventory_path, table, allow_pickle=False)
    if quick:
        from .catalog import extract
        candidates = [i for i in chronological[np.linspace(0, len(first)-1, 70, dtype=int)]
                      if masks[i] in (0, 1<<14) and table["ccdzpt"][i] > 0]
        stats = []
        for i in candidates[:4]:
            try:
                catalog, qc = extract(table[i], IMAGE_ROOT, dict(
                    catalog_snr=4.25, detect_sigma=1.5, min_area=4,
                    minimum_good_fraction=.60, aperture_fwhm=1.15))
                qc.pop("wcs")
                qc["snr_quantiles"] = np.quantile(catalog["snr"], [.1,.5,.9]).tolist()
                qc["mag_quantiles"] = np.quantile(catalog["mag_ab"], [.1,.5,.9]).tolist()
                np.save(out / f"sample-{i}.npy", catalog, allow_pickle=False)
            except (ValueError, OSError, KeyError, IndexError) as exc:
                qc = dict(expnum=int(table["expnum"][i]), error=str(exc))
            stats.append(qc)
            print(json.dumps(qc), flush=True)
        (out / "smoke_catalogs.json").write_text(json.dumps(stats, indent=2) + "\n")
        if not any("retained" in row and row["retained"] for row in stats):
            raise RuntimeError("CP extraction produced no usable sample catalogs")
    with fitsio.FITS(annotated) as handle:
        ann_columns = handle[1].get_colnames()
        selected = [c for c in ann_columns if c.lower() in
                    {"camera", "ccdname", "expnum", "psfdepth", "galdepth", "sig1", "meansky"}]
        annot = handle[1].read(columns=selected, lower=True)
    np.save(out / "annotated.npy", annot, allow_pickle=False)
    summary = dict(survey_path=str(survey), survey_bytes=survey.stat().st_size, survey_columns=columns,
                   annotated_path=str(annotated), annotated_bytes=annotated.stat().st_size,
                   annotated_columns=ann_columns, annotated_rows=len(annot),
                   survey_rows=len(table), exposures=len(first), min_mjd=float(table["mjd_obs"].min()),
                   max_mjd=float(table["mjd_obs"].max()), cut_bit_counts={str(i): int(np.count_nonzero(masks & (1<<i))) for i in range(31)},
                   bands={str(b): int(np.count_nonzero(table["filter"]==b)) for b in np.unique(table["filter"])},
                   samples=samples)
    (out / "inventory_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"inventory complete: {len(table)} CCDs, {len(first)} exposures", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), quick="--quick" in sys.argv)
