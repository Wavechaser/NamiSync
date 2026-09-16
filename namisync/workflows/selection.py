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
    calculate_required_bytes,
    quarantined_operation_ids,
    selection_digest,
)
from namisync.core.scalars import scalar_64_to_text


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
class DestructiveOperationCounts:
    update: int
    move_update: int
    trash: int
    delete: int

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 0
            for value in (self.update, self.move_update, self.trash, self.delete)
        ):
            raise ValueError("destructive operation counts must be nonnegative ints")

    @property
    def total(self) -> int:
        return self.update + self.move_update + self.trash + self.delete


_SELECTION_AUTHORITY = object()


@dataclass(frozen=True, slots=True, init=False)
class ExecutionSelection:
    selection: frozenset[OpId]
    selection_digest: bytes
    exclusions: tuple[OperationExclusion, ...]
    destructive_operation_counts: DestructiveOperationCounts
    irreversible_update_count: int
    required_bytes: str
    _plan: Plan = field(repr=False, compare=False)
    _user_deselected: frozenset[OpId] = field(repr=False, compare=False)

    def __init__(
        self,
        selection: frozenset[OpId],
        selection_digest: bytes,
        exclusions: tuple[OperationExclusion, ...],
        destructive_operation_counts: DestructiveOperationCounts,
        irreversible_update_count: int,
        required_bytes: str,
        *,
        _authority: object,
        _plan: Plan,
        _user_deselected: frozenset[OpId],
    ) -> None:
        if _authority is not _SELECTION_AUTHORITY:
            raise TypeError("execution selection is workflow-derived authority")
        object.__setattr__(self, "selection", selection)
        object.__setattr__(self, "selection_digest", selection_digest)
        object.__setattr__(self, "exclusions", exclusions)
        object.__setattr__(
            self, "destructive_operation_counts", destructive_operation_counts
        )
        object.__setattr__(self, "irreversible_update_count", irreversible_update_count)
        object.__setattr__(self, "required_bytes", required_bytes)
        object.__setattr__(self, "_plan", _plan)
        object.__setattr__(self, "_user_deselected", _user_deselected)

    @property
    def destructive_operation_count(self) -> int:
        return self.destructive_operation_counts.total

    @property
    def irreversible_operation_count(self) -> int:
        return (
            self.irreversible_update_count
            + self.destructive_operation_counts.delete
        )

    @property
    def requires_destructive_confirmation(self) -> bool:
        return self.destructive_operation_count > 0


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
    selected_operations = tuple(
        operation
        for operation in plan.operations
        if operation.op_id not in exclusions
    )
    selection = frozenset(operation.op_id for operation in selected_operations)
    update_count = 0
    move_update_count = 0
    trash_count = 0
    delete_count = 0
    for operation in selected_operations:
        if operation.kind is OperationKind.UPDATE:
            update_count += 1
        elif operation.kind is OperationKind.MOVE_UPDATE:
            move_update_count += 1
        elif operation.kind is OperationKind.TRASH:
            trash_count += 1
        elif operation.kind is OperationKind.DELETE:
            delete_count += 1
    return ExecutionSelection(
        selection,
        selection_digest(selection),
        tuple(
            exclusions[operation.op_id]
            for operation in plan.operations
            if operation.op_id in exclusions
        ),
        DestructiveOperationCounts(
            update_count,
            move_update_count,
            trash_count,
            delete_count,
        ),
        0 if plan.trash_on_update else update_count,
        scalar_64_to_text(
            calculate_required_bytes(
                selected_operations,
                target_profile=plan.target_profile,
                trash_on_update=plan.trash_on_update,
            ),
            "execution selection required_bytes",
        ),
        _authority=_SELECTION_AUTHORITY,
        _plan=plan,
        _user_deselected=user_deselected,
    )


def require_derived_execution_selection(
    value: object,
    *,
    plan: Plan,
    user_deselected: frozenset[OpId],
) -> ExecutionSelection:
    """Require selection authority for these exact immutable reviewed inputs."""

    if type(value) is not ExecutionSelection:
        raise TypeError("execution selection must be workflow-derived authority")
    if value._plan is not plan:
        raise ValueError("execution selection belongs to a different plan")
    if value._user_deselected is not user_deselected:
        raise ValueError("execution selection belongs to different user intent")
    return value


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

    quarantined = (
        quarantined_operation_ids(plan.operations)
        if exclusions
        else frozenset()
    )
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
