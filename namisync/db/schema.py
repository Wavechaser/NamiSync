"""Owned SQLite schemas for the main ledger and independent history store."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .connections import (
    DEFAULT_BUSY_TIMEOUT_MS,
    connect_history_reader,
    connect_history_writer,
    connect_ledger_reader,
    connect_ledger_writer,
    validate_database_path,
)


LEDGER_SCHEMA_VERSION = 3
HISTORY_SCHEMA_VERSION = 4
LEDGER_CONTRACT_ID = "m1-ledger-xxh3-128-invalidation-v1"
HISTORY_CONTRACT_ID = "m1-history-windowed-events-v1"
MAX_HISTORY_PHASE_NAME_BYTES = 256
MAX_HISTORY_ERROR_TYPE_BYTES = 256
MAX_HISTORY_ERROR_MESSAGE_BYTES = 4_096


class SchemaResetRequired(sqlite3.DatabaseError):
    """An incompatible pre-release schema must be reset, never migrated."""


_LEDGER_SCHEMA = f"""
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

INSERT INTO schema_metadata(key, value)
VALUES ('schema_version', '{LEDGER_SCHEMA_VERSION}')
ON CONFLICT(key) DO NOTHING;

INSERT INTO schema_metadata(key, value)
VALUES ('contract_id', '{LEDGER_CONTRACT_ID}')
ON CONFLICT(key) DO NOTHING;

CREATE TABLE IF NOT EXISTS hosts (
    id INTEGER PRIMARY KEY,
    host_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS volumes (
    id INTEGER PRIMARY KEY,
    serial TEXT NOT NULL,
    fs_type TEXT NOT NULL,
    label TEXT,
    device_id TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(serial, fs_type)
) STRICT;

CREATE INDEX IF NOT EXISTS volumes_serial_idx ON volumes(serial);

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY,
    volume_id INTEGER NOT NULL REFERENCES volumes(id),
    volume_relative_path TEXT NOT NULL,
    volume_relative_path_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    rebound_at TEXT,
    UNIQUE(volume_id, volume_relative_path_key)
) STRICT;

CREATE TABLE IF NOT EXISTS mappings (
    id INTEGER PRIMARY KEY,
    source_location_id INTEGER NOT NULL REFERENCES locations(id),
    target_location_id INTEGER NOT NULL REFERENCES locations(id),
    created_at TEXT NOT NULL,
    deleted_at TEXT,
    CHECK(source_location_id <> target_location_id)
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS mappings_active_pair_uq
ON mappings(source_location_id, target_location_id)
WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id),
    rel_path TEXT NOT NULL,
    rel_path_key TEXT NOT NULL,
    entry_kind TEXT NOT NULL CHECK(entry_kind IN ('file', 'directory', 'unsupported')),
    presence TEXT NOT NULL CHECK(presence IN ('present', 'missing', 'unsupported')),

    observed_size INTEGER,
    observed_mtime_ns INTEGER,
    file_identity_volume_serial TEXT,
    file_identity_file_index INTEGER,
    observed_nlink INTEGER,
    observed_attributes INTEGER,
    observed_created_ns INTEGER,
    hardlink_group TEXT,
    last_observed_at TEXT,
    observation_host_id INTEGER REFERENCES hosts(id),
    scope_token TEXT NOT NULL,

    content_algorithm TEXT,
    content_digest BLOB,
    content_size INTEGER,
    hash_provenance TEXT,
    content_observed_at TEXT,
    attested_kind TEXT,
    attested_size INTEGER,
    attested_mtime_ns INTEGER,
    attested_file_identity_volume_serial TEXT,
    attested_file_identity_file_index INTEGER,
    attested_nlink INTEGER,
    attested_attributes INTEGER,
    attested_created_ns INTEGER,
    last_verified_at TEXT,
    verification_invalidated_at TEXT,
    verification_invalidated_reason TEXT CHECK(
        verification_invalidated_reason IS NULL
        OR verification_invalidated_reason IN ('metadata-drift', 'hash-mismatch')
    ),

    missing_since TEXT,
    acknowledged_at TEXT,
    reappeared_at TEXT,
    unsupported_reason TEXT,

    UNIQUE(location_id, rel_path_key),
    CHECK(
        (content_algorithm IS NULL AND content_digest IS NULL AND content_size IS NULL
         AND hash_provenance IS NULL AND content_observed_at IS NULL
         AND attested_kind IS NULL AND attested_size IS NULL AND attested_mtime_ns IS NULL
         AND attested_nlink IS NULL AND attested_attributes IS NULL)
        OR
        (content_algorithm IS NOT NULL AND content_digest IS NOT NULL AND content_size IS NOT NULL
         AND hash_provenance IS NOT NULL AND content_observed_at IS NOT NULL
         AND attested_kind IS NOT NULL AND attested_size IS NOT NULL AND attested_mtime_ns IS NOT NULL
         AND attested_nlink IS NOT NULL AND attested_attributes IS NOT NULL)
    ),
    CHECK(
        (verification_invalidated_at IS NULL)
        = (verification_invalidated_reason IS NULL)
    ),
    CHECK(
        verification_invalidated_reason IS NULL OR content_algorithm IS NOT NULL
    ),
    CHECK(last_verified_at IS NULL OR content_algorithm IS NOT NULL),
    CHECK(
        content_algorithm IS NULL
        OR verification_invalidated_at IS NOT NULL
        OR (
            presence = 'present'
            AND entry_kind IS attested_kind
            AND observed_size IS attested_size
            AND observed_mtime_ns IS attested_mtime_ns
            AND (
                (
                    attested_file_identity_volume_serial IS NULL
                    AND attested_file_identity_file_index IS NULL
                )
                OR (
                    file_identity_volume_serial
                        IS attested_file_identity_volume_serial
                    AND file_identity_file_index
                        IS attested_file_identity_file_index
                )
            )
        )
    )
) STRICT;

