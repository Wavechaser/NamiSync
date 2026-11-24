"""The schema migrator: classification, exclusive access, backup and rollback.

Real files throughout; concurrency uses real child processes. Pair-level
migration, interruption and admission live in
``tests/test_database_pair_migration.py``.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sqlite3
from time import monotonic, sleep

import pytest

import namisync.db.migration as migration
from namisync.core.formats import FORMAT_VERSIONS
from namisync.db.claims import (
    DatabaseInUse,
    acquire_database_claim,
    hold_maintenance_claims,
)
from namisync.db.connections import connect_history_writer
from namisync.db.contracts import probe_database_file_contract
from namisync.db.history import HistoryRepository
from namisync.db.migration import (
    MIGRATION_STEPS,
    DatabaseBackupFailed,
    DatabaseMigrationFailed,
    migrate_database,
)
from namisync.db.repositories import LedgerRepository
from namisync.db.schema import (
    HISTORY_FORMATS,
    HISTORY_SCHEMA_VERSION,
    LEDGER_FORMATS,
    LEDGER_SCHEMA_VERSION,
    RELEASED_HISTORY_SCHEMA_VERSION,
    RELEASED_LEDGER_SCHEMA_VERSION,
    DatabaseMigrationRequired,
    DatabaseNewerVersion,
    DatabaseRoleMismatch,
    SchemaResetRequired,
    classify_database,
    initialize_history,
    initialize_ledger,
)

from _child_process import WAIT_SECONDS, Child, run_child
from _released_fixture import (
    carried_rows,
    copy_released_pair,
    copy_released_role,
    released_columns,
)


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows file sharing and claims")

# The formats each schema version embeds, as literals. A core format bump
# changes FORMAT_VERSIONS and fails here until a new schema version, with its
# migration or invalidating step, pins the new value.
PINNED_FORMATS = {
    ("ledger", 5): {
        "event": 5, "evidence": 2, "identity": 1, "numeric": 1,
        "path-key": 1, "preimage": 1, "recording": 1,
    },
    ("history", 9): {"event": 5, "numeric": 1, "preimage": 1, "recording": 1},
}
_HOLD_SQLITE = """
import sqlite3, sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None)
mode = sys.argv[2]
if mode == "reader":
    connection.execute("SELECT count(*) FROM schema_metadata").fetchall()
elif mode == "read-transaction":
    connection.execute("BEGIN")
    connection.execute("SELECT count(*) FROM schema_metadata").fetchall()
elif mode == "writer":
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("PRAGMA user_version = 7")
    connection.execute("COMMIT")
print("held", flush=True)
sys.stdin.read()
"""
_PIN_LIKE_DESKTOP = """
import sys
from pathlib import Path
from namisync.interfaces.web.paths import WindowsPathLeaseNative
handle = WindowsPathLeaseNative().open(Path(sys.argv[1]), directory=False)
print("held", flush=True)
sys.stdin.read()
"""
_TRY_READ = """
import sqlite3, sys
connection = sqlite3.connect(sys.argv[1], timeout=0, isolation_level=None)
try:
    connection.execute("SELECT count(*) FROM schema_metadata").fetchall()
    print("read")
except sqlite3.OperationalError as error:
    print("refused " + str(error))
"""
_TRY_WRITE = """
import sqlite3, sys
connection = sqlite3.connect(sys.argv[1], timeout=0, isolation_level=None)
try:
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("PRAGMA user_version = 9")
    connection.execute("COMMIT")
    print("wrote")
except sqlite3.OperationalError as error:
    print("refused " + str(error))
