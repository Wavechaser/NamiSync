"""Pair migration of the released v0.1.0 fixture: data kept, kills, refusals.

Every pair is a copy of ``tests/assets/v0_1_0/``. Concurrency and death use
real child processes that run the real migration and are killed from the
parent once their own script reports the stage it stopped at.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from datetime import timedelta
import os
from pathlib import Path
import re
import sqlite3
from time import monotonic, sleep

import pytest

import namisync.db.history as history_module
from namisync.core.planning import OperationKind, selection_digest
from namisync.core.recording import SyncRunCommand
from namisync.db.contracts import DatabaseConnectionOwner, probe_database_file_contract
from namisync.db.history import HistoryRepository
from namisync.db.recorder import LedgerRecorder
from namisync.db.schema import (
    HISTORY_FORMATS,
    LEDGER_FORMATS,
    DatabaseMigrationRequired,
    initialize_history,
    initialize_ledger,
)
from namisync.db.writer import TokenConflictError
from namisync.core.formats import FORMAT_VERSIONS
from namisync.workflows.database_pair import (
    DatabasePairRefusedError,
    DatabasePairState,
    ensure_database_pair,
    migrate_database_pair,
    validate_database_pair,
)
from namisync.workflows.runtime import LocalWorkflowRuntime

from _child_process import WAIT_SECONDS, Child
from _db_fixtures import NOW, FakeClock, attestation, file_stat, operation, plan, setup_recorder
from _released_fixture import (
    carried_rows,
    copy_released_pair,
    copy_released_role,
    released_columns,
)


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows file sharing and claims")

_BACKUP = re.compile(r"(ledger|history)\.db\.backup-v(4|8)-\d{8}T\d{12}Z")
_INSTANCE = re.compile("[0-9a-f]{32}")
_ROLES = (("ledger", False), ("history", True))
_INTERRUPTED = r"""
import os, sys, time
import namisync.db.migration as migration
import namisync.workflows.database_pair as pair

ledger, history, stage, role = sys.argv[1:5]


def hang():
    print("stopped", flush=True)
    time.sleep(120)


def stop(module, name, nth, *, after):
    original = getattr(module, name)
    calls = [0]

    def wrapped(*args, **kwargs):
        calls[0] += 1
        if not after and calls[0] == nth:
            hang()
        result = original(*args, **kwargs)
        if after and calls[0] == nth:
            hang()
        return result

    setattr(module, name, wrapped)


once = 1 if role == "ledger" else 2
if stage == "backup-written":
    stop(os, "rename", once, after=False)
elif stage == "backup-published":
    stop(migration, "_publish_backup", once, after=True)
elif stage == "renamed":
    stop(migration, "_rename_aside", once, after=True)
elif stage == "created":
    stop(migration, "_create_tables", once, after=True)
elif stage == "mid-copy":
    stop(migration, "_copy_table", 2 if role == "ledger" else 12, after=True)
elif stage == "copied":
    stop(migration, "_verify", once, after=False)
elif stage == "committed":
    stop(migration, "_commit", once, after=True)
elif stage == "between":
    stop(pair, "migrate_database", 2, after=False)
print("ready", flush=True)
result = pair.migrate_database_pair(ledger, history)
print("finished " + result.contract.state, flush=True)
"""
_HOLD = r"""
import sqlite3, sys
from pathlib import Path
kind, target = sys.argv[1:3]
if kind in ("shared-claim", "exclusive-claim"):
    from namisync.db.claims import acquire_database_claim
    held = acquire_database_claim(target, exclusive=kind == "exclusive-claim")
elif kind == "sqlite-reader":
    held = sqlite3.connect(target)
    held.execute("SELECT count(*) FROM schema_metadata").fetchall()
else:
    from namisync.interfaces.web.paths import WindowsPathLeaseNative
    held = WindowsPathLeaseNative().open(Path(target), directory=False)
