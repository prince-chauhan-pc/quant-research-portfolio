# -*- coding: utf-8 -*-
"""Tests for SVI static-arbitrage checks."""
import unittest
import numpy as np
from .surface_model import check_butterfly_arbitrage, check_calendar_arbitrage, fit_svi_slice

# Known SVI slice with butterfly arbitrage (Axel Vogt's example, in Gatheral & Jacquier 2014)
VOGT = {"a": -0.0410, "b": 0.1331, "rho": 0.3060, "m": 0.3586, "sigma": 0.4153}
CLEAN = {"a": 0.04, "b": 0.1, "rho": -0.4, "m": 0.0, "sigma": 0.2}


class TestArbitrageChecks(unittest.TestCase):
    def test_vogt_slice_has_butterfly_arbitrage(self):
        res = check_butterfly_arbitrage(VOGT)
        self.assertFalse(res["arbitrage_free"])
        self.assertLess(res["min_g"], 0)

    def test_clean_slice_passes(self):
        self.assertTrue(check_butterfly_arbitrage(CLEAN)["arbitrage_free"])

    def test_calendar_detects_variance_drop(self):
        higher = dict(CLEAN, a=0.06)
        ok = check_calendar_arbitrage([{"T": 0.1, "params": CLEAN}, {"T": 0.3, "params": higher}])
        bad = check_calendar_arbitrage([{"T": 0.1, "params": higher}, {"T": 0.3, "params": CLEAN}])
        self.assertTrue(ok["arbitrage_free"])
        self.assertFalse(bad["arbitrage_free"])
        self.assertLess(bad["worst_variance_drop"], 0)

    def test_fitted_smile_is_checked(self):
        f, t = 25000.0, 7 / 365
        strikes = np.arange(23500, 26600, 100, dtype=float)
        k = np.log(strikes / f)
        ivs = 0.13 + 0.25 * k ** 2 - 0.08 * k
        fit = fit_svi_slice(strikes, f, t, ivs)
        res = check_butterfly_arbitrage(fit["params"], k_grid=np.linspace(k.min(), k.max(), 500))
        self.assertIn("arbitrage_free", res)
        self.assertLess(fit["rmse"], 0.01)


if __name__ == "__main__":
    unittest.main()
