"""Retained policy oracle and differential trace for executor settlement.

Run this module directly with ``python -m tools.executor_settlement_audit``.
The expected policy below is deliberately independent of the optional JSON
baseline: matching yesterday's implementation never makes an oracle mismatch
acceptable.
"""

from __future__ import annotations

import argparse
import copy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import UTC, datetime
import hashlib
import itertools
import json
import math
import os
from pathlib import Path, PureWindowsPath
import stat as stat_module
import subprocess
import tempfile
from typing import Any

from xxhash import xxh3_128

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import ItemOutcome, PhaseChanged, Progress
from namisync.core.execution import (
    Continue,
    CopyDigest,
    ExecutionSet,
    RecordedCopyIdentity,
    Retry,
    Stop,
    validated_run_id,
)
from namisync.core.models import (
    CapabilityProfile,
    EntryKind,
    FileIdentity,
    FileStat,
    Root,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import (
    Assignment,
    DeletionPolicy,
    FilterSet,
    OpId,
    OperationKind,
    OperationReason,
    Plan,
    PlanFingerprint,
    PlanOperation,
    PreservationPolicy,
)
from namisync.core.session import (
    Canceled,
    OperationResult,
    PauseRequested,
    RunContext,
    SessionState,
)
from namisync.modules.executor import ExecutorPolicies, NativeFileSystem, execute


FORMAT_VERSION = 1
RUN_ID = validated_run_id("a" * 32)
DEFAULT_BASELINE = Path(__file__).with_name("executor_settlement_baseline.json")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_BASELINE_GIT_PATH = "tools/executor_settlement_baseline.json"
REVIEWED_BASELINE_SHA256 = (
    "ed760ac0d4a90e766415018cf6db98e442f14b785cce5e25b32b82b2255bce2d"
)
_BYTE_KINDS = frozenset(
    {OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE}
)
_MISSING = {"$missing": True}
_CLOCK_INCIDENTAL_TREE_TIMESTAMPS = {
    "cleanup.ordinary.pre-retry-cleanup-fails": {
        f"$TARGET/copy.bin.synctmp-{RUN_ID}-{1:032x}": frozenset(
            {"created", "mtime"}
        ),
    },
}


class AuditError(RuntimeError):
    """The audit could not produce trustworthy evidence."""


@dataclass(slots=True)
class FaultRule:
    """Inject one public filesystem-boundary fault before or after a call."""

    method: str
    phase: str
    action: Callable[[tuple[object, ...], Mapping[str, object], object], None]
    predicate: Callable[[tuple[object, ...], Mapping[str, object], object], bool] = (
        lambda _args, _kwargs, _result: True
    )
    remaining: int = 1

    def matches(
        self,
        method: str,
        phase: str,
        args: tuple[object, ...],
        kwargs: Mapping[str, object],
        result: object,
    ) -> bool:
        return (
            self.remaining > 0
            and self.method == method
            and self.phase == phase
            and self.predicate(args, kwargs, result)
        )

    def fire(
        self,
        args: tuple[object, ...],
        kwargs: Mapping[str, object],
        result: object,
    ) -> None:
        self.remaining -= 1
        self.action(args, kwargs, result)


class TracingFileSystem:
    """Trace and fault only the public ``ExecutorFileSystem`` boundary."""

    def __init__(
        self,
        source_root: Path,
        target_root: Path,
        rules: Sequence[FaultRule] = (),
        timeline: list[str] | None = None,
    ) -> None:
        self._inner = NativeFileSystem()
        self._source_root = source_root
        self._target_root = target_root
        self._rules = list(rules)
        self._identity_labels: dict[FileIdentity, str] = {}
        self._volume_labels: dict[VolumeId, str] = {}
        self._timestamp_labels: dict[int, str] = {}
        self.trace: list[dict[str, object]] = []
        self.counts: dict[str, int] = {}
        self._timeline = timeline if timeline is not None else []

    def __getattr__(self, name: str) -> object:
        target = getattr(self._inner, name)
        if not callable(target):
            return target

        def invoke(*args: object, **kwargs: object) -> object:
            self.counts[name] = self.counts.get(name, 0) + 1
            self._timeline.append(f"fs:{name}:begin")
            entry: dict[str, object] = {
                "call": name,
                "args": self.value(args),
                "kwargs": self.value(kwargs),
            }
            try:
                self._fire(name, "before", args, kwargs, None)
                result = target(*args, **kwargs)
                if name == "trash_destination" and isinstance(result, Path):
                    # Audit-created trash parents carry no plan metadata. Pin
                    # their otherwise clock-dependent birth times so symbolic
                    # equality remains reproducible without flattening values.
                    current = result.parent
                    while current != self._target_root:
                        _stabilize_fixture_metadata(current)
                        current = current.parent
                entry["result"] = self.value(result)
                self._fire(name, "after", args, kwargs, result)
            except BaseException as error:
                entry["error"] = type(error).__name__
                entry["message"] = self.text(str(error))
                self.trace.append(entry)
                self._timeline.append(f"fs:{name}:error")
                raise
            self.trace.append(entry)
            self._timeline.append(f"fs:{name}:end")
            return result

        return invoke

    def _fire(
        self,
        method: str,
        phase: str,
        args: tuple[object, ...],
        kwargs: Mapping[str, object],
        result: object,
    ) -> None:
        for rule in self._rules:
            if rule.matches(method, phase, args, kwargs, result):
                rule.fire(args, kwargs, result)

    def require_faults_consumed(self, row: str) -> None:
        unused = [
            f"{index}:{rule.method}/{rule.phase} remaining={rule.remaining}"
            for index, rule in enumerate(self._rules, start=1)
            if rule.remaining != 0
        ]
        if unused:
            raise AuditError(
                f"{row}: installed fault rules were not consumed: {', '.join(unused)}"
            )

    def path(self, value: Path | str) -> str:
        candidate = Path(value)
        for root, label in (
            (self._source_root, "$SOURCE"),
            (self._target_root, "$TARGET"),
        ):
            try:
                relative = candidate.relative_to(root)
            except ValueError:
                continue
            suffix = relative.as_posix()
            return label if suffix == "." else f"{label}/{suffix}"
        return self.text(str(candidate))

    def text(self, value: str) -> str:
        text = value.replace("\\\\?\\", "")
        replacements = sorted(
            (
                (str(self._source_root), "$SOURCE"),
                (str(self._target_root), "$TARGET"),
            ),
            key=lambda pair: len(pair[0]),
            reverse=True,
        )
        for root, label in replacements:
            text = text.replace(root, label)
            text = text.replace(root.replace("\\", "/"), label)
        return text.replace("\\", "/")

    def timestamp(self, _category: str, value: int | None) -> str | None:
        if value is None:
            return None
        label = self._timestamp_labels.get(value)
        if label is None:
            label = f"time-{len(self._timestamp_labels) + 1}"
            self._timestamp_labels[value] = label
        return label

    def snapshot_identity(self, path: Path) -> object:
        observed = self._inner.stat_path(path)
        if observed is None:
            raise AuditError(f"tree file disappeared during identity snapshot: {path}")
        return self.value(observed.file_identity)

    def value(self, value: object) -> object:
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, Path):
            return self.path(value)
        if isinstance(value, bytes):
            return {
                "bytes": len(value),
                "sha256": hashlib.sha256(value).hexdigest(),
            }
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, FileIdentity):
            label = self._identity_labels.get(value)
            if label is None:
                label = f"identity-{len(self._identity_labels) + 1}"
                self._identity_labels[value] = label
            return label
        if isinstance(value, VolumeId):
            label = self._volume_labels.get(value)
            if label is None:
                label = f"volume-{len(self._volume_labels) + 1}"
                self._volume_labels[value] = label
            return label
        if isinstance(value, FileStat):
            return {
                "kind": value.kind.value,
                "size": value.size,
                "mtime": self.timestamp("mtime", value.mtime_ns),
                "identity": self.value(value.file_identity),
                "nlink": value.nlink,
                "attributes": value.metadata.attributes,
                "created": self.timestamp("created", value.metadata.created_ns),
            }
        if is_dataclass(value) and not isinstance(value, type):
            return {
                field.name: self.value(getattr(value, field.name))
                for field in fields(value)
            }
        if isinstance(value, Mapping):
            return {
                str(key): self.value(item)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            }
        if isinstance(value, (tuple, list)):
            return [self.value(item) for item in value]
        if isinstance(value, (set, frozenset)):
            return sorted(
                (self.value(item) for item in value),
                key=lambda item: json.dumps(item, sort_keys=True),
            )
        if hasattr(value, "read") or hasattr(value, "write"):
            return "<stream>"
        if callable(value):
            return "<callable>"
        enum_value = getattr(value, "value", None)
        if isinstance(enum_value, str):
            return enum_value
        return f"<{type(value).__name__}>"


class SynchronousCopyBackend:
    """Deterministic one-thread CopyBackend used to isolate settlement policy."""

    def __init__(
        self,
        *,
        fail_before_read: bool = False,
        fail_midcopy_sharing_once: bool = False,
    ) -> None:
        self.fail_before_read = fail_before_read
        self.fail_midcopy_sharing_once = fail_midcopy_sharing_once
        self.calls = 0
        self.trace: list[dict[str, object]] = []
        self._timeline: list[str] = []

    def bind_timeline(self, timeline: list[str]) -> None:
        self._timeline = timeline

    def copy(
        self,
        source,
        target,
        *,
        chunk_size: int,
        checkpoint: Callable[[], None],
        on_chunk: Callable[[int], None],
    ) -> CopyDigest:
        self.calls += 1
        call = self.calls
        self._timeline.append(f"backend:copy:{call}:begin")
        record: dict[str, object] = {
            "call": call,
            "chunk_size": chunk_size,
        }
        try:
            self._timeline.append(f"backend:copy:{call}:checkpoint:begin")
            try:
                checkpoint()
            except BaseException as error:
                self._timeline.append(
                    f"backend:copy:{call}:checkpoint:raise:{type(error).__name__}"
                )
                raise
            self._timeline.append(f"backend:copy:{call}:checkpoint:end")
            if self.fail_before_read:
                raise OSError("injected copy failure before read")
            hasher = xxh3_128()
            total = 0
            chunks = 0
            while True:
                chunk = source.read(chunk_size)
                if not chunk:
                    break
                if self.fail_midcopy_sharing_once and call == 1 and chunks == 1:
                    raise _sharing_error("injected mid-copy sharing failure")
                hasher.update(chunk)
                view = memoryview(chunk)
                written = 0
                while written < len(view):
                    count = target.write(view[written:])
                    if count is None or count <= 0:
                        raise OSError("synchronous audit backend made no write progress")
                    written += count
                total += len(chunk)
                chunks += 1
                self._timeline.append(
                    f"backend:copy:{call}:chunk:{chunks}:bytes:{len(chunk)}"
                )
                on_chunk(len(chunk))
            record.update({"bytes": total, "chunks": chunks})
            self.trace.append(record)
            self._timeline.append(f"backend:copy:{call}:end")
            return CopyDigest(hasher.digest(), total)
        except BaseException as error:
            record["error"] = type(error).__name__
            self.trace.append(record)
            self._timeline.append(
                f"backend:copy:{call}:error:{type(error).__name__}"
            )
            raise


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 10, 12, tzinfo=UTC)


class TrackingFailurePolicy:
    def __init__(
        self,
        *,
        retries: int = 0,
        stop: bool = False,
        raise_once: bool = False,
        timeline: list[str] | None = None,
    ) -> None:
        self.retries = retries
        self.stop = stop
        self.raise_remaining = 1 if raise_once else 0
        self.trace: list[dict[str, object]] = []
        self._timeline = timeline if timeline is not None else []

    def on_item_failed(
        self, operation: PlanOperation, error: Exception, attempt: int
    ) -> Continue | Retry | Stop:
        if self.raise_remaining:
            self.raise_remaining -= 1
            self.trace.append(
                {
                    "op": str(operation.op_id),
                    "kind": operation.kind.value,
                    "attempt": attempt,
                    "error": type(error).__name__,
                    "decision": "raise",
                }
            )
            self._timeline.append(
                "failure-policy:"
                f"{operation.op_id}:attempt:{attempt}:raise:RuntimeError"
            )
            raise RuntimeError("injected failure-policy escape")
        if len(self.trace) < self.retries:
            decision: Continue | Retry | Stop = Retry(0)
            decision_name = "retry"
        elif self.stop:
            decision = Stop()
            decision_name = "stop"
        else:
            decision = Continue()
            decision_name = "continue"
        self.trace.append(
            {
                "op": str(operation.op_id),
                "kind": operation.kind.value,
                "attempt": attempt,
                "error": type(error).__name__,
                "decision": decision_name,
            }
        )
        self._timeline.append(
            "failure-policy:"
            f"{operation.op_id}:attempt:{attempt}:decision:{decision_name}"
        )
        return decision


class TrackingControl:
    def __init__(
        self,
        *,
        cancel_at: int | None = None,
        pause_at: int | None = None,
        exception_at: int | None = None,
        retry_control: str | None = None,
        timeline: list[str] | None = None,
    ) -> None:
        self.cancel_at = cancel_at
        self.pause_at = pause_at
        self.exception_at = exception_at
        self.exception_remaining = 1 if exception_at is not None else 0
        self.retry_control = retry_control
        self.checkpoints = 0
        self.backoff_started = False
        self.pause_observed = False
        self._timeline = timeline if timeline is not None else []

    def checkpoint(self) -> None:
        self.checkpoints += 1
        token = f"control:checkpoint:{self.checkpoints}"
        self._timeline.append(f"{token}:begin")
        if self.exception_at == self.checkpoints:
            self.exception_remaining -= 1
            self._timeline.append(f"{token}:raise:RuntimeError")
            raise RuntimeError("injected checkpoint infrastructure escape")
        if self.cancel_at == self.checkpoints:
            self._timeline.append(f"{token}:raise:Canceled")
            raise Canceled()
        if self.pause_at == self.checkpoints:
            self._timeline.append(f"{token}:raise:PauseRequested")
            raise PauseRequested()
        if self.backoff_started and self.retry_control == "pause":
            self._timeline.append(f"{token}:raise:PauseRequested")
            raise PauseRequested()
        if self.backoff_started and self.retry_control == "pause-then-cancel":
            if not self.pause_observed:
                self.pause_observed = True
                self._timeline.append(f"{token}:raise:PauseRequested")
                raise PauseRequested()
            self._timeline.append(f"{token}:raise:Canceled")
            raise Canceled()
        self._timeline.append(f"{token}:end")


class TrackingPacing:
    def __init__(
        self,
        *,
        cancel_on_sleep: bool = False,
        raise_on_sleep: bool = False,
        control: TrackingControl | None = None,
        timeline: list[str] | None = None,
    ) -> None:
        self._ticks = itertools.count()
        self.sleeps: list[float] = []
        self.cancel_on_sleep = cancel_on_sleep
        self.raise_remaining = 1 if raise_on_sleep else 0
        self.control = control
        self._timeline = timeline if timeline is not None else []

    def monotonic(self) -> float:
        return float(next(self._ticks))

    def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        token = f"pacing:sleep:{delay:g}"
        self._timeline.append(f"{token}:begin")
        if self.control is not None:
            self.control.backoff_started = True
        if self.cancel_on_sleep:
            self._timeline.append(f"{token}:raise:Canceled")
            raise Canceled()
        if self.raise_remaining:
            self.raise_remaining -= 1
            self._timeline.append(f"{token}:raise:RuntimeError")
            raise RuntimeError("injected retry-sleep escape")
        self._timeline.append(f"{token}:end")


class TraceRecorder:
    """Recorder double with coherent public identities and ordered calls."""

    def __init__(
        self,
        plan: Plan,
        *,
        fail: frozenset[str] = frozenset(),
        fail_once: frozenset[str] = frozenset(),
        timeline: list[str] | None = None,
        normalize: Callable[[object], object] | None = None,
    ) -> None:
        self._paths = {
            operation.op_id: normalize_relative_path(operation.target_rel_path)
            for operation in plan.operations
        }
        self._fail = fail
        self._fail_once = set(fail_once)
        self.trace: list[dict[str, object]] = []
        self._timeline = timeline if timeline is not None else []
        self._normalize = normalize or (lambda value: value)

    def _call(
        self,
        command: str,
        payload: Mapping[str, object],
        result: object = None,
    ) -> object:
        self._timeline.append(f"recorder:{command}")
        entry: dict[str, object] = {
            "command": command,
            "payload": self._normalize(payload),
            "result": None,
        }
        if command in self._fail or command in self._fail_once:
            self._fail_once.discard(command)
            entry["error"] = "RuntimeError"
            entry["message"] = f"injected {command} recorder failure"
            self.trace.append(entry)
            self._timeline.append(f"recorder:{command}:error:RuntimeError")
            raise RuntimeError(f"injected {command} recorder failure")
        entry["result"] = self._normalize(result)
        self.trace.append(entry)
        self._timeline.append(f"recorder:{command}:end")
        return result

    def _identity(self, op: OpId) -> RecordedCopyIdentity:
        return RecordedCopyIdentity(
            row_id=f"row-{op}",
            location_id="audit-target",
            scope_token=str(RUN_ID),
            rel_path_key=self._paths[op],
        )

    def flush(self) -> None:
        self._call("flush", {})

    def record_copied(self, op: OpId, attestation) -> RecordedCopyIdentity:
        identity = self._identity(op)
        self._call(
            "copied",
            {"op": str(op), "attestation": attestation},
            identity,
        )
        return identity

    def record_updated(self, op: OpId, attestation) -> RecordedCopyIdentity:
        identity = self._identity(op)
        self._call(
            "updated",
            {"op": str(op), "attestation": attestation},
            identity,
        )
        return identity

    def record_move_updated(self, op: OpId, attestation) -> RecordedCopyIdentity:
        identity = self._identity(op)
        self._call(
            "move_updated",
            {"op": str(op), "attestation": attestation},
            identity,
        )
        return identity

    def record_moved(self, op: OpId, target: FileStat) -> None:
        self._call("moved", {"op": str(op), "target": target})

    def record_recased(self, op: OpId, target: FileStat) -> None:
        self._call("recased", {"op": str(op), "target": target})

    def record_mkdir(self, op: OpId, target: FileStat) -> None:
        self._call("mkdir", {"op": str(op), "target": target})

    def record_trashed(
        self, op: OpId, trash_relative_path: str, target: FileStat
    ) -> None:
        self._call(
            "trashed",
            {
                "op": str(op),
                "trash_relative_path": trash_relative_path,
                "target": target,
            },
        )

    def record_deleted(self, op: OpId, prior: FileStat) -> None:
        self._call("deleted", {"op": str(op), "prior": prior})

    def record_noop(
        self, op: OpId, source: FileStat, target: FileStat
    ) -> None:
        self._call(
            "noop",
            {"op": str(op), "source": source, "target": target},
        )


@dataclass(frozen=True, slots=True)
class ExpectedItem:
    kind: str
    outcome: str
    reason: str | None
    detail_contains: tuple[tuple[str, object], ...] = ()
    detail_absent: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _TreeMetadataRelation:
    operation: int
    reference: str
    mtime_matches: bool
    created_matches: bool
    identity_matches: bool | None

    @property
    def op(self) -> str:
        return f"{self.operation:032x}"


@dataclass(frozen=True, slots=True)
class ExpectedSettlement:
    returned: str | None
    raised: str | None
    recording: str
    items: tuple[ExpectedItem, ...]
    recorder_commands: tuple[str, ...]
    evidence_recorded: tuple[bool, ...] = ()
    tree_files: tuple[tuple[str, str], ...] = ()
    tree_directories: tuple[str, ...] = ()
    tree_readonly: tuple[str, ...] = ()
    tree_absent: tuple[str, ...] = ()
    backend_calls: int | None = None
    recorder_flushes: int | None = None
    control_checkpoints: int | None = None
    policy_decisions: tuple[str, ...] = ()
    fs_counts: tuple[tuple[str, int], ...] = ()
    timeline_subsequence: tuple[str, ...] = ()
    row: str = ""

    def errors(self, report: Mapping[str, object]) -> list[str]:
        errors: list[str] = []
        expected_policy = _expected_policy_projection(self)
        observed_policy = _policy_projection(report)
        difference = _first_strict_difference(expected_policy, observed_policy)
        if difference is not None:
            errors.append(f"exact policy projection: {difference}")
        _expect(errors, "row", report.get("row"), self.row)
        termination = _mapping(report.get("termination"), "termination", errors)
        _expect(errors, "termination.returned", termination.get("returned"), self.returned)
        _expect(errors, "termination.raised", termination.get("raised"), self.raised)
        xset = _mapping(report.get("execution_set"), "execution_set", errors)
        _expect(errors, "execution_set.recording", xset.get("recording"), self.recording)

        raw_items = report.get("items")
        items = raw_items if isinstance(raw_items, list) else []
        if len(items) != len(self.items):
            errors.append(f"items length: expected {len(self.items)}, observed {len(items)}")
        for index, expected in enumerate(self.items):
            if index >= len(items) or not isinstance(items[index], Mapping):
                continue
            actual = items[index]
            prefix = f"items[{index}]"
            _expect(errors, f"{prefix}.kind", actual.get("kind"), expected.kind)
            _expect(errors, f"{prefix}.outcome", actual.get("outcome"), expected.outcome)
            _expect(errors, f"{prefix}.reason", actual.get("reason"), expected.reason)
            detail = actual.get("detail")
            detail_map = detail if isinstance(detail, Mapping) else {}
            for key, value in expected.detail_contains:
                _expect(errors, f"{prefix}.detail.{key}", detail_map.get(key), value)
            for key in expected.detail_absent:
                if key in detail_map:
                    errors.append(f"{prefix}.detail.{key}: expected absent, observed {detail_map[key]!r}")

        recorder = _mapping(report.get("recorder"), "recorder", errors)
        trace = recorder.get("trace")
        commands = tuple(
            str(entry.get("command"))
            for entry in trace if isinstance(entry, Mapping)
            if entry.get("command") != "flush"
        ) if isinstance(trace, list) else ()
        _expect(errors, "recorder commands", commands, self.recorder_commands)
        if self.recorder_flushes is not None:
            flushes = (
                sum(
                    1
                    for entry in trace
                    if isinstance(entry, Mapping)
                    and entry.get("command") == "flush"
                )
                if isinstance(trace, list)
                else 0
            )
            _expect(errors, "recorder flushes", flushes, self.recorder_flushes)

        evidence = xset.get("published_evidence")
        recorded = tuple(
            bool(entry.get("recorded"))
            for entry in evidence if isinstance(entry, Mapping)
        ) if isinstance(evidence, list) else ()
        _expect(errors, "published evidence", recorded, self.evidence_recorded)

        tree = report.get("tree")
        tree_map = tree if isinstance(tree, Mapping) else {}
        for path, content in self.tree_files:
            observed = tree_map.get(path)
            if not isinstance(observed, Mapping):
                errors.append(f"tree {path}: expected file, observed {observed!r}")
                continue
            _expect(errors, f"tree {path}.kind", observed.get("kind"), "file")
            _expect(errors, f"tree {path}.text", observed.get("text"), content)
        for path in self.tree_directories:
            observed = tree_map.get(path)
            if not isinstance(observed, Mapping):
                errors.append(f"tree {path}: expected directory, observed {observed!r}")
                continue
            _expect(errors, f"tree {path}.kind", observed.get("kind"), "directory")
        for path in self.tree_absent:
            if path in tree_map:
                errors.append(f"tree {path}: expected absent, observed {tree_map[path]!r}")

        backend = _mapping(report.get("copy_backend"), "copy_backend", errors)
        if self.backend_calls is not None:
            _expect(errors, "copy_backend.calls", backend.get("calls"), self.backend_calls)
        control = _mapping(report.get("control"), "control", errors)
        if self.control_checkpoints is not None:
            _expect(
                errors,
                "control.checkpoints",
                control.get("checkpoints"),
                self.control_checkpoints,
            )
        policy = _mapping(report.get("failure_policy"), "failure_policy", errors)
        policy_trace = policy.get("trace")
        decisions = tuple(
            str(entry.get("decision"))
            for entry in policy_trace if isinstance(entry, Mapping)
        ) if isinstance(policy_trace, list) else ()
        _expect(errors, "failure policy decisions", decisions, self.policy_decisions)
        fs = _mapping(report.get("filesystem"), "filesystem", errors)
        counts = fs.get("counts")
        count_map = counts if isinstance(counts, Mapping) else {}
        for method, expected_count in self.fs_counts:
            _expect(errors, f"filesystem.counts.{method}", count_map.get(method, 0), expected_count)
        timeline = report.get("timeline")
        timeline_items = [str(item) for item in timeline] if isinstance(timeline, list) else []
        cursor = 0
        for expected_token in self.timeline_subsequence:
            try:
                cursor = timeline_items.index(expected_token, cursor) + 1
            except ValueError:
                errors.append(
                    "timeline subsequence: expected "
                    f"{expected_token!r} after index {cursor}, observed {timeline_items!r}"
                )
                break
        errors.extend(_global_invariant_errors(report))
        return errors


@dataclass(frozen=True, slots=True)
class Scenario:
    scenario_id: str
    kinds: frozenset[OperationKind]
    tags: frozenset[str]
    runner: Callable[[Path], list[dict[str, object]]]
    expected: tuple[ExpectedSettlement, ...]


def _mapping(value: object, name: str, errors: list[str]) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    errors.append(f"{name}: expected mapping, observed {value!r}")
    return {}


def _expect(errors: list[str], path: str, actual: object, expected: object) -> None:
    if actual != expected:
        errors.append(f"{path}: expected {expected!r}, observed {actual!r}")


def _first_strict_difference(expected: object, observed: object, path: str = "$") -> str | None:
    if type(expected) is not type(observed):
        return (
            f"{path}: expected {type(expected).__name__} {expected!r}, "
            f"observed {type(observed).__name__} {observed!r}"
        )
    if isinstance(expected, Mapping):
        expected_keys = set(expected)
        observed_keys = set(observed)
        if expected_keys != observed_keys:
            return (
                f"{path}: expected keys {sorted(expected_keys)!r}, "
                f"observed {sorted(observed_keys)!r}"
            )
        for key in expected:
            difference = _first_strict_difference(
                expected[key], observed[key], f"{path}.{key}"
            )
            if difference is not None:
                return difference
        return None
    if isinstance(expected, (tuple, list)):
        if len(expected) != len(observed):
            return f"{path}: expected length {len(expected)}, observed {len(observed)}"
        for index, (expected_item, observed_item) in enumerate(
            zip(expected, observed, strict=True)
        ):
            difference = _first_strict_difference(
                expected_item, observed_item, f"{path}[{index}]"
            )
            if difference is not None:
                return difference
        return None
    if expected != observed:
        return f"{path}: expected {expected!r}, observed {observed!r}"
    return None


def _profile(*, hardlinks: bool = True) -> CapabilityProfile:
    return CapabilityProfile(
        fs_type="NTFS",
        mtime_granularity_ns=100,
        stable_file_identity=True,
        incurs_seek_penalty=False,
        max_path=32767,
        supports_ads=True,
        supports_hardlinks=hardlinks,
    )


def _operation(
    number: int,
    kind: OperationKind,
    *,
    source_rel_path: str | None,
    target_rel_path: str,
    source_expected: FileStat | None,
    target_expected: FileStat | None,
    intended: FileStat | None,
    prior_target_rel_path: str | None = None,
    prior_target_expected: FileStat | None = None,
    dependencies: tuple[OpId, ...] = (),
    reason: OperationReason = OperationReason.SOURCE_ONLY,
) -> PlanOperation:
    return PlanOperation(
        op_id=OpId(f"{number:032x}"),
        kind=kind,
        source_rel_path=source_rel_path,
        target_rel_path=target_rel_path,
        source_expected=source_expected,
        target_expected=target_expected,
        intended=intended,
        prior_target_rel_path=prior_target_rel_path,
        prior_target_expected=prior_target_expected,
        metadata=None if intended is None else intended.metadata,
        content_bytes=(
            source_expected.size
            if source_expected is not None and kind in _BYTE_KINDS
            else 0
        ),
        dependencies=dependencies,
        reason=reason,
    )


