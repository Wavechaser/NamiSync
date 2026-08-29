"""Executor continuation state and injected collaborator protocols."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
import re
from types import MappingProxyType
from typing import BinaryIO, NewType, Protocol, TypeAlias

from .evidence import (
    Attestation,
    ContentEvidence,
    Outcome,
    Provenance,
    RecordingStatus,
    attestation_fact,
)
from .models import (
    EntryKind,
    FileStat,
    VolumeId,
)
from .pathing import normalize_relative_path
from .planning import (
    OpId,
    OperationKind,
    Plan,
    PlanFingerprint,
    PlanOperation,
    plan_fingerprint,
)
from .scalars import (
    bounded_utf8_text,
    checked_add_signed_64,
    require_safe_int,
    require_signed_64,
)


RunId = NewType("RunId", str)

_FIXED_ID = re.compile(r"[0-9a-f]{32}\Z")
RECORDING_DETAIL_MAX_BYTES = 1024


def validated_run_id(value: str) -> RunId:
    """Return a fixed-format run id suitable for owned artifact names."""

    if _FIXED_ID.fullmatch(value) is None:
        raise ValueError("run id must contain exactly 32 lowercase hex digits")
    return RunId(value)


class ItemRecordingReason(StrEnum):
    """Closed operation-local causes of recording degradation."""

    RECORD_WRITE_FAILED = "record-write-failed"
    UNRECORDED_MUTATION = "unrecorded-mutation"
    RECORDING_PREREQUISITE_FAILED = "recording-prerequisite-failed"


def validate_item_recording_outcome(
    outcome: Outcome | None, reason: ItemRecordingReason
) -> None:
    """Require one degraded item's reason to agree with filesystem truth."""

    if not isinstance(reason, ItemRecordingReason):
        raise TypeError("item recording reason has the wrong type")
    expected = (
        {Outcome.SUCCEEDED, Outcome.SKIPPED}
        if reason is ItemRecordingReason.RECORD_WRITE_FAILED
        else {Outcome.FAILED}
    )
    if outcome not in expected:
        raise ValueError("item recording reason contradicts operation outcome")


class TaskRecordingIssueReason(StrEnum):
    """Closed task-wide causes of recording degradation."""

    RECORDING_OPEN_FAILED = "recording-open-failed"
    FINAL_FLUSH_FAILED = "final-flush-failed"
    FINISH_FAILED = "finish-failed"
    RECORDING_CLOSE_FAILED = "recording-close-failed"
    POST_SETTLEMENT_STATE_DIVERGED = "post-settlement-state-diverged"


def bounded_recording_detail(value: str | None) -> str | None:
    """Return a complete bounded diagnostic, or omit it without truncation."""

    return bounded_utf8_text(
        value,
        "recording detail",
        maximum_bytes=RECORDING_DETAIL_MAX_BYTES,
    )


@dataclass(frozen=True, slots=True)
class TaskRecordingIssue:
    """First bounded observation of one task-wide recording failure class."""

    reason: TaskRecordingIssueReason
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reason, TaskRecordingIssueReason):
            raise TypeError("task recording issue reason has the wrong type")
        if bounded_recording_detail(self.detail) != self.detail:
            raise ValueError("task recording issue detail exceeds its bound")


@dataclass(frozen=True, slots=True)
class Commitment:
    """Human authorization bound to one plan and exact operation selection."""

    plan_fingerprint: PlanFingerprint
    selection_digest: bytes
    committed_at: datetime

    def __post_init__(self) -> None:
        if not self.plan_fingerprint:
            raise ValueError("commitment plan fingerprint is required")
        if len(self.selection_digest) != 32:
            raise ValueError("commitment selection digest must contain 32 bytes")
        if self.committed_at.tzinfo is None or self.committed_at.utcoffset() is None:
            raise ValueError("commitment timestamp must be timezone-aware")
        if self.committed_at.utcoffset() != timezone.utc.utcoffset(self.committed_at):
            raise ValueError("commitment timestamp must be UTC")


@dataclass(frozen=True, slots=True)
class RecordingSpec:
    """Immutable reviewed inputs exposed to run-recording collaborators."""

    plan: Plan
    selection: frozenset[OpId]
    run_id: RunId
    commitment: Commitment | None

    def __post_init__(self) -> None:
        if type(self.plan) is not Plan:
            raise TypeError("recording spec plan has the wrong type")
        if type(self.selection) is not frozenset:
            raise TypeError("recording spec selection must be an exact frozenset")
        if type(self.run_id) is not str:
            raise TypeError("recording spec run id must be exact text")
        validated_run_id(self.run_id)
        if self.commitment is not None and type(self.commitment) is not Commitment:
            raise TypeError("recording spec commitment has the wrong type")


@dataclass(frozen=True, slots=True)
class RecordedCopyIdentity:
    """Durable ledger identity returned by one successful copy transaction."""

    row_id: str
    location_id: str
    scope_token: str
    rel_path_key: str

    def __post_init__(self) -> None:
        values = (
            self.row_id,
            self.location_id,
            self.scope_token,
            self.rel_path_key,
        )
        if not all(isinstance(value, str) for value in values):
            raise TypeError("recorded copy identity fields must be strings")
        if not all(values):
            raise ValueError("recorded copy identity fields must be non-empty strings")
        if normalize_relative_path(self.rel_path_key) != self.rel_path_key:
            raise ValueError("recorded copy relative path key must be canonical")


@dataclass(frozen=True, slots=True)
class PublishedCopyEvidence:
    """Post-publish evidence plus optional durable ledger identity."""

    attestation: Attestation
    recorded_identity: RecordedCopyIdentity | None

    def __post_init__(self) -> None:
        if not isinstance(self.attestation, Attestation):
            raise TypeError("published copy evidence requires an attestation")
        if self.attestation.content.provenance is not Provenance.COPY_ATTESTED:
            raise ValueError("published copy evidence must be copy-attested")
        if self.attestation.subject.kind is not EntryKind.FILE:
            raise ValueError("published copy evidence must attest a regular file")
        if self.recorded_identity is not None and not isinstance(
            self.recorded_identity, RecordedCopyIdentity
        ):
            raise TypeError("recorded copy identity has the wrong type")

    @property
    def copy_recorded(self) -> bool:
        """Whether the copy transaction returned a complete durable identity."""

        return self.recorded_identity is not None


def _validate_published_evidence_shape(
    value: object,
) -> PublishedCopyEvidence:
    """Validate immutable evidence shape and its local compound relations."""

    if type(value) is not PublishedCopyEvidence:
        raise TypeError("published evidence must have the exact public shape")
    attestation = value.attestation
    if type(attestation) is not Attestation:
        raise TypeError("published evidence attestation has the wrong type")
    content = attestation.content
    subject = attestation.subject
    if type(content) is not ContentEvidence:
        raise TypeError("published evidence content has the wrong type")
    if type(subject) is not FileStat:
        raise TypeError("published evidence subject has the wrong type")
    if type(content.algorithm) is not str:
        raise TypeError("published evidence algorithm must be exact text")
    if type(content.digest) is not bytes:
        raise TypeError("published evidence digest must be exact bytes")
    if type(content.observed_at) is not datetime:
        raise TypeError("published evidence time must be an exact datetime")
    if type(content.size) is not int or type(subject.size) is not int:
        raise TypeError("published evidence sizes must be exact integers")
    if content.provenance is not Provenance.COPY_ATTESTED:
        raise ValueError("published copy evidence must be copy-attested")
    if subject.kind is not EntryKind.FILE:
        raise ValueError("published copy evidence must attest a regular file")
    if content.size != subject.size:
        raise ValueError("attestation content size must match its subject")
    recorded = value.recorded_identity
    if recorded is not None:
        if type(recorded) is not RecordedCopyIdentity:
            raise TypeError("recorded copy identity has the wrong type")
        if any(
            type(field_value) is not str
            for field_value in (
                recorded.row_id,
                recorded.location_id,
                recorded.scope_token,
                recorded.rel_path_key,
            )
        ):
            raise TypeError("recorded copy identity fields must be exact text")
    return value


def _remaining_operations(
    plan: Plan,
    selection: frozenset[OpId],
    status: Mapping[OpId, Outcome],
) -> tuple[PlanOperation, ...]:
    """Return selected unsettled operations in reviewed plan order."""

    return tuple(
        operation
        for operation in plan.operations
        if operation.op_id in selection and operation.op_id not in status
    )


