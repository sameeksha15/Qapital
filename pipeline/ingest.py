"""Download prices for every universe, check their quality and save a dated snapshot.

    python -m pipeline.ingest                    # all universes, prices from 2015
    python -m pipeline.ingest --start 2018-01-01

Runs nightly in GitHub Actions (.github/workflows/data.yml). This is the only code that calls Yahoo Finance; the app
itself only reads snapshots (hard rule 7)."""

import argparse
import time
from datetime import UTC, datetime

import pandas as pd
import yfinance as yf

from qapital.config import SNAPSHOTS_DIR
from qapital.data.quality import check_ticker, market_calendar
from qapital.data.snapshot import write_snapshot
from qapital.data.universe import load_universe, universe_ids

START = "2015-01-01"
BATCH = 40
RETRIES = 2


def download(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Adjusted daily closes before `end`, one column per ticker; tickers that fail are retried one by one."""
    frames = [_closes(tickers[i : i + BATCH], start, end) for i in range(0, len(tickers), BATCH)]
    prices = pd.concat(frames, axis=1)
    for attempt in range(RETRIES):
        missing = [t for t in tickers if t not in prices or prices[t].dropna().empty]
        if not missing:
            break
        print(f"retrying {len(missing)} tickers (attempt {attempt + 1}): {', '.join(missing)}")
        time.sleep(5)
        retried = pd.concat([_closes([t], start, end) for t in missing], axis=1)
        prices = prices.drop(columns=[t for t in missing if t in prices]).join(retried, how="outer")
    return prices.reindex(columns=tickers)


def _closes(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False, threads=True, group_by="column")
    if raw.empty:
        return pd.DataFrame(columns=tickers)
    closes = raw["Close"]
    return closes.to_frame(tickers[0]) if isinstance(closes, pd.Series) else closes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default=START, help=f"first date of prices (default {START})")
    parser.add_argument(
        "--end",
        default=datetime.now(UTC).date().isoformat(),
        help="stop before this date (default: today in UTC, so a trading day still in progress is never saved)",
    )
    args = parser.parse_args()

    universes = [load_universe(universe_id) for universe_id in universe_ids()]
    extra = {u.benchmark.ticker for u in universes} | {u.risk_free.ticker for u in universes if u.risk_free.ticker}
    tickers = sorted({t for u in universes for t in u.tickers} | extra)
    print(f"downloading {len(tickers)} series from {args.start} to before {args.end} ...")
    prices = download(tickers, args.start, args.end)

    quality = {}
    for universe in universes:
        calendar = market_calendar(prices, universe.benchmark.ticker)
        quality[universe.id] = {t: check_ticker(t, prices[t], calendar) for t in universe.tickers}
        usable = sum(q.usable for q in quality[universe.id].values())
        print(f"\n{universe.name}: {usable} of {len(universe.tickers)} stocks usable, {len(calendar)} trading days")
        for ticker, q in quality[universe.id].items():
            for line in q.problems:
                print(f"  EXCLUDED {ticker}: {line}")
            for line in q.warnings:
                print(f"  note     {ticker}: {line}")

    sources = {
        "prices": f"Yahoo Finance via yfinance {yf.__version__} (auto_adjust=True)",
        "lists": {u.id: u.list_source for u in universes},
    }
    folder = write_snapshot(prices, universes, quality, sources, SNAPSHOTS_DIR)
    print(f"\nwrote {folder}")


if __name__ == "__main__":
    main()