def _plan(
    source: Path,
    target: Path,
    operations: tuple[PlanOperation, ...],
    *,
    hardlinks: bool = True,
    trash_on_update: bool = True,
) -> Plan:
    profile = _profile(hardlinks=hardlinks)
    return Plan(
        source_root=Root(str(source), "source"),
        target_root=Root(str(target), "target"),
        source_volume_id=None,
        target_volume_id=None,
        source_volume_evidence=None,
        target_volume_evidence=None,
        source_profile=profile,
        target_profile=profile,
        source_complete=True,
        target_complete=True,
        operations=operations,
        assignment=Assignment("identity", "1", ()),
        preservation=PreservationPolicy(),
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=trash_on_update,
        policy_fingerprint="p" * 64,
        required_volumes=frozenset(),
        required_bytes=sum(operation.content_bytes for operation in operations),
        fingerprint=PlanFingerprint("f" * 64),
    )


def _write(root: Path, relative: str, content: bytes) -> Path:
    path = root.joinpath(*PureWindowsPath(relative).parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    _stabilize_fixture_metadata(path)
    return path


def _mkdir(root: Path, relative: str) -> Path:
    path = root.joinpath(*PureWindowsPath(relative).parts)
    path.mkdir(parents=True, exist_ok=True)
    _stabilize_fixture_metadata(path)
    return path


def _stabilize_fixture_metadata(path: Path) -> None:
    """Assign repeatable, distinct audit-only times before execution observes a path."""
    parts = path.parts
    anchor = next(
        (
            index
            for index, part in enumerate(parts)
            if part.casefold() in {"source", "target"}
        ),
        len(parts) - 1,
    )
    role = parts[anchor].casefold()
    relative = "/".join(part.casefold() for part in parts[anchor + 1 :])
    digest = hashlib.sha256(f"{role}/{relative}".encode("utf-8")).digest()
    offset = int.from_bytes(digest[:6], "big") * 100
    created_ns = 1_700_000_000_000_000_000 + offset
    mtime_ns = created_ns + 10_000
    filesystem = NativeFileSystem()
    observed = filesystem.stat_path(path)
    if observed is None:
        raise AuditError(f"fixture path disappeared during metadata setup: {path}")
    filesystem.apply_metadata(
        path,
        replace(
            observed,
            mtime_ns=mtime_ns,
            metadata=replace(observed.metadata, created_ns=created_ns),
        ),
        preserve_created=True,
        apply_readonly=True,
    )


def _stat(fs: NativeFileSystem, root: Path, relative: str) -> FileStat:
    observed = fs.stat(root, relative)
    if observed is None:
        raise AuditError(f"fixture path is missing: {relative}")
    return observed


def _sync_mtime(path: Path, expected: FileStat) -> None:
    os.utime(path, ns=(expected.mtime_ns, expected.mtime_ns))


def _io_error(message: str) -> OSError:
    return OSError(message)


def _sharing_error(message: str) -> OSError:
    error = OSError(message)
    error.winerror = 32  # type: ignore[attr-defined]
    return error


def _raise(error_factory: Callable[[], BaseException]) -> Callable[..., None]:
    def action(_args, _kwargs, _result) -> None:
        raise error_factory()

    return action


def _path_argument_is(expected: Path) -> Callable[..., bool]:
    def predicate(args, _kwargs, _result) -> bool:
        return bool(args) and Path(args[0]) == expected

    return predicate


def _target_argument_is(expected: Path) -> Callable[..., bool]:
    def predicate(args, _kwargs, _result) -> bool:
        return len(args) >= 2 and Path(args[1]) == expected

    return predicate


def _run_fixture(
    source: Path,
    target: Path,
    operations: tuple[PlanOperation, ...],
    *,
    row: str = "",
    rules: Sequence[FaultRule] = (),
    backend: SynchronousCopyBackend | None = None,
    recorder_fail: frozenset[str] = frozenset(),
    recorder_fail_once: frozenset[str] = frozenset(),
    retries: int = 0,
    stop: bool = False,
    failure_policy_escape: bool = False,
    cancel_at: int | None = None,
    pause_at: int | None = None,
    checkpoint_exception_at: int | None = None,
    cancel_on_sleep: bool = False,
    retry_sleep_escape: bool = False,
    retry_control: str | None = None,
    hardlinks: bool = True,
    trash_on_update: bool = True,
) -> dict[str, object]:
    plan = _plan(
        source,
        target,
        operations,
        hardlinks=hardlinks,
        trash_on_update=trash_on_update,
    )
    xset = ExecutionSet(
        plan,
        frozenset(operation.op_id for operation in operations),
        RUN_ID,
    )
    timeline: list[str] = []
    filesystem = TracingFileSystem(source, target, rules, timeline)
    copy_backend = backend or SynchronousCopyBackend()
    copy_backend.bind_timeline(timeline)
    recorder = TraceRecorder(
        plan,
        fail=recorder_fail,
        fail_once=recorder_fail_once,
        timeline=timeline,
        normalize=filesystem.value,
    )
    failure = TrackingFailurePolicy(
        retries=retries,
        stop=stop,
        raise_once=failure_policy_escape,
        timeline=timeline,
    )
    control = TrackingControl(
        cancel_at=cancel_at,
        pause_at=pause_at,
        exception_at=checkpoint_exception_at,
        retry_control=retry_control,
        timeline=timeline,
    )
    pacing = TrackingPacing(
        cancel_on_sleep=cancel_on_sleep,
        raise_on_sleep=retry_sleep_escape,
        control=control,
        timeline=timeline,
    )
    events: list[object] = []

    def emit(event: object) -> None:
        # Progress is intentionally lossy/coalesced; only reliable phase/item
        # emissions belong to the exact tape. The final progress projection is
        # retained separately below.
        if isinstance(event, PhaseChanged):
            timeline.append(f"emit:phase:{event.phase}")
        elif isinstance(event, ItemOutcome):
            timeline.append(
                "emit:item:"
                f"{event.item_id}:{event.kind}:{event.outcome.value}"
            )
        events.append(event)

    result = None
    raised: BaseException | None = None
    policies = ExecutorPolicies(
        copy_backend=copy_backend,
        failure=failure,
        clock=FixedClock(),
        max_chunk_size=4,
        max_retries=max(1, retries),
        progress_interval_seconds=10_000,
        monotonic=pacing.monotonic,
        sleep=pacing.sleep,
    )
    try:
        result = execute(
            xset,
            RunContext(emit, control.checkpoint),
            recorder,
            policies,
            filesystem,  # type: ignore[arg-type]
        )
    except (Canceled, PauseRequested) as error:
        raised = error
    except BaseException as error:  # retained for exact terminal expectations
        raised = error

    filesystem.require_faults_consumed(row)
    unused_injections = []
    if failure.raise_remaining:
        unused_injections.append("failure-policy escape")
    if control.exception_remaining:
        unused_injections.append("checkpoint exception")
    if pacing.raise_remaining:
        unused_injections.append("retry-sleep escape")
    if unused_injections:
        raise AuditError(
            f"{row}: installed collaborator injections were not consumed: "
            + ", ".join(unused_injections)
        )

    return _build_report(
        row=row,
        source=source,
        target=target,
        operations=operations,
        xset=xset,
        result=result,
        raised=raised,
        events=events,
        filesystem=filesystem,
        copy_backend=copy_backend,
        recorder=recorder,
        failure=failure,
        control=control,
        pacing=pacing,
        timeline=timeline,
    )


def _event_projection(
    events: Sequence[object], normalizer: TracingFileSystem
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object] | None]:
    item_events = [event for event in events if isinstance(event, ItemOutcome)]
    reliable_events: list[dict[str, object]] = []
    for event in events:
        if isinstance(event, PhaseChanged):
            reliable_events.append({"type": "phase", "phase": event.phase})
        elif isinstance(event, ItemOutcome):
            reliable_events.append(
                {
                    "type": "item",
                    "op": event.item_id,
                    "kind": event.kind,
                    "path": event.path,
                    "outcome": event.outcome.value,
                    "reason": event.reason,
                    "detail": normalizer.value(event.detail),
                }
            )
    progress = [event for event in events if isinstance(event, Progress)]
    final_progress = None
    if progress:
        final = progress[-1]
        final_progress = {
            "items_done": final.items_done,
            "items_total": final.items_total,
            "bytes_done": final.bytes_done,
            "bytes_total": final.bytes_total,
            "current_path": final.current_path,
        }

    items = [
        {
            "op": event.item_id,
            "kind": event.kind,
            "path": event.path,
            "outcome": event.outcome.value,
            "reason": event.reason,
            "detail": normalizer.value(event.detail),
        }
        for event in item_events
    ]
    return items, reliable_events, final_progress


def _execution_set_projection(
    xset: ExecutionSet,
    operations: Sequence[PlanOperation],
    normalizer: TracingFileSystem,
) -> dict[str, object]:
    evidence: list[dict[str, object]] = []
    for operation in operations:
        published = xset.published_evidence.get(operation.op_id)
        if published is None:
            continue
        evidence.append(
            {
                "op": str(operation.op_id),
                "kind": operation.kind.value,
                "path": operation.target_rel_path,
                "recorded": published.recorded_identity is not None,
                "content": {
                    "algorithm": published.attestation.content.algorithm,
                    "digest": published.attestation.content.digest.hex(),
                    "size": published.attestation.content.size,
                    "provenance": published.attestation.content.provenance.value,
                    "observed_at": normalizer.value(
                        published.attestation.content.observed_at
                    ),
                },
                "subject": normalizer.value(published.attestation.subject),
                "recorded_identity": normalizer.value(
                    published.recorded_identity
                ),
            }
        )

    return {
        "selected": len(xset.selection),
        "selection": [
            {"op": str(operation.op_id), "kind": operation.kind.value}
            for operation in operations
            if operation.op_id in xset.selection
        ],
        "recording": xset.recording.value,
        "status": [
            {
                "op": str(operation.op_id),
                "kind": operation.kind.value,
                "outcome": xset.status[operation.op_id].value,
            }
            for operation in operations
            if operation.op_id in xset.status
        ],
        "published_evidence": evidence,
    }


def _operation_contract_projection(
    operations: Sequence[PlanOperation],
    normalizer: TracingFileSystem,
) -> list[dict[str, object]]:
    """Retain reviewed metadata facts used by the independent tree oracle."""

    return [
        {
            "op": str(operation.op_id),
            "kind": operation.kind.value,
            "source_rel_path": operation.source_rel_path,
            "target_rel_path": operation.target_rel_path,
            "prior_target_rel_path": operation.prior_target_rel_path,
            "source_expected": normalizer.value(operation.source_expected),
            "target_expected": normalizer.value(operation.target_expected),
            "intended": normalizer.value(operation.intended),
            "prior_target_expected": normalizer.value(
                operation.prior_target_expected
            ),
        }
        for operation in operations
    ]


def _build_report(
    *,
    row: str,
    source: Path,
    target: Path,
    operations: Sequence[PlanOperation],
    xset: ExecutionSet,
    result: OperationResult | None,
    raised: BaseException | None,
    events: Sequence[object],
    filesystem: TracingFileSystem,
    copy_backend: SynchronousCopyBackend,
    recorder: TraceRecorder,
    failure: TrackingFailurePolicy,
    control: TrackingControl,
    pacing: TrackingPacing,
    timeline: list[str],
) -> dict[str, object]:
    items, reliable_events, final_progress = _event_projection(events, filesystem)
    return {
        "row": row,
        "termination": {
            "returned": None if result is None else result.status.value,
            "raised": None if raised is None else type(raised).__name__,
        },
        "result": None if result is None else _operation_result(result, filesystem),
        "execution_set": _execution_set_projection(xset, operations, filesystem),
        "operation_contracts": _operation_contract_projection(
            operations, filesystem
        ),
        "items": items,
        "reliable_events": reliable_events,
        "progress_final": final_progress,
        "recorder": {"trace": recorder.trace},
        "failure_policy": {"trace": failure.trace},
        "control": {
            "checkpoints": control.checkpoints,
            "sleeps": pacing.sleeps,
        },
        "copy_backend": {
            "calls": copy_backend.calls,
            "trace": copy_backend.trace,
        },
        "filesystem": {
            "counts": dict(sorted(filesystem.counts.items())),
            "trace": filesystem.trace,
        },
        "timeline": timeline,
        "tree": _tree_snapshot(source, target, filesystem, row=row),
    }


def _operation_result(
    result: OperationResult, normalizer: TracingFileSystem
) -> dict[str, object]:
    return {
        "status": result.status.value,
        "recording": result.recording.value,
        "audit": result.audit.value,
        "disposition": result.disposition.value,
        "canceled": result.canceled,
        "items": [
            {
                "op": item.item_id,
                "kind": item.kind,
                "path": item.path,
                "outcome": item.outcome.value,
                "reason": item.reason,
                "detail": normalizer.value(item.detail),
            }
            for item in result.items
        ],
        "phases": [
            {
                "phase": phase.phase,
                "status": phase.status.value,
                "items_done": phase.items_done,
                "items_total": phase.items_total,
                "bytes_done": phase.bytes_done,
                "bytes_total": phase.bytes_total,
                "error": phase.error,
            }
            for phase in result.phases
        ],
        "bytes_done": result.bytes_done,
        "bytes_total": result.bytes_total,
        "error": (
            None
            if result.error is None
            else {
                "type_name": result.error.type_name,
                "message": result.error.message,
            }
        ),
    }


def _attestation_subject_policy(
    subject: object, target: object
) -> dict[str, object]:
    subject_map = subject if isinstance(subject, Mapping) else {}
    target_map = target if isinstance(target, Mapping) else {}
    return {
        "schema": sorted(str(key) for key in subject_map),
        "kind": subject_map.get("kind"),
        "size": subject_map.get("size"),
        "identity_present": subject_map.get("identity") is not None,
        "identity_matches_tree": (
            subject_map.get("identity") == target_map.get("identity")
        ),
        "nlink": subject_map.get("nlink"),
        "attributes": subject_map.get("attributes"),
        "mtime_present": subject_map.get("mtime") is not None,
        "created_present": subject_map.get("created") is not None,
        "mtime_matches_tree": subject_map.get("mtime") == target_map.get("mtime"),
        "created_matches_tree": subject_map.get("created")
        == target_map.get("created"),
    }


def _recorded_stat_policy(
    value: object, reference: object
) -> dict[str, object]:
    stat_map = value if isinstance(value, Mapping) else {}
    reference_map = reference if isinstance(reference, Mapping) else {}

    def matches(key: str) -> bool | None:
        if key not in stat_map or key not in reference_map:
            return None
        return stat_map[key] == reference_map[key]

    return {
        "schema": sorted(str(key) for key in stat_map),
        "kind": stat_map.get("kind"),
        "size": stat_map.get("size"),
        "identity_present": stat_map.get("identity") is not None,
        "nlink": stat_map.get("nlink"),
        "attributes": stat_map.get("attributes"),
        "kind_matches_reference": matches("kind"),
        "size_matches_reference": matches("size"),
        "identity_matches_reference": matches("identity"),
        "mtime_matches_reference": matches("mtime"),
        "created_matches_reference": matches("created"),
    }


def _recorder_policy_projection(
    report: Mapping[str, object],
    tree_map: Mapping[str, object],
    contract_map: Mapping[str, Mapping[str, object] | None],
) -> list[dict[str, object]] | object:
    recorder = report.get("recorder")
    recorder_map = recorder if isinstance(recorder, Mapping) else {}
    trace = recorder_map.get("trace")
    if not isinstance(trace, list):
        return _MISSING if "recorder" not in report else {"$invalid": trace}

    projected: list[dict[str, object]] = []
    for raw in trace:
        if not isinstance(raw, Mapping):
            projected.append({"malformed": raw})
            continue
        command = raw.get("command")
        if command == "flush":
            projected.append(
                {
                    "schema": sorted(str(key) for key in raw),
                    "command": command,
                    "payload": raw.get("payload"),
                    "result": raw.get("result"),
                    "error": raw.get("error"),
                    "message": raw.get("message"),
                }
            )
            continue
        payload = raw.get("payload")
        payload_map = payload if isinstance(payload, Mapping) else {}
        op = payload_map.get("op")
        contract = contract_map.get(str(op))
        contract_values = contract if isinstance(contract, Mapping) else {}
        target_relative = contract_values.get("target_rel_path")
        target_path = (
            None
            if not isinstance(target_relative, str)
            else "$TARGET/" + PureWindowsPath(target_relative).as_posix()
        )
        target = tree_map.get(target_path) if target_path is not None else None
        projected_payload: dict[str, object] = {
            "schema": sorted(str(key) for key in payload_map),
            "op": op,
        }
        if command in {"copied", "updated", "move_updated"}:
            attestation = payload_map.get("attestation")
            attestation_map = (
                attestation if isinstance(attestation, Mapping) else {}
            )
            projected_payload["attestation"] = {
                "schema": sorted(str(key) for key in attestation_map),
                "content": attestation_map.get("content"),
                "subject": _attestation_subject_policy(
                    attestation_map.get("subject"), target
                ),
            }
        elif command in {"moved", "recased", "mkdir"}:
            projected_payload["target"] = _recorded_stat_policy(
                payload_map.get("target"), target
            )
        elif command == "trashed":
            trash_relative = payload_map.get("trash_relative_path")
            trash_path = (
                None
                if not isinstance(trash_relative, str)
                else "$TARGET/" + PureWindowsPath(trash_relative).as_posix()
            )
            projected_payload["trash_relative_path"] = trash_relative
            projected_payload["target"] = _recorded_stat_policy(
                payload_map.get("target"), tree_map.get(trash_path)
            )
        elif command == "deleted":
            projected_payload["prior"] = _recorded_stat_policy(
                payload_map.get("prior"), contract_values.get("target_expected")
            )
        elif command == "noop":
            source_relative = contract_values.get("source_rel_path")
            source_path = (
                None
                if not isinstance(source_relative, str)
                else "$SOURCE/" + PureWindowsPath(source_relative).as_posix()
            )
            projected_payload["source"] = _recorded_stat_policy(
                payload_map.get("source"), tree_map.get(source_path)
            )
            projected_payload["target"] = _recorded_stat_policy(
                payload_map.get("target"), target
            )
        else:
            projected_payload["unsupported"] = payload_map
        projected.append(
            {
                "schema": sorted(str(key) for key in raw),
                "command": command,
                "payload": projected_payload,
                "result": raw.get("result"),
                "error": raw.get("error"),
                "message": raw.get("message"),
            }
        )
    return projected


def _policy_projection(report: Mapping[str, object]) -> dict[str, object]:
    xset = report.get("execution_set")
    xset_map = xset if isinstance(xset, Mapping) else {}
    tree = report.get("tree")
    tree_map = tree if isinstance(tree, Mapping) else {}
    contract_map: dict[str, Mapping[str, object] | None] = {}
    raw_contracts = report.get("operation_contracts")
    if isinstance(raw_contracts, list):
        for contract in raw_contracts:
            if not isinstance(contract, Mapping) or not isinstance(
                contract.get("op"), str
            ):
                continue
            op = str(contract["op"])
            contract_map[op] = None if op in contract_map else contract
    evidence: list[dict[str, object]] = []
    raw_evidence = xset_map.get("published_evidence", _MISSING)
    if isinstance(raw_evidence, list):
        for raw in raw_evidence:
            if not isinstance(raw, Mapping):
                evidence.append({"malformed": raw})
                continue
            path = raw.get("path")
            target = tree_map.get(f"$TARGET/{path}")
            evidence.append(
                {
                    "schema": sorted(str(key) for key in raw),
                    "op": raw.get("op"),
                    "kind": raw.get("kind"),
                    "path": path,
                    "recorded": raw.get("recorded"),
                    "content": raw.get("content"),
                    "subject": _attestation_subject_policy(
                        raw.get("subject"), target
                    ),
                    "recorded_identity": raw.get("recorded_identity"),
                }
            )
    elif raw_evidence is _MISSING:
        evidence = _MISSING
    else:
        evidence = {"$invalid": raw_evidence}

    policy_tree: dict[str, object] = {}
    for path, raw in tree_map.items():
        if not isinstance(path, str) or not isinstance(raw, Mapping):
            policy_tree[str(path)] = {"malformed": raw}
            continue
        if raw.get("kind") == "directory":
            policy_tree[path] = {
                "schema": sorted(str(key) for key in raw),
                "kind": "directory",
                "identity_present": raw.get("identity") is not None,
                "mtime_present": raw.get("mtime") is not None,
                "created_present": raw.get("created") is not None,
            }
        else:
            policy_tree[path] = {
                "schema": sorted(str(key) for key in raw),
                "kind": raw.get("kind"),
                "size": raw.get("size"),
                "text": raw.get("text"),
                "sha256": raw.get("sha256"),
                "readonly": raw.get("readonly"),
                "identity_present": raw.get("identity") is not None,
                "mtime_present": raw.get("mtime") is not None,
                "created_present": raw.get("created") is not None,
            }

    row = report.get("row")
    relations = (
        _TREE_METADATA_RELATIONS.get(row, {}) if isinstance(row, str) else {}
    )
    for path, node in policy_tree.items():
        if not isinstance(node, dict):
            continue
        relation = relations.get(path)
        if relation is None:
            node.update(
                {
                    "metadata_reference": None,
                    "reference_available": None,
                    "reference_schema": None,
                    "reference_kind": None,
                    "mtime_matches_reference": None,
                    "created_matches_reference": None,
                    "identity_matches_reference": None,
                }
            )
            continue
        contract = contract_map.get(relation.op)
        reference = (
            contract.get(relation.reference)
            if isinstance(contract, Mapping)
            else None
        )
        reference_map = reference if isinstance(reference, Mapping) else {}
        raw = tree_map.get(path)
        raw_map = raw if isinstance(raw, Mapping) else {}
        node.update(
            {
                "metadata_reference": f"{relation.op}:{relation.reference}",
                "reference_available": isinstance(reference, Mapping),
                "reference_schema": sorted(str(key) for key in reference_map),
                "reference_kind": reference_map.get("kind"),
                "mtime_matches_reference": raw_map.get("mtime")
                == reference_map.get("mtime"),
                "created_matches_reference": raw_map.get("created")
                == reference_map.get("created"),
                "identity_matches_reference": (
                    raw_map.get("identity") == reference_map.get("identity")
                    if "identity" in raw_map and "identity" in reference_map
                    else None
                ),
            }
        )

    projected_tree: object = dict(sorted(policy_tree.items()))
    if "tree" not in report:
        projected_tree = _MISSING

    projection = {
        "row": report.get("row"),
        "termination": report.get("termination"),
        "result": report["result"] if "result" in report else _MISSING,
        "execution_set": {
            "schema": sorted(str(key) for key in xset_map),
            "selected": xset_map.get("selected"),
            "selection": xset_map.get("selection"),
            "recording": xset_map.get("recording"),
            "status": xset_map.get("status"),
            "published_evidence": evidence,
        },
        "items": report.get("items"),
        "reliable_events": report.get("reliable_events"),
        "recorder_calls": _recorder_policy_projection(
            report, tree_map, contract_map
        ),
        "tree": projected_tree,
    }
    invocations = report.get("invocations")
    if invocations is not None:
        projection["invocations"] = invocations
    return projection


def _tree_snapshot(
    source: Path,
    target: Path,
    normalizer: TracingFileSystem,
    *,
    row: str,
) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for root, label in ((source, "$SOURCE"), (target, "$TARGET")):
        for current, directory_names, file_names in os.walk(root):
            directory_names.sort(key=str.casefold)
            file_names.sort(key=str.casefold)
            current_path = Path(current)
            for name in directory_names:
                path = current_path / name
                relative = path.relative_to(root).as_posix()
                info = path.stat(follow_symlinks=False)
                snapshot[f"{label}/{relative}"] = {
                    "kind": "directory",
                    "identity": normalizer.snapshot_identity(path),
                    "mtime": normalizer.timestamp("mtime", info.st_mtime_ns),
                    "created": normalizer.timestamp("created", _created_ns(info)),
                }
            for name in file_names:
                path = current_path / name
                relative = path.relative_to(root).as_posix()
                content = path.read_bytes()
                try:
                    text = content.decode("utf-8")
                except UnicodeDecodeError:
                    text = None
                info = path.stat(follow_symlinks=False)
                attributes = info.st_file_attributes
                snapshot[f"{label}/{relative}"] = {
                    "kind": "file",
                    "size": len(content),
                    "text": text,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "identity": normalizer.snapshot_identity(path),
                    "mtime": normalizer.timestamp("mtime", info.st_mtime_ns),
                    "created": normalizer.timestamp("created", _created_ns(info)),
                    "readonly": bool(
                        attributes & stat_module.FILE_ATTRIBUTE_READONLY
                    ),
                }
    return _normalize_clock_incidental_tree_timestamps(
        row,
        dict(sorted(snapshot.items())),
    )


def _normalize_clock_incidental_tree_timestamps(
    row: str,
    snapshot: Mapping[str, object],
) -> dict[str, object]:
    normalized = dict(snapshot)
    for path, fields_to_exclude in _CLOCK_INCIDENTAL_TREE_TIMESTAMPS.get(
        row, {}
    ).items():
        node = normalized.get(path)
        if not isinstance(node, Mapping):
            raise AuditError(
                f"clock-incidental timestamp declaration names absent tree path: "
                f"{row} {path}"
            )
        replacement = dict(node)
        for field in fields_to_exclude:
            if field not in replacement:
                raise AuditError(
                    "clock-incidental timestamp declaration names absent field: "
                    f"{row} {path} {field}"
                )
            replacement[field] = f"$clock-incidental:{field}"
        normalized[path] = replacement
    return normalized


def _created_ns(info: os.stat_result) -> int | None:
    value = getattr(info, "st_birthtime_ns", None)
    if value is None and os.name == "nt":
        value = getattr(info, "st_ctime_ns", None)
    return None if value is None else int(value)


