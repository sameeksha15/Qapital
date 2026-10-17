import json

import numpy as np
import pandas as pd
import pytest

from qapital.core.schemas import MarketData
from qapital.data.market import load_market, validate_market_data
from qapital.data.toy import toy


@pytest.fixture
def files(tmp_path):
    dates = pd.bdate_range("2023-01-02", "2025-06-30")
    rng = np.random.default_rng(0)
    prices = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(dates), 3)), axis=0)),
        index=dates,
        columns=["AAA.NS", "BBB.NS", "^IDX"],
    )
    market = {"fee": 0.002, "index": "^IDX", "sectors": {"AAA.NS": "Banking", "BBB.NS": "IT"}}
    (tmp_path / "market.json").write_text(json.dumps(market))
    prices.to_csv(tmp_path / "prices.csv")
    return tmp_path / "market.json", tmp_path / "prices.csv", prices


def test_load_market_uses_only_the_estimation_window(files):
    market, csv, prices = files
    data = load_market(market, csv)
    daily = prices.loc[:"2024-12-31", ["AAA.NS", "BBB.NS"]].pct_change().iloc[1:]
    assert data.tickers == ["AAA.NS", "BBB.NS"] and data.sectors == ["Banking", "IT"]
    assert np.allclose(data.mu, daily.mean() * 252)
    assert np.allclose(data.sigma, daily.cov() * 252)
    assert np.allclose(data.fees, 0.002)

    prices.loc["2025-01-01":, "AAA.NS"] *= 3  # the future must not matter
    prices.to_csv(csv)
    assert np.allclose(load_market(market, csv).mu, data.mu)


def test_load_market_errors(files, tmp_path):
    market, csv, prices = files
    prices.drop(columns="AAA.NS").to_csv(tmp_path / "missing.csv")
    gaps = prices.copy()
    gaps.loc["2024-03-01":"2024-03-15", "BBB.NS"] = np.nan
    gaps.to_csv(tmp_path / "gaps.csv")

    with pytest.raises(ValueError, match=r"No saved prices for AAA\.NS"):
        load_market(market, tmp_path / "missing.csv")
    with pytest.raises(ValueError, match=r"gaps for BBB\.NS"):
        load_market(market, tmp_path / "gaps.csv")
    with pytest.raises(ValueError, match="at least 60"):
        load_market(market, csv, start="2024-12-01", end="2024-12-31")


def broken(**change):
    data = toy()
    return MarketData(**{**vars(data), **change})


@pytest.mark.parametrize(
    "data, message",
    [
        (
            broken(tickers=["BANK1"], sectors=["Banking"], mu=np.array([0.1]), sigma=np.eye(1), fees=np.zeros(1)),
            "at least 2",
        ),
        (broken(tickers=["BANK1", "BANK1", "TECH", "FMCG"]), "only once"),
        (broken(sectors=["Banking", "IT", "FMCG"]), "needs a sector"),
        (broken(mu=np.array([0.1, np.nan, 0.1, 0.1])), "missing"),
        (broken(sigma=np.triu(toy().sigma)), "symmetric"),
        (broken(sigma=toy().sigma - np.diag([0.04, 0, 0, 0])), "positive variance"),
    ],
)
def test_validate_market_data_errors(data, message):
    with pytest.raises(ValueError, match=message):
        validate_market_data(data)


def test_validate_market_data_converts_lists_to_arrays():
    data = toy()
    cleaned = validate_market_data(
        MarketData(data.tickers, data.sectors, data.mu.tolist(), data.sigma.tolist(), data.fees.tolist())
    )
    assert isinstance(cleaned.sigma, np.ndarray) and cleaned.sigma.dtype == float
