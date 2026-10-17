"""Market data: cached prices → MarketData (spec §5), and the checks every MarketData must pass.

A market file is JSON: {"fee": 0.0012, "index": "^NSEI", "sectors": {"TICKER.NS": "Sector", ...}}."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from qapital.core.schemas import MarketData

TRADING_DAYS = 252
ESTIMATION_START, ESTIMATION_END = "2021-01-01", "2024-12-31"
MIN_RETURNS = 60


def load_market(
    market_file: str | Path, prices_csv: str | Path, start: str = ESTIMATION_START, end: str = ESTIMATION_END
) -> MarketData:
    """Yearly μ and Σ from daily returns between `start` and `end` only, so later prices stay unseen."""
    market = json.loads(Path(market_file).read_text())
    tickers = list(market["sectors"])
    prices = pd.read_csv(prices_csv, index_col=0, parse_dates=True)

    missing = [t for t in tickers if t not in prices.columns]
    if missing:
        raise ValueError(f"No saved prices for {', '.join(missing)}. Run scripts/download_prices.py again.")
    window = prices.loc[start:end, tickers]
    broken = [t for t in tickers if window[t].isna().any() or (window[t] <= 0).any()]
    if broken:
        raise ValueError(
            f"Prices between {start} and {end} have gaps for {', '.join(broken)}. "
            "Remove these stocks or download the prices again."
        )
    returns = window.pct_change().iloc[1:]
    if len(returns) < MIN_RETURNS:
        raise ValueError(
            f"Only {len(returns)} days of prices between {start} and {end}; at least {MIN_RETURNS} are needed."
        )

    return MarketData(
        tickers=tickers,
        sectors=[market["sectors"][t] for t in tickers],
        mu=returns.mean().to_numpy() * TRADING_DAYS,
        sigma=returns.cov().to_numpy() * TRADING_DAYS,
        fees=np.full(len(tickers), float(market["fee"])),
    )


def validate_market_data(data: MarketData) -> MarketData:
    """A copy with float arrays, or a ValueError the website can show."""
    n = len(data.tickers)
    mu, sigma, fees = (np.asarray(values, dtype=float) for values in (data.mu, data.sigma, data.fees))
    if n < 2:
        raise ValueError("Add at least 2 stocks.")
    if len(set(data.tickers)) != n:
        raise ValueError("Each stock can appear only once in the list.")
    if len(data.sectors) != n or mu.shape != (n,) or fees.shape != (n,) or sigma.shape != (n, n):
        raise ValueError("Every stock needs a sector, an expected return, a fee and a row of the covariance matrix.")
    if not (np.isfinite(mu).all() and np.isfinite(sigma).all() and np.isfinite(fees).all()):
        raise ValueError("Some returns, risks or fees are missing. Check the price data for gaps.")
    if not np.allclose(sigma, sigma.T) or (np.diag(sigma) <= 0).any():
        raise ValueError("The covariance matrix must be symmetric, with a positive variance for every stock.")
    return MarketData(list(data.tickers), list(data.sectors), mu, sigma, fees)


def subset(data: MarketData, tickers: list[str]) -> MarketData:
    """The same market restricted to `tickers`, in the order given."""
    missing = [ticker for ticker in tickers if ticker not in data.tickers]
    if missing:
        raise ValueError(f"These stocks aren't in the market data: {', '.join(missing)}.")
    rows = np.array([data.tickers.index(ticker) for ticker in tickers])
    return MarketData(
        tickers=list(tickers),
        sectors=[data.sectors[i] for i in rows],
        mu=data.mu[rows],
        sigma=data.sigma[np.ix_(rows, rows)],
        fees=data.fees[rows],
    )
