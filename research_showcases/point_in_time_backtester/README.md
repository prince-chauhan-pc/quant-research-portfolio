# Option trade-ledger simulator

Folder name: `point_in_time_backtester`. Prices option trades one at a time with whole-lot margin sizing and costs, and keeps a running capital balance. Entry and exit prices come from the caller, who must use only data available at entry time. The code does not check that for you.

What it does:
- **Lot sizing from margin.** Lots = floor(capital / margin per lot). No fractional lots and no 1-lot minimum: if capital is below one lot's margin (or is zero or negative), the size is 0 lots and the trade is skipped. `simulate_trade` then returns `None`, capital is unchanged and `skipped_trades` goes up by one. Example margins in the code: INR 2.5 L per straddle lot, 1.8 L per naked short lot, 1.0 L per hedged spread lot. Change them to match current exchange SPAN.
- **Costs on each leg.** 0.50% of the entry premium plus 0.50% of the exit premium is charged before P&L is counted.
- **Performance.** Net P&L, win rate, max drawdown, Sharpe, Sortino (downside deviation over all periods), profit factor. Sharpe and Sortino are worked out per trade and scaled by the square root of 252.
- **Ledger.** Exports an 11-column CSV: `Date, Instrument, Strike, Expiry, Type, TradeType, EntryTime, ExitTime, EntryPrice, ExitPrice, NetPointsAfterCost`. The last column is P&L per unit in option points after cost.

Worked example (from the tests): sell a call at 100, buy back at 50. Gross 50 points, cost (100 + 50) x 0.50% = 0.75 points, net 49.25 points. With 10 lots of 65 that is INR 32,012.50.

```bash
python -m pytest research_showcases/point_in_time_backtester
```

Limits: no intrabar fills or slippage model here (see `execution_simulator`), and trades are supplied by the caller rather than generated from signals.
