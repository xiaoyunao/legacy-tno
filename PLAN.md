# Current plan

## Pilot checkpoint

Perlmutter processed real DR11 CP science, weight, and DQ. The blind fit recovered 2013 TV158 and 2017 OF201 in separate validation settings. The bounded non-DES field completed all configured bins, the identity comparison, and both controls. Preserve the wide-field constraints, alternate runs, actual exit states, and result locations under `results/v1/`.

## Remaining acceptance work

1. Improve the scale of the pair–triplet search and design overlapping tiles with time windows that complete without caps. Confirm distance-envelope recall across bins independent of the seed approximation.
2. Add a tested cross-season extension using the predicted footprint and multiple viable orbits. Keep the original anonymous memberships for provenance.
3. Run the catalog-ambiguity sensitivity branch and a larger independent injection campaign, accounting for the depth and cadence of each field.
4. Compare surviving candidate chains against a comprehensive current known-object catalog. Preserve image adjudication and all excluded regions.

## Active v2 goal

The [v2 execution specification](docs/v2_execution_spec.md) records the latest GPT Pro recommendations. The active Codex goal uses the same eight workstreams. Preserve baseline commit 830ae82 and work on codex/catalog-first-v2.

Start with the versioned Legacy SE path audit and real reads from NSC DR2. Check exposure, chip and measurement access separately before expanding to the control exposures. Keep 2021 catalog availability separate from the NSC-era pilot. See the specification for the end-to-end acceptance criteria and required outputs.

### v2 catalog audit checkpoint

The five archived v1 fields were checked against 7,446 unique DR11.1.0 SE paths in the DR11 data and work roots. The NOIRLab Query Client SQL route works from Perlmutter with `ofmt=csv` and `async=False`. The early validation, deep TV158 and OF201 fields matched 11/11, 35/36 and 38/38 physical exposures. Both 2021 windows had no NSC DR2 match. One reference CCD query returned 1,104 measurement rows.

The archived image headers confirmed 2,555 common control-field CCDs listed in NSC. The expanded comparison found reciprocal counterparts for 23/23 recovered TV158 members and 3/4 OF201 members. The OF201 miss is EXPNUM 759212. Full measurements for the two fields were fetched and checked against the chip counts. The 923 TV158-field CCDs yielded 1,356,317 measurements and the 962 OF201-field CCDs yielded 936,200.

1. Add Gaia QC summaries to the completed NSC normalization and catalog runs, including astrometric offsets and source-retention counts by reason.
2. The frozen TV158 control was recovered blind. OF201 has three surviving epochs, below the four-night test, and had 15 truncated bins. Independent Horizons diagnostics agreed with the RD124, RQ157 and OF201 catalog misses. Run a bounded ambiguity branch and compare NSC with the v1 SEP control as an independent extraction.
3. The independent pilot at RA 38°, Dec +10° completed all 24 declared distance bins at SNR ≥ 5 with zero accepted chains. Its single 0.20° core has 0.112 deg² with coverage and the 13.1-day interval spans five Legacy nights. Compare the separate bright and ambiguous static branches on its frozen catalog product.
4. Complete anonymous cross-season searches 61392435/61392436 and independently score the new epochs. Check OF201-field candidates against the frozen MPCORB snapshot and CP images. The completed pilot injection recovered 4/12 trajectories. Archive product coverage, association efficiency, both pilot sensitivities and scheduler exit states. Keep complete source measurements and tables under NERSC scratch.
