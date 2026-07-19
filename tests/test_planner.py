"""Pure deterministic M0 planner acceptance tests."""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

import pytest

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
from namisync.core.pathing import PathValidationError, normalize_relative_path
from namisync.core.planning import (
    Assignment,
    BlockedReason,
    DeletionPolicy,
    DestinationAssignment,
    FilterSet,
    IdentityDestinationPolicy,
    MappingPair,
    MappingSnapshot,
    OperationKind,
    OperationReason,
    PlanOperation,
    PreservationPolicy,
    Scope,
    SyncOptions,
    calculate_required_bytes,
    deterministic_operation_id,
    serialize_plan,
)
from namisync.modules.planner import plan


META = MetadataSnapshot(0, 100)
SOURCE_VOLUME = VolumeId("SRC", "NTFS")
TARGET_VOLUME = VolumeId("DST", "NTFS")


def _profile(*, hardlinks: bool = True, stable: bool = True, granularity: int = 100) -> CapabilityProfile:
    return CapabilityProfile("NTFS" if stable else "exFAT", granularity, stable, None, 32767, False, hardlinks)


def _file(
    path: str,
    *,
    size: int = 10,
    mtime: int = 1_000,
    identity: FileIdentity | None = None,
    nlink: int = 1,
) -> FileRecord:
    return FileRecord(path, normalize_relative_path(path), size, mtime, identity, nlink, META)


def _dir(path: str, *, mtime: int = 500, identity: FileIdentity | None = None) -> DirRecord:
    return DirRecord(
        path,
        normalize_relative_path(path, allow_root=True),
        mtime,
        META,
        identity,
    )


def _unsupported(path: str) -> UnsupportedRecord:
    return UnsupportedRecord(path, normalize_relative_path(path), UnsupportedReason.PLACEHOLDER, EntryKind.FILE)


def _scan(
    root_id: str,
    volume: VolumeId,
    *,
    files: tuple[FileRecord, ...] = (),
    directories: tuple[DirRecord, ...] = (),
    unsupported: tuple[UnsupportedRecord, ...] = (),
    profile: CapabilityProfile | None = None,
    complete: bool = True,
) -> ScanResult:
    return ScanResult(
        Root(fr"C:\{root_id}", root_id),
        volume,
        VolumeEvidence(device_id=volume.serial),
        profile or _profile(),
        files,
        (_dir(""), *directories),
        unsupported,
        (),
        IgnoreSet(),
        ScanScope.full(),
        complete,
    )


def _plan(
    source: ScanResult,
    target: ScanResult,
    *,
    correspondence: MappingSnapshot | None = None,
    options: SyncOptions | None = None,
):
    return plan(
        source,
        target,
        correspondence or MappingSnapshot.empty(source.volume_id, target.volume_id),
        options or SyncOptions(),
        Scope.everything(),
    )


def _mutations(result) -> list[PlanOperation]:
    return [operation for operation in result.operations if operation.kind is not OperationKind.NOOP]


def test_repeated_serialization_and_randomized_input_order_are_byte_identical() -> None:
    files = [_file("b.txt", size=2), _file("A.txt", size=1), _file(r"folder\c.txt", size=3)]
    directories = [_dir("folder")]
    baseline = None
    randomizer = random.Random(9182)
    for _ in range(20):
        randomizer.shuffle(files)
        source = _scan("source", SOURCE_VOLUME, files=tuple(files), directories=tuple(reversed(directories)))
        target = _scan("target", TARGET_VOLUME)
        serialized = serialize_plan(_plan(source, target))
        baseline = serialized if baseline is None else baseline
        assert serialized == baseline