@dataclass(frozen=True, slots=True)
class ExecutionReview:
    """Immutable execution facts exposed to read-only collaborators."""

    plan: Plan
    selection: frozenset[OpId]
    run_id: RunId
    status: Mapping[OpId, Outcome]

    def __post_init__(self) -> None:
        if type(self.plan) is not Plan or type(self.plan.operations) is not tuple:
            raise TypeError("execution review plan has the wrong shape")
        if type(self.plan.fingerprint) is not str:
            raise TypeError("execution review plan fingerprint must be exact text")
        if type(self.selection) is not frozenset:
            raise TypeError("execution review selection must be an exact frozenset")
        if type(self.run_id) is not str:
            raise TypeError("execution review run id must be exact text")
        validated_run_id(self.run_id)
        if type(self.status) not in {dict, MappingProxyType}:
            raise TypeError(
                "execution review status must be an exact dict or mapping proxy"
            )
        if any(
            type(op_id) is not str or _FIXED_ID.fullmatch(op_id) is None
            for op_id in self.selection
        ):
            raise TypeError("execution review selection must contain exact ids")
        operation_ids: set[OpId] = set()
        for operation in self.plan.operations:
            if type(operation) is not PlanOperation:
                raise TypeError(
                    "execution review plan must contain exact PlanOperation values"
                )
            operation_ids.add(operation.op_id)
        unknown = self.selection - operation_ids
        if unknown:
            raise ValueError(
                "execution review selection contains unknown operation ids: "
                f"{sorted(unknown)!r}"
            )
        status = dict(self.status)
        if any(
            type(op_id) is not str or _FIXED_ID.fullmatch(op_id) is None
            for op_id in status
        ):
            raise TypeError("execution review status must contain exact ids")
        if any(type(outcome) is not Outcome for outcome in status.values()):
            raise TypeError("execution review status values have the wrong type")
        invalid_status = status.keys() - self.selection
        if invalid_status:
            raise ValueError(
                "execution review status contains unselected operation ids: "
                f"{sorted(invalid_status)!r}"
            )
        object.__setattr__(self, "status", MappingProxyType(status))

    def remaining(self) -> tuple[PlanOperation, ...]:
        """Return selected operations without a final status, in plan order."""

        return _remaining_operations(self.plan, self.selection, self.status)


