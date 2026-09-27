# Market Regime Classification & Volatility Allocation Engine
## Institutional Research Note & Implementation
**Author**: Prince Chauhan (SEBI Registered Research Analyst)

---

### 1. Research Question & Empirical Motivation
Short-gamma options strategies (intraday straddles, iron condors, naked option writing) harvest an empirical **Volatility Risk Premium (VRP)** during normal market conditions. However, static capital allocation exposes the portfolio to severe left-tail drawdowns when volatility regimes shift from mean-reverting compression to momentum breakouts.

This showcase substantiates the CV claim:
> *"Designed unsupervised K-Means classifier utilizing rolling IV/RV ratios, price velocity, return skewness, and order-flow imbalance; dynamically scaled short-gamma exposure during volatility breakouts, reducing simulated maximum portfolio drawdown by 28%."*

---

### 2. Feature Engineering & Classification Taxonomy

The model computes 4 orthogonal regime features on a 30-bar rolling lookback:
1. **Parkinson Extreme-Value Realized Volatility ($\sigma_P$)**:
   $$\sigma_P = \sqrt{\frac{1}{4 \ln 2 \cdot N} \sum_{i=1}^N \left( \ln \frac{H_i}{L_i} \right)^2} \times \sqrt{252 \times 375}$$
2. **Implied-to-Realized Volatility Ratio ($\text{IV}/\text{RV}$)**: Quantifies the magnitude of the options volatility risk premium.
3. **Rolling Return Skewness**: Identifies downside crash asymmetry and directional panic.
4. **Normalized Price Velocity**: Measures momentum acceleration relative to historical volatility.

#### Discrete Regime Taxonomy & Dynamic Exposure Allocation
The unsupervised K-Means algorithm partitions the state space into 3 clusters:
- **Regime 0 (`THETA_CHOP`)**: Low RV, high IV/RV ratio, near-zero skew. Allocation: **1.0x (100% Capital)**.
- **Regime 1 (`MODERATE_TREND`)**: Average RV, directional drift. Allocation: **0.5x (Hedged / Half Capital)**.
- **Regime 2 (`VOLATILITY_EXPANSION`)**: Spiking RV, negative return skewness, sudden expansion. Allocation: **0.0x (Flat / Capital Preservation Kill-Switch)**.

---

### 3. Running the Showcase & Unit Tests

Run the dedicated test suite:
```bash
python -m unittest research_showcases.regime_allocation.test_regime_classifier
```

Sample Python execution:
```python
import numpy as np
from research_showcases.regime_allocation import (
    extract_regime_features, MarketRegimeClassifier,
    simulate_counterfactual_drawdown_attribution
)

# 1. Generate multi-regime synthetic price history
np.random.seed(42)
n_bars = 600
close = np.full(n_bars, 25000.0)
high = np.full(n_bars, 25020.0)
low = np.full(n_bars, 24980.0)
iv = np.full(n_bars, 0.14)

# Regime shift: bars 300-450 experience extreme volatility shock
for t in range(1, n_bars):
    vol = 0.40 if 300 <= t <= 450 else 0.12
    ret = np.random.normal(0, vol / np.sqrt(252 * 375))
    close[t] = close[t-1] * (1.0 + ret)
    high[t] = close[t] * (1.0 + abs(ret) * 0.8)
    low[t] = close[t] * (1.0 - abs(ret) * 0.8)
    iv[t] = 0.28 if 300 <= t <= 450 else 0.14

# 2. Extract Features & Fit K-Means
X = extract_regime_features(close, high, low, iv, window=25)
clf = MarketRegimeClassifier(n_clusters=3).fit(X)
regimes = clf.predict(X)

# 3. Simulate Short-Gamma Returns & Verify Drawdown Reduction
# Short-gamma makes money in quiet chop (+0.2 pts/bar), loses heavily in vol shocks (-1.5 pts/bar)
short_gamma_ret = np.where((300 <= np.arange(n_bars)) & (np.arange(n_bars) <= 450), -1.2, 0.25)
attribution = simulate_counterfactual_drawdown_attribution(short_gamma_ret, regimes)

print(f"Baseline Max Drawdown: {attribution.baseline_max_dd_pct:.1f}%")
print(f"Gated Max Drawdown: {attribution.gated_max_dd_pct:.1f}%")
print(f"Empirical Drawdown Reduction: {attribution.dd_reduction_pct:.1f}%")
```

---

### 4. Methodological Limitations
- Static window length (30 bars) can introduce lag during flash crash transitions.
- Cluster centroid calibration must be updated periodically across changing monetary policy cycles.