CREATE INDEX IF NOT EXISTS inventory_location_presence_idx
ON inventory(location_id, presence, rel_path_key);
CREATE INDEX IF NOT EXISTS inventory_identity_idx
ON inventory(location_id, file_identity_volume_serial, file_identity_file_index);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    run_token TEXT NOT NULL UNIQUE,
    activity_kind TEXT NOT NULL,
    host_id INTEGER NOT NULL REFERENCES hosts(id),
    mapping_id INTEGER REFERENCES mappings(id),
    source_location_id INTEGER REFERENCES locations(id),
    target_location_id INTEGER REFERENCES locations(id),
    plan_fingerprint TEXT,
    selection_digest BLOB,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    filesystem_status TEXT,
    recording_status TEXT,
    start_payload_hash BLOB NOT NULL,
    finish_payload_hash BLOB
) STRICT;

CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    op_token TEXT NOT NULL,
    kind TEXT NOT NULL,
    source_rel_path TEXT,
    target_rel_path TEXT NOT NULL,
    outcome TEXT NOT NULL,
    content_bytes INTEGER NOT NULL DEFAULT 0,
    trash_rel_path TEXT,
    recorded_at TEXT NOT NULL,
    payload_hash BLOB NOT NULL,
    UNIQUE(run_id, op_token)
) STRICT;

CREATE INDEX IF NOT EXISTS operations_run_order_idx ON operations(run_id, id);

