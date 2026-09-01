"""Executable primary ownership for collected pytest modules."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).parents[1]

DEPARTMENTS: dict[str, tuple[str, ...]] = {
    "core": (
        "tests/core/test_event_v5_consumers.py",
        "tests/core/test_exception_graph.py",
        "tests/core/test_integrity.py",
        "tests/core/test_root_authority.py",
        "tests/core/test_scalar_identity_contracts.py",
        "tests/core/test_session_events.py",
        "tests/test_core_scanplan.py",
        "tests/test_plan_review_limits.py",
    ),
    "scanner": ("tests/test_scanner.py",),
    "planner": ("tests/test_planner.py",),
    "preflight": ("tests/test_preflight.py",),
    "executor": (
        "tests/test_executor_acl.py",
        "tests/test_executor_native.py",
        "tests/test_executor_pending_cancel.py",
        "tests/test_executor_pipeline.py",
        "tests/test_executor_runtime.py",
        "tests/test_executor_settlement.py",
    ),
    "verifier": (
        "tests/modules/test_verifier_engine.py",
        "tests/modules/test_verifier_native.py",
    ),
    "database": (
        "tests/test_db_history.py",
        "tests/test_db_repositories.py",
        "tests/test_db_schema.py",
        "tests/test_db_write_boundary.py",
        "tests/test_db_writer.py",
        "tests/test_recorder_concurrency.py",
        "tests/test_recorder_identity_receipts.py",
        "tests/test_recorder_inventory_integrity.py",
        "tests/test_recorder_setup_and_move.py",
        "tests/test_recorder_sync.py",
        "tests/test_settings.py",
    ),
    "workflows": (
        "tests/test_bridge_resume.py",
        "tests/test_bridge_scan_scope.py",
        "tests/test_bridge_selection.py",
        "tests/test_bridge_tree.py",
        "tests/test_database_contracts.py",
        "tests/test_inventory_runtime.py",
        "tests/test_inventory_workflow.py",
        "tests/test_workflow_domain_checkpoints.py",
        "tests/test_post_execution_workflow.py",
        "tests/test_runtime_readers.py",
        "tests/test_verifier_recorder_integration.py",
        "tests/test_workflow_views.py",
        "tests/test_workflows.py",
    ),
    "dispatcher": (
        "tests/dispatcher/test_boundaries.py",
        "tests/dispatcher/test_custody.py",
        "tests/dispatcher/test_dispatcher.py",
        "tests/dispatcher/test_event_bus.py",
    ),
    "interfaces": (
        "tests/interfaces/test_ui_state.py",
        "tests/interfaces/test_launcher.py",
        "tests/interfaces/web/test_bridge.py",
        "tests/interfaces/web/test_bridge_event_benchmark.py",
        "tests/interfaces/web/test_bridge_transport_custody.py",
        "tests/interfaces/web/test_bridge_transport_custody_holdout.py",
        "tests/interfaces/web/test_bridge_transport_custody_live.py",
        "tests/interfaces/web/test_commands.py",
        "tests/interfaces/web/test_component_gallery_headed.py",
        "tests/interfaces/web/test_cosmetic_channel.py",
        "tests/interfaces/web/test_design_tokens.py",
        "tests/interfaces/web/test_document_channel.py",
        "tests/interfaces/web/test_drain.py",
        "tests/interfaces/web/test_browser_event_v5_consumers.py",
        "tests/interfaces/web/test_frontend_static.py",
        "tests/interfaces/web/test_headed_evidence.py",
        "tests/interfaces/web/test_headed_native.py",
        "tests/interfaces/web/test_host.py",
        "tests/interfaces/web/test_icons.py",
        "tests/interfaces/web/test_logging_config.py",
        "tests/interfaces/web/test_materials.py",
        "tests/interfaces/web/test_materials_headed.py",
        "tests/interfaces/web/test_motion.py",
        "tests/interfaces/web/test_native_host_gates.py",
        "tests/interfaces/web/test_paths.py",
        "tests/interfaces/web/test_readiness.py",
        "tests/interfaces/web/test_shell_headed.py",
        "tests/interfaces/web/test_single_instance.py",
        "tests/interfaces/web/test_slice1_headed.py",
        "tests/interfaces/web/test_slots.py",
        "tests/interfaces/web/test_transport.py",
        "tests/interfaces/web/test_transport_headed.py",
        "tests/interfaces/web/test_visible_sequence.py",
        "tests/interfaces/web/test_wheel_assets.py",
        "tests/test_bridge_service.py",
        "tests/test_cli.py",
        "tests/test_package.py",
        "tests/test_pywebview_runtime.py",
        "tests/test_result_classification.py",
        "tests/test_service.py",
        "tests/test_settings_facade.py",
        "tests/test_task_lifecycle.py",
        "tests/test_version.py",
        "tests/test_wheel_metadata.py",
    ),
    "tools": (
        "tests/test_department_policy.py",
        "tests/test_task_lifecycle_audit.py",
        "tests/test_tools_cli.py",
        "tests/test_tools_corpus.py",
        "tests/test_tools_executor.py",
        "tests/test_tools_executor_settlement_audit.py",
        "tests/test_tools_gui.py",
        "tests/test_tools_verifier.py",
    ),
}


class DepartmentManifestError(ValueError):
    """The executable ownership manifest is incomplete or inconsistent."""


def discover_test_modules(project_root: Path = PROJECT_ROOT) -> frozenset[str]:
    tests_root = project_root / "tests"
    return frozenset(
        path.relative_to(project_root).as_posix()
        for pattern in ("test_*.py", "*_test.py")
        for path in tests_root.rglob(pattern)
        if path.is_file()
    )


def validate_department_manifest(
    project_root: Path = PROJECT_ROOT,
    departments: Mapping[str, Sequence[str]] = DEPARTMENTS,
) -> dict[str, str]:
    ownership: dict[str, str] = {}
    problems: list[str] = []
    for department, modules in departments.items():
        if not modules:
            problems.append(f"department {department!r} owns no modules")
        for module in modules:
            normalized = Path(module).as_posix()
            if normalized != module or not module.startswith("tests/"):
                problems.append(
                    f"manifest path {module!r} is not normalized beneath tests/"
                )
                continue
            prior = ownership.get(module)
            if prior is not None:
                problems.append(
                    f"{module} is owned by both {prior!r} and {department!r}"
                )
                continue
            ownership[module] = department

    discovered = discover_test_modules(project_root)
    missing = sorted(set(ownership) - discovered)
    unowned = sorted(discovered - set(ownership))
    if missing:
        problems.append("missing manifest paths: " + ", ".join(missing))
    if unowned:
        problems.append("unowned test modules: " + ", ".join(unowned))
    if problems:
        raise DepartmentManifestError(
            "department manifest is invalid:\n- " + "\n- ".join(problems)
            + "\nUpdate tests/_departments.py so every collected test module has "
            "exactly one primary owner."
        )
    return ownership


def requested_departments(
    values: Iterable[str],
    departments: Mapping[str, Sequence[str]] = DEPARTMENTS,
) -> frozenset[str]:
    selected = frozenset(values)
    unknown = sorted(selected - set(departments))
    if unknown:
        raise DepartmentManifestError(
            "unknown department(s): "
            + ", ".join(unknown)
            + "; choose from: "
            + ", ".join(sorted(departments))
        )
    return selected


def modules_for_departments(
    selected: frozenset[str],
    ownership: Mapping[str, str],
) -> frozenset[str]:
    return frozenset(
        module for module, department in ownership.items() if department in selected
    )


def repository_module_path(path: Path, project_root: Path = PROJECT_ROOT) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()
