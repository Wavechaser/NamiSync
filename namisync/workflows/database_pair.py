"""Read-only contract checks and coordinated creation for the database pair."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import sqlite3
import stat

from namisync.db.claims import DatabaseClaimRefused, hold_maintenance_claims
from namisync.db.contracts import (
    DATABASE_UNAVAILABLE_DIRECTION,
    DatabaseArtifactsChanged,
    DatabaseBusyError,
    DatabaseConnectionOwner,
    DatabaseDamagedError,
    DatabaseFileEvidence,
    probe_database_file_contract,
    retry_database_validation,
)
from namisync.db.migration import (
    DatabaseBackupFailed,
    DatabaseMigration,
    DatabaseMigrationFailed,
    migrate_database,
    require_no_open_handles,
)
from namisync.db.schema import (
    DatabaseAdmissionError,
    DatabaseMigrationRequired,
    DatabaseNewerVersion,
    DatabaseRoleMismatch,
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
DATABASE_MIGRATION_DIRECTION = (
    "The database pair was written by NamiSync 0.1.0 and must be updated "
    "before use. Start NamiSync, or run a sync or inventory command, once to "
    "update it; a backup of each database is kept beside it."
)
_SQLITE_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")
_ARTIFACT_NATIVE: ArtifactNative = WindowsArtifactNative()


class DatabasePairState(StrEnum):
    FRESH = "fresh"
    READY = "ready"
    MIGRATION_REQUIRED = "migration-required"
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class DatabasePairContract:
    state: DatabasePairState
    reason: str | None = None
    reset_direction: str | None = None
    guidance: str | None = None


@dataclass(frozen=True, slots=True)
class MigratedDatabase:
    """One database this call migrated: its role, source version and backup."""

    role: str
    source_version: int
    backup: Path


@dataclass(frozen=True, slots=True)
class DatabasePairMigration:
    """A pair migration's resulting contract and the databases it migrated."""

    contract: DatabasePairContract
    migrated: tuple[MigratedDatabase, ...] = ()

    @property
    def backups(self) -> tuple[Path, ...]:
        return tuple(database.backup for database in self.migrated)


class DatabasePairInitializationError(RuntimeError):
    """A fresh pair could not be published and owned artifacts were retracted."""


class DatabasePairRefusedError(RuntimeError):
    """A mutating admission encountered a refused or not yet migrated pair."""

    def __init__(self, contract: DatabasePairContract) -> None:
        if contract.state not in (
            DatabasePairState.REFUSED, DatabasePairState.MIGRATION_REQUIRED,
        ):
            raise ValueError("database refusal requires a refused pair contract")
        super().__init__(
            f"database pair refused ({contract.reason}). "
            f"{contract.guidance or contract.reset_direction}"
        )
        self.contract = contract


def validate_database_pair(
    ledger_path: str | Path,
    history_path: str | Path,
    *,
    ledger_database: DatabaseConnectionOwner | None = None,
    history_database: DatabaseConnectionOwner | None = None,
) -> DatabasePairContract:
    """Classify cold files without writes, or validate supplied live owners."""

    ledger = Path(ledger_path).resolve()
    history = Path(history_path).resolve()
    if ledger == history:
        raise ValueError("ledger and history databases must use distinct paths")

    try:
        return retry_database_validation(lambda: _validate_database_pair_once(
            ledger, history, ledger_database=ledger_database, history_database=history_database,
        ))
    except DatabaseBusyError as error:
        return _refused("database-busy", guidance=str(error))
    except DatabaseDamagedError as error:
        return _refused("database-damaged", guidance=str(error))
    except (DatabaseAdmissionError, OSError):
        return _refused("database-unavailable")


def _validate_database_pair_once(
    ledger: Path, history: Path, *,
    ledger_database: DatabaseConnectionOwner | None,
    history_database: DatabaseConnectionOwner | None,
) -> DatabasePairContract:

    try:
        ledger_main = _entry_exists(ledger)
        history_main = _entry_exists(history)
        ledger_sidecars = any(_entry_exists(path) for path in _sidecars(ledger))
        history_sidecars = any(_entry_exists(path) for path in _sidecars(history))
        # Check both before either role can open SQLite, including an empty,
        # directory, or dangling-link journal entry.
        journals = any(_entry_exists(Path(f"{path}-journal")) for path in (ledger, history))
    except OSError:
        return _refused("database-unavailable")

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

    evidence: list[DatabaseFileEvidence] = []
    older: list[str] = []
    reset: tuple[str, Path, bool, DatabaseConnectionOwner | None] | None = None
    for role, path, is_history, database in (
        ("ledger", ledger, False, ledger_database),
        ("history", history, True, history_database),
    ):
        try:
            role_evidence = _validate_role(path, history=is_history, database=database)
        except SchemaResetRequired:
            # The reset direction covers both databases, so the other role is
            # classified first: a newer or misplaced one must not be discarded.
            reset = reset or (role, path, is_history, database)
            continue
        except DatabaseNewerVersion as error:
            return _refused(f"{role}-newer", guidance=str(error))
        except DatabaseRoleMismatch as error:
            return _refused(f"{role}-wrong-role", guidance=str(error))
        except DatabaseMigrationRequired:
            older.append(role)
            continue
        if role_evidence is not None:
            evidence.append(role_evidence)
    for role_evidence in evidence:
        role_evidence.require_unchanged()
    if reset is not None:
        # The verdict was reached before the other role was read, and it
        # advises discarding both, so it must still hold now.
        role, path, is_history, database = reset
        try:
            _validate_role(path, history=is_history, database=database)
        except SchemaResetRequired:
            return _refused(f"{role}-contract", reset=True)
        except (DatabaseMigrationRequired, DatabaseNewerVersion, DatabaseRoleMismatch):
            pass
        raise DatabaseArtifactsChanged(f"{role} database changed during validation")
    if older:
        return DatabasePairContract(
            DatabasePairState.MIGRATION_REQUIRED,
            f"{'pair' if len(older) == 2 else older[0]}-older",
            None,
            DATABASE_MIGRATION_DIRECTION,
        )
    return DatabasePairContract(DatabasePairState.READY)