@dataclass(slots=True)
class ExecutionSet:
    """A selected plan plus mutable continuation state for pause/resume."""

    plan: Plan
    selection: frozenset[OpId]
    run_id: RunId
    status: dict[OpId, Outcome] = field(default_factory=dict)
    commitment: Commitment | None = None
    published_evidence: dict[OpId, PublishedCopyEvidence] = field(
        default_factory=dict
    )
    recording_reasons: dict[OpId, ItemRecordingReason] = field(
        default_factory=dict
    )
    recording_issues: tuple[TaskRecordingIssue, ...] = ()
    omitted_detail_count: int = 0
    user_deselected: frozenset[OpId] = frozenset()
    bytes_done_high_water: int = field(default=0, repr=False)
    _selected_bytes_bound: int = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        validated_run_id(str(self.run_id))
        operations = {
            operation.op_id: operation for operation in self.plan.operations
        }
        known = set(operations)
        unknown = self.selection - known
        if unknown:
            raise ValueError(f"selection contains unknown operation ids: {sorted(unknown)!r}")
        if not isinstance(self.user_deselected, frozenset):
            raise TypeError("user_deselected must be a frozenset")
        unknown_user_deselected = self.user_deselected - known
        if unknown_user_deselected:
            raise ValueError(
                "user deselection contains unknown operation ids: "
                f"{sorted(unknown_user_deselected)!r}"
            )
        selected_user_deselected = self.user_deselected & self.selection
        if selected_user_deselected:
            raise ValueError(
                "user-deselected operation ids cannot remain selected: "
                f"{sorted(selected_user_deselected)!r}"
            )
        invalid_status = self.status.keys() - self.selection
        if invalid_status:
            raise ValueError(
                f"status contains unselected operation ids: {sorted(invalid_status)!r}"
            )
        invalid_evidence = self.published_evidence.keys() - self.selection
        if invalid_evidence:
            raise ValueError(
                "published evidence contains unselected operation ids: "
                f"{sorted(invalid_evidence)!r}"
            )
        if not isinstance(self.recording_reasons, dict):
            raise TypeError("execution recording reasons must be a dict")
        invalid_recording = self.recording_reasons.keys() - self.selection
        if invalid_recording:
            raise ValueError(
                "recording degradation contains unselected operation ids: "
                f"{sorted(invalid_recording)!r}"
            )
        for op_id, reason in self.recording_reasons.items():
            validate_item_recording_outcome(self.status.get(op_id), reason)
        if not isinstance(self.recording_issues, tuple):
            raise TypeError("task recording issues must be a tuple")
        if any(
            not isinstance(issue, TaskRecordingIssue)
            for issue in self.recording_issues
        ):
            raise TypeError(
                "task recording issues must contain TaskRecordingIssue values"
            )
        issue_reasons = tuple(issue.reason for issue in self.recording_issues)
        if len(issue_reasons) != len(set(issue_reasons)):
            raise ValueError("task recording issue reasons must be unique")
        require_safe_int(
            self.omitted_detail_count,
            "execution omitted_detail_count",
        )
        byte_kinds = {
            OperationKind.COPY,
            OperationKind.UPDATE,
            OperationKind.MOVE_UPDATE,
        }
        self._selected_bytes_bound = 0
        for operation in operations.values():
            if operation.op_id in self.selection and operation.kind in byte_kinds:
                self._selected_bytes_bound = checked_add_signed_64(
                    self._selected_bytes_bound,
                    operation.content_bytes,
                    "selected execution bytes",
                )
        require_signed_64(
            self.bytes_done_high_water,
            "execution byte high-water",
        )
        if self.bytes_done_high_water > self._selected_bytes_bound:
            raise ValueError("execution byte high-water exceeds selected content")
        recorded_location_id: str | None = None
        for op_id, evidence in self.published_evidence.items():
            _validate_published_evidence_shape(evidence)
            operation = operations[op_id]
            if operation.kind not in byte_kinds:
                raise ValueError(
                    "published evidence belongs to a non-byte-producing operation"
                )
            if self.status.get(op_id) is not Outcome.SUCCEEDED:
                raise ValueError(
                    "published evidence requires a successful operation status"
                )
            if evidence.attestation.content.size != operation.content_bytes:
                raise ValueError(
                    "published evidence size does not match reviewed content bytes"
                )
            identity = evidence.recorded_identity
            if identity is None:
                if (
                    self.recording_reasons.get(op_id)
                    is not ItemRecordingReason.RECORD_WRITE_FAILED
                ):
                    raise ValueError(
                        "identityless published evidence requires that operation's "
                        "record-write-failed reason"
                )
                continue
            if (
                self.recording_reasons.get(op_id)
                is ItemRecordingReason.RECORD_WRITE_FAILED
            ):
                raise ValueError(
                    "record-write-failed evidence cannot carry a recorded identity"
                )
            if identity.scope_token != str(self.run_id):
                raise ValueError(
                    "recorded copy scope token does not match the execution run"
                )
            expected_path_key = normalize_relative_path(
                operation.target_rel_path
            )
            if identity.rel_path_key != expected_path_key:
                raise ValueError(
                    "recorded copy relative path key does not match its operation"
                )
            if recorded_location_id is None:
                recorded_location_id = identity.location_id
            elif identity.location_id != recorded_location_id:
                raise ValueError(
                    "recorded copy identities do not share one target location"
                )

    @property
    def recording(self) -> RecordingStatus:
        """Aggregate recording truth derived from item and task attribution."""

        return (
            RecordingStatus.DEGRADED
            if self.recording_reasons or self.recording_issues
            else RecordingStatus.OK
        )

    def note_item_recording_failure(
        self,
        op_id: OpId,
        reason: ItemRecordingReason,
    ) -> None:
        """Retain one settled operation's recording failure."""

        if op_id not in self.selection:
            raise ValueError("recording degradation belongs to an unselected operation")
        validate_item_recording_outcome(self.status.get(op_id), reason)
        evidence = self.published_evidence.get(op_id)
        if (
            reason is ItemRecordingReason.RECORD_WRITE_FAILED
            and evidence is not None
            and evidence.recorded_identity is not None
        ):
            raise ValueError(
                "record-write-failed evidence cannot carry a recorded identity"
            )
        if op_id in self.recording_reasons:
            raise ValueError("operation recording degradation is already settled")
        self.recording_reasons[op_id] = reason

    def note_task_recording_issue(
        self,
        reason: TaskRecordingIssueReason,
        detail: str | None = None,
    ) -> None:
        """Retain the first observation of one task-wide issue reason."""

        if not isinstance(reason, TaskRecordingIssueReason):
            raise TypeError("task recording issue reason has the wrong type")
        if any(issue.reason is reason for issue in self.recording_issues):
            return
        bounded_detail = bounded_recording_detail(detail)
        if detail is not None and bounded_detail is None:
            self.omitted_detail_count = require_safe_int(
                self.omitted_detail_count + 1,
                "execution omitted_detail_count",
            )
        issue = TaskRecordingIssue(reason, bounded_detail)
        self.recording_issues = (*self.recording_issues, issue)

    def note_bytes_done(self, bytes_done: int) -> None:
        require_signed_64(bytes_done, "execution byte progress")
        if bytes_done < self.bytes_done_high_water:
            raise ValueError("execution byte progress cannot regress")
        if bytes_done > self._selected_bytes_bound:
            raise ValueError("execution byte progress exceeds selected content")
        self.bytes_done_high_water = bytes_done

    def remaining(self) -> tuple[PlanOperation, ...]:
        """Return selected operations without a final status, in plan order."""

        return _remaining_operations(self.plan, self.selection, self.status)


