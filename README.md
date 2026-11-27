# quant-research-portfolio

[![tests](https://github.com/prince-chauhan-pc/quant-research-portfolio/actions/workflows/tests.yml/badge.svg)](https://github.com/prince-chauhan-pc/quant-research-portfolio/actions/workflows/tests.yml)

Small, tested Python versions of research methods I use on Indian index options (Nifty, Bank Nifty, Sensex): backtesting with costs, volatility smiles, cointegration, regime filters, execution cost, and checks for overfit backtests.

All data in this repo is synthetic and seeded, so each method can be checked on a problem where the right answer is known. Nothing here is a trading result. The desk's production code, strategy parameters and market data stay private.

## What's inside

| Module | What it does |
|---|---|
| [`point_in_time_backtester`](research_showcases/point_in_time_backtester/) | Option trade-ledger simulator: whole lots sized from margin, 0.50% cost on each leg, Sharpe / Sortino / profit factor, trade ledger |
| [`options_volatility_surface`](research_showcases/options_volatility_surface/) | IV inversion, Greeks, SVI smile fit, butterfly and calendar arbitrage checks, dealer gamma (GEX) |
| [`banknifty_cointegration`](research_showcases/banknifty_cointegration/) | Engle-Granger for pairs, Johansen for baskets, half-life, z-score pairs simulator |
| [`regime_allocation`](research_showcases/regime_allocation/) | k-means volatility regimes that size down short gamma, applied with a one-bar lag and tested out of sample |
| [`execution_simulator`](research_showcases/execution_simulator/) | Simple fill rules for market and limit orders, square-root impact, cost of latency |
| [`tearsheet_generator`](research_showcases/tearsheet_generator/) | Scorecard, monthly grid, drawdown curve, PDF tear sheet |
| [`strategy_validator_gate`](research_showcases/strategy_validator_gate/) | 11 ledger checks, 2x cost stress, Monte Carlo drawdowns, Deflated Sharpe, Probability of Backtest Overfitting |

## Run it

```bash
git clone https://github.com/prince-chauhan-pc/quant-research-portfolio.git
cd quant-research-portfolio
pip install -r requirements.txt pytest
python -m pytest research_showcases
python -m research_showcases.reproduce_benchmarks
```

The last command prints the numbers in [`BENCHMARKS.md`](BENCHMARKS.md). That file is written by the script, not by hand. On each push, CI runs the tests on Python 3.11 and 3.12, rebuilds `BENCHMARKS.md` with the script and fails if the result differs from the committed file.

## Rules the code follows

- Costs are charged before any metric is computed: 0.50% of premium on each leg (entry and exit).
- A signal can only use data that existed when the trade was placed. The regime filter refuses a zero-bar lag for this reason, and its benchmark fits k-means on the first 400 bars and tests on the next 400.
- Lots = floor(capital / margin per lot). No fractional lots. If capital is below one lot's margin, the trade is skipped.
- The validator gate checks that a backtest survives doubled costs and shuffled trade order. Deflated Sharpe is a separate check for the number of variants tried.

## Author

Prince Chauhan, Senior Quantitative Researcher & Trader, SMC Global Securities, New Delhi. SEBI Registered Research Analyst.
[CV (PDF)](docs/PC_CV/Prince%20Chauhan%20-%20Quant%20Researcher%20and%20Trader.pdf) · pchauhanrajput.pc@gmail.com

MIT licence.
