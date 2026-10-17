"""Where Qapital finds its data: the repo's data/ folder, or wherever QAPITAL_DATA points (e.g. in Docker)."""

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("QAPITAL_DATA", Path(__file__).resolve().parents[2] / "data"))
UNIVERSES_DIR = DATA_DIR / "universes"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
