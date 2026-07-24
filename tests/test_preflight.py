"""Scoped observation and pure M0 preflight acceptance tests."""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
import inspect

import pytest

from namisync.core.evidence import Outcome
from namisync.core.execution import ExecutionSet, validated_run_id
from namisync.core.models import (
    CapabilityProfile,
    DirRecord,
    EntryKind,
    FileIdentity,
    FileRecord,
    IgnoreSet,
    MetadataSnapshot,
    Root,
    ScanResult,
    ScanScope,
    UnsupportedReason,
    UnsupportedRecord,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import (
    DeletionPolicy,
    FilterSet,
    MappingSnapshot,
    OperationKind,
    Scope,
    SyncOptions,
    calculate_required_bytes,
    serialize_plan,
)
from namisync.core.preflight import (
    ObservedWorld,
    RefusalCode,
    RootObservation,
    StatObservation,
    Subject,
    TrashObservation,
)
from namisync.modules.planner import plan
from namisync.modules.preflight import LocalObservationFileSystem, observe, preflight


NOW = datetime(2026, 7, 18, tzinfo=timezone.utc)
META = MetadataSnapshot(0, 100)
SOURCE_VOLUME = VolumeId("SRC", "NTFS")
TARGET_VOLUME = VolumeId("DST", "NTFS")
PROFILE = CapabilityProfile("NTFS", 100, True, None, 32767, False, True)


def _file(
    path: str,
    *,
    size: int = 10,
    mtime: int = 1_000,
    volume: str = "SRC",
    index: int = 1,
) -> FileRecord:
    return FileRecord(
        path,
        normalize_relative_path(path),
        size,
        mtime,
        FileIdentity(volume, index),
        1,
        META,
    )


def _dir(path: str) -> DirRecord:
    return DirRecord(path, normalize_relative_path(path, allow_root=True), 500, META, None)


def _scan(
    root_id: str,
    volume: VolumeId,
    *,
    files: tuple[FileRecord, ...] = (),
    directories: tuple[DirRecord, ...] = (),
    profile: CapabilityProfile = PROFILE,
    complete: bool = True,
    unsupported: tuple[UnsupportedRecord, ...] = (),
) -> ScanResult:
    return ScanResult(
        Root(fr"C:\{root_id}", root_id),
        volume,
        VolumeEvidence(device_id=volume.serial),
        profile,
        files,
        (_dir(""), *directories),
        unsupported,
        (),
        IgnoreSet(),
        ScanScope.full(),
        complete,
    )


def _xset(
    *,
    source_files: tuple[FileRecord, ...] = (_file("copy.bin"),),
    target_files: tuple[FileRecord, ...] = (),
    source_directories: tuple[DirRecord, ...] = (),
    target_directories: tuple[DirRecord, ...] = (),
    source_complete: bool = True,
    target_complete: bool = True,
    options: SyncOptions | None = None,
    target_profile: CapabilityProfile = PROFILE,
) -> ExecutionSet:
    source = _scan(
        "source",
        SOURCE_VOLUME,
        files=source_files,
        directories=source_directories,
        complete=source_complete,
    )
    target = _scan(
        "target",
        TARGET_VOLUME,
        files=target_files,
        directories=target_directories,
        profile=target_profile,
        complete=target_complete,
    )
    built = plan(
        source,
        target,
        MappingSnapshot.empty(SOURCE_VOLUME, TARGET_VOLUME),
        options or SyncOptions(),
        Scope.everything(),
    )
    return ExecutionSet(
        built,
        frozenset(operation.op_id for operation in built.operations if not operation.blocked),
        validated_run_id("a" * 32),
    )


def _world(xset: ExecutionSet, *, free_space: int = 10_000) -> ObservedWorld:
    stats: dict[Subject, StatObservation] = {}
    paths: dict[Subject, str] = {}
    for operation in xset.remaining():
        if operation.source_rel_path is not None and operation.source_expected is not None:
            subject = Subject(xset.plan.source_root.root_id, normalize_relative_path(operation.source_rel_path))
            stats[subject] = StatObservation(operation.source_expected)
            paths[subject] = operation.source_rel_path
        target_subject = Subject(xset.plan.target_root.root_id, normalize_relative_path(operation.target_rel_path))
        stats[target_subject] = StatObservation(operation.target_expected)
        paths[target_subject] = operation.target_rel_path
        if operation.prior_target_rel_path is not None:
            prior = Subject(xset.plan.target_root.root_id, normalize_relative_path(operation.prior_target_rel_path))
            stats[prior] = StatObservation(operation.prior_target_expected)
            paths[prior] = operation.prior_target_rel_path
    return ObservedWorld(
        stats,
        paths,
        frozenset(),
        {
            xset.plan.source_root.root_id: RootObservation(
                xset.plan.source_root.path,
                xset.plan.source_volume_id,
                xset.plan.source_volume_evidence,
            ),
            xset.plan.target_root.root_id: RootObservation(
                xset.plan.target_root.path,
                xset.plan.target_volume_id,
                xset.plan.target_volume_evidence,
            ),
        },
        free_space,
        0,
        TrashObservation(r"C:\target\.synctrash", True, True, True, True, True),
        NOW,
    )


def _codes(xset: ExecutionSet, world: ObservedWorld) -> set[RefusalCode]:
    return {refusal.code for refusal in preflight(xset, world).refusals}


def test_pure_preflight_accepts_matching_snapshot_without_filesystem() -> None:
    xset = _xset()
    verdict = preflight(xset, _world(xset))
    assert verdict.ok
    assert verdict.refusals == ()


def test_execution_preflight_has_no_live_settings_drift_path() -> None:
    import namisync.core.preflight as core_preflight
    import namisync.modules.preflight as module_preflight
    import namisync.workflows.sync as sync_workflow

    source = "\n".join(
        inspect.getsource(module)
        for module in (core_preflight, module_preflight, sync_workflow)
    )
    for retired in (
        "SettingsReader",
        "StaticSettingsReader",
        "current_filters",
        "current_policy_fingerprint",
        "settings_error",
        "FILTER_DRIFT",
        "OPTIONS_DRIFT",
    ):
        assert retired not in source


def test_preflight_accepts_new_identity_when_scan_had_no_identity_evidence() -> None:
    source = replace(_file("copy.bin"), file_identity=None)
    xset = _xset(source_files=(source,))
    world = _world(xset)
    operation = xset.remaining()[0]
    subject = Subject(
        xset.plan.source_root.root_id,
        normalize_relative_path(operation.source_rel_path),
    )
    stats = dict(world.stats)
    observed = stats[subject].stat
    assert observed is not None
    stats[subject] = StatObservation(
        replace(observed, file_identity=FileIdentity("SRC", 999))
    )

    assert RefusalCode.IDENTITY_CHANGED not in _codes(
        xset, replace(world, stats=stats)
    )


@pytest.mark.parametrize(
    ("source_complete", "target_complete"),
    [(False, True), (True, False), (False, False)],
)
def test_incomplete_scan_allows_selected_copy_work(
    source_complete: bool, target_complete: bool
) -> None:
    xset = _xset(source_complete=source_complete, target_complete=target_complete)

    assert preflight(xset, _world(xset)).ok


@pytest.mark.parametrize(
    ("source_complete", "target_complete", "expected"),
    [
        (False, True, {RefusalCode.INCOMPLETE_SOURCE_SCAN}),
        (True, False, {RefusalCode.INCOMPLETE_TARGET_SCAN}),
        (
            False,
            False,
            {
                RefusalCode.INCOMPLETE_SOURCE_SCAN,
                RefusalCode.INCOMPLETE_TARGET_SCAN,
            },
        ),
    ],
)
def test_incomplete_scan_refuses_selected_destructive_work(
    source_complete: bool,
    target_complete: bool,
    expected: set[RefusalCode],
) -> None:
    xset = _xset(
        source_files=(),
        target_files=(_file("target-only.bin", volume="DST"),),
        source_complete=source_complete,
        target_complete=target_complete,
    )

    assert expected <= _codes(xset, _world(xset))


def test_preflight_refuses_manually_selected_blocked_correspondence() -> None:
    source = _scan(
        "source",
        SOURCE_VOLUME,
        complete=False,
        unsupported=(
            UnsupportedRecord(
                "foo",
                normalize_relative_path("foo"),
                UnsupportedReason.REPARSE_POINT,
                EntryKind.DIRECTORY,
            ),
        ),
    )
    target = _scan(
        "target",
        TARGET_VOLUME,
        files=(_file(r"foo\keep.txt", volume="DST"),),
        directories=(_dir("foo"),),
    )
    built = plan(
        source,
        target,
        MappingSnapshot.empty(SOURCE_VOLUME, TARGET_VOLUME),
        SyncOptions(),
        Scope.everything(),
    )
    counterpart = next(
        operation
        for operation in built.operations
        if operation.target_rel_path == r"foo\keep.txt"
    )
    xset = ExecutionSet(
        built,
        frozenset({counterpart.op_id}),
        validated_run_id("b" * 32),
    )

    assert RefusalCode.BLOCKED_CORRESPONDENCE in _codes(xset, _world(xset))


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("source_absent", RefusalCode.SOURCE_DRIFT),
        ("target_absent", RefusalCode.TARGET_DRIFT),
        ("destination_appeared", RefusalCode.DESTINATION_APPEARED),
        ("type", RefusalCode.TYPE_CHANGED),
        ("identity", RefusalCode.IDENTITY_CHANGED),
        ("size", RefusalCode.SIZE_CHANGED),
        ("mtime", RefusalCode.MTIME_CHANGED),
    ],
)
def test_touched_evidence_drift_yields_typed_refusal(mutation: str, expected: RefusalCode) -> None:
    if mutation == "target_absent":
        xset = _xset(
            source_files=(_file("same.bin", size=20, mtime=2_000),),
            target_files=(_file("same.bin", size=10, mtime=1_000, volume="DST", index=2),),
        )
    else:
        xset = _xset()
    world = _world(xset)
    operation = xset.remaining()[0]
    source_subject = Subject(xset.plan.source_root.root_id, normalize_relative_path(operation.source_rel_path))
    target_subject = Subject(xset.plan.target_root.root_id, normalize_relative_path(operation.target_rel_path))
    stats = dict(world.stats)
    if mutation == "source_absent":
        stats[source_subject] = StatObservation(None)
    elif mutation == "target_absent":
        stats[target_subject] = StatObservation(None)
    elif mutation == "destination_appeared":
        stats[target_subject] = StatObservation(_file("appeared.bin", volume="DST", index=9).stat)
    else:
        current = stats[source_subject].stat
        assert current is not None
        if mutation == "type":
            changed = replace(current, kind=EntryKind.DIRECTORY, size=0)
        elif mutation == "identity":
            changed = replace(current, file_identity=FileIdentity("SRC", 999))
        elif mutation == "size":
            changed = replace(current, size=current.size + 1)
        else:
            changed = replace(current, mtime_ns=current.mtime_ns + 101)
        stats[source_subject] = StatObservation(changed)
    assert expected in _codes(xset, replace(world, stats=stats))


