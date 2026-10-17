"""Trading costs from cited rate cards (data/costs/<id>.json), itemised per order.

Charges can be a share of the trade value, an amount per share (with an optional cap per order) or a fixed amount per
order; some attract GST. `score_fees` turns them into the per-stock cost term the optimiser's score uses."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, model_validator

from qapital.config import DATA_DIR

COSTS_DIR = DATA_DIR / "costs"
Side = Literal["buy", "sell"]


class Charge(BaseModel):
    name: str
    side: Literal["buy", "sell", "both"]
    rate: float = 0.0  # share of the trade value
    per_share: float = 0.0  # amount per share traded
    max_per_order: float | None = None  # cap on the per-share part
    per_order: float = 0.0  # fixed amount per order
    gst: bool = False  # tax added on top of this charge

    @model_validator(mode="after")
    def _not_negative(self) -> "Charge":
        if min(self.rate, self.per_share, self.per_order) < 0:
            raise ValueError(f"{self.name}: charges can't be negative.")
        return self

    def amount(self, side: Side, shares: float, price: float) -> float:
        if self.side not in (side, "both") or shares <= 0:
            return 0.0
        per_share = self.per_share * shares
        if self.max_per_order is not None:
            per_share = min(per_share, self.max_per_order)
        return self.rate * shares * price + per_share + self.per_order


class CostModel(BaseModel):
    id: str
    name: str
    currency: str
    as_of: str
    sources: list[str]
    gst: float = 0.0
    charges: list[Charge]

    def itemise(self, side: Side, shares: float, price: float) -> list[tuple[str, float]]:
        """Each charge on one order, plus GST on the charges that attract it; zero lines are left out."""
        lines = [(c.name, c.amount(side, shares, price)) for c in self.charges]
        taxed = sum(c.amount(side, shares, price) for c in self.charges if c.gst)
        if self.gst and taxed:
            lines.append((f"GST ({self.gst:.0%})", self.gst * taxed))
        return [(name, value) for name, value in lines if value > 0]

    def cost(self, side: Side, shares: float, price: float) -> float:
        return sum(value for _, value in self.itemise(side, shares, price))

    def share_of_value(self, side: Side, value: float, price: float) -> float:
        """Cost of trading `value` worth of a stock priced `price`, as a share of `value`."""
        if value <= 0:
            return 0.0
        return self.cost(side, value / price, price) / value


def load_cost_model(model_id: str, directory: Path = COSTS_DIR) -> CostModel:
    path = directory / f"{model_id}.json"
    if not path.exists():
        raise ValueError(f"Unknown cost model '{model_id}'. Add data/costs/{model_id}.json.")
    return CostModel.model_validate(json.loads(path.read_text(encoding="utf-8")))


@dataclass
class FeeTerms:
    """The per-stock cost term for the score, and what went into it."""

    fees: np.ndarray  # one value per stock, in the score's yearly units
    round_trip: np.ndarray  # cost of buying now and selling later, as a share of the position
    sell: np.ndarray  # cost of selling an existing holding, as a share of the position


def score_fees(
    model: CostModel,
    prices: np.ndarray,
    position_value: float,
    held: np.ndarray | None = None,
    horizon_years: float = 1.0,
) -> FeeTerms:
    """Trading cost per stock for the score, spread over the holding horizon.

    A stock not yet owned costs a round trip (buy now, sell at the end) if chosen. A stock already owned costs nothing
    to keep but a sale if dropped; since the score only counts chosen stocks, that appears as a negative cost
    (a reward for keeping it). Both are linear in the 0/1 choice, so they fit the QUBO's per-stock terms."""
    if horizon_years <= 0 or position_value <= 0:
        raise ValueError("The holding horizon and the amount per stock must both be positive.")
    held = np.zeros(len(prices), dtype=bool) if held is None else np.asarray(held, dtype=bool)
    buy = np.array([model.share_of_value("buy", position_value, p) for p in prices])
    sell = np.array([model.share_of_value("sell", position_value, p) for p in prices])
    round_trip = buy + sell
    fees = np.where(held, -sell, round_trip) / horizon_years
    return FeeTerms(fees=fees, round_trip=round_trip, sell=sell)
