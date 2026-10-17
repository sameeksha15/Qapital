"""Score and rules → QUBO → Ising coefficients for the circuit (spec §6).

Qubits 0..n-1 are the stocks; slack qubits for sector caps above 1 come after them.
Energy arrays are indexed by basis number b, where qubit i is bit i of b (Qiskit's order)."""

import itertools
from dataclasses import dataclass

import numpy as np

from qapital.core.schemas import MarketData, Settings


@dataclass(frozen=True)
class SectorRule:
    """At most `cap` of `stocks` may be bought. Caps above 1 need slack qubits."""

    stocks: tuple[int, ...]
    cap: int
    slack: tuple[int, ...]


@dataclass
class Qubo:
    """f(z) = const + Σ linear[i]·z_i + Σ_{i<j} quadratic[i, j]·z_i·z_j over 0/1 variables z."""

    linear: np.ndarray
    quadratic: np.ndarray
    const: float = 0.0

    @classmethod
    def zeros(cls, num_qubits: int) -> "Qubo":
        return cls(np.zeros(num_qubits), np.zeros((num_qubits, num_qubits)))

    def add_square(self, weights: dict[int, float], target: float) -> None:
        """Adds (Σ weights[i]·z_i − target)², using z_i² = z_i."""
        for i, w in weights.items():
            self.linear[i] += w * w - 2 * target * w
        for (i, wi), (j, wj) in itertools.combinations(sorted(weights.items()), 2):
            self.quadratic[i, j] += 2 * wi * wj
        self.const += target * target

    def plus(self, other: "Qubo", weight: float) -> "Qubo":
        return Qubo(
            self.linear + weight * other.linear,
            self.quadratic + weight * other.quadratic,
            self.const + weight * other.const,
        )

    def energies(self, bits: np.ndarray) -> np.ndarray:
        """f for every row of a 0/1 matrix."""
        return self.const + bits @ self.linear + np.einsum("bi,ij,bj->b", bits, self.quadratic, bits)


@dataclass(frozen=True)
class Hamiltonian:
    num_stocks: int
    num_qubits: int
    h: np.ndarray  # Z coefficients, divided by `scale`
    J: np.ndarray  # ZZ coefficients (upper triangle), divided by `scale`
    scale: float  # largest |h| or |J| before scaling
    penalty: float  # λ, shared by every rule in H
    energies: np.ndarray  # energy of every basis state in score units, rules included


def sector_rules(sectors: list[str], settings: Settings) -> list[SectorRule]:
    cap = settings.sector_cap
    if cap is None or cap >= settings.k:
        return []
    rules, next_qubit = [], len(sectors)
    for sector in dict.fromkeys(sectors):
        stocks = tuple(i for i, s in enumerate(sectors) if s == sector)
        if len(stocks) > cap:
            width = 0 if cap == 1 else cap.bit_length()
            rules.append(SectorRule(stocks, cap, tuple(range(next_qubit, next_qubit + width))))
            next_qubit += width
    return rules


def count_qubits(sectors: list[str], settings: Settings) -> int:
    return len(sectors) + sum(len(rule.slack) for rule in sector_rules(sectors, settings))


def kept_pairs(sigma: np.ndarray, fraction: float) -> list[tuple[int, int]]:
    """The strongest `fraction` of stock pairs by |covariance| (spec §7.6)."""
    pairs = sorted(itertools.combinations(range(len(sigma)), 2), key=lambda pair: -abs(sigma[pair]))
    return pairs[: round(fraction * len(pairs))]


def score_qubo(data: MarketData, settings: Settings, num_qubits: int) -> Qubo:
    """q·xᵀΣx − μᵀx + feesᵀx, with only the kept covariance pairs."""
    q, n = settings.risk_aversion, len(data.tickers)
    qubo = Qubo.zeros(num_qubits)
    qubo.linear[:n] = q * np.diag(data.sigma) - data.mu + data.fees
    for i, j in kept_pairs(data.sigma, settings.pairs_kept):
        qubo.quadratic[i, j] = 2 * q * data.sigma[i, j]
    return qubo


