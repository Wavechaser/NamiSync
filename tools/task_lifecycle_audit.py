"""Temporary boundary-invariance oracle for task lifecycle simplification.

The capture deliberately crosses the production bridge and CLI surfaces.  It
normalizes only the tool-owned fixture root, opaque identifiers, and timestamp
occurrences.  Everything else, including event bodies and persisted hashes,
remains exact.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
from typing import Never, Sequence

from namisync.modules import preflight as preflight_module
from namisync.interfaces.cli import main as cli_main
from namisync.interfaces.service import NamiSyncService
from namisync.interfaces.web.bridge import (
    AdmissionGranted,
    BRIDGE_SCHEMA_VERSION,
    BridgeDispatcher,
)
from namisync.interfaces.web.commands import production_command_specs
from namisync.interfaces.web.drain import TaskRegistry
from namisync.interfaces.web.readiness import CommandPhase, ReadinessContext
from namisync.interfaces.web.slots import FolderSlotTable


FORMAT_VERSION = 1
DEFAULT_FIXTURE_ROOT = (
    Path(tempfile.gettempdir()) / "namisync-task-lifecycle-audit-v1"
)
_FIXTURE_BYTES = b"task lifecycle boundary fixture\n"
_FIXTURE_MTIME_NS = 1_700_000_000_000_000_000
_CLI_FREE_BYTES = 1_099_511_627_776
_OPAQUE_ID = re.compile(
    r"(?<![A-Za-z0-9_-])(?:task-|slot-)?[0-9a-f]{32}(?![0-9a-f])"
)
_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)
_HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
_BRIDGE_RESPONSE_KEYS = (
    "start_plan",
    "start_plan_replay",
    "next_events",
    "release_terminal_session",
    "release_terminal_session_replay",
    "close_task",
    "close_task_replay",
)
_DATABASE_NAMES = (
    "bridge-ledger.db",
    "bridge-history.db",
    "cli-ledger.db",
    "cli-history.db",
)
_DATABASE_SUFFIXES = ("", "-wal", "-shm", "-journal")
class AuditError(RuntimeError):
    """The boundary corpus could not be captured or verified truthfully."""


class _TrustedDocument:
    def require_trusted(self) -> None:
        return None


class _UnusedCosmetics:
    """The four audited production commands never reach cosmetic state."""


def _raise(message: str) -> Never:
    raise AuditError(message)


def _require_exact_keys(value: object, keys: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        _raise(f"{label} has the wrong fields")
    return value


def _canonical(value: object) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise AuditError(f"capture is not canonical JSON: {error}") from error


def _request(request_id: str, command: str, payload: dict[str, object]) -> str:
    return json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": request_id,
            "command": command,
            "payload": payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _request_id(index: int) -> str:
    if index < 1:
        raise ValueError("request index must be positive")
    return f"{index:032x}"


def _dispatch(
    bridge: BridgeDispatcher,
    index: int,
    command: str,
    payload: dict[str, object],
) -> dict[str, object]:
    response = bridge.dispatch(_request(_request_id(index), command, payload))
    if (
        type(response) is not dict
        or response.get("schema_version") != BRIDGE_SCHEMA_VERSION
        or response.get("request_id") != _request_id(index)
        or response.get("ok") is not True
        or "result" not in response
    ):
        raise AuditError(f"{command} did not return a successful bridge envelope")
    return copy.deepcopy(response)


def _admit_open(_name: str) -> AdmissionGranted:
    return AdmissionGranted(ReadinessContext(CommandPhase.OPEN, 0))


def _assert_directory_shape(path: Path, expected: set[str], label: str) -> None:
    actual = {item.name for item in path.iterdir()}
    if actual != expected:
        raise AuditError(
            f"{label} fixture contains unexpected entries: "
            f"expected={sorted(expected)!r}, actual={sorted(actual)!r}"
        )


def prepare_fixture(root: Path) -> dict[str, Path]:
    """Create the stable fixture once, then refuse any unexplained drift."""

    root = root.resolve()
    if root.exists() and root.is_symlink():
        raise AuditError("fixture root cannot be a symbolic link")
    root.mkdir(parents=True, exist_ok=True)
    layout: dict[str, Path] = {"root": root}
    for surface in ("bridge", "cli"):
        surface_root = root / surface
        source = surface_root / "source"
        target = surface_root / "target"
        surface_root.mkdir(exist_ok=True)
        source.mkdir(exist_ok=True)
        target.mkdir(exist_ok=True)
        payload = source / "payload.txt"
        if not payload.exists():
            payload.write_bytes(_FIXTURE_BYTES)
            os.utime(payload, ns=(_FIXTURE_MTIME_NS, _FIXTURE_MTIME_NS))
        if payload.is_symlink() or not payload.is_file():
            raise AuditError(f"{surface} source payload is not a regular file")
        if payload.read_bytes() != _FIXTURE_BYTES:
            raise AuditError(f"{surface} source payload bytes changed")
        if payload.stat().st_mtime_ns != _FIXTURE_MTIME_NS:
            raise AuditError(f"{surface} source payload timestamp changed")
        _assert_directory_shape(source, {"payload.txt"}, f"{surface} source")
        _assert_directory_shape(target, set(), f"{surface} target")
        _assert_directory_shape(
            surface_root,
            {"source", "target"},
            f"{surface} root",
        )
        layout[f"{surface}_source"] = source
        layout[f"{surface}_target"] = target

    state = root / "state"
    state.mkdir(exist_ok=True)
    _assert_directory_shape(root, {"bridge", "cli", "state"}, "audit root")
    expected_state: set[str] = set()
    for name in _DATABASE_NAMES:
        for suffix in _DATABASE_SUFFIXES:
            candidate = state / f"{name}{suffix}"
            layout[f"{name}{suffix}"] = candidate
            if candidate.exists():
                expected_state.add(candidate.name)
    if expected_state:
        raise AuditError(
            "plan-only fixture retained database bytes before capture: "
            f"{sorted(expected_state)!r}"
        )
    _assert_directory_shape(state, set(), "audit state")
    layout["state"] = state
    return layout


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def filesystem_manifest(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        modified = path.lstat().st_mtime_ns
        if path.is_symlink():
            entries.append(
                {"path": relative, "kind": "symlink", "mtime_ns": modified}
            )
        elif path.is_dir():
            entries.append(
                {"path": relative, "kind": "directory", "mtime_ns": modified}
            )
        elif path.is_file():
            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "mtime_ns": modified,
                    "size": path.stat().st_size,
                    "sha256": _file_sha256(path),
                }
            )
        else:
            entries.append(
                {"path": relative, "kind": "other", "mtime_ns": modified}
            )
    return entries


def persistence_manifest(state: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for name in _DATABASE_NAMES:
        for suffix in _DATABASE_SUFFIXES:
            path = state / f"{name}{suffix}"
            exists = path.is_file()
            entries.append(
                {
                    "name": f"{name}{suffix}",
                    "exists": exists,
                    "sha256": _file_sha256(path) if exists else None,
                }
            )
    return entries


def _capture_bridge(layout: dict[str, Path]) -> dict[str, object]:
    state = layout["state"]
    service = NamiSyncService(
        state / "bridge-ledger.db",
        state / "bridge-history.db",
        settings_path=state / "bridge-settings.json",
    )
    registry = TaskRegistry(service)
    slots = FolderSlotTable()
    bridge: BridgeDispatcher | None = None
    try:
        source_id, _source_display = slots.store(
            str(layout["bridge_source"]), purpose="source"
        )
        target_id, _target_display = slots.store(
            str(layout["bridge_target"]), purpose="target"
        )
        commands = production_command_specs(
            picker=lambda: None,
            slots=slots,
            registry=registry,
            cosmetics=_UnusedCosmetics(),
            shell_ready=lambda _generation: None,
            readiness_echo=lambda _generation, _challenge: False,
        )
        bridge = BridgeDispatcher(
            document=_TrustedDocument(),
            commands=commands,
            admit=_admit_open,
        )
        start_payload = {
            "command_id": "a0" * 16,
            "source_id": source_id,
            "target_id": target_id,
            "deletion_policy": None,
        }
        start = _dispatch(bridge, 1, "start_plan", start_payload)
        start_replay = _dispatch(bridge, 2, "start_plan", start_payload)
        start_result = _require_exact_keys(
            start["result"],
            {"task_id", "request_id", "session_id"},
            "start_plan result",
        )
        if start_replay.get("result") != start_result:
            raise AuditError("start_plan replay changed its result")
        task_id = start_result["task_id"]
        session_id = start_result["session_id"]
        if type(task_id) is not str or type(session_id) is not str:
            raise AuditError("start_plan returned invalid task/session ids")

        # Hold the fixed script at a production service boundary until the
        # complete plan observation has reached the adapter.  Without this
        # barrier, scheduler timing changes only how the same updates are split
        # across next_events responses, making the temporary oracle measure its
        # own call timing instead of the delivered stream contract.
        terminal = service.wait(session_id)
        if terminal.result is None:
            raise AuditError("plan session wait returned a nonterminal record")

        drains: list[dict[str, object]] = []
        updates: list[dict[str, object]] = []
        next_request_index = 3
        for drain_index in range(1, 65):
            response = _dispatch(
                bridge,
                next_request_index,
                "next_events",
                {
                    "task_id": task_id,
                    "session_id": session_id,
                    "drain_id": f"{0x1000 + drain_index:032x}",
                    "replay_from": None,
                },
            )
            next_request_index += 1
            drains.append(response)
            result = _require_exact_keys(
                response["result"],
                {"task_id", "session_id", "drain_id", "updates"},
                "next_events result",
            )
            batch = result["updates"]
            if type(batch) is not list:
                raise AuditError("next_events updates are not a list")
            if (
                result["task_id"] != task_id
                or result["session_id"] != session_id
                or result["drain_id"] != f"{0x1000 + drain_index:032x}"
            ):
                raise AuditError("next_events changed its exact task/session/drain identity")
            updates.extend(copy.deepcopy(batch))
            if any(
                type(update) is dict and update.get("update_type") == "record"
                for update in batch
            ):
                break
        else:
            raise AuditError("plan session did not deliver a terminal record")

        release_payload = {"task_id": task_id, "session_id": session_id}
        release = _dispatch(
            bridge,
            next_request_index,
            "release_terminal_session",
            release_payload,
        )
        next_request_index += 1
        release_replay = _dispatch(
            bridge,
            next_request_index,
            "release_terminal_session",
            release_payload,
        )
        next_request_index += 1
        close = _dispatch(bridge, next_request_index, "close_task", release_payload)
        next_request_index += 1
        close_replay = _dispatch(
            bridge,
            next_request_index,
            "close_task",
            release_payload,
        )
        if release.get("result") != release_replay.get("result"):
            raise AuditError("terminal release replay changed its result")
        if close.get("result") != close_replay.get("result"):
            raise AuditError("task close replay changed its result")
        return {
            "responses": {
                "start_plan": start,
                "start_plan_replay": start_replay,
                "next_events": drains,
                "release_terminal_session": release,
                "release_terminal_session_replay": release_replay,
                "close_task": close,
                "close_task_replay": close_replay,
            },
            "event_stream": updates,
        }
    finally:
        registry.begin_close()
        shutdown = service.close()
        if not shutdown.complete:
            raise AuditError(
                "bridge service shutdown was incomplete: "
                f"unfinished={shutdown.unfinished!r}"
            )
        del bridge


def _capture_cli(layout: dict[str, Path]) -> dict[str, object]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    original_disk_usage = preflight_module.shutil.disk_usage

    def fixed_disk_usage(_path: object) -> object:
        return SimpleNamespace(
            total=_CLI_FREE_BYTES * 2,
            used=_CLI_FREE_BYTES,
            free=_CLI_FREE_BYTES,
        )

    preflight_module.shutil.disk_usage = fixed_disk_usage
    try:
        exit_code = cli_main(
            [
                "sync",
                str(layout["cli_source"]),
                str(layout["cli_target"]),
                "--database",
                str(layout["state"] / "cli-ledger.db"),
                "--history-database",
                str(layout["state"] / "cli-history.db"),
            ],
            stdin=io.StringIO("\n"),
            stdout=stdout,
            stderr=stderr,
        )
    finally:
        preflight_module.shutil.disk_usage = original_disk_usage
    return {
        "script": "sync SOURCE TARGET --database LEDGER --history-database HISTORY < blank-line",
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "exit_code": exit_code,
    }


class _Normalizer:
    def __init__(self, fixture_root: Path, generated_opaque_ids: frozenset[str]) -> None:
        variants = {str(fixture_root.resolve()), fixture_root.resolve().as_posix()}
        self._root_patterns = tuple(
            re.compile(re.escape(value), re.IGNORECASE)
            for value in sorted(variants, key=len, reverse=True)
        )
        self._opaque: dict[str, str] = {}
        self._timestamps: dict[str, str] = {}
        self._generated_opaque_ids = generated_opaque_ids

    def normalize(self, value: object) -> object:
        if type(value) is dict:
            return {
                key: self.normalize(value[key])
                for key in sorted(value)
            }
        if type(value) is list:
            return [self.normalize(item) for item in value]
        if type(value) is str:
            return self._normalize_text(value)
        if value is None or type(value) in {bool, int, float}:
            return value
        raise AuditError(f"capture contains unsupported value: {type(value).__name__}")

    def _normalize_text(self, value: str) -> str:
        for pattern in self._root_patterns:
            value = pattern.sub("$AUDIT_ROOT", value)

        def timestamp_replacement(match: re.Match[str]) -> str:
            timestamp = match.group(0)
            replacement = self._timestamps.get(timestamp)
            if replacement is None:
                replacement = f"$TIMESTAMP_{len(self._timestamps) + 1:04d}"
                self._timestamps[timestamp] = replacement
            return replacement

        value = _TIMESTAMP.sub(timestamp_replacement, value)

        def opaque_replacement(match: re.Match[str]) -> str:
            token = match.group(0)
            if token not in self._generated_opaque_ids:
                return token
            replacement = self._opaque.get(token)
            if replacement is None:
                replacement = f"$OPAQUE_{len(self._opaque) + 1:04d}"
                self._opaque[token] = replacement
            return replacement

        return _OPAQUE_ID.sub(opaque_replacement, value)


def normalize_capture(
    capture: dict[str, object],
    fixture_root: Path,
    generated_opaque_ids: frozenset[str],
) -> dict[str, object]:
    normalized = _Normalizer(fixture_root, generated_opaque_ids).normalize(capture)
    if type(normalized) is not dict:
        raise AssertionError("normalization changed the capture root type")
    return normalized


def capture_boundaries(fixture_root: Path = DEFAULT_FIXTURE_ROOT) -> dict[str, object]:
    layout = prepare_fixture(fixture_root)
    filesystem_before = {
        surface: {
            side: filesystem_manifest(layout[f"{surface}_{side}"])
            for side in ("source", "target")
        }
        for surface in ("bridge", "cli")
    }
    persistence_before = persistence_manifest(layout["state"])
    bridge = _capture_bridge(layout)
    cli = _capture_cli(layout)
    raw = {
        "format_version": FORMAT_VERSION,
        "bridge": bridge,
        "cli": cli,
        "filesystem": {
            "before": filesystem_before,
            "after": {
                surface: {
                    side: filesystem_manifest(layout[f"{surface}_{side}"])
                    for side in ("source", "target")
                }
                for surface in ("bridge", "cli")
            },
        },
        "persistence": {
            "before": persistence_before,
            "after": persistence_manifest(layout["state"]),
        },
    }
    start_result = bridge["responses"]["start_plan"]["result"]
    generated_values = (
        start_result["task_id"],
        start_result["request_id"],
        start_result["session_id"],
    )
    if not all(
        type(value) is str and _OPAQUE_ID.fullmatch(value) is not None
        for value in generated_values
    ):
        raise AuditError("bridge start did not produce three exact opaque identities")
    generated_opaque_ids = frozenset(generated_values)
    if len(generated_opaque_ids) != 3:
        raise AuditError("bridge start reused one generated opaque identity")
    normalized = normalize_capture(raw, layout["root"], generated_opaque_ids)
    validate_capture(normalized)
    return normalized


def _validate_response(value: object, label: str) -> dict[str, object]:
    response = _require_exact_keys(
        value,
        {"schema_version", "request_id", "ok", "result"},
        label,
    )
    if response["schema_version"] != BRIDGE_SCHEMA_VERSION or response["ok"] is not True:
        raise AuditError(f"{label} is not a successful schema-v1 response")
    if type(response["request_id"]) is not str:
        raise AuditError(f"{label} request id is invalid")
    return response


def _validate_manifest(value: object, label: str) -> list[dict[str, object]]:
    if type(value) is not list:
        raise AuditError(f"{label} is not a manifest list")
    prior = ""
    for index, raw_entry in enumerate(value):
        entry = _require_exact_keys(
            raw_entry,
            {"path", "kind", "mtime_ns"}
            if type(raw_entry) is dict and raw_entry.get("kind") != "file"
            else {"path", "kind", "mtime_ns", "size", "sha256"},
            f"{label}[{index}]",
        )
        path = entry["path"]
        kind = entry["kind"]
        if type(path) is not str or not path or path <= prior:
            raise AuditError(f"{label} paths are not strictly ordered")
        if kind not in {"directory", "file", "symlink", "other"}:
            raise AuditError(f"{label} contains an invalid entry kind")
        if type(entry["mtime_ns"]) is not int or entry["mtime_ns"] < 0:
            raise AuditError(f"{label} contains an invalid timestamp")
        if kind == "file" and (
            type(entry["size"]) is not int
            or entry["size"] < 0
            or type(entry["sha256"]) is not str
            or _HEX_SHA256.fullmatch(entry["sha256"]) is None
        ):
            raise AuditError(f"{label} contains invalid file evidence")
        prior = path
    return value


def _validate_persistence(value: object, label: str) -> list[dict[str, object]]:
    if type(value) is not list or len(value) != len(_DATABASE_NAMES) * len(
        _DATABASE_SUFFIXES
    ):
        raise AuditError(f"{label} has the wrong persistence entry count")
    expected_names = [
        f"{name}{suffix}" for name in _DATABASE_NAMES for suffix in _DATABASE_SUFFIXES
    ]
    for index, (raw_entry, expected_name) in enumerate(zip(value, expected_names)):
        entry = _require_exact_keys(
            raw_entry,
            {"name", "exists", "sha256"},
            f"{label}[{index}]",
        )
        if entry["name"] != expected_name or type(entry["exists"]) is not bool:
            raise AuditError(f"{label}[{index}] has invalid identity/existence")
        digest = entry["sha256"]
        if entry["exists"]:
            if type(digest) is not str or _HEX_SHA256.fullmatch(digest) is None:
                raise AuditError(f"{label}[{index}] has an invalid persisted hash")
        elif digest is not None:
            raise AuditError(f"{label}[{index}] hashes an absent persisted file")
    return value


def validate_capture(value: object) -> None:
    capture = _require_exact_keys(
        value,
        {"format_version", "bridge", "cli", "filesystem", "persistence"},
        "capture",
    )
    if capture["format_version"] != FORMAT_VERSION:
        raise AuditError("capture format version is unsupported")
    bridge = _require_exact_keys(capture["bridge"], {"responses", "event_stream"}, "bridge")
    responses = _require_exact_keys(
        bridge["responses"], set(_BRIDGE_RESPONSE_KEYS), "bridge responses"
    )
    start = _validate_response(responses["start_plan"], "start_plan")
    start_replay = _validate_response(
        responses["start_plan_replay"], "start_plan replay"
    )
    if start["request_id"] != _request_id(1):
        raise AuditError("start_plan response changed its request identity")
    if start_replay["request_id"] != _request_id(2):
        raise AuditError("start_plan replay changed its request identity")
    if start["result"] != start_replay["result"]:
        raise AuditError("start_plan replay result differs")
    start_result = _require_exact_keys(
        start["result"],
        {"task_id", "request_id", "session_id"},
        "start_plan result",
    )
    drains = responses["next_events"]
    if type(drains) is not list or not drains:
        raise AuditError("next_events response corpus is empty")
    delivered: list[object] = []
    for index, raw_response in enumerate(drains):
        response = _validate_response(raw_response, f"next_events[{index}]")
        result = _require_exact_keys(
            response["result"],
            {"task_id", "session_id", "drain_id", "updates"},
            f"next_events[{index}] result",
        )
        if response["request_id"] != _request_id(index + 3):
            raise AuditError(f"next_events[{index}] changed its request identity")
        if (
            result["task_id"] != start_result["task_id"]
            or result["session_id"] != start_result["session_id"]
            or result["drain_id"] != f"{0x1001 + index:032x}"
        ):
            raise AuditError(f"next_events[{index}] changed its exact identity")
        if type(result["updates"]) is not list:
            raise AuditError(f"next_events[{index}] updates are invalid")
        delivered.extend(result["updates"])
    stream = bridge["event_stream"]
    if type(stream) is not list or stream != delivered:
        raise AuditError("event stream differs from delivered next_events updates")
    if not stream:
        raise AuditError("event stream is empty")
    record_indexes: list[int] = []
    terminal_indexes: list[int] = []
    sequences: list[int] = []
    for index, raw_update in enumerate(stream):
        if type(raw_update) is not dict or raw_update.get("update_type") not in {
            "event",
            "record",
        }:
            raise AuditError(f"event stream update {index} has an invalid tag")
        if raw_update["update_type"] == "record":
            _require_exact_keys(raw_update, {"update_type", "record"}, f"record {index}")
            record = raw_update["record"]
            if type(record) is not dict or record.get("result") is None:
                raise AuditError("delivered record is not terminal")
            record_indexes.append(index)
            continue
        _require_exact_keys(raw_update, {"update_type", "event"}, f"event {index}")
        event = raw_update["event"]
        if type(event) is not dict or type(event.get("sequence")) is not int:
            raise AuditError(f"event {index} has no exact sequence")
        sequences.append(event["sequence"])
        if event.get("body_type") == "Terminal":
            terminal_indexes.append(index)
    if record_indexes != [len(stream) - 1]:
        raise AuditError("terminal record is not the unique last delivered update")
    if len(terminal_indexes) != 1 or terminal_indexes[0] >= record_indexes[0]:
        raise AuditError("event stream lacks one terminal event before its record")
    if sequences != sorted(set(sequences)):
        raise AuditError("delivered event sequences are not unique and increasing")

    trailing = (
        "release_terminal_session",
        "release_terminal_session_replay",
        "close_task",
        "close_task_replay",
    )
    for offset, name in enumerate(trailing, start=3 + len(drains)):
        response = _validate_response(responses[name], name)
        if response["request_id"] != _request_id(offset):
            raise AuditError(f"{name} changed its request identity")
        result = _require_exact_keys(
            response["result"], {"task_id", "session_id"}, f"{name} result"
        )
        if (
            result["task_id"] != start_result["task_id"]
            or result["session_id"] != start_result["session_id"]
        ):
            raise AuditError(f"{name} changed its task/session identity")
    if (
        responses["release_terminal_session"]["result"]
        != responses["release_terminal_session_replay"]["result"]
    ):
        raise AuditError("terminal release replay result differs")
    if responses["close_task"]["result"] != responses["close_task_replay"]["result"]:
        raise AuditError("task close replay result differs")

    cli = _require_exact_keys(
        capture["cli"], {"script", "stdout", "stderr", "exit_code"}, "cli"
    )
    if (
        type(cli["script"]) is not str
        or type(cli["stdout"]) is not str
        or type(cli["stderr"]) is not str
        or type(cli["exit_code"]) is not int
    ):
        raise AuditError("CLI capture has invalid field types")

    filesystem = _require_exact_keys(
        capture["filesystem"], {"before", "after"}, "filesystem"
    )
    for moment in ("before", "after"):
        surfaces = _require_exact_keys(
            filesystem[moment], {"bridge", "cli"}, f"filesystem {moment}"
        )
        for surface in ("bridge", "cli"):
            roots = _require_exact_keys(
                surfaces[surface],
                {"source", "target"},
                f"filesystem {moment} {surface}",
            )
            for side in ("source", "target"):
                _validate_manifest(
                    roots[side], f"filesystem {moment} {surface} {side}"
                )
    if filesystem["before"] != filesystem["after"]:
        raise AuditError("plan-only capture changed source or target manifests")

    persistence = _require_exact_keys(
        capture["persistence"], {"before", "after"}, "persistence"
    )
    _validate_persistence(persistence["before"], "persistence before")
    _validate_persistence(persistence["after"], "persistence after")
    if persistence["before"] != persistence["after"]:
        raise AuditError("plan-only capture changed persisted bytes")
    if any(entry["exists"] for entry in persistence["after"]):
        raise AuditError("declined plan unexpectedly created database bytes")
    _canonical(capture)


def _first_difference(expected: object, actual: object, path: str = "$") -> str:
    if type(expected) is not type(actual):
        return path
    if type(expected) is dict:
        if set(expected) != set(actual):
            return path
        for key in sorted(expected):
            difference = _first_difference(expected[key], actual[key], f"{path}.{key}")
            if difference:
                return difference
        return ""
    if type(expected) is list:
        if len(expected) != len(actual):
            return path
        for index, (left, right) in enumerate(zip(expected, actual)):
            difference = _first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
        return ""
    return "" if expected == actual else path


def verify_captures(expected: object, actual: object) -> None:
    validate_capture(expected)
    validate_capture(actual)
    difference = _first_difference(expected, actual)
    if difference:
        raise AuditError(f"boundary corpus differs at {difference}")


def _parse_capture(text: str, source: str) -> dict[str, object]:
    try:
        value = json.loads(
            text,
            parse_constant=lambda constant: (_raise(
                f"{source} contains non-standard JSON constant {constant}"
            )),
            object_pairs_hook=_reject_duplicate_members,
        )
    except AuditError:
        raise
    except (TypeError, ValueError) as error:
        raise AuditError(f"cannot parse {source}: {error}") from error
    validate_capture(value)
    return value


def _reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AuditError(f"capture contains duplicate JSON member: {key}")
        result[key] = value
    return result


def read_capture(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise AuditError(f"cannot read capture {path}: {error}") from error
    return _parse_capture(text, str(path))


def write_capture(path: Path, capture: object) -> None:
    validate_capture(capture)
    if not path.parent.is_dir():
        raise AuditError(f"capture parent does not exist: {path.parent}")
    payload = json.dumps(
        capture,
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        temporary.replace(path)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise AuditError(f"cannot write capture {path}: {error}") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture", help="capture current boundaries")
    capture.add_argument("--output", required=True, type=Path)
    capture.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    verify = commands.add_parser("verify", help="compare current boundaries to a capture")
    verify.add_argument("--baseline", required=True, type=Path)
    verify.add_argument("--output", type=Path)
    verify.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        current = capture_boundaries(args.fixture_root)
        if args.output is not None:
            write_capture(args.output, current)
        if args.command == "verify":
            expected = read_capture(args.baseline)
            verify_captures(expected, current)
            print("task lifecycle boundary corpus matches")
        else:
            print(f"wrote task lifecycle boundary capture: {args.output}")
        return 0
    except AuditError as error:
        print(f"task lifecycle audit failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
