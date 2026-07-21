from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
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
from namisync.core.session import Disposition, OperationResult, RunContext, SessionState
from namisync.core.preflight import Refusal, RefusalCode, Verdict
from namisync.workflows.selection import ExclusionReason, derive_execution_selection
from namisync.workflows.sync import run_execution
from namisync.workflows.models import PlanArtifact, PlanRequest
from namisync.workflows.runtime import LocalWorkflowRuntime


NOW = datetime(2026, 7, 19, tzinfo=timezone.utc)


def _empty_plan() -> Plan:
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
        operations=(),
        assignment=Assignment("identity", "1", ()),
        preservation=PreservationPolicy(),
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=True,
        policy_fingerprint="p" * 64,
        worker_count=1,
        required_volumes=frozenset(),
        required_bytes=0,
        fingerprint=PlanFingerprint("0" * 64),
    )
    return replace(placeholder, fingerprint=plan_fingerprint(placeholder))


def _operation(
    index: int,
    kind: OperationKind,
    target: str,
    *,
    source: str | None = None,
    prior_target: str | None = None,
    dependencies: tuple[OpId, ...] = (),
    reason: OperationReason = OperationReason.SOURCE_ONLY,
    blocked_reason: BlockedReason | None = None,
    content_bytes: int = 0,
) -> PlanOperation:
    return PlanOperation(
        OpId(f"{index:032x}"),
        kind,
        source,
        target,
        None,
        None,
        None,
        prior_target_rel_path=prior_target,
        content_bytes=content_bytes,
        dependencies=dependencies,
        reason=reason,
        blocked_reason=blocked_reason,
    )


def _plan_with(
    operations: tuple[PlanOperation, ...],
    *,
    source_complete: bool = True,
    target_complete: bool = True,
) -> Plan:
    value = replace(
        _empty_plan(),
        source_complete=source_complete,
        target_complete=target_complete,
        operations=operations,
        fingerprint=PlanFingerprint("0" * 64),
    )
    return replace(value, fingerprint=plan_fingerprint(value))


