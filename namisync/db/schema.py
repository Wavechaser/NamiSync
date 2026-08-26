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


LEDGER_SCHEMA_VERSION = 4
HISTORY_SCHEMA_VERSION = 6
DATA_EPOCH = 5
LEDGER_CONTRACT_ID = "m1-ledger-v4-event-v5-evidence-v1"
HISTORY_CONTRACT_ID = "m1-history-v6-event-v5-recording-v1"
MAX_HISTORY_PHASE_NAME_BYTES = 1_024
MAX_HISTORY_ERROR_TYPE_BYTES = 1_024
MAX_HISTORY_ERROR_MESSAGE_BYTES = 1_024


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

INSERT INTO schema_metadata(key, value)
VALUES ('data_epoch', '{DATA_EPOCH}')
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

    observed_size INTEGER CHECK(observed_size IS NULL OR observed_size >= 0),
    observed_mtime_ns INTEGER CHECK(
        observed_mtime_ns IS NULL OR observed_mtime_ns >= 0
    ),
    file_identity_volume_serial TEXT,
    file_identity_file_index TEXT,
    observed_nlink INTEGER CHECK(observed_nlink IS NULL OR observed_nlink >= 1),
    observed_attributes INTEGER CHECK(
        observed_attributes IS NULL OR observed_attributes >= 0
    ),
    observed_created_ns INTEGER CHECK(
        observed_created_ns IS NULL OR observed_created_ns >= 0
    ),
    hardlink_group TEXT,
    last_observed_at TEXT,
    observation_host_id INTEGER REFERENCES hosts(id),
    scope_token TEXT NOT NULL,

    content_algorithm TEXT,
    content_digest BLOB,
    content_size INTEGER CHECK(content_size IS NULL OR content_size >= 0),
    hash_provenance TEXT,
    content_observed_at TEXT,
    attested_kind TEXT,
    attested_size INTEGER CHECK(attested_size IS NULL OR attested_size >= 0),
    attested_mtime_ns INTEGER CHECK(
        attested_mtime_ns IS NULL OR attested_mtime_ns >= 0
    ),
    attested_file_identity_volume_serial TEXT,
    attested_file_identity_file_index TEXT,
    attested_nlink INTEGER CHECK(attested_nlink IS NULL OR attested_nlink >= 1),
    attested_attributes INTEGER CHECK(
        attested_attributes IS NULL OR attested_attributes >= 0
    ),
    attested_created_ns INTEGER CHECK(
        attested_created_ns IS NULL OR attested_created_ns >= 0
    ),
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
        (file_identity_volume_serial IS NULL)
        = (file_identity_file_index IS NULL)
    ),
    CHECK(
        (attested_file_identity_volume_serial IS NULL)
        = (attested_file_identity_file_index IS NULL)
    ),
    CHECK(
        file_identity_file_index IS NULL OR (
            typeof(file_identity_file_index) = 'text'
            AND (
                file_identity_file_index = '0'
                OR (
                    file_identity_file_index NOT GLOB '*[^0-9]*'
                    AND substr(file_identity_file_index, 1, 1) BETWEEN '1' AND '9'
                    AND (
                        length(file_identity_file_index) < 39
                        OR (
                            length(file_identity_file_index) = 39
                            AND file_identity_file_index <=
                                '340282366920938463463374607431768211455'
                        )
                    )
                )
            )
        )
    ),
    CHECK(
        attested_file_identity_file_index IS NULL OR (
            typeof(attested_file_identity_file_index) = 'text'
            AND (
                attested_file_identity_file_index = '0'
                OR (
                    attested_file_identity_file_index NOT GLOB '*[^0-9]*'
                    AND substr(attested_file_identity_file_index, 1, 1)
                        BETWEEN '1' AND '9'
                    AND (
                        length(attested_file_identity_file_index) < 39
                        OR (
                            length(attested_file_identity_file_index) = 39
                            AND attested_file_identity_file_index <=
                                '340282366920938463463374607431768211455'
                        )
                    )
                )
            )
        )
    ),
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
    content_bytes INTEGER NOT NULL DEFAULT 0 CHECK(content_bytes >= 0),
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
    source_identity_file_index TEXT NOT NULL CHECK(
        typeof(source_identity_file_index) = 'text'
        AND (
            source_identity_file_index = '0'
            OR (
                source_identity_file_index NOT GLOB '*[^0-9]*'
                AND substr(source_identity_file_index, 1, 1) BETWEEN '1' AND '9'
                AND (
                    length(source_identity_file_index) < 39
                    OR (
                        length(source_identity_file_index) = 39
                        AND source_identity_file_index <=
                            '340282366920938463463374607431768211455'
                    )
                )
            )
        )
    ),
    target_identity_volume_serial TEXT,
    target_identity_file_index TEXT CHECK(
        target_identity_file_index IS NULL OR (
            typeof(target_identity_file_index) = 'text'
            AND (
                target_identity_file_index = '0'
                OR (
                    target_identity_file_index NOT GLOB '*[^0-9]*'
                    AND substr(target_identity_file_index, 1, 1) BETWEEN '1' AND '9'
                    AND (
                        length(target_identity_file_index) < 39
                        OR (
                            length(target_identity_file_index) = 39
                            AND target_identity_file_index <=
                                '340282366920938463463374607431768211455'
                        )
                    )
                )
            )
        )
    ),
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

