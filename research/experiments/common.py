"""What every experiment shares: the problems it runs on, and how results and settings are saved.

A problem is what the live app would have solved on a given day: estimates from the three years of prices before
that day (Bayes-Stein returns, Ledoit-Wolf risk), real trading costs for the market's typical amount of money, and
the shortlist the circuit gets. Running an experiment on one problem per quarter turns each finding into a mean with
a spread over many real problems, instead of one possibly lucky case."""

import dataclasses
import json
import os
import platform
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import qiskit
import qiskit_aer

from qapital.api.service import DataSource
from qapital.core.portfolios import can_brute_force, every_portfolio
from qapital.core.schemas import MarketData, Settings
from qapital.data.snapshot import Snapshot
from qapital.finance.costs import load_cost_model, score_fees
from qapital.finance.estimate import estimate
from qapital.finance.walkforward import rebalance_days
from qapital.quantum.shortlist import fit_to_simulator
from qapital.quantum.solver import solve
from scripts.paths import RESULTS, ROOT

MARKETS = ("nifty50", "sp100")
MARKET_NAMES = {"nifty50": "NIFTY 50", "sp100": "S&P 100"}
CASH = {"nifty50": 1_000_000.0, "sp100": 100_000.0}  # the website's default amounts
INVESTOR = {"k": 4, "sector_cap": 1, "risk_aversion": 1.0, "seed": 42}
FIRST_DATE = "2019-01-01"  # three years of prices before it, from the 2015 start
WEBSITE = ROOT / "web" / "public" / "research"
Job = dict[str, Any]  # one unit of work for a worker process: plain values only, so it can be sent to it


@dataclasses.dataclass
class Problem:
    market: str
    as_of: str  # last day of prices used
    full: MarketData  # every stock with enough history, costs included
    data: MarketData  # the circuit's shortlist
    shortlist: list[str]
    true_best: list[str] | None  # best portfolio of the full list, when it can be checked exhaustively

    @property
    def best_kept(self) -> bool | None:
        """Whether the shortlist still holds the full list's best portfolio."""
        return None if self.true_best is None else set(self.true_best) <= set(self.shortlist)


class Problems:
    """Builds and remembers problems for one snapshot."""

    def __init__(self, source: DataSource | None = None):
        self.source = source or DataSource()
        self.snapshot: Snapshot = self.source.snapshot()
        self._cache: dict[tuple, Problem] = {}

    def dates(self, market: str, every: int = 1, start: str = FIRST_DATE) -> list[str]:
        """First trading day of each quarter from `start` on; `every` keeps every n-th quarter, counted back from
        the newest, so the most recent quarter is always included."""
        prices = self.snapshot.market_prices(self.source.universe(market))
        days = [d.date().isoformat() for d in rebalance_days(prices.loc[start:].index, "quarterly")]
        if QUICK:  # a dry run: two dates, to check the code end to end in a few minutes
            return [days[0], days[-1]]
        return days[::-1][::every][::-1]

    def latest(self, market: str) -> str:
        return self.snapshot.market_prices(self.source.universe(market)).index.max().date().isoformat()

    def get(self, market: str, as_of: str, size: int, settings: Settings | None = None) -> Problem:
        settings = settings or Settings(**INVESTOR)
        key = (market, as_of, size, settings.k, settings.sector_cap, settings.risk_aversion)
        if key not in self._cache:
            self._cache[key] = self._build(market, as_of, size, settings)
        return self._cache[key]

    def _build(self, market: str, as_of: str, size: int, settings: Settings) -> Problem:
        universe = self.source.universe(market)
        estimated = estimate(self.snapshot, universe, as_of=as_of)
        prices = np.array([estimated.prices[t] for t in estimated.data.tickers])
        model = load_cost_model(universe.cost_model)
        fees = score_fees(model, prices, CASH.get(market, 1_000_000.0) / settings.k).fees
        full = dataclasses.replace(estimated.data, fees=fees)
        data, shortlist = fit_to_simulator(full, settings, size)
        true_best = None
        if can_brute_force(len(full.tickers), settings.k):
            true_best = [full.tickers[i] for i in every_portfolio(full, settings).best]
        return Problem(market, estimated.window[1], full, data, shortlist or list(full.tickers), true_best)


WORKERS = int(os.environ.get("QAPITAL_RESEARCH_WORKERS", "6"))
QUICK = os.environ.get("QAPITAL_RESEARCH_QUICK") == "1"
_problems: Problems | None = None