def test_selection_excludes_blocker_and_quarantines_its_target_tree() -> None:
    blocked = _operation(
        1,
        OperationKind.NOOP,
        "foo",
        source="foo",
        reason=OperationReason.UNSUPPORTED,
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    independent = _operation(2, OperationKind.COPY, "normal.txt", source="normal.txt")
    counterpart = _operation(
        3,
        OperationKind.TRASH,
        r"foo\keep.txt",
        reason=OperationReason.TARGET_ONLY,
    )
    cleanup = _operation(
        4,
        OperationKind.DELETE,
        "foo",
        dependencies=(counterpart.op_id,),
        reason=OperationReason.DIRECTORY_CLEANUP,
    )
    unrelated_removal = _operation(
        5,
        OperationKind.TRASH,
        "old.txt",
        reason=OperationReason.TARGET_ONLY,
    )

    decision = derive_execution_selection(
        _plan_with((blocked, independent, counterpart, cleanup, unrelated_removal))
    )
    excluded = {item.op_id: item for item in decision.exclusions}

    assert decision.selection == frozenset(
        {independent.op_id, unrelated_removal.op_id}
    )
    assert excluded[blocked.op_id].outcome is Outcome.BLOCKED
    assert excluded[blocked.op_id].reason == BlockedReason.UNSUPPORTED.value
    assert excluded[counterpart.op_id].outcome is Outcome.DEFERRED
    assert excluded[counterpart.op_id].reason == ExclusionReason.BLOCKED_CORRESPONDENCE
    assert excluded[cleanup.op_id].reason == ExclusionReason.BLOCKED_CORRESPONDENCE


def test_selection_closes_over_dependencies_of_excluded_operations() -> None:
    blocked = _operation(
        1,
        OperationKind.NOOP,
        "blocked.bin",
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    dependent = _operation(
        2,
        OperationKind.COPY,
        "elsewhere.bin",
        source="elsewhere.bin",
        dependencies=(blocked.op_id,),
    )

    decision = derive_execution_selection(_plan_with((blocked, dependent)))
    excluded = {item.op_id: item for item in decision.exclusions}

    assert decision.selection == frozenset()
    assert excluded[dependent.op_id].reason == ExclusionReason.BLOCKED_DEPENDENCY


def test_incomplete_scan_keeps_guarded_work_but_withholds_destructive_and_moves() -> None:
    operations = (
        _operation(1, OperationKind.MKDIR, "folder", source="folder"),
        _operation(2, OperationKind.COPY, "copy.bin", source="copy.bin"),
        _operation(3, OperationKind.UPDATE, "update.bin", source="update.bin"),
        _operation(4, OperationKind.NOOP, "same.bin", source="same.bin"),
        _operation(
            5,
            OperationKind.RECASE,
            "KEEP.bin",
            source="KEEP.bin",
            prior_target="keep.bin",
        ),
        _operation(6, OperationKind.TRASH, "trash.bin"),
        _operation(7, OperationKind.DELETE, "delete.bin"),
        _operation(
            8,
            OperationKind.MOVE,
            "moved.bin",
            source="moved.bin",
            prior_target="old.bin",
        ),
        _operation(
            9,
            OperationKind.MOVE_UPDATE,
            "moved-update.bin",
            source="moved-update.bin",
            prior_target="old-update.bin",
        ),
    )

    decision = derive_execution_selection(
        _plan_with(operations, source_complete=False)
    )
    selected_kinds = {
        operation.kind
        for operation in operations
        if operation.op_id in decision.selection
    }
    excluded = {item.op_id: item for item in decision.exclusions}

    assert selected_kinds == {
        OperationKind.MKDIR,
        OperationKind.COPY,
        OperationKind.UPDATE,
        OperationKind.NOOP,
        OperationKind.RECASE,
    }
    assert {
        excluded[operation.op_id].reason
        for operation in operations
        if operation.kind
        in {
            OperationKind.TRASH,
            OperationKind.DELETE,
            OperationKind.MOVE,
            OperationKind.MOVE_UPDATE,
        }
    } == {ExclusionReason.INCOMPLETE_SCAN}

    complete_decision = derive_execution_selection(_plan_with(operations))
    assert complete_decision.selection == frozenset(
        operation.op_id for operation in operations
    )
    assert complete_decision.exclusions == ()


def test_execution_reports_exclusions_without_failing_successful_subset() -> None:
    blocked = _operation(
        1,
        OperationKind.NOOP,
        "junction",
        source="junction",
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    copied = _operation(2, OperationKind.COPY, "normal.txt", source="normal.txt")
    plan = _plan_with((blocked, copied))
    decision = derive_execution_selection(plan)
    run_id = validated_run_id("5" * 32)
    xset = ExecutionSet(
        plan,
        decision.selection,
        run_id,
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(decision.selection),
            NOW,
        ),
    )
    events: list[object] = []
    saved: list[object] = []
    finished: list[tuple[SessionState, object]] = []
    world = SimpleNamespace(paths={}, target_parent_paths=frozenset({""}))
    cleanup_calls: list[tuple[Path, frozenset[str], object]] = []

    class FileSystem:
        def remove_orphaned_temps(self, target, parents, current_run_id) -> None:
            cleanup_calls.append((target, parents, current_run_id))

    class Recording:
        recorder = object()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def finish(self, status, recording) -> None:
            finished.append((status, recording))

    def executor(execution_set, ctx, recorder, policies, fs):
        del recorder, policies, fs
        operation = next(
            operation
            for operation in execution_set.plan.operations
            if operation.op_id in execution_set.selection
        )
        item = ItemOutcome(
            str(operation.op_id),
            operation.kind.value,
            operation.target_rel_path,
            Outcome.SUCCEEDED,
        )
        ctx.emit(item)
        return OperationResult(SessionState.COMPLETED, operations=(item,))

    deps = SimpleNamespace(
        save_execution_details=saved.append,
        observer=lambda *args: world,
        observation_fs=object(),
        settings=lambda value: object(),
        preflight=lambda execution_set, observed: Verdict(True, (), observed),
        open_recording=lambda execution_set: Recording(),
        executor=executor,
        executor_policies=object(),
        executor_fs=FileSystem(),
    )

    result = run_execution(xset, RunContext(events.append, lambda: None), deps)

    assert result.status is SessionState.COMPLETED
    assert [item.outcome for item in result.operations] == [
        Outcome.BLOCKED,
        Outcome.SUCCEEDED,
    ]
    assert [item.outcome for item in events if isinstance(item, ItemOutcome)] == [
        Outcome.SUCCEEDED,
        Outcome.BLOCKED,
    ]
    assert cleanup_calls == [
        (Path(plan.target_root.path), frozenset({""}), run_id)
    ]
    assert finished and saved


def test_review_and_commit_bind_the_same_safe_selection(tmp_path: Path) -> None:
    blocked = _operation(
        1,
        OperationKind.NOOP,
        "junction",
        source="junction",
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    copied = _operation(
        2,
        OperationKind.COPY,
        "normal.txt",
        source="normal.txt",
        content_bytes=17,
    )
    withheld = _operation(3, OperationKind.TRASH, "old.txt")
    plan = _plan_with(
        (blocked, copied, withheld),
        source_complete=False,
    )
    request = PlanRequest("request", plan.source_root.path, plan.target_root.path)
    world = SimpleNamespace(
        paths={}, free_space=1_000, reclaimable_temp_bytes=0
    )
    artifact = PlanArtifact(
        request,
        SimpleNamespace(warnings=()),
        SimpleNamespace(warnings=()),
        plan,
        Verdict(True, (), world),
    )
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db", tmp_path / "history.db"
    )
    try:
        runtime._save_plan(artifact)

        review = runtime.get_plan_review(request.request_id)
        execution = runtime.commit_plan(
            request.request_id,
            run_id="6" * 32,
            committed_at=NOW,
        )
    finally:
        runtime.close()

    selected = execution.execution_set.selection
    assert selected == frozenset({copied.op_id})
    assert review.selection_digest_hex == selection_digest(selected).hex()
    assert review.required_bytes == 17
    assert execution.execution_set.commitment is not None
    assert execution.execution_set.commitment.selection_digest == selection_digest(
        selected
    )


def test_fresh_preflight_refusal_still_reports_known_exclusions() -> None:
    blocked = _operation(
        1,
        OperationKind.NOOP,
        "junction",
        source="junction",
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    plan = _plan_with((blocked,))
    decision = derive_execution_selection(plan)
    xset = ExecutionSet(
        plan,
        decision.selection,
        validated_run_id("7" * 32),
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(decision.selection),
            NOW,
        ),
    )
    world = SimpleNamespace(paths={})
    events: list[object] = []
    deps = SimpleNamespace(
        save_execution_details=lambda value: None,
        observer=lambda *args: world,
        observation_fs=object(),
        settings=lambda value: object(),
        preflight=lambda execution_set, observed: Verdict(
            False,
            (Refusal(RefusalCode.ROOT_CHANGED),),
            observed,
        ),
    )

    result = run_execution(xset, RunContext(events.append, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert [item.outcome for item in result.operations] == [Outcome.BLOCKED]
    assert [item.outcome for item in events if isinstance(item, ItemOutcome)] == [
        Outcome.BLOCKED
    ]


def test_temp_recovery_failure_stops_before_executor_and_records_failure() -> None:
    plan = _plan_with(
        (_operation(1, OperationKind.COPY, "normal.txt", source="normal.txt"),)
    )
    selection = frozenset(operation.op_id for operation in plan.operations)
    run_id = validated_run_id("8" * 32)
    xset = ExecutionSet(
        plan,
        selection,
        run_id,
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    finished: list[SessionState] = []
    executor_called = False
    world = SimpleNamespace(paths={}, target_parent_paths=frozenset({""}))

    class Recording:
        recorder = object()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def finish(self, status, recording) -> None:
            del recording
            finished.append(status)

    class FileSystem:
        def remove_orphaned_temps(self, target, parents, current_run_id) -> None:
            del target, parents, current_run_id
            raise PermissionError("orphan is locked")

    def executor(*args):
        nonlocal executor_called
        executor_called = True
        return OperationResult(SessionState.COMPLETED)

    deps = SimpleNamespace(
        save_execution_details=lambda value: None,
        observer=lambda *args: world,
        observation_fs=object(),
        settings=lambda value: object(),
        preflight=lambda execution_set, observed: Verdict(True, (), observed),
        open_recording=lambda execution_set: Recording(),
        executor=executor,
        executor_policies=object(),
        executor_fs=FileSystem(),
    )

    with pytest.raises(PermissionError, match="orphan is locked"):
        run_execution(xset, RunContext(lambda value: None, lambda: None), deps)

    assert not executor_called
    assert finished == [SessionState.FAILED]


def test_execution_refuses_uncommitted_set_before_preflight() -> None:
    saved = []
    xset = ExecutionSet(
        _empty_plan(), frozenset(), validated_run_id("1" * 32)
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert saved[0].commitment_error == "execution set is not committed"


def test_execution_refuses_changed_selection_digest_before_preflight() -> None:
    saved = []
    plan = _empty_plan()
    xset = ExecutionSet(
        plan,
        frozenset(),
        validated_run_id("2" * 32),
        commitment=Commitment(plan.fingerprint, b"x" * 32, NOW),
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert "selection digest" in saved[0].commitment_error


def test_execution_refuses_changed_plan_fingerprint_before_preflight() -> None:
    saved = []
    plan = _empty_plan()
    xset = ExecutionSet(
        plan,
        frozenset(),
        validated_run_id("3" * 32),
        commitment=Commitment(PlanFingerprint("e" * 64), b"x" * 32, NOW),
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert "plan fingerprint" in saved[0].commitment_error


def test_execution_refuses_plan_content_that_no_longer_matches_fingerprint() -> None:
    saved = []
    plan = _empty_plan()
    tampered = replace(plan, deletion_policy=DeletionPolicy.ADDITIVE)
    xset = ExecutionSet(
        tampered,
        frozenset(),
        validated_run_id("4" * 32),
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(frozenset()),
            NOW,
        ),
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert "plan content" in saved[0].commitment_error
