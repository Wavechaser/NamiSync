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
import namisync.workflows.inventory as inventory_workflow_module
import namisync.workflows.sync as sync_workflow_module
from namisync.core.evidence import Outcome
from namisync.core.execution import ExecutionReview, validated_run_id
from namisync.core.models import (
    CapabilityProfile, DirRecord, EntryKind, FileIdentity, FileRecord,
    IgnoreSet, MetadataSnapshot, Root, ScanResult, ScanScope, ScanWarning,
    ScanWarningCode, UnsupportedReason, UnsupportedRecord, VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import (
    Assignment, FilterSet, MappingPair, MappingSnapshot, OperationKind,
    OperationReason, Plan, PlanOperation, Scope, SyncOptions,
)
from namisync.core.preflight import (
    ObservedWorld, Refusal, RefusalCode, RootObservation, StatObservation,
    Subject, TrashObservation, Verdict,
)
from namisync.core.review import (
    MAX_PLAN_DOMAIN_RETAINED_BYTES, MAX_PLAN_INFORMATIONAL_RETAINED_BYTES,
    MAX_PLAN_REVIEW_ROWS, PlanReviewAdmission, PlanReviewProducerAdmission,
    ReviewFactLimitExceeded, ReviewLimitAxis, ReviewPopulation, ReviewTreeKind,
    admit_retained_plan_scan, adopt_plan_scan_result,
    exceeds_population_wall, require_population_measure,
    _PlanReviewLimitSignal,
)
from namisync.core.session import Disposition, RunContext, SessionState
from namisync.core.scalars import MAX_SIGNED_64, ScalarDomainError
from namisync.modules.planner import (
    adopt_plan_candidate, plan, snapshot_mapping_snapshot,
)
from namisync.modules.preflight import (
    adopt_plan_observed_world, adopt_plan_verdict, observe, preflight,
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


def test_population_measure_primitives_preserve_exact_first_excess_semantics(
) -> None:
    assert require_population_measure(2, "test population") == 2
    assert not exceeds_population_wall(
        2,
        limit=2,
        field_name="test population",
    )
    assert exceeds_population_wall(
        3,
        limit=2,
        field_name="test population",
    )
    with pytest.raises(
        TypeError,
        match="test population must be a non-Boolean integer",
    ):
        exceeds_population_wall(
            True,
            limit=2,
            field_name="test population",
        )
    with pytest.raises(
        ValueError,
        match="test population must be nonnegative",
    ):
        require_population_measure(-1, "test population")


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

def _xset(value: Plan, token: str = "c" * 32) -> ExecutionReview:
    return ExecutionReview(
        value,
        derive_execution_selection(value).selection,
        validated_run_id(token),
        {},
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
    with pytest.raises(_PlanReviewLimitSignal) as caught:
        admission.admit(**{key: 1 for key in charge})
    assert caught.value.fact == fact

def test_final_admission_is_atomic_with_fixed_precedence() -> None:
    admission = PlanReviewAdmission()
    with pytest.raises(
        ValueError,
        match="plan informational retained bytes must be nonnegative",
    ):
        admission.admit(
            domain_rows=MAX_PLAN_REVIEW_ROWS + 1,
            informational_bytes=-1,
        )
    _fill_final_ledger(admission)

    admission = PlanReviewAdmission()
    with pytest.raises(_PlanReviewLimitSignal) as caught:
        admission.admit(
            domain_rows=MAX_PLAN_REVIEW_ROWS + 1,
            domain_bytes=MAX_PLAN_DOMAIN_RETAINED_BYTES + 1,
            informational_rows=MAX_PLAN_REVIEW_ROWS + 1,
        )
    assert caught.value.fact == ReviewFactLimitExceeded.plan_domain_rows()
    _fill_final_ledger(admission)
    with pytest.raises(_PlanReviewLimitSignal):
        admission.admit(domain_rows=1)

def test_source_checks_are_counter_free_and_independent_of_final_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 2)
    retained = PlanReviewAdmission()
    admission = PlanReviewProducerAdmission()
    assert type(admission) is PlanReviewProducerAdmission
    assert not hasattr(retained, "fresh")
    assert not hasattr(retained, "require_source_rows")
    assert not hasattr(retained, "require_informational_source_rows")
    assert not hasattr(admission, "admit")
    assert not hasattr(admission, "fresh")
    admission.require_source_rows(2)
    admission.require_source_rows(2)
    admission.require_informational_source_rows(2)
    admission.require_informational_source_rows(2)
    with pytest.raises(_PlanReviewLimitSignal) as domain:
        admission.require_source_rows(3)
    with pytest.raises(_PlanReviewLimitSignal) as informational:
        admission.require_informational_source_rows(3)
    assert type(domain.value) is _PlanReviewLimitSignal
    assert type(informational.value) is _PlanReviewLimitSignal
    assert domain.value.fact == ReviewFactLimitExceeded.plan_domain_rows()
    assert informational.value.fact == (
        ReviewFactLimitExceeded.plan_informational_rows()
    )
    _fill_final_ledger(retained)

def test_plan_review_capabilities_reject_cross_role_use() -> None:
    value = _scan(SOURCE_ROOT)
    with pytest.raises(TypeError, match="plan review admission"):
        adopt_plan_scan_result(value, PlanReviewAdmission())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="plan review admission"):
        admit_retained_plan_scan(  # type: ignore[arg-type]
            value,
            PlanReviewProducerAdmission(),
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
    retained = PlanReviewAdmission()
    assert adopt_plan_scan_result(
        value,
        PlanReviewProducerAdmission(),
    ) is value
    _fill_final_ledger(retained)


def test_scan_adoption_refuses_domain_at_first_excess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)
    record = _file("valid.bin")
    value = _scan(SOURCE_ROOT, files=(record, record))

    with pytest.raises(_PlanReviewLimitSignal) as raised:
        adopt_plan_scan_result(value, PlanReviewProducerAdmission())

    assert raised.value.fact == ReviewFactLimitExceeded.plan_domain_rows()


def test_scan_adoption_refuses_information_after_valid_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)
    record = _file("valid.bin")
    warning = ScanWarning(ScanWarningCode.DISAPPEARED, "gone.bin")
    value = _scan(
        SOURCE_ROOT,
        files=(record,),
        warnings=(warning, warning),
    )

    with pytest.raises(_PlanReviewLimitSignal) as raised:
        adopt_plan_scan_result(value, PlanReviewProducerAdmission())

    assert raised.value.fact == (
        ReviewFactLimitExceeded.plan_informational_rows()
    )


