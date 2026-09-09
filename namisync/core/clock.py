"""Injected wall-clock contract shared across product layers."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return an aware UTC timestamp."""