"""What the API does for each request, without any web code: from a market, the investor's money and settings to a
full result (quantum run, classical baselines, whole-share orders with costs), a walk-forward backtest, or a hardware
check. Long steps report progress through `on_progress(stage, step, total)`, which may raise to cancel the run."""

import dataclasses
import time
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from qapital.api.schemas import (
    MARKET_ALIASES,
    Allocation,
    BacktestRequest,
    BacktestResult,
    Correlations,
    CostInfo,
    CostLine,
    Dataset,
    Estimation,
    FullResult,
    HardwareRequest,
    Market,
    MarketList,
    OptimiseRequest,
    Order,
    Performance,
    PruningRow,
    Rebalancing,
    StockInfo,
    StockList,
    StrategyRun,
)
from qapital.classical.report import run_classical
from qapital.config import SNAPSHOTS_DIR, UNIVERSES_DIR
from qapital.core.schemas import HardwareCheck, MarketData
from qapital.data.snapshot import Snapshot, load_snapshot, snapshot_ids
from qapital.data.universe import Universe, load_universe, universe_ids
from qapital.finance.costs import CostModel, load_cost_model, score_fees
from qapital.finance.estimate import Estimate, estimate
from qapital.finance.estimators import Method
from qapital.finance.risk import correlations as risk_correlations
from qapital.finance.risk import sector_exposure
from qapital.finance.sizing import equal_weights, lowest_risk_weights, rebalance
from qapital.finance.walkforward import Strategy, StrategyResult, walk_forward
from qapital.quantum.solver import SHOTS, hardware_check, pruning_study, solve
from qapital.report import frontier, optimal_block, report_card, verdict
from qapital.strategies import classical_best, everything, quantum

ProgressFn = Callable[[str, int, int], None]
DEFAULT_CASH = 1_000_000.0
CAVEATS = [
    "The stock lists are today's index members, so companies that left the index earlier are missing "
    "(survivorship bias): past results look better than an investor at the time could have done.",
    "Every past trade is charged with today's rate card.",
    "Prices are adjusted for splits and dividends; taxes on gains are not included.",
]


def _quiet(stage: str, step: int, total: int) -> None:
    pass


def _without_done(report: ProgressFn) -> ProgressFn:
    """The engine says "Done" when its own part ends; a full run still has steps after that."""

    def forward(stage: str, step: int, total: int) -> None:
        if stage != "Done":
            report(stage, step, total)

    return forward


@dataclasses.dataclass(frozen=True)
class DataSource:
    """Where the stock lists and price snapshots are read from (folders, so tests can use their own)."""

    universes_dir: Path = UNIVERSES_DIR
    snapshots_dir: Path = SNAPSHOTS_DIR

    def snapshot(self) -> Snapshot:
        """The newest snapshot; reloaded only when the nightly job has added a newer one."""
        ids = snapshot_ids(self.snapshots_dir)
        if not ids:
            raise ValueError("No price data is available yet. Run: python -m pipeline.ingest")
        return _load_snapshot(ids[-1], self.snapshots_dir)

    def market_ids(self) -> list[str]:
        return universe_ids(self.universes_dir)

    def universe(self, market: str, tickers: list[str] | None = None) -> Universe:
        """The market's stock list, narrowed to `tickers` when given."""
        market = MARKET_ALIASES.get(market, market)
        if market not in self.market_ids():
            raise ValueError(f"Unknown market '{market}'. Choose one of: {', '.join(self.market_ids())}.")
        universe = load_universe(market, self.universes_dir)
        if not tickers:
            return universe
        unknown = [t for t in tickers if t not in universe.sectors]
        if unknown:
            raise ValueError(f"These stocks aren't in {universe.name}: {', '.join(unknown)}.")
        if len(set(tickers)) != len(tickers):
            raise ValueError("A stock appears twice in the list.")
        stocks = {stock.ticker: stock for stock in universe.stocks}
        return universe.model_copy(update={"stocks": [stocks[t] for t in tickers]})


@lru_cache(maxsize=2)
def _load_snapshot(snapshot_id: str, directory: Path) -> Snapshot:
    return load_snapshot(snapshot_id, directory)