def test_scan_adoption_requires_the_exact_scan_result_type() -> None:
    value = _scan(SOURCE_ROOT)
    lookalike = SimpleNamespace(
        **{
            field.name: getattr(value, field.name)
            for field in fields(value)
        }
    )

    with pytest.raises(TypeError):
        adopt_plan_scan_result(lookalike, PlanReviewProducerAdmission())


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
    retained = PlanReviewAdmission()
    assert snapshot_mapping_snapshot(
        value,
        review_admission=PlanReviewProducerAdmission(),
    ) == value
    _fill_final_ledger(retained)

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

def test_scan_adoption_preserves_identity_without_constructor_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _file("file.bin", identity=FileIdentity("SOURCE", 1))
    value = _scan(
        SOURCE_ROOT,
        files=(record,),
        directories=(_directory("folder"),),
        unsupported=(_unsupported("link.bin"),),
        warnings=(ScanWarning(ScanWarningCode.DISAPPEARED, "gone.bin"),),
    )

    def forbid_construction(_value: object) -> None:
        raise AssertionError("scan adoption reconstructed a validated contract")

    for contract in (
        CapabilityProfile,
        DirRecord,
        FileIdentity,
        FileRecord,
        MetadataSnapshot,
        Root,
        ScanResult,
        ScanScope,
        ScanWarning,
        UnsupportedRecord,
        VolumeEvidence,
        VolumeId,
    ):
        monkeypatch.setattr(contract, "__post_init__", forbid_construction)

    adopted = adopt_plan_scan_result(value, PlanReviewProducerAdmission())

    assert adopted is value
    assert adopted.files[0] is record


def test_mapping_snapshot_and_plan_adoption_preserve_semantics() -> None:
    source = _scan(SOURCE_ROOT, files=(_file("file.bin"),))
    target = _scan(TARGET_ROOT)
    mapping = _mapping(source, target)
    copied_mapping = snapshot_mapping_snapshot(mapping)
    assert copied_mapping == mapping and copied_mapping is not mapping

    raw_plan = _planned(source, target, mapping)
    adopted_plan = adopt_plan_candidate(raw_plan, source, target, SyncOptions())
    assert adopted_plan is raw_plan
    assert adopted_plan.operations[0] is raw_plan.operations[0]

    wrong_fingerprint = replace(raw_plan, fingerprint="f" * 64)
    with pytest.raises(ValueError, match="fingerprint"):
        adopt_plan_candidate(
            wrong_fingerprint,
            source,
            target,
            SyncOptions(),
        )


def test_plan_adoption_does_not_reconstruct_plan_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _scan(SOURCE_ROOT, files=(_file("file.bin"),))
    target = _scan(TARGET_ROOT)
    raw_plan = _planned(source, target)

    def forbid_construction(_value: object) -> None:
        raise AssertionError("plan adoption reconstructed a plan contract")

    monkeypatch.setattr(Plan, "__post_init__", forbid_construction)
    monkeypatch.setattr(PlanOperation, "__post_init__", forbid_construction)

    adopted = adopt_plan_candidate(raw_plan, source, target, SyncOptions())

    assert adopted is raw_plan
    assert adopted.operations[0] is raw_plan.operations[0]


def test_plan_adoption_accepts_asymmetric_endpoint_evidence() -> None:
    source = replace(_scan(SOURCE_ROOT), volume_evidence=None)
    target = _scan(TARGET_ROOT)
    raw_plan = _planned(source, target)

    adopted = adopt_plan_candidate(raw_plan, source, target, SyncOptions())

    assert adopted is raw_plan
    assert adopted.source_volume_evidence is None
    assert adopted.target_volume_evidence is target.volume_evidence


