#!/usr/bin/env python3
"""Prepare physical-CCD catalogs from a completed NSC download manifest."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path

from legacy_tno.nsc import query_measurement_group
from legacy_tno.nsc_adapter import normalize
from legacy_tno.pipeline import save_npz, write_json


def read_group(name, ids, cache):
    try:
        return query_measurement_group(name, ids, cache)
    except OverflowError:
        if len(ids) == 1:
            raise
        middle = len(ids) // 2
        return read_group(name, ids[:middle], cache) + read_group(name, ids[middle:], cache)


def prepare_exposure(args):
    entry, ccds, cache, image_root, config, output = args
    planned = {int(row["nsc_ccdnum"]): row for row in ccds}
    results = []
    for group in entry["groups"]:
        expected = {r["ccdnum"]: r["rows"] for r in group["measurements"]}
        chosen = planned.keys() & expected.keys()
        if not chosen:
            continue
        received = defaultdict(list)
        for measurement in read_group(entry["exposure"], group["ccdnums"], cache):
            received[int(measurement["ccdnum"])].append(measurement)
        for number in sorted(chosen):
            row = planned[number]
            records = received[number]
            if len(records) != expected[number]:
                raise ValueError(f"Measurement-cache count altered for {entry['exposure']}/{number}")
            table, qc = normalize(records, entry["chips"][str(number)], row, image_root, config)
            path = output / f"decam-{row['expnum']}-{row['ccdname']}.npz"
            save_npz(path, detections=table, qc=json.dumps(qc))
            with path.open("rb") as handle:
                diff = hashlib.file_digest(handle, "sha256").hexdigest()
            results.append(dict(file=path.name, sha256=diff, **{k: v for k, v in qc.items() if k != "file"}))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ccd_inventory", type=Path)
    parser.add_argument("fetched", type=Path)
    parser.add_argument("--image-root", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit-ccds", type=int)
    args = parser.parse_args()
    fetch_bytes = args.fetched.read_bytes()
    fetched = json.loads(fetch_bytes)
    work = args.ccd_inventory.parent.parent
    archived = json.loads((work / "runs" / fetched["field"] / "run_manifest.json").read_text())
    source = json.loads(args.ccd_inventory.read_text())[fetched["field"]]
    rows = [row for row in source if row["nsc_chip_status"] == "chip_listed"]
    if args.limit_ccds is not None:
        rows = rows[:args.limit_ccds]
    keys = {(row["expnum"], row["ccdname"]) for row in rows}
    if not keys or len(keys) != len(rows):
        raise ValueError("Expected nonempty and unique physical CCDs")
    if (args.output / "manifest.json").exists():
        raise FileExistsError(f"Prepared product already exists in {args.output}")
    by_exposure = defaultdict(list)
    for row in rows:
        by_exposure[row["nsc_exposure"]].append(row)
    entries = {entry["exposure"]: entry for entry in fetched["exposures"]}
    config = json.loads(args.config.read_text())["extract"]
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = [(entries[name], selected, args.ccd_inventory.parent / "nsc_query_cache",
             args.image_root, config, args.output) for name, selected in sorted(by_exposure.items())]
    all_ccds = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for index, result in enumerate(pool.map(prepare_exposure, jobs), 1):
            all_ccds.extend(result)
            print(f"Prepared {index}/{len(jobs)} exposures", flush=True)
    if {(r["expnum"], r["ccdname"]) for r in all_ccds} != keys:
        raise ValueError("Prepared CCD list does not match exposure inventory")
    summary = dict(backend="NSC-DR2:AUTO", field=fetched["field"], requested_legacy_ccds=len(source),
                   prepared_ccds=len(all_ccds), source_rows=sum(r["extracted"] for r in all_ccds),
                   retained=sum(r["retained"] for r in all_ccds),
                   outside_cp=sum(r["outside_cp"] for r in all_ccds),
                   diagnostic_subset=args.limit_ccds is not None)
    write_json(args.output / "manifest.json", dict(**summary, legacy_field=archived["field"],
               fetch_sha256=hashlib.sha256(fetch_bytes).hexdigest(), mask_config=config, ccds=all_ccds))
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
