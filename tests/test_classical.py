"""Classical baselines: they must agree with the shared score and the engine's brute-force reference."""

import numpy as np
import pytest

from qapital import Settings, is_valid, score
from qapital.classical.annealing import simulated_annealing
from qapital.classical.frontier import continuous_frontier, discrete_frontier
from qapital.classical.random_guess import random_guess
from qapital.classical.relaxation import relax_and_round
from qapital.classical.report import run_classical
from qapital.core.metrics import brute_force
from qapital.core.portfolios import count_legal, every_portfolio, sample_legal
from qapital.core.problem import score_many
from qapital.data.toy import random_market, toy

SECTORS = ["A", "A", "A", "B", "B", "C", "C", "D", "E", "F"]


def as_vector(chosen, n):
    x = np.zeros(n, dtype=int)
    x[list(chosen)] = 1
    return x


def test_score_many_is_score_for_each_portfolio():
    data, settings = random_market(SECTORS, seed=3), Settings(k=3, risk_aversion=0.7)
    rows = np.array([[0, 4, 7], [1, 2, 9], [3, 5, 6]])
    batch = score_many(rows, data, settings)
    single = [score(as_vector(row, len(SECTORS)), data, settings) for row in rows]
    assert batch == pytest.approx(single, abs=1e-12)


def test_toy_answer_is_unchanged():
    data, settings = toy(), Settings(k=2, sector_cap=1)
    best = every_portfolio(data, settings)
    assert sorted(data.tickers[i] for i in best.best) == ["BANK2", "FMCG"]
    assert best.scores.min() == pytest.approx(-0.138)


@pytest.mark.parametrize("cap", [None, 1, 2])
def test_brute_force_matches_the_engine_reference(cap):
    data, settings = random_market(SECTORS, seed=1), Settings(k=4, sector_cap=cap)
    everything = every_portfolio(data, settings)
    reference = brute_force(data, settings)
    ours = {tuple(as_vector(row, len(SECTORS))): s for row, s in zip(everything.chosen, everything.scores, strict=True)}
    assert ours.keys() == reference.scores.keys()
    assert all(ours[x] == pytest.approx(reference.scores[x], abs=1e-12) for x in ours)
    assert all(is_valid(x, data, settings) for x in ours)
    assert everything.returns == pytest.approx(data.mu[everything.chosen].mean(axis=1))


def test_annealing_finds_a_legal_portfolio_and_repeats_with_the_same_seed():
    data, settings = random_market(SECTORS, seed=2), Settings(k=4, sector_cap=1)
    best = every_portfolio(data, settings).scores.min()
    found = [simulated_annealing(data, settings, seed) for seed in range(5)]
    assert all(is_valid(as_vector(chosen, len(SECTORS)), data, settings) for chosen, _ in found)
    assert all(s >= best - 1e-12 for _, s in found)
    assert sum(abs(s - best) < 1e-9 for _, s in found) >= 4
    assert np.array_equal(simulated_annealing(data, settings, 7)[0], simulated_annealing(data, settings, 7)[0])


def test_relaxation_gives_a_lower_bound_and_a_legal_rounding():
    data, settings = random_market(SECTORS, seed=4), Settings(k=4, sector_cap=1)
    relaxed = relax_and_round(data, settings)
    assert relaxed.lower_bound <= every_portfolio(data, settings).scores.min() + 1e-6
    assert is_valid(as_vector(relaxed.chosen, len(SECTORS)), data, settings)
    assert relaxed.amounts.sum() == pytest.approx(4, abs=1e-6)


def test_random_guessing_draws_legal_portfolios_reproducibly():
    data, settings = random_market(SECTORS, seed=5), Settings(k=3, sector_cap=1)
    everything = every_portfolio(data, settings)
    chosen, s = random_guess(everything, shots=50, seed=11)
    assert is_valid(as_vector(chosen, len(SECTORS)), data, settings) and s >= everything.scores.min()
    assert np.array_equal(chosen, random_guess(everything, shots=50, seed=11)[0])


def test_frontiers_rise_with_risk():
    data, settings = random_market(SECTORS, seed=6), Settings(k=3, sector_cap=1)
    for curve in (continuous_frontier(data, settings, points=8), discrete_frontier(every_portfolio(data, settings))):
        risks, returns = zip(*curve, strict=True)
        assert list(risks) == sorted(risks) and list(returns) == sorted(returns)
    discrete = discrete_frontier(every_portfolio(data, settings))
    continuous = continuous_frontier(data, settings, points=8)
    assert continuous[0][0] <= discrete[0][0] + 1e-6  # fractional amounts can always be at least as safe
    assert continuous[-1][1] >= discrete[-1][1] - 1e-6  # and reach at least the same return


def test_report_names_the_brute_force_best_as_the_true_best():
    data, settings = random_market(SECTORS, seed=7), Settings(k=3, sector_cap=1, seed=1)
    result = run_classical(data, settings, shortlist=data.tickers[:8], shots=64)
    best = every_portfolio(data, settings).best
    assert set(result.true_best) == {data.tickers[i] for i in best}
    assert [m.name for m in result.methods] == [
        "Brute force",
        "Simulated annealing",
        "Relaxation + rounding",
        "Random guessing",
    ]
    assert result.methods[0].chosen == result.true_best
    assert all(m.hit_rate is None or 0 <= m.hit_rate <= 1 for m in result.methods)
    assert set(result.shortlist_best) <= set(data.tickers[:8])


def test_impossible_sector_rule_gives_a_friendly_error():
    data, settings = random_market(["A", "A", "A", "B"], seed=0), Settings(k=3, sector_cap=1)
    with pytest.raises(ValueError, match="sector rule"):
        every_portfolio(data, settings)


@pytest.mark.parametrize("cap", [None, 1, 2])
def test_counting_legal_portfolios_matches_listing_them(cap):
    data = random_market(SECTORS, seed=1)
    assert count_legal(data.sectors, 4, cap) == len(every_portfolio(data, Settings(k=4, sector_cap=cap)).scores)


def test_sampling_legal_portfolios_is_uniform_and_legal():
    data, settings = random_market(SECTORS, seed=1), Settings(k=4, sector_cap=1)
    draws = sample_legal(data, settings, np.random.default_rng(0), 30_000)
    assert all(is_valid(as_vector(row, len(SECTORS)), data, settings) for row in draws[:500])
    _, frequency = np.unique(draws, axis=0, return_counts=True)
    expected = len(draws) / count_legal(data.sectors, 4, 1)
    assert len(frequency) == count_legal(data.sectors, 4, 1)  # every legal portfolio shows up
    assert np.abs(frequency - expected).max() < 6 * np.sqrt(expected)  # and none far from its fair share


def test_lists_too_long_to_check_report_the_best_known(monkeypatch):
    # Between the shortlist (56 ways) and the full list (120 ways), so only the full list takes the large-list path.
    monkeypatch.setattr("qapital.core.portfolios.MAX_PORTFOLIOS", 60)
    data, settings = random_market(SECTORS, seed=7), Settings(k=3, sector_cap=1, seed=1)
    result = run_classical(data, settings, shortlist=data.tickers[:8], shots=256)
    assert not result.best_is_exact and "best known" in result.best_found_by
    assert [m.name for m in result.methods] == ["Simulated annealing", "Relaxation + rounding", "Random guessing"]
    assert result.discrete_frontier == [] and result.num_valid == count_legal(data.sectors, 3, 1)
    monkeypatch.undo()
    proven = every_portfolio(data, settings).best
    assert set(result.true_best) == {data.tickers[i] for i in proven}  # on a small market, the best known is the best