INSERT INTO schema_metadata(key, value)
VALUES ('data_epoch', '{DATA_EPOCH}')
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
        CHECK(last_committed_seq BETWEEN 0 AND 9007199254740991),
    item_count INTEGER NOT NULL DEFAULT 0
        CHECK(item_count BETWEEN 0 AND 9007199254740991),
    duplicate_item_count INTEGER NOT NULL DEFAULT 0
        CHECK(duplicate_item_count BETWEEN 0 AND 9007199254740991),
    rejected_event_count INTEGER NOT NULL DEFAULT 0
        CHECK(rejected_event_count BETWEEN 0 AND 9007199254740991),
    last_committed_at TEXT,
    context_hash BLOB NOT NULL,
    event_chain_hash BLOB NOT NULL,
    prefix_projection_hash BLOB NOT NULL
        CHECK(length(prefix_projection_hash) = 32),
    terminal_payload_hash BLOB,
    succeeded_count INTEGER NOT NULL DEFAULT 0
        CHECK(succeeded_count BETWEEN 0 AND 9007199254740991),
    skipped_count INTEGER NOT NULL DEFAULT 0
        CHECK(skipped_count BETWEEN 0 AND 9007199254740991),
    failed_count INTEGER NOT NULL DEFAULT 0
        CHECK(failed_count BETWEEN 0 AND 9007199254740991),
    canceled_count INTEGER NOT NULL DEFAULT 0
        CHECK(canceled_count BETWEEN 0 AND 9007199254740991),
    deferred_count INTEGER NOT NULL DEFAULT 0
        CHECK(deferred_count BETWEEN 0 AND 9007199254740991),
    blocked_count INTEGER NOT NULL DEFAULT 0
        CHECK(blocked_count BETWEEN 0 AND 9007199254740991),
    filesystem_status TEXT,
    recording_status TEXT,
    audit_status TEXT,
    disposition TEXT,
    canceled INTEGER CHECK(canceled IN (0, 1)),
    bytes_done INTEGER,
    bytes_total INTEGER,
    recording_degraded_items INTEGER CHECK(
        recording_degraded_items IS NULL
        OR recording_degraded_items BETWEEN 0 AND 9007199254740991
    ),
    recording_issues_json TEXT CHECK(
        recording_issues_json IS NULL
        OR (
            json_valid(recording_issues_json)
            AND json_type(recording_issues_json, '$') = 'array'
            AND json_array_length(recording_issues_json) <= 5
        )
    ),
    omitted_detail_count INTEGER CHECK(
        omitted_detail_count IS NULL
        OR omitted_detail_count BETWEEN 0 AND 9007199254740991
    ),
    review_reason TEXT,
    review_tree_kind TEXT,
    review_population TEXT,
    review_axis TEXT,
    review_row_limit INTEGER,
    review_byte_limit INTEGER,
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
            AND recording_degraded_items IS NULL
            AND recording_issues_json IS NULL
            AND omitted_detail_count IS NULL
            AND review_reason IS NULL
            AND review_tree_kind IS NULL
            AND review_population IS NULL
            AND review_axis IS NULL
            AND review_row_limit IS NULL
            AND review_byte_limit IS NULL
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
            AND recording_degraded_items IS NOT NULL
            AND recording_issues_json IS NOT NULL
            AND omitted_detail_count IS NOT NULL
            AND ((error_type IS NULL) = (error_message IS NULL))
            AND (rejected_event_count = 0 OR audit_status = 'degraded')
        )
    ),
    CHECK(
        (
            review_reason IS NULL
            AND review_tree_kind IS NULL
            AND review_population IS NULL
            AND review_axis IS NULL
            AND review_row_limit IS NULL
            AND review_byte_limit IS NULL
        )
        OR
        (
            review_reason IS NOT NULL
            AND review_tree_kind IS NOT NULL
            AND review_population IS NOT NULL
            AND review_axis IS NOT NULL
            AND review_reason = 'review_fact_limit_exceeded'
            AND review_tree_kind IN ('plan', 'inventory')
            AND review_population IN ('domain', 'informational')
            AND review_axis IN ('rows', 'retained-bytes', 'logical-bytes')
            AND (
                (
                    review_axis = 'rows'
                    AND review_row_limit = 120000
                    AND review_byte_limit IS NULL
                )
                OR (
                    review_axis = 'retained-bytes'
                    AND review_row_limit IS NULL
                    AND review_byte_limit = CASE
                        WHEN review_tree_kind = 'plan'
                         AND review_population = 'domain'
                        THEN 134217728
                        ELSE 201326592
                    END
                )
                OR (
                    review_axis = 'logical-bytes'
                    AND review_tree_kind = 'plan'
                    AND review_population = 'domain'
                    AND review_row_limit IS NULL
                    AND review_byte_limit = 9223372036854775807
                )
            )
        )
    )
) STRICT;

