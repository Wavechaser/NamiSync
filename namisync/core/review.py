"""Typed review limits and finite prepublication plan-source admission."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .models import (
    CapabilityProfile,
    DirRecord,
    FileRecord,
    Root,
    ScanResult,
    ScanScope,
    ScanWarning,
    UnsupportedRecord,
    VolumeEvidence,
    VolumeId,
)
from .scalars import (
    MAX_SIGNED_64,
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


class ScanPopulationAdmission(Protocol):
    """Gate aggregate scanner populations before each owned append."""

    def require_source_rows(self, count: int) -> None: ...

    def require_informational_source_rows(self, count: int) -> None: ...


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
        if (
            type(self.reason) is not str
            or self.reason != "review_fact_limit_exceeded"
        ):
            raise ValueError("review fact reason is invalid")
        if type(self.tree_kind) is not ReviewTreeKind:
            raise TypeError("review tree_kind has the wrong type")
        if type(self.population) is not ReviewPopulation:
            raise TypeError("review population has the wrong type")
        if type(self.axis) is not ReviewLimitAxis:
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


class _PlanReviewLimitSignal(ValueError):
    """Private exact signal for an unpublished plan-review limit."""

    def __init__(
        self,
        fact: ReviewFactLimitExceeded,
        *,
        _admission_token: object | None = None,
    ) -> None:
        super().__init__(fact.reason)
        self.fact = fact
        self._admission_token = _admission_token


def snapshot_review_fact_limit(value: object) -> ReviewFactLimitExceeded:
    """Return one fresh exact review refusal fact."""

    if type(value) is not ReviewFactLimitExceeded:
        raise TypeError("review fact limit must be exact")
    return ReviewFactLimitExceeded(
        value.reason,
        value.tree_kind,
        value.population,
        value.axis,
        value.row_limit,
        value.byte_limit,
    )


MAX_PLAN_REVIEW_ROWS = 120_000
MAX_PLAN_DOMAIN_RETAINED_BYTES = 134_217_728
MAX_PLAN_INFORMATIONAL_RETAINED_BYTES = 201_326_592
PLAN_SOURCE_REFERENCE_BYTES = 8


def require_population_measure(value: object, field_name: str) -> int:
    """Return one exact, nonnegative population measure."""

    if type(value) is not int:
        raise TypeError(f"{field_name} must be a non-Boolean integer")
    if value < 0:
        raise ValueError(f"{field_name} must be nonnegative")
    return value


def exceeds_population_wall(
    value: object,
    *,
    limit: int,
    field_name: str,
) -> bool:
    """Return whether one validated population exceeds its declared wall."""

    return require_population_measure(value, field_name) > limit


class PlanReviewProducerAdmission:
    """Gate independent raw producer populations without retaining charges."""

    __slots__ = ("_admission_token",)

    def __init__(
        self,
        retained_admission: PlanReviewAdmission | None = None,
    ) -> None:
        if retained_admission is None:
            self._admission_token = object()
        elif type(retained_admission) is PlanReviewAdmission:
            self._admission_token = retained_admission._admission_token
        else:
            raise TypeError("plan review admission has the wrong type")

    def _limit_signal(
        self,
        fact: ReviewFactLimitExceeded,
    ) -> _PlanReviewLimitSignal:
        return _PlanReviewLimitSignal(
            fact,
            _admission_token=self._admission_token,
        )

    def require_source_rows(self, count: int) -> None:
        """Check one independent raw domain population without retaining it."""

        if exceeds_population_wall(
            count,
            limit=MAX_PLAN_REVIEW_ROWS,
            field_name="plan source row count",
        ):
            raise self._limit_signal(
                ReviewFactLimitExceeded.plan_domain_rows()
            )

    def require_informational_source_rows(self, count: int) -> None:
        """Check one independent raw notice population without retaining it."""

        if exceeds_population_wall(
            count,
            limit=MAX_PLAN_REVIEW_ROWS,
            field_name="plan informational source row count",
        ):
            raise self._limit_signal(
                ReviewFactLimitExceeded.plan_informational_rows()
            )


class PlanReviewAdmission:
    """Bound one unpublished plan's final retained rows and reference slots."""

    __slots__ = (
        "_admission_token",
        "_domain_rows",
        "_domain_bytes",
        "_informational_rows",
        "_informational_bytes",
    )

    def __init__(self) -> None:
        self._admission_token = object()
        self._domain_rows = 0
        self._domain_bytes = 0
        self._informational_rows = 0
        self._informational_bytes = 0

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
            require_population_measure(value, field_name)

        next_domain_rows = self._domain_rows + domain_rows
        next_domain_bytes = self._domain_bytes + domain_bytes
        next_informational_rows = self._informational_rows + informational_rows
        next_informational_bytes = (
            self._informational_bytes + informational_bytes
        )
        if exceeds_population_wall(
            next_domain_rows,
            limit=MAX_PLAN_REVIEW_ROWS,
            field_name="plan domain rows",
        ):
            raise self._limit_signal(
                ReviewFactLimitExceeded.plan_domain_rows()
            )
        if exceeds_population_wall(
            next_domain_bytes,
            limit=MAX_PLAN_DOMAIN_RETAINED_BYTES,
            field_name="plan domain retained bytes",
        ):
            raise self._limit_signal(
                ReviewFactLimitExceeded.plan_domain_retained_bytes()
            )
        if exceeds_population_wall(
            next_informational_rows,
            limit=MAX_PLAN_REVIEW_ROWS,
            field_name="plan informational rows",
        ):
            raise self._limit_signal(
                ReviewFactLimitExceeded.plan_informational_rows()
            )
        if exceeds_population_wall(
            next_informational_bytes,
            limit=MAX_PLAN_INFORMATIONAL_RETAINED_BYTES,
            field_name="plan informational retained bytes",
        ):
            raise self._limit_signal(
                ReviewFactLimitExceeded.plan_informational_retained_bytes()
            )

        self._domain_rows = next_domain_rows
        self._domain_bytes = next_domain_bytes
        self._informational_rows = next_informational_rows
        self._informational_bytes = next_informational_bytes

    def _limit_signal(
        self,
        fact: ReviewFactLimitExceeded,
    ) -> _PlanReviewLimitSignal:
        return _PlanReviewLimitSignal(
            fact,
            _admission_token=self._admission_token,
        )