def test_plan_adoption_rejects_ordinary_wrong_shapes_and_compound_drift() -> None:
    source = _scan(SOURCE_ROOT, files=(_file("file.bin"),))
    target = _scan(TARGET_ROOT)
    raw_plan = _planned(source, target)
    operation = raw_plan.operations[0]

    plan_lookalike = SimpleNamespace(
        **{
            field.name: getattr(raw_plan, field.name)
            for field in fields(raw_plan)
        }
    )
    with pytest.raises(TypeError, match="exact Plan"):
        adopt_plan_candidate(plan_lookalike, source, target, SyncOptions())

    list_operations = replace(
        raw_plan,
        operations=list(raw_plan.operations),  # type: ignore[arg-type]
    )
    with pytest.raises(TypeError, match="exact tuple"):
        adopt_plan_candidate(list_operations, source, target, SyncOptions())

    operation_lookalike = SimpleNamespace(
        **{
            field.name: getattr(operation, field.name)
            for field in fields(operation)
        }
    )
    lookalike_operation_plan = replace(
        raw_plan,
        operations=(operation_lookalike,),  # type: ignore[arg-type]
    )
    with pytest.raises(TypeError, match="exact PlanOperation"):
        adopt_plan_candidate(
            lookalike_operation_plan,
            source,
            target,
            SyncOptions(),
        )

    wrong_op_id = "0" * 32 if operation.op_id != "0" * 32 else "f" * 32
    wrong_operation = replace(operation, op_id=wrong_op_id)
    wrong_intent_plan = replace(raw_plan, operations=(wrong_operation,))
    with pytest.raises(ValueError, match="canonical intent"):
        adopt_plan_candidate(wrong_intent_plan, source, target, SyncOptions())

    wrong_endpoint_plan = replace(
        raw_plan,
        source_root=Root(r"C:\other", "other"),
    )
    with pytest.raises(ValueError, match="endpoint evidence"):
        adopt_plan_candidate(wrong_endpoint_plan, source, target, SyncOptions())

    wrong_policy_plan = replace(
        raw_plan,
        filter_snapshot=FilterSet(("*.tmp",)),
    )
    with pytest.raises(ValueError, match="policy snapshot"):
        adopt_plan_candidate(wrong_policy_plan, source, target, SyncOptions())

    wrong_volumes_plan = replace(raw_plan, required_volumes=frozenset())
    with pytest.raises(ValueError, match="required volumes"):
        adopt_plan_candidate(wrong_volumes_plan, source, target, SyncOptions())

    wrong_bytes_plan = replace(raw_plan, required_bytes=raw_plan.required_bytes + 1)
    with pytest.raises(ValueError, match="required bytes"):
        adopt_plan_candidate(wrong_bytes_plan, source, target, SyncOptions())

    wrong_policy_fingerprint_plan = replace(
        raw_plan,
        policy_fingerprint="0" * 64,
    )
    with pytest.raises(ValueError, match="policy fingerprint"):
        adopt_plan_candidate(
            wrong_policy_fingerprint_plan,
            source,
            target,
            SyncOptions(),
        )


