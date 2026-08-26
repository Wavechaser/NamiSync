from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import traceback

import pytest

import namisync.db.contracts as file_contracts
import namisync.db.repositories as repositories_module
import namisync.db.schema as schema_module
import namisync.workflows.database_pair as database_pair
from namisync.db.connections import connect_history_writer, connect_ledger_writer
from namisync.db.history import HistoryRepository
from namisync.db.repositories import LedgerRepository
from namisync.db.schema import (
    HISTORY_CONTRACT_ID,
    LEDGER_CONTRACT_ID,
    SchemaResetRequired,
    initialize_history,
    initialize_ledger,
)
from namisync.interfaces.service import NamiSyncService
from namisync.workflows._database_pair_native import (
    OwnedArtifactLease,
    WindowsArtifactNative,
)
from namisync.workflows.database_pair import DatabasePairInitializationError


_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _artifacts(path: Path) -> tuple[Path, ...]:
    return (path, *(Path(f"{path}{suffix}") for suffix in _SIDECAR_SUFFIXES))


def _snapshot(*paths: Path) -> dict[Path, bytes]:
    return {
        artifact: artifact.read_bytes()
        for path in paths
        for artifact in _artifacts(path)
        if artifact.exists()
    }


def _service(tmp_path: Path) -> tuple[NamiSyncService, Path, Path]:
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    return NamiSyncService(ledger, history), ledger, history


def test_database_contract_preflight_is_read_only_for_fresh_pair(
    tmp_path: Path,
) -> None:
    root = tmp_path / "missing"
    ledger = root / "ledger.db"
    history = root / "history.db"
    service = NamiSyncService(ledger, history)

    first = service.validate_database_contracts()
    second = service.validate_database_contracts()

    assert first == second
    assert first.state == "fresh"
    assert first.reason is None
    assert first.reset_direction is None
    assert not root.exists()
    service.close()


@pytest.mark.parametrize("role", ("ledger", "history"))
@pytest.mark.parametrize("suffix", _SIDECAR_SUFFIXES)
def test_orphan_database_sidecar_refuses_without_mutation(
    tmp_path: Path,
    role: str,
    suffix: str,
) -> None:
    service, ledger, history = _service(tmp_path)
    path = ledger if role == "ledger" else history
    sidecar = Path(f"{path}{suffix}")
    sidecar.write_bytes(b"orphan-sidecar")
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "refused"
    assert result.reason == "inconsistent-pair"
    assert result.reset_direction is not None
    assert _snapshot(ledger, history) == before
    service.close()


@pytest.mark.parametrize("present_role", ("ledger", "history"))
def test_exactly_one_database_main_refuses_without_creating_peer(
    tmp_path: Path,
    present_role: str,
) -> None:
    service, ledger, history = _service(tmp_path)
    present = ledger if present_role == "ledger" else history
    missing = history if present_role == "ledger" else ledger
    present.write_bytes(b"existing-main")
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "refused"
    assert result.reason == "inconsistent-pair"
    assert result.reset_direction is not None
    assert _snapshot(ledger, history) == before
    assert not missing.exists()
    service.close()


def test_empty_database_pair_refuses_read_only(tmp_path: Path) -> None:
    service, ledger, history = _service(tmp_path)
    ledger.touch()
    history.touch()
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "refused"
    assert result.reason == "ledger-contract"
    assert result.reset_direction is not None
    assert _snapshot(ledger, history) == before
    service.close()


@pytest.mark.parametrize("wrong_role", ("ledger", "history"))
def test_wrong_role_contract_marker_refuses_read_only(
    tmp_path: Path,
    wrong_role: str,
) -> None:
    service, ledger, history = _service(tmp_path)
    initialize_ledger(ledger)
    initialize_history(history)
    changed = ledger if wrong_role == "ledger" else history
    with closing(sqlite3.connect(changed)) as connection:
        with connection:
            connection.execute(
                "UPDATE schema_metadata SET value = ? WHERE key = 'contract_id'",
                ("wrong-role-contract",),
            )
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "refused"
    assert result.reason == f"{wrong_role}-contract"
    assert result.reset_direction is not None
    assert _snapshot(ledger, history) == before
    service.close()


@pytest.mark.parametrize(
    ("role", "key", "old_value"),
    (
        ("ledger", "schema_version", "3"),
        ("history", "schema_version", "5"),
        ("ledger", "data_epoch", "4"),
        ("history", "data_epoch", "4"),
    ),
)
def test_old_or_mixed_database_epoch_refuses_without_mutation(
    tmp_path: Path,
    role: str,
    key: str,
    old_value: str,
) -> None:
    service, ledger, history = _service(tmp_path)
    initialize_ledger(ledger)
    initialize_history(history)
    selected = ledger if role == "ledger" else history
    with closing(sqlite3.connect(selected)) as connection:
        with connection:
            connection.execute(
                "UPDATE schema_metadata SET value = ? WHERE key = ?",
                (old_value, key),
            )
    before = _snapshot(ledger, history)

    first = service.validate_database_contracts()
    second = service.validate_database_contracts()

    assert first == second
    assert first.state == "refused"
    assert first.reason == f"{role}-contract"
    assert first.reset_direction is not None
    assert _snapshot(ledger, history) == before
    service.close()


def test_matching_database_pair_is_ready_and_read_only(tmp_path: Path) -> None:
    service, ledger, history = _service(tmp_path)
    initialize_ledger(ledger)
    initialize_history(history)
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "ready"
    assert result.reason is None
    assert result.reset_direction is None
    assert _snapshot(ledger, history) == before
    service.close()


