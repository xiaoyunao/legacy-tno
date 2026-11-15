# Legacy TNO

Catalog-first search for distant Solar System objects in single-epoch DECam observations. The program uses DR11 Community Pipeline calibrated exposures, independent SEP detections, Gaia EDR3 astrometry, the DR11 Sweep static reference, detection-level linking, and anonymous orbital fits with DE440s planetary perturbations.

- [试点运行报告](reports/v1_report.md)
- [NERSC operations](docs/operations.md)
- [Input audit](docs/data_inventory.md) and [methods](docs/method_v1.md)
- [Validation definitions](docs/validation_v1.md) and [limits](docs/limitations.md)

Python packages are listed in `configs/requirements.txt`. The `legacy-tno` command provides inventory, pilot selection, field execution and plotting. Slurm launches compute on Perlmutter. Small audit and pilot products live under `results/v1/`. NERSC scratch stores raw catalogs, intermediate arrays and the private input cache. The GitHub repository is private.

The first pilot is partial. It blind-recovered 2013 TV158 and 2017 OF201 and completed an independent non-DES search of a 0.122 deg² core at aperture SNR ≥ 8. The compact run left zero accepted candidates. The wider trial retained one low-evidence unresolved chain and had truncated distance bins.

The fixed-field pilot limits the sampled interval, filters, footprint and distance constraints. Published DES objects are used for evaluation after the fit. Reported photometry uses calibrated apertures. Refer to the release report before interpreting candidates, recovery fractions or coverage measurements.