CREATE INDEX IF NOT EXISTS history_runs_started_idx
ON history_runs(COALESCE(started_at, created_at) DESC, id DESC);

CREATE TRIGGER IF NOT EXISTS history_runs_finalized_update
BEFORE UPDATE ON history_runs
WHEN OLD.terminal_payload_hash IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'finalized history runs are immutable');
END;

CREATE TRIGGER IF NOT EXISTS history_runs_update_identity_conflict
BEFORE UPDATE OF id, run_token ON history_runs
WHEN EXISTS (
    SELECT 1 FROM history_runs AS existing
     WHERE existing.id <> OLD.id
       AND (existing.id = NEW.id OR existing.run_token = NEW.run_token)
)
BEGIN
    SELECT RAISE(ABORT, 'history runs cannot replace another run');
END;

CREATE TRIGGER IF NOT EXISTS history_runs_append_only_delete
BEFORE DELETE ON history_runs
BEGIN
    SELECT RAISE(ABORT, 'history runs cannot be deleted');
END;

CREATE TRIGGER IF NOT EXISTS history_runs_append_only_replace
BEFORE INSERT ON history_runs
WHEN EXISTS (
    SELECT 1 FROM history_runs AS existing
     WHERE existing.id = NEW.id OR existing.run_token = NEW.run_token
)
BEGIN
    SELECT RAISE(ABORT, 'history runs cannot be replaced');
END;

