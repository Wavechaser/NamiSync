from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from namisync.core.events import ItemOutcome
from namisync.core.evidence import Outcome
from namisync.core.execution import Commitment, ExecutionSet, validated_run_id
from namisync.core.models import CapabilityProfile, Root
from namisync.core.planning import (
    Assignment,
    BlockedReason,
    DeletionPolicy,
    FilterSet,
    OpId,
    OperationKind,
    OperationReason,
    Plan,
    PlanFingerprint,
    PlanOperation,
    PreservationPolicy,
    plan_fingerprint,
    selection_digest,
)
from namisync.core.session import (
    Disposition,
    OperationResult,
    RunContext,
    SessionState,
)
from namisync.workflows.selection import (
    ExclusionReason,
    SELECTION_EXCLUSION_REASONS,
    apply_selection_mutation,
    derive_execution_selection,
)
from namisync.workflows.sync import run_execution
from namisync.workflows.views import operation_result_view


def _operation(
    index: int,
    kind: OperationKind,
    target: str,
    *,
    dependencies: tuple[OpId, ...] = (),
    blocked_reason: BlockedReason | None = None,
) -> PlanOperation:
    return PlanOperation(
        op_id=OpId(f"{index:032x}"),
        kind=kind,
        source_rel_path=None if kind is OperationKind.DELETE else target,
        target_rel_path=target,
        source_expected=None,
        target_expected=None,
        intended=None,
        dependencies=dependencies,
        reason=(
            OperationReason.DIRECTORY_CLEANUP
            if kind is OperationKind.DELETE
            else OperationReason.SOURCE_ONLY
        ),
        blocked_reason=blocked_reason,
    )


def _plan(operations: tuple[PlanOperation, ...]) -> Plan:
    profile = CapabilityProfile("NTFS", 100, True, False, 32767, True, True)
    placeholder = Plan(
        source_root=Root(r"C:\source", "source"),
        target_root=Root(r"D:\target", "target"),
        source_volume_id=None,
        target_volume_id=None,
        source_volume_evidence=None,
        target_volume_evidence=None,
        source_profile=profile,
        target_profile=profile,
        source_complete=True,
        target_complete=True,
        operations=operations,
        assignment=Assignment("identity", "1", ()),
        preservation=PreservationPolicy(),
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=True,
        policy_fingerprint="p" * 64,
        required_volumes=frozenset(),
        required_bytes=0,
        fingerprint=PlanFingerprint("0" * 64),
    )
    return replace(placeholder, fingerprint=plan_fingerprint(placeholder))


def _selection_plan() -> tuple[Plan, tuple[PlanOperation, ...]]:
    folder = _operation(1, OperationKind.MKDIR, "folder")
    child = _operation(
        2,
        OperationKind.COPY,
        r"folder\child.bin",
        dependencies=(folder.op_id,),
    )
    leaf_removal = _operation(3, OperationKind.TRASH, r"old\leaf.bin")
    folder_cleanup = _operation(
        4,
        OperationKind.DELETE,
        "old",
        dependencies=(leaf_removal.op_id,),
    )
    noop = _operation(5, OperationKind.NOOP, "same.bin")
    operations = (folder, child, leaf_removal, folder_cleanup, noop)
    return _plan(operations), operations


def test_br_g_12_user_deselection_cascades_and_reselection_closes_upward() -> None:
    plan, (folder, child, leaf_removal, cleanup, noop) = _selection_plan()

    user_deselected = apply_selection_mutation(
        plan,
        frozenset(),
        deselect=frozenset({folder.op_id, leaf_removal.op_id}),
    )
    deselected = derive_execution_selection(
        plan,
        user_deselected=user_deselected,
    )
    exclusions = {item.op_id: item for item in deselected.exclusions}

    assert user_deselected == frozenset({folder.op_id, leaf_removal.op_id})
    assert deselected.selection == frozenset({noop.op_id})
    assert exclusions[folder.op_id].outcome is Outcome.SKIPPED
    assert exclusions[folder.op_id].reason == ExclusionReason.USER_DESELECTED
    assert exclusions[leaf_removal.op_id].outcome is Outcome.SKIPPED
    assert exclusions[child.op_id].outcome is Outcome.DEFERRED
    assert exclusions[child.op_id].reason == ExclusionReason.BLOCKED_DEPENDENCY
    assert exclusions[cleanup.op_id].outcome is Outcome.DEFERRED

    reselected = apply_selection_mutation(
        plan,
        user_deselected,
        reselect=frozenset({child.op_id}),
    )
    decision = derive_execution_selection(plan, user_deselected=reselected)

    assert reselected == frozenset({leaf_removal.op_id})
    assert child.op_id in decision.selection
    assert folder.op_id in decision.selection
    assert cleanup.op_id not in decision.selection


def test_br_g_12_unknown_and_safety_excluded_mutations_are_refused() -> None:
    blocked = _operation(
        1,
        OperationKind.MKDIR,
        "blocked",
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    child = _operation(
        2,
        OperationKind.COPY,
        r"blocked\child.bin",
        dependencies=(blocked.op_id,),
    )
    plan = _plan((blocked, child))

    with pytest.raises(ValueError, match="unknown operation"):
        apply_selection_mutation(
            plan,
            frozenset(),
            deselect=frozenset({OpId("f" * 32)}),
        )
    with pytest.raises(ValueError, match="safety-excluded"):
        apply_selection_mutation(
            plan,
            frozenset(),
            reselect=frozenset({child.op_id}),
        )

    decision = derive_execution_selection(plan)
    assert child.op_id not in decision.selection


def test_br_g_11_all_noop_uses_selected_kinds_not_skipped_outcomes() -> None:
    noop = ItemOutcome(
        "noop",
        OperationKind.NOOP.value,
        "same.bin",
        Outcome.SKIPPED,
        reason="noop",
    )
    user_copy = ItemOutcome(
        "copy",
        OperationKind.COPY.value,
        "copy.bin",
        Outcome.SKIPPED,
        reason=ExclusionReason.USER_DESELECTED.value,
    )

    mixed = operation_result_view(
        OperationResult(SessionState.COMPLETED, items=(noop, user_copy))
    )
    empty = operation_result_view(
        OperationResult(SessionState.COMPLETED, items=(user_copy,))
    )

    assert mixed.headline == "all-noop"
    assert empty.headline == "success"
    assert SELECTION_EXCLUSION_REASONS == frozenset(
        {
            "blocked-correspondence",
            "blocked-dependency",
            "incomplete-scan",
            "user-deselected",
            "unsupported",
            "case_mismatch",
            "case_collision",
            "type_collision",
            "destination_collision",
            "blocked_dependency",
        }
    )


def test_br_g_11_empty_effective_selection_is_refused_before_preflight() -> None:
    operation = _operation(1, OperationKind.COPY, "copy.bin")
    plan = _plan((operation,))
    user_deselected = frozenset({operation.op_id})
    selection = derive_execution_selection(
        plan,
        user_deselected=user_deselected,
    ).selection
    xset = ExecutionSet(
        plan=plan,
        selection=selection,
        run_id=validated_run_id("a" * 32),
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(selection),
            datetime(2026, 7, 30, tzinfo=timezone.utc),
        ),
        user_deselected=user_deselected,
    )
    preflight_calls: list[object] = []

    result = run_execution(
        xset,
        RunContext(lambda body: None, lambda: None),
        SimpleNamespace(
            save_execution_details=lambda details: None,
            observer=lambda *args: preflight_calls.append(args),
        ),
    )

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert preflight_calls == []
