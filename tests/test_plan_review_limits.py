"""Finite plan-source and retained-owner review admission."""

from __future__ import annotations

import gc
import stat as stat_module
import weakref
from contextlib import contextmanager
from dataclasses import fields, replace as _replace
from datetime import datetime as _datetime
from datetime import timedelta as _timedelta
from datetime import timezone as _timezone
from types import MappingProxyType as _MappingProxyType
from types import SimpleNamespace

import pytest

import namisync.core.review as review_module
import namisync.modules.planner as planner_module
import namisync.modules.preflight as preflight_module
import namisync.modules.scanner as scanner_module
import namisync.workflows.sync as sync_workflow_module
from namisync.core.execution import ExecutionSet, validated_run_id
from namisync.core.models import (
    CapabilityProfile,
    DirRecord,
    FileIdentity,
    FileRecord,
    IgnoreSet,
    MetadataSnapshot,
    Root,
    ScanResult,
    ScanScope,
    ScanWarning,
    ScanWarningCode,
    UnsupportedReason,
    UnsupportedRecord,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.preflight import (
    ObservedWorld,
    Refusal,
    RefusalCode,
    RootObservation,
    StatObservation,
    TrashObservation,
    Verdict,
)
from namisync.core.planning import (
    Assignment,
    BlockedReason,
    DestinationAssignment,
    MappingPair,
    MappingSnapshot,
    OperationKind,
    PlanOperation,
    Scope,
    SyncOptions,
)
from namisync.core.review import (
    MAX_PLAN_DOMAIN_RETAINED_BYTES,
    MAX_PLAN_INFORMATIONAL_RETAINED_BYTES,
    MAX_PLAN_REVIEW_ROWS,
    PLAN_SOURCE_REFERENCE_BYTES,
    PlanReviewAdmission,
    ReviewFactLimitError,
    ReviewFactLimitExceeded,
    admit_plan_scan_copy,
    admit_retained_plan_scan,
    snapshot_admitted_plan_scan,
    snapshot_plan_scan_result,
)
from namisync.core.scalars import MAX_SIGNED_64, ScalarDomainError
from namisync.core.session import Disposition, RunContext, SessionState
from namisync.modules.planner import (
    admit_plan_mapping_copy,
    admit_retained_plan_candidate,
    plan,
)
from namisync.modules.preflight import observe, preflight
from namisync.modules.scanner import VolumeSnapshot, WalkingScanner
from namisync.workflows.models import PlanRequest
from namisync.workflows.runtime import LocalWorkflowRuntime
from namisync.workflows.selection import (
    derive_execution_selection,
    derive_plan_review_selection,
)
from namisync.workflows.sync import run_plan


META = MetadataSnapshot(0, None)
PROFILE = CapabilityProfile("NTFS", 100, True, False, 32_767, False, True)
VOLUME = VolumeId("SOURCE", "NTFS")


def _file(path: str, *, size: int = 1) -> FileRecord:
    return FileRecord(
        path,
        normalize_relative_path(path),
        size,
        1,
        None,
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


def _scan(
    *,
    files: tuple[FileRecord, ...] = (),
    directories: tuple[DirRecord, ...] = (),
    unsupported: tuple[UnsupportedRecord, ...] = (),
    warnings: tuple[ScanWarning, ...] = (),
) -> ScanResult:
    return ScanResult(
        Root(r"C:\source", "source"),
        VOLUME,
        VolumeEvidence(device_id="SOURCE"),
        PROFILE,
        files,
        directories,
        unsupported,
        warnings,
        ScanScope.full(),
        True,
    )


def _forge_scan(value: ScanResult, **changes: object) -> ScanResult:
    forged = object.__new__(ScanResult)
    for field in fields(ScanResult):
        object.__setattr__(
            forged,
            field.name,
            changes.get(field.name, getattr(value, field.name)),
        )
    return forged


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


class _ScannerBackend:
    def __init__(self, entries: list[object]) -> None:
        self.entries = entries

    def resolve_root(self, path: str) -> str:
        return path

    def volume_snapshot(self, root: str) -> VolumeSnapshot:
        del root
        return VolumeSnapshot(
            VOLUME,
            VolumeEvidence(device_id="SOURCE"),
            PROFILE,
        )

    def lstat(self, path: str) -> SimpleNamespace:
        del path
        return _scanner_stat(directory=True, inode=1)

    @contextmanager
    def scandir(self, path: str):
        del path
        yield iter(self.entries)


class _IgnoredScannerEntry:
    def __init__(self) -> None:
        self.name_reads = 0
        self.path_reads = 0

    @property
    def name(self) -> str:
        self.name_reads += 1
        return ".synctrash"

    @property
    def path(self) -> str:
        self.path_reads += 1
        return r"C:\source\.synctrash"

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        assert not follow_symlinks
        return True

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        raise AssertionError("ignored entry was probed as a file")

    def stat(self, *, follow_symlinks: bool = True) -> SimpleNamespace:
        raise AssertionError("ignored entry was statted")


class _NestedIgnoredScannerEntry(_IgnoredScannerEntry):
    @property
    def name(self) -> str:
        self.name_reads += 1
        return "DESKTOP.INI"

    @property
    def path(self) -> str:
        self.path_reads += 1
        return r"C:\source\child\DESKTOP.INI"


class _AlternatingScannerEntry:
    def __init__(self) -> None:
        self.name_reads = 0
        self.path_reads = 0

    @property
    def name(self) -> str:
        self.name_reads += 1
        return "stable.bin" if self.name_reads == 1 else "changed.bin"

    @property
    def path(self) -> str:
        self.path_reads += 1
        return (
            r"C:\source\stable.bin"
            if self.path_reads == 1
            else r"C:\source\changed.bin"
        )

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        assert not follow_symlinks
        return False

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        assert not follow_symlinks
        return True

    def stat(self, *, follow_symlinks: bool = True) -> SimpleNamespace:
        assert not follow_symlinks
        return _scanner_stat(directory=False, inode=2)


class _StableScannerEntry(_AlternatingScannerEntry):
    @property
    def name(self) -> str:
        self.name_reads += 1
        return "stable.bin"

    @property
    def path(self) -> str:
        self.path_reads += 1
        return r"C:\source\stable.bin"


class _DirectoryScannerEntry:
    name = "child"
    path = r"C:\source\child"

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        assert not follow_symlinks
        return True

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        raise AssertionError("directory entry was probed as a file")

    def stat(self, *, follow_symlinks: bool = True) -> SimpleNamespace:
        assert not follow_symlinks
        return _scanner_stat(directory=True, inode=2)


class _NestedScannerBackend(_ScannerBackend):
    def __init__(self, child_entries: list[object]) -> None:
        super().__init__([_DirectoryScannerEntry()])
        self.child_entries = child_entries

    @contextmanager
    def scandir(self, path: str):
        yield iter(
            self.child_entries
            if path == _DirectoryScannerEntry.path
            else self.entries
        )


class _OfflineScannerBackend:
    def resolve_root(self, path: str) -> str:
        del path
        raise OSError("offline fixture")


class _EnumerationFailure:
    def __iter__(self):
        return self

    def __next__(self):
        raise OSError("enumeration failed")


class _TerminalDriftScannerBackend(_ScannerBackend):
    def __init__(self) -> None:
        super().__init__([])
        self.swapped = False

    def lstat(self, path: str) -> SimpleNamespace:
        del path
        result = _scanner_stat(directory=True, inode=1)
        if self.swapped:
            result.st_file_attributes = (
                scanner_module.FILE_ATTRIBUTE_REPARSE_POINT
            )
        return result

    @contextmanager
    def scandir(self, path: str):
        del path
        self.swapped = True
        yield _EnumerationFailure()


@pytest.mark.parametrize(
    ("fact", "population", "axis", "row_limit", "byte_limit"),
    (
        (
            ReviewFactLimitExceeded.plan_domain_rows(),
            "domain",
            "rows",
            MAX_PLAN_REVIEW_ROWS,
            None,
        ),
        (
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
            "domain",
            "retained-bytes",
            None,
            MAX_PLAN_DOMAIN_RETAINED_BYTES,
        ),
        (
            ReviewFactLimitExceeded.plan_informational_rows(),
            "informational",
            "rows",
            MAX_PLAN_REVIEW_ROWS,
            None,
        ),
        (
            ReviewFactLimitExceeded.plan_informational_retained_bytes(),
            "informational",
            "retained-bytes",
            None,
            MAX_PLAN_INFORMATIONAL_RETAINED_BYTES,
        ),
    ),
)
def test_plan_review_fact_constructors_are_exact(
    fact: ReviewFactLimitExceeded,
    population: str,
    axis: str,
    row_limit: int | None,
    byte_limit: int | None,
) -> None:
    assert fact.reason == "review_fact_limit_exceeded"
    assert fact.tree_kind == "plan"
    assert fact.population == population
    assert fact.axis == axis
    assert fact.row_limit == row_limit
    assert fact.byte_limit == byte_limit


@pytest.mark.parametrize(
    ("field", "fact"),
    (
        ("domain_rows", ReviewFactLimitExceeded.plan_domain_rows()),
        (
            "informational_rows",
            ReviewFactLimitExceeded.plan_informational_rows(),
        ),
    ),
)
def test_final_row_wall_accepts_exact_and_rejects_first_excess(
    field: str,
    fact: ReviewFactLimitExceeded,
) -> None:
    admission = PlanReviewAdmission()
    admission.admit(**{field: MAX_PLAN_REVIEW_ROWS})

    with pytest.raises(ReviewFactLimitError) as caught:
        admission.admit(**{field: 1})

    assert caught.value.fact == fact


@pytest.mark.parametrize(
    ("field", "limit", "fact"),
    (
        (
            "domain_bytes",
            MAX_PLAN_DOMAIN_RETAINED_BYTES,
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
        ),
        (
            "informational_bytes",
            MAX_PLAN_INFORMATIONAL_RETAINED_BYTES,
            ReviewFactLimitExceeded.plan_informational_retained_bytes(),
        ),
    ),
)
def test_retained_byte_wall_accepts_exact_and_rejects_first_excess(
    field: str,
    limit: int,
    fact: ReviewFactLimitExceeded,
) -> None:
    admission = PlanReviewAdmission()
    admission.admit(**{field: limit})

    with pytest.raises(ReviewFactLimitError) as caught:
        admission.admit(**{field: 1})

    assert caught.value.fact == fact


@pytest.mark.parametrize(
    ("charges", "fact"),
    (
        (
            {
                "domain_rows": MAX_PLAN_REVIEW_ROWS + 1,
                "domain_bytes": MAX_PLAN_DOMAIN_RETAINED_BYTES + 1,
                "informational_rows": MAX_PLAN_REVIEW_ROWS + 1,
                "informational_bytes": (
                    MAX_PLAN_INFORMATIONAL_RETAINED_BYTES + 1
                ),
            },
            ReviewFactLimitExceeded.plan_domain_rows(),
        ),
        (
            {
                "domain_bytes": MAX_PLAN_DOMAIN_RETAINED_BYTES + 1,
                "informational_rows": MAX_PLAN_REVIEW_ROWS + 1,
                "informational_bytes": (
                    MAX_PLAN_INFORMATIONAL_RETAINED_BYTES + 1
                ),
            },
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
        ),
        (
            {
                "informational_rows": MAX_PLAN_REVIEW_ROWS + 1,
                "informational_bytes": (
                    MAX_PLAN_INFORMATIONAL_RETAINED_BYTES + 1
                ),
            },
            ReviewFactLimitExceeded.plan_informational_rows(),
        ),
    ),
)
def test_admission_has_fixed_precedence_and_is_atomic(
    charges: dict[str, int],
    fact: ReviewFactLimitExceeded,
) -> None:
    admission = PlanReviewAdmission()
    admission.admit(
        domain_rows=1,
        domain_bytes=2,
        informational_rows=3,
        informational_bytes=4,
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        admission.admit(**charges)

    assert caught.value.fact == fact
    assert (
        admission.domain_rows,
        admission.domain_bytes,
        admission.informational_rows,
        admission.informational_bytes,
    ) == (1, 2, 3, 4)


@pytest.mark.parametrize("value", (True, 1.0, "1", None, -1))
def test_admission_rejects_noncanonical_charges_without_mutation(
    value: object,
) -> None:
    admission = PlanReviewAdmission()

    with pytest.raises((TypeError, ValueError)):
        admission.admit(domain_rows=value)  # type: ignore[arg-type]

    assert admission.domain_rows == 0


def test_source_populations_are_independent_stateless_axes() -> None:
    admission = PlanReviewAdmission()

    admission.require_source_rows(MAX_PLAN_REVIEW_ROWS)
    admission.require_source_rows(MAX_PLAN_REVIEW_ROWS)
    admission.require_informational_source_rows(MAX_PLAN_REVIEW_ROWS)
    admission.require_informational_source_rows(MAX_PLAN_REVIEW_ROWS)

    assert (
        admission.domain_rows,
        admission.domain_bytes,
        admission.informational_rows,
        admission.informational_bytes,
    ) == (0, 0, 0, 0)
    with pytest.raises(ReviewFactLimitError) as domain:
        admission.require_source_rows(MAX_PLAN_REVIEW_ROWS + 1)
    with pytest.raises(ReviewFactLimitError) as informational:
        admission.require_informational_source_rows(
            MAX_PLAN_REVIEW_ROWS + 1
        )
    assert domain.value.fact == ReviewFactLimitExceeded.plan_domain_rows()
    assert (
        informational.value.fact
        == ReviewFactLimitExceeded.plan_informational_rows()
    )


def test_fork_copies_counters_without_sharing_mutation() -> None:
    admission = PlanReviewAdmission()
    admission.admit(
        domain_rows=1,
        domain_bytes=2,
        informational_rows=3,
        informational_bytes=4,
    )

    forked = admission.fork()
    forked.admit(
        domain_rows=10,
        domain_bytes=20,
        informational_rows=30,
        informational_bytes=40,
    )

    assert (
        admission.domain_rows,
        admission.domain_bytes,
        admission.informational_rows,
        admission.informational_bytes,
    ) == (1, 2, 3, 4)
    assert (
        forked.domain_rows,
        forked.domain_bytes,
        forked.informational_rows,
        forked.informational_bytes,
    ) == (11, 22, 33, 44)


def test_shape_admission_charges_only_reference_slots() -> None:
    admission = PlanReviewAdmission()

    admission.admit_domain_shape(reference_slots=3, rows=2)
    admission.admit_informational_shape(reference_slots=2)

    assert admission.domain_rows == 2
    assert admission.domain_bytes == 3 * PLAN_SOURCE_REFERENCE_BYTES
    assert admission.informational_rows == 1
    assert (
        admission.informational_bytes
        == 2 * PLAN_SOURCE_REFERENCE_BYTES
    )


def test_scan_snapshot_is_exact_detached_and_does_not_charge_final_rows() -> None:
    original_file = _file("file.bin")
    original = _scan(
        files=(original_file,),
        warnings=(
            ScanWarning(ScanWarningCode.ENUMERATION_ERROR, None, "notice"),
        ),
    )
    admission = PlanReviewAdmission()

    snapshot = snapshot_plan_scan_result(original, admission)
    object.__setattr__(original_file, "size", 9)

    assert snapshot is not original
    assert snapshot.files[0] is not original_file
    assert snapshot.files[0].size == 1
    assert (
        admission.domain_rows,
        admission.domain_bytes,
        admission.informational_rows,
        admission.informational_bytes,
    ) == (0, 0, 0, 0)


def test_scan_snapshot_rejects_domain_first_excess_before_item_validation() -> None:
    forged = _forge_scan(
        _scan(),
        files=(object(),) * (MAX_PLAN_REVIEW_ROWS + 1),
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        snapshot_plan_scan_result(forged, PlanReviewAdmission())

    assert caught.value.fact == ReviewFactLimitExceeded.plan_domain_rows()


def test_logical_source_overflow_precedes_informational_excess() -> None:
    exact = _scan(files=(_file("maximum-only.bin", size=MAX_SIGNED_64),))
    assert (
        snapshot_plan_scan_result(
            exact,
            PlanReviewAdmission(),
            logical_source=True,
        )
        == exact
    )

    warning = ScanWarning(ScanWarningCode.ENUMERATION_ERROR, None, "notice")
    forged = _forge_scan(
        _scan(),
        files=(
            _file("maximum.bin", size=MAX_SIGNED_64),
            _file("excess.bin"),
        ),
        warnings=(warning,) * (MAX_PLAN_REVIEW_ROWS + 1),
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        snapshot_plan_scan_result(
            forged,
            PlanReviewAdmission(),
            logical_source=True,
        )

    assert caught.value.fact == ReviewFactLimitExceeded.plan_logical_bytes()


def test_logical_source_preserves_invalid_file_scalar_error() -> None:
    forged_file = _file("invalid.bin")
    object.__setattr__(forged_file, "size", -1)
    forged = _forge_scan(_scan(), files=(forged_file,))

    with pytest.raises(ScalarDomainError, match="file size"):
        snapshot_plan_scan_result(
            forged,
            PlanReviewAdmission(),
            logical_source=True,
        )


def test_scan_snapshot_does_not_copy_an_undeclared_instance_graph() -> None:
    original = _scan(files=(_file("valid.bin"),))

    class HostileHiddenGraph:
        def __deepcopy__(self, memo: object) -> object:
            del memo
            raise AssertionError("undeclared scan graph was copied")

    object.__setattr__(original, "hidden_graph", HostileHiddenGraph())

    snapshot = snapshot_plan_scan_result(original, PlanReviewAdmission())

    assert not hasattr(snapshot, "hidden_graph")


def test_scan_copy_admission_precedes_detached_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _scan(files=(_file("one.bin"),))
    admission = PlanReviewAdmission()
    admission.admit(
        domain_bytes=(
            MAX_PLAN_DOMAIN_RETAINED_BYTES
            - PLAN_SOURCE_REFERENCE_BYTES
            + 1
        )
    )
    monkeypatch.setattr(
        review_module,
        "_copy_plan_scan_result",
        lambda value: (_ for _ in ()).throw(
            AssertionError("scan copy allocated before admission")
        ),
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        snapshot_admitted_plan_scan(result, admission)

    assert (
        caught.value.fact
        == ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )


def test_scan_copy_keeps_logical_overflow_ahead_of_retained_bytes() -> None:
    admission = PlanReviewAdmission()
    admission.admit(domain_bytes=MAX_PLAN_DOMAIN_RETAINED_BYTES)
    result = _scan(
        files=(
            _file("maximum.bin", size=MAX_SIGNED_64),
            _file("excess.bin"),
        )
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        snapshot_admitted_plan_scan(
            result,
            admission,
            logical_source=True,
        )

    assert caught.value.fact == ReviewFactLimitExceeded.plan_logical_bytes()


def test_retained_scan_charges_domain_slots_and_warning_rows_separately() -> None:
    warning = ScanWarning(ScanWarningCode.ENUMERATION_ERROR, None, "notice")
    result = _scan(
        files=(_file("file.bin"),),
        directories=(_directory("directory"),),
        unsupported=(
            UnsupportedRecord(
                "blocked",
                normalize_relative_path("blocked"),
                UnsupportedReason.ACCESS_DENIED,
            ),
        ),
        warnings=(warning, warning),
    )
    admission = PlanReviewAdmission()

    admit_retained_plan_scan(result, admission)

    assert admission.domain_rows == 0
    assert admission.domain_bytes == 3 * PLAN_SOURCE_REFERENCE_BYTES
    assert admission.informational_rows == 2
    assert admission.informational_bytes == 2 * PLAN_SOURCE_REFERENCE_BYTES


def test_disposable_scan_copy_does_not_recount_warning_rows() -> None:
    warning = ScanWarning(ScanWarningCode.ENUMERATION_ERROR, None, "notice")
    admission = PlanReviewAdmission()
    admission.admit(informational_rows=MAX_PLAN_REVIEW_ROWS)

    admit_plan_scan_copy(_scan(warnings=(warning,)), admission)

    assert admission.informational_rows == MAX_PLAN_REVIEW_ROWS
    assert admission.informational_bytes == PLAN_SOURCE_REFERENCE_BYTES


def test_two_maximum_scans_do_not_consume_final_plan_rows() -> None:
    record = _file("file.bin")
    result = _forge_scan(
        _scan(),
        files=(record,) * MAX_PLAN_REVIEW_ROWS,
    )
    admission = PlanReviewAdmission()

    admit_retained_plan_scan(result, admission)
    admit_retained_plan_scan(result, admission)
    admission.admit(domain_rows=MAX_PLAN_REVIEW_ROWS)

    assert admission.domain_rows == MAX_PLAN_REVIEW_ROWS
    assert (
        admission.domain_bytes
        == 2 * MAX_PLAN_REVIEW_ROWS * PLAN_SOURCE_REFERENCE_BYTES
    )
    with pytest.raises(ReviewFactLimitError) as caught:
        admission.admit(domain_rows=1)
    assert caught.value.fact == ReviewFactLimitExceeded.plan_domain_rows()


def test_module_scanner_forwards_exact_plan_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _scan()
    admission = PlanReviewAdmission()
    observed: list[object] = []

    class ForwardedScanner:
        def scan(self, *args: object, **kwargs: object) -> ScanResult:
            del args
            observed.append(kwargs.get("review_admission"))
            return expected

    monkeypatch.setattr(scanner_module, "WalkingScanner", ForwardedScanner)

    result = scanner_module.scan(
        expected.root,
        IgnoreSet(),
        RunContext(lambda event: None, lambda: None),
        review_admission=admission,
    )

    assert result is expected
    assert observed == [admission]


def test_walking_scanner_rejects_nonexact_plan_admission_before_backend() -> None:
    class DerivedAdmission(PlanReviewAdmission):
        pass

    scanner = WalkingScanner(object())  # type: ignore[arg-type]
    for invalid in (object(), DerivedAdmission()):
        with pytest.raises(TypeError, match="plan review admission"):
            scanner.scan(
                Root(r"C:\source", "source"),
                IgnoreSet(),
                RunContext(lambda event: None, lambda: None),
                review_admission=invalid,  # type: ignore[arg-type]
            )


def test_plan_scan_collectors_share_row_gates_and_append_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)
    admission = PlanReviewAdmission()
    collectors = scanner_module._PlanScanCollectors(admission)
    files = scanner_module._PlanScanList(collectors, informational=False)
    directories = scanner_module._PlanScanList(
        collectors,
        informational=False,
    )
    warnings = scanner_module._PlanScanList(
        collectors,
        informational=True,
    )

    files.append(_file("one.bin"))
    warning = ScanWarning(ScanWarningCode.ENUMERATION_ERROR, None, "notice")
    warnings.append(warning)
    before = (
        admission.domain_rows,
        admission.domain_bytes,
        admission.informational_rows,
        admission.informational_bytes,
    )

    with pytest.raises(ReviewFactLimitError) as domain:
        directories.append(_directory(""))
    with pytest.raises(ReviewFactLimitError) as informational:
        warnings.append(warning)

    assert domain.value.fact == ReviewFactLimitExceeded.plan_domain_rows()
    assert (
        informational.value.fact
        == ReviewFactLimitExceeded.plan_informational_rows()
    )
    assert files == [_file("one.bin")]
    assert directories == []
    assert warnings == [warning]
    assert collectors.domain_count == collectors.informational_count == 1
    assert before == (0, PLAN_SOURCE_REFERENCE_BYTES, 1, PLAN_SOURCE_REFERENCE_BYTES)
    assert before == (
        admission.domain_rows,
        admission.domain_bytes,
        admission.informational_rows,
        admission.informational_bytes,
    )


def test_plan_scanner_gates_each_directory_before_the_second_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)
    exact_entry = _IgnoredScannerEntry()
    exact = WalkingScanner(_ScannerBackend([exact_entry])).scan(
        Root(r"C:\source", "source"),
        IgnoreSet(),
        RunContext(lambda event: None, lambda: None),
        review_admission=PlanReviewAdmission(),
    )

    first = _IgnoredScannerEntry()
    excess = _IgnoredScannerEntry()
    with pytest.raises(ReviewFactLimitError) as caught:
        WalkingScanner(_ScannerBackend([first, excess])).scan(
            Root(r"C:\source", "source"),
            IgnoreSet(),
            RunContext(lambda event: None, lambda: None),
            review_admission=PlanReviewAdmission(),
        )

    assert exact.complete
    assert exact_entry.name_reads == exact_entry.path_reads == 1
    assert first.name_reads == first.path_reads == 1
    assert excess.name_reads == excess.path_reads == 0
    assert caught.value.fact == ReviewFactLimitExceeded.plan_domain_rows()


def test_plan_scanner_resets_the_raw_gate_for_each_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 2)
    child_entries = [
        _NestedIgnoredScannerEntry(),
        _NestedIgnoredScannerEntry(),
    ]

    result = WalkingScanner(_NestedScannerBackend(child_entries)).scan(
        Root(r"C:\source", "source"),
        IgnoreSet(),
        RunContext(lambda event: None, lambda: None),
        review_admission=PlanReviewAdmission(),
    )

    assert tuple(record.rel_path for record in result.directories) == (
        "",
        "child",
    )
    assert all(
        entry.name_reads == entry.path_reads == 1
        for entry in child_entries
    )


def test_plan_scanner_offline_result_charges_its_fixed_warning_owner() -> None:
    admission = PlanReviewAdmission()

    protected = WalkingScanner(_OfflineScannerBackend()).scan(
        Root(r"C:\source", "source"),
        IgnoreSet(),
        RunContext(lambda event: None, lambda: None),
        review_admission=admission,
    )
    ordinary = WalkingScanner(_OfflineScannerBackend()).scan(
        Root(r"C:\source", "source"),
        IgnoreSet(),
        RunContext(lambda event: None, lambda: None),
    )

    assert protected == ordinary
    assert admission.informational_rows == 1
    assert admission.informational_bytes == PLAN_SOURCE_REFERENCE_BYTES


def test_terminal_scanner_replacement_discards_provisional_warning_charge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_INFORMATIONAL_RETAINED_BYTES",
        PLAN_SOURCE_REFERENCE_BYTES,
    )
    admission = PlanReviewAdmission()

    result = WalkingScanner(_TerminalDriftScannerBackend()).scan(
        Root(r"C:\source", "source"),
        IgnoreSet(),
        RunContext(lambda event: None, lambda: None),
        review_admission=admission,
    )

    assert result.files == result.directories == result.unsupported == ()
    assert tuple(warning.code for warning in result.warnings) == (
        ScanWarningCode.ROOT_UNAVAILABLE,
    )
    assert admission.domain_bytes == 0
    assert admission.informational_rows == 1
    assert admission.informational_bytes == PLAN_SOURCE_REFERENCE_BYTES


def test_scanner_builder_sort_and_tuple_overlap_refuses_before_result_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        2 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    monkeypatch.setattr(
        scanner_module,
        "ScanResult",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("scanner result allocated before overlap admission")
        ),
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        WalkingScanner(_ScannerBackend([])).scan(
            Root(r"C:\source", "source"),
            IgnoreSet(),
            RunContext(lambda event: None, lambda: None),
            review_admission=PlanReviewAdmission(),
        )

    assert (
        caught.value.fact
        == ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )


def test_plan_scanner_captures_entry_name_and_path_once() -> None:
    entry = _AlternatingScannerEntry()

    result = WalkingScanner(_ScannerBackend([entry])).scan(
        Root(r"C:\source", "source"),
        IgnoreSet(),
        RunContext(lambda event: None, lambda: None),
        review_admission=PlanReviewAdmission(),
    )

    assert tuple(record.rel_path for record in result.files) == ("stable.bin",)
    assert entry.name_reads == entry.path_reads == 1


def test_plan_scanner_omits_oversized_join_before_construction() -> None:
    collectors = scanner_module._PlanScanCollectors(PlanReviewAdmission())
    warnings = scanner_module._PlanScanList(
        collectors,
        informational=True,
    )

    assert WalkingScanner._joined_warning_detail(
        warnings,
        ["x" * 1_024],
    ) == "x" * 1_024
    assert WalkingScanner._joined_warning_detail(
        warnings,
        ["x" * 1_025],
    ) == ""


def test_plan_scanner_diagnostic_callsites_omit_oversized_joins() -> None:
    collision_collectors = scanner_module._PlanScanCollectors(
        PlanReviewAdmission()
    )
    collision_files = scanner_module._PlanScanList(
        collision_collectors,
        informational=False,
    )
    collision_warnings = scanner_module._PlanScanList(
        collision_collectors,
        informational=True,
    )
    collision_files.append(_file("a" * 600))
    collision_files.append(_file("A" * 600))

    complete = WalkingScanner._append_collision_warnings(
        collision_files,
        [],
        [],
        collision_warnings,
    )

    identity = FileIdentity(VOLUME.serial, 1)
    identity_collectors = scanner_module._PlanScanCollectors(
        PlanReviewAdmission()
    )
    identity_files = scanner_module._PlanScanList(
        identity_collectors,
        informational=False,
    )
    identity_warnings = scanner_module._PlanScanList(
        identity_collectors,
        informational=True,
    )
    for path in ("b" * 600, "c" * 600):
        identity_files.append(
            FileRecord(
                path,
                normalize_relative_path(path),
                1,
                1,
                identity,
                1,
                META,
            )
        )
    WalkingScanner._append_identity_warnings(
        identity_files,
        [],
        identity_warnings,
    )

    assert not complete
    assert collision_warnings[0].code is ScanWarningCode.CASE_COLLISION
    assert collision_warnings[0].detail == ""
    assert identity_warnings[0].code is ScanWarningCode.DUPLICATE_IDENTITY
    assert identity_warnings[0].detail == ""


def test_ordinary_scanner_bypasses_plan_wrapper_and_keeps_literal_join(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scanner_module,
        "_PlanDirectoryEntry",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("ordinary scan constructed a plan wrapper")
        ),
    )

    result = WalkingScanner(_ScannerBackend([_StableScannerEntry()])).scan(
        Root(r"C:\source", "source"),
        IgnoreSet(),
        RunContext(lambda event: None, lambda: None),
    )

    oversized = "x" * 1_025
    assert tuple(record.rel_path for record in result.files) == ("stable.bin",)
    assert WalkingScanner._joined_warning_detail([], [oversized]) == oversized


def test_planner_callback_fork_charges_detached_scan_and_record_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _scan(files=(_file("source.bin"),))
    target = _scan()
    admission = PlanReviewAdmission()
    retained_calls: list[PlanReviewAdmission] = []
    assignment_calls: list[PlanReviewAdmission] = []
    callback_record_refs: list[weakref.ReferenceType[FileRecord]] = []
    callback_target_refs: list[weakref.ReferenceType[ScanResult]] = []
    detached_inputs: list[bool] = []
    original_admit = planner_module.snapshot_admitted_plan_scan
    original_snapshot_assignment = planner_module._snapshot_assignment

    def recording_admit(
        result: ScanResult,
        owner: PlanReviewAdmission,
        **kwargs: object,
    ) -> ScanResult:
        retained_calls.append(owner)
        return original_admit(result, owner, **kwargs)

    def recording_snapshot_assignment(
        value: object,
        owner: PlanReviewAdmission,
        **kwargs: object,
    ) -> Assignment:
        if assignment_calls:
            gc.collect()
            assert callback_record_refs[0]() is None
            assert callback_target_refs[0]() is None
        assignment_calls.append(owner)
        return original_snapshot_assignment(value, owner, **kwargs)

    class CapturingPolicy:
        name = "capture"
        version = "1"

        def assign(
            self,
            records: tuple[FileRecord, ...],
            meta: dict[str, object],
            callback_target: ScanResult,
        ) -> Assignment:
            del meta
            callback_record_refs.append(weakref.ref(records[0]))
            callback_target_refs.append(weakref.ref(callback_target))
            detached_inputs.append(
                records[0] is not source.files[0]
                and callback_target is not target
            )
            object.__setattr__(records[0], "size", 99)
            record = records[0]
            return Assignment(
                self.name,
                self.version,
                (
                    DestinationAssignment(
                        record.rel_path,
                        record.rel_path_key,
                        record.rel_path,
                        record.rel_path_key,
                    ),
                ),
            )

    monkeypatch.setattr(
        planner_module,
        "snapshot_admitted_plan_scan",
        recording_admit,
    )
    monkeypatch.setattr(
        planner_module,
        "_snapshot_assignment",
        recording_snapshot_assignment,
    )
    result = plan(
        source,
        target,
        MappingSnapshot.empty(source.volume_id, target.volume_id),
        SyncOptions(destination_policy=CapturingPolicy()),
        Scope.everything(),
        review_admission=admission,
    )

    construction_admission = retained_calls[0]
    callback_admission = retained_calls[2]
    assert construction_admission is not admission
    assert retained_calls[:2] == [construction_admission, construction_admission]
    assert retained_calls[2:] == [callback_admission, callback_admission]
    assert callback_admission is not construction_admission
    assert assignment_calls == [callback_admission, construction_admission]
    assert callback_admission is not admission
    assert callback_admission.domain_rows == 0
    assert callback_admission.domain_bytes == 4 * PLAN_SOURCE_REFERENCE_BYTES
    assert detached_inputs == [True]
    assert callback_record_refs[0]() is None
    assert callback_target_refs[0]() is None
    assert result.operations[0].source_expected is not None
    assert result.operations[0].source_expected.size == 1


def test_planner_scan_copies_do_not_false_refuse_maximum_warning_rows() -> None:
    warning = ScanWarning(ScanWarningCode.ENUMERATION_ERROR, None, "notice")
    admission = PlanReviewAdmission()
    admission.admit(informational_rows=MAX_PLAN_REVIEW_ROWS)

    result = plan(
        _scan(warnings=(warning,)),
        _scan(),
        MappingSnapshot.empty(VOLUME, VOLUME),
        SyncOptions(),
        Scope.everything(),
        review_admission=admission,
    )

    assert result.operations == ()
    assert admission.informational_rows == MAX_PLAN_REVIEW_ROWS


@pytest.mark.parametrize("population", ("pair", "ambiguous"))
def test_mapping_snapshot_rejects_noncanonical_source_keys(
    population: str,
) -> None:
    pair = MappingPair(
        "lower.bin",
        "target.bin",
        normalize_relative_path("target.bin"),
        FileIdentity("SOURCE", 1),
        None,
    )
    correspondence = (
        MappingSnapshot(VOLUME, VOLUME, (pair,))
        if population == "pair"
        else MappingSnapshot(
            VOLUME,
            VOLUME,
            ambiguous_source_keys=frozenset({"lower.bin"}),
        )
    )

    with pytest.raises(ValueError, match="canonical"):
        planner_module.snapshot_mapping_snapshot(
            correspondence,
            review_admission=PlanReviewAdmission(),
        )


def test_required_directory_population_refuses_before_operation_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)
    monkeypatch.setattr(
        planner_module,
        "_blocked_operation",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("operation constructed after derived-row excess")
        ),
    )
    source = _scan(files=(_file(r"a\b\source.bin"),))
    target = _scan()

    with pytest.raises(ReviewFactLimitError) as caught:
        plan(
            source,
            target,
            MappingSnapshot.empty(source.volume_id, target.volume_id),
            SyncOptions(),
            Scope.everything(),
            review_admission=PlanReviewAdmission(),
        )

    assert caught.value.fact == ReviewFactLimitExceeded.plan_domain_rows()


