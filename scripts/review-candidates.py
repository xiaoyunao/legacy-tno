#!/usr/bin/env python3
"""Write whole-night holdouts and diagnostic CP image strips for accepted chains."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from astropy.wcs import WCS

from legacy_tno.catalog import cp_mask, fitsio_header_to_astropy, image_arrays
from legacy_tno.geometry import sky
from legacy_tno.orbit import Dynamics
from legacy_tno.pipeline import write_json
from legacy_tno.validate import leave_night_out


def main():
    p=argparse.ArgumentParser()
    p.add_argument("work",type=Path)
    p.add_argument("run")
    p.add_argument("--all", action="store_true", help="Inspect every unresolved chain")
    p.add_argument("--candidate", action="append", help="Inspect a specific candidate; may be repeated")
    args=p.parse_args()
    out=args.work/"runs"/args.run
    record=json.loads((out/"run_manifest.json").read_text())
    root=Path(record["config"]["image_root"])
    blind=json.loads((out/"blind_candidates.json").read_text())
    valid=json.loads((out/"candidate_summary.json").read_text())
    target_ids = (set(args.candidate) if args.candidate else
                  {v["candidate_id"] for v in valid if v["status"]=="known_status_unresolved"})
    index=np.load(out/"exposures.npy",allow_pickle=False)
    by_ccd={(int(row["expnum"]),str(row["ccdname"]).strip()):row for row in index}
    with np.load(out/"classified.npz",allow_pickle=False) as data:
        table,t,o=[data[n] for n in ("detections","tdb","observer")]
    model=Dynamics(t.min(),t.max(),str(args.work/"inputs"/"de440s.bsp"))
    products=[]
    fig_root=out/"figures"
    fig_root.mkdir(exist_ok=True)
    unresolved = [b for b in blind if b["candidate_id"] in target_ids]
    for source in unresolved if args.all or args.candidate else unresolved[:3]:
        ident=source["candidate_id"]
        members=np.asarray(source["members"],dtype=int)
        source["members"]=members
        source["initial_state"]=np.asarray(source["initial_state"])
        held=leave_night_out(source,table,t,o,model,config=record["config"])
        predicted = dict(zip(members, np.asarray(source["fitted_directions"]), strict=True))
        order=members[np.argsort(t[members])]
        nights=np.unique(table["night"][order])
        picks=[order[np.flatnonzero(table["night"][order]==night)[0]] for night in nights]
        fig,axes=plt.subplots(2,len(picks),figsize=(3.1*len(picks),6),squeeze=False)
        inspected=[]
        for ax, bx, j in zip(axes[0], axes[1], picks):
            det=table[j]
            row=by_ccd[int(det["expnum"]),str(det["ccdname"])]
            (im,weight,dq),header,primaries=image_arrays(
                root/str(row["image_filename"]).strip(),int(row["image_hdu"]))
            x,y=round(float(det["x_pix"])),round(float(det["y_pix"]))
            radius=17
            x1,x2=max(0,x-radius),min(im.shape[1],x+radius+1)
            y1,y2=max(0,y-radius),min(im.shape[0],y+radius+1)
            image=im[y1:y2,x1:x2].astype(float)
            a,b=np.nanpercentile(image,(8,99))
            ax.imshow(image,origin="lower",cmap="gray",vmin=a,vmax=b)
            xc,yc=float(det["x_pix"])-x1,float(det["y_pix"])-y1
            ax.add_patch(plt.Circle((xc,yc),4.4,fill=False,edgecolor="#18cdae",linewidth=.95))
            wcs = WCS(fitsio_header_to_astropy(header), relax=True)
            # Apply the astrometric residual in the CP pixel system, retaining the SEP tile offset.
            calc_x, calc_y = wcs.all_world2pix(*sky(predicted[j]),0,quiet=True)
            measured_x, measured_y = wcs.all_world2pix(det["ra_deg"],det["dec_deg"],0,quiet=True)
            ax.scatter([xc+calc_x-measured_x],[yc+calc_y-measured_y],marker="+",color="#fdb863",s=44)
            ax.set_title(f'MJD {det["mjd_mid_utc"]:.3f} · {det["band"]}\n'
                         f'SNR {det["snr"]:.1f} · DQ {int(dq[y,x])}',fontsize=10)
            ax.set_axis_off()
            tile_weight = weight[y1:y2,x1:x2]
            tile_dq = dq[y1:y2,x1:x2]
            bad = cp_mask(tile_dq, tile_weight, image, primaries[2]["PLVER"])
            bx.imshow(np.where(bad, np.nan, tile_weight), origin="lower", cmap="viridis")
            bx.imshow(np.ma.masked_where(~bad, bad), origin="lower", cmap="Reds", alpha=.65, vmin=0, vmax=1)
            bx.add_patch(plt.Circle((xc,yc),4.4,fill=False,edgecolor="#18cdae",linewidth=.95))
            bx.set_title("Weight and invalid pixels",fontsize=9)
            bx.set_axis_off()
            yy, xx = np.indices(image.shape)
            center = np.hypot(xx-xc, yy-yc)<=4.4
            background = image[~center & ~bad]
            sky_level = np.nanmedian(background) if len(background) else np.nan
            scatter = 1.4826*np.nanmedian(np.abs(background-sky_level)) if len(background) else np.nan
            inspected.append(dict(utc_mjd=det["mjd_mid_utc"],band=det["band"],
                                  catalog_snr=det["snr"],dq_center=int(dq[y,x]),
                                  central_invalid_fraction=float(np.mean(bad[center])),
                                  sky_mad_adu=float(scatter) if np.isfinite(scatter) else None))
        fig.suptitle(f"{record['run_id']} | {ident} · one CP frame per observing night",fontsize=12)
        fig.tight_layout()
        for ext in ("png","pdf"):
            fig.savefig(fig_root/f"candidate_stamps_{ident}.{ext}",dpi=170)
        plt.close(fig)
        products.append(dict(candidate_id=ident,holdouts=held,stamps=inspected,
                             review_status="CP cutout montage generated", image_status="review_context_only"))
    write_json(out/"candidate_review.json",products)
    print(f"Generated review products for {len(products)} unresolved chains")


if __name__=="__main__":
    main()
