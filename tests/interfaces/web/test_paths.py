"""GUI local-artifact path tests."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import namisync.interfaces.web.paths as paths_module
from namisync.interfaces.web.paths import (
    AppPathError,
    AppPaths,
    resolve_local_index_path,
)


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
        "/posix-spelling",
    ],
)
def test_sh_g_2_nonlocal_or_relative_root_is_refused_without_creation(
    value: str,
) -> None:
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


def test_construction_index_override_requires_an_absolute_local_file(
    tmp_path: Path,
) -> None:
    index = tmp_path / "headed-test.html"
    index.write_text("<!doctype html>", encoding="utf-8")

    assert resolve_local_index_path(index) == index.resolve()

    for value in ("relative.html", r"\\server\share\test.html", "/test.html"):
        with pytest.raises(AppPathError, match="absolute local path"):
            resolve_local_index_path(value)

    with pytest.raises(AppPathError, match="local file"):
        resolve_local_index_path(tmp_path / "missing.html")
    with pytest.raises(AppPathError, match="local file"):
        resolve_local_index_path(tmp_path)


def test_construction_index_override_rechecks_physical_locality(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = tmp_path / "headed-test.html"
    index.write_text("<!doctype html>", encoding="utf-8")
    monkeypatch.setattr(paths_module, "_drive_type", lambda path: 4)

    with pytest.raises(AppPathError, match="absolute local path"):
        resolve_local_index_path(index)

    observed = iter((3, 4))
    monkeypatch.setattr(paths_module, "_drive_type", lambda path: next(observed))

    with pytest.raises(AppPathError, match="absolute local path"):
        resolve_local_index_path(index)


def test_directory_creation_is_idempotent(tmp_path: Path) -> None:
    paths = AppPaths.from_root(tmp_path / "isolated")

    paths.ensure_directories()
    paths.ensure_directories()

    assert paths.root.is_dir()
    assert paths.logs.is_dir()
    assert paths.webview2.is_dir()


def test_path_lease_binds_directories_and_databases_and_retries_close(
    tmp_path: Path,
) -> None:
    class FakeNative:
        def __init__(self) -> None:
            self.opened: list[tuple[Path, bool]] = []
            self.closed: list[object] = []
            self.fail_once: set[object] = set()

        def open(self, path: Path, *, directory: bool) -> object:
            self.opened.append((path, directory))
            return f"handle:{path}"

        def close(self, handle: object) -> None:
            if handle in self.fail_once:
                self.fail_once.remove(handle)
                raise OSError("injected close failure")
            self.closed.append(handle)

    paths = AppPaths.from_root(tmp_path / "isolated")
    native = FakeNative()
    lease = paths.acquire_lease(native=native)
    paths.ledger.touch()
    paths.history.touch()

    lease.bind_databases()
    lease.bind_databases()

    assert native.opened == [
        (paths.root, True),
        (paths.logs, True),
        (paths.webview2, True),
        (paths.ledger, False),
        (paths.history, False),
    ]
    failed_handle = f"handle:{paths.logs}"
    native.fail_once.add(failed_handle)
    with pytest.raises(OSError, match="injected close failure"):
        lease.close()
    assert failed_handle not in native.closed

    lease.close()
    assert native.closed.count(failed_handle) == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows delete-sharing semantics")
def test_real_path_lease_blocks_replacement_until_release(tmp_path: Path) -> None:
    paths = AppPaths.from_root(tmp_path / "isolated")
    paths.ensure_directories()
    paths.ledger.touch()
    paths.history.touch()
    lease = paths.acquire_lease()
    lease.bind_databases()
    try:
        with pytest.raises(OSError):
            paths.logs.rename(paths.root / "moved-logs")
        with pytest.raises(OSError):
            paths.ledger.replace(paths.root / "moved-ledger.db")
    finally:
        lease.close()

    paths.logs.rename(paths.root / "moved-logs")
    paths.ledger.replace(paths.root / "moved-ledger.db")


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
