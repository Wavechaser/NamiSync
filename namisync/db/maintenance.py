"""Check, backup, restore and backup rotation of one database.

Each operation runs under its database's held exclusive maintenance claim,
which refuses every NamiSync writer. A backup is a verified standalone copy
published beside the database; a ledger backup records its own cut. Restore
replaces a database only from a verified backup at the current schema: a
database that still backs up cleanly is backed up and overwritten in place in
one SQLite transaction, and any other is renamed aside and kept.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
from typing import Callable, TypeVar

from .claims import DatabaseClaim, DatabaseInUse, claim_path
from .connections import DEFAULT_BUSY_TIMEOUT_MS, validate_database_path
from .contracts import _validate_file_contract, retry_database_validation
from .migration import (
    DatabaseBackupFailed,
    _BackupVerificationFailed,
    publish_verified_copy,
    require_no_open_handles,
)
from .schema import (
    HISTORY_SCHEMA_VERSION,
    LEDGER_SCHEMA_VERSION,
    DatabaseAdmissionError,
    DatabaseNewerVersion,
    DatabaseRoleMismatch,
    LedgerIsBackup,
    SchemaResetRequired,
    _validate_reader_contract,
    classify_database,
    ledger_instance_id,
    new_instance_id,
)
from .timestamps import decode_utc, encode_utc


BACKUP_KEEP = 3
_PROBLEM_LINES = 20
# Pages per backup step into a live database. The destination's write
# transaction spans every step and commits only at the end, so the step size
# changes no outcome; between steps a lock refusal can abort the copy.
_COPY_PAGES = 1024
_SIDECARS = ("-wal", "-shm", "-journal")
_STAMP = "%Y%m%dT%H%M%S%f"
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_Result = TypeVar("_Result")


class DatabaseCheckState(StrEnum):
    OK = "ok"
    # Admitted and passing integrity_check, but foreign_key_check reports
    # rows: usable, backs up cleanly, so restore still overwrites it in place.
    FOREIGN_KEY_VIOLATIONS = "foreign-key-violations"
    MISSING = "missing"
    DAMAGED = "damaged"
    OLDER = "older"
    NEWER = "newer"
    WRONG_ROLE = "wrong-role"
    UNSUPPORTED = "unsupported"
    IS_BACKUP = "is-backup"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class DatabaseCheck:
    """One database's state and, when it is not usable, why."""

    role: str
    state: DatabaseCheckState
    problems: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BackupRotation:
    """Rotated backups removed, and each removal that failed with its error."""

    removed: tuple[Path, ...] = ()
    failures: tuple[tuple[Path, str], ...] = ()


@dataclass(frozen=True, slots=True)
class DatabaseRestore:
    """A completed restore: its source, how the replaced database was kept, its lineage."""

    role: str
    source: Path
    # The pre-restore backup ("backup"), the renamed database ("replaced"),
    # or None when no database was there.
    kept: Path | None
    kept_as: str | None
    # A ledger's new instance id, and the instance and cut of the backup.
    instance_id: str | None
    restored_instance_id: str | None
    cut_at: datetime | None


class DatabaseRestoreRefused(DatabaseAdmissionError):
    """Restore refused before changing anything; ``reason`` names why."""

    def __init__(self, reason: str, message: str, path: Path) -> None:
        super().__init__(message)
        self.reason = reason
        self.path = path


