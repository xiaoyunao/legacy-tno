"""Matplotlib figures with the measured DR11 pilot summaries."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from astropy.coordinates import SkyCoord
from astropy import units as u

from .nsc_adapter import PRODUCT


def read(out, filename):
    return json.loads((out/filename).read_text())


def plot(out: Path):
    figures = out/"figures"
    figures.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.dpi": 130, "axes.grid": True, "grid.alpha": .2,
                         "axes.titleweight":"medium", "pdf.fonttype": 42})
    exposure = read(out,"exposure_summary.json")
    label = f"Legacy Surveys DR11 DECam | {exposure['field']['id']}"
    field = exposure["field"]
    qc = read(out,"astrometry_photometry_qc.json")
    domain = read(out,"search_domain_summary.json")
    candidates = read(out,"candidate_summary.json")
    known = read(out,"known_recovery_summary.json")
    with np.load(out/"classified.npz",allow_pickle=False) as table:
        sources, reasons, gaia, sep, excess = (table[k] for k in
            ("detections","reasons","gaia_residual","gaia_sep_arcsec","excess"))
    nsc = sources["processing_version"] == PRODUCT
    photometry_label = ("NSC AUTO" if nsc.all() else "AUTO or aperture by product" if nsc.any() else "aperture")

    def save(name, fig):
        fig.suptitle(label, y=.997)
        fig.tight_layout()
        fig.savefig(figures/f"{name}.png",dpi=160,bbox_inches="tight")
        fig.savefig(figures/f"{name}.pdf",bbox_inches="tight")
        plt.close(fig)

    coverage = np.asarray(exposure["coverage"])
    center = SkyCoord(field["ra_deg"]*u.deg,field["dec_deg"]*u.deg).barycentrictrueecliptic
    longitude = center.lon.deg + (SkyCoord(coverage[:,0]*u.deg,coverage[:,1]*u.deg)
                               .barycentrictrueecliptic.lon.deg-center.lon.deg+180)%360-180
    latitude = SkyCoord(coverage[:,0]*u.deg,coverage[:,1]*u.deg).barycentrictrueecliptic.lat.deg
    fig, ax = plt.subplots(figsize=(7,5))
    chart = ax.scatter(longitude,latitude,c=coverage[:,2],s=4,cmap="viridis",rasterized=True)
    fig.colorbar(chart,label="Distinct CTIO nights")
    ax.set(xlabel="Ecliptic longitude (deg)", ylabel="Ecliptic latitude (deg)",
           title=f"CCD footprint union {exposure['read_area_deg2']:.2f} deg²")
    save("coverage_nights",fig)

    valid = [r for r in qc if "astrometry" in r and "exclusion" not in r["astrometry"]]
    times = np.unique([r["middle_mjd"] for r in valid])
    fig, (ax,bx) = plt.subplots(1,2,figsize=(10,4))
    for band in sorted({r["band"] for r in valid}):
        by_band = [r["middle_mjd"] for r in valid if r["band"]==band]
        ax.hist(by_band,bins=np.linspace(min(times)-1,max(times)+1,32),histtype="step",label=band)
    ax.legend(title="Filter")
    ax.set(xlabel="MJD (UTC)",ylabel="CCD count",title=f"{len(times)} exposures across {exposure['nights']} nights")
    gaps = np.diff(times)
    bx.hist(gaps[gaps>0],bins=np.geomspace(max(gaps[gaps>0].min()*.9,1e-6),
                                          gaps.max()*1.1,24),color="#2C6977")
    bx.set(xscale="log",xlabel="Times between exposures (days)",ylabel="Count")
    save("cadence",fig)

    fig, axes = plt.subplots(1,3,figsize=(12,4))
    for band in sorted(np.unique(sources["band"])):
        subset=sources[sources["band"]==band]
        axes[0].hist(subset["mag_ab"],bins=np.arange(15,26,.25),histtype="step",label=band)
    axes[0].legend(title="Band")
    axes[0].set(xlabel=f"AB magnitude ({photometry_label})",ylabel="Detections",yscale="log")
    axes[1].hist(sources["snr"],bins=np.geomspace(4,1500,36),color="#2C6977")
    axes[1].set(xlabel=f"Photometric SNR ({photometry_label})",ylabel="Detections",xscale="log",yscale="log")
    axes[2].hist([r["retained"] for r in qc if "retained" in r],bins=24,color="#2C6977")
    axes[2].set(xlabel="Retained sources per CP CCD",ylabel="CCD count")
    save("catalog_diagnostics",fig)

    fig, axes=plt.subplots(2,3,figsize=(11,6))
    for column,label_x in enumerate(("CCD x (pix)","CCD y (pix)",f"AB magnitude ({photometry_label})")):
        for j, label_y in enumerate(("Gaia − measured RA cos Dec (arcsec)","Gaia − measured Dec (arcsec)")):
            axes[j,column].hexbin(gaia[:,column],gaia[:,j+3],gridsize=36,mincnt=1,bins="log",cmap="viridis")
            axes[j,column].set(xlabel=label_x,ylabel=label_y)
    save("gaia_residuals",fig)

    fig, axes=plt.subplots(1,3,figsize=(13,4))
    unique,count = np.unique(reasons,return_counts=True)
    axes[0].barh([n.replace("_"," ") for n in unique],count,color="#2C6977")
    axes[0].set(xlabel="Detections",xscale="log")
    axes[1].hist(sep[np.isfinite(sep)],bins=25,color="#2C6977")
    axes[1].set(xlabel="Gaia separation (arcsec)",ylabel="Detections")
    finite=excess[np.isfinite(excess)]
    axes[2].hist(np.clip(finite,-15,15),bins=36,color="#2C6977")
    axes[2].set(xlabel="SEP aperture − Sweep PSF flux (σ), clipped",ylabel="Detections")
    if nsc.all():
        axes[2].text(.5, .5, "NSC AUTO flux excluded from this comparison",
                     transform=axes[2].transAxes, ha="center", va="center", wrap=True)
    save("static_classification",fig)

    fig,ax=plt.subplots(figsize=(8,4))
    labels=["A Geometry","B Raw","C Clean","D Linkable","E Blind","F Guided only"]
    values=list(known["counts"].values())
    ax.bar(labels,values,color=["#2C6977"]*5+["#b28c40"])
    for i,v in enumerate(values):
        ax.text(i,v+.025*max(1,max(values)),str(v),ha="center")
    ax.set(ylabel="DES validation objects",ylim=(0,max(1,max(values))*1.2))
    ax.tick_params(axis="x",rotation=15)
    save("known_recovery",fig)

    injection_file=out/"injection_recovery_summary.json"
    if injection_file.exists():
        injection=read(out,"injection_recovery_summary.json")
        fig,(ax,bx)=plt.subplots(1,2,figsize=(10,4))
        for group in sorted({r["group"] for r in injection["objects"]}):
            sample=[r for r in injection["objects"] if r["group"]==group and not r["search_truncated"]]
            for lo,hi in ((30,60),(60,120),(120,300)):
                cell=[r for r in sample if lo<=r["distance_au"]<hi]
                if cell:
                    k=sum(r["recovered"] for r in cell)
                    ax.scatter(np.sqrt(lo*hi),k/len(cell),label=group.replace("_"," ") if lo==30 else None)
                    ax.annotate(f"{k}/{len(cell)}",(np.sqrt(lo*hi),k/len(cell)),xytext=(4,4),
                                textcoords="offset points")
        ax.set(xlabel="Distance bin (au)",ylabel="Pure catalog recovery",xscale="log",ylim=(-.07,1.16))
        if ax.get_legend_handles_labels()[0]:
            ax.legend()
        null=read(out,"null_test_summary.json")["controls"]
        bx.bar(["Observed", "Permuted night"],[len(candidates), sum(r["candidates"] for r in null)],color="#2C6977")
        bx.set(ylabel="Accepted fits",title="Night permutation control")
        save("injection_and_null",fig)

    for known_object in read(out,"blind_known_plot_data.json")[:6]:
        ident = known_object["candidate_id"]
        ra,dec=np.asarray(known_object["ra_deg"]),np.asarray(known_object["dec_deg"])
        ra0, dec0=np.median(ra),np.median(dec)
        x=(ra-ra0+180)%360-180
        x*=3600*np.cos(np.deg2rad(dec0))
        y=(dec-dec0)*3600
        obs=np.asarray(known_object["mjd_tdb"])
        err=known_object["sigma_arcsec"]
        fig, (ax,bx) = plt.subplots(1,2,figsize=(11,4.4))
        raster=ax.scatter(x,y,c=obs,cmap="plasma",s=24)
        ax.errorbar(x,y,xerr=err,yerr=err,fmt="none",color="#566")
        order=np.argsort(obs)
        model_ra,model_dec=np.asarray(known_object["predicted_ra"]),np.asarray(known_object["predicted_dec"])
        ax.plot(((model_ra[order]-ra0+180)%360-180)*3600*np.cos(np.deg2rad(dec0)),
                (model_dec[order]-dec0)*3600,color="#566",lw=.7)
        fig.colorbar(raster,ax=ax,label="MJD (TDB)")
        ax.set(title=f"{known_object['target']} | {len(ra)} blind detections",
               xlabel="RA cos Dec offset (arcsec)",ylabel="Declination offset (arcsec)")
        for band in np.unique(known_object["band"]):
            sel=np.asarray(known_object["band"])==band
            bx.errorbar(obs[sel], np.asarray(known_object["magnitude"])[sel],
                        yerr=np.asarray(known_object["mag_err"])[sel],fmt="o",label=band)
        bx.invert_yaxis()
        bx.legend(title="Filter")
        bx.set(xlabel="MJD (TDB)",ylabel="AB aperture magnitude")
        save(f"known_track_{ident}",fig)

        fig,(ax,bx)=plt.subplots(1,2,figsize=(10,4))
        offsets=np.array(known_object["offsets_arcsec"])
        for i,component in enumerate(("RA cos Dec","Dec")):
            ax.errorbar(obs,offsets[:,i],yerr=err,fmt="o",label=component)
            for night in known_object["held_nights"]:
                if "offsets_arcsec" in night:
                    bx.scatter(night["mjd"],np.asarray(night["offsets_arcsec"])[:,i],s=10)
        ax.legend()
        ax.set(xlabel="MJD (TDB)",ylabel="Model − observed (arcsec)")
        bx.set(xlabel="Held-night MJD (TDB)",ylabel="Prediction − observed (arcsec)")
        save(f"known_residuals_{ident}",fig)

    fig,(ax,bx)=plt.subplots(1,2,figsize=(10,4))
    kinds=["Known blind","Contaminated","Identity unresolved"]
    values=[sum(r["status"]==key for r in candidates) for key in
            ("known_recovered_blind","contaminated_or_ambiguous","known_status_unresolved")]
    ax.bar(kinds,values,color="#2C6977")
    ax.tick_params(axis="x",rotation=15)
    ax.set(ylabel="Accepted candidate chains",ylim=(0,max(1,max(values))*1.15))
    pairs=domain["pair_counts"]
    phases=["pairs","triplets","chains"]
    values=[pairs.get(p,0) for p in phases]
    bx.bar(phases,values,color="#2C6977")
    bx.set(ylabel="Enumerated combinations",yscale="symlog",title=f"{len(domain['truncated'])} truncated bins")
    save("candidates_and_association",fig)
