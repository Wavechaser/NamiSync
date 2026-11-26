"""Owned SQLite schemas for the main ledger and independent history store."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
from pathlib import Path
from typing import Iterable

from namisync.core.formats import FORMAT_VERSIONS

from .connections import (
    DEFAULT_BUSY_TIMEOUT_MS,
    connect_history_writer,
    connect_ledger_writer,
    validate_database_path,
)


LEDGER_SCHEMA_VERSION = 5
HISTORY_SCHEMA_VERSION = 9
# The core formats each current schema embeds, stored as ``format.<name>``
# rows with their ``FORMAT_VERSIONS`` values. A core format change therefore
# needs a new schema version and its migration (tests pin these sets).
LEDGER_FORMATS = (
    "event", "evidence", "identity", "numeric", "path-key", "preimage", "recording",
)
HISTORY_FORMATS = ("event", "numeric", "preimage", "recording")
# The only supported older source is the pair NamiSync 0.1.0 released. Its
# ``data_epoch`` row is never read.
RELEASED_LEDGER_SCHEMA_VERSION = 4
RELEASED_HISTORY_SCHEMA_VERSION = 8
RELEASED_LEDGER_CONTRACT_ID = "m1-ledger-v4-event-v5-evidence-v2"
RELEASED_HISTORY_CONTRACT_ID = "m1-history-v8-event-v5-recording-v1"
# SHA-256 of the released complete ``sqlite_schema`` topology, as serialized
# by ``_topology_digest``; tests check both against the v0.1.0 fixture.
_RELEASED_LEDGER_TOPOLOGY_SHA256 = (
    "99591e4cb8d60a68d2ce496d94bd9c69521ffa05df16efe1b3a7d72761f3b126"
)
_RELEASED_HISTORY_TOPOLOGY_SHA256 = (
    "0b1410757609d54161fd06c05d221de903c1d37488f635288df82805cc9697c3"
)
_INSTANCE_ID = re.compile("[0-9a-f]{32}")
MAX_HISTORY_PHASE_NAME_BYTES = 1_024
MAX_HISTORY_ERROR_TYPE_BYTES = 1_024
MAX_HISTORY_ERROR_MESSAGE_BYTES = 1_024
# One database's own refusal: whether its peer goes too is the pair's decision.
_RESET_DIRECTION = (
    "Close every NamiSync process, then archive or delete this database main "
    "file and all of its -wal, -shm, and -journal sidecars before restarting."
)


class DatabaseAdmissionError(sqlite3.DatabaseError):
    """Database admission could not safely establish a usable contract."""


class SchemaResetRequired(DatabaseAdmissionError):
    """An unsupported schema can only be archived and recreated, never migrated."""


class DatabaseMigrationRequired(DatabaseAdmissionError):
    """A supported older database must be migrated before ordinary use."""


class DatabaseNewerVersion(DatabaseAdmissionError):
    """A database written by a newer NamiSync, which this version never changes."""


class DatabaseRoleMismatch(DatabaseAdmissionError):
    """The path holds the other role (paths look swapped) or a role this version does not know."""


class LedgerIsBackup(DatabaseAdmissionError):
    """A live ledger whose lineage names its own instance: a backup copied into place by hand.

    Raised only after the rest of the current reader contract has passed, so
    a caller that validates a backup file may accept exactly this refusal.
    """


def _statements(script: str) -> tuple[str, ...]:
    """Split a schema script into complete statements, trigger bodies included."""

    statements: list[str] = []
    pending = ""
    for line in script.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            statements.append(pending.strip().removesuffix(";").rstrip())
            pending = ""
    if pending.strip():
        raise ValueError("schema script ends inside a statement")
    return tuple(statements)


_LEDGER_STATEMENTS = _statements("""
CREATE TABLE schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE hosts (
    id INTEGER PRIMARY KEY,
    host_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
) STRICT;

CREATE TABLE volumes (
    id INTEGER PRIMARY KEY,
    serial TEXT NOT NULL,
    fs_type TEXT NOT NULL,
    label TEXT,
    device_id TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(serial, fs_type)
) STRICT;

CREATE INDEX volumes_serial_idx ON volumes(serial);

CREATE TABLE locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    volume_id INTEGER NOT NULL REFERENCES volumes(id),
    volume_relative_path TEXT NOT NULL,
    volume_relative_path_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    rebound_at TEXT,
    UNIQUE(volume_id, volume_relative_path_key)
) STRICT;

