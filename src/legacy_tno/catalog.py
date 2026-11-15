"""Extract independent detections from DR11's DECam CP frames."""
import re
from pathlib import Path

import fitsio
import numpy as np
import sep
from astropy.time import Time
from astropy.wcs import WCS

from .geometry import night_id
from .profile import companions

DETECTION = np.dtype([
    ("det_id", "U40"), ("camera", "U5"), ("expnum", "i8"), ("ccdname", "U4"),
    ("image_hdu", "i2"), ("source_row_id", "i4"), ("processing_version", "U40"),
    ("mjd_start_utc", "f8"), ("mjd_mid_utc", "f8"), ("exptime_s", "f4"),
    ("night", "i4"), ("band", "U2"), ("ra_deg", "f8"), ("dec_deg", "f8"),
    ("sigma_arcsec", "f4"), ("x_pix", "f4"), ("y_pix", "f4"),
    ("flux", "f4"), ("flux_err", "f4"), ("snr", "f4"), ("mag_ab", "f4"),
    ("mag_err", "f4"), ("fwhm_arcsec", "f4"), ("a_pix", "f4"), ("b_pix", "f4"),
    ("extractor_flags", "u2"), ("dq_flags", "i2"), ("edge_distance_pix", "f4"),
    ("mask_fraction", "f4")
])


def mjd_mid(header, table_exptime):
    start = float(header["MJD-OBS"])
    exposure = float(header["EXPTIME"])
    date = Time(header["DATE-OBS"], format="isot", scale="utc").mjd
    if abs(start-date)*86400 > 2 or abs(exposure-table_exptime) > .2:
        raise ValueError("CP DATE-OBS, MJD-OBS or EXPTIME inconsistent with exposure inventory")
    return start, start + exposure / (2*86400), exposure


def cp_mask(dq, weight, science, version):
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", version)
    if match is None or tuple(int(value or 0) for value in match.groups()) < (3, 5, 0):
        raise ValueError(f"CP DQ encoding unverified for {version}")
    if np.any((dq < 0) | (dq > 8)):
        raise ValueError(f"Unexpected integer DQ codes for {version}")
    # Code 7 is multi-epoch outlier detection, potentially real motion.
    return np.ascontiguousarray(~np.isfinite(science) | ~np.isfinite(weight) |
                                (weight <= 0) | ((dq != 0) & (dq != 7)))


def image_arrays(science, hdu):
    files = companions(science)
    arrays, headers, primary_headers = [], [], []
    for file in files:
        with fitsio.FITS(file) as handle:
            arrays.append(handle[hdu].read())
            headers.append(handle[hdu].read_header())
            primary_headers.append(handle[0].read_header())
    if len({h["EXTNAME"].strip() for h in headers}) != 1:
        raise ValueError(f"Inconsistent CP CCD identifiers for {science}")
    if len({p["PLPROCID"] for p in primary_headers}) != 1:
        raise ValueError(f"Inconsistent CP processing identifiers for {science}")
    return arrays, headers[0], primary_headers