def markets(source: DataSource) -> MarketList:
    snapshot = source.snapshot()
    found = []
    for market in source.market_ids():
        universe = load_universe(market, source.universes_dir)
        if universe.id not in snapshot.manifest["universes"]:
            continue
        prices = snapshot.market_prices(universe)
        model = load_cost_model(universe.cost_model)
        found.append(
            Market(
                id=universe.id,
                name=universe.name,
                country=universe.country,
                currency=universe.currency,
                benchmark=universe.benchmark.name,
                num_stocks=prices.shape[1],
                snapshot=snapshot.id,
                prices_as_of=prices.index.max().date().isoformat(),
                risk_free=float(snapshot.risk_free(universe).iloc[-1]),
                risk_free_source=universe.risk_free.source,
                cost_model=model.name,
                list_source=universe.list_source,
                list_as_of=universe.list_as_of,
            )
        )
    return MarketList(markets=found)


_STOCK_LISTS: dict[tuple, StockList] = {}


def stock_list(source: DataSource, market: str, estimator: Method = "shrunk-lw", years: float = 3.0) -> StockList:
    snapshot, universe = source.snapshot(), source.universe(market)
    key = (snapshot.id, universe.id, source, estimator, years)
    if key not in _STOCK_LISTS:
        if len(_STOCK_LISTS) > 16:
            _STOCK_LISTS.clear()
        _STOCK_LISTS[key] = _stock_list(snapshot, universe, estimator, years)
    return _STOCK_LISTS[key]


def _stock_list(snapshot: Snapshot, universe: Universe, estimator: Method, years: float) -> StockList:
    estimated = estimate(snapshot, universe, years=years, method=estimator)
    data, last = estimated.data, _last_prices(snapshot, universe, None)
    stocks = []
    for stock in universe.stocks:
        info = StockInfo(ticker=stock.ticker, sector=stock.sector, name=stock.name, price=last.get(stock.ticker))
        if stock.ticker in data.tickers:
            i = data.tickers.index(stock.ticker)
            info.expected_return, info.volatility = float(data.mu[i]), float(np.sqrt(data.sigma[i, i]))
        else:
            info.excluded = estimated.excluded.get(stock.ticker, "no usable prices")
        stocks.append(info)
    return StockList(
        market=universe.id,
        stocks=stocks,
        estimation_window=estimated.window,
        currency=universe.currency,
        snapshot=snapshot.id,
        estimator=estimator,
    )


def correlations(source: DataSource, market: str, years: float = 3.0) -> Correlations:
    """How each pair of stocks moved together over the trailing window (from the Ledoit-Wolf covariance)."""
    snapshot, universe = source.snapshot(), source.universe(market)
    estimated = estimate(snapshot, universe, years=years)
    data = estimated.data
    order = sorted(range(len(data.tickers)), key=lambda i: (data.sectors[i], data.tickers[i]))
    matrix = risk_correlations(data.sigma)[np.ix_(order, order)]
    return Correlations(
        market=universe.id,
        snapshot=snapshot.id,
        window=estimated.window,
        tickers=[data.tickers[i] for i in order],
        sectors=[data.sectors[i] for i in order],
        matrix=[[round(float(v), 4) for v in row] for row in matrix],
    )


