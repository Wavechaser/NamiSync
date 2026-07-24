"""Location inventory and standalone integrity workflow coordination."""

from __future__ import annotations

import json
import os
import stat as stat_module
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Callable, Mapping, Protocol

from namisync.core.events import PhaseChanged
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityRunResult,
    IntegritySelection,
    IntegritySelectionItem,
    InventoryState,
    RecordDisposition,
    VerifierContext,
)
from namisync.core.models import (
    IgnoreSet,
    Root,
    ScanResult,
    ScanScope,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import (
    to_extended_length_path,
    validate_relative_path,
)
from namisync.core.planning import FilterSet
from namisync.core.recording import (
    HostCommand,
    InventoryCommand,
    InventoryVisibilityAction,
    InventoryVisibilityCommand,
    LocationCommand,
    MappingFilterCommand,
    MappingFilterEvaluation,
    VolumeCommand,
)
from namisync.core.session import (
    Disposition,
    FailureDetail,
    OperationResult,
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
        canonical = validate_relative_path(
            self.volume_relative_path, allow_root=True
        )
        object.__setattr__(self, "volume_relative_path", canonical)
        if not self.selected_mount or not self.expected_mounts:
            raise ValueError("location binding requires a selected mounted volume")
        expected_keys = tuple(_path_key(path) for path in self.expected_mounts)
        if len(expected_keys) != len(set(expected_keys)):
            raise ValueError("location binding mount candidates must be unique")
        if _path_key(self.selected_mount) not in set(expected_keys):
            raise ValueError("selected mount must be one of the expected candidates")
        if self.explicit_ambiguity_choice and len(self.expected_mounts) < 2:
            raise ValueError("explicit ambiguity choice requires multiple candidates")
        if self.location_id is not None and self.location_id < 1:
            raise ValueError("location binding id must be positive")


@dataclass(frozen=True, slots=True)
class VolumeResolution:
    state: VolumeResolutionState
    binding: LocationBinding
    root_path: str | None = None
    evidence: VolumeEvidence | None = None
    candidates: tuple[str, ...] = ()
    detail: str | None = None


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

    def __post_init__(self) -> None:
        _validate_location_request(
            self.request_id, self.root_path, self.location_id
        )
        if self.selected_paths:
            object.__setattr__(
                self,
                "selected_paths",
                ScanScope.selected(self.selected_paths).selected_paths,
            )


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
        if self.selected_paths:
            object.__setattr__(
                self,
                "selected_paths",
                ScanScope.selected(self.selected_paths).selected_paths,
            )
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


@dataclass(frozen=True, slots=True)
class InventoryWorkflowRequest:
    request_id: str
    binding: LocationBinding
    selected_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request id is required")
        if self.selected_paths:
            object.__setattr__(
                self,
                "selected_paths",
                ScanScope.selected(self.selected_paths).selected_paths,
            )


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

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request id is required")
        if self.selected_paths:
            object.__setattr__(
                self,
                "selected_paths",
                ScanScope.selected(self.selected_paths).selected_paths,
            )
        if self.stale_before is not None:
            _require_utc(self.stale_before, "stale_before")
        if any(not item_id for item_id in self.selection_item_ids):
            raise ValueError("integrity selection item ids are required")
        if len(self.selection_item_ids) != len(set(self.selection_item_ids)):
            raise ValueError("integrity selection item ids must be unique")
        item_ids = [item_id for item_id, _ in self.completed_bytes]
        if any(not item_id for item_id in item_ids):
            raise ValueError("completed integrity item ids are required")
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("completed integrity item ids must be unique")
        if not set(item_ids).issubset(self.selection_item_ids):
            raise ValueError(
                "completed integrity items must belong to the saved selection"
            )
        if any(size < 0 for _, size in self.completed_bytes):
            raise ValueError("completed integrity byte counts cannot be negative")
        if self.processed_bytes > 0 and not self.selection_item_ids:
            raise ValueError(
                "integrity progress requires the saved admitted selection"
            )
        if self.processed_bytes < sum(size for _, size in self.completed_bytes):
            raise ValueError("processed bytes cannot trail completed bytes")
        if self.refresh_generation < 0:
            raise ValueError("inventory refresh generation cannot be negative")


Scanner = Callable[[Root, IgnoreSet, RunContext, ScanScope | None], ScanResult]
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
        candidates = {*hints, *_logical_drive_roots()}
        mounted: dict[str, MountedVolume] = {}
        for path in candidates:
            if not path:
                continue
            try:
                snapshot = self._backend.volume_snapshot(path)
            except (OSError, PermissionError):
                continue
            if snapshot.volume_id != volume_id:
                continue
            mount = snapshot.evidence.device_id or path
            mounted[_path_key(mount)] = MountedVolume(mount, snapshot.evidence)
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
    binding = _bind_request_location(
        request.root_path,
        request.location_id,
        request.selected_mount,
        ledger_path=ledger_path,
        backend=backend,
        resolver=resolver,
    )
    return InventoryWorkflowRequest(
        request.request_id, binding, request.selected_paths
    )


def bind_integrity_request(
    request: IntegrityRequest,
    *,
    ledger_path: Path,
    backend: VolumeBindingBackend,
    resolver: MountedVolumeResolver,
) -> IntegrityWorkflowRequest:
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
    mounted = resolver.mounted_volumes(
        binding.volume_id, hints=binding.expected_mounts
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
        root_stat = os.stat(
            to_extended_length_path(root_path),
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return VolumeResolution(
            VolumeResolutionState.ROOT_MISSING,
            binding,
            root_path=root_path,
            evidence=selected.evidence,
            candidates=candidates,
            detail="configured root no longer exists",
        )
    except (OSError, PermissionError) as error:
        return VolumeResolution(
            VolumeResolutionState.ROOT_UNAVAILABLE,
            binding,
            root_path=root_path,
            evidence=selected.evidence,
            candidates=candidates,
            detail=str(error),
        )
    if not stat_module.S_ISDIR(root_stat.st_mode):
        return VolumeResolution(
            VolumeResolutionState.ROOT_MISSING,
            binding,
            root_path=root_path,
            evidence=selected.evidence,
            candidates=candidates,
            detail="configured root is not a directory",
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
            detail=str(error),
        )
    return VolumeResolution(
        VolumeResolutionState.RESOLVED,
        binding,
        root_path=root_path,
        evidence=selected.evidence,
        candidates=candidates,
    )


def run_inventory(
    request: InventoryWorkflowRequest,
    ctx: RunContext,
    deps: InventoryDependencies,
) -> OperationResult:
    resolution = resolve_binding(request.binding, deps.resolver)
    if resolution.state != VolumeResolutionState.RESOLVED:
        deps.save_details(InventoryDetails(request.request_id, resolution))
        return _refused_resolution(resolution)
    if resolution.root_path is None or resolution.evidence is None:
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
        )
    )
    return OperationResult(SessionState.COMPLETED)


def run_integrity(
    request: IntegrityWorkflowRequest,
    ctx: RunContext,
    deps: IntegrityDependencies,
    *,
    selection_sink: Callable[[IntegritySelection], None] | None = None,
) -> OperationResult:
    resolution = resolve_binding(request.binding, deps.resolver)
    if resolution.state != VolumeResolutionState.RESOLVED:
        deps.save_details(InventoryDetails(request.request_id, resolution))
        return _refused_resolution(resolution)
    if resolution.root_path is None:
        raise RuntimeError("resolved integrity root lacks a path")
    root = resolution.root_path
    scope_token = f"{request.request_id}:refresh:{request.refresh_generation}"
    with LedgerRecorder(
        deps.ledger_path, clock=deps.clock, managed_roots=(root,)
    ) as recorder:
        host_id, location_id, scan = _register_and_scan(
            request.request_id,
            scope_token,
            request.binding,
            resolution,
            request.selected_paths,
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
            )
        )
        if request.selected_paths and not scan.complete:
            return OperationResult(
                SessionState.FAILED,
                error=FailureDetail(
                    "InventoryScopeIncomplete",
                    "selected inventory refresh was not authoritative",
                ),
            )
        with LedgerRepository(deps.ledger_path) as repository:
            rows = _integrity_rows(
                repository,
                location_id,
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
            raise RuntimeError(f"integrity runner is not configured: {request.mode.value}")
        result = runner(selection, deps.verifier_context(ctx), recorder)
    bytes_total = sum(
        0 if item.expected_stat is None else item.expected_stat.size
        for item in selection.items
    )
    return OperationResult(
        SessionState.COMPLETED,
        recording=result.recording,
        items=result.outcomes,
        bytes_done=selection.processed_bytes,
        bytes_total=max(bytes_total, selection.processed_bytes),
    )


def replace_mapping_filter(
    command_id: str,
    mapping_id: int,
    filter_snapshot: FilterSet,
    *,
    ledger_path: Path,
    clock: Clock,
) -> None:
    """Atomically replace authoritative mapping policy and its full projection."""

    with LedgerRepository(ledger_path) as repository:
        snapshot = repository.get_mapping_inventory(mapping_id)
    evaluations = tuple(
        MappingFilterEvaluation(
            row.inventory.location_id,
            row.inventory.row_id,
            row.inventory.rel_path_key,
            filter_snapshot.excludes(row.inventory.rel_path),
        )
        for row in (*snapshot.source_rows, *snapshot.target_rows)
    )
    with LedgerRecorder(ledger_path, clock=clock) as recorder:
        recorder.record_mapping_filter(
            MappingFilterCommand(
                command_id,
                mapping_id,
                filter_snapshot,
                evaluations,
                (snapshot.source_location_id, snapshot.target_location_id),
                clock.now(),
            )
        )


def change_inventory_visibility(
    command_id: str,
    location_id: int,
    row_id: str,
    action: InventoryVisibilityAction,
    *,
    ledger_path: Path,
    clock: Clock,
) -> RecordDisposition:
    """Acknowledge or restore one missing row through the ledger owner."""

    with LedgerRecorder(ledger_path, clock=clock) as recorder:
        return recorder.change_inventory_visibility(
            InventoryVisibilityCommand(
                command_id,
                location_id,
                row_id,
                action,
                clock.now(),
            )
        )


def encode_inventory_request(request: InventoryWorkflowRequest) -> bytes:
    return _json_bytes(
        {
            "version": 1,
            "kind": "inventory",
            "request_id": request.request_id,
            "binding": _binding_dict(request.binding),
            "selected_paths": list(request.selected_paths),
        }
    )


def decode_inventory_request(payload: bytes) -> InventoryWorkflowRequest:
    value = _payload(payload, "inventory")
    return InventoryWorkflowRequest(
        str(value["request_id"]),
        _decode_binding(value["binding"]),
        tuple(str(item) for item in _list(value["selected_paths"])),
    )


def encode_integrity_request(request: IntegrityWorkflowRequest) -> bytes:
    return _json_bytes(
        {
            "version": 1,
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
            "refresh_generation": request.refresh_generation,
        }
    )


def decode_integrity_request(payload: bytes) -> IntegrityWorkflowRequest:
    value = _payload(payload, "integrity")
    stale = value["stale_before"]
    return IntegrityWorkflowRequest(
        request_id=str(value["request_id"]),
        binding=_decode_binding(value["binding"]),
        mode=IntegrityMode(str(value["mode"])),
        selected_paths=tuple(
            str(item) for item in _list(value["selected_paths"])
        ),
        stale_before=None if stale is None else datetime.fromisoformat(str(stale)),
        selection_item_ids=tuple(
            str(item) for item in _list(value["selection_item_ids"])
        ),
        completed_bytes=tuple(
            (str(item[0]), int(item[1]))
            for item in (_list(raw) for raw in _list(value["completed_bytes"]))
        ),
        processed_bytes=int(value["processed_bytes"]),
        refresh_generation=int(value["refresh_generation"]),
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
    snapshot = backend.volume_snapshot(resolved)
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
    hints = () if mount_hint is None else (mount_hint,)
    mounted = resolver.mounted_volumes(volume_id, hints)
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
    ctx: RunContext,
    deps: InventoryDependencies,
    recorder: LedgerRecorder,
) -> tuple[int, int, ScanResult]:
    if resolution.root_path is None or resolution.evidence is None:
        raise RuntimeError("resolved inventory root lacks volume evidence")
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
    ctx.emit(PhaseChanged("inventory"))
    scope = (
        ScanScope.full()
        if not selected_paths
        else ScanScope.selected(selected_paths)
    )
    scan = deps.scanner(
        Root(resolution.root_path, f"inventory:{scope_token}"),
        deps.ignores,
        ctx,
        scope,
    )
    if scan.volume_id != binding.volume_id:
        raise RuntimeError("inventory scan volume changed after preflight")
    return host_id, location_id, scan


def _integrity_rows(
    repository: LedgerRepository,
    location_id: int,
    selected_paths: tuple[str, ...],
    stale_before: datetime | None,
    selection_item_ids: tuple[str, ...],
    completed_item_ids: frozenset[str],
) -> tuple[InventorySnapshot, ...]:
    if selection_item_ids:
        rows = {
            f"{row.location_id}:{row.row_id}": row
            for row in repository.get_inventory(location_id)
        }
        missing = [
            item_id for item_id in selection_item_ids if item_id not in rows
        ]
        if missing:
            raise RuntimeError(
                "saved integrity selection references missing inventory rows"
            )
        return tuple(rows[item_id] for item_id in selection_item_ids)
    if selected_paths:
        return tuple(
            row
            for row in repository.get_inventory(location_id, selected_paths)
            if (
                row.entry_kind is None
                or row.entry_kind.value != "directory"
                or f"{row.location_id}:{row.row_id}" in completed_item_ids
            )
        )
    if stale_before is not None:
        stale_ids = {
            f"{row.location_id}:{row.row_id}"
            for row in repository.get_stale_inventory(location_id, stale_before)
        }
        return tuple(
            row
            for row in repository.get_inventory(location_id)
            if (
                f"{row.location_id}:{row.row_id}" in stale_ids
                or f"{row.location_id}:{row.row_id}" in completed_item_ids
            )
        )
    return tuple(
        row
        for row in repository.get_inventory(location_id)
        if (
            row.entry_kind is None
            or row.entry_kind.value != "directory"
            or f"{row.location_id}:{row.row_id}" in completed_item_ids
        )
    )


def _integrity_selection(
    request: IntegrityWorkflowRequest,
    rows: tuple[InventorySnapshot, ...],
    root: str,
) -> IntegritySelection:
    completed = dict(request.completed_bytes)
    items = tuple(
        IntegritySelectionItem(
            item_id=f"{row.location_id}:{row.row_id}",
            row_id=row.row_id,
            location_id=str(row.location_id),
            root=Path(root),
            rel_path_key=row.rel_path_key,
            display_path=row.rel_path,
            expected_state=InventoryState(row.presence.value),
            expected_stat=row.observed,
            baseline=row.attestation,
            scope_token=row.scope_token,
            reappeared_at=row.reappeared_at,
        )
        for row in rows
    )
    return IntegritySelection(items, completed, request.processed_bytes)


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
    volume = _mapping(data["volume"])
    return LocationBinding(
        VolumeId(str(volume["serial"]), str(volume["fs_type"])),
        str(data["volume_relative_path"]),
        str(data["selected_mount"]),
        tuple(str(item) for item in _list(data["expected_mounts"])),
        bool(data["explicit_ambiguity_choice"]),
        None if data["location_id"] is None else int(data["location_id"]),
    )


def _payload(payload: bytes, expected_kind: str) -> Mapping[str, object]:
    value = json.loads(payload.decode("utf-8"))
    data = _mapping(value)
    if int(data["version"]) != 1 or data["kind"] != expected_kind:
        raise ValueError("unsupported inventory workflow payload")
    return data


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", errors="backslashreplace")


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("workflow payload value must be an object")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError("workflow payload value must be a list")
    return value


def _validate_location_request(
    request_id: str, root_path: str | None, location_id: int | None
) -> None:
    if not request_id:
        raise ValueError("request id is required")
    if (root_path is None) == (location_id is None):
        raise ValueError("request requires exactly one root path or location id")
    if root_path is not None and not root_path:
        raise ValueError("root path cannot be empty")
    if location_id is not None and location_id < 1:
        raise ValueError("location id must be positive")


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
    length = kernel32.GetLogicalDriveStringsW(0, None)
    if length <= 0:
        raise OSError(ctypes.get_last_error(), "GetLogicalDriveStringsW failed")
    buffer = ctypes.create_unicode_buffer(length + 1)
    if kernel32.GetLogicalDriveStringsW(len(buffer), buffer) == 0:
        raise OSError(ctypes.get_last_error(), "GetLogicalDriveStringsW failed")
    return tuple(value for value in buffer[:length].split("\x00") if value)


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field_name} must be UTC")


def _missing_verifier_context() -> VerifierContext:
    raise RuntimeError("verifier context factory is required")