def _global_invariant_errors(report: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    xset = report.get("execution_set")
    if not isinstance(xset, Mapping):
        return ["global invariant: execution_set is unavailable"]
    statuses = xset.get("status")
    selection = xset.get("selection")
    items = report.get("items")
    evidence = xset.get("published_evidence")
    if (
        not isinstance(selection, list)
        or not isinstance(statuses, list)
        or not isinstance(items, list)
        or not isinstance(evidence, list)
    ):
        return ["global invariant: selection, statuses, items, or evidence unavailable"]
    selected = xset.get("selected")
    if selected != len(selection):
        errors.append(
            f"global invariant: selection count {len(selection)} differs from {selected}"
        )
    selected_by_op: dict[object, object] = {}
    for entry in selection:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("op"), str):
            errors.append("global invariant: malformed selected operation")
            continue
        op = entry.get("op")
        if op in selected_by_op:
            errors.append(f"global invariant: duplicate selected operation: {op}")
        selected_by_op[op] = entry.get("kind")
    termination = report.get("termination")
    partial_exception_exit = (
        isinstance(termination, Mapping)
        and termination.get("raised") not in {None, "Canceled"}
    )
    if not partial_exception_exit and len(statuses) != selected:
        errors.append(
            f"global invariant: {len(statuses)} terminal statuses for {selected} selections"
        )
    if len(items) != len(statuses):
        errors.append("global invariant: item/status cardinality differs")
    status_by_op: dict[object, Mapping[str, object]] = {}
    for entry in statuses:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("op"), str):
            errors.append("global invariant: malformed terminal status")
            continue
        op = entry.get("op")
        if op in status_by_op:
            errors.append(f"global invariant: duplicate terminal status: {op}")
        status_by_op[op] = entry
        if op not in selected_by_op:
            errors.append(f"global invariant: status for unselected operation: {op}")
        elif selected_by_op[op] != entry.get("kind"):
            errors.append(f"global invariant: selection/status kind disagreement for {op}")

    evidence_counts: dict[object, int] = {}
    for entry in evidence:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("op"), str):
            errors.append("global invariant: malformed operation evidence")
            continue
        op = entry.get("op")
        evidence_counts[op] = evidence_counts.get(op, 0) + 1
        if op not in selected_by_op:
            errors.append(f"global invariant: evidence for unselected operation: {op}")
        if op not in status_by_op:
            errors.append(f"global invariant: evidence without terminal status: {op}")
    for op, count in evidence_counts.items():
        if count > 1:
            errors.append(f"global invariant: duplicate operation evidence: {op}")

    for item in items:
        if not isinstance(item, Mapping):
            errors.append("global invariant: malformed item")
            continue
        op = item.get("op")
        status = status_by_op.get(op)
        if status is None or status.get("outcome") != item.get("outcome"):
            errors.append(f"global invariant: item/status disagreement for {op}")
        if status is not None and status.get("kind") != item.get("kind"):
            errors.append(f"global invariant: item/status kind disagreement for {op}")

    byte_kinds = {member.value for member in _BYTE_KINDS}
    for op in selected_by_op:
        status = status_by_op.get(op)
        should_have_evidence = bool(
            status is not None
            and status.get("outcome") == Outcome.SUCCEEDED.value
            and status.get("kind") in byte_kinds
        )
        count = evidence_counts.get(op, 0)
        if should_have_evidence and count == 0:
            errors.append(f"global invariant: successful byte operation lacks evidence: {op}")
        elif not should_have_evidence and count:
            errors.append(
                "global invariant: operation has evidence without a successful "
                f"byte outcome: {op}"
            )
    reliable = report.get("reliable_events")
    reliable_items = [
        entry.get("op")
        for entry in reliable if isinstance(entry, Mapping) and entry.get("type") == "item"
    ] if isinstance(reliable, list) else []
    item_ids = [item.get("op") for item in items if isinstance(item, Mapping)]
    if reliable_items != item_ids:
        errors.append("global invariant: reliable item event order differs from result items")
    return errors


def _clear_readonly_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        try:
            os.chmod(path, stat_module.S_IWRITE | stat_module.S_IREAD)
        except OSError:
            pass


def _run_in_sandbox(runner: Callable[[Path], list[dict[str, object]]]) -> list[dict[str, object]]:
    temporary = tempfile.TemporaryDirectory(prefix="namisync-settlement-")
    base = Path(temporary.name)
    try:
        return runner(base)
    finally:
        _clear_readonly_tree(base)
        temporary.cleanup()


def _roots(base: Path, name: str = "case") -> tuple[Path, Path, NativeFileSystem]:
    source = base / name / "source"
    target = base / name / "target"
    source.mkdir(parents=True)
    target.mkdir(parents=True)
    return source, target, NativeFileSystem()


def _copy_operation(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
    *,
    number: int = 1,
    relative: str = "copy.bin",
    content: bytes = b"copy-payload",
) -> PlanOperation:
    _write(source, relative, content)
    observed = _stat(fs, source, relative)
    return _operation(
        number,
        OperationKind.COPY,
        source_rel_path=relative,
        target_rel_path=relative,
        source_expected=observed,
        target_expected=None,
        intended=observed,
    )


def _update_operation(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
    *,
    number: int = 1,
    relative: str = "update.bin",
    source_content: bytes = b"new-version",
    target_content: bytes = b"old-version",
    readonly: bool = False,
) -> PlanOperation:
    source_path = _write(source, relative, source_content)
    target_path = _write(target, relative, target_content)
    if readonly:
        before = _stat(fs, target, relative)
        fs.apply_metadata(
            target_path,
            replace(
                before,
                metadata=replace(
                    before.metadata,
                    attributes=(
                        before.metadata.attributes
                        | stat_module.FILE_ATTRIBUTE_READONLY
                    ),
                ),
            ),
            preserve_created=True,
            apply_readonly=True,
        )
    source_stat = _stat(fs, source, relative)
    target_stat = _stat(fs, target, relative)
    return _operation(
        number,
        OperationKind.UPDATE,
        source_rel_path=relative,
        target_rel_path=relative,
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )


def _move_operation(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
    *,
    number: int = 1,
    old: str = "old.bin",
    new: str = "new.bin",
) -> PlanOperation:
    old_path = _write(target, old, b"move-payload")
    old_stat = _stat(fs, target, old)
    source_path = _write(source, new, b"move-payload")
    _sync_mtime(source_path, old_stat)
    source_stat = _stat(fs, source, new)
    return _operation(
        number,
        OperationKind.MOVE,
        source_rel_path=new,
        target_rel_path=new,
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path=old,
        prior_target_expected=old_stat,
        reason=OperationReason.IDENTITY_RENAME,
    )


def _recase_operation(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
    *,
    number: int = 1,
) -> PlanOperation:
    _write(source, "KEEP.txt", b"same")
    _write(target, "keep.txt", b"same")
    source_stat = _stat(fs, source, "KEEP.txt")
    target_stat = _stat(fs, target, "keep.txt")
    return _operation(
        number,
        OperationKind.RECASE,
        source_rel_path="KEEP.txt",
        target_rel_path="KEEP.txt",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=target_stat,
        prior_target_rel_path="keep.txt",
        prior_target_expected=target_stat,
        reason=OperationReason.CASE_MISMATCH,
    )


def _move_update_operation(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
    *,
    number: int = 1,
) -> PlanOperation:
    _write(source, "renamed.bin", b"changed-version")
    _write(target, "old.bin", b"old-version")
    source_stat = _stat(fs, source, "renamed.bin")
    old_stat = _stat(fs, target, "old.bin")
    return _operation(
        number,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
        reason=OperationReason.IDENTITY_RENAME_CHANGED,
    )


def _trash_operation(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
    *,
    number: int = 1,
    relative: str = "trash.bin",
) -> PlanOperation:
    del source
    _write(target, relative, b"trash-payload")
    target_stat = _stat(fs, target, relative)
    return _operation(
        number,
        OperationKind.TRASH,
        source_rel_path=None,
        target_rel_path=relative,
        source_expected=None,
        target_expected=target_stat,
        intended=None,
        reason=OperationReason.TARGET_ONLY,
    )


def _delete_operation(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
    *,
    number: int = 1,
    relative: str = "delete.bin",
    directory: bool = False,
) -> PlanOperation:
    del source
    if directory:
        _mkdir(target, relative)
    else:
        _write(target, relative, b"delete-payload")
    target_stat = _stat(fs, target, relative)
    return _operation(
        number,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path=relative,
        source_expected=None,
        target_expected=target_stat,
        intended=None,
        reason=(
            OperationReason.DIRECTORY_CLEANUP
            if directory
            else OperationReason.TARGET_ONLY
        ),
    )


def _mkdir_operation(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
    *,
    number: int = 1,
    relative: str = "folder",
) -> PlanOperation:
    del target
    _mkdir(source, relative)
    source_stat = _stat(fs, source, relative)
    return _operation(
        number,
        OperationKind.MKDIR,
        source_rel_path=relative,
        target_rel_path=relative,
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        reason=OperationReason.REQUIRED_DIRECTORY,
    )


def _noop_operation(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
    *,
    number: int = 1,
    relative: str = "noop.bin",
) -> PlanOperation:
    _write(source, relative, b"same")
    _write(target, relative, b"same")
    source_stat = _stat(fs, source, relative)
    target_stat = _stat(fs, target, relative)
    return _operation(
        number,
        OperationKind.NOOP,
        source_rel_path=relative,
        target_rel_path=relative,
        source_expected=source_stat,
        target_expected=target_stat,
        intended=target_stat,
        reason=OperationReason.METADATA_MATCH,
    )


def _success_all_nine(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    copy = _copy_operation(source, target, fs, number=1)
    update = _update_operation(source, target, fs, number=2)
    move = _move_operation(
        source, target, fs, number=3, old="move-old.bin", new="move-new.bin"
    )
    move_update = _move_update_operation(source, target, fs, number=4)
    recase = _recase_operation(source, target, fs, number=5)
    mkdir = _mkdir_operation(source, target, fs, number=6)
    trash = _trash_operation(source, target, fs, number=7)
    delete = _delete_operation(source, target, fs, number=8)
    noop = _noop_operation(source, target, fs, number=9)
    return [
        _run_fixture(
            source,
            target,
            (copy, update, move, move_update, recase, mkdir, trash, delete, noop),
            row="success.all-nine",
        )
    ]


def _failure_copy_prepublish(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _copy_operation(source, target, fs)
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="failure.copy-prepublish-cleanup-ok",
            backend=SynchronousCopyBackend(fail_before_read=True),
        )
    ]


def _failure_move_precommit(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _move_operation(source, target, fs)
    rules = (
        FaultRule(
            "rename_new",
            "before",
            _raise(lambda: _io_error("injected move failure before commit")),
        ),
    )
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="failure.move-precommit-unchanged",
            rules=rules,
        )
    ]


def _failure_byte_published(base: Path) -> list[dict[str, object]]:
    reports: list[dict[str, object]] = []
    for index, kind in enumerate(
        (OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE),
        start=1,
    ):
        source, target, fs = _roots(base, f"variant-{index}")
        if kind is OperationKind.COPY:
            operation = _copy_operation(source, target, fs)
            method = "publish_new"
        elif kind is OperationKind.UPDATE:
            operation = _update_operation(source, target, fs)
            method = "replace"
        else:
            operation = _move_update_operation(source, target, fs)
            method = "publish_new"
        rules = (
            FaultRule(
                method,
                "after",
                _raise(lambda: _io_error("injected failure after byte publication")),
            ),
        )
        reports.append(
            _run_fixture(
                source,
                target,
                (operation,),
                row=f"failure.byte-published.{kind.value.replace('_', '-')}",
                rules=rules,
            )
        )

    for target_state in ("changed", "missing", "unreadable"):
        source, target, fs = _roots(base, f"target-{target_state}")
        operation = _copy_operation(source, target, fs)
        live = target / "copy.bin"
        state = {"armed": False}

        def fail_durability(
            _args,
            _kwargs,
            _result,
            *,
            target_state: str = target_state,
            live: Path = live,
            state: dict[str, bool] = state,
        ) -> None:
            state["armed"] = True
            if target_state == "changed":
                live.write_bytes(b"foreign-published")
            elif target_state == "missing":
                live.unlink()
            raise _io_error("injected durability failure after byte publication")

        rules = (FaultRule("flush_directory", "before", fail_durability),)
        if target_state == "unreadable":
            rules += (
                FaultRule(
                    "stat_path",
                    "before",
                    _raise(lambda: PermissionError("published target probe unavailable")),
                    predicate=lambda args, _kwargs, _result, live=live, state=state: (
                        state["armed"] and bool(args) and Path(args[0]) == live
                    ),
                ),
            )
        reports.append(
            _run_fixture(
                source,
                target,
                (operation,),
                row=f"failure.byte-published.target-{target_state}",
                rules=rules,
            )
        )
    return reports


def _failure_nonbyte_commit(base: Path) -> list[dict[str, object]]:
    reports: list[dict[str, object]] = []
    kinds = (
        OperationKind.MOVE,
        OperationKind.RECASE,
        OperationKind.TRASH,
        OperationKind.DELETE,
        OperationKind.MKDIR,
    )
    for index, kind in enumerate(kinds, start=1):
        source, target, fs = _roots(base, f"variant-{index}")
        if kind is OperationKind.MOVE:
            operation = _move_operation(source, target, fs)
            method, phase = "rename_new", "after"
        elif kind is OperationKind.RECASE:
            operation = _recase_operation(source, target, fs)
            method, phase = "rename_new", "after"
        elif kind is OperationKind.TRASH:
            operation = _trash_operation(source, target, fs)
            method, phase = "rename_new", "after"
        elif kind is OperationKind.DELETE:
            operation = _delete_operation(source, target, fs)
            method, phase = "remove_file", "after"
        else:
            operation = _mkdir_operation(source, target, fs)
            method, phase = "apply_metadata", "before"
        rules = (
            FaultRule(
                method,
                phase,
                _raise(lambda: _io_error("injected failure after mutation")),
            ),
        )
        reports.append(
            _run_fixture(
                source,
                target,
                (operation,),
                row=f"failure.nonbyte-commit.{kind.value}",
                rules=rules,
            )
        )

    for kind in (OperationKind.MOVE, OperationKind.TRASH):
        source, target, fs = _roots(base, f"{kind.value}-restored")
        if kind is OperationKind.MOVE:
            operation = _move_operation(source, target, fs)
            original = target / "old.bin"
            destination = target / "new.bin"
        else:
            operation = _trash_operation(source, target, fs)
            original = target / "trash.bin"
            destination = target / ".synctrash" / str(RUN_ID) / "trash.bin"

        def restore_rename(
            _args,
            _kwargs,
            _result,
            *,
            original: Path = original,
            destination: Path = destination,
        ) -> None:
            destination.rename(original)
            raise _io_error("injected failure after restored mutation")

        reports.append(
            _run_fixture(
                source,
                target,
                (operation,),
                row=f"failure.nonbyte-commit.{kind.value}-restored",
                rules=(FaultRule("flush_directory", "before", restore_rename),),
            )
        )

    source, target, fs = _roots(base, "delete-restored")
    operation = _delete_operation(source, target, fs)
    live = target / "delete.bin"
    retained_link = base / "delete-restored-link.bin"
    os.link(live, retained_link)
    operation = replace(
        operation,
        target_expected=_stat(fs, target, "delete.bin"),
    )

    def restore_delete(_args, _kwargs, _result) -> None:
        os.link(retained_link, live)
        raise _io_error("injected failure after restored mutation")

    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="failure.nonbyte-commit.delete-restored",
            rules=(FaultRule("flush_directory", "before", restore_delete),),
        )
    )

    source, target, fs = _roots(base, "delete-unreadable")
    operation = _delete_operation(source, target, fs)
    live = target / "delete.bin"
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="failure.nonbyte-unreadable.delete-precommit",
            rules=(
                FaultRule(
                    "remove_file",
                    "before",
                    _raise(lambda: _io_error("injected delete failure before commit")),
                ),
                FaultRule(
                    "stat_path",
                    "before",
                    _raise(lambda: PermissionError("delete state probe unavailable")),
                    predicate=_path_argument_is(live),
                ),
            ),
        )
    )
    return reports


def _readonly_composition_fixture(
    base: Path,
    *,
    cancel: bool,
    row: str,
) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _update_operation(source, target, fs, readonly=True)
    live = target / "update.bin"
    state = {"probe_armed": False}

    def fail_restore(_args, _kwargs, _result) -> None:
        state["probe_armed"] = True
        raise PermissionError("injected readonly restoration failure")

    def restoration(args, kwargs, _result) -> bool:
        return (
            bool(args)
            and Path(args[0]) == live
            and bool(kwargs.get("apply_readonly"))
        )

    def armed_target_probe(args, _kwargs, _result) -> bool:
        return (
            state["probe_armed"]
            and bool(args)
            and Path(args[0]) == live
        )

    rules = (
        FaultRule(
            "replace",
            "before",
            _raise(
                lambda: (
                    _sharing_error("injected update replace sharing failure")
                    if cancel
                    else PermissionError("injected update replace failure")
                )
            ),
        ),
        FaultRule(
            "apply_metadata",
            "before",
            fail_restore,
            predicate=restoration,
        ),
        FaultRule(
            "stat_path",
            "before",
            _raise(lambda: PermissionError("publication-state probe unavailable")),
            predicate=armed_target_probe,
        ),
    )
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row=row,
            rules=rules,
            retries=1 if cancel else 0,
            cancel_on_sleep=cancel,
            trash_on_update=False,
        )
    ]


def _failure_move_update_trash(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _move_update_operation(source, target, fs)
    rules = (
        FaultRule(
            "rename_new",
            "after",
            _raise(lambda: _io_error("injected failure after move-update trash")),
        ),
    )
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="failure.move-update-new-and-trash",
            rules=rules,
        )
    ]


def _failure_noop_drift(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _noop_operation(source, target, fs)
    (target / "noop.bin").write_bytes(b"drift")
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="failure.noop-drift",
        )
    ]


def _retry_copy_prepared(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _copy_operation(source, target, fs)
    rules = (
        FaultRule(
            "publish_new",
            "before",
            _raise(lambda: _sharing_error("injected prepublish sharing failure")),
        ),
    )
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="retry.copy-prepared",
            rules=rules,
            retries=1,
        )
    ]


def _retry_copy_published(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _copy_operation(source, target, fs)
    rules = (
        FaultRule(
            "publish_new",
            "after",
            _raise(lambda: _sharing_error("injected postpublish sharing failure")),
        ),
    )
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="retry.copy-published",
            rules=rules,
            retries=1,
        )
    ]


def _retry_update_after_backup(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _update_operation(source, target, fs)
    rules = (
        FaultRule(
            "replace",
            "before",
            _raise(lambda: _sharing_error("injected update replace retry")),
        ),
    )
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="retry.update-after-backup",
            rules=rules,
            retries=1,
        )
    ]


def _retry_move_update_after_publish(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _move_update_operation(source, target, fs)
    rules = (
        FaultRule(
            "rename_new",
            "before",
            _raise(lambda: _sharing_error("injected move-update trash retry")),
        ),
    )
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="retry.move-update-after-publish",
            rules=rules,
            retries=1,
        )
    ]


def _retry_committed_move(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _move_operation(source, target, fs)
    rules = (
        FaultRule(
            "rename_new",
            "after",
            _raise(lambda: _sharing_error("injected committed move retry")),
        ),
    )
    reports = [
        _run_fixture(
            source,
            target,
            (operation,),
            row="retry.committed-move-settles-once",
            rules=rules,
            retries=1,
        )
    ]

    source, target, fs = _roots(base, "failure-policy-escape")
    operation = _move_operation(source, target, fs)
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="retry.committed-move-failure-policy-escape",
            rules=(
                FaultRule(
                    "rename_new",
                    "after",
                    _raise(lambda: _io_error("injected committed move failure")),
                ),
            ),
            failure_policy_escape=True,
        )
    )

    source, target, fs = _roots(base, "retry-sleep-escape")
    operation = _move_operation(source, target, fs)
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="retry.committed-move-sleep-escape",
            rules=(
                FaultRule(
                    "rename_new",
                    "after",
                    _raise(lambda: _sharing_error("injected committed move retry")),
                ),
            ),
            retries=1,
            retry_sleep_escape=True,
        )
    )
    return reports


def _cancel_before_effect(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    first = _copy_operation(source, target, fs, number=1, relative="first.bin")
    second = _delete_operation(
        source, target, fs, number=2, relative="second.bin"
    )
    return [
        _run_fixture(
            source,
            target,
            (first, second),
            row="cancel.before-effect-sweep",
            cancel_at=1,
        )
    ]


def _cancel_copy_prepared(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _copy_operation(source, target, fs)
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="cancel.copy-prepared",
            cancel_at=2,
        )
    ]


def _cancel_copy_published(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _copy_operation(source, target, fs)
    rules = (
        FaultRule(
            "publish_new",
            "after",
            _raise(Canceled),
        ),
    )
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="cancel.copy-published",
            rules=rules,
        )
    ]


def _cancel_committed_move(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _move_operation(source, target, fs)
    rules = (FaultRule("rename_new", "after", _raise(Canceled)),)
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="cancel.committed-move",
            rules=rules,
        )
    ]


def _cancel_update_composed(base: Path) -> list[dict[str, object]]:
    return _readonly_composition_fixture(
        base,
        cancel=True,
        row="cancel.update-composed-unverified-plus-readonly",
    )


def _cancel_move_update_partial(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _move_update_operation(source, target, fs)
    rules = (FaultRule("publish_new", "after", _raise(Canceled)),)
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="cancel.move-update-partial-publish",
            rules=rules,
        )
    ]


def _cleanup_ordinary_failure(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _copy_operation(source, target, fs)
    rules = (
        FaultRule(
            "remove_owned_temp",
            "before",
            _raise(lambda: PermissionError("injected temp cleanup failure")),
            predicate=lambda args, _kwargs, _result: bool(args)
            and Path(args[0]).exists(),
        ),
    )
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="cleanup.ordinary.no-durable-cleanup-failure",
            rules=rules,
            backend=SynchronousCopyBackend(fail_before_read=True),
        )
    ]


def _cleanup_canceled_failure(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _copy_operation(source, target, fs)
    rules = (
        FaultRule(
            "remove_owned_temp",
            "before",
            _raise(lambda: PermissionError("injected canceled cleanup failure")),
            predicate=lambda args, _kwargs, _result: bool(args)
            and Path(args[0]).exists(),
        ),
    )
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="cleanup.canceled-failure",
            rules=rules,
            cancel_at=2,
        )
    ]


def _record_copy_failure(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _copy_operation(source, target, fs)
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="record.copy-failure",
            recorder_fail=frozenset({"copied"}),
        )
    ]


def _record_nonbyte_failure(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _move_operation(source, target, fs)
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="record.nonbyte-failure",
            recorder_fail=frozenset({"moved"}),
        )
    ]


def _update_backup_state_matrix(base: Path) -> list[dict[str, object]]:
    reports: list[dict[str, object]] = []
    for terminal in ("failure", "cancel"):
        for backup_state in ("retained", "changed", "absent", "unverified"):
            source, target, fs = _roots(base, f"{terminal}-{backup_state}")
            operation = _update_operation(source, target, fs)
            backup = target / ".synctrash" / str(RUN_ID) / "update.bin"
            state = {"probe_unavailable": False}

            def fail_replace(
                _args,
                _kwargs,
                _result,
                *,
                backup_state: str = backup_state,
                backup: Path = backup,
                state: dict[str, bool] = state,
                terminal: str = terminal,
            ) -> None:
                if backup_state == "changed":
                    backup.write_bytes(b"foreign-backup")
                elif backup_state == "absent":
                    backup.unlink()
                elif backup_state == "unverified":
                    state["probe_unavailable"] = True
                if terminal == "cancel":
                    raise _sharing_error("injected update replace sharing failure")
                raise PermissionError("injected update replace failure")

            def unavailable_backup_probe(
                args,
                _kwargs,
                _result,
                *,
                backup: Path = backup,
                state: dict[str, bool] = state,
            ) -> bool:
                return (
                    state["probe_unavailable"]
                    and bool(args)
                    and Path(args[0]) == backup
                )

            rules = (FaultRule("replace", "before", fail_replace),)
            if backup_state == "unverified":
                rules += (
                    FaultRule(
                        "stat_path",
                        "before",
                        _raise(lambda: PermissionError("backup probe unavailable")),
                        predicate=unavailable_backup_probe,
                    ),
                )
            reports.append(
                _run_fixture(
                    source,
                    target,
                    (operation,),
                    row=f"update.backup-state.{terminal}.{backup_state}",
                    rules=rules,
                    retries=1 if terminal == "cancel" else 0,
                    cancel_on_sleep=terminal == "cancel",
                    hardlinks=False,
                )
            )
    return reports


def _update_sibling_matrix(base: Path) -> list[dict[str, object]]:
    reports = _readonly_composition_fixture(
        base / "unverified",
        cancel=False,
        row="failure.update-sibling.publication-unverified-plus-readonly",
    )

    source, target, fs = _roots(base, "confirmed")
    operation = _update_operation(source, target, fs, readonly=True)
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="failure.update-sibling.confirmed-publication-suppresses-readonly",
            rules=(
                FaultRule(
                    "replace",
                    "after",
                    _raise(lambda: PermissionError("post-publication failure")),
                ),
            ),
            trash_on_update=False,
        )
    )

    source, target, fs = _roots(base, "unchanged")
    operation = _update_operation(source, target, fs, readonly=True)
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="failure.update-sibling.unchanged-readonly",
            rules=(
                FaultRule(
                    "replace",
                    "before",
                    _raise(lambda: PermissionError("pre-publication failure")),
                ),
            ),
            trash_on_update=False,
        )
    )

    source, target, fs = _roots(base, "unreadable-mutation")
    operation = _update_operation(source, target, fs, readonly=True)
    live = target / "update.bin"
    state = {"armed": False, "target_probes": 0}

    def fail_restore(_args, _kwargs, _result) -> None:
        state["armed"] = True
        raise PermissionError("injected readonly restoration failure")

    def restoration(args, kwargs, _result) -> bool:
        return (
            bool(args)
            and Path(args[0]) == live
            and bool(kwargs.get("apply_readonly"))
        )

    def second_settlement_probe(args, _kwargs, _result) -> bool:
        if not state["armed"] or not args or Path(args[0]) != live:
            return False
        state["target_probes"] += 1
        return state["target_probes"] == 2

    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="failure.update-sibling.unreadable-readonly-mutation",
            rules=(
                FaultRule(
                    "replace",
                    "before",
                    _raise(lambda: PermissionError("injected update replace failure")),
                ),
                FaultRule(
                    "apply_metadata",
                    "before",
                    fail_restore,
                    predicate=restoration,
                ),
                FaultRule(
                    "stat_path",
                    "before",
                    _raise(lambda: PermissionError("update state probe unavailable")),
                    predicate=second_settlement_probe,
                ),
            ),
            trash_on_update=False,
        )
    )
    return reports


def _cleanup_ordinary_matrix(base: Path) -> list[dict[str, object]]:
    reports = _cleanup_ordinary_failure(base / "failure-no-durable")

    source, target, fs = _roots(base, "one-shot-precleanup")
    operation = _copy_operation(source, target, fs)
    _write(
        target,
        f"copy.bin.synctmp-{RUN_ID}-{operation.op_id}",
        b"stale-owned-temp",
    )
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="cleanup.ordinary.stale-owned-temp-recovered",
        )
    )

    source, target, fs = _roots(base, "pre-retry-cleanup")
    operation = _copy_operation(source, target, fs)
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="cleanup.ordinary.pre-retry-cleanup-succeeds",
            rules=(
                FaultRule(
                    "finalize_temp",
                    "before",
                    _raise(lambda: _sharing_error("retry after prepared temp")),
                ),
            ),
            retries=1,
        )
    )

    source, target, fs = _roots(base, "pre-retry-cleanup-failure")
    operation = _copy_operation(source, target, fs)
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="cleanup.ordinary.pre-retry-cleanup-fails",
            rules=(
                FaultRule(
                    "remove_owned_temp",
                    "before",
                    _raise(lambda: PermissionError("injected retry cleanup failure")),
                    predicate=lambda args, _kwargs, _result: bool(args)
                    and Path(args[0]).exists(),
                ),
            ),
            backend=SynchronousCopyBackend(fail_midcopy_sharing_once=True),
            retries=1,
        )
    )

    source, target, fs = _roots(base, "failure-with-durable")
    operation = _update_operation(source, target, fs)
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="cleanup.ordinary.durable-verdict-plus-cleanup-failure",
            rules=(
                FaultRule(
                    "replace",
                    "before",
                    _raise(lambda: PermissionError("update publish failure")),
                ),
                FaultRule(
                    "remove_owned_temp",
                    "before",
                    _raise(lambda: PermissionError("durable cleanup failure")),
                    predicate=lambda args, _kwargs, _result: bool(args)
                    and Path(args[0]).exists(),
                ),
            ),
        )
    )
    return reports


