"""Local M0 composition root for workflows, persistence, and audit."""

from __future__ import annotations

import os
import platform
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from xxhash import xxh3_128

from namisync.core.execution import Commitment, ExecutionSet
from namisync.core.evidence import RecordingStatus
from namisync.core.integrity import (
    IntegrityMode,
    IntegritySelection,
    RecordDisposition,
    VerifierContext,
)
from namisync.core.models import ScanResult, VolumeEvidence, VolumeId
from namisync.core.planning import (
    MappingSnapshot,
    Plan,
    calculate_required_bytes,
    selection_digest,
)
from namisync.core.recording import (
    FinishRunCommand,
    HostCommand,
    InventoryVisibilityAction,
    LocationCommand,
    MappingCommand,
    SyncRunCommand,
    VolumeCommand,
)
from namisync.core.session import SessionRecord, SessionState
from namisync.db.connections import validate_database_path
from namisync.db.history import (
    HistoryContext,
    HistoryObserver,
    HistoryRepository,
    HistoryStore,
)
from namisync.db.recorder import LedgerRecorder, SyncRunRecorder
from namisync.db.repositories import InventorySnapshot, LedgerRepository
from namisync.modules.executor import (
    ExecutorPolicies,
    NativeCopyBackend,
    NativeFileSystem,
    SystemClock,
    execute,
)
from namisync.modules.planner import plan
from namisync.modules.preflight import LocalObservationFileSystem, observe, preflight
from namisync.modules.scanner import NativeScannerBackend, WalkingScanner
from namisync.modules.verifier import baseline, rebaseline, verify

from .inventory import (
    IntegrityDependencies,
    IntegrityRequest,
    IntegrityRunner,
    IntegrityWorkflowRequest,
    InventoryDependencies,
    InventoryDetails,
    InventoryRequest,
    InventoryWorkflowRequest,
    LocationBinding,
    MountedVolumeResolver,
    NativeMountedVolumeResolver,
    Scanner,
    bind_integrity_request,
    bind_inventory_request,
    change_inventory_visibility,
    decode_integrity_request,
    decode_inventory_request,
    encode_integrity_request,
    encode_inventory_request,
    run_integrity,
    run_inventory,
)
from .models import (
    ExecutionDetails,
    ExecutionRequest,
    HistoryRunView,
    PlanArtifact,
    PlanOperationView,
    PlanRequest,
    PlanReview,
    WorkflowPreparation,
)
from .payloads import (
    decode_execution_request,
    decode_plan_request,
    encode_execution_request,
    encode_plan_request,
)
from .sync import SyncDependencies, refusal_views, run_execution, run_plan
from .selection import derive_execution_selection
from .views import result_item_view


PLAN_KIND = "sync-plan"
EXECUTION_KIND = "sync-execution"
INVENTORY_KIND = "inventory"
BASELINE_KIND = "baseline"
VERIFY_KIND = "verify"
REBASELINE_KIND = "rebaseline"

_INTEGRITY_KINDS = {
    BASELINE_KIND: IntegrityMode.BASELINE,
    VERIFY_KIND: IntegrityMode.VERIFY,
    REBASELINE_KIND: IntegrityMode.REBASELINE,
}


def default_database_paths() -> tuple[Path, Path]:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Local"
    app = root / "NamiSync"
    return app / "ledger.db", app / "history.db"


