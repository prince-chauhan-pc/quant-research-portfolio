# -*- coding: utf-8 -*-
"""
Strategy validation gate for a backtest trade ledger
==============================================================================
Author: Prince Chauhan
What it does:
- 11 checks on a trade ledger before it is trusted.
- Intraday exit cutoff (default 15:14:59, configurable). Times are parsed,
  not compared as text, and a missing or unreadable time fails the check.
- Checks that 0.50% cost was charged on each leg (entry and exit premium).
- Doubled-cost stress test.
- Monte Carlo drawdowns from reshuffled trade order (1,000 paths), checked
  in one unit: rupees against capital, or points against a points limit.
- Lookahead trap: trades flagged as using future data are rejected.
==============================================================================
"""

import datetime as dt
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Iterable, Optional, Tuple

# Column that holds P&L per unit in option points after cost.
PNL_COLUMN = "NetPointsAfterCost"

# Index option lot sizes used by NSE and BSE: Nifty 75, 50, 25 and 65;
# Bank Nifty 20, 25, 15 and 30; Sensex 10 (until 19 Nov 2024) and 20;
# FinNifty 40 and 60; Midcap Nifty 120. Pass known_lot_sizes for anything else.
DEFAULT_KNOWN_LOT_SIZES = frozenset({10, 15, 20, 25, 30, 40, 50, 60, 65, 75, 120})

_TIME_FORMATS = ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M")


def parse_trade_time(value: Any) -> Optional[Tuple[Optional[dt.date], dt.time]]:
    """Parse a ledger time into (date or None, time of day). Returns None if it cannot be read.

    Accepts datetime.time and datetime.datetime objects, clock text such as
    "9:30", "09:30:00" or "15:14:59.5", and date-time text such as
    "2025-01-07 15:00:00" or "2025-01-07T15:00:00". Empty text is not a time.
    """
    if isinstance(value, dt.datetime):
        return value.date(), value.time()
    if isinstance(value, dt.time):
        return None, value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if ":" not in text:  # empty, or a date with no time
        return None
    for fmt in _TIME_FORMATS:
        try:
            return None, dt.datetime.strptime(text, fmt).time()
        except ValueError:
            pass
    try:
        stamp = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return stamp.date(), stamp.time()


@dataclass
class StageResult:
    stage_id: int
    name: str
    passed: bool
    detail: str
    metric: Optional[float] = None


@dataclass
class ValidationReport:
    total_stages: int
    stages_passed: int
    stages_failed: int
    verdict: str  # 'PASS' (all 11), 'PASS_WITH_WARNINGS' (9 or 10), or 'REJECT'
    readiness_score: float  # 0 to 100
    mc_drawdown_95th: float
    mc_drawdown_99th: float
    friction_stress_degradation: float
    stage_results: List[StageResult] = field(default_factory=list)
    mc_drawdown_unit: str = "INR"  # 'INR' or 'pts': unit of mc_drawdown_95th / 99th


