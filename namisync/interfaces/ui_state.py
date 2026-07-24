"""GUI-owned cosmetic state kept separate from semantic planning settings."""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


_RECENT_LIMIT = 5


class UiStateFormatError(ValueError):
    """The cosmetic state file cannot be interpreted safely."""


@dataclass(frozen=True, slots=True)
class UiState:
    recent_sources: tuple[str, ...] = ()
    recent_targets: tuple[str, ...] = ()
    window: Mapping[str, object] = field(default_factory=dict)
    columns: Mapping[str, object] = field(default_factory=dict)
    sort: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, recents in (
            ("recent_sources", self.recent_sources),
            ("recent_targets", self.recent_targets),
        ):
            if len(recents) > _RECENT_LIMIT:
                raise ValueError(f"{name} cannot contain more than {_RECENT_LIMIT} paths")
            if any(not isinstance(path, str) or not path for path in recents):
                raise ValueError(f"{name} must contain non-empty path strings")
            keys = [os.path.normcase(path) for path in recents]
            if len(keys) != len(set(keys)):
                raise ValueError(f"{name} cannot contain duplicate paths")
        for name in ("window", "columns", "sort"):
            _require_json_object(getattr(self, name), name)

    def remember_source(self, path: str) -> UiState:
        return UiState(
            _remember(self.recent_sources, path),
            self.recent_targets,
            self.window,
            self.columns,
            self.sort,
        )

    def remember_target(self, path: str) -> UiState:
        return UiState(
            self.recent_sources,
            _remember(self.recent_targets, path),
            self.window,
            self.columns,
            self.sort,
        )


class UiStateStore:
    """Plain single-owner cosmetic state; no cross-interface mutex is needed."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()

    def read(self) -> UiState:
        try:
            payload = self.path.read_bytes()
        except FileNotFoundError:
            return UiState()
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UiStateFormatError("ui-state.json is not valid UTF-8 JSON") from error
        return _decode_ui_state(value)

    def write(self, value: UiState) -> None:
        if not isinstance(value, UiState):
            raise TypeError("UI state write requires UiState")
        payload = {
            "recent_sources": list(value.recent_sources),
            "recent_targets": list(value.recent_targets),
            "window": dict(value.window),
            "columns": dict(value.columns),
            "sort": dict(value.sort),
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
        _atomic_write(self.path, encoded)


def _remember(recents: tuple[str, ...], path: str) -> tuple[str, ...]:
    if not isinstance(path, str) or not path:
        raise ValueError("recent path must be a non-empty string")
    key = os.path.normcase(path)
    return (path,) + tuple(
        item for item in recents if os.path.normcase(item) != key
    )[: _RECENT_LIMIT - 1]


def _decode_ui_state(value: object) -> UiState:
    if not isinstance(value, dict) or set(value) != {
        "recent_sources",
        "recent_targets",
        "window",
        "columns",
        "sort",
    }:
        raise UiStateFormatError("ui-state.json has missing or unknown keys")
    sources = value["recent_sources"]
    targets = value["recent_targets"]
    if not isinstance(sources, list) or not isinstance(targets, list):
        raise UiStateFormatError("UI recents must be JSON arrays")
    try:
        return UiState(
            recent_sources=tuple(sources),
            recent_targets=tuple(targets),
            window=_require_json_object(value["window"], "window"),
            columns=_require_json_object(value["columns"], "columns"),
            sort=_require_json_object(value["sort"], "sort"),
        )
    except (TypeError, ValueError) as error:
        raise UiStateFormatError("ui-state.json contains an invalid value") from error


def _require_json_object(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"{name} must be a string-keyed JSON object")
    _require_json_value(value, name)
    return value


def _require_json_value(value: object, name: str) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise ValueError(f"{name} must contain finite JSON numbers")
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ValueError(f"{name} must contain only string-keyed objects")
        for item in value.values():
            _require_json_value(item, name)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _require_json_value(item, name)
        return
    raise ValueError(f"{name} must contain JSON-compatible values")


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
