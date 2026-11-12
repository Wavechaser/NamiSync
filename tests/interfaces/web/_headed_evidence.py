"""Immutable lifecycle evidence for headed test subprocesses."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4


_SCHEMA = "namisync-headed-evidence-v1"
_MAX_RECORD_BYTES = 1_048_576
_MILESTONES = ("ready", "failure", "final")
_TEMP_GLOB = ".namisync-headed-evidence-*.tmp"

Milestone = Literal["ready", "failure", "final"]


class EvidenceProtocolError(RuntimeError):
    """A headed child and parent disagreed on immutable evidence."""


@dataclass(frozen=True, slots=True)
class EvidencePaths:
    root: Path

    def __post_init__(self) -> None:
        root = Path(self.root)
        if not root.is_absolute():
            raise ValueError("headed evidence root must be absolute")
        object.__setattr__(self, "root", root)

    @property
    def ready(self) -> Path:
        return self.root / "ready.json"

    @property
    def failure(self) -> Path:
        return self.root / "failure.json"

    @property
    def final(self) -> Path:
        return self.root / "final.json"

    def for_milestone(self, milestone: Milestone) -> Path:
        if milestone not in _MILESTONES:
            raise ValueError("unknown headed evidence milestone")
        return getattr(self, milestone)

    def temporary(self, milestone: Milestone) -> Path:
        self.for_milestone(milestone)
        return self.root / (
            f".namisync-headed-evidence-{milestone}-{os.getpid()}-"
            f"{uuid4().hex}.tmp"
        )

    def orphan_temporaries(self) -> tuple[Path, ...]:
        if not self.root.exists():
            return ()
        return tuple(sorted(self.root.glob(_TEMP_GLOB)))


class EvidencePublisher:
    """Publish each headed lifecycle milestone at most once."""

    def __init__(self, paths: EvidencePaths) -> None:
        if type(paths) is not EvidencePaths:
            raise TypeError("evidence paths must be exact")
        if not paths.root.is_dir():
            raise ValueError("headed evidence root must already exist")
        self._paths = paths
        self._lock = Lock()
        self._phase: Milestone | None = None

    def publish_ready(self, payload: dict[str, object]) -> None:
        self._publish("ready", payload)

    def publish_failure(self, payload: dict[str, object]) -> None:
        self._publish("failure", payload)

    def publish_final(self, payload: dict[str, object]) -> None:
        self._publish("final", payload)

    def _publish(self, milestone: Milestone, payload: dict[str, object]) -> None:
        if type(payload) is not dict:
            raise TypeError("headed evidence payload must be an exact object")
        encoded = _encode_record(milestone, payload)
        with self._lock:
            if self._phase == "final":
                raise EvidenceProtocolError(
                    "headed evidence cannot publish after final"
                )
            if milestone != "final" and self._phase is not None:
                raise EvidenceProtocolError(
                    "ready and failure evidence are mutually exclusive"
                )
            target = self._paths.for_milestone(milestone)
            temporary = self._paths.temporary(milestone)
            try:
                _write_complete_temporary(temporary, encoded)
                _move_no_replace(temporary, target)
            except BaseException:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            self._phase = milestone


class EvidenceReader:
    """Read each immutable milestone once and cache its exact payload."""

    def __init__(self, paths: EvidencePaths) -> None:
        if type(paths) is not EvidencePaths:
            raise TypeError("evidence paths must be exact")
        self._paths = paths
        self._cache: dict[Milestone, dict[str, object]] = {}
        self._names_at_final: frozenset[Milestone] | None = None

    def available_initial(self) -> Milestone | None:
        names = self._published_names()
        if "ready" in names and "failure" in names:
            raise EvidenceProtocolError(
                "ready and failure evidence cannot both be published"
            )
        if "ready" in names:
            return "ready"
        if "failure" in names:
            return "failure"
        return None

    def read_ready(self) -> dict[str, object] | None:
        return self._read("ready")

    def read_failure(self) -> dict[str, object] | None:
        return self._read("failure")

    def read_final(self) -> dict[str, object] | None:
        return self._read("final")

    def assert_consistent(
        self,
        *,
        require_final: bool,
        allow_final_only: bool = False,
    ) -> None:
        self._audit_after_final()
        names = self._published_names()
        if "ready" in names and "failure" in names:
            raise EvidenceProtocolError(
                "ready and failure evidence cannot both be published"
            )
        if require_final and "final" not in names:
            raise EvidenceProtocolError("final evidence was not published")
        if (
            "final" in names
            and "ready" not in names
            and "failure" not in names
            and not allow_final_only
        ):
            raise EvidenceProtocolError("final-only evidence was not expected")
        orphans = self._paths.orphan_temporaries()
        if orphans:
            names_text = ", ".join(path.name for path in orphans)
            raise EvidenceProtocolError(
                f"headed evidence left temporary files: {names_text}"
            )

    def _read(self, milestone: Milestone) -> dict[str, object] | None:
        names = self._published_names()
        if "ready" in names and "failure" in names:
            raise EvidenceProtocolError(
                "ready and failure evidence cannot both be published"
            )
        self._audit_after_final()
        cached = self._cache.get(milestone)
        if cached is not None:
            return deepcopy(cached)
        path = self._paths.for_milestone(milestone)
        if not path.exists():
            return None
        try:
            with path.open("rb") as stream:
                encoded = stream.read(_MAX_RECORD_BYTES + 1)
        except OSError as error:
            raise EvidenceProtocolError(
                f"could not read {milestone} evidence"
            ) from error
        payload = _decode_record(encoded, milestone)
        self._cache[milestone] = payload
        if milestone == "final":
            self._names_at_final = self._published_names()
        self._audit_after_final()
        return deepcopy(payload)

    def _published_names(self) -> frozenset[Milestone]:
        return frozenset(
            milestone
            for milestone in _MILESTONES
            if self._paths.for_milestone(milestone).exists()
        )

    def _audit_after_final(self) -> None:
        if self._names_at_final is None:
            return
        if self._published_names() != self._names_at_final:
            raise EvidenceProtocolError(
                "headed evidence changed after final was observed"
            )


def require_host_final(
    payload: dict[str, object],
    *,
    exit_code: int,
) -> bool:
    """Validate the common headed-host completion payload exactly."""

    if (
        type(payload) is not dict
        or set(payload) != {"host_returned", "exit_code"}
        or type(payload.get("host_returned")) is not bool
        or type(payload.get("exit_code")) is not int
        or type(exit_code) is not int
        or payload["exit_code"] != exit_code
    ):
        raise EvidenceProtocolError("headed host final evidence is invalid")
    return payload["host_returned"]


def _encode_record(milestone: Milestone, payload: dict[str, object]) -> bytes:
    try:
        _require_exact_json(payload)
        text = json.dumps(
            {
                "milestone": milestone,
                "payload": payload,
                "schema": _SCHEMA,
            },
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise EvidenceProtocolError("headed evidence is not exact JSON") from error
    encoded = (text + "\n").encode("utf-8")
    if len(encoded) > _MAX_RECORD_BYTES:
        raise EvidenceProtocolError("headed evidence exceeds 1048576 bytes")
    return encoded


def _require_exact_json(value: object) -> None:
    if value is None or type(value) in {bool, int, float, str}:
        return
    if type(value) is list:
        for item in value:
            _require_exact_json(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise EvidenceProtocolError(
                    "headed evidence is not exact JSON"
                )
            _require_exact_json(item)
        return
    raise EvidenceProtocolError("headed evidence is not exact JSON")


def _decode_record(encoded: bytes, milestone: Milestone) -> dict[str, object]:
    if len(encoded) > _MAX_RECORD_BYTES:
        raise EvidenceProtocolError("headed evidence exceeds 1048576 bytes")
    try:
        text = encoded.decode("utf-8", errors="strict")
        value = json.loads(text, parse_constant=_reject_json_constant)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
    ) as error:
        raise EvidenceProtocolError("headed evidence is not valid JSON") from error
    if (
        type(value) is not dict
        or set(value) != {"milestone", "payload", "schema"}
        or value.get("schema") != _SCHEMA
        or value.get("milestone") != milestone
        or type(value.get("payload")) is not dict
    ):
        raise EvidenceProtocolError("headed evidence envelope is invalid")
    payload = value["payload"]
    if _encode_record(milestone, payload) != encoded:
        raise EvidenceProtocolError("headed evidence is not canonical")
    return payload


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"unsupported JSON constant: {value}")


def _write_complete_temporary(path: Path, encoded: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _move_no_replace(source: Path, target: Path) -> None:
    if target.exists():
        raise FileExistsError(target)
    if os.name == "nt":
        source.rename(target)
        return
    os.link(source, target)
    source.unlink()
