"""Phase 0 acceptance: on the 48-stock data the hackathon website was built on, the moved engine and the rewritten
classical baselines reproduce the saved results. Skipped when that (unpublished) data file isn't present."""

import json

import pytest

from qapital import Settings, solve
from qapital.classical.report import run_classical
from qapital.data.returns import load_returns
from qapital.quantum.shortlist import fit_to_simulator
from qapital.quantum.solver import MAX_QUBITS, SHOTS
from scripts.paths import LEGACY_RETURNS

SAVED = LEGACY_RETURNS.parent / "hackathon_xy_p2_pairs100_cobyla.json"  # the hackathon website's saved result
pytestmark = pytest.mark.skipif(not LEGACY_RETURNS.exists(), reason="needs data/legacy/ (not published)")


@pytest.fixture(scope="module")
def problem():
    data = load_returns(LEGACY_RETURNS, "log", fee=0.0012)
    settings = Settings(
        k=4, sector_cap=1, risk_aversion=1.0, depth=2, mixer="xy", optimiser="COBYLA", seed=42, cvar_alpha=1.0
    )
    return data, settings, json.loads(SAVED.read_text())


def test_quantum_run_is_unchanged(problem):
    data, settings, saved = problem
    now = solve(data, settings).model_dump()
    for key in [
        "chosen",
        "p_optimal",
        "lift_over_random",
        "feasible_rate",
        "two_qubit_gates",
        "circuit_depth",
        "layer_probs",
        "shortlist",
    ]:
        assert now[key] == saved["quantum"][key], key
    for ours, theirs in zip(now["top_samples"], saved["quantum"]["top_samples"], strict=True):
        assert {**ours, "score": 0} == {**theirs, "score": 0}
        assert ours["score"] == pytest.approx(theirs["score"], abs=1e-12)  # same sum, added in a different order
    assert now["convergence"] == pytest.approx(saved["quantum"]["convergence"], abs=1e-12)


def test_rewritten_classical_baselines_agree_with_the_saved_report(problem):
    data, settings, saved = problem
    shortlist = fit_to_simulator(data, settings, MAX_QUBITS)[1]
    result = run_classical(data, settings, shortlist, SHOTS)
    optimal = saved["optimal"]
    assert result.true_best == sorted(optimal["best"]["stocks"])
    assert result.shortlist_best == optimal["shortlist_best"]["stocks"]
    assert result.num_valid_shortlist == optimal["num_valid_shortlist"]
    assert result.relaxation_lower_bound == pytest.approx(optimal["relaxation_lower_bound"], abs=1e-4)
    assert result.methods[1].hit_rate == 1.0  # simulated annealing, 10 seeds
    # The new envelope keeps every best portfolio; the old one kept a subset of them.
    ours = {(round(risk, 10), round(ret, 10)) for risk, ret in result.discrete_frontier}
    assert {(round(risk, 10), round(ret, 10)) for risk, ret in saved["frontier"]["discrete"]} <= ours
    assert result.discrete_frontier[-1] == pytest.approx(tuple(saved["frontier"]["discrete"][-1]), abs=1e-12)
    saved_curve = saved["frontier"]["continuous"]
    assert result.continuous_frontier[0][0] <= saved_curve[0][0]  # starts at least as safe (true minimum risk)
    assert result.continuous_frontier[-1] == pytest.approx(saved_curve[-1], abs=2e-4)
