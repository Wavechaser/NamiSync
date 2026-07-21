from __future__ import annotations

import io
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from namisync.core.events import Envelope, ItemOutcome, SCHEMA_VERSION
from namisync.core.evidence import Outcome
from namisync.core.session import (
    OperationResult,
    SessionId,
    SessionRecord,
    SessionState,
)
from namisync.db.history import HistoryContext, HistoryStore
from namisync.interfaces.cli import (
    EXIT_PARTIAL,
    EXIT_REFUSED,
    EXIT_SUCCESS,
    EXIT_USAGE,
    _exit_for_record,
    _render_execution,
    main,
)

from _db_fixtures import FakeClock, NOW


def _arguments(source: Path, target: Path, ledger: Path, history: Path) -> list[str]:
    return [
        "sync",
        str(source),
        str(target),
        "--database",
        str(ledger),
        "--history-database",
        str(history),
    ]


def test_no_subcommand_prints_usage_and_returns_nonzero() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main([], stdout=stdout, stderr=stderr)

    assert result == EXIT_USAGE
    assert "usage:" in stderr.getvalue()


def test_completed_execution_with_exclusions_is_reported_as_partial() -> None:
    blocked = ItemOutcome(
        "blocked",
        "noop",
        "junction",
        Outcome.BLOCKED,
        reason="unsupported",
    )
    deferred = ItemOutcome(
        "withheld",
        "trash",
        "old.bin",
        Outcome.DEFERRED,
        reason="incomplete-scan",
    )
    record = SimpleNamespace(
        result=OperationResult(
            SessionState.COMPLETED,
            operations=(blocked, deferred),
        )
    )
    details = SimpleNamespace(commitment_error=None, refusals=())
    stdout = io.StringIO()
    stderr = io.StringIO()

    _render_execution(record, details, stdout, stderr)

    assert _exit_for_record(record) == EXIT_PARTIAL
    assert "completed with exceptions: blocked=1; deferred=1" in stdout.getvalue()


def test_recent_history_lists_safe_subset_exception_counts(tmp_path: Path) -> None:
    history = tmp_path / "history.db"
    record = SessionRecord(
        SessionId("session"),
        "sync-execution",
        SessionState.PENDING,
        (),
        b"payload",
        True,
        1,
        NOW,
    )
    blocked = ItemOutcome(
        "blocked",
        "noop",
        "junction",
        Outcome.BLOCKED,
        reason="unsupported",
    )
    with HistoryStore(history, clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext(
                "partial-run",
                "host",
                activity_kind="sync",
                source_context="source",
                target_context="target",
            ),
        )
        observer.on_event(
            Envelope(record.session_id, 1, NOW, SCHEMA_VERSION, blocked)
        )
        observer.finalize(
            OperationResult(SessionState.COMPLETED, operations=(blocked,))
        )
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        ["history", "--history-database", str(history)],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS
    assert "exceptions=blocked:1,deferred:0" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_declined_plan_mutates_neither_files_nor_databases(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.txt").write_text("review only", encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS, (stdout.getvalue(), stderr.getvalue())
    assert not (target / "payload.txt").exists()
    assert not ledger.exists()
    assert not history.exists()
    assert "Plan left uncommitted" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_cli_runs_real_reviewed_sync_and_browses_history(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    payload = b"NamiSync end-to-end\n"
    (source / "payload.bin").write_bytes(payload)
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS, (stdout.getvalue(), stderr.getvalue())
    assert (target / "payload.bin").read_bytes() == payload
    assert ledger.exists()
    assert history.exists()
    assert "filesystem=completed; ledger=ok; audit=ok" in stdout.getvalue()
    assert stderr.getvalue() == ""

    history_output = io.StringIO()
    history_errors = io.StringIO()
    history_result = main(
        ["history", "--history-database", str(history)],
        stdout=history_output,
        stderr=history_errors,
    )

    assert history_result == EXIT_SUCCESS
    assert "completed" in history_output.getvalue()
    assert str(source) in history_output.getvalue()
    assert history_errors.getvalue() == ""


def test_case_only_name_advisory_does_not_suppress_changed_content(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "KEEP.txt").write_bytes(b"changed source content")
    (target / "keep.txt").write_bytes(b"old")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS, (stdout.getvalue(), stderr.getvalue())
    assert (target / "keep.txt").read_bytes() == b"changed source content"
    assert [entry.name for entry in target.iterdir() if entry.is_file()] == ["keep.txt"]
    assert "update=1" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_successful_rerun_removes_prior_run_temp_from_touched_parent(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.bin").write_bytes(b"completed retry")
    orphan = target / (
        "abandoned.bin.synctmp-" + "1" * 32 + "-" + "2" * 32
    )
    orphan.write_bytes(b"partial copy")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS, (stdout.getvalue(), stderr.getvalue())
    assert (target / "payload.bin").read_bytes() == b"completed retry"
    assert not orphan.exists()


class _DriftingConfirmation(io.StringIO):
    def __init__(self, target: Path) -> None:
        super().__init__("execute\n")
        self._target = target

    def readline(self, *args, **kwargs) -> str:
        (self._target / "payload.txt").write_text("external writer", encoding="utf-8")
        return super().readline(*args, **kwargs)


def test_execution_fresh_preflight_refuses_drift_without_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.txt").write_text("reviewed source", encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=_DriftingConfirmation(target),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_REFUSED
    assert (target / "payload.txt").read_text(encoding="utf-8") == "external writer"
    assert not ledger.exists()
    assert history.exists()
    assert "destination_appeared" in stderr.getvalue()


def test_database_inside_managed_root_is_rejected_before_planning(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.txt").write_text("unchanged", encoding="utf-8")
    ledger = source / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_USAGE
    assert not ledger.exists()
    assert not history.exists()
    assert not (target / "payload.txt").exists()
    assert "outside both roots" in stderr.getvalue()


def test_immediate_rerun_is_noop_and_each_explicit_run_is_retained(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.txt").write_text("stable", encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"

    first = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    second_output = io.StringIO()
    second_errors = io.StringIO()
    second = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=second_output,
        stderr=second_errors,
    )

    assert first == EXIT_SUCCESS
    assert second == EXIT_SUCCESS, (second_output.getvalue(), second_errors.getvalue())
    assert "noop=1" in second_output.getvalue()
    assert "disposition=ran" in second_output.getvalue()

    history_output = io.StringIO()
    history_result = main(
        ["history", "--history-database", str(history)],
        stdout=history_output,
        stderr=io.StringIO(),
    )

    assert history_result == EXIT_SUCCESS
    assert history_output.getvalue().count(" -> ") == 2


def test_second_sync_uses_recorded_correspondence_for_source_rename(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "before.txt").write_text("moved without copying", encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"

    first = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    (source / "before.txt").rename(source / "after.txt")
    output = io.StringIO()
    errors = io.StringIO()
    second = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=output,
        stderr=errors,
    )

    assert first == EXIT_SUCCESS
    assert second == EXIT_SUCCESS, (output.getvalue(), errors.getvalue())
    assert not (target / "before.txt").exists()
    assert (target / "after.txt").read_text(encoding="utf-8") == "moved without copying"
    assert "move=1" in output.getvalue()
    assert "bytes=0/0" in output.getvalue()


def test_attribute_only_change_is_planned_and_propagated(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    source_file = source / "payload.txt"
    target_file = target / "payload.txt"
    source_file.write_text("same content and mtime", encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"

    first = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    original_mtime = source_file.stat().st_mtime_ns
    source_file.chmod(stat.S_IREAD)
    try:
        assert source_file.stat().st_mtime_ns == original_mtime
        output = io.StringIO()
        errors = io.StringIO()
        second = main(
            _arguments(source, target, ledger, history),
            stdin=io.StringIO("execute\n"),
            stdout=output,
            stderr=errors,
        )

        assert first == EXIT_SUCCESS
        assert second == EXIT_SUCCESS, (output.getvalue(), errors.getvalue())
        assert "update=1" in output.getvalue()
        assert target_file.read_text(encoding="utf-8") == "same content and mtime"
        assert target_file.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY
    finally:
        source_file.chmod(stat.S_IWRITE)
        if target_file.exists():
            os.chmod(target_file, stat.S_IWRITE)


def test_real_module_and_console_entry_points_use_process_argv(tmp_path: Path) -> None:
    module = subprocess.run(
        [sys.executable, "-m", "namisync"],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    console = Path(sys.executable).with_name("nami-sync.exe")
    assert console.exists(), "editable/install build must provide nami-sync.exe"
    executable = subprocess.run(
        [str(console)],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert module.returncode == EXIT_USAGE
    assert executable.returncode == EXIT_USAGE
    assert "usage:" in module.stderr
    assert "usage:" in executable.stderr


def test_real_process_entry_points_run_sync_and_history(tmp_path: Path) -> None:
    console = Path(sys.executable).with_name("nami-sync.exe")
    entry_points = (
        [sys.executable, "-m", "namisync"],
        [str(console)],
    )
    for index, prefix in enumerate(entry_points):
        case = tmp_path / str(index)
        source = case / "source"
        target = case / "target"
        source.mkdir(parents=True)
        target.mkdir()
        (source / "payload.txt").write_text("real argv", encoding="utf-8")
        ledger = case / "ledger.db"
        history = case / "history.db"

        sync = subprocess.run(
            [*prefix, *_arguments(source, target, ledger, history)],
            cwd=Path(__file__).parents[1],
            input="execute\n",
            text=True,
            capture_output=True,
            check=False,
        )
        browsed = subprocess.run(
            [*prefix, "history", "--history-database", str(history)],
            cwd=Path(__file__).parents[1],
            text=True,
            capture_output=True,
            check=False,
        )

        assert sync.returncode == EXIT_SUCCESS, (sync.stdout, sync.stderr)
        assert (target / "payload.txt").read_text(encoding="utf-8") == "real argv"
        assert browsed.returncode == EXIT_SUCCESS, (browsed.stdout, browsed.stderr)
        assert "completed" in browsed.stdout
