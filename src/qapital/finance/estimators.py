"""Expected returns and covariance from daily returns, three ways (all yearly, 252 trading days):

- "historical": average daily return and sample covariance. Extreme past winners dominate.
- "shrunk": Bayes-Stein returns (Jorion 1986): each stock's average is pulled towards the return of the
  minimum-variance portfolio, more strongly when the averages are noisy relative to how far apart they are.
- "shrunk-lw" (default): Bayes-Stein returns with the Ledoit-Wolf (2004) shrunk covariance, used both for the
  shrinkage itself and as the risk model."""

from typing import Literal

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

TRADING_DAYS = 252
Method = Literal["historical", "shrunk", "shrunk-lw"]
METHODS: tuple[Method, ...] = ("historical", "shrunk", "shrunk-lw")
DEFAULT_METHOD: Method = "shrunk-lw"


def yearly_moments(returns: pd.DataFrame, method: Method = DEFAULT_METHOD) -> tuple[np.ndarray, np.ndarray, float]:
    """Yearly expected returns, yearly covariance, and the shrinkage intensity applied to the returns (0 = none)."""
    if method not in METHODS:
        raise ValueError(f"Unknown estimate '{method}'. Choose one of: {', '.join(METHODS)}.")
    daily = returns.to_numpy(dtype=float)
    mean = daily.mean(axis=0)
    covariance = ledoit_wolf(daily) if method == "shrunk-lw" else np.cov(daily, rowvar=False)
    intensity = 0.0
    if method != "historical":
        mean, intensity = bayes_stein(mean, covariance, len(daily))
    return mean * TRADING_DAYS, covariance * TRADING_DAYS, intensity


def ledoit_wolf(daily: np.ndarray) -> np.ndarray:
    return LedoitWolf().fit(daily).covariance_


def bayes_stein(mean: np.ndarray, covariance: np.ndarray, observations: int) -> tuple[np.ndarray, float]:
    """Jorion's Bayes-Stein estimator: shrink `mean` towards the minimum-variance portfolio's return."""
    n = len(mean)
    inverse = np.linalg.pinv(covariance)
    ones = np.ones(n)
    weights = inverse @ ones / (ones @ inverse @ ones)
    target = float(weights @ mean)
    gap = mean - target
    intensity = (n + 2) / ((n + 2) + observations * float(gap @ inverse @ gap))
    intensity = float(np.clip(intensity, 0.0, 1.0))
    return (1 - intensity) * mean + intensity * target, intensity
