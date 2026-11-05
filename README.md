# quant-research-portfolio

[![tests](https://github.com/prince-chauhan-pc/quant-research-portfolio/actions/workflows/tests.yml/badge.svg)](https://github.com/prince-chauhan-pc/quant-research-portfolio/actions)

Small, tested Python versions of the methods I use on an Indian index options desk (Nifty, Bank Nifty, Sensex): backtesting with real costs, volatility smiles, cointegration, regime filters, execution cost, and checks for overfit backtests.

The live strategies, their parameters and the market data stay private. Everything here runs on synthetic, seeded data, so you can see each method work on a problem where the right answer is known.

## What's inside

| Module | What it does |
|---|---|
| [`point_in_time_backtester`](research_showcases/point_in_time_backtester/) | Bar-by-bar option backtest, lots sized from margin, 0.50% cost on every leg, Sharpe / Sortino / Calmar, trade ledger |
| [`options_volatility_surface`](research_showcases/options_volatility_surface/) | IV inversion, Greeks, SVI smile fit, butterfly and calendar arbitrage checks, dealer gamma (GEX) |
| [`banknifty_cointegration`](research_showcases/banknifty_cointegration/) | Engle-Granger for pairs, Johansen for baskets, half-life, z-score pairs simulator |
| [`regime_allocation`](research_showcases/regime_allocation/) | k-means volatility regimes that size down short gamma, applied with a one-bar lag |
| [`execution_simulator`](research_showcases/execution_simulator/) | Queue fills for limit orders, square-root impact, cost of latency |
| [`institutional_tearsheet_generator`](research_showcases/institutional_tearsheet_generator/) | Scorecard, monthly grid, drawdown curve, PDF tear sheet |
| [`strategy_validator_gate`](research_showcases/strategy_validator_gate/) | 11 ledger checks, 2x cost stress, Monte Carlo drawdowns, Deflated Sharpe, Probability of Backtest Overfitting |

## Run it

```bash
git clone https://github.com/prince-chauhan-pc/quant-research-portfolio.git
cd quant-research-portfolio
pip install -r requirements.txt
python -m unittest discover research_showcases
python -m research_showcases.reproduce_benchmarks
```

The last command prints [`BENCHMARKS.md`](BENCHMARKS.md). Every number in that file comes from the script; none are typed by hand.

## Rules the code follows

- Costs are charged before any metric is computed: 0.50% of premium turnover on every leg.
- A signal can only use data that existed when the trade was placed. The regime filter refuses a zero-bar lag for this reason.
- Lots = floor(capital / margin per lot). No fractional lots.
- A backtest is not believed until it survives doubled costs, shuffled trade order, and a Deflated Sharpe check for the number of variants tried.

## Author

Prince Chauhan, Senior Quantitative Researcher, New Delhi. SEBI Registered Research Analyst.
[LinkedIn](https://www.linkedin.com/in/prince-chauhan-quant/) · [CV (PDF)](docs/PC_CV/Prince%20Chauhan%20Quants%20Researcher.pdf) · pchauhanrajput.pc@gmail.com

MIT licence.