def _pause_copy_prepared(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    operation = _copy_operation(source, target, fs)
    return [
        _run_fixture(
            source,
            target,
            (operation,),
            row="pause.copy-prepared",
            pause_at=2,
        )
    ]


def _retry_control_matrix(base: Path) -> list[dict[str, object]]:
    reports: list[dict[str, object]] = []
    for mode in ("pause", "pause-then-cancel"):
        source, target, fs = _roots(base, mode)
        operation = _update_operation(source, target, fs)
        failure_count = 1 if mode == "pause" else 2
        reports.append(
            _run_fixture(
                source,
                target,
                (operation,),
                rules=(
                    FaultRule(
                        "replace",
                        "before",
                        _raise(lambda: _sharing_error("retry control failure")),
                        remaining=failure_count,
                    ),
                ),
                row=f"retry.control.{mode}",
                retries=1 if mode == "pause" else 2,
                retry_control=mode,
            )
        )
    return reports


def _resume_same_execution_set(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    first = _copy_operation(
        source,
        target,
        fs,
        number=1,
        relative="first.bin",
        content=b"first-payload",
    )
    update = _update_operation(source, target, fs, number=2)
    third = _copy_operation(
        source,
        target,
        fs,
        number=3,
        relative="third.bin",
        content=b"third-payload",
    )
    operations = (first, update, third)
    plan = _plan(source, target, operations)
    xset = ExecutionSet(plan, frozenset(op.op_id for op in operations), RUN_ID)
    timeline: list[str] = []
    filesystem = TracingFileSystem(
        source,
        target,
        (
            FaultRule(
                "replace",
                "before",
                _raise(lambda: _sharing_error("resume retry publication failure")),
            ),
        ),
        timeline,
    )
    copy_backend = SynchronousCopyBackend()
    copy_backend.bind_timeline(timeline)
    recorder = TraceRecorder(
        plan,
        timeline=timeline,
        normalize=filesystem.value,
    )
    failure = TrackingFailurePolicy(retries=1, timeline=timeline)
    control = TrackingControl(retry_control="pause", timeline=timeline)
    pacing = TrackingPacing(control=control, timeline=timeline)
    events: list[object] = []

    def emit(event: object) -> None:
        if isinstance(event, PhaseChanged):
            timeline.append(f"emit:phase:{event.phase}")
        elif isinstance(event, ItemOutcome):
            timeline.append(
                f"emit:item:{event.item_id}:{event.kind}:{event.outcome.value}"
            )
        events.append(event)

    policies = ExecutorPolicies(
        copy_backend=copy_backend,
        failure=failure,
        clock=FixedClock(),
        max_chunk_size=4,
        max_retries=1,
        progress_interval_seconds=10_000,
        monotonic=pacing.monotonic,
        sleep=pacing.sleep,
    )
    invocations: list[dict[str, object]] = []

    def invoke() -> tuple[OperationResult | None, BaseException | None]:
        event_start = len(events)
        result: OperationResult | None = None
        raised: BaseException | None = None
        try:
            result = execute(
                xset,
                RunContext(emit, control.checkpoint),
                recorder,
                policies,
                filesystem,  # type: ignore[arg-type]
            )
        except (Canceled, PauseRequested) as error:
            raised = error
        except BaseException as error:
            raised = error
        invocation_events = events[event_start:]
        items, reliable, progress = _event_projection(
            invocation_events, filesystem
        )
        snapshot = {
            "row": "resume.pause-same-execution-set",
            "termination": {
                "returned": None if result is None else result.status.value,
                "raised": None if raised is None else type(raised).__name__,
            },
            "result": (
                None if result is None else _operation_result(result, filesystem)
            ),
            "execution_set": _execution_set_projection(
                xset, operations, filesystem
            ),
            "operation_contracts": _operation_contract_projection(
                operations, filesystem
            ),
            "items": items,
            "reliable_events": reliable,
            "progress_final": progress,
            "recorder": {"trace": recorder.trace},
            "tree": _tree_snapshot(
                source,
                target,
                filesystem,
                row="resume.pause-same-execution-set",
            ),
        }
        invocation = _policy_projection(snapshot)
        invocation["recorder_commands"] = [
            entry["command"]
            for entry in recorder.trace
            if entry["command"] != "flush"
        ]
        invocation["recorder_flushes"] = sum(
            entry["command"] == "flush" for entry in recorder.trace
        )
        invocation["backend_calls"] = copy_backend.calls
        invocations.append(invocation)
        return result, raised

    first_result, first_raised = invoke()
    if first_result is not None or not isinstance(first_raised, PauseRequested):
        raise AuditError("resume fixture did not pause after settling its retry")
    control.retry_control = None
    control.backoff_started = False
    second_result, second_raised = invoke()
    if (
        second_result is None
        or second_result.status is not SessionState.COMPLETED
        or second_raised is not None
    ):
        raise AuditError("resume fixture did not complete its remaining operation")
    result, raised = invoke()
    if (
        result is None
        or result.status is not SessionState.COMPLETED
        or raised is not None
    ):
        raise AuditError("terminal execution-set reinvocation did not remain complete")
    filesystem.require_faults_consumed("resume.pause-same-execution-set")
    report = _build_report(
        row="resume.pause-same-execution-set",
        source=source,
        target=target,
        operations=operations,
        xset=xset,
        result=result,
        raised=raised,
        events=events,
        filesystem=filesystem,
        copy_backend=copy_backend,
        recorder=recorder,
        failure=failure,
        control=control,
        pacing=pacing,
        timeline=timeline,
    )
    report["invocations"] = invocations
    return [report]


def _failure_policy_stop(base: Path) -> list[dict[str, object]]:
    source, target, fs = _roots(base)
    failing = _copy_operation(
        source,
        target,
        fs,
        number=1,
        relative="failing.bin",
        content=b"failing-payload",
    )
    later = _copy_operation(
        source,
        target,
        fs,
        number=2,
        relative="later.bin",
        content=b"later-payload",
    )
    dependent = _copy_operation(
        source,
        target,
        fs,
        number=3,
        relative="dependent.bin",
        content=b"dependent-payload",
    )
    dependent = replace(dependent, dependencies=(failing.op_id, later.op_id))
    return [
        _run_fixture(
            source,
            target,
            (failing, later, dependent),
            row="failure.policy-stop-sweep",
            backend=SynchronousCopyBackend(fail_before_read=True),
            stop=True,
        )
    ]


def _mkdir_matrix(base: Path) -> list[dict[str, object]]:
    reports: list[dict[str, object]] = []
    for name, phase, row in (
        (
            "precommit",
            "before",
            "mkdir.primitive-precommit-unchanged",
        ),
        (
            "commit-raise",
            "after",
            "mkdir.primitive-commit-then-raise",
        ),
    ):
        source, target, fs = _roots(base, name)
        operation = _mkdir_operation(source, target, fs)
        reports.append(
            _run_fixture(
                source,
                target,
                (operation,),
                row=row,
                rules=(
                    FaultRule(
                        "mkdir_new",
                        phase,
                        _raise(lambda: PermissionError("mkdir injected failure")),
                    ),
                ),
            )
        )

    source, target, fs = _roots(base, "metadata-available")
    operation = _mkdir_operation(source, target, fs)
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="mkdir.metadata-failure.available-probe",
            rules=(
                FaultRule(
                    "apply_metadata",
                    "before",
                    _raise(lambda: PermissionError("mkdir metadata failure")),
                ),
            ),
        )
    )

    source, target, fs = _roots(base, "metadata-unavailable")
    operation = _mkdir_operation(source, target, fs)
    directory = target / "folder"
    state = {"armed": False}

    def fail_metadata(_args, _kwargs, _result) -> None:
        state["armed"] = True
        raise PermissionError("mkdir metadata failure")

    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="mkdir.metadata-failure.unavailable-probe",
            rules=(
                FaultRule("apply_metadata", "before", fail_metadata),
                FaultRule(
                    "stat_path",
                    "before",
                    _raise(lambda: PermissionError("mkdir probe unavailable")),
                    predicate=lambda args, _kwargs, _result: state["armed"]
                    and bool(args)
                    and Path(args[0]) == directory,
                ),
            ),
        )
    )

    source, target, fs = _roots(base, "metadata-disappeared")
    operation = _mkdir_operation(source, target, fs)
    directory = target / "folder"

    def remove_before_metadata(_args, _kwargs, _result) -> None:
        directory.rmdir()
        raise PermissionError("mkdir metadata target disappeared")

    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="mkdir.metadata-failure.disappeared-after-create",
            rules=(
                FaultRule("apply_metadata", "before", remove_before_metadata),
            ),
        )
    )

    for name, control_name in (("child-cancel", "cancel"), ("child-pause", "pause")):
        source, target, fs = _roots(base, name)
        mkdir = _mkdir_operation(source, target, fs, number=1)
        child = _copy_operation(
            source,
            target,
            fs,
            number=2,
            relative="folder\\child.bin",
            content=b"child",
        )
        refreshed = _stat(fs, source, "folder")
        mkdir = replace(
            mkdir,
            source_expected=refreshed,
            intended=refreshed,
        )
        child = replace(child, dependencies=(mkdir.op_id,))
        reports.append(
            _run_fixture(
                source,
                target,
                (mkdir, child),
                row=f"mkdir.pending-child-{control_name}",
                cancel_at=2 if control_name == "cancel" else None,
                pause_at=2 if control_name == "pause" else None,
            )
        )

    source, target, fs = _roots(base, "child-checkpoint-exception")
    mkdir = _mkdir_operation(source, target, fs, number=1)
    child = _copy_operation(
        source,
        target,
        fs,
        number=2,
        relative="folder\\child.bin",
        content=b"child",
    )
    refreshed = _stat(fs, source, "folder")
    mkdir = replace(mkdir, source_expected=refreshed, intended=refreshed)
    child = replace(child, dependencies=(mkdir.op_id,))
    reports.append(
        _run_fixture(
            source,
            target,
            (mkdir, child),
            row="mkdir.pending-child-checkpoint-exception",
            checkpoint_exception_at=2,
        )
    )

    source, target, fs = _roots(base, "record-failure")
    operation = _mkdir_operation(source, target, fs)
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="mkdir.record-failure",
            recorder_fail=frozenset({"mkdir"}),
        )
    )
    return reports


def _recording_order_matrix(base: Path) -> list[dict[str, object]]:
    reports: list[dict[str, object]] = []
    source, target, fs = _roots(base, "pre-destructive-flush")
    operation = _move_operation(source, target, fs)
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="recording.pre-destructive-flush-refusal",
            recorder_fail_once=frozenset({"flush"}),
        )
    )

    source, target, fs = _roots(base, "final-flush")
    operation = _copy_operation(source, target, fs)
    reports.append(
        _run_fixture(
            source,
            target,
            (operation,),
            row="recording.final-flush-degradation",
            recorder_fail=frozenset({"flush"}),
        )
    )

    source, target, fs = _roots(base, "sticky")
    first = _copy_operation(source, target, fs, number=1, relative="first.bin")
    second = _copy_operation(source, target, fs, number=2, relative="second.bin")
    reports.append(
        _run_fixture(
            source,
            target,
            (first, second),
            row="recording.sticky-aggregate-degradation",
            recorder_fail_once=frozenset({"copied"}),
        )
    )
    return reports


def _item(
    kind: OperationKind,
    outcome: Outcome,
    reason: str | None,
    *,
    detail: tuple[tuple[str, object], ...] = (),
    absent: tuple[str, ...] = (),
) -> ExpectedItem:
    return ExpectedItem(kind.value, outcome.value, reason, detail, absent)


@dataclass(frozen=True, slots=True)
class _ExpectedOperation:
    number: int
    kind: str
    path: str

    @property
    def op(self) -> str:
        return f"{self.number:032x}"


_DEFAULT_OPERATION_PATH = {
    OperationKind.COPY.value: "copy.bin",
    OperationKind.UPDATE.value: "update.bin",
    OperationKind.MOVE.value: "new.bin",
    OperationKind.MOVE_UPDATE.value: "renamed.bin",
    OperationKind.RECASE.value: "KEEP.txt",
    OperationKind.TRASH.value: "trash.bin",
    OperationKind.DELETE.value: "delete.bin",
    OperationKind.NOOP.value: "noop.bin",
    OperationKind.MKDIR.value: "folder",
}

_SOURCE_CONTENT = {
    OperationKind.COPY.value: b"copy-payload",
    OperationKind.UPDATE.value: b"new-version",
    OperationKind.MOVE.value: b"move-payload",
    OperationKind.MOVE_UPDATE.value: b"changed-version",
    OperationKind.RECASE.value: b"same",
    OperationKind.NOOP.value: b"same",
}

_SOURCE_CONTENT_OVERRIDES: dict[tuple[str, int], bytes] = {
    ("mkdir.pending-child-cancel", 2): b"child",
    ("mkdir.pending-child-pause", 2): b"child",
    ("mkdir.pending-child-checkpoint-exception", 2): b"child",
    ("resume.pause-same-execution-set", 1): b"first-payload",
    ("resume.pause-same-execution-set", 3): b"third-payload",
    ("failure.policy-stop-sweep", 1): b"failing-payload",
    ("failure.policy-stop-sweep", 2): b"later-payload",
    ("failure.policy-stop-sweep", 3): b"dependent-payload",
}


def _op(number: int, kind: OperationKind, path: str | None = None) -> _ExpectedOperation:
    return _ExpectedOperation(
        number,
        kind.value,
        _DEFAULT_OPERATION_PATH[kind.value] if path is None else path,
    )


_ITEM_COORDINATES: dict[str, tuple[_ExpectedOperation, ...]] = {
    "success.all-nine": (
        _op(1, OperationKind.COPY),
        _op(2, OperationKind.UPDATE),
        _op(3, OperationKind.MOVE, "move-new.bin"),
        _op(4, OperationKind.MOVE_UPDATE),
        _op(5, OperationKind.RECASE),
        _op(7, OperationKind.TRASH),
        _op(8, OperationKind.DELETE),
        _op(9, OperationKind.NOOP),
        _op(6, OperationKind.MKDIR),
    ),
    "cancel.before-effect-sweep": (
        _op(1, OperationKind.COPY, "first.bin"),
        _op(2, OperationKind.DELETE, "second.bin"),
    ),
    "mkdir.pending-child-cancel": (
        _op(1, OperationKind.MKDIR),
        _op(2, OperationKind.COPY, "folder\\child.bin"),
    ),
    "mkdir.pending-child-pause": (_op(1, OperationKind.MKDIR),),
    "mkdir.pending-child-checkpoint-exception": (
        _op(1, OperationKind.MKDIR),
    ),
    "recording.sticky-aggregate-degradation": (
        _op(1, OperationKind.COPY, "first.bin"),
        _op(2, OperationKind.COPY, "second.bin"),
    ),
    "resume.pause-same-execution-set": (
        _op(1, OperationKind.COPY, "first.bin"),
        _op(2, OperationKind.UPDATE),
        _op(3, OperationKind.COPY, "third.bin"),
    ),
    "failure.policy-stop-sweep": (
        _op(1, OperationKind.COPY, "failing.bin"),
        _op(2, OperationKind.COPY, "later.bin"),
        _op(3, OperationKind.COPY, "dependent.bin"),
    ),
}

_SELECTION_COORDINATES: dict[str, tuple[_ExpectedOperation, ...]] = {
    "pause.copy-prepared": (_op(1, OperationKind.COPY),),
    "mkdir.pending-child-pause": (
        _op(1, OperationKind.MKDIR),
        _op(2, OperationKind.COPY, "folder\\child.bin"),
    ),
    "mkdir.pending-child-checkpoint-exception": (
        _op(1, OperationKind.MKDIR),
        _op(2, OperationKind.COPY, "folder\\child.bin"),
    ),
}


def _expected_item_coordinates(
    expected: ExpectedSettlement,
) -> tuple[_ExpectedOperation, ...]:
    explicit = _ITEM_COORDINATES.get(expected.row)
    if explicit is not None:
        return explicit
    return tuple(
        _ExpectedOperation(index, item.kind, _DEFAULT_OPERATION_PATH[item.kind])
        for index, item in enumerate(expected.items, start=1)
    )


def _expected_selection_coordinates(
    expected: ExpectedSettlement,
) -> tuple[_ExpectedOperation, ...]:
    explicit = _SELECTION_COORDINATES.get(expected.row)
    if explicit is not None:
        return explicit
    return tuple(
        sorted(_expected_item_coordinates(expected), key=lambda operation: operation.number)
    )


def _policy_file(content: bytes, *, readonly: bool = False) -> dict[str, object]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    return {
        "schema": [
            "created",
            "identity",
            "kind",
            "mtime",
            "readonly",
            "sha256",
            "size",
            "text",
        ],
        "kind": "file",
        "size": len(content),
        "text": text,
        "sha256": hashlib.sha256(content).hexdigest(),
        "readonly": readonly,
        "identity_present": True,
        "mtime_present": True,
        "created_present": True,
        "metadata_reference": None,
        "reference_available": None,
        "reference_schema": None,
        "reference_kind": None,
        "mtime_matches_reference": None,
        "created_matches_reference": None,
        "identity_matches_reference": None,
    }


def _policy_directory() -> dict[str, object]:
    return {
        "schema": ["created", "identity", "kind", "mtime"],
        "kind": "directory",
        "identity_present": True,
        "mtime_present": True,
        "created_present": True,
        "metadata_reference": None,
        "reference_available": None,
        "reference_schema": None,
        "reference_kind": None,
        "mtime_matches_reference": None,
        "created_matches_reference": None,
        "identity_matches_reference": None,
    }


def _add_parent_directories(tree: dict[str, object], path: str) -> None:
    root, _, relative = path.partition("/")
    parts = PureWindowsPath(relative).parts
    for count in range(1, len(parts)):
        parent = "/".join((root, *parts[:count]))
        tree.setdefault(parent, _policy_directory())


def _expected_tree(expected: ExpectedSettlement) -> dict[str, object]:
    tree: dict[str, object] = {}
    for operation in _expected_selection_coordinates(expected):
        if operation.kind == OperationKind.MKDIR.value:
            path = f"$SOURCE/{operation.path}"
            _add_parent_directories(tree, path)
            tree[path] = _policy_directory()
            continue
        content = _SOURCE_CONTENT_OVERRIDES.get(
            (expected.row, operation.number), _SOURCE_CONTENT.get(operation.kind)
        )
        if content is None:
            continue
        path = f"$SOURCE/{operation.path.replace('\\', '/')}"
        _add_parent_directories(tree, path)
        tree[path] = _policy_file(content)

    readonly = set(expected.tree_readonly) | set(
        _EXTRA_TREE_READONLY.get(expected.row, ())
    )
    for path, content in expected.tree_files:
        payload = content.encode("utf-8")
        _add_parent_directories(tree, path)
        tree[path] = _policy_file(payload, readonly=path in readonly)
    for path, content in _EXTRA_TREE_FILES.get(expected.row, ()):
        payload = content.encode("utf-8")
        _add_parent_directories(tree, path)
        tree[path] = _policy_file(payload, readonly=path in readonly)
    for path in expected.tree_directories:
        _add_parent_directories(tree, path)
        tree[path] = _policy_directory()
    for path in _EXTRA_TREE_DIRECTORIES.get(expected.row, ()):
        _add_parent_directories(tree, path)
        tree[path] = _policy_directory()
    relations = _TREE_METADATA_RELATIONS.get(expected.row, {})
    for path, relation in relations.items():
        node = tree.get(path)
        if not isinstance(node, dict):
            raise AuditError(
                f"metadata relation for {expected.row} names absent tree path {path}"
            )
        node.update(
            {
                "metadata_reference": f"{relation.op}:{relation.reference}",
                "reference_available": True,
                "reference_schema": [
                    "attributes",
                    "created",
                    "identity",
                    "kind",
                    "mtime",
                    "nlink",
                    "size",
                ],
                "reference_kind": node.get("kind"),
                "mtime_matches_reference": relation.mtime_matches,
                "created_matches_reference": relation.created_matches,
                "identity_matches_reference": relation.identity_matches,
            }
        )
    for path in tree:
        if (
            path.startswith(("$SOURCE/", "$TARGET/"))
            and path not in relations
            and not _is_unbound_trash_parent(path)
        ):
            raise AuditError(
                f"metadata relation catalog omits {expected.row} tree path {path}"
            )
    return dict(sorted(tree.items()))


def _exact_items(
    expected: ExpectedSettlement,
) -> tuple[list[dict[str, object]], tuple[_ExpectedOperation, ...]]:
    coordinates = _expected_item_coordinates(expected)
    details = _EXACT_ITEM_DETAILS.get(expected.row)
    if details is None:
        details = tuple({} for _ in expected.items)
    if len(coordinates) != len(expected.items) or len(details) != len(expected.items):
        raise AuditError(f"invalid exact item declaration for {expected.row}")
    items = [
        {
            "op": operation.op,
            "kind": item.kind,
            "path": operation.path,
            "outcome": item.outcome,
            "reason": item.reason,
            "detail": dict(detail),
        }
        for operation, item, detail in zip(
            coordinates, expected.items, details, strict=True
        )
    ]
    return items, coordinates