def test_visible_unsupported_population_refuses_before_operation_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)
    monkeypatch.setattr(
        planner_module,
        "_blocked_operation",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("operation constructed after derived-row excess")
        ),
    )
    source = _scan(
        unsupported=(
            UnsupportedRecord(
                "source-blocked",
                normalize_relative_path("source-blocked"),
                UnsupportedReason.ACCESS_DENIED,
            ),
        )
    )
    target = _scan(
        unsupported=(
            UnsupportedRecord(
                "target-blocked",
                normalize_relative_path("target-blocked"),
                UnsupportedReason.ACCESS_DENIED,
            ),
        )
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        plan(
            source,
            target,
            MappingSnapshot.empty(source.volume_id, target.volume_id),
            SyncOptions(),
            Scope.everything(),
            review_admission=PlanReviewAdmission(),
        )

    assert caught.value.fact == ReviewFactLimitExceeded.plan_domain_rows()


def test_mapping_copy_admits_builder_and_final_overlap_before_freeze(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pair = MappingPair(
        normalize_relative_path("source.bin"),
        "target.bin",
        normalize_relative_path("target.bin"),
        FileIdentity("SOURCE", 1),
        None,
    )
    value = MappingSnapshot(VOLUME, VOLUME, (pair,))
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        2 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    exact_admission = PlanReviewAdmission()

    copied = planner_module.snapshot_mapping_snapshot(
        value,
        review_admission=exact_admission,
    )

    assert copied.pairs == value.pairs
    assert exact_admission.domain_bytes == PLAN_SOURCE_REFERENCE_BYTES

    allocated = False

    def forbidden_freeze(values: object) -> tuple[object, ...]:
        nonlocal allocated
        allocated = True
        raise AssertionError("mapping final container was allocated")

    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        PLAN_SOURCE_REFERENCE_BYTES,
    )
    monkeypatch.setattr(
        planner_module,
        "_freeze_reference_list",
        forbidden_freeze,
    )
    refused_admission = PlanReviewAdmission()

    with pytest.raises(ReviewFactLimitError) as caught:
        planner_module.snapshot_mapping_snapshot(
            value,
            review_admission=refused_admission,
        )

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert not allocated
    assert refused_admission.domain_bytes == 0


def test_mapping_copy_retires_sequential_population_builders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_identity = FileIdentity("SOURCE", 1)
    target_identity = FileIdentity("SOURCE", 2)
    value = MappingSnapshot(
        VOLUME,
        VOLUME,
        (
            MappingPair(
                normalize_relative_path("source.bin"),
                "target.bin",
                normalize_relative_path("target.bin"),
                source_identity,
                target_identity,
            ),
        ),
        frozenset({normalize_relative_path("ambiguous.bin")}),
        frozenset({source_identity}),
        frozenset({target_identity}),
    )
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        5 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    admission = PlanReviewAdmission()

    copied = planner_module.snapshot_mapping_snapshot(
        value,
        review_admission=admission,
    )

    assert copied == value
    assert admission.domain_bytes == 4 * PLAN_SOURCE_REFERENCE_BYTES


def test_callback_detached_file_tuple_refuses_before_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allocated = False

    def forbidden_freeze(*args: object) -> tuple[FileRecord, ...]:
        nonlocal allocated
        allocated = True
        raise AssertionError("callback file tuple was allocated")

    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        2 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    monkeypatch.setattr(
        planner_module,
        "_freeze_callback_source_files",
        forbidden_freeze,
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        plan(
            _scan(files=(_file("source.bin"),)),
            _scan(),
            MappingSnapshot.empty(VOLUME, VOLUME),
            SyncOptions(),
            Scope.everything(),
            review_admission=PlanReviewAdmission(),
        )

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert not allocated


def test_callback_assignment_source_and_copy_refuse_before_copy_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_file = _file("source.bin")
    raw_assignment = Assignment(
        "fixed",
        "1",
        (
            DestinationAssignment(
                source_file.rel_path,
                source_file.rel_path_key,
                source_file.rel_path,
                source_file.rel_path_key,
            ),
        ),
    )
    copied = False

    class FixedPolicy:
        name = "fixed"
        version = "1"

        def assign(self, *args: object) -> Assignment:
            return raw_assignment

    def forbidden_copy(*args: object) -> object:
        nonlocal copied
        copied = True
        raise AssertionError("callback assignment copy was allocated")

    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        4 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    monkeypatch.setattr(
        planner_module,
        "DestinationAssignment",
        forbidden_copy,
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        plan(
            _scan(files=(source_file,)),
            _scan(),
            MappingSnapshot.empty(VOLUME, VOLUME),
            SyncOptions(destination_policy=FixedPolicy()),
            Scope.everything(),
            review_admission=PlanReviewAdmission(),
        )

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert not copied


def test_snapshot_plan_operation_builder_peak_isolated_from_returned_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _forge_scan(
        _scan(),
        volume_id=None,
        volume_evidence=None,
    )
    target = _forge_scan(
        _scan(files=(_file("target.bin"),)),
        volume_id=None,
        volume_evidence=None,
    )
    options = SyncOptions()
    raw = plan(
        source,
        target,
        MappingSnapshot.empty(None, None),
        options,
        Scope.everything(),
    )
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        2 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    exact_admission = PlanReviewAdmission()

    copied = planner_module.snapshot_plan_candidate(
        raw,
        source,
        target,
        options,
        review_admission=exact_admission,
    )

    assert len(copied.operations) == 1
    assert exact_admission.domain_rows == 1
    assert exact_admission.domain_bytes == PLAN_SOURCE_REFERENCE_BYTES

    allocated = False

    def forbidden_freeze(values: object) -> tuple[PlanOperation, ...]:
        nonlocal allocated
        allocated = True
        raise AssertionError("snapshot operation tuple was allocated")

    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        PLAN_SOURCE_REFERENCE_BYTES,
    )
    monkeypatch.setattr(
        planner_module,
        "_freeze_snapshot_operations",
        forbidden_freeze,
    )
    refused_admission = PlanReviewAdmission()

    with pytest.raises(ReviewFactLimitError) as caught:
        planner_module.snapshot_plan_candidate(
            raw,
            source,
            target,
            options,
            review_admission=refused_admission,
        )

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert not allocated
    assert refused_admission.domain_rows == 0
    assert refused_admission.domain_bytes == 0


def test_snapshot_operation_dependency_refuses_before_first_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _forge_scan(
        _scan(),
        volume_id=None,
        volume_evidence=None,
    )
    target = _forge_scan(
        _scan(
            files=(_file("folder\\target.bin"),),
            directories=(_directory("folder"),),
        ),
        volume_id=None,
        volume_evidence=None,
    )
    options = SyncOptions()
    raw = plan(
        source,
        target,
        MappingSnapshot.empty(None, None),
        options,
        Scope.everything(),
    )
    assert any(operation.dependencies for operation in raw.operations)

    remembered = False
    frozen = False

    def forbidden_remember(*args: object) -> None:
        nonlocal remembered
        remembered = True
        raise AssertionError("dependency validation copy was retained")

    def forbidden_freeze(*args: object) -> tuple[str, ...]:
        nonlocal frozen
        frozen = True
        raise AssertionError("dependency tuple was allocated")

    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        2 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    monkeypatch.setattr(
        planner_module,
        "_remember_operation_dependency",
        forbidden_remember,
    )
    monkeypatch.setattr(
        planner_module,
        "_freeze_operation_dependencies",
        forbidden_freeze,
    )
    admission = PlanReviewAdmission()

    with pytest.raises(ReviewFactLimitError) as caught:
        planner_module.snapshot_plan_candidate(
            raw,
            source,
            target,
            options,
            review_admission=admission,
        )

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert not remembered
    assert not frozen
    assert admission.domain_rows == 0
    assert admission.domain_bytes == 0


def test_cleanup_dependency_builder_refuses_before_first_excess_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        7 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    admission = PlanReviewAdmission()
    admission.admit_domain_shape(reference_slots=2)
    gate = planner_module._OperationAdmission(admission, rows=True)
    allocated = False

    def forbidden_sort(*args: object) -> list[str]:
        nonlocal allocated
        allocated = True
        raise AssertionError("dependency sort list was allocated")

    monkeypatch.setattr(
        planner_module,
        "_sort_operation_dependencies",
        forbidden_sort,
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        planner_module._cleanup_operation_dependencies(
            iter(("c", "a", "b")),
            gate,
        )

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert not allocated
    assert admission.domain_rows == 0
    assert admission.domain_bytes == 2 * PLAN_SOURCE_REFERENCE_BYTES


def test_cleanup_dependency_tuple_refuses_before_first_excess_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        8 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    admission = PlanReviewAdmission()
    admission.admit_domain_shape(reference_slots=2)
    gate = planner_module._OperationAdmission(admission, rows=True)
    original_sort = planner_module._sort_operation_dependencies
    sorted_allocated = False
    tuple_allocated = False

    def tightening_sort(values: set[str]) -> list[str]:
        nonlocal sorted_allocated
        sorted_allocated = True
        result = original_sort(values)
        monkeypatch.setattr(
            review_module,
            "MAX_PLAN_DOMAIN_RETAINED_BYTES",
            7 * PLAN_SOURCE_REFERENCE_BYTES,
        )
        return result

    def forbidden_freeze(*args: object) -> tuple[str, ...]:
        nonlocal tuple_allocated
        tuple_allocated = True
        raise AssertionError("dependency tuple was allocated")

    monkeypatch.setattr(
        planner_module,
        "_sort_operation_dependencies",
        tightening_sort,
    )
    monkeypatch.setattr(
        planner_module,
        "_freeze_operation_dependencies",
        forbidden_freeze,
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        planner_module._cleanup_operation_dependencies(
            iter(("c", "a", "b")),
            gate,
        )

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert sorted_allocated
    assert not tuple_allocated
    assert admission.domain_rows == 0
    assert admission.domain_bytes == 2 * PLAN_SOURCE_REFERENCE_BYTES


def test_plan_operation_builder_peak_refuses_before_final_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _forge_scan(
        _scan(),
        volume_id=None,
        volume_evidence=None,
    )
    target = _forge_scan(
        _scan(files=(_file("target.bin"),)),
        volume_id=None,
        volume_evidence=None,
    )
    options = SyncOptions()
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        3 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    exact_admission = PlanReviewAdmission()

    exact = plan(
        source,
        target,
        MappingSnapshot.empty(None, None),
        options,
        Scope.everything(),
        review_admission=exact_admission,
    )

    assert len(exact.operations) == 1
    assert exact_admission.domain_rows == 1
    assert exact_admission.domain_bytes == PLAN_SOURCE_REFERENCE_BYTES

    allocated = False

    def forbidden_freeze(*args: object) -> tuple[PlanOperation, ...]:
        nonlocal allocated
        allocated = True
        raise AssertionError("producer operation tuple was allocated")

    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        2 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    monkeypatch.setattr(
        planner_module,
        "_freeze_operation_builders",
        forbidden_freeze,
    )
    refused_admission = PlanReviewAdmission()

    with pytest.raises(ReviewFactLimitError) as caught:
        plan(
            source,
            target,
            MappingSnapshot.empty(None, None),
            options,
            Scope.everything(),
            review_admission=refused_admission,
        )

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert not allocated
    assert refused_admission.domain_rows == 0
    assert refused_admission.domain_bytes == 0


def test_plan_required_volume_builder_peak_refuses_before_frozenset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        3 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    exact_admission = PlanReviewAdmission()

    exact = plan(
        _scan(),
        _scan(),
        MappingSnapshot.empty(VOLUME, VOLUME),
        SyncOptions(),
        Scope.everything(),
        review_admission=exact_admission,
    )

    assert exact.required_volumes == frozenset({VOLUME})
    assert exact_admission.domain_bytes == PLAN_SOURCE_REFERENCE_BYTES

    allocated = False

    def forbidden_freeze(values: object) -> frozenset[VolumeId]:
        nonlocal allocated
        allocated = True
        raise AssertionError("required-volume frozenset was allocated")

    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        2 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    monkeypatch.setattr(
        planner_module,
        "_freeze_required_volumes",
        forbidden_freeze,
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        plan(
            _scan(),
            _scan(),
            MappingSnapshot.empty(VOLUME, VOLUME),
            SyncOptions(),
            Scope.everything(),
            review_admission=PlanReviewAdmission(),
        )

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert not allocated


def test_snapshot_plan_required_volume_builder_peak_isolated_from_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _scan()
    target = _scan()
    options = SyncOptions()
    raw = plan(
        source,
        target,
        MappingSnapshot.empty(VOLUME, VOLUME),
        options,
        Scope.everything(),
    )
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        2 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    exact_admission = PlanReviewAdmission()

    copied = planner_module.snapshot_plan_candidate(
        raw,
        source,
        target,
        options,
        review_admission=exact_admission,
    )

    assert copied.required_volumes == raw.required_volumes
    assert exact_admission.domain_bytes == PLAN_SOURCE_REFERENCE_BYTES

    allocated = False

    def forbidden_freeze(values: object) -> frozenset[VolumeId]:
        nonlocal allocated
        allocated = True
        raise AssertionError("snapshot volume frozenset was allocated")

    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        PLAN_SOURCE_REFERENCE_BYTES,
    )
    monkeypatch.setattr(
        planner_module,
        "_freeze_required_volumes",
        forbidden_freeze,
    )
    refused_admission = PlanReviewAdmission()

    with pytest.raises(ReviewFactLimitError) as caught:
        planner_module.snapshot_plan_candidate(
            raw,
            source,
            target,
            options,
            review_admission=refused_admission,
        )

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert not allocated
    assert refused_admission.domain_bytes == 0


# Workflow-level custody and hostile-callback regressions live at the tail so
# the lower-level admission fixtures above remain independently readable.


def _workflow_scan(
    root: Root,
    *,
    files: tuple[FileRecord, ...] = (),
) -> ScanResult:
    anchor = str(root.path[:3])
    volume = VolumeId(root.root_id.upper(), "NTFS")
    return ScanResult(
        root,
        volume,
        VolumeEvidence(device_id=anchor),
        PROFILE,
        files,
        (),
        (),
        (),
        ScanScope.full(),
        True,
    )


def _workflow_plan(
    *,
    source_files: tuple[FileRecord, ...] = (),
) -> tuple[object, ScanResult, ScanResult]:
    source = _workflow_scan(
        Root(r"C:\source", "source"),
        files=source_files,
    )
    target = _workflow_scan(Root(r"D:\target", "target"))
    value = plan(
        source,
        target,
        MappingSnapshot.empty(source.volume_id, target.volume_id),
        SyncOptions(),
        Scope.everything(),
    )
    return value, source, target


class _WorkflowObservationFileSystem:
    def __init__(self, source_stats: dict[str, object] | None = None) -> None:
        self.source_stats = source_stats or {}

    def observe_root(self, authority: object) -> RootObservation:
        return RootObservation(
            authority.logical_root,
            authority.expected_volume_id,
            VolumeEvidence(device_id=authority.reviewed_anchor),
        )

    def stat(
        self,
        authority: object,
        rel_path: str,
        profile: CapabilityProfile,
    ) -> StatObservation:
        del profile
        return StatObservation(
            self.source_stats.get(rel_path)
            if authority.logical_root.startswith("C:")
            else None
        )

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
            authority.logical_root + r"\.synctrash",
            True,
            True,
            True,
            True,
            True,
        )

    def now_utc(self) -> _datetime:
        return _datetime.now(_timezone.utc)


def _empty_correspondence(
    source: ScanResult,
    target: ScanResult,
    *,
    review_admission: PlanReviewAdmission | None = None,
) -> MappingSnapshot:
    result = MappingSnapshot.empty(source.volume_id, target.volume_id)
    if review_admission is not None:
        admit_plan_mapping_copy(result, review_admission)
    return result


def _workflow_dependencies(
    scanner: object,
    saved: list[object],
    *,
    correspondence: object = _empty_correspondence,
) -> SimpleNamespace:
    source_stat = _file("source.bin").stat
    return SimpleNamespace(
        scanner=scanner,
        ignores=IgnoreSet(),
        correspondence=correspondence,
        planner=plan,
        observer=observe,
        observation_fs=_WorkflowObservationFileSystem(
            {"source.bin": source_stat}
        ),
        preflight=preflight,
        save_plan=saved.append,
    )


def _run_plan_scanner(
    root: Root,
    ignores: IgnoreSet,
    ctx: RunContext,
    *,
    review_admission: PlanReviewAdmission | None = None,
) -> ScanResult:
    del ignores, ctx
    result = _workflow_scan(
        root,
        files=(_file("source.bin"),) if root.root_id == "source" else (),
    )
    if review_admission is not None:
        admit_retained_plan_scan(result, review_admission)
    return result


def _run_plan_request() -> PlanRequest:
    return PlanRequest("a" * 32, r"C:\source", r"D:\target")


def _patch_workflow_roots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sync_workflow_module,
        "_validated_roots",
        lambda source, target: (
            Root(source, "source"),
            Root(target, "target"),
        ),
    )


def test_operation_subject_producer_refuses_first_excess_without_partial_insert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value, _, _ = _workflow_plan(
        source_files=(_file("first.bin"), _file("second.bin"))
    )
    selection = frozenset(operation.op_id for operation in value.operations)
    xset = ExecutionSet(value, selection, validated_run_id("b" * 32))
    admission = PlanReviewAdmission()
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 2)

    with pytest.raises(ReviewFactLimitError) as caught:
        preflight_module._operation_subjects(
            xset,
            review_admission=admission,
        )

    assert caught.value.fact == ReviewFactLimitExceeded.plan_domain_rows()
    assert admission.domain_bytes == 5 * PLAN_SOURCE_REFERENCE_BYTES


def test_runtime_correspondence_refuses_input_first_excess_before_repository(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    runtime = object.__new__(LocalWorkflowRuntime)
    runtime.ledger_path = tmp_path / "ledger.db"
    runtime.ledger_path.touch()
    source = _workflow_scan(Root(r"C:\source", "source"))
    target = _workflow_scan(
        Root(r"D:\target", "target"),
        files=(_file("first.bin"), _file("second.bin")),
    )
    admission = PlanReviewAdmission()
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 1)

    with pytest.raises(ReviewFactLimitError) as caught:
        runtime._correspondence(
            source,
            target,
            review_admission=admission,
        )

    assert caught.value.fact == ReviewFactLimitExceeded.plan_domain_rows()
    assert admission.domain_bytes == 0


def test_refusal_collector_owner_admission_is_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_INFORMATIONAL_RETAINED_BYTES",
        5 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    admission = PlanReviewAdmission()
    collector = preflight_module._PlanRefusalCollector(admission)

    with pytest.raises(ReviewFactLimitError) as caught:
        collector.append(Refusal(RefusalCode.ROOTS_OVERLAP))

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_informational_retained_bytes()
    )
    assert tuple(collector.values()) == ()
    assert collector._raw_count == 0
    assert admission.informational_rows == 0
    assert admission.informational_bytes == 0


