"""Time utilities using zoneinfo for timezone-aware datetimes."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def now(tz_name: str = "Asia/Shanghai") -> datetime:
    """Return current time in the given timezone."""
    return datetime.now(tz=ZoneInfo(tz_name))


def now_iso(tz_name: str = "Asia/Shanghai") -> str:
    """Return current time as an ISO format string in the given timezone."""
    return now(tz_name).isoformat()


def now_utc() -> datetime:
    """Return current UTC time."""
    return datetime.now(tz=UTC)


def now_utc_iso() -> str:
    """Return current UTC time as an ISO format string."""
    return now_utc().isoformat()


def minutes_since(dt: datetime) -> float:
    """Return minutes elapsed since the given datetime."""
    return (now_utc() - dt).total_seconds() / 60.0
