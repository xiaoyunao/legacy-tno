#!/usr/bin/env python3
"""Cache topocentric astrometric directions for one known object and fixed epochs."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("designation")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if not args.designation.strip() or any(c in args.designation for c in "'\r\n;"):
        parser.error("Expected one known-object designation")
    with args.input_csv.open() as f:
        dates = [datetime.fromisoformat(row["utc"]).replace(tzinfo=timezone.utc)
                 for row in csv.DictReader(f)]
    epochs = [date.timestamp()/86400 + 2440587.5 for date in dates]
    q = {
        "format": "json", "COMMAND": f"'DES={args.designation};'", "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'OBSERVER'", "CENTER": "'W84@399'",
        "TIME_TYPE": "'UT'", "TLIST_TYPE": "'JD'", "TLIST": "'"+" ".join(f"{x:.10f}" for x in epochs)+"'",
        "REF_SYSTEM": "'ICRF'", "QUANTITIES": "'1'", "ANG_FORMAT": "'DEG'",
        "CAL_FORMAT": "'JD'", "CSV_FORMAT": "'YES'", "EXTRA_PREC": "'YES'",
    }
    url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urlencode(q)
    with urlopen(url, timeout=60) as response:
        raw = json.load(response)
    result = raw["result"]
    if "$$SOE" not in result:
        raise ValueError(result[:500])
    lines = result.split("$$SOE",1)[1].split("$$EOE",1)[0].strip().splitlines()
    rows=[]
    for row in csv.reader(lines):
        rows.append([float(row[i]) for i in (0,3,4)])
    if len(rows)!=len(epochs):
        raise ValueError(f"Horizons returned {len(rows)} epochs for {len(epochs)} requested")
    args.output.write_text(json.dumps(dict(query=q, request_url=url, api_signature=raw.get("signature"),
                                           retrieved_utc=datetime.now(timezone.utc).isoformat(),
                                           jd_ra_dec=rows, header=result.split("$$SOE")[0]),
                                       indent=2)+"\n")


if __name__=="__main__":
    main()
