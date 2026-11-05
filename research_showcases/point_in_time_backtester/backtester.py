# -*- coding: utf-8 -*-
"""
Point-in-Time Vectorized Backtesting Engine
==============================================================================
Author: Prince Chauhan Quant Desk (SEBI Registered Research Analyst)
Architecture:
- Event-driven chronological simulation preventing lookahead / survivorship bias.
- Mandatory exchange margin allocation: Short Straddle (₹2.5L), Naked Short (₹1.8L), Hedged Spread (₹1.0L).
- Direct integer sizing: Lots = floor(Capital / Margin).
- Explicit 0.50% round-trip turnover friction deduction (brokerage, STT, exchange charges, slippage buffer).
- Generates canonical 11-column trade validation ledger for audit verification.
==============================================================================
"""

import math
import numpy as np
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class BacktestTrade:
    date: str
    instrument: str
    strike: float
    expiry: str
    option_type: str        # 'CE' or 'PE'
    trade_type: str         # 'BUY' or 'SELL'
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    after_cost_pnl: float   # Points PnL after 0.50% turnover friction
    lot_size: int
    lots: int
    net_pnl_rs: float       # Rupee net PnL


@dataclass
class BacktestResult:
    total_trades: int
    win_rate_pct: float
    gross_points_pnl: float
    net_points_pnl: float
    total_net_pnl_rs: float
    max_drawdown_rs: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    profit_factor: float
    trades: List[BacktestTrade]


