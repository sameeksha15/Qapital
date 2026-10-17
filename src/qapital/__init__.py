"""Qapital: quantum-assisted portfolio optimisation (QAOA with constraint-preserving mixers),
benchmarked honestly against classical methods. The names most callers need are re-exported here."""

from qapital.core.problem import is_valid, portfolio_stats, score
from qapital.core.schemas import MarketData, QuantumResult, Settings
from qapital.data.market import load_market
from qapital.quantum.solver import hardware_check, pruning_study, solve

__all__ = [
    "MarketData",
    "QuantumResult",
    "Settings",
    "hardware_check",
    "is_valid",
    "load_market",
    "portfolio_stats",
    "pruning_study",
    "score",
    "solve",
]
