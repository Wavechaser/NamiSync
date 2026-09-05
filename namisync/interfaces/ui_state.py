"""Typed GUI-owned cosmetic state, separate from semantic planning settings."""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable, Final


UI_STATE_SCHEMA_VERSION: Final = 1
APPEARANCE_VALUE_VERSION: Final = 1
UI_STATE_MAX_BYTES: Final = 1024 * 1024
MAX_JAVASCRIPT_SAFE_INTEGER: Final = 9_007_199_254_740_991

_APPEARANCE_SECTION: Final = "appearance"
_LEGACY_KEYS: Final = frozenset(
    {"recent_sources", "recent_targets", "window", "columns", "sort"}
)


class UiStateFormatError(ValueError):
    """The cosmetic state file cannot be interpreted safely."""


class UiStateClosedError(RuntimeError):
    """The cosmetic state owner no longer accepts operations."""


class _ForwardUiStateError(UiStateFormatError):
    """The artifact belongs to a newer state or section schema."""


class _LegacyUiStateError(UiStateFormatError):
    """The artifact is the retired unversioned prototype."""


class ThemeMode(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class CosmeticDisposition(StrEnum):
    APPLIED = "applied"
    NOOP = "noop"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class AppearanceValue:
    theme: ThemeMode = ThemeMode.SYSTEM

    def __post_init__(self) -> None:
        if type(self.theme) is str:
            try:
                object.__setattr__(self, "theme", ThemeMode(self.theme))
            except ValueError as error:
                raise ValueError("appearance theme is invalid") from error
        elif not isinstance(self.theme, ThemeMode):
            raise TypeError("appearance theme must be a ThemeMode")


@dataclass(frozen=True, slots=True)
class UiState:
    appearance: AppearanceValue = AppearanceValue()


@dataclass(frozen=True, slots=True)
class CosmeticSectionSnapshot:
    section: str
    value_version: int
    revision: int
    dirty: bool
    value: AppearanceValue


@dataclass(frozen=True, slots=True)
class CosmeticReplaceResult(CosmeticSectionSnapshot):
    disposition: CosmeticDisposition


class CosmeticSubscription:
    """Atomic registration receipt carrying the subscribed current snapshot."""

    __slots__ = ("snapshot", "_close_lock", "_unsubscribe")

    def __init__(
        self,
        snapshot: CosmeticSectionSnapshot,
        unsubscribe: Callable[[], None],
    ) -> None:
        self.snapshot = snapshot
        self._close_lock = threading.Lock()
        self._unsubscribe: Callable[[], None] | None = unsubscribe

    def close(self) -> None:
        with self._close_lock:
            unsubscribe = self._unsubscribe
            self._unsubscribe = None
        if unsubscribe is not None:
            unsubscribe()

    def __enter__(self) -> CosmeticSubscription:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class _LoadedState:
    value: UiState
    dirty: bool
    persistence_blocked: bool


@dataclass(frozen=True, slots=True)
class _PendingWrite:
    generation: int
    value: UiState
    deadline_ns: int


class UiStateOwner:
    """Process-local authority for the strict cosmetic state document."""

    def __init__(
        self, path: str | Path, *, write_delay_seconds: float = 0.250,
    ) -> None:
        if isinstance(write_delay_seconds, bool) or not isinstance(write_delay_seconds, (int, float)):
            raise TypeError("write delay must be a finite nonnegative number")
        if write_delay_seconds < 0 or (
            isinstance(write_delay_seconds, float) and not math.isfinite(write_delay_seconds)
        ):
            raise ValueError("write delay must be a finite nonnegative number")
        self._write_delay_ns = (
            int(write_delay_seconds) * 1_000_000_000
            + int((write_delay_seconds % 1) * 1_000_000_000)
        )
        self.path = Path(path).resolve()
        loaded = _load_state(self.path)

        self._condition = threading.Condition(threading.RLock())
        self._close_lock = threading.Lock()
        self._accepting = True
        self._closed = False
        self._value = loaded.value
        self._appearance_revision = 0
        self._document_generation = 0
        self._dirty = loaded.dirty
        self._persistence_blocked = loaded.persistence_blocked
        self._current_generation_attempted = False
        self._pending_write: _PendingWrite | None = None
        self._active_generation: int | None = None
        self._writer_thread: threading.Thread | None = None
        self._next_subscriber = 0
        self._appearance_subscribers: dict[
            int, Callable[[CosmeticSectionSnapshot], None]
        ] = {}

    def read_section(
        self,
        section: str,
        value_version: int,
    ) -> CosmeticSectionSnapshot:
        _validate_section(section, value_version)
        with self._condition:
            self._require_open_locked()
            return self._snapshot_locked()

    def replace_section(
        self,
        section: str,
        value_version: int,
        expected_revision: int,
        value: AppearanceValue,
    ) -> CosmeticReplaceResult:
        _validate_section(section, value_version)
        _validate_revision(expected_revision)
        if not isinstance(value, AppearanceValue):
            raise TypeError("appearance replacement requires AppearanceValue")

        subscribers: tuple[Callable[[CosmeticSectionSnapshot], None], ...] = ()
        notification: CosmeticSectionSnapshot | None = None
        with self._condition:
            self._require_open_locked()
            current = self._value.appearance
            if expected_revision != self._appearance_revision:
                disposition = (
                    CosmeticDisposition.NOOP
                    if value == current
                    else CosmeticDisposition.CONFLICT
                )
                return self._replace_result_locked(disposition)

            if value == current:
                if self._dirty and not self._persistence_blocked:
                    self._schedule_current_locked()
                return self._replace_result_locked(CosmeticDisposition.NOOP)

            if self._appearance_revision >= MAX_JAVASCRIPT_SAFE_INTEGER:
                raise OverflowError("appearance revision is exhausted")
            self._value = UiState(appearance=value)
            self._appearance_revision += 1
            self._document_generation += 1
            self._dirty = True
            self._current_generation_attempted = False
            if not self._persistence_blocked:
                self._schedule_current_locked()
            notification = self._snapshot_locked()
            subscribers = tuple(self._appearance_subscribers.values())
            result = self._replace_result_locked(CosmeticDisposition.APPLIED)

        assert notification is not None
        _notify_subscribers(subscribers, notification)
        return result

    def subscribe(
        self,
        section: str,
        callback: Callable[[CosmeticSectionSnapshot], None],
    ) -> CosmeticSubscription:
        _validate_section(section, APPEARANCE_VALUE_VERSION)
        if not callable(callback):
            raise TypeError("cosmetic subscriber must be callable")
        with self._condition:
            self._require_open_locked()
            token = self._next_subscriber
            self._next_subscriber += 1
            self._appearance_subscribers[token] = callback
            snapshot = self._snapshot_locked()
            return CosmeticSubscription(
                snapshot,
                lambda: self._unsubscribe(token),
            )

    def close(self) -> None:
        with self._close_lock:
            with self._condition:
                if self._closed:
                    return
                self._accepting = False
                self._pending_write = None
                self._appearance_subscribers.clear()
                self._condition.notify_all()
                writer = self._writer_thread

            if writer is not None and writer is not threading.current_thread():
                writer.join()

            with self._condition:
                should_flush = (
                    self._dirty
                    and not self._persistence_blocked
                    and not self._current_generation_attempted
                )
                if should_flush:
                    generation = self._document_generation
                    value = self._value
                    self._current_generation_attempted = True
                else:
                    generation = -1
                    value = self._value

            if should_flush:
                succeeded = _write_state(self.path, value)
                if succeeded:
                    with self._condition:
                        if generation == self._document_generation:
                            self._dirty = False

            with self._condition:
                self._closed = True
                self._condition.notify_all()

    def __enter__(self) -> UiStateOwner:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _require_open_locked(self) -> None:
        if not self._accepting:
            raise UiStateClosedError("cosmetic state owner is closed")

    def _snapshot_locked(self) -> CosmeticSectionSnapshot:
        return CosmeticSectionSnapshot(
            section=_APPEARANCE_SECTION,
            value_version=APPEARANCE_VALUE_VERSION,
            revision=self._appearance_revision,
            dirty=self._dirty,
            value=self._value.appearance,
        )

    def _replace_result_locked(
        self,
        disposition: CosmeticDisposition,
    ) -> CosmeticReplaceResult:
        snapshot = self._snapshot_locked()
        return CosmeticReplaceResult(
            section=snapshot.section,
            value_version=snapshot.value_version,
            revision=snapshot.revision,
            dirty=snapshot.dirty,
            value=snapshot.value,
            disposition=disposition,
        )

    def _schedule_current_locked(self) -> None:
        generation = self._document_generation
        if self._active_generation == generation:
            return
        if (
            self._pending_write is not None
            and self._pending_write.generation == generation
        ):
            return
        self._pending_write = _PendingWrite(
            generation=generation,
            value=self._value,
            deadline_ns=time.monotonic_ns() + self._write_delay_ns,
        )
        if self._writer_thread is None:
            writer = threading.Thread(
                target=self._writer_loop,
                name="namisync-ui-state-writer",
                daemon=True,
            )
            self._writer_thread = writer
            try:
                writer.start()
            except Exception as error:
                self._writer_thread = None
                self._pending_write = None
                _log_failure("ui_state.writer_start_failed", error)
                return
        self._condition.notify_all()

    def _writer_loop(self) -> None:
        while True:
            with self._condition:
                while self._accepting and self._pending_write is None:
                    self._condition.wait()
                if not self._accepting:
                    return
                pending = self._pending_write
                assert pending is not None
                remaining_ns = pending.deadline_ns - time.monotonic_ns()
                if remaining_ns > 0:
                    self._condition.wait(
                        min(remaining_ns, int(threading.TIMEOUT_MAX * 1_000_000_000))
                        / 1_000_000_000
                    )
                    continue
                if pending is not self._pending_write:
                    continue
                self._pending_write = None
                self._active_generation = pending.generation
                if pending.generation == self._document_generation:
                    self._current_generation_attempted = True

            succeeded = _write_state(self.path, pending.value)

            with self._condition:
                self._active_generation = None
                if succeeded and pending.generation == self._document_generation:
                    self._dirty = False
                self._condition.notify_all()

    def _unsubscribe(self, token: int) -> None:
        with self._condition:
            self._appearance_subscribers.pop(token, None)


def _validate_section(section: str, value_version: int) -> None:
    if section != _APPEARANCE_SECTION:
        raise ValueError("cosmetic section is unsupported")
    if type(value_version) is not int or value_version != APPEARANCE_VALUE_VERSION:
        raise ValueError("cosmetic value version is unsupported")


def _validate_revision(value: int) -> None:
    if (
        type(value) is not int
        or value < 0
        or value > MAX_JAVASCRIPT_SAFE_INTEGER
    ):
        raise ValueError("cosmetic revision is invalid")


def _notify_subscribers(
    subscribers: tuple[Callable[[CosmeticSectionSnapshot], None], ...],
    snapshot: CosmeticSectionSnapshot,
) -> None:
    for callback in subscribers:
        try:
            callback(snapshot)
        except Exception as error:
            _log_failure("ui_state.subscriber_failed", error)


def _load_state(path: Path) -> _LoadedState:
    try:
        payload = _read_bounded(path)
    except FileNotFoundError:
        return _LoadedState(UiState(), dirty=False, persistence_blocked=False)
    except UiStateFormatError as error:
        _log_failure("ui_state.load_recovered", error)
        return _LoadedState(UiState(), dirty=True, persistence_blocked=False)
    except OSError as error:
        _log_failure("ui_state.load_unavailable", error)
        return _LoadedState(UiState(), dirty=True, persistence_blocked=True)

    try:
        value = _decode_state(payload)
    except _ForwardUiStateError as error:
        _log_failure("ui_state.load_unsupported", error)
        return _LoadedState(UiState(), dirty=True, persistence_blocked=True)
    except (
        UiStateFormatError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
    ) as error:
        event = (
            "ui_state.load_legacy"
            if isinstance(error, _LegacyUiStateError)
            else "ui_state.load_recovered"
        )
        _log_failure(event, error)
        return _LoadedState(UiState(), dirty=True, persistence_blocked=False)
    return _LoadedState(value, dirty=False, persistence_blocked=False)


def _read_bounded(path: Path) -> bytes:
    with path.open("rb") as stream:
        payload = stream.read(UI_STATE_MAX_BYTES + 1)
    if len(payload) > UI_STATE_MAX_BYTES:
        raise UiStateFormatError("ui-state.json exceeds its size limit")
    return payload


def _decode_state(payload: bytes) -> UiState:
    decoded = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )
    if not isinstance(decoded, dict):
        raise UiStateFormatError("ui-state.json must contain one object")
    if frozenset(decoded) == _LEGACY_KEYS:
        raise _LegacyUiStateError("ui-state.json uses the retired prototype")

    schema_version = decoded.get("schema_version")
    if type(schema_version) is int and schema_version > UI_STATE_SCHEMA_VERSION:
        raise _ForwardUiStateError("ui-state.json belongs to a newer schema")
    if type(schema_version) is not int or schema_version != UI_STATE_SCHEMA_VERSION:
        raise UiStateFormatError("ui-state.json schema version is invalid")
    if set(decoded) != {"schema_version", "sections"}:
        raise UiStateFormatError("ui-state.json has missing or unknown keys")

    sections = decoded["sections"]
    if not isinstance(sections, dict) or set(sections) != {_APPEARANCE_SECTION}:
        raise UiStateFormatError("ui-state.json sections are invalid")
    appearance = sections[_APPEARANCE_SECTION]
    if not isinstance(appearance, dict):
        raise UiStateFormatError("appearance section must be an object")
    value_version = appearance.get("value_version")
    if type(value_version) is int and value_version > APPEARANCE_VALUE_VERSION:
        raise _ForwardUiStateError("appearance belongs to a newer value schema")
    if (
        type(value_version) is not int
        or value_version != APPEARANCE_VALUE_VERSION
        or set(appearance) != {"value_version", "value"}
    ):
        raise UiStateFormatError("appearance section shape is invalid")
    value = appearance["value"]
    if not isinstance(value, dict) or set(value) != {"theme"}:
        raise UiStateFormatError("appearance value shape is invalid")
    theme = value["theme"]
    if type(theme) is not str:
        raise UiStateFormatError("appearance theme is invalid")
    try:
        return UiState(appearance=AppearanceValue(ThemeMode(theme)))
    except ValueError as error:
        raise UiStateFormatError("appearance theme is invalid") from error


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise UiStateFormatError("ui-state.json contains a duplicate key")
        value[key] = item
    return value


def _reject_constant(_value: str) -> object:
    raise UiStateFormatError("ui-state.json contains a non-finite number")


def _encode_state(value: UiState) -> bytes:
    payload = {
        "schema_version": UI_STATE_SCHEMA_VERSION,
        "sections": {
            _APPEARANCE_SECTION: {
                "value_version": APPEARANCE_VALUE_VERSION,
                "value": {"theme": value.appearance.theme.value},
            }
        },
    }
    encoded = (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    if len(encoded) > UI_STATE_MAX_BYTES:
        raise UiStateFormatError("ui-state.json exceeds its size limit")
    return encoded


def _write_state(path: Path, value: UiState) -> bool:
    try:
        _atomic_write(path, _encode_state(value))
    except Exception as error:
        _log_failure("ui_state.save_failed", error)
        return False
    return True


def _log_failure(event: str, error: Exception) -> None:
    logging.getLogger(__name__).warning(
        "%s exception_type=%s",
        event,
        type(error).__name__,
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
