"""Read bounded, cached NSC DR2 queries through the NOIRLab Query Client service."""
import csv
import hashlib
import io
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENDPOINT = "https://datalab.noirlab.edu/query/query"
EXPOSURE_COLUMNS = "exposure expnum instrument mjd dateobs filter exptime nmeas nchips".split()
CHIP_COLUMNS = "exposure ccdnum".split()
MEAS_COLUMNS = "measid exposure ccdnum mjd ra dec raerr decerr mag_auto magerr_auto flags".split()


def parse_csv(payload, columns):
    reader = csv.DictReader(io.StringIO(payload), strict=True)
    if reader.fieldnames != columns:
        raise ValueError(f"Expected columns {columns}, got {reader.fieldnames}")
    rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("Incomplete or malformed NSC query row")
    return rows


def query(sql, columns, cache, timeout=60, retries=2, max_bytes=32 * 1024**2):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((ENDPOINT + "\n" + sql).encode()).hexdigest()
    path = cache / f"{key}.csv"
    if path.is_file():
        return parse_csv(path.read_text(encoding="utf-8"), columns)
    params = urllib.parse.urlencode({"sql": sql, "ofmt": "csv", "async": "False"})
    request = urllib.request.Request(f"{ENDPOINT}?{params}",
                                     headers={"X-DL-AuthToken": "anonymous.0.0.anon_access"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise ValueError("NSC response exceeded the query byte limit")
            decoded = payload.decode("utf-8-sig")
            rows = parse_csv(decoded, columns)
        except (urllib.error.URLError, TimeoutError) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code < 500 and error.code != 429:
                raise
            if attempt == retries:
                raise
            time.sleep(2**attempt)
        else:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=cache, delete=False) as stream:
                stream.write(decoded)
                temporary = Path(stream.name)
            temporary.replace(path)
            return rows
    raise AssertionError("Unreachable")


def query_exposures(expnums, cache):
    if not expnums or len(expnums) > 24:
        raise ValueError("Request 1–24 physical exposure numbers per query")
    ids = ",".join(str(int(number)) for number in sorted(set(expnums)))
    return query(f"SELECT {','.join(EXPOSURE_COLUMNS)} FROM nsc_dr2.exposure "
                 f"WHERE instrument='c4d' AND expnum IN ({ids})", EXPOSURE_COLUMNS, cache)


def exposure_literal(name):
    if re.fullmatch(r"c4d_[A-Za-z0-9_.-]+", name) is None:
        raise ValueError(f"Unexpected DECam exposure name {name!r}")
    return f"'{name}'"


def query_chips(names, cache):
    if not names or len(names) > 24:
        raise ValueError("Request 1–24 exposures per chip query")
    exposures = ",".join(exposure_literal(name) for name in sorted(set(names)))
    return query(f"SELECT {','.join(CHIP_COLUMNS)} FROM nsc_dr2.chip "
                 f"WHERE exposure IN ({exposures})", CHIP_COLUMNS, cache)


def query_measurements(name, ccdnum, cache, max_rows=15000):
    if not 1 <= max_rows <= 50000:
        raise ValueError("Choose a measurement limit from 1 to 50000")
    rows = query(f"SELECT {','.join(MEAS_COLUMNS)} FROM nsc_dr2.meas "
                 f"WHERE exposure={exposure_literal(name)} AND ccdnum={int(ccdnum)} LIMIT {max_rows + 1}",
                 MEAS_COLUMNS, cache)
    if len(rows) > max_rows:
        raise ValueError(f"NSC CCD {name}/{ccdnum} exceeds {max_rows} rows")
    return rows
