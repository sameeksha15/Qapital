"""The Qapital web API. Run locally with:  uvicorn qapital.api.main:create_app --factory --reload
(interactive docs at http://localhost:8000/docs)

Settings come from environment variables:
  DATABASE_URL           where results are kept (default: SQLite file data/qapital.db; Postgres URLs work too)
  QAPITAL_CORS_ORIGINS   websites allowed to call the API, comma-separated (default: the local dev server)
  QAPITAL_WORKERS        runs processed at the same time (default 2)
  QAPITAL_TRUST_PROXY    "1" behind a proxy that sets X-Forwarded-For (as Caddy does in deploy/oracle)
  QAPITAL_ADMIN_KEY      enables POST /admin/hardware for requests carrying it in X-Admin-Key
  QAPITAL_SNAPSHOT_REPO  "owner/repo" whose "data" release holds the nightly price snapshots; fetched at start-up
                         and every few hours (unset: use whatever is already in data/snapshots/)
  QISKIT_IBM_TOKEN       IBM Quantum token for real hardware runs (never logged or returned)"""

import asyncio
import hashlib
import json
import logging
import os
import secrets
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from qapital.api import service
from qapital.api.jobs import Job, JobManager, Kind, Work
from qapital.api.limits import LimitReached, Limits, RateLimiter
from qapital.api.schemas import (
    BacktestRequest,
    BacktestResult,
    Correlations,
    DataStatus,
    FullResult,
    HardwareRequest,
    JobCreated,
    JobStatus,
    MarketList,
    MarketStatus,
    OptimiseRequest,
    SnapshotInfo,
    StockList,
)
from qapital.api.service import DataSource
from qapital.api.storage import Storage
from qapital.config import DATA_DIR
from qapital.core.schemas import HardwareCheck
from qapital.data.remote import sync_snapshot
from qapital.data.snapshot import snapshot_ids
from qapital.finance.estimators import Method

log = logging.getLogger("qapital.api")
KEEP_ALIVE_SECONDS = 15.0
POLL_SECONDS = 0.25
NOT_FOUND = "This run isn't known: runs are kept for an hour. A finished result stays available at /results/{id}."


def _version() -> str:
    try:
        return version("qapital")
    except PackageNotFoundError:
        return "dev"


