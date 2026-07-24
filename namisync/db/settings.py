"""Schema-versioned semantic defaults stored outside the live databases."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from types import TracebackType

from namisync.core.planning import (
    DeletionPolicy,
    FilterSet,
    PreservationPolicy,
    SyncOptions,
)


SETTINGS_SCHEMA_VERSION = 1


class SettingsFormatError(ValueError):
    """The semantic settings file is malformed or from another schema."""


@dataclass(frozen=True, slots=True)
class SemanticSettings:
    filters: FilterSet = FilterSet()
    deletion_policy: DeletionPolicy = DeletionPolicy.TRASH
    trash_on_update: bool = True
    preservation: PreservationPolicy = PreservationPolicy()
    propagate_source_casing: bool = False

    def __post_init__(self) -> None:
        if self.deletion_policy not in {
            DeletionPolicy.TRASH,
            DeletionPolicy.ADDITIVE,
        }:
            raise ValueError("semantic defaults cannot enable hidden mirror deletion")

    def to_sync_options(self) -> SyncOptions:
        """Return the immutable planning snapshot represented by these defaults."""

        return SyncOptions(
            deletion_policy=self.deletion_policy,
            preservation=self.preservation,
            filters=self.filters,
            trash_on_update=self.trash_on_update,
            propagate_source_casing=self.propagate_source_casing,
        )


@dataclass(frozen=True, slots=True)
class SemanticSettingsPatch:
    """A partial commit; omitted keys retain the value re-read under the mutex."""

    filters: FilterSet | None = None
    deletion_policy: DeletionPolicy | None = None
    trash_on_update: bool | None = None
    preservation: PreservationPolicy | None = None
    propagate_source_casing: bool | None = None


class SemanticSettingsStore:
    """Atomic settings reads and cross-process serialized partial commits."""

    def __init__(
        self,
        path: str | Path,
        *,
        mutex_timeout_seconds: float = 30.0,
    ) -> None:
        if mutex_timeout_seconds <= 0:
            raise ValueError("settings mutex timeout must be positive")
        self.path = Path(path).resolve()
        self._mutex_timeout_seconds = mutex_timeout_seconds

    @property
    def mutex_name(self) -> str:
        material = os.path.normcase(str(self.path)).encode("utf-8")
        digest = hashlib.sha256(material).hexdigest()
        return rf"Local\NamiSync.Settings.{digest}"

    def read(self) -> SemanticSettings:
        try:
            payload = self.path.read_bytes()
        except FileNotFoundError:
            return SemanticSettings()
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SettingsFormatError("settings.json is not valid UTF-8 JSON") from error
        return _decode_settings(value)

    def commit(self, patch: SemanticSettingsPatch) -> SemanticSettings:
        if not isinstance(patch, SemanticSettingsPatch):
            raise TypeError("semantic settings commit requires SemanticSettingsPatch")
        with _WindowsNamedMutex(
            self.mutex_name,
            timeout_seconds=self._mutex_timeout_seconds,
        ):
            current = self.read()
            updated = _apply_patch(current, patch)
            if updated != current or not self.path.exists():
                _atomic_write(self.path, _encode_settings(updated))
            return updated


class _WindowsNamedMutex:
    _WAIT_OBJECT_0 = 0x00000000
    _WAIT_ABANDONED = 0x00000080
    _WAIT_TIMEOUT = 0x00000102
    _WAIT_FAILED = 0xFFFFFFFF

    def __init__(self, name: str, *, timeout_seconds: float) -> None:
        if os.name != "nt":
            raise OSError("semantic settings require a Windows named mutex")
        self._name = name
        self._timeout_ms = max(1, int(timeout_seconds * 1000))
        self._handle: int | None = None
        self._release = None
        self._close = None

    def __enter__(self) -> _WindowsNamedMutex:
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel32.CreateMutexW
        create.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        create.restype = wintypes.HANDLE
        wait = kernel32.WaitForSingleObject
        wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        wait.restype = wintypes.DWORD
        self._release = kernel32.ReleaseMutex
        self._release.argtypes = (wintypes.HANDLE,)
        self._release.restype = wintypes.BOOL
        self._close = kernel32.CloseHandle
        self._close.argtypes = (wintypes.HANDLE,)
        self._close.restype = wintypes.BOOL

        handle = create(None, False, self._name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        outcome = wait(handle, self._timeout_ms)
        if outcome in (self._WAIT_OBJECT_0, self._WAIT_ABANDONED):
            self._handle = handle
            return self
        self._close(handle)
        if outcome == self._WAIT_TIMEOUT:
            raise TimeoutError("timed out waiting to commit semantic settings")
        if outcome == self._WAIT_FAILED:
            raise ctypes.WinError(ctypes.get_last_error())
        raise OSError(f"unexpected settings mutex wait result: {outcome}")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        handle = self._handle
        self._handle = None
        if handle is None or self._release is None or self._close is None:
            return
        try:
            if not self._release(handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self._close(handle)


def _apply_patch(
    current: SemanticSettings, patch: SemanticSettingsPatch
) -> SemanticSettings:
    values = {
        field: value
        for field in (
            "filters",
            "deletion_policy",
            "trash_on_update",
            "preservation",
            "propagate_source_casing",
        )
        if (value := getattr(patch, field)) is not None
    }
    return replace(current, **values)


def _encode_settings(value: SemanticSettings) -> bytes:
    payload = {
        "schema_version": SETTINGS_SCHEMA_VERSION,
        "filters": list(value.filters.patterns),
        "deletion_policy": value.deletion_policy.value,
        "trash_on_update": value.trash_on_update,
        "preservation": {
            "preserve_ads": value.preservation.preserve_ads,
            "preserve_created": value.preservation.preserve_created,
            "preserve_acl": value.preservation.preserve_acl,
        },
        "propagate_source_casing": value.propagate_source_casing,
    }
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _decode_settings(value: object) -> SemanticSettings:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise SettingsFormatError("settings.json must contain one JSON object")
    expected = {
        "schema_version",
        "filters",
        "deletion_policy",
        "trash_on_update",
        "preservation",
        "propagate_source_casing",
    }
    if set(value) != expected:
        raise SettingsFormatError("settings.json has missing or unknown keys")
    if value["schema_version"] != SETTINGS_SCHEMA_VERSION:
        raise SettingsFormatError(
            f"unsupported settings schema version: {value['schema_version']}"
        )
    filters = value["filters"]
    if not isinstance(filters, list) or not all(
        isinstance(item, str) for item in filters
    ):
        raise SettingsFormatError("settings filters must be a list of strings")
    preservation = value["preservation"]
    if not isinstance(preservation, dict) or set(preservation) != {
        "preserve_ads",
        "preserve_created",
        "preserve_acl",
    }:
        raise SettingsFormatError("settings preservation object is malformed")
    booleans = (
        value["trash_on_update"],
        value["propagate_source_casing"],
        preservation["preserve_ads"],
        preservation["preserve_created"],
        preservation["preserve_acl"],
    )
    if not all(isinstance(item, bool) for item in booleans):
        raise SettingsFormatError("settings boolean values must be true or false")
    try:
        return SemanticSettings(
            filters=FilterSet(tuple(filters)),
            deletion_policy=DeletionPolicy(str(value["deletion_policy"])),
            trash_on_update=value["trash_on_update"],
            preservation=PreservationPolicy(
                preserve_ads=preservation["preserve_ads"],
                preserve_created=preservation["preserve_created"],
                preserve_acl=preservation["preserve_acl"],
            ),
            propagate_source_casing=value["propagate_source_casing"],
        )
    except (TypeError, ValueError) as error:
        raise SettingsFormatError("settings.json contains an invalid value") from error


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