class LocalWorkflowRuntime:
    """Own injected local collaborators and workflow-owned result artifacts."""

    def __init__(
        self,
        ledger_path: str | Path,
        history_path: str | Path,
        *,
        clock=None,
        host_key: str | None = None,
        host_name: str | None = None,
        resource_resolver: Callable[[str], VolumeId] | None = None,
        mounted_volume_resolver: MountedVolumeResolver | None = None,
        inventory_scanner: Scanner | None = None,
        integrity_runners: Mapping[IntegrityMode, IntegrityRunner] | None = None,
    ) -> None:
        self.ledger_path = Path(ledger_path).resolve()
        self.history_path = Path(history_path).resolve()
        self.clock = clock or SystemClock()
        detected_host = platform.node().strip() or "unknown-host"
        self.host_key = host_key or detected_host
        self.host_name = host_name or detected_host
        self._scanner_backend = NativeScannerBackend()
        self._scanner = WalkingScanner(self._scanner_backend)
        self._mounted_volume_resolver = (
            mounted_volume_resolver
            or NativeMountedVolumeResolver(self._scanner_backend)
        )
        self._resource_resolver = resource_resolver or self._resolve_volume
        self._observation_fs = LocalObservationFileSystem()
        self._executor_fs = NativeFileSystem()
        self._hasher_factory = xxh3_128
        self._executor_policies = ExecutorPolicies(
            copy_backend=NativeCopyBackend(
                hasher_factory=self._hasher_factory
            ),
            clock=self.clock,
        )
        self._lock = Lock()
        self._plans: dict[str, PlanArtifact] = {}
        self._execution_details: dict[str, ExecutionDetails] = {}
        self._inventory_details: dict[str, InventoryDetails] = {}
        self._execution_started: dict[str, datetime] = {}
        self._history_store: HistoryStore | None = None
        self._closed = False

        self._deps = SyncDependencies(
            scanner=self._scanner.scan,
            planner=plan,
            correspondence=self._correspondence,
            observation_fs=self._observation_fs,
            observer=observe,
            preflight=preflight,
            executor=execute,
            executor_policies=self._executor_policies,
            executor_fs=self._executor_fs,
            open_recording=self._open_recording,
            save_plan=self._save_plan,
            save_execution_details=self._save_execution_details,
        )
        inventory_scan = inventory_scanner or self._scanner.scan
        self._inventory_deps = InventoryDependencies(
            ledger_path=self.ledger_path,
            scanner=inventory_scan,
            resolver=self._mounted_volume_resolver,
            clock=self.clock,
            host_key=self.host_key,
            host_name=self.host_name,
            save_details=self._save_inventory_details,
        )
        self._integrity_deps = IntegrityDependencies(
            ledger_path=self.ledger_path,
            scanner=inventory_scan,
            resolver=self._mounted_volume_resolver,
            clock=self.clock,
            host_key=self.host_key,
            host_name=self.host_name,
            save_details=self._save_inventory_details,
            verifier_context=lambda context: VerifierContext(
                run=context,
                clock=self.clock,
                hasher_factory=self._hasher_factory,
            ),
            runners=(
                {
                    IntegrityMode.BASELINE: baseline,
                    IntegrityMode.VERIFY: verify,
                    IntegrityMode.REBASELINE: rebaseline,
                }
                if integrity_runners is None
                else dict(integrity_runners)
            ),
        )

    def prepare_plan(self, request: object) -> WorkflowPreparation:
        self._require_open()
        if not isinstance(request, PlanRequest):
            raise TypeError("sync planning requires PlanRequest")
        self._validate_database_roots(
            (request.source_path, request.target_path)
        )
        resources = self._resources_for_paths(
            request.source_path, request.target_path
        )
        return WorkflowPreparation(encode_plan_request(request), resources)

    def open_plan(self, payload: bytes) -> _PlanInvocation:
        self._require_open()
        return _PlanInvocation(decode_plan_request(payload), payload, self._deps)

    def prepare_execution(self, request: object) -> WorkflowPreparation:
        self._require_open()
        if not isinstance(request, ExecutionRequest):
            raise TypeError("sync execution requires ExecutionRequest")
        plan_value = request.execution_set.plan
        self._validate_database_locations(plan_value)
        resources = tuple(
            sorted(
                ("volume", _volume_resource_key(volume))
                for volume in plan_value.required_volumes
            )
        )
        return WorkflowPreparation(encode_execution_request(request), resources)

    def open_execution(self, payload: bytes) -> _ExecutionInvocation:
        self._require_open()
        request = decode_execution_request(payload)
        started_at = request.started_at or self.clock.now()
        _require_utc(started_at, "execution start")
        request = ExecutionRequest(request.execution_set, started_at)
        with self._lock:
            self._execution_started[str(request.execution_set.run_id)] = started_at
        return _ExecutionInvocation(request, self._deps)

    def prepare_inventory(self, request: object) -> WorkflowPreparation:
        self._require_open()
        if not isinstance(request, InventoryRequest):
            raise TypeError("inventory requires InventoryRequest")
        prepared = bind_inventory_request(
            request,
            ledger_path=self.ledger_path,
            backend=self._scanner_backend,
            resolver=self._mounted_volume_resolver,
        )
        self._validate_prepared_location(prepared.binding)
        return WorkflowPreparation(
            encode_inventory_request(prepared),
            (("volume", _volume_resource_key(prepared.binding.volume_id)),),
        )

    def open_inventory(self, payload: bytes) -> _InventoryInvocation:
        self._require_open()
        return _InventoryInvocation(
            decode_inventory_request(payload),
            payload,
            self._inventory_deps,
        )

    def prepare_baseline(self, request: object) -> WorkflowPreparation:
        return self._prepare_integrity(request, IntegrityMode.BASELINE)

    def open_baseline(self, payload: bytes) -> _IntegrityInvocation:
        return self._open_integrity(payload, IntegrityMode.BASELINE)

    def prepare_verify(self, request: object) -> WorkflowPreparation:
        return self._prepare_integrity(request, IntegrityMode.VERIFY)

    def open_verify(self, payload: bytes) -> _IntegrityInvocation:
        return self._open_integrity(payload, IntegrityMode.VERIFY)

    def prepare_rebaseline(self, request: object) -> WorkflowPreparation:
        return self._prepare_integrity(request, IntegrityMode.REBASELINE)

    def open_rebaseline(self, payload: bytes) -> _IntegrityInvocation:
        return self._open_integrity(payload, IntegrityMode.REBASELINE)

    def audit_observer(self, record: SessionRecord) -> HistoryObserver | None:
        if record.kind == EXECUTION_KIND:
            request = decode_execution_request(record.payload)
            plan_value = request.execution_set.plan
            store = self._ensure_history_store(
                (
                    plan_value.source_root.path,
                    plan_value.target_root.path,
                )
            )
            return store.observer(
                record,
                HistoryContext(
                    run_token=str(request.execution_set.run_id),
                    host_key=self.host_key,
                    activity_kind="sync",
                    source_context=plan_value.source_root.path,
                    target_context=plan_value.target_root.path,
                ),
            )
        if record.kind == INVENTORY_KIND:
            request = decode_inventory_request(record.payload)
            activity_kind = INVENTORY_KIND
        elif record.kind in _INTEGRITY_KINDS:
            request = decode_integrity_request(record.payload)
            expected_mode = _INTEGRITY_KINDS[record.kind]
            if request.mode is not expected_mode:
                raise ValueError("integrity history kind does not match its payload")
            activity_kind = request.mode.value
        else:
            return None
        root = _binding_root(request.binding)
        store = self._ensure_history_store((root,))
        return store.observer(
            record,
            HistoryContext(
                run_token=request.request_id,
                host_key=self.host_key,
                activity_kind=activity_kind,
                subject_kind="location",
                subject_id=_location_subject_id(request.binding),
            ),
        )

    def get_plan_review(self, request_id: str) -> PlanReview:
        with self._lock:
            artifact = self._plans.get(request_id)
        if artifact is None:
            raise KeyError(request_id)
        plan_value = artifact.plan
        decision = derive_execution_selection(plan_value)
        exclusions = {item.op_id: item for item in decision.exclusions}
        warnings = tuple(
            _warning_text("source", warning.code.value, warning.rel_path, warning.detail)
            for warning in artifact.source_scan.warnings
        ) + tuple(
            _warning_text("target", warning.code.value, warning.rel_path, warning.detail)
            for warning in artifact.target_scan.warnings
        )
        return PlanReview(
            request_id=request_id,
            source_path=plan_value.source_root.path,
            target_path=plan_value.target_root.path,
            source_volume=_volume_text(plan_value.source_volume_id),
            target_volume=_volume_text(plan_value.target_volume_id),
            deletion_policy=plan_value.deletion_policy.value,
            trash_on_update=plan_value.trash_on_update,
            fingerprint=str(plan_value.fingerprint),
            selection_digest_hex=selection_digest(decision.selection).hex(),
            required_bytes=calculate_required_bytes(
                tuple(
                    operation
                    for operation in plan_value.operations
                    if operation.op_id in decision.selection
                ),
                target_profile=plan_value.target_profile,
                trash_on_update=plan_value.trash_on_update,
            ),
            free_bytes=artifact.verdict.observed.free_space,
            reclaimable_temp_bytes=artifact.verdict.observed.reclaimable_temp_bytes,
            warnings=warnings,
            refusals=refusal_views(artifact.verdict),
            operations=tuple(
                PlanOperationView(
                    operation_id=str(operation.op_id),
                    kind=operation.kind.value,
                    source_path=operation.source_rel_path,
                    target_path=operation.target_rel_path,
                    prior_target_path=operation.prior_target_rel_path,
                    reason=operation.reason.value,
                    blocked_reason=None
                    if operation.blocked_reason is None
                    else operation.blocked_reason.value,
                    selection_outcome=None
                    if operation.op_id not in exclusions
                    else exclusions[operation.op_id].outcome.value,
                    selection_reason=None
                    if operation.op_id not in exclusions
                    else exclusions[operation.op_id].reason,
                    content_bytes=operation.content_bytes,
                )
                for operation in plan_value.operations
            ),
        )

    def commit_plan(
        self,
        request_id: str,
        *,
        run_id: str | None = None,
        committed_at: datetime | None = None,
    ) -> ExecutionRequest:
        with self._lock:
            artifact = self._plans.get(request_id)
        if artifact is None:
            raise KeyError(request_id)
        if not artifact.verdict.ok:
            raise ValueError("a refused plan cannot be committed")
        selection = derive_execution_selection(artifact.plan).selection
        committed = committed_at or self.clock.now()
        _require_utc(committed, "commitment")
        commitment = Commitment(
            artifact.plan.fingerprint,
            selection_digest(selection),
            committed,
        )
        token = run_id or uuid4().hex
        return ExecutionRequest(
            ExecutionSet(
                artifact.plan,
                selection,
                token,
                commitment=commitment,
            )
        )

    def get_execution_details(self, run_id: str) -> ExecutionDetails:
        with self._lock:
            details = self._execution_details.get(run_id)
        return details or ExecutionDetails(run_id)

    def get_inventory_details(self, request_id: str) -> InventoryDetails:
        with self._lock:
            details = self._inventory_details.get(request_id)
        if details is None:
            raise KeyError(request_id)
        return details

    def list_inventory(
        self, location_id: int, selected_paths: tuple[str, ...] = ()
    ) -> tuple[InventorySnapshot, ...]:
        self._require_open()
        with LedgerRepository(self.ledger_path) as repository:
            return repository.get_inventory(
                location_id,
                None if not selected_paths else selected_paths,
            )

    def list_stale_inventory(
        self, location_id: int, verified_before: datetime
    ) -> tuple[InventorySnapshot, ...]:
        self._require_open()
        _require_utc(verified_before, "stale inventory cutoff")
        with LedgerRepository(self.ledger_path) as repository:
            return repository.get_stale_inventory(location_id, verified_before)

    def list_unacknowledged_missing(
        self, location_id: int
    ) -> tuple[InventorySnapshot, ...]:
        self._require_open()
        with LedgerRepository(self.ledger_path) as repository:
            return repository.get_unacknowledged_missing(location_id)

    def acknowledge_inventory(
        self, command_id: str, location_id: int, row_id: str
    ) -> RecordDisposition:
        self._require_open()
        return change_inventory_visibility(
            command_id,
            location_id,
            row_id,
            InventoryVisibilityAction.ACKNOWLEDGE,
            ledger_path=self.ledger_path,
            clock=self.clock,
        )

    def restore_inventory(
        self, command_id: str, location_id: int, row_id: str
    ) -> RecordDisposition:
        self._require_open()
        return change_inventory_visibility(
            command_id,
            location_id,
            row_id,
            InventoryVisibilityAction.RESTORE,
            ledger_path=self.ledger_path,
            clock=self.clock,
        )

    def list_history(self, limit: int = 50) -> tuple[HistoryRunView, ...]:
        if not self.history_path.exists():
            return ()
        with HistoryRepository(self.history_path) as repository:
            return tuple(_history_view(item) for item in repository.list_recent(limit))

    def get_history(self, run_token: str) -> HistoryRunView:
        if not self.history_path.exists():
            raise KeyError(run_token)
        with HistoryRepository(self.history_path) as repository:
            return _history_view(repository.get(run_token))

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            store = self._history_store
            self._history_store = None
        if store is not None:
            store.close()

    def _resolve_volume(self, path: str) -> VolumeId:
        resolved = self._scanner_backend.resolve_root(path)
        return self._scanner_backend.volume_snapshot(resolved).volume_id

    def _resources_for_paths(
        self, source_path: str, target_path: str
    ) -> tuple[tuple[str, str], ...]:
        volumes = {
            self._resource_resolver(source_path),
            self._resource_resolver(target_path),
        }
        return tuple(
            sorted(("volume", _volume_resource_key(volume)) for volume in volumes)
        )

    def _prepare_integrity(
        self, request: object, mode: IntegrityMode
    ) -> WorkflowPreparation:
        self._require_open()
        if not isinstance(request, IntegrityRequest):
            raise TypeError(f"{mode.value} requires IntegrityRequest")
        if request.mode is not mode:
            raise ValueError(
                f"{mode.value} preparation requires mode={mode.value}"
            )
        prepared = bind_integrity_request(
            request,
            ledger_path=self.ledger_path,
            backend=self._scanner_backend,
            resolver=self._mounted_volume_resolver,
        )
        self._validate_prepared_location(prepared.binding)
        return WorkflowPreparation(
            encode_integrity_request(prepared),
            (("volume", _volume_resource_key(prepared.binding.volume_id)),),
        )

    def _open_integrity(
        self, payload: bytes, mode: IntegrityMode
    ) -> _IntegrityInvocation:
        self._require_open()
        request = decode_integrity_request(payload)
        if request.mode is not mode:
            raise ValueError(
                f"{mode.value} invocation payload contains {request.mode.value}"
            )
        return _IntegrityInvocation(request, self._integrity_deps)

    def _validate_prepared_location(self, binding: LocationBinding) -> None:
        self._validate_database_roots((_binding_root(binding),))

    def _correspondence(
        self, source: ScanResult, target: ScanResult
    ) -> MappingSnapshot:
        if source.volume_id is None or target.volume_id is None:
            return MappingSnapshot.empty(source.volume_id, target.volume_id)
        if not self.ledger_path.exists():
            return MappingSnapshot.empty(source.volume_id, target.volume_id)
        source_relative = _volume_relative_path(
            source.root.path, source.volume_evidence
        )
        target_relative = _volume_relative_path(
            target.root.path, target.volume_evidence
        )
        with LedgerRepository(self.ledger_path) as repository:
            found = repository.find_mapping(
                source.volume_id,
                source_relative,
                target.volume_id,
                target_relative,
            )
        return (
            MappingSnapshot.empty(source.volume_id, target.volume_id)
            if found is None
            else found.snapshot
        )

    def _open_recording(
        self, xset: ExecutionSet
    ) -> AbstractContextManager[_LedgerRunRecording]:
        with self._lock:
            started_at = self._execution_started.get(str(xset.run_id))
        if started_at is None:
            raise RuntimeError("execution start time was not established")
        return _LedgerRunRecording(self, xset, started_at)

    def _save_plan(self, artifact: PlanArtifact) -> None:
        with self._lock:
            self._plans[artifact.request.request_id] = artifact

    def _save_execution_details(self, details: ExecutionDetails) -> None:
        with self._lock:
            self._execution_details[details.run_id] = details

    def _save_inventory_details(self, details: InventoryDetails) -> None:
        with self._lock:
            self._inventory_details[details.request_id] = details

    def _validate_database_locations(self, plan_value: Plan) -> None:
        self._validate_database_roots(
            (
                plan_value.source_root.path,
                plan_value.target_root.path,
            )
        )

    def _validate_database_roots(
        self, roots: tuple[str, ...]
    ) -> None:
        if self.ledger_path == self.history_path:
            raise ValueError("ledger and history databases must use distinct paths")
        managed_roots = tuple(Path(root) for root in roots)
        validate_database_path(self.ledger_path, managed_roots=managed_roots)
        validate_database_path(self.history_path, managed_roots=managed_roots)

    def _ensure_history_store(self, managed_roots: tuple[str, ...]) -> HistoryStore:
        self._validate_database_roots(managed_roots)
        with self._lock:
            if self._history_store is None:
                self._history_store = HistoryStore(
                    self.history_path,
                    clock=self.clock,
                    managed_roots=managed_roots,
                )
            return self._history_store

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("workflow runtime is closed")


