"""Pair maintenance under both exclusive claims: refusals, kills, readers, a desktop.

Restore trials run the real workflow in a child process that stops at a named
stage and is killed from here; every trial then finds the old or the new
database, never a mix, and a rerun finishes.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import io
import os
from pathlib import Path
import re
import shutil
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep

import pytest

import namisync.db.maintenance as maintenance
from namisync.core.planning import OperationKind
from namisync.db.claims import hold_maintenance_claims
from namisync.db.contracts import DatabaseDamagedError, probe_database_file_contract
from namisync.db.maintenance import DatabaseCheckState, backup_database
from namisync.db.migration import _BackupVerificationFailed
from namisync.core.session import SessionAdmissionRefused
from namisync.interfaces.cli import EXIT_REFUSED, EXIT_SUCCESS, main
from namisync.interfaces.service import NamiSyncService
from namisync.workflows.database_maintenance import (
    backup_database_pair,
    check_database_pair,
    restore_database_from_backup,
)
from namisync.workflows.database_pair import (
    DatabasePairState,
    upgrade_database_pair,
    initialize_database_pair,
    validate_database_pair,
)
from namisync.workflows.runtime import LocalWorkflowRuntime

from _child_process import WAIT_SECONDS, Child, run_child
from _db_fixtures import NOW, file_stat, operation, plan, seed_history_run, setup_recorder
from _maintenance_children import DESKTOP as _DESKTOP, HOLD as _HOLD, RESTORE as _RESTORE
from _released_fixture import copy_released_pair


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows file sharing and claims")

UTC = timezone.utc
_T1 = datetime(2026, 11, 25, 9, 0, tzinfo=UTC)
_READ_INSTANCE = r"""
import sqlite3, sys
connection = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
print(connection.execute("SELECT value FROM schema_metadata WHERE key = 'instance_id'").fetchone()[0])
"""


class _Clock:
    def __init__(self, value: datetime | None = None) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value or datetime.now(UTC)


def _pair(directory: Path) -> tuple[Path, Path]:
    ledger, history = directory / "ledger.db", directory / "history.db"
    assert initialize_database_pair(ledger, history).state is DatabasePairState.READY
    copy = operation(OperationKind.COPY, source=file_stat(), target=None)
    setup_recorder(ledger, plan((copy,))).recorder.close()
    seed_history_run(
        history, "seeded", ledger_instance_id=_instance(ledger), created_at=NOW, started_at=NOW,
    )
    return ledger, history


def _add_run(ledger: Path) -> None:
    copy = operation(OperationKind.COPY, source=file_stat(identity_index=9), target=None)
    setup_recorder(ledger, plan((copy,)), run_token="b" * 32).recorder.close()


def _query(main: Path, sql: str) -> list[tuple]:
    """Read a private copy of the main and its -wal; nothing beside them changes."""

    with TemporaryDirectory(dir=main.parent.parent) as scratch:
        copy = Path(scratch) / "copy.db"
        for suffix in ("", "-wal"):
            if Path(f"{main}{suffix}").exists():
                shutil.copyfile(f"{main}{suffix}", f"{copy}{suffix}")
        with closing(sqlite3.connect(copy.as_uri() + "?mode=ro", uri=True)) as connection:
            return connection.execute(sql).fetchall()


def _instance(ledger: Path) -> str:
    return _query(ledger, "SELECT value FROM schema_metadata WHERE key = 'instance_id'")[0][0]


def _bytes(*mains: Path) -> dict[str, bytes | None]:
    return {
        f"{main.name}{suffix}": (
            Path(f"{main}{suffix}").read_bytes() if Path(f"{main}{suffix}").exists() else None
        )
        for main in mains
        for suffix in ("", "-wal")
    }


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes() for path in directory.iterdir()
        if path.is_file() and not path.name.endswith(".claim")
    }


def _backup(ledger: Path, history: Path, *, clock: _Clock | None = None):
    result = backup_database_pair(ledger, history, clock=clock or _Clock())
    assert result.contract.state is DatabasePairState.READY, result.contract
    return {backup.role: backup.path for backup in result.backups}


def _eventually(operation):
    # A killed holder's locks and handles may outlive it briefly on Windows.
    deadline = monotonic() + WAIT_SECONDS
    while True:
        result = operation()
        if getattr(getattr(result, "contract", None), "reason", None) != "database-in-use":
            return result
        if monotonic() > deadline:
            return result
        sleep(0.05)


def _read_instance_eventually(ledger: Path) -> str:
    deadline = monotonic() + WAIT_SECONDS
    while True:
        try:
            with closing(sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True)) as connection:
                return connection.execute(
                    "SELECT value FROM schema_metadata WHERE key = 'instance_id'"
                ).fetchone()[0]
        except sqlite3.OperationalError:
            # SQLITE_IOERR_TRUNCATE while a killed process's -shm handle lingers.
            if monotonic() > deadline:
                raise
            sleep(0.05)


# --- claims ------------------------------------------------------------------


@pytest.mark.parametrize("kind", ("recorder", "observer"))
def test_maintenance_refuses_while_a_writer_holds_a_shared_claim(
    tmp_path: Path, kind: str,
) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)["ledger"]
    child = Child(_HOLD, kind, str(ledger), str(history))
    try:
        assert child.read() == "held"
        before = _bytes(ledger, history)
        files = sorted(path.name for path in tmp_path.iterdir())
        results = (
            check_database_pair(ledger, history),
            backup_database_pair(ledger, history, clock=_Clock()),
            restore_database_from_backup(ledger, history, "ledger", backup, clock=_Clock()),
        )
        for result in results:
            assert result.contract.state is DatabasePairState.REFUSED
            assert result.contract.reason == "database-in-use"
            assert "in use by NamiSync work" in result.contract.guidance
        assert results[0].checks == ()
        assert results[1].backups == ()
        assert results[2].restore is None
        assert _bytes(ledger, history) == before
        assert sorted(path.name for path in tmp_path.iterdir()) == files
    finally:
        child.kill()
    assert _eventually(lambda: check_database_pair(ledger, history)).contract.state is (
        DatabasePairState.READY
    )


# --- check and backup ----------------------------------------------------------


def test_check_reports_every_role_in_any_pair_state(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    result = check_database_pair(ledger, history)
    assert result.contract.state is DatabasePairState.READY
    assert [(check.role, check.state) for check in result.checks] == [
        ("ledger", DatabaseCheckState.OK), ("history", DatabaseCheckState.OK),
    ]
    for suffix in ("", "-wal", "-shm"):
        Path(f"{ledger}{suffix}").unlink(missing_ok=True)
    result = check_database_pair(ledger, history)
    assert (result.contract.state, result.contract.reason) == (
        DatabasePairState.INCOMPLETE, "ledger-missing",
    )
    assert [(check.role, check.state) for check in result.checks] == [
        ("ledger", DatabaseCheckState.MISSING), ("history", DatabaseCheckState.OK),
    ]
    # A stray sidecar where the ledger was is still an inconsistent pair.
    Path(f"{ledger}-wal").write_bytes(b"")
    result = check_database_pair(ledger, history)
    assert (result.contract.state, result.contract.reason) == (
        DatabasePairState.REFUSED, "inconsistent-pair",
    )
    assert [(check.role, check.state) for check in result.checks] == [
        ("ledger", DatabaseCheckState.MISSING), ("history", DatabaseCheckState.OK),
    ]
    assert result.checks[0].problems == ("ledger.db-wal is present without its database",)


def test_backup_requires_a_ready_pair_and_writes_nothing_otherwise(tmp_path: Path) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")
    before = _files(ledger.parent)
    result = backup_database_pair(ledger, history, clock=_Clock())
    assert (result.contract.state, result.contract.reason) == (
        DatabasePairState.MIGRATION_REQUIRED, "pair-older",
    )
    assert result.backups == ()
    assert _files(ledger.parent) == before


@pytest.mark.parametrize("missing", ("ledger", "history"))
def test_backup_refuses_an_incomplete_pair_with_the_completion_direction(
    tmp_path: Path, missing: str,
) -> None:
    ledger, history = _pair(tmp_path)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{ledger if missing == 'ledger' else history}{suffix}").unlink(missing_ok=True)
    before = _files(tmp_path)
    result = backup_database_pair(ledger, history, clock=_Clock())
    assert (result.contract.state, result.contract.reason) == (
        DatabasePairState.INCOMPLETE, f"{missing}-missing",
    )
    assert "run a sync or inventory command, once to create a new one" in result.contract.guidance
    assert result.backups == ()
    assert _files(tmp_path) == before


def test_backups_rotate_to_three_and_leave_migration_backups(tmp_path: Path) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")
    migrated = upgrade_database_pair(ledger, history, create=True).backups
    assert len(migrated) == 2
    published = []
    for minute in range(5):
        result = backup_database_pair(
            ledger, history, clock=_Clock(_T1 + timedelta(minutes=minute)),
        )
        assert result.contract.state is DatabasePairState.READY
        assert result.removal_failures == ()
        published.append(result)
    assert [len(result.removed) for result in published] == [0, 0, 0, 2, 2]
    for role in ("ledger", "history"):
        assert sorted(path.name for path in ledger.parent.glob(f"{role}.db.backup-2*")) == [
            f"{role}.db.backup-20261125T09{minute:02d}00000000Z" for minute in (2, 3, 4)
        ]
    assert all(path.exists() for path in migrated)


def test_rotation_never_removes_a_live_database_named_like_a_backup(tmp_path: Path) -> None:
    # A valid custom History path that matches the ledger's backup pattern,
    # with the oldest stamp of all.
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "ledger.db.backup-20200101T000000000000Z"
    assert initialize_database_pair(ledger, history).state is DatabasePairState.READY
    history_bytes = history.read_bytes()

    for minute in range(5):
        result = backup_database_pair(
            ledger, history, clock=_Clock(_T1 + timedelta(minutes=minute)),
        )
        assert result.contract.state is DatabasePairState.READY, result.contract
        assert history not in result.removed and result.removal_failures == ()

    assert history.read_bytes() == history_bytes
    # History is not counted toward the three kept ledger backups.
    assert sorted(path.name for path in tmp_path.glob("ledger.db.backup-2026*")) == [
        f"ledger.db.backup-20261125T09{minute:02d}00000000Z" for minute in (2, 3, 4)
    ]
    assert check_database_pair(ledger, history).contract.state is DatabasePairState.READY


def test_a_failed_history_backup_keeps_the_ledger_backup_and_rotates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = _pair(tmp_path)
    for minute in range(3):
        _backup(ledger, history, clock=_Clock(_T1 + timedelta(minutes=minute)))
    before = sorted(path.name for path in tmp_path.glob("*.backup-*"))
    verify = maintenance._verify_backup

    def reject_history(copy, *, history, **keywords):
        if history:
            raise _BackupVerificationFailed("the backup failed its integrity check")
        verify(copy, history=history, **keywords)

    monkeypatch.setattr(maintenance, "_verify_backup", reject_history)
    result = backup_database_pair(ledger, history, clock=_Clock(_T1 + timedelta(hours=1)))

    assert (result.contract.state, result.contract.reason) == (
        DatabasePairState.REFUSED, "backup-failed",
    )
    assert [backup.role for backup in result.backups] == ["ledger"]
    assert result.removed == ()
    assert sorted(path.name for path in tmp_path.glob("*.backup-*")) == sorted(
        [*before, result.backups[0].path.name]
    )


def _dangle(main: Path, *, history: bool = False) -> None:
    """Leave one row that refers to a row that is not there."""

    with closing(sqlite3.connect(main, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        if history:
            connection.execute(
                "INSERT INTO history_phases(run_id, phase_order, phase, status, "
                "items_done, bytes_done) VALUES (999, 0, 'scan', 'completed', 0, 0)"
            )
        else:
            connection.execute(
                "INSERT INTO mappings(source_location_id, target_location_id, created_at) "
                "VALUES (1000, 2000, '2026-01-01T00:00:00.000000Z')"
            )


def test_backups_of_a_ledger_with_a_dangling_reference_never_displace_restorable_ones(
    tmp_path: Path,
) -> None:
    # The review's reproduction: three backups after a dangling foreign key
    # used to rotate out every backup that restore accepts.
    ledger, history = _pair(tmp_path)
    good = [
        _backup(ledger, history, clock=_Clock(_T1 + timedelta(minutes=minute)))["ledger"]
        for minute in range(3)
    ]
    _dangle(ledger)
    assert check_database_pair(ledger, history).checks[0].state is (
        DatabaseCheckState.FOREIGN_KEY_VIOLATIONS
    )
    before = sorted(path.name for path in tmp_path.glob("*.backup-*"))

    for hour in range(1, 4):
        result = backup_database_pair(ledger, history, clock=_Clock(_T1 + timedelta(hours=hour)))
        assert (result.contract.state, result.contract.reason) == (
            DatabasePairState.REFUSED, "backup-failed",
        )
        assert "foreign key violations" in result.contract.guidance
        assert (result.backups, result.removed) == ((), ())
    assert sorted(path.name for path in tmp_path.glob("*.backup-*")) == before

    # Each kept backup still restores; the first sets the violating ledger aside.
    for index, backup in enumerate(good):
        restored = restore_database_from_backup(
            ledger, history, "ledger", backup, clock=_Clock(_T1 + timedelta(hours=5 + index)),
        )
        assert restored.contract.state is DatabasePairState.READY, restored.contract
        assert restored.restore.kept_as == ("replaced" if index == 0 else "backup")
    assert check_database_pair(ledger, history).checks[0].state is DatabaseCheckState.OK


def test_a_history_with_a_dangling_reference_keeps_the_ledger_backup_and_rotates_nothing(
    tmp_path: Path,
) -> None:
    ledger, history = _pair(tmp_path)
    for minute in range(3):
        _backup(ledger, history, clock=_Clock(_T1 + timedelta(minutes=minute)))
    before = sorted(path.name for path in tmp_path.glob("*.backup-*"))
    _dangle(history, history=True)

    result = backup_database_pair(ledger, history, clock=_Clock(_T1 + timedelta(hours=1)))

    assert (result.contract.state, result.contract.reason) == (
        DatabasePairState.REFUSED, "backup-failed",
    )
    assert "The history database" in result.contract.guidance
    assert "foreign key violations" in result.contract.guidance
    assert [backup.role for backup in result.backups] == ["ledger"]
    assert result.removed == ()
    assert sorted(path.name for path in tmp_path.glob("*.backup-*")) == sorted(
        [*before, result.backups[0].path.name]
    )


# --- restore refusals ----------------------------------------------------------


def _refusal_sources(tmp_path: Path, ledger: Path, history: Path) -> dict[str, tuple[str, Path]]:
    released = tmp_path / "released"
    old_ledger, old_history = copy_released_pair(released)
    migrated = upgrade_database_pair(old_ledger, old_history, create=True).backups
    v4 = next(path for path in migrated if path.name.startswith("ledger"))
    v8 = next(path for path in migrated if path.name.startswith("history"))
    backups = _backup(ledger, history)
    damaged = tmp_path / "damaged.backup"
    data = bytearray(backups["ledger"].read_bytes())
    data[100:612] = b"\xa5" * 512
    damaged.write_bytes(bytes(data))
    unstamped = tmp_path / "unstamped.db"
    with closing(sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(unstamped)) as copy:
            source.backup(copy)
            copy.execute("PRAGMA journal_mode = DELETE")
    return {
        "backup-older": ("ledger", v4),
        "backup-older-history": ("history", v8),
        "backup-wrong-role": ("ledger", backups["history"]),
        "backup-wrong-role-history": ("history", backups["ledger"]),
        "backup-damaged": ("ledger", damaged),
        "backup-unstamped": ("ledger", unstamped),
        "backup-unavailable": ("ledger", tmp_path / "absent.backup"),
    }


def test_restore_refusals_leave_both_databases_byte_identical(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path / "data")
    sources = _refusal_sources(tmp_path, ledger, history)
    before = _bytes(ledger, history)
    files = _files(ledger.parent)

    for expected, (role, source) in sources.items():
        result = restore_database_from_backup(ledger, history, role, source, clock=_Clock())
        assert result.contract.state is DatabasePairState.REFUSED, expected
        assert result.contract.reason == expected.removesuffix("-history"), result.contract
        # The result says nothing changed; the guidance does not repeat it.
        assert (result.restore, result.kept) == (None, None), expected
        assert "Nothing was changed" not in result.contract.guidance, expected
        assert result.contract.reset_direction is None
        assert result.restore is None
        assert _bytes(ledger, history) == before, expected
        assert _files(ledger.parent) == files, expected
    assert "way back to the version that wrote it" in restore_database_from_backup(
        ledger, history, "ledger", sources["backup-older"][1], clock=_Clock(),
    ).contract.guidance

    # Swapped paths. For a ledger the pair rule sees History's path holding a
    # ledger first; History's own target check sees the other role.
    backups = _backup(ledger, history)
    swapped = restore_database_from_backup(
        history, ledger, "ledger", backups["ledger"], clock=_Clock(),
    )
    assert (swapped.contract.reason, swapped.restore) == ("history-wrong-role", None)
    swapped = restore_database_from_backup(
        history, ledger, "history", backups["history"], clock=_Clock(),
    )
    assert (swapped.contract.reason, swapped.restore) == ("target-wrong-role", None)
    assert _bytes(ledger, history) == before
    # Sidecars without a main.
    for suffix in ("", "-shm"):
        Path(f"{history}{suffix}").unlink(missing_ok=True)
    Path(f"{history}-wal").write_bytes(b"")
    inconsistent = restore_database_from_backup(
        ledger, history, "history", _backup_history_elsewhere(tmp_path), clock=_Clock(),
    )
    assert inconsistent.contract.reason == "target-inconsistent"
    assert Path(f"{history}-wal").read_bytes() == b"" and not history.exists()


def test_a_restore_that_cannot_be_confirmed_is_never_reported_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)["ledger"]

    def unreadable(*_arguments, **_keywords):
        raise OSError("read back failed")

    monkeypatch.setattr(maintenance, "_confirm", unreadable)
    result = restore_database_from_backup(ledger, history, "ledger", backup, clock=_Clock())

    assert (result.contract.state, result.contract.reason) == (
        DatabasePairState.REFUSED, "restore-unconfirmed",
    )
    assert "could not be confirmed" in result.contract.guidance
    assert "run check" in result.contract.guidance
    assert "nothing was restored" not in result.contract.guidance.lower()
    assert result.restore is None
    assert not list(tmp_path.glob("*.restore-*"))


def _backup_history_elsewhere(tmp_path: Path) -> Path:
    other_ledger, other_history = _pair(tmp_path / "other")
    return _backup(other_ledger, other_history)["history"]


# --- restore kill trials -------------------------------------------------------


def _state(ledger: Path, old: str, backup_instance: str) -> str:
    """Name what the live ledger holds; anything else fails the trial.

    Right after a kill the dead child's -shm locks can linger briefly, so a
    read that fails for any reason other than SQLite damage is retried within
    a bound; the verdict itself stays strict.
    """

    deadline = monotonic() + WAIT_SECONDS
    while True:
        if not ledger.exists():
            return "missing"
        try:
            probe_database_file_contract(ledger, history=False)
            break
        except DatabaseDamagedError:
            return "unusable"
        except Exception:
            if monotonic() > deadline:
                raise
            sleep(0.05)
    instance = _instance(ledger)
    runs = _query(ledger, "SELECT run_token FROM runs ORDER BY 1")
    lineage = _query(ledger, "SELECT instance_id FROM ledger_lineage")
    if instance == old and len(runs) == 2 and lineage == []:
        return "old"
    if instance not in (old, backup_instance) and len(runs) == 1 and lineage == [(old,)]:
        return "new"
    pytest.fail(f"mixed ledger: {instance=} {runs=} {lineage=}")


def _stop_child(ledger: Path, history: Path, backup: Path, stage: str, nth: int = 0) -> Child:
    child = Child(_RESTORE, str(ledger), str(history), "ledger", str(backup), stage, str(nth))
    assert child.read() == "ready"
    assert child.read() == "stopped"
    return child


_IN_PLACE = {"backed-up": "old", "image-written": "old", "mid-copy": "old", "committed": "new"}


@pytest.mark.parametrize("stage", tuple(_IN_PLACE))
def test_killed_in_place_restore_leaves_old_or_new_and_a_rerun_finishes(
    tmp_path: Path, stage: str,
) -> None:
    ledger, history = _pair(tmp_path)
    old = _instance(ledger)
    backup = _backup(ledger, history)["ledger"]
    _add_run(ledger)
    root = tmp_path / "root"
    root.mkdir()
    arguments = [
        "inventory", str(root), "--database", str(ledger), "--history-database", str(history),
    ]
    # A window opened before maintenance, its ledger and History readers admitted.
    service = NamiSyncService(ledger, history)
    try:
        assert [run.run_token for run in service.list_history(10)] == ["seeded"]
        child = _stop_child(ledger, history, backup, stage)
        try:
            before = _bytes(ledger, history)
            # New work is refused at admission while maintenance holds the claims.
            with pytest.raises(SessionAdmissionRefused, match="maintenance is in progress"):
                service.start_inventory(root_path=str(root))
            stderr = io.StringIO()
            assert main(arguments, stdout=io.StringIO(), stderr=stderr) == EXIT_REFUSED
            if stage == "mid-copy":
                # The copy's open write transaction locks part of the -shm, so a
                # new process's cold pair check cannot read the files and
                # refuses first (exit 3, nothing changed).
                assert stderr.getvalue().startswith(
                    "Database pair refused: database-unavailable."
                ), stderr.getvalue()
                # Readers keep the old ledger while the copy is uncommitted.
                assert run_child(_READ_INSTANCE, str(ledger)) == old
            else:
                assert stderr.getvalue().startswith(
                    "Inventory refused: Database maintenance is in progress"
                ), stderr.getvalue()
            assert _bytes(ledger, history) == before
            assert not os.path.lexists(Path(f"{ledger}-journal"))
        finally:
            child.kill()
    finally:
        service.close()

    assert _state(ledger, old, old) == _IN_PLACE[stage]
    if stage == "mid-copy":
        assert _read_instance_eventually(ledger) == old
    temporaries = sorted(path.name for path in tmp_path.glob("ledger.db.restore-*.tmp"))
    assert len(temporaries) == (0 if stage == "backed-up" else 1)
    pre_restore = sorted(path.name for path in tmp_path.glob("ledger.db.backup-*"))
    assert len(pre_restore) == 2

    result = _eventually(lambda: restore_database_from_backup(
        ledger, history, "ledger", backup, clock=_Clock(),
    ))
    assert result.contract.state is DatabasePairState.READY, result.contract
    assert result.restore.kept_as == "backup"
    assert _state(ledger, old, old) == "new"
    assert _instance(ledger) == result.restore.instance_id
    # A crash's temporary is neither removed nor reused.
    assert sorted(path.name for path in tmp_path.glob("ledger.db.restore-*.tmp")) == temporaries
    assert main(arguments, stdout=io.StringIO(), stderr=io.StringIO()) == EXIT_SUCCESS


def _damage_with_sidecars(ledger: Path) -> dict[str, bytes]:
    connection = sqlite3.connect(ledger, isolation_level=None)
    connection.execute("PRAGMA wal_autocheckpoint = 0")
    connection.execute("UPDATE hosts SET display_name = 'after backup'")
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
    connection.close()
    data = bytearray(ledger.read_bytes())
    data[100:612] = b"\xa5" * 512
    ledger.write_bytes(bytes(data))
    files = {suffix: Path(f"{ledger}{suffix}").read_bytes() for suffix in ("", "-wal", "-shm")}
    assert files["-wal"]
    return files


# rename calls: -wal, -shm, the main, then the image into place.
_SET_ASIDE = {
    "image-written": (0, "unusable", ()),
    "sidecars-aside": (2, "unusable", ("-wal", "-shm")),
    "main-aside": (3, "missing", ("", "-wal", "-shm")),
    "published": (4, "new", ("", "-wal", "-shm")),
}


@pytest.mark.parametrize("stage", tuple(_SET_ASIDE))
def test_killed_set_aside_restore_keeps_the_damaged_set_and_a_rerun_finishes(
    tmp_path: Path, stage: str,
) -> None:
    ledger, history = _pair(tmp_path)
    old = _instance(ledger)
    backup = _backup(ledger, history)["ledger"]
    _add_run(ledger)
    damaged = _damage_with_sidecars(ledger)
    nth, expected, moved = _SET_ASIDE[stage]
    child = _stop_child(
        ledger, history, backup, "image-written" if stage == "image-written" else "renamed", nth,
    )
    child.kill()

    assert _state(ledger, old, old) == expected
    aside = sorted(tmp_path.glob("ledger.db.replaced-*Z"))
    if moved:
        stamp = next(iter({
            path.name.removeprefix("ledger.db.replaced-")[:22]
            for path in tmp_path.glob("ledger.db.replaced-*")
        }))
        kept = tmp_path / f"ledger.db.replaced-{stamp}"
        assert {
            suffix: Path(f"{kept}{suffix}").read_bytes() for suffix in moved
        } == {suffix: damaged[suffix] for suffix in moved}
    else:
        assert aside == []
    if expected == "unusable":
        assert {
            suffix: Path(f"{ledger}{suffix}").read_bytes()
            for suffix in ("", "-wal", "-shm") if suffix not in moved
        } == {suffix: damaged[suffix] for suffix in damaged if suffix not in moved}

    result = _eventually(lambda: restore_database_from_backup(
        ledger, history, "ledger", backup, clock=_Clock(),
    ))
    assert result.contract.state is DatabasePairState.READY, result.contract
    assert _state(ledger, old, old) == "new"
    # Every damaged file is kept, possibly split across two stamps.
    kept_files = sorted(
        path.read_bytes() for path in tmp_path.glob("ledger.db.replaced-*")
    )
    assert kept_files == sorted(damaged.values())


@pytest.mark.parametrize("stage", ("image-written", "published"))
def test_killed_restore_into_a_missing_ledger_leaves_none_or_new(
    tmp_path: Path, stage: str,
) -> None:
    ledger, history = _pair(tmp_path)
    old = _instance(ledger)
    backup = _backup(ledger, history)["ledger"]
    _add_run(ledger)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{ledger}{suffix}").unlink(missing_ok=True)
    child = _stop_child(
        ledger, history, backup, "image-written" if stage == "image-written" else "renamed", 1,
    )
    child.kill()

    assert _state(ledger, old, old) == ("missing" if stage == "image-written" else "new")
    result = _eventually(lambda: restore_database_from_backup(
        ledger, history, "ledger", backup, clock=_Clock(),
    ))
    assert result.contract.state is DatabasePairState.READY, result.contract
    assert _state(ledger, old, old) == "new"


# --- beside a desktop ----------------------------------------------------------


def test_in_place_restore_runs_beside_an_idle_desktop_that_then_reads_the_new_ledger(
    tmp_path: Path,
) -> None:
    ledger, history = _pair(tmp_path)
    old = _instance(ledger)
    backup = _backup(ledger, history)["ledger"]
    _add_run(ledger)
    desktop = Child(_DESKTOP, str(ledger), str(history))
    try:
        assert desktop.read() == f"held {old}"
        result = restore_database_from_backup(ledger, history, "ledger", backup, clock=_Clock())
        assert result.contract.state is DatabasePairState.READY, result.contract
        assert result.restore.kept_as == "backup"
        assert desktop.process.stdin is not None
        desktop.process.stdin.write("read\n")
        desktop.process.stdin.flush()
        # The same owner validates the same main file, and its idle
        # repository now reads the new instance.
        assert desktop.read() == f"instance {result.restore.instance_id}"
    finally:
        desktop.kill()
    assert _state(ledger, old, old) == "new"


def test_set_aside_restore_refuses_while_a_desktop_pins_the_damaged_ledger(
    tmp_path: Path,
) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)["ledger"]
    _damage_with_sidecars(ledger)
    files = _files(tmp_path)
    pin = Child(_HOLD, "pin", str(ledger), str(history))
    try:
        assert pin.read() == "held"
        result = restore_database_from_backup(ledger, history, "ledger", backup, clock=_Clock())
        assert (result.contract.state, result.contract.reason) == (
            DatabasePairState.REFUSED, "database-in-use",
        )
        assert result.restore is None
        assert _files(tmp_path) == files
    finally:
        pin.kill()
    result = _eventually(lambda: restore_database_from_backup(
        ledger, history, "ledger", backup, clock=_Clock(),
    ))
    assert result.restore.kept_as == "replaced"


# --- lineage -------------------------------------------------------------------


def _membership(ledger: Path, history: Path) -> dict[str, str]:
    with closing(LocalWorkflowRuntime(ledger, history)) as runtime:
        return {run.run_token: run.ledger_membership for run in runtime.list_history(50)}


def test_runs_of_both_ancestors_stay_current_through_two_restores(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    a = _instance(ledger)
    t1 = datetime(2026, 11, 25, 9, 0, tzinfo=UTC)
    t3 = datetime(2026, 11, 25, 11, 0, tzinfo=UTC)
    seed_history_run(history, "a-before", ledger_instance_id=a,
                     created_at=t1 - timedelta(hours=1), started_at=t1 - timedelta(hours=1))
    backup_a = _backup(ledger, history, clock=_Clock(t1))["ledger"]
    seed_history_run(history, "a-after", ledger_instance_id=a,
                     created_at=t1 + timedelta(minutes=5), started_at=t1 + timedelta(minutes=5))

    first = restore_database_from_backup(ledger, history, "ledger", backup_a, clock=_Clock(
        t1 + timedelta(minutes=30),
    ))
    b = first.restore.instance_id
    seed_history_run(history, "b-before", ledger_instance_id=b,
                     created_at=t3 - timedelta(minutes=10), started_at=t3 - timedelta(minutes=10))
    backup_b = _backup(ledger, history, clock=_Clock(t3))["ledger"]
    seed_history_run(history, "b-after", ledger_instance_id=b,
                     created_at=t3 + timedelta(minutes=5), started_at=t3 + timedelta(minutes=5))

    second = restore_database_from_backup(ledger, history, "ledger", backup_b, clock=_Clock(
        t3 + timedelta(minutes=30),
    ))
    c = second.restore.instance_id
    assert len({a, b, c}) == 3
    assert (second.restore.restored_instance_id, second.restore.cut_at) == (b, t3)
    assert _query(ledger, "SELECT instance_id, at FROM ledger_lineage ORDER BY id") == [
        (a, "2026-11-25T09:00:00.000000Z"), (b, "2026-11-25T11:00:00.000000Z"),
    ]
    assert _membership(ledger, history) == {
        "seeded": "current",
        "a-before": "current",
        "a-after": "earlier",
        "b-before": "current",
        "b-after": "earlier",
    }


# --- the pair rule for a ledger restore ------------------------------------------


def _released_runs(history: Path) -> set[str]:
    return {row[0] for row in _query(history, "SELECT run_token FROM history_runs")}


def test_a_healthy_v0_1_0_pair_is_updated_before_its_ledger_is_restored(tmp_path: Path) -> None:
    # Advice, not protection: replacing a readable 0.1.0 ledger with a
    # current backup is almost certainly a mistake.
    ledger, history = copy_released_pair(tmp_path / "data")
    other_backup = _backup(*_pair(tmp_path / "other"))["ledger"]
    files = _files(ledger.parent)

    refused = restore_database_from_backup(
        ledger, history, "ledger", other_backup, clock=_Clock(),
    )

    assert (refused.contract.state, refused.contract.reason) == (
        DatabasePairState.REFUSED, "pair-older",
    )
    assert (
        "Start NamiSync, or run a sync or inventory command, once to update the pair"
        in refused.contract.guidance
    )
    assert "Nothing was changed" not in refused.contract.guidance
    assert (refused.restore, refused.kept) == (None, None)
    assert _files(ledger.parent) == files

    # Updating the pair first stamps the 0.1.0 runs with the migrated ledger;
    # after the restore they belong to an earlier ledger.
    assert upgrade_database_pair(ledger, history, create=True).contract.state is DatabasePairState.READY
    released = _released_runs(history)
    restored = restore_database_from_backup(
        ledger, history, "ledger", other_backup, clock=_Clock(),
    )
    assert restored.contract.state is DatabasePairState.READY, restored.contract
    assert restored.restore.kept_as == "backup"
    membership = _membership(ledger, history)
    assert set(membership) == released and len(released) == 15
    assert set(membership.values()) == {"earlier"}


@pytest.mark.parametrize("ledger_shape", ("damaged", "missing"))
def test_an_unusable_ledger_is_restored_beside_an_older_history(
    tmp_path: Path, ledger_shape: str,
) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")
    other_backup = _backup(*_pair(tmp_path / "other"))["ledger"]
    # v0.1.0 keeps its committed pages in the -wal, so damage reaches the main
    # only without it.
    for suffix in ("-wal", "-shm") if ledger_shape == "damaged" else ("", "-wal", "-shm"):
        Path(f"{ledger}{suffix}").unlink(missing_ok=True)
    if ledger_shape == "damaged":
        data = bytearray(ledger.read_bytes())
        data[100:612] = b"\xa5" * 512
        ledger.write_bytes(bytes(data))

    restored = restore_database_from_backup(
        ledger, history, "ledger", other_backup, clock=_Clock(),
    )

    assert restored.restore is not None, restored.contract
    assert restored.restore.kept_as == ("replaced" if ledger_shape == "damaged" else None)
    assert (restored.contract.state, restored.contract.reason) == (
        DatabasePairState.MIGRATION_REQUIRED, "history-older",
    )
    assert "At least one database of this pair" in restored.contract.guidance


def test_with_both_roles_damaged_the_ledger_can_be_restored_first(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path / "data")
    backups = _backup(ledger, history)
    for main in (ledger, history):
        data = bytearray(main.read_bytes())
        data[100:612] = b"\xa5" * 512
        main.write_bytes(bytes(data))

    first = restore_database_from_backup(ledger, history, "ledger", backups["ledger"], clock=_Clock())
    assert first.restore is not None and first.restore.kept_as == "replaced", first.contract
    assert (first.contract.state, first.contract.reason) == (
        DatabasePairState.REFUSED, "database-damaged",
    )
    second = restore_database_from_backup(
        ledger, history, "history", backups["history"], clock=_Clock(),
    )
    assert second.restore is not None and second.restore.kept_as == "replaced", second.contract
    assert second.contract.state is DatabasePairState.READY, second.contract
    checked = check_database_pair(ledger, history)
    assert [check.state for check in checked.checks] == [DatabaseCheckState.OK] * 2


def _history_beside(history: Path, shape: str, tmp_path: Path) -> None:
    if shape == "newer":
        with closing(sqlite3.connect(history)) as connection, connection:
            connection.execute(
                "UPDATE schema_metadata SET value = '10' WHERE key = 'schema_version'"
            )
    elif shape == "wrong-role":
        other_ledger = _pair(tmp_path / "wrong")[0]
        for suffix in ("", "-wal", "-shm"):
            Path(f"{history}{suffix}").unlink(missing_ok=True)
        with closing(sqlite3.connect(other_ledger.as_uri() + "?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(history)) as copy:
                source.backup(copy)
    elif shape == "damaged":
        data = bytearray(history.read_bytes())
        data[100:612] = b"\xa5" * 512
        history.write_bytes(bytes(data))
    elif shape == "sidecars-only":
        for suffix in ("", "-shm"):
            Path(f"{history}{suffix}").unlink(missing_ok=True)
        Path(f"{history}-wal").write_bytes(b"")
    elif shape == "missing":
        for suffix in ("", "-wal", "-shm"):
            Path(f"{history}{suffix}").unlink(missing_ok=True)


@pytest.mark.parametrize(("shape", "reason"), [
    ("newer", "history-newer"),
    ("wrong-role", "history-wrong-role"),
    ("damaged", None),
    ("sidecars-only", None),
    ("missing", None),
])
def test_a_ledger_restore_is_refused_only_beside_a_newer_or_misplaced_history(
    tmp_path: Path, shape: str, reason: str | None,
) -> None:
    ledger, history = _pair(tmp_path / "data")
    backup = _backup(ledger, history)["ledger"]
    _history_beside(history, shape, tmp_path)
    files = _files(ledger.parent)

    result = restore_database_from_backup(ledger, history, "ledger", backup, clock=_Clock())

    if reason is None:
        assert result.restore is not None and result.restore.kept_as == "backup"
        if shape == "missing":
            # The restored ledger stands alone until the pair is completed.
            assert (result.contract.state, result.contract.reason) == (
                DatabasePairState.INCOMPLETE, "history-missing",
            )
            completion = upgrade_database_pair(ledger, history, create=True)
            assert completion.contract.state is DatabasePairState.READY
            assert [database.role for database in completion.created] == ["history"]
        return
    assert (result.contract.reason, result.restore, result.kept) == (reason, None, None)
    assert "Nothing was changed" not in result.contract.guidance
    assert _files(ledger.parent) == files


def test_history_is_restored_beside_a_v0_1_0_ledger_and_joins_nothing(tmp_path: Path) -> None:
    # A restored History is already stamped; the ledger's later update issues
    # a new instance that none of its runs carry.
    ledger, history = copy_released_pair(tmp_path / "data")
    other_backup = _backup(*_pair(tmp_path / "other"))["history"]

    result = restore_database_from_backup(
        ledger, history, "history", other_backup, clock=_Clock(),
    )

    assert result.restore is not None and result.restore.kept_as == "replaced"
    assert (result.contract.state, result.contract.reason) == (
        DatabasePairState.MIGRATION_REQUIRED, "ledger-older",
    )
    assert upgrade_database_pair(ledger, history, create=True).contract.state is DatabasePairState.READY
    assert _membership(ledger, history) == {"seeded": "earlier"}


def test_history_restored_where_the_ledger_is_missing_gains_a_new_ledger(
    tmp_path: Path,
) -> None:
    ledger, history = _pair(tmp_path / "data")
    backup = _backup(ledger, history)["history"]
    for suffix in ("", "-wal", "-shm"):
        Path(f"{ledger}{suffix}").unlink(missing_ok=True)

    result = restore_database_from_backup(ledger, history, "history", backup, clock=_Clock())

    assert result.restore is not None and result.restore.kept_as == "backup"
    assert (result.contract.state, result.contract.reason) == (
        DatabasePairState.INCOMPLETE, "ledger-missing",
    )
    completion = upgrade_database_pair(ledger, history, create=True)
    assert completion.contract.state is DatabasePairState.READY
    assert [database.role for database in completion.created] == ["ledger"]
    assert _query(ledger, "SELECT kind, instance_id FROM ledger_lineage") == [
        ("replaced-missing", None),
    ]
    assert _membership(ledger, history) == {"seeded": "earlier"}


# --- failures after the point of no return ---------------------------------------


@pytest.mark.parametrize("at", ("first-step", "final-step"))
def test_an_in_place_copy_failure_is_unconfirmed_never_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, at: str,
) -> None:
    ledger, history = _pair(tmp_path)
    old = _instance(ledger)
    backup = _backup(ledger, history)["ledger"]
    _add_run(ledger)
    monkeypatch.setattr(maintenance, "_COPY_PAGES", 1)

    def failing(status: int, remaining: int, total: int) -> None:
        # The final step's callback runs after its commit.
        if (remaining == 0) == (at == "final-step"):
            raise RuntimeError("copy step failed")

    monkeypatch.setattr(maintenance, "_copy_progress", failing)
    result = restore_database_from_backup(ledger, history, "ledger", backup, clock=_Clock())

    assert (result.contract.state, result.contract.reason) == (
        DatabasePairState.REFUSED, "restore-unconfirmed",
    )
    assert "could not be confirmed" in result.contract.guidance
    assert "nothing was restored" not in result.contract.guidance.lower()
    assert result.kept is not None and result.kept.exists()
    assert str(result.kept) not in result.contract.guidance
    assert _state(ledger, old, old) == ("new" if at == "final-step" else "old")


def test_a_set_aside_failure_after_a_sidecar_moved_is_unconfirmed_and_keeps_every_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)["ledger"]
    damaged = _damage_with_sidecars(ledger)
    rename = os.rename

    def main_refused(source, destination) -> None:
        if str(destination).endswith("Z"):
            raise OSError(32, "The process cannot access the file")
        rename(source, destination)

    monkeypatch.setattr(os, "rename", main_refused)
    result = restore_database_from_backup(
        ledger, history, "ledger", backup, clock=_Clock(_T1),
    )

    assert result.contract.reason == "restore-unconfirmed"
    kept = ledger.with_name("ledger.db.replaced-20261125T090000000000Z")
    assert Path(f"{kept}-wal").read_bytes() == damaged["-wal"]
    assert Path(f"{kept}-shm").read_bytes() == damaged["-shm"]
    assert ledger.read_bytes() == damaged[""] and not kept.exists()
    assert not list(tmp_path.glob("*.restore-*"))
    # Only the sidecars moved: no kept main is claimed, every path the
    # guidance names exists, and it says the database is still in place.
    assert result.kept is None
    guidance = result.contract.guidance
    named = {
        match.rstrip(".")
        for match in re.findall(re.escape(str(tmp_path)) + r"[^\s,()]*", guidance)
    }
    assert named == {str(ledger), str(backup), f"{kept}-wal", f"{kept}-shm"}
    assert all(Path(path).exists() for path in named)
    assert f"The database itself is still at {ledger}" in guidance


def test_a_handle_opened_while_the_image_is_prepared_refuses_with_nothing_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import _winapi

    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)["ledger"]
    _damage_with_sidecars(ledger)
    files = _files(tmp_path)
    prepare = maintenance._prepare_image
    handles: list[int] = []

    def prepare_then_open(*arguments, **keywords) -> None:
        prepare(*arguments, **keywords)
        # As a desktop starting now would pin the main: no delete sharing.
        handles.append(_winapi.CreateFile(
            str(ledger), _winapi.GENERIC_READ, 0x1 | 0x2, 0, _winapi.OPEN_EXISTING, 0, 0,
        ))

    monkeypatch.setattr(maintenance, "_prepare_image", prepare_then_open)
    try:
        result = restore_database_from_backup(
            ledger, history, "ledger", backup, clock=_Clock(),
        )
    finally:
        for handle in handles:
            _winapi.CloseHandle(handle)

    assert handles, "the stop point was not reached"
    assert (result.contract.reason, result.restore) == ("database-in-use", None)
    assert _files(tmp_path) == files
    assert not list(tmp_path.glob("ledger.db.replaced-*"))


def test_a_lock_holder_aborts_the_in_place_copy_without_waiting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = _pair(tmp_path)
    old = _instance(ledger)
    backup = _backup(ledger, history)["ledger"]
    _add_run(ledger)
    prepare = maintenance._prepare_image
    writers: list[sqlite3.Connection] = []
    locked: dict[str, bytes | None] = {}

    def prepare_then_lock(*arguments, **keywords) -> None:
        prepare(*arguments, **keywords)
        writer = sqlite3.connect(ledger, isolation_level=None, check_same_thread=False)
        writer.execute("BEGIN IMMEDIATE")
        writers.append(writer)
        locked.update(_bytes(ledger))

    monkeypatch.setattr(maintenance, "_prepare_image", prepare_then_lock)
    outcome: list = []
    worker = Thread(target=lambda: outcome.append(restore_database_from_backup(
        ledger, history, "ledger", backup, clock=_Clock(),
    )), daemon=True)
    worker.start()
    worker.join(10.0)
    waited = worker.is_alive()
    for writer in writers:
        writer.rollback()
    worker.join(WAIT_SECONDS)
    for writer in writers:
        writer.close()

    assert not waited, "the in-place copy waited for another writer's lock"
    (result,) = outcome
    assert (result.contract.reason, result.restore) == ("database-in-use", None)
    assert result.kept is not None and result.kept.exists()
    assert str(result.kept) not in result.contract.guidance
    # The main is untouched and the aborted copy left no frames; the lock
    # holder's empty -wal goes when it closes.
    after = _bytes(ledger)
    assert after["ledger.db"] == locked["ledger.db"]
    assert after["ledger.db-wal"] in (locked["ledger.db-wal"], None)
    assert locked["ledger.db-wal"] in (None, b"")
    assert _state(ledger, old, old) == "old"


# --- rename publication never replaces a file --------------------------------------


def test_restore_into_a_missing_slot_never_replaces_a_file_that_appeared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)["ledger"]
    for suffix in ("", "-wal", "-shm"):
        Path(f"{ledger}{suffix}").unlink(missing_ok=True)
    prepare = maintenance._prepare_image

    def prepare_then_occupy(*arguments, **keywords) -> None:
        prepare(*arguments, **keywords)
        ledger.write_bytes(b"appeared meanwhile")

    monkeypatch.setattr(maintenance, "_prepare_image", prepare_then_occupy)
    result = restore_database_from_backup(ledger, history, "ledger", backup, clock=_Clock())

    assert (result.contract.reason, result.restore) == ("restore-failed", None)
    assert ledger.read_bytes() == b"appeared meanwhile"
    assert not list(tmp_path.glob("*.restore-*"))


def test_set_aside_never_replaces_a_file_at_a_replaced_name(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)["ledger"]
    damaged = _damage_with_sidecars(ledger)
    occupied = Path(f"{ledger}.replaced-20261125T090000000000Z-wal")
    occupied.write_bytes(b"someone else's")

    result = restore_database_from_backup(
        ledger, history, "ledger", backup, clock=_Clock(_T1),
    )

    assert (result.contract.reason, result.restore) == ("restore-failed", None)
    assert occupied.read_bytes() == b"someone else's"
    assert {
        suffix: Path(f"{ledger}{suffix}").read_bytes() for suffix in damaged
    } == damaged


def test_the_image_never_replaces_a_file_that_took_the_main_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)["ledger"]
    damaged = _damage_with_sidecars(ledger)
    set_aside = maintenance._set_aside

    def set_aside_then_occupy(path, replaced, moved) -> None:
        set_aside(path, replaced, moved)
        path.write_bytes(b"appeared meanwhile")

    monkeypatch.setattr(maintenance, "_set_aside", set_aside_then_occupy)
    result = restore_database_from_backup(
        ledger, history, "ledger", backup, clock=_Clock(_T1),
    )

    assert result.contract.reason == "restore-unconfirmed"
    assert ledger.read_bytes() == b"appeared meanwhile"
    kept = ledger.with_name("ledger.db.replaced-20261125T090000000000Z")
    assert {
        suffix: Path(f"{kept}{suffix}").read_bytes() for suffix in damaged
    } == damaged


# --- a History kill trial ----------------------------------------------------------


def test_killed_history_restore_mid_copy_leaves_the_old_history(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)["history"]
    seed_history_run(history, "later", ledger_instance_id=_instance(ledger),
                     created_at=NOW, started_at=NOW)
    child = Child(_RESTORE, str(ledger), str(history), "history", str(backup), "mid-copy", "0")
    try:
        assert child.read() == "ready"
        assert child.read() == "stopped"
    finally:
        child.kill()

    assert _query(history, "SELECT run_token FROM history_runs ORDER BY 1") == [
        ("later",), ("seeded",),
    ]
    result = _eventually(lambda: restore_database_from_backup(
        ledger, history, "history", backup, clock=_Clock(),
    ))
    assert result.contract.state is DatabasePairState.READY, result.contract
    assert _query(history, "SELECT run_token FROM history_runs") == [("seeded",)]
