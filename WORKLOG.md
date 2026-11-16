# Work log

## 2026-11-16

- Verified Perlmutter access and inspected 28 exact Legacy SE paths for the 14 v1 audit CCDs in the DR11 data and work roots using the DR11.1.0 path rule. All 28 were absent. This sampled result leaves the control- and exploration-field audit open. Initial NOIRLab TAP GET timed out and Query Client HTTP probes did not return catalog rows.

- Established the active catalog-first v2 goal and created the codex/catalog-first-v2 branch from the clean, synchronized v1 baseline. Added the GPT Pro execution specification and the first catalog audit milestones.

- Recovered 2013 TV158 blind with 23/23 clean matched detections across six nights. The fit RMS was 0.107 arcsec and held-night RMS values ranged from 0.043 to 0.444 arcsec. An independent bound-constrained fit produced nearly the same residual RMS, emphasizing energy degeneracy.
- Recovered high-eccentricity 2017 OF201 with four independent nights, four pure members and a 96.74-day arc in the four-detection stress branch. The separate published W84 benchmark also agreed with Horizons.
- The broad non-DES replay retained one weak, nominally hyperbolic chain and 18 truncated distance bins. Its held-night residuals and CP striping support a low validation grade. Completed the bounded non-DES field in job 61347537 with 283 CCDs, 23 exposures, 10 nights, and no truncated boxes or accepted chains.
- Materialized report, small result tables, physical control summaries, figures, and Slurm accounting. Final acceptance remains partial until the broader search, cross-season growth, full identity screen and other stated gaps are closed.

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
