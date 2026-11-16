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

### v2 delivery checkpoint

The five archived v1 fields were checked against 7,446 unique DR11.1.0 SE paths in the DR11 data and work roots. The NOIRLab Query Client SQL route works from Perlmutter with `ofmt=csv` and `async=False`. The early validation, deep TV158 and OF201 fields matched 11/11, 35/36 and 38/38 physical exposures. Both 2021 windows had no NSC DR2 match. One reference CCD query returned 1,104 measurement rows.

The archived image headers confirmed 2,555 common control-field CCDs listed in NSC. The expanded comparison found reciprocal counterparts for 23/23 recovered TV158 members and 3/4 OF201 members. The OF201 miss is EXPNUM 759212. Full measurements for the two fields were fetched and checked against the chip counts. The 923 TV158-field CCDs yielded 1,356,317 measurements and the 962 OF201-field CCDs yielded 936,200.

1. The pinned upstream LegacySurveyImage naming methods verified 7,946 paths. Four pre-2021 samples have 2,805 of 2,810 usable NSC CCDs. All five missing TV158 CCDs passed an independent SEP fallback test; the 2021 archived samples use SEP. Coverage, Gaia/CP QA and same-detector position/photometry statistics are archived.
2. The frozen TV158 control was recovered blind. OF201 has three surviving NSC epochs, below the four-night test. Horizons verified the missing target measurement and the RD124/RQ157 misses. The original OF201 wide stress run and its 0.35-degree sensitivity are still partial; the separate 0.16-degree endpoint sensitivity completed all declared bins.
3. The independent SNR ≥ 5 pilot at RA 38°, Dec +10° completed all 24 declared bins with zero accepted chains on its 0.20-degree core. The SNR ≥ 8 contrast finished separately. Both 0.06-degree ambiguity controls completed; the extra ambiguity chain failed image and holdout review. The 173,839-record wide ambiguity run remains partial.
4. Anonymous cross-season joint fits and independent Horizons scoring verified 20 additional TV158 measurements in seven nights and two additional OF201 epochs. Reviewed unresolved candidates with MPCORB, CP images, DQ, weight, holdouts and exact membership overlap. Stratified real-pool injections recovered 4/12. The public report, operations notes and scheduler accounting link to each archive. Complete source measurements and tables remain on NERSC.

Any later survey expansion inherits the measured footprint, stage efficiency and bin-cost constraints. Retain the wide runs' truncation records and the narrow experiments' explicit seed-domain definitions.
