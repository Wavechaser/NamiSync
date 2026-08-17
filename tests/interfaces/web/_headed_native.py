"""Bounded Win32 probes used only by real headed child-process tests."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence
from uuid import uuid4

from _headed_evidence import EvidenceReader


_WM_CLOSE = 0x0010
_BM_CLICK = 0x00F5
_GW_OWNER = 4
_DIALOG_WINDOW_CLASS = "#32770"
_DEFAULT_SCENARIO_SECONDS = 45.0
_CLEANUP_SECONDS = 3.0
_LOCAL_DRIVE_TYPES = frozenset({2, 3, 5, 6})
_ERROR_MORE_DATA = 234
_STILL_ACTIVE = 259
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_HOST_CHILD = Path(__file__).with_name("_headed_host_child.py")


class _JobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = (
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    )


class _IoCounters(ctypes.Structure):
    _fields_ = tuple(
        (name, ctypes.c_ulonglong)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    )


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = (
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    )


@dataclass(frozen=True, slots=True)
class ScenarioDeadline:
    expires_at: float

    def remaining(self) -> float:
        remaining = self.expires_at - time.monotonic()
        if remaining <= 0:
            raise AssertionError("headed scenario exceeded its whole-scenario deadline")
        return remaining


@dataclass(slots=True)
class HeadedProcess:
    """A wrapper process and every descendant held in one kill-on-close job."""

    process: subprocess.Popen[str]
    command: tuple[str, ...]
    job_handle: object
    gate_handle: object
    _handles_closed: bool = field(default=False, init=False)

    @property
    def pid(self) -> int:
        return self.process.pid

    @property
    def args(self) -> tuple[str, ...]:
        return self.command

    def poll(self) -> int | None:
        kernel32 = _kernel32()
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(
            int(self.process._handle),
            ctypes.byref(exit_code),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if exit_code.value == _STILL_ACTIVE:
            return None
        return int(exit_code.value)

    def process_ids(self) -> frozenset[int]:
        return _job_process_ids(self.job_handle)

    def close_job(self) -> None:
        if self._handles_closed:
            return
        self._handles_closed = True
        kernel32 = _kernel32()
        if self.job_handle:
            kernel32.CloseHandle(self.job_handle)
            self.job_handle = None
        if self.gate_handle:
            kernel32.CloseHandle(self.gate_handle)
            self.gate_handle = None


def scenario_deadline(
    seconds: float = _DEFAULT_SCENARIO_SECONDS,
) -> ScenarioDeadline:
    return ScenarioDeadline(time.monotonic() + seconds)


def clean_child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONUTF8"] = "1"
    return environment


def start_headed_process(
    command: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path,
    environment: dict[str, str],
    deadline: ScenarioDeadline,
) -> HeadedProcess:
    """Start a command behind a pre-launch gate inside a hard Job Object."""

    deadline.remaining()
    actual_command = tuple(os.fspath(part) for part in command)
    gate_name = rf"Local\NamiSync.Headed.Gate.{uuid4().hex}"
    kernel32 = _kernel32()
    gate = kernel32.CreateEventW(None, True, False, gate_name)
    if not gate:
        raise ctypes.WinError(ctypes.get_last_error())
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        kernel32.CloseHandle(gate)
        raise ctypes.WinError(ctypes.get_last_error())
    information = _JobObjectExtendedLimitInformation()
    information.BasicLimitInformation.LimitFlags = (
        _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    if not kernel32.SetInformationJobObject(
        job,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(information),
        ctypes.sizeof(information),
    ):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        kernel32.CloseHandle(gate)
        raise ctypes.WinError(error)

    wrapper_command = (
        os.fspath(Path(sys._base_executable)),
        os.fspath(_HOST_CHILD),
        "--job-wrapper",
        "--gate",
        gate_name,
        "--gate-timeout-ms",
        str(max(1, int(deadline.remaining() * 1000))),
        "--",
        *actual_command,
    )
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            wrapper_command,
            cwd=cwd,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if process.poll() is not None:
            raise AssertionError("headed job wrapper exited before job assignment")
        if not kernel32.AssignProcessToJobObject(job, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.SetEvent(gate):
            raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        kernel32.CloseHandle(job)
        kernel32.CloseHandle(gate)
        if process is not None:
            _bounded_reap(process, kill=True, timeout=_cleanup_budget(deadline))
        raise
    return HeadedProcess(process, actual_command, job, gate)


def require_absolute_local_test_root(
    path: Path,
    *,
    drive_type: Callable[[Path], int] | None = None,
) -> Path:
    """Refuse unsafe spelling before and after physical path resolution."""

    probe = _drive_type if drive_type is None else drive_type
    _require_local_drive_spelling(path, probe)
    resolved = path.resolve()
    _require_local_drive_spelling(resolved, probe)
    return resolved


def _require_local_drive_spelling(
    path: Path,
    drive_type: Callable[[Path], int],
) -> None:
    if (
        not path.is_absolute()
        or len(path.drive) != 2
        or not path.drive[0].isalpha()
        or path.drive[1] != ":"
        or drive_type(path) not in _LOCAL_DRIVE_TYPES
    ):
        raise ValueError("headed test data root must be an absolute local drive path")


def _drive_type(path: Path) -> int:
    return int(ctypes.windll.kernel32.GetDriveTypeW(f"{path.drive}\\"))


def wait_for_window(
    process: HeadedProcess,
    title: str,
    *,
    exclude: frozenset[int] = frozenset(),
    deadline: ScenarioDeadline,
) -> int:
    while True:
        remaining = deadline.remaining()
        handle = _find_window(title, exclude, process_ids=process.process_ids())
        if handle is not None:
            return handle
        if process.poll() is not None:
            completed = wait_for_process(process, deadline=deadline)
            raise AssertionError(
                f"headed child exited {completed.returncode} before opening {title!r}\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        time.sleep(min(0.05, remaining))


def wait_for_process(
    process: HeadedProcess,
    *,
    deadline: ScenarioDeadline,
) -> subprocess.CompletedProcess[str]:
    while process.poll() is None:
        try:
            remaining = deadline.remaining()
        except AssertionError:
            terminate_process_tree(process, deadline=deadline)
            raise AssertionError(
                f"headed child {process.pid} did not exit before the scenario deadline"
            ) from None
        time.sleep(min(0.025, remaining))
    returncode = process.poll()
    assert returncode is not None
    process.process.returncode = returncode
    process.close_job()
    remaining = deadline.expires_at - time.monotonic()
    if remaining <= 0:
        _bounded_reap(process.process, kill=True, timeout=_cleanup_budget(deadline))
        raise AssertionError(
            f"headed child {process.pid} exited after the scenario deadline"
        )
    try:
        stdout, stderr = process.process.communicate(
            timeout=min(_CLEANUP_SECONDS, remaining)
        )
    except subprocess.TimeoutExpired:
        _bounded_reap(
            process.process,
            kill=True,
            timeout=_cleanup_budget(deadline),
        )
        raise AssertionError(
            f"headed child {process.pid} closed but its output pipes did not reach EOF"
        ) from None
    return subprocess.CompletedProcess(
        process.command,
        returncode,
        stdout,
        stderr,
    )


def terminate_process_tree(
    process: HeadedProcess,
    *,
    deadline: ScenarioDeadline,
) -> None:
    """Close the Job Object, killing every current or late descendant."""

    process.close_job()
    _bounded_reap(
        process.process,
        kill=True,
        timeout=_cleanup_budget(deadline),
    )


def wait_for_exit_or_dialog(
    process: HeadedProcess,
    caption: str,
    *,
    exclude: frozenset[int] = frozenset(),
    deadline: ScenarioDeadline,
) -> tuple[subprocess.CompletedProcess[str] | None, int | None]:
    while True:
        remaining = deadline.remaining()
        handle = _find_window(caption, exclude, process_ids=process.process_ids())
        if handle is not None:
            return None, handle
        if process.poll() is not None:
            return wait_for_process(process, deadline=deadline), None
        time.sleep(min(0.05, remaining))


def dialog_text(handle: int) -> str:
    text = "\n".join(_child_window_text(handle, "Static"))
    if not text:
        raise AssertionError("native dialog exposed no Static control text")
    return text


def close_window(handle: int) -> None:
    user32 = _user32()
    if not user32.PostMessageW(handle, _WM_CLOSE, 0, 0):
        raise ctypes.WinError(ctypes.get_last_error())


def wait_for_accessible_text(
    handle: int,
    expected: str,
    *,
    python: Path,
    deadline: ScenarioDeadline,
) -> tuple[str, ...]:
    """Run potentially blocking UI Automation behind its own hard job boundary."""

    command = (
        python,
        _HOST_CHILD,
        "--uia-probe",
        "--handle",
        str(handle),
        "--expected",
        expected,
        "--timeout",
        str(deadline.remaining()),
    )
    process = start_headed_process(
        command,
        cwd=python.parent.parent,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    completed = wait_for_process(process, deadline=deadline)
    try:
        result = json.loads(completed.stdout.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise AssertionError(
            "UI Automation probe produced no valid result; "
            f"stdout={completed.stdout!r}, stderr={completed.stderr!r}"
        ) from error
    names = tuple(result.get("names", ()))
    if completed.returncode != 0 or expected not in names:
        raise AssertionError(
            f"UI Automation did not expose {expected!r}; observed names: {names!r}; "
            f"error: {result.get('error')!r}"
        )
    return names


def wait_for_dialog_text(
    process: HeadedProcess,
    caption: str,
    *,
    exclude: frozenset[int] = frozenset(),
    deadline: ScenarioDeadline,
) -> tuple[int, str]:
    handle = wait_for_window(
        process,
        caption,
        exclude=exclude,
        deadline=deadline,
    )
    return handle, dialog_text(handle)


def select_folder_in_native_dialog(
    process: HeadedProcess,
    owner_handle: int,
    path: Path,
    *,
    python: Path,
    deadline: ScenarioDeadline,
) -> dict[str, object]:
    """Select one physical-local folder in the child-owned common dialog."""

    selected_path = require_absolute_local_test_root(path)
    dialog = _wait_for_owned_common_dialog(
        process,
        owner_handle,
        deadline=deadline,
    )
    dialog_process_id = _window_process_id(dialog)
    if dialog_process_id not in process.process_ids():
        raise AssertionError("native folder dialog left the headed child job")
    automation = start_headed_process(
        (
            python,
            _HOST_CHILD,
            "--uia-select-folder",
            "--handle",
            str(dialog),
            "--owner-handle",
            str(owner_handle),
            "--process-id",
            str(dialog_process_id),
            "--path",
            str(selected_path),
            "--timeout",
            str(deadline.remaining()),
        ),
        cwd=python.parent.parent,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    completed = wait_for_process(automation, deadline=deadline)
    try:
        result = json.loads(completed.stdout.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise AssertionError(
            "folder-dialog automation produced no valid result; "
            f"stdout={completed.stdout!r}, stderr={completed.stderr!r}"
        ) from error
    if completed.returncode != 0 or result.get("selected") is not True:
        raise AssertionError(
            "folder-dialog automation did not select the requested folder; "
            f"result={result!r}, stderr={completed.stderr!r}"
        )
    while _is_window(dialog):
        remaining = deadline.remaining()
        if process.poll() is not None:
            completed_host = wait_for_process(process, deadline=deadline)
            raise AssertionError(
                "headed child exited while its native folder dialog was open\n"
                f"stdout:\n{completed_host.stdout}\n"
                f"stderr:\n{completed_host.stderr}"
            )
        time.sleep(min(0.025, remaining))
    return result


def _wait_for_owned_common_dialog(
    process: HeadedProcess,
    owner_handle: int,
    *,
    deadline: ScenarioDeadline,
) -> int:
    while True:
        remaining = deadline.remaining()
        process_ids = process.process_ids()
        matches = tuple(
            handle
            for handle in _enumerate_windows()
            if handle != owner_handle
            and _window_process_id(handle) in process_ids
            and _window_class(handle) == _DIALOG_WINDOW_CLASS
            and _window_owner(handle) == owner_handle
            and _is_window_visible(handle)
        )
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise AssertionError(
                "headed child exposed multiple owned common dialogs"
            )
        if process.poll() is not None:
            completed = wait_for_process(process, deadline=deadline)
            raise AssertionError(
                "headed child exited before opening its native folder dialog\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        time.sleep(min(0.025, remaining))


def dismiss_ok_dialog(handle: int) -> None:
    """Post an asynchronous click; never block the test thread in user32."""

    user32 = _user32()
    button = user32.GetDlgItem(handle, 1)
    if not button:
        close_window(handle)
        return
    if not user32.PostMessageW(button, _BM_CLICK, 0, 0):
        raise ctypes.WinError(ctypes.get_last_error())


def wait_for_path(path: Path, *, deadline: ScenarioDeadline) -> None:
    while not path.exists():
        remaining = deadline.remaining()
        time.sleep(min(0.025, remaining))


def wait_for_initial_evidence(
    reader: EvidenceReader,
    process: HeadedProcess,
    *,
    deadline: ScenarioDeadline,
) -> tuple[str, dict[str, object]]:
    """Wait for one immutable ready/failure record or a premature exit."""

    while True:
        milestone = reader.available_initial()
        if milestone is not None:
            payload = (
                reader.read_ready()
                if milestone == "ready"
                else reader.read_failure()
            )
            if payload is None:
                raise AssertionError("headed evidence disappeared after publication")
            return milestone, payload
        if process.poll() is not None:
            completed = wait_for_process(process, deadline=deadline)
            raise AssertionError(
                "headed child exited before publishing ready or failure evidence\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        remaining = deadline.remaining()
        time.sleep(min(0.025, remaining))


def directory_snapshot(
    root: Path,
    *,
    deadline: ScenarioDeadline,
) -> tuple[tuple[object, ...], ...]:
    if not root.exists():
        return ()
    records: list[tuple[object, ...]] = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        deadline.remaining()
        current = Path(directory)
        names.sort()
        filenames.sort()
        for name in (*names, *filenames):
            path = current / name
            stat = path.lstat()
            digest = None
            if path.is_file() and not path.is_symlink():
                digest = _hash_file(path, deadline=deadline)
            records.append(
                (
                    str(path.relative_to(root)),
                    stat.st_mode,
                    stat.st_size,
                    stat.st_mtime_ns,
                    digest,
                )
            )
    return tuple(records)


def read_bytes(
    path: Path,
    *,
    deadline: ScenarioDeadline,
) -> bytes:
    chunks: list[bytes] = []
    with path.open("rb") as stream:
        while True:
            deadline.remaining()
            chunk = stream.read(1024 * 1024)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)


def read_text(
    path: Path,
    *,
    deadline: ScenarioDeadline,
    encoding: str = "utf-8",
) -> str:
    return read_bytes(path, deadline=deadline).decode(encoding)


def run_with_deadline(
    command: Sequence[str | os.PathLike[str]],
    *,
    deadline: ScenarioDeadline,
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    """Run one non-window child inside the scenario's single time budget."""

    return subprocess.run(
        [os.fspath(part) for part in command],
        timeout=deadline.remaining(),
        **kwargs,
    )


