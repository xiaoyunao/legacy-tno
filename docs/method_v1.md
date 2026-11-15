# Search method

The extractor uses CP astrometry first. A per-CCD robust translation is measured against Gaia EDR3 after proper-motion propagation and observer-dependent parallax. Pre-existing Legacy offset columns are not applied. Seeing/SNR and the Gaia scatter determine the uncertainty floor. The CCD position and magnitude residual distributions make trends inspectable.

A unique close Gaia match or independent repeated detections around a single fixed Sweep position can establish static evidence. Cross-night persistence requires three independent nights and a 30-day span. A close deep match without persistence remains ambiguous. Significant flux excess over the same-band Sweep PSF model can protect a transient from a static match. Model flux for extended sources is excluded from that test.

Directions are projected onto one tangent plane per field. NERSC reductions use a physical-exposure key. The blind linker checks a pair of nights using inverse-depth parallax and the solar escape speed. The third-night envelope evaluates depth and radial-velocity box corners and adds acceleration and measurement padding. A weighted bounded fit solves the linearized plane equations, then a fourth night must add a compatible detection. The search gates the first detection to the core disk, deduplicates exact detection sets, and records per-bin limits. The model currently gates tangent depth over the engineering distance interval. Final fits gate the actual heliocentric distance.

The orbit fitter optimizes six SSB ICRS Cartesian parameters. DOP853 propagates under DE440s Sun and planetary-system positions, including the Earth–Moon barycenter. Astropy converts reception UTC to TDB and computes the CTIO observer offset from the geocenter. The fitter iterates retarded time and minimizes RA cos Dec and Dec residuals. The output gives Cartesian fit parameters and heliocentric ecliptic J2000 osculating elements. A local covariance is available for well-conditioned derivatives. Short arcs and nonbound solutions are labeled ambiguous.

[Bernardinelli et al. 2020](https://arxiv.org/html/1909.01478v2)  
[JPL DE440s](https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/)  
[Find_Orb command-line documentation](https://www.projectpluto.com/fo_usage.htm)
