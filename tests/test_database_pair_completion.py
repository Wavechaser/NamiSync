"""One-present pairs: a lone ledger gains a History, a lone History a new ledger.

Released databases are copies of ``tests/assets/v0_1_0/``. Concurrency and
death use real child processes that run the real completion and are killed
from the parent once their own script reports the stage it stopped at.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
import os
from pathlib import Path
import re
import sqlite3
from time import monotonic, sleep

import pytest

from namisync.core.planning import OperationKind
from namisync.db.contracts import probe_database_file_contract
from namisync.db.schema import DatabaseMigrationRequired, initialize_history, initialize_ledger
import namisync.workflows.database_pair as database_pair
from namisync.workflows.database_pair import (
    CreatedDatabase,
    DatabasePairRefusedError,
    DatabasePairState,
    upgrade_database_pair,
    ensure_database_pair,
    validate_database_pair,
)
from namisync.workflows.runtime import LocalWorkflowRuntime

from _child_process import WAIT_SECONDS, Child
from _db_fixtures import NOW, file_stat, operation, plan, seed_history_run, setup_recorder
from _released_fixture import carried_rows, copy_released_pair, copy_released_role


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows file sharing and claims")

_INSTANCE = re.compile("[0-9a-f]{32}")
_AT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z")
_INTERRUPTED = r"""
import sys, time
import namisync.db.maintenance as maintenance
import namisync.workflows.database_pair as pair

ledger, history, stage = sys.argv[1:4]


def hang():
    print("stopped", flush=True)
    time.sleep(120)


def stop(module, name, *, after):
    original = getattr(module, name)

    def wrapped(*args, **kwargs):
        if not after:
            hang()
        result = original(*args, **kwargs)
        hang()
        return result

    setattr(module, name, wrapped)


if stage == "migrated":
    stop(pair, "migrate_database", after=True)
elif stage == "mid-image":
    # Inside the image's creation transaction, before its metadata.
    stop(maintenance, "_metadata_rows", after=False)
elif stage == "image-written":
    stop(maintenance, "_write_new_image", after=True)
elif stage == "published":
    stop(pair, "create_database", after=True)
print("ready", flush=True)
result = pair.upgrade_database_pair(ledger, history, create=True)
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


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes() for path in directory.iterdir()
        if path.is_file() and not path.name.endswith(".claim")
    }


def _bytes(*mains: Path) -> dict[str, bytes | None]:
    return {
        f"{main.name}{suffix}": (
            Path(f"{main}{suffix}").read_bytes() if Path(f"{main}{suffix}").exists() else None
        )
        for main in mains
        for suffix in ("", "-wal")
    }


def _classify(main: Path, *, history: bool) -> str:
    try:
        probe_database_file_contract(main, history=history)
    except DatabaseMigrationRequired:
        return "older"
    return "current"


def _read(main: Path, sql: str) -> list[tuple]:
    with closing(sqlite3.connect(main.as_uri() + "?mode=ro", uri=True)) as connection:
        return connection.execute(sql).fetchall()


def _instance(ledger: Path) -> str:
    return _read(ledger, "SELECT value FROM schema_metadata WHERE key = 'instance_id'")[0][0]


def _membership(ledger: Path, history: Path) -> dict[str, str]:
    with closing(LocalWorkflowRuntime(ledger, history)) as runtime:
        return {run.run_token: run.ledger_membership for run in runtime.list_history(50)}


def _assert_new_ledger(ledger: Path) -> str:
    """A normal WAL-header main with no sidecars, a new id and one boundary row."""

    header = ledger.read_bytes()[:100]
    assert header[:16] == b"SQLite format 3\x00" and header[18:20] == b"\x02\x02"
    assert not any(Path(f"{ledger}{suffix}").exists() for suffix in ("-wal", "-journal"))
    instance_id = _instance(ledger)
    assert _INSTANCE.fullmatch(instance_id)
    ((kind, lineage_instance, at),) = _read(ledger, "SELECT kind, instance_id, at FROM ledger_lineage")
    assert (kind, lineage_instance) == ("replaced-missing", None) and _AT.fullmatch(at)
    for table in ("locations", "inventory", "runs", "mappings"):
        assert _read(ledger, f"SELECT count(*) FROM {table}") == [(0,)]
    return instance_id


