from __future__ import annotations

import ast
import io
import json
from collections import deque
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from threading import Event, Lock, Thread

import pytest

import namisync.interfaces.cli as cli_module
from namisync.core.events import (
    Envelope,
    Gap,
    PhaseChanged,
    SCHEMA_VERSION,
    Terminal,
)
from namisync.core.models import VolumeId
from namisync.core.planning import OperationKind
from namisync.core.session import (
    OperationResult,
    SessionId,
    SessionRecord,
    SessionState,
)
from namisync.dispatcher import SessionNotFound
from namisync.interfaces import main as package_main
from namisync.interfaces.service import (
    InventoryDetailsView,
    InventoryRowView,
    LocationResolutionError,
    LocationResolutionView,
    NamiSyncService,
    PreservationSettingsView,
    ResultCategory,
    SemanticSettingsView,
    SessionEventView,
    SessionObserver,
    SessionRecordView,
)
from namisync.workflows import InventoryRequest, LocalWorkflowRuntime
from namisync.workflows.inventory import (
    IntegrityRequest,
    LocationBinding,
    VolumeResolution,
    VolumeResolutionRequired,
    VolumeResolutionState,
)
from namisync.workflows.views import operation_result_view

from _db_fixtures import NOW, operation, plan


def _record(
    session_id: str,
    *,
    terminal: bool = False,
) -> SessionRecord:
    state = SessionState.COMPLETED if terminal else SessionState.RUNNING
    return SessionRecord(
        SessionId(session_id),
        "test",
        state,
        (),
        b"payload",
        True,
        0,
        NOW,
        started_at=NOW,
        ended_at=NOW if terminal else None,
        result=OperationResult(SessionState.COMPLETED) if terminal else None,
    )


def _envelope(session_id: str, sequence: int, body: object) -> Envelope:
    return Envelope(
        SessionId(session_id),
        sequence,
        NOW,
        SCHEMA_VERSION,
        body,
    )


class _SequenceStream:
    def __init__(self, *items: Envelope) -> None:
        self._items = deque(items)
        self.closed = False
        self.next_arguments: list[tuple[object, ...]] = []

    def next(self, *args) -> Envelope:
        self.next_arguments.append(args)
        if self.closed or not self._items:
            raise StopIteration
        return self._items.popleft()

    def close(self) -> None:
        self.closed = True


class _BlockingStream:
    def __init__(
        self,
        name: str,
        *,
        close_log: list[str] | None = None,
        all_closed: Event | None = None,
        close_count: list[int] | None = None,
        close_lock: Lock | None = None,
    ) -> None:
        self.name = name
        self.entered = Event()
        self.released = Event()
        self.closed = False
        self.next_arguments: list[tuple[object, ...]] = []
        self._close_log = close_log
        self._all_closed = all_closed
        self._close_count = close_count
        self._close_lock = close_lock

    def next(self, *args) -> Envelope:
        self.next_arguments.append(args)
        self.entered.set()
        self.released.wait(2.0)
        if self._all_closed is not None:
            self._all_closed.wait(2.0)
        raise StopIteration

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self._close_log is not None:
            self._close_log.append(f"close:{self.name}")
        if self._close_count is not None and self._close_lock is not None:
            with self._close_lock:
                self._close_count[0] += 1
                if (
                    self._all_closed is not None
                    and self._close_count[0] == 2
                ):
                    self._all_closed.set()
        self.released.set()


def test_observe_returns_finished_record_without_subscribing() -> None:
    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id, terminal=True)

        def subscribe(self, session_id: str, from_seq=None):
            raise AssertionError("finished session must not subscribe")

    observer = SessionObserver(Dispatcher())
    updates = []

    current = observer.observe("finished", updates.append)

    assert current.result is not None
    assert updates == []
    observer.close()


def test_interfaces_package_preserves_lazy_main_entry_point() -> None:
    stderr = io.StringIO()

    result = package_main([], stdout=io.StringIO(), stderr=stderr)

    assert result == 2
    assert "usage:" in stderr.getvalue()


