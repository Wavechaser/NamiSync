"""Canonical UTC timestamp representation shared by both databases."""

from __future__ import annotations

from datetime import datetime, timezone


def encode_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("timestamp must be UTC")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def decode_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("stored timestamp is not UTC")
    return parsed
