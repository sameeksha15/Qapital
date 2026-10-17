"""The IBM hardware path, exercised on a fake chip in Qiskit Runtime's local mode (no token, no network)."""

import pytest

from qapital import Settings, hardware_check
from qapital.data.toy import toy
from qapital.quantum.ibm import TOKEN_VARIABLE, _calibration, ibm_backend


def test_hardware_check_on_a_fake_chip_grades_like_a_noisy_run():
    result = hardware_check(toy(), Settings(k=2, sector_cap=1, depth=1), backend="fake:FakeBrisbane")
    assert result.local and result.job_id and result.backend.lower().endswith("brisbane")
    assert result.two_qubit_gates > 0
    comparison = result.comparison
    assert 0 < comparison.readout_error < 0.1
    assert 0 <= comparison.noisy_p_optimal <= 1 and comparison.mitigated_postselected_p_optimal is not None
    assert comparison.postselected_feasible_rate >= comparison.noisy_feasible_rate


def test_real_hardware_without_a_token_gives_a_friendly_error(monkeypatch):
    monkeypatch.delenv(TOKEN_VARIABLE, raising=False)
    with pytest.raises(ValueError, match=TOKEN_VARIABLE):
        ibm_backend("ibm_brisbane", 4)


def test_calibration_counts_misreads_per_qubit():
    # 3 qubits; qubit 0 is the rightmost character. All-0 run: qubit 0 misread in 10 of 100 shots.
    zeros = {"000": 90, "001": 10}
    ones = {"111": 80, "011": 20}  # all-1 run: qubit 2 (leftmost) read as 0 in 20 of 100 shots
    calibration = _calibration(zeros, ones, 3)
    assert list(calibration.read_one_given_zero) == [0.1, 0.0, 0.0]
    assert list(calibration.read_zero_given_one) == [0.0, 0.0, 0.2]
