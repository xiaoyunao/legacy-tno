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
