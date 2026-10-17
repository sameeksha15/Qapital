"""solve(): the engine's entry point (Join 2), and pruning_study() for the website's pruning chart.

Builds the Hamiltonian, tunes the QAOA angles on the ideal simulator, samples 4,096 portfolios from
the tuned circuit and grades every sample against brute force on the full, unpruned score.
With `noisy=True` the same tuned circuit is also sampled on a noisy fake IBM chip (at most 12 qubits), with readout
mitigation unless switched off. The knobs are tuned for the average energy, or for the best α-fraction of outcomes
(CVaR-QAOA, Barkoutsos et al., Quantum 4, 256, 2020) when `cvar_alpha` < 1."""

import itertools
from collections import Counter
from collections.abc import Callable

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter

from qapital.classical.relaxation import relax_and_round
from qapital.core.metrics import Portfolio, Reference, brute_force, grade
from qapital.core.problem import is_valid, portfolio_stats, score
from qapital.core.schemas import (
    HardwareCheck,
    MarketData,
    PruningPoint,
    QuantumResult,
    SampledPortfolio,
    Settings,
    StartQuality,
)
from qapital.data.market import validate_market_data
from qapital.quantum.circuits import beta_period, qaoa_circuit, warm_start_angles
from qapital.quantum.hamiltonian import Hamiltonian, build_hamiltonian
from qapital.quantum.hardware import DEFAULT_CHIP, hardware_cost
from qapital.quantum.ibm import run_on_hardware
from qapital.quantum.noise import (
    MAX_NOISY_QUBITS,
    calibrate_readout,
    compare,
    grade_postselected,
    mitigate_readout,
    noisy_run,
    noisy_sample,
)
from qapital.quantum.optimise import Energy, evaluation_budget, tune
from qapital.quantum.shortlist import fit_to_simulator
from qapital.quantum.simulator import IdealSimulator

MAX_QUBITS = 16
SHOTS = 4096
TOP_SAMPLES = 20
LAYER_PORTFOLIOS = 8
PRUNING_LEVELS = (1.0, 0.75, 0.5, 0.25)
ProgressFn = Callable[[str, int, int], None]
CircuitBuilder = Callable[[int], tuple[QuantumCircuit, list[Parameter]]]  # layers -> circuit and its knobs


def solve(data: MarketData, settings: Settings, on_progress: ProgressFn | None = None) -> QuantumResult:
    """`settings.run_pruning_study` is for the backend: when it is on, the backend also calls pruning_study()."""
    report = on_progress or (lambda stage, step, total: None)
    max_qubits = MAX_NOISY_QUBITS if settings.noisy else MAX_QUBITS
    data, shortlist = fit_to_simulator(validate_market_data(data), settings, max_qubits)

    report("Building the score", 0, 1)
    ham = build_hamiltonian(data, settings)
    reference = brute_force(data, settings)
    build = circuit_builder(data, ham, settings)

    total = evaluation_budget(settings.depth, beta_period(settings.mixer))
    steps = itertools.count(1)
    theta, convergence = _tune(
        build, ham, settings, on_step=lambda: report("Tuning circuit", min(next(steps), total), total)
    )

    report("Sampling portfolios", 0, 1)
    tuned = _tuned_circuit(build, settings, theta)
    counts = _ideal_counts(build, ham, settings, theta)
    chosen = _best_sample(counts, reference)
    quality = grade(counts, reference)
    two_qubit_gates, circuit_depth = hardware_cost(tuned, settings.seed)
    shown = sorted(reference.scores, key=lambda x: reference.scores[x])[:LAYER_PORTFOLIOS]
    expected_return, risk = portfolio_stats(np.array(chosen), data)

    noise = None
    if settings.noisy:
        report("Running on noisy chip", 0, 1)
        run = noisy_run(tuned, SHOTS, settings.seed)
        mitigated = readout_error = None
        if settings.mitigate_readout:
            calibration = calibrate_readout(run, ham.num_qubits, SHOTS)
            readout_error = calibration.average
            mitigated = _portfolio_chances(mitigate_readout(run.counts, calibration, ham.num_qubits), ham.num_stocks)
        noisy_counts = _portfolio_counts(run.counts, ham.num_stocks)
        noise = compare(quality, noisy_counts, reference, settings.k, run.chip, mitigated, readout_error)
    report("Done", 1, 1)

    return QuantumResult(
        chosen=_tickers(chosen, data),
        score=reference.scores[chosen],
        expected_return=expected_return,
        risk=risk,
        p_optimal=quality.p_optimal,
        feasible_rate=quality.feasible_rate,
        lift_over_random=quality.lift_over_random,
        approx_ratio=quality.approx_ratio,
        num_qubits=ham.num_qubits,
        num_slack_qubits=ham.num_qubits - ham.num_stocks,
        two_qubit_gates=two_qubit_gates,
        circuit_depth=circuit_depth,
        convergence=convergence,
        top_samples=_top_samples(counts, data, settings),
        layer_probs=_layer_probabilities(build, ham, settings, theta, shown),
        layer_labels=[", ".join(_tickers(x, data)) for x in shown],
        noise=noise,
        shortlist=shortlist,
        warm_start_alone=_start_quality(build, ham, reference) if settings.mixer == "warm" else None,
    )


