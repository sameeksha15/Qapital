"""Every experiment, one after another, each saving its results as it finishes (so a stop loses only the current one).
Run from the repo root (about an hour with 6 worker processes):  python -m research.experiments.run_all
Set QAPITAL_RESEARCH_WORKERS to change the number of processes, or QAPITAL_RESEARCH_QUICK=1 for a few-minute dry run
on two dates (written to research/results/<name>-quick/, never to the website)."""

import importlib
import sys
import time

EXPERIMENTS = ("covariance", "circuits", "equal_quality", "families", "optimisers", "noise")


def main() -> None:
    chosen = sys.argv[1:] or EXPERIMENTS
    for name in chosen:
        started = time.perf_counter()
        print(f"=== {name}", flush=True)
        importlib.import_module(f"research.experiments.{name}").main()
        print(f"=== {name} done in {(time.perf_counter() - started) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
