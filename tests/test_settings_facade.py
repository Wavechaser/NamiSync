from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

import namisync.interfaces.service as service_module
from namisync.core.session import RunContext, SessionState
from namisync.interfaces.service import (
    NamiSyncService,
    PreservationSettingsView,
    SemanticSettingsPatchView,
    SemanticSettingsView,
)
from namisync.interfaces.task_lifecycle import TaskLifecycle
from namisync.workflows.runtime import LocalWorkflowRuntime


def _wait_for_terminal(service: NamiSyncService, session_id: str):
    current = service.observe(session_id, lambda _update: None)
    try:
        return current if current.result is not None else service.wait(session_id)
    finally:
        service.unsubscribe(session_id)


def test_runtime_settings_views_preserve_unpatched_keys_and_default_path(
    tmp_path: Path,
) -> None:
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    try:
        assert runtime.settings_path == (tmp_path / "settings.json").resolve()

        first = runtime.commit_semantic_settings(
            SemanticSettingsPatchView(
                filters=("*.tmp", "*.bak"),
                trash_on_update=False,
                preservation=PreservationSettingsView(
                    preserve_ads=True,
                    preserve_created=False,
                    preserve_acl=True,
                ),
                propagate_source_casing=True,
            )
        )
        second = runtime.commit_semantic_settings(
            SemanticSettingsPatchView(deletion_policy="additive")
        )

        assert second == runtime.read_semantic_settings()
        assert second.filters == ("*.bak", "*.tmp")
        assert second.deletion_policy == "additive"
        assert not second.trash_on_update
        assert second.preservation == first.preservation
        assert second.propagate_source_casing
    finally:
        runtime.close()


