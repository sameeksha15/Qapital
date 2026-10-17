"""Getting the newest price snapshot from the project's GitHub release, where the nightly data job publishes it.

The release named "data" holds `latest.json` ({"snapshot": "<date>"}) and, for each date, `prices-<date>.parquet` and
`manifest-<date>.json`. A downloaded snapshot is checked against the fingerprint in its manifest before it is used, so
a broken download is never served. Only our own published files are fetched; no market-data provider is called."""

import json
import logging
import shutil
import tempfile
import urllib.request
from pathlib import Path

from qapital.config import SNAPSHOTS_DIR
from qapital.data.snapshot import MANIFEST_FILE, PRICES_FILE, load_snapshot, snapshot_ids

log = logging.getLogger("qapital.data")
RELEASE = "data"
KEEP = 3  # snapshots kept on disk; older ones are removed
TIMEOUT_S = 60


def release_url(repo: str, name: str) -> str:
    return f"https://github.com/{repo}/releases/download/{RELEASE}/{name}"


def sync_snapshot(repo: str, directory: Path = SNAPSHOTS_DIR, fetch=None) -> str | None:
    """Download the newest published snapshot into `directory` unless it is already there; returns its id.
    `fetch(url) -> bytes` can be replaced in tests."""
    fetch = fetch or _fetch
    latest = json.loads(fetch(release_url(repo, "latest.json")))["snapshot"]
    if latest in snapshot_ids(directory):
        return latest
    with tempfile.TemporaryDirectory(dir=directory.parent if directory.parent.exists() else None) as scratch:
        folder = Path(scratch) / latest
        folder.mkdir()
        (folder / MANIFEST_FILE).write_bytes(fetch(release_url(repo, f"manifest-{latest}.json")))
        (folder / PRICES_FILE).write_bytes(fetch(release_url(repo, f"prices-{latest}.parquet")))
        load_snapshot(latest, Path(scratch))  # raises if the prices don't match the manifest's fingerprint
        directory.mkdir(parents=True, exist_ok=True)
        shutil.move(str(folder), str(directory / latest))
    for old in snapshot_ids(directory)[:-KEEP]:
        shutil.rmtree(directory / old, ignore_errors=True)
    log.info("Downloaded price snapshot %s", latest)
    return latest


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "qapital"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return response.read()
