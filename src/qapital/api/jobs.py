"""Long runs in background threads: each job reports progress, can be cancelled, and stores its result when done.

Jobs live in memory for an hour after they finish; their results are stored for good (qapital.api.storage), so
GET /results/{id} keeps working after a restart. Cancelling stops a running job at its next progress report."""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from qapital.api.schemas import BacktestResult, FullResult, JobStatus, Progress
from qapital.api.storage import Storage
from qapital.core.schemas import HardwareCheck

log = logging.getLogger("qapital.api")
Kind = Literal["optimise", "backtest", "hardware"]
State = Literal["queued", "running", "done", "error", "cancelled"]
Work = Callable[[Callable[[str, int, int], None]], BaseModel]
KEEP_SECONDS = 3600.0
UNEXPECTED = "Something went wrong on our side while running this. Please try again, or change the settings."


class Cancelled(Exception):
    pass


@dataclass
class Job:
    id: str
    kind: Kind
    visitor: str
    status: State = "queued"
    progress: Progress | None = None
    result: BaseModel | None = None
    error: str | None = None
    cached: bool = False
    version: int = 0  # goes up on every change, so a live stream knows when to send
    started: float | None = None
    finished: float | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    future: Future | None = None

    @property
    def over(self) -> bool:
        return self.status in ("done", "error", "cancelled")

    def as_status(self) -> JobStatus:
        status = JobStatus(
            status=self.status, progress=self.progress, error=self.error, kind=self.kind, cached=self.cached
        )
        if isinstance(self.result, FullResult):
            status.result = self.result
        elif isinstance(self.result, BacktestResult):
            status.backtest = self.result
        elif isinstance(self.result, HardwareCheck):
            status.hardware = self.result
        return status


class JobManager:
    def __init__(self, storage: Storage, workers: int = 2, keep_seconds: float = KEEP_SECONDS):
        self.storage = storage
        self.keep_seconds = keep_seconds
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="qapital-job")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, kind: Kind, visitor: str, request_key: str, snapshot: str, work: Work) -> Job:
        job = Job(id=uuid.uuid4().hex, kind=kind, visitor=visitor)
        self._add(job)
        job.future = self._pool.submit(self._run, job, work, request_key, snapshot)
        return job

    def answered(self, kind: Kind, visitor: str, result: BaseModel) -> Job:
        """A job that is done already: an identical request was answered before."""
        job = Job(id=uuid.uuid4().hex, kind=kind, visitor=visitor, status="done", result=result, cached=True)
        job.progress = Progress(stage="Done", step=1, total=1, elapsed_s=0.0)
        job.finished = time.monotonic()
        self._add(job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> Job | None:
        job = self._jobs.get(job_id)
        if job is None or job.over:
            return job
        job.cancel.set()
        if job.future is not None and job.future.cancel():  # still waiting in the queue: stop it now
            self._finish(job, "cancelled")
        return job

    def active(self, visitor: str) -> int:
        return sum(1 for job in list(self._jobs.values()) if job.visitor == visitor and not job.over)

    def shutdown(self) -> None:
        for job in list(self._jobs.values()):
            job.cancel.set()
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _add(self, job: Job) -> None:
        with self._lock:
            now = time.monotonic()
            stale = [i for i, j in self._jobs.items() if j.finished and now - j.finished > self.keep_seconds]
            for job_id in stale:
                del self._jobs[job_id]
            self._jobs[job.id] = job

    def _run(self, job: Job, work: Work, request_key: str, snapshot: str) -> None:
        if job.cancel.is_set():
            self._finish(job, "cancelled")
            return
        job.status, job.started = "running", time.monotonic()
        self._changed(job)

        def on_progress(stage: str, step: int, total: int) -> None:
            if job.cancel.is_set():
                raise Cancelled
            elapsed = time.monotonic() - (job.started or time.monotonic())
            job.progress = Progress(stage=stage, step=step, total=total, elapsed_s=round(elapsed, 1))
            self._changed(job)

        try:
            result = work(on_progress)
        except Cancelled:
            self._finish(job, "cancelled")
            return
        except ValueError as error:  # our own messages, written for the person running it
            self._finish(job, "error", str(error))
            return
        except Exception:
            log.exception("Job %s (%s) failed", job.id, job.kind)
            self._finish(job, "error", UNEXPECTED)
            return

        result_id = uuid.uuid4().hex
        if isinstance(result, FullResult | BacktestResult):
            result.result_id = result_id
        try:
            self.storage.save(job.kind, request_key, snapshot, result.model_dump_json(), result_id)
        except Exception:
            log.exception("Could not store the result of job %s", job.id)
        job.result = result
        elapsed = time.monotonic() - (job.started or time.monotonic())
        job.progress = Progress(stage="Done", step=1, total=1, elapsed_s=round(elapsed, 1))
        self._finish(job, "done")

    def _finish(self, job: Job, status: State, error: str | None = None) -> None:
        job.status, job.error, job.finished = status, error, time.monotonic()
        self._changed(job)

    def _changed(self, job: Job) -> None:
        with self._lock:
            job.version += 1
