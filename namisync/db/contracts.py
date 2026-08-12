"""No-write probes for published ledger and history role contracts."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

from .schema import (
    validate_history_reader_contract,
    validate_ledger_reader_contract,
)


_ContractValidator = Callable[[sqlite3.Connection], None]


def ledger_file_contract_matches(path: str | Path) -> bool:
    """Return whether the durable main file has the exact ledger contract."""

    return _file_contract_matches(path, validate_ledger_reader_contract)


def history_file_contract_matches(path: str | Path) -> bool:
    """Return whether the durable main file has the exact history contract."""

    return _file_contract_matches(path, validate_history_reader_contract)


def _file_contract_matches(
    path: str | Path,
    validator: _ContractValidator,
) -> bool:
    connection: sqlite3.Connection | None = None
    try:
        # Schema version and contract metadata become immutable when a schema is
        # published. Reading the durable main file with SQLite's immutable mode
        # therefore avoids creating, recovering, checkpointing, or rewriting
        # WAL/SHM/journal state during this startup classification.
        uri = Path(path).resolve().as_uri() + "?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True, isolation_level=None)
        connection.execute("PRAGMA query_only = ON")
        validator(connection)
    except (OSError, sqlite3.Error, ValueError):
        return False
    finally:
        if connection is not None:
            connection.close()
    return True
