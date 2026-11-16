#!/usr/bin/env python3
"""Check which chains in a restricted replay had already been reviewed."""
import argparse
import json
from pathlib import Path

from legacy_tno.pipeline import write_json


def chains(run):
    return {candidate["candidate_id"]: frozenset(candidate["det_ids"])
            for candidate in json.loads((run/"blind_candidates.json").read_text())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("baseline", type=Path)
    p.add_argument("replay", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    baseline = chains(args.baseline)
    replay = chains(args.replay)
    rows = []
    for label, ids in replay.items():
        identical = [name for name, members in baseline.items() if ids == members]
        competing = [dict(baseline_id=name, shared_measurements=len(ids & members))
                     for name, members in baseline.items() if ids != members and ids & members]
        rows.append(dict(replay_id=label, identical_baseline=identical, competing_baseline=competing))
    write_json(args.output, dict(baseline=args.baseline.name, replay=args.replay.name, chains=rows))
    for row in rows:
        if not row["identical_baseline"]:
            print(row["replay_id"])


if __name__ == "__main__":
    main()
