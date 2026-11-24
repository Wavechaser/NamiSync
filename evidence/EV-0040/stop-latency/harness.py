"""Stop-latency harness for M2-A2 (cancel-to-terminal and cancel-to-custody-release).

Read-only toward the product: only imports namisync public facades and wraps
WalkingScanner.scan in-process (harness side) to count scanner checkpoints.

Subcommands (all paths explicit; nothing defaults to the live NamiSync root):
  gen        generate a deterministic fixture tree pair (src, tgt)
  calibrate  run each case to completion once and record scan phase durations
  run        run N cancel samples per case, write raw JSON
  cold       spawn one fresh process per sample (cold-ish = fresh process)

Clock: time.perf_counter_ns (QPC; one clock for all timestamps, all threads).
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import random
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
now_ns = time.perf_counter_ns


# --------------------------------------------------------------------- fixture
def gen_tree(root: Path, files: int, seed: int, tag: str) -> dict:
    """Deterministic tree: ~files/50 dirs, random-parent nesting, tiny files.

    File sizes are 0..512 bytes so NTFS keeps data resident in the MFT record
    (no clusters allocated for most files).
    """
    rng = random.Random(seed)
    root.mkdir(parents=True, exist_ok=True)
    ndirs = max(1, files // 50)
    dirs = [root]
    rels = [""]
    for i in range(ndirs):
        pi = rng.randrange(len(dirs))
        if rels[pi].count("\\") >= 6:  # cap depth at 7
            pi = 0
        rel = f"{rels[pi]}\\d{i:05d}".lstrip("\\")
        p = root / rel
        p.mkdir(parents=True, exist_ok=True)
        dirs.append(p)
        rels.append(rel)
    h = hashlib.sha256()
    total = 0
    for i in range(files):
        d = dirs[rng.randrange(len(dirs))]
        size = rng.randrange(0, 513)
        name = f"{tag}{i:06d}.dat"
        with open(d / name, "wb") as f:
            f.write(bytes([i & 0xFF]) * size)
        total += size
        h.update(f"{d.relative_to(root)}\\{name}:{size}\n".encode())
    return {
        "root": str(root),
        "files": files,
        "dirs": len(dirs) - 1,
        "payload_bytes": total,
        "seed": seed,
        "listing_sha256": h.hexdigest(),
    }


def cmd_gen(a) -> None:
    base = Path(a.fixture_root).resolve()
    if base.exists() and any(base.iterdir()) and not a.force:
        sys.exit(f"{base} not empty; pass --force to reuse (will not delete)")
    t0 = time.time()
    man = {
        "src": gen_tree(base / "src", a.src_files, a.seed, "s"),
        "tgt": gen_tree(base / "tgt", a.tgt_files, a.seed + 1, "t"),
        "generated_seconds": round(time.time() - t0, 1),
    }
    (base / "manifest.json").write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


# ------------------------------------------------------------- runtime identity
def identity() -> dict:
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(REPO), *args], capture_output=True, text=True
        ).stdout.strip()

    status = git("status", "--porcelain")
    # build/ is ignored; any porcelain line is tracked/untracked-not-ignored change
    return {
        "python": sys.version,
        "sqlite": sqlite3.sqlite_version,
        "platform": platform.platform(),
        "git_revision": git("rev-parse", "HEAD"),
        "git_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": bool(status),
        "git_status_lines": status.splitlines()[:20],
    }


# ---------------------------------------------------------------- scanner probe
class ScanProbe:
    """Wraps WalkingScanner.scan to count checkpoints and stamp the cancel raise."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.calls = 0
        self.checkpoints = 0
        self.first_ns = None
        self.last_ns = None
        self.max_gap_ns = 0
        self.raised_ns = None
        self.scan_started_ns = []
        self.scan_returned_ns = []

    def install(self) -> None:
        from namisync.core.session import Canceled, RunContext
        from namisync.modules.scanner import WalkingScanner

        probe = self
        orig = WalkingScanner.scan

        def scan(self_, root, ignores, ctx, *args, **kw):
            inner = ctx.checkpoint

            def checkpoint():
                t = now_ns()
                probe.checkpoints += 1
                if probe.last_ns is not None:
                    gap = t - probe.last_ns
                    if gap > probe.max_gap_ns:
                        probe.max_gap_ns = gap
                probe.last_ns = t
                if probe.first_ns is None:
                    probe.first_ns = t
                try:
                    return inner()
                except Canceled:
                    probe.raised_ns = now_ns()
                    raise

            probe.calls += 1
            probe.scan_started_ns.append(now_ns())
            out = orig(self_, root, ignores, RunContext(ctx.emit, checkpoint), *args, **kw)
            probe.scan_returned_ns.append(now_ns())
            return out

        WalkingScanner.scan = scan


