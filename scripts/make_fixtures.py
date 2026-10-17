"""Builds tests/fixtures/*.json from a real engine run on the toy data + backend models,
so the frontend's mock data always matches the real contract. `quantum` (including `quantum.noise`) and
`pruning` come from real runs on the toy data; everything else is example data.
Run from the repo root:  python -m scripts.make_fixtures"""

import json
from pathlib import Path

from qapital import Settings, pruning_study, solve
from qapital.api.schemas import (
    Backtest,
    Dataset,
    Frontier,
    FullResult,
    JobStatus,
    Optimal,
    Pick,
    Portfolio,
    Progress,
    PruningRow,
    ReportRow,
    Stats,
)
from qapital.data.toy import toy

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)

data = toy()
settings = Settings(k=2, sector_cap=1, noisy=True)
q = solve(data, settings)
pruning = [PruningRow(**point.model_dump()) for point in pruning_study(data, settings)]
best = Portfolio(stocks=q.chosen, score=q.score, expected_return=q.expected_return, risk=q.risk)


def row(solver: str, runtime_s: float, universe: str, hit_rate: float | None = None) -> ReportRow:
    return ReportRow(
        solver=solver,
        found_best=True,
        score=q.score,
        runtime_s=runtime_s,
        hit_rate=hit_rate,
        chosen=q.chosen,
        expected_return=q.expected_return,
        risk=q.risk,
        universe=universe,
    )


done = JobStatus(
    status="done",
    progress=Progress(stage="Done", step=1, total=1),
    result=FullResult(
        quantum=q,
        report_card=[
            row("QAOA", 41.8, "shortlist"),
            row("Brute force", 0.001, "full"),
            row("Simulated annealing", 0.9, "full", hit_rate=1.0),
            row("Relaxation + rounding", 0.03, "full"),
            row("Random guessing", 0.002, "full", hit_rate=1.0),
        ],
        optimal=Optimal(
            best=best,
            best_is_exact=True,
            best_found_by="Brute force",
            shortlist_best=best,
            num_valid_shortlist=5,
            shortlisting_gap=0.0,
            relaxation_lower_bound=q.score - 0.01,
        ),
        dataset=Dataset(
            source="scripts/toy_data.py (made-up)",
            returns="simple",
            estimation_window=("2021-01-01", "2024-12-31"),
            test_window=("2025-01-01", "2025-12-31"),
            fee=0.005,
            safe_rate=0.065,
            num_stocks=4,
            num_sectors=3,
        ),
        frontier=Frontier(
            continuous=[(0.10, 0.09), (0.11, 0.105), (0.13, 0.12), (0.16, 0.135)],
            discrete=[(0.10, 0.09), (0.127, 0.11), (0.15, 0.12)],
            picks=[
                Pick(solver="QAOA", risk=q.risk, ret=q.expected_return),
                Pick(solver="Brute force", risk=q.risk, ret=q.expected_return),
            ],
        ),
        backtest=Backtest(
            portfolio=Stats(ret=0.11, volatility=0.13, sharpe=0.35),
            index=Stats(ret=0.08, volatility=0.15, sharpe=0.1),
            equal_weight_all=Stats(ret=0.09, volatility=0.12, sharpe=0.2),
        ),
        pruning=pruning,
        verdict="EXAMPLE DATA. QAOA found the best portfolio, more often than random guessing; "
        "brute force was faster at this size.",
    ),
)
running = JobStatus(status="running", progress=Progress(stage="Tuning circuit", step=12, total=30))
error = JobStatus(status="error", error="Pick 16 or fewer stocks for this setting.")

for name, obj in [("job_done", done), ("job_running", running), ("job_error", error)]:
    (OUT / f"{name}.json").write_text(json.dumps(obj.model_dump(mode="json"), indent=2))
    print("wrote", OUT / f"{name}.json")
