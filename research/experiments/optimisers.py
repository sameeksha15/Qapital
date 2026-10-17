"""COBYLA vs SPSA, and our layer-by-layer start vs a random start, on 10-stock shortlists of every second quarter's
problem since 2019 in both markets, three seeds each.

Our start tunes layer 1 from the best point of a coarse grid, then each extra layer from the previous layer's angles
stretched to one more layer (INTERP). A random start tunes all layers at once from seeded random angles, with the same
maximum number of circuit runs. XY circuit, all links kept, tuned for the best 25% of outcomes (CVaR).
Run from the repo root (about 10 minutes):  python -m research.experiments.optimisers"""

import functools
import time
from datetime import datetime

import pandas as pd

from qapital.core.metrics import brute_force, grade
from qapital.core.schemas import Settings
from qapital.quantum.circuits import beta_period
from qapital.quantum.hamiltonian import build_hamiltonian
from qapital.quantum.optimise import tune
from qapital.quantum.solver import _energy, _ideal_counts, circuit_builder
from research.experiments.common import (
    INVESTOR,
    MARKETS,
    Job,
    problems,
    run_info,
    run_parallel,
    save,
    spread,
)

SIZE = 10
DEPTHS = (1, 2, 3)
OPTIMISERS = ("COBYLA", "SPSA")
STARTS = ("warm", "random")  # "warm" here means the grid + layer-by-layer start, not the warm-start circuit
SEEDS = (42, 43, 44)
CVAR_ALPHA = 0.25
KEYS = ["depth", "optimiser", "start"]


def jobs() -> list[Job]:
    return [{"market": market, "as_of": day} for market in MARKETS for day in problems().dates(market, every=2)]


def task(job: Job) -> list[dict]:
    problem = problems().get(job["market"], job["as_of"], SIZE)
    data = problem.data
    rows = []
    for depth in DEPTHS:
        base = Settings(**INVESTOR, mixer="xy", depth=depth, cvar_alpha=CVAR_ALPHA)
        reference = brute_force(data, base)
        ham = build_hamiltonian(data, base)
        for optimiser in OPTIMISERS:
            for start in STARTS:
                for seed in SEEDS:
                    settings = base.model_copy(update={"optimiser": optimiser, "seed": seed})
                    build = circuit_builder(data, ham, settings)
                    steps: list[int] = []
                    started = time.perf_counter()
                    theta, _ = tune(
                        functools.partial(_energy, build, ham, settings),
                        depth,
                        optimiser,
                        beta_period("xy"),
                        seed,
                        on_step=functools.partial(steps.append, 1),
                        start=start,
                    )
                    quality = grade(_ideal_counts(build, ham, settings, theta), reference)
                    rows.append(
                        {
                            "market": problem.market,
                            "as_of": problem.as_of,
                            "depth": depth,
                            "optimiser": optimiser,
                            "start": start,
                            "seed": seed,
                            "objective": _energy(build, ham, settings, depth)(theta),
                            "lift": quality.lift_over_random,
                            "p_best": quality.p_optimal,
                            "closeness": quality.approx_ratio,
                            "found_best": quality.p_optimal > 0,
                            "circuit_runs": len(steps),
                            "seconds": time.perf_counter() - started,
                        }
                    )
    return rows


def summarise(runs: pd.DataFrame) -> dict:
    rows = [
        {
            **dict(zip(KEYS, values, strict=True)),
            **{m: spread(group[m]) for m in ("lift", "p_best", "closeness", "circuit_runs", "seconds")},
            "found_best": float(group["found_best"].mean()),
        }
        for values, group in runs.groupby(KEYS)
    ]
    return {"rows": rows, "problems": int(runs.groupby(["market", "as_of"]).ngroups), "seeds": len(SEEDS)}


def main() -> None:
    started = datetime.now()
    runs = run_parallel(task, jobs())
    summary = {"all": summarise(runs), **{m: summarise(runs[runs["market"] == m]) for m in MARKETS}}
    info = run_info(
        "COBYLA vs SPSA; layer-by-layer start vs random start",
        problems(),
        started,
        size=SIZE,
        depths=DEPTHS,
        optimisers=OPTIMISERS,
        starts={
            "warm": "best point of a coarse (γ, β) grid, then each extra layer from INTERP of the previous one",
            "random": "all angles uniform at random (seeded), same maximum number of circuit runs",
        },
        seeds=SEEDS,
        cvar_alpha=CVAR_ALPHA,
        dates="first trading day of every second quarter from 2019",
    )
    save("optimisers", runs, info, {"summary": summary})


if __name__ == "__main__":
    main()