class _PlanInvocation:
    def __init__(
        self, request: PlanRequest, payload: bytes, deps: SyncDependencies
    ) -> None:
        self._request = request
        self._payload = payload
        self._deps = deps

    def run(self, context) -> object:
        return run_plan(self._request, context, self._deps)

    def snapshot(self) -> bytes:
        return self._payload


class _ExecutionInvocation:
    def __init__(self, request: ExecutionRequest, deps: SyncDependencies) -> None:
        self._request = request
        self._deps = deps

    def run(self, context) -> object:
        return run_execution(self._request.execution_set, context, self._deps)

    def snapshot(self) -> bytes:
        return encode_execution_request(self._request)


class _InventoryInvocation:
    def __init__(
        self,
        request: InventoryWorkflowRequest,
        payload: bytes,
        deps: InventoryDependencies,
    ) -> None:
        self._request = request
        self._payload = payload
        self._deps = deps

    def run(self, context) -> object:
        return run_inventory(self._request, context, self._deps)

    def snapshot(self) -> bytes:
        return self._payload


class _IntegrityInvocation:
    def __init__(
        self,
        request: IntegrityWorkflowRequest,
        deps: IntegrityDependencies,
    ) -> None:
        self._request = request
        self._deps = deps
        self._selection: IntegritySelection | None = None

    def run(self, context) -> object:
        return run_integrity(
            self._request,
            context,
            self._deps,
            selection_sink=self._capture_selection,
        )

    def snapshot(self) -> bytes:
        completed_bytes = self._request.completed_bytes
        processed_bytes = self._request.processed_bytes
        if self._selection is not None:
            completed_bytes = tuple(
                sorted(self._selection.completed_bytes.items())
            )
            processed_bytes = self._selection.processed_bytes
        return encode_integrity_request(
            replace(
                self._request,
                selection_item_ids=(
                    self._request.selection_item_ids
                    if self._selection is None
                    else tuple(
                        item.item_id for item in self._selection.items
                    )
                ),
                completed_bytes=completed_bytes,
                processed_bytes=processed_bytes,
                refresh_generation=self._request.refresh_generation + 1,
            )
        )

    def _capture_selection(self, selection: IntegritySelection) -> None:
        self._selection = selection


