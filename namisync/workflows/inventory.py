"""Location inventory and standalone integrity workflow coordination."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Callable, Iterator, Mapping, Protocol

from namisync.core.exception_graph import retire_exception_graph
from namisync.core.events import PhaseChanged
from namisync.core.evidence import RecordingStatus, snapshot_attestation
from namisync.core.execution import (
    TaskRecordingIssue,
    TaskRecordingIssueReason,
    bounded_recording_detail,
)
from namisync.core.integrity import (
    INTEGRITY_CANDIDATE_ROW_LIMIT,
    IntegrityCandidateLimitError,
    IntegrityCandidateLimitExceeded,
    IntegrityMode,
    IntegrityOutcome,
    IntegrityRunResult,
    IntegritySelection,
    IntegritySelectionItemFact,
    IntegritySelectionItem,
    InventoryState,
    RecordDisposition,
    VerificationInvalidation,
    VerifierContext,
    bind_verifier_context,
    revalidate_integrity_selection_authority,
    snapshot_integrity_selection_authority,
    snapshot_integrity_outcome,
    validate_integrity_run_result,
)
from namisync.core.models import (
    MAX_VOLUME_TEXT_UTF16_UNITS,
    CapabilityProfile,
    IgnoreSet,
    Root,
    ScanResult,
    ScanScope,
    ScanScopeKind,
    ScanWarning,
    ScanWarningCode,
    SCAN_SCOPE_ENTRY_LIMIT,
    VolumeEvidence,
    VolumeId,
    snapshot_file_stat,
    snapshot_ignore_set,
)
from namisync.core.pathing import (
    PathValidationError,
    lexical_path_chain,
    logical_error_text,
    normalize_relative_path,
    validate_relative_path,
)
from namisync.core.recording import (
    HostCommand,
    InventoryCommand,
    InventoryVisibilityAction,
    InventoryVisibilityCommand,
    LocationCommand,
    VolumeCommand,
)
from namisync.core.root_authority import (
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
    admit_root_chain,
)
from namisync.core.review import (
    MAX_PLAN_REVIEW_ROWS,
    ReviewFactLimitError,
    ReviewFactLimitExceeded,
    ReviewLimitAxis,
    ReviewPopulation,
    ReviewTreeKind,
    ScanPopulationAdmission,
    snapshot_scan_result,
    snapshot_review_fact_limit,
)
from namisync.core.scalars import (
    MAX_DIAGNOSTIC_UTF8_BYTES,
    MAX_PATH_UTF16_UNITS,
    MAX_REQUEST_ID_UTF8_BYTES,
    MAX_SIGNED_64,
    bounded_utf8_text,
    checked_add_signed_64,
    require_json_unicode,
    require_safe_int,
    require_signed_64,
    require_utf16_path,
    require_utf16_text,
    require_utf8_text,
)
from namisync.core.session import (
    Canceled,
    Disposition,
    FailureDetail,
    OperationResult,
    PauseRequested,
    RunContext,
    SessionState,
)
from namisync.db.recorder import LedgerRecorder
from namisync.db.repositories import (
    InventorySnapshot,
    LedgerRepository,
    LocationSnapshot,
)
from namisync.modules.scanner import (
    NativeScannerBackend,
    VolumeSnapshot,
    validate_volume_snapshot,
)

from ._json_envelope import (
    JSON_SCALAR_CHARGE,
    JsonEnvelopeCounter,
    canonical_byte_ceiling,
    encode_canonical_json,
    model_array_charge,
    model_object_charge,
    model_text_charge,
    object_layout,
    require_payload_bytes,
)


_MAX_LOGICAL_DRIVE_ROOTS = 26
_MAX_PERSISTED_MOUNT_HINTS = 1
# A production binding is formed from the logical-drive enumeration plus at
# most one persisted folder-mounted-volume hint. A later resolution may replay
# every admitted binding candidate as a hint and enumerate the drives again.
# These limits describe this resolver's source graph, not all Windows mounts.
MAX_MOUNT_CANDIDATES = (
    _MAX_LOGICAL_DRIVE_ROOTS + _MAX_PERSISTED_MOUNT_HINTS
)
MAX_VOLUME_RESOLUTION_CANDIDATES = (
    MAX_MOUNT_CANDIDATES + _MAX_LOGICAL_DRIVE_ROOTS
)
# The zero-buffer GetLogicalDriveStringsW result includes the final MULTI_SZ
# terminator: 26 drive roots at four characters each, plus one trailing NUL.
_MAX_LOGICAL_DRIVE_STRING_CHARS = _MAX_LOGICAL_DRIVE_ROOTS * 4 + 1

_PATH_UTF8_LIMIT = MAX_PATH_UTF16_UNITS * 3
_VOLUME_TEXT_UTF8_LIMIT = MAX_VOLUME_TEXT_UTF16_UNITS * 3
_TIMESTAMP_UTF8_LIMIT = len(
    datetime.max.replace(tzinfo=timezone.utc).isoformat()
)
_INTEGRITY_ITEM_ID_UTF8_LIMIT = 2 * len(str(MAX_SIGNED_64)) + 1
_INTEGRITY_RECORDING_ISSUE_LIMIT = 5

_VOLUME_ID_LAYOUT = object_layout("serial", "fs_type")
_LOCATION_BINDING_LAYOUT = object_layout(
    "volume",
    "volume_relative_path",
    "selected_mount",
    "expected_mounts",
    "explicit_ambiguity_choice",
    "location_id",
)
_INVENTORY_PAYLOAD_LAYOUT = object_layout(
    "version",
    "kind",
    "request_id",
    "binding",
    "selected_paths",
    "subtree_roots",
)
_INTEGRITY_PAYLOAD_LAYOUT = object_layout(
    "version",
    "kind",
    "request_id",
    "binding",
    "mode",
    "selected_paths",
    "stale_before",
    "selection_item_ids",
    "completed_bytes",
    "processed_bytes",
    "bytes_total_high_water",
    "recording",
    "recording_issues",
    "omitted_detail_count",
    "refresh_generation",
)
_INTEGRITY_COMPLETION_LAYOUT = model_array_charge(2)
_INTEGRITY_ISSUE_LAYOUT = object_layout("reason", "detail")


def _enum_utf8_limit(enum_type: type[StrEnum]) -> int:
    return max(len(item.value.encode("utf-8")) for item in enum_type)


_LOCATION_BINDING_MAX_OCCURRENCE_CHARGE = (
    model_object_charge(_LOCATION_BINDING_LAYOUT)
    + model_object_charge(_VOLUME_ID_LAYOUT)
    + 2 * model_text_charge(_VOLUME_TEXT_UTF8_LIMIT)
    + 2 * model_text_charge(_PATH_UTF8_LIMIT)
    + model_array_charge(MAX_MOUNT_CANDIDATES)
    + MAX_MOUNT_CANDIDATES * model_text_charge(_PATH_UTF8_LIMIT)
    + 2 * JSON_SCALAR_CHARGE
)
_INVENTORY_MAX_OCCURRENCE_CHARGE = (
    model_object_charge(_INVENTORY_PAYLOAD_LAYOUT)
    + JSON_SCALAR_CHARGE
    + model_text_charge(len("inventory"))
    + model_text_charge(MAX_REQUEST_ID_UTF8_BYTES)
    + _LOCATION_BINDING_MAX_OCCURRENCE_CHARGE
    + model_array_charge(SCAN_SCOPE_ENTRY_LIMIT)
    + model_array_charge(0)
    + SCAN_SCOPE_ENTRY_LIMIT * model_text_charge(_PATH_UTF8_LIMIT)
)
_INTEGRITY_COMPLETION_MAX_OCCURRENCE_CHARGE = (
    _INTEGRITY_COMPLETION_LAYOUT
    + model_text_charge(_INTEGRITY_ITEM_ID_UTF8_LIMIT)
    + JSON_SCALAR_CHARGE
)
_INTEGRITY_ISSUE_MAX_OCCURRENCE_CHARGE = (
    model_object_charge(_INTEGRITY_ISSUE_LAYOUT)
    + model_text_charge(_enum_utf8_limit(TaskRecordingIssueReason))
    + max(JSON_SCALAR_CHARGE, model_text_charge(MAX_DIAGNOSTIC_UTF8_BYTES))
)
_INTEGRITY_MAX_OCCURRENCE_CHARGE = (
    model_object_charge(_INTEGRITY_PAYLOAD_LAYOUT)
    + JSON_SCALAR_CHARGE
    + model_text_charge(len("integrity"))
    + model_text_charge(MAX_REQUEST_ID_UTF8_BYTES)
    + _LOCATION_BINDING_MAX_OCCURRENCE_CHARGE
    + model_text_charge(_enum_utf8_limit(IntegrityMode))
    + model_array_charge(INTEGRITY_CANDIDATE_ROW_LIMIT)
    + INTEGRITY_CANDIDATE_ROW_LIMIT * model_text_charge(_PATH_UTF8_LIMIT)
    + max(JSON_SCALAR_CHARGE, model_text_charge(_TIMESTAMP_UTF8_LIMIT))
    + model_array_charge(INTEGRITY_CANDIDATE_ROW_LIMIT)
    + INTEGRITY_CANDIDATE_ROW_LIMIT
    * model_text_charge(_INTEGRITY_ITEM_ID_UTF8_LIMIT)
    + model_array_charge(INTEGRITY_CANDIDATE_ROW_LIMIT)
    + INTEGRITY_CANDIDATE_ROW_LIMIT
    * _INTEGRITY_COMPLETION_MAX_OCCURRENCE_CHARGE
    + 4 * JSON_SCALAR_CHARGE
    + model_text_charge(_enum_utf8_limit(RecordingStatus))
    + model_array_charge(_INTEGRITY_RECORDING_ISSUE_LIMIT)
    + _INTEGRITY_RECORDING_ISSUE_LIMIT
    * _INTEGRITY_ISSUE_MAX_OCCURRENCE_CHARGE
)

INVENTORY_PAYLOAD_BYTE_LIMIT = canonical_byte_ceiling(
    _INVENTORY_MAX_OCCURRENCE_CHARGE
)
INTEGRITY_PAYLOAD_BYTE_LIMIT = canonical_byte_ceiling(
    _INTEGRITY_MAX_OCCURRENCE_CHARGE
)


class VolumeResolutionState(StrEnum):
    RESOLVED = "resolved"
    OFFLINE = "offline"
    AMBIGUOUS = "ambiguous"
    ROOT_MISSING = "root_missing"
    ROOT_UNAVAILABLE = "root_unavailable"


@dataclass(frozen=True, slots=True)
class MountedVolume:
    mount_path: str
    evidence: VolumeEvidence

    def __post_init__(self) -> None:
        _require_mounted_volume_fields(self)


def _require_mounted_volume_fields(value: MountedVolume) -> None:
    require_utf16_path(value.mount_path, "mounted volume path")
    if not value.mount_path:
        raise ValueError("mounted volume path is required")
    if type(value.evidence) is not VolumeEvidence:
        raise TypeError("mounted volume evidence has the wrong type")
    VolumeEvidence(
        value.evidence.label,
        value.evidence.device_id,
        value.evidence.clone_ambiguous,
    )


class MountedVolumeResolver(Protocol):
    def mounted_volumes(
        self, volume_id: VolumeId, hints: tuple[str, ...] = ()
    ) -> tuple[MountedVolume, ...]: ...

    def probe_root(self, root_path: str) -> None: ...


def _mounted_volume_snapshot(
    resolver: MountedVolumeResolver,
    volume_id: VolumeId,
    hints: tuple[str, ...],
) -> tuple[MountedVolume, ...]:
    value = resolver.mounted_volumes(
        VolumeId(volume_id.serial, volume_id.fs_type),
        hints=hints,
    )
    if type(value) is not tuple:
        raise TypeError("mounted-volume result must be a tuple")
    if len(value) > MAX_VOLUME_RESOLUTION_CANDIDATES:
        raise ValueError("mounted-volume result exceeds the candidate limit")
    keys: set[str] = set()
    mounted: list[MountedVolume] = []
    for item in value:
        if type(item) is not MountedVolume:
            raise TypeError("mounted-volume result contains an invalid value")
        evidence = item.evidence
        if type(evidence) is not VolumeEvidence:
            raise TypeError("mounted volume evidence has the wrong type")
        snapshot = MountedVolume(
            item.mount_path,
            VolumeEvidence(
                evidence.label,
                evidence.device_id,
                evidence.clone_ambiguous,
            ),
        )
        key = _path_key(snapshot.mount_path)
        if key in keys:
            raise ValueError("mounted-volume result contains duplicate paths")
        keys.add(key)
        mounted.append(snapshot)
    del value, keys
    return tuple(mounted)


class VolumeBindingBackend(Protocol):
    def resolve_root(self, path: str) -> str: ...

    def volume_snapshot(self, root: str) -> VolumeSnapshot: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class LocationBinding:
    volume_id: VolumeId
    volume_relative_path: str
    selected_mount: str
    expected_mounts: tuple[str, ...]
    explicit_ambiguity_choice: bool
    location_id: int | None = None

    def __post_init__(self) -> None:
        _require_location_binding_fields(self, canonicalize=True)


def _require_location_binding_fields(
    value: LocationBinding,
    *,
    canonicalize: bool = False,
) -> None:
    if type(value.volume_id) is not VolumeId:
        raise TypeError("location binding volume has the wrong type")
    VolumeId(value.volume_id.serial, value.volume_id.fs_type)
    canonical = validate_relative_path(
        value.volume_relative_path, allow_root=True
    )
    if canonical != value.volume_relative_path:
        if canonicalize:
            object.__setattr__(value, "volume_relative_path", canonical)
        else:
            raise ValueError("location binding relative path is not canonical")
    require_utf16_path(value.selected_mount, "selected volume mount")
    if type(value.expected_mounts) is not tuple:
        raise TypeError("location binding mount candidates must be a tuple")
    if not value.selected_mount or not value.expected_mounts:
        raise ValueError("location binding requires a selected mounted volume")
    if len(value.expected_mounts) > MAX_MOUNT_CANDIDATES:
        raise ValueError("location binding exceeds the mount-candidate limit")
    for path in value.expected_mounts:
        require_utf16_path(path, "expected volume mount")
        if not path:
            raise ValueError("expected volume mount is required")
    expected_keys = tuple(_path_key(path) for path in value.expected_mounts)
    if len(expected_keys) != len(set(expected_keys)):
        raise ValueError("location binding mount candidates must be unique")
    if _path_key(value.selected_mount) not in set(expected_keys):
        raise ValueError("selected mount must be one of the expected candidates")
    if type(value.explicit_ambiguity_choice) is not bool:
        raise TypeError("explicit ambiguity choice must be a bool")
    if value.explicit_ambiguity_choice and len(value.expected_mounts) < 2:
        raise ValueError("explicit ambiguity choice requires multiple candidates")
    if value.location_id is not None:
        require_safe_int(value.location_id, "location binding id")
        if value.location_id < 1:
            raise ValueError("location binding id must be positive")


def _snapshot_location_binding(value: object) -> LocationBinding:
    if type(value) is not LocationBinding:
        raise TypeError("volume resolution requires LocationBinding")
    volume_id = value.volume_id
    relative = value.volume_relative_path
    selected_mount = value.selected_mount
    expected_mounts = value.expected_mounts
    explicit_choice = value.explicit_ambiguity_choice
    location_id = value.location_id
    if type(volume_id) is not VolumeId:
        raise TypeError("location binding volume has the wrong type")
    if type(expected_mounts) is not tuple:
        raise TypeError("location binding mount candidates must be a tuple")
    snapshot = LocationBinding(
        VolumeId(volume_id.serial, volume_id.fs_type),
        relative,
        selected_mount,
        expected_mounts,
        explicit_choice,
        location_id,
    )
    if snapshot.volume_relative_path != relative:
        raise ValueError("location binding relative path is not canonical")
    return snapshot


@dataclass(frozen=True, slots=True)
class VolumeResolution:
    state: VolumeResolutionState
    binding: LocationBinding
    root_path: str | None = None
    selected_mount: str | None = None
    evidence: VolumeEvidence | None = None
    candidates: tuple[str, ...] = ()
    detail: str | None = None

    def __post_init__(self) -> None:
        if type(self.state) is not VolumeResolutionState:
            raise TypeError("volume resolution state has the wrong type")
        if type(self.binding) is not LocationBinding:
            raise TypeError("volume resolution binding has the wrong type")
        _require_location_binding_fields(self.binding)
        for field_name, path in (
            ("resolved root path", self.root_path),
            ("resolved selected mount", self.selected_mount),
        ):
            if path is not None:
                require_utf16_path(path, field_name)
                if not path:
                    raise ValueError(f"{field_name} is required when present")
        if self.evidence is not None:
            if type(self.evidence) is not VolumeEvidence:
                raise TypeError("volume resolution evidence has the wrong type")
            VolumeEvidence(
                self.evidence.label,
                self.evidence.device_id,
                self.evidence.clone_ambiguous,
            )
        if type(self.candidates) is not tuple:
            raise TypeError("volume resolution candidates must be a tuple")
        if len(self.candidates) > MAX_VOLUME_RESOLUTION_CANDIDATES:
            raise ValueError("volume resolution exceeds the mount-candidate limit")
        for candidate in self.candidates:
            require_utf16_path(candidate, "volume resolution candidate")
            if not candidate:
                raise ValueError("volume resolution candidate is required")
        candidate_keys = tuple(_path_key(path) for path in self.candidates)
        if len(candidate_keys) != len(set(candidate_keys)):
            raise ValueError("volume resolution candidates must be unique")
        if self.detail is not None:
            if type(self.detail) is not str:
                raise TypeError("volume resolution detail must be text or None")
            if bounded_utf8_text(
                self.detail,
                "volume resolution detail",
                maximum_bytes=MAX_DIAGNOSTIC_UTF8_BYTES,
            ) is None:
                object.__setattr__(self, "detail", None)
        if self.state is VolumeResolutionState.RESOLVED:
            if self.root_path is None or self.selected_mount is None:
                raise ValueError(
                    "resolved volume requires its current root and mount"
                )
            try:
                lexical_path_chain(
                    self.root_path,
                    trusted_anchor=self.selected_mount,
                )
            except PathValidationError as error:
                raise ValueError(
                    "resolved root is outside its current mount"
                ) from error


class VolumeResolutionRequired(ValueError):
    def __init__(self, resolution: VolumeResolution) -> None:
        super().__init__(
            resolution.state
            if resolution.detail is None
            else f"{resolution.state}: {resolution.detail}"
        )
        self.resolution = resolution


@dataclass(frozen=True, slots=True)
class InventoryRequest:
    request_id: str
    root_path: str | None = None
    location_id: int | None = None
    selected_paths: tuple[str, ...] = ()
    selected_mount: str | None = None
    subtree_roots: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_location_request(
            self.request_id, self.root_path, self.location_id
        )
        if self.selected_mount is not None:
            require_utf16_path(self.selected_mount, "selected volume mount")
        scope = ScanScope.scoped(
            selected_paths=self.selected_paths,
            subtree_roots=self.subtree_roots,
        )
        object.__setattr__(self, "selected_paths", scope.selected_paths)
        object.__setattr__(self, "subtree_roots", scope.subtree_roots)


@dataclass(frozen=True, slots=True)
class IntegrityRequest:
    request_id: str
    mode: IntegrityMode
    root_path: str | None = None
    location_id: int | None = None
    selected_paths: tuple[str, ...] = ()
    selected_mount: str | None = None
    stale_before: datetime | None = None

    def __post_init__(self) -> None:
        _validate_location_request(
            self.request_id, self.root_path, self.location_id
        )
        if type(self.mode) is not IntegrityMode:
            raise TypeError("integrity mode has the wrong type")
        if self.selected_mount is not None:
            require_utf16_path(self.selected_mount, "selected volume mount")
        if type(self.selected_paths) is not tuple:
            raise TypeError("integrity selected_paths must be a tuple")
        scope = ScanScope.scoped(selected_paths=self.selected_paths)
        object.__setattr__(self, "selected_paths", scope.selected_paths)
        if self.stale_before is not None:
            _require_utc(self.stale_before, "stale_before")


@dataclass(frozen=True, slots=True)
class InventoryDetails:
    request_id: str
    resolution: VolumeResolution
    location_id: int | None = None
    observed_count: int = 0
    missing_count: int = 0
    complete: bool = False
    selected_paths: tuple[str, ...] = ()
    warnings: tuple[ScanWarning, ...] = ()


@dataclass(frozen=True, slots=True)
class InventoryWorkflowRequest:
    request_id: str
    binding: LocationBinding
    selected_paths: tuple[str, ...] = ()
    subtree_roots: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_workflow_request(self.request_id, self.binding)
        scope = ScanScope.scoped(
            selected_paths=self.selected_paths,
            subtree_roots=self.subtree_roots,
        )
        object.__setattr__(self, "selected_paths", scope.selected_paths)
        object.__setattr__(self, "subtree_roots", scope.subtree_roots)


@dataclass(frozen=True, slots=True)
class IntegrityWorkflowRequest:
    request_id: str
    binding: LocationBinding
    mode: IntegrityMode
    selected_paths: tuple[str, ...] = ()
    stale_before: datetime | None = None
    selection_item_ids: tuple[str, ...] = ()
    completed_bytes: tuple[tuple[str, int], ...] = ()
    processed_bytes: int = 0
    refresh_generation: int = 0
    bytes_total_high_water: int = 0
    recording: RecordingStatus = RecordingStatus.OK
    recording_issues: tuple[TaskRecordingIssue, ...] = ()
    omitted_detail_count: int = 0

    def __post_init__(self) -> None:
        _require_workflow_request(self.request_id, self.binding)
        if type(self.mode) is not IntegrityMode:
            raise TypeError("integrity mode has the wrong type")
        if type(self.selected_paths) is not tuple:
            raise TypeError("integrity selected_paths must be a tuple")
        if len(self.selected_paths) > INTEGRITY_CANDIDATE_ROW_LIMIT:
            raise IntegrityCandidateLimitError(
                IntegrityCandidateLimitExceeded.rows()
            )
        if self.selected_paths:
            object.__setattr__(
                self,
                "selected_paths",
                ScanScope.selected(self.selected_paths).selected_paths,
            )
        if self.stale_before is not None:
            _require_utc(self.stale_before, "stale_before")
        if type(self.selection_item_ids) is not tuple:
            raise TypeError("integrity selection_item_ids must be a tuple")
        if len(self.selection_item_ids) > INTEGRITY_CANDIDATE_ROW_LIMIT:
            raise IntegrityCandidateLimitError(
                IntegrityCandidateLimitExceeded.rows()
            )
        if type(self.completed_bytes) is not tuple:
            raise TypeError("integrity completed_bytes must be a tuple")
        if len(self.completed_bytes) > len(self.selection_item_ids):
            raise ValueError(
                "completed integrity items must belong to the saved selection"
            )
        selection_positions: dict[str, int] = {}
        for index, item_id in enumerate(self.selection_item_ids):
            _require_integrity_item_id(
                item_id,
                "integrity selection item id",
            )
            if item_id in selection_positions:
                raise ValueError("integrity selection item ids must be unique")
            selection_positions[item_id] = index
        completed_ids: set[str] = set()
        last_completed_position = -1
        completed_bytes = 0
        for entry in self.completed_bytes:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise TypeError(
                    "integrity completed_bytes entries must be two-item tuples"
                )
            item_id, size = entry
            _require_integrity_item_id(
                item_id,
                "completed integrity item id",
            )
            if item_id in completed_ids:
                raise ValueError("completed integrity item ids must be unique")
            completed_ids.add(item_id)
            position = selection_positions.get(item_id)
            if position is None:
                raise ValueError(
                    "completed integrity items must belong to the saved selection"
                )
            if position <= last_completed_position:
                raise ValueError(
                    "completed integrity items must follow saved selection order"
                )
            last_completed_position = position
            require_signed_64(size, "completed integrity byte count")
            completed_bytes = checked_add_signed_64(
                completed_bytes,
                size,
                "completed integrity bytes",
            )
        require_signed_64(self.processed_bytes, "integrity processed bytes")
        if self.processed_bytes > 0 and not self.selection_item_ids:
            raise ValueError(
                "integrity progress requires the saved admitted selection"
            )
        if self.processed_bytes < completed_bytes:
            raise ValueError("processed bytes cannot trail completed bytes")
        require_signed_64(
            self.bytes_total_high_water,
            "integrity byte-total high-water",
        )
        if self.bytes_total_high_water < self.processed_bytes:
            raise ValueError(
                "integrity byte-total high-water cannot trail processed bytes"
            )
        if self.bytes_total_high_water > 0 and not self.selection_item_ids:
            raise ValueError(
                "integrity byte-total high-water requires the saved admitted selection"
            )
        if not isinstance(self.recording, RecordingStatus):
            raise TypeError("integrity recording status has the wrong type")
        if not isinstance(self.recording_issues, tuple) or any(
            not isinstance(issue, TaskRecordingIssue)
            for issue in self.recording_issues
        ):
            raise TypeError(
                "integrity recording issues must contain TaskRecordingIssue values"
            )
        issue_reasons = tuple(issue.reason for issue in self.recording_issues)
        if len(issue_reasons) != len(set(issue_reasons)):
            raise ValueError("integrity recording issue reasons must be unique")
        if len(self.recording_issues) > 5:
            raise ValueError("integrity recording issues exceed their bound")
        if self.recording_issues and self.recording is not RecordingStatus.DEGRADED:
            raise ValueError("integrity recording issues require degraded status")
        require_safe_int(
            self.omitted_detail_count,
            "integrity omitted_detail_count",
        )
        require_safe_int(
            self.refresh_generation,
            "inventory refresh generation",
        )


def _require_integrity_item_id(value: object, context: str) -> str:
    return require_utf8_text(
        value,
        context,
        minimum_bytes=1,
        maximum_bytes=_INTEGRITY_ITEM_ID_UTF8_LIMIT,
    )


def _exact_inventory_request(value: object) -> InventoryRequest:
    if type(value) is not InventoryRequest:
        raise TypeError("inventory binding requires InventoryRequest")
    return InventoryRequest(
        request_id=value.request_id,
        root_path=value.root_path,
        location_id=value.location_id,
        selected_paths=value.selected_paths,
        selected_mount=value.selected_mount,
        subtree_roots=value.subtree_roots,
    )


def _exact_integrity_request(value: object) -> IntegrityRequest:
    if type(value) is not IntegrityRequest:
        raise TypeError("integrity binding requires IntegrityRequest")
    return IntegrityRequest(
        request_id=value.request_id,
        mode=value.mode,
        root_path=value.root_path,
        location_id=value.location_id,
        selected_paths=value.selected_paths,
        selected_mount=value.selected_mount,
        stale_before=value.stale_before,
    )


def _exact_inventory_workflow_request(
    value: object,
) -> InventoryWorkflowRequest:
    if type(value) is not InventoryWorkflowRequest:
        raise TypeError("inventory workflow requires InventoryWorkflowRequest")
    return InventoryWorkflowRequest(
        value.request_id,
        value.binding,
        value.selected_paths,
        value.subtree_roots,
    )


def _exact_integrity_workflow_request(
    value: object,
) -> IntegrityWorkflowRequest:
    if type(value) is not IntegrityWorkflowRequest:
        raise TypeError("integrity workflow requires IntegrityWorkflowRequest")
    return IntegrityWorkflowRequest(
        request_id=value.request_id,
        binding=value.binding,
        mode=value.mode,
        selected_paths=value.selected_paths,
        stale_before=value.stale_before,
        selection_item_ids=value.selection_item_ids,
        completed_bytes=value.completed_bytes,
        processed_bytes=value.processed_bytes,
        refresh_generation=value.refresh_generation,
        bytes_total_high_water=value.bytes_total_high_water,
        recording=value.recording,
        recording_issues=value.recording_issues,
        omitted_detail_count=value.omitted_detail_count,
    )


@dataclass(frozen=True, slots=True)
class _ObservedTaskRecordingIssue:
    issue: TaskRecordingIssue
    omitted_detail_count: int
    failure: FailureDetail


class _InventoryScanAdmission:
    """Issue exact inventory review facts for one raw scan population."""

    __slots__ = ("_issuer",)

    def __init__(self) -> None:
        self._issuer = object()

    def _limit_error(
        self,
        population: ReviewPopulation,
    ) -> ReviewFactLimitError:
        fact = ReviewFactLimitExceeded(
            "review_fact_limit_exceeded",
            ReviewTreeKind.INVENTORY,
            population,
            ReviewLimitAxis.ROWS,
            MAX_PLAN_REVIEW_ROWS,
            None,
        )
        error = ReviewFactLimitError(fact)
        error._inventory_review_issuer = self._issuer
        return error

    def require_source_rows(self, count: int) -> None:
        _require_inventory_scan_count(count, "inventory scan domain rows")
        if count > MAX_PLAN_REVIEW_ROWS:
            raise self._limit_error(ReviewPopulation.DOMAIN)

    def require_informational_source_rows(self, count: int) -> None:
        _require_inventory_scan_count(
            count,
            "inventory scan informational rows",
        )
        if count > MAX_PLAN_REVIEW_ROWS:
            raise self._limit_error(ReviewPopulation.INFORMATIONAL)


class Scanner(Protocol):
    def __call__(
        self,
        root: Root,
        ignores: IgnoreSet,
        context: RunContext,
        scope: ScanScope | None,
        *,
        trusted_anchor: str | None = None,
        population_admission: ScanPopulationAdmission,
    ) -> ScanResult: ...


IntegrityRunner = Callable[
    [IntegritySelection, VerifierContext, LedgerRecorder], IntegrityRunResult
]


@dataclass(frozen=True, slots=True)
class InventoryDependencies:
    ledger_path: Path
    scanner: Scanner
    resolver: MountedVolumeResolver
    clock: Clock
    host_key: str
    host_name: str
    save_details: Callable[[InventoryDetails], None]
    ignores: IgnoreSet = IgnoreSet()


@dataclass(frozen=True, slots=True)
class IntegrityDependencies(InventoryDependencies):
    verifier_context: Callable[[RunContext], VerifierContext] = field(
        default=lambda _context: _missing_verifier_context()
    )
    runners: Mapping[IntegrityMode, IntegrityRunner] = field(default_factory=dict)


class NativeMountedVolumeResolver:
    """Resolve a stable volume identity back to its currently mounted roots."""

    def __init__(self, backend: NativeScannerBackend | None = None) -> None:
        self._backend = backend or NativeScannerBackend()

    def mounted_volumes(
        self, volume_id: VolumeId, hints: tuple[str, ...] = ()
    ) -> tuple[MountedVolume, ...]:
        if type(volume_id) is not VolumeId:
            raise TypeError("mounted-volume lookup requires VolumeId")
        VolumeId(volume_id.serial, volume_id.fs_type)
        if type(hints) is not tuple:
            raise TypeError("mounted-volume hints must be a tuple")
        if len(hints) > MAX_MOUNT_CANDIDATES:
            raise ValueError("mounted-volume hints exceed the candidate limit")
        for hint in hints:
            require_utf16_path(hint, "mounted-volume hint")
        candidates = {*hints, *_logical_drive_roots()}
        mounted: dict[str, MountedVolume] = {}
        for path in candidates:
            if not path:
                continue
            try:
                snapshot = self._backend.volume_snapshot(path)
            except (OSError, PermissionError):
                continue
            validate_volume_snapshot(snapshot)
            if snapshot.volume_id != volume_id:
                continue
            mount = snapshot.evidence.device_id or path
            mounted[_path_key(mount)] = MountedVolume(mount, snapshot.evidence)
            if len(mounted) > MAX_VOLUME_RESOLUTION_CANDIDATES:
                raise ValueError("mounted-volume result exceeds the candidate limit")
        return tuple(mounted[key] for key in sorted(mounted))

    def probe_root(self, root_path: str) -> None:
        with self._backend.scandir(root_path):
            return


def bind_inventory_request(
    request: InventoryRequest,
    *,
    ledger_path: Path,
    backend: VolumeBindingBackend,
    resolver: MountedVolumeResolver,
) -> InventoryWorkflowRequest:
    request = _exact_inventory_request(request)
    binding = _bind_request_location(
        request.root_path,
        request.location_id,
        request.selected_mount,
        ledger_path=ledger_path,
        backend=backend,
        resolver=resolver,
    )
    return InventoryWorkflowRequest(
        request.request_id,
        binding,
        request.selected_paths,
        request.subtree_roots,
    )


def bind_integrity_request(
    request: IntegrityRequest,
    *,
    ledger_path: Path,
    backend: VolumeBindingBackend,
    resolver: MountedVolumeResolver,
) -> IntegrityWorkflowRequest:
    request = _exact_integrity_request(request)
    binding = _bind_request_location(
        request.root_path,
        request.location_id,
        request.selected_mount,
        ledger_path=ledger_path,
        backend=backend,
        resolver=resolver,
    )
    return IntegrityWorkflowRequest(
        request.request_id,
        binding,
        request.mode,
        request.selected_paths,
        request.stale_before,
    )


def resolve_binding(
    binding: LocationBinding, resolver: MountedVolumeResolver
) -> VolumeResolution:
    binding = _snapshot_location_binding(binding)
    mounted = _mounted_volume_snapshot(
        resolver,
        binding.volume_id,
        binding.expected_mounts,
    )
    candidates = tuple(item.mount_path for item in mounted)
    if not mounted:
        return VolumeResolution(
            VolumeResolutionState.OFFLINE,
            binding,
            candidates=candidates,
            detail="recorded volume is not mounted",
        )
    if binding.explicit_ambiguity_choice:
        expected = {_path_key(path) for path in binding.expected_mounts}
        current = {_path_key(path) for path in candidates}
        choice = next(
            (
                item
                for item in mounted
                if _path_key(item.mount_path) == _path_key(binding.selected_mount)
            ),
            None,
        )
        if current != expected or choice is None:
            return VolumeResolution(
                VolumeResolutionState.AMBIGUOUS,
                binding,
                candidates=candidates,
                detail="duplicate volume identity requires a fresh explicit choice",
            )
        selected = choice
    elif len(mounted) > 1:
        return VolumeResolution(
            VolumeResolutionState.AMBIGUOUS,
            binding,
            candidates=candidates,
            detail="duplicate volume identity requires a fresh explicit choice",
        )
    else:
        selected = mounted[0]
    root_path = _join_volume_root(
        selected.mount_path, binding.volume_relative_path
    )
    try:
        admit_root_chain(
            RootAuthority(root_path, selected.mount_path),
            anchor_probe=lambda _path: selected.mount_path,
        )
    except PathValidationError as error:
        return VolumeResolution(
            VolumeResolutionState.ROOT_UNAVAILABLE,
            binding,
            root_path=root_path,
            evidence=selected.evidence,
            candidates=candidates,
            detail=logical_error_text(error),
        )
    except RootAuthorityError as error:
        cause = error.__cause__
        missing = (
            error.issue is RootAuthorityIssue.NON_DIRECTORY_COMPONENT
            or (
                error.issue is RootAuthorityIssue.COMPONENT_UNAVAILABLE
                and isinstance(cause, FileNotFoundError)
            )
        )
        reparse = error.issue in {
            RootAuthorityIssue.PLACEHOLDER_COMPONENT,
            RootAuthorityIssue.REPARSE_COMPONENT,
        }
        detail_source = cause if isinstance(cause, OSError) else error
        return VolumeResolution(
            (
                VolumeResolutionState.ROOT_MISSING
                if missing
                else VolumeResolutionState.ROOT_UNAVAILABLE
            ),
            binding,
            root_path=root_path,
            evidence=selected.evidence,
            candidates=candidates,
            detail=(
                "configured root no longer exists"
                if isinstance(cause, FileNotFoundError)
                else (
                    "configured root chain is not a directory"
                    if missing
                    else (
                        "configured root chain contains a reparse point"
                        if reparse
                        else logical_error_text(detail_source)
                    )
                )
            ),
        )
    try:
        resolver.probe_root(root_path)
    except (OSError, PermissionError) as error:
        return VolumeResolution(
            VolumeResolutionState.ROOT_UNAVAILABLE,
            binding,
            root_path=root_path,
            evidence=selected.evidence,
            candidates=candidates,
            detail=logical_error_text(error),
        )
    current_mounted = _mounted_volume_snapshot(
        resolver,
        binding.volume_id,
        binding.expected_mounts,
    )
    if len(current_mounted) != len(mounted) or any(
        item not in current_mounted for item in mounted
    ):
        return VolumeResolution(
            VolumeResolutionState.ROOT_UNAVAILABLE,
            binding,
            root_path=root_path,
            evidence=selected.evidence,
            candidates=tuple(item.mount_path for item in current_mounted),
            detail="mounted volume set changed during root admission; retry",
        )
    return VolumeResolution(
        VolumeResolutionState.RESOLVED,
        binding,
        root_path=root_path,
        selected_mount=selected.mount_path,
        evidence=selected.evidence,
        candidates=candidates,
    )


def run_inventory(
    request: InventoryWorkflowRequest,
    ctx: RunContext,
    deps: InventoryDependencies,
) -> OperationResult:
    request = _exact_inventory_workflow_request(request)
    resolution = resolve_binding(request.binding, deps.resolver)
    if resolution.state != VolumeResolutionState.RESOLVED:
        deps.save_details(
            InventoryDetails(
                request.request_id,
                resolution,
                selected_paths=request.selected_paths,
            )
        )
        return _refused_resolution(resolution)
    if (
        resolution.root_path is None
        or resolution.selected_mount is None
        or resolution.evidence is None
    ):
        raise RuntimeError("resolved inventory root lacks volume evidence")
    root = resolution.root_path
    scope_token = request.request_id
    review_admission = _InventoryScanAdmission()
    review_limit_fact: ReviewFactLimitExceeded | None = None
    invalid_review_limit = False
    unadmitted_review_limit = False
    try:
        with LedgerRecorder(
            deps.ledger_path, clock=deps.clock, managed_roots=(root,)
        ) as recorder:
            host_id, location_id, scan = _register_and_scan(
                request.request_id,
                scope_token,
                resolution.binding,
                resolution,
                request.selected_paths,
                request.subtree_roots,
                ctx,
                deps,
                recorder,
                review_admission,
            )
            recorded = recorder.record_inventory(
                InventoryCommand(
                    location_id,
                    host_id,
                    scan,
                    scope_token,
                    deps.clock.now(),
                )
            )
    except ReviewFactLimitError as error:
        if type(error) is not ReviewFactLimitError:
            invalid_review_limit = True
        else:
            try:
                review_limit_fact = _consume_inventory_review_limit(
                    error,
                    review_admission,
                )
                unadmitted_review_limit = review_limit_fact is None
            except (AttributeError, TypeError, ValueError) as fact_error:
                retire_exception_graph(fact_error)
                invalid_review_limit = True
        retire_exception_graph(error)

    if invalid_review_limit:
        raise RuntimeError("inventory review limit failure is invalid") from None
    if unadmitted_review_limit:
        raise RuntimeError(
            "unadmitted collaborator raised an inventory review fact limit"
        ) from None
    if review_limit_fact is not None:
        return OperationResult(
            SessionState.REFUSED,
            disposition=Disposition.UNRUN,
            review_fact_limit=review_limit_fact,
        )
    deps.save_details(
        InventoryDetails(
            request.request_id,
            resolution,
            location_id,
            recorded.observed_count,
            recorded.missing_count,
            scan.complete,
            request.selected_paths,
            scan.warnings,
        )
    )
    return OperationResult(SessionState.COMPLETED)


def run_integrity(
    request: IntegrityWorkflowRequest,
    ctx: RunContext,
    deps: IntegrityDependencies,
    *,
    selection_sink: Callable[[IntegritySelection], None] | None = None,
    recording_sink: (
        Callable[
            [RecordingStatus, tuple[TaskRecordingIssue, ...], int],
            None,
        ]
        | None
    ) = None,
) -> OperationResult:
    request = _exact_integrity_workflow_request(request)
    try:
        resolution = resolve_binding(request.binding, deps.resolver)
        if resolution.state != VolumeResolutionState.RESOLVED:
            deps.save_details(
                InventoryDetails(
                    request.request_id,
                    resolution,
                    selected_paths=request.selected_paths,
                )
            )
            refused = _refused_resolution(resolution)
            if request.refresh_generation > 0:
                assert refused.error is not None
                return _integrity_request_terminal_result(
                    request,
                    SessionState.FAILED,
                    recording=request.recording,
                    items=(),
                    error=refused.error,
                )
            return refused
        if resolution.root_path is None or resolution.selected_mount is None:
            raise RuntimeError("resolved integrity root lacks its current mount")
    except PauseRequested:
        raise
    except Canceled:
        return _integrity_request_terminal_result(
            request,
            SessionState.CANCELED,
            recording=request.recording,
            items=(),
            canceled=True,
        )
    except Exception as error:
        return _integrity_request_terminal_result(
            request,
            SessionState.FAILED,
            recording=request.recording,
            items=(),
            error=FailureDetail(type(error).__name__, logical_error_text(error)),
        )
    root = resolution.root_path
    scope_token = f"{request.request_id}:refresh:{request.refresh_generation}"
    selection: IntegritySelection | None = None
    observed_outcomes: list[IntegrityOutcome] = []
    observed_recording = request.recording
    recorder_observation: list[_ObservedTaskRecordingIssue | None] = [None]
    try:
        with _integrity_recorder(
            deps,
            root,
            recorder_observation=recorder_observation,
        ) as recorder:
            host_id, location_id, scan = _register_and_scan(
                request.request_id,
                scope_token,
                resolution.binding,
                resolution,
                request.selected_paths,
                (),
                ctx,
                deps,
                recorder,
                _InventoryScanAdmission(),
            )
            recorded = recorder.record_inventory(
                InventoryCommand(
                    location_id,
                    host_id,
                    scan,
                    scope_token,
                    deps.clock.now(),
                )
            )
            deps.save_details(
                InventoryDetails(
                    request.request_id,
                    resolution,
                    location_id,
                    recorded.observed_count,
                    recorded.missing_count,
                    scan.complete,
                    request.selected_paths,
                    scan.warnings,
                )
            )
            if not scan.complete and not (
                request.selected_paths
                and _subject_local_incompleteness(scan)
            ):
                error = FailureDetail(
                    "InventoryScopeIncomplete",
                    "inventory refresh was not authoritative",
                )
                if request.refresh_generation > 0:
                    return _integrity_request_terminal_result(
                        request,
                        SessionState.FAILED,
                        recording=observed_recording,
                        items=(),
                        error=error,
                    )
                return OperationResult(SessionState.FAILED, error=error)
            with LedgerRepository(deps.ledger_path) as repository:
                rows = _integrity_rows(
                    repository,
                    location_id,
                    request.mode,
                    request.selected_paths,
                    request.stale_before,
                    request.selection_item_ids,
                    frozenset(item_id for item_id, _ in request.completed_bytes),
                )
            del repository
            _require_integrity_candidate_rows(rows)
            selection = _integrity_selection(request, rows, root)
            del rows
            selection_authority = snapshot_integrity_selection_authority(
                selection
            )
            if selection_sink is not None:
                try:
                    selection_sink(selection)
                except Exception:
                    revalidate_integrity_selection_authority(
                        selection,
                        selection_authority,
                        allow_progress=False,
                    )
                    raise
                revalidate_integrity_selection_authority(
                    selection,
                    selection_authority,
                    allow_progress=False,
                )
            initial_completed_ids = frozenset(
                item_id
                for item_id, _completed_bytes in selection_authority.completed_bytes
            )
            observed_ids = set(initial_completed_ids)
            pending_by_id = {
                item.item_id: item
                for item in selection_authority.items
                if item.item_id not in observed_ids
            }
            fixed_selection = selection
            fixed_items = selection.items
            fixed_completion_map = selection._completed_bytes
            confirmed_completion_by_id = dict(
                selection_authority.completed_bytes
            )
            confirmed_completion_count = len(confirmed_completion_by_id)
            confirmed_completed_bytes = 0
            for completed_bytes in confirmed_completion_by_id.values():
                confirmed_completed_bytes = checked_add_signed_64(
                    confirmed_completed_bytes,
                    completed_bytes,
                    "completed integrity bytes",
                )
            confirmed_processed_bytes = selection_authority.processed_bytes
            confirmed_bytes_total = selection_authority.bytes_total_high_water
            pending_completion_id: str | None = None
            full_reconciliation_attempted = False
            full_reconciliation_error: BaseException | None = None

            def reconcile_verification_edge(
                *,
                allow_pending: bool,
                allow_progress: bool,
            ) -> None:
                nonlocal confirmed_completion_count
                nonlocal confirmed_completed_bytes
                nonlocal confirmed_processed_bytes
                nonlocal confirmed_bytes_total
                nonlocal pending_completion_id
                if (
                    selection is not fixed_selection
                    or selection.items is not fixed_items
                ):
                    raise ValueError(
                        "integrity selection items changed during collaboration"
                    )
                completed = selection._completed_bytes
                processed_bytes = selection._processed_bytes
                bytes_total = selection._bytes_total_high_water
                if type(completed) is not dict:
                    raise TypeError(
                        "integrity completion state must be an exact dict"
                    )
                if completed is not fixed_completion_map:
                    raise ValueError(
                        "integrity completion state changed during collaboration"
                    )
                if type(processed_bytes) is not int:
                    raise TypeError(
                        "integrity processed bytes have the wrong type"
                    )
                if type(bytes_total) is not int:
                    raise TypeError("integrity byte total has the wrong type")
                require_signed_64(processed_bytes, "integrity processed bytes")
                require_signed_64(bytes_total, "integrity byte-total high-water")

                pending_item_id = pending_completion_id
                if pending_item_id is None:
                    if len(completed) != confirmed_completion_count:
                        raise ValueError(
                            "integrity runner completion must match its "
                            "emitted outcomes"
                        )
                elif len(completed) == confirmed_completion_count:
                    if not allow_pending or pending_item_id in completed:
                        raise ValueError(
                            "integrity runner completion must match its "
                            "emitted outcomes"
                        )
                elif (
                    len(completed) == confirmed_completion_count + 1
                    and pending_item_id in completed
                ):
                    completed_bytes = completed[pending_item_id]
                    if type(completed_bytes) is not int:
                        raise TypeError(
                            "integrity completion facts have the wrong type"
                        )
                    require_signed_64(
                        completed_bytes,
                        "completed integrity byte count",
                    )
                    confirmed_completed_bytes = checked_add_signed_64(
                        confirmed_completed_bytes,
                        completed_bytes,
                        "completed integrity bytes",
                    )
                    confirmed_completion_count += 1
                    confirmed_completion_by_id[pending_item_id] = completed_bytes
                    pending_completion_id = None
                else:
                    raise ValueError(
                        "integrity runner completion must match its emitted outcomes"
                    )
                if processed_bytes < confirmed_completed_bytes:
                    raise ValueError(
                        "integrity processed bytes cannot trail completed bytes"
                    )
                if allow_progress:
                    if processed_bytes < confirmed_processed_bytes:
                        raise ValueError("integrity processed bytes regressed")
                    if bytes_total < confirmed_bytes_total:
                        raise ValueError("integrity byte total regressed")
                elif (
                    processed_bytes != confirmed_processed_bytes
                    or bytes_total != confirmed_bytes_total
                ):
                    raise ValueError(
                        "integrity progress changed during callback"
                    )
                if bytes_total < processed_bytes:
                    raise ValueError(
                        "integrity byte-total high-water cannot trail processed bytes"
                    )
                confirmed_processed_bytes = processed_bytes
                confirmed_bytes_total = bytes_total

            def revalidate_runner_authority_once() -> None:
                nonlocal full_reconciliation_attempted
                nonlocal full_reconciliation_error
                if full_reconciliation_attempted:
                    if full_reconciliation_error is not None:
                        raise full_reconciliation_error
                    return
                full_reconciliation_attempted = True
                try:
                    revalidate_integrity_selection_authority(
                        selection,
                        selection_authority,
                        allow_progress=True,
                    )
                except BaseException as error:
                    full_reconciliation_error = error
                    raise

            def reconcile_runner_completion(*, complete: bool) -> None:
                revalidate_runner_authority_once()
                reconcile_verification_edge(
                    allow_pending=False,
                    allow_progress=True,
                )
                if selection._completed_bytes != confirmed_completion_by_id:
                    raise ValueError(
                        "integrity completion changed after reconciliation"
                    )
                _validate_integrity_runner_completion(
                    selection,
                    observed_ids,
                    pending_by_id,
                    complete=complete,
                )

            reconcile_verification_edge(
                allow_pending=False,
                allow_progress=True,
            )
            try:
                ctx.emit(PhaseChanged(request.mode.value))
            finally:
                reconcile_verification_edge(
                    allow_pending=False,
                    allow_progress=False,
                )
            runner = deps.runners.get(request.mode)
            if runner is None:
                raise RuntimeError(
                    f"integrity runner is not configured: {request.mode.value}"
                )

            def observe_verification(body: object) -> None:
                nonlocal observed_recording, pending_completion_id
                if not isinstance(body, IntegrityOutcome):
                    reconcile_verification_edge(
                        allow_pending=False,
                        allow_progress=True,
                    )
                    try:
                        ctx.emit(body)
                    finally:
                        reconcile_verification_edge(
                            allow_pending=False,
                            allow_progress=False,
                        )
                    return
                reconcile_verification_edge(
                    allow_pending=False,
                    allow_progress=True,
                )
                item_id = body.item_id
                if type(item_id) is not str:
                    raise TypeError("integrity outcome item id must be text")
                if item_id in observed_ids:
                    raise ValueError("integrity runner emitted a duplicate outcome")
                candidate = pending_by_id.get(item_id)
                if candidate is None:
                    raise ValueError(
                        "integrity runner emitted an outcome outside its selection"
                    )
                snapshot = snapshot_integrity_outcome(
                    body,
                    item_id=candidate.item_id,
                    row_id=candidate.row_id,
                    location_id=candidate.location_id,
                    path=candidate.display_path,
                    phase=request.mode.value,
                )
                try:
                    ctx.emit(
                        snapshot_integrity_outcome(
                            snapshot,
                            item_id=snapshot.item_id,
                            row_id=snapshot.row_id,
                            location_id=snapshot.location_id,
                            path=snapshot.path,
                            phase=snapshot.phase,
                        )
                    )
                except BaseException:
                    reconcile_verification_edge(
                        allow_pending=False,
                        allow_progress=False,
                    )
                    raise
                observed_outcomes.append(snapshot)
                observed_ids.add(item_id)
                pending_by_id.pop(item_id)
                if snapshot.recording is RecordingStatus.DEGRADED:
                    observed_recording = RecordingStatus.DEGRADED
                # The outer sink has accepted the reliable item.  Keep that
                # prefix even when its callback changed custody state, but do
                # not mistake callback-written completion for module progress.
                reconcile_verification_edge(
                    allow_pending=False,
                    allow_progress=False,
                )
                pending_completion_id = item_id

            def checkpoint_verification() -> None:
                reconcile_verification_edge(
                    allow_pending=False,
                    allow_progress=True,
                )
                try:
                    ctx.checkpoint()
                finally:
                    reconcile_verification_edge(
                        allow_pending=False,
                        allow_progress=False,
                    )

            owned_run = RunContext(
                observe_verification,
                checkpoint_verification,
            )
            reconcile_verification_edge(
                allow_pending=False,
                allow_progress=True,
            )
            try:
                raw_verification_context = deps.verifier_context(owned_run)
            finally:
                reconcile_verification_edge(
                    allow_pending=False,
                    allow_progress=False,
                )
            verification_context = bind_verifier_context(
                raw_verification_context,
                owned_run,
                root_authority=RootAuthority(
                    logical_root=resolution.root_path,
                    reviewed_anchor=resolution.selected_mount,
                    expected_volume_id=resolution.binding.volume_id,
                ),
            )
            del raw_verification_context
            try:
                result = runner(selection, verification_context, recorder)
            except PauseRequested as error:
                try:
                    reconcile_runner_completion(complete=False)
                except Exception as reconciliation_error:
                    retire_exception_graph(error)
                    raise reconciliation_error
                raise
            except Canceled as error:
                try:
                    reconcile_runner_completion(complete=False)
                except Exception as reconciliation_error:
                    retire_exception_graph(error)
                    raise reconciliation_error
                raise
            except Exception as error:
                try:
                    revalidate_runner_authority_once()
                    reconcile_verification_edge(
                        allow_pending=True,
                        allow_progress=True,
                    )
                    if selection._completed_bytes != confirmed_completion_by_id:
                        raise ValueError(
                            "integrity completion changed after reconciliation"
                        )
                except Exception as reconciliation_error:
                    retire_exception_graph(error)
                    raise reconciliation_error
                raise
            try:
                aggregate_recording = validate_integrity_run_result(
                    result,
                    observed_outcomes,
                )
                reconcile_runner_completion(complete=True)
            except Exception:
                revalidate_runner_authority_once()
                raise
            finally:
                del result
    except PauseRequested:
        recording, recording_issues, omitted_detail_count = (
            _integrity_recording_truth(
                request,
                observed_recording,
                recorder_observation[0],
            )
        )
        if recording_sink is not None:
            recording_sink(
                recording,
                recording_issues,
                omitted_detail_count,
            )
        raise
    except Canceled:
        recording, recording_issues, omitted_detail_count = (
            _integrity_recording_truth(
                request,
                observed_recording,
                recorder_observation[0],
            )
        )
        if selection is None:
            return _integrity_request_terminal_result(
                request,
                SessionState.CANCELED,
                recording=recording,
                items=tuple(observed_outcomes),
                recording_issues=recording_issues,
                omitted_detail_count=omitted_detail_count,
                canceled=True,
            )
        return _integrity_terminal_result(
            selection,
            SessionState.CANCELED,
            recording=recording,
            items=tuple(observed_outcomes),
            recording_issues=recording_issues,
            omitted_detail_count=omitted_detail_count,
            canceled=True,
        )
    except Exception as error:
        recording, recording_issues, omitted_detail_count = (
            _integrity_recording_truth(
                request,
                observed_recording,
                recorder_observation[0],
            )
        )
        if (
            isinstance(error, IntegrityCandidateLimitError)
            and recorder_observation[0] is not None
        ):
            failure = recorder_observation[0].failure
        elif isinstance(error, IntegrityCandidateLimitError):
            failure = FailureDetail(
                type(error.fact).__name__,
                logical_error_text(error),
            )
        else:
            failure = FailureDetail(type(error).__name__, logical_error_text(error))
        retire_exception_graph(error)
        if selection is None:
            return _integrity_request_terminal_result(
                request,
                SessionState.FAILED,
                recording=recording,
                items=tuple(observed_outcomes),
                recording_issues=recording_issues,
                omitted_detail_count=omitted_detail_count,
                error=failure,
            )
        return _integrity_terminal_result(
            selection,
            SessionState.FAILED,
            recording=recording,
            items=tuple(observed_outcomes),
            recording_issues=recording_issues,
            omitted_detail_count=omitted_detail_count,
            error=failure,
        )

    recording, recording_issues, omitted_detail_count = _integrity_recording_truth(
        request,
        _integrity_recording(
            observed_recording,
            aggregate_recording,
            has_task_issue=False,
        ),
        recorder_observation[0],
    )
    return _integrity_terminal_result(
        selection,
        SessionState.COMPLETED,
        recording=recording,
        items=tuple(observed_outcomes),
        recording_issues=recording_issues,
        omitted_detail_count=omitted_detail_count,
    )


def settle_canceled_integrity(
    request: IntegrityWorkflowRequest,
    disposition: Disposition,
) -> OperationResult:
    """Settle one paused standalone integrity session without reopening work."""

    request = _exact_integrity_workflow_request(request)
    if disposition is not Disposition.RAN:
        raise ValueError("started integrity cancellation must retain RAN disposition")
    return OperationResult(
        SessionState.CANCELED,
        recording=request.recording,
        disposition=disposition,
        canceled=True,
        bytes_done=request.processed_bytes,
        bytes_total=request.bytes_total_high_water,
        recording_issues=request.recording_issues,
        omitted_detail_count=request.omitted_detail_count,
    )


@contextmanager
def _integrity_recorder(
    deps: IntegrityDependencies,
    root: str,
    *,
    recorder_observation: list[_ObservedTaskRecordingIssue | None],
) -> Iterator[LedgerRecorder]:
    """Close the ledger owner without replacing an in-flight primary signal."""

    try:
        recorder = LedgerRecorder(
            deps.ledger_path,
            clock=deps.clock,
            managed_roots=(root,),
        )
    except Exception as error:
        recorder_observation[0] = _task_recording_issue(
            TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
            error,
        )
        raise
    try:
        yield recorder
    except BaseException:
        try:
            recorder.close()
        except Exception as error:
            recorder_observation[0] = _task_recording_issue(
                TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
                error,
            )
        raise
    else:
        try:
            recorder.close()
        except Exception as error:
            recorder_observation[0] = _task_recording_issue(
                TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
                error,
            )
            raise


def _integrity_recording(
    *statuses: RecordingStatus,
    has_task_issue: bool,
) -> RecordingStatus:
    if has_task_issue or any(
        status is RecordingStatus.DEGRADED for status in statuses
    ):
        return RecordingStatus.DEGRADED
    return RecordingStatus.OK


def _integrity_terminal_result(
    selection: IntegritySelection,
    status: SessionState,
    *,
    recording: RecordingStatus,
    items: tuple[IntegrityOutcome, ...],
    recording_issues: tuple[TaskRecordingIssue, ...] = (),
    omitted_detail_count: int = 0,
    canceled: bool = False,
    error: FailureDetail | None = None,
) -> OperationResult:
    return OperationResult(
        status,
        recording=recording,
        disposition=Disposition.RAN,
        canceled=canceled,
        items=items,
        bytes_done=selection.processed_bytes,
        bytes_total=selection.bytes_total_high_water,
        error=error,
        recording_issues=recording_issues,
        omitted_detail_count=omitted_detail_count,
    )


def _integrity_request_terminal_result(
    request: IntegrityWorkflowRequest,
    status: SessionState,
    *,
    recording: RecordingStatus,
    items: tuple[IntegrityOutcome, ...],
    recording_issues: tuple[TaskRecordingIssue, ...] | None = None,
    omitted_detail_count: int | None = None,
    canceled: bool = False,
    error: FailureDetail | None = None,
) -> OperationResult:
    """Project truth available before the persisted selection is rebuilt."""

    return OperationResult(
        status,
        recording=recording,
        disposition=Disposition.RAN,
        canceled=canceled,
        items=items,
        bytes_done=request.processed_bytes,
        bytes_total=request.bytes_total_high_water,
        error=error,
        recording_issues=(
            request.recording_issues
            if recording_issues is None
            else recording_issues
        ),
        omitted_detail_count=(
            request.omitted_detail_count
            if omitted_detail_count is None
            else omitted_detail_count
        ),
    )


def _task_recording_issue(
    reason: TaskRecordingIssueReason,
    error: BaseException,
) -> _ObservedTaskRecordingIssue:
    type_name = type(error).__name__
    message = logical_error_text(error)
    raw_detail = f"{type_name}: {message}"
    detail = bounded_recording_detail(raw_detail)
    return _ObservedTaskRecordingIssue(
        TaskRecordingIssue(reason, detail),
        1 if detail is None else 0,
        FailureDetail(type_name, message),
    )


def _integrity_recording_truth(
    request: IntegrityWorkflowRequest,
    observed_recording: RecordingStatus,
    current: _ObservedTaskRecordingIssue | None,
) -> tuple[RecordingStatus, tuple[TaskRecordingIssue, ...], int]:
    current_issue = None if current is None else current.issue
    retains_current = current_issue is not None and not any(
        issue.reason is current_issue.reason
        for issue in request.recording_issues
    )
    recording_issues = _merge_recording_issues(
        request.recording_issues,
        current_issue,
    )
    omitted_detail_count = require_safe_int(
        request.omitted_detail_count
        + (
            current.omitted_detail_count
            if current is not None and retains_current
            else 0
        ),
        "integrity omitted_detail_count",
    )
    return (
        _integrity_recording(
            observed_recording,
            has_task_issue=bool(recording_issues),
        ),
        recording_issues,
        omitted_detail_count,
    )


def _merge_recording_issues(
    existing: tuple[TaskRecordingIssue, ...],
    current: TaskRecordingIssue | None,
) -> tuple[TaskRecordingIssue, ...]:
    if current is None or any(
        issue.reason is current.reason for issue in existing
    ):
        return existing
    return (*existing, current)


def change_inventory_visibility(
    command_id: str,
    location_id: int,
    row_id: str,
    action: InventoryVisibilityAction,
    *,
    ledger_path: Path,
    clock: Clock,
    changed_at: datetime | None = None,
) -> RecordDisposition:
    """Acknowledge or restore one missing row through the ledger owner."""

    at = clock.now() if changed_at is None else changed_at
    _require_utc(at, "inventory visibility change")
    with LedgerRecorder(ledger_path, clock=clock) as recorder:
        return recorder.change_inventory_visibility(
            InventoryVisibilityCommand(
                command_id,
                location_id,
                row_id,
                action,
                at,
            )
        )


def _charge_inventory_enum(
    counter: JsonEnvelopeCounter,
    value: object,
    enum_type: type[StrEnum],
    context: str,
) -> None:
    if type(value) is not enum_type:
        raise TypeError(f"{context} has the wrong enum type")
    counter.text(
        value.value,
        context,
        maximum_utf8_bytes=_enum_utf8_limit(enum_type),
    )


def _charge_inventory_path(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
    *,
    allow_root: bool = False,
) -> None:
    canonical = validate_relative_path(value, allow_root=allow_root)
    if canonical != value:
        raise ValueError(f"{context} is not canonical")
    counter.text(
        value,
        context,
        maximum_utf8_bytes=_PATH_UTF8_LIMIT,
    )


def _charge_location_binding(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not LocationBinding:
        raise TypeError(f"{context} must be LocationBinding")
    if type(value.volume_id) is not VolumeId:
        raise TypeError(f"{context}.volume_id must be VolumeId")
    require_utf16_text(
        value.volume_id.serial,
        f"{context}.volume.serial",
        maximum_units=MAX_VOLUME_TEXT_UTF16_UNITS,
        allow_empty=False,
    )
    require_utf16_text(
        value.volume_id.fs_type,
        f"{context}.volume.fs_type",
        maximum_units=MAX_VOLUME_TEXT_UTF16_UNITS,
        allow_empty=False,
    )
    if type(value.expected_mounts) is not tuple:
        raise TypeError(f"{context}.expected_mounts must be a tuple")
    if not value.expected_mounts:
        raise ValueError(f"{context}.expected_mounts cannot be empty")
    if len(value.expected_mounts) > MAX_MOUNT_CANDIDATES:
        raise ValueError(f"{context}.expected_mounts exceed the source limit")

    counter.object(_LOCATION_BINDING_LAYOUT)
    counter.object(_VOLUME_ID_LAYOUT)
    counter.text(
        value.volume_id.serial,
        f"{context}.volume.serial",
        maximum_utf8_bytes=_VOLUME_TEXT_UTF8_LIMIT,
        minimum_utf8_bytes=1,
    )
    counter.text(
        value.volume_id.fs_type,
        f"{context}.volume.fs_type",
        maximum_utf8_bytes=_VOLUME_TEXT_UTF8_LIMIT,
        minimum_utf8_bytes=1,
    )
    _charge_inventory_path(
        counter,
        value.volume_relative_path,
        f"{context}.volume_relative_path",
        allow_root=True,
    )
    require_utf16_path(value.selected_mount, f"{context}.selected_mount")
    if not value.selected_mount:
        raise ValueError(f"{context}.selected_mount cannot be empty")
    counter.text(
        value.selected_mount,
        f"{context}.selected_mount",
        maximum_utf8_bytes=_PATH_UTF8_LIMIT,
        minimum_utf8_bytes=1,
    )
    counter.array(len(value.expected_mounts))
    selected_key = _path_key(value.selected_mount)
    selected_seen = False
    for index, path in enumerate(value.expected_mounts):
        require_utf16_path(path, f"{context}.expected_mounts[{index}]")
        if not path:
            raise ValueError(f"{context}.expected_mounts cannot contain empty paths")
        path_key = _path_key(path)
        if any(
            _path_key(value.expected_mounts[prior_index]) == path_key
            for prior_index in range(index)
        ):
            raise ValueError(f"{context}.expected_mounts contain duplicates")
        selected_seen = selected_seen or path_key == selected_key
        counter.text(
            path,
            f"{context}.expected_mounts[{index}]",
            maximum_utf8_bytes=_PATH_UTF8_LIMIT,
            minimum_utf8_bytes=1,
        )
    if not selected_seen:
        raise ValueError(f"{context}.selected_mount is not an expected mount")
    counter.boolean(
        value.explicit_ambiguity_choice,
        f"{context}.explicit_ambiguity_choice",
    )
    if value.explicit_ambiguity_choice and len(value.expected_mounts) < 2:
        raise ValueError(f"{context}.explicit_ambiguity_choice requires ambiguity")
    if value.location_id is None:
        counter.null()
    else:
        require_safe_int(value.location_id, f"{context}.location_id")
        if value.location_id < 1:
            raise ValueError(f"{context}.location_id must be positive")
        counter.integer(value.location_id, f"{context}.location_id")


def _charge_inventory_paths(
    counter: JsonEnvelopeCounter,
    values: object,
    context: str,
    *,
    limit: int,
    allow_root: bool = False,
) -> None:
    if type(values) is not tuple:
        raise TypeError(f"{context} must be a tuple")
    if len(values) > limit:
        raise ValueError(f"{context} exceeds its source limit")
    counter.array(len(values))
    for index, path in enumerate(values):
        _charge_inventory_path(
            counter,
            path,
            f"{context}[{index}]",
            allow_root=allow_root,
        )


def _charge_inventory_workflow_request(
    request: object,
) -> JsonEnvelopeCounter:
    if type(request) is not InventoryWorkflowRequest:
        raise TypeError("inventory payload requires InventoryWorkflowRequest")
    if type(request.selected_paths) is not tuple:
        raise TypeError("inventory selected_paths must be a tuple")
    if type(request.subtree_roots) is not tuple:
        raise TypeError("inventory subtree_roots must be a tuple")
    if len(request.selected_paths) > SCAN_SCOPE_ENTRY_LIMIT - len(
        request.subtree_roots
    ):
        raise ValueError("inventory payload exceeds the scan-scope item limit")
    require_utf8_text(
        request.request_id,
        "inventory request id",
        minimum_bytes=1,
        maximum_bytes=MAX_REQUEST_ID_UTF8_BYTES,
    )
    counter = JsonEnvelopeCounter()
    counter.object(_INVENTORY_PAYLOAD_LAYOUT)
    counter.integer(2, "inventory version")
    counter.text("inventory", "inventory kind", maximum_utf8_bytes=len("inventory"))
    counter.text(
        request.request_id,
        "inventory request id",
        maximum_utf8_bytes=MAX_REQUEST_ID_UTF8_BYTES,
        minimum_utf8_bytes=1,
    )
    _charge_location_binding(counter, request.binding, "inventory.binding")
    _charge_inventory_paths(
        counter,
        request.selected_paths,
        "inventory.selected_paths",
        limit=SCAN_SCOPE_ENTRY_LIMIT,
    )
    _charge_inventory_paths(
        counter,
        request.subtree_roots,
        "inventory.subtree_roots",
        limit=SCAN_SCOPE_ENTRY_LIMIT,
        allow_root=True,
    )
    counter.require_within(
        _INVENTORY_MAX_OCCURRENCE_CHARGE,
        "inventory payload",
    )
    return counter


def _charge_integrity_item_id(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    _require_integrity_item_id(value, context)
    counter.text(
        value,
        context,
        maximum_utf8_bytes=_INTEGRITY_ITEM_ID_UTF8_LIMIT,
        minimum_utf8_bytes=1,
    )


def _charge_integrity_workflow_request(
    request: object,
) -> JsonEnvelopeCounter:
    if type(request) is not IntegrityWorkflowRequest:
        raise TypeError("integrity payload requires IntegrityWorkflowRequest")
    for field_name in ("selected_paths", "selection_item_ids", "completed_bytes"):
        population = getattr(request, field_name)
        if type(population) is not tuple:
            raise TypeError(f"integrity {field_name} must be a tuple")
        if len(population) > INTEGRITY_CANDIDATE_ROW_LIMIT:
            raise ValueError(f"integrity {field_name} exceeds its source limit")
    if len(request.completed_bytes) > len(request.selection_item_ids):
        raise ValueError("integrity completed_bytes exceed the saved selection")
    if type(request.recording_issues) is not tuple:
        raise TypeError("integrity recording_issues must be a tuple")
    if len(request.recording_issues) > _INTEGRITY_RECORDING_ISSUE_LIMIT:
        raise ValueError("integrity recording_issues exceed their source limit")
    require_utf8_text(
        request.request_id,
        "integrity request id",
        minimum_bytes=1,
        maximum_bytes=MAX_REQUEST_ID_UTF8_BYTES,
    )

    counter = JsonEnvelopeCounter()
    counter.object(_INTEGRITY_PAYLOAD_LAYOUT)
    counter.integer(2, "integrity version")
    counter.text("integrity", "integrity kind", maximum_utf8_bytes=len("integrity"))
    counter.text(
        request.request_id,
        "integrity request id",
        maximum_utf8_bytes=MAX_REQUEST_ID_UTF8_BYTES,
        minimum_utf8_bytes=1,
    )
    _charge_location_binding(counter, request.binding, "integrity.binding")
    _charge_inventory_enum(counter, request.mode, IntegrityMode, "integrity.mode")
    _charge_inventory_paths(
        counter,
        request.selected_paths,
        "integrity.selected_paths",
        limit=INTEGRITY_CANDIDATE_ROW_LIMIT,
    )
    if request.stale_before is None:
        counter.null()
    else:
        if type(request.stale_before) is not datetime:
            raise TypeError("integrity.stale_before must be datetime or None")
        _require_utc(request.stale_before, "integrity.stale_before")
        counter.text(
            request.stale_before.isoformat(),
            "integrity.stale_before",
            maximum_utf8_bytes=_TIMESTAMP_UTF8_LIMIT,
        )
    counter.array(len(request.selection_item_ids))
    for index, item_id in enumerate(request.selection_item_ids):
        _charge_integrity_item_id(
            counter,
            item_id,
            f"integrity.selection_item_ids[{index}]",
        )
    counter.array(len(request.completed_bytes))
    for index, entry in enumerate(request.completed_bytes):
        if type(entry) is not tuple or len(entry) != 2:
            raise TypeError("integrity completed_bytes entries must be pairs")
        item_id, size = entry
        counter.array(2)
        _charge_integrity_item_id(
            counter,
            item_id,
            f"integrity.completed_bytes[{index}].item_id",
        )
        require_signed_64(size, f"integrity.completed_bytes[{index}].bytes")
        counter.integer(size, f"integrity.completed_bytes[{index}].bytes")
    require_signed_64(request.processed_bytes, "integrity.processed_bytes")
    require_signed_64(
        request.bytes_total_high_water,
        "integrity.bytes_total_high_water",
    )
    counter.integer(request.processed_bytes, "integrity.processed_bytes")
    counter.integer(
        request.bytes_total_high_water,
        "integrity.bytes_total_high_water",
    )
    _charge_inventory_enum(
        counter,
        request.recording,
        RecordingStatus,
        "integrity.recording",
    )
    counter.array(len(request.recording_issues))
    for index, issue in enumerate(request.recording_issues):
        if type(issue) is not TaskRecordingIssue:
            raise TypeError("integrity recording_issues contain an invalid value")
        counter.object(_INTEGRITY_ISSUE_LAYOUT)
        _charge_inventory_enum(
            counter,
            issue.reason,
            TaskRecordingIssueReason,
            f"integrity.recording_issues[{index}].reason",
        )
        counter.optional_text(
            issue.detail,
            f"integrity.recording_issues[{index}].detail",
            maximum_utf8_bytes=MAX_DIAGNOSTIC_UTF8_BYTES,
        )
    require_safe_int(
        request.omitted_detail_count,
        "integrity.omitted_detail_count",
    )
    require_safe_int(
        request.refresh_generation,
        "integrity.refresh_generation",
    )
    counter.integer(
        request.omitted_detail_count,
        "integrity.omitted_detail_count",
    )
    counter.integer(request.refresh_generation, "integrity.refresh_generation")
    counter.require_within(
        _INTEGRITY_MAX_OCCURRENCE_CHARGE,
        "integrity payload",
    )
    return counter


def encode_inventory_request(request: InventoryWorkflowRequest) -> bytes:
    admission = _charge_inventory_workflow_request(request)
    admitted = _exact_inventory_workflow_request(request)
    if admitted != request:
        raise ValueError("inventory workflow request is not canonical")
    projection = {
            "version": 2,
            "kind": "inventory",
            "request_id": admitted.request_id,
            "binding": _binding_dict(admitted.binding),
            "selected_paths": list(admitted.selected_paths),
            "subtree_roots": list(admitted.subtree_roots),
        }
    return encode_canonical_json(
        projection,
        expected_bytes=admission.canonical_bytes,
        byte_ceiling=INVENTORY_PAYLOAD_BYTE_LIMIT,
        encoder=_json_bytes,
        context="inventory workflow payload",
    )


def decode_inventory_request(payload: bytes) -> InventoryWorkflowRequest:
    value = _payload(
        payload,
        "inventory",
        2,
        byte_ceiling=INVENTORY_PAYLOAD_BYTE_LIMIT,
    )
    _expect_keys(
        value,
        {
            "version",
            "kind",
            "request_id",
            "binding",
            "selected_paths",
            "subtree_roots",
        },
        "inventory payload",
    )
    selected_paths = _list(value["selected_paths"])
    subtree_roots = _list(value["subtree_roots"])
    if len(selected_paths) > SCAN_SCOPE_ENTRY_LIMIT - len(subtree_roots):
        raise ValueError("inventory payload exceeds the scan-scope item limit")
    return InventoryWorkflowRequest(
        _string(value["request_id"], "inventory.request_id"),
        _decode_binding(value["binding"]),
        tuple(
            _string(item, "inventory.selected_paths[]")
            for item in selected_paths
        ),
        tuple(
            _string(item, "inventory.subtree_roots[]")
            for item in subtree_roots
        ),
    )


def encode_integrity_request(request: IntegrityWorkflowRequest) -> bytes:
    admission = _charge_integrity_workflow_request(request)
    admitted = _exact_integrity_workflow_request(request)
    if admitted != request:
        raise ValueError("integrity workflow request is not canonical")
    projection = {
            "version": 2,
            "kind": "integrity",
            "request_id": admitted.request_id,
            "binding": _binding_dict(admitted.binding),
            "mode": admitted.mode.value,
            "selected_paths": list(admitted.selected_paths),
            "stale_before": (
                None
                if admitted.stale_before is None
                else admitted.stale_before.isoformat()
            ),
            "selection_item_ids": list(admitted.selection_item_ids),
            "completed_bytes": [list(item) for item in admitted.completed_bytes],
            "processed_bytes": admitted.processed_bytes,
            "bytes_total_high_water": admitted.bytes_total_high_water,
            "recording": admitted.recording.value,
            "recording_issues": [
                {"reason": issue.reason.value, "detail": issue.detail}
                for issue in admitted.recording_issues
            ],
            "omitted_detail_count": admitted.omitted_detail_count,
            "refresh_generation": admitted.refresh_generation,
        }
    return encode_canonical_json(
        projection,
        expected_bytes=admission.canonical_bytes,
        byte_ceiling=INTEGRITY_PAYLOAD_BYTE_LIMIT,
        encoder=_json_bytes,
        context="integrity workflow payload",
    )


def decode_integrity_request(payload: bytes) -> IntegrityWorkflowRequest:
    value = _payload(
        payload,
        "integrity",
        2,
        byte_ceiling=INTEGRITY_PAYLOAD_BYTE_LIMIT,
    )
    _expect_keys(
        value,
        {
            "version",
            "kind",
            "request_id",
            "binding",
            "mode",
            "selected_paths",
            "stale_before",
            "selection_item_ids",
            "completed_bytes",
            "processed_bytes",
            "bytes_total_high_water",
            "recording",
            "recording_issues",
            "omitted_detail_count",
            "refresh_generation",
        },
        "integrity payload",
    )
    stale = value["stale_before"]
    selected_paths = _list(value["selected_paths"])
    selection_item_ids = _list(value["selection_item_ids"])
    raw_completed_bytes = _list(value["completed_bytes"])
    raw_recording_issues = _list(value["recording_issues"])
    for population, context, limit in (
        (selected_paths, "integrity.selected_paths", INTEGRITY_CANDIDATE_ROW_LIMIT),
        (
            selection_item_ids,
            "integrity.selection_item_ids",
            INTEGRITY_CANDIDATE_ROW_LIMIT,
        ),
        (
            raw_completed_bytes,
            "integrity.completed_bytes",
            INTEGRITY_CANDIDATE_ROW_LIMIT,
        ),
        (raw_recording_issues, "integrity.recording_issues", 5),
    ):
        if len(population) > limit:
            raise ValueError(f"{context} exceeds its item limit")
    completed_bytes: list[tuple[str, int]] = []
    for raw in raw_completed_bytes:
        item = _list(raw)
        if len(item) != 2:
            raise ValueError(
                "integrity.completed_bytes[] must contain an id and byte count"
            )
        completed_bytes.append(
            (
                _string(item[0], "integrity.completed_bytes[].item_id"),
                _integer(item[1], "integrity.completed_bytes[].bytes"),
            )
        )
    return IntegrityWorkflowRequest(
        request_id=_string(value["request_id"], "integrity.request_id"),
        binding=_decode_binding(value["binding"]),
        mode=IntegrityMode(_string(value["mode"], "integrity.mode")),
        selected_paths=tuple(
            _string(item, "integrity.selected_paths[]")
            for item in selected_paths
        ),
        stale_before=(
            None
            if stale is None
            else datetime.fromisoformat(
                _string(stale, "integrity.stale_before")
            )
        ),
        selection_item_ids=tuple(
            _string(item, "integrity.selection_item_ids[]")
            for item in selection_item_ids
        ),
        completed_bytes=tuple(completed_bytes),
        processed_bytes=_integer(
            value["processed_bytes"],
            "integrity.processed_bytes",
        ),
        bytes_total_high_water=_integer(
            value["bytes_total_high_water"],
            "integrity.bytes_total_high_water",
        ),
        recording=RecordingStatus(
            _string(value["recording"], "integrity.recording")
        ),
        recording_issues=tuple(
            _decode_integrity_recording_issue(issue, index)
            for index, issue in enumerate(raw_recording_issues)
        ),
        omitted_detail_count=_integer(
            value["omitted_detail_count"],
            "integrity.omitted_detail_count",
        ),
        refresh_generation=_integer(
            value["refresh_generation"],
            "integrity.refresh_generation",
        ),
    )


def _bind_request_location(
    root_path: str | None,
    location_id: int | None,
    selected_mount: str | None,
    *,
    ledger_path: Path,
    backend: VolumeBindingBackend,
    resolver: MountedVolumeResolver,
) -> LocationBinding:
    if location_id is not None:
        with LedgerRepository(ledger_path) as repository:
            location = repository.get_location(location_id)
        return _binding_from_location(location, selected_mount, resolver)
    if root_path is None:
        raise RuntimeError("validated root-path request lost its path")
    resolved = backend.resolve_root(root_path)
    require_utf16_path(resolved, "resolved root path")
    snapshot = validate_volume_snapshot(backend.volume_snapshot(resolved))
    mount = snapshot.evidence.device_id or Path(resolved).anchor
    relative = _relative_to_mount(resolved, mount)
    return _binding_from_identity(
        snapshot.volume_id,
        relative,
        mount,
        selected_mount,
        None,
        resolver,
    )


def _binding_from_location(
    location: LocationSnapshot,
    selected_mount: str | None,
    resolver: MountedVolumeResolver,
) -> LocationBinding:
    return _binding_from_identity(
        location.volume_id,
        location.volume_relative_path,
        location.mount_hint,
        selected_mount,
        location.location_id,
        resolver,
    )


def _binding_from_identity(
    volume_id: VolumeId,
    relative: str,
    mount_hint: str | None,
    selected_mount: str | None,
    location_id: int | None,
    resolver: MountedVolumeResolver,
) -> LocationBinding:
    if type(volume_id) is not VolumeId:
        raise TypeError("volume binding requires VolumeId")
    volume_id = VolumeId(volume_id.serial, volume_id.fs_type)
    if mount_hint is not None:
        require_utf16_path(mount_hint, "persisted mount hint")
    if selected_mount is not None:
        require_utf16_path(selected_mount, "selected volume mount")
    hints = () if mount_hint is None else (mount_hint,)
    mounted = _mounted_volume_snapshot(resolver, volume_id, hints)
    candidates = tuple(item.mount_path for item in mounted)
    del mounted
    if not candidates:
        unresolved_mount = mount_hint or "<unmounted>"
        provisional = LocationBinding(
            volume_id,
            relative,
            unresolved_mount,
            (unresolved_mount,),
            False,
            location_id,
        )
        raise VolumeResolutionRequired(
            VolumeResolution(
                VolumeResolutionState.OFFLINE,
                provisional,
                candidates=(),
                detail="recorded volume is not mounted",
            )
        )
    explicit = len(candidates) > 1
    if explicit and selected_mount is None:
        provisional = LocationBinding(
            volume_id, relative, candidates[0], candidates, False, location_id
        )
        raise VolumeResolutionRequired(
            VolumeResolution(
                VolumeResolutionState.AMBIGUOUS,
                provisional,
                candidates=candidates,
                detail="choose one mounted clone before submission",
            )
        )
    chosen = selected_mount or candidates[0]
    if _path_key(chosen) not in {_path_key(path) for path in candidates}:
        raise ValueError("selected volume mount is not a current candidate")
    binding = LocationBinding(
        volume_id,
        relative,
        chosen,
        candidates,
        explicit,
        location_id,
    )
    resolution = resolve_binding(binding, resolver)
    if resolution.state != VolumeResolutionState.RESOLVED:
        raise VolumeResolutionRequired(resolution)
    return resolution.binding


def _require_inventory_scan_count(count: object, field_name: str) -> int:
    if type(count) is not int:
        raise TypeError(f"{field_name} must be a non-Boolean integer")
    if count < 0:
        raise ValueError(f"{field_name} must be nonnegative")
    return count


def _consume_inventory_review_limit(
    error: ReviewFactLimitError,
    admission: _InventoryScanAdmission,
) -> ReviewFactLimitExceeded | None:
    issuer = error.__dict__.pop("_inventory_review_issuer", None)
    fact = snapshot_review_fact_limit(error.fact)
    if (
        fact.tree_kind is not ReviewTreeKind.INVENTORY
        or fact.axis is not ReviewLimitAxis.ROWS
    ):
        raise ValueError("inventory review limit fact has the wrong scope")
    return fact if issuer is admission._issuer else None


def _admit_inventory_scan_result(
    value: object,
    admission: _InventoryScanAdmission,
) -> ScanResult:
    """Revalidate hostile scanner populations before any ledger publication."""

    return snapshot_scan_result(
        value,
        admission,
        row_limit=MAX_PLAN_REVIEW_ROWS,
    )


def _register_and_scan(
    request_id: str,
    scope_token: str,
    binding: LocationBinding,
    resolution: VolumeResolution,
    selected_paths: tuple[str, ...],
    subtree_roots: tuple[str, ...],
    ctx: RunContext,
    deps: InventoryDependencies,
    recorder: LedgerRecorder,
    review_admission: _InventoryScanAdmission,
) -> tuple[int, int, ScanResult]:
    if (
        resolution.root_path is None
        or resolution.selected_mount is None
        or resolution.evidence is None
    ):
        raise RuntimeError("resolved inventory root lacks volume evidence")
    if type(binding.volume_id) is not VolumeId:
        raise TypeError("inventory binding volume has the wrong type")
    if type(resolution.evidence) is not VolumeEvidence:
        raise TypeError("inventory resolution evidence has the wrong type")
    expected_volume_id = VolumeId(
        binding.volume_id.serial,
        binding.volume_id.fs_type,
    )
    expected_evidence = VolumeEvidence(
        resolution.evidence.label,
        resolution.evidence.device_id,
        resolution.evidence.clone_ambiguous,
    )
    root_path = require_utf16_path(
        resolution.root_path,
        "resolved inventory root",
    )
    selected_mount = require_utf16_path(
        resolution.selected_mount,
        "resolved inventory mount",
    )
    volume_relative_path = validate_relative_path(
        binding.volume_relative_path,
        allow_root=True,
    )
    if volume_relative_path != binding.volume_relative_path:
        raise ValueError("inventory binding relative path is not canonical")
    expected_location_id = binding.location_id
    if expected_location_id is not None:
        require_safe_int(expected_location_id, "inventory location id")
        if expected_location_id < 1:
            raise ValueError("inventory location id must be positive")
    if type(deps.host_key) is not str or type(deps.host_name) is not str:
        raise TypeError("inventory host facts must be exact strings")
    host_key = deps.host_key
    host_name = deps.host_name
    scanner = deps.scanner
    clock = deps.clock
    expected_scope = ScanScope.scoped(
        selected_paths=selected_paths,
        subtree_roots=subtree_roots,
    )
    expected_root = Root(root_path, f"inventory:{scope_token}")
    scanner_root = Root(expected_root.path, expected_root.root_id)
    scanner_scope = ScanScope(
        expected_scope.kind,
        expected_scope.selected_paths,
        expected_scope.subtree_roots,
    )
    scanner_ignores = snapshot_ignore_set(deps.ignores)
    ctx.emit(PhaseChanged("inventory"))
    raw_scan = scanner(
        scanner_root,
        scanner_ignores,
        ctx,
        scanner_scope,
        trusted_anchor=selected_mount,
        population_admission=review_admission,
    )
    scan = _admit_inventory_scan_result(raw_scan, review_admission)
    if scan.root != expected_root:
        raise RuntimeError("inventory scanner returned a different root")
    if scan.scope != expected_scope:
        raise RuntimeError("inventory scanner returned a different scope")
    if scan.volume_id != expected_volume_id:
        raise RuntimeError("inventory scan volume changed after preflight")
    now = clock.now()
    host_id = recorder.ensure_host(HostCommand(host_key, host_name, now))
    volume_row = recorder.observe_volume(
        VolumeCommand(expected_volume_id, expected_evidence, now)
    )
    location_id = recorder.ensure_location(
        LocationCommand(volume_row, volume_relative_path, now)
    )
    if expected_location_id is not None and expected_location_id != location_id:
        raise RuntimeError("resolved location identity changed")
    return host_id, location_id, scan


def _integrity_rows(
    repository: LedgerRepository,
    location_id: int,
    mode: IntegrityMode,
    selected_paths: tuple[str, ...],
    stale_before: datetime | None,
    selection_item_ids: tuple[str, ...],
    completed_item_ids: frozenset[str],
) -> tuple[InventorySnapshot, ...]:
    if selection_item_ids:
        row_ids = _saved_inventory_row_ids(location_id, selection_item_ids)
        return repository.get_integrity_candidates(
            location_id,
            mode,
            saved_row_ids=row_ids,
        )
    if selected_paths:
        return repository.get_integrity_candidates(
            location_id,
            mode,
            path_keys=selected_paths,
        )
    if stale_before is not None:
        completed_row_ids = _saved_inventory_row_ids(
            location_id,
            tuple(completed_item_ids),
        )
        return repository.get_integrity_candidates(
            location_id,
            mode,
            stale_before=stale_before,
            completed_row_ids=completed_row_ids,
        )
    return repository.get_integrity_candidates(location_id, mode)


def _saved_inventory_row_ids(
    location_id: int, item_ids: tuple[str, ...]
) -> tuple[str, ...]:
    prefix = f"{location_id}:"
    row_ids = tuple(
        item_id[len(prefix) :] for item_id in item_ids if item_id.startswith(prefix)
    )
    if len(row_ids) != len(item_ids):
        raise RuntimeError(
            "saved integrity selection references another inventory location"
        )
    return row_ids


def _integrity_selection(
    request: IntegrityWorkflowRequest,
    rows: tuple[InventorySnapshot, ...],
    root: str,
) -> IntegritySelection:
    completed = dict(request.completed_bytes)
    shared_root = Path(root)

    def owned_item(row: InventorySnapshot) -> IntegritySelectionItem:
        return IntegritySelectionItem(
            item_id=f"{row.location_id}:{row.row_id}",
            row_id=row.row_id,
            location_id=str(row.location_id),
            root=shared_root,
            rel_path_key=row.rel_path_key,
            display_path=row.rel_path,
            expected_state=InventoryState(row.presence.value),
            expected_stat=(
                None if row.observed is None else snapshot_file_stat(row.observed)
            ),
            baseline=(
                None if row.attestation is None else snapshot_attestation(row.attestation)
            ),
            scope_token=row.scope_token,
            reappeared_at=(
                None
                if row.reappeared_at is None
                else datetime.fromisoformat(row.reappeared_at.isoformat())
            ),
            invalidation=(
                None
                if row.invalidation is None
                else VerificationInvalidation(
                    datetime.fromisoformat(row.invalidation.at.isoformat()),
                    row.invalidation.reason,
                )
            ),
        )

    items = tuple(
        owned_item(row)
        for row in rows
    )
    pending_admission = request.processed_bytes
    for item in items:
        if (
            item.item_id not in completed
            and item.expected_state is InventoryState.PRESENT
            and item.expected_stat is not None
        ):
            pending_admission = checked_add_signed_64(
                pending_admission,
                item.expected_stat.size,
                "integrity admitted bytes",
            )
    return IntegritySelection(
        items=items,
        _completed_bytes=completed,
        _processed_bytes=request.processed_bytes,
        _bytes_total_high_water=max(
            request.bytes_total_high_water,
            pending_admission,
        ),
    )


def _validate_integrity_runner_completion(
    selection: IntegritySelection,
    observed_ids: set[str],
    pending_by_id: dict[str, IntegritySelectionItemFact],
    *,
    complete: bool,
) -> None:
    """Require verifier completion to match accepted item truth."""

    if frozenset(selection._completed_bytes) != frozenset(observed_ids):
        raise ValueError(
            "integrity runner completion must match its emitted outcomes"
        )
    if complete and pending_by_id:
        raise ValueError("integrity runner returned with pending candidates")


def _require_integrity_candidate_rows(
    rows: object,
) -> tuple[InventorySnapshot, ...]:
    if type(rows) is not tuple:
        raise TypeError("integrity candidate rows must be an exact tuple")
    if any(type(row) is not InventorySnapshot for row in rows):
        raise TypeError(
            "integrity candidate rows must contain exact inventory snapshots"
        )
    if len(rows) > INTEGRITY_CANDIDATE_ROW_LIMIT:
        raise IntegrityCandidateLimitError(
            IntegrityCandidateLimitExceeded.rows()
        )
    return rows


def _decode_integrity_recording_issue(
    value: object,
    index: int,
) -> TaskRecordingIssue:
    context = f"integrity.recording_issues[{index}]"
    item = _mapping(value)
    _expect_keys(item, {"reason", "detail"}, context)
    raw_detail = item["detail"]
    return TaskRecordingIssue(
        TaskRecordingIssueReason(_string(item["reason"], f"{context}.reason")),
        None if raw_detail is None else _string(raw_detail, f"{context}.detail"),
    )


def _subject_local_incompleteness(scan: ScanResult) -> bool:
    """Return whether exact frozen subjects fully explain incompleteness."""

    if scan.scope.kind is not ScanScopeKind.PATHS or not scan.unsupported:
        return False
    selected_keys = {
        normalize_relative_path(path)
        for path in scan.scope.selected_paths
    }
    observed_keys = {
        record.rel_path_key
        for record in (
            *scan.files,
            *scan.directories,
            *scan.unsupported,
        )
    }
    warning_keys = {
        normalize_relative_path(warning.rel_path)
        for warning in scan.warnings
        if warning.rel_path is not None
    }
    unsupported_keys = {
        record.rel_path_key for record in scan.unsupported
    }
    disappeared_keys = {
        normalize_relative_path(warning.rel_path)
        for warning in scan.warnings
        if (
            warning.rel_path is not None
            and warning.code is ScanWarningCode.DISAPPEARED
        )
    }
    if any(
        warning.rel_path is None
        or normalize_relative_path(warning.rel_path) not in selected_keys
        for warning in scan.warnings
    ):
        return False
    if not unsupported_keys <= warning_keys:
        return False
    return selected_keys <= observed_keys | disappeared_keys


def _refused_resolution(resolution: VolumeResolution) -> OperationResult:
    return OperationResult(
        SessionState.REFUSED,
        disposition=Disposition.UNRUN,
        error=FailureDetail(
            "VolumeResolution",
            resolution.state
            if resolution.detail is None
            else f"{resolution.state}: {resolution.detail}",
        ),
    )


def _binding_dict(binding: LocationBinding) -> dict[str, object]:
    if type(binding) is not LocationBinding:
        raise TypeError("location binding projection requires LocationBinding")
    _require_location_binding_fields(binding)
    return {
        "volume": {
            "serial": binding.volume_id.serial,
            "fs_type": binding.volume_id.fs_type,
        },
        "volume_relative_path": binding.volume_relative_path,
        "selected_mount": binding.selected_mount,
        "expected_mounts": list(binding.expected_mounts),
        "explicit_ambiguity_choice": binding.explicit_ambiguity_choice,
        "location_id": binding.location_id,
    }


def _decode_binding(value: object) -> LocationBinding:
    data = _mapping(value)
    _expect_keys(
        data,
        {
            "volume",
            "volume_relative_path",
            "selected_mount",
            "expected_mounts",
            "explicit_ambiguity_choice",
            "location_id",
        },
        "location binding",
    )
    volume = _mapping(data["volume"])
    _expect_keys(volume, {"serial", "fs_type"}, "location binding volume")
    raw_expected_mounts = _list(data["expected_mounts"])
    if len(raw_expected_mounts) > MAX_MOUNT_CANDIDATES:
        raise ValueError("location binding exceeds the mount-candidate limit")
    return LocationBinding(
        VolumeId(
            _string(volume["serial"], "location binding volume.serial"),
            _string(volume["fs_type"], "location binding volume.fs_type"),
        ),
        _string(
            data["volume_relative_path"],
            "location binding.volume_relative_path",
        ),
        _string(data["selected_mount"], "location binding.selected_mount"),
        tuple(
            _string(item, "location binding.expected_mounts[]")
            for item in raw_expected_mounts
        ),
        _boolean(
            data["explicit_ambiguity_choice"],
            "location binding.explicit_ambiguity_choice",
        ),
        (
            None
            if data["location_id"] is None
            else _integer(data["location_id"], "location binding.location_id")
        ),
    )


def _payload(
    payload: bytes,
    expected_kind: str,
    expected_version: int,
    *,
    byte_ceiling: int,
) -> Mapping[str, object]:
    payload = require_payload_bytes(
        payload,
        byte_ceiling=byte_ceiling,
        context=f"{expected_kind} workflow payload",
    )
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(
            "inventory workflow payload is not valid UTF-8 JSON"
        ) from error
    require_json_unicode(value)
    data = _mapping(value)
    version = data.get("version")
    if (
        type(version) is not int
        or version != expected_version
        or data.get("kind") != expected_kind
    ):
        raise ValueError("unsupported inventory workflow payload")
    return data


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", errors="strict")


def _mapping(value: object) -> Mapping[str, object]:
    if type(value) is not dict or not all(
        type(key) is str for key in value
    ):
        raise ValueError("workflow payload value must be an object")
    return value


def _list(value: object) -> list[object]:
    if type(value) is not list:
        raise ValueError("workflow payload value must be a list")
    return value


def _unique_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(
                f"inventory workflow payload contains duplicate key: {key}"
            )
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON number: {value}")


def _expect_keys(
    value: Mapping[str, object],
    expected: set[str],
    context: str,
) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} has missing or unknown fields")


def _string(value: object, context: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{context} must be a string")
    return value


def _integer(value: object, context: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{context} must be an integer")
    return value


def _boolean(value: object, context: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{context} must be a boolean")
    return value


def _validate_location_request(
    request_id: str, root_path: str | None, location_id: int | None
) -> None:
    require_utf8_text(
        request_id,
        "request id",
        minimum_bytes=1,
        maximum_bytes=MAX_REQUEST_ID_UTF8_BYTES,
    )
    if (root_path is None) == (location_id is None):
        raise ValueError("request requires exactly one root path or location id")
    if root_path is not None:
        require_utf16_path(root_path, "root path")
        if not root_path:
            raise ValueError("root path cannot be empty")
    if location_id is not None:
        require_safe_int(location_id, "location id")
        if location_id < 1:
            raise ValueError("location id must be positive")


def _require_workflow_request(
    request_id: object,
    binding: object,
) -> None:
    require_utf8_text(
        request_id,
        "request id",
        minimum_bytes=1,
        maximum_bytes=MAX_REQUEST_ID_UTF8_BYTES,
    )
    if type(binding) is not LocationBinding:
        raise TypeError("workflow request binding has the wrong type")
    _require_location_binding_fields(binding)


def _relative_to_mount(path: str, mount: str) -> str:
    relative = os.path.relpath(path, mount)
    if relative == ".":
        return ""
    if relative == ".." or relative.startswith(".." + os.sep):
        raise ValueError("managed root is outside its observed volume mount")
    return relative.replace(os.sep, "\\")


def _join_volume_root(mount: str, relative: str) -> str:
    if not relative:
        return mount
    return os.path.join(mount, *relative.split("\\"))


def _path_key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)).rstrip("\\/")


def _logical_drive_roots() -> tuple[str, ...]:
    if os.name != "nt":
        return ()
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = ctypes.create_unicode_buffer(_MAX_LOGICAL_DRIVE_STRING_CHARS)
    length = kernel32.GetLogicalDriveStringsW(len(buffer), buffer)
    if length <= 0:
        raise OSError(ctypes.get_last_error(), "GetLogicalDriveStringsW failed")
    if length >= len(buffer):
        raise OSError("logical-drive enumeration exceeded its fixed source bound")
    roots = tuple(value for value in buffer[:length].split("\x00") if value)
    if len(roots) > _MAX_LOGICAL_DRIVE_ROOTS:
        raise OSError("logical-drive enumeration exceeded its fixed source bound")
    for root in roots:
        require_utf16_path(root, "logical drive root")
    return roots


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field_name} must be UTC")


def _missing_verifier_context() -> VerifierContext:
    raise RuntimeError("verifier context factory is required")