def _complete_eventually(ledger: Path, history: Path):
    # A killed holder's locks and handles may outlive it briefly on Windows.
    deadline = monotonic() + WAIT_SECONDS
    while True:
        result = upgrade_database_pair(ledger, history, create=True)
        if result.contract.reason != "database-in-use" or monotonic() > deadline:
            return result
        sleep(0.05)


def _current_ledger_with_a_run(directory: Path) -> Path:
    ledger = initialize_ledger(directory / "ledger.db")
    copy = operation(OperationKind.COPY, source=file_stat(), target=None)
    setup_recorder(ledger, plan((copy,))).recorder.close()
    return ledger


# --- classification and admission ----------------------------------------------


def test_admission_never_completes_and_classification_writes_nothing(tmp_path: Path) -> None:
    ledger = _current_ledger_with_a_run(tmp_path)
    history = tmp_path / "history.db"
    for name in ("source", "target"):
        (tmp_path / name).mkdir()
    before = sorted(path.name for path in tmp_path.iterdir()), _files(tmp_path)

    contract = validate_database_pair(ledger, history)
    assert (contract.state, contract.reason) == (DatabasePairState.INCOMPLETE, "history-missing")
    with pytest.raises(DatabasePairRefusedError, match="History database is missing") as raised:
        ensure_database_pair(ledger, history)
    assert raised.value.contract == contract
    with closing(LocalWorkflowRuntime(ledger, history)) as runtime:
        assert runtime.validate_database_contracts() == contract
        request = runtime.create_plan_request(
            "request-1", str(tmp_path / "source"), str(tmp_path / "target"),
        )
        with pytest.raises(DatabasePairRefusedError) as raised:
            runtime.prepare_plan(request)
        assert raised.value.contract.state is DatabasePairState.INCOMPLETE
    # Nothing written, no claim file either.
    assert (sorted(path.name for path in tmp_path.iterdir()), _files(tmp_path)) == before


@pytest.mark.parametrize("present", ("ledger", "history"))
def test_orphan_sidecars_of_the_missing_role_stay_inconsistent(
    tmp_path: Path, present: str,
) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    (initialize_ledger if present == "ledger" else initialize_history)(
        ledger if present == "ledger" else history
    )
    Path(f"{history if present == 'ledger' else ledger}-shm").write_bytes(b"orphan")
    files = _files(tmp_path)

    contract = validate_database_pair(ledger, history)
    assert (contract.state, contract.reason) == (DatabasePairState.REFUSED, "inconsistent-pair")
    completion = upgrade_database_pair(ledger, history, create=True)
    assert (completion.contract, completion.created) == (contract, ())
    assert _files(tmp_path) == files


@pytest.mark.parametrize("present", ("ledger", "history"))
def test_a_lone_main_with_its_own_journal_stays_inconsistent(
    tmp_path: Path, present: str,
) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    main = (initialize_ledger if present == "ledger" else initialize_history)(
        ledger if present == "ledger" else history
    )
    Path(f"{main}-journal").write_bytes(b"")
    files = _files(tmp_path)

    contract = validate_database_pair(ledger, history)
    assert (contract.state, contract.reason) == (DatabasePairState.REFUSED, "inconsistent-pair")
    completion = upgrade_database_pair(ledger, history, create=True)
    assert (completion.contract, completion.created) == (contract, ())
    assert _files(tmp_path) == files


def test_a_lone_database_needing_a_reset_names_only_itself_and_where_the_other_was(
    tmp_path: Path,
) -> None:
    ledger = initialize_ledger(tmp_path / "ledger.db")
    history = tmp_path / "history.db"
    with closing(sqlite3.connect(ledger)) as connection, connection:
        connection.execute("DELETE FROM schema_metadata WHERE key = 'format.numeric'")
    files = _files(tmp_path)

    contract = validate_database_pair(ledger, history)

    assert (contract.state, contract.reason) == (DatabasePairState.REFUSED, "ledger-contract")
    assert contract.guidance == contract.reset_direction
    assert f"archive or delete the ledger database file {ledger} and its" in contract.guidance
    assert f"The history database is missing at {history}" in contract.guidance
    assert "both" not in contract.guidance
    assert upgrade_database_pair(ledger, history, create=True).created == ()
    assert _files(tmp_path) == files


def _discarding(guidance: str) -> list[str]:
    """The sentences of a direction that tell the user to discard something."""

    return [sentence for sentence in guidance.split(". ") if re.search("archive|delete", sentence)]