def test_interface_views_are_recursive_json_primitives_without_duck_typing() -> None:
    result = operation_result_view(OperationResult(SessionState.COMPLETED))
    views = (
        SessionEventView(
            session_id="session",
            sequence=1,
            at=NOW.isoformat(),
            body_type="PhaseChanged",
            body={"phase": "inventory"},
        ),
        SessionRecordView(
            session_id="session",
            kind="inventory",
            state="completed",
            supports_pause=False,
            created_at=NOW.isoformat(),
            started_at=NOW.isoformat(),
            ended_at=NOW.isoformat(),
            result=result,
        ),
        InventoryRowView(
            row_id="row",
            location_id="7",
            path="file.bin",
            path_key="file.bin",
            entry_kind="file",
            presence="present",
            size=7,
            mtime_ns=1,
            has_baseline=True,
            last_observed_at=NOW.isoformat(),
            last_verified_at=NOW.isoformat(),
            missing_since=None,
            acknowledged_at=None,
            reappeared_at=None,
            unsupported_reason=None,
        ),
        SemanticSettingsView(
            filters=("*.tmp",),
            deletion_policy="trash",
            trash_on_update=True,
            preservation=PreservationSettingsView(False, False, False),
            propagate_source_casing=False,
        ),
        LocationResolutionView(
            state="resolved",
            root_path=r"F:\library",
            location_id=7,
            selected_mount="F:\\",
            candidates=("F:\\",),
            detail=None,
        ),
        InventoryDetailsView(
            request_id="inventory",
            state="resolved",
            root_path=r"F:\library",
            location_id=7,
            selected_mount="F:\\",
            candidates=("F:\\",),
            detail=None,
            selected_paths=("file.bin",),
            observed_count=1,
            missing_count=0,
            complete=True,
        ),
        ResultCategory(
            headline="success",
            filesystem="completed",
            integrity="not-run",
            recording="ok",
            audit="ok",
            disposition="ran",
            canceled=False,
        ),
    )

    json.dumps([asdict(view) for view in views])
    tree = ast.parse(Path(cli_module.__file__).read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "hasattr"
        for node in ast.walk(tree)
    )


def test_finish_between_get_and_subscribe_returns_terminal_record() -> None:
    class Dispatcher:
        def __init__(self) -> None:
            self.get_count = 0

        def get(self, session_id: str) -> SessionRecord:
            self.get_count += 1
            return _record(session_id, terminal=self.get_count > 1)

        def subscribe(self, session_id: str, from_seq=None):
            raise SessionNotFound(session_id)

    observer = SessionObserver(Dispatcher())

    current = observer.observe("raced", lambda _update: None)

    assert current.result is not None
    observer.close()


def test_unsubscribe_closes_blocking_stream_and_uses_no_poll_timeout() -> None:
    stream = _BlockingStream("live")

    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            return stream

    observer = SessionObserver(Dispatcher())
    observer.observe("live", lambda _update: None)
    assert stream.entered.wait(0.5)

    observer.unsubscribe("live")
    observer.unsubscribe("live")

    assert stream.closed
    assert stream.next_arguments == [()]
    observer.close()


def test_close_closes_every_stream_before_joining_observers() -> None:
    log: list[str] = []
    all_closed = Event()
    close_count = [0]
    close_lock = Lock()
    streams = {
        name: _BlockingStream(
            name,
            close_log=log,
            all_closed=all_closed,
            close_count=close_count,
            close_lock=close_lock,
        )
        for name in ("one", "two")
    }

    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            return streams[session_id]

    observer = SessionObserver(Dispatcher())
    for session_id in streams:
        observer.observe(session_id, lambda _update: None)
    assert all(stream.entered.wait(0.5) for stream in streams.values())

    observer.close()
    observer.close()

    assert log[:2] == ["close:one", "close:two"]
    assert all(stream.closed for stream in streams.values())


def test_observer_close_timeout_retains_thread_for_retry() -> None:
    session_id = "slow-sink"
    stream = _SequenceStream(
        _envelope(session_id, 1, PhaseChanged("blocked"))
    )
    sink_entered = Event()
    release_sink = Event()

    class Dispatcher:
        def get(self, requested: str) -> SessionRecord:
            return _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            assert requested == session_id
            return stream

    def sink(_update) -> None:
        sink_entered.set()
        assert release_sink.wait(2)

    observer = SessionObserver(Dispatcher(), join_timeout=0.05)
    observer.observe(session_id, sink)
    assert sink_entered.wait(0.5)
    observation = observer._observations[session_id]

    with pytest.raises(TimeoutError, match="slow-sink"):
        observer.close()
    assert observer._observations[session_id] is observation

    release_sink.set()
    assert observation.done.wait(0.5)
    observer.close()
    observer.close()
    assert observer._observations == {}


