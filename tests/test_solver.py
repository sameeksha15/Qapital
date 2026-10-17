"""solve() end to end: paths through the engine and the situations a website user can create."""

from math import comb

import numpy as np
import pytest

from qapital import Settings, is_valid, load_market, solve
from qapital.core.metrics import brute_force
from qapital.core.problem import score
from qapital.data.toy import NIFTY_LIKE_SECTORS, random_market, toy
from scripts.paths import MARKET_FILE, PRICES_CSV


@pytest.mark.parametrize("mixer", ["standard", "xy"])
@pytest.mark.parametrize("optimiser", ["COBYLA", "SPSA"])
def test_every_mixer_and_optimiser_finds_the_toy_answer(mixer, optimiser):
    result = solve(toy(), Settings(k=2, sector_cap=1, mixer=mixer, optimiser=optimiser, depth=1))
    assert sorted(result.chosen) == ["BANK2", "FMCG"]
    assert result.score == pytest.approx(-0.138)


def test_same_settings_and_seed_give_the_same_result():
    settings = Settings(k=3, sector_cap=2, depth=2, seed=5)
    data = random_market(["A", "A", "A", "B", "B", "C"])
    assert solve(data, settings) == solve(data, settings)


def test_sector_cap_above_one_uses_slack_qubits():
    data, settings = random_market(["A", "A", "A", "B", "B", "C"], seed=2), Settings(k=3, sector_cap=2)
    result = solve(data, settings)
    assert result.num_slack_qubits == 2 and result.num_qubits == 8
    chosen = np.array([t in result.chosen for t in data.tickers], dtype=int)
    assert is_valid(chosen, data, settings)
    assert result.score == pytest.approx(score(chosen, data, settings))


def test_long_lists_are_shortlisted():
    data, settings = random_market(NIFTY_LIKE_SECTORS), Settings(k=10, sector_cap=1, depth=1)
    result = solve(data, settings)
    assert result.shortlist is not None and len(result.shortlist) == 16 == result.num_qubits
    assert set(result.chosen) <= set(result.shortlist)


def test_result_details():
    data, settings = random_market(["A", "A", "B", "B", "C", "D"], seed=1), Settings(k=3, sector_cap=1, depth=3)
    stages = []
    result = solve(data, settings, on_progress=lambda *update: stages.append(update))

    names = [stage for stage, _, _ in stages]
    assert names[0] == "Building the score" and names[-1] == "Done"
    assert names.index("Tuning circuit") < names.index("Sampling portfolios")
    assert all(0 <= step <= total for _, step, total in stages)

    assert 0 < len(result.top_samples) <= 20
    counts = [sample.count for sample in result.top_samples]
    assert counts == sorted(counts, reverse=True)
    assert all(set(sample.stocks) <= set(data.tickers) for sample in result.top_samples)

    assert len(result.layer_probs) == settings.depth + 1
    assert all(len(row) == len(result.layer_labels) <= 8 for row in result.layer_probs)
    reference = brute_force(data, settings)
    assert result.layer_probs[0] == pytest.approx([1 / comb(6, 3)] * len(result.layer_labels))  # Dicke start
    assert result.lift_over_random == pytest.approx(result.p_optimal * len(reference.scores))
    assert 0 <= result.approx_ratio <= 1 and 0 < result.feasible_rate <= 1
    assert result.two_qubit_gates > 0 and result.circuit_depth > 0
    assert result.noise is None and result.shortlist is None


def test_bad_data_gives_a_friendly_error():
    data = toy()
    data.mu = data.mu[:3]
    with pytest.raises(ValueError, match="needs a sector, an expected return"):
        solve(data, Settings(k=2))


def test_no_valid_sample_gives_a_friendly_error(monkeypatch):
    monkeypatch.setattr(
        "qapital.quantum.solver.IdealSimulator.sample", lambda self, theta, shots, seed: {"0011": shots}
    )
    with pytest.raises(ValueError, match="followed the rules"):
        solve(toy(), Settings(k=2, sector_cap=1, depth=1))


@pytest.mark.skipif(not PRICES_CSV.exists(), reason="needs the cached price CSV")
def test_real_8_stock_universe_finds_the_brute_force_best():
    data, settings = load_market(MARKET_FILE, PRICES_CSV), Settings(k=4, sector_cap=1, depth=2)
    result = solve(data, settings)
    best = brute_force(data, settings)
    assert result.score == pytest.approx(best.best_score)
    assert result.lift_over_random > 1
