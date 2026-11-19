# Strategy validation gate

Checks a backtest before anyone trusts it.

**Ledger checks** (`StrategyValidatorGate.audit_trade_ledger`), 11 stages:
1. Ledger has the 11 expected columns, ending in `NetPointsAfterCost` (P&L per unit in option points after cost).
2. Each intraday trade is out by the cutoff (default 15:14:59, configurable). Times are parsed, so `9:30` and `2025-01-07 15:00:00` are read correctly. A missing or unreadable exit time fails the check.
3. Exit time is after entry time. Full date-times are compared as date-times, so an overnight hold passes.
4. 0.50% cost was charged on each leg (entry premium and exit premium).
5. No zero or negative prices.
6. Lot size is a known exchange lot size. The default list covers Nifty (75, 50, 25, 65), Bank Nifty (20, 25, 15, 30), Sensex (10 until 19 Nov 2024, then 20), FinNifty (40, 60) and Midcap Nifty (120). Pass `known_lot_sizes` for other contracts.
7. Lot count is a positive whole number.
8. Losing streaks stay under a cap.
9. Strategy is still profitable with costs doubled.
10. Monte Carlo: trade order shuffled 1,000 times. The 95th percentile max drawdown must stay under 25% of capital. Points are turned into rupees with lots x lot size (or a `point_value` you pass) before the comparison. You can pass `max_dd_limit_pts` to check in points instead. If the ledger cannot be put in rupees and no points limit is given, this check fails.
11. Lookahead trap: trades flagged as using future data are rejected.

Verdict: `PASS` when all 11 checks pass, `PASS_WITH_WARNINGS` with 9 or 10, `REJECT` below that.

**Overfitting statistics** (`overfitting_stats.py`):
- **Probabilistic Sharpe Ratio.** Chance the true Sharpe is above a benchmark, given sample length, skew and fat tails.
- **Deflated Sharpe Ratio.** The same, but the benchmark is the best Sharpe you would expect by luck after trying N variants. The test shows the best of 50 zero-edge strategies scoring above 0.95 on plain PSR and well below it once the 50 tries are counted.
- **Probability of Backtest Overfitting (CSCV).** Splits time into blocks, tries all half/half combinations, and measures how often the in-sample winner ends up in the bottom half out of sample.

References: Bailey and Lopez de Prado (2012, 2014); Bailey, Borwein, Lopez de Prado and Zhu (2017).

```bash
python -m pytest research_showcases/strategy_validator_gate
```
