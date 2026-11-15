# Work log

## 2026-11-15

- Initialized the empty local project and preserved the supplied execution specification.
- Verified the existing Perlmutter SSH session and GitHub account. Live archive and scheduler inspection started.

- NERSC persistent code and scratch roots created. Private GitHub repository initialized and pushed.
- DR11 DECam metadata, CP staging, Gaia EDR3 and DR11 Sweep roots identified. First sample catalogs measured 1,748 and 1,667 retained detections.
- Job 61345772 wrote the full survey CCD selection columns and real CP extractions, then hit its memory limit opening compressed annotated metadata. Job 61345841 also reached its selection memory limit. Streaming annotated FITS and compact-column selection reruns are active.
- Implemented SEP measured detections, Gaia calibration, Sweep and persistence classification, anonymous distance-binned association, DE440s perturbed fit and post-search truth evaluation.
