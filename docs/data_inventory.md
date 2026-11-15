# DR11 input inventory

The full survey-ccds and ccds-annotated tables include rejected CCDs as well as coadd inputs. The staged columns come from the compressed full FITS tables. The fast .kd products are unsuitable for counting rejected observations. Selection accepts all rows with a valid DECam zero point and no cut bits other than DR11 DEPTH_CUT (14) and DEPTH_CUT_2 (18), then deduplicates by physical exposure and CCD. The selection score ranks DES Y6 objects by eligible nights and brightness in an opposition window, and independently ranks non-DES fields by time sampling.

Shared archive paths verified on Perlmutter:

- `/global/cfs/cdirs/cosmo/data/legacysurvey/dr11` for survey CCDs and released calibrations.
- `/global/cfs/cdirs/cosmo/staging/decam` for CP science, weight and DQ images using survey CCD filenames.
- `/global/cfs/cdirs/cosmo/data/gaia/edr3/healpix` for the Gaia EDR3 reference.
- `/global/cfs/cdirs/cosmo/data/legacysurvey/dr11/south/sweep/11.0` for a deep static reference.

The pilot union areas use the metadata TAN WCS on a 0.025° grid, with cosine-weighted declination. The four-night count measures coverage at a fixed location and puts no floor on target detection probability. CCD interiors and gaps are represented at the grid resolution. Pixel masks, nonuniform depth and moving-object reach require a separate measurement.

[DR11 files](https://www.legacysurvey.org/dr11/files/)  
[DR11 CCD cut bits](https://www.legacysurvey.org/dr11/bitmasks/)
