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
from typing import Callable, Iterator

from .schema import (
    SchemaResetRequired,
    validate_history_reader_contract,
    validate_ledger_reader_contract,
)


_ContractValidator = Callable[[sqlite3.Connection], None]
_ArtifactStamp = tuple[int, int, int, int, int]
_CONTENT_SUFFIXES = ("", "-wal", "-shm")


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
            return _snapshot_artifacts(self.path, expected=self.artifacts) == self.artifacts
        except OSError:
            return False


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
        return None
    if not stat.S_ISREG(observed.st_mode):
        raise OSError("database artifact is not a regular file")
    stamp = _stamp(observed)
    if expected is not None and stamp != expected.stamp:
        raise OSError("database artifact changed before reading")
    digest = hashlib.sha256()
    source = path.open("rb", buffering=0)
    with _cleanup_on_exit(source.close, "database artifact reader close was incomplete"):
        if _stamp(os.fstat(source.fileno())) != stamp:
            raise OSError("database artifact changed before reading")
        output = None if destination is None else destination.open("xb")
        with (
            nullcontext() if output is None else
            _cleanup_on_exit(output.close, "private database snapshot writer close was incomplete")
        ):
            remaining = observed.st_size
            while remaining:
                chunk = source.read(min(remaining, 1_048_576))
                if not chunk:
                    raise OSError("database artifact shrank while reading")
                digest.update(chunk)
                if output is not None:
                    output.write(chunk)
                remaining -= len(chunk)
            if source.read(1) or _stamp(os.fstat(source.fileno())) != stamp:
                raise OSError("database artifact changed while reading")
    current = _entry_stat(path)
    if current is None or _stamp(current) != stamp:
        raise OSError("database artifact pathname changed while reading")
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
            raise OSError("database artifact membership changed while reading")
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

    validator = validate_history_reader_contract if history else validate_ledger_reader_contract
    try:
        return _validate_file_contract(Path(path).resolve(), validator)
    except SchemaResetRequired:
        raise
    except (OSError, sqlite3.Error, ValueError) as error:
        role = "history" if history else "ledger"
        raise SchemaResetRequired(
            f"cannot validate a stable {role} database contract. "
            "Close every NamiSync process, then archive or delete both database "
            "main files and all of their -wal, -shm, and -journal sidecars "
            "together before restarting."
        ) from error


def _validate_file_contract(path: Path, validator: _ContractValidator) -> DatabaseFileEvidence:
    evidence = DatabaseFileEvidence(path, _snapshot_artifacts(path))
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
                    raise OSError("database snapshot differs from observed evidence")
            _require_no_journal(path)
            _validate_connection(snapshot, validator, immutable=False)
    if not evidence.unchanged():
        raise OSError("database artifacts changed during contract validation")
    return evidence


def _validate_connection(path: Path, validator: _ContractValidator, *, immutable: bool) -> None:
    uri = path.as_uri() + ("?mode=ro&immutable=1" if immutable else "?mode=ro")
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    with _cleanup_on_exit(connection.close, "database validation connection close was incomplete"):
        connection.execute("PRAGMA query_only = ON")
        validator(connection)
