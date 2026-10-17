"""Risk and performance of a portfolio's daily value: growth, volatility, Sharpe, Sortino, drawdown, VaR/CVaR, beta.

All yearly figures use 252 trading days. The Sharpe and Sortino ratios use the market's own risk-free rate."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass
class Performance:
    cagr: float  # compound yearly growth
    volatility: float  # yearly standard deviation of daily returns
    sharpe: float  # yearly excess return per unit of volatility
    sortino: float  # yearly excess return per unit of downside deviation
    max_drawdown: float  # worst fall from a previous peak (negative)
    drawdown_start: str  # the peak before the worst fall
    drawdown_bottom: str  # the bottom of the worst fall
    var_95: float  # one-day loss exceeded on 5% of days (positive number)
    cvar_95: float  # average one-day loss on those 5% of days
    beta: float | None  # sensitivity to the benchmark
    tracking_error: float | None  # yearly volatility of the difference from the benchmark
    days: int

    def as_dict(self) -> dict:
        return asdict(self)


def performance(values: pd.Series, risk_free: pd.Series, benchmark: pd.Series | None = None) -> Performance:
    """`values`: daily portfolio value; `risk_free`: yearly rate (decimal) per day; `benchmark`: index level."""
    values = values.dropna()
    if len(values) < 20:
        raise ValueError("At least 20 trading days are needed to measure performance.")
    returns = values.pct_change().dropna()
    years = len(returns) / TRADING_DAYS
    daily_rf = (1 + risk_free.reindex(returns.index).ffill().bfill()) ** (1 / TRADING_DAYS) - 1
    excess = returns - daily_rf
    volatility = float(returns.std() * np.sqrt(TRADING_DAYS))
    downside = float(np.sqrt(np.mean(np.minimum(excess, 0) ** 2)) * np.sqrt(TRADING_DAYS))

    peaks = values.cummax()
    drawdowns = values / peaks - 1
    bottom = drawdowns.idxmin()
    peak = values.loc[:bottom].idxmax()
    cutoff = float(returns.quantile(0.05))

    beta = tracking = None
    if benchmark is not None:
        index_returns = benchmark.reindex(values.index).ffill().pct_change().reindex(returns.index)
        both = pd.concat([returns, index_returns], axis=1).dropna()
        if len(both) > 20:
            beta = float(both.cov().iloc[0, 1] / both.iloc[:, 1].var())
            tracking = float((both.iloc[:, 0] - both.iloc[:, 1]).std() * np.sqrt(TRADING_DAYS))

    return Performance(
        cagr=float((values.iloc[-1] / values.iloc[0]) ** (1 / years) - 1),
        volatility=volatility,
        sharpe=float(excess.mean() * TRADING_DAYS / volatility) if volatility else 0.0,
        sortino=float(excess.mean() * TRADING_DAYS / downside) if downside else 0.0,
        max_drawdown=float(drawdowns.min()),
        drawdown_start=peak.date().isoformat(),
        drawdown_bottom=bottom.date().isoformat(),
        var_95=-cutoff,
        cvar_95=float(-returns[returns <= cutoff].mean()),
        beta=beta,
        tracking_error=tracking,
        days=len(returns),
    )


def sector_exposure(tickers: list[str], weights: np.ndarray, sectors: dict[str, str]) -> dict[str, float]:
    """Share of the money in each sector, largest first."""
    exposure: dict[str, float] = {}
    for ticker, weight in zip(tickers, weights, strict=True):
        exposure[sectors[ticker]] = exposure.get(sectors[ticker], 0.0) + float(weight)
    return dict(sorted(exposure.items(), key=lambda item: -item[1]))


def correlations(sigma: np.ndarray) -> np.ndarray:
    scale = np.sqrt(np.diag(sigma))
    return sigma / np.outer(scale, scale)
