# Volatility regime filter

Cuts short-gamma size when the market moves into a high-volatility state.

What it does:
- **Features per bar.** Parkinson (high-low) realised volatility, IV / realised vol ratio, rolling skew, and how fast price is moving.
- **Regimes.** k-means with 3 clusters, sorted from calm to stressed.
- **Sizing.** Full size in the calm regime, half in the middle one, flat in the stressed one.
- **No lookahead.** A bar's regime uses that bar's own high and low, so it can only size the next bar. `lag_bars` must be at least 1 and the function refuses 0.

```bash
python -m pytest research_showcases/regime_allocation
```

Out of sample: `reproduce_benchmarks.py` and `test_walk_forward_fit_then_label_later_bars` fit k-means on a training window only and label later bars, including a shock the model has not seen. The other unit tests fit and label the same sample, to check cluster order and the lag rule.

Limits: synthetic data and a single train/test split. For real use, refit on a rolling window and test on the bars after it.
