# Point-in-time backtester

Simulates option trades one bar at a time, using only data available at that bar.

What it does:
- **Lot sizing from margin.** Lots = floor(capital / margin per lot). Example margins in the code: INR 2.5 L per straddle lot, 1.8 L per naked short lot, 1.0 L per hedged spread lot. Change them to match current exchange SPAN.
- **Costs on every leg.** 0.50% of premium turnover (entry + exit premium) is charged on each trade before P&L is counted.
- **Performance.** Net P&L, win rate, max drawdown, Sharpe, Sortino (downside deviation over all periods), Calmar.
- **Ledger.** Exports an 11-column CSV: `Date, Instrument, Strike, Expiry, Type, TradeType, EntryTime, ExitTime, EntryPrice, ExitPrice, after cost`.

Worked example (from the tests): sell a call at 100, buy back at 50. Gross 50 points, cost (100 + 50) x 0.50% = 0.75 points, net 49.25 points. With 10 lots of 65 that is INR 32,012.50.

```bash
python -m unittest research_showcases.point_in_time_backtester.test_backtester
```

Limits: no intrabar fills or slippage model here (see `execution_simulator`), and trades are supplied by the caller rather than generated from signals.
