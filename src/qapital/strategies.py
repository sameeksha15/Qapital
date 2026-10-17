"""Ways to pick stocks, for live runs and walk-forward backtests. Each takes the market (with trading costs already in
its fees) and the investor's settings, and returns the chosen tickers."""

import math

from qapital.classical.annealing import simulated_annealing
from qapital.core.portfolios import MAX_PORTFOLIOS, every_portfolio
from qapital.core.schemas import MarketData, Settings
from qapital.finance.walkforward import Selector
from qapital.quantum.solver import solve


def classical_best(seed: int = 42) -> Selector:
    """The exact best by brute force when the list is small enough to check every portfolio; otherwise the best that
    simulated annealing finds."""

    def select(data: MarketData, settings: Settings) -> list[str]:
        if math.comb(len(data.tickers), settings.k) <= MAX_PORTFOLIOS:
            chosen = every_portfolio(data, settings).best
        else:
            chosen, _ = simulated_annealing(data, settings, seed)
        return [data.tickers[int(i)] for i in chosen]

    return select


def quantum(**circuit) -> Selector:
    """QAOA (XY circuit by default): the best legal portfolio among the circuit's samples, on its shortlist."""

    def select(data: MarketData, settings: Settings) -> list[str]:
        return solve(data, settings.model_copy(update=circuit)).chosen

    return select


def everything(data: MarketData, settings: Settings) -> list[str]:
    """Every stock with enough history: the equal-split benchmark."""
    return list(data.tickers)