# --------------------------------------------------------------- custody prober
class CustodyProbe(threading.Thread):
    """Blocks on the dispatcher's Windows named mutex from another thread.

    Acquisition time == moment custody became available to another session
    (the same primitive another process/session would wait on).
    """

    def __init__(self, resource_key: str) -> None:
        super().__init__(daemon=True)
        from namisync.core.session import ResourceId
        from namisync.dispatcher.custody import WindowsNamedMutexProvider

        self.name_ = WindowsNamedMutexProvider.mutex_name(ResourceId("volume", resource_key))
        self.armed = threading.Event()
        self.done = threading.Event()
        self.held_when_armed = None
        self.acquired_ns = None
        self.error = None
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        k.CreateMutexW.restype = wintypes.HANDLE
        k.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        k.WaitForSingleObject.restype = wintypes.DWORD
        k.ReleaseMutex.argtypes = (wintypes.HANDLE,)
        k.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.k = k

    def run(self) -> None:
        k = self.k
        h = k.CreateMutexW(None, False, self.name_)
        try:
            # 0 ms wait: must time out (0x102) while a session holds custody.
            first = k.WaitForSingleObject(h, 0)
            self.held_when_armed = first == 0x102
            if first in (0, 0x80):  # wrong key / not held: release and bail
                k.ReleaseMutex(h)
                self.error = "mutex was free at arm time (not held or wrong key)"
                return
            self.armed.set()
            r = k.WaitForSingleObject(h, 120_000)
            self.acquired_ns = now_ns()
            if r not in (0, 0x80):
                self.error = f"wait result {r:#x}"
            else:
                k.ReleaseMutex(h)
        finally:
            if h:
                k.CloseHandle(h)
            self.armed.set()
            self.done.set()


# ----------------------------------------------------------------- event sink
class Sink:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.events = []  # (t_ns, kind, body_type, detail)
        self.cv = threading.Condition(self.lock)

    def __call__(self, item) -> None:
        t = now_ns()
        if hasattr(item, "body_type"):
            kind, bt = "event", item.body_type
            detail = dict(item.body) if isinstance(item.body, dict) else str(item.body)
        else:
            kind, bt = "record", item.state
            detail = {"state": item.state}
        with self.cv:
            self.events.append((t, kind, bt, detail))
            self.cv.notify_all()

    def wait_for(self, pred, timeout: float):
        end = time.monotonic() + timeout
        with self.cv:
            while True:
                for e in self.events:
                    if pred(e):
                        return e
                left = end - time.monotonic()
                if left <= 0:
                    return None
                self.cv.wait(left)


def is_phase(name):
    return lambda e: e[1] == "event" and e[2] == "PhaseChanged" and name in json.dumps(e[3])


def is_terminal(e):
    return e[1] == "event" and e[2] == "Terminal"


def is_final_record(e):
    return e[1] == "record" and e[2] in ("canceled", "completed", "failed")


# ---------------------------------------------------------------------- driver
CASES = {
    "inventory-scan": {"phase": "inventory"},
    "plan-source-scan": {"phase": "scan-source"},
    "plan-target-scan": {"phase": "scan-target"},
    # cancel lands after both scans returned: planner computation, no checkpoints
    "plan-compute": {"phase": "scan-target"},
}


