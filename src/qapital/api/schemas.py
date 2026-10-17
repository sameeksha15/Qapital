"""Join 1: the contract between the React website and the FastAPI backend.
The website mirrors these in web/src/api/contract.js; the static backend serves the same shapes.

Version 2 only adds: markets, live prices and estimates, cash and holdings, whole-share orders with itemised costs,
walk-forward backtests and job kinds. Every new field is optional, so version 1 clients keep working."""

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

from qapital.core.schemas import HardwareCheck, QuantumResult, Settings

Estimator = Literal["historical", "shrunk", "shrunk-lw"]
MARKET_ALIASES = {"india": "nifty50", "us": "sp100"}  # version 1 market names


def _iso_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"'{value}' isn't a date; use the form YYYY-MM-DD, e.g. 2024-03-31.") from None
    return value


IsoDate = Annotated[str, AfterValidator(_iso_date)]


class Market(BaseModel):
    """GET /markets: one stock market the website can optimise over."""

    id: str
    name: str
    country: str
    currency: str
    benchmark: str  # index name
    num_stocks: int  # stocks with usable prices in the snapshot
    snapshot: str  # id of the price snapshot in use
    prices_as_of: str  # last trading day with prices
    risk_free: float | None = None  # latest yearly rate (decimal)
    risk_free_source: str | None = None
    cost_model: str  # name of the trading-cost rate card
    list_source: str
    list_as_of: str


class MarketList(BaseModel):
    markets: list[Market]


class SnapshotInfo(BaseModel):
    id: str
    created_at: str
    start: str
    end: str
    price_field: str


class MarketStatus(BaseModel):
    id: str
    stocks: int  # on the market's list
    usable: int  # with prices good enough to use
    prices_as_of: str
    problems: dict[str, list[str]]  # ticker -> data problems found by the quality checks


class DataStatus(BaseModel):
    """GET /data/status: which price snapshot is in use, and how good its data is."""

    snapshot: SnapshotInfo
    available: list[str]  # every snapshot on this server
    markets: list[MarketStatus]


class Correlations(BaseModel):
    """GET /markets/{id}/correlations: how each pair of stocks moved together, grouped by sector."""

    market: str
    snapshot: str
    window: tuple[str, str]
    tickers: list[str]
    sectors: list[str]
    matrix: list[list[float]]  # matrix[i][j]: correlation of tickers[i] and tickers[j], from -1 to 1


class StockInfo(BaseModel):
    ticker: str
    sector: str
    expected_return: float | None = None  # yearly, over the estimation window
    volatility: float | None = None  # yearly
    name: str | None = None
    price: float | None = None  # last price in the snapshot, in the market's currency
    excluded: str | None = None  # why the stock can't be chosen right now (e.g. too little history)


class StockList(BaseModel):
    """GET /stocks?market=… and GET /markets/{id}/stocks"""

    market: str
    stocks: list[StockInfo]
    estimation_window: tuple[str, str] | None = None
    fee: float | None = None
    currency: str | None = None
    snapshot: str | None = None
    estimator: Estimator | None = None


class Holding(BaseModel):
    ticker: str
    shares: int = Field(ge=0)


class OptimiseRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list, description="Stocks to choose from; empty means the whole market")
    market: str = "nifty50"
    settings: Settings
    cash: float = Field(1_000_000.0, ge=0, description="Money to invest, in the market's currency")
    holdings: list[Holding] = Field(default_factory=list, description="Shares already owned")
    estimator: Estimator = "shrunk-lw"
    window_years: float = Field(3.0, ge=1, le=10, description="Years of past prices used for the estimates")
    horizon_years: float = Field(1.0, gt=0, le=10, description="How long the portfolio is meant to be held")
    as_of: IsoDate | None = Field(None, description="Use only prices up to this date (YYYY-MM-DD); default: latest")


class JobCreated(BaseModel):
    job_id: str


class Progress(BaseModel):
    stage: str
    step: int
    total: int
    elapsed_s: float | None = None


class ReportRow(BaseModel):
    solver: Literal["QAOA", "Brute force", "Simulated annealing", "Relaxation + rounding", "Random guessing"]
    found_best: bool  # picked the best known portfolio of the full list
    score: float  # qapital.core.problem.score on the full problem
    runtime_s: float
    hit_rate: float | None = None  # share of seeded runs that found the best (random methods)
    chosen: list[str] | None = None
    expected_return: float | None = None
    risk: float | None = None
    universe: Literal["full", "shortlist"] | None = None  # what the method could choose from


class Pick(BaseModel):
    solver: str
    risk: float
    ret: float


class Frontier(BaseModel):
    continuous: list[tuple[float, float]]  # (volatility, return)
    discrete: list[tuple[float, float]]
    picks: list[Pick]


class Stats(BaseModel):
    ret: float
    volatility: float
    sharpe: float


class Backtest(BaseModel):
    portfolio: Stats
    index: Stats
    equal_weight_all: Stats


class PruningRow(BaseModel):
    """qapital.core.schemas.PruningPoint as the website receives it:
    lift over random legal guessing at each level of pruning."""

    kept: float
    gates: int
    ideal: float
    noisy: float
    noisy_postselected: float


class Portfolio(BaseModel):
    stocks: list[str]
    score: float
    expected_return: float
    risk: float


