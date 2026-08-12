"""Bounded process-local authority for native folder selections."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from uuid import uuid4


_CAPACITY = 32
_TTL_SECONDS = 1_800.0
_TOKEN = re.compile(r"[0-9a-f]{32}")
_SLOT_ID = re.compile(r"slot-[0-9a-f]{32}")


class SlotUnavailableError(LookupError):
    """An opaque folder slot is absent, expired, or purpose-mismatched."""


@dataclass(slots=True)
class _FolderSlot:
    path: str
    purpose: str
    display: str
    expires_at: float
    last_used: float


class FolderSlotTable:
    """Retain native paths behind fixed-lifetime, purpose-bound opaque ids."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        token: Callable[[], str] | None = None,
    ) -> None:
        if not callable(clock):
            raise TypeError("clock must be callable")
        if token is not None and not callable(token):
            raise TypeError("token must be callable")
        self._clock = clock
        self._token = token if token is not None else _new_token
        self._entries: dict[str, _FolderSlot] = {}
        self._lock = Lock()

    def store(self, path: str, *, purpose: str) -> tuple[str, str]:
        """Insert one native selection and return only opaque presentation data."""

        if type(purpose) is not str or purpose not in {"source", "target"}:
            raise ValueError("folder slot purpose must be source or target")
        _require_valid_text(path, label="path")
        display = path

        with self._lock:
            now = self._clock()
            self._sweep(now)
            slot_id = self._mint_id()
            if len(self._entries) == _CAPACITY:
                evicted = min(
                    self._entries,
                    key=lambda candidate: (
                        self._entries[candidate].last_used,
                        candidate,
                    ),
                )
                del self._entries[evicted]
            self._entries[slot_id] = _FolderSlot(
                path=path,
                purpose=purpose,
                display=display,
                expires_at=now + _TTL_SECONDS,
                last_used=now,
            )
            return slot_id, display

    def resolve_pair(self, source_id: str, target_id: str) -> tuple[str, str]:
        """Atomically resolve one live purpose-correct pair without consuming it."""

        with self._lock:
            now = self._clock()
            self._sweep(now)
            if (
                type(source_id) is not str
                or _SLOT_ID.fullmatch(source_id) is None
                or type(target_id) is not str
                or _SLOT_ID.fullmatch(target_id) is None
            ):
                raise SlotUnavailableError("folder slot is unavailable")
            source = self._entries.get(source_id)
            target = self._entries.get(target_id)
            if (
                source is None
                or target is None
                or source.purpose != "source"
                or target.purpose != "target"
            ):
                raise SlotUnavailableError("folder slot is unavailable")
            source.last_used = now
            target.last_used = now
            return source.path, target.path

    def _sweep(self, now: float) -> None:
        expired = tuple(
            slot_id
            for slot_id, entry in self._entries.items()
            if entry.expires_at <= now
        )
        for slot_id in expired:
            del self._entries[slot_id]

    def _mint_id(self) -> str:
        while True:
            token = self._token()
            if type(token) is not str or _TOKEN.fullmatch(token) is None:
                raise ValueError("folder slot token must be 32 lowercase hex digits")
            slot_id = f"slot-{token}"
            if slot_id not in self._entries:
                return slot_id


def _new_token() -> str:
    return uuid4().hex


def _require_valid_text(value: object, *, label: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"folder slot {label} must be a nonempty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"folder slot {label} must be valid Unicode") from error


__all__ = ["FolderSlotTable", "SlotUnavailableError"]
