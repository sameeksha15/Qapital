import numpy as np
import pytest

from qapital.core.metrics import Reference, brute_force, grade
from qapital.core.schemas import MarketData, Settings
from qapital.data.toy import toy

BEST, SECOND, WORST, INVALID = (0, 1, 0, 1), (0, 1, 1, 0), (1, 0, 1, 0), (1, 1, 0, 0)


def test_brute_force_on_the_toy_example():
    reference = brute_force(toy(), Settings(k=2, sector_cap=1))
    assert len(reference.scores) == 5
    assert reference.best == {BEST}
    assert reference.best_score == pytest.approx(-0.138)
    assert INVALID not in reference.scores  # two banks


def test_grading_by_hand():
    reference = brute_force(toy(), Settings(k=2, sector_cap=1))
    quality = grade({BEST: 50, WORST: 25, INVALID: 25}, reference)
    assert quality.p_optimal == pytest.approx(0.5)
    assert quality.feasible_rate == pytest.approx(0.75)
    assert quality.lift_over_random == pytest.approx(0.5 * 5)
    assert quality.approx_ratio == pytest.approx(0.5 * 1 + 0.25 * 0 + 0.25 * 0)


def test_ties_share_the_random_chance():
    reference = Reference({BEST: -1.0, SECOND: -1.0, WORST: 0.0}, frozenset({BEST, SECOND}), -1.0, 0.0)
    assert grade({BEST: 1}, reference).lift_over_random == pytest.approx(1 * 3 / 2)


def test_equal_scores_count_every_valid_shot_as_best():
    data = MarketData(["W", "X", "Y"], ["A", "B", "C"], np.full(3, 0.1), np.eye(3) * 0.04, np.zeros(3))
    reference = brute_force(data, Settings(k=1))
    assert len(reference.best) == 3
    quality = grade({(1, 0, 0): 3, (1, 1, 0): 1}, reference)
    assert quality.p_optimal == pytest.approx(0.75)
    assert quality.approx_ratio == pytest.approx(0.75)
    assert quality.lift_over_random == pytest.approx(0.75)