class Optimal(BaseModel):
    """What is known about the best portfolio, so every method can be judged against it."""

    best: Portfolio  # best known portfolio of the full list
    best_is_exact: bool  # True when every portfolio of the full list was checked
    best_found_by: str
    shortlist_best: Portfolio | None = None
    num_valid_shortlist: int | None = None  # legal portfolios on the shortlist
    shortlisting_gap: float | None = None  # shortlist best score − best score (0 = nothing lost)
    relaxation_lower_bound: float | None = None  # no portfolio can score below this
    num_valid: int | None = None  # legal portfolios of the full list (counted, even when too many to check)


class Dataset(BaseModel):
    """Where the numbers came from."""

    source: str
    returns: Literal["simple", "log"]  # what the source held; μ and Σ always use simple returns
    estimation_window: tuple[str, str]
    test_window: tuple[str, str] | None = None
    fee: float
    safe_rate: float | None = None
    num_stocks: int
    num_sectors: int


class CostLine(BaseModel):
    name: str
    amount: float


class Order(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    shares: int
    price: float
    value: float
    costs: list[CostLine]  # itemised, from the market's cited rate card
    cost: float


class Allocation(BaseModel):
    """The chosen stocks turned into whole shares for the investor's money and holdings."""

    sizing: Literal["equal", "lowest-risk"]
    weights: dict[str, float]  # target share of the money in each stock
    shares: dict[str, int]  # holdings after trading
    orders: list[Order]
    costs: float  # all trading costs
    cash_left: float
    invested: float  # value of the holdings after trading
    expected_return: float  # yearly, with the target weights
    volatility: float  # yearly, with the target weights
    sector_exposure: dict[str, float]


class Estimation(BaseModel):
    """How the expected returns and risks were estimated."""

    market: str
    snapshot: str
    window: tuple[str, str]  # first and last day of returns used
    days: int
    method: Estimator
    shrinkage: float  # how strongly the returns were pulled together (0 = not at all)
    excluded: dict[str, str]  # ticker -> why it was left out
    currency: str


class CostInfo(BaseModel):
    """How trading costs entered the score."""

    model: str
    currency: str
    as_of: str
    sources: list[str]
    horizon_years: float
    position_value: float  # money per stock the costs were worked out for
    held: list[str]  # stocks already owned (keeping them avoids a sale)


class FullResult(BaseModel):
    quantum: QuantumResult
    report_card: list[ReportRow]
    frontier: Frontier
    backtest: Backtest | None = None
    pruning: list[PruningRow] | None = None
    verdict: str
    optimal: Optimal | None = None
    dataset: Dataset | None = None
    result_id: str | None = None  # GET /results/{result_id} returns this result again
    estimation: Estimation | None = None
    costs: CostInfo | None = None
    allocations: list[Allocation] | None = None
    request: OptimiseRequest | None = None  # what was asked, so a shared result can be shown and re-run
    stocks: list[StockInfo] | None = None  # every stock of the run, with the estimates this run used


class BacktestRequest(BaseModel):
    """POST /backtest: replay the strategy through history, rebalancing with only the data known at the time."""

    market: str = "nifty50"
    tickers: list[str] = Field(default_factory=list, description="Stocks to choose from; empty means the whole market")
    settings: Settings
    start: IsoDate = "2018-01-01"
    end: IsoDate | None = None
    frequency: Literal["monthly", "quarterly", "yearly"] = "quarterly"
    capital: float = Field(1_000_000.0, gt=0)
    estimator: Estimator = "shrunk-lw"
    window_years: float = Field(3.0, ge=1, le=10)
    horizon_years: float = Field(1.0, gt=0, le=10)
    include_quantum: bool = Field(False, description="Also run QAOA at every rebalance (slow)")


class Rebalancing(BaseModel):
    date: str
    chosen: list[str]
    weights: dict[str, float]
    turnover: float  # value traded as a share of the portfolio
    costs: float


class Performance(BaseModel):
    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    drawdown_start: str
    drawdown_bottom: str
    var_95: float
    cvar_95: float
    beta: float | None = None
    tracking_error: float | None = None
    days: int


class StrategyRun(BaseModel):
    name: str
    values: list[float]  # portfolio value on each of BacktestResult.dates
    performance: Performance
    costs: float
    rebalances: list[Rebalancing]


class BacktestResult(BaseModel):
    market: str
    snapshot: str
    currency: str
    start: str
    end: str
    frequency: str
    window_years: float
    method: Estimator
    capital: float
    dates: list[str]
    strategies: list[StrategyRun]
    benchmark: StrategyRun
    caveats: list[str]
    result_id: str | None = None
    request: BacktestRequest | None = None  # what was asked


class JobStatus(BaseModel):
    status: Literal["queued", "running", "done", "error", "cancelled"]
    progress: Progress | None = None
    result: FullResult | None = None
    error: str | None = None
    kind: Literal["optimise", "backtest", "hardware"] = "optimise"
    backtest: BacktestResult | None = None
    hardware: HardwareCheck | None = None
    cached: bool = False  # True when the answer came from an identical earlier request


class HardwareRequest(BaseModel):
    """POST /admin/hardware: run a small tuned circuit on IBM hardware (or a fake chip with "fake:<name>")."""

    market: str = "nifty50"
    tickers: list[str]
    settings: Settings
    backend: str | None = None
    estimator: Estimator = "shrunk-lw"
    window_years: float = Field(3.0, ge=1, le=10)
