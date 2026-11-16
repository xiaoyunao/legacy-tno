"""Per-exposure Gaia calibration and recoverable catalog-level static classification."""
from functools import lru_cache
from pathlib import Path
import re

import fitsio
import numpy as np
from astropy import units as u
from astropy_healpix import HEALPix
from scipy.spatial import cKDTree

from .geometry import ARCSEC, angular_residual, sky, unit
from .nsc_adapter import FATAL_EXTRACTOR_FLAGS, PRODUCT

QUALITY = 1
ASTROM = 2
GAIA = 4
PERSISTENT = 8
NEAR_STATIC = 16
EXCESS = 32
LOW_SNR = 64
ARTIFACT = 128

GAIA_COLUMNS = ["source_id","ra","dec","pmra","pmdec","parallax","ref_epoch",
                "phot_g_mean_mag","ruwe"]
SWEEP_COLUMNS = ["ra","dec","type","flux_g","flux_r","flux_i","flux_z",
                 "flux_ivar_g","flux_ivar_r","flux_ivar_i","flux_ivar_z"]


def chord(arcsec):
    return 2*np.sin(arcsec/(2*ARCSEC))


def link_classes(cfg):
    return (["transient_clean", "ambiguous_static_match"]
            if cfg["link"].get("include_ambiguous_static", False) else ["transient_clean"])


def link_mask(table, reasons, cfg):
    minimum = cfg["link"].get("min_catalog_snr", cfg["filter"]["search_snr"])
    return np.isin(reasons, link_classes(cfg)) & (table["snr"] >= minimum)


@lru_cache(maxsize=12)
def gaia_chunk(root, index):
    path = Path(root) / f"healpix-{index:05d}.fits"
    table = fitsio.read(path, columns=GAIA_COLUMNS, lower=True)
    return table


def gaia_field(root, field):
    # NERSC Gaia EDR3 HEALPix shards use nside=32, NESTED.
    hp = HEALPix(nside=32, order="nested")
    indices = hp.cone_search_lonlat(field["ra_deg"]*u.deg, field["dec_deg"]*u.deg,
                                    (field["read_radius_deg"]+.45)*u.deg)
    result = []
    for index in indices:
        table = gaia_chunk(root, int(index))
        pixel = hp.lonlat_to_healpix(table["ra"][::100]*u.deg, table["dec"][::100]*u.deg)
        if len(pixel) and np.mean(pixel==index) < .95:
            raise ValueError(f"Gaia shard {index} fails nested HEALPix verification")
        use = np.linalg.norm(unit(table["ra"], table["dec"]) -
                             unit(field["ra_deg"],field["dec_deg"]), axis=1)
        result.append(table[use <= chord((field["read_radius_deg"]+.46)*3600)])
    return np.concatenate(result)


def gaia_directions(table, mjd_tdb, observer):
    p = unit(table["ra"], table["dec"])
    east = unit(table["ra"]+90, np.zeros(len(table)))
    north = unit(table["ra"]+180, 90-table["dec"])
    elapsed = (mjd_tdb-51544.5)/365.25 + (2000-table["ref_epoch"])
    pm = np.nan_to_num(table["pmra"])[:,None]*east + np.nan_to_num(table["pmdec"])[:,None]*north
    parallax = np.maximum(0, np.nan_to_num(table["parallax"]))
    direction = p + (pm*elapsed[:, None] - parallax[:, None]*observer)/(1000*ARCSEC)
    return direction/np.linalg.norm(direction, axis=1)[:, None]


