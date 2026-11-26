"""CLI check, backup and restore: output, exit codes, pairs as found and the A4 gate.

The commands call the existing pair maintenance workflow under both exclusive
claims, so the cases here prove the adapter: what each prints, which exit code
it maps to, that none migrates, completes or creates anything, and the three
closing conditions of the maintenance row with real child processes.
"""

from __future__ import annotations

import base64
from contextlib import closing
from dataclasses import dataclass
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
from time import monotonic, sleep
from types import SimpleNamespace

import pytest

import namisync.db.maintenance as maintenance
from namisync.core.session import (
    FailureDetail, OperationResult, PhaseResult, PhaseStatus, SessionState,
)
import namisync.interfaces.cli as cli_module
from namisync.interfaces.cli import (
    EXIT_FAILED, EXIT_REFUSED, EXIT_SUCCESS, EXIT_USAGE, main,
)
from namisync.interfaces.service import NamiSyncService
from namisync.workflows.database_maintenance import DatabasePairBackup, DatabasePairRestore
from namisync.workflows.database_pair import (
    DatabasePairContract,
    DatabasePairState,
    initialize_database_pair,
    upgrade_database_pair,
)
from namisync.workflows.sync import LedgerInstanceChanged, require_planned_ledger
from namisync.workflows.views import operation_result_view

from _child_process import PROJECT_ROOT, WAIT_SECONDS, Child
from _db_fixtures import NOW, seed_history_run, stored_ledger_instance
from _maintenance_children import DESKTOP, HOLD, RESTORE
from _released_fixture import copy_released_pair


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows file sharing and claims")


@dataclass
class Run:
    code: int
    out: str
    err: str


def _flags(ledger: Path, history: Path) -> list[str]:
    return ["--database", str(ledger), "--history-database", str(history)]


def _selected(ledger: Path, history: Path) -> str:
    return (
        f"These databases were selected with --database '{ledger}' "
        f"--history-database '{history}'. Add the same options to any NamiSync "
        "command above."
    )


def test_a_selected_path_is_shown_as_it_can_be_pasted() -> None:
    # Single quotes keep PowerShell from expanding $, and a bracket is not
    # doubled as it is in other output; every single quote PowerShell reads is
    # doubled, and only control characters are escaped.
    assert cli_module._powershell_quoted(Path(r"C:\data [x] $HOME\it's.db")) == (
        r"'C:\data [x] $HOME\it''s.db'"
    )
    assert cli_module._powershell_quoted(Path("C:\\data\\O\u2019Brien.db")) == (
        "'C:\\data\\O\u2019\u2019Brien.db'"
    )
    assert cli_module._powershell_quoted(Path("C:\\data\x1b$x\\ledger.db")) == (
        "'C:\\data[U+001B]$x\\ledger.db'"
    )


# Every character PowerShell reads as a single or double quote, the characters
# that are live inside double quotes, and others a shell treats specially.
_AWKWARD_NAMES = (
    "it's", "O\u2018Brien", "O\u2019Brien", "low\u201aquote", "rev\u201bquote",
    "\u201cdouble\u201d \u201equote", "$HOME", "$(Get-Date)", "back`tick",
    "two  spaces", "a & b", "a; b", "[x] {y} (z)", "-dash", "emoji \U0001F600",
)
_PARSE_ARGUMENTS = r"""
$cases = Get-Content -LiteralPath $env:NAMISYNC_PARSE_INPUT -Raw -Encoding utf8 | ConvertFrom-Json
$results = foreach ($case in $cases) {
    $tokens = $null
    $errors = $null
    # Parsed only: nothing in the input is evaluated.
    $ast = [System.Management.Automation.Language.Parser]::ParseInput($case, [ref]$tokens, [ref]$errors)
    $elements = @(foreach ($statement in $ast.EndBlock.Statements) {
        foreach ($element in $statement.PipelineElements[0].CommandElements) {
            if ($element -is [System.Management.Automation.Language.StringConstantExpressionAst]) {
                @{ kind = $element.StringConstantType.ToString(); value = $element.Value }
            } else {
                @{ kind = $element.GetType().Name; value = $element.Extent.Text }
            }
        }
    })
    @{ errors = @($errors | ForEach-Object { $_.ErrorId }); elements = $elements }
}
$json = ConvertTo-Json -InputObject @($results) -Depth 5
[System.IO.File]::WriteAllText($env:NAMISYNC_PARSE_OUTPUT, $json, [System.Text.UTF8Encoding]::new($false))
"""