CREATE TABLE IF NOT EXISTS history_events (
    run_id INTEGER NOT NULL REFERENCES history_runs(id) ON DELETE CASCADE,
    event_seq INTEGER NOT NULL
        CHECK(event_seq BETWEEN 1 AND 9007199254740991),
    event_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK(schema_version = 5),
    body_type TEXT NOT NULL CHECK(length(body_type) > 0),
    event_disposition TEXT NOT NULL
        CHECK(event_disposition IN ('recorded', 'duplicate', 'rejected')),
    envelope_json TEXT,
    payload_hash BLOB NOT NULL CHECK(length(payload_hash) = 32),
    receipt_hash BLOB NOT NULL CHECK(length(receipt_hash) = 32),
    item_identity_hash BLOB CHECK(
        item_identity_hash IS NULL OR length(item_identity_hash) = 32
    ),
    item_payload_hash BLOB CHECK(
        item_payload_hash IS NULL OR length(item_payload_hash) = 32
    ),
    duplicate_of_seq INTEGER CHECK(
        duplicate_of_seq IS NULL
        OR duplicate_of_seq BETWEEN 1 AND 9007199254740991
    ),
    rejection_reason TEXT,
    item_order INTEGER CHECK(
        item_order IS NULL OR item_order BETWEEN 1 AND 9007199254740991
    ),
    item_type TEXT,
    phase TEXT,
    item_id TEXT,
    kind TEXT,
    path TEXT,
    result TEXT,
    reason TEXT,
    recording TEXT,
    recording_reason TEXT,
    recording_detail TEXT CHECK(
        recording_detail IS NULL
        OR length(CAST(recording_detail AS BLOB)) <= 1024
    ),
    detail_omitted_count INTEGER CHECK(
        detail_omitted_count IS NULL
        OR detail_omitted_count BETWEEN 0 AND 9007199254740991
    ),
    PRIMARY KEY(run_id, event_seq),
    UNIQUE(run_id, item_order),
    FOREIGN KEY(run_id, duplicate_of_seq)
        REFERENCES history_events(run_id, event_seq),
    CHECK(
        envelope_json IS NULL
        OR CASE WHEN json_valid(envelope_json)
                THEN json_type(envelope_json, '$') = 'object'
                ELSE 0 END
    ),
    CHECK(
        (
            event_disposition = 'recorded'
            AND envelope_json IS NOT NULL
            AND duplicate_of_seq IS NULL
            AND rejection_reason IS NULL
            AND item_identity_hash IS NULL
            AND item_payload_hash IS NULL
            AND item_order IS NULL
            AND item_type IS NULL
            AND phase IS NULL
            AND item_id IS NULL
            AND kind IS NULL
            AND path IS NULL
            AND result IS NULL
            AND reason IS NULL
            AND recording IS NULL
            AND recording_reason IS NULL
            AND recording_detail IS NULL
            AND detail_omitted_count IS NULL
        )
        OR
        (
            event_disposition = 'recorded'
            AND envelope_json IS NOT NULL
            AND duplicate_of_seq IS NULL
            AND rejection_reason IS NULL
            AND item_identity_hash IS NOT NULL
            AND item_payload_hash IS NOT NULL
            AND item_order IS NOT NULL
            AND item_type IS NOT NULL AND length(item_type) > 0
            AND phase IS NOT NULL AND length(phase) > 0
            AND item_id IS NOT NULL AND length(item_id) > 0
            AND kind IS NOT NULL AND length(kind) > 0
            AND path IS NOT NULL
            AND result IS NOT NULL AND length(result) > 0
            AND recording IN ('ok', 'degraded')
            AND detail_omitted_count IS NOT NULL
            AND (
                (
                    item_type = 'operation'
                    AND (
                        (
                            recording = 'ok'
                            AND recording_reason IS NULL
                            AND recording_detail IS NULL
                        )
                        OR (
                            recording = 'degraded'
                            AND recording_reason IN (
                                'record-write-failed',
                                'unrecorded-mutation',
                                'recording-prerequisite-failed'
                            )
                        )
                    )
                )
                OR (
                    item_type = 'integrity'
                    AND recording_reason IS NULL
                    AND recording_detail IS NULL
                )
            )
        )
        OR
        (
            event_disposition = 'duplicate'
            AND envelope_json IS NOT NULL
            AND item_identity_hash IS NOT NULL
            AND item_payload_hash IS NOT NULL
            AND duplicate_of_seq IS NOT NULL
            AND duplicate_of_seq > 0
            AND duplicate_of_seq < event_seq
            AND rejection_reason IS NULL
            AND item_order IS NULL
            AND item_type IS NOT NULL AND length(item_type) > 0
            AND phase IS NOT NULL AND length(phase) > 0
            AND item_id IS NOT NULL AND length(item_id) > 0
            AND kind IS NOT NULL AND length(kind) > 0
            AND path IS NOT NULL
            AND result IS NOT NULL AND length(result) > 0
            AND recording IN ('ok', 'degraded')
            AND detail_omitted_count IS NOT NULL
            AND (
                (
                    item_type = 'operation'
                    AND (
                        (
                            recording = 'ok'
                            AND recording_reason IS NULL
                            AND recording_detail IS NULL
                        )
                        OR (
                            recording = 'degraded'
                            AND recording_reason IN (
                                'record-write-failed',
                                'unrecorded-mutation',
                                'recording-prerequisite-failed'
                            )
                        )
                    )
                )
                OR (
                    item_type = 'integrity'
                    AND recording_reason IS NULL
                    AND recording_detail IS NULL
                )
            )
        )
        OR
        (
            event_disposition = 'rejected'
            AND envelope_json IS NULL
            AND (
                (
                    body_type IN ('ItemOutcome', 'IntegrityOutcome')
                    AND item_identity_hash IS NOT NULL
                    AND item_payload_hash IS NOT NULL
                    AND (
                        duplicate_of_seq IS NULL
                        OR (
                            duplicate_of_seq > 0
                            AND duplicate_of_seq < event_seq
                        )
                    )
                )
                OR
                (
                    body_type NOT IN ('ItemOutcome', 'IntegrityOutcome')
                    AND item_identity_hash IS NULL
                    AND item_payload_hash IS NULL
                    AND duplicate_of_seq IS NULL
                )
            )
            AND rejection_reason = 'event-too-large'
            AND item_order IS NULL
            AND item_type IS NULL
            AND phase IS NULL
            AND item_id IS NULL
            AND kind IS NULL
            AND path IS NULL
            AND result IS NULL
            AND reason IS NULL
            AND recording IS NULL
            AND recording_reason IS NULL
            AND recording_detail IS NULL
            AND detail_omitted_count IS NULL
        )
    )
) STRICT, WITHOUT ROWID;

