#!/usr/bin/env python3
"""Verify the delivered small products and build a cross-run manifest."""
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import struct

PROJECT=Path(__file__).resolve().parents[1]
RESULTS=PROJECT/"results"/"v1"


def read(folder, key, default=None):
    path=folder/(key+".json")
    return json.loads(path.read_text()) if path.exists() else default


def main():
    with (PROJECT/"logs"/"slurm-accounting.psv").open() as f:
        accounting={r["JobID"]:r for r in csv.DictReader(f,delimiter="|")}
    runs=[]
    recovered=set()
    for d in sorted(RESULTS.iterdir()):
        if not d.is_dir():
            continue
        manifest=read(d,"run_manifest")
        if not manifest:
            continue
        name=d.name
        domain=read(d,"search_domain_summary",{})
        candidates=read(d,"candidate_summary",[])
        truth=read(d,"known_recovery_summary",{"counts":{}})
        tracks=read(d,"blind_known_plot_data",[])
        counts=Counter(r["status"] for r in candidates)
        for r in candidates:
            if r["status"]=="known_recovered_blind":
                assert r["matched_detections"]==r["n_det"]
                assert r["matched_nights"]==r["n_night"]
                track=next(t for t in tracks if t["candidate_id"]==r["candidate_id"])
                assert len(track["ra_deg"])==r["n_det"]
                for part in ("track","residuals"):
                    for ext in ("png","pdf"):
                        assert (d/"figures"/f"known_{part}_{r['candidate_id']}.{ext}").is_file()
                recovered.add(r["catalog_association"])
        job=str(manifest["slurm_job"])
        assert job in accounting, (name,job)
        event=accounting[job]
        assert event["State"] not in ("RUNNING","PENDING","COMPLETING"), event
        correct=read(d,"identity_revision",{})
        phases=[key for key in (
            "exposure_summary","search_domain_summary","candidate_summary","known_recovery_summary",
            "injection_recovery_summary","null_test_summary") if (d/(key+".json")).exists()]
        runs.append(dict(label=name,run_id=manifest["run_id"],run_code_commit=manifest["run_code_commit"],
                         slurm_job=job,slurm_state=event["State"],exit_code=event["ExitCode"],
                         pipeline_status=manifest["status"],remote_path=manifest["path"],
                         truncated_bins=len(domain.get("truncated",[])),identity_revision=correct,
                         counts=counts,des_validation_counts=truth["counts"],finished_products=phases))
    nfiles=0
    for path in RESULTS.rglob("*"):
        assert not path.is_symlink(),path
        if path.is_file() and path!=RESULTS/"run_manifest.json":
            assert path.suffix in {".json",".pdf",".png"},path
            assert path.stat().st_size<=4*1024**2,path
            if path.suffix==".png":
                with path.open("rb") as f:
                    header=f.read(24)
                assert header[:8]==b"\x89PNG\r\n\x1a\n"
                width,height=struct.unpack(">II",header[16:24])
                assert width>300 and height>200,path
                assert path.with_suffix(".pdf").is_file(),path
            if path.suffix==".pdf":
                with path.open("rb") as f:
                    assert f.read(5)==b"%PDF-",path
            nfiles+=1
    state=dict(status="partial", checked_utc=datetime.now(timezone.utc).isoformat(),
               archive="DESI Legacy Surveys DR11 DECam",
               persistent_project="/global/homes/y/yunao/projects/legacy-tno",
               work="/pscratch/sd/y/yunao/legacy-tno",
               repository="https://github.com/xiaoyunao/legacy-tno",
               unique_known_blind_objects=sorted(recovered), verified_files=nfiles,
               search_limits="Distance-bin truncations, small bounded pilots, DES plus targeted Horizons identity",
               run_products=runs)
    (RESULTS/"run_manifest.json").write_text(json.dumps(state,indent=2)+"\n")
    report=PROJECT/"reports"/"v1_report.md"
    for link in re.findall(r"\]\(([^)]+)\)",report.read_text()):
        if "://" not in link:
            assert (report.parent/link).exists(),link
    print(f"Verified {len(runs)} run summaries and {nfiles} files. Blind recovered: {', '.join(sorted(recovered))}")


if __name__=="__main__":
    main()
