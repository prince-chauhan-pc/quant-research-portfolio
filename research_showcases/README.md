# research_showcases

Seven small modules. Each one has its own README, its own tests, and nothing that needs a broker or market data feed.

| Folder | What it does |
|---|---|
| `point_in_time_backtester/` | Bar-by-bar backtest of option trades: margin-based lot sizing, 0.50% cost per leg, Sharpe / Sortino / Calmar, trade ledger CSV |
| `options_volatility_surface/` | Black-Scholes pricing and IV inversion, Greeks, SVI smile fit, butterfly and calendar arbitrage checks, dealer gamma (GEX) profile |
| `banknifty_cointegration/` | Engle-Granger test for pairs, Johansen trace test for baskets, rolling hedge ratio, mean-reversion half-life, z-score pairs simulator |
| `regime_allocation/` | Parkinson volatility and IV/RV features, k-means volatility regimes, short-gamma sizing by regime (one-bar lag, no lookahead) |
| `execution_simulator/` | Limit-order queue fills, square-root market impact, cost of order latency |
| `institutional_tearsheet_generator/` | Performance scorecard, monthly returns grid, drawdown series, PDF tear sheet |
| `strategy_validator_gate/` | Checks a trade ledger before it is trusted (timing, costs, 2x cost stress, Monte Carlo drawdowns, lookahead trap) plus Probabilistic / Deflated Sharpe and Probability of Backtest Overfitting |

Run everything from the repo root:

```bash
python -m unittest discover research_showcases
python -m research_showcases.reproduce_benchmarks
```

The second command prints the numbers in [`../BENCHMARKS.md`](../BENCHMARKS.md).
