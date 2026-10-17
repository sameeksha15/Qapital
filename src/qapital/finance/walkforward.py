"""Walk-forward backtest: re-optimise on a schedule using only the data available on each date, trade with real
costs, and hold the whole shares in between.

On each rebalance day: estimate returns and risk from the trailing window ending that day, price in the trading
costs at the portfolio's current size (holdings are rewarded for staying), let each strategy pick its stocks, size
them, and trade. The index is tracked alongside. The stock list is today's (survivorship bias: stocks that left the
index before today are not in it), which flatters every strategy equally."""

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from qapital.core.schemas import MarketData, Settings
from qapital.data.market import subset
from qapital.data.snapshot import Snapshot
from qapital.data.universe import Universe
from qapital.finance.costs import load_cost_model, score_fees
from qapital.finance.estimate import estimate
from qapital.finance.estimators import DEFAULT_METHOD, Method
from qapital.finance.risk import Performance, performance
from qapital.finance.sizing import equal_weights, lowest_risk_weights, rebalance

Selector = Callable[[MarketData, Settings], list[str]]
Frequency = Literal["monthly", "quarterly", "yearly"]
PERIOD_STARTS = {"monthly": "MS", "quarterly": "QS", "yearly": "YS"}


@dataclass
class Strategy:
    name: str
    select: Selector
    sizing: Literal["equal", "lowest-risk"] = "equal"


@dataclass
class Rebalancing:
    date: str
    chosen: list[str]
    weights: dict[str, float]
    turnover: float  # value traded as a share of the portfolio
    costs: float


@dataclass
class StrategyResult:
    name: str
    values: pd.Series
    performance: Performance
    rebalances: list[Rebalancing] = field(default_factory=list)

    @property
    def costs(self) -> float:
        return sum(r.costs for r in self.rebalances)


@dataclass
class WalkForward:
    universe: str
    snapshot: str
    start: str
    end: str
    frequency: Frequency
    window_years: float
    method: Method
    capital: float
    strategies: list[StrategyResult]
    benchmark: StrategyResult


def rebalance_days(calendar: pd.DatetimeIndex, frequency: Frequency) -> list[pd.Timestamp]:
    """The first trading day on or after the start of each period."""
    starts = pd.date_range(calendar[0], calendar[-1], freq=PERIOD_STARTS[frequency])
    days = {calendar[calendar.searchsorted(start)] for start in starts if calendar.searchsorted(start) < len(calendar)}
    return sorted(days | {calendar[0]})


def walk_forward(
    snapshot: Snapshot,
    universe: Universe,
    strategies: list[Strategy],
    settings: Settings,
    start: str = "2018-01-01",
    end: str | None = None,
    capital: float = 1_000_000.0,
    frequency: Frequency = "quarterly",
    window_years: float = 3.0,
    method: Method = DEFAULT_METHOD,
    horizon_years: float = 1.0,
    on_progress: Callable[[int, int], None] | None = None,
) -> WalkForward:
    model = load_cost_model(universe.cost_model)
    prices = snapshot.market_prices(universe).ffill()  # trade and value at the last known price
    calendar = prices.loc[start:end].index
    if len(calendar) < 60:
        raise ValueError("The backtest period needs at least 60 trading days.")
    days = rebalance_days(calendar, frequency)
    cash = dict.fromkeys((s.name for s in strategies), capital)
    held: dict[str, dict[str, int]] = {s.name: {} for s in strategies}
    states: dict[str, list[tuple[pd.Timestamp, float, dict[str, int]]]] = {s.name: [] for s in strategies}
    records: dict[str, list[Rebalancing]] = {s.name: [] for s in strategies}

    for number, day in enumerate(days):
        if on_progress:
            on_progress(number, len(days))
        today = prices.loc[day]
        estimated = estimate(snapshot, universe, as_of=day.date().isoformat(), years=window_years, method=method)
        tradable = [t for t in estimated.data.tickers if pd.notna(today.get(t))]
        base = subset(estimated.data, tradable)
        for strategy in strategies:
            name = strategy.name
            worth = cash[name] + sum(n * today[t] for t, n in held[name].items())
            owned = np.array([t in held[name] for t in base.tickers])
            terms = score_fees(model, today[base.tickers].to_numpy(), worth / settings.k, owned, horizon_years)
            chosen = strategy.select(dataclasses.replace(base, fees=terms.fees), settings)
            weights = _weights(strategy, base, chosen)
            trade_prices = {t: float(today[t]) for t in {*held[name], *chosen}}
            result = rebalance(cash[name], held[name], trade_prices, dict(zip(chosen, weights, strict=True)), model)
            traded = sum(order.value for order in result.orders)
            records[name].append(
                Rebalancing(
                    date=day.date().isoformat(),
                    chosen=chosen,
                    weights=dict(zip(chosen, map(float, weights), strict=True)),
                    turnover=traded / worth,
                    costs=result.costs,
                )
            )
            cash[name], held[name] = result.cash, result.shares
            states[name].append((day, result.cash, dict(result.shares)))

    risk_free = snapshot.risk_free(universe)
    index = snapshot.prices[universe.benchmark.ticker].reindex(calendar).ffill()
    results = []
    for strategy in strategies:
        series = _values(prices.loc[calendar], states[strategy.name])
        results.append(
            StrategyResult(strategy.name, series, performance(series, risk_free, index), records[strategy.name])
        )
    index_values = capital * index / index.iloc[0]
    benchmark = StrategyResult(universe.benchmark.name, index_values, performance(index_values, risk_free, index))
    return WalkForward(
        universe=universe.id,
        snapshot=snapshot.id,
        start=calendar[0].date().isoformat(),
        end=calendar[-1].date().isoformat(),
        frequency=frequency,
        window_years=window_years,
        method=method,
        capital=capital,
        strategies=results,
        benchmark=benchmark,
    )


def _weights(strategy: Strategy, data: MarketData, chosen: list[str]) -> np.ndarray:
    if strategy.sizing == "equal" or len(chosen) == 1:
        return equal_weights(len(chosen))
    rows = [data.tickers.index(t) for t in chosen]
    return lowest_risk_weights(data.sigma[np.ix_(rows, rows)])


def _values(prices: pd.DataFrame, states: list[tuple[pd.Timestamp, float, dict[str, int]]]) -> pd.Series:
    """Daily value: from each rebalance until the next, the cash plus the shares at that day's prices."""
    values = pd.Series(np.nan, index=prices.index)
    for number, (day, cash, shares) in enumerate(states):
        first = prices.index.get_loc(day)
        last = prices.index.get_loc(states[number + 1][0]) if number + 1 < len(states) else len(prices)
        tickers = list(shares)
        held = prices.iloc[first:last][tickers].to_numpy() @ np.array([shares[t] for t in tickers], dtype=float)
        values.iloc[first:last] = cash + (held if tickers else 0.0)
    return values