def _parsed_by_powershell(tmp_path: Path, shell: str, sources: list[str]) -> list[dict]:
    """How the real PowerShell parser reads each command line, in one launch."""

    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is not on PATH")
    source, parsed = tmp_path / "sources.json", tmp_path / "parsed.json"
    source.write_text(json.dumps(sources), encoding="utf-8")
    completed = subprocess.run(
        [
            executable, "-NoProfile", "-NonInteractive", "-EncodedCommand",
            base64.b64encode(_PARSE_ARGUMENTS.encode("utf-16-le")).decode("ascii"),
        ],
        env={
            **os.environ,
            "NAMISYNC_PARSE_INPUT": str(source), "NAMISYNC_PARSE_OUTPUT": str(parsed),
        },
        capture_output=True, text=True, timeout=WAIT_SECONDS * 6,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(parsed.read_text(encoding="utf-8"))


# PowerShell 7 and Windows PowerShell 5.1, which every Windows 11 has.
@pytest.mark.parametrize("shell", ["pwsh", "powershell"])
def test_a_selected_path_parses_back_in_powershell_as_the_same_path(
    tmp_path: Path, shell: str,
) -> None:
    data = Path("C:/data")
    cases = []
    for name in (*_AWKWARD_NAMES, "esc\x1bname", "esc\x1b$(Get-Date) ”quote"):
        ledger, history = data / name / "ledger.db", data / f"{name}.db"
        line = cli_module._selected_databases(
            SimpleNamespace(database=str(ledger), history_database=str(history)),
            ledger, history,
        )
        options = line.removeprefix("These databases were selected with ").removesuffix(
            ". Add the same options to any NamiSync command above."
        )
        cases.append(("namisync check " + options, str(ledger), str(history)))

    parsed = _parsed_by_powershell(tmp_path, shell, [source for source, _, _ in cases])

    for (source, ledger, history), result in zip(cases, parsed, strict=True):
        if "\x1b" in ledger:
            # Not shown as it is: its markers, quoted alike, are never run.
            ledger, history = cli_module._safe(ledger), cli_module._safe(history)
        assert (result["errors"], result["elements"]) == ([], [
            {"kind": "BareWord", "value": "namisync"},
            {"kind": "BareWord", "value": "check"},
            {"kind": "BareWord", "value": "--database"},
            {"kind": "SingleQuoted", "value": ledger},
            {"kind": "BareWord", "value": "--history-database"},
            {"kind": "SingleQuoted", "value": history},
        ]), source


@pytest.mark.parametrize("given", [(), ("ledger",), ("history",), ("ledger", "history")])
def test_a_history_refusal_repeats_exactly_the_database_options_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: tuple[str, ...],
) -> None:
    # A 0.1.0 History is refused with direction to run another command.
    ledger, history = copy_released_pair(tmp_path / "it's ’data")
    monkeypatch.setattr(cli_module, "default_database_paths", lambda: (ledger, history))
    options = {"ledger": ["--database", str(ledger)], "history": ["--history-database", str(history)]}

    run = _main(["history", *(value for role in given for value in options[role])])

    assert run.code == EXIT_REFUSED and run.out == ""
    refusal, *repeated = run.err.splitlines()
    assert refusal.startswith("History admission refused: The history database")
    assert "run a sync or inventory command" in refusal
    quoted = {
        "ledger": f"--database {cli_module._powershell_quoted(ledger)}",
        "history": f"--history-database {cli_module._powershell_quoted(history)}",
    }
    if given == ("history",):
        # Followed literally, another command would pair this History with the
        # default ledger: it is told to name its own, and is offered no path.
        assert repeated == [
            f"This command was run with {quoted['history']} and no --database. "
            "Any NamiSync command above must also name this History's own ledger "
            "with --database; otherwise it pairs this History with the default ledger."
        ]
        assert "--database '" not in repeated[0] and str(ledger) not in repeated[0]
        return
    assert repeated == ([
        f"This command was run with {' '.join(quoted[role] for role in given)}. "
        "Add the same options to any NamiSync command above."
    ] if given else [])


def test_history_output_that_directs_no_command_repeats_no_options(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)

    listed = _main(["history", "--history-database", str(history)])
    unknown = _main(["history", "missing-run", *_flags(ledger, history)])

    assert (listed.code, listed.err) == (EXIT_SUCCESS, (
        "Ledger membership is unknown: no ledger was given, only --history-database.\n"
    ))
    assert (unknown.code, unknown.err) == (
        EXIT_USAGE, "No retained history run named missing-run.\n",
    )


def _closing(run: Run, ledger: Path, history: Path) -> str:
    """The outcome line before the closing line that names the custom pair."""

    *_, outcome, selected = run.err.splitlines()
    assert selected == _selected(ledger, history)
    return outcome


def _main(arguments: list[str]) -> Run:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = main(arguments, stdout=stdout, stderr=stderr)
    return Run(code, stdout.getvalue(), stderr.getvalue())


def _process(arguments: list[str]) -> Run:
    """The real entry point, as a user's shell runs it."""

    completed = subprocess.run(
        [sys.executable, "-m", "namisync", *arguments],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=WAIT_SECONDS * 3,
    )
    return Run(completed.returncode, completed.stdout, completed.stderr)


def _pair(directory: Path) -> tuple[Path, Path]:
    ledger, history = directory / "ledger.db", directory / "history.db"
    assert initialize_database_pair(ledger, history).state is DatabasePairState.READY
    seed_history_run(
        history, "seeded", ledger_instance_id=stored_ledger_instance(ledger),
        created_at=NOW, started_at=NOW,
    )
    return ledger, history


def _unlink(main_file: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{main_file}{suffix}").unlink(missing_ok=True)


def _damage(main_file: Path) -> None:
    # No sidecar can hide the damaged page: the pages are all in the main file.
    for suffix in ("-wal", "-shm"):
        Path(f"{main_file}{suffix}").unlink(missing_ok=True)
    data = bytearray(main_file.read_bytes())
    data[100:612] = b"\xa5" * 512
    main_file.write_bytes(bytes(data))


def _listing(directory: Path) -> dict[str, bytes]:
    """Every file but the claim files, which maintenance creates and never deletes."""

    return {
        path.name: path.read_bytes() for path in directory.iterdir()
        if path.is_file() and not path.name.endswith(".claim")
    }


def _backup(ledger: Path, history: Path) -> dict[str, Path]:
    run = _main(["backup", *_flags(ledger, history)])
    assert run.code == EXIT_SUCCESS, run.err
    paths = {}
    for line in run.out.splitlines():
        match = re.fullmatch(r"Backed up the (ledger|history) to (.+)", line)
        if match:
            paths[match[1]] = Path(match[2])
    assert set(paths) == {"ledger", "history"}
    return paths


def _eventually(operation, *, refused: int = EXIT_REFUSED) -> Run:
    # A killed holder's locks and handles can outlive it briefly on Windows.
    deadline = monotonic() + WAIT_SECONDS
    while True:
        run = operation()
        if run.code != refused or monotonic() > deadline:
            return run
        sleep(0.05)


def _instance(main_file: Path) -> str:
    with closing(sqlite3.connect(main_file.as_uri() + "?mode=ro", uri=True)) as connection:
        return connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'instance_id'"
        ).fetchone()[0]


# --- a ready pair ------------------------------------------------------------------


