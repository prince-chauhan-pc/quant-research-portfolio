# Tear sheet generator

Builds the summary a reviewer reads before looking at any trades.

What it does:
- **Scorecard.** Net P&L, return, CAGR, win rate, profit factor, expectancy, Sharpe, Sortino, Calmar, max drawdown, recovery factor.
- **Monthly grid.** P&L by month and year.
- **Underwater curve.** Drawdown from the running peak, for each day.
- **PDF.** Renders the scorecard and monthly grid as a PDF with ReportLab. No name or firm is printed unless you pass `author_line` (for example "Synthetic data, not a trading result").

```bash
python -m pytest research_showcases/tearsheet_generator
```
