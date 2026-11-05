# -*- coding: utf-8 -*-
"""
Unit Tests for Market Regime Classification & Volatility Allocation Engine
"""

import unittest
import numpy as np
from .regime_classifier import (
    extract_regime_features,
    MarketRegimeClassifier,
    simulate_counterfactual_drawdown_attribution
)


class TestMarketRegimeClassifier(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        self.n_bars = 500
        self.close = np.full(self.n_bars, 25000.0)
        self.high = np.full(self.n_bars, 25020.0)
        self.low = np.full(self.n_bars, 24980.0)
        self.iv = np.full(self.n_bars, 0.14)

        # Inject high-volatility crash regime in bars 250 to 350
        for t in range(1, self.n_bars):
            vol = 0.45 if 250 <= t <= 350 else 0.12
            ret = np.random.normal(0, vol / np.sqrt(252 * 375))
            self.close[t] = self.close[t-1] * (1.0 + ret)
            self.high[t] = self.close[t] * (1.0 + abs(ret) * 0.9)
            self.low[t] = self.close[t] * (1.0 - abs(ret) * 0.9)
            self.iv[t] = 0.30 if 250 <= t <= 350 else 0.14

    def test_feature_extraction(self):
        """Verify feature matrix dimensions and numerical stability."""
        X = extract_regime_features(self.close, self.high, self.low, self.iv, window=20)
        self.assertEqual(X.shape, (self.n_bars, 4))
        self.assertTrue(np.all(np.isfinite(X)))

    def test_kmeans_clustering_properties(self):
        """Verify K-Means yields 3 clusters sorted monotonically by Realized Volatility."""
        X = extract_regime_features(self.close, self.high, self.low, self.iv, window=20)
        clf = MarketRegimeClassifier(n_clusters=3).fit(X)
        labels = clf.predict(X)

        self.assertEqual(len(np.unique(labels)), 3)
        # Cluster 0 must have lower average RV than Cluster 2
        rv_col = X[:, 0]
        mean_rv_0 = np.mean(rv_col[labels == 0])
        mean_rv_2 = np.mean(rv_col[labels == 2])
        self.assertLess(mean_rv_0, mean_rv_2)

    def test_drawdown_reduction_attribution(self):
        """Regime gating, applied with a one-bar lag (no lookahead), must cut max drawdown by at least 20%."""
        X = extract_regime_features(self.close, self.high, self.low, self.iv, window=20)
        clf = MarketRegimeClassifier(n_clusters=3).fit(X)
        labels = clf.predict(X)

        # Baseline unhedged returns: steady theta gains (+0.3 pts/bar), severe crash during shock (-1.8 pts/bar)
        short_gamma_ret = np.where((250 <= np.arange(self.n_bars)) & (np.arange(self.n_bars) <= 350), -1.8, 0.30)
        res = simulate_counterfactual_drawdown_attribution(short_gamma_ret, labels)

        self.assertGreater(res.dd_reduction_pct, 20.0)  # Significant DD reduction
        self.assertLess(res.gated_max_dd_pct, res.baseline_max_dd_pct)
        self.assertGreater(res.gated_sharpe, res.baseline_sharpe)

    def test_zero_lag_is_rejected(self):
        """Using a bar's own label to size that same bar is lookahead and must raise."""
        X = extract_regime_features(self.close, self.high, self.low, self.iv, window=20)
        labels = MarketRegimeClassifier(n_clusters=3).fit(X).predict(X)
        with self.assertRaises(ValueError):
            simulate_counterfactual_drawdown_attribution(np.zeros(self.n_bars), labels, lag_bars=0)


if __name__ == "__main__":
    unittest.main()