def test_refusal_collector_refuses_before_candidate_key_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HashBomb:
        def __hash__(self) -> int:
            raise AssertionError("candidate key was used before admission")

    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_INFORMATIONAL_RETAINED_BYTES",
        3 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    admission = PlanReviewAdmission()
    collector = preflight_module._PlanRefusalCollector(admission)
    refusal = Refusal(RefusalCode.ROOTS_OVERLAP)
    object.__setattr__(refusal, "code", HashBomb())

    with pytest.raises(ReviewFactLimitError) as caught:
        collector.append(refusal)

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_informational_retained_bytes()
    )


def test_refusal_collector_duplicate_charges_only_candidate_key_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_INFORMATIONAL_RETAINED_BYTES",
        10 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    admission = PlanReviewAdmission()
    collector = preflight_module._PlanRefusalCollector(admission)
    duplicate = Refusal(RefusalCode.ROOTS_OVERLAP)

    collector.append(duplicate)
    collector.append(duplicate)

    assert tuple(collector.values()) == (duplicate,)
    assert collector._raw_count == 2
    assert admission.informational_rows == 1
    assert admission.informational_bytes == 6 * PLAN_SOURCE_REFERENCE_BYTES


def test_preflight_checks_sort_and_final_tuple_overlap_before_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value, source, target = _workflow_plan()
    xset = ExecutionSet(value, frozenset(), validated_run_id("c" * 32))
    source_root = RootObservation(
        r"E:\same",
        source.volume_id,
        source.volume_evidence,
    )
    target_root = RootObservation(
        r"E:\same",
        target.volume_id,
        target.volume_evidence,
    )
    world = ObservedWorld(
        {},
        {},
        frozenset(),
        {
            value.source_root.root_id: source_root,
            value.target_root.root_id: target_root,
        },
        0,
        0,
        None,
        _datetime.now(_timezone.utc),
    )
    admission = PlanReviewAdmission()
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_INFORMATIONAL_RETAINED_BYTES",
        7 * PLAN_SOURCE_REFERENCE_BYTES,
    )

    with pytest.raises(ReviewFactLimitError) as caught:
        preflight(xset, world, review_admission=admission)

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_informational_retained_bytes()
    )
    assert admission.informational_rows == 0
    assert admission.informational_bytes == 0