def optimise(source: DataSource, request: OptimiseRequest, on_progress: ProgressFn | None = None) -> FullResult:
    report = on_progress or _quiet
    settings = request.settings
    snapshot, universe = source.snapshot(), source.universe(request.market, request.tickers)
    report("Estimating returns and risk", 0, 1)
    estimated = estimate(snapshot, universe, None, request.as_of, request.window_years, request.estimator)
    held = {h.ticker: h.shares for h in request.holdings if h.shares > 0}
    prices = _prices_for(source, snapshot, universe, request.as_of, estimated, held)
    model = load_cost_model(universe.cost_model)
    total = request.cash + sum(n * prices[t] for t, n in held.items())
    if total <= 0:
        raise ValueError("Enter some cash or shares you already own, so there is money to invest.")
    data, costs, round_trip = _with_costs(estimated, model, prices, held, total / settings.k, request.horizon_years)

    started = time.perf_counter()
    result = solve(data, settings, _without_done(report))
    seconds = time.perf_counter() - started
    report("Classical baselines", 0, 1)
    classical = run_classical(data, settings, result.shortlist or data.tickers, SHOTS)
    pruning = None
    if settings.run_pruning_study:
        pruning = [PruningRow(**point.model_dump()) for point in pruning_study(data, settings, _without_done(report))]

    optimal = optimal_block(classical, result, data, settings)
    rows = report_card(result, seconds, classical, optimal, data, settings)
    report("Turning the portfolio into orders", 0, 1)
    allocations = [
        _allocation(sizing, optimal.best.stocks, data, request.cash, held, prices, model, universe)
        for sizing in ("equal", "lowest-risk")
    ]
    return FullResult(
        quantum=result,
        report_card=rows,
        frontier=frontier(classical, rows),
        pruning=pruning,
        verdict=verdict(result, rows, optimal, classical, len(data.tickers)),
        optimal=optimal,
        dataset=Dataset(
            source=f"price snapshot {snapshot.id}",
            returns="simple",
            estimation_window=estimated.window,
            fee=float(np.mean(round_trip)),
            safe_rate=float(snapshot.risk_free(universe).loc[: estimated.window[1]].iloc[-1]),
            num_stocks=len(data.tickers),
            num_sectors=len(set(data.sectors)),
        ),
        estimation=Estimation(
            market=universe.id,
            snapshot=snapshot.id,
            window=estimated.window,
            days=estimated.days,
            method=estimated.method,
            shrinkage=estimated.shrinkage,
            excluded=estimated.excluded,
            currency=universe.currency,
        ),
        costs=costs,
        allocations=allocations,
        request=request,
        stocks=_stock_infos(data, universe, prices),
    )


def backtest(source: DataSource, request: BacktestRequest, on_progress: ProgressFn | None = None) -> BacktestResult:
    report = on_progress or _quiet
    snapshot, universe = source.snapshot(), source.universe(request.market, request.tickers)
    settings, k = request.settings, request.settings.k
    strategies = [
        Strategy(f"Best {k} stocks, equal money", classical_best(settings.seed)),
        Strategy(f"Best {k} stocks, lowest-risk split", classical_best(settings.seed), "lowest-risk"),
        Strategy("All stocks, equal money", everything),
    ]
    if request.include_quantum:
        strategies.insert(1, Strategy(f"QAOA {k} stocks, equal money", quantum()))
    run = walk_forward(
        snapshot,
        universe,
        strategies,
        settings,
        start=request.start,
        end=request.end,
        capital=request.capital,
        frequency=request.frequency,
        window_years=request.window_years,
        method=request.estimator,
        horizon_years=request.horizon_years,
        on_progress=lambda step, total: report("Rebalancing through history", step, total),
    )
    caveats = list(CAVEATS)
    if universe.risk_free.kind == "constant":
        caveats.append(f"The risk-free rate is today's ({universe.risk_free.source}) for every past day.")
    return BacktestResult(
        market=universe.id,
        snapshot=snapshot.id,
        currency=universe.currency,
        start=run.start,
        end=run.end,
        frequency=run.frequency,
        window_years=run.window_years,
        method=run.method,
        capital=run.capital,
        dates=[day.date().isoformat() for day in run.benchmark.values.index],
        strategies=[_strategy_run(strategy) for strategy in run.strategies],
        benchmark=_strategy_run(run.benchmark),
        caveats=caveats,
        request=request,
    )


def hardware(source: DataSource, request: HardwareRequest, on_progress: ProgressFn | None = None) -> HardwareCheck:
    snapshot, universe = source.snapshot(), source.universe(request.market, request.tickers)
    estimated = estimate(snapshot, universe, None, None, request.window_years, request.estimator)
    prices = _prices_for(source, snapshot, universe, None, estimated, {})
    model = load_cost_model(universe.cost_model)
    data, _, _ = _with_costs(estimated, model, prices, {}, DEFAULT_CASH / request.settings.k, 1.0)
    return hardware_check(data, request.settings, request.backend, _without_done(on_progress or _quiet))


def _last_prices(snapshot: Snapshot, universe: Universe, as_of: str | None) -> dict[str, float]:
    prices = snapshot.market_prices(universe)
    if as_of:
        prices = prices.loc[: pd.Timestamp(as_of)]
    last = prices.ffill().iloc[-1].dropna()
    return {ticker: float(price) for ticker, price in last.items()}


