#!/usr/bin/env python3
"""Join the sampled Legacy, NSC metadata and actual catalog-run coverage."""
import argparse
from collections import Counter, defaultdict
from datetime import date, timedelta
import json
from pathlib import Path

from legacy_tno.geometry import night_id
from legacy_tno.pipeline import write_json

FIELDS = {
    "validation-c36e0a643fc984": ("Original misses", "validation-fdd2c34bae73f8", "NSC"),
    "validation-97d3348bc5c4b3": ("TV158 control", "validation-2757671f191346", "NSC"),
    "validation-7185aa85687161": ("OF201 control", "validation-ef4655b225ac2a", "NSC"),
    "exploration-f742d8b20d9ab4": ("2021 broad", "exploration-f742d8b20d9ab4", "SEP"),
    "exploration-cb6d398cc191bd": ("2021 narrow", "exploration-cb6d398cc191bd", "SEP"),
}
PILOT = {
    "pilot-38-10": ("2018 independent pilot", "exploration-b49f1211213970", "NSC"),
}


def year(mjd):
    return (date(1858, 11, 17) + timedelta(days=int(mjd))).year


def summarize(rows):
    metadata = Counter(r["nsc_chip_status"] for r in rows)
    chosen = Counter(r["product_usable"] for r in rows)
    matched = [r for r in rows if r["nsc_chip_status"] == "chip_listed"]
    usable = [r for r in rows if r["product_usable"] in ("NSC", "SEP")]
    return dict(legacy_ccds=len(rows), legacy_exposures=len({r["expnum"] for r in rows}),
                legacy_nights=len({int(night_id(r["mjd"])) for r in rows}),
                nsc_metadata=dict(metadata), nsc_exposures=len({r["expnum"] for r in matched}),
                usable_ccds=dict(chosen), usable_exposures=len({r["expnum"] for r in usable}),
                usable_nights=len({int(night_id(r["mjd"])) for r in usable}),
                mjd_min=min(r["mjd"] for r in rows), mjd_max=max(r["mjd"] for r in rows),
                exclusions=dict(Counter(r["run_exclusion"] for r in rows if r["run_exclusion"])))


def load(work, ledger, field_map, coverage):
    output = []
    for field_id, rows in json.loads(ledger.read_text()).items():
        label, run_id, backend = field_map[field_id]
        path = work/"runs"/run_id
        manifest = json.loads((path/"run_manifest.json").read_text())
        ccd_audit = path/"ccd_audit.json"
        audit = {(int(r["expnum"]), r["ccdname"].strip()): r
                 for r in json.loads(ccd_audit.read_text())}
        existing = set()
        joined = []
        buckets = defaultdict(list)
        for row in rows:
            key = (row["expnum"], row["ccdname"])
            if key in existing:
                raise ValueError(f"Duplicate physical CCD in {field_id}: {key}")
            existing.add(key)
            qc = audit.get(key, {})
            catalog_error = qc.get("error")
            astro = qc.get("astrometry", {})
            exclusion = catalog_error or astro.get("exclusion") or (
                None if "astrometry" in qc else "no run CCD audit")
            usable = backend if exclusion is None else "none"
            data = dict(**row, product_usable=usable, run_exclusion=exclusion,
                        input_rows=qc.get("extracted"), normalized_rows=qc.get("retained"),
                        astrometry=qc.get("astrometry"), usable_fraction=qc.get("usable_fraction"),
                        footprint_reference=str(path/"exposures.npy"))
            joined.append(data)
            buckets[year(row["mjd"]), row["band"]].append(data)
        coverage[field_id] = joined
        output.append(dict(field_id=field_id, label=label, run_id=run_id, field=manifest["field"],
                           total=summarize(joined), breakdown=[
                               dict(year=y, band=b, **summarize(block))
                               for (y, b), block in sorted(buckets.items())]))
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("work", type=Path)
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--ledger", type=Path, required=True)
    args = p.parse_args()
    coverage = {}
    v2 = args.work/"v2"
    fields = load(args.work, v2/"nsc_ccds.json", FIELDS, coverage)
    fields += load(args.work, v2/"pilot-nsc-ccds.json", PILOT, coverage)
    write_json(args.ledger, coverage)
    write_json(args.summary, dict(fields=fields, detailed_ledger=str(args.ledger),
        scope="Sampled archived fields and independent pilot; archived 2021 scopes can overlap. "
              "Totals are per field and must not be added as unique survey coverage."))


if __name__ == "__main__":
    main()
