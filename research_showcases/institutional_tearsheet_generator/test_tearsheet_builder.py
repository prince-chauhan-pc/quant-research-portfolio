# -*- coding: utf-8 -*-
"""Unit tests for Institutional Performance Tear Sheet Generator."""

import unittest
import tempfile
from pathlib import Path
from .tearsheet_builder import TearsheetBuilder, TearsheetScorecard


class TestTearsheetBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = TearsheetBuilder(initial_capital=10000000.0, risk_free_rate=0.065)
        # Synthetic daily PnL series: 252 days with modest upward drift
        self.daily_pnls = [25000.0 if i % 3 != 0 else -15000.0 for i in range(252)]

    def test_scorecard_metrics_calculation(self):
        scorecard = self.builder.compute_scorecard(self.daily_pnls)
        self.assertIsInstance(scorecard, TearsheetScorecard)
        self.assertGreater(scorecard.total_net_pnl, 0.0)
        self.assertGreater(scorecard.sharpe_ratio, 0.0)
        self.assertGreater(scorecard.sortino_ratio, 0.0)
        self.assertGreater(scorecard.win_rate_pct, 50.0)
        self.assertGreater(scorecard.profit_factor, 1.0)
        self.assertGreater(scorecard.max_drawdown_rs, 0.0)

    def test_monthly_returns_matrix(self):
        records = [
            {"date": "2024-01-15", "pnl": 50000.0},
            {"date": "2024-01-16", "pnl": 25000.0},
            {"date": "2024-02-10", "pnl": -10000.0},
            {"date": "2025-01-05", "pnl": 40000.0}
        ]
        matrix = self.builder.compute_monthly_matrix(records)
        self.assertIn(2024, matrix)
        self.assertIn(2025, matrix)
        self.assertAlmostEqual(matrix[2024]["Jan"], 0.75, places=2)
        self.assertAlmostEqual(matrix[2024]["Feb"], -0.10, places=2)
        self.assertAlmostEqual(matrix[2024]["Year"], 0.65, places=2)

    def test_underwater_drawdown_series(self):
        series = self.builder.compute_underwater_series([10000.0, -20000.0, 5000.0, 15000.0])
        self.assertEqual(len(series), 4)
        # Day 2 experienced a drawdown
        self.assertGreater(series[1]["drawdown_rs"], 0.0)
        self.assertGreater(series[1]["drawdown_pct"], 0.0)
        # Day 4 makes new equity peak (10010000)
        self.assertEqual(series[3]["drawdown_rs"], 0.0)

    def test_pdf_compilation(self):
        scorecard = self.builder.compute_scorecard(self.daily_pnls)
        matrix = self.builder.compute_monthly_matrix([{"date": "2024-01-15", "pnl": 100000.0}])
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = f.name

        ok = self.builder.export_pdf_report(pdf_path, "NIFTY SHORT STRADDLE", scorecard, matrix)
        if ok:
            p = Path(pdf_path)
            self.assertTrue(p.exists())
            self.assertGreater(p.stat().st_size, 1000)
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
