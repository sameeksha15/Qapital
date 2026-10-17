"""What a circuit would cost on a real IBM chip, using fake backends with each device's gates, wiring and errors."""

from functools import cache

from qiskit import QuantumCircuit
from qiskit.providers import BackendV2
from qiskit.transpiler import generate_preset_pass_manager
from qiskit_ibm_runtime import fake_provider

CHIPS = ("FakeBrisbane", "FakeFez")  # an older Eagle chip (gate counts, default noise) and a newer Heron chip
DEFAULT_CHIP = "FakeBrisbane"


@cache
def fake_chip(name: str = DEFAULT_CHIP) -> BackendV2:
    if name not in CHIPS:
        raise ValueError(f"Unknown chip {name!r}. Choose one of: {', '.join(CHIPS)}.")
    return getattr(fake_provider, name)()


def compile_for_chip(circuit: QuantumCircuit, seed: int, chip: str = DEFAULT_CHIP) -> QuantumCircuit:
    """The circuit rewritten for the chip's gates and wiring (routing SWAPs included). Same seed, same result."""
    return generate_preset_pass_manager(optimization_level=3, backend=fake_chip(chip), seed_transpiler=seed).run(
        circuit
    )


def two_qubit_gates(compiled: QuantumCircuit) -> int:
    return sum(
        1
        for instruction in compiled.data
        if instruction.operation.num_qubits == 2 and instruction.operation.name != "barrier"
    )


def hardware_cost(circuit: QuantumCircuit, seed: int) -> tuple[int, int]:
    """Two-qubit gate count and depth after compiling for the default fake chip."""
    compiled = compile_for_chip(circuit, seed)
    return two_qubit_gates(compiled), compiled.depth()
