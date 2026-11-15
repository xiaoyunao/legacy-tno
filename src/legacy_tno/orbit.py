"""Anonymous Cartesian orbit fitting using DE440s perturbers and topocentric light time."""
from dataclasses import dataclass

import numpy as np
from astropy import units as u
from astropy.coordinates import EarthLocation, get_body_barycentric_posvel, solar_system_ephemeris
from astropy.time import Time
from astropy.utils import iers
from scipy.integrate import solve_ivp
from scipy.interpolate import CubicHermiteSpline
from scipy.optimize import least_squares

from .geometry import angular_residual

# JPL DE440 system gravitational parameters in km^3 s^-2 (satellites grouped
# at their planetary-system barycentre). The AU has its exact IAU definition.
GM = {
    "sun": 132712440041.279,
    "mercury": 22031.868551, "venus": 324858.592000,
    "earth-moon-barycenter": 403503.235625, "mars": 42828.375816,
    "jupiter": 126712764.100000, "saturn": 37940584.841800,
    "uranus": 5794556.400000, "neptune": 6836527.100580,
}
AU_KM = u.au.to(u.km)
GM = {body: value * 86400**2 / AU_KM**3 for body, value in GM.items()}
LIGHT_SPEED = 299792.458 * 86400 / AU_KM
# Blanco / DECam, MPC W84. Topocentric routine uses ellipsoidal coordinates.
SITE = EarthLocation.from_geodetic(-70.8065 * u.deg, -30.1690 * u.deg, 2207 * u.m)


def observatory(mjd, kernel):
    iers.conf.auto_download = False
    utc = Time(mjd, format="mjd", scale="utc")
    with solar_system_ephemeris.set(kernel):
        earth, _ = get_body_barycentric_posvel("earth", utc.tdb)
    site, _ = SITE.get_gcrs_posvel(utc)
    return utc.tdb.mjd, (earth.xyz.to_value(u.au) + site.xyz.to_value(u.au)).T


class Dynamics:
    def __init__(self, start, end, kernel):
        grid = np.arange(np.floor(start) - 3, np.ceil(end) + 4, 0.5)
        with solar_system_ephemeris.set(kernel):
            time = Time(grid, format="mjd", scale="tdb")
            states = [get_body_barycentric_posvel(body, time) for body in GM]
        position = np.stack([p.xyz.to_value(u.au).T for p, _ in states], axis=1)
        velocity = np.stack([v.xyz.to_value(u.au/u.day).T for _, v in states], axis=1)
        self.planets = CubicHermiteSpline(grid, position, velocity, extrapolate=False)
        self.mu = np.asarray(list(GM.values()))

    def derivative(self, epoch, state):
        delta = self.planets(epoch) - state[:3]
        acceleration = np.sum(delta * (self.mu / np.linalg.norm(delta, axis=1)**3)[:, None], axis=0)
        return np.r_[state[3:], acceleration]

    def propagate(self, state, epoch, times):
        times = np.atleast_1d(times)
        states = np.empty((times.size, 6))
        states[times == epoch] = state
        for direction in (-1, 1):
            use = (times - epoch) * direction > 0
            if np.any(use):
                stop = np.max(times[use]) if direction > 0 else np.min(times[use])
                integration = solve_ivp(self.derivative, (epoch, stop), state,
                                        method="DOP853", rtol=2e-11, atol=1e-13,
                                        dense_output=True, max_step=25)
                if not integration.success:
                    raise RuntimeError(integration.message)
                states[use] = integration.sol(times[use]).T
        return states

    def apparent(self, state, epoch, times, observer):
        # Solve retarded emission time. Observer remains at reception.
        emit = times - np.linalg.norm(state[:3] - observer, axis=1) / LIGHT_SPEED
        for _ in range(3):
            point = self.propagate(state, epoch, emit)
            delta = point[:, :3] - observer
            distance = np.linalg.norm(delta, axis=1)
            emit = times - distance / LIGHT_SPEED
        return delta / distance[:, None]


@dataclass
class Fit:
    epoch: float
    state: np.ndarray
    offsets: np.ndarray
    errors: np.ndarray
    convergence: bool
    jacobian: np.ndarray

    @property
    def chi2(self):
        return float(np.sum((self.offsets / self.errors)**2))

    @property
    def dof(self):
        return self.offsets.size - 6

    @property
    def rms(self):
        return float(np.sqrt(np.mean(self.offsets**2)))

    def reduced_chi2(self):
        return self.chi2 / self.dof if self.dof > 0 else None


def fit(dynamics, initial_state, epoch, times, observers, directions, sigma, max_nfev=45):
    scale = np.array([1.0, 1.0, 1.0, .01, .01, .01])
    errors = np.broadcast_to(np.asarray(sigma)[:, None], (len(times), 2))

    def residual(scaled):
        model = dynamics.apparent(scaled * scale, epoch, times, observers)
        return (angular_residual(model, directions) / errors).ravel()

    result = least_squares(residual, initial_state / scale, diff_step=1e-5,
                           max_nfev=max_nfev, ftol=1e-7, gtol=1e-6, xtol=1e-8)
    return Fit(epoch, result.x * scale, result.fun.reshape(-1, 2) * errors,
               errors, result.success, result.jac / scale)


def heliocentric_elements(dynamics, state, epoch):
    r = state[:3] - dynamics.planets(epoch)[0]
    v = state[3:] - dynamics.planets(epoch, 1)[0]
    obliquity = np.deg2rad(23.439291111)
    c, s = np.cos(obliquity), np.sin(obliquity)
    rotation = np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
    r, v = rotation @ r, rotation @ v
    mu = GM["sun"]
    distance = np.linalg.norm(r)
    h = np.cross(r, v)
    hnorm = np.linalg.norm(h)
    evec = np.cross(v, h) / mu - r / distance
    eccentricity = np.linalg.norm(evec)
    energy = np.dot(v, v)/2 - mu / distance
    a = -mu/(2*energy) if energy != 0 else None
    node = np.cross([0, 0, 1], h)
    inclination = np.rad2deg(np.arctan2(np.hypot(h[0], h[1]), h[2]))
    omega = lan = mean = None
    if np.linalg.norm(node) > 1e-14 and eccentricity > 1e-10:
        lan = np.rad2deg(np.arctan2(node[1], node[0])) % 360
        omega = np.rad2deg(np.arctan2(np.dot(np.cross(node, evec), h) / hnorm,
                                     np.dot(node, evec))) % 360
    if a and a > 0 and 1e-10 < eccentricity < 1:
        E = np.arctan2(np.dot(r, v) / (eccentricity * np.sqrt(mu * a)),
                       (1 - distance/a)/eccentricity)
        mean = np.rad2deg(E - eccentricity*np.sin(E)) % 360
    return dict(r_au=distance, a_au=a, e=eccentricity, i_deg=inclination,
                node_deg=lan, argperi_deg=omega, mean_anomaly_deg=mean,
                q_au=hnorm**2 / (mu * (1 + eccentricity)), bound=energy < 0,
                frame="heliocentric ecliptic J2000 osculating")
