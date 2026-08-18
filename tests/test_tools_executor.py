from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from namisync.core.execution import validated_run_id
from namisync.core.planning import OperationKind
from namisync.core.session import SessionState
from tools import corpus, executor_rig


def _record_outputs(
    workspace: corpus.WorkspaceClaim,
    run: executor_rig.ExecutorRun,
) -> None:
    files, directories = executor_rig.expected_output_paths(run)
    corpus.record_outputs(workspace, files=files, directories=directories)


def test_executor_diagnostics_tap_is_removed_when_disabled(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"

    with corpus.claim(target) as workspace:
        without_metrics = executor_rig.run_executor(
            source, workspace, collect_metrics=False
        )
        _record_outputs(workspace, without_metrics)
        corpus.empty(workspace)
        with_metrics = executor_rig.run_executor(
            source, workspace, collect_metrics=True
        )
        _record_outputs(workspace, with_metrics)
        corpus.teardown(workspace)

    assert without_metrics.result.status is SessionState.COMPLETED
    assert without_metrics.copy_samples == ()
    assert with_metrics.result.status is SessionState.COMPLETED
    assert len(with_metrics.copy_samples) == 1
    assert with_metrics.copy_samples[0].metrics is not None


def test_move_update_output_always_includes_the_prior_path_trash_copy() -> None:
    op_id = "a" * 32
    run_id = validated_run_id("b" * 32)
    operation = SimpleNamespace(
        op_id=op_id,
        kind=OperationKind.MOVE_UPDATE,
        target_rel_path="renamed.bin",
        prior_target_rel_path="prior.bin",
    )
    run = SimpleNamespace(
        target_scan=SimpleNamespace(
            files=(SimpleNamespace(rel_path="prior.bin"),),
            directories=(),
        ),
        plan=SimpleNamespace(
            operations=(operation,),
            trash_on_update=False,
        ),
        execution_set=SimpleNamespace(
            selection=frozenset({op_id}),
            run_id=run_id,
        ),
    )

    files, directories = executor_rig.expected_output_paths(run)

    assert files == {
        "renamed.bin",
        f".synctrash/{run_id}/prior.bin",
    }
    assert ".synctrash" in directories
    assert f".synctrash/{run_id}" in directories


def test_prepared_copy_plan_reuses_plan_with_fresh_execution_state(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"

    with corpus.claim(target) as workspace:
        prepared = executor_rig.prepare_execution(source, target)
        executor_rig.require_reusable_copy_plan(prepared)

        first = executor_rig.execute_prepared(prepared, workspace)
        _record_outputs(workspace, first)
        corpus.empty(workspace)
        second = executor_rig.execute_prepared(
            prepared,
            workspace,
            preflight_gate=False,
        )
        _record_outputs(workspace, second)
        corpus.empty(workspace)
        corpus.teardown(workspace)

    assert first.plan is second.plan is prepared.plan
    assert first.execution_set is not second.execution_set
    assert first.execution_set.run_id != second.execution_set.run_id
    assert first.result.status is second.result.status is SessionState.COMPLETED
    executor_rig.require_stable_copy_evidence(first, second)


def test_reusable_copy_plan_refuses_a_nonempty_target_workload(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"new")
    target = tmp_path / "target"

    with corpus.claim(target) as workspace:
        (target / "data.bin").write_bytes(b"old")
        prepared = executor_rig.prepare_execution(source, target)

        with pytest.raises(executor_rig.ExecutorRigError, match="empty-target copy"):
            executor_rig.require_reusable_copy_plan(prepared)

        corpus.record_outputs(workspace, files={"data.bin"}, directories=set())
        corpus.empty(workspace)
        corpus.teardown(workspace)


def test_reused_plan_detects_same_stat_content_drift_between_samples(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    payload = source / "data.bin"
    payload.write_bytes(b"first!!")
    target = tmp_path / "target"

    with corpus.claim(target) as workspace:
        prepared = executor_rig.prepare_execution(source, target)
        first = executor_rig.execute_prepared(prepared, workspace)
        _record_outputs(workspace, first)
        corpus.empty(workspace)

        before = payload.stat()
        payload.write_bytes(b"second!")
        os.utime(payload, ns=(before.st_atime_ns, before.st_mtime_ns))
        second = executor_rig.execute_prepared(
            prepared,
            workspace,
            preflight_gate=False,
        )
        _record_outputs(workspace, second)

        with pytest.raises(executor_rig.ExecutorRigError, match="copy evidence changed"):
            executor_rig.require_stable_copy_evidence(first, second)

        corpus.empty(workspace)
        corpus.teardown(workspace)


def test_reused_plan_detects_source_membership_drift(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"

    with corpus.claim(target) as workspace:
        prepared = executor_rig.prepare_execution(source, target)
        (source / "added.bin").write_bytes(b"added")

        with pytest.raises(executor_rig.ExecutorRigError, match="source corpus changed"):
            executor_rig.require_source_unchanged(prepared)

        corpus.teardown(workspace)


def test_executor_requires_a_live_workspace_claim(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target"
    workspace = corpus.claim(target)
    workspace.close()

    try:
        with pytest.raises(corpus.CorpusError, match="no longer live"):
            executor_rig.run_executor(source, workspace)
    finally:
        with corpus.claim(target) as cleanup:
            corpus.teardown(cleanup)


def test_executor_refuses_an_incomplete_benchmark_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    incomplete = SimpleNamespace(
        complete=False,
        unsupported=(),
        warnings=(),
    )
    monkeypatch.setattr(executor_rig, "scan_root", lambda *args, **kwargs: incomplete)

    with pytest.raises(executor_rig.ExecutorRigError, match="not a complete"):
        executor_rig.prepare_execution(tmp_path / "source", tmp_path / "target")


@pytest.mark.parametrize("relationship", ["equal", "source_contains", "target_contains"])
def test_executor_refuses_source_target_overlap_for_direct_callers(
    tmp_path: Path, relationship: str
) -> None:
    if relationship == "equal":
        target = tmp_path / "target"
        with corpus.claim(target) as workspace:
            with pytest.raises(executor_rig.ExecutorRigError, match="must not overlap"):
                executor_rig.run_executor(target, workspace)
            corpus.teardown(workspace)
        return

    if relationship == "source_contains":
        source = tmp_path / "source"
        source.mkdir()
        target = source / "target"
        with corpus.claim(target) as workspace:
            with pytest.raises(executor_rig.ExecutorRigError, match="must not overlap"):
                executor_rig.run_executor(source, workspace)
            corpus.teardown(workspace)
        return

    target = tmp_path / "target"
    with corpus.claim(target) as workspace:
        source = target / "source"
        source.mkdir()
        with pytest.raises(executor_rig.ExecutorRigError, match="must not overlap"):
            executor_rig.run_executor(source, workspace)
        corpus.force_teardown(workspace)


def test_executor_refuses_a_plan_with_safety_exclusions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scan = SimpleNamespace(
        complete=True,
        unsupported=(),
        warnings=(),
        volume_id=None,
    )
    plan = SimpleNamespace(operations=())
    selection = SimpleNamespace(
        selection=frozenset(),
        exclusions=(SimpleNamespace(reason="blocked"),),
    )
    monkeypatch.setattr(executor_rig, "scan_root", lambda *args, **kwargs: scan)
    monkeypatch.setattr(executor_rig, "build_plan", lambda *args, **kwargs: plan)
    monkeypatch.setattr(
        executor_rig,
        "derive_execution_selection",
        lambda *args, **kwargs: selection,
    )

    with pytest.raises(executor_rig.ExecutorRigError, match="safety exclusions"):
        executor_rig.prepare_execution(tmp_path / "source", tmp_path / "target")