CREATE UNIQUE INDEX IF NOT EXISTS history_events_run_canonical_item_uq
ON history_events(run_id, item_type, item_id)
WHERE event_disposition = 'recorded' AND item_order IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS history_events_run_identity_hash_idx
ON history_events(run_id, item_identity_hash)
WHERE (
      event_disposition = 'recorded'
      OR (event_disposition = 'rejected' AND duplicate_of_seq IS NULL)
  )
  AND item_identity_hash IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS history_events_append_insert
BEFORE INSERT ON history_events
WHEN EXISTS (
    SELECT 1 FROM history_runs AS run
     WHERE run.id = NEW.run_id
       AND (
           run.terminal_payload_hash IS NOT NULL
           OR NEW.event_seq <= run.last_committed_seq
           OR NEW.event_seq <= COALESCE((
               SELECT tail.event_seq
                 FROM history_events AS tail
                WHERE tail.run_id = NEW.run_id
                ORDER BY tail.event_seq DESC LIMIT 1
           ), 0)
           OR (
               NEW.item_order IS NOT NULL
               AND (
                   NEW.item_order <= run.item_count
                   OR NEW.item_order <= COALESCE((
                       SELECT tail.item_order
                         FROM history_events AS tail
                        WHERE tail.run_id = NEW.run_id
                          AND tail.item_order IS NOT NULL
                        ORDER BY tail.item_order DESC LIMIT 1
                   ), 0)
               )
           )
           OR (
               (
                   (
                       NEW.event_disposition = 'recorded'
                       AND NEW.item_order IS NOT NULL
                   )
                   OR (
                       NEW.event_disposition = 'rejected'
                       AND NEW.duplicate_of_seq IS NULL
                       AND NEW.item_identity_hash IS NOT NULL
                   )
               )
               AND EXISTS (
                   SELECT 1 FROM history_events AS representative
                        INDEXED BY history_events_run_identity_hash_idx
                    WHERE representative.run_id = NEW.run_id
                      AND (
                          representative.event_disposition = 'recorded'
                          OR (
                              representative.event_disposition = 'rejected'
                              AND representative.duplicate_of_seq IS NULL
                          )
                      )
                      AND representative.item_identity_hash
                          = NEW.item_identity_hash
               )
           )
           OR (
               NEW.event_disposition = 'recorded'
               AND NEW.item_order IS NOT NULL
               AND (
                   EXISTS (
                       SELECT 1 FROM history_events AS canonical
                            INDEXED BY history_events_run_canonical_item_uq
                        WHERE canonical.run_id = NEW.run_id
                          AND canonical.event_disposition = 'recorded'
                          AND canonical.item_order IS NOT NULL
                          AND canonical.item_type = NEW.item_type
                          AND canonical.item_id = NEW.item_id
                   )
               )
           )
       )
)
BEGIN
    SELECT RAISE(ABORT, 'history event insert is outside the writable tail');
