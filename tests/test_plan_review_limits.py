"""Contract tests for finite plan review admission and hostile boundaries."""

from __future__ import annotations

import gc
import stat as stat_module
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone, tzinfo
from types import MappingProxyType, SimpleNamespace
from typing import Callable
from weakref import ref

import pytest

import namisync.core.review as review_module
import namisync.modules.planner as planner_module
import namisync.workflows.sync as sync_workflow_module
from namisync.core.execution import ExecutionSet, validated_run_id
from namisync.core.models import (
    CapabilityProfile, DirRecord, EntryKind, FileIdentity, FileRecord,
    IgnoreSet, MetadataSnapshot, Root, ScanResult, ScanScope, ScanWarning,
    ScanWarningCode, UnsupportedReason, UnsupportedRecord, VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import (
    Assignment, FilterSet, MappingPair, MappingSnapshot, OperationKind,
    OperationReason, Plan, Scope, SyncOptions,
)
from namisync.core.preflight import (
    ObservedWorld, Refusal, RefusalCode, RootObservation, StatObservation,
    Subject, TrashObservation, Verdict,
)
from namisync.core.review import (
    MAX_PLAN_DOMAIN_RETAINED_BYTES, MAX_PLAN_INFORMATIONAL_RETAINED_BYTES,
    MAX_PLAN_REVIEW_ROWS, PlanReviewAdmission, ReviewFactLimitError,
    ReviewFactLimitExceeded, ReviewLimitAxis, ReviewPopulation, ReviewTreeKind,
    consume_plan_review_fact_limit, snapshot_plan_scan_result,
)
from namisync.core.session import Disposition, RunContext, SessionState
from namisync.core.scalars import MAX_SIGNED_64, ScalarDomainError
from namisync.modules.planner import (
    plan, snapshot_mapping_snapshot, snapshot_plan_candidate,
)
from namisync.modules.preflight import (
    observe, preflight, snapshot_plan_observed_world, snapshot_plan_verdict,
)
from namisync.modules.scanner import VolumeSnapshot, WalkingScanner
from namisync.workflows.models import PlanArtifact, PlanRequest
from namisync.workflows.selection import derive_execution_selection
from namisync.workflows.sync import run_plan

META = MetadataSnapshot(0, None)
PROFILE = CapabilityProfile("NTFS", 100, True, False, 32_767, False, True)
NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
SOURCE_ROOT = Root(r"C:\source", "source")
TARGET_ROOT = Root(r"D:\target", "target")


class _PrivatePlanFrameValue:
    pass


def _raise_with_private_plan_frame(
    error: BaseException,
    references: list[ref[_PrivatePlanFrameValue]],
) -> None:
    private = _PrivatePlanFrameValue()
    references.append(ref(private))
    raise error


def _volume(root: Root) -> VolumeId:
    return VolumeId(root.root_id.upper(), "NTFS")

def _evidence(root: Root) -> VolumeEvidence:
    return VolumeEvidence(device_id=str(root.path[:3]))

def _file(
    path: str,
    *,
    size: int = 1,
    mtime_ns: int = 1,
    identity: FileIdentity | None = None,
) -> FileRecord:
    return FileRecord(
        path,
        normalize_relative_path(path),
        size,
        mtime_ns,
        identity,
        1,
        META,
    )

def _directory(path: str) -> DirRecord:
    return DirRecord(
        path,
        normalize_relative_path(path, allow_root=True),
        1,
        META,
        None,
    )

def _unsupported(path: str) -> UnsupportedRecord:
    return UnsupportedRecord(
        path,
        normalize_relative_path(path),
        UnsupportedReason.REPARSE_POINT,
        EntryKind.FILE,
    )

def _scan(
    root: Root,
    *,
    files: tuple[FileRecord, ...] = (),
    directories: tuple[DirRecord, ...] = (),
    unsupported: tuple[UnsupportedRecord, ...] = (),
    warnings: tuple[ScanWarning, ...] = (),
    complete: bool = True,
) -> ScanResult:
    return ScanResult(
        root,
        _volume(root),
        _evidence(root),
        PROFILE,
        files,
        directories,
        unsupported,
        warnings,
        ScanScope.full(),
        complete,
    )

def _forge(value: object, **changes: object) -> object:
    forged = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(
            forged,
            field.name,
            changes.get(field.name, getattr(value, field.name)),
        )
    return forged

def _mapping(source: ScanResult, target: ScanResult) -> MappingSnapshot:
    return MappingSnapshot.empty(source.volume_id, target.volume_id)

def _planned(
    source: ScanResult,
    target: ScanResult,
    mapping: MappingSnapshot | None = None,
    options: SyncOptions = SyncOptions(),
) -> Plan:
    return plan(
        source,
        target,
        mapping or _mapping(source, target),
        options,
        Scope.everything(),
    )

def _xset(value: Plan, token: str = "c" * 32) -> ExecutionSet:
    return ExecutionSet(
        value,
        derive_execution_selection(value).selection,
        validated_run_id(token),
    )

def _fill_final_ledger(admission: PlanReviewAdmission) -> None:
    admission.admit(
        domain_rows=review_module.MAX_PLAN_REVIEW_ROWS,
        domain_bytes=review_module.MAX_PLAN_DOMAIN_RETAINED_BYTES,
        informational_rows=review_module.MAX_PLAN_REVIEW_ROWS,
        informational_bytes=review_module.MAX_PLAN_INFORMATIONAL_RETAINED_BYTES,
    )

class _ObservationFileSystem:
    def __init__(self, source: ScanResult, target: ScanResult) -> None:
        self._records = {
            source.root.root_id: {
                record.rel_path: record.stat
                for record in (*source.files, *source.directories)
            },
            target.root.root_id: {
                record.rel_path: record.stat
                for record in (*target.files, *target.directories)
            },
        }

    def observe_root(self, authority: object) -> RootObservation:
        return RootObservation(
            authority.logical_root,  # type: ignore[attr-defined]
            authority.expected_volume_id,  # type: ignore[attr-defined]
            VolumeEvidence(
                device_id=authority.reviewed_anchor  # type: ignore[attr-defined]
            ),
        )

    def stat(
        self,
        authority: object,
        rel_path: str,
        profile: CapabilityProfile,
    ) -> StatObservation:
        del profile
        logical_root = authority.logical_root  # type: ignore[attr-defined]
        root_id = "source" if logical_root.startswith("C:") else "target"
        return StatObservation(self._records[root_id].get(rel_path))

    def free_space(self, authority: object) -> int:
        del authority
        return 1_000_000

    def reclaimable_temp_bytes(
        self,
        authority: object,
        parent_paths: frozenset[str],
        run_id: str,
    ) -> int:
        del authority, parent_paths, run_id
        return 0

    def observe_trash(self, authority: object) -> TrashObservation:
        return TrashObservation(
            authority.logical_root + r"\.synctrash",  # type: ignore[attr-defined]
            True,
            True,
            True,
            True,
            True,
        )

    def now_utc(self) -> datetime:
        return NOW

@pytest.mark.parametrize(
    ("fact", "population", "axis", "row_limit", "byte_limit"),
    (
        (
            ReviewFactLimitExceeded.plan_domain_rows(),
            ReviewPopulation.DOMAIN,
            ReviewLimitAxis.ROWS,
            MAX_PLAN_REVIEW_ROWS,
            None,
        ),
        (
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
            ReviewPopulation.DOMAIN,
            ReviewLimitAxis.RETAINED_BYTES,
            None,
            MAX_PLAN_DOMAIN_RETAINED_BYTES,
        ),
        (
            ReviewFactLimitExceeded.plan_informational_rows(),
            ReviewPopulation.INFORMATIONAL,
            ReviewLimitAxis.ROWS,
            MAX_PLAN_REVIEW_ROWS,
            None,
        ),
        (
            ReviewFactLimitExceeded.plan_informational_retained_bytes(),
            ReviewPopulation.INFORMATIONAL,
            ReviewLimitAxis.RETAINED_BYTES,
            None,
            MAX_PLAN_INFORMATIONAL_RETAINED_BYTES,
        ),
    ),
)
def test_review_limit_facts_are_exact_typed_contracts(
    fact: ReviewFactLimitExceeded,
    population: ReviewPopulation,
    axis: ReviewLimitAxis,
    row_limit: int | None,
    byte_limit: int | None,
) -> None:
    assert fact == ReviewFactLimitExceeded(
        "review_fact_limit_exceeded",
        ReviewTreeKind.PLAN,
        population,
        axis,
        row_limit,
        byte_limit,
    )

@pytest.mark.parametrize(
    ("charge", "fact"),
    (
        (
            {"domain_rows": MAX_PLAN_REVIEW_ROWS},
            ReviewFactLimitExceeded.plan_domain_rows(),
        ),
        (
            {"domain_bytes": MAX_PLAN_DOMAIN_RETAINED_BYTES},
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
        ),
        (
            {"informational_rows": MAX_PLAN_REVIEW_ROWS},
            ReviewFactLimitExceeded.plan_informational_rows(),
        ),
        (
            {
                "informational_bytes": MAX_PLAN_INFORMATIONAL_RETAINED_BYTES,
            },
            ReviewFactLimitExceeded.plan_informational_retained_bytes(),
        ),
    ),
)
def test_admission_accepts_exact_limit_and_rejects_first_excess(
    charge: dict[str, int],
    fact: ReviewFactLimitExceeded,
) -> None:
    admission = PlanReviewAdmission()
    admission.admit(**charge)
    with pytest.raises(ReviewFactLimitError) as caught:
        admission.admit(**{key: 1 for key in charge})
    assert caught.value.fact == fact

def test_final_admission_is_atomic_with_fixed_precedence() -> None:
    admission = PlanReviewAdmission()
    with pytest.raises(ReviewFactLimitError) as caught:
        admission.admit(
            domain_rows=MAX_PLAN_REVIEW_ROWS + 1,
            domain_bytes=MAX_PLAN_DOMAIN_RETAINED_BYTES + 1,
            informational_rows=MAX_PLAN_REVIEW_ROWS + 1,
        )
    assert caught.value.fact == ReviewFactLimitExceeded.plan_domain_rows()
    _fill_final_ledger(admission)
    with pytest.raises(ReviewFactLimitError):
        admission.admit(domain_rows=1)

    admission = PlanReviewAdmission()
    with pytest.raises(ValueError):
        admission.admit(domain_rows=-1)
    _fill_final_ledger(admission)

def test_source_checks_are_stateless_and_independent_of_final_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 2)
    admission = PlanReviewAdmission()
    admission.require_source_rows(2)
    admission.require_source_rows(2)
    admission.require_informational_source_rows(2)
    admission.require_informational_source_rows(2)
    with pytest.raises(ReviewFactLimitError) as domain:
        admission.require_source_rows(3)
    with pytest.raises(ReviewFactLimitError) as informational:
        admission.require_informational_source_rows(3)
    assert domain.value.fact == ReviewFactLimitExceeded.plan_domain_rows()
    assert informational.value.fact == (
        ReviewFactLimitExceeded.plan_informational_rows()
    )
    _fill_final_ledger(admission)