def test_plan_adoption_failure_keeps_identity_after_frame_retirement(
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
        adopt_plan_candidate(raw_plan, source, target, SyncOptions())

    assert raised.value is failure
    gc.collect()
    assert references and all(reference() is None for reference in references)


def test_world_construction_canonicalizes_utc_alias_and_adoption_keeps_identity() -> None:
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
    assert type(raw_world.observed_at) is datetime
    assert raw_world.observed_at.tzinfo is timezone.utc
    assert raw_world.observed_at is not alias_time

    class _MutableUtcDatetime(datetime):
        pass

    subclass_time = _MutableUtcDatetime(
        2026,
        8,
        27,
        12,
        0,
        tzinfo=timezone.utc,
    )
    subclass_time.mutable_state = ["before"]
    subclass_world = replace(ordinary, observed_at=subclass_time)
    subclass_time.mutable_state.append("after")
    assert type(subclass_world.observed_at) is datetime
    assert subclass_world.observed_at == subclass_time
    assert subclass_world.observed_at is not subclass_time
    assert subclass_world.observed_at.tzinfo is timezone.utc
    assert not hasattr(subclass_world.observed_at, "mutable_state")

    captured = adopt_plan_observed_world(
        raw_world,
        xset,
        PlanReviewProducerAdmission(),
    )
    assert captured is raw_world
    assert captured == replace(ordinary, observed_at=NOW)
    assert type(captured.stats) is MappingProxyType

    raw_verdict = Verdict(
        False,
        (
            Refusal(RefusalCode.ROOTS_OVERLAP, detail="first"),
            Refusal(RefusalCode.ROOT_CHANGED, detail="second"),
        ),
        captured,
    )
    verdict = adopt_plan_verdict(
        raw_verdict,
        captured,
        xset,
        PlanReviewProducerAdmission(),
    )
    assert verdict is raw_verdict
    assert verdict.refusals == raw_verdict.refusals
    assert verdict.observed is captured


def test_world_constructor_normalizes_declared_mapping_enumeration() -> None:
    source = _scan(SOURCE_ROOT)
    target = _scan(TARGET_ROOT, files=(_file("obsolete.bin"),))
    value_plan = _planned(source, target)
    xset = _xset(value_plan)
    ordinary = observe(xset, _ObservationFileSystem(source, target))

    normalized = replace(
        ordinary,
        stats=_LyingLengthMapping(ordinary.stats),
        paths=_LyingLengthMapping(ordinary.paths),
        roots=_LyingLengthMapping(ordinary.roots),
    )
    captured = adopt_plan_observed_world(
        normalized,
        xset,
        PlanReviewProducerAdmission(),
    )
    assert captured is normalized
    assert captured == ordinary

    duplicate_items_normalized = replace(
        ordinary,
        stats=_DuplicateItemMapping(ordinary.stats),
    )
    assert duplicate_items_normalized.stats == ordinary.stats
    assert type(duplicate_items_normalized.stats) is MappingProxyType


def test_world_adoption_rejects_ordinary_wrong_shapes_and_compound_drift() -> None:
    source = _scan(SOURCE_ROOT)
    target = _scan(
        TARGET_ROOT,
        files=(_file(r"folder\sub\obsolete.bin"),),
    )
    review = _xset(_planned(source, target))
    world = observe(review, _ObservationFileSystem(source, target))
    subject = next(
        subject
        for subject, path in world.paths.items()
        if path == r"folder\sub\obsolete.bin"
    )
    outside = Subject(TARGET_ROOT.root_id, "OUTSIDE.BIN")

    wrong_stats = dict(world.stats)
    wrong_stats[subject] = SimpleNamespace(stat=None)
    wrong_paths = dict(world.paths)
    wrong_paths[subject] = "other.bin"
    slash_paths = dict(world.paths)
    slash_paths[subject] = "folder/sub/obsolete.bin"
    stat_observation = world.stats[subject]
    root_id, root_observation = next(iter(world.roots.items()))
    assert world.trash is not None
    trash_observation = world.trash

    def with_stat(observation: StatObservation) -> ObservedWorld:
        stats = dict(world.stats)
        stats[subject] = observation
        return replace(world, stats=stats)

    def with_root(observation: RootObservation) -> ObservedWorld:
        roots = dict(world.roots)
        roots[root_id] = observation
        return replace(world, roots=roots)

    malformed_subject = Subject(TARGET_ROOT.root_id, 1)  # type: ignore[arg-type]
    noncanonical_subject = Subject(
        subject.root_id,
        subject.rel_path_key.lower(),
    )
    sparse = replace(
        world,
        stats={},
        paths={},
        target_parent_paths=frozenset(),
        roots={},
    )

    assert adopt_plan_observed_world(
        sparse,
        review,
        PlanReviewProducerAdmission(),
    ) is sparse

    cases = (
        (SimpleNamespace(), TypeError, "exact ObservedWorld"),
        (
            replace(world, stats=wrong_stats),
            TypeError,
            "StatObservation",
        ),
        (
            with_stat(replace(stat_observation, stat=SimpleNamespace())),
            TypeError,
            "file stat",
        ),
        (
            with_stat(replace(stat_observation, contained=1)),
            TypeError,
            "stat flags",
        ),
        (
            with_stat(replace(stat_observation, error=1)),
            TypeError,
            "stat observation error",
        ),
        (
            with_root(replace(root_observation, volume_id=SimpleNamespace())),
            TypeError,
            "volume identity",
        ),
        (
            with_root(
                replace(root_observation, volume_evidence=SimpleNamespace())
            ),
            TypeError,
            "volume evidence",
        ),
        (
            with_root(replace(root_observation, error=1)),
            TypeError,
            "root observation error",
        ),
        (
            replace(
                world,
                trash=replace(trash_observation, available=1),
            ),
            TypeError,
            "trash flags",
        ),
        (
            replace(
                world,
                trash=replace(trash_observation, resolved_path=1),
            ),
            TypeError,
            "trash path",
        ),
        (
            replace(
                world,
                trash=replace(trash_observation, error=1),
            ),
            TypeError,
            "trash observation error",
        ),
        (
            replace(
                world,
                stats={malformed_subject: stat_observation},
                paths={malformed_subject: r"folder\sub\obsolete.bin"},
            ),
            TypeError,
            "subject fields",
        ),
        (
            replace(
                world,
                stats={noncanonical_subject: stat_observation},
                paths={
                    noncanonical_subject: r"folder\sub\obsolete.bin",
                },
            ),
            ValueError,
            "subject path key is not canonical",
        ),
        (
            replace(
                world,
                stats={outside: StatObservation(None)},
                paths={outside: "outside.bin"},
            ),
            ValueError,
            "outside the plan",
        ),
        (replace(world, paths={}), ValueError, "same subjects"),
        (replace(world, paths=wrong_paths), ValueError, "outside the plan"),
        (replace(world, paths=slash_paths), ValueError, "outside the plan"),
        (
            replace(world, target_parent_paths=frozenset({"unknown"})),
            ValueError,
            "unknown target parent",
        ),
        (
            replace(world, target_parent_paths=frozenset({1})),
            TypeError,
            "target parents must contain text",
        ),
        (
            replace(world, target_parent_paths=frozenset({"folder/sub"})),
            ValueError,
            "unknown target parent",
        ),
        (
            replace(world, roots={"unknown": root_observation}),
            ValueError,
            "unknown endpoint",
        ),
    )

    for candidate, error_type, match in cases:
        with pytest.raises(error_type, match=match):
            adopt_plan_observed_world(
                candidate,
                review,
                PlanReviewProducerAdmission(),
            )


def test_verdict_adoption_rejects_ordinary_wrong_shapes_and_compound_drift() -> None:
    source = _scan(SOURCE_ROOT)
    target = _scan(TARGET_ROOT, files=(_file("obsolete.bin"),))
    review = _xset(_planned(source, target))
    world = observe(review, _ObservationFileSystem(source, target))
    operation = review.plan.operations[0]
    outside = Subject(TARGET_ROOT.root_id, "OUTSIDE.BIN")
    refusal = Refusal(RefusalCode.ROOT_CHANGED, detail="changed")

    cases = (
        (SimpleNamespace(), TypeError, "exact Verdict"),
        (Verdict(1, (), world), ValueError, "truth"),  # type: ignore[arg-type]
        (
            Verdict(False, [refusal], world),  # type: ignore[arg-type]
            TypeError,
            "exact Verdict",
        ),
        (
            Verdict(False, (SimpleNamespace(),), world),  # type: ignore[arg-type]
            TypeError,
            "exact Refusal",
        ),
        (
            Verdict(
                False,
                (Refusal("wrong", detail="changed"),),  # type: ignore[arg-type]
                world,
            ),
            TypeError,
            "code",
        ),
        (
            Verdict(
                False,
                (Refusal(RefusalCode.ROOT_CHANGED, op_id="f" * 32),),
                world,
            ),
            ValueError,
            "unselected operation",
        ),
        (
            Verdict(
                False,
                (Refusal(RefusalCode.ROOT_CHANGED, subject=outside),),
                world,
            ),
            ValueError,
            "unobserved subject",
        ),
        (
            Verdict(
                False,
                (
                    Refusal(
                        RefusalCode.ROOT_CHANGED,
                        op_id=operation.op_id,
                        detail=1,  # type: ignore[arg-type]
                    ),
                ),
                world,
            ),
            TypeError,
            "detail",
        ),
    )

    for candidate, error_type, match in cases:
        with pytest.raises(error_type, match=match):
            adopt_plan_verdict(
                candidate,
                world,
                review,
                PlanReviewProducerAdmission(),
            )


def test_verdict_adoption_gates_information_before_refusal_traversal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)
    source = _scan(SOURCE_ROOT)
    target = _scan(TARGET_ROOT, files=(_file("obsolete.bin"),))
    review = _xset(_planned(source, target))
    world = observe(review, _ObservationFileSystem(source, target))
    value = Verdict(
        False,
        (SimpleNamespace(), SimpleNamespace()),  # type: ignore[arg-type]
        world,
    )

    with pytest.raises(_PlanReviewLimitSignal) as raised:
        adopt_plan_verdict(
            value,
            world,
            review,
            PlanReviewProducerAdmission(),
        )

    assert raised.value.fact == (
        ReviewFactLimitExceeded.plan_informational_rows()
    )