@pytest.mark.parametrize("peer", ("current", "released"))
@pytest.mark.parametrize("role", ("ledger", "history"))
def test_a_reset_beside_a_usable_database_names_only_itself_and_keeps_the_other(
    tmp_path: Path, role: str, peer: str,
) -> None:
    # A zero-byte main beside a healthy database (user report, 2026-11-26):
    # following the direction must never discard the healthy one.
    other = "history" if role == "ledger" else "ledger"
    if peer == "current":
        kept = (initialize_history if other == "history" else initialize_ledger)(
            tmp_path / f"{other}.db"
        ).resolve()
    else:
        kept = copy_released_role(tmp_path, history=other == "history").resolve()
    unusable = (tmp_path / f"{role}.db").resolve()
    unusable.touch()
    ledger, history = (unusable, kept) if role == "ledger" else (kept, unusable)
    files = _files(tmp_path)

    contract = validate_database_pair(ledger, history)

    assert (contract.state, contract.reason) == (DatabasePairState.REFUSED, f"{role}-contract")
    guidance = contract.guidance
    assert guidance == contract.reset_direction
    discarding = _discarding(guidance)
    assert len(discarding) == 1
    assert f"the {role} database file {unusable} and its" in discarding[0]
    assert str(kept) not in discarding[0] and "both" not in guidance
    assert f"Keep the {other} database {kept} as it is." in guidance
    # Only its contract was read, not its integrity: no claim about its health.
    assert not re.search(r"\b(usable|healthy)\b", guidance)
    assert f"once to create a new {role}" in guidance
    assert ("earlier ledger" in guidance) is (role == "ledger")
    assert ("written by NamiSync 0.1.0" in guidance) is (peer == "released")
    assert f"namisync restore {role} <backup file>" in guidance
    with pytest.raises(DatabasePairRefusedError) as raised:
        ensure_database_pair(ledger, history)
    assert guidance in str(raised.value)
    assert _files(tmp_path) == files

    # Following it: the unusable file archived, the next start creates a new one
    # beside the kept database.
    unusable.rename(tmp_path / "archived.db")
    assert validate_database_pair(ledger, history).reason == f"{role}-missing"
    upgraded = upgrade_database_pair(ledger, history, create=True)
    assert upgraded.created == (CreatedDatabase(role, unusable),)
    assert upgraded.contract.state is DatabasePairState.READY
    if peer == "current":
        assert kept.read_bytes() == files[kept.name]


@pytest.mark.parametrize("peer", ("damaged", "is-backup"))
def test_a_reset_beside_an_unusable_ledger_reports_the_ledger_and_discards_nothing(
    tmp_path: Path, peer: str,
) -> None:
    from _db_fixtures import add_ledger_lineage, stored_ledger_instance

    ledger = initialize_ledger(tmp_path / "ledger.db")
    if peer == "damaged":
        data = bytearray(ledger.read_bytes())
        data[100:612] = b"\xa5" * 512
        ledger.write_bytes(bytes(data))
    else:
        add_ledger_lineage(ledger, "backup-cut", stored_ledger_instance(ledger), NOW)
    history = tmp_path / "history.db"
    history.touch()

    contract = validate_database_pair(ledger, history)

    assert contract.reason == ("database-damaged" if peer == "damaged" else "ledger-is-backup")
    assert contract.reset_direction is None
    assert _discarding(contract.guidance) == []


def test_upgrade_returns_a_fresh_or_ready_pair_unchanged_without_a_claim(tmp_path: Path) -> None:
    fresh_ledger, fresh_history = tmp_path / "fresh" / "ledger.db", tmp_path / "fresh" / "history.db"
    result = upgrade_database_pair(fresh_ledger, fresh_history, create=True)
    assert (result.contract.state, result.migrated, result.created) == (
        DatabasePairState.FRESH, (), (),
    )
    assert not (tmp_path / "fresh").exists()

    ledger = initialize_ledger(tmp_path / "ledger.db")
    history = initialize_history(tmp_path / "history.db")
    before = sorted(path.name for path in tmp_path.iterdir())
    result = upgrade_database_pair(ledger, history, create=True)
    assert (result.contract.state, result.migrated, result.created) == (
        DatabasePairState.READY, (), (),
    )
    assert sorted(path.name for path in tmp_path.iterdir()) == before


# --- a lone ledger -------------------------------------------------------------


