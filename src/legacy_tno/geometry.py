"""ICRS directions, angular residuals, and UTC observing-night convention."""
import numpy as np

ARCSEC = 180 * 3600 / np.pi


def unit(ra_deg, dec_deg):
    ra, dec = np.deg2rad(ra_deg), np.deg2rad(dec_deg)
    return np.stack((np.cos(ra) * np.cos(dec), np.sin(ra) * np.cos(dec), np.sin(dec)), axis=-1)


def sky(direction):
    x, y, z = np.moveaxis(direction, -1, 0)
    return np.rad2deg(np.arctan2(y, x)) % 360, np.rad2deg(np.arctan2(z, np.hypot(x, y)))


def basis(ra, dec):
    """Rows point east, north, and along the tangent-point direction."""
    return np.stack((unit(ra + 90, 0), unit(ra + 180, 90 - dec), unit(ra, dec)))


def project(direction, axes):
    coordinates = direction @ axes.T
    return coordinates[..., :2] / coordinates[..., 2:]


def angular_residual(predicted, observed):
    ra, dec = sky(observed)
    east = unit(ra + 90, np.zeros_like(ra))
    north = unit(ra + 180, 90 - dec)
    normal = np.sum(predicted * observed, axis=-1)
    return ARCSEC * np.stack((np.arctan2(np.sum(predicted * east, axis=-1), normal),
                              np.arctan2(np.sum(predicted * north, axis=-1), normal)), axis=-1)


def night_id(mjd_utc):
    """Integer MJD of noon-to-noon observing night in fixed UTC-4 Chile time."""
    return np.floor(np.asarray(mjd_utc) - 16 / 24).astype(np.int64)
