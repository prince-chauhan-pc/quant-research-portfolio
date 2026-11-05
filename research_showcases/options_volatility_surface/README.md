# Options volatility surface

Tools for turning an option chain into a smooth, arbitrage-checked volatility smile.

What it does:
- **Pricing and IV.** Black-Scholes prices and Greeks; IV inversion with Newton-Raphson, falling back to Brent when Newton steps leave the bracket.
- **Quote filter.** Drops zero bids, crossed or stale quotes before fitting.
- **SVI fit.** Fits the raw SVI smile (a, b, rho, m, sigma) to one expiry by least squares in IV space.
- **Arbitrage checks.**
  - Butterfly: computes Gatheral's density function g(k) across strikes; the slice is clean only if g(k) >= 0 everywhere.
  - Calendar: total variance at each strike must not fall as expiry gets longer.
- **Dealer gamma (GEX).** Net dealer gamma by strike, to see where hedging flows are likely to flip.

The tests include Axel Vogt's well-known SVI slice that looks fine but contains butterfly arbitrage; the check catches it.

```bash
python -m unittest research_showcases.options_volatility_surface.test_surface_model research_showcases.options_volatility_surface.test_arbitrage_checks
```

Limits: SVI parameters are fitted per expiry with simple bounds, not with the full SSVI no-arbitrage parameterisation. The checks tell you when a fit is bad; they do not repair it.
