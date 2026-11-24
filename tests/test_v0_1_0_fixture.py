"""The released v0.1.0 database pair fixture is intact and carries its markers.

`tests/assets/v0_1_0/` holds files written by the released v0.1.0 CLI;
`tools/fixtures/v0_1_0_pair.py` is the method and `PROVENANCE.json` the record.
v0.1.0 exits with its committed rows still in the `-wal` sidecar, so the
fixture is each database with its `-wal` and `-shm`. Tests only read the
tracked files to copy them and open the copies. Nothing here says how current
code classifies the pair.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import pytest


FIXTURE = Path(__file__).parent / "assets" / "v0_1_0"
PROVENANCE = json.loads((FIXTURE / "PROVENANCE.json").read_text(encoding="utf-8"))
RELEASED = {
    "ledger": ("ledger.db", "4", "m1-ledger-v4-event-v5-evidence-v2"),
    "history": ("history.db", "8", "m1-history-v8-event-v5-recording-v1"),
}
WRITTEN = sorted(
    name
    for database in PROVENANCE["databases"].values()
    for name in database["files"]
)


@pytest.fixture
def pair(tmp_path: Path) -> Path:
    for name in WRITTEN:
        shutil.copyfile(FIXTURE / name, tmp_path / name)
    return tmp_path


def _row_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    return {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in tables
    }


def test_fixture_holds_exactly_the_files_the_release_left() -> None:
    assert WRITTEN == PROVENANCE["data_folder_entries"]
    assert sorted(path.name for path in FIXTURE.iterdir()) == sorted(
        [*WRITTEN, "PROVENANCE.json"]
    )
    assert not [name for name in WRITTEN if name.endswith("-journal")]


def test_copied_bytes_match_the_recorded_hashes(pair: Path) -> None:
    for database in PROVENANCE["databases"].values():
        for name, identity in database["files"].items():
            data = (pair / name).read_bytes()
            assert len(data) == identity["size"], name
            assert hashlib.sha256(data).hexdigest() == identity["sha256"], name


@pytest.mark.parametrize("database", sorted(RELEASED))
def test_copy_carries_the_released_markers_and_recorded_rows(
    pair: Path, database: str
) -> None:
    main, version, contract = RELEASED[database]
    recorded = PROVENANCE["databases"][database]
    connection = sqlite3.connect(f"{(pair / main).as_uri()}?mode=ro", uri=True)
    try:
        metadata = dict(connection.execute("SELECT key, value FROM schema_metadata"))
        assert metadata["schema_version"] == version
        assert metadata["contract_id"] == contract
        assert metadata == recorded["schema_metadata"]
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert (
            connection.execute("PRAGMA user_version").fetchone()[0]
            == recorded["user_version"]
        )
        assert _row_counts(connection) == recorded["row_counts"]
    finally:
        connection.close()


@pytest.mark.parametrize("database", sorted(RELEASED))
def test_main_file_alone_holds_only_the_schema(
    tmp_path: Path, database: str
) -> None:
    main = RELEASED[database][0]
    shutil.copyfile(FIXTURE / main, tmp_path / main)
    connection = sqlite3.connect(
        f"{(tmp_path / main).as_uri()}?mode=ro&immutable=1", uri=True
    )
    try:
        counts = _row_counts(connection)
    finally:
        connection.close()
    assert counts == PROVENANCE["databases"][database]["main_only_row_counts"]
    assert {table for table, count in counts.items() if count} == {"schema_metadata"}