def test_a_ready_pair_checks_backs_up_and_restores_each_role(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)

    checked = _main(["check", *flags])
    assert (checked.code, checked.out, checked.err) == (
        EXIT_SUCCESS, "ledger: ok\nhistory: ok\n", "",
    )

    backed_up = _main(["backup", *flags])
    assert backed_up.code == EXIT_SUCCESS and backed_up.err == ""
    history_backup, ledger_backup = sorted(tmp_path.glob("*.db.backup-*"))
    assert backed_up.out.splitlines() == [
        f"Backed up the ledger to {ledger_backup}",
        f"Backed up the history to {history_backup}",
    ]

    restored = _main(["restore", "history", str(history_backup), *flags])
    assert (restored.code, restored.err) == (EXIT_SUCCESS, "")
    lines = restored.out.splitlines()
    assert lines[0] == f"Restored the history from {history_backup}."
    assert re.fullmatch(
        r"The replaced history was backed up to .*history\.db\.backup-.*Z\.", lines[1]
    )
    assert len(lines) == 2

    before = _instance(ledger)
    restored = _main(["restore", "ledger", str(ledger_backup), *flags])
    assert (restored.code, restored.err) == (EXIT_SUCCESS, "")
    lines = restored.out.splitlines()
    assert lines[0] == f"Restored the ledger from {ledger_backup}."
    assert re.fullmatch(
        r"The backup was cut at 20\d\d-\d\d-\d\dT[\d:.]+\+00:00\. History runs recorded "
        r"after that time are now shown as belonging to an earlier ledger\.",
        lines[1],
    )
    assert re.fullmatch(
        r"The replaced ledger was backed up to .*ledger\.db\.backup-.*Z\.", lines[2]
    )
    assert _instance(ledger) != before
    assert _main(["check", *flags]).out == "ledger: ok\nhistory: ok\n"


def test_backup_rotation_is_reported_and_a_failed_removal_only_warns(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)
    removed_counts = []
    for _ in range(5):
        run = _main(["backup", *flags])
        assert (run.code, run.err) == (EXIT_SUCCESS, "")
        removed = [line for line in run.out.splitlines() if line.startswith("Removed")]
        removed_counts.append(len(removed))
        for line in removed:
            assert re.fullmatch(
                r"Removed 2 older backup\(s\): .*ledger\.db\.backup-.*Z, "
                r".*history\.db\.backup-.*Z", line,
            )
    assert removed_counts == [0, 0, 0, 1, 1]
    assert len(list(tmp_path.glob("ledger.db.backup-*"))) == 3

    contract = DatabasePairContract(DatabasePairState.READY)
    result = DatabasePairBackup(
        contract, (), (), ((tmp_path / "old.backup", "PermissionError: denied"),),
    )
    stdout, stderr = io.StringIO(), io.StringIO()
    assert cli_module._render_backup(result, stdout, stderr) == EXIT_SUCCESS
    assert stdout.getvalue() == ""
    assert stderr.getvalue().startswith(
        f"Warning: could not remove the older backup {tmp_path / 'old.backup'}: "
        "PermissionError: denied."
    )


def test_a_pair_refused_while_every_role_reads_fine_is_reported_and_not_usable(
    tmp_path: Path,
) -> None:
    from namisync.db.maintenance import DatabaseCheck, DatabaseCheckState
    from namisync.workflows.database_maintenance import DatabasePairCheck

    contract = DatabasePairContract(
        DatabasePairState.REFUSED, "database-busy", None, "Retry in a moment.",
    )
    roles = tuple(DatabaseCheck(role, DatabaseCheckState.OK) for role in ("ledger", "history"))
    stdout, stderr = io.StringIO(), io.StringIO()

    code = cli_module._render_check(
        DatabasePairCheck(contract, roles), tmp_path / "l.db", tmp_path / "h.db", stdout, stderr,
    )

    assert code == EXIT_FAILED and stderr.getvalue() == ""
    assert stdout.getvalue() == (
        "ledger: ok\nhistory: ok\nPair: database-busy.\nRetry in a moment.\n"
    )


def test_a_failed_history_backup_reports_the_kept_ledger_backup_and_exits_four(
    tmp_path: Path,
) -> None:
    from namisync.workflows.database_maintenance import DatabaseBackup

    kept = tmp_path / "ledger.db.backup-x"
    contract = DatabasePairContract(
        DatabasePairState.REFUSED, "backup-failed", None,
        "NamiSync could not write a verified backup of the history database, so no "
        "backup was written.",
    )
    stdout, stderr = io.StringIO(), io.StringIO()

    code = cli_module._render_backup(
        DatabasePairBackup(contract, (DatabaseBackup("ledger", kept),)), stdout, stderr,
    )

    assert code == EXIT_FAILED
    assert stdout.getvalue() == f"Backed up the ledger to {kept}\n"
    assert stderr.getvalue().splitlines() == [
        "Database pair refused: backup-failed.",
        "NamiSync could not write a verified backup of the history database, so no "
        "backup was written.",
        "The backups listed above were kept.",
    ]


@pytest.mark.parametrize("guidance", (
    "Database is in use. Retry.",
    # Text that happens to say otherwise decides nothing.
    "Nothing was changed. The file is kept as somewhere.",
))
def test_a_kept_file_is_named_from_the_result_never_from_the_guidance(
    tmp_path: Path, guidance: str,
) -> None:
    kept = tmp_path / "ledger.db.backup-x"
    contract = DatabasePairContract(
        DatabasePairState.REFUSED, "database-in-use", None, guidance,
    )
    stdout, stderr = io.StringIO(), io.StringIO()

    code = cli_module._render_restore(
        DatabasePairRestore(contract, None, kept), stdout, stderr,
    )

    assert code == EXIT_REFUSED and stdout.getvalue() == ""
    assert stderr.getvalue().splitlines() == [
        "Database pair refused: database-in-use.",
        guidance,
        f"Kept: {kept}, the database as it was before this restore (with any -wal "
        "and -shm files beside it).",
    ]

    # Without a kept file, a refusal closes with one structural line.
    stderr = io.StringIO()
    cli_module._render_restore(DatabasePairRestore(contract), io.StringIO(), stderr)
    assert stderr.getvalue().splitlines()[-1] == "Nothing was changed."