CREATE TABLE mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_location_id INTEGER NOT NULL REFERENCES locations(id),
    target_location_id INTEGER NOT NULL REFERENCES locations(id),
    created_at TEXT NOT NULL,
    deleted_at TEXT,
    CHECK(source_location_id <> target_location_id)
) STRICT;

CREATE UNIQUE INDEX mappings_active_pair_uq
ON mappings(source_location_id, target_location_id)
WHERE deleted_at IS NULL;

CREATE TABLE inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

CREATE INDEX inventory_location_presence_idx
ON inventory(location_id, presence, rel_path_key);
CREATE INDEX inventory_identity_idx
ON inventory(location_id, file_identity_volume_serial, file_identity_file_index);

CREATE TABLE runs (
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

CREATE TABLE operations (
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

CREATE INDEX operations_run_order_idx ON operations(run_id, id);

CREATE TABLE mapping_correspondence (
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

CREATE TRIGGER mapping_correspondence_locations_insert
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

CREATE TRIGGER mapping_correspondence_locations_update
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

CREATE TABLE recording_commands (
    command_key TEXT PRIMARY KEY,
    command_kind TEXT NOT NULL,
    payload_hash BLOB NOT NULL,
    disposition TEXT NOT NULL,
    recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE annotations (
    id INTEGER PRIMARY KEY,
    entity_kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    key TEXT NOT NULL CHECK(instr(key, '.') > 1),
    value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(entity_kind, entity_id, key)
) STRICT;

CREATE TABLE ledger_lineage (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('backup-cut', 'replaced-missing')),
    instance_id TEXT UNIQUE CHECK(
        instance_id IS NULL
        OR (length(instance_id) = 32 AND instance_id NOT GLOB '*[^0-9a-f]*')
    ),
    at TEXT NOT NULL,
    CHECK((kind = 'backup-cut') = (instance_id IS NOT NULL))
) STRICT;
""")


_HISTORY_STATEMENTS = _statements(f"""
CREATE TABLE schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE history_runs (
    id INTEGER PRIMARY KEY,
    run_token TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    activity_kind TEXT NOT NULL,
    host_key TEXT NOT NULL,
    ledger_instance_id TEXT CHECK(
        ledger_instance_id IS NULL
        OR (
            length(ledger_instance_id) = 32
            AND ledger_instance_id NOT GLOB '*[^0-9a-f]*'
        )
    ),
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
                    AND review_row_limit IS NOT NULL
                    AND review_row_limit IN (120000, 150000)
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

CREATE INDEX history_runs_started_idx
ON history_runs(COALESCE(started_at, created_at) DESC, id DESC);

CREATE TRIGGER history_runs_finalized_update
BEFORE UPDATE ON history_runs
WHEN OLD.terminal_payload_hash IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'finalized history runs are immutable');
END;

CREATE TRIGGER history_runs_ledger_instance_immutable
BEFORE UPDATE OF ledger_instance_id ON history_runs
WHEN NEW.ledger_instance_id IS NOT OLD.ledger_instance_id
BEGIN
    SELECT RAISE(ABORT, 'history run ledger instance is immutable');
END;

CREATE TRIGGER history_runs_update_identity_conflict
BEFORE UPDATE OF id, run_token ON history_runs
WHEN EXISTS (
    SELECT 1 FROM history_runs AS existing
     WHERE existing.id <> OLD.id
       AND (existing.id = NEW.id OR existing.run_token = NEW.run_token)
)
BEGIN
    SELECT RAISE(ABORT, 'history runs cannot replace another run');
END;

CREATE TRIGGER history_runs_append_only_delete
BEFORE DELETE ON history_runs
BEGIN
    SELECT RAISE(ABORT, 'history runs cannot be deleted');
END;

CREATE TRIGGER history_runs_append_only_replace
BEFORE INSERT ON history_runs
WHEN EXISTS (
    SELECT 1 FROM history_runs AS existing
     WHERE existing.id = NEW.id OR existing.run_token = NEW.run_token
)
BEGIN
    SELECT RAISE(ABORT, 'history runs cannot be replaced');
END;

CREATE TABLE history_events (
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

CREATE UNIQUE INDEX history_events_run_canonical_item_uq
ON history_events(run_id, item_type, item_id)
WHERE event_disposition = 'recorded' AND item_order IS NOT NULL;

CREATE UNIQUE INDEX history_events_run_identity_hash_idx
ON history_events(run_id, item_identity_hash)
WHERE (
      event_disposition = 'recorded'
      OR (event_disposition = 'rejected' AND duplicate_of_seq IS NULL)
  )
  AND item_identity_hash IS NOT NULL;

CREATE TRIGGER history_events_append_insert
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

CREATE TRIGGER history_events_duplicate_link_insert
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

CREATE TRIGGER history_events_append_only_update
BEFORE UPDATE ON history_events
BEGIN
    SELECT RAISE(ABORT, 'history events are append-only');
END;

CREATE TRIGGER history_events_append_only_delete
BEFORE DELETE ON history_events
BEGIN
    SELECT RAISE(ABORT, 'history events are append-only');
END;

CREATE INDEX history_events_run_item_order_idx
ON history_events(run_id, item_order)
WHERE item_order IS NOT NULL;

CREATE INDEX history_events_run_item_aggregate_idx
ON history_events(run_id, item_type, phase, kind, result, reason)
WHERE item_order IS NOT NULL;

CREATE TABLE history_phases (
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
""")


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


def _role(history: bool) -> str:
    return "history" if history else "ledger"


def _schema_statements(history: bool) -> tuple[str, ...]:
    return _HISTORY_STATEMENTS if history else _LEDGER_STATEMENTS


def new_instance_id() -> str:
    """A random ledger instance id in its canonical 32 lowercase hex form."""

    return secrets.token_hex(16)


def _metadata_rows(history: bool, instance_id: str | None) -> tuple[tuple[str, str], ...]:
    formats = HISTORY_FORMATS if history else LEDGER_FORMATS
    rows = [
        ("role", _role(history)),
        ("schema_version", str(HISTORY_SCHEMA_VERSION if history else LEDGER_SCHEMA_VERSION)),
        *((f"format.{name}", str(FORMAT_VERSIONS[name])) for name in formats),
    ]
    if not history:
        if instance_id is None or _INSTANCE_ID.fullmatch(instance_id) is None:
            raise ValueError("a ledger requires a canonical instance id")
        rows.append(("instance_id", instance_id))
    elif instance_id is not None:
        raise ValueError("only a ledger carries an instance id")
    return tuple(rows)


def _schema_script(history: bool) -> str:
    """One creation transaction: the shipped statements, then the metadata rows.

    A ledger receives a fresh random instance id each time this is rendered.
    """

    inserts = tuple(
        f"INSERT INTO schema_metadata(key, value) VALUES ('{key}', '{value}')"
        for key, value in _metadata_rows(history, None if history else new_instance_id())
    )
    return "BEGIN IMMEDIATE;\n" + ";\n\n".join(
        (*_schema_statements(history), *inserts)
    ) + ";\nCOMMIT;\n"


def _without_statistics(actual: list[_SchemaObject]) -> list[_SchemaObject]:
    for statistic in _SQLITE_STATISTICS_TOPOLOGY:
        if statistic in actual:
            # Each exact SQLite-owned table is optional once, not a wildcard
            # exemption for duplicate, poisoned, or additional catalog rows.
            actual.remove(statistic)
    return actual


def _topology_digest(topology: list[_SchemaObject]) -> str:
    return hashlib.sha256(
        json.dumps(topology, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _refuse_topology(history: bool) -> None:
    raise SchemaResetRequired(
        f"unsupported {_role(history)} schema topology. {_RESET_DIRECTION}"
    )


def _validate_schema_topology(
    connection: sqlite3.Connection, *, history: bool,
) -> None:
    """Compare complete definitions without writing to the candidate connection."""

    reference = sqlite3.connect(":memory:")
    try:
        reference.executescript(_schema_script(history))
        expected = _schema_topology(reference)
    finally:
        reference.close()
    if _without_statistics(_schema_topology(connection)) != expected:
        _refuse_topology(history)


def _validate_released_topology(
    connection: sqlite3.Connection, *, history: bool,
) -> None:
    expected = (
        _RELEASED_HISTORY_TOPOLOGY_SHA256 if history else _RELEASED_LEDGER_TOPOLOGY_SHA256
    )
    if _topology_digest(_without_statistics(_schema_topology(connection))) != expected:
        _refuse_topology(history)


def _metadata(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        str(key): str(value)
        for key, value in connection.execute("SELECT key, value FROM schema_metadata")
    }


def _format_version(value: str) -> int | None:
    return int(value) if re.fullmatch("[1-9][0-9]{0,8}", value) else None


def _raise_newer(history: bool, detail: str) -> None:
    raise DatabaseNewerVersion(
        f"The {_role(history)} database was written by a newer NamiSync ({detail}). "
        "Open it with that NamiSync version; this version cannot use it and "
        "leaves it unchanged."
    )


def _refuse_metadata(history: bool, detail: str) -> None:
    raise SchemaResetRequired(
        f"unsupported {_role(history)} schema metadata ({detail}). {_RESET_DIRECTION}"
    )


def classify_database(connection: sqlite3.Connection, *, history: bool) -> int:
    """Return the schema version of a current or supported older database.

    Raises ``DatabaseNewerVersion`` for a database of this role written by a
    newer NamiSync, ``DatabaseRoleMismatch`` for a database of the other role
    (the paths look swapped) or of a role this version does not know, and
    ``SchemaResetRequired`` for anything else this version cannot use. Reads
    the catalog and metadata only.
    """

    version = _existing_schema_version(connection, history=history)
    if version is None:
        _raise_reset_required("empty", history=history)
    metadata = _metadata(connection)
    role = metadata.get("role")
    other_contract = RELEASED_LEDGER_CONTRACT_ID if history else RELEASED_HISTORY_CONTRACT_ID
    if role == _role(not history) or (
        role is None and metadata.get("contract_id") == other_contract
    ):
        raise DatabaseRoleMismatch(
            f"The {_role(history)} database path holds a {_role(not history)} "
            "database: the ledger and history database paths look swapped. Check "
            "the two database paths (for the command line, --database and "
            "--history-database), then start again. Nothing was changed."
        )
    if role is not None and role != _role(history):
        # Only a newer NamiSync could write a role this version does not know.
        raise DatabaseRoleMismatch(
            f"The file at the {_role(history)} database path is not a NamiSync "
            f"{_role(history)} database this version knows (its role is "
            f"{role!r}). Check the database path (for the command line, "
            "--database and --history-database), then start again. Nothing was "
            "changed."
        )
    current = HISTORY_SCHEMA_VERSION if history else LEDGER_SCHEMA_VERSION
    if version > current:
        # Only a database that names this role can be from a newer NamiSync.
        if role is None:
            _raise_reset_required(version, history=history)
        _raise_newer(history, f"schema version {version}")
    if version == current:
        if role is None:
            _refuse_metadata(history, "role")
        _require_current_metadata(metadata, history=history)
        _validate_schema_topology(connection, history=history)
        return version
    released = RELEASED_HISTORY_SCHEMA_VERSION if history else RELEASED_LEDGER_SCHEMA_VERSION
    if version != released or role is not None:
        _raise_reset_required(version, history=history)
    contract = RELEASED_HISTORY_CONTRACT_ID if history else RELEASED_LEDGER_CONTRACT_ID
    if metadata.get("contract_id") != contract:
        _raise_reset_required(
            f"{version} contract {metadata.get('contract_id', 'missing')}", history=history,
        )
    _validate_released_topology(connection, history=history)
    return version


def _require_current_metadata(metadata: dict[str, str], *, history: bool) -> None:
    for key, value in metadata.items():
        if key.startswith("format."):
            stored = _format_version(value)
            known = FORMAT_VERSIONS.get(key.removeprefix("format."))
            if stored is not None and known is not None and stored > known:
                _raise_newer(history, f"{key} {stored}")
    instance_id = metadata.get("instance_id")
    if not history and (instance_id is None or _INSTANCE_ID.fullmatch(instance_id) is None):
        _refuse_metadata(history, "instance id")
    expected = dict(_metadata_rows(history, None if history else instance_id))
    if metadata != expected:
        differing = sorted(
            key for key in metadata.keys() | expected.keys()
            if metadata.get(key) != expected.get(key)
        )
        _refuse_metadata(history, ", ".join(differing))


def ledger_instance_id(connection: sqlite3.Connection) -> str:
    """Read the canonical instance id of an admitted current ledger."""

    row = connection.execute(
        "SELECT value FROM schema_metadata WHERE key = 'instance_id'"
    ).fetchone()
    value = None if row is None else row[0]
    if type(value) is not str or _INSTANCE_ID.fullmatch(value) is None:
        _refuse_metadata(False, "instance id")
    return value


def _initialize(
    path: str | Path,
    *,
    history: bool,
    busy_timeout_ms: int,
    managed_roots: Iterable[str | Path],
) -> Path:
    # Deferred import: the shared file probe selects this module's validators.
    from .contracts import database_artifacts_present, require_database_file_contract

    resolved = validate_database_path(path, managed_roots=managed_roots)
    if busy_timeout_ms < 0:
        raise ValueError("busy timeout cannot be negative")
    if database_artifacts_present(resolved):
        require_database_file_contract(resolved, history=history)
        return resolved
    return _create_schema(resolved, history=history, busy_timeout_ms=busy_timeout_ms)


def _create_schema(
    resolved: Path, *, history: bool, busy_timeout_ms: int,
) -> Path:
    # Deferred import: claim refusals extend this module's admission error.
    from .claims import acquire_database_claim

    resolved.parent.mkdir(parents=True, exist_ok=True)
    connect = connect_history_writer if history else connect_ledger_writer
    # Released before return, so a caller may take its shared writer claim next.
    with acquire_database_claim(resolved, exclusive=True):
        connection = connect(resolved, busy_timeout_ms=busy_timeout_ms)
        try:
            version = _existing_schema_version(connection, history=history)
            if version is not None:
                _raise_reset_required("not-empty", history=history)
            connection.executescript(_schema_script(history))
            _validate_reader_contract(connection, history=history)
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
    raise SchemaResetRequired(
        f"unsupported {_role(history)} schema version {version}; this NamiSync "
        f"uses ledger v{LEDGER_SCHEMA_VERSION} and history v{HISTORY_SCHEMA_VERSION} "
        f"and updates the ledger v{RELEASED_LEDGER_SCHEMA_VERSION} and history "
        f"v{RELEASED_HISTORY_SCHEMA_VERSION} of NamiSync 0.1.0. {_RESET_DIRECTION}"
    )


def _validate_reader_contract(
    connection: sqlite3.Connection, *, history: bool
) -> None:
    version = classify_database(connection, history=history)
    if version != (HISTORY_SCHEMA_VERSION if history else LEDGER_SCHEMA_VERSION):
        raise DatabaseMigrationRequired(
            f"The {_role(history)} database was written by NamiSync 0.1.0 and "
            "must be updated before use. Start NamiSync, or run a sync or "
            f"inventory command, once to update it together with its "
            f"{_role(not history)} database, which is created new if it is "
            "missing; a backup of each updated database is kept beside it."
        )
    if not history:
        _refuse_live_backup(connection)


def ledger_backup_cut(connection: sqlite3.Connection) -> str | None:
    """The recorded time of the backup cut naming this ledger's own instance, or None.

    Only a backup carries one, so a ledger with one is a backup. Read through
    a connection to a ledger already classified as current.
    """

    row = connection.execute(
        "SELECT at FROM ledger_lineage WHERE kind = 'backup-cut' AND instance_id = ?",
        (ledger_instance_id(connection),),
    ).fetchone()
    return None if row is None else row[0]


def _refuse_live_backup(connection: sqlite3.Connection) -> None:
    # A backup carries a cut row naming its own instance and a restore always
    # issues a new one, so only a backup file copied into place matches here.
    if ledger_backup_cut(connection) is not None:
        raise LedgerIsBackup(
            "The ledger database is a NamiSync backup copied into place by hand: "
            "its lineage records a backup of its own ledger instance. NamiSync "
            "does not use a backup as the live ledger, because History runs "
            "recorded after the backup was made would count as its own. Put back "
            "the ledger it replaced, or restore the backup with the command "
            "namisync restore ledger <backup file>, which gives the restored "
            "ledger a new instance. Nothing was changed."
        )


def validate_ledger_reader_contract(connection: sqlite3.Connection) -> None:
    """Refuse an incompatible ledger through an already read-only connection.

    ``LedgerIsBackup`` comes last, once the ledger is otherwise current;
    ``classify_database`` alone never applies that live-ledger rule.
    """

    _validate_reader_contract(connection, history=False)


def validate_history_reader_contract(connection: sqlite3.Connection) -> None:
    """Refuse an incompatible history store through a read-only connection."""

    _validate_reader_contract(connection, history=True)


def _initialize_reserved_ledger(path: Path) -> Path:
    """Create only under the pair coordinator's existing empty reservations."""

    return _create_schema(
        path, history=False, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS,
    )


def _initialize_reserved_history(path: Path) -> Path:
    """Create only under the pair coordinator's existing empty reservations."""

    return _create_schema(
        path, history=True, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS,
    )


def initialize_ledger(
    path: str | Path,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    managed_roots: Iterable[str | Path] = (),
) -> Path:
    return _initialize(
        path,
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
