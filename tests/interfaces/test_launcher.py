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
    assert captured.err.startswith("usage: namisync")
    assert "namisync-gui" in captured.err


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
        ["--index-path", r"C:\headed-probe.html"],
        [r"--index-path=C:\headed-probe.html"],
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


@pytest.mark.parametrize("equals", (False, True))
def test_gui_ingress_admits_exact_utf8_request_and_refuses_first_excess(
    equals: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = "C:\\" + "界" * 21_840 + "xx"
    arguments = ["--data-dir=" + value] if equals else ["--data-dir", value]
    assert sum(len(arg.encode("utf-8")) for arg in arguments) + len(arguments) - 1 == 65_536
    assert launcher._parse_gui_arguments(arguments).data_dir == Path(value)

    def forbidden(*args, **kwargs):
        pytest.fail("first-excess request reached interface construction")

    monkeypatch.setattr(launcher, "Path", forbidden)
    monkeypatch.setattr(launcher, "GuiArguments", forbidden)
    arguments[-1] += "x"
    with pytest.raises(launcher.GuiArgumentError, match="^Invalid command request\\.$"):
        launcher._parse_gui_arguments(arguments)


@pytest.mark.parametrize("value", (object(), type("Text", (str,), {})("subclass"), "\ud800"))
@pytest.mark.parametrize("equals", (False, True))
def test_gui_ingress_refuses_invalid_arguments_before_effects(
    value: object, equals: bool, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reports = []

    def forbidden(*args, **kwargs):
        pytest.fail("invalid request reached interface construction")

    if equals:
        arguments = ["--data-dir=" + value] if type(value) is str else [value]
    else:
        arguments = ["--data-dir", value]
    monkeypatch.setattr(launcher, "Path", forbidden)
    monkeypatch.setattr(launcher, "GuiArguments", forbidden)
    monkeypatch.setattr(launcher, "_native_startup_error", reports.append)
    assert launcher.gui_main(arguments) == 2  # type: ignore[arg-type]
    assert reports == ["Invalid command request."]
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows Unicode argv limit")
@pytest.mark.parametrize("equals", (False, True))
def test_real_windows_gui_argv_refuses_66k_before_import_or_construction(equals: bool) -> None:
    script = """
import json
import sys
from namisync.interfaces import launcher
def forbidden(*args, **kwargs):
    raise AssertionError("oversized argv reached interface construction")
launcher.Path = launcher.GuiArguments = forbidden
reports = []
launcher._native_startup_error = reports.append
code = launcher.gui_main()
loaded = sorted(name for name in sys.modules if name in {
    "namisync.interfaces.cli", "namisync.interfaces.service", "webview"
} or name.startswith("namisync.interfaces.web."))
print(json.dumps({"code": code, "reports": reports, "loaded": loaded,
    "request_bytes": sum(len(arg.encode("utf-8")) for arg in sys.argv[1:]) + len(sys.argv[1:]) - 1}))
"""
    value = "C:\\" + "\\".join(["界" * 200] * 110)
    arguments = ["--data-dir=" + value] if equals else ["--data-dir", value]
    command = [sys.executable, "-c", script, *arguments]
    assert len(subprocess.list2cmdline(command).encode("utf-16-le")) // 2 + 1 < 32_767
    completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "code": 2, "reports": ["Invalid command request."], "loaded": [],
        "request_bytes": 66_123,
    }


@pytest.mark.parametrize("equals", (False, True))
def test_gui_launcher_constructs_the_fixed_production_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    equals: bool,
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

    value = str(tmp_path / "isolated")
    arguments = ["--data-dir=" + value] if equals else ["--data-dir", value]
    result = launcher.gui_main(arguments)

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