def test_nested_empty_directories_are_explicit_parent_first_and_rerun_has_no_mutation() -> None:
    source = _scan("source", SOURCE_VOLUME, directories=(_dir("a"), _dir(r"a\b"), _dir(r"a\b\c")))
    target = _scan("target", TARGET_VOLUME)
    first = _plan(source, target)
    mkdirs = [operation for operation in first.operations if operation.kind is OperationKind.MKDIR]
    assert [operation.target_rel_path for operation in mkdirs] == ["a", r"a\b", r"a\b\c"]
    assert mkdirs[0].dependencies == ()
    assert mkdirs[1].dependencies == (mkdirs[0].op_id,)
    assert mkdirs[2].dependencies == (mkdirs[1].op_id,)
    assert all(operation.metadata == META for operation in mkdirs)

    converged_target = _scan("target", TARGET_VOLUME, directories=(_dir("a"), _dir(r"a\b"), _dir(r"a\b\c")))
    assert _mutations(_plan(source, converged_target)) == []


def test_file_depends_on_nearest_explicit_parent_directory() -> None:
    source = _scan(
        "source",
        SOURCE_VOLUME,
        files=(_file(r"a\b\file.bin"),),
        directories=(_dir("a"), _dir(r"a\b")),
    )
    result = _plan(source, _scan("target", TARGET_VOLUME))
    operations = {operation.target_rel_path: operation for operation in result.operations}
    assert operations[r"a\b\file.bin"].dependencies == (operations[r"a\b"].op_id,)
    assert operations[r"a\b"].dependencies == (operations["a"].op_id,)


def test_same_plan_removals_enable_dependency_ordered_directory_cleanup() -> None:
    source = _scan("source", SOURCE_VOLUME)
    target = _scan(
        "target",
        TARGET_VOLUME,
        files=(_file(r"obsolete\file.bin", identity=FileIdentity("DST", 4)),),
        directories=(_dir("obsolete"),),
    )
    result = _plan(source, target)
    trash = next(operation for operation in result.operations if operation.kind is OperationKind.TRASH)
    cleanup = next(
        operation
        for operation in result.operations
        if operation.kind is OperationKind.DELETE and operation.target_expected.kind is EntryKind.DIRECTORY
    )
    assert trash.op_id in cleanup.dependencies


def test_additive_keeps_target_only_entries_and_mirror_requires_internal_authorization() -> None:
    source = _scan("source", SOURCE_VOLUME)
    target = _scan("target", TARGET_VOLUME, files=(_file("old.bin"),))
    additive = _plan(source, target, options=SyncOptions(deletion_policy=DeletionPolicy.ADDITIVE))
    assert not _mutations(additive)
    with pytest.raises(ValueError, match="internal authorization"):
        SyncOptions(deletion_policy=DeletionPolicy.MIRROR)
    mirror = _plan(
        source,
        target,
        options=SyncOptions(deletion_policy=DeletionPolicy.MIRROR, internal_mirror_authorized=True),
    )
    assert [operation.kind for operation in _mutations(mirror)] == [OperationKind.DELETE]


def test_persisted_paired_noop_evidence_enables_move_and_empty_correspondence_does_not() -> None:
    source_identity = FileIdentity("SRC", 10)
    target_identity = FileIdentity("DST", 20)
    source = _scan("source", SOURCE_VOLUME, files=(_file("new.bin", identity=source_identity),))
    target = _scan("target", TARGET_VOLUME, files=(_file("old.bin", identity=target_identity),))
    pair = MappingPair(
        normalize_relative_path("old.bin"),
        "old.bin",
        normalize_relative_path("old.bin"),
        source_identity,
        target_identity,
    )
    correspondence = MappingSnapshot(SOURCE_VOLUME, TARGET_VOLUME, (pair,))

    moved = _plan(source, target, correspondence=correspondence)
    move = next(operation for operation in moved.operations if operation.kind is OperationKind.MOVE)
    assert move.target_rel_path == "new.bin"
    assert move.prior_target_rel_path == "old.bin"
    assert move.content_bytes == 0

    without_evidence = _plan(source, target)
    assert OperationKind.MOVE not in {operation.kind for operation in without_evidence.operations}


