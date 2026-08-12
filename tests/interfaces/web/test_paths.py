"""GUI local-artifact path tests."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import namisync.interfaces.web.paths as paths_module
from namisync.interfaces.web.paths import AppPathError, AppPaths


PROJECT_ROOT = Path(__file__).parents[3]


def test_injected_root_moves_every_gui_artifact_together(tmp_path: Path) -> None:
    root = tmp_path / "isolated"
    paths = AppPaths.from_root(root)

    assert paths.root == root.resolve()
    assert {
        paths.ledger,
        paths.history,
        paths.settings,
        paths.ui_state,
        paths.logs,
        paths.log_file,
        paths.webview2,
    } == {
        paths.root / "ledger.db",
        paths.root / "history.db",
        paths.root / "settings.json",
        paths.root / "ui-state.json",
        paths.root / "logs",
        paths.root / "logs" / "namisync.log",
        paths.root / "webview2",
    }
    assert all(
        path == paths.root or paths.root in path.parents
        for path in (
            paths.ledger,
            paths.history,
            paths.settings,
            paths.ui_state,
            paths.logs,
            paths.log_file,
            paths.webview2,
        )
    )


def test_production_root_uses_local_app_data() -> None:
    paths = AppPaths.production({"LOCALAPPDATA": r"C:\Users\Alice\AppData\Local"})

    assert paths.root == Path(r"C:\Users\Alice\AppData\Local\NamiSync")


@pytest.mark.parametrize(
    "value",
    [
        "relative",
        r"..\relative",
        r"\\server\share\NamiSync",
    ],
)
def test_nonlocal_or_relative_root_is_refused_without_creation(value: str) -> None:
    with pytest.raises(AppPathError, match="absolute local path"):
        AppPaths.from_root(value)


def test_missing_local_app_data_is_actionable() -> None:
    with pytest.raises(AppPathError, match="LOCALAPPDATA"):
        AppPaths.production({})


def test_mapped_remote_drive_is_refused_before_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(paths_module, "_drive_type", lambda path: 4)
    root = tmp_path / "remote"

    with pytest.raises(AppPathError, match="absolute local path"):
        AppPaths.from_root(root)

    assert not root.exists()


def test_resolved_root_is_rechecked_for_locality(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = iter((3, 4))
    monkeypatch.setattr(paths_module, "_drive_type", lambda path: next(observed))
    root = tmp_path / "redirected"

    with pytest.raises(AppPathError, match="absolute local path"):
        AppPaths.from_root(root)

    assert not root.exists()


def test_directory_creation_is_idempotent(tmp_path: Path) -> None:
    paths = AppPaths.from_root(tmp_path / "isolated")

    paths.ensure_directories()
    paths.ensure_directories()

    assert paths.root.is_dir()
    assert paths.logs.is_dir()
    assert paths.webview2.is_dir()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction containment")
def test_existing_child_junction_cannot_redirect_an_artifact_outside_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "isolated"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    environment = os.environ.copy()
    environment["NAMISYNC_TEST_LINK"] = str(root / "logs")
    environment["NAMISYNC_TEST_TARGET"] = str(outside)
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "New-Item -ItemType Junction -Path $env:NAMISYNC_TEST_LINK "
            "-Target $env:NAMISYNC_TEST_TARGET -ErrorAction Stop | Out-Null",
        ],
        capture_output=True,
        text=True,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    paths = AppPaths.from_root(root)

    with pytest.raises(AppPathError, match="outside"):
        paths.ensure_directories()

    assert tuple(outside.iterdir()) == ()
    assert not paths.webview2.exists()


def test_importing_paths_loads_no_webview_module() -> None:
    script = """
import json
import sys
from namisync.interfaces.web.paths import AppPaths
AppPaths.from_root(r"C:\\NamiSync-Test")
print(json.dumps(sorted(
    name for name in sys.modules
    if name == "webview" or name.startswith("webview.")
)))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == []
