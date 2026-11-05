# -*- coding: utf-8 -*-
"""
Unit Tests for Bank Nifty Basket Cointegration & Statistical Arbitrage Engine
"""

import math
import unittest
import numpy as np
from .cointegration_engine import (
    calculate_ols,
    engle_granger_test,
    estimate_ornstein_uhlenbeck_halflife,
    calculate_spread_zscore,
    simulate_pairs_trade
)


class TestCointegrationEngine(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        self.n_bars = 400
        # Common stochastic trend I(1)
        self.trend = np.cumsum(np.random.normal(0.02, 1.0, self.n_bars))
        # Stationary mean-reverting noise I(0)
        self.spread = np.zeros(self.n_bars)
        for t in range(1, self.n_bars):
            self.spread[t] = 0.80 * self.spread[t-1] + np.random.normal(0, 0.5)

        self.x = 500.0 + self.trend
        self.y = 1.50 * self.x + 30.0 + self.spread

    def test_ols_estimation(self):
        """Verify closed-form OLS parameter recovery."""
        beta, alpha, residuals = calculate_ols(self.y, self.x)
        self.assertAlmostEqual(beta, 1.50, delta=0.05)
        # Residuals must sum to zero in OLS
        self.assertAlmostEqual(float(np.mean(residuals)), 0.0, places=5)
        self.assertEqual(len(residuals), self.n_bars)

    def test_cointegration_detection(self):
        """Verify cointegration detected on synthetic pair and rejected on independent walks."""
        # 1. Truly cointegrated pair
        res_coint = engle_granger_test(self.y, self.x)
        self.assertTrue(res_coint.is_cointegrated)
        self.assertLess(res_coint.t_stat, res_coint.critical_value_5pct)
        self.assertLess(res_coint.p_value_approx, 0.05)

        # 2. Independent random walks
        indep_y = 500.0 + np.cumsum(np.random.normal(0.01, 1.0, self.n_bars))
        res_indep = engle_granger_test(indep_y, self.x)
        self.assertFalse(res_indep.is_cointegrated)

    def test_ou_halflife_estimation(self):
        """Verify Ornstein-Uhlenbeck half-life estimation on mean-reverting spread."""
        hl = estimate_ornstein_uhlenbeck_halflife(self.spread)
        # For AR(1) coef = 0.80, half-life is approx -ln(2)/ln(0.80) ~= 3.1 bars
        self.assertGreater(hl, 1.0)
        self.assertLess(hl, 10.0)

    def test_pairs_trade_simulation(self):
        """Verify statistical arbitrage trading simulation and turnover friction deduction."""
        beta, alpha, residuals = calculate_ols(self.y, self.x)
        zscore = calculate_spread_zscore(residuals, window=40)
        trades = simulate_pairs_trade(residuals, zscore, entry_z=1.8, exit_z=0.4, friction_pct=0.0050)

        self.assertGreater(len(trades), 0)
        for t in trades:
            self.assertIn(t.direction, ["LONG_SPREAD", "SHORT_SPREAD"])
            # Friction must be strictly deducted
            self.assertLessEqual(t.net_pnl_pts, t.gross_pnl_pts)


if __name__ == "__main__":
    unittest.main()