def test_root_swap_and_clone_are_typed() -> None:
    xset = _xset(options=SyncOptions(filters=FilterSet(("*.tmp",))))
    world = _world(xset)
    roots = dict(world.roots)
    roots[xset.plan.source_root.root_id] = replace(
        roots[xset.plan.source_root.root_id],
        volume_id=VolumeId("SWAPPED", "NTFS"),
        volume_evidence=VolumeEvidence(device_id="clone", clone_ambiguous=True),
    )
    drifted = replace(world, roots=roots)
    assert {
        RefusalCode.ROOT_CHANGED,
        RefusalCode.VOLUME_CLONE_AMBIGUOUS,
    } <= _codes(xset, drifted)


def test_same_or_nested_resolved_roots_are_refused() -> None:
    xset = _xset()
    world = _world(xset)
    roots = dict(world.roots)
    roots[xset.plan.target_root.root_id] = replace(
        roots[xset.plan.target_root.root_id], resolved_path=r"C:\source\nested"
    )
    assert RefusalCode.ROOTS_OVERLAP in _codes(xset, replace(world, roots=roots))


def test_dependency_break_and_blocked_dependency_are_refused() -> None:
    xset = _xset(
        source_files=(_file(r"folder\copy.bin"),),
        source_directories=(_dir("folder"),),
    )
    mkdir = next(operation for operation in xset.plan.operations if operation.kind is OperationKind.MKDIR)
    copy_op = next(operation for operation in xset.plan.operations if operation.kind is OperationKind.COPY)
    not_closed = ExecutionSet(xset.plan, frozenset({copy_op.op_id}), xset.run_id)
    assert RefusalCode.SELECTION_NOT_CLOSED in _codes(not_closed, _world(not_closed))

    failed = ExecutionSet(xset.plan, xset.selection, xset.run_id, {mkdir.op_id: Outcome.FAILED})
    assert RefusalCode.DEPENDENCY_UNAVAILABLE in _codes(failed, _world(failed))

    blocked = ExecutionSet(
        xset.plan,
        xset.selection,
        xset.run_id,
        {mkdir.op_id: Outcome.BLOCKED},
    )
    assert RefusalCode.DEPENDENCY_UNAVAILABLE in _codes(
        blocked, _world(blocked)
    )


