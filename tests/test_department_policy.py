from __future__ import annotations

import ast
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


def _collected_module_names(modules: frozenset[str]) -> frozenset[str]:
    names: set[str] = set()
    for module in modules:
        parts = Path(module).with_suffix("").parts
        names.add(".".join(parts))
        names.add(".".join(parts[1:]))
        names.add(parts[-1])
    return frozenset(names)


def _imported_collected_modules(
    source: str,
    collected_names: frozenset[str],
) -> tuple[tuple[int, str], ...]:
    found: set[tuple[int, str]] = set()
    for node in ast.walk(ast.parse(source)):
        candidates: list[str] = []
        if isinstance(node, ast.Import):
            candidates.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                candidates.append(node.module)
                candidates.extend(
                    f"{node.module}.{alias.name}" for alias in node.names
                )
            else:
                candidates.extend(alias.name for alias in node.names)
        found.update(
            (node.lineno, candidate)
            for candidate in candidates
            if candidate in collected_names
        )
    return tuple(sorted(found))


def _test_tree_import_offenders(project_root: Path) -> tuple[str, ...]:
    collected_names = _collected_module_names(
        discover_test_modules(project_root)
    )
    return tuple(
        f"{path.relative_to(project_root).as_posix()}:{line}: {target}"
        for path in sorted((project_root / "tests").rglob("*.py"))
        if path.is_file()
        for line, target in _imported_collected_modules(
            path.read_text(encoding="utf-8"),
            collected_names,
        )
    )


def test_department_manifest_owns_every_test_module_exactly_once() -> None:
    ownership = validate_department_manifest()

    assert frozenset(ownership) == discover_test_modules()
    assert frozenset(ownership.values()) == frozenset(DEPARTMENTS)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import test_owned\n", ("test_owned",)),
        ("from test_owned import helper\n", ("test_owned",)),
        (
            "from tests.area.test_owned import helper\n",
            ("tests.area.test_owned",),
        ),
        (
            "from tests.area import test_owned\n",
            ("tests.area.test_owned",),
        ),
        (
            "def load():\n    from . import test_owned\n",
            ("test_owned",),
        ),
        ("from _test_support import helper\n", ()),
        ("from package.test_helpers import helper\n", ()),
        ("note = 'import test_owned'\n", ()),
    ],
)
def test_collected_import_guard_recognizes_import_forms_without_false_positives(
    source: str,
    expected: tuple[str, ...],
) -> None:
    collected_names = _collected_module_names(
        frozenset({"tests/area/test_owned.py"})
    )

    imported = _imported_collected_modules(source, collected_names)

    assert tuple(target for _, target in imported) == expected


def test_test_tree_python_modules_do_not_import_collected_test_modules() -> None:
    assert _test_tree_import_offenders(PROJECT_ROOT) == ()


def test_collected_import_guard_scans_noncollected_support_modules(
    tmp_path: Path,
) -> None:
    _test_module(tmp_path, "tests/test_owned.py")
    support = tmp_path / "tests" / "_support.py"
    support.write_text("from test_owned import helper\n", encoding="utf-8")

    assert _test_tree_import_offenders(tmp_path) == (
        "tests/_support.py:1: test_owned",
    )


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


def test_department_manifest_owns_pytest_suffix_form_modules(
    tmp_path: Path,
) -> None:
    _test_module(tmp_path, "tests/owned_test.py")

    ownership = validate_department_manifest(
        tmp_path,
        {"owner": ("tests/owned_test.py",)},
    )

    assert ownership == {"tests/owned_test.py": "owner"}


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
    assert message.endswith(
        "Update tests/_departments.py so every collected test module has "
        "exactly one primary owner."
    )


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