def test_service_uses_explicit_settings_path_and_has_no_database_import(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "profile" / "semantic.json"
    with NamiSyncService(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
        settings_path=settings_path,
    ) as service:
        updated = service.commit_semantic_settings(
            SemanticSettingsPatchView(deletion_policy="additive")
        )
        assert service.read_semantic_settings() == updated

    assert settings_path.exists()
    tree = ast.parse(Path(service_module.__file__).read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(name == "namisync.db" or name.startswith("namisync.db.") for name in imports)


def test_settings_path_cannot_alias_a_database_or_managed_root(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    with pytest.raises(ValueError, match="distinct from both databases"):
        LocalWorkflowRuntime(
            ledger,
            history,
            settings_path=ledger,
        )

    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    runtime = LocalWorkflowRuntime(
        ledger,
        history,
        settings_path=source / "settings.json",
    )
    try:
        request = runtime.create_plan_request(
            "unsafe-settings",
            str(source),
            str(target),
        )
        with pytest.raises(ValueError, match="outside managed roots"):
            runtime.prepare_plan(request)
    finally:
        runtime.close()


def test_invalid_public_settings_values_never_poison_or_create_a_file(
    tmp_path: Path,
) -> None:
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    try:
        runtime.commit_semantic_settings(
            SemanticSettingsPatchView(deletion_policy="additive")
        )
        original = runtime.settings_path.read_bytes()
        invalid_values = (
            lambda: SemanticSettingsPatchView(filters=["*.tmp"]),  # type: ignore[arg-type]
            lambda: SemanticSettingsPatchView(filters=(1,)),  # type: ignore[arg-type]
            lambda: SemanticSettingsPatchView(deletion_policy="mirror"),
            lambda: SemanticSettingsPatchView(trash_on_update=1),  # type: ignore[arg-type]
            lambda: SemanticSettingsPatchView(preservation=object()),  # type: ignore[arg-type]
            lambda: SemanticSettingsPatchView(
                propagate_source_casing="yes"  # type: ignore[arg-type]
            ),
            lambda: PreservationSettingsView(False, 0, False),  # type: ignore[arg-type]
            lambda: SemanticSettingsView(
                filters=(),
                deletion_policy="trash",
                trash_on_update=True,
                preservation=PreservationSettingsView(False, True, False),
                propagate_source_casing=1,  # type: ignore[arg-type]
            ),
        )

        for construct in invalid_values:
            with pytest.raises((TypeError, ValueError)):
                construct()
            assert runtime.settings_path.read_bytes() == original
            assert runtime.read_semantic_settings().deletion_policy == "additive"
    finally:
        runtime.close()

    missing = tmp_path / "missing" / "settings.json"
    missing_runtime = LocalWorkflowRuntime(
        tmp_path / "missing-ledger.db",
        tmp_path / "missing-history.db",
        settings_path=missing,
    )
    try:
        with pytest.raises(TypeError, match="trash_on_update must be a bool"):
            missing_runtime.commit_semantic_settings(
                SemanticSettingsPatchView(
                    trash_on_update="false"  # type: ignore[arg-type]
                )
            )
    finally:
        missing_runtime.close()
    assert not missing.exists()


def test_plan_request_captures_stored_defaults_and_one_plan_deletion_override(
    tmp_path: Path,
) -> None:
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    try:
        runtime.commit_semantic_settings(
            SemanticSettingsPatchView(
                filters=("*.tmp",),
                deletion_policy="additive",
                trash_on_update=False,
                preservation=PreservationSettingsView(
                    preserve_ads=True,
                    preserve_created=False,
                    preserve_acl=True,
                ),
                propagate_source_casing=True,
            )
        )

        stored = runtime.create_plan_request("stored", "source", "target")
        overridden = runtime.create_plan_request(
            "override",
            "source",
            "target",
            deletion_policy="trash",
        )

        assert stored.options.deletion_policy.value == "additive"
        assert stored.options.filters.patterns == ("*.tmp",)
        assert not stored.options.trash_on_update
        assert stored.options.preservation.preserve_ads
        assert not stored.options.preservation.preserve_created
        assert stored.options.preservation.preserve_acl
        assert stored.options.propagate_source_casing
        assert overridden.options.deletion_policy.value == "trash"
        assert overridden.options.filters == stored.options.filters
        assert overridden.options.trash_on_update == stored.options.trash_on_update
        assert overridden.options.preservation == stored.options.preservation
        assert (
            overridden.options.propagate_source_casing
            == stored.options.propagate_source_casing
        )
        assert runtime.read_semantic_settings().deletion_policy == "additive"
    finally:
        runtime.close()


def test_malformed_settings_refuse_planning_before_dispatcher_submit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"schema_version":999}', encoding="utf-8")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
        settings_path=settings_path,
    )

    class Dispatcher:
        def submit(self, kind: str, request: object):
            raise AssertionError("malformed settings must fail before submission")

    service = object.__new__(NamiSyncService)
    service._runtime = runtime
    service._dispatcher = Dispatcher()
    service._lifecycle = TaskLifecycle()
    try:
        with pytest.raises(ValueError, match="missing or unknown"):
            service.start_plan(str(source), str(target))
    finally:
        runtime.close()
    assert not (tmp_path / "ledger.db").exists()
    assert not (tmp_path / "history.db").exists()


def test_committed_plan_keeps_captured_settings_after_defaults_change(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.txt").write_text("included", encoding="utf-8")
    (source / "ignored.tmp").write_text("excluded", encoding="utf-8")
    (target / "orphan.txt").write_text("retained", encoding="utf-8")

    with NamiSyncService(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    ) as service:
        service.commit_semantic_settings(
            SemanticSettingsPatchView(
                filters=("*.tmp",),
                deletion_policy="additive",
                trash_on_update=False,
            )
        )
        planned = service.start_plan(str(source), str(target))
        plan_record = _wait_for_terminal(service, planned.session_id)
        assert plan_record.result is not None
        assert plan_record.result.filesystem == "completed"

        service.commit_semantic_settings(
            SemanticSettingsPatchView(
                filters=(),
                deletion_policy="trash",
                trash_on_update=True,
            )
        )
        review = service.get_plan_review(planned.request_id)
        artifact = service.get_plan(planned.request_id)
        execution = service.start_execution(planned.request_id)
        execution_record = _wait_for_terminal(service, execution.session_id)

        assert review.deletion_policy == "additive"
        assert not review.trash_on_update
        assert review.semantic_settings.filters == ("*.tmp",)
        assert review.semantic_settings.deletion_policy == "additive"
        assert not review.semantic_settings.trash_on_update
        assert not review.semantic_settings.preservation.preserve_ads
        assert review.semantic_settings.preservation.preserve_created
        assert not review.semantic_settings.preservation.preserve_acl
        assert not review.semantic_settings.propagate_source_casing
        assert artifact.request.options.filters.patterns == ("*.tmp",)
        assert artifact.plan.filter_snapshot.patterns == ("*.tmp",)
        assert artifact.plan.deletion_policy.value == "additive"
        assert execution_record.result is not None
        assert execution_record.result.filesystem == "completed"

    assert (target / "payload.txt").read_text(encoding="utf-8") == "included"
    assert not (target / "ignored.tmp").exists()
    assert (target / "orphan.txt").read_text(encoding="utf-8") == "retained"


def test_xv_11_committed_plan_executes_every_original_semantic_default(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.txt").write_text("new payload", encoding="utf-8")
    (target / "payload.txt").write_text("old", encoding="utf-8")
    (source / "ignored.tmp").write_text("excluded", encoding="utf-8")
    source_case = source / "KEEP.txt"
    source_case.write_text("same", encoding="utf-8")
    shutil.copy2(source_case, target / "keep.txt")
    (target / "orphan.txt").write_text("retained", encoding="utf-8")

    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    context = RunContext(lambda _event: None, lambda: None)
    try:
        original = PreservationSettingsView(
            preserve_ads=False,
            preserve_created=True,
            preserve_acl=False,
        )
        runtime.commit_semantic_settings(
            SemanticSettingsPatchView(
                filters=("*.tmp",),
                deletion_policy="additive",
                trash_on_update=False,
                preservation=original,
                propagate_source_casing=False,
            )
        )
        request = runtime.create_plan_request(
            "1" * 32,
            str(source),
            str(target),
        )
        plan_preparation = runtime.prepare_plan(request)
        plan_result = runtime.open_plan(plan_preparation.checkpoint).run(context)
        review = runtime.get_plan_review(request.request_id)
        committed = runtime.commit_plan(request.request_id)

        runtime.commit_semantic_settings(
            SemanticSettingsPatchView(
                filters=(),
                deletion_policy="trash",
                trash_on_update=True,
                preservation=PreservationSettingsView(
                    preserve_ads=True,
                    preserve_created=False,
                    preserve_acl=True,
                ),
                propagate_source_casing=True,
            )
        )
        execution_preparation = runtime.prepare_execution(committed)
        execution_result = runtime.open_execution(
            execution_preparation.checkpoint
        ).run(context)
        reviewed_again = runtime.get_plan_review(request.request_id)

        assert plan_result.status is SessionState.COMPLETED
        assert execution_result.status is SessionState.COMPLETED
        assert review.semantic_settings == reviewed_again.semantic_settings
        assert review.semantic_settings.filters == ("*.tmp",)
        assert review.semantic_settings.deletion_policy == "additive"
        assert not review.semantic_settings.trash_on_update
        assert review.semantic_settings.preservation == original
        assert not review.semantic_settings.propagate_source_casing
        assert committed.execution_set.plan.deletion_policy.value == "additive"
        assert not committed.execution_set.plan.trash_on_update
        assert committed.execution_set.plan.preservation == (
            request.options.preservation
        )
    finally:
        runtime.close()

    assert (target / "payload.txt").read_text(encoding="utf-8") == "new payload"
    assert not (target / "ignored.tmp").exists()
    assert (target / "orphan.txt").exists()
    assert "keep.txt" in {path.name for path in target.iterdir()}
    assert not (target / ".synctrash").exists()


def test_xv_11_execution_and_preflight_have_no_live_settings_dependency() -> None:
    root = Path(__file__).parents[1] / "namisync"
    executor_sources = tuple((root / "modules" / "executor").glob("*.py"))
    sources = executor_sources + (
        root / "modules" / "preflight.py",
        root / "workflows" / "sync.py",
    )
    for source_path in sources:
        source = source_path.read_text(encoding="utf-8")
        assert "namisync.db.settings" not in source
        assert "SemanticSettings" not in source
        assert "SemanticSettingsStore" not in source
        assert "_settings_store" not in source

    runtime_source = (
        root / "workflows" / "runtime.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(runtime_source)
    execution_methods = {
        node.name: ast.get_source_segment(runtime_source, node) or ""
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name
        in {
            "commit_plan",
            "prepare_execution",
            "open_execution",
            "settle_canceled_execution",
        }
    }
    assert set(execution_methods) == {
        "commit_plan",
        "prepare_execution",
        "open_execution",
        "settle_canceled_execution",
    }
    assert all(
        "_settings_store" not in source
        and "read_semantic_settings" not in source
        for source in execution_methods.values()
    )
