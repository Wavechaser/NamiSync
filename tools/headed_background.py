"""Run the page-directed headed tests on a fresh, non-input Windows desktop."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from contextlib import ExitStack
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


class _StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("reserved", wintypes.LPWSTR),
        ("desktop", wintypes.LPWSTR), ("title", wintypes.LPWSTR),
        *[(field, wintypes.DWORD) for field in
          ("x", "y", "width", "height", "columns", "lines", "fill", "flags")],
        ("show", wintypes.WORD), ("reserved_size", wintypes.WORD),
        ("reserved_data", wintypes.LPVOID),
        ("stdin", wintypes.HANDLE), ("stdout", wintypes.HANDLE), ("stderr", wintypes.HANDLE),
    ]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("process", wintypes.HANDLE), ("thread", wintypes.HANDLE),
        ("pid", wintypes.DWORD), ("tid", wintypes.DWORD),
    ]


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "tests" / "interfaces" / "web"))
    from _headed_native import create_headed_job

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID,
                                    wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
    user.CreateDesktopW.restype = wintypes.HANDLE
    user.CloseDesktop.argtypes = [wintypes.HANDLE]
    kernel.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL,
        wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
        ctypes.POINTER(_StartupInfo), ctypes.POINTER(_ProcessInfo),
    ]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD

    desktop_name = f"NamiSyncTests-{uuid4().hex}"
    # CREATEWINDOW, CREATEMENU, READOBJECTS and WRITEOBJECTS; no SWITCHDESKTOP.
    desktop = user.CreateDesktopW(desktop_name, None, None, 0, 0x0087, None)
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())
    with ExitStack() as handles:
        handles.callback(user.CloseDesktop, desktop)
        startup = _StartupInfo(cb=ctypes.sizeof(_StartupInfo), desktop=desktop_name)
        process = _ProcessInfo()
        job = create_headed_job()
        handles.callback(kernel.CloseHandle, job)

        def close_process():
            if process.process:
                # Also covers interruption while the child is still suspended
                # before Job assignment. Its descendants belong to the Job.
                if kernel.WaitForSingleObject(process.process, 0) == 258:
                    kernel.TerminateProcess(process.process, 1)
                kernel.CloseHandle(process.process)
            if process.thread:
                kernel.CloseHandle(process.thread)

        handles.callback(close_process)
        args = [sys.executable, "-m", "pytest", "-q", "-o", "addopts=", "-m", "background_headed"]
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(args))
        with ExitStack() as pipes:
            for name in ("stdin", "stdout", "stderr"):
                fd = os.dup(getattr(sys, name).fileno())
                pipes.callback(os.close, fd)
                os.set_inheritable(fd, True)
                setattr(startup, name, msvcrt.get_osfhandle(fd))
            startup.flags = subprocess.STARTF_USESTDHANDLES
            if not kernel.CreateProcessW(sys.executable, command, None, None, True,
                                         subprocess.CREATE_NO_WINDOW | 0x4, None,
                                         str(repo),
                                         ctypes.byref(startup), ctypes.byref(process)):
                raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(job, process.process):
            raise ctypes.WinError(ctypes.get_last_error())
        if kernel.ResumeThread(process.thread) == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        # A finite wait lets Python handle Ctrl+C; closing the Job reaps descendants.
        while (wait := kernel.WaitForSingleObject(process.process, 250)) == 258:
            pass
        if wait != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(process.process, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return code.value


if __name__ == "__main__":
    raise SystemExit(main())
