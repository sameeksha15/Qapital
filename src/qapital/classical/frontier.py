"""Efficient frontiers: the best yearly return available at each level of yearly volatility.

Continuous: fractional amounts, with at most 1/K of the money in any stock and at most cap/K in any sector, i.e.
the money-weighted version of "K stocks, equal money in each". Discrete: the best real K-stock portfolios."""

import cvxpy as cp
import numpy as np

from qapital.core.portfolios import AllPortfolios
from qapital.core.schemas import MarketData, Settings

POINTS = 30
Curve = list[tuple[float, float]]  # (volatility, return), volatility increasing


def continuous_frontier(data: MarketData, settings: Settings, points: int = POINTS) -> Curve:
    n, k = len(data.tickers), settings.k
    w = cp.Variable(n)
    constraints = [w >= 0, w <= 1 / k, cp.sum(w) == 1]
    if settings.sector_cap is not None:
        for sector in sorted(set(data.sectors)):
            members = [i for i, s in enumerate(data.sectors) if s == sector]
            if len(members) > settings.sector_cap:
                constraints.append(cp.sum(w[members]) <= settings.sector_cap / k)
    variance = cp.quad_form(w, cp.psd_wrap(data.sigma))

    # Several mixes can share the lowest risk; the frontier starts at the one with the highest return.
    least_risk = cp.Problem(cp.Minimize(variance), constraints)
    least_risk.solve()
    cp.Problem(cp.Maximize(data.mu @ w), [*constraints, variance <= least_risk.value * (1 + 1e-6)]).solve()
    lowest = float(data.mu @ w.value)
    cp.Problem(cp.Maximize(data.mu @ w), constraints).solve()
    top = np.asarray(w.value, dtype=float)
    highest = float(data.mu @ top)

    curve = []
    for target in np.linspace(lowest, highest, points)[:-1]:
        problem = cp.Problem(cp.Minimize(variance), [*constraints, data.mu @ w >= target - 1e-9])
        problem.solve()
        if problem.status in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            curve.append((float(np.sqrt(max(problem.value, 0))), float(data.mu @ w.value)))
    # At the very top only one mix reaches the target; take it directly rather than asking the solver to pin it down.
    curve.append((float(np.sqrt(max(top @ data.sigma @ top, 0))), highest))
    return curve


def discrete_frontier(portfolios: AllPortfolios) -> Curve:
    """Upper-left envelope: each kept portfolio has a higher return than every less risky one."""
    curve, best_return = [], -np.inf
    for i in np.lexsort((-portfolios.returns, portfolios.risks)):
        if portfolios.returns[i] > best_return:
            best_return = portfolios.returns[i]
            curve.append((float(portfolios.risks[i]), float(portfolios.returns[i])))
    return curve
