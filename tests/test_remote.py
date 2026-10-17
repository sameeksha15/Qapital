"""Downloading the newest snapshot from the GitHub release, with the network replaced by local files."""

import json

import pytest

from qapital.data.remote import release_url, sync_snapshot
from qapital.data.snapshot import load_snapshot, snapshot_ids

REPO = "someone/qapital"


@pytest.fixture
def published(source):
    """The test market's snapshot as the nightly job publishes it: release file name -> bytes."""
    snapshot = load_snapshot("latest", source.snapshots_dir)
    files = {
        "latest.json": json.dumps({"snapshot": snapshot.id}).encode(),
        f"prices-{snapshot.id}.parquet": (snapshot.path / "prices.parquet").read_bytes(),
        f"manifest-{snapshot.id}.json": (snapshot.path / "manifest.json").read_bytes(),
    }
    return snapshot.id, files


def server(files: dict[str, bytes], calls: list[str]):
    def fetch(url: str) -> bytes:
        calls.append(url)
        name = url.removeprefix(release_url(REPO, ""))
        if name not in files:
            raise OSError(f"404 {url}")
        return files[name]

    return fetch


def test_downloads_the_newest_snapshot_once(published, tmp_path):
    snapshot_id, files = published
    calls: list[str] = []
    target = tmp_path / "snapshots"
    assert sync_snapshot(REPO, target, server(files, calls)) == snapshot_id
    assert snapshot_ids(target) == [snapshot_id]
    assert load_snapshot("latest", target).id == snapshot_id  # complete and its fingerprint checks out
    calls.clear()
    assert sync_snapshot(REPO, target, server(files, calls)) == snapshot_id
    assert calls == [release_url(REPO, "latest.json")]  # already there: nothing else fetched


def test_a_damaged_download_is_never_kept(published, tmp_path):
    snapshot_id, files = published
    files[f"prices-{snapshot_id}.parquet"] = files[f"prices-{snapshot_id}.parquet"][:-100] + b"x" * 100
    target = tmp_path / "snapshots"
    with pytest.raises(ValueError, match="damaged"):
        sync_snapshot(REPO, target, server(files, []))
    assert snapshot_ids(target) == []
