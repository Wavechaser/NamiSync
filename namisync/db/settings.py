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
    FILTER_PATTERN_LIMIT,
    FILTER_TOTAL_UTF8_LIMIT,
    FilterSet,
    PreservationPolicy,
    SyncOptions,
    validate_filter_set,
)
from namisync.core.scalars import require_utf16_path


SETTINGS_SCHEMA_VERSION = 1
_MAX_JSON_CHARACTER_ESCAPE_BYTES = 6
_LONGEST_FIXED_SETTINGS_DOCUMENT = (
    b'{"deletion_policy":"additive","filters":[],"preservation":'
    b'{"preserve_acl":false,"preserve_ads":false,"preserve_created":false},'
    b'"propagate_source_casing":false,"schema_version":1,'
    b'"trash_on_update":false}\n'
)
SETTINGS_MAX_BYTES = (
    len(_LONGEST_FIXED_SETTINGS_DOCUMENT)
    + FILTER_TOTAL_UTF8_LIMIT * _MAX_JSON_CHARACTER_ESCAPE_BYTES
    + FILTER_PATTERN_LIMIT * 3
    - 1
)


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
        validate_filter_set(self.filters)
        if type(self.deletion_policy) is not DeletionPolicy:
            raise TypeError("semantic deletion policy has the wrong type")
        if type(self.preservation) is not PreservationPolicy:
            raise TypeError("semantic preservation policy has the wrong type")
        PreservationPolicy(
            self.preservation.preserve_ads,
            self.preservation.preserve_created,
            self.preservation.preserve_acl,
        )
        if (
            type(self.trash_on_update) is not bool
            or type(self.propagate_source_casing) is not bool
        ):
            raise TypeError("semantic settings switches must be bools")
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

    def __post_init__(self) -> None:
        if self.filters is not None:
            validate_filter_set(self.filters)
        if (
            self.deletion_policy is not None
            and type(self.deletion_policy) is not DeletionPolicy
        ):
            raise TypeError("semantic deletion patch has the wrong type")
        if self.preservation is not None:
            if type(self.preservation) is not PreservationPolicy:
                raise TypeError("semantic preservation patch has the wrong type")
            PreservationPolicy(
                self.preservation.preserve_ads,
                self.preservation.preserve_created,
                self.preservation.preserve_acl,
            )
        for field_name, value in (
            ("trash_on_update", self.trash_on_update),
            ("propagate_source_casing", self.propagate_source_casing),
        ):
            if value is not None and type(value) is not bool:
                raise TypeError(f"semantic {field_name} patch must be a bool")


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
        raw_path = os.fspath(path)
        require_utf16_path(raw_path, "settings path")
        resolved = str(Path(raw_path).resolve())
        require_utf16_path(resolved, "settings path")
        self.path = Path(resolved)
        self._mutex_timeout_seconds = mutex_timeout_seconds

    @property
    def mutex_name(self) -> str:
        material = os.path.normcase(str(self.path)).encode("utf-8")
        digest = hashlib.sha256(material).hexdigest()
        return rf"Local\NamiSync.Settings.{digest}"

    def read(self) -> SemanticSettings:
        try:
            with self.path.open("rb") as stream:
                payload = stream.read(SETTINGS_MAX_BYTES + 1)
        except FileNotFoundError:
            return SemanticSettings()
        if len(payload) > SETTINGS_MAX_BYTES:
            raise SettingsFormatError(
                "settings.json exceeds the complete document byte limit"
            )
        try:
            value = json.loads(
                payload.decode("utf-8"),
                object_pairs_hook=_unique_settings_object,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SettingsFormatError("settings.json is not valid UTF-8 JSON") from error
        return _decode_settings(value)

    def commit(self, patch: SemanticSettingsPatch) -> SemanticSettings:
        if type(patch) is not SemanticSettingsPatch:
            raise TypeError("semantic settings commit requires SemanticSettingsPatch")
        patch = SemanticSettingsPatch(
            filters=patch.filters,
            deletion_policy=patch.deletion_policy,
            trash_on_update=patch.trash_on_update,
            preservation=patch.preservation,
            propagate_source_casing=patch.propagate_source_casing,
        )
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
    if type(value) is not SemanticSettings:
        raise TypeError("settings encoder requires SemanticSettings")
    SemanticSettings(
        filters=value.filters,
        deletion_policy=value.deletion_policy,
        trash_on_update=value.trash_on_update,
        preservation=value.preservation,
        propagate_source_casing=value.propagate_source_casing,
    )
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
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    if len(encoded) > SETTINGS_MAX_BYTES:
        raise RuntimeError("settings encoding exceeded its derived byte limit")
    return encoded


def _decode_settings(value: object) -> SemanticSettings:
    if type(value) is not dict or not all(
        type(key) is str for key in value
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
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != SETTINGS_SCHEMA_VERSION
    ):
        raise SettingsFormatError(
            f"unsupported settings schema version: {value['schema_version']}"
        )
    filters = value["filters"]
    if type(filters) is not list:
        raise SettingsFormatError("settings filters must be a list of strings")
    if len(filters) > FILTER_PATTERN_LIMIT:
        raise SettingsFormatError("settings filters exceed the pattern limit")
    if not all(type(item) is str for item in filters):
        raise SettingsFormatError("settings filters must be a list of strings")
    preservation = value["preservation"]
    if type(preservation) is not dict or set(preservation) != {
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
    if not all(type(item) is bool for item in booleans):
        raise SettingsFormatError("settings boolean values must be true or false")
    deletion_policy = value["deletion_policy"]
    if type(deletion_policy) is not str:
        raise SettingsFormatError("settings deletion policy must be a string")
    try:
        return SemanticSettings(
            filters=FilterSet(tuple(filters)),
            deletion_policy=DeletionPolicy(deletion_policy),
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


def _unique_settings_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise SettingsFormatError(
                f"settings.json contains duplicate key: {key}"
            )
        value[key] = item
    return value


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
