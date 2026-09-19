"""Workflow-owned classification of durable execution evidence."""

from __future__ import annotations

from namisync.core.evidence import ContentEvidence, Outcome, Provenance
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import OperationKind
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
)


_COPY_LIKE = {
    OperationKind.COPY,
    OperationKind.UPDATE,
    OperationKind.MOVE_UPDATE,
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