@pytest.mark.parametrize(
    "source_file,source_profile,target_file,correspondence_override",
    [
        (_file("new.bin", identity=None), _profile(stable=False), _file("old.bin", identity=FileIdentity("DST", 2)), None),
        (_file("new.bin", identity=FileIdentity("SRC", 1), nlink=2), _profile(), _file("old.bin", identity=FileIdentity("DST", 2)), None),
        (_file("new.bin", identity=FileIdentity("OTHER", 1)), _profile(), _file("old.bin", identity=FileIdentity("DST", 2)), None),
        (_file("new.bin", identity=FileIdentity("SRC", 1)), _profile(), _file("old.bin", identity=FileIdentity("DST", 2)), "cross"),
    ],
)
def test_unstable_multilink_and_cross_location_cases_emit_no_move(
    source_file: FileRecord,
    source_profile: CapabilityProfile,
    target_file: FileRecord,
    correspondence_override: str | None,
) -> None:
    source = _scan("source", SOURCE_VOLUME, files=(source_file,), profile=source_profile)
    target = _scan("target", TARGET_VOLUME, files=(target_file,))
    identity = source_file.file_identity or FileIdentity("SRC", 99)
    pair = MappingPair("OLD.BIN", "old.bin", "OLD.BIN", identity, target_file.file_identity)
    source_volume = VolumeId("OTHER", "NTFS") if correspondence_override else SOURCE_VOLUME
    correspondence = MappingSnapshot(source_volume, TARGET_VOLUME, (pair,))
    result = _plan(source, target, correspondence=correspondence)
    assert not any(operation.kind in {OperationKind.MOVE, OperationKind.MOVE_UPDATE} for operation in result.operations)


def test_directory_rename_decomposes_to_mkdir_file_move_and_dependent_cleanup() -> None:
    source_identity = FileIdentity("SRC", 7)
    target_identity = FileIdentity("DST", 8)
    source = _scan(
        "source",
        SOURCE_VOLUME,
        files=(_file(r"new\file.bin", identity=source_identity),),
        directories=(_dir("new"),),
    )
    target = _scan(
        "target",
        TARGET_VOLUME,
        files=(_file(r"old\file.bin", identity=target_identity),),
        directories=(_dir("old"),),
    )
    pair = MappingPair("OLD\\FILE.BIN", r"old\file.bin", "OLD\\FILE.BIN", source_identity, target_identity)
    result = _plan(source, target, correspondence=MappingSnapshot(SOURCE_VOLUME, TARGET_VOLUME, (pair,)))
    mkdir = next(operation for operation in result.operations if operation.kind is OperationKind.MKDIR)
    move = next(operation for operation in result.operations if operation.kind is OperationKind.MOVE)
    cleanup = next(operation for operation in result.operations if operation.reason.value == "directory_cleanup")
    assert move.dependencies == (mkdir.op_id,)
    assert move.op_id in cleanup.dependencies
    assert result.required_bytes == 0


def test_move_update_is_one_composite_operation_and_capacity_counts_backup_when_needed() -> None:
    source_identity = FileIdentity("SRC", 7)
    target_identity = FileIdentity("DST", 8)
    source = _scan("source", SOURCE_VOLUME, files=(_file("new.bin", size=20, mtime=2_000, identity=source_identity),))
    target = _scan(
        "target",
        TARGET_VOLUME,
        files=(_file("old.bin", size=10, mtime=1_000, identity=target_identity),),
        profile=_profile(hardlinks=False),
    )
    pair = MappingPair("OLD.BIN", "old.bin", "OLD.BIN", source_identity, target_identity)
    result = _plan(source, target, correspondence=MappingSnapshot(SOURCE_VOLUME, TARGET_VOLUME, (pair,)))
    composites = [operation for operation in result.operations if operation.kind is OperationKind.MOVE_UPDATE]
    assert len(composites) == 1
    assert result.required_bytes == 30


