"""Running a tuned circuit on IBM quantum hardware through Qiskit Runtime (the client-side Sampler).

The token is read only from the environment (QISKIT_IBM_TOKEN, and optionally QISKIT_IBM_INSTANCE); it never appears in
code, logs or results. The circuit and two readout-calibration circuits (all 0s, all 1s on the same physical qubits)
go in one job. On real hardware, dynamical decoupling and gate and measurement twirling are switched on.
`backend="fake:FakeBrisbane"` runs the same code in Runtime's local mode on a fake chip, for tests and dry runs."""

import os
from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit
from qiskit.providers import BackendV2
from qiskit.transpiler import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.executor_sampler import Sampler

from qapital.quantum.hardware import fake_chip, two_qubit_gates
from qapital.quantum.noise import ReadoutCalibration

TOKEN_VARIABLE = "QISKIT_IBM_TOKEN"
INSTANCE_VARIABLE = "QISKIT_IBM_INSTANCE"
FAKE_PREFIX = "fake:"


@dataclass
class HardwareRun:
    counts: dict[str, int]
    calibration: ReadoutCalibration
    backend: str
    job_id: str
    two_qubit_gates: int
    local: bool  # True when run on a fake chip in Runtime's local mode


def ibm_backend(name: str | None, min_qubits: int) -> BackendV2:
    """A fake chip ("fake:<name>"), a named IBM backend, or the least busy real one with enough qubits."""
    if name and name.startswith(FAKE_PREFIX):
        return fake_chip(name.removeprefix(FAKE_PREFIX))
    token = os.environ.get(TOKEN_VARIABLE)
    if not token:
        raise ValueError(
            f"Running on IBM hardware needs an IBM Quantum token in the {TOKEN_VARIABLE} environment variable."
        )
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform", token=token, instance=os.environ.get(INSTANCE_VARIABLE) or None
    )
    if name:
        return service.backend(name)
    return service.least_busy(min_num_qubits=min_qubits, operational=True, simulator=False)


def run_on_hardware(circuit: QuantumCircuit, shots: int, seed: int, backend: str | None = None) -> HardwareRun:
    """Sample `circuit` (angles bound, no measurements) and calibrate its readout, in one Runtime job."""
    target = ibm_backend(backend, circuit.num_qubits)
    compiled = generate_preset_pass_manager(optimization_level=3, backend=target, seed_transpiler=seed).run(
        circuit.measure_all(inplace=False)
    )
    physical = compiled.layout.final_index_layout()[: circuit.num_qubits]
    calibrations = []
    for flip in (False, True):
        prepared = QuantumCircuit(circuit.num_qubits)
        if flip:
            prepared.x(range(circuit.num_qubits))
        prepared.measure_all()
        calibrations.append(
            generate_preset_pass_manager(optimization_level=0, backend=target, initial_layout=physical).run(prepared)
        )

    local = backend is not None and backend.startswith(FAKE_PREFIX)
    sampler = Sampler(mode=target)
    sampler.options.default_shots = shots
    if local:
        sampler.options.simulator.seed_simulator = seed
    else:
        sampler.options.dynamical_decoupling.enable = True
        sampler.options.dynamical_decoupling.sequence_type = "XY4"
        sampler.options.twirling.enable_gates = True
        sampler.options.twirling.enable_measure = True
    job = sampler.run([compiled, *calibrations])
    results = job.result()
    counts = [result.data.meas.get_counts() for result in results]
    return HardwareRun(
        counts=counts[0],
        calibration=_calibration(counts[1], counts[2], circuit.num_qubits),
        backend=target.name,
        job_id=job.job_id(),
        two_qubit_gates=two_qubit_gates(compiled),
        local=local,
    )


def _calibration(zeros: dict[str, int], ones: dict[str, int], num_qubits: int) -> ReadoutCalibration:
    def misread(counts: dict[str, int], qubit: int, expected: str) -> float:
        total = sum(counts.values())
        wrong = sum(n for bits, n in counts.items() if bits.replace(" ", "")[num_qubits - 1 - qubit] != expected)
        return wrong / total

    return ReadoutCalibration(
        read_one_given_zero=np.array([misread(zeros, q, "0") for q in range(num_qubits)]),
        read_zero_given_one=np.array([misread(ones, q, "1") for q in range(num_qubits)]),
    )
