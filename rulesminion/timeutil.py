"""IST (Asia/Kolkata) helpers for digest headers and snapshot timestamps."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


def now_ist() -> datetime:
    return datetime.now(IST)


def format_ist(dt: datetime) -> str:
    return dt.astimezone(IST).strftime("%Y-%m-%d %H:%M IST")


def now_ist_label() -> str:
    return format_ist(now_ist())


def from_unix(ts: int | float) -> datetime:
    return datetime.fromtimestamp(float(ts), tz=UTC)


def from_iso(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def iso_to_ist_label(value: str) -> str | None:
    dt = from_iso(value)
    return format_ist(dt) if dt else None


def unix_to_ist_label(ts: int | float) -> str:
    return format_ist(from_unix(ts))