def problems() -> Problems:
    """This process's problem builder (each worker process makes its own and caches its problems)."""
    global _problems
    if _problems is None:
        _problems = Problems()
    return _problems


def run_parallel(task: Callable[[Job], list[dict]], jobs: list[Job], workers: int = WORKERS) -> pd.DataFrame:
    """Run `task` on every job in separate processes and collect the rows. Each job carries its own seed, so the
    result doesn't depend on which process ran it or in what order."""
    os.environ.setdefault("OMP_NUM_THREADS", "2")  # several simulators at once: don't let each take every core
    rows: list[dict] = []
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(task, job): job for job in jobs}
        for done, future in enumerate(as_completed(futures), 1):
            rows.extend(future.result())
            elapsed = time.perf_counter() - started
            left = elapsed / done * (len(jobs) - done)
            print(f"  {done}/{len(jobs)} jobs · {elapsed / 60:.1f} min · about {left / 60:.0f} min left", flush=True)
    return pd.DataFrame(rows)


def circuit_row(problem: Problem, settings: Settings) -> dict:
    """One ideal-simulator run of the circuit on the problem's shortlist, graded against that shortlist's best
    (brute force) and, where it can be checked, against the full list's best."""
    started = time.perf_counter()
    result = solve(problem.data, settings)
    warm = result.warm_start_alone
    return {
        "market": problem.market,
        "as_of": problem.as_of,
        "stocks": len(problem.shortlist),
        "mixer": settings.mixer,
        "depth": settings.depth,
        "pairs_kept": settings.pairs_kept,
        "cvar_alpha": settings.cvar_alpha,
        "optimiser": settings.optimiser,
        "seed": settings.seed,
        "lift": result.lift_over_random,
        "p_best": result.p_optimal,
        "legal": result.feasible_rate,
        "closeness": result.approx_ratio,
        "found_best": result.p_optimal > 0,  # sampled the shortlist's best at least once
        "found_true_best": None if problem.true_best is None else set(result.chosen) == set(problem.true_best),
        "best_kept": problem.best_kept,
        "gates": result.two_qubit_gates,
        "circuit_depth": result.circuit_depth,
        "qubits": result.num_qubits,
        "tuning_steps": len(result.convergence),
        "warm_alone_lift": warm.lift_over_random if warm else None,
        "warm_alone_p_best": warm.p_optimal if warm else None,
        "chosen": " + ".join(result.chosen),
        "seconds": time.perf_counter() - started,
    }


def run_info(experiment: str, problems: Problems, started: datetime, **settings) -> dict:
    return {
        "experiment": experiment,
        "snapshot": problems.snapshot.id,
        "estimates": "trailing 3 years of daily prices before each date; Bayes-Stein returns, Ledoit-Wolf risk",
        "costs": "each market's rate card, for its default amount of money split over k stocks, held one year",
        "cash": CASH,
        "investor": INVESTOR,
        **settings,
        "qiskit": qiskit.__version__,
        "qiskit_aer": qiskit_aer.__version__,
        "python": platform.python_version(),
        "started": started.isoformat(timespec="seconds"),
        "minutes": round((datetime.now() - started).total_seconds() / 60, 1),
    }


def save(name: str, runs: pd.DataFrame, info: dict, website: dict | None = None) -> None:
    """Every run as CSV and the settings as JSON in research/results/<name>/; the website's summary, if any, in
    web/public/research/<name>.json."""
    if QUICK:  # dry runs never replace real results
        name, website = f"{name}-quick", None
    folder = RESULTS / name
    folder.mkdir(parents=True, exist_ok=True)
    runs.to_csv(folder / "runs.csv", index=False)
    (folder / "run_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print("wrote", folder)
    if website is not None:
        WEBSITE.mkdir(parents=True, exist_ok=True)
        path = WEBSITE / f"{name}.json"
        payload = _no_nan({"run_info": info, **website})  # browsers reject NaN in JSON: missing values become null
        path.write_text(json.dumps(payload, separators=(",", ":"), default=_plain, allow_nan=False), encoding="utf-8")
        print("wrote", path)


def spread(values: pd.Series) -> dict:
    """Mean, lowest and highest, for the website's error bars."""
    return {"mean": float(values.mean()), "min": float(values.min()), "max": float(values.max()), "n": int(values.size)}


def _no_nan(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _no_nan(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_no_nan(item) for item in value]
    if isinstance(value, float | np.floating) and np.isnan(value):
        return None
    return value


def _plain(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Can't write {type(value).__name__}")