def test_fresh_admissions_share_only_one_refusal_issuer() -> None:
    root = PlanReviewAdmission()
    sibling = root.fresh()
    fact = ReviewFactLimitExceeded.plan_domain_rows()

    with pytest.raises(ReviewFactLimitError) as issued:
        sibling.require_source_rows(MAX_PLAN_REVIEW_ROWS + 1)
    snapshot = consume_plan_review_fact_limit(issued.value, root)

    assert snapshot == fact
    assert snapshot is not issued.value.fact

    with pytest.raises(ReviewFactLimitError) as unrelated:
        PlanReviewAdmission().require_source_rows(MAX_PLAN_REVIEW_ROWS + 1)
    assert consume_plan_review_fact_limit(unrelated.value, root) is None
    assert (
        consume_plan_review_fact_limit(ReviewFactLimitError(fact), root)
        is None
    )

def test_scan_domain_and_warning_sources_are_independently_admitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 2)
    value = _scan(
        SOURCE_ROOT,
        files=(_file("one.bin"),),
        directories=(_directory("folder"),),
        warnings=(
            ScanWarning(ScanWarningCode.DISAPPEARED, "one.bin"),
            ScanWarning(ScanWarningCode.ACCESS_DENIED, "folder"),
        ),
    )
    admission = PlanReviewAdmission()
    assert snapshot_plan_scan_result(value, admission) == value
    _fill_final_ledger(admission)


def test_scan_snapshot_validates_malformed_first_excess_before_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)
    record = _file("valid.bin")
    value = _scan(SOURCE_ROOT, files=(record, record))
    object.__setattr__(value, "files", (record, object()))

    with pytest.raises(TypeError):
        snapshot_plan_scan_result(value, PlanReviewAdmission())


def test_scan_snapshot_validates_domain_before_informational_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)
    record = _file("forged.bin")
    warning = ScanWarning(ScanWarningCode.DISAPPEARED, "gone.bin")
    value = _scan(
        SOURCE_ROOT,
        files=(record,),
        warnings=(warning, warning),
    )
    object.__setattr__(record, "rel_path_key", "NOT-THE-PATH")

    with pytest.raises(ValueError):
        snapshot_plan_scan_result(value, PlanReviewAdmission())


def test_scan_snapshot_validates_malformed_informational_first_excess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)
    warning = ScanWarning(ScanWarningCode.DISAPPEARED, "gone.bin")
    value = _scan(SOURCE_ROOT, warnings=(warning, warning))
    object.__setattr__(value, "warnings", (warning, object()))

    with pytest.raises(TypeError):
        snapshot_plan_scan_result(value, PlanReviewAdmission())


