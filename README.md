# Legacy TNO

Catalog-first search for distant Solar System objects in single-epoch DECam observations. The v2 search uses NSC DR2 measurements on matched Legacy Surveys DR11 exposures, CP image weights and DQ, Gaia EDR3, and the DR11 Sweep static reference. The v1 SEP input remains available for comparison and for years outside NSC coverage. Both paths use detection-level linking and anonymous orbital fits with DE440s planetary perturbations.

- [v2 实测运行报告](reports/v2_report.md)
- [v2 复跑与续跑](docs/v2_operations.md)
- [v1 基准报告](reports/v1_report.md)
- [NERSC operations](docs/operations.md)
- [Input audit](docs/data_inventory.md) and [methods](docs/method_v1.md)
- [Validation definitions](docs/validation_v1.md) and [limits](docs/limitations.md)

Python packages are listed in `configs/requirements.txt`. The `legacy-tno` command provides inventory, pilot selection, field execution and plotting. Slurm launches compute on Perlmutter. Audit and pilot summaries live under `results/v1/` and `results/v2/`. NERSC scratch stores the full source tables and intermediate arrays.

The first pilot is partial. It blind-recovered 2013 TV158 and 2017 OF201 and completed an independent non-DES search of a 0.122 deg² core at aperture SNR ≥ 8. The compact run left zero accepted candidates. The wider trial retained one low-evidence unresolved chain and had truncated distance bins.

The frozen pilots state their sampled intervals, filters, footprints and distance definitions. Known objects are used for evaluation after the anonymous search. v2 uses calibrated NSC AUTO photometry and v1 uses SEP aperture photometry. The reports document the distinct coverage and recovery denominators.