def test_world_and_verdict_adoption_do_not_reconstruct_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _scan(SOURCE_ROOT)
    target = _scan(TARGET_ROOT, files=(_file("obsolete.bin"),))
    review = _xset(_planned(source, target))
    world = observe(review, _ObservationFileSystem(source, target))
    verdict = Verdict(True, (), world)

    def forbid_construction(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("world or verdict adoption rebuilt a contract")

    monkeypatch.setattr(ObservedWorld, "__post_init__", forbid_construction)
    monkeypatch.setattr(RootObservation, "__post_init__", forbid_construction)
    monkeypatch.setattr(StatObservation, "__init__", forbid_construction)
    monkeypatch.setattr(Refusal, "__init__", forbid_construction)
    monkeypatch.setattr(Verdict, "__post_init__", forbid_construction)

    adopted_world = adopt_plan_observed_world(
        world,
        review,
        PlanReviewProducerAdmission(),
    )
    adopted_verdict = adopt_plan_verdict(
        verdict,
        adopted_world,
        review,
        PlanReviewProducerAdmission(),
    )

    assert adopted_world is world
    assert adopted_verdict is verdict


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
        population_admission=PlanReviewProducerAdmission(),
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
        review_admission=PlanReviewProducerAdmission(),
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
        review_admission=PlanReviewProducerAdmission(),
    )
    assert protected_world == ordinary_world

    ordinary_verdict = preflight(ordinary_xset, ordinary_world)
    protected_verdict = preflight(
        protected_xset,
        protected_world,
        review_admission=PlanReviewProducerAdmission(),
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

    def scanner(root, ignores, ctx, *, population_admission=None):
        del ignores, ctx, population_admission
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
    for admission in (None, PlanReviewProducerAdmission()):
        with pytest.raises(_PlanReviewLimitSignal) as caught:
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
    population_admission: PlanReviewProducerAdmission | None = None,
) -> ScanResult:
    del ignores, ctx, population_admission
    return _scan(
        root,
        files=(_file("source.bin"),) if root.root_id == "source" else (),
    )

