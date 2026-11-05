# -*- coding: utf-8 -*-
"""
Unit Tests for Point-in-Time Vectorized Backtester
"""

import unittest
from .backtester import PointInTimeBacktester, BacktestTrade


class TestPointInTimeBacktester(unittest.TestCase):

    def setUp(self):
        self.bt_straddle = PointInTimeBacktester(initial_capital=10000000.0, strategy_type="STRADDLE")
        self.bt_naked = PointInTimeBacktester(initial_capital=10000000.0, strategy_type="NAKED_SHORT")
        self.bt_spread = PointInTimeBacktester(initial_capital=10000000.0, strategy_type="HEDGED_SPREAD")

    def test_direct_integer_margin_sizing(self):
        """Verify direct integer sizing floor(Cap / Margin) with zero arbitrary cash haircuts."""
        self.assertEqual(self.bt_straddle.calculate_lot_allocation(), 40)   # 1.0Cr / 2.5L = 40
        self.assertEqual(self.bt_naked.calculate_lot_allocation(), 55)      # 1.0Cr / 1.8L = 55
        self.assertEqual(self.bt_spread.calculate_lot_allocation(), 100)    # 1.0Cr / 1.0L = 100

    def test_turnover_friction_math(self):
        """Verify 0.50% turnover friction deduction on entry + exit premium."""
        trade = self.bt_straddle.simulate_trade(
            date="2026-09-01", instrument="NIFTY", strike=25000.0, expiry="02-Sep-2026",
            option_type="CE", trade_type="SELL", entry_time="09:20", exit_time="15:10",
            entry_price=100.0, exit_price=50.0, lot_size=65, allocated_lots=10
        )
        # Gross = 100 - 50 = 50.0
        # Friction = (100 + 50) * 0.0050 = 0.75 points
        # After cost = 50.0 - 0.75 = 49.25 points
        self.assertEqual(trade.after_cost_pnl, 49.25)
        # Net Rupee = 49.25 * (10 * 65) = 49.25 * 650 = 32012.50
        self.assertEqual(trade.net_pnl_rs, 32012.50)

    def test_canonical_11_column_ledger_format(self):
        """Verify output ledger matches exact 11 columns required by institutional auditor."""
        trade = self.bt_straddle.simulate_trade(
            date="2026-09-01", instrument="NIFTY", strike=25000.0, expiry="02-Sep-2026",
            option_type="PE", trade_type="SELL", entry_time="09:20", exit_time="15:10",
            entry_price=120.0, exit_price=70.0, lot_size=65, allocated_lots=10
        )
        csv_text = self.bt_straddle.export_canonical_11_col_ledger([trade])
        lines = csv_text.strip().split("\n")
        expected_header = "Date,Instrument,Strike,Expiry,Type,TradeType,EntryTime,ExitTime,EntryPrice,ExitPrice,after cost"
        self.assertEqual(lines[0], expected_header)
        self.assertEqual(len(lines[0].split(",")), 11)
        self.assertEqual(len(lines[1].split(",")), 11)

    def test_performance_evaluation(self):
        """Verify Sharpe, Win Rate, and Drawdown calculations."""
        trades = []
        for i in range(10):
            # 7 wins, 3 losses
            exit_p = 40.0 if i < 7 else 120.0
            t = self.bt_straddle.simulate_trade(
                date=f"2026-09-{i+1:02d}", instrument="NIFTY", strike=25000.0,
                expiry="02-Sep-2026", option_type="CE", trade_type="SELL",
                entry_time="09:20", exit_time="15:10", entry_price=100.0,
                exit_price=exit_p, lot_size=65, allocated_lots=10
            )
            trades.append(t)

        res = self.bt_straddle.evaluate_performance(trades)
        self.assertEqual(res.total_trades, 10)
        self.assertEqual(res.win_rate_pct, 70.0)
        self.assertGreater(res.sharpe_ratio, 0.0)
        self.assertGreater(res.profit_factor, 1.0)


if __name__ == "__main__":
    unittest.main()