def test_gap_recovery_resubscribes_from_first_undelivered_sequence() -> None:
    session_id = "gap"
    terminal_result = OperationResult(SessionState.COMPLETED)
    first = _SequenceStream(
        _envelope(session_id, 1, PhaseChanged("one")),
        _envelope(session_id, 3, Gap(first_missed_seq=2)),
    )
    second = _SequenceStream(
        _envelope(session_id, 2, PhaseChanged("two")),
        _envelope(session_id, 4, Terminal(terminal_result)),
    )
    terminal_record = _record(session_id, terminal=True)

    class Dispatcher:
        def __init__(self) -> None:
            self.subscribe_calls: list[int | None] = []
            self.finished = False

        def get(self, requested: str) -> SessionRecord:
            return terminal_record if self.finished else _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            self.subscribe_calls.append(from_seq)
            if len(self.subscribe_calls) == 1:
                return first
            return second

    dispatcher = Dispatcher()
    observer = SessionObserver(dispatcher)
    updates: list[SessionEventView | SessionRecordView] = []
    completed = Event()

    def receive(update: SessionEventView | SessionRecordView) -> None:
        updates.append(update)
        if isinstance(update, SessionEventView) and update.body_type == "Terminal":
            dispatcher.finished = True
        if isinstance(update, SessionRecordView) and update.result is not None:
            completed.set()

    observer.observe(session_id, receive)
    assert completed.wait(0.5)
    observer.close()

    events = [item for item in updates if isinstance(item, SessionEventView)]
    assert dispatcher.subscribe_calls == [None, 2]
    assert [item.body_type for item in events] == [
        "PhaseChanged",
        "Gap",
        "PhaseChanged",
        "Terminal",
    ]
    assert [
        item.body["phase"]
        for item in events
        if item.body_type == "PhaseChanged"
    ] == ["one", "two"]


def test_sink_exception_closes_stream_and_does_not_block_shutdown() -> None:
    stream = _SequenceStream(_envelope("sink", 1, PhaseChanged("explode")))
    closed = Event()
    original_close = stream.close

    def close() -> None:
        original_close()
        closed.set()

    stream.close = close

    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            return stream

    observer = SessionObserver(Dispatcher())

    def explode(_update) -> None:
        raise RuntimeError("sink failed")

    observer.observe("sink", explode)
    assert closed.wait(0.5)
    with pytest.raises(RuntimeError, match="session observation failed") as raised:
        observer.wait("sink")
    assert isinstance(raised.value.__cause__, RuntimeError)
    assert str(raised.value.__cause__) == "sink failed"
    observer.close()


def test_sink_can_unsubscribe_itself_without_self_join_or_deadlock() -> None:
    stream = _SequenceStream(
        _envelope("self-unsubscribe", 1, PhaseChanged("inventory"))
    )

    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            return stream

    observer = SessionObserver(Dispatcher())
    returned = Event()

    def receive(_update) -> None:
        observer.unsubscribe("self-unsubscribe")
        returned.set()

    observer.observe("self-unsubscribe", receive)

    assert returned.wait(0.5)
    assert stream.closed
    observer.close()


def test_service_shutdown_orders_observer_dispatcher_and_runtime() -> None:
    log: list[str] = []

    class Observer:
        def close(self) -> None:
            log.append("observer")

    class Dispatcher:
        def shutdown(self, timeout: float):
            log.append("dispatcher")
            return SimpleNamespace(
                complete=True,
                unfinished=(),
                custody_released=True,
            )

    class Runtime:
        def close(self) -> None:
            log.append("runtime")

    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = Dispatcher()
    service._runtime = Runtime()
    service._lock = Lock()
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False

    first = service.close()
    second = service.close()

    assert log == ["observer", "dispatcher", "runtime"]
    assert first is second
    assert first.complete


