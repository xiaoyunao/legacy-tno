#!/usr/bin/env python3
"""Render timing, verified candidates and coverage opportunities from small results."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np


def read(root, name):
    path=root/(name+".json")
    return json.loads(path.read_text()) if path.exists() else None


def render(root):
    m=read(root,"run_manifest")
    s=read(root,"exposure_summary")
    if m is None or s is None:
        return
    fig_root=root/"figures"
    fig_root.mkdir(exist_ok=True)
    plt.rcParams.update({"axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,
                         "grid.alpha":.20,"pdf.fonttype":42,"font.size":10})
    name="DR11 DECam | "+m["run_id"]

    def save(fig, filename):
        fig.suptitle(name,fontsize=12)
        for ext in ("png","pdf"):
            fig.savefig(fig_root/f"{filename}.{ext}",dpi=170)
        plt.close(fig)

    time=read(root,"performance_summary")
    stages=m.get("stages",{})
    values=[v["seconds"] for v in stages.values() if v.get("seconds") is not None]
    phases=[k.replace("_"," ") for k,v in stages.items() if v.get("seconds") is not None]
    if time and time.get("wall_seconds") and values:
        remainder=max(0,time["wall_seconds"]-sum(values))
        if remainder>1:
            phases.append("identity, controls and other")
            values.append(remainder)
    if values:
        fig,ax=plt.subplots(figsize=(8,3.2),layout="constrained")
        ax.barh(phases,np.asarray(values)/60,color="#326d72")
        ax.invert_yaxis()
        for i,val in enumerate(values):
            ax.text(val/60,i,f"  {val/60:.2f} min",va="center")
        ax.set(xlabel="Elapsed minutes",xlim=(0,max(values)/60*1.25))
        save(fig,"wall_time")

    known=read(root,"known_recovery_summary")
    tests=read(root,"injection_recovery_summary")
    if known is not None or tests is not None:
        fig,axes=plt.subplots(1,2,figsize=(10,4.4),layout="constrained")
        a,b=axes
        rows=known["objects"] if known else []
        injections=tests["objects"] if tests else []
        if rows:
            x=[r["geometry_nights"] for r in rows]
            y=[r["A_geometry_exposures"] for r in rows]
            color=["#2d766f" if r["E_blind"] else "#ad7a44" for r in rows]
            a.scatter(x,y,c=color)
            for r in rows[:8]:
                a.annotate(r["target"], (r["geometry_nights"],r["A_geometry_exposures"]),
                           xytext=(3,4),textcoords="offset points",fontsize=8)
        a.set(xlabel="Independent nights intersecting CCDs",ylabel="Intersecting exposures",
              title=f"DES validation catalog | {len(rows)} covered")
        a.xaxis.set_major_locator(MaxNLocator(integer=True))
        a.yaxis.set_major_locator(MaxNLocator(integer=True))
        if injections:
            b.scatter([r["geometry_arc_days"] for r in injections],
                      [r["geometry_exposures"] for r in injections],s=16,alpha=.7,
                      c=["#2d766f" if r["recovered"] else "#ad7a44" for r in injections])
        b.set(xlabel="Geometric arc duration (days)",ylabel="Intersecting exposures",
              title=f"Simulated tracks | {len(injections)} catalog eligible")
        b.yaxis.set_major_locator(MaxNLocator(integer=True))
        save(fig,"track_opportunities")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("root",type=Path,nargs="+")
    for field in p.parse_args().root:
        render(field)