@pytest.mark.parametrize("role", ["ledger", "history"])
@pytest.mark.parametrize("shape", ["marker-only", "poisoned-table", "missing-trigger", "extra-view"])
def test_current_markers_do_not_admit_or_repair_invalid_topology(
    tmp_path: Path, role: str, shape: str,
) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    selected = ledger if role == "ledger" else history
    initialize_other = initialize_history if role == "ledger" else initialize_ledger
    initialize_other(history if role == "ledger" else ledger)
    script = schema_module._LEDGER_SCHEMA if role == "ledger" else schema_module._HISTORY_SCHEMA
    if shape == "marker-only":
        first_table = "hosts" if role == "ledger" else "history_runs"
        script = script.split(f"CREATE TABLE IF NOT EXISTS {first_table}", 1)[0] + "COMMIT;"
    with closing(sqlite3.connect(selected)) as connection:
        connection.executescript(script)
        if shape == "poisoned-table":
            connection.execute("ALTER TABLE schema_metadata ADD COLUMN poison TEXT")
        elif shape == "missing-trigger":
            name = connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'trigger' LIMIT 1"
            ).fetchone()[0]
            connection.execute(f'DROP TRIGGER "{name}"')
        elif shape == "extra-view":
            connection.execute("CREATE VIEW poison AS SELECT * FROM schema_metadata")
        connection.commit()
    before = _snapshot(ledger, history)
    probe = file_contracts.ledger_file_contract_matches if role == "ledger" else file_contracts.history_file_contract_matches
    repository = LedgerRepository if role == "ledger" else HistoryRepository
    initialize = initialize_ledger if role == "ledger" else initialize_history

    assert not probe(selected)
    assert _snapshot(ledger, history) == before
    result = database_pair.validate_database_pair(ledger, history)
    assert result.state == "refused"
    assert result.reason == f"{role}-contract"
    for consumer in (repository, initialize):
        with pytest.raises(SchemaResetRequired, match="archive or delete both database main files"):
            consumer(selected)
        assert _snapshot(ledger, history) == before


def _entry_snapshot(*paths: Path) -> dict[Path, tuple[str, object]]:
    return {
        artifact: (
            ("link", os.readlink(artifact)) if artifact.is_symlink()
            else ("directory", tuple(artifact.iterdir())) if artifact.is_dir()
            else ("file", artifact.read_bytes())
        )
        for path in paths for artifact in _artifacts(path)
        if os.path.lexists(artifact)
    }


@pytest.mark.parametrize("role", ["ledger", "history"])
@pytest.mark.parametrize("kind", ["empty", "payload", "directory", "unfollowed-entry"])
def test_any_journal_entry_refuses_before_any_sqlite_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str, kind: str,
) -> None:
    ledger = initialize_ledger(tmp_path / "ledger.db")
    history = initialize_history(tmp_path / "history.db")
    selected = ledger if role == "ledger" else history
    journal = Path(f"{selected}-journal")
    if kind == "directory":
        journal.mkdir()
    else:
        journal.write_bytes(b"untrusted journal" if kind == "payload" else b"")
    if kind == "unfollowed-entry":
        # Pin lexical presence even when target-following existence says no,
        # without requiring Windows symbolic-link creation privileges.
        exists = Path.exists
        monkeypatch.setattr(Path, "exists", lambda path: False if path == journal else exists(path))
    before = _entry_snapshot(ledger, history)

    def unexpected(*args, **kwargs):
        pytest.fail("journal presence must refuse before opening either source role")

    monkeypatch.setattr(file_contracts.sqlite3, "connect", unexpected)
    assert database_pair.validate_database_pair(ledger, history).state == "refused"
    probe = file_contracts.ledger_file_contract_matches if role == "ledger" else file_contracts.history_file_contract_matches
    assert not probe(selected)
    for consumer in (
        LedgerRepository if role == "ledger" else HistoryRepository,
        initialize_ledger if role == "ledger" else initialize_history,
    ):
        with pytest.raises(SchemaResetRequired):
            consumer(selected)
    assert _entry_snapshot(ledger, history) == before


@pytest.mark.parametrize("role", ["ledger", "history"])
def test_fresh_pair_cannot_ignore_a_journal_seen_after_the_sidecar_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str,
) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    journal = Path(f"{ledger if role == 'ledger' else history}-journal")
    entry_exists = database_pair._entry_exists
    lookups = 0

    def journal_appears(path: Path) -> bool:
        nonlocal lookups
        if path == journal:
            lookups += 1
            if lookups == 2:
                journal.write_bytes(b"external journal")
        return entry_exists(path)

    def unexpected(*args, **kwargs):
        pytest.fail("an observed journal must refuse before any SQLite connection")

    monkeypatch.setattr(database_pair, "_entry_exists", journal_appears)
    monkeypatch.setattr(file_contracts.sqlite3, "connect", unexpected)

    result = database_pair.validate_database_pair(ledger, history)

    assert lookups == 2
    assert _snapshot(ledger, history) == {journal: b"external journal"}
    assert result.state == "refused"
    assert result.reason == "inconsistent-pair"


@pytest.mark.parametrize("role", ["ledger", "history"])
@pytest.mark.parametrize("include_shm", [False, True], ids=["missing-shm", "present-shm"])
@pytest.mark.parametrize("change", ["benign", "marker", "topology"])
def test_wal_contract_truth_is_checked_without_source_artifact_changes(
    tmp_path: Path, role: str, include_shm: bool, change: str,
) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    selected = ledger if role == "ledger" else history
    (initialize_history if role == "ledger" else initialize_ledger)(
        history if role == "ledger" else ledger
    )
    script = schema_module._LEDGER_SCHEMA if role == "ledger" else schema_module._HISTORY_SCHEMA
    producer = tmp_path / "producer.db"
    with closing(sqlite3.connect(producer, isolation_level=None)) as writer:
        writer.executescript(script)
        assert writer.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
        writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        writer.execute({
            "benign": "PRAGMA user_version = 99",
            "marker": "UPDATE schema_metadata SET value = 'wal-poison' WHERE key = 'contract_id'",
            "topology": "CREATE VIEW wal_poison AS SELECT * FROM schema_metadata",
        }[change])
        for suffix in ("", "-wal", "-shm") if include_shm else ("", "-wal"):
            Path(f"{selected}{suffix}").write_bytes(Path(f"{producer}{suffix}").read_bytes())
        assert Path(f"{selected}-wal").stat().st_size > 0
        before = _snapshot(ledger, history)
        probe = file_contracts.ledger_file_contract_matches if role == "ledger" else file_contracts.history_file_contract_matches
        assert probe(selected) is (change == "benign")
        assert _snapshot(ledger, history) == before
        result = database_pair.validate_database_pair(ledger, history)
        assert result.state == ("ready" if change == "benign" else "refused")
        assert _snapshot(ledger, history) == before
        initialize = initialize_ledger if role == "ledger" else initialize_history
        if change == "benign":
            assert initialize(selected) == selected
        else:
            for consumer in (initialize, LedgerRepository if role == "ledger" else HistoryRepository):
                with pytest.raises(SchemaResetRequired):
                    consumer(selected)
                assert _snapshot(ledger, history) == before
        assert _snapshot(ledger, history) == before


