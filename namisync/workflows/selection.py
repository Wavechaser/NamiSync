"""Deterministic safe-subset selection for reviewed sync plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

from namisync.core.evidence import Outcome
from namisync.core.planning import (
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


def derive_execution_selection(plan: Plan) -> ExecutionSelection:
    """Select the safe independent subset and explain every forced exclusion."""

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