def _expected_evidence(
    expected: ExpectedSettlement,
    item_maps: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    eligible = [
        item
        for item in item_maps
        if item["kind"] in {kind.value for kind in _BYTE_KINDS}
        and item["outcome"] == Outcome.SUCCEEDED.value
    ]
    if len(eligible) != len(expected.evidence_recorded):
        raise AuditError(f"invalid exact evidence declaration for {expected.row}")
    evidence: list[dict[str, object]] = []
    for item, recorded in zip(eligible, expected.evidence_recorded, strict=True):
        content = _SOURCE_CONTENT_OVERRIDES.get(
            (expected.row, int(str(item["op"]), 16)),
            _SOURCE_CONTENT[str(item["kind"])],
        )
        path = str(item["path"])
        op_id = str(item["op"])
        evidence.append(
            {
                "schema": [
                    "content",
                    "kind",
                    "op",
                    "path",
                    "recorded",
                    "recorded_identity",
                    "subject",
                ],
                "op": op_id,
                "kind": item["kind"],
                "path": path,
                "recorded": recorded,
                "content": {
                    "algorithm": "xxh3_128",
                    "digest": xxh3_128(content).hexdigest(),
                    "size": len(content),
                    "provenance": "copy",
                    "observed_at": "2026-08-10T12:00:00+00:00",
                },
                "subject": {
                    "schema": [
                        "attributes",
                        "created",
                        "identity",
                        "kind",
                        "mtime",
                        "nlink",
                        "size",
                    ],
                    "kind": "file",
                    "size": len(content),
                    "identity_present": True,
                    "identity_matches_tree": True,
                    "nlink": 1,
                    "attributes": stat_module.FILE_ATTRIBUTE_ARCHIVE,
                    "mtime_present": True,
                    "created_present": True,
                    "mtime_matches_tree": True,
                    "created_matches_tree": True,
                },
                "recorded_identity": (
                    None
                    if not recorded
                    else {
                        "row_id": f"row-{op_id}",
                        "location_id": "audit-target",
                        "scope_token": str(RUN_ID),
                        "rel_path_key": normalize_relative_path(path),
                    }
                ),
            }
        )
    return evidence


_RECORDER_COMMAND_BY_KIND = {
    OperationKind.COPY.value: "copied",
    OperationKind.UPDATE.value: "updated",
    OperationKind.MOVE.value: "moved",
    OperationKind.MOVE_UPDATE.value: "move_updated",
    OperationKind.RECASE.value: "recased",
    OperationKind.TRASH.value: "trashed",
    OperationKind.DELETE.value: "deleted",
    OperationKind.NOOP.value: "noop",
    OperationKind.MKDIR.value: "mkdir",
}
_RECORDER_FAILURE_CALLS = {
    ("mkdir.record-failure", 0),
    ("recording.sticky-aggregate-degradation", 0),
    ("record.copy-failure", 0),
    ("record.nonbyte-failure", 0),
}


def _build_recorder_trace_schedules() -> dict[str, tuple[str, ...]]:
    """Declare every recorder call, including failed and successful flushes."""

    schedules: dict[str, tuple[str, ...]] = {}

    def add(rows: Sequence[str], *tokens: str) -> None:
        for row in rows:
            if row in schedules:
                raise AuditError(f"duplicate recorder trace schedule for {row}")
            schedules[row] = tokens

    add(
        ("success.all-nine",),
        "copied",
        "flush",
        "updated",
        "flush",
        "moved",
        "flush",
        "move_updated",
        "flush",
        "recased",
        "flush",
        "trashed",
        "flush",
        "deleted",
        "noop",
        "mkdir",
        "flush",
    )
    add(
        (
            "failure.copy-prepublish-cleanup-ok",
            "failure.policy-stop-sweep",
            "failure.byte-published.copy",
            "failure.byte-published.target-changed",
            "failure.byte-published.target-missing",
            "failure.byte-published.target-unreadable",
            "failure.byte-published.move-update",
            "failure.nonbyte-commit.mkdir",
            "failure.noop-drift",
            "cancel.before-effect-sweep",
            "cancel.copy-prepared",
            "cancel.copy-published",
            "cancel.move-update-partial-publish",
            "pause.copy-prepared",
            "cleanup.ordinary.no-durable-cleanup-failure",
            "cleanup.ordinary.pre-retry-cleanup-fails",
            "cleanup.canceled-failure",
            "mkdir.primitive-precommit-unchanged",
            "mkdir.primitive-commit-then-raise",
            "mkdir.metadata-failure.available-probe",
            "mkdir.metadata-failure.unavailable-probe",
            "mkdir.metadata-failure.disappeared-after-create",
        ),
        "flush",
    )
    add(
        (
            "failure.move-precommit-unchanged",
            "failure.byte-published.update",
            "failure.nonbyte-commit.move",
            "failure.nonbyte-commit.recase",
            "failure.nonbyte-commit.trash",
            "failure.nonbyte-commit.delete",
            "failure.nonbyte-commit.move-restored",
            "failure.nonbyte-commit.trash-restored",
            "failure.nonbyte-commit.delete-restored",
            "failure.nonbyte-unreadable.delete-precommit",
            "update.backup-state.failure.retained",
            "update.backup-state.failure.changed",
            "update.backup-state.failure.absent",
            "update.backup-state.failure.unverified",
            "update.backup-state.cancel.retained",
            "update.backup-state.cancel.changed",
            "update.backup-state.cancel.absent",
            "update.backup-state.cancel.unverified",
            "failure.update-sibling.publication-unverified-plus-readonly",
            "failure.update-sibling.confirmed-publication-suppresses-readonly",
            "failure.update-sibling.unchanged-readonly",
            "failure.update-sibling.unreadable-readonly-mutation",
            "failure.move-update-new-and-trash",
            "cancel.committed-move",
            "cancel.update-composed-unverified-plus-readonly",
            "cleanup.ordinary.durable-verdict-plus-cleanup-failure",
        ),
        "flush",
        "flush",
    )
    add(
        (
            "retry.copy-prepared",
            "retry.copy-published",
            "cleanup.ordinary.stale-owned-temp-recovered",
            "cleanup.ordinary.pre-retry-cleanup-succeeds",
        ),
        "copied",
        "flush",
    )
    add(
        ("retry.update-after-backup", "retry.control.pause"),
        "flush",
        "flush",
        "updated",
        "flush",
    )
    add(
        ("retry.move-update-after-publish",),
        "flush",
        "flush",
        "move_updated",
        "flush",
    )
    add(
        ("retry.committed-move-settles-once", "retry.control.pause-then-cancel"),
        "flush",
        "flush",
        "flush",
    )
    add(
        (
            "retry.committed-move-failure-policy-escape",
            "retry.committed-move-sleep-escape",
        ),
        "flush",
        "flush",
    )
    add(
        ("resume.pause-same-execution-set",),
        "copied",
        "flush",
        "flush",
        "updated",
        "flush",
        "copied",
        "flush",
        "flush",
    )
    add(
        (
            "mkdir.pending-child-cancel",
            "mkdir.pending-child-pause",
            "mkdir.pending-child-checkpoint-exception",
        ),
        "mkdir",
        "flush",
    )
    add(("mkdir.record-failure",), "mkdir!", "flush")
    add(("recording.pre-destructive-flush-refusal",), "flush!", "flush")
    add(("recording.final-flush-degradation",), "copied", "flush!")
    add(
        ("recording.sticky-aggregate-degradation",),
        "copied!",
        "copied",
        "flush",
    )
    add(("record.copy-failure",), "copied!", "flush")
    add(("record.nonbyte-failure",), "flush", "moved!", "flush")
    return schedules


_RECORDER_TRACE_SCHEDULES = _build_recorder_trace_schedules()


def _expected_recorded_stat(
    *,
    kind: str,
    size: int,
    reference_size: bool = True,
    reference_identity: bool = True,
) -> dict[str, object]:
    is_directory = kind == EntryKind.DIRECTORY.value
    return {
        "schema": [
            "attributes",
            "created",
            "identity",
            "kind",
            "mtime",
            "nlink",
            "size",
        ],
        "kind": kind,
        "size": size,
        "identity_present": True,
        "nlink": 1,
        "attributes": (
            stat_module.FILE_ATTRIBUTE_DIRECTORY
            if is_directory
            else stat_module.FILE_ATTRIBUTE_ARCHIVE
        ),
        "kind_matches_reference": True,
        "size_matches_reference": True if reference_size else None,
        "identity_matches_reference": True if reference_identity else None,
        "mtime_matches_reference": True,
        "created_matches_reference": True,
    }


def _expected_recorder_calls(
    expected: ExpectedSettlement,
    evidence: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    coordinates = list(_expected_item_coordinates(expected))
    used: set[int] = set()
    evidence_by_op = {str(entry["op"]): entry for entry in evidence}
    tree = _expected_tree(expected)
    nonflush_calls: list[dict[str, object]] = []
    for call_index, command in enumerate(expected.recorder_commands):
        operation_index = next(
            (
                index
                for index, operation in enumerate(coordinates)
                if index not in used
                and _RECORDER_COMMAND_BY_KIND.get(operation.kind) == command
            ),
            None,
        )
        if operation_index is None:
            raise AuditError(
                f"recorder command {command!r} has no operation in {expected.row}"
            )
        used.add(operation_index)
        operation = coordinates[operation_index]
        payload: dict[str, object] = {"op": operation.op}
        target_path = (
            "$TARGET/" + PureWindowsPath(operation.path).as_posix()
        )
        if command in {"copied", "updated", "move_updated"}:
            published = evidence_by_op.get(operation.op)
            if published is None:
                raise AuditError(
                    f"recorder byte command lacks evidence in {expected.row}"
                )
            content = dict(published["content"])
            digest = bytes.fromhex(str(content["digest"]))
            content["digest"] = {
                "bytes": len(digest),
                "sha256": hashlib.sha256(digest).hexdigest(),
            }
            payload.update(
                {
                    "schema": ["attestation", "op"],
                    "attestation": {
                        "schema": ["content", "subject"],
                        "content": content,
                        "subject": published["subject"],
                    },
                }
            )
            result = published["recorded_identity"]
        elif command in {"moved", "recased"}:
            target = tree.get(target_path)
            if not isinstance(target, Mapping):
                raise AuditError(
                    f"recorder target is absent from {expected.row}: {target_path}"
                )
            payload.update(
                {
                    "schema": ["op", "target"],
                    "target": _expected_recorded_stat(
                        kind=EntryKind.FILE.value,
                        size=int(target["size"]),
                    ),
                }
            )
            result = None
        elif command == "mkdir":
            payload.update(
                {
                    "schema": ["op", "target"],
                    "target": _expected_recorded_stat(
                        kind=EntryKind.DIRECTORY.value,
                        size=0,
                        reference_size=False,
                    ),
                }
            )
            result = None
        elif command == "trashed":
            trash_relative = (
                f".synctrash/{RUN_ID}/"
                f"{PureWindowsPath(operation.path).as_posix()}"
            )
            trash_path = f"$TARGET/{trash_relative}"
            target = tree.get(trash_path)
            if not isinstance(target, Mapping):
                raise AuditError(
                    f"recorder trash target is absent from {expected.row}: {trash_path}"
                )
            payload.update(
                {
                    "schema": ["op", "target", "trash_relative_path"],
                    "trash_relative_path": trash_relative,
                    "target": _expected_recorded_stat(
                        kind=EntryKind.FILE.value,
                        size=int(target["size"]),
                    ),
                }
            )
            result = None
        elif command == "deleted":
            payload.update(
                {
                    "schema": ["op", "prior"],
                    "prior": _expected_recorded_stat(
                        kind=EntryKind.FILE.value,
                        size=len(b"delete-payload"),
                    ),
                }
            )
            result = None
        elif command == "noop":
            source_path = (
                "$SOURCE/" + PureWindowsPath(operation.path).as_posix()
            )
            source = tree.get(source_path)
            target = tree.get(target_path)
            if not isinstance(source, Mapping) or not isinstance(target, Mapping):
                raise AuditError(f"recorder noop paths are absent in {expected.row}")
            payload.update(
                {
                    "schema": ["op", "source", "target"],
                    "source": _expected_recorded_stat(
                        kind=EntryKind.FILE.value,
                        size=int(source["size"]),
                    ),
                    "target": _expected_recorded_stat(
                        kind=EntryKind.FILE.value,
                        size=int(target["size"]),
                    ),
                }
            )
            result = None
        else:
            raise AuditError(
                f"unsupported recorder expectation {command!r} in {expected.row}"
            )
        failed = (expected.row, call_index) in _RECORDER_FAILURE_CALLS
        nonflush_calls.append(
            {
                "schema": (
                    ["command", "error", "message", "payload", "result"]
                    if failed
                    else ["command", "payload", "result"]
                ),
                "command": command,
                "payload": payload,
                "result": None if failed else result,
                "error": "RuntimeError" if failed else None,
                "message": (
                    f"injected {command} recorder failure" if failed else None
                ),
            }
        )
    schedule = _RECORDER_TRACE_SCHEDULES.get(expected.row)
    if schedule is None:
        raise AuditError(f"recorder trace schedule is absent for {expected.row}")
    calls: list[dict[str, object]] = []
    nonflush_index = 0
    for token in schedule:
        failed = token.endswith("!")
        command = token.removesuffix("!")
        if command == "flush":
            calls.append(
                {
                    "schema": (
                        ["command", "error", "message", "payload", "result"]
                        if failed
                        else ["command", "payload", "result"]
                    ),
                    "command": "flush",
                    "payload": {},
                    "result": None,
                    "error": "RuntimeError" if failed else None,
                    "message": (
                        "injected flush recorder failure" if failed else None
                    ),
                }
            )
            continue
        if nonflush_index >= len(nonflush_calls):
            raise AuditError(
                f"recorder trace schedule has extra command {token!r} "
                f"for {expected.row}"
            )
        call = nonflush_calls[nonflush_index]
        nonflush_index += 1
        if call["command"] != command or (call["error"] is not None) != failed:
            raise AuditError(
                f"recorder trace schedule disagrees with {expected.row}: {token!r}"
            )
        calls.append(call)
    if nonflush_index != len(nonflush_calls):
        raise AuditError(f"recorder trace schedule omits calls for {expected.row}")
    flush_count = sum(token.removesuffix("!") == "flush" for token in schedule)
    if (
        expected.recorder_flushes is not None
        and flush_count != expected.recorder_flushes
    ):
        raise AuditError(
            f"recorder trace schedule flush count disagrees with {expected.row}"
        )
    return calls


def _expected_policy_projection(expected: ExpectedSettlement) -> dict[str, object]:
    item_maps, _ = _exact_items(expected)
    selection = _expected_selection_coordinates(expected)
    result = None
    if expected.returned is not None:
        bytes_done, bytes_total = _RESULT_BYTES.get(expected.row, (0, 0))
        result = {
            "status": expected.returned,
            "recording": expected.recording,
            "audit": "ok",
            "disposition": "ran",
            "canceled": False,
            "items": sorted(item_maps, key=lambda item: str(item["op"])),
            "phases": [],
            "bytes_done": bytes_done,
            "bytes_total": bytes_total,
            "error": None,
        }
    evidence = _expected_evidence(expected, item_maps)
    projection: dict[str, object] = {
        "row": expected.row,
        "termination": {"returned": expected.returned, "raised": expected.raised},
        "result": result,
        "execution_set": {
            "schema": [
                "published_evidence",
                "recording",
                "selected",
                "selection",
                "status",
            ],
            "selected": len(selection),
            "selection": [
                {"op": operation.op, "kind": operation.kind}
                for operation in selection
            ],
            "recording": expected.recording,
            "status": [
                {
                    "op": item["op"],
                    "kind": item["kind"],
                    "outcome": item["outcome"],
                }
                for item in sorted(item_maps, key=lambda item: str(item["op"]))
            ],
            "published_evidence": evidence,
        },
        "items": item_maps,
        "reliable_events": [
            {"type": "phase", "phase": "execute"},
            *({"type": "item", **item} for item in item_maps),
        ],
        "recorder_calls": _expected_recorder_calls(expected, evidence),
        "tree": _expected_tree(expected),
    }
    if expected.row == "resume.pause-same-execution-set":
        _apply_resume_policy_projection(projection, item_maps)
    return projection


def _apply_resume_policy_projection(
    projection: dict[str, object], item_maps: list[dict[str, object]]
) -> None:
    xset = projection["execution_set"]
    if not isinstance(xset, dict):
        raise AuditError("resume exact projection lacks an execution set")
    final_result = projection["result"]
    if not isinstance(final_result, dict):
        raise AuditError("resume exact projection lacks a result")
    second_items = [
        {
            **item,
            "reason": "previously-settled",
            "detail": {"continued": True},
        }
        if index < 2
        else dict(item)
        for index, item in enumerate(item_maps)
    ]
    terminal_items = [
        {
            **item,
            "reason": "previously-settled",
            "detail": {"continued": True},
        }
        for item in item_maps
    ]
    second_result = {**final_result, "items": second_items}
    terminal_result = {**final_result, "items": terminal_items}
    projection["result"] = terminal_result
    projection["reliable_events"] = [
        {"type": "phase", "phase": "execute"},
        *({"type": "item", **item} for item in item_maps[:2]),
        {"type": "phase", "phase": "execute"},
        {"type": "item", **item_maps[2]},
        {"type": "phase", "phase": "execute"},
    ]
    final_tree = projection["tree"]
    if not isinstance(final_tree, dict):
        raise AuditError("resume exact projection lacks a tree")
    recorder_calls = projection["recorder_calls"]
    if not isinstance(recorder_calls, list):
        raise AuditError("resume exact projection lacks recorder calls")
    first_tree = dict(final_tree)
    first_tree.pop("$TARGET/third.bin")
    first_xset = {
        **xset,
        "status": list(xset["status"][:2]),
        "published_evidence": list(xset["published_evidence"][:2]),
    }
    first_items = item_maps[:2]
    first_invocation = {
        "row": projection["row"],
        "termination": {"returned": None, "raised": "PauseRequested"},
        "result": None,
        "execution_set": first_xset,
        "items": first_items,
        "reliable_events": [
            {"type": "phase", "phase": "execute"},
            *({"type": "item", **item} for item in first_items),
        ],
        "recorder_calls": recorder_calls[:5],
        "tree": first_tree,
        "recorder_commands": ["copied", "updated"],
        "recorder_flushes": 3,
        "backend_calls": 2,
    }
    second_invocation = {
        "row": projection["row"],
        "termination": {"returned": "completed", "raised": None},
        "result": second_result,
        "execution_set": xset,
        "items": [item_maps[2]],
        "reliable_events": [
            {"type": "phase", "phase": "execute"},
            {"type": "item", **item_maps[2]},
        ],
        "recorder_calls": recorder_calls[:7],
        "tree": final_tree,
        "recorder_commands": ["copied", "updated", "copied"],
        "recorder_flushes": 4,
        "backend_calls": 3,
    }
    third_invocation = {
        "row": projection["row"],
        "termination": {"returned": "completed", "raised": None},
        "result": terminal_result,
        "execution_set": xset,
        "items": [],
        "reliable_events": [{"type": "phase", "phase": "execute"}],
        "recorder_calls": recorder_calls,
        "tree": final_tree,
        "recorder_commands": ["copied", "updated", "copied"],
        "recorder_flushes": 5,
        "backend_calls": 3,
    }
    projection["invocations"] = [
        first_invocation,
        second_invocation,
        third_invocation,
    ]


_SUCCESS_ALL_NINE = ExpectedSettlement(
    returned=SessionState.COMPLETED.value,
    raised=None,
    recording=RecordingStatus.OK.value,
    items=(
        _item(OperationKind.COPY, Outcome.SUCCEEDED, None),
        _item(OperationKind.UPDATE, Outcome.SUCCEEDED, None),
        _item(OperationKind.MOVE, Outcome.SUCCEEDED, None),
        _item(OperationKind.MOVE_UPDATE, Outcome.SUCCEEDED, None),
        _item(OperationKind.RECASE, Outcome.SUCCEEDED, None),
        _item(OperationKind.TRASH, Outcome.SUCCEEDED, None),
        _item(OperationKind.DELETE, Outcome.SUCCEEDED, None),
        _item(OperationKind.NOOP, Outcome.SKIPPED, "noop"),
        _item(OperationKind.MKDIR, Outcome.SUCCEEDED, None),
    ),
    recorder_commands=(
        "copied",
        "updated",
        "moved",
        "move_updated",
        "recased",
        "trashed",
        "deleted",
        "noop",
        "mkdir",
    ),
    evidence_recorded=(True, True, True),
    tree_files=(
        ("$TARGET/copy.bin", "copy-payload"),
        ("$TARGET/update.bin", "new-version"),
        ("$TARGET/move-new.bin", "move-payload"),
        ("$TARGET/renamed.bin", "changed-version"),
        ("$TARGET/KEEP.txt", "same"),
        ("$TARGET/noop.bin", "same"),
    ),
    tree_absent=(
        "$TARGET/move-old.bin",
        "$TARGET/old.bin",
        "$TARGET/keep.txt",
        "$TARGET/trash.bin",
        "$TARGET/delete.bin",
    ),
    backend_calls=3,
    row="success.all-nine",
)


_FAILURE_BYTE_PUBLISHED = (
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(
            OperationKind.COPY,
            Outcome.FAILED,
            "io-error",
            detail=(("publish_state", "published"), ("durable_state", "target-published")),
        ),),
        (),
        tree_files=(("$TARGET/copy.bin", "copy-payload"),),
        backend_calls=1,
        policy_decisions=("continue",),
        row="failure.byte-published.copy",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(
            OperationKind.UPDATE,
            Outcome.FAILED,
            "io-error",
            detail=(
                ("publish_state", "published"),
                ("durable_state", "target-published-with-backup"),
                ("backup_state", "retained"),
            ),
        ),),
        (),
        tree_files=(("$TARGET/update.bin", "new-version"),),
        backend_calls=1,
        policy_decisions=("continue",),
        row="failure.byte-published.update",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(
            OperationKind.MOVE_UPDATE,
            Outcome.FAILED,
            "io-error",
            detail=(("publish_state", "published"), ("durable_state", "new-and-old")),
        ),),
        (),
        tree_files=(
            ("$TARGET/renamed.bin", "changed-version"),
            ("$TARGET/old.bin", "old-version"),
        ),
        backend_calls=1,
        policy_decisions=("continue",),
        row="failure.byte-published.move-update",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(
            OperationKind.COPY,
            Outcome.FAILED,
            "io-error",
            detail=(
                ("publish_state", "published"),
                ("target_state", "changed-after-publish"),
                ("durable_state", "target-changed-after-publish"),
            ),
        ),),
        (),
        tree_files=(("$TARGET/copy.bin", "foreign-published"),),
        backend_calls=1,
        policy_decisions=("continue",),
        fs_counts=(("flush_directory", 1),),
        row="failure.byte-published.target-changed",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(
            OperationKind.COPY,
            Outcome.FAILED,
            "io-error",
            detail=(
                ("publish_state", "published"),
                ("target_state", "missing-after-publish"),
                ("durable_state", "target-missing-after-publish"),
            ),
        ),),
        (),
        tree_absent=("$TARGET/copy.bin",),
        backend_calls=1,
        policy_decisions=("continue",),
        fs_counts=(("flush_directory", 1),),
        row="failure.byte-published.target-missing",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(
            OperationKind.COPY,
            Outcome.FAILED,
            "io-error",
            detail=(
                ("publish_state", "published"),
                ("target_state", "unverified-after-publish"),
                ("durable_state", "target-unverified-after-publish"),
                (
                    "target_state_error",
                    "PermissionError: published target probe unavailable",
                ),
            ),
        ),),
        (),
        tree_files=(("$TARGET/copy.bin", "copy-payload"),),
        backend_calls=1,
        policy_decisions=("continue",),
        fs_counts=(("flush_directory", 1),),
        row="failure.byte-published.target-unreadable",
    ),
)


_FAILURE_NONBYTE_COMMIT = (
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(OperationKind.MOVE, Outcome.FAILED, "io-error", detail=(("durable_state", "target-renamed"),)),),
        (),
        tree_files=(("$TARGET/new.bin", "move-payload"),),
        backend_calls=0,
        policy_decisions=("continue",),
        row="failure.nonbyte-commit.move",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(OperationKind.RECASE, Outcome.FAILED, "io-error", detail=(("durable_state", "recase-state-unverified"),)),),
        (),
        tree_files=(("$TARGET/KEEP.txt", "same"),),
        backend_calls=0,
        policy_decisions=("continue",),
        row="failure.nonbyte-commit.recase",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(OperationKind.TRASH, Outcome.FAILED, "io-error", detail=(("durable_state", "target-trashed"),)),),
        (),
        tree_absent=("$TARGET/trash.bin",),
        backend_calls=0,
        policy_decisions=("continue",),
        row="failure.nonbyte-commit.trash",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(OperationKind.DELETE, Outcome.FAILED, "io-error", detail=(("durable_state", "target-deleted"),)),),
        (),
        tree_absent=("$TARGET/delete.bin",),
        backend_calls=0,
        policy_decisions=("continue",),
        row="failure.nonbyte-commit.delete",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(OperationKind.MKDIR, Outcome.FAILED, "io-error", detail=(("durable_state", "directory-created"),)),),
        (),
        backend_calls=0,
        row="failure.nonbyte-commit.mkdir",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(
            OperationKind.MOVE,
            Outcome.FAILED,
            "io-error",
            detail=(("durable_state", "source-restored-after-move"),),
        ),),
        (),
        tree_files=(("$TARGET/old.bin", "move-payload"),),
        tree_absent=("$TARGET/new.bin",),
        backend_calls=0,
        recorder_flushes=2,
        policy_decisions=("continue",),
        row="failure.nonbyte-commit.move-restored",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(
            OperationKind.TRASH,
            Outcome.FAILED,
            "io-error",
            detail=(("durable_state", "source-restored-after-trash"),),
        ),),
        (),
        tree_files=(("$TARGET/trash.bin", "trash-payload"),),
        backend_calls=0,
        recorder_flushes=2,
        policy_decisions=("continue",),
        row="failure.nonbyte-commit.trash-restored",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(
            OperationKind.DELETE,
            Outcome.FAILED,
            "io-error",
            detail=(("durable_state", "target-restored-after-delete"),),
        ),),
        (),
        tree_files=(("$TARGET/delete.bin", "delete-payload"),),
        backend_calls=0,
        recorder_flushes=2,
        policy_decisions=("continue",),
        row="failure.nonbyte-commit.delete-restored",
    ),
    ExpectedSettlement(
        SessionState.FAILED.value,
        None,
        RecordingStatus.DEGRADED.value,
        (_item(
            OperationKind.DELETE,
            Outcome.FAILED,
            "io-error",
            detail=(
                ("durable_state", "delete-state-unverified"),
                (
                    "mutation_state_error",
                    "PermissionError: delete state probe unavailable",
                ),
            ),
        ),),
        (),
        tree_files=(("$TARGET/delete.bin", "delete-payload"),),
        backend_calls=0,
        recorder_flushes=2,
        policy_decisions=("continue",),
        row="failure.nonbyte-unreadable.delete-precommit",
    ),
)


_UPDATE_BACKUP_PATH = f"$TARGET/.synctrash/{RUN_ID}/update.bin"
_UPDATE_BACKUP_STATE_MATRIX = (
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.FAILED,
                "io-error",
                detail=(
                    ("publish_state", "not-published"),
                    ("backup_state", "retained"),
                    ("durable_state", "backup-retained"),
                ),
                absent=("mutation_durable_state", "published_path", "recording"),
            ),
        ),
        recorder_commands=(),
        tree_files=(
            ("$TARGET/update.bin", "old-version"),
            (_UPDATE_BACKUP_PATH, "old-version"),
        ),
        backend_calls=1,
        policy_decisions=("continue",),
        row="update.backup-state.failure.retained",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.FAILED,
                "io-error",
                absent=(
                    "publish_state",
                    "backup_state",
                    "durable_state",
                    "mutation_durable_state",
                    "recording",
                ),
            ),
        ),
        recorder_commands=(),
        tree_files=(
            ("$TARGET/update.bin", "old-version"),
            (_UPDATE_BACKUP_PATH, "foreign-backup"),
        ),
        backend_calls=1,
        policy_decisions=("continue",),
        row="update.backup-state.failure.changed",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.FAILED,
                "io-error",
                absent=(
                    "publish_state",
                    "backup_state",
                    "durable_state",
                    "mutation_durable_state",
                    "recording",
                ),
            ),
        ),
        recorder_commands=(),
        tree_files=(("$TARGET/update.bin", "old-version"),),
        tree_absent=(_UPDATE_BACKUP_PATH,),
        backend_calls=1,
        policy_decisions=("continue",),
        row="update.backup-state.failure.absent",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.FAILED,
                "io-error",
                absent=(
                    "publish_state",
                    "backup_state",
                    "durable_state",
                    "mutation_durable_state",
                    "recording",
                ),
            ),
        ),
        recorder_commands=(),
        tree_files=(
            ("$TARGET/update.bin", "old-version"),
            (_UPDATE_BACKUP_PATH, "old-version"),
        ),
        backend_calls=1,
        policy_decisions=("continue",),
        row="update.backup-state.failure.unverified",
    ),
    ExpectedSettlement(
        returned=None,
        raised="Canceled",
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.CANCELED,
                "canceled",
                detail=(
                    ("publish_state", "not-published"),
                    ("backup_state", "retained"),
                    ("durable_state", "backup-retained"),
                ),
                absent=("mutation_durable_state", "recording"),
            ),
        ),
        recorder_commands=(),
        tree_files=(
            ("$TARGET/update.bin", "old-version"),
            (_UPDATE_BACKUP_PATH, "old-version"),
        ),
        backend_calls=1,
        policy_decisions=("retry",),
        row="update.backup-state.cancel.retained",
    ),
    ExpectedSettlement(
        returned=None,
        raised="Canceled",
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.CANCELED,
                "canceled",
                detail=(
                    ("publish_state", "not-published"),
                    ("backup_state", "changed"),
                    ("durable_state", "target-not-published"),
                ),
                absent=("mutation_durable_state", "recording"),
            ),
        ),
        recorder_commands=(),
        tree_files=(
            ("$TARGET/update.bin", "old-version"),
            (_UPDATE_BACKUP_PATH, "foreign-backup"),
        ),
        backend_calls=1,
        policy_decisions=("retry",),
        row="update.backup-state.cancel.changed",
    ),
    ExpectedSettlement(
        returned=None,
        raised="Canceled",
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.CANCELED,
                "canceled",
                detail=(
                    ("publish_state", "not-published"),
                    ("backup_state", "absent"),
                    ("durable_state", "target-not-published"),
                ),
                absent=("mutation_durable_state", "recording"),
            ),
        ),
        recorder_commands=(),
        tree_files=(("$TARGET/update.bin", "old-version"),),
        tree_absent=(_UPDATE_BACKUP_PATH,),
        backend_calls=1,
        policy_decisions=("retry",),
        row="update.backup-state.cancel.absent",
    ),
    ExpectedSettlement(
        returned=None,
        raised="Canceled",
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.CANCELED,
                "canceled",
                detail=(
                    ("publish_state", "not-published"),
                    ("backup_state", "unverified"),
                    ("durable_state", "target-not-published"),
                ),
                absent=("mutation_durable_state", "recording"),
            ),
        ),
        recorder_commands=(),
        tree_files=(
            ("$TARGET/update.bin", "old-version"),
            (_UPDATE_BACKUP_PATH, "old-version"),
        ),
        backend_calls=1,
        policy_decisions=("retry",),
        row="update.backup-state.cancel.unverified",
    ),
)


_UPDATE_SIBLING_MATRIX = (
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.DEGRADED.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.FAILED,
                "io-error",
                detail=(
                    ("publish_state", "unverified"),
                    ("durable_state", "publication-unverified"),
                    (
                        "mutation_durable_state",
                        "target-metadata-changed-before-publish",
                    ),
                ),
            ),
        ),
        recorder_commands=(),
        tree_files=(("$TARGET/update.bin", "old-version"),),
        backend_calls=1,
        policy_decisions=("continue",),
        row="failure.update-sibling.publication-unverified-plus-readonly",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.DEGRADED.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.FAILED,
                "io-error",
                detail=(
                    ("publish_state", "published"),
                    ("target_state", "published"),
                    ("durable_state", "target-published"),
                ),
                absent=("mutation_state", "mutation_durable_state"),
            ),
        ),
        recorder_commands=(),
        tree_files=(("$TARGET/update.bin", "new-version"),),
        backend_calls=1,
        policy_decisions=("continue",),
        row="failure.update-sibling.confirmed-publication-suppresses-readonly",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.FAILED,
                "io-error",
                absent=(
                    "publish_state",
                    "durable_state",
                    "mutation_state",
                    "mutation_durable_state",
                    "recording",
                ),
            ),
        ),
        recorder_commands=(),
        tree_files=(("$TARGET/update.bin", "old-version"),),
        backend_calls=1,
        policy_decisions=("continue",),
        row="failure.update-sibling.unchanged-readonly",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.DEGRADED.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.FAILED,
                "io-error",
                detail=(
                    ("publish_state", "not-published"),
                    ("durable_state", "update-state-unverified"),
                    ("mutation_state", "unverified"),
                    (
                        "mutation_state_error",
                        "PermissionError: update state probe unavailable",
                    ),
                ),
            ),
        ),
        recorder_commands=(),
        tree_files=(("$TARGET/update.bin", "old-version"),),
        backend_calls=1,
        recorder_flushes=2,
        policy_decisions=("continue",),
        row="failure.update-sibling.unreadable-readonly-mutation",
    ),
)


