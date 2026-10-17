"""Finance: cited trading costs, estimators, sizing into whole shares, risk metrics and the walk-forward backtest."""

import numpy as np
import pandas as pd
import pytest

from qapital import Settings
from qapital.data.quality import check_ticker
from qapital.data.snapshot import load_snapshot, write_snapshot
from qapital.data.universe import Benchmark, RiskFree, Stock, Universe
from qapital.finance.costs import load_cost_model, score_fees
from qapital.finance.estimators import bayes_stein, yearly_moments
from qapital.finance.risk import performance, sector_exposure
from qapital.finance.sizing import equal_weights, lowest_risk_weights, rebalance
from qapital.finance.walkforward import Strategy, rebalance_days, walk_forward
from qapital.strategies import classical_best, everything

INDIA = load_cost_model("india_delivery")
US = load_cost_model("us_equity")


def test_india_costs_match_a_hand_calculation():
    # Rs 1,00,000 delivery buy: STT 100 + NSE 3.07 + SEBI 0.10 + stamp 15 + GST 18% of (3.07 + 0.10)
    assert INDIA.cost("buy", 100, 1000.0) == pytest.approx(100 + 3.07 + 0.10 + 15 + 0.18 * 3.17)
    # the same sale: STT, NSE, SEBI, GST, and the fixed DP charge instead of stamp duty
    assert INDIA.cost("sell", 100, 1000.0) == pytest.approx(100 + 3.07 + 0.10 + 0.18 * 3.17 + 15.34)
    names = [name for name, _ in INDIA.itemise("buy", 100, 1000.0)]
    assert "Stamp duty" in names and "Brokerage" not in names  # zero lines are left out


def test_us_costs_cap_the_finra_fee_and_charge_sales_only():
    assert US.cost("buy", 1000, 50.0) == 0.0
    small = US.cost("sell", 1000, 50.0)  # $50,000 sale: SEC fee + 1000 shares of TAF
    assert small == pytest.approx(50_000 * 0.0000206 + 1000 * 0.000195)
    large = US.cost("sell", 1_000_000, 1.0)  # a million shares: the TAF hits its $9.79 cap
    assert large == pytest.approx(1_000_000 * 0.0000206 + 9.79)


def test_fees_reward_keeping_holdings_and_shrink_with_a_longer_horizon():
    prices = np.array([1000.0, 2000.0, 500.0])
    held = np.array([True, False, False])
    one_year = score_fees(INDIA, prices, 100_000, held, horizon_years=1)
    assert one_year.fees[0] < 0 < one_year.fees[1]  # dropping a holding costs a sale; buying costs a round trip
    assert one_year.fees[1] == pytest.approx(one_year.round_trip[1])
    two_years = score_fees(INDIA, prices, 100_000, held, horizon_years=2)
    assert two_years.fees == pytest.approx(one_year.fees / 2)
    with pytest.raises(ValueError, match="positive"):
        score_fees(INDIA, prices, 0)


def returns_frame(seed=0, days=750, stocks=6):
    rng = np.random.default_rng(seed)
    drift = rng.normal(0.0006, 0.0006, stocks)
    return pd.DataFrame(rng.normal(drift, 0.015, (days, stocks)), columns=[f"S{i}" for i in range(stocks)])


def test_historical_estimate_is_the_plain_sample():
    frame = returns_frame()
    mu, sigma, intensity = yearly_moments(frame, "historical")
    assert mu == pytest.approx(frame.mean().to_numpy() * 252) and intensity == 0
    assert sigma == pytest.approx(frame.cov().to_numpy() * 252)


@pytest.mark.parametrize("method", ["shrunk", "shrunk-lw"])
def test_shrinkage_pulls_returns_together_but_keeps_their_order(method):
    frame = returns_frame(seed=1)
    plain, _, _ = yearly_moments(frame, "historical")
    shrunk, sigma, intensity = yearly_moments(frame, method)
    assert 0 < intensity <= 1 and np.std(shrunk) < np.std(plain)
    assert list(np.argsort(shrunk)) == list(np.argsort(plain))
    assert np.all(np.linalg.eigvalsh(sigma) > 0)


def test_identical_averages_need_no_shrinking():
    mean = np.full(4, 0.001)
    shrunk, intensity = bayes_stein(mean, np.eye(4) * 1e-4, 500)
    assert intensity == 1.0 and shrunk == pytest.approx(mean)


def test_lowest_risk_weights_beat_equal_weights_on_risk():
    sigma = np.cov(returns_frame(seed=2).to_numpy(), rowvar=False)
    weights = lowest_risk_weights(sigma)
    equal = equal_weights(len(sigma))
    assert weights.sum() == pytest.approx(1) and weights.min() >= 0
    assert weights @ sigma @ weights <= equal @ sigma @ equal + 1e-12
    with pytest.raises(ValueError, match="can't add up"):
        lowest_risk_weights(sigma, max_weight=0.1)


def test_rebalance_from_cash_buys_whole_shares_within_budget():
    prices = {"A": 1234.5, "B": 310.0, "C": 87.25}
    result = rebalance(100_000.0, {}, prices, {"A": 0.5, "B": 0.3, "C": 0.2}, INDIA)
    assert all(isinstance(n, int) and n > 0 for n in result.shares.values())
    assert 0 <= result.cash < max(prices.values()) * 1.01  # leftover is less than one more share
    spent = sum(o.value + o.cost for o in result.orders)
    assert spent + result.cash == pytest.approx(100_000.0)
    assert {o.side for o in result.orders} == {"buy"}


