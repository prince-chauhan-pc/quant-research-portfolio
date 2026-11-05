# -*- coding: utf-8 -*-
"""
Reproduce every number quoted in BENCHMARKS.md.

    python -m research_showcases.reproduce_benchmarks            # print
    python -m research_showcases.reproduce_benchmarks --write    # also rewrite BENCHMARKS.md

All inputs are synthetic and seeded, so the output is identical on every run.
These are demonstrations of the methods, not market results.
"""

import sys
from pathlib import Path

import numpy as np

from research_showcases.banknifty_cointegration import johansen_test, engle_granger_test
from research_showcases.options_volatility_surface import (
    black_scholes_price, implied_volatility, fit_svi_slice, check_butterfly_arbitrage,
)
from research_showcases.execution_simulator import simulate_latency_cost_comparison, expected_latency_drift_bps
from research_showcases.regime_allocation.regime_classifier import (
    extract_regime_features, MarketRegimeClassifier, simulate_counterfactual_drawdown_attribution,
)
from research_showcases.strategy_validator_gate import (
    probabilistic_sharpe_ratio, deflated_sharpe_ratio, expected_max_sharpe, probability_of_backtest_overfitting,
)

ROOT = Path(__file__).resolve().parent.parent


def cointegration_demo():
    rng = np.random.default_rng(11)
    t = 800
    common = np.cumsum(rng.normal(size=t))
    basket = np.column_stack([
        100 + common + rng.normal(scale=0.5, size=t),
        80 + 0.7 * common + rng.normal(scale=0.5, size=t),
        50 + np.cumsum(rng.normal(size=t)),
    ])
    jo = johansen_test(basket, k_ar_diff=1)
    eg = engle_granger_test(basket[:, 0], basket[:, 1])
    return [
        ("Johansen trace stat, H0: no relation (3-series basket, 1 true relation)",
         f"{jo.trace_stats[0]:.1f} vs 95% critical {jo.crit_95[0]:.1f}"),
        ("Johansen cointegration rank found at 95%", f"{jo.rank_95} (true: 1)"),
        ("Engle-Granger ADF t-stat on the cointegrated pair", f"{eg.t_stat:.2f} (5% critical {eg.critical_value_5pct})"),
        ("Hedge ratio recovered by Engle-Granger", f"{eg.hedge_ratio_beta:.3f} (true: {1 / 0.7:.3f})"),
    ]


def surface_demo():
    f, t, r = 25000.0, 7 / 365, 0.065
    strikes = np.arange(23500, 26600, 100, dtype=float)
    k = np.log(strikes / f)
    true_iv = 0.13 + 0.25 * k ** 2 - 0.08 * k
    prices = [black_scholes_price(f, kk, t, r, iv, "CE") for kk, iv in zip(strikes, true_iv)]
    solved = np.array([implied_volatility(p, f, kk, t, r, "CE") for p, kk in zip(prices, strikes)], dtype=float)
    fit = fit_svi_slice(strikes, f, t, true_iv)
    arb = check_butterfly_arbitrage(fit["params"], k_grid=np.linspace(k.min(), k.max(), 500))
    return [
        ("IV inversion max error, 31 strikes", f"{np.nanmax(np.abs(solved - true_iv)) * 100:.4f} vol points"),
        ("SVI fit RMSE in IV", f"{fit['rmse'] * 100:.3f} vol points"),
        ("Butterfly arbitrage check on fitted slice", "pass" if arb["arbitrage_free"] else f"FAIL (min g = {arb['min_g']:.4f})"),
    ]


def execution_demo():
    s = simulate_latency_cost_comparison(n_orders=2000, annual_volatility=0.15, slow_latency_ms=350, fast_latency_ms=5)
    theory = expected_latency_drift_bps(0.15, 350) - expected_latency_drift_bps(0.15, 5)
    return [
        ("Latency saving, 350 ms vs 5 ms, Nifty at 15% vol (simulated)", f"{s.cost_savings_bps:.2f} bps"),
        ("Same saving from the random-walk formula", f"{theory:.2f} bps"),
    ]


def regime_demo():
    rng = np.random.default_rng(42)
    n = 500
    close = np.full(n, 25000.0)
    high, low = close.copy(), close.copy()
    iv = np.full(n, 0.14)
    for i in range(1, n):
        vol = 0.45 if 250 <= i <= 350 else 0.12
        ret = rng.normal(0, vol / np.sqrt(252 * 375))
        close[i] = close[i - 1] * (1 + ret)
        high[i] = close[i] * (1 + abs(ret) * 0.9)
        low[i] = close[i] * (1 - abs(ret) * 0.9)
        iv[i] = 0.30 if 250 <= i <= 350 else 0.14
    x = extract_regime_features(close, high, low, iv, window=20)
    labels = MarketRegimeClassifier(n_clusters=3).fit(x).predict(x)
    pnl = np.where((np.arange(n) >= 250) & (np.arange(n) <= 350), -1.8, 0.30)
    res = simulate_counterfactual_drawdown_attribution(pnl, labels, lag_bars=1)
    return [
        ("Short-gamma max drawdown, no filter (synthetic shock)", f"{res.baseline_max_dd_pct:.1f} pts"),
        ("Same, regime filter applied with one-bar lag", f"{res.gated_max_dd_pct:.1f} pts ({res.dd_reduction_pct:.0f}% lower)"),
    ]


def overfitting_demo():
    rng = np.random.default_rng(1)
    noise = rng.normal(0.0, 0.01, (1000, 50))
    srs = noise.mean(0) / noise.std(0, ddof=1)
    best = noise[:, int(np.argmax(srs))]
    edge = noise.copy()
    edge[:, 0] += 0.002
    return [
        ("Best of 50 zero-edge strategies: annualised Sharpe", f"{srs.max() * np.sqrt(252):.2f}"),
        ("  its Probabilistic Sharpe (looks real)", f"{probabilistic_sharpe_ratio(best):.3f}"),
        ("  its Deflated Sharpe after counting 50 tries", f"{deflated_sharpe_ratio(best, 50, float(srs.var())):.3f}"),
        ("  luck benchmark: best annualised Sharpe expected from 50 tries", f"{expected_max_sharpe(50, float(srs.var())) * np.sqrt(252):.2f}"),
        ("PBO, 50 zero-edge strategies (CSCV, 10 blocks)", f"{probability_of_backtest_overfitting(noise).pbo:.2f}"),
        ("PBO, same set with one real edge added", f"{probability_of_backtest_overfitting(edge).pbo:.2f}"),
    ]


SECTIONS = [
    ("Cointegration (Bank Nifty basket method)", cointegration_demo),
    ("Volatility surface", surface_demo),
    ("Execution cost", execution_demo),
    ("Regime filter", regime_demo),
    ("Backtest overfitting", overfitting_demo),
]


def render() -> str:
    out = [
        "# Benchmarks",
        "",
        "Generated by `python -m research_showcases.reproduce_benchmarks --write`. Do not edit by hand.",
        "",
        "Every input is synthetic and seeded. These numbers show that each method does what it claims on data",
        "where the right answer is known. They are not trading results.",
        "",
    ]
    for title, fn in SECTIONS:
        out += [f"## {title}", "", "| Check | Result |", "|---|---|"]
        out += [f"| {k} | {v} |" for k, v in fn()]
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    text = render()
    print(text)
    if "--write" in sys.argv:
        (ROOT / "BENCHMARKS.md").write_text(text + "\n", encoding="utf-8")
        print(f"\nWrote {ROOT / 'BENCHMARKS.md'}")