_CLEANUP_ORDINARY_MATRIX = (
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.OK.value,
        items=(_item(OperationKind.COPY, Outcome.FAILED, "cleanup-failed"),),
        recorder_commands=(),
        tree_files=((f"$TARGET/copy.bin.synctmp-{RUN_ID}-{1:032x}", ""),),
        tree_absent=("$TARGET/copy.bin",),
        backend_calls=1,
        policy_decisions=("continue",),
        fs_counts=(("remove_owned_temp", 2),),
        row="cleanup.ordinary.no-durable-cleanup-failure",
    ),
    ExpectedSettlement(
        returned=SessionState.COMPLETED.value,
        raised=None,
        recording=RecordingStatus.OK.value,
        items=(_item(OperationKind.COPY, Outcome.SUCCEEDED, None),),
        recorder_commands=("copied",),
        evidence_recorded=(True,),
        tree_files=(("$TARGET/copy.bin", "copy-payload"),),
        tree_absent=(f"$TARGET/copy.bin.synctmp-{RUN_ID}-{1:032x}",),
        backend_calls=1,
        fs_counts=(("remove_owned_temp", 1),),
        row="cleanup.ordinary.stale-owned-temp-recovered",
    ),
    ExpectedSettlement(
        returned=SessionState.COMPLETED.value,
        raised=None,
        recording=RecordingStatus.OK.value,
        items=(_item(OperationKind.COPY, Outcome.SUCCEEDED, None),),
        recorder_commands=("copied",),
        evidence_recorded=(True,),
        tree_files=(("$TARGET/copy.bin", "copy-payload"),),
        tree_absent=(f"$TARGET/copy.bin.synctmp-{RUN_ID}-{1:032x}",),
        backend_calls=2,
        policy_decisions=("retry",),
        fs_counts=(("remove_owned_temp", 3), ("finalize_temp", 2)),
        row="cleanup.ordinary.pre-retry-cleanup-succeeds",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.OK.value,
        items=(_item(OperationKind.COPY, Outcome.FAILED, "cleanup-failed"),),
        recorder_commands=(),
        tree_files=(
            (f"$TARGET/copy.bin.synctmp-{RUN_ID}-{1:032x}", "copy"),
        ),
        tree_absent=("$TARGET/copy.bin",),
        backend_calls=1,
        policy_decisions=("retry",),
        fs_counts=(("remove_owned_temp", 2),),
        row="cleanup.ordinary.pre-retry-cleanup-fails",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.FAILED,
                "io-error",
                detail=(
                    ("publish_state", "not-published"),
                    ("backup_state", "retained"),
                    ("durable_state", "backup-retained"),
                    ("cleanup_error", "durable cleanup failure"),
                ),
                absent=("mutation_durable_state", "recording"),
            ),
        ),
        recorder_commands=(),
        tree_files=(
            ("$TARGET/update.bin", "old-version"),
            (f"$TARGET/.synctrash/{RUN_ID}/update.bin", "old-version"),
            (f"$TARGET/update.bin.synctmp-{RUN_ID}-{1:032x}", "new-version"),
        ),
        backend_calls=1,
        policy_decisions=("continue",),
        fs_counts=(("remove_owned_temp", 2),),
        row="cleanup.ordinary.durable-verdict-plus-cleanup-failure",
    ),
)


_PAUSE_COPY_PREPARED = ExpectedSettlement(
    returned=None,
    raised="PauseRequested",
    recording=RecordingStatus.OK.value,
    items=(),
    recorder_commands=(),
    tree_absent=(
        "$TARGET/copy.bin",
        f"$TARGET/copy.bin.synctmp-{RUN_ID}-{1:032x}",
    ),
    backend_calls=1,
    fs_counts=(("remove_owned_temp", 2),),
    row="pause.copy-prepared",
)


_RETRY_CONTROL_MATRIX = (
    ExpectedSettlement(
        returned=None,
        raised="PauseRequested",
        recording=RecordingStatus.OK.value,
        items=(_item(OperationKind.UPDATE, Outcome.SUCCEEDED, None),),
        recorder_commands=("updated",),
        evidence_recorded=(True,),
        tree_files=(
            ("$TARGET/update.bin", "new-version"),
            (_UPDATE_BACKUP_PATH, "old-version"),
        ),
        backend_calls=1,
        policy_decisions=("retry",),
        fs_counts=(("replace", 2),),
        row="retry.control.pause",
    ),
    ExpectedSettlement(
        returned=None,
        raised="Canceled",
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.UPDATE,
                Outcome.CANCELED,
                "canceled",
                detail=(
                    ("publish_state", "not-published"),
                    ("backup_state", "retained"),
                    ("durable_state", "backup-retained"),
                ),
                absent=("recording",),
            ),
        ),
        recorder_commands=(),
        tree_files=(
            ("$TARGET/update.bin", "old-version"),
            (_UPDATE_BACKUP_PATH, "old-version"),
        ),
        backend_calls=1,
        policy_decisions=("retry", "retry"),
        fs_counts=(("replace", 2),),
        row="retry.control.pause-then-cancel",
    ),
)


_MKDIR_MATRIX = (
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.OK.value,
        items=(
            _item(
                OperationKind.MKDIR,
                Outcome.FAILED,
                "io-error",
                absent=("durable_state", "mutation_state", "recording"),
            ),
        ),
        recorder_commands=(),
        tree_absent=("$TARGET/folder",),
        backend_calls=0,
        recorder_flushes=1,
        fs_counts=(("mkdir_new", 1), ("apply_metadata", 0)),
        row="mkdir.primitive-precommit-unchanged",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.DEGRADED.value,
        items=(
            _item(
                OperationKind.MKDIR,
                Outcome.FAILED,
                "io-error",
                detail=(
                    ("durable_state", "directory-present-after-create-attempt"),
                    ("mutation_state", "unverified"),
                    ("recording", "degraded"),
                ),
            ),
        ),
        recorder_commands=(),
        tree_directories=("$TARGET/folder",),
        backend_calls=0,
        recorder_flushes=1,
        fs_counts=(("mkdir_new", 1), ("apply_metadata", 0)),
        row="mkdir.primitive-commit-then-raise",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.DEGRADED.value,
        items=(
            _item(
                OperationKind.MKDIR,
                Outcome.FAILED,
                "io-error",
                detail=(
                    ("durable_state", "directory-created"),
                    ("mutation_state", "committed"),
                    ("recording", "degraded"),
                ),
            ),
        ),
        recorder_commands=(),
        tree_directories=("$TARGET/folder",),
        backend_calls=0,
        recorder_flushes=1,
        fs_counts=(("mkdir_new", 1), ("apply_metadata", 1), ("stat_path", 1)),
        row="mkdir.metadata-failure.available-probe",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.DEGRADED.value,
        items=(
            _item(
                OperationKind.MKDIR,
                Outcome.FAILED,
                "io-error",
                detail=(
                    ("durable_state", "mkdir-state-unverified"),
                    ("mutation_state", "committed"),
                    (
                        "mutation_state_error",
                        "PermissionError: mkdir probe unavailable",
                    ),
                    ("recording", "degraded"),
                ),
            ),
        ),
        recorder_commands=(),
        tree_directories=("$TARGET/folder",),
        backend_calls=0,
        recorder_flushes=1,
        fs_counts=(("mkdir_new", 1), ("apply_metadata", 1), ("stat_path", 1)),
        row="mkdir.metadata-failure.unavailable-probe",
    ),
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.DEGRADED.value,
        items=(
            _item(
                OperationKind.MKDIR,
                Outcome.FAILED,
                "io-error",
                detail=(
                    ("durable_state", "directory-missing-after-create"),
                    ("mutation_state", "committed"),
                    ("recording", "degraded"),
                ),
            ),
        ),
        recorder_commands=(),
        tree_absent=("$TARGET/folder",),
        backend_calls=0,
        recorder_flushes=1,
        fs_counts=(("mkdir_new", 1), ("apply_metadata", 1), ("stat_path", 1)),
        row="mkdir.metadata-failure.disappeared-after-create",
    ),
    ExpectedSettlement(
        returned=None,
        raised="Canceled",
        recording=RecordingStatus.OK.value,
        items=(
            _item(OperationKind.MKDIR, Outcome.SUCCEEDED, None),
            _item(OperationKind.COPY, Outcome.CANCELED, "canceled"),
        ),
        recorder_commands=("mkdir",),
        tree_directories=("$TARGET/folder",),
        tree_absent=("$TARGET/folder/child.bin",),
        backend_calls=0,
        recorder_flushes=1,
        fs_counts=(("mkdir_new", 1), ("apply_metadata", 1)),
        timeline_subsequence=("fs:mkdir_new:end", "recorder:mkdir", "recorder:flush"),
        row="mkdir.pending-child-cancel",
    ),
    ExpectedSettlement(
        returned=None,
        raised="PauseRequested",
        recording=RecordingStatus.OK.value,
        items=(_item(OperationKind.MKDIR, Outcome.SUCCEEDED, None),),
        recorder_commands=("mkdir",),
        tree_directories=("$TARGET/folder",),
        tree_absent=("$TARGET/folder/child.bin",),
        backend_calls=0,
        recorder_flushes=1,
        fs_counts=(("mkdir_new", 1), ("apply_metadata", 1)),
        timeline_subsequence=("fs:mkdir_new:end", "recorder:mkdir", "recorder:flush"),
        row="mkdir.pending-child-pause",
    ),
    ExpectedSettlement(
        returned=None,
        raised="RuntimeError",
        recording=RecordingStatus.OK.value,
        items=(_item(OperationKind.MKDIR, Outcome.SUCCEEDED, None),),
        recorder_commands=("mkdir",),
        tree_directories=("$TARGET/folder",),
        tree_absent=("$TARGET/folder/child.bin",),
        backend_calls=0,
        recorder_flushes=1,
        control_checkpoints=2,
        fs_counts=(("mkdir_new", 1), ("apply_metadata", 1)),
        timeline_subsequence=(
            "fs:mkdir_new:end",
            "control:checkpoint:2:raise:RuntimeError",
            "fs:apply_metadata:end",
            "recorder:mkdir",
            "emit:item:00000000000000000000000000000001:mkdir:succeeded",
            "recorder:flush",
        ),
        row="mkdir.pending-child-checkpoint-exception",
    ),
    ExpectedSettlement(
        returned=SessionState.COMPLETED.value,
        raised=None,
        recording=RecordingStatus.DEGRADED.value,
        items=(
            _item(
                OperationKind.MKDIR,
                Outcome.SUCCEEDED,
                None,
                detail=(("recording", "degraded"),),
            ),
        ),
        recorder_commands=("mkdir",),
        tree_directories=("$TARGET/folder",),
        backend_calls=0,
        recorder_flushes=1,
        fs_counts=(("mkdir_new", 1), ("apply_metadata", 1)),
        row="mkdir.record-failure",
    ),
)


_RECORDING_ORDER_MATRIX = (
    ExpectedSettlement(
        returned=SessionState.FAILED.value,
        raised=None,
        recording=RecordingStatus.DEGRADED.value,
        items=(
            _item(
                OperationKind.MOVE,
                Outcome.FAILED,
                "recorder-failed",
                absent=("durable_state",),
            ),
        ),
        recorder_commands=(),
        tree_files=(("$TARGET/old.bin", "move-payload"),),
        tree_absent=("$TARGET/new.bin",),
        backend_calls=0,
        recorder_flushes=2,
        policy_decisions=("continue",),
        fs_counts=(("rename_new", 0),),
        timeline_subsequence=("recorder:flush", "recorder:flush"),
        row="recording.pre-destructive-flush-refusal",
    ),
    ExpectedSettlement(
        returned=SessionState.COMPLETED.value,
        raised=None,
        recording=RecordingStatus.DEGRADED.value,
        items=(
            _item(
                OperationKind.COPY,
                Outcome.SUCCEEDED,
                None,
                absent=("recording",),
            ),
        ),
        recorder_commands=("copied",),
        evidence_recorded=(True,),
        tree_files=(("$TARGET/copy.bin", "copy-payload"),),
        backend_calls=1,
        recorder_flushes=1,
        timeline_subsequence=("recorder:copied", "recorder:flush"),
        row="recording.final-flush-degradation",
    ),
    ExpectedSettlement(
        returned=SessionState.COMPLETED.value,
        raised=None,
        recording=RecordingStatus.DEGRADED.value,
        items=(
            _item(
                OperationKind.COPY,
                Outcome.SUCCEEDED,
                None,
                detail=(("recording", "degraded"),),
            ),
            _item(
                OperationKind.COPY,
                Outcome.SUCCEEDED,
                None,
                absent=("recording",),
            ),
        ),
        recorder_commands=("copied", "copied"),
        evidence_recorded=(False, True),
        tree_files=(
            ("$TARGET/first.bin", "copy-payload"),
            ("$TARGET/second.bin", "copy-payload"),
        ),
        backend_calls=2,
        recorder_flushes=1,
        timeline_subsequence=(
            "recorder:copied",
            "recorder:copied",
            "recorder:flush",
        ),
        row="recording.sticky-aggregate-degradation",
    ),
)


_RESULT_BYTES: dict[str, tuple[int, int]] = {
    "success.all-nine": (38, 38),
    "failure.copy-prepublish-cleanup-ok": (0, 12),
    "failure.byte-published.copy": (12, 12),
    "failure.byte-published.update": (11, 11),
    "failure.byte-published.move-update": (15, 15),
    "failure.byte-published.target-changed": (12, 12),
    "failure.byte-published.target-missing": (12, 12),
    "failure.byte-published.target-unreadable": (12, 12),
    "update.backup-state.failure.retained": (11, 11),
    "update.backup-state.failure.changed": (11, 11),
    "update.backup-state.failure.absent": (11, 11),
    "update.backup-state.failure.unverified": (11, 11),
    "failure.update-sibling.publication-unverified-plus-readonly": (11, 11),
    "failure.update-sibling.confirmed-publication-suppresses-readonly": (11, 11),
    "failure.update-sibling.unchanged-readonly": (11, 11),
    "failure.update-sibling.unreadable-readonly-mutation": (11, 11),
    "failure.move-update-new-and-trash": (15, 15),
    "retry.copy-prepared": (12, 12),
    "retry.copy-published": (12, 12),
    "retry.update-after-backup": (11, 11),
    "retry.move-update-after-publish": (15, 15),
    "cleanup.ordinary.no-durable-cleanup-failure": (0, 12),
    "cleanup.ordinary.stale-owned-temp-recovered": (12, 12),
    "cleanup.ordinary.pre-retry-cleanup-succeeds": (12, 12),
    "cleanup.ordinary.pre-retry-cleanup-fails": (4, 12),
    "cleanup.ordinary.durable-verdict-plus-cleanup-failure": (11, 11),
    "recording.final-flush-degradation": (12, 12),
    "recording.sticky-aggregate-degradation": (24, 24),
    "record.copy-failure": (12, 12),
    "resume.pause-same-execution-set": (37, 37),
    "failure.policy-stop-sweep": (0, 45),
}

_EXTRA_TREE_FILES: dict[str, tuple[tuple[str, str], ...]] = {
    "success.all-nine": (
        (_UPDATE_BACKUP_PATH, "old-version"),
        (f"$TARGET/.synctrash/{RUN_ID}/old.bin", "old-version"),
        (f"$TARGET/.synctrash/{RUN_ID}/trash.bin", "trash-payload"),
    ),
    "failure.byte-published.update": ((_UPDATE_BACKUP_PATH, "old-version"),),
    "failure.nonbyte-commit.trash": (
        (f"$TARGET/.synctrash/{RUN_ID}/trash.bin", "trash-payload"),
    ),
    "failure.move-update-new-and-trash": (
        (f"$TARGET/.synctrash/{RUN_ID}/old.bin", "old-version"),
    ),
    "retry.update-after-backup": ((_UPDATE_BACKUP_PATH, "old-version"),),
    "retry.move-update-after-publish": (
        (f"$TARGET/.synctrash/{RUN_ID}/old.bin", "old-version"),
    ),
    "resume.pause-same-execution-set": (
        (_UPDATE_BACKUP_PATH, "old-version"),
    ),
}

_EXTRA_TREE_DIRECTORIES: dict[str, tuple[str, ...]] = {
    "success.all-nine": ("$TARGET/folder",),
    "failure.nonbyte-commit.mkdir": ("$TARGET/folder",),
    "failure.nonbyte-commit.trash-restored": (
        "$TARGET/.synctrash",
        f"$TARGET/.synctrash/{RUN_ID}",
    ),
    "update.backup-state.failure.absent": (
        "$TARGET/.synctrash",
        f"$TARGET/.synctrash/{RUN_ID}",
    ),
    "update.backup-state.cancel.absent": (
        "$TARGET/.synctrash",
        f"$TARGET/.synctrash/{RUN_ID}",
    ),
}

_EXTRA_TREE_READONLY: dict[str, tuple[str, ...]] = {
    "failure.update-sibling.unchanged-readonly": ("$TARGET/update.bin",),
}


def _is_unbound_trash_parent(path: str) -> bool:
    return path in {
        "$TARGET/.synctrash",
        f"$TARGET/.synctrash/{RUN_ID}",
    }


def _build_tree_metadata_relations() -> dict[
    str, dict[str, _TreeMetadataRelation]
]:
    """Declare every final target leaf's reviewed metadata relationship."""

    catalog: dict[str, dict[str, _TreeMetadataRelation]] = {}

    def add(
        rows: Sequence[str],
        path: str,
        operation: int,
        reference: str,
        *,
        mtime: bool = True,
        created: bool = True,
        identity: bool | None = True,
    ) -> None:
        relation = _TreeMetadataRelation(
            operation,
            reference,
            mtime,
            created,
            identity,
        )
        for row in rows:
            relations = catalog.setdefault(row, {})
            if path in relations:
                raise AuditError(
                    f"duplicate metadata relation for {row} tree path {path}"
                )
            relations[path] = relation

    add(
        ("success.all-nine",),
        "$TARGET/copy.bin",
        1,
        "intended",
        identity=False,
    )
    add(
        (
            "failure.byte-published.copy",
            "failure.byte-published.target-unreadable",
            "retry.copy-prepared",
            "retry.copy-published",
            "cancel.copy-published",
            "cleanup.ordinary.stale-owned-temp-recovered",
            "cleanup.ordinary.pre-retry-cleanup-succeeds",
            "recording.final-flush-degradation",
            "record.copy-failure",
        ),
        "$TARGET/copy.bin",
        1,
        "intended",
        identity=False,
    )
    add(
        ("failure.byte-published.target-changed",),
        "$TARGET/copy.bin",
        1,
        "intended",
        mtime=False,
        identity=False,
    )
    add(
        ("recording.sticky-aggregate-degradation",),
        "$TARGET/first.bin",
        1,
        "intended",
        identity=False,
    )
    add(
        ("recording.sticky-aggregate-degradation",),
        "$TARGET/second.bin",
        2,
        "intended",
        identity=False,
    )
    add(
        ("resume.pause-same-execution-set",),
        "$TARGET/first.bin",
        1,
        "intended",
        identity=False,
    )
    add(
        ("resume.pause-same-execution-set",),
        "$TARGET/third.bin",
        3,
        "intended",
        identity=False,
    )

    add(
        ("success.all-nine",),
        "$TARGET/update.bin",
        2,
        "intended",
        identity=False,
    )
    add(
        (
            "failure.byte-published.update",
            "failure.update-sibling.confirmed-publication-suppresses-readonly",
            "retry.update-after-backup",
            "retry.control.pause",
        ),
        "$TARGET/update.bin",
        1,
        "intended",
        identity=False,
    )
    add(
        ("resume.pause-same-execution-set",),
        "$TARGET/update.bin",
        2,
        "intended",
        identity=False,
    )
    add(
        (
            "update.backup-state.failure.retained",
            "update.backup-state.failure.changed",
            "update.backup-state.failure.absent",
            "update.backup-state.failure.unverified",
            "update.backup-state.cancel.retained",
            "update.backup-state.cancel.changed",
            "update.backup-state.cancel.absent",
            "update.backup-state.cancel.unverified",
            "failure.update-sibling.publication-unverified-plus-readonly",
            "failure.update-sibling.unchanged-readonly",
            "failure.update-sibling.unreadable-readonly-mutation",
            "retry.control.pause-then-cancel",
            "cancel.update-composed-unverified-plus-readonly",
            "cleanup.ordinary.durable-verdict-plus-cleanup-failure",
        ),
        "$TARGET/update.bin",
        1,
        "target_expected",
    )

    add(
        ("success.all-nine",),
        "$TARGET/move-new.bin",
        3,
        "prior_target_expected",
    )
    add(
        (
            "failure.move-precommit-unchanged",
            "failure.nonbyte-commit.move-restored",
            "recording.pre-destructive-flush-refusal",
        ),
        "$TARGET/old.bin",
        1,
        "prior_target_expected",
    )
    add(
        (
            "failure.nonbyte-commit.move",
            "retry.committed-move-settles-once",
            "retry.committed-move-failure-policy-escape",
            "retry.committed-move-sleep-escape",
            "cancel.committed-move",
            "record.nonbyte-failure",
        ),
        "$TARGET/new.bin",
        1,
        "prior_target_expected",
    )
    add(
        ("failure.nonbyte-commit.trash-restored",),
        "$TARGET/trash.bin",
        1,
        "target_expected",
    )
    add(
        (
            "failure.nonbyte-commit.delete-restored",
            "failure.nonbyte-unreadable.delete-precommit",
        ),
        "$TARGET/delete.bin",
        1,
        "target_expected",
    )
    add(
        ("success.all-nine",),
        "$TARGET/KEEP.txt",
        5,
        "prior_target_expected",
    )
    add(
        ("failure.nonbyte-commit.recase",),
        "$TARGET/KEEP.txt",
        1,
        "prior_target_expected",
    )

    add(
        ("success.all-nine",),
        "$TARGET/renamed.bin",
        4,
        "intended",
        identity=False,
    )
    add(
        (
            "failure.byte-published.move-update",
            "failure.move-update-new-and-trash",
            "retry.move-update-after-publish",
            "cancel.move-update-partial-publish",
        ),
        "$TARGET/renamed.bin",
        1,
        "intended",
        identity=False,
    )
    add(
        (
            "failure.byte-published.move-update",
            "cancel.move-update-partial-publish",
        ),
        "$TARGET/old.bin",
        1,
        "prior_target_expected",
    )

    add(
        ("success.all-nine",),
        "$TARGET/noop.bin",
        9,
        "target_expected",
    )
    add(
        ("failure.noop-drift",),
        "$TARGET/noop.bin",
        1,
        "target_expected",
        mtime=False,
    )
    add(
        ("cancel.before-effect-sweep",),
        "$TARGET/second.bin",
        2,
        "target_expected",
    )

    add(
        ("success.all-nine",),
        "$TARGET/folder",
        6,
        "intended",
        identity=False,
    )
    add(
        (
            "mkdir.pending-child-cancel",
            "mkdir.pending-child-pause",
            "mkdir.pending-child-checkpoint-exception",
            "mkdir.record-failure",
        ),
        "$TARGET/folder",
        1,
        "intended",
        identity=False,
    )
    add(
        (
            "failure.nonbyte-commit.mkdir",
            "mkdir.primitive-commit-then-raise",
            "mkdir.metadata-failure.available-probe",
            "mkdir.metadata-failure.unavailable-probe",
        ),
        "$TARGET/folder",
        1,
        "intended",
        mtime=False,
        created=False,
        identity=False,
    )

    add(
        ("success.all-nine",),
        f"$TARGET/.synctrash/{RUN_ID}/update.bin",
        2,
        "target_expected",
    )
    add(
        (
            "failure.byte-published.update",
            "retry.update-after-backup",
            "retry.control.pause",
            "retry.control.pause-then-cancel",
            "cleanup.ordinary.durable-verdict-plus-cleanup-failure",
        ),
        _UPDATE_BACKUP_PATH,
        1,
        "target_expected",
    )
    add(
        ("resume.pause-same-execution-set",),
        _UPDATE_BACKUP_PATH,
        2,
        "target_expected",
    )
    add(
        (
            "update.backup-state.failure.retained",
            "update.backup-state.failure.unverified",
            "update.backup-state.cancel.retained",
            "update.backup-state.cancel.unverified",
        ),
        _UPDATE_BACKUP_PATH,
        1,
        "target_expected",
        identity=False,
    )
    add(
        (
            "update.backup-state.failure.changed",
            "update.backup-state.cancel.changed",
        ),
        _UPDATE_BACKUP_PATH,
        1,
        "target_expected",
        mtime=False,
        identity=False,
    )

    add(
        ("success.all-nine",),
        f"$TARGET/.synctrash/{RUN_ID}/old.bin",
        4,
        "prior_target_expected",
    )
    add(
        (
            "failure.move-update-new-and-trash",
            "retry.move-update-after-publish",
        ),
        f"$TARGET/.synctrash/{RUN_ID}/old.bin",
        1,
        "prior_target_expected",
    )
    add(
        ("success.all-nine",),
        f"$TARGET/.synctrash/{RUN_ID}/trash.bin",
        7,
        "target_expected",
    )
    add(
        ("failure.nonbyte-commit.trash",),
        f"$TARGET/.synctrash/{RUN_ID}/trash.bin",
        1,
        "target_expected",
    )

    empty_temp = f"$TARGET/copy.bin.synctmp-{RUN_ID}-{1:032x}"
    add(
        (
            "cleanup.ordinary.no-durable-cleanup-failure",
            "cleanup.ordinary.pre-retry-cleanup-fails",
            "cleanup.canceled-failure",
        ),
        empty_temp,
        1,
        "intended",
        mtime=False,
        created=False,
        identity=False,
    )
    add(
        ("cleanup.ordinary.durable-verdict-plus-cleanup-failure",),
        f"$TARGET/update.bin.synctmp-{RUN_ID}-{1:032x}",
        1,
        "intended",
        identity=False,
    )
    return catalog


_TREE_METADATA_RELATIONS = _build_tree_metadata_relations()


def _details(**values: object) -> Mapping[str, object]:
    return values


