# -*- coding: utf-8 -*-
"""Tests for PSR, DSR and PBO."""
import unittest
import numpy as np
from .overfitting_stats import (
    probabilistic_sharpe_ratio,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    probability_of_backtest_overfitting,
)


class TestOverfittingStats(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.noise = rng.normal(0.0, 0.01, (1000, 50))
        self.srs = self.noise.mean(0) / self.noise.std(0, ddof=1)

    def test_psr_rises_with_edge(self):
        rng = np.random.default_rng(2)
        weak = rng.normal(0.0002, 0.01, 1000)
        strong = rng.normal(0.0015, 0.01, 1000)
        self.assertGreater(probabilistic_sharpe_ratio(strong), probabilistic_sharpe_ratio(weak))

    def test_dsr_punishes_best_of_many_noise(self):
        best = self.noise[:, int(np.argmax(self.srs))]
        psr = probabilistic_sharpe_ratio(best)
        dsr = deflated_sharpe_ratio(best, n_trials=50, sr_variance=float(self.srs.var()))
        self.assertGreater(psr, 0.95)      # looks great on its own
        self.assertLess(dsr, 0.95)         # not significant once 50 tries are counted

    def test_expected_max_sharpe_grows_with_trials(self):
        v = float(self.srs.var())
        self.assertLess(expected_max_sharpe(10, v), expected_max_sharpe(1000, v))
        self.assertEqual(expected_max_sharpe(1, v), 0.0)

    def test_pbo_high_for_noise_low_for_real_edge(self):
        noise_pbo = probability_of_backtest_overfitting(self.noise, n_blocks=10).pbo
        with_edge = self.noise.copy()
        with_edge[:, 0] += 0.002
        edge_pbo = probability_of_backtest_overfitting(with_edge, n_blocks=10).pbo
        self.assertGreater(noise_pbo, 0.3)
        self.assertLess(edge_pbo, 0.05)


if __name__ == "__main__":
    unittest.main()
