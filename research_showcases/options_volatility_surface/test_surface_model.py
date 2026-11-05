# -*- coding: utf-8 -*-
"""
Unit Tests for Options Implied Volatility Surface & Greeks Engine
"""

import math
import unittest
import numpy as np
from .surface_model import (
    black_scholes_price,
    implied_volatility,
    calculate_greeks,
    fit_svi_slice,
    filter_option_quotes,
    calculate_gex_profile
)


class TestOptionsIVSurface(unittest.TestCase):

    def setUp(self):
        self.spot = 25000.0
        self.strike = 25000.0
        self.T = 7.0 / 365.0
        self.r = 0.065
        self.sigma = 0.15

    def test_bs_pricing_and_inversion(self):
        """Verify Black-Scholes pricing and exact implied volatility numerical inversion."""
        call_p = black_scholes_price(self.spot, self.strike, self.T, self.r, self.sigma, "CE")
        put_p = black_scholes_price(self.spot, self.strike, self.T, self.r, self.sigma, "PE")

        self.assertGreater(call_p, 0.0)
        self.assertGreater(put_p, 0.0)

        # Inversion
        solved_call_iv = implied_volatility(call_p, self.spot, self.strike, self.T, self.r, "CE")
        solved_put_iv = implied_volatility(put_p, self.spot, self.strike, self.T, self.r, "PE")

        self.assertIsNotNone(solved_call_iv)
        self.assertIsNotNone(solved_put_iv)
        self.assertAlmostEqual(solved_call_iv, self.sigma, places=3)
        self.assertAlmostEqual(solved_put_iv, self.sigma, places=3)

    def test_greeks_properties(self):
        """Verify standard Greeks boundaries (Delta ~ 0.5 ATM, Gamma > 0, Vega > 0)."""
        ce_g = calculate_greeks(self.spot, self.strike, self.T, self.r, self.sigma, "CE")
        pe_g = calculate_greeks(self.spot, self.strike, self.T, self.r, self.sigma, "PE")

        # ATM Delta
        self.assertAlmostEqual(ce_g.delta, 0.51, places=1)
        self.assertAlmostEqual(pe_g.delta, -0.49, places=1)

        # Gamma identical for Call and Put
        self.assertGreater(ce_g.gamma, 0.0)
        self.assertAlmostEqual(ce_g.gamma, pe_g.gamma, places=5)

        # Vega positive
        self.assertGreater(ce_g.vega, 0.0)

    def test_svi_surface_fitting(self):
        """Verify SVI calibration converges on market strike slice."""
        strikes = np.array([24400, 24600, 24800, 25000, 25200, 25400, 25600])
        market_ivs = np.array([0.165, 0.155, 0.146, 0.140, 0.136, 0.134, 0.133])

        fit = fit_svi_slice(strikes, forward_F=25000.0, T=self.T, market_ivs=market_ivs)
        self.assertIn("rmse", fit)
        self.assertLess(fit["rmse"], 0.005)  # RMSE under 0.50% vol
        self.assertGreater(fit["params"]["b"], 0.0)

    def test_microstructure_quote_filter(self):
        """Verify quote filtering drops zero-bid and inverted quotes."""
        raw_quotes = [
            {"strike": 25000, "bid": 120.0, "ask": 122.0, "type": "CE"},  # Valid
            {"strike": 26000, "bid": 0.0, "ask": 2.5, "type": "CE"},      # Zero bid (drop)
            {"strike": 24000, "bid": 1050.0, "ask": 1040.0, "type": "CE"} # Inverted book (drop)
        ]
        clean = filter_option_quotes(raw_quotes, self.spot)
        self.assertEqual(len(clean), 1)
        self.assertEqual(clean[0]["strike"], 25000)

    def test_gex_calculation(self):
        """Verify Dealer Gamma Exposure calculation across strikes."""
        oi_map = {
            24800.0: {"CE": 500000, "PE": 1200000},
            25000.0: {"CE": 2500000, "PE": 2200000},
            25200.0: {"CE": 1800000, "PE": 400000}
        }
        gex_res = calculate_gex_profile(self.spot, oi_map, self.T)
        self.assertIn("total_gex_cr", gex_res)
        self.assertEqual(len(gex_res["profile"]), 3)


if __name__ == "__main__":
    unittest.main()
