from math import comb

import numpy as np
import pytest

from qapital.core.metrics import brute_force
from qapital.core.problem import score
from qapital.core.schemas import MarketData, Settings
from qapital.data.toy import random_market, toy
from qapital.quantum.hamiltonian import (
    basis_bits,
    build_hamiltonian,
    count_qubits,
    kept_pairs,
    penalty_for,
    sector_rules,
)

SECTORS = ["A", "A", "A", "B", "B", "C"]


def expected_energy(bits, data, settings, penalty):
    """Score plus λ × every broken rule, written out directly from the spec."""
    n = len(data.tickers)
    x = bits[:n]
    energy = score(x, data, settings)
    if settings.mixer == "standard":
        energy += penalty * (x.sum() - settings.k) ** 2
    for rule in sector_rules(data.sectors, settings):
        chosen = x[list(rule.stocks)].sum()
        if rule.cap == 1:
            energy += penalty * comb(chosen, 2)
        else:
            slack_value = sum(bits[qubit] << b for b, qubit in enumerate(rule.slack))
            energy += penalty * (chosen + slack_value - rule.cap) ** 2
    return energy


@pytest.mark.parametrize("mixer", ["standard", "xy"])
@pytest.mark.parametrize("cap", [None, 1, 2])
def test_energy_of_every_basis_state_is_score_plus_penalties(mixer, cap):
    data, settings = random_market(SECTORS), Settings(k=3, sector_cap=cap, mixer=mixer)
    ham = build_hamiltonian(data, settings)
    expected = [expected_energy(bits, data, settings, ham.penalty) for bits in basis_bits(ham.num_qubits)]
    assert np.allclose(ham.energies, expected)


@pytest.mark.parametrize("mixer", ["standard", "xy"])
@pytest.mark.parametrize("cap", [1, 2])
def test_lowest_energy_the_circuit_can_reach_is_the_best_valid_portfolio(mixer, cap):
    data, settings = random_market(SECTORS, seed=3), Settings(k=3, sector_cap=cap, mixer=mixer)
    ham = build_hamiltonian(data, settings)
    bits = basis_bits(ham.num_qubits)
    reachable = bits[:, :6].sum(axis=1) == 3 if mixer == "xy" else np.ones(len(bits), dtype=bool)
    lowest = np.flatnonzero(reachable)[np.argmin(ham.energies[reachable])]
    reference = brute_force(data, settings)
    assert tuple(int(b) for b in bits[lowest, :6]) in reference.best
    assert ham.energies[lowest] == pytest.approx(reference.best_score)


@pytest.mark.parametrize("mixer", ["standard", "xy"])
def test_ising_coefficients_reproduce_the_energies(mixer):
    data, settings = random_market(SECTORS, seed=1), Settings(k=3, sector_cap=2, mixer=mixer)
    ham = build_hamiltonian(data, settings)
    z = 1 - 2 * basis_bits(ham.num_qubits)
    ising = z @ ham.h + np.einsum("bi,ij,bj->b", z, ham.J, z)
    assert np.ptp(ham.energies - ham.scale * ising) < 1e-9  # equal up to a constant
    assert max(np.abs(ham.h).max(), np.abs(ham.J).max()) == pytest.approx(1.0)


def test_calibrated_penalty_puts_the_best_rule_breaker_halfway():
    data, settings = toy(), Settings(k=2, sector_cap=1, mixer="standard")
    ham = build_hamiltonian(data, settings)
    scores = np.array([expected_energy(bits, data, settings, 0) for bits in basis_bits(4)])
    rule_breaking = ~np.isclose(ham.energies, scores)
    reference = brute_force(data, settings)
    target = (reference.best_score + np.mean(list(reference.scores.values()))) / 2
    assert ham.energies[rule_breaking].min() == pytest.approx(target, abs=1e-9)


def test_tied_portfolios_still_get_a_positive_margin():
    n = 4
    data = MarketData(["W", "X", "Y", "Z"], ["A", "B", "C", "D"], np.full(n, 0.1), np.eye(n) * 0.04, np.zeros(n))
    ham = build_hamiltonian(data, Settings(k=2, mixer="standard"))
    bits = basis_bits(n)
    two_stocks = bits.sum(axis=1) == 2
    assert ham.energies[~two_stocks].min() > ham.energies[two_stocks].max()


def test_no_rule_breakers_means_no_penalty():
    assert build_hamiltonian(random_market(SECTORS), Settings(k=3, mixer="xy")).penalty == 0
    allowed = np.ones(4, dtype=bool)
    assert penalty_for(np.zeros(4), np.zeros(4), allowed, target=1.0) == 0


def test_penalty_found_by_bisection_reaches_the_target():
    score_energy, rule_energy = np.array([0.0, -5.0, -3.0]), np.array([0.0, 2.0, 1.0])
    penalty = penalty_for(score_energy, rule_energy, np.ones(3, dtype=bool), target=1.0)
    assert min(-5 + 2 * penalty, -3 + penalty) == pytest.approx(1.0)


def test_sector_rules_and_slack_qubits():
    assert sector_rules(SECTORS, Settings(k=3)) == []
    assert sector_rules(SECTORS, Settings(k=3, sector_cap=3)) == []  # cap ≥ K: can never break
    cap_one = sector_rules(SECTORS, Settings(k=3, sector_cap=1))
    assert [(r.stocks, r.slack) for r in cap_one] == [((0, 1, 2), ()), ((3, 4), ())]
    cap_two = sector_rules(SECTORS, Settings(k=3, sector_cap=2))
    assert [(r.stocks, r.slack) for r in cap_two] == [((0, 1, 2), (6, 7))]
    assert count_qubits(SECTORS, Settings(k=3, sector_cap=2)) == 8
    assert count_qubits(["A"] * 6, Settings(k=5, sector_cap=4)) == 6 + 3  # cap 4 needs 3 bits


def test_pruning_keeps_the_strongest_pairs_and_only_saves_couplings_with_xy():
    data = random_market(["A", "B", "C", "D", "E", "F", "G", "H"], seed=2)
    kept = kept_pairs(data.sigma, 0.5)
    strengths = sorted((abs(data.sigma[i, j]) for i in range(8) for j in range(i + 1, 8)), reverse=True)
    assert len(kept) == 14
    assert sorted((abs(data.sigma[p]) for p in kept), reverse=True) == strengths[:14]

    def couplings(mixer):
        return np.count_nonzero(build_hamiltonian(data, Settings(k=4, mixer=mixer, pairs_kept=0.5)).J)

    assert couplings("standard") == 28
    assert couplings("xy") == 14
