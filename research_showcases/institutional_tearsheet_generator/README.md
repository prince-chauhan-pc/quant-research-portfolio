# Institutional Performance Tear Sheet & Heatmap Builder

**Author**: Prince Chauhan Quant Desk (SEBI Registered Research Analyst)
**Classification**: Systematic Performance Attribution & Visual Analytics

---

## Executive Overview
Institutional allocators and risk committees evaluate quantitative strategies not through terminal printouts, but via structured, publication-quality **Performance Tear Sheets**.

This engine implements the core attribution logic used in institutional desks:
1. **6x2 KPI Scorecard Grid**: Total Net PnL, CAGR, Sharpe Ratio, Sortino Ratio, Calmar Ratio, Maximum Drawdown, Win Rate, Profit Factor, Total Trades, Expectancy, and Recovery Factor.
2. **Multi-Year Monthly Returns Matrix**: Calendar year vs. month return distribution grid with annual performance rollups.
3. **Underwater Drawdown Dynamics**: Continuous tracking of peak-to-trough equity degradation, duration, and recovery phases.
4. **Publication-Grade PDF Engine**: Direct compilation of executive 3-page tear sheets with clean tabular styling and currency formatting.

---

## Mathematical Formulations

### 1. Annualized Sharpe Ratio
$$\text{Sharpe} = \frac{\mu_{R} - R_f / 252}{\sigma_{R}} \times \sqrt{252}$$
Where $R_f = 6.50\%$ (RBI benchmark repo rate).

### 2. Downside Deviation & Sortino Ratio
$$\sigma_{\text{downside}} = \sqrt{\frac{1}{N-1}\sum_{t=1}^{N} \min(0, R_t)^2}$$
$$\text{Sortino} = \frac{\mu_R - R_f / 252}{\sigma_{\text{downside}}} \times \sqrt{252}$$

### 3. Calmar Ratio
$$\text{Calmar} = \frac{\text{CAGR (\%)}}{\text{Max Drawdown (\%)}}$$

---

## Unit Test Verification
```bash
python -m unittest research_showcases.institutional_tearsheet_generator.test_tearsheet_builder
```
