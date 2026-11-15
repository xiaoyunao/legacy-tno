"""Small deterministic scientific regression checks."""
import json
from pathlib import Path
import unittest

import numpy as np
from astropy.time import Time

from .catalog import DETECTION, cp_mask, mjd_mid
from .geometry import angular_residual, basis, night_id, sky, unit
from .link import depth_bins, search
from .orbit import GM, LIGHT_SPEED
from .validate import kepler_generator


class ScientificChecks(unittest.TestCase):
    def test_ra_wrap_and_projection(self):
        observed = unit(359.999, 60)
        predicted = unit(.001, 60)
        offset = angular_residual(predicted, observed)
        self.assertAlmostEqual(offset[0], 3.6, places=6)
        self.assertLess(abs(offset[1]), 1e-4)

    def test_midpoint_and_local_observing_night(self):
        start = Time("2018-09-01T23:59:50", scale="utc").mjd
        a, b, exp = mjd_mid(dict(DATE_OBS="", **{"MJD-OBS": start, "DATE-OBS":"2018-09-01T23:59:50",
                                                "EXPTIME":90}), 90)
        self.assertAlmostEqual((b-a)*86400,45,places=5)
        self.assertEqual(exp, 90)
        self.assertEqual(night_id(a),night_id(b))
        self.assertGreater(Time(b, format="mjd", scale="utc").tdb.mjd-b, .0007)

    def test_cp_dq_categories(self):
        science = np.ones((1,4))
        dq = np.array([[0, 5, 7, 8]])
        self.assertEqual(cp_mask(dq,science,science,"V5.5LS").tolist(), [[False,True,False,True]])
        with self.assertRaises(ValueError):
            cp_mask(dq,science,science,"V3.0.0")

    def test_depth_edges(self):
        bins=depth_bins(30,300,.05)
        self.assertEqual(bins[0][1],300)
        self.assertAlmostEqual(bins[-1][0],30)
        for high,low in zip(bins,bins[1:]):
            self.assertEqual(high[0],low[1])

    def test_analytic_high_eccentricity_track(self):
        cfg = json.loads((Path(__file__).parents[2]/"configs"/"pilot.json").read_text())["link"]
        field=dict(ra_deg=359.95,dec_deg=13.,core_radius_deg=1.4)
        axes=basis(field["ra_deg"],field["dec_deg"])
        t=58001+np.array([0,.03,8,8.07,18,18.04,28,28.02,39,39.04])
        earth_phase=(t-t[0])/365.25*2*np.pi
        observer=np.stack([np.cos(earth_phase),np.sin(earth_phase),np.zeros_like(t)],axis=1)
        radius=58.44
        model=kepler_generator(radius*axes[2],.8*axes[0]+.6*axes[1],.91,1.5,t[0])
        dt=t-radius/LIGHT_SPEED
        for _ in range(3):
            delta=model(dt)-observer
            norm=np.linalg.norm(delta,axis=1)
            dt=t-norm/LIGHT_SPEED
        ra,dec=sky(delta/norm[:,None])
        table=np.zeros(len(t),dtype=DETECTION)
        table["ra_deg"],table["dec_deg"]=ra,dec
        table["expnum"]=np.arange(len(t))
        table["night"]=night_id(t)
        table["sigma_arcsec"]=.16
        result=search(table,t,observer,field,cfg)
        self.assertTrue(result.chains, result.counts)
        self.assertEqual(result.truncated,[])
        highest=max(map(len,result.chains))
        self.assertGreaterEqual(highest,8)
        no_arc=table.copy()
        no_arc["night"]=1
        self.assertEqual(search(no_arc,t,observer,field,cfg).chains,{})


if __name__ == "__main__":
    unittest.main()