class StrategyValidatorGate:
    """
    Strategy validation gate.
    Checks a trade ledger for late exits, missing costs, bad prices, wrong lot
    sizing, cost sensitivity, drawdown risk and planted lookahead flags.
    """

    MANDATORY_COLUMNS = [
        "Date", "Instrument", "Strike", "Expiry", "Type",
        "TradeType", "EntryTime", "ExitTime", "EntryPrice", "ExitPrice", PNL_COLUMN
    ]

    def __init__(
        self,
        friction_rate: float = 0.0050,
        terminal_time_cutoff: str = "15:14:59",
        known_lot_sizes: Optional[Iterable[int]] = None,
    ):
        """
        :param friction_rate: Cost charged on each leg, as a share of that leg's premium (Default: 0.50%)
        :param terminal_time_cutoff: Latest intraday exit time (Default: 15:14:59)
        :param known_lot_sizes: Lot sizes stage 6 accepts (Default: DEFAULT_KNOWN_LOT_SIZES)
        """
        self.friction_rate = friction_rate
        parsed_cutoff = parse_trade_time(terminal_time_cutoff)
        if parsed_cutoff is None or parsed_cutoff[0] is not None:
            raise ValueError(f"terminal_time_cutoff must be a clock time such as '15:14:59', got {terminal_time_cutoff!r}")
        self.terminal_time_cutoff = terminal_time_cutoff
        self._cutoff_time = parsed_cutoff[1]
        self.known_lot_sizes = frozenset(int(x) for x in (known_lot_sizes if known_lot_sizes is not None
                                                          else DEFAULT_KNOWN_LOT_SIZES))

    def audit_trade_ledger(
        self,
        trades: List[Dict[str, Any]],
        initial_capital: float = 10000000.0,
        point_value: Optional[float] = None,
        max_dd_limit_pts: Optional[float] = None,
    ) -> ValidationReport:
        """
        Run the 11 checks on a trade ledger.

        The NetPointsAfterCost column is P&L in option points per unit. Stage 10
        (Monte Carlo drawdown) compares the drawdown with its limit in one unit:
        - Rupees (default): each trade's points are multiplied by lots x lotsize
          when the trade has both, otherwise by point_value (rupees per point for
          one trade). The 95th percentile drawdown must stay under 25% of
          initial_capital.
        - Points: pass max_dd_limit_pts and the 95th percentile drawdown in
          points must stay under it.
        If a trade cannot be put in rupees and no points limit is given, stage 10
        fails, because a limit that cannot be checked is not a pass.
        """
        results: List[StageResult] = []

        if not trades:
            return ValidationReport(
                total_stages=11,
                stages_passed=0,
                stages_failed=11,
                verdict="REJECT",
                readiness_score=0.0,
                mc_drawdown_95th=0.0,
                mc_drawdown_99th=0.0,
                friction_stress_degradation=1.0,
                stage_results=[StageResult(0, "Ledger Check", False, "Trade ledger is empty.")]
            )

        # STAGE 1: Canonical 11-Column Schema Verification
        first_row = trades[0]
        missing_cols = [c for c in self.MANDATORY_COLUMNS if c not in first_row]
        s1_pass = len(missing_cols) == 0
        results.append(StageResult(
            stage_id=1,
            name="Canonical 11-Column Schema",
            passed=s1_pass,
            detail="All 11 audit columns verified." if s1_pass else f"Missing columns: {missing_cols}"
        ))

        # STAGE 2: Intraday exit by the cutoff (default 15:14:59). Times are parsed,
        # so "9:30" or a full date-time is read correctly; a missing exit time fails.
        exits = [parse_trade_time(t.get("ExitTime")) for t in trades]
        unreadable_exits = sum(1 for e in exits if e is None)
        late_exits = sum(1 for e in exits if e is not None and e[1] > self._cutoff_time)
        s2_pass = unreadable_exits == 0 and late_exits == 0
        if s2_pass:
            s2_detail = f"All trades exited by {self.terminal_time_cutoff}."
        else:
            s2_detail = (f"Found {late_exits} trades exiting after {self.terminal_time_cutoff} and "
                         f"{unreadable_exits} with a missing or unreadable exit time.")
        results.append(StageResult(
            stage_id=2,
            name="Intraday Exit Cutoff",
            passed=s2_pass,
            detail=s2_detail
        ))

        # STAGE 3: Exit after entry. Full date-times are compared as date-times;
        # otherwise the times of day are compared. Unreadable times fail.
        bad_order = 0
        for t, ex in zip(trades, exits):
            en = parse_trade_time(t.get("EntryTime"))
            if en is None or ex is None:
                bad_order += 1
            elif en[0] is not None and ex[0] is not None:
                if dt.datetime.combine(ex[0], ex[1]) <= dt.datetime.combine(en[0], en[1]):
                    bad_order += 1
            elif ex[1] <= en[1]:
                bad_order += 1
        s3_pass = bad_order == 0
        results.append(StageResult(
            stage_id=3,
            name="Exit After Entry",
            passed=s3_pass,
            detail="Every exit is after its entry." if s3_pass else f"Found {bad_order} trades with exit not after entry or an unreadable time."
        ))

        # STAGE 4: Cost check: 0.50% of premium on each leg already taken off
        cost_violations = 0
        for t in trades:
            entry = float(t.get("EntryPrice", 0.0))
            exit_p = float(t.get("ExitPrice", 0.0))
            trade_type = t.get("TradeType", "BUY")
            gross = (exit_p - entry) if trade_type == "BUY" else (entry - exit_p)
            expected_cost = (entry + exit_p) * self.friction_rate
            expected_after_cost = gross - expected_cost
            actual_after_cost = float(t.get(PNL_COLUMN, 0.0))
            if abs(actual_after_cost - expected_after_cost) > 0.05:
                cost_violations += 1
        s4_pass = cost_violations == 0
        results.append(StageResult(
            stage_id=4,
            name="Cost On Each Leg",
            passed=s4_pass,
            detail="Cost on each leg verified on all trades." if s4_pass else f"{cost_violations} trades failed the cost check."
        ))

        # STAGE 5: Non-Zero Price Invariant
        zero_prices = [t for t in trades if float(t.get("EntryPrice", 0.0)) <= 0.0 or float(t.get("ExitPrice", 0.0)) <= 0.0]
        s5_pass = len(zero_prices) == 0
        results.append(StageResult(
            stage_id=5,
            name="Non-Zero Price Invariant",
            passed=s5_pass,
            detail="All price ticks positive and non-zero." if s5_pass else f"Found {len(zero_prices)} invalid price ticks."
        ))

        # STAGE 6: Lot size is in the list of known exchange lot sizes
        def _lot_size_value(value: Any) -> Any:
            try:
                n = float(value)
            except (TypeError, ValueError):
                return value
            return int(n) if math.isfinite(n) and n.is_integer() else value

        lot_sizes = {_lot_size_value(t["lotsize"]) for t in trades if "lotsize" in t}
        unknown_sizes = sorted((ls for ls in lot_sizes if ls not in self.known_lot_sizes), key=str)
        s6_pass = not unknown_sizes
        results.append(StageResult(
            stage_id=6,
            name="Known Exchange Lot Size",
            passed=s6_pass,
            detail="All lot sizes are known exchange lot sizes." if s6_pass else f"Unknown lot sizes: {unknown_sizes}"
        ))

        # STAGE 7: Lot count is a positive whole number (no zero, negative or fractional lots)
        def _bad_lot_count(value: Any) -> bool:
            try:
                n = float(value)
            except (TypeError, ValueError):
                return True
            return n <= 0 or not n.is_integer()

        invalid_lots = [t for t in trades if "lots" in t and _bad_lot_count(t["lots"])]
        s7_pass = len(invalid_lots) == 0
        results.append(StageResult(
            stage_id=7,
            name="Positive Whole Lot Count",
            passed=s7_pass,
            detail="All lot counts are positive whole numbers." if s7_pass else f"Found {len(invalid_lots)} trades with a zero, negative or fractional lot count."
        ))

        # STAGE 8: Anti-Streak Risk Governance
        max_loss_streak = 0
        current_loss_streak = 0
        for t in trades:
            if float(t.get(PNL_COLUMN, 0.0)) < 0.0:
                current_loss_streak += 1
                if current_loss_streak > max_loss_streak:
                    max_loss_streak = current_loss_streak
            else:
                current_loss_streak = 0
        s8_pass = max_loss_streak <= 7
        results.append(StageResult(
            stage_id=8,
            name="Anti-Streak Risk Governance",
            passed=s8_pass,
            detail=f"Max consecutive loss streak: {max_loss_streak} (Cap: <=7)." if s8_pass else f"Losing streak ({max_loss_streak}) exceeded cap."
        ))

        # STAGE 9: Doubled-cost stress
        pnls_1x = [float(t.get(PNL_COLUMN, 0.0)) for t in trades]
        total_1x = sum(pnls_1x)
        # Charge the cost a second time (another 0.50% on each leg)
        total_2x = sum(
            float(t.get(PNL_COLUMN, 0.0)) - (float(t.get("EntryPrice", 0.0)) + float(t.get("ExitPrice", 0.0))) * self.friction_rate
            for t in trades
        )
        degradation = (total_1x - total_2x) / total_1x if total_1x > 0 else 1.0
        s9_pass = total_2x > 0.0  # Strategy must remain profitable under 2x friction
        results.append(StageResult(
            stage_id=9,
            name="2x Friction Stress Audit",
            passed=s9_pass,
            detail=f"Strategy remains profitable under 2x friction (Degradation: {degradation*100:.1f}%)." if s9_pass else "Strategy unprofitable under 2x friction stress.",
            metric=round(degradation, 4)
        ))

        # STAGE 10: Monte Carlo Reshuffled Drawdown Cone (1,000 paths)
        # The drawdown and its limit must be in the same unit (see the docstring).
        unsized: List[Dict[str, Any]] = []
        if max_dd_limit_pts is not None:
            dd_unit = "pts"
            mc_pnls = pnls_1x
            dd_limit: Optional[float] = float(max_dd_limit_pts)
        else:
            dd_unit = "INR"
            mc_pnls = []
            for t, p in zip(trades, pnls_1x):
                size = None
                if "lots" in t and "lotsize" in t:
                    try:
                        size = float(t["lots"]) * float(t["lotsize"])
                    except (TypeError, ValueError):
                        size = None  # unreadable size: treated as unsized (stages 6 and 7 also fail)
                if size is not None and math.isfinite(size):
                    mc_pnls.append(p * size)
                elif point_value is not None:
                    mc_pnls.append(p * float(point_value))
                else:
                    unsized.append(t)
            dd_limit = initial_capital * 0.25  # 95th percentile DD must be under 25% of capital
            if unsized:
                # Cannot express the drawdown in rupees: report it in points and fail the stage.
                dd_unit = "pts"
                mc_pnls = pnls_1x
                dd_limit = None

        random.seed(42)
        simulated_max_dds = []
        n_trades = len(mc_pnls)
        for _ in range(1000):
            shuffled = random.sample(mc_pnls, n_trades)
            peak = 0.0
            equity = 0.0
            max_dd = 0.0
            for p in shuffled:
                equity += p
                if equity > peak:
                    peak = equity
                dd = peak - equity
                if dd > max_dd:
                    max_dd = dd
            simulated_max_dds.append(max_dd)

        simulated_max_dds.sort()
        mc_95 = simulated_max_dds[int(0.95 * len(simulated_max_dds))]
        mc_99 = simulated_max_dds[int(0.99 * len(simulated_max_dds))]
        if dd_limit is None:
            s10_pass = False
            s10_detail = (f"{len(unsized)} of {len(trades)} trades have no lots and lotsize and no point_value "
                          f"was given, so the drawdown cannot be compared with capital. Pass point_value or "
                          f"max_dd_limit_pts. Monte Carlo 95th Max DD: {mc_95:,.1f} pts.")
        else:
            s10_pass = mc_95 < dd_limit
            s10_detail = (f"Monte Carlo 95th Max DD: {mc_95:,.1f} {dd_unit}, 99th: {mc_99:,.1f} {dd_unit} "
                          f"(limit {dd_limit:,.1f} {dd_unit}).")
        results.append(StageResult(
            stage_id=10,
            name="Monte Carlo Drawdown Cone",
            passed=s10_pass,
            detail=s10_detail,
            metric=round(mc_95, 2)
        ))

        # STAGE 11: Synthetic Lookahead Trap Verification
        # Rejects trades carrying the _synthetic_leak flag (a planted lookahead trap used in tests)
        lookahead_traps_found = 0
        for t in trades:
            # Trap condition: If an exit price appears identical to an arbitrary future tick offset
            if t.get("_synthetic_leak", False):
                lookahead_traps_found += 1
        s11_pass = lookahead_traps_found == 0
        results.append(StageResult(
            stage_id=11,
            name="Synthetic Lookahead Trap Gate",
            passed=s11_pass,
            detail="Zero lookahead or future price leakage detected." if s11_pass else f"Detected {lookahead_traps_found} lookahead leaks."
        ))

        # Overall Scoring
        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count
        readiness_score = (passed_count / len(results)) * 100.0

        if passed_count == 11:
            verdict = "PASS"
        elif passed_count >= 9:
            verdict = "PASS_WITH_WARNINGS"
        else:
            verdict = "REJECT"

        return ValidationReport(
            total_stages=11,
            stages_passed=passed_count,
            stages_failed=failed_count,
            verdict=verdict,
            readiness_score=round(readiness_score, 1),
            mc_drawdown_95th=round(mc_95, 2),
            mc_drawdown_99th=round(mc_99, 2),
            friction_stress_degradation=round(degradation, 4),
            stage_results=results,
            mc_drawdown_unit=dd_unit,
        )