@pytest.mark.parametrize("command", (["check"], ["backup"], ["restore", "ledger", "{backup}"]))
def test_an_invalid_database_path_is_an_input_error_that_touches_nothing(
    tmp_path: Path, command: list[str],
) -> None:
    ledger, history = _pair(tmp_path)
    backup = _backup(ledger, history)["ledger"]
    before = sorted((path.name, path.read_bytes()) for path in tmp_path.iterdir())
    arguments = [part.replace("{backup}", str(backup)) for part in command]

    for flags in (
        ["--database", str(tmp_path / "le?dger.db"), "--history-database", str(history)],
        ["--database", str(ledger), "--history-database", str(tmp_path / "hist|ory.db")],
    ):
        run = _main([*arguments, *flags])

        assert (run.code, run.out) == (EXIT_USAGE, "")
        assert run.err.startswith("Input error: a database path is not valid:")
        assert run.err.endswith("Check --database and --history-database. Nothing was changed.\n")
        assert "Error" not in run.err and "Traceback" not in run.err
        assert "may have changed" not in run.err
        assert sorted((path.name, path.read_bytes()) for path in tmp_path.iterdir()) == before


@pytest.mark.parametrize("command", (["check"], ["backup"], ["restore", "ledger", "{backup}"]))
def test_an_invalid_parent_in_both_paths_is_an_input_error_not_missing_folders(
    tmp_path: Path, command: list[str],
) -> None:
    backup = _backup(*_pair(tmp_path / "source"))["ledger"]
    invalid = tmp_path / "in?valid"
    arguments = [part.replace("{backup}", str(backup)) for part in command]

    run = _main([*arguments, *_flags(invalid / "ledger.db", invalid / "history.db")])

    assert (run.code, run.out) == (EXIT_USAGE, "")
    assert run.err.startswith("Input error: a database path is not valid:")
    assert "No NamiSync databases" not in run.err
    assert sorted(path.name for path in tmp_path.iterdir()) == ["source"]


def test_guidance_for_a_custom_pair_names_the_options_that_select_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    custom = _pair(tmp_path / "data")
    default = _pair(tmp_path / "local" / "NamiSync-Development")
    root = tmp_path / "root"
    root.mkdir()

    for ledger, history, flags in (
        (*custom, _flags(*custom)),
        # The default pair: no options were given, so no line is added.
        (*default, []),
    ):
        selected = [_selected(ledger, history)] if flags else []
        backup = _backup(ledger, history)["ledger"]
        _unlink(ledger)

        # check: a missing ledger points at restore.
        checked = _main(["check", *flags])
        assert checked.code == EXIT_FAILED
        assert "namisync restore ledger <backup file>" in checked.out
        assert ("selected with" in checked.out) == bool(flags)
        if flags:
            assert checked.out.splitlines()[-1] == selected[0]

        # A restore refusal: a ledger backup is not a History backup.
        refused = _main(["restore", "history", str(backup), *flags])
        assert refused.code == EXIT_REFUSED
        assert refused.err.splitlines()[-1 - len(selected):] == ["Nothing was changed.", *selected]

        # A mutating command's pair refusal, here a ledger copied into place.
        ledger.write_bytes(backup.read_bytes())
        inventory = _main(["inventory", str(root), *flags])
        assert inventory.code == EXIT_REFUSED
        assert "Database pair refused: ledger-is-backup." in inventory.err
        assert "namisync restore ledger <backup file>" in inventory.err
        assert ("selected with" in inventory.err) == bool(flags)
        if flags:
            assert inventory.err.splitlines()[-1] == selected[0]


# --- pairs as found: none of the commands migrates, completes or creates ---------------


def test_a_fresh_pair_says_so_and_nothing_is_created(tmp_path: Path) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    flags = _flags(ledger, history)

    checked = _main(["check", *flags])
    assert (checked.code, checked.err) == (EXIT_SUCCESS, "")
    assert checked.out.splitlines()[0] == (
        f"No NamiSync databases were found at {ledger} and {history}."
    )
    backed_up = _main(["backup", *flags])
    assert backed_up.code == EXIT_REFUSED and backed_up.out == ""
    assert "There is nothing to back up" in backed_up.err
    assert backed_up.err.endswith("Nothing was changed.\n")

    assert _listing(tmp_path) == {}
    assert not any(path.suffix != ".claim" for path in tmp_path.iterdir())


def test_a_restore_into_a_fresh_pair_publishes_only_that_database(tmp_path: Path) -> None:
    source_ledger, source_history = _pair(tmp_path / "source")
    backups = _backup(source_ledger, source_history)
    ledger, history = tmp_path / "data" / "ledger.db", tmp_path / "data" / "history.db"
    ledger.parent.mkdir()

    run = _main(["restore", "ledger", str(backups["ledger"]), *_flags(ledger, history)])

    assert (run.code, run.err) == (EXIT_SUCCESS, "")
    assert f"There was no ledger database to replace." in run.out
    assert "Note: the database pair is not ready yet (history-missing)." in run.out
    assert sorted(_listing(ledger.parent)) == ["ledger.db"]
    assert not history.exists()


def test_a_missing_database_folder_is_an_input_error_and_check_says_no_databases(
    tmp_path: Path,
) -> None:
    flags = _flags(tmp_path / "absent" / "ledger.db", tmp_path / "absent" / "history.db")

    checked = _main(["check", *flags])
    assert (checked.code, checked.err) == (EXIT_SUCCESS, "")
    assert checked.out.startswith("No NamiSync databases were found at")
    run = _main(["backup", *flags])
    assert run.code == EXIT_USAGE and run.out == ""
    assert "the folder of the ledger database does not exist" in run.err
    assert run.err.endswith("Nothing was changed.\n")
    assert not (tmp_path / "absent").exists()

    # Only one folder missing: check cannot look at the other, so it is an input error.
    one = _main(["check", *_flags(tmp_path / "absent" / "ledger.db", tmp_path / "history.db")])
    assert (one.code, one.out) == (EXIT_USAGE, "")
    assert "the folder of the ledger database does not exist" in one.err