def _two_mapping_items() -> dict[str, object]:
    source_ids = (FileIdentity("SOURCE", 1), FileIdentity("SOURCE", 2))
    target_ids = (FileIdentity("TARGET", 1), FileIdentity("TARGET", 2))
    return {
        "pairs": tuple(
            MappingPair(
                normalize_relative_path(f"source{index}.bin"),
                f"target{index}.bin",
                normalize_relative_path(f"target{index}.bin"),
                source_ids[index],
                target_ids[index],
            )
            for index in range(2)
        ),
        "ambiguous_source_keys": frozenset({"ONE.BIN", "TWO.BIN"}),
        "disqualified_source_identities": frozenset(source_ids),
        "disqualified_target_identities": frozenset(target_ids),
    }

def test_mapping_source_populations_are_independent_not_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 2)
    source = _scan(SOURCE_ROOT)
    target = _scan(TARGET_ROOT)
    value = MappingSnapshot(
        source.volume_id,
        target.volume_id,
        **_two_mapping_items(),
    )
    admission = PlanReviewAdmission()
    assert snapshot_mapping_snapshot(value, review_admission=admission) == value
    _fill_final_ledger(admission)

class _DeepcopyBomb:
    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise AssertionError("undeclared graph was copied")

class _DeclaredMapping(Mapping[object, object]):
    def __init__(self, values: Mapping[object, object]) -> None:
        self._values = dict(values)

    def __getitem__(self, key: object) -> object:
        return self._values[key]

    def __iter__(self) -> Iterator[object]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise AssertionError("declared mapping was deep-copied")

class _LyingLengthMapping(_DeclaredMapping):
    def __len__(self) -> int:
        return MAX_PLAN_REVIEW_ROWS + 1

class _DuplicateItemMapping(_DeclaredMapping):
    def __iter__(self) -> Iterator[object]:
        key = next(iter(self._values))
        yield key
        yield key

class _UtcAlias(tzinfo):
    def utcoffset(self, value: datetime | None) -> timedelta:
        del value
        return timedelta(0)

    def dst(self, value: datetime | None) -> timedelta:
        del value
        return timedelta(0)

def _attach_bomb(value: object) -> None:
    object.__setattr__(value, "_undeclared", _DeepcopyBomb())

def test_scan_snapshot_reconstructs_declared_typed_fields() -> None:
    record = _file("file.bin", identity=FileIdentity("SOURCE", 1))
    value = _scan(
        SOURCE_ROOT,
        files=(record,),
        directories=(_directory("folder"),),
        unsupported=(_unsupported("link.bin"),),
        warnings=(ScanWarning(ScanWarningCode.DISAPPEARED, "gone.bin"),),
    )
    snapshot = snapshot_plan_scan_result(value, PlanReviewAdmission())
    assert snapshot == value
    assert snapshot is not value and snapshot.files[0] is not record

def test_mapping_and_plan_snapshots_drop_hidden_graphs_and_preserve_semantics() -> None:
    source = _scan(SOURCE_ROOT, files=(_file("file.bin"),))
    target = _scan(TARGET_ROOT)
    mapping = _mapping(source, target)
    _attach_bomb(mapping)
    copied_mapping = snapshot_mapping_snapshot(mapping)
    assert copied_mapping == mapping and copied_mapping is not mapping
    assert not hasattr(copied_mapping, "_undeclared")

    raw_plan = _planned(source, target, mapping)
    _attach_bomb(raw_plan)
    _attach_bomb(raw_plan.operations[0])
    copied_plan = snapshot_plan_candidate(raw_plan, source, target, SyncOptions())
    assert copied_plan == raw_plan
    assert copied_plan.fingerprint == raw_plan.fingerprint
    assert copied_plan is not raw_plan
    assert copied_plan.operations[0] is not raw_plan.operations[0]
    assert not hasattr(copied_plan, "_undeclared")
    assert not hasattr(copied_plan.operations[0], "_undeclared")

    hostile_fingerprint = replace(raw_plan, fingerprint="f" * 64)
    with pytest.raises(ValueError, match="fingerprint"):
        snapshot_plan_candidate(
            hostile_fingerprint,
            source,
            target,
            SyncOptions(),
        )


def test_plan_candidate_failure_keeps_identity_after_frame_retirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _scan(SOURCE_ROOT, files=(_file("source.bin"),))
    target = _scan(TARGET_ROOT)
    raw_plan = _planned(source, target)
    failure = ValueError("fingerprint callback failed")
    references: list[ref[_PrivatePlanFrameValue]] = []

    def fail_fingerprint(value: object) -> str:
        del value
        _raise_with_private_plan_frame(failure, references)

    monkeypatch.setattr(planner_module, "plan_fingerprint", fail_fingerprint)

    with pytest.raises(ValueError) as raised:
        snapshot_plan_candidate(raw_plan, source, target, SyncOptions())

    assert raised.value is failure
    gc.collect()
    assert references and all(reference() is None for reference in references)


def test_world_and_verdict_accept_declared_mappings_and_zero_offset_utc_alias() -> None:
    source = _scan(SOURCE_ROOT)
    target = _scan(TARGET_ROOT, files=(_file("obsolete.bin"),))
    value_plan = _planned(source, target)
    xset = _xset(value_plan)
    ordinary = observe(xset, _ObservationFileSystem(source, target))
    alias_time = datetime(2026, 8, 27, 12, 0, tzinfo=_UtcAlias())
    raw_world = ObservedWorld(
        _DeclaredMapping(ordinary.stats),
        _DeclaredMapping(ordinary.paths),
        ordinary.target_parent_paths,
        _DeclaredMapping(ordinary.roots),
        ordinary.free_space,
        ordinary.reclaimable_temp_bytes,
        ordinary.trash,
        alias_time,
    )
    _attach_bomb(raw_world)
    captured = snapshot_plan_observed_world(
        raw_world,
        xset,
        PlanReviewAdmission(),
    )
    assert captured == replace(ordinary, observed_at=NOW)
    assert isinstance(captured.stats, MappingProxyType)
    assert captured.observed_at.tzinfo is timezone.utc
    assert not hasattr(captured, "_undeclared")

    raw_verdict = Verdict(
        False,
        (
            Refusal(RefusalCode.ROOTS_OVERLAP, detail="first"),
            Refusal(RefusalCode.ROOT_CHANGED, detail="second"),
        ),
        captured,
    )
    _attach_bomb(raw_verdict)
    verdict = snapshot_plan_verdict(
        raw_verdict,
        captured,
        captured,
        xset,
        PlanReviewAdmission(),
    )
    assert verdict.refusals == raw_verdict.refusals
    assert verdict.observed is captured
    assert not hasattr(verdict, "_undeclared")