_EXACT_ITEM_DETAILS: dict[str, tuple[Mapping[str, object], ...]] = {
    "success.all-nine": (
        {},
        _details(backup="hardlink"),
        {},
        {},
        {},
        {},
        {},
        {},
        {},
    ),
    "failure.copy-prepublish-cleanup-ok": (
        _details(error_type="OSError", message="injected copy failure before read"),
    ),
    "failure.move-precommit-unchanged": (
        _details(error_type="OSError", message="injected move failure before commit"),
    ),
    "failure.byte-published.copy": (
        _details(
            durable_state="target-published",
            error_type="OSError",
            message="injected failure after byte publication",
            publish_state="published",
            published_path="copy.bin",
            recording="degraded",
            recording_error="published filesystem mutation failed before ledger settlement",
            target_state="published",
        ),
    ),
    "failure.byte-published.update": (
        _details(
            backup="hardlink",
            backup_metadata="unrepaired",
            backup_path=f".synctrash/{RUN_ID}/update.bin",
            backup_state="retained",
            durable_state="target-published-with-backup",
            error_type="OSError",
            message="injected failure after byte publication",
            publish_state="published",
            published_path="update.bin",
            recording="degraded",
            recording_error="published filesystem mutation failed before ledger settlement",
            target_state="published",
        ),
    ),
    "failure.byte-published.move-update": (
        _details(
            durable_state="new-and-old",
            error_type="OSError",
            message="injected failure after byte publication",
            prior_path="old.bin",
            publish_state="published",
            published_path="renamed.bin",
            recording="degraded",
            recording_error="published filesystem mutation failed before ledger settlement",
            target_state="published",
        ),
    ),
    "failure.byte-published.target-changed": (
        _details(
            durable_state="target-changed-after-publish",
            error_type="OSError",
            message="injected durability failure after byte publication",
            publish_state="published",
            published_path="copy.bin",
            recording="degraded",
            recording_error="published filesystem mutation failed before ledger settlement",
            target_state="changed-after-publish",
        ),
    ),
    "failure.byte-published.target-missing": (
        _details(
            durable_state="target-missing-after-publish",
            error_type="OSError",
            message="injected durability failure after byte publication",
            publish_state="published",
            published_path="copy.bin",
            recording="degraded",
            recording_error="published filesystem mutation failed before ledger settlement",
            target_state="missing-after-publish",
        ),
    ),
    "failure.byte-published.target-unreadable": (
        _details(
            durable_state="target-unverified-after-publish",
            error_type="OSError",
            message="injected durability failure after byte publication",
            publish_state="published",
            published_path="copy.bin",
            recording="degraded",
            recording_error="published filesystem mutation failed before ledger settlement",
            target_state="unverified-after-publish",
            target_state_error="PermissionError: published target probe unavailable",
        ),
    ),
    "failure.nonbyte-commit.move": (
        _details(
            destination_state="reviewed",
            durable_state="target-renamed",
            error_type="OSError",
            message="injected failure after mutation",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
            source_state="absent",
        ),
    ),
    "failure.nonbyte-commit.recase": (
        _details(
            durable_state="recase-state-unverified",
            error_type="OSError",
            message="injected failure after mutation",
            mutation_state="unverified",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
        ),
    ),
    "failure.nonbyte-commit.trash": (
        _details(
            destination_state="reviewed",
            durable_state="target-trashed",
            error_type="OSError",
            message="injected failure after mutation",
            mutation_destination=f".synctrash/{RUN_ID}/trash.bin",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
            source_state="absent",
        ),
    ),
    "failure.nonbyte-commit.delete": (
        _details(
            durable_state="target-deleted",
            error_type="OSError",
            message="injected failure after mutation",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
        ),
    ),
    "failure.nonbyte-commit.mkdir": (
        _details(
            durable_state="directory-created",
            error_type="OSError",
            message="injected failure after mutation",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
        ),
    ),
    "failure.nonbyte-commit.move-restored": (
        _details(
            destination_state="absent",
            durable_state="source-restored-after-move",
            error_type="OSError",
            message="injected failure after restored mutation",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
            source_state="reviewed",
        ),
    ),
    "failure.nonbyte-commit.trash-restored": (
        _details(
            destination_state="absent",
            durable_state="source-restored-after-trash",
            error_type="OSError",
            message="injected failure after restored mutation",
            mutation_destination=f".synctrash/{RUN_ID}/trash.bin",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
            source_state="reviewed",
        ),
    ),
    "failure.nonbyte-commit.delete-restored": (
        _details(
            durable_state="target-restored-after-delete",
            error_type="OSError",
            message="injected failure after restored mutation",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
        ),
    ),
    "failure.nonbyte-unreadable.delete-precommit": (
        _details(
            durable_state="delete-state-unverified",
            error_type="OSError",
            message="injected delete failure before commit",
            mutation_state="unverified",
            mutation_state_error="PermissionError: delete state probe unavailable",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
        ),
    ),
    "update.backup-state.failure.retained": (
        _details(
            backup="copy",
            backup_path=f".synctrash/{RUN_ID}/update.bin",
            backup_state="retained",
            durable_state="backup-retained",
            error_type="PermissionError",
            message="injected update replace failure",
            publish_state="not-published",
        ),
    ),
    "update.backup-state.failure.changed": (
        _details(error_type="PermissionError", message="injected update replace failure"),
    ),
    "update.backup-state.failure.absent": (
        _details(error_type="PermissionError", message="injected update replace failure"),
    ),
    "update.backup-state.failure.unverified": (
        _details(error_type="PermissionError", message="injected update replace failure"),
    ),
    "update.backup-state.cancel.retained": (
        _details(
            backup="copy",
            backup_path=f".synctrash/{RUN_ID}/update.bin",
            backup_state="retained",
            durable_state="backup-retained",
            publish_state="not-published",
            retry_error="injected update replace sharing failure",
            retry_error_type="OSError",
        ),
    ),
    "update.backup-state.cancel.changed": (
        _details(
            backup="copy",
            backup_path=f".synctrash/{RUN_ID}/update.bin",
            backup_state="changed",
            durable_state="target-not-published",
            publish_state="not-published",
            retry_error="injected update replace sharing failure",
            retry_error_type="OSError",
        ),
    ),
    "update.backup-state.cancel.absent": (
        _details(
            backup="copy",
            backup_path=f".synctrash/{RUN_ID}/update.bin",
            backup_state="absent",
            durable_state="target-not-published",
            publish_state="not-published",
            retry_error="injected update replace sharing failure",
            retry_error_type="OSError",
        ),
    ),
    "update.backup-state.cancel.unverified": (
        _details(
            backup="copy",
            backup_path=f".synctrash/{RUN_ID}/update.bin",
            backup_state="unverified",
            backup_state_error="PermissionError: backup probe unavailable",
            durable_state="target-not-published",
            publish_state="not-published",
            retry_error="injected update replace sharing failure",
            retry_error_type="OSError",
        ),
    ),
    "failure.update-sibling.publication-unverified-plus-readonly": (
        _details(
            durable_state="publication-unverified",
            error_type="PermissionError",
            message="injected readonly restoration failure",
            mutation_durable_state="target-metadata-changed-before-publish",
            mutation_state="unverified",
            publish_state="unverified",
            published_path="update.bin",
            recording="degraded",
            recording_error="filesystem mutation may have published but durable state could not be verified",
            state_error="publication-state probe unavailable",
            state_error_type="PermissionError",
        ),
    ),
    "failure.update-sibling.confirmed-publication-suppresses-readonly": (
        _details(
            durable_state="target-published",
            error_type="PermissionError",
            message="post-publication failure",
            publish_state="published",
            published_path="update.bin",
            recording="degraded",
            recording_error="published filesystem mutation failed before ledger settlement",
            target_state="published",
        ),
    ),
    "failure.update-sibling.unchanged-readonly": (
        _details(error_type="PermissionError", message="pre-publication failure"),
    ),
    "failure.update-sibling.unreadable-readonly-mutation": (
        _details(
            durable_state="update-state-unverified",
            error_type="PermissionError",
            message="injected readonly restoration failure",
            mutation_state="unverified",
            mutation_state_error="PermissionError: update state probe unavailable",
            publish_state="not-published",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
        ),
    ),
    "failure.move-update-new-and-trash": (
        _details(
            durable_state="new-and-trash",
            error_type="OSError",
            message="injected failure after move-update trash",
            prior_path="old.bin",
            publish_state="published",
            published_path="renamed.bin",
            recording="degraded",
            recording_error="published filesystem mutation failed before ledger settlement",
            target_state="published",
            trash_path=f".synctrash/{RUN_ID}/old.bin",
        ),
    ),
    "failure.noop-drift": (
        _details(error_type="OperationFailure", message="planned evidence drifted: noop.bin"),
    ),
    "retry.update-after-backup": (_details(backup="hardlink"),),
    "retry.committed-move-settles-once": (
        _details(
            destination_state="reviewed",
            durable_state="target-renamed",
            error_type="OperationFailure",
            message="planned path is missing: old.bin",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
            source_state="absent",
        ),
    ),
    "retry.committed-move-failure-policy-escape": (
        _details(
            destination_state="reviewed",
            durable_state="target-renamed",
            error_type="OSError",
            message="injected committed move failure",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
            source_state="absent",
        ),
    ),
    "retry.committed-move-sleep-escape": (
        _details(
            destination_state="reviewed",
            durable_state="target-renamed",
            error_type="OSError",
            message="injected committed move retry",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
            source_state="absent",
        ),
    ),
    "retry.control.pause": (_details(backup="hardlink"),),
    "retry.control.pause-then-cancel": (
        _details(
            backup="hardlink",
            backup_metadata="unrepaired",
            backup_path=f".synctrash/{RUN_ID}/update.bin",
            backup_state="retained",
            durable_state="backup-retained",
            publish_state="not-published",
            retry_error="retry control failure",
            retry_error_type="OSError",
        ),
    ),
    "cancel.committed-move": (
        _details(
            destination_state="reviewed",
            durable_state="target-renamed",
            error_type="Canceled",
            message="cancellation interrupted settlement after a mutation attempt",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
            source_state="absent",
        ),
    ),
    "cancel.copy-published": (
        _details(
            durable_state="target-published",
            publish_state="published",
            published_path="copy.bin",
            recording="degraded",
            recording_error="cancellation interrupted settlement of a published filesystem mutation",
            target_state="published",
        ),
    ),
    "cancel.update-composed-unverified-plus-readonly": (
        _details(
            durable_state="unverified",
            error_type="PermissionError",
            message="cancellation interrupted settlement after a mutation attempt",
            mutation_durable_state="target-metadata-changed-before-publish",
            mutation_state="unverified",
            publish_state="unverified",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
            retry_error="injected readonly restoration failure",
            retry_error_type="PermissionError",
            state_error="publication-state probe unavailable",
            state_error_type="PermissionError",
        ),
    ),
    "cancel.move-update-partial-publish": (
        _details(
            durable_state="new-and-old",
            prior_path="old.bin",
            publish_state="published",
            published_path="renamed.bin",
            recording="degraded",
            recording_error="cancellation interrupted settlement of a published filesystem mutation",
            target_state="published",
        ),
    ),
    "cleanup.ordinary.no-durable-cleanup-failure": (
        _details(
            error_type="OperationFailure",
            message="operation failed and its owned temp could not be removed: injected temp cleanup failure",
        ),
    ),
    "cleanup.ordinary.pre-retry-cleanup-fails": (
        _details(
            error_type="OperationFailure",
            message="operation failed and its owned temp could not be removed: injected retry cleanup failure",
        ),
    ),
    "cleanup.ordinary.durable-verdict-plus-cleanup-failure": (
        _details(
            backup="hardlink",
            backup_metadata="unrepaired",
            backup_path=f".synctrash/{RUN_ID}/update.bin",
            backup_state="retained",
            cleanup_error="durable cleanup failure",
            durable_state="backup-retained",
            error_type="PermissionError",
            message="update publish failure",
            publish_state="not-published",
        ),
    ),
    "cleanup.canceled-failure": (
        _details(cleanup_error="injected canceled cleanup failure"),
    ),
    "mkdir.primitive-precommit-unchanged": (
        _details(error_type="PermissionError", message="mkdir injected failure"),
    ),
    "mkdir.primitive-commit-then-raise": (
        _details(
            durable_state="directory-present-after-create-attempt",
            error_type="PermissionError",
            message="mkdir injected failure",
            mutation_state="unverified",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
        ),
    ),
    "mkdir.metadata-failure.available-probe": (
        _details(
            durable_state="directory-created",
            error_type="PermissionError",
            message="mkdir metadata failure",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
        ),
    ),
    "mkdir.metadata-failure.unavailable-probe": (
        _details(
            durable_state="mkdir-state-unverified",
            error_type="PermissionError",
            message="mkdir metadata failure",
            mutation_state="committed",
            mutation_state_error="PermissionError: mkdir probe unavailable",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
        ),
    ),
    "mkdir.metadata-failure.disappeared-after-create": (
        _details(
            durable_state="directory-missing-after-create",
            error_type="PermissionError",
            message="mkdir metadata target disappeared",
            mutation_state="committed",
            recording="degraded",
            recording_error="filesystem mutation may have committed before ledger settlement",
        ),
    ),
    "mkdir.pending-child-checkpoint-exception": ({},),
    "mkdir.record-failure": (
        _details(
            recording="degraded",
            recording_error="RuntimeError: injected mkdir recorder failure",
        ),
    ),
    "recording.pre-destructive-flush-refusal": (
        _details(
            error_type="OperationFailure",
            message="recorder flush failed before destructive operation",
        ),
    ),
    "recording.sticky-aggregate-degradation": (
        _details(
            recording="degraded",
            recording_error="RuntimeError: injected copied recorder failure",
        ),
        {},
    ),
    "record.copy-failure": (
        _details(
            recording="degraded",
            recording_error="RuntimeError: injected copied recorder failure",
        ),
    ),
    "record.nonbyte-failure": (
        _details(
            recording="degraded",
            recording_error="RuntimeError: injected moved recorder failure",
        ),
    ),
    "resume.pause-same-execution-set": (
        {},
        _details(backup="hardlink"),
        {},
    ),
    "failure.policy-stop-sweep": (
        _details(error_type="OSError", message="injected copy failure before read"),
        {},
        {},
    ),
}


_RESUME_SAME_EXECUTION_SET = ExpectedSettlement(
    returned=SessionState.COMPLETED.value,
    raised=None,
    recording=RecordingStatus.OK.value,
    items=(
        _item(OperationKind.COPY, Outcome.SUCCEEDED, None),
        _item(OperationKind.UPDATE, Outcome.SUCCEEDED, None),
        _item(OperationKind.COPY, Outcome.SUCCEEDED, None),
    ),
    recorder_commands=("copied", "updated", "copied"),
    evidence_recorded=(True, True, True),
    tree_files=(
        ("$TARGET/first.bin", "first-payload"),
        ("$TARGET/update.bin", "new-version"),
        ("$TARGET/third.bin", "third-payload"),
    ),
    backend_calls=3,
    recorder_flushes=5,
    control_checkpoints=11,
    policy_decisions=("retry",),
    fs_counts=(
        ("open_source", 3),
        ("create_temp", 3),
        ("finalize_temp", 3),
        ("remove_owned_temp", 3),
        ("replace", 2),
        ("publish_new", 2),
        ("hardlink", 1),
    ),
    timeline_subsequence=(
        "backend:copy:2:end",
        "fs:replace:error",
        "failure-policy:00000000000000000000000000000002:attempt:1:decision:retry",
        "control:checkpoint:8:raise:PauseRequested",
        "fs:replace:end",
        "recorder:updated",
        "emit:item:00000000000000000000000000000002:update:succeeded",
        "emit:phase:execute",
        "backend:copy:3:begin",
        "recorder:copied",
        "emit:item:00000000000000000000000000000003:copy:succeeded",
    ),
    row="resume.pause-same-execution-set",
)


_FAILURE_POLICY_STOP = ExpectedSettlement(
    returned=SessionState.FAILED.value,
    raised=None,
    recording=RecordingStatus.OK.value,
    items=(
        _item(OperationKind.COPY, Outcome.FAILED, "io-error"),
        _item(OperationKind.COPY, Outcome.CANCELED, "policy-stop"),
        _item(OperationKind.COPY, Outcome.CANCELED, "policy-stop"),
    ),
    recorder_commands=(),
    backend_calls=1,
    recorder_flushes=1,
    control_checkpoints=4,
    policy_decisions=("stop",),
    fs_counts=(
        ("open_source", 1),
        ("create_temp", 1),
        ("remove_owned_temp", 2),
        ("finalize_temp", 0),
        ("publish_new", 0),
    ),
    timeline_subsequence=(
        "backend:copy:1:error:OSError",
        "failure-policy:00000000000000000000000000000001:attempt:1:decision:stop",
        "fs:remove_owned_temp:end",
        "emit:item:00000000000000000000000000000001:copy:failed",
        "control:checkpoint:3:begin",
        "emit:item:00000000000000000000000000000002:copy:canceled",
        "control:checkpoint:4:begin",
        "emit:item:00000000000000000000000000000003:copy:canceled",
        "recorder:flush",
    ),
    row="failure.policy-stop-sweep",
)


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "success.all-nine",
        frozenset(OperationKind),
        frozenset({"success", "all-operations", "recording"}),
        _success_all_nine,
        (_SUCCESS_ALL_NINE,),
    ),
    Scenario(
        "failure.copy-prepublish-cleanup-ok",
        frozenset({OperationKind.COPY}),
        frozenset({"failure", "byte-effect", "cleanup"}),
        _failure_copy_prepublish,
        (
            ExpectedSettlement(
                SessionState.FAILED.value,
                None,
                RecordingStatus.OK.value,
                (_item(OperationKind.COPY, Outcome.FAILED, "io-error"),),
                (),
                tree_absent=("$TARGET/copy.bin",),
                backend_calls=1,
                policy_decisions=("continue",),
                fs_counts=(("remove_owned_temp", 2),),
                row="failure.copy-prepublish-cleanup-ok",
            ),
        ),
    ),
    Scenario(
        "failure.policy-stop-sweep",
        frozenset({OperationKind.COPY}),
        frozenset({"failure", "stop", "control", "sweep", "dependency"}),
        _failure_policy_stop,
        (_FAILURE_POLICY_STOP,),
    ),
    Scenario(
        "failure.move-precommit-unchanged",
        frozenset({OperationKind.MOVE}),
        frozenset({"failure", "mutation-effect", "unchanged"}),
        _failure_move_precommit,
        (
            ExpectedSettlement(
                SessionState.FAILED.value,
                None,
                RecordingStatus.OK.value,
                (_item(OperationKind.MOVE, Outcome.FAILED, "io-error", absent=("durable_state",)),),
                (),
                tree_files=(("$TARGET/old.bin", "move-payload"),),
                tree_absent=("$TARGET/new.bin",),
                backend_calls=0,
                policy_decisions=("continue",),
                row="failure.move-precommit-unchanged",
            ),
        ),
    ),
    Scenario(
        "failure.byte-published",
        frozenset(_BYTE_KINDS),
        frozenset({"failure", "byte-effect", "published", "matrix"}),
        _failure_byte_published,
        _FAILURE_BYTE_PUBLISHED,
    ),
    Scenario(
        "failure.nonbyte-commit",
        frozenset({OperationKind.MOVE, OperationKind.RECASE, OperationKind.TRASH, OperationKind.DELETE, OperationKind.MKDIR}),
        frozenset({"failure", "mutation-effect", "durable", "matrix"}),
        _failure_nonbyte_commit,
        _FAILURE_NONBYTE_COMMIT,
    ),
    Scenario(
        "update.backup-state-matrix",
        frozenset({OperationKind.UPDATE}),
        frozenset({"failure", "cancel", "byte-effect", "backup", "matrix"}),
        _update_backup_state_matrix,
        _UPDATE_BACKUP_STATE_MATRIX,
    ),
    Scenario(
        "failure.update-sibling-matrix",
        frozenset({OperationKind.UPDATE}),
        frozenset(
            {"failure", "byte-effect", "mutation-effect", "sibling", "matrix"}
        ),
        _update_sibling_matrix,
        _UPDATE_SIBLING_MATRIX,
    ),
    Scenario(
        "failure.move-update-new-and-trash",
        frozenset({OperationKind.MOVE_UPDATE}),
        frozenset({"failure", "byte-effect", "mutation-effect", "composite"}),
        _failure_move_update_trash,
        (
            ExpectedSettlement(
                SessionState.FAILED.value,
                None,
                RecordingStatus.DEGRADED.value,
                (_item(OperationKind.MOVE_UPDATE, Outcome.FAILED, "io-error", detail=(("durable_state", "new-and-trash"),)),),
                (),
                tree_files=(("$TARGET/renamed.bin", "changed-version"),),
                tree_absent=("$TARGET/old.bin",),
                backend_calls=1,
                policy_decisions=("continue",),
                row="failure.move-update-new-and-trash",
            ),
        ),
    ),
    Scenario(
        "failure.noop-drift",
        frozenset({OperationKind.NOOP}),
        frozenset({"failure", "no-effect", "drift"}),
        _failure_noop_drift,
        (
            ExpectedSettlement(
                SessionState.FAILED.value,
                None,
                RecordingStatus.OK.value,
                (_item(OperationKind.NOOP, Outcome.FAILED, "target-drift"),),
                (),
                tree_files=(("$TARGET/noop.bin", "drift"),),
                backend_calls=0,
                policy_decisions=("continue",),
                row="failure.noop-drift",
            ),
        ),
    ),
    Scenario(
        "retry.copy-prepared",
        frozenset({OperationKind.COPY}),
        frozenset({"retry", "byte-effect", "prepared"}),
        _retry_copy_prepared,
        (
            ExpectedSettlement(
                SessionState.COMPLETED.value,
                None,
                RecordingStatus.OK.value,
                (_item(OperationKind.COPY, Outcome.SUCCEEDED, None),),
                ("copied",),
                evidence_recorded=(True,),
                tree_files=(("$TARGET/copy.bin", "copy-payload"),),
                backend_calls=1,
                policy_decisions=("retry",),
                fs_counts=(("publish_new", 2),),
                row="retry.copy-prepared",
            ),
        ),
    ),
    Scenario(
        "retry.copy-published",
        frozenset({OperationKind.COPY}),
        frozenset({"retry", "byte-effect", "published"}),
        _retry_copy_published,
        (
            ExpectedSettlement(
                SessionState.COMPLETED.value,
                None,
                RecordingStatus.OK.value,
                (_item(OperationKind.COPY, Outcome.SUCCEEDED, None),),
                ("copied",),
                evidence_recorded=(True,),
                tree_files=(("$TARGET/copy.bin", "copy-payload"),),
                backend_calls=1,
                policy_decisions=("retry",),
                fs_counts=(("publish_new", 1),),
                row="retry.copy-published",
            ),
        ),
    ),
    Scenario(
        "retry.update-after-backup",
        frozenset({OperationKind.UPDATE}),
        frozenset({"retry", "byte-effect", "backup"}),
        _retry_update_after_backup,
        (
            ExpectedSettlement(
                SessionState.COMPLETED.value,
                None,
                RecordingStatus.OK.value,
                (_item(OperationKind.UPDATE, Outcome.SUCCEEDED, None),),
                ("updated",),
                evidence_recorded=(True,),
                tree_files=(("$TARGET/update.bin", "new-version"),),
                backend_calls=1,
                policy_decisions=("retry",),
                fs_counts=(("replace", 2), ("hardlink", 1)),
                row="retry.update-after-backup",
            ),
        ),
    ),
    Scenario(
        "retry.move-update-after-publish",
        frozenset({OperationKind.MOVE_UPDATE}),
        frozenset({"retry", "byte-effect", "mutation-effect", "published"}),
        _retry_move_update_after_publish,
        (
            ExpectedSettlement(
                SessionState.COMPLETED.value,
                None,
                RecordingStatus.OK.value,
                (_item(OperationKind.MOVE_UPDATE, Outcome.SUCCEEDED, None),),
                ("move_updated",),
                evidence_recorded=(True,),
                tree_files=(("$TARGET/renamed.bin", "changed-version"),),
                tree_absent=("$TARGET/old.bin",),
                backend_calls=1,
                policy_decisions=("retry",),
                fs_counts=(("publish_new", 1), ("rename_new", 2)),
                row="retry.move-update-after-publish",
            ),
        ),
    ),
    Scenario(
        "retry.committed-move-settles-once",
        frozenset({OperationKind.MOVE}),
        frozenset({"retry", "mutation-effect", "durable"}),
        _retry_committed_move,
        (
            ExpectedSettlement(
                SessionState.FAILED.value,
                None,
                RecordingStatus.DEGRADED.value,
                (_item(OperationKind.MOVE, Outcome.FAILED, "target-missing", detail=(("durable_state", "target-renamed"),)),),
                (),
                tree_files=(("$TARGET/new.bin", "move-payload"),),
                backend_calls=0,
                policy_decisions=("retry", "continue"),
                fs_counts=(("rename_new", 1),),
                row="retry.committed-move-settles-once",
            ),
            ExpectedSettlement(
                None,
                "RuntimeError",
                RecordingStatus.DEGRADED.value,
                (_item(
                    OperationKind.MOVE,
                    Outcome.FAILED,
                    "io-error",
                    detail=(("durable_state", "target-renamed"),),
                ),),
                (),
                tree_files=(("$TARGET/new.bin", "move-payload"),),
                backend_calls=0,
                recorder_flushes=2,
                policy_decisions=("raise",),
                fs_counts=(("rename_new", 1),),
                timeline_subsequence=(
                    "fs:rename_new:error",
                    "failure-policy:00000000000000000000000000000001:attempt:1:raise:RuntimeError",
                    "emit:item:00000000000000000000000000000001:move:failed",
                    "recorder:flush",
                ),
                row="retry.committed-move-failure-policy-escape",
            ),
            ExpectedSettlement(
                None,
                "RuntimeError",
                RecordingStatus.DEGRADED.value,
                (_item(
                    OperationKind.MOVE,
                    Outcome.FAILED,
                    "sharing-violation",
                    detail=(("durable_state", "target-renamed"),),
                ),),
                (),
                tree_files=(("$TARGET/new.bin", "move-payload"),),
                backend_calls=0,
                recorder_flushes=2,
                control_checkpoints=2,
                policy_decisions=("retry",),
                fs_counts=(("rename_new", 1),),
                timeline_subsequence=(
                    "failure-policy:00000000000000000000000000000001:attempt:1:decision:retry",
                    "control:checkpoint:2:end",
                    "pacing:sleep:0:raise:RuntimeError",
                    "emit:item:00000000000000000000000000000001:move:failed",
                    "recorder:flush",
                ),
                row="retry.committed-move-sleep-escape",
            ),
        ),
    ),
    Scenario(
        "retry.control-matrix",
        frozenset({OperationKind.UPDATE}),
        frozenset({"retry", "pause", "cancel", "control", "matrix"}),
        _retry_control_matrix,
        _RETRY_CONTROL_MATRIX,
    ),
    Scenario(
        "resume.pause-same-execution-set",
        frozenset({OperationKind.COPY, OperationKind.UPDATE}),
        frozenset({"pause", "resume", "retry", "continuation", "stateful"}),
        _resume_same_execution_set,
        (_RESUME_SAME_EXECUTION_SET,),
    ),
    Scenario(
        "cancel.before-effect-sweep",
        frozenset({OperationKind.COPY, OperationKind.DELETE}),
        frozenset({"cancel", "no-effect", "sweep"}),
        _cancel_before_effect,
        (
            ExpectedSettlement(
                None,
                "Canceled",
                RecordingStatus.OK.value,
                (
                    _item(OperationKind.COPY, Outcome.CANCELED, "canceled"),
                    _item(OperationKind.DELETE, Outcome.CANCELED, "canceled"),
                ),
                (),
                tree_files=(("$TARGET/second.bin", "delete-payload"),),
                tree_absent=("$TARGET/first.bin",),
                backend_calls=0,
                row="cancel.before-effect-sweep",
            ),
        ),
    ),
    Scenario(
        "cancel.copy-prepared",
        frozenset({OperationKind.COPY}),
        frozenset({"cancel", "byte-effect", "prepared", "cleanup"}),
        _cancel_copy_prepared,
        (
            ExpectedSettlement(
                None,
                "Canceled",
                RecordingStatus.OK.value,
                (_item(OperationKind.COPY, Outcome.CANCELED, "canceled"),),
                (),
                tree_absent=("$TARGET/copy.bin",),
                backend_calls=1,
                fs_counts=(("remove_owned_temp", 2),),
                row="cancel.copy-prepared",
            ),
        ),
    ),
    Scenario(
        "cancel.copy-published",
        frozenset({OperationKind.COPY}),
        frozenset({"cancel", "byte-effect", "published"}),
        _cancel_copy_published,
        (
            ExpectedSettlement(
                None,
                "Canceled",
                RecordingStatus.DEGRADED.value,
                (_item(OperationKind.COPY, Outcome.FAILED, "canceled-after-publish", detail=(("durable_state", "target-published"),)),),
                (),
                tree_files=(("$TARGET/copy.bin", "copy-payload"),),
                backend_calls=1,
                row="cancel.copy-published",
            ),
        ),
    ),
    Scenario(
        "cancel.committed-move",
        frozenset({OperationKind.MOVE}),
        frozenset({"cancel", "mutation-effect", "durable"}),
        _cancel_committed_move,
        (
            ExpectedSettlement(
                None,
                "Canceled",
                RecordingStatus.DEGRADED.value,
                (_item(OperationKind.MOVE, Outcome.FAILED, "canceled-after-mutation", detail=(("durable_state", "target-renamed"),)),),
                (),
                tree_files=(("$TARGET/new.bin", "move-payload"),),
                backend_calls=0,
                row="cancel.committed-move",
            ),
        ),
    ),
    Scenario(
        "cancel.update-composed-unverified-plus-readonly",
        frozenset({OperationKind.UPDATE}),
        frozenset({"cancel", "byte-effect", "mutation-effect", "sibling", "unverified"}),
        _cancel_update_composed,
        (
            ExpectedSettlement(
                None,
                "Canceled",
                RecordingStatus.DEGRADED.value,
                (_item(
                    OperationKind.UPDATE,
                    Outcome.FAILED,
                    "canceled-after-mutation",
                    detail=(
                        ("publish_state", "unverified"),
                        ("durable_state", "unverified"),
                        ("mutation_durable_state", "target-metadata-changed-before-publish"),
                    ),
                ),),
                (),
                tree_files=(("$TARGET/update.bin", "old-version"),),
                backend_calls=1,
                policy_decisions=("retry",),
                row="cancel.update-composed-unverified-plus-readonly",
            ),
        ),
    ),
    Scenario(
        "cancel.move-update-partial-publish",
        frozenset({OperationKind.MOVE_UPDATE}),
        frozenset({"cancel", "byte-effect", "mutation-effect", "composite"}),
        _cancel_move_update_partial,
        (
            ExpectedSettlement(
                None,
                "Canceled",
                RecordingStatus.DEGRADED.value,
                (_item(OperationKind.MOVE_UPDATE, Outcome.FAILED, "canceled-after-publish", detail=(("durable_state", "new-and-old"),)),),
                (),
                tree_files=(
                    ("$TARGET/renamed.bin", "changed-version"),
                    ("$TARGET/old.bin", "old-version"),
                ),
                backend_calls=1,
                row="cancel.move-update-partial-publish",
            ),
        ),
    ),
    Scenario(
        "pause.copy-prepared",
        frozenset({OperationKind.COPY}),
        frozenset({"pause", "byte-effect", "prepared", "cleanup"}),
        _pause_copy_prepared,
        (_PAUSE_COPY_PREPARED,),
    ),
    Scenario(
        "cleanup.ordinary-matrix",
        frozenset({OperationKind.COPY, OperationKind.UPDATE}),
        frozenset({"cleanup", "failure", "retry", "durable", "matrix"}),
        _cleanup_ordinary_matrix,
        _CLEANUP_ORDINARY_MATRIX,
    ),
    Scenario(
        "cleanup.canceled-failure",
        frozenset({OperationKind.COPY}),
        frozenset({"cleanup", "cancel", "temp-retained"}),
        _cleanup_canceled_failure,
        (
            ExpectedSettlement(
                None,
                "Canceled",
                RecordingStatus.OK.value,
                (_item(OperationKind.COPY, Outcome.CANCELED, "canceled", detail=(("cleanup_error", "injected canceled cleanup failure"),)),),
                (),
                tree_files=((f"$TARGET/copy.bin.synctmp-{RUN_ID}-{1:032x}", ""),),
                tree_absent=("$TARGET/copy.bin",),
                backend_calls=1,
                fs_counts=(("remove_owned_temp", 2),),
                row="cleanup.canceled-failure",
            ),
        ),
    ),
    Scenario(
        "mkdir.settlement-matrix",
        frozenset({OperationKind.MKDIR, OperationKind.COPY}),
        frozenset(
            {
                "mkdir",
                "failure",
                "mutation-effect",
                "cancel",
                "pause",
                "recording",
                "matrix",
            }
        ),
        _mkdir_matrix,
        _MKDIR_MATRIX,
    ),
    Scenario(
        "recording.flush-and-sticky-matrix",
        frozenset({OperationKind.COPY, OperationKind.MOVE}),
        frozenset(
            {
                "recording",
                "flush",
                "mutation-effect",
                "byte-effect",
                "degraded",
                "matrix",
            }
        ),
        _recording_order_matrix,
        _RECORDING_ORDER_MATRIX,
    ),
    Scenario(
        "record.copy-failure",
        frozenset({OperationKind.COPY}),
        frozenset({"recording", "byte-effect", "degraded"}),
        _record_copy_failure,
        (
            ExpectedSettlement(
                SessionState.COMPLETED.value,
                None,
                RecordingStatus.DEGRADED.value,
                (_item(OperationKind.COPY, Outcome.SUCCEEDED, None, detail=(("recording", "degraded"),)),),
                ("copied",),
                evidence_recorded=(False,),
                tree_files=(("$TARGET/copy.bin", "copy-payload"),),
                backend_calls=1,
                row="record.copy-failure",
            ),
        ),
    ),
    Scenario(
        "record.nonbyte-failure",
        frozenset({OperationKind.MOVE}),
        frozenset({"recording", "mutation-effect", "degraded"}),
        _record_nonbyte_failure,
        (
            ExpectedSettlement(
                SessionState.COMPLETED.value,
                None,
                RecordingStatus.DEGRADED.value,
                (_item(OperationKind.MOVE, Outcome.SUCCEEDED, None, detail=(("recording", "degraded"),)),),
                ("moved",),
                tree_files=(("$TARGET/new.bin", "move-payload"),),
                backend_calls=0,
                recorder_flushes=2,
                timeline_subsequence=("fs:rename_new:end", "recorder:moved"),
                row="record.nonbyte-failure",
            ),
        ),
    ),
)


