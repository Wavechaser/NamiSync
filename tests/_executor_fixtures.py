from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, TypeVar

from xxhash import xxh3_128

from namisync.core.events import ItemOutcome
from namisync.core.execution import (
    ExecutionSet,
    RecordedCopyIdentity,
    validated_run_id,
)
from namisync.core.models import CapabilityProfile, FileStat, Root
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
from namisync.core.session import RunContext
from namisync.modules.executor import (
    BoundedFailurePolicy,
    ExecutorPolicies,
    NativeCopyBackend,
    NativeFileSystem,
    execute,
)


RUN_ID = validated_run_id("1" * 32)
_FileSystemT = TypeVar("_FileSystemT", bound=NativeFileSystem)


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

    @staticmethod
    def _copy_identity(op: OpId) -> RecordedCopyIdentity:
        return RecordedCopyIdentity(
            row_id=f"row-{op}",
            location_id="target-location",
            scope_token=f"scope-{op}",
            rel_path_key=f"PATH-{op}".upper(),
        )

    def record_copied(self, op, attestation) -> RecordedCopyIdentity:
        self._record("copied", op, attestation)
        return self._copy_identity(op)

    def record_updated(self, op, attestation) -> RecordedCopyIdentity:
        self._record("updated", op, attestation)
        return self._copy_identity(op)

    def record_moved(self, op, target) -> None:
        self._record("moved", op, target)

    def record_recased(self, op, target) -> None:
        self._record("recased", op, target)

    def record_move_updated(self, op, attestation) -> RecordedCopyIdentity:
        self._record("move_updated", op, attestation)
        return self._copy_identity(op)

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
            0
            if source_expected is None
            or kind
            not in {
                OperationKind.COPY,
                OperationKind.UPDATE,
                OperationKind.MOVE_UPDATE,
            }
            else source_expected.size
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
        "copy_backend": NativeCopyBackend(hasher_factory=xxh3_128),
        "clock": FixedClock(),
        "max_chunk_size": 4,
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


def _item_outcome(
    events: list[object],
    op_id: OpId | str | None = None,
) -> ItemOutcome:
    outcomes = [event for event in events if isinstance(event, ItemOutcome)]
    if op_id is not None:
        outcomes = [outcome for outcome in outcomes if outcome.item_id == str(op_id)]
    assert len(outcomes) == 1
    return outcomes[0]


def _recorder_names(recorder: FakeRecorder) -> list[str]:
    return [call[0] for call in recorder.calls]


def _sharing_violation(message: str) -> OSError:
    error = OSError(message)
    error.winerror = 32  # type: ignore[attr-defined]
    return error


class _ControlLatch:
    def __init__(self, control_type: type[BaseException]) -> None:
        self.control_type = control_type
        self.armed = False

    def arm(self, _delay: float) -> None:
        self.armed = True

    def checkpoint(self) -> None:
        if self.armed:
            raise self.control_type()


def _make_readonly(fs: NativeFileSystem, path: Path, expected: FileStat) -> None:
    fs.apply_metadata(
        path,
        replace(
            expected,
            metadata=replace(
                expected.metadata,
                attributes=expected.metadata.attributes | 1,
            ),
        ),
        preserve_created=True,
        apply_readonly=True,
    )


def _readonly_update_setup(
    tmp_path: Path,
    fs_factory: Callable[[Path], _FileSystemT],
    *,
    retain_backup: bool,
) -> tuple[Path, Path, NativeFileSystem, _FileSystemT, ExecutionSet]:
    source, target = _roots(tmp_path)
    (source / "readonly.bin").write_bytes(b"new-version")
    live = target / "readonly.bin"
    live.write_bytes(b"old-version")
    setup_fs = NativeFileSystem()
    expected = setup_fs.stat(target, "readonly.bin")
    assert expected is not None
    _make_readonly(setup_fs, live, expected)

    fs = fs_factory(live)
    source_stat = fs.stat(source, "readonly.bin")
    target_stat = fs.stat(target, "readonly.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="readonly.bin",
        target_rel_path="readonly.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    xset = _xset(
        _plan(
            source,
            target,
            (operation,),
            trash_on_update=retain_backup,
        )
    )
    return target, live, setup_fs, fs, xset


def _reviewed_byte_operation(
    kind: OperationKind,
    source: Path,
    target: Path,
    fs: NativeFileSystem,
) -> tuple[PlanOperation, Path]:
    target_rel_path = (
        "renamed.bin" if kind is OperationKind.MOVE_UPDATE else "file.bin"
    )
    (source / target_rel_path).write_bytes(b"new-version")
    source_stat = fs.stat(source, target_rel_path)
    assert source_stat is not None

    target_expected = None
    prior_target_rel_path = None
    prior_target_expected = None
    if kind is OperationKind.UPDATE:
        (target / target_rel_path).write_bytes(b"old-version")
        target_expected = fs.stat(target, target_rel_path)
        assert target_expected is not None
    elif kind is OperationKind.MOVE_UPDATE:
        prior_target_rel_path = "old.bin"
        (target / prior_target_rel_path).write_bytes(b"old-version")
        prior_target_expected = fs.stat(target, prior_target_rel_path)
        assert prior_target_expected is not None

    return (
        _operation(
            1,
            kind,
            source_rel_path=target_rel_path,
            target_rel_path=target_rel_path,
            source_expected=source_stat,
            target_expected=target_expected,
            intended=source_stat,
            prior_target_rel_path=prior_target_rel_path,
            prior_target_expected=prior_target_expected,
        ),
        target / target_rel_path,
    )