"""


def _bytes(main: Path) -> dict[str, bytes | None]:
    return {
        suffix: Path(f"{main}{suffix}").read_bytes() if Path(f"{main}{suffix}").exists() else None
        for suffix in ("", "-wal")
    }


def _eventually(operation):
    # Windows may release a killed process's handles and locks slightly late.
    deadline = monotonic() + WAIT_SECONDS
    while True:
        try:
            return operation()
        except DatabaseInUse:
            if monotonic() > deadline:
                raise
            sleep(0.05)


def _migrate_ledger(main: Path) -> migration.DatabaseMigration:
    with acquire_database_claim(main, exclusive=True) as claim:
        return migrate_database(main, history=False, claim=claim)


def _classify_cold(main: Path, *, history: bool) -> str:
    try:
        probe_database_file_contract(main, history=history)
    except DatabaseMigrationRequired:
        return "older"
    return "current"


@pytest.fixture
def released_ledger(tmp_path: Path) -> Path:
    return copy_released_role(tmp_path / "data", history=False)


def test_each_schema_version_embeds_exactly_its_pinned_formats() -> None:
    declared = {
        ("ledger", LEDGER_SCHEMA_VERSION): {name: FORMAT_VERSIONS[name] for name in LEDGER_FORMATS},
        ("history", HISTORY_SCHEMA_VERSION): {
            name: FORMAT_VERSIONS[name] for name in HISTORY_FORMATS
        },
    }
    assert declared == PINNED_FORMATS


def test_every_supported_source_version_has_a_migration_step() -> None:
    for role, oldest, current in (
        ("ledger", RELEASED_LEDGER_SCHEMA_VERSION, LEDGER_SCHEMA_VERSION),
        ("history", RELEASED_HISTORY_SCHEMA_VERSION, HISTORY_SCHEMA_VERSION),
    ):
        version = oldest
        while version < current:
            step = MIGRATION_STEPS[(role, version)]
            assert (step.role, step.source_version) == (role, version)
            assert step.target_version > version
            version = step.target_version
        assert version == current
    assert {key[0] for key in MIGRATION_STEPS} == {"ledger", "history"}


@pytest.mark.parametrize("history", (False, True), ids=("ledger", "history"))
def test_released_database_classifies_older_and_altered_topology_is_refused(
    tmp_path: Path, history: bool,
) -> None:
    main = copy_released_role(tmp_path / "data", history=history)
    before = _bytes(main)
    with pytest.raises(DatabaseMigrationRequired, match="Start NamiSync, or run a sync"):
        probe_database_file_contract(main, history=history)
    assert _bytes(main) == before
    with closing(sqlite3.connect(main)) as connection:
        with connection:
            connection.execute("DROP INDEX " + (
                "history_runs_started_idx" if history else "volumes_serial_idx"
            ))
    with pytest.raises(SchemaResetRequired, match="schema topology"):
        probe_database_file_contract(main, history=history)


@pytest.mark.parametrize(("history", "change"), [
    *(
        (history, change)
        for history in (False, True)
        for change in (
            "schema-version", "format-above", "unknown-role", "other-role",
            "missing-format", "wrong-format", "unknown-format",
        )
    ),
    (False, "missing-instance"),
    (False, "malformed-instance"),
])
def test_current_metadata_is_newer_or_refused_without_change(
    tmp_path: Path, history: bool, change: str,
) -> None:
    main = (initialize_history if history else initialize_ledger)(tmp_path / "database.db")
    statement = {
        "schema-version": (
            "UPDATE schema_metadata SET value = ? WHERE key = 'schema_version'",
            (str((HISTORY_SCHEMA_VERSION if history else LEDGER_SCHEMA_VERSION) + 1),),
        ),
        "format-above": (
            "UPDATE schema_metadata SET value = ? WHERE key = 'format.recording'",
            (str(FORMAT_VERSIONS["recording"] + 1),),
        ),
        "unknown-role": (
            "UPDATE schema_metadata SET value = 'unknown' WHERE key = 'role'", (),
        ),
        "other-role": (
            "UPDATE schema_metadata SET value = ? WHERE key = 'role'",
            ("ledger" if history else "history",),
        ),
        "missing-instance": ("DELETE FROM schema_metadata WHERE key = 'instance_id'", ()),
        "malformed-instance": (
            "UPDATE schema_metadata SET value = ? WHERE key = 'instance_id'", ("A" * 32,),
        ),
        "missing-format": ("DELETE FROM schema_metadata WHERE key = 'format.numeric'", ()),
        "wrong-format": (
            "UPDATE schema_metadata SET value = '0' WHERE key = 'format.numeric'", (),
        ),
        "unknown-format": (
            "INSERT INTO schema_metadata(key, value) VALUES ('format.unknown', '1')", (),
        ),
    }[change]
    with closing(sqlite3.connect(main)) as connection:
        with connection:
            assert connection.execute(*statement).rowcount == 1
    before = _bytes(main)
    newer = change in {"schema-version", "format-above"}
    swapped = change in {"other-role", "unknown-role"}
    expected = (
        DatabaseNewerVersion if newer else DatabaseRoleMismatch if swapped
        else SchemaResetRequired
    )
    repository = HistoryRepository if history else LedgerRepository
    for consumer in (
        lambda: probe_database_file_contract(main, history=history),
        lambda: repository(main),
        lambda: (initialize_history if history else initialize_ledger)(main),
    ):
        with pytest.raises(expected) as raised:
            consumer()
        assert type(raised.value) is expected
        text = str(raised.value).lower()
        if newer or swapped:
            assert ("newer namisync" in text) is newer
            assert ("look swapped" in text) is (change == "other-role")
            assert ("is not a namisync" in text) is (change == "unknown-role")
            assert not {"delete", "archive", "reset"} & set(text.replace(".", " ").split())
        else:
            assert "archive or delete" in text
        assert _bytes(main) == before


def test_fresh_ledger_never_reuses_a_deleted_highest_id(tmp_path: Path) -> None:
    ledger = initialize_ledger(tmp_path / "ledger.db")
    history = initialize_history(tmp_path / "history.db")
    now = "2026-01-01T00:00:00.000000Z"
    with closing(sqlite3.connect(ledger)) as connection:
        with connection:
            volume = connection.execute(
                "INSERT INTO volumes(serial, fs_type, first_seen_at, last_seen_at) "
                "VALUES ('serial', 'NTFS', ?, ?) RETURNING id", (now, now),
            ).fetchone()[0]
            insert = (
                "INSERT INTO locations(volume_id, volume_relative_path, "
                "volume_relative_path_key, created_at, last_seen_at) "
                "VALUES (?, ?, ?, ?, ?) RETURNING id"
            )
            connection.execute(insert, (volume, "a", "A", now, now))
            highest = connection.execute(insert, (volume, "b", "B", now, now)).fetchone()[0]
            connection.execute("DELETE FROM locations WHERE id = ?", (highest,))
            assert connection.execute(insert, (volume, "c", "C", now, now)).fetchone()[0] > highest
    with closing(sqlite3.connect(history)) as connection:
        assert connection.execute(
            "SELECT count(*) FROM sqlite_schema WHERE name = 'sqlite_sequence'"
        ).fetchone()[0] == 0


def test_history_run_ledger_instance_is_checked_and_write_once(tmp_path: Path) -> None:
    history = initialize_history(tmp_path / "history.db")
    insert = (
        "INSERT INTO history_runs(run_token, session_id, activity_kind, host_key, "
        "ledger_instance_id, created_at, current_state, context_hash, "
        "event_chain_hash, prefix_projection_hash) "
        "VALUES (?, 's', 'sync', 'h', ?, '2026-01-01T00:00:00.000000Z', 'running', "
        "x'00', x'00', zeroblob(32))"
    )
    with closing(connect_history_writer(history)) as connection:
        for malformed in ("A" * 32, "0" * 31, "g" * 32):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(insert, ("bad", malformed))
        connection.execute(insert, ("run", "0" * 32))
        with pytest.raises(sqlite3.IntegrityError, match="ledger instance is immutable"):
            connection.execute(
                "UPDATE history_runs SET ledger_instance_id = ? WHERE run_token = 'run'",
                ("1" * 32,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="ledger instance is immutable"):
            connection.execute(
                "UPDATE history_runs SET ledger_instance_id = NULL WHERE run_token = 'run'"
            )


def test_migration_requires_the_held_exclusive_claim_of_its_database(
    released_ledger: Path, tmp_path: Path,
) -> None:
    other = tmp_path / "data" / "other.db"
    before = _bytes(released_ledger)
    with acquire_database_claim(released_ledger, exclusive=False) as shared:
        with pytest.raises(ValueError, match="exclusive maintenance claim"):
            migrate_database(released_ledger, history=False, claim=shared)
    with acquire_database_claim(other, exclusive=True) as foreign:
        with pytest.raises(ValueError, match="exclusive maintenance claim"):
            migrate_database(released_ledger, history=False, claim=foreign)
    released = acquire_database_claim(released_ledger, exclusive=True)
    released.release()
    with pytest.raises(ValueError, match="exclusive maintenance claim"):
        migrate_database(released_ledger, history=False, claim=released)
    with acquire_database_claim(released_ledger, exclusive=True) as claim:
        with pytest.raises(ValueError, match="ledger instance id"):
            migrate_database(released_ledger, history=False, claim=claim, ledger_instance_id="0" * 32)
    assert _bytes(released_ledger) == before
    assert not list(released_ledger.parent.glob("*.backup-*"))


def test_failed_verification_rolls_back_and_names_its_verified_backup(
    released_ledger: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = carried_rows(released_ledger, tmp_path / "before", history=False)

    def refuse(*args, **kwargs):
        raise sqlite3.DatabaseError("injected verification failure")

    monkeypatch.setattr(migration, "_verify", refuse)
    with acquire_database_claim(released_ledger, exclusive=True) as claim:
        with pytest.raises(DatabaseMigrationFailed) as raised:
            migrate_database(released_ledger, history=False, claim=claim)
    backup = raised.value.backup
    assert raised.value.path == released_ledger
    assert backup is not None and str(backup) in str(raised.value)
    assert "left unchanged" in str(raised.value)
    assert "delete" not in str(raised.value).lower()
    assert backup.name.startswith("ledger.db.backup-v4-")
    assert _classify_cold(released_ledger, history=False) == "older"
    assert carried_rows(released_ledger, tmp_path / "after", history=False) == old
    with closing(sqlite3.connect(backup.as_uri() + "?mode=ro", uri=True)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert classify_database(connection, history=False) == 4
    assert carried_rows(backup, tmp_path / "backup", history=False) == old
    assert [path.name for path in released_ledger.parent.glob("*.tmp*")] == []

    monkeypatch.undo()
    with acquire_database_claim(released_ledger, exclusive=True) as claim:
        second = migrate_database(released_ledger, history=False, claim=claim)
    assert second.backup is not None and second.backup != backup
    assert _classify_cold(released_ledger, history=False) == "current"


def test_backup_never_replaces_an_existing_file(
    released_ledger: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    moment = datetime(2026, 11, 25, 1, 2, 3, 456789, tzinfo=timezone.utc)

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment

    monkeypatch.setattr(migration, "datetime", FixedClock)
    occupied = released_ledger.with_name("ledger.db.backup-v4-20261125T010203456789Z")
    occupied.write_bytes(b"someone else's file")
    before = _bytes(released_ledger)
    with acquire_database_claim(released_ledger, exclusive=True) as claim:
        with pytest.raises(DatabaseBackupFailed) as raised:
            migrate_database(released_ledger, history=False, claim=claim)
    assert type(raised.value.__cause__) is FileExistsError
    assert "could not write a verified backup" in str(raised.value)
    assert "changed nothing" in str(raised.value)
    assert "three times the database's size" in str(raised.value)
    assert occupied.read_bytes() == b"someone else's file"
    assert _bytes(released_ledger) == before
    assert sorted(path.name for path in released_ledger.parent.iterdir()) == sorted(
        ["ledger.db", "ledger.db-wal", "ledger.db-shm", "ledger.db.claim", occupied.name]
    )


@pytest.mark.parametrize("mode", ("open", "reader", "read-transaction", "writer"))
def test_open_main_handles_refuse_migration_until_their_process_dies(
    released_ledger: Path, mode: str,
) -> None:
    child = Child(_HOLD_SQLITE, str(released_ledger), mode)
    try:
        assert child.read() == "held"
        before = _bytes(released_ledger)
        with acquire_database_claim(released_ledger, exclusive=True) as claim:
            with pytest.raises(DatabaseInUse, match="open in another NamiSync process"):
                migrate_database(released_ledger, history=False, claim=claim)
        assert _bytes(released_ledger) == before
        assert not list(released_ledger.parent.glob("*.backup-*"))
    finally:
        child.kill()
    assert _eventually(lambda: _migrate_ledger(released_ledger)).backup is not None


def test_desktop_style_pin_refuses_migration_though_sqlite_could_open(
    released_ledger: Path,
) -> None:
    child = Child(_PIN_LIKE_DESKTOP, str(released_ledger))
    try:
        assert child.read() == "held"
        # The pin shares read and write, so SQLite alone would not notice it.
        assert run_child(_TRY_READ, str(released_ledger)) == "read"
        before = _bytes(released_ledger)
        with acquire_database_claim(released_ledger, exclusive=True) as claim:
            with pytest.raises(DatabaseInUse):
                migrate_database(released_ledger, history=False, claim=claim)
        assert _bytes(released_ledger) == before
    finally:
        child.kill()
    assert _eventually(lambda: _migrate_ledger(released_ledger)).backup is not None


@pytest.mark.parametrize("mode", ("reader", "read-transaction", "writer"))
def test_exclusive_lock_is_refused_under_another_connection_and_then_shuts_others_out(
    released_ledger: Path, mode: str,
) -> None:
    # The second gate, for a process that opened the database after the
    # delete-access probe: SQLite's exclusive lock.
    child = Child(_HOLD_SQLITE, str(released_ledger), mode)
    try:
        assert child.read() == "held"
        with pytest.raises(DatabaseInUse):
            migration._open_exclusive(released_ledger)
    finally:
        child.kill()
    connection = _eventually(lambda: migration._open_exclusive(released_ledger))
    try:
        assert run_child(_TRY_READ, str(released_ledger)).startswith("refused database is locked")
        assert run_child(_TRY_WRITE, str(released_ledger)).startswith("refused database is locked")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("PRAGMA user_version = 3")
        connection.execute("COMMIT")
        assert run_child(_TRY_READ, str(released_ledger)).startswith("refused database is locked")
        backup = sqlite3.connect(":memory:")
        connection.backup(backup)
        assert backup.execute("SELECT count(*) FROM locations").fetchone()[0] == 5
        backup.close()
    finally:
        connection.close()
    assert run_child(_TRY_READ, str(released_ledger)) == "read"


def test_migrating_a_current_database_is_a_no_op(tmp_path: Path) -> None:
    ledger = initialize_ledger(tmp_path / "ledger.db")
    history = initialize_history(tmp_path / "history.db")
    before = (_bytes(ledger), _bytes(history))
    with hold_maintenance_claims(ledger, history) as claims:
        ledger_result = migrate_database(ledger, history=False, claim=claims.ledger)
        history_result = migrate_database(
            history, history=True, claim=claims.history,
            ledger_instance_id=ledger_result.ledger_instance_id,
        )
    assert ledger_result.backup is None and history_result.backup is None
    with closing(sqlite3.connect(ledger.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
        assert ledger_result.ledger_instance_id == connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'instance_id'"
        ).fetchone()[0]
    assert (_bytes(ledger), _bytes(history)) == before


@pytest.mark.parametrize("history", (False, True), ids=("ledger", "history"))
def test_copy_lists_equal_the_released_catalog_columns(tmp_path: Path, history: bool) -> None:
    # Derived from the fixture's own catalog, never from the step: a column
    # missing from a copy list would otherwise be dropped silently.
    catalog = released_columns(tmp_path / "catalog", history=history)
    step = MIGRATION_STEPS[("history", 8) if history else ("ledger", 4)]
    assert dict(step.tables) == catalog
    assert [table for table, _ in step.tables] == list(catalog)


def _checkpointed_ledger(tmp_path: Path) -> Path:
    """A released ledger copy whose WAL is folded into its main file."""

    main = copy_released_role(tmp_path / "data", history=False)
    with closing(sqlite3.connect(main)) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
    return main


def test_foreign_key_violation_in_the_source_refuses_and_keeps_the_old_database(
    released_ledger: Path, tmp_path: Path,
) -> None:
    # Written with foreign keys off, as no released writer could.
    with closing(sqlite3.connect(released_ledger)) as connection:
        with connection:
            connection.execute(
                "INSERT INTO operations(run_id, op_token, kind, target_rel_path, outcome, "
                "recorded_at, payload_hash) VALUES (9999, 'orphan', 'copy', 'x', "
                "'succeeded', '2026-01-01T00:00:00.000000Z', zeroblob(32))"
            )
    assert _classify_cold(released_ledger, history=False) == "older"
    old = carried_rows(released_ledger, tmp_path / "before", history=False)

    with acquire_database_claim(released_ledger, exclusive=True) as claim:
        with pytest.raises(DatabaseMigrationFailed, match="left unchanged") as raised:
            migrate_database(released_ledger, history=False, claim=claim)

    assert "foreign key check" in str(raised.value)
    assert _classify_cold(released_ledger, history=False) == "older"
    assert carried_rows(released_ledger, tmp_path / "after", history=False) == old


def test_backup_that_fails_verification_publishes_and_migrates_nothing(
    tmp_path: Path,
) -> None:
    main = _checkpointed_ledger(tmp_path)
    with closing(sqlite3.connect(main.as_uri() + "?mode=ro", uri=True)) as connection:
        root = connection.execute(
            "SELECT rootpage FROM sqlite_schema WHERE name = 'mappings_active_pair_uq'"
        ).fetchone()[0]
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
    # Drop one entry from the partial index's leaf page: a real corruption
    # that the catalog, the classification and count(*) never read, and
    # that the backup copies page for page.
    data = bytearray(main.read_bytes())
    offset = (root - 1) * page_size
    assert data[offset] == 0x0A
    cells = int.from_bytes(data[offset + 3:offset + 5], "big")
    assert cells >= 1
    data[offset + 3:offset + 5] = (cells - 1).to_bytes(2, "big")
    main.write_bytes(bytes(data))
    with closing(sqlite3.connect(main.as_uri() + "?mode=ro", uri=True)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]
    assert _classify_cold(main, history=False) == "older"
    before = _bytes(main)

    with acquire_database_claim(main, exclusive=True) as claim:
        with pytest.raises(DatabaseBackupFailed) as raised:
            migrate_database(main, history=False, claim=claim)

    # Damage guidance: the backup is a page copy, so space or access advice
    # cannot help, and nothing directs the user to discard the files.
    text = str(raised.value)
    assert "failed SQLite's integrity check" in text
    assert "BackupVerificationFailed" not in text
    assert "nothing was changed" in text
    assert "Keep the database files and their -wal and -shm sidecars for inspection" in text
    assert not re.search(r"free space|three times|write access|delete|archive|reset", text, re.I)
    assert _bytes(main) == before
    assert _classify_cold(main, history=False) == "older"
    assert not list(main.parent.glob("*.backup-*"))
    assert not list(main.parent.glob("*.tmp*"))


@pytest.mark.parametrize("history", (False, True), ids=("ledger", "history"))
def test_released_version_with_a_role_row_is_not_older_and_supported(
    tmp_path: Path, history: bool,
) -> None:
    main = copy_released_role(tmp_path / "data", history=history)
    with closing(sqlite3.connect(main)) as connection:
        with connection:
            connection.execute(
                "INSERT INTO schema_metadata(key, value) VALUES ('role', ?)",
                ("history" if history else "ledger",),
            )
    before = _bytes(main)
    with pytest.raises(SchemaResetRequired, match="schema version (4|8)"):
        probe_database_file_contract(main, history=history)
    assert _bytes(main) == before


@pytest.mark.parametrize("released", (True, False), ids=("released", "current"))
def test_swapped_paths_are_refused_as_swapped_without_reset_or_newer(
    tmp_path: Path, released: bool,
) -> None:
    if released:
        ledger, history = copy_released_pair(tmp_path / "data")
    else:
        ledger = initialize_ledger(tmp_path / "data" / "ledger.db")
        history = initialize_history(tmp_path / "data" / "history.db")
    before = (_bytes(ledger), _bytes(history))
    for path, expected_history in ((ledger, True), (history, False)):
        with pytest.raises(DatabaseRoleMismatch) as raised:
            probe_database_file_contract(path, history=expected_history)
        text = str(raised.value).lower()
        assert "look swapped" in text and "--database and --history-database" in text
        assert not re.search(r"newer|delete|archive|reset", text)
    assert (_bytes(ledger), _bytes(history)) == before


def test_a_failed_commit_is_reported_as_unconfirmed(
    released_ledger: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_commit(connection):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(migration, "_commit", fail_commit)
    with acquire_database_claim(released_ledger, exclusive=True) as claim:
        with pytest.raises(DatabaseMigrationFailed) as raised:
            migrate_database(released_ledger, history=False, claim=claim)
    text = str(raised.value)
    assert "could not be confirmed" in text
    assert "checks the databases again at the next start" in text
    assert "left unchanged" not in text and str(raised.value.backup) in text


@pytest.mark.parametrize("history", (False, True), ids=("ledger", "history"))
def test_role_less_database_above_current_is_unsupported_not_newer(
    tmp_path: Path, history: bool,
) -> None:
    # Only a database whose role row names this role can be from a newer NamiSync.
    main = copy_released_role(tmp_path / "data", history=history)
    with closing(sqlite3.connect(main)) as connection:
        with connection:
            connection.execute(
                "UPDATE schema_metadata SET value = '12' WHERE key = 'schema_version'"
            )
    with pytest.raises(SchemaResetRequired, match="schema version 12") as raised:
        probe_database_file_contract(main, history=history)
    assert type(raised.value) is SchemaResetRequired
    assert "newer" not in str(raised.value).lower()