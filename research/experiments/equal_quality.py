"""Same quality, fewer gates: how many two-qubit gates the penalty circuit and the XY circuit (with pruning) need, and
how good their answers are, on 8-stock shortlists of every quarter's problem since 2019 in both markets.

For each circuit and depth the summary gives the mean and range over all problems, and names the cheapest XY circuit
whose mean lift is at least the best penalty circuit's.
Run from the repo root (about 5 minutes):  python -m research.experiments.equal_quality"""

from datetime import datetime

import pandas as pd

from qapital.core.schemas import Settings
from research.experiments.common import (
    INVESTOR,
    MARKETS,
    Job,
    circuit_row,
    problems,
    run_info,
    run_parallel,
    save,
    spread,
)

SIZE = 8
DEPTHS = (1, 2, 3, 4)
CIRCUITS = (("standard", 1.0), ("xy", 1.0), ("xy", 0.5), ("xy", 0.25))
CVAR_ALPHA = 0.25
KEYS = ["mixer", "pairs_kept", "depth"]


def jobs() -> list[Job]:
    return [{"market": market, "as_of": day} for market in MARKETS for day in problems().dates(market)]


def task(job: Job) -> list[dict]:
    problem = problems().get(job["market"], job["as_of"], SIZE)
    rows = []
    for depth in DEPTHS:
        for mixer, kept in CIRCUITS:
            settings = Settings(**INVESTOR, cvar_alpha=CVAR_ALPHA, mixer=mixer, pairs_kept=kept, depth=depth)
            rows.append(circuit_row(problem, settings))
    return rows


def summarise(runs: pd.DataFrame) -> dict:
    rows = []
    for values, group in runs.groupby(KEYS):
        rows.append(
            {
                **dict(zip(KEYS, values, strict=True)),
                "lift": spread(group["lift"]),
                "legal": spread(group["legal"]),
                "closeness": spread(group["closeness"]),
                "gates": spread(group["gates"]),
                "found_best": float(group["found_best"].mean()),
            }
        )
    penalty = [r for r in rows if r["mixer"] == "standard"]
    best_penalty = max(penalty, key=lambda r: r["lift"]["mean"])
    matches = [r for r in rows if r["mixer"] == "xy" and r["lift"]["mean"] >= best_penalty["lift"]["mean"]]
    cheapest = min(matches, key=lambda r: r["gates"]["mean"]) if matches else None
    return {
        "rows": rows,
        "problems": int(runs.groupby(["market", "as_of"]).ngroups),
        "best_penalty": {k: best_penalty[k] for k in KEYS},
        "cheapest_match": {k: cheapest[k] for k in KEYS} if cheapest else None,
    }


def main() -> None:
    started = datetime.now()
    runs = run_parallel(task, jobs())
    summary = {"all": summarise(runs), **{m: summarise(runs[runs["market"] == m]) for m in MARKETS}}
    info = run_info(
        "Same quality, fewer gates: penalty vs XY with pruning",
        problems(),
        started,
        size=SIZE,
        depths=DEPTHS,
        circuits=CIRCUITS,
        cvar_alpha=CVAR_ALPHA,
        dates="first trading day of every quarter from 2019",
        chip="fake IBM Brisbane (gate counts)",
    )
    save("equal_quality", runs, info, {"summary": summary})


if __name__ == "__main__":
    main()
