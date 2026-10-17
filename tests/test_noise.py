"""Noisy runs on fake IBM chips: post-selection, the ideal-vs-noisy comparison, the 12-qubit limit and
the pruning study."""

from collections import Counter

import pytest

from qapital import Settings, pruning_study, solve
from qapital.core.metrics import brute_force, grade
from qapital.data.toy import NIFTY_LIKE_SECTORS, random_market, toy
from qapital.quantum.hardware import fake_chip
from qapital.quantum.noise import NoisyRun, compare, grade_postselected, postselect


def test_postselection_keeps_only_shots_with_k_stocks():
    counts = Counter({(1, 1, 0, 0): 5, (1, 0, 0, 0): 3, (1, 1, 1, 0): 2, (0, 0, 1, 1): 1})
    assert postselect(counts, 2) == Counter({(1, 1, 0, 0): 5, (0, 0, 1, 1): 1})


def test_comparing_a_run_with_itself_changes_nothing():
    data, settings = toy(), Settings(k=2, sector_cap=1)
    reference = brute_force(data, settings)
    counts = Counter({x: 10 for x in reference.scores})
    ideal = grade(counts, reference)
    noise = compare(ideal, counts, reference, settings.k)
    assert noise.noisy_p_optimal == noise.ideal_p_optimal == noise.postselected_p_optimal
    assert noise.postselected_share == 1.0


def test_no_shot_passing_the_count_check_grades_as_zero():
    data, settings = toy(), Settings(k=2, sector_cap=1)
    quality, share = grade_postselected(Counter({(1, 1, 1, 0): 7}), brute_force(data, settings), settings.k)
    assert share == 0 and quality.p_optimal == quality.lift_over_random == 0


@pytest.mark.parametrize("mixer", ["standard", "xy"])
def test_noisy_run_reports_ideal_noisy_and_postselected_quality(mixer):
    settings = Settings(k=2, sector_cap=1, depth=1, mixer=mixer, noisy=True)
    stages = []
    result = solve(toy(), settings, on_progress=lambda *update: stages.append(update[0]))
    noise = result.noise
    assert "Running on noisy chip" in stages and stages[-1] == "Done"
    assert sorted(result.chosen) == ["BANK2", "FMCG"]
    assert noise.chip == "FakeBrisbane"
    assert (noise.ideal_p_optimal, noise.ideal_feasible_rate) == (result.p_optimal, result.feasible_rate)
    values = noise.model_dump(exclude={"chip"}).values()
    assert all(0 <= value <= 1 for value in values)
    assert 0 < noise.postselected_share <= 1
    # Only shots with exactly k stocks can be legal or best, so keeping just those can only raise these shares.
    assert noise.postselected_feasible_rate >= noise.noisy_feasible_rate
    assert noise.postselected_p_optimal >= noise.noisy_p_optimal


def test_same_seed_gives_the_same_noisy_result():
    settings = Settings(k=2, sector_cap=1, depth=1, noisy=True, seed=3)
    assert solve(toy(), settings).noise == solve(toy(), settings).noise


def test_noisy_runs_are_shortlisted_to_12_qubits(monkeypatch):
    def fake_run(circuit, shots, seed):
        return NoisyRun({"0" * circuit.num_qubits: shots}, 0, circuit, "FakeBrisbane", seed)

    monkeypatch.setattr("qapital.quantum.solver.noisy_run", fake_run)
    settings = Settings(k=4, sector_cap=1, depth=1, noisy=True, mitigate_readout=False)
    result = solve(random_market(NIFTY_LIKE_SECTORS), settings)
    assert result.num_qubits == 12 == len(result.shortlist)
    assert result.noise.noisy_p_optimal == 0 and result.noise.postselected_share == 0
    assert result.noise.mitigated_p_optimal is None and result.noise.readout_error is None


def test_unknown_chip_gives_a_friendly_error():
    with pytest.raises(ValueError, match="Unknown chip"):
        fake_chip("FakeNowhere")


def test_pruning_study_saves_gates_only_on_the_xy_circuit():
    data = random_market(["A", "A", "B", "B", "C", "D"], seed=1)
    points = {
        mixer: pruning_study(data, Settings(k=3, sector_cap=1, depth=1, mixer=mixer)) for mixer in ["standard", "xy"]
    }
    for rows in points.values():
        assert [row.kept for row in rows] == [1.0, 0.75, 0.5, 0.25]
        assert all(row.ideal >= 0 and row.noisy >= 0 and row.noisy_postselected >= 0 for row in rows)
    assert len({row.gates for row in points["standard"]}) == 1
    assert points["xy"][-1].gates < points["xy"][0].gates
