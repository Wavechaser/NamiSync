"""Immutable observations and typed pure-preflight verdict contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Mapping, NamedTuple

from .models import FileStat, VolumeEvidence, VolumeId
from .planning import FilterSet, OpId


class Subject(NamedTuple):
    root_id: str
    rel_path_key: str


@dataclass(frozen=True)
class StatObservation:
    stat: FileStat | None
    error: str | None = None
    contained: bool = True
    representable: bool = True


@dataclass(frozen=True)
class RootObservation:
    resolved_path: str | None
    volume_id: VolumeId | None
    volume_evidence: VolumeEvidence | None
    error: str | None = None


@dataclass(frozen=True)
class TrashObservation:
    resolved_path: str | None
    available: bool
    contained: bool
    same_volume: bool
    writable: bool
    reparse_safe: bool
    error: str | None = None


@dataclass(frozen=True)
class ObservedWorld:
    stats: Mapping[Subject, StatObservation]
    paths: Mapping[Subject, str]
    roots: Mapping[str, RootObservation]
    free_space: int | None
    reclaimable_temp_bytes: int
    trash: TrashObservation | None
    current_filters: FilterSet
    current_policy_fingerprint: str
    observed_at: datetime
    settings_error: str | None = None

    def __post_init__(self) -> None:
        if self.free_space is not None and self.free_space < 0:
            raise ValueError("free space cannot be negative")
        if self.reclaimable_temp_bytes < 0:
            raise ValueError("reclaimable temp bytes cannot be negative")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observation timestamp must be timezone-aware")
        if self.observed_at.utcoffset() != timezone.utc.utcoffset(self.observed_at):
            raise ValueError("observation timestamp must be UTC")


class RefusalCode(StrEnum):
    INCOMPLETE_SOURCE_SCAN = "incomplete_source_scan"
    INCOMPLETE_TARGET_SCAN = "incomplete_target_scan"
    ROOT_UNAVAILABLE = "root_unavailable"
    ROOT_CHANGED = "root_changed"
    ROOTS_OVERLAP = "roots_overlap"
    VOLUME_CLONE_AMBIGUOUS = "volume_clone_ambiguous"
    SELECTION_NOT_CLOSED = "selection_not_closed"
    OPERATION_BLOCKED = "operation_blocked"
    BLOCKED_CORRESPONDENCE = "blocked_correspondence"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    OBSERVATION_UNAVAILABLE = "observation_unavailable"
    SOURCE_DRIFT = "source_drift"
    TARGET_DRIFT = "target_drift"
    DESTINATION_APPEARED = "destination_appeared"
    TYPE_CHANGED = "type_changed"
    IDENTITY_CHANGED = "identity_changed"
    SIZE_CHANGED = "size_changed"
    MTIME_CHANGED = "mtime_changed"
    METADATA_CHANGED = "metadata_changed"
    FILTER_DRIFT = "filter_drift"
    OPTIONS_DRIFT = "options_drift"
    INSUFFICIENT_SPACE = "insufficient_space"
    TRASH_UNAVAILABLE = "trash_unavailable"
    TRASH_ESCAPE = "trash_escape"
    TRASH_OFF_VOLUME = "trash_off_volume"
    TRASH_NOT_WRITABLE = "trash_not_writable"
    TRASH_REPARSE = "trash_reparse"
    PATH_ESCAPE = "path_escape"
    PATH_UNREPRESENTABLE = "path_unrepresentable"


@dataclass(frozen=True)
class Refusal:
    code: RefusalCode
    op_id: OpId | None = None
    subject: Subject | None = None
    detail: str = ""


@dataclass(frozen=True)
class Verdict:
    ok: bool
    refusals: tuple[Refusal, ...]
    observed: ObservedWorld

    def __post_init__(self) -> None:
        if self.ok == bool(self.refusals):
            raise ValueError("verdict ok flag must agree with refusals")
