"""Stock universes: which stocks a market offers, their sectors, its benchmark index and its risk-free rate.

The lists live in data/universes/<id>.json, written by `python -m pipeline.universes` from the official sources and
reviewed before they are committed. Prices come separately, from the nightly snapshot."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from qapital.config import UNIVERSES_DIR


class Stock(BaseModel):
    ticker: str = Field(description="Yahoo Finance ticker, e.g. RELIANCE.NS or AAPL")
    name: str
    sector: str


class Benchmark(BaseModel):
    ticker: str
    name: str


class RiskFree(BaseModel):
    """Either a daily series in the snapshot (a yield in percent, e.g. ^IRX) or a fixed yearly rate with its source."""

    kind: Literal["series", "constant"]
    ticker: str | None = None
    rate: float | None = None
    source: str
    note: str | None = None

    @model_validator(mode="after")
    def _complete(self) -> "RiskFree":
        if self.kind == "series" and not self.ticker:
            raise ValueError("A risk-free series needs a ticker.")
        if self.kind == "constant" and self.rate is None:
            raise ValueError("A constant risk-free rate needs a rate.")
        return self


class Universe(BaseModel):
    id: str
    name: str
    country: str
    currency: str
    benchmark: Benchmark
    risk_free: RiskFree
    cost_model: str = Field(description="id of the trading-cost model in data/costs/")
    list_source: str
    list_as_of: str
    stocks: list[Stock]

    @model_validator(mode="after")
    def _unique(self) -> "Universe":
        tickers = [stock.ticker for stock in self.stocks]
        if len(set(tickers)) != len(tickers):
            raise ValueError(f"{self.id}: a ticker appears twice.")
        return self

    @property
    def tickers(self) -> list[str]:
        return [stock.ticker for stock in self.stocks]

    @property
    def sectors(self) -> dict[str, str]:
        return {stock.ticker: stock.sector for stock in self.stocks}


def universe_ids(directory: Path = UNIVERSES_DIR) -> list[str]:
    return sorted(path.stem for path in directory.glob("*.json"))


def load_universe(universe_id: str, directory: Path = UNIVERSES_DIR) -> Universe:
    path = directory / f"{universe_id}.json"
    if not path.exists():
        raise ValueError(f"Unknown market '{universe_id}'. Choose one of: {', '.join(universe_ids(directory))}.")
    return Universe.model_validate(json.loads(path.read_text(encoding="utf-8")))
