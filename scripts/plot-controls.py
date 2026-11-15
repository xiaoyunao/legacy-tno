#!/usr/bin/env python3
"""Regenerate the catalog-injection and null diagnostic from small summaries."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from scipy.stats import binomtest


def main():
    p=argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    args=p.parse_args()
    root=args.directory
    injection=json.loads((root/"injection_recovery_summary.json").read_text())
    null=json.loads((root/"null_test_summary.json").read_text())["controls"]
    observed=json.loads((root/"candidate_summary.json").read_text())
    manifest=json.loads((root/"run_manifest.json").read_text())
    fig, axes=plt.subplots(1,2,figsize=(10.8,4.4),layout="constrained",
                          gridspec_kw={"width_ratios":[1.65,1]})
    ax,bx=axes
    groups=[("all_points_present","All catalog points", "#276567", -.13),
            ("hypothetical_missingness","Noise and missingness", "#c77c28", .13)]
    for group,label,color,offset in groups:
        ax.plot([],[],ls="",marker="o",color=color,label=label)
        for j,(lo,hi) in enumerate(((30,60),(60,120),(120,300.01))):
            records=[v for v in injection["objects"] if v["group"]==group and
                     lo<=v["distance_au"]<hi and not v["search_truncated"]]
            n=len(records)
            if not n:
                continue
            k=sum(v["recovered"] for v in records)
            mean=k/n
            interval=binomtest(k,n).proportion_ci()
            ax.errorbar(j+offset,mean,yerr=[[max(0,mean-interval.low)],[max(0,interval.high-mean)]],
                        fmt="o",color=color,capsize=3)
            ax.annotate(f"{k}/{n}", (j+offset,mean),xytext=(4,5),textcoords="offset points",
                        color=color)
    ax.set(xticks=[0,1,2],xticklabels=["30–60","60–120","120–300"],
           xlabel="Heliocentric distance bin (au)",ylabel="Pure catalog recovery",
           ylim=(-.07,1.13),xlim=(-.45,2.46),title="Catalog injections | exact 95% intervals")
    ax.grid(axis="y",alpha=.2)
    ax.legend(loc="lower left",fontsize=9)
    values=[len(observed)]+[x["candidates"] for x in null]
    tags=["Observed"]+[f"Permutation {k+1}" for k in range(len(null))]
    bx.bar(tags,values,width=.55,color=["#276567"]+["#92999d"]*len(null))
    bx.set(ylabel="Accepted chains",ylim=(-.05,max(1,max(values))*1.2),title="Whole-night permutation")
    bx.yaxis.set_major_locator(MaxNLocator(integer=True))
    bx.grid(axis="y",alpha=.2)
    for j,value in enumerate(values):
        bx.annotate(str(value),(j,value),xytext=(0,6),textcoords="offset points",ha="center")
    for a in axes:
        a.spines[["top","right"]].set_visible(False)
    fig.suptitle(f"Legacy Surveys DR11 DECam | {manifest['run_id']}",fontsize=12)
    for ext in ("png","pdf"):
        fig.savefig(root/"figures"/f"injection_and_null.{ext}",dpi=175)


if __name__=="__main__":
    main()