def test_an_older_pair_is_reported_and_never_migrated(tmp_path: Path) -> None:
    ledger, history = copy_released_pair(tmp_path / "data")
    other_ledger, other_history = _pair(tmp_path / "other")
    backups = _backup(other_ledger, other_history)
    before = _listing(ledger.parent)
    flags = _flags(ledger, history)

    checked = _main(["check", *flags])
    assert (checked.code, checked.err) == (EXIT_FAILED, "")
    lines = checked.out.splitlines()
    assert lines[0] == "ledger: older" and lines[2] == "history: older"
    assert "Written by NamiSync 0.1.0." in lines[1]

    backed_up = _main(["backup", *flags])
    assert (backed_up.code, backed_up.out) == (EXIT_REFUSED, "")
    assert backed_up.err.splitlines()[0] == "Database pair refused: pair-older."
    assert "Start NamiSync, or run a sync or inventory command, once to update it" in backed_up.err
    # The pair's own admission refusal: its shared text speaks for itself.
    assert _closing(backed_up, ledger, history) == "No backup was written."

    # The readable ledger of a healthy 0.1.0 pair is not restored: update the pair first.
    restored = _main(["restore", "ledger", str(backups["ledger"]), *flags])
    assert (restored.code, restored.out) == (EXIT_REFUSED, "")
    assert restored.err.splitlines()[0] == "Database pair refused: pair-older."
    assert "Start NamiSync, or run a sync or inventory command, once to update the pair" in restored.err
    assert _closing(restored, ledger, history) == "Nothing was changed."
    assert restored.err.count("Nothing was changed.") == 1

    assert _listing(ledger.parent) == before
    assert not list(ledger.parent.glob("*.backup-*")) and not list(ledger.parent.glob("*.tmp"))


def test_a_v4_migration_backup_is_refused_as_a_restore_source(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path / "data")
    old_ledger, old_history = copy_released_pair(tmp_path / "released")
    v4 = next(
        path for path in upgrade_database_pair(old_ledger, old_history, create=True).backups
        if path.name.startswith("ledger")
    )
    before = _listing(ledger.parent)

    run = _main(["restore", "ledger", str(v4), *_flags(ledger, history)])

    assert (run.code, run.out) == (EXIT_REFUSED, "")
    assert run.err.splitlines()[0] == "Database pair refused: backup-older."
    assert "way back to the version that wrote it" in run.err
    assert _closing(run, ledger, history) == "Nothing was changed."
    assert run.err.count("Nothing was changed.") == 1
    assert _listing(ledger.parent) == before


@pytest.mark.parametrize("missing", ("ledger", "history"))
def test_an_incomplete_pair_is_reported_and_never_completed(
    tmp_path: Path, missing: str,
) -> None:
    ledger, history = _pair(tmp_path)
    _unlink(ledger if missing == "ledger" else history)
    before = _listing(tmp_path)
    flags = _flags(ledger, history)

    checked = _main(["check", *flags])
    assert (checked.code, checked.err) == (EXIT_FAILED, "")
    lines = checked.out.splitlines()
    assert f"{missing}: missing" in lines
    assert "ok" in " ".join(lines) and "start NamiSync, or run a sync" in checked.out

    backed_up = _main(["backup", *flags])
    assert (backed_up.code, backed_up.out) == (EXIT_REFUSED, "")
    assert backed_up.err.splitlines()[0] == f"Database pair refused: {missing}-missing."
    assert "run a sync or inventory command, once to create a new one" in backed_up.err
    assert _closing(backed_up, ledger, history) == "No backup was written."

    assert _listing(tmp_path) == before


def test_stray_sidecars_of_a_missing_database_are_listed_and_kept(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    _unlink(history)
    Path(f"{history}-wal").write_bytes(b"")
    before = _listing(tmp_path)

    checked = _main(["check", *_flags(ledger, history)])

    assert checked.code == EXIT_FAILED
    assert "history: missing\n  - history.db-wal is present without its database\n" in checked.out
    assert "Keep them for inspection." in checked.out
    assert _listing(tmp_path) == before


# --- damage, a backup in place, swapped paths -----------------------------------------


@pytest.mark.parametrize("role", ("ledger", "history"))
def test_a_damaged_role_is_named_by_check_and_restore_sets_it_aside(
    tmp_path: Path, role: str,
) -> None:
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)
    backup = _backup(ledger, history)[role]
    damaged = ledger if role == "ledger" else history
    _damage(damaged)
    damaged_bytes = damaged.read_bytes()
    other = history if role == "ledger" else ledger

    checked = _main(["check", *flags])
    assert (checked.code, checked.err) == (EXIT_FAILED, "")
    assert f"{role}: damaged\n" in checked.out
    assert f"{'history' if role == 'ledger' else 'ledger'}: ok\n" in checked.out
    assert f"namisync restore {role} <backup file> replaces it and keeps the damaged files" in checked.out

    # Backup, like every admission, refuses and names the way forward.
    backed_up = _main(["backup", *flags])
    assert backed_up.code == EXIT_REFUSED
    assert "Database pair refused: database-damaged." in backed_up.err
    assert f"namisync restore {role} <backup file>" in backed_up.err
    assert not re.search(r"delete|archive|reset", backed_up.err, re.IGNORECASE)

    other_before = other.read_bytes()
    restored = _main(["restore", role, str(backup), *flags])

    assert (restored.code, restored.err) == (EXIT_SUCCESS, "")
    replaced = next(tmp_path.glob(f"{damaged.name}.replaced-*Z"))
    assert replaced.read_bytes() == damaged_bytes
    assert f"The replaced {role}'s files were kept at {replaced} " in restored.out
    assert other.read_bytes() == other_before
    assert _main(["check", *flags]).out == "ledger: ok\nhistory: ok\n"


def _discarding(text: str) -> list[str]:
    """The sentences of the output that tell the user to discard something."""

    return [
        sentence for line in text.splitlines() for sentence in line.split(". ")
        if re.search("archive|delete", sentence)
    ]


