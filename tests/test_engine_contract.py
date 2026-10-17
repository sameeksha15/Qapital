"""Join 2 check."""

import json

import numpy as np
import pytest

from qapital import QuantumResult, Settings, score, solve
from qapital.data.toy import toy


def test_output_fits_contract_and_is_json_safe():
    calls = []
    result = solve(toy(), Settings(k=2, sector_cap=1), on_progress=lambda *a: calls.append(a))
    assert isinstance(result, QuantumResult)
    json.dumps(result.model_dump(mode="json"))  # fails on NumPy values
    assert calls, "solve() must report progress"


def test_finds_true_best_on_toy():
    data, settings = toy(), Settings(k=2, sector_cap=1)
    result = solve(data, settings)
    assert sorted(result.chosen) == ["BANK2", "FMCG"]
    x = np.array([t in result.chosen for t in data.tickers], dtype=int)
    assert result.score == pytest.approx(score(x, data, settings))
    assert result.score == pytest.approx(-0.138)


def test_tickers_not_bitstrings():
    result = solve(toy(), Settings(k=2, sector_cap=1))
    assert all(t in toy().tickers for t in result.chosen)


def test_friendly_error_k_too_big():
    with pytest.raises(ValueError, match="fewer stocks"):
        solve(toy(), Settings(k=4))


def test_friendly_error_sector_cap_too_strict():
    data = toy()
    data.sectors = ["Banking"] * 4  # every stock in one sector
    with pytest.raises(ValueError, match="sector cap"):
        solve(data, Settings(k=2, sector_cap=1))
