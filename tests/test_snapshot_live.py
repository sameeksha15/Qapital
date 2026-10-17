"""Checks on the real, latest snapshot (skipped when none has been downloaded: python -m pipeline.ingest)."""

import pytest

from qapital import Settings
from qapital.core.portfolios import every_portfolio
from qapital.data.returns import load_returns
from qapital.data.snapshot import load_snapshot, snapshot_ids
from qapital.data.universe import load_universe
from qapital.finance.estimate import estimate
from scripts.paths import LEGACY_RETURNS

pytestmark = pytest.mark.skipif(not snapshot_ids(), reason="no price snapshot downloaded yet")


@pytest.mark.parametrize("universe_id, at_least", [("nifty50", 45), ("sp100", 90)])
def test_both_markets_estimate_from_the_latest_snapshot(universe_id, at_least):
    result = estimate(load_snapshot(), load_universe(universe_id))
    assert len(result.data.tickers) >= at_least and result.days >= 700
    assert all(result.data.sigma[i, i] > 0 for i in range(len(result.data.tickers)))


@pytest.mark.skipif(not LEGACY_RETURNS.exists(), reason="needs data/legacy/ (not published)")
def test_our_data_reproduces_the_hackathon_answer():
    legacy = load_returns(LEGACY_RETURNS, "log", fee=0.0012)
    settings = Settings(k=4, sector_cap=1, risk_aversion=1.0)
    ours = estimate(
        load_snapshot(),
        load_universe("nifty50"),
        tickers=legacy.tickers,
        as_of="2024-12-31",
        years=4,
        method="historical",
    )
    ours.data.sectors = legacy.sectors  # same sector labels as the hackathon file, so the rule matches
    best = every_portfolio(ours.data, settings).best
    assert sorted(ours.data.tickers[i] for i in best) == ["BEL.NS", "BSE.NS", "MAXHEALTH.NS", "TRENT.NS"]
