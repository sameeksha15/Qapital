"""Relaxation + rounding (spec §8).

Let each stock be bought in any amount between 0 and 1 (instead of 0 or 1), keep "exactly K in total" and the sector
cap, and minimise the same score; that is a convex problem, solved exactly. Its optimum is a lower bound no portfolio
can beat. Rounding then takes the stocks with the largest amounts, skipping any whose sector is already full."""

from dataclasses import dataclass

import cvxpy as cp
import numpy as np

from qapital.core.schemas import MarketData, Settings


@dataclass(frozen=True)
class Relaxed:
    chosen: np.ndarray  # ascending stock indices of the rounded portfolio
    lower_bound: float  # optimum of the relaxed problem, in score units
    amounts: np.ndarray  # the relaxed solution, one value in [0, 1] per stock


def relax_and_round(data: MarketData, settings: Settings) -> Relaxed:
    n = len(data.tickers)
    x = cp.Variable(n)
    constraints = [x >= 0, x <= 1, cp.sum(x) == settings.k]
    if settings.sector_cap is not None:
        for sector in sorted(set(data.sectors)):
            members = [i for i, s in enumerate(data.sectors) if s == sector]
            if len(members) > settings.sector_cap:
                constraints.append(cp.sum(x[members]) <= settings.sector_cap)
    objective = settings.risk_aversion * cp.quad_form(x, cp.psd_wrap(data.sigma)) - data.mu @ x + data.fees @ x
    problem = cp.Problem(cp.Minimize(objective), constraints)
    problem.solve()
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise ValueError("The relaxed problem has no solution with these rules. Allow more stocks per sector.")
    amounts = np.clip(np.asarray(x.value, dtype=float), 0, 1)
    return Relaxed(chosen=_round(amounts, data, settings), lower_bound=float(problem.value), amounts=amounts)


def _round(amounts: np.ndarray, data: MarketData, settings: Settings) -> np.ndarray:
    chosen: list[int] = []
    per_sector: dict[str, int] = {}
    for i in np.argsort(-amounts, kind="stable"):
        sector = data.sectors[i]
        if settings.sector_cap is None or per_sector.get(sector, 0) < settings.sector_cap:
            chosen.append(int(i))
            per_sector[sector] = per_sector.get(sector, 0) + 1
            if len(chosen) == settings.k:
                break
    return np.sort(np.array(chosen))