def _workflow_correspondence(
    source: ScanResult,
    target: ScanResult,
) -> MappingSnapshot:
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
    original_plan_adoption = sync_workflow_module.adopt_plan_candidate

    def track_plan_adoption(
        value: object,
        source: ScanResult,
        target: ScanResult,
        options: SyncOptions,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
    ) -> Plan:
        calls.append("plan-adoption")
        return original_plan_adoption(
            value,
            source,
            target,
            options,
            review_admission=review_admission,
        )

    monkeypatch.setattr(
        sync_workflow_module,
        "adopt_plan_candidate",
        track_plan_adoption,
    )

    def scanner(
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        population_admission: PlanReviewProducerAdmission | None = None,
    ) -> ScanResult:
        del ignores, ctx, population_admission
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
                files=(
                    _file(
                        "new.bin" if root.root_id == "source" else "old.bin"
                    ),
                ),
            )
        return _scan(root)

    def correspondence(
        source: ScanResult,
        target: ScanResult,
    ) -> MappingSnapshot:
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
        review_admission: PlanReviewProducerAdmission | None = None,
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
            assignment = replace(value.assignment, items=(item, item))
            return replace(value, assignment=assignment)
        if population == "plan-operations":
            assert len(value.operations) == 2
            calls.append("planner-return")
        del review_admission
        return value

    def observer(
        execution_set: ExecutionReview,
        fs: object,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
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
        execution_set: ExecutionReview,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
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
        assert "planner" in calls
        assert "plan-adoption" in calls
        assert "observer" not in calls
        if population == "plan-operations":
            assert "planner-return" in calls
    elif population.startswith("world-"):
        assert "observer" in calls and "preflight" not in calls
    else:
        assert "preflight" in calls
    assert saved == []


@pytest.mark.parametrize(
    ("source", "expected_fact"),
    (
        ("producer", ReviewFactLimitExceeded.plan_domain_rows()),
        (
            "retained",
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
        ),
        ("logical-overflow", ReviewFactLimitExceeded.plan_logical_bytes()),
    ),
)
def test_workflow_copies_and_retires_authorized_review_limits(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    expected_fact: ReviewFactLimitExceeded,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    retained_errors: list[_PlanReviewLimitSignal] = []
    graph_references: list[ref[_PrivatePlanFrameValue]] = []

    def reraising(error: _PlanReviewLimitSignal) -> None:
        retained_errors.append(error)
        _raise_with_private_plan_frame(error, graph_references)

    def scanner(
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        population_admission: PlanReviewProducerAdmission | None = None,
    ) -> ScanResult:
        assert population_admission is not None
        if source == "producer":
            try:
                population_admission.require_source_rows(
                    MAX_PLAN_REVIEW_ROWS + 1
                )
            except _PlanReviewLimitSignal as error:
                reraising(error)
        if root.root_id == "source" and source == "logical-overflow":
            return _scan(
                root,
                files=(
                    _file("maximum.bin", size=MAX_SIGNED_64),
                    _file("extra.bin", size=1),
                ),
            )
        return _workflow_scanner(
            root,
            ignores,
            ctx,
            population_admission=population_admission,
        )

    deps = _workflow_dependencies(saved, scanner=scanner)
    if source == "retained":
        monkeypatch.setattr(
            review_module,
            "MAX_PLAN_DOMAIN_RETAINED_BYTES",
            0,
        )
        original_admit = sync_workflow_module.admit_retained_plan_scan

        def admit_retained(
            value: ScanResult,
            admission: PlanReviewAdmission,
        ) -> None:
            try:
                original_admit(value, admission)
            except _PlanReviewLimitSignal as error:
                reraising(error)

        monkeypatch.setattr(
            sync_workflow_module,
            "admit_retained_plan_scan",
            admit_retained,
        )
    elif source == "logical-overflow":
        original_plan = deps.planner

        def planner(*args: object, **kwargs: object) -> Plan:
            try:
                return original_plan(*args, **kwargs)
            except _PlanReviewLimitSignal as error:
                reraising(error)

        deps.planner = planner

    result = _run(deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert result.review_fact_limit == expected_fact
    assert saved == []
    assert retained_errors
    assert type(retained_errors[0]) is _PlanReviewLimitSignal
    assert result.review_fact_limit is not retained_errors[0].fact
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


@pytest.mark.parametrize("source", ("event", "correspondence", "policy", "scanner"))
def test_ordinary_review_limit_lookalike_keeps_failure_identity(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    class ReviewLimitLookalike(ValueError):
        def __init__(self) -> None:
            super().__init__("review_fact_limit_exceeded")
            self.fact = ReviewFactLimitExceeded.plan_domain_rows()

    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    raw_error = ReviewLimitLookalike()

    def raise_spoof(*_args, **_kwargs):
        raise raw_error

    deps = _workflow_dependencies(
        saved,
        scanner=(
            raise_spoof
            if source == "scanner"
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

    with pytest.raises(ReviewLimitLookalike) as raised:
        run_plan(
            _workflow_request(options),
            RunContext(emit, lambda: None),
            deps,
        )

    assert raised.value is raw_error
    assert raised.value.__cause__ is raised.value.__context__ is None
    assert saved == []


@pytest.mark.parametrize(
    ("provenance", "source"),
    [
        *(("untagged", source) for source in (
            "phase-delivery", "scanner", "correspondence", "planner",
            "observer", "preflight", "destination-policy", "nested-scanner",
            "nested-observer-clock", "nested-world-mapping",
        )),
        ("different-run", "scanner"),
    ],
)
def test_unadmitted_exact_plan_signal_cannot_become_refusal(
    monkeypatch: pytest.MonkeyPatch,
    provenance: str,
    source: str,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    if provenance == "untagged":
        raw_error = _PlanReviewLimitSignal(
            ReviewFactLimitExceeded.plan_domain_rows()
        )
    else:
        different_run = PlanReviewProducerAdmission()
        try:
            different_run.require_source_rows(MAX_PLAN_REVIEW_ROWS + 1)
        except _PlanReviewLimitSignal as error:
            raw_error = error
        else:
            raise AssertionError("different-run first excess was admitted")
    graph_references: list[ref[_PrivatePlanFrameValue]] = []

    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        _raise_with_private_plan_frame(raw_error, graph_references)

    deps = _workflow_dependencies(saved)
    options = SyncOptions()
    emit = fail if source == "phase-delivery" else lambda _event: None
    if source in {
        "scanner",
        "correspondence",
        "planner",
        "observer",
        "preflight",
    }:
        setattr(deps, source, fail)
    elif source == "destination-policy":
        class FailingPolicy:
            name = "unadmitted"
            version = "1"

            def assign(self, *_args: object) -> object:
                fail()

        options = SyncOptions(
            destination_policy=FailingPolicy(),  # type: ignore[arg-type]
        )
    elif source == "nested-scanner":
        class FailingBackend(_ScannerBackend):
            def resolve_root(self, path: str) -> str:
                del path
                fail()

        deps.scanner = WalkingScanner(FailingBackend()).scan
    elif source == "nested-observer-clock":
        class FailingClock(_ObservationFileSystem):
            def now_utc(self) -> datetime:
                fail()

        deps.observation_fs = FailingClock(
            _scan(SOURCE_ROOT, files=(_file("source.bin"),)),
            _scan(TARGET_ROOT),
        )
    elif source == "nested-world-mapping":
        class FailingMapping(Mapping[Subject, StatObservation]):
            def __len__(self) -> int:
                return 0

            def __iter__(self) -> Iterator[Subject]:
                fail()

            def __getitem__(self, key: Subject) -> StatObservation:
                raise KeyError(key)

        def observer(
            execution_set: ExecutionReview,
            fs: object,
            *,
            review_admission: PlanReviewProducerAdmission | None = None,
        ) -> ObservedWorld:
            world = observe(
                execution_set,
                fs,  # type: ignore[arg-type]
                review_admission=review_admission,
            )
            return replace(world, stats=FailingMapping())

        deps.observer = observer

    with pytest.raises(
        RuntimeError,
        match="^unadmitted collaborator raised a review fact limit$",
    ) as raised:
        run_plan(
            _workflow_request(options),
            RunContext(emit, lambda: None),
            deps,
        )

    assert raised.value.__cause__ is raised.value.__context__ is None
    assert saved == []
    assert BaseException.__dict__["__traceback__"].__get__(
        raw_error,
        type(raw_error),
    ) is None
    assert BaseException.__dict__["__cause__"].__get__(
        raw_error,
        type(raw_error),
    ) is None
    assert BaseException.__dict__["__context__"].__get__(
        raw_error,
        type(raw_error),
    ) is None
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)


def test_exact_plan_signal_with_inventory_fact_is_invalid_and_never_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    graph_references: list[ref[_PrivatePlanFrameValue]] = []
    raw_error = _PlanReviewLimitSignal(
        ReviewFactLimitExceeded(
            "review_fact_limit_exceeded",
            ReviewTreeKind.INVENTORY,
            ReviewPopulation.DOMAIN,
            ReviewLimitAxis.ROWS,
            MAX_PLAN_REVIEW_ROWS,
            None,
        )
    )

    def scanner(
        *_args,
        population_admission: PlanReviewProducerAdmission | None = None,
        **_kwargs,
    ) -> ScanResult:
        assert population_admission is not None
        _raise_with_private_plan_frame(raw_error, graph_references)

    with pytest.raises(
        RuntimeError,
        match="^plan review limit failure is invalid$",
    ):
        _run(_workflow_dependencies(saved, scanner=scanner))

    assert saved == []
    assert BaseException.__dict__["__traceback__"].__get__(
        raw_error,
        type(raw_error),
    ) is None
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)


def test_inventory_signal_keeps_identity_across_plan_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    raw_error = inventory_workflow_module._InventoryReviewLimitSignal(
        ReviewFactLimitExceeded(
            "review_fact_limit_exceeded",
            ReviewTreeKind.INVENTORY,
            ReviewPopulation.DOMAIN,
            ReviewLimitAxis.ROWS,
            MAX_PLAN_REVIEW_ROWS,
            None,
        )
    )

    def scanner(*_args: object, **_kwargs: object) -> ScanResult:
        raise raw_error

    with pytest.raises(
        inventory_workflow_module._InventoryReviewLimitSignal
    ) as raised:
        _run(_workflow_dependencies(saved, scanner=scanner))

    assert raised.value is raw_error
    assert saved == []


def test_exact_plan_signal_from_save_callback_is_not_demoted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_roots(monkeypatch)
    raw_error = _PlanReviewLimitSignal(
        ReviewFactLimitExceeded.plan_domain_rows()
    )
    deps = _workflow_dependencies([])

    def save_plan(_artifact: PlanArtifact) -> None:
        raise raw_error

    deps.save_plan = save_plan
    with pytest.raises(_PlanReviewLimitSignal) as raised:
        _run(deps)

    assert raised.value is raw_error


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
        population_admission: PlanReviewProducerAdmission | None = None,
    ) -> ScanResult:
        del ignores, ctx, population_admission
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

def test_workflow_producers_receive_only_counter_free_admission_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    admissions: list[PlanReviewProducerAdmission] = []

    def capture(admission: PlanReviewProducerAdmission | None) -> None:
        assert type(admission) is PlanReviewProducerAdmission
        assert not hasattr(admission, "admit")
        assert not hasattr(admission, "fresh")
        admissions.append(admission)

    def scanner(
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        population_admission: PlanReviewProducerAdmission | None = None,
    ) -> ScanResult:
        del ignores, ctx
        capture(population_admission)
        return _scan(
            root,
            files=(_file("source.bin"),)
            if root.root_id == "source"
            else (),
        )

    def correspondence(
        source: ScanResult,
        target: ScanResult,
    ) -> MappingSnapshot:
        return _mapping(source, target)

    def planner(
        source: ScanResult,
        target: ScanResult,
        mapping: MappingSnapshot,
        options: SyncOptions,
        scope: Scope,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
    ) -> Plan:
        capture(review_admission)
        return plan(source, target, mapping, options, scope)

    def observer(
        execution_set: ExecutionReview,
        fs: object,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
    ) -> ObservedWorld:
        capture(review_admission)
        return observe(execution_set, fs)  # type: ignore[arg-type]

    def preflight_callback(
        execution_set: ExecutionReview,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
    ) -> Verdict:
        capture(review_admission)
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
    assert len(admissions) == 5
    assert len({id(admission) for admission in admissions}) == 1

def test_workflow_adopts_immutable_results_once_and_detaches_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    raw: dict[str, object] = {}
    adoption_calls: list[ScanResult] = []
    original_adopt = sync_workflow_module.adopt_plan_scan_result
    plan_adoption_calls: list[object] = []
    original_plan_adoption = sync_workflow_module.adopt_plan_candidate

    def track_adoption(
        value: ScanResult,
        admission: PlanReviewProducerAdmission,
    ) -> ScanResult:
        adoption_calls.append(value)
        return original_adopt(value, admission)

    monkeypatch.setattr(
        sync_workflow_module,
        "adopt_plan_scan_result",
        track_adoption,
    )

    def track_plan_adoption(
        value: object,
        source: ScanResult,
        target: ScanResult,
        options: SyncOptions,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
    ) -> Plan:
        plan_adoption_calls.append(value)
        return original_plan_adoption(
            value,
            source,
            target,
            options,
            review_admission=review_admission,
        )

    monkeypatch.setattr(
        sync_workflow_module,
        "adopt_plan_candidate",
        track_plan_adoption,
    )

    def scanner(
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        population_admission: PlanReviewProducerAdmission | None = None,
    ) -> ScanResult:
        del ignores, ctx, population_admission
        value = _scan(
            root,
            files=(
                (_file("source.bin"),)
                if root.root_id == "source"
                else ()
            ),
        )
        raw[root.root_id] = value
        return value

    def correspondence(
        source: ScanResult,
        target: ScanResult,
    ) -> MappingSnapshot:
        assert source is raw["source"]
        assert target is raw["target"]
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
        review_admission: PlanReviewProducerAdmission | None = None,
    ) -> Plan:
        del review_admission
        assert source is raw["source"]
        assert target is raw["target"]
        assert mapping is not raw["mapping"]
        assert mapping.ambiguous_source_keys == frozenset()
        value = plan(source, target, mapping, options, scope)
        raw["plan"] = value
        return value

    def observer(
        review: ExecutionReview,
        fs: object,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
    ) -> ObservedWorld:
        del review_admission
        assert type(review) is ExecutionReview
        assert review.plan is raw["plan"]
        assert len(review.plan.operations) == 1
        with pytest.raises(TypeError):
            review.status[review.plan.operations[0].op_id] = Outcome.SUCCEEDED
        raw["review"] = review
        value = observe(review, fs)  # type: ignore[arg-type]
        raw["world"] = value
        return value

    def preflight_callback(
        review: ExecutionReview,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
    ) -> Verdict:
        del review_admission
        assert review is raw["review"]
        assert world is raw["world"]
        assert world.stats
        subject = next(iter(world.stats))
        with pytest.raises(TypeError):
            world.stats[subject] = StatObservation(None)
        raw["adopted_world"] = world
        value = preflight(review, world)
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
    assert len(adoption_calls) == 2
    assert plan_adoption_calls == [raw["plan"]]
    assert adoption_calls[0] is raw["source"]
    assert adoption_calls[1] is raw["target"]
    assert artifact.source_scan is raw["source"]
    assert artifact.target_scan is raw["target"]
    assert [record.rel_path for record in artifact.source_scan.files] == [
        "source.bin"
    ]
    assert len(artifact.plan.operations) == 1
    assert artifact.verdict.observed.stats
    assert artifact.plan is raw["plan"]
    assert artifact.plan is raw["review"].plan
    assert artifact.verdict.observed is raw["world"]
    assert artifact.verdict.observed is raw["adopted_world"]
    assert artifact.verdict is raw["verdict"]
    assert artifact.verdict.refusals == ()

def test_workflow_admitted_world_refuses_ordinary_mapping_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    deps = _workflow_dependencies(saved)

    def read_only_preflight(
        review: ExecutionReview,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
    ) -> Verdict:
        del review_admission
        subject = next(iter(world.stats))
        with pytest.raises(TypeError):
            world.stats[subject] = StatObservation(None)
        return preflight(review, world)

    deps.preflight = read_only_preflight
    assert _run(deps).status is SessionState.COMPLETED
    assert len(saved) == 1


def test_preflight_equal_replacement_world_is_ordinary_identity_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 4)
    _patch_workflow_roots(monkeypatch)
    saved: list[PlanArtifact] = []
    deps = _workflow_dependencies(saved)

    def replacing_preflight(
        execution_set: ExecutionReview,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
    ) -> Verdict:
        del execution_set, review_admission
        replacement = replace(world)
        assert replacement == world and replacement is not world
        return Verdict(True, (), replacement)

    deps.preflight = replacing_preflight
    with pytest.raises(ValueError, match="observed a different world"):
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
        execution_set: ExecutionReview,
        fs: object,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
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
        execution_set: ExecutionReview,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewProducerAdmission | None = None,
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
