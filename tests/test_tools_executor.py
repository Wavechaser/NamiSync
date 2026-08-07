from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from namisync.core.session import SessionState
from tools import corpus, executor_rig


def test_executor_diagnostics_tap_is_removed_when_disabled(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"

    with corpus.claim(target) as workspace:
        without_metrics = executor_rig.run_executor(
            source, workspace, collect_metrics=False
        )
        corpus.empty(workspace)
        with_metrics = executor_rig.run_executor(
            source, workspace, collect_metrics=True
        )
        corpus.teardown(workspace)

    assert without_metrics.result.status is SessionState.COMPLETED
    assert without_metrics.copy_samples == ()
    assert with_metrics.result.status is SessionState.COMPLETED
    assert len(with_metrics.copy_samples) == 1
    assert with_metrics.copy_samples[0].metrics is not None


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
        executor_rig.build_execution_set(tmp_path / "source", tmp_path / "target")


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
        corpus.teardown(workspace)


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
        executor_rig.build_execution_set(tmp_path / "source", tmp_path / "target")
