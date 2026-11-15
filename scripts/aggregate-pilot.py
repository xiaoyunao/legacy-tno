#!/usr/bin/env python3
"""Export bounded scientific diagnostics from the large intermediate tables."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from legacy_tno.geometry import night_id, unit
from legacy_tno.link import season_labels
from legacy_tno.pipeline import write_json
from legacy_tno.select import DEPTH_BITS, evaluate_footprint


def load(out, name):
    return json.loads((out/name).read_text())


def histogram(values, bins):
    count, edges = np.histogram(values, bins=bins)
    return dict(edges=edges, count=count)


def injection_bins(injection):
    axes = {
        "distance_au": [30, 60, 120, 300.0001],
        "mag_r": [19, 21, 22, 23, 24],
        "geometry_nights": [4, 6, 10, 15, 100],
        "geometry_arc_days": [7, 20, 50, 90, 181],
        "e": [0,.3,.6,.8,1],
    }
    result = []
    objects = injection["objects"]
    for group in sorted({r["group"] for r in objects}):
        for key, boundaries in axes.items():
            for lo, hi in zip(boundaries, boundaries[1:]):
                rows = [r for r in objects if r["group"]==group and lo<=r[key]<hi]
                complete = [r for r in rows if not r["search_truncated"]]
                matched = sum(r["recovered"] for r in complete)
                ci = binomtest(matched, len(complete)).proportion_ci() if complete else (None,None)
                result.append(dict(group=group, variable=key, lo=lo, hi=hi,
                                   n=len(complete), successes=matched,
                                   excluded_truncated=len(rows)-len(complete),
                                   fraction=matched/len(complete) if complete else None,
                                   confidence_95=list(ci)))
    return result


def metadata_diagnostics(out, work, exposure, qc, manifest):
    from scipy.spatial import cKDTree

    table = np.load(out/"exposures.npy", allow_pickle=False, mmap_mode="r")
    valid = {(r["expnum"],r["ccdname"]):r for r in qc if "astrometry" in r and "exclusion" not in r["astrometry"]}
    use = np.array([(int(r["expnum"]),str(r["ccdname"]).strip()) in valid for r in table])
    table = table[use]
    audit = np.load(work/"smoke"/"annotated.npy", allow_pickle=False, mmap_mode="r")
    rows = audit[np.isin(audit["expnum"], np.unique(table["expnum"]))]
    depth = {(int(r["expnum"]),str(r["ccdname"]).strip()): float(r["psfdepth"]) for r in rows}
    grid = np.array(exposure["coverage"])
    footprint = cKDTree(unit(grid[:,0],grid[:,1]))
    nights = night_id(table["mjd_obs"])
    seasons = season_labels(nights,manifest["config"]["link"]["season_gap_days"])
    values = np.full(len(grid),-np.inf)
    cover_seasons = np.zeros((len(grid), len(np.unique(seasons))),dtype=bool)
    payload = []
    for row,season in zip(table,seasons):
        key = (int(row["expnum"]),str(row["ccdname"]).strip())
        coords = np.asarray(footprint.query_ball_point(unit(row["ra"],row["dec"]),.004),dtype=int)
        matched = coords[evaluate_footprint(row,(grid[coords,0],grid[coords,1]))]
        cover_seasons[matched,season] = True
        mag = depth.get(key,0)
        if 10 < mag < 30:
            values[matched] = np.maximum(values[matched],mag)
        trace = valid[key]
        payload.append(dict(expnum=key[0],ccd=key[1],band=str(row["filter"]).strip(),
                            mjd=trace["middle_mjd"], n_detection=trace["retained"],
                            gaia_calibration_stars=trace["astrometry"]["n_gaia"],
                            gaia_calibration_fraction=trace["astrometry"]["n_gaia"]/max(1,trace["retained"]),
                            psfdepth_5sigma_mag=mag if 10 < mag < 30 else None,
                            season=int(season),depth_only_cuts=int(row["ccd_cuts"]&DEPTH_BITS)))
    return dict(ccds=payload,seasons=int(len(np.unique(seasons))),
                depth_only_ccds=int(np.count_nonzero(table["ccd_cuts"]&DEPTH_BITS)),
                depth_only_nights=int(len(np.unique(nights[(table["ccd_cuts"]&DEPTH_BITS)!=0]))),
                grid=np.c_[grid[:,:3], np.sum(cover_seasons,axis=1), np.where(np.isfinite(values),values,np.nan)])


def metadata_figures(out, exposure, diagnostics):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from astropy.coordinates import SkyCoord
    from astropy import units as u
    fig_root=out/"figures"
    fig_root.mkdir(exist_ok=True)
    sample=diagnostics["ccds"]
    grid=diagnostics["grid"]
    ecliptic=SkyCoord(grid[:,0]*u.deg,grid[:,1]*u.deg).barycentrictrueecliptic
    longitude = ecliptic.lon.deg
    center = SkyCoord(exposure["field"]["ra_deg"]*u.deg,exposure["field"]["dec_deg"]*u.deg).barycentrictrueecliptic.lon.deg
    longitude = center+(longitude-center+180)%360-180
    title="DR11 DECam | "+exposure["field"]["id"]
    fig, axes=plt.subplots(1,3,figsize=(13,4),layout="constrained")
    for j,(ax,key) in enumerate(zip(axes,("Observing nights","Seasons","Deepest single-CCD 5σ PSF depth (AB mag)"))):
        vals=grid[:,j+2]
        good=np.isfinite(vals)
        c=ax.scatter(longitude[good],ecliptic.lat.deg[good],c=vals[good],s=3,rasterized=True,cmap="viridis")
        ax.set(xlabel="Ecliptic longitude (deg)",ylabel="Ecliptic latitude (deg)")
        fig.colorbar(c,ax=ax,label=key)
    fig.suptitle(title)
    for ext in ("png","pdf"):
        fig.savefig(fig_root/f"coverage_depth_seasons.{ext}",dpi=170)
    plt.close(fig)
    fig, axes=plt.subplots(1,2,figsize=(9,4),layout="constrained")
    for band in sorted({r["band"] for r in sample}):
        rows=[r for r in sample if r["band"]==band and r["psfdepth_5sigma_mag"] is not None]
        if rows:
            x=[r["psfdepth_5sigma_mag"] for r in rows]
            axes[0].scatter(x,[r["n_detection"] for r in rows],label=band,s=5,alpha=.6)
            axes[1].scatter(x,[r["gaia_calibration_fraction"] for r in rows],label=band,s=5,alpha=.6)
    axes[0].set(xlabel="Annotated single-CCD 5σ PSF depth (AB mag)",ylabel="SEP catalog source count")
    axes[1].set(xlabel="Annotated single-CCD 5σ PSF depth (AB mag)",ylabel="Fraction used in Gaia calibration")
    if axes[0].get_legend_handles_labels()[0]:
        axes[0].legend(title="Filter")
    fig.suptitle(title)
    for ext in ("png","pdf"):
        fig.savefig(fig_root/f"catalog_depth.{ext}",dpi=170)
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("run",type=Path)
    parser.add_argument("--work",type=Path,required=True)
    args=parser.parse_args()
    out=args.run
    manifest=load(out,"run_manifest.json")
    stage_counts=manifest["stages"]
    write_json(out/"stage_counts.json",stage_counts)
    write_json(out/"performance_summary.json",dict(run=manifest["run_id"],
                    scope="main-process RSS in KiB; .batch MaxRSS in Slurm accounting",
                    wall_seconds=manifest.get("wall_seconds"), max_rss_kib=manifest.get("max_rss_kib"),
                    stages={k:v.get("seconds") for k,v in stage_counts.items()},
                    disk_bytes=sum(p.stat().st_size for p in out.rglob("*") if p.is_file())))
    if (out/"injection_recovery_summary.json").exists():
        inj = load(out,"injection_recovery_summary.json")
        inj["recovery_bins"] = injection_bins(inj)
        write_json(out/"injection_recovery_summary.json",inj)
    if not (out/"classified.npz").exists():
        return
    with np.load(out/"classified.npz",allow_pickle=False) as data:
        detections=data["detections"]
        reasons=data["reasons"]
        residual=data["gaia_residual"]
        sep=data["gaia_sep_arcsec"]
        flux=data["excess"]
    product=dict(
        source_magnitude_by_band={band:histogram(detections["mag_ab"][detections["band"]==band],
                                               np.arange(14,27,.2)) for band in np.unique(detections["band"])},
        aperture_snr=histogram(detections["snr"],np.geomspace(4,1500,48)),
        gaia_separation=histogram(sep[np.isfinite(sep)],np.linspace(0,1.5,41)),
        matched_psf_excess=histogram(np.clip(flux[np.isfinite(flux)],-15,15),np.linspace(-15,15,41)),
        classes=dict(Counter(reasons)),
        n_gaia=int(np.count_nonzero(np.isfinite(sep))),
        n_total=len(detections))
    for i, (name, bins) in enumerate((("x_pix",np.linspace(0,2048,37)),
                         ("y_pix",np.linspace(0,4096,37)),("mag",np.linspace(15,23,37)))):
        for j, coordinate in enumerate(("ra_cosdec","dec")):
            count, xedge, yedge = np.histogram2d(residual[:,i],residual[:,3+j],
                                               bins=(bins,np.linspace(-1,1,41)))
            product[f"gaia_by_{name}_{coordinate}"] = dict(count=count.astype(int),x_edges=xedge,y_edges=yedge)
    exposure=load(out,"exposure_summary.json")
    metadata=metadata_diagnostics(out,args.work,exposure,load(out,"astrometry_photometry_qc.json"),manifest)
    metadata_figures(out,exposure,metadata)
    # Keep JSON strict for downstream tools.
    grid=metadata.pop("grid")
    metadata["grid"]=[[float(x) if np.isfinite(x) else None for x in row] for row in grid]
    product["depth_season_coverage"]=metadata
    write_json(out/"plot_data.json",product)


if __name__=="__main__":
    main()
