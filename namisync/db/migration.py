"""Forward migration of a NamiSync 0.1.0 database to the current schema.

One database at a time, under its held exclusive maintenance claim: prove
through the files that no other process has it open, hold SQLite's exclusive
locking mode, publish a verified backup, then rebuild the schema with the
shipped statements and copy every row in one transaction that is verified
before COMMIT. Any failure rolls back and leaves the old database.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import sqlite3
from typing import Callable, Mapping

from namisync.core.pathing import to_extended_length_path

from .claims import DatabaseClaim, DatabaseInUse, claim_path
from .connections import validate_database_path
from .schema import (
    HISTORY_SCHEMA_VERSION,
    LEDGER_SCHEMA_VERSION,
    RELEASED_HISTORY_SCHEMA_VERSION,
    RELEASED_LEDGER_SCHEMA_VERSION,
    DatabaseAdmissionError,
    _metadata_rows,
    _schema_statements,
    _validate_reader_contract,
    classify_database,
    ledger_instance_id as _stored_instance_id,
    new_instance_id,
)


_ASIDE_PREFIX = "_migration_old_"
_DELETE = 0x00010000
_FILE_SHARE_READ_WRITE_DELETE = 0x00000007
_OPEN_EXISTING = 3
_ERROR_SHARING_VIOLATION = 32
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


@dataclass(frozen=True, slots=True)
class MigrationStep:
    """Copy one source schema version's tables, column by column, into the current one."""

    role: str
    source_version: int
    target_version: int
    # Each source table with the columns copied unchanged, ids included.
    tables: tuple[tuple[str, tuple[str, ...]], ...]
    # A legacy step's own operations, given the instance id of the ledger the
    # database belongs to: ``transform`` runs after the copy, before the
    # triggers; ``verify`` checks its result before COMMIT.
    transform: Callable[[sqlite3.Connection, str | None], None] | None = None
    verify: Callable[[sqlite3.Connection, str | None], None] | None = None


_LEDGER_V4 = MigrationStep("ledger", RELEASED_LEDGER_SCHEMA_VERSION, LEDGER_SCHEMA_VERSION, (
    ("hosts", ("id", "host_key", "display_name", "first_seen_at", "last_seen_at")),
    ("volumes", (
        "id", "serial", "fs_type", "label", "device_id", "first_seen_at",
        "last_seen_at",
    )),
    ("locations", (
        "id", "volume_id", "volume_relative_path", "volume_relative_path_key",
        "created_at", "last_seen_at", "rebound_at",
    )),
    ("mappings", (
        "id", "source_location_id", "target_location_id", "created_at", "deleted_at",
    )),
    ("inventory", (
        "id", "location_id", "rel_path", "rel_path_key", "entry_kind", "presence",
        "observed_size", "observed_mtime_ns", "file_identity_volume_serial",
        "file_identity_file_index", "observed_nlink", "observed_attributes",
        "observed_created_ns", "hardlink_group", "last_observed_at",
        "observation_host_id", "scope_token", "content_algorithm", "content_digest",
        "content_size", "hash_provenance", "content_observed_at", "attested_kind",
        "attested_size", "attested_mtime_ns", "attested_file_identity_volume_serial",
        "attested_file_identity_file_index", "attested_nlink", "attested_attributes",
        "attested_created_ns", "last_verified_at", "verification_invalidated_at",
        "verification_invalidated_reason", "missing_since", "acknowledged_at",
        "reappeared_at", "unsupported_reason",
    )),
    ("runs", (
        "id", "run_token", "activity_kind", "host_id", "mapping_id",
        "source_location_id", "target_location_id", "plan_fingerprint",
        "selection_digest", "started_at", "ended_at", "filesystem_status",
        "recording_status", "start_payload_hash", "finish_payload_hash",
    )),
    ("operations", (
        "id", "run_id", "op_token", "kind", "source_rel_path", "target_rel_path",
        "outcome", "content_bytes", "trash_rel_path", "recorded_at", "payload_hash",
    )),
    ("mapping_correspondence", (
        "mapping_id", "source_inventory_id", "target_inventory_id",
        "source_identity_volume_serial", "source_identity_file_index",
        "target_identity_volume_serial", "target_identity_file_index", "last_seen_at",
        "run_token", "op_token",
    )),
    ("recording_commands", (
        "command_key", "command_kind", "payload_hash", "disposition", "recorded_at",
    )),
    ("annotations", (
        "id", "entity_kind", "entity_id", "key", "value", "created_at", "updated_at",
    )),
))


