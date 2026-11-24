"""M2-A3 design probe: can SQLite itself prove this is the sole connection to a WAL database?

Everything happens in a fresh temporary directory beside this script.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

HOLDER = r"""
import sqlite3, sys, time
mode, path = sys.argv[1], sys.argv[2]
c = sqlite3.connect(path, isolation_level=None)
if mode == "reader":
    c.execute("SELECT count(*) FROM t").fetchone()
elif mode == "open-read-tx":
    c.execute("BEGIN"); c.execute("SELECT count(*) FROM t").fetchone()
elif mode == "writer-idle":
    c.execute("PRAGMA journal_mode=WAL"); c.execute("INSERT INTO t VALUES (2)")
elif mode == "never-touched":
    pass
print("ready", flush=True)
time.sleep(60)
"""

MIGRATOR_CRASH = r"""
import os, sqlite3, sys
path = sys.argv[1]
c = sqlite3.connect(path, isolation_level=None)
c.execute("PRAGMA locking_mode=EXCLUSIVE")
c.execute("BEGIN IMMEDIATE")
c.execute("ALTER TABLE t RENAME TO old_t")
c.execute("CREATE TABLE t(x INTEGER PRIMARY KEY AUTOINCREMENT)")
c.execute("INSERT INTO t SELECT x FROM old_t")
c.execute("DROP TABLE old_t")
c.execute("INSERT INTO t VALUES (999)")
print("mid", flush=True)
os._exit(3)
"""


def fresh(directory: Path, name: str) -> Path:
    path = directory / name
    c = sqlite3.connect(path, isolation_level=None)
    assert c.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    c.execute("CREATE TABLE t(x INTEGER PRIMARY KEY)")
    c.execute("INSERT INTO t VALUES (1)")
    c.close()
    return path


def try_exclusive(path: Path) -> str:
    c = sqlite3.connect(path, isolation_level=None, timeout=0.2)
    try:
        c.execute("PRAGMA locking_mode=EXCLUSIVE")
        try:
            c.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as error:
            return f"refused ({error})"
        mode = c.execute("PRAGMA journal_mode").fetchone()[0]
        c.execute("ROLLBACK")
        return f"acquired (journal_mode={mode})"
    finally:
        c.close()


def main() -> None:
    print("sqlite", sqlite3.sqlite_version, "python", sys.version.split()[0])
    with tempfile.TemporaryDirectory(dir=HERE, prefix="probe-") as raw:
        directory = Path(raw)

        path = fresh(directory, "alone.db")
        print("alone:", try_exclusive(path))

        for mode in ("reader", "open-read-tx", "writer-idle", "never-touched"):
            path = fresh(directory, f"{mode}.db")
            child = subprocess.Popen(
                [sys.executable, "-I", "-c", HOLDER, mode, str(path)],
                stdout=subprocess.PIPE, text=True,
            )
            assert child.stdout.readline().strip() == "ready"
            print(f"other process {mode}:", try_exclusive(path))
            child.kill(); child.wait()
            print(f"  after kill {mode}:", try_exclusive(path))

        # While we hold exclusive, can another process read or write?
        path = fresh(directory, "held.db")
        holder = sqlite3.connect(path, isolation_level=None)
        holder.execute("PRAGMA locking_mode=EXCLUSIVE")
        holder.execute("BEGIN IMMEDIATE")
        for label, sql in (("read", "SELECT count(*) FROM t"), ("write", "INSERT INTO t VALUES (5)")):
            other = sqlite3.connect(path, isolation_level=None, timeout=0.2)
            try:
                other.execute(sql).fetchall()
                print(f"while held, other {label}: ALLOWED")
            except sqlite3.OperationalError as error:
                print(f"while held, other {label}: refused ({error})")
            other.close()
        # Does the exclusive lock survive COMMIT (between backup and migration)?
        holder.execute("COMMIT")
        other = sqlite3.connect(path, isolation_level=None, timeout=0.2)
        try:
            other.execute("SELECT count(*) FROM t").fetchall()
            print("after COMMIT still holding connection, other read: ALLOWED")
        except sqlite3.OperationalError as error:
            print(f"after COMMIT still holding connection, other read: refused ({error})")
        other.close()
        # Backup API from the exclusive connection.
        destination = sqlite3.connect(directory / "backup.db")
        holder.backup(destination)
        print("backup from exclusive holder rows:",
              destination.execute("SELECT count(*) FROM t").fetchone()[0],
              "integrity:", destination.execute("PRAGMA integrity_check").fetchone()[0])
        destination.close()
        holder.close()
        print("sidecars after close:", sorted(p.name for p in directory.glob("held.db*")))

        # Crash mid-transaction: old or new?
        path = fresh(directory, "crash.db")
        child = subprocess.run(
            [sys.executable, "-I", "-c", MIGRATOR_CRASH, str(path)],
            stdout=subprocess.PIPE, text=True,
        )
        print("crash child:", child.stdout.strip(), "exit", child.returncode)
        print("  artifacts:", sorted((p.name, p.stat().st_size) for p in directory.glob("crash.db*")))
        c = sqlite3.connect(path, isolation_level=None)
        print("  after crash rows:", c.execute("SELECT x FROM t").fetchall(),
              "sql:", c.execute("SELECT sql FROM sqlite_schema WHERE name='t'").fetchone()[0],
              "mode:", c.execute("PRAGMA journal_mode").fetchone()[0])
        c.close()

        # Topology text after rename-old / create-fresh / copy / drop-old.
        path = fresh(directory, "topology.db")
        c = sqlite3.connect(path, isolation_level=None)
        c.execute("CREATE INDEX t_idx ON t(x)")
        c.execute("PRAGMA locking_mode=EXCLUSIVE")
        c.execute("BEGIN IMMEDIATE")
        c.execute("DROP INDEX t_idx")
        c.execute("ALTER TABLE t RENAME TO migrate_old_t")
        c.execute("CREATE TABLE IF NOT EXISTS t (\n    x INTEGER PRIMARY KEY AUTOINCREMENT\n) STRICT")
        c.execute("CREATE INDEX IF NOT EXISTS t_idx ON t(x)")
        c.execute("INSERT INTO t SELECT x FROM migrate_old_t")
        c.execute("DROP TABLE migrate_old_t")
        c.execute("COMMIT")
        migrated = c.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY 1,2").fetchall()
        seq = c.execute("SELECT * FROM sqlite_sequence").fetchall()
        c.close()
        ref = sqlite3.connect(":memory:")
        ref.execute("CREATE TABLE IF NOT EXISTS t (\n    x INTEGER PRIMARY KEY AUTOINCREMENT\n) STRICT")
        ref.execute("CREATE INDEX IF NOT EXISTS t_idx ON t(x)")
        reference = ref.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY 1,2").fetchall()
        print("topology identical to fresh:", migrated == reference, "| sqlite_sequence:", seq)
        if migrated != reference:
            print("  migrated:", migrated); print("  reference:", reference)


if __name__ == "__main__":
    main()