def calibrate(table, gaia, mjd_tdb, observer, cfg, *, apply_offset=True):
    source = unit(table["ra_deg"], table["dec_deg"])
    ref = gaia_directions(gaia, mjd_tdb, observer)
    tree = cKDTree(ref)
    dist, idx = tree.query(source, distance_upper_bound=chord(cfg["gaia_calibration_radius_arcsec"]))
    good_reference = np.isfinite(dist) & (table["snr"] > 18) & (table["mask_fraction"] < .03)
    if not apply_offset:
        good_reference &= (table["extractor_flags"] & FATAL_EXTRACTOR_FLAGS) == 0
    i = np.flatnonzero(good_reference)
    i = i[(gaia["phot_g_mean_mag"][idx[i]] > 15.0) & (gaia["phot_g_mean_mag"][idx[i]] < 20.5)]
    residual = angular_residual(ref[idx[i]], source[i])
    if len(i) < cfg["min_gaia_matches"]:
        return None, dict(n_gaia=len(i), exclusion="insufficient Gaia references"), []
    offset = np.median(residual, axis=0)
    scatter = 1.4826*np.median(np.abs(residual-offset), axis=0)
    good = np.linalg.norm(residual-offset, axis=1) < min(1, max(.18, 4*max(scatter)))
    if np.count_nonzero(good) < cfg["min_gaia_matches"]:
        return None, dict(n_gaia=int(np.count_nonzero(good)), exclusion="Gaia clipping"), []
    # Measure a single robust offset and retain x/y residuals for trend diagnostics.
    offset = np.median(residual[good], axis=0)
    centered = residual[good]-offset
    scatter = 1.4826*np.median(np.abs(centered), axis=0)
    details = dict(n_gaia=int(np.count_nonzero(good)), offset_arcsec=offset.tolist(),
                   mad_arcsec=scatter.tolist(), offset_applied=apply_offset)
    if max(scatter) > cfg["max_astrom_scatter_arcsec"]:
        details["exclusion"] = "Gaia scatter"
        return None, details, []
    aligned = table.copy()
    if apply_offset:
        aligned["ra_deg"] = (table["ra_deg"] + offset[0] /
                            (3600*np.cos(np.deg2rad(table["dec_deg"])))) % 360
        aligned["dec_deg"] = table["dec_deg"] + offset[1]/3600
    aligned["sigma_arcsec"] = np.sqrt(aligned["sigma_arcsec"]**2 +
                                     max(cfg["astrom_floor_arcsec"], float(max(scatter)))**2)
    diagnostics = np.c_[table["x_pix"][i[good]], table["y_pix"][i[good]],
                        table["mag_ab"][i[good]], centered]
    return aligned, details, diagnostics


def sweep_field(root, field):
    table = []
    center = unit(field["ra_deg"], field["dec_deg"])
    radius = field["read_radius_deg"] + .4
    for filename in sorted(Path(root).glob("sweep-*.fits")):
        parts = re.fullmatch(r"sweep-(\d+)([mp])(\d+)-(\d+)([mp])(\d+)\.fits", filename.name)
        if parts is None:
            continue
        a, s, b, c, t, d = parts.groups()
        a, b, c, d = int(a), int(b)*(-1 if s=="m" else 1), int(c), int(d)*(-1 if t=="m" else 1)
        right = c if c > a else c+360
        ra = field["ra_deg"] + 360*round(((a+right)/2-field["ra_deg"])/360)
        reaches = radius / max(.15, np.cos(np.deg2rad(abs(field["dec_deg"])+radius)))
        if ra < a-reaches or ra > right+reaches or field["dec_deg"] < b-radius or field["dec_deg"] > d+radius:
            continue
        rows = fitsio.read(filename, columns=SWEEP_COLUMNS, lower=True)
        match = np.linalg.norm(unit(rows["ra"], rows["dec"])-center, axis=1) < chord(radius*3600)
        table.append(rows[match])
    if not table:
        raise FileNotFoundError("No DR11 Sweep shards cover this pilot")
    return np.concatenate(table)


