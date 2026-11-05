# -*- coding: utf-8 -*-
"""Unit tests for Quantitative Strategy Validator Gate."""

import unittest
from .validator_gate import StrategyValidatorGate, ValidationReport


class TestStrategyValidatorGate(unittest.TestCase):
    def setUp(self):
        self.validator = StrategyValidatorGate(friction_rate=0.0050, terminal_time_cutoff="15:14:59")
        # Build clean baseline trade ledger satisfying all 11 stages
        self.clean_trades = []
        for i in range(100):
            entry = 100.0 + (i % 20)
            # 60% win rate
            exit_p = entry + 10.0 if i % 5 != 0 else entry - 8.0
            cost = (entry + exit_p) * 0.0050
            after_cost = (exit_p - entry) - cost
            self.clean_trades.append({
                "Date": f"2024-01-{(i%28)+1:02d}",
                "Instrument": "NIFTY",
                "Strike": 21500.0,
                "Expiry": "2024-01-25",
                "Type": "CE",
                "TradeType": "BUY",
                "EntryTime": "09:30:00",
                "ExitTime": "14:45:00",
                "EntryPrice": entry,
                "ExitPrice": exit_p,
                "after cost": round(after_cost, 2),
                "lotsize": 65,
                "lots": 10
            })

    def test_clean_strategy_passes_all_stages(self):
        report = self.validator.audit_trade_ledger(self.clean_trades)
        self.assertEqual(report.total_stages, 11)
        self.assertEqual(report.stages_passed, 11)
        self.assertEqual(report.stages_failed, 0)
        self.assertEqual(report.verdict, "PRODUCTION_GRADE")
        self.assertEqual(report.readiness_score, 100.0)

    def test_trade_boundary_clamping_violation(self):
        corrupted = [dict(t) for t in self.clean_trades]
        corrupted[10]["ExitTime"] = "15:20:00"  # Exiting after 15:14:59
        report = self.validator.audit_trade_ledger(corrupted)
        s2 = next(r for r in report.stage_results if r.stage_id == 2)
        self.assertFalse(s2.passed)
        self.assertNotEqual(report.verdict, "PRODUCTION_GRADE")

    def test_friction_leakage_detection(self):
        corrupted = [dict(t) for t in self.clean_trades]
        # Zero cost deduction (leakage)
        corrupted[5]["after cost"] = corrupted[5]["ExitPrice"] - corrupted[5]["EntryPrice"]
        report = self.validator.audit_trade_ledger(corrupted)
        s4 = next(r for r in report.stage_results if r.stage_id == 4)
        self.assertFalse(s4.passed)

    def test_synthetic_lookahead_trap_detection(self):
        corrupted = [dict(t) for t in self.clean_trades]
        corrupted[15]["_synthetic_leak"] = True
        report = self.validator.audit_trade_ledger(corrupted)
        s11 = next(r for r in report.stage_results if r.stage_id == 11)
        self.assertFalse(s11.passed)

    def test_monte_carlo_drawdown_cone(self):
        report = self.validator.audit_trade_ledger(self.clean_trades)
        self.assertGreater(report.mc_drawdown_95th, 0.0)
        self.assertGreaterEqual(report.mc_drawdown_99th, report.mc_drawdown_95th)


if __name__ == "__main__":
    unittest.main()