def test_observed_world_snapshot_never_invokes_hostile_deepcopy() -> None:
    value, _, _ = _workflow_plan(source_files=(_file("source.bin"),))
    selection = derive_execution_selection(value).selection
    allowed_paths, allowed_parents = sync_workflow_module._plan_observation_scope(
        value,
        selection,
        PlanReviewAdmission(),
    )
    subject = next(
        subject
        for subject in allowed_paths
        if subject.root_id == value.source_root.root_id
    )

    class Hostile:
        calls = 0

        def __deepcopy__(self, memo: object) -> object:
            del memo
            type(self).calls += 1
            raise AssertionError("hostile deepcopy was invoked")

    observation = StatObservation(None)
    object.__setattr__(observation, "stat", Hostile())
    world = ObservedWorld(
        {subject: observation},
        {subject: allowed_paths[subject]},
        frozenset(),
        {},
        None,
        0,
        None,
        _datetime.now(_timezone.utc),
    )

    with pytest.raises(TypeError, match="file stat"):
        sync_workflow_module._snapshot_plan_observed_world(
            world,
            value,
            allowed_paths,
            allowed_parents,
            PlanReviewAdmission(),
        )

    assert Hostile.calls == 0


def test_observed_world_snapshot_rejects_raw_mapping_proxy_before_iteration() -> None:
    value, _, _ = _workflow_plan()
    raw = ObservedWorld(
        _MappingProxyType({}),
        {},
        frozenset(),
        {},
        None,
        0,
        None,
        _datetime.now(_timezone.utc),
    )

    with pytest.raises(TypeError, match="exact dictionaries"):
        sync_workflow_module._snapshot_plan_observed_world(
            raw,
            value,
            {},
            frozenset(),
            PlanReviewAdmission(),
        )