@pytest.mark.parametrize(
    ("trash", "expected"),
    [
        (TrashObservation(None, False, False, False, False, False, "missing"), RefusalCode.TRASH_UNAVAILABLE),
        (TrashObservation("outside", True, False, True, True, True), RefusalCode.TRASH_ESCAPE),
        (TrashObservation("other", True, True, False, True, True), RefusalCode.TRASH_OFF_VOLUME),
        (TrashObservation("readonly", True, True, True, False, True), RefusalCode.TRASH_NOT_WRITABLE),
        (TrashObservation("reparse", True, True, True, True, False), RefusalCode.TRASH_REPARSE),
    ],
)
def test_trash_safety_failures_are_typed(trash: TrashObservation, expected: RefusalCode) -> None:
    xset = _xset(
        source_files=(_file("same.bin", size=20, mtime=2_000),),
        target_files=(_file("same.bin", size=10, mtime=1_000, volume="DST", index=2),),
    )
    assert expected in _codes(xset, replace(_world(xset), trash=trash))


def test_capacity_boundary_uses_same_function_and_only_exact_reclaimable_bytes() -> None:
    no_hardlinks = CapabilityProfile("NTFS", 100, True, None, 32767, False, False)
    xset = _xset(
        source_files=(_file("same.bin", size=20, mtime=2_000),),
        target_files=(_file("same.bin", size=10, mtime=1_000, volume="DST", index=2),),
        target_profile=no_hardlinks,
    )
    required = calculate_required_bytes(
        xset.remaining(), target_profile=xset.plan.target_profile, trash_on_update=True
    )
    assert required == xset.plan.required_bytes == 30
    assert RefusalCode.INSUFFICIENT_SPACE in _codes(xset, _world(xset, free_space=29))
    assert preflight(xset, replace(_world(xset, free_space=29), reclaimable_temp_bytes=1)).ok


