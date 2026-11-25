"""CLI admission of a one-present pair: complete it up front and say so, or change nothing."""

from __future__ import annotations

from contextlib import closing
import io
import os
from pathlib import Path
import sqlite3

import pytest

import namisync.interfaces.cli as cli_module
from namisync.db.claims import acquire_database_claim
from namisync.db.schema import initialize_ledger
from namisync.interfaces.cli import EXIT_FAILED, EXIT_REFUSED, EXIT_SUCCESS, main

from _db_fixtures import NOW, seed_history_run
from _released_fixture import copy_released_role


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows file sharing and claims")

_HISTORY_CREATED = (
    "Created a new history database at {} because it was missing; the existing "
    "ledger is kept."
)
_LEDGER_CREATED = (
    "Created a new ledger at {} because it was missing. The existing history is "
    "kept; its runs are shown as belonging to an earlier ledger."
)


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes() for path in directory.iterdir()
        if path.is_file() and not path.name.endswith(".claim")
    }


def _read(main_file: Path, sql: str) -> list[tuple]:
    with closing(sqlite3.connect(main_file.as_uri() + "?mode=ro", uri=True)) as connection:
        return connection.execute(sql).fetchall()


def _lines(output: io.StringIO, prefix: str) -> list[str]:
    return [line for line in output.getvalue().splitlines() if line.startswith(prefix)]


def _arguments(command: list[str], ledger: Path, history: Path) -> list[str]:
    return [*command, "--database", str(ledger), "--history-database", str(history)]


