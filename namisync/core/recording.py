"""Typed commands for the main-ledger recording boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from .evidence import RecordingStatus
from .models import ScanResult, VolumeEvidence, VolumeId
from .pathing import normalize_relative_path
from .planning import (
    FilterSet,
    OpId,
    Plan,
    selection_digest as calculate_selection_digest,
)
from .session import SessionState


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError(f"{field_name} must be UTC")


@dataclass(frozen=True, slots=True)
class HostCommand:
    host_key: str
    display_name: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.host_key or not self.display_name:
            raise ValueError("host key and display name are required")
        _require_utc(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class VolumeCommand:
    volume_id: VolumeId
    evidence: VolumeEvidence
    observed_at: datetime

    def __post_init__(self) -> None:
        _require_utc(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class LocationCommand:
    volume_row_id: int
    volume_relative_path: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.volume_row_id < 1:
            raise ValueError("volume row id must be positive")
        _require_utc(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class MappingCommand:
    source_location_id: int
    target_location_id: int
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.source_location_id < 1 or self.target_location_id < 1:
            raise ValueError("mapping location ids must be positive")
        if self.source_location_id == self.target_location_id:
            raise ValueError("mapping locations must be distinct")
        _require_utc(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class SyncRunCommand:
    run_token: str
    host_id: int
    mapping_id: int
    source_location_id: int
    target_location_id: int
    plan: Plan
    selection: frozenset[OpId]
    selection_digest: bytes
    started_at: datetime

    def __post_init__(self) -> None:
        if not self.run_token:
            raise ValueError("run token is required")
        if min(
            self.host_id,
            self.mapping_id,
            self.source_location_id,
            self.target_location_id,
        ) < 1:
            raise ValueError("run database ids must be positive")
        if len(self.selection_digest) != 32:
            raise ValueError("selection digest must contain exactly 32 bytes")
        known = {operation.op_id for operation in self.plan.operations}
        if not self.selection <= known:
            raise ValueError("run selection contains an unknown operation")
        if calculate_selection_digest(self.selection) != self.selection_digest:
            raise ValueError("selection digest does not match the selected operations")
        _require_utc(self.started_at, "started_at")


@dataclass(frozen=True, slots=True)
class FinishRunCommand:
    run_token: str
    status: SessionState
    recording: RecordingStatus
    ended_at: datetime

    def __post_init__(self) -> None:
        if not self.run_token:
            raise ValueError("run token is required")
        if self.status not in {
            SessionState.COMPLETED,
            SessionState.FAILED,
            SessionState.CANCELED,
            SessionState.REFUSED,
        }:
            raise ValueError("run finish status must be terminal")
        _require_utc(self.ended_at, "ended_at")


@dataclass(frozen=True, slots=True)
class InventoryCommand:
    location_id: int
    host_id: int
    scan: ScanResult
    scope_token: str
    observed_at: datetime
    online: bool = True

    def __post_init__(self) -> None:
        if self.location_id < 1 or self.host_id < 1:
            raise ValueError("inventory database ids must be positive")
        if not self.scope_token:
            raise ValueError("inventory scope token is required")
        _require_utc(self.observed_at, "observed_at")


class InventoryVisibilityAction(StrEnum):
    ACKNOWLEDGE = "acknowledge"
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class InventoryVisibilityCommand:
    command_id: str
    location_id: int
    row_id: str
    action: InventoryVisibilityAction
    changed_at: datetime

    def __post_init__(self) -> None:
        if not self.command_id or not self.row_id:
            raise ValueError("inventory visibility identifiers are required")
        if self.location_id < 1:
            raise ValueError("inventory visibility location id must be positive")
        _require_utc(self.changed_at, "changed_at")


@dataclass(frozen=True, slots=True)
class MappingFilterEvaluation:
    location_id: int
    row_id: str
    rel_path_key: str
    excluded: bool

    def __post_init__(self) -> None:
        if self.location_id < 1 or not self.row_id or not self.rel_path_key:
            raise ValueError("mapping filter evaluation identity is required")
        if self.rel_path_key != normalize_relative_path(self.rel_path_key):
            raise ValueError("mapping filter evaluation path must be canonical")


@dataclass(frozen=True, slots=True)
class MappingFilterCommand:
    command_id: str
    mapping_id: int
    filter_snapshot: FilterSet
    evaluations: tuple[MappingFilterEvaluation, ...]
    complete_location_ids: tuple[int, ...]
    changed_at: datetime

    def __post_init__(self) -> None:
        if not self.command_id:
            raise ValueError("mapping filter command id is required")
        if self.mapping_id < 1:
            raise ValueError("mapping id must be positive")
        identities = [
            (item.location_id, item.row_id, item.rel_path_key)
            for item in self.evaluations
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("mapping filter evaluations must be unique")
        if any(value < 1 for value in self.complete_location_ids):
            raise ValueError("complete mapping-filter location ids must be positive")
        if len(self.complete_location_ids) != len(set(self.complete_location_ids)):
            raise ValueError("complete mapping-filter location ids must be unique")
        _require_utc(self.changed_at, "changed_at")
