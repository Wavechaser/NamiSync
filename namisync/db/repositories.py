"""Typed read-only snapshots over the main ledger."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Callable, Iterable

from namisync.core.evidence import Attestation, ContentEvidence, Provenance
from namisync.core.models import (
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import FilterSet, MappingPair, MappingSnapshot

from .connections import DEFAULT_BUSY_TIMEOUT_MS, connect_ledger_reader
from .schema import validate_ledger_reader_contract
from .timestamps import decode_utc, encode_utc


class InventoryPresence(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class InventorySnapshot:
    row_id: str
    location_id: int
    rel_path: str
    rel_path_key: str
    entry_kind: EntryKind | None
    presence: InventoryPresence
    observed: FileStat | None
    attestation: Attestation | None
    last_observed_at: datetime | None
    last_verified_at: datetime | None
    scope_token: str
    missing_since: datetime | None
    acknowledged_at: datetime | None
    reappeared_at: datetime | None
    unsupported_reason: str | None
    hardlink_group: str | None


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    run_token: str
    activity_kind: str
    host_id: int
    mapping_id: int | None
    started_at: datetime
    ended_at: datetime | None
    filesystem_status: str | None
    recording_status: str | None


@dataclass(frozen=True, slots=True)
class MappingLookup:
    mapping_id: int
    source_location_id: int
    target_location_id: int
    snapshot: MappingSnapshot


@dataclass(frozen=True, slots=True)
class LocationSnapshot:
    location_id: int
    volume_id: VolumeId
    volume_relative_path: str
    mount_hint: str | None


@dataclass(frozen=True, slots=True)
class MappingInventoryRow:
    inventory: InventorySnapshot
    excluded_at: datetime | None
    excluded_by_filter: bool
    projection_current: bool

    @property
    def excluded(self) -> bool:
        return self.excluded_by_filter


@dataclass(frozen=True, slots=True)
class MappingFilterSnapshot:
    mapping_id: int
    filter_snapshot: FilterSet
    updated_at: datetime | None
    source_location_id: int
    target_location_id: int
    source_rows: tuple[MappingInventoryRow, ...]
    target_rows: tuple[MappingInventoryRow, ...]

    @property
    def planner_source_rows(self) -> tuple[InventorySnapshot, ...]:
        return tuple(row.inventory for row in self.source_rows if not row.excluded)

    @property
    def planner_target_rows(self) -> tuple[InventorySnapshot, ...]:
        return tuple(row.inventory for row in self.target_rows if not row.excluded)


def _optional_time(value: str | None) -> datetime | None:
    return None if value is None else decode_utc(value)


def _identity(serial: str | None, index: int | None) -> FileIdentity | None:
    if serial is None or index is None:
        return None
    return FileIdentity(serial, int(index))


def _observed_stat(row: sqlite3.Row) -> FileStat | None:
    if row["presence"] == InventoryPresence.UNSUPPORTED.value:
        return None
    if row["observed_size"] is None or row["observed_mtime_ns"] is None:
        return None
    return FileStat(
        EntryKind(row["entry_kind"]),
        int(row["observed_size"]),
        int(row["observed_mtime_ns"]),
        _identity(
            row["file_identity_volume_serial"], row["file_identity_file_index"]
        ),
        int(row["observed_nlink"]),
        MetadataSnapshot(
            int(row["observed_attributes"]), row["observed_created_ns"]
        ),
    )


def _attestation(row: sqlite3.Row) -> Attestation | None:
    if row["content_algorithm"] is None:
        return None
    subject = FileStat(
        EntryKind(row["attested_kind"]),
        int(row["attested_size"]),
        int(row["attested_mtime_ns"]),
        _identity(
            row["attested_file_identity_volume_serial"],
            row["attested_file_identity_file_index"],
        ),
        int(row["attested_nlink"]),
        MetadataSnapshot(
            int(row["attested_attributes"]), row["attested_created_ns"]
        ),
    )
    content = ContentEvidence(
        str(row["content_algorithm"]),
        bytes(row["content_digest"]),
        int(row["content_size"]),
        Provenance(row["hash_provenance"]),
        decode_utc(row["content_observed_at"]),
    )
    return Attestation(content, subject)


def _inventory_snapshot(row: sqlite3.Row) -> InventorySnapshot:
    kind = None if row["entry_kind"] == "unsupported" else EntryKind(row["entry_kind"])
    return InventorySnapshot(
        row_id=str(row["id"]),
        location_id=int(row["location_id"]),
        rel_path=str(row["rel_path"]),
        rel_path_key=str(row["rel_path_key"]),
        entry_kind=kind,
        presence=InventoryPresence(row["presence"]),
        observed=_observed_stat(row),
        attestation=_attestation(row),
        last_observed_at=_optional_time(row["last_observed_at"]),
        last_verified_at=_optional_time(row["last_verified_at"]),
        scope_token=str(row["scope_token"]),
        missing_since=_optional_time(row["missing_since"]),
        acknowledged_at=_optional_time(row["acknowledged_at"]),
        reappeared_at=_optional_time(row["reappeared_at"]),
        unsupported_reason=row["unsupported_reason"],
        hardlink_group=row["hardlink_group"],
    )


class LedgerRepository:
    """Read-only ledger queries with bounded path selection batches."""

    def __init__(
        self,
        path: str | Path,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        trace_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.path = Path(path).resolve()
        self._connection = connect_ledger_reader(
            self.path, busy_timeout_ms=busy_timeout_ms
        )
        try:
            validate_ledger_reader_contract(self._connection)
        except BaseException:
            self._connection.close()
            raise
        if trace_callback is not None:
            self._connection.set_trace_callback(trace_callback)

    def get_inventory(
        self, location_id: int, path_keys: Iterable[str] | None = None
    ) -> tuple[InventorySnapshot, ...]:
        if path_keys is None:
            rows = self._connection.execute(
                "SELECT * FROM inventory WHERE location_id = ? ORDER BY rel_path_key, id",
                (location_id,),
            ).fetchall()
        else:
            keys = sorted({normalize_relative_path(path) for path in path_keys})
            rows = []
            for start in range(0, len(keys), 400):
                chunk = keys[start : start + 400]
                placeholders = ",".join("?" for _ in chunk)
                rows.extend(
                    self._connection.execute(
                        f"""SELECT * FROM inventory
                              WHERE location_id = ? AND rel_path_key IN ({placeholders})
                              ORDER BY rel_path_key, id""",
                        (location_id, *chunk),
                    ).fetchall()
                )
        return tuple(_inventory_snapshot(row) for row in rows)

    def get_location(self, location_id: int) -> LocationSnapshot:
        row = self._connection.execute(
            """SELECT location.id, location.volume_relative_path,
                      volume.serial, volume.fs_type, volume.device_id
                 FROM locations AS location
                 JOIN volumes AS volume ON volume.id = location.volume_id
                WHERE location.id = ?""",
            (location_id,),
        ).fetchone()
        if row is None:
            raise KeyError(location_id)
        return LocationSnapshot(
            location_id=int(row["id"]),
            volume_id=VolumeId(row["serial"], row["fs_type"]),
            volume_relative_path=row["volume_relative_path"],
            mount_hint=row["device_id"],
        )

    def find_location(
        self, volume_id: VolumeId, volume_relative_path: str
    ) -> LocationSnapshot | None:
        key = normalize_relative_path(volume_relative_path, allow_root=True)
        row = self._connection.execute(
            """SELECT location.id, location.volume_relative_path, volume.device_id
                 FROM locations AS location
                 JOIN volumes AS volume ON volume.id = location.volume_id
                WHERE volume.serial = ? AND volume.fs_type = ?
                  AND location.volume_relative_path_key = ?""",
            (volume_id.serial, volume_id.fs_type, key),
        ).fetchone()
        if row is None:
            return None
        return LocationSnapshot(
            location_id=int(row["id"]),
            volume_id=volume_id,
            volume_relative_path=row["volume_relative_path"],
            mount_hint=row["device_id"],
        )

    def get_stale_inventory(
        self, location_id: int, verified_before: datetime
    ) -> tuple[InventorySnapshot, ...]:
        rows = self._connection.execute(
            """SELECT * FROM inventory
                WHERE location_id = ?
                  AND presence = 'present'
                  AND entry_kind = 'file'
                  AND (
                      last_verified_at IS NULL
                      OR last_verified_at < ?
                  )
                ORDER BY rel_path_key, id""",
            (location_id, encode_utc(verified_before)),
        ).fetchall()
        return tuple(_inventory_snapshot(row) for row in rows)

    def get_unacknowledged_missing(
        self, location_id: int
    ) -> tuple[InventorySnapshot, ...]:
        rows = self._connection.execute(
            """SELECT * FROM inventory
                WHERE location_id = ? AND presence = 'missing'
                  AND acknowledged_at IS NULL
                ORDER BY rel_path_key, id""",
            (location_id,),
        ).fetchall()
        return tuple(_inventory_snapshot(row) for row in rows)

    def get_mapping_inventory(self, mapping_id: int) -> MappingFilterSnapshot:
        if self._connection.in_transaction:
            raise RuntimeError("mapping inventory snapshot requires an idle reader")
        self._connection.execute("BEGIN")
        try:
            mapping = self._connection.execute(
                """SELECT source_location_id, target_location_id
                     FROM mappings
                    WHERE id = ? AND deleted_at IS NULL""",
                (mapping_id,),
            ).fetchone()
            if mapping is None:
                raise KeyError(mapping_id)
            filter_row = self._connection.execute(
                """SELECT patterns_json, snapshot_hash, updated_at
                     FROM mapping_filters WHERE mapping_id = ?""",
                (mapping_id,),
            ).fetchone()
            raw_patterns = (
                [] if filter_row is None else json.loads(filter_row["patterns_json"])
            )
            if not isinstance(raw_patterns, list) or not all(
                isinstance(pattern, str) for pattern in raw_patterns
            ):
                raise ValueError("stored mapping filter patterns are invalid")
            patterns = tuple(raw_patterns)
            filter_snapshot = FilterSet(patterns)

            def rows_for(location_id: int) -> tuple[MappingInventoryRow, ...]:
                rows = self._connection.execute(
                    """SELECT inventory.*,
                              exclusion.excluded_at AS mapping_excluded_at,
                              exclusion.snapshot_hash AS projection_snapshot_hash
                         FROM inventory
                         LEFT JOIN mapping_exclusions AS exclusion
                           ON exclusion.inventory_id = inventory.id
                          AND exclusion.mapping_id = ?
                        WHERE inventory.location_id = ?
                        ORDER BY inventory.rel_path_key, inventory.id""",
                    (mapping_id, location_id),
                ).fetchall()
                result: list[MappingInventoryRow] = []
                current_hash = (
                    None if filter_row is None else bytes(filter_row["snapshot_hash"])
                )
                for row in rows:
                    excluded_by_filter = filter_snapshot.excludes(row["rel_path"])
                    excluded_at = _optional_time(row["mapping_excluded_at"])
                    projection_hash = row["projection_snapshot_hash"]
                    result.append(
                        MappingInventoryRow(
                            _inventory_snapshot(row),
                            excluded_at,
                            excluded_by_filter,
                            (excluded_at is not None) == excluded_by_filter
                            and (
                                excluded_at is None
                                or (
                                    current_hash is not None
                                    and projection_hash is not None
                                    and bytes(projection_hash) == current_hash
                                )
                            ),
                        )
                    )
                return tuple(result)

            source_location_id = int(mapping["source_location_id"])
            target_location_id = int(mapping["target_location_id"])
            snapshot = MappingFilterSnapshot(
                mapping_id=mapping_id,
                filter_snapshot=filter_snapshot,
                updated_at=(
                    None
                    if filter_row is None
                    else decode_utc(filter_row["updated_at"])
                ),
                source_location_id=source_location_id,
                target_location_id=target_location_id,
                source_rows=rows_for(source_location_id),
                target_rows=rows_for(target_location_id),
            )
            self._connection.execute("COMMIT")
            return snapshot
        except BaseException:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise

    def get_mapping_snapshot(self, mapping_id: int) -> MappingSnapshot:
        mapping = self._connection.execute(
            """SELECT mapping.source_location_id, mapping.target_location_id,
                      source_volume.serial AS source_serial,
                      source_volume.fs_type AS source_fs_type,
                      target_volume.serial AS target_serial,
                      target_volume.fs_type AS target_fs_type
                 FROM mappings AS mapping
                 JOIN locations AS source_location
                   ON source_location.id = mapping.source_location_id
                 JOIN volumes AS source_volume
                   ON source_volume.id = source_location.volume_id
                 JOIN locations AS target_location
                   ON target_location.id = mapping.target_location_id
                 JOIN volumes AS target_volume
                   ON target_volume.id = target_location.volume_id
                WHERE mapping.id = ? AND mapping.deleted_at IS NULL""",
            (mapping_id,),
        ).fetchone()
        if mapping is None:
            raise KeyError(f"unknown active mapping: {mapping_id}")
        pair_rows = self._connection.execute(
            """SELECT source.rel_path_key AS source_rel_path_key,
                      target.rel_path AS target_rel_path,
                      target.rel_path_key AS target_rel_path_key,
                      pair.source_identity_volume_serial,
                      pair.source_identity_file_index,
                      pair.target_identity_volume_serial,
                      pair.target_identity_file_index
                 FROM mapping_correspondence AS pair
                 JOIN inventory AS source ON source.id = pair.source_inventory_id
                 JOIN inventory AS target ON target.id = pair.target_inventory_id
                WHERE pair.mapping_id = ?
                ORDER BY source.rel_path_key, target.rel_path_key""",
            (mapping_id,),
        ).fetchall()
        pairs = tuple(
            MappingPair(
                source_rel_path_key=normalize_relative_path(row["source_rel_path_key"]),
                target_rel_path=row["target_rel_path"],
                target_rel_path_key=normalize_relative_path(row["target_rel_path_key"]),
                source_identity=FileIdentity(
                    row["source_identity_volume_serial"],
                    int(row["source_identity_file_index"]),
                ),
                target_identity=_identity(
                    row["target_identity_volume_serial"],
                    row["target_identity_file_index"],
                ),
            )
            for row in pair_rows
        )
        return MappingSnapshot(
            source_volume_id=VolumeId(
                mapping["source_serial"], mapping["source_fs_type"]
            ),
            target_volume_id=VolumeId(
                mapping["target_serial"], mapping["target_fs_type"]
            ),
            pairs=pairs,
            ambiguous_source_keys=frozenset(),
            disqualified_source_identities=self._disqualified_identities(
                int(mapping["source_location_id"])
            ),
            disqualified_target_identities=self._disqualified_identities(
                int(mapping["target_location_id"])
            ),
        )

    def find_mapping(
        self,
        source_volume: VolumeId,
        source_relative_root: str,
        target_volume: VolumeId,
        target_relative_root: str,
    ) -> MappingLookup | None:
        """Return the active mapping matching two physical volume roots."""

        source_key = normalize_relative_path(source_relative_root, allow_root=True)
        target_key = normalize_relative_path(target_relative_root, allow_root=True)
        row = self._connection.execute(
            """SELECT mapping.id, mapping.source_location_id,
                      mapping.target_location_id
                 FROM mappings AS mapping
                 JOIN locations AS source_location
                   ON source_location.id = mapping.source_location_id
                 JOIN volumes AS source_volume ON source_volume.id = source_location.volume_id
                 JOIN locations AS target_location
                   ON target_location.id = mapping.target_location_id
                 JOIN volumes AS target_volume ON target_volume.id = target_location.volume_id
                WHERE mapping.deleted_at IS NULL
                  AND source_volume.serial = ? AND source_volume.fs_type = ?
                  AND source_location.volume_relative_path_key = ?
                  AND target_volume.serial = ? AND target_volume.fs_type = ?
                  AND target_location.volume_relative_path_key = ?
                ORDER BY mapping.id
                LIMIT 1""",
            (
                source_volume.serial,
                source_volume.fs_type,
                source_key,
                target_volume.serial,
                target_volume.fs_type,
                target_key,
            ),
        ).fetchone()
        if row is None:
            return None
        mapping_id = int(row["id"])
        return MappingLookup(
            mapping_id=mapping_id,
            source_location_id=int(row["source_location_id"]),
            target_location_id=int(row["target_location_id"]),
            snapshot=self.get_mapping_snapshot(mapping_id),
        )

    def _disqualified_identities(self, location_id: int) -> frozenset[FileIdentity]:
        rows = self._connection.execute(
            """SELECT file_identity_volume_serial, file_identity_file_index
                 FROM inventory
                WHERE location_id = ? AND file_identity_volume_serial IS NOT NULL
                GROUP BY file_identity_volume_serial, file_identity_file_index
               HAVING count(*) > 1 OR max(observed_nlink) > 1""",
            (location_id,),
        ).fetchall()
        return frozenset(
            FileIdentity(row[0], int(row[1])) for row in rows
        )

    def mapping_ids_for_location(self, location_id: int) -> tuple[int, ...]:
        return tuple(
            int(row[0])
            for row in self._connection.execute(
                """SELECT id FROM mappings
                    WHERE deleted_at IS NULL
                      AND (source_location_id = ? OR target_location_id = ?)
                    ORDER BY id""",
                (location_id, location_id),
            )
        )

    def get_run(self, run_token: str) -> RunSnapshot:
        row = self._connection.execute(
            "SELECT * FROM runs WHERE run_token = ?", (run_token,)
        ).fetchone()
        if row is None:
            raise KeyError(run_token)
        return RunSnapshot(
            run_token=row["run_token"],
            activity_kind=row["activity_kind"],
            host_id=int(row["host_id"]),
            mapping_id=None if row["mapping_id"] is None else int(row["mapping_id"]),
            started_at=decode_utc(row["started_at"]),
            ended_at=_optional_time(row["ended_at"]),
            filesystem_status=row["filesystem_status"],
            recording_status=row["recording_status"],
        )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> LedgerRepository:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