def test_case_type_and_unsupported_conflicts_are_blocked_while_independent_work_remains_ready() -> None:
    source = _scan(
        "source",
        SOURCE_VOLUME,
        files=(_file("Foo.txt"), _file("foo.TXT"), _file("independent.bin"), _file("occupied")),
        unsupported=(_unsupported("cloud.bin"),),
    )
    target = _scan("target", TARGET_VOLUME, directories=(_dir("occupied"),))
    result = _plan(source, target)
    blocked = [operation for operation in result.operations if operation.blocked]
    assert {operation.blocked_reason for operation in blocked} >= {
        BlockedReason.CASE_COLLISION,
        BlockedReason.TYPE_COLLISION,
        BlockedReason.UNSUPPORTED,
    }
    independent = next(operation for operation in result.operations if operation.target_rel_path == "independent.bin")
    assert independent.kind is OperationKind.COPY
    assert not independent.blocked


def test_incomplete_scans_remain_reviewable_but_are_snapshotted_unexecutable() -> None:
    result = _plan(
        _scan("source", SOURCE_VOLUME, files=(_file("a.bin"),), complete=False),
        _scan("target", TARGET_VOLUME, complete=False),
    )
    assert result.operations
    assert not result.source_complete
    assert not result.target_complete


def test_capacity_formula_counts_every_update_and_no_hardlink_backup() -> None:
    source = _scan(
        "source",
        SOURCE_VOLUME,
        files=(_file("a.bin", size=20, mtime=2_000), _file("b.bin", size=40, mtime=2_000)),
    )
    target_files = (_file("a.bin", size=10), _file("b.bin", size=30))
    no_hardlinks = _plan(
        source,
        _scan("target", TARGET_VOLUME, files=target_files, profile=_profile(hardlinks=False)),
    )
    hardlinks = _plan(
        source,
        _scan("target", TARGET_VOLUME, files=target_files, profile=_profile(hardlinks=True)),
    )
    assert no_hardlinks.required_bytes == 100
    assert hardlinks.required_bytes == 60
    selected = [operation for operation in no_hardlinks.operations if operation.target_rel_path == "a.bin"]
    assert calculate_required_bytes(selected, target_profile=no_hardlinks.target_profile, trash_on_update=True) == 30


def test_filters_apply_symmetrically_and_snapshot_without_target_only_deletion() -> None:
    filters = FilterSet(("*.tmp",))
    source = _scan("source", SOURCE_VOLUME, files=(_file("source.tmp"), _file("keep.bin")))
    target = _scan("target", TARGET_VOLUME, files=(_file("target.tmp"),))
    result = _plan(source, target, options=SyncOptions(filters=filters))
    assert result.filter_snapshot == filters
    paths = {operation.target_rel_path for operation in result.operations}
    assert "source.tmp" not in paths
    assert "target.tmp" not in paths
    assert "keep.bin" in paths


def test_excluded_subtrees_and_empty_target_directories_are_never_planned_as_missing() -> None:
    filters = FilterSet(("excluded",))
    source = _scan(
        "source",
        SOURCE_VOLUME,
        files=(_file(r"excluded\source.bin"),),
        directories=(_dir("excluded"),),
    )
    target = _scan("target", TARGET_VOLUME, directories=(_dir("excluded"),))
    result = _plan(source, target, options=SyncOptions(filters=filters))
    assert _mutations(result) == []


def test_coarse_timestamp_granularity_produces_metadata_noop() -> None:
    coarse = _profile(stable=False, granularity=2_000_000_000)
    source = _scan("source", SOURCE_VOLUME, files=(_file("same.bin", mtime=3_000_000_000),), profile=coarse)
    target = _scan(
        "target",
        TARGET_VOLUME,
        files=(_file("same.bin", mtime=1_000_000_000, identity=FileIdentity("DST", 2)),),
        profile=coarse,
    )
    assert [operation.kind for operation in _plan(source, target).operations] == [OperationKind.NOOP]


