"""The circuit grid: every circuit setting on today's problem in each market, on the full 16-stock shortlist.

Penalty, XY and warm-started circuits, 1–3 layers, 100/75/50/25% of stock links kept (pruning only changes the XY
circuit's gates; the penalty and warm circuits need every pair for the count fine), COBYLA and SPSA. Each is graded
against the shortlist's best (brute force) and two-qubit gates are counted on a fake IBM Brisbane chip.
Feeds the Research page's gates-vs-quality chart and the How-it-works numbers.
Run from the repo root (about 15 minutes):  python -m research.experiments.circuits"""

from datetime import datetime

import pandas as pd

from qapital.core.metrics import brute_force
from qapital.core.schemas import Settings
from research.experiments.common import (
    INVESTOR,
    MARKET_NAMES,
    MARKETS,
    Job,
    circuit_row,
    problems,
    run_info,
    run_parallel,
    save,
)

SIZE = 16
DEPTHS = (1, 2, 3)
PAIRS = (1.0, 0.75, 0.5, 0.25)
OPTIMISERS = ("COBYLA", "SPSA")
CVAR_ALPHA = 0.25  # the website's default


def jobs() -> list[Job]:
    found = []
    for market in MARKETS:
        as_of = problems().latest(market)
        for depth in DEPTHS:
            for optimiser in OPTIMISERS:
                found.append(
                    {
                        "market": market,
                        "as_of": as_of,
                        "mixer": "warm",
                        "depth": depth,
                        "pairs_kept": 1.0,
                        "optimiser": optimiser,
                    }
                )
                for mixer in ("standard", "xy"):
                    for kept in PAIRS:
                        found.append(
                            {
                                "market": market,
                                "as_of": as_of,
                                "mixer": mixer,
                                "depth": depth,
                                "pairs_kept": kept,
                                "optimiser": optimiser,
                            }
                        )
    # the slowest (XY, many layers) first, so the pool doesn't wait on them at the end
    return sorted(found, key=lambda job: (job["mixer"] != "xy", -job["depth"]))


def task(job: Job) -> list[dict]:
    problem = problems().get(job["market"], job["as_of"], SIZE)
    settings = Settings(
        **INVESTOR, cvar_alpha=CVAR_ALPHA, **{k: job[k] for k in ("mixer", "depth", "pairs_kept", "optimiser")}
    )
    return [circuit_row(problem, settings)]


def website(runs: pd.DataFrame) -> dict:
    markets = {}
    for market in MARKETS:
        problem = problems().get(market, problems().latest(market), SIZE)
        reference = brute_force(problem.data, Settings(**INVESTOR))
        best = [problem.data.tickers[i] for i, bit in enumerate(next(iter(reference.best))) if bit]
        markets[market] = {
            "name": MARKET_NAMES[market],
            "as_of": problem.as_of,
            "stocks": len(problem.full.tickers),
            "shortlist": problem.shortlist,
            "shortlist_best": best,
            "true_best": problem.true_best,
            "best_kept": problem.best_kept,
            "legal_on_shortlist": len(reference.scores),
        }
    columns = [
        "market",
        "mixer",
        "depth",
        "pairs_kept",
        "optimiser",
        "lift",
        "p_best",
        "legal",
        "closeness",
        "found_best",
        "gates",
        "circuit_depth",
        "qubits",
        "warm_alone_lift",
        "seconds",
        "chosen",
    ]
    return {"markets": markets, "runs": runs[columns].to_dict(orient="records")}


def main() -> None:
    started = datetime.now()
    runs = run_parallel(task, jobs())
    runs = runs.sort_values(
        ["market", "mixer", "depth", "pairs_kept", "optimiser"], ascending=[True, True, True, False, True]
    )
    info = run_info(
        "Circuit grid: every circuit setting on today's problem",
        problems(),
        started,
        size=SIZE,
        depths=DEPTHS,
        pairs_kept=PAIRS,
        optimisers=OPTIMISERS,
        cvar_alpha=CVAR_ALPHA,
        chip="fake IBM Brisbane (gate counts)",
        shots=4096,
    )
    save("circuits", runs, info, website(runs))


if __name__ == "__main__":
    main()
