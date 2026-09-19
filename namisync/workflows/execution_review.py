"""Workflow-owned classification of durable execution evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from namisync.core.evidence import ContentEvidence, Outcome, Provenance
from namisync.core.events import ItemOutcome
from namisync.core.execution import ExecutionReason
from namisync.core.integrity import IntegrityOutcome
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import OperationKind, Plan
from namisync.core.session import OperationResult
from namisync.db.repositories import (
    EXECUTION_EVIDENCE_SUBJECT_LIMIT,
    ExecutionEvidenceKey,
    ExecutionEvidenceReceiptFact,
    ExecutionEvidenceSnapshot,
    ExecutionEvidenceSubjectLimitError,
    InventorySnapshot,
    LedgerRepository,
)

from .models import (
    ExecutionEvidenceResult,
    ExecutionEvidenceState,
    ExecutionEvidenceSubject,
    ExecutionEvidenceWindow,
    RetainedExecutionBinding,
    RetainedExecutionItemWindow,
    RetainedExecutionSummary,
    RetainedIntegrityItemWindow,
)


_COPY_LIKE = {
    OperationKind.COPY,
    OperationKind.UPDATE,
    OperationKind.MOVE_UPDATE,
}

RETAINED_EXECUTION_READ_LIMIT = 256


class RetainedExecutionReadLimitError(ValueError):
    """A retained execution item request exceeded its hard population bound."""


@dataclass(slots=True)
class RetainedExecutionReview:
    binding: RetainedExecutionBinding
    result: OperationResult
    summary: RetainedExecutionSummary
    operation_items: dict[str, ItemOutcome]
    integrity_items: dict[str, IntegrityOutcome]
    target_owner_unique: dict[str, bool]


def build_retained_execution_review(
    binding: RetainedExecutionBinding,
    result: OperationResult,
    plan: Plan,
    selection: frozenset[str],
) -> RetainedExecutionReview:
    """Validate and index one exact task-bound terminal execution result."""

    if type(binding) is not RetainedExecutionBinding:
        raise TypeError("retained execution binding has the wrong type")
    if type(result) is not OperationResult:
        raise TypeError("retained execution result must be an exact OperationResult")
    if type(plan) is not Plan:
        raise TypeError("retained execution plan must be an exact Plan")
    if type(selection) is not frozenset:
        raise TypeError("retained execution selection must be an exact frozenset")
    members = {str(operation.op_id): operation for operation in plan.operations}
    selected = {str(operation_id) for operation_id in selection}
    if not selected <= members.keys():
        raise ValueError("retained execution selection is outside its Plan")
    operations: dict[str, ItemOutcome] = {}
    integrity: dict[str, IntegrityOutcome] = {}
    for item in result.items:
        item_id = item.item_id
        if item_id not in members:
            raise ValueError("retained execution item is outside its Plan")
        if type(item) is ItemOutcome:
            operation = members[item_id]
            if item.kind is not operation.kind or item.path != operation.target_rel_path:
                raise ValueError("retained operation item changed its Plan identity")
            if item_id in operations:
                raise ValueError("retained execution operation identity is duplicated")
            operations[item_id] = item
        elif type(item) is IntegrityOutcome:
            if item_id not in selected:
                raise ValueError("retained integrity item is outside the selection")
            operation = members[item_id]
            if item.phase != "verify" or item.path != operation.target_rel_path:
                raise ValueError("retained integrity item changed its Plan identity")
            if item_id in integrity:
                raise ValueError("retained integrity identity is duplicated")
            integrity[item_id] = item
        else:
            raise TypeError("retained execution item type is unsupported")
    failed = tuple(
        item for item in operations.values() if item.outcome is Outcome.FAILED
    )
    return RetainedExecutionReview(
        binding,
        result,
        RetainedExecutionSummary.from_result(
            binding,
            result,
            failed_operation_count=len(failed),
            disk_capacity_failure_count=sum(
                item.reason == ExecutionReason.DISK_CAPACITY.value for item in failed
            ),
            trash_location=str(
                Path(plan.target_root.path) / ".synctrash" / binding.run_id
            ),
        ),
        operations,
        integrity,
        _target_ownership(plan, selected),
    )


def read_retained_operation_items(
    review: RetainedExecutionReview,
    operation_ids: tuple[str, ...],
) -> RetainedExecutionItemWindow:
    _admit_retained_ids(operation_ids)
    return RetainedExecutionItemWindow(
        review.binding.task_id,
        review.binding.run_id,
        tuple(
            item
            for operation_id in operation_ids
            if (item := review.operation_items.get(operation_id)) is not None
        ),
    )


def read_retained_integrity_items(
    review: RetainedExecutionReview,
    operation_ids: tuple[str, ...],
) -> RetainedIntegrityItemWindow:
    _admit_retained_ids(operation_ids)
    return RetainedIntegrityItemWindow(
        review.binding.task_id,
        review.binding.run_id,
        tuple(
            item
            for operation_id in operation_ids
            if (item := review.integrity_items.get(operation_id)) is not None
        ),
    )


def retained_evidence_subjects(
    review: RetainedExecutionReview,
    operation_ids: tuple[str, ...],
) -> tuple[ExecutionEvidenceSubject, ...]:
    window = read_retained_operation_items(review, operation_ids)
    return tuple(
        ExecutionEvidenceSubject(
            item,
            review.target_owner_unique.get(item.item_id, False),
        )
        for item in window.items
    )


def _admit_retained_ids(operation_ids: tuple[str, ...]) -> None:
    if type(operation_ids) is not tuple:
        raise TypeError("retained execution operation ids must be an exact tuple")
    if len(operation_ids) > RETAINED_EXECUTION_READ_LIMIT:
        raise RetainedExecutionReadLimitError(
            "retained execution read exceeds 256 operation identities"
        )
    if any(type(operation_id) is not str or not operation_id for operation_id in operation_ids):
        raise ValueError("retained execution operation identity is invalid")


def _target_ownership(plan: Plan, selected: set[str]) -> dict[str, bool]:
    touches: dict[str, set[str]] = {}
    for operation in plan.operations:
        operation_id = str(operation.op_id)
        if operation_id not in selected:
            continue
        keys = {normalize_relative_path(operation.target_rel_path)}
        if (
            operation.kind in {OperationKind.MOVE, OperationKind.MOVE_UPDATE}
            and operation.prior_target_rel_path is not None
        ):
            keys.add(normalize_relative_path(operation.prior_target_rel_path))
        for key in keys:
            touches.setdefault(key, set()).add(operation_id)
    return {
        operation_id: len(
            touches[normalize_relative_path(operation.target_rel_path)]
        ) == 1
        for operation_id, operation in (
            (str(operation.op_id), operation) for operation in plan.operations
        )
        if operation_id in selected
    }


def read_execution_evidence(
    repository: LedgerRepository,
    run_token: str,
    subjects: tuple[ExecutionEvidenceSubject, ...],
) -> ExecutionEvidenceWindow:
    """Classify one bounded window without inferring complete-run ownership."""

    admit_execution_evidence_subjects(run_token, subjects)
    eligible: list[tuple[ExecutionEvidenceSubject, str]] = []
    for subject in subjects:
        if subject.item.kind in _COPY_LIKE and subject.item.outcome is Outcome.SUCCEEDED:
            eligible.append((subject, normalize_relative_path(subject.item.path)))

    snapshot = repository.read_execution_evidence(
        run_token,
        tuple(
            ExecutionEvidenceKey(subject.item.item_id, target_key)
            for subject, target_key in eligible
        ),
    )
    receipts = {receipt.operation_token: receipt for receipt in snapshot.receipts}
    inventory = {row.rel_path_key: row for row in snapshot.inventory}
    results: list[ExecutionEvidenceResult] = []
    for subject in subjects:
        item = subject.item
        if item.kind not in _COPY_LIKE or item.outcome is not Outcome.SUCCEEDED:
            results.append(_result(item.item_id, ExecutionEvidenceState.NOT_APPLICABLE))
            continue
        target_key = normalize_relative_path(item.path)
        receipt = receipts.get(item.item_id)
        if not _is_matching_receipt(receipt, item.kind, target_key):
            results.append(_result(item.item_id, ExecutionEvidenceState.UNRECORDED))
            continue
        assert receipt is not None
        state, content = _coherent_state(
            snapshot, run_token, subject, inventory.get(target_key)
        )
        results.append(ExecutionEvidenceResult(item.item_id, state, content))
    return ExecutionEvidenceWindow(run_token, tuple(results))


def admit_execution_evidence_subjects(
    run_token: str,
    subjects: tuple[ExecutionEvidenceSubject, ...],
) -> None:
    """Enforce the raw public wall before normalization or reader acquisition."""

    if type(run_token) is not str or not run_token:
        raise ValueError("execution evidence run token is required")
    if type(subjects) is not tuple:
        raise TypeError("execution evidence subjects must be an exact tuple")
    if len(subjects) > EXECUTION_EVIDENCE_SUBJECT_LIMIT:
        raise ExecutionEvidenceSubjectLimitError()
    if any(type(subject) is not ExecutionEvidenceSubject for subject in subjects):
        raise TypeError("execution evidence subject has the wrong type")


def _coherent_state(
    snapshot: ExecutionEvidenceSnapshot,
    expected_run_token: str,
    subject: ExecutionEvidenceSubject,
    row: InventorySnapshot | None,
) -> tuple[ExecutionEvidenceState, ContentEvidence | None]:
    run = snapshot.run
    if (
        run is None
        or run.run_token != expected_run_token
        or run.activity_kind != "sync"
        or run.target_location_id is None
        or not subject.target_owner_unique
        or row is None
        or row.location_id != run.target_location_id
        or row.presence.value != "present"
        or row.scope_token != run.run_token
        or row.invalidation is not None
        or row.observed is None
        or row.attestation is None
        or row.observed != row.attestation.subject
        or row.attestation.content.algorithm != "xxh3_128"
    ):
        return ExecutionEvidenceState.SUPERSEDED, None
    content = row.attestation.content
    if (
        content.provenance is Provenance.COPY_ATTESTED
        and row.last_verified_at is None
    ):
        return ExecutionEvidenceState.RECORDED_COPY, content
    if (
        content.provenance in {Provenance.READBACK_ATTESTED, Provenance.VERIFY_ATTESTED}
        and row.last_verified_at is not None
    ):
        return ExecutionEvidenceState.ALREADY_VERIFIED, content
    return ExecutionEvidenceState.SUPERSEDED, None


def _is_matching_receipt(
    receipt: ExecutionEvidenceReceiptFact | None,
    kind: OperationKind,
    target_key: str,
) -> bool:
    return (
        receipt is not None
        and receipt.kind == kind.value
        and receipt.target_path_key == target_key
        and receipt.outcome == Outcome.SUCCEEDED.value
    )


def _result(
    operation_id: str, state: ExecutionEvidenceState
) -> ExecutionEvidenceResult:
    return ExecutionEvidenceResult(operation_id, state)