def _wal_candidate(tmp_path: Path, *, history: bool = False) -> Path:
    initialize = initialize_history if history else initialize_ledger
    connect = connect_history_writer if history else connect_ledger_writer
    producer = initialize(tmp_path / "producer.db")
    candidate = tmp_path / "candidate.db"
    with closing(connect(producer)) as writer:
        writer.execute("PRAGMA user_version = 99")
        for suffix in ("", "-wal", "-shm"):
            Path(f"{candidate}{suffix}").write_bytes(Path(f"{producer}{suffix}").read_bytes())
    assert Path(f"{candidate}-wal").stat().st_size > 0
    return candidate


@pytest.fixture
def private_snapshots(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    created: list[Path] = []
    temporary_directory = file_contracts.TemporaryDirectory

    def track_snapshot(*args, **kwargs):
        temporary = temporary_directory(*args, **kwargs)
        created.append(Path(temporary.name))
        return temporary

    monkeypatch.setattr(file_contracts, "TemporaryDirectory", track_snapshot)
    return created


@pytest.mark.parametrize("history_role", [False, True], ids=["ledger", "history"])
def test_private_snapshot_stays_beside_database_despite_ambient_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, private_snapshots: list[Path],
    history_role: bool,
) -> None:
    candidate = _wal_candidate(tmp_path, history=history_role)
    before = _snapshot(candidate)
    ambient = tmp_path / "ambient-temp"
    ambient.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(ambient))
    validate = file_contracts._validate_connection
    copied = []

    def inspect_private_copy(path: Path, validator, *, immutable: bool) -> None:
        assert not immutable
        assert path.read_bytes() == before[candidate]
        assert Path(f"{path}-wal").read_bytes() == before[Path(f"{candidate}-wal")]
        assert not Path(f"{path}-shm").exists()
        copied.append(path)
        validate(path, validator, immutable=immutable)

    monkeypatch.setattr(file_contracts, "_validate_connection", inspect_private_copy)
    evidence = file_contracts.require_database_file_contract(candidate, history=history_role)

    assert evidence.path == candidate
    assert len(private_snapshots) == 1
    directory = private_snapshots[0]
    assert directory.parent == candidate.parent
    assert directory.name.startswith("namisync-db-contract-")
    assert copied == [directory / "database.db"]
    assert not directory.exists()
    assert list(ambient.iterdir()) == []
    assert _snapshot(candidate) == before


@pytest.mark.parametrize("history_role", [False, True], ids=["ledger", "history"])
def test_immutable_database_validation_needs_no_private_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, history_role: bool,
) -> None:
    initialize = initialize_history if history_role else initialize_ledger
    candidate = initialize(tmp_path / "candidate.db")
    before = _snapshot(candidate)

    def forbidden_directory(*args, **kwargs):
        raise AssertionError("sidecar-free validation attempted scratch creation")

    monkeypatch.setattr(file_contracts, "TemporaryDirectory", forbidden_directory)
    evidence = file_contracts.require_database_file_contract(candidate, history=history_role)

    assert evidence.path == candidate
    assert _snapshot(candidate) == before


