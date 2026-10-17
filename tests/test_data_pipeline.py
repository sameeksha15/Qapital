"""The data layer: stock lists, price quality checks, snapshots and trailing-window estimates (on made-up prices)."""

import json

import numpy as np
import pandas as pd
import pytest

from qapital.config import UNIVERSES_DIR
from qapital.data.quality import check_ticker, clean
from qapital.data.snapshot import load_snapshot, write_snapshot
from qapital.data.universe import Benchmark, RiskFree, Stock, Universe, load_universe, universe_ids
from qapital.finance.estimate import estimate

DAYS = pd.bdate_range("2019-01-01", "2023-12-29")


def walk(seed: int, start: float = 100.0) -> np.ndarray:
    returns = np.random.default_rng(seed).normal(0.0005, 0.015, len(DAYS))
    return start * np.cumprod(1 + returns)


def universe(stocks: dict[str, str], risk_free: RiskFree | None = None) -> Universe:
    return Universe(
        id="test",
        name="Test market",
        country="Nowhere",
        currency="XXX",
        benchmark=Benchmark(ticker="^IDX", name="Test index"),
        risk_free=risk_free or RiskFree(kind="constant", rate=0.05, source="made up"),
        cost_model="india_delivery",
        list_source="tests",
        list_as_of="2024-01-01",
        stocks=[Stock(ticker=t, name=t, sector=s) for t, s in stocks.items()],
    )


@pytest.fixture
def market(tmp_path):
    prices = pd.DataFrame({t: walk(i) for i, t in enumerate(["^IDX", "AAA", "BBB", "CCC", "DDD"])}, index=DAYS)
    prices.loc[:"2022-06-30", "DDD"] = np.nan  # listed mid-2022
    prices.loc["2023-12-20":, "CCC"] = np.nan  # stopped trading
    u = universe({"AAA": "Tech", "BBB": "Banks", "CCC": "Tech", "DDD": "Energy"})
    quality = {u.id: {t: check_ticker(t, prices[t], DAYS) for t in u.tickers}}
    write_snapshot(prices, [u], quality, {"prices": "made up"}, tmp_path)
    return load_snapshot("latest", tmp_path), u, prices


def test_clean_series_has_no_problems_or_warnings():
    q = check_ticker("AAA", pd.Series(walk(1), index=DAYS), DAYS)
    assert q.usable and not q.warnings and q.coverage == 1.0 and q.first == "2019-01-01"


@pytest.mark.parametrize(
    "damage, expect_problem, expect_warning",
    [
        (lambda s: s.where(s.index < "2023-12-01"), "no price since", None),
        (lambda s: s.mask(s.index == "2021-03-03", 0.0), "zero or negative", None),
        (lambda s: s.mask((s.index >= "2021-03-01") & (s.index < "2021-03-15")), None, "without a price"),
        (lambda s: s.mask((s.index >= "2021-03-01") & (s.index < "2021-03-20"), 50.0), None, "unchanged"),
        (lambda s: s.mask(s.index >= "2021-03-03", s * 2.5), None, "unadjusted split"),
        (lambda s: s.where(s.index >= "2020-06-01"), None, "listed later"),
    ],
)
def test_planted_problems_are_found(damage, expect_problem, expect_warning):
    q = check_ticker("AAA", damage(pd.Series(walk(2), index=DAYS)), DAYS)
    if expect_problem:
        assert not q.usable and any(expect_problem in p for p in q.problems)
    if expect_warning:
        assert q.usable and any(expect_warning in w for w in q.warnings)


def test_filled_gaps_are_not_mistaken_for_a_frozen_price():
    series = pd.Series(walk(3), index=DAYS)
    series.loc["2021-03-01":"2021-03-03"] = np.nan  # a 3-day gap gets filled, but the feed isn't frozen
    assert check_ticker("AAA", series, DAYS).frozen_days < 3


