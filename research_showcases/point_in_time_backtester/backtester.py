# -*- coding: utf-8 -*-
"""
Option trade-ledger simulator (point_in_time_backtester)
==============================================================================
Author: Prince Chauhan
What it does:
- Prices one option trade at a time from caller-supplied entry and exit
  prices, and keeps a running capital balance. The caller must use only data
  available at entry time.
- Example margin per lot: short straddle INR 2.5 L, naked short INR 1.8 L,
  hedged spread INR 1.0 L. Change these to current exchange margins.
- Whole-lot sizing: lots = floor(capital / margin per lot). When capital is
  below one lot's margin (or is zero or negative) the size is 0 lots and the
  trade is skipped: simulate_trade returns None and capital is unchanged.
- Charges 0.50% of premium on each leg (0.50% of the entry premium plus 0.50%
  of the exit premium), as an allowance for brokerage, STT, exchange charges
  and slippage.
- Exports an 11-column trade ledger CSV.
==============================================================================
"""

import math
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


def _whole_lot_count(value: Any) -> int:
    """Return value as a lot count, or raise ValueError if it is not a whole number of 0 or more."""
    if isinstance(value, bool):
        raise ValueError(f"allocated_lots must be a whole number of 0 or more, got {value!r}")
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"allocated_lots must be a whole number of 0 or more, got {value!r}") from None
    if not math.isfinite(n) or n < 0 or not n.is_integer():
        raise ValueError(f"allocated_lots must be a whole number of 0 or more, got {value!r}")
    return int(n)


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
    after_cost_pnl: float   # Points P&L per unit after 0.50% cost on each leg
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
    Option trade-ledger simulator.
    Sizes whole lots from margin, charges cost on each leg and tracks capital.
    A trade is skipped (0 lots) when capital is below one lot's margin.
    """

    FRICTION_PCT: float = 0.0050  # 0.50% of premium on each leg (entry and exit)

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
        self.skipped_trades = 0  # trades not taken because capital was below one lot's margin

    def calculate_lot_allocation(self, available_capital: Optional[float] = None) -> int:
        """
        Whole-lot sizing: lots = floor(available capital / margin per lot).
        Returns 0 when capital is below one lot's margin, zero, negative or not
        a finite number. There is no 1-lot minimum: a 0 means skip the trade.
        """
        cap = available_capital if available_capital is not None else self.current_capital
        try:
            cap = float(cap)
        except (TypeError, ValueError):
            return 0
        if not math.isfinite(cap) or cap <= 0.0:
            return 0
        return max(0, int(math.floor(cap / self.margin_per_lot)))

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
    ) -> Optional[BacktestTrade]:
        """
        Prices one trade from the caller's entry and exit prices, with 0.50% cost
        on each leg, and adds its rupee P&L to the running capital.

        Lots come from allocated_lots when given, otherwise from margin sizing.
        When that gives 0 lots the trade is skipped: the method returns None,
        capital is unchanged and skipped_trades goes up by one.
        allocated_lots must be a whole number of 0 or more.
        """
        if allocated_lots is not None:
            lots = _whole_lot_count(allocated_lots)
        else:
            lots = self.calculate_lot_allocation()
        if lots == 0:
            self.skipped_trades += 1
            return None
        qty = lots * lot_size

        # Gross Points PnL
        if trade_type.upper() == "SELL":
            gross_points = entry_price - exit_price
        else:
            gross_points = exit_price - entry_price

        # Cost: 0.50% of premium on each leg (entry leg plus exit leg)
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
        Computes risk and performance metrics from closed trades.
        Skipped trades (None from simulate_trade) are ignored.
        """
        trades = [t for t in trades if t is not None]
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
        Exports the 11-column CSV ledger:
        Date,Instrument,Strike,Expiry,Type,TradeType,EntryTime,ExitTime,EntryPrice,ExitPrice,NetPointsAfterCost
        NetPointsAfterCost is the P&L per unit in option points after cost.
        """
        header = "Date,Instrument,Strike,Expiry,Type,TradeType,EntryTime,ExitTime,EntryPrice,ExitPrice,NetPointsAfterCost"
        lines = [header]
        for t in trades:
            if t is None:  # simulate_trade returns None for a skipped trade (capital below one lot's margin)
                continue
            line = f"{t.date},{t.instrument},{t.strike:.2f},{t.expiry},{t.option_type},{t.trade_type},{t.entry_time},{t.exit_time},{t.entry_price:.2f},{t.exit_price:.2f},{t.after_cost_pnl:.2f}"
            lines.append(line)
        return "\n".join(lines)
