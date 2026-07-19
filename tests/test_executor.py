"""M0 executor acceptance and PoC-regression tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from typing import Callable

import pytest

from namisync.core.evidence import Outcome, Provenance, RecordingStatus
from namisync.core.events import ItemOutcome, Progress, Terminal
from namisync.core.execution import ExecutionSet, RunId, validated_run_id
from namisync.core.models import CapabilityProfile, EntryKind, FileStat, IgnoreSet, Root
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
from namisync.core.session import Canceled, PauseRequested, RunContext, SessionState
from namisync.modules.executor import (
    BoundedFailurePolicy,
    ExecutorPolicies,
    NativeCopyBackend,
    NativeFileSystem,
    SystemClock,
    UnsafeExecutionPath,
    execute,
)
from namisync.modules.scanner import scan


RUN_ID = validated_run_id("1" * 32)


class FakeRecorder:
    def __init__(self, *, fail: str | None = None) -> None:
        self.fail = fail
        self.calls: list[tuple[str, object, object | None]] = []
        self.flushes = 0

    def _record(self, name: str, first: object, second: object | None = None) -> None:
        if self.fail == name:
            raise RuntimeError(f"injected {name} failure")
        self.calls.append((name, first, second))

    def flush(self) -> None:
        self.flushes += 1
        if self.fail == "flush":
            raise RuntimeError("injected flush failure")

    def record_copied(self, op, attestation) -> None:
        self._record("copied", op, attestation)

    def record_updated(self, op, attestation) -> None:
        self._record("updated", op, attestation)

    def record_moved(self, op, target) -> None:
        self._record("moved", op, target)

    def record_move_updated(self, op, attestation) -> None:
        self._record("move_updated", op, attestation)

    def record_mkdir(self, op, target) -> None:
        self._record("mkdir", op, target)

    def record_trashed(self, op, trash_relative_path, target) -> None:
        self._record("trashed", op, (trash_relative_path, target))

    def record_deleted(self, op, prior) -> None:
        self._record("deleted", op, prior)

    def record_noop(self, op, source, target) -> None:
        self._record("noop", op, (source, target))


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 7, 18, 12, tzinfo=UTC)


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
            0
            if source_expected is None
            or kind not in {OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE}
            else source_expected.size
        ),
        dependencies=dependencies,
        reason=OperationReason.SOURCE_ONLY,
    )


def _plan(
    source: Path,
    target: Path,
    operations: tuple[PlanOperation, ...],
    *,
    hardlinks: bool = True,
    preservation: PreservationPolicy = PreservationPolicy(),
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
        preservation=preservation,
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=trash_on_update,
        policy_fingerprint="p" * 64,
        worker_count=1,
        required_volumes=frozenset(),
        required_bytes=sum(operation.content_bytes for operation in operations),
        fingerprint=PlanFingerprint("f" * 64),
    )


def _xset(plan: Plan) -> ExecutionSet:
    return ExecutionSet(
        plan=plan,
        selection=frozenset(operation.op_id for operation in plan.operations),
        run_id=RUN_ID,
    )


def _policies(**changes: object) -> ExecutorPolicies:
    values: dict[str, object] = {
        "failure": BoundedFailurePolicy(retries=2, initial_delay=0),
        "copy_backend": NativeCopyBackend(),
        "clock": FixedClock(),
        "chunk_size": 4,
        "progress_interval_seconds": 0,
        "sleep": lambda _: None,
    }
    values.update(changes)
    return ExecutorPolicies(**values)  # type: ignore[arg-type]


def _run(
    xset: ExecutionSet,
    *,
    fs: NativeFileSystem | None = None,
    recorder: FakeRecorder | None = None,
    policies: ExecutorPolicies | None = None,
    checkpoint: Callable[[], None] = lambda: None,
) -> tuple[object, list[object], FakeRecorder]:
    events: list[object] = []
    actual_recorder = recorder or FakeRecorder()
    result = execute(
        xset,
        RunContext(events.append, checkpoint),
        actual_recorder,
        policies or _policies(),
        fs or NativeFileSystem(),
    )
    return result, events, actual_recorder


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    return source, target


def test_copy_is_atomic_hashed_and_attested_to_published_target(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"complete-content")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, events, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert result.bytes_total == len(b"complete-content")
    assert (target / "file.bin").read_bytes() == b"complete-content"
    assert not list(target.glob("*.synctmp-*"))
    name, _, attestation = recorder.calls[0]
    assert name == "copied"
    assert attestation.content.digest == hashlib.sha256(b"complete-content").digest()
    assert attestation.content.provenance is Provenance.COPY_ATTESTED
    assert attestation.content.observed_at == FixedClock().now()
    assert attestation.subject.file_identity != source_stat.file_identity
    progress = [event for event in events if isinstance(event, Progress)]
    assert [event.bytes_done for event in progress] == sorted(
        event.bytes_done for event in progress
    )
    assert max(event.bytes_done for event in progress) == len(b"complete-content")
    assert not any(isinstance(event, Terminal) for event in events)


def test_executor_live_stat_matches_native_scanner_evidence(tmp_path: Path) -> None:
    source, _ = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"evidence")
    scanned = scan(
        Root(str(source), "source"),
        IgnoreSet(),
        RunContext(lambda _: None, lambda: None),
    )

    assert scanned.complete
    assert len(scanned.files) == 1
    actual = NativeFileSystem().stat(source, "file.bin")
    assert actual is not None
    assert replace(actual, file_identity=scanned.files[0].stat.file_identity) == scanned.files[0].stat


class MutatingBackend(NativeCopyBackend):
    def __init__(self, source: Path) -> None:
        self.source = source

    def copy(self, *args, **kwargs):
        digest = super().copy(*args, **kwargs)
        self.source.write_bytes(b"drifted-source")
        return digest


def test_source_drift_after_stream_removes_temp_and_records_nothing(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    path = source / "file.bin"
    path.write_bytes(b"original")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(copy_backend=MutatingBackend(path)),
    )

    assert result.status is SessionState.FAILED
    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    assert recorder.calls == []
    outcome = next(event for event in events if isinstance(event, ItemOutcome))
    assert outcome.reason == "source-drift"


class AppearanceFileSystem(NativeFileSystem):
    def publish_new(self, temp: Path, target: Path) -> None:
        target.write_bytes(b"external")
        super().publish_new(temp, target)


def test_conditional_publish_does_not_overwrite_target_appearance(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"planned")
    fs = AppearanceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "file.bin").read_bytes() == b"external"
    assert recorder.calls == []


def test_exact_temp_recovery_preserves_user_lookalike(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    exact = fs.owned_temp(target / "file.bin", RUN_ID, operation.op_id)
    exact.write_bytes(b"orphan")
    lookalike = target / "notes.synctmp-user.txt"
    lookalike.write_bytes(b"user")

    result, _, _ = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert not exact.exists()
    assert lookalike.read_bytes() == b"user"


@pytest.mark.parametrize("hardlinks", [True, False])
def test_update_preserves_displaced_version_before_replace(
    tmp_path: Path, hardlinks: bool
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=hardlinks)), fs=fs
    )

    assert result.status is SessionState.COMPLETED
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert recorder.calls[0][0] == "updated"
    assert result.bytes_total == len(b"new-version")


def test_no_hardlink_update_flushes_readonly_backup_before_readonly(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    live = target / "file.bin"
    live.write_bytes(b"old")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    old = fs.stat(target, "file.bin")
    assert source_stat is not None and old is not None
    fs.apply_metadata(
        live,
        replace(old, metadata=replace(old.metadata, attributes=old.metadata.attributes | 1)),
        preserve_created=True,
        apply_readonly=True,
    )
    old = fs.stat(target, "file.bin")
    assert old is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=old,
        intended=source_stat,
    )

    result, _, _ = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)), fs=fs
    )

    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    trash_stat = fs.stat_path(trash)
    assert result.status is SessionState.COMPLETED
    assert trash.read_bytes() == b"old"
    assert trash_stat is not None and trash_stat.metadata.attributes & 1


class ReplaceFaultFileSystem(NativeFileSystem):
    def __init__(self, *, after: bool) -> None:
        self.after = after

    def replace(self, temp: Path, target: Path) -> None:
        if self.after:
            super().replace(temp, target)
        raise OSError("injected replace fault")


@pytest.mark.parametrize("after", [False, True])
def test_update_fault_never_leaves_live_target_absent(tmp_path: Path, after: bool) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceFaultFileSystem(after=after)
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "file.bin").read_bytes() == (
        b"new-version" if after else b"old-version"
    )
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert recorder.calls == []


class AclFailureFileSystem(NativeFileSystem):
    def copy_security(self, source: Path, target: Path) -> None:
        raise PermissionError("ACL copy denied")


def test_acl_failure_happens_before_update_publish(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    (target / "file.bin").write_bytes(b"old")
    fs = AclFailureFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    plan = _plan(
        source,
        target,
        (operation,),
        preservation=PreservationPolicy(preserve_acl=True),
    )

    result, events, recorder = _run(_xset(plan), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "file.bin").read_bytes() == b"old"
    assert recorder.calls == []
    assert next(event for event in events if isinstance(event, ItemOutcome)).reason == "acl-copy-failed"


def test_failed_work_does_not_abort_independent_and_defers_dependents(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "missing.bin").write_bytes(b"gone")
    (source / "good.bin").write_bytes(b"good")
    fs = NativeFileSystem()
    missing_stat = fs.stat(source, "missing.bin")
    good_stat = fs.stat(source, "good.bin")
    assert missing_stat is not None and good_stat is not None
    first = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="missing.bin",
        target_rel_path="missing.bin",
        source_expected=missing_stat,
        target_expected=None,
        intended=missing_stat,
    )
    second = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="good.bin",
        target_rel_path="good.bin",
        source_expected=good_stat,
        target_expected=None,
        intended=good_stat,
    )
    dependent = _operation(
        3,
        OperationKind.NOOP,
        source_rel_path="missing.bin",
        target_rel_path="missing.bin",
        source_expected=missing_stat,
        target_expected=missing_stat,
        intended=missing_stat,
        dependencies=(first.op_id,),
    )
    (source / "missing.bin").unlink()

    xset = _xset(_plan(source, target, (first, second, dependent)))
    result, _, recorder = _run(xset, fs=fs)

    assert result.status is SessionState.FAILED
    assert xset.status == {
        first.op_id: Outcome.FAILED,
        second.op_id: Outcome.SUCCEEDED,
        dependent.op_id: Outcome.DEFERRED,
    }
    assert (target / "good.bin").read_bytes() == b"good"
    assert [call[0] for call in recorder.calls] == ["copied"]


def test_directory_metadata_is_applied_after_child_operation(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "folder").mkdir()
    (source / "folder" / "file.bin").write_bytes(b"child")

    class LoggingFileSystem(NativeFileSystem):
        def __init__(self) -> None:
            self.metadata_paths: list[Path] = []

        def apply_metadata(self, path: Path, *args, **kwargs) -> None:
            self.metadata_paths.append(path)
            super().apply_metadata(path, *args, **kwargs)

    fs = LoggingFileSystem()
    dir_stat = fs.stat(source, "folder")
    file_stat = fs.stat(source, "folder\\file.bin")
    assert dir_stat is not None and file_stat is not None
    mkdir = _operation(
        1,
        OperationKind.MKDIR,
        source_rel_path="folder",
        target_rel_path="folder",
        source_expected=dir_stat,
        target_expected=None,
        intended=dir_stat,
    )
    copy = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="folder\\file.bin",
        target_rel_path="folder\\file.bin",
        source_expected=file_stat,
        target_expected=None,
        intended=file_stat,
        dependencies=(mkdir.op_id,),
    )

    result, _, recorder = _run(_xset(_plan(source, target, (mkdir, copy))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.metadata_paths.index(target / "folder" / "file.bin") < fs.metadata_paths.index(
        target / "folder"
    )
    assert [call[0] for call in recorder.calls] == ["copied", "mkdir"]


def test_explicit_directory_chain_supports_long_destination_path(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    first_name = "a" * 150
    second_name = "b" * 100
    source_first = source / first_name
    source_second = source_first / second_name
    source_second.mkdir(parents=True)
    (source_second / "file.bin").write_bytes(b"long-path")
    first_rel = first_name
    second_rel = f"{first_name}\\{second_name}"
    file_rel = f"{second_rel}\\file.bin"
    fs = NativeFileSystem()
    first_stat = fs.stat(source, first_rel)
    second_stat = fs.stat(source, second_rel)
    file_stat = fs.stat(source, file_rel)
    assert first_stat is not None and second_stat is not None and file_stat is not None
    first = _operation(
        1,
        OperationKind.MKDIR,
        source_rel_path=first_rel,
        target_rel_path=first_rel,
        source_expected=first_stat,
        target_expected=None,
        intended=first_stat,
    )
    second = _operation(
        2,
        OperationKind.MKDIR,
        source_rel_path=second_rel,
        target_rel_path=second_rel,
        source_expected=second_stat,
        target_expected=None,
        intended=second_stat,
        dependencies=(first.op_id,),
    )
    copy = _operation(
        3,
        OperationKind.COPY,
        source_rel_path=file_rel,
        target_rel_path=file_rel,
        source_expected=file_stat,
        target_expected=None,
        intended=file_stat,
        dependencies=(second.op_id,),
    )

    result, _, _ = _run(_xset(_plan(source, target, (first, second, copy))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert (target / first_name / second_name / "file.bin").read_bytes() == b"long-path"


def test_nonempty_directory_delete_refuses_without_recursive_removal(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (target / "folder").mkdir()
    (target / "folder" / "child.txt").write_text("keep", encoding="utf-8")
    fs = NativeFileSystem()
    directory_stat = fs.stat(target, "folder")
    assert directory_stat is not None and directory_stat.kind is EntryKind.DIRECTORY
    operation = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="folder",
        source_expected=None,
        target_expected=directory_stat,
        intended=None,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "folder" / "child.txt").read_text(encoding="utf-8") == "keep"
    assert recorder.calls == []


def test_noop_drift_does_not_refresh_recorder_evidence(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"same")
    (target / "file.bin").write_bytes(b"same")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.NOOP,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=target_stat,
    )
    (target / "file.bin").write_bytes(b"drift")

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert recorder.calls == []


class CountingCheckpoint:
    def __init__(self, error: type[Exception], at: int) -> None:
        self.error = error
        self.at = at
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1
        if self.calls == self.at:
            raise self.error()


@pytest.mark.parametrize("control", [Canceled, PauseRequested])
def test_copy_control_unwinds_within_one_chunk_and_cleans_temp(
    tmp_path: Path, control: type[Exception]
) -> None:
    source, target = _roots(tmp_path)
    (source / "large.bin").write_bytes(b"x" * 32)
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "large.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="large.bin",
        target_rel_path="large.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    checkpoint = CountingCheckpoint(control, at=3)
    events: list[object] = []

    with pytest.raises(control):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(chunk_size=4),
            fs,
        )

    assert not (target / "large.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    assert not any(isinstance(event, Terminal) for event in events)
    if control is Canceled:
        assert xset.status[operation.op_id] is Outcome.CANCELED
    else:
        assert operation.op_id not in xset.status


class InterruptingBackend(NativeCopyBackend):
    def copy(self, _source, target, **_kwargs):
        target.write(b"partial")
        raise KeyboardInterrupt()


def test_unexpected_base_exception_cleans_owned_temp_before_propagating(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"complete")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()

    with pytest.raises(KeyboardInterrupt):
        execute(
            xset,
            RunContext(lambda _: None, lambda: None),
            recorder,
            _policies(copy_backend=InterruptingBackend()),
            fs,
        )

    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    assert operation.op_id not in xset.status
    assert recorder.calls == []
    assert recorder.flushes == 1


class SharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def publish_new(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        if self.attempts == 1:
            error = OSError("sharing violation")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        super().publish_new(temp, target)


def test_transient_sharing_violation_retries_within_bound(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"retry")
    fs = SharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, _, _ = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 2
    assert (target / "file.bin").read_bytes() == b"retry"


class ReplaceSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def replace(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        if self.attempts == 1:
            error = OSError("sharing violation during replace")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        super().replace(temp, target)


@pytest.mark.parametrize("hardlinks", [True, False])
def test_update_retries_replace_without_restarting_after_backup(
    tmp_path: Path, hardlinks: bool
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=hardlinks)), fs=fs
    )

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 2
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert [call[0] for call in recorder.calls] == ["updated"]


class ReplaceSharingAfterCommitFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def replace(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        super().replace(temp, target)
        error = OSError("sharing report after committed replace")
        error.winerror = 32  # type: ignore[attr-defined]
        raise error


def test_update_retry_recognizes_replace_that_committed_before_error(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingAfterCommitFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 1
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert [call[0] for call in recorder.calls] == ["updated"]


class BackupSharingAfterCommitFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def copy_backup(self, source, temp, target, checkpoint) -> None:
        self.attempts += 1
        super().copy_backup(source, temp, target, checkpoint)
        error = OSError("sharing report after committed backup")
        error.winerror = 32  # type: ignore[attr-defined]
        raise error


def test_update_retry_recognizes_committed_copy_backup(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = BackupSharingAfterCommitFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)), fs=fs
    )

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 1
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert [call[0] for call in recorder.calls] == ["updated"]


class ReplaceSharingAlwaysFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def replace(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        error = OSError("persistent replace sharing violation")
        error.winerror = 32  # type: ignore[attr-defined]
        raise error


def test_persistent_update_sharing_exhausts_policy_without_false_drift(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingAlwaysFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    outcome = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert fs.attempts == 3
    assert outcome.reason == "sharing-violation"
    assert (target / "file.bin").read_bytes() == b"old-version"
    assert recorder.calls == []


class PersistentSharingFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def publish_new(self, temp: Path, target: Path) -> None:
        if target.name == "locked.bin":
            self.attempts += 1
            error = OSError("persistent sharing violation")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        super().publish_new(temp, target)


def test_persistent_sharing_is_bounded_and_independent_work_continues(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "locked.bin").write_bytes(b"locked")
    (source / "free.bin").write_bytes(b"free")
    fs = PersistentSharingFileSystem()
    locked_stat = fs.stat(source, "locked.bin")
    free_stat = fs.stat(source, "free.bin")
    assert locked_stat is not None and free_stat is not None
    locked = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="locked.bin",
        target_rel_path="locked.bin",
        source_expected=locked_stat,
        target_expected=None,
        intended=locked_stat,
    )
    free = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="free.bin",
        target_rel_path="free.bin",
        source_expected=free_stat,
        target_expected=None,
        intended=free_stat,
    )

    result, events, _ = _run(_xset(_plan(source, target, (locked, free))), fs=fs)

    assert result.status is SessionState.FAILED
    assert fs.attempts == 3
    assert not (target / "locked.bin").exists()
    assert (target / "free.bin").read_bytes() == b"free"
    outcome = next(
        event
        for event in events
        if isinstance(event, ItemOutcome) and event.item_id == str(locked.op_id)
    )
    assert outcome.reason == "sharing-violation"


def test_recorder_failure_preserves_filesystem_success_and_degrades_axis(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"copied")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, events, _ = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        recorder=FakeRecorder(fail="copied"),
    )

    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    assert (target / "file.bin").read_bytes() == b"copied"
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.outcome is Outcome.SUCCEEDED
    assert item.detail["recording"] == "degraded"


def test_trash_collision_preserves_live_item(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (target / "file.bin").write_bytes(b"live")
    collision = target / ".synctrash" / str(RUN_ID) / "file.bin"
    collision.parent.mkdir(parents=True)
    collision.write_bytes(b"existing-trash")
    fs = NativeFileSystem()
    target_stat = fs.stat(target, "file.bin")
    assert target_stat is not None
    operation = _operation(
        1,
        OperationKind.TRASH,
        source_rel_path=None,
        target_rel_path="file.bin",
        source_expected=None,
        target_expected=target_stat,
        intended=None,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "file.bin").read_bytes() == b"live"
    assert collision.read_bytes() == b"existing-trash"
    assert recorder.calls == []


class UnsafeTrashFileSystem(NativeFileSystem):
    def trash_destination(self, target_root, run_id, relative_path):
        raise UnsafeExecutionPath("injected reparse/off-volume trash")


def test_unsafe_trash_is_refused_before_move(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (target / "file.bin").write_bytes(b"live")
    fs = UnsafeTrashFileSystem()
    target_stat = fs.stat(target, "file.bin")
    assert target_stat is not None
    operation = _operation(
        1,
        OperationKind.TRASH,
        source_rel_path=None,
        target_rel_path="file.bin",
        source_expected=None,
        target_expected=target_stat,
        intended=None,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "file.bin").read_bytes() == b"live"
    assert recorder.calls == []


def test_move_uses_nonreplacing_target_rename_and_records_result(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (target / "old.bin").write_bytes(b"moved")
    fs = NativeFileSystem()
    old_stat = fs.stat(target, "old.bin")
    assert old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE,
        source_rel_path=None,
        target_rel_path="new.bin",
        source_expected=None,
        target_expected=None,
        intended=old_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert not (target / "old.bin").exists()
    assert (target / "new.bin").read_bytes() == b"moved"
    assert recorder.calls[0][0] == "moved"
    assert result.bytes_total == 0


@pytest.mark.parametrize("old_missing", [False, True])
def test_move_occupancy_or_vanished_old_path_fails_without_overwrite(
    tmp_path: Path, old_missing: bool
) -> None:
    source, target = _roots(tmp_path)
    (target / "old.bin").write_bytes(b"old")
    fs = NativeFileSystem()
    old_stat = fs.stat(target, "old.bin")
    assert old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE,
        source_rel_path=None,
        target_rel_path="new.bin",
        source_expected=None,
        target_expected=None,
        intended=old_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    if old_missing:
        (target / "old.bin").unlink()
    else:
        (target / "new.bin").write_bytes(b"occupant")

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    if not old_missing:
        assert (target / "old.bin").read_bytes() == b"old"
        assert (target / "new.bin").read_bytes() == b"occupant"
    assert recorder.calls == []


def test_composite_move_update_publishes_new_then_trashes_old(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert not (target / "old.bin").exists()
    assert (target / ".synctrash" / str(RUN_ID) / "old.bin").read_bytes() == b"old"
    assert [call[0] for call in recorder.calls] == ["move_updated"]


class MoveUpdateTrashSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def rename_new(self, source: Path, target: Path) -> None:
        if ".synctrash" in target.parts:
            self.attempts += 1
            if self.attempts == 1:
                error = OSError("sharing violation while trashing old path")
                error.winerror = 32  # type: ignore[attr-defined]
                raise error
        super().rename_new(source, target)


def test_move_update_retries_old_to_trash_without_republishing(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = MoveUpdateTrashSharingOnceFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 2
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert not (target / "old.bin").exists()
    assert (target / ".synctrash" / str(RUN_ID) / "old.bin").read_bytes() == b"old"
    assert [call[0] for call in recorder.calls] == ["move_updated"]


class MoveUpdateTrashSharingAfterCommitFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def rename_new(self, source: Path, target: Path) -> None:
        if ".synctrash" in target.parts:
            self.attempts += 1
            super().rename_new(source, target)
            error = OSError("sharing report after committed trash rename")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        super().rename_new(source, target)


def test_move_update_retry_recognizes_committed_old_to_trash_rename(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = MoveUpdateTrashSharingAfterCommitFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 1
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert not (target / "old.bin").exists()
    assert (target / ".synctrash" / str(RUN_ID) / "old.bin").read_bytes() == b"old"
    assert [call[0] for call in recorder.calls] == ["move_updated"]


class CompositeTrashFaultFileSystem(NativeFileSystem):
    def rename_new(self, source: Path, target: Path) -> None:
        raise OSError("injected old-path trash failure")


def test_composite_fault_after_publish_leaves_both_versions_and_no_record(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = CompositeTrashFaultFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert (target / "old.bin").read_bytes() == b"old"
    assert recorder.calls == []


def test_successful_trash_delete_and_noop_record_after_filesystem_result(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "same.bin").write_bytes(b"same")
    (target / "same.bin").write_bytes(b"same")
    (target / "trash.bin").write_bytes(b"trash")
    (target / "delete.bin").write_bytes(b"delete")
    fs = NativeFileSystem()
    source_same = fs.stat(source, "same.bin")
    target_same = fs.stat(target, "same.bin")
    trash_stat = fs.stat(target, "trash.bin")
    delete_stat = fs.stat(target, "delete.bin")
    assert all(value is not None for value in (source_same, target_same, trash_stat, delete_stat))
    noop = _operation(
        1,
        OperationKind.NOOP,
        source_rel_path="same.bin",
        target_rel_path="same.bin",
        source_expected=source_same,
        target_expected=target_same,
        intended=target_same,
    )
    trash = _operation(
        2,
        OperationKind.TRASH,
        source_rel_path=None,
        target_rel_path="trash.bin",
        source_expected=None,
        target_expected=trash_stat,
        intended=None,
    )
    delete = _operation(
        3,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="delete.bin",
        source_expected=None,
        target_expected=delete_stat,
        intended=None,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (noop, trash, delete))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert not (target / "trash.bin").exists()
    assert (target / ".synctrash" / str(RUN_ID) / "trash.bin").read_bytes() == b"trash"
    assert not (target / "delete.bin").exists()
    assert [call[0] for call in recorder.calls] == ["noop", "trashed", "deleted"]


def test_recorder_flush_failure_blocks_destructive_delete(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (target / "file.bin").write_bytes(b"keep")
    fs = NativeFileSystem()
    target_stat = fs.stat(target, "file.bin")
    assert target_stat is not None
    operation = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="file.bin",
        source_expected=None,
        target_expected=target_stat,
        intended=None,
    )

    result, _, _ = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        recorder=FakeRecorder(fail="flush"),
    )

    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert (target / "file.bin").read_bytes() == b"keep"


class FailingReadonlyDeleteFileSystem(NativeFileSystem):
    def remove_file(self, path: Path) -> None:
        raise PermissionError("injected delete failure")


def test_failed_readonly_delete_restores_planned_attributes(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    live = target / "readonly.bin"
    live.write_bytes(b"keep")
    fs = FailingReadonlyDeleteFileSystem()
    expected = fs.stat(target, "readonly.bin")
    assert expected is not None
    fs.apply_metadata(
        live,
        replace(
            expected,
            metadata=replace(
                expected.metadata, attributes=expected.metadata.attributes | 1
            ),
        ),
        preserve_created=True,
        apply_readonly=True,
    )
    expected = fs.stat(target, "readonly.bin")
    assert expected is not None
    operation = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="readonly.bin",
        source_expected=None,
        target_expected=expected,
        intended=None,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    restored = fs.stat(target, "readonly.bin")
    assert result.status is SessionState.FAILED
    assert live.read_bytes() == b"keep"
    assert restored is not None and restored.metadata.attributes & 1
    assert recorder.calls == []


class ExternalSwapAfterBackupFileSystem(NativeFileSystem):
    def hardlink(self, source: Path, target: Path) -> None:
        super().hardlink(source, target)
        source.unlink()
        source.write_bytes(b"external-swap")


def test_update_external_swap_bound_preserves_planned_old_and_attests_new(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"planned-new")
    (target / "file.bin").write_bytes(b"planned-old")
    fs = ExternalSwapAfterBackupFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert (target / "file.bin").read_bytes() == b"planned-new"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"planned-old"
    attestation = recorder.calls[0][2]
    assert attestation.subject == fs.stat(target, "file.bin")


def test_progress_rate_is_throttled_while_item_outcomes_remain_reliable(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operations: list[PlanOperation] = []
    for number in range(1, 21):
        name = f"file-{number}.bin"
        (source / name).write_bytes(b"same")
        (target / name).write_bytes(b"same")
        source_stat = fs.stat(source, name)
        target_stat = fs.stat(target, name)
        assert source_stat is not None and target_stat is not None
        operations.append(
            _operation(
                number,
                OperationKind.NOOP,
                source_rel_path=name,
                target_rel_path=name,
                source_expected=source_stat,
                target_expected=target_stat,
                intended=target_stat,
            )
        )

    result, events, _ = _run(
        _xset(_plan(source, target, tuple(operations))),
        fs=fs,
        policies=_policies(monotonic=lambda: 0.0, progress_interval_seconds=10.0),
    )

    assert result.status is SessionState.COMPLETED
    assert len([event for event in events if isinstance(event, Progress)]) == 2
    assert len([event for event in events if isinstance(event, ItemOutcome)]) == 20


def test_failed_copy_without_transferred_bytes_keeps_byte_progress_at_zero(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    path = source / "missing.bin"
    path.write_bytes(b"planned")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "missing.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="missing.bin",
        target_rel_path="missing.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    path.unlink()

    result, events, _ = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    progress = [event for event in events if isinstance(event, Progress)]
    assert result.status is SessionState.FAILED
    assert progress[-1].bytes_done == 0
    assert progress[-1].bytes_total == len(b"planned")


def test_executor_imports_core_but_no_sibling_module() -> None:
    source = Path(__file__).parents[1] / "namisync" / "modules" / "executor.py"
    text = source.read_text(encoding="utf-8")
    assert "namisync.modules." not in text
    assert "namisync.core" in text


def test_run_id_rejects_user_controlled_temp_name_material() -> None:
    with pytest.raises(ValueError):
        validated_run_id("../not-an-owned-id")