@dataclass
class Config:
    database_url: str = f"sqlite:///{(DATA_DIR / 'qapital.db').as_posix()}"
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    workers: int = 2
    trust_proxy: bool = False
    admin_key: str | None = None
    limits: Limits = field(default_factory=Limits)
    source: DataSource = field(default_factory=DataSource)
    snapshot_repo: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        config = cls()
        config.database_url = os.environ.get("DATABASE_URL") or config.database_url
        origins = os.environ.get("QAPITAL_CORS_ORIGINS")
        if origins:
            config.cors_origins = [origin.strip() for origin in origins.split(",") if origin.strip()]
        config.workers = int(os.environ.get("QAPITAL_WORKERS") or config.workers)
        config.trust_proxy = os.environ.get("QAPITAL_TRUST_PROXY") == "1"
        config.admin_key = os.environ.get("QAPITAL_ADMIN_KEY") or None
        config.snapshot_repo = os.environ.get("QAPITAL_SNAPSHOT_REPO") or None
        return config


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config.from_env()
    source = config.source
    storage = Storage(config.database_url)
    jobs = JobManager(storage, config.workers)
    limiter = RateLimiter(config.limits)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        stop = threading.Event()
        if config.snapshot_repo:
            if not snapshot_ids(source.snapshots_dir):  # nothing to serve yet: wait for the first download
                await asyncio.to_thread(_sync, config.snapshot_repo, source)
            threading.Thread(target=_keep_synced, args=(config.snapshot_repo, source, stop), daemon=True).start()
        yield
        stop.set()
        jobs.shutdown()

    app = FastAPI(
        title="Qapital API",
        version=_version(),
        description="Quantum-assisted portfolio optimisation (QAOA), benchmarked honestly against classical methods.",
        lifespan=lifespan,
    )
    app.state.jobs, app.state.storage, app.state.limiter = jobs, storage, limiter
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Admin-Key"],
    )

    @app.exception_handler(ValueError)
    async def friendly_error(request: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.exception_handler(LimitReached)
    async def limit_reached(request: Request, error: LimitReached) -> JSONResponse:
        return JSONResponse(
            status_code=429, content={"detail": str(error)}, headers={"Retry-After": str(error.retry_after)}
        )

    def visitor(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if config.trust_proxy and forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def start(kind: Kind, who: str, payload: BaseModel, buckets: list[str], work: Work) -> JobCreated:
        """Answer from the stored results when the same request was run on the same data; otherwise queue it."""
        snapshot = source.snapshot().id
        key = _request_key(kind, payload, snapshot)
        found = storage.find(key)
        if found is not None:
            _, stored_kind, stored = found
            return JobCreated(job_id=jobs.answered(kind, who, _load(stored_kind, stored)).id)
        limiter.take(who, buckets, jobs.active(who))
        return JobCreated(job_id=jobs.submit(kind, who, key, snapshot, work).id)

    def find_job(job_id: str) -> Job:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        return job

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"name": "Qapital API", "version": _version(), "docs": "/docs"}

    @app.get("/health")
    def health() -> dict:
        ids = snapshot_ids(source.snapshots_dir)
        return {"status": "ok", "version": _version(), "snapshot": ids[-1] if ids else None}

    @app.get("/markets", response_model=MarketList)
    def markets() -> MarketList:
        return service.markets(source)

    @app.get("/markets/{market}/stocks", response_model=StockList)
    def market_stocks(market: str, estimator: Method = "shrunk-lw", window_years: float = 3.0) -> StockList:
        if not 1 <= window_years <= 10:
            raise ValueError("The estimation window must be between 1 and 10 years.")
        return service.stock_list(source, market, estimator, window_years)

    @app.get("/markets/{market}/correlations", response_model=Correlations)
    def market_correlations(market: str, window_years: float = 3.0) -> Correlations:
        if not 1 <= window_years <= 10:
            raise ValueError("The estimation window must be between 1 and 10 years.")
        return service.correlations(source, market, window_years)

    @app.get("/stocks", response_model=StockList, summary="Version 1 alias of /markets/{market}/stocks")
    def stocks(market: str = "nifty50") -> StockList:
        return service.stock_list(source, market)

    @app.post("/optimise", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED)
    def optimise(body: OptimiseRequest, request: Request) -> JobCreated:
        universe = source.universe(body.market, body.tickers)  # unknown market or stock: answer now, not later
        if body.settings.k > len(universe.stocks):
            raise ValueError(f"You asked for {body.settings.k} stocks but the list only has {len(universe.stocks)}.")
        heavy = body.settings.noisy or body.settings.run_pruning_study
        buckets = ["runs", "heavy"] if heavy else ["runs"]
        return start("optimise", visitor(request), body, buckets, partial(service.optimise, source, body))

    @app.post("/backtest", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED)
    def backtest(body: BacktestRequest, request: Request) -> JobCreated:
        source.universe(body.market, body.tickers)
        buckets = ["backtests", "heavy"] if body.include_quantum else ["backtests"]
        return start("backtest", visitor(request), body, buckets, partial(service.backtest, source, body))

    @app.get("/jobs/{job_id}", response_model=JobStatus)
    def job_status(job_id: str) -> JobStatus:
        return find_job(job_id).as_status()

    @app.delete("/jobs/{job_id}", response_model=JobStatus)
    def cancel_job(job_id: str) -> JobStatus:
        find_job(job_id)
        job = jobs.cancel(job_id)
        assert job is not None
        return job.as_status()

    @app.get("/jobs/{job_id}/events", response_class=EventSourceResponse)
    async def job_events(job_id: str) -> AsyncIterator[ServerSentEvent]:
        """Live progress: a `progress` event on every change, then one `done`, `error` or `cancelled` event."""
        job = find_job(job_id)
        seen, quiet = -1, 0.0
        while True:
            if job.version != seen:
                seen, quiet = job.version, 0.0
                event = job.status if job.over else "progress"
                yield ServerSentEvent(data=job.as_status().model_dump(mode="json"), event=event, id=str(seen))
                if job.over:
                    return
            elif quiet >= KEEP_ALIVE_SECONDS:
                quiet = 0.0
                yield ServerSentEvent(comment="still working")
            await asyncio.sleep(POLL_SECONDS)
            quiet += POLL_SECONDS

    @app.get("/results/{result_id}", response_model=JobStatus)
    def stored_result(result_id: str) -> JobStatus:
        found = storage.get(result_id)
        if found is None:
            raise HTTPException(status_code=404, detail="No result with this id.")
        kind, payload = found
        job = Job(id=result_id, kind=kind, visitor="", status="done", result=_load(kind, payload))  # type: ignore[arg-type]
        return job.as_status()

    @app.get("/data/status", response_model=DataStatus)
    def data_status() -> DataStatus:
        snapshot = source.snapshot()
        manifest = snapshot.manifest
        found = []
        for market in source.market_ids():
            universe = source.universe(market)
            if universe.id not in manifest["universes"]:
                continue
            quality = snapshot.quality(universe)
            notes = {
                ticker: [*info.get("problems", []), *(f"warning: {w}" for w in info.get("warnings", []))]
                for ticker, info in quality.items()
            }
            found.append(
                MarketStatus(
                    id=universe.id,
                    stocks=len(universe.stocks),
                    usable=sum(1 for info in quality.values() if info.get("usable")),
                    prices_as_of=snapshot.market_prices(universe).index.max().date().isoformat(),
                    problems={ticker: lines for ticker, lines in notes.items() if lines},
                )
            )
        return DataStatus(
            snapshot=SnapshotInfo(
                id=snapshot.id,
                created_at=manifest["created_at"],
                start=manifest["start"],
                end=manifest["end"],
                price_field=manifest["price_field"],
            ),
            available=snapshot_ids(source.snapshots_dir),
            markets=found,
        )

    @app.post("/admin/hardware", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED)
    def run_hardware(
        body: HardwareRequest, request: Request, x_admin_key: str | None = Header(default=None)
    ) -> JobCreated:
        if not config.admin_key:
            raise HTTPException(status_code=403, detail="Hardware runs are switched off on this server.")
        if not x_admin_key or not secrets.compare_digest(x_admin_key, config.admin_key):
            raise HTTPException(status_code=403, detail="This needs the admin key.")
        source.universe(body.market, body.tickers)
        work: Work = partial(service.hardware, source, body)
        snapshot = source.snapshot().id
        return JobCreated(job_id=jobs.submit("hardware", visitor(request), "", snapshot, work).id)

    return app


SYNC_EVERY_S = 6 * 3600


def _sync(repo: str, source: DataSource) -> None:
    try:
        sync_snapshot(repo, source.snapshots_dir)
    except Exception:  # the next try comes later; meanwhile the last good snapshot keeps being served
        log.exception("Couldn't download the newest price snapshot from %s", repo)


def _keep_synced(repo: str, source: DataSource, stop: threading.Event) -> None:
    while not stop.wait(SYNC_EVERY_S):
        _sync(repo, source)


def _request_key(kind: str, payload: BaseModel, snapshot: str) -> str:
    text = json.dumps({"kind": kind, "snapshot": snapshot, "request": payload.model_dump(mode="json")}, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


LOADERS: dict[str, Callable[[str], BaseModel]] = {
    "optimise": FullResult.model_validate_json,
    "backtest": BacktestResult.model_validate_json,
    "hardware": HardwareCheck.model_validate_json,
}


def _load(kind: str, payload: str) -> BaseModel:
    return LOADERS[kind](payload)