# v0.1.0 recorded no ledger on its runs: they take the instance id the pair
# upgrade passes, that of the ledger it migrated in the same call, or none.
def _stamp_v8_runs(connection: sqlite3.Connection, instance_id: str | None) -> None:
    if instance_id is not None:
        connection.execute("UPDATE history_runs SET ledger_instance_id = ?", (instance_id,))


def _verify_v8_stamps(connection: sqlite3.Connection, instance_id: str | None) -> None:
    if connection.execute(
        "SELECT count(*) FROM history_runs WHERE ledger_instance_id IS NOT ?", (instance_id,),
    ).fetchone()[0]:
        raise sqlite3.DatabaseError("migrated history run stamps do not match their ledger")


_HISTORY_V8 = MigrationStep("history", RELEASED_HISTORY_SCHEMA_VERSION, HISTORY_SCHEMA_VERSION, (
    ("history_runs", (
        "id", "run_token", "session_id", "activity_kind", "host_key", "subject_kind",
        "subject_id", "source_context", "target_context", "created_at", "started_at",
        "ended_at", "current_state", "current_phase", "last_committed_seq",
        "item_count", "duplicate_item_count", "rejected_event_count",
        "last_committed_at", "context_hash", "event_chain_hash",
        "prefix_projection_hash", "terminal_payload_hash", "succeeded_count",
        "skipped_count", "failed_count", "canceled_count", "deferred_count",
        "blocked_count", "filesystem_status", "recording_status", "audit_status",
        "disposition", "canceled", "bytes_done", "bytes_total",
        "recording_degraded_items", "recording_issues_json", "omitted_detail_count",
        "review_reason", "review_tree_kind", "review_population", "review_axis",
        "review_row_limit", "review_byte_limit", "error_type", "error_message",
    )),
    ("history_events", (
        "run_id", "event_seq", "event_at", "schema_version", "body_type",
        "event_disposition", "envelope_json", "payload_hash", "receipt_hash",
        "item_identity_hash", "item_payload_hash", "duplicate_of_seq",
        "rejection_reason", "item_order", "item_type", "phase", "item_id", "kind",
        "path", "result", "reason", "recording", "recording_reason",
        "recording_detail", "detail_omitted_count",
    )),
    ("history_phases", (
        "run_id", "phase_order", "phase", "status", "items_done", "items_total",
        "bytes_done", "bytes_total", "error",
    )),
), transform=_stamp_v8_runs, verify=_verify_v8_stamps)
# (role, source schema version) -> the step from it. Every version from the
# oldest supported source to the current one must have an entry (tested).
MIGRATION_STEPS: Mapping[tuple[str, int], MigrationStep] = {
    ("ledger", _LEDGER_V4.source_version): _LEDGER_V4,
    ("history", _HISTORY_V8.source_version): _HISTORY_V8,
}


class DatabaseMigrationFailed(DatabaseAdmissionError):
    """Migration rolled back or could not be confirmed; its backup is kept."""

    def __init__(self, message: str, path: Path, backup: Path | None) -> None:
        super().__init__(message)
        self.path = path
        self.backup = backup


class DatabaseBackupFailed(DatabaseAdmissionError):
    """No verified backup could be published, so nothing was migrated."""

    def __init__(self, message: str, path: Path) -> None:
        super().__init__(message)
        self.path = path


class _BackupVerificationFailed(Exception):
    """The page-for-page backup failed verification: the source is damaged."""


class _CommitUnconfirmed(Exception):
    """COMMIT itself failed, so the update may or may not be durable."""


