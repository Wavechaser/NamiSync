"""Build a large v0.1.0-shaped pair template: fixture plus many inventory rows, all in the WAL."""

from __future__ import annotations

from contextlib import closing
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import copy_pair, fresh_dir  # noqa: E402

ROWS = int(sys.argv[1]) if len(sys.argv) > 1 else 400_000
template = fresh_dir(HERE / "large-template")
ledger, history = copy_pair(template)
T = "2026-01-01T00:00:00.000000Z"
with closing(sqlite3.connect(ledger, isolation_level=None)) as c:
    c.execute("PRAGMA foreign_keys = ON")
    assert c.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
    c.execute("PRAGMA wal_autocheckpoint = 0")
    c.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
    c.execute("BEGIN IMMEDIATE")
    vol = c.execute("SELECT id FROM volumes LIMIT 1").fetchone()[0]
    loc = c.execute(
        "INSERT INTO locations(volume_id, volume_relative_path, volume_relative_path_key, created_at, last_seen_at) "
        "VALUES (?, 'large', 'LARGE', ?, ?) RETURNING id", (vol, T, T),
    ).fetchone()[0]
    c.executemany(
        "INSERT INTO inventory(location_id, rel_path, rel_path_key, entry_kind, presence, observed_size, observed_mtime_ns, "
        "file_identity_volume_serial, file_identity_file_index, scope_token) VALUES (?, ?, ?, 'file', 'present', ?, ?, 'VS', ?, 'scope')",
        (
            (loc, f"dir{i % 977:04d}/some/longer/path/component/file-{i:09d}.bin",
             f"DIR{i % 977:04d}/SOME/LONGER/PATH/COMPONENT/FILE-{i:09d}.BIN", i * 4096, i * 1000, str(i))
            for i in range(ROWS)
        ),
    )
    c.execute("COMMIT")
for suffix in ("", "-wal", "-shm"):
    path = Path(f"{ledger}{suffix}")
    print(path.name, path.stat().st_size if path.exists() else None)
