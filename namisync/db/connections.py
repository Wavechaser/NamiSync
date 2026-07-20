"""SQLite connection factories and local-database path guards."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterable


DEFAULT_BUSY_TIMEOUT_MS = 5_000


class DatabaseLocationError(ValueError):
    """A live database path overlaps user-managed data."""


def validate_database_path(
    path: str | Path, *, managed_roots: Iterable[str | Path] = ()
) -> Path:
    resolved = Path(path).resolve()
    for root in managed_roots:
        managed = Path(root).resolve()
        try:
            common = Path(os.path.commonpath((resolved, managed)))
        except ValueError:
            continue
        if common == managed:
            raise DatabaseLocationError(
                f"live database must be outside managed root: {managed}"
            )
    return resolved


def _configure(
    connection: sqlite3.Connection,
    *,
    busy_timeout_ms: int,
    readonly: bool,
) -> sqlite3.Connection:
    if busy_timeout_ms < 0:
        connection.close()
        raise ValueError("busy timeout cannot be negative")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    if readonly:
        connection.execute("PRAGMA query_only = ON")
    else:
        mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if str(mode).lower() != "wal":
            connection.close()
            raise sqlite3.OperationalError("SQLite refused WAL journal mode")
    return connection


def _connect_writer(
    path: str | Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
) -> sqlite3.Connection:
    connection = sqlite3.connect(
        Path(path),
        timeout=busy_timeout_ms / 1_000,
        isolation_level=None,
        check_same_thread=False,
    )
    return _configure(
        connection,
        busy_timeout_ms=busy_timeout_ms,
        readonly=False,
    )


def _connect_reader(
    path: str | Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    uri = resolved.as_uri() + "?mode=ro"
    connection = sqlite3.connect(
        uri,
        uri=True,
        timeout=busy_timeout_ms / 1_000,
        isolation_level=None,
        check_same_thread=False,
    )
    return _configure(
        connection,
        busy_timeout_ms=busy_timeout_ms,
        readonly=True,
    )


def connect_ledger_writer(
    path: str | Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
) -> sqlite3.Connection:
    return _connect_writer(path, busy_timeout_ms=busy_timeout_ms)


def connect_ledger_reader(
    path: str | Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
) -> sqlite3.Connection:
    return _connect_reader(path, busy_timeout_ms=busy_timeout_ms)


def connect_history_writer(
    path: str | Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
) -> sqlite3.Connection:
    return _connect_writer(path, busy_timeout_ms=busy_timeout_ms)


def connect_history_reader(
    path: str | Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
) -> sqlite3.Connection:
    return _connect_reader(path, busy_timeout_ms=busy_timeout_ms)
