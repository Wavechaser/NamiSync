r"""Opt-in installed-wheel WebView2 benchmark for SH-G-8/BR-G-42.

Run from the repository root after committing the harness::

    .\.venv\Scripts\python.exe tests\bridge_event_benchmark.py --output "$env:TEMP\namisync-bridge-event-benchmark.json"

The wheel is built from ``git archive HEAD``. The script is intentionally not
named ``test_*.py`` because its event fixture runs for a real 60 seconds.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile
from ctypes import wintypes
from functools import lru_cache
from pathlib import Path
from uuid import uuid4


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WEB_TEST_ROOT = Path(__file__).resolve().parent / "interfaces" / "web"
if str(WEB_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_TEST_ROOT))

from _headed_native import (  # noqa: E402
    HeadedProcess,
    ScenarioDeadline,
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    _JobObjectExtendedLimitInformation,
    _kernel32,
    clean_child_environment,
    close_window,
    scenario_deadline,
    terminate_process_tree,
    wait_for_process,
    wait_for_window,
)


_CHILD = WEB_TEST_ROOT / "_bridge_event_benchmark_child.py"
_ASSETS = Path(__file__).resolve().parent / "assets" / "bridge_event_benchmark"
_RELIABLE_P95_MAX_MS = 100.0
_RELIABLE_MAX_MS = 250.0
_PROGRESS_P95_MAX_MS = 1_000.0
_PROGRESS_MAX_MS = 2_000.0
_MEMORY_SAMPLE_SECONDS = 0.02
_MEMORY_BASELINE_SECONDS = 1.0
_MEMORY_MAX_BLIND_INTERVAL_SECONDS = 0.1
_PRODUCER_EARLY_TOLERANCE_SECONDS = 0.01
_PRODUCER_MAX_LATENESS_SECONDS = 0.1
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_PROCESS_VM_READ = 0x0010
_PROCESS_COMMAND_LINE_INFORMATION = 60
_TH32CS_SNAPTHREAD = 0x00000004
_RESOURCE_SAMPLE_SECONDS = 1.0
_RESOURCE_MAX_BLIND_INTERVAL_SECONDS = 1.25
_REFERENCE_OS_BUILD = "26200"
_REFERENCE_OS_CAPTION = "Microsoft Windows 11 Pro"
_REFERENCE_OS_ARCHITECTURE = "64-bit"
_REFERENCE_CPU = "13th Gen Intel(R) Core(TM) i7-13700K"
_REFERENCE_STORAGE = "WD_BLACK SN850X 4000GB"
_REFERENCE_PHYSICAL_CPUS = 16
_REFERENCE_LOGICAL_CPUS = 24
_REFERENCE_MEMORY_MIN_BYTES = 63 * 1024**3
_REFERENCE_MEMORY_MAX_BYTES = 65 * 1024**3
_REFERENCE_PYTHON_PREFIX = "3.13.14 "
_REFERENCE_SQLITE = "3.50.4"
_REFERENCE_PYWEBVIEW = "6.2.1"
_REFERENCE_PYTHONNET = "3.1.0"


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = (
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    )


class _ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = (
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    )


class _SystemPowerStatus(ctypes.Structure):
    _fields_ = (
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    )


class _UnicodeString(ctypes.Structure):
    _fields_ = (
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_void_p),
    )


class _ThreadEntry32(ctypes.Structure):
    _fields_ = (
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ThreadID", wintypes.DWORD),
        ("th32OwnerProcessID", wintypes.DWORD),
        ("tpBasePri", wintypes.LONG),
        ("tpDeltaPri", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
    )


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _run(
    command: list[str],
    *,
    cwd: Path,
    timeout: float,
    environment: dict[str, str] | None = None,
) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout.strip()


def _build_archived_wheel(root: Path) -> tuple[Path, str, tuple[str, ...]]:
    commit = _run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        timeout=10,
    )
    status_text = _run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=REPOSITORY_ROOT,
        timeout=10,
    )
    archive = root / "source.zip"
    build_environment = _clean_python_environment()
    _run(
        ["git", "archive", "--format=zip", f"--output={archive}", commit],
        cwd=REPOSITORY_ROOT,
        timeout=60,
    )
    source = root / "source"
    source.mkdir()
    with zipfile.ZipFile(archive) as compressed:
        compressed.extractall(source)
    wheel_dir = root / "wheel"
    wheel_dir.mkdir()
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(source),
        ],
        cwd=wheel_dir,
        timeout=180,
        environment=build_environment,
    )
    wheels = tuple(wheel_dir.glob("namisync-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("archive build did not produce exactly one NamiSync wheel")
    status = tuple(line for line in status_text.splitlines() if line)
    return wheels[0], commit, status


def _install_wheel(root: Path, wheel: Path) -> Path:
    environment = _clean_python_environment()
    venv_root = root / "venv"
    _run(
        [sys.executable, "-m", "venv", "--clear", str(venv_root)],
        cwd=root,
        timeout=120,
        environment=environment,
    )
    python = venv_root / "Scripts" / "python.exe"
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            str(wheel),
        ],
        cwd=venv_root,
        timeout=240,
        environment=environment,
    )
    _run(
        [str(python), "-m", "pip", "check"],
        cwd=venv_root,
        timeout=60,
        environment=environment,
    )
    return python


def _stage_page(root: Path, python: Path, archived_source: Path) -> Path:
    page = root / "page"
    archived_assets = archived_source / "tests" / "assets" / _ASSETS.name
    shutil.copytree(archived_assets, page)
    shutil.copy2(
        archived_source / "tests" / "assets" / "bootstrap_test_bridge.js",
        page / "bootstrap_test_bridge.js",
    )
    site_packages = python.parents[1] / "Lib" / "site-packages"
    installed_assets = (
        site_packages / "namisync" / "interfaces" / "web" / "assets"
    )
    for name in ("bridge.js", "readiness.js", "render.js"):
        shutil.copy2(installed_assets / name, page / name)
    return page / "index.html"


def _read_evidence(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return value if type(value) is dict else {}


def _read_sample_stream(
    path: Path,
    metadata: object,
) -> list[dict[str, object]]:
    if (
        type(metadata) is not dict
        or set(metadata) != {"batch_count", "sample_count", "sha256"}
        or type(metadata.get("batch_count")) is not int
        or metadata["batch_count"] < 0
        or type(metadata.get("sample_count")) is not int
        or metadata["sample_count"] < 0
        or type(metadata.get("sha256")) is not str
        or re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"]) is None
    ):
        raise RuntimeError("benchmark sample-stream metadata is invalid")
    encoded_lines = (
        []
        if not path.exists()
        else path.read_bytes().splitlines(keepends=True)
    )
    samples: list[dict[str, object]] = []
    digest = hashlib.sha256()
    for encoded in encoded_lines:
        if not encoded.endswith(b"\n"):
            raise RuntimeError("benchmark sample stream ended with a partial batch")
        digest.update(encoded)
        try:
            batch = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError("benchmark sample stream is corrupt") from error
        if (
            type(batch) is not list
            or not batch
            or len(batch) > 100
            or any(type(sample) is not dict for sample in batch)
        ):
            raise RuntimeError("benchmark sample stream batch is invalid")
        samples.extend(batch)
    if (
        len(encoded_lines) != metadata["batch_count"]
        or len(samples) != metadata["sample_count"]
        or digest.hexdigest() != metadata["sha256"]
    ):
        raise RuntimeError("benchmark sample stream does not match its manifest")
    return samples


def _attach_streamed_evidence(
    evidence: dict[str, object],
    evidence_path: Path,
) -> dict[str, object]:
    attached = dict(evidence)
    attached["samples"] = _read_sample_stream(
        evidence_path.with_suffix(evidence_path.suffix + ".samples.jsonl"),
        evidence.get("sample_stream"),
    )
    producer_streams = evidence.get("producer_streams")
    if type(producer_streams) is not dict or set(producer_streams) != {
        "0",
        "1",
        "2",
        "3",
    }:
        raise RuntimeError("benchmark producer-stream manifest is invalid")
    for task_index in range(4):
        metadata = producer_streams[str(task_index)]
        if (
            type(metadata) is not dict
            or set(metadata) != {"byte_count", "sha256", "timings"}
            or type(metadata.get("byte_count")) is not int
            or metadata["byte_count"] <= 0
            or type(metadata.get("sha256")) is not str
            or re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"]) is None
        ):
            raise RuntimeError("benchmark producer-stream metadata is invalid")
        path = evidence_path.with_suffix(
            evidence_path.suffix + f".producer-{task_index}.json"
        )
        try:
            encoded = path.read_bytes()
            value = json.loads(encoded.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError("benchmark producer stream is corrupt") from error
        if (
            len(encoded) != metadata["byte_count"]
            or hashlib.sha256(encoded).hexdigest() != metadata["sha256"]
            or type(value) is not dict
        ):
            raise RuntimeError("benchmark producer stream does not match its manifest")
        progress, reliable = _read_producer_timing_stream(
            evidence_path.with_suffix(
                evidence_path.suffix
                + f".producer-{task_index}.timings.jsonl"
            ),
            metadata["timings"],
        )
        value["progress_emission_offsets_seconds"] = progress
        value["reliable_emission_offsets_seconds"] = reliable
        attached[f"producer_task_{task_index}"] = value
    return attached


def _read_producer_timing_stream(
    path: Path,
    metadata: object,
) -> tuple[list[float], list[float]]:
    if (
        type(metadata) is not dict
        or set(metadata)
        != {"batch_count", "progress_count", "reliable_count", "sha256"}
        or type(metadata.get("batch_count")) is not int
        or metadata["batch_count"] <= 0
        or type(metadata.get("progress_count")) is not int
        or metadata["progress_count"] <= 0
        or type(metadata.get("reliable_count")) is not int
        or metadata["reliable_count"] < 0
        or type(metadata.get("sha256")) is not str
        or re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"]) is None
    ):
        raise RuntimeError("benchmark producer-timing metadata is invalid")
    try:
        encoded_lines = path.read_bytes().splitlines(keepends=True)
    except OSError as error:
        raise RuntimeError("benchmark producer timing stream is missing") from error
    progress: list[float] = []
    reliable: list[float] = []
    digest = hashlib.sha256()
    for encoded in encoded_lines:
        if not encoded.endswith(b"\n"):
            raise RuntimeError("benchmark producer timing stream ended partially")
        digest.update(encoded)
        try:
            batch = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError("benchmark producer timing stream is corrupt") from error
        if (
            type(batch) is not dict
            or set(batch) != {"progress", "reliable"}
            or type(batch["progress"]) is not list
            or not batch["progress"]
            or len(batch["progress"]) > 125
            or type(batch["reliable"]) is not list
            or len(batch["reliable"]) > 125
            or any(not _is_finite_number(value) for value in batch["progress"])
            or any(not _is_finite_number(value) for value in batch["reliable"])
        ):
            raise RuntimeError("benchmark producer timing batch is invalid")
        progress.extend(float(value) for value in batch["progress"])
        reliable.extend(float(value) for value in batch["reliable"])
    if (
        len(encoded_lines) != metadata["batch_count"]
        or len(progress) != metadata["progress_count"]
        or len(reliable) != metadata["reliable_count"]
        or digest.hexdigest() != metadata["sha256"]
    ):
        raise RuntimeError(
            "benchmark producer timing stream does not match its manifest"
        )
    return progress, reliable


def _clean_python_environment() -> dict[str, str]:
    environment = clean_child_environment()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def _start_direct_job_process(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    deadline: ScenarioDeadline,
) -> HeadedProcess:
    """Assign the actual benchmark host before admitting product composition."""

    gate_name = rf"Local\NamiSync.BridgeBenchmark.Admission.{uuid4().hex}"
    admission_timeout_ms = str(max(1, int(deadline.remaining() * 1_000)))
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

    actual_command = (
        *command,
        "--admission-gate",
        gate_name,
        "--admission-timeout-ms",
        admission_timeout_ms,
    )
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            actual_command,
            cwd=cwd,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if process.poll() is not None:
            raise RuntimeError("benchmark host exited before Job assignment")
        if not kernel32.AssignProcessToJobObject(job, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.SetEvent(gate):
            raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        kernel32.CloseHandle(job)
        kernel32.CloseHandle(gate)
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5.0)
        raise
    return HeadedProcess(process, tuple(actual_command), job, gate)


@lru_cache(maxsize=1)
def _private_memory_apis():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    kernel32.OpenProcess.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetProcessHandleCount.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.GetProcessHandleCount.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    )
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CreateToolhelp32Snapshot.argtypes = (
        wintypes.DWORD,
        wintypes.DWORD,
    )
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Thread32First.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_ThreadEntry32),
    )
    kernel32.Thread32First.restype = wintypes.BOOL
    kernel32.Thread32Next.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_ThreadEntry32),
    )
    kernel32.Thread32Next.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_ProcessMemoryCountersEx),
        wintypes.DWORD,
    )
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    ntdll.NtQueryInformationProcess.argtypes = (
        wintypes.HANDLE,
        wintypes.ULONG,
        ctypes.c_void_p,
        wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG),
    )
    ntdll.NtQueryInformationProcess.restype = wintypes.LONG
    return kernel32, psapi, ntdll


def _process_private_bytes(process_id: int) -> int | None:
    kernel32, psapi, _ntdll = _private_memory_apis()
    handle = kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION | _PROCESS_VM_READ,
        False,
        process_id,
    )
    if not handle:
        return None
    try:
        counters = _ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            handle,
            ctypes.byref(counters),
            ctypes.sizeof(counters),
        ):
            return None
        return int(counters.PrivateUsage)
    finally:
        kernel32.CloseHandle(handle)


def _process_metadata(
    process_id: int,
    *,
    root_process_id: int,
) -> dict[str, object] | None:
    kernel32, _psapi, ntdll = _private_memory_apis()
    handle = kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION | _PROCESS_VM_READ,
        False,
        process_id,
    )
    if not handle:
        return None
    try:
        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
        image = ctypes.create_unicode_buffer(32_768)
        image_length = wintypes.DWORD(len(image))
        if not kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            image,
            ctypes.byref(image_length),
        ):
            return None
        command_line = _query_process_command_line(ntdll, handle)
        image_path = image.value
        return {
            "command_role": _classify_process_role(
                process_id,
                root_process_id=root_process_id,
                image_path=image_path,
                command_line=command_line,
            ),
            "creation_time_100ns": (
                int(created.dwHighDateTime) << 32
            ) | int(created.dwLowDateTime),
            "image_name": Path(image_path).name,
            "process_id": process_id,
        }
    finally:
        kernel32.CloseHandle(handle)


def _query_process_command_line(ntdll: object, handle: object) -> str | None:
    required = wintypes.ULONG()
    ntdll.NtQueryInformationProcess(
        handle,
        _PROCESS_COMMAND_LINE_INFORMATION,
        None,
        0,
        ctypes.byref(required),
    )
    if required.value < ctypes.sizeof(_UnicodeString):
        return None
    buffer = ctypes.create_string_buffer(required.value)
    status = ntdll.NtQueryInformationProcess(
        handle,
        _PROCESS_COMMAND_LINE_INFORMATION,
        buffer,
        required.value,
        ctypes.byref(required),
    )
    if status < 0:
        return None
    value = _UnicodeString.from_buffer(buffer)
    if not value.Buffer or value.Length % ctypes.sizeof(ctypes.c_wchar) != 0:
        return None
    return ctypes.wstring_at(
        value.Buffer,
        value.Length // ctypes.sizeof(ctypes.c_wchar),
    )


def _classify_process_role(
    process_id: int,
    *,
    root_process_id: int,
    image_path: str,
    command_line: str | None,
) -> str:
    if process_id == root_process_id:
        return "python-host"
    image_name = Path(image_path).name.casefold()
    if image_name == "msedgewebview2.exe":
        if command_line is None:
            return "unknown:webview2-command-line-unavailable"
        command = command_line
        process_type = re.search(r"(?:^|\s)--type=([^\s\"]+)", command)
        if process_type is None:
            return "webview2-browser"
        role = process_type.group(1)
        if role == "utility":
            subtype = re.search(
                r"(?:^|\s)--utility-sub-type=([^\s\"]+)",
                command,
            )
            if subtype is not None:
                return f"webview2-utility:{subtype.group(1)}"
        return f"webview2-{role}"
    if image_name.startswith("python"):
        return "python-child"
    return f"other:{image_name or 'unknown'}"


def _process_resource_snapshot(
    process_ids: tuple[int, ...],
) -> dict[int, dict[str, int]] | None:
    thread_counts = _thread_counts(process_ids)
    if thread_counts is None:
        return None
    kernel32, _psapi, _ntdll = _private_memory_apis()
    resources: dict[int, dict[str, int]] = {}
    for process_id in process_ids:
        handle = kernel32.OpenProcess(
            _PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            process_id,
        )
        if not handle:
            return None
        try:
            handle_count = wintypes.DWORD()
            if not kernel32.GetProcessHandleCount(
                handle,
                ctypes.byref(handle_count),
            ):
                return None
            resources[process_id] = {
                "handle_count": int(handle_count.value),
                "thread_count": thread_counts.get(process_id, 0),
            }
        finally:
            kernel32.CloseHandle(handle)
    return resources


def _thread_counts(process_ids: tuple[int, ...]) -> dict[int, int] | None:
    kernel32, _psapi, _ntdll = _private_memory_apis()
    snapshot = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPTHREAD, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return None
    wanted = set(process_ids)
    counts = {process_id: 0 for process_id in process_ids}
    try:
        entry = _ThreadEntry32()
        entry.dwSize = ctypes.sizeof(entry)
        present = bool(kernel32.Thread32First(snapshot, ctypes.byref(entry)))
        while present:
            owner = int(entry.th32OwnerProcessID)
            if owner in wanted:
                counts[owner] += 1
            entry.dwSize = ctypes.sizeof(entry)
            present = bool(kernel32.Thread32Next(snapshot, ctypes.byref(entry)))
    finally:
        kernel32.CloseHandle(snapshot)
    return counts


class _JobPrivateMemorySampler:
    def __init__(self, process) -> None:
        self._process = process
        self._started_at = time.perf_counter()
        self._samples: list[dict[str, object]] = []
        self._processes: dict[str, dict[str, object]] = {}
        self._resource_samples: list[dict[str, object]] = []
        self._topology_transitions: list[dict[str, object]] = []
        self._previous_process_ids: tuple[int, ...] = ()
        self._next_resource_sample_at = self._started_at
        self._fixture_ended_at_seconds: float | None = None
        self._diagnostics_disabled = False

    def sample(self, phase: str) -> None:
        sampled_at = time.perf_counter()
        if self._diagnostics_disabled:
            self._append_unavailable_sample(sampled_at, phase, error=None)
            return
        try:
            self._sample(phase, sampled_at)
        except Exception as error:
            self._diagnostics_disabled = True
            self._append_unavailable_sample(
                sampled_at,
                phase,
                error=f"{type(error).__name__}: {error}",
            )

    def _sample(self, phase: str, sampled_at: float) -> None:
        process_ids: tuple[int, ...] = ()
        private_bytes: int | None = None
        private_bytes_by_process: dict[str, int] = {}
        missing_process_ids: tuple[int, ...] = ()
        for _ in range(3):
            before = tuple(sorted(self._process.process_ids()))
            values = {
                process_id: _process_private_bytes(process_id)
                for process_id in before
            }
            after = tuple(sorted(self._process.process_ids()))
            missing = tuple(
                process_id
                for process_id, value in values.items()
                if value is None
            )
            if before == after and not missing:
                process_ids = before
                private_bytes = sum(int(value) for value in values.values())
                private_bytes_by_process = {
                    str(process_id): int(value)
                    for process_id, value in values.items()
                }
                missing_process_ids = ()
                break
            process_ids = after
            missing_process_ids = missing
        elapsed_seconds = sampled_at - self._started_at
        if private_bytes is not None:
            for process_id in process_ids:
                key = str(process_id)
                if key not in self._processes:
                    metadata = _process_metadata(
                        process_id,
                        root_process_id=self._process.pid,
                    )
                    if metadata is None:
                        raise RuntimeError(
                            f"process metadata unavailable for PID {process_id}"
                        )
                    self._processes[key] = metadata
            if private_bytes is not None:
                if process_ids != self._previous_process_ids:
                    previous = set(self._previous_process_ids)
                    current = set(process_ids)
                    self._topology_transitions.append(
                        {
                            "elapsed_seconds": elapsed_seconds,
                            "exited_process_ids": sorted(previous - current),
                            "joined_process_ids": sorted(current - previous),
                        }
                    )
                    self._previous_process_ids = process_ids
                if sampled_at >= self._next_resource_sample_at:
                    self._next_resource_sample_at = (
                        sampled_at + _RESOURCE_SAMPLE_SECONDS
                    )
                    resources = _process_resource_snapshot(process_ids)
                    if resources is None:
                        missing_process_ids = (*missing_process_ids, *process_ids)
                        private_bytes = None
                        private_bytes_by_process = {}
                    else:
                        self._resource_samples.append(
                            {
                                "elapsed_seconds": elapsed_seconds,
                                "phase": phase,
                                "processes": {
                                    str(process_id): values
                                    for process_id, values in resources.items()
                                },
                            }
                        )
        self._samples.append(
            {
                "diagnostic_error": None,
                "elapsed_seconds": elapsed_seconds,
                "missing_process_ids": sorted(set(missing_process_ids)),
                "phase": phase,
                "private_bytes": private_bytes,
                "private_bytes_by_process": private_bytes_by_process,
                "process_ids": list(process_ids),
            }
        )

    def _append_unavailable_sample(
        self,
        sampled_at: float,
        phase: str,
        *,
        error: str | None,
    ) -> None:
        self._samples.append(
            {
                "diagnostic_error": error,
                "elapsed_seconds": sampled_at - self._started_at,
                "missing_process_ids": [],
                "phase": phase,
                "private_bytes": None,
                "private_bytes_by_process": {},
                "process_ids": [],
            }
        )

    def wait_until_ready(self, marker: Path, deadline: ScenarioDeadline) -> None:
        while True:
            deadline.remaining()
            if marker.is_file():
                return
            if self._process.poll() is not None:
                raise RuntimeError("benchmark child exited before browser readiness")
            time.sleep(0.02)

    def take_idle_baseline(self, deadline) -> None:
        ends_at = time.perf_counter() + _MEMORY_BASELINE_SECONDS
        next_sample = time.perf_counter()
        while time.perf_counter() < ends_at:
            deadline.remaining()
            self.sample("baseline")
            next_sample += _MEMORY_SAMPLE_SECONDS
            remaining = next_sample - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)

    def run_until_browser_report(
        self,
        report_marker: Path,
        failure_marker: Path,
        begin_marker: Path,
        deadline: ScenarioDeadline,
    ) -> bool:
        begin_marker.write_text("begin\n", encoding="ascii")
        next_sample = time.perf_counter()
        while True:
            deadline.remaining()
            self.sample("fixture")
            if failure_marker.is_file() or report_marker.is_file():
                self._fixture_ended_at_seconds = (
                    time.perf_counter() - self._started_at
                )
                return not failure_marker.is_file()
            if self._process.poll() is not None:
                raise RuntimeError("benchmark child exited before browser report")
            next_sample += _MEMORY_SAMPLE_SECONDS
            remaining = next_sample - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)

    def result(self) -> dict[str, object]:
        return _job_memory_result(
            self._samples,
            fixture_ended_at_seconds=self._fixture_ended_at_seconds,
            processes=self._processes,
            resource_samples=self._resource_samples,
            root_process_id=self._process.pid,
            topology_transitions=self._topology_transitions,
        )


def _wait_for_browser_presentation(
    marker: Path,
    failure_marker: Path,
    process: HeadedProcess,
    deadline: ScenarioDeadline,
) -> bool:
    while True:
        deadline.remaining()
        if failure_marker.is_file():
            return False
        if marker.is_file():
            return True
        if process.poll() is not None:
            raise RuntimeError("benchmark child exited before browser presentation")
        time.sleep(0.02)


def _job_memory_result(
    samples: list[dict[str, object]],
    *,
    fixture_ended_at_seconds: float | None = None,
    processes: dict[str, dict[str, object]],
    resource_samples: list[dict[str, object]],
    root_process_id: int,
    topology_transitions: list[dict[str, object]],
) -> dict[str, object]:
    valid_samples = [
        sample
        for sample in samples
        if type(sample) is dict
        and set(sample)
        == {
            "diagnostic_error",
            "elapsed_seconds",
            "missing_process_ids",
            "phase",
            "private_bytes",
            "private_bytes_by_process",
            "process_ids",
        }
        and (
            type(sample.get("elapsed_seconds")) in {int, float}
            and math.isfinite(float(sample["elapsed_seconds"]))
            and float(sample["elapsed_seconds"]) >= 0
        )
        and sample.get("phase") in {"baseline", "fixture"}
        and (
            sample.get("diagnostic_error") is None
            or (
                type(sample.get("diagnostic_error")) is str
                and bool(sample["diagnostic_error"])
            )
        )
        and (
            sample.get("private_bytes") is None
            or (
                type(sample.get("private_bytes")) is int
                and sample["private_bytes"] >= 0
            )
        )
        and type(sample.get("process_ids")) is list
        and all(
            type(process_id) is int and process_id > 0
            for process_id in sample["process_ids"]
        )
        and len(sample["process_ids"]) == len(set(sample["process_ids"]))
        and type(sample.get("missing_process_ids")) is list
        and all(
            type(process_id) is int and process_id > 0
            for process_id in sample["missing_process_ids"]
        )
        and len(sample["missing_process_ids"])
        == len(set(sample["missing_process_ids"]))
        and type(sample.get("private_bytes_by_process")) is dict
        and (
            (
                sample["private_bytes"] is None
                and sample["private_bytes_by_process"] == {}
            )
            or (
                type(sample["private_bytes"]) is int
                and set(sample["private_bytes_by_process"])
                == {str(process_id) for process_id in sample["process_ids"]}
                and all(
                    type(value) is int and value >= 0
                    for value in sample["private_bytes_by_process"].values()
                )
                and sum(sample["private_bytes_by_process"].values())
                == sample["private_bytes"]
            )
        )
    ]
    elapsed = [float(sample["elapsed_seconds"]) for sample in valid_samples]
    timestamps_strict = all(
        earlier < later
        for earlier, later in zip(elapsed, elapsed[1:], strict=False)
    )
    phases = [sample["phase"] for sample in valid_samples]
    phase_order_valid = phases == sorted(
        phases,
        key={"baseline": 0, "fixture": 1}.__getitem__,
    )
    fixture_end_valid = bool(
        type(fixture_ended_at_seconds) in {int, float}
        and math.isfinite(float(fixture_ended_at_seconds))
        and float(fixture_ended_at_seconds) >= 0
        and bool(elapsed)
        and float(fixture_ended_at_seconds) >= elapsed[-1]
    )
    intervals = [
        later - earlier
        for earlier, later in zip(elapsed, elapsed[1:], strict=False)
    ]
    if fixture_end_valid:
        intervals.append(float(fixture_ended_at_seconds) - elapsed[-1])
    max_sample_interval_seconds = (
        max(intervals) if intervals and timestamps_strict and fixture_end_valid else None
    )
    baseline = [
        sample["private_bytes"]
        for sample in valid_samples
        if sample["phase"] == "baseline"
        and type(sample["private_bytes"]) is int
    ]
    fixture = [
        sample["private_bytes"]
        for sample in valid_samples
        if sample["phase"] == "fixture"
        and type(sample["private_bytes"]) is int
    ]
    idle_baseline = min(baseline) if baseline else None
    sampled_peak = max(fixture) if fixture else None
    incremental_peak = (
        max(0, sampled_peak - idle_baseline)
        if idle_baseline is not None and sampled_peak is not None
        else None
    )
    fixture_times = [
        float(sample["elapsed_seconds"])
        for sample in valid_samples
        if sample.get("phase") == "fixture"
        and _is_finite_number(sample.get("elapsed_seconds"))
    ]
    process_metadata_valid = bool(
        type(processes) is dict
        and processes
        and all(
            type(process_id) is str
            and process_id.isdecimal()
            and type(metadata) is dict
            and set(metadata)
            == {
                "command_role",
                "creation_time_100ns",
                "image_name",
                "process_id",
            }
            and metadata.get("process_id") == int(process_id)
            and type(metadata.get("creation_time_100ns")) is int
            and metadata["creation_time_100ns"] > 0
            and type(metadata.get("image_name")) is str
            and bool(metadata["image_name"])
            and type(metadata.get("command_role")) is str
            and bool(metadata["command_role"])
            and not metadata["command_role"].startswith("unknown:")
            for process_id, metadata in processes.items()
        )
        and {
            process_id
            for sample in valid_samples
            for process_id in sample["process_ids"]
        }
        == {int(process_id) for process_id in processes}
        and processes.get(str(root_process_id), {}).get("command_role")
        == "python-host"
    )
    sample_memberships = {
        float(sample["elapsed_seconds"]): {
            str(process_id) for process_id in sample["process_ids"]
        }
        for sample in valid_samples
    }
    sample_phases = {
        float(sample["elapsed_seconds"]): sample["phase"]
        for sample in valid_samples
    }
    resource_values = resource_samples if type(resource_samples) is list else []
    fixture_resource_times = [
        float(sample["elapsed_seconds"])
        for sample in resource_values
        if type(sample) is dict
        and sample.get("phase") == "fixture"
        and _is_finite_number(sample.get("elapsed_seconds"))
    ]
    fixture_resource_intervals = [
        later - earlier
        for earlier, later in zip(
            fixture_resource_times,
            fixture_resource_times[1:],
            strict=False,
        )
    ]
    resource_fixture_coverage_valid = bool(
        fixture_times
        and fixture_resource_times
        and fixture_resource_times[0] - min(fixture_times)
        <= _RESOURCE_MAX_BLIND_INTERVAL_SECONDS
        and max(fixture_times) - fixture_resource_times[-1]
        <= _RESOURCE_MAX_BLIND_INTERVAL_SECONDS
        and max(fixture_resource_intervals, default=0.0)
        <= _RESOURCE_MAX_BLIND_INTERVAL_SECONDS
    )
    resource_samples_valid = bool(
        type(resource_samples) is list
        and resource_samples
        and all(
            type(sample) is dict
            and set(sample) == {"elapsed_seconds", "phase", "processes"}
            and _is_finite_number(sample.get("elapsed_seconds"))
            and sample.get("phase") in {"baseline", "fixture"}
            and sample["phase"]
            == sample_phases.get(float(sample["elapsed_seconds"]))
            and type(sample.get("processes")) is dict
            and bool(sample["processes"])
            and set(sample["processes"])
            == sample_memberships.get(float(sample["elapsed_seconds"]))
            and all(
                type(process_id) is str
                and process_id in processes
                and type(values) is dict
                and set(values) == {"handle_count", "thread_count"}
                and type(values.get("handle_count")) is int
                and values["handle_count"] >= 0
                and type(values.get("thread_count")) is int
                and values["thread_count"] > 0
                for process_id, values in sample["processes"].items()
            )
            for sample in resource_samples
        )
        and all(
            earlier["elapsed_seconds"] < later["elapsed_seconds"]
            for earlier, later in zip(
                resource_samples,
                resource_samples[1:],
                strict=False,
            )
        )
        and resource_fixture_coverage_valid
    )
    expected_transitions = []
    previous_process_ids: set[int] = set()
    for sample in valid_samples:
        current_process_ids = set(sample["process_ids"])
        if current_process_ids != previous_process_ids:
            expected_transitions.append(
                {
                    "elapsed_seconds": sample["elapsed_seconds"],
                    "exited_process_ids": sorted(
                        previous_process_ids - current_process_ids
                    ),
                    "joined_process_ids": sorted(
                        current_process_ids - previous_process_ids
                    ),
                }
            )
            previous_process_ids = current_process_ids
    topology_valid = topology_transitions == expected_transitions
    return {
        "all_samples_complete": bool(samples)
        and len(valid_samples) == len(samples)
        and timestamps_strict
        and phase_order_valid
        and fixture_end_valid
        and all(
            type(sample["private_bytes"]) is int
            and type(sample["process_ids"]) is list
            and bool(sample["process_ids"])
            and root_process_id in sample["process_ids"]
            and sample.get("missing_process_ids") == []
            and sample.get("diagnostic_error") is None
            for sample in valid_samples
        )
        and process_metadata_valid
        and resource_samples_valid
        and topology_valid,
        "baseline_sample_count": len(baseline),
        "diagnostic_errors": [
            {
                "elapsed_seconds": sample["elapsed_seconds"],
                "error": sample["diagnostic_error"],
                "phase": sample["phase"],
            }
            for sample in valid_samples
            if sample["diagnostic_error"] is not None
        ],
        "fixture_sample_count": len(fixture),
        "fixture_sample_span_seconds": (
            max(fixture_times) - min(fixture_times)
            if fixture_times
            else None
        ),
        "fixture_ended_at_seconds": fixture_ended_at_seconds,
        "idle_baseline_private_bytes": idle_baseline,
        "incremental_peak_private_bytes": incremental_peak,
        "max_sample_interval_seconds": max_sample_interval_seconds,
        "processes": processes,
        "resource_samples": resource_samples,
        "sampled_peak_private_bytes": sampled_peak,
        "samples": samples,
        "root_process_id": root_process_id,
        "target_sample_interval_seconds": _MEMORY_SAMPLE_SECONDS,
        "topology_transitions": topology_transitions,
    }


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[percentile - 1]


def _sample_summary(values: list[float]) -> dict[str, object]:
    return {
        "count": len(values),
        "p95_ms": _percentile(values, 95),
        "maximum_ms": max(values) if values else None,
    }


def _machine(benchmark_root: Path) -> dict[str, object]:
    memory = _MemoryStatusEx()
    memory.dwLength = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise ctypes.WinError(ctypes.get_last_error())
    power = _SystemPowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)):
        raise ctypes.WinError(ctypes.get_last_error())
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        raise RuntimeError("PowerShell is unavailable for reference-machine evidence")

    def cim(class_name: str, properties: str) -> object:
        raw = _run(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                (
                    f"Get-CimInstance {class_name} | "
                    f"Select-Object {properties} | ConvertTo-Json -Compress"
                ),
            ],
            cwd=REPOSITORY_ROOT,
            timeout=15,
        )
        return json.loads(raw) if raw else None

    operating_system = cim(
        "Win32_OperatingSystem",
        "Caption,Version,BuildNumber,OSArchitecture",
    )
    processor = cim(
        "Win32_Processor",
        "Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors",
    )
    repository_drive = REPOSITORY_ROOT.drive.rstrip(":")
    benchmark_drive = benchmark_root.drive.rstrip(":")
    if benchmark_drive != repository_drive:
        raise RuntimeError("benchmark workspace is not on the repository volume")
    repository_storage_raw = _run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                f"Get-Partition -DriveLetter '{repository_drive}' | Get-Disk | "
                "Select-Object Number,FriendlyName,Model,"
                "@{Name='BusType';Expression={$_.BusType.ToString()}},Size | "
                "ConvertTo-Json -Compress"
            ),
        ],
        cwd=REPOSITORY_ROOT,
        timeout=15,
    )
    repository_storage = (
        json.loads(repository_storage_raw) if repository_storage_raw else None
    )
    on_ac_power = power.ACLineStatus == 1
    reference_profile = bool(
        type(operating_system) is dict
        and operating_system.get("Caption") == _REFERENCE_OS_CAPTION
        and operating_system.get("BuildNumber") == _REFERENCE_OS_BUILD
        and operating_system.get("OSArchitecture")
        == _REFERENCE_OS_ARCHITECTURE
        and type(processor) is dict
        and processor.get("Name") == _REFERENCE_CPU
        and processor.get("NumberOfCores") == _REFERENCE_PHYSICAL_CPUS
        and processor.get("NumberOfLogicalProcessors")
        == _REFERENCE_LOGICAL_CPUS
        and type(repository_storage) is dict
        and repository_storage.get("Model") == _REFERENCE_STORAGE
        and repository_storage.get("BusType") == "NVMe"
        and int(memory.ullTotalPhys) >= _REFERENCE_MEMORY_MIN_BYTES
        and int(memory.ullTotalPhys) <= _REFERENCE_MEMORY_MAX_BYTES
        and on_ac_power
    )
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor_signature": platform.processor(),
        "operating_system": operating_system,
        "processor": processor,
        "repository_drive": repository_drive,
        "repository_storage": repository_storage,
        "system_power_status": {
            "ac_line_status": int(power.ACLineStatus),
            "battery_flag": int(power.BatteryFlag),
            "battery_life_percent": int(power.BatteryLifePercent),
        },
        "on_ac_power": on_ac_power,
        "logical_cpu_count": os.cpu_count(),
        "physical_memory_bytes": int(memory.ullTotalPhys),
        "reference_profile_match": reference_profile,
    }


def _is_finite_number(value: object) -> bool:
    return (
        type(value) in {int, float}
        and math.isfinite(float(value))
        and float(value) >= 0
    )


def _valid_sample(sample: object) -> bool:
    if type(sample) is not dict or set(sample) != {
        "class",
        "event_id",
        "event_result",
        "latency_ms",
        "observed_offset_ms",
        "position",
        "record_state",
        "session_id",
        "sequence",
    }:
        return False
    sample_class = sample["class"]
    if sample_class not in {
        "progress",
        "reliable",
        "terminal_event",
        "terminal_record",
    }:
        return False
    if not _is_finite_number(sample["latency_ms"]):
        return False
    if not _is_finite_number(sample["observed_offset_ms"]):
        return False
    if (
        type(sample["session_id"]) is not str
        or not re.fullmatch(r"[0-9a-f]{32}", sample["session_id"])
    ):
        return False
    sequence = sample["sequence"]
    if sample_class == "terminal_record":
        return (
            sample["event_id"] == "record"
            and sample["position"] is None
            and sequence is None
            and sample["record_state"] == "completed"
            and _successful_result_view(sample["event_result"])
        )
    if sample["record_state"] is not None:
        return False
    if type(sequence) is not int or sequence < 1:
        return False
    if sample_class == "progress":
        return (
            sample["event_id"] == "Progress"
            and sample["event_result"] is None
            and type(sample["position"]) is int
            and 1 <= sample["position"] <= 1_500
        )
    if sample["position"] is not None:
        return False
    if sample_class == "terminal_event":
        return (
            sample["event_id"] == "Terminal"
            and _successful_core_result(sample["event_result"])
        )
    return bool(
        (
            type(sample["event_id"]) is str
            and re.fullmatch(r"task-[0-3]-item-[0-5][0-9]-[0-2]", sample["event_id"])
            and sample["event_result"] == "succeeded"
        )
        or (
            sample["event_id"] == "StateChanged"
            and type(sample["event_result"]) is dict
            and set(sample["event_result"]) == {"state"}
            and sample["event_result"]["state"]
            in {"pending", "running", "completed"}
        )
    )


def _successful_result_items(items: object) -> bool:
    return (
        type(items) is list
        and all(
            type(item) is list
            and len(item) == 2
            and type(item[0]) is str
            and item[1] == "succeeded"
            for item in items
        )
    )


def _successful_core_result(value: object) -> bool:
    return bool(
        type(value) is dict
        and set(value)
        == {
            "audit",
            "bytes_done",
            "bytes_total",
            "canceled",
            "disposition",
            "error",
            "items",
            "phase_count",
            "recording",
            "status",
        }
        and value.get("status") == "completed"
        and value.get("recording") == "ok"
        and value.get("audit") == "ok"
        and value.get("disposition") == "ran"
        and value.get("canceled") is False
        and value.get("phase_count") == 0
        and value.get("bytes_done") == 1_500
        and value.get("bytes_total") == 1_500
        and value.get("error") is None
        and _successful_result_items(value.get("items"))
    )


def _successful_result_view(value: object) -> bool:
    return bool(
        type(value) is dict
        and set(value)
        == {
            "audit",
            "bytes_done",
            "bytes_total",
            "canceled",
            "disposition",
            "error",
            "filesystem",
            "headline",
            "integrity",
            "items",
            "phase_count",
            "recording",
        }
        and value.get("headline") == "success"
        and value.get("filesystem") == "completed"
        and value.get("integrity") == "not-run"
        and value.get("recording") == "ok"
        and value.get("audit") == "ok"
        and value.get("disposition") == "ran"
        and value.get("canceled") is False
        and value.get("phase_count") == 0
        and value.get("bytes_done") == 1_500
        and value.get("bytes_total") == 1_500
        and value.get("error") is None
        and _successful_result_items(value.get("items"))
    )


def _expected_reliable_ids(task_index: int) -> list[str]:
    pattern = (3, 3, 2, 2)
    expected = []
    for second in range(60):
        count = pattern[(task_index + second) % 4]
        ticks = sorted(
            ((item_index + 1) * 25) // (count + 1)
            for item_index in range(count)
        )
        expected.extend(
            f"task-{task_index}-item-{second:02d}-{item_index}"
            for item_index, _ in enumerate(ticks)
        )
    return expected


def _expected_reliable_offsets(task_index: int) -> list[float]:
    pattern = (3, 3, 2, 2)
    expected = []
    for second in range(60):
        count = pattern[(task_index + second) % 4]
        ticks = sorted(
            ((item_index + 1) * 25) // (count + 1)
            for item_index in range(count)
        )
        expected.extend(
            (second * 25 + tick) * 0.04 for tick in ticks
        )
    return expected


def _valid_emission_offsets(
    observed: object,
    expected: list[float],
) -> bool:
    return bool(
        type(observed) is list
        and len(observed) == len(expected)
        and all(
            type(value) in {int, float}
            and math.isfinite(float(value))
            and float(value) >= 0
            for value in observed
        )
        and all(
            earlier <= later
            for earlier, later in zip(observed, observed[1:], strict=False)
        )
        and all(
            -_PRODUCER_EARLY_TOLERANCE_SECONDS
            <= float(actual) - scheduled
            <= _PRODUCER_MAX_LATENESS_SECONDS
            for actual, scheduled in zip(observed, expected, strict=True)
        )
    )


def _emission_delay_summary(
    observed: object,
    expected: list[float],
) -> dict[str, object]:
    if type(observed) is not list or len(observed) != len(expected):
        return {"count": 0, "p95_ms": None, "maximum_ms": None}
    delays = [
        max(0.0, (float(actual) - scheduled) * 1_000)
        for actual, scheduled in zip(observed, expected, strict=True)
        if type(actual) in {int, float}
        and math.isfinite(float(actual))
        and float(actual) >= 0
    ]
    if len(delays) != len(expected):
        return {"count": len(delays), "p95_ms": None, "maximum_ms": None}
    return {
        "count": len(delays),
        "p95_ms": _percentile(delays, 95),
        "maximum_ms": max(delays) if delays else None,
    }


def _summarize(
    evidence: dict[str, object],
    *,
    benchmark_root: Path,
    commit: str,
    status: tuple[str, ...],
    job_memory: dict[str, object],
) -> dict[str, object]:
    raw_samples = evidence.get("samples")
    samples = raw_samples if type(raw_samples) is list else []
    samples_valid = bool(samples) and all(_valid_sample(sample) for sample in samples)
    progress = [
        float(sample["latency_ms"])
        for sample in samples
        if type(sample) is dict and sample.get("class") == "progress"
        and _is_finite_number(sample.get("latency_ms"))
    ]
    reliable = [
        float(sample["latency_ms"])
        for sample in samples
        if type(sample) is dict
        and sample.get("class") in {
            "reliable",
            "terminal_event",
            "terminal_record",
        }
        and _is_finite_number(sample.get("latency_ms"))
    ]
    browser_value = evidence.get("browser")
    browser = browser_value if type(browser_value) is dict else {}
    terminal_event_samples = [
        sample
        for sample in samples
        if type(sample) is dict and sample.get("class") == "terminal_event"
    ]
    terminal_record_samples = [
        sample
        for sample in samples
        if type(sample) is dict and sample.get("class") == "terminal_record"
    ]
    session_ids_value = browser.get("session_ids")
    session_ids = session_ids_value if type(session_ids_value) is list else []
    sessions_valid = (
        len(session_ids) == 4
        and all(
            type(session_id) is str
            and re.fullmatch(r"[0-9a-f]{32}", session_id)
            for session_id in session_ids
        )
        and len(set(session_ids)) == 4
    )
    session_evidence = []
    for task_index, session_id in enumerate(
        session_ids if sessions_valid and samples_valid else []
    ):
        session_samples = [
            sample for sample in samples if sample.get("session_id") == session_id
        ]
        reliable_samples = [
            sample
            for sample in session_samples
            if sample["class"] == "reliable"
            and sample["event_id"].startswith("task-")
        ]
        state_samples = [
            sample
            for sample in session_samples
            if sample["class"] == "reliable"
            and sample["event_id"] == "StateChanged"
        ]
        progress_samples = [
            sample for sample in session_samples if sample["class"] == "progress"
        ]
        terminal_events = [
            sample
            for sample in session_samples
            if sample["class"] == "terminal_event"
        ]
        terminal_records = [
            sample
            for sample in session_samples
            if sample["class"] == "terminal_record"
        ]
        reliable_ids = [sample["event_id"] for sample in reliable_samples]
        reliable_sequences = [sample["sequence"] for sample in reliable_samples]
        progress_positions = [sample["position"] for sample in progress_samples]
        progress_offsets = [
            float(sample["observed_offset_ms"])
            for sample in progress_samples
        ]
        progress_sequences = [sample["sequence"] for sample in progress_samples]
        event_samples = [
            sample
            for sample in session_samples
            if sample["class"] != "terminal_record"
        ]
        event_sequences = [sample["sequence"] for sample in event_samples]
        observed_offsets = [
            float(sample["observed_offset_ms"])
            for sample in session_samples
        ]
        state_values = [
            sample["event_result"]["state"] for sample in state_samples
        ]
        terminal_event_ids = (
            [item[0] for item in terminal_events[0]["event_result"]["items"]]
            if terminal_events
            else []
        )
        terminal_record_ids = (
            [item[0] for item in terminal_records[0]["event_result"]["items"]]
            if terminal_records
            else []
        )
        valid = bool(
            reliable_ids == _expected_reliable_ids(task_index)
            and reliable_sequences == sorted(set(reliable_sequences))
            and len(progress_positions) >= 30
            and progress_positions == sorted(set(progress_positions))
            and progress_positions[-1] == 1_500
            and progress_offsets[0] <= 2_000
            and progress_offsets[-1] >= 59_000
            and max(
                later - earlier
                for earlier, later in zip(
                    progress_offsets,
                    progress_offsets[1:],
                    strict=False,
                )
            ) <= _PROGRESS_MAX_MS
            and progress_sequences == sorted(set(progress_sequences))
            and event_sequences == sorted(set(event_sequences))
            and observed_offsets == sorted(observed_offsets)
            and state_values == ["pending", "running", "completed"]
            and [
                (sample["event_id"], sample["event_result"])
                for sample in event_samples[:2]
            ]
            == [
                ("StateChanged", {"state": "pending"}),
                ("StateChanged", {"state": "running"}),
            ]
            and event_samples[-2]["event_id"] == "StateChanged"
            and event_samples[-2]["event_result"] == {"state": "completed"}
            and event_samples[-1]["class"] == "terminal_event"
            and len(terminal_events) == 1
            and len(terminal_records) == 1
            and terminal_event_ids == reliable_ids
            and terminal_record_ids == reliable_ids
            and [sample["class"] for sample in session_samples[-3:]]
            == ["reliable", "terminal_event", "terminal_record"]
        )
        session_evidence.append(
            {
                "session_id": session_id,
                "reliable_count": len(reliable_samples),
                "progress_sample_count": len(progress_samples),
                "final_progress": progress_positions[-1] if progress_positions else None,
                "terminal_event_count": len(terminal_events),
                "terminal_record_count": len(terminal_records),
                "valid": valid,
            }
        )
    producers = [evidence.get(f"producer_task_{index}") for index in range(4)]
    producer_timing = [
        {
            "task_index": index,
            "progress_schedule_delay": _emission_delay_summary(
                producer.get("progress_emission_offsets_seconds"),
                [tick * 0.04 for tick in range(1_500)],
            ) if type(producer) is dict else {},
            "reliable_schedule_delay": _emission_delay_summary(
                producer.get("reliable_emission_offsets_seconds"),
                _expected_reliable_offsets(index),
            ) if type(producer) is dict else {},
        }
        for index, producer in enumerate(producers)
    ]
    producer_counts_exact = bool(
        all(
            type(producer) is dict
            and producer.get("progress_emissions") == 1_500
            and _valid_emission_offsets(
                producer.get("progress_emission_offsets_seconds"),
                [tick * 0.04 for tick in range(1_500)],
            )
            and producer.get("reliable_emissions") == 150
            and producer.get("reliable_by_second")
            == [
                (3, 3, 2, 2)[(index + second) % 4]
                for second in range(60)
            ]
            and _valid_emission_offsets(
                producer.get("reliable_emission_offsets_seconds"),
                _expected_reliable_offsets(index),
            )
            and _is_finite_number(producer.get("elapsed_seconds"))
            and _is_finite_number(
                producer.get("first_emission_offset_seconds")
            )
            and _is_finite_number(
                producer.get("last_emission_offset_seconds")
            )
            and producer["first_emission_offset_seconds"] <= 0.25
            and 59.8 <= producer["last_emission_offset_seconds"] <= 60.5
            and producer["elapsed_seconds"]
            >= producer["last_emission_offset_seconds"]
            and producer["elapsed_seconds"] <= 61.0
            for index, producer in enumerate(producers)
        )
    )
    first_offsets = [
        float(producer["first_emission_offset_seconds"])
        for producer in producers
        if type(producer) is dict
        and _is_finite_number(producer.get("first_emission_offset_seconds"))
    ]
    last_offsets = [
        float(producer["last_emission_offset_seconds"])
        for producer in producers
        if type(producer) is dict
        and _is_finite_number(producer.get("last_emission_offset_seconds"))
    ]
    emission_window_seconds = (
        max(last_offsets) - min(first_offsets)
        if len(first_offsets) == 4 and len(last_offsets) == 4
        else None
    )
    aggregate_progress_rate = (
        6_000 / emission_window_seconds
        if emission_window_seconds is not None and emission_window_seconds > 0
        else None
    )
    aggregate_reliable_rate = (
        600 / emission_window_seconds
        if emission_window_seconds is not None and emission_window_seconds > 0
        else None
    )
    allowed_status = {"?? M1_SHELL.md", "?? S0-S3_REALIGNMENT.md"}
    archive_scope_clean = set(status) <= allowed_status
    progress_summary = _sample_summary(progress)
    reliable_summary = _sample_summary(reliable)
    gaps = browser.get("gap_events")
    terminal_event_latencies = browser.get("terminal_event_latencies_ms")
    terminal_record_latencies = browser.get("terminal_record_latencies_ms")
    terminal_arrays_match = bool(
        samples_valid
        and type(terminal_event_latencies) is list
        and type(terminal_record_latencies) is list
        and terminal_event_latencies
        == [sample["latency_ms"] for sample in terminal_event_samples]
        and terminal_record_latencies
        == [sample["latency_ms"] for sample in terminal_record_samples]
    )
    raw_job_samples = job_memory.get("samples")
    recomputed_job_memory = (
        _job_memory_result(
            raw_job_samples,
            fixture_ended_at_seconds=job_memory.get(
                "fixture_ended_at_seconds"
            ),
            processes=job_memory.get("processes", {}),
            resource_samples=job_memory.get("resource_samples", []),
            root_process_id=job_memory.get("root_process_id", -1),
            topology_transitions=job_memory.get(
                "topology_transitions",
                [],
            ),
        )
        if type(raw_job_samples) is list
        and type(job_memory.get("root_process_id")) is int
        else {}
    )
    memory_peak = job_memory.get("incremental_peak_private_bytes")
    memory_evidence_complete = bool(
        job_memory == recomputed_job_memory
        and job_memory.get("all_samples_complete") is True
        and type(job_memory.get("root_process_id")) is int
        and job_memory["root_process_id"] > 0
        and type(job_memory.get("baseline_sample_count")) is int
        and job_memory["baseline_sample_count"] >= 30
        and type(job_memory.get("fixture_sample_count")) is int
        and job_memory["fixture_sample_count"] >= 2_500
        and _is_finite_number(job_memory.get("fixture_sample_span_seconds"))
        and job_memory["fixture_sample_span_seconds"] >= 59.8
        and type(memory_peak) is int
        and job_memory["max_sample_interval_seconds"]
        <= _MEMORY_MAX_BLIND_INTERVAL_SECONDS
    )
    production_names = [
        "close_task",
        "next_events",
        "pick_folder",
        "readiness_echo",
        "release_terminal_session",
        "shell_ready",
        "start_plan",
    ]
    combined_names = sorted(
        [*production_names, "benchmark_report", "benchmark_start"]
    )
    runtime_value = evidence.get("runtime")
    runtime = runtime_value if type(runtime_value) is dict else {}
    packages_value = runtime.get("packages")
    packages = packages_value if type(packages_value) is dict else {}
    runtime_profile_match = bool(
        type(runtime.get("python")) is str
        and runtime["python"].startswith(_REFERENCE_PYTHON_PREFIX)
        and runtime.get("sqlite") == _REFERENCE_SQLITE
        and type(packages.get("namisync")) is str
        and type(packages.get("bottle")) is str
        and bool(packages["bottle"])
        and packages.get("pywebview") == _REFERENCE_PYWEBVIEW
        and packages.get("pythonnet") == _REFERENCE_PYTHONNET
        and type(evidence.get("webview2")) is str
        and bool(evidence["webview2"])
        and type(evidence.get("clr_runtime")) is str
        and "Runtime: .NET Framework" in evidence["clr_runtime"]
    )
    machine = _machine(benchmark_root)
    event_passed = bool(
        samples_valid
        and sessions_valid
        and {sample["session_id"] for sample in samples} == set(session_ids)
        and len(session_evidence) == 4
        and all(session["valid"] for session in session_evidence)
        and len(terminal_event_samples) == 4
        and len(terminal_record_samples) == 4
        and terminal_arrays_match
        and browser.get("terminal_record_count") == 4
        and browser.get("task_count") == 4
        and "failure" not in browser
        and gaps == []
        and browser.get("progress_monotonic") is True
        and evidence.get("browser_presented") is True
        and evidence.get("complete") is True
        and len(progress) >= 120
        and reliable_summary["p95_ms"] <= _RELIABLE_P95_MAX_MS
        and reliable_summary["maximum_ms"] <= _RELIABLE_MAX_MS
        and progress_summary["p95_ms"] <= _PROGRESS_P95_MAX_MS
        and progress_summary["maximum_ms"] <= _PROGRESS_MAX_MS
        and producer_counts_exact
        and aggregate_progress_rate is not None
        and aggregate_progress_rate >= 100.0
        and aggregate_reliable_rate is not None
        and aggregate_reliable_rate >= 10.0
        and evidence.get("startup_errors") == []
        and evidence.get("exit_code") == 0
        and evidence.get("production_command_names") == production_names
        and evidence.get("combined_command_names") == combined_names
        and runtime_profile_match
        and machine.get("reference_profile_match") is True
        and archive_scope_clean
    )
    return {
        "schema_version": 1,
        "gate": "SH-G-8 event limb / BR-G-42 bridge event envelope",
        "passed": event_passed,
        "event_passed": event_passed,
        "sh_g_8_acceptance": "incomplete-without-custody",
        "tested_commit": commit,
        "worktree_status": list(status),
        "archive_scope_clean": archive_scope_clean,
        "machine": machine,
        "runtime": runtime,
        "runtime_profile_match": runtime_profile_match,
        "clr_runtime": evidence.get("clr_runtime"),
        "webview2": evidence.get("webview2"),
        "fixture": {
            "seed": 0,
            "wall_seconds": 60,
            "task_count": 4,
            "progress_emissions": 6_000,
            "reliable_emissions": 600,
        },
        "producers": producers,
        "producer_timing": producer_timing,
        "emission_window_seconds": emission_window_seconds,
        "aggregate_progress_rate_per_second": aggregate_progress_rate,
        "aggregate_reliable_rate_per_second": aggregate_reliable_rate,
        "progress": progress_summary,
        "reliable_and_terminal": reliable_summary,
        "sessions": session_evidence,
        "gaps": gaps,
        "progress_monotonic": browser.get("progress_monotonic"),
        "memory": {
            "job_private_memory": job_memory,
            "whole_runtime_diagnostics_complete": memory_evidence_complete,
            "whole_runtime_acceptance": "not-defined",
        },
        "raw_samples": samples,
        "startup_errors": evidence.get("startup_errors"),
        "browser_failure": browser.get("failure"),
        "browser_report": browser,
    }


def _failure_result(
    error: Exception,
    *,
    commit: str | None,
    status: tuple[str, ...],
    evidence: dict[str, object],
    job_memory: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "gate": "SH-G-8 event limb / BR-G-42 bridge event envelope",
        "passed": False,
        "event_passed": False,
        "sh_g_8_acceptance": "incomplete-without-custody",
        "tested_commit": commit,
        "worktree_status": list(status),
        "failure": {
            "exception_type": type(error).__name__,
            "message": str(error),
        },
        "memory": {
            "job_private_memory": job_memory,
            "whole_runtime_diagnostics_complete": False,
            "whole_runtime_acceptance": "not-defined",
        },
        "partial_evidence": evidence,
    }


def main() -> int:
    arguments = _arguments()
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    commit: str | None = None
    status: tuple[str, ...] = ()
    evidence: dict[str, object] = {}
    job_memory: dict[str, object] = {}
    try:
        with tempfile.TemporaryDirectory(
            prefix=".namisync-bridge-benchmark-",
            dir=REPOSITORY_ROOT.parent,
        ) as raw:
            root = Path(raw).resolve()
            wheel, commit, status = _build_archived_wheel(root)
            python = _install_wheel(root, wheel)
            index = _stage_page(root, python, root / "source")
            child = (
                root
                / "source"
                / "tests"
                / "interfaces"
                / "web"
                / _CHILD.name
            )
            data_dir = root / "data"
            evidence_path = root / "child-evidence.json"
            begin_marker = data_dir / "benchmark.begin"
            ready_marker = data_dir / "benchmark.ready"
            report_marker = data_dir / "benchmark.report"
            failure_marker = data_dir / "benchmark.failure"
            presented_marker = data_dir / "benchmark.presented"
            title = f"NamiSync bridge benchmark {uuid4().hex}"
            mutex = rf"Local\NamiSync.BridgeBenchmark.{uuid4().hex}"
            deadline = scenario_deadline(110)
            process = _start_direct_job_process(
                [
                    str(python),
                    str(child),
                    "--data-dir",
                    str(data_dir),
                    "--index",
                    str(index),
                    "--mutex",
                    mutex,
                    "--title",
                    title,
                    "--output",
                    str(evidence_path),
                ],
                cwd=root,
                environment=_clean_python_environment(),
                deadline=deadline,
            )
            sampler = _JobPrivateMemorySampler(process)
            try:
                window = wait_for_window(process, title, deadline=deadline)
                sampler.wait_until_ready(ready_marker, deadline)
                sampler.take_idle_baseline(deadline)
                browser_succeeded = sampler.run_until_browser_report(
                    report_marker,
                    failure_marker,
                    begin_marker,
                    deadline,
                )
                if browser_succeeded:
                    _wait_for_browser_presentation(
                        presented_marker,
                        failure_marker,
                        process,
                        deadline,
                    )
                close_window(window)
                completed = wait_for_process(process, deadline=deadline)
                evidence = _read_evidence(evidence_path)
                if completed.returncode != 0:
                    raise RuntimeError(completed.stdout + completed.stderr)
                if evidence.get("complete") is not True:
                    raise RuntimeError("benchmark child did not publish final evidence")
                evidence = _attach_streamed_evidence(
                    evidence,
                    evidence_path,
                )
            finally:
                try:
                    job_memory = sampler.result()
                    latest_evidence = _read_evidence(evidence_path)
                    if latest_evidence:
                        evidence = (
                            _attach_streamed_evidence(
                                latest_evidence,
                                evidence_path,
                            )
                            if latest_evidence.get("complete") is True
                            else latest_evidence
                        )
                finally:
                    if process.poll() is None:
                        terminate_process_tree(process, deadline=deadline)
                    else:
                        process.close_job()
            result = _summarize(
                evidence,
                benchmark_root=root,
                commit=commit,
                status=status,
                job_memory=job_memory,
            )
    except Exception as error:
        result = _failure_result(
            error,
            commit=commit,
            status=status,
            evidence=evidence,
            job_memory=job_memory,
        )
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_keys = ("passed", "progress", "reliable_and_terminal", "memory")
    print(
        json.dumps(
            {key: result.get(key) for key in summary_keys},
            indent=2,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
