"""No-write probes for published ledger and history role contracts."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
import hashlib
import os
import sqlite3
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from time import sleep
from typing import Callable, Iterator, TypeVar

from .schema import (
    DatabaseAdmissionError,
    SchemaResetRequired,
    validate_history_reader_contract,
    validate_ledger_reader_contract,
)
from .connections import (
    DEFAULT_BUSY_TIMEOUT_MS,
    connect_history_reader,
    connect_history_writer,
    connect_ledger_reader,
    connect_ledger_writer,
)


_ContractValidator = Callable[[sqlite3.Connection], None]
_ArtifactStamp = tuple[int, int, int, int, int]
_CONTENT_SUFFIXES = ("", "-wal", "-shm")
_ValidationResult = TypeVar("_ValidationResult")
DATABASE_BUSY_DIRECTION = (
    "Database files changed during validation. Wait for other database activity "
    "to settle, then retry."
)
DATABASE_UNAVAILABLE_DIRECTION = (
    "Database files could not be safely read. Check access permissions and the "
    "database files and sidecars; preserve them for inspection before retrying."
)


class DatabaseArtifactsChanged(OSError):
    """Observed artifact drift, rather than a schema or access failure."""


class DatabaseBusyError(DatabaseAdmissionError):
    """Cold validation exhausted its bounded artifact-drift retries."""


def retry_database_validation(operation: Callable[[], _ValidationResult]) -> _ValidationResult:
    """Retry a complete, effect-free validation; never retry failed cleanup."""

    for attempt in range(3):
        try:
            return operation()
        except DatabaseArtifactsChanged as error:
            if getattr(error, "__notes__", ()):
                raise DatabaseAdmissionError(DATABASE_UNAVAILABLE_DIRECTION) from error
            if attempt == 2:
                raise DatabaseBusyError(DATABASE_BUSY_DIRECTION) from error
            sleep(0.01)
    raise AssertionError("unreachable validation retry")


class DatabaseConnectionOwner:
    """Keep an admitted database open while its live SQLite users come and go."""

    def __init__(self, path: str | Path, *, history: bool) -> None:
        self.path = Path(path).resolve()
        self.history = history
        self._lock = RLock()
        require_database_file_contract(self.path, history=history)
        self._identity = self._main_identity()
        connect = connect_history_reader if history else connect_ledger_reader
        self._connection = connect(self.path)
        self._closed = False
        try:
            self.validate()
        except BaseException:
            self._connection.close()
            raise

    def _main_identity(self) -> tuple[int, int, int]:
        value = self.path.lstat()
        if not stat.S_ISREG(value.st_mode):
            raise DatabaseAdmissionError("owned database main is not a regular file")
        return value.st_dev, value.st_ino, value.st_mode

    def require_role(self, path: str | Path, *, history: bool) -> None:
        if Path(path).resolve() != self.path or history != self.history:
            raise ValueError("database owner does not match the requested path and role")

    def _validate_connection(self, connection: sqlite3.Connection) -> None:
        validator = (
            validate_history_reader_contract if self.history else
            validate_ledger_reader_contract
        )
        connection.execute("BEGIN")
        try:
            validator(connection)
        finally:
            connection.rollback()

    def validate(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("database connection owner is closed")
            try:
                _require_no_journal(self.path)
                if self._main_identity() != self._identity:
                    raise DatabaseAdmissionError("owned database main was replaced")
                self._validate_connection(self._connection)
                _require_no_journal(self.path)
                if self._main_identity() != self._identity:
                    raise DatabaseAdmissionError("owned database main was replaced")
            except SchemaResetRequired:
                raise
            except (OSError, sqlite3.Error) as error:
                raise DatabaseAdmissionError(DATABASE_UNAVAILABLE_DIRECTION) from error

    def _open(
        self, path: str | Path, *, readonly: bool, busy_timeout_ms: int,
    ) -> sqlite3.Connection:
        self.require_role(path, history=self.history)
        with self._lock:
            self.validate()
            connect = (
                (connect_history_reader if readonly else connect_history_writer)
                if self.history else
                (connect_ledger_reader if readonly else connect_ledger_writer)
            )
            connection = connect(self.path, busy_timeout_ms=busy_timeout_ms)
            try:
                self._validate_connection(connection)
            except BaseException:
                connection.close()
                raise
            return connection

    def open_reader(
        self, path: str | Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> sqlite3.Connection:
        return self._open(path, readonly=True, busy_timeout_ms=busy_timeout_ms)

    def open_writer(
        self, path: str | Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> sqlite3.Connection:
        return self._open(path, readonly=False, busy_timeout_ms=busy_timeout_ms)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True


@dataclass(frozen=True, slots=True)
class _ArtifactEvidence:
    stamp: _ArtifactStamp
    digest: bytes


@dataclass(frozen=True, slots=True)
class DatabaseFileEvidence:
    """Ephemeral preflight observations, not a lease over subsequent SQLite use."""

    path: Path
    artifacts: tuple[_ArtifactEvidence | None, ...]

    def unchanged(self) -> bool:
        try:
            self.require_unchanged()
        except OSError:
            return False
        return True

    def require_unchanged(self) -> None:
        if _snapshot_artifacts(self.path, expected=self.artifacts) != self.artifacts:
            raise DatabaseArtifactsChanged("database artifact contents changed during validation")


def _entry_stat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def database_artifacts_present(path: Path) -> bool:
    """Distinguish truly fresh paths without treating access errors as absence."""

    return any(
        _entry_stat(Path(f"{path}{suffix}")) is not None
        for suffix in (*_CONTENT_SUFFIXES, "-journal")
    )


def _require_no_journal(path: Path) -> None:
    if _entry_stat(Path(f"{path}-journal")) is not None:
        raise OSError("database journal presence requires explicit recovery")


def _stamp(value: os.stat_result) -> _ArtifactStamp:
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns)


@contextmanager
def _cleanup_on_exit(cleanup: Callable[[], None], failure_note: str) -> Iterator[None]:
    try:
        yield
    except BaseException as error:
        try:
            cleanup()
        except BaseException as cleanup_error:
            if isinstance(error, Exception) and not isinstance(cleanup_error, Exception):
                raise
            error.add_note(failure_note)
        raise
    else:
        cleanup()


def _read_artifact(
    path: Path, destination: Path | None = None, *, expected: _ArtifactEvidence | None = None,
) -> _ArtifactEvidence | None:
    observed = _entry_stat(path)
    if observed is None:
        if expected is not None:
            raise DatabaseArtifactsChanged("database artifact disappeared before reading")
        return None
    if not stat.S_ISREG(observed.st_mode):
        raise OSError("database artifact is not a regular file")
    stamp = _stamp(observed)
    if expected is not None and stamp != expected.stamp:
        raise DatabaseArtifactsChanged("database artifact changed before reading")
    digest = hashlib.sha256()
    try:
        source = path.open("rb", buffering=0)
    except FileNotFoundError as error:
        raise DatabaseArtifactsChanged("database artifact disappeared before opening") from error
    with _cleanup_on_exit(source.close, "database artifact reader close was incomplete"):
        if _stamp(os.fstat(source.fileno())) != stamp:
            raise DatabaseArtifactsChanged("database artifact changed before reading")
        output = None if destination is None else destination.open("xb")
        with (
            nullcontext() if output is None else
            _cleanup_on_exit(output.close, "private database snapshot writer close was incomplete")
        ):
            remaining = observed.st_size
            while remaining:
                chunk = source.read(min(remaining, 1_048_576))
                if not chunk:
                    raise DatabaseArtifactsChanged("database artifact shrank while reading")
                digest.update(chunk)
                if output is not None:
                    output.write(chunk)
                remaining -= len(chunk)
            if source.read(1) or _stamp(os.fstat(source.fileno())) != stamp:
                raise DatabaseArtifactsChanged("database artifact changed while reading")
    current = _entry_stat(path)
    if current is None or _stamp(current) != stamp:
        raise DatabaseArtifactsChanged("database artifact pathname changed while reading")
    return _ArtifactEvidence(stamp, digest.digest())


def _snapshot_artifacts(
    path: Path, *, expected: tuple[_ArtifactEvidence | None, ...] | None = None,
) -> tuple[_ArtifactEvidence | None, ...]:
    _require_no_journal(path)
    paths = tuple(Path(f"{path}{suffix}") for suffix in _CONTENT_SUFFIXES)
    evidence = tuple(
        None if expected is not None and expected[index] is None else
        _read_artifact(artifact, expected=None if expected is None else expected[index])
        for index, artifact in enumerate(paths)
    )
    if evidence[0] is None:
        raise OSError("database main file is missing")
    for artifact, recorded in zip(paths, evidence):
        current = _entry_stat(artifact)
        if (None if current is None else _stamp(current)) != (
            None if recorded is None else recorded.stamp
        ):
            raise DatabaseArtifactsChanged("database artifact membership changed while reading")
    _require_no_journal(path)
    return evidence


def ledger_file_contract_matches(path: str | Path) -> bool:
    """Return whether stable main/WAL evidence has the exact ledger contract."""

    return _file_contract_matches(path, validate_ledger_reader_contract)


def history_file_contract_matches(path: str | Path) -> bool:
    """Return whether stable main/WAL evidence has the exact history contract."""

    return _file_contract_matches(path, validate_history_reader_contract)


def _file_contract_matches(
    path: str | Path,
    validator: _ContractValidator,
) -> bool:
    try:
        _validate_file_contract(Path(path).resolve(), validator)
    except (OSError, sqlite3.Error, ValueError):
        return False
    return True


def require_database_file_contract(path: str | Path, *, history: bool) -> DatabaseFileEvidence:
    """Refuse unstable or incompatible artifacts before an ordinary SQLite open."""

    return retry_database_validation(lambda: probe_database_file_contract(path, history=history))


def probe_database_file_contract(path: str | Path, *, history: bool) -> DatabaseFileEvidence:
    """One cold attempt, so a pair can own retries including its final checks."""

    validator = validate_history_reader_contract if history else validate_ledger_reader_contract
    try:
        return _validate_file_contract(Path(path).resolve(), validator)
    except (DatabaseArtifactsChanged, DatabaseAdmissionError):
        raise
    except (OSError, sqlite3.Error, ValueError) as error:
        if (
            getattr(error, "sqlite_errorcode", 0) & 0xFF
        ) in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB):
            raise SchemaResetRequired(
                "The stable database is corrupt or is not a SQLite database. "
                "Close every NamiSync process, then archive or delete both database "
                "main files and all of their -wal, -shm, and -journal sidecars "
                "together before restarting."
            ) from error
        raise DatabaseAdmissionError(DATABASE_UNAVAILABLE_DIRECTION) from error


def _validate_file_contract(path: Path, validator: _ContractValidator) -> DatabaseFileEvidence:
    evidence = DatabaseFileEvidence(path, _snapshot_artifacts(path))
    try:
        _validate_observed_file(path, validator, evidence)
    except (sqlite3.Error, ValueError) as error:
        if getattr(error, "__notes__", ()):
            raise DatabaseAdmissionError(DATABASE_UNAVAILABLE_DIRECTION) from error
        evidence.require_unchanged()
        raise
    evidence.require_unchanged()
    return evidence


def _validate_observed_file(
    path: Path, validator: _ContractValidator, evidence: DatabaseFileEvidence,
) -> None:
    if all(artifact is None for artifact in evidence.artifacts[1:]):
        _require_no_journal(path)
        _validate_connection(path, validator, immutable=True)
    else:
        temporary = TemporaryDirectory(prefix="namisync-db-contract-", dir=path.parent)
        with _cleanup_on_exit(
            temporary.cleanup, f"private database snapshot cleanup was incomplete: {temporary.name}",
        ):
            snapshot = Path(temporary.name) / "database.db"
            # Source SHM is drift evidence only. SQLite builds its own private
            # index from the copied WAL, including when source SHM is absent.
            for suffix, expected in zip(("", "-wal"), evidence.artifacts):
                if expected is not None and _read_artifact(
                    Path(f"{path}{suffix}"), Path(f"{snapshot}{suffix}"), expected=expected,
                ) != expected:
                    raise DatabaseArtifactsChanged("database snapshot differs from observed evidence")
            _require_no_journal(path)
            _validate_connection(snapshot, validator, immutable=False)


def _validate_connection(path: Path, validator: _ContractValidator, *, immutable: bool) -> None:
    uri = path.as_uri() + ("?mode=ro&immutable=1" if immutable else "?mode=ro")
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    with _cleanup_on_exit(connection.close, "database validation connection close was incomplete"):
        connection.execute("PRAGMA query_only = ON")
        validator(connection)