def test_clean_fills_short_gaps_only_and_never_outside_the_trading_life():
    raw = pd.DataFrame({"A": walk(4)}, index=DAYS)
    raw.iloc[:10, 0] = np.nan  # not listed yet
    raw.iloc[100:102, 0] = np.nan  # short gap: filled
    raw.iloc[200:206, 0] = np.nan  # long gap: the first 3 days are filled, the rest stay empty
    raw.iloc[-5:, 0] = np.nan  # stopped trading: never filled
    cleaned = clean(raw, DAYS)["A"]
    assert cleaned.iloc[:10].isna().all() and cleaned.iloc[100:102].notna().all()
    assert cleaned.iloc[200:203].notna().all() and cleaned.iloc[203:206].isna().all()
    assert cleaned.iloc[-5:].isna().all()


def test_snapshot_round_trip_and_tamper_check(market, tmp_path):
    snapshot, _, prices = market
    assert snapshot.id == "2023-12-29"
    assert snapshot.prices.shape == prices.shape
    assert snapshot.manifest["universes"]["test"]["usable"] == 3  # CCC stopped trading
    (snapshot.path / "prices.parquet").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="damaged"):
        load_snapshot("latest", tmp_path)


def test_missing_snapshot_gives_a_friendly_error(tmp_path):
    with pytest.raises(ValueError, match="No price snapshots"):
        load_snapshot("latest", tmp_path)


def test_estimate_uses_only_the_trailing_window_and_explains_exclusions(market):
    snapshot, u, prices = market
    result = estimate(snapshot, u, as_of="2023-06-30", years=3, method="historical")
    assert result.data.tickers == ["AAA", "BBB"]
    assert "only 1.0 of 3 years" in result.excluded["DDD"] and "no price since" in result.excluded["CCC"]
    expected = prices.loc["2020-07-01":"2023-06-30", ["AAA", "BBB"]].pct_change().dropna()
    assert result.data.mu == pytest.approx(expected.mean().to_numpy() * 252)
    assert result.data.sigma == pytest.approx(expected.cov().to_numpy() * 252)
    assert result.window[1] == "2023-06-30" and result.data.sectors == ["Tech", "Banks"]


def test_estimate_never_looks_ahead(market, tmp_path):
    snapshot, u, prices = market
    before = estimate(snapshot, u, as_of="2022-12-30", years=2, method="historical")
    changed = prices.copy()
    changed.loc["2023-01-02":, ["AAA", "BBB"]] *= 3  # wild prices after the date
    quality = {u.id: {t: check_ticker(t, changed[t], DAYS) for t in u.tickers}}
    write_snapshot(changed, [u], quality, {"prices": "made up"}, tmp_path / "other")
    after = estimate(load_snapshot("latest", tmp_path / "other"), u, as_of="2022-12-30", years=2, method="historical")
    assert after.data.mu == pytest.approx(before.data.mu) and after.data.sigma == pytest.approx(before.data.sigma)


def test_estimate_rejects_unknown_stocks(market):
    snapshot, u, _ = market
    with pytest.raises(ValueError, match="aren't in Test market"):
        estimate(snapshot, u, tickers=["AAA", "ZZZ"])


def test_risk_free_constant_and_series(market):
    snapshot, u, prices = market
    assert snapshot.risk_free(u).eq(0.05).all()
    series_rule = u.model_copy(update={"risk_free": RiskFree(kind="series", ticker="AAA", source="made up")})
    assert snapshot.risk_free(series_rule).iloc[-1] == pytest.approx(prices["AAA"].iloc[-1] / 100)


def test_universe_rules():
    twice = universe({"AAA": "Tech"}).model_dump() | {"stocks": [{"ticker": "A", "name": "A", "sector": "x"}] * 2}
    with pytest.raises(ValueError, match="appears twice"):
        Universe.model_validate(twice)
    with pytest.raises(ValueError, match="needs a rate"):
        RiskFree(kind="constant", source="x")
    with pytest.raises(ValueError, match="Unknown market"):
        load_universe("atlantis")


def test_committed_universe_files_are_valid():
    ids = universe_ids()
    assert {"nifty50", "sp100"} <= set(ids)
    for universe_id in ids:
        u = load_universe(universe_id)
        raw = json.loads((UNIVERSES_DIR / f"{universe_id}.json").read_text(encoding="utf-8"))
        assert u.id == universe_id == raw["id"] and len(u.stocks) >= 40
        assert all(s.sector for s in u.stocks) and len(set(u.sectors.values())) >= 10
