"""Simulated annealing over legal portfolios (spec §8).

Start from a random legal portfolio; a move swaps one chosen stock for one unchosen stock, so the count stays K, and
moves that break the sector rule are skipped. A worse move is accepted with probability exp(−Δ/T). The starting
temperature is the spread of scores of random legal portfolios, cooled geometrically to 0.1% of it;
best of 5 restarts."""

import numpy as np

from qapital.core.problem import score_many
from qapital.core.schemas import MarketData, Settings

STEPS = 3000
RESTARTS = 5
TEMPERATURE_SAMPLES = 200
COOLING_TO = 0.001


def simulated_annealing(data: MarketData, settings: Settings, seed: int) -> tuple[np.ndarray, float]:
    """Best portfolio found (ascending stock indices) and its score."""
    rng = np.random.default_rng(seed)
    samples = np.array([random_legal(data, settings, rng) for _ in range(TEMPERATURE_SAMPLES)])
    start_temperature = float(np.std(score_many(samples, data, settings))) or 1e-9
    temperatures = start_temperature * COOLING_TO ** (np.arange(STEPS) / (STEPS - 1))

    best, best_score = np.array([], dtype=int), np.inf
    for _ in range(RESTARTS):
        current = random_legal(data, settings, rng)
        current_score = _score(current, data, settings)
        if current_score < best_score:
            best, best_score = np.sort(current), current_score
        for temperature in temperatures:
            candidate = _swap(current, len(data.tickers), rng)
            if not _within_cap(candidate, data, settings):
                continue
            candidate_score = _score(candidate, data, settings)
            change = candidate_score - current_score
            if change <= 0 or rng.random() < np.exp(-change / temperature):
                current, current_score = candidate, candidate_score
                if current_score < best_score:
                    best, best_score = np.sort(current), current_score
    return best, float(best_score)


def random_legal(data: MarketData, settings: Settings, rng: np.random.Generator) -> np.ndarray:
    """A uniformly shuffled legal portfolio: take stocks in random order, skipping those whose sector is full."""
    chosen: list[int] = []
    per_sector: dict[str, int] = {}
    for i in rng.permutation(len(data.tickers)):
        sector = data.sectors[i]
        if settings.sector_cap is None or per_sector.get(sector, 0) < settings.sector_cap:
            chosen.append(int(i))
            per_sector[sector] = per_sector.get(sector, 0) + 1
            if len(chosen) == settings.k:
                return np.array(chosen)
    raise ValueError("No portfolio follows the sector rule. Allow more stocks per sector or buy fewer stocks.")


def _swap(chosen: np.ndarray, num_stocks: int, rng: np.random.Generator) -> np.ndarray:
    unchosen = np.setdiff1d(np.arange(num_stocks), chosen)
    swapped = chosen.copy()
    swapped[rng.integers(len(chosen))] = unchosen[rng.integers(len(unchosen))]
    return swapped


def _within_cap(chosen: np.ndarray, data: MarketData, settings: Settings) -> bool:
    if settings.sector_cap is None:
        return True
    _, counts = np.unique([data.sectors[i] for i in chosen], return_counts=True)
    return bool(counts.max() <= settings.sector_cap)


def _score(chosen: np.ndarray, data: MarketData, settings: Settings) -> float:
    return float(score_many(chosen[None, :], data, settings)[0])