@pytest.mark.parametrize("suffix", ["", "-wal"], ids=["main", "wal"])
def test_snapshot_copy_refuses_changed_artifact_before_reading_or_copying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str,
) -> None:
    candidate = _wal_candidate(tmp_path)
    changed = Path(f"{candidate}{suffix}")
    capture = file_contracts._snapshot_artifacts
    open_path = Path.open
    raced = False
    changed_reads: list[Path] = []
    changed_copies: list[Path] = []
    after_external_change: dict[Path, bytes] = {}

    def capture_then_grow(path: Path, *args, **kwargs):
        nonlocal raced, after_external_change
        evidence = capture(path, *args, **kwargs)
        if not raced:
            changed.write_bytes(changed.read_bytes() + b"external growth")
            after_external_change = _snapshot(candidate)
            raced = True
        return evidence

    def track_open(path: Path, mode="r", *args, **kwargs):
        if raced and path == changed and mode == "rb":
            changed_reads.append(path)
        if mode == "xb" and path.name == f"database.db{suffix}":
            changed_copies.append(path)
        return open_path(path, mode, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(file_contracts, "_snapshot_artifacts", capture_then_grow)
        patch.setattr(Path, "open", track_open)
        assert not file_contracts.ledger_file_contract_matches(candidate)

    assert raced
    assert changed_reads == []
    assert changed_copies == []
    assert _snapshot(candidate) == after_external_change


@pytest.mark.parametrize("suffix", ["", "-wal", "-shm", "new-shm"])
def test_evidence_recheck_does_not_read_grown_or_new_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str,
) -> None:
    candidate = _wal_candidate(tmp_path)
    changed = Path(f"{candidate}{'-shm' if suffix == 'new-shm' else suffix}")
    if suffix == "new-shm":
        changed.unlink()
    evidence = file_contracts.require_database_file_contract(candidate, history=False)
    changed.write_bytes((changed.read_bytes() if changed.exists() else b"") + b"external growth")
    after_external_change = _snapshot(candidate)
    open_path = Path.open
    changed_reads: list[Path] = []

    def track_open(path: Path, mode="r", *args, **kwargs):
        if path == changed and mode == "rb":
            changed_reads.append(path)
        return open_path(path, mode, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", track_open)
        assert not evidence.unchanged()

    assert changed_reads == []
    assert _snapshot(candidate) == after_external_change


@pytest.mark.parametrize("consumer", ["probe", "repository", "initializer"])
@pytest.mark.parametrize("change", [
    "same-stamp-main", "same-stamp-shm", "replacement", "grow-wal", "shrink-wal",
    "remove-wal", "new-journal", "new-wal", "new-shm",
])
def test_admission_drift_refuses_with_only_the_external_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, private_snapshots: list[Path],
    consumer: str, change: str,
) -> None:
    direct = change in {"new-wal", "new-shm"}
    candidate = initialize_ledger(tmp_path / "candidate.db") if direct else _wal_candidate(tmp_path)
    validate = file_contracts._validate_connection
    after_external_change: dict[Path, bytes] = {}

    def validate_then_change(*args, **kwargs):
        nonlocal after_external_change
        validate(*args, **kwargs)
        if change.startswith("same-stamp"):
            changed = candidate if change.endswith("main") else Path(f"{candidate}-shm")
            stamp = changed.stat()
            content = changed.read_bytes()
            changed.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
            os.utime(changed, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            assert file_contracts._stamp(changed.stat()) == file_contracts._stamp(stamp)
        elif change == "replacement":
            stamp = candidate.stat()
            content = candidate.read_bytes()
            candidate.rename(tmp_path / "externally-displaced.db")
            candidate.write_bytes(content)
            os.utime(candidate, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            assert candidate.stat().st_ino != stamp.st_ino
        elif change in {"grow-wal", "shrink-wal", "remove-wal"}:
            wal = Path(f"{candidate}-wal")
            if change == "remove-wal":
                wal.unlink()
            else:
                content = wal.read_bytes()
                wal.write_bytes(content + b"external growth" if change == "grow-wal" else content[:-1])
        else:
            Path(f"{candidate}-{change.removeprefix('new-')}").write_bytes(b"external artifact")
        after_external_change = _snapshot(candidate)

    def ordinary_open_is_forbidden(*args, **kwargs):
        pytest.fail("drift must refuse before ordinary source SQLite use")

    monkeypatch.setattr(file_contracts, "_validate_connection", validate_then_change)
    monkeypatch.setattr(repositories_module, "connect_ledger_reader", ordinary_open_is_forbidden)
    monkeypatch.setattr(schema_module, "connect_ledger_writer", ordinary_open_is_forbidden)
    if consumer == "probe":
        assert not file_contracts.ledger_file_contract_matches(candidate)
    else:
        with pytest.raises(SchemaResetRequired):
            (LedgerRepository if consumer == "repository" else initialize_ledger)(candidate)

    assert after_external_change
    assert _snapshot(candidate) == after_external_change
    assert len(private_snapshots) == (0 if direct else 1)
    assert all(not path.exists() for path in private_snapshots)


def test_pair_rechecks_ledger_after_history_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = initialize_ledger(tmp_path / "ledger.db")
    history = initialize_history(tmp_path / "history.db")
    require = database_pair.require_database_file_contract
    after_external_change: dict[Path, bytes] = {}

    def require_then_change_peer(path: Path, *, history: bool):
        nonlocal after_external_change
        evidence = require(path, history=history)
        if history:
            Path(f"{ledger}-journal").write_bytes(b"external journal")
            after_external_change = _snapshot(ledger, path)
        return evidence

    monkeypatch.setattr(database_pair, "require_database_file_contract", require_then_change_peer)
    result = database_pair.validate_database_pair(ledger, history)

    assert result.state == "refused"
    assert result.reason == "ledger-contract"
    assert _snapshot(ledger, history) == after_external_change


def test_wal_probe_uses_private_sqlite_without_copying_source_shm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, private_snapshots: list[Path],
) -> None:
    candidate = _wal_candidate(tmp_path)
    Path(f"{candidate}-shm").write_bytes(b"source SHM is not recovery authority")
    before = _snapshot(candidate)
    connect = sqlite3.connect
    validate = file_contracts.validate_ledger_reader_contract
    opened: list[str] = []

    def private_connect(database, *args, **kwargs):
        if database != ":memory:":
            snapshot = private_snapshots[-1] / "database.db"
            assert database == snapshot.as_uri() + "?mode=ro"
            assert {path.name for path in snapshot.parent.iterdir()} == {"database.db", "database.db-wal"}
            assert snapshot.read_bytes() == before[candidate]
            assert Path(f"{snapshot}-wal").read_bytes() == before[Path(f"{candidate}-wal")]
            opened.append(database)
        return connect(database, *args, **kwargs)

    def validate_wal_truth(connection):
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        validate(connection)

    monkeypatch.setattr(file_contracts.sqlite3, "connect", private_connect)
    monkeypatch.setattr(file_contracts, "validate_ledger_reader_contract", validate_wal_truth)

    assert file_contracts.ledger_file_contract_matches(candidate)
    assert len(opened) == len(private_snapshots) == 1
    assert not private_snapshots[0].exists()
    assert _snapshot(candidate) == before


@pytest.mark.parametrize("stage", ["copy-open", "copy-read", "copy-write", "sqlite-open", "validation"])
@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt, SystemExit])
def test_snapshot_failure_closes_handles_cleans_private_files_and_preserves_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, private_snapshots: list[Path],
    stage: str, error_type,
) -> None:
    candidate = _wal_candidate(tmp_path)
    before = _snapshot(candidate)
    failure = error_type("injected snapshot failure")
    open_path = Path.open
    connect = sqlite3.connect
    validate = file_contracts.validate_ledger_reader_contract
    streams = []
    connections = []

    class TrackedConnection(sqlite3.Connection):
        closed = False

        def close(self):
            super().close()
            self.closed = True

    class FailingStream:
        def __init__(self, stream):
            self.stream = stream

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def read(self, _size=-1):
            raise failure

        def write(self, _chunk):
            raise failure

    def open_or_fail(path: Path, mode="r", *args, **kwargs):
        if stage == "copy-open" and mode == "xb" and path.name == "database.db-wal":
            raise failure
        stream = open_path(path, mode, *args, **kwargs)
        if path in _artifacts(candidate) and mode == "rb":
            streams.append(stream)
            if stage == "copy-read" and private_snapshots and path == Path(f"{candidate}-wal"):
                return FailingStream(stream)
        if stage == "copy-write" and mode == "xb" and path.name == "database.db-wal":
            streams.append(stream)
            return FailingStream(stream)
        return stream

    def connect_or_fail(database, *args, **kwargs):
        if database != ":memory:":
            if stage == "sqlite-open":
                raise failure
            connection = connect(database, *args, factory=TrackedConnection, **kwargs)
            connections.append(connection)
            return connection
        return connect(database, *args, **kwargs)

    def validate_or_fail(connection):
        if stage == "validation":
            raise failure
        validate(connection)

    monkeypatch.setattr(Path, "open", open_or_fail)
    monkeypatch.setattr(file_contracts.sqlite3, "connect", connect_or_fail)
    monkeypatch.setattr(file_contracts, "validate_ledger_reader_contract", validate_or_fail)
    with pytest.raises(SchemaResetRequired if error_type is OSError else error_type) as raised:
        file_contracts.require_database_file_contract(candidate, history=False)
    monkeypatch.setattr(Path, "open", open_path)

    assert (raised.value.__cause__ if error_type is OSError else raised.value) is failure
    assert streams and all(stream.closed for stream in streams)
    assert len(connections) == (1 if stage == "validation" else 0)
    assert all(connection.closed for connection in connections)
    assert len(private_snapshots) == 1
    assert not private_snapshots[0].exists()
    assert _snapshot(candidate) == before


