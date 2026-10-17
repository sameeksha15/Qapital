"""Fitting a stock list onto the simulator (spec §8).

When the problem needs more qubits than allowed, the list is shortlisted: every sector first gets
its best stock, then leftover slots are shared in proportion to sector size. "Best" means the highest
merit, return − q·variance − fee: the stock's own part of the score, so the ranking follows the risk slider."""

import numpy as np

from qapital.core.schemas import MarketData, Settings
from qapital.quantum.hamiltonian import count_qubits


def fit_to_simulator(data: MarketData, settings: Settings, max_qubits: int) -> tuple[MarketData, list[str] | None]:
    """The data to solve and the shortlist (None when every stock fits)."""
    check_can_choose(data.sectors, settings)
    if count_qubits(data.sectors, settings) <= max_qubits:
        return data, None
    sizes = range(min(len(data.tickers), max_qubits), 0, -1)
    smaller = next(
        s
        for s in (shortlist(data, size, settings.risk_aversion) for size in sizes)
        if count_qubits(s.sectors, settings) <= max_qubits
    )
    if settings.k >= len(smaller.tickers):
        raise ValueError(
            f"Only {len(smaller.tickers)} of your stocks fit on the simulator, "
            f"so choose fewer than {len(smaller.tickers)} stocks to buy."
        )
    check_can_choose(smaller.sectors, settings)
    return smaller, smaller.tickers


def check_can_choose(sectors: list[str], settings: Settings) -> None:
    if settings.k >= len(sectors):
        raise ValueError("Choose fewer stocks to buy than stocks in your list.")
    if settings.sector_cap is not None:
        room = sum(min(sectors.count(s), settings.sector_cap) for s in set(sectors))
        if room < settings.k:
            raise ValueError("The sector cap is too strict to pick that many stocks. Raise the cap or lower K.")


def shortlist(data: MarketData, size: int, risk_aversion: float) -> MarketData:
    merit = data.mu - risk_aversion * np.diag(data.sigma) - data.fees
    by_sector: dict[str, list[int]] = {}  # best stock first; sectors ordered by their best stock
    for i in sorted(range(len(data.tickers)), key=lambda i: -merit[i]):
        by_sector.setdefault(data.sectors[i], []).append(i)

    slots = {sector: 0 for sector in by_sector}
    for sector in list(by_sector)[:size]:
        slots[sector] = 1

    def fair_share_gap(sector: str) -> float:
        return len(by_sector[sector]) * size / len(data.tickers) - slots[sector]

    while sum(slots.values()) < size:
        open_sectors = [s for s in by_sector if slots[s] < len(by_sector[s])]
        slots[max(open_sectors, key=fair_share_gap)] += 1

    kept = sorted(i for sector, stocks in by_sector.items() for i in stocks[: slots[sector]])
    return MarketData(
        tickers=[data.tickers[i] for i in kept],
        sectors=[data.sectors[i] for i in kept],
        mu=data.mu[kept],
        sigma=data.sigma[np.ix_(kept, kept)],
        fees=data.fees[kept],
    )
