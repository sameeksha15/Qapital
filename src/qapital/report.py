"""Putting a quantum run and the classical baselines together into the website's result: the comparison table, the
frontier picks, what is known about the best portfolio, and a plain-language verdict built only from these numbers.
Shared by the live API and the static-site builder, so both say exactly the same thing."""

import math

from qapital.api.schemas import Frontier, Optimal, Pick, Portfolio, ReportRow
from qapital.classical.report import Classical, describe
from qapital.core.schemas import MarketData, QuantumResult, Settings


def scored(tickers: list[str], data: MarketData, settings: Settings) -> dict:
    """Score, return and volatility of a pick, for a report row."""
    info = describe(tickers, data, settings)
    return {"chosen": tickers, "score": info["score"], "expected_return": info["expected_return"], "risk": info["risk"]}


def optimal_block(classical: Classical, quantum: QuantumResult, data: MarketData, settings: Settings) -> Optimal:
    """The best portfolio known. When the list is too long to check, the circuit's pick counts if it scored best."""
    best_tickers, found_by = classical.true_best, classical.best_found_by
    if not classical.best_is_exact:
        mine, theirs = describe(quantum.chosen, data, settings), describe(best_tickers, data, settings)
        if mine["score"] < theirs["score"] - 1e-12:
            best_tickers, found_by = quantum.chosen, "QAOA (best known; too many portfolios to check them all)"
    best = Portfolio(**describe(best_tickers, data, settings))
    shortlist_best = Portfolio(**describe(classical.shortlist_best, data, settings))
    return Optimal(
        best=best,
        best_is_exact=classical.best_is_exact,
        best_found_by=found_by,
        shortlist_best=shortlist_best,
        num_valid_shortlist=classical.num_valid_shortlist,
        shortlisting_gap=shortlist_best.score - best.score,
        relaxation_lower_bound=classical.relaxation_lower_bound,
        num_valid=classical.num_valid,
    )


def report_card(
    quantum: QuantumResult, seconds: float, classical: Classical, optimal: Optimal, data: MarketData, settings: Settings
) -> list[ReportRow]:
    best = set(optimal.best.stocks)
    qaoa = ReportRow(
        solver="QAOA",
        found_best=set(quantum.chosen) == best,
        runtime_s=round(seconds, 4),
        universe="shortlist" if quantum.shortlist else "full",
        **scored(quantum.chosen, data, settings),
    )
    rows = [
        ReportRow(
            solver=method.name,
            found_best=set(method.chosen) == best,
            runtime_s=round(method.runtime_s, 4),
            hit_rate=method.hit_rate,
            universe=method.universe,
            **scored(method.chosen, data, settings),
        )
        for method in classical.methods
    ]
    return [qaoa, *rows]


def frontier(classical: Classical, rows: list[ReportRow]) -> Frontier:
    return Frontier(
        continuous=classical.continuous_frontier,
        discrete=classical.discrete_frontier,
        picks=[Pick(solver=row.solver, risk=row.risk or 0.0, ret=row.expected_return or 0.0) for row in rows],
    )


def verdict(quantum: QuantumResult, rows: list[ReportRow], optimal: Optimal, classical: Classical, n: int) -> str:
    """Plain-language summary built only from the numbers in the result."""
    qaoa = rows[0]
    if optimal.best_is_exact:
        best = f"the true best portfolio of all {n} stocks"
    else:
        best = f"the best portfolio any method found among {classical.num_valid:,} legal portfolios (not proven best)"
    if qaoa.found_best:
        first = f"The quantum circuit picked {best}."
    else:
        gap = (qaoa.score - optimal.best.score) / abs(optimal.best.score)
        first = f"The quantum circuit's pick scores {gap:.1%} worse than {best}."
    shortlist_size = len(quantum.shortlist or [])
    where = f"of its {shortlist_size}-stock shortlist " if shortlist_size else ""
    lift = f"{quantum.lift_over_random:.1f}×"
    parts = [first, f"It sampled the best portfolio {where}{lift} more often than random guessing."]
    if quantum.warm_start_alone is not None:
        parts.append(
            f"Its classical warm start alone gave {quantum.warm_start_alone.lift_over_random:.1f}×, "
            "so the difference is what the quantum layers added."
        )
    brute = next((row for row in rows if row.solver == "Brute force"), None)
    if brute is not None:
        parts.append(
            f"Brute force checked all {math.comb(n, len(quantum.chosen)):,} possible portfolios in "
            f"{brute.runtime_s:.2f} s, so this shows what the quantum method needs in order to compete, "
            "not a speed advantage."
        )
    else:
        parts.append(
            "There were too many portfolios to check them all; classical heuristics still found answers in seconds, "
            "so this shows what the quantum method needs in order to compete, not a speed advantage."
        )
    return " ".join(parts)
