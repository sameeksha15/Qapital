"""QAOA circuits (spec §7.1).

Standard version: Hadamards on every qubit, RX mixer. XY version: Dicke state on the stock qubits and a ring XY
mixer, which keeps exactly K stocks. Warm-start version (Egger, Mareček & Woerner, Quantum 5, 479, 2021): each stock
qubit starts tilted to read 1 with chance cᵢ (the classical relaxed amount) and its mixer is rotated to match.
Slack qubits always use Hadamards and the RX mixer."""

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter, ParameterVector
from qiskit.circuit.library import XXPlusYYGate

from qapital.quantum.hamiltonian import Hamiltonian

WARM_EPSILON = 0.25  # starting chances are kept in [ε, 1 − ε] so no qubit starts frozen (as in the paper)


def warm_start_angles(amounts: np.ndarray, epsilon: float = WARM_EPSILON) -> np.ndarray:
    """RY angle that makes a qubit read 1 with chance cᵢ = the relaxed amount, kept in [ε, 1 − ε]."""
    return 2 * np.arcsin(np.sqrt(np.clip(amounts, epsilon, 1 - epsilon)))


def qaoa_circuit(
    ham: Hamiltonian, k: int, mixer: str, depth: int, warm_angles: np.ndarray | None = None
) -> tuple[QuantumCircuit, list[Parameter]]:
    """Returns the circuit and its parameters in the order γ1..γp, β1..βp. The "warm" mixer needs `warm_angles`."""
    if mixer == "warm" and (warm_angles is None or len(warm_angles) != ham.num_stocks):
        raise ValueError("A warm-start circuit needs one starting angle per stock.")
    angles = np.asarray(warm_angles if warm_angles is not None else [], dtype=float)
    gammas, betas = ParameterVector("gamma", depth), ParameterVector("beta", depth)
    xy, warm = mixer == "xy", mixer == "warm"
    stocks = list(range(ham.num_stocks))
    rx_qubits = list(range(ham.num_stocks, ham.num_qubits)) if xy or warm else list(range(ham.num_qubits))

    qc = QuantumCircuit(ham.num_qubits)
    if xy:
        qc.compose(dicke_state(ham.num_stocks, k), stocks, inplace=True)
    if warm:
        for qubit, angle in zip(stocks, angles, strict=True):
            qc.ry(float(angle), qubit)
    for qubit in rx_qubits:
        qc.h(qubit)

    for gamma, beta in zip(gammas, betas, strict=True):
        _cost_layer(qc, ham, gamma)
        if xy:
            for i, j in ring_pairs(stocks):
                qc.append(XXPlusYYGate(2 * beta), [i, j])
        if warm:
            for qubit, angle in zip(stocks, angles, strict=True):
                qc.ry(-float(angle), qubit)
                qc.rz(-2 * beta, qubit)
                qc.ry(float(angle), qubit)
        for qubit in rx_qubits:
            qc.rx(2 * beta, qubit)
    return qc, [*gammas, *betas]


def beta_period(mixer: str) -> float:
    """RX(2β) and the warm mixer's RZ(2β) repeat every π in β (up to a global phase); the XY gate every 2π."""
    return 2 * np.pi if mixer == "xy" else np.pi


def ring_pairs(qubits: list[int]) -> list[tuple[int, int]]:
    """Neighbours around a ring: pairs starting at even positions first, then odd ones,
    so the gates inside each group can run side by side."""
    n = len(qubits)
    if n < 3:
        return [(qubits[0], qubits[1])] if n == 2 else []
    starts = [*range(0, n, 2), *range(1, n, 2)]
    return [(qubits[i], qubits[(i + 1) % n]) for i in starts]


def dicke_state(num_qubits: int, k: int) -> QuantumCircuit:
    """Equal superposition of every bitstring with exactly k ones, with O(n·k) gates
    (Bärtschi & Eidenbenz, "Deterministic Preparation of Dicke States", 2019)."""
    if k > num_qubits - k:
        qc = dicke_state(num_qubits, num_qubits - k)
        qc.x(range(num_qubits))
        return qc
    qc = QuantumCircuit(num_qubits)
    for qubit in range(num_qubits - k, num_qubits):
        qc.x(qubit)
    for n in range(num_qubits, 1, -1):
        _split_and_cyclic_shift(qc, n, min(k, n - 1))
    return qc


def _split_and_cyclic_shift(qc: QuantumCircuit, n: int, k: int) -> None:
    """The paper's SCS(n, k), acting on qubits n-k-1 … n-1."""
    top = n - 1
    qc.cx(top - 1, top)
    qc.cry(2 * np.arccos(np.sqrt(1 / n)), top, top - 1)
    qc.cx(top - 1, top)
    for step in range(2, k + 1):
        qc.cx(top - step, top)
        _doubly_controlled_ry(qc, 2 * np.arccos(np.sqrt(step / n)), top, top - step + 1, top - step)
        qc.cx(top - step, top)


def _doubly_controlled_ry(qc: QuantumCircuit, theta: float, control1: int, control2: int, target: int) -> None:
    """RY(θ) on the target when both controls are 1, with 4 CNOTs: each CNOT flips the sign of
    the following rotations, and the four ±θ/4 turns only add up when both controls are 1."""
    for angle, control in (
        (theta / 4, control1),
        (-theta / 4, control2),
        (theta / 4, control1),
        (-theta / 4, control2),
    ):
        qc.ry(angle, target)
        qc.cx(control, target)


def _cost_layer(qc: QuantumCircuit, ham: Hamiltonian, gamma: Parameter) -> None:
    """exp(−iγH): RZ(2γh_i) on each qubit and RZZ(2γJ_ij) on each coupled pair."""
    for i, h in enumerate(ham.h):
        if h:
            qc.rz(2 * gamma * float(h), i)
    for i, j in zip(*np.nonzero(ham.J), strict=True):
        qc.rzz(2 * gamma * float(ham.J[i, j]), int(i), int(j))