@dataclass(frozen=True, slots=True)
class DatabaseMigration:
    """One database's outcome: what it migrated from, its backup, and a ledger's instance."""

    source_version: int | None
    backup: Path | None
    ledger_instance_id: str | None


def migrate_database(
    path: str | Path,
    *,
    history: bool,
    claim: DatabaseClaim,
    ledger_instance_id: str | None = None,
) -> DatabaseMigration:
    """Migrate one supported older database in place, or confirm it is current.

    ``claim`` must be this database's held exclusive maintenance claim. A
    ledger receives a new instance id. ``ledger_instance_id``, which the pair
    operation passes only for the ledger it migrated in the same call, reaches
    only a step's own operations: the v0.1.0 History step stamps every run with
    it, and with none leaves them unstamped so they never join a ledger they
    were not recorded with.
    """

    resolved = validate_database_path(path)
    if not claim.held or not claim.exclusive or claim.path != claim_path(resolved):
        raise ValueError("migration requires this database's held exclusive maintenance claim")
    require_no_open_handles(resolved)
    connection = _open_exclusive(resolved)
    try:
        version = classify_database(connection, history=history)
        if version == (HISTORY_SCHEMA_VERSION if history else LEDGER_SCHEMA_VERSION):
            # Already current: close as any ordinary last connection does.
            connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, False)
            return DatabaseMigration(
                None, None, None if history else _stored_instance_id(connection),
            )
        step = MIGRATION_STEPS[("history" if history else "ledger", version)]
        counts = _row_counts(connection, (table for table, _ in step.tables))
        try:
            backup = _publish_backup(connection, resolved, step, counts)
        except (_BackupVerificationFailed, OSError, sqlite3.Error) as error:
            verification = isinstance(error, _BackupVerificationFailed)
            if verification or (
                getattr(error, "sqlite_errorcode", 0) & 0xFF
            ) in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB):
                # The backup is a page-for-page copy, so it fails only for a
                # damaged source; space or permissions advice cannot help.
                detail = str(error) if verification else f"{type(error).__name__}: {error}"
                raise DatabaseBackupFailed(
                    f"The {step.role} database {resolved} failed SQLite's "
                    f"integrity check ({detail}) while "
                    "NamiSync was backing it up before updating it, so nothing "
                    "was changed. Keep the database files and their -wal and "
                    "-shm sidecars for inspection.",
                    resolved,
                ) from error
            raise DatabaseBackupFailed(
                f"NamiSync could not write a verified backup of the {step.role} "
                f"database {resolved} ({type(error).__name__}: {error}), so it "
                "changed nothing. Check write access to that folder and its free "
                "space (updating needs roughly three times the database's size "
                "beside it), then start NamiSync again.",
                resolved,
            ) from error
        instance_id = ledger_instance_id if history else new_instance_id()
        try:
            _migrate(connection, step, counts, history=history, instance_id=instance_id)
        except _CommitUnconfirmed as error:
            cause = error.__cause__
            raise DatabaseMigrationFailed(
                f"Updating the {step.role} database {resolved} could not be "
                f"confirmed: its final commit reported {type(cause).__name__}: "
                f"{cause}. It may already be updated; NamiSync checks the databases "
                f"again at the next start. Its backup is {backup}.",
                resolved,
                backup,
            ) from cause
        except Exception as error:
            raise DatabaseMigrationFailed(
                f"Updating the {step.role} database {resolved} failed and it was "
                f"left unchanged ({type(error).__name__}: {error}). Its backup is "
                f"{backup}. Close every other NamiSync window and command, then "
                "start NamiSync again; if this repeats, keep both files for "
                "inspection.",
                resolved,
                backup,
            ) from error
        # Closing now checkpoints the committed WAL into the main file and
        # removes it; v0.1.0's stale -shm is reinitialized by the next opener.
        connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, False)
        return DatabaseMigration(version, backup, None if history else instance_id)
    finally:
        connection.close()


def _in_use(path: Path) -> DatabaseInUse:
    return DatabaseInUse(
        f"Database {path} is open in another NamiSync process, possibly an "
        "earlier version, so it cannot be updated now. Close every other "
        "NamiSync window and command, then start this again.",
        path,
    )


