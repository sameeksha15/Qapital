"""The web API on a small made-up market: endpoints, jobs (polling and live stream), caching, limits, cancelling."""

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from qapital.api import service
from qapital.api.limits import LimitReached, Limits, RateLimiter
from qapital.api.main import Config, create_app
from qapital.api.service import DataSource
from qapital.api.storage import Storage

SETTINGS = {"k": 2, "sector_cap": 1, "depth": 1}


def client_for(source: DataSource, **options) -> TestClient:
    config = Config(database_url="sqlite://", source=source, workers=2, **options)
    return TestClient(create_app(config))


@pytest.fixture
def client(source):
    with client_for(source) as test_client:
        yield test_client


def wait(client: TestClient, job_id: str, seconds: float = 120) -> dict:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status = client.get(f"/jobs/{job_id}").json()
        if status["status"] in ("done", "error", "cancelled"):
            return status
        time.sleep(0.1)
    raise AssertionError("the job didn't finish in time")


def test_health_markets_and_stocks(client):
    assert client.get("/health").json()["snapshot"] == "2021-06-30"
    (market,) = client.get("/markets").json()["markets"]
    assert market["id"] == "small" and market["currency"] == "INR" and market["prices_as_of"] == "2021-06-30"
    assert market["risk_free"] == pytest.approx(0.05)
    stocks = {s["ticker"]: s for s in client.get("/markets/small/stocks").json()["stocks"]}
    assert stocks["S0"]["name"] == "Stock 0" and stocks["S0"]["price"] > 0 and stocks["S0"]["volatility"] > 0
    assert stocks["NEW"]["expected_return"] is None and "years of prices" in stocks["NEW"]["excluded"]


def test_friendly_errors(client):
    body = {"market": "mars", "settings": SETTINGS}
    assert client.post("/optimise", json=body).json() == {"detail": "Unknown market 'mars'. Choose one of: small."}
    body = {"market": "small", "tickers": ["S0", "XYZ"], "settings": SETTINGS}
    assert "XYZ" in client.post("/optimise", json=body).json()["detail"]
    body = {"market": "small", "settings": SETTINGS, "as_of": "31/03/2021"}
    response = client.post("/optimise", json=body)
    assert response.status_code == 422 and "YYYY-MM-DD" in response.text
    assert client.get("/jobs/nope").status_code == 404


def test_optimise_end_to_end_then_cached(client):
    body = {
        "market": "small",
        "tickers": [f"S{i}" for i in range(6)],
        "settings": SETTINGS,
        "cash": 200_000,
        "holdings": [{"ticker": "NEW", "shares": 10}],
    }
    response = client.post("/optimise", json=body)
    assert response.status_code == 202
    status = wait(client, response.json()["job_id"])
    assert status["status"] == "done", status
    result = status["result"]
    assert result["optimal"]["best_is_exact"] and result["optimal"]["num_valid"] == 12
    assert {a["sizing"] for a in result["allocations"]} == {"equal", "lowest-risk"}
    equal = result["allocations"][0]
    assert {o["ticker"] for o in equal["orders"] if o["side"] == "sell"} == {"NEW"}  # the old holding is sold
    assert all(o["cost"] > 0 and o["costs"] for o in equal["orders"])
    assert equal["cash_left"] >= 0 and equal["invested"] > 0
    assert result["costs"]["held"] == ["NEW"] and result["estimation"]["method"] == "shrunk-lw"
    assert result["request"]["cash"] == 200_000  # a shared result shows what was asked
    assert {s["ticker"] for s in result["stocks"]} == set(body["tickers"])  # with the estimates it used

    stored = client.get(f"/results/{result['result_id']}").json()
    assert stored["result"]["quantum"] == result["quantum"]

    again = wait(client, client.post("/optimise", json=body).json()["job_id"], seconds=2)
    assert again["cached"] and again["result"]["result_id"] == result["result_id"]


def test_live_stream_ends_with_the_result(client, monkeypatch):
    def fake(source, request, on_progress):
        for step in range(3):
            on_progress("Working", step, 3)
        raise ValueError("Made-up failure for the test.")

    monkeypatch.setattr(service, "optimise", fake)
    job_id = client.post("/optimise", json={"market": "small", "settings": SETTINGS, "cash": 1}).json()["job_id"]
    with client.stream("GET", f"/jobs/{job_id}/events") as stream:
        text = "".join(stream.iter_text())
    events = [line.removeprefix("event: ") for line in text.splitlines() if line.startswith("event: ")]
    assert events[-1] == "error" and set(events[:-1]) <= {"progress"}
    last = [line for line in text.splitlines() if line.startswith("data: ")][-1]
    assert json.loads(last.removeprefix("data: "))["error"] == "Made-up failure for the test."


def test_cancel_and_one_job_at_a_time(client, monkeypatch):
    started = threading.Event()

    def endless(source, request, on_progress):
        started.set()
        while True:
            on_progress("Working", 0, 1)
            time.sleep(0.01)

    monkeypatch.setattr(service, "optimise", endless)
    job_id = client.post("/optimise", json={"market": "small", "settings": SETTINGS, "cash": 2}).json()["job_id"]
    started.wait(5)
    busy = client.post("/optimise", json={"market": "small", "settings": SETTINGS, "cash": 3})
    assert busy.status_code == 429 and "in progress" in busy.json()["detail"]
    assert client.delete(f"/jobs/{job_id}").status_code == 200
    assert wait(client, job_id, seconds=5)["status"] == "cancelled"


def test_hourly_limit(source, monkeypatch):
    def fails(source, request, on_progress):
        raise ValueError("Made-up failure for the test.")

    monkeypatch.setattr(service, "optimise", fails)
    with client_for(source, limits=Limits(runs_per_hour=1)) as limited:
        first = limited.post("/optimise", json={"market": "small", "settings": SETTINGS, "cash": 4}).json()
        wait(limited, first["job_id"], seconds=5)
        second = limited.post("/optimise", json={"market": "small", "settings": SETTINGS, "cash": 5})
        assert second.status_code == 429 and int(second.headers["Retry-After"]) > 0


def test_correlations(client):
    corr = client.get("/markets/small/correlations").json()
    assert corr["sectors"] == sorted(corr["sectors"]) and "NEW" not in corr["tickers"]
    assert all(abs(corr["matrix"][i][i] - 1) < 1e-6 for i in range(len(corr["tickers"])))


def test_backtest(client):
    body = {"market": "small", "settings": SETTINGS, "start": "2019-01-01", "frequency": "yearly", "capital": 1e6}
    status = wait(client, client.post("/backtest", json=body).json()["job_id"])
    assert status["status"] == "done", status
    run = status["backtest"]
    assert [s["name"] for s in run["strategies"]] == [
        "Best 2 stocks, equal money",
        "Best 2 stocks, lowest-risk split",
        "All stocks, equal money",
    ]
    assert len(run["dates"]) == len(run["benchmark"]["values"]) == len(run["strategies"][0]["values"])
    assert [r["date"] for r in run["strategies"][0]["rebalances"]] == ["2019-01-01", "2020-01-01", "2021-01-01"]
    assert any("survivorship" in caveat for caveat in run["caveats"])


def test_hardware_needs_the_admin_key(source):
    body = {"market": "small", "tickers": ["S0", "S2", "S4"], "settings": SETTINGS, "backend": "fake:FakeBrisbane"}
    with client_for(source) as closed:
        assert closed.post("/admin/hardware", json=body).status_code == 403
    with client_for(source, admin_key="secret") as admin:
        assert admin.post("/admin/hardware", json=body, headers={"X-Admin-Key": "wrong"}).status_code == 403


def test_rate_limiter_window_slides():
    now = [0.0]
    limiter = RateLimiter(Limits(backtests_per_hour=2), clock=lambda: now[0])
    limiter.take("me", ["backtests"], 0)
    limiter.take("me", ["backtests"], 0)
    with pytest.raises(LimitReached):
        limiter.take("me", ["backtests"], 0)
    limiter.take("you", ["backtests"], 0)  # other visitors are counted separately
    now[0] = 3601.0
    limiter.take("me", ["backtests"], 0)


def test_storage_finds_the_newest_identical_request():
    storage = Storage("sqlite://")
    storage.save("optimise", "key", "s1", '{"a": 1}', "first")
    time.sleep(0.02)  # a later timestamp
    storage.save("optimise", "key", "s1", '{"a": 2}', "second")
    assert storage.find("key") == ("second", "optimise", '{"a": 2}')
    assert storage.get("first") == ("optimise", '{"a": 1}') and storage.find("other") is None


def test_the_websites_copy_of_the_api_description_is_current():
    from scripts.export_openapi import OUT, openapi_text

    assert OUT.read_text(encoding="utf-8") == openapi_text(), "Run: python -m scripts.export_openapi"