print("held", flush=True)
sys.stdin.read()
"""


def _bytes(*mains: Path) -> dict[str, bytes | None]:
    return {
        f"{main.name}{suffix}": (
            Path(f"{main}{suffix}").read_bytes() if Path(f"{main}{suffix}").exists() else None
        )
        for main in mains
        for suffix in ("", "-wal")
    }


def _entries(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in directory.iterdir()}


def _classify(main: Path, *, history: bool) -> str:
    try:
        probe_database_file_contract(main, history=history)
    except DatabaseMigrationRequired:
        return "older"
    return "current"


def _rows(ledger: Path, history: Path, scratch: Path) -> dict[str, dict[str, list[tuple]]]:
    return {
        role: carried_rows(main, scratch / role, history=is_history)
        for (role, is_history), main in zip(_ROLES, (ledger, history))
    }


def _runtime_contract(ledger: Path, history: Path):
    with closing(LocalWorkflowRuntime(ledger, history)) as runtime:
        return runtime.validate_database_contracts()


def _metadata(main: Path) -> dict[str, str]:
    with closing(sqlite3.connect(main.as_uri() + "?mode=ro", uri=True)) as connection:
        return dict(connection.execute("SELECT key, value FROM schema_metadata"))


def _migrate_eventually(ledger: Path, history: Path):
    # A killed holder's locks and handles may outlive it briefly on Windows.
    deadline = monotonic() + WAIT_SECONDS
    while True:
        result = migrate_database_pair(ledger, history)
        if result.contract.reason != "database-in-use" or monotonic() > deadline:
            return result
        sleep(0.05)


def _assert_migrated(ledger: Path, history: Path) -> str:
    assert _classify(ledger, history=False) == "current"
    assert _classify(history, history=True) == "current"
    ledger_metadata = _metadata(ledger)
    instance_id = ledger_metadata.pop("instance_id")
    assert _INSTANCE.fullmatch(instance_id)
    assert ledger_metadata == {
        "role": "ledger", "schema_version": "5",
        **{f"format.{name}": str(FORMAT_VERSIONS[name]) for name in LEDGER_FORMATS},
    }
    assert _metadata(history) == {
        "role": "history", "schema_version": "9",
        **{f"format.{name}": str(FORMAT_VERSIONS[name]) for name in HISTORY_FORMATS},
    }
    with closing(sqlite3.connect(history.as_uri() + "?mode=ro", uri=True)) as connection:
        stamps = {row[0] for row in connection.execute("SELECT ledger_instance_id FROM history_runs")}
    assert stamps == {instance_id}
    return instance_id


def test_released_pair_migrates_with_every_row_and_id_kept(tmp_path: Path) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")
    old = _rows(ledger, history, tmp_path / "old")

    result = migrate_database_pair(ledger, history)

    assert result.contract.state is DatabasePairState.READY
    assert sorted(path.parent for path in result.backups) == [ledger.parent] * 2
    assert sorted(_BACKUP.fullmatch(path.name).group(1) for path in result.backups) == [
        "history", "ledger",
    ]
    assert _rows(ledger, history, tmp_path / "new") == old
    # The committed WAL was folded into the main file; v0.1.0's stale -shm
    # stays for SQLite to reinitialize at the next ordinary open.
    assert not Path(f"{ledger}-wal").exists() and not Path(f"{history}-wal").exists()
    assert Path(f"{ledger}-shm").exists() and Path(f"{history}-shm").exists()
    instance_id = _assert_migrated(ledger, history)
    with closing(sqlite3.connect(ledger.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
        assert dict(connection.execute("SELECT name, seq FROM sqlite_sequence")) == {
            table: max(row[0] for row in old["ledger"][table])
            for table in ("locations", "mappings", "inventory")
        }

    with closing(LocalWorkflowRuntime(ledger, history)) as runtime:
        assert runtime.validate_database_contracts().state is DatabasePairState.READY
        assert len(runtime.list_history(50)) == len(old["history"]["history_runs"])
        with runtime._ledger_read() as repository:
            assert repository.ledger_instance_id() == instance_id
            # Each carried row pairs a value with its type: index 2 is location_id.
            location_id = old["ledger"]["inventory"][0][2]
            assert len(repository.get_inventory(location_id)) == sum(
                1 for row in old["ledger"]["inventory"] if row[2] == location_id
            )

    before = _entries(ledger.parent)
    again = migrate_database_pair(ledger, history)
    assert (again.contract.state, again.backups) == (DatabasePairState.READY, ())
    assert _entries(ledger.parent) == before

    highest = max(row[0] for row in old["ledger"]["locations"])
    with closing(sqlite3.connect(ledger, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DELETE FROM locations WHERE id = ?", (highest,))
        replacement = connection.execute(
            "INSERT INTO locations(volume_id, volume_relative_path, "
            "volume_relative_path_key, created_at, last_seen_at) "
            "SELECT volume_id, 'new', 'NEW', created_at, last_seen_at FROM locations "
            "LIMIT 1 RETURNING id"
        ).fetchone()[0]
    assert replacement > highest


def test_migrated_history_pages_and_every_stored_hash_still_verifies(tmp_path: Path) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")
    assert migrate_database_pair(ledger, history).contract.state is DatabasePairState.READY

    with HistoryRepository(history) as repository:
        summaries = repository.list_summaries(50)
        assert len(summaries) == 15
        for summary in summaries:
            assert repository.get_summary(summary.run_token).run_token == summary.run_token
            items, after = 0, 0
            while True:
                page = repository.get_item_page(summary.run_token, after_order=after)
                items += len(page.items)
                if not page.has_more:
                    break
                after = page.next_after_order
            assert items == summary.item_count
            after = 0
            while True:
                event_page = repository.get_event_page(summary.run_token, after_seq=after)
                if not event_page.has_more:
                    break
                after = event_page.next_after_seq

    with closing(sqlite3.connect(history.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        runs = connection.execute("SELECT * FROM history_runs ORDER BY id").fetchall()
        assert len(runs) == 15
        for run in runs:
            history_module._validate_context_snapshot(run)
            history_module._validate_prefix_snapshot(run)
            chain = history_module._EMPTY_EVENT_CHAIN
            for event in connection.execute(
                "SELECT * FROM history_events WHERE run_id = ? ORDER BY event_seq", (run["id"],),
            ):
                receipt = history_module._validated_receipt(event)
                chain = history_module._advance_event_chain(chain, receipt.receipt_hash)
            assert chain == bytes(run["event_chain_hash"])


def _released_shape_ledger(
    directory: Path, recorded: Path, reference: Path, columns: dict[str, tuple[str, ...]],
) -> Path:
    """A ledger built from the released DDL, carrying rows a recorder wrote."""

    with closing(sqlite3.connect(reference.as_uri() + "?mode=ro", uri=True)) as source:
        ddl = [row[0] for row in source.execute(
            "SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY rowid"
        )]
        markers = source.execute("SELECT key, value FROM schema_metadata").fetchall()
    target = directory / "ledger.db"
    with closing(sqlite3.connect(target, isolation_level=None)) as connection:
        assert connection.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
        connection.execute("ATTACH DATABASE ? AS recorded", (str(recorded),))
        connection.execute("BEGIN")
        for statement in ddl:
            connection.execute(statement)
        connection.executemany("INSERT INTO schema_metadata(key, value) VALUES (?, ?)", markers)
        for table, table_columns in columns.items():
            listed = ", ".join(table_columns)
            connection.execute(
                f"INSERT INTO main.{table}({listed}) SELECT {listed} FROM recorded.{table}"
            )
        connection.execute("COMMIT")
        connection.execute("DETACH DATABASE recorded")
    return target


def test_recorder_replays_existing_run_and_operation_tokens_after_migration(
    tmp_path: Path,
) -> None:
    source = file_stat(identity_index=1)
    published = file_stat(identity_index=2, volume_serial="target-serial")
    copy = operation(OperationKind.COPY, source=source, target=None, intended=published)
    sync_plan = plan((copy,))
    evidence = attestation(published)
    (tmp_path / "recorded").mkdir()
    setup = setup_recorder(tmp_path / "recorded" / "ledger.db", sync_plan)
    try:
        identity = setup.run.record_copied(copy.op_id, evidence)
        run_row_id = setup.run._run_row_id
    finally:
        setup.recorder.close()
    selection = frozenset({copy.op_id})
    command = SyncRunCommand(
        setup.run_token, setup.host_id, setup.mapping_id, setup.source_location_id,
        setup.target_location_id, sync_plan, selection, selection_digest(selection), NOW,
    )
    data = tmp_path / "data"
    data.mkdir()
    ledger = _released_shape_ledger(
        data, setup.recorder.path,
        copy_released_role(tmp_path / "reference", history=False),
        released_columns(tmp_path / "columns", history=False),
    )
    history = copy_released_role(data, history=True)
    with pytest.raises(DatabaseMigrationRequired):
        probe_database_file_contract(ledger, history=False)

    assert migrate_database_pair(ledger, history).contract.state is DatabasePairState.READY
    assert carried_rows(ledger, tmp_path / "migrated", history=False) == carried_rows(
        setup.recorder.path, tmp_path / "recorded-rows", history=False,
    )

    recorder = LedgerRecorder(ledger, clock=FakeClock())
    try:
        before = carried_rows(ledger, tmp_path / "before", history=False)
        replayed = recorder.begin_sync_run(command)
        assert replayed._run_row_id == run_row_id
        assert replayed.record_copied(copy.op_id, evidence) == identity
        assert carried_rows(ledger, tmp_path / "after", history=False) == before
        with pytest.raises(TokenConflictError):
            recorder.begin_sync_run(replace(command, started_at=NOW + timedelta(microseconds=1)))
    finally:
        recorder.close()


_KILL_STAGES = [
    *((stage, role) for role in ("ledger", "history") for stage in (
        "backup-written", "backup-published", "renamed", "created",
        "mid-copy", "copied", "committed",
    )),
    ("between", "ledger"),
]


@pytest.mark.parametrize(("stage", "role"), _KILL_STAGES)
def test_killed_migration_leaves_old_or_new_and_the_next_call_finishes(
    tmp_path: Path, stage: str, role: str,
) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")
    old = _rows(ledger, history, tmp_path / "old")
    child = Child(_INTERRUPTED, str(ledger), str(history), stage, role)
    try:
        assert child.read() == "ready"
        assert child.read() == "stopped"
    finally:
        child.kill()

    ledger_done = role == "history" or stage in {"committed", "between"}
    history_done = role == "history" and stage == "committed"
    assert _classify(ledger, history=False) == ("current" if ledger_done else "older")
    assert _classify(history, history=True) == ("current" if history_done else "older")
    assert _rows(ledger, history, tmp_path / "killed") == old
    temporaries = sorted(path.name for path in ledger.parent.glob("*.migration-*.tmp"))
    assert len(temporaries) == (1 if stage == "backup-written" else 0)

    result = _migrate_eventually(ledger, history)

    assert result.contract.state is DatabasePairState.READY
    assert all(_BACKUP.fullmatch(path.name) for path in result.backups)
    assert _rows(ledger, history, tmp_path / "finished") == old
    _assert_migrated(ledger, history)
    # A crash's temporary is neither removed nor taken for a backup.
    assert sorted(path.name for path in ledger.parent.glob("*.migration-*.tmp")) == temporaries


@pytest.mark.parametrize(("kind", "held_role"), [
    ("shared-claim", "ledger"),
    ("exclusive-claim", "history"),
    ("sqlite-reader", "ledger"),
    ("desktop-pin", "ledger"),
    ("sqlite-reader", "history"),
    ("desktop-pin", "history"),
])
def test_migration_refuses_while_another_process_holds_either_database(
    tmp_path: Path, kind: str, held_role: str,
) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")
    old = _rows(ledger, history, tmp_path / "old")
    held = ledger if held_role == "ledger" else history
    child = Child(_HOLD, kind, str(held))
    try:
        assert child.read() == "held"
        before = _bytes(ledger, history)
        result = migrate_database_pair(ledger, history)
        assert result.contract.state is DatabasePairState.REFUSED
        assert result.contract.reason == "database-in-use"
        assert result.contract.reset_direction is None
        assert "delete" not in result.contract.guidance.lower()
        assert "in use" in result.contract.guidance or "open in another" in result.contract.guidance
        # Claims refuse before any file is touched, and both main files are
        # probed before either migrates: a holder of either one leaves both
        # databases byte-identical, with no backup.
        assert _bytes(ledger, history) == before
        assert _classify(history, history=True) == "older"
        assert _classify(ledger, history=False) == "older"
        assert result.migrated == ()
        assert not list(ledger.parent.glob("*.backup-*"))
        assert _rows(ledger, history, tmp_path / "refused") == old
    finally:
        child.kill()

    assert _migrate_eventually(ledger, history).contract.state is DatabasePairState.READY
    assert _rows(ledger, history, tmp_path / "finished") == old
    _assert_migrated(ledger, history)


def test_classifying_released_and_migrated_pairs_writes_nothing(tmp_path: Path) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")
    before = _entries(ledger.parent)
    for classify in (
        lambda: validate_database_pair(ledger, history),
        lambda: _runtime_contract(ledger, history),
    ):
        contract = classify()
        assert (contract.state, contract.reason) == (
            DatabasePairState.MIGRATION_REQUIRED, "pair-older",
        )
        assert contract.reset_direction is None
        assert "Start NamiSync, or run a sync or inventory command, once" in contract.guidance
        assert _entries(ledger.parent) == before
    assert not list(ledger.parent.glob("*.claim"))

    assert migrate_database_pair(ledger, history).contract.state is DatabasePairState.READY
    migrated = _entries(ledger.parent)
    assert validate_database_pair(ledger, history).state is DatabasePairState.READY
    assert _entries(ledger.parent) == migrated


@pytest.mark.parametrize("newer", ("schema-version", "format-row"))
def test_newer_role_refuses_pair_admission_without_reset_or_change(
    tmp_path: Path, newer: str,
) -> None:
    # The older ledger beside a newer history must not migrate either.
    data = tmp_path / "data"
    ledger = copy_released_role(data, history=False)
    history = initialize_history(data / "history.db")
    with closing(sqlite3.connect(history)) as connection:
        with connection:
            connection.execute(*(
                ("UPDATE schema_metadata SET value = '10' WHERE key = 'schema_version'",)
                if newer == "schema-version" else
                ("UPDATE schema_metadata SET value = ? WHERE key = 'format.event'",
                 (str(FORMAT_VERSIONS["event"] + 1),))
            ))
    before = {name: value for name, value in _entries(data).items() if not name.endswith(".claim")}

    contract = validate_database_pair(ledger, history)
    assert (contract.state, contract.reason) == (DatabasePairState.REFUSED, "history-newer")
    assert contract.reset_direction is None
    assert "newer NamiSync" in contract.guidance
    assert not re.search(r"delete|archive|reset", contract.guidance, re.IGNORECASE)
    assert {name: value for name, value in _entries(data).items() if not name.endswith(".claim")} == before

    with pytest.raises(DatabasePairRefusedError, match="newer NamiSync"):
        ensure_database_pair(ledger, history)
    migration = migrate_database_pair(ledger, history)
    assert (migration.contract, migration.backups) == (contract, ())
    assert _classify(ledger, history=False) == "older"
    assert {name: value for name, value in _entries(data).items() if not name.endswith(".claim")} == before


def test_ensure_migrates_before_any_owner_opens_and_refuses_after(tmp_path: Path) -> None:
    data = tmp_path / "data"
    ledger = initialize_ledger(data / "ledger.db")
    history = copy_released_role(data, history=True)
    owner = DatabaseConnectionOwner(ledger, history=False)
    try:
        before = _bytes(ledger, history)
        with pytest.raises(DatabasePairRefusedError, match="Start NamiSync") as raised:
            ensure_database_pair(ledger, history, ledger_database=owner)
        assert raised.value.contract.state is DatabasePairState.MIGRATION_REQUIRED
        assert _bytes(ledger, history) == before
        assert not list(data.glob("*.backup-*"))
    finally:
        owner.close()

    old = carried_rows(history, tmp_path / "old", history=True)
    assert ensure_database_pair(ledger, history).state is DatabasePairState.READY
    assert carried_rows(history, tmp_path / "new", history=True) == old
    # A history migrating beside an already current ledger takes its instance.
    instance_id = _assert_migrated(ledger, history)
    assert instance_id == _metadata(ledger)["instance_id"]


@pytest.mark.parametrize("released", (True, False), ids=("released", "current"))
def test_swapped_pair_is_refused_as_swapped_and_nothing_is_written(
    tmp_path: Path, released: bool,
) -> None:
    data = tmp_path / "data"
    if released:
        ledger, history = copy_released_pair(data)
    else:
        ledger = initialize_ledger(data / "ledger.db")
        history = initialize_history(data / "history.db")
    before = {name: value for name, value in _entries(data).items() if not name.endswith(".claim")}

    for classify in (
        lambda: validate_database_pair(history, ledger),
        lambda: _runtime_contract(history, ledger),
    ):
        contract = classify()
        assert (contract.state, contract.reason) == (DatabasePairState.REFUSED, "ledger-wrong-role")
        assert contract.reset_direction is None
        assert "look swapped" in contract.guidance
        assert not re.search(r"newer|delete|archive|reset", contract.guidance, re.IGNORECASE)
    with pytest.raises(DatabasePairRefusedError, match="look swapped"):
        ensure_database_pair(history, ledger)
    assert {
        name: value for name, value in _entries(data).items() if not name.endswith(".claim")
    } == before