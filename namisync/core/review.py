"""Typed review limits and finite prepublication plan-source admission."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import (
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
    validate_scan_result,
)
from .scalars import (
    MAX_SIGNED_64,
    ScalarDomainError,
    checked_add_signed_64,
    require_safe_int,
    require_signed_64,
)


class ReviewTreeKind(StrEnum):
    PLAN = "plan"
    INVENTORY = "inventory"


class ReviewPopulation(StrEnum):
    DOMAIN = "domain"
    INFORMATIONAL = "informational"


class ReviewLimitAxis(StrEnum):
    ROWS = "rows"
    RETAINED_BYTES = "retained-bytes"
    LOGICAL_BYTES = "logical-bytes"


@dataclass(frozen=True, slots=True)
class ReviewFactLimitExceeded:
    """Exact bounded fact explaining why no complete review was published."""

    reason: str
    tree_kind: ReviewTreeKind
    population: ReviewPopulation
    axis: ReviewLimitAxis
    row_limit: int | None
    byte_limit: int | None

    def __post_init__(self) -> None:
        if self.reason != "review_fact_limit_exceeded":
            raise ValueError("review fact reason is invalid")
        if not isinstance(self.tree_kind, ReviewTreeKind):
            raise TypeError("review tree_kind has the wrong type")
        if not isinstance(self.population, ReviewPopulation):
            raise TypeError("review population has the wrong type")
        if not isinstance(self.axis, ReviewLimitAxis):
            raise TypeError("review axis has the wrong type")
        if self.row_limit is not None:
            require_safe_int(self.row_limit, "review row_limit")
        if self.byte_limit is not None:
            require_signed_64(self.byte_limit, "review byte_limit")
        if self.axis is ReviewLimitAxis.ROWS:
            if self.row_limit != 120_000 or self.byte_limit is not None:
                raise ValueError("row review fact has invalid limits")
            return
        if self.row_limit is not None or self.byte_limit is None:
            raise ValueError("byte review fact has invalid nullability")
        if self.axis is ReviewLimitAxis.LOGICAL_BYTES:
            if (
                self.tree_kind is not ReviewTreeKind.PLAN
                or self.population is not ReviewPopulation.DOMAIN
                or self.byte_limit != MAX_SIGNED_64
            ):
                raise ValueError("logical-byte review fact is invalid")
            return
        expected = (
            134_217_728
            if self.tree_kind is ReviewTreeKind.PLAN
            and self.population is ReviewPopulation.DOMAIN
            else 201_326_592
        )
        if self.byte_limit != expected:
            raise ValueError("retained-byte review fact has the wrong limit")

    @classmethod
    def plan_logical_bytes(cls) -> "ReviewFactLimitExceeded":
        return cls(
            reason="review_fact_limit_exceeded",
            tree_kind=ReviewTreeKind.PLAN,
            population=ReviewPopulation.DOMAIN,
            axis=ReviewLimitAxis.LOGICAL_BYTES,
            row_limit=None,
            byte_limit=MAX_SIGNED_64,
        )

    @classmethod
    def plan_domain_rows(cls) -> "ReviewFactLimitExceeded":
        return cls(
            reason="review_fact_limit_exceeded",
            tree_kind=ReviewTreeKind.PLAN,
            population=ReviewPopulation.DOMAIN,
            axis=ReviewLimitAxis.ROWS,
            row_limit=120_000,
            byte_limit=None,
        )

    @classmethod
    def plan_domain_retained_bytes(cls) -> "ReviewFactLimitExceeded":
        return cls(
            reason="review_fact_limit_exceeded",
            tree_kind=ReviewTreeKind.PLAN,
            population=ReviewPopulation.DOMAIN,
            axis=ReviewLimitAxis.RETAINED_BYTES,
            row_limit=None,
            byte_limit=134_217_728,
        )

    @classmethod
    def plan_informational_rows(cls) -> "ReviewFactLimitExceeded":
        return cls(
            reason="review_fact_limit_exceeded",
            tree_kind=ReviewTreeKind.PLAN,
            population=ReviewPopulation.INFORMATIONAL,
            axis=ReviewLimitAxis.ROWS,
            row_limit=120_000,
            byte_limit=None,
        )

    @classmethod
    def plan_informational_retained_bytes(
        cls,
    ) -> "ReviewFactLimitExceeded":
        return cls(
            reason="review_fact_limit_exceeded",
            tree_kind=ReviewTreeKind.PLAN,
            population=ReviewPopulation.INFORMATIONAL,
            axis=ReviewLimitAxis.RETAINED_BYTES,
            row_limit=None,
            byte_limit=201_326_592,
        )


class ReviewFactLimitError(ValueError):
    """Raised before publication when a complete review cannot be represented."""

    def __init__(self, fact: ReviewFactLimitExceeded) -> None:
        super().__init__(fact.reason)
        self.fact = fact


MAX_PLAN_REVIEW_ROWS = 120_000
MAX_PLAN_DOMAIN_RETAINED_BYTES = 134_217_728
MAX_PLAN_INFORMATIONAL_RETAINED_BYTES = 201_326_592
PLAN_SOURCE_REFERENCE_BYTES = 8


class PlanReviewAdmission:
    """Bound one unpublished plan's retained rows and reference slots.

    Raw producer populations are checked independently because sequential
    source collections do not become completed plan rows merely by being read.
    Full identity-deduplicated graph validation remains the artifact
    reservation validator's job.
    """

    __slots__ = (
        "_domain_rows",
        "_domain_bytes",
        "_informational_rows",
        "_informational_bytes",
    )

    def __init__(self) -> None:
        self._domain_rows = 0
        self._domain_bytes = 0
        self._informational_rows = 0
        self._informational_bytes = 0

    @property
    def domain_rows(self) -> int:
        return self._domain_rows

    @property
    def domain_bytes(self) -> int:
        return self._domain_bytes

    @property
    def informational_rows(self) -> int:
        return self._informational_rows

    @property
    def informational_bytes(self) -> int:
        return self._informational_bytes

    def fork(self) -> "PlanReviewAdmission":
        """Return an isolated counter snapshot for one disposable producer."""

        forked = PlanReviewAdmission()
        forked._domain_rows = self._domain_rows
        forked._domain_bytes = self._domain_bytes
        forked._informational_rows = self._informational_rows
        forked._informational_bytes = self._informational_bytes
        return forked

    def admit(
        self,
        *,
        domain_rows: int = 0,
        domain_bytes: int = 0,
        informational_rows: int = 0,
        informational_bytes: int = 0,
    ) -> None:
        """Atomically admit final retained charges in fixed policy order."""

        charges = (
            (domain_rows, "plan domain rows"),
            (domain_bytes, "plan domain retained bytes"),
            (informational_rows, "plan informational rows"),
            (informational_bytes, "plan informational retained bytes"),
        )
        for value, field_name in charges:
            _require_nonnegative_int(value, field_name)

        next_domain_rows = self._domain_rows + domain_rows
        next_domain_bytes = self._domain_bytes + domain_bytes
        next_informational_rows = self._informational_rows + informational_rows
        next_informational_bytes = (
            self._informational_bytes + informational_bytes
        )
        if next_domain_rows > MAX_PLAN_REVIEW_ROWS:
            raise ReviewFactLimitError(
                ReviewFactLimitExceeded.plan_domain_rows()
            )
        if next_domain_bytes > MAX_PLAN_DOMAIN_RETAINED_BYTES:
            raise ReviewFactLimitError(
                ReviewFactLimitExceeded.plan_domain_retained_bytes()
            )
        if next_informational_rows > MAX_PLAN_REVIEW_ROWS:
            raise ReviewFactLimitError(
                ReviewFactLimitExceeded.plan_informational_rows()
            )
        if (
            next_informational_bytes
            > MAX_PLAN_INFORMATIONAL_RETAINED_BYTES
        ):
            raise ReviewFactLimitError(
                ReviewFactLimitExceeded.plan_informational_retained_bytes()
            )

        self._domain_rows = next_domain_rows
        self._domain_bytes = next_domain_bytes
        self._informational_rows = next_informational_rows
        self._informational_bytes = next_informational_bytes

    def require_source_rows(self, count: int) -> None:
        """Check one independent raw domain population without retaining it."""

        _require_nonnegative_int(count, "plan source row count")
        if count > MAX_PLAN_REVIEW_ROWS:
            raise ReviewFactLimitError(
                ReviewFactLimitExceeded.plan_domain_rows()
            )

    def require_informational_source_rows(self, count: int) -> None:
        """Check one independent raw notice population without retaining it."""

        _require_nonnegative_int(count, "plan informational source row count")
        if count > MAX_PLAN_REVIEW_ROWS:
            raise ReviewFactLimitError(
                ReviewFactLimitExceeded.plan_informational_rows()
            )

    def admit_domain_shape(
        self,
        *,
        reference_slots: int = 0,
        rows: int = 0,
    ) -> None:
        self._admit_shape(
            reference_slots=reference_slots,
            rows=rows,
            informational=False,
        )

    def admit_informational_shape(
        self,
        *,
        reference_slots: int = 0,
        rows: int = 1,
    ) -> None:
        self._admit_shape(
            reference_slots=reference_slots,
            rows=rows,
            informational=True,
        )

    def _admit_shape(
        self,
        *,
        reference_slots: int,
        rows: int,
        informational: bool,
    ) -> None:
        _require_nonnegative_int(reference_slots, "retained reference slots")
        _require_nonnegative_int(rows, "plan review row charge")
        retained_bytes = reference_slots * PLAN_SOURCE_REFERENCE_BYTES
        if informational:
            self.admit(
                informational_rows=rows,
                informational_bytes=retained_bytes,
            )
        else:
            self.admit(domain_rows=rows, domain_bytes=retained_bytes)


def snapshot_plan_scan_result(
    result: ScanResult,
    admission: PlanReviewAdmission,
    *,
    logical_source: bool = False,
) -> ScanResult:
    """Validate and copy one exact bounded scan graph for plan construction."""

    _validate_plan_scan_source(
        result,
        admission,
        logical_source=logical_source,
    )
    snapshot = _copy_plan_scan_result(result)
    _validate_plan_scan_source(
        snapshot,
        admission,
        logical_source=logical_source,
    )
    return snapshot


def snapshot_admitted_plan_scan(
    result: ScanResult,
    admission: PlanReviewAdmission,
    *,
    logical_source: bool = False,
    retain_information: bool = False,
) -> ScanResult:
    """Admit copy slots before constructing one detached exact scan."""

    if type(retain_information) is not bool:
        raise TypeError("retain_information must be a bool")
    domain_count, informational_count = _validate_plan_scan_source(
        result,
        admission,
        logical_source=logical_source,
    )
    admission.admit(
        domain_bytes=domain_count * PLAN_SOURCE_REFERENCE_BYTES,
        informational_rows=(
            informational_count if retain_information else 0
        ),
        informational_bytes=(
            informational_count * PLAN_SOURCE_REFERENCE_BYTES
        ),
    )
    snapshot = _copy_plan_scan_result(result)
    _validate_plan_scan_source(
        snapshot,
        admission,
        logical_source=logical_source,
    )
    return snapshot


def admit_retained_plan_scan(
    result: ScanResult,
    admission: PlanReviewAdmission,
) -> None:
    """Charge tuple slots and retained warnings, never scan domain rows."""

    domain_count, informational_count = _validate_plan_scan_source(
        result,
        admission,
        logical_source=False,
    )
    admission.admit(
        domain_bytes=domain_count * PLAN_SOURCE_REFERENCE_BYTES,
        informational_rows=informational_count,
        informational_bytes=(
            informational_count * PLAN_SOURCE_REFERENCE_BYTES
        ),
    )


def admit_plan_scan_copy(
    result: ScanResult,
    admission: PlanReviewAdmission,
) -> None:
    """Charge one disposable scan copy without recounting review rows."""

    domain_count, informational_count = _validate_plan_scan_source(
        result,
        admission,
        logical_source=False,
    )
    admission.admit(
        domain_bytes=domain_count * PLAN_SOURCE_REFERENCE_BYTES,
        informational_bytes=(
            informational_count * PLAN_SOURCE_REFERENCE_BYTES
        ),
    )


def _validate_plan_scan_source(
    result: ScanResult,
    admission: PlanReviewAdmission,
    *,
    logical_source: bool,
) -> tuple[int, int]:
    domain_count, informational_count = _bounded_scan_counts(
        result,
        admission,
    )
    if type(logical_source) is not bool:
        raise TypeError("logical_source must be a bool")
    if logical_source:
        logical_bytes = 0
        for record in result.files:
            if type(record) is not FileRecord:
                raise TypeError(
                    "plan scan files must contain exact FileRecord values"
                )
            # Re-admit the individual scalar before translating only a valid
            # population's aggregate overflow into a review-limit refusal.
            FileRecord(
                record.rel_path,
                record.rel_path_key,
                record.size,
                record.mtime_ns,
                record.file_identity,
                record.nlink,
                record.metadata,
            )
            try:
                logical_bytes = checked_add_signed_64(
                    logical_bytes,
                    record.size,
                    "plan logical bytes",
                )
            except ScalarDomainError as error:
                raise ReviewFactLimitError(
                    ReviewFactLimitExceeded.plan_logical_bytes()
                ) from error
    admission.require_informational_source_rows(informational_count)
    validate_scan_result(result)
    return domain_count, informational_count


def _copy_plan_scan_result(result: ScanResult) -> ScanResult:
    """Reconstruct the declared graph without copying undeclared attributes."""

    def copy_identity(value: FileIdentity | None) -> FileIdentity | None:
        return (
            None
            if value is None
            else FileIdentity(value.volume_serial, value.file_index)
        )

    def copy_metadata(value: MetadataSnapshot) -> MetadataSnapshot:
        return MetadataSnapshot(value.attributes, value.created_ns)

    return ScanResult(
        root=Root(result.root.path, result.root.root_id),
        volume_id=(
            None
            if result.volume_id is None
            else VolumeId(result.volume_id.serial, result.volume_id.fs_type)
        ),
        volume_evidence=(
            None
            if result.volume_evidence is None
            else VolumeEvidence(
                result.volume_evidence.label,
                result.volume_evidence.device_id,
                result.volume_evidence.clone_ambiguous,
            )
        ),
        profile=CapabilityProfile(
            result.profile.fs_type,
            result.profile.mtime_granularity_ns,
            result.profile.stable_file_identity,
            result.profile.incurs_seek_penalty,
            result.profile.max_path,
            result.profile.supports_ads,
            result.profile.supports_hardlinks,
        ),
        files=tuple(
            FileRecord(
                record.rel_path,
                record.rel_path_key,
                record.size,
                record.mtime_ns,
                copy_identity(record.file_identity),
                record.nlink,
                copy_metadata(record.metadata),
            )
            for record in result.files
        ),
        directories=tuple(
            DirRecord(
                record.rel_path,
                record.rel_path_key,
                record.mtime_ns,
                copy_metadata(record.metadata),
                copy_identity(record.file_identity),
                record.nlink,
            )
            for record in result.directories
        ),
        unsupported=tuple(
            UnsupportedRecord(
                record.rel_path,
                record.rel_path_key,
                record.reason,
                record.kind,
            )
            for record in result.unsupported
        ),
        warnings=tuple(
            ScanWarning(warning.code, warning.rel_path, warning.detail)
            for warning in result.warnings
        ),
        scope=ScanScope(
            result.scope.kind,
            tuple(result.scope.selected_paths),
            tuple(result.scope.subtree_roots),
        ),
        complete=result.complete,
    )


def _bounded_scan_counts(
    result: ScanResult,
    admission: PlanReviewAdmission,
) -> tuple[int, int]:
    if type(result) is not ScanResult:
        raise TypeError("plan scanner must return an exact ScanResult")
    if type(admission) is not PlanReviewAdmission:
        raise TypeError("plan review admission has the wrong type")
    for field_name, population in (
        ("files", result.files),
        ("directories", result.directories),
        ("unsupported", result.unsupported),
        ("warnings", result.warnings),
    ):
        if type(population) is not tuple:
            raise TypeError(f"plan scan {field_name} must be an exact tuple")
    domain_count = (
        len(result.files)
        + len(result.directories)
        + len(result.unsupported)
    )
    admission.require_source_rows(domain_count)
    return domain_count, len(result.warnings)


def _require_nonnegative_int(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be a non-Boolean integer")
    if value < 0:
        raise ValueError(f"{field_name} must be nonnegative")
    return value
