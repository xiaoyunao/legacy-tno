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

FULL_CHIP_COLUMNS = ("exposure ccdnum nmeas fwhm depth10sig vertex_ra1 vertex_ra2 vertex_ra3 vertex_ra4 "
                     "vertex_dec1 vertex_dec2 vertex_dec3 vertex_dec4").split()
FULL_MEAS_COLUMNS = MEAS_COLUMNS + "x y asemi bsemi fwhm filter".split()


def query_chip_details(name, cache):
    rows = query(f"SELECT {','.join(FULL_CHIP_COLUMNS)} FROM nsc_dr2.chip "
                 f"WHERE exposure={exposure_literal(name)}", FULL_CHIP_COLUMNS, cache)
    chips = {int(row["ccdnum"]): row for row in rows}
    if len(chips) != len(rows) or any(row["exposure"] != name for row in rows):
        raise ValueError(f"Non-unique or inconsistent NSC chip table for {name}")
    return chips


def query_measurement_group(name, ccdnums, cache, max_rows=60000):
    """Read a complete group of CCDs, with an explicit overflow failure."""
    ccdnums = sorted(set(map(int, ccdnums)))
    if not 1 <= len(ccdnums) <= 8 or not 1 <= max_rows <= 100000:
        raise ValueError("Request 1–8 CCDs and at most 100,000 rows per query")
    ids = ",".join(map(str, ccdnums))
    rows = query(f"SELECT {','.join(FULL_MEAS_COLUMNS)} FROM nsc_dr2.meas "
                 f"WHERE exposure={exposure_literal(name)} AND ccdnum IN ({ids}) LIMIT {max_rows + 1}",
                 FULL_MEAS_COLUMNS, cache)
    if len(rows) > max_rows:
        raise OverflowError(f"NSC {name}/{ids} exceeds {max_rows} rows")
    selected = set(ccdnums)
    if any(row["exposure"] != name or int(row["ccdnum"]) not in selected for row in rows):
        raise ValueError(f"Unexpected NSC exposure or CCD in query for {name}/{ids}")
    return rows
