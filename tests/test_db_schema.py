from __future__ import annotations

from contextlib import closing
import os
import sqlite3
from pathlib import Path

import pytest

import namisync.db.history as history_module
import namisync.db.repositories as repositories_module
import namisync.db.schema as schema_module
from namisync.core.pathing import to_extended_length_path
from namisync.db.connections import (
    DatabaseLocationError,
    connect_history_reader,
    connect_history_writer,
    connect_ledger_reader,
    connect_ledger_writer,
    validate_database_path,
)
from namisync.db.history import HistoryRepository
from namisync.db.repositories import LedgerRepository
from namisync.db.schema import (
    HISTORY_CONTRACT_ID,
    HISTORY_SCHEMA_VERSION,
    LEDGER_CONTRACT_ID,
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


def test_history_connections_enforce_wal_foreign_keys_and_readonly(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    initialize_history(path, busy_timeout_ms=2_750)

    writer = connect_history_writer(path, busy_timeout_ms=2_750)
    reader = connect_history_reader(path, busy_timeout_ms=2_750)
    try:
        assert _pragma(writer, "foreign_keys") == 1
        assert _pragma(writer, "journal_mode") == "wal"
        assert _pragma(writer, "busy_timeout") == 2_750
        assert _pragma(writer, "recursive_triggers") == 1
        assert _pragma(reader, "foreign_keys") == 1
        assert _pragma(reader, "journal_mode") == "wal"
        assert _pragma(reader, "query_only") == 1
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("DELETE FROM history_runs")
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
            "verification_invalidated_at",
            "verification_invalidated_reason",
            "missing_since",
            "acknowledged_at",
            "reappeared_at",
            "unsupported_reason",
        } <= inventory_columns
    finally:
        connection.close()


def test_inventory_verification_invalidation_constraints_are_enforced(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.db"
    initialize_ledger(path)
    connection = connect_ledger_writer(path)
    now = "2026-01-01T00:00:00.000000Z"
    try:
        with connection:
            host_id = connection.execute(
                "INSERT INTO hosts(host_key, display_name, first_seen_at, last_seen_at) "
                "VALUES ('host', 'host', ?, ?) RETURNING id",
                (now, now),
            ).fetchone()[0]
            volume_id = connection.execute(
                "INSERT INTO volumes(serial, fs_type, first_seen_at, last_seen_at) "
                "VALUES ('serial', 'NTFS', ?, ?) RETURNING id",
                (now, now),
            ).fetchone()[0]
            location_id = connection.execute(
                """INSERT INTO locations(
                       volume_id, volume_relative_path,
                       volume_relative_path_key, created_at, last_seen_at
                   ) VALUES (?, 'root', 'ROOT', ?, ?) RETURNING id""",
                (volume_id, now, now),
            ).fetchone()[0]
            row_id = connection.execute(
                """INSERT INTO inventory(
                       location_id, rel_path, rel_path_key, entry_kind, presence,
                       observed_size, observed_mtime_ns, observed_nlink,
                       observed_attributes, last_observed_at,
                       observation_host_id, scope_token
                   ) VALUES (?, 'a.txt', 'A.TXT', 'file', 'present',
                             1, 1, 1, 0, ?, ?, 'scope')
                   RETURNING id""",
                (location_id, now, host_id),
            ).fetchone()[0]

        invalid_updates = (
            (
                "UPDATE inventory SET verification_invalidated_at = ? WHERE id = ?",
                (now, row_id),
            ),
            (
                """UPDATE inventory
                      SET verification_invalidated_at = ?,
                          verification_invalidated_reason = 'metadata-drift'
                    WHERE id = ?""",
                (now, row_id),
            ),
            (
                "UPDATE inventory SET last_verified_at = ? WHERE id = ?",
                (now, row_id),
            ),
        )
        for statement, parameters in invalid_updates:
            with pytest.raises(sqlite3.IntegrityError):
                with connection:
                    connection.execute(statement, parameters)

        with connection:
            connection.execute(
                """UPDATE inventory SET
                       content_algorithm = 'xxh3_128',
                       content_digest = zeroblob(16), content_size = 1,
                       hash_provenance = 'verify', content_observed_at = ?,
                       attested_kind = 'file', attested_size = 1,
                       attested_mtime_ns = 1, attested_nlink = 1,
                       attested_attributes = 0, last_verified_at = ?
                     WHERE id = ?""",
                (now, now, row_id),
            )

        with pytest.raises(sqlite3.IntegrityError):
            with connection:
                connection.execute(
                    "UPDATE inventory SET observed_size = 2 WHERE id = ?",
                    (row_id,),
                )

        with connection:
            connection.execute(
                """UPDATE inventory
                      SET observed_size = 2,
                          verification_invalidated_at = ?,
                          verification_invalidated_reason = 'metadata-drift'
                    WHERE id = ?""",
                (now, row_id),
            )
        row = connection.execute(
            """SELECT observed_size, verification_invalidated_reason
                 FROM inventory WHERE id = ?""",
            (row_id,),
        ).fetchone()
        assert tuple(row) == (2, "metadata-drift")
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


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths")
def test_database_guard_resolves_deep_managed_roots_without_prefix_leak(
    tmp_path: Path,
) -> None:
    managed = tmp_path / ("m" * 90) / ("n" * 90) / ("o" * 90)
    assert len(str(managed)) > 260
    os.makedirs(to_extended_length_path(str(managed)))

    with pytest.raises(DatabaseLocationError):
        validate_database_path(
            managed / "ledger.db", managed_roots=(managed,)
        )

    outside = tmp_path / "local" / "ledger.db"
    resolved = validate_database_path(outside, managed_roots=(managed,))
    assert resolved == outside.resolve()
    assert not str(resolved).startswith("\\\\?\\")


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


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_superseded_history_versions_are_refused_without_mutation(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / f"history-v{version}.db"
    _seed_schema_version(path, version)

    with pytest.raises(
        SchemaResetRequired,
        match="history v6.*archive or delete both database main files",
    ):
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


@pytest.mark.parametrize("version", [1, 2, 3])
def test_superseded_ledger_versions_are_refused_without_mutation(
    tmp_path: Path,
    version: int,
) -> None:
    path = tmp_path / f"ledger-v{version}.db"
    _seed_schema_version(path, version)

    with pytest.raises(
        SchemaResetRequired,
        match="ledger v4 and history v6 at data epoch 5.*archive or delete",
    ):
        initialize_ledger(path)

    connection = sqlite3.connect(path)
    try:
        retained_version = int(
            connection.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
        )
        marker = connection.execute("SELECT value FROM legacy_marker").fetchone()[0]
    finally:
        connection.close()

    assert retained_version == version
    assert marker == "preserve"
    assert not path.with_name(path.name + "-wal").exists()
    assert not path.with_name(path.name + "-shm").exists()
    check = sqlite3.connect(path)
    try:
        assert check.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        check.close()


def test_event_v5_coordinated_reset_recreates_exact_database_epoch(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    _seed_schema_version(ledger, 1)
    _seed_schema_version(history, 2)
    ledger.with_name(ledger.name + "-journal").write_bytes(b"stale-ledger")
    history.with_name(history.name + "-journal").write_bytes(b"stale-history")

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
        ledger_contract = ledger_reader.execute(
            "SELECT value FROM schema_metadata WHERE key = 'contract_id'"
        ).fetchone()[0]
        history_contract = history_reader.execute(
            "SELECT value FROM schema_metadata WHERE key = 'contract_id'"
        ).fetchone()[0]
        ledger_epoch = ledger_reader.execute(
            "SELECT value FROM schema_metadata WHERE key = 'data_epoch'"
        ).fetchone()[0]
        history_epoch = history_reader.execute(
            "SELECT value FROM schema_metadata WHERE key = 'data_epoch'"
        ).fetchone()[0]
        ledger_tables = {
            row[0]
            for row in ledger_reader.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        history_tables = {
            row[0]
            for row in history_reader.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        run_columns = {
            row[1] for row in history_reader.execute("PRAGMA table_info(history_runs)")
        }
        event_column_rows = tuple(
            history_reader.execute("PRAGMA table_xinfo(history_events)")
        )
        event_columns = {row[1] for row in event_column_rows}
        phase_columns = {
            row[1] for row in history_reader.execute("PRAGMA table_info(history_phases)")
        }
        phase_count = int(
            history_reader.execute("SELECT COUNT(*) FROM history_phases").fetchone()[0]
        )
    finally:
        history_reader.close()
        ledger_reader.close()

    assert ledger_version == LEDGER_SCHEMA_VERSION == 4
    assert history_version == HISTORY_SCHEMA_VERSION == 6
    assert ledger_epoch == history_epoch == "5"
    assert (
        ledger_contract
        == LEDGER_CONTRACT_ID
        == "m1-ledger-v4-event-v5-evidence-v1"
    )
    assert (
        history_contract
        == HISTORY_CONTRACT_ID
        == "m1-history-v6-event-v5-recording-v1"
    )
    assert not ledger.with_name(ledger.name + "-journal").exists()
    assert not history.with_name(history.name + "-journal").exists()
    assert {"history_runs", "history_events", "history_phases"} <= history_tables
    assert "history_items" not in history_tables
    assert {
        "created_at",
        "started_at",
        "ended_at",
        "current_state",
        "current_phase",
        "last_committed_seq",
        "item_count",
        "duplicate_item_count",
        "rejected_event_count",
        "last_committed_at",
        "context_hash",
        "event_chain_hash",
        "prefix_projection_hash",
        "terminal_payload_hash",
        "recording_degraded_items",
        "recording_issues_json",
        "omitted_detail_count",
        "review_reason",
        "review_tree_kind",
        "review_population",
        "review_axis",
        "review_row_limit",
        "review_byte_limit",
    } <= run_columns
    assert {
        "event_seq",
        "event_at",
        "schema_version",
        "body_type",
        "event_disposition",
        "envelope_json",
        "payload_hash",
        "receipt_hash",
        "item_identity_hash",
        "item_payload_hash",
        "duplicate_of_seq",
        "rejection_reason",
        "item_order",
        "item_type",
        "phase",
        "item_id",
        "result",
        "recording",
        "recording_reason",
        "recording_detail",
        "detail_omitted_count",
    } <= event_columns
    generated_event_columns = {
        row[1] for row in event_column_rows if int(row[6]) == 3
    }
    assert generated_event_columns == set()
    assert {
        "phase_order",
        "phase",
        "status",
        "items_done",
        "items_total",
        "bytes_done",
        "bytes_total",
        "error",
    } <= phase_columns
    assert phase_count == 0


@pytest.mark.parametrize(
    ("initializer", "version", "name"),
    [
        (initialize_ledger, LEDGER_SCHEMA_VERSION, "ledger"),
        (initialize_history, HISTORY_SCHEMA_VERSION, "history"),
    ],
)
def test_transitional_current_version_without_contract_is_refused_read_only(
    tmp_path: Path, initializer, version: int, name: str
) -> None:
    path = tmp_path / f"{name}-transitional.db"
    _seed_schema_version(path, version)

    with pytest.raises(
        SchemaResetRequired,
        match="archive or delete both database main files",
    ):
        initializer(path)

    connection = sqlite3.connect(path)
    try:
        metadata = dict(connection.execute("SELECT key, value FROM schema_metadata"))
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        connection.close()
    assert metadata == {"schema_version": str(version)}
    assert tables == {"schema_metadata", "legacy_marker"}
    assert journal_mode == "delete"
    assert not path.with_name(path.name + "-wal").exists()
    assert not path.with_name(path.name + "-shm").exists()


@pytest.mark.parametrize(
    ("initializer", "version", "name"),
    [
        (initialize_ledger, LEDGER_SCHEMA_VERSION, "ledger"),
        (initialize_history, HISTORY_SCHEMA_VERSION, "history"),
    ],
)
def test_mismatched_contract_is_refused_without_backfill(
    tmp_path: Path, initializer, version: int, name: str
) -> None:
    path = tmp_path / f"{name}-mismatch.db"
    _seed_schema_version(path, version)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO schema_metadata(key, value) VALUES ('contract_id', 'wrong')"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(SchemaResetRequired, match="schema contract wrong"):
        initializer(path)

    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'contract_id'"
        ).fetchone()[0] == "wrong"
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        connection.close()


def test_reopening_complete_contract_is_schema_noop(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    reset_databases(ledger, history)

    before: list[tuple[int, tuple[tuple[object, ...], ...]]] = []
    for path in (ledger, history):
        connection = sqlite3.connect(path)
        try:
            before.append(
                (
                    int(connection.execute("PRAGMA schema_version").fetchone()[0]),
                    tuple(
                        connection.execute(
                            """SELECT type, name, sql FROM sqlite_master
                                WHERE name NOT LIKE 'sqlite_%'
                                ORDER BY type, name"""
                        )
                    ),
                )
            )
        finally:
            connection.close()

    initialize_ledger(ledger)
    initialize_history(history)

    after: list[tuple[int, tuple[tuple[object, ...], ...]]] = []
    for path in (ledger, history):
        connection = sqlite3.connect(path)
        try:
            after.append(
                (
                    int(connection.execute("PRAGMA schema_version").fetchone()[0]),
                    tuple(
                        connection.execute(
                            """SELECT type, name, sql FROM sqlite_master
                                WHERE name NOT LIKE 'sqlite_%'
                                ORDER BY type, name"""
                        )
                    ),
                )
            )
        finally:
            connection.close()
    assert after == before


@pytest.mark.parametrize("history", [False, True], ids=["ledger-v4", "history-v6"])
@pytest.mark.parametrize("layout", ["fresh", "populated", "relocated"])
def test_exact_schema_topology_accepts_complete_definitions_without_writes(
    history: bool, layout: str,
) -> None:
    script = schema_module._HISTORY_SCHEMA if history else schema_module._LEDGER_SCHEMA
    with closing(sqlite3.connect(":memory:")) as connection:
        if layout == "relocated":
            connection.execute("CREATE TABLE padding (value BLOB)")
            connection.execute("INSERT INTO padding VALUES (zeroblob(32768))")
        connection.executescript(script)
        if layout == "populated":
            connection.execute("INSERT INTO schema_metadata VALUES ('fixture', 'preserve')")
        elif layout == "relocated":
            connection.execute("DROP TABLE padding")
        connection.commit()
        before = connection.serialize()
        connection.row_factory = sqlite3.Row
        connection.set_authorizer(
            lambda action, *_: (
                sqlite3.SQLITE_OK
                if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ}
                else sqlite3.SQLITE_DENY
            )
        )
        assert schema_module._validate_schema_topology(connection, history=history) is None
        connection.set_authorizer(None)
        assert connection.serialize() == before
        assert not connection.in_transaction
        if layout == "relocated":
            pages = tuple(connection.execute("SELECT rootpage FROM sqlite_schema"))
            connection.execute("VACUUM")
            assert tuple(connection.execute("SELECT rootpage FROM sqlite_schema")) != pages
            schema_module._validate_schema_topology(connection, history=history)


@pytest.mark.parametrize("history", [False, True], ids=["ledger-v4", "history-v6"])
def test_exact_schema_topology_is_main_only_and_preserves_caller_transaction(history: bool) -> None:
    script = schema_module._HISTORY_SCHEMA if history else schema_module._LEDGER_SCHEMA
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.executescript(script)
        connection.execute("ATTACH DATABASE ':memory:' AS unrelated")
        connection.execute("CREATE TABLE unrelated.untrusted (value TEXT)")
        connection.execute("CREATE TEMP TABLE untrusted (value TEXT)")
        connection.execute("BEGIN")
        connection.execute("INSERT INTO schema_metadata VALUES ('fixture', 'uncommitted')")
        before = connection.serialize()
        schema_module._validate_schema_topology(connection, history=history)
        assert connection.in_transaction
        assert connection.serialize() == before
        connection.rollback()
        assert connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'fixture'"
        ).fetchone() is None


@pytest.mark.parametrize("history", [False, True], ids=["ledger-v4", "history-v6"])
@pytest.mark.parametrize("shape", [
    "empty", "marker-only", "missing-table", "missing-index", "missing-trigger",
    "missing-autoindex", "poisoned-table", "extra-table", "extra-view",
    "extra-index", "extra-trigger", "sqlite-wildcard-lookalike",
])
def test_exact_schema_topology_refuses_incomplete_or_extra_objects(
    history: bool, shape: str,
) -> None:
    script = schema_module._HISTORY_SCHEMA if history else schema_module._LEDGER_SCHEMA
    if shape == "marker-only":
        first_table = "history_runs" if history else "hosts"
        script = script.split(f"CREATE TABLE IF NOT EXISTS {first_table}", 1)[0] + "COMMIT;"
    with closing(sqlite3.connect(":memory:")) as connection:
        if shape != "empty":
            connection.executescript(script)
        if shape == "missing-table":
            connection.execute("DROP TABLE " + ("history_phases" if history else "annotations"))
        elif shape in {"missing-index", "missing-trigger"}:
            kind = shape.removeprefix("missing-")
            name = connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = ? AND sql IS NOT NULL LIMIT 1",
                (kind,),
            ).fetchone()[0]
            connection.execute(f'DROP {kind} "{name}"')
        elif shape == "missing-autoindex":
            connection.execute("PRAGMA writable_schema = ON")
            connection.execute(
                "DELETE FROM sqlite_schema WHERE name = 'sqlite_autoindex_schema_metadata_1'"
            )
        elif shape == "poisoned-table":
            connection.execute("ALTER TABLE schema_metadata ADD COLUMN untrusted TEXT")
        elif shape.startswith("extra-") or shape == "sqlite-wildcard-lookalike":
            connection.executescript({
                "extra-table": "CREATE TABLE untrusted (value TEXT)",
                "extra-view": "CREATE VIEW untrusted AS SELECT * FROM schema_metadata",
                "extra-index": "CREATE INDEX untrusted ON schema_metadata(value)",
                "extra-trigger": (
                    "CREATE TRIGGER untrusted AFTER INSERT ON schema_metadata "
                    "BEGIN SELECT 1; END"
                ),
                "sqlite-wildcard-lookalike": "CREATE TABLE sqliteXextra (value TEXT)",
            }[shape])
        connection.commit()
        before = connection.serialize() if shape != "empty" else None
        with pytest.raises(SchemaResetRequired, match="schema topology"):
            schema_module._validate_schema_topology(connection, history=history)
        if before is not None:
            assert connection.serialize() == before


@pytest.mark.parametrize("history", [False, True], ids=["ledger-v4", "history-v6"])
@pytest.mark.parametrize("change", [
    "type", "nullability", "unique", "default", "strict", "check", "foreign-key",
    "index-expression", "index-order", "index-predicate", "trigger-body", "literal-case",
    "literal-whitespace",
])
def test_exact_schema_topology_refuses_definition_drift(history: bool, change: str) -> None:
    script = schema_module._HISTORY_SCHEMA if history else schema_module._LEDGER_SCHEMA
    literal = "finalized history runs are immutable" if history else "correspondence location mismatch"
    before, after = {
        "type": ("value TEXT NOT NULL", "value ANY NOT NULL"),
        "nullability": ("value TEXT NOT NULL", "value TEXT"),
        "unique": (
            ("run_token TEXT NOT NULL UNIQUE", "run_token TEXT NOT NULL")
            if history else ("host_key TEXT NOT NULL UNIQUE", "host_key TEXT NOT NULL")
        ),
        "default": ("DEFAULT 0", "DEFAULT 1"),
        "strict": (") STRICT;", ");"),
        "check": (
            ("last_committed_seq BETWEEN 0 AND 9007199254740991", "last_committed_seq >= 0")
            if history else ("CHECK(source_location_id <> target_location_id)", "CHECK(1)")
        ),
        "foreign-key": (
            ("REFERENCES history_runs(id) ON DELETE CASCADE", "REFERENCES history_runs(id)")
            if history else ("REFERENCES volumes(id)", "REFERENCES volumes(id) ON DELETE CASCADE")
        ),
        "index-expression": (
            ("COALESCE(started_at, created_at)", "COALESCE(created_at, started_at)")
            if history else ("ON volumes(serial)", "ON volumes(lower(serial))")
        ),
        "index-order": (
            ("created_at) DESC, id DESC", "created_at) ASC, id DESC")
            if history else ("ON operations(run_id, id)", "ON operations(id, run_id)")
        ),
        "index-predicate": (
            ("WHERE item_order IS NOT NULL;", "WHERE item_order > 0;")
            if history else ("WHERE deleted_at IS NULL;", "WHERE deleted_at IS NOT NULL;")
        ),
        "trigger-body": (f"RAISE(ABORT, '{literal}')", "RAISE(IGNORE)"),
        "literal-case": (literal, literal.upper()),
        "literal-whitespace": (literal, literal.replace(" ", "  ")),
    }[change]
    assert before in script
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.executescript(script.replace(before, after, 1))
        with pytest.raises(SchemaResetRequired, match="schema topology"):
            schema_module._validate_schema_topology(connection, history=history)


def test_exact_schema_topology_refuses_loss_of_without_rowid() -> None:
    script = schema_module._HISTORY_SCHEMA
    assert script.count("STRICT, WITHOUT ROWID") == 1
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.executescript(script.replace("STRICT, WITHOUT ROWID", "STRICT"))
        with pytest.raises(SchemaResetRequired, match="schema topology"):
            schema_module._validate_schema_topology(connection, history=True)


@pytest.mark.parametrize("history", [False, True], ids=["ledger-v4", "history-v6"])
@pytest.mark.parametrize("statistics", ["analyze", "stat4"])
def test_exact_schema_topology_allows_only_declared_statistics_tables(
    history: bool, statistics: str,
) -> None:
    script = schema_module._HISTORY_SCHEMA if history else schema_module._LEDGER_SCHEMA
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.executescript(script)
        if statistics == "analyze":
            connection.execute("ANALYZE")
            assert connection.execute(
                "SELECT sql FROM sqlite_schema WHERE name = 'sqlite_stat1'"
            ).fetchone() == ("CREATE TABLE sqlite_stat1(tbl,idx,stat)",)
        else:
            # Pin optional STAT4's catalog shape even on builds without STAT4.
            connection.execute("PRAGMA writable_schema = ON")
            connection.execute(
                "INSERT INTO sqlite_schema(type,name,tbl_name,rootpage,sql) VALUES(?,?,?,?,?)",
                ("table", "sqlite_stat4", "sqlite_stat4", 0,
                 "CREATE TABLE sqlite_stat4(tbl,idx,neq,nlt,ndlt,sample)"),
            )
        connection.commit()
        before = connection.serialize()
        schema_module._validate_schema_topology(connection, history=history)
        assert connection.serialize() == before


@pytest.mark.parametrize("history", [False, True], ids=["ledger-v4", "history-v6"])
@pytest.mark.parametrize("poison", [
    "type", "owner", "definition", "duplicate", "undeclared-table", "index", "trigger",
])
def test_exact_schema_topology_refuses_statistics_spoofing(history: bool, poison: str) -> None:
    script = schema_module._HISTORY_SCHEMA if history else schema_module._LEDGER_SCHEMA
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.executescript(script)
        connection.execute("ANALYZE")
        row = connection.execute(
            "SELECT type,name,tbl_name,rootpage,sql FROM sqlite_schema WHERE name = 'sqlite_stat1'"
        ).fetchone()
        connection.execute("PRAGMA writable_schema = ON")
        if poison in {"type", "owner", "definition"}:
            column, value = {
                "type": ("type", "view"),
                "owner": ("tbl_name", "schema_metadata"),
                "definition": ("sql", "CREATE TABLE sqlite_stat1(tbl,idx,stat,untrusted)"),
            }[poison]
            connection.execute(
                f"UPDATE sqlite_schema SET {column} = ? WHERE name = 'sqlite_stat1'", (value,)
            )
        else:
            added = {
                "duplicate": row,
                "undeclared-table": (
                    "table", "sqlite_stat3", "sqlite_stat3", 0,
                    "CREATE TABLE sqlite_stat3(tbl,idx,neq,nlt,ndlt,sample)",
                ),
                "index": ("index", "untrusted", "sqlite_stat1", 0,
                          "CREATE INDEX untrusted ON sqlite_stat1(tbl)"),
                "trigger": ("trigger", "untrusted", "sqlite_stat1", 0,
                            "CREATE TRIGGER untrusted AFTER INSERT ON sqlite_stat1 BEGIN SELECT 1; END"),
            }[poison]
            connection.execute(
                "INSERT INTO sqlite_schema(type,name,tbl_name,rootpage,sql) VALUES(?,?,?,?,?)", added,
            )
        connection.commit()
        before = connection.serialize()
        with pytest.raises(SchemaResetRequired, match="schema topology"):
            schema_module._validate_schema_topology(connection, history=history)
        assert connection.serialize() == before


@pytest.mark.parametrize("history", [False, True], ids=["ledger-v4", "history-v6"])
def test_exact_schema_topology_does_not_replace_marker_value_validation(history: bool) -> None:
    script = schema_module._HISTORY_SCHEMA if history else schema_module._LEDGER_SCHEMA
    validate = (
        schema_module.validate_history_reader_contract
        if history else schema_module.validate_ledger_reader_contract
    )
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.executescript(script)
        connection.execute("UPDATE schema_metadata SET value = 'wrong' WHERE key = 'contract_id'")
        schema_module._validate_schema_topology(connection, history=history)
        with pytest.raises(SchemaResetRequired, match="schema contract wrong"):
            validate(connection)


def test_exact_schema_topology_is_not_selected_by_production_callers_yet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from namisync.db.contracts import history_file_contract_matches, ledger_file_contract_matches
    from namisync.workflows.database_pair import validate_database_pair

    def unexpected(*args, **kwargs):
        pytest.fail("the preparatory topology authority must remain dormant")

    monkeypatch.setattr(schema_module, "_validate_schema_topology", unexpected, raising=False)
    ledger = initialize_ledger(tmp_path / "ledger.db")
    history = initialize_history(tmp_path / "history.db")
    initialize_ledger(ledger)
    initialize_history(history)
    with closing(connect_ledger_reader(ledger)) as connection:
        schema_module.validate_ledger_reader_contract(connection)
    with closing(connect_history_reader(history)) as connection:
        schema_module.validate_history_reader_contract(connection)
    LedgerRepository(ledger).close()
    HistoryRepository(history).close()
    assert ledger_file_contract_matches(ledger)
    assert history_file_contract_matches(history)
    assert validate_database_pair(ledger, history).state == "ready"


def _sqlite_artifact_snapshot(path: Path) -> dict[str, bytes | None]:
    return {
        suffix: (
            candidate.read_bytes() if candidate.exists() else None
        )
        for suffix in ("", "-wal", "-shm", "-journal")
        for candidate in (path.with_name(path.name + suffix),)
    }


@pytest.mark.parametrize(
    ("repository_type", "version", "name"),
    [
        (LedgerRepository, LEDGER_SCHEMA_VERSION, "ledger"),
        (HistoryRepository, HISTORY_SCHEMA_VERSION, "history"),
    ],
)
@pytest.mark.parametrize(
    "shape",
    ["old", "markerless", "mismatched", "unversioned", "empty"],
)
def test_read_repositories_refuse_incompatible_contracts_without_mutation(
    tmp_path: Path,
    repository_type,
    version: int,
    name: str,
    shape: str,
) -> None:
    path = tmp_path / f"{name}-{shape}.db"
    if shape == "empty":
        sqlite3.connect(path).close()
    elif shape == "unversioned":
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE legacy_marker (value TEXT)")
            connection.execute(
                "INSERT INTO legacy_marker(value) VALUES ('preserve')"
            )
            connection.commit()
        finally:
            connection.close()
    else:
        _seed_schema_version(
            path,
            version - 1 if shape == "old" else version,
        )
        if shape == "mismatched":
            connection = sqlite3.connect(path)
            try:
                connection.execute(
                    """INSERT INTO schema_metadata(key, value)
                       VALUES ('contract_id', 'wrong')"""
                )
                connection.commit()
            finally:
                connection.close()
    before = _sqlite_artifact_snapshot(path)

    with pytest.raises(
        SchemaResetRequired, match="archive or delete both database main files"
    ):
        repository_type(path)

    assert _sqlite_artifact_snapshot(path) == before


@pytest.mark.parametrize(
    ("repository_type", "module", "connect_name"),
    [
        (LedgerRepository, repositories_module, "connect_ledger_reader"),
        (HistoryRepository, history_module, "connect_history_reader"),
    ],
)
def test_read_repositories_close_reader_when_contract_validation_refuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repository_type,
    module,
    connect_name: str,
) -> None:
    path = tmp_path / f"{repository_type.__name__}.db"
    sqlite3.connect(path).close()
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)

    class TrackedReader:
        closed = False

        def execute(self, statement: str, parameters=()):
            return connection.execute(statement, parameters)

        def close(self) -> None:
            self.closed = True
            connection.close()

    reader = TrackedReader()
    monkeypatch.setattr(module, connect_name, lambda *args, **kwargs: reader)

    with pytest.raises(SchemaResetRequired):
        repository_type(path)

    assert reader.closed
