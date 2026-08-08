"""Shared process-local facade for NamiSync interface adapters."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from typing import Callable
from uuid import uuid4

from namisync.dispatcher import (
    Dispatcher,
    EventStream,
    PreparedSession,
    SessionCleanupPending,
    SessionNotFound,
    WorkflowRegistration,
)
from namisync.workflows import (
    BASELINE_KIND,
    EXECUTION_KIND,
    HistoryEventPageView,
    HistoryItemPageView,
    HistoryRunSummaryView,
    INVENTORY_KIND,
    PLAN_KIND,
    REBASELINE_KIND,
    VERIFY_KIND,
    InventoryRequest,
    LocalWorkflowRuntime,
    VolumeResolutionRequired,
    default_database_paths,
    integrity_request,
    validate_sync_paths,
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
    SessionEventView,
    SessionRecordView,
    inventory_row_view,
    session_event_view,
    session_record_view,
)


SessionUpdate = SessionEventView | SessionRecordView
SessionSink = Callable[[SessionUpdate], None]
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


class SyncPathInputError(ValueError):
    """A source/target pair failed interface-level path validation."""


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
class ResultCategory:
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
class _Observation:
    session_id: str
    sink: SessionSink
    stream: EventStream
    streams: list[EventStream] = field(default_factory=list)
    stop: Event = field(default_factory=Event)
    done: Event = field(default_factory=Event)
    thread: Thread | None = None
    failure: Exception | None = None


@dataclass(slots=True)
class _PlanSelectionState:
    artifact: object
    revision: int = 0
    user_deselected: frozenset[str] = frozenset()
    phase: str = "reviewing"
    mutation_receipts: dict[str, tuple[object, ...]] = field(
        default_factory=dict
    )
    execution_session: ExecutionSession | None = None


@dataclass(frozen=True, slots=True)
class _SessionReceipt:
    kind: str
    signature: tuple[object, ...]
    request_id: str
    session_id: str


class SessionObserver:
    """Translate blocking dispatcher streams into sink-delivered views."""

    def __init__(self, dispatcher: Dispatcher, *, join_timeout: float = 2.0) -> None:
        if join_timeout <= 0:
            raise ValueError("observer join timeout must be positive")
        self._dispatcher = dispatcher
        self._join_timeout = join_timeout
        self._lock = Lock()
        self._observations: dict[str, _Observation] = {}
        self._closed = False

    def observe(self, session_id: str, sink: SessionSink) -> SessionRecordView:
        with self._lock:
            if self._closed:
                raise RuntimeError("session observer is closed")
            if session_id in self._observations:
                raise ValueError(f"session is already observed: {session_id}")

        record = self._dispatcher.get(session_id)
        current = session_record_view(record)
        if current.result is not None:
            return current

        try:
            stream = self._dispatcher.subscribe(session_id)
        except (SessionCleanupPending, SessionNotFound):
            finished = session_record_view(self._dispatcher.get(session_id))
            if finished.result is None:
                raise
            return finished

        observation = _Observation(
            session_id=session_id,
            sink=sink,
            stream=stream,
            streams=[stream],
        )
        thread = Thread(
            target=self._run,
            args=(observation,),
            name=f"namisync-observer-{session_id}",
            daemon=True,
        )
        observation.thread = thread
        with self._lock:
            if self._closed:
                stream.close()
                raise RuntimeError("session observer is closed")
            if session_id in self._observations:
                stream.close()
                raise ValueError(f"session is already observed: {session_id}")
            self._observations[session_id] = observation
            thread.start()
        return current

    def unsubscribe(self, session_id: str) -> None:
        with self._lock:
            observation = self._observations.get(session_id)
        if observation is None:
            return
        observation.stop.set()
        self._close_streams((observation,))
        self._join_threads((observation,))
        with self._lock:
            if self._observations.get(session_id) is observation:
                self._observations.pop(session_id, None)

    def wait(self, session_id: str) -> SessionRecordView:
        with self._lock:
            observation = self._observations.get(session_id)
        if observation is None:
            current = session_record_view(self._dispatcher.get(session_id))
            if current.result is not None:
                return current
            raise KeyError(f"session is not observed: {session_id}")
        observation.done.wait()
        if observation.failure is not None:
            raise RuntimeError(
                f"session observation failed: {session_id}"
            ) from observation.failure
        current = session_record_view(self._dispatcher.get(session_id))
        if current.result is None:
            raise RuntimeError(
                f"session observation stopped before terminal: {session_id}"
            )
        return current

    def close(self) -> None:
        with self._lock:
            if self._closed and not self._observations:
                return
            self._closed = True
            observations = tuple(self._observations.values())
        for observation in observations:
            observation.stop.set()
        self._close_streams(observations)
        try:
            self._join_threads(observations)
        finally:
            with self._lock:
                for observation in observations:
                    thread = observation.thread
                    if (
                        thread is None
                        or thread is current_thread()
                        or not thread.is_alive()
                    ):
                        if (
                            self._observations.get(observation.session_id)
                            is observation
                        ):
                            self._observations.pop(
                                observation.session_id,
                                None,
                            )

    def _run(self, observation: _Observation) -> None:
        stream = observation.stream
        next_sequence = 1
        try:
            while not observation.stop.is_set():
                try:
                    envelope = stream.next()
                except StopIteration:
                    if observation.stop.is_set():
                        return
                    record = session_record_view(
                        self._dispatcher.get(observation.session_id)
                    )
                    if record.result is not None:
                        observation.sink(record)
                        return
                    replacement = self._dispatcher.subscribe(
                        observation.session_id, next_sequence
                    )
                    with self._lock:
                        if (
                            self._closed
                            or observation.stop.is_set()
                            or self._observations.get(observation.session_id)
                            is not observation
                        ):
                            replacement.close()
                            return
                        observation.streams.append(replacement)
                        observation.stream = replacement
                    stream.close()
                    stream = replacement
                    continue

                event = session_event_view(envelope)
                if event.body_type == "Gap":
                    missed = event.body.get("first_missed_seq")
                    if isinstance(missed, int):
                        next_sequence = max(next_sequence, missed)
                else:
                    next_sequence = max(next_sequence, event.sequence + 1)
                observation.sink(event)
                if event.body_type == "Terminal":
                    observation.sink(
                        session_record_view(
                            self._dispatcher.get(observation.session_id)
                        )
                    )
                    return
        except Exception as error:
            observation.failure = error
        finally:
            for opened in observation.streams:
                opened.close()
            observation.done.set()

    @staticmethod
    def _close_streams(observations: tuple[_Observation, ...]) -> None:
        for observation in observations:
            for stream in observation.streams:
                stream.close()

    def _join_threads(self, observations: tuple[_Observation, ...]) -> None:
        deadline = monotonic() + self._join_timeout
        alive: list[str] = []
        for observation in observations:
            thread = observation.thread
            if thread is None or thread is current_thread():
                continue
            thread.join(max(0.0, deadline - monotonic()))
            if thread.is_alive():
                alive.append(observation.session_id)
        if alive:
            joined = ", ".join(sorted(alive))
            raise TimeoutError(f"session observers did not stop: {joined}")


class NamiSyncService:
    """Own the local workflow runtime, dispatcher, and interface observation."""

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
        self._plan_selections: dict[str, _PlanSelectionState] = {}
        self._session_receipts: dict[str, _SessionReceipt] = {}
        self._receipt_ids_by_session: dict[str, set[str]] = {}
        self._session_receipt_locks = tuple(Lock() for _ in range(64))
        self._session_receipt_lifecycle = Lock()
        self._visibility_receipts: dict[str, tuple[object, ...]] = {}
        self._closed = False
        self._shutdown: ShutdownView | None = None
        self._runtime_closed = False
        self._observer_closed = False

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
        with self._session_command_guard(command_id):
            replay = self._session_receipt(
                command_id,
                "plan",
                signature,
            )
            if replay is not None:
                return PlanSession(replay.request_id, replay.session_id)
            try:
                source_path, target_path = validate_sync_paths(source, target)
            except (OSError, ValueError) as error:
                raise SyncPathInputError(str(error)) from error
            request = self._runtime.create_plan_request(
                uuid4().hex,
                str(source_path),
                str(target_path),
                deletion_policy=deletion_policy,
            )
            session_id = self._dispatcher.submit(PLAN_KIND, request)
            result = PlanSession(request.request_id, str(session_id))
            self._remember_session_receipt(
                command_id,
                "plan",
                signature,
                result.request_id,
                result.session_id,
            )
            return result

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
            prior_signature = (
                None
                if command_id is None
                else state.mutation_receipts.get(command_id)
            )
            if prior_signature is not None:
                if prior_signature != signature:
                    raise ValueError(
                        "command_id was reused for a different selection mutation"
                    )
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
                    "in-flight" if state.phase == "committing" else "frozen",
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
                if command_id is not None:
                    state.mutation_receipts[command_id] = signature
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
        with self._session_command_guard(command_id):
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
        replay = self._session_receipt(
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
            session_id = self._dispatcher.submit(EXECUTION_KIND, request)
            result = ExecutionSession(
                str(request.execution_set.run_id),
                str(session_id),
            )
            self._remember_session_receipt(
                command_id,
                "execution",
                signature,
                result.run_id,
                result.session_id,
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
        with self._session_command_guard(command_id):
            replay = self._session_receipt(
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
            result = self._start_location(INVENTORY_KIND, request_id, request)
            self._remember_session_receipt(
                command_id,
                INVENTORY_KIND,
                signature,
                result.request_id,
                result.session_id,
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
        with self._lock:
            prior = self._plan_selections.get(request_id)
            if prior is None:
                self._plan_selections[request_id] = _PlanSelectionState(artifact)
            elif prior.artifact is not artifact:
                self._plan_selections[request_id] = _PlanSelectionState(
                    artifact,
                    revision=prior.revision + 1,
                    mutation_receipts=dict(prior.mutation_receipts),
                )

    def get_plan(self, request_id: str) -> object:
        self._require_open()
        return self._runtime.get_plan(request_id)

    def drop_plan(self, request_id: str) -> None:
        self._require_open()
        self._runtime.drop_plan(request_id)
        with self._lock:
            self._plan_selections.pop(request_id, None)

    def get_session(self, session_id: str) -> SessionRecordView:
        return session_record_view(self._dispatcher.get(session_id))

    def list_sessions(self) -> tuple[SessionRecordView, ...]:
        return tuple(session_record_view(item) for item in self._dispatcher.list())

    def observe(self, session_id: str, sink: SessionSink) -> SessionRecordView:
        self._require_open()
        return self._observer.observe(session_id, sink)

    def unsubscribe(self, session_id: str) -> None:
        self._observer.unsubscribe(session_id)

    def wait(self, session_id: str) -> SessionRecordView:
        return self._observer.wait(session_id)

    def cancel(self, session_id: str) -> ControlView:
        return _control_view(self._dispatcher.cancel(session_id))

    def pause(self, session_id: str) -> ControlView:
        return _control_view(self._dispatcher.pause(session_id))

    def resume(self, session_id: str) -> ControlView:
        return _control_view(self._dispatcher.resume(session_id))

    def close_session(self, session_id: str) -> None:
        self._observer.unsubscribe(session_id)
        with self._session_receipt_lifecycle_guard():
            self._dispatcher.close(session_id)
            with self._lock:
                for command_id in self._receipt_ids_by_session.pop(
                    session_id,
                    (),
                ):
                    self._session_receipts.pop(command_id, None)

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
                self._session_receipts.clear()
                self._receipt_ids_by_session.clear()
                self._visibility_receipts.clear()
        observer_failure: BaseException | None = None
        if not getattr(self, "_observer_closed", False):
            try:
                self._observer.close()
            except BaseException as error:
                observer_failure = error
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
        if observer_failure is not None:
            raise observer_failure
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
        with self._session_command_guard(command_id):
            replay = self._session_receipt(command_id, kind, signature)
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
            result = self._start_location(kind, request_id, request)
            self._remember_session_receipt(
                command_id,
                kind,
                signature,
                result.request_id,
                result.session_id,
            )
            return result

    def _start_location(
        self,
        kind: str,
        request_id: str,
        request: object,
    ) -> LocationSession:
        try:
            session_id = self._dispatcher.submit(kind, request)
        except VolumeResolutionRequired as error:
            raise LocationResolutionError(
                _location_resolution_view(error.resolution)
            ) from error
        return LocationSession(request_id, str(session_id))

    def _selection_state(
        self,
        request_id: str,
    ) -> tuple[_PlanSelectionState, object]:
        self._require_open()
        artifact = self._runtime.get_plan(request_id)
        with self._lock:
            state = self._plan_selections.get(request_id)
            if state is None:
                state = _PlanSelectionState(artifact)
                self._plan_selections[request_id] = state
            elif state.artifact is not artifact:
                state = _PlanSelectionState(
                    artifact,
                    revision=state.revision + 1,
                    mutation_receipts=dict(state.mutation_receipts),
                )
                self._plan_selections[request_id] = state
            return state, artifact

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

    def _session_command_guard(self, command_id: str | None):
        self._require_open()
        if command_id is None:
            return nullcontext()
        if not command_id:
            raise ValueError("command_id must be nonempty")
        digest = sha256(
            command_id.encode("utf-8", errors="surrogatepass")
        ).digest()
        return self._session_receipt_locks[
            int.from_bytes(digest[:2], "big")
            % len(self._session_receipt_locks)
        ]

    def _require_open(self) -> None:
        lock = getattr(self, "_lock", None)
        if lock is None:
            return
        with lock:
            if getattr(self, "_closed", False):
                raise RuntimeError("service is closed")

    def _session_receipt_lifecycle_guard(self):
        lock = getattr(self, "_session_receipt_lifecycle", None)
        return nullcontext() if lock is None else lock

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

    def _session_receipt(
        self,
        command_id: str | None,
        kind: str,
        signature: tuple[object, ...],
    ) -> _SessionReceipt | None:
        if command_id is None:
            return None
        if not command_id:
            raise ValueError("command_id must be nonempty")
        with self._session_receipt_lifecycle_guard():
            with self._lock:
                if self._closed:
                    raise RuntimeError("service is closed")
                receipt = self._session_receipts.get(command_id)
            if receipt is None:
                return None
            if receipt.kind != kind or receipt.signature != signature:
                raise ValueError("command_id was reused for a different command")
            get_session = getattr(self._dispatcher, "get", None)
            if get_session is not None:
                try:
                    get_session(receipt.session_id)
                except SessionNotFound:
                    with self._lock:
                        if self._session_receipts.get(command_id) is receipt:
                            self._session_receipts.pop(command_id, None)
                            receipt_ids = self._receipt_ids_by_session.get(
                                receipt.session_id
                            )
                            if receipt_ids is not None:
                                receipt_ids.discard(command_id)
                                if not receipt_ids:
                                    self._receipt_ids_by_session.pop(
                                        receipt.session_id,
                                        None,
                                    )
                    return None
            return receipt

    def _remember_session_receipt(
        self,
        command_id: str | None,
        kind: str,
        signature: tuple[object, ...],
        request_id: str,
        session_id: str,
    ) -> None:
        if command_id is None:
            return
        receipt = _SessionReceipt(
            kind,
            signature,
            request_id,
            session_id,
        )
        with self._session_receipt_lifecycle_guard():
            get_session = getattr(self._dispatcher, "get", None)
            if get_session is not None:
                try:
                    get_session(session_id)
                except SessionNotFound:
                    return
            with self._lock:
                if self._closed:
                    return
                existing = self._session_receipts.get(command_id)
                if existing is not None and existing != receipt:
                    raise ValueError(
                        "command_id raced with a different admitted session"
                    )
                self._session_receipts[command_id] = receipt
                self._receipt_ids_by_session.setdefault(
                    session_id,
                    set(),
                ).add(command_id)

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
                raise ValueError("command_id was reused for a different gesture")
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
                prepared.payload, prepared.resources
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
        ),
        VERIFY_KIND: registration(
            runtime.prepare_verify,
            runtime.open_verify,
            supports_pause=True,
        ),
        REBASELINE_KIND: registration(
            runtime.prepare_rebaseline,
            runtime.open_rebaseline,
            supports_pause=True,
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


def classify_result(result: OperationResultView) -> ResultCategory:
    """Expose the workflow-owned headline with every independent result axis."""

    return ResultCategory(
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
    selected_mount = binding.selected_mount
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


__all__ = [
    "ControlView",
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
    "ResultCategory",
    "ScanWarningView",
    "SemanticSettingsPatchView",
    "SemanticSettingsView",
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
