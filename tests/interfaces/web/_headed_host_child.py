"""Out-of-process boundaries for installed-wheel desktop acceptance tests."""

from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from unittest.mock import patch


_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_SYNCHRONIZE = 0x00100000
_UI_AUTOMATION_CLIENT = (
    "UIAutomationClient, Version=3.0.0.0, Culture=neutral, "
    "PublicKeyToken=31bf3856ad364e35"
)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--job-wrapper":
        return _run_job_wrapper(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--uia-probe":
        return _run_uia_probe(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--production-identity-probe":
        return _run_production_identity_probe(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--gui-argument-probe":
        return _run_gui_argument_probe(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--activation-failure-probe":
        return _run_activation_failure_probe(sys.argv[2:])
    return _run_installed_host(sys.argv[1:])


def _run_installed_host(argv: list[str]) -> int:
    from namisync.interfaces.launcher import _report_startup_error
    from namisync.interfaces.web.host import DesktopInstanceIdentity, run_desktop
    from namisync.interfaces.web.paths import AppPaths

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    arguments = parser.parse_args(argv)
    return run_desktop(
        AppPaths.from_root(arguments.data_dir),
        DesktopInstanceIdentity(arguments.mutex, arguments.title),
        startup_error=_report_startup_error,
    )


def _run_job_wrapper(argv: list[str]) -> int:
    """Wait until the parent assigns this process to its kill-on-close job."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", required=True)
    parser.add_argument("--gate-timeout-ms", required=True, type=int)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args(argv)
    command = arguments.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        return 64
    if not _wait_for_named_gate(
        arguments.gate,
        timeout_ms=max(1, arguments.gate_timeout_ms),
    ):
        return 65
    return subprocess.run(command, check=False).returncode


def _wait_for_named_gate(name: str, *, timeout_ms: int) -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenEventW.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenEventW(_SYNCHRONIZE, False, name)
    if not handle:
        return False
    try:
        result = int(kernel32.WaitForSingleObject(handle, timeout_ms))
        if result == _WAIT_OBJECT_0:
            return True
        if result == _WAIT_TIMEOUT:
            return False
        raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(handle)


def _run_uia_probe(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handle", required=True, type=int)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--timeout", required=True, type=float)
    arguments = parser.parse_args(argv)
    deadline = time.monotonic() + max(0.0, arguments.timeout)
    last: tuple[str, ...] = ()
    try:
        while time.monotonic() < deadline:
            last = _automation_names(arguments.handle)
            if arguments.expected in last:
                print(json.dumps({"names": last}))
                return 0
            time.sleep(0.1)
    except Exception as error:
        print(json.dumps({"names": last, "error": repr(error)}))
        return 2
    print(json.dumps({"names": last}))
    return 1


def _automation_names(handle: int) -> tuple[str, ...]:
    import clr

    clr.AddReference(_UI_AUTOMATION_CLIENT)
    from System import IntPtr
    from System.Windows.Automation import AutomationElement, Condition, TreeScope

    root = AutomationElement.FromHandle(IntPtr(handle))
    elements = root.FindAll(TreeScope.Descendants, Condition.TrueCondition)
    names: list[str] = []
    for index in range(elements.Count):
        try:
            name = str(elements[index].Current.Name)
        except Exception:
            continue
        if name:
            names.append(name)
    return tuple(names)


class _BoundaryMappedNative:
    """Map only the OS boundary while preserving the logical identity."""

    def __init__(self, mapped_mutex: str) -> None:
        from namisync.interfaces.web.host import WindowsInstanceNative

        self._mutex_native = WindowsInstanceNative()
        self._mapped_mutex = mapped_mutex
        self.mutex_names: list[str] = []
        self.found: list[str] = []
        self.restored = 0
        self.foregrounded = 0

    def create_mutex(self, name: str) -> tuple[object, bool]:
        self.mutex_names.append(name)
        return self._mutex_native.create_mutex(self._mapped_mutex)

    def close_handle(self, handle: object) -> None:
        self._mutex_native.close_handle(handle)

    def find_window(self, title: str) -> object:
        self.found.append(title)
        return object()

    def restore_window(self, window: object) -> None:
        self.restored += 1

    def foreground_window(self, window: object) -> bool:
        self.foregrounded += 1
        return True


class _ForcedForegroundFailureNative:
    """Delegate real UUID window discovery/restore, then refuse foreground."""

    def __init__(self) -> None:
        from namisync.interfaces.web.host import WindowsInstanceNative

        self._native = WindowsInstanceNative()
        self.mutex_names: list[str] = []
        self.find_titles: list[str] = []
        self.restore_calls = 0
        self.foreground_calls = 0

    def create_mutex(self, name: str) -> tuple[object, bool]:
        self.mutex_names.append(name)
        return self._native.create_mutex(name)

    def close_handle(self, handle: object) -> None:
        self._native.close_handle(handle)

    def find_window(self, title: str) -> object | None:
        self.find_titles.append(title)
        return self._native.find_window(title)

    def restore_window(self, window: object) -> None:
        self.restore_calls += 1
        self._native.restore_window(window)

    def foreground_window(self, window: object) -> bool:
        del window
        self.foreground_calls += 1
        return False


def _run_production_identity_probe(argv: list[str]) -> int:
    """Compose the installed launcher, mapping its identity at the OS boundary."""

    from namisync.interfaces import launcher
    from namisync.interfaces.web import host

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--test-mutex", required=True)
    parser.add_argument("--test-title", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ready", required=True, type=Path)
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--hold-timeout", required=True, type=float)
    arguments = parser.parse_args(argv)

    def probe_run_desktop(paths, identity, *, startup_error) -> int:
        del startup_error
        native = _BoundaryMappedNative(arguments.test_mutex)
        admission = host.acquire_desktop_instance(
            identity,
            native=native,
        )
        result = {
            "launcher_mutex": identity.mutex_name,
            "launcher_title": identity.window_title,
            "data_root": str(paths.root),
            "primary": admission.is_primary,
            "activated": admission.activated,
            "activation_error": admission.activation_error,
            "mutex_names": native.mutex_names,
            "find_titles": native.found,
            "restore_calls": native.restored,
            "foreground_boundary_calls": native.foregrounded,
        }
        arguments.output.write_text(json.dumps(result), encoding="utf-8")
        if admission.is_primary:
            arguments.ready.touch()
            deadline = time.monotonic() + arguments.hold_timeout
            while not arguments.release.exists():
                if time.monotonic() >= deadline:
                    return 66
                time.sleep(0.025)
        if admission.lease is not None:
            admission.lease.close()
        return 0

    with patch.object(host, "run_desktop", probe_run_desktop):
        return launcher.gui_main(["--data-dir", str(arguments.data_dir)])


def _run_gui_argument_probe(argv: list[str]) -> int:
    """Exercise installed GUI parsing without touching the product namespace."""

    from namisync.interfaces import launcher
    from namisync.interfaces.web import host

    parser = argparse.ArgumentParser()
    parser.add_argument("--value", required=True)
    parser.add_argument("--test-mutex", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)

    def guarded_run_desktop(paths, identity, *, startup_error) -> int:
        del startup_error
        native = _BoundaryMappedNative(arguments.test_mutex)
        admission = host.acquire_desktop_instance(identity, native=native)
        result = {
            "unexpected_host_entry": True,
            "launcher_mutex": identity.mutex_name,
            "launcher_title": identity.window_title,
            "data_root": str(paths.root),
            "mutex_names": native.mutex_names,
            "find_titles": native.found,
        }
        arguments.output.write_text(json.dumps(result), encoding="utf-8")
        if admission.lease is not None:
            admission.lease.close()
        return 67

    with patch.object(host, "run_desktop", guarded_run_desktop):
        return launcher.gui_main(["--data-dir", arguments.value])


def _run_activation_failure_probe(argv: list[str]) -> int:
    """Make only SetForegroundWindow fail after real test-window discovery."""

    from namisync.interfaces.launcher import _report_startup_error
    from namisync.interfaces.web.host import DesktopInstanceIdentity, run_desktop
    from namisync.interfaces.web.paths import AppPaths

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    native = _ForcedForegroundFailureNative()
    result = run_desktop(
        AppPaths.from_root(arguments.data_dir),
        DesktopInstanceIdentity(arguments.mutex, arguments.title),
        startup_error=_report_startup_error,
        instance_native=native,
    )
    arguments.output.write_text(
        json.dumps(
            {
                "exit_code": result,
                "mutex_names": native.mutex_names,
                "find_titles": native.find_titles,
                "restore_calls": native.restore_calls,
                "foreground_calls": native.foreground_calls,
            }
        ),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
