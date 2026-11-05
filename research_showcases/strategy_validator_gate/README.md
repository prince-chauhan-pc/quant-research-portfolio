# Strategy validation gate

Checks a backtest before anyone trusts it.

**Ledger checks** (`StrategyValidatorGate.audit_trade_ledger`), 11 stages:
1. Ledger has the 11 expected columns.
2. Every intraday trade is out by the cutoff (default 15:14:59, configurable).
3. Exit time is after entry time.
4. 0.50% cost was charged on every trade.
5. No zero or negative prices.
6. Quantities are whole exchange lots.
7. Lots match floor(capital / margin).
8. Losing streaks stay under a cap.
9. Strategy is still profitable with costs doubled.
10. Monte Carlo: trade order shuffled 1,000 times; 95th and 99th percentile max drawdown reported.
11. Lookahead trap: trades flagged as using future data are rejected.

**Overfitting statistics** (`overfitting_stats.py`):
- **Probabilistic Sharpe Ratio.** Chance the true Sharpe is above a benchmark, given sample length, skew and fat tails.
- **Deflated Sharpe Ratio.** The same, but the benchmark is the best Sharpe you would expect by luck after trying N variants. The test shows the best of 50 zero-edge strategies scoring above 0.95 on plain PSR and well below it once the 50 tries are counted.
- **Probability of Backtest Overfitting (CSCV).** Splits time into blocks, tries every half/half combination, and measures how often the in-sample winner ends up in the bottom half out of sample.

References: Bailey and Lopez de Prado (2012, 2014); Bailey, Borwein, Lopez de Prado and Zhu (2017).

```bash
python -m unittest research_showcases.strategy_validator_gate.test_validator_gate research_showcases.strategy_validator_gate.test_overfitting_stats
```