class _LedgerRunRecording:
    def __init__(
        self,
        runtime: LocalWorkflowRuntime,
        xset: ExecutionSet,
        started_at: datetime,
    ) -> None:
        self._runtime = runtime
        self._xset = xset
        self._owner = LedgerRecorder(
            runtime.ledger_path,
            clock=runtime.clock,
            managed_roots=(
                xset.plan.source_root.path,
                xset.plan.target_root.path,
            ),
        )
        try:
            self.recorder = self._begin(started_at)
        except BaseException:
            self._owner.close()
            raise

    def _begin(self, started_at: datetime) -> SyncRunRecorder:
        plan_value = self._xset.plan
        if (
            plan_value.source_volume_id is None
            or plan_value.target_volume_id is None
            or plan_value.source_volume_evidence is None
            or plan_value.target_volume_evidence is None
            or self._xset.commitment is None
        ):
            raise ValueError("executable plan lacks volume or commitment evidence")
        now = self._runtime.clock.now()
        host_id = self._owner.ensure_host(
            HostCommand(self._runtime.host_key, self._runtime.host_name, now)
        )
        source_volume = self._owner.observe_volume(
            VolumeCommand(
                plan_value.source_volume_id,
                plan_value.source_volume_evidence,
                now,
            )
        )
        target_volume = self._owner.observe_volume(
            VolumeCommand(
                plan_value.target_volume_id,
                plan_value.target_volume_evidence,
                now,
            )
        )
        source_location = self._owner.ensure_location(
            LocationCommand(
                source_volume,
                _volume_relative_path(
                    plan_value.source_root.path,
                    plan_value.source_volume_evidence,
                ),
                now,
            )
        )
        target_location = self._owner.ensure_location(
            LocationCommand(
                target_volume,
                _volume_relative_path(
                    plan_value.target_root.path,
                    plan_value.target_volume_evidence,
                ),
                now,
            )
        )
        mapping_id = self._owner.ensure_mapping(
            MappingCommand(source_location, target_location, now)
        )
        return self._owner.begin_sync_run(
            SyncRunCommand(
                run_token=str(self._xset.run_id),
                host_id=host_id,
                mapping_id=mapping_id,
                source_location_id=source_location,
                target_location_id=target_location,
                plan=plan_value,
                selection=self._xset.selection,
                selection_digest=self._xset.commitment.selection_digest,
                started_at=started_at,
            )
        )

    def finish(
        self, status: SessionState, recording: RecordingStatus
    ) -> None:
        self.recorder.finish(
            FinishRunCommand(
                str(self._xset.run_id),
                status,
                recording,
                self._runtime.clock.now(),
            )
        )

    def __enter__(self) -> _LedgerRunRecording:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._owner.close()


