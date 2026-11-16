#!/usr/bin/env python3
"""Cross-check NSC DR2 against Legacy exposure metadata and inventory NSC chips."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from legacy_tno.nsc import query_chips, query_exposures, query_measurements

DAY_SECONDS = 86400
MAX_TIME_DIFF_S = 2
MAX_EXPTIME_DIFF_S = 0.1


def groups(values):
    values = sorted(set(values))
    for index in range(0, len(values), 24):
        yield values[index:index + 24]


def check(legacy, nsc):
    delta = (float(nsc["mjd"]) - legacy["mjd"]) * DAY_SECONDS
    duration_delta = float(nsc["exptime"]) - legacy["exptime"]
    accepted = (nsc["filter"].strip().lower() == legacy["band"].lower()
                and abs(delta) <= MAX_TIME_DIFF_S
                and abs(duration_delta) <= MAX_EXPTIME_DIFF_S)
    return dict(exposure=nsc["exposure"], mjd_start_delta_s=delta, exptime_delta_s=duration_delta,
                nsc_filter=nsc["filter"], legacy_filter=legacy["band"], metadata_match=accepted)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("legacy_audit", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    fields = json.loads(args.legacy_audit.read_text())["results"]
    if any(row["camera"] != "decam" for rows in fields.values() for row in rows):
        raise ValueError("This inventory supports only Legacy DECam exposures")
    cache = args.output.parent / "nsc_query_cache"
    ids = {row["expnum"] for rows in fields.values() for row in rows} | {339232}
    observed = defaultdict(list)
    for batch in groups(ids):
        for row in query_exposures(batch, cache):
            observed[int(row["expnum"])].append(row)
    chips = defaultdict(list)
    for batch in groups(row["exposure"] for entries in observed.values() for row in entries):
        for row in query_chips(batch, cache):
            chips[row["exposure"]].append(int(row["ccdnum"]))
    samples = {}
    summaries = {}
    for name, rows in fields.items():
        results = []
        for expnum, row in sorted({r["expnum"]: r for r in rows}.items()):
            matches = [check(row, item) for item in observed[expnum]]
            compatible = [m for m in matches if m["metadata_match"]]
            status = ("matched" if len(compatible) == 1 else "ambiguous" if compatible
                      else "metadata_mismatch" if matches else "no_nsc_exposure")
            results.append(dict(expnum=expnum, mjd_legacy=row["mjd"], status=status,
                                matches=matches, nsc_ccdnums=sorted(set(chips[compatible[0]["exposure"]]))
                                if status == "matched" else []))
        samples[name] = results
        matched = [r for r in results if r["status"] == "matched"]
        summaries[name] = dict(exposures=len(results), status_counts=dict(Counter(r["status"] for r in results)),
                               exposures_with_nsc_chips=sum(bool(r["nsc_ccdnums"]) for r in matched),
                               max_match_time_delta_s=max(
                                   (abs(m["mjd_start_delta_s"]) for r in matched for m in r["matches"]
                                    if m["metadata_match"]), default=None))
    reference = observed[339232]
    if len(reference) != 1:
        raise RuntimeError("Expected a unique NSC reference exposure 339232")
    probe_ccds = sorted(set(chips[reference[0]["exposure"]]))
    ccd = probe_ccds[0]
    measured = query_measurements(reference[0]["exposure"], ccd, cache)
    if not measured or any(r["exposure"] != reference[0]["exposure"] or int(r["ccdnum"]) != ccd for r in measured):
        raise RuntimeError("NSC measurement query returned no matching CCD rows")
    summary = dict(fields=summaries, tolerances={"epoch_seconds": MAX_TIME_DIFF_S, "exptime_seconds": MAX_EXPTIME_DIFF_S},
                   reference_probe=dict(exposure=reference[0]["exposure"], ccdnum=ccd,
                                        exposure_measurements=int(reference[0]["nmeas"]), chip_count=len(probe_ccds),
                                        measurement_rows=len(measured)),
                   detail_path=str(args.output.absolute()))
    args.output.write_text(json.dumps(dict(summary=summary, legacy_matches=samples), indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
