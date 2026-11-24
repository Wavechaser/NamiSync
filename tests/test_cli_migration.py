"""CLI admission of a released v0.1.0 pair: migrate up front, or refuse with direction."""

from __future__ import annotations

from contextlib import closing
import io
import os
from pathlib import Path
import re
import sqlite3

import pytest

import namisync.interfaces.cli as cli_module
from namisync.db.claims import acquire_database_claim
from namisync.db.schema import initialize_history, initialize_ledger
from namisync.interfaces.cli import EXIT_REFUSED, EXIT_SUCCESS, main

from _released_fixture import carried_rows, copy_released_pair


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows file sharing and claims")


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes() for path in directory.iterdir()
        if path.is_file() and not path.name.endswith(".claim")
    }


def _stamps(ledger: Path, history: Path) -> tuple[str, set[str | None]]:
    with closing(sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True)) as connection:
        instance_id = connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'instance_id'"
        ).fetchone()[0]
    with closing(sqlite3.connect(history.as_uri() + "?mode=ro", uri=True)) as connection:
        stamps = {row[0] for row in connection.execute("SELECT ledger_instance_id FROM history_runs")}
    return instance_id, stamps


def test_mutating_command_migrates_a_released_pair_up_front_then_proceeds(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("a", encoding="utf-8")
    ledger, history = copy_released_pair(tmp_path / "data")
    old_runs = carried_rows(history, tmp_path / "old", history=True)["history_runs"]
    stdout, stderr = io.StringIO(), io.StringIO()

    result = main(
        ["inventory", str(root), "--database", str(ledger), "--history-database", str(history)],
        stdout=stdout, stderr=stderr,
    )

    assert result == EXIT_SUCCESS, stderr.getvalue()
    notices = [line for line in stdout.getvalue().splitlines() if line.startswith("Updated")]
    backups = sorted(ledger.parent.glob("*.backup-*"))
    assert [path.name[:20] for path in backups] == ["history.db.backup-v8", "ledger.db.backup-v4-"]
    assert notices == [
        "Updated the ledger (v4) and history (v8) databases written by NamiSync 0.1.0; "
        f"backups kept at: {ledger.parent / backups[1].name}, {ledger.parent / backups[0].name}"
    ]
    instance_id, stamps = _stamps(ledger, history)
    # The released runs and the new inventory run all carry the ledger instance.
    assert stamps == {instance_id}
    assert len(carried_rows(history, tmp_path / "new", history=True)["history_runs"]) == (
        len(old_runs) + 1
    )

    stdout = io.StringIO()
    assert main(
        ["inventory", str(root), "--database", str(ledger), "--history-database", str(history)],
        stdout=stdout, stderr=io.StringIO(),
    ) == EXIT_SUCCESS
    assert "Updated" not in stdout.getvalue()
    assert len(list(ledger.parent.glob("*.backup-*"))) == 2


def test_fresh_pair_runs_record_the_ledger_instance(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    for command in ("inventory", "baseline"):
        assert main(
            [command, str(root), "--database", str(ledger), "--history-database", str(history)],
            stdout=io.StringIO(), stderr=io.StringIO(),
        ) == EXIT_SUCCESS
    instance_id, stamps = _stamps(ledger, history)
    assert re.fullmatch("[0-9a-f]{32}", instance_id) and stamps == {instance_id}


def test_history_command_refuses_a_released_history_without_migrating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")
    monkeypatch.setattr(cli_module, "default_database_paths", lambda: (ledger, history))
    before = _files(ledger.parent)
    stdout, stderr = io.StringIO(), io.StringIO()

    result = main(["history", "--history-database", str(history)], stdout=stdout, stderr=stderr)

    assert result == EXIT_REFUSED
    assert stdout.getvalue() == ""
    assert stderr.getvalue().startswith("History admission refused: The history database")
    assert "Start NamiSync, or run a sync or inventory command, once" in stderr.getvalue()
    assert "delete" not in stderr.getvalue().lower()
    assert _files(ledger.parent) == before
    assert not list(ledger.parent.glob("*.backup-*"))


def test_mutating_command_refuses_a_newer_database_without_reset_guidance(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    ledger = initialize_ledger(tmp_path / "ledger.db")
    history = initialize_history(tmp_path / "history.db")
    with closing(sqlite3.connect(ledger)) as connection:
        with connection:
            connection.execute("UPDATE schema_metadata SET value = '6' WHERE key = 'schema_version'")
    before = _files(tmp_path)
    stderr = io.StringIO()

    result = main(
        ["inventory", str(root), "--database", str(ledger), "--history-database", str(history)],
        stdout=io.StringIO(), stderr=stderr,
    )

    assert result == EXIT_REFUSED
    assert "Database pair refused: ledger-newer." in stderr.getvalue()
    assert "written by a newer NamiSync (schema version 6)" in stderr.getvalue()
    assert not re.search(r"delete|archive|reset", stderr.getvalue(), re.IGNORECASE)
    assert _files(tmp_path) == before


def test_mutating_command_reports_a_refused_migration_and_changes_nothing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    ledger, history = copy_released_pair(tmp_path / "data")
    before = _files(ledger.parent)
    stdout, stderr = io.StringIO(), io.StringIO()

    with acquire_database_claim(history, exclusive=False):
        result = main(
            ["inventory", str(root), "--database", str(ledger), "--history-database", str(history)],
            stdout=stdout, stderr=stderr,
        )

    assert result == EXIT_REFUSED
    assert "Updated" not in stdout.getvalue()
    assert "Database pair refused: database-in-use." in stderr.getvalue()
    assert "is in use by NamiSync work" in stderr.getvalue()
    assert "delete" not in stderr.getvalue().lower()
    assert _files(ledger.parent) == before


def test_notice_names_only_the_database_that_migrated(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    data = tmp_path / "data"
    ledger = initialize_ledger(data / "ledger.db")
    history = copy_released_pair(tmp_path / "released")[1]
    for suffix in ("", "-wal", "-shm"):
        Path(f"{data / 'history.db'}{suffix}").write_bytes(Path(f"{history}{suffix}").read_bytes())
    history = data / "history.db"
    stdout = io.StringIO()

    assert main(
        ["inventory", str(root), "--database", str(ledger), "--history-database", str(history)],
        stdout=stdout, stderr=io.StringIO(),
    ) == EXIT_SUCCESS

    backup = next(data.glob("history.db.backup-v8-*"))
    assert [line for line in stdout.getvalue().splitlines() if line.startswith("Updated")] == [
        "Updated the history (v8) database written by NamiSync 0.1.0; "
        f"backup kept at: {backup}"
    ]
    assert not list(data.glob("ledger.db.backup-*"))


@pytest.mark.parametrize("released", (True, False), ids=("released", "current"))
def test_swapped_database_paths_are_refused_as_swapped_and_change_nothing(
    tmp_path: Path, released: bool,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    if released:
        ledger, history = copy_released_pair(tmp_path / "data")
    else:
        ledger = initialize_ledger(tmp_path / "data" / "ledger.db")
        history = initialize_history(tmp_path / "data" / "history.db")
    before = _files(ledger.parent)
    stdout, stderr = io.StringIO(), io.StringIO()

    result = main(
        ["inventory", str(root), "--database", str(history), "--history-database", str(ledger)],
        stdout=stdout, stderr=stderr,
    )

    assert result == EXIT_REFUSED
    assert "Database pair refused: ledger-wrong-role." in stderr.getvalue()
    assert "look swapped" in stderr.getvalue()
    assert not re.search(r"newer|delete|archive|reset", stderr.getvalue(), re.IGNORECASE)
    assert "Updated" not in stdout.getvalue()
    assert _files(ledger.parent) == before