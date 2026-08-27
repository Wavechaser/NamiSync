"""Local M0 composition root for workflows, persistence, and audit."""

from __future__ import annotations

import os
import platform
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from xxhash import xxh3_128

from namisync.core.execution import Commitment, ExecutionSet, TaskRecordingIssue
from namisync.core.evidence import RecordingStatus
from namisync.core.integrity import (
    IntegrityMode,
    IntegritySelection,
    RecordDisposition,
    VerifierContext,
)
from namisync.core.models import ScanResult, VolumeEvidence, VolumeId
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import (
    DeletionPolicy,
    FilterSet,
    MappingSnapshot,
    OperationKind,
    Plan,
    PreservationPolicy,
    SyncOptions,
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
from namisync.core.session import (
    Disposition,
    OperationResult,
    PauseRequested,
    PhaseResult,
    SessionRecord,
    SessionState,
)
from namisync.core.scalars import require_safe_int, scalar_64_to_text
from namisync.db.connections import validate_database_path
from namisync.db.history import (
    DEFAULT_HISTORY_WINDOW_POLICY,
    HistoryClassificationQuery,
    HistoryContext,
    HistoryEventPage,
    HistoryItemPage,
    HistoryObserver,
    HistoryRepository,
    HistoryRunSummary,
    HistoryStore,
)
from namisync.db.recorder import LedgerRecorder, SyncRunRecorder
from namisync.db.repositories import InventorySnapshot, LedgerRepository
from namisync.db.settings import (
    SemanticSettings,
    SemanticSettingsPatch,
    SemanticSettingsStore,
)
from namisync.db.writer import DEFAULT_RETRY_TIMEOUT_SECONDS
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
from namisync.modules.verifier import baseline, rebaseline, verify, verify_post_copy

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
    settle_canceled_integrity,
)
from .database_pair import (
    DatabasePairContract,
    DatabasePairRefusedError,
    DatabasePairState,
    ensure_database_pair,
    initialize_database_pair,
    validate_database_pair,
)
from .models import (
    ExecuteContinuation,
    ExecutionDetails,
    ExecutionRequest,
    HistoryEventView,
    HistoryEventPageView,
    HistoryItemPageView,
    HistoryItemView,
    HistoryRunSummaryView,
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
from .sync import (
    SyncDependencies,
    refusal_views,
    run_execution,
    run_plan,
    settle_canceled_execution as settle_canceled_sync_execution,
)
from .node_tree import NodeTree, NodeTreeKind, NodeTreeMember, build_node_tree
from .selection import SELECTION_EXCLUSION_REASONS, derive_execution_selection
from .views import (
    PreservationSettingsView,
    RecordingIssueView,
    ReviewFactLimitView,
    ResultClassificationFacts,
    SemanticSettingsPatchView,
    SemanticSettingsView,
    classify_result_facts,
    phase_result_view,
    result_item_view,
    session_event_view,
)


# History finalization is an independently degradable axis, so it retries for
# less than the ledger's generic bound: exhausting it costs one audit row and
# an honest ``audit=degraded``, never filesystem or integrity truth. Every
# derived audit and shutdown bound scales from this value, so keeping it well
# under the generic default is what keeps window close responsive.
HISTORY_WRITER_RETRY_TIMEOUT_SECONDS = 5.0
if HISTORY_WRITER_RETRY_TIMEOUT_SECONDS > DEFAULT_RETRY_TIMEOUT_SECONDS:
    raise AssertionError(
        "history retry must not exceed the generic serialized-writer bound"
    )


_HISTORY_CLASSIFICATION_QUERY = HistoryClassificationQuery(
    excluded_operation_reasons=tuple(sorted(SELECTION_EXCLUSION_REASONS)),
    noop_operation_kind=OperationKind.NOOP.value,
)


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


def execution_selection_digest_hex(selection: frozenset[str]) -> str:
    """Return the canonical commitment digest for one effective selection."""

    return selection_digest(selection).hex()


def build_plan_node_tree(request_id: str, plan_value: Plan) -> NodeTree:
    """Build the workflow-owned hierarchy for one immutable plan artifact."""

    return build_node_tree(
        tree_kind=NodeTreeKind.PLAN,
        scope_identity=request_id,
        members=(
            NodeTreeMember(
                str(operation.op_id),
                operation.target_rel_path,
                normalize_relative_path(operation.target_rel_path),
                operation.kind.value == "mkdir"
                or operation.reason.value == "directory_cleanup",
            )
            for operation in plan_value.operations
        ),
    )


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
        settings_path: str | Path | None = None,
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
        self.settings_path = (
            self.ledger_path.parent / "settings.json"
            if settings_path is None
            else Path(settings_path).resolve()
        )
        if self.settings_path in {self.ledger_path, self.history_path}:
            raise ValueError(
                "semantic settings must use a path distinct from both databases"
            )
        self._settings_store = SemanticSettingsStore(self.settings_path)
        self.clock = clock or SystemClock()
        self.history_window_policy = DEFAULT_HISTORY_WINDOW_POLICY
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
        self._close_lock = Lock()
        self._database_pair_lock = Lock()
        self._ledger_reader_lock = Lock()
        self._history_reader_lock = Lock()
        self._ledger_reader: LedgerRepository | None = None
        self._history_reader: HistoryRepository | None = None
        self._plans: dict[str, PlanArtifact] = {}
        self._execution_details: dict[str, ExecutionDetails] = {}
        self._inventory_details: dict[str, InventoryDetails] = {}
        self._execution_started: dict[str, datetime] = {}
        self._history_store: HistoryStore | None = None
        self._closing = False
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
            verifier=verify_post_copy,
            verifier_context=lambda context: VerifierContext(
                run=context,
                clock=self.clock,
                hasher_factory=self._hasher_factory,
            ),
            open_recording=self._open_recording,
            save_plan=self.save_plan,
            save_execution_details=self._save_execution_details,
            finish_existing_recording=self._finish_existing_recording,
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

    def validate_database_contracts(self) -> DatabasePairContract:
        """Return the read-only ledger/history pair classification."""

        self._require_open()
        with self._database_pair_lock:
            return validate_database_pair(self.ledger_path, self.history_path)

    def initialize_database_contracts(self) -> DatabasePairContract:
        """Coordinately initialize a fresh pair without resetting existing data."""

        self._require_open()
        with self._database_pair_lock:
            return initialize_database_pair(self.ledger_path, self.history_path)

    def _ensure_database_contracts(self) -> DatabasePairContract:
        with self._database_pair_lock:
            return ensure_database_pair(self.ledger_path, self.history_path)

    def create_plan_request(
        self,
        request_id: str,
        source_path: str,
        target_path: str,
        *,
        deletion_policy: str | None = None,
    ) -> PlanRequest:
        """Capture one immutable semantic-settings snapshot for planning."""

        self._require_open()
        settings = self._settings_store.read()
        if deletion_policy is not None:
            settings = replace(
                settings,
                deletion_policy=DeletionPolicy(deletion_policy),
            )
        return PlanRequest(
            request_id=request_id,
            source_path=source_path,
            target_path=target_path,
            options=settings.to_sync_options(),
        )

    def read_semantic_settings(self) -> SemanticSettingsView:
        self._require_open()
        return _semantic_settings_view(self._settings_store.read())

    def commit_semantic_settings(
        self,
        patch: SemanticSettingsPatchView,
    ) -> SemanticSettingsView:
        self._require_open()
        if not isinstance(patch, SemanticSettingsPatchView):
            raise TypeError(
                "semantic settings commit requires SemanticSettingsPatchView"
            )
        updated = self._settings_store.commit(_semantic_settings_patch(patch))
        return _semantic_settings_view(updated)

    def prepare_plan(self, request: object) -> WorkflowPreparation:
        self._require_open()
        if not isinstance(request, PlanRequest):
            raise TypeError("sync planning requires PlanRequest")
        self._validate_database_roots(
            (request.source_path, request.target_path)
        )
        contract = self.validate_database_contracts()
        if contract.state is DatabasePairState.REFUSED:
            raise DatabasePairRefusedError(contract)
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
        self._ensure_database_contracts()
        return WorkflowPreparation(encode_execution_request(request), resources)

    def open_execution(self, payload: bytes) -> _ExecutionInvocation:
        self._require_open()
        request = decode_execution_request(payload)
        resumed = request.started_at is not None
        started_at = request.started_at or self.clock.now()
        _require_utc(started_at, "execution start")
        request = ExecutionRequest(request.continuation, started_at)
        if resumed:
            self._validate_execution_start(request)
        return _ExecutionInvocation(
            request,
            self._deps,
            resumed=resumed,
            claim_start=self._claim_execution_start,
            release_start=self._release_execution_start,
        )

    def settle_canceled_execution(
        self,
        payload: bytes,
        disposition: Disposition,
    ) -> OperationResult:
        """Settle a started execution cancellation from its exact continuation."""

        self._require_open()
        request = decode_execution_request(payload)
        if request.started_at is None:
            raise ValueError(
                "started execution cancellation lacks its original start time"
            )
        _require_utc(request.started_at, "execution start")
        with self._lock:
            established = self._execution_started.get(
                str(request.execution_set.run_id)
            )
            if established != request.started_at:
                raise ValueError(
                    "canceled execution does not match runtime custody"
                )
        try:
            return settle_canceled_sync_execution(
                request.continuation,
                disposition,
                self._deps,
            )
        finally:
            self._release_execution_start(request)

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
        self._ensure_database_contracts()
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

    def settle_canceled_baseline(
        self,
        payload: bytes,
        disposition: Disposition,
    ) -> OperationResult:
        return self._settle_canceled_integrity(
            payload,
            disposition,
            IntegrityMode.BASELINE,
        )

    def settle_canceled_verify(
        self,
        payload: bytes,
        disposition: Disposition,
    ) -> OperationResult:
        return self._settle_canceled_integrity(
            payload,
            disposition,
            IntegrityMode.VERIFY,
        )

    def settle_canceled_rebaseline(
        self,
        payload: bytes,
        disposition: Disposition,
    ) -> OperationResult:
        return self._settle_canceled_integrity(
            payload,
            disposition,
            IntegrityMode.REBASELINE,
        )

    def audit_observer(self, record: SessionRecord) -> HistoryObserver | None:
        if record.payload is None:
            raise ValueError("audit observer requires a nonterminal payload")
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

    def get_plan_review(
        self,
        request_id: str,
        *,
        user_deselected: frozenset[str] = frozenset(),
        expected_artifact: object | None = None,
    ) -> PlanReview:
        artifact = self.get_plan(request_id)
        if expected_artifact is not None and artifact is not expected_artifact:
            raise ValueError("plan changed before review projection")
        plan_value = artifact.plan
        decision = derive_execution_selection(
            plan_value,
            user_deselected=user_deselected,
        )
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
            semantic_settings=_sync_options_view(
                artifact.request.options
            ),
            fingerprint=str(plan_value.fingerprint),
            selection_digest_hex=selection_digest(decision.selection).hex(),
            required_bytes=scalar_64_to_text(
                calculate_required_bytes(
                    tuple(
                        operation
                        for operation in plan_value.operations
                        if operation.op_id in decision.selection
                    ),
                    target_profile=plan_value.target_profile,
                    trash_on_update=plan_value.trash_on_update,
                ),
                "plan review required_bytes",
            ),
            free_bytes=(
                None
                if artifact.verdict.observed.free_space is None
                else scalar_64_to_text(
                    artifact.verdict.observed.free_space,
                    "plan review free_bytes",
                )
            ),
            reclaimable_temp_bytes=scalar_64_to_text(
                artifact.verdict.observed.reclaimable_temp_bytes,
                "plan review reclaimable_temp_bytes",
            ),
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
                    content_bytes=scalar_64_to_text(
                        operation.content_bytes,
                        "plan operation content_bytes",
                    ),
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
        verify_after_execute: bool = False,
        user_deselected: frozenset[str] = frozenset(),
        expected_artifact: object | None = None,
    ) -> ExecutionRequest:
        artifact = self.get_plan(request_id)
        if expected_artifact is not None and artifact is not expected_artifact:
            raise ValueError("plan changed before selection commitment")
        if not artifact.verdict.ok:
            raise ValueError("a refused plan cannot be committed")
        selection = derive_execution_selection(
            artifact.plan,
            user_deselected=user_deselected,
        ).selection
        if not selection:
            raise ValueError("Nothing is selected to synchronize")
        committed = committed_at or self.clock.now()
        _require_utc(committed, "commitment")
        commitment = Commitment(
            artifact.plan.fingerprint,
            selection_digest(selection),
            committed,
        )
        token = run_id or uuid4().hex
        return ExecutionRequest(
            ExecuteContinuation(
                ExecutionSet(
                    artifact.plan,
                    selection,
                    token,
                    commitment=commitment,
                    user_deselected=user_deselected,
                ),
                verify_after_execute=verify_after_execute,
            )
        )

    def get_execution_details(self, run_id: str) -> ExecutionDetails:
        with self._lock:
            details = self._execution_details.get(run_id)
        return details or ExecutionDetails(run_id)

    def drop_execution_details(self, run_id: str) -> None:
        with self._lock:
            self._execution_details.pop(run_id, None)

    def get_inventory_details(self, request_id: str) -> InventoryDetails:
        with self._lock:
            details = self._inventory_details.get(request_id)
        if details is None:
            raise KeyError(request_id)
        return details

    def drop_inventory_details(self, request_id: str) -> None:
        with self._lock:
            self._inventory_details.pop(request_id, None)

    def list_inventory(
        self, location_id: int, selected_paths: tuple[str, ...] = ()
    ) -> tuple[InventorySnapshot, ...]:
        with self._ledger_read() as repository:
            return repository.get_inventory(
                location_id,
                None if not selected_paths else selected_paths,
            )

    def mapping_ids_for_location(self, location_id: int) -> tuple[int, ...]:
        with self._ledger_read() as repository:
            return repository.mapping_ids_for_location(location_id)

    def list_stale_inventory(
        self, location_id: int, verified_before: datetime
    ) -> tuple[InventorySnapshot, ...]:
        self._require_open()
        _require_utc(verified_before, "stale inventory cutoff")
        with self._ledger_read() as repository:
            return repository.get_stale_inventory(location_id, verified_before)

    def list_unacknowledged_missing(
        self, location_id: int
    ) -> tuple[InventorySnapshot, ...]:
        with self._ledger_read() as repository:
            return repository.get_unacknowledged_missing(location_id)

    def acknowledge_inventory(
        self,
        command_id: str,
        location_id: int,
        row_id: str,
        *,
        changed_at: datetime | None = None,
    ) -> RecordDisposition:
        self._require_open()
        self._ensure_database_contracts()
        return self._change_inventory_visibility(
            command_id,
            location_id,
            row_id,
            InventoryVisibilityAction.ACKNOWLEDGE,
            changed_at=changed_at,
        )

    def restore_inventory(
        self,
        command_id: str,
        location_id: int,
        row_id: str,
        *,
        changed_at: datetime | None = None,
    ) -> RecordDisposition:
        self._require_open()
        self._ensure_database_contracts()
        return self._change_inventory_visibility(
            command_id,
            location_id,
            row_id,
            InventoryVisibilityAction.RESTORE,
            changed_at=changed_at,
        )

    def _change_inventory_visibility(
        self,
        command_id: str,
        location_id: int,
        row_id: str,
        action: InventoryVisibilityAction,
        *,
        changed_at: datetime | None,
    ) -> RecordDisposition:
        at = self.clock.now() if changed_at is None else changed_at
        _require_utc(at, "inventory visibility change")
        return change_inventory_visibility(
            command_id,
            location_id,
            row_id,
            action,
            ledger_path=self.ledger_path,
            clock=self.clock,
            changed_at=at,
        )

    def list_history(self, limit: int = 50) -> tuple[HistoryRunSummaryView, ...]:
        with self._history_read() as repository:
            if repository is None:
                return ()
            return tuple(
                _history_summary_view(item)
                for item in repository.list_summaries(limit)
            )

    def get_history_summary(self, run_token: str) -> HistoryRunSummaryView:
        with self._history_read() as repository:
            if repository is None:
                raise KeyError(run_token)
            return _history_summary_view(repository.get_summary(run_token))

    def get_history_items(
        self,
        run_token: str,
        *,
        after_order: int = 0,
        through_order: int | None = None,
        limit: int = 256,
    ) -> HistoryItemPageView:
        with self._history_read() as repository:
            if repository is None:
                raise KeyError(run_token)
            return _history_item_page_view(
                repository.get_item_page(
                    run_token,
                    after_order=after_order,
                    through_order=through_order,
                    limit=limit,
                )
            )

    def get_history_events(
        self,
        run_token: str,
        *,
        after_seq: int = 0,
        through_seq: int | None = None,
        limit: int = 256,
    ) -> HistoryEventPageView:
        with self._history_read() as repository:
            if repository is None:
                raise KeyError(run_token)
            return _history_event_page_view(
                repository.get_event_page(
                    run_token,
                    after_seq=after_seq,
                    through_seq=through_seq,
                    limit=limit,
                )
            )

    @contextmanager
    def _ledger_read(self) -> Iterator[LedgerRepository]:
        with self._ledger_reader_lock:
            self._require_open()
            if self._ledger_reader is None:
                self._ledger_reader = LedgerRepository(self.ledger_path)
            try:
                yield self._ledger_reader
            except BaseException as error:
                if self._close_failed_reader(self._ledger_reader, error):
                    self._ledger_reader = None
                raise

    @contextmanager
    def _history_read(self) -> Iterator[HistoryRepository | None]:
        with self._history_reader_lock:
            self._require_open()
            if self._history_reader is None:
                if not self.history_path.exists():
                    yield None
                    return
                self._history_reader = HistoryRepository(
                    self.history_path,
                    classification_query=_HISTORY_CLASSIFICATION_QUERY,
                )
            try:
                yield self._history_reader
            except BaseException as error:
                if self._close_failed_reader(self._history_reader, error):
                    self._history_reader = None
                raise

    def _close_failed_reader(
        self, reader: LedgerRepository | HistoryRepository, primary: BaseException,
    ) -> bool:
        try:
            reader.close()
        except BaseException as cleanup:
            with self._lock:
                self._closing = True
            if isinstance(primary, Exception) and not isinstance(cleanup, Exception):
                raise cleanup from primary
            primary.add_note("runtime database reader close was incomplete")
            return False
        return True

    def close(self) -> None:
        with self._close_lock:
            with self._lock:
                if self._closed:
                    return
                self._closing = True
                store = self._history_store
            if store is not None:
                store.close()
                with self._lock:
                    self._history_store = None
            with self._ledger_reader_lock:
                if self._ledger_reader is not None:
                    self._ledger_reader.close()
                    self._ledger_reader = None
            with self._history_reader_lock:
                if self._history_reader is not None:
                    self._history_reader.close()
                    self._history_reader = None
            with self._lock:
                self._plans.clear()
                self._execution_details.clear()
                self._inventory_details.clear()
                self._execution_started.clear()
                self._closed = True

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
        self._ensure_database_contracts()
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

    def _settle_canceled_integrity(
        self,
        payload: bytes,
        disposition: Disposition,
        mode: IntegrityMode,
    ) -> OperationResult:
        self._require_open()
        request = decode_integrity_request(payload)
        if request.mode is not mode:
            raise ValueError(
                f"{mode.value} cancellation payload contains {request.mode.value}"
            )
        return settle_canceled_integrity(request, disposition)

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
            found = repository.find_current_mapping(
                source.volume_id,
                source_relative,
                target.volume_id,
                target_relative,
                target_path_keys=tuple(record.rel_path_key for record in target.files),
                source_identities=frozenset(
                    record.file_identity
                    for record in source.files
                    if record.file_identity is not None
                ),
                target_identities=frozenset(
                    record.file_identity
                    for record in target.files
                    if record.file_identity is not None
                ),
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

    def _validate_execution_start(self, request: ExecutionRequest) -> None:
        started_at = request.started_at
        if started_at is None:
            raise ValueError("execution start time was not established")
        run_token = str(request.execution_set.run_id)
        with self._lock:
            established = self._execution_started.get(run_token)
        if established is None:
            raise ValueError(
                "resumed execution was not established by this runtime"
            )
        if established != started_at:
            raise ValueError(
                "resumed execution start time does not match custody"
            )

    def _claim_execution_start(
        self,
        request: ExecutionRequest,
        resumed: bool,
    ) -> None:
        started_at = request.started_at
        if started_at is None:
            raise ValueError("execution start time was not established")
        run_token = str(request.execution_set.run_id)
        with self._lock:
            established = self._execution_started.get(run_token)
            if resumed:
                if established is None:
                    raise ValueError(
                        "resumed execution was not established by this runtime"
                    )
                if established != started_at:
                    raise ValueError(
                        "resumed execution start time does not match custody"
                    )
            elif established is not None:
                raise ValueError("execution run token is already in use")
            else:
                self._execution_started[run_token] = started_at

    def _release_execution_start(self, request: ExecutionRequest) -> None:
        started_at = request.started_at
        if started_at is None:
            return
        run_token = str(request.execution_set.run_id)
        with self._lock:
            if self._execution_started.get(run_token) == started_at:
                self._execution_started.pop(run_token, None)

    def _finish_existing_recording(
        self,
        xset: ExecutionSet,
        status: SessionState,
        recording: RecordingStatus,
    ) -> None:
        run_token = str(xset.run_id)
        with self._lock:
            if run_token not in self._execution_started:
                raise RuntimeError(
                    "execution start time was not established"
                )
        with LedgerRecorder(
            self.ledger_path,
            clock=self.clock,
        ) as recorder:
            recorder.finish_run(
                FinishRunCommand(
                    run_token,
                    status,
                    recording,
                    self.clock.now(),
                )
            )
        with self._lock:
            self._execution_started.pop(run_token, None)

    def save_plan(self, artifact: PlanArtifact) -> None:
        with self._lock:
            self._plans[artifact.request.request_id] = artifact

    def get_plan(self, request_id: str) -> PlanArtifact:
        with self._lock:
            artifact = self._plans.get(request_id)
        if artifact is None:
            raise KeyError(request_id)
        return artifact

    def drop_plan(self, request_id: str) -> None:
        with self._lock:
            self._plans.pop(request_id, None)

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
        try:
            validate_database_path(
                self.settings_path,
                managed_roots=managed_roots,
            )
        except ValueError as error:
            raise ValueError(
                "semantic settings must be outside managed roots"
            ) from error

    def _ensure_history_store(self, managed_roots: tuple[str, ...]) -> HistoryStore:
        self._validate_database_roots(managed_roots)
        with self._lock:
            self._require_open()
            if self._history_store is None:
                self._history_store = HistoryStore(
                    self.history_path,
                    clock=self.clock,
                    window_policy=self.history_window_policy,
                    retry_timeout_seconds=HISTORY_WRITER_RETRY_TIMEOUT_SECONDS,
                    managed_roots=managed_roots,
                )
            return self._history_store

    def _require_open(self) -> None:
        if self._closed or self._closing:
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
    def __init__(
        self,
        request: ExecutionRequest,
        deps: SyncDependencies,
        *,
        resumed: bool,
        claim_start: Callable[[ExecutionRequest, bool], None],
        release_start: Callable[[ExecutionRequest], None],
    ) -> None:
        self._request = request
        self._continuation = request.continuation
        self._deps = deps
        self._resumed = resumed
        self._claim_start = claim_start
        self._release_start = release_start
        self._started = False

    def run(self, context) -> object:
        self._ensure_started()
        paused = False
        try:
            return run_execution(
                self._continuation,
                context,
                self._deps,
                continuation_sink=self._capture_continuation,
                resumed=self._resumed,
            )
        except PauseRequested:
            paused = True
            raise
        finally:
            if not paused:
                self._release_start(self._request)
                self._started = False

    def snapshot(self) -> bytes:
        self._ensure_started()
        return encode_execution_request(
            ExecutionRequest(
                self._continuation,
                self._request.started_at,
            )
        )

    def _capture_continuation(
        self,
        continuation,
    ) -> None:
        self._continuation = continuation

    def _ensure_started(self) -> None:
        if self._started:
            return
        self._claim_start(self._request, self._resumed)
        self._started = True


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
        self._recording = request.recording
        self._recording_issues = request.recording_issues
        self._omitted_detail_count = request.omitted_detail_count

    def run(self, context) -> object:
        return run_integrity(
            self._request,
            context,
            self._deps,
            selection_sink=self._capture_selection,
            recording_sink=self._capture_recording,
        )

    def snapshot(self) -> bytes:
        completed_bytes = self._request.completed_bytes
        processed_bytes = self._request.processed_bytes
        bytes_total_high_water = self._request.bytes_total_high_water
        if self._selection is not None:
            completed = self._selection.completed_bytes
            completed_bytes = tuple(
                (item.item_id, completed[item.item_id])
                for item in self._selection.items
                if item.item_id in completed
            )
            processed_bytes = self._selection.processed_bytes
            bytes_total_high_water = self._selection.bytes_total_high_water
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
                bytes_total_high_water=bytes_total_high_water,
                recording=self._recording,
                recording_issues=self._recording_issues,
                omitted_detail_count=self._omitted_detail_count,
                refresh_generation=require_safe_int(
                    self._request.refresh_generation + 1,
                    "inventory refresh generation",
                ),
            )
        )

    def _capture_selection(self, selection: IntegritySelection) -> None:
        self._selection = selection

    def _capture_recording(
        self,
        recording: RecordingStatus,
        recording_issues: tuple[TaskRecordingIssue, ...],
        omitted_detail_count: int,
    ) -> None:
        if recording is RecordingStatus.DEGRADED:
            self._recording = RecordingStatus.DEGRADED
        self._recording_issues = recording_issues
        self._omitted_detail_count = omitted_detail_count


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
        with self._runtime._lock:
            self._runtime._execution_started.pop(
                str(self._xset.run_id),
                None,
            )

    def __enter__(self) -> _LedgerRunRecording:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._owner.close()