class DatabaseRestoreFailed(DatabaseAdmissionError):
    """Restore failed; ``unconfirmed`` when the database may already have changed.

    ``kept`` names a pre-restore backup or replaced set that this call left.
    """

    def __init__(
        self, message: str, path: Path, *, unconfirmed: bool, kept: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.path = path
        self.unconfirmed = unconfirmed
        self.kept = kept


class DatabaseRestoreInUse(DatabaseInUse):
    """The in-place copy met another lock holder; its pre-restore backup is ``kept``."""

    def __init__(self, message: str, path: Path, *, kept: Path | None) -> None:
        super().__init__(message, path)
        self.kept = kept


class _CopyBusy(Exception):
    """Another connection holds a lock the in-place copy needs."""


@dataclass(frozen=True, slots=True)
class _SourceFacts:
    counts: dict[str, int]
    lineage: tuple[tuple, ...]
    instance_id: str | None
    cut_at: datetime | None


def _role(history: bool) -> str:
    return "history" if history else "ledger"


def _require_claim(path: str | Path, claim: DatabaseClaim) -> Path:
    resolved = validate_database_path(path)
    if not claim.held or not claim.exclusive or claim.path != claim_path(resolved):
        raise ValueError("maintenance requires this database's held exclusive maintenance claim")
    return resolved


def _stamp(now: datetime) -> str:
    encode_utc(now)  # refuses a naive or non-UTC time
    return now.strftime(_STAMP) + "Z"


def _sidecar(path: Path, suffix: str) -> Path:
    return Path(f"{path}{suffix}")


def _exists(path: Path) -> bool:
    return os.path.lexists(path)


def _damage(error: BaseException) -> bool:
    return (getattr(error, "sqlite_errorcode", 0) & 0xFF) in (
        sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB,
    )


def _read_cold(path: Path, inspect: Callable[[sqlite3.Connection], _Result]) -> _Result:
    """Read a live database without writing it or its sidecars."""

    results: list[_Result] = []

    def validate(connection: sqlite3.Connection) -> None:
        results.clear()
        results.append(inspect(connection))

    retry_database_validation(lambda: _validate_file_contract(path, validate))
    return results[-1]


def _open_read_only(path: Path, *, immutable: bool = False) -> sqlite3.Connection:
    connection = sqlite3.connect(
        path.as_uri() + ("?mode=ro&immutable=1" if immutable else "?mode=ro"),
        uri=True, isolation_level=None, timeout=DEFAULT_BUSY_TIMEOUT_MS / 1_000,
    )
    try:
        connection.execute("PRAGMA query_only = ON")
    except BaseException:
        connection.close()
        raise
    return connection


def _tables(connection: sqlite3.Connection) -> tuple[str, ...]:
    return tuple(
        str(row[0]) for row in connection.execute(
            "SELECT name FROM main.sqlite_schema WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    )


def _row_counts(connection: sqlite3.Connection, tables) -> dict[str, int]:
    return {
        table: int(connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])
        for table in tables
    }


def _lineage(connection: sqlite3.Connection) -> tuple[tuple, ...]:
    return tuple(
        tuple(row) for row in connection.execute(
            "SELECT id, kind, instance_id, at FROM ledger_lineage ORDER BY id"
        )
    )


def _problems(connection: sqlite3.Connection) -> tuple[list[str], list[str]]:
    """integrity_check problems, then foreign key violations, 20 in all."""

    integrity = [
        str(row[0]) for row in connection.execute(
            f"PRAGMA integrity_check({_PROBLEM_LINES})"
        )
    ]
    if integrity == ["ok"]:
        integrity = []
    violations: list[str] = []
    remaining = _PROBLEM_LINES - len(integrity)
    if remaining > 0:
        # fetchmany(0) would return every row.
        cursor = connection.execute("PRAGMA foreign_key_check")
        for table, rowid, parent, _ in cursor.fetchmany(remaining):
            violations.append(f"foreign key violation: {table} row {rowid} references {parent}")
    return integrity, violations


# --- check -------------------------------------------------------------------


def check_database(path: str | Path, *, history: bool, claim: DatabaseClaim) -> DatabaseCheck:
    """Classify one database without writing it, then run SQLite's own checks.

    ``integrity_check`` and ``foreign_key_check`` run, bounded to the first 20
    problems, when the database is of this role at the current or the
    supported older version.
    """

    resolved = _require_claim(path, claim)
    role = _role(history)

    def result(state: DatabaseCheckState, *problems: str) -> DatabaseCheck:
        return DatabaseCheck(role, state, tuple(problems))

    try:
        if not _exists(resolved):
            stray = [
                f"{resolved.name}{suffix} is present without its database"
                for suffix in _SIDECARS if _exists(_sidecar(resolved, suffix))
            ]
            return result(DatabaseCheckState.MISSING, *stray)
        if _exists(_sidecar(resolved, "-journal")):
            return result(
                DatabaseCheckState.DAMAGED,
                f"{resolved.name}-journal is present beside the database; NamiSync "
                "databases never leave a rollback journal",
            )
        if not stat.S_ISREG(resolved.lstat().st_mode):
            return result(DatabaseCheckState.UNAVAILABLE, f"{resolved} is not a regular file")
    except OSError as error:
        return result(DatabaseCheckState.UNAVAILABLE, f"{type(error).__name__}: {error}")

    current = HISTORY_SCHEMA_VERSION if history else LEDGER_SCHEMA_VERSION

    def inspect(connection: sqlite3.Connection) -> tuple[int, list[str], list[str], bool]:
        version = classify_database(connection, history=history)
        integrity, violations = _problems(connection)
        is_backup = False
        if version == current:
            try:
                _validate_reader_contract(connection, history=history)
            except LedgerIsBackup:
                is_backup = True
        return version, integrity, violations, is_backup

    try:
        version, integrity, violations, is_backup = _read_cold(resolved, inspect)
    except DatabaseRoleMismatch as error:
        return result(DatabaseCheckState.WRONG_ROLE, str(error))
    except DatabaseNewerVersion as error:
        return result(DatabaseCheckState.NEWER, str(error))
    except SchemaResetRequired as error:
        return result(DatabaseCheckState.UNSUPPORTED, str(error))
    except (DatabaseAdmissionError, OSError, sqlite3.Error, ValueError) as error:
        if _damage(error):
            return result(DatabaseCheckState.DAMAGED, f"{type(error).__name__}: {error}")
        return result(DatabaseCheckState.UNAVAILABLE, f"{type(error).__name__}: {error}")
    if integrity:
        return result(DatabaseCheckState.DAMAGED, *integrity, *violations)
    if version != current:
        return result(DatabaseCheckState.OLDER, *violations)
    if is_backup:
        return result(
            DatabaseCheckState.IS_BACKUP,
            "the ledger is a NamiSync backup copied into place: its lineage records "
            "a backup of its own instance",
            *violations,
        )
    if violations:
        return result(DatabaseCheckState.FOREIGN_KEY_VIOLATIONS, *violations)
    return result(DatabaseCheckState.OK)


# --- backup ------------------------------------------------------------------


def _backup_failed(role: str, path: Path, error: BaseException) -> DatabaseBackupFailed:
    if isinstance(error, _BackupVerificationFailed) or _damage(error):
        # The backup is a page-for-page copy, so it fails only for a damaged
        # source; space or permissions advice cannot help.
        detail = (
            str(error) if isinstance(error, _BackupVerificationFailed)
            else f"{type(error).__name__}: {error}"
        )
        return DatabaseBackupFailed(
            f"The {role} database {path} failed SQLite's integrity check ({detail}) "
            "while NamiSync was backing it up, so no backup was written. Keep the "
            "database files and their -wal and -shm sidecars for inspection.",
            path,
        )
    return DatabaseBackupFailed(
        f"NamiSync could not write a verified backup of the {role} database {path} "
        f"({type(error).__name__}: {error}), so no backup was written. Check write "
        "access to that folder and its free space (a backup needs as much free "
        "space as the database), then try again.",
        path,
    )


def backup_database(
    path: str | Path, *, history: bool, claim: DatabaseClaim, now: datetime,
) -> Path:
    """Publish a verified backup beside a current database, named for ``now``.

    ``now`` must be read after both maintenance claims are held. A ledger
    backup's copy, and only the copy, gains a ``backup-cut`` row naming its
    own instance at ``now``, so it classifies as a ledger that is a backup.
    The source is read through a read-only connection; SQLite may create its
    usual ``-wal`` and ``-shm`` sidecars but never changes the main file.
    """

    resolved = _require_claim(path, claim)
    role = _role(history)
    name = resolved.with_name(f"{resolved.name}.backup-{_stamp(now)}")
    cut_at = encode_utc(now)
    try:
        source = _open_read_only(resolved)
    except sqlite3.Error as error:
        raise _backup_failed(role, resolved, error) from error
    try:
        try:
            # A backup in place, an older or unusable source refuses typed.
            _validate_reader_contract(source, history=history)
            counts = _row_counts(source, _tables(source))
            instance_id = None if history else ledger_instance_id(source)
            expected = dict(counts)
            if not history:
                expected["ledger_lineage"] += 1

            def finish(copy: sqlite3.Connection) -> None:
                if not history:
                    copy.execute(
                        "INSERT INTO ledger_lineage(kind, instance_id, at) "
                        "VALUES ('backup-cut', ?, ?)",
                        (ledger_instance_id(copy), cut_at),
                    )
                _verify_backup(copy, history=history, expected=expected,
                               instance_id=instance_id, cut_at=cut_at)

            return publish_verified_copy(
                source,
                resolved.with_name(f"{resolved.name}.backup-{secrets.token_hex(8)}.tmp"),
                finish,
                lambda: name,
            )
        except DatabaseAdmissionError:
            raise
        except (_BackupVerificationFailed, OSError, sqlite3.Error) as error:
            raise _backup_failed(role, resolved, error) from error
    finally:
        source.close()


def _verify_backup(
    copy: sqlite3.Connection,
    *,
    history: bool,
    expected: dict[str, int],
    instance_id: str | None,
    cut_at: str,
) -> None:
    if copy.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise _BackupVerificationFailed("the backup failed its integrity check")
    stamped = False
    try:
        _validate_reader_contract(copy, history=history)
    except LedgerIsBackup:
        # Expected: the backup's cut names its own instance.
        stamped = not history
    except DatabaseAdmissionError as error:
        raise _BackupVerificationFailed(
            "the backup does not classify as a current database of its role"
        ) from error
    if stamped == history:
        raise _BackupVerificationFailed("the backup does not record its own cut")
    if _row_counts(copy, expected) != expected or set(_tables(copy)) != set(expected):
        raise _BackupVerificationFailed("the backup row counts differ from the source")
    if not history and (
        ledger_instance_id(copy) != instance_id
        or copy.execute(
            "SELECT count(*) FROM ledger_lineage "
            "WHERE kind = 'backup-cut' AND instance_id = ? AND at = ?",
            (instance_id, cut_at),
        ).fetchone()[0] != 1
    ):
        raise _BackupVerificationFailed("the backup's cut does not name its own instance")


# --- rotation ----------------------------------------------------------------


def rotate_backups(
    path: str | Path, *, claim: DatabaseClaim, keep: int, protect: Path,
) -> BackupRotation:
    """Remove the oldest maintenance backups beyond ``keep``, always keeping ``protect``.

    ``claim`` must be this database's held exclusive maintenance claim. The
    population is regular files beside the database named exactly
    ``<main>.backup-<UTC stamp>Z`` in the maintenance backup's own format
    (ASCII digits only); migration backups, temporaries and replaced sets never
    match. ``protect`` is kept whatever its name, with the newest others by
    stamp. A failed removal is reported, never raised.
    """

    if keep < 1:
        raise ValueError("rotation keeps at least the new backup")
    resolved = _require_claim(path, claim)
    pattern = re.compile(re.escape(resolved.name) + r"\.backup-([0-9]{8}T[0-9]{12})Z")
    try:
        entries = list(os.scandir(resolved.parent))
    except OSError as error:
        return BackupRotation((), ((resolved.parent, f"{type(error).__name__}: {error}"),))
    others: list[tuple[str, Path]] = []
    for entry in entries:
        match = pattern.fullmatch(entry.name)
        if match is None or entry.name == protect.name:
            continue
        try:
            observed = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        if not stat.S_ISREG(observed.st_mode) or (
            getattr(observed, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
        ):
            continue
        others.append((match.group(1), resolved.parent / entry.name))
    others.sort(reverse=True)
    removed: list[Path] = []
    failures: list[tuple[Path, str]] = []
    for _, candidate in others[keep - 1:]:
        try:
            candidate.unlink()
        except OSError as error:
            failures.append((candidate, f"{type(error).__name__}: {error}"))
        else:
            removed.append(candidate)
    return BackupRotation(tuple(removed), tuple(failures))


# --- restore -----------------------------------------------------------------


def _refused(reason: str, message: str, path: Path) -> DatabaseRestoreRefused:
    return DatabaseRestoreRefused(reason, f"{message} Nothing was changed.", path)


def _validate_restore_source(source: Path, *, history: bool) -> _SourceFacts:
    role = _role(history)
    unavailable = (
        f"The backup {source} cannot be read as a standalone {role} backup file"
    )
    try:
        if not stat.S_ISREG(source.stat().st_mode):
            raise _refused("backup-unavailable", f"{unavailable}: it is not a file.", source)
        # A published backup stands alone. A -wal or -journal beside it means
        # it is open or not a backup, and its committed state is not the file.
        for suffix in ("-wal", "-journal"):
            if _exists(_sidecar(source, suffix)):
                raise _refused(
                    "backup-unavailable",
                    f"{unavailable}: {source.name}{suffix} is beside it. Use a backup "
                    "file NamiSync wrote, with nothing open on it.",
                    source,
                )
    except OSError as error:
        raise _refused(
            "backup-unavailable", f"{unavailable} ({type(error).__name__}: {error}).", source,
        ) from error
    try:
        connection = _open_read_only(source, immutable=True)
    except sqlite3.Error as error:
        raise _refused(
            "backup-unavailable", f"{unavailable} ({type(error).__name__}: {error}).", source,
        ) from error
    try:
        if connection.execute("PRAGMA integrity_check(1)").fetchall() != [("ok",)]:
            raise _refused(
                "backup-damaged",
                f"The backup {source} failed SQLite's integrity check, so it cannot be "
                "restored. Choose another backup.",
                source,
            )
        try:
            version = classify_database(connection, history=history)
        except DatabaseRoleMismatch as error:
            raise _refused(
                "backup-wrong-role",
                f"The backup {source} is not a {role} backup. Restore it as the "
                f"database of its own role, or choose a {role} backup.",
                source,
            ) from error
        except DatabaseNewerVersion as error:
            raise _refused(
                "backup-newer",
                f"The backup {source} was written by a newer NamiSync, so this version "
                "cannot restore it.",
                source,
            ) from error
        except SchemaResetRequired as error:
            raise _refused(
                "backup-unsupported",
                f"The backup {source} is not a {role} database this NamiSync can "
                "restore.",
                source,
            ) from error
        if version != (HISTORY_SCHEMA_VERSION if history else LEDGER_SCHEMA_VERSION):
            raise _refused(
                "backup-older",
                f"The backup {source} is a NamiSync 0.1.0 {role} kept by the update to "
                "this version. Restore takes only backups made by this version; that "
                "file is the way back to NamiSync 0.1.0.",
                source,
            )
        stamped = False
        try:
            _validate_reader_contract(connection, history=history)
        except LedgerIsBackup:
            stamped = True
        if not history and not stamped:
            raise _refused(
                "backup-unstamped",
                f"The ledger file {source} does not record the backup it is, so NamiSync "
                "cannot tell when it was made. Restore a backup NamiSync wrote.",
                source,
            )
        counts = _row_counts(connection, _tables(connection))
        if history:
            return _SourceFacts(counts, (), None, None)
        instance_id = ledger_instance_id(connection)
        row = connection.execute(
            "SELECT at FROM ledger_lineage WHERE kind = 'backup-cut' AND instance_id = ?",
            (instance_id,),
        ).fetchone()
        return _SourceFacts(counts, _lineage(connection), instance_id, decode_utc(row[0]))
    except DatabaseRestoreRefused:
        raise
    except (sqlite3.Error, ValueError) as error:
        if _damage(error):
            raise _refused(
                "backup-damaged",
                f"The backup {source} is damaged or is not a SQLite database "
                f"({type(error).__name__}: {error}). Choose another backup.",
                source,
            ) from error
        raise _refused(
            "backup-unavailable", f"{unavailable} ({type(error).__name__}: {error}).", source,
        ) from error
    finally:
        connection.close()


def _prepare_image(
    source: Path,
    image: Path,
    *,
    history: bool,
    facts: _SourceFacts,
    instance_id: str | None,
    write_ahead: bool,
) -> None:
    """Copy the backup into the image, give a ledger its new id, verify, flush."""

    reader = _open_read_only(source, immutable=True)
    try:
        copy = sqlite3.connect(image.as_uri() + "?mode=rw", uri=True, isolation_level=None)
        try:
            reader.backup(copy)
            if copy.execute("PRAGMA journal_mode = DELETE").fetchone()[0] != "delete":
                raise sqlite3.OperationalError("restore image kept a write-ahead log")
            if not history:
                copy.execute(
                    "UPDATE schema_metadata SET value = ? WHERE key = 'instance_id'",
                    (instance_id,),
                )
            _verify_image(copy, history=history, facts=facts, instance_id=instance_id)
        finally:
            copy.close()
    finally:
        reader.close()
    if write_ahead:
        # Published by rename, it must carry the WAL header like every NamiSync
        # main; closing the converting connection removes its -wal and -shm.
        copy = sqlite3.connect(image.as_uri() + "?mode=rw", uri=True, isolation_level=None)
        try:
            if copy.execute("PRAGMA journal_mode = WAL").fetchone()[0] != "wal":
                raise sqlite3.OperationalError("SQLite refused WAL journal mode")
        finally:
            copy.close()
        left = [suffix for suffix in _SIDECARS if _exists(_sidecar(image, suffix))]
        if left:
            raise OSError(f"restore image left {', '.join(left)} beside it")
    with image.open("r+b") as written:
        os.fsync(written.fileno())


def _verify_image(
    copy: sqlite3.Connection, *, history: bool, facts: _SourceFacts, instance_id: str | None,
) -> None:
    if copy.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise sqlite3.DatabaseError("restore image failed its integrity check")
    if copy.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise sqlite3.DatabaseError("restore image failed its foreign key check")
    # The full current reader contract; a ledger is no longer a backup.
    _validate_reader_contract(copy, history=history)
    if _row_counts(copy, facts.counts) != facts.counts or set(_tables(copy)) != set(facts.counts):
        raise sqlite3.DatabaseError("restore image row counts differ from the backup")
    if not history and (
        _lineage(copy) != facts.lineage
        or ledger_instance_id(copy) != instance_id
        or copy.execute(
            "SELECT count(*) FROM ledger_lineage WHERE instance_id = ?", (instance_id,),
        ).fetchone()[0]
    ):
        raise sqlite3.DatabaseError("restore image lineage differs from the backup")


def _copy_progress(status: int, remaining: int, total: int) -> None:
    # Called after every step, the final one included; a lock refusal aborts
    # the copy, which rolls the destination's transaction back.
    if status in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
        raise _CopyBusy()


def _copy_into_place(image: Path, path: Path) -> None:
    """Overwrite the live database with the image in one destination transaction.

    The SQLite backup API holds the destination's write lock from the first
    step and commits at the end; readers keep their snapshots meanwhile, and
    the destination keeps WAL mode, its file and its pinned handles.
    """

    reader = _open_read_only(image)
    try:
        destination = sqlite3.connect(
            path.as_uri() + "?mode=rw", uri=True, timeout=0, isolation_level=None,
        )
        try:
            reader.backup(destination, pages=_COPY_PAGES, progress=_copy_progress)
        finally:
            destination.close()
    finally:
        reader.close()


def _set_aside(path: Path, replaced: Path, moved: list[Path]) -> None:
    """Rename the database and its sidecars aside as one set, sidecars first.

    A sidecar keeps its suffix, so the kept main opens with its own WAL.
    """

    for suffix in _SIDECARS:
        sidecar = _sidecar(path, suffix)
        if _exists(sidecar):
            os.rename(sidecar, _sidecar(replaced, suffix))
            moved.append(_sidecar(replaced, suffix))
    os.rename(path, replaced)
    moved.append(replaced)


def _confirm(path: Path, *, history: bool) -> tuple[str | None, dict[str, int]]:
    """Read the published database cold: the contract, a ledger's id, row counts.

    History has no instance id, so its row counts are what tell the restored
    content from the database it replaced.
    """

    def inspect(connection: sqlite3.Connection) -> tuple[str | None, dict[str, int]]:
        _validate_reader_contract(connection, history=history)
        return (
            None if history else ledger_instance_id(connection),
            _row_counts(connection, _tables(connection)),
        )

    return _read_cold(path, inspect)


def _remove_created(image: Path) -> None:
    for leftover in (image, *(_sidecar(image, suffix) for suffix in _SIDECARS)):
        try:
            leftover.unlink(missing_ok=True)
        except OSError:
            pass


def restore_database(
    path: str | Path,
    backup: str | Path,
    *,
    history: bool,
    claim: DatabaseClaim,
    now: datetime,
) -> DatabaseRestore:
    """Replace one database with a verified image of a current-schema backup.

    ``now`` must be read after both maintenance claims are held. A ledger
    image gets a new instance id and keeps every lineage row of the backup.
    A database that checks as usable is backed up first and overwritten in
    place; one that fails admission is renamed aside with its sidecars, kept,
    once no other handle is open on it; a missing one is simply published.
    Refusals change nothing. A failure after the point of no return is
    reported as unconfirmed, never as unchanged.
    """

    resolved = _require_claim(path, claim)
    role = _role(history)
    stamp = _stamp(now)
    source = Path(os.path.abspath(backup))
    facts = _validate_restore_source(source, history=history)

    target = check_database(resolved, history=history, claim=claim)
    if target.state is DatabaseCheckState.WRONG_ROLE:
        raise _refused(
            "target-wrong-role",
            f"The {role} database path {resolved} holds a database of another role; "
            "the database paths look swapped. Check them, then restore again.",
            resolved,
        )
    if target.state is DatabaseCheckState.MISSING and target.problems:
        raise _refused(
            "target-inconsistent",
            f"The {role} database {resolved} is missing but its sidecars are present "
            f"({'; '.join(target.problems)}). Keep those files for inspection.",
            resolved,
        )
    if target.state is DatabaseCheckState.UNAVAILABLE:
        raise DatabaseRestoreFailed(
            f"The {role} database {resolved} could not be read "
            f"({'; '.join(target.problems)}), so nothing was restored. Check access to "
            "it, close other NamiSync windows and commands, then try again.",
            resolved, unconfirmed=False,
        )
    # A database that admission accepts and whose integrity_check passes still
    # backs up cleanly, so it is overwritten in place even with foreign key
    # violations; anything else is set aside.
    in_place = target.state in (
        DatabaseCheckState.OK, DatabaseCheckState.FOREIGN_KEY_VIOLATIONS,
    )
    missing = target.state is DatabaseCheckState.MISSING
    if not missing and not in_place:
        # Renaming needs every other handle closed; refuse before any write.
        require_no_open_handles(resolved)
    backup_kept: Path | None = None
    if in_place:
        # No backup, no change. Not followed by rotation, so a restore never
        # removes its own source.
        backup_kept = backup_database(resolved, history=history, claim=claim, now=now)
    kept, kept_as = backup_kept, ("backup" if in_place else None)

    instance_id = None if history else new_instance_id()
    image = resolved.with_name(f"{resolved.name}.restore-{secrets.token_hex(8)}.tmp")
    try:
        # Created exclusively: cleanup below removes only what this call made.
        os.close(os.open(image, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except OSError as error:
        raise _not_restored(role, resolved, source, backup_kept, error) from error
    try:
        try:
            _prepare_image(
                source, image, history=history, facts=facts,
                instance_id=instance_id, write_ahead=not in_place,
            )
        except (OSError, sqlite3.Error, ValueError) as error:
            raise _not_restored(role, resolved, source, backup_kept, error) from error
        if in_place:
            try:
                _copy_into_place(image, resolved)
            except _CopyBusy as error:
                raise DatabaseRestoreInUse(
                    f"Database {resolved} is in use by another process, so nothing was "
                    "restored. Close other NamiSync windows and commands, then try again."
                    f" A backup of the database was made first and is kept as {backup_kept}.",
                    resolved, kept=backup_kept,
                ) from error
            except Exception as error:
                # Any other failure, the final committed step's included, may
                # follow the commit.
                raise _unconfirmed(role, resolved, source, kept, error) from error
        elif missing:
            try:
                os.rename(image, resolved)
            except OSError as error:
                raise _not_restored(role, resolved, source, None, error) from error
        else:
            replaced = resolved.with_name(f"{resolved.name}.replaced-{stamp}")
            moved: list[Path] = []
            # Again right before the renames: a process that opened the
            # database while the image was prepared would split the set.
            require_no_open_handles(resolved)
            try:
                _set_aside(resolved, replaced, moved)
            except OSError as error:
                if not moved:
                    raise _not_restored(role, resolved, source, None, error) from error
                raise _unconfirmed(role, resolved, source, replaced, error) from error
            kept, kept_as = replaced, "replaced"
            try:
                os.rename(image, resolved)
            except OSError as error:
                raise _unconfirmed(role, resolved, source, kept, error) from error
        try:
            confirmed_id, confirmed_counts = _confirm(resolved, history=history)
        except (DatabaseAdmissionError, OSError, sqlite3.Error, ValueError) as error:
            raise _unconfirmed(role, resolved, source, kept, error) from error
        if confirmed_id != instance_id or confirmed_counts != facts.counts:
            raise _unconfirmed(
                role, resolved, source, kept,
                ValueError("the database read back is not the restored content"),
            )
    finally:
        _remove_created(image)
    return DatabaseRestore(
        role, source, kept, kept_as, instance_id, facts.instance_id, facts.cut_at,
    )


def _not_restored(
    role: str, path: Path, source: Path, backup: Path | None, error: BaseException,
) -> DatabaseRestoreFailed:
    made = "" if backup is None else (
        f" A backup of the database was made first and is kept as {backup}."
    )
    return DatabaseRestoreFailed(
        f"NamiSync could not restore the {role} database {path} from {source} "
        f"({type(error).__name__}: {error}), so nothing was restored. Check write "
        f"access to the database folder and its free space, then try again.{made}",
        path, unconfirmed=False, kept=backup,
    )


def _unconfirmed(
    role: str, path: Path, source: Path, kept: Path | None, error: BaseException,
) -> DatabaseRestoreFailed:
    keeping = "" if kept is None else f" The database it replaced is kept as {kept}."
    return DatabaseRestoreFailed(
        f"Restoring the {role} database {path} from {source} could not be confirmed "
        f"({type(error).__name__}: {error}). It may already be restored or only partly "
        f"moved; run check before using NamiSync, and keep every file beside it.{keeping}",
        path, unconfirmed=True, kept=kept,
    )
