"""Typed read-only snapshots over the main ledger."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Callable, Iterable

from namisync.core.evidence import Attestation, ContentEvidence, Provenance
from namisync.core.integrity import (
    INTEGRITY_CANDIDATE_ROW_LIMIT,
    IntegrityCandidateLimitError,
    IntegrityCandidateLimitExceeded,
    IntegrityMode,
    InventoryVerificationState,
    VerificationInvalidation,
    VerificationInvalidationReason,
)
from namisync.core.models import (
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import MappingPair, MappingSnapshot
from namisync.core.review import (
    MAX_PLAN_REVIEW_ROWS,
    exceeds_population_wall,
)
from namisync.core.scalars import file_index_128_from_text, file_index_128_to_text

from .connections import (
    DEFAULT_BUSY_TIMEOUT_MS,
    QUERY_SUBJECT_BATCH_SIZE,
    connect_ledger_reader,
)
from .contracts import require_database_file_contract
from .schema import validate_ledger_reader_contract
from .timestamps import decode_utc, encode_utc


class InventoryPresence(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"


INVENTORY_POPULATION_ROW_LIMIT = MAX_PLAN_REVIEW_ROWS


class InventoryPopulationLimitError(ValueError):
    """Raised before a general inventory read retains its first excess row."""

    def __init__(self) -> None:
        super().__init__("inventory population exceeds the review row limit")


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
    invalidation: VerificationInvalidation | None = None

    @property
    def verification_state(self) -> InventoryVerificationState:
        if (
            self.presence is not InventoryPresence.PRESENT
            or self.observed is None
            or self.attestation is None
        ):
            return InventoryVerificationState.UNVERIFIED
        if (
            self.invalidation is not None
            and self.invalidation.reason
            is VerificationInvalidationReason.HASH_MISMATCH
        ):
            return InventoryVerificationState.MISMATCHED
        baseline = self.attestation.subject
        observed = self.observed
        if (
            baseline.kind is not observed.kind
            or baseline.size != observed.size
            or baseline.mtime_ns != observed.mtime_ns
            or (
                baseline.file_identity is not None
                and baseline.file_identity != observed.file_identity
            )
        ):
            return InventoryVerificationState.MODIFIED
        if self.invalidation is not None:
            return InventoryVerificationState.MODIFIED
        if self.last_verified_at is None:
            return InventoryVerificationState.UNVERIFIED
        return InventoryVerificationState.VERIFIED


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


def _optional_time(value: str | None) -> datetime | None:
    return None if value is None else decode_utc(value)


def _identity(serial: str | None, index: str | None) -> FileIdentity | None:
    if (serial is None) != (index is None):
        raise ValueError("stored file identity columns disagree")
    if serial is None:
        return None
    assert index is not None
    return FileIdentity(serial, file_index_128_from_text(index))


def _identity_query_values(
    identities: Iterable[FileIdentity],
) -> tuple[tuple[str, str], ...]:
    values: set[FileIdentity] = set()
    for occurrence, identity in enumerate(identities):
        if exceeds_population_wall(
            occurrence + 1,
            limit=INVENTORY_POPULATION_ROW_LIMIT,
            field_name="inventory identity occurrences",
        ):
            raise InventoryPopulationLimitError()
        values.add(identity)
    ordered = list(values)
    del values
    ordered.sort()
    return tuple(
        (identity.volume_serial, file_index_128_to_text(identity.file_index))
        for identity in ordered
    )


def _bounded_normalized_path_keys(
    paths: Iterable[str],
    *,
    limit: int,
    limit_error: Callable[[], ValueError],
) -> tuple[str, ...]:
    keys: set[str] = set()
    for occurrence, path in enumerate(paths):
        if exceeds_population_wall(
            occurrence + 1,
            limit=limit,
            field_name="inventory path occurrences",
        ):
            raise limit_error()
        keys.add(normalize_relative_path(path))
    ordered = list(keys)
    del keys
    ordered.sort()
    return tuple(ordered)


def _mapping_pair(row: sqlite3.Row) -> MappingPair:
    return MappingPair(
        source_rel_path_key=normalize_relative_path(row["source_rel_path_key"]),
        target_rel_path=row["target_rel_path"],
        target_rel_path_key=normalize_relative_path(row["target_rel_path_key"]),
        source_identity=FileIdentity(
            row["source_identity_volume_serial"],
            file_index_128_from_text(row["source_identity_file_index"]),
        ),
        target_identity=_identity(
            row["target_identity_volume_serial"],
            row["target_identity_file_index"],
        ),
    )


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
        invalidation=(
            None
            if row["verification_invalidated_at"] is None
            else VerificationInvalidation(
                decode_utc(row["verification_invalidated_at"]),
                VerificationInvalidationReason(
                    row["verification_invalidated_reason"]
                ),
            )
        ),
    )


def _integrity_row_limit_error() -> IntegrityCandidateLimitError:
    return IntegrityCandidateLimitError(IntegrityCandidateLimitExceeded.rows())


def _append_inventory_snapshots(
    snapshots: list[InventorySnapshot],
    rows: Iterable[sqlite3.Row],
) -> None:
    for row in rows:
        if exceeds_population_wall(
            len(snapshots) + 1,
            limit=INVENTORY_POPULATION_ROW_LIMIT,
            field_name="inventory returned rows",
        ):
            raise InventoryPopulationLimitError()
        snapshots.append(_inventory_snapshot(row))


def _bounded_integrity_path_keys(paths: Iterable[str]) -> tuple[str, ...]:
    return _bounded_normalized_path_keys(
        paths,
        limit=INTEGRITY_CANDIDATE_ROW_LIMIT,
        limit_error=_integrity_row_limit_error,
    )


def _bounded_integrity_row_ids(row_ids: Iterable[str]) -> tuple[str, ...]:
    requested: dict[str, None] = {}
    for occurrence, row_id in enumerate(row_ids):
        if exceeds_population_wall(
            occurrence + 1,
            limit=INTEGRITY_CANDIDATE_ROW_LIMIT,
            field_name="integrity row-id occurrences",
        ):
            raise _integrity_row_limit_error()
        if not isinstance(row_id, str) or not row_id:
            raise ValueError("integrity inventory row id is invalid")
        if row_id in requested:
            raise ValueError("integrity inventory row ids must be unique")
        requested[row_id] = None
    return tuple(requested)


def _integrity_eligibility_sql(mode: IntegrityMode) -> str:
    if mode is IntegrityMode.BASELINE:
        return "content_algorithm IS NULL"
    if mode is IntegrityMode.REBASELINE:
        return "content_algorithm IS NOT NULL"
    return "1"


def _append_integrity_candidates(
    candidates: list[InventorySnapshot],
    rows: Iterable[sqlite3.Row],
) -> None:
    for row in rows:
        if exceeds_population_wall(
            len(candidates) + 1,
            limit=INTEGRITY_CANDIDATE_ROW_LIMIT,
            field_name="integrity returned rows",
        ):
            raise _integrity_row_limit_error()
        candidates.append(_inventory_snapshot(row))


def _append_integrity_candidate_by_id(
    candidates: dict[str, tuple[tuple[str, int], InventorySnapshot]],
    row: sqlite3.Row,
) -> None:
    row_id = str(row["id"])
    if row_id in candidates:
        return
    if exceeds_population_wall(
        len(candidates) + 1,
        limit=INTEGRITY_CANDIDATE_ROW_LIMIT,
        field_name="integrity unique returned rows",
    ):
        raise _integrity_row_limit_error()
    candidates[row_id] = (
        (str(row["rel_path_key"]), int(row["id"])),
        _inventory_snapshot(row),
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
        require_database_file_contract(self.path, history=False)
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
        snapshots: list[InventorySnapshot] = []
        if path_keys is None:
            cursor = self._connection.execute(
                """SELECT * FROM inventory
                     WHERE location_id = ?
                     ORDER BY rel_path_key, id
                     LIMIT ?""",
                (location_id, INVENTORY_POPULATION_ROW_LIMIT + 1),
            )
            _append_inventory_snapshots(snapshots, cursor)
        else:
            keys = _bounded_normalized_path_keys(
                path_keys,
                limit=INVENTORY_POPULATION_ROW_LIMIT,
                limit_error=InventoryPopulationLimitError,
            )
            if keys:
                self._connection.execute("BEGIN")
                try:
                    for start in range(0, len(keys), QUERY_SUBJECT_BATCH_SIZE):
                        chunk = keys[start : start + QUERY_SUBJECT_BATCH_SIZE]
                        placeholders = ",".join("?" for _ in chunk)
                        cursor = self._connection.execute(
                            f"""SELECT * FROM inventory
                                  WHERE location_id = ?
                                    AND rel_path_key IN ({placeholders})
                                  ORDER BY rel_path_key, id
                                  LIMIT ?""",
                            (
                                location_id,
                                *chunk,
                                INVENTORY_POPULATION_ROW_LIMIT + 1,
                            ),
                        )
                        _append_inventory_snapshots(snapshots, cursor)
                finally:
                    self._connection.rollback()
            del keys
        return tuple(snapshots)

    def get_inventory_by_row_ids(
        self, location_id: int, row_ids: Iterable[str]
    ) -> tuple[InventorySnapshot, ...]:
        """Return location-owned rows in first-requested canonical ID order."""

        requested_keys: dict[str, None] = {}
        for occurrence, row_id in enumerate(row_ids):
            if exceeds_population_wall(
                occurrence + 1,
                limit=INVENTORY_POPULATION_ROW_LIMIT,
                field_name="inventory row-id occurrences",
            ):
                raise InventoryPopulationLimitError()
            if (
                not isinstance(row_id, str)
                or not row_id.isascii()
                or not row_id.isdecimal()
                or row_id.startswith("0")
                or row_id in requested_keys
            ):
                continue
            requested_keys[row_id] = None
        requested = tuple(requested_keys)
        del requested_keys

        rows_by_id: dict[str, InventorySnapshot] = {}
        if requested:
            self._connection.execute("BEGIN")
            try:
                for start in range(0, len(requested), QUERY_SUBJECT_BATCH_SIZE):
                    chunk = requested[start : start + QUERY_SUBJECT_BATCH_SIZE]
                    placeholders = ",".join("?" for _ in chunk)
                    for row in self._connection.execute(
                        f"""SELECT * FROM inventory
                              WHERE location_id = ?
                                AND id IN ({placeholders})""",
                        (location_id, *chunk),
                    ):
                        if exceeds_population_wall(
                            len(rows_by_id) + 1,
                            limit=INVENTORY_POPULATION_ROW_LIMIT,
                            field_name="inventory returned rows",
                        ):
                            raise InventoryPopulationLimitError()
                        snapshot = _inventory_snapshot(row)
                        rows_by_id[snapshot.row_id] = snapshot
            finally:
                self._connection.rollback()
        return tuple(
            rows_by_id[row_id] for row_id in requested if row_id in rows_by_id
        )

    def get_integrity_candidates(
        self,
        location_id: int,
        mode: IntegrityMode,
        *,
        path_keys: Iterable[str] = (),
        stale_before: datetime | None = None,
        saved_row_ids: Iterable[str] = (),
        completed_row_ids: Iterable[str] = (),
    ) -> tuple[InventorySnapshot, ...]:
        """Read one complete, bounded integrity population from one snapshot."""

        if not isinstance(mode, IntegrityMode):
            raise TypeError("integrity candidate mode has the wrong type")
        paths = _bounded_integrity_path_keys(path_keys)
        saved = _bounded_integrity_row_ids(saved_row_ids)
        completed = _bounded_integrity_row_ids(completed_row_ids)
        if saved and (paths or stale_before is not None or completed):
            raise ValueError("saved integrity selection cannot combine query scopes")
        if paths and stale_before is not None:
            raise ValueError("integrity path and stale scopes are mutually exclusive")
        if completed and stale_before is None:
            raise ValueError("completed integrity rows require a stale scope")

        self._connection.execute("BEGIN")
        try:
            if saved:
                return self._saved_integrity_candidates(location_id, saved)
            if stale_before is not None:
                return self._stale_integrity_candidates(
                    location_id,
                    mode,
                    stale_before,
                    completed,
                )
            return self._fresh_integrity_candidates(location_id, mode, paths)
        finally:
            self._connection.rollback()

    def _fresh_integrity_candidates(
        self,
        location_id: int,
        mode: IntegrityMode,
        path_keys: tuple[str, ...],
    ) -> tuple[InventorySnapshot, ...]:
        predicate = _integrity_eligibility_sql(mode)
        candidates: list[InventorySnapshot] = []
        if not path_keys:
            cursor = self._connection.execute(
                f"""SELECT * FROM inventory
                      WHERE location_id = ?
                        AND entry_kind <> 'directory'
                        AND {predicate}
                      ORDER BY rel_path_key, id
                      LIMIT ?""",
                (location_id, INTEGRITY_CANDIDATE_ROW_LIMIT + 1),
            )
            _append_integrity_candidates(candidates, cursor)
            return tuple(candidates)

        for start in range(0, len(path_keys), QUERY_SUBJECT_BATCH_SIZE):
            chunk = path_keys[start : start + QUERY_SUBJECT_BATCH_SIZE]
            placeholders = ",".join("?" for _ in chunk)
            cursor = self._connection.execute(
                f"""SELECT * FROM inventory
                      WHERE location_id = ?
                        AND rel_path_key IN ({placeholders})
                        AND entry_kind <> 'directory'
                        AND {predicate}
                      ORDER BY rel_path_key, id
                      LIMIT ?""",
                (
                    location_id,
                    *chunk,
                    INTEGRITY_CANDIDATE_ROW_LIMIT + 1,
                ),
            )
            _append_integrity_candidates(candidates, cursor)
        return tuple(candidates)

    def _saved_integrity_candidates(
        self,
        location_id: int,
        row_ids: tuple[str, ...],
    ) -> tuple[InventorySnapshot, ...]:
        rows_by_id: dict[str, InventorySnapshot] = {}
        for start in range(0, len(row_ids), QUERY_SUBJECT_BATCH_SIZE):
            chunk = row_ids[start : start + QUERY_SUBJECT_BATCH_SIZE]
            placeholders = ",".join("?" for _ in chunk)
            cursor = self._connection.execute(
                f"""SELECT * FROM inventory
                      WHERE location_id = ? AND id IN ({placeholders})
                      LIMIT ?""",
                (
                    location_id,
                    *chunk,
                    INTEGRITY_CANDIDATE_ROW_LIMIT + 1,
                ),
            )
            for row in cursor:
                rows_by_id[str(row["id"])] = _inventory_snapshot(row)
        if any(row_id not in rows_by_id for row_id in row_ids):
            raise RuntimeError(
                "saved integrity selection references missing inventory rows"
            )
        return tuple(rows_by_id[row_id] for row_id in row_ids)

    def _stale_integrity_candidates(
        self,
        location_id: int,
        mode: IntegrityMode,
        stale_before: datetime,
        completed_row_ids: tuple[str, ...],
    ) -> tuple[InventorySnapshot, ...]:
        candidates: dict[
            str,
            tuple[tuple[str, int], InventorySnapshot],
        ] = {}
        found_completed: set[str] = set()
        for start in range(0, len(completed_row_ids), QUERY_SUBJECT_BATCH_SIZE):
            chunk = completed_row_ids[start : start + QUERY_SUBJECT_BATCH_SIZE]
            placeholders = ",".join("?" for _ in chunk)
            cursor = self._connection.execute(
                f"""SELECT * FROM inventory
                      WHERE location_id = ? AND id IN ({placeholders})
                      LIMIT ?""",
                (
                    location_id,
                    *chunk,
                    INTEGRITY_CANDIDATE_ROW_LIMIT + 1,
                ),
            )
            for row in cursor:
                row_id = str(row["id"])
                found_completed.add(row_id)
                _append_integrity_candidate_by_id(candidates, row)
        if any(row_id not in found_completed for row_id in completed_row_ids):
            raise RuntimeError(
                "saved integrity progress references missing inventory rows"
            )
        del found_completed

        predicate = _integrity_eligibility_sql(mode)
        cursor = self._connection.execute(
            f"""SELECT * FROM inventory
                  WHERE location_id = ?
                    AND presence = 'present'
                    AND entry_kind = 'file'
                    AND {predicate}
                    AND (
                        content_algorithm IS NULL
                        OR last_verified_at IS NULL
                        OR last_verified_at < ?
                        OR verification_invalidated_at IS NOT NULL
                        OR attested_kind IS NOT entry_kind
                        OR attested_size IS NOT observed_size
                        OR attested_mtime_ns IS NOT observed_mtime_ns
                        OR (
                            attested_file_identity_volume_serial IS NOT NULL
                            AND (
                                attested_file_identity_volume_serial
                                    IS NOT file_identity_volume_serial
                                OR attested_file_identity_file_index
                                    IS NOT file_identity_file_index
                            )
                        )
                    )
                  ORDER BY rel_path_key, id
                  LIMIT ?""",
            (
                location_id,
                encode_utc(stale_before),
                INTEGRITY_CANDIDATE_ROW_LIMIT + 1,
            ),
        )
        for row in cursor:
            _append_integrity_candidate_by_id(candidates, row)
        return tuple(
            snapshot
            for _, snapshot in sorted(candidates.values(), key=lambda item: item[0])
        )

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
        cursor = self._connection.execute(
            """SELECT * FROM inventory
                WHERE location_id = ?
                  AND presence = 'present'
                  AND entry_kind = 'file'
                  AND (
                      content_algorithm IS NULL
                      OR last_verified_at IS NULL
                      OR last_verified_at < ?
                      OR verification_invalidated_at IS NOT NULL
                      OR attested_kind IS NOT entry_kind
                      OR attested_size IS NOT observed_size
                      OR attested_mtime_ns IS NOT observed_mtime_ns
                      OR (
                          attested_file_identity_volume_serial IS NOT NULL
                          AND (
                              attested_file_identity_volume_serial
                                  IS NOT file_identity_volume_serial
                              OR attested_file_identity_file_index
                                  IS NOT file_identity_file_index
                          )
                      )
                  )
                ORDER BY rel_path_key, id
                LIMIT ?""",
            (
                location_id,
                encode_utc(verified_before),
                INVENTORY_POPULATION_ROW_LIMIT + 1,
            ),
        )
        snapshots: list[InventorySnapshot] = []
        _append_inventory_snapshots(snapshots, cursor)
        return tuple(snapshots)

    def get_unacknowledged_missing(
        self, location_id: int
    ) -> tuple[InventorySnapshot, ...]:
        cursor = self._connection.execute(
            """SELECT * FROM inventory
                WHERE location_id = ? AND presence = 'missing'
                  AND acknowledged_at IS NULL
                ORDER BY rel_path_key, id
                LIMIT ?""",
            (location_id, INVENTORY_POPULATION_ROW_LIMIT + 1),
        )
        snapshots: list[InventorySnapshot] = []
        _append_inventory_snapshots(snapshots, cursor)
        return tuple(snapshots)

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
        pairs = tuple(_mapping_pair(row) for row in pair_rows)
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

    def find_current_mapping(
        self,
        source_volume: VolumeId,
        source_relative_root: str,
        target_volume: VolumeId,
        target_relative_root: str,
        *,
        target_path_keys: Iterable[str],
        source_identities: Iterable[FileIdentity],
        target_identities: Iterable[FileIdentity],
    ) -> MappingLookup | None:
        """Return correspondence relevant to one pair of current file scans."""

        source_key = normalize_relative_path(source_relative_root, allow_root=True)
        target_key = normalize_relative_path(target_relative_root, allow_root=True)
        current_target_keys = _bounded_normalized_path_keys(
            target_path_keys,
            limit=INVENTORY_POPULATION_ROW_LIMIT,
            limit_error=InventoryPopulationLimitError,
        )
        current_source_identities = _identity_query_values(source_identities)
        current_target_identities = _identity_query_values(target_identities)
        source_identity_values = frozenset(current_source_identities)
        target_identity_values = frozenset(current_target_identities)

        self._connection.execute("BEGIN")
        try:
            row = self._connection.execute(
                """SELECT mapping.id, mapping.source_location_id,
                          mapping.target_location_id
                     FROM mappings AS mapping
                     JOIN locations AS source_location
                       ON source_location.id = mapping.source_location_id
                     JOIN volumes AS source_volume
                       ON source_volume.id = source_location.volume_id
                     JOIN locations AS target_location
                       ON target_location.id = mapping.target_location_id
                     JOIN volumes AS target_volume
                       ON target_volume.id = target_location.volume_id
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
            source_location_id = int(row["source_location_id"])
            target_location_id = int(row["target_location_id"])
            pairs: list[MappingPair] = []
            if current_target_keys and source_identity_values:
                for start in range(0, len(current_target_keys), QUERY_SUBJECT_BATCH_SIZE):
                    chunk = current_target_keys[start : start + QUERY_SUBJECT_BATCH_SIZE]
                    placeholders = ",".join("?" for _ in chunk)
                    cursor = self._connection.execute(
                        f"""SELECT source.rel_path_key AS source_rel_path_key,
                                   target.rel_path AS target_rel_path,
                                   target.rel_path_key AS target_rel_path_key,
                                   pair.source_identity_volume_serial,
                                   pair.source_identity_file_index,
                                   pair.target_identity_volume_serial,
                                   pair.target_identity_file_index
                              FROM mapping_correspondence AS pair
                              JOIN inventory AS source
                                ON source.id = pair.source_inventory_id
                             JOIN inventory AS target
                                ON target.id = pair.target_inventory_id
                             WHERE pair.mapping_id = ?
                               AND pair.target_inventory_id IN (
                                   SELECT current_target.id
                                     FROM inventory AS current_target
                                    WHERE current_target.location_id = ?
                                      AND current_target.rel_path_key
                                          IN ({placeholders})
                               )
                             ORDER BY source.rel_path_key, target.rel_path_key""",
                        (mapping_id, target_location_id, *chunk),
                    )
                    for pair_row in cursor:
                        pair = _mapping_pair(pair_row)
                        stored_source_identity = (
                            pair.source_identity.volume_serial,
                            file_index_128_to_text(pair.source_identity.file_index),
                        )
                        if stored_source_identity not in source_identity_values:
                            continue
                        stored_target_identity = (
                            None
                            if pair.target_identity is None
                            else (
                                pair.target_identity.volume_serial,
                                file_index_128_to_text(
                                    pair.target_identity.file_index
                                ),
                            )
                        )
                        if stored_target_identity is not None and (
                            stored_target_identity not in target_identity_values
                        ):
                            continue
                        pairs.append(pair)
            pairs.sort(
                key=lambda pair: (
                    pair.source_rel_path_key,
                    pair.target_rel_path_key,
                )
            )
            return MappingLookup(
                mapping_id=mapping_id,
                source_location_id=source_location_id,
                target_location_id=target_location_id,
                snapshot=MappingSnapshot(
                    source_volume_id=source_volume,
                    target_volume_id=target_volume,
                    pairs=tuple(pairs),
                    ambiguous_source_keys=frozenset(),
                    disqualified_source_identities=(
                        self._current_disqualified_identities(
                            source_location_id,
                            current_source_identities,
                        )
                    ),
                    disqualified_target_identities=(
                        self._current_disqualified_identities(
                            target_location_id,
                            current_target_identities,
                        )
                    ),
                ),
            )
        finally:
            self._connection.rollback()

    def _current_disqualified_identities(
        self,
        location_id: int,
        identities: tuple[tuple[str, str], ...],
    ) -> frozenset[FileIdentity]:
        disqualified: set[FileIdentity] = set()
        for start in range(0, len(identities), QUERY_SUBJECT_BATCH_SIZE):
            chunk = identities[start : start + QUERY_SUBJECT_BATCH_SIZE]
            values = ",".join("(?, ?)" for _ in chunk)
            parameters = tuple(value for identity in chunk for value in identity)
            cursor = self._connection.execute(
                f"""WITH requested(volume_serial, file_index) AS (VALUES {values})
                     SELECT inventory.file_identity_volume_serial,
                            inventory.file_identity_file_index
                       FROM inventory
                       JOIN requested
                         ON requested.volume_serial =
                                inventory.file_identity_volume_serial
                        AND requested.file_index =
                                inventory.file_identity_file_index
                      WHERE inventory.location_id = ?
                      GROUP BY inventory.file_identity_volume_serial,
                               inventory.file_identity_file_index
                     HAVING count(*) > 1 OR max(inventory.observed_nlink) > 1""",
                (*parameters, location_id),
            )
            for identity_row in cursor:
                identity = _identity(identity_row[0], identity_row[1])
                assert identity is not None
                disqualified.add(identity)
        return frozenset(disqualified)

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
            FileIdentity(row[0], file_index_128_from_text(row[1]))
            for row in rows
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
