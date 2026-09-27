# Bank Nifty Basket Cointegration & Statistical Arbitrage Engine
## Institutional Research Note & Implementation
**Author**: Prince Chauhan (SEBI Registered Research Analyst)

---

### 1. Research Question & Econometric Motivation
Pairs trading and basket statistical arbitrage rely on the assumption of **cointegration**—the existence of a stationary linear combination between two or more non-stationary price series $I(1)$:
$$e_t = y_t - \beta x_t - \alpha \sim I(0)$$

Standard correlation is a flawed metric for statistical arbitrage: two assets can exhibit a 95% rolling correlation yet diverge indefinitely without mean-reverting. Cointegration guarantees that deviations from the equilibrium basis are temporary and mean-reverting.

This showcase implements a **vectorized statistical arbitrage engine** calibrated for Indian banking equities (HDFC Bank, ICICI Bank, SBI, Axis Bank, Kotak Mahindra Bank):
- Two-step **Engle-Granger cointegration test** with Augmented Dickey-Fuller (ADF) stationarity evaluation.
- **Ornstein-Uhlenbeck (OU)** continuous-time stochastic process calibration for empirical half-life estimation ($\tau$).
- **Rolling dynamic OLS hedge ratio ($\beta$)** to accommodate structural macroeconomic drift.
- Causal Z-score execution simulator with stop-loss boundaries and explicit 0.50% combined leg turnover friction.

---

### 2. Mathematical Framework

#### A. Cointegration Test & Stationarity Verification
Given two asset price series $y_t$ (e.g. HDFCBANK) and $x_t$ (e.g. ICICIBANK):
1. **Cointegrating Regression**:
   $$y_t = \alpha + \beta x_t + e_t$$
2. **ADF Stationarity Test on Residuals**:
   $$\Delta e_t = \gamma e_{t-1} + \sum_{i=1}^p \phi_i \Delta e_{t-i} + \epsilon_t$$
   We test the null hypothesis $H_0: \gamma = 0$ (unit root / non-stationary) against $H_1: \gamma < 0$. The test statistic $t_\gamma$ is compared against MacKinnon (1991) asymptotic critical values:
   $$\text{Reject } H_0 \text{ at 5\% level if } t_\gamma < -3.34$$

#### B. Ornstein-Uhlenbeck Half-Life Estimation
The spread residual $e_t$ is modeled as a mean-reverting OU diffusion:
$$d e_t = \lambda (\mu - e_t) dt + \sigma dW_t$$

Regressing $\Delta e_t = a + b e_{t-1}$ yields the mean-reversion speed $\lambda = -b$. The empirical half-life is:
$$\tau = \frac{-\ln 2}{\ln(1 + b)} \approx \frac{-\ln 2}{\lambda}$$
If $\tau > 120$ bars, the spread reverts too slowly to overcome transaction costs. Ideal statistical arbitrage pairs exhibit $10 \le \tau \le 60$ bars.

---

### 3. Running the Showcase & Unit Tests

Run the dedicated test suite:
```bash
python -m unittest research_showcases.banknifty_cointegration.test_cointegration
```

Sample Python execution:
```python
import numpy as np
from research_showcases.banknifty_cointegration import (
    engle_granger_test, calculate_spread_zscore, simulate_pairs_trade
)

# Generate synthetic cointegrated banking pair
np.random.seed(42)
n_bars = 500
common_trend = np.cumsum(np.random.normal(0.05, 1.0, n_bars))
spread_ou = np.zeros(n_bars)
for t in range(1, n_bars):
    spread_ou[t] = 0.85 * spread_ou[t-1] + np.random.normal(0, 0.5)

x = 1000.0 + common_trend
y = 1.25 * x + 50.0 + spread_ou

# 1. Cointegration Test & Half-life
coint_res = engle_granger_test(y, x)
print(f"Cointegrated: {coint_res.is_cointegrated} | t-stat: {coint_res.t_stat:.2f} (5% CV: {coint_res.critical_value_5pct})")
print(f"Hedge Ratio Beta: {coint_res.hedge_ratio_beta:.4f} | Half-Life: {coint_res.half_life_bars:.1f} bars")

# 2. Z-Score Spread & Execution Simulation
spread = y - (coint_res.intercept_alpha + coint_res.hedge_ratio_beta * x)
zscore = calculate_spread_zscore(spread, window=60)
trades = simulate_pairs_trade(spread, zscore, entry_z=2.0, exit_z=0.5, friction_pct=0.0050)
print(f"Executed Pairs Trades: {len(trades)}")
```

---

### 4. Methodological Limitations
- Assumes linear cointegrating vector; does not account for regime-shifting non-linear basis breaks (e.g. RBI rate surprises).
- Cointegration can break down during merger, acquisition, or credit distress events.