def test_repeated_contexts_are_identical_for_identical_worlds_and_fresh_drift_changes_verdict() -> None:
    xset = _xset()
    world = _world(xset)
    review = preflight(xset, world)
    execution = preflight(xset, world)
    resume = preflight(xset, world)
    queue_wakeup = preflight(xset, world)
    assert review == execution == resume == queue_wakeup
    operation = xset.remaining()[0]
    subject = Subject(xset.plan.source_root.root_id, normalize_relative_path(operation.source_rel_path))
    drift_stats = dict(world.stats)
    drift_stats[subject] = StatObservation(None)
    assert not preflight(xset, replace(world, stats=drift_stats, observed_at=NOW.replace(second=1))).ok


def test_refusal_leaves_plan_selection_status_and_world_unchanged() -> None:
    xset = _xset()
    world = replace(_world(xset), free_space=0)
    before_plan = serialize_plan(xset.plan)
    before_selection = xset.selection
    before_status = copy.deepcopy(xset.status)
    before_world = copy.deepcopy(world)
    verdict = preflight(xset, world)
    assert not verdict.ok
    assert serialize_plan(xset.plan) == before_plan
    assert xset.selection == before_selection
    assert xset.status == before_status
    assert world == before_world


def test_unrelated_stat_change_is_ignored_but_touched_change_refuses() -> None:
    xset = _xset()
    world = _world(xset)
    unrelated = Subject(xset.plan.target_root.root_id, "UNRELATED.BIN")
    stats = dict(world.stats)
    stats[unrelated] = StatObservation(_file("unrelated.bin", volume="DST", index=99).stat)
    assert preflight(xset, replace(world, stats=stats)).ok
    operation = xset.remaining()[0]
    touched = Subject(xset.plan.source_root.root_id, normalize_relative_path(operation.source_rel_path))
    stats[touched] = StatObservation(None)
    assert RefusalCode.SOURCE_DRIFT in _codes(xset, replace(world, stats=stats))


