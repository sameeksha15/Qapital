"""Grading samples against brute force (spec §7.4).

Every portfolio is scored with qapital.core.problem.score on the full, unpruned problem."""

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from qapital.core.portfolios import every_portfolio
from qapital.core.schemas import MarketData, Settings

Portfolio = tuple[int, ...]  # 0/1 per stock, in data.tickers order


@dataclass(frozen=True)
class Reference:
    scores: dict[Portfolio, float]  # every valid portfolio
    best: frozenset[Portfolio]  # valid portfolios that share the best score
    best_score: float
    worst_score: float


@dataclass(frozen=True)
class Quality:
    p_optimal: float
    feasible_rate: float
    lift_over_random: float
    approx_ratio: float


def brute_force(data: MarketData, settings: Settings) -> Reference:
    everything = every_portfolio(data, settings)
    vectors = np.zeros((len(everything.scores), len(data.tickers)), dtype=int)
    vectors[np.arange(len(vectors))[:, None], everything.chosen] = 1
    scores: dict[Portfolio, float] = dict(zip(map(tuple, vectors.tolist()), everything.scores.tolist(), strict=True))
    best_score, worst_score = min(scores.values()), max(scores.values())
    best = frozenset(x for x, s in scores.items() if math.isclose(s, best_score, abs_tol=1e-12))
    return Reference(scores, best, best_score, worst_score)


def grade(counts: Mapping[Portfolio, float], reference: Reference) -> Quality:
    """`counts`: shots per portfolio, or chances (any non-negative weights)."""
    shots = sum(counts.values())
    spread = reference.worst_score - reference.best_score

    def closeness(x: Portfolio) -> float:
        if x not in reference.scores:
            return 0.0
        return 1.0 if spread == 0 else (reference.worst_score - reference.scores[x]) / spread

    p_optimal = sum(count for x, count in counts.items() if x in reference.best) / shots
    return Quality(
        p_optimal=p_optimal,
        feasible_rate=sum(count for x, count in counts.items() if x in reference.scores) / shots,
        lift_over_random=p_optimal * len(reference.scores) / len(reference.best),
        approx_ratio=sum(count * closeness(x) for x, count in counts.items()) / shots,
    )