def test_lone_current_ledger_gains_a_history_and_is_left_as_it_was(tmp_path: Path) -> None:
    ledger = _current_ledger_with_a_run(tmp_path)
    history = tmp_path / "history.db"
    before = _bytes(ledger)

    result = upgrade_database_pair(ledger, history, create=True)

    assert result.contract.state is DatabasePairState.READY
    assert (result.created, result.migrated) == ((CreatedDatabase("history", history),), ())
    assert _bytes(ledger) == before
    assert _classify(history, history=True) == "current"
    assert history.read_bytes()[18:20] == b"\x02\x02"
    assert not any(Path(f"{history}{suffix}").exists() for suffix in ("-wal", "-journal"))
    assert _read(history, "SELECT count(*) FROM history_runs") == [(0,)]
    assert not list(tmp_path.glob("*.tmp"))
    again = upgrade_database_pair(ledger, history, create=True)
    assert (again.contract.state, again.created) == (DatabasePairState.READY, ())


def test_lone_released_ledger_migrates_and_gains_a_new_history(tmp_path: Path) -> None:
    ledger = copy_released_role(tmp_path / "data", history=False)
    history = tmp_path / "data" / "history.db"
    old = carried_rows(ledger, tmp_path / "old", history=False)
    contract = validate_database_pair(ledger, history)
    assert (contract.state, contract.reason) == (DatabasePairState.INCOMPLETE, "history-missing")
    assert "written by NamiSync 0.1.0 and is updated first" in contract.guidance

    result = upgrade_database_pair(ledger, history, create=True)

    assert result.contract.state is DatabasePairState.READY
    assert result.created == (CreatedDatabase("history", history),)
    ((role, version, backup),) = (
        (database.role, database.source_version, database.backup) for database in result.migrated
    )
    assert (role, version) == ("ledger", 4) and backup.exists()
    assert carried_rows(ledger, tmp_path / "new", history=False) == old
    assert _INSTANCE.fullmatch(_instance(ledger))
    # The kept ledger records no boundary.
    assert _read(ledger, "SELECT kind, instance_id FROM ledger_lineage") == []
    assert _read(history, "SELECT count(*) FROM history_runs") == [(0,)]


# --- a lone History ------------------------------------------------------------


def test_lone_released_history_migrates_then_gains_a_new_ledger(tmp_path: Path) -> None:
    data = tmp_path / "data"
    history = copy_released_role(data, history=True)
    ledger = data / "ledger.db"
    old = carried_rows(history, tmp_path / "old", history=True)
    contract = validate_database_pair(ledger, history)
    assert (contract.state, contract.reason) == (DatabasePairState.INCOMPLETE, "ledger-missing")
    assert "runs are shown as belonging to an earlier ledger" in contract.guidance
    assert "written by NamiSync 0.1.0 and is updated first" in contract.guidance

    result = upgrade_database_pair(ledger, history, create=True)

    assert result.contract.state is DatabasePairState.READY, result.contract
    assert result.created == (CreatedDatabase("ledger", ledger),)
    assert [(database.role, database.source_version) for database in result.migrated] == [
        ("history", 8),
    ]
    assert carried_rows(history, tmp_path / "new", history=True) == old
    _assert_new_ledger(ledger)
    assert not list(data.glob("*.create-*"))
    # The conservative reading: this call migrated no ledger, so no run joins
    # the ledger created for it.
    assert set(_membership(ledger, history).values()) == {"earlier"}


def test_lone_current_history_gains_a_new_ledger_and_is_left_as_it_was(tmp_path: Path) -> None:
    history = tmp_path / "history.db"
    seed_history_run(history, "stamped", ledger_instance_id="a" * 32, created_at=NOW, started_at=NOW)
    seed_history_run(history, "unstamped", ledger_instance_id=None, created_at=NOW, started_at=NOW)
    ledger = tmp_path / "ledger.db"
    before = _bytes(history)

    result = upgrade_database_pair(ledger, history, create=True)

    assert result.contract.state is DatabasePairState.READY
    assert (result.created, result.migrated) == ((CreatedDatabase("ledger", ledger),), ())
    assert _bytes(history) == before
    assert _assert_new_ledger(ledger) != "a" * 32
    assert _membership(ledger, history) == {"stamped": "earlier", "unstamped": "earlier"}


# --- permission to create --------------------------------------------------------


