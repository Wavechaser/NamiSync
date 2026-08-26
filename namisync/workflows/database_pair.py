"""Read-only contract checks and coordinated creation for the database pair."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import stat

from namisync.db.contracts import (
    require_database_file_contract,
)
from namisync.db.schema import (
    SchemaResetRequired,
    _initialize_reserved_history,
    _initialize_reserved_ledger,
)
from namisync.workflows._database_pair_native import (
    ArtifactNative,
    OwnedArtifactLease,
    WindowsArtifactNative,
)


DATABASE_RESET_DIRECTION = (
    "Close every NamiSync process, then archive or delete both database main "
    "files and all of their -wal, -shm, and -journal sidecars together before "
    "restarting NamiSync."
)
_SQLITE_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")
_ARTIFACT_NATIVE: ArtifactNative = WindowsArtifactNative()


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

    try:
        ledger_main = _entry_exists(ledger)
        history_main = _entry_exists(history)
        ledger_sidecars = any(_entry_exists(path) for path in _sidecars(ledger))
        history_sidecars = any(_entry_exists(path) for path in _sidecars(history))
        # Check both before either role can open SQLite, including an empty,
        # directory, or dangling-link journal entry.
        journals = any(_entry_exists(Path(f"{path}-journal")) for path in (ledger, history))
    except OSError:
        return _refused("inconsistent-pair")

    if journals:
        return _refused("inconsistent-pair")
    if not ledger_main and not history_main:
        if ledger_sidecars or history_sidecars:
            return _refused("inconsistent-pair")
        return DatabasePairContract(DatabasePairState.FRESH)
    if ledger_main != history_main:
        return _refused("inconsistent-pair")
    if not ledger.is_file() or not history.is_file():
        return _refused("inconsistent-pair")

    try:
        ledger_evidence = require_database_file_contract(ledger, history=False)
    except SchemaResetRequired:
        return _refused("ledger-contract")
    try:
        history_evidence = require_database_file_contract(history, history=True)
    except SchemaResetRequired:
        return _refused("history-contract")
    if not ledger_evidence.unchanged():
        return _refused("ledger-contract")
    if not history_evidence.unchanged():
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

    owned: dict[Path, OwnedArtifactLease] = {}
    try:
        _reserve_database(ledger, owned)
        _require_empty_reservations(ledger, owned)
        _initialize_reserved_ledger(ledger)
        _require_owned(owned[ledger])
        _discard_reserved_sidecars(ledger, owned)

        _reserve_database(history, owned)
        _require_empty_reservations(history, owned)
        _initialize_reserved_history(history)
        _require_owned(owned[history])
        _discard_reserved_sidecars(history, owned)

        ready = validate_database_pair(ledger, history)
        if ready.state is not DatabasePairState.READY:
            raise RuntimeError("published database pair failed its contract check")
    except BaseException as error:
        try:
            cleanup_errors = _retract_owned(owned)
        except BaseException as cleanup_error:
            cleanup_errors = (cleanup_error,)
        cleanup_interrupt = next(
            (
                cleanup_error
                for cleanup_error in cleanup_errors
                if not isinstance(cleanup_error, Exception)
            ),
            None,
        )
        if cleanup_interrupt is not None and isinstance(error, Exception):
            cleanup_interrupt.add_note(
                "NamiSync database initialization cleanup was incomplete. "
                f"{DATABASE_RESET_DIRECTION}"
            )
            raise cleanup_interrupt
        if not isinstance(error, Exception):
            if cleanup_errors:
                error.add_note(
                    "NamiSync database initialization cleanup was incomplete. "
                    f"{DATABASE_RESET_DIRECTION}"
                )
            raise
        suffix = "" if not cleanup_errors else "; cleanup was incomplete"
        raise DatabasePairInitializationError(
            f"coordinated database initialization failed{suffix}"
        ) from error
    release_errors = _release_owned(owned)
    release_interrupt = next(
        (
            release_error
            for release_error in release_errors
            if not isinstance(release_error, Exception)
        ),
        None,
    )
    if release_interrupt is not None:
        release_interrupt.add_note(
            "NamiSync database initialization succeeded, but ownership-handle "
            "release was incomplete. Restart NamiSync before retrying."
        )
        raise release_interrupt
    if release_errors:
        raise DatabasePairInitializationError(
            "coordinated database initialization succeeded, but ownership-handle "
            "release was incomplete"
        )
    return ready


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


def _reserve(path: Path, owned: dict[Path, OwnedArtifactLease]) -> None:
    owned[path] = OwnedArtifactLease.reserve(path, _ARTIFACT_NATIVE)


def _reserve_database(
    main: Path,
    owned: dict[Path, OwnedArtifactLease],
) -> None:
    # Every path that cleanup may remove is exclusively reserved and identified
    # before SQLite runs. Absence-before/presence-after alone cannot establish
    # ownership when another process can race initialization.
    for artifact in (main, *_sidecars(main)):
        _reserve(artifact, owned)


def _require_empty_reservations(main: Path, owned: dict[Path, OwnedArtifactLease]) -> None:
    for artifact in (main, *_sidecars(main)):
        _require_owned(owned[artifact])
        entry = artifact.lstat()
        if not stat.S_ISREG(entry.st_mode) or entry.st_size != 0:
            raise OSError("database reservation is no longer an empty regular file")


def _require_owned(lease: OwnedArtifactLease) -> None:
    if not lease.matches_path():
        raise OSError("database publication replaced its reserved file")


def _discard_reserved_sidecars(
    main: Path,
    owned: dict[Path, OwnedArtifactLease],
) -> None:
    for artifact in _sidecars(main):
        lease = owned[artifact]
        if not _entry_exists(artifact):
            failures = lease.release()
            if failures:
                raise failures[0]
            del owned[artifact]
            continue
        _, failures = lease.retract()
        if failures:
            raise failures[0]
        if _entry_exists(artifact):
            raise OSError("database publication replaced a reserved sidecar")
        del owned[artifact]


def _retract_owned(
    owned: dict[Path, OwnedArtifactLease],
) -> tuple[BaseException, ...]:
    failures: list[BaseException] = []
    # Deletion authority is the lease's newly bound handle.  A pathname
    # identity precheck here would merely recreate the check/use race.
    for lease in reversed(tuple(owned.values())):
        try:
            deleted, lease_failures = lease.retract()
            failures.extend(lease_failures)
            if not deleted and not lease_failures:
                failures.append(
                    OSError(
                        "owned database artifact was displaced before cleanup"
                    )
                )
        except BaseException as error:
            failures.append(error)
    return tuple(failures)


def _release_owned(
    owned: dict[Path, OwnedArtifactLease],
) -> tuple[BaseException, ...]:
    failures: list[BaseException] = []
    for lease in reversed(tuple(owned.values())):
        try:
            failures.extend(lease.release())
        except BaseException as error:
            failures.append(error)
    return tuple(failures)


def _sidecars(path: Path) -> tuple[Path, ...]:
    return tuple(Path(f"{path}{suffix}") for suffix in _SQLITE_SIDECAR_SUFFIXES)


def _entry_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _refused(reason: str) -> DatabasePairContract:
    return DatabasePairContract(
        DatabasePairState.REFUSED,
        reason,
        DATABASE_RESET_DIRECTION,
    )
