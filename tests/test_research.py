"""The research toolkit on the small made-up market: dated problems, one graded circuit run, the risk-model variants."""

import numpy as np
import pandas as pd
import pytest

from qapital.core.schemas import Settings
from research.experiments.common import Problems, circuit_row, spread
from research.experiments.covariance import pruned, relative_error

SMALL = Settings(k=2, sector_cap=1, depth=1)


def test_problem_dates_are_the_first_trading_day_of_each_quarter(source):
    problems = Problems(source)
    dates = problems.dates("small")
    assert dates[:3] == ["2019-01-01", "2019-04-01", "2019-07-01"]
    assert dates[-1] == "2021-04-01"
    assert problems.dates("small", every=3) == ["2019-01-01", "2019-10-01", "2020-07-01", "2021-04-01"]


def test_a_problem_is_what_the_app_would_have_solved_that_day(source):
    problem = Problems(source).get("small", "2020-06-30", 4, SMALL)
    assert problem.as_of <= "2020-06-30"
    assert "NEW" not in problem.full.tickers  # listed later: no prices yet
    assert len(problem.shortlist) == 4 and problem.data.tickers == problem.shortlist
    assert (problem.full.fees > 0).all()  # real trading costs
    assert problem.true_best is not None and len(problem.true_best) == 2
    assert problem.best_kept in (True, False)


def test_a_circuit_run_is_graded_against_the_shortlist(source):
    problem = Problems(source).get("small", "2020-06-30", 4, SMALL)
    row = circuit_row(problem, SMALL)
    assert row["market"] == "small" and row["stocks"] == 4
    assert 0 <= row["legal"] <= 1 and row["gates"] > 0 and row["lift"] >= 0
    assert row["found_best"] == (row["p_best"] > 0)


def test_pruning_keeps_the_diagonal_and_the_strongest_pairs():
    sigma = np.array([[1.0, 0.9, 0.1], [0.9, 1.0, -0.5], [0.1, -0.5, 1.0]])
    kept = pruned(sigma, 2 / 3)
    assert np.array_equal(np.diag(kept), np.diag(sigma))
    assert kept[0, 1] == 0.9 and kept[1, 2] == -0.5 and kept[0, 2] == 0
    assert relative_error(sigma, sigma) == 0


def test_spread_summarises_runs():
    assert spread(pd.Series([1.0, 2.0, 6.0])) == {"mean": pytest.approx(3.0), "min": 1.0, "max": 6.0, "n": 3}


def test_website_files_never_hold_nan(tmp_path, monkeypatch):
    import json

    from research.experiments import common

    monkeypatch.setattr(common, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(common, "WEBSITE", tmp_path / "web")
    runs = pd.DataFrame({"x": [1.0, float("nan")]})
    common.save("demo", runs, {"experiment": "demo"}, {"rows": runs.to_dict(orient="records")})
    text = (tmp_path / "web" / "demo.json").read_text(encoding="utf-8")
    assert "NaN" not in text and json.loads(text)["rows"][1]["x"] is None