def hardware_check(
    data: MarketData, settings: Settings, backend: str | None = None, on_progress: ProgressFn | None = None
) -> HardwareCheck:
    """Tune on the ideal simulator, then run the same circuit on IBM hardware through Qiskit Runtime (or on a fake chip
    with backend="fake:FakeBrisbane") and grade it like a noisy run: raw, count check, readout mitigation, both."""
    report = on_progress or (lambda stage, step, total: None)
    data, _ = fit_to_simulator(validate_market_data(data), settings, MAX_QUBITS)
    report("Building the score", 0, 1)
    ham = build_hamiltonian(data, settings)
    reference = brute_force(data, settings)
    build = circuit_builder(data, ham, settings)
    total = evaluation_budget(settings.depth, beta_period(settings.mixer))
    steps = itertools.count(1)
    theta, _ = _tune(build, ham, settings, on_step=lambda: report("Tuning circuit", min(next(steps), total), total))
    ideal = grade(_ideal_counts(build, ham, settings, theta), reference)

    report("Running on IBM hardware", 0, 1)
    run = run_on_hardware(_tuned_circuit(build, settings, theta), SHOTS, settings.seed, backend)
    noisy = _portfolio_counts(run.counts, ham.num_stocks)
    mitigated = _portfolio_chances(mitigate_readout(run.counts, run.calibration, ham.num_qubits), ham.num_stocks)
    comparison = compare(ideal, noisy, reference, settings.k, run.backend, mitigated, run.calibration.average)
    report("Done", 1, 1)
    return HardwareCheck(
        backend=run.backend,
        job_id=run.job_id,
        local=run.local,
        two_qubit_gates=run.two_qubit_gates,
        comparison=comparison,
    )


def circuit_builder(data: MarketData, ham: Hamiltonian, settings: Settings) -> CircuitBuilder:
    """Circuits of any depth for this problem. A warm start takes its starting chances from the classical relaxed
    solution of the same problem (relaxation + rounding's amounts)."""
    angles = warm_start_angles(relax_and_round(data, settings).amounts) if settings.mixer == "warm" else None

    def build(depth: int) -> tuple[QuantumCircuit, list[Parameter]]:
        return qaoa_circuit(ham, settings.k, settings.mixer, depth, angles)

    return build


def pruning_study(
    data: MarketData, settings: Settings, on_progress: ProgressFn | None = None, chip: str = DEFAULT_CHIP
) -> list[PruningPoint]:
    """Spec §7.6 (E8): the same problem with 100, 75, 50 and 25% of stock links kept, each tuned on the ideal
    simulator and sampled on both simulators. Lists are shortlisted to the noisy limit of 12 qubits.
    `settings.pairs_kept` is ignored; every level is graded on the full, unpruned score."""
    report = on_progress or (lambda stage, step, total: None)
    data, _ = fit_to_simulator(validate_market_data(data), settings, MAX_NOISY_QUBITS)
    reference = brute_force(data, settings)
    points = []
    for level, kept in enumerate(PRUNING_LEVELS):
        report("Pruning study", level, len(PRUNING_LEVELS))
        run = settings.model_copy(update={"pairs_kept": kept})
        ham = build_hamiltonian(data, run)
        build = circuit_builder(data, ham, run)
        theta, _ = _tune(build, ham, run)
        ideal = grade(_ideal_counts(build, ham, run, theta), reference)
        bitstrings, gates = noisy_sample(_tuned_circuit(build, run, theta), SHOTS, run.seed, chip)
        noisy_counts = _portfolio_counts(bitstrings, ham.num_stocks)
        postselected, _ = grade_postselected(noisy_counts, reference, run.k)
        points.append(
            PruningPoint(
                kept=kept,
                gates=gates,
                ideal=ideal.lift_over_random,
                noisy=grade(noisy_counts, reference).lift_over_random,
                noisy_postselected=postselected.lift_over_random,
            )
        )
    report("Done", 1, 1)
    return points


def _tune(build: CircuitBuilder, ham: Hamiltonian, settings: Settings, on_step: Callable[[], None] | None = None):
    return tune(
        lambda depth: _energy(build, ham, settings, depth),
        settings.depth,
        settings.optimiser,
        beta_period(settings.mixer),
        settings.seed,
        on_step=on_step or (lambda: None),
    )


def _tuned_circuit(build: CircuitBuilder, settings: Settings, theta: np.ndarray) -> QuantumCircuit:
    """The circuit with its tuned angles filled in, without measurements."""
    circuit, params = build(settings.depth)
    return circuit.assign_parameters(dict(zip(params, theta, strict=True)))


