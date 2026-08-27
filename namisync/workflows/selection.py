"""Deterministic safe-subset selection for reviewed sync plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

from namisync.core.evidence import Outcome
from namisync.core.planning import (
    BlockedReason,
    OpId,
    OperationKind,
    Plan,
    quarantined_operation_ids,
)


class ExclusionReason(StrEnum):
    """Why an otherwise nonblocked plan operation was not selected."""

    BLOCKED_CORRESPONDENCE = "blocked-correspondence"
    BLOCKED_DEPENDENCY = "blocked-dependency"
    INCOMPLETE_SCAN = "incomplete-scan"
    USER_DESELECTED = "user-deselected"


SELECTION_EXCLUSION_REASONS = frozenset(
    reason.value for reason in (*ExclusionReason, *BlockedReason)
)


@dataclass(frozen=True, slots=True)
class OperationExclusion:
    op_id: OpId
    outcome: Outcome
    reason: str
    detail: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionSelection:
    selection: frozenset[OpId]
    exclusions: tuple[OperationExclusion, ...]


_INCOMPLETE_SCAN_UNSAFE = {
    OperationKind.MOVE,
    OperationKind.MOVE_UPDATE,
    OperationKind.TRASH,
    OperationKind.DELETE,
}


def derive_execution_selection(
    plan: Plan,
    *,
    user_deselected: frozenset[OpId] = frozenset(),
) -> ExecutionSelection:
    """Derive the safe effective selection from plan and direct user intent."""

    safety_exclusions = _derive_safety_exclusions(plan)
    _validate_user_deselected(plan, user_deselected, safety_exclusions)
    exclusions = dict(safety_exclusions)
    for operation in plan.operations:
        if operation.op_id not in user_deselected:
            continue
        exclusions[operation.op_id] = OperationExclusion(
            operation.op_id,
            Outcome.SKIPPED,
            ExclusionReason.USER_DESELECTED.value,
        )

    _close_exclusions_over_dependencies(plan, exclusions)
    return ExecutionSelection(
        frozenset(
            operation.op_id
            for operation in plan.operations
            if operation.op_id not in exclusions
        ),
        tuple(
            exclusions[operation.op_id]
            for operation in plan.operations
            if operation.op_id in exclusions
        ),
    )


def apply_selection_mutation(
    plan: Plan,
    user_deselected: frozenset[OpId],
    *,
    deselect: frozenset[OpId] = frozenset(),
    reselect: frozenset[OpId] = frozenset(),
) -> frozenset[OpId]:
    """Apply one direct-user batch, closing reselection over dependencies."""

    safety_exclusions = _derive_safety_exclusions(plan)
    _validate_user_deselected(plan, user_deselected, safety_exclusions)
    if deselect & reselect:
        raise ValueError("one selection mutation cannot both deselect and reselect an id")
    _validate_mutation_ids(plan, deselect | reselect, safety_exclusions)

    updated = set(user_deselected)
    updated.update(deselect)
    pending = list(reselect)
    visited: set[OpId] = set()
    operations = {operation.op_id: operation for operation in plan.operations}
    while pending:
        op_id = pending.pop()
        if op_id in visited:
            continue
        visited.add(op_id)
        updated.discard(op_id)
        pending.extend(operations[op_id].dependencies)
    return frozenset(updated)


def _derive_safety_exclusions(
    plan: Plan,
) -> dict[OpId, OperationExclusion]:
    exclusions: dict[OpId, OperationExclusion] = {}
    for operation in plan.operations:
        if not operation.blocked:
            continue
        exclusions[operation.op_id] = OperationExclusion(
            operation.op_id,
            Outcome.BLOCKED,
            operation.blocked_reason.value,
        )

    quarantined = quarantined_operation_ids(plan.operations)
    for operation in plan.operations:
        if operation.op_id in quarantined:
            exclusions[operation.op_id] = OperationExclusion(
                operation.op_id,
                Outcome.DEFERRED,
                ExclusionReason.BLOCKED_CORRESPONDENCE.value,
            )

    incomplete_sides = tuple(
        side
        for side, complete in (
            ("source", plan.source_complete),
            ("target", plan.target_complete),
        )
        if not complete
    )
    if incomplete_sides:
        for operation in plan.operations:
            if (
                operation.op_id not in exclusions
                and operation.kind in _INCOMPLETE_SCAN_UNSAFE
            ):
                exclusions[operation.op_id] = OperationExclusion(
                    operation.op_id,
                    Outcome.DEFERRED,
                    ExclusionReason.INCOMPLETE_SCAN.value,
                    {"incomplete_sides": incomplete_sides},
                )

    _close_exclusions_over_dependencies(plan, exclusions)
    return exclusions


def _close_exclusions_over_dependencies(
    plan: Plan,
    exclusions: dict[OpId, OperationExclusion],
) -> None:
    changed = True
    while changed:
        changed = False
        for operation in plan.operations:
            if operation.op_id in exclusions:
                continue
            excluded_dependencies = tuple(
                dependency
                for dependency in operation.dependencies
                if dependency in exclusions
            )
            if not excluded_dependencies:
                continue
            dependency_exclusions = tuple(
                exclusions[dependency] for dependency in excluded_dependencies
            )
            reason = (
                ExclusionReason.INCOMPLETE_SCAN
                if all(
                    item.reason == ExclusionReason.INCOMPLETE_SCAN
                    for item in dependency_exclusions
                )
                else ExclusionReason.BLOCKED_DEPENDENCY
            )
            exclusions[operation.op_id] = OperationExclusion(
                operation.op_id,
                Outcome.DEFERRED,
                reason.value,
                {
                    "excluded_dependencies": tuple(
                        str(dependency) for dependency in excluded_dependencies
                    )
                },
            )
            changed = True


def _validate_user_deselected(
    plan: Plan,
    user_deselected: frozenset[OpId],
    safety_exclusions: Mapping[OpId, OperationExclusion],
) -> None:
    if not isinstance(user_deselected, frozenset):
        raise TypeError("user_deselected must be a frozenset")
    known = {operation.op_id for operation in plan.operations}
    unknown = user_deselected - known
    if unknown:
        raise ValueError(
            f"user deselection contains unknown operation ids: {sorted(unknown)!r}"
        )
    unavailable = user_deselected & safety_exclusions.keys()
    if unavailable:
        raise ValueError(
            "user deselection contains safety-excluded operation ids: "
            f"{sorted(unavailable)!r}"
        )


def _validate_mutation_ids(
    plan: Plan,
    operation_ids: frozenset[OpId],
    safety_exclusions: Mapping[OpId, OperationExclusion],
) -> None:
    if not isinstance(operation_ids, frozenset):
        raise TypeError("selection mutation ids must be frozensets")
    known = {operation.op_id for operation in plan.operations}
    unknown = operation_ids - known
    if unknown:
        raise ValueError(
            f"selection mutation names an unknown operation: {sorted(unknown)!r}"
        )
    unavailable = operation_ids & safety_exclusions.keys()
    if unavailable:
        raise ValueError(
            "selection mutation names a safety-excluded operation: "
            f"{sorted(unavailable)!r}"
        )
