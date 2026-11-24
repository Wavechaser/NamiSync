"""Child: run the real pair migration and die at a chosen point (TerminateProcess)."""

from __future__ import annotations

import ctypes
import sqlite3
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import namisync.db.migration as migration  # noqa: E402
from namisync.workflows.database_pair import migrate_database_pair  # noqa: E402

ledger, history, stage = sys.argv[1:4]
delay = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetCurrentProcess.restype = ctypes.c_void_p
kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]


def die_after(seconds: float, label: str) -> None:
    def run() -> None:
        time.sleep(seconds)
        print("killing " + label, flush=True)
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), 9)

    threading.Thread(target=run, daemon=True).start()


def die_now(label: str) -> None:
    print("killing " + label, flush=True)
    kernel32.TerminateProcess(kernel32.GetCurrentProcess(), 9)


class Hooked(sqlite3.Connection):
    commits = 0

    def backup(self, target, **kwargs):
        if stage == "in-backup":
            calls = [0]

            def progress(status, remaining, total):
                calls[0] += 1
                if calls[0] == 2:
                    die_now(f"in-backup remaining={remaining} total={total}")

            return super().backup(target, pages=4, progress=progress)
        return super().backup(target, **kwargs)

    def execute(self, sql, *args):
        if sql == "COMMIT":
            Hooked.commits += 1
            if stage == "in-commit" and Hooked.commits == 2:
                print("commit-start", flush=True)
                die_after(delay, f"in-commit +{delay}")
                result = super().execute(sql, *args)
                print("commit-done", flush=True)
                return result
        if stage == "in-copy" and sql.startswith("INSERT INTO inventory("):
            die_after(delay, f"in-copy +{delay}")
        return super().execute(sql, *args)

    def close(self):
        if stage == "in-close" and Hooked.commits >= 2:
            print("close-start", flush=True)
            die_after(delay, f"in-close +{delay}")
            super().close()
            print("close-done", flush=True)
            time.sleep(30)
            return
        return super().close()


_connect = sqlite3.connect


def connect(database, *args, **kwargs):
    if isinstance(database, str) and database.endswith("?mode=rw") and Path(ledger).name in database:
        kwargs["factory"] = Hooked
    return _connect(database, *args, **kwargs)


migration.sqlite3 = type(sys)("sqlite3_proxy")
migration.sqlite3.__dict__.update(sqlite3.__dict__)
migration.sqlite3.connect = connect

if stage == "rename-kill":
    import os as _os

    _rename = _os.rename

    def rename(src, dst):
        die_now("before-rename")

    migration.os = type(sys)("os_proxy")
    migration.os.__dict__.update(_os.__dict__)
    migration.os.rename = rename

print("ready", flush=True)
result = migrate_database_pair(ledger, history)
print("finished " + result.contract.state + " " + str(result.contract.reason), flush=True)
