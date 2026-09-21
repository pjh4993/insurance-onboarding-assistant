"""Small shared helpers: clock, date parsing and ISO formatting."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(UTC)


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
