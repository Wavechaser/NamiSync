from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from namisync.db.connections import (
    DatabaseLocationError,
    connect_history_reader,
    connect_ledger_reader,
    connect_ledger_writer,
    validate_database_path,
)
from namisync.db.schema import (
    HISTORY_SCHEMA_VERSION,
    LEDGER_SCHEMA_VERSION,
    SchemaResetRequired,
    initialize_history,
    initialize_ledger,
    reset_databases,
)


def _pragma(connection: sqlite3.Connection, name: str):
    return connection.execute(f"PRAGMA {name}").fetchone()[0]


def test_ledger_connections_enforce_safety_pragmas_and_readonly(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    initialize_ledger(path, busy_timeout_ms=2_750)

    writer = connect_ledger_writer(path, busy_timeout_ms=2_750)
    reader = connect_ledger_reader(path, busy_timeout_ms=2_750)
    try:
        assert _pragma(writer, "foreign_keys") == 1
        assert _pragma(writer, "journal_mode") == "wal"
        assert _pragma(writer, "busy_timeout") == 2_750
        assert _pragma(reader, "foreign_keys") == 1
        assert _pragma(reader, "journal_mode") == "wal"
        assert _pragma(reader, "busy_timeout") == 2_750
        assert _pragma(reader, "query_only") == 1
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("INSERT INTO hosts(host_key, display_name, first_seen_at, last_seen_at) VALUES ('x', 'x', '2026-01-01T00:00:00.000000Z', '2026-01-01T00:00:00.000000Z')")
    finally:
        reader.close()
        writer.close()


def test_fresh_ledger_contains_schema_freeze_bones(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    initialize_ledger(path)

    connection = connect_ledger_reader(path)
    try:
        version = connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
        ).fetchone()[0]
        assert int(version) == LEDGER_SCHEMA_VERSION
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "hosts",
            "volumes",
            "locations",
            "mappings",
            "inventory",
            "mapping_correspondence",
            "runs",
            "operations",
            "recording_commands",
            "annotations",
        } <= tables

        inventory_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(inventory)")
        }
        assert {
            "file_identity_volume_serial",
            "file_identity_file_index",
            "hardlink_group",
            "content_algorithm",
            "content_digest",
            "content_size",
            "hash_provenance",
            "content_observed_at",
            "attested_size",
            "attested_mtime_ns",
            "attested_file_identity_volume_serial",
            "attested_file_identity_file_index",
            "last_verified_at",
            "missing_since",
            "acknowledged_at",
            "excluded_at",
            "reappeared_at",
            "unsupported_reason",
        } <= inventory_columns
    finally:
        connection.close()


