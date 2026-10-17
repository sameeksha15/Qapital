"""Join 2: the contract between the FastAPI backend and the quantum engine.

Rules
- Returns and risk are yearly decimals (0.12 means 12%).
- Stocks are always ticker names, never bitstrings.
- Every number is a plain Python float or int; lists, not NumPy arrays.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field


@dataclass
class MarketData:
    """Built by the backend's data pipeline, handed to solve()."""

    tickers: list[str]
    sectors: list[str]
    mu: np.ndarray  # yearly expected return per stock
    sigma: np.ndarray  # yearly covariance matrix
    fees: np.ndarray  # cost of buying each stock, as a decimal


class Settings(BaseModel):
    """What the user chose on the website."""

    k: int = Field(ge=1, description="Number of stocks to pick")
    risk_aversion: float = Field(1.0, gt=0, description="Risk slider (q)")
    sector_cap: int | None = Field(None, ge=1, description="Max stocks per sector")
    pairs_kept: float = Field(1.0, ge=0.25, le=1.0, description="Accuracy vs noise slider")
    depth: int = Field(2, ge=1, le=4, description="QAOA layers (p)")
    optimiser: Literal["COBYLA", "SPSA"] = "COBYLA"
    mixer: Literal["standard", "xy", "warm"] = Field(
        "xy", description="standard (penalty), xy (keeps K; ours), warm (penalty started from the relaxed solution)"
    )
    cvar_alpha: float = Field(
        0.25, gt=0, le=1, description="Tune for the best α-fraction of outcomes (CVaR); 1 = the plain average"
    )
    noisy: bool = False
    mitigate_readout: bool = Field(True, description="On noisy runs, measure and undo readout errors")
    run_pruning_study: bool = False
    seed: int = 42


class SampledPortfolio(BaseModel):
    stocks: list[str]
    count: int
    score: float
    valid: bool


class NoiseComparison(BaseModel):
    """Same quality numbers on the perfect simulator and the fake IBM chip.
    `postselected_*` grade only the noisy shots that hold exactly K stocks; `postselected_share` is how many did.
    `mitigated_*` (when readout mitigation is on) undo the measured readout errors first; `readout_error` is the
    average chance a qubit was misread in calibration."""

    chip: str  # fake IBM chip whose noise was used, e.g. "FakeBrisbane"
    ideal_p_optimal: float
    noisy_p_optimal: float
    ideal_approx_ratio: float
    noisy_approx_ratio: float
    ideal_feasible_rate: float
    noisy_feasible_rate: float
    postselected_share: float
    postselected_p_optimal: float
    postselected_approx_ratio: float
    postselected_feasible_rate: float
    readout_error: float | None = None
    mitigated_p_optimal: float | None = None
    mitigated_approx_ratio: float | None = None
    mitigated_feasible_rate: float | None = None
    mitigated_postselected_p_optimal: float | None = None
    mitigated_postselected_approx_ratio: float | None = None
    mitigated_postselected_feasible_rate: float | None = None


class HardwareCheck(BaseModel):
    """A tuned circuit run on IBM hardware (or a fake chip in Runtime's local mode), graded like a noisy run."""

    backend: str
    job_id: str
    local: bool  # True for a fake chip in local mode, False for real hardware
    two_qubit_gates: int  # after compiling for that backend
    comparison: NoiseComparison


class StartQuality(BaseModel):
    """What a circuit's starting state alone gives, before any quantum layer (exact chances)."""

    p_optimal: float
    feasible_rate: float
    lift_over_random: float


class PruningPoint(BaseModel):
    """One row of the pruning study: share of stock links kept, two-qubit gates on the noisy chip,
    and lift over random legal guessing on each simulator (always graded on the full, unpruned score)."""

    kept: float
    gates: int
    ideal: float
    noisy: float
    noisy_postselected: float


class QuantumResult(BaseModel):
    chosen: list[str]  # stocks QAOA picked
    score: float  # on the full, unpruned problem
    expected_return: float  # yearly, equal weights
    risk: float  # yearly volatility, equal weights
    p_optimal: float  # share of shots that were the true best
    feasible_rate: float  # share of shots that obeyed all rules
    lift_over_random: float  # p_optimal / chance of random valid guess
    approx_ratio: float  # mean closeness to the best over all shots (1.0 = every shot best, rule-breakers count 0)
    num_qubits: int  # stocks + slack
    num_slack_qubits: int  # extra qubits that enforce sector caps above 1
    two_qubit_gates: int  # after transpiling for the fake IBM chip
    circuit_depth: int  # after transpiling for the fake IBM chip
    convergence: list[float]  # tuning objective after each round (average energy, or CVaR when alpha < 1)
    top_samples: list[SampledPortfolio]  # top 20 by count
    layer_probs: list[list[float]]  # chance of each valid portfolio after each layer
    layer_labels: list[str]  # which portfolio each layer_probs column is
    noise: NoiseComparison | None = None
    shortlist: list[str] | None = None
    warm_start_alone: StartQuality | None = None  # warm-start circuits only: the starting state's own quality
