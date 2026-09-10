"""Shared process-local facade for NamiSync interface adapters."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from hashlib import sha256
from json import dumps
from pathlib import Path
from threading import Lock
from typing import Callable, Never
from uuid import uuid4

from namisync.dispatcher import (
    AdmissionAttachment,
    Dispatcher,
    EventStream,
    PreparedSession,
    retire_exception_graph,
    SessionNotFound,
    WorkflowRegistration,
)
from namisync.workflows import (
    BASELINE_KIND,
    DatabasePairContract,
    EXECUTION_KIND,
    DeletionPolicy,
    FilterSet,
    HistoryEventPageView,
    HistoryItemPageView,
    HistoryRunSummaryView,
    INVENTORY_KIND,
    PLAN_KIND,
    PreservationPolicy,
    REBASELINE_KIND,
    VERIFY_KIND,
    InventoryRequest,
    LocationCandidate,
    LocationCandidateResult,
    LocationCandidateState,
    LocationBinding,
    LocalWorkflowRuntime,
    RememberedLocations,
    SyncOptions,
    VolumeResolutionRequired,
    VolumeResolutionState,
    default_database_paths,
    integrity_request,
)
from namisync.workflows.node_tree import (
    NodeTree,
    NodeTreeKind,
    NodeTreeMember,
    build_node_tree,
)
from namisync.workflows.runtime import (
    HISTORY_WRITER_RETRY_TIMEOUT_SECONDS,
    build_plan_node_tree,
    execution_selection_digest_hex,
)
from namisync.workflows.selection import (
    apply_selection_mutation,
    derive_execution_selection,
)
from namisync.workflows.views import (
    InventoryRowView,
    OperationResultView,
    PreservationSettingsView,
    SemanticSettingsPatchView,
    SemanticSettingsView,
    SetupOptionsView,
    SessionEventView,
    SessionRecordView,
    inventory_row_view,
    session_event_view,
    session_record_view,
    terminal_result_event_data,
)

from namisync.interfaces.session_observer import (
    SessionObserver,
    SessionSink,
    SessionUpdate,
)
from namisync.interfaces.task_lifecycle import (
    LifecycleAssociationError,
    LifecycleReceiptConflictError,
    LifecycleTaskCapacityError,
    PlanToken,
    StartReceipt,
    TaskLifecycle,
)
from namisync.interfaces.task_port import (
    TaskCloseView,
    TaskDeliveryFactory,
    TaskDeliverySink,
    TaskIntentConflictError,
    PlanAgainReadinessView,
    TaskSessionReleaseView,
    TaskShellDeliveryFactory,
    TaskShellView,
    TaskStartView,
    TaskSetupLocationView,
    TaskSetupSnapshotView,
    TaskStartOutcome,
    TaskTerminalDelivery,
    TaskUnavailableError,
)


FINALIZATION_TIMEOUT_MARGIN_SECONDS = 1.0
# Keep ordinary history retry inside the audit cutoff, and shutdown long enough
# for a late pump claim to consume both bounds in sequence.
AUDIT_FINALIZATION_TIMEOUT_SECONDS = (
    HISTORY_WRITER_RETRY_TIMEOUT_SECONDS + FINALIZATION_TIMEOUT_MARGIN_SECONDS
)
SERVICE_CLOSE_TIMEOUT_SECONDS = (
    AUDIT_FINALIZATION_TIMEOUT_SECONDS
    + HISTORY_WRITER_RETRY_TIMEOUT_SECONDS
    + FINALIZATION_TIMEOUT_MARGIN_SECONDS
)
# Producer backpressure only. A wedged audit writer must degrade the audit axis
# quickly rather than stall the emitting workflow thread, so this bound is
# deliberately independent of the finalization cutoff above and must not scale
# with the history writer's retry bound.
AUDIT_OFFER_TIMEOUT_SECONDS = 5.0
_SERVICE_OBSERVER_CLEANUP_FAILURE = "service observer cleanup failed"
_SERVICE_OBSERVER_CLEANUP_INTERRUPTED = (
    "service observer cleanup was interrupted"
)
def _raise_service_observer_failure(*, interrupted: bool) -> Never:
    if interrupted:
        raise KeyboardInterrupt(_SERVICE_OBSERVER_CLEANUP_INTERRUPTED) from None
    raise RuntimeError(_SERVICE_OBSERVER_CLEANUP_FAILURE) from None


class SyncPathInputError(ValueError):
    """A source/target pair failed interface-level path validation."""

    def __init__(
        self,
        detail: str,
        result: LocationCandidateResult | None = None,
    ) -> None:
        super().__init__(detail)
        self.result = result


class CommandIdConflictError(ValueError):
    """A receipted command id was reused for different admitted intent."""


@dataclass(frozen=True, slots=True)
class PlanSession:
    request_id: str
    session_id: str


@dataclass(frozen=True, slots=True)
class ExecutionSession:
    run_id: str
    session_id: str


@dataclass(frozen=True, slots=True)
class LocationSession:
    request_id: str
    session_id: str


@dataclass(frozen=True, slots=True)
class LocationResolutionView:
    state: str
    root_path: str | None
    location_id: int | None
    selected_mount: str | None
    candidates: tuple[str, ...]
    detail: str | None


@dataclass(frozen=True, slots=True)
class DatabaseContractView:
    state: str
    reason: str | None
    reset_direction: str | None


class LocationResolutionError(ValueError):
    """An explicit location could not be safely bound before admission."""

    def __init__(self, resolution: LocationResolutionView) -> None:
        super().__init__(
            resolution.state
            if resolution.detail is None
            else f"{resolution.state}: {resolution.detail}"
        )
        self.resolution = resolution


@dataclass(frozen=True, slots=True)
class InventoryDetailsView:
    request_id: str
    state: str
    root_path: str | None
    location_id: int | None
    selected_mount: str | None
    candidates: tuple[str, ...]
    detail: str | None
    selected_paths: tuple[str, ...]
    observed_count: int
    missing_count: int
    complete: bool
    warnings: tuple[ScanWarningView, ...] = ()


@dataclass(frozen=True, slots=True)
class ScanWarningView:
    code: str
    path: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class SelectionOperationView:
    operation_id: str
    selected: bool
    outcome: str | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class SelectionPreviewView:
    request_id: str
    revision: int
    state: str
    selection_digest: str
    selected_operation_ids: tuple[str, ...]
    user_deselected: tuple[str, ...]
    requires_destructive_confirmation: bool
    irreversible_update_count: int
    operations: tuple[SelectionOperationView, ...]


@dataclass(frozen=True, slots=True)
class SelectionMutationView:
    disposition: str
    revision: int
    state: str
    preview: SelectionPreviewView


@dataclass(frozen=True, slots=True)
class ExecutionAdmissionView:
    disposition: str
    revision: int
    state: str
    session: ExecutionSession | None = None


@dataclass(frozen=True, slots=True)
class InventoryDispositionView:
    row_id: str
    disposition: str


@dataclass(frozen=True, slots=True)
class ResultClassificationView:
    headline: str
    filesystem: str
    integrity: str
    recording: str
    audit: str
    disposition: str
    canceled: bool


@dataclass(frozen=True, slots=True)
class ControlView:
    code: str
    session_id: str
    before: str | None
    after: str | None
    detail: str
    accepted: bool


@dataclass(frozen=True, slots=True)
class ShutdownView:
    complete: bool
    unfinished: tuple[str, ...]
    custody_released: bool


@dataclass(slots=True)
class _PlanSelectionState:
    artifact: object
    plan_token: PlanToken
    revision: int = 0
    user_deselected: frozenset[str] = frozenset()
    phase: str = "reviewing"
    execution_session: ExecutionSession | None = None


class NamiSyncService:
    """Compose the local runtime, dispatcher, and session observer."""

    def __init__(
        self,
        ledger_path: str | Path,
        history_path: str | Path,
        *,
        settings_path: str | Path | None = None,
    ) -> None:
        self._runtime = LocalWorkflowRuntime(
            ledger_path,
            history_path,
            settings_path=settings_path,
        )
        self._dispatcher = _dispatcher(self._runtime)
        self._observer = SessionObserver(self._dispatcher)
        self._lock = Lock()
        self._close_lock = Lock()
        self._lifecycle = TaskLifecycle()
        self._plan_selections: dict[str, _PlanSelectionState] = {}
        self._visibility_receipts: dict[str, tuple[object, ...]] = {}
        self._closed = False
        self._shutdown: ShutdownView | None = None
        self._runtime_closed = False
        self._observer_closed = False

    def validate_database_contracts(self) -> DatabaseContractView:
        """Classify the database pair through the read-only workflow preflight."""

        self._require_open()
        return _database_contract_view(
            self._runtime.validate_database_contracts()
        )

    def initialize_database_contracts(self) -> DatabaseContractView:
        """Publish a fresh pair as one coordinated application operation."""

        self._require_open()
        return _database_contract_view(
            self._runtime.initialize_database_contracts()
        )

    def admit_location_candidate(
        self,
        candidate: LocationCandidate,
    ) -> LocationCandidateResult:
        self._require_open()
        return self._runtime.admit_location_candidate(candidate)

    def remembered_locations(self) -> RememberedLocations:
        self._require_open()
        return self._runtime.remembered_locations()

    def read_setup_options(self) -> SetupOptionsView:
        self._require_open()
        return self._runtime.read_setup_options()

    def prepare_setup_options(self, value: SetupOptionsView) -> SetupOptionsView:
        self._require_open()
        return self._runtime.prepare_setup_options(value)

    def start_task_setup_plan(
        self,
        task_id: str,
        source: LocationCandidate,
        target: LocationCandidate,
        options: SetupOptionsView,
        *,
        command_id: str,
        signature: tuple[object, ...],
        delivery_factory: TaskDeliveryFactory,
    ) -> TaskStartView | TaskStartOutcome:
        """Attach one fully admitted plan to an exact published blank task."""

        if not callable(delivery_factory):
            raise TypeError("task delivery factory must be callable")
        with self._lifecycle.command_guard(command_id):
            replay = self._lifecycle.replay_start(
                command_id,
                "task-plan",
                signature,
            )
            if replay is not None:
                if replay.task_id != task_id:
                    raise TaskIntentConflictError("task command intent conflicts")
                return TaskStartView(task_id, replay.request_id, replay.session_id)
            canonical = self._runtime.prepare_setup_options(options)
            source_result = self._runtime.admit_location_candidate(source)
            target_result = self._runtime.admit_location_candidate(target)
            refused = next(
                (
                    value
                    for value in (source_result, target_result)
                    if value.state is not LocationCandidateState.RESOLVED
                ),
                None,
            )
            if refused is not None:
                raise SyncPathInputError(
                    refused.detail or refused.state.value,
                    refused,
                )
            try:
                self._runtime.admit_plan_locations(
                    source_result.root_path,
                    target_result.root_path,
                )
            except ValueError as error:
                raise SyncPathInputError(str(error)) from error
            assert source_result.root_path is not None
            assert target_result.root_path is not None
            assert source_result.binding is not None
            assert target_result.binding is not None
            try:
                self._lifecycle.begin_task_shell_start(
                    task_id,
                    command_id,
                    "task-plan",
                    signature,
                )
            except LifecycleReceiptConflictError:
                raise TaskIntentConflictError("task command intent conflicts") from None
            except LifecycleAssociationError as error:
                raise TaskUnavailableError("task is unavailable") from error
            try:
                sink = delivery_factory(task_id)
                if not callable(sink):
                    raise TypeError("task delivery factory must return a sink")
                request = self._runtime.create_plan_request(
                    uuid4().hex,
                    source_result.root_path,
                    target_result.root_path,
                    options=_setup_sync_options(canonical),
                    source_binding=source_result.binding,
                    target_binding=target_result.binding,
                    verify_after_execute=canonical.verify_after_execute,
                )
                session_id, receipt = self._submit_session(
                    PLAN_KIND,
                    request,
                    effect_kind="task-plan",
                    command_id=command_id,
                    signature=signature,
                    request_id=request.request_id,
                    observation_sink=sink,
                    task_id=task_id,
                )
                start = TaskStartView(task_id, receipt.request_id, str(session_id))
                snapshot = TaskSetupSnapshotView(
                    "frozen",
                    "sync-plan",
                    _setup_location(source_result),
                    _setup_location(target_result),
                    None,
                    canonical,
                )
                return TaskStartOutcome(start, snapshot)
            except BaseException:
                self._lifecycle.abort_task_start(task_id)
                raise

    def start_task_setup_inventory(
        self,
        task_id: str,
        root: LocationCandidate,
        *,
        command_id: str,
        signature: tuple[object, ...],
        delivery_factory: TaskDeliveryFactory,
    ) -> TaskStartView | TaskStartOutcome:
        """Attach one standalone inventory session to a blank task."""

        if not callable(delivery_factory):
            raise TypeError("task delivery factory must be callable")
        with self._lifecycle.command_guard(command_id):
            replay = self._lifecycle.replay_start(
                command_id,
                "task-inventory",
                signature,
            )
            if replay is not None:
                if replay.task_id != task_id:
                    raise TaskIntentConflictError("task command intent conflicts")
                return TaskStartView(task_id, replay.request_id, replay.session_id)
            admitted = self._runtime.admit_location_candidate(root)
            if admitted.state is not LocationCandidateState.RESOLVED:
                raise SyncPathInputError(
                    admitted.detail or admitted.state.value,
                    admitted,
                )
            assert admitted.root_path is not None
            assert admitted.binding is not None
            try:
                self._lifecycle.begin_task_shell_start(
                    task_id,
                    command_id,
                    "task-inventory",
                    signature,
                )
            except LifecycleReceiptConflictError:
                raise TaskIntentConflictError("task command intent conflicts") from None
            except LifecycleAssociationError as error:
                raise TaskUnavailableError("task is unavailable") from error
            try:
                sink = delivery_factory(task_id)
                if not callable(sink):
                    raise TypeError("task delivery factory must return a sink")
                request_id = uuid4().hex
                request = InventoryRequest(
                    request_id=request_id,
                    root_path=(
                        admitted.root_path
                        if admitted.binding.location_id is None
                        else None
                    ),
                    location_id=admitted.binding.location_id,
                    selected_mount=admitted.binding.selected_mount,
                )
                session_id, receipt = self._submit_session(
                    INVENTORY_KIND,
                    request,
                    effect_kind="task-inventory",
                    command_id=command_id,
                    signature=signature,
                    request_id=request_id,
                    observation_sink=sink,
                    task_id=task_id,
                    detail_owner=("inventory", request_id),
                )
                start = TaskStartView(task_id, receipt.request_id, str(session_id))
                snapshot = TaskSetupSnapshotView(
                    "frozen",
                    "inventory",
                    None,
                    None,
                    _setup_location(admitted),
                    None,
                )
                return TaskStartOutcome(start, snapshot)
            except BaseException:
                self._lifecycle.abort_task_start(task_id)
                raise

    def read_plan_setup(self, request_id: str) -> TaskSetupSnapshotView:
        artifact = self._runtime.get_plan(request_id)
        request = artifact.request
        source_binding = request.source_binding
        target_binding = request.target_binding
        readiness = None
        if (
            type(source_binding) is LocationBinding
            and type(target_binding) is LocationBinding
        ):
            source = self._runtime.resolve_reviewed_location(source_binding)
            target = self._runtime.resolve_reviewed_location(target_binding)
            readiness = PlanAgainReadinessView(
                _plan_again_state(source.state),
                tuple(source.candidates),
                _plan_again_state(target.state),
                tuple(target.candidates),
            )
        return TaskSetupSnapshotView(
            "frozen",
            "sync-plan",
            TaskSetupLocationView(
                request.source_path,
                None
                if source_binding is None or source_binding.location_id is None
                else str(source_binding.location_id),
            ),
            TaskSetupLocationView(
                request.target_path,
                None
                if target_binding is None or target_binding.location_id is None
                else str(target_binding.location_id),
            ),
            None,
            _setup_options_from_request(request.options, request.verify_after_execute),
            readiness,
        )

    def start_task_plan_again(
        self,
        old_task_id: str,
        request_id: str,
        *,
        source_mount: str | None,
        target_mount: str | None,
        command_id: str,
        signature: tuple[object, ...],
        delivery_factory: TaskDeliveryFactory,
    ) -> TaskStartView | TaskStartOutcome:
        """Create a new plan task from freshly resolved reviewed identities."""

        if not callable(delivery_factory):
            raise TypeError("task delivery factory must be callable")
        with self._lifecycle.command_guard(command_id):
            replay = self._lifecycle.replay_start(
                command_id,
                "task-plan",
                signature,
            )
            if replay is not None:
                return TaskStartView(
                    replay.task_id,
                    replay.request_id,
                    replay.session_id,
                )
            artifact = self._runtime.get_plan(request_id)
            old = artifact.request
            if (
                type(old.source_binding) is not LocationBinding
                or type(old.target_binding) is not LocationBinding
            ):
                raise SyncPathInputError(
                    "reviewed location identity is unavailable"
                )
            source = self._runtime.resolve_reviewed_location(
                old.source_binding,
                selected_mount=source_mount,
            )
            target = self._runtime.resolve_reviewed_location(
                old.target_binding,
                selected_mount=target_mount,
            )
            refused = next(
                (
                    value
                    for value in (source, target)
                    if value.state is not VolumeResolutionState.RESOLVED
                ),
                None,
            )
            if refused is not None:
                raise SyncPathInputError(
                    refused.detail or _plan_again_state(refused.state)
                )
            assert source.root_path is not None
            assert target.root_path is not None
            try:
                claim = self._lifecycle.begin_task_start(command_id, signature)
            except LifecycleReceiptConflictError:
                raise TaskIntentConflictError("task command intent conflicts") from None
            except LifecycleTaskCapacityError as error:
                raise TaskUnavailableError(str(error)) from None
            if claim.replay is not None:
                replay = claim.replay
                return TaskStartView(
                    claim.task_id,
                    replay.request_id,
                    replay.session_id,
                )
            try:
                sink = delivery_factory(claim.task_id)
                if not callable(sink):
                    raise TypeError("task delivery factory must return a sink")
                request = self._runtime.create_plan_request(
                    uuid4().hex,
                    source.root_path,
                    target.root_path,
                    options=old.options,
                    source_binding=source.binding,
                    target_binding=target.binding,
                    verify_after_execute=old.verify_after_execute,
                )
                session_id, receipt = self._submit_session(
                    PLAN_KIND,
                    request,
                    effect_kind="task-plan",
                    command_id=command_id,
                    signature=signature,
                    request_id=request.request_id,
                    observation_sink=sink,
                    task_id=claim.task_id,
                )
                start = TaskStartView(
                    claim.task_id,
                    receipt.request_id,
                    str(session_id),
                )
                snapshot = TaskSetupSnapshotView(
                    "frozen",
                    "sync-plan",
                    TaskSetupLocationView(
                        source.root_path,
                        None
                        if source.binding.location_id is None
                        else str(source.binding.location_id),
                    ),
                    TaskSetupLocationView(
                        target.root_path,
                        None
                        if target.binding.location_id is None
                        else str(target.binding.location_id),
                    ),
                    None,
                    _setup_options_from_request(
                        old.options,
                        old.verify_after_execute,
                    ),
                )
                return TaskStartOutcome(start, snapshot)
            except BaseException:
                self._lifecycle.abort_task_start(claim.task_id)
                raise

    def start_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None = None,
        command_id: str | None = None,
    ) -> PlanSession:
        signature = (
            source,
            target,
            deletion_policy,
        )
        with self._lifecycle.command_guard(command_id):
            replay = self._replay_start(
                command_id,
                "plan",
                signature,
            )
            if replay is not None:
                return PlanSession(replay.request_id, replay.session_id)
            source_path, target_path = self._admit_plan_locations(source, target)
            request = self._runtime.create_plan_request(
                uuid4().hex,
                source_path,
                target_path,
                deletion_policy=deletion_policy,
            )
            session_id, _receipt = self._submit_session(
                PLAN_KIND,
                request,
                effect_kind="plan",
                command_id=command_id,
                signature=signature,
                request_id=request.request_id,
            )
            result = PlanSession(request.request_id, str(session_id))
            return result

    def start_task_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None,
        command_id: str,
        delivery_factory: TaskDeliveryFactory,
    ) -> TaskStartView:
        """Start one task-bound plan while application state owns its effect."""

        if not callable(delivery_factory):
            raise TypeError("task delivery factory must be callable")
        signature = (source, target, deletion_policy)
        guard = self._lifecycle.command_guard(command_id)
        with guard:
            self._require_plan_location_bounds(source, target)
            try:
                claim = self._lifecycle.begin_task_start(command_id, signature)
            except LifecycleReceiptConflictError:
                raise TaskIntentConflictError(
                    "task command intent conflicts"
                ) from None
            except LifecycleTaskCapacityError as error:
                raise TaskUnavailableError(str(error)) from None
            if claim.replay is not None:
                replay = claim.replay
                return TaskStartView(
                    claim.task_id,
                    replay.request_id,
                    replay.session_id,
                )

            try:
                source_path, target_path = self._admit_plan_locations(
                    source,
                    target,
                )
                sink = delivery_factory(claim.task_id)
                if not callable(sink):
                    raise TypeError("task delivery factory must return a sink")
                request = self._runtime.create_plan_request(
                    uuid4().hex,
                    source_path,
                    target_path,
                    deletion_policy=deletion_policy,
                )
                session_id, receipt = self._submit_session(
                    PLAN_KIND,
                    request,
                    effect_kind="task-plan",
                    command_id=command_id,
                    signature=signature,
                    request_id=request.request_id,
                    observation_sink=sink,
                    task_id=claim.task_id,
                )
                if receipt.task_id != claim.task_id:
                    raise RuntimeError(
                        "task start receipt changed application task identity"
                    )
                return TaskStartView(
                    claim.task_id,
                    receipt.request_id,
                    str(session_id),
                )
            except BaseException:
                self._lifecycle.abort_task_start(claim.task_id)
                raise

    def create_task_shell(
        self,
        command_id: str,
        delivery_factory: TaskShellDeliveryFactory,
    ) -> TaskShellView:
        """Create one process-live task without starting domain work."""

        if not callable(delivery_factory):
            raise TypeError("task shell delivery factory must be callable")
        guard = self._lifecycle.command_guard(command_id)
        with guard:
            try:
                claim = self._lifecycle.begin_task_shell(command_id)
            except LifecycleReceiptConflictError:
                raise TaskIntentConflictError(
                    "task command intent conflicts"
                ) from None
            except LifecycleTaskCapacityError as error:
                raise TaskUnavailableError(str(error)) from None
            try:
                delivery_factory(claim.task_id)
                self._lifecycle.complete_task_shell(claim)
                return TaskShellView(claim.task_id)
            except BaseException:
                self._lifecycle.abort_task_shell(claim)
                raise

    def read_semantic_settings(self) -> SemanticSettingsView:
        self._require_open()
        return self._runtime.read_semantic_settings()

    def commit_semantic_settings(
        self,
        patch: SemanticSettingsPatchView,
    ) -> SemanticSettingsView:
        self._require_open()
        return self._runtime.commit_semantic_settings(patch)

    def get_plan_review(self, request_id: str):
        state, artifact = self._selection_state(request_id)
        with self._lock:
            user_deselected = state.user_deselected
        return self._runtime.get_plan_review(
            request_id,
            user_deselected=user_deselected,
            expected_artifact=artifact,
        )

    def preview_selection(self, request_id: str) -> SelectionPreviewView:
        state, artifact = self._selection_state(request_id)
        with self._lock:
            return self._selection_preview_locked(
                request_id,
                state,
                artifact,
            )

    def mutate_selection(
        self,
        request_id: str,
        expected_revision: int,
        *,
        deselect: tuple[str, ...] = (),
        reselect: tuple[str, ...] = (),
        command_id: str | None = None,
    ) -> SelectionMutationView:
        if type(expected_revision) is not int:
            raise TypeError("expected_revision must be an int")
        state, artifact = self._selection_state(request_id)
        signature = (
            expected_revision,
            tuple(deselect),
            tuple(reselect),
        )
        try:
            claim = self._lifecycle.begin_plan_mutation(
                state.plan_token,
                command_id,
                signature,
            )
        except LifecycleReceiptConflictError as error:
            raise CommandIdConflictError(str(error)) from None
        completed = False
        effect_applied = False
        try:
            with self._lock:
                current = self._plan_selections.get(request_id)
                if current is not state:
                    if current is None:
                        raise KeyError(request_id)
                    return SelectionMutationView(
                        "conflict",
                        current.revision,
                        current.phase,
                        self._selection_preview_locked(
                            request_id,
                            current,
                            current.artifact,
                        ),
                    )
                if claim.replay:
                    response = SelectionMutationView(
                        "noop",
                        state.revision,
                        state.phase,
                        self._selection_preview_locked(
                            request_id,
                            state,
                            artifact,
                        ),
                    )
                elif state.phase != "reviewing":
                    response = SelectionMutationView(
                        "in-flight"
                        if state.phase == "committing"
                        else "frozen",
                        state.revision,
                        state.phase,
                        self._selection_preview_locked(
                            request_id,
                            state,
                            artifact,
                        ),
                    )
                elif expected_revision != state.revision:
                    response = SelectionMutationView(
                        "conflict",
                        state.revision,
                        state.phase,
                        self._selection_preview_locked(
                            request_id,
                            state,
                            artifact,
                        ),
                    )
                else:
                    plan = artifact.plan
                    resolved_deselect = self._resolve_plan_selection_ids(
                        request_id,
                        plan,
                        deselect,
                    )
                    resolved_reselect = self._resolve_plan_selection_ids(
                        request_id,
                        plan,
                        reselect,
                    )
                    state.user_deselected = apply_selection_mutation(
                        plan,
                        state.user_deselected,
                        deselect=frozenset(resolved_deselect),
                        reselect=frozenset(resolved_reselect),
                    )
                    state.revision += 1
                    effect_applied = True
                    response = SelectionMutationView(
                        "applied",
                        state.revision,
                        state.phase,
                        self._selection_preview_locked(
                            request_id,
                            state,
                            artifact,
                        ),
                    )
            if self._runtime.get_plan(request_id) is artifact:
                if effect_applied:
                    self._lifecycle.complete_plan_mutation(claim)
                    completed = True
                return response
            current, current_artifact = self._selection_state(request_id)
            with self._lock:
                return SelectionMutationView(
                    "conflict",
                    current.revision,
                    current.phase,
                    self._selection_preview_locked(
                        request_id,
                        current,
                        current_artifact,
                    ),
                )
        finally:
            if not completed:
                self._lifecycle.abandon_plan_mutation(claim)

    def start_execution(
        self,
        request_id: str,
        *,
        verify_after_execute: bool = False,
        expected_revision: int | None = None,
        destructive_acknowledged: bool = False,
        command_id: str | None = None,
    ) -> ExecutionSession | ExecutionAdmissionView:
        if type(verify_after_execute) is not bool:
            raise TypeError("verify_after_execute must be a bool")
        if expected_revision is not None and type(expected_revision) is not int:
            raise TypeError("expected_revision must be an int or None")
        if type(destructive_acknowledged) is not bool:
            raise TypeError("destructive_acknowledged must be a bool")
        with self._lifecycle.command_guard(command_id):
            return self._start_execution_once(
                request_id,
                verify_after_execute=verify_after_execute,
                expected_revision=expected_revision,
                destructive_acknowledged=destructive_acknowledged,
                command_id=command_id,
            )

    def _start_execution_once(
        self,
        request_id: str,
        *,
        verify_after_execute: bool,
        expected_revision: int | None,
        destructive_acknowledged: bool,
        command_id: str | None,
    ) -> ExecutionSession | ExecutionAdmissionView:
        signature = (
            request_id,
            verify_after_execute,
            expected_revision,
            destructive_acknowledged,
        )
        replay = self._replay_start(
            command_id,
            "execution",
            signature,
        )
        if replay is not None:
            return ExecutionSession(replay.request_id, replay.session_id)

        state, artifact = self._selection_state(request_id)
        with self._lock:
            if state.phase == "committing":
                return ExecutionAdmissionView(
                    "in-flight",
                    state.revision,
                    state.phase,
                )
            if state.phase == "committed":
                return ExecutionAdmissionView(
                    "frozen",
                    state.revision,
                    state.phase,
                    state.execution_session,
                )
            pristine = (
                state.revision == 0
                and not state.user_deselected
                and state.phase == "reviewing"
            )
            if expected_revision is None:
                if not pristine:
                    return ExecutionAdmissionView(
                        "conflict",
                        state.revision,
                        state.phase,
                    )
            elif expected_revision != state.revision:
                return ExecutionAdmissionView(
                    "conflict",
                    state.revision,
                    state.phase,
                )
            decision = derive_execution_selection(
                artifact.plan,
                user_deselected=state.user_deselected,
            )
            if not decision.selection:
                raise ValueError("Nothing is selected to synchronize")
            risk_count = self._irreversible_update_count(
                artifact.plan,
                decision.selection,
            )
            if risk_count and not destructive_acknowledged:
                return ExecutionAdmissionView(
                    "confirmation-required",
                    state.revision,
                    state.phase,
                )
            user_deselected = state.user_deselected
            state.phase = "committing"

        succeeded = False
        result: ExecutionSession | None = None
        try:
            request = self._runtime.commit_plan(
                request_id,
                verify_after_execute=verify_after_execute,
                user_deselected=user_deselected,
                expected_artifact=artifact,
            )
            session_id, _receipt = self._submit_session(
                EXECUTION_KIND,
                request,
                effect_kind="execution",
                command_id=command_id,
                signature=signature,
                request_id=str(request.execution_set.run_id),
                detail_owner=(
                    "execution",
                    str(request.execution_set.run_id),
                ),
            )
            result = ExecutionSession(
                str(request.execution_set.run_id),
                str(session_id),
            )
            succeeded = True
            return result
        finally:
            with self._lock:
                current = self._plan_selections.get(request_id)
                if current is state:
                    state.phase = "committed" if succeeded else "reviewing"
                    state.execution_session = result if succeeded else None

    def start_inventory(
        self,
        *,
        root_path: str | None = None,
        location_id: int | None = None,
        selected_paths: tuple[str, ...] = (),
        selected_mount: str | None = None,
        selected_ids: tuple[str, ...] | None = None,
        command_id: str | None = None,
    ) -> LocationSession:
        signature = (
            root_path,
            location_id,
            tuple(selected_paths),
            selected_mount,
            _canonical_id_gesture(selected_ids),
        )
        with self._lifecycle.command_guard(command_id):
            replay = self._replay_start(
                command_id,
                INVENTORY_KIND,
                signature,
            )
            if replay is not None:
                return LocationSession(replay.request_id, replay.session_id)
            subtree_roots: tuple[str, ...] = ()
            if selected_ids is not None:
                selected_paths, subtree_roots = self._resolve_location_ids(
                    location_id,
                    selected_ids,
                    recursive=True,
                )
            request_id = uuid4().hex
            request = InventoryRequest(
                request_id=request_id,
                root_path=root_path,
                location_id=location_id,
                selected_paths=selected_paths,
                selected_mount=selected_mount,
                subtree_roots=subtree_roots,
            )
            result = self._start_location(
                INVENTORY_KIND,
                request_id,
                request,
                command_id=command_id,
                signature=signature,
            )
            return result

    def start_baseline(
        self,
        *,
        root_path: str | None = None,
        location_id: int | None = None,
        selected_paths: tuple[str, ...] = (),
        selected_mount: str | None = None,
        selected_ids: tuple[str, ...] | None = None,
        command_id: str | None = None,
    ) -> LocationSession:
        return self._start_integrity(
            BASELINE_KIND,
            root_path=root_path,
            location_id=location_id,
            selected_paths=selected_paths,
            selected_mount=selected_mount,
            selected_ids=selected_ids,
            command_id=command_id,
        )

    def start_verify(
        self,
        *,
        root_path: str | None = None,
        location_id: int | None = None,
        selected_paths: tuple[str, ...] = (),
        selected_mount: str | None = None,
        selected_ids: tuple[str, ...] | None = None,
        command_id: str | None = None,
    ) -> LocationSession:
        return self._start_integrity(
            VERIFY_KIND,
            root_path=root_path,
            location_id=location_id,
            selected_paths=selected_paths,
            selected_mount=selected_mount,
            selected_ids=selected_ids,
            command_id=command_id,
        )

    def start_rebaseline(
        self,
        *,
        root_path: str | None = None,
        location_id: int | None = None,
        selected_paths: tuple[str, ...] = (),
        selected_mount: str | None = None,
        selected_ids: tuple[str, ...] | None = None,
        command_id: str | None = None,
    ) -> LocationSession:
        self._require_open()
        if selected_ids is None and not selected_paths:
            raise ValueError("rebaseline requires an explicit selected scope")
        return self._start_integrity(
            REBASELINE_KIND,
            root_path=root_path,
            location_id=location_id,
            selected_paths=selected_paths,
            selected_mount=selected_mount,
            selected_ids=selected_ids,
            command_id=command_id,
        )

    def save_plan(self, artifact: object) -> None:
        self._require_open()
        self._runtime.save_plan(artifact)
        request_id = artifact.request.request_id
        plan_token = self._lifecycle.require_plan(request_id)
        with self._lock:
            prior = self._plan_selections.get(request_id)
            if prior is None:
                self._plan_selections[request_id] = _PlanSelectionState(
                    artifact,
                    plan_token,
                )
            elif prior.artifact is not artifact:
                self._plan_selections[request_id] = _PlanSelectionState(
                    artifact,
                    prior.plan_token,
                    revision=prior.revision + 1,
                )

    def get_plan(self, request_id: str) -> object:
        self._require_open()
        return self._runtime.get_plan(request_id)

    def drop_plan(self, request_id: str) -> None:
        self._require_open()
        try:
            plan_token = self._lifecycle.require_plan(request_id)
        except LifecycleAssociationError:
            plan_token = None
        stale_selection = None
        if plan_token is None:
            with self._lock:
                stale_selection = self._plan_selections.get(request_id)
        retirement = (
            None
            if plan_token is None
            else self._lifecycle.begin_plan_retirement(plan_token)
        )
        if plan_token is not None and retirement is None:
            return
        try:
            self._runtime.drop_plan(request_id)
        except BaseException:
            if retirement is not None:
                self._lifecycle.abandon_plan_retirement(retirement)
            raise
        if retirement is not None:
            self._drop_exact_plan_selection(retirement.token)
            self._lifecycle.complete_plan_retirement(retirement)
        elif stale_selection is not None:
            with self._lock:
                if self._plan_selections.get(request_id) is stale_selection:
                    self._plan_selections.pop(request_id, None)

    def get_session(self, session_id: str) -> SessionRecordView:
        return session_record_view(self._dispatcher.get(session_id))

    def list_sessions(self) -> tuple[SessionRecordView, ...]:
        return tuple(session_record_view(item) for item in self._dispatcher.list())

    def observe(self, session_id: str, sink: SessionSink) -> SessionRecordView:
        self._require_open()
        claim = self._lifecycle.begin_observation(session_id)
        return self._complete_observation_call(
            claim,
            lambda: self._observer.observe(session_id, sink),
        )

    def reobserve(
        self,
        session_id: str,
        sink: SessionSink,
        from_sequence: int,
    ) -> SessionRecordView:
        self._require_open()
        return self._reobserve_session(session_id, sink, from_sequence)

    def reobserve_task(
        self,
        task_id: str,
        session_id: str,
        sink: TaskDeliverySink,
        from_sequence: int,
    ) -> SessionRecordView:
        try:
            return self._reobserve_session(
                session_id,
                sink,
                from_sequence,
                task_id=task_id,
            )
        except LifecycleAssociationError:
            raise TaskUnavailableError("task is unavailable") from None

    def unsubscribe(self, session_id: str) -> None:
        try:
            claim = self._lifecycle.begin_observation(session_id)
        except LifecycleAssociationError:
            return
        try:
            self._observer.release(session_id)
        finally:
            self._lifecycle.end_observation(claim)

    def wait(self, session_id: str) -> SessionRecordView:
        return self._observer.wait(session_id)

    def cancel(self, session_id: str) -> ControlView:
        if not self._has_live_association(session_id):
            return self._missing_control_view(session_id)
        return _control_view(self._dispatcher.cancel(session_id))

    def pause(self, session_id: str) -> ControlView:
        if not self._has_live_association(session_id):
            return self._missing_control_view(session_id)
        return _control_view(self._dispatcher.pause(session_id))

    def resume(self, session_id: str) -> ControlView:
        if not self._has_live_association(session_id):
            return self._missing_control_view(session_id)
        return _control_view(self._dispatcher.resume(session_id))

    def close_session(self, session_id: str) -> None:
        try:
            self._settle_session(
                session_id,
                task_id=None,
                retire_plan=False,
            )
        except LifecycleAssociationError:
            raise SessionNotFound(session_id) from None

    def release_task_session(
        self,
        task_id: str,
        session_id: str,
        delivery: TaskTerminalDelivery,
    ) -> TaskSessionReleaseView:
        if type(delivery) is not TaskTerminalDelivery:
            raise TypeError("task terminal delivery is invalid")
        try:
            self._settle_session(
                session_id,
                task_id=task_id,
                retire_plan=False,
                delivery=delivery,
            )
        except LifecycleAssociationError:
            raise TaskUnavailableError("task is unavailable") from None
        return TaskSessionReleaseView(task_id, session_id)

    def cancel_task_session(self, task_id: str, session_id: str) -> ControlView:
        try:
            self._lifecycle.require_session(session_id, task_id=task_id)
        except LifecycleAssociationError:
            raise TaskUnavailableError("task is unavailable") from None
        return _control_view(self._dispatcher.cancel(session_id))

    def close_task_shell(self, task_id: str) -> TaskShellView:
        try:
            self._lifecycle.close_task_shell(task_id)
        except LifecycleAssociationError:
            raise TaskUnavailableError("task is unavailable") from None
        return TaskShellView(task_id)

    def close_task(
        self,
        task_id: str,
        session_id: str,
        delivery: TaskTerminalDelivery,
    ) -> TaskCloseView:
        if type(delivery) is not TaskTerminalDelivery:
            raise TypeError("task terminal delivery is invalid")
        try:
            self._settle_session(
                session_id,
                task_id=task_id,
                retire_plan=True,
                delivery=delivery,
            )
        except LifecycleAssociationError:
            raise TaskUnavailableError("task is unavailable") from None
        return TaskCloseView(task_id, session_id)

    def get_execution_details(self, run_id: str):
        self._require_open()
        return self._runtime.get_execution_details(run_id)

    def get_inventory_details(self, request_id: str) -> InventoryDetailsView:
        self._require_open()
        details = self._runtime.get_inventory_details(request_id)
        resolution = _location_resolution_view(details.resolution)
        return InventoryDetailsView(
            request_id=details.request_id,
            state=resolution.state,
            root_path=resolution.root_path,
            location_id=(
                resolution.location_id
                if details.location_id is None
                else details.location_id
            ),
            selected_mount=resolution.selected_mount,
            candidates=resolution.candidates,
            detail=resolution.detail,
            selected_paths=details.selected_paths,
            observed_count=details.observed_count,
            missing_count=details.missing_count,
            complete=details.complete,
            warnings=tuple(
                ScanWarningView(
                    warning.code.value,
                    warning.rel_path,
                    warning.detail,
                )
                for warning in details.warnings
            ),
        )

    def list_inventory(
        self,
        location_id: int,
        selected_paths: tuple[str, ...] = (),
    ) -> tuple[InventoryRowView, ...]:
        self._require_open()
        return tuple(
            inventory_row_view(row)
            for row in self._runtime.list_inventory(
                location_id,
                selected_paths,
            )
        )

    def mapping_ids_for_location(self, location_id: int) -> tuple[str, ...]:
        self._require_open()
        return tuple(
            str(mapping_id)
            for mapping_id in self._runtime.mapping_ids_for_location(
                location_id
            )
        )

    def list_unacknowledged_missing(
        self,
        location_id: int,
    ) -> tuple[InventoryRowView, ...]:
        self._require_open()
        return tuple(
            inventory_row_view(row)
            for row in self._runtime.list_unacknowledged_missing(location_id)
        )

    def list_stale_inventory(
        self,
        location_id: int,
        verified_before: datetime,
    ) -> tuple[InventoryRowView, ...]:
        self._require_open()
        return tuple(
            inventory_row_view(row)
            for row in self._runtime.list_stale_inventory(
                location_id,
                verified_before,
            )
        )

    def acknowledge_inventory(
        self,
        command_id: str,
        location_id: int,
        row_ids: tuple[str, ...],
        *,
        changed_at: datetime,
    ) -> tuple[InventoryDispositionView, ...]:
        self._require_open()
        return self._change_inventory_visibility(
            "acknowledge",
            command_id,
            location_id,
            row_ids,
            changed_at,
        )

    def restore_inventory(
        self,
        command_id: str,
        location_id: int,
        row_ids: tuple[str, ...],
        *,
        changed_at: datetime,
    ) -> tuple[InventoryDispositionView, ...]:
        self._require_open()
        return self._change_inventory_visibility(
            "restore",
            command_id,
            location_id,
            row_ids,
            changed_at,
        )

    def list_history(
        self, limit: int = 50
    ) -> tuple[HistoryRunSummaryView, ...]:
        self._require_open()
        return self._runtime.list_history(limit)

    def get_history_summary(self, run_token: str) -> HistoryRunSummaryView:
        self._require_open()
        return self._runtime.get_history_summary(run_token)

    def get_history_items(
        self,
        run_token: str,
        *,
        after_order: int = 0,
        through_order: int | None = None,
        limit: int = 256,
    ) -> HistoryItemPageView:
        self._require_open()
        return self._runtime.get_history_items(
            run_token,
            after_order=after_order,
            through_order=through_order,
            limit=limit,
        )

    def get_history_events(
        self,
        run_token: str,
        *,
        after_seq: int = 0,
        through_seq: int | None = None,
        limit: int = 256,
    ) -> HistoryEventPageView:
        self._require_open()
        return self._runtime.get_history_events(
            run_token,
            after_seq=after_seq,
            through_seq=through_seq,
            limit=limit,
        )

    def close(self, timeout: float = SERVICE_CLOSE_TIMEOUT_SECONDS) -> ShutdownView:
        close_lock = getattr(self, "_close_lock", None)
        with (nullcontext() if close_lock is None else close_lock):
            return self._close_once(timeout)

    def _close_once(self, timeout: float) -> ShutdownView:
        close_lifecycle = False
        with self._lock:
            if self._closed:
                if (
                    self._shutdown is not None
                    and self._shutdown.complete
                    and getattr(self, "_runtime_closed", False)
                    and getattr(self, "_observer_closed", False)
                ):
                    return self._shutdown
            else:
                self._closed = True
                self._plan_selections.clear()
                self._visibility_receipts.clear()
                close_lifecycle = True
        if close_lifecycle:
            self._lifecycle.close()
        observer_failure_interrupted: bool | None = None
        if not getattr(self, "_observer_closed", False):
            try:
                self._observer.close()
            except BaseException as error:
                observer_failure_interrupted = not isinstance(error, Exception)
                retire_exception_graph(error)
            else:
                with self._lock:
                    self._observer_closed = True
        with self._lock:
            view = self._shutdown
        if view is None or not view.complete:
            result = self._dispatcher.shutdown(timeout=timeout)
            view = ShutdownView(
                complete=result.complete,
                unfinished=tuple(str(item) for item in result.unfinished),
                custody_released=result.custody_released,
            )
            with self._lock:
                self._shutdown = view
        if view.complete:
            if not getattr(self, "_runtime_closed", False):
                self._runtime.close()
                with self._lock:
                    self._runtime_closed = True
                self._lifecycle.retire_all()
        if observer_failure_interrupted is not None:
            _raise_service_observer_failure(
                interrupted=observer_failure_interrupted,
            )
        return view

    def __enter__(self) -> NamiSyncService:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _start_integrity(
        self,
        kind: str,
        *,
        root_path: str | None,
        location_id: int | None,
        selected_paths: tuple[str, ...],
        selected_mount: str | None,
        selected_ids: tuple[str, ...] | None,
        command_id: str | None,
    ) -> LocationSession:
        signature = (
            root_path,
            location_id,
            tuple(selected_paths),
            selected_mount,
            _canonical_id_gesture(selected_ids),
        )
        with self._lifecycle.command_guard(command_id):
            replay = self._replay_start(command_id, kind, signature)
            if replay is not None:
                return LocationSession(replay.request_id, replay.session_id)
            if selected_ids is not None:
                selected_paths, _subtree_roots = self._resolve_location_ids(
                    location_id,
                    selected_ids,
                    recursive=False,
                )
            request_id = uuid4().hex
            request = integrity_request(
                kind,
                request_id,
                root_path=root_path,
                location_id=location_id,
                selected_paths=selected_paths,
                selected_mount=selected_mount,
            )
            result = self._start_location(
                kind,
                request_id,
                request,
                command_id=command_id,
                signature=signature,
            )
            return result

    def _start_location(
        self,
        kind: str,
        request_id: str,
        request: object,
        *,
        command_id: str | None,
        signature: tuple[object, ...],
    ) -> LocationSession:
        try:
            session_id, _receipt = self._submit_session(
                kind,
                request,
                effect_kind=kind,
                command_id=command_id,
                signature=signature,
                request_id=request_id,
                detail_owner=("inventory", request_id),
            )
        except VolumeResolutionRequired as error:
            raise LocationResolutionError(
                _location_resolution_view(error.resolution)
            ) from error
        result = LocationSession(request_id, str(session_id))
        return result

    def _submit_session(
        self,
        kind: str,
        request: object,
        *,
        effect_kind: str,
        command_id: str | None,
        signature: tuple[object, ...],
        request_id: str,
        detail_owner: tuple[str, str] | None = None,
        observation_sink: SessionSink | None = None,
        task_id: str | None = None,
    ) -> tuple[SessionId, StartReceipt]:
        self._require_open()
        admission = self._lifecycle.begin_admission(
            effect_kind,
            command_id,
            signature,
            task_id=task_id,
            detail_owner=detail_owner,
        )

        def rollback() -> None:
            claim = self._lifecycle.begin_admission_rollback(admission)
            if claim is None:
                return
            try:
                if claim.session_id is not None:
                    self._observer.release(claim.session_id)
                self._drop_runtime_details(claim.detail_owner)
            except BaseException:
                self._lifecycle.abandon_admission_rollback(claim)
                raise
            self._lifecycle.complete_admission_rollback(claim)

        def attach(
            session_id: SessionId,
            stream: EventStream,
        ) -> Callable[[], None]:
            stream_needs_close = True
            try:
                self._lifecycle.attach_session(
                    admission,
                    str(session_id),
                )
                if observation_sink is None:
                    stream.close()
                    stream_needs_close = False
                else:
                    # SessionObserver.adopt closes a rejected stream itself.
                    stream_needs_close = False
                    self._observer.adopt(
                        str(session_id),
                        observation_sink,
                        stream,
                    )
            except BaseException:
                if stream_needs_close:
                    try:
                        stream.close()
                    except BaseException as error:
                        retire_exception_graph(error)
                raise

            return rollback

        try:
            session_id = self._dispatcher.submit(
                kind,
                request,
                attach=AdmissionAttachment(attach, rollback),
            )
        except BaseException:
            try:
                rollback()
            except BaseException as cleanup_error:
                retire_exception_graph(cleanup_error)
            raise
        try:
            _association, receipt = self._lifecycle.publish_start(
                admission,
                str(session_id),
                request_id,
            )
        except LifecycleReceiptConflictError as error:
            raise CommandIdConflictError(str(error)) from None
        return session_id, receipt

    def _reobserve_session(
        self,
        session_id: str,
        sink: SessionSink,
        from_sequence: int,
        *,
        task_id: str | None | object = ...,
    ) -> SessionRecordView:
        if task_id is ...:
            claim = self._lifecycle.begin_observation(session_id)
        else:
            claim = self._lifecycle.begin_observation(
                session_id,
                task_id=task_id,
            )
        return self._complete_observation_call(
            claim,
            lambda: self._observer.reobserve(
                session_id,
                sink,
                from_sequence,
            ),
        )

    def _complete_observation_call(
        self,
        claim,
        operation: Callable[[], SessionRecordView],
    ) -> SessionRecordView:
        try:
            return operation()
        finally:
            self._lifecycle.end_observation(claim)

    def _has_live_association(self, session_id: str) -> bool:
        try:
            self._lifecycle.require_session(session_id)
        except LifecycleAssociationError:
            return False
        return True

    @staticmethod
    def _missing_control_view(session_id: str) -> ControlView:
        return ControlView(
            code="not-found",
            session_id=session_id,
            before=None,
            after=None,
            detail="session does not exist",
            accepted=False,
        )

    def _settle_session(
        self,
        session_id: str,
        *,
        task_id: str | None,
        retire_plan: bool,
        delivery: TaskTerminalDelivery | None = None,
    ) -> None:
        claim = self._lifecycle.begin_settlement(
            session_id,
            task_id=task_id,
            close_task=retire_plan,
        )
        retirement = None
        try:
            terminal_digest: bytes | None = None
            dispatcher_truth_observed = False
            if delivery is not None:
                (
                    terminal_digest,
                    dispatcher_truth_observed,
                ) = self._reconcile_terminal_delivery(session_id, delivery)
            work = self._lifecycle.confirm_settlement(
                claim,
                terminal_digest=terminal_digest,
                dispatcher_truth_observed=dispatcher_truth_observed,
            )
            if not work.replay:
                self._observer.release(work.session_id)
                try:
                    self._dispatcher.close(work.session_id)
                except SessionNotFound:
                    # Only a confirmed exact application settlement may
                    # interpret absent Dispatcher custody as already closed.
                    pass
                self._drop_runtime_details(work.detail_owner)
                if work.plan_token is not None:
                    retirement = self._lifecycle.begin_plan_retirement(
                        work.plan_token
                    )
                    if retirement is not None:
                        request_id = work.plan_token.request_id
                        self._runtime.drop_plan(request_id)
                        self._drop_exact_plan_selection(work.plan_token)
                        self._lifecycle.complete_plan_retirement(retirement)
                        retirement = None
            self._lifecycle.complete_settlement(work)
        except BaseException:
            if retirement is not None:
                self._lifecycle.abandon_plan_retirement(retirement)
            self._lifecycle.abandon_settlement(claim)
            raise

    def _reconcile_terminal_delivery(
        self,
        session_id: str,
        delivery: TaskTerminalDelivery,
    ) -> tuple[bytes, bool]:
        delivered = delivery.record
        if delivered.session_id != session_id or delivered.result is None:
            raise RuntimeError(
                "delivered terminal truth disagrees with dispatcher truth"
            )
        terminal_digest = sha256(
            b"NamiSync/task-terminal/v1\0"
            + dumps(
                asdict(delivery),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).digest()
        try:
            record = self._dispatcher.get(session_id)
        except SessionNotFound:
            return terminal_digest, False
        expected = session_record_view(record)
        if delivered != expected or record.result is None:
            raise RuntimeError(
                "delivered terminal truth disagrees with dispatcher truth"
            )
        terminal = delivery.terminal_event
        if terminal is not None and (
            terminal.session_id != session_id
            or terminal.body_type != "Terminal"
            or terminal.body.get("result")
            != terminal_result_event_data(record.result)
        ):
            raise RuntimeError(
                "delivered terminal truth disagrees with dispatcher truth"
            )
        return terminal_digest, True

    def _drop_runtime_details(self, owner: tuple[str, str] | None) -> None:
        if owner is None:
            return
        detail_kind, detail_id = owner
        if detail_kind == "execution":
            self._runtime.drop_execution_details(detail_id)
            return
        if detail_kind == "inventory":
            self._runtime.drop_inventory_details(detail_id)
            return
        raise RuntimeError(f"unknown runtime detail owner kind: {detail_kind}")

    def _drop_exact_plan_selection(self, token: PlanToken) -> None:
        with self._lock:
            selection = self._plan_selections.get(token.request_id)
            if selection is not None and selection.plan_token == token:
                self._plan_selections.pop(token.request_id, None)

    def _selection_state(
        self,
        request_id: str,
    ) -> tuple[_PlanSelectionState, object]:
        self._require_open()
        artifact = self._runtime.get_plan(request_id)
        try:
            plan_token = self._lifecycle.require_plan(request_id)
        except LifecycleAssociationError:
            # Preserve the runtime's public retirement result when a drop lands
            # between the first successful read and lifecycle token lookup.
            self._runtime.get_plan(request_id)
            raise
        with self._lock:
            state = self._plan_selections.get(request_id)
            if state is None:
                state = _PlanSelectionState(
                    artifact,
                    plan_token,
                )
                self._plan_selections[request_id] = state
            else:
                artifact = state.artifact

        while True:
            try:
                live_artifact = self._runtime.get_plan(request_id)
            except KeyError:
                removed = False
                with self._lock:
                    if self._plan_selections.get(request_id) is state:
                        self._plan_selections.pop(request_id)
                        removed = True
                if removed:
                    retirement = self._lifecycle.begin_plan_retirement(
                        state.plan_token
                    )
                    if retirement is not None:
                        self._lifecycle.complete_plan_retirement(retirement)
                raise
            with self._lock:
                current = self._plan_selections.get(request_id)
                if current is not state:
                    if current is None:
                        # A concurrent retirement or replacement owns the next
                        # token lookup; restart without nesting lifecycle state
                        # under the service cache lock.
                        pass
                    else:
                        state = current
                        artifact = current.artifact
                        continue
                else:
                    if live_artifact is artifact:
                        return state, artifact
                    state = _PlanSelectionState(
                        live_artifact,
                        state.plan_token,
                        revision=state.revision + 1,
                    )
                    self._plan_selections[request_id] = state
                    artifact = live_artifact
                    continue
            artifact = self._runtime.get_plan(request_id)
            plan_token = self._lifecycle.require_plan(request_id)
            with self._lock:
                current = self._plan_selections.get(request_id)
                if current is None:
                    state = _PlanSelectionState(artifact, plan_token)
                    self._plan_selections[request_id] = state
                else:
                    state = current
                    artifact = current.artifact

    def _selection_preview_locked(
        self,
        request_id: str,
        state: _PlanSelectionState,
        artifact: object,
    ) -> SelectionPreviewView:
        decision = derive_execution_selection(
            artifact.plan,
            user_deselected=state.user_deselected,
        )
        exclusions = {
            str(exclusion.op_id): exclusion
            for exclusion in decision.exclusions
        }
        selected_ids = tuple(
            str(operation.op_id)
            for operation in artifact.plan.operations
            if operation.op_id in decision.selection
        )
        risk_count = self._irreversible_update_count(
            artifact.plan,
            decision.selection,
        )
        return SelectionPreviewView(
            request_id=request_id,
            revision=state.revision,
            state=state.phase,
            selection_digest=execution_selection_digest_hex(
                decision.selection
            ),
            selected_operation_ids=selected_ids,
            user_deselected=tuple(sorted(state.user_deselected)),
            requires_destructive_confirmation=bool(risk_count),
            irreversible_update_count=risk_count,
            operations=tuple(
                SelectionOperationView(
                    operation_id=str(operation.op_id),
                    selected=operation.op_id in decision.selection,
                    outcome=(
                        None
                        if str(operation.op_id) not in exclusions
                        else exclusions[str(operation.op_id)].outcome.value
                    ),
                    reason=(
                        None
                        if str(operation.op_id) not in exclusions
                        else exclusions[str(operation.op_id)].reason
                    ),
                )
                for operation in artifact.plan.operations
            ),
        )

    @staticmethod
    def _irreversible_update_count(plan, selection: frozenset[str]) -> int:
        if plan.trash_on_update:
            return 0
        return sum(
            operation.op_id in selection
            and operation.kind.value == "update"
            for operation in plan.operations
        )

    @staticmethod
    def _plan_tree(request_id: str, plan) -> NodeTree:
        return build_plan_node_tree(request_id, plan)

    def _resolve_plan_selection_ids(
        self,
        request_id: str,
        plan,
        identifiers: tuple[str, ...],
    ) -> tuple[str, ...]:
        known = {str(operation.op_id) for operation in plan.operations}
        toggleable = {
            str(operation_id)
            for operation_id in derive_execution_selection(plan).selection
        }
        tree: NodeTree | None = None
        resolved: set[str] = set()
        for identifier in identifiers:
            if identifier in known:
                resolved.add(identifier)
                continue
            if tree is None:
                tree = self._plan_tree(request_id, plan)
            try:
                members = tuple(
                    member_id
                    for member_id in tree.subtree_member_ids(identifier)
                    if member_id in toggleable
                )
            except KeyError as error:
                raise ValueError(
                    f"selection id does not belong to plan: {identifier}"
                ) from error
            if not members:
                raise ValueError(
                    f"selection node contains no selectable operations: {identifier}"
                )
            resolved.update(members)
        return tuple(sorted(resolved))

    def _replay_start(
        self,
        command_id: str | None,
        kind: str,
        signature: tuple[object, ...],
    ):
        try:
            return self._lifecycle.replay_start(
                command_id,
                kind,
                signature,
            )
        except LifecycleReceiptConflictError as error:
            raise CommandIdConflictError(str(error)) from None

    def _admit_plan_locations(
        self,
        source: str,
        target: str,
    ) -> tuple[str, str]:
        failure_detail = None
        try:
            admitted = self._runtime.admit_plan_locations(source, target)
        except (OSError, ValueError) as error:
            try:
                failure_detail = str(error)
            finally:
                retire_exception_graph(error)
        if failure_detail is not None:
            raise SyncPathInputError(failure_detail) from None
        if (
            type(admitted) is not tuple
            or len(admitted) != 2
            or any(type(item) is not LocationCandidateResult for item in admitted)
        ):
            raise TypeError("plan location admission returned invalid results")
        source_result, target_result = admitted
        for result in admitted:
            if result.state is not LocationCandidateState.RESOLVED:
                raise SyncPathInputError(
                    result.detail or result.state.value,
                    result,
                ) from None
            if result.root_path is None:
                raise RuntimeError("resolved plan location lacks its root path")
        assert source_result.root_path is not None
        assert target_result.root_path is not None
        return source_result.root_path, target_result.root_path

    def _require_plan_location_bounds(self, source: str, target: str) -> None:
        failure_detail = None
        try:
            LocationCandidate.literal(source)
            LocationCandidate.literal(target)
        except (OSError, ValueError) as error:
            try:
                failure_detail = str(error)
            finally:
                retire_exception_graph(error)
        if failure_detail is not None:
            raise SyncPathInputError(failure_detail) from None

    def _require_open(self) -> None:
        lock = getattr(self, "_lock", None)
        if lock is None:
            return
        with lock:
            if getattr(self, "_closed", False):
                raise RuntimeError("service is closed")

    def _resolve_location_ids(
        self,
        location_id: int | None,
        selected_ids: tuple[str, ...],
        *,
        recursive: bool,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if location_id is None:
            raise ValueError("id-based location commands require location_id")
        if not selected_ids:
            raise ValueError("id-based location commands require selected ids")
        rows = self._runtime.list_inventory(location_id)
        rows_by_id = {row.row_id: row for row in rows}
        tree = build_node_tree(
            tree_kind=NodeTreeKind.INVENTORY,
            scope_identity=str(location_id),
            members=(
                NodeTreeMember(
                    row.row_id,
                    row.rel_path,
                    row.rel_path_key,
                    row.entry_kind is not None
                    and row.entry_kind.value == "directory",
                )
                for row in rows
            ),
        )
        exact_paths: set[str] = set()
        subtree_roots: set[str] = set()
        for identifier in selected_ids:
            row = rows_by_id.get(identifier)
            if row is not None:
                exact_paths.add(row.rel_path)
                continue
            try:
                node = tree.node_for_id(identifier)
            except KeyError as error:
                raise ValueError(
                    "inventory id does not belong to location "
                    f"{location_id}: {identifier}"
                ) from error
            if recursive and node.is_container:
                subtree_roots.add(node.rel_path)
                continue
            member_ids = tree.subtree_member_ids(identifier)
            if not member_ids:
                raise ValueError(
                    f"inventory node contains no subjects: {identifier}"
                )
            exact_paths.update(rows_by_id[row_id].rel_path for row_id in member_ids)
        return tuple(sorted(exact_paths)), tuple(sorted(subtree_roots))

    def _change_inventory_visibility(
        self,
        action: str,
        command_id: str,
        location_id: int,
        row_ids: tuple[str, ...],
        changed_at: datetime,
    ) -> tuple[InventoryDispositionView, ...]:
        self._require_open()
        if not command_id:
            raise ValueError("command_id must be nonempty")
        if (
            changed_at.tzinfo is None
            or changed_at.utcoffset() != timezone.utc.utcoffset(changed_at)
        ):
            raise ValueError("changed_at must be timezone-aware UTC")
        canonical_rows = tuple(sorted(set(row_ids)))
        if not canonical_rows:
            raise ValueError("inventory visibility gesture requires row ids")
        known_rows = {
            row.row_id
            for row in self._runtime.list_inventory(location_id)
        }
        unknown = set(canonical_rows) - known_rows
        if unknown:
            raise ValueError(
                f"inventory rows do not belong to location: {sorted(unknown)!r}"
            )
        signature = (
            action,
            location_id,
            canonical_rows,
            changed_at.isoformat(),
        )
        with self._lock:
            if self._closed:
                raise RuntimeError("service is closed")
            existing = self._visibility_receipts.get(command_id)
            if existing is not None and existing != signature:
                raise CommandIdConflictError(
                    "command_id was reused for a different gesture"
                )
            self._visibility_receipts[command_id] = signature
        change = (
            self._runtime.acknowledge_inventory
            if action == "acknowledge"
            else self._runtime.restore_inventory
        )
        return tuple(
            InventoryDispositionView(
                row_id,
                change(
                    _row_command_id(command_id, row_id),
                    location_id,
                    row_id,
                    changed_at=changed_at,
                ).value,
            )
            for row_id in canonical_rows
        )


def _dispatcher(runtime: LocalWorkflowRuntime) -> Dispatcher:
    return Dispatcher(
        _workflow_registry(runtime),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
        audit_timeout=AUDIT_FINALIZATION_TIMEOUT_SECONDS,
        audit_offer_timeout=AUDIT_OFFER_TIMEOUT_SECONDS,
        audit_flush_interval=runtime.history_window_policy.max_age_seconds,
    )


def _workflow_registry(
    runtime: LocalWorkflowRuntime,
) -> dict[str, WorkflowRegistration]:
    def registration(
        prepare,
        open_invocation,
        *,
        supports_pause: bool = False,
        settle_canceled=None,
    ) -> WorkflowRegistration:
        def prepare_session(request: object) -> PreparedSession:
            prepared = prepare(request)
            return PreparedSession.from_resource_keys(
                prepared.checkpoint, prepared.resources
            )

        optional = (
            {}
            if settle_canceled is None
            else {"settle_canceled": settle_canceled}
        )
        return WorkflowRegistration(
            prepare_session,
            open_invocation,
            supports_pause=supports_pause,
            **optional,
        )

    return {
        PLAN_KIND: registration(runtime.prepare_plan, runtime.open_plan),
        EXECUTION_KIND: registration(
            runtime.prepare_execution,
            runtime.open_execution,
            supports_pause=True,
            settle_canceled=runtime.settle_canceled_execution,
        ),
        INVENTORY_KIND: registration(
            runtime.prepare_inventory,
            runtime.open_inventory,
        ),
        BASELINE_KIND: registration(
            runtime.prepare_baseline,
            runtime.open_baseline,
            supports_pause=True,
            settle_canceled=runtime.settle_canceled_baseline,
        ),
        VERIFY_KIND: registration(
            runtime.prepare_verify,
            runtime.open_verify,
            supports_pause=True,
            settle_canceled=runtime.settle_canceled_verify,
        ),
        REBASELINE_KIND: registration(
            runtime.prepare_rebaseline,
            runtime.open_rebaseline,
            supports_pause=True,
            settle_canceled=runtime.settle_canceled_rebaseline,
        ),
    }


def _row_command_id(command_id: str, row_id: str) -> str:
    if not command_id:
        raise ValueError("command_id must be nonempty")
    digest = sha256()
    digest.update(command_id.encode("utf-8"))
    digest.update(b"\0")
    digest.update(row_id.encode("utf-8"))
    return digest.hexdigest()


def _canonical_id_gesture(
    identifiers: tuple[str, ...] | None,
) -> tuple[str, ...] | None:
    if identifiers is None:
        return None
    return tuple(sorted(set(identifiers)))


def _control_view(result) -> ControlView:
    return ControlView(
        code=result.code.value,
        session_id=str(result.session_id),
        before=None if result.before is None else result.before.value,
        after=None if result.after is None else result.after.value,
        detail=result.detail,
        accepted=result.accepted,
    )


def _database_contract_view(
    contract: DatabasePairContract,
) -> DatabaseContractView:
    return DatabaseContractView(
        state=contract.state.value,
        reason=contract.reason,
        reset_direction=contract.reset_direction,
    )


def classify_result(result: OperationResultView) -> ResultClassificationView:
    """Expose the workflow-owned headline with every independent result axis."""

    return ResultClassificationView(
        headline=result.headline,
        filesystem=result.filesystem,
        integrity=result.integrity,
        recording=result.recording,
        audit=result.audit,
        disposition=result.disposition,
        canceled=result.canceled,
    )


def _location_resolution_view(resolution) -> LocationResolutionView:
    binding = resolution.binding
    selected_mount = (
        getattr(resolution, "selected_mount", None) or binding.selected_mount
    )
    if selected_mount == "<unmounted>" or (
        resolution.state.value == "ambiguous"
        and not binding.explicit_ambiguity_choice
    ):
        selected_mount = None
    return LocationResolutionView(
        state=resolution.state.value,
        root_path=resolution.root_path,
        location_id=binding.location_id,
        selected_mount=selected_mount,
        candidates=tuple(resolution.candidates),
        detail=resolution.detail,
    )


def _setup_sync_options(value: SetupOptionsView) -> SyncOptions:
    value.__post_init__()
    return SyncOptions(
        deletion_policy=DeletionPolicy(value.deletion_policy),
        preservation=PreservationPolicy(
            preserve_ads=False,
            preserve_created=value.preservation.preserve_created,
            preserve_acl=value.preservation.preserve_acl,
        ),
        filters=FilterSet(value.filters),
        trash_on_update=value.trash_on_update,
        propagate_source_casing=value.propagate_source_casing,
    )


def _setup_options_from_request(
    value: SyncOptions,
    verify_after_execute: bool,
) -> SetupOptionsView:
    if type(value) is not SyncOptions:
        raise TypeError("plan Setup options must be exact SyncOptions")
    return SetupOptionsView(
        value.filters.patterns,
        value.deletion_policy.value,
        value.trash_on_update,
        PreservationSettingsView(
            False,
            value.preservation.preserve_created,
            value.preservation.preserve_acl,
        ),
        value.propagate_source_casing,
        verify_after_execute,
    )


def _plan_again_state(value: VolumeResolutionState) -> str:
    return {
        VolumeResolutionState.RESOLVED: "resolved",
        VolumeResolutionState.OFFLINE: "offline",
        VolumeResolutionState.AMBIGUOUS: "ambiguous",
        VolumeResolutionState.ROOT_MISSING: "missing",
        VolumeResolutionState.ROOT_UNAVAILABLE: "unavailable",
    }[value]


def _setup_location(value: LocationCandidateResult) -> TaskSetupLocationView:
    if (
        value.state is not LocationCandidateState.RESOLVED
        or value.root_path is None
        or value.binding is None
    ):
        raise ValueError("Setup location requires a resolved candidate")
    location_id = value.binding.location_id
    return TaskSetupLocationView(
        value.root_path,
        None if location_id is None else str(location_id),
    )


__all__ = [
    "CommandIdConflictError",
    "ControlView",
    "DatabaseContractView",
    "ExecutionAdmissionView",
    "ExecutionSession",
    "InventoryDispositionView",
    "InventoryDetailsView",
    "InventoryRowView",
    "LocationResolutionError",
    "LocationResolutionView",
    "LocationSession",
    "NamiSyncService",
    "PlanSession",
    "PreservationSettingsView",
    "ResultClassificationView",
    "ScanWarningView",
    "SemanticSettingsPatchView",
    "SemanticSettingsView",
    "SetupOptionsView",
    "SessionEventView",
    "SessionObserver",
    "SessionRecordView",
    "SessionSink",
    "SessionUpdate",
    "SelectionMutationView",
    "SelectionOperationView",
    "SelectionPreviewView",
    "ShutdownView",
    "SyncPathInputError",
    "classify_result",
    "default_database_paths",
]