def test_an_empty_history_beside_a_healthy_ledger_is_the_only_file_to_discard(
    tmp_path: Path,
) -> None:
    # User report (2026-11-26): every command told the user to delete both.
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)
    backup = _backup(ledger, history)["ledger"]
    _unlink(history)
    history.touch()
    ledger, history = ledger.resolve(), history.resolve()
    keep = f"Keep the ledger database {ledger} as it is"

    checked = _main(["check", *flags])
    assert (checked.code, checked.err) == (EXIT_FAILED, "")
    assert "ledger: ok\nhistory: unsupported\n" in checked.out
    assert "Pair: history-contract.\n" in checked.out and keep in checked.out
    assert f"archive or delete the history database file {history} and its" in checked.out
    assert "Keep its files" not in checked.out
    assert all(str(ledger) not in sentence for sentence in _discarding(checked.out))

    root = tmp_path / "root"
    root.mkdir()
    refused = _main(["inventory", str(root), *flags])
    assert refused.code == EXIT_REFUSED
    assert "Database pair refused: history-contract." in refused.err and keep in refused.err
    assert all(str(ledger) not in sentence for sentence in _discarding(refused.err))

    restored = _main(["restore", "ledger", str(backup), *flags])
    assert (restored.code, restored.err) == (EXIT_SUCCESS, "")
    assert "Note: the database pair is not ready yet (history-contract)." in restored.out
    assert f"archive or delete the history database file {history} and its" in restored.out
    assert keep in restored.out
    assert all(str(ledger) not in sentence for sentence in _discarding(restored.out))


def test_foreign_key_violations_are_refused_by_backup_and_restored_aside(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)
    backup = _backup(ledger, history)["ledger"]
    with closing(sqlite3.connect(ledger, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "INSERT INTO mappings(source_location_id, target_location_id, created_at) "
            "VALUES (1000, 2000, '2026-01-01T00:00:00.000000Z')"
        )

    checked = _main(["check", *flags])
    assert (checked.code, checked.err) == (EXIT_FAILED, "")
    assert checked.out.startswith("ledger: foreign-key-violations\n  - foreign key violation:")
    assert "NamiSync still opens it, but namisync backup refuses it" in checked.out
    assert "namisync restore ledger <backup file> replaces it" in checked.out
    assert "to keep a copy" not in checked.out

    backups_before = sorted(tmp_path.glob("*.backup-*"))
    backed_up = _main(["backup", *flags])
    assert (backed_up.code, backed_up.out) == (EXIT_FAILED, "")
    assert backed_up.err.splitlines()[0] == "Database pair refused: backup-failed."
    assert "foreign key violations" in backed_up.err
    assert sorted(tmp_path.glob("*.backup-*")) == backups_before

    restored = _main(["restore", "ledger", str(backup), *flags])
    assert (restored.code, restored.err) == (EXIT_SUCCESS, "")
    assert "The replaced ledger's files were kept at" in restored.out
    assert _main(["check", *flags]).out == "ledger: ok\nhistory: ok\n"


def test_a_ledger_copied_into_place_from_a_backup_is_restored_by_the_named_command(
    tmp_path: Path,
) -> None:
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)
    backup = _backup(ledger, history)["ledger"]
    _unlink(ledger)
    ledger.write_bytes(backup.read_bytes())

    checked = _main(["check", *flags])
    assert (checked.code, checked.err) == (EXIT_FAILED, "")
    assert checked.out.startswith("ledger: is-backup\n")
    assert "namisync restore ledger <backup file>" in checked.out

    # The refusal at admission names the same command, and it is literally this one.
    root = tmp_path / "root"
    root.mkdir()
    refused = _main(["inventory", str(root), *flags])
    assert refused.code == EXIT_REFUSED
    assert "Database pair refused: ledger-is-backup." in refused.err
    assert "namisync restore ledger <backup file>" in refused.err

    restored = _main(["restore", "ledger", str(backup), *flags])
    assert (restored.code, restored.err) == (EXIT_SUCCESS, "")
    assert "The replaced ledger's files were kept at" in restored.out
    assert next(tmp_path.glob("ledger.db.replaced-*Z")).read_bytes() == backup.read_bytes()
    assert _main(["check", *flags]).out == "ledger: ok\nhistory: ok\n"


def test_swapped_paths_are_named_and_every_command_leaves_both_databases_alone(
    tmp_path: Path,
) -> None:
    ledger, history = _pair(tmp_path)
    backups = _backup(ledger, history)
    swapped = _flags(history, ledger)
    before = _listing(tmp_path)

    checked = _main(["check", *swapped])
    assert (checked.code, checked.err) == (EXIT_FAILED, "")
    assert "ledger: wrong-role\n" in checked.out and "history: wrong-role\n" in checked.out
    assert "look swapped" in checked.out

    backed_up = _main(["backup", *swapped])
    assert (backed_up.code, backed_up.out) == (EXIT_REFUSED, "")
    assert "Database pair refused: ledger-wrong-role." in backed_up.err

    # The ledger's pair rule sees History's path holding a ledger; History's own
    # target check sees the other role.
    assert _main(["restore", "ledger", str(backups["ledger"]), *swapped]).err.startswith(
        "Database pair refused: history-wrong-role."
    )
    run = _main(["restore", "history", str(backups["history"]), *swapped])
    assert run.code == EXIT_REFUSED
    assert run.err.startswith("Database pair refused: target-wrong-role.")
    assert _listing(tmp_path) == before