def window_handles(title: str) -> frozenset[int]:
    return frozenset(
        handle for handle in _enumerate_windows() if _window_text(handle) == title
    )


def foreground_window_handle() -> int | None:
    handle = _user32().GetForegroundWindow()
    return int(handle) if handle else None


def _bounded_reap(
    process: subprocess.Popen[str],
    *,
    kill: bool,
    timeout: float,
) -> None:
    if kill and process.poll() is None:
        process.kill()
    try:
        process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if process.poll() is None:
            process.kill()
        for pipe in (process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            pass


def _cleanup_budget(deadline: ScenarioDeadline) -> float:
    """Retain only a tiny bounded cleanup allowance after a hard deadline."""

    remaining = deadline.expires_at - time.monotonic()
    return min(_CLEANUP_SECONDS, max(0.1, remaining))


def _hash_file(path: Path, *, deadline: ScenarioDeadline) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            deadline.remaining()
            chunk = stream.read(1024 * 1024)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def _job_process_ids(job_handle: object) -> frozenset[int]:
    """Return every active job member, including reparented descendants."""

    kernel32 = _kernel32()
    capacity = 32
    while capacity <= 2048:
        class _ProcessIdList(ctypes.Structure):
            _fields_ = (
                ("NumberOfAssignedProcesses", wintypes.DWORD),
                ("NumberOfProcessIdsInList", wintypes.DWORD),
                ("ProcessIdList", ctypes.c_size_t * capacity),
            )

        information = _ProcessIdList()
        returned = wintypes.DWORD()
        ctypes.set_last_error(0)
        if kernel32.QueryInformationJobObject(
            job_handle,
            3,
            ctypes.byref(information),
            ctypes.sizeof(information),
            ctypes.byref(returned),
        ):
            return frozenset(
                int(information.ProcessIdList[index])
                for index in range(information.NumberOfProcessIdsInList)
            )
        error = ctypes.get_last_error()
        if error != _ERROR_MORE_DATA:
            raise ctypes.WinError(error)
        capacity = max(capacity * 2, int(information.NumberOfAssignedProcesses))
    raise AssertionError("headed job exceeded 2048 active processes")


def _find_window(
    title: str,
    exclude: frozenset[int],
    *,
    process_ids: frozenset[int] | None = None,
) -> int | None:
    for handle in _enumerate_windows():
        if (
            handle not in exclude
            and _window_text(handle) == title
            and _is_window_visible(handle)
            and (process_ids is None or _window_process_id(handle) in process_ids)
        ):
            return handle
    return None


def _enumerate_windows() -> tuple[int, ...]:
    user32 = _user32()
    handles: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def collect(handle: int, _: int) -> bool:
        handles.append(int(handle))
        return True

    if not user32.EnumWindows(collect, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return tuple(handles)


def _window_process_id(handle: int) -> int:
    process_id = wintypes.DWORD()
    _user32().GetWindowThreadProcessId(handle, ctypes.byref(process_id))
    return int(process_id.value)


def _window_class(handle: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    _user32().GetClassNameW(handle, buffer, len(buffer))
    return buffer.value


def _window_owner(handle: int) -> int | None:
    owner = _user32().GetWindow(handle, _GW_OWNER)
    return int(owner) if owner else None


def _is_window(handle: int) -> bool:
    return bool(_user32().IsWindow(handle))


def _is_window_visible(handle: int) -> bool:
    return bool(_user32().IsWindowVisible(handle))


def _window_text(handle: int) -> str:
    user32 = _user32()
    length = user32.GetWindowTextLengthW(handle)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, len(buffer))
    return buffer.value


def _child_window_text(handle: int, class_name: str) -> tuple[str, ...]:
    user32 = _user32()
    values: list[str] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def collect(child: int, _: int) -> bool:
        class_buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(child, class_buffer, len(class_buffer))
        if class_buffer.value == class_name:
            text = _window_text(int(child))
            if text:
                values.append(text)
        return True

    if not user32.EnumChildWindows(handle, collect, 0):
        error = ctypes.get_last_error()
        if error:
            raise ctypes.WinError(error)
    return tuple(values)


def _kernel32():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateEventW.argtypes = (
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.SetEvent.argtypes = (wintypes.HANDLE,)
    kernel32.SetEvent.restype = wintypes.BOOL
    kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.QueryInformationJobObject.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def _user32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.EnumWindows.argtypes = (ctypes.c_void_p, wintypes.LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumChildWindows.argtypes = (
        wintypes.HWND,
        ctypes.c_void_p,
        wintypes.LPARAM,
    )
    user32.EnumChildWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    )
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    )
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = (
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    )
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetWindow.restype = wintypes.HWND
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsWindowEnabled.argtypes = (wintypes.HWND,)
    user32.IsWindowEnabled.restype = wintypes.BOOL
    user32.IsChild.argtypes = (wintypes.HWND, wintypes.HWND)
    user32.IsChild.restype = wintypes.BOOL
    user32.GetDlgCtrlID.argtypes = (wintypes.HWND,)
    user32.GetDlgCtrlID.restype = ctypes.c_int
    user32.PostMessageW.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    user32.PostMessageW.restype = wintypes.BOOL
    user32.GetDlgItem.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.GetDlgItem.restype = wintypes.HWND
    user32.GetForegroundWindow.argtypes = ()
    user32.GetForegroundWindow.restype = wintypes.HWND
    return user32
