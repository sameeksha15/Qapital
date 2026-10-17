"""Random guessing: as many tries as the quantum circuit's shots, drawn uniformly from the legal portfolios."""

import numpy as np

from qapital.core.portfolios import AllPortfolios, sample_legal
from qapital.core.problem import score_many
from qapital.core.schemas import MarketData, Settings


def random_guess(portfolios: AllPortfolios, shots: int, seed: int) -> tuple[np.ndarray, float]:
    """Best of `shots` uniform draws (with replacement) from every legal portfolio, and its score."""
    draws = np.random.default_rng(seed).integers(len(portfolios.scores), size=shots)
    best = draws[int(np.argmin(portfolios.scores[draws]))]
    return portfolios.chosen[best], float(portfolios.scores[best])


def random_guess_sampled(data: MarketData, settings: Settings, shots: int, seed: int) -> tuple[np.ndarray, float]:
    """The same blind guessing for lists too long to enumerate: uniform draws made by counting, not listing."""
    draws = sample_legal(data, settings, np.random.default_rng(seed), shots)
    scores = score_many(draws, data, settings)
    best = int(np.argmin(scores))
    return draws[best], float(scores[best])