def _history_summary_view(value: HistoryRunSummary) -> HistoryRunSummaryView:
    terminal_values = (
        value.ended_at,
        value.filesystem_status,
        value.recording,
        value.audit,
        value.disposition,
        value.canceled,
        value.bytes_done,
        value.bytes_total,
        value.recording_degraded_items,
        value.omitted_detail_count,
    )
    if value.finalized and any(item is None for item in terminal_values):
        raise ValueError("finalized history has incomplete terminal fields")
    if not value.finalized and any(item is not None for item in terminal_values):
        raise ValueError("incomplete history exposes terminal fields")
    phases = tuple(snapshot.phase for snapshot in value.phases)
    integrity, terminal_headline = classify_result_facts(
        _history_classification_facts(value, phases)
    )
    headline = (
        terminal_headline.value
        if value.finalized
        else "incomplete"
    )
    return HistoryRunSummaryView(
        run_token=value.run_token,
        session_id=value.session_id,
        activity_kind=value.activity_kind,
        subject_kind=value.subject_kind,
        subject_id=value.subject_id,
        source_context=value.source_context,
        target_context=value.target_context,
        created_at=value.created_at,
        started_at=value.started_at,
        ended_at=value.ended_at,
        completion_status="finalized" if value.finalized else "incomplete",
        current_state=value.current_state.value,
        current_phase=value.current_phase,
        last_committed_seq=value.last_committed_seq,
        item_count=value.item_count,
        duplicate_item_count=value.duplicate_item_count,
        rejected_event_count=value.rejected_event_count,
        last_committed_at=value.last_committed_at,
        filesystem_status=(
            None
            if value.filesystem_status is None
            else value.filesystem_status.value
        ),
        recording_status=(
            None if value.recording is None else value.recording.value
        ),
        audit_status=None if value.audit is None else value.audit.value,
        disposition=value.disposition,
        canceled=value.canceled,
        integrity_status=integrity,
        headline=headline,
        bytes_done=(
            None
            if value.bytes_done is None
            else scalar_64_to_text(value.bytes_done, "history bytes_done")
        ),
        bytes_total=(
            None
            if value.bytes_total is None
            else scalar_64_to_text(value.bytes_total, "history bytes_total")
        ),
        recording_degraded_items=value.recording_degraded_items,
        recording_issues=tuple(
            RecordingIssueView(issue.reason.value, issue.detail)
            for issue in value.recording_issues
        ),
        omitted_detail_count=value.omitted_detail_count,
        review_refusal=(
            None
            if value.review_fact_limit is None
            else ReviewFactLimitView(
                reason=value.review_fact_limit.reason,
                tree_kind=value.review_fact_limit.tree_kind.value,
                population=value.review_fact_limit.population.value,
                axis=value.review_fact_limit.axis.value,
                row_limit=value.review_fact_limit.row_limit,
                byte_limit=(
                    None
                    if value.review_fact_limit.byte_limit is None
                    else scalar_64_to_text(
                        value.review_fact_limit.byte_limit,
                        "history review byte_limit",
                    )
                ),
            )
        ),
        succeeded_count=value.succeeded_count,
        skipped_count=value.skipped_count,
        failed_count=value.failed_count,
        canceled_count=value.canceled_count,
        deferred_count=value.deferred_count,
        blocked_count=value.blocked_count,
        phases=tuple(phase_result_view(phase) for phase in phases),
        error=None
        if value.error_type is None
        else f"{value.error_type}: {value.error_message or ''}".rstrip(),
    )


