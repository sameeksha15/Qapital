"""How a portfolio did on the hidden test period (spec §8). Equal money in each stock, rebalanced daily,
as in reference/classical_prototype/finance.py."""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def yearly_stats(daily: pd.Series, safe_rate: float) -> dict:
    """Yearly return (compounded), yearly volatility and Sharpe ratio of a series of daily simple returns."""
    daily = daily.dropna()
    yearly_return = float((1 + daily).prod() ** (TRADING_DAYS / len(daily)) - 1)
    volatility = float(daily.std() * np.sqrt(TRADING_DAYS))
    return {"ret": yearly_return, "volatility": volatility, "sharpe": (yearly_return - safe_rate) / volatility}


def backtest(test_returns: pd.DataFrame, chosen: list[str], index_returns: pd.Series, safe_rate: float) -> dict:
    """`test_returns`: daily simple returns in the test window, one column per ticker."""
    return {
        "portfolio": yearly_stats(test_returns[chosen].mean(axis=1), safe_rate),
        "index": yearly_stats(index_returns, safe_rate),
        "equal_weight_all": yearly_stats(test_returns.mean(axis=1), safe_rate),
    }
