# -*- coding: utf-8 -*-
"""
Backtest overfitting statistics
==============================================================================
- Probabilistic Sharpe Ratio (PSR): chance the true Sharpe beats a benchmark,
  allowing for sample length, skew and fat tails.
- Deflated Sharpe Ratio (DSR): PSR where the benchmark is the best Sharpe you
  would expect from luck alone after trying N strategy variants.
- Probability of Backtest Overfitting (PBO): combinatorially symmetric
  cross-validation (CSCV). How often the variant that looked best in-sample
  lands in the bottom half out-of-sample.

References: Bailey & Lopez de Prado (2012, 2014); Bailey, Borwein,
Lopez de Prado & Zhu (2017). All Sharpe ratios here are per-period
(not annualised), as the formulas require.
==============================================================================
"""

import itertools
import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.stats import norm, skew, kurtosis

EULER_GAMMA = 0.5772156649015329


def sharpe_per_period(returns: Sequence[float]) -> float:
    r = np.asarray(returns, dtype=float)
    sd = r.std(ddof=1)
    return float(r.mean() / sd) if sd > 0 else 0.0


def probabilistic_sharpe_ratio(returns: Sequence[float], benchmark_sr: float = 0.0) -> float:
    """P(true per-period Sharpe > benchmark_sr) given the observed returns."""
    r = np.asarray(returns, dtype=float)
    t = len(r)
    if t < 3:
        raise ValueError("need at least 3 returns")
    sr = sharpe_per_period(r)
    g3 = float(skew(r))
    g4 = float(kurtosis(r, fisher=False))  # plain kurtosis, normal = 3
    denom = 1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr ** 2
    if denom <= 0:
        return float("nan")
    return float(norm.cdf((sr - benchmark_sr) * math.sqrt(t - 1) / math.sqrt(denom)))


def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """Best per-period Sharpe expected from n_trials of pure noise with the given
    cross-trial variance of Sharpe ratios (False Strategy Theorem)."""
    if n_trials < 2:
        return 0.0
    return math.sqrt(sr_variance) * (
        (1 - EULER_GAMMA) * norm.ppf(1 - 1.0 / n_trials)
        + EULER_GAMMA * norm.ppf(1 - 1.0 / (n_trials * math.e))
    )


def deflated_sharpe_ratio(returns: Sequence[float], n_trials: int, sr_variance: float) -> float:
    """PSR against the luck benchmark implied by n_trials variants tried."""
    return probabilistic_sharpe_ratio(returns, expected_max_sharpe(n_trials, sr_variance))


@dataclass
class PBOResult:
    pbo: float               # share of splits where the in-sample winner ranks below median out-of-sample
    n_splits: int
    mean_logit: float


def probability_of_backtest_overfitting(returns_matrix: np.ndarray, n_blocks: int = 10) -> PBOResult:
    """
    CSCV on a (T x N) matrix: T periods of returns for N strategy variants.
    Splits time into n_blocks (even), tries every half/half combination.
    """
    m = np.asarray(returns_matrix, dtype=float)
    t, n = m.shape
    if n < 2:
        raise ValueError("need at least 2 strategy variants")
    if n_blocks % 2 or n_blocks < 2:
        raise ValueError("n_blocks must be an even number >= 2")
    blocks = np.array_split(np.arange(t), n_blocks)
    logits = []
    for is_ids in itertools.combinations(range(n_blocks), n_blocks // 2):
        is_rows = np.concatenate([blocks[i] for i in is_ids])
        oos_rows = np.concatenate([blocks[i] for i in range(n_blocks) if i not in is_ids])
        is_sr = _col_sharpe(m[is_rows])
        oos_sr = _col_sharpe(m[oos_rows])
        best = int(np.argmax(is_sr))
        # relative rank of the IS winner out-of-sample, in (0, 1)
        rank = (np.sum(oos_sr < oos_sr[best]) + 0.5 * (np.sum(oos_sr == oos_sr[best]) + 1)) / (n + 1)
        logits.append(math.log(rank / (1 - rank)))
    logits = np.array(logits)
    return PBOResult(pbo=float(np.mean(logits <= 0)), n_splits=len(logits), mean_logit=float(logits.mean()))


def _col_sharpe(x: np.ndarray) -> np.ndarray:
    sd = x.std(axis=0, ddof=1)
    sd[sd == 0] = np.inf
    return x.mean(axis=0) / sd