def extract(row, image_root: Path, parameters):
    path = image_root / str(row["image_filename"]).strip()
    hdu = int(row["image_hdu"])
    (science, weight, dq), header, primaries = image_arrays(path, hdu)
    science = np.ascontiguousarray(science, dtype=np.float32)
    weight = np.ascontiguousarray(weight, dtype=np.float32)
    primary = primaries[0]
    if header["EXTNAME"].strip() != str(row["ccdname"]).strip():
        raise ValueError(f"Unexpected {path} extension {hdu}")
    bunit = str(header.get("BUNIT", primary.get("BUNIT", ""))).strip().upper()
    if bunit and bunit not in ("ADU", "COUNT", "COUNTS"):
        raise ValueError(f"Unverified science BUNIT {bunit}")
    start, middle, exposure = mjd_mid(primary, row["exptime"])
    if abs(start - row["mjd_obs"]) > 2 / 86400:
        raise ValueError("MJD-OBS differs from survey metadata")
    mask = cp_mask(dq, weight, science, primaries[2]["PLVER"])
    usable_fraction = float(np.mean(~mask))
    if usable_fraction < parameters["minimum_good_fraction"]:
        raise ValueError(f"Only {usable_fraction:.3f} of CCD usable")
    science[mask] = 0
    background = sep.Background(science, mask=mask, bw=64, bh=64)
    background.subfrom(science)
    science[mask] = 0
    error = np.full(science.shape, 1e10, np.float32)
    np.divide(1, np.sqrt(np.maximum(weight, 0)), out=error, where=~mask)
    measured = sep.extract(science, parameters["detect_sigma"], err=error, mask=mask,
                           minarea=parameters["min_area"], filter_type="matched")
    seeing_pix = float(row["fwhm"])
    sigma_pix = seeing_pix / 2.35482
    aperture = parameters["aperture_fwhm"] * seeing_pix
    x0, y0 = measured["x"], measured["y"]
    x, y, center_flags = sep.winpos(science, x0, y0, sigma_pix, mask=mask)
    bad_center = (center_flags != 0) | (np.hypot(x-x0, y-y0) > seeing_pix)
    x[bad_center], y[bad_center] = x0[bad_center], y0[bad_center]
    gain = header.get("GAIN")
    if not gain or gain <= 0:
        gains = [header.get(key) for key in ("GAINA", "GAINB")]
        gain = min(gains) if all(value and value > 0 for value in gains) else None
    adu, adu_err, aperture_flags = sep.sum_circle(science, x, y, aperture, err=error,
                                                   gain=gain, mask=mask, subpix=3)
    # Measure the masked fraction separately, including pixels absent from science.
    masked_pixels, _, _ = sep.sum_circle(mask.astype(np.float32), x, y, aperture, subpix=3)
    mask_fraction = np.clip(masked_pixels/(np.pi*aperture**2), 0, 1)
    snr = np.divide(adu, adu_err, out=np.zeros_like(adu), where=adu_err > 0)
    keep = (snr >= parameters["catalog_snr"]) & np.isfinite(snr)
    wcs_header = fitsio_header_to_astropy(header)
    deccam = WCS(wcs_header, relax=True)
    ra, dec = deccam.all_pix2world(x[keep], y[keep], 0)
    flux_scale = 10**(.4*(float(row["ccdzpt"])-22.5)) * exposure
    xx, yy = np.rint(x[keep]).astype(int), np.rint(y[keep]).astype(int)
    xx, yy = np.clip(xx, 0, science.shape[1]-1), np.clip(yy, 0, science.shape[0]-1)
    indices = np.flatnonzero(keep)
    ccd = str(row["ccdname"]).strip()
    result = np.empty(len(indices), dtype=DETECTION)
    result["det_id"] = [f'decam:{row["expnum"]}:{ccd}:{i}' for i in indices]
    result["camera"], result["expnum"], result["ccdname"] = "decam", row["expnum"], ccd
    result["image_hdu"], result["source_row_id"] = hdu, indices
    result["processing_version"] = f'{primary["PLVER"]}:{primary["PLPROCID"]}'
    result["mjd_start_utc"], result["mjd_mid_utc"], result["exptime_s"] = start, middle, exposure
    result["night"], result["band"] = night_id(middle), str(row["filter"]).strip()
    result["ra_deg"], result["dec_deg"] = ra, dec
    result["x_pix"], result["y_pix"] = x[keep], y[keep]
    result["flux"], result["flux_err"] = adu[keep] / flux_scale, adu_err[keep] / flux_scale
    result["snr"] = snr[keep]
    result["mag_ab"] = 22.5 - 2.5*np.log10(result["flux"])
    result["mag_err"] = (2.5/np.log(10)) / snr[keep]
    result["fwhm_arcsec"] = seeing_pix * 0.262
    result["sigma_arcsec"] = result["fwhm_arcsec"] / (2.35482 * snr[keep])
    result["a_pix"], result["b_pix"] = measured["a"][keep], measured["b"][keep]
    result["extractor_flags"] = measured["flag"][keep] | (aperture_flags[keep].astype(np.uint16) << 8)
    result["dq_flags"] = dq[yy, xx]
    result["edge_distance_pix"] = np.minimum.reduce((result["x_pix"], result["y_pix"],
                                        science.shape[1]-1-result["x_pix"], science.shape[0]-1-result["y_pix"]))
    result["mask_fraction"] = mask_fraction[keep]
    qc = dict(file=str(path), expnum=int(row["expnum"]), ccdname=ccd, band=str(row["filter"]).strip(),
              start_mjd=start, middle_mjd=middle, extracted=len(snr), retained=len(result),
              dq_counts=np.bincount(dq.ravel().astype(np.int64), minlength=9).tolist(),
              sky_adu=float(background.globalback), sky_rms_adu=float(background.globalrms),
              usable_fraction=usable_fraction, wcs=wcs_header.tostring().strip(),
              nx=science.shape[1], ny=science.shape[0],
              weight_rms_adu=float(np.median(error[~mask])),
              flux_gain_e_per_adu=gain, ccdzpt=float(row["ccdzpt"]),
              source_backend="SEP windowed centroid and matched detection",
              bunit=bunit or "ADU per DR11 data model")
    return result, qc


def fitsio_header_to_astropy(header):
    from astropy.io.fits import Header

    return Header((r["name"], r["value"], r.get("comment", "")) for r in header.records()
                  if r["name"] not in ("", "HISTORY", "COMMENT", "CONTINUE"))