def test_incomplete_service_shutdown_keeps_runtime_open_and_can_retry() -> None:
    log: list[str] = []
    shutdowns = [
        SimpleNamespace(
            complete=False,
            unfinished=("running-session",),
            custody_released=False,
        ),
        SimpleNamespace(
            complete=True,
            unfinished=(),
            custody_released=True,
        ),
    ]

    class Observer:
        def close(self) -> None:
            log.append("observer")

    class Dispatcher:
        def shutdown(self, timeout: float):
            log.append("dispatcher")
            return shutdowns.pop(0)

    class Runtime:
        def close(self) -> None:
            log.append("runtime")

    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = Dispatcher()
    service._runtime = Runtime()
    service._lock = Lock()
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False

    incomplete = service.close(timeout=0)
    assert not incomplete.complete
    assert log == ["observer", "dispatcher"]
    with pytest.raises(RuntimeError, match="service is closed"):
        service.read_semantic_settings()
    with pytest.raises(RuntimeError, match="service is closed"):
        service.start_inventory(root_path="F:\\library")
    assert log == ["observer", "dispatcher"]

    complete = service.close(timeout=1)
    cached = service.close(timeout=1)

    assert complete.complete
    assert cached is complete
    assert log == ["observer", "dispatcher", "dispatcher", "runtime"]


def test_service_close_retries_an_observer_join_failure() -> None:
    log: list[str] = []
    observer_attempts = 0

    class Observer:
        def close(self) -> None:
            nonlocal observer_attempts
            observer_attempts += 1
            log.append("observer")
            if observer_attempts == 1:
                raise TimeoutError("observer still running")

    class Dispatcher:
        def shutdown(self, timeout: float):
            log.append("dispatcher")
            return SimpleNamespace(
                complete=True,
                unfinished=(),
                custody_released=True,
            )

    class Runtime:
        def close(self) -> None:
            log.append("runtime")

    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = Dispatcher()
    service._runtime = Runtime()
    service._lock = Lock()
    service._close_lock = Lock()
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False
    service._observer_closed = False

    with pytest.raises(TimeoutError, match="observer still running"):
        service.close()
    completed = service.close()
    cached = service.close()

    assert completed.complete
    assert cached is completed
    assert log == ["observer", "dispatcher", "runtime", "observer"]


def test_runtime_close_failure_can_be_retried_without_repeating_shutdown() -> None:
    log: list[str] = []
    close_attempts = 0

    class Observer:
        def close(self) -> None:
            log.append("observer")

    class Dispatcher:
        def shutdown(self, timeout: float):
            log.append("dispatcher")
            return SimpleNamespace(
                complete=True,
                unfinished=(),
                custody_released=True,
            )

    class Runtime:
        def close(self) -> None:
            nonlocal close_attempts
            close_attempts += 1
            log.append("runtime")
            if close_attempts == 1:
                raise RuntimeError("history close failed")

    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = Dispatcher()
    service._runtime = Runtime()
    service._lock = Lock()
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False

    with pytest.raises(RuntimeError, match="history close failed"):
        service.close()
    completed = service.close()
    cached = service.close()

    assert completed.complete
    assert cached is completed
    assert log == ["observer", "dispatcher", "runtime", "runtime"]


def test_concurrent_service_close_serializes_dependency_retry() -> None:
    first_runtime_close = Event()
    release_first_close = Event()
    second_started = Event()
    second_done = Event()
    close_attempts = 0
    shutdown_attempts = 0

    class Observer:
        def close(self) -> None:
            pass

    class Dispatcher:
        def shutdown(self, timeout: float):
            nonlocal shutdown_attempts
            shutdown_attempts += 1
            return SimpleNamespace(
                complete=True,
                unfinished=(),
                custody_released=True,
            )

    class Runtime:
        def close(self) -> None:
            nonlocal close_attempts
            close_attempts += 1
            if close_attempts == 1:
                first_runtime_close.set()
                assert release_first_close.wait(2)
                raise RuntimeError("first close failed")

    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = Dispatcher()
    service._runtime = Runtime()
    service._lock = Lock()
    service._close_lock = Lock()
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False
    first_errors: list[Exception] = []
    second_results: list[object] = []

    def first_close() -> None:
        try:
            service.close()
        except Exception as error:
            first_errors.append(error)

    def second_close() -> None:
        second_started.set()
        second_results.append(service.close())
        second_done.set()

    first = Thread(target=first_close)
    second = Thread(target=second_close)
    first.start()
    assert first_runtime_close.wait(1)
    second.start()
    assert second_started.wait(1)
    assert not second_done.wait(0.1)
    release_first_close.set()
    first.join(2)
    second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(first_errors) == 1
    assert str(first_errors[0]) == "first close failed"
    assert second_results[0].complete
    assert shutdown_attempts == 1
    assert close_attempts == 2


