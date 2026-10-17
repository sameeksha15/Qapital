"""Fair use for a free public demo: per visitor, one job at a time and a few runs per hour.

Counts live in memory (one server process), in sliding one-hour windows. Answers served from the cache don't count."""

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

HOUR = 3600.0


@dataclass(frozen=True)
class Limits:
    runs_per_hour: int = 20  # every optimisation
    heavy_per_hour: int = 3  # noisy-chip runs and pruning studies, which take minutes
    backtests_per_hour: int = 5
    jobs_at_once: int = 1


BUCKET_NAMES = {
    "runs": "optimisation runs",
    "heavy": "noisy-chip runs and pruning studies",
    "backtests": "backtests",
}


class LimitReached(Exception):
    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


class RateLimiter:
    def __init__(self, limits: Limits, clock=time.monotonic):
        self.limits = limits
        self.clock = clock
        self._used: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def take(self, visitor: str, buckets: list[str], active_jobs: int) -> None:
        """Count one use of each bucket, or raise LimitReached without counting any."""
        if active_jobs >= self.limits.jobs_at_once:
            raise LimitReached("You already have a run in progress. Wait for it to finish, or cancel it.", 5)
        with self._lock:
            now = self.clock()
            for bucket in buckets:
                used = self._window(visitor, bucket, now)
                allowed = self._allowed(bucket)
                if len(used) >= allowed:
                    wait = int(used[0] + HOUR - now) + 1
                    raise LimitReached(
                        f"You've reached the limit of {allowed} {BUCKET_NAMES[bucket]} per hour on this free demo. "
                        f"Try again in {max(1, wait // 60)} minutes, or run Qapital locally without limits.",
                        wait,
                    )
            for bucket in buckets:
                self._used[(visitor, bucket)].append(now)

    def _window(self, visitor: str, bucket: str, now: float) -> deque[float]:
        used = self._used[(visitor, bucket)]
        while used and used[0] <= now - HOUR:
            used.popleft()
        return used

    def _allowed(self, bucket: str) -> int:
        return {
            "runs": self.limits.runs_per_hour,
            "heavy": self.limits.heavy_per_hour,
            "backtests": self.limits.backtests_per_hour,
        }[bucket]
