# Cointegration and pairs / basket trading

Finds price combinations that move back to an average, and trades the gap.

What it does:
- **Engle-Granger (pairs).** OLS hedge ratio, then an ADF test on the leftover spread with MacKinnon critical values.
- **Johansen (baskets of 2 to 6 series).** Trace test with a constant in the relation; returns how many independent mean-reverting combinations exist and the basket weights of the strongest one. Pure NumPy, checked against statsmodels `coint_johansen` to three decimals.
- **Half-life.** How many bars the spread takes to close half its gap (Ornstein-Uhlenbeck fit).
- **Rolling hedge ratio and z-score.**
- **Pairs simulator.** Enter at |z| > 2, exit at |z| < 0.5, stop at |z| > 3.5, 0.50% cost on both legs.

```bash
python -m unittest research_showcases.banknifty_cointegration.test_cointegration research_showcases.banknifty_cointegration.test_johansen
```

Limits: critical values cover up to 6 series. Cointegration found in one window often breaks later; re-test on a rolling basis before trading it.
