"""Read-only contract checks and coordinated creation for the database pair."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from namisync.db.contracts import (
    history_file_contract_matches,
    ledger_file_contract_matches,
)
from namisync.db.schema import (
    initialize_history,
    initialize_ledger,
)


DATABASE_RESET_DIRECTION = (
    "Close every NamiSync process, manually delete or otherwise reset both "
    "database files together, and restart NamiSync."
)
_SQLITE_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


class DatabasePairState(StrEnum):
    FRESH = "fresh"
    READY = "ready"
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class DatabasePairContract:
    state: DatabasePairState
    reason: str | None = None
    reset_direction: str | None = None


class DatabasePairInitializationError(RuntimeError):
    """A fresh pair could not be published and owned artifacts were retracted."""


class DatabasePairRefusedError(RuntimeError):
    """A mutating admission encountered a refused database pair."""

    def __init__(self, contract: DatabasePairContract) -> None:
        if contract.state is not DatabasePairState.REFUSED:
            raise ValueError("database refusal requires a refused pair contract")
        super().__init__(
            f"database pair refused ({contract.reason}). "
            f"{contract.reset_direction}"
        )
        self.contract = contract


def validate_database_pair(
    ledger_path: str | Path,
    history_path: str | Path,
) -> DatabasePairContract:
    """Classify both database roles without creating or changing an artifact."""

    ledger = Path(ledger_path).resolve()
    history = Path(history_path).resolve()
    if ledger == history:
        raise ValueError("ledger and history databases must use distinct paths")

    ledger_main = _entry_exists(ledger)
    history_main = _entry_exists(history)
    ledger_sidecars = any(_entry_exists(path) for path in _sidecars(ledger))
    history_sidecars = any(_entry_exists(path) for path in _sidecars(history))

    if not ledger_main and not history_main:
        if ledger_sidecars or history_sidecars:
            return _refused("inconsistent-pair")
        return DatabasePairContract(DatabasePairState.FRESH)
    if ledger_main != history_main:
        return _refused("inconsistent-pair")
    if not ledger.is_file() or not history.is_file():
        return _refused("inconsistent-pair")

    if not ledger_file_contract_matches(ledger):
        return _refused("ledger-contract")
    if not history_file_contract_matches(history):
        return _refused("history-contract")
    return DatabasePairContract(DatabasePairState.READY)


def initialize_database_pair(
    ledger_path: str | Path,
    history_path: str | Path,
) -> DatabasePairContract:
    """Publish a fresh ledger then history, retracting only owned files on error."""

    ledger = Path(ledger_path).resolve()
    history = Path(history_path).resolve()
    state = validate_database_pair(ledger, history)
    if state.state is not DatabasePairState.FRESH:
        return state

    owned: dict[Path, tuple[int, int]] = {}
    try:
        _reserve_database(ledger, owned)
        initialize_ledger(ledger)
        _require_owned(ledger, owned[ledger])
        _discard_reserved_sidecars(ledger, owned)

        _reserve_database(history, owned)
        initialize_history(history)
        _require_owned(history, owned[history])
        _discard_reserved_sidecars(history, owned)

        ready = validate_database_pair(ledger, history)
        if ready.state is not DatabasePairState.READY:
            raise RuntimeError("published database pair failed its contract check")
        return ready
    except Exception as error:
        cleanup_errors = _retract_owned(owned)
        suffix = "" if not cleanup_errors else "; cleanup was incomplete"
        raise DatabasePairInitializationError(
            f"coordinated database initialization failed{suffix}"
        ) from error


def ensure_database_pair(
    ledger_path: str | Path,
    history_path: str | Path,
) -> DatabasePairContract:
    """Require a ready pair before admitting work that can mutate both stores."""

    contract = validate_database_pair(ledger_path, history_path)
    if contract.state is DatabasePairState.FRESH:
        contract = initialize_database_pair(ledger_path, history_path)
    if contract.state is DatabasePairState.REFUSED:
        raise DatabasePairRefusedError(contract)
    return contract


def _reserve(path: Path, owned: dict[Path, tuple[int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb"):
        pass
    owned[path] = _identity(path)


def _reserve_database(
    main: Path,
    owned: dict[Path, tuple[int, int]],
) -> None:
    # Every path that cleanup may remove is exclusively reserved and identified
    # before SQLite runs. Absence-before/presence-after alone cannot establish
    # ownership when another process can race initialization.
    for artifact in (main, *_sidecars(main)):
        _reserve(artifact, owned)


def _require_owned(path: Path, expected: tuple[int, int]) -> None:
    if not _matches_identity(path, expected):
        raise OSError("database publication replaced its reserved file")


def _discard_reserved_sidecars(
    main: Path,
    owned: dict[Path, tuple[int, int]],
) -> None:
    for artifact in _sidecars(main):
        if not _entry_exists(artifact):
            continue
        expected = owned[artifact]
        if not _matches_identity(artifact, expected):
            raise OSError("database publication replaced a reserved sidecar")
        artifact.unlink()


def _retract_owned(owned: dict[Path, tuple[int, int]]) -> tuple[OSError, ...]:
    failures: list[OSError] = []
    for artifact, expected in reversed(tuple(owned.items())):
        if not _matches_identity(artifact, expected):
            continue
        try:
            artifact.unlink(missing_ok=True)
        except OSError as error:
            failures.append(error)
    return tuple(failures)


def _identity(path: Path) -> tuple[int, int]:
    stat = path.lstat()
    return stat.st_dev, stat.st_ino


def _matches_identity(path: Path, expected: tuple[int, int]) -> bool:
    try:
        return _identity(path) == expected
    except OSError:
        return False


def _sidecars(path: Path) -> tuple[Path, ...]:
    return tuple(Path(f"{path}{suffix}") for suffix in _SQLITE_SIDECAR_SUFFIXES)


def _entry_exists(path: Path) -> bool:
    return os.path.lexists(path)


def _refused(reason: str) -> DatabasePairContract:
    return DatabasePairContract(
        DatabasePairState.REFUSED,
        reason,
        DATABASE_RESET_DIRECTION,
    )