def test_standard_attribute_change_plans_update_without_mtime_change() -> None:
    source_file = replace(
        _file("same.bin"), metadata=MetadataSnapshot(1, META.created_ns)
    )
    target_file = _file("same.bin", identity=FileIdentity("DST", 2))
    source = _scan("source", SOURCE_VOLUME, files=(source_file,))
    target = _scan("target", TARGET_VOLUME, files=(target_file,))

    operations = _plan(source, target).operations

    assert [operation.kind for operation in operations] == [OperationKind.UPDATE]
    assert operations[0].reason is OperationReason.METADATA_CHANGED
    assert operations[0].metadata == source_file.metadata
    assert operations[0].content_bytes == source_file.size


def test_duplicate_identity_and_ambiguous_prior_correspondence_disable_move() -> None:
    identity = FileIdentity("SRC", 11)
    target_identity = FileIdentity("DST", 22)
    source = _scan(
        "source",
        SOURCE_VOLUME,
        files=(_file("new-a.bin", identity=identity), _file("new-b.bin", identity=identity)),
    )
    target = _scan("target", TARGET_VOLUME, files=(_file("old.bin", identity=target_identity),))
    pair = MappingPair("OLD.BIN", "old.bin", "OLD.BIN", identity, target_identity)
    duplicate = _plan(source, target, correspondence=MappingSnapshot(SOURCE_VOLUME, TARGET_VOLUME, (pair,)))
    assert not any(operation.kind in {OperationKind.MOVE, OperationKind.MOVE_UPDATE} for operation in duplicate.operations)

    unique_source = _scan("source", SOURCE_VOLUME, files=(_file("new.bin", identity=identity),))
    ambiguous = _plan(
        unique_source,
        target,
        correspondence=MappingSnapshot(
            SOURCE_VOLUME,
            TARGET_VOLUME,
            (pair,),
            ambiguous_source_keys=frozenset({normalize_relative_path("new.bin")}),
        ),
    )
    assert not any(operation.kind in {OperationKind.MOVE, OperationKind.MOVE_UPDATE} for operation in ambiguous.operations)


@dataclass(frozen=True)
class CollidingPolicy:
    name: str = "collision-fixture"
    version: str = "1"

    def assign(self, records, meta, target) -> Assignment:
        del meta, target
        return Assignment(
            self.name,
            self.version,
            tuple(
                DestinationAssignment(
                    record.rel_path,
                    record.rel_path_key,
                    "same.bin",
                    normalize_relative_path("same.bin"),
                    group_id="companions",
                )
                for record in sorted(records, key=lambda item: item.rel_path_key)
            ),
        )


def test_destination_policy_collision_is_deterministic_unique_and_reviewable() -> None:
    source = _scan("source", SOURCE_VOLUME, files=(_file("a.raw"), _file("a.xmp")))
    options = SyncOptions(destination_policy=CollidingPolicy())
    first = _plan(source, _scan("target", TARGET_VOLUME), options=options)
    second = _plan(source, _scan("target", TARGET_VOLUME), options=options)
    assert serialize_plan(first) == serialize_plan(second)
    collision_ops = [operation for operation in first.operations if operation.target_rel_path == "same.bin"]
    assert len(collision_ops) == 2
    assert len({operation.op_id for operation in collision_ops}) == 2
    assert all(operation.blocked_reason is BlockedReason.DESTINATION_COLLISION for operation in collision_ops)


def test_long_destination_paths_are_validated_without_legacy_max_path_truncation() -> None:
    long_path = "\\".join(["directory" * 10] * 4 + ["file.bin"])
    result = _plan(_scan("source", SOURCE_VOLUME, files=(_file(long_path),)), _scan("target", TARGET_VOLUME))
    assert any(operation.target_rel_path == long_path for operation in result.operations)


def test_plan_operation_rejects_root_escape() -> None:
    with pytest.raises(PathValidationError):
        PlanOperation(
            deterministic_operation_id(OperationKind.COPY, "good.bin", "good.bin", None, __import__("namisync.core.planning", fromlist=["OperationReason"]).OperationReason.SOURCE_ONLY),
            OperationKind.COPY,
            "good.bin",
            r"..\escape.bin",
            _file("good.bin").stat,
            None,
            _file("good.bin").stat,
        )
