# Options Implied Volatility Surface & Greeks Engine
## Institutional Research Note & Implementation
**Author**: Prince Chauhan (SEBI Registered Research Analyst)

---

### 1. Research Question & Mathematical Motivation
Liquid options markets exhibit prominent volatility smiles and skewness across moneyness ($k = \ln(K/F)$) and term structure. Direct naive interpolation across raw option quotes frequently produces:
1. **Numerical Inversion Failures**: Vanishing Vega near deep ITM/OTM wings causing standard Newton-Raphson solvers to diverge.
2. **Calendar & Butterfly Arbitrage Violations**: Non-convex total variance slices resulting in negative implied probability density ($\partial^2 C / \partial K^2 < 0$).
3. **Microstructure Quote Noise**: Distortions from stale quotes, wide bid-ask spreads, and zero-bid illiquid wing contracts.

This showcase implements a **high-precision, arbitrage-free options volatility modeling engine** featuring:
- Hybrid Newton-Raphson solver with guaranteed Brent root-finding fallback.
- Gatheral's **Raw SVI (Stochastic Volatility Inspired)** formulation for total implied variance fitting.
- Closed-form analytical Greeks (Delta, Gamma, Vega, Theta, Rho).
- Microstructure bad-quote scrubbing and dealer Gamma Exposure (GEX) profile aggregation.

---

### 2. Mathematical Framework

#### A. Total Implied Variance & Raw SVI Parameterization
Following Gatheral (2004), for a given time to expiry $T$, total implied variance $w(k) = \sigma_{\text{BS}}^2(k) T$ is modeled as:
$$w(k; a, b, \rho, m, \sigma) = a + b \left[ \rho (k - m) + \sqrt{(k - m)^2 + \sigma^2} \right]$$

Subject to no-arbitrage boundary constraints:
- $a \in \mathbb{R}, \; b \ge 0$
- $|\rho| < 1$ (asymmetry bound)
- $\sigma > 0$ (smoothness parameter)
- $a + b \sigma \sqrt{1 - \rho^2} \ge 0$ (non-negative total variance)

#### B. Dealer Gamma Exposure (GEX) Profile
Dealer inventory positioning creates structural market pinning or volatility acceleration:
$$\text{GEX}_{\text{strike}} = \frac{(\text{OI}_{\text{CE}} - \text{OI}_{\text{PE}}) \times \Gamma \times S^2 \times 0.01}{10^7} \quad (\text{₹ Crores})$$
When aggregate Net GEX is positive, market-maker delta-hedging dampens realized volatility (mean-reverting regime). When Net GEX flips negative, dealer hedging amplifies trending momentum.

---

### 3. Running the Showcase & Unit Tests

Execute the unit test suite:
```bash
python -m unittest research_showcases.options_volatility_surface.test_surface_model
```

Sample Python execution:
```python
from research_showcases.options_volatility_surface import (
    black_scholes_price, implied_volatility, calculate_greeks, fit_svi_slice
)
import numpy as np

spot = 25000.0
strike = 25000.0
T = 7.0 / 365.0  # 7-day weekly contract
r = 0.065        # 6.5% RBI MIBOR benchmark
sigma = 0.14     # 14% annualized volatility

# 1. Analytical Pricing & Greeks
call_price = black_scholes_price(spot, strike, T, r, sigma, "CE")
greeks = calculate_greeks(spot, strike, T, r, sigma, "CE")
print(f"Call Price: ₹{call_price:.2f} | Delta: {greeks.delta:.4f} | Gamma: {greeks.gamma:.6f}")

# 2. Implied Volatility Solver
solved_iv = implied_volatility(call_price, spot, strike, T, r, "CE")
print(f"Solved IV: {solved_iv * 100:.2f}% (Error: {abs(solved_iv - sigma):.6f})")

# 3. SVI Strike Calibration
strikes = np.array([24400, 24600, 24800, 25000, 25200, 25400, 25600])
market_ivs = np.array([0.165, 0.155, 0.146, 0.140, 0.136, 0.134, 0.133])
svi_fit = fit_svi_slice(strikes, forward_F=25000.0, T=T, market_ivs=market_ivs)
print("SVI Calibration RMSE:", svi_fit["rmse"])
```

---

### 4. Methodological Limitations
- SVI parameters must be dynamically re-calibrated intraday to account for jump-diffusion events.
- Extreme OTM strikes with near-zero open interest may exhibit wide bid-ask spreads that distort wing curvature without liquidity weighting.
