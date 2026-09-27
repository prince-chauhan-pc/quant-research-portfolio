# Point-in-Time Vectorized Backtesting Engine
## Institutional Research Note & Implementation
**Author**: Prince Chauhan (SEBI Registered Research Analyst)

---

### 1. Research Question & Empirical Motivation
Most retail options backtests generate severely inflated Sharpe ratios (often 4.0+) due to three fatal methodological flaws:
1. **Lookahead & Bid-Ask Bias**: Assuming entry at the exact closing price of a signal candle rather than enforcing chronological execution on subsequent tick availability.
2. **Turnover Friction Neglect**: Ignoring the cumulative impact of Securities Transaction Tax (STT), exchange turnover fees, GST, SEBI turnover charges, and bid-ask crossing slippage. On modern weekly options, friction frequently consumes 25% to 40% of gross theoretical edge.
3. **Unrealistic Capital Sizing**: Assuming arbitrary cash haircuts or static lot counts that ignore exchange SPAN + Exposure clearing margin requirements.

This showcase presents an **event-driven, point-in-time intraday options simulation engine** enforcing:
- Causal sequential bar processing ($t \le T-1$).
- Explicit pre-deduction of **0.50% turnover friction** across entry and exit premium notional.
- Direct regulatory margin sizing calibrated to exchange benchmarks:
  $$\text{Lots} = \left\lfloor \frac{\text{Available Equity}}{\text{Margin per Lot}} \right\rfloor$$
- Canonical 11-column trade audit ledger export.

---

### 2. Mathematical Formulation & Friction Accounting

#### A. Turnover Friction Deduction
For each closed position:
$$\text{Gross PnL Points} = \begin{cases} P_{\text{entry}} - P_{\text{exit}} & \text{if Short (SELL)} \\ P_{\text{exit}} - P_{\text{entry}} & \text{if Long (BUY)} \end{cases}$$

The round-trip premium turnover friction is defined as:
$$\text{Friction Points} = (P_{\text{entry}} + P_{\text{exit}}) \times 0.0050$$

The after-cost net edge per point is therefore:
$$\text{After-Cost Points} = \text{Gross PnL Points} - \text{Friction Points}$$

$$\text{Net PnL (₹)} = \text{After-Cost Points} \times (\text{Lots} \times \text{Lot Size})$$

#### B. Direct Sizing Benchmark Calibration
- **Short Straddle**: ₹2,50,000 per lot (₹1.00 Cr base capital $\implies 40$ Lots).
- **Naked Short**: ₹1,80,000 per lot (₹1.00 Cr base capital $\implies 55$ Lots).
- **Hedged Option Spread**: ₹1,00,000 per lot (₹1.00 Cr base capital $\implies 100$ Lots).

---

### 3. Canonical 11-Column Validation Ledger
The engine outputs an audit ledger strictly adhering to the 11 unpivoted columns required by institutional quantitative validators:
```csv
Date,Instrument,Strike,Expiry,Type,TradeType,EntryTime,ExitTime,EntryPrice,ExitPrice,after cost
2026-09-01,NIFTY,25000.00,02-Sep-2026,CE,SELL,09:20,15:10,145.20,92.40,51.61
2026-09-01,NIFTY,25000.00,02-Sep-2026,PE,SELL,09:20,15:10,132.80,88.10,43.60
```

---

### 4. Running the Showcase & Unit Tests

Run the dedicated test suite:
```bash
python -m unittest research_showcases.point_in_time_backtester.test_backtester
```

Sample Python execution:
```python
from research_showcases.point_in_time_backtester import PointInTimeBacktester

# Initialize ₹1.00 Crore Straddle Backtester
bt = PointInTimeBacktester(initial_capital=10000000.0, strategy_type="STRADDLE")

# Allocate lots via direct integer sizing (₹1.00 Cr / ₹2.50L = 40 lots)
lots = bt.calculate_lot_allocation()

# Simulate short trade with 0.50% turnover friction pre-deducted
trade = bt.simulate_trade(
    date="2026-09-01", instrument="NIFTY", strike=25000.0, expiry="02-Sep-2026",
    option_type="CE", trade_type="SELL", entry_time="09:20", exit_time="15:10",
    entry_price=150.0, exit_price=90.0, lot_size=65, allocated_lots=lots
)

result = bt.evaluate_performance([trade])
print("Net Rupee PnL:", result.total_net_pnl_rs)
print("After Cost Points:", trade.after_cost_pnl)
```

---

### 5. Methodological Limitations
- Assumes fills occur within the bid-ask spread; under extreme gap volatility, crossing costs can temporarily exceed 0.50%.
- Does not model intraday margin calls if unrealized drawdown breaches peak intraday SPAN maintenance.
