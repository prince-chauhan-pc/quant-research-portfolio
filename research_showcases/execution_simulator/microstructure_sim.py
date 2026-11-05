# -*- coding: utf-8 -*-
"""
Execution Microstructure & Market-Crossing Cost Simulator
==============================================================================
Author: Prince Chauhan Quant Desk (SEBI Registered Research Analyst)
Architecture:
- High-fidelity Limit Order Book (LOB) matching & queue position simulator.
- Square-root market impact modeling (Almgren-Chriss / Barra framework):
  I_temp = eta * sigma * sqrt(Q / V)
- Comprehensive transaction cost attribution:
  * Half-Spread Crossing Cost
  * Market Impact Cost
  * Latency & Adverse Selection Cost
- Latency cost model: adverse price move while an order is in flight, scaled
  by volatility and latency (random walk), comparing a slow and a fast path.
==============================================================================
"""

import math
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple


@dataclass
class OrderRequest:
    order_id: str
    symbol: str
    order_type: str     # 'MARKET' or 'LIMIT'
    side: str           # 'BUY' or 'SELL'
    qty: int
    limit_price: Optional[float]
    timestamp_ms: float
    arrival_mid_price: float


@dataclass
class ExecutionFill:
    order_id: str
    fill_qty: int
    fill_price: float
    spread_cost_pts: float
    impact_cost_pts: float
    slippage_cost_pts: float
    total_cost_bps: float
    is_fully_filled: bool


@dataclass
class CostAttributionSummary:
    total_orders: int
    fill_rate_pct: float
    mean_spread_cost_bps: float
    mean_impact_cost_bps: float
    mean_slippage_cost_bps: float
    total_execution_cost_bps: float
    cost_savings_bps: float


class MicrostructureSimulator:
    """
    Microsecond-scale order book execution and market impact simulator.
    """

    def __init__(
        self,
        daily_volume: float = 5000000.0,
        annual_volatility: float = 0.16,
        impact_eta: float = 0.142
    ):
        """
        :param daily_volume: Average Daily Volume (shares/contracts).
        :param annual_volatility: Instrument annualized volatility.
        :param impact_eta: Temporary market impact coefficient (Barra standard).
        """
        self.daily_volume = daily_volume
        self.annual_volatility = annual_volatility
        self.impact_eta = impact_eta

    def calculate_market_impact(self, qty: int, spot: float) -> float:
        """
        Computes temporary market impact (points) via square-root model:
        I_temp = eta * sigma_daily * sqrt(Q / V_daily) * Spot
        """
        sigma_daily = self.annual_volatility / math.sqrt(252.0)
        participation = qty / self.daily_volume
        impact_pct = self.impact_eta * sigma_daily * math.sqrt(participation)
        return impact_pct * spot

    def execute_order(
        self,
        order: OrderRequest,
        bid_price: float,
        ask_price: float,
        queue_ahead_qty: int,
        traded_volume_window: int,
        latency_drift_pts: float = 0.0
    ) -> ExecutionFill:
        """
        Simulates execution through the order book:
        - MARKET order: Crosses spread immediately, pays half-spread + market impact + latency drift.
        - LIMIT order: Posts to touch queue; fills if traded volume exceeds queue ahead.
        """
        mid = (bid_price + ask_price) / 2.0
        half_spread = (ask_price - bid_price) / 2.0
        impact = self.calculate_market_impact(order.qty, mid)

        if order.order_type.upper() == "MARKET":
            # Aggressive market order
            if order.side.upper() == "BUY":
                fill_price = ask_price + impact + latency_drift_pts
                spread_cost = half_spread
                slippage = latency_drift_pts
            else:
                fill_price = bid_price - impact - latency_drift_pts
                spread_cost = half_spread
                slippage = latency_drift_pts

            total_cost_pts = spread_cost + impact + slippage
            cost_bps = (total_cost_pts / order.arrival_mid_price) * 10000.0

            return ExecutionFill(
                order_id=order.order_id,
                fill_qty=order.qty,
                fill_price=round(fill_price, 2),
                spread_cost_pts=round(spread_cost, 4),
                impact_cost_pts=round(impact, 4),
                slippage_cost_pts=round(slippage, 4),
                total_cost_bps=round(cost_bps, 2),
                is_fully_filled=True
            )

        else:
            # Passive limit order at the touch
            is_filled = traded_volume_window >= queue_ahead_qty + order.qty
            if is_filled:
                fill_price = bid_price if order.side.upper() == "BUY" else ask_price
                # Passive fills earn half-spread (negative spread cost), zero impact
                spread_cost = -half_spread
                total_cost_pts = max(0.0, spread_cost + latency_drift_pts)
                cost_bps = (total_cost_pts / order.arrival_mid_price) * 10000.0

                return ExecutionFill(
                    order_id=order.order_id,
                    fill_qty=order.qty,
                    fill_price=round(fill_price, 2),
                    spread_cost_pts=round(spread_cost, 4),
                    impact_cost_pts=0.0,
                    slippage_cost_pts=round(latency_drift_pts, 4),
                    total_cost_bps=round(cost_bps, 2),
                    is_fully_filled=True
                )
            else:
                return ExecutionFill(
                    order_id=order.order_id,
                    fill_qty=0,
                    fill_price=0.0,
                    spread_cost_pts=0.0,
                    impact_cost_pts=0.0,
                    slippage_cost_pts=0.0,
                    total_cost_bps=0.0,
                    is_fully_filled=False
                )


