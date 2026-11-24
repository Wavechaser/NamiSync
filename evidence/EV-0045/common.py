"""Shared helpers for the independent migrator review (scratch only)."""

from __future__ import annotations

from contextlib import closing
import hashlib
import shutil
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "tests" / "assets" / "v0_1_0"
FILES = (
    "ledger.db", "ledger.db-wal", "ledger.db-shm",
    "history.db", "history.db-wal", "history.db-shm",
)


def fresh_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def copy_pair(directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copyfile(FIXTURE / name, directory / name)
    return directory / "ledger.db", directory / "history.db"


def snapshot_copy(main: Path, scratch: Path) -> Path:
    """Byte copy of main + -wal into scratch so reading never touches the source."""
    fresh_dir(scratch)
    copy = scratch / main.name
    for suffix in ("", "-wal"):
        source = Path(f"{main}{suffix}")
        if source.exists():
            shutil.copyfile(source, f"{copy}{suffix}")
    return copy


def user_tables(connection: sqlite3.Connection) -> list[str]:
    return [
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f"PRAGMA table_xinfo({table})")]


def pk_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    rows = sorted(
        (row[5], row[1]) for row in connection.execute(f"PRAGMA table_info({table})") if row[5]
    )
    return [name for _, name in rows]


def full_content(main: Path, scratch: Path, column_sets: dict[str, list[str]] | None = None):
    """{table: {pk: {column: (typeof, value)}}} for every column of every user table."""
    copy = snapshot_copy(main, scratch)
    result: dict[str, dict] = {}
    with closing(sqlite3.connect(copy.as_uri() + "?mode=ro", uri=True)) as connection:
        for table in user_tables(connection):
            columns = column_sets[table] if column_sets and table in column_sets else table_columns(connection, table)
            pk = pk_columns(connection, table) or ["rowid"]
            selected = ", ".join(f"typeof({c}), {c}" for c in columns)
            rows = {}
            for row in connection.execute(f"SELECT {', '.join(pk)}, {selected} FROM {table}"):
                key = tuple(row[: len(pk)])
                values = row[len(pk):]
                rows[key] = {
                    column: (values[2 * index], values[2 * index + 1])
                    for index, column in enumerate(columns)
                }
            result[table] = rows
    return result


def file_digests(*mains: Path) -> dict[str, str | None]:
    out = {}
    for main in mains:
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{main}{suffix}")
            out[path.name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    return out
