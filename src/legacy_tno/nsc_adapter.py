"""Normalize NSC CCD measurements to the detection schema used by the linker."""
from pathlib import Path

import fitsio
import numpy as np
import sep
from astropy.wcs import WCS

from .catalog import DETECTION, cp_mask, fitsio_header_to_astropy, mjd_mid
from .geometry import night_id
from .profile import companions

PRODUCT = "NSC-DR2:AUTO"
LEGACY_PIXEL_SCALE = .262  # reference scale used by the existing shape classifier
FATAL_EXTRACTOR_FLAGS = 4 | 8 | 16 | 32 | 64 | 128


def normalize(rows, chip, legacy, image_root, config):
    """Use calibrated NSC sky positions and the physical Legacy CCD mask."""
    image = Path(image_root) / legacy["image_filename"]
    _, weight_file, dq_file = companions(image)
    hdu = legacy["image_hdu"]
    with fitsio.FITS(image) as handle:
        primary, header = handle[0].read_header(), handle[hdu].read_header()
        shape = tuple(handle[hdu].get_dims())
    if (str(header["EXTNAME"]).strip() != legacy["ccdname"]
            or int(header["CCDNUM"]) != int(chip["ccdnum"])):
        raise ValueError(f"NSC CCD identity does not match {image}[{hdu}]")
    raw_time, midpoint, exptime = mjd_mid(primary, legacy["exptime"])
    if abs(raw_time - legacy["mjd"]) * 86400 > 2:
        raise ValueError("Legacy NSC inventory does not match CP exposure start")
    if any(r["exposure"] != chip["exposure"] or r["filter"].lower() != legacy["band"].lower()
           or int(r["ccdnum"]) != int(chip["ccdnum"]) for r in rows):
        raise ValueError("Measurements disagree with matched exposure, CCD or filter")
    rows = sorted(rows, key=lambda row: row["measid"])
    ids = [f'nsc:{row["measid"]}' for row in rows]
    if len(set(ids)) != len(ids) or any(len(value) > 40 for value in ids):
        raise ValueError("Invalid or duplicate NSC detection IDs")

    columns = "mjd ra dec raerr decerr mag_auto magerr_auto asemi bsemi fwhm x y".split()
    values = np.array([[float(row[name] or "nan") for name in columns] for row in rows],
                      dtype=float).reshape(-1, len(columns))
    time, ra, dec, er, ed, mag, err, major, minor, fwhm, nsc_x, nsc_y = values.T
    if np.any(~np.isfinite(time) | (np.abs(time - raw_time) * 86400 > 2)):
        raise ValueError("Inconsistent NSC measurement exposure start")
    flags = np.array([int(row["flags"]) for row in rows], dtype=np.int64)
    if np.any((flags < 0) | (flags > 65535)):
        raise ValueError("Invalid NSC extractor flag")
    snr = np.divide(2.5 / np.log(10), err, out=np.zeros_like(err), where=(err > 0) & np.isfinite(err))
    good = (np.isfinite(values[:, 1:10]).all(axis=1) & (ra >= 0) & (ra < 360)
            & (np.abs(dec) <= 90) & (er > 0) & (ed > 0) & (mag < 90) & (snr > 0)
            & (major >= minor) & (minor > 0) & (fwhm > 0))
    i = np.flatnonzero(good)

    def read_companion(file):
        with fitsio.FITS(file) as handle:
            extension, primary_header = handle[hdu].read_header(), handle[0].read_header()
            if (extension["EXTNAME"].strip() != legacy["ccdname"]
                    or primary_header["PLPROCID"] != primary["PLPROCID"]):
                raise ValueError(f"CP companion does not match {image}[{hdu}]")
            return handle[hdu].read(), primary_header

    weight, _ = read_companion(weight_file)
    dq, dq_primary = read_companion(dq_file)
    if weight.shape != shape or dq.shape != shape:
        raise ValueError(f"CP companion shapes differ for {image}[{hdu}]: {shape}, {weight.shape}, {dq.shape}")
    mask = cp_mask(dq, weight, weight, dq_primary["PLVER"])
    usable_fraction = float(np.mean(~mask))
    wcs = WCS(fitsio_header_to_astropy(header), relax=True)
    x, y = wcs.all_world2pix(ra[i], dec[i], 0, quiet=True)
    height, width = mask.shape
    inside = np.isfinite(x) & np.isfinite(y) & (x >= 0) & (x < width) & (y >= 0) & (y < height)
    seeing = float(chip["fwhm"])
    if not np.isfinite(seeing) or seeing <= 0:
        raise ValueError("NSC chip seeing is missing or nonpositive")
    radius = config["aperture_fwhm"] * seeing / LEGACY_PIXEL_SCALE
    mask_fraction = np.ones(len(i))
    center_dq = np.full(len(i), -1)
    if inside.any():
        mask_sum, _, _ = sep.sum_circle(mask.astype(np.float32), x[inside], y[inside], radius, subpix=3)
        xx = np.minimum(np.rint(x[inside]).astype(int), width - 1)
        yy = np.minimum(np.rint(y[inside]).astype(int), height - 1)
        mask_fraction[inside] = np.clip(mask_sum / (np.pi * radius**2), 0, 1)
        mask_fraction[inside] = np.where(mask[yy, xx], 1, mask_fraction[inside])
        center_dq[inside] = dq[yy, xx]

    table = np.empty(len(i), dtype=DETECTION)
    table["det_id"] = np.asarray(ids)[i]
    table["source_row_id"], table["camera"] = i, "decam"
    table["expnum"], table["ccdname"], table["image_hdu"] = legacy["expnum"], legacy["ccdname"], hdu
    table["processing_version"] = PRODUCT
    table["mjd_start_utc"], table["mjd_mid_utc"], table["exptime_s"] = raw_time, midpoint, exptime
    table["night"], table["band"] = night_id(midpoint), legacy["band"]
    table["ra_deg"], table["dec_deg"] = ra[i], dec[i]
    # A conservative common component avoids interpreting raerr as a coordinate angle twice.
    table["sigma_arcsec"] = np.maximum(er[i], ed[i])
    table["x_pix"], table["y_pix"] = x, y
    table["mag_ab"], table["mag_err"], table["snr"] = mag[i], err[i], snr[i]
    table["flux"] = 10**(.4*(22.5-mag[i]))
    table["flux_err"] = table["flux"] / snr[i]
    table["fwhm_arcsec"] = seeing
    table["a_pix"], table["b_pix"] = major[i] / LEGACY_PIXEL_SCALE, minor[i] / LEGACY_PIXEL_SCALE
    table["extractor_flags"], table["dq_flags"] = flags[i], center_dq
    table["edge_distance_pix"] = np.where(inside, np.minimum.reduce([x, y, width-1-x, height-1-y]), -1)
    table["mask_fraction"] = mask_fraction

    pixel_residual = np.hypot(x - (nsc_x[i] - 1), y - (nsc_y[i] - 1))
    usable = inside & np.isfinite(pixel_residual)
    qc = dict(source_backend=PRODUCT, nsc_exposure=chip["exposure"], nsc_ccdnum=int(chip["ccdnum"]),
              expnum=legacy["expnum"], ccdname=legacy["ccdname"], file=str(image),
              band=legacy["band"], start_mjd=raw_time, middle_mjd=midpoint,
              extracted=len(rows), retained=len(table), invalid_measurements=len(rows)-len(table),
              outside_cp=int((~inside).sum()), nsc_chip_nmeas=int(chip["nmeas"]),
              usable_fraction=usable_fraction,
              fatal_extractor_flags=int(np.count_nonzero(flags[i] & FATAL_EXTRACTOR_FLAGS)),
              median_cp_vs_nsc_pix=float(np.median(pixel_residual[usable])) if usable.any() else None,
              nsc_detection_fwhm_p50_arcsec=float(np.median(fwhm[i])) if len(i) else None)
    return table, qc