CREATE TABLE IF NOT EXISTS mapping_correspondence (
    mapping_id INTEGER NOT NULL REFERENCES mappings(id) ON DELETE CASCADE,
    source_inventory_id INTEGER NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
    target_inventory_id INTEGER NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
    source_identity_volume_serial TEXT NOT NULL,
    source_identity_file_index INTEGER NOT NULL,
    target_identity_volume_serial TEXT,
    target_identity_file_index INTEGER,
    last_seen_at TEXT NOT NULL,
    run_token TEXT NOT NULL,
    op_token TEXT NOT NULL,
    PRIMARY KEY(mapping_id, source_inventory_id),
    UNIQUE(mapping_id, target_inventory_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS mapping_correspondence_locations_insert
BEFORE INSERT ON mapping_correspondence
WHEN NOT EXISTS (
    SELECT 1
      FROM mappings AS mapping
      JOIN inventory AS source_row ON source_row.id = NEW.source_inventory_id
      JOIN inventory AS target_row ON target_row.id = NEW.target_inventory_id
     WHERE mapping.id = NEW.mapping_id
       AND source_row.location_id = mapping.source_location_id
       AND target_row.location_id = mapping.target_location_id
)
BEGIN
    SELECT RAISE(ABORT, 'correspondence location mismatch');
END;

CREATE TRIGGER IF NOT EXISTS mapping_correspondence_locations_update
BEFORE UPDATE ON mapping_correspondence
WHEN NOT EXISTS (
    SELECT 1
      FROM mappings AS mapping
      JOIN inventory AS source_row ON source_row.id = NEW.source_inventory_id
      JOIN inventory AS target_row ON target_row.id = NEW.target_inventory_id
     WHERE mapping.id = NEW.mapping_id
       AND source_row.location_id = mapping.source_location_id
       AND target_row.location_id = mapping.target_location_id
)
BEGIN
    SELECT RAISE(ABORT, 'correspondence location mismatch');
END;

CREATE TABLE IF NOT EXISTS recording_commands (
    command_key TEXT PRIMARY KEY,
    command_kind TEXT NOT NULL,
    payload_hash BLOB NOT NULL,
    disposition TEXT NOT NULL,
    recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY,
    entity_kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    key TEXT NOT NULL CHECK(instr(key, '.') > 1),
    value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(entity_kind, entity_id, key)
) STRICT;

COMMIT;
"""


_HISTORY_SCHEMA = f"""
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

INSERT INTO schema_metadata(key, value)
VALUES ('schema_version', '{HISTORY_SCHEMA_VERSION}')
ON CONFLICT(key) DO NOTHING;

INSERT INTO schema_metadata(key, value)
VALUES ('contract_id', '{HISTORY_CONTRACT_ID}')
ON CONFLICT(key) DO NOTHING;

CREATE TABLE IF NOT EXISTS history_runs (
    id INTEGER PRIMARY KEY,
    run_token TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    activity_kind TEXT NOT NULL,
    host_key TEXT NOT NULL,
    subject_kind TEXT,
    subject_id TEXT,
    source_context TEXT,
    target_context TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    current_state TEXT NOT NULL,
    current_phase TEXT,
    last_committed_seq INTEGER NOT NULL DEFAULT 0
        CHECK(last_committed_seq >= 0),
    item_count INTEGER NOT NULL DEFAULT 0 CHECK(item_count >= 0),
    last_committed_at TEXT,
    context_hash BLOB NOT NULL,
    event_chain_hash BLOB NOT NULL,
    terminal_payload_hash BLOB,
    succeeded_count INTEGER NOT NULL DEFAULT 0 CHECK(succeeded_count >= 0),
    skipped_count INTEGER NOT NULL DEFAULT 0 CHECK(skipped_count >= 0),
    failed_count INTEGER NOT NULL DEFAULT 0 CHECK(failed_count >= 0),
    canceled_count INTEGER NOT NULL DEFAULT 0 CHECK(canceled_count >= 0),
    deferred_count INTEGER NOT NULL DEFAULT 0 CHECK(deferred_count >= 0),
    blocked_count INTEGER NOT NULL DEFAULT 0 CHECK(blocked_count >= 0),
    filesystem_status TEXT,
    recording_status TEXT,
    audit_status TEXT,
    disposition TEXT,
    canceled INTEGER CHECK(canceled IN (0, 1)),
    bytes_done INTEGER,
    bytes_total INTEGER,
    error_type TEXT CHECK(
        error_type IS NULL
        OR length(CAST(error_type AS BLOB)) <= {MAX_HISTORY_ERROR_TYPE_BYTES}
    ),
    error_message TEXT CHECK(
        error_message IS NULL
        OR length(CAST(error_message AS BLOB)) <= {MAX_HISTORY_ERROR_MESSAGE_BYTES}
    ),
    CHECK(ended_at IS NULL OR ended_at >= COALESCE(started_at, created_at)),
    CHECK(
        (
            terminal_payload_hash IS NULL
            AND ended_at IS NULL
            AND filesystem_status IS NULL
            AND recording_status IS NULL
            AND audit_status IS NULL
            AND disposition IS NULL
            AND canceled IS NULL
            AND bytes_done IS NULL
            AND bytes_total IS NULL
            AND error_type IS NULL
            AND error_message IS NULL
        )
        OR
        (
            terminal_payload_hash IS NOT NULL
            AND ended_at IS NOT NULL
            AND filesystem_status IS NOT NULL
            AND recording_status IS NOT NULL
            AND audit_status IS NOT NULL
            AND disposition IS NOT NULL
            AND canceled IS NOT NULL
            AND bytes_done IS NOT NULL
            AND bytes_done >= 0
            AND bytes_total IS NOT NULL
            AND bytes_total >= 0
            AND bytes_done <= bytes_total
            AND ((error_type IS NULL) = (error_message IS NULL))
        )
    )
) STRICT;

CREATE INDEX IF NOT EXISTS history_runs_started_idx
ON history_runs(COALESCE(started_at, created_at) DESC, id DESC);

CREATE TABLE IF NOT EXISTS history_events (
    run_id INTEGER NOT NULL REFERENCES history_runs(id) ON DELETE CASCADE,
    event_seq INTEGER NOT NULL CHECK(event_seq > 0),
    event_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK(schema_version > 0),
    body_type TEXT NOT NULL CHECK(length(body_type) > 0),
    envelope_json TEXT NOT NULL,
    payload_hash BLOB NOT NULL,
    item_order INTEGER CHECK(item_order IS NULL OR item_order > 0),
    item_type TEXT,
    phase TEXT,
    item_id TEXT,
    kind TEXT,
    path TEXT,
    result TEXT,
    reason TEXT,
    PRIMARY KEY(run_id, event_seq),
    UNIQUE(run_id, item_order),
    UNIQUE(run_id, item_type, item_id),
    CHECK(
        (
            item_order IS NULL
            AND item_type IS NULL
            AND phase IS NULL
            AND item_id IS NULL
            AND kind IS NULL
            AND path IS NULL
            AND result IS NULL
            AND reason IS NULL
        )
        OR
        (
            item_order IS NOT NULL
            AND item_type IS NOT NULL AND length(item_type) > 0
            AND phase IS NOT NULL AND length(phase) > 0
            AND item_id IS NOT NULL AND length(item_id) > 0
            AND kind IS NOT NULL AND length(kind) > 0
            AND path IS NOT NULL
            AND result IS NOT NULL AND length(result) > 0
        )
    )
) STRICT;

CREATE INDEX IF NOT EXISTS history_events_run_item_order_idx
ON history_events(run_id, item_order)
WHERE item_order IS NOT NULL;

CREATE INDEX IF NOT EXISTS history_events_run_item_aggregate_idx
ON history_events(run_id, item_type, phase, kind, result, reason)
WHERE item_order IS NOT NULL;

CREATE TABLE IF NOT EXISTS history_phases (
    run_id INTEGER NOT NULL REFERENCES history_runs(id) ON DELETE CASCADE,
    phase_order INTEGER NOT NULL CHECK(phase_order >= 0 AND phase_order < 256),
    phase TEXT NOT NULL CHECK(
        length(CAST(phase AS BLOB)) <= {MAX_HISTORY_PHASE_NAME_BYTES}
    ),
    status TEXT NOT NULL,
    items_done INTEGER NOT NULL,
    items_total INTEGER,
    bytes_done INTEGER NOT NULL,
    bytes_total INTEGER,
    error TEXT CHECK(
        error IS NULL
        OR length(CAST(error AS BLOB)) <= {MAX_HISTORY_ERROR_MESSAGE_BYTES}
    ),
    PRIMARY KEY(run_id, phase_order),
    UNIQUE(run_id, phase),
    CHECK(length(phase) > 0),
    CHECK(length(status) > 0),
    CHECK(items_done >= 0),
    CHECK(items_total IS NULL OR items_total >= items_done),
    CHECK(bytes_done >= 0),
    CHECK(bytes_total IS NULL OR bytes_total >= bytes_done)
) STRICT;

COMMIT;
"""


def _initialize(
    path: str | Path,
    schema: str,
    *,
    history: bool,
    busy_timeout_ms: int,
    managed_roots: Iterable[str | Path],
) -> Path:
    resolved = validate_database_path(path, managed_roots=managed_roots)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if resolved.exists():
        read = connect_history_reader if history else connect_ledger_reader
        readonly = read(resolved, busy_timeout_ms=busy_timeout_ms)
        try:
            version = _existing_schema_version(readonly, history=history)
            expected = HISTORY_SCHEMA_VERSION if history else LEDGER_SCHEMA_VERSION
            if version is not None and version != expected:
                _raise_reset_required(version, history=history)
            if version is not None:
                _require_contract_id(readonly, history=history)
        finally:
            readonly.close()
    connect = connect_history_writer if history else connect_ledger_writer
    connection = connect(resolved, busy_timeout_ms=busy_timeout_ms)
    try:
        version = _existing_schema_version(connection, history=history)
        expected = HISTORY_SCHEMA_VERSION if history else LEDGER_SCHEMA_VERSION
        if version is not None and version != expected:
            _raise_reset_required(version, history=history)
        if version is not None:
            _require_contract_id(connection, history=history)
        connection.executescript(schema)
        version = int(
            connection.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
        )
        if version != expected:
            _raise_reset_required(version, history=history)
        _require_contract_id(connection, history=history)
    finally:
        connection.close()
    return resolved


def _existing_schema_version(
    connection: sqlite3.Connection, *, history: bool
) -> int | None:
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if not tables:
        return None
    if "schema_metadata" not in tables:
        _raise_reset_required("unversioned", history=history)
    row = connection.execute(
        "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        _raise_reset_required("missing", history=history)
    try:
        return int(row[0])
    except (TypeError, ValueError):
        _raise_reset_required("invalid", history=history)


def _raise_reset_required(version: object, *, history: bool) -> None:
    database = "history" if history else "ledger"
    raise SchemaResetRequired(
        f"unsupported {database} schema version {version}; "
        "NamiSync M1 requires ledger v3 and history v4. "
        "Close every NamiSync process, manually delete or otherwise reset both "
        "database files together, and restart."
    )


def _require_contract_id(
    connection: sqlite3.Connection, *, history: bool
) -> None:
    expected = HISTORY_CONTRACT_ID if history else LEDGER_CONTRACT_ID
    row = connection.execute(
        "SELECT value FROM schema_metadata WHERE key = 'contract_id'"
    ).fetchone()
    actual = None if row is None else str(row[0])
    if actual != expected:
        database = "history" if history else "ledger"
        value = "missing" if actual is None else actual
        raise SchemaResetRequired(
            f"unsupported {database} schema contract {value}; "
            "NamiSync M1 requires ledger v3 and history v4 with the final "
            "M1 contract. Close every NamiSync process, manually delete or "
            "otherwise reset both database files together, and restart."
        )


def _validate_reader_contract(
    connection: sqlite3.Connection, *, history: bool
) -> None:
    version = _existing_schema_version(connection, history=history)
    expected = HISTORY_SCHEMA_VERSION if history else LEDGER_SCHEMA_VERSION
    if version != expected:
        _raise_reset_required(
            "empty" if version is None else version,
            history=history,
        )
    _require_contract_id(connection, history=history)


def validate_ledger_reader_contract(connection: sqlite3.Connection) -> None:
    """Refuse an incompatible ledger through an already read-only connection."""

    _validate_reader_contract(connection, history=False)


def validate_history_reader_contract(connection: sqlite3.Connection) -> None:
    """Refuse an incompatible history store through a read-only connection."""

    _validate_reader_contract(connection, history=True)


def initialize_ledger(
    path: str | Path,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    managed_roots: Iterable[str | Path] = (),
) -> Path:
    return _initialize(
        path,
        _LEDGER_SCHEMA,
        history=False,
        busy_timeout_ms=busy_timeout_ms,
        managed_roots=managed_roots,
    )


def initialize_history(
    path: str | Path,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    managed_roots: Iterable[str | Path] = (),
) -> Path:
    return _initialize(
        path,
        _HISTORY_SCHEMA,
        history=True,
        busy_timeout_ms=busy_timeout_ms,
        managed_roots=managed_roots,
    )


def reset_databases(
    ledger_path: str | Path,
    history_path: str | Path,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    managed_roots: Iterable[str | Path] = (),
) -> tuple[Path, Path]:
    """Destructively recreate the ledger and history as one explicit boundary."""

    roots = tuple(managed_roots)
    ledger = validate_database_path(ledger_path, managed_roots=roots)
    history = validate_database_path(history_path, managed_roots=roots)
    if ledger == history:
        raise ValueError("ledger and history databases must use distinct paths")
    for path in (ledger, history):
        path.parent.mkdir(parents=True, exist_ok=True)
    for path in (ledger, history):
        _delete_sqlite_artifacts(path)
    return (
        initialize_ledger(
            ledger,
            busy_timeout_ms=busy_timeout_ms,
            managed_roots=roots,
        ),
        initialize_history(
            history,
            busy_timeout_ms=busy_timeout_ms,
            managed_roots=roots,
        ),
    )


def _delete_sqlite_artifacts(path: Path) -> None:
    for candidate in (
        path,
        path.with_name(path.name + "-wal"),
        path.with_name(path.name + "-shm"),
        path.with_name(path.name + "-journal"),
    ):
        candidate.unlink(missing_ok=True)
