import numpy as np
import pytest
from qiskit.quantum_info import Statevector

from qapital.core.schemas import Settings
from qapital.data.toy import random_market
from qapital.quantum.circuits import beta_period, dicke_state, qaoa_circuit, ring_pairs
from qapital.quantum.hamiltonian import basis_bits, build_hamiltonian


@pytest.mark.parametrize("n", range(2, 8))
def test_dicke_state_is_the_equal_superposition_of_weight_k(n):
    weights = basis_bits(n).sum(axis=1)
    for k in range(1, n):
        expected = (weights == k) / np.sqrt(np.sum(weights == k))
        assert np.allclose(Statevector(dicke_state(n, k)).data, expected)


def test_ring_pairs():
    assert ring_pairs([0, 1]) == [(0, 1)]
    assert sorted(ring_pairs([0, 1, 2])) == [(0, 1), (1, 2), (2, 0)]
    pairs = ring_pairs(list(range(8)))
    assert sorted(pairs) == sorted((i, (i + 1) % 8) for i in range(8))
    for group in (pairs[:4], pairs[4:]):
        assert len({q for pair in group for q in pair}) == 8  # no shared qubit in a group


def bound(ham, settings, theta):
    circuit, params = qaoa_circuit(ham, settings.k, settings.mixer, len(theta) // 2)
    return Statevector(circuit.assign_parameters(dict(zip(params, theta, strict=True))))


@pytest.mark.parametrize("cap", [None, 2])
def test_xy_circuit_always_keeps_exactly_k_stocks(cap):
    data, settings = random_market(["A", "A", "A", "B", "B", "C"]), Settings(k=3, sector_cap=cap, mixer="xy")
    ham = build_hamiltonian(data, settings)
    probabilities = bound(ham, settings, np.random.default_rng(0).uniform(0, 3, 6)).probabilities()
    weight = basis_bits(ham.num_qubits)[:, :6].sum(axis=1)
    assert probabilities[weight != 3].sum() < 1e-12


def test_cost_layer_applies_exp_minus_i_gamma_h():
    data, settings = random_market(["A", "A", "B", "C"]), Settings(k=2, sector_cap=1, mixer="standard")
    ham = build_hamiltonian(data, settings)
    gamma = 0.37
    amplitudes = bound(ham, settings, [gamma, 0.0]).data  # β = 0: mixer does nothing
    expected = np.exp(-1j * gamma * ham.energies / ham.scale)
    assert np.allclose(amplitudes * np.conj(amplitudes[0]), expected * np.conj(expected[0]) / len(expected))


def test_beta_period():
    assert beta_period("standard") == pytest.approx(np.pi)
    assert beta_period("xy") == pytest.approx(2 * np.pi)