def test_a_backup_of_the_wrong_role_is_refused_with_nothing_changed(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    backups = _backup(ledger, history)
    before = _listing(tmp_path)

    run = _main(["restore", "history", str(backups["ledger"]), *_flags(ledger, history)])

    assert (run.code, run.out) == (EXIT_REFUSED, "")
    assert run.err.startswith("Database pair refused: backup-wrong-role.")
    assert _closing(run, ledger, history) == "Nothing was changed."
    assert _listing(tmp_path) == before


def test_a_ledger_is_restored_beside_an_older_history_and_the_pair_still_needs_updating(
    tmp_path: Path,
) -> None:
    source_ledger, source_history = _pair(tmp_path / "source")
    backup = _backup(source_ledger, source_history)["ledger"]
    ledger = _pair(tmp_path / "data")[0]
    history = copy_released_pair(tmp_path / "old")[1]
    history_before = _listing(history.parent)

    run = _main(["restore", "ledger", str(backup), *_flags(ledger, history)])

    assert (run.code, run.err) == (EXIT_SUCCESS, "")
    assert f"Restored the ledger from {backup}." in run.out
    assert "Note: the database pair is not ready yet (history-older)." in run.out
    assert "Start NamiSync, or run a sync or inventory command, once" in run.out
    assert _listing(history.parent) == history_before


# --- usage ---------------------------------------------------------------------------


def test_a_backup_that_is_not_a_file_is_an_input_error_before_any_claim(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    before = sorted((path.name, path.read_bytes()) for path in tmp_path.iterdir())

    for target in (tmp_path / "absent.backup", tmp_path):
        run = _main(["restore", "ledger", str(target), *_flags(ledger, history)])
        assert (run.code, run.out) == (EXIT_USAGE, "")
        assert run.err.splitlines()[0] == f"Input error: {target} is not an existing file."
        assert run.err.endswith("Nothing was changed.\n")
    assert sorted((path.name, path.read_bytes()) for path in tmp_path.iterdir()) == before


def test_one_path_for_both_databases_and_unknown_roles_are_usage_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    same = tmp_path / "one.db"
    for command in (["check"], ["backup"]):
        run = _main([*command, *_flags(same, same)])
        assert run.code == EXIT_USAGE
        assert "must use distinct paths" in run.err
    assert not list(tmp_path.iterdir())
    for arguments in (["restore"], ["restore", "ledger"], ["restore", "settings", "x"]):
        assert main(arguments, stdout=io.StringIO(), stderr=io.StringIO()) == EXIT_USAGE
        assert "usage: namisync restore" in capsys.readouterr().err


@pytest.mark.parametrize(("ledger_name", "history_name", "role"), [
    ("collision.db", "collision.db.claim", "history"),
    ("Collision.DB.Claim", "collision.db", "ledger"),
])
def test_a_database_at_the_other_ones_claim_path_is_a_configuration_error(
    tmp_path: Path, ledger_name: str, history_name: str, role: str,
) -> None:
    # External review (third A4): with both mains absent, check created a
    # zero-byte History main when it took the ledger's claim.
    root = tmp_path / "root"
    root.mkdir()
    flags = _flags(tmp_path / ledger_name, tmp_path / history_name)
    for arguments in (["check", *flags], ["backup", *flags], ["inventory", str(root), *flags]):
        run = _main(arguments)
        assert (run.code, run.out) == (EXIT_USAGE, ""), run
        assert run.err.startswith(f"Configuration error: the {role} database path ")
        assert "database's .claim file" in run.err
    assert [path.name for path in tmp_path.iterdir()] == ["root"]


def test_the_commands_share_the_cli_argument_bound(tmp_path: Path) -> None:
    run = _main(["restore", "ledger", "x" * 70_000])
    assert (run.code, run.out, run.err) == (EXIT_USAGE, "", "Invalid command request.\n")


def test_building_the_service_opens_no_database_and_creates_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, expected in (("fresh", set()), ("ready", None)):
        directory = tmp_path / name
        if name == "ready":
            ledger, history = _pair(directory)
            expected = {path.name: path.stat().st_mtime_ns for path in directory.iterdir()}
        else:
            directory.mkdir()
            ledger, history = directory / "ledger.db", directory / "history.db"
        connects = []
        original = sqlite3.connect
        monkeypatch.setattr(
            sqlite3, "connect", lambda *a, **k: connects.append(a) or original(*a, **k),
        )
        with NamiSyncService(ledger, history):
            pass
        monkeypatch.undo()
        assert connects == []
        if name == "fresh":
            assert list(directory.iterdir()) == []
        else:
            assert {path.name: path.stat().st_mtime_ns for path in directory.iterdir()} == expected


# --- failures after the point of no return -----------------------------------------------


def test_a_restore_that_cannot_be_confirmed_says_so_and_names_what_it_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)
    backup = _backup(ledger, history)["ledger"]
    monkeypatch.setattr(
        maintenance, "_confirm", lambda *a, **k: (_ for _ in ()).throw(OSError("read back failed")),
    )

    run = _main(["restore", "ledger", str(backup), *flags])

    assert (run.code, run.out) == (EXIT_FAILED, "")
    assert run.err.splitlines()[0] == "Database pair refused: restore-unconfirmed."
    assert "could not be confirmed" in run.err
    assert "Run namisync check" in run.err
    pre_restore = [
        path for path in tmp_path.glob("ledger.db.backup-*")
        if path != backup and str(path) in run.err
    ]
    assert len(pre_restore) == 1
    assert "Nothing was changed" not in run.err


def test_a_restore_that_failed_before_the_copy_exits_four_naming_its_pre_restore_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)
    backup = _backup(ledger, history)["ledger"]
    before = _instance(ledger)
    monkeypatch.setattr(
        maintenance, "_prepare_image", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )

    run = _main(["restore", "ledger", str(backup), *flags])

    assert (run.code, run.out) == (EXIT_FAILED, "")
    assert run.err.splitlines()[0] == "Database pair refused: restore-failed."
    assert "so nothing was restored" in run.err
    (pre_restore,) = [path for path in tmp_path.glob("ledger.db.backup-*") if path != backup]
    assert _closing(run, ledger, history) == (
        f"Kept: {pre_restore}, the database as it was before this restore (with any "
        "-wal and -shm files beside it)."
    )
    assert run.err.count(str(pre_restore)) == 1
    assert "Nothing was changed" not in run.err
    assert _instance(ledger) == before


# --- the closing conditions of the maintenance row, with real processes ------------------


@pytest.mark.parametrize("kind", ("recorder", "observer"))
def test_maintenance_commands_are_refused_while_a_run_holds_a_claim(
    tmp_path: Path, kind: str,
) -> None:
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)
    backup = _backup(ledger, history)["ledger"]
    child = Child(HOLD, kind, str(ledger), str(history))
    try:
        assert child.read() == "held"
        before = _listing(tmp_path)
        runs = {
            "check": _process(["check", *flags]),
            "backup": _process(["backup", *flags]),
            "restore": _process(["restore", "ledger", str(backup), *flags]),
        }
        for command, run in runs.items():
            assert run.code == EXIT_REFUSED, (command, run)
            assert run.out == ""
            assert run.err.splitlines()[0] == "Database pair refused: database-in-use."
            assert "in use by NamiSync work" in run.err
            assert _closing(run, ledger, history) == "Nothing was changed."
        assert _listing(tmp_path) == before
    finally:
        child.kill()
    assert _eventually(lambda: _main(["check", *flags])).out == "ledger: ok\nhistory: ok\n"