def test_observed_world_snapshot_rejects_foreign_path_and_nonexact_utc() -> None:
    value, _, _ = _workflow_plan(source_files=(_file("source.bin"),))
    selection = derive_execution_selection(value).selection
    allowed_paths, allowed_parents = sync_workflow_module._plan_observation_scope(
        value,
        selection,
        PlanReviewAdmission(),
    )
    subject = next(iter(allowed_paths))
    stat = StatObservation(None)
    foreign = ObservedWorld(
        {subject: stat},
        {subject: "foreign.bin"},
        frozenset(),
        {},
        None,
        0,
        None,
        _datetime.now(_timezone.utc),
    )
    with pytest.raises(ValueError, match="outside the plan"):
        sync_workflow_module._snapshot_plan_observed_world(
            foreign,
            value,
            allowed_paths,
            allowed_parents,
            PlanReviewAdmission(),
        )

    utc_alias = _timezone(_timedelta(0), "UTC alias")
    wrong_time = _replace(foreign, paths={subject: allowed_paths[subject]})
    object.__setattr__(wrong_time, "observed_at", _datetime.now(utc_alias))
    with pytest.raises(TypeError, match="exact UTC datetime"):
        sync_workflow_module._snapshot_plan_observed_world(
            wrong_time,
            value,
            allowed_paths,
            allowed_parents,
            PlanReviewAdmission(),
        )