def test_path_escape_and_unrepresentable_destination_are_refused() -> None:
    xset = _xset()
    world = _world(xset)
    operation = xset.remaining()[0]
    target = Subject(xset.plan.target_root.root_id, normalize_relative_path(operation.target_rel_path))
    stats = dict(world.stats)
    stats[target] = StatObservation(None, None, contained=False, representable=False)
    assert {RefusalCode.PATH_ESCAPE, RefusalCode.PATH_UNREPRESENTABLE} <= _codes(
        xset, replace(world, stats=stats)
    )


class InstrumentedFileSystem:
    def __init__(self, xset: ExecutionSet) -> None:
        self.xset = xset
        self.stat_calls: list[tuple[str, str]] = []
        self.root_calls: list[str] = []
        self.user_state = b"unchanged"

    def observe_root(self, root: Root) -> RootObservation:
        self.root_calls.append(root.root_id)
        volume = self.xset.plan.source_volume_id if root.root_id == "source" else self.xset.plan.target_volume_id
        evidence = self.xset.plan.source_volume_evidence if root.root_id == "source" else self.xset.plan.target_volume_evidence
        return RootObservation(root.path, volume, evidence)

    def stat(self, root: Root, rel_path: str, profile: CapabilityProfile) -> StatObservation:
        del profile
        self.stat_calls.append((root.root_id, rel_path))
        for operation in self.xset.plan.operations:
            if root.root_id == "source" and operation.source_rel_path == rel_path:
                return StatObservation(operation.source_expected)
            if root.root_id == "target" and operation.target_rel_path == rel_path:
                return StatObservation(operation.target_expected)
            if root.root_id == "target" and operation.prior_target_rel_path == rel_path:
                return StatObservation(operation.prior_target_expected)
        return StatObservation(None)

    def free_space(self, target: Root) -> int:
        return 10_000

    def reclaimable_temp_bytes(
        self,
        target: Root,
        parent_paths: frozenset[str],
        current_run_id: str,
    ) -> int:
        return 0

    def observe_trash(self, target: Root, expected_volume: VolumeId | None) -> TrashObservation:
        return TrashObservation(r"C:\target\.synctrash", True, True, True, True, True)

    def now_utc(self) -> datetime:
        return NOW


def test_observation_is_read_only_and_stats_only_remaining_touched_paths_and_parents() -> None:
    xset = _xset(
        source_files=(_file(r"folder\one.bin", index=1), _file(r"folder\two.bin", index=2)),
        source_directories=(_dir("folder"),),
    )
    first_copy = next(operation for operation in xset.plan.operations if operation.target_rel_path.endswith("one.bin"))
    selected = ExecutionSet(xset.plan, frozenset({first_copy.op_id}), xset.run_id)
    fs = InstrumentedFileSystem(selected)
    before = fs.user_state
    world = observe(selected, fs)
    assert fs.user_state == before
    assert set(fs.root_calls) == {"source", "target"}
    assert ("source", r"folder\one.bin") in fs.stat_calls
    assert ("target", r"folder\one.bin") in fs.stat_calls
    assert ("target", "folder") in fs.stat_calls
    assert not any(path.endswith("two.bin") for _, path in fs.stat_calls)
    assert world.observed_at is NOW


