from __future__ import annotations

from pathlib import Path

import pytest

from _departments import (
    DEPARTMENTS,
    PROJECT_ROOT,
    DepartmentManifestError,
    discover_test_modules,
    modules_for_departments,
    repository_module_path,
    requested_departments,
    validate_department_manifest,
)


def _test_module(project_root: Path, relative: str) -> None:
    path = project_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def test_placeholder(): pass\n", encoding="utf-8")


def test_department_manifest_owns_every_test_module_exactly_once() -> None:
    ownership = validate_department_manifest()

    assert frozenset(ownership) == discover_test_modules()
    assert frozenset(ownership.values()) == frozenset(DEPARTMENTS)


def test_department_manifest_rejects_duplicate_ownership(tmp_path: Path) -> None:
    _test_module(tmp_path, "tests/test_owned.py")

    with pytest.raises(DepartmentManifestError, match="owned by both"):
        validate_department_manifest(
            tmp_path,
            {
                "first": ("tests/test_owned.py",),
                "second": ("tests/test_owned.py",),
            },
        )


def test_department_manifest_rejects_missing_and_unowned_modules(
    tmp_path: Path,
) -> None:
    _test_module(tmp_path, "tests/test_unowned.py")

    with pytest.raises(DepartmentManifestError) as raised:
        validate_department_manifest(
            tmp_path,
            {"owner": ("tests/test_missing.py",)},
        )

    message = str(raised.value)
    assert "missing manifest paths: tests/test_missing.py" in message
    assert "unowned test modules: tests/test_unowned.py" in message


def test_requested_departments_deduplicate_unions_and_reject_unknown() -> None:
    selected = requested_departments(("executor", "workflows", "executor"))
    ownership = {
        "tests/test_executor.py": "executor",
        "tests/test_workflow.py": "workflows",
        "tests/test_interface.py": "interfaces",
    }

    assert selected == frozenset({"executor", "workflows"})
    assert modules_for_departments(selected, ownership) == frozenset(
        {"tests/test_executor.py", "tests/test_workflow.py"}
    )
    with pytest.raises(DepartmentManifestError, match="unknown department"):
        requested_departments(("unknown",))


def test_repository_module_path_is_normalized_relative_to_project() -> None:
    path = PROJECT_ROOT / "tests" / "core" / "test_integrity.py"

    assert repository_module_path(path) == "tests/core/test_integrity.py"
