# Validation definitions

A measures DES catalog objects that intersect the processed CCD footprints. B counts objects matched in the unfiltered extracted source table. C requires a match in the clean search class. D checks the anonymous association logic on surviving true members using identical distance and cadence settings. E requires every fitted blind member to agree with one unique truth object. F applies the fitter to links within the separate ephemeris-selected list for objects not recovered blind. Entire nights of recovered detections are held out for forward prediction.

The DES FITS catalog contains 814 published objects, with a barycentric Cartesian state at J2016.0 TDB (MJD 57388.5). Two W84 Horizons comparisons confirmed the epoch conversion. Both object residual RMS values fell below 0.032 arcsec. It serves as the only catalog in the current identity stage. The outcome of a matching chain with unexplained members is ambiguous. Every other accepted orbit has unresolved identity.

The analytic Kepler injection generator builds an independent ellipse, models topocentric light time and places it at the exposure times. Half the sample uses assumed missingness and positional noise. It injects catalog detections in small batches into the real background and reruns filtering, linking and fitting. Pixel-dependent extraction losses are unmeasured. Null controls permute whole observing nights while retaining timing offsets within each night.

[DES Y6 release repository](https://github.com/bernardinelli/des_tno_catalog/tree/8f254ca30fa0e8fc1576a5a9fad7300124d3b3ee)
[DESTNOSIM](https://github.com/bernardinelli/DESTNOSIM)
