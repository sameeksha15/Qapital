"""Tuning the circuit angles θ = (γ1..γp, β1..βp) to minimise the average energy (spec §7.2).

Depth 1 starts from the lowest point of a coarse (γ, β) grid. Each deeper circuit starts from the
previous optimum stretched by INTERP (Zhou et al., PRX 2020), so no information about the answer goes in.
For experiment E6, `start="random"` instead tunes all layers at once from seeded random angles."""

import itertools
from collections.abc import Callable

import numpy as np
from scipy.optimize import minimize

Energy = Callable[[np.ndarray], float]

GRID_POINTS_PER_PI = 10
EVALUATIONS_PER_LAYER = 150
SPSA_CALIBRATION_STEPS = 5


def tune(
    energy_at_depth: Callable[[int], Energy],
    depth: int,
    optimiser: str,
    beta_period: float,
    seed: int,
    on_step: Callable[[], None] = lambda: None,
    start: str = "warm",
) -> tuple[np.ndarray, list[float]]:
    """Returns the best angles for `depth` layers and the energy after every optimiser step.
    `start="random"` gets the same total number of circuit runs as the warm start may use."""
    if start not in ("warm", "random"):
        raise ValueError(f"Unknown start {start!r}. Use 'warm' or 'random'.")
    rng = np.random.default_rng(seed)
    history = []

    def counted(energy: Energy, record: bool) -> Energy:
        def wrapped(theta: np.ndarray) -> float:
            value = energy(theta)
            if record:
                history.append(value)
            on_step()
            return value

        return wrapped

    if start == "random":
        tracked = counted(energy_at_depth(depth), record=True)
        theta, budget = random_angles(depth, beta_period, rng), evaluation_budget(depth, beta_period)
        theta = cobyla(tracked, theta, budget) if optimiser == "COBYLA" else spsa(tracked, theta, budget, rng)
        return theta, history

    energy = energy_at_depth(1)
    theta = min(start_grid(beta_period), key=counted(energy, record=False))
    for layers in range(1, depth + 1):
        if layers > 1:
            theta, energy = interp(theta), energy_at_depth(layers)
        budget = EVALUATIONS_PER_LAYER * layers
        tracked = counted(energy, record=True)
        theta = cobyla(tracked, theta, budget) if optimiser == "COBYLA" else spsa(tracked, theta, budget, rng)
    return theta, history


def evaluation_budget(depth: int, beta_period: float) -> int:
    """Most circuit evaluations `tune` can use; COBYLA may stop sooner."""
    return len(start_grid(beta_period)) + EVALUATIONS_PER_LAYER * depth * (depth + 1) // 2


def start_grid(beta_period: float) -> np.ndarray:
    gammas = np.linspace(0, np.pi, GRID_POINTS_PER_PI + 1)[1:]
    betas = np.linspace(0, beta_period, round(GRID_POINTS_PER_PI * beta_period / np.pi), endpoint=False)
    return np.array(list(itertools.product(gammas, betas)))


def random_angles(depth: int, beta_period: float, rng: np.random.Generator) -> np.ndarray:
    """γ1..γp uniform in [0, π), β1..βp uniform in [0, beta_period)."""
    return np.concatenate([rng.uniform(0, np.pi, depth), rng.uniform(0, beta_period, depth)])


def interp(theta: np.ndarray) -> np.ndarray:
    """Optimum at depth p → starting point at depth p+1, e.g. γ = [0.3, 0.6] → [0.3, 0.45, 0.6]."""
    p = len(theta) // 2

    def stretch(angles: np.ndarray) -> np.ndarray:
        padded = np.concatenate([[0.0], angles, [0.0]])
        return np.array([(i - 1) / p * padded[i - 1] + (p - i + 1) / p * padded[i] for i in range(1, p + 2)])

    return np.concatenate([stretch(theta[:p]), stretch(theta[p:])])


def cobyla(energy: Energy, theta: np.ndarray, budget: int) -> np.ndarray:
    return minimize(energy, theta, method="COBYLA", options={"maxiter": budget, "rhobeg": 0.2}).x


def spsa(
    energy: Energy,
    theta: np.ndarray,
    budget: int,
    rng: np.random.Generator,
    perturbation: float = 0.1,
    first_step: float = 0.1,
) -> np.ndarray:
    """Spall's SPSA with the standard decays a/(k+1+A)^0.602 and c/(k+1)^0.101.
    `a` is set so the first step moves the angles by about `first_step` radians. A step is only
    taken if it doesn't raise the energy ("blocking"), so a badly sized step can't throw the angles away."""
    iterations = (budget - 1 - 2 * SPSA_CALIBRATION_STEPS) // 3
    stability = 0.1 * iterations

    def gradient(theta: np.ndarray, size: float) -> np.ndarray:
        delta = rng.choice([-1.0, 1.0], size=len(theta))
        return (energy(theta + size * delta) - energy(theta - size * delta)) / (2 * size) * delta

    typical = np.mean([np.abs(gradient(theta, perturbation)).mean() for _ in range(SPSA_CALIBRATION_STEPS)])
    gain = first_step * (stability + 1) ** 0.602 / typical if typical > 0 else first_step
    current = energy(theta)
    for k in range(iterations):
        candidate = theta - gain / (k + 1 + stability) ** 0.602 * gradient(theta, perturbation / (k + 1) ** 0.101)
        candidate_energy = energy(candidate)
        if candidate_energy <= current:
            theta, current = candidate, candidate_energy
    return theta
