"""Download the official stock lists and write data/universes/<id>.json, showing what changed.

    python -m pipeline.universes            # fetch both lists, write them, print the changes
    python -m pipeline.universes --check    # only print the changes

Review the printed changes before committing the files: a broken source page must never silently change a market."""

import argparse
import io
import json
import urllib.request
from datetime import date

import pandas as pd

from qapital.config import UNIVERSES_DIR
from qapital.data.universe import Benchmark, RiskFree, Stock, Universe

USER_AGENT = {"User-Agent": "Mozilla/5.0 (compatible; Qapital-data/0.2; +https://github.com/)"}
NIFTY_URL = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
SP100_URL = "https://en.wikipedia.org/wiki/S%26P_100"
RBI_91_DAY_YIELD = 0.052599
RBI_SOURCE = (
    "RBI 91-day T-bill auction cut-off yield 5.2599%, press release 2 Sep 2026: "
    "https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63500"
)


def download(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=USER_AGENT), timeout=60) as response:
        return response.read()


def nifty50() -> Universe:
    table = pd.read_csv(io.BytesIO(download(NIFTY_URL)))
    table = table[table["Series"].str.strip() == "EQ"]
    stocks = [
        Stock(ticker=f"{symbol.strip()}.NS", name=company.strip(), sector=industry.strip())
        for symbol, company, industry in zip(table["Symbol"], table["Company Name"], table["Industry"], strict=True)
    ]
    return Universe(
        id="nifty50",
        name="NIFTY 50",
        country="India",
        currency="INR",
        benchmark=Benchmark(ticker="^NSEI", name="NIFTY 50 index"),
        risk_free=RiskFree(
            kind="constant",
            rate=RBI_91_DAY_YIELD,
            source=RBI_SOURCE,
            note="India has no free daily T-bill series; update this from the latest RBI auction result.",
        ),
        cost_model="india_delivery",
        list_source=NIFTY_URL,
        list_as_of=date.today().isoformat(),
        stocks=_expect(stocks, 50, "NIFTY 50"),
    )


def sp100() -> Universe:
    tables = pd.read_html(io.BytesIO(download(SP100_URL)))
    table = next(t for t in tables if {"Symbol", "Name", "Sector"} <= set(t.columns))
    stocks = [
        Stock(
            ticker=str(row.Symbol).strip().replace(".", "-"), name=str(row.Name).strip(), sector=str(row.Sector).strip()
        )
        for row in table.itertuples()
    ]
    return Universe(
        id="sp100",
        name="S&P 100",
        country="United States",
        currency="USD",
        benchmark=Benchmark(ticker="^GSPC", name="S&P 500 index"),
        risk_free=RiskFree(kind="series", ticker="^IRX", source="13-week US Treasury bill yield (Yahoo ^IRX), percent"),
        cost_model="us_equity",
        list_source=SP100_URL,
        list_as_of=date.today().isoformat(),
        stocks=_expect(stocks, 100, "S&P 100", tolerance=3),
    )


def _expect(stocks: list[Stock], size: int, name: str, tolerance: int = 0) -> list[Stock]:
    """Refuse a list whose size is off: that usually means the source page changed shape."""
    if abs(len(stocks) - size) > tolerance:
        raise ValueError(f"The {name} source returned {len(stocks)} stocks instead of about {size}; check the page.")
    return stocks


def changes(new: Universe) -> list[str]:
    path = UNIVERSES_DIR / f"{new.id}.json"
    if not path.exists():
        return [f"{new.id}: new list with {len(new.stocks)} stocks"]
    old = Universe.model_validate(json.loads(path.read_text(encoding="utf-8")))
    old_sectors, new_sectors = old.sectors, new.sectors
    lines = [f"{new.id}: + {ticker}" for ticker in sorted(set(new_sectors) - set(old_sectors))]
    lines += [f"{new.id}: - {ticker}" for ticker in sorted(set(old_sectors) - set(new_sectors))]
    lines += [
        f"{new.id}: {ticker} sector {old_sectors[ticker]!r} -> {new_sectors[ticker]!r}"
        for ticker in sorted(set(old_sectors) & set(new_sectors))
        if old_sectors[ticker] != new_sectors[ticker]
    ]
    return lines or [f"{new.id}: no changes"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="only print the changes; write nothing")
    args = parser.parse_args()
    UNIVERSES_DIR.mkdir(parents=True, exist_ok=True)
    for build in (nifty50, sp100):
        universe = build()
        print("\n".join(changes(universe)))
        if not args.check:
            path = UNIVERSES_DIR / f"{universe.id}.json"
            path.write_text(json.dumps(universe.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"wrote {path} ({len(universe.stocks)} stocks, {len(set(universe.sectors.values()))} sectors)")


if __name__ == "__main__":
    main()
