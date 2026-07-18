from __future__ import annotations

from pathlib import Path


def test_production_ledger_mutation_sql_is_owned_by_recorder_or_schema() -> None:
    package = Path(__file__).parents[1] / "namisync"
    allowed = {
        package / "db" / "recorder.py",
        package / "db" / "schema.py",
        package / "db" / "history.py",
    }
    mutation_markers = (
        "INSERT INTO ",
        "UPDATE inventory",
        "UPDATE runs",
        "UPDATE mappings",
        "DELETE FROM inventory",
        "DELETE FROM mappings",
    )

    violations: list[str] = []
    for path in package.rglob("*.py"):
        if path in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        if any(marker in source for marker in mutation_markers):
            violations.append(str(path.relative_to(package.parent)))

    assert violations == []