class Rig:
    def __init__(self, fixture: Path, data_root: Path) -> None:
        self.fixture = fixture
        self.src = str(fixture / "src")
        self.tgt = str(fixture / "tgt")
        self.data = data_root
        self.data.mkdir(parents=True, exist_ok=True)
        self.probe = ScanProbe()
        self.probe.install()
        from namisync.interfaces.service import NamiSyncService

        self.service = NamiSyncService(
            self.data / "ledger.db",
            self.data / "history.db",
            settings_path=self.data / "settings.json",
        )
        self.service.initialize_database_contracts()
        self.resource_key = None

    def close(self):
        self.service.close()

    def volume_key(self) -> str:
        if self.resource_key is None:
            from namisync.workflows import LocationCandidate

            res = self.service.admit_location_candidate(LocationCandidate.literal(self.src))
            vid = res.binding.volume_id
            self.resource_key = f"{vid.serial}:{vid.fs_type}"
        return self.resource_key

    def start(self, case: str):
        if case == "inventory-scan":
            return self.service.start_inventory(root_path=self.src).session_id
        return self.service.start_plan(self.src, self.tgt).session_id

    def one(self, case: str, delay_ms: float | None, *, complete: bool = False,
            timeout: float = 600) -> dict:
        """One sample. delay_ms None + complete=True: run to completion (calibration)."""
        phase = CASES[case]["phase"]
        sink = Sink()
        self.probe.reset()
        key = self.volume_key()
        sid = self.start(case)
        t_submit = now_ns()
        self.service.observe(sid, sink)
        rec = {"case": case, "delay_ms": delay_ms, "session_id": sid}
        ph = sink.wait_for(is_phase(phase), 120)
        if ph is None:
            rec["error"] = "phase event not seen"
            self._finish(sid)
            return rec
        t_phase = ph[0]
        if case == "plan-compute":
            while len(self.probe.scan_returned_ns) < 2:
                time.sleep(0.001)
            t_phase = self.probe.scan_returned_ns[1]
        rec["submit_to_phase_ms"] = (t_phase - t_submit) / 1e6
        if complete:
            # Calibrate scan duration only: planning/persistence after the scan is not
            # needed (and a 100k-operation plan takes many minutes). Cancel once the
            # last scan call has returned.
            want = 2 if case != "inventory-scan" else 1
            end = time.monotonic() + timeout
            while len(self.probe.scan_returned_ns) < want and time.monotonic() < end:
                time.sleep(0.002)
            if case == "inventory-scan":
                self.service.cancel(sid)
            else:  # planning has no checkpoints: do not wait for it (see REPORT)
                rec["scan_ms"] = [(b - a) / 1e6 for a, b in zip(self.probe.scan_started_ns, self.probe.scan_returned_ns)]
                rec["checkpoints"] = self.probe.checkpoints
                return rec
            term = sink.wait_for(is_terminal, 600)
            fin = sink.wait_for(is_final_record, 30)
            rec["events"] = [(round((e[0] - t_phase) / 1e6, 2), e[2], e[3]) for e in sink.events
                             if e[1] == "event" and e[2] in ("PhaseChanged", "StateChanged", "Terminal")]
            rec["final_state"] = fin[2] if fin else None
            rec["phase_to_terminal_ms"] = (term[0] - t_phase) / 1e6 if term else None
            rec["scan_calls_ms"] = [
                (s - t_phase) / 1e6 for s in self.probe.scan_started_ns
            ], [(s - t_phase) / 1e6 for s in self.probe.scan_returned_ns]
            rec["checkpoints"] = self.probe.checkpoints
            self._finish(sid)
            return rec
        # wait until the delay elapsed since phase start (sleep coarse, spin fine)
        target = t_phase + int(delay_ms * 1e6)
        while True:
            left = target - now_ns()
            if left <= 0:
                break
            if left > 3_000_000:
                time.sleep((left - 2_000_000) / 1e9)
        prober = CustodyProbe(key)
        prober.start()
        prober.armed.wait(5)
        # re-spin if arming took past target (it is fine: delay is a lower bound)
        cp_before = self.probe.checkpoints
        alive_before = self.probe.raised_ns is None and len(self.probe.scan_returned_ns) < (2 if case != "inventory-scan" else 1) if case != "plan-compute" else len(self.probe.scan_returned_ns) >= 2
        t_cancel = now_ns()
        ctrl = self.service.cancel(sid)
        t_cancel_ret = now_ns()
        term = sink.wait_for(is_terminal, 120)
        fin = sink.wait_for(is_final_record, 120)
        prober.done.wait(120)
        rec.update(
            {
                "accepted": bool(ctrl.accepted),
                "cancel_code": ctrl.code,
                "scan_alive_at_cancel": alive_before,
                "checkpoints_at_cancel": cp_before,
                "checkpoints_final": self.probe.checkpoints,
                "scan_call_index": self.probe.calls,
                "since_phase_ms": (t_cancel - t_phase) / 1e6,
                "cancel_call_ms": (t_cancel_ret - t_cancel) / 1e6,
                "scanner_raise_ms": None if self.probe.raised_ns is None
                else (self.probe.raised_ns - t_cancel) / 1e6,
                "custody_release_ms": None if prober.acquired_ns is None
                else (prober.acquired_ns - t_cancel) / 1e6,
                "terminal_event_ms": None if term is None else (term[0] - t_cancel) / 1e6,
                "final_record_ms": None if fin is None else (fin[0] - t_cancel) / 1e6,
                "final_state": None if fin is None else fin[2],
                "held_when_armed": prober.held_when_armed,
                "prober_error": prober.error,
                "max_checkpoint_gap_ms": self.probe.max_gap_ns / 1e6,
                "post_cancel_events": [
                    (round((e[0] - t_cancel) / 1e6, 3), e[2],
                     e[3] if e[2] in ("StateChanged", "Terminal") else "")
                    for e in sink.events if e[0] >= t_cancel
                ],
            }
        )
        self._finish(sid)
        return rec

    def _finish(self, sid: str) -> None:
        try:
            self.service.wait(sid)
        except Exception as e:  # noqa: BLE001
            print("wait failed", e, file=sys.stderr)
        try:
            self.service.close_session(sid)
        except Exception as e:  # noqa: BLE001
            print("close_session failed", e, file=sys.stderr)