def test_observed_world_snapshot_rejects_nonexact_nested_fields() -> None:
    value, _, _ = _workflow_plan(source_files=(_file("source.bin"),))
    selection = derive_execution_selection(value).selection
    allowed_paths, allowed_parents = sync_workflow_module._plan_observation_scope(
        value,
        selection,
        PlanReviewAdmission(),
    )
    subject = next(iter(allowed_paths))
    observed_at = _datetime.now(_timezone.utc)

    stat = StatObservation(None)
    object.__setattr__(stat, "contained", 1)
    invalid_stat = ObservedWorld(
        {subject: stat},
        {subject: allowed_paths[subject]},
        frozenset(),
        {},
        None,
        0,
        None,
        observed_at,
    )
    root = RootObservation(None, None, None)
    object.__setattr__(root, "resolved_path", object())
    invalid_root = ObservedWorld(
        {},
        {},
        frozenset(),
        {value.source_root.root_id: root},
        None,
        0,
        None,
        observed_at,
    )
    trash = TrashObservation(None, True, True, True, True, True)
    object.__setattr__(trash, "available", 1)
    invalid_trash = ObservedWorld(
        {},
        {},
        frozenset(),
        {},
        None,
        0,
        trash,
        observed_at,
    )
    invalid_scalar = ObservedWorld(
        {},
        {},
        frozenset(),
        {},
        None,
        0,
        None,
        observed_at,
    )
    object.__setattr__(invalid_scalar, "free_space", True)

    for world in (invalid_stat, invalid_root, invalid_trash, invalid_scalar):
        with pytest.raises(TypeError):
            sync_workflow_module._snapshot_plan_observed_world(
                world,
                value,
                allowed_paths,
                allowed_parents,
                PlanReviewAdmission(),
            )


def test_plan_verdict_rejects_refusal_for_unselected_operation() -> None:
    value, _, _ = _workflow_plan(
        source_files=(_file("first.bin"), _file("second.bin"))
    )
    selection = frozenset({value.operations[0].op_id})
    allowed_paths, allowed_parents = sync_workflow_module._plan_observation_scope(
        value,
        selection,
        PlanReviewAdmission(),
    )
    callback_world = ObservedWorld(
        _MappingProxyType({}),
        _MappingProxyType({}),
        frozenset(),
        _MappingProxyType({}),
        None,
        0,
        None,
        _datetime.now(_timezone.utc),
    )
    authoritative_world = _replace(callback_world)
    raw = Verdict(
        False,
        (
            Refusal(
                RefusalCode.ROOT_CHANGED,
                value.operations[1].op_id,
            ),
        ),
        callback_world,
    )

    with pytest.raises(ValueError, match="unselected operation"):
        sync_workflow_module._snapshot_plan_verdict(
            raw,
            callback_world,
            callback_world.stats,
            callback_world.paths,
            callback_world.roots,
            authoritative_world,
            value,
            allowed_paths,
            allowed_parents,
            selection,
            PlanReviewAdmission(),
        )


def test_plan_verdict_copy_charges_key_dictionary_sort_and_tuple_owners() -> None:
    value, _, _ = _workflow_plan(source_files=(_file("source.bin"),))
    selection = frozenset({value.operations[0].op_id})
    callback_world = ObservedWorld(
        _MappingProxyType({}),
        _MappingProxyType({}),
        frozenset(),
        _MappingProxyType({}),
        None,
        0,
        None,
        _datetime.now(_timezone.utc),
    )
    authoritative_world = _replace(callback_world)
    raw = Verdict(
        False,
        (Refusal(RefusalCode.ROOT_CHANGED, value.operations[0].op_id),),
        callback_world,
    )
    admission = PlanReviewAdmission()

    snapshot = sync_workflow_module._snapshot_plan_verdict(
        raw,
        callback_world,
        callback_world.stats,
        callback_world.paths,
        callback_world.roots,
        authoritative_world,
        value,
        {},
        frozenset(),
        selection,
        admission,
    )

    assert snapshot.refusals == raw.refusals
    assert admission.informational_rows == 0
    assert (
        admission.informational_bytes
        == 8 * PLAN_SOURCE_REFERENCE_BYTES
    )


def test_plan_verdict_refuses_before_candidate_key_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value, _, _ = _workflow_plan(source_files=(_file("source.bin"),))
    selection = frozenset({value.operations[0].op_id})
    callback_world = ObservedWorld(
        _MappingProxyType({}),
        _MappingProxyType({}),
        frozenset(),
        _MappingProxyType({}),
        None,
        0,
        None,
        _datetime.now(_timezone.utc),
    )
    authoritative_world = _replace(callback_world)
    raw = Verdict(
        False,
        (Refusal(RefusalCode.ROOT_CHANGED, value.operations[0].op_id),),
        callback_world,
    )
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_INFORMATIONAL_RETAINED_BYTES",
        3 * PLAN_SOURCE_REFERENCE_BYTES,
    )

    def hash_bomb(value: object) -> int:
        del value
        raise AssertionError("candidate key was used before admission")

    monkeypatch.setattr(RefusalCode, "__hash__", hash_bomb)

    with pytest.raises(ReviewFactLimitError) as caught:
        sync_workflow_module._snapshot_plan_verdict(
            raw,
            callback_world,
            callback_world.stats,
            callback_world.paths,
            callback_world.roots,
            authoritative_world,
            value,
            {},
            frozenset(),
            selection,
            PlanReviewAdmission(),
        )

    assert caught.value.fact == (
        ReviewFactLimitExceeded.plan_informational_retained_bytes()
    )


def test_plan_verdict_duplicate_charges_only_candidate_key_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value, _, _ = _workflow_plan(source_files=(_file("source.bin"),))
    selection = frozenset({value.operations[0].op_id})
    callback_world = ObservedWorld(
        _MappingProxyType({}),
        _MappingProxyType({}),
        frozenset(),
        _MappingProxyType({}),
        None,
        0,
        None,
        _datetime.now(_timezone.utc),
    )
    authoritative_world = _replace(callback_world)
    duplicate = Refusal(RefusalCode.ROOT_CHANGED, value.operations[0].op_id)
    raw = Verdict(False, (duplicate, duplicate), callback_world)
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_INFORMATIONAL_RETAINED_BYTES",
        10 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    admission = PlanReviewAdmission()

    snapshot = sync_workflow_module._snapshot_plan_verdict(
        raw,
        callback_world,
        callback_world.stats,
        callback_world.paths,
        callback_world.roots,
        authoritative_world,
        value,
        {},
        frozenset(),
        selection,
        admission,
    )

    assert snapshot.refusals == (duplicate,)
    assert admission.informational_bytes == 8 * PLAN_SOURCE_REFERENCE_BYTES