def validate_execution_set(value: object) -> None:
    """Revalidate the exact mutable execution continuation in place."""

    if type(value) is not ExecutionSet:
        raise TypeError("execution continuation must be an exact ExecutionSet")
    if type(value.plan) is not Plan or type(value.plan.operations) is not tuple:
        raise TypeError("execution continuation plan has the wrong shape")
    if any(type(operation) is not PlanOperation for operation in value.plan.operations):
        raise TypeError("execution plan must contain exact PlanOperation values")
    if type(value.plan.fingerprint) is not str:
        raise TypeError("execution plan fingerprint must be exact text")
    if type(value.selection) is not frozenset:
        raise TypeError("execution selection must be an exact frozenset")
    if type(value.user_deselected) is not frozenset:
        raise TypeError("execution user deselection must be an exact frozenset")
    if type(value.run_id) is not str:
        raise TypeError("execution run id must be exact text")
    if value.commitment is not None and type(value.commitment) is not Commitment:
        raise TypeError("execution commitment must have the exact public shape")
    if type(value.status) is not dict:
        raise TypeError("execution status must be an exact dict")
    if any(type(outcome) is not Outcome for outcome in value.status.values()):
        raise TypeError("execution status values have the wrong type")
    if type(value.published_evidence) is not dict:
        raise TypeError("execution published evidence must be an exact dict")
    if any(
        type(evidence) is not PublishedCopyEvidence
        for evidence in value.published_evidence.values()
    ):
        raise TypeError("execution published evidence values have the wrong type")
    if type(value.recording_reasons) is not dict:
        raise TypeError("execution recording reasons must be an exact dict")
    if any(
        type(reason) is not ItemRecordingReason
        for reason in value.recording_reasons.values()
    ):
        raise TypeError("execution recording reasons have the wrong type")
    if type(value.recording_issues) is not tuple:
        raise TypeError("execution recording issues must be an exact tuple")
    if any(type(issue) is not TaskRecordingIssue for issue in value.recording_issues):
        raise TypeError("execution recording issues have the wrong type")
    for population in (
        value.selection,
        value.user_deselected,
        value.status,
        value.published_evidence,
        value.recording_reasons,
    ):
        if any(
            type(op_id) is not str or _FIXED_ID.fullmatch(op_id) is None
            for op_id in population
        ):
            raise TypeError("execution operation identities must be exact ids")
    ExecutionSet.__post_init__(value)


@dataclass(frozen=True, slots=True)
class ExecutionOperationFact:
    """Immutable operation fields needed to bind reliable executor outcomes."""

    kind: OperationKind
    target_rel_path: str
    content_bytes: int

    def __post_init__(self) -> None:
        if type(self.kind) is not OperationKind:
            raise TypeError("execution operation fact kind has the wrong type")
        if type(self.target_rel_path) is not str:
            raise TypeError("execution operation fact path must be text")
        normalize_relative_path(self.target_rel_path)
        require_signed_64(self.content_bytes, "execution operation fact bytes")


@dataclass(frozen=True, slots=True)
class ExecutionSettlementFact:
    """One settlement that existed before an executor invocation."""

    outcome: Outcome
    recording_reason: ItemRecordingReason | None
    evidence: tuple[object, ...] | None

    def __post_init__(self) -> None:
        if type(self.outcome) is not Outcome:
            raise TypeError("execution settlement outcome has the wrong type")
        if (
            self.recording_reason is not None
            and type(self.recording_reason) is not ItemRecordingReason
        ):
            raise TypeError("execution settlement recording reason has the wrong type")
        if self.evidence is not None and type(self.evidence) is not tuple:
            raise TypeError("execution settlement evidence must be an exact tuple")


@dataclass(frozen=True, slots=True)
class ExecutionSetAuthority:
    """Closed pre-call facts for one mutable executor continuation."""

    plan_fingerprint: str
    operations: Mapping[str, ExecutionOperationFact]
    run_id: str
    commitment: tuple[str, bytes, str] | None
    user_deselected: frozenset[str]
    settlements: Mapping[str, ExecutionSettlementFact]
    recording_issues: tuple[TaskRecordingIssue, ...]
    omitted_detail_count: int
    bytes_done_high_water: int


