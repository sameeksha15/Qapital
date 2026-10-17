"""Shared test data: a small made-up market (6 stocks in 3 sectors, plus one listed recently), saved as a real
stock list and price snapshot in a temporary folder, so the API and the research code can be tested end to end."""

import numpy as np
import pandas as pd
import pytest

from qapital.api.service import DataSource
from qapital.data.quality import check_ticker
from qapital.data.snapshot import write_snapshot
from qapital.data.universe import Benchmark, RiskFree, Stock, Universe

SECTORS = ["A", "A", "B", "B", "C", "C"]


@pytest.fixture(scope="module")
def source(tmp_path_factory) -> DataSource:
    folder = tmp_path_factory.mktemp("data")
    days = pd.bdate_range("2015-01-01", "2021-06-30")
    rng = np.random.default_rng(7)
    names = ["^IDX", *[f"S{i}" for i in range(len(SECTORS))], "NEW"]
    returns = rng.normal(0.0004, 0.012, (len(days), len(names)))
    prices = pd.DataFrame(100 * np.cumprod(1 + returns, axis=0), index=days, columns=names)
    prices.loc[:"2020-12-31", "NEW"] = np.nan  # listed recently: too little history to estimate
    universe = Universe(
        id="small",
        name="Small market",
        country="Nowhere",
        currency="INR",
        benchmark=Benchmark(ticker="^IDX", name="Small index"),
        risk_free=RiskFree(kind="constant", rate=0.05, source="made up"),
        cost_model="india_delivery",
        list_source="tests",
        list_as_of="2021-07-01",
        stocks=[
            *[Stock(ticker=f"S{i}", name=f"Stock {i}", sector=s) for i, s in enumerate(SECTORS)],
            Stock(ticker="NEW", name="New listing", sector="D"),
        ],
    )
    (folder / "universes").mkdir()
    (folder / "universes" / "small.json").write_text(universe.model_dump_json(), encoding="utf-8")
    quality = {"small": {t: check_ticker(t, prices[t], days) for t in universe.tickers}}
    write_snapshot(prices, [universe], quality, {"prices": "made up"}, folder / "snapshots")
    return DataSource(universes_dir=folder / "universes", snapshots_dir=folder / "snapshots")