def test_plan_review_selection_matches_blocked_dependency_semantics() -> None:
    value, _, _ = _workflow_plan(
        source_files=(
            _file("blocked.bin"),
            _file("dependent.bin"),
            _file("safe.bin"),
        )
    )
    blocked, dependent, safe = value.operations
    blocked = _replace(blocked, blocked_reason=BlockedReason.UNSUPPORTED)
    dependent = _replace(dependent, dependencies=(blocked.op_id,))
    value = _replace(value, operations=(blocked, dependent, safe))

    actual = derive_plan_review_selection(
        value,
        review_admission=PlanReviewAdmission(),
    )

    assert actual == derive_execution_selection(value).selection
    assert actual == frozenset({safe.op_id})


def test_run_plan_clones_ignore_set_for_each_scanner_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[object] = []
    observed_names: list[frozenset[str]] = []
    _patch_workflow_roots(monkeypatch)

    def scanner(
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ScanResult:
        observed_names.append(ignores.exact_names)
        if len(observed_names) == 1:
            object.__setattr__(
                ignores,
                "exact_names",
                frozenset({"MUTATED"}),
            )
        return _run_plan_scanner(
            root,
            ignores,
            ctx,
            review_admission=review_admission,
        )

    result = run_plan(
        _run_plan_request(),
        RunContext(lambda event: None, lambda: None),
        _workflow_dependencies(scanner, saved),
    )

    assert result.status is SessionState.COMPLETED
    assert observed_names == [IgnoreSet().exact_names, IgnoreSet().exact_names]
    assert len(saved) == 1


def test_run_plan_refuses_raw_scan_and_capture_overlap_without_saving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[object] = []
    calls = 0
    _patch_workflow_roots(monkeypatch)

    def scanner(*args: object, **kwargs: object) -> ScanResult:
        nonlocal calls
        calls += 1
        return _run_plan_scanner(*args, **kwargs)

    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        3 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    result = run_plan(
        _run_plan_request(),
        RunContext(lambda event: None, lambda: None),
        _workflow_dependencies(scanner, saved),
    )

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert result.review_fact_limit == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert calls == 1
    assert saved == []


def test_run_plan_drops_correspondence_producer_peak_before_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[object] = []
    _patch_workflow_roots(monkeypatch)

    def empty_scanner(
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ScanResult:
        del ignores, ctx
        result = _workflow_scan(root)
        if review_admission is not None:
            admit_retained_plan_scan(result, review_admission)
        return result

    def correspondence(
        source: ScanResult,
        target: ScanResult,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> MappingSnapshot:
        assert review_admission is not None
        review_admission.admit_domain_shape(reference_slots=17)
        result = MappingSnapshot.empty(source.volume_id, target.volume_id)
        admit_plan_mapping_copy(result, review_admission)
        return result

    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        20 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    result = run_plan(
        _run_plan_request(),
        RunContext(lambda event: None, lambda: None),
        _workflow_dependencies(
            empty_scanner,
            saved,
            correspondence=correspondence,
        ),
    )

    assert result.status is SessionState.COMPLETED
    assert len(saved) == 1


def test_run_plan_keeps_scope_owners_through_observer_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[object] = []
    observer_returned = False
    _patch_workflow_roots(monkeypatch)
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        45 * PLAN_SOURCE_REFERENCE_BYTES,
    )

    deps = _workflow_dependencies(_run_plan_scanner, saved)

    def recording_observer(*args: object, **kwargs: object) -> ObservedWorld:
        nonlocal observer_returned
        value = observe(*args, **kwargs)
        observer_returned = True
        return value

    deps.observer = recording_observer
    result = run_plan(
        _run_plan_request(),
        RunContext(lambda event: None, lambda: None),
        deps,
    )

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert result.review_fact_limit == (
        ReviewFactLimitExceeded.plan_domain_retained_bytes()
    )
    assert observer_returned
    assert saved == []


def test_run_plan_checks_selection_producer_copy_then_retires_raw_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[object] = []
    calls: list[tuple[PlanReviewAdmission, int, int]] = []
    producer_calls: list[tuple[PlanReviewAdmission, int, int]] = []
    _patch_workflow_roots(monkeypatch)
    original = sync_workflow_module._admit_plan_selection_shape
    original_producer = sync_workflow_module.derive_plan_review_selection

    def recording_admission(
        value: object,
        admission: PlanReviewAdmission,
    ) -> frozenset[object]:
        before = admission.domain_bytes
        retained = original(value, admission)
        calls.append((admission, before, admission.domain_bytes))
        return retained

    monkeypatch.setattr(
        sync_workflow_module,
        "_admit_plan_selection_shape",
        recording_admission,
    )

    def recording_producer(
        value: object,
        *,
        review_admission: PlanReviewAdmission,
    ) -> frozenset[object]:
        before = review_admission.domain_bytes
        retained = original_producer(
            value,
            review_admission=review_admission,
        )
        producer_calls.append(
            (review_admission, before, review_admission.domain_bytes)
        )
        return retained

    monkeypatch.setattr(
        sync_workflow_module,
        "derive_plan_review_selection",
        recording_producer,
    )

    result = run_plan(
        _run_plan_request(),
        RunContext(lambda event: None, lambda: None),
        _workflow_dependencies(_run_plan_scanner, saved),
    )

    assert result.status is SessionState.COMPLETED
    assert len(saved) == 1
    raw_owner, raw_before, raw_after = producer_calls[0]
    copy_owner, copy_before, copy_after = calls[0]
    retained_owner, retained_before, retained_after = calls[1]
    assert len({id(raw_owner), id(copy_owner), id(retained_owner)}) == 3
    assert raw_after - raw_before == PLAN_SOURCE_REFERENCE_BYTES
    assert copy_before == raw_after
    assert copy_after - copy_before == PLAN_SOURCE_REFERENCE_BYTES
    assert retained_before == raw_before
    assert retained_after - retained_before == PLAN_SOURCE_REFERENCE_BYTES


def test_plan_review_selection_capture_accepts_exact_raw_and_copy_peak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value, _, _ = _workflow_plan(source_files=(_file("source.bin"),))
    monkeypatch.setattr(
        review_module,
        "MAX_PLAN_DOMAIN_RETAINED_BYTES",
        2 * PLAN_SOURCE_REFERENCE_BYTES,
    )
    producer = PlanReviewAdmission()

    raw = derive_plan_review_selection(value, review_admission=producer)
    capture = producer.fork()
    copied = sync_workflow_module._snapshot_plan_selection(raw, capture)

    assert producer.domain_bytes == PLAN_SOURCE_REFERENCE_BYTES
    assert copied == raw
    assert copied is not raw
    assert capture.domain_bytes == 2 * PLAN_SOURCE_REFERENCE_BYTES


def test_run_plan_revalidates_preflight_world_before_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[object] = []
    _patch_workflow_roots(monkeypatch)

    class HostileMapping(dict[object, object]):
        comparisons = 0

        def __eq__(self, other: object) -> bool:
            del other
            type(self).comparisons += 1
            raise AssertionError("hostile equality was invoked")

        def __ne__(self, other: object) -> bool:
            del other
            type(self).comparisons += 1
            raise AssertionError("hostile inequality was invoked")

    def mutating_preflight(
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict:
        del execution_set, review_admission
        object.__setattr__(world, "stats", HostileMapping(world.stats))
        return Verdict(True, (), world)

    deps = _workflow_dependencies(_run_plan_scanner, saved)
    deps.preflight = mutating_preflight

    with pytest.raises(TypeError, match="owned observed-world mapping"):
        run_plan(
            _run_plan_request(),
            RunContext(lambda event: None, lambda: None),
            deps,
        )

    assert HostileMapping.comparisons == 0
    assert saved == []


def test_run_plan_rejects_equal_mapping_type_mutation_from_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[object] = []
    _patch_workflow_roots(monkeypatch)

    def mutating_preflight(
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict:
        del execution_set, review_admission
        object.__setattr__(world, "stats", dict(world.stats))
        return Verdict(True, (), world)

    deps = _workflow_dependencies(_run_plan_scanner, saved)
    deps.preflight = mutating_preflight

    with pytest.raises(TypeError, match="owned observed-world mapping"):
        run_plan(
            _run_plan_request(),
            RunContext(lambda event: None, lambda: None),
            deps,
        )

    assert saved == []


def test_run_plan_rejects_equal_replacement_mapping_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[object] = []
    _patch_workflow_roots(monkeypatch)

    def mutating_preflight(
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict:
        del execution_set, review_admission
        object.__setattr__(
            world,
            "stats",
            _MappingProxyType(dict(world.stats)),
        )
        return Verdict(True, (), world)

    deps = _workflow_dependencies(_run_plan_scanner, saved)
    deps.preflight = mutating_preflight

    with pytest.raises(TypeError, match="owned observed-world mapping"):
        run_plan(
            _run_plan_request(),
            RunContext(lambda event: None, lambda: None),
            deps,
        )

    assert saved == []


def test_run_plan_rejects_hostile_proxy_backing_before_delegation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[object] = []
    _patch_workflow_roots(monkeypatch)

    class HostileBacking(dict[object, object]):
        calls = 0

        def __len__(self) -> int:
            type(self).calls += 1
            raise AssertionError("hostile proxy length was invoked")

        def __iter__(self):
            type(self).calls += 1
            raise AssertionError("hostile proxy iteration was invoked")

        def items(self):
            type(self).calls += 1
            raise AssertionError("hostile proxy items were invoked")

        def __eq__(self, other: object) -> bool:
            del other
            type(self).calls += 1
            raise AssertionError("hostile proxy equality was invoked")

    def mutating_preflight(
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict:
        del execution_set, review_admission
        backing = HostileBacking()
        dict.update(backing, dict(world.stats))
        object.__setattr__(world, "stats", _MappingProxyType(backing))
        return Verdict(True, (), world)

    deps = _workflow_dependencies(_run_plan_scanner, saved)
    deps.preflight = mutating_preflight

    with pytest.raises(TypeError, match="owned observed-world mapping"):
        run_plan(
            _run_plan_request(),
            RunContext(lambda event: None, lambda: None),
            deps,
        )

    assert HostileBacking.calls == 0
    assert saved == []


def test_run_plan_freezes_request_fields_before_policy_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_id = "a" * 32
    original_source = r"C:\source"
    original_target = r"D:\target"
    drifted_id = "b" * 32
    drifted_source = r"E:\drifted-source"
    drifted_target = r"F:\drifted-target"
    saved: list[object] = []
    observed_run_ids: list[str] = []

    class MutatingPolicy:
        request: PlanRequest

        @property
        def name(self) -> str:
            object.__setattr__(self.request, "request_id", drifted_id)
            object.__setattr__(self.request, "source_path", drifted_source)
            object.__setattr__(self.request, "target_path", drifted_target)
            return "identity"

        version = "1"

        def assign(
            self,
            records: object,
            meta: object,
            target: object,
        ) -> Assignment:
            return SyncOptions().destination_policy.assign(records, meta, target)

    policy = MutatingPolicy()
    request = PlanRequest(
        original_id,
        original_source,
        original_target,
        SyncOptions(destination_policy=policy),
    )
    policy.request = request
    _patch_workflow_roots(monkeypatch)
    deps = _workflow_dependencies(_run_plan_scanner, saved)
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
    assert request.request_id == drifted_id
    assert request.source_path == drifted_source
    assert request.target_path == drifted_target
    assert observed_run_ids == [original_id]
    assert len(saved) == 1
    artifact = saved[0]
    assert artifact.request.request_id == original_id
    assert artifact.request.source_path == original_source
    assert artifact.request.target_path == original_target
    assert artifact.source_scan.root.path == original_source
    assert artifact.target_scan.root.path == original_target


def _saturate_plan_domain_bytes(admission: PlanReviewAdmission) -> None:
    admission.admit(
        domain_bytes=(
            review_module.MAX_PLAN_DOMAIN_RETAINED_BYTES
            - admission.domain_bytes
        )
    )


def _saturate_plan_informational_bytes(
    admission: PlanReviewAdmission,
) -> None:
    admission.admit(
        informational_bytes=(
            review_module.MAX_PLAN_INFORMATIONAL_RETAINED_BYTES
            - admission.informational_bytes
        )
    )


@pytest.mark.parametrize(
    ("stage", "expected_fact", "expected_calls"),
    (
        pytest.param(
            "target-scan",
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
            ("scan-source", "scan-target"),
            id="target-scan",
        ),
        pytest.param(
            "correspondence-producer",
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
            ("scan-source", "scan-target", "correspondence"),
            id="correspondence-producer",
        ),
        pytest.param(
            "correspondence-copy",
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
            ("scan-source", "scan-target", "correspondence"),
            id="correspondence-copy",
        ),
        pytest.param(
            "planner-producer",
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
            ("scan-source", "scan-target", "correspondence", "planner"),
            id="planner-producer",
        ),
        pytest.param(
            "planner-copy",
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
            ("scan-source", "scan-target", "correspondence", "planner"),
            id="planner-copy",
        ),
        pytest.param(
            "planner-final-candidate",
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
            ("scan-source", "scan-target", "correspondence", "planner"),
            id="planner-final-candidate",
        ),
        pytest.param(
            "selection",
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
            ("scan-source", "scan-target", "correspondence", "planner"),
            id="selection",
        ),
        pytest.param(
            "observer-final-retention",
            ReviewFactLimitExceeded.plan_domain_retained_bytes(),
            (
                "scan-source",
                "scan-target",
                "correspondence",
                "planner",
                "observer",
            ),
            id="observer-final-retention",
        ),
        pytest.param(
            "preflight-producer",
            ReviewFactLimitExceeded.plan_informational_retained_bytes(),
            (
                "scan-source",
                "scan-target",
                "correspondence",
                "planner",
                "observer",
                "preflight",
            ),
            id="preflight-producer",
        ),
        pytest.param(
            "preflight-copy",
            ReviewFactLimitExceeded.plan_informational_retained_bytes(),
            (
                "scan-source",
                "scan-target",
                "correspondence",
                "planner",
                "observer",
                "preflight",
            ),
            id="preflight-copy",
        ),
        pytest.param(
            "final-verdict-retention",
            ReviewFactLimitExceeded.plan_informational_rows(),
            (
                "scan-source",
                "scan-target",
                "correspondence",
                "planner",
                "observer",
                "preflight",
            ),
            id="final-verdict-retention",
        ),
    ),
)
def test_run_plan_refuses_each_first_excess_stage_without_publication(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    expected_fact: ReviewFactLimitExceeded,
    expected_calls: tuple[str, ...],
) -> None:
    calls: list[str] = []
    saved: list[object] = []
    _patch_workflow_roots(monkeypatch)
    if stage == "final-verdict-retention":
        monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 2)

    def scanner(
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ScanResult:
        del ignores, ctx
        calls.append(f"scan-{root.root_id}")
        warnings = (
            (
                ScanWarning(ScanWarningCode.ENUMERATION_ERROR, None, "first"),
                ScanWarning(ScanWarningCode.DISAPPEARED, "gone.bin", "second"),
            )
            if stage == "final-verdict-retention" and root.root_id == "source"
            else ()
        )
        files = (
            (_file("source.bin"),)
            if root.root_id == "source"
            else ((_file("target.bin"),) if stage == "target-scan" else ())
        )
        result = _replace(
            _workflow_scan(root, files=files),
            warnings=warnings,
        )
        assert review_admission is not None
        if stage == "target-scan" and root.root_id == "target":
            _saturate_plan_domain_bytes(review_admission)
        admit_retained_plan_scan(result, review_admission)
        return result

    def correspondence(
        source: ScanResult,
        target: ScanResult,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> MappingSnapshot:
        calls.append("correspondence")
        assert review_admission is not None
        if stage == "correspondence-producer":
            _saturate_plan_domain_bytes(review_admission)
            review_admission.admit_domain_shape(reference_slots=1)
        if stage == "correspondence-copy":
            result = MappingSnapshot(
                source.volume_id,
                target.volume_id,
                ambiguous_source_keys=frozenset({"SOURCE.BIN"}),
            )
            admit_plan_mapping_copy(result, review_admission)
            _saturate_plan_domain_bytes(review_admission)
            return result
        return _empty_correspondence(
            source,
            target,
            review_admission=review_admission,
        )

    def planner(
        source: ScanResult,
        target: ScanResult,
        mapping: MappingSnapshot,
        options: SyncOptions,
        scope: Scope,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> object:
        calls.append("planner")
        assert review_admission is not None
        if stage == "planner-producer":
            _saturate_plan_domain_bytes(review_admission)
            review_admission.admit_domain_shape(reference_slots=1)
        if stage in {
            "planner-copy",
            "planner-final-candidate",
        }:
            result = plan(source, target, mapping, options, scope)
            _saturate_plan_domain_bytes(review_admission)
            if stage == "planner-final-candidate":
                admit_retained_plan_candidate(result, review_admission)
            return result
        return plan(
            source,
            target,
            mapping,
            options,
            scope,
            review_admission=review_admission,
        )

    def observer(
        execution_set: ExecutionSet,
        fs: object,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ObservedWorld:
        calls.append("observer")
        assert review_admission is not None
        if stage == "observer-final-retention":
            result = observe(execution_set, fs)
            _saturate_plan_domain_bytes(review_admission)
            return result
        return observe(
            execution_set,
            fs,
            review_admission=review_admission,
        )

    def preflight_callback(
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict:
        calls.append("preflight")
        assert review_admission is not None
        if stage == "preflight-producer":
            _saturate_plan_informational_bytes(review_admission)
            review_admission.admit_informational_shape(reference_slots=1)
        if stage == "preflight-copy":
            result = Verdict(
                False,
                (Refusal(RefusalCode.ROOT_CHANGED),),
                world,
            )
            review_admission.admit_informational_shape(reference_slots=1)
            _saturate_plan_informational_bytes(review_admission)
            return result
        if stage == "final-verdict-retention":
            return Verdict(
                False,
                (Refusal(RefusalCode.ROOT_CHANGED),),
                world,
            )
        return preflight(
            execution_set,
            world,
            review_admission=review_admission,
        )

    if stage == "selection":
        real_selection = sync_workflow_module.derive_plan_review_selection

        def saturated_selection(
            value: object,
            *,
            review_admission: PlanReviewAdmission,
        ) -> frozenset[object]:
            _saturate_plan_domain_bytes(review_admission)
            return real_selection(
                value,
                review_admission=review_admission,
            )

        monkeypatch.setattr(
            sync_workflow_module,
            "derive_plan_review_selection",
            saturated_selection,
        )

    deps = _workflow_dependencies(
        scanner,
        saved,
        correspondence=correspondence,
    )
    deps.planner = planner
    deps.observer = observer
    deps.preflight = preflight_callback
    result = run_plan(
        _run_plan_request(),
        RunContext(lambda event: None, lambda: None),
        deps,
    )

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert result.review_fact_limit == expected_fact
    assert tuple(calls) == expected_calls
    assert saved == []


def test_protected_full_scanner_output_matches_ordinary_output() -> None:
    root = Root(r"C:\source", "source")
    context = RunContext(lambda event: None, lambda: None)

    ordinary = WalkingScanner(
        _ScannerBackend([_StableScannerEntry()])
    ).scan(root, IgnoreSet(), context)
    protected = WalkingScanner(
        _ScannerBackend([_StableScannerEntry()])
    ).scan(
        root,
        IgnoreSet(),
        context,
        review_admission=PlanReviewAdmission(),
    )

    assert ordinary.complete and ordinary.scope == ScanScope.full()
    assert ordinary.files and ordinary.directories
    assert protected == ordinary


def test_protected_plan_observe_and_preflight_match_ordinary_semantics() -> None:
    source_files = (
        _file(r"folder\copy.bin", size=5),
        _file("same.bin", size=3),
        _file("update.bin", size=4),
    )
    target_files = (
        _file("obsolete.bin", size=7),
        _file("same.bin", size=3),
        _file("update.bin", size=2),
    )
    source = _replace(
        _workflow_scan(
            Root(r"C:\source", "source"),
            files=source_files,
        ),
        directories=(_directory("folder"),),
    )
    target = _workflow_scan(
        Root(r"D:\target", "target"),
        files=target_files,
    )
    mapping = MappingSnapshot.empty(source.volume_id, target.volume_id)
    options = SyncOptions()

    ordinary_plan = plan(
        source,
        target,
        mapping,
        options,
        Scope.everything(),
    )
    protected_plan = plan(
        source,
        target,
        mapping,
        options,
        Scope.everything(),
        review_admission=PlanReviewAdmission(),
    )

    expected_kinds = {
        OperationKind.MKDIR,
        OperationKind.COPY,
        OperationKind.NOOP,
        OperationKind.UPDATE,
        OperationKind.TRASH,
    }
    assert {operation.kind for operation in ordinary_plan.operations} == expected_kinds
    assert protected_plan == ordinary_plan
    assert protected_plan.fingerprint == ordinary_plan.fingerprint

    fixed_now = _datetime(2026, 8, 27, 12, 0, tzinfo=_timezone.utc)

    class SemanticObservationFileSystem(_WorkflowObservationFileSystem):
        def __init__(self) -> None:
            super().__init__({record.rel_path: record.stat for record in source_files})
            self.target_stats = {
                record.rel_path: record.stat for record in target_files
            }

        def stat(
            self,
            authority: object,
            rel_path: str,
            profile: CapabilityProfile,
        ) -> StatObservation:
            del profile
            population = (
                self.source_stats
                if authority.logical_root.startswith("C:")
                else self.target_stats
            )
            return StatObservation(population.get(rel_path))

        def now_utc(self) -> _datetime:
            return fixed_now

    fs = SemanticObservationFileSystem()
    run_id = validated_run_id("c" * 32)
    ordinary_xset = ExecutionSet(
        ordinary_plan,
        derive_execution_selection(ordinary_plan).selection,
        run_id,
    )
    protected_xset = ExecutionSet(
        protected_plan,
        derive_execution_selection(protected_plan).selection,
        run_id,
    )

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