def test_local_reclaimable_temp_count_is_exact_and_excludes_synctrash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "folder"
    parent.mkdir()
    exact = parent / ("data.bin.synctmp-" + "a" * 32 + "-" + "b" * 32)
    exact.write_bytes(b"12345")
    current = parent / ("current.bin.synctmp-" + "c" * 32 + "-" + "d" * 32)
    current.write_bytes(b"current")
    (parent / "my.synctmp-notes.txt").write_bytes(b"user")
    trash = tmp_path / ".synctrash"
    trash.mkdir()
    (trash / ("old.bin.synctmp-" + "a" * 32 + "-" + "b" * 32)).write_bytes(b"ignored")
    off_volume = tmp_path / "off-volume"
    off_volume.mkdir()
    (off_volume / ("mounted.bin.synctmp-" + "a" * 32 + "-" + "b" * 32)).write_bytes(
        b"other volume"
    )
    monkeypatch.setattr(
        "namisync.modules.preflight._volume_observation",
        lambda path: (
            VolumeId("OTHER", "UNKNOWN")
            if Path(path).name == "off-volume"
            else VolumeId("TARGET", "UNKNOWN"),
            VolumeEvidence(device_id=str(path)),
        ),
    )
    fs = LocalObservationFileSystem()
    assert fs.reclaimable_temp_bytes(
        Root(str(tmp_path), "target"),
        frozenset({"folder", ".synctrash", "off-volume"}),
        "c" * 32,
    ) == 5


def test_required_existing_parent_disappearance_or_type_change_refuses() -> None:
    xset = _xset(
        source_files=(_file(r"folder\copy.bin"),),
        source_directories=(_dir("folder"),),
        target_directories=(_dir("folder"),),
    )
    world = _world(xset)
    parent = Subject(xset.plan.target_root.root_id, normalize_relative_path("folder"))
    paths = dict(world.paths)
    paths[parent] = "folder"
    stats = dict(world.stats)
    stats[parent] = StatObservation(_dir("folder").stat)
    assert preflight(xset, replace(world, stats=stats, paths=paths)).ok
    stats[parent] = StatObservation(None)
    assert RefusalCode.TARGET_DRIFT in _codes(xset, replace(world, stats=stats, paths=paths))
    stats[parent] = StatObservation(_file("folder", volume="DST", index=4).stat)
    assert RefusalCode.TYPE_CHANGED in _codes(xset, replace(world, stats=stats, paths=paths))


def test_observation_failure_is_evidence_and_refuses_affected_operation() -> None:
    xset = _xset()
    world = _world(xset)
    operation = xset.remaining()[0]
    subject = Subject(xset.plan.source_root.root_id, normalize_relative_path(operation.source_rel_path))
    stats = dict(world.stats)
    stats[subject] = StatObservation(None, "access denied")
    assert RefusalCode.OBSERVATION_UNAVAILABLE in _codes(xset, replace(world, stats=stats))


def test_partial_remaining_selection_recomputes_capacity_from_shared_formula() -> None:
    no_hardlinks = CapabilityProfile("NTFS", 100, True, None, 32767, False, False)
    original = _xset(
        source_files=(
            _file("a.bin", size=20, mtime=2_000, index=1),
            _file("b.bin", size=40, mtime=2_000, index=2),
        ),
        target_files=(
            _file("a.bin", size=10, volume="DST", index=11),
            _file("b.bin", size=30, volume="DST", index=12),
        ),
        target_profile=no_hardlinks,
    )
    first = next(operation for operation in original.plan.operations if operation.target_rel_path == "a.bin")
    remaining = ExecutionSet(original.plan, original.selection, original.run_id, {first.op_id: Outcome.SUCCEEDED})
    required = calculate_required_bytes(
        remaining.remaining(), target_profile=remaining.plan.target_profile, trash_on_update=True
    )
    assert required == 70
    assert RefusalCode.INSUFFICIENT_SPACE in _codes(remaining, _world(remaining, free_space=69))
    assert preflight(remaining, _world(remaining, free_space=70)).ok
