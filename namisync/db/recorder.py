"""Serialized sole-writer implementation for the main NamiSync ledger."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from namisync.core.evidence import Attestation, ContentEvidence, Provenance, RecordingStatus
from namisync.core.execution import RecordedCopyIdentity
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityRecordCommand,
    InventoryState,
    RecordDisposition,
    VerificationInvalidation,
    VerificationInvalidationCommand,
    VerificationInvalidationReason,
)
from namisync.core.models import (
    DirRecord,
    EntryKind,
    FileIdentity,
    FileRecord,
    FileStat,
    ScanResult,
    ScanScope,
    ScanScopeKind,
    ScanWarning,
    UnsupportedReason,
    UnsupportedRecord,
    VolumeId,
    capability_profile_projection,
    file_identity_projection,
    file_stat_projection,
    metadata_projection,
    root_projection,
    volume_evidence_projection,
    volume_id_projection,
    validate_scan_result,
    validate_scan_scope,
    validate_scan_warning,
)
from namisync.core.pathing import normalize_relative_path, validate_relative_path
from namisync.core.planning import (
    OpId,
    OperationKind,
    PlanOperation,
    canonical_json_bytes,
    operation_projection,
    plan_projection,
)
from namisync.core.scalars import file_index_128_to_text
from namisync.core.recording import (
    FinishRunCommand,
    HostCommand,
    InventoryCommand,
    InventoryVisibilityAction,
    InventoryVisibilityCommand,
    LocationCommand,
    MappingCommand,
    SyncRunCommand,
    VolumeCommand,
)
from namisync.core.session import SessionState

from .connections import DEFAULT_BUSY_TIMEOUT_MS, connect_ledger_writer
from .schema import initialize_ledger
from .timestamps import encode_utc
from .writer import (
    DEFAULT_RETRY_TIMEOUT_SECONDS,
    RecordingError,
    SerializedWriter,
    TokenConflictError,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class VolumeRebindRequired(RecordingError):
    """A known serial appeared with a different filesystem type."""


class AmbiguousVolumeError(RecordingError):
    """The caller reported simultaneous duplicate volume identity."""


class MappingValidationError(RecordingError):
    """A mapping violates physical-root safety constraints."""


class MappingRestoreRequired(RecordingError):
    """An equivalent soft-deleted mapping must be restored explicitly."""


class StaleRecordingError(RecordingError):
    """Post-filesystem evidence no longer matches the reviewed operation."""


@dataclass(frozen=True, slots=True)
class InventoryReconcileResult:
    disposition: RecordDisposition
    observed_count: int
    missing_count: int


_SUBTREE_DESCENDANT_PREDICATE = (
    "rel_path_key >= ? || '\\' AND rel_path_key < ? || ']'"
)
_OBSERVATION_MATCHES_ATTESTATION = """(
    inventory.attested_kind IS excluded.entry_kind
    AND inventory.attested_size IS excluded.observed_size
    AND inventory.attested_mtime_ns IS excluded.observed_mtime_ns
    AND (
        (
            inventory.attested_file_identity_volume_serial IS NULL
            AND inventory.attested_file_identity_file_index IS NULL
        )
        OR (
            inventory.attested_file_identity_volume_serial
                IS excluded.file_identity_volume_serial
            AND inventory.attested_file_identity_file_index
                IS excluded.file_identity_file_index
        )
    )
)"""


def _payload_hash(value: object) -> bytes:
    return hashlib.sha256(canonical_json_bytes(value)).digest()


def _bytes_projection(value: bytes) -> dict[str, str]:
    if type(value) is not bytes:
        raise TypeError("digest projection requires bytes")
    return {"$bytes": value.hex()}


def _file_record_projection(value: FileRecord) -> dict[str, object]:
    if type(value) is not FileRecord:
        raise TypeError("file record projection requires FileRecord")
    return {
        "rel_path": value.rel_path,
        "rel_path_key": value.rel_path_key,
        "size": value.size,
        "mtime_ns": value.mtime_ns,
        "file_identity": file_identity_projection(value.file_identity),
        "nlink": value.nlink,
        "metadata": metadata_projection(value.metadata),
    }


def _directory_record_projection(value: DirRecord) -> dict[str, object]:
    if type(value) is not DirRecord:
        raise TypeError("directory projection requires DirRecord")
    return {
        "rel_path": value.rel_path,
        "rel_path_key": value.rel_path_key,
        "mtime_ns": value.mtime_ns,
        "metadata": metadata_projection(value.metadata),
        "file_identity": file_identity_projection(value.file_identity),
        "nlink": value.nlink,
    }


def _unsupported_record_projection(value: UnsupportedRecord) -> dict[str, object]:
    if (
        type(value) is not UnsupportedRecord
        or type(value.reason) is not UnsupportedReason
        or (value.kind is not None and type(value.kind) is not EntryKind)
    ):
        raise TypeError("unsupported record projection requires typed record and reasons")
    return {
        "rel_path": value.rel_path,
        "rel_path_key": value.rel_path_key,
        "reason": value.reason.value,
        "kind": None if value.kind is None else value.kind.value,
    }


def _scan_warning_projection(value: ScanWarning) -> dict[str, object]:
    validate_scan_warning(value)
    return {"code": value.code.value, "rel_path": value.rel_path, "detail": value.detail}


def _scan_scope_projection(value: ScanScope) -> dict[str, object]:
    validate_scan_scope(value)
    return {
        "kind": value.kind.value,
        "selected_paths": list(value.selected_paths),
        "subtree_roots": list(value.subtree_roots),
    }


def _scan_projection(value: ScanResult) -> dict[str, object]:
    validate_scan_result(value)
    return {
        "root": root_projection(value.root),
        "volume_id": volume_id_projection(value.volume_id),
        "volume_evidence": volume_evidence_projection(value.volume_evidence),
        "profile": capability_profile_projection(value.profile),
        "files": [_file_record_projection(item) for item in value.files],
        "directories": [_directory_record_projection(item) for item in value.directories],
        "unsupported": [_unsupported_record_projection(item) for item in value.unsupported],
        "warnings": [_scan_warning_projection(item) for item in value.warnings],
        "scope": _scan_scope_projection(value.scope),
        "complete": value.complete,
    }


def _content_projection(value: ContentEvidence) -> dict[str, object]:
    if type(value) is not ContentEvidence or type(value.provenance) is not Provenance:
        raise TypeError("content projection requires ContentEvidence with Provenance")
    return {
        "algorithm": value.algorithm,
        "digest": _bytes_projection(value.digest),
        "size": value.size,
        "provenance": value.provenance.value,
        "observed_at": encode_utc(value.observed_at),
    }


def _attestation_projection(value: Attestation | None) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not Attestation:
        raise TypeError("attestation projection requires Attestation")
    return {
        "content": _content_projection(value.content),
        "subject": file_stat_projection(value.subject),
    }


def _invalidation_projection(value: VerificationInvalidation | None) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not VerificationInvalidation or type(value.reason) is not VerificationInvalidationReason:
        raise TypeError("invalidation projection requires typed invalidation and reason")
    return {"at": encode_utc(value.at), "reason": value.reason.value}


def _sync_run_projection(value: SyncRunCommand) -> dict[str, object]:
    if type(value) is not SyncRunCommand or type(value.selection) is not frozenset:
        raise TypeError("run projection requires SyncRunCommand with frozen selection")
    return {
        "run_token": value.run_token,
        "host_id": value.host_id,
        "mapping_id": value.mapping_id,
        "source_location_id": value.source_location_id,
        "target_location_id": value.target_location_id,
        "plan": plan_projection(value.plan),
        "selection": sorted(value.selection),
        "selection_digest": _bytes_projection(value.selection_digest),
        "started_at": encode_utc(value.started_at),
    }


def _finish_run_projection(value: FinishRunCommand) -> dict[str, object]:
    if (
        type(value) is not FinishRunCommand
        or type(value.status) is not SessionState
        or type(value.recording) is not RecordingStatus
    ):
        raise TypeError("finish projection requires typed command and statuses")
    return {
        "run_token": value.run_token,
        "status": value.status.value,
        "recording": value.recording.value,
        "ended_at": encode_utc(value.ended_at),
    }


def _inventory_projection(value: InventoryCommand) -> dict[str, object]:
    if type(value) is not InventoryCommand:
        raise TypeError("inventory projection requires InventoryCommand")
    return {
        "location_id": value.location_id,
        "host_id": value.host_id,
        "scan": _scan_projection(value.scan),
        "scope_token": value.scope_token,
        "observed_at": encode_utc(value.observed_at),
        "online": value.online,
    }


def _visibility_projection(value: InventoryVisibilityCommand) -> dict[str, object]:
    if type(value) is not InventoryVisibilityCommand or type(value.action) is not InventoryVisibilityAction:
        raise TypeError("visibility projection requires typed command and action")
    return {
        "command_id": value.command_id,
        "location_id": value.location_id,
        "row_id": value.row_id,
        "action": value.action.value,
        "changed_at": encode_utc(value.changed_at),
    }


def _integrity_projection(value: IntegrityRecordCommand) -> dict[str, object]:
    if (
        type(value) is not IntegrityRecordCommand
        or type(value.mode) is not IntegrityMode
        or type(value.expected_state) is not InventoryState
    ):
        raise TypeError("integrity projection requires typed command, mode, and state")
    return {
        "mode": value.mode.value,
        "item_id": value.item_id,
        "row_id": value.row_id,
        "location_id": value.location_id,
        "rel_path_key": value.rel_path_key,
        "scope_token": value.scope_token,
        "expected_state": value.expected_state.value,
        "expected_stat": file_stat_projection(value.expected_stat),
        "expected_baseline": _attestation_projection(value.expected_baseline),
        "attestation": _attestation_projection(value.attestation),
        "advances_last_verified": value.advances_last_verified,
        "clear_reappeared": value.clear_reappeared,
        "expected_invalidation": _invalidation_projection(value.expected_invalidation),
    }


def _verification_invalidation_projection(value: VerificationInvalidationCommand) -> dict[str, object]:
    if (
        type(value) is not VerificationInvalidationCommand
        or type(value.expected_state) is not InventoryState
        or type(value.reason) is not VerificationInvalidationReason
    ):
        raise TypeError("invalidation command projection requires typed command, state, and reason")
    return {
        "item_id": value.item_id,
        "row_id": value.row_id,
        "location_id": value.location_id,
        "rel_path_key": value.rel_path_key,
        "scope_token": value.scope_token,
        "expected_state": value.expected_state.value,
        "expected_stat": file_stat_projection(value.expected_stat),
        "expected_baseline": _attestation_projection(value.expected_baseline),
        "expected_invalidation": _invalidation_projection(value.expected_invalidation),
        "reason": value.reason.value,
        "invalidated_at": encode_utc(value.invalidated_at),
    }


def _identity_values(identity: FileIdentity | None) -> tuple[str | None, str | None]:
    if identity is None:
        return None, None
    return identity.volume_serial, file_index_128_to_text(identity.file_index)


def _same_volume(row: sqlite3.Row, volume_id: VolumeId | None) -> bool:
    return volume_id is not None and row["serial"] == volume_id.serial and row["fs_type"] == volume_id.fs_type


def _nested_path(first: str, second: str) -> bool:
    if first == "" or second == "":
        return True
    return first.startswith(second + "\\") or second.startswith(first + "\\")


class LedgerRecorder:
    """Normal writer entry point for setup, sync, inventory, and integrity."""

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Clock,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        retry_timeout_seconds: float = DEFAULT_RETRY_TIMEOUT_SECONDS,
        retry_interval_seconds: float = 0.025,
        managed_roots: tuple[str | Path, ...] = (),
    ) -> None:
        self.path = initialize_ledger(
            path,
            busy_timeout_ms=busy_timeout_ms,
            managed_roots=managed_roots,
        )
        self._clock = clock
        self._writer = SerializedWriter(
            self.path,
            connect_ledger_writer,
            busy_timeout_ms=busy_timeout_ms,
            retry_timeout_seconds=retry_timeout_seconds,
            retry_interval_seconds=retry_interval_seconds,
        )

    def ensure_host(self, command: HostCommand) -> int:
        at = encode_utc(command.observed_at)

        def apply(connection: sqlite3.Connection) -> int:
            row = connection.execute(
                "SELECT id FROM hosts WHERE host_key = ?", (command.host_key,)
            ).fetchone()
            if row is not None:
                connection.execute(
                    "UPDATE hosts SET display_name = ?, last_seen_at = ? WHERE id = ?",
                    (command.display_name, at, row["id"]),
                )
                return int(row["id"])
            return int(
                connection.execute(
                    """INSERT INTO hosts(host_key, display_name, first_seen_at, last_seen_at)
                       VALUES (?, ?, ?, ?) RETURNING id""",
                    (command.host_key, command.display_name, at, at),
                ).fetchone()["id"]
            )

        return self._writer.transact(apply)

    def observe_volume(self, command: VolumeCommand) -> int:
        if type(command) is not VolumeCommand:
            raise TypeError("volume observation requires VolumeCommand")
        command = VolumeCommand(
            command.volume_id,
            command.evidence,
            command.observed_at,
        )
        if command.evidence.clone_ambiguous:
            raise AmbiguousVolumeError("duplicate mounted volume identity requires explicit choice")
        at = encode_utc(command.observed_at)

        def apply(connection: sqlite3.Connection) -> int:
            exact = connection.execute(
                "SELECT id FROM volumes WHERE serial = ? AND fs_type = ?",
                (command.volume_id.serial, command.volume_id.fs_type),
            ).fetchone()
            if exact is not None:
                connection.execute(
                    """UPDATE volumes
                          SET label = ?, device_id = ?, last_seen_at = ?
                        WHERE id = ?""",
                    (
                        command.evidence.label,
                        command.evidence.device_id,
                        at,
                        exact["id"],
                    ),
                )
                return int(exact["id"])
            changed_fs = connection.execute(
                "SELECT fs_type FROM volumes WHERE serial = ? LIMIT 1",
                (command.volume_id.serial,),
            ).fetchone()
            if changed_fs is not None:
                raise VolumeRebindRequired(
                    f"volume serial {command.volume_id.serial!r} changed filesystem type "
                    f"from {changed_fs['fs_type']!r} to {command.volume_id.fs_type!r}"
                )
            return int(
                connection.execute(
                    """INSERT INTO volumes(
                           serial, fs_type, label, device_id, first_seen_at, last_seen_at
                       ) VALUES (?, ?, ?, ?, ?, ?) RETURNING id""",
                    (
                        command.volume_id.serial,
                        command.volume_id.fs_type,
                        command.evidence.label,
                        command.evidence.device_id,
                        at,
                        at,
                    ),
                ).fetchone()["id"]
            )

        return self._writer.transact(apply)

    def ensure_location(self, command: LocationCommand) -> int:
        if type(command) is not LocationCommand:
            raise TypeError("location observation requires LocationCommand")
        command = LocationCommand(
            command.volume_row_id,
            command.volume_relative_path,
            command.observed_at,
        )
        canonical = validate_relative_path(command.volume_relative_path, allow_root=True)
        key = normalize_relative_path(canonical, allow_root=True)
        at = encode_utc(command.observed_at)

        def apply(connection: sqlite3.Connection) -> int:
            row = connection.execute(
                """SELECT id FROM locations
                    WHERE volume_id = ? AND volume_relative_path_key = ?""",
                (command.volume_row_id, key),
            ).fetchone()
            if row is not None:
                connection.execute(
                    """UPDATE locations
                          SET volume_relative_path = ?, last_seen_at = ?
                        WHERE id = ?""",
                    (canonical, at, row["id"]),
                )
                return int(row["id"])
            return int(
                connection.execute(
                    """INSERT INTO locations(
                           volume_id, volume_relative_path, volume_relative_path_key,
                           created_at, last_seen_at
                       ) VALUES (?, ?, ?, ?, ?) RETURNING id""",
                    (command.volume_row_id, canonical, key, at, at),
                ).fetchone()["id"]
            )

        return self._writer.transact(apply)

    def ensure_mapping(self, command: MappingCommand) -> int:
        at = encode_utc(command.observed_at)

        def apply(connection: sqlite3.Connection) -> int:
            locations = connection.execute(
                """SELECT id, volume_id, volume_relative_path_key
                     FROM locations WHERE id IN (?, ?)""",
                (command.source_location_id, command.target_location_id),
            ).fetchall()
            by_id = {int(row["id"]): row for row in locations}
            if set(by_id) != {command.source_location_id, command.target_location_id}:
                raise MappingValidationError("mapping references an unknown location")
            source = by_id[command.source_location_id]
            target = by_id[command.target_location_id]
            if source["volume_id"] == target["volume_id"] and _nested_path(
                str(source["volume_relative_path_key"]),
                str(target["volume_relative_path_key"]),
            ):
                raise MappingValidationError("mapping roots must be non-nested")
            existing = connection.execute(
                """SELECT id, deleted_at FROM mappings
                    WHERE source_location_id = ? AND target_location_id = ?
                    ORDER BY id DESC LIMIT 1""",
                (command.source_location_id, command.target_location_id),
            ).fetchone()
            if existing is not None:
                if existing["deleted_at"] is not None:
                    raise MappingRestoreRequired(
                        "matching mapping is soft-deleted and must be restored explicitly"
                    )
                return int(existing["id"])
            return int(
                connection.execute(
                    """INSERT INTO mappings(
                           source_location_id, target_location_id, created_at
                       ) VALUES (?, ?, ?) RETURNING id""",
                    (command.source_location_id, command.target_location_id, at),
                ).fetchone()["id"]
            )

        return self._writer.transact(apply)

    def begin_sync_run(self, command: SyncRunCommand) -> SyncRunRecorder:
        start_hash = _payload_hash(_sync_run_projection(command))
        started = encode_utc(command.started_at)

        def apply(connection: sqlite3.Connection) -> int:
            self._validate_run_context(connection, command)
            existing = connection.execute(
                "SELECT id, start_payload_hash FROM runs WHERE run_token = ?",
                (command.run_token,),
            ).fetchone()
            if existing is not None:
                if bytes(existing["start_payload_hash"]) != start_hash:
                    raise TokenConflictError("run token was reused with different input")
                return int(existing["id"])
            return int(
                connection.execute(
                    """INSERT INTO runs(
                           run_token, activity_kind, host_id, mapping_id,
                           source_location_id, target_location_id, plan_fingerprint,
                           selection_digest, started_at, start_payload_hash
                       ) VALUES (?, 'sync', ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
                    (
                        command.run_token,
                        command.host_id,
                        command.mapping_id,
                        command.source_location_id,
                        command.target_location_id,
                        str(command.plan.fingerprint),
                        command.selection_digest,
                        started,
                        start_hash,
                    ),
                ).fetchone()["id"]
            )

        run_row_id = self._writer.transact(apply)
        return SyncRunRecorder(self, command, run_row_id)

    def _validate_run_context(
        self, connection: sqlite3.Connection, command: SyncRunCommand
    ) -> None:
        mapping = connection.execute(
            """SELECT source_location_id, target_location_id, deleted_at
                 FROM mappings WHERE id = ?""",
            (command.mapping_id,),
        ).fetchone()
        if mapping is None or mapping["deleted_at"] is not None:
            raise MappingValidationError("run mapping is unavailable")
        if (
            mapping["source_location_id"] != command.source_location_id
            or mapping["target_location_id"] != command.target_location_id
        ):
            raise MappingValidationError("run locations do not match its mapping")
        locations = connection.execute(
            """SELECT locations.id, volumes.serial, volumes.fs_type
                 FROM locations JOIN volumes ON volumes.id = locations.volume_id
                WHERE locations.id IN (?, ?)""",
            (command.source_location_id, command.target_location_id),
        ).fetchall()
        by_id = {int(row["id"]): row for row in locations}
        if (
            command.source_location_id not in by_id
            or command.target_location_id not in by_id
        ):
            raise MappingValidationError("run location is unavailable")
        if not _same_volume(by_id[command.source_location_id], command.plan.source_volume_id):
            raise MappingValidationError("plan source volume does not match the location")
        if not _same_volume(by_id[command.target_location_id], command.plan.target_volume_id):
            raise MappingValidationError("plan target volume does not match the location")

    def finish_run(self, command: FinishRunCommand) -> RecordDisposition:
        finish_hash = _payload_hash(_finish_run_projection(command))
        ended = encode_utc(command.ended_at)

        def apply(connection: sqlite3.Connection) -> RecordDisposition:
            row = connection.execute(
                """SELECT started_at, finish_payload_hash FROM runs
                    WHERE run_token = ?""",
                (command.run_token,),
            ).fetchone()
            if row is None:
                raise RecordingError("cannot finish an unknown run")
            if ended < row["started_at"]:
                raise RecordingError("run end precedes its actual start")
            if row["finish_payload_hash"] is not None:
                if bytes(row["finish_payload_hash"]) != finish_hash:
                    raise TokenConflictError("run finish token payload changed")
                return RecordDisposition.NOOP
            connection.execute(
                """UPDATE runs
                      SET ended_at = ?, filesystem_status = ?, recording_status = ?,
                          finish_payload_hash = ?
                    WHERE run_token = ?""",
                (
                    ended,
                    command.status.value,
                    command.recording.value,
                    finish_hash,
                    command.run_token,
                ),
            )
            return RecordDisposition.APPLIED

        return self._writer.transact(apply)

    def record_inventory(self, command: InventoryCommand) -> InventoryReconcileResult:
        if type(command) is not InventoryCommand:
            raise TypeError("inventory recording requires InventoryCommand")
        command = InventoryCommand(
            command.location_id,
            command.host_id,
            command.scan,
            command.scope_token,
            command.observed_at,
            command.online,
        )
        if not command.online:
            return InventoryReconcileResult(RecordDisposition.NOOP, 0, 0)
        payload_hash = _payload_hash(_inventory_projection(command))
        command_key = f"inventory:{command.location_id}:{command.scope_token}"

        def apply(connection: sqlite3.Connection) -> InventoryReconcileResult:
            prior = self._command_receipt(connection, command_key, payload_hash)
            if prior is not None:
                return InventoryReconcileResult(prior, 0, 0)
            self._validate_inventory_location(connection, command)
            observed_count, missing_count = self._reconcile_inventory(connection, command)
            self._store_command_receipt(
                connection,
                command_key,
                "inventory",
                payload_hash,
                RecordDisposition.APPLIED,
                command.observed_at,
            )
            return InventoryReconcileResult(
                RecordDisposition.APPLIED, observed_count, missing_count
            )

        return self._writer.transact(apply)

    def change_inventory_visibility(
        self, command: InventoryVisibilityCommand
    ) -> RecordDisposition:
        payload_hash = _payload_hash(_visibility_projection(command))
        command_key = f"inventory-visibility:{command.command_id}"

        def apply(connection: sqlite3.Connection) -> RecordDisposition:
            prior = self._command_receipt(connection, command_key, payload_hash)
            if prior is not None:
                return prior
            row = connection.execute(
                """SELECT location_id, presence, acknowledged_at
                     FROM inventory WHERE id = ?""",
                (command.row_id,),
            ).fetchone()
            if row is None or int(row["location_id"]) != command.location_id:
                disposition = RecordDisposition.STALE
            elif row["presence"] != "missing":
                disposition = RecordDisposition.STALE
            elif command.action is InventoryVisibilityAction.ACKNOWLEDGE:
                if row["acknowledged_at"] is not None:
                    disposition = RecordDisposition.NOOP
                else:
                    connection.execute(
                        "UPDATE inventory SET acknowledged_at = ? WHERE id = ?",
                        (encode_utc(command.changed_at), command.row_id),
                    )
                    disposition = RecordDisposition.APPLIED
            elif row["acknowledged_at"] is None:
                disposition = RecordDisposition.NOOP
            else:
                connection.execute(
                    "UPDATE inventory SET acknowledged_at = NULL WHERE id = ?",
                    (command.row_id,),
                )
                disposition = RecordDisposition.APPLIED
            self._store_command_receipt(
                connection,
                command_key,
                "inventory-visibility",
                payload_hash,
                disposition,
                command.changed_at,
            )
            return disposition

        return self._writer.transact(apply)

    def _validate_inventory_location(
        self, connection: sqlite3.Connection, command: InventoryCommand
    ) -> None:
        row = connection.execute(
            """SELECT volumes.serial, volumes.fs_type
                 FROM locations JOIN volumes ON volumes.id = locations.volume_id
                WHERE locations.id = ?""",
            (command.location_id,),
        ).fetchone()
        if row is None:
            raise RecordingError("inventory location does not exist")
        if not _same_volume(row, command.scan.volume_id):
            raise StaleRecordingError("scan volume does not match inventory location")

    def _reconcile_inventory(
        self, connection: sqlite3.Connection, command: InventoryCommand
    ) -> tuple[int, int]:
        at = encode_utc(command.observed_at)
        observed_keys: list[str] = []
        observation_rows: list[tuple[object, ...]] = []
        for record in (*command.scan.files, *command.scan.directories):
            if isinstance(record, DirRecord) and record.rel_path == "":
                continue
            stat = record.stat
            identity_serial, identity_index = _identity_values(stat.file_identity)
            observation_rows.append(
                (
                    command.location_id,
                    record.rel_path,
                    record.rel_path_key,
                    stat.kind.value,
                    stat.size,
                    stat.mtime_ns,
                    identity_serial,
                    identity_index,
                    stat.nlink,
                    stat.metadata.attributes,
                    stat.metadata.created_ns,
                    at,
                    command.host_id,
                    command.scope_token,
                )
            )
            observed_keys.append(record.rel_path_key)
        for start in range(0, len(observation_rows), 400):
            connection.executemany(
                f"""INSERT INTO inventory(
                       location_id, rel_path, rel_path_key, entry_kind, presence,
                       observed_size, observed_mtime_ns, file_identity_volume_serial,
                       file_identity_file_index, observed_nlink, observed_attributes,
                       observed_created_ns, last_observed_at, observation_host_id,
                       scope_token
                   ) VALUES (?, ?, ?, ?, 'present', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(location_id, rel_path_key) DO UPDATE SET
                       rel_path = excluded.rel_path,
                       entry_kind = excluded.entry_kind,
                       presence = 'present',
                       observed_size = excluded.observed_size,
                       observed_mtime_ns = excluded.observed_mtime_ns,
                       file_identity_volume_serial = excluded.file_identity_volume_serial,
                       file_identity_file_index = excluded.file_identity_file_index,
                       observed_nlink = excluded.observed_nlink,
                       observed_attributes = excluded.observed_attributes,
                       observed_created_ns = excluded.observed_created_ns,
                       last_observed_at = excluded.last_observed_at,
                       observation_host_id = excluded.observation_host_id,
                       scope_token = excluded.scope_token,
                       verification_invalidated_at = CASE
                           WHEN inventory.content_algorithm IS NOT NULL
                                AND NOT {_OBSERVATION_MATCHES_ATTESTATION}
                           THEN COALESCE(
                               inventory.verification_invalidated_at,
                               excluded.last_observed_at
                           )
                           ELSE inventory.verification_invalidated_at END,
                       verification_invalidated_reason = CASE
                           WHEN inventory.content_algorithm IS NOT NULL
                                AND NOT {_OBSERVATION_MATCHES_ATTESTATION}
                           THEN COALESCE(
                               inventory.verification_invalidated_reason,
                               'metadata-drift'
                           )
                           ELSE inventory.verification_invalidated_reason END,
                       reappeared_at = CASE
                           WHEN inventory.presence = 'missing' THEN excluded.last_observed_at
                           ELSE inventory.reappeared_at END,
                       missing_since = NULL,
                       acknowledged_at = NULL,
                       unsupported_reason = NULL""",
                observation_rows[start : start + 400],
            )
        unsupported_rows = [
            (
                command.location_id,
                record.rel_path,
                record.rel_path_key,
                at,
                command.host_id,
                command.scope_token,
                record.reason.value,
            )
            for record in command.scan.unsupported
        ]
        observed_keys.extend(record.rel_path_key for record in command.scan.unsupported)
        for start in range(0, len(unsupported_rows), 400):
            connection.executemany(
                """INSERT INTO inventory(
                       location_id, rel_path, rel_path_key, entry_kind, presence,
                       last_observed_at, observation_host_id, scope_token,
                       unsupported_reason
                   ) VALUES (?, ?, ?, 'unsupported', 'unsupported', ?, ?, ?, ?)
                   ON CONFLICT(location_id, rel_path_key) DO UPDATE SET
                       rel_path = excluded.rel_path,
                       entry_kind = 'unsupported', presence = 'unsupported',
                       observed_size = NULL, observed_mtime_ns = NULL,
                       file_identity_volume_serial = NULL,
                       file_identity_file_index = NULL, observed_nlink = NULL,
                       observed_attributes = NULL, observed_created_ns = NULL,
                       last_observed_at = excluded.last_observed_at,
                       observation_host_id = excluded.observation_host_id,
                       scope_token = excluded.scope_token,
                       unsupported_reason = excluded.unsupported_reason,
                       verification_invalidated_at = CASE
                           WHEN inventory.content_algorithm IS NOT NULL
                           THEN COALESCE(
                               inventory.verification_invalidated_at,
                               excluded.last_observed_at
                           )
                           ELSE inventory.verification_invalidated_at END,
                       verification_invalidated_reason = CASE
                           WHEN inventory.content_algorithm IS NOT NULL
                           THEN COALESCE(
                               inventory.verification_invalidated_reason,
                               'metadata-drift'
                           )
                           ELSE inventory.verification_invalidated_reason END,
                       reappeared_at = CASE
                           WHEN inventory.presence = 'missing' THEN excluded.last_observed_at
                           ELSE inventory.reappeared_at END,
                       missing_since = NULL, acknowledged_at = NULL""",
                unsupported_rows[start : start + 400],
            )

        missing = 0
        scope_kind = command.scan.scope.kind
        if (
            command.scan.complete
            and scope_kind in {ScanScopeKind.FULL, ScanScopeKind.SUBTREES}
        ):
            connection.execute(
                "CREATE TEMP TABLE IF NOT EXISTS current_scan_keys(rel_path_key TEXT PRIMARY KEY) WITHOUT ROWID"
            )
            connection.execute("DELETE FROM current_scan_keys")
            connection.executemany(
                "INSERT INTO current_scan_keys(rel_path_key) VALUES (?)",
                ((key,) for key in observed_keys),
            )
        if command.scan.complete and scope_kind is ScanScopeKind.FULL:
            cursor = connection.execute(
                """UPDATE inventory
                      SET presence = 'missing',
                          missing_since = COALESCE(missing_since, ?),
                          scope_token = ?,
                          verification_invalidated_at = CASE
                              WHEN content_algorithm IS NOT NULL
                              THEN COALESCE(verification_invalidated_at, ?)
                              ELSE verification_invalidated_at END,
                          verification_invalidated_reason = CASE
                              WHEN content_algorithm IS NOT NULL
                              THEN COALESCE(
                                  verification_invalidated_reason,
                                  'metadata-drift'
                              )
                              ELSE verification_invalidated_reason END
                    WHERE location_id = ?
                      AND presence IN ('present', 'unsupported')
                      AND NOT EXISTS (
                          SELECT 1 FROM current_scan_keys
                           WHERE current_scan_keys.rel_path_key = inventory.rel_path_key
                      )""",
                (at, command.scope_token, at, command.location_id),
            )
            missing = cursor.rowcount
            connection.execute("DELETE FROM current_scan_keys")
        elif command.scan.complete and scope_kind is ScanScopeKind.PATHS:
            observed = set(observed_keys)
            absent = [
                normalize_relative_path(path)
                for path in command.scan.scope.selected_paths
                if normalize_relative_path(path) not in observed
            ]
            for start in range(0, len(absent), 400):
                chunk = absent[start : start + 400]
                placeholders = ",".join("?" for _ in chunk)
                cursor = connection.execute(
                    f"""UPDATE inventory
                           SET presence = 'missing',
                               missing_since = COALESCE(missing_since, ?),
                               scope_token = ?,
                               verification_invalidated_at = CASE
                                   WHEN content_algorithm IS NOT NULL
                                   THEN COALESCE(verification_invalidated_at, ?)
                                   ELSE verification_invalidated_at END,
                               verification_invalidated_reason = CASE
                                   WHEN content_algorithm IS NOT NULL
                                   THEN COALESCE(
                                       verification_invalidated_reason,
                                       'metadata-drift'
                                   )
                                   ELSE verification_invalidated_reason END
                         WHERE location_id = ? AND rel_path_key IN ({placeholders})
                           AND presence IN ('present', 'unsupported')""",
                    (at, command.scope_token, at, command.location_id, *chunk),
                )
                missing += cursor.rowcount
        elif command.scan.complete and scope_kind is ScanScopeKind.SUBTREES:
            observed = set(observed_keys)
            absent_exact = [
                normalize_relative_path(path)
                for path in command.scan.scope.selected_paths
                if normalize_relative_path(path) not in observed
            ]
            for start in range(0, len(absent_exact), 400):
                chunk = absent_exact[start : start + 400]
                placeholders = ",".join("?" for _ in chunk)
                cursor = connection.execute(
                    f"""UPDATE inventory
                           SET presence = 'missing',
                               missing_since = COALESCE(missing_since, ?),
                               scope_token = ?,
                               verification_invalidated_at = CASE
                                   WHEN content_algorithm IS NOT NULL
                                   THEN COALESCE(verification_invalidated_at, ?)
                                   ELSE verification_invalidated_at END,
                               verification_invalidated_reason = CASE
                                   WHEN content_algorithm IS NOT NULL
                                   THEN COALESCE(
                                       verification_invalidated_reason,
                                       'metadata-drift'
                                   )
                                   ELSE verification_invalidated_reason END
                         WHERE location_id = ?
                           AND rel_path_key IN ({placeholders})
                           AND presence IN ('present', 'unsupported')""",
                    (at, command.scope_token, at, command.location_id, *chunk),
                )
                missing += cursor.rowcount
            for root in command.scan.scope.subtree_roots:
                root_key = normalize_relative_path(root)
                cursor = connection.execute(
                    """UPDATE inventory
                          SET presence = 'missing',
                              missing_since = COALESCE(missing_since, ?),
                              scope_token = ?,
                              verification_invalidated_at = CASE
                                  WHEN content_algorithm IS NOT NULL
                                  THEN COALESCE(verification_invalidated_at, ?)
                                  ELSE verification_invalidated_at END,
                              verification_invalidated_reason = CASE
                                  WHEN content_algorithm IS NOT NULL
                                  THEN COALESCE(
                                      verification_invalidated_reason,
                                      'metadata-drift'
                                  )
                                  ELSE verification_invalidated_reason END
                        WHERE location_id = ?
                          AND presence IN ('present', 'unsupported')
                          AND rel_path_key = ?
                          AND NOT EXISTS (
                              SELECT 1 FROM current_scan_keys
                               WHERE current_scan_keys.rel_path_key =
                                     inventory.rel_path_key
                          )""",
                    (
                        at,
                        command.scope_token,
                        at,
                        command.location_id,
                        root_key,
                    ),
                )
                missing += cursor.rowcount
                cursor = connection.execute(
                    f"""UPDATE inventory
                           SET presence = 'missing',
                               missing_since = COALESCE(missing_since, ?),
                               scope_token = ?,
                               verification_invalidated_at = CASE
                                   WHEN content_algorithm IS NOT NULL
                                   THEN COALESCE(verification_invalidated_at, ?)
                                   ELSE verification_invalidated_at END,
                               verification_invalidated_reason = CASE
                                   WHEN content_algorithm IS NOT NULL
                                   THEN COALESCE(
                                       verification_invalidated_reason,
                                       'metadata-drift'
                                   )
                                   ELSE verification_invalidated_reason END
                         WHERE location_id = ?
                           AND presence IN ('present', 'unsupported')
                           AND {_SUBTREE_DESCENDANT_PREDICATE}
                           AND NOT EXISTS (
                               SELECT 1 FROM current_scan_keys
                                WHERE current_scan_keys.rel_path_key =
                                      inventory.rel_path_key
                           )""",
                    (
                        at,
                        command.scope_token,
                        at,
                        command.location_id,
                        root_key,
                        root_key,
                    ),
                )
                missing += cursor.rowcount
            connection.execute("DELETE FROM current_scan_keys")
        return len(observed_keys), missing

    def record_integrity(self, command: IntegrityRecordCommand) -> RecordDisposition:
        command_key = f"integrity:{command.scope_token}:{command.item_id}"
        payload_hash = _payload_hash(_integrity_projection(command))

        def apply(connection: sqlite3.Connection) -> RecordDisposition:
            prior = self._command_receipt(connection, command_key, payload_hash)
            if prior is not None:
                return prior
            disposition = self._apply_integrity(connection, command)
            self._store_command_receipt(
                connection,
                command_key,
                "integrity",
                payload_hash,
                disposition,
                command.attestation.content.observed_at,
            )
            return disposition

        return self._writer.transact(apply)

    def record_verification_invalidation(
        self, command: VerificationInvalidationCommand
    ) -> RecordDisposition:
        command_key = (
            f"verification-invalidation:{command.scope_token}:{command.item_id}"
        )
        payload_hash = _payload_hash(_verification_invalidation_projection(command))

        def apply(connection: sqlite3.Connection) -> RecordDisposition:
            prior = self._command_receipt(connection, command_key, payload_hash)
            if prior is not None:
                return prior
            disposition = self._apply_verification_invalidation(connection, command)
            self._store_command_receipt(
                connection,
                command_key,
                "verification-invalidation",
                payload_hash,
                disposition,
                command.invalidated_at,
            )
            return disposition

        return self._writer.transact(apply)

    def _apply_integrity(
        self, connection: sqlite3.Connection, command: IntegrityRecordCommand
    ) -> RecordDisposition:
        row = connection.execute(
            "SELECT * FROM inventory WHERE id = ?", (command.row_id,)
        ).fetchone()
        if row is None:
            return RecordDisposition.STALE
        if (
            str(row["location_id"]) != command.location_id
            or row["rel_path_key"] != command.rel_path_key
            or row["presence"] != InventoryState.PRESENT.value
            or row["scope_token"] != command.scope_token
            or not self._row_matches_stat(row, command.expected_stat)
            or not self._row_matches_attestation(row, command.expected_baseline)
            or not self._row_matches_invalidation(
                row, command.expected_invalidation
            )
        ):
            return RecordDisposition.STALE
        subject = command.attestation.subject
        expected = command.expected_stat
        if (
            subject.kind is not expected.kind
            or subject.size != expected.size
            or subject.mtime_ns != expected.mtime_ns
            or subject.file_identity != expected.file_identity
        ):
            raise RecordingError("integrity attestation subject does not match its guarded stat")

        desired = command.attestation
        already = self._row_matches_attestation(row, desired)
        desired_verified_at = (
            encode_utc(desired.content.observed_at)
            if command.advances_last_verified
            else None
        )
        verified_ok = row["last_verified_at"] == desired_verified_at
        reappeared_ok = not command.clear_reappeared or row["reappeared_at"] is None
        invalidation_cleared = row["verification_invalidated_at"] is None
        if already and verified_ok and reappeared_ok and invalidation_cleared:
            return RecordDisposition.NOOP

        subject = desired.subject
        identity_serial, identity_index = _identity_values(subject.file_identity)
        connection.execute(
            """UPDATE inventory
                  SET content_algorithm = ?, content_digest = ?, content_size = ?,
                      hash_provenance = ?, content_observed_at = ?,
                      attested_kind = ?, attested_size = ?, attested_mtime_ns = ?,
                      attested_file_identity_volume_serial = ?,
                      attested_file_identity_file_index = ?, attested_nlink = ?,
                      attested_attributes = ?, attested_created_ns = ?,
                      last_verified_at = ?,
                      verification_invalidated_at = NULL,
                      verification_invalidated_reason = NULL,
                      reappeared_at = CASE WHEN ? THEN NULL ELSE reappeared_at END
                WHERE id = ?""",
            (
                desired.content.algorithm,
                desired.content.digest,
                desired.content.size,
                desired.content.provenance.value,
                encode_utc(desired.content.observed_at),
                subject.kind.value,
                subject.size,
                subject.mtime_ns,
                identity_serial,
                identity_index,
                subject.nlink,
                subject.metadata.attributes,
                subject.metadata.created_ns,
                desired_verified_at,
                command.clear_reappeared,
                command.row_id,
            ),
        )
        return RecordDisposition.APPLIED

    def _apply_verification_invalidation(
        self,
        connection: sqlite3.Connection,
        command: VerificationInvalidationCommand,
    ) -> RecordDisposition:
        row = connection.execute(
            "SELECT * FROM inventory WHERE id = ?", (command.row_id,)
        ).fetchone()
        if row is None:
            return RecordDisposition.STALE
        if (
            str(row["location_id"]) != command.location_id
            or row["rel_path_key"] != command.rel_path_key
            or row["presence"] != command.expected_state.value
            or row["scope_token"] != command.scope_token
            or not self._row_matches_stat(row, command.expected_stat)
            or not self._row_matches_attestation(row, command.expected_baseline)
            or not self._row_matches_invalidation(
                row, command.expected_invalidation
            )
        ):
            return RecordDisposition.STALE
        connection.execute(
            """UPDATE inventory
                  SET verification_invalidated_at =
                          COALESCE(verification_invalidated_at, ?),
                      verification_invalidated_reason = CASE
                          WHEN verification_invalidated_reason = 'hash-mismatch'
                               OR ? = 'hash-mismatch'
                          THEN 'hash-mismatch'
                          ELSE 'metadata-drift' END
                WHERE id = ?""",
            (
                encode_utc(command.invalidated_at),
                command.reason.value,
                command.row_id,
            ),
        )
        return RecordDisposition.APPLIED

    @staticmethod
    def _row_matches_stat(row: sqlite3.Row, stat: FileStat) -> bool:
        identity = _identity_values(stat.file_identity)
        return (
            row["entry_kind"] == stat.kind.value
            and row["observed_size"] == stat.size
            and row["observed_mtime_ns"] == stat.mtime_ns
            and row["file_identity_volume_serial"] == identity[0]
            and row["file_identity_file_index"] == identity[1]
            and row["observed_nlink"] == stat.nlink
            and row["observed_attributes"] == stat.metadata.attributes
            and row["observed_created_ns"] == stat.metadata.created_ns
        )

    @staticmethod
    def _row_matches_attestation(
        row: sqlite3.Row, attestation: Attestation | None
    ) -> bool:
        if attestation is None:
            return row["content_algorithm"] is None
        subject = attestation.subject
        identity = _identity_values(subject.file_identity)
        return (
            row["content_algorithm"] == attestation.content.algorithm
            and row["content_digest"] is not None
            and bytes(row["content_digest"]) == attestation.content.digest
            and row["content_size"] == attestation.content.size
            and row["hash_provenance"] == attestation.content.provenance.value
            and row["content_observed_at"] == encode_utc(attestation.content.observed_at)
            and row["attested_kind"] == subject.kind.value
            and row["attested_size"] == subject.size
            and row["attested_mtime_ns"] == subject.mtime_ns
            and row["attested_file_identity_volume_serial"] == identity[0]
            and row["attested_file_identity_file_index"] == identity[1]
            and row["attested_nlink"] == subject.nlink
            and row["attested_attributes"] == subject.metadata.attributes
            and row["attested_created_ns"] == subject.metadata.created_ns
        )

    @staticmethod
    def _row_attested_subject_matches_stat(
        row: sqlite3.Row,
        stat: FileStat,
    ) -> bool:
        if row["content_algorithm"] is None:
            return True
        identity = _identity_values(stat.file_identity)
        attested_identity_is_wildcard = (
            row["attested_file_identity_volume_serial"] is None
            and row["attested_file_identity_file_index"] is None
        )
        return (
            row["attested_kind"] == stat.kind.value
            and row["attested_size"] == stat.size
            and row["attested_mtime_ns"] == stat.mtime_ns
            and (
                attested_identity_is_wildcard
                or (
                    row["attested_file_identity_volume_serial"] == identity[0]
                    and row["attested_file_identity_file_index"] == identity[1]
                )
            )
        )

    @staticmethod
    def _row_matches_invalidation(
        row: sqlite3.Row,
        expected: VerificationInvalidation | None,
    ) -> bool:
        if expected is None:
            return (
                row["verification_invalidated_at"] is None
                and row["verification_invalidated_reason"] is None
            )
        return (
            row["verification_invalidated_at"] == encode_utc(expected.at)
            and row["verification_invalidated_reason"] == expected.reason.value
        )

    def _command_receipt(
        self, connection: sqlite3.Connection, key: str, payload_hash: bytes
    ) -> RecordDisposition | None:
        row = connection.execute(
            "SELECT payload_hash, disposition FROM recording_commands WHERE command_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        if bytes(row["payload_hash"]) != payload_hash:
            raise TokenConflictError(f"recording command token changed payload: {key}")
        prior = RecordDisposition(str(row["disposition"]))
        return RecordDisposition.NOOP if prior is RecordDisposition.APPLIED else prior

    @staticmethod
    def _store_command_receipt(
        connection: sqlite3.Connection,
        key: str,
        kind: str,
        payload_hash: bytes,
        disposition: RecordDisposition,
        at: datetime,
    ) -> None:
        connection.execute(
            """INSERT INTO recording_commands(
                   command_key, command_kind, payload_hash, disposition, recorded_at
               ) VALUES (?, ?, ?, ?, ?)""",
            (key, kind, payload_hash, disposition.value, encode_utc(at)),
        )

    def _upsert_observation(
        self,
        connection: sqlite3.Connection,
        location_id: int,
        host_id: int,
        scope_token: str,
        rel_path: str,
        stat: FileStat,
        at: str,
    ) -> int:
        canonical = validate_relative_path(rel_path)
        key = normalize_relative_path(canonical)
        identity_serial, identity_index = _identity_values(stat.file_identity)
        row = connection.execute(
            f"""INSERT INTO inventory(
                   location_id, rel_path, rel_path_key, entry_kind, presence,
                   observed_size, observed_mtime_ns, file_identity_volume_serial,
                   file_identity_file_index, observed_nlink, observed_attributes,
                   observed_created_ns, last_observed_at, observation_host_id,
                   scope_token
               ) VALUES (?, ?, ?, ?, 'present', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(location_id, rel_path_key) DO UPDATE SET
                   rel_path = excluded.rel_path,
                   entry_kind = excluded.entry_kind,
                   presence = 'present',
                   observed_size = excluded.observed_size,
                   observed_mtime_ns = excluded.observed_mtime_ns,
                   file_identity_volume_serial = excluded.file_identity_volume_serial,
                   file_identity_file_index = excluded.file_identity_file_index,
                   observed_nlink = excluded.observed_nlink,
                   observed_attributes = excluded.observed_attributes,
                   observed_created_ns = excluded.observed_created_ns,
                   last_observed_at = excluded.last_observed_at,
                   observation_host_id = excluded.observation_host_id,
                   scope_token = excluded.scope_token,
                   verification_invalidated_at = CASE
                       WHEN inventory.content_algorithm IS NOT NULL
                            AND NOT {_OBSERVATION_MATCHES_ATTESTATION}
                       THEN COALESCE(
                           inventory.verification_invalidated_at,
                           excluded.last_observed_at
                       )
                       ELSE inventory.verification_invalidated_at END,
                   verification_invalidated_reason = CASE
                       WHEN inventory.content_algorithm IS NOT NULL
                            AND NOT {_OBSERVATION_MATCHES_ATTESTATION}
                       THEN COALESCE(
                           inventory.verification_invalidated_reason,
                           'metadata-drift'
                       )
                       ELSE inventory.verification_invalidated_reason END,
                   reappeared_at = CASE
                       WHEN inventory.presence = 'missing' THEN excluded.last_observed_at
                       ELSE inventory.reappeared_at END,
                   missing_since = NULL,
                   acknowledged_at = NULL,
                   unsupported_reason = NULL
               RETURNING id""",
            (
                location_id,
                canonical,
                key,
                stat.kind.value,
                stat.size,
                stat.mtime_ns,
                identity_serial,
                identity_index,
                stat.nlink,
                stat.metadata.attributes,
                stat.metadata.created_ns,
                at,
                host_id,
                scope_token,
            ),
        ).fetchone()
        return int(row["id"])

    def flush(self) -> None:
        self._writer.flush()

    def close(self) -> None:
        self._writer.close()

    def __enter__(self) -> LedgerRecorder:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


class SyncRunRecorder:
    """Run-bound narrow view consumed directly by the executor."""

    def __init__(
        self, owner: LedgerRecorder, command: SyncRunCommand, run_row_id: int
    ) -> None:
        self._owner = owner
        self._command = command
        self._run_row_id = run_row_id
        self._operations = {operation.op_id: operation for operation in command.plan.operations}

    def flush(self) -> None:
        self._owner.flush()

    def finish(self, command: FinishRunCommand) -> RecordDisposition:
        if command.run_token != self._command.run_token:
            raise TokenConflictError("finish command belongs to another run")
        return self._owner.finish_run(command)

    def record_copied(
        self, op: OpId, attestation: Attestation
    ) -> RecordedCopyIdentity:
        identity = self._record(
            op,
            OperationKind.COPY,
            {"attestation": _attestation_projection(attestation)},
            lambda connection, plan_op, at: self._record_copy_like(
                connection, plan_op, attestation, at
            ),
            return_copy_identity=True,
        )
        if identity is None:  # guarded by _record; defensive only
            raise RecordingError("copy recording did not return a durable identity")
        return identity

    def record_updated(
        self, op: OpId, attestation: Attestation
    ) -> RecordedCopyIdentity:
        identity = self._record(
            op,
            OperationKind.UPDATE,
            {"attestation": _attestation_projection(attestation)},
            lambda connection, plan_op, at: self._record_copy_like(
                connection, plan_op, attestation, at
            ),
            return_copy_identity=True,
        )
        if identity is None:  # guarded by _record; defensive only
            raise RecordingError("update recording did not return a durable identity")
        return identity

    def record_moved(self, op: OpId, target: FileStat) -> None:
        self._record(op, OperationKind.MOVE, {"target": file_stat_projection(target)}, lambda connection, plan_op, at: self._record_move(connection, plan_op, target, at, None))

    def record_recased(self, op: OpId, target: FileStat) -> None:
        self._record(op, OperationKind.RECASE, {"target": file_stat_projection(target)}, lambda connection, plan_op, at: self._record_move(connection, plan_op, target, at, None))

    def record_move_updated(
        self, op: OpId, attestation: Attestation
    ) -> RecordedCopyIdentity:
        identity = self._record(
            op,
            OperationKind.MOVE_UPDATE,
            {"attestation": _attestation_projection(attestation)},
            lambda connection, plan_op, at: self._record_move(
                connection, plan_op, attestation.subject, at, attestation
            ),
            return_copy_identity=True,
        )
        if identity is None:  # guarded by _record; defensive only
            raise RecordingError(
                "move-update recording did not return a durable identity"
            )
        return identity

    def record_integrity(
        self, command: IntegrityRecordCommand
    ) -> RecordDisposition:
        """Use the same serialized writer for linked post-copy verification."""

        return self._owner.record_integrity(command)

    def record_verification_invalidation(
        self, command: VerificationInvalidationCommand
    ) -> RecordDisposition:
        """Use the same serialized writer for linked negative verification."""

        return self._owner.record_verification_invalidation(command)

    def record_mkdir(self, op: OpId, target: FileStat) -> None:
        def apply(connection: sqlite3.Connection, plan_op: PlanOperation, at: str) -> None:
            if target.kind is not EntryKind.DIRECTORY:
                raise StaleRecordingError("mkdir result is not a directory")
            self._owner._upsert_observation(connection, self._command.target_location_id, self._command.host_id, self._command.run_token, plan_op.target_rel_path, target, at)

        self._record(op, OperationKind.MKDIR, {"target": file_stat_projection(target)}, apply)

    def record_trashed(self, op: OpId, trash_relative_path: str, target: FileStat) -> None:
        validate_relative_path(trash_relative_path)
        self._record(op, OperationKind.TRASH, {"trash": trash_relative_path, "target": file_stat_projection(target)}, lambda connection, plan_op, at: self._record_absent(connection, plan_op, target, at), trash_relative_path)

    def record_deleted(self, op: OpId, prior: FileStat) -> None:
        self._record(op, OperationKind.DELETE, {"prior": file_stat_projection(prior)}, lambda connection, plan_op, at: self._record_absent(connection, plan_op, prior, at))

    def record_noop(self, op: OpId, source: FileStat, target: FileStat) -> None:
        def apply(connection: sqlite3.Connection, plan_op: PlanOperation, at: str) -> None:
            if source != plan_op.source_expected or target != plan_op.target_expected:
                raise StaleRecordingError("no-op live snapshots differ from the reviewed plan")
            if plan_op.source_rel_path is None:
                raise StaleRecordingError("no-op reviewed operation has no source path")
            source_id = self._owner._upsert_observation(connection, self._command.source_location_id, self._command.host_id, self._command.run_token, plan_op.source_rel_path, source, at)
            target_id = self._owner._upsert_observation(connection, self._command.target_location_id, self._command.host_id, self._command.run_token, plan_op.target_rel_path, target, at)
            self._record_correspondence(connection, plan_op, source_id, target_id, source, target, at)

        self._record(op, OperationKind.NOOP, {"source": file_stat_projection(source), "target": file_stat_projection(target)}, apply)

    def _record(
        self,
        op_id: OpId,
        expected_kind: OperationKind,
        evidence: object,
        apply: Callable[[sqlite3.Connection, PlanOperation, str], int | None],
        trash_relative_path: str | None = None,
        *,
        return_copy_identity: bool = False,
    ) -> RecordedCopyIdentity | None:
        if op_id not in self._command.selection:
            raise StaleRecordingError("operation is not part of the reviewed selection")
        operation = self._operations.get(op_id)
        if operation is None or operation.kind is not expected_kind:
            raise StaleRecordingError("recording call does not match its reviewed operation")
        payload_hash = _payload_hash(
            {
                "run_token": self._command.run_token,
                "operation": operation_projection(operation),
                "evidence": evidence,
                "trash_relative_path": trash_relative_path,
            }
        )

        def transaction(
            connection: sqlite3.Connection,
        ) -> RecordedCopyIdentity | None:
            prior = connection.execute(
                "SELECT payload_hash FROM operations WHERE run_id = ? AND op_token = ?",
                (self._run_row_id, str(op_id)),
            ).fetchone()
            if prior is not None:
                if bytes(prior["payload_hash"]) != payload_hash:
                    raise TokenConflictError("operation token was reused with different evidence")
                return (
                    self._recorded_copy_identity(connection, operation)
                    if return_copy_identity
                    else None
                )
            now = self._owner._clock.now()
            at = encode_utc(now)
            row_id = apply(connection, operation, at)
            connection.execute(
                """INSERT INTO operations(
                       run_id, op_token, kind, source_rel_path, target_rel_path,
                       outcome, content_bytes, trash_rel_path, recorded_at, payload_hash
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self._run_row_id,
                    str(op_id),
                    operation.kind.value,
                    operation.source_rel_path,
                    operation.target_rel_path,
                    "skipped" if operation.kind is OperationKind.NOOP else "succeeded",
                    operation.content_bytes,
                    trash_relative_path,
                    at,
                    payload_hash,
                ),
            )
            if not return_copy_identity:
                return None
            if row_id is None:
                raise RecordingError(
                    "copy-producing transaction did not identify its target row"
                )
            return self._recorded_copy_identity(
                connection, operation, row_id=row_id
            )

        return self._owner._writer.transact(transaction)

    def _recorded_copy_identity(
        self,
        connection: sqlite3.Connection,
        operation: PlanOperation,
        *,
        row_id: int | None = None,
    ) -> RecordedCopyIdentity:
        key = normalize_relative_path(operation.target_rel_path)
        if row_id is None:
            row = connection.execute(
                """SELECT id, scope_token, rel_path_key
                     FROM inventory
                    WHERE location_id = ? AND rel_path_key = ?""",
                (self._command.target_location_id, key),
            ).fetchone()
        else:
            row = connection.execute(
                """SELECT id, scope_token, rel_path_key
                     FROM inventory
                    WHERE id = ? AND location_id = ? AND rel_path_key = ?""",
                (row_id, self._command.target_location_id, key),
            ).fetchone()
        if (
            row is None
            or row["scope_token"] != self._command.run_token
            or row["rel_path_key"] != key
        ):
            raise StaleRecordingError(
                "recorded copy target identity is no longer available"
            )
        return RecordedCopyIdentity(
            row_id=str(row["id"]),
            location_id=str(self._command.target_location_id),
            scope_token=str(row["scope_token"]),
            rel_path_key=str(row["rel_path_key"]),
        )

    def _record_copy_like(
        self,
        connection: sqlite3.Connection,
        operation: PlanOperation,
        attestation: Attestation,
        at: str,
    ) -> int:
        if (
            operation.source_rel_path is None
            or operation.source_expected is None
            or attestation.content.provenance is not Provenance.COPY_ATTESTED
            or attestation.content.size != attestation.subject.size
            or attestation.content.size != operation.source_expected.size
            or attestation.subject.kind is not EntryKind.FILE
            or not self._matches_intended(operation, attestation.subject)
        ):
            raise StaleRecordingError("copy evidence is incomplete or not copy-attested")
        source_id = self._owner._upsert_observation(
            connection,
            self._command.source_location_id,
            self._command.host_id,
            self._command.run_token,
            operation.source_rel_path,
            operation.source_expected,
            at,
        )
        target_id = self._owner._upsert_observation(
            connection,
            self._command.target_location_id,
            self._command.host_id,
            self._command.run_token,
            operation.target_rel_path,
            attestation.subject,
            at,
        )
        self._store_attestation(connection, target_id, attestation)
        self._record_correspondence(
            connection,
            operation,
            source_id,
            target_id,
            operation.source_expected,
            attestation.subject,
            at,
        )
        return target_id

    def _record_move(
        self,
        connection: sqlite3.Connection,
        operation: PlanOperation,
        target: FileStat,
        at: str,
        attestation: Attestation | None,
    ) -> int:
        if operation.source_rel_path is None or operation.source_expected is None:
            raise StaleRecordingError("move lacks source evidence")
        if attestation is None:
            if (
                operation.prior_target_expected is None
                or not self._matches_reviewed_stat(
                    target, operation.prior_target_expected
                )
            ):
                raise StaleRecordingError(
                    "move result is not the reviewed target version"
                )
        elif not self._matches_intended(operation, target):
            raise StaleRecordingError("move result differs from reviewed intent")
        source_id = self._owner._upsert_observation(
            connection,
            self._command.source_location_id,
            self._command.host_id,
            self._command.run_token,
            operation.source_rel_path,
            operation.source_expected,
            at,
        )
        target_id = self._move_target_row(connection, operation, target, at)
        if attestation is not None:
            if attestation.content.provenance is not Provenance.COPY_ATTESTED or attestation.subject != target:
                raise StaleRecordingError("move-update attestation is inconsistent")
            self._store_attestation(connection, target_id, attestation)
        self._record_correspondence(connection, operation, source_id, target_id, operation.source_expected, target, at)
        return target_id

    def _move_target_row(
        self,
        connection: sqlite3.Connection,
        operation: PlanOperation,
        target: FileStat,
        at: str,
    ) -> int:
        new_key = normalize_relative_path(operation.target_rel_path)
        collision = connection.execute(
            "SELECT id, presence FROM inventory WHERE location_id = ? AND rel_path_key = ?",
            (self._command.target_location_id, new_key),
        ).fetchone()
        old_path = operation.prior_target_rel_path or operation.target_rel_path
        old_key = normalize_relative_path(old_path)
        old = connection.execute(
            "SELECT * FROM inventory WHERE location_id = ? AND rel_path_key = ?",
            (self._command.target_location_id, old_key),
        ).fetchone()
        if collision is not None and (old is None or collision["id"] != old["id"]):
            if collision["presence"] != "missing":
                raise StaleRecordingError("move destination collides with present ledger evidence")
            connection.execute("DELETE FROM inventory WHERE id = ?", (collision["id"],))
        if (
            old is not None
            and operation.prior_target_expected is not None
            and not self._owner._row_matches_stat(old, operation.prior_target_expected)
        ):
            raise StaleRecordingError("move source ledger evidence differs from the reviewed plan")
        if old is None:
            return self._owner._upsert_observation(
                connection,
                self._command.target_location_id,
                self._command.host_id,
                self._command.run_token,
                operation.target_rel_path,
                target,
                at,
            )
        identity_serial, identity_index = _identity_values(target.file_identity)
        invalidated = not self._owner._row_attested_subject_matches_stat(old, target)
        invalidated_at = (
            old["verification_invalidated_at"] or at
            if invalidated
            else old["verification_invalidated_at"]
        )
        invalidated_reason = (
            old["verification_invalidated_reason"]
            or VerificationInvalidationReason.METADATA_DRIFT.value
            if invalidated
            else old["verification_invalidated_reason"]
        )
        connection.execute(
            """UPDATE inventory SET
                   rel_path = ?, rel_path_key = ?, entry_kind = ?, presence = 'present',
                   observed_size = ?, observed_mtime_ns = ?,
                   file_identity_volume_serial = ?, file_identity_file_index = ?,
                   observed_nlink = ?, observed_attributes = ?, observed_created_ns = ?,
                   last_observed_at = ?, observation_host_id = ?, scope_token = ?,
                   missing_since = NULL, acknowledged_at = NULL, reappeared_at = NULL,
                   unsupported_reason = NULL,
                   verification_invalidated_at = ?,
                   verification_invalidated_reason = ?
                 WHERE id = ?""",
            (
                operation.target_rel_path,
                new_key,
                target.kind.value,
                target.size,
                target.mtime_ns,
                identity_serial,
                identity_index,
                target.nlink,
                target.metadata.attributes,
                target.metadata.created_ns,
                at,
                self._command.host_id,
                self._command.run_token,
                invalidated_at,
                invalidated_reason,
                old["id"],
            ),
        )
        return int(old["id"])

    @staticmethod
    def _matches_intended(operation: PlanOperation, actual: FileStat) -> bool:
        intended = operation.intended
        if intended is None:
            return True
        return (
            actual.kind is intended.kind
            and actual.size == intended.size
            and actual.mtime_ns == intended.mtime_ns
        )

    @staticmethod
    def _matches_reviewed_stat(actual: FileStat, expected: FileStat) -> bool:
        return (
            actual.kind is expected.kind
            and actual.size == expected.size
            and actual.mtime_ns == expected.mtime_ns
            and actual.nlink == expected.nlink
            and actual.metadata == expected.metadata
            and (
                expected.file_identity is None
                or actual.file_identity == expected.file_identity
            )
        )

    def _record_absent(
        self,
        connection: sqlite3.Connection,
        operation: PlanOperation,
        prior: FileStat,
        at: str,
    ) -> None:
        if operation.target_expected is not None and prior != operation.target_expected:
            raise StaleRecordingError("destructive result differs from reviewed target evidence")
        row_id = self._owner._upsert_observation(
            connection,
            self._command.target_location_id,
            self._command.host_id,
            self._command.run_token,
            operation.target_rel_path,
            prior,
            at,
        )
        connection.execute(
            """UPDATE inventory
                  SET presence = 'missing', missing_since = ?, scope_token = ?,
                      verification_invalidated_at = CASE
                          WHEN content_algorithm IS NOT NULL
                          THEN COALESCE(verification_invalidated_at, ?)
                          ELSE verification_invalidated_at END,
                      verification_invalidated_reason = CASE
                          WHEN content_algorithm IS NOT NULL
                          THEN COALESCE(
                              verification_invalidated_reason,
                              'metadata-drift'
                          )
                          ELSE verification_invalidated_reason END
                WHERE id = ?""",
            (at, self._command.run_token, at, row_id),
        )

    @staticmethod
    def _store_attestation(
        connection: sqlite3.Connection, row_id: int, attestation: Attestation
    ) -> None:
        subject = attestation.subject
        identity_serial, identity_index = _identity_values(subject.file_identity)
        connection.execute(
            """UPDATE inventory SET
                   content_algorithm = ?, content_digest = ?, content_size = ?,
                   hash_provenance = ?, content_observed_at = ?,
                   attested_kind = ?, attested_size = ?, attested_mtime_ns = ?,
                   attested_file_identity_volume_serial = ?,
                   attested_file_identity_file_index = ?, attested_nlink = ?,
                   attested_attributes = ?, attested_created_ns = ?,
                   last_verified_at = NULL,
                   verification_invalidated_at = NULL,
                   verification_invalidated_reason = NULL
                 WHERE id = ?""",
            (
                attestation.content.algorithm,
                attestation.content.digest,
                attestation.content.size,
                attestation.content.provenance.value,
                encode_utc(attestation.content.observed_at),
                subject.kind.value,
                subject.size,
                subject.mtime_ns,
                identity_serial,
                identity_index,
                subject.nlink,
                subject.metadata.attributes,
                subject.metadata.created_ns,
                row_id,
            ),
        )

    def _record_correspondence(
        self,
        connection: sqlite3.Connection,
        operation: PlanOperation,
        source_id: int,
        target_id: int,
        source: FileStat,
        target: FileStat,
        at: str,
    ) -> None:
        if source.file_identity is None:
            return
        target_identity = _identity_values(target.file_identity)
        connection.execute(
            """DELETE FROM mapping_correspondence
                WHERE mapping_id = ?
                  AND (source_inventory_id = ? OR target_inventory_id = ?)""",
            (self._command.mapping_id, source_id, target_id),
        )
        connection.execute(
            """INSERT INTO mapping_correspondence(
                   mapping_id, source_inventory_id, target_inventory_id,
                   source_identity_volume_serial, source_identity_file_index,
                   target_identity_volume_serial, target_identity_file_index,
                   last_seen_at, run_token, op_token
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self._command.mapping_id,
                source_id,
                target_id,
                source.file_identity.volume_serial,
                file_index_128_to_text(source.file_identity.file_index),
                target_identity[0],
                target_identity[1],
                at,
                self._command.run_token,
                str(operation.op_id),
            ),
        )