def _ideal_counts(build: CircuitBuilder, ham: Hamiltonian, settings: Settings, theta: np.ndarray) -> Counter[Portfolio]:
    circuit, params = build(settings.depth)
    return _portfolio_counts(IdealSimulator(circuit, params).sample(theta, SHOTS, settings.seed), ham.num_stocks)


def _energy(build: CircuitBuilder, ham: Hamiltonian, settings: Settings, depth: int) -> Energy:
    """The tuning objective, exact from the statevector, in score units: the average energy ⟨H⟩ = Σ_b P(b)·E(b),
    or with cvar_alpha < 1 the average energy of the best α-fraction of outcomes (CVaR)."""
    circuit, params = build(depth)
    simulator = IdealSimulator(circuit, params)
    alpha = settings.cvar_alpha
    if alpha >= 1:
        return lambda theta: float(simulator.probabilities(theta) @ ham.energies)
    order = np.argsort(ham.energies, kind="stable")
    ordered = ham.energies[order]

    def cvar(theta: np.ndarray) -> float:
        p = simulator.probabilities(theta)[order]
        taken = np.minimum(p, np.maximum(alpha - (np.cumsum(p) - p), 0.0))  # fill the best α of probability
        return float(taken @ ordered / alpha)

    return cvar


def _start_quality(build: CircuitBuilder, ham: Hamiltonian, reference: Reference) -> StartQuality:
    """Exact quality of the starting state alone (no layers): what a warm start gives before any quantum work."""
    circuit, _ = build(0)
    probabilities = IdealSimulator(circuit, []).probabilities(np.array([]))
    distribution: dict[Portfolio, float] = {}
    stock_part = np.arange(len(probabilities)) % 2**ham.num_stocks
    for number, p in enumerate(np.bincount(stock_part, weights=probabilities, minlength=2**ham.num_stocks)):
        distribution[tuple((number >> i) & 1 for i in range(ham.num_stocks))] = float(p)
    quality = grade(distribution, reference)
    return StartQuality(
        p_optimal=quality.p_optimal, feasible_rate=quality.feasible_rate, lift_over_random=quality.lift_over_random
    )


def _portfolio_counts(bitstrings: dict[str, int], num_stocks: int) -> Counter[Portfolio]:
    """Qiskit bitstrings are little-endian (rightmost character = qubit 0), so reverse them.
    Slack qubits come after the stocks and are dropped."""
    counts: Counter[Portfolio] = Counter()
    for bitstring, count in bitstrings.items():
        counts[tuple(int(bit) for bit in reversed(bitstring))[:num_stocks]] += count
    return counts


def _portfolio_chances(distribution: dict[str, float], num_stocks: int) -> dict[Portfolio, float]:
    """The same as _portfolio_counts, for a probability distribution over bitstrings."""
    chances: dict[Portfolio, float] = {}
    for bitstring, chance in distribution.items():
        portfolio = tuple(int(bit) for bit in reversed(bitstring))[:num_stocks]
        chances[portfolio] = chances.get(portfolio, 0.0) + chance
    return chances


def _best_sample(counts: Counter[Portfolio], reference: Reference) -> Portfolio:
    valid = [x for x in counts if x in reference.scores]
    if not valid:
        raise ValueError(
            f"None of the {SHOTS:,} sampled portfolios followed the rules. Try more layers or the XY mixer."
        )
    return min(valid, key=lambda x: reference.scores[x])


def _top_samples(counts: Counter[Portfolio], data: MarketData, settings: Settings) -> list[SampledPortfolio]:
    samples = [
        SampledPortfolio(
            stocks=_tickers(x, data),
            count=count,
            score=score(np.array(x), data, settings),
            valid=is_valid(np.array(x), data, settings),
        )
        for x, count in counts.items()
    ]
    return sorted(samples, key=lambda sample: (-sample.count, sample.score))[:TOP_SAMPLES]


def _layer_probabilities(
    build: CircuitBuilder, ham: Hamiltonian, settings: Settings, theta: np.ndarray, portfolios: list[Portfolio]
) -> list[list[float]]:
    """Chance of each portfolio after 0, 1, …, p layers of the tuned circuit (spec §7.7)."""
    depth = settings.depth
    stock_part = np.arange(2**ham.num_qubits) % 2**ham.num_stocks
    numbers = [sum(bit << i for i, bit in enumerate(x)) for x in portfolios]
    rows = []
    for layers in range(depth + 1):
        circuit, params = build(layers)
        angles = np.concatenate([theta[:layers], theta[depth : depth + layers]])
        probabilities = IdealSimulator(circuit, params).probabilities(angles)
        per_portfolio = np.bincount(stock_part, weights=probabilities, minlength=2**ham.num_stocks)
        rows.append([float(per_portfolio[b]) for b in numbers])
    return rows


def _tickers(x: Portfolio, data: MarketData) -> list[str]:
    return [ticker for ticker, bit in zip(data.tickers, x, strict=True) if bit]
