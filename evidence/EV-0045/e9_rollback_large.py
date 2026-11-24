"""E9: rollback of a large migration (cache spill): what the files hold, who can read them."""

from __future__ import annotations

from contextlib import closing
import hashlib
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import REPO, fresh_dir  # noqa: E402
from e3_kills import fingerprint  # noqa: E402

sys.path.insert(0, str(REPO))
import namisync.db.migration as migration  # noqa: E402
from namisync.workflows.database_pair import migrate_database_pair  # noqa: E402

work = fresh_dir(HERE / "e9")
for item in (HERE / "large-template").iterdir():
    shutil.copyfile(item, work / item.name)
ledger, history = work / "ledger.db", work / "history.db"


def stat(main: Path) -> dict[str, tuple[int, str] | None]:
    out = {}
    for suffix in ("", "-wal"):
        p = Path(f"{main}{suffix}")
        out[p.name] = (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()[:12]) if p.exists() else None
    return out


before_files = stat(ledger)
before = fingerprint(ledger, HERE / "e9-fp0")
original = migration._verify


def refuse(*args, **kwargs):
    raise sqlite3.DatabaseError("injected verification failure")


migration._verify = refuse
try:
    result = migrate_database_pair(ledger, history)
finally:
    migration._verify = original
after_files = stat(ledger)
print("result:", result.contract.state.value, result.contract.reason)
print("guidance:", result.contract.guidance)
print("before:", before_files)
print("after: ", after_files)
# An ordinary (v0.1.0-like) opener with the stale -shm present, normal locking mode.
with closing(sqlite3.connect(ledger, isolation_level=None)) as c:
    meta = dict(c.execute("SELECT key, value FROM schema_metadata"))
    count = c.execute("SELECT count(*) FROM inventory").fetchone()[0]
    integrity = c.execute("PRAGMA quick_check").fetchone()[0]
print("ordinary reader sees:", meta, "inventory", count, "quick_check", integrity)
print("fingerprint same:", fingerprint(ledger, HERE / "e9-fp1") == before)
second = migrate_database_pair(ledger, history)
print("second:", second.contract.state.value, [p.name for p in second.backups])
print("fingerprint after migration same:", fingerprint(ledger, HERE / "e9-fp2") == before)
print("final files:", sorted(p.name for p in work.iterdir()))
