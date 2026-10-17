"""From chosen stocks to whole shares and an order list.

Weights are either equal (what the score assumes) or the lowest-risk split of the same stocks. Rebalancing sells
first, so the proceeds (after costs) fund the buys; buys must fit the cash including their own costs, and any cash
left over buys extra shares of the stocks furthest below their target."""

import math
from dataclasses import dataclass, field

import cvxpy as cp
import numpy as np

from qapital.finance.costs import CostModel, Side


def equal_weights(count: int) -> np.ndarray:
    return np.full(count, 1.0 / count)


def lowest_risk_weights(sigma: np.ndarray, max_weight: float = 1.0) -> np.ndarray:
    """Long-only weights summing to 1 with the lowest variance (each at most `max_weight`)."""
    n = len(sigma)
    if max_weight * n < 1 - 1e-9:
        raise ValueError(f"With {n} stocks, a cap of {max_weight:.0%} per stock can't add up to 100%.")
    w = cp.Variable(n)
    problem = cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(sigma))), [w >= 0, w <= max_weight, cp.sum(w) == 1])
    problem.solve()
    weights = np.clip(np.asarray(w.value, dtype=float), 0, None)
    return weights / weights.sum()


@dataclass
class Order:
    ticker: str
    side: Side
    shares: int
    price: float
    costs: list[tuple[str, float]] = field(default_factory=list)

    @property
    def value(self) -> float:
        return self.shares * self.price

    @property
    def cost(self) -> float:
        return sum(amount for _, amount in self.costs)


@dataclass
class Rebalance:
    orders: list[Order]
    shares: dict[str, int]  # holdings after trading
    cash: float  # cash left after trading and costs

    @property
    def costs(self) -> float:
        return sum(order.cost for order in self.orders)

    def value(self, prices: dict[str, float]) -> float:
        return self.cash + sum(n * prices[t] for t, n in self.shares.items())


def rebalance(
    cash: float,
    held: dict[str, int],
    prices: dict[str, float],
    targets: dict[str, float],
    model: CostModel,
) -> Rebalance:
    """Trade from `held` (shares) and `cash` towards target weights (ticker -> weight, summing to 1)."""
    if not math.isclose(sum(targets.values()), 1.0, abs_tol=1e-6):
        raise ValueError("Target weights must add up to 100%.")
    missing = [t for t in [*held, *targets] if t not in prices or not prices[t] > 0]
    if missing:
        raise ValueError(f"No current price for: {', '.join(sorted(set(missing)))}.")
    total = cash + sum(n * prices[t] for t, n in held.items())
    wanted = {t: int(w * total // prices[t]) for t, w in targets.items()}
    orders: list[Order] = []
    shares = dict(held)

    for ticker in sorted(held):  # sell what isn't wanted, or the part above target
        surplus = held[ticker] - wanted.get(ticker, 0)
        if surplus > 0:
            order = _order(ticker, "sell", surplus, prices[ticker], model)
            orders.append(order)
            cash += order.value - order.cost
            shares[ticker] -= surplus

    for ticker in sorted(targets, key=lambda t: -targets[t]):  # then buy, as far as the cash goes
        need = wanted[ticker] - shares.get(ticker, 0)
        while need > 0 and _price_with_costs(ticker, need, prices[ticker], model) > cash:
            need -= 1
        if need > 0:
            order = _order(ticker, "buy", need, prices[ticker], model)
            orders.append(order)
            cash -= order.value + order.cost
            shares[ticker] = shares.get(ticker, 0) + need

    cash = _top_up(cash, shares, prices, targets, total, orders, model)
    return Rebalance(orders=orders, shares={t: n for t, n in shares.items() if n > 0}, cash=cash)


def _top_up(cash, shares, prices, targets, total, orders, model) -> float:
    """Spend leftover cash one share at a time on the stock furthest below its target value."""
    while True:
        shortfall = {t: targets[t] * total - shares.get(t, 0) * prices[t] for t in targets}
        affordable = [t for t in shortfall if _price_with_costs(t, 1, prices[t], model) <= cash and shortfall[t] > 0]
        if not affordable:
            return cash
        ticker = max(affordable, key=lambda t: shortfall[t])
        existing = next((o for o in orders if o.ticker == ticker and o.side == "buy"), None)
        before = existing.cost if existing else 0.0
        if existing:
            existing.shares += 1
            existing.costs = model.itemise("buy", existing.shares, existing.price)
        else:
            existing = _order(ticker, "buy", 1, prices[ticker], model)
            orders.append(existing)
        cash -= prices[ticker] + existing.cost - before
        shares[ticker] = shares.get(ticker, 0) + 1


def _order(ticker: str, side: Side, shares: int, price: float, model: CostModel) -> Order:
    return Order(ticker=ticker, side=side, shares=shares, price=price, costs=model.itemise(side, shares, price))


def _price_with_costs(ticker: str, shares: int, price: float, model: CostModel) -> float:
    return shares * price + model.cost("buy", shares, price)