def _history_item_page_view(value: HistoryItemPage) -> HistoryItemPageView:
    return HistoryItemPageView(
        run_token=value.run_token,
        through_order=value.through_order,
        next_after_order=value.next_after_order,
        has_more=value.has_more,
        items=tuple(
            HistoryItemView(
                item_order=snapshot.item_order,
                event_seq=snapshot.event_seq,
                item=result_item_view(snapshot.item),
            )
            for snapshot in value.items
        ),
    )


def _history_event_page_view(value: HistoryEventPage) -> HistoryEventPageView:
    return HistoryEventPageView(
        run_token=value.run_token,
        through_seq=value.through_seq,
        next_after_seq=value.next_after_seq,
        has_more=value.has_more,
        events=tuple(
            HistoryEventView(
                session_id=value.session_id,
                sequence=snapshot.event_seq,
                at=snapshot.event_at.isoformat(),
                schema_version=snapshot.schema_version,
                body_type=snapshot.body_type,
                disposition=snapshot.disposition.value,
                body=(
                    None
                    if snapshot.envelope is None
                    else session_event_view(snapshot.envelope).body
                ),
                payload_hash=snapshot.payload_hash.hex(),
                receipt_hash=snapshot.receipt_hash.hex(),
                duplicate_of_seq=snapshot.duplicate_of_seq,
                rejection_reason=snapshot.rejection_reason,
            )
            for snapshot in value.events
        ),
    )