def _operation_fact(value: object) -> ExecutionOperationFact:
    if type(value) is not PlanOperation:
        raise TypeError("execution plan must contain exact PlanOperation values")
    return ExecutionOperationFact(
        value.kind,
        value.target_rel_path,
        value.content_bytes,
    )


def _commitment_fact(value: object | None) -> tuple[str, bytes, str] | None:
    if value is None:
        return None
    if type(value) is not Commitment:
        raise TypeError("execution commitment must have the exact public shape")
    selection = value.selection_digest
    committed_at = value.committed_at
    if type(selection) is not bytes:
        raise TypeError("execution commitment digest must be exact bytes")
    if type(committed_at) is not datetime:
        raise TypeError("execution commitment time must be an exact datetime")
    Commitment(value.plan_fingerprint, selection, committed_at)
    return str(value.plan_fingerprint), bytes(selection), committed_at.isoformat()


def _published_evidence_fact(value: object) -> tuple[object, ...]:
    if type(value) is not PublishedCopyEvidence:
        raise TypeError("published evidence must have the exact public shape")
    PublishedCopyEvidence.__post_init__(value)
    Attestation.__post_init__(value.attestation)
    attestation = attestation_fact(value.attestation)
    recorded = value.recorded_identity
    if recorded is not None and type(recorded) is not RecordedCopyIdentity:
        raise TypeError("recorded copy identity has the wrong type")
    if recorded is not None and any(
        type(field_value) is not str
        for field_value in (
            recorded.row_id,
            recorded.location_id,
            recorded.scope_token,
            recorded.rel_path_key,
        )
    ):
        raise TypeError("recorded copy identity fields must be exact text")
    recorded_snapshot = (
        None
        if recorded is None
        else RecordedCopyIdentity(
            recorded.row_id,
            recorded.location_id,
            recorded.scope_token,
            recorded.rel_path_key,
        )
    )
    return attestation, recorded_snapshot


def _recording_issue_snapshot(value: object) -> TaskRecordingIssue:
    if type(value) is not TaskRecordingIssue:
        raise TypeError("task recording issue must have the exact public shape")
    if type(value.reason) is not TaskRecordingIssueReason:
        raise TypeError("task recording issue reason has the wrong type")
    detail = value.detail
    if detail is not None and type(detail) is not str:
        raise TypeError("task recording issue detail must be exact text")
    return TaskRecordingIssue(value.reason, detail)


def snapshot_execution_set_authority(value: object) -> ExecutionSetAuthority:
    """Capture immutable pre-call facts while leaving mutable deltas explicit."""

    validate_execution_set(value)
    assert type(value) is ExecutionSet
    plan = value.plan
    computed_fingerprint = str(plan_fingerprint(plan))
    if str(plan.fingerprint) != computed_fingerprint:
        raise ValueError("execution continuation plan fingerprint is invalid")

    selection = frozenset(str(op_id) for op_id in value.selection)
    operations = MappingProxyType(
        {
            str(operation.op_id): _operation_fact(operation)
            for operation in plan.operations
            if str(operation.op_id) in selection
        }
    )
    user_deselected = frozenset(str(op_id) for op_id in value.user_deselected)
    settlements = MappingProxyType(
        {
            str(op_id): ExecutionSettlementFact(
                outcome,
                value.recording_reasons.get(op_id),
                (
                    _published_evidence_fact(value.published_evidence[op_id])
                    if op_id in value.published_evidence
                    else None
                ),
            )
            for op_id, outcome in value.status.items()
        }
    )
    issues = tuple(_recording_issue_snapshot(issue) for issue in value.recording_issues)
    return ExecutionSetAuthority(
        computed_fingerprint,
        operations,
        str(value.run_id),
        _commitment_fact(value.commitment),
        user_deselected,
        settlements,
        issues,
        value.omitted_detail_count,
        value.bytes_done_high_water,
    )


