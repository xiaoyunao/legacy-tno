# Data schema

Each tile stores an immutable NumPy structured detection array plus the CP audit record. `det_id` encodes camera, exposure, CCD and source row. Exposure metadata and the tile audit resolve the CP path, image HDU, processing identifier and time. The camera is DECam, site W84, frame astrometric ICRS, and the extractor uses SEP 1.4.1. UTC MJD starts come from CP MJD-OBS and are checked against DATE-OBS. `mjd_mid_utc` adds half EXPTIME. Integer observing-night boundaries are at 16:00 UTC. Time gaps >120 days define the association seasons for the selected patch.

`ra_deg` and `dec_deg` are degrees and `x_pix`, `y_pix` use zero-based pixels. A single `sigma_arcsec` models both tangent components with zero correlation. `flux` and `flux_err` use calibrated aperture nanomaggies. `mag_ab`, `mag_err`, `snr`, `fwhm_arcsec`, `a_pix`, `b_pix`, extraction flags, raw integer DQ and aperture mask fraction describe the measurement. Alignment creates a separate copy.

The classified artifact contains Gaia source IDs, nearest Gaia separation, the same-band Sweep PSF flux excess in sigma, classification and reason bits. Reason bits include Gaia position, persistence, deep proximity, flux excess, low SNR and artifact criteria. Truth joins are separate from the classified table and blind linker.
