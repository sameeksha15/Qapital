"""CVaR vs average, and warm start vs cold: the three circuits (penalty, XY, warm-started penalty), each tuned for the
plain average energy (α = 1) or for the best 25% or 10% of outcomes (CVaR), at 1–3 layers, on 10-stock shortlists of
every quarter's problem since 2019 in both markets.

The comparisons are paired: on each problem, did CVaR do better than the average with the same circuit? Did the
warm-started circuit beat its warm start alone, and the XY circuit? Wins are counted problem by problem.
Run from the repo root (about 15 minutes):  python -m research.experiments.families"""

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

SIZE = 10
MIXERS = ("standard", "xy", "warm")
ALPHAS = (1.0, 0.25, 0.1)
DEPTHS = (1, 2, 3)
KEYS = ["mixer", "cvar_alpha", "depth"]
PROBLEM = ["market", "as_of"]


def jobs() -> list[Job]:
    return [{"market": market, "as_of": day} for market in MARKETS for day in problems().dates(market)]


def task(job: Job) -> list[dict]:
    problem = problems().get(job["market"], job["as_of"], SIZE)
    return [
        circuit_row(problem, Settings(**INVESTOR, mixer=mixer, cvar_alpha=alpha, depth=depth))
        for depth in DEPTHS
        for mixer in MIXERS
        for alpha in ALPHAS
    ]


def wins(runs: pd.DataFrame, better: dict, worse: dict, measure: str = "lift") -> dict:
    """On how many problems the `better` setting beat, tied or lost to the `worse` one (paired by problem)."""
    a = runs.loc[(runs[list(better)] == pd.Series(better)).all(axis=1)].set_index(PROBLEM)[measure]
    b = runs.loc[(runs[list(worse)] == pd.Series(worse)).all(axis=1)].set_index(PROBLEM)[measure]
    a, b = a.align(b, join="inner")
    return {
        "wins": int((a > b + 1e-9).sum()),
        "ties": int(((a - b).abs() <= 1e-9).sum()),
        "losses": int((a < b - 1e-9).sum()),
    }


def summarise(runs: pd.DataFrame) -> dict:
    rows = [
        {
            **dict(zip(KEYS, values, strict=True)),
            "lift": spread(group["lift"]),
            "p_best": spread(group["p_best"]),
            "closeness": spread(group["closeness"]),
            "legal": spread(group["legal"]),
            "found_best": float(group["found_best"].mean()),
            "gates": spread(group["gates"]),
            **({"warm_alone_lift": spread(group["warm_alone_lift"])} if values[0] == "warm" else {}),
        }
        for values, group in runs.groupby(KEYS)
    ]
    cvar = {
        f"{mixer} p={depth} α={alpha}": wins(
            runs,
            {"mixer": mixer, "depth": depth, "cvar_alpha": alpha},
            {"mixer": mixer, "depth": depth, "cvar_alpha": 1.0},
        )
        for mixer in MIXERS
        for depth in DEPTHS
        for alpha in ALPHAS[1:]
    }
    warm = runs[runs["mixer"] == "warm"]
    layers_added = {
        f"p={depth} α={alpha}": {
            "wins": int((g["lift"] > g["warm_alone_lift"] + 1e-9).sum()),
            "losses": int((g["lift"] < g["warm_alone_lift"] - 1e-9).sum()),
            "problems": len(g),
        }
        for (depth, alpha), g in warm.groupby(["depth", "cvar_alpha"])
    }
    warm_vs_xy = {
        f"p={depth} α={alpha}": wins(
            runs,
            {"mixer": "warm", "depth": depth, "cvar_alpha": alpha},
            {"mixer": "xy", "depth": depth, "cvar_alpha": alpha},
        )
        for depth in DEPTHS
        for alpha in ALPHAS
    }
    return {
        "rows": rows,
        "problems": int(runs.groupby(PROBLEM).ngroups),
        "cvar_vs_average": cvar,
        "warm_vs_warm_alone": layers_added,
        "warm_vs_xy": warm_vs_xy,
    }


def main() -> None:
    started = datetime.now()
    runs = run_parallel(task, jobs())
    summary = {"all": summarise(runs), **{m: summarise(runs[runs["market"] == m]) for m in MARKETS}}
    info = run_info(
        "CVaR vs average, warm start vs cold",
        problems(),
        started,
        size=SIZE,
        mixers=MIXERS,
        cvar_alphas=ALPHAS,
        depths=DEPTHS,
        warm_epsilon=0.25,
        dates="first trading day of every quarter from 2019",
    )
    save("families", runs, info, {"summary": summary})


if __name__ == "__main__":
    main()
