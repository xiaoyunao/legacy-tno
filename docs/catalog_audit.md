# Detection product audit

The shared DR11 release and work-dir calib trees expose PSFEx, sky, and sky-pattern products. The exposure-specific SExtractor legacy pattern was probed in DR9, DR10 and both DR11 roots for the audit sample. Tractor and Sweep are model catalogs built from stacked-image detections. Forced products measure positions established by a reference list. Those products cannot provide an independent single-epoch search catalog.

The fallback reads CP InstCal science, inverse variance and integer DQ. For each exposure it estimates a local sky using SEP, runs a matched pixel-threshold detection, measures a windowed centroid and integrates aperture flux. Catalog and search cuts apply to integrated SNR and are configured separately. In DECam, the science pixels are in ADU and CCDZPT refers to ADU/s. The aperture flux in nanomaggies is ADU / EXPTIME / 10^[(CCDZPT−22.5)/2.5]. Aperture correction to a fitted PSF flux has not been measured. The magnitude is approximate calibrated aperture AB.

Distance to edges, masked fraction, shape, aperture flags and DQ are retained. Weight <=0 and severe DQ classes are masked. Raw code 7 is retained where positive weight exists. Legacy releases before the CP 3.5 integer-code convention are rejected by this adapter. Pixel coordinates are zero-based in SEP and in WCS evaluation.

[DR11 data model](https://www.legacysurvey.org/dr11/files/)
[NOIRLab pipeline handbook index](https://nsf-noirlab.gitlab.io/csdc/csdc-mso-docs/)
[legacypipe DECam adapter](https://github.com/legacysurvey/legacypipe/blob/main/py/legacypipe/decam.py)