def test_inventory_beside_a_lone_ledger_creates_a_history_and_says_so(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    ledger = initialize_ledger(tmp_path / "data" / "ledger.db")
    history = tmp_path / "data" / "history.db"
    stdout, stderr = io.StringIO(), io.StringIO()

    result = main(_arguments(["inventory", str(root)], ledger, history), stdout=stdout, stderr=stderr)

    assert result == EXIT_SUCCESS, stderr.getvalue()
    assert _lines(stdout, "Created") == [_HISTORY_CREATED.format(history)]
    assert _lines(stdout, "Updated") == []
    assert len(_read(history, "SELECT run_token FROM history_runs")) == 1
    stdout = io.StringIO()
    assert main(
        _arguments(["inventory", str(root)], ledger, history), stdout=stdout, stderr=io.StringIO(),
    ) == EXIT_SUCCESS
    assert _lines(stdout, "Created") == []


def test_inventory_beside_a_lone_released_history_updates_it_and_creates_a_ledger(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    history = copy_released_role(tmp_path / "data", history=True)
    ledger = tmp_path / "data" / "ledger.db"
    stdout, stderr = io.StringIO(), io.StringIO()

    result = main(_arguments(["inventory", str(root)], ledger, history), stdout=stdout, stderr=stderr)

    assert result == EXIT_SUCCESS, stderr.getvalue()
    backup = next(ledger.parent.glob("history.db.backup-v8-*"))
    assert stdout.getvalue().splitlines()[:2] == [
        f"Updated the history (v8) database written by NamiSync 0.1.0; backup kept at: {backup}"
        "; the history's runs are shown as belonging to an earlier ledger",
        _LEDGER_CREATED.format(ledger),
    ]
    instance_id = _read(ledger, "SELECT value FROM schema_metadata WHERE key = 'instance_id'")[0][0]
    stamps = [row[0] for row in _read(history, "SELECT ledger_instance_id FROM history_runs")]
    # The released runs stay unstamped; only the new inventory run joins the ledger.
    assert sorted(stamps, key=str) == sorted([None] * 15 + [instance_id], key=str)

    stdout, stderr = io.StringIO(), io.StringIO()
    assert main(
        ["history", "--database", str(ledger), "--history-database", str(history)],
        stdout=stdout, stderr=stderr,
    ) == EXIT_SUCCESS
    assert stdout.getvalue().count("(earlier ledger)") == 15


def test_declined_sync_beside_a_lone_history_still_creates_the_ledger(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    history = tmp_path / "data" / "history.db"
    seed_history_run(history, "kept", ledger_instance_id="a" * 32, created_at=NOW, started_at=NOW)
    ledger = tmp_path / "data" / "ledger.db"
    stdout, stderr = io.StringIO(), io.StringIO()

    result = main(
        _arguments(["sync", str(source), str(target)], ledger, history),
        stdin=io.StringIO(""), stdout=stdout, stderr=stderr,
    )

    assert result == EXIT_SUCCESS, stderr.getvalue()
    assert _lines(stdout, "Created") == [_LEDGER_CREATED.format(ledger)]
    assert _read(ledger, "SELECT kind, instance_id FROM ledger_lineage") == [
        ("replaced-missing", None),
    ]


@pytest.mark.parametrize("arguments", (
    ["inventory", "relative-root"],
    ["inventory", "{missing}"],
    ["verify", "{root}", "--path", "a/../b"],
    ["sync", "relative-source", "{root}"],
    ["inventory", "{root}"],
), ids=(
    "relative-root", "missing-root", "unsafe-path", "sync-relative-source",
    "history-inside-root",
))
def test_refused_roots_create_nothing(tmp_path: Path, arguments: list[str]) -> None:
    root = tmp_path / "root"
    root.mkdir()
    data = tmp_path / "data"
    ledger = initialize_ledger(data / "ledger.db")
    history = (
        root / "nami-history.db" if arguments == ["inventory", "{root}"]
        else data / "history.db"
    )
    before = (
        sorted(path.name for path in data.iterdir()), _files(data),
        sorted(path.name for path in root.iterdir()),
    )
    stdout = io.StringIO()
    filled = [
        argument.format(root=root, missing=tmp_path / "absent") for argument in arguments
    ]

    result = main(
        _arguments(filled, ledger, history),
        stdin=io.StringIO(""), stdout=stdout, stderr=io.StringIO(),
    )

    assert result != EXIT_SUCCESS
    assert _lines(stdout, "Created") == []
    assert (
        sorted(path.name for path in data.iterdir()), _files(data),
        sorted(path.name for path in root.iterdir()),
    ) == before


@pytest.mark.parametrize("present", ("ledger", "history"))
def test_location_id_never_creates_the_missing_database(tmp_path: Path, present: str) -> None:
    # --location-id gives no root to check the new database's path against.
    data = tmp_path / "data"
    ledger, history = data / "ledger.db", data / "history.db"
    if present == "ledger":
        initialize_ledger(ledger)
    else:
        seed_history_run(history, "kept", ledger_instance_id=None, created_at=NOW, started_at=NOW)
    before = sorted(path.name for path in data.iterdir()), _files(data)
    stdout, stderr = io.StringIO(), io.StringIO()

    result = main(
        _arguments(["inventory", "--location-id", "1"], ledger, history),
        stdout=stdout, stderr=stderr,
    )

    assert result == EXIT_REFUSED
    assert stdout.getvalue() == ""
    role = "history" if present == "ledger" else "ledger"
    assert stderr.getvalue().splitlines() == [
        f"Database pair refused: {role}-missing.",
        f"The {role} database is missing. A --location-id command does "
        "not create it, because no root is given to check its path against. Run "
        "the command with its ROOT, run a sync, or start NamiSync once to create it, "
        "then try again. Nothing was changed.",
    ]
    assert (sorted(path.name for path in data.iterdir()), _files(data)) == before


def test_location_id_never_creates_a_database_inside_a_managed_root(tmp_path: Path) -> None:
    # The reproduction: the History path lies inside the location's root.
    root = tmp_path / "root"
    root.mkdir()
    ledger = tmp_path / "data" / "ledger.db"
    assert main(
        ["inventory", str(root), "--database", str(ledger),
         "--history-database", str(tmp_path / "data" / "history.db")],
        stdout=io.StringIO(), stderr=io.StringIO(),
    ) == EXIT_SUCCESS
    inside = root / "nami-history.db"
    stdout, stderr = io.StringIO(), io.StringIO()

    result = main(
        _arguments(["inventory", "--location-id", "1"], ledger, inside),
        stdout=stdout, stderr=stderr,
    )

    assert result == EXIT_REFUSED
    assert _lines(stdout, "Created") == []
    assert stderr.getvalue().startswith("Database pair refused: history-missing.")
    assert sorted(path.name for path in root.iterdir()) == []


def test_a_claim_on_the_lone_database_refuses_and_creates_nothing(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    ledger = initialize_ledger(tmp_path / "data" / "ledger.db")
    history = tmp_path / "data" / "history.db"
    before = _files(ledger.parent)
    stdout, stderr = io.StringIO(), io.StringIO()

    with acquire_database_claim(ledger, exclusive=False):
        result = main(
            _arguments(["inventory", str(root)], ledger, history), stdout=stdout, stderr=stderr,
        )

    assert result == EXIT_REFUSED
    assert _lines(stdout, "Created") == []
    assert "Database pair refused: database-in-use." in stderr.getvalue()
    assert "delete" not in stderr.getvalue().lower()
    assert _files(ledger.parent) == before and not history.exists()


def test_failed_placement_check_never_leads_to_an_unannounced_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    ledger = initialize_ledger(tmp_path / "data" / "ledger.db")
    history = tmp_path / "data" / "history.db"
    monkeypatch.setattr(
        cli_module.NamiSyncService, "database_placement_admitted", lambda *_, **__: False,
    )
    stdout, stderr = io.StringIO(), io.StringIO()

    result = main(_arguments(["inventory", str(root)], ledger, history), stdout=stdout, stderr=stderr)

    assert result == EXIT_FAILED
    assert _lines(stdout, "Created") == []
    assert stderr.getvalue().startswith(
        "Inventory could not start: database pair refused (history-missing)."
    )
    assert "once to create a new one" in stderr.getvalue()
    assert not history.exists()


# --- the read-only history command -----------------------------------------------


def test_history_beside_a_lone_ledger_lists_nothing_and_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = initialize_ledger(tmp_path / "ledger.db")
    history = tmp_path / "history.db"
    monkeypatch.setattr(cli_module, "default_database_paths", lambda: (ledger, history))
    before = sorted(path.name for path in tmp_path.iterdir()), _files(tmp_path)
    stdout = io.StringIO()

    assert main(["history"], stdout=stdout, stderr=io.StringIO()) == EXIT_SUCCESS

    assert stdout.getvalue() == "No retained history runs.\n"
    assert (sorted(path.name for path in tmp_path.iterdir()), _files(tmp_path)) == before


def test_history_of_a_lone_current_history_lists_it_without_creating_a_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    seed_history_run(history, "kept", ledger_instance_id="a" * 32, created_at=NOW, started_at=NOW)
    monkeypatch.setattr(cli_module, "default_database_paths", lambda: (ledger, history))
    stdout, stderr = io.StringIO(), io.StringIO()

    assert main(["history"], stdout=stdout, stderr=stderr) == EXIT_SUCCESS

    assert "kept" in stdout.getvalue()
    assert stderr.getvalue() == f"Ledger membership is unknown: no usable ledger at {ledger}.\n"
    # The History reader's own -wal and -shm may appear; nothing of a ledger does.
    assert not [path.name for path in tmp_path.iterdir() if path.name.startswith("ledger")]


def test_history_of_a_lone_released_history_refuses_with_the_update_direction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = copy_released_role(tmp_path, history=True)
    ledger = tmp_path / "ledger.db"
    monkeypatch.setattr(cli_module, "default_database_paths", lambda: (ledger, history))
    before = _files(tmp_path)
    stdout, stderr = io.StringIO(), io.StringIO()

    assert main(["history"], stdout=stdout, stderr=stderr) == EXIT_REFUSED

    assert stdout.getvalue() == ""
    assert stderr.getvalue().startswith("History admission refused: The history database")
    assert "which is created new if it is missing" in stderr.getvalue()
    assert "cannot be updated" not in stderr.getvalue()
    assert _files(tmp_path) == before and not ledger.exists()
