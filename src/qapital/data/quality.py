"""Quality checks for downloaded prices, each stock measured against its own market's trading days.

Problems make a stock unusable (no prices, non-positive prices, no recent price). Warnings are worth a look but keep
the stock: long gaps, frozen prices, very large one-day moves (often an unadjusted split) and late listings."""

from dataclasses import asdict, dataclass, field

import pandas as pd

MAX_FILL_DAYS = 3  # missing days in a row that may be filled with the last price (holidays, short suspensions)
FROZEN_DAYS = 10  # the same price this many days in a row looks like a dead feed
BIG_MOVE = 0.5  # a one-day move above 50% often means an unadjusted split or a bad tick
RECENT_DAYS = 5  # a usable stock has a price within its market's last 5 trading days


@dataclass
class TickerQuality:
    ticker: str
    first: str | None = None
    last: str | None = None
    coverage: float = 0.0  # share of the market's trading days with a price, from the first price on
    longest_gap: int = 0  # most missing trading days in a row
    frozen_days: int = 0  # most days in a row with an unchanged price
    biggest_move: float = 0.0  # largest one-day move, as a decimal
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return not self.problems

    def as_dict(self) -> dict:
        return {**asdict(self), "usable": self.usable}


def market_calendar(prices: pd.DataFrame, benchmark: str) -> pd.DatetimeIndex:
    """The market's trading days: the days its benchmark index has a price."""
    if benchmark not in prices or prices[benchmark].dropna().empty:
        raise ValueError(f"No prices for the benchmark {benchmark}; can't tell which days the market traded.")
    return pd.DatetimeIndex(prices[benchmark].dropna().index)


def check_ticker(ticker: str, prices: pd.Series, calendar: pd.DatetimeIndex) -> TickerQuality:
    series = prices.reindex(calendar)
    valid = series.dropna()
    quality = TickerQuality(ticker=ticker)
    if valid.empty:
        quality.problems.append("no prices at all")
        return quality
    first, last = valid.index[0], valid.index[-1]
    quality.first, quality.last = first.date().isoformat(), last.date().isoformat()
    if (valid <= 0).any():
        quality.problems.append("zero or negative prices")
    if last < calendar[-min(RECENT_DAYS, len(calendar))]:
        quality.problems.append(f"no price since {quality.last} (delisted, renamed or stale)")

    span = series.loc[first:last]
    quality.coverage = float(span.notna().mean())
    quality.longest_gap = _longest_run(span.isna())
    if quality.longest_gap > MAX_FILL_DAYS:
        quality.warnings.append(f"{quality.longest_gap} trading days in a row without a price")

    # Only real prices count here: a gap filled with the last price is not a frozen feed.
    quality.frozen_days = _longest_run(valid.diff().eq(0)) + 1 if len(valid) > 1 else 0
    if quality.frozen_days >= FROZEN_DAYS:
        quality.warnings.append(f"price unchanged for {quality.frozen_days} trading days in a row")

    moves = span.ffill().pct_change().dropna()
    if len(moves):
        quality.biggest_move = float(moves.abs().max())
        if quality.biggest_move > BIG_MOVE:
            day = moves.abs().idxmax().date().isoformat()
            quality.warnings.append(f"a {quality.biggest_move:.0%} move on {day}: check for an unadjusted split")
    if first > calendar[0]:
        quality.warnings.append(f"prices start on {quality.first} (listed later than the snapshot start)")
    return quality


def clean(prices: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """Prices on the market's trading days. Short gaps take the last price; nothing is filled before a stock's first
    price or after its last one, and longer gaps stay empty."""
    on_calendar = prices.reindex(calendar)
    filled = on_calendar.ffill(limit=MAX_FILL_DAYS)
    started = on_calendar.notna().cummax()
    still_trading = on_calendar.notna()[::-1].cummax()[::-1]
    return filled.where(started & still_trading)


def _longest_run(flags: pd.Series) -> int:
    """Length of the longest run of True values."""
    longest = current = 0
    for flag in flags.to_numpy():
        current = current + 1 if flag else 0
        longest = max(longest, current)
    return longest