def classify(table, gaia, sweep, tdb, observers, cfg):
    p = unit(table["ra_deg"], table["dec_deg"])
    mask = np.zeros(len(table), dtype=np.uint16)
    faint = table["snr"] < cfg["search_snr"]
    nsc = table["processing_version"] == PRODUCT
    width = np.sqrt(table["a_pix"]*table["b_pix"])*2.35482*.262
    bad = ((width < cfg["min_fwhm_ratio"]*table["fwhm_arcsec"]) |
           (table["a_pix"] > cfg["max_axis_ratio"]*table["b_pix"]) |
           (table["edge_distance_pix"] < cfg["min_edge_pix"]) |
           (table["mask_fraction"] > cfg["max_mask_fraction"]) |
           (nsc & ((table["extractor_flags"] & FATAL_EXTRACTOR_FLAGS) != 0)))
    mask[faint] |= LOW_SNR
    mask[bad] |= ARTIFACT
    matched_source = np.full(len(table), -1, dtype=np.int64)
    gaia_sep = np.full(len(table), np.nan)
    for exp in np.unique(table["expnum"]):
        i = np.flatnonzero(table["expnum"] == exp)
        ref = gaia_directions(gaia, tdb[i[0]], observers[i[0]])
        dist, index = cKDTree(ref).query(p[i], distance_upper_bound=chord(cfg["ambiguous_radius_arcsec"]), k=2)
        good = np.isfinite(dist[:,0])
        hit = i[good]
        gaia_sep[hit] = 2*ARCSEC*np.arcsin(dist[good,0]/2)
        matched_source[hit] = gaia["source_id"][index[good,0]]
        threshold = np.clip(3*table["sigma_arcsec"][hit], .33, cfg["gaia_static_max_arcsec"])
        certain = (gaia_sep[hit] < threshold) & (dist[good,1] > 1.7*dist[good,0])
        mask[hit[certain]] |= GAIA
        mask[hit[~certain]] |= NEAR_STATIC
    deep = cKDTree(unit(sweep["ra"], sweep["dec"]))
    distance, deep_idx = deep.query(p, distance_upper_bound=chord(cfg["ambiguous_radius_arcsec"]))
    has_deep = np.isfinite(distance)
    excess = np.full(len(table), np.nan)
    for band in ("g","r","i","z"):
        # NSC AUTO and Sweep PSF fluxes require an empirical cross-calibration.
        i = np.flatnonzero((table["band"] == band) & has_deep & ~nsc)
        d = sweep[deep_idx[i]]
        is_psf = np.char.strip(d["type"].astype(str)) == "PSF"
        i, d = i[is_psf], d[is_psf]
        reference = d[f"flux_{band}"]
        invvar = d[f"flux_ivar_{band}"]
        available = invvar > 0
        i, reference, invvar = i[available], reference[available], invvar[available]
        noise = np.sqrt(table["flux_err"][i]**2 + 1/invvar +
                        (cfg["coadd_relative_floor"]*reference)**2)
        excess[i] = (table["flux"][i]-reference) / noise
    bright = excess >= cfg["excess_sigma"]
    mask[bright] |= EXCESS
    mask[bright] &= np.uint16(~np.uint16(GAIA))
    # Sets of detections around one fixed deep reference position cannot bridge by transitivity.
    persistent = np.flatnonzero(has_deep & (distance <= chord(cfg["persistent_radius_arcsec"])) & ~bad & ~faint)
    order = persistent[np.argsort(deep_idx[persistent])]
    for i in np.split(order, np.flatnonzero(np.diff(deep_idx[order]))+1):
        if (len(i) >= cfg["persistent_min_nights"] and
                len(np.unique(table["night"][i])) >= cfg["persistent_min_nights"] and
                np.ptp(table["mjd_mid_utc"][i]) >= cfg["persistent_min_span_days"]):
            mask[i[~bright[i]]] |= PERSISTENT
    mask[has_deep & ~bright & ((mask & (GAIA|PERSISTENT)) == 0)] |= NEAR_STATIC
    reason = np.full(len(table), "transient_clean", dtype="U23")
    reason[(mask & NEAR_STATIC) > 0] = "ambiguous_static_match"
    reason[(mask & (GAIA|PERSISTENT)) > 0] = "static_confident"
    reason[(mask & ARTIFACT) > 0] = "artifact_flagged"
    reason[(mask & LOW_SNR) > 0] = "quality_rejected"
    return reason, mask, matched_source, gaia_sep, excess