@pytest.mark.parametrize("history_role", [False, True], ids=["ledger", "history"])
@pytest.mark.parametrize("primary_kind", ["none", "ordinary", "interrupt"])
@pytest.mark.parametrize("cleanup_kind", ["ordinary", "interrupt"])
def test_snapshot_cleanup_failure_preserves_error_and_control_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primary_kind: str, cleanup_kind: str,
    history_role: bool,
) -> None:
    candidate = _wal_candidate(tmp_path, history=history_role)
    before = _snapshot(candidate)
    primary = (
        None if primary_kind == "none" else OSError("validation failed")
        if primary_kind == "ordinary" else KeyboardInterrupt("validation interrupted")
    )
    cleanup_error = OSError("cleanup failed") if cleanup_kind == "ordinary" else SystemExit(23)
    temporary_directory = file_contracts.TemporaryDirectory
    validator_name = "validate_history_reader_contract" if history_role else "validate_ledger_reader_contract"
    validate = getattr(file_contracts, validator_name)
    owned = []

    def fail_cleanup():
        raise cleanup_error

    def temporary_with_failed_cleanup(*args, **kwargs):
        temporary = temporary_directory(*args, **kwargs)
        owned.append((Path(temporary.name), temporary.cleanup))
        monkeypatch.setattr(temporary, "cleanup", fail_cleanup)
        return temporary

    def validate_or_fail(connection):
        if primary is not None:
            raise primary
        validate(connection)

    monkeypatch.setattr(file_contracts, "TemporaryDirectory", temporary_with_failed_cleanup)
    monkeypatch.setattr(file_contracts, validator_name, validate_or_fail)
    expected = primary if primary is not None and (
        not isinstance(primary, Exception) or isinstance(cleanup_error, Exception)
    ) else cleanup_error
    try:
        with pytest.raises(SchemaResetRequired if isinstance(expected, Exception) else type(expected)) as raised:
            file_contracts.require_database_file_contract(candidate, history=history_role)
        assert (raised.value.__cause__ if isinstance(expected, Exception) else raised.value) is expected
        assert len(owned) == 1
        directory, _cleanup = owned[0]
        assert directory.is_dir()
        if primary is not None and expected is primary:
            assert primary.__notes__ == [f"private database snapshot cleanup was incomplete: {directory}"]
        assert _snapshot(candidate) == before
    finally:
        for _directory, cleanup in owned:
            cleanup()
    assert all(not directory.exists() for directory, _cleanup in owned)


@pytest.mark.parametrize("resource_kind", ["source", "destination", "sqlite", "cascade"])
@pytest.mark.parametrize("primary_kind", ["none", "ordinary", "interrupt"])
@pytest.mark.parametrize("cleanup_kind", ["ordinary", "interrupt"])
def test_snapshot_handle_close_preserves_error_and_control_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, private_snapshots: list[Path],
    resource_kind: str, primary_kind: str, cleanup_kind: str,
) -> None:
    candidate = _wal_candidate(tmp_path)
    before = _snapshot(candidate)
    primary = (
        None if primary_kind == "none" else OSError("primary failure")
        if primary_kind == "ordinary" else KeyboardInterrupt("primary interruption")
    )
    cleanup_error = OSError("close failed") if cleanup_kind == "ordinary" else SystemExit(23)
    open_path = Path.open
    connect = sqlite3.connect
    validate = file_contracts.validate_ledger_reader_contract
    create_temporary = file_contracts.TemporaryDirectory
    handles = []
    cleanup_calls: list[Path] = []

    def counted_temporary(*args, **kwargs):
        temporary = create_temporary(*args, **kwargs)
        cleanup = temporary.cleanup

        def counted_cleanup():
            cleanup_calls.append(Path(temporary.name))
            cleanup()

        monkeypatch.setattr(temporary, "cleanup", counted_cleanup)
        return temporary

    class Handle:
        def __init__(self, resource, *, fail_close: bool):
            self.resource = resource
            self.fail_close = fail_close
            self.closed = False
            self.close_calls = 0
            handles.append(self)

        def __getattr__(self, name):
            return getattr(self.resource, name)

        def read(self, size=-1):
            if primary is not None:
                raise primary
            return self.resource.read(size)

        def close(self):
            self.close_calls += 1
            self.resource.close()
            self.closed = True
            if self.fail_close:
                raise cleanup_error

    def wrap_copy_handle(path: Path, mode="r", *args, **kwargs):
        stream = open_path(path, mode, *args, **kwargs)
        if resource_kind != "sqlite" and private_snapshots:
            if path == Path(f"{candidate}-wal") and mode == "rb":
                return Handle(stream, fail_close=resource_kind in {"source", "cascade"})
            if path.name == "database.db-wal" and mode == "xb":
                return Handle(stream, fail_close=resource_kind in {"destination", "cascade"})
        return stream

    def wrap_sqlite_handle(database, *args, **kwargs):
        connection = connect(database, *args, **kwargs)
        return Handle(connection, fail_close=True) if resource_kind == "sqlite" and database != ":memory:" else connection

    def validate_or_fail(connection):
        if resource_kind == "sqlite" and primary is not None:
            raise primary
        validate(connection)

    monkeypatch.setattr(Path, "open", wrap_copy_handle)
    monkeypatch.setattr(file_contracts.sqlite3, "connect", wrap_sqlite_handle)
    monkeypatch.setattr(file_contracts, "validate_ledger_reader_contract", validate_or_fail)
    monkeypatch.setattr(file_contracts, "TemporaryDirectory", counted_temporary)
    expected = primary if primary is not None and (
        not isinstance(primary, Exception) or isinstance(cleanup_error, Exception)
    ) else cleanup_error
    with pytest.raises(SchemaResetRequired if isinstance(expected, Exception) else type(expected)) as raised:
        file_contracts.require_database_file_contract(candidate, history=False)
    monkeypatch.setattr(Path, "open", open_path)

    assert (raised.value.__cause__ if isinstance(expected, Exception) else raised.value) is expected
    if primary is not None and expected is primary:
        assert primary.__notes__ == {
            "source": ["database artifact reader close was incomplete"],
            "destination": ["private database snapshot writer close was incomplete"],
            "sqlite": ["database validation connection close was incomplete"],
            "cascade": [
                "private database snapshot writer close was incomplete",
                "database artifact reader close was incomplete",
            ],
        }[resource_kind]
    assert handles and all(handle.closed and handle.close_calls == 1 for handle in handles)
    assert len(private_snapshots) == 1
    assert cleanup_calls == private_snapshots
    assert not private_snapshots[0].exists()
    assert _snapshot(candidate) == before


