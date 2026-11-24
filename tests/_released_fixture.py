"""Copies of the released v0.1.0 database pair for tests that open them.

SQLite never opens the tracked files under ``tests/assets/v0_1_0/``: every
helper copies a database together with its ``-wal`` and ``-shm`` first,
because the committed rows live in each database's ``-wal``.
"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import shutil
import sqlite3


RELEASED_FIXTURE = Path(__file__).parent / "assets" / "v0_1_0"
RELEASED_FILES = (
    "ledger.db", "ledger.db-wal", "ledger.db-shm",
    "history.db", "history.db-wal", "history.db-shm",
)


def copy_released_pair(directory: Path) -> tuple[Path, Path]:
    """Copy the released pair into ``directory``; return its ledger and history mains."""

    directory.mkdir(parents=True, exist_ok=True)
    for name in RELEASED_FILES:
        shutil.copyfile(RELEASED_FIXTURE / name, directory / name)
    return directory / "ledger.db", directory / "history.db"


def copy_released_role(directory: Path, *, history: bool, name: str | None = None) -> Path:
    """Copy one released database with its sidecars, optionally renamed."""

    source = "history.db" if history else "ledger.db"
    main = directory / (name or source)
    directory.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        shutil.copyfile(RELEASED_FIXTURE / f"{source}{suffix}", Path(f"{main}{suffix}"))
    return main


def released_columns(scratch: Path, *, history: bool) -> dict[str, tuple[str, ...]]:
    """Every released data table with its columns, from the fixture's own catalog.

    The released main file alone holds the complete schema, so a copy of it is
    read immutably. ``schema_metadata`` is excluded: migration rewrites it.
    """

    scratch.mkdir(parents=True)
    main = scratch / ("history.db" if history else "ledger.db")
    shutil.copyfile(RELEASED_FIXTURE / main.name, main)
    with closing(sqlite3.connect(main.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
        tables = [
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' AND name <> 'schema_metadata' ORDER BY rowid"
            )
        ]
        return {
            table: tuple(row[1] for row in connection.execute(f"PRAGMA table_xinfo({table})"))
            for table in tables
        }


def carried_rows(main: Path, scratch: Path, *, history: bool) -> dict[str, list[tuple]]:
    """Every released column of every released table, with each value's type.

    Columns come from the released catalog, not from the migrator's own copy
    lists, and each value is paired with its ``typeof()``, so equality before
    and after migration proves every row, id and value was kept unchanged.
    ``scratch`` must not exist yet.
    """

    columns_by_table = released_columns(scratch / "catalog", history=history)
    copy = scratch / main.name
    for suffix in ("", "-wal"):
        if Path(f"{main}{suffix}").exists():
            shutil.copyfile(f"{main}{suffix}", f"{copy}{suffix}")
    with closing(sqlite3.connect(copy.as_uri() + "?mode=ro", uri=True)) as connection:
        return {
            table: connection.execute(
                "SELECT "
                + ", ".join(f"{column}, typeof({column})" for column in columns)
                + f" FROM {table} ORDER BY "
                + ", ".join(str(2 * index + 1) for index in range(len(columns)))
            ).fetchall()
            for table, columns in columns_by_table.items()
        }
