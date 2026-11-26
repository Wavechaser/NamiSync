"""Ledger restore lineage: storage, the hand-copied backup refusal, the read rule.

Lineage rows are inserted directly (``add_ledger_lineage``), so each case
states the row it needs without a backup or restore. A backup carries a
``backup-cut`` row naming its own instance, and restore always issues a new
one; a live ledger whose lineage names its own instance can only be a backup
copied into place.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

import pytest

import namisync.db.schema as schema_module
import namisync.workflows.runtime as runtime_module
from namisync.db.contracts import (
    DatabaseConnectionOwner,
    probe_database_file_contract,
    require_database_file_contract,
)
from namisync.db.recorder import LedgerRecorder
from namisync.db.repositories import LedgerCut, LedgerLineage, LedgerRepository
from namisync.db.schema import (
    LEDGER_SCHEMA_VERSION,
    DatabaseNewerVersion,
    LedgerIsBackup,
    SchemaResetRequired,
    classify_database,
    initialize_history,
    initialize_ledger,
    new_instance_id,
    validate_ledger_reader_contract,
)
from namisync.workflows.database_pair import (
    DatabasePairRefusedError,
    DatabasePairState,
    ensure_database_pair,
    upgrade_database_pair,
    validate_database_pair,
)
from namisync.workflows.runtime import LocalWorkflowRuntime

from _db_fixtures import (
    NOW,
    FakeClock,
    add_ledger_lineage,
    seed_history_run,
    stored_ledger_instance,
)
from _released_fixture import copy_released_pair


UTC = timezone.utc
_CUT_A = datetime(2026, 1, 10, tzinfo=UTC)
_CUT_B = datetime(2026, 2, 10, tzinfo=UTC)


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes() for path in directory.iterdir()
        if path.is_file() and not path.name.endswith(".claim")
    }


def _topology(main: Path) -> list[tuple]:
    with closing(sqlite3.connect(main.as_uri() + "?mode=ro", uri=True)) as connection:
        return schema_module._schema_topology(connection)


def _lineage_rows(main: Path) -> list[tuple]:
    with closing(sqlite3.connect(main.as_uri() + "?mode=ro", uri=True)) as connection:
        return connection.execute("SELECT * FROM ledger_lineage").fetchall()


def _pair(directory: Path) -> tuple[Path, Path]:
    return (
        initialize_ledger(directory / "ledger.db"),
        initialize_history(directory / "history.db"),
    )


@pytest.fixture
def backup_pair(tmp_path: Path) -> tuple[Path, Path]:
    """A current pair whose ledger is a backup copied into place by hand."""

    ledger, history = _pair(tmp_path)
    add_ledger_lineage(ledger, "backup-cut", stored_ledger_instance(ledger), NOW)
    return ledger, history


def test_fresh_ledger_has_the_lineage_table_and_no_rows(tmp_path: Path) -> None:
    ledger = initialize_ledger(tmp_path / "ledger.db")

    assert ("table", "ledger_lineage", "ledger_lineage") in {
        entry[:3] for entry in _topology(ledger)
    }
    assert _lineage_rows(ledger) == []
    with LedgerRepository(ledger) as repository:
        assert repository.ledger_lineage() == LedgerLineage(stored_ledger_instance(ledger), ())


@pytest.mark.skipif(os.name != "nt", reason="Windows file sharing and claims")
def test_migrated_released_ledger_has_the_fresh_topology_and_no_lineage(
    tmp_path: Path,
) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")

    assert upgrade_database_pair(ledger, history).contract.state is DatabasePairState.READY

    assert _topology(ledger) == _topology(initialize_ledger(tmp_path / "fresh.db"))
    assert _lineage_rows(ledger) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows file sharing and claims")
def test_a_ledger_with_the_withdrawn_marker_kind_is_refused_with_reset(
    tmp_path: Path,
) -> None:
    # Schema 5 was amended in place again: a ledger a source-tree run created
    # or migrated while the lineage CHECK allowed 'migrated-released' fails
    # the exact topology check, marker row or not.
    amended = schema_module._LEDGER_STATEMENTS[-1].replace(
        "'backup-cut', 'replaced-missing'",
        "'backup-cut', 'replaced-missing', 'migrated-released'",
    )
    assert amended != schema_module._LEDGER_STATEMENTS[-1]
    ledger = tmp_path / "ledger.db"
    with closing(sqlite3.connect(ledger, isolation_level=None)) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        for statement in (*schema_module._LEDGER_STATEMENTS[:-1], amended):
            connection.execute(statement)
        connection.executemany(
            "INSERT INTO schema_metadata(key, value) VALUES (?, ?)",
            schema_module._metadata_rows(False, new_instance_id()),
        )
        connection.execute(
            "INSERT INTO ledger_lineage(kind, instance_id, at) "
            "VALUES ('migrated-released', NULL, '2026-11-25T00:00:00.000000Z')"
        )
    history = initialize_history(tmp_path / "history.db")
    before = _files(tmp_path)

    with pytest.raises(SchemaResetRequired, match="unsupported ledger schema topology"):
        probe_database_file_contract(ledger, history=False)
    contract = validate_database_pair(ledger, history)
    assert (contract.state, contract.reason) == (DatabasePairState.REFUSED, "ledger-contract")
    assert contract.reset_direction is not None
    assert upgrade_database_pair(ledger, history).contract == contract
    assert _files(tmp_path) == before


@pytest.mark.parametrize(("kind", "instance_id", "at"), [
    ("other", "a" * 32, "2026-01-01T00:00:00.000000Z"),
    ("backup-cut", None, "2026-01-01T00:00:00.000000Z"),
    ("replaced-missing", "a" * 32, "2026-01-01T00:00:00.000000Z"),
    ("migrated-released", None, "2026-01-01T00:00:00.000000Z"),
    ("backup-cut", "A" * 32, "2026-01-01T00:00:00.000000Z"),
    ("backup-cut", "a" * 31, "2026-01-01T00:00:00.000000Z"),
    ("backup-cut", "a" * 33, "2026-01-01T00:00:00.000000Z"),
    ("backup-cut", "g" * 32, "2026-01-01T00:00:00.000000Z"),
    ("backup-cut", "a" * 32, None),
    (None, None, "2026-01-01T00:00:00.000000Z"),
])
def test_lineage_rows_are_checked_by_the_schema(
    tmp_path: Path, kind: str | None, instance_id: str | None, at: str | None,
) -> None:
    ledger = initialize_ledger(tmp_path / "ledger.db")
    with closing(sqlite3.connect(ledger)) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO ledger_lineage(kind, instance_id, at) VALUES (?, ?, ?)",
                (kind, instance_id, at),
            )


def test_lineage_instance_is_unique_and_boundaries_carry_none(tmp_path: Path) -> None:
    ledger = initialize_ledger(tmp_path / "ledger.db")
    add_ledger_lineage(ledger, "backup-cut", "a" * 32, _CUT_A)
    add_ledger_lineage(ledger, "replaced-missing", None, _CUT_A)
    add_ledger_lineage(ledger, "replaced-missing", None, _CUT_B)
    with pytest.raises(sqlite3.IntegrityError):
        add_ledger_lineage(ledger, "backup-cut", "a" * 32, _CUT_B)

    with LedgerRepository(ledger) as repository:
        # A boundary joins nothing, so only cuts are read.
        assert repository.ledger_lineage().cuts == (LedgerCut("a" * 32, _CUT_A),)


def test_old_shape_schema_5_ledger_is_refused_as_reset_required_unchanged(
    tmp_path: Path,
) -> None:
    # Ledger schema 5 as a source-tree run since M2-A3 made it: no lineage table.
    ledger, history = _pair(tmp_path)
    with closing(sqlite3.connect(ledger)) as connection, connection:
        connection.execute("DROP TABLE ledger_lineage")
    before = _files(tmp_path)

    with pytest.raises(SchemaResetRequired, match="schema topology"):
        probe_database_file_contract(ledger, history=False)
    contract = validate_database_pair(ledger, history)

    assert (contract.state, contract.reason) == (DatabasePairState.REFUSED, "ledger-contract")
    assert contract.reset_direction is not None
    assert _files(tmp_path) == before


def _assert_backup_refusal(contract) -> None:
    assert (contract.state, contract.reason) == (DatabasePairState.REFUSED, "ledger-is-backup")
    assert contract.reset_direction is None
    assert "namisync restore ledger <backup file>" in contract.guidance
    assert "Put back the ledger it replaced" in contract.guidance
    for word in ("delete", "archive", "reset"):
        assert word not in contract.guidance.lower()


def test_backup_copied_into_place_is_refused_at_every_admission_without_change(
    backup_pair: tuple[Path, Path], tmp_path: Path,
) -> None:
    ledger, history = backup_pair
    before = _files(tmp_path)

    with pytest.raises(LedgerIsBackup):
        probe_database_file_contract(ledger, history=False)
    with pytest.raises(LedgerIsBackup):
        require_database_file_contract(ledger, history=False)
    with pytest.raises(LedgerIsBackup):
        DatabaseConnectionOwner(ledger, history=False)
    with pytest.raises(LedgerIsBackup):
        LedgerRepository(ledger)
    with pytest.raises(LedgerIsBackup):
        LedgerRecorder(ledger, clock=FakeClock())
    _assert_backup_refusal(validate_database_pair(ledger, history))
    with pytest.raises(DatabasePairRefusedError) as refused:
        ensure_database_pair(ledger, history)
    _assert_backup_refusal(refused.value.contract)
    with closing(LocalWorkflowRuntime(ledger, history)) as runtime:
        _assert_backup_refusal(runtime.validate_database_contracts())

    assert _files(tmp_path) == before


@pytest.mark.skipif(os.name != "nt", reason="Windows file sharing and claims")
def test_maintenance_classification_refuses_a_backup_and_migrates_nothing(
    backup_pair: tuple[Path, Path], tmp_path: Path,
) -> None:
    ledger, history = backup_pair
    before = _files(tmp_path)

    result = upgrade_database_pair(ledger, history)

    _assert_backup_refusal(result.contract)
    assert result.migrated == ()
    assert _files(tmp_path) == before


def test_live_owner_refuses_a_backup_that_replaces_its_contents(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    owner = DatabaseConnectionOwner(ledger, history=False)
    try:
        add_ledger_lineage(ledger, "backup-cut", stored_ledger_instance(ledger), NOW)

        # Typed, not wrapped as an unavailable database.
        with pytest.raises(LedgerIsBackup):
            owner.validate()
        _assert_backup_refusal(validate_database_pair(ledger, history, ledger_database=owner))
    finally:
        owner.close()


def test_backup_file_classifies_current_and_is_refused_only_after_the_rest(
    backup_pair: tuple[Path, Path],
) -> None:
    # The seam restore's backup verification uses: classification never
    # applies the live-ledger rule, and the reader contract applies it last.
    ledger, _ = backup_pair
    with closing(sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True)) as connection:
        assert classify_database(connection, history=False) == LEDGER_SCHEMA_VERSION
        with pytest.raises(LedgerIsBackup):
            validate_ledger_reader_contract(connection)

    with closing(sqlite3.connect(ledger)) as connection, connection:
        connection.execute("CREATE INDEX extra_idx ON ledger_lineage(at)")
    with pytest.raises(SchemaResetRequired):
        probe_database_file_contract(ledger, history=False)
    with closing(sqlite3.connect(ledger)) as connection, connection:
        connection.execute("DROP INDEX extra_idx")
        connection.execute("UPDATE schema_metadata SET value = '99' WHERE key = 'format.event'")
    with pytest.raises(DatabaseNewerVersion):
        probe_database_file_contract(ledger, history=False)


def test_ledger_with_only_other_instances_cuts_is_admitted(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    ancestor = new_instance_id()
    add_ledger_lineage(ledger, "backup-cut", ancestor, _CUT_A)
    add_ledger_lineage(ledger, "replaced-missing", None, _CUT_B)

    probe_database_file_contract(ledger, history=False)
    assert validate_database_pair(ledger, history).state is DatabasePairState.READY
    with LedgerRepository(ledger) as repository:
        assert repository.ledger_lineage() == LedgerLineage(
            stored_ledger_instance(ledger), (LedgerCut(ancestor, _CUT_A),),
        )


def _day(month: int, day: int) -> datetime:
    return datetime(2026, month, day, tzinfo=UTC)


def _membership(runtime: LocalWorkflowRuntime, **options) -> dict[str, str]:
    listed = {run.run_token: run.ledger_membership for run in runtime.list_history(50, **options)}
    detailed = {
        token: runtime.get_history_summary(token, **options).ledger_membership
        for token in listed
    }
    assert detailed == listed
    return listed


def test_runs_join_the_ledger_through_its_ancestor_chain(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    current = stored_ledger_instance(ledger)
    a, b, unrelated = new_instance_id(), new_instance_id(), new_instance_id()
    # A backup of ledger A was restored as B; a backup of B became this ledger.
    add_ledger_lineage(ledger, "backup-cut", a, _CUT_A)
    add_ledger_lineage(ledger, "backup-cut", b, _CUT_B)
    runs = {
        "current": (current, _day(3, 1), _day(3, 1)),
        "no-instance": (None, _day(1, 5), _day(1, 5)),
        "unrelated": (unrelated, _day(1, 5), _day(1, 5)),
        "a-before-cut": (a, _day(1, 5), _day(1, 5)),
        "a-at-cut": (a, _day(1, 9), _CUT_A),
        "a-after-cut": (a, _day(1, 15), _day(1, 15)),
        "a-created-before-started-after": (a, _day(1, 9), _day(1, 11)),
        "a-never-started-before": (a, _day(1, 5), None),
        "a-never-started-after": (a, _day(1, 15), None),
        "b-before-cut": (b, _day(2, 1), _day(2, 1)),
        "b-after-cut": (b, _day(2, 20), _day(2, 20)),
    }
    for token, (instance_id, created_at, started_at) in runs.items():
        seed_history_run(
            history, token, ledger_instance_id=instance_id,
            created_at=created_at, started_at=started_at,
        )

    with closing(LocalWorkflowRuntime(ledger, history)) as runtime:
        assert _membership(runtime) == {
            "current": "current",
            "no-instance": "earlier",
            "unrelated": "earlier",
            "a-before-cut": "current",
            "a-at-cut": "earlier",
            "a-after-cut": "earlier",
            "a-created-before-started-after": "earlier",
            "a-never-started-before": "current",
            "a-never-started-after": "earlier",
            "b-before-cut": "current",
            "b-after-cut": "earlier",
        }


@pytest.mark.parametrize("ledger_state", ("missing", "damaged", "backup", "old-shape"))
def test_history_is_listed_with_unknown_membership_without_a_usable_ledger(
    tmp_path: Path, ledger_state: str,
) -> None:
    ledger, history = _pair(tmp_path)
    instance_id = stored_ledger_instance(ledger)
    seed_history_run(
        history, "run", ledger_instance_id=instance_id, created_at=NOW, started_at=NOW,
    )
    if ledger_state == "missing":
        ledger.unlink()
    elif ledger_state == "damaged":
        ledger.write_bytes(b"not a SQLite database")
    elif ledger_state == "backup":
        add_ledger_lineage(ledger, "backup-cut", instance_id, NOW)
    else:
        with closing(sqlite3.connect(ledger)) as connection, connection:
            connection.execute("DROP TABLE ledger_lineage")
    before = _files(tmp_path)

    with closing(LocalWorkflowRuntime(ledger, history)) as runtime:
        assert _membership(runtime) == {"run": "unknown"}

    # The live History reader may add its own sidecars; the ledger is untouched.
    after = _files(tmp_path)
    assert {name: value for name, value in after.items() if name.startswith("ledger")} == {
        name: value for name, value in before.items() if name.startswith("ledger")
    }


def test_history_read_without_the_ledger_never_opens_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = _pair(tmp_path)
    seed_history_run(
        history, "run", ledger_instance_id=stored_ledger_instance(ledger),
        created_at=NOW, started_at=NOW,
    )
    adopted: list[bool] = []
    owner = runtime_module.DatabaseConnectionOwner

    def adopt(path, *, history):
        adopted.append(history)
        return owner(path, history=history)

    monkeypatch.setattr(runtime_module, "DatabaseConnectionOwner", adopt)

    with closing(LocalWorkflowRuntime(ledger, history)) as runtime:
        assert _membership(runtime, read_ledger=False) == {"run": "unknown"}
        assert adopted == [True]
        assert _membership(runtime) == {"run": "current"}
        assert adopted == [True, False]