@pytest.mark.parametrize("history_role", [False, True], ids=["ledger", "history"])
def test_snapshot_directory_creation_failure_leaves_source_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, history_role: bool,
) -> None:
    candidate = _wal_candidate(tmp_path, history=history_role)
    before = _snapshot(candidate)
    failure = OSError("cannot create private snapshot")
    create_temporary = file_contracts.TemporaryDirectory
    attempts = []

    def unavailable(*args, **kwargs):
        attempts.append((args, kwargs))
        if len(attempts) == 1:
            raise failure
        return create_temporary(*args, **kwargs)

    monkeypatch.setattr(file_contracts, "TemporaryDirectory", unavailable)
    with pytest.raises(SchemaResetRequired) as raised:
        file_contracts.require_database_file_contract(candidate, history=history_role)

    assert raised.value.__cause__ is failure
    assert attempts == [((), {"prefix": "namisync-db-contract-", "dir": candidate.parent})]
    assert _snapshot(candidate) == before


@pytest.mark.parametrize("history_role", [False, True], ids=["ledger", "history"])
@pytest.mark.parametrize("with_wal", [False, True], ids=["immutable", "wal"])
def test_valid_existing_initializer_never_uses_an_ordinary_source_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, history_role: bool, with_wal: bool,
) -> None:
    initialize = initialize_history if history_role else initialize_ledger
    candidate = (
        _wal_candidate(tmp_path, history=history_role) if with_wal
        else initialize(tmp_path / "candidate.db")
    )
    before = _snapshot(candidate)
    connect = sqlite3.connect
    opened = []

    def no_ordinary_source(database, *args, **kwargs):
        assert database not in {candidate, str(candidate), candidate.as_uri() + "?mode=ro"}
        if database != ":memory:":
            opened.append(database)
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(file_contracts.sqlite3, "connect", no_ordinary_source)

    assert initialize(candidate) == candidate
    assert len(opened) == 1
    if not with_wal:
        assert opened == [candidate.as_uri() + "?mode=ro&immutable=1"]
    assert _snapshot(candidate) == before


@pytest.mark.parametrize("history_role", [False, True], ids=["ledger", "history"])
@pytest.mark.parametrize("suffix", ["", "-wal", "-shm", "-journal"])
def test_public_initializer_refuses_preexisting_empty_or_orphan_artifacts(
    tmp_path: Path, history_role: bool, suffix: str,
) -> None:
    candidate = tmp_path / "candidate.db"
    Path(f"{candidate}{suffix}").touch()
    before = _snapshot(candidate)

    with pytest.raises(SchemaResetRequired):
        (initialize_history if history_role else initialize_ledger)(candidate)

    assert _snapshot(candidate) == before


@pytest.mark.parametrize("history_role", [False, True], ids=["ledger", "history"])
@pytest.mark.parametrize("existing", [False, True], ids=["fresh", "existing"])
def test_journal_access_error_cannot_be_treated_as_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, history_role: bool, existing: bool,
) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    if existing:
        initialize_ledger(ledger)
        initialize_history(history)
    candidate = history if history_role else ledger
    journal = Path(f"{candidate}-journal")
    before = _snapshot(ledger, history)
    lstat = Path.lstat

    def inaccessible(path: Path, *args, **kwargs):
        if path == journal:
            raise PermissionError("journal lookup denied")
        return lstat(path, *args, **kwargs)

    def no_sqlite(*args, **kwargs):
        pytest.fail("an inaccessible journal must not be treated as a fresh path")

    monkeypatch.setattr(Path, "lstat", inaccessible)
    monkeypatch.setattr(file_contracts.sqlite3, "connect", no_sqlite)

    assert database_pair.validate_database_pair(ledger, history).state == "refused"
    with pytest.raises(SchemaResetRequired):
        (HistoryRepository if history_role else LedgerRepository)(candidate)
    with pytest.raises(SchemaResetRequired if existing else PermissionError):
        (initialize_history if history_role else initialize_ledger)(candidate)
    assert _snapshot(ledger, history) == before


@pytest.mark.parametrize(
    ("role", "connect_writer"),
    (
        ("ledger", connect_ledger_writer),
        ("history", connect_history_writer),
    ),
)
def test_live_wal_sidecars_are_not_changed_by_contract_preflight(
    tmp_path: Path,
    role: str,
    connect_writer,
) -> None:
    service, ledger, history = _service(tmp_path)
    initialize_ledger(ledger)
    initialize_history(history)
    selected = ledger if role == "ledger" else history
    connection = connect_writer(selected)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("PRAGMA user_version = 99")
        connection.execute("COMMIT")
        wal = Path(f"{selected}-wal")
        shm = Path(f"{selected}-shm")
        assert wal.is_file() and wal.stat().st_size > 0
        assert shm.is_file() and shm.stat().st_size > 0
        before = _snapshot(ledger, history)

        result = service.validate_database_contracts()
        after = _snapshot(ledger, history)
    finally:
        connection.close()

    assert result.state == "ready"
    assert after == before
    service.close()


def test_ready_database_initialization_is_a_byte_exact_noop(
    tmp_path: Path,
) -> None:
    service, ledger, history = _service(tmp_path)
    initialize_ledger(ledger)
    initialize_history(history)
    ledger_writer = connect_ledger_writer(ledger)
    history_writer = connect_history_writer(history)
    try:
        for value, connection in enumerate((ledger_writer, history_writer), start=1):
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(f"PRAGMA user_version = {value}")
            connection.execute("COMMIT")
        for path in (ledger, history):
            assert Path(f"{path}-wal").is_file()
            assert Path(f"{path}-shm").is_file()
        before = _snapshot(ledger, history)

        first = service.initialize_database_contracts()
        second = service.initialize_database_contracts()
        after = _snapshot(ledger, history)
    finally:
        history_writer.close()
        ledger_writer.close()

    assert first.state == second.state == "ready"
    assert after == before
    service.close()


@pytest.mark.parametrize("role", ("ledger", "history"))
@pytest.mark.parametrize("shape", ("malformed", "unversioned", "swapped-marker"))
def test_role_contract_counterexamples_refuse_without_mutation(
    tmp_path: Path,
    role: str,
    shape: str,
) -> None:
    service, ledger, history = _service(tmp_path)
    selected = ledger if role == "ledger" else history
    other = history if role == "ledger" else ledger
    initialize_other = initialize_history if role == "ledger" else initialize_ledger
    initialize_other(other)

    if shape == "malformed":
        selected.write_bytes(b"not a SQLite database")
    elif shape == "unversioned":
        with closing(sqlite3.connect(selected)) as connection:
            with connection:
                connection.execute("CREATE TABLE legacy_marker(value TEXT)")
                connection.execute(
                    "INSERT INTO legacy_marker(value) VALUES ('preserve')"
                )
    else:
        initialize_selected = (
            initialize_ledger if role == "ledger" else initialize_history
        )
        initialize_selected(selected)
        swapped = HISTORY_CONTRACT_ID if role == "ledger" else LEDGER_CONTRACT_ID
        with closing(sqlite3.connect(selected)) as connection:
            with connection:
                connection.execute(
                    "UPDATE schema_metadata SET value = ? "
                    "WHERE key = 'contract_id'",
                    (swapped,),
                )
    before = _snapshot(ledger, history)

    first = service.validate_database_contracts()
    second = service.validate_database_contracts()

    assert first == second
    assert first.state == "refused"
    assert first.reason == f"{role}-contract"
    assert _snapshot(ledger, history) == before
    service.close()


def test_fresh_database_pair_initializes_coordinately(tmp_path: Path) -> None:
    service, ledger, history = _service(tmp_path)
    assert service.validate_database_contracts().state == "fresh"

    initialized = service.initialize_database_contracts()
    repeated = service.initialize_database_contracts()

    assert initialized.state == "ready"
    assert repeated.state == "ready"
    assert service.validate_database_contracts().state == "ready"
    assert ledger.exists()
    assert history.exists()
    assert set(_snapshot(ledger, history)) == {ledger, history}
    service.close()


@pytest.mark.parametrize("role", ["ledger", "history"])
@pytest.mark.parametrize("suffix", ["", "-wal", "-shm", "-journal"])
@pytest.mark.parametrize("change", ["write", "replace"])
def test_fresh_creation_rechecks_every_owned_reservation_before_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str, suffix: str, change: str,
) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    selected = ledger if role == "ledger" else history
    artifact = Path(f"{selected}{suffix}")
    displaced = tmp_path / "externally-displaced-reservation"
    reserve = database_pair._reserve_database

    def reserve_then_change(main: Path, owned):
        reserve(main, owned)
        if main == selected:
            if change == "replace":
                artifact.rename(displaced)
                artifact.touch()
            else:
                artifact.write_bytes(b"external contents")

    def no_initialization(*args, **kwargs):
        pytest.fail("a changed reservation must refuse before SQLite creation")

    monkeypatch.setattr(database_pair, "_reserve_database", reserve_then_change)
    monkeypatch.setattr(database_pair, f"_initialize_reserved_{role}", no_initialization)

    with pytest.raises(DatabasePairInitializationError) as raised:
        database_pair.initialize_database_pair(ledger, history)

    assert isinstance(raised.value.__cause__, OSError)
    assert _snapshot(ledger, history) == ({artifact: b""} if change == "replace" else {})
    assert not displaced.exists()


def test_fresh_creation_refuses_a_nonregular_reservation_even_with_matching_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    reserve = database_pair._reserve_database
    lstat = Path.lstat

    def classify_as_link(path: Path, *args, **kwargs):
        value = lstat(path, *args, **kwargs)
        # Inject a reparse classification without requiring symlink privileges;
        # the native lease still identifies the original reserved object.
        return os.stat_result((stat.S_IFLNK, *value[1:])) if path == ledger else value

    def reserve_then_reclassify(main: Path, owned):
        reserve(main, owned)
        monkeypatch.setattr(Path, "lstat", classify_as_link)

    def no_initialization(*args, **kwargs):
        pytest.fail("a nonregular reservation must refuse before SQLite creation")

    monkeypatch.setattr(database_pair, "_reserve_database", reserve_then_reclassify)
    monkeypatch.setattr(database_pair, "_initialize_reserved_ledger", no_initialization)

    with pytest.raises(DatabasePairInitializationError) as raised:
        database_pair.initialize_database_pair(ledger, history)

    assert isinstance(raised.value.__cause__, OSError)
    assert _snapshot(ledger, history) == {}


def test_caught_partial_database_initialization_removes_owned_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ledger, history = _service(tmp_path)

    def fail_history(path: str | Path, **_kwargs: object) -> Path:
        assert Path(path) == history
        Path(f"{path}-wal").write_bytes(b"attempt-owned-sidecar")
        raise OSError("injected history publication failure")

    monkeypatch.setattr(database_pair, "_initialize_reserved_history", fail_history)

    with pytest.raises(
        DatabasePairInitializationError,
        match="coordinated database initialization failed",
    ):
        service.initialize_database_contracts()

    assert _snapshot(ledger, history) == {}
    service.close()


def test_initialization_cleanup_preserves_unproven_raced_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ledger, history = _service(tmp_path)
    sidecar = Path(f"{ledger}-wal")
    reserve = database_pair._reserve

    def reserve_with_race(path: Path, owned: dict[Path, tuple[int, int]]) -> None:
        reserve(path, owned)
        if path == ledger:
            sidecar.write_bytes(b"foreign-sidecar")

    monkeypatch.setattr(database_pair, "_reserve", reserve_with_race)

    with pytest.raises(DatabasePairInitializationError):
        service.initialize_database_contracts()

    assert not ledger.exists()
    assert not history.exists()
    assert sidecar.read_bytes() == b"foreign-sidecar"
    service.close()


def test_initialization_cleanup_deletes_displaced_owned_sidecar_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ledger, history = _service(tmp_path)
    sidecar = Path(f"{ledger}-wal")
    displaced = tmp_path / "attempt-owned-ledger-wal"

    def fail_ledger_after_sidecar_write(
        path: str | Path,
        **_kwargs: object,
    ) -> Path:
        sidecar.write_bytes(b"attempt-owned-sidecar")
        raise OSError(f"injected ledger failure for {path}")

    retract = database_pair._retract_owned

    def replace_before_retract(
        owned: dict[Path, OwnedArtifactLease],
    ) -> tuple[BaseException, ...]:
        assert sidecar in owned
        sidecar.rename(displaced)
        sidecar.write_bytes(b"foreign-replacement")
        return retract(owned)

    monkeypatch.setattr(
        database_pair,
        "_initialize_reserved_ledger",
        fail_ledger_after_sidecar_write,
    )
    monkeypatch.setattr(database_pair, "_retract_owned", replace_before_retract)

    with pytest.raises(DatabasePairInitializationError):
        service.initialize_database_contracts()

    assert not ledger.exists()
    assert not history.exists()
    assert sidecar.read_bytes() == b"foreign-replacement"
    assert not displaced.exists()
    service.close()