def test_workflow_runtime_retains_a_store_whose_close_failed() -> None:
    attempts = 0

    class Store:
        def close(self) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("writer close failed")

    store = Store()
    runtime = object.__new__(LocalWorkflowRuntime)
    runtime._lock = Lock()
    runtime._close_lock = Lock()
    runtime._closed = False
    runtime._history_store = store

    with pytest.raises(RuntimeError, match="writer close failed"):
        runtime.close()
    assert not runtime._closed
    assert runtime._history_store is store

    runtime.close()
    assert runtime._closed
    assert runtime._history_store is None
    assert attempts == 2


def test_concurrent_workflow_runtime_close_waits_for_failed_attempt() -> None:
    first_entered = Event()
    release_first = Event()
    second_started = Event()
    second_done = Event()
    attempts = 0

    class Store:
        def close(self) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                first_entered.set()
                assert release_first.wait(2)
                raise RuntimeError("writer close failed")

    store = Store()
    runtime = object.__new__(LocalWorkflowRuntime)
    runtime._lock = Lock()
    runtime._close_lock = Lock()
    runtime._closed = False
    runtime._history_store = store
    first_errors: list[Exception] = []

    def first_close() -> None:
        try:
            runtime.close()
        except Exception as error:
            first_errors.append(error)

    def second_close() -> None:
        second_started.set()
        runtime.close()
        second_done.set()

    first = Thread(target=first_close)
    second = Thread(target=second_close)
    first.start()
    assert first_entered.wait(1)
    second.start()
    assert second_started.wait(1)
    assert not second_done.wait(0.1)
    release_first.set()
    first.join(2)
    second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(first_errors) == 1
    assert second_done.is_set()
    assert attempts == 2
    assert runtime._closed
    assert runtime._history_store is None


def test_service_execution_opt_in_reaches_runtime_without_changing_default() -> None:
    calls: list[tuple[str, bool]] = []
    artifact = SimpleNamespace(plan=plan((operation(OperationKind.NOOP),)))

    class Runtime:
        def get_plan(self, request_id: str):
            return artifact

        def commit_plan(
            self,
            request_id: str,
            *,
            verify_after_execute: bool = False,
            user_deselected=frozenset(),
            expected_artifact=None,
        ):
            assert user_deselected == frozenset()
            assert expected_artifact is artifact
            calls.append((request_id, verify_after_execute))
            return SimpleNamespace(
                execution_set=SimpleNamespace(run_id=f"run-{request_id}")
            )

    class Dispatcher:
        def submit(self, kind: str, request: object):
            assert kind == "sync-execution"
            return f"session-{len(calls)}"

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()
    service._dispatcher = Dispatcher()
    service._lock = Lock()
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}

    default = service.start_execution("default")
    verified = service.start_execution(
        "verified",
        verify_after_execute=True,
    )

    assert calls == [("default", False), ("verified", True)]
    assert (default.run_id, default.session_id) == (
        "run-default",
        "session-1",
    )
    assert (verified.run_id, verified.session_id) == (
        "run-verified",
        "session-2",
    )