_kernel32: ctypes.WinDLL | None = None


def _bindings() -> ctypes.WinDLL:
    global _kernel32
    if _kernel32 is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        _kernel32 = kernel32
    return _kernel32


def require_no_open_handles(path: str | Path) -> None:
    """Refuse while any other handle without delete sharing is open on the main.

    Every SQLite connection and a desktop's pinned database handle share read
    and write but not delete, so this open fails while either exists.
    """

    path = validate_database_path(path)
    handle = _bindings().CreateFileW(
        to_extended_length_path(str(path)), _DELETE,
        _FILE_SHARE_READ_WRITE_DELETE, None, _OPEN_EXISTING, 0, None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        error = ctypes.get_last_error()
        if error == _ERROR_SHARING_VIOLATION:
            raise _in_use(path)
        raise ctypes.WinError(error)
    if not _bindings().CloseHandle(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _open_exclusive(path: Path) -> sqlite3.Connection:
    """One connection holding SQLite's exclusive lock until it closes."""

    connection = sqlite3.connect(
        path.as_uri() + "?mode=rw", uri=True, timeout=0, isolation_level=None,
    )
    try:
        # Neither pragma can change inside a transaction. Foreign keys stay off
        # so renaming and dropping the old tables neither cascades nor fails;
        # foreign_key_check proves the copy before COMMIT.
        connection.execute("PRAGMA foreign_keys = OFF")
        # A refusal, a no-op or a rollback closes without folding the WAL into
        # the main file, so the files stay as found; success re-enables it.
        connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
        connection.execute("PRAGMA locking_mode = EXCLUSIVE")
        connection.execute("BEGIN EXCLUSIVE")
        connection.execute("COMMIT")
    except sqlite3.OperationalError as error:
        connection.close()
        if error.sqlite_errorcode & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            raise _in_use(path) from error
        raise
    except BaseException:
        connection.close()
        raise
    return connection


def _row_counts(connection: sqlite3.Connection, tables) -> dict[str, int]:
    return {
        table: int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def _publish_backup(
    connection: sqlite3.Connection, path: Path, step: MigrationStep, counts: dict[str, int],
) -> Path:
    """Copy, verify, flush and publish a backup that never replaces a file."""

    def verify(target: sqlite3.Connection) -> None:
        if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise _BackupVerificationFailed("the backup failed its integrity check")
        try:
            classified = classify_database(target, history=step.role == "history")
        except DatabaseAdmissionError as error:
            raise _BackupVerificationFailed(
                "the backup does not classify as its source"
            ) from error
        if classified != step.source_version:
            raise _BackupVerificationFailed("the backup does not classify as its source")
        if _row_counts(target, counts) != counts:
            raise _BackupVerificationFailed("the backup row counts differ from the source")

    def published() -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return path.with_name(f"{path.name}.backup-v{step.source_version}-{stamp}")

    return publish_verified_copy(
        connection,
        path.with_name(f"{path.name}.migration-{secrets.token_hex(8)}.tmp"),
        verify,
        published,
    )


def publish_verified_copy(
    source: sqlite3.Connection,
    temporary: Path,
    finish: Callable[[sqlite3.Connection], None],
    published: Callable[[], Path],
) -> Path:
    """Copy a database into a standalone file, verify, flush and publish it.

    Migration and maintenance publish every backup this way. ``temporary`` is
    created exclusively; ``finish`` runs on the copy once it is in rollback-
    journal mode and raises to refuse it; ``published`` names the final file
    after the flush. The rename never replaces a file, and a failure removes
    only the temporary this call created.
    """

    # Create it exclusively: a file already at this name is never reused, and
    # cleanup below removes only what this call created.
    os.close(os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    try:
        target = sqlite3.connect(
            temporary.as_uri() + "?mode=rw", uri=True, isolation_level=None,
        )
        try:
            source.backup(target)
            # A standalone file: the copied header still names WAL.
            if target.execute("PRAGMA journal_mode = DELETE").fetchone()[0] != "delete":
                raise sqlite3.OperationalError("backup kept its write-ahead log")
            finish(target)
        finally:
            target.close()
        with temporary.open("r+b") as written:
            os.fsync(written.fileno())
        backup = published()
        # Windows rename never replaces an existing file.
        os.rename(temporary, backup)
    except BaseException:
        for leftover in (temporary, Path(f"{temporary}-journal")):
            try:
                leftover.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return backup


def _migrate(
    connection: sqlite3.Connection,
    step: MigrationStep,
    counts: dict[str, int],
    *,
    history: bool,
    instance_id: str | None,
) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        _rename_aside(connection, step)
        _create_tables(connection, history)
        _copy_rows(connection, step)
        if step.transform is not None:
            step.transform(connection, instance_id)
        _drop_aside(connection, step)
        _create_triggers(connection, history)
        _write_metadata(connection, history, instance_id)
        _verify(connection, step, counts, history=history, instance_id=instance_id)
        try:
            _commit(connection)
        except Exception as error:
            raise _CommitUnconfirmed() from error
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _rename_aside(connection: sqlite3.Connection, step: MigrationStep) -> None:
    """Drop the old triggers and indexes, then move every old table aside."""

    for kind in ("trigger", "index"):
        names = [
            str(row[0]) for row in connection.execute(
                "SELECT name FROM main.sqlite_schema WHERE type = ? AND sql IS NOT NULL "
                "ORDER BY name",
                (kind,),
            )
        ]
        for name in names:
            connection.execute(f'DROP {kind.upper()} "{name}"')
    for table in ("schema_metadata", *(table for table, _ in step.tables)):
        connection.execute(f"ALTER TABLE {table} RENAME TO {_ASIDE_PREFIX}{table}")


def _create_tables(connection: sqlite3.Connection, history: bool) -> None:
    # Triggers come after the copy: the rows were admitted under the same
    # guards, and history's append guards would refuse events of finalized runs.
    for statement in _schema_statements(history):
        if not statement.startswith("CREATE TRIGGER"):
            connection.execute(statement)


def _copy_rows(connection: sqlite3.Connection, step: MigrationStep) -> None:
    for table, columns in step.tables:
        _copy_table(connection, table, columns)


def _copy_table(connection: sqlite3.Connection, table: str, columns: tuple[str, ...]) -> None:
    listed = ", ".join(columns)
    connection.execute(
        f"INSERT INTO {table}({listed}) SELECT {listed} FROM {_ASIDE_PREFIX}{table}"
    )


def _drop_aside(connection: sqlite3.Connection, step: MigrationStep) -> None:
    for table in ("schema_metadata", *(table for table, _ in step.tables)):
        connection.execute(f"DROP TABLE {_ASIDE_PREFIX}{table}")


def _create_triggers(connection: sqlite3.Connection, history: bool) -> None:
    for statement in _schema_statements(history):
        if statement.startswith("CREATE TRIGGER"):
            connection.execute(statement)


def _write_metadata(
    connection: sqlite3.Connection, history: bool, instance_id: str | None,
) -> None:
    connection.executemany(
        "INSERT INTO schema_metadata(key, value) VALUES (?, ?)",
        _metadata_rows(history, None if history else instance_id),
    )


def _verify(
    connection: sqlite3.Connection,
    step: MigrationStep,
    counts: dict[str, int],
    *,
    history: bool,
    instance_id: str | None,
) -> None:
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise sqlite3.DatabaseError("migrated database failed its integrity check")
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise sqlite3.DatabaseError("migrated database failed its foreign key check")
    # The full current reader contract: role, version, formats, instance id
    # and the exact topology of a freshly created database.
    _validate_reader_contract(connection, history=history)
    if _row_counts(connection, counts) != counts:
        raise sqlite3.DatabaseError("migrated row counts differ from the source")
    if step.verify is not None:
        step.verify(connection, instance_id)


def _commit(connection: sqlite3.Connection) -> None:
    connection.execute("COMMIT")
