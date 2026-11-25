"""Database maintenance: check, backup, rotation and restore of one database.

Each operation runs under the pair's exclusive maintenance claims, held here
with ``hold_maintenance_claims``. Child-process trials (kills, concurrent
readers, a desktop beside a restore) are in ``test_database_maintenance.py``.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import shutil
import sqlite3
from tempfile import TemporaryDirectory

import pytest

import namisync.db.maintenance as maintenance
from namisync.core.planning import OperationKind
from namisync.db.claims import hold_maintenance_claims
from namisync.db.maintenance import (
    DatabaseCheckState,
    DatabaseRestoreFailed,
    backup_database,
    check_database,
    restore_database,
    rotate_backups,
)
from namisync.db.migration import DatabaseBackupFailed, _BackupVerificationFailed
from namisync.db.schema import (
    LEDGER_SCHEMA_VERSION,
    LedgerIsBackup,
    classify_database,
    validate_history_reader_contract,
    validate_ledger_reader_contract,
)
from namisync.db.timestamps import encode_utc
from namisync.workflows.database_pair import (
    DatabasePairState,
    initialize_database_pair,
    migrate_database_pair,
    validate_database_pair,
)

from _db_fixtures import NOW, file_stat, operation, plan, seed_history_run, setup_recorder
from _released_fixture import copy_released_pair


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows file sharing and claims")

UTC = timezone.utc
_T1 = datetime(2026, 11, 25, 9, 30, 1, 250000, tzinfo=UTC)
_T2 = datetime(2026, 11, 25, 10, 0, 0, tzinfo=UTC)
_BACKUP_NAME = re.compile(r"(ledger|history)\.db\.backup-(\d{8}T\d{12})Z")


def _pair(directory: Path, *, recorded: bool = True) -> tuple[Path, Path]:
    """A ready pair; the ledger holds one recorded run and History one run."""

    ledger, history = directory / "ledger.db", directory / "history.db"
    assert initialize_database_pair(ledger, history).state is DatabasePairState.READY
    if recorded:
        copy = operation(OperationKind.COPY, source=file_stat(), target=None)
        setup = setup_recorder(ledger, plan((copy,)))
        setup.recorder.close()
        seed_history_run(
            history, "seeded", ledger_instance_id=_instance(ledger),
            created_at=NOW, started_at=NOW,
        )
    return ledger, history


def _query(main: Path, sql: str, parameters: tuple = ()) -> list[tuple]:
    """Read through a private copy of the main and its -wal, writing nothing beside it."""

    with TemporaryDirectory(dir=main.parent.parent) as scratch:
        copy = Path(scratch) / "copy.db"
        for suffix in ("", "-wal"):
            if Path(f"{main}{suffix}").exists():
                shutil.copyfile(f"{main}{suffix}", f"{copy}{suffix}")
        with closing(sqlite3.connect(copy.as_uri() + "?mode=ro", uri=True)) as connection:
            return connection.execute(sql, parameters).fetchall()


def _instance(ledger: Path) -> str:
    return _query(ledger, "SELECT value FROM schema_metadata WHERE key = 'instance_id'")[0][0]


def _counts(main: Path) -> dict[str, int]:
    tables = [row[0] for row in _query(
        main, "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'",
    )]
    return {table: _query(main, f"SELECT count(*) FROM {table}")[0][0] for table in tables}


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes() for path in directory.iterdir()
        if path.is_file() and not path.name.endswith(".claim")
    }


def _immutable(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)


def _touch(path: Path, content: bytes = b"x") -> Path:
    path.write_bytes(content)
    return path


# --- backup ------------------------------------------------------------------


def test_ledger_backup_records_its_own_cut_and_leaves_the_source_main_unchanged(
    tmp_path: Path,
) -> None:
    ledger, history = _pair(tmp_path)
    source_counts = _counts(ledger)
    instance_id = _instance(ledger)
    main_before = ledger.read_bytes()
    wal_before = Path(f"{ledger}-wal").read_bytes() if Path(f"{ledger}-wal").exists() else None

    with hold_maintenance_claims(ledger, history) as claims:
        backup = backup_database(ledger, history=False, claim=claims.ledger, now=_T1)

    assert backup == ledger.with_name("ledger.db.backup-20261125T093001250000Z")
    assert _BACKUP_NAME.fullmatch(backup.name)
    # The source main is byte-identical; a -wal that existed keeps its bytes.
    # A read-only connection may leave SQLite's own empty -wal and -shm behind.
    assert ledger.read_bytes() == main_before
    wal = Path(f"{ledger}-wal")
    if wal_before is None:
        assert not wal.exists() or wal.stat().st_size == 0
    else:
        assert wal.read_bytes() == wal_before
    assert _query(ledger, "SELECT count(*) FROM ledger_lineage") == [(0,)]
    # A standalone rollback-journal file: no sidecars, header bytes 18/19 = 1.
    assert [path.name for path in tmp_path.glob("ledger.db.backup-*")] == [backup.name]
    assert backup.read_bytes()[18:20] == b"\x01\x01"
    assert not list(tmp_path.glob("*.tmp"))
    with closing(_immutable(backup)) as connection:
        assert classify_database(connection, history=False) == LEDGER_SCHEMA_VERSION
        with pytest.raises(LedgerIsBackup):
            validate_ledger_reader_contract(connection)
        assert connection.execute(
            "SELECT kind, instance_id, at FROM ledger_lineage"
        ).fetchall() == [("backup-cut", instance_id, encode_utc(_T1))]
    assert _counts(backup) == {**source_counts, "ledger_lineage": source_counts["ledger_lineage"] + 1}


def test_history_backup_is_an_exact_current_copy(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    counts = _counts(history)
    main_before = history.read_bytes()

    with hold_maintenance_claims(ledger, history) as claims:
        backup = backup_database(history, history=True, claim=claims.history, now=_T1)

    assert backup.name == "history.db.backup-20261125T093001250000Z"
    assert history.read_bytes() == main_before
    assert _counts(backup) == counts
    assert _query(backup, "SELECT run_token FROM history_runs") == [("seeded",)]
    with closing(_immutable(backup)) as connection:
        validate_history_reader_contract(connection)


def test_a_failed_backup_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = _pair(tmp_path)
    before = _files(tmp_path)

    def reject(*_arguments, **_keywords) -> None:
        raise _BackupVerificationFailed("the backup failed its integrity check")

    monkeypatch.setattr(maintenance, "_verify_backup", reject)
    with hold_maintenance_claims(ledger, history) as claims:
        with pytest.raises(DatabaseBackupFailed, match="failed SQLite's integrity check") as failed:
            backup_database(ledger, history=False, claim=claims.ledger, now=_T1)
    assert "Keep the database files" in str(failed.value)
    assert "free space" not in str(failed.value)
    monkeypatch.undo()

    real_rename = os.rename

    def no_space(source, destination) -> None:
        if ".backup-" in str(destination):
            raise OSError(28, "There is not enough space on the disk")
        real_rename(source, destination)

    monkeypatch.setattr(os, "rename", no_space)
    with hold_maintenance_claims(ledger, history) as claims:
        with pytest.raises(DatabaseBackupFailed, match="free space"):
            backup_database(history, history=True, claim=claims.history, now=_T1)

    after = _files(tmp_path)
    assert not [name for name in after if ".backup-" in name or name.endswith(".tmp")]
    assert {name: after[name] for name in before if not name.endswith(("-wal", "-shm"))} == {
        name: value for name, value in before.items() if not name.endswith(("-wal", "-shm"))
    }


def test_a_backup_never_replaces_a_file_at_its_name(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    occupied = _touch(tmp_path / "ledger.db.backup-20261125T093001250000Z", b"someone else's")

    with hold_maintenance_claims(ledger, history) as claims:
        with pytest.raises(DatabaseBackupFailed):
            backup_database(ledger, history=False, claim=claims.ledger, now=_T1)

    assert occupied.read_bytes() == b"someone else's"
    assert not list(tmp_path.glob("*.tmp"))


def test_a_ledger_backup_in_place_is_not_backed_up_again(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    with hold_maintenance_claims(ledger, history) as claims:
        backup = backup_database(ledger, history=False, claim=claims.ledger, now=_T1)
    copied = tmp_path / "copied"
    copied.mkdir()
    shutil.copyfile(backup, copied / "ledger.db")
    with hold_maintenance_claims(copied / "ledger.db", copied / "history.db") as claims:
        with pytest.raises(LedgerIsBackup):
            backup_database(copied / "ledger.db", history=False, claim=claims.ledger, now=_T2)
    assert sorted(path.name for path in copied.iterdir()) == [
        "history.db.claim", "ledger.db", "ledger.db.claim",
    ]


def test_maintenance_requires_the_databases_own_exclusive_claim(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path, recorded=False)
    with hold_maintenance_claims(ledger, history) as claims:
        for call in (
            lambda: backup_database(ledger, history=False, claim=claims.history, now=_T1),
            lambda: check_database(history, history=True, claim=claims.ledger),
            lambda: restore_database(ledger, ledger, history=False, claim=claims.history, now=_T1),
            lambda: rotate_backups(ledger, claim=claims.history, keep=3, protect=ledger),
        ):
            with pytest.raises(ValueError, match="exclusive maintenance claim"):
                call()
        with pytest.raises(ValueError, match="timezone-aware"):
            backup_database(ledger, history=False, claim=claims.ledger, now=datetime(2026, 1, 1))


# --- rotation ----------------------------------------------------------------


def test_rotation_removes_only_the_oldest_recognized_backups(tmp_path: Path) -> None:
    import _winapi

    main = tmp_path / "ledger.db"
    _touch(main)
    stamps = [
        "20261120T000000000000", "20261121T000000000000", "20261122T000000000000",
        "20261123T000000000000", "20261124T000000000000",
    ]
    recognized = [_touch(tmp_path / f"ledger.db.backup-{stamp}Z") for stamp in stamps]
    # The newly published backup carries an older stamp than two others
    # (a clock set back): it is kept anyway, with the newest two others.
    published = _touch(tmp_path / "ledger.db.backup-20261119T000000000000Z")
    target = tmp_path / "elsewhere"
    target.mkdir()
    (tmp_path / "ledger.db.backup-20261130T000000000000Z").mkdir()
    _winapi.CreateJunction(str(target), str(tmp_path / "ledger.db.backup-20261129T000000000000Z"))
    noise = [
        _touch(tmp_path / name) for name in (
            "ledger.db.backup-v4-20261101T000000000000Z",
            "ledger.db.backup-v4-20261101T000000000001Z",
            "ledger.db.backup-0123456789abcdef.tmp",
            "ledger.db.migration-0123456789abcdef.tmp",
            "ledger.db.restore-0123456789abcdef.tmp",
            "ledger.db.replaced-20261101T000000000000Z",
            "ledger.db.replaced-20261101T000000000000Z-wal",
            "history.db.backup-20261101T000000000000Z",
            "ledger.db.backup-20261101T000000000000Z.old",
            "ledger.db.backup-2026110T000000000000Z",
            "LEDGER.DB.backup-20261101T000000000000Z",
            "ledger.db.backup-20261101T000000000000",
            # Unicode digits are not the stamp's ASCII digits.
            "ledger.db.backup-٢٠٢٦١١٢٩T000000000000Z",
        )
    ]
    before = _files(tmp_path)

    with hold_maintenance_claims(main, tmp_path / "history.db") as claims:
        rotation = rotate_backups(main, claim=claims.ledger, keep=3, protect=published)

    assert rotation.failures == ()
    assert sorted(path.name for path in rotation.removed) == sorted(
        path.name for path in recognized[:3]
    )
    assert not any(path.exists() for path in recognized[:3])
    assert all(path.exists() for path in (*recognized[3:], published, *noise))
    assert (tmp_path / "ledger.db.backup-20261130T000000000000Z").is_dir()
    assert os.path.lexists(tmp_path / "ledger.db.backup-20261129T000000000000Z")
    assert _files(tmp_path) == {
        name: value for name, value in before.items()
        if name not in {path.name for path in recognized[:3]}
    }


def test_a_failed_removal_is_reported_and_the_rest_rotate(tmp_path: Path) -> None:
    import _winapi

    main = tmp_path / "history.db"
    _touch(main)
    names = [f"history.db.backup-2026112{day}T000000000000Z" for day in range(5)]
    paths = [_touch(tmp_path / name) for name in names]
    # Open without delete sharing, as another program reading it would.
    handle = _winapi.CreateFile(
        str(paths[0]), _winapi.GENERIC_READ, 0, 0, _winapi.OPEN_EXISTING, 0, 0,
    )
    try:
        with hold_maintenance_claims(tmp_path / "ledger.db", main) as claims:
            rotation = rotate_backups(main, claim=claims.history, keep=3, protect=paths[4])
    finally:
        _winapi.CloseHandle(handle)
    assert [path.name for path, _ in rotation.failures] == [names[0]]
    assert [path.name for path in rotation.removed] == [names[1]]
    assert paths[0].exists() and not paths[1].exists()
    assert all(path.exists() for path in paths[2:])


# --- check -------------------------------------------------------------------


def _check(ledger: Path, history: Path, *, role_history: bool = False):
    with hold_maintenance_claims(ledger, history) as claims:
        return check_database(
            history if role_history else ledger,
            history=role_history,
            claim=claims.history if role_history else claims.ledger,
        )


def _replace_main(main: Path, source: Path) -> None:
    """Copy ``source``'s committed content over ``main``, sidecars removed."""

    for suffix in ("", "-wal", "-shm"):
        Path(f"{main}{suffix}").unlink(missing_ok=True)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as reader:
        with closing(sqlite3.connect(main)) as writer:
            reader.backup(writer)


