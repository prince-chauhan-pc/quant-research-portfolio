# Volatility regime filter

Cuts short-gamma size when the market moves into a high-volatility state.

What it does:
- **Features per bar.** Parkinson (high-low) realised volatility, IV / realised vol ratio, rolling skew, and how fast price is moving.
- **Regimes.** k-means with 3 clusters, sorted from calm to stressed.
- **Sizing.** Full size in the calm regime, half in the middle one, flat in the stressed one.
- **No lookahead.** A bar's regime uses that bar's own high and low, so it can only size the next bar. `lag_bars` must be at least 1 and the function refuses 0.

```bash
python -m unittest research_showcases.regime_allocation.test_regime_classifier
```

Limits: the example fits k-means on the whole sample. For a real test, fit on a training window and predict forward.
