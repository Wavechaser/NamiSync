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
_GW_OWNER = 4
_DIALOG_WINDOW_CLASS = "#32770"
_EDIT_CONTROL_TYPE = "ControlType.Edit"
_BUTTON_CONTROL_TYPE = "ControlType.Button"
_MAX_REDACTED_UIA_CANDIDATES = 16
_MAX_REDACTED_UIA_IDENTITY_CHARS = 32
_UI_AUTOMATION_CLIENT = (
    "UIAutomationClient, Version=3.0.0.0, Culture=neutral, "
    "PublicKeyToken=31bf3856ad364e35"
)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--job-wrapper":
        return _run_job_wrapper(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--uia-probe":
        return _run_uia_probe(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--uia-select-folder":
        return _run_uia_select_folder(sys.argv[2:])
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


def _run_uia_select_folder(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handle", required=True, type=int)
    parser.add_argument("--owner-handle", required=True, type=int)
    parser.add_argument("--process-id", required=True, type=int)
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--timeout", required=True, type=float)
    arguments = parser.parse_args(argv)
    deadline = time.monotonic() + max(0.0, arguments.timeout)
    last: dict[str, object] = {}
    try:
        last = _select_folder_with_automation(
            arguments.handle,
            str(arguments.path),
            owner_handle=arguments.owner_handle,
            process_id=arguments.process_id,
            deadline=deadline,
        )
        if last.get("selected") is True:
            print(json.dumps(last))
            return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    **last,
                    "selected": False,
                    "error_type": type(error).__name__,
                }
            )
        )
        return 2
    print(json.dumps({**last, "selected": False}))
    return 1


def _select_folder_with_automation(
    handle: int,
    path: str,
    *,
    owner_handle: int,
    process_id: int,
    deadline: float,
) -> dict[str, object]:
    import clr

    clr.AddReference(_UI_AUTOMATION_CLIENT)
    from System import IntPtr
    from System.Windows.Automation import (
        AutomationElement,
        Condition,
        InvokePattern,
        TreeScope,
        ValuePattern,
    )

    def exact_controls() -> tuple[
        object | None,
        object | None,
        dict[str, object],
    ]:
        _require_exact_dialog_identity(handle, owner_handle, process_id)
        root = AutomationElement.FromHandle(IntPtr(handle))
        elements = root.FindAll(TreeScope.Descendants, Condition.TrueCondition)
        return _classify_folder_dialog_controls(elements)

    edit, button, observed = exact_controls()
    if edit is None or button is None:
        return {"selected": False, "controls": observed}
    value_pattern = edit.GetCurrentPattern(ValuePattern.Pattern)
    _require_exact_dialog_identity(handle, owner_handle, process_id)
    value_pattern.SetValue(path)
    invokes = 0
    while invokes < 2:
        _require_exact_dialog_identity(handle, owner_handle, process_id)
        button.GetCurrentPattern(InvokePattern.Pattern).Invoke()
        invokes += 1
        close_observation_until = min(deadline, time.monotonic() + 0.75)
        while time.monotonic() < close_observation_until:
            if not _native_window_exists(handle):
                return {"selected": True, "invokes": invokes}
            time.sleep(0.025)
        if invokes == 1:
            _unused_edit, button, observed = exact_controls()
            if button is None:
                return {
                    "selected": False,
                    "invokes": invokes,
                    "controls": observed,
                }
    while time.monotonic() < deadline:
        if not _native_window_exists(handle):
            return {"selected": True, "invokes": invokes}
        time.sleep(0.025)
    return {"selected": False, "invokes": invokes}


