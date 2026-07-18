"""Owned SQLite schemas for the main ledger and independent history store."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .connections import (
    DEFAULT_BUSY_TIMEOUT_MS,
    connect_history_writer,
    connect_ledger_writer,
    validate_database_path,
)


LEDGER_SCHEMA_VERSION = 1
HISTORY_SCHEMA_VERSION = 1


_LEDGER_SCHEMA = f"""
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

INSERT INTO schema_metadata(key, value)
VALUES ('schema_version', '{LEDGER_SCHEMA_VERSION}')
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

    missing_since TEXT,
    acknowledged_at TEXT,
    excluded_at TEXT,
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
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    filesystem_status TEXT NOT NULL,
    recording_status TEXT NOT NULL,
    audit_status TEXT NOT NULL,
    disposition TEXT NOT NULL,
    canceled INTEGER NOT NULL CHECK(canceled IN (0, 1)),
    bytes_done INTEGER NOT NULL,
    bytes_total INTEGER NOT NULL,
    succeeded_count INTEGER NOT NULL,
    skipped_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    canceled_count INTEGER NOT NULL,
    deferred_count INTEGER NOT NULL,
    error_type TEXT,
    error_message TEXT,
    payload_hash BLOB NOT NULL,
    CHECK(ended_at >= started_at)
) STRICT;

CREATE INDEX IF NOT EXISTS history_runs_started_idx
ON history_runs(started_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS history_operations (
    run_id INTEGER NOT NULL REFERENCES history_runs(id) ON DELETE CASCADE,
    item_order INTEGER NOT NULL,
    event_seq INTEGER,
    item_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    outcome TEXT NOT NULL,
    reason TEXT,
    detail_json TEXT NOT NULL,
    PRIMARY KEY(run_id, item_order),
    UNIQUE(run_id, item_id)
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
    connect = connect_history_writer if history else connect_ledger_writer
    connection = connect(resolved, busy_timeout_ms=busy_timeout_ms)
    try:
        connection.executescript(schema)
        version = int(
            connection.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
        )
        expected = HISTORY_SCHEMA_VERSION if history else LEDGER_SCHEMA_VERSION
        if version != expected:
            raise sqlite3.DatabaseError(
                f"unsupported schema version {version}; expected {expected}"
            )
    finally:
        connection.close()
    return resolved


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
