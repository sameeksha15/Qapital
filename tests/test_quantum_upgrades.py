"""Phase 3 engine upgrades: CVaR-QAOA, warm-start QAOA and readout-error mitigation."""

import itertools

import numpy as np
import pytest
from pydantic import ValidationError

from qapital import Settings, solve
from qapital.classical.relaxation import relax_and_round
from qapital.core.metrics import brute_force
from qapital.data.toy import random_market, toy
from qapital.quantum.circuits import WARM_EPSILON, qaoa_circuit, warm_start_angles
from qapital.quantum.hamiltonian import build_hamiltonian
from qapital.quantum.noise import ReadoutCalibration, mitigate_readout
from qapital.quantum.simulator import IdealSimulator
from qapital.quantum.solver import _energy, circuit_builder


@pytest.fixture
def toy_xy():
    data = toy()
    settings = Settings(k=2, sector_cap=1, depth=1)
    ham = build_hamiltonian(data, settings)
    return data, ham, circuit_builder(data, ham, settings)


def test_cvar_is_never_above_the_average_and_tends_to_the_best_outcome(toy_xy):
    _, ham, build = toy_xy
    theta = np.array([0.7, 0.4])
    average = _energy(build, ham, Settings(k=2, cvar_alpha=1.0, depth=1), 1)(theta)
    probabilities = IdealSimulator(*build(1)).probabilities(theta)
    assert average == pytest.approx(probabilities @ ham.energies)
    values = [_energy(build, ham, Settings(k=2, cvar_alpha=a, depth=1), 1)(theta) for a in (0.5, 0.1, 1e-6)]
    assert values[0] <= average + 1e-12 and values[1] <= values[0] + 1e-12
    reachable = ham.energies[probabilities > 1e-9]
    assert values[2] == pytest.approx(reachable.min(), abs=1e-6)


def test_cvar_run_still_finds_the_toy_answer():
    result = solve(toy(), Settings(k=2, sector_cap=1, depth=1, cvar_alpha=0.25))
    assert sorted(result.chosen) == ["BANK2", "FMCG"] and result.score == pytest.approx(-0.138)
    assert result.warm_start_alone is None


@pytest.mark.parametrize("alpha", [0.0, -0.1, 1.5])
def test_bad_cvar_alpha_is_rejected(alpha):
    with pytest.raises(ValidationError):
        Settings(k=2, cvar_alpha=alpha)


def test_warm_start_state_reads_one_with_the_relaxed_chances():
    data = random_market(["A", "A", "B", "B", "C"], seed=4)
    settings = Settings(k=2, sector_cap=1, mixer="warm")
    ham = build_hamiltonian(data, settings)
    amounts = relax_and_round(data, settings).amounts
    circuit, params = qaoa_circuit(ham, 2, "warm", 0, warm_start_angles(amounts))
    probabilities = IdealSimulator(circuit, params).probabilities(np.array([]))
    states = np.arange(len(probabilities))
    reads_one = [probabilities[(states >> q) & 1 == 1].sum() for q in range(ham.num_stocks)]
    assert reads_one == pytest.approx(np.clip(amounts, WARM_EPSILON, 1 - WARM_EPSILON))
    with pytest.raises(ValueError, match="starting angle per stock"):
        qaoa_circuit(ham, 2, "warm", 1)


def test_warm_start_needs_the_count_fine_like_the_penalty_circuit():
    data = toy()
    warm = build_hamiltonian(data, Settings(k=2, sector_cap=1, mixer="warm"))
    penalty = build_hamiltonian(data, Settings(k=2, sector_cap=1, mixer="standard"))
    assert warm.energies == pytest.approx(penalty.energies)


def test_warm_start_run_reports_what_the_start_alone_gives():
    settings = Settings(k=2, sector_cap=1, depth=2, mixer="warm")
    result = solve(toy(), settings)
    assert sorted(result.chosen) == ["BANK2", "FMCG"]
    alone = result.warm_start_alone
    assert alone is not None and 0 <= alone.p_optimal <= alone.feasible_rate <= 1
    assert alone.p_optimal == pytest.approx(result.layer_probs[0][0])  # layer 0 is the starting state
    reference = brute_force(toy(), settings)
    assert alone.lift_over_random == pytest.approx(alone.p_optimal * len(reference.scores) / len(reference.best))


def test_readout_mitigation_undoes_a_known_misreading():
    n = 3
    rng = np.random.default_rng(0)
    truth = rng.dirichlet(np.ones(2**n))
    e01, e10 = np.array([0.02, 0.05, 0.01]), np.array([0.03, 0.01, 0.04])
    measured = truth.reshape((2,) * n)
    for q in range(n):
        table = np.array([[1 - e01[q], e10[q]], [e01[q], 1 - e10[q]]])
        axis = n - 1 - q
        measured = np.moveaxis(np.tensordot(table, measured, axes=([1], [axis])), 0, axis)
    counts = {format(s, f"0{n}b"): round(p * 10**8) for s, p in enumerate(measured.reshape(-1))}
    fixed = mitigate_readout(counts, ReadoutCalibration(e01, e10), n)
    recovered = np.array([fixed.get(format(s, f"0{n}b"), 0.0) for s in range(2**n)])
    assert recovered == pytest.approx(truth, abs=1e-6)
    assert ReadoutCalibration(e01, e10).average == pytest.approx(np.mean([*e01, *e10]))


def test_noisy_run_reports_mitigated_results_by_default():
    result = solve(toy(), Settings(k=2, sector_cap=1, depth=1, noisy=True))
    noise = result.noise
    assert noise.readout_error is not None and 0 < noise.readout_error < 0.1
    mitigated = [noise.mitigated_p_optimal, noise.mitigated_feasible_rate, noise.mitigated_postselected_p_optimal]
    assert all(value is not None and 0 <= value <= 1 for value in mitigated)
    off = solve(toy(), Settings(k=2, sector_cap=1, depth=1, noisy=True, mitigate_readout=False)).noise
    assert off.mitigated_p_optimal is None and off.noisy_p_optimal == noise.noisy_p_optimal


def test_every_mixer_and_objective_combination_runs():
    data = random_market(["A", "A", "B", "B", "C", "D"], seed=8)
    for mixer, alpha in itertools.product(["standard", "xy", "warm"], [1.0, 0.25]):
        result = solve(data, Settings(k=3, sector_cap=1, depth=1, mixer=mixer, cvar_alpha=alpha))
        assert len(result.chosen) == 3 and (result.warm_start_alone is not None) == (mixer == "warm")
