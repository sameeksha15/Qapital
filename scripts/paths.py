"""Where the scripts, experiments and tests read and write files. MARKET_FILE, PRICES_CSV and LEGACY_RETURNS are
older local data sets that aren't published; the tests that use them skip when they are missing."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKET_FILE = ROOT / "data" / "markets" / "india.json"
PRICES_CSV = ROOT / "data" / "cache" / "prices.csv"
LEGACY_RETURNS = ROOT / "data" / "legacy" / "response_1791528369368.json"  # the 48-stock file the website was built on
RESULTS = ROOT / "research" / "results"
WEB_PUBLIC = ROOT / "web" / "public"
