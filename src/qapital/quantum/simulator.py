"""Ideal (noise-free) runs on Qiskit Aer's statevector simulator."""

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Parameter
from qiskit_aer import AerSimulator

_AER = AerSimulator(method="statevector")


class IdealSimulator:
    """Compiles a parameterised circuit once, then runs it for any parameter values.
    Optimisation level 0 only translates gates, and it is the level that compiles the same way every time."""

    def __init__(self, circuit: QuantumCircuit, params: list[Parameter]):
        self._params = params
        with_probabilities = circuit.copy()
        with_probabilities.save_probabilities()
        self._probability_circuit = transpile(with_probabilities, _AER, optimization_level=0)
        self._sampling_circuit = transpile(circuit.measure_all(inplace=False), _AER, optimization_level=0)

    def probabilities(self, theta: np.ndarray) -> np.ndarray:
        """Exact probability of every basis state; index b = basis state b (qubit i is bit i)."""
        result = _AER.run(self._bind(self._probability_circuit, theta)).result()
        return np.asarray(result.data()["probabilities"])

    def sample(self, theta: np.ndarray, shots: int, seed: int) -> dict[str, int]:
        """Measured bitstrings and their counts. Qiskit bitstrings put qubit 0 last."""
        result = _AER.run(self._bind(self._sampling_circuit, theta), shots=shots, seed_simulator=seed).result()
        return result.get_counts()

    def _bind(self, circuit: QuantumCircuit, theta: np.ndarray) -> QuantumCircuit:
        return circuit.assign_parameters(dict(zip(self._params, theta, strict=True)), strict=True)