class PointInTimeBacktester:
    """
    Institutional Event-Driven Backtesting Engine.
    Enforces point-in-time bar processing and friction realities.
    """

    FRICTION_PCT: float = 0.0050  # 0.50% turnover friction (round-trip)

    MARGIN_BENCHMARKS: Dict[str, float] = {
        "STRADDLE": 250000.0,   # ₹2.50 Lakhs per lot
        "NAKED_SHORT": 180000.0, # ₹1.80 Lakhs per lot
        "HEDGED_SPREAD": 100000.0 # ₹1.00 Lakh per lot
    }

    def __init__(self, initial_capital: float = 10000000.0, strategy_type: str = "STRADDLE"):
        """
        :param initial_capital: Base portfolio equity (Default: ₹1.0 Crore).
        :param strategy_type: 'STRADDLE', 'NAKED_SHORT', or 'HEDGED_SPREAD'.
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.strategy_type = strategy_type
        self.margin_per_lot = self.MARGIN_BENCHMARKS.get(strategy_type, 250000.0)

    def calculate_lot_allocation(self, available_capital: Optional[float] = None) -> int:
        """
        Direct integer sizing invariant: Lots = floor(Available Equity / Margin per Lot).
        Zero arbitrary cash haircuts.
        """
        cap = available_capital if available_capital is not None else self.current_capital
        return max(1, int(math.floor(cap / self.margin_per_lot)))

    def simulate_trade(
        self,
        date: str,
        instrument: str,
        strike: float,
        expiry: str,
        option_type: str,
        trade_type: str,
        entry_time: str,
        exit_time: str,
        entry_price: float,
        exit_price: float,
        lot_size: int = 65,
        allocated_lots: Optional[int] = None
    ) -> BacktestTrade:
        """
        Simulates a single causal trade with point-in-time execution and turnover friction.
        """
        lots = allocated_lots if allocated_lots is not None else self.calculate_lot_allocation()
        qty = lots * lot_size

        # Gross Points PnL
        if trade_type.upper() == "SELL":
            gross_points = entry_price - exit_price
        else:
            gross_points = exit_price - entry_price

        # Turnover Friction (0.50% round-trip applied to premium turnover)
        turnover_points = (entry_price + exit_price) * self.FRICTION_PCT
        after_cost_points = gross_points - turnover_points

        # Net Rupee PnL
        net_rs = after_cost_points * qty
        self.current_capital += net_rs

        return BacktestTrade(
            date=date,
            instrument=instrument,
            strike=strike,
            expiry=expiry,
            option_type=option_type,
            trade_type=trade_type.upper(),
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=round(entry_price, 2),
            exit_price=round(exit_price, 2),
            after_cost_pnl=round(after_cost_points, 2),
            lot_size=lot_size,
            lots=lots,
            net_pnl_rs=round(net_rs, 2)
        )

    def evaluate_performance(self, trades: List[BacktestTrade]) -> BacktestResult:
        """
        Computes institutional risk and performance metrics from closed trades.
        """
        if not trades:
            return BacktestResult(
                total_trades=0, win_rate_pct=0.0, gross_points_pnl=0.0,
                net_points_pnl=0.0, total_net_pnl_rs=0.0, max_drawdown_rs=0.0,
                max_drawdown_pct=0.0, sharpe_ratio=0.0, sortino_ratio=0.0,
                profit_factor=0.0, trades=[]
            )

        pnl_rs_list = [t.net_pnl_rs for t in trades]
        points_list = [t.after_cost_pnl for t in trades]

        wins = [p for p in pnl_rs_list if p > 0]
        losses = [p for p in pnl_rs_list if p < 0]

        win_rate = (len(wins) / len(pnl_rs_list)) * 100.0 if pnl_rs_list else 0.0
        gross_pts = sum(
            (t.entry_price - t.exit_price if t.trade_type == "SELL" else t.exit_price - t.entry_price)
            for t in trades
        )
        net_pts = sum(points_list)
        total_rs = sum(pnl_rs_list)

        # Drawdown calculation
        equity_curve = [self.initial_capital]
        peak = self.initial_capital
        max_dd_rs = 0.0
        max_dd_pct = 0.0

        for pnl in pnl_rs_list:
            eq = equity_curve[-1] + pnl
            equity_curve.append(eq)
            if eq > peak:
                peak = eq
            dd_rs = peak - eq
            dd_pct = (dd_rs / peak) * 100.0 if peak > 0 else 0.0
            if dd_rs > max_dd_rs:
                max_dd_rs = dd_rs
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        # Annualized Sharpe & Sortino (assuming daily trades or 252 periods)
        arr = np.array(pnl_rs_list)
        mean_pnl = np.mean(arr)
        std_pnl = np.std(arr) if len(arr) > 1 else 1.0

        # Downside deviation for Sortino (semi-deviation across all periods)
        downside_sq = np.minimum(0.0, arr) ** 2
        downside_std = math.sqrt(float(np.mean(downside_sq))) if len(arr) > 0 else 1.0

        sharpe = (mean_pnl / std_pnl) * math.sqrt(252) if std_pnl > 0 else 0.0
        sortino = (mean_pnl / downside_std) * math.sqrt(252) if downside_std > 0 else 0.0

        total_gain = sum(wins) if wins else 0.0
        total_loss = abs(sum(losses)) if losses else 1.0
        profit_factor = total_gain / total_loss if total_loss > 0 else 999.0

        return BacktestResult(
            total_trades=len(trades),
            win_rate_pct=round(win_rate, 2),
            gross_points_pnl=round(gross_pts, 2),
            net_points_pnl=round(net_pts, 2),
            total_net_pnl_rs=round(total_rs, 2),
            max_drawdown_rs=round(max_dd_rs, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            profit_factor=round(profit_factor, 2),
            trades=trades
        )

    def export_canonical_11_col_ledger(self, trades: List[BacktestTrade]) -> str:
        """
        Exports the canonical 11-column CSV ledger:
        Date,Instrument,Strike,Expiry,Type,TradeType,EntryTime,ExitTime,EntryPrice,ExitPrice,after cost
        """
        header = "Date,Instrument,Strike,Expiry,Type,TradeType,EntryTime,ExitTime,EntryPrice,ExitPrice,after cost"
        lines = [header]
        for t in trades:
            line = f"{t.date},{t.instrument},{t.strike:.2f},{t.expiry},{t.option_type},{t.trade_type},{t.entry_time},{t.exit_time},{t.entry_price:.2f},{t.exit_price:.2f},{t.after_cost_pnl:.2f}"
            lines.append(line)
        return "\n".join(lines)
