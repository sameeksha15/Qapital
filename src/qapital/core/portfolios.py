"""Every legal portfolio of a list, scored with the shared score (brute force).

The one enumeration in the project: it is the grading reference for the quantum engine, the brute-force baseline,
the pool random guessing draws from, and the source of the discrete frontier."""

import itertools
import math
from dataclasses import dataclass

import numpy as np

from qapital.core.problem import score_many
from qapital.core.schemas import MarketData, Settings

MAX_PORTFOLIOS = 2_000_000  # ways to pick K; above this, checking one by one is too slow for a web request
CHUNK = 200_000


@dataclass(frozen=True)
class AllPortfolios:
    """Every legal portfolio. Row i of `chosen` holds the (ascending) stock indices of portfolio i."""

    chosen: np.ndarray  # (m, k) int
    scores: np.ndarray  # (m,) shared score, lower is better
    returns: np.ndarray  # (m,) yearly return, equal money in each stock
    risks: np.ndarray  # (m,) yearly volatility, equal money in each stock

    @property
    def best(self) -> np.ndarray:
        return self.chosen[int(np.argmin(self.scores))]


def can_brute_force(num_stocks: int, k: int) -> bool:
    return math.comb(num_stocks, k) <= MAX_PORTFOLIOS


def every_portfolio(data: MarketData, settings: Settings) -> AllPortfolios:
    n, k = len(data.tickers), settings.k
    if not can_brute_force(n, k):
        raise ValueError(
            f"{math.comb(n, k):,} ways to pick {k} of {n} stocks are too many to check one by one. "
            "Pick fewer stocks or fewer to buy."
        )
    _, sector_codes = np.unique(data.sectors, return_inverse=True)
    combinations = itertools.combinations(range(n), k)
    parts = []
    while block := list(itertools.islice(combinations, CHUNK)):
        chosen = np.array(block, dtype=int).reshape(-1, k)
        chosen = chosen[_within_sector_cap(sector_codes[chosen], settings.sector_cap)]
        if len(chosen):
            parts.append(chosen)
    if not parts:
        raise ValueError("No portfolio follows the sector rule. Allow more stocks per sector or buy fewer stocks.")
    chosen = np.concatenate(parts)
    scores = score_many(chosen, data, settings)
    quadratic = data.sigma[chosen[:, :, None], chosen[:, None, :]].sum(axis=(1, 2))
    return AllPortfolios(
        chosen=chosen,
        scores=scores,
        returns=data.mu[chosen].sum(axis=1) / k,
        risks=np.sqrt(np.maximum(quadratic, 0)) / k,
    )


def _within_sector_cap(codes: np.ndarray, cap: int | None) -> np.ndarray:
    """Which rows (sector codes of each portfolio's stocks) hold at most `cap` stocks of any one sector."""
    if cap is None:
        return np.ones(len(codes), dtype=bool)
    ordered = np.sort(codes, axis=1)
    if cap == 1:
        return np.all(ordered[:, 1:] != ordered[:, :-1], axis=1)
    return np.all([(codes == sector).sum(axis=1) <= cap for sector in np.unique(codes)], axis=0)


def count_legal(sectors: list[str], k: int, cap: int | None) -> int:
    """How many legal portfolios exist (exact, without listing them): choose k stocks, at most `cap` per sector."""
    return _ways(_sector_sizes(sectors), k, cap)[-1][k]


def sample_legal(data: MarketData, settings: Settings, rng: np.random.Generator, size: int) -> np.ndarray:
    """`size` legal portfolios drawn uniformly at random (with replacement), without listing them all: pick how many
    stocks each sector gives, in proportion to the number of portfolios with that split, then which ones."""
    sizes = _sector_sizes(data.sectors)
    ways = _ways(sizes, settings.k, settings.sector_cap)
    if ways[-1][settings.k] == 0:
        raise ValueError("No portfolio follows the sector rule. Allow more stocks per sector or buy fewer stocks.")
    members = {sector: [i for i, s in enumerate(data.sectors) if s == sector] for sector in sizes}
    names = list(sizes)
    draws = np.empty((size, settings.k), dtype=int)
    for row in range(size):
        remaining, chosen = settings.k, []
        for position in range(len(names) - 1, -1, -1):
            sector = names[position]
            limit = min(sizes[sector], remaining, settings.sector_cap or remaining)
            weights = [math.comb(sizes[sector], c) * ways[position][remaining - c] for c in range(limit + 1)]
            pick = rng.random() * sum(weights)
            take = next(c for c, w in enumerate(itertools.accumulate(weights)) if pick < w)
            chosen += list(rng.choice(members[sector], size=take, replace=False))
            remaining -= take
        draws[row] = np.sort(chosen)
    return draws


def _sector_sizes(sectors: list[str]) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for sector in sectors:
        sizes[sector] = sizes.get(sector, 0) + 1
    return sizes


def _ways(sizes: dict[str, int], k: int, cap: int | None) -> list[list[int]]:
    """ways[s][j]: portfolios of j stocks from the first s sectors (exact integers, so no overflow)."""
    ways = [[1] + [0] * k]
    for size in sizes.values():
        previous = ways[-1]
        limit = min(size, cap if cap is not None else size)
        ways.append([sum(math.comb(size, c) * previous[j - c] for c in range(min(limit, j) + 1)) for j in range(k + 1)])
    return ways