def fresh_data_root(p: Path) -> Path:
    p = p.resolve()
    assert str(p).startswith(str(HERE)), "data root must be inside the build folder"
    if p.exists():
        shutil.rmtree(p)
    return p


def cmd_calibrate(a) -> None:
    rig = Rig(Path(a.fixture_root).resolve(), fresh_data_root(Path(a.data_root)))
    out = {}
    try:
        for case in ("inventory-scan", "plan-source-scan"):
            r = rig.one(case, None, complete=True)
            out[case] = r
            print(case, json.dumps({k: v for k, v in r.items() if k != "events"}, default=str))
            print("  events", json.dumps(r.get("events"), default=str)[:1500])
    finally:
        pass
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    sys.stdout.flush()
    os._exit(0)  # the plan session keeps planning (no checkpoints); do not wait for it


def cmd_run(a) -> None:
    fixture = Path(a.fixture_root).resolve()
    rig = Rig(fixture, fresh_data_root(Path(a.data_root)))
    scan_ms = json.loads(Path(a.scan_ms).read_text() if Path(a.scan_ms).is_file() else a.scan_ms)  # {"case": scan duration ms}
    fracs = [float(x) for x in a.fractions.split(",")]
    samples = []
    try:
        # warm-up: one throwaway full-scan cancel at 50% to load code paths/caches
        for _ in range(a.warmup):
            for case in a.cases.split(","):
                rig.one(case, scan_ms[case] * 0.5)
        for i in range(a.samples):
            for case in a.cases.split(","):
                d = scan_ms[case] * fracs[i % len(fracs)]
                r = rig.one(case, d)
                r["i"] = i
                r["frac"] = fracs[i % len(fracs)]
                r["tag"] = a.tag
                samples.append(r)
                print(case, i, f"delay={d:.0f}ms", r.get("final_state"),
                      "cust=%.2f term=%.2f" % (r.get("custody_release_ms") or -1,
                                                  r.get("terminal_event_ms") or -1), flush=True)
    finally:
        rig.close()
    Path(a.out).write_text(json.dumps({"identity": identity(), "args": vars(a),
                                       "samples": samples}, indent=1, default=str))


def cmd_cold(a) -> None:
    """One fresh Python process per sample (cold-ish: process/import/JIT/SQLite state cold,
    OS metadata cache NOT cold)."""
    allsamples = []
    for i in range(a.samples):
        for case in a.cases.split(","):
            out = HERE / f"_cold_{case}_{i}.json"
            cmd = [sys.executable, str(HERE / "harness.py"), "run", "--fixture-root", a.fixture_root,
                   "--data-root", str(Path(a.data_root) / f"c{i}"), "--scan-ms", a.scan_ms,
                   "--fractions", a.fractions.split(",")[i % len(a.fractions.split(","))],
                   "--cases", case, "--samples", "1", "--warmup", "0", "--tag", "cold-ish",
                   "--out", str(out)]
            subprocess.run(cmd, check=True, capture_output=True)
            allsamples.extend(json.loads(out.read_text())["samples"])
            out.unlink()
    Path(a.out).write_text(json.dumps({"identity": identity(), "args": vars(a),
                                       "samples": allsamples}, indent=1, default=str))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--fixture-root", required=True)
    g.add_argument("--src-files", type=int, default=100_000)
    g.add_argument("--tgt-files", type=int, default=30_000)
    g.add_argument("--seed", type=int, default=0x4E414D49)
    g.add_argument("--force", action="store_true")
    for name in ("calibrate", "run", "cold"):
        p = sub.add_parser(name)
        p.add_argument("--fixture-root", required=True)
        p.add_argument("--data-root", required=True, help="isolated dir inside the build folder")
        p.add_argument("--out", required=True)
        if name != "calibrate":
            p.add_argument("--scan-ms", required=True, help='JSON {"case": ms}')
            p.add_argument("--fractions", default="0.05,0.2,0.35,0.5,0.65,0.8")
            p.add_argument("--cases", default="inventory-scan,plan-source-scan,plan-target-scan")
            p.add_argument("--samples", type=int, default=30)
            p.add_argument("--warmup", type=int, default=1)
            p.add_argument("--tag", default="warm")
    a = ap.parse_args()
    {"gen": cmd_gen, "calibrate": cmd_calibrate, "run": cmd_run, "cold": cmd_cold}[a.cmd](a)


if __name__ == "__main__":
    main()
