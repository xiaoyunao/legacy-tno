#!/usr/bin/env python3
"""Cache complete NSC measurement batches for all matched CCDs of a frozen field."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from legacy_tno.nsc import query_chip_details, query_measurement_group


def fetch_group(name, ids, cache):
    try:
        rows = query_measurement_group(name, ids, cache)
    except OverflowError:
        if len(ids) == 1:
            raise
        middle = len(ids) // 2
        return fetch_group(name, ids[:middle], cache) + fetch_group(name, ids[middle:], cache)
    count = Counter(int(row["ccdnum"]) for row in rows)
    if len({row["measid"] for row in rows}) != len(rows):
        raise ValueError(f"Duplicate measurement IDs in {name}/{ids}")
    return [dict(ccdnum=number, rows=count[number]) for number in ids]


def fetch_exposure(name, numbers, cache):
    chips = query_chip_details(name, cache)
    ids = sorted(numbers)
    groups = []
    for start in range(0, len(ids), 8):
        group = ids[start:start+8]
        groups.append(dict(ccdnums=group, measurements=fetch_group(name, group, cache)))
    return dict(exposure=name, groups=groups,
                chips={str(number): chips[number] for number in ids})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ccd_inventory", type=Path)
    parser.add_argument("field")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = json.loads(args.ccd_inventory.read_text())[args.field]
    by_exposure = defaultdict(set)
    for row in rows:
        if row["nsc_chip_status"] == "chip_listed":
            by_exposure[row["nsc_exposure"]].add(row["nsc_ccdnum"])
    if not by_exposure:
        raise ValueError(f"{args.field} has no NSC coverage")
    cache = args.ccd_inventory.parent / "nsc_query_cache"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = []
    with ThreadPoolExecutor(max_workers=3) as workers:
        jobs = {name: workers.submit(fetch_exposure, name, numbers, cache)
                for name, numbers in sorted(by_exposure.items())}
        for index, (name, job) in enumerate(jobs.items(), 1):
            result.append(job.result())
            print(f"{index}/{len(jobs)} {name}", flush=True)
    summary = Counter()
    for entry in result:
        for group in entry["groups"]:
            for ccd in group["measurements"]:
                summary["ccds_fetched"] += 1
                summary["source_rows"] += ccd["rows"]
                expected = int(entry["chips"][str(ccd["ccdnum"])]["nmeas"])
                if ccd["rows"] != expected:
                    summary["ccds_with_count_disagreement"] += 1
                if ccd["rows"] == 0:
                    summary["empty_ccds"] += 1
    report = dict(field=args.field, ccd_rows=len(rows), matched_exposures=len(by_exposure),
                  **summary, exposures=result)
    tmp = args.output.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2) + "\n")
    tmp.replace(args.output)
    print(json.dumps({k: v for k, v in report.items() if k != "exposures"}), flush=True)


if __name__ == "__main__":
    main()
