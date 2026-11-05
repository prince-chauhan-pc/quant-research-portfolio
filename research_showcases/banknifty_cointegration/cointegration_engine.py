# -*- coding: utf-8 -*-
"""
Bank Nifty Basket Cointegration & Statistical Arbitrage Engine
==============================================================================
Author: Prince Chauhan Quant Desk (SEBI Registered Research Analyst)
Architecture:
- Engle-Granger two-step test for pairs; Johansen trace test for baskets.
- Rolling dynamic beta / hedge ratio estimation via Ordinary Least Squares (OLS).
- Ornstein-Uhlenbeck (OU) mean-reversion modeling and empirical half-life estimation.
- Normalized rolling Z-score spread generation.
- Causal pairs execution simulator with explicit round-trip friction and stop-loss bounds.
- 100% self-contained: pure NumPy/SciPy linear algebra without heavy dependencies.
==============================================================================
"""

import math
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple


@dataclass
class CointegrationResult:
    is_cointegrated: bool
    t_stat: float
    critical_value_1pct: float
    critical_value_5pct: float
    critical_value_10pct: float
    p_value_approx: float
    hedge_ratio_beta: float
    intercept_alpha: float
    half_life_bars: float


@dataclass
class SpreadTrade:
    entry_idx: int
    exit_idx: int
    direction: str          # 'LONG_SPREAD' or 'SHORT_SPREAD'
    entry_zscore: float
    exit_zscore: float
    entry_spread: float
    exit_spread: float
    gross_pnl_pts: float
    net_pnl_pts: float      # After 0.50% combined leg friction
    duration_bars: int


def calculate_ols(y: np.ndarray, x: np.ndarray) -> Tuple[float, float, np.ndarray]:
    """
    Fits y = alpha + beta * x via closed-form OLS.
    Returns: (beta, alpha, residuals)
    """
    x_mean = np.mean(x)
    y_mean = np.mean(y)

    var_x = np.var(x)
    if var_x <= 1e-12:
        return 1.0, 0.0, y - x

    cov_xy = np.mean((x - x_mean) * (y - y_mean))
    beta = cov_xy / var_x
    alpha = y_mean - beta * x_mean
    residuals = y - (alpha + beta * x)

    return float(beta), float(alpha), residuals


def estimate_ornstein_uhlenbeck_halflife(residuals: np.ndarray) -> float:
    """
    Estimates Ornstein-Uhlenbeck mean-reversion speed:
    delta_e(t) = lambda * (mu - e(t-1)) * dt + noise
    Half-life tau = -ln(2) / lambda
    """
    if len(residuals) < 10:
        return 999.0

    e_lag = residuals[:-1]
    delta_e = residuals[1:] - e_lag

    # Regress delta_e on e_lag: delta_e = a + b * e_lag
    var_lag = np.var(e_lag)
    if var_lag <= 1e-12:
        return 999.0

    b = np.mean((e_lag - np.mean(e_lag)) * (delta_e - np.mean(delta_e))) / var_lag

    if b >= 0.0:
        return 999.0  # Mean-divergent or random walk

    # lambda = -b
    halflife = -math.log(2.0) / math.log(1.0 + b) if (1.0 + b) > 0 else 1.0
    return max(1.0, min(float(halflife), 500.0))


