"""E3: kill the real migration at points the builder's suite does not cover."""

from __future__ import annotations

from contextlib import closing
import hashlib
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import REPO, copy_pair, fresh_dir, snapshot_copy, table_columns, user_tables  # noqa: E402

sys.path.insert(0, str(REPO))
from namisync.db.contracts import probe_database_file_contract  # noqa: E402
from namisync.db.schema import DatabaseMigrationRequired  # noqa: E402
from namisync.workflows.database_pair import migrate_database_pair  # noqa: E402

RELEASED_COLUMNS: dict[str, list[str]] = {}
with closing(sqlite3.connect((HERE / "large-template" / "ledger.db").as_uri() + "?mode=ro&immutable=1", uri=True)) as c:
    for t in user_tables(c):
        RELEASED_COLUMNS[t] = table_columns(c, t)


def fingerprint(main: Path, scratch: Path) -> dict[str, str]:
    copy = snapshot_copy(main, scratch)
    out = {}
    with closing(sqlite3.connect(copy.as_uri() + "?mode=ro", uri=True)) as c:
        for table, columns in RELEASED_COLUMNS.items():
            if table == "schema_metadata":
                continue
            digest = hashlib.sha256()
            select = ", ".join(f"typeof({x}), quote({x})" for x in columns)
            count = 0
            for row in c.execute(f"SELECT {select} FROM {table} ORDER BY {columns[0]}, {columns[1]}, {columns[2]}"):
                digest.update(repr(row).encode())
                count += 1
            out[table] = f"{count}:{digest.hexdigest()[:16]}"
    shutil.rmtree(scratch)
    return out


def classify(main: Path, history: bool) -> str:
    try:
        probe_database_file_contract(main, history=history)
    except DatabaseMigrationRequired:
        return "older"
    except Exception as error:  # noqa: BLE001
        return f"ERROR {type(error).__name__}: {error}"
    return "current"


def trial(name: str, stage: str, delay: float, *, large: bool) -> None:
    work = fresh_dir(HERE / "e3" / name)
    if large:
        for item in (HERE / "large-template").iterdir():
            shutil.copyfile(item, work / item.name)
        ledger, history = work / "ledger.db", work / "history.db"
    else:
        ledger, history = copy_pair(work)
    before = fingerprint(ledger, HERE / "e3" / f"{name}-fp0")
    completed = subprocess.run(
        [sys.executable, str(HERE / "kill_child.py"), str(ledger), str(history), stage, str(delay)],
        capture_output=True, text=True, timeout=600,
    )
    lines = completed.stdout.strip().splitlines()
    state = classify(ledger, False)
    after = fingerprint(ledger, HERE / "e3" / f"{name}-fp1")
    leftovers = sorted(p.name for p in work.iterdir() if ".migration-" in p.name or ".backup-" in p.name)
    verdict = "same-content" if after == before else "CONTENT CHANGED"
    print(f"[{name}] exit={completed.returncode} out={lines[-2:]} -> ledger {state}, {verdict}, files {leftovers}")
    if completed.stderr.strip():
        print("   stderr:", completed.stderr.strip().splitlines()[-1][:300])
    result = migrate_database_pair(ledger, history)
    again = fingerprint(ledger, HERE / "e3" / f"{name}-fp2")
    print(f"   rerun: {result.contract.state} {result.contract.reason} backups={[p.name for p in result.backups]} "
          f"ledger {classify(ledger, False)} history {classify(history, True)} content {'same' if again == before else 'CHANGED'}")
    shutil.rmtree(work)


if __name__ == "__main__":
    which = sys.argv[1:] or ["small"]
    if "small" in which:
        trial("in-backup-small", "in-backup", 0, large=False)
        trial("rename-kill-small", "rename-kill", 0, large=False)
    if "backup-large" in which:
        trial("in-backup-large", "in-backup", 0, large=True)
    if "copy" in which:
        for d in (0.2, 1.0, 3.0):
            trial(f"in-copy-{d}", "in-copy", d, large=True)
    if "commit" in which:
        for d in (0.0, 0.002, 0.01, 0.05, 0.2):
            trial(f"in-commit-{d}", "in-commit", d, large=True)
    if "close" in which:
        for d in (0.0, 0.05, 0.3, 1.0):
            trial(f"in-close-{d}", "in-close", d, large=True)
