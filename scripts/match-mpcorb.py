#!/usr/bin/env python3
"""Compare accepted chains to a frozen full MPC asteroid orbit snapshot."""
import argparse
from collections import defaultdict
from hashlib import file_digest
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np

from legacy_tno.geometry import angular_residual, unit
from legacy_tno.mpc import export_mpc
from legacy_tno.pipeline import write_json

RADIUS = 120


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("--astcheck", required=True, type=Path)
    p.add_argument("--catalog", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    run = args.run
    catalog = args.catalog.resolve()
    blind = json.loads((run/"blind_candidates.json").read_text())
    with np.load(run/"classified.npz", allow_pickle=False) as f:
        table, tdb = f["detections"], f["tdb"]
    matches = []
    with tempfile.TemporaryDirectory(prefix="legacy-astcheck-", dir=run) as work:
        tmp = Path(work).resolve()
        for candidate in blind:
            members = np.asarray(candidate["members"])
            observations = table[members]
            records = []
            for j, member in enumerate(members):
                sample = dict(mjd_tdb=[tdb[member]], ra_deg=[table[member]["ra_deg"]],
                              dec_deg=[table[member]["dec_deg"]])
                records.append(export_mpc(sample, f"L{j:06d}"))
            with (tmp/"candidate.mpc").open("w") as f:
                f.writelines(records)
            tool_output = tmp/"candidate.json"
            command = [str(args.astcheck.resolve()), str(tmp/"candidate.mpc"), "-r120", "-m30",
                       "-M200", f"-p{catalog}", f"-j{tool_output}", f"-f{catalog/'mpcorb.sof'}"]
            completed = subprocess.run(command, cwd=tmp, check=True, capture_output=True, text=True)
            if "parallax won't be included" in completed.stdout:
                raise ValueError("Astcheck did not load observatory codes")
            response = json.loads(tool_output.read_text())
            expected = {f"L{j:06d}" for j in range(len(members))}
            if response.keys() != expected:
                raise ValueError(f"Astcheck returned unexpected anonymous observation keys for {candidate['candidate_id']}")
            ranks = defaultdict(list)
            limited = 0
            for j, obs in enumerate(observations):
                replies = response[f"L{j:06d}"]["matches"]
                limited += len(replies) >= 200
                truth = unit(obs["ra_deg"], obs["dec_deg"])
                for item in replies:
                    predicted = unit(item["ra"], item["dec"])
                    residual = angular_residual(predicted, truth)
                    ranks[item.get("packedID", item["object"])].append(
                        (int(obs["night"]), int(obs["expnum"]), residual.tolist()))
            alternatives = []
            for key, evidence in ranks.items():
                nights = len({r[0] for r in evidence})
                if nights < 2:
                    continue
                rms = float(np.sqrt(np.mean(np.square([r[2] for r in evidence]))))
                alternatives.append(dict(mpc_id=key, nights=nights,
                    measurements=len(evidence), component_rms_arcsec=rms,
                    expnums=[r[1] for r in evidence]))
            alternatives.sort(key=lambda item: (-item["nights"], -item["measurements"], item["component_rms_arcsec"]))
            matches.append(dict(candidate_id=candidate["candidate_id"], measured_epochs=len(members),
                                measured_nights=len(np.unique(observations["night"])),
                                epochs_hitting_output_limit=limited, alternatives=alternatives,
                                status="mpcorb_identity_requires_ephemeris" if alternatives else "no_multipoint_match"))
    with (catalog/"MPCORB.DAT.gz").open("rb") as f:
        code = file_digest(f, "sha256").hexdigest()
    write_json(args.output, dict(run_id=run.name, dataset="MPCORB asteroid orbits",
        snapshot_sha256=code, rows=int((catalog/"orbit-count.txt").read_text()),
        screening_radius_arcsec=RADIUS, limiting_vmag=30,
        scope="Astcheck preliminary propagation, W84; reliable identities require further ephemeris verification",
        candidates=matches))


if __name__ == "__main__":
    main()