def _validate_role(
    path: Path, *, history: bool, database: DatabaseConnectionOwner | None,
) -> DatabaseFileEvidence | None:
    if database is None:
        return probe_database_file_contract(path, history=history)
    database.require_role(path, history=history)
    database.validate()
    return None


def initialize_database_pair(
    ledger_path: str | Path,
    history_path: str | Path,
    *,
    ledger_database: DatabaseConnectionOwner | None = None,
    history_database: DatabaseConnectionOwner | None = None,
) -> DatabasePairContract:
    """Publish a fresh ledger then history, retracting only owned files on error."""

    ledger = Path(ledger_path).resolve()
    history = Path(history_path).resolve()
    state = validate_database_pair(
        ledger, history, ledger_database=ledger_database, history_database=history_database,
    )
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
    *,
    ledger_database: DatabaseConnectionOwner | None = None,
    history_database: DatabaseConnectionOwner | None = None,
) -> DatabasePairContract:
    """Require a ready pair before admitting work that can mutate both stores.

    A fresh pair is created. An older one is refused with the migration
    direction: only ``migrate_database_pair`` migrates, so every migration
    reaches a caller that reports it.
    """

    contract = validate_database_pair(
        ledger_path, history_path,
        ledger_database=ledger_database, history_database=history_database,
    )
    if contract.state is DatabasePairState.FRESH:
        contract = initialize_database_pair(ledger_path, history_path)
    if contract.state in (DatabasePairState.REFUSED, DatabasePairState.MIGRATION_REQUIRED):
        raise DatabasePairRefusedError(contract)
    return contract


def migrate_database_pair(
    ledger_path: str | Path, history_path: str | Path,
) -> DatabasePairMigration:
    """Migrate whichever roles of an older pair need it, ledger first.

    Both exclusive maintenance claims are held throughout, and the pair is
    classified again under them. Each database migrates in its own
    transaction, so a pair an interruption left half done finishes here. A
    refusal leaves both databases as they were, apart from a ledger that had
    already migrated.
    """

    ledger = Path(ledger_path).resolve()
    history = Path(history_path).resolve()
    migrated: list[MigratedDatabase] = []
    try:
        with hold_maintenance_claims(ledger, history) as claims:
            contract = validate_database_pair(ledger, history)
            if contract.state is not DatabasePairState.MIGRATION_REQUIRED:
                return DatabasePairMigration(contract)
            # Both files first, so a process holding only History cannot let
            # the ledger migrate and leave the pair half done.
            require_no_open_handles(ledger)
            require_no_open_handles(history)
            ledger_result = migrate_database(ledger, history=False, claim=claims.ledger)
            _record_migrated(migrated, "ledger", ledger_result)
            _record_migrated(migrated, "history", migrate_database(
                history, history=True, claim=claims.history,
                ledger_instance_id=ledger_result.ledger_instance_id,
            ))
            contract = validate_database_pair(ledger, history)
    except DatabaseClaimRefused as error:
        contract = _refused("database-in-use", guidance=str(error))
    except DatabaseBackupFailed as error:
        contract = _refused("backup-failed", guidance=str(error))
    except DatabaseMigrationFailed as error:
        contract = _refused("migration-failed", guidance=str(error))
    except (sqlite3.Error, OSError) as error:
        # Admission or access errors met under the claims; nothing was
        # migrated by the call that raised.
        contract = _refused("migration-unavailable", guidance=(
            f"{DATABASE_UNAVAILABLE_DIRECTION} ({type(error).__name__}: {error})"
        ))
    return DatabasePairMigration(contract, tuple(migrated))


def _record_migrated(
    migrated: list[MigratedDatabase], role: str, result: DatabaseMigration,
) -> None:
    if result.backup is not None and result.source_version is not None:
        migrated.append(MigratedDatabase(role, result.source_version, result.backup))


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


def _refused(
    reason: str, *, reset: bool = False, guidance: str = DATABASE_UNAVAILABLE_DIRECTION,
) -> DatabasePairContract:
    return DatabasePairContract(
        DatabasePairState.REFUSED,
        reason,
        DATABASE_RESET_DIRECTION if reset else None,
        DATABASE_RESET_DIRECTION if reset else guidance,
    )
