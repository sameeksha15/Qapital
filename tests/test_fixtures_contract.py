"""Join 1 check: the frontend's mock files match the API contract."""

import json
from pathlib import Path

import pytest

from qapital.api.schemas import JobStatus

FIXTURES = sorted((Path(__file__).resolve().parents[1] / "tests" / "fixtures").glob("*.json"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_matches_contract(path):
    JobStatus.model_validate(json.loads(path.read_text()))


def test_fixtures_exist():
    assert {p.name for p in FIXTURES} >= {"job_done.json", "job_running.json", "job_error.json"}
