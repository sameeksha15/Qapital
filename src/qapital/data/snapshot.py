"""Price snapshots: one folder per data date, data/snapshots/<YYYY-MM-DD>/, holding prices.parquet (adjusted closes,
one column per ticker, including benchmarks and risk-free series) and manifest.json (sources, hashes, quality).

Every result records the snapshot it used, so the same settings + seed + snapshot always give the same answer."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from qapital.config import SNAPSHOTS_DIR
from qapital.data.quality import TickerQuality, clean, market_calendar
from qapital.data.universe import Universe

PRICES_FILE = "prices.parquet"
MANIFEST_FILE = "manifest.json"


@dataclass
class Snapshot:
    id: str
    path: Path
    prices: pd.DataFrame  # raw adjusted closes on the union of all markets' trading days
    manifest: dict

    def market_prices(self, universe: Universe) -> pd.DataFrame:
        """Cleaned prices of the universe's usable stocks, on its own market's trading days."""
        quality = self.manifest["universes"][universe.id]["quality"]
        usable = [t for t in universe.tickers if t in self.prices and quality.get(t, {}).get("usable", False)]
        calendar = market_calendar(self.prices, universe.benchmark.ticker)
        return clean(self.prices[usable], calendar)

    def quality(self, universe: Universe) -> dict[str, dict]:
        return self.manifest["universes"][universe.id]["quality"]

    def risk_free(self, universe: Universe) -> pd.Series:
        """Yearly risk-free rate (decimal) on each of the market's trading days."""
        calendar = market_calendar(self.prices, universe.benchmark.ticker)
        rule = universe.risk_free
        if rule.kind == "constant":
            return pd.Series(float(rule.rate or 0.0), index=calendar)
        series = self.prices[rule.ticker].reindex(calendar).ffill() / 100
        return series.bfill()


def write_snapshot(
    prices: pd.DataFrame,
    universes: list[Universe],
    quality: dict[str, dict[str, TickerQuality]],
    sources: dict,
    directory: Path = SNAPSHOTS_DIR,
) -> Path:
    """Save prices and a manifest under the date of the last trading day in the data."""
    prices = prices.sort_index().astype(float)
    prices.index = pd.DatetimeIndex(prices.index).tz_localize(None).normalize()
    prices.index.name = "date"
    snapshot_id = prices.index.max().date().isoformat()
    folder = directory / snapshot_id
    folder.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(folder / PRICES_FILE, engine="pyarrow")
    manifest = {
        "snapshot": snapshot_id,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "start": prices.index.min().date().isoformat(),
        "end": snapshot_id,
        "price_field": "adjusted close (splits and dividends)",
        "sources": sources,
        "files": {
            PRICES_FILE: {"sha256": _sha256(folder / PRICES_FILE), "rows": len(prices), "columns": prices.shape[1]}
        },
        "universes": {
            universe.id: {
                "name": universe.name,
                "list_as_of": universe.list_as_of,
                "list_sha256": hashlib.sha256(universe.model_dump_json().encode()).hexdigest(),
                "stocks": len(universe.stocks),
                "usable": sum(q.usable for q in quality[universe.id].values()),
                "quality": {ticker: q.as_dict() for ticker, q in quality[universe.id].items()},
            }
            for universe in universes
        },
    }
    (folder / MANIFEST_FILE).write_text(json.dumps(manifest, indent=1, default=_plain) + "\n", encoding="utf-8")
    return folder


def snapshot_ids(directory: Path = SNAPSHOTS_DIR) -> list[str]:
    return sorted(path.name for path in directory.glob("*") if (path / MANIFEST_FILE).exists())


def load_snapshot(snapshot_id: str = "latest", directory: Path = SNAPSHOTS_DIR) -> Snapshot:
    ids = snapshot_ids(directory)
    if not ids:
        raise ValueError(f"No price snapshots in {directory}. Run: python -m pipeline.ingest")
    if snapshot_id == "latest":
        snapshot_id = ids[-1]
    if snapshot_id not in ids:
        raise ValueError(f"Snapshot {snapshot_id} isn't available. Available: {', '.join(ids)}.")
    folder = directory / snapshot_id
    manifest = json.loads((folder / MANIFEST_FILE).read_text(encoding="utf-8"))
    expected = manifest["files"][PRICES_FILE]["sha256"]
    if _sha256(folder / PRICES_FILE) != expected:
        raise ValueError(f"Snapshot {snapshot_id} is damaged (its price file doesn't match the manifest).")
    return Snapshot(id=snapshot_id, path=folder, prices=pd.read_parquet(folder / PRICES_FILE), manifest=manifest)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plain(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Can't write {type(value).__name__} to the manifest")
