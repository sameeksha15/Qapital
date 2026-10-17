"""Pruning vs shrinkage, walk-forward: each quarter since 2019 that has a full year after it, in both markets, the best
portfolio is chosen with five versions of the risk model, then judged on the following year, which the estimate never
saw.

The versions: the plain sample covariance of the past three years; Ledoit-Wolf shrinkage (the app's default); and the
sample covariance keeping only its strongest 75 / 50 / 25% of stock pairs (what pruning does to the circuit's score).
Expected returns are the same in every version (Bayes-Stein), so only the risk model changes. For each version: the
portfolio's next-year return, volatility and Sharpe ratio (equal money, no rebalancing), and how far the covariance
was from the one the next year actually showed (relative Frobenius error, over every stock).
Run from the repo root (about 5 minutes):  python -m research.experiments.covariance"""

import dataclasses
import itertools
from datetime import datetime

import numpy as np
import pandas as pd

from qapital.core.schemas import Settings
from qapital.finance.estimators import TRADING_DAYS
from qapital.strategies import classical_best
from research.experiments.common import (
    INVESTOR,
    MARKETS,
    Job,
    problems,
    run_info,
    run_parallel,
    save,
    spread,
)

VERSIONS = ("sample", "ledoit-wolf", "pruned 75%", "pruned 50%", "pruned 25%")
WINDOW_YEARS = 3
SIZE = 16  # unused by the classical choice; the problem builder needs one


def pruned(sigma: np.ndarray, fraction: float) -> np.ndarray:
    """Keep the diagonal and the strongest `fraction` of pairs by |covariance|; zero the rest
    (as qapital.quantum.hamiltonian keeps pairs for the circuit)."""
    pairs = sorted(itertools.combinations(range(len(sigma)), 2), key=lambda pair: -abs(sigma[pair]))
    kept = np.diag(np.diag(sigma))
    for i, j in pairs[: round(fraction * len(pairs))]:
        kept[i, j] = kept[j, i] = sigma[i, j]
    return kept


def relative_error(estimate: np.ndarray, truth: np.ndarray) -> float:
    return float(np.linalg.norm(estimate - truth) / np.linalg.norm(truth))


def jobs() -> list[Job]:
    found = []
    for market in MARKETS:
        latest = pd.Timestamp(problems().latest(market))
        for day in problems().dates(market):
            if pd.Timestamp(day) + pd.DateOffset(years=1) <= latest:
                found.append({"market": market, "as_of": day})
    return found


def task(job: Job) -> list[dict]:
    p = problems()
    problem = p.get(job["market"], job["as_of"], SIZE)
    full = problem.full
    universe = p.source.universe(job["market"])
    prices = p.snapshot.market_prices(universe)[full.tickers]
    returns = prices.pct_change(fill_method=None)
    end = pd.Timestamp(problem.as_of)
    past = returns.loc[(returns.index > end - pd.DateOffset(years=WINDOW_YEARS)) & (returns.index <= end)].dropna()
    future = returns.loc[returns.index > end].iloc[:TRADING_DAYS].dropna()
    sample = np.cov(past.to_numpy(), rowvar=False) * TRADING_DAYS
    realised = np.cov(future.to_numpy(), rowvar=False) * TRADING_DAYS
    risk_free = float(p.snapshot.risk_free(universe).loc[future.index].mean())
    versions = {
        "sample": sample,
        "ledoit-wolf": full.sigma,
        **{f"pruned {round(100 * f)}%": pruned(sample, f) for f in (0.75, 0.5, 0.25)},
    }
    settings = Settings(**INVESTOR)
    rows = []
    for name, sigma in versions.items():
        chosen = classical_best(settings.seed)(dataclasses.replace(full, sigma=sigma), settings)
        daily = future[chosen].mean(axis=1)
        growth = float((1 + daily).prod() - 1)
        volatility = float(daily.std() * np.sqrt(TRADING_DAYS))
        rows.append(
            {
                "market": problem.market,
                "as_of": problem.as_of,
                "version": name,
                "stocks": len(full.tickers),
                "chosen": " + ".join(chosen),
                "next_year_return": growth,
                "next_year_volatility": volatility,
                "next_year_sharpe": (growth - risk_free) / volatility if volatility else 0.0,
                "covariance_error": relative_error(sigma, realised),
                "exhaustive": problem.true_best is not None,
            }
        )
    return rows


def summarise(runs: pd.DataFrame) -> dict:
    measures = ("next_year_return", "next_year_volatility", "next_year_sharpe", "covariance_error")
    rows = [
        {"version": version, **{m: spread(group[m]) for m in measures}}
        for version, group in runs.groupby("version", sort=False)
    ]
    sample = runs[runs["version"] == "sample"].set_index(["market", "as_of"])
    vs_sample = {}
    for version in VERSIONS[1:]:
        other = runs[runs["version"] == version].set_index(["market", "as_of"])
        vs_sample[version] = {
            "lower_error": int((other["covariance_error"] < sample["covariance_error"]).sum()),
            "lower_volatility": int((other["next_year_volatility"] < sample["next_year_volatility"] - 1e-12).sum()),
            "same_portfolio": int((other["chosen"] == sample["chosen"]).sum()),
            "problems": len(other),
        }
    return {"rows": rows, "vs_sample": vs_sample, "problems": int(runs.groupby(["market", "as_of"]).ngroups)}


def main() -> None:
    started = datetime.now()
    runs = run_parallel(task, jobs())
    runs = runs.sort_values(
        ["market", "as_of", "version"], key=lambda c: c.map(VERSIONS.index) if c.name == "version" else c
    )
    summary = {"all": summarise(runs), **{m: summarise(runs[runs["market"] == m]) for m in MARKETS}}
    info = run_info(
        "Pruning vs shrinkage, walk-forward",
        problems(),
        started,
        versions=VERSIONS,
        window_years=WINDOW_YEARS,
        choice="the best portfolio by the shared score: brute force when the list allows (NIFTY 50), "
        "otherwise simulated annealing (S&P 100)",
        judged_on="the 252 trading days after each date; equal money, no rebalancing",
        dates="first trading day of every quarter from 2019 with a full year after it",
    )
    save("covariance", runs, info, {"summary": summary})


if __name__ == "__main__":
    main()
