# -*- coding: utf-8 -*-
"""
Unit Tests for Execution Microstructure & Market-Crossing Cost Simulator
"""

import unittest
from .microstructure_sim import (
    MicrostructureSimulator,
    OrderRequest,
    simulate_latency_cost_comparison,
    expected_latency_drift_bps,
)


class TestMicrostructureSimulator(unittest.TestCase):

    def setUp(self):
        self.sim = MicrostructureSimulator(daily_volume=4000000.0, annual_volatility=0.15)
        self.spot = 25000.0
        self.bid = 24995.0
        self.ask = 25005.0

    def test_market_impact_scaling(self):
        """Verify square-root scaling of market impact with order quantity."""
        impact_1 = self.sim.calculate_market_impact(qty=65, spot=self.spot)
        impact_4 = self.sim.calculate_market_impact(qty=260, spot=self.spot)

        self.assertGreater(impact_1, 0.0)
        # Quadrupling quantity should approximately double square-root impact (sqrt(4) = 2)
        self.assertAlmostEqual(impact_4 / impact_1, 2.0, places=1)

    def test_market_order_execution(self):
        """Verify market order pays half-spread and market impact."""
        req = OrderRequest(
            order_id="TEST_01", symbol="NIFTY", order_type="MARKET",
            side="BUY", qty=65, limit_price=None, timestamp_ms=1000.0,
            arrival_mid_price=self.spot
        )
        fill = self.sim.execute_order(req, self.bid, self.ask, queue_ahead_qty=100, traded_volume_window=200)

        self.assertTrue(fill.is_fully_filled)
        self.assertEqual(fill.spread_cost_pts, 5.0)  # (25005 - 24995)/2
        self.assertGreater(fill.fill_price, self.ask)
        self.assertGreater(fill.total_cost_bps, 0.0)

    def test_limit_order_queue_matching(self):
        """Verify limit order fills only when traded volume exceeds queue depth."""
        req = OrderRequest(
            order_id="TEST_02", symbol="NIFTY", order_type="LIMIT",
            side="BUY", qty=50, limit_price=self.bid, timestamp_ms=1000.0,
            arrival_mid_price=self.spot
        )
        # Case A: Volume insufficient -> Not filled
        fill_unfilled = self.sim.execute_order(req, self.bid, self.ask, queue_ahead_qty=100, traded_volume_window=80)
        self.assertFalse(fill_unfilled.is_fully_filled)

        # Case B: Volume sufficient -> Filled at bid
        fill_filled = self.sim.execute_order(req, self.bid, self.ask, queue_ahead_qty=100, traded_volume_window=200)
        self.assertTrue(fill_filled.is_fully_filled)
        self.assertEqual(fill_filled.fill_price, self.bid)

    def test_latency_cost_savings_attribution(self):
        """Saving from lower latency must match the random-walk expectation, not a typed-in number."""
        summary = simulate_latency_cost_comparison(n_orders=2000, base_spot=self.spot, lot_size=65,
                                                   annual_volatility=0.15, slow_latency_ms=350.0, fast_latency_ms=5.0)
        expected = expected_latency_drift_bps(0.15, 350.0) - expected_latency_drift_bps(0.15, 5.0)
        self.assertGreater(summary.cost_savings_bps, 0.0)
        self.assertAlmostEqual(summary.cost_savings_bps, expected, delta=0.1 + 0.15 * expected)

    def test_latency_saving_scales_with_volatility(self):
        """Double the volatility, roughly double the saving: the result must respond to inputs."""
        low = simulate_latency_cost_comparison(n_orders=2000, annual_volatility=0.15)
        high = simulate_latency_cost_comparison(n_orders=2000, annual_volatility=0.30)
        self.assertGreater(high.cost_savings_bps, 1.6 * low.cost_savings_bps)


if __name__ == "__main__":
    unittest.main()