def test_without_permission_a_lone_database_is_returned_incomplete_and_nothing_is_made(
    tmp_path: Path,
) -> None:
    ledger = copy_released_role(tmp_path / "data", history=False)
    history = tmp_path / "new" / "deeper" / "history.db"
    before = _files(tmp_path / "data")

    result = upgrade_database_pair(ledger, history, create=False)

    assert result.contract == validate_database_pair(ledger, history)
    assert (result.contract.state, result.contract.reason) == (
        DatabasePairState.INCOMPLETE, "history-missing",
    )
    assert (result.migrated, result.created) == ((), ())
    # No claim, folder, backup or migration: the directory is as found.
    assert not (tmp_path / "new").exists()
    assert sorted(path.name for path in (tmp_path / "data").iterdir()) == sorted(before)
    assert _files(tmp_path / "data") == before


@pytest.mark.parametrize("create", (False, True))
def test_a_database_that_vanishes_under_the_claims_is_created_only_with_permission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, create: bool,
) -> None:
    # Cold, both databases are from 0.1.0; under the claims the History is gone.
    data = tmp_path / "data"
    ledger, history = copy_released_pair(data)
    assert validate_database_pair(ledger, history).state is DatabasePairState.MIGRATION_REQUIRED
    hold = database_pair.hold_maintenance_claims

    @contextmanager
    def history_vanishes(*arguments):
        with hold(*arguments) as claims:
            for suffix in ("", "-wal", "-shm"):
                Path(f"{history}{suffix}").unlink()
            yield claims

    monkeypatch.setattr(database_pair, "hold_maintenance_claims", history_vanishes)
    ledger_files = {name: data.joinpath(name).read_bytes() for name in (
        "ledger.db", "ledger.db-wal", "ledger.db-shm",
    )}

    result = upgrade_database_pair(ledger, history, create=create)

    if not create:
        assert (result.contract.state, result.contract.reason) == (
            DatabasePairState.INCOMPLETE, "history-missing",
        )
        assert (result.migrated, result.created) == ((), ())
        # The ledger is not migrated: no backup, no new sidecar, every byte kept.
        assert _files(data) == ledger_files
        assert _classify(ledger, history=False) == "older"
        return
    assert result.contract.state is DatabasePairState.READY, result.contract
    assert result.created == (CreatedDatabase("history", history),)
    assert [(database.role, database.source_version) for database in result.migrated] == [
        ("ledger", 4),
    ]
    assert _classify(ledger, history=False) == "current"


# --- refusals ------------------------------------------------------------------


@pytest.mark.parametrize(("kind", "held"), [
    ("shared-claim", "present"),
    ("exclusive-claim", "missing"),
    ("sqlite-reader", "present"),
    ("desktop-pin", "present"),
])
@pytest.mark.parametrize("present_role", ("ledger", "history"))
def test_completion_refuses_while_another_process_holds_the_pair(
    tmp_path: Path, kind: str, held: str, present_role: str,
) -> None:
    # The present database is from 0.1.0: an open handle refuses its update.
    data = tmp_path / "data"
    present = copy_released_role(data, history=present_role == "history")
    missing = data / ("ledger.db" if present_role == "history" else "history.db")
    ledger, history = (present, missing) if present_role == "ledger" else (missing, present)
    child = Child(_HOLD, kind, str(present if held == "present" else missing))
    try:
        assert child.read() == "held"
        before = _bytes(present)
        files = sorted(path.name for path in data.iterdir() if not path.name.endswith(".claim"))
        result = upgrade_database_pair(ledger, history, create=True)
        assert (result.contract.state, result.contract.reason) == (
            DatabasePairState.REFUSED, "database-in-use",
        )
        assert result.contract.reset_direction is None
        assert "delete" not in result.contract.guidance.lower()
        assert (result.created, result.migrated) == ((), ())
        assert _bytes(present) == before
        assert sorted(
            path.name for path in data.iterdir() if not path.name.endswith(".claim")
        ) == files
        assert not missing.exists()
    finally:
        child.kill()
    assert _complete_eventually(ledger, history).contract.state is DatabasePairState.READY


def test_a_refused_claim_leaves_no_new_folder_and_a_later_call_creates_it(
    tmp_path: Path,
) -> None:
    ledger = _current_ledger_with_a_run(tmp_path)
    history = tmp_path / "new" / "deeper" / "history.db"
    child = Child(_HOLD, "shared-claim", str(ledger))
    try:
        assert child.read() == "held"
        result = upgrade_database_pair(ledger, history, create=True)
        assert (result.contract.reason, result.created) == ("database-in-use", ())
        assert not (tmp_path / "new").exists()
    finally:
        child.kill()
    result = _complete_eventually(ledger, history)
    assert result.contract.state is DatabasePairState.READY
    assert result.created == (CreatedDatabase("history", history),)


