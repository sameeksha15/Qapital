"""The website's saved mode: real runs on the current price snapshot, written in exactly the shapes the live API
returns, so the site works (read-only) while the free backend is asleep or waking up.

Writes web/public/saved/:
  markets.json, data-status.json                    what GET /markets and GET /data/status return
  stocks/<market>.json, correlations/<market>.json  GET /markets/<market>/stocks and /correlations
  runs.json                                          the saved runs: title, what was asked, and the result's id
  results/<id>.json                                  what GET /results/<id> returns (a finished JobStatus)
Run from the repo root after each new snapshot (about 15 minutes):
  python -m scripts.build_saved_site"""

import argparse
import json
import shutil
import time
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from qapital.api import service
from qapital.api.main import Config, create_app
from qapital.api.schemas import BacktestRequest, DataStatus, JobStatus, OptimiseRequest, Progress
from qapital.api.service import DataSource
from qapital.core.schemas import Settings
from scripts.paths import WEB_PUBLIC

OUT = WEB_PUBLIC / "saved"
INVESTOR = {"k": 4, "sector_cap": 1, "risk_aversion": 1.0, "seed": 42}


def runs() -> list[dict]:
    """Each saved run: an id (also its result id), a title, a one-line description and the request."""
    return [
        {
            "id": "nifty50-default",
            "title": "NIFTY 50, four stocks",
            "description": "The whole NIFTY 50 list, at most one stock per sector, ₹10 lakh, XY circuit with CVaR.",
            "kind": "optimise",
            "request": OptimiseRequest(market="nifty50", settings=Settings(**INVESTOR), cash=1_000_000),
        },
        {
            "id": "sp100-default",
            "title": "S&P 100, four stocks",
            "description": "The whole S&P 100 list, at most one stock per sector, $100,000, XY circuit with CVaR.",
            "kind": "optimise",
            "request": OptimiseRequest(market="sp100", settings=Settings(**INVESTOR), cash=100_000),
        },
        {
            "id": "nifty50-warm",
            "title": "NIFTY 50, warm-started circuit",
            "description": "The same question with a warm start from the classical relaxation, shown next to the "
            "warm start alone.",
            "kind": "optimise",
            "request": OptimiseRequest(market="nifty50", settings=Settings(**INVESTOR, mixer="warm"), cash=1_000_000),
        },
        {
            "id": "nifty50-noisy",
            "title": "NIFTY 50 on a noisy IBM chip",
            "description": "Ten stocks, run on the noise model of a real IBM chip, with readout mitigation.",
            "kind": "optimise",
            "request": OptimiseRequest(
                market="nifty50",
                tickers=NOISY_TICKERS,
                settings=Settings(**INVESTOR, noisy=True),
                cash=1_000_000,
            ),
        },
        {
            "id": "nifty50-backtest",
            "title": "NIFTY 50 backtest, 2018 to now",
            "description": "Rebalanced every quarter using only the prices known at the time, with real costs.",
            "kind": "backtest",
            "request": BacktestRequest(market="nifty50", settings=Settings(**INVESTOR)),
        },
        {
            "id": "sp100-backtest",
            "title": "S&P 100 backtest, 2018 to now",
            "description": "Rebalanced every quarter using only the prices known at the time, with real costs.",
            "kind": "backtest",
            "request": BacktestRequest(market="sp100", settings=Settings(**INVESTOR), capital=100_000),
        },
    ]


NOISY_TICKERS = [
    "HDFCBANK.NS",
    "INFY.NS",
    "RELIANCE.NS",
    "HINDUNILVR.NS",
    "SUNPHARMA.NS",
    "LT.NS",
    "MARUTI.NS",
    "BHARTIARTL.NS",
    "TITAN.NS",
    "NTPC.NS",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="*", help="rebuild only these run ids (the rest are kept)")
    args = parser.parse_args()
    source = DataSource()
    snapshot = source.snapshot()
    if not args.only and OUT.exists():
        shutil.rmtree(OUT)

    client = _client(source)
    write(OUT / "markets.json", service.markets(source))
    write(OUT / "data-status.json", DataStatus.model_validate(client("/data/status")))
    for market in source.market_ids():
        write(OUT / "stocks" / f"{market}.json", service.stock_list(source, market))
        write(OUT / "correlations" / f"{market}.json", service.correlations(source, market))

    index = []
    for run in runs():
        if not args.only or run["id"] in args.only:
            started = time.perf_counter()
            status = _run(run, source)
            write(OUT / "results" / f"{run['id']}.json", status)
            print(f"{run['id']}: {time.perf_counter() - started:.0f} s", flush=True)
        index.append(
            {
                "id": run["id"],
                "title": run["title"],
                "description": run["description"],
                "kind": run["kind"],
                "market": run["request"].market,
                "request": run["request"].model_dump(mode="json"),
            }
        )
    write(OUT / "runs.json", {"snapshot": snapshot.id, "runs": index})
    print(f"Wrote the saved site for snapshot {snapshot.id} to {OUT}")


def _run(run: dict, source: DataSource) -> JobStatus:
    done = Progress(stage="Done", step=1, total=1)
    if run["kind"] == "optimise":
        result = service.optimise(source, run["request"])
        result.result_id = run["id"]
        return JobStatus(status="done", progress=done, kind="optimise", result=result)
    backtest = service.backtest(source, run["request"])
    backtest.result_id = run["id"]
    return JobStatus(status="done", progress=done, kind="backtest", backtest=backtest)


def _client(source: DataSource) -> Callable[[str], dict]:
    from fastapi.testclient import TestClient

    test_client = TestClient(create_app(Config(database_url="sqlite://", source=source)))
    return lambda path: test_client.get(path).raise_for_status().json()


def write(path: Path, payload: BaseModel | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = payload.model_dump_json() if isinstance(payload, BaseModel) else json.dumps(payload, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
