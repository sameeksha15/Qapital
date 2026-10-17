import numpy as np
import pytest

from qapital.core.schemas import MarketData, Settings
from qapital.data.toy import NIFTY_LIKE_SECTORS as NIFTY_LIKE
from qapital.data.toy import random_market
from qapital.quantum.hamiltonian import count_qubits
from qapital.quantum.shortlist import fit_to_simulator, shortlist

Q = 1.0


def merit(data, i):
    return data.mu[i] - Q * data.sigma[i, i] - data.fees[i]


def test_every_sector_gets_its_best_stock_first():
    data = random_market(NIFTY_LIKE)
    small = shortlist(data, 16, Q)
    assert len(small.tickers) == 16 and set(small.sectors) == set(NIFTY_LIKE)
    for sector in set(NIFTY_LIKE):
        members = [i for i, s in enumerate(data.sectors) if s == sector]
        best = max(members, key=lambda i: merit(data, i))
        assert data.tickers[best] in small.tickers


def test_ranking_follows_the_risk_slider():
    # Shaped like MAXHEALTH vs SUNPHARMA in 2021–2024: almost the same return ÷ volatility,
    # but the first earns far more, so it wins unless the investor is very cautious.
    data = MarketData(
        ["HIGH", "STEADY", "OTHER"],
        ["Health", "Health", "IT"],
        np.array([0.53, 0.31, 0.1]),
        np.diag([0.37**2, 0.21**2, 0.04]),
        np.zeros(3),
    )
    assert "HIGH" in shortlist(data, 2, 1.0).tickers
    assert "STEADY" in shortlist(data, 2, 10.0).tickers


def test_leftover_slots_follow_sector_size():
    small = shortlist(random_market(NIFTY_LIKE), 16, Q)
    assert small.sectors.count("Fin") == max(small.sectors.count(s) for s in set(small.sectors))


def test_more_sectors_than_slots_keeps_the_sectors_with_the_best_stocks():
    data = random_market(NIFTY_LIKE, seed=4)
    small = shortlist(data, 5, Q)
    best_per_sector = {}
    for i, sector in enumerate(data.sectors):
        best_per_sector[sector] = max(best_per_sector.get(sector, -np.inf), merit(data, i))
    assert sorted(set(small.sectors)) == sorted(sorted(best_per_sector, key=best_per_sector.get)[-5:])


def test_shortlist_keeps_rows_and_columns_together():
    data = random_market(NIFTY_LIKE, seed=5)
    small = shortlist(data, 10, Q)
    kept = [data.tickers.index(t) for t in small.tickers]
    assert kept == sorted(kept)
    assert np.array_equal(small.sigma, data.sigma[np.ix_(kept, kept)])
    assert np.array_equal(small.mu, data.mu[kept]) and np.array_equal(small.fees, data.fees[kept])


def test_lists_that_fit_are_left_alone():
    data = random_market(["A", "B"] * 4)
    assert fit_to_simulator(data, Settings(k=4), 16) == (data, None)


@pytest.mark.parametrize("cap", [None, 1, 2, 3])
def test_long_lists_are_shortlisted_to_fit_including_slack_qubits(cap):
    data, settings = random_market(NIFTY_LIKE), Settings(k=10, sector_cap=cap)
    small, names = fit_to_simulator(data, settings, 16)
    assert names == small.tickers
    assert count_qubits(small.sectors, settings) <= 16
    assert count_qubits(shortlist(data, len(names) + 1, Q).sectors, settings) > 16  # largest list that fits


def test_slack_qubits_alone_can_trigger_a_shortlist():
    data, settings = random_market(["A"] * 6 + ["B"] * 6 + ["C"] * 4), Settings(k=6, sector_cap=2)
    small, names = fit_to_simulator(data, settings, 16)
    assert len(names) < 16 and count_qubits(small.sectors, settings) <= 16


def test_friendly_errors():
    with pytest.raises(ValueError, match="fit on the simulator"):
        fit_to_simulator(random_market(NIFTY_LIKE), Settings(k=16), 16)
    with pytest.raises(ValueError, match="fewer stocks"):
        fit_to_simulator(random_market(["A", "B"]), Settings(k=2), 16)
    with pytest.raises(ValueError, match="sector cap"):
        fit_to_simulator(random_market(["A", "A", "A"]), Settings(k=2, sector_cap=1), 16)