def revalidate_execution_set_authority(
    value: object,
    authority: object,
    *,
    allow_progress: bool,
) -> None:
    """Require fixed facts and prior settlements to survive a collaborator call."""

    if type(authority) is not ExecutionSetAuthority:
        raise TypeError("execution authority has the wrong type")
    if type(allow_progress) is not bool:
        raise TypeError("execution authority progress policy must be a boolean")
    validate_execution_set(value)
    assert type(value) is ExecutionSet
    plan = value.plan
    if str(plan_fingerprint(plan)) != authority.plan_fingerprint:
        raise ValueError("executor changed the reviewed plan")
    if str(plan.fingerprint) != authority.plan_fingerprint:
        raise ValueError("executor changed the declared plan fingerprint")
    if len(value.selection) != len(authority.operations) or any(
        str(op_id) not in authority.operations for op_id in value.selection
    ):
        raise ValueError("executor changed the reviewed selection")
    if str(value.run_id) != authority.run_id:
        raise ValueError("executor changed the execution run identity")
    if _commitment_fact(value.commitment) != authority.commitment:
        raise ValueError("executor changed the execution commitment")
    if (
        frozenset(str(op_id) for op_id in value.user_deselected)
        != authority.user_deselected
    ):
        raise ValueError("executor changed reviewed user deselection")

    op_id_by_text = {str(op_id): op_id for op_id in value.selection}
    for item_id, settlement in authority.settlements.items():
        op_id = op_id_by_text.get(item_id)
        if op_id is None or value.status.get(op_id) is not settlement.outcome:
            raise ValueError("executor changed an existing settlement")
        if value.recording_reasons.get(op_id) is not settlement.recording_reason:
            raise ValueError("executor changed existing settlement recording")
        evidence = (
            _published_evidence_fact(value.published_evidence[op_id])
            if op_id in value.published_evidence
            else None
        )
        if evidence != settlement.evidence:
            raise ValueError("executor changed existing publication evidence")
    current_issues = tuple(
        _recording_issue_snapshot(issue) for issue in value.recording_issues
    )
    if not allow_progress:
        if len(value.status) != len(authority.settlements):
            raise ValueError("execution settlement changed before execution")
        if current_issues != authority.recording_issues:
            raise ValueError("execution recording issues changed before execution")
        if value.omitted_detail_count != authority.omitted_detail_count:
            raise ValueError("execution omission witness changed before execution")
        if value.bytes_done_high_water != authority.bytes_done_high_water:
            raise ValueError("execution byte progress changed before execution")
        return
    if len(current_issues) < len(authority.recording_issues) or any(
        issue != expected
        for issue, expected in zip(current_issues, authority.recording_issues)
    ):
        raise ValueError("executor changed existing task recording issues")
    if value.omitted_detail_count < authority.omitted_detail_count:
        raise ValueError("executor reduced the omission witness")
    if value.bytes_done_high_water < authority.bytes_done_high_water:
        raise ValueError("executor regressed execution byte progress")


class ExecutionReason(StrEnum):
    """Typed executor reasons; detail text is presentation-only."""

    NOOP = "noop"
    ALREADY_EXISTS = "already-exists"
    BLOCKED = "blocked"
    DEPENDENCY_FAILED = "dependency-failed"
    SOURCE_DRIFT = "source-drift"
    TARGET_DRIFT = "target-drift"
    DESTINATION_OCCUPIED = "destination-occupied"
    WRONG_TYPE = "wrong-type"
    SOURCE_MISSING = "source-missing"
    TARGET_MISSING = "target-missing"
    TRASH_COLLISION = "trash-collision"
    UNSAFE_PATH = "unsafe-path"
    SHARING_VIOLATION = "sharing-violation"
    ACL_COPY_FAILED = "acl-copy-failed"
    CLEANUP_FAILED = "cleanup-failed"
    PUBLISHED_SIZE_MISMATCH = "published-size-mismatch"
    IO_ERROR = "io-error"
    POLICY_STOP = "policy-stop"
    CANCELED = "canceled"
    CANCELED_AFTER_PUBLISH = "canceled-after-publish"
    CANCELED_AFTER_MUTATION = "canceled-after-mutation"
    RECORDER_FAILED = "recorder-failed"


@dataclass(frozen=True, slots=True)
class Continue:
    """Continue with later independent operations."""


@dataclass(frozen=True, slots=True)
class Stop:
    """Stop admission of later operations after the current failure."""


@dataclass(frozen=True, slots=True)
class Retry:
    """Retry the guarded operation after a bounded delay."""

    after: float

    def __post_init__(self) -> None:
        if self.after < 0:
            raise ValueError("retry delay cannot be negative")


FailureDecision: TypeAlias = Continue | Stop | Retry


class FailurePolicy(Protocol):
    def on_item_failed(
        self, operation: PlanOperation, error: Exception, attempt: int
    ) -> FailureDecision: ...


