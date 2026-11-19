# research_showcases

Seven small modules. Each one has its own README and its own tests, and none needs a broker or a market data feed. All inputs are synthetic.

| Folder | What it does |
|---|---|
| `point_in_time_backtester/` | Option trade-ledger simulator: whole-lot margin sizing (a trade is skipped when capital is below one lot's margin), 0.50% cost on each leg, Sharpe / Sortino / profit factor, trade ledger CSV |
| `options_volatility_surface/` | Black-Scholes pricing and IV inversion, Greeks, SVI smile fit, butterfly and calendar arbitrage checks, dealer gamma (GEX) profile |
| `banknifty_cointegration/` | Engle-Granger test for pairs, Johansen trace test for baskets, rolling hedge ratio, mean-reversion half-life, z-score pairs simulator |
| `regime_allocation/` | Parkinson volatility and IV/RV features, k-means volatility regimes, short-gamma sizing by regime (one-bar lag, no lookahead; the benchmark fits on a training window and tests on a later one) |
| `execution_simulator/` | Simple fill rules for market and limit orders, square-root market impact, cost of order latency |
| `tearsheet_generator/` | Performance scorecard, monthly returns grid, drawdown series, PDF tear sheet |
| `strategy_validator_gate/` | Checks a trade ledger before it is trusted (timing, costs, 2x cost stress, Monte Carlo drawdowns, lookahead trap) plus Probabilistic / Deflated Sharpe and Probability of Backtest Overfitting |

Run everything from the repo root:

```bash
python -m pytest research_showcases
python -m research_showcases.reproduce_benchmarks
```

The second command prints the numbers in [`../BENCHMARKS.md`](../BENCHMARKS.md). Add `--write` to rewrite that file.