END;

CREATE TRIGGER IF NOT EXISTS history_events_duplicate_link_insert
BEFORE INSERT ON history_events
WHEN (
        NEW.event_disposition = 'duplicate'
        OR (
            NEW.event_disposition = 'rejected'
            AND NEW.duplicate_of_seq IS NOT NULL
        )
    )
    AND NOT EXISTS (
    SELECT 1 FROM history_events AS canonical
     WHERE canonical.run_id = NEW.run_id
       AND canonical.event_seq = NEW.duplicate_of_seq
       AND canonical.item_identity_hash = NEW.item_identity_hash
       AND canonical.item_payload_hash = NEW.item_payload_hash
       AND (
           (
               canonical.event_disposition = 'recorded'
               AND canonical.item_order IS NOT NULL
               AND (
                   NEW.event_disposition = 'rejected'
                   OR (
                       canonical.item_type = NEW.item_type
                       AND canonical.item_id = NEW.item_id
                   )
               )
           )
           OR (
               canonical.event_disposition = 'rejected'
               AND canonical.duplicate_of_seq IS NULL
           )
       )
)
BEGIN
    SELECT RAISE(ABORT, 'duplicate receipt link mismatch');
END;

CREATE TRIGGER IF NOT EXISTS history_events_duplicate_link_update
BEFORE UPDATE ON history_events
WHEN (
        NEW.event_disposition = 'duplicate'
        OR (
            NEW.event_disposition = 'rejected'
            AND NEW.duplicate_of_seq IS NOT NULL
        )
    )
    AND NOT EXISTS (
    SELECT 1 FROM history_events AS canonical
     WHERE canonical.run_id = NEW.run_id
       AND canonical.event_seq = NEW.duplicate_of_seq
       AND canonical.item_identity_hash = NEW.item_identity_hash
       AND canonical.item_payload_hash = NEW.item_payload_hash
       AND (
           (
               canonical.event_disposition = 'recorded'
               AND canonical.item_order IS NOT NULL
               AND (
                   NEW.event_disposition = 'rejected'
                   OR (
                       canonical.item_type = NEW.item_type
                       AND canonical.item_id = NEW.item_id
                   )
               )
           )
           OR (
               canonical.event_disposition = 'rejected'
               AND canonical.duplicate_of_seq IS NULL
           )
       )
)
BEGIN
    SELECT RAISE(ABORT, 'duplicate receipt link mismatch');
