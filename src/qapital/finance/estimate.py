"""From a snapshot to the engine's inputs: yearly expected returns and covariance over a trailing window.

Only prices up to `as_of` are used (no look-ahead), so the same function serves live runs and walk-forward backtests.
Stocks without enough history in the window are left out, each with a reason the website can show. Trading costs
are not included here (fees are zero); qapital.finance.costs adds them for a given amount of money."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from qapital.core.schemas import MarketData
from qapital.data.snapshot import Snapshot
from qapital.data.universe import Universe
from qapital.finance.estimators import DEFAULT_METHOD, TRADING_DAYS, Method, yearly_moments

DEFAULT_YEARS = 3
MIN_COVERAGE = 0.95  # share of the window's trading days a stock must have a return on


@dataclass
class Estimate:
    data: MarketData
    snapshot: str
    universe: str
    window: tuple[str, str]  # first and last day of returns used
    days: int  # trading days of returns used
    excluded: dict[str, str]  # ticker -> why it was left out
    method: Method  # how returns and risk were estimated
    shrinkage: float  # how strongly the returns were pulled together (0 = not at all)
    prices: dict[str, float]  # last price of each kept stock on the window's last day


def estimate(
    snapshot: Snapshot,
    universe: Universe,
    tickers: list[str] | None = None,
    as_of: str | None = None,
    years: float = DEFAULT_YEARS,
    method: Method = DEFAULT_METHOD,
) -> Estimate:
    wanted = tickers or universe.tickers
    unknown = [t for t in wanted if t not in universe.sectors]
    if unknown:
        raise ValueError(f"These stocks aren't in {universe.name}: {', '.join(unknown)}.")

    prices = snapshot.market_prices(universe)
    end = pd.Timestamp(as_of) if as_of else prices.index.max()
    start = end - pd.DateOffset(months=round(12 * years))
    window = prices.loc[(prices.index > start) & (prices.index <= end)]
    if len(window) < 60:
        raise ValueError(f"Only {len(window)} trading days of prices before {end.date()}; pick a later date.")
    returns = window.pct_change(fill_method=None).iloc[1:]

    excluded = {}
    quality = snapshot.quality(universe)
    for ticker in wanted:
        if ticker not in returns:
            excluded[ticker] = "; ".join(quality.get(ticker, {}).get("problems", [])) or "no prices in the snapshot"
            continue
        coverage = float(returns[ticker].notna().mean())
        if coverage < MIN_COVERAGE:
            have = coverage * len(returns) / TRADING_DAYS
            excluded[ticker] = f"only {have:.1f} of {years:g} years of prices before {end.date()}"
    kept = [t for t in wanted if t not in excluded]
    if len(kept) < 2:
        raise ValueError("Fewer than 2 of the chosen stocks have enough price history in this window.")

    complete = returns[kept].dropna()
    mu, sigma, shrinkage = yearly_moments(complete, method)
    data = MarketData(
        tickers=kept,
        sectors=[universe.sectors[t] for t in kept],
        mu=mu,
        sigma=sigma,
        fees=np.zeros(len(kept)),
    )
    return Estimate(
        data=data,
        snapshot=snapshot.id,
        universe=universe.id,
        window=(complete.index.min().date().isoformat(), complete.index.max().date().isoformat()),
        days=len(complete),
        excluded=excluded,
        method=method,
        shrinkage=shrinkage,
        prices={t: float(window[t].loc[: complete.index.max()].dropna().iloc[-1]) for t in kept},
    )