def test_rebalance_sells_first_and_pays_for_both_sides():
    prices = {"A": 100.0, "B": 200.0, "C": 50.0}
    result = rebalance(1_000.0, {"A": 100, "B": 10}, prices, {"B": 0.5, "C": 0.5}, INDIA)
    sides = [(o.ticker, o.side) for o in result.orders]
    assert sides[0] == ("A", "sell") and ("C", "buy") in sides
    assert "A" not in result.shares and result.cash >= 0
    before = 1_000 + 100 * 100 + 10 * 200
    assert result.value(prices) + result.costs == pytest.approx(before)
    with pytest.raises(ValueError, match="add up to 100%"):
        rebalance(1_000.0, {}, prices, {"A": 0.5}, INDIA)


def test_performance_of_a_known_path():
    days = pd.bdate_range("2020-01-01", periods=253)
    values = pd.Series(100 * 1.10 ** (np.arange(253) / 252), index=days)  # steady 10% a year
    values.iloc[100:120] *= 0.8  # a 20% dip that recovers
    result = performance(values, pd.Series(0.0, index=days), benchmark=values)
    assert result.max_drawdown == pytest.approx(-0.2, abs=1e-3)
    assert result.cagr == pytest.approx(0.10, abs=1e-3)
    assert result.beta == pytest.approx(1.0) and result.tracking_error == pytest.approx(0.0)
    assert result.cvar_95 >= result.var_95  # the average of the worst days is at least the cut-off


def test_sector_exposure_adds_up():
    exposure = sector_exposure(["A", "B", "C"], np.array([0.5, 0.3, 0.2]), {"A": "X", "B": "Y", "C": "X"})
    assert exposure == {"X": pytest.approx(0.7), "Y": pytest.approx(0.3)}


@pytest.fixture
def small_market(tmp_path):
    days = pd.bdate_range("2015-01-01", "2020-12-31")
    rng = np.random.default_rng(3)
    names = ["^IDX", *[f"S{i}" for i in range(8)]]
    returns = rng.normal(0.0004, 0.012, (len(days), len(names)))
    prices = pd.DataFrame(100 * np.cumprod(1 + returns, axis=0), index=days, columns=names)
    sectors = ["A", "A", "B", "B", "C", "C", "D", "D"]
    universe = Universe(
        id="small",
        name="Small market",
        country="Nowhere",
        currency="INR",
        benchmark=Benchmark(ticker="^IDX", name="Index"),
        risk_free=RiskFree(kind="constant", rate=0.05, source="made up"),
        cost_model="india_delivery",
        list_source="tests",
        list_as_of="2021-01-01",
        stocks=[Stock(ticker=f"S{i}", name=f"S{i}", sector=s) for i, s in enumerate(sectors)],
    )
    quality = {"small": {t: check_ticker(t, prices[t], days) for t in universe.tickers}}
    write_snapshot(prices, [universe], quality, {"prices": "made up"}, tmp_path)
    return load_snapshot("latest", tmp_path), universe, prices


def test_rebalance_days_are_the_first_trading_day_of_each_quarter():
    days = rebalance_days(pd.bdate_range("2019-01-01", "2019-12-31"), "quarterly")
    assert [d.date().isoformat() for d in days] == ["2019-01-01", "2019-04-01", "2019-07-01", "2019-10-01"]


def test_walk_forward_trades_with_costs_and_tracks_the_index(small_market):
    snapshot, universe, prices = small_market
    strategies = [Strategy("best", classical_best()), Strategy("all", everything)]
    result = walk_forward(snapshot, universe, strategies, Settings(k=2, sector_cap=1), start="2019-01-01", capital=1e6)
    best, every = result.strategies
    assert len(best.rebalances) == 8 and best.values.index[0].date().isoformat() == "2019-01-01"
    assert best.values.iloc[0] == pytest.approx(1e6 - best.rebalances[0].costs, rel=1e-3)
    assert all(len(r.chosen) == 2 for r in best.rebalances) and len(every.rebalances[0].chosen) == 8
    assert best.costs > 0 and best.rebalances[0].turnover > 0.9
    index = prices["^IDX"].loc["2019-01-01":]
    assert result.benchmark.values.iloc[-1] == pytest.approx(1e6 * index.iloc[-1] / index.iloc[0])


def test_walk_forward_never_looks_ahead(small_market, tmp_path):
    snapshot, universe, prices = small_market
    settings = Settings(k=2, sector_cap=1)
    before = walk_forward(
        snapshot, universe, [Strategy("best", classical_best())], settings, "2019-01-01", "2019-12-31"
    )
    changed = prices.copy()
    changed.loc["2020-01-01":, "S0"] *= 10  # a huge move after the backtest's end
    quality = {"small": {t: check_ticker(t, changed[t], changed.index) for t in universe.tickers}}
    write_snapshot(changed, [universe], quality, {"prices": "made up"}, tmp_path / "other")
    after = walk_forward(
        load_snapshot("latest", tmp_path / "other"),
        universe,
        [Strategy("best", classical_best())],
        settings,
        "2019-01-01",
        "2019-12-31",
    )
    assert [r.chosen for r in after.strategies[0].rebalances] == [r.chosen for r in before.strategies[0].rebalances]
    assert after.strategies[0].values.to_numpy() == pytest.approx(before.strategies[0].values.to_numpy())
