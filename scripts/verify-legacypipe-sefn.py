#!/usr/bin/env python3
"""Reconstruct every audited path using the pinned upstream LegacySurveyImage methods."""
import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

from legacy_tno.pipeline import write_json

SOURCE_COMMIT = "769e266b837196a7d5c2dfda245cd1f5d64abd91"
SOURCE_SHA256 = "1393c86ebb55c391bfd0de68630ada3679a24c251b8727380813ae234ab1d1ba"


def naming_methods(path):
    upstream = path.read_bytes()
    if hashlib.sha256(upstream).hexdigest() != SOURCE_SHA256:
        raise ValueError("Wrong DR11.1.0 upstream image.py")
    tree = ast.parse(upstream)
    image, = (node for node in tree.body if isinstance(node, ast.ClassDef)
              and node.name == "LegacySurveyImage")
    methods = [node for node in image.body if isinstance(node, ast.FunctionDef)
               and node.name in ("set_calib_filenames", "get_base_name")]
    scope = {"os": os}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), "exec"), scope)
    return scope["get_base_name"], scope["set_calib_filenames"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("ledgers", type=Path, nargs="+")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    base_name, name = naming_methods(args.source)
    unique = {}
    counts = {}
    for ledger in args.ledgers:
        records = json.loads(ledger.read_text())
        roots = [Path(s) for s in records["survey_roots"]]
        for field, rows in records["results"].items():
            per_field = Counter()
            for row in rows:
                item = SimpleNamespace(image_filename=row["image_filename"], ccdname=row["ccdname"])
                item.get_base_name = lambda: base_name(item)
                for root, entry in zip(roots, row["paths"], strict=True):
                    item.survey = SimpleNamespace(get_calib_dir=lambda: str(root/"calib"))
                    name(item)
                    if item.sefn != entry["path"]:
                        raise ValueError(f"Archived path differs from upstream im.sefn: {entry['path']}")
                    old = unique.setdefault(item.sefn, entry["status"])
                    if old != entry["status"]:
                        raise ValueError(f"Inconsistent archived status for {item.sefn}")
                    per_field[entry["status"]] += 1
            counts[field] = dict(per_field)
    write_json(args.output, dict(tag="DR11.1.0", commit=SOURCE_COMMIT, source_sha256=SOURCE_SHA256,
        source="https://github.com/legacysurvey/legacypipe/blob/"+SOURCE_COMMIT+"/py/legacypipe/image.py",
        method="Executed get_base_name and set_calib_filenames on the audited image metadata",
        paths_verified=len(unique), per_field=counts, archived_status=dict(Counter(unique.values()))))


if __name__ == "__main__":
    main()