def _history_classification_facts(
    value: HistoryRunSummary, phases: tuple[PhaseResult, ...]
) -> ResultClassificationFacts:
    aggregate = value.classification
    verify_phase = next(
        (phase for phase in phases if phase.phase == IntegrityMode.VERIFY.value),
        None,
    )
    return ResultClassificationFacts(
        filesystem=(
            value.current_state.value
            if value.filesystem_status is None
            else value.filesystem_status.value
        ),
        recording=(
            RecordingStatus.OK.value
            if value.recording is None
            else value.recording.value
        ),
        audit=(
            RecordingStatus.OK.value
            if value.audit is None
            else value.audit.value
        ),
        canceled=bool(value.canceled),
        operation_results=aggregate.operation_results,
        selected_operation_count=aggregate.selected_operation_count,
        selected_other_operation_count=(
            aggregate.selected_other_operation_count
        ),
        integrity_results=aggregate.integrity_results,
        verify_phase_status=(
            None if verify_phase is None else verify_phase.status.value
        ),
        verify_phase_baseline=aggregate.verify_phase_baseline,
    )


def _semantic_settings_view(
    value: SemanticSettings,
) -> SemanticSettingsView:
    return _sync_options_view(value.to_sync_options())


def _sync_options_view(value: SyncOptions) -> SemanticSettingsView:
    return SemanticSettingsView(
        filters=value.filters.patterns,
        deletion_policy=value.deletion_policy.value,
        trash_on_update=value.trash_on_update,
        preservation=PreservationSettingsView(
            preserve_ads=value.preservation.preserve_ads,
            preserve_created=value.preservation.preserve_created,
            preserve_acl=value.preservation.preserve_acl,
        ),
        propagate_source_casing=value.propagate_source_casing,
    )


def _semantic_settings_patch(
    value: SemanticSettingsPatchView,
) -> SemanticSettingsPatch:
    preservation = value.preservation
    return SemanticSettingsPatch(
        filters=(
            None if value.filters is None else FilterSet(value.filters)
        ),
        deletion_policy=(
            None
            if value.deletion_policy is None
            else DeletionPolicy(value.deletion_policy)
        ),
        trash_on_update=value.trash_on_update,
        preservation=(
            None
            if preservation is None
            else PreservationPolicy(
                preserve_ads=preservation.preserve_ads,
                preserve_created=preservation.preserve_created,
                preserve_acl=preservation.preserve_acl,
            )
        ),
        propagate_source_casing=value.propagate_source_casing,
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