@dataclass(frozen=True, slots=True)
class CopyDigest:
    digest: bytes
    size: int

    def __post_init__(self) -> None:
        if not isinstance(self.digest, bytes):
            raise TypeError("copy digest must be bytes")
        if len(self.digest) != 16:
            raise ValueError("copy digest must be XXH3-128")
        require_signed_64(self.size, "copied size")


class CopyBackend(Protocol):
    """Writes bytes only; the executor retains every guard and publish step."""

    def copy(
        self,
        source: BinaryIO,
        target: BinaryIO,
        *,
        chunk_size: int,
        checkpoint: Callable[[], None],
        on_chunk: Callable[[int], None],
    ) -> CopyDigest: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class Recorder(Protocol):
    """Typed ledger commands consumed by the M0 executor."""

    def flush(self) -> None: ...

    def record_copied(
        self, op: OpId, attestation: Attestation
    ) -> RecordedCopyIdentity: ...

    def record_updated(
        self, op: OpId, attestation: Attestation
    ) -> RecordedCopyIdentity: ...

    def record_moved(self, op: OpId, target: FileStat) -> None: ...

    def record_recased(self, op: OpId, target: FileStat) -> None: ...

    def record_move_updated(
        self, op: OpId, attestation: Attestation
    ) -> RecordedCopyIdentity: ...

    def record_mkdir(self, op: OpId, target: FileStat) -> None: ...

    def record_trashed(
        self, op: OpId, trash_relative_path: str, target: FileStat
    ) -> None: ...

    def record_deleted(self, op: OpId, prior: FileStat) -> None: ...

    def record_noop(
        self, op: OpId, source: FileStat, target: FileStat
    ) -> None: ...


class ExecutorFileSystem(Protocol):
    """Operation-matched filesystem primitives retained by the state machine."""

    def resolve(self, root: Path, relative_path: str, *, must_exist: bool) -> Path: ...

    def revalidate_root(
        self,
        root: Path,
        *,
        trusted_anchor: Path | None = None,
        expected_volume: VolumeId | None = None,
    ) -> None: ...

    def stat(self, root: Path, relative_path: str) -> FileStat | None: ...

    def stat_path(self, path: Path) -> FileStat | None: ...

    def owned_temp(self, target: Path, run_id: RunId, op_id: OpId) -> Path: ...

    def remove_owned_temp(self, path: Path) -> None: ...

    def remove_orphaned_temps(
        self,
        target_root: Path,
        parent_paths: frozenset[str],
        current_run_id: RunId,
    ) -> None: ...

    def open_source(self, path: Path) -> BinaryIO: ...

    def create_temp(
        self, path: Path, *, allocation_size: int | None
    ) -> BinaryIO: ...

    def flush_file(self, stream: BinaryIO) -> None: ...

    def flush_path(self, path: Path) -> None: ...

    def apply_metadata(
        self,
        path: Path,
        stat: FileStat,
        *,
        preserve_created: bool,
        apply_readonly: bool,
    ) -> None: ...

    def copy_security(self, source: Path, target: Path) -> None: ...

    def finalize_temp(
        self,
        path: Path,
        intended: FileStat,
        *,
        preserve_created: bool,
        acl_source: Path | None,
    ) -> FileStat: ...

    def ensure_published_metadata(
        self,
        path: Path,
        finalized_temp: FileStat,
        intended: FileStat,
        *,
        preserve_created: bool,
        apply_readonly: bool,
    ) -> FileStat: ...

    def publish_new(self, temp: Path, target: Path) -> None: ...

    def replace(self, temp: Path, target: Path) -> None: ...

    def hardlink(self, source: Path, target: Path) -> None: ...

    def copy_backup(
        self,
        source: Path,
        temp: Path,
        target: Path,
        source_expected: FileStat,
        checkpoint: Callable[[], None],
        validate_destination: Callable[[], None],
    ) -> None: ...

    def clear_readonly(self, path: Path) -> None: ...

    def rename_new(self, source: Path, target: Path) -> None: ...

    def mkdir_new(self, path: Path) -> None: ...

    def remove_file(self, path: Path) -> None: ...

    def remove_directory(self, path: Path) -> None: ...

    def trash_destination(
        self, target_root: Path, run_id: RunId, relative_path: str
    ) -> Path: ...

    def revalidate_trash_destination(
        self,
        target_root: Path,
        run_id: RunId,
        relative_path: str,
        destination: Path,
    ) -> None: ...

    def flush_directory(self, path: Path) -> bool: ...
