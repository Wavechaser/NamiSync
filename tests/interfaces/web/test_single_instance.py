"""Per-logon desktop single-instance identity tests."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest

from namisync.interfaces import launcher
from namisync.interfaces.web.host import (
    DesktopInstanceIdentity,
    WindowsInstanceNative,
    acquire_desktop_instance,
    production_instance_identity,
)


class FakeNative:
    def __init__(
        self,
        *,
        already_exists: bool,
        window: object | None = object(),
        foregrounded: bool = True,
    ) -> None:
        self.already_exists = already_exists
        self.window = window
        self.foregrounded = foregrounded
        self.created: list[str] = []
        self.closed: list[object] = []
        self.found: list[str] = []
        self.restored: list[object] = []

    def create_mutex(self, name: str) -> tuple[object, bool]:
        self.created.append(name)
        return "mutex-handle", self.already_exists

    def close_handle(self, handle: object) -> None:
        self.closed.append(handle)

    def find_window(self, title: str) -> object | None:
        self.found.append(title)
        return self.window

    def restore_window(self, window: object) -> None:
        self.restored.append(window)

    def foreground_window(self, window: object) -> bool:
        assert window is self.window
        return self.foregrounded


def _test_identity() -> DesktopInstanceIdentity:
    token = uuid4().hex
    return DesktopInstanceIdentity(
        mutex_name=rf"Local\NamiSync.Test.{token}",
        window_title=f"NamiSync Test {token}",
    )


def test_production_identity_is_fixed_and_version_independent() -> None:
    first = production_instance_identity()
    second = production_instance_identity()

    assert first == second == DesktopInstanceIdentity(
        mutex_name=r"Local\NamiSync.Desktop",
        window_title="NamiSync",
    )
    assert "0.1.0" not in first.mutex_name


def test_sh_g_10_production_namespace_has_no_external_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for arguments in (
        ["--mutex", r"Local\NamiSync.Test.Override"],
        ["--window-title", "NamiSync Test Override"],
        ["--instance-identity", "override"],
        ["--data-dir", r"C:\isolated", "--mutex=override"],
    ):
        with pytest.raises(launcher.GuiArgumentError):
            launcher._parse_gui_arguments(arguments)

    for name in (
        "NAMISYNC_MUTEX",
        "NAMISYNC_WINDOW_TITLE",
        "NAMISYNC_INSTANCE_IDENTITY",
    ):
        monkeypatch.setenv(name, "override")
    assert production_instance_identity() == DesktopInstanceIdentity(
        mutex_name=r"Local\NamiSync.Desktop",
        window_title="NamiSync",
    )

    project_root = Path(__file__).parents[3]
    launcher_source = Path(launcher.__file__).read_text(encoding="utf-8")
    host_source = (project_root / "namisync/interfaces/web/host.py").read_text(
        encoding="utf-8"
    )
    assert "os.environ" not in launcher_source + host_source
    assert "os.getenv" not in launcher_source + host_source

    launcher_tree = ast.parse(launcher_source)
    host_calls = [
        node
        for node in ast.walk(launcher_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "run_desktop"
    ]
    assert len(host_calls) == 1
    assert isinstance(host_calls[0].args[1], ast.Call)
    assert isinstance(host_calls[0].args[1].func, ast.Name)
    assert host_calls[0].args[1].func.id == "production_instance_identity"

    browser_surface = (
        project_root / "namisync/interfaces/web/bridge.py"
    ).read_text(encoding="utf-8")
    assets = project_root / "namisync/interfaces/web/assets"
    browser_surface += "".join(
        path.read_text(encoding="utf-8")
        for path in sorted(assets.iterdir())
        if path.is_file()
    )
    for forbidden in (
        r"Local\NamiSync.Desktop",
        "DesktopInstanceIdentity",
        "instance_identity",
        "mutex_name",
        "window_title",
    ):
        assert forbidden not in browser_surface


def test_primary_holds_one_mutex_until_idempotent_release() -> None:
    native = FakeNative(already_exists=False)
    identity = _test_identity()

    admission = acquire_desktop_instance(identity, native=native)

    assert admission.is_primary
    assert native.created == [identity.mutex_name]
    assert native.closed == []
    assert admission.lease is not None
    admission.lease.close()
    admission.lease.close()
    assert native.closed == ["mutex-handle"]


def test_losing_instance_activates_using_the_same_injected_identity() -> None:
    native = FakeNative(already_exists=True)
    identity = _test_identity()

    admission = acquire_desktop_instance(identity, native=native)

    assert not admission.is_primary
    assert admission.activated
    assert admission.activation_error is None
    assert native.created == [identity.mutex_name]
    assert native.closed == ["mutex-handle"]
    assert native.found == [identity.window_title]
    assert native.restored == [native.window]


def test_activation_failure_is_typed_and_still_a_losing_admission() -> None:
    native = FakeNative(already_exists=True, window=None)

    admission = acquire_desktop_instance(_test_identity(), native=native)

    assert not admission.is_primary
    assert not admission.activated
    assert admission.activation_error == (
        "The existing NamiSync window could not be found."
    )


def test_distinct_injected_identities_hold_independent_real_mutexes() -> None:
    native = WindowsInstanceNative()
    first = acquire_desktop_instance(_test_identity(), native=native)
    second = acquire_desktop_instance(_test_identity(), native=native)
    try:
        assert first.is_primary
        assert second.is_primary
    finally:
        if first.lease is not None:
            first.lease.close()
        if second.lease is not None:
            second.lease.close()
