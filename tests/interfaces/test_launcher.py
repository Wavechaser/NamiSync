"""Console and GUI launcher tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import namisync.interfaces.launcher as launcher


def test_console_launcher_without_command_names_gui(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = launcher.main([])

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert captured.err.startswith("usage: nami-sync")
    assert "nami-sync-gui" in captured.err


def test_console_launcher_delegates_explicit_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from namisync.interfaces import cli

    seen: list[list[str]] = []
    monkeypatch.setattr(cli, "main", lambda arguments: seen.append(arguments) or 7)

    assert launcher.main(["history", "--limit", "1"]) == 7
    assert seen == [["history", "--limit", "1"]]


def test_explicit_cli_subprocess_loads_no_webview_module(tmp_path: Path) -> None:
    history = tmp_path / "history.db"
    script = """
import json
import sys
from namisync.interfaces.launcher import main
code = main(["history", "--history-database", sys.argv[1]])
print("MODULES=" + json.dumps(sorted(
    name for name in sys.modules
    if name == "webview" or name.startswith("webview.")
)))
raise SystemExit(code)
"""

    completed = subprocess.run(
        [sys.executable, "-c", script, str(history)],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    modules_line = next(
        line for line in completed.stdout.splitlines() if line.startswith("MODULES=")
    )
    assert json.loads(modules_line.removeprefix("MODULES=")) == []


@pytest.mark.parametrize(
    "arguments",
    [
        ["--help"],
        ["-h"],
        ["positional"],
        ["--unknown"],
        ["--data-dir"],
        ["--data-dir="],
        ["--data-dir", "--other"],
        ["--data-dir=C:\\one", "--data-dir=C:\\two"],
        ["--data-dir", "C:\\one", "extra"],
    ],
)
def test_invalid_gui_grammar_reports_natively_without_console_output(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports: list[str] = []
    before = set(sys.modules)
    monkeypatch.setattr(launcher, "_native_startup_error", reports.append)

    result = launcher.gui_main(arguments)

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == captured.err == ""
    assert len(reports) == 1
    assert "webview" not in set(sys.modules) - before
    assert not any(name.startswith("webview.") for name in set(sys.modules) - before)


def test_relative_gui_data_root_is_refused_before_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports: list[str] = []
    relative = Path("relative-app-data")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(launcher, "_native_startup_error", reports.append)

    result = launcher.gui_main(["--data-dir", str(relative)])

    assert result == 2
    assert reports == ["application data root must be an absolute local path"]
    assert not (tmp_path / relative).exists()


def test_gui_parser_accepts_both_absolute_data_dir_spellings(
    tmp_path: Path,
) -> None:
    expected = tmp_path / "isolated"

    assert launcher._parse_gui_arguments(
        ["--data-dir", str(expected)]
    ) == launcher.GuiArguments(expected)
    assert launcher._parse_gui_arguments(
        [f"--data-dir={expected}"]
    ) == launcher.GuiArguments(expected)


def test_gui_launcher_constructs_the_fixed_production_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from namisync.interfaces.web import host

    seen: list[tuple[object, ...]] = []
    identity = host.production_instance_identity()
    monkeypatch.setattr(host, "production_instance_identity", lambda: identity)
    monkeypatch.setattr(
        host,
        "run_desktop",
        lambda paths, actual_identity, *, startup_error: seen.append(
            (paths, actual_identity, startup_error)
        )
        or 0,
    )

    result = launcher.gui_main(["--data-dir", str(tmp_path / "isolated")])

    assert result == 0
    assert len(seen) == 1
    assert seen[0][0].root == (tmp_path / "isolated").resolve()
    assert seen[0][1] is identity
    assert seen[0][2] is launcher._report_startup_error


def test_native_startup_reporter_uses_stable_caption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []
    user32 = SimpleNamespace(
        MessageBoxW=lambda *arguments: calls.append(arguments) or 1
    )
    monkeypatch.setattr(
        launcher.ctypes,
        "windll",
        SimpleNamespace(user32=user32),
    )

    launcher._native_startup_error("synthetic failure")

    assert calls == [
        (
            None,
            "synthetic failure",
            "NamiSync - Startup Error",
            0x00000010,
        )
    ]
