"""Scoped observation and pure M0 preflight acceptance tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timezone
import os
import stat as stat_module
from pathlib import Path, PureWindowsPath
import inspect
from types import MappingProxyType, SimpleNamespace
from unittest.mock import patch

import pytest

import namisync.core.review as review_module
import namisync.modules.preflight as preflight_module

from namisync.core.evidence import Outcome
from namisync.core.execution import ExecutionReview, ExecutionSet, validated_run_id
from namisync.core.models import (
    CapabilityProfile,
    DirRecord,
    EntryKind,
    FileIdentity,
    FileRecord,
    MetadataSnapshot,
    Root,
    ScanResult,
    ScanScope,
    UnsupportedReason,
    UnsupportedRecord,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path, to_extended_length_path
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
    Refusal,
    RefusalCode,
    RootObservation,
    StatObservation,
    Subject,
    TrashObservation,
    Verdict,
)
from namisync.core.review import (
    PlanReviewAdmission,
    ReviewFactLimitError,
    ReviewFactLimitExceeded,
)
from namisync.core.root_authority import (
    NativeVolumeInfo,
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
    observe_native_volume,
)
from namisync.core.scalars import MAX_SIGNED_64, ScalarDomainError
from namisync.modules.planner import plan
from namisync.modules.preflight import LocalObservationFileSystem, observe, preflight


NOW = datetime(2026, 7, 18, tzinfo=timezone.utc)
META = MetadataSnapshot(0, 100)
SOURCE_VOLUME = VolumeId("SRC", "NTFS")
TARGET_VOLUME = VolumeId("DST", "NTFS")
PROFILE = CapabilityProfile("NTFS", 100, True, None, 32767, False, True)


def _assert_declared_slots(value: object) -> None:
    assert not hasattr(value, "__dict__")
    assert type(value).__slots__ == tuple(field.name for field in fields(value))
    with pytest.raises(AttributeError):
        object.__setattr__(value, "_undeclared", object())


def test_preflight_contracts_are_exactly_slotted() -> None:
    subject = Subject("source", "FILE.BIN")
    stat_observation = StatObservation(None)
    root_observation = RootObservation(r"C:\source", SOURCE_VOLUME, None)
    trash_observation = TrashObservation(
        r"C:\target\.synctrash",
        True,
        True,
        True,
        True,
        True,
    )
    world = ObservedWorld(
        {subject: stat_observation},
        {subject: "file.bin"},
        frozenset(),
        {"source": root_observation},
        1,
        0,
        trash_observation,
        NOW,
    )
    refusal = Refusal(RefusalCode.OBSERVATION_UNAVAILABLE, subject=subject)
    verdict = Verdict(False, (refusal,), world)
    values = (
        stat_observation,
        root_observation,
        trash_observation,
        world,
        refusal,
        verdict,
    )
    assert tuple(type(value).__name__ for value in values) == (
        "StatObservation",
        "RootObservation",
        "TrashObservation",
        "ObservedWorld",
        "Refusal",
        "Verdict",
    )
    for value in values:
        _assert_declared_slots(value)


def test_observed_world_detaches_mapping_aliases_and_remains_replaceable() -> None:
    subject = Subject("source", "FILE.BIN")
    stats = {subject: StatObservation(None)}
    paths = {subject: "file.bin"}
    roots = {"source": RootObservation(r"C:\source", SOURCE_VOLUME, None)}
    world = ObservedWorld(
        stats,
        paths,
        frozenset(),
        roots,
        1,
        0,
        None,
        NOW,
    )

    stats.clear()
    paths.clear()
    roots.clear()

    assert type(world.stats) is MappingProxyType
    assert type(world.paths) is MappingProxyType
    assert type(world.roots) is MappingProxyType
    assert subject in world.stats
    assert world.paths[subject] == "file.bin"
    assert "source" in world.roots
    with pytest.raises(TypeError):
        world.stats[subject] = StatObservation(None)
    with pytest.raises(TypeError):
        world.paths[subject] = "other.bin"
    with pytest.raises(TypeError):
        world.roots["source"] = RootObservation(
            r"C:\other",
            SOURCE_VOLUME,
            None,
        )
    with pytest.raises(AttributeError):
        world.target_parent_paths.add("other")
    with pytest.raises(FrozenInstanceError):
        world.roots["source"].error = "changed"
    with pytest.raises(FrozenInstanceError):
        world.stats = {}

    copied = replace(world)
    assert copied == world
    assert copied.stats is not world.stats
    assert copied.paths is not world.paths
    assert copied.roots is not world.roots


class _UnreadableMapping(Mapping[object, object]):
    def __getitem__(self, key: object) -> object:
        raise AssertionError(f"mapping was read for {key!r}")

    def __iter__(self):
        raise AssertionError("mapping was iterated")

    def __len__(self) -> int:
        raise AssertionError("mapping length was read")


@pytest.mark.parametrize(
    ("free_space", "reclaimable", "observed_at", "match"),
    [
        (MAX_SIGNED_64 + 1, 0, NOW, "free space"),
        (1, MAX_SIGNED_64 + 1, NOW, "reclaimable temporary bytes"),
        (1, 0, NOW.replace(tzinfo=None), "timezone-aware"),
    ],
)
def test_observed_world_validates_scalars_and_time_before_mapping_copy(
    free_space: int,
    reclaimable: int,
    observed_at: datetime,
    match: str,
) -> None:
    unreadable = _UnreadableMapping()

    with pytest.raises((ScalarDomainError, ValueError), match=match):
        ObservedWorld(
            unreadable,
            unreadable,
            frozenset(),
            unreadable,
            free_space,
            reclaimable,
            None,
            observed_at,
        )


def _native_info(
    authority: RootAuthority,
    volume_id: VolumeId | None = None,
) -> NativeVolumeInfo:
    return NativeVolumeInfo(
        volume_id or authority.expected_volume_id or TARGET_VOLUME,
        VolumeEvidence(
            device_id=(
                authority.reviewed_anchor
                or str(Path(authority.logical_root).anchor)
            )
        ),
        255,
        0,
    )


def _local_authority(path: Path) -> RootAuthority:
    observed = observe_native_volume(path)
    return RootAuthority(
        str(path),
        observed.evidence.device_id,
        observed.volume_id,
    )


def _raise(error: BaseException) -> None:
    raise error


def _explode(probe: str) -> None:
    raise AssertionError(f"authority rejection reached {probe}")


@pytest.mark.parametrize("surface", ("root", "subject", "free-space"))
def test_local_root_authority_failure_stops_before_later_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
) -> None:
    authority = RootAuthority(str(tmp_path), expected_volume_id=TARGET_VOLUME)
    rejected = RootAuthorityError(
        RootAuthorityIssue.REPARSE_COMPONENT,
        str(tmp_path),
        "configured root is a reparse component",
    )
    monkeypatch.setattr(
        preflight_module,
        "admit_root",
        lambda _authority: _raise(rejected),
    )
    monkeypatch.setattr(
        preflight_module,
        "_resolved_logical_path",
        lambda *_args, **_kwargs: _explode("physical resolution"),
    )

    with patch.object(
        preflight_module.shutil,
        "disk_usage",
        side_effect=lambda *_args, **_kwargs: _explode("disk usage"),
    ):
        if surface == "root":
            observation = LocalObservationFileSystem().observe_root(authority)
            assert observation.error is not None
            assert observation.authority_issue is rejected.issue
        else:
            with pytest.raises(RootAuthorityError) as raised:
                if surface == "subject":
                    LocalObservationFileSystem().stat(
                        authority,
                        "payload.bin",
                        PROFILE,
                    )
                else:
                    LocalObservationFileSystem().free_space(authority)
            assert raised.value is rejected


def test_local_missing_subject_stops_before_final_leaf_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = RootAuthority(str(tmp_path), expected_volume_id=TARGET_VOLUME)
    admissions: list[RootAuthority] = []
    monkeypatch.setattr(
        preflight_module,
        "admit_root",
        lambda observed: admissions.append(observed) or _native_info(authority),
    )
    monkeypatch.setattr(
        preflight_module,
        "admit_existing_relative_chain",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        preflight_module,
        "_resolved_logical_path",
        lambda path, *, strict: str(path),
    )

    with patch.object(
        preflight_module.os,
        "stat",
        side_effect=AssertionError("missing subject reached final leaf stat"),
    ):
        observation = LocalObservationFileSystem().stat(
            authority,
            "missing.bin",
            PROFILE,
        )

    assert observation == StatObservation(None)
    assert admissions == [authority]


@pytest.mark.parametrize("surface", ("subject", "temp", "trash"))
def test_local_unsafe_relative_chain_stops_before_later_probes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
) -> None:
    authority = RootAuthority(str(tmp_path), expected_volume_id=TARGET_VOLUME)
    monkeypatch.setattr(
        preflight_module,
        "admit_root",
        lambda _authority: _native_info(authority),
    )
    monkeypatch.setattr(
        preflight_module,
        "admit_existing_relative_chain",
        lambda *_args, **_kwargs: _raise(
            RootAuthorityError(
                RootAuthorityIssue.REPARSE_COMPONENT,
                str(tmp_path / "unsafe"),
                "relative chain is a reparse component",
            )
        ),
    )
    monkeypatch.setattr(
        preflight_module,
        "_resolved_logical_path",
        lambda *_args, **_kwargs: _explode("physical resolution"),
    )
    monkeypatch.setattr(
        preflight_module,
        "observe_native_volume",
        lambda _path: _explode("volume observation"),
    )

    with patch.object(
        preflight_module.os,
        "scandir",
        side_effect=lambda *_args, **_kwargs: _explode("enumeration"),
    ), patch.object(
        preflight_module.os,
        "stat",
        side_effect=lambda *_args, **_kwargs: _explode("leaf stat"),
    ), patch.object(
        preflight_module.os,
        "access",
        side_effect=lambda *_args, **_kwargs: _explode("access probe"),
    ):
        filesystem = LocalObservationFileSystem()
        if surface == "subject":
            observed = filesystem.stat(
                authority,
                r"unsafe\payload.bin",
                PROFILE,
            )
            assert observed.error is not None
        elif surface == "temp":
            assert filesystem.reclaimable_temp_bytes(
                authority,
                frozenset({"unsafe"}),
                "a" * 32,
            ) == 0
        else:
            observed_trash = filesystem.observe_trash(authority)
            assert observed_trash.error is not None
            assert not observed_trash.reparse_safe


def test_local_trash_escape_stops_before_access_and_volume_probes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = RootAuthority(str(tmp_path), expected_volume_id=TARGET_VOLUME)
    escaped = tmp_path.parent / "escaped-trash"
    monkeypatch.setattr(
        preflight_module,
        "admit_root",
        lambda _authority: _native_info(authority),
    )
    monkeypatch.setattr(
        preflight_module,
        "admit_existing_relative_chain",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        preflight_module,
        "_resolved_logical_path",
        lambda path, *, strict: (
            str(tmp_path)
            if os.path.normcase(str(path)) == os.path.normcase(str(tmp_path))
            else str(escaped)
        ),
    )
    monkeypatch.setattr(
        preflight_module,
        "observe_native_volume",
        lambda _path: _explode("volume observation"),
    )

    with patch.object(
        preflight_module.os,
        "access",
        side_effect=lambda *_args, **_kwargs: _explode("access probe"),
    ):
        observed = LocalObservationFileSystem().observe_trash(authority)

    assert observed.resolved_path == str(escaped)
    assert not observed.available
    assert not observed.contained
    assert not observed.same_volume
    assert not observed.writable
    assert not observed.reparse_safe
    assert observed.error == "trash path resolves outside target root"


@pytest.mark.parametrize(
    ("mode", "attributes", "reparse_tag"),
    (
        (stat_module.S_IFREG | 0o644, 0, 0),
        (stat_module.S_IFIFO | 0o644, 0, 0),
        (stat_module.S_IFDIR | 0o755, 0x400, 1),
        (stat_module.S_IFDIR | 0o755, 0x1400, 1),
    ),
)
def test_local_temp_parent_must_be_an_ordinary_directory_before_later_probes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: int,
    attributes: int,
    reparse_tag: int,
) -> None:
    authority = RootAuthority(str(tmp_path), expected_volume_id=TARGET_VOLUME)
    parent_stat = SimpleNamespace(
        st_mode=mode,
        st_file_attributes=attributes,
        st_reparse_tag=reparse_tag,
    )
    monkeypatch.setattr(
        preflight_module,
        "admit_root",
        lambda _authority: _native_info(authority),
    )
    monkeypatch.setattr(
        preflight_module,
        "admit_existing_relative_chain",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        preflight_module,
        "observe_native_volume",
        lambda _path: _explode("volume observation"),
    )

    with patch.object(
        preflight_module.os,
        "stat",
        return_value=parent_stat,
    ), patch.object(
        preflight_module.os,
        "scandir",
        side_effect=lambda *_args, **_kwargs: _explode("enumeration"),
    ):
        reclaimable = LocalObservationFileSystem().reclaimable_temp_bytes(
            authority,
            frozenset({"unsafe"}),
            "a" * 32,
        )

    assert reclaimable == 0


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
        VolumeEvidence(device_id="C:\\"),
        profile,
        files,
        (_dir(""), *directories),
        unsupported,
        (),
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
) -> ExecutionReview:
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
    return ExecutionReview(
        built,
        frozenset(operation.op_id for operation in built.operations if not operation.blocked),
        validated_run_id("a" * 32),
        {},
    )


def _world(xset: ExecutionReview, *, free_space: int = 10_000) -> ObservedWorld:
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


def _codes(xset: ExecutionReview, world: ObservedWorld) -> set[RefusalCode]:
    return {refusal.code for refusal in preflight(xset, world).refusals}


def _world_fact(world: ObservedWorld) -> tuple[object, ...]:
    return (
        dict(world.stats),
        dict(world.paths),
        world.target_parent_paths,
        dict(world.roots),
        world.free_space,
        world.reclaimable_temp_bytes,
        world.trash,
        world.observed_at,
    )


def test_execution_review_detaches_status_and_preserves_remaining_semantics() -> None:
    initial = _xset(
        source_files=(
            _file("first.bin", index=1),
            _file("second.bin", index=2),
            _file("unselected.bin", index=3),
        ),
    )
    operations = initial.plan.operations
    assert len(operations) == 3
    selection = frozenset(operation.op_id for operation in operations[:2])
    pending = ExecutionReview(
        initial.plan,
        selection,
        initial.run_id,
        {},
    )
    assert pending.remaining() == operations[:2]

    first = operations[0]
    source_status = {first.op_id: Outcome.SUCCEEDED}
    review = ExecutionReview(
        initial.plan,
        selection,
        initial.run_id,
        source_status,
    )
    mutable = ExecutionSet(
        initial.plan,
        selection,
        initial.run_id,
        dict(source_status),
    )

    source_status.clear()

    _assert_declared_slots(review)
    assert type(review.status) is MappingProxyType
    assert review.status == {first.op_id: Outcome.SUCCEEDED}
    assert review.remaining() == (operations[1],)
    assert mutable.remaining() == (operations[1],)
    with pytest.raises(TypeError):
        review.status[first.op_id] = Outcome.FAILED
    with pytest.raises(FrozenInstanceError):
        review.selection = frozenset()
    with pytest.raises(FrozenInstanceError):
        review.status = {}

    copied = replace(review)
    assert copied == review
    assert copied.status is not review.status
    assert copied.remaining() == review.remaining()


def test_execution_review_rejects_invalid_run_selection_and_status() -> None:
    review = _xset()
    first = review.remaining()[0]
    unknown = "f" * 32
    if unknown in {operation.op_id for operation in review.plan.operations}:
        unknown = "e" * 32

    with pytest.raises(ValueError, match="run id"):
        replace(review, run_id="not-a-run-id")
    with pytest.raises(TypeError, match="frozenset"):
        ExecutionReview(review.plan, set(review.selection), review.run_id, {})
    with pytest.raises(ValueError, match="unknown operation ids"):
        replace(review, selection=frozenset({unknown}))
    with pytest.raises(ValueError, match="unselected operation ids"):
        ExecutionReview(
            review.plan,
            frozenset(),
            review.run_id,
            {first.op_id: Outcome.SUCCEEDED},
        )
    with pytest.raises(TypeError, match="status values"):
        replace(review, status={first.op_id: object()})
    with pytest.raises(TypeError, match="exact dict or mapping proxy"):
        replace(review, status=_UnreadableMapping())


def test_preflight_requires_execution_review_not_mutable_execution_set() -> None:
    review = _xset()
    mutable = ExecutionSet(
        review.plan,
        review.selection,
        review.run_id,
    )

    with pytest.raises(TypeError, match="exact ExecutionReview"):
        preflight(mutable, _world(review))


def test_pure_preflight_accepts_matching_snapshot_without_filesystem() -> None:
    xset = _xset()
    verdict = preflight(xset, _world(xset))
    assert verdict.ok
    assert verdict.refusals == ()


def test_preflight_review_admission_is_stateless() -> None:
    xset = _xset()
    world = replace(_world(xset), free_space=None)
    admission = PlanReviewAdmission()

    verdict = preflight(xset, world, review_admission=admission)

    assert len(verdict.refusals) == 1
    assert verdict == preflight(xset, world)
    admission.admit(
        domain_rows=review_module.MAX_PLAN_REVIEW_ROWS,
        domain_bytes=review_module.MAX_PLAN_DOMAIN_RETAINED_BYTES,
        informational_rows=review_module.MAX_PLAN_REVIEW_ROWS,
        informational_bytes=(
            review_module.MAX_PLAN_INFORMATIONAL_RETAINED_BYTES
        ),
    )


def test_duplicate_raw_refusals_are_bounded_before_public_deduplication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 2)
    xset = _xset()
    world = replace(_world(xset), roots={})
    admission = PlanReviewAdmission()

    verdict = preflight(xset, world, review_admission=admission)

    assert verdict.refusals == (
        Refusal(
            RefusalCode.ROOT_UNAVAILABLE,
            detail="missing root observation",
        ),
    )
    admission.admit(
        domain_rows=review_module.MAX_PLAN_REVIEW_ROWS,
        domain_bytes=review_module.MAX_PLAN_DOMAIN_RETAINED_BYTES,
        informational_rows=review_module.MAX_PLAN_REVIEW_ROWS,
        informational_bytes=(
            review_module.MAX_PLAN_INFORMATIONAL_RETAINED_BYTES
        ),
    )


def test_refusal_first_excess_does_not_mutate_admission_or_world(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)
    xset = _xset()
    world = replace(_world(xset), roots={})
    before = _world_fact(world)
    admission = PlanReviewAdmission()

    with pytest.raises(ReviewFactLimitError) as caught:
        preflight(xset, world, review_admission=admission)

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_informational_rows()
    )
    assert _world_fact(world) == before
    admission.admit(
        domain_rows=review_module.MAX_PLAN_REVIEW_ROWS,
        domain_bytes=review_module.MAX_PLAN_DOMAIN_RETAINED_BYTES,
        informational_rows=review_module.MAX_PLAN_REVIEW_ROWS,
        informational_bytes=(
            review_module.MAX_PLAN_INFORMATIONAL_RETAINED_BYTES
        ),
    )


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
    xset = ExecutionReview(
        built,
        frozenset({counterpart.op_id}),
        validated_run_id("b" * 32),
        {},
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


@pytest.mark.parametrize(
    ("issue", "expected"),
    (
        (RootAuthorityIssue.ANCHOR_CHANGED, RefusalCode.ROOT_CHANGED),
        (RootAuthorityIssue.VOLUME_CHANGED, RefusalCode.ROOT_CHANGED),
        (
            RootAuthorityIssue.ANCHOR_UNAVAILABLE,
            RefusalCode.ROOT_UNAVAILABLE,
        ),
        (
            RootAuthorityIssue.REPARSE_COMPONENT,
            RefusalCode.ROOT_UNAVAILABLE,
        ),
    ),
)
def test_root_authority_issue_mapping_remains_pure_and_typed(
    issue: RootAuthorityIssue,
    expected: RefusalCode,
) -> None:
    xset = _xset()
    world = _world(xset)
    roots = dict(world.roots)
    roots[xset.plan.source_root.root_id] = RootObservation(
        None,
        None,
        None,
        "root authority rejected",
        issue,
    )

    codes = _codes(xset, replace(world, roots=roots))

    assert expected in codes
    assert (
        RefusalCode.ROOT_UNAVAILABLE
        if expected is RefusalCode.ROOT_CHANGED
        else RefusalCode.ROOT_CHANGED
    ) not in codes


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
    not_closed = ExecutionReview(
        xset.plan,
        frozenset({copy_op.op_id}),
        xset.run_id,
        {},
    )
    assert RefusalCode.SELECTION_NOT_CLOSED in _codes(not_closed, _world(not_closed))

    failed = ExecutionReview(
        xset.plan,
        xset.selection,
        xset.run_id,
        {mkdir.op_id: Outcome.FAILED},
    )
    assert RefusalCode.DEPENDENCY_UNAVAILABLE in _codes(failed, _world(failed))

    blocked = ExecutionReview(
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


def test_capacity_available_bytes_refuses_signed_64_overflow() -> None:
    xset = _xset()

    with pytest.raises(ScalarDomainError, match="available target bytes"):
        preflight(
            xset,
            replace(
                _world(xset, free_space=MAX_SIGNED_64),
                reclaimable_temp_bytes=1,
            ),
        )


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
    before_status = dict(xset.status)
    before_world = _world_fact(world)
    verdict = preflight(xset, world)
    assert not verdict.ok
    assert serialize_plan(xset.plan) == before_plan
    assert xset.selection == before_selection
    assert xset.status == before_status
    assert _world_fact(world) == before_world


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
    def __init__(self, xset: ExecutionReview) -> None:
        self.xset = xset
        self.stat_calls: list[tuple[str, str]] = []
        self.root_calls: list[str] = []
        self.authorities: list[RootAuthority] = []
        self.user_state = b"unchanged"

    def _root_id(self, authority: RootAuthority) -> str:
        return (
            "source"
            if authority.logical_root == self.xset.plan.source_root.path
            else "target"
        )

    def observe_root(
        self,
        authority: RootAuthority,
    ) -> RootObservation:
        root_id = self._root_id(authority)
        self.root_calls.append(root_id)
        self.authorities.append(authority)
        volume = (
            self.xset.plan.source_volume_id
            if root_id == "source"
            else self.xset.plan.target_volume_id
        )
        evidence = (
            self.xset.plan.source_volume_evidence
            if root_id == "source"
            else self.xset.plan.target_volume_evidence
        )
        return RootObservation(authority.logical_root, volume, evidence)

    def stat(
        self,
        authority: RootAuthority,
        rel_path: str,
        profile: CapabilityProfile,
    ) -> StatObservation:
        del profile
        root_id = self._root_id(authority)
        self.stat_calls.append((root_id, rel_path))
        self.authorities.append(authority)
        for operation in self.xset.plan.operations:
            if root_id == "source" and operation.source_rel_path == rel_path:
                return StatObservation(operation.source_expected)
            if root_id == "target" and operation.target_rel_path == rel_path:
                return StatObservation(operation.target_expected)
            if root_id == "target" and operation.prior_target_rel_path == rel_path:
                return StatObservation(operation.prior_target_expected)
        return StatObservation(None)

    def free_space(self, authority: RootAuthority) -> int:
        self.authorities.append(authority)
        return 10_000

    def reclaimable_temp_bytes(
        self,
        authority: RootAuthority,
        parent_paths: frozenset[str],
        current_run_id: str,
    ) -> int:
        self.authorities.append(authority)
        return 0

    def observe_trash(
        self,
        authority: RootAuthority,
    ) -> TrashObservation:
        self.authorities.append(authority)
        return TrashObservation(r"C:\target\.synctrash", True, True, True, True, True)

    def now_utc(self) -> datetime:
        return NOW


def test_observation_is_read_only_and_stats_only_remaining_touched_paths_and_parents() -> None:
    xset = _xset(
        source_files=(_file(r"folder\one.bin", index=1), _file(r"folder\two.bin", index=2)),
        source_directories=(_dir("folder"),),
    )
    first_copy = next(operation for operation in xset.plan.operations if operation.target_rel_path.endswith("one.bin"))
    selected = ExecutionReview(
        xset.plan,
        frozenset({first_copy.op_id}),
        xset.run_id,
        {},
    )
    fs = InstrumentedFileSystem(selected)
    before = fs.user_state
    world = observe(selected, fs)
    assert fs.user_state == before
    assert set(fs.root_calls) == {"source", "target"}
    assert ("source", r"folder\one.bin") in fs.stat_calls
    assert ("target", r"folder\one.bin") in fs.stat_calls
    assert ("target", "folder") in fs.stat_calls
    assert not any(path.endswith("two.bin") for _, path in fs.stat_calls)
    for authority in fs.authorities:
        if authority.logical_root == selected.plan.source_root.path:
            assert authority.reviewed_anchor == "C:\\"
            assert authority.expected_volume_id == SOURCE_VOLUME
        else:
            assert authority.reviewed_anchor == "C:\\"
            assert authority.expected_volume_id == TARGET_VOLUME
    assert world.observed_at is NOW


@pytest.mark.parametrize("rejected_root", ("source", "target"))
def test_observe_gates_rejected_root_but_continues_the_other_root(
    monkeypatch: pytest.MonkeyPatch,
    rejected_root: str,
) -> None:
    xset = _xset(
        source_files=(_file("same.bin", size=20, mtime=2_000),),
        target_files=(
            _file("same.bin", size=10, volume="DST", index=2),
        ),
    )
    filesystem = InstrumentedFileSystem(xset)
    original_root = filesystem.observe_root
    original_stat = filesystem.stat
    original_free_space = filesystem.free_space
    original_reclaimable = filesystem.reclaimable_temp_bytes
    original_trash = filesystem.observe_trash
    trace: list[tuple[str, str]] = []

    def observe_root(authority: RootAuthority) -> RootObservation:
        root_id = filesystem._root_id(authority)
        trace.append(("root", root_id))
        if root_id == rejected_root:
            raise RootAuthorityError(
                RootAuthorityIssue.ANCHOR_CHANGED,
                authority.logical_root,
                f"{root_id} anchor changed",
            )
        return original_root(authority)

    def stat(
        authority: RootAuthority,
        rel_path: str,
        profile: CapabilityProfile,
    ) -> StatObservation:
        root_id = filesystem._root_id(authority)
        if root_id == rejected_root:
            _explode(f"{root_id} stat")
        trace.append(("stat", root_id))
        return original_stat(authority, rel_path, profile)

    def target_probe(name: str, original, authority, *args):
        if rejected_root == "target":
            _explode(name)
        trace.append((name, "target"))
        return original(authority, *args)

    monkeypatch.setattr(filesystem, "observe_root", observe_root)
    monkeypatch.setattr(filesystem, "stat", stat)
    monkeypatch.setattr(
        filesystem,
        "free_space",
        lambda authority: target_probe(
            "free-space", original_free_space, authority
        ),
    )
    monkeypatch.setattr(
        filesystem,
        "reclaimable_temp_bytes",
        lambda authority, parents, run_id: target_probe(
            "reclaimable",
            original_reclaimable,
            authority,
            parents,
            run_id,
        ),
    )
    monkeypatch.setattr(
        filesystem,
        "observe_trash",
        lambda authority: target_probe(
            "trash", original_trash, authority
        ),
    )

    world = observe(xset, filesystem)
    codes = _codes(xset, world)

    assert trace[:2] == [("root", "source"), ("root", "target")]
    assert ("stat", rejected_root) not in trace
    assert ("stat", "target" if rejected_root == "source" else "source") in trace
    target_surfaces = {name for name, root_id in trace if root_id == "target"}
    if rejected_root == "source":
        assert {"free-space", "reclaimable", "trash"} <= target_surfaces
    else:
        assert not {"free-space", "reclaimable", "trash"} & target_surfaces
    assert codes & {
        RefusalCode.ROOT_CHANGED,
        RefusalCode.ROOT_UNAVAILABLE,
    } == {RefusalCode.ROOT_CHANGED}


@pytest.mark.parametrize(
    ("returned_fact", "expected_root_code"),
    (
        ("volume", RefusalCode.ROOT_CHANGED),
        ("anchor", RefusalCode.ROOT_CHANGED),
        ("missing-evidence-and-volume", RefusalCode.ROOT_UNAVAILABLE),
        ("missing-device", RefusalCode.ROOT_UNAVAILABLE),
        ("invalid-device", RefusalCode.ROOT_UNAVAILABLE),
    ),
)
def test_observe_gates_incompatible_returned_target_root_facts(
    monkeypatch: pytest.MonkeyPatch,
    returned_fact: str,
    expected_root_code: RefusalCode,
) -> None:
    xset = _xset(
        source_files=(_file("same.bin", size=20, mtime=2_000),),
        target_files=(
            _file("same.bin", size=10, volume="DST", index=2),
        ),
    )
    filesystem = InstrumentedFileSystem(xset)
    original_root = filesystem.observe_root
    original_stat = filesystem.stat
    trace: list[tuple[str, str]] = []
    returned: list[RootObservation] = []

    def observe_root(authority: RootAuthority) -> RootObservation:
        root_id = filesystem._root_id(authority)
        trace.append(("root", root_id))
        observation = original_root(authority)
        if root_id == "source":
            return observation
        assert observation.volume_id is not None
        wrong_volume = VolumeId("RETURNED", observation.volume_id.fs_type)
        if returned_fact == "volume":
            observation = replace(observation, volume_id=wrong_volume)
        elif returned_fact == "anchor":
            observation = replace(
                observation,
                volume_evidence=VolumeEvidence(device_id="D:\\"),
            )
        elif returned_fact == "missing-evidence-and-volume":
            observation = replace(
                observation,
                volume_id=wrong_volume,
                volume_evidence=None,
            )
        elif returned_fact == "missing-device":
            observation = replace(
                observation,
                volume_evidence=VolumeEvidence(),
            )
        else:
            observation = replace(
                observation,
                volume_evidence=VolumeEvidence(device_id=r"\\.\C:"),
            )
        returned.append(observation)
        return observation

    def stat(
        authority: RootAuthority,
        rel_path: str,
        profile: CapabilityProfile,
    ) -> StatObservation:
        root_id = filesystem._root_id(authority)
        if root_id == "target":
            _explode("target stat")
        trace.append(("stat", root_id))
        return original_stat(authority, rel_path, profile)

    monkeypatch.setattr(filesystem, "observe_root", observe_root)
    monkeypatch.setattr(filesystem, "stat", stat)
    monkeypatch.setattr(
        filesystem,
        "free_space",
        lambda _authority: _explode("free-space probe"),
    )
    monkeypatch.setattr(
        filesystem,
        "reclaimable_temp_bytes",
        lambda *_args: _explode("reclaimable-temp probe"),
    )
    monkeypatch.setattr(
        filesystem,
        "observe_trash",
        lambda _authority: _explode("trash probe"),
    )

    world = observe(xset, filesystem)
    verdict = preflight(xset, world)
    codes = {refusal.code for refusal in verdict.refusals}

    assert trace[:2] == [("root", "source"), ("root", "target")]
    assert ("stat", "source") in trace
    assert returned and world.roots["target"] is returned[0]
    assert returned[0].error is None
    assert returned[0].authority_issue is None
    assert codes & {
        RefusalCode.ROOT_CHANGED,
        RefusalCode.ROOT_UNAVAILABLE,
    } == {expected_root_code}
    root_refusal = next(
        refusal
        for refusal in verdict.refusals
        if refusal.code is expected_root_code
    )
    assert isinstance(root_refusal.detail, str)


def test_later_stat_root_failure_gates_target_while_relative_error_stays_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    xset = _xset(
        source_files=(
            _file("a.bin", size=20, mtime=2_000, index=1),
            _file("b.bin", size=20, mtime=2_000, index=2),
        ),
        target_files=(
            _file("a.bin", size=10, volume="DST", index=11),
            _file("b.bin", size=10, volume="DST", index=12),
        ),
    )
    filesystem = InstrumentedFileSystem(xset)
    original_stat = filesystem.stat
    source_calls: list[str] = []
    target_calls: list[str] = []

    def stat(
        authority: RootAuthority,
        rel_path: str,
        profile: CapabilityProfile,
    ) -> StatObservation:
        root_id = filesystem._root_id(authority)
        if root_id == "source":
            source_calls.append(rel_path)
            if rel_path == "a.bin":
                return StatObservation(None, "relative chain rejected")
            return original_stat(authority, rel_path, profile)
        target_calls.append(rel_path)
        if len(target_calls) > 1:
            _explode("second target stat")
        raise RootAuthorityError(
            RootAuthorityIssue.VOLUME_CHANGED,
            authority.logical_root,
            "target volume changed",
        )

    monkeypatch.setattr(filesystem, "stat", stat)
    monkeypatch.setattr(
        filesystem,
        "free_space",
        lambda _authority: _explode("free-space probe"),
    )
    monkeypatch.setattr(
        filesystem,
        "reclaimable_temp_bytes",
        lambda *_args: _explode("reclaimable-temp probe"),
    )
    monkeypatch.setattr(
        filesystem,
        "observe_trash",
        lambda _authority: _explode("trash probe"),
    )

    codes = _codes(xset, observe(xset, filesystem))

    assert source_calls == ["a.bin", "b.bin"]
    assert target_calls == ["a.bin"]
    assert codes & {
        RefusalCode.ROOT_CHANGED,
        RefusalCode.ROOT_UNAVAILABLE,
    } == {RefusalCode.ROOT_CHANGED}


def test_free_space_root_failure_skips_reclaimable_and_trash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    xset = _xset(
        source_files=(_file("same.bin", size=20, mtime=2_000),),
        target_files=(
            _file("same.bin", size=10, volume="DST", index=2),
        ),
    )
    filesystem = InstrumentedFileSystem(xset)
    free_space_error = RootAuthorityError(
        RootAuthorityIssue.ANCHOR_CHANGED,
        xset.plan.target_root.path,
        "target anchor changed",
    )
    monkeypatch.setattr(
        filesystem,
        "free_space",
        lambda _authority: _raise(free_space_error),
    )
    monkeypatch.setattr(
        filesystem,
        "reclaimable_temp_bytes",
        lambda *_args: _explode("reclaimable-temp probe"),
    )
    monkeypatch.setattr(
        filesystem,
        "observe_trash",
        lambda _authority: _explode("trash probe"),
    )

    world = observe(xset, filesystem)
    codes = _codes(xset, world)

    assert world.free_space is None
    assert world.reclaimable_temp_bytes == 0
    assert world.trash is None
    assert codes & {
        RefusalCode.ROOT_CHANGED,
        RefusalCode.ROOT_UNAVAILABLE,
    } == {RefusalCode.ROOT_CHANGED}


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
    unavailable = tmp_path / "unavailable"
    unavailable.mkdir()
    (unavailable / ("unreadable.bin.synctmp-" + "a" * 32 + "-" + "b" * 32)).write_bytes(
        b"must not hide the safe sibling credit"
    )
    authority = _local_authority(tmp_path)
    expected_volume = authority.expected_volume_id
    assert expected_volume is not None
    monkeypatch.setattr(
        preflight_module,
        "observe_native_volume",
        lambda path: _raise(OSError("parent volume unavailable"))
        if Path(path).name == "unavailable"
        else _native_info(
            authority,
            VolumeId("OTHER", expected_volume.fs_type)
            if Path(path).name == "off-volume"
            else expected_volume,
        ),
    )
    fs = LocalObservationFileSystem()
    assert fs.reclaimable_temp_bytes(
        authority,
        frozenset(
            {"folder", ".synctrash", "off-volume", "unavailable"}
        ),
        "c" * 32,
    ) == 5


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths")
def test_local_observation_uses_native_spelling_but_reports_logical_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_path = tmp_path / "root"
    root_path.mkdir()
    subject = root_path / "payload.bin"
    subject.write_bytes(b"payload")
    authority = _local_authority(root_path)
    observed_paths: list[str] = []
    real_stat = preflight_module.os.stat

    def recording_stat(path, *args, **kwargs):
        observed_paths.append(str(path))
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(preflight_module.os, "stat", recording_stat)
    filesystem = LocalObservationFileSystem()
    root_observation = filesystem.observe_root(authority)
    stat_observation = filesystem.stat(
        authority,
        "payload.bin",
        PROFILE,
    )

    assert root_observation.resolved_path == str(root_path.resolve())
    assert not root_observation.resolved_path.startswith("\\\\?\\")
    assert stat_observation.stat is not None
    assert stat_observation.representable
    assert to_extended_length_path(str(subject)) in observed_paths

    short_profile = replace(PROFILE, max_path=len(str(subject)) - 1)
    assert not filesystem.stat(
        authority, "payload.bin", short_profile
    ).representable


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths")
def test_deep_observation_failure_reports_logical_path_spelling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_path = tmp_path / ("a" * 90) / ("b" * 90) / ("c" * 90)
    assert len(str(root_path)) > 260
    os.makedirs(to_extended_length_path(str(root_path)))
    authority = _local_authority(root_path)
    native_subject = to_extended_length_path(
        str(root_path / "blocked.bin")
    )
    real_stat = preflight_module.os.stat

    def denied_stat(path, *args, **kwargs):
        if str(path) == native_subject:
            raise PermissionError(13, "denied", native_subject)
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(preflight_module.os, "stat", denied_stat)
    observation = LocalObservationFileSystem().stat(
        authority,
        "blocked.bin",
        PROFILE,
    )

    assert observation.stat is None
    assert observation.error is not None
    assert "blocked.bin" in observation.error
    assert "\\\\?\\" not in observation.error


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
    remaining = ExecutionReview(
        original.plan,
        original.selection,
        original.run_id,
        {first.op_id: Outcome.SUCCEEDED},
    )
    required = calculate_required_bytes(
        remaining.remaining(), target_profile=remaining.plan.target_profile, trash_on_update=True
    )
    assert required == 70
    assert RefusalCode.INSUFFICIENT_SPACE in _codes(remaining, _world(remaining, free_space=69))
    assert preflight(remaining, _world(remaining, free_space=70)).ok
