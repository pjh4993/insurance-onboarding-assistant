"""Small shared helpers: clock, date parsing and ISO formatting."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(UTC)


# The calendar a market's customers live by: "bought today" and "departs tomorrow" mean their local day.
MARKET_TIMEZONES = {"KR": ZoneInfo("Asia/Seoul"), "US": ZoneInfo("America/New_York")}


def market_today(market: str, now: datetime) -> date:
    """`now` as the date on the market's local calendar (UTC for an unknown market)."""
    return now.astimezone(MARKET_TIMEZONES.get(market, UTC)).date()


def parse_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def iso(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return dt.isoformat()
