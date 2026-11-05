# Tear sheet generator

Builds the summary a reviewer reads before looking at any trades.

What it does:
- **Scorecard.** Net P&L, return, CAGR, win rate, profit factor, expectancy, Sharpe, Sortino, Calmar, max drawdown, recovery factor.
- **Monthly grid.** P&L by month and year.
- **Underwater curve.** Drawdown from the running peak, every day.
- **PDF.** Renders the scorecard as a PDF with ReportLab.

```bash
python -m unittest research_showcases.institutional_tearsheet_generator.test_tearsheet_builder
```