def rules_qubo(settings: Settings, rules: list[SectorRule], num_stocks: int, num_qubits: int) -> Qubo:
    """Zero when every rule holds, at least 1 when one breaks. The XY mixer keeps 'exactly K' by itself;
    the penalty and warm-start circuits need the fine."""
    qubo = Qubo.zeros(num_qubits)
    if settings.mixer != "xy":
        qubo.add_square({i: 1 for i in range(num_stocks)}, settings.k)
    for rule in rules:
        if rule.cap == 1:
            for i, j in itertools.combinations(rule.stocks, 2):
                qubo.quadratic[i, j] += 1
        else:
            slack_weights = {qubit: 2**bit for bit, qubit in enumerate(rule.slack)}
            qubo.add_square({i: 1 for i in rule.stocks} | slack_weights, rule.cap)
    return qubo


def to_ising(qubo: Qubo) -> tuple[np.ndarray, np.ndarray]:
    """Substitutes z_i = (1 − Z_i)/2 and drops the constant (spec §6.3)."""
    b = qubo.quadratic
    h = -qubo.linear / 2 - (b + b.T).sum(axis=1) / 4
    return h, np.triu(b, 1) / 4


def basis_bits(num_qubits: int) -> np.ndarray:
    """Row b holds the bits of basis state b, qubit 0 first."""
    return (np.arange(2**num_qubits)[:, None] >> np.arange(num_qubits)) & 1


def penalty_for(score_energy: np.ndarray, rule_energy: np.ndarray, allowed: np.ndarray, target: float) -> float:
    """Smallest λ at which every rule-breaker in `allowed` has energy ≥ target."""
    breakers = allowed & (rule_energy > 0)
    if not breakers.any():
        return 0.0

    def lowest_breaker(penalty: float) -> float:
        return np.min(score_energy[breakers] + penalty * rule_energy[breakers])

    if lowest_breaker(0.0) >= target:
        return 0.0
    low, high = 0.0, 1.0
    while lowest_breaker(high) < target:
        high *= 2
    for _ in range(100):
        middle = (low + high) / 2
        low, high = (middle, high) if lowest_breaker(middle) < target else (low, middle)
    return high


def calibrated_penalty(score_energy: np.ndarray, rule_energy: np.ndarray, allowed: np.ndarray) -> float:
    """Spec §6.5: the best rule-breaker sits halfway between the best and the average valid portfolio."""
    valid_scores = score_energy[allowed & (rule_energy == 0)]
    best, mean = valid_scores.min(), valid_scores.mean()
    target = max((best + mean) / 2, best + 1e-6 * (1 + abs(best)))
    return penalty_for(score_energy, rule_energy, allowed, target)


def build_hamiltonian(data: MarketData, settings: Settings) -> Hamiltonian:
    num_stocks = len(data.tickers)
    rules = sector_rules(data.sectors, settings)
    num_qubits = count_qubits(data.sectors, settings)
    score_part = score_qubo(data, settings, num_qubits)
    rules_part = rules_qubo(settings, rules, num_stocks, num_qubits)

    bits = basis_bits(num_qubits)
    score_energy, rule_energy = score_part.energies(bits), rules_part.energies(bits)
    if settings.mixer == "xy":
        allowed = bits[:, :num_stocks].sum(axis=1) == settings.k
    else:
        allowed = np.ones(len(bits), dtype=bool)
    penalty = calibrated_penalty(score_energy, rule_energy, allowed)

    h, J = to_ising(score_part.plus(rules_part, penalty))
    scale = max(np.abs(h).max(), np.abs(J).max()) or 1.0
    return Hamiltonian(
        num_stocks, num_qubits, h / scale, J / scale, scale, penalty, score_energy + penalty * rule_energy
    )