def _history_view(value) -> HistoryRunView:
    return HistoryRunView(
        run_token=value.run_token,
        activity_kind=value.activity_kind,
        subject_kind=value.subject_kind,
        subject_id=value.subject_id,
        source_context=value.source_context,
        target_context=value.target_context,
        started_at=value.started_at,
        ended_at=value.ended_at,
        filesystem_status=value.filesystem_status.value,
        recording_status=value.recording.value,
        audit_status=value.audit.value,
        disposition=value.disposition,
        bytes_done=value.bytes_done,
        bytes_total=value.bytes_total,
        items=tuple(result_item_view(snapshot.item) for snapshot in value.items),
        error=None
        if value.error_type is None
        else f"{value.error_type}: {value.error_message or ''}".rstrip(),
    )


def _volume_relative_path(path: str, evidence: VolumeEvidence | None) -> str:
    mount = None if evidence is None else evidence.device_id
    if not mount:
        mount = Path(path).anchor
    if not mount:
        raise ValueError("volume mount evidence is unavailable")
    relative = os.path.relpath(path, mount)
    if relative == ".":
        return ""
    if relative == ".." or relative.startswith(".." + os.sep):
        raise ValueError("managed root is outside its observed volume mount")
    return relative.replace(os.sep, "\\")


def _volume_resource_key(volume: VolumeId) -> str:
    return f"{volume.serial}:{volume.fs_type}"


def _binding_root(binding: LocationBinding) -> str:
    if not binding.volume_relative_path:
        return binding.selected_mount
    return os.path.join(
        binding.selected_mount,
        *binding.volume_relative_path.split("\\"),
    )


def _location_subject_id(binding: LocationBinding) -> str:
    if binding.location_id is not None:
        return str(binding.location_id)
    relative = binding.volume_relative_path or "."
    return f"{_volume_resource_key(binding.volume_id)}:{relative}"


def _volume_text(volume: VolumeId | None) -> str:
    return "unavailable" if volume is None else _volume_resource_key(volume)


def _warning_text(
    side: str, code: str, path: str | None, detail: str
) -> str:
    subject = side if path is None else f"{side}:{path}"
    return f"{subject}: {code}" + (f" ({detail})" if detail else "")


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError(f"{field_name} must be UTC")
