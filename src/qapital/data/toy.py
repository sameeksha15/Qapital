"""Made-up data: the 4-stock toy example, and random markets of any shape for tests."""

import numpy as np

from qapital.core.schemas import MarketData

# Sector sizes shaped like NIFTY 50: one big sector, many small ones.
NIFTY_LIKE_SECTORS = (
    ["Fin"] * 12
    + ["IT"] * 5
    + ["Energy"] * 4
    + ["FMCG"] * 5
    + ["Auto"] * 6
    + ["Pharma"] * 4
    + ["Metals"] * 4
    + ["Cement"] * 2
    + ["Telecom"]
    + ["Power"] * 2
    + ["Infra"] * 2
    + ["Consumer"] * 2
    + ["Insurance"]
)


def toy() -> MarketData:
    return MarketData(
        tickers=["BANK1", "BANK2", "TECH", "FMCG"],
        sectors=["Banking", "Banking", "IT", "FMCG"],
        mu=np.array([0.12, 0.14, 0.10, 0.08]),
        sigma=np.array(
            [
                [0.04, 0.03, 0.01, 0.002],
                [0.03, 0.05, 0.01, 0.001],
                [0.01, 0.01, 0.03, -0.005],
                [0.002, 0.001, -0.005, 0.02],
            ]
        ),
        fees=np.full(4, 0.005),
    )


def random_market(sectors: list[str], seed: int = 0) -> MarketData:
    """Yearly returns of 5–30% and a positive-definite covariance with volatilities around 20–30%."""
    rng = np.random.default_rng(seed)
    n = len(sectors)
    a = rng.normal(size=(n, n))
    return MarketData(
        tickers=[f"S{i}" for i in range(n)],
        sectors=list(sectors),
        mu=rng.uniform(0.05, 0.3, n),
        sigma=a @ a.T / n * 0.04 + np.eye(n) * 0.01,
        fees=np.full(n, 0.001),
    )
