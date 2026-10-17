"""Reading a daily-returns JSON (pandas 'split' layout with [ticker, sector] columns) into MarketData.
Used by scripts/run_on_returns and the hackathon-equivalence test."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from qapital.core.schemas import MarketData
from qapital.data.market import ESTIMATION_END, ESTIMATION_START, MIN_RETURNS, TRADING_DAYS


def daily_returns(path: str | Path, kind: str) -> pd.DataFrame:
    """Simple daily returns, one column per (ticker, sector). `kind` says what the file holds:
    "simple" (P_t/P_{t−1} − 1, what the engine expects) or "log" (ln(P_t/P_{t−1}), converted with e^r − 1)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    columns = pd.MultiIndex.from_tuples([tuple(column) for column in raw["columns"]])
    returns = pd.DataFrame(raw["data"], index=pd.to_datetime(raw["index"]), columns=columns)
    return np.expm1(returns) if kind == "log" else returns


def load_returns(path: str | Path, kind: str, fee: float) -> MarketData:
    """Yearly μ and Σ from the 2021–2024 window only, as in load_market."""
    window = daily_returns(path, kind).loc[ESTIMATION_START:ESTIMATION_END]
    broken = [ticker for (ticker, _), gaps in window.isna().any().items() if gaps]
    if broken:
        raise ValueError(f"Returns between {ESTIMATION_START} and {ESTIMATION_END} have gaps for {', '.join(broken)}.")
    if len(window) < MIN_RETURNS:
        raise ValueError(
            f"Only {len(window)} days of returns between {ESTIMATION_START} and {ESTIMATION_END}; "
            f"at least {MIN_RETURNS} are needed."
        )
    return MarketData(
        tickers=[ticker for ticker, _ in window.columns],
        sectors=[sector for _, sector in window.columns],
        mu=window.mean().to_numpy() * TRADING_DAYS,
        sigma=window.cov().to_numpy() * TRADING_DAYS,
        fees=np.full(len(window.columns), fee),
    )