def _classify_folder_dialog_controls(
    elements: object,
) -> tuple[object | None, object | None, dict[str, object]]:
    """Classify exact controls and retain one bounded, redacted diagnostic."""

    edit = None
    button = None
    ranked_candidates: dict[
        str,
        dict[tuple[str | None, str | None, bool | None], int],
    ] = {
        "exact_id_1152": {},
        "exact_id_1": {},
        "edit": {},
        "default_button": {},
        "other_button": {},
    }
    category_counts = dict.fromkeys(ranked_candidates, 0)
    element_count = int(elements.Count)
    candidate_count = 0
    unreadable_count = 0
    for index in range(element_count):
        element = elements[index]
        try:
            current = element.Current
        except Exception:
            unreadable_count += 1
            continue
        try:
            control_type: str | None = str(current.ControlType.ProgrammaticName)
        except Exception:
            control_type = None
        try:
            automation_id: str | None = str(current.AutomationId)
        except Exception:
            automation_id = None
        try:
            is_default: bool | None = bool(current.IsDefault)
        except Exception:
            is_default = None
        if (
            control_type in {_EDIT_CONTROL_TYPE, _BUTTON_CONTROL_TYPE}
            or automation_id in {"1152", "1"}
        ):
            candidate_count += 1
            identity = (
                control_type,
                automation_id,
                is_default,
            )
            if automation_id == "1152":
                category = "exact_id_1152"
            elif automation_id == "1":
                category = "exact_id_1"
            elif control_type == _EDIT_CONTROL_TYPE:
                category = "edit"
            elif control_type == _BUTTON_CONTROL_TYPE and is_default is True:
                category = "default_button"
            else:
                category = "other_button"
            category_counts[category] += 1
            destination = ranked_candidates[category]
            destination[identity] = destination.get(identity, 0) + 1
        if control_type == _EDIT_CONTROL_TYPE and automation_id == "1152":
            if edit is not None:
                raise RuntimeError("multiple exact folder path edits")
            edit = element
        if (
            control_type == _BUTTON_CONTROL_TYPE
            and automation_id == "1"
        ):
            if button is not None:
                raise RuntimeError("multiple exact folder confirmation buttons")
            button = element
    candidates = [
        {
            "control_type": _bounded_uia_identity(identity[0]),
            "automation_id": _bounded_uia_identity(identity[1]),
            "is_default": identity[2],
            "occurrences": occurrences,
        }
        for category in ranked_candidates.values()
        for identity, occurrences in category.items()
    ][:_MAX_REDACTED_UIA_CANDIDATES]
    unique_candidate_count = sum(
        len(category) for category in ranked_candidates.values()
    )
    represented_candidate_count = sum(
        int(candidate["occurrences"]) for candidate in candidates
    )
    return edit, button, {
        "element_count": element_count,
        "candidate_count": candidate_count,
        "omitted_candidate_count": max(
            0,
            candidate_count - represented_candidate_count,
        ),
        "unique_candidate_count": unique_candidate_count,
        "omitted_unique_candidate_count": max(
            0,
            unique_candidate_count - len(candidates),
        ),
        "unreadable_count": unreadable_count,
        "category_counts": category_counts,
        "candidates": candidates,
    }


def _bounded_uia_identity(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:_MAX_REDACTED_UIA_IDENTITY_CHARS]


def _native_window_exists(handle: int) -> bool:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL
    return bool(user32.IsWindow(handle))


def _require_exact_dialog_identity(
    handle: int,
    owner_handle: int,
    process_id: int,
) -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    )
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetClassNameW.argtypes = (
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    )
    user32.GetClassNameW.restype = ctypes.c_int
    observed_process_id = wintypes.DWORD()
    class_buffer = ctypes.create_unicode_buffer(256)
    if (
        not user32.IsWindow(handle)
        or not user32.IsWindowVisible(handle)
        or int(user32.GetWindow(handle, _GW_OWNER) or 0) != owner_handle
        or not user32.GetWindowThreadProcessId(
            handle,
            ctypes.byref(observed_process_id),
        )
        or int(observed_process_id.value) != process_id
        or not user32.GetClassNameW(handle, class_buffer, len(class_buffer))
        or class_buffer.value != _DIALOG_WINDOW_CLASS
    ):
        raise RuntimeError("folder dialog identity changed")


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