def engle_granger_test(y: np.ndarray, x: np.ndarray, max_lags: int = 1) -> CointegrationResult:
    """
    Performs Engle-Granger two-step cointegration test using ADF on OLS residuals.
    MacKinnon (1991) asymptotic critical values for 2 variables:
    1%: -3.90, 5%: -3.34, 10%: -3.04
    """
    beta, alpha, residuals = calculate_ols(y, x)
    n = len(residuals)
    if n < 30:
        return CointegrationResult(
            is_cointegrated=False, t_stat=0.0, critical_value_1pct=-3.90,
            critical_value_5pct=-3.34, critical_value_10pct=-3.04,
            p_value_approx=1.0, hedge_ratio_beta=beta, intercept_alpha=alpha,
            half_life_bars=999.0
        )

    # ADF test on residuals: delta_e(t) = gamma * e(t-1) + sum(phi_i * delta_e(t-i))
    delta_e = np.diff(residuals)
    y_reg = delta_e[max_lags:]
    x_lag = residuals[max_lags:-1]

    # Design matrix with lagged differences
    if max_lags > 0:
        lagged_diffs = np.column_stack([delta_e[max_lags - i - 1: -i - 1] for i in range(max_lags)])
        X_mat = np.column_stack([x_lag, lagged_diffs])
    else:
        X_mat = x_lag.reshape(-1, 1)

    # Solve X_mat * params = y_reg
    params, residuals_adf, rank, s = np.linalg.lstsq(X_mat, y_reg, rcond=None)
    gamma = params[0]

    # Standard error of gamma
    residuals_reg = y_reg - X_mat @ params
    sigma_sq = np.sum(residuals_reg ** 2) / (len(y_reg) - X_mat.shape[1])
    try:
        var_cov = sigma_sq * np.linalg.inv(X_mat.T @ X_mat)
        se_gamma = math.sqrt(max(1e-12, var_cov[0, 0]))
        t_stat = float(gamma / se_gamma)
    except np.linalg.LinAlgError:
        t_stat = 0.0

    cv_1 = -3.90
    cv_5 = -3.34
    cv_10 = -3.04

    is_coint = bool(t_stat < cv_5)
    halflife = estimate_ornstein_uhlenbeck_halflife(residuals)

    # Approximate p-value based on MacKinnon surface
    if t_stat < cv_1:
        p_val = 0.005
    elif t_stat < cv_5:
        p_val = 0.035
    elif t_stat < cv_10:
        p_val = 0.085
    else:
        p_val = min(1.0, 0.10 + (t_stat - cv_10) * 0.15)

    return CointegrationResult(
        is_cointegrated=is_coint,
        t_stat=round(t_stat, 3),
        critical_value_1pct=cv_1,
        critical_value_5pct=cv_5,
        critical_value_10pct=cv_10,
        p_value_approx=round(p_val, 4),
        hedge_ratio_beta=round(beta, 4),
        intercept_alpha=round(alpha, 4),
        half_life_bars=round(halflife, 1)
    )


def calculate_rolling_hedge_ratio(y: np.ndarray, x: np.ndarray, window: int = 60) -> np.ndarray:
    """
    Calculates rolling OLS hedge ratio (beta) to adapt to structural basis drift.
    """
    n = len(y)
    betas = np.zeros(n)
    for i in range(n):
        if i < window:
            b, _, _ = calculate_ols(y[:max(10, i + 1)], x[:max(10, i + 1)])
        else:
            b, _, _ = calculate_ols(y[i - window:i], x[i - window:i])
        betas[i] = b
    return betas


def calculate_spread_zscore(spread: np.ndarray, window: int = 60) -> np.ndarray:
    """
    Computes rolling mean and standard deviation normalized Z-score:
    Z(t) = (spread(t) - mean_rolling) / std_rolling
    """
    n = len(spread)
    z = np.zeros(n)
    for i in range(n):
        start = max(0, i - window + 1)
        sub = spread[start:i + 1]
        m = np.mean(sub)
        s = np.std(sub)
        z[i] = (spread[i] - m) / s if s > 1e-6 else 0.0
    return z


def simulate_pairs_trade(
    spread: np.ndarray,
    zscore: np.ndarray,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    stop_z: float = 3.5,
    friction_pct: float = 0.0050
) -> List[SpreadTrade]:
    """
    Simulates statistical arbitrage pairs trading on mean-reverting spread:
    - Long spread when Z < -entry_z, Short spread when Z > entry_z.
    - Exit when |Z| <= exit_z.
    - Stop loss when |Z| >= stop_z.
    - Pre-deducts 0.50% combined leg turnover friction.
    """
    trades = []
    position = 0  # +1: Long spread, -1: Short spread, 0: Flat
    entry_idx = 0
    entry_spread = 0.0
    entry_z_val = 0.0

    for i in range(len(spread)):
        z = zscore[i]
        s = spread[i]

        if position == 0:
            if z <= -entry_z:
                position = 1  # Long spread
                entry_idx = i
                entry_spread = s
                entry_z_val = z
            elif z >= entry_z:
                position = -1  # Short spread
                entry_idx = i
                entry_spread = s
                entry_z_val = z
        elif position == 1:
            # Long spread: exit when reverts up to -exit_z or stops out at -stop_z
            if z >= -exit_z or z <= -stop_z or i == len(spread) - 1:
                gross_pnl = s - entry_spread
                friction = (abs(entry_spread) + abs(s)) * friction_pct
                net_pnl = gross_pnl - friction
                trades.append(SpreadTrade(
                    entry_idx=entry_idx, exit_idx=i, direction="LONG_SPREAD",
                    entry_zscore=round(entry_z_val, 2), exit_zscore=round(z, 2),
                    entry_spread=round(entry_spread, 2), exit_spread=round(s, 2),
                    gross_pnl_pts=round(gross_pnl, 2), net_pnl_pts=round(net_pnl, 2),
                    duration_bars=i - entry_idx
                ))
                position = 0
        elif position == -1:
            # Short spread: exit when reverts down to exit_z or stops out at stop_z
            if z <= exit_z or z >= stop_z or i == len(spread) - 1:
                gross_pnl = entry_spread - s
                friction = (abs(entry_spread) + abs(s)) * friction_pct
                net_pnl = gross_pnl - friction
                trades.append(SpreadTrade(
                    entry_idx=entry_idx, exit_idx=i, direction="SHORT_SPREAD",
                    entry_zscore=round(entry_z_val, 2), exit_zscore=round(z, 2),
                    entry_spread=round(entry_spread, 2), exit_spread=round(s, 2),
                    gross_pnl_pts=round(gross_pnl, 2), net_pnl_pts=round(net_pnl, 2),
                    duration_bars=i - entry_idx
                ))
                position = 0

    return trades


# ==============================================================================
# JOHANSEN COINTEGRATION TEST (basket of 2+ series)
# ==============================================================================
# Trace-test critical values (90%, 95%, 99%) for a constant term in the
# cointegrating relation (det_order = 0), indexed by number of series minus
# hypothesised rank. Source: MacKinnon, Haug & Michelis (1999), as tabulated
# in statsmodels.tsa.coint_tables.c_sjt(n, 0).
_JOHANSEN_TRACE_CV = {
    1: (2.7055, 3.8415, 6.6349),
    2: (13.4294, 15.4943, 19.9349),
    3: (27.0669, 29.7961, 35.4628),
    4: (44.4929, 47.8545, 54.6815),
    5: (65.8202, 69.8189, 77.8202),
    6: (91.1090, 95.7542, 104.9637),
}


@dataclass
class JohansenResult:
    rank_95: int                 # number of cointegrating relations at 95%
    trace_stats: List[float]     # trace statistic for H0: rank <= r, r = 0..n-1
    crit_95: List[float]
    eigenvalues: List[float]
    first_vector: List[float]    # basket weights of the strongest relation (first weight = 1)


def johansen_test(prices: np.ndarray, k_ar_diff: int = 1) -> JohansenResult:
    """
    Johansen trace test on a (T x n) price matrix, constant in the cointegrating
    relation, k_ar_diff lagged differences. Pure NumPy port of the standard
    algorithm; matches statsmodels coint_johansen(det_order=0).
    """
    y = np.asarray(prices, dtype=float)
    if y.ndim != 2 or y.shape[1] < 2:
        raise ValueError("prices must be a T x n matrix with n >= 2")
    n = y.shape[1]
    if n > max(_JOHANSEN_TRACE_CV):
        raise ValueError(f"critical values available for up to {max(_JOHANSEN_TRACE_CV)} series")

    y = y - y.mean(axis=0)
    dy = np.diff(y, axis=0)
    # lagged differences as regressors
    if k_ar_diff > 0:
        z = np.column_stack([dy[k_ar_diff - i - 1: len(dy) - i - 1] for i in range(k_ar_diff)])
        z = z - z.mean(axis=0)
    else:
        z = np.empty((len(dy), 0))
    dy_t = dy[k_ar_diff:]
    dy_t = dy_t - dy_t.mean(axis=0)
    y_lag = y[1: len(y) - k_ar_diff]
    y_lag = y_lag - y_lag.mean(axis=0)

    def resid(a, x):
        if x.size == 0:
            return a
        return a - x @ (np.linalg.pinv(x) @ a)

    r0 = resid(dy_t, z)
    rk = resid(y_lag, z)
    t_obs = rk.shape[0]
    skk = rk.T @ rk / t_obs
    sk0 = rk.T @ r0 / t_obs
    s00 = r0.T @ r0 / t_obs
    m = np.linalg.inv(skk) @ sk0 @ np.linalg.inv(s00) @ sk0.T
    eigvals, eigvecs = np.linalg.eig(m)
    eigvals, eigvecs = np.real(eigvals), np.real(eigvecs)
    order = np.argsort(eigvals)[::-1]
    eigvals, eigvecs = eigvals[order], eigvecs[:, order]

    trace = [float(-t_obs * np.sum(np.log(1.0 - eigvals[r:]))) for r in range(n)]
    crit95 = [_JOHANSEN_TRACE_CV[n - r][1] for r in range(n)]
    rank = 0
    for r in range(n):
        if trace[r] > crit95[r]:
            rank = r + 1
        else:
            break

    v = eigvecs[:, 0]
    v = v / v[0] if abs(v[0]) > 1e-12 else v
    return JohansenResult(
        rank_95=rank,
        trace_stats=[round(s, 4) for s in trace],
        crit_95=crit95,
        eigenvalues=[round(float(e), 6) for e in eigvals],
        first_vector=[round(float(w), 6) for w in v],
    )
