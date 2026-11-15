#!/usr/bin/env python3
"""Use independent Horizons ephemerides and pixel photometry to diagnose blank matches."""
import argparse
import json
from pathlib import Path

import numpy as np
import sep
from astropy.io.fits import Header
from astropy.wcs import WCS

from legacy_tno.catalog import cp_mask, image_arrays
from legacy_tno.geometry import ARCSEC, angular_residual, sky, unit
from legacy_tno.orbit import Dynamics, observatory
from legacy_tno.pipeline import write_json
from legacy_tno.profile import IMAGE_ROOT
from legacy_tno.select import DES_EPOCH_TDB, des_orbits, evaluate_footprint


def diagnostic(work, run):
    out=work/"runs"/run
    qcs=json.loads((out/"ccd_audit.json").read_text())
    by_ccd={(r["expnum"],r["ccdname"]):r for r in qcs if "wcs" in r and "exclusion" not in r["astrometry"]}
    exposure=np.load(out/"exposures.npy",mmap_mode="r",allow_pickle=False)
    with np.load(out/"classified.npz",allow_pickle=False) as saved:
        catalog, classes=saved["detections"],saved["reasons"]
    output=[]
    lookup=dict((name,(state,mag)) for name,state,mag in des_orbits(work/"inputs"/"des-y6-tno.fits"))
    k=str(work/"inputs"/"de440s.bsp")
    for target,hfile in (("2013 RD124","horizons-rd124.json"),("2013 RQ157","horizons-rq157.json")):
        raw=json.loads((work/"inputs"/hfile).read_text())
        eph=np.asarray(raw["jd_ra_dec"],dtype=float)
        mjd=eph[:,0]-2400000.5
        t,o=observatory(mjd,k)
        model=Dynamics(min(t.min(),DES_EPOCH_TDB),max(t.max(),DES_EPOCH_TDB),k)
        predicted=model.apparent(lookup[target][0],DES_EPOCH_TDB,t,o)
        angles=unit(eph[:,1],eph[:,2])
        disagreement=angular_residual(predicted,angles)
        comparisons=[]
        for epoch in (57387.5,57388.0,57388.5):
            residual=angular_residual(model.apparent(lookup[target][0],epoch,t,o),angles)
            comparisons.append(dict(epoch_tdb_mjd=epoch,rms_arcsec=np.sqrt(np.mean(residual**2)),
                                    residuals_arcsec=residual))
        rows=[]
        for e,vec in zip(mjd,angles):
            near=exposure[np.abs(exposure["mjd_obs"]+exposure["exptime"]/(2*86400)-e)<2/86400]
            near=near[evaluate_footprint(near,sky(vec),pad_px=18)]
            for c in near:
                key=int(c["expnum"]),str(c["ccdname"]).strip()
                ccd=by_ccd.get(key)
                if ccd is None:
                    continue
                x_ra,x_dec=sky(vec)
                ar,ad=ccd["astrometry"]["offset_arcsec"]
                cal_ra=x_ra-ar/(3600*np.cos(np.deg2rad(x_dec)))
                cal_dec=x_dec-ad/3600
                wcs=WCS(Header.fromstring(ccd["wcs"]))
                x,y=map(float,wcs.all_world2pix(cal_ra,cal_dec,0))
                if not (0<=x<ccd["nx"] and 0<=y<ccd["ny"]):
                    continue
                d=np.flatnonzero((catalog["expnum"]==key[0]) & (catalog["ccdname"]==key[1]))
                seps=ARCSEC*np.linalg.norm(unit(catalog["ra_deg"][d],catalog["dec_deg"][d])-vec,axis=1)
                near_j=np.argmin(seps) if len(seps) else None
                matched_class=classes[d[near_j]] if near_j is not None else None
                match_sep=float(seps[near_j]) if near_j is not None else None
                match_snr=float(catalog["snr"][d[near_j]]) if near_j is not None else None
                delta=dict(expnum=key[0],ccd=key[1],mjd=e,band=ccd["band"],nearest_sep_arcsec=match_sep,
                           nearest_snr=match_snr,nearest_class=matched_class)
                (image,weight,dq), header, primaries=image_arrays(IMAGE_ROOT/str(c["image_filename"]).strip(),
                                                                  int(c["image_hdu"]))
                sci=np.ascontiguousarray(image,dtype=np.float32)
                weight=np.ascontiguousarray(weight,dtype=np.float32)
                mask=cp_mask(dq,weight,sci,primaries[2]["PLVER"])
                sci[mask]=0
                bkg=sep.Background(sci,mask=mask,bw=64,bh=64)
                bkg.subfrom(sci)
                sci[mask]=0
                error=np.full(sci.shape,1e10,dtype=np.float32)
                np.divide(1,np.sqrt(np.maximum(weight,0)),out=error,where=~mask)
                radius=float(c["fwhm"])*1.15
                xy=(np.array([x]),np.array([y]))
                flux, var, flags=sep.sum_circle(sci,*xy,radius,err=error,
                                                 gain=ccd["flux_gain_e_per_adu"],mask=mask,subpix=3)
                delta.update(forced_aperture_snr=float(flux[0]/var[0]) if var[0]>0 else None,
                             mask_at_center=bool(mask[int(np.floor(y)),int(np.floor(x))]),
                             extraction_forced_flags=int(flags[0]))
                rows.append(delta)
        output.append(dict(target=target,ephemeris_source="JPL Horizons W84 astrometric ICRF",
                           des_horizons_rms_arcsec=np.sqrt(np.mean(disagreement**2)),
                           des_horizons_max_sep_arcsec=np.max(np.linalg.norm(disagreement,axis=1)),
                           matched_within_1p25_arcsec=sum(r["nearest_sep_arcsec"] is not None and
                                                       r["nearest_sep_arcsec"]<1.25 for r in rows),
                           epoch_comparison=comparisons, ccds=rows))
    write_json(out/"known_miss_diagnostic.json",output)
    print(json.dumps([dict(target=r["target"],rms=float(r["des_horizons_rms_arcsec"]),
                           matched=r["matched_within_1p25_arcsec"]) for r in output]))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("work",type=Path)
    p.add_argument("run")
    args=p.parse_args()
    diagnostic(args.work,args.run)
