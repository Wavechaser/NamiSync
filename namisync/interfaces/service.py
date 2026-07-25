"""Shared process-local facade for NamiSync interface adapters."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from typing import Callable
from uuid import uuid4

from namisync.dispatcher import (
    Dispatcher,
    EventStream,
    PreparedSession,
    SessionNotFound,
    WorkflowRegistration,
)
from namisync.workflows import (
    BASELINE_KIND,
    EXECUTION_KIND,
    INVENTORY_KIND,
    PLAN_KIND,
    REBASELINE_KIND,
    VERIFY_KIND,
    InventoryRequest,
    LocalWorkflowRuntime,
    VolumeResolutionRequired,
    default_database_paths,
    integrity_request,
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
        except SessionNotFound:
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
            observation = self._observations.pop(session_id, None)
        if observation is None:
            return
        observation.stop.set()
        self._close_streams((observation,))
        self._join_threads((observation,))

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
            if self._closed:
                return
            self._closed = True
            observations = tuple(self._observations.values())
            self._observations.clear()
        for observation in observations:
            observation.stop.set()
        self._close_streams(observations)
        self._join_threads(observations)

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
        self._closed = False
        self._shutdown: ShutdownView | None = None

    def start_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None = None,
    ) -> PlanSession:
        try:
            source_path, target_path = _validated_paths(source, target)
        except (OSError, ValueError) as error:
            raise SyncPathInputError(str(error)) from error
        request = self._runtime.create_plan_request(
            uuid4().hex,
            str(source_path),
            str(target_path),
            deletion_policy=deletion_policy,
        )
        session_id = self._dispatcher.submit(PLAN_KIND, request)
        return PlanSession(request.request_id, str(session_id))

    def read_semantic_settings(self) -> SemanticSettingsView:
        return self._runtime.read_semantic_settings()

    def commit_semantic_settings(
        self,
        patch: SemanticSettingsPatchView,
    ) -> SemanticSettingsView:
        return self._runtime.commit_semantic_settings(patch)

    def get_plan_review(self, request_id: str):
        return self._runtime.get_plan_review(request_id)

    def start_execution(
        self,
        request_id: str,
        *,
        verify_after_execute: bool = False,
    ) -> ExecutionSession:
        request = self._runtime.commit_plan(
            request_id,
            verify_after_execute=verify_after_execute,
        )
        session_id = self._dispatcher.submit(EXECUTION_KIND, request)
        return ExecutionSession(
            str(request.execution_set.run_id),
            str(session_id),
        )

    def start_inventory(
        self,
        *,
        root_path: str | None = None,
        location_id: int | None = None,
        selected_paths: tuple[str, ...] = (),
        selected_mount: str | None = None,
    ) -> LocationSession:
        request_id = uuid4().hex
        request = InventoryRequest(
            request_id=request_id,
            root_path=root_path,
            location_id=location_id,
            selected_paths=selected_paths,
            selected_mount=selected_mount,
        )
        return self._start_location(INVENTORY_KIND, request_id, request)

    def start_baseline(
        self,
        *,
        root_path: str | None = None,
        location_id: int | None = None,
        selected_paths: tuple[str, ...] = (),
        selected_mount: str | None = None,
    ) -> LocationSession:
        return self._start_integrity(
            BASELINE_KIND,
            root_path=root_path,
            location_id=location_id,
            selected_paths=selected_paths,
            selected_mount=selected_mount,
        )

    def start_verify(
        self,
        *,
        root_path: str | None = None,
        location_id: int | None = None,
        selected_paths: tuple[str, ...] = (),
        selected_mount: str | None = None,
    ) -> LocationSession:
        return self._start_integrity(
            VERIFY_KIND,
            root_path=root_path,
            location_id=location_id,
            selected_paths=selected_paths,
            selected_mount=selected_mount,
        )

    def start_rebaseline(
        self,
        *,
        root_path: str | None = None,
        location_id: int | None = None,
        selected_paths: tuple[str, ...] = (),
        selected_mount: str | None = None,
    ) -> LocationSession:
        if not selected_paths:
            raise ValueError("rebaseline requires an explicit selected scope")
        return self._start_integrity(
            REBASELINE_KIND,
            root_path=root_path,
            location_id=location_id,
            selected_paths=selected_paths,
            selected_mount=selected_mount,
        )

    def save_plan(self, artifact: object) -> None:
        self._runtime.save_plan(artifact)

    def get_plan(self, request_id: str) -> object:
        return self._runtime.get_plan(request_id)

    def drop_plan(self, request_id: str) -> None:
        self._runtime.drop_plan(request_id)

    def get_session(self, session_id: str) -> SessionRecordView:
        return session_record_view(self._dispatcher.get(session_id))

    def list_sessions(self) -> tuple[SessionRecordView, ...]:
        return tuple(session_record_view(item) for item in self._dispatcher.list())

    def observe(self, session_id: str, sink: SessionSink) -> SessionRecordView:
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
        self._dispatcher.close(session_id)

    def get_execution_details(self, run_id: str):
        return self._runtime.get_execution_details(run_id)

    def get_inventory_details(self, request_id: str) -> InventoryDetailsView:
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
        )

    def list_inventory(
        self,
        location_id: int,
        selected_paths: tuple[str, ...] = (),
    ) -> tuple[InventoryRowView, ...]:
        return tuple(
            inventory_row_view(row)
            for row in self._runtime.list_inventory(
                location_id,
                selected_paths,
            )
        )

    def mapping_ids_for_location(self, location_id: int) -> tuple[str, ...]:
        return tuple(
            str(mapping_id)
            for mapping_id in self._runtime.mapping_ids_for_location(
                location_id
            )
        )

    def list_history(self, limit: int = 50):
        return self._runtime.list_history(limit)

    def get_history(self, run_token: str):
        return self._runtime.get_history(run_token)

    def close(self, timeout: float = 10.0) -> ShutdownView:
        with self._lock:
            if self._closed:
                if self._shutdown is None:
                    raise RuntimeError("service shutdown did not complete")
                return self._shutdown
            self._closed = True
        try:
            self._observer.close()
        finally:
            try:
                result = self._dispatcher.shutdown(timeout=timeout)
                view = ShutdownView(
                    complete=result.complete,
                    unfinished=tuple(str(item) for item in result.unfinished),
                    custody_released=result.custody_released,
                )
                with self._lock:
                    self._shutdown = view
            finally:
                self._runtime.close()
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
    ) -> LocationSession:
        request_id = uuid4().hex
        request = integrity_request(
            kind,
            request_id,
            root_path=root_path,
            location_id=location_id,
            selected_paths=selected_paths,
            selected_mount=selected_mount,
        )
        return self._start_location(kind, request_id, request)

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


def _dispatcher(runtime: LocalWorkflowRuntime) -> Dispatcher:
    return Dispatcher(
        _workflow_registry(runtime),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
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


def _validated_paths(source: str, target: str) -> tuple[Path, Path]:
    source_path = Path(source).resolve(strict=True)
    target_path = Path(target).resolve(strict=True)
    if not source_path.is_dir():
        raise NotADirectoryError(f"source is not a directory: {source_path}")
    if not target_path.is_dir():
        raise NotADirectoryError(f"target is not a directory: {target_path}")
    source_key = os.path.normcase(str(source_path))
    target_key = os.path.normcase(str(target_path))
    try:
        common = os.path.normcase(os.path.commonpath((source_key, target_key)))
    except ValueError:
        common = ""
    if common in {source_key, target_key}:
        raise ValueError("source and target overlap")
    return source_path, target_path


__all__ = [
    "ControlView",
    "ExecutionSession",
    "InventoryDetailsView",
    "InventoryRowView",
    "LocationResolutionError",
    "LocationResolutionView",
    "LocationSession",
    "NamiSyncService",
    "PlanSession",
    "PreservationSettingsView",
    "ResultCategory",
    "SemanticSettingsPatchView",
    "SemanticSettingsView",
    "SessionEventView",
    "SessionObserver",
    "SessionRecordView",
    "SessionSink",
    "SessionUpdate",
    "ShutdownView",
    "SyncPathInputError",
    "classify_result",
    "default_database_paths",
]
