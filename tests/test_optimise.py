import numpy as np
import pytest

from qapital.quantum.optimise import cobyla, evaluation_budget, interp, spsa, start_grid, tune


def bowl(theta):
    return float(np.sum((np.asarray(theta) - 0.5) ** 2))


def test_interp_matches_the_spec_example():
    assert np.allclose(interp(np.array([0.3, 0.6, 0.1, 0.2])), [0.3, 0.45, 0.6, 0.1, 0.15, 0.2])
    assert np.allclose(interp(np.array([0.4, 0.9])), [0.4, 0.4, 0.9, 0.9])


def test_start_grid_covers_one_period_of_beta():
    assert start_grid(np.pi).shape == (100, 2)
    assert start_grid(2 * np.pi).shape == (200, 2)
    assert start_grid(np.pi)[:, 1].max() < np.pi


@pytest.mark.parametrize("method", ["COBYLA", "SPSA"])
def test_optimisers_find_the_bottom_of_a_bowl(method):
    start = np.zeros(4)
    theta = cobyla(bowl, start, 600) if method == "COBYLA" else spsa(bowl, start, 600, np.random.default_rng(0))
    assert np.allclose(theta, 0.5, atol=0.05)


@pytest.mark.parametrize("optimiser", ["COBYLA", "SPSA"])
def test_tune_returns_angles_for_the_full_depth_within_budget(optimiser):
    steps = []
    theta, history = tune(lambda depth: bowl, 3, optimiser, np.pi, seed=1, on_step=lambda: steps.append(1))
    assert len(theta) == 6
    assert len(steps) <= evaluation_budget(3, np.pi)
    assert len(history) == len(steps) - len(start_grid(np.pi))
    assert bowl(theta) < 0.01


def test_tune_is_repeatable_with_the_same_seed():
    first = tune(lambda depth: bowl, 2, "SPSA", np.pi, seed=7)
    second = tune(lambda depth: bowl, 2, "SPSA", np.pi, seed=7)
    assert np.array_equal(first[0], second[0]) and first[1] == second[1]


@pytest.mark.parametrize("optimiser", ["COBYLA", "SPSA"])
def test_random_start_tunes_every_layer_at_once_within_the_same_budget(optimiser):
    steps, depths = [], []

    def energy_at_depth(depth):
        depths.append(depth)
        return bowl

    theta, history = tune(energy_at_depth, 3, optimiser, np.pi, seed=1, on_step=lambda: steps.append(1), start="random")
    assert depths == [3] and len(theta) == 6
    assert len(history) == len(steps) <= evaluation_budget(3, np.pi)
    assert bowl(theta) < 0.01


def test_random_start_depends_on_the_seed_and_repeats_with_it():
    first = tune(lambda depth: bowl, 2, "COBYLA", np.pi, seed=7, start="random")
    again = tune(lambda depth: bowl, 2, "COBYLA", np.pi, seed=7, start="random")
    other = tune(lambda depth: bowl, 2, "COBYLA", np.pi, seed=8, start="random")
    assert first[1] == again[1] and first[1][0] != other[1][0]


def test_unknown_start_gives_a_friendly_error():
    with pytest.raises(ValueError, match="Unknown start"):
        tune(lambda depth: bowl, 1, "COBYLA", np.pi, seed=0, start="sideways")