def test_schema_rejects_correspondence_rows_from_unrelated_locations(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    initialize_ledger(path)
    connection = connect_ledger_writer(path)
    now = "2026-01-01T00:00:00.000000Z"
    try:
        with connection:
            host_id = connection.execute(
                "INSERT INTO hosts(host_key, display_name, first_seen_at, last_seen_at) VALUES ('host', 'host', ?, ?) RETURNING id",
                (now, now),
            ).fetchone()[0]
            volume_id = connection.execute(
                "INSERT INTO volumes(serial, fs_type, first_seen_at, last_seen_at) VALUES ('serial', 'NTFS', ?, ?) RETURNING id",
                (now, now),
            ).fetchone()[0]
            locations = [
                connection.execute(
                    "INSERT INTO locations(volume_id, volume_relative_path, volume_relative_path_key, created_at, last_seen_at) VALUES (?, ?, ?, ?, ?) RETURNING id",
                    (volume_id, value, value.upper(), now, now),
                ).fetchone()[0]
                for value in ("source", "target", "unrelated")
            ]
            mapping_id = connection.execute(
                "INSERT INTO mappings(source_location_id, target_location_id, created_at) VALUES (?, ?, ?) RETURNING id",
                (locations[0], locations[1], now),
            ).fetchone()[0]
            rows = [
                connection.execute(
                    """INSERT INTO inventory(
                           location_id, rel_path, rel_path_key, entry_kind, presence,
                           observed_size, observed_mtime_ns, observed_nlink,
                           observed_attributes, last_observed_at, observation_host_id,
                           scope_token
                       ) VALUES (?, 'a.txt', 'A.TXT', 'file', 'present', 1, 1, 1, 0, ?, ?, 'scope')
                       RETURNING id""",
                    (location_id, now, host_id),
                ).fetchone()[0]
                for location_id in locations
            ]

        with pytest.raises(sqlite3.IntegrityError, match="correspondence location mismatch"):
            with connection:
                connection.execute(
                    """INSERT INTO mapping_correspondence(
                           mapping_id, source_inventory_id, target_inventory_id,
                           source_identity_volume_serial, source_identity_file_index,
                           last_seen_at, run_token, op_token
                       ) VALUES (?, ?, ?, 'serial', 1, ?, 'run', 'op')""",
                    (mapping_id, rows[0], rows[2], now),
                )
    finally:
        connection.close()


def test_database_path_is_refused_inside_managed_root(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    managed.mkdir()
    with pytest.raises(DatabaseLocationError):
        validate_database_path(managed / "ledger.db", managed_roots=(managed,))

    outside = tmp_path / "local" / "ledger.db"
    assert validate_database_path(outside, managed_roots=(managed,)) == outside.resolve()


def _seed_schema_version(path: Path, version: int) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE schema_metadata "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT"
        )
        connection.execute(
            "INSERT INTO schema_metadata(key, value) "
            "VALUES ('schema_version', ?)",
            (str(version),),
        )
        connection.execute("CREATE TABLE legacy_marker (value TEXT) STRICT")
        connection.execute("INSERT INTO legacy_marker(value) VALUES ('preserve')")
        connection.commit()
    finally:
        connection.close()


@pytest.mark.parametrize("version", [1, 2])
def test_history_v1_and_v2_are_refused_without_mutation(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / f"history-v{version}.db"
    _seed_schema_version(path, version)

    with pytest.raises(SchemaResetRequired, match="reset both database files together"):
        initialize_history(path)

    connection = sqlite3.connect(path)
    try:
        retained_version = int(
            connection.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
        )
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        connection.close()

    assert retained_version == version
    assert tables == {"schema_metadata", "legacy_marker"}
    assert not path.with_name(path.name + "-wal").exists()
    assert not path.with_name(path.name + "-shm").exists()
    check = sqlite3.connect(path)
    try:
        assert check.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        check.close()


def test_ledger_v1_is_refused_without_mutation(tmp_path: Path) -> None:
    path = tmp_path / "ledger-v1.db"
    _seed_schema_version(path, 1)

    with pytest.raises(SchemaResetRequired, match="reset both database files together"):
        initialize_ledger(path)

    connection = sqlite3.connect(path)
    try:
        version = int(
            connection.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
        )
        marker = connection.execute("SELECT value FROM legacy_marker").fetchone()[0]
    finally:
        connection.close()

    assert version == 1
    assert marker == "preserve"
    assert not path.with_name(path.name + "-wal").exists()
    assert not path.with_name(path.name + "-shm").exists()
    check = sqlite3.connect(path)
    try:
        assert check.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        check.close()


def test_coordinated_reset_recreates_final_m1_schema_shapes(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    _seed_schema_version(ledger, 1)
    _seed_schema_version(history, 2)

    assert reset_databases(ledger, history) == (ledger.resolve(), history.resolve())

    ledger_reader = connect_ledger_reader(ledger)
    history_reader = connect_history_reader(history)
    try:
        ledger_version = int(
            ledger_reader.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
        )
        history_version = int(
            history_reader.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
        )
        history_tables = {
            row[0]
            for row in history_reader.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        item_columns = {
            row[1] for row in history_reader.execute("PRAGMA table_info(history_items)")
        }
        phase_columns = {
            row[1] for row in history_reader.execute("PRAGMA table_info(history_phases)")
        }
        phase_count = int(
            history_reader.execute("SELECT COUNT(*) FROM history_phases").fetchone()[0]
        )
    finally:
        history_reader.close()
        ledger_reader.close()

    assert ledger_version == LEDGER_SCHEMA_VERSION == 2
    assert history_version == HISTORY_SCHEMA_VERSION == 3
    assert {"history_items", "history_phases"} <= history_tables
    assert {"item_type", "phase", "item_id", "result", "detail_json"} <= item_columns
    assert {
        "phase_order",
        "phase",
        "status",
        "items_done",
        "items_total",
        "bytes_done",
        "bytes_total",
        "error",
        "detail_json",
    } <= phase_columns
    assert phase_count == 0
