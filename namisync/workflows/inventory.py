"""Location inventory and standalone integrity workflow coordination."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Callable, Iterator, Mapping, Protocol

from namisync.core.events import PhaseChanged
from namisync.core.evidence import RecordingStatus
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
    IntegritySelectionItem,
    InventoryState,
    RecordDisposition,
    VerifierContext,
)
from namisync.core.models import (
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
    validate_scan_result,
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
from namisync.core.scalars import (
    MAX_DIAGNOSTIC_UTF8_BYTES,
    MAX_REQUEST_ID_UTF8_BYTES,
    bounded_utf8_text,
    checked_add_signed_64,
    require_json_unicode,
    require_safe_int,
    require_signed_64,
    require_utf16_path,
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


def _require_mounted_volumes(value: object) -> tuple[MountedVolume, ...]:
    if type(value) is not tuple:
        raise TypeError("mounted-volume result must be a tuple")
    if len(value) > MAX_VOLUME_RESOLUTION_CANDIDATES:
        raise ValueError("mounted-volume result exceeds the candidate limit")
    keys: set[str] = set()
    for item in value:
        if type(item) is not MountedVolume:
            raise TypeError("mounted-volume result contains an invalid value")
        _require_mounted_volume_fields(item)
        key = _path_key(item.mount_path)
        if key in keys:
            raise ValueError("mounted-volume result contains duplicate paths")
        keys.add(key)
    return value


class MountedVolumeResolver(Protocol):
    def mounted_volumes(
        self, volume_id: VolumeId, hints: tuple[str, ...] = ()
    ) -> tuple[MountedVolume, ...]: ...

    def probe_root(self, root_path: str) -> None: ...


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
            if not isinstance(item_id, str) or not item_id:
                raise ValueError("integrity selection item ids are required")
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
            if not isinstance(item_id, str) or not item_id:
                raise ValueError("completed integrity item ids are required")
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


class Scanner(Protocol):
    def __call__(
        self,
        root: Root,
        ignores: IgnoreSet,
        context: RunContext,
        scope: ScanScope | None,
        *,
        trusted_anchor: str | None = None,
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
    if type(binding) is not LocationBinding:
        raise TypeError("volume resolution requires LocationBinding")
    _require_location_binding_fields(binding)
    mounted = _require_mounted_volumes(
        resolver.mounted_volumes(
            binding.volume_id, hints=binding.expected_mounts
        )
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
    with LedgerRecorder(
        deps.ledger_path, clock=deps.clock, managed_roots=(root,)
    ) as recorder:
        host_id, location_id, scan = _register_and_scan(
            request.request_id,
            scope_token,
            request.binding,
            resolution,
            request.selected_paths,
            request.subtree_roots,
            ctx,
            deps,
            recorder,
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
                request.binding,
                resolution,
                request.selected_paths,
                (),
                ctx,
                deps,
                recorder,
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
            selection = _integrity_selection(request, rows, root)
            if selection_sink is not None:
                selection_sink(selection)
            ctx.emit(PhaseChanged(request.mode.value))
            runner = deps.runners.get(request.mode)
            if runner is None:
                raise RuntimeError(
                    f"integrity runner is not configured: {request.mode.value}"
                )

            def observe_verification(body: object) -> None:
                nonlocal observed_recording
                ctx.emit(body)
                if not isinstance(body, IntegrityOutcome):
                    return
                observed_outcomes.append(body)
                if body.recording is RecordingStatus.DEGRADED:
                    observed_recording = RecordingStatus.DEGRADED

            verification_context = replace(
                deps.verifier_context(
                    RunContext(observe_verification, ctx.checkpoint)
                ),
                root_authority=RootAuthority(
                    logical_root=resolution.root_path,
                    reviewed_anchor=resolution.selected_mount,
                    expected_volume_id=request.binding.volume_id,
                ),
            )
            result = runner(selection, verification_context, recorder)
            if not isinstance(result, IntegrityRunResult):
                raise TypeError("integrity runner must return IntegrityRunResult")
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
        _integrity_recording(observed_recording, result.recording, has_task_issue=False),
        recorder_observation[0],
    )
    return _integrity_terminal_result(
        selection,
        SessionState.COMPLETED,
        recording=recording,
        items=result.outcomes,
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


def encode_inventory_request(request: InventoryWorkflowRequest) -> bytes:
    request = _exact_inventory_workflow_request(request)
    return _json_bytes(
        {
            "version": 2,
            "kind": "inventory",
            "request_id": request.request_id,
            "binding": _binding_dict(request.binding),
            "selected_paths": list(request.selected_paths),
            "subtree_roots": list(request.subtree_roots),
        }
    )


def decode_inventory_request(payload: bytes) -> InventoryWorkflowRequest:
    value = _payload(payload, "inventory", 2)
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
    request = _exact_integrity_workflow_request(request)
    return _json_bytes(
        {
            "version": 2,
            "kind": "integrity",
            "request_id": request.request_id,
            "binding": _binding_dict(request.binding),
            "mode": request.mode.value,
            "selected_paths": list(request.selected_paths),
            "stale_before": (
                None
                if request.stale_before is None
                else request.stale_before.isoformat()
            ),
            "selection_item_ids": list(request.selection_item_ids),
            "completed_bytes": [list(item) for item in request.completed_bytes],
            "processed_bytes": request.processed_bytes,
            "bytes_total_high_water": request.bytes_total_high_water,
            "recording": request.recording.value,
            "recording_issues": [
                {"reason": issue.reason.value, "detail": issue.detail}
                for issue in request.recording_issues
            ],
            "omitted_detail_count": request.omitted_detail_count,
            "refresh_generation": request.refresh_generation,
        }
    )


def decode_integrity_request(payload: bytes) -> IntegrityWorkflowRequest:
    value = _payload(payload, "integrity", 2)
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
    if mount_hint is not None:
        require_utf16_path(mount_hint, "persisted mount hint")
    if selected_mount is not None:
        require_utf16_path(selected_mount, "selected volume mount")
    hints = () if mount_hint is None else (mount_hint,)
    mounted = _require_mounted_volumes(
        resolver.mounted_volumes(volume_id, hints)
    )
    candidates = tuple(item.mount_path for item in mounted)
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
    return binding


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
) -> tuple[int, int, ScanResult]:
    if resolution.root_path is None or resolution.evidence is None:
        raise RuntimeError("resolved inventory root lacks volume evidence")
    scope = ScanScope.scoped(
        selected_paths=selected_paths,
        subtree_roots=subtree_roots,
    )
    root = Root(resolution.root_path, f"inventory:{scope_token}")
    ctx.emit(PhaseChanged("inventory"))
    scan = validate_scan_result(
        deps.scanner(
            root,
            deps.ignores,
            ctx,
            scope,
            trusted_anchor=resolution.selected_mount,
        )
    )
    if scan.root != root:
        raise RuntimeError("inventory scanner returned a different root")
    if scan.scope != scope:
        raise RuntimeError("inventory scanner returned a different scope")
    if scan.volume_id != binding.volume_id:
        raise RuntimeError("inventory scan volume changed after preflight")
    now = deps.clock.now()
    host_id = recorder.ensure_host(
        HostCommand(deps.host_key, deps.host_name, now)
    )
    volume_row = recorder.observe_volume(
        VolumeCommand(binding.volume_id, resolution.evidence, now)
    )
    location_id = recorder.ensure_location(
        LocationCommand(volume_row, binding.volume_relative_path, now)
    )
    if binding.location_id is not None and binding.location_id != location_id:
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
    items = tuple(
        IntegritySelectionItem(
            item_id=f"{row.location_id}:{row.row_id}",
            row_id=row.row_id,
            location_id=str(row.location_id),
            root=shared_root,
            rel_path_key=row.rel_path_key,
            display_path=row.rel_path,
            expected_state=InventoryState(row.presence.value),
            expected_stat=row.observed,
            baseline=row.attestation,
            scope_token=row.scope_token,
            reappeared_at=row.reappeared_at,
            invalidation=row.invalidation,
        )
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
) -> Mapping[str, object]:
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