def _prices_for(
    source: DataSource,
    snapshot: Snapshot,
    universe: Universe,
    as_of: str | None,
    estimated: Estimate,
    held: dict[str, int],
) -> dict[str, float]:
    """Prices to trade at: the estimate's last day for the chosen list, the last known price for anything held."""
    full = _with_held(source, universe, held) if held else universe
    prices = {**_last_prices(snapshot, full, as_of), **estimated.prices}
    missing = [t for t in held if t not in prices]
    if missing:
        raise ValueError(f"There is no price for these holdings: {', '.join(missing)}.")
    return prices


def _with_held(source: DataSource, universe: Universe, held: dict[str, int]) -> Universe:
    """The stock list plus any holdings outside it, so they can be priced (and sold)."""
    market = source.universe(universe.id)
    known = {stock.ticker: stock for stock in market.stocks}
    unknown = [t for t in held if t not in known]
    if unknown:
        raise ValueError(f"These holdings aren't in {market.name}: {', '.join(unknown)}.")
    extra = [known[t] for t in held if t not in universe.sectors]
    return universe.model_copy(update={"stocks": [*universe.stocks, *extra]})


def _price_array(data: MarketData, prices: dict[str, float]) -> np.ndarray:
    return np.array([prices[t] for t in data.tickers])


def _with_costs(
    estimated: Estimate,
    model: CostModel,
    prices: dict[str, float],
    held: dict[str, int],
    position: float,
    horizon_years: float,
) -> tuple[MarketData, CostInfo, np.ndarray]:
    data = estimated.data
    owned = np.array([t in held for t in data.tickers])
    terms = score_fees(model, _price_array(data, prices), position, owned, horizon_years)
    info = CostInfo(
        model=model.name,
        currency=model.currency,
        as_of=model.as_of,
        sources=model.sources,
        horizon_years=horizon_years,
        position_value=position,
        held=sorted(held),
    )
    return dataclasses.replace(data, fees=terms.fees), info, terms.round_trip


def _allocation(
    sizing: str,
    chosen: list[str],
    data: MarketData,
    cash: float,
    held: dict[str, int],
    prices: dict[str, float],
    model: CostModel,
    universe: Universe,
) -> Allocation:
    rows = [data.tickers.index(t) for t in chosen]
    sigma = data.sigma[np.ix_(rows, rows)]
    weights = equal_weights(len(chosen)) if sizing == "equal" or len(chosen) == 1 else lowest_risk_weights(sigma)
    trade = {t: prices[t] for t in {*held, *chosen}}
    result = rebalance(cash, held, trade, dict(zip(chosen, map(float, weights), strict=True)), model)
    return Allocation(
        sizing="equal" if sizing == "equal" else "lowest-risk",
        weights=dict(zip(chosen, map(float, weights), strict=True)),
        shares=result.shares,
        orders=[
            Order(
                ticker=order.ticker,
                side=order.side,
                shares=order.shares,
                price=order.price,
                value=order.value,
                costs=[CostLine(name=name, amount=amount) for name, amount in order.costs],
                cost=order.cost,
            )
            for order in result.orders
        ],
        costs=result.costs,
        cash_left=result.cash,
        invested=result.value(trade) - result.cash,
        expected_return=float(weights @ data.mu[rows]),
        volatility=float(np.sqrt(weights @ sigma @ weights)),
        sector_exposure=sector_exposure(chosen, weights, universe.sectors),
    )


def _stock_infos(data: MarketData, universe: Universe, prices: dict[str, float]) -> list[StockInfo]:
    names = {stock.ticker: stock.name for stock in universe.stocks}
    return [
        StockInfo(
            ticker=ticker,
            sector=data.sectors[i],
            name=names.get(ticker),
            price=prices.get(ticker),
            expected_return=float(data.mu[i]),
            volatility=float(np.sqrt(data.sigma[i, i])),
        )
        for i, ticker in enumerate(data.tickers)
    ]


def _strategy_run(result: StrategyResult) -> StrategyRun:
    return StrategyRun(
        name=result.name,
        values=[round(float(v), 2) for v in result.values],
        performance=Performance(**result.performance.as_dict()),
        costs=result.costs,
        rebalances=[Rebalancing(**dataclasses.asdict(r)) for r in result.rebalances],
    )