def _install_source_tree_metadata_relations() -> None:
    """Bind every reviewed source leaf to its immutable plan evidence."""

    for scenario in SCENARIOS:
        for expected in scenario.expected:
            relations = _TREE_METADATA_RELATIONS.setdefault(expected.row, {})
            for operation in _expected_selection_coordinates(expected):
                if operation.kind == OperationKind.MKDIR.value:
                    identity: bool | None = True
                elif operation.kind in _SOURCE_CONTENT:
                    identity = True
                else:
                    continue
                path = f"$SOURCE/{PureWindowsPath(operation.path).as_posix()}"
                if path in relations:
                    raise AuditError(
                        f"duplicate source metadata relation for {expected.row}: {path}"
                    )
                relations[path] = _TreeMetadataRelation(
                    operation.number,
                    "source_expected",
                    True,
                    True,
                    identity,
                )


_install_source_tree_metadata_relations()


_SCENARIO_BY_ID = {scenario.scenario_id: scenario for scenario in SCENARIOS}
_REQUIRED_IDS = frozenset(
    {
        "success.all-nine",
        "failure.copy-prepublish-cleanup-ok",
        "failure.policy-stop-sweep",
        "failure.move-precommit-unchanged",
        "failure.byte-published",
        "failure.nonbyte-commit",
        "update.backup-state-matrix",
        "failure.update-sibling-matrix",
        "failure.move-update-new-and-trash",
        "failure.noop-drift",
        "retry.copy-prepared",
        "retry.copy-published",
        "retry.update-after-backup",
        "retry.move-update-after-publish",
        "retry.committed-move-settles-once",
        "retry.control-matrix",
        "resume.pause-same-execution-set",
        "cancel.before-effect-sweep",
        "cancel.copy-prepared",
        "cancel.copy-published",
        "cancel.committed-move",
        "cancel.update-composed-unverified-plus-readonly",
        "cancel.move-update-partial-publish",
        "pause.copy-prepared",
        "cleanup.ordinary-matrix",
        "cleanup.canceled-failure",
        "mkdir.settlement-matrix",
        "recording.flush-and-sticky-matrix",
        "record.copy-failure",
        "record.nonbyte-failure",
    }
)

_REQUIRED_ROWS = frozenset(
    {
        "success.all-nine",
        "failure.copy-prepublish-cleanup-ok",
        "failure.policy-stop-sweep",
        "failure.move-precommit-unchanged",
        "failure.byte-published.copy",
        "failure.byte-published.update",
        "failure.byte-published.move-update",
        "failure.byte-published.target-changed",
        "failure.byte-published.target-missing",
        "failure.byte-published.target-unreadable",
        "failure.nonbyte-commit.move",
        "failure.nonbyte-commit.recase",
        "failure.nonbyte-commit.trash",
        "failure.nonbyte-commit.delete",
        "failure.nonbyte-commit.mkdir",
        "failure.nonbyte-commit.move-restored",
        "failure.nonbyte-commit.trash-restored",
        "failure.nonbyte-commit.delete-restored",
        "failure.nonbyte-unreadable.delete-precommit",
        "update.backup-state.failure.retained",
        "update.backup-state.failure.changed",
        "update.backup-state.failure.absent",
        "update.backup-state.failure.unverified",
        "update.backup-state.cancel.retained",
        "update.backup-state.cancel.changed",
        "update.backup-state.cancel.absent",
        "update.backup-state.cancel.unverified",
        "failure.update-sibling.publication-unverified-plus-readonly",
        "failure.update-sibling.confirmed-publication-suppresses-readonly",
        "failure.update-sibling.unchanged-readonly",
        "failure.update-sibling.unreadable-readonly-mutation",
        "failure.move-update-new-and-trash",
        "failure.noop-drift",
        "retry.copy-prepared",
        "retry.copy-published",
        "retry.update-after-backup",
        "retry.move-update-after-publish",
        "retry.committed-move-settles-once",
        "retry.committed-move-failure-policy-escape",
        "retry.committed-move-sleep-escape",
        "retry.control.pause",
        "retry.control.pause-then-cancel",
        "resume.pause-same-execution-set",
        "cancel.before-effect-sweep",
        "cancel.copy-prepared",
        "cancel.copy-published",
        "cancel.committed-move",
        "cancel.update-composed-unverified-plus-readonly",
        "cancel.move-update-partial-publish",
        "pause.copy-prepared",
        "cleanup.ordinary.no-durable-cleanup-failure",
        "cleanup.ordinary.stale-owned-temp-recovered",
        "cleanup.ordinary.pre-retry-cleanup-succeeds",
        "cleanup.ordinary.pre-retry-cleanup-fails",
        "cleanup.ordinary.durable-verdict-plus-cleanup-failure",
        "cleanup.canceled-failure",
        "mkdir.primitive-precommit-unchanged",
        "mkdir.primitive-commit-then-raise",
        "mkdir.metadata-failure.available-probe",
        "mkdir.metadata-failure.unavailable-probe",
        "mkdir.metadata-failure.disappeared-after-create",
        "mkdir.pending-child-cancel",
        "mkdir.pending-child-pause",
        "mkdir.pending-child-checkpoint-exception",
        "mkdir.record-failure",
        "recording.pre-destructive-flush-refusal",
        "recording.final-flush-degradation",
        "recording.sticky-aggregate-degradation",
        "record.copy-failure",
        "record.nonbyte-failure",
    }
)


def manifest_errors() -> list[str]:
    errors: list[str] = []
    ids = [scenario.scenario_id for scenario in SCENARIOS]
    if len(ids) != len(set(ids)):
        errors.append("scenario ids are not unique")
    if set(ids) != _REQUIRED_IDS:
        errors.append(
            "scenario manifest differs from its required ids: "
            f"missing={sorted(_REQUIRED_IDS - set(ids))}, "
            f"extra={sorted(set(ids) - _REQUIRED_IDS)}"
        )
    covered = frozenset(kind for scenario in SCENARIOS for kind in scenario.kinds)
    if covered != frozenset(OperationKind):
        errors.append(
            "scenario manifest does not cover every operation kind: "
            f"{sorted(kind.value for kind in frozenset(OperationKind) - covered)}"
        )
    rows: list[str] = []
    for scenario in SCENARIOS:
        if not scenario.expected:
            errors.append(f"{scenario.scenario_id}: has no expected settlement")
        if not scenario.kinds:
            errors.append(f"{scenario.scenario_id}: declares no operation kind")
        if not scenario.tags:
            errors.append(f"{scenario.scenario_id}: declares no coverage tags")
        scenario_rows = [expected.row for expected in scenario.expected]
        rows.extend(scenario_rows)
        if any(not row for row in scenario_rows):
            errors.append(f"{scenario.scenario_id}: has an empty expected row label")
        if len(scenario_rows) != len(set(scenario_rows)):
            errors.append(f"{scenario.scenario_id}: has duplicate expected row labels")
        for expected in scenario.expected:
            try:
                _expected_policy_projection(expected)
            except AuditError as error:
                errors.append(
                    f"{scenario.scenario_id}[{expected.row}]: invalid exact policy: {error}"
                )
    if len(rows) != len(set(rows)):
        errors.append("expected row labels are not globally unique")
    if set(rows) != _REQUIRED_ROWS:
        errors.append(
            "settlement rows differ from their required labels: "
            f"missing={sorted(_REQUIRED_ROWS - set(rows))}, "
            f"extra={sorted(set(rows) - _REQUIRED_ROWS)}"
        )
    row_set = set(rows)
    exact_catalogs = {
        "item details": set(_EXACT_ITEM_DETAILS),
        "item coordinates": set(_ITEM_COORDINATES),
        "selection coordinates": set(_SELECTION_COORDINATES),
        "result bytes": set(_RESULT_BYTES),
        "extra tree files": set(_EXTRA_TREE_FILES),
        "extra tree directories": set(_EXTRA_TREE_DIRECTORIES),
        "extra tree readonly": set(_EXTRA_TREE_READONLY),
        "tree metadata relations": set(_TREE_METADATA_RELATIONS),
        "clock-incidental tree timestamps": set(
            _CLOCK_INCIDENTAL_TREE_TIMESTAMPS
        ),
        "recorder trace schedules": set(_RECORDER_TRACE_SCHEDULES),
    }
    for name, labels in exact_catalogs.items():
        stale = labels - row_set
        if stale:
            errors.append(f"exact {name} contains stale rows: {sorted(stale)}")
    return errors


@dataclass(frozen=True, slots=True)
class Capture:
    scenarios: Mapping[str, object]
    oracle_errors: tuple[str, ...]
    determinism_errors: tuple[str, ...]
    completed_repeats: int
    manifest_complete: bool

    @property
    def ok(self) -> bool:
        return not self.oracle_errors and not self.determinism_errors

    @property
    def baseline_eligible(self) -> bool:
        return (
            self.ok
            and self.completed_repeats >= 3
            and self.manifest_complete is True
            and not manifest_errors()
            and _scenarios_match_manifest(self.scenarios)
        )


def _scenarios_match_manifest(scenarios: Mapping[str, object]) -> bool:
    if tuple(scenarios) != tuple(scenario.scenario_id for scenario in SCENARIOS):
        return False
    for scenario in SCENARIOS:
        report = scenarios.get(scenario.scenario_id)
        if not isinstance(report, Mapping):
            return False
        variants = report.get("variants")
        if not isinstance(variants, list) or len(variants) != len(scenario.expected):
            return False
        rows = [
            variant.get("row") if isinstance(variant, Mapping) else None
            for variant in variants
        ]
        expected_rows = {expected.row for expected in scenario.expected}
        if (
            any(not isinstance(row, str) or not row for row in rows)
            or len(rows) != len(set(rows))
            or set(rows) != expected_rows
        ):
            return False
    return True


def _run_scenario(scenario: Scenario) -> tuple[dict[str, object], list[str]]:
    reports = _run_in_sandbox(scenario.runner)
    errors: list[str] = []
    expected_rows = {expected.row for expected in scenario.expected}
    report_by_row: dict[str, Mapping[str, object]] = {}
    observed_rows: list[str] = []
    for index, report in enumerate(reports):
        row = report.get("row")
        if not isinstance(row, str) or not row:
            errors.append(
                f"{scenario.scenario_id}: report {index} has an empty or invalid row label"
            )
            continue
        observed_rows.append(row)
        if row in report_by_row:
            errors.append(f"{scenario.scenario_id}: duplicate report row {row!r}")
            continue
        report_by_row[row] = report

    missing = expected_rows - set(observed_rows)
    extra = set(observed_rows) - expected_rows
    if missing or extra:
        errors.append(
            f"{scenario.scenario_id}: report rows differ from expected rows: "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )
    for expected in scenario.expected:
        report = report_by_row.get(expected.row)
        if report is None:
            continue
        errors.extend(
            f"{scenario.scenario_id}[{expected.row}]: {error}"
            for error in expected.errors(report)
        )
    return {"variants": reports}, errors


def capture_all(*, repeat: int = 3) -> Capture:
    if repeat <= 0:
        raise AuditError("repeat must be positive")
    first: dict[str, object] = {}
    manifest_issues = manifest_errors()
    oracle_errors: list[str] = list(manifest_issues)
    determinism_errors: list[str] = []
    canonical: dict[str, str] = {}
    completed_repeats = 0
    for iteration in range(1, repeat + 1):
        for scenario in SCENARIOS:
            report, errors = _run_scenario(scenario)
            oracle_errors.extend(errors)
            encoded = _canonical(report)
            if iteration == 1:
                first[scenario.scenario_id] = report
                canonical[scenario.scenario_id] = encoded
            elif encoded != canonical[scenario.scenario_id]:
                previous = first[scenario.scenario_id]
                difference = _first_difference(previous, report)
                determinism_errors.append(
                    f"{scenario.scenario_id}: run {iteration} differs at {difference}"
                )
        completed_repeats += 1
    return Capture(
        scenarios=first,
        oracle_errors=tuple(dict.fromkeys(oracle_errors)),
        determinism_errors=tuple(dict.fromkeys(determinism_errors)),
        completed_repeats=completed_repeats,
        manifest_complete=not manifest_issues and _scenarios_match_manifest(first),
    )


def capture_one(scenario_id: str, *, repeat: int = 1) -> Capture:
    try:
        scenario = _SCENARIO_BY_ID[scenario_id]
    except KeyError:
        raise AuditError(f"unknown scenario: {scenario_id}") from None
    if repeat <= 0:
        raise AuditError("repeat must be positive")
    first: dict[str, object] = {}
    oracle_errors: list[str] = []
    determinism_errors: list[str] = []
    canonical: str | None = None
    first_report: object = None
    completed_repeats = 0
    for iteration in range(1, repeat + 1):
        report, errors = _run_scenario(scenario)
        oracle_errors.extend(errors)
        encoded = _canonical(report)
        if iteration == 1:
            first[scenario_id] = report
            first_report = report
            canonical = encoded
        elif encoded != canonical:
            determinism_errors.append(
                f"{scenario_id}: run {iteration} differs at "
                f"{_first_difference(first_report, report)}"
            )
        completed_repeats += 1
    return Capture(
        first,
        tuple(dict.fromkeys(oracle_errors)),
        tuple(dict.fromkeys(determinism_errors)),
        completed_repeats,
        False,
    )


def _manifest_payload() -> list[dict[str, object]]:
    return [
        {
            "id": scenario.scenario_id,
            "kinds": sorted(kind.value for kind in scenario.kinds),
            "tags": sorted(scenario.tags),
            "variants": len(scenario.expected),
            "rows": [expected.row for expected in scenario.expected],
        }
        for scenario in SCENARIOS
    ]


def _validate_baseline_capture(capture: Capture) -> None:
    if (
        isinstance(capture.completed_repeats, bool)
        or not isinstance(capture.completed_repeats, int)
        or capture.completed_repeats < 3
    ):
        raise AuditError("snapshot requires at least three completed repeats")
    if not capture.ok:
        raise AuditError("snapshot refused because oracle or determinism checks failed")
    if (
        capture.manifest_complete is not True
        or manifest_errors()
        or not _scenarios_match_manifest(capture.scenarios)
    ):
        raise AuditError("snapshot requires one complete current scenario manifest")


def _baseline_payload(capture: Capture) -> dict[str, object]:
    _validate_baseline_capture(capture)
    return {
        "format_version": FORMAT_VERSION,
        "repeat": capture.completed_repeats,
        "manifest": _manifest_payload(),
        "scenarios": copy.deepcopy(capture.scenarios),
    }


def _canonical(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except ValueError as error:
        raise AuditError(f"capture contains a non-finite JSON number: {error}") from error


def _first_difference(expected: object, actual: object, path: str = "$") -> str:
    if type(expected) is not type(actual):
        return path
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        expected_keys = set(expected)
        actual_keys = set(actual)
        if expected_keys != actual_keys:
            key = sorted(expected_keys ^ actual_keys, key=str)[0]
            return f"{path}.{key}"
        for key in sorted(expected_keys, key=str):
            if expected[key] != actual[key]:
                return _first_difference(expected[key], actual[key], f"{path}.{key}")
        return path
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return f"{path}.length"
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            if left != right:
                return _first_difference(left, right, f"{path}[{index}]")
        return path
    return path


class _DuplicateJsonMember(ValueError):
    pass


class _NonJsonConstant(ValueError):
    pass


class _NonFiniteJsonNumber(ValueError):
    pass


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonMember(key)
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise _NonJsonConstant(value)


def _strict_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _NonFiniteJsonNumber(value)
    return parsed


def _parse_baseline(text: str, source: str) -> Mapping[str, object]:
    try:
        data = json.loads(
            text,
            object_pairs_hook=_strict_json_object,
            parse_constant=_reject_json_constant,
            parse_float=_strict_json_float,
        )
    except _DuplicateJsonMember as error:
        raise AuditError(
            f"settlement baseline contains duplicate JSON member: {error}"
        ) from error
    except _NonJsonConstant as error:
        raise AuditError(
            f"settlement baseline contains non-standard JSON constant: {error}"
        ) from error
    except _NonFiniteJsonNumber as error:
        raise AuditError(
            f"settlement baseline contains non-finite JSON number: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise AuditError(f"cannot read settlement baseline {source}: {error}") from error
    if not isinstance(data, Mapping):
        raise AuditError("settlement baseline root must be an object")
    required = {"format_version", "repeat", "manifest", "scenarios"}
    if set(data) != required:
        raise AuditError(
            "settlement baseline fields differ from the exact schema: "
            f"{sorted(data)}"
        )
    format_version = data.get("format_version")
    if isinstance(format_version, bool) or not isinstance(format_version, int):
        raise AuditError("settlement baseline format version must be an integer")
    if format_version != FORMAT_VERSION:
        raise AuditError(
            f"unsupported settlement baseline version: {format_version!r}"
        )
    repeat = data.get("repeat")
    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 3:
        raise AuditError(
            "settlement baseline repeat must be an integer of at least three"
        )
    if not isinstance(data.get("manifest"), list) or not isinstance(
        data.get("scenarios"), Mapping
    ):
        raise AuditError("settlement baseline manifest/scenarios have the wrong type")
    return data


def _read_baseline(path: Path) -> Mapping[str, object]:
    if not path.is_file():
        raise AuditError(
            f"settlement baseline is missing: {path}; snapshot the corrected "
            "committed monolith before restructuring"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise AuditError(f"cannot read settlement baseline {path}: {error}") from error
    return _parse_baseline(text, str(path))


def _is_default_baseline(path: Path) -> bool:
    return os.path.normcase(str(path.resolve())) == os.path.normcase(
        str(DEFAULT_BASELINE.resolve())
    )


def _run_git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ("git", *arguments),
            cwd=_REPOSITORY_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        raise AuditError(
            f"cannot inspect committed settlement baseline: {error}"
        ) from error


def _read_reviewed_committed_baseline() -> Mapping[str, object]:
    cleanliness_checks = (
        (
            "staged",
            (
                "diff",
                "--cached",
                "--quiet",
                "HEAD",
                "--",
                _DEFAULT_BASELINE_GIT_PATH,
            ),
        ),
        (
            "unstaged",
            ("diff", "--quiet", "--", _DEFAULT_BASELINE_GIT_PATH),
        ),
    )
    for label, arguments in cleanliness_checks:
        dirty = _run_git(*arguments)
        if dirty.returncode == 1:
            raise AuditError(
                f"default settlement baseline has {label} changes; the official "
                "check requires the reviewed baseline to be committed and clean"
            )
        if dirty.returncode != 0:
            message = dirty.stderr.decode("utf-8", errors="replace").strip()
            raise AuditError(
                "cannot inspect committed settlement baseline"
                + (f": {message}" if message else "")
            )

    committed = _run_git("show", f"HEAD:{_DEFAULT_BASELINE_GIT_PATH}")
    if committed.returncode != 0:
        message = committed.stderr.decode("utf-8", errors="replace").strip()
        raise AuditError(
            "cannot read committed settlement baseline"
            + (f": {message}" if message else "")
        )
    try:
        text = committed.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AuditError(
            "cannot read committed settlement baseline as UTF-8"
        ) from error
    baseline = _parse_baseline(text, f"HEAD:{_DEFAULT_BASELINE_GIT_PATH}")
    observed_digest = hashlib.sha256(
        _canonical(baseline).encode("utf-8")
    ).hexdigest()
    if observed_digest != REVIEWED_BASELINE_SHA256:
        raise AuditError(
            "committed settlement baseline is not the reviewed baseline: "
            f"expected semantic SHA-256 {REVIEWED_BASELINE_SHA256}, "
            f"observed {observed_digest}"
        )
    return baseline


def _baseline_differences(
    baseline: Mapping[str, object], capture: Capture
) -> list[str]:
    differences: list[str] = []
    expected_manifest = baseline.get("manifest")
    actual_manifest = _manifest_payload()
    manifest_difference = _first_strict_difference(
        expected_manifest, actual_manifest
    )
    if manifest_difference is not None:
        differences.append(
            "manifest differs at " + manifest_difference
        )
    expected_scenarios = baseline.get("scenarios")
    scenario_difference = _first_strict_difference(
        expected_scenarios, capture.scenarios
    )
    if scenario_difference is not None:
        differences.append(
            "scenario trace differs at " + scenario_difference
        )
    return differences


def _write_baseline(
    path: Path,
    capture: Capture,
    *,
    replace_existing: bool,
) -> None:
    payload_object = _baseline_payload(capture)
    if not path.parent.is_dir():
        raise AuditError(f"settlement baseline parent does not exist: {path.parent}")
    try:
        payload = json.dumps(
            payload_object,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ) + "\n"
    except ValueError as error:
        raise AuditError(
            f"settlement baseline contains a non-finite JSON number: {error}"
        ) from error
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if replace_existing:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise AuditError(
                    f"settlement baseline collision: {path}; "
                    "replacement requires --replace"
                ) from error
            temporary.unlink()
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _print_errors(capture: Capture) -> None:
    for error in capture.oracle_errors:
        print(f"oracle: {error}")
    for error in capture.determinism_errors:
        print(f"determinism: {error}")


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.executor_settlement_audit",
        description="Independent executor settlement oracle and retained trace.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the complete scenario manifest")
    run = commands.add_parser("run", help="run and print one scenario")
    run.add_argument("scenario_id")
    run.add_argument("--repeat", type=_positive_int, default=1)
    oracle = commands.add_parser("oracle", help="check independent policy expectations")
    oracle.add_argument("--repeat", type=_positive_int, default=3)
    snapshot = commands.add_parser("snapshot", help="write a corrected baseline")
    snapshot.add_argument("--repeat", type=_positive_int, default=3)
    snapshot.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    snapshot.add_argument("--replace", action="store_true")
    diff = commands.add_parser("diff", help="compare current traces with the baseline")
    diff.add_argument("--repeat", type=_positive_int, default=3)
    diff.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    check = commands.add_parser("check", help="require oracle, stability, and baseline parity")
    check.add_argument("--repeat", type=_positive_int, default=3)
    check.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "list":
            for scenario in SCENARIOS:
                kinds = ",".join(sorted(kind.value for kind in scenario.kinds))
                tags = ",".join(sorted(scenario.tags))
                print(f"{scenario.scenario_id}\t{kinds}\t{tags}")
            return 0
        if args.command == "run":
            capture = capture_one(args.scenario_id, repeat=args.repeat)
            print(
                json.dumps(
                    capture.scenarios[args.scenario_id],
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
            )
            _print_errors(capture)
            return 0 if capture.ok else 1

        if args.command in {"snapshot", "check"} and args.repeat < 3:
            raise AuditError(f"{args.command} requires at least three repeats")
        baseline: Mapping[str, object] | None = None
        official_check = args.command == "check" and _is_default_baseline(
            args.baseline
        )
        if args.command == "check":
            baseline = (
                _read_reviewed_committed_baseline()
                if official_check
                else _read_baseline(args.baseline)
            )
        capture = capture_all(repeat=args.repeat)
        if args.command == "oracle":
            _print_errors(capture)
            if capture.ok:
                print(f"oracle passed: {len(SCENARIOS)} scenarios x {args.repeat} runs")
            return 0 if capture.ok else 1
        if args.command == "snapshot":
            _print_errors(capture)
            _write_baseline(
                args.baseline,
                capture,
                replace_existing=args.replace,
            )
            print(f"wrote settlement baseline: {args.baseline}")
            return 0

        if baseline is None:
            baseline = _read_baseline(args.baseline)
        differences = _baseline_differences(baseline, capture)
        if args.command == "diff":
            for difference in differences:
                print(f"diff: {difference}")
            for error in capture.determinism_errors:
                print(f"determinism: {error}")
            if not differences and not capture.determinism_errors:
                print("settlement baseline matches")
            return 0 if not differences and not capture.determinism_errors else 1
        _print_errors(capture)
        for difference in differences:
            print(f"diff: {difference}")
        if capture.ok and not differences:
            if official_check:
                print(
                    "settlement check passed: "
                    f"{len(SCENARIOS)} scenarios x {args.repeat} runs"
                )
            else:
                print(
                    "unpinned custom-baseline diagnostic passed: "
                    f"{len(SCENARIOS)} scenarios x {args.repeat} runs"
                )
            return 0
        return 1
    except AuditError as error:
        print(f"error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