def test_a_reader_beside_a_current_lone_ledger_does_not_stop_completion(tmp_path: Path) -> None:
    # A current database is not changed, so its readers need not close.
    ledger = _current_ledger_with_a_run(tmp_path)
    history = tmp_path / "history.db"
    child = Child(_HOLD, "sqlite-reader", str(ledger))
    try:
        assert child.read() == "held"
        result = upgrade_database_pair(ledger, history, create=True)
    finally:
        child.kill()
    assert result.contract.state is DatabasePairState.READY
    assert result.created == (CreatedDatabase("history", history),)


def test_a_file_that_takes_the_missing_name_is_never_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import namisync.db.maintenance as maintenance

    ledger = _current_ledger_with_a_run(tmp_path)
    history = tmp_path / "history.db"
    write = maintenance._write_new_image

    def write_then_occupy(*arguments, **keywords) -> None:
        write(*arguments, **keywords)
        history.write_bytes(b"appeared meanwhile")

    monkeypatch.setattr(maintenance, "_write_new_image", write_then_occupy)
    result = upgrade_database_pair(ledger, history, create=True)

    assert (result.contract.reason, result.created) == ("creation-failed", ())
    assert "none was created" in result.contract.guidance
    assert history.read_bytes() == b"appeared meanwhile"
    assert not list(tmp_path.glob("*.create-*"))


# --- kill trials ---------------------------------------------------------------


_KILLS = {
    # (present database, stage): (present state, missing created) after the kill
    ("released-history", "migrated"): ("current", False),
    ("released-history", "mid-image"): ("current", False),
    ("released-history", "image-written"): ("current", False),
    ("released-history", "published"): ("current", True),
    ("released-ledger", "migrated"): ("current", False),
    ("current-ledger", "mid-image"): ("current", False),
    ("current-ledger", "image-written"): ("current", False),
    ("current-ledger", "published"): ("current", True),
}


@pytest.mark.parametrize(("shape", "stage"), tuple(_KILLS))
def test_killed_completion_leaves_the_database_missing_or_complete_and_a_rerun_finishes(
    tmp_path: Path, shape: str, stage: str,
) -> None:
    data = tmp_path / "data"
    if shape == "current-ledger":
        data.mkdir()
        present = _current_ledger_with_a_run(data)
    else:
        present = copy_released_role(data, history=shape == "released-history")
    present_history = shape == "released-history"
    old = carried_rows(present, tmp_path / "old", history=present_history)
    ledger, history = (
        (data / "ledger.db", present) if present_history else (present, data / "history.db")
    )
    missing = ledger if present_history else history
    child = Child(_INTERRUPTED, str(ledger), str(history), stage)
    try:
        assert child.read() == "ready"
        assert child.read() == "stopped"
    finally:
        child.kill()

    present_state, created = _KILLS[(shape, stage)]
    assert _classify(present, history=present_history) == present_state
    assert carried_rows(present, tmp_path / "killed", history=present_history) == old
    contract = validate_database_pair(ledger, history)
    # Never a reset, never an empty or partial main at the missing name.
    assert contract.reset_direction is None
    if created:
        assert contract.state is DatabasePairState.READY, contract
    else:
        assert not missing.exists()
        assert (contract.state, contract.reason) == (
            DatabasePairState.INCOMPLETE, f"{'ledger' if present_history else 'history'}-missing",
        )
    temporaries = sorted(path.name for path in data.glob("*.create-*"))
    assert len(list(data.glob("*.create-*.tmp"))) == (
        1 if stage in ("mid-image", "image-written") else 0
    )
    # Mid-creation the image's own rollback journal sits beside it, never
    # beside the missing main.
    assert len(list(data.glob("*.create-*.tmp-journal"))) == (1 if stage == "mid-image" else 0)

    result = _complete_eventually(ledger, history)

    assert result.contract.state is DatabasePairState.READY, result.contract
    assert carried_rows(present, tmp_path / "finished", history=present_history) == old
    if present_history:
        _assert_new_ledger(ledger)
    # A crash's temporary is neither removed nor reused.
    assert sorted(path.name for path in data.glob("*.create-*")) == temporaries