def test_world_snapshot_uses_enumerated_mapping_items_and_rejects_duplicates() -> None:
    source = _scan(SOURCE_ROOT)
    target = _scan(TARGET_ROOT, files=(_file("obsolete.bin"),))
    value_plan = _planned(source, target)
    xset = _xset(value_plan)
    ordinary = observe(xset, _ObservationFileSystem(source, target))

    captured = snapshot_plan_observed_world(
        replace(
            ordinary,
            stats=_LyingLengthMapping(ordinary.stats),
            paths=_LyingLengthMapping(ordinary.paths),
            roots=_LyingLengthMapping(ordinary.roots),
        ),
        xset,
        PlanReviewAdmission(),
    )
    assert captured == ordinary

    with pytest.raises(ValueError, match="duplicate stat subject"):
        snapshot_plan_observed_world(
            replace(
                ordinary,
                stats=_DuplicateItemMapping(ordinary.stats),
            ),
            xset,
            PlanReviewAdmission(),
        )

def _scanner_stat(*, directory: bool, inode: int) -> SimpleNamespace:
    return SimpleNamespace(
        st_mode=(
            stat_module.S_IFDIR | 0o755
            if directory
            else stat_module.S_IFREG | 0o644
        ),
        st_ino=inode,
        st_size=0 if directory else 1,
        st_mtime_ns=1,
        st_birthtime_ns=1,
        st_file_attributes=0,
        st_nlink=1,
    )

class _ScannerEntry:
    name = "stable.bin"
    path = r"C:\source\stable.bin"

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        assert not follow_symlinks
        return False

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        assert not follow_symlinks
        return True

    def stat(self, *, follow_symlinks: bool = True) -> SimpleNamespace:
        assert not follow_symlinks
        return _scanner_stat(directory=False, inode=2)

class _ScannerBackend:
    def __init__(self, *, fail_enumeration: bool = False) -> None:
        self.fail_enumeration = fail_enumeration

    def resolve_root(self, path: str) -> str:
        return path

    def volume_snapshot(self, root: str) -> VolumeSnapshot:
        del root
        return VolumeSnapshot(
            _volume(SOURCE_ROOT),
            _evidence(SOURCE_ROOT),
            PROFILE,
        )

    def lstat(self, path: str) -> SimpleNamespace:
        del path
        return _scanner_stat(directory=True, inode=1)

    @contextmanager
    def scandir(self, path: str):
        del path
        if self.fail_enumeration:
            class _Failure:
                def __iter__(self) -> "_Failure":
                    return self

                def __next__(self) -> object:
                    raise OSError("enumeration failed")

            yield _Failure()
        else:
            yield iter((_ScannerEntry(),))

@pytest.mark.parametrize("fail_enumeration", (False, True))
def test_protected_scanner_matches_ordinary_output(
    fail_enumeration: bool,
) -> None:
    ctx = RunContext(lambda event: None, lambda: None)
    ordinary = WalkingScanner(
        _ScannerBackend(fail_enumeration=fail_enumeration)
    ).scan(SOURCE_ROOT, IgnoreSet(), ctx)
    protected = WalkingScanner(
        _ScannerBackend(fail_enumeration=fail_enumeration)
    ).scan(
        SOURCE_ROOT,
        IgnoreSet(),
        ctx,
        review_admission=PlanReviewAdmission(),
    )
    assert protected == ordinary

def _parity_case(
    name: str,
) -> tuple[
    ScanResult,
    ScanResult,
    MappingSnapshot,
    Callable[[Plan, Verdict], bool],
]:
    if name == "representative":
        source = _scan(
            SOURCE_ROOT,
            files=(
                _file(r"folder\copy.bin", size=5),
                _file("same.bin", size=3),
                _file("update.bin", size=4),
            ),
            directories=(_directory("folder"),),
        )
        target = _scan(
            TARGET_ROOT,
            files=(
                _file("obsolete.bin", size=7),
                _file("same.bin", size=3),
                _file("update.bin", size=2),
            ),
        )
        marker = lambda value, verdict: (
            {operation.kind for operation in value.operations}
            == {
                OperationKind.MKDIR,
                OperationKind.COPY,
                OperationKind.NOOP,
                OperationKind.UPDATE,
                OperationKind.TRASH,
            }
        )
        return source, target, _mapping(source, target), marker
    if name == "identity":
        source_identity = FileIdentity("SOURCE", 1)
        target_identity = FileIdentity("TARGET", 2)
        source = _scan(
            SOURCE_ROOT,
            files=(_file("new.bin", identity=source_identity),),
        )
        target = _scan(
            TARGET_ROOT,
            files=(_file("old.bin", identity=target_identity),),
        )
        mapping = MappingSnapshot(
            source.volume_id,
            target.volume_id,
            pairs=(
                MappingPair(
                    normalize_relative_path("new.bin"),
                    "old.bin",
                    normalize_relative_path("old.bin"),
                    source_identity,
                    target_identity,
                ),
            ),
        )
        marker = lambda value, verdict: any(
            operation.kind is OperationKind.MOVE
            for operation in value.operations
        )
        return source, target, mapping, marker
    if name == "unsupported":
        source = _scan(
            SOURCE_ROOT,
            unsupported=(_unsupported("link.bin"),),
        )
        target = _scan(TARGET_ROOT)
        marker = lambda value, verdict: any(
            operation.blocked_reason is not None
            for operation in value.operations
        )
        return source, target, _mapping(source, target), marker
    if name == "incomplete":
        source = _scan(SOURCE_ROOT, complete=False)
        target = _scan(TARGET_ROOT, files=(_file("obsolete.bin"),))
        marker = lambda value, verdict: (
            not value.source_complete and verdict.ok
        )
        return source, target, _mapping(source, target), marker
    source = _scan(SOURCE_ROOT)
    target = _scan(
        TARGET_ROOT,
        files=(_file(r"obsolete\file.bin"),),
        directories=(_directory("obsolete"),),
    )
    marker = lambda value, verdict: any(
        operation.reason is OperationReason.DIRECTORY_CLEANUP
        for operation in value.operations
    )
    return source, target, _mapping(source, target), marker

@pytest.mark.parametrize(
    "name",
    ("representative", "identity", "unsupported", "incomplete", "cleanup"),
)
def test_protected_planner_observer_and_preflight_match_ordinary_semantics(
    name: str,
) -> None:
    source, target, mapping, marker = _parity_case(name)
    ordinary_plan = plan(
        source,
        target,
        mapping,
        SyncOptions(),
        Scope.everything(),
    )
    protected_plan = plan(
        source,
        target,
        mapping,
        SyncOptions(),
        Scope.everything(),
        review_admission=PlanReviewAdmission(),
    )
    assert protected_plan == ordinary_plan
    assert protected_plan.fingerprint == ordinary_plan.fingerprint

    fs = _ObservationFileSystem(source, target)
    ordinary_xset = _xset(ordinary_plan)
    protected_xset = _xset(protected_plan)
    ordinary_world = observe(ordinary_xset, fs)
    protected_world = observe(
        protected_xset,
        fs,
        review_admission=PlanReviewAdmission(),
    )
    assert protected_world == ordinary_world

    ordinary_verdict = preflight(ordinary_xset, ordinary_world)
    protected_verdict = preflight(
        protected_xset,
        protected_world,
        review_admission=PlanReviewAdmission(),
    )
    assert protected_verdict == ordinary_verdict
    assert marker(protected_plan, protected_verdict)

