"""Running a tuned circuit on a noisy copy of a real IBM chip, and grading what comes out (spec §7.5).

Train on ideal, test on noisy: the angles are tuned on the perfect simulator, and the noisy simulator only samples.
Post-selection keeps the shots that hold exactly K stocks. On the XY circuit every other count can only come from a
hardware error, so it is an error check built into the circuit. On the penalty circuit it is a plain filter.

Readout mitigation: two calibration circuits (all 0s, all 1s) on the same physical qubits measure how often each
qubit is misread; inverting each qubit's 2×2 misreading table estimates what the circuit really produced. It fixes
measurement errors only, not gate errors."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

from qapital.core.metrics import Portfolio, Quality, Reference, grade
from qapital.core.schemas import NoiseComparison
from qapital.quantum.hardware import DEFAULT_CHIP, compile_for_chip, fake_chip, two_qubit_gates

MAX_NOISY_QUBITS = 12
NO_SHOTS = Quality(p_optimal=0.0, feasible_rate=0.0, lift_over_random=0.0, approx_ratio=0.0)


@cache
def _noisy_simulator(chip: str) -> AerSimulator:
    return AerSimulator.from_backend(fake_chip(chip))


@dataclass
class NoisyRun:
    counts: dict[str, int]  # Qiskit bitstrings (qubit 0 last) and how often each came out
    two_qubit_gates: int
    compiled: QuantumCircuit  # as run on the chip, with its qubit layout
    chip: str
    seed: int


def noisy_run(circuit: QuantumCircuit, shots: int, seed: int, chip: str = DEFAULT_CHIP) -> NoisyRun:
    """Sample `circuit` (angles bound, no measurements) on the chip's noise model."""
    compiled = compile_for_chip(circuit.measure_all(inplace=False), seed, chip)
    result = _noisy_simulator(chip).run(compiled, shots=shots, seed_simulator=seed).result()
    return NoisyRun(result.get_counts(), two_qubit_gates(compiled), compiled, chip, seed)


def noisy_sample(
    circuit: QuantumCircuit, shots: int, seed: int, chip: str = DEFAULT_CHIP
) -> tuple[dict[str, int], int]:
    """Measured bitstrings from the chip's noise model, and the two-qubit gates the compiled circuit uses."""
    run = noisy_run(circuit, shots, seed, chip)
    return run.counts, run.two_qubit_gates


@dataclass
class ReadoutCalibration:
    read_one_given_zero: np.ndarray  # per circuit qubit: chance a prepared 0 is read as 1
    read_zero_given_one: np.ndarray  # per circuit qubit: chance a prepared 1 is read as 0

    @property
    def average(self) -> float:
        return float(np.mean([*self.read_one_given_zero, *self.read_zero_given_one]))


def calibrate_readout(run: NoisyRun, num_qubits: int, shots: int) -> ReadoutCalibration:
    """Prepare all 0s and all 1s on the physical qubits the run used, and count the misreadings."""
    physical = run.compiled.layout.final_index_layout()[:num_qubits]
    vectors = []
    for flip in (False, True):
        prepared = QuantumCircuit(num_qubits)
        if flip:
            prepared.x(range(num_qubits))
        prepared.measure_all()
        on_chip = transpile(prepared, fake_chip(run.chip), initial_layout=physical, optimization_level=0)
        counts = _noisy_simulator(run.chip).run(on_chip, shots=shots, seed_simulator=run.seed + 1).result()
        vectors.append(_distribution(counts.get_counts(), num_qubits))
    states = np.arange(2**num_qubits)
    ones = [(states >> qubit) & 1 for qubit in range(num_qubits)]
    return ReadoutCalibration(
        read_one_given_zero=np.array([vectors[0][bit == 1].sum() for bit in ones]),
        read_zero_given_one=np.array([vectors[1][bit == 0].sum() for bit in ones]),
    )


def mitigate_readout(counts: dict[str, int], calibration: ReadoutCalibration, num_qubits: int) -> dict[str, float]:
    """Estimated true distribution over bitstrings: each qubit's misreading table inverted, small negatives set to 0."""
    tensor = _distribution(counts, num_qubits).reshape((2,) * num_qubits)
    for qubit in range(num_qubits):
        e01, e10 = calibration.read_one_given_zero[qubit], calibration.read_zero_given_one[qubit]
        table = np.array([[1 - e01, e10], [e01, 1 - e10]])
        axis = num_qubits - 1 - qubit  # bitstrings put qubit 0 last, i.e. on the last axis
        tensor = np.moveaxis(np.tensordot(np.linalg.inv(table), tensor, axes=([1], [axis])), 0, axis)
    corrected = np.clip(tensor.reshape(-1), 0, None)
    corrected /= corrected.sum()
    return {format(state, f"0{num_qubits}b"): float(p) for state, p in enumerate(corrected) if p > 1e-12}


def _distribution(counts: dict, num_qubits: int) -> np.ndarray:
    vector = np.zeros(2**num_qubits)
    for bits, count in counts.items():
        vector[int(bits.replace(" ", ""), 2)] += count
    return vector / vector.sum()


def postselect(counts: Mapping[Portfolio, float], k: int) -> dict[Portfolio, float]:
    """Only the shots (or chances) of portfolios that hold exactly k stocks."""
    return {x: count for x, count in counts.items() if sum(x) == k}


def grade_postselected(counts: Mapping[Portfolio, float], reference: Reference, k: int) -> tuple[Quality, float]:
    """Quality of the shots that pass the count check, and the share of shots that passed."""
    kept = postselect(counts, k)
    share = sum(kept.values()) / sum(counts.values())
    return (grade(kept, reference) if kept else NO_SHOTS), share


def compare(
    ideal: Quality,
    noisy_counts: Mapping[Portfolio, float],
    reference: Reference,
    k: int,
    chip: str = DEFAULT_CHIP,
    mitigated: Mapping[Portfolio, float] | None = None,
    readout_error: float | None = None,
) -> NoiseComparison:
    noisy = grade(noisy_counts, reference)
    after, share = grade_postselected(noisy_counts, reference, k)
    extra = {}
    if mitigated is not None:
        fixed = grade(mitigated, reference)
        both, _ = grade_postselected(mitigated, reference, k)
        extra = {
            "readout_error": readout_error,
            "mitigated_p_optimal": fixed.p_optimal,
            "mitigated_approx_ratio": fixed.approx_ratio,
            "mitigated_feasible_rate": fixed.feasible_rate,
            "mitigated_postselected_p_optimal": both.p_optimal,
            "mitigated_postselected_approx_ratio": both.approx_ratio,
            "mitigated_postselected_feasible_rate": both.feasible_rate,
        }
    return NoiseComparison(
        chip=chip,
        ideal_p_optimal=ideal.p_optimal,
        noisy_p_optimal=noisy.p_optimal,
        ideal_approx_ratio=ideal.approx_ratio,
        noisy_approx_ratio=noisy.approx_ratio,
        ideal_feasible_rate=ideal.feasible_rate,
        noisy_feasible_rate=noisy.feasible_rate,
        postselected_share=share,
        postselected_p_optimal=after.p_optimal,
        postselected_approx_ratio=after.approx_ratio,
        postselected_feasible_rate=after.feasible_rate,
        **extra,
    )