def _garble(main: Path, offset: int) -> None:
    data = bytearray(main.read_bytes())
    data[offset:offset + 512] = b"\xa5" * 512
    main.write_bytes(bytes(data))


def _break_an_index(ledger: Path) -> None:
    """Zero the end of the hosts index page: integrity_check reports rows, nothing raises."""

    with closing(sqlite3.connect(ledger)) as connection:
        page = connection.execute(
            "SELECT rootpage FROM sqlite_schema WHERE name = 'sqlite_autoindex_hosts_1'"
        ).fetchone()[0]
        size = connection.execute("PRAGMA page_size").fetchone()[0]
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    data = bytearray(ledger.read_bytes())
    end = page * size
    data[end - 40:end] = b"\x00" * 40
    ledger.write_bytes(bytes(data))


def _violate_foreign_keys(ledger: Path, rows: int) -> None:
    with closing(sqlite3.connect(ledger, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.executemany(
            "INSERT INTO mappings(source_location_id, target_location_id, created_at) "
            "VALUES (?, ?, '2026-01-01T00:00:00.000000Z')",
            [(1000 + index, 2000 + index) for index in range(rows)],
        )


@pytest.mark.parametrize(("shape", "state"), [
    ("ok", DatabaseCheckState.OK),
    ("missing", DatabaseCheckState.MISSING),
    ("garbage-0", DatabaseCheckState.DAMAGED),
    ("garbage-100", DatabaseCheckState.DAMAGED),
    ("broken-index", DatabaseCheckState.DAMAGED),
    ("journal", DatabaseCheckState.DAMAGED),
    ("foreign-keys", DatabaseCheckState.FOREIGN_KEY_VIOLATIONS),
    ("newer", DatabaseCheckState.NEWER),
    ("wrong-role", DatabaseCheckState.WRONG_ROLE),
    ("old-shape", DatabaseCheckState.UNSUPPORTED),
    ("is-backup", DatabaseCheckState.IS_BACKUP),
])
def test_check_reports_each_ledger_state_and_writes_nothing(
    tmp_path: Path, shape: str, state: DatabaseCheckState,
) -> None:
    ledger, history = _pair(tmp_path)
    if shape == "missing":
        ledger.unlink()
    elif shape.startswith("garbage-"):
        _garble(ledger, int(shape.removeprefix("garbage-")))
    elif shape == "broken-index":
        _break_an_index(ledger)
    elif shape == "journal":
        Path(f"{ledger}-journal").write_bytes(b"")
    elif shape == "foreign-keys":
        _violate_foreign_keys(ledger, 2)
    elif shape == "newer":
        with closing(sqlite3.connect(ledger)) as connection, connection:
            connection.execute("UPDATE schema_metadata SET value = '6' WHERE key = 'schema_version'")
    elif shape == "wrong-role":
        _replace_main(ledger, history)
    elif shape == "old-shape":
        with closing(sqlite3.connect(ledger)) as connection, connection:
            connection.execute("DROP TABLE ledger_lineage")
    elif shape == "is-backup":
        with hold_maintenance_claims(ledger, history) as claims:
            backup = backup_database(ledger, history=False, claim=claims.ledger, now=_T1)
        _replace_main(ledger, backup)
    before = _files(tmp_path)

    result = _check(ledger, history)

    assert (result.role, result.state) == ("ledger", state)
    assert bool(result.problems) == (
        state not in (DatabaseCheckState.OK, DatabaseCheckState.MISSING)
    )
    assert len(result.problems) <= 20
    assert _files(tmp_path) == before


def test_check_bounds_its_problems_to_twenty(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path, recorded=False)
    _violate_foreign_keys(ledger, 30)
    result = _check(ledger, history)
    # Admitted and intact apart from the violations: not damage.
    assert result.state is DatabaseCheckState.FOREIGN_KEY_VIOLATIONS
    assert len(result.problems) == 20
    assert result.problems[0].startswith("foreign key violation: mappings row ")

    class Damaged:
        # integrity_check already reports the bound; nothing more is read.
        def execute(self, sql: str):
            if sql == "PRAGMA integrity_check(20)":
                return [(f"problem {index}",) for index in range(20)]
            raise AssertionError(sql)

    integrity, violations = maintenance._problems(Damaged())
    assert (len(integrity), violations) == (20, [])


def test_check_reports_older_databases_and_sidecars_without_a_main(tmp_path: Path) -> None:
    ledger, history = copy_released_pair(tmp_path / "released")
    assert _check(ledger, history).state is DatabaseCheckState.OLDER
    assert _check(ledger, history, role_history=True).state is DatabaseCheckState.OLDER

    current, current_history = _pair(tmp_path / "current", recorded=False)
    current.unlink()
    Path(f"{current}-wal").write_bytes(b"")
    result = _check(current, current_history)
    assert result.state is DatabaseCheckState.MISSING
    assert result.problems == ("ledger.db-wal is present without its database",)


# --- restore -----------------------------------------------------------------


def _backup(ledger: Path, history: Path, *, role_history: bool = False, now=_T1) -> Path:
    with hold_maintenance_claims(ledger, history) as claims:
        return backup_database(
            history if role_history else ledger, history=role_history,
            claim=claims.history if role_history else claims.ledger, now=now,
        )


def _restore(ledger: Path, history: Path, backup: Path, *, role_history: bool = False):
    with hold_maintenance_claims(ledger, history) as claims:
        return restore_database(
            history if role_history else ledger, backup, history=role_history,
            claim=claims.history if role_history else claims.ledger, now=_T2,
        )


def test_ledger_restore_in_place_issues_a_new_instance_and_keeps_the_lineage(
    tmp_path: Path,
) -> None:
    ledger, history = _pair(tmp_path)
    old_instance = _instance(ledger)
    backup = _backup(ledger, history)
    backup_counts = _counts(backup)
    # The live ledger moves on after the backup.
    copy = operation(OperationKind.COPY, source=file_stat(identity_index=9), target=None)
    setup_recorder(ledger, plan((copy,)), run_token="b" * 32).recorder.close()
    replaced_counts = _counts(ledger)
    assert replaced_counts != {**backup_counts, "ledger_lineage": 0}
    inode = ledger.stat().st_ino

    result = _restore(ledger, history, backup)

    assert (result.role, result.kept_as, result.source) == ("ledger", "backup", backup)
    assert result.kept == ledger.with_name("ledger.db.backup-20261125T100000000000Z")
    assert (result.restored_instance_id, result.cut_at) == (old_instance, _T1)
    assert result.instance_id not in (None, old_instance)
    assert ledger.stat().st_ino == inode
    assert _instance(ledger) == result.instance_id
    assert _counts(ledger) == backup_counts
    assert _query(ledger, "SELECT kind, instance_id, at FROM ledger_lineage") == [
        ("backup-cut", old_instance, encode_utc(_T1)),
    ]
    # The pre-restore backup holds what was replaced, cut at the restore.
    assert _counts(result.kept) == {**replaced_counts, "ledger_lineage": 1}
    assert _query(result.kept, "SELECT instance_id, at FROM ledger_lineage") == [
        (old_instance, encode_utc(_T2)),
    ]
    assert validate_database_pair(ledger, history).state is DatabasePairState.READY
    assert not list(tmp_path.glob("*.tmp"))


def test_a_database_with_only_foreign_key_violations_is_restored_in_place(
    tmp_path: Path,
) -> None:
    # It is admitted and backs up cleanly, so no backup, no change means in place.
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)
    _violate_foreign_keys(ledger, 2)
    assert _check(ledger, history).state is DatabaseCheckState.FOREIGN_KEY_VIOLATIONS

    result = _restore(ledger, history, backup)

    assert result.kept_as == "backup"
    assert _query(
        result.kept, "SELECT count(*) FROM mappings WHERE source_location_id >= 1000",
    ) == [(2,)]
    assert not list(tmp_path.glob("ledger.db.replaced-*"))
    assert _check(ledger, history).state is DatabaseCheckState.OK


def test_a_database_failing_integrity_check_is_set_aside(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)
    _break_an_index(ledger)
    broken = ledger.read_bytes()

    result = _restore(ledger, history, backup)

    assert result.kept_as == "replaced"
    assert result.kept.read_bytes() == broken
    assert not list(tmp_path.glob("ledger.db.backup-20261125T100000000000Z"))
    assert _check(ledger, history).state is DatabaseCheckState.OK


def test_restoring_from_the_oldest_backup_rotates_nothing(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    backups = [_backup(ledger, history, now=_T1 + timedelta(minutes=minute)) for minute in range(4)]
    contents = {path: path.read_bytes() for path in backups}

    result = _restore(ledger, history, backups[0])

    assert result.kept_as == "backup" and result.kept.exists()
    assert {path: path.read_bytes() for path in backups} == contents
    assert len(list(tmp_path.glob("ledger.db.backup-*"))) == 5


@pytest.mark.parametrize("offset", (0, 100))
def test_a_damaged_ledger_is_set_aside_with_its_sidecars_byte_for_byte(
    tmp_path: Path, offset: int,
) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)
    # Leave committed frames in the -wal, then damage the main.
    connection = sqlite3.connect(ledger, isolation_level=None)
    connection.execute("PRAGMA wal_autocheckpoint = 0")
    connection.execute("UPDATE hosts SET display_name = 'after backup'")
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
    connection.close()
    _garble(ledger, offset)
    damaged = {
        suffix: Path(f"{ledger}{suffix}").read_bytes()
        for suffix in ("", "-wal", "-shm") if Path(f"{ledger}{suffix}").exists()
    }
    assert set(damaged) == {"", "-wal", "-shm"} and damaged["-wal"]

    result = _restore(ledger, history, backup)

    assert (result.kept_as, result.kept) == (
        "replaced", ledger.with_name("ledger.db.replaced-20261125T100000000000Z"),
    )
    assert {
        suffix: Path(f"{result.kept}{suffix}").read_bytes() for suffix in damaged
    } == damaged
    assert ledger.read_bytes()[18:20] == b"\x02\x02"
    assert not Path(f"{ledger}-journal").exists()
    assert _instance(ledger) == result.instance_id
    assert validate_database_pair(ledger, history).state is DatabasePairState.READY
    assert not list(tmp_path.glob("*.tmp"))


def test_history_restores_in_place_into_a_missing_slot_and_aside(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history, role_history=True)
    seed_history_run(history, "later", ledger_instance_id=_instance(ledger),
                     created_at=NOW, started_at=NOW)

    result = _restore(ledger, history, backup, role_history=True)
    assert (result.kept_as, result.instance_id, result.cut_at) == ("backup", None, None)
    assert _query(history, "SELECT run_token FROM history_runs") == [("seeded",)]
    assert _query(result.kept, "SELECT run_token FROM history_runs ORDER BY 1") == [
        ("later",), ("seeded",),
    ]

    for suffix in ("", "-wal", "-shm"):
        Path(f"{history}{suffix}").unlink(missing_ok=True)
    result = _restore(ledger, history, backup, role_history=True)
    assert (result.kept_as, result.kept) == (None, None)
    assert history.read_bytes()[18:20] == b"\x02\x02"
    assert validate_database_pair(ledger, history).state is DatabasePairState.READY

    released = copy_released_pair(tmp_path / "released")[1]
    for suffix in ("", "-wal", "-shm"):
        Path(f"{history}{suffix}").unlink(missing_ok=True)
        if Path(f"{released}{suffix}").exists():
            shutil.copyfile(f"{released}{suffix}", f"{history}{suffix}")
    result = _restore(ledger, history, backup, role_history=True)
    assert result.kept_as == "replaced"
    assert validate_database_pair(ledger, history).state is DatabasePairState.READY


def test_a_history_copy_that_did_not_land_is_unconfirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # History has no instance id: its row counts tell restored from replaced.
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history, role_history=True)
    seed_history_run(history, "later", ledger_instance_id=_instance(ledger),
                     created_at=NOW, started_at=NOW)
    monkeypatch.setattr(maintenance, "_copy_into_place", lambda image, path: None)

    with pytest.raises(DatabaseRestoreFailed, match="could not be confirmed") as failed:
        _restore(ledger, history, backup, role_history=True)
    assert failed.value.unconfirmed
    assert failed.value.kept is not None and str(failed.value.kept) in str(failed.value)


def test_a_restore_image_that_fails_verification_restores_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)
    instance_id = _instance(ledger)

    def reject(*_arguments, **_keywords) -> None:
        raise sqlite3.DatabaseError("restore image row counts differ from the backup")

    monkeypatch.setattr(maintenance, "_verify_image", reject)
    with pytest.raises(DatabaseRestoreFailed, match="nothing was restored") as failed:
        _restore(ledger, history, backup)
    assert not failed.value.unconfirmed
    # The pre-restore backup was published first; the failure names it.
    assert failed.value.kept == ledger.with_name("ledger.db.backup-20261125T100000000000Z")
    assert failed.value.kept.exists() and str(failed.value.kept) in str(failed.value)
    assert _instance(ledger) == instance_id
    assert not list(tmp_path.glob("*.restore-*"))


def test_a_migrated_pair_backs_up_and_restores(tmp_path: Path) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")
    assert migrate_database_pair(ledger, history).contract.state is DatabasePairState.READY
    backup = _backup(ledger, history)
    result = _restore(ledger, history, backup)
    assert result.kept_as == "backup"
    assert validate_database_pair(ledger, history).state is DatabasePairState.READY