def test_new_runs_are_refused_while_maintenance_holds_the_claims(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)
    backup = _backup(ledger, history)["ledger"]
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("a", encoding="utf-8")
    # A restore stopped after its pre-restore backup, holding both exclusive claims.
    child = Child(RESTORE, str(ledger), str(history), "ledger", str(backup), "backed-up", "0")
    try:
        assert child.read() == "ready" and child.read() == "stopped"
        before = {
            name: path.read_bytes() for name in (
                "ledger.db", "ledger.db-wal", "history.db", "history.db-wal",
            ) if (path := tmp_path / name).exists()
        }
        files = sorted(path.name for path in tmp_path.iterdir())

        refused = _process(["inventory", str(root), *flags])
        assert refused.code == EXIT_REFUSED and refused.out == ""
        assert refused.err.startswith("Inventory refused: Database maintenance is in progress")
        assert "New work is refused, not queued" in refused.err
        # Maintenance does not run beside maintenance either.
        assert _process(["check", *flags]).err.startswith(
            "Database pair refused: database-in-use."
        )

        assert {
            name: (tmp_path / name).read_bytes() for name in before
        } == before
        assert sorted(path.name for path in tmp_path.iterdir()) == files
    finally:
        child.kill()


def test_a_plan_reviewed_before_a_restore_command_is_refused_at_start(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.bin").write_bytes(b"payload")
    ledger, history = _pair(tmp_path / "data")
    flags = _flags(ledger, history)
    backup = _backup(ledger, history)["ledger"]
    restored: list[Run] = []

    class RestoredWhileConfirming(io.StringIO):
        def readline(self, *args) -> str:
            # The real command, in its own process, while the plan waits at the prompt.
            restored.append(_process(["restore", "ledger", str(backup), *flags]))
            return super().readline(*args)

    stdout, stderr = io.StringIO(), io.StringIO()
    result = main(
        ["sync", str(source), str(target), *flags],
        stdin=RestoredWhileConfirming("execute\n"), stdout=stdout, stderr=stderr,
    )

    assert (restored[0].code, restored[0].err) == (EXIT_SUCCESS, "")
    assert "The replaced ledger was backed up to" in restored[0].out
    assert result == EXIT_REFUSED, (stdout.getvalue(), stderr.getvalue())
    assert list(target.iterdir()) == []
    assert (
        "Refused: The ledger was replaced (restored or reset) after this plan was "
        "made, so it cannot run. Rerun the same sync command to review a new plan.\n"
    ) in stderr.getvalue()
    assert "Plan again" not in stderr.getvalue()


@pytest.mark.parametrize("verify_after_copy", [False, True])
def test_a_ledger_replaced_after_the_start_check_names_the_command_line_step(
    verify_after_copy: bool,
) -> None:
    try:
        require_planned_ledger(
            SimpleNamespace(ledger_instance_id="a" * 32), lambda: "b" * 32,
        )
    except LedgerInstanceChanged as error:
        message = str(error)
    # The workflow's own text, which other adapters receive, is unchanged.
    assert message.endswith(" Plan again to review it against the current ledger.")
    # As a writer refuses it after the start check: the run's error, not a
    # commitment refusal. With --verify-after-copy the execute phase carries it too.
    failure = f"LedgerInstanceChanged: {message}"
    phases = (
        (PhaseResult("execute", PhaseStatus.FAILED, 0, 1, 0, 7, error=failure),)
        if verify_after_copy else ()
    )
    result = operation_result_view(OperationResult(
        SessionState.FAILED, phases=phases,
        error=FailureDetail("LedgerInstanceChanged", message),
    ))
    output, errors = io.StringIO(), io.StringIO()

    cli_module._render_execution(
        SimpleNamespace(result=result),
        SimpleNamespace(commitment_error=None, refusals=()),
        (), output, errors,
    )

    rerun = (
        "LedgerInstanceChanged: The ledger was replaced (restored or reset) after "
        "this plan was made, so it cannot run. Rerun the same sync command to "
        "review a new plan."
    )
    assert errors.getvalue().splitlines()[0] == rerun
    assert ("; error=" + rerun in output.getvalue()) is verify_after_copy
    assert "Plan again" not in output.getvalue() + errors.getvalue()


def test_restore_runs_in_place_beside_a_desktop_that_then_reads_the_new_ledger(
    tmp_path: Path,
) -> None:
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)
    backup = _backup(ledger, history)["ledger"]
    desktop = Child(DESKTOP, str(ledger), str(history))
    try:
        held = desktop.read()
        assert held == f"held {_instance(ledger)}"

        restored = _process(["restore", "ledger", str(backup), *flags])
        assert (restored.code, restored.err) == (EXIT_SUCCESS, "")
        assert "The replaced ledger was backed up to" in restored.out
        assert desktop.process.stdin is not None
        desktop.process.stdin.write("read\n")
        desktop.process.stdin.flush()
        assert desktop.read() == f"instance {_instance(ledger)}"
        assert _instance(ledger) != held.removeprefix("held ")
    finally:
        desktop.kill()


def test_a_damaged_target_needs_every_other_process_closed(tmp_path: Path) -> None:
    ledger, history = _pair(tmp_path)
    flags = _flags(ledger, history)
    backup = _backup(ledger, history)["ledger"]
    desktop = Child(DESKTOP, str(ledger), str(history))
    try:
        assert desktop.read() == f"held {_instance(ledger)}"
        # Damage the main file under the open window: the pages are all in it.
        data = bytearray(ledger.read_bytes())
        data[100:612] = b"\xa5" * 512
        ledger.write_bytes(bytes(data))
        before = _listing(tmp_path)

        assert _process(["check", *flags]).out.startswith("ledger: damaged\n")
        refused = _process(["restore", "ledger", str(backup), *flags])

        assert (refused.code, refused.out) == (EXIT_REFUSED, "")
        assert refused.err.splitlines()[0] == "Database pair refused: database-in-use."
        assert _closing(refused, ledger, history) == "Nothing was changed."
        assert _listing(tmp_path) == before
    finally:
        desktop.kill()
    restored = _eventually(lambda: _process(["restore", "ledger", str(backup), *flags]))
    assert restored.code == EXIT_SUCCESS, restored.err
    assert "The replaced ledger's files were kept at" in restored.out