@pytest.mark.parametrize("mode", ("noop", "excluded"))
def test_scan_wide_logical_sum_does_not_refuse_noncopy_work(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    _patch_workflow_roots(monkeypatch)
    files = (
        _file("one.bin", size=MAX_SIGNED_64),
        _file("two.bin", size=MAX_SIGNED_64),
    )
    source = _scan(SOURCE_ROOT, files=files)
    target = _scan(TARGET_ROOT, files=files if mode == "noop" else ())
    options = (
        SyncOptions()
        if mode == "noop"
        else SyncOptions(filters=FilterSet(("*.bin",)))
    )
    saved: list[PlanArtifact] = []

    def scanner(root, ignores, ctx, *, review_admission=None):
        del ignores, ctx, review_admission
        return source if root.root_id == "source" else target

    deps = _workflow_dependencies(saved, scanner=scanner)
    deps.observation_fs = _ObservationFileSystem(source, target)
    result = run_plan(
        _workflow_request(options),
        RunContext(lambda event: None, lambda: None),
        deps,
    )
    assert result.status is SessionState.COMPLETED
    kinds = {operation.kind for operation in saved[0].plan.operations}
    assert kinds == ({OperationKind.NOOP} if mode == "noop" else set())

def test_planner_required_bytes_remains_logical_overflow_owner() -> None:
    source = _scan(
        SOURCE_ROOT,
        files=(
            _file("maximum.bin", size=MAX_SIGNED_64),
            _file("extra.bin", size=1),
        ),
    )
    target = _scan(TARGET_ROOT)
    for admission in (None, PlanReviewAdmission()):
        with pytest.raises(ReviewFactLimitError) as caught:
            plan(
                source,
                target,
                _mapping(source, target),
                SyncOptions(),
                Scope.everything(),
                review_admission=admission,
            )
        assert caught.value.fact == ReviewFactLimitExceeded.plan_logical_bytes()
        assert isinstance(caught.value.__cause__, ScalarDomainError)

def _patch_workflow_roots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sync_workflow_module,
        "_validated_roots",
        lambda source, target: (
            Root(source, "source"),
            Root(target, "target"),
        ),
    )

def _workflow_request(options: SyncOptions = SyncOptions()) -> PlanRequest:
    return PlanRequest("a" * 32, SOURCE_ROOT.path, TARGET_ROOT.path, options)

def _workflow_scanner(
    root: Root,
    ignores: IgnoreSet,
    ctx: RunContext,
    *,
    review_admission: PlanReviewAdmission | None = None,
) -> ScanResult:
    del ignores, ctx, review_admission
    return _scan(
        root,
        files=(_file("source.bin"),) if root.root_id == "source" else (),
    )

def _workflow_correspondence(
    source: ScanResult,
    target: ScanResult,
    *,
    review_admission: PlanReviewAdmission | None = None,
) -> MappingSnapshot:
    del review_admission
    return _mapping(source, target)

def _workflow_dependencies(
    saved: list[PlanArtifact],
    *,
    scanner: object = _workflow_scanner,
    correspondence: object = _workflow_correspondence,
) -> SimpleNamespace:
    source = _scan(SOURCE_ROOT, files=(_file("source.bin"),))
    target = _scan(TARGET_ROOT)
    return SimpleNamespace(
        scanner=scanner,
        ignores=IgnoreSet(),
        correspondence=correspondence,
        planner=plan,
        observer=observe,
        observation_fs=_ObservationFileSystem(source, target),
        preflight=preflight,
        save_plan=saved.append,
    )

def _run(deps: object) -> object:
    return run_plan(
        _workflow_request(),
        RunContext(lambda event: None, lambda: None),
        deps,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    "owner",
    (
        "event",
        "scanner",
        "correspondence",
        "planner",
        "observer",
        "preflight",
        "save",
    ),
)
def test_run_plan_retires_phase_failure_frames_without_changing_identity(
    monkeypatch: pytest.MonkeyPatch,
    owner: str,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    deps = _workflow_dependencies(saved)
    failure = RuntimeError(f"{owner} failed")
    references: list[ref[_PrivatePlanFrameValue]] = []

    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        _raise_with_private_plan_frame(failure, references)

    if owner != "event":
        attribute = "save_plan" if owner == "save" else owner
        setattr(deps, attribute, fail)
    emit = fail if owner == "event" else lambda event: None

    with pytest.raises(RuntimeError) as raised:
        run_plan(
            _workflow_request(),
            RunContext(emit, lambda: None),
            deps,
        )

    assert raised.value is failure
    assert saved == []
    gc.collect()
    assert references and all(reference() is None for reference in references)


@pytest.mark.parametrize(
    ("population", "limit"),
    (
        ("scan-domain", 1),
        ("scan-warnings", 1),
        ("mapping-pairs", 1),
        ("mapping-ambiguous", 1),
        ("mapping-disqualified-source", 1),
        ("mapping-disqualified-target", 1),
        ("plan-assignment", 1),
        ("plan-operations", 1),
        ("world-stats", 1),
        ("world-paths", 1),
        ("world-parents", 1),
        ("world-roots", 1),
        ("verdict-refusals", 2),
    ),
)
def test_each_raw_population_refuses_first_excess_before_save(
    monkeypatch: pytest.MonkeyPatch,
    population: str,
    limit: int,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", limit)
    _patch_workflow_roots(monkeypatch)
    calls: list[str] = []
    saved: list[PlanArtifact] = []

    def scanner(
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ScanResult:
        del ignores, ctx, review_admission
        calls.append(f"scan-{root.root_id}")
        if root.root_id == "source" and population == "scan-domain":
            return _scan(
                root,
                files=(_file("one.bin"), _file("two.bin")),
            )
        if root.root_id == "source" and population == "scan-warnings":
            return _scan(
                root,
                warnings=(
                    ScanWarning(ScanWarningCode.DISAPPEARED, "one.bin"),
                    ScanWarning(ScanWarningCode.DISAPPEARED, "two.bin"),
                ),
            )
        if population.startswith("world-"):
            identity = FileIdentity(root.root_id.upper(), 1)
            return _scan(
                root,
                files=(
                    _file(
                        "new.bin" if root.root_id == "source" else "old.bin",
                        identity=identity,
                    ),
                ),
            )
        if population == "verdict-refusals":
            return _scan(
                root,
                files=(_file("obsolete.bin"),)
                if root.root_id == "target"
                else (),
            )
        if population == "plan-assignment":
            return _scan(
                root,
                files=(_file("one.bin"),)
                if root.root_id == "source"
                else (),
            )
        if population == "plan-operations":
            return _scan(
                root,
                files=(_file("one.bin"),)
                if root.root_id == "target"
                else (),
            )
        return _scan(root)

    def correspondence(
        source: ScanResult,
        target: ScanResult,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> MappingSnapshot:
        del review_admission
        calls.append("correspondence")
        if population.startswith("world-"):
            source_identity = source.files[0].file_identity
            target_identity = target.files[0].file_identity
            assert source_identity is not None and target_identity is not None
            return MappingSnapshot(
                source.volume_id,
                target.volume_id,
                pairs=(
                    MappingPair(
                        normalize_relative_path("new.bin"),
                        "old.bin",
                        normalize_relative_path("old.bin"),
                        source_identity,
                        target_identity,
                    ),
                ),
            )
        values = _two_mapping_items()
        mapping_fields = {
            "mapping-pairs": "pairs",
            "mapping-ambiguous": "ambiguous_source_keys",
            "mapping-disqualified-source": "disqualified_source_identities",
            "mapping-disqualified-target": "disqualified_target_identities",
        }
        if population in mapping_fields:
            field_name = mapping_fields[population]
            return replace(
                _mapping(source, target),
                **{field_name: values[field_name]},
            )
        return _mapping(source, target)

    def planner(
        source: ScanResult,
        target: ScanResult,
        mapping: MappingSnapshot,
        options: SyncOptions,
        scope: Scope,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Plan:
        calls.append("planner")
        value = plan(
            source,
            target,
            mapping,
            options,
            scope,
        )
        if population == "plan-assignment":
            item = value.assignment.items[0]
            assignment = _forge(
                value.assignment,
                items=(item, item),
            )
            return _forge(value, assignment=assignment)  # type: ignore[return-value]
        if population == "plan-operations":
            operation = value.operations[0]
            return _forge(  # type: ignore[return-value]
                value,
                operations=(operation, operation),
            )
        del review_admission
        return value

    def observer(
        execution_set: ExecutionSet,
        fs: object,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ObservedWorld:
        del review_admission
        calls.append("observer")
        world = observe(execution_set, fs)  # type: ignore[arg-type]
        if population == "world-stats":
            return replace(
                world,
                paths={},
                roots={},
            )
        if population == "world-paths":
            return replace(
                world,
                stats={},
                roots={},
            )
        if population == "world-parents":
            return replace(
                world,
                stats={},
                paths={},
                target_parent_paths=frozenset({"one", "two"}),
                roots={},
            )
        if population == "world-roots":
            return replace(world, stats={}, paths={})
        return world

    def preflight_callback(
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict:
        del execution_set, review_admission
        calls.append("preflight")
        if population == "verdict-refusals":
            return Verdict(
                False,
                tuple(
                    Refusal(RefusalCode.ROOTS_OVERLAP, detail=str(index))
                    for index in range(3)
                ),
                world,
            )
        raise AssertionError("preflight should not be reached")

    deps = _workflow_dependencies(
        saved,
        scanner=scanner,
        correspondence=correspondence,
    )
    deps.planner = planner
    deps.observer = observer
    deps.preflight = preflight_callback
    result = _run(deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    expected_fact = (
        ReviewFactLimitExceeded.plan_informational_rows()
        if population in {"scan-warnings", "verdict-refusals"}
        else ReviewFactLimitExceeded.plan_domain_rows()
    )
    assert result.review_fact_limit == expected_fact
    if population.startswith("scan-"):
        assert "scan-source" in calls and "scan-target" not in calls
    elif population.startswith("mapping-"):
        assert "correspondence" in calls and "planner" not in calls
    elif population.startswith("plan-"):
        assert "planner" in calls and "observer" not in calls
    elif population.startswith("world-"):
        assert "observer" in calls and "preflight" not in calls
    else:
        assert "preflight" in calls
    assert saved == []


def test_workflow_copies_and_retires_owned_review_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PrivateGraph:
        pass

    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    retained_errors: list[BaseException] = []
    graph_references = []
    original_fact = ReviewFactLimitExceeded.plan_domain_rows()

    def scanner(
        *_args,
        review_admission: PlanReviewAdmission | None = None,
        **_kwargs,
    ):
        assert review_admission is not None
        graph = PrivateGraph()
        graph_references.append(ref(graph))
        try:
            review_admission.require_source_rows(MAX_PLAN_REVIEW_ROWS + 1)
        except ReviewFactLimitError as error:
            retained_errors.append(error)
            raise

    result = _run(_workflow_dependencies(saved, scanner=scanner))

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert result.review_fact_limit == original_fact
    assert result.review_fact_limit is not original_fact
    assert saved == []
    assert retained_errors
    assert all(
        BaseException.__dict__["__traceback__"].__get__(error, type(error))
        is None
        and BaseException.__dict__["__cause__"].__get__(error, type(error))
        is None
        and BaseException.__dict__["__context__"].__get__(error, type(error))
        is None
        for error in retained_errors
    )
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)


@pytest.mark.parametrize(
    ("source", "expected_message"),
    (
        ("event", "unadmitted collaborator raised a review fact limit"),
        (
            "correspondence",
            "unadmitted collaborator raised a review fact limit",
        ),
        (
            "policy",
            "unadmitted collaborator raised a review fact limit",
        ),
        (
            "scanner-unissued",
            "unadmitted collaborator raised a review fact limit",
        ),
        ("scanner-malformed", "plan review limit failure is invalid"),
        ("scanner-subclass", "plan review limit failure is invalid"),
    ),
)
def test_spoofed_review_limit_fails_instead_of_refusing(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    expected_message: str,
) -> None:
    class SpoofedReviewLimit(ReviewFactLimitError):
        pass

    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    raw_fact = ReviewFactLimitExceeded.plan_domain_rows()
    if source == "scanner-malformed":
        object.__setattr__(raw_fact, "axis", "rows")
    raw_error = (
        SpoofedReviewLimit(raw_fact)
        if source == "scanner-subclass"
        else ReviewFactLimitError(raw_fact)
    )

    def raise_spoof(*_args, **_kwargs):
        raise raw_error

    deps = _workflow_dependencies(
        saved,
        scanner=(
            raise_spoof
            if source in {
                "scanner-unissued",
                "scanner-malformed",
                "scanner-subclass",
            }
            else _workflow_scanner
        ),
        correspondence=(
            raise_spoof
            if source == "correspondence"
            else _workflow_correspondence
        ),
    )
    options = SyncOptions()
    if source == "policy":
        class SpoofingPolicy:
            name = "spoof"
            version = "1"

            def assign(self, *_args):
                raise raw_error

        options = SyncOptions(
            destination_policy=SpoofingPolicy(),  # type: ignore[arg-type]
        )
    emit = raise_spoof if source == "event" else lambda event: None

    with pytest.raises(RuntimeError, match=f"^{expected_message}$") as raised:
        run_plan(
            _workflow_request(options),
            RunContext(emit, lambda: None),
            deps,
        )

    assert raised.value.__cause__ is raised.value.__context__ is None
    assert saved == []
    assert BaseException.__dict__["__traceback__"].__get__(
        raw_error, type(raw_error)
    ) is None
    assert BaseException.__dict__["__cause__"].__get__(
        raw_error, type(raw_error)
    ) is None
    assert BaseException.__dict__["__context__"].__get__(
        raw_error, type(raw_error)
    ) is None


@pytest.mark.parametrize("source", ("scanner-backend", "clock", "world-mapping"))
def test_nested_collaborator_cannot_launder_unissued_review_limit(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    raw_error = ReviewFactLimitError(
        ReviewFactLimitExceeded.plan_domain_rows()
    )

    class SpoofingBackend(_ScannerBackend):
        def resolve_root(self, path: str) -> str:
            del path
            raise raw_error

    class SpoofingClock(_ObservationFileSystem):
        def now_utc(self) -> datetime:
            raise raw_error

    class SpoofingMapping(Mapping[Subject, StatObservation]):
        def __len__(self) -> int:
            return 0

        def __iter__(self) -> Iterator[Subject]:
            raise raw_error

        def __getitem__(self, key: Subject) -> StatObservation:
            raise KeyError(key)

    deps = _workflow_dependencies(saved)
    if source == "scanner-backend":
        deps.scanner = WalkingScanner(SpoofingBackend()).scan
    elif source == "clock":
        deps.observation_fs = SpoofingClock(
            _scan(SOURCE_ROOT, files=(_file("source.bin"),)),
            _scan(TARGET_ROOT),
        )
    else:
        def observer(
            execution_set: ExecutionSet,
            fs: object,
            *,
            review_admission: PlanReviewAdmission | None = None,
        ) -> ObservedWorld:
            world = observe(
                execution_set,
                fs,  # type: ignore[arg-type]
                review_admission=review_admission,
            )
            return replace(world, stats=SpoofingMapping())

        deps.observer = observer

    with pytest.raises(
        RuntimeError,
        match="^unadmitted collaborator raised a review fact limit$",
    ) as raised:
        _run(deps)

    assert raised.value.__cause__ is raised.value.__context__ is None
    assert saved == []
    assert BaseException.__dict__["__traceback__"].__get__(
        raw_error,
        type(raw_error),
    ) is None


def test_issued_non_plan_fact_is_invalid_and_never_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    retained_errors: list[ReviewFactLimitError] = []

    def scanner(
        *_args,
        review_admission: PlanReviewAdmission | None = None,
        **_kwargs,
    ) -> ScanResult:
        assert review_admission is not None
        try:
            review_admission.require_source_rows(MAX_PLAN_REVIEW_ROWS + 1)
        except ReviewFactLimitError as error:
            retained_errors.append(error)
            object.__setattr__(
                error.fact,
                "tree_kind",
                ReviewTreeKind.INVENTORY,
            )
            raise

    with pytest.raises(
        RuntimeError,
        match="^plan review limit failure is invalid$",
    ):
        _run(_workflow_dependencies(saved, scanner=scanner))

    assert saved == []
    assert retained_errors
    assert BaseException.__dict__["__traceback__"].__get__(
        retained_errors[0],
        type(retained_errors[0]),
    ) is None


def test_workflow_accepts_planner_issued_logical_byte_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    source = _scan(
        SOURCE_ROOT,
        files=(
            _file("maximum.bin", size=MAX_SIGNED_64),
            _file("extra.bin", size=1),
        ),
    )
    target = _scan(TARGET_ROOT)

    def scanner(
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ScanResult:
        del ignores, ctx, review_admission
        return source if root.root_id == "source" else target

    deps = _workflow_dependencies(saved, scanner=scanner)
    deps.observation_fs = _ObservationFileSystem(source, target)
    result = _run(deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert result.review_fact_limit == (
        ReviewFactLimitExceeded.plan_logical_bytes()
    )
    assert saved == []

def test_producer_accounting_cannot_poison_outer_final_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []

    def poison(admission: PlanReviewAdmission | None) -> None:
        if admission is None:
            return
        admission.admit(
            domain_rows=MAX_PLAN_REVIEW_ROWS,
            domain_bytes=MAX_PLAN_DOMAIN_RETAINED_BYTES,
            informational_rows=MAX_PLAN_REVIEW_ROWS,
            informational_bytes=MAX_PLAN_INFORMATIONAL_RETAINED_BYTES,
        )

    def scanner(
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ScanResult:
        del ignores, ctx
        poison(review_admission)
        return _scan(
            root,
            files=(_file("source.bin"),)
            if root.root_id == "source"
            else (),
        )

    def correspondence(
        source: ScanResult,
        target: ScanResult,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> MappingSnapshot:
        assert review_admission is None
        return _mapping(source, target)

    def planner(
        source: ScanResult,
        target: ScanResult,
        mapping: MappingSnapshot,
        options: SyncOptions,
        scope: Scope,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Plan:
        poison(review_admission)
        return plan(source, target, mapping, options, scope)

    def observer(
        execution_set: ExecutionSet,
        fs: object,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ObservedWorld:
        poison(review_admission)
        return observe(execution_set, fs)  # type: ignore[arg-type]

    def preflight_callback(
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict:
        poison(review_admission)
        return preflight(execution_set, world)

    deps = _workflow_dependencies(
        saved,
        scanner=scanner,
        correspondence=correspondence,
    )
    deps.planner = planner
    deps.observer = observer
    deps.preflight = preflight_callback
    result = _run(deps)
    assert result.status is SessionState.COMPLETED
    assert len(saved) == 1

def test_workflow_detaches_each_successful_collaborator_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    raw: dict[str, object] = {}

    def scanner(
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ScanResult:
        del ignores, ctx, review_admission
        if root.root_id == "target":
            object.__setattr__(raw["source"], "files", ())
            return _scan(root)
        value = _scan(root, files=(_file("source.bin"),))
        raw["source"] = value
        return value

    def correspondence(
        source: ScanResult,
        target: ScanResult,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> MappingSnapshot:
        del review_admission
        assert [record.rel_path for record in source.files] == ["source.bin"]
        value = _mapping(source, target)
        raw["mapping"] = value
        return value

    def planner(
        source: ScanResult,
        target: ScanResult,
        mapping: MappingSnapshot,
        options: SyncOptions,
        scope: Scope,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Plan:
        del review_admission
        object.__setattr__(
            raw["mapping"],
            "ambiguous_source_keys",
            frozenset({"POISON.BIN"}),
        )
        assert mapping.ambiguous_source_keys == frozenset()
        value = plan(source, target, mapping, options, scope)
        raw["plan"] = value
        return value

    def observer(
        execution_set: ExecutionSet,
        fs: object,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ObservedWorld:
        del review_admission
        object.__setattr__(raw["plan"], "operations", ())
        assert len(execution_set.plan.operations) == 1
        value = observe(execution_set, fs)  # type: ignore[arg-type]
        raw["world"] = value
        return value

    def preflight_callback(
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict:
        del review_admission
        object.__setattr__(raw["world"], "stats", {})
        assert world.stats
        value = preflight(execution_set, world)
        raw["verdict"] = value
        return value

    deps = _workflow_dependencies(
        saved,
        scanner=scanner,
        correspondence=correspondence,
    )
    deps.planner = planner
    deps.observer = observer
    deps.preflight = preflight_callback
    result = _run(deps)
    assert result.status is SessionState.COMPLETED
    artifact = saved[0]
    assert [record.rel_path for record in artifact.source_scan.files] == [
        "source.bin"
    ]
    assert len(artifact.plan.operations) == 1
    assert artifact.verdict.observed.stats

    object.__setattr__(
        raw["verdict"],
        "refusals",
        (Refusal(RefusalCode.ROOT_CHANGED),),
    )
    assert artifact.verdict.refusals == ()

def test_workflow_rejects_preflight_mutation_of_captured_world(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    deps = _workflow_dependencies(saved)

    def mutating_preflight(
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict:
        del execution_set, review_admission
        object.__setattr__(world, "stats", {})
        object.__setattr__(world, "paths", {})
        return Verdict(True, (), world)

    deps.preflight = mutating_preflight
    with pytest.raises(ValueError, match="mutated its admitted observed world"):
        _run(deps)
    assert saved == []


@pytest.mark.parametrize("replacement", (False, True))
def test_preflight_population_mutation_cannot_become_capacity_refusal(
    monkeypatch: pytest.MonkeyPatch,
    replacement: bool,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 4)
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    deps = _workflow_dependencies(saved)

    def mutating_preflight(
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict:
        del execution_set, review_admission
        mutated = replace(
            world,
            target_parent_paths=frozenset(str(index) for index in range(5)),
        )
        if replacement:
            return Verdict(True, (), mutated)
        object.__setattr__(
            world,
            "target_parent_paths",
            mutated.target_parent_paths,
        )
        return Verdict(True, (), world)

    deps.preflight = mutating_preflight
    with pytest.raises(
        RuntimeError,
        match="^unadmitted collaborator raised a review fact limit$",
    ):
        _run(deps)
    assert saved == []

def test_run_plan_freezes_request_fields_before_policy_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_id = "a" * 32
    drifted_id = "b" * 32
    saved: list[PlanArtifact] = []
    observed_run_ids: list[str] = []

    class MutatingPolicy:
        request: PlanRequest

        @property
        def name(self) -> str:
            object.__setattr__(self.request, "request_id", drifted_id)
            object.__setattr__(self.request, "source_path", r"E:\drift")
            object.__setattr__(self.request, "target_path", r"F:\drift")
            return "identity"

        version = "1"

        def assign(
            self,
            records: object,
            meta: object,
            target: object,
        ) -> Assignment:
            return SyncOptions().destination_policy.assign(  # type: ignore[arg-type]
                records,
                meta,
                target,
            )

    policy = MutatingPolicy()
    request = PlanRequest(
        original_id,
        SOURCE_ROOT.path,
        TARGET_ROOT.path,
        SyncOptions(destination_policy=policy),  # type: ignore[arg-type]
    )
    policy.request = request
    _patch_workflow_roots(monkeypatch)
    deps = _workflow_dependencies(saved)
    real_observer = deps.observer

    def recording_observer(
        execution_set: ExecutionSet,
        fs: object,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ObservedWorld:
        observed_run_ids.append(str(execution_set.run_id))
        return real_observer(
            execution_set,
            fs,
            review_admission=review_admission,
        )

    deps.observer = recording_observer
    result = run_plan(
        request,
        RunContext(lambda event: None, lambda: None),
        deps,
    )
    assert result.status is SessionState.COMPLETED
    assert observed_run_ids == [original_id]
    artifact = saved[0]
    assert artifact.request.request_id == original_id
    assert artifact.request.source_path == SOURCE_ROOT.path
    assert artifact.request.target_path == TARGET_ROOT.path
    assert request.request_id == drifted_id

@pytest.mark.parametrize(
    ("axis", "expected_fact"),
    (
        ("domain", ReviewFactLimitExceeded.plan_domain_retained_bytes()),
        (
            "informational",
            ReviewFactLimitExceeded.plan_informational_retained_bytes(),
        ),
    ),
)
def test_workflow_accepts_exact_final_retention_and_refuses_first_extra(
    monkeypatch: pytest.MonkeyPatch,
    axis: str,
    expected_fact: ReviewFactLimitExceeded,
) -> None:
    _patch_workflow_roots(monkeypatch)

    def refusing_preflight(
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict:
        del execution_set, review_admission
        return Verdict(
            False,
            (Refusal(RefusalCode.ROOTS_OVERLAP),),
            world,
        )

    baseline_saved: list[PlanArtifact] = []
    baseline = _workflow_dependencies(baseline_saved)
    if axis == "informational":
        baseline.preflight = refusing_preflight
    assert _run(baseline).status is SessionState.COMPLETED
    artifact = baseline_saved[0]
    scan_domain_slots = sum(
        len(scan.files) + len(scan.directories) + len(scan.unsupported)
        for scan in (artifact.source_scan, artifact.target_scan)
    )
    plan_slots = (
        sum(1 + len(op.dependencies) for op in artifact.plan.operations)
        + len(artifact.plan.assignment.items)
        + len(artifact.plan.required_volumes)
    )
    world = artifact.verdict.observed
    world_slots = (
        2 * len(world.stats)
        + 2 * len(world.paths)
        + len(world.target_parent_paths)
        + 2 * len(world.roots)
    )
    informational_slots = (
        len(artifact.source_scan.warnings)
        + len(artifact.target_scan.warnings)
        + len(artifact.verdict.refusals)
    )
    exact = review_module.PLAN_SOURCE_REFERENCE_BYTES * (
        scan_domain_slots + plan_slots + world_slots
        if axis == "domain"
        else informational_slots
    )
    limit_name = (
        "MAX_PLAN_DOMAIN_RETAINED_BYTES"
        if axis == "domain"
        else "MAX_PLAN_INFORMATIONAL_RETAINED_BYTES"
    )

    exact_saved: list[PlanArtifact] = []
    exact_deps = _workflow_dependencies(exact_saved)
    if axis == "informational":
        exact_deps.preflight = refusing_preflight
    monkeypatch.setattr(review_module, limit_name, exact)
    assert _run(exact_deps).status is SessionState.COMPLETED
    assert len(exact_saved) == 1

    refused_saved: list[PlanArtifact] = []
    refused_deps = _workflow_dependencies(refused_saved)
    if axis == "informational":
        refused_deps.preflight = refusing_preflight
    monkeypatch.setattr(review_module, limit_name, exact - 1)
    refused = _run(refused_deps)
    assert refused.status is SessionState.REFUSED
    assert refused.disposition is Disposition.UNRUN
    assert refused.review_fact_limit == expected_fact
    assert refused_saved == []
