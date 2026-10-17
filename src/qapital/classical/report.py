"""Every classical baseline on one problem, for the website's comparison table and frontier chart.

Simulated annealing, relaxation + rounding and random guessing run on the FULL list; the quantum circuit only sees the
shortlist, so the shortlist's own best is reported too. Random methods run over 10 seeds for a hit rate.

When every legal portfolio of the list can be checked (up to 2 million), brute force gives the proven best. Beyond
that, the best portfolio any method found is reported as the "best known", and is marked as not proven; random
guessing then samples legal portfolios uniformly by counting them instead of listing them."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from qapital.classical.annealing import simulated_annealing
from qapital.classical.frontier import Curve, continuous_frontier, discrete_frontier
from qapital.classical.random_guess import random_guess, random_guess_sampled
from qapital.classical.relaxation import relax_and_round
from qapital.core.portfolios import can_brute_force, count_legal, every_portfolio
from qapital.core.problem import portfolio_stats, score
from qapital.core.schemas import MarketData, Settings
from qapital.data.market import subset

RUNS_PER_METHOD = 10  # seeded runs of each random method, for its hit rate
MethodName = Literal["Brute force", "Simulated annealing", "Relaxation + rounding", "Random guessing"]


@dataclass
class Method:
    name: MethodName
    chosen: list[str]
    runtime_s: float
    universe: Literal["full", "shortlist"]
    hit_rate: float | None = None  # share of seeded runs that found the best (proven or best known)


@dataclass
class Classical:
    methods: list[Method]
    true_best: list[str]  # the proven best when best_is_exact, otherwise the best any classical method found
    best_is_exact: bool
    best_found_by: str
    num_valid: int  # legal portfolios of the full list (counted exactly, even when too many to list)
    shortlist_best: list[str]
    num_valid_shortlist: int
    relaxation_lower_bound: float  # in score units: no portfolio can score below this
    continuous_frontier: Curve
    discrete_frontier: Curve  # empty when the list is too long to check every portfolio


def run_classical(data: MarketData, settings: Settings, shortlist: list[str], shots: int) -> Classical:
    exact = can_brute_force(len(data.tickers), settings.k)
    seeds = range(settings.seed, settings.seed + RUNS_PER_METHOD)
    annealed = {seed: _timed(simulated_annealing, data, settings, seed) for seed in seeds}
    relaxed, relax_seconds = _timed(relax_and_round, data, settings)
    on_shortlist = every_portfolio(subset(data, shortlist), settings)
    by_score = _scorer(data, settings)

    methods: list[Method] = []
    if exact:
        everything, brute_seconds = _timed(every_portfolio, data, settings)
        guessed = {seed: _timed(random_guess, everything, shots, seed) for seed in seeds}
        true_best, found_by = _tickers(everything.best, data), "Brute force (every portfolio of the full list)"
        methods.append(Method("Brute force", true_best, brute_seconds, "full"))
        discrete = discrete_frontier(everything)
    else:
        guessed = {seed: _timed(random_guess_sampled, data, settings, shots, seed) for seed in seeds}
        candidates: dict[MethodName, np.ndarray] = {
            "Simulated annealing": min((chosen for (chosen, _), _ in annealed.values()), key=by_score),
            "Relaxation + rounding": relaxed.chosen,
            "Random guessing": min((chosen for (chosen, _), _ in guessed.values()), key=by_score),
        }
        winner = min(candidates, key=lambda name: by_score(candidates[name]))
        true_best = _tickers(candidates[winner], data)
        found_by = f"{winner} (best known; too many portfolios to check them all)"
        discrete = []

    def hit_rate(runs: dict) -> float:
        return sum(set(_tickers(chosen, data)) == set(true_best) for (chosen, _), _ in runs.values()) / len(runs)

    first = settings.seed
    methods += [
        Method(
            "Simulated annealing", _tickers(annealed[first][0][0], data), annealed[first][1], "full", hit_rate(annealed)
        ),
        Method("Relaxation + rounding", _tickers(relaxed.chosen, data), relax_seconds, "full"),
        Method("Random guessing", _tickers(guessed[first][0][0], data), guessed[first][1], "full", hit_rate(guessed)),
    ]
    return Classical(
        methods=methods,
        true_best=true_best,
        best_is_exact=exact,
        best_found_by=found_by,
        num_valid=count_legal(data.sectors, settings.k, settings.sector_cap),
        shortlist_best=[shortlist[i] for i in on_shortlist.best],
        num_valid_shortlist=len(on_shortlist.scores),
        relaxation_lower_bound=relaxed.lower_bound,
        continuous_frontier=continuous_frontier(data, settings),
        discrete_frontier=discrete,
    )


def describe(tickers: list[str], data: MarketData, settings: Settings) -> dict:
    """Score, return and volatility of a portfolio given by ticker names."""
    x = np.array([t in tickers for t in data.tickers], dtype=int)
    expected_return, risk = portfolio_stats(x, data)
    return {"stocks": tickers, "score": score(x, data, settings), "expected_return": expected_return, "risk": risk}


def _scorer(data: MarketData, settings: Settings) -> Callable[[np.ndarray], float]:
    def by_score(chosen: np.ndarray) -> float:
        x = np.zeros(len(data.tickers), dtype=int)
        x[np.asarray(chosen, dtype=int)] = 1
        return score(x, data, settings)

    return by_score


def _timed(function: Callable[..., Any], *args: Any) -> tuple[Any, float]:
    started = time.perf_counter()
    result = function(*args)
    return result, time.perf_counter() - started


def _tickers(chosen: np.ndarray, data: MarketData) -> list[str]:
    return [data.tickers[int(i)] for i in sorted(chosen)]