SECONDS_PER_TRADING_YEAR = 252 * 6.25 * 3600  # NSE cash session, 09:15-15:30


def expected_latency_drift_bps(annual_volatility: float, latency_ms: float) -> float:
    """
    Expected adverse price move while an order is in flight, in bps.
    Price moves like a random walk, so over latency t the move is
    |N(0, vol * sqrt(t))| and its mean is vol * sqrt(t) * sqrt(2 / pi).
    """
    t_years = (latency_ms / 1000.0) / SECONDS_PER_TRADING_YEAR
    return annual_volatility * math.sqrt(t_years) * math.sqrt(2.0 / math.pi) * 10000.0


def simulate_latency_cost_comparison(
    n_orders: int = 500,
    base_spot: float = 25000.0,
    lot_size: int = 65,
    annual_volatility: float = 0.15,
    slow_latency_ms: float = 350.0,
    fast_latency_ms: float = 5.0,
    seed: int = 42,
) -> CostAttributionSummary:
    """
    Compares market-order cost for a slow path (REST polling, ~350 ms) against a
    fast path (~5 ms). The price drift while the order is in flight is drawn from
    a random walk scaled by volatility and latency; nothing is hard-coded, so the
    saving is an output of the inputs above, not an assumption.
    """
    rng = np.random.default_rng(seed)
    sim = MicrostructureSimulator(daily_volume=3000000, annual_volatility=annual_volatility)

    slow_costs = []
    fast_costs = []
    sd_slow = annual_volatility * math.sqrt((slow_latency_ms / 1000.0) / SECONDS_PER_TRADING_YEAR)
    sd_fast = annual_volatility * math.sqrt((fast_latency_ms / 1000.0) / SECONDS_PER_TRADING_YEAR)

    for i in range(n_orders):
        spot = base_spot + rng.normal(0, 50.0)
        spread_half = spot * 0.00025  # 2.5 bps half spread

        bid = spot - spread_half
        ask = spot + spread_half

        # Adverse move while the order travels (absolute value: we only pay when price runs away)
        drift_slow = abs(rng.normal(0.0, sd_slow)) * spot
        drift_fast = abs(rng.normal(0.0, sd_fast)) * spot

        order = OrderRequest(
            order_id=f"ORD_{i:04d}",
            symbol="NIFTY",
            order_type="MARKET",
            side="BUY" if rng.random() > 0.5 else "SELL",
            qty=lot_size * 2,
            limit_price=None,
            timestamp_ms=float(i * 1000),
            arrival_mid_price=spot
        )

        fill_slow = sim.execute_order(order, bid, ask, 500, 1000, latency_drift_pts=drift_slow)
        fill_fast = sim.execute_order(order, bid, ask, 500, 1000, latency_drift_pts=drift_fast)

        slow_costs.append(fill_slow.total_cost_bps)
        fast_costs.append(fill_fast.total_cost_bps)

    mean_slow = float(np.mean(slow_costs))
    mean_fast = float(np.mean(fast_costs))
    savings = mean_slow - mean_fast

    return CostAttributionSummary(
        total_orders=n_orders,
        fill_rate_pct=100.0,
        mean_spread_cost_bps=round(float(np.mean([spread_half / base_spot * 10000])), 2),
        mean_impact_cost_bps=round(float(np.mean([sim.calculate_market_impact(lot_size * 2, base_spot) / base_spot * 10000])), 2),
        mean_slippage_cost_bps=round(mean_slow - (spread_half / base_spot * 10000), 2),
        total_execution_cost_bps=round(mean_slow, 2),
        cost_savings_bps=round(savings, 2)
    )
