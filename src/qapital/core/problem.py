"""The ONE score used by the quantum engine and every classical method.
Import it; never rewrite it. `score_many` is the formula; `score` is the same formula for one portfolio."""

import numpy as np

from qapital.core.schemas import MarketData, Settings


def score_many(chosen: np.ndarray, data: MarketData, settings: Settings) -> np.ndarray:
    """Scores of many portfolios at once. Each row of `chosen` holds the stock indices of one portfolio.
    Lower is better: risk_aversion · xᵀΣx − μᵀx + feesᵀx for the 0/1 vector x of that row."""
    chosen = np.atleast_2d(np.asarray(chosen, dtype=int))
    quadratic = data.sigma[chosen[:, :, None], chosen[:, None, :]].sum(axis=(1, 2))
    return settings.risk_aversion * quadratic - data.mu[chosen].sum(axis=1) + data.fees[chosen].sum(axis=1)


def score(x: np.ndarray, data: MarketData, settings: Settings) -> float:
    """Lower is better. x is a 0/1 vector over data.tickers."""
    return float(score_many(np.flatnonzero(np.asarray(x))[None, :], data, settings)[0])


def is_valid(x: np.ndarray, data: MarketData, settings: Settings) -> bool:
    x = np.asarray(x)
    if int(x.sum()) != settings.k:
        return False
    if settings.sector_cap is not None:
        chosen = [s for s, xi in zip(data.sectors, x, strict=True) if xi]
        if any(chosen.count(s) > settings.sector_cap for s in set(chosen)):
            return False
    return True


def portfolio_stats(x: np.ndarray, data: MarketData) -> tuple[float, float]:
    """Yearly return and volatility with equal money in each chosen stock."""
    x = np.asarray(x, dtype=float)
    w = x / x.sum()
    return float(data.mu @ w), float(np.sqrt(w @ data.sigma @ w))