@pytest.mark.skipif(os.name != "nt", reason="requires Win32 delete-by-handle")
def test_owned_artifact_delete_cannot_be_redirected_after_bound_identity_check(
    tmp_path: Path,
) -> None:
    path = tmp_path / "reserved.db-wal"
    displaced = tmp_path / "reserved-displaced.db-wal"
    native = WindowsArtifactNative()
    lease = OwnedArtifactLease.reserve(path, native)
    path.write_bytes(b"attempt-owned")
    path.rename(displaced)
    path.write_bytes(b"foreign-replacement")

    deleted, failures = lease.retract()

    assert deleted is True
    assert failures == ()
    assert path.read_bytes() == b"foreign-replacement"
    assert not displaced.exists()


@pytest.mark.parametrize(
    ("phase", "interruption"),
    (
        ("ledger", KeyboardInterrupt("stop ledger publication")),
        ("history", SystemExit(19)),
    ),
)
def test_database_initialization_interrupt_retracts_every_owned_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    interruption: BaseException,
) -> None:
    service, ledger, history = _service(tmp_path)
    selected = ledger if phase == "ledger" else history

    def interrupt_publication(path: str | Path, **_kwargs: object) -> Path:
        assert Path(path) == selected
        Path(f"{path}-wal").write_bytes(b"attempt-owned-sidecar")
        raise interruption

    monkeypatch.setattr(
        database_pair,
        "_initialize_reserved_ledger" if phase == "ledger" else "_initialize_reserved_history",
        interrupt_publication,
    )

    with pytest.raises(type(interruption)) as raised:
        service.initialize_database_contracts()

    assert raised.value is interruption
    assert traceback.extract_tb(raised.value.__traceback__)[-1].name == (
        "interrupt_publication"
    )
    assert _snapshot(ledger, history) == {}
    service.close()


def test_database_initialization_interrupt_reports_incomplete_cleanup_without_wrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ledger, history = _service(tmp_path)
    interruption = KeyboardInterrupt("stop publication")
    retract = database_pair._retract_owned

    def interrupt_publication(_path: str | Path, **_kwargs: object) -> Path:
        raise interruption

    def report_cleanup_failure(
        owned: dict[Path, OwnedArtifactLease],
    ) -> tuple[BaseException, ...]:
        assert retract(owned) == ()
        return (OSError("injected cleanup report"),)

    monkeypatch.setattr(database_pair, "_initialize_reserved_ledger", interrupt_publication)
    monkeypatch.setattr(database_pair, "_retract_owned", report_cleanup_failure)

    with pytest.raises(KeyboardInterrupt) as raised:
        service.initialize_database_contracts()

    assert raised.value is interruption
    assert raised.value.__notes__ == [
        "NamiSync database initialization cleanup was incomplete. "
        f"{database_pair.DATABASE_RESET_DIRECTION}"
    ]
    assert _snapshot(ledger, history) == {}
    service.close()


def test_cleanup_interrupt_is_not_wrapped_after_ordinary_publication_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ledger, history = _service(tmp_path)
    interruption = KeyboardInterrupt("stop cleanup")

    def fail_publication(_path: str | Path, **_kwargs: object) -> Path:
        raise OSError("injected publication failure")

    def interrupt_cleanup(
        _owned: dict[Path, OwnedArtifactLease],
    ) -> tuple[BaseException, ...]:
        return (interruption,)

    monkeypatch.setattr(database_pair, "_initialize_reserved_ledger", fail_publication)
    monkeypatch.setattr(database_pair, "_retract_owned", interrupt_cleanup)

    with pytest.raises(KeyboardInterrupt) as raised:
        service.initialize_database_contracts()

    assert raised.value is interruption
    assert raised.value.__notes__ == [
        "NamiSync database initialization cleanup was incomplete. "
        f"{database_pair.DATABASE_RESET_DIRECTION}"
    ]
    service.close()


def test_retract_owned_continues_after_a_cleanup_interrupt(tmp_path: Path) -> None:
    class Native:
        def __init__(self) -> None:
            self.deleted: list[int] = []
            self.closed: list[int] = []

        def reserve(self, path: Path) -> tuple[int, tuple[int, int]]:
            handle = len(self.deleted) + len(self.closed) + 1
            return handle, (1, handle)

        def path_identity(self, path: Path) -> tuple[int, int]:
            raise AssertionError(path)

        def delete(self, handle: int) -> None:
            self.deleted.append(handle)
            if handle == 2:
                raise KeyboardInterrupt("stop exact-object cleanup")

        def close(self, handle: int) -> None:
            self.closed.append(handle)

    native = Native()
    owned = {
        tmp_path / f"artifact-{handle}": OwnedArtifactLease(
            tmp_path / f"artifact-{handle}",
            (1, handle),
            handle,
            native,
        )
        for handle in (1, 2, 3)
    }

    failures = database_pair._retract_owned(owned)

    assert len(failures) == 1
    assert isinstance(failures[0], KeyboardInterrupt)
    assert native.deleted == [3, 2, 1]
    assert native.closed == [3, 2, 1]


def test_successful_publication_does_not_wrap_a_release_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ledger, history = _service(tmp_path)
    interruption = SystemExit(23)
    release = database_pair._release_owned

    def report_release_interrupt(
        owned: dict[Path, OwnedArtifactLease],
    ) -> tuple[BaseException, ...]:
        assert release(owned) == ()
        return (interruption,)

    monkeypatch.setattr(database_pair, "_release_owned", report_release_interrupt)

    with pytest.raises(SystemExit) as raised:
        service.initialize_database_contracts()

    assert raised.value is interruption
    assert raised.value.__notes__ == [
        "NamiSync database initialization succeeded, but ownership-handle "
        "release was incomplete. Restart NamiSync before retrying."
    ]
    assert database_pair.validate_database_pair(ledger, history).state == "ready"
    service.close()


def test_initialization_cleanup_never_deletes_raced_preexisting_peer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ledger, history = _service(tmp_path)

    def fail_ledger(path: str | Path, **_kwargs: object) -> Path:
        assert Path(path) == ledger
        history.write_bytes(b"created outside this attempt")
        raise OSError("injected ledger publication failure")

    monkeypatch.setattr(database_pair, "_initialize_reserved_ledger", fail_ledger)

    with pytest.raises(DatabasePairInitializationError):
        service.initialize_database_contracts()

    assert not ledger.exists()
    assert history.read_bytes() == b"created outside this attempt"
    service.close()


def test_crash_shaped_single_publication_refuses_next_launch(
    tmp_path: Path,
) -> None:
    service, ledger, history = _service(tmp_path)
    initialize_ledger(ledger)
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "refused"
    assert result.reason == "inconsistent-pair"
    assert _snapshot(ledger, history) == before
    assert not history.exists()
    service.close()
