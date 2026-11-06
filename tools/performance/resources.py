"""SH-G-15 resource collector for the unchanged portable GUI package.

Each run is one fresh process with an isolated ``--data-dir`` inside a
kill-on-close Job. A 1 s passive sampler records every Job member except the
launch wrapper. Workload runs set only WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS
to expose a loopback DevTools port and drive the page with trusted CDP input;
startup acceptance runs set nothing. PERFORMANCE owns the method;
``validate_resources`` owns the verdict. This module never judges budgets.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from ctypes import wintypes
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
WEB_TESTS = REPOSITORY / "tests" / "interfaces" / "web"
if str(WEB_TESTS) not in sys.path:
    sys.path.insert(0, str(WEB_TESTS))

from _headed_native import (  # noqa: E402
    _find_window,
    clean_child_environment,
    close_window,
    scenario_deadline,
    start_headed_process,
)

from tools.performance import _cdp  # noqa: E402
from tools.performance.bridge_event import _process_metadata  # noqa: E402

INTERVAL = 1.0
EMERGENCY_PRIVATE_BYTES = 8 * 1024**3
FIXED_MTIME = 1_577_836_800  # 2020-01-01T00:00:00Z
TRASH = ".synctrash"
SOAK_CYCLES = 100
SOAK_CHANGED = 10

# Frozen schedule: name -> (profile, parameters). Order is collection order.
SCHEDULE: dict[str, tuple[str, dict]] = {
    **{f"startup-{i:02}": ("startup", {"cdp": False}) for i in (1, 2, 3)},
    **{f"startup-cdp-{i:02}": ("startup", {"cdp": True}) for i in (1, 2, 3)},
    **{f"soak-{i:02}": ("soak", {}) for i in (1, 2, 3)},
    **{f"scale-{n // 1000}k-{i:02}": ("scale", {"files": n}) for i in (1, 2, 3) for n in (10_000, 100_000)},
    "payload-01": ("payload", {"groups": ["1x4GiB", "64x4MiB"]}),
    "idle-open-01": ("idle_open", {"files": 10_000, "minutes": 60}),
}


# ---------------------------------------------------------------- process reads
class _Counters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
            "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
            "PrivateUsage")]


_KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
_PSAPI = ctypes.WinDLL("psapi", use_last_error=True)
_USER = ctypes.WinDLL("user32", use_last_error=True)
_KERNEL.OpenProcess.restype = wintypes.HANDLE
_KERNEL.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_KERNEL.CloseHandle.argtypes = (wintypes.HANDLE,)
_KERNEL.GetProcessHandleCount.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
_KERNEL.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
_PSAPI.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.POINTER(_Counters), wintypes.DWORD)
_USER.GetGuiResources.argtypes = (wintypes.HANDLE, wintypes.DWORD)


def _filetime(value: wintypes.FILETIME) -> int:
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


def read_process(pid: int) -> dict | None:
    handle = _KERNEL.OpenProcess(0x1000 | 0x0010, False, pid)
    if not handle:
        return None
    try:
        counters = _Counters()
        counters.cb = ctypes.sizeof(counters)
        handles = wintypes.DWORD()
        times = [wintypes.FILETIME() for _ in range(4)]
        if not (_PSAPI.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
                and _KERNEL.GetProcessHandleCount(handle, ctypes.byref(handles))
                and _KERNEL.GetProcessTimes(handle, *map(ctypes.byref, times))):
            return None
        return {"created": _filetime(times[0]), "private": counters.PrivateUsage, "ws": counters.WorkingSetSize,
                "handles": handles.value, "cpu_100ns": _filetime(times[2]) + _filetime(times[3]),
                "gdi": _USER.GetGuiResources(handle, 0), "user": _USER.GetGuiResources(handle, 1)}
    finally:
        _KERNEL.CloseHandle(handle)


def digest(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def tree_hashes(root: Path, *, exclude_top: str | None = None) -> dict[str, str]:
    root = Path(root)
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if exclude_top is not None and relative.parts[0] == exclude_top:
            continue
        if path.lstat().st_file_attributes & 0x400:
            raise RuntimeError(f"reparse point in fixture: {path}")
        if path.is_file():
            result[relative.as_posix()] = digest(path)
    return result


def tree_metadata(root: Path) -> dict[str, list[int]]:
    return {p.relative_to(root).as_posix(): [p.stat().st_size, p.stat().st_mtime_ns]
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


# ---------------------------------------------------------------- one process
class Run:
    def __init__(self, out: Path, name: str, exe: Path, *, cdp: bool) -> None:
        self.dir = out / "runs" / name
        self.dir.mkdir(parents=True)  # refuses to replace any run
        self.profile = out / "profiles" / name
        self.exe = exe
        self.cdp = cdp
        self._events = (self.dir / "events.jsonl").open("x", encoding="utf-8")
        self._samples = (self.dir / "samples.jsonl").open("x", encoding="utf-8")
        self._roles: dict[tuple[int, int], str] = {}
        self._stop = threading.Event()
        self.failure: str | None = None
        self.phase = "launch"
        self.session: _cdp.Session | None = None
        self.process = None
        self.started = 0.0

    def t(self) -> float:
        return time.perf_counter() - self.started

    def event(self, kind: str, **extra: object) -> None:
        record = {"t": round(self.t(), 3), "kind": kind, "phase": self.phase, **extra}
        self._events.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._events.flush()
        print(json.dumps(record, ensure_ascii=False), flush=True)

    # sampler
    def _role(self, pid: int, created: int) -> str | None:
        key = (pid, created)
        if key not in self._roles:
            meta = _process_metadata(pid, root_process_id=-1)
            if meta is None:
                return None
            self._roles[key] = "host" if meta["image_name"].casefold() == self.exe.name.casefold() else meta["command_role"]
        return self._roles[key]

    def _sample(self) -> None:
        began = time.perf_counter()
        pids = sorted(self.process.process_ids() - {self.process.pid})
        processes, complete = [], bool(pids)
        for pid in pids:
            info = read_process(pid)
            role = None if info is None else self._role(pid, info["created"])
            if info is None or role is None:
                complete = False
                continue
            processes.append({"pid": pid, "role": role, **info})
        complete = complete and sum(p["role"] == "host" for p in processes) == 1
        total = sum(p["private"] for p in processes)
        self._samples.write(json.dumps({
            "t": round(began - self.started, 3), "obs": round(time.perf_counter() - began, 4), "phase": self.phase,
            "complete": complete, "private": total, "procs": processes}) + "\n")
        self._samples.flush()
        if complete and total > EMERGENCY_PRIVATE_BYTES:
            self.failure = f"emergency stop: whole-Job private bytes {total}"

    def _sampler(self) -> None:
        deadline = time.perf_counter()
        while not self._stop.is_set():
            try:
                self._sample()
            except Exception as error:
                self.failure = f"sampler failure: {type(error).__name__}: {error}"
                return
            deadline += INTERVAL
            self._stop.wait(max(0.0, deadline - time.perf_counter()))

    # lifecycle
    def launch(self) -> None:
        self.profile.mkdir(parents=True)
        environment = clean_child_environment()
        environment.pop("PYTHONHOME", None)
        environment.pop("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", None)
        if self.cdp:
            environment["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
                "--disable-features=ElasticOverscroll --remote-debugging-port=0")
        self._log = (self.dir / "app.log").open("xb")
        self.started = time.perf_counter()
        self.process = start_headed_process(
            [self.exe, "--data-dir", self.profile], cwd=self.exe.parent, environment=environment,
            deadline=scenario_deadline(4 * 3600), stdout=self._log, stderr=self._log)
        self._thread = threading.Thread(target=self._sampler, daemon=True)
        self._thread.start()
        self.event("launched", cdp=self.cdp)
        if self.cdp:
            self.session, endpoint = _cdp.connect_page(self.profile, self.process.process_ids, timeout=90)
            self.event("devtools-attached", **endpoint)
            self.wait_for(lambda: self.js("!!document.getElementById('setup-source-path')"), 90, "setup ready")
            self.event("ready")

    def window(self) -> int | None:
        return _find_window("NamiSync", frozenset(), process_ids=self.process.process_ids() - {self.process.pid})

    def close(self) -> dict:
        self.set_phase("close")
        if self.session is not None:
            self.session.close()
        handle = self.window()
        result: dict[str, object] = {"window_found": bool(handle)}
        if handle:
            close_window(handle)
        end = time.perf_counter() + 120
        while self.process.poll() is None and time.perf_counter() < end:
            time.sleep(0.1)
        grace = time.perf_counter() + 10
        while self.process.process_ids() - {self.process.pid} and time.perf_counter() < grace:
            time.sleep(0.1)
        result["exit_code"] = self.process.poll()
        result["remaining_pids"] = sorted(self.process.process_ids() - {self.process.pid})
        self._stop.set()
        self._thread.join(10)
        self.process.close_job()
        self.event("closed", **result)
        self._events.close()
        self._samples.close()
        self._log.close()
        return result

    # observation
    def set_phase(self, phase: str) -> None:
        self.phase = phase
        self.event("phase")

    def check(self) -> None:
        if self.failure:
            raise RuntimeError(self.failure)
        if self.process.poll() is not None:
            raise RuntimeError(f"application exited unexpectedly with {self.process.poll()}")

    def window_idle(self, name: str, seconds: float) -> None:
        """A hands-off statistic window: no CDP traffic, only passive sampling."""

        self.set_phase(name)
        start = self.t()
        end = time.perf_counter() + seconds
        while time.perf_counter() < end:
            self.check()
            time.sleep(min(0.5, max(0.0, end - time.perf_counter())))
        self.event("window", name=name, start=round(start, 3), end=round(self.t(), 3))

    def wait_for(self, predicate, timeout: float, what: str):
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            self.check()
            value = predicate()
            if value:
                return value
            time.sleep(0.5)
        raise TimeoutError(f"timed out waiting for {what}")

    def js(self, expression: str):
        return self.session.evaluate(expression)

    def screenshot(self, name: str) -> None:
        data = self.session.call("Page.captureScreenshot", format="png")["data"]
        (self.dir / f"{name}.png").write_bytes(base64.b64decode(data))

    def click(self, element_js: str, what: str) -> None:
        point = self.js(f"""(() => {{ const el = {element_js};
            if (!el || el.disabled || el.hidden) return null;
            el.scrollIntoView({{block: 'center', inline: 'center'}});
            const r = el.getBoundingClientRect();
            return r.width && r.height ? [r.left + r.width / 2, r.top + r.height / 2] : null; }})()""")
        if point is None:
            raise RuntimeError(f"cannot click {what}: missing, disabled or hidden")
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            self.session.call("Input.dispatchMouseEvent", type=kind, x=point[0], y=point[1], button="left", clickCount=1)
        self.event("click", target=what)

    def type_path(self, input_id: str, text: str) -> None:
        self.js(f"(() => {{ const el = document.getElementById('{input_id}'); el.focus(); el.select(); }})()")
        self.session.call("Input.insertText", text=text)
        for kind in ("keyDown", "keyUp"):
            self.session.call("Input.dispatchKeyEvent", type=kind, key="Enter", code="Enter",
                              windowsVirtualKeyCode=13, nativeVirtualKeyCode=13)
        actual = self.js(f"document.getElementById('{input_id}').value")
        if actual != text:
            raise RuntimeError(f"path readback mismatch for {input_id}: {actual!r}")
        self.event("typed", field=input_id, value=text)


def _button(text: str) -> str:
    return (f"[...document.querySelectorAll('button')].find(b => b.textContent.trim() === {json.dumps(text)}"
            " && !b.hidden && b.offsetParent !== null)")


_CARD = "document.querySelector('.nami-task-rail__items .nami-task-card[aria-current=\"page\"]')"
_STATUS = f"(() => {{ const c = {_CARD}; return c ? [c.dataset.status, c.innerText.split('\\n').slice(0, 2)] : null; }})()"
_FAILED = {"error", "degraded", "canceled", "attention", "unavailable"}


def sync_task(run: Run, source: Path, target: Path, *, label: str, new_task: bool,
              destructive: int, plan_timeout: float, execute_timeout: float, open_seconds: float = 0.0) -> None:
    """Setup -> Create plan -> Execute (verify on) -> completed. Leaves the task open."""

    run.set_phase(f"{label}-setup")
    if new_task:
        run.click("document.querySelector('.nami-task-rail__create')", "New task")
        run.wait_for(lambda: run.js("!!document.getElementById('setup-source-path')"), 30, "setup")
    toggle = "document.querySelector('input[data-option=verify_after_execute]')"
    if not run.js(f"{toggle}.checked"):
        run.click(toggle, "Verify execution")
    if not run.js(f"{toggle}.checked"):
        raise RuntimeError("Verify execution did not turn on")
    run.type_path("setup-source-path", str(source))
    run.type_path("setup-target-path", str(target))
    run.wait_for(lambda: run.js(f"(() => {{ const b = {_button('Create plan')}; return b && !b.disabled; }})()"),
                 60, "Create plan enabled")
    run.set_phase(f"{label}-plan")
    run.click(_button("Create plan"), "Create plan")
    # While planning, the card can transiently report status "completed" with title "Completed";
    # only "plan" or an explicit failure state ends the wait.
    status = run.wait_for(lambda: (s := run.js(_STATUS)) and s[0] in {"plan"} | _FAILED and s, plan_timeout, "plan")
    run.event("plan-status", status=status)
    if status[0] != "plan":
        raise RuntimeError(f"plan did not become ready: {status}")
    if open_seconds:
        run.window_idle(f"{label}-plan-open", open_seconds)
    run.set_phase(f"{label}-execute")
    run.click(_button("Execute"), "Execute")
    run.wait_for(lambda: run.js("document.getElementById('execution-confirmation').open")
                 or run.js(_STATUS)[0] != "plan", 30, "execution start or confirmation")
    if run.js("document.getElementById('execution-confirmation').open"):
        count = run.js("document.getElementById('execution-confirmation-count').innerText")
        run.event("confirmation", text=count)
        if count != f"{destructive} selected destructive operations":
            raise RuntimeError(f"unexpected destructive confirmation: {count!r}")
        run.click("document.querySelector('#execution-confirmation [data-confirm-execution]')", "Confirm and execute")
    elif destructive:
        raise RuntimeError("expected destructive confirmation did not appear")
    status = run.wait_for(lambda: (s := run.js(_STATUS)) and (s[0] in _FAILED or s[1][:1] == ["Execution completed"]) and s,
                          execute_timeout, "terminal")
    run.event("terminal-status", status=status)
    if status[0] != "completed" or status[1][0] != "Execution completed":
        run.screenshot(f"{label}-terminal")
        raise RuntimeError(f"execution did not complete cleanly: {status}")


def close_task(run: Run, label: str) -> None:
    run.set_phase(f"{label}-close-task")
    run.click("document.querySelector('.nami-task-rail__close')", "Close task")
    run.wait_for(lambda: run.js(f"!{_CARD}"), 60, "task closed")


def check_mirror(run: Run, source: Path, target: Path, *, trash_files: int, label: str) -> None:
    """Outside statistic windows: exact mirror plus expected preserved-version count."""

    started = time.perf_counter()
    source_hashes = tree_hashes(source)
    target_hashes = tree_hashes(target, exclude_top=TRASH)
    trash = Path(target) / TRASH
    trash_count = sum(1 for p in trash.rglob("*") if p.is_file()) if trash.exists() else 0
    ok = source_hashes == target_hashes and trash_count == trash_files
    run.event("mirror-check", label=label, ok=ok, files=len(source_hashes), trash_files=trash_count,
              expected_trash_files=trash_files, seconds=round(time.perf_counter() - started, 3))
    if not ok:
        raise RuntimeError(f"mirror check failed for {label}")


# ---------------------------------------------------------------- fixtures
class Fixtures:
    """Registry-first creation of study-owned source/target roots."""

    def __init__(self, out: Path, source_parent: Path, target_parent: Path) -> None:
        self.registry = out / "fixtures.jsonl"
        self.source_parent, self.target_parent = source_parent, target_parent

    def _register(self, root: Path, kind: str) -> Path:
        if root.exists():
            raise FileExistsError(root)
        with self.registry.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"root": str(root), "kind": kind}) + "\n")
        root.mkdir()
        return root

    def source(self, name: str, files: int, size: int, per_dir: int = 100) -> Path:
        root = self._register(self.source_parent / f"NamiSync-resource-{name}-{uuid.uuid4().hex[:8]}", "source")
        source = root / "source"
        source.mkdir()
        for index in range(files):
            directory = source / f"d{index // per_dir:04}"
            directory.mkdir(exist_ok=True)
            write_member(directory / f"f{index:06}.bin", f"{name}:{index}", size, FIXED_MTIME)
        return source

    def target(self, name: str) -> Path:
        root = self._register(self.target_parent / f"NamiSync-resource-{name}-{uuid.uuid4().hex[:8]}", "target")
        target = root / "target"
        target.mkdir()
        return target


def write_member(path: Path, seed: str, size: int, mtime: int) -> None:
    block = hashlib.sha256(seed.encode()).digest()
    path.write_bytes((block * (size // 32 + 1))[:size])
    os.utime(path, (mtime, mtime))


# ---------------------------------------------------------------- profiles
def profile_startup(run: Run, **_: object) -> None:
    run.wait_for(run.window, 90, "owned window")
    run.event("window-observed")
    run.window_idle("startup-idle", 180)


def profile_soak(run: Run, fixtures: Fixtures, name: str, **_: object) -> None:
    source = fixtures.source(name, 1000, 4096)
    target = fixtures.target(name)
    run.window_idle("initial-idle", 60)
    for cycle in range(1, SOAK_CYCLES + 1):
        label = f"cycle-{cycle:03}"
        if cycle > 1:
            for j in range(SOAK_CHANGED):
                index = (cycle * SOAK_CHANGED + j) % 1000
                write_member(source / f"d{index // 100:04}" / f"f{index:06}.bin",
                             f"{name}:{cycle}:{index}", 4096, FIXED_MTIME + 60 * cycle)
        sync_task(run, source, target, label=label, new_task=cycle > 1,
                  destructive=0 if cycle == 1 else SOAK_CHANGED, plan_timeout=300, execute_timeout=600)
        check_mirror(run, source, target, trash_files=SOAK_CHANGED * (cycle - 1), label=label)
        close_task(run, label)
        run.window_idle(f"{label}-closed", 15)
    run.window_idle("final-idle", 120)


_SCALE_SOURCES: dict[int, Path] = {}


def profile_scale(run: Run, fixtures: Fixtures, name: str, files: int, **_: object) -> None:
    if files not in _SCALE_SOURCES:  # immutable source shared by the three runs of one size
        _SCALE_SOURCES[files] = fixtures.source(f"scale-{files // 1000}k", files, 32)
    source = _SCALE_SOURCES[files]
    target = fixtures.target(name)
    run.window_idle("initial-idle", 60)
    sync_task(run, source, target, label="task", new_task=False, destructive=0,
              plan_timeout=1200, execute_timeout=3600, open_seconds=30)
    run.window_idle("task-executed-open", 30)
    close_task(run, "task")
    run.window_idle("final-idle", 60)
    run.event("deferred-mirror-check", source=str(source), target=str(target))
    run.deferred.append((source, target, "task"))


def profile_payload(run: Run, fixtures: Fixtures, name: str, groups: list[str], corpus: Path, **_: object) -> None:
    run.window_idle("initial-idle", 60)
    for index, group in enumerate(groups):
        source = corpus / group
        target = fixtures.target(f"{name}-{group}")
        label = f"group-{group}"
        sync_task(run, source, target, label=label, new_task=index > 0, destructive=0,
                  plan_timeout=600, execute_timeout=3600)
        close_task(run, label)
        run.window_idle(f"{label}-closed", 30)
        run.deferred.append((source, target, label))
    run.window_idle("final-idle", 60)


def profile_idle_open(run: Run, fixtures: Fixtures, name: str, files: int, minutes: int, **_: object) -> None:
    if files not in _SCALE_SOURCES:
        _SCALE_SOURCES[files] = fixtures.source(f"scale-{files // 1000}k", files, 32)
    source = _SCALE_SOURCES[files]
    target = fixtures.target(name)
    run.window_idle("initial-idle", 60)
    sync_task(run, source, target, label="task", new_task=False, destructive=0, plan_timeout=1200, execute_timeout=3600)
    run.window_idle("long-idle-open", minutes * 60)
    close_task(run, "task")
    run.window_idle("final-idle", 60)
    run.deferred.append((source, target, "task"))


PROFILES = {"startup": profile_startup, "soak": profile_soak, "scale": profile_scale,
            "payload": profile_payload, "idle_open": profile_idle_open}


# ---------------------------------------------------------------- collection
def extract(archive: Path, expected_sha256: str, out: Path) -> tuple[Path, dict[str, str]]:
    if digest(archive) != expected_sha256:
        raise RuntimeError("archive hash mismatch")
    app = out / "app"
    expected = {}
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            name = Path(entry.filename)
            if name.is_absolute() or ".." in name.parts or name.parts[0] != "NamiSync":
                raise RuntimeError(f"unsafe archive member: {entry.filename}")
            if not entry.is_dir():
                expected[name.relative_to("NamiSync").as_posix()] = hashlib.sha256(bundle.read(entry)).hexdigest()
        if app.exists():
            raise FileExistsError(app)
        bundle.extractall(app)
    actual = tree_hashes(app / "NamiSync")
    if actual != expected:
        raise RuntimeError("extracted bundle differs from archive")
    return app / "NamiSync" / "namisync-gui.exe", actual


def host_facts() -> dict:
    def text(command: list[str]) -> str:
        return subprocess.run(command, capture_output=True, text=True, check=False).stdout.strip()

    class _Memory(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
            (n, ctypes.c_ulonglong) for n in ("total", "avail", "tp", "ap", "tv", "av", "ae")]

    memory = _Memory()
    memory.length = ctypes.sizeof(memory)
    _KERNEL.GlobalMemoryStatusEx(ctypes.byref(memory))
    return {"platform": platform.platform(), "processor": platform.processor(), "cpu_count": os.cpu_count(),
            "total_physical_bytes": memory.total, "power_scheme": text(["powercfg", "/getactivescheme"]),
            "git_head": text(["git", "-C", str(REPOSITORY), "rev-parse", "HEAD"]),
            "git_status": text(["git", "-C", str(REPOSITORY), "status", "--porcelain"])}


def collect(args: argparse.Namespace) -> int:
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "collection.json"
    names = list(SCHEDULE) if not args.only else args.only
    unknown = [name for name in names if name not in SCHEDULE]
    if unknown:
        raise SystemExit(f"unknown runs: {unknown}")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        exe = Path(manifest["exe"])
        if tree_hashes(exe.parent) != manifest["bundle"]:
            raise RuntimeError("extracted bundle changed since collection began")
    else:
        exe, bundle = extract(args.archive, args.archive_sha256, out)
        tools = {p.relative_to(REPOSITORY).as_posix(): digest(p) for p in (
            Path(__file__), Path(_cdp.__file__), WEB_TESTS / "_headed_native.py", WEB_TESTS / "_headed_host_child.py",
            REPOSITORY / "tools/performance/bridge_event/__init__.py", REPOSITORY / "tools/performance/validate_resources.py")}
        manifest = {"archive": str(args.archive), "archive_sha256": args.archive_sha256, "exe": str(exe),
                    "bundle": bundle, "host": host_facts(), "tools": tools, "corpus": str(args.corpus),
                    "corpus_metadata_before": {g: tree_metadata(args.corpus / g) for g in ("1x4GiB", "64x4MiB")},
                    "source_parent": str(args.source_parent), "target_parent": str(args.target_parent)}
        manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    fixtures = Fixtures(out, args.source_parent, args.target_parent)
    for name in names:
        profile, parameters = SCHEDULE[name]
        run = Run(out, name, exe, cdp=profile != "startup" or parameters.get("cdp", False))
        run.deferred = []
        result: dict[str, object] = {"name": name, "profile": profile, "parameters": parameters, "complete": False}
        try:
            run.launch()
            PROFILES[profile](run, fixtures=fixtures, name=name, corpus=args.corpus, **parameters)
            result["complete"] = True
        except Exception as error:
            result["error"] = f"{type(error).__name__}: {error}"
            try:
                run.event("failure", error=result["error"])
                if run.session is not None:
                    run.screenshot("failure")
            except Exception:
                pass
        finally:
            if run.process is not None:
                result["close"] = run.close()
        mirrors = []
        for source, target, label in run.deferred:  # app closed: hashing cannot overlap any window
            same = tree_hashes(source) == tree_hashes(target, exclude_top=TRASH)
            trash = (Path(target) / TRASH).exists()
            mirrors.append({"label": label, "ok": same and not trash, "source": str(source), "target": str(target)})
        result["deferred_mirror_checks"] = mirrors
        if any(not item["ok"] for item in mirrors):
            result["complete"] = False
        (run.dir / "result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(json.dumps({"run": name, "complete": result["complete"], "error": result.get("error")}), flush=True)
        if not result["complete"]:
            return 1
    after = {g: tree_metadata(args.corpus / g) for g in ("1x4GiB", "64x4MiB")}
    if after != manifest["corpus_metadata_before"]:
        print("supplied corpus metadata changed", flush=True)
        return 1
    if tree_hashes(exe.parent) != manifest["bundle"]:
        print("extracted bundle changed during collection", flush=True)
        return 1
    return 0


def cleanup(args: argparse.Namespace) -> int:
    """Remove registered study-owned fixture roots and profiles only."""

    out = args.out.resolve()
    manifest = json.loads((out / "collection.json").read_text(encoding="utf-8"))
    parents = {Path(manifest["source_parent"]), Path(manifest["target_parent"])}
    for line in (out / "fixtures.jsonl").read_text(encoding="utf-8").splitlines():
        root = Path(json.loads(line)["root"])
        if root.parent not in parents or not root.name.startswith("NamiSync-resource-"):
            raise RuntimeError(f"refusing unregistered-shaped root {root}")
        if root.exists():
            if root.lstat().st_file_attributes & 0x400:
                raise RuntimeError(f"reparse root {root}")
            shutil.rmtree(root)
            print("removed", root)
    for directory in ("profiles", "app"):
        if (out / directory).exists():
            shutil.rmtree(out / directory)
            print("removed", out / directory)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("collect")
    run.add_argument("--archive", type=Path, required=True)
    run.add_argument("--archive-sha256", required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--corpus", type=Path, required=True)
    run.add_argument("--source-parent", type=Path, required=True)
    run.add_argument("--target-parent", type=Path, required=True)
    run.add_argument("--only", nargs="*", help="run names from the frozen schedule (pilots)")
    clean = sub.add_parser("cleanup")
    clean.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    return collect(args) if args.command == "collect" else cleanup(args)


if __name__ == "__main__":
    raise SystemExit(main())
