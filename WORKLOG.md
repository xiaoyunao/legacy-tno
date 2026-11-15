# Work log

## 2026-11-16

- Corrected DES barycentric state epoch to J2016.0 TDB (MJD 57388.5). Horizons checks for RD124 and RQ157 reduced RMS from 5.119 and 5.735 arcsec to 0.027 and 0.031 arcsec. Guided CP aperture probes peaked below SNR 3.3 in this shallow z-only window.

- Completed DR11 inventory and initial validation. 14 sampled CP exposure triplets readable. Two geometrically covered DES objects had no close SEP detection at independent Horizons positions. Baseline catalog injections recovered 16/16 guaranteed and 3/16 noisy/missing tracks.
- Completed anonymous published W84 orbital benchmark. Exploratory run, added deep validation, and an independent four-night 2017 OF201 stress test are in progress.
- Added parallel per-distance-bin association and compatible catalog replay after serial association proved costly for the larger survey field. Validated identical synthetic acceptance in serial and parallel.

## 2026-11-15

- Initialized the empty local project and preserved the supplied execution specification.
- Verified the existing Perlmutter SSH session and GitHub account. Live archive and scheduler inspection started.

- NERSC persistent code and scratch roots created. Private GitHub repository initialized and pushed.
- DR11 DECam metadata, CP staging, Gaia EDR3 and DR11 Sweep roots identified. First sample catalogs measured 1,748 and 1,667 retained detections.
- Job 61345772 wrote the full survey CCD selection columns and real CP extractions, then hit its memory limit opening compressed annotated metadata. Job 61345841 also reached its selection memory limit. Streaming annotated FITS and compact-column selection reruns are active.
- Implemented SEP measured detections, Gaia calibration, Sweep and persistence classification, anonymous distance-binned association, DE440s perturbed fit and post-search truth evaluation.