END;

CREATE TRIGGER IF NOT EXISTS history_events_append_only_update
BEFORE UPDATE ON history_events
BEGIN
    SELECT RAISE(ABORT, 'history events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS history_events_append_only_delete
BEFORE DELETE ON history_events
BEGIN
    SELECT RAISE(ABORT, 'history events are append-only');
END;

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
    CHECK(items_done BETWEEN 0 AND 9007199254740991),
    CHECK(
        items_total IS NULL
        OR items_total BETWEEN items_done AND 9007199254740991
    ),
    CHECK(bytes_done >= 0),
    CHECK(bytes_total IS NULL OR bytes_total >= bytes_done)
) STRICT;

COMMIT;
"""


_SchemaObject = tuple[str, str, str, str | None]
_SQLITE_STATISTICS_TOPOLOGY: tuple[_SchemaObject, ...] = (
    ("table", "sqlite_stat1", "sqlite_stat1", "CREATE TABLE sqlite_stat1(tbl,idx,stat)"),
    ("table", "sqlite_stat4", "sqlite_stat4",
     "CREATE TABLE sqlite_stat4(tbl,idx,neq,nlt,ndlt,sample)"),
)


def _schema_topology(connection: sqlite3.Connection) -> list[_SchemaObject]:
    # Retain SQLite's stored SQL verbatim, including literal text and NULL SQL
    # for automatic indexes. Physical root pages are not schema definitions.
    return [
        tuple(row)
        for row in connection.execute(
            "SELECT type, name, tbl_name, sql FROM main.sqlite_schema "
            "ORDER BY type, name, tbl_name, sql"
        )
    ]


def _validate_schema_topology(
    connection: sqlite3.Connection, *, history: bool,
) -> None:
    """Compare complete definitions without writing to the candidate connection."""

    reference = sqlite3.connect(":memory:")
    try:
        reference.executescript(_HISTORY_SCHEMA if history else _LEDGER_SCHEMA)
        expected = _schema_topology(reference)
    finally:
        reference.close()
    actual = _schema_topology(connection)
    for statistic in _SQLITE_STATISTICS_TOPOLOGY:
        if statistic in actual:
            # Each exact SQLite-owned table is optional once, not a wildcard
            # exemption for duplicate, poisoned, or additional catalog rows.
            actual.remove(statistic)
    if actual != expected:
        database = "history" if history else "ledger"
        raise SchemaResetRequired(
            f"unsupported {database} schema topology. "
            "Close every NamiSync process, then archive or delete both database "
            "main files and all of their -wal, -shm, and -journal sidecars "
            "together before restarting."
        )


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
        "NamiSync M1 requires ledger v4 and history v6 at data epoch 5. "
        "Close every NamiSync process, then archive or delete both database "
        "main files and all of their -wal, -shm, and -journal sidecars "
        "together before restarting."
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
            "NamiSync M1 requires ledger v4 and history v6 at data epoch 5. "
            "Close every NamiSync process, then archive or delete both database "
            "main files and all of their -wal, -shm, and -journal sidecars "
            "together before restarting."
        )
    epoch_row = connection.execute(
        "SELECT value FROM schema_metadata WHERE key = 'data_epoch'"
    ).fetchone()
    epoch = None if epoch_row is None else str(epoch_row[0])
    if epoch != str(DATA_EPOCH):
        database = "history" if history else "ledger"
        value = "missing" if epoch is None else epoch
        raise SchemaResetRequired(
            f"unsupported {database} data epoch {value}; "
            "NamiSync M1 requires ledger v4 and history v6 at data epoch 5. "
            "Close every NamiSync process, then archive or delete both database "
            "main files and all of their -wal, -shm, and -journal sidecars "
            "together before restarting."
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
