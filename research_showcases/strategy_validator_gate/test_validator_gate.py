# -*- coding: utf-8 -*-
"""Unit tests for the strategy validation gate."""

import unittest
import datetime as dt

from .validator_gate import (
    DEFAULT_KNOWN_LOT_SIZES, PNL_COLUMN, StrategyValidatorGate, parse_trade_time,
)


def _losing_ledger(with_size: bool):
    """200 short calls sold at 100 and bought back at 500: about -403 points each after cost."""
    trades = []
    for _ in range(200):
        entry, exit_p = 100.0, 500.0
        after = (entry - exit_p) - (entry + exit_p) * 0.0050
        row = {
            "Date": "2025-01-01", "Instrument": "NIFTY", "Strike": 25000, "Expiry": "2025-01-07",
            "Type": "CE", "TradeType": "SELL", "EntryTime": "09:30:00", "ExitTime": "15:00:00",
            "EntryPrice": entry, "ExitPrice": exit_p, PNL_COLUMN: round(after, 2),
        }
        if with_size:
            row.update({"lots": 1, "lotsize": 65})
        trades.append(row)
    return trades


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
                PNL_COLUMN: round(after_cost, 2),
                "lotsize": 65,
                "lots": 10
            })

    def test_clean_strategy_passes_all_stages(self):
        report = self.validator.audit_trade_ledger(self.clean_trades)
        self.assertEqual(report.total_stages, 11)
        self.assertEqual(report.stages_passed, 11)
        self.assertEqual(report.stages_failed, 0)
        self.assertEqual(report.verdict, "PASS")
        self.assertEqual(report.readiness_score, 100.0)

    def test_trade_boundary_clamping_violation(self):
        corrupted = [dict(t) for t in self.clean_trades]
        corrupted[10]["ExitTime"] = "15:25:00"  # Exiting after 15:14:59
        report = self.validator.audit_trade_ledger(corrupted)
        s2 = next(r for r in report.stage_results if r.stage_id == 2)
        self.assertFalse(s2.passed)
        self.assertNotEqual(report.verdict, "PASS")

    def test_friction_leakage_detection(self):
        corrupted = [dict(t) for t in self.clean_trades]
        # Zero cost deduction (leakage)
        corrupted[5][PNL_COLUMN] = corrupted[5]["ExitPrice"] - corrupted[5]["EntryPrice"]
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
        # Clean ledger has lots and lotsize, so the drawdown is in rupees.
        self.assertEqual(report.mc_drawdown_unit, "INR")

    def test_lot_count_must_be_positive_whole_number(self):
        for bad in (0, -1, 2.5):
            corrupted = [dict(t) for t in self.clean_trades]
            corrupted[3]["lots"] = bad
            report = self.validator.audit_trade_ledger(corrupted)
            s7 = next(r for r in report.stage_results if r.stage_id == 7)
            self.assertFalse(s7.passed, f"lots={bad} should fail stage 7")

    def test_drawdown_in_rupees_fails_large_loss(self):
        # -80,600 points x 65 = about INR 52 L of drawdown, above 25% of INR 1 Cr.
        report = self.validator.audit_trade_ledger(_losing_ledger(with_size=True))
        s10 = next(r for r in report.stage_results if r.stage_id == 10)
        self.assertEqual(report.mc_drawdown_unit, "INR")
        self.assertGreater(report.mc_drawdown_95th, 2_500_000.0)
        self.assertFalse(s10.passed)

    def test_drawdown_with_point_value_fails_large_loss(self):
        report = self.validator.audit_trade_ledger(_losing_ledger(with_size=False), point_value=65.0)
        s10 = next(r for r in report.stage_results if r.stage_id == 10)
        self.assertEqual(report.mc_drawdown_unit, "INR")
        self.assertFalse(s10.passed)

    def test_drawdown_with_points_limit_fails_large_loss(self):
        report = self.validator.audit_trade_ledger(_losing_ledger(with_size=False), max_dd_limit_pts=5000.0)
        s10 = next(r for r in report.stage_results if r.stage_id == 10)
        self.assertEqual(report.mc_drawdown_unit, "pts")
        self.assertAlmostEqual(report.mc_drawdown_95th, 80600.0, delta=1.0)
        self.assertFalse(s10.passed)

    def test_drawdown_without_unit_fails_closed(self):
        # The old code compared 80,600 points with INR 25 L and passed this ledger.
        report = self.validator.audit_trade_ledger(_losing_ledger(with_size=False))
        s10 = next(r for r in report.stage_results if r.stage_id == 10)
        self.assertFalse(s10.passed)
        self.assertIn("point_value", s10.detail)

    def test_small_drawdown_in_points_passes(self):
        report = self.validator.audit_trade_ledger(self.clean_trades, max_dd_limit_pts=1000.0)
        s10 = next(r for r in report.stage_results if r.stage_id == 10)
        self.assertEqual(report.mc_drawdown_unit, "pts")
        self.assertTrue(s10.passed)

    def _stage(self, report, stage_id):
        return next(r for r in report.stage_results if r.stage_id == stage_id)

    def _with_times(self, entry, exit_value):
        rows = [dict(t) for t in self.clean_trades]
        rows[7]["EntryTime"] = entry
        rows[7]["ExitTime"] = exit_value
        return rows

    def test_exit_times_are_parsed_not_compared_as_text(self):
        # As text, "9:45" > "15:14:59" and the old check called it late.
        cases = [
            ("9:15", "9:45", True),                                   # short hour, morning exit
            ("09:30:00", "15:14:59", True),                           # exactly at the cutoff
            ("09:30:00", "15:15:00", False),                          # one second late
            ("2025-01-07 09:30:00", "2025-01-07 15:00:00", True),     # full date-time, on time
            ("2025-01-07T09:30:00", "2025-01-07T15:25:00", False),    # full date-time, late
            ("09:30:00", "", False),                                  # empty exit used to pass
            ("09:30:00", None, False),                                # missing exit
            ("09:30:00", "2025-01-07", False),                        # a date is not a time
            ("09:30:00", "half past two", False),                     # unreadable
            ("09:30:00", dt.time(14, 0), True),                       # time object
        ]
        for entry, exit_value, ok in cases:
            with self.subTest(exit=exit_value):
                s2 = self._stage(self.validator.audit_trade_ledger(self._with_times(entry, exit_value)), 2)
                self.assertEqual(s2.passed, ok, s2.detail)

    def test_exit_after_entry_uses_parsed_times(self):
        cases = [
            ("9:30", "10:05", True),                                  # text order would say 10:05 < 9:30
            ("14:00:00", "13:59:59", False),
            ("14:00:00", "14:00:00", False),
            ("2025-01-06 14:30:00", "2025-01-07 10:00:00", True),     # held overnight
            ("2025-01-07 10:00:00", "2025-01-06 14:30:00", False),
            ("", "14:45:00", False),                                  # missing entry
        ]
        for entry, exit_value, ok in cases:
            with self.subTest(entry=entry, exit=exit_value):
                s3 = self._stage(self.validator.audit_trade_ledger(self._with_times(entry, exit_value)), 3)
                self.assertEqual(s3.passed, ok, s3.detail)

    def test_parse_trade_time(self):
        self.assertEqual(parse_trade_time("9:30"), (None, dt.time(9, 30)))
        self.assertEqual(parse_trade_time(" 15:14:59 "), (None, dt.time(15, 14, 59)))
        self.assertEqual(parse_trade_time("2025-01-07 15:00:00"), (dt.date(2025, 1, 7), dt.time(15, 0)))
        self.assertEqual(parse_trade_time(dt.datetime(2025, 1, 7, 9, 31)), (dt.date(2025, 1, 7), dt.time(9, 31)))
        for bad in ("", "   ", None, "2025-01-07", "25:00", 930):
            self.assertIsNone(parse_trade_time(bad), bad)

    def test_bad_cutoff_is_refused(self):
        for bad in ("", "3pm", "2025-01-07 15:14:59"):
            with self.assertRaises(ValueError):
                StrategyValidatorGate(terminal_time_cutoff=bad)
        self.assertTrue(StrategyValidatorGate(terminal_time_cutoff="15:14").audit_trade_ledger(self.clean_trades))

    def test_known_lot_sizes_include_history(self):
        # Sensex was 10 a lot until 19 Nov 2024 and is 20 now; Nifty 65, Bank Nifty 30.
        for size in (10, 20, 65, 30, 75, 25, 15, 60, 120, 65.0):
            with self.subTest(lotsize=size):
                rows = [dict(t, lotsize=size) for t in self.clean_trades]
                self.assertTrue(self._stage(self.validator.audit_trade_ledger(rows), 6).passed)
        for size in (35, 64, 65.5, "abc"):
            with self.subTest(lotsize=size):
                rows = [dict(t) for t in self.clean_trades]
                rows[0]["lotsize"] = size
                self.assertFalse(self._stage(self.validator.audit_trade_ledger(rows), 6).passed)
        self.assertIn(10, DEFAULT_KNOWN_LOT_SIZES)

    def test_custom_known_lot_sizes(self):
        gate = StrategyValidatorGate(known_lot_sizes=[35])
        rows = [dict(t, lotsize=35) for t in self.clean_trades]
        self.assertTrue(self._stage(gate.audit_trade_ledger(rows), 6).passed)
        self.assertFalse(self._stage(self.validator.audit_trade_ledger(rows), 6).passed)

    def test_ledger_needs_net_points_column(self):
        rows = [dict(t) for t in self.clean_trades]
        for r in rows:
            r["after cost"] = r.pop(PNL_COLUMN)
        s1 = self._stage(self.validator.audit_trade_ledger(rows), 1)
        self.assertFalse(s1.passed)
        self.assertIn(PNL_COLUMN, s1.detail)

    def test_backtester_ledger_passes_the_gate(self):
        """A ledger written by the backtester uses the same column names the gate needs."""
        try:  # pytest imports the package; unittest discover imports each module folder on its own
            from ..point_in_time_backtester import PointInTimeBacktester
        except ImportError:
            from point_in_time_backtester import PointInTimeBacktester
        bt = PointInTimeBacktester(initial_capital=10000000.0, strategy_type="STRADDLE")
        trade = bt.simulate_trade(
            date="2026-09-01", instrument="NIFTY", strike=25000.0, expiry="2026-09-08",
            option_type="CE", trade_type="SELL", entry_time="9:20", exit_time="15:10",
            entry_price=100.0, exit_price=60.0, lot_size=65,
        )
        header, line = bt.export_canonical_11_col_ledger([trade]).splitlines()
        row = dict(zip(header.split(","), line.split(",")))
        self.assertEqual([c for c in StrategyValidatorGate.MANDATORY_COLUMNS if c not in row], [])
        report = self.validator.audit_trade_ledger([row], max_dd_limit_pts=1000.0)
        for stage_id in (1, 2, 3, 4, 5):
            self.assertTrue(self._stage(report, stage_id).passed, self._stage(report, stage_id).detail)


if __name__ == "__main__":
    unittest.main()