def test_location_commands_submit_exact_typed_workflow_requests() -> None:
    submitted: list[tuple[str, object]] = []

    class Dispatcher:
        def submit(self, kind: str, request: object) -> str:
            submitted.append((kind, request))
            return f"session-{kind}"

    service = object.__new__(NamiSyncService)
    service._dispatcher = Dispatcher()

    inventory = service.start_inventory(
        root_path=r"F:\library",
        selected_paths=("a.bin",),
    )
    baseline = service.start_baseline(location_id=7)
    verify = service.start_verify(
        location_id=7,
        selected_mount="F:\\",
    )
    rebaseline = service.start_rebaseline(
        location_id=7,
        selected_paths=("a.bin",),
    )

    assert [kind for kind, _ in submitted] == [
        "inventory",
        "baseline",
        "verify",
        "rebaseline",
    ]
    assert isinstance(submitted[0][1], InventoryRequest)
    assert submitted[0][1].root_path == r"F:\library"
    assert submitted[0][1].selected_paths == ("a.bin",)
    assert all(
        isinstance(request, IntegrityRequest)
        for _, request in submitted[1:]
    )
    assert [
        request.mode.value for _, request in submitted[1:]
    ] == ["baseline", "verify", "rebaseline"]
    assert inventory.session_id == "session-inventory"
    assert baseline.session_id == "session-baseline"
    assert verify.session_id == "session-verify"
    assert rebaseline.session_id == "session-rebaseline"


def test_rebaseline_refuses_an_unselected_scope_before_submission() -> None:
    class Dispatcher:
        def submit(self, kind: str, request: object) -> str:
            raise AssertionError("unselected rebaseline must not be submitted")

    service = object.__new__(NamiSyncService)
    service._dispatcher = Dispatcher()

    with pytest.raises(ValueError, match="explicit selected scope"):
        service.start_rebaseline(location_id=7)


@pytest.mark.parametrize(
    ("state", "selected_mount", "candidates", "root_path"),
    [
        (VolumeResolutionState.OFFLINE, "<unmounted>", (), None),
        (
            VolumeResolutionState.AMBIGUOUS,
            "F:\\",
            ("F:\\", "G:\\"),
            None,
        ),
        (
            VolumeResolutionState.ROOT_MISSING,
            "F:\\",
            ("F:\\",),
            r"F:\library",
        ),
        (
            VolumeResolutionState.ROOT_UNAVAILABLE,
            "F:\\",
            ("F:\\",),
            r"F:\library",
        ),
    ],
)
def test_location_resolution_is_primitive_and_precedes_admission(
    state: VolumeResolutionState,
    selected_mount: str,
    candidates: tuple[str, ...],
    root_path: str | None,
) -> None:
    expected_mounts = candidates or (selected_mount,)
    binding = LocationBinding(
        VolumeId("serial", "NTFS"),
        "library",
        selected_mount,
        expected_mounts,
        False,
        7,
    )
    resolution = VolumeResolution(
        state,
        binding,
        root_path=root_path,
        candidates=candidates,
        detail="resolution detail",
    )

    class Dispatcher:
        def submit(self, kind: str, request: object) -> str:
            raise VolumeResolutionRequired(resolution)

    service = object.__new__(NamiSyncService)
    service._dispatcher = Dispatcher()

    with pytest.raises(LocationResolutionError) as raised:
        service.start_verify(location_id=7)

    view = raised.value.resolution
    assert view.state == state.value
    assert view.root_path == root_path
    assert view.location_id == 7
    assert view.selected_mount == (
        None
        if selected_mount == "<unmounted>"
        or state is VolumeResolutionState.AMBIGUOUS
        else selected_mount
    )
    assert view.candidates == candidates
    assert view.detail == "resolution detail"


def test_ambiguous_resolution_preserves_only_a_real_explicit_choice() -> None:
    binding = LocationBinding(
        VolumeId("serial", "NTFS"),
        "library",
        "F:\\",
        ("F:\\", "G:\\"),
        True,
        7,
    )
    resolution = VolumeResolution(
        VolumeResolutionState.AMBIGUOUS,
        binding,
        candidates=("F:\\", "G:\\"),
        detail="mounted candidates changed",
    )

    class Dispatcher:
        def submit(self, kind: str, request: object) -> str:
            raise VolumeResolutionRequired(resolution)

    service = object.__new__(NamiSyncService)
    service._dispatcher = Dispatcher()

    with pytest.raises(LocationResolutionError) as raised:
        service.start_verify(location_id=7)

    assert raised.value.resolution.selected_mount == "F:\\"
