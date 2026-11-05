# -*- coding: utf-8 -*-
"""Tests for the Johansen trace test."""
import unittest
import numpy as np
from .cointegration_engine import johansen_test


class TestJohansen(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(11)
        t = 800
        common = np.cumsum(rng.normal(size=t))
        self.coint_basket = np.column_stack([
            100 + common + rng.normal(scale=0.5, size=t),
            80 + 0.7 * common + rng.normal(scale=0.5, size=t),
            50 + np.cumsum(rng.normal(size=t)),
        ])
        self.independent = 100 + np.cumsum(np.random.default_rng(3).normal(size=(t, 3)), axis=0)

    def test_finds_relation_in_cointegrated_basket(self):
        res = johansen_test(self.coint_basket, k_ar_diff=1)
        self.assertGreaterEqual(res.rank_95, 1)
        self.assertGreater(res.trace_stats[0], res.crit_95[0])

    def test_no_relation_in_independent_walks(self):
        res = johansen_test(self.independent, k_ar_diff=1)
        self.assertEqual(res.rank_95, 0)

    def test_hedge_vector_recovers_ratio(self):
        two = self.coint_basket[:, :2]
        res = johansen_test(two, k_ar_diff=1)
        # spread = y1 + w * y2 is stationary, true w = -1/0.7
        self.assertAlmostEqual(res.first_vector[1], -1 / 0.7, delta=0.1)

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            johansen_test(np.ones((100, 1)))


if __name__ == "__main__":
    unittest.main()