def adopt_plan_scan_result(
    result: ScanResult,
    admission: PlanReviewProducerAdmission,
) -> ScanResult:
    """Adopt one exact immutable plan scan after counter-free source admission."""

    _require_plan_producer_admission(admission)
    return adopt_scan_result(
        result,
        admission,
        row_limit=MAX_PLAN_REVIEW_ROWS,
    )


def adopt_scan_result(
    result: object,
    admission: ScanPopulationAdmission,
    *,
    row_limit: int,
) -> ScanResult:
    """Validate and adopt one bounded immutable scan without rebuilding it."""

    require_population_measure(row_limit, "scan population row limit")
    populations = _plan_scan_populations(result)
    files, directories, unsupported, warnings = populations
    assert type(result) is ScanResult
    if type(result.root) is not Root:
        raise TypeError("scan root has the wrong type")
    if result.volume_id is not None and type(result.volume_id) is not VolumeId:
        raise TypeError("scan volume has the wrong type")
    if (
        result.volume_evidence is not None
        and type(result.volume_evidence) is not VolumeEvidence
    ):
        raise TypeError("scan volume evidence has the wrong type")
    if type(result.profile) is not CapabilityProfile:
        raise TypeError("scan capability profile has the wrong type")
    if type(result.scope) is not ScanScope:
        raise TypeError("scan scope has the wrong type")
    if type(result.complete) is not bool:
        raise TypeError("scan completeness must be an exact bool")

    domain_count = len(files) + len(directories) + len(unsupported)
    informational_count = len(warnings)
    if exceeds_population_wall(
        domain_count,
        limit=row_limit,
        field_name="scan domain rows",
    ):
        admission.require_source_rows(row_limit + 1)
        raise RuntimeError("scan admission accepted an excess domain population")
    admission.require_source_rows(domain_count)

    if exceeds_population_wall(
        informational_count,
        limit=row_limit,
        field_name="scan informational rows",
    ):
        admission.require_informational_source_rows(row_limit + 1)
        raise RuntimeError(
            "scan admission accepted an excess informational population"
        )
    admission.require_informational_source_rows(informational_count)
    return result


def admit_retained_plan_scan(
    result: ScanResult,
    admission: PlanReviewAdmission,
) -> None:
    """Charge tuple slots and retained warnings, never scan domain rows."""

    _require_plan_admission(admission)
    files, directories, unsupported, warnings = _plan_scan_populations(result)
    domain_count = len(files) + len(directories) + len(unsupported)
    informational_count = len(warnings)
    admission.admit(
        domain_bytes=domain_count * PLAN_SOURCE_REFERENCE_BYTES,
        informational_rows=informational_count,
        informational_bytes=(
            informational_count * PLAN_SOURCE_REFERENCE_BYTES
        ),
    )


def _plan_scan_populations(
    result: object,
) -> tuple[
    tuple[FileRecord, ...],
    tuple[DirRecord, ...],
    tuple[UnsupportedRecord, ...],
    tuple[ScanWarning, ...],
]:
    if type(result) is not ScanResult:
        raise TypeError("scanner must return an exact ScanResult")
    populations = (
        ("files", result.files),
        ("directories", result.directories),
        ("unsupported", result.unsupported),
        ("warnings", result.warnings),
    )
    for field_name, population in populations:
        if type(population) is not tuple:
            raise TypeError(f"scan {field_name} must be an exact tuple")
    return (
        populations[0][1],
        populations[1][1],
        populations[2][1],
        populations[3][1],
    )


def _require_plan_admission(value: object) -> PlanReviewAdmission:
    if type(value) is not PlanReviewAdmission:
        raise TypeError("plan review admission has the wrong type")
    return value


def _require_plan_producer_admission(
    value: object,
) -> PlanReviewProducerAdmission:
    if type(value) is not PlanReviewProducerAdmission:
        raise TypeError("plan review admission has the wrong type")
    return value
