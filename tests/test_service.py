from __future__ import annotations

import ast
import gc
import io
import json
import sys
from hashlib import blake2b
from collections import deque
from dataclasses import asdict, replace
from pathlib import Path
import threading
from types import SimpleNamespace
from threading import current_thread, Event, Lock, Thread
from unittest.mock import Mock
from weakref import ref

import pytest

import namisync.interfaces.cli as cli_module
import namisync.interfaces.service as service_module
from namisync.core.events import (
    Envelope,
    Gap,
    ItemOutcome,
    PhaseChanged,
    CORE_EVENT_SCHEMA_VERSION,
    Terminal,
    TerminalSummary,
)
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.integrity import IntegrityOutcome, IntegrityResult
from namisync.core.models import ScanWarning, ScanWarningCode, VolumeId
from namisync.core.planning import OperationKind
from namisync.core.session import (
    OperationResult,
    SessionId,
    SessionRecord,
    SessionState,
)
from namisync.dispatcher import SessionCleanupPending, SessionNotFound
from namisync.db.history import HistoryContext, HistoryStore, HistoryWindowPolicy
from namisync.db.writer import DEFAULT_RETRY_TIMEOUT_SECONDS
from namisync.interfaces import main as package_main
from namisync.interfaces.service import (
    CommandIdConflictError,
    InventoryDetailsView,
    InventoryRowView,
    LocationResolutionError,
    LocationResolutionView,
    NamiSyncService,
    PreservationSettingsView,
    ResultClassificationView,
    SemanticSettingsView,
    SessionEventView,
    SessionRecordView,
)
from namisync.interfaces.session_observer import SessionObserver
from namisync.interfaces.task_lifecycle import (
    LifecycleAssociationError,
    TASK_EFFECT_CAPACITY,
    TaskLifecycle,
)
from namisync.interfaces.task_port import (
    TaskCloseView,
    TaskSessionReleaseView,
    TaskStartView,
    TaskTerminalDelivery,
    TaskUnavailableError,
)
from namisync.workflows import (
    ExecutionDetails,
    HistoryEventView,
    InventoryDetails,
    InventoryRequest,
    LocalWorkflowRuntime,
)
from namisync.workflows.runtime import HISTORY_WRITER_RETRY_TIMEOUT_SECONDS
from namisync.workflows.models import RefusalView
from namisync.workflows.inventory import (
    IntegrityRequest,
    LocationBinding,
    VolumeResolution,
    VolumeResolutionRequired,
    VolumeResolutionState,
)
from namisync.workflows.views import (
    operation_result_view,
    session_event_view,
    session_record_view,
)

from _db_fixtures import FakeClock, NOW, operation, plan


def _raise_private_observer_failure(
    references: list[object],
    *,
    exception_base: type[BaseException] = Exception,
    hostile_text: bool = False,
) -> None:
    payload_type = type("PrivateObserverPayload", (), {})

    def render(_error: BaseException) -> str:
        raise AssertionError("private observer failure text was rendered")

    failure_type = type(
        "PrivateObserverFailure",
        (exception_base,),
        {"__str__": render} if hostile_text else {},
    )
    attached_payload = payload_type()
    cause_payload = payload_type()
    frame_only_payload = payload_type()
    cause = failure_type("private observer cause")
    cause.payload = cause_payload
    failure = failure_type("private observer failure")
    failure.payload = attached_payload
    references.extend(
        ref(value)
        for value in (
            payload_type,
            failure_type,
            attached_payload,
            cause_payload,
            frame_only_payload,
        )
    )
    raise failure from cause


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
        None if terminal else b"payload",
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
        CORE_EVENT_SCHEMA_VERSION,
        body,
    )


def _task_terminal_truth(
    session_id: str,
) -> tuple[SessionRecord, TaskTerminalDelivery]:
    result = OperationResult(SessionState.COMPLETED)
    record = SessionRecord(
        session_id=SessionId(session_id),
        kind="sync-plan",
        state=SessionState.COMPLETED,
        resources=(),
        checkpoint=None,
        supports_pause=False,
        admission_order=0,
        created_at=NOW,
        started_at=NOW,
        ended_at=NOW,
        result=result,
    )
    delivery = TaskTerminalDelivery(
        session_record_view(record),
        session_event_view(
            _envelope(
                session_id,
                1,
                Terminal(TerminalSummary.from_result(result)),
            )
        ),
    )
    return record, delivery


def _publish_session(
    lifecycle: TaskLifecycle,
    session_id: str,
    *,
    kind: str,
    command_id: str | None = None,
    signature: tuple[object, ...] = (),
    task_id: str | None = None,
    detail_owner: tuple[str, str] | None = None,
    request_id: str | None = None,
):
    admission = lifecycle.begin_admission(
        kind,
        command_id,
        signature,
        task_id=task_id,
        detail_owner=detail_owner,
    )
    lifecycle.attach_session(admission, session_id)
    association, _receipt = lifecycle.publish_start(
        admission,
        session_id,
        session_id if request_id is None else request_id,
    )
    return association


def _publish_task_plan(
    lifecycle: TaskLifecycle,
    session_id: str,
    command_id: str,
    request_id: str,
    signature: tuple[object, ...],
    *,
    detail_owner: tuple[str, str] | None = None,
) -> tuple[str, object]:
    task = lifecycle.begin_task_start(command_id, signature)
    association = _publish_session(
        lifecycle,
        session_id,
        kind="task-plan",
        command_id=command_id,
        signature=signature,
        task_id=task.task_id,
        detail_owner=detail_owner,
        request_id=request_id,
    )
    return task.task_id, association


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
    assert observer._subscriptions == {}
    observer.close()


def test_interfaces_package_preserves_lazy_main_entry_point() -> None:
    stderr = io.StringIO()

    result = package_main([], stdout=io.StringIO(), stderr=stderr)

    assert result == 2
    assert "usage:" in stderr.getvalue()


def test_history_facade_exposes_only_bounded_summary_and_page_reads() -> None:
    calls: list[tuple[object, ...]] = []
    summaries = (object(),)
    summary = object()
    item_page = object()
    event_page = object()

    class Runtime:
        def list_history(self, limit: int):
            calls.append(("list", limit))
            return summaries

        def get_history_summary(self, run_token: str):
            calls.append(("summary", run_token))
            return summary

        def get_history_items(self, run_token: str, **options):
            calls.append(("items", run_token, options))
            return item_page

        def get_history_events(self, run_token: str, **options):
            calls.append(("events", run_token, options))
            return event_page

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()

    assert service.list_history(7) is summaries
    assert service.get_history_summary("run") is summary
    assert service.get_history_items(
        "run", after_order=4, through_order=12, limit=8
    ) is item_page
    assert service.get_history_events(
        "run", after_seq=9, through_seq=30, limit=16
    ) is event_page
    assert not hasattr(service, "get_history")
    assert calls == [
        ("list", 7),
        ("summary", "run"),
        (
            "items",
            "run",
            {"after_order": 4, "through_order": 12, "limit": 8},
        ),
        (
            "events",
            "run",
            {"after_seq": 9, "through_seq": 30, "limit": 16},
        ),
    ]


def test_history_service_repairs_a_gap_through_one_fixed_durable_watermark(
    tmp_path: Path,
) -> None:
    history = tmp_path / "history.db"
    ledger = tmp_path / "ledger.db"
    record = SessionRecord(
        SessionId("1" * 32),
        "inventory",
        SessionState.RUNNING,
        (),
        b"payload",
        False,
        0,
        NOW,
        started_at=NOW,
    )
    with HistoryStore(history, clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext(
                "recovery-run",
                "host",
                activity_kind="inventory",
                subject_kind="location",
                subject_id="7",
            ),
        )
        # Odd sequence numbers stand in for lossy Progress events, which are
        # deliberately absent from durable history.
        for sequence in range(2, 602, 2):
            observer.on_event(
                Envelope(
                    record.session_id,
                    sequence,
                    NOW,
                    CORE_EVENT_SCHEMA_VERSION,
                    PhaseChanged("inventory"),
                )
            )
        observer.finalize(OperationResult(SessionState.COMPLETED))

    with NamiSyncService(ledger, history) as service:
        events_by_sequence: dict[int, SessionEventView] = {}
        after_seq = 0
        through_seq = None
        page_count = 0
        while True:
            page = service.get_history_events(
                "recovery-run",
                after_seq=after_seq,
                through_seq=through_seq,
                limit=128,
            )
            page_count += 1
            if through_seq is None:
                through_seq = page.through_seq
                # The catch-up consumer may overlap live replay with the first
                # durable page; keyed application makes that replay harmless.
                for event in page.events:
                    events_by_sequence[event.sequence] = event
            for event in page.events:
                events_by_sequence[event.sequence] = event
            if not page.has_more:
                break
            after_seq = page.next_after_seq

        summary = service.get_history_summary("recovery-run")

    assert page_count == 3
    assert through_seq == 600
    assert tuple(events_by_sequence) == tuple(range(2, 602, 2))
    assert all(
        event.body_type != "Terminal" for event in events_by_sequence.values()
    )
    assert summary.completion_status == "finalized"
    assert summary.current_state == "completed"
    assert summary.filesystem_status == "completed"
    assert summary.headline == "success"


def test_history_event_views_preserve_the_exact_persisted_v5_contract(
    tmp_path: Path,
) -> None:
    history = tmp_path / "history.db"
    ledger = tmp_path / "ledger.db"
    record = _record("a" * 32)
    with HistoryStore(history, clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext("exact-v5-run", "host"),
        )
        observer.on_event(
            Envelope(
                record.session_id,
                1,
                NOW,
                CORE_EVENT_SCHEMA_VERSION,
                PhaseChanged("current-inventory"),
            )
        )
        observer.close()

    with NamiSyncService(ledger, history) as service:
        page = service.get_history_events("exact-v5-run")

    assert all(type(event) is HistoryEventView for event in page.events)
    assert all(not isinstance(event, SessionEventView) for event in page.events)
    assert [event.schema_version for event in page.events] == [5]
    assert [event.body for event in page.events] == [
        {"phase": "current-inventory"},
    ]


def test_history_service_ends_a_fresh_traversal_ahead_of_durability(
    tmp_path: Path,
) -> None:
    history = tmp_path / "history.db"
    ledger = tmp_path / "ledger.db"
    record = SessionRecord(
        SessionId("2" * 32),
        "inventory",
        SessionState.RUNNING,
        (),
        b"payload",
        False,
        0,
        NOW,
        started_at=NOW,
    )
    with HistoryStore(history, clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext(
                "recovery-ahead-run",
                "host",
                activity_kind="inventory",
                subject_kind="location",
                subject_id="7",
            ),
        )
        observer.on_event(
            Envelope(
                record.session_id,
                1,
                NOW,
                CORE_EVENT_SCHEMA_VERSION,
                PhaseChanged("inventory"),
            )
        )
        observer.flush()

    with NamiSyncService(ledger, history) as service:
        page = service.get_history_events(
            "recovery-ahead-run",
            after_seq=2,
        )

    assert page.through_seq == 1
    assert page.next_after_seq == 2
    assert page.events == ()
    assert not page.has_more


def test_history_service_exposes_receipts_and_degradation_counts(
    tmp_path: Path,
) -> None:
    history = tmp_path / "history.db"
    ledger = tmp_path / "ledger.db"
    record = _record("3" * 32)
    oversized = ItemOutcome(
        "4" * 32,
        "copy",
        "large.bin",
        Outcome.SUCCEEDED,
        detail={"message": "x" * 500},
    )
    with HistoryStore(
        history,
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(
            max_bytes=512,
            max_event_bytes=512,
        ),
    ) as store:
        observer = store.observer(
            record,
            HistoryContext("receipt-run", "host"),
        )
        assert (
            observer.on_event(
                Envelope(
                    record.session_id,
                    1,
                    NOW,
                    CORE_EVENT_SCHEMA_VERSION,
                    oversized,
                )
            )
            is RecordingStatus.DEGRADED
        )
        observer.finalize(OperationResult(SessionState.COMPLETED))

    with NamiSyncService(ledger, history) as service:
        summary = service.get_history_summary("receipt-run")
        page = service.get_history_events("receipt-run")

    assert summary.item_count == 0
    assert summary.duplicate_item_count == 0
    assert summary.rejected_event_count == 1
    assert summary.audit_status == RecordingStatus.DEGRADED.value
    assert page.events[0].session_id == "3" * 32
    assert page.events[0].schema_version == CORE_EVENT_SCHEMA_VERSION
    assert page.events[0].disposition == "rejected"
    assert page.events[0].body is None
    assert page.events[0].rejection_reason == "event-too-large"
    assert len(page.events[0].payload_hash) == 64
    assert len(page.events[0].receipt_hash) == 64


def test_history_service_exposes_cleanly_flushed_nonterminal_run_as_incomplete(
    tmp_path: Path,
) -> None:
    history = tmp_path / "history.db"
    record = SessionRecord(
        SessionId("5" * 32),
        "inventory",
        SessionState.RUNNING,
        (),
        b"payload",
        False,
        0,
        NOW,
        started_at=NOW,
    )
    with HistoryStore(history, clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext(
                "incomplete-run",
                "host",
                activity_kind="inventory",
                subject_kind="location",
                subject_id="7",
            ),
        )
        observer.on_event(
            Envelope(
                record.session_id,
                3,
                NOW,
                CORE_EVENT_SCHEMA_VERSION,
                PhaseChanged("inventory"),
            )
        )
        observer.close()

    with NamiSyncService(tmp_path / "ledger.db", history) as service:
        summary = service.get_history_summary("incomplete-run")

    assert summary.completion_status == "incomplete"
    assert summary.headline == "incomplete"
    assert summary.current_state == "running"
    assert summary.current_phase == "inventory"
    assert summary.last_committed_seq == 3
    assert summary.filesystem_status is None
    assert summary.ended_at is None


@pytest.mark.parametrize(
    ("run_token", "result"),
    [
        (
            "retained-canceled",
            OperationResult(SessionState.CANCELED, canceled=True),
        ),
        (
            "retained-mismatch",
            OperationResult(
                SessionState.COMPLETED,
                items=(
                    IntegrityOutcome(
                        "mismatch",
                        None,
                        None,
                        "mismatch.bin",
                        IntegrityResult.MISMATCHED,
                    ),
                ),
            ),
        ),
        (
            "retained-partial-degraded",
            OperationResult(
                SessionState.COMPLETED,
                audit=RecordingStatus.DEGRADED,
                items=(
                    ItemOutcome(
                        "a" * 32,
                        OperationKind.NOOP.value,
                        "blocked.bin",
                        Outcome.BLOCKED,
                    ),
                ),
            ),
        ),
        (
            "retained-all-noop",
            OperationResult(
                SessionState.COMPLETED,
                items=(
                    ItemOutcome(
                        "b" * 32,
                        OperationKind.NOOP.value,
                        "selected.bin",
                        Outcome.SKIPPED,
                    ),
                ),
            ),
        ),
        (
            "retained-deselected-noop",
            OperationResult(
                SessionState.COMPLETED,
                items=(
                    ItemOutcome(
                        "c" * 32,
                        OperationKind.NOOP.value,
                        "deselected.bin",
                        Outcome.SKIPPED,
                        reason="user-deselected",
                    ),
                ),
            ),
        ),
    ],
)
def test_retained_summary_classification_matches_live_result(
    tmp_path: Path, run_token: str, result: OperationResult
) -> None:
    history = tmp_path / f"{run_token}.db"
    ledger = tmp_path / f"{run_token}-ledger.db"
    record = SessionRecord(
        SessionId(blake2b(run_token.encode("utf-8"), digest_size=16).hexdigest()),
        "sync-execution",
        SessionState.RUNNING,
        (),
        b"payload",
        True,
        0,
        NOW,
        started_at=NOW,
    )
    with HistoryStore(history, clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext(
                run_token,
                "host",
                activity_kind="sync",
                source_context="source",
                target_context="target",
            ),
        )
        for sequence, item in enumerate(result.items, start=1):
            observer.on_event(
                Envelope(
                    record.session_id,
                    sequence,
                    NOW,
                    CORE_EVENT_SCHEMA_VERSION,
                    item,
                )
            )
        observer.finalize(result)

    live = operation_result_view(result)
    with NamiSyncService(ledger, history) as service:
        retained = service.get_history_summary(run_token)

    assert retained.integrity_status == live.integrity
    assert retained.headline == live.headline


def test_interface_views_are_recursive_json_primitives_without_duck_typing() -> None:
    result = operation_result_view(OperationResult(SessionState.COMPLETED))
    views = (
        SessionEventView(
            session_id="session",
            sequence=1,
            at=NOW.isoformat(),
            schema_version=CORE_EVENT_SCHEMA_VERSION,
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
            verification_state="verified",
            verification_invalidated_at=None,
            verification_invalidated_reason=None,
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
        ResultClassificationView(
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


@pytest.mark.parametrize(
    "subscribe_error",
    (SessionNotFound("raced"), SessionCleanupPending("cleanup pending")),
)
def test_finish_between_get_and_subscribe_returns_terminal_record(
    subscribe_error: Exception,
) -> None:
    class Dispatcher:
        def __init__(self) -> None:
            self.get_count = 0

        def get(self, session_id: str) -> SessionRecord:
            self.get_count += 1
            return _record(session_id, terminal=self.get_count > 1)

        def subscribe(self, session_id: str, from_seq=None):
            raise subscribe_error

    observer = SessionObserver(Dispatcher())

    current = observer.observe("raced", lambda _update: None)

    assert current.result is not None
    observer.close()


def test_release_closes_stream_and_waits_for_worker_without_poll_timeout() -> None:
    stream = _BlockingStream("live")

    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            return stream

    observer = SessionObserver(Dispatcher())
    observer.observe("live", lambda _update: None)
    assert stream.entered.wait(0.5)
    subscription = observer._subscriptions["live"]

    observer.release("live")
    observer.release("live")

    assert stream.closed
    assert stream.next_arguments == [()]
    assert subscription.done.is_set()
    assert subscription.thread is not None
    assert not subscription.thread.is_alive()
    assert observer._subscriptions == {}
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
    session_id = "6" * 32
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
    subscription = observer._subscriptions[session_id]

    with pytest.raises(TimeoutError) as raised:
        observer.close()
    assert str(raised.value) == "session observers did not stop"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert observer._subscriptions[session_id] is subscription

    release_sink.set()
    assert subscription.done.wait(0.5)
    observer.close()
    observer.close()
    assert observer._subscriptions == {}


@pytest.mark.parametrize("cleanup", ("close", "release"))
@pytest.mark.parametrize(
    ("exception_base", "expected_type", "expected_message"),
    (
        (Exception, RuntimeError, "session observer cleanup failed"),
        (TimeoutError, TimeoutError, "session observers did not stop"),
        (
            KeyboardInterrupt,
            KeyboardInterrupt,
            "session observer cleanup was interrupted",
        ),
        (
            SystemExit,
            KeyboardInterrupt,
            "session observer cleanup was interrupted",
        ),
        (
            GeneratorExit,
            KeyboardInterrupt,
            "session observer cleanup was interrupted",
        ),
    ),
    ids=(
        "ordinary",
        "timeout",
        "keyboard-interrupt",
        "system-exit",
        "generator-exit",
    ),
)
def test_observer_direct_join_failure_retires_private_graph_and_stopped_stream(
    cleanup: str,
    exception_base: type[BaseException],
    expected_type: type[BaseException],
    expected_message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "6" * 32
    graph_references: list[object] = []
    pending_streams = [_BlockingStream("join-failure")]

    class Dispatcher:
        def get(self, requested: str) -> SessionRecord:
            return _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            del requested, from_seq
            return pending_streams.pop()

    observer = SessionObserver(Dispatcher())
    observer.observe(session_id, lambda _update: None)
    subscription = observer._subscriptions[session_id]
    stream_reference = ref(subscription.stream)
    assert subscription.stream.entered.wait(0.5)
    original_join = observer._join_threads
    join_attempts = 0

    def fail_first_join(observations) -> None:
        nonlocal join_attempts
        join_attempts += 1
        original_join(observations)
        if join_attempts == 1:
            _raise_private_observer_failure(
                graph_references,
                exception_base=exception_base,
                hostile_text=True,
            )

    monkeypatch.setattr(observer, "_join_threads", fail_first_join)

    with pytest.raises(expected_type) as raised:
        if cleanup == "close":
            observer.close()
        else:
            observer.release(session_id)

    assert str(raised.value) == expected_message
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert observer._subscriptions == {}
    del subscription
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert stream_reference() is None
    if cleanup == "release":
        observer.release(session_id)
        assert join_attempts == 1
    observer.close()


def test_observer_join_failure_retires_stopped_and_retains_only_live_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stopped_id = "6" * 32
    live_id = "7" * 32
    stopped_stream = _BlockingStream("stopped")
    live_stream = _SequenceStream(
        _envelope(live_id, 1, PhaseChanged("blocked"))
    )
    pending_streams = {
        stopped_id: stopped_stream,
        live_id: live_stream,
    }
    live_sink_entered = Event()
    release_live_sink = Event()
    graph_references: list[object] = []

    class Dispatcher:
        def get(self, requested: str) -> SessionRecord:
            return _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            del from_seq
            return pending_streams.pop(requested)

    def live_sink(_update) -> None:
        live_sink_entered.set()
        assert release_live_sink.wait(2)

    observer = SessionObserver(Dispatcher())
    observer.observe(stopped_id, lambda _update: None)
    observer.observe(live_id, live_sink)
    assert stopped_stream.entered.wait(0.5)
    assert live_sink_entered.wait(0.5)
    stopped_reference = ref(stopped_stream)
    del stopped_stream
    original_join = observer._join_threads
    join_attempts = 0

    def fail_first_join(observations) -> None:
        nonlocal join_attempts
        join_attempts += 1
        if join_attempts == 1:
            for candidate in observations:
                if candidate.session_id == stopped_id:
                    assert candidate.thread is not None
                    candidate.thread.join(0.5)
                    assert not candidate.thread.is_alive()
            del candidate
            _raise_private_observer_failure(
                graph_references,
                exception_base=Exception,
                hostile_text=True,
            )
        original_join(observations)

    monkeypatch.setattr(observer, "_join_threads", fail_first_join)

    with pytest.raises(RuntimeError) as raised:
        observer.close()

    assert str(raised.value) == "session observer cleanup failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert tuple(observer._subscriptions) == (live_id,)
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert stopped_reference() is None

    release_live_sink.set()
    observer.close()
    assert observer._subscriptions == {}


def test_gap_recovery_resubscribes_from_first_undelivered_sequence() -> None:
    session_id = "7" * 32
    terminal_result = OperationResult(SessionState.COMPLETED)
    first = _SequenceStream(
        _envelope(session_id, 1, PhaseChanged("one")),
        _envelope(session_id, 3, Gap(first_missed_seq=2)),
    )
    second = _SequenceStream(
        _envelope(session_id, 2, PhaseChanged("two")),
        _envelope(
            session_id,
            4,
            Terminal(TerminalSummary.from_result(terminal_result)),
        ),
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


def test_gap_recovery_releases_retired_streams_while_observation_is_live() -> None:
    session_id = "7" * 32
    current = _BlockingStream("current")
    retired_refs = []
    retired_closed = []

    class RetiredStream(_SequenceStream):
        def __init__(self, index: int) -> None:
            super().__init__(
                _envelope(session_id, index + 1, Gap(first_missed_seq=index + 1))
            )
            self.index = index

        def close(self) -> None:
            if not self.closed:
                retired_closed.append(self.index)
            super().close()

    class Dispatcher:
        def get(self, requested: str) -> SessionRecord:
            return _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            if len(retired_refs) == 32:
                return current
            stream = RetiredStream(len(retired_refs))
            retired_refs.append(ref(stream))
            return stream

    observer = SessionObserver(Dispatcher())
    observer.observe(session_id, lambda _update: None)
    try:
        assert current.entered.wait(0.5)
        assert retired_closed == list(range(32))
        assert all(reference() is None for reference in retired_refs)
        assert observer._subscriptions[session_id].stream is current
        assert not current.closed
    finally:
        observer.close()


@pytest.mark.parametrize("stop_method", ("release", "close"))
@pytest.mark.parametrize("blocked_stage", ("subscribe", "retire"))
def test_gap_recovery_stop_closes_racing_replacement_outside_observer_lock(
    stop_method: str,
    blocked_stage: str,
) -> None:
    session_id = "7" * 32
    subscribed = Event()
    first_closed = Event()
    replacement_closed = Event()
    release = Event()
    stopped = Event()
    close_outside_lock = []
    close_errors = []
    subscribe_count = 0

    class FirstStream(_SequenceStream):
        def close(self) -> None:
            if self.closed:
                return
            super().close()
            first_closed.set()
            if blocked_stage == "retire":
                assert release.wait(2)

    class ReplacementStream(_BlockingStream):
        def close(self) -> None:
            if self.closed:
                return
            acquired = observer._lock.acquire(timeout=0.5)
            close_outside_lock.append(acquired)
            if acquired:
                observer._lock.release()
            super().close()
            replacement_closed.set()

    first = FirstStream()
    replacement = ReplacementStream("replacement")

    class Dispatcher:
        def get(self, requested: str) -> SessionRecord:
            return _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            nonlocal subscribe_count
            subscribe_count += 1
            if subscribe_count == 1:
                return first
            assert subscribe_count == 2
            subscribed.set()
            if blocked_stage == "subscribe":
                assert release.wait(2)
            return replacement

    observer = SessionObserver(Dispatcher())

    def stop() -> None:
        try:
            if stop_method == "release":
                observer.release(session_id)
            else:
                observer.close()
        except Exception as error:
            close_errors.append(error)
        finally:
            stopped.set()

    closer = Thread(target=stop)
    observer.observe(session_id, lambda _update: None)
    subscription = observer._subscriptions[session_id]
    try:
        assert subscribed.wait(0.5)
        if blocked_stage == "retire":
            assert first_closed.wait(0.5)
            assert subscription.stream is replacement
        closer.start()
        assert first_closed.wait(0.5)
        if blocked_stage == "retire":
            assert replacement_closed.wait(0.5)
        assert not stopped.is_set()
    finally:
        release.set()
        if closer.ident is not None:
            closer.join(2)
        observer.close()

    assert stopped.is_set()
    assert close_errors == []
    assert first.closed and replacement.closed
    assert close_outside_lock == [True]
    assert subscription.done.is_set()
    assert not subscription.failed
    assert observer._subscriptions == {}


def test_sink_exception_closes_stream_and_does_not_block_shutdown() -> None:
    session_id = "8" * 32
    stream = _SequenceStream(_envelope(session_id, 1, PhaseChanged("explode")))
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

    observer.observe(session_id, explode)
    assert closed.wait(0.5)
    with pytest.raises(RuntimeError, match="session observation failed") as raised:
        observer.wait(session_id)
    assert str(raised.value) == "session observation failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    observer.close()


@pytest.mark.parametrize("cleanup", ("release", "close"))
@pytest.mark.parametrize(
    "exception_base",
    (Exception, BaseException),
    ids=("exception", "base-exception"),
)
def test_observer_failure_retires_private_graph_before_wait_and_cleanup(
    cleanup: str,
    exception_base: type[BaseException],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "8" * 32
    stream = _SequenceStream(_envelope(session_id, 1, PhaseChanged("explode")))
    graph_references: list[object] = []
    excepthook_calls = []
    monkeypatch.setattr(threading, "excepthook", excepthook_calls.append)

    class Dispatcher:
        def get(self, requested: str) -> SessionRecord:
            return _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            return stream

    def explode(_update) -> None:
        _raise_private_observer_failure(
            graph_references,
            exception_base=exception_base,
        )

    observer = SessionObserver(Dispatcher())
    observer.observe(session_id, explode)
    subscription = observer._subscriptions[session_id]
    assert subscription.done.wait(0.5)
    assert subscription.thread is not None
    subscription.thread.join(0.5)
    assert not subscription.thread.is_alive()
    assert subscription.failed
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert excepthook_calls == []

    failures = []
    for _ in range(2):
        with pytest.raises(RuntimeError) as raised:
            observer.wait(session_id)
        failures.append(raised.value)
    assert failures[0] is not failures[1]
    assert all(str(error) == "session observation failed" for error in failures)
    assert all(error.__cause__ is None for error in failures)
    assert all(error.__context__ is None for error in failures)

    if cleanup == "release":
        observer.release(session_id)
    else:
        observer.close()
    assert observer._subscriptions == {}
    observer.close()


def test_observer_stream_close_base_exception_is_contained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "8" * 32
    graph_references: list[object] = []
    excepthook_calls = []
    monkeypatch.setattr(threading, "excepthook", excepthook_calls.append)

    class Stream(_SequenceStream):
        def __init__(self) -> None:
            super().__init__(_envelope(session_id, 1, PhaseChanged("closing")))
            self.close_attempts = 0

        def close(self) -> None:
            self.close_attempts += 1
            if self.close_attempts == 1:
                _raise_private_observer_failure(
                    graph_references,
                    exception_base=BaseException,
                )
            super().close()

    stream = Stream()

    class Dispatcher:
        def __init__(self) -> None:
            self.get_count = 0

        def get(self, requested: str) -> SessionRecord:
            self.get_count += 1
            return _record(requested, terminal=self.get_count > 1)

        def subscribe(self, requested: str, from_seq=None):
            return stream

    observer = SessionObserver(Dispatcher())
    observer.observe(session_id, lambda _update: None)
    subscription = observer._subscriptions[session_id]
    assert subscription.done.wait(0.5)
    assert subscription.thread is not None
    subscription.thread.join(0.5)
    assert not subscription.thread.is_alive()
    assert subscription.failed
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert excepthook_calls == []

    with pytest.raises(RuntimeError) as raised:
        observer.wait(session_id)
    assert str(raised.value) == "session observation failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    observer.close()
    assert stream.closed
    assert stream.close_attempts == 2


def test_observer_close_continues_after_private_base_exception_and_retires_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph_references: list[object] = []
    excepthook_calls = []
    monkeypatch.setattr(threading, "excepthook", excepthook_calls.append)

    class FirstStream(_BlockingStream):
        def close(self) -> None:
            if self.closed:
                return
            super().close()
            _raise_private_observer_failure(
                graph_references,
                exception_base=BaseException,
            )

    streams = {
        "first": FirstStream("first"),
        "second": _BlockingStream("second"),
    }

    class Dispatcher:
        def get(self, requested: str) -> SessionRecord:
            return _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            return streams[requested]

    observer = SessionObserver(Dispatcher())
    for session_id in streams:
        observer.observe(session_id, lambda _update: None)
    assert all(stream.entered.wait(0.5) for stream in streams.values())
    subscriptions = tuple(observer._subscriptions.values())

    with pytest.raises(RuntimeError) as raised:
        observer.close()

    assert str(raised.value) == "session observer cleanup failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert all(stream.closed for stream in streams.values())
    assert all(
        subscription.thread is not None and not subscription.thread.is_alive()
        for subscription in subscriptions
    )
    assert observer._subscriptions == {}
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert excepthook_calls == []
    observer.close()


def test_observer_close_failure_traceback_does_not_own_retired_subscriptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "8" * 32
    graph_references: list[object] = []
    retired_references: list[object] = []
    excepthook_calls = []
    monkeypatch.setattr(threading, "excepthook", excepthook_calls.append)

    class Stream(_BlockingStream):
        def close(self) -> None:
            if self.closed:
                return
            super().close()
            _raise_private_observer_failure(
                graph_references,
                exception_base=BaseException,
                hostile_text=True,
            )

    stream = Stream("retired")

    class Dispatcher:
        def get(self, requested: str) -> SessionRecord:
            return _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            del requested, from_seq
            return stream

    observer = SessionObserver(Dispatcher())
    observer.observe(session_id, lambda _update: None)
    assert stream.entered.wait(0.5)
    retired_references.append(ref(stream))
    del stream

    with pytest.raises(RuntimeError) as raised:
        observer.close()

    assert str(raised.value) == "session observer cleanup failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert all(reference() is None for reference in retired_references)
    assert observer._subscriptions == {}
    assert excepthook_calls == []
    observer.close()


@pytest.mark.parametrize("admission", ("observe", "adopt"))
def test_observer_single_cleanup_retires_after_private_close_base_exception(
    admission: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "8" * 32
    graph_references: list[object] = []
    excepthook_calls = []
    monkeypatch.setattr(threading, "excepthook", excepthook_calls.append)

    class Stream(_BlockingStream):
        def close(self) -> None:
            if self.closed:
                return
            super().close()
            _raise_private_observer_failure(
                graph_references,
                exception_base=BaseException,
            )

    stream = Stream(admission)

    class Dispatcher:
        def get(self, requested: str) -> SessionRecord:
            return _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            return stream

    observer = SessionObserver(Dispatcher())
    if admission == "observe":
        observer.observe(session_id, lambda _update: None)
    else:
        assert observer.adopt(session_id, lambda _update: None, stream) is None
    assert stream.entered.wait(0.5)
    subscription = observer._subscriptions[session_id]

    with pytest.raises(RuntimeError) as raised:
        observer.release(session_id)

    assert str(raised.value) == "session observer cleanup failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert stream.closed
    assert subscription.thread is not None
    assert not subscription.thread.is_alive()
    assert observer._subscriptions == {}
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert excepthook_calls == []
    observer.close()


def test_callback_self_release_retires_atomically_without_self_join() -> None:
    session_id = "9" * 32
    stream = _SequenceStream(
        _envelope(session_id, 1, PhaseChanged("inventory"))
    )

    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            return stream

    observer = SessionObserver(Dispatcher())
    callback_entered = Event()
    allow_release = Event()
    self_release_returned = Event()
    allow_callback_return = Event()
    external_release_started = Event()
    external_release_returned = Event()
    returned = Event()
    retained_after_release: list[bool] = []

    def receive(_update) -> None:
        callback_entered.set()
        assert allow_release.wait(2)
        observer.release(session_id)
        retained_after_release.append(session_id in observer._subscriptions)
        self_release_returned.set()
        assert allow_callback_return.wait(2)
        returned.set()

    observer.observe(session_id, receive)
    assert callback_entered.wait(0.5)
    subscription = observer._subscriptions[session_id]
    allow_release.set()

    assert self_release_returned.wait(0.5)
    external_release = Thread(
        target=lambda: (
            external_release_started.set(),
            observer.release(session_id),
            external_release_returned.set(),
        )
    )
    external_release.start()
    assert external_release_started.wait(0.5)
    assert not external_release_returned.wait(0.05)
    allow_callback_return.set()
    assert returned.wait(0.5)
    external_release.join(0.5)
    assert not external_release.is_alive()
    assert external_release_returned.is_set()
    assert stream.closed
    assert retained_after_release == [False]
    assert subscription.done.wait(0.5)
    assert subscription.thread is not None
    subscription.thread.join(0.5)
    assert not subscription.thread.is_alive()
    observer.close()


def test_terminal_callback_self_release_preserves_terminal_record_pair() -> None:
    session_id = f"{90_001:032x}"
    terminal = OperationResult(SessionState.COMPLETED)
    stream = _SequenceStream(
        _envelope(
            session_id,
            1,
            Terminal(TerminalSummary.from_result(terminal)),
        )
    )

    class Dispatcher:
        def __init__(self) -> None:
            self.get_count = 0

        def get(self, requested: str) -> SessionRecord:
            self.get_count += 1
            return _record(requested, terminal=self.get_count > 1)

        def subscribe(self, requested: str, from_seq=None):
            del requested, from_seq
            return stream

    observer = SessionObserver(Dispatcher())
    updates: list[SessionEventView | SessionRecordView] = []
    complete = Event()

    def receive(update: SessionEventView | SessionRecordView) -> None:
        updates.append(update)
        if type(update) is SessionEventView:
            observer.release(session_id)
        else:
            complete.set()

    observer.observe(session_id, receive)

    assert complete.wait(0.5)
    assert [type(update) for update in updates] == [
        SessionEventView,
        SessionRecordView,
    ]
    assert updates[0].body_type == "Terminal"
    assert updates[1].result is not None
    observer.close()


def test_adopt_rejection_closes_offer_and_returns_no_rollback_capability() -> None:
    accepted_stream = _BlockingStream("accepted")
    rejected_stream = _BlockingStream("rejected")
    invalid_stream = _BlockingStream("invalid")

    observer = SessionObserver(SimpleNamespace())

    result = observer.adopt(
        "same-session",
        lambda _update: None,
        accepted_stream,
    )
    assert result is None
    assert accepted_stream.entered.wait(0.5)

    with pytest.raises(ValueError, match="already observed"):
        observer.adopt(
            "same-session",
            lambda _update: None,
            rejected_stream,
        )

    assert rejected_stream.closed
    assert not rejected_stream.entered.is_set()
    with pytest.raises(TypeError, match="callable"):
        observer.adopt("invalid", object(), invalid_stream)
    assert invalid_stream.closed
    assert not invalid_stream.entered.is_set()
    observer.release("same-session")
    observer.close()


def test_stale_subscription_release_cannot_remove_replacement() -> None:
    first_stream = _BlockingStream("first-generation")
    second_stream = _BlockingStream("second-generation")

    class Dispatcher:
        pass

    observer = SessionObserver(Dispatcher())
    assert observer.adopt(
        "same-session",
        lambda _update: None,
        first_stream,
    ) is None
    assert first_stream.entered.wait(0.5)
    retired = observer._subscriptions["same-session"]
    observer.release("same-session")

    assert observer.adopt(
        "same-session",
        lambda _update: None,
        second_stream,
    ) is None
    assert second_stream.entered.wait(0.5)
    replacement = observer._subscriptions["same-session"]

    observer._release_subscription(retired)

    assert observer._subscriptions["same-session"] is replacement
    assert not second_stream.closed
    observer.release("same-session")
    assert observer._subscriptions == {}
    observer.close()


def test_reobserve_replaces_stream_from_exact_positive_sequence() -> None:
    first_stream = _BlockingStream("initial")
    replacement_stream = _BlockingStream("replacement")
    retired_subscriptions = []

    class Dispatcher:
        def __init__(self) -> None:
            self.subscribe_calls: list[int | None] = []

        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            del session_id
            self.subscribe_calls.append(from_seq)
            if len(self.subscribe_calls) == 1:
                return first_stream
            retired = retired_subscriptions[0]
            assert retired.done.is_set()
            assert retired.thread is not None
            assert not retired.thread.is_alive()
            return replacement_stream

    dispatcher = Dispatcher()
    observer = SessionObserver(dispatcher)
    observer.observe("recovering", lambda _update: None)
    assert first_stream.entered.wait(0.5)
    retired_subscriptions.append(observer._subscriptions["recovering"])

    current = observer.reobserve(
        "recovering",
        lambda _update: None,
        7,
    )

    assert current.result is None
    assert dispatcher.subscribe_calls == [None, 7]
    assert first_stream.closed
    assert replacement_stream.entered.wait(0.5)
    observer.close()


@pytest.mark.parametrize("from_sequence", (0, -1, True, 1.5, "1"))
def test_reobserve_rejects_nonpositive_or_noninteger_sequence(
    from_sequence: object,
) -> None:
    observer = SessionObserver(SimpleNamespace())

    with pytest.raises(ValueError, match="positive integer"):
        observer.reobserve(
            "invalid-sequence",
            lambda _update: None,
            from_sequence,
        )

    observer.close()


def test_invalid_reobserve_preserves_existing_observation() -> None:
    stream = _BlockingStream("retained")

    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            del session_id, from_seq
            return stream

    observer = SessionObserver(Dispatcher())
    observer.observe("retained", lambda _update: None)
    assert stream.entered.wait(0.5)
    retained = observer._subscriptions["retained"]

    with pytest.raises(ValueError, match="positive integer"):
        observer.reobserve("retained", lambda _update: None, 0)

    assert observer._subscriptions["retained"] is retained
    assert not stream.closed

    with pytest.raises(TypeError, match="callable"):
        observer.reobserve("retained", object(), 1)

    assert observer._subscriptions["retained"] is retained
    assert not stream.closed
    observer.close()


def test_reobserve_terminal_session_installs_no_stream() -> None:
    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id, terminal=True)

        def subscribe(self, session_id: str, from_seq=None):
            raise AssertionError("terminal reobserve must not subscribe")

    observer = SessionObserver(Dispatcher())

    current = observer.reobserve(
        "already-terminal",
        lambda _update: None,
        3,
    )

    assert current.result is not None
    assert observer._subscriptions == {}
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
    service._lifecycle = TaskLifecycle()
    service._plan_selections = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False

    first = service.close()
    second = service.close()

    assert log == ["observer", "dispatcher", "runtime"]
    assert first is second
    assert first.complete


def test_production_timeouts_order_writer_audit_and_shutdown() -> None:
    # History finalization retries for strictly less than the generic writer
    # bound, because every audit and shutdown bound scales from it and the
    # worst-case window close must stay responsive.
    assert 0 < HISTORY_WRITER_RETRY_TIMEOUT_SECONDS < DEFAULT_RETRY_TIMEOUT_SECONDS
    assert service_module.FINALIZATION_TIMEOUT_MARGIN_SECONDS > 0
    assert service_module.AUDIT_FINALIZATION_TIMEOUT_SECONDS == (
        HISTORY_WRITER_RETRY_TIMEOUT_SECONDS
        + service_module.FINALIZATION_TIMEOUT_MARGIN_SECONDS
    )
    assert service_module.SERVICE_CLOSE_TIMEOUT_SECONDS == (
        service_module.AUDIT_FINALIZATION_TIMEOUT_SECONDS
        + HISTORY_WRITER_RETRY_TIMEOUT_SECONDS
        + service_module.FINALIZATION_TIMEOUT_MARGIN_SECONDS
    )
    assert service_module.SERVICE_CLOSE_TIMEOUT_SECONDS <= 15.0


def test_audit_offer_backpressure_is_independent_of_finalization() -> None:
    # A wedged audit writer must degrade quickly rather than stall the emitting
    # workflow thread, so producer backpressure must never scale with the
    # finalization cutoff derived from the history writer's retry bound.
    assert service_module.AUDIT_OFFER_TIMEOUT_SECONDS > 0
    assert service_module.AUDIT_OFFER_TIMEOUT_SECONDS <= (
        HISTORY_WRITER_RETRY_TIMEOUT_SECONDS
    )
    assert service_module.AUDIT_OFFER_TIMEOUT_SECONDS < (
        service_module.AUDIT_FINALIZATION_TIMEOUT_SECONDS
    )


def test_service_composition_passes_derived_audit_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def dispatcher(registry, **kwargs):
        captured["registry"] = registry
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(service_module, "Dispatcher", dispatcher)
    runtime = Mock()
    runtime.history_window_policy.max_age_seconds = 0.75

    service_module._dispatcher(runtime)

    assert captured["audit_timeout"] == (
        service_module.AUDIT_FINALIZATION_TIMEOUT_SECONDS
    )
    assert captured["audit_offer_timeout"] == (
        service_module.AUDIT_OFFER_TIMEOUT_SECONDS
    )
    assert captured["audit_flush_interval"] == 0.75
    assert captured["clock"] is runtime.clock
    assert captured["audit_observer_factory"] is runtime.audit_observer


def test_service_default_close_uses_ordered_shutdown_timeout() -> None:
    observed: list[float] = []

    class Observer:
        def close(self) -> None:
            pass

    class Dispatcher:
        def shutdown(self, timeout: float):
            observed.append(timeout)
            return SimpleNamespace(
                complete=True,
                unfinished=(),
                custody_released=True,
            )

    class Runtime:
        def close(self) -> None:
            pass

    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = Dispatcher()
    service._runtime = Runtime()
    service._lock = Lock()
    service._close_lock = Lock()
    service._lifecycle = TaskLifecycle()
    service._plan_selections = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False
    service._observer_closed = False

    assert service.close().complete
    assert observed == [service_module.SERVICE_CLOSE_TIMEOUT_SECONDS]


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
        def __init__(self) -> None:
            self.inventory = {"request": object()}

        def close(self) -> None:
            log.append("runtime")
            self.inventory.clear()

    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = Dispatcher()
    service._runtime = Runtime()
    service._lock = Lock()
    service._lifecycle = TaskLifecycle()
    service._plan_selections = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False

    incomplete = service.close(timeout=0)
    assert not incomplete.complete
    assert log == ["observer", "dispatcher"]
    assert tuple(service._runtime.inventory) == ("request",)
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
    assert service._runtime.inventory == {}


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
    service._lifecycle = TaskLifecycle()
    service._plan_selections = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False
    service._observer_closed = False

    with pytest.raises(RuntimeError) as raised:
        service.close()
    assert str(raised.value) == "service observer cleanup failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    completed = service.close()
    cached = service.close()

    assert completed.complete
    assert cached is completed
    assert log == ["observer", "dispatcher", "runtime", "observer"]


@pytest.mark.parametrize(
    ("exception_base", "expected_type", "expected_message"),
    (
        (Exception, RuntimeError, "service observer cleanup failed"),
        (
            KeyboardInterrupt,
            KeyboardInterrupt,
            "service observer cleanup was interrupted",
        ),
        (
            SystemExit,
            KeyboardInterrupt,
            "service observer cleanup was interrupted",
        ),
        (
            GeneratorExit,
            KeyboardInterrupt,
            "service observer cleanup was interrupted",
        ),
    ),
    ids=("exception", "keyboard-interrupt", "system-exit", "generator-exit"),
)
def test_service_close_retires_private_observer_failure_before_dependency_close(
    exception_base: type[BaseException],
    expected_type: type[BaseException],
    expected_message: str,
) -> None:
    log: list[str] = []
    graph_references: list[object] = []
    observer_attempts = 0

    class Observer:
        def close(self) -> None:
            nonlocal observer_attempts
            observer_attempts += 1
            log.append("observer")
            if observer_attempts == 1:
                _raise_private_observer_failure(
                    graph_references,
                    exception_base=exception_base,
                    hostile_text=True,
                )

    class Dispatcher:
        def shutdown(self, timeout: float):
            del timeout
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
    service._lifecycle = TaskLifecycle()
    service._plan_selections = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False
    service._observer_closed = False

    with pytest.raises(expected_type) as raised:
        service.close()

    assert str(raised.value) == expected_message
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert log == ["observer", "dispatcher", "runtime"]
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)

    completed = service.close()
    assert completed.complete
    assert service.close() is completed
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
    service._lifecycle = TaskLifecycle()
    service._plan_selections = {}
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
    service._lifecycle = TaskLifecycle()
    service._plan_selections = {}
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

    class Details:
        pass

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
    runtime._ledger_reader_lock = Lock()
    runtime._history_reader_lock = Lock()
    runtime._ledger_reader = None
    runtime._history_reader = None
    runtime._closing = False
    runtime._closed = False
    runtime._history_store = store
    plan = Details()
    execution_details = Details()
    inventory_details = Details()
    plan_ref = ref(plan)
    execution_ref = ref(execution_details)
    inventory_ref = ref(inventory_details)
    runtime._plans = {"request": plan}
    runtime._execution_details = {"run": execution_details}
    runtime._inventory_details = {"request": inventory_details}
    runtime._execution_started = {"run": NOW}
    del plan, execution_details, inventory_details

    with pytest.raises(RuntimeError, match="writer close failed"):
        runtime.close()
    assert not runtime._closed
    assert runtime._history_store is store
    assert tuple(runtime._plans) == ("request",)
    assert tuple(runtime._execution_details) == ("run",)
    assert tuple(runtime._inventory_details) == ("request",)
    assert runtime._execution_started == {"run": NOW}
    assert plan_ref() is not None
    assert execution_ref() is not None
    assert inventory_ref() is not None

    runtime.close()
    assert runtime._closed
    assert runtime._history_store is None
    assert runtime._plans == {}
    assert runtime._execution_details == {}
    assert runtime._inventory_details == {}
    assert runtime._execution_started == {}
    assert plan_ref() is None
    assert execution_ref() is None
    assert inventory_ref() is None
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
    runtime._ledger_reader_lock = Lock()
    runtime._history_reader_lock = Lock()
    runtime._ledger_reader = None
    runtime._history_reader = None
    runtime._closing = False
    runtime._closed = False
    runtime._history_store = store
    runtime._plans = {}
    runtime._execution_details = {}
    runtime._inventory_details = {}
    runtime._execution_started = {}
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


def test_runtime_detail_drops_release_complete_diagnostic_graphs(
    tmp_path: Path,
) -> None:
    class WeakResolution(VolumeResolution):
        __slots__ = ("__weakref__",)

    class WeakInventoryDetails(InventoryDetails):
        __slots__ = ("__weakref__",)

    class WeakScanWarning(ScanWarning):
        __slots__ = ("__weakref__",)

    class WeakRefusal(RefusalView):
        __slots__ = ("__weakref__",)

    class WeakExecutionDetails(ExecutionDetails):
        __slots__ = ("__weakref__",)

    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    binding = LocationBinding(
        VolumeId("serial", "NTFS"),
        "library",
        "F:\\",
        ("F:\\",),
        False,
        7,
    )
    resolution = WeakResolution(VolumeResolutionState.OFFLINE, binding)
    warning = WeakScanWarning(
        ScanWarningCode.ACCESS_DENIED,
        "private.bin",
        "denied",
    )
    inventory = WeakInventoryDetails(
        "inventory-request",
        resolution,
        selected_paths=("private.bin",),
        warnings=(warning,),
    )
    refusal = WeakRefusal("unsafe", "target.bin", "changed")
    execution = WeakExecutionDetails("execution-run", (refusal,))
    resolution_ref = ref(resolution)
    warning_ref = ref(warning)
    inventory_ref = ref(inventory)
    refusal_ref = ref(refusal)
    execution_ref = ref(execution)
    runtime._save_inventory_details(inventory)
    runtime._save_execution_details(execution)
    del resolution, warning, inventory, refusal, execution

    assert all(
        reference() is not None
        for reference in (
            resolution_ref,
            warning_ref,
            inventory_ref,
            refusal_ref,
            execution_ref,
        )
    )

    runtime.drop_inventory_details("inventory-request")
    runtime.drop_execution_details("execution-run")

    assert all(
        reference() is None
        for reference in (
            resolution_ref,
            warning_ref,
            inventory_ref,
            refusal_ref,
            execution_ref,
        )
    )
    runtime.close()


def test_lifecycle_cleanup_sequences_are_fixed_and_owner_idempotent() -> None:
    owned_session = f"{9_001:032x}"
    unrelated_session = f"{9_002:032x}"
    owned_request = f"{9_003:032x}"
    unrelated_request = f"{9_004:032x}"
    inventory_details = object()
    unrelated_details = object()
    calls: list[tuple[str, str]] = []
    transitions: list[tuple[str, str]] = []

    class Observer:
        present = True

        def release(self, session_id: str) -> None:
            calls.append(("observer", session_id))
            if self.present:
                self.present = False
                transitions.append(("observer", session_id))

    class Dispatcher:
        closing = False
        present = True

        def close(self, session_id: str) -> None:
            self.closing = True
            calls.append(("dispatcher", session_id))
            self.closing = False
            if self.present:
                self.present = False
                transitions.append(("dispatcher", session_id))

    dispatcher = Dispatcher()

    class Runtime:
        inventory = {
            owned_request: inventory_details,
            unrelated_request: unrelated_details,
        }

        def get_inventory_details(self, request_id: str):
            return self.inventory[request_id]

        def drop_inventory_details(self, request_id: str) -> None:
            assert not dispatcher.closing
            assert service._lock.acquire(blocking=False)
            service._lock.release()
            calls.append(("detail", request_id))
            if self.inventory.pop(request_id, None) is not None:
                transitions.append(("detail", request_id))
                raise RuntimeError("detail owner interrupted after effect")

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()
    service._dispatcher = dispatcher
    service._observer = Observer()
    service._lock = Lock()
    service._lifecycle = TaskLifecycle()
    _publish_session(
        service._lifecycle,
        owned_session,
        kind="inventory",
        detail_owner=("inventory", owned_request),
        request_id=owned_request,
    )
    unrelated = _publish_session(
        service._lifecycle,
        unrelated_session,
        kind="inventory",
        detail_owner=("inventory", unrelated_request),
        request_id=unrelated_request,
    )

    assert service._runtime.get_inventory_details(owned_request) is inventory_details
    with pytest.raises(RuntimeError, match="interrupted after effect"):
        service.close_session(owned_session)
    service.close_session(owned_session)

    expected = [
        ("observer", owned_session),
        ("dispatcher", owned_session),
        ("detail", owned_request),
    ]
    assert calls == [*expected, *expected]
    assert transitions == expected
    assert service._runtime.inventory == {
        unrelated_request: unrelated_details,
    }
    with pytest.raises(LifecycleAssociationError):
        service._lifecycle.require_session(owned_session, live=False)
    assert service._lifecycle.require_session(
        unrelated_session,
        live=False,
    ) == unrelated


def test_cleanup_retry_uses_current_owner_truth_not_application_progress() -> None:
    session_id = f"{9_101:032x}"
    run_id = f"{9_102:032x}"
    close_calls = 0
    close_transitions = 0

    class Observer:
        def release(self, session_id: str) -> None:
            pass

    class Dispatcher:
        def close(self, session_id: str) -> None:
            nonlocal close_calls, close_transitions
            close_calls += 1
            if close_calls == 1:
                close_transitions += 1
                raise TimeoutError(
                    "session worker retired before acknowledgement"
                )
            raise SessionNotFound(session_id)

    class Runtime:
        def __init__(self) -> None:
            self.execution = {run_id: object()}

        def drop_execution_details(self, run_id: str) -> None:
            self.execution.pop(run_id, None)

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()
    service._dispatcher = Dispatcher()
    service._observer = Observer()
    service._lock = Lock()
    service._lifecycle = TaskLifecycle()
    _publish_session(
        service._lifecycle,
        session_id,
        kind="execution",
        detail_owner=("execution", run_id),
        request_id=run_id,
    )

    with pytest.raises(TimeoutError, match="before acknowledgement"):
        service.close_session(session_id)
    assert tuple(service._runtime.execution) == (run_id,)
    service._lifecycle.require_session(session_id, live=False)

    service.close_session(session_id)

    assert close_calls == 2
    assert close_transitions == 1
    assert service._runtime.execution == {}
    with pytest.raises(LifecycleAssociationError):
        service._lifecycle.require_session(session_id, live=False)


def test_blocked_session_retirement_keeps_details_until_close_returns() -> None:
    session_id = f"{9_201:032x}"
    request_id = f"{9_202:032x}"
    close_entered = Event()
    release_close = Event()
    close_done = Event()

    class Observer:
        def release(self, session_id: str) -> None:
            pass

    class Dispatcher:
        def close(self, session_id: str) -> None:
            close_entered.set()
            assert release_close.wait(2)

    class Runtime:
        def __init__(self) -> None:
            self.inventory = {request_id: object()}

        def get_inventory_details(self, request_id: str):
            return self.inventory[request_id]

        def drop_inventory_details(self, request_id: str) -> None:
            self.inventory.pop(request_id, None)

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()
    service._dispatcher = Dispatcher()
    service._observer = Observer()
    service._lock = Lock()
    service._lifecycle = TaskLifecycle()
    _publish_session(
        service._lifecycle,
        session_id,
        kind="inventory",
        detail_owner=("inventory", request_id),
        request_id=request_id,
    )

    def close_session() -> None:
        service.close_session(session_id)
        close_done.set()

    closer = Thread(target=close_session)
    closer.start()
    assert close_entered.wait(1)
    assert service._runtime.get_inventory_details(request_id) is not None
    assert not close_done.is_set()
    release_close.set()
    closer.join(2)

    assert not closer.is_alive()
    assert close_done.is_set()
    assert service._runtime.inventory == {}


def test_service_shutdown_preserves_detail_owners_until_runtime_close_succeeds() -> None:
    runtime_close_attempts = 0

    class Observer:
        def close(self) -> None:
            pass

    class Dispatcher:
        def shutdown(self, timeout: float):
            return SimpleNamespace(
                complete=True,
                unfinished=(),
                custody_released=True,
            )

    class Runtime:
        def __init__(self) -> None:
            self.inventory = {"request": object()}

        def close(self) -> None:
            nonlocal runtime_close_attempts
            runtime_close_attempts += 1
            if runtime_close_attempts == 1:
                raise RuntimeError("runtime detail owner still closing")
            self.inventory.clear()

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()
    service._dispatcher = Dispatcher()
    service._observer = Observer()
    service._lock = Lock()
    service._close_lock = Lock()
    service._lifecycle = TaskLifecycle()
    service._plan_selections = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False
    service._observer_closed = False

    with pytest.raises(RuntimeError, match="detail owner still closing"):
        service.close()
    assert tuple(service._runtime.inventory) == ("request",)

    assert service.close().complete
    assert service._runtime.inventory == {}


def _detail_lifecycle_service(runtime, dispatcher) -> NamiSyncService:
    service = object.__new__(NamiSyncService)
    service._runtime = runtime
    service._dispatcher = dispatcher
    service._observer = SimpleNamespace(
        close=lambda: None,
        release=lambda _session_id: None,
    )
    service._lock = Lock()
    service._close_lock = Lock()
    service._lifecycle = TaskLifecycle()
    service._plan_selections = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False
    service._observer_closed = False
    return service


def test_detail_owner_attachment_rolls_back_a_failed_publication() -> None:
    session_id = f"{9_301:032x}"
    drops: list[str] = []

    class Runtime:
        def drop_inventory_details(self, request_id: str) -> None:
            drops.append(request_id)

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            assert service._lock.acquire(blocking=False)
            service._lock.release()
            assert attach is not None
            stream = _SequenceStream()
            rollback = attach(session_id, stream)
            assert stream.closed
            rollback()
            raise RuntimeError("publication failed")

    service = _detail_lifecycle_service(Runtime(), Dispatcher())

    with pytest.raises(RuntimeError, match="publication failed"):
        service.start_inventory(root_path=r"F:\library")

    assert len(drops) == 1
    with pytest.raises(LifecycleAssociationError):
        service._lifecycle.require_session(session_id, live=False)


def test_detail_owner_attachment_rechecks_service_lifecycle() -> None:
    session_id = f"{9_401:032x}"
    command_id = f"{9_402:032x}"
    stream = _SequenceStream()
    request_ids: list[str] = []
    drops: list[str] = []
    unrelated_id = f"{9_403:032x}"
    unrelated_detail = object()
    details = {unrelated_id: unrelated_detail}

    class Runtime:
        def drop_inventory_details(self, request_id: str) -> None:
            assert details.pop(request_id, None) is not None
            drops.append(request_id)

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            assert attach is not None
            request_ids.append(request.request_id)
            details[request.request_id] = object()
            service._lifecycle.close()
            attach(session_id, stream)
            raise AssertionError("closed service attachment returned")

    service = _detail_lifecycle_service(Runtime(), Dispatcher())

    with pytest.raises(RuntimeError, match="service is closed"):
        service.start_inventory(
            root_path=r"F:\library",
            command_id=command_id,
        )

    assert stream.closed
    assert len(request_ids) == 1
    assert drops == request_ids
    assert details == {unrelated_id: unrelated_detail}
    assert service._lifecycle._admissions == {}
    assert service._lifecycle._sessions == {}
    assert service._lifecycle._start_receipts == {}


def test_observed_start_adoption_rejection_retires_exact_liabilities() -> None:
    session_id = f"{9_451:032x}"
    request_id = f"{9_452:032x}"
    command_id = f"{9_453:032x}"
    signature = ("inventory", "observed-rejection")
    unrelated_id = f"{9_454:032x}"
    detail = object()
    unrelated_detail = object()
    details = {request_id: detail, unrelated_id: unrelated_detail}
    stream = _SequenceStream()
    adoption_calls: list[str] = []
    release_calls: list[str] = []
    published = False

    class Runtime:
        def drop_inventory_details(self, candidate: str) -> None:
            details.pop(candidate, None)

    class Observer:
        def adopt(self, candidate: str, sink, offered_stream):
            assert candidate == session_id
            assert callable(sink)
            assert offered_stream is stream
            adoption_calls.append(candidate)
            offered_stream.close()
            raise RuntimeError("observer adoption rejected")

        def release(self, candidate: str) -> None:
            release_calls.append(candidate)

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            nonlocal published
            assert attach is not None
            attach(session_id, stream)
            published = True
            return session_id

    service = _detail_lifecycle_service(Runtime(), Dispatcher())
    service._observer = Observer()

    with pytest.raises(RuntimeError, match="observer adoption rejected"):
        service._submit_session(
            "inventory",
            object(),
            effect_kind="inventory",
            command_id=command_id,
            signature=signature,
            request_id=request_id,
            detail_owner=("inventory", request_id),
            observation_sink=lambda _update: None,
        )

    assert stream.closed
    assert adoption_calls == [session_id]
    assert release_calls == [session_id]
    assert not published
    assert details == {unrelated_id: unrelated_detail}
    assert service._lifecycle.replay_start(
        command_id,
        "inventory",
        signature,
    ) is None
    assert service._lifecycle._admissions == {}
    assert service._lifecycle._sessions == {}
    assert service._lifecycle._start_receipts == {}
    with pytest.raises(LifecycleAssociationError):
        service._lifecycle.require_session(session_id, live=False)


def test_whole_admission_rollback_replays_without_duplicate_effect() -> None:
    session_id = f"{9_501:032x}"
    detail_id = f"{9_502:032x}"
    details = {detail_id: object()}
    transitions: list[str] = []

    class Runtime:
        def drop_inventory_details(self, request_id: str) -> None:
            assert request_id == detail_id
            if details.pop(request_id, None) is not None:
                transitions.append(request_id)

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            assert attach is not None
            rollback = attach(session_id, _SequenceStream())
            rollback()
            rollback()
            raise RuntimeError("publication failed")

    service = _detail_lifecycle_service(Runtime(), Dispatcher())

    with pytest.raises(RuntimeError, match="publication failed"):
        service._submit_session(
            "inventory",
            object(),
            effect_kind="inventory",
            command_id=None,
            signature=(),
            request_id=detail_id,
            detail_owner=("inventory", detail_id),
        )

    assert transitions == [detail_id]
    with pytest.raises(LifecycleAssociationError):
        service._lifecycle.require_session(session_id, live=False)


@pytest.mark.parametrize(
    ("fault_owner", "fault_timing"),
    (
        ("observer", "before"),
        ("observer", "after"),
        ("detail", "before"),
        ("detail", "after"),
    ),
)
def test_ls_4a_admission_rollback_owner_fault_retries_from_observer(
    fault_owner: str,
    fault_timing: str,
) -> None:
    session_id = f"{9_551:032x}"
    detail_id = f"{9_552:032x}"
    unrelated_session = f"{9_553:032x}"
    unrelated_detail_id = f"{9_554:032x}"
    command_id = f"{9_555:032x}"
    signature = ("inventory", fault_owner, fault_timing)
    stream = _SequenceStream()
    unrelated_stream = _SequenceStream()
    unrelated_sink = object()
    unrelated_detail = object()
    details = {
        detail_id: object(),
        unrelated_detail_id: unrelated_detail,
    }
    observations = {
        unrelated_session: (unrelated_sink, unrelated_stream),
    }
    calls: list[tuple[str, str]] = []
    transitions: list[tuple[str, str]] = []
    faulted = False

    def fault(owner: str, timing: str) -> None:
        nonlocal faulted
        if (
            owner == fault_owner
            and timing == fault_timing
            and not faulted
        ):
            faulted = True
            raise RuntimeError(f"{owner} {timing} fault")

    class Runtime:
        def drop_inventory_details(self, candidate: str) -> None:
            calls.append(("detail", candidate))
            fault("detail", "before")
            if details.pop(candidate, None) is not None:
                transitions.append(("detail", candidate))
            fault("detail", "after")

    class Observer:
        def adopt(self, candidate: str, sink, offered_stream):
            observations[candidate] = (sink, offered_stream)
            return None

        def release(self, candidate: str) -> None:
            calls.append(("observer", candidate))
            fault("observer", "before")
            retained = observations.pop(candidate, None)
            if retained is not None:
                retained[1].close()
                transitions.append(("observer", candidate))
            fault("observer", "after")

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            assert attach is not None
            rollback = attach(session_id, stream)
            with pytest.raises(
                RuntimeError,
                match=f"{fault_owner} {fault_timing} fault",
            ):
                rollback()
            rollback()
            raise RuntimeError("publication failed")

    service = _detail_lifecycle_service(Runtime(), Dispatcher())
    service._observer = Observer()

    with pytest.raises(RuntimeError, match="publication failed"):
        service._submit_session(
            "inventory",
            object(),
            effect_kind="inventory",
            command_id=command_id,
            signature=signature,
            request_id=detail_id,
            detail_owner=("inventory", detail_id),
            observation_sink=lambda _update: None,
        )

    assert faulted
    assert calls.count(("observer", session_id)) == 2
    assert calls.count(("detail", detail_id)) == (
        2 if fault_owner == "detail" else 1
    )
    assert transitions == [
        ("observer", session_id),
        ("detail", detail_id),
    ]
    assert observations == {
        unrelated_session: (unrelated_sink, unrelated_stream)
    }
    assert not unrelated_stream.closed
    assert details == {unrelated_detail_id: unrelated_detail}
    assert stream.closed
    assert service._lifecycle.replay_start(
        command_id,
        "inventory",
        signature,
    ) is None
    with pytest.raises(LifecycleAssociationError):
        service._lifecycle.require_session(session_id, live=False)


def test_whole_admission_rollback_singleflights_concurrent_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = f"{9_601:032x}"
    detail_id = f"{9_602:032x}"
    observer_entered = Event()
    peer_waiting = Event()
    release_observer = Event()
    observer_releases = 0
    detail_drops = 0

    class Runtime:
        def drop_inventory_details(self, candidate: str) -> None:
            nonlocal detail_drops
            assert candidate == detail_id
            detail_drops += 1

    class Observer:
        def __init__(self) -> None:
            self.stream = None

        def adopt(self, candidate: str, sink, stream):
            assert candidate == session_id
            assert callable(sink)
            self.stream = stream
            return None

        def release(self, candidate: str) -> None:
            nonlocal observer_releases
            assert candidate == session_id
            observer_releases += 1
            observer_entered.set()
            assert release_observer.wait(2)
            assert self.stream is not None
            self.stream.close()

    observer = Observer()

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            assert attach is not None
            rollback = attach(session_id, _SequenceStream())
            failures: list[BaseException] = []

            def run_rollback() -> None:
                try:
                    rollback()
                except BaseException as error:
                    failures.append(error)

            first = Thread(
                target=run_rollback,
                name="admission-rollback-owner",
            )
            second = Thread(
                target=run_rollback,
                name="admission-rollback-peer",
            )
            first.start()
            assert observer_entered.wait(1)
            second.start()
            assert peer_waiting.wait(1)
            release_observer.set()
            first.join(2)
            second.join(2)
            assert not first.is_alive()
            assert not second.is_alive()
            assert failures == []
            raise RuntimeError("publication failed")

    service = _detail_lifecycle_service(Runtime(), Dispatcher())
    service._observer = observer
    condition_type = type(service._lifecycle._condition)
    original_wait = condition_type.wait

    def observe_wait(condition, timeout=None):
        if (
            condition is service._lifecycle._condition
            and current_thread().name == "admission-rollback-peer"
        ):
            peer_waiting.set()
        return original_wait(condition, timeout)

    monkeypatch.setattr(condition_type, "wait", observe_wait)

    with pytest.raises(RuntimeError, match="publication failed"):
        service._submit_session(
            "inventory",
            object(),
            effect_kind="inventory",
            command_id=None,
            signature=(),
            request_id=detail_id,
            detail_owner=("inventory", detail_id),
            observation_sink=lambda _update: None,
        )

    assert observer_releases == 1
    assert detail_drops == 1
    assert observer.stream is not None and observer.stream.closed


def test_service_execution_opt_in_reaches_runtime_without_changing_default() -> None:
    default_request = f"{10_001:032x}"
    verified_request = f"{10_002:032x}"
    default_run = f"{10_003:032x}"
    verified_run = f"{10_004:032x}"
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
                execution_set=SimpleNamespace(
                    run_id=(
                        default_run
                        if request_id == default_request
                        else verified_run
                    )
                )
            )

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None):
            assert kind == "sync-execution"
            session_id = f"{10_100 + len(calls):032x}"
            assert attach is not None
            attach(session_id, _SequenceStream())
            return session_id

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()
    service._dispatcher = Dispatcher()
    service._observer = SimpleNamespace(release=lambda _session_id: None)
    service._lock = Lock()
    service._plan_selections = {}
    service._lifecycle = TaskLifecycle()
    service._closed = False
    _publish_session(
        service._lifecycle,
        f"{10_201:032x}",
        kind="plan",
        request_id=default_request,
    )
    _publish_session(
        service._lifecycle,
        f"{10_202:032x}",
        kind="plan",
        request_id=verified_request,
    )

    default = service.start_execution(default_request)
    verified = service.start_execution(
        verified_request,
        verify_after_execute=True,
    )

    assert calls == [
        (default_request, False),
        (verified_request, True),
    ]
    assert (default.run_id, default.session_id) == (
        default_run,
        f"{10_101:032x}",
    )
    assert (verified.run_id, verified.session_id) == (
        verified_run,
        f"{10_102:032x}",
    )
    service._lifecycle.require_session(default.session_id)
    service._lifecycle.require_session(verified.session_id)


def test_location_commands_submit_exact_typed_workflow_requests() -> None:
    submitted: list[tuple[str, object]] = []
    session_ids = {
        kind: f"{10_300 + index:032x}"
        for index, kind in enumerate(
            ("inventory", "baseline", "verify", "rebaseline"),
            start=1,
        )
    }

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            submitted.append((kind, request))
            session_id = session_ids[kind]
            assert attach is not None
            attach(session_id, _SequenceStream())
            return session_id

    service = object.__new__(NamiSyncService)
    service._dispatcher = Dispatcher()
    service._observer = SimpleNamespace(release=lambda _session_id: None)
    service._lifecycle = TaskLifecycle()
    service._lock = Lock()
    service._closed = False

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
    assert inventory.session_id == session_ids["inventory"]
    assert baseline.session_id == session_ids["baseline"]
    assert verify.session_id == session_ids["verify"]
    assert rebaseline.session_id == session_ids["rebaseline"]
    for session in (inventory, baseline, verify, rebaseline):
        service._lifecycle.require_session(session.session_id)


def test_rebaseline_refuses_an_unselected_scope_before_submission() -> None:
    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
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
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            raise VolumeResolutionRequired(resolution)

    service = object.__new__(NamiSyncService)
    service._dispatcher = Dispatcher()
    service._runtime = SimpleNamespace(
        drop_inventory_details=lambda _request_id: None,
    )
    service._observer = SimpleNamespace(release=lambda _session_id: None)
    service._lifecycle = TaskLifecycle()
    service._lock = Lock()
    service._closed = False

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
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            raise VolumeResolutionRequired(resolution)

    service = object.__new__(NamiSyncService)
    service._dispatcher = Dispatcher()
    service._runtime = SimpleNamespace(
        drop_inventory_details=lambda _request_id: None,
    )
    service._observer = SimpleNamespace(release=lambda _session_id: None)
    service._lifecycle = TaskLifecycle()
    service._lock = Lock()
    service._closed = False

    with pytest.raises(LocationResolutionError) as raised:
        service.start_verify(location_id=7)

    assert raised.value.resolution.selected_mount == "F:\\"


def _task_capacity_service(
    lifecycle: TaskLifecycle | None = None,
    stage: Callable[[str], None] | None = None,
) -> tuple[
    NamiSyncService,
    SimpleNamespace,
]:
    counts = SimpleNamespace(requests=0, adoptions=0, submissions=0)
    counts_lock = Lock()

    def increment(name: str) -> int:
        with counts_lock:
            value = getattr(counts, name) + 1
            setattr(counts, name, value)
            return value

    class Runtime:
        def create_plan_request(
            self,
            request_id: str,
            source_path: str,
            target_path: str,
            *,
            deletion_policy: str | None,
        ) -> object:
            del source_path, target_path, deletion_policy
            if stage is not None:
                stage("runtime")
            increment("requests")
            return SimpleNamespace(request_id=request_id)

    class Observer:
        def adopt(self, session_id: str, sink, stream):
            del session_id, sink, stream
            if stage is not None:
                stage("observer")
            increment("adoptions")
            return lambda: None

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach) -> SessionId:
            del kind, request
            if stage is not None:
                stage("dispatcher")
            submission = increment("submissions")
            session_id = SessionId(f"{40_000 + submission:032x}")
            rollback = attach(session_id, _SequenceStream())
            assert callable(rollback)
            return session_id

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()
    service._observer = Observer()
    service._dispatcher = Dispatcher()
    service._lifecycle = lifecycle or TaskLifecycle()
    service._lock = Lock()
    service._closed = False
    return service, counts


def test_application_same_command_joiner_replays_single_48th_task_effect(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()

    service, counts = _task_capacity_service()
    delivery_calls: list[str] = []
    final_factory_entered = Event()
    release_final_factory = Event()

    def delivery_factory(task_id: str):
        delivery_calls.append(task_id)
        if len(delivery_calls) == TASK_EFFECT_CAPACITY:
            final_factory_entered.set()
            assert release_final_factory.wait(2)
        return lambda _update: None

    for index in range(TASK_EFFECT_CAPACITY - 1):
        started = service.start_task_plan(
            str(source),
            str(target),
            deletion_policy=None,
            command_id=f"{40_100 + index:032x}",
            delivery_factory=delivery_factory,
        )
        assert started.task_id == delivery_calls[-1]

    final_command_id = f"{40_500:032x}"
    results: list[object] = []
    failures: list[BaseException] = []
    joiner_done = Event()

    def start_final(*, joiner: bool) -> None:
        try:
            results.append(
                service.start_task_plan(
                    str(source),
                    str(target),
                    deletion_policy=None,
                    command_id=final_command_id,
                    delivery_factory=delivery_factory,
                )
            )
        except BaseException as error:
            failures.append(error)
        finally:
            if joiner:
                joiner_done.set()

    owner = Thread(target=start_final, kwargs={"joiner": False})
    joiner = Thread(target=start_final, kwargs={"joiner": True})
    owner.start()
    assert final_factory_entered.wait(1)
    joiner.start()
    assert not joiner_done.wait(0.05)
    assert len(delivery_calls) == TASK_EFFECT_CAPACITY
    assert counts.requests == TASK_EFFECT_CAPACITY - 1
    release_final_factory.set()
    owner.join(2)
    joiner.join(2)
    assert not owner.is_alive()
    assert not joiner.is_alive()
    assert failures == []
    assert len(results) == 2
    assert results[0] == results[1]
    assert len(delivery_calls) == TASK_EFFECT_CAPACITY
    assert counts.requests == TASK_EFFECT_CAPACITY
    assert counts.submissions == TASK_EFFECT_CAPACITY
    assert counts.adoptions == TASK_EFFECT_CAPACITY


def test_disjoint_task_starts_overlap_all_lower_application_work(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    lifecycle = TaskLifecycle()
    first_command_id = f"{40_601:032x}"
    second_command_id = f"{40_602:032x}"
    first_stripe = lifecycle.command_guard(first_command_id)
    assert lifecycle.command_guard(second_command_id) is not first_stripe
    barriers = {
        name: threading.Barrier(2)
        for name in ("delivery", "runtime", "dispatcher", "observer")
    }

    def stage(name: str) -> None:
        barriers[name].wait(2)

    service, counts = _task_capacity_service(lifecycle, stage)
    delivery_calls: list[str] = []

    def delivery_factory(task_id: str):
        delivery_calls.append(task_id)
        stage("delivery")
        return lambda _update: None

    results: list[TaskStartView] = []
    failures: list[BaseException] = []

    def start(command_id: str) -> None:
        try:
            results.append(
                service.start_task_plan(
                    str(source),
                    str(target),
                    deletion_policy=None,
                    command_id=command_id,
                    delivery_factory=delivery_factory,
                )
            )
        except BaseException as error:
            failures.append(error)

    first = Thread(target=start, args=(first_command_id,))
    second = Thread(target=start, args=(second_command_id,))
    first.start()
    second.start()
    first.join(3)
    second.join(3)

    assert not first.is_alive()
    assert not second.is_alive()
    assert failures == []
    assert len(results) == 2
    assert len(set(delivery_calls)) == 2
    assert counts.requests == 2
    assert counts.submissions == 2
    assert counts.adoptions == 2


def test_application_refuses_distinct_49th_task_before_lower_effects(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    service, counts = _task_capacity_service()
    delivery_calls: list[str] = []

    def delivery_factory(task_id: str):
        delivery_calls.append(task_id)
        return lambda _update: None

    for index in range(TASK_EFFECT_CAPACITY):
        service.start_task_plan(
            str(source),
            str(target),
            deletion_policy=None,
            command_id=f"{41_100 + index:032x}",
            delivery_factory=delivery_factory,
        )

    before = (
        len(delivery_calls),
        counts.requests,
        counts.submissions,
        counts.adoptions,
    )
    with pytest.raises(TaskUnavailableError, match="capacity"):
        service.start_task_plan(
            str(source),
            str(target),
            deletion_policy=None,
            command_id=f"{40_999:032x}",
            delivery_factory=delivery_factory,
        )

    assert (
        len(delivery_calls),
        counts.requests,
        counts.submissions,
        counts.adoptions,
    ) == before


def test_direct_start_replay_waits_for_close_and_admits_successor() -> None:
    close_entered = Event()
    release_close = Event()

    class Runtime:
        def __init__(self) -> None:
            self.detail_drops: list[str] = []

        def drop_inventory_details(self, request_id: str) -> None:
            self.detail_drops.append(request_id)

    class Dispatcher:
        def __init__(self) -> None:
            self.submissions = 0
            self.closes: list[str] = []

        def submit(self, kind: str, request: object, *, attach) -> SessionId:
            del kind, request
            self.submissions += 1
            session_id = SessionId(f"{50_000 + self.submissions:032x}")
            rollback = attach(session_id, _SequenceStream())
            assert callable(rollback)
            return session_id

        def close(self, session_id: str) -> None:
            close_entered.set()
            assert release_close.wait(2)
            self.closes.append(session_id)

    runtime = Runtime()
    dispatcher = Dispatcher()
    service = object.__new__(NamiSyncService)
    service._runtime = runtime
    service._dispatcher = dispatcher
    service._observer = SimpleNamespace(release=lambda _session_id: None)
    service._lifecycle = TaskLifecycle()
    service._lock = Lock()
    service._closed = False
    command_id = "direct-close-replay"
    first = service.start_inventory(
        root_path=r"F:\library",
        command_id=command_id,
    )
    closed: list[bool] = []
    replayed: list[LocationSession] = []
    failures: list[BaseException] = []
    retry_done = Event()

    def close() -> None:
        try:
            service.close_session(first.session_id)
            closed.append(True)
        except BaseException as error:
            failures.append(error)

    def replay() -> None:
        try:
            replayed.append(
                service.start_inventory(
                    root_path=r"F:\library",
                    command_id=command_id,
                )
            )
        except BaseException as error:
            failures.append(error)
        finally:
            retry_done.set()

    closer = Thread(target=close)
    retry = Thread(target=replay)
    closer.start()
    assert close_entered.wait(1)
    retry.start()
    assert not retry_done.wait(0.05)
    release_close.set()
    closer.join(2)
    retry.join(2)

    assert not closer.is_alive()
    assert not retry.is_alive()
    assert failures == []
    assert closed == [True]
    assert len(replayed) == 1
    assert replayed[0].session_id != first.session_id
    assert dispatcher.submissions == 2
    assert dispatcher.closes == [first.session_id]
    assert runtime.detail_drops == [first.request_id]


@pytest.mark.parametrize(
    ("start_kind", "receipt_kind", "detail_kind"),
    [
        ("plan", "plan", None),
        ("execution", "execution", "execution"),
        ("inventory", "inventory", "inventory"),
        ("baseline", "baseline", "inventory"),
        ("verify", "verify", "inventory"),
        ("rebaseline", "rebaseline", "inventory"),
    ],
)
def test_direct_starts_associate_and_retire_exact_session_receipts(
    tmp_path: Path,
    start_kind: str,
    receipt_kind: str,
    detail_kind: str | None,
) -> None:
    source = tmp_path / f"{start_kind}-source"
    target = tmp_path / f"{start_kind}-target"
    source.mkdir()
    target.mkdir()
    plan_request_id = f"{41_001:032x}"
    run_id = f"{41_002:032x}"
    command_id = f"{41_003:032x}"
    artifact = SimpleNamespace(
        request=SimpleNamespace(request_id=plan_request_id),
        plan=plan((operation(OperationKind.COPY),)),
    )

    class Runtime:
        def __init__(self) -> None:
            self.execution_drops: list[str] = []
            self.inventory_drops: list[str] = []
            self.plan_drops: list[str] = []

        def create_plan_request(
            self,
            request_id: str,
            source_path: str,
            target_path: str,
            *,
            deletion_policy: str | None,
        ) -> object:
            del source_path, target_path, deletion_policy
            return SimpleNamespace(request_id=request_id)

        def get_plan(self, request_id: str) -> object:
            if request_id != plan_request_id:
                raise KeyError(request_id)
            return artifact

        def commit_plan(self, request_id: str, **_kwargs) -> object:
            assert request_id == plan_request_id
            return SimpleNamespace(
                execution_set=SimpleNamespace(run_id=run_id),
            )

        def drop_execution_details(self, detail_id: str) -> None:
            self.execution_drops.append(detail_id)

        def drop_inventory_details(self, detail_id: str) -> None:
            self.inventory_drops.append(detail_id)

        def drop_plan(self, request_id: str) -> None:
            self.plan_drops.append(request_id)

    class Dispatcher:
        def __init__(self) -> None:
            self.submissions = 0
            self.closed: list[str] = []
            self.stream_closes = 0

        def submit(self, kind: str, request: object, *, attach) -> SessionId:
            del kind, request
            self.submissions += 1
            session_id = SessionId(f"{41_100 + self.submissions:032x}")

            def close_stream() -> None:
                self.stream_closes += 1

            rollback = attach(
                session_id,
                SimpleNamespace(close=close_stream),
            )
            assert callable(rollback)
            return session_id

        def close(self, session_id: str) -> None:
            self.closed.append(session_id)

    runtime = Runtime()
    dispatcher = Dispatcher()
    service = object.__new__(NamiSyncService)
    service._runtime = runtime
    service._dispatcher = dispatcher
    service._observer = SimpleNamespace(release=lambda _session_id: None)
    service._lifecycle = TaskLifecycle()
    service._lock = Lock()
    service._plan_selections = {}
    service._closed = False
    if start_kind == "execution":
        _publish_session(
            service._lifecycle,
            f"{41_050:032x}",
            kind="plan",
            request_id=plan_request_id,
        )

    selected_paths = ("a.txt",)

    def start():
        if start_kind == "plan":
            return service.start_plan(
                str(source),
                str(target),
                command_id=command_id,
            )
        if start_kind == "execution":
            return service.start_execution(
                plan_request_id,
                command_id=command_id,
            )
        method = getattr(service, f"start_{start_kind}")
        return method(
            root_path=str(source),
            selected_paths=selected_paths,
            command_id=command_id,
        )

    if start_kind == "plan":
        signature = (str(source), str(target), None)
    elif start_kind == "execution":
        signature = (plan_request_id, False, None, False)
    else:
        signature = (str(source), None, selected_paths, None, None)

    started = start()
    assert start() == started
    assert dispatcher.submissions == 1
    assert dispatcher.stream_closes == 1
    association = service._lifecycle.require_session(
        started.session_id,
        task_id=None,
    )
    receipt = service._lifecycle.replay_start(
        command_id,
        receipt_kind,
        signature,
    )
    assert receipt is not None
    assert receipt.session_id == started.session_id
    assert receipt.request_id == getattr(
        started,
        "request_id",
        getattr(started, "run_id", None),
    )

    service.close_session(started.session_id)

    assert dispatcher.closed == [started.session_id]
    with pytest.raises(LifecycleAssociationError):
        service._lifecycle.require_session(
            association.session_id,
            task_id=None,
            live=False,
        )
    assert service._lifecycle.replay_start(
        command_id,
        receipt_kind,
        signature,
    ) is None
    assert runtime.plan_drops == []
    assert runtime.execution_drops == (
        [run_id] if detail_kind == "execution" else []
    )
    assert runtime.inventory_drops == (
        [receipt.request_id] if detail_kind == "inventory" else []
    )


def test_ls_3_terminal_reconciliation_matches_dispatcher_truth() -> None:
    session_id = f"{42_001:032x}"
    command_id = f"{42_002:032x}"
    request_id = f"{42_003:032x}"
    signature = ("source", "target", None)
    record, exact_delivery = _task_terminal_truth(session_id)
    delivered_record = exact_delivery.record
    assert exact_delivery.terminal_event is not None
    delivered_event = exact_delivery.terminal_event
    lifecycle = TaskLifecycle()
    task_id, association = _publish_task_plan(
        lifecycle,
        session_id,
        command_id,
        request_id,
        signature,
    )

    class Dispatcher:
        def __init__(self) -> None:
            self.present = True
            self.close_attempts = 0
            self.close_transitions = 0

        def get(self, candidate: str) -> SessionRecord:
            if candidate != session_id or not self.present:
                raise SessionNotFound(candidate)
            return record

        def close(self, candidate: str) -> None:
            assert candidate == session_id
            self.close_attempts += 1
            if self.present:
                self.present = False
                self.close_transitions += 1

    class Runtime:
        def __init__(self) -> None:
            self.dropped: list[str] = []

        def drop_plan(self, candidate: str) -> None:
            self.dropped.append(candidate)

    dispatcher = Dispatcher()
    runtime = Runtime()
    service = object.__new__(NamiSyncService)
    service._dispatcher = dispatcher
    service._observer = SimpleNamespace(release=lambda _session_id: None)
    service._runtime = runtime
    service._lifecycle = lifecycle
    service._lock = Lock()
    service._plan_selections = {}

    wrong_record = replace(
        delivered_record,
        created_at="2026-01-02T03:04:06.123456+00:00",
    )
    wrong_result = dict(delivered_event.body["result"])
    wrong_result["status"] = "failed"
    wrong_event = replace(
        delivered_event,
        body={"result": wrong_result},
    )
    for mismatch in (
        TaskTerminalDelivery(wrong_record, delivered_event),
        TaskTerminalDelivery(delivered_record, wrong_event),
    ):
        for _attempt in range(2):
            with pytest.raises(
                RuntimeError,
                match="delivered terminal truth disagrees",
            ):
                service.release_task_session(task_id, session_id, mismatch)
            assert dispatcher.close_attempts == 0
            assert lifecycle.require_session(
                session_id,
                task_id=task_id,
            ) == association

    released = service.release_task_session(
        task_id,
        session_id,
        exact_delivery,
    )
    assert (released.task_id, released.session_id) == (task_id, session_id)
    assert dispatcher.close_attempts == 1
    assert dispatcher.close_transitions == 1
    assert not dispatcher.present

    replayed = service.release_task_session(
        task_id,
        session_id,
        exact_delivery,
    )
    assert replayed == released
    assert dispatcher.close_attempts == 1
    assert dispatcher.close_transitions == 1

    closed = service.close_task(task_id, session_id, exact_delivery)
    assert (closed.task_id, closed.session_id) == (task_id, session_id)
    assert dispatcher.close_attempts == 2
    assert dispatcher.close_transitions == 1
    assert runtime.dropped == [request_id]
    with pytest.raises(LifecycleAssociationError):
        lifecycle.require_session(session_id, task_id=task_id, live=False)


def test_task_association_gates_reobserve_release_and_close_effects() -> None:
    session_id = f"{43_001:032x}"
    wrong_session_id = f"{43_002:032x}"
    command_id = f"{43_003:032x}"
    request_id = f"{43_004:032x}"
    wrong_task_id = f"task-{43_005:032x}"
    signature = ("source", "target", None)
    record, delivery = _task_terminal_truth(session_id)
    running = session_record_view(
        SessionRecord(
            session_id=SessionId(session_id),
            kind="sync-plan",
            state=SessionState.RUNNING,
            resources=(),
            checkpoint=b"checkpoint",
            supports_pause=False,
            admission_order=0,
            created_at=NOW,
            started_at=NOW,
        )
    )
    lifecycle = TaskLifecycle()
    task_id, _association = _publish_task_plan(
        lifecycle,
        session_id,
        command_id,
        request_id,
        signature,
    )

    class Observer:
        def __init__(self) -> None:
            self.reobserved: list[str] = []
            self.release_calls: list[str] = []
            self.release_transitions: list[str] = []
            self.observing = False

        def reobserve(self, candidate: str, sink, from_sequence: int):
            del sink, from_sequence
            self.reobserved.append(candidate)
            self.observing = True
            return running

        def release(self, candidate: str) -> None:
            self.release_calls.append(candidate)
            if self.observing:
                self.observing = False
                self.release_transitions.append(candidate)

    class Dispatcher:
        def __init__(self) -> None:
            self.present = True
            self.close_calls: list[str] = []
            self.close_transitions: list[str] = []

        def get(self, candidate: str) -> SessionRecord:
            if candidate != session_id or not self.present:
                raise SessionNotFound(candidate)
            return record

        def close(self, candidate: str) -> None:
            self.close_calls.append(candidate)
            if self.present:
                self.present = False
                self.close_transitions.append(candidate)

    class Runtime:
        def __init__(self) -> None:
            self.plan_drops: list[str] = []

        def drop_plan(self, candidate: str) -> None:
            self.plan_drops.append(candidate)

    observer = Observer()
    dispatcher = Dispatcher()
    runtime = Runtime()
    service = object.__new__(NamiSyncService)
    service._observer = observer
    service._dispatcher = dispatcher
    service._runtime = runtime
    service._lifecycle = lifecycle
    service._lock = Lock()
    service._plan_selections = {}

    for candidate_task, candidate_session in (
        (wrong_task_id, session_id),
        (task_id, wrong_session_id),
    ):
        with pytest.raises(TaskUnavailableError):
            service.reobserve_task(
                candidate_task,
                candidate_session,
                lambda _update: None,
                1,
            )
        with pytest.raises(TaskUnavailableError):
            service.release_task_session(
                candidate_task,
                candidate_session,
                delivery,
            )
        with pytest.raises(TaskUnavailableError):
            service.close_task(
                candidate_task,
                candidate_session,
                delivery,
            )
    assert observer.reobserved == []
    assert observer.release_calls == []
    assert dispatcher.close_calls == []
    assert runtime.plan_drops == []

    assert service.reobserve_task(
        task_id,
        session_id,
        lambda _update: None,
        1,
    ) == running
    released = service.release_task_session(
        task_id,
        session_id,
        delivery,
    )
    assert released.session_id == session_id
    assert observer.reobserved == [session_id]
    assert observer.release_calls == [session_id]
    assert observer.release_transitions == [session_id]
    assert dispatcher.close_calls == [session_id]
    assert dispatcher.close_transitions == [session_id]

    closed = service.close_task(task_id, session_id, delivery)
    assert closed.task_id == task_id
    assert observer.release_calls == [session_id, session_id]
    assert observer.release_transitions == [session_id]
    assert dispatcher.close_calls == [session_id, session_id]
    assert dispatcher.close_transitions == [session_id]
    assert runtime.plan_drops == [request_id]

    for retired_operation in (
        lambda: service.reobserve_task(
            task_id,
            session_id,
            lambda _update: None,
            1,
        ),
        lambda: service.release_task_session(task_id, session_id, delivery),
        lambda: service.close_task(task_id, session_id, delivery),
    ):
        with pytest.raises(TaskUnavailableError):
            retired_operation()
    assert observer.reobserved == [session_id]
    assert observer.release_calls == [session_id, session_id]
    assert observer.release_transitions == [session_id]
    assert dispatcher.close_calls == [session_id, session_id]
    assert dispatcher.close_transitions == [session_id]
    assert runtime.plan_drops == [request_id]


@pytest.mark.parametrize(
    "fault_step",
    ["observer", "dispatcher", "detail", "plan"],
)
def test_ls_4b_whole_operation_cleanup_replay_converges(
    fault_step: str,
) -> None:
    session_id = f"{44_001:032x}"
    command_id = f"{44_002:032x}"
    request_id = f"{44_003:032x}"
    detail_id = f"{44_004:032x}"
    signature = ("source", "target", None)
    record, delivery = _task_terminal_truth(session_id)
    lifecycle = TaskLifecycle()
    task_id, _association = _publish_task_plan(
        lifecycle,
        session_id,
        command_id,
        request_id,
        signature,
        detail_owner=("inventory", detail_id),
    )
    order = ("observer", "dispatcher", "detail", "plan")
    calls: list[tuple[str, str]] = []
    transitions: list[tuple[str, str]] = []
    present = {name: True for name in order}
    faulted = False

    def effect(name: str, subject: str) -> None:
        nonlocal faulted
        calls.append((name, subject))
        if name == fault_step and not faulted:
            faulted = True
            raise RuntimeError(f"{name} fault")
        if present[name]:
            present[name] = False
            transitions.append((name, subject))

    class Observer:
        def release(self, candidate: str) -> None:
            assert candidate == session_id
            effect("observer", candidate)

    class Dispatcher:
        def get(self, candidate: str) -> SessionRecord:
            if candidate != session_id or not present["dispatcher"]:
                raise SessionNotFound(candidate)
            return record

        def close(self, candidate: str) -> None:
            assert candidate == session_id
            if not present["dispatcher"]:
                calls.append(("dispatcher", candidate))
                raise SessionNotFound(candidate)
            effect("dispatcher", candidate)

    class Runtime:
        def drop_inventory_details(self, candidate: str) -> None:
            assert candidate == detail_id
            effect("detail", candidate)

        def drop_plan(self, candidate: str) -> None:
            assert candidate == request_id
            effect("plan", candidate)

    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = Dispatcher()
    service._runtime = Runtime()
    service._lifecycle = lifecycle
    service._lock = Lock()
    service._plan_selections = {}

    with pytest.raises(RuntimeError, match=f"{fault_step} fault"):
        service.close_task(task_id, session_id, delivery)
    assert service.close_task(task_id, session_id, delivery) == TaskCloseView(
        task_id,
        session_id,
    )

    subjects = {
        "observer": session_id,
        "dispatcher": session_id,
        "detail": detail_id,
        "plan": request_id,
    }
    assert transitions == [(name, subjects[name]) for name in order]
    fault_index = order.index(fault_step)
    assert {
        name: sum(call_name == name for call_name, _subject in calls)
        for name in order
    } == {
        name: 2 if index <= fault_index else 1
        for index, name in enumerate(order)
    }
    with pytest.raises(LifecycleAssociationError):
        lifecycle.require_session(session_id, task_id=task_id, live=False)


def test_ls_4b_whole_operation_cleanup_singleflights_concurrent_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = f"{45_001:032x}"
    command_id = f"{45_002:032x}"
    request_id = f"{45_003:032x}"
    signature = ("source", "target", None)
    record, delivery = _task_terminal_truth(session_id)
    lifecycle = TaskLifecycle()
    task_id, _association = _publish_task_plan(
        lifecycle,
        session_id,
        command_id,
        request_id,
        signature,
        detail_owner=("inventory", request_id),
    )
    observer_entered = Event()
    peer_waiting = Event()
    release_observer = Event()
    transitions: list[tuple[str, str]] = []

    class Observer:
        def release(self, candidate: str) -> None:
            assert candidate == session_id
            transitions.append(("observer", candidate))
            observer_entered.set()
            assert release_observer.wait(2)

    class Dispatcher:
        def __init__(self) -> None:
            self.present = True

        def get(self, candidate: str) -> SessionRecord:
            if candidate != session_id or not self.present:
                raise SessionNotFound(candidate)
            return record

        def close(self, candidate: str) -> None:
            assert candidate == session_id
            transitions.append(("dispatcher", candidate))
            self.present = False

    dispatcher = Dispatcher()

    class Runtime:
        def drop_inventory_details(self, candidate: str) -> None:
            transitions.append(("detail", candidate))

    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = dispatcher
    service._runtime = Runtime()
    service._lifecycle = lifecycle
    service._lock = Lock()
    service._plan_selections = {}
    condition_type = type(lifecycle._condition)
    original_wait = condition_type.wait

    def observe_wait(condition, timeout=None):
        if (
            condition is lifecycle._condition
            and current_thread().name == "settlement-peer"
        ):
            peer_waiting.set()
        return original_wait(condition, timeout)

    monkeypatch.setattr(condition_type, "wait", observe_wait)

    results: list[TaskSessionReleaseView] = []
    failures: list[BaseException] = []

    def release() -> None:
        try:
            results.append(
                service.release_task_session(task_id, session_id, delivery)
            )
        except BaseException as error:
            failures.append(error)

    first = Thread(target=release, name="settlement-owner")
    second = Thread(target=release, name="settlement-peer")
    first.start()
    assert observer_entered.wait(1)
    second.start()
    assert peer_waiting.wait(1)
    release_observer.set()
    first.join(2)
    second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert failures == []
    assert sorted(results, key=repr) == [
        TaskSessionReleaseView(task_id, session_id),
        TaskSessionReleaseView(task_id, session_id),
    ]
    assert transitions == [
        ("observer", session_id),
        ("dispatcher", session_id),
        ("detail", request_id),
    ]


def test_cleanup_post_effect_interrupt_replays_calls_not_effects() -> None:
    session_id = f"{45_101:032x}"
    request_id = f"{45_103:032x}"
    lifecycle = TaskLifecycle()
    _publish_session(
        lifecycle,
        session_id,
        kind="inventory",
        detail_owner=("inventory", request_id),
        request_id=request_id,
    )
    calls: list[tuple[str, str]] = []
    transitions: list[tuple[str, str]] = []

    class Observer:
        present = True

        def release(self, candidate: str) -> None:
            calls.append(("observer", candidate))
            if self.present:
                self.present = False
                transitions.append(("observer", candidate))
                raise TimeoutError(
                    "observer retired before join acknowledgement"
                )

    class Dispatcher:
        def close(self, candidate: str) -> None:
            calls.append(("dispatcher", candidate))
            transitions.append(("dispatcher", candidate))

    class Runtime:
        def drop_inventory_details(self, candidate: str) -> None:
            calls.append(("detail", candidate))
            transitions.append(("detail", candidate))

    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = Dispatcher()
    service._runtime = Runtime()
    service._lifecycle = lifecycle
    service._lock = Lock()
    service._plan_selections = {}

    with pytest.raises(TimeoutError, match="before join acknowledgement"):
        service.close_session(session_id)
    service.close_session(session_id)

    assert calls == [
        ("observer", session_id),
        ("observer", session_id),
        ("dispatcher", session_id),
        ("detail", request_id),
    ]
    assert transitions == [
        ("observer", session_id),
        ("dispatcher", session_id),
        ("detail", request_id),
    ]


def test_s6_cleanup_replay_repeats_owner_calls_not_effects() -> None:
    session_id = f"{45_201:032x}"
    command_id = f"{45_202:032x}"
    mutation_id = f"{45_203:032x}"
    request_id = f"{45_204:032x}"
    unrelated_id = f"{45_205:032x}"
    detail_id = f"{45_206:032x}"
    unrelated_detail_id = f"{45_207:032x}"
    signature = ("source", "target", None)
    mutation_signature = (0, ("selected",), ())
    record, delivery = _task_terminal_truth(session_id)
    lifecycle = TaskLifecycle()
    task_id, _association = _publish_task_plan(
        lifecycle,
        session_id,
        command_id,
        request_id,
        signature,
        detail_owner=("inventory", detail_id),
    )
    plan_token = lifecycle.require_plan(request_id)
    mutation = lifecycle.begin_plan_mutation(
        plan_token,
        mutation_id,
        mutation_signature,
    )
    lifecycle.complete_plan_mutation(mutation)

    class Observer:
        def __init__(self) -> None:
            self.present = True
            self.calls: list[str] = []
            self.transitions: list[str] = []

        def release(self, candidate: str) -> None:
            self.calls.append(candidate)
            if self.present:
                self.present = False
                self.transitions.append(candidate)

    class Dispatcher:
        def __init__(self) -> None:
            self.present = True
            self.calls: list[str] = []
            self.transitions: list[str] = []

        def get(self, candidate: str) -> SessionRecord:
            if candidate != session_id or not self.present:
                raise SessionNotFound(candidate)
            return record

        def close(self, candidate: str) -> None:
            self.calls.append(candidate)
            if not self.present:
                raise SessionNotFound(candidate)
            self.present = False
            self.transitions.append(candidate)

    class Runtime:
        def __init__(self) -> None:
            self.plans = {
                request_id: object(),
                unrelated_id: object(),
            }
            self.details = {
                detail_id: object(),
                unrelated_detail_id: object(),
            }
            self.plan_calls: list[str] = []
            self.plan_transitions: list[str] = []
            self.detail_calls: list[str] = []
            self.detail_transitions: list[str] = []
            self.interrupted = False

        def drop_plan(self, candidate: str) -> None:
            self.plan_calls.append(candidate)
            if self.plans.pop(candidate, None) is not None:
                self.plan_transitions.append(candidate)
                if not self.interrupted:
                    self.interrupted = True
                    raise RuntimeError(
                        "plan retired before caller acknowledgement"
                    )

        def drop_inventory_details(self, candidate: str) -> None:
            self.detail_calls.append(candidate)
            if self.details.pop(candidate, None) is not None:
                self.detail_transitions.append(candidate)

    observer = Observer()
    dispatcher = Dispatcher()
    runtime = Runtime()
    unrelated_plan = runtime.plans[unrelated_id]
    unrelated_detail = runtime.details[unrelated_detail_id]
    selection = service_module._PlanSelectionState(object(), plan_token)
    unrelated_selection = object()
    service = object.__new__(NamiSyncService)
    service._observer = observer
    service._dispatcher = dispatcher
    service._runtime = runtime
    service._lifecycle = lifecycle
    service._lock = Lock()
    service._plan_selections = {
        request_id: selection,
        unrelated_id: unrelated_selection,
    }

    with pytest.raises(RuntimeError, match="before caller acknowledgement"):
        service.close_task(task_id, session_id, delivery)

    assert runtime.detail_calls == [detail_id]
    assert runtime.detail_transitions == [detail_id]
    assert runtime.plan_calls == [request_id]
    assert runtime.plan_transitions == [request_id]
    assert service._plan_selections[request_id] is selection
    assert lifecycle.require_plan(request_id) == plan_token

    assert service.close_task(task_id, session_id, delivery) == TaskCloseView(
        task_id,
        session_id,
    )

    assert observer.calls == [session_id, session_id]
    assert observer.transitions == [session_id]
    assert dispatcher.calls == [session_id, session_id]
    assert dispatcher.transitions == [session_id]
    assert runtime.detail_calls == [detail_id, detail_id]
    assert runtime.detail_transitions == [detail_id]
    assert runtime.plan_calls == [request_id, request_id]
    assert runtime.plan_transitions == [request_id]
    assert runtime.plans == {unrelated_id: unrelated_plan}
    assert runtime.details == {unrelated_detail_id: unrelated_detail}
    assert request_id not in service._plan_selections
    assert service._plan_selections[unrelated_id] is unrelated_selection
    with pytest.raises(LifecycleAssociationError):
        lifecycle.require_plan(request_id)
    with pytest.raises(LifecycleAssociationError):
        lifecycle.begin_plan_mutation(
            plan_token,
            mutation_id,
            mutation_signature,
        )
    assert lifecycle.replay_start(
        command_id,
        "task-plan",
        signature,
    ) is None


def test_disjoint_session_settlements_overlap_at_lower_owner_barrier() -> None:
    first_session = f"{45_301:032x}"
    second_session = f"{45_302:032x}"
    first_request = f"{45_303:032x}"
    second_request = f"{45_304:032x}"
    lifecycle = TaskLifecycle()
    _publish_session(
        lifecycle,
        first_session,
        kind="inventory",
        detail_owner=("inventory", first_request),
        request_id=first_request,
    )
    _publish_session(
        lifecycle,
        second_session,
        kind="inventory",
        detail_owner=("inventory", second_request),
        request_id=second_request,
    )
    entered: set[str] = set()
    entered_lock = Lock()
    first_entered = Event()
    both_entered = Event()
    release = Event()

    class Observer:
        def release(self, candidate: str) -> None:
            with entered_lock:
                entered.add(candidate)
                if candidate == first_session:
                    first_entered.set()
                if len(entered) == 2:
                    both_entered.set()
            assert release.wait(2)

    class Dispatcher:
        def __init__(self) -> None:
            self.closed: list[str] = []

        def close(self, candidate: str) -> None:
            self.closed.append(candidate)

    class Runtime:
        def __init__(self) -> None:
            self.details = {
                first_request: object(),
                second_request: object(),
            }
            self.dropped: list[str] = []

        def drop_inventory_details(self, candidate: str) -> None:
            if self.details.pop(candidate, None) is not None:
                self.dropped.append(candidate)

    dispatcher = Dispatcher()
    runtime = Runtime()
    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = dispatcher
    service._runtime = runtime
    service._lifecycle = lifecycle
    service._lock = Lock()
    service._plan_selections = {}
    failures: list[BaseException] = []

    def close(candidate: str) -> None:
        try:
            service.close_session(candidate)
        except BaseException as error:
            failures.append(error)

    first = Thread(target=close, args=(first_session,))
    second = Thread(target=close, args=(second_session,))
    first.start()
    assert first_entered.wait(1)
    second.start()
    assert both_entered.wait(1)
    assert entered == {first_session, second_session}
    release.set()
    first.join(2)
    second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert failures == []
    assert set(dispatcher.closed) == {first_session, second_session}
    assert set(runtime.dropped) == {first_request, second_request}
    assert runtime.details == {}


def test_selection_mutation_drop_race_does_not_retain_or_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_id = f"{31_001:032x}"
    command_id = f"{31_002:032x}"
    plan_operation = operation(OperationKind.COPY)
    artifact = SimpleNamespace(
        request=SimpleNamespace(request_id=request_id),
        plan=plan((plan_operation,)),
    )

    class Runtime:
        def __init__(self) -> None:
            self._lock = Lock()
            self.current: object | None = artifact
            self.drop_calls = 0

        def get_plan(self, candidate: str) -> object:
            with self._lock:
                if candidate != request_id or self.current is None:
                    raise KeyError(candidate)
                return self.current

        def drop_plan(self, candidate: str) -> None:
            assert candidate == request_id
            with self._lock:
                self.drop_calls += 1
                self.current = None

    runtime = Runtime()
    effects: list[object] = []
    apply_selection = service_module.apply_selection_mutation

    def record_effect(*args, **kwargs):
        effects.append(args[1])
        return apply_selection(*args, **kwargs)

    monkeypatch.setattr(
        service_module,
        "apply_selection_mutation",
        record_effect,
    )
    service = object.__new__(NamiSyncService)
    service._runtime = runtime
    service._lock = Lock()
    service._plan_selections = {}
    service._lifecycle = TaskLifecycle()
    service._closed = False
    _publish_session(
        service._lifecycle,
        f"{31_003:032x}",
        kind="plan",
        request_id=request_id,
    )
    selection_code = service._selection_state.__func__.__code__
    artifact_read = Event()
    allow_selection_install = Event()
    failures: list[BaseException] = []

    def trace_selection_gap(frame, event, _arg):
        if (
            event == "line"
            and frame.f_code is selection_code
            and frame.f_locals.get("artifact") is artifact
            and "state" not in frame.f_locals
        ):
            artifact_read.set()
            assert allow_selection_install.wait(2)
        return trace_selection_gap

    def mutate() -> None:
        sys.settrace(trace_selection_gap)
        try:
            service.mutate_selection(
                request_id,
                0,
                deselect=(str(plan_operation.op_id),),
                command_id=command_id,
            )
        except BaseException as error:
            failures.append(error)
        finally:
            sys.settrace(None)

    mutation = Thread(target=mutate)
    mutation.start()
    assert artifact_read.wait(2)

    service.drop_plan(request_id)
    assert runtime.current is None
    assert runtime.drop_calls == 1

    allow_selection_install.set()
    mutation.join(2)

    assert not mutation.is_alive()
    assert len(failures) == 1
    assert type(failures[0]) is KeyError
    assert failures[0].args == (request_id,)
    assert request_id not in service._plan_selections
    assert effects == []

    with pytest.raises(KeyError) as replay:
        service.mutate_selection(
            request_id,
            0,
            deselect=(str(plan_operation.op_id),),
            command_id=command_id,
        )

    assert replay.value.args == (request_id,)
    assert service._plan_selections == {}
    assert effects == []
    assert runtime.drop_calls == 1


def test_selection_liveness_retry_preserves_concurrent_successor() -> None:
    request_id = f"{31_101:032x}"
    plan_operation = operation(OperationKind.COPY)
    sync_plan = plan((plan_operation,))

    def plan_artifact() -> object:
        return SimpleNamespace(
            request=SimpleNamespace(request_id=request_id),
            plan=sync_plan,
        )

    original = plan_artifact()
    observed_replacement = plan_artifact()
    first_successor = plan_artifact()
    final_successor = plan_artifact()
    fresh_snapshot = Event()
    allow_fresh_read = Event()

    class Runtime:
        def __init__(self) -> None:
            self._lock = Lock()
            self.current = original
            self.reads = 0

        def get_plan(self, candidate: str) -> object:
            assert candidate == request_id
            with self._lock:
                self.reads += 1
                if self.reads == 1:
                    return original
                if self.reads == 2:
                    self.current = observed_replacement
                    return observed_replacement
                current = self.current
                read = self.reads
            if read == 3:
                fresh_snapshot.set()
                assert allow_fresh_read.wait(2)
            return current

        def save_plan(self, candidate: object) -> None:
            with self._lock:
                self.current = candidate

    runtime = Runtime()
    service = object.__new__(NamiSyncService)
    service._runtime = runtime
    service._lock = Lock()
    service._plan_selections = {}
    service._lifecycle = TaskLifecycle()
    service._closed = False
    _publish_session(
        service._lifecycle,
        f"{31_102:032x}",
        kind="plan",
        request_id=request_id,
    )
    selection_code = service._selection_state.__func__.__code__
    replacement_read = Event()
    allow_retry = Event()
    failures: list[BaseException] = []
    responses: list[object] = []

    def trace_replacement_gap(frame, event, _arg):
        if (
            event == "line"
            and frame.f_code is selection_code
            and frame.f_locals.get("artifact") is original
            and frame.f_locals.get("live_artifact") is observed_replacement
        ):
            replacement_read.set()
            assert allow_retry.wait(2)
        return trace_replacement_gap

    def preview() -> None:
        sys.settrace(trace_replacement_gap)
        try:
            responses.append(service.preview_selection(request_id))
        except BaseException as error:
            failures.append(error)
        finally:
            sys.settrace(None)

    reader = Thread(target=preview)
    reader.start()
    assert replacement_read.wait(2)

    service.save_plan(first_successor)
    first_successor_state = service._plan_selections[request_id]

    allow_retry.set()
    assert fresh_snapshot.wait(2)

    service.save_plan(final_successor)
    final_successor_state = service._plan_selections[request_id]
    assert final_successor_state is not first_successor_state

    allow_fresh_read.set()
    reader.join(2)

    assert not reader.is_alive()
    assert failures == []
    assert len(responses) == 1
    assert runtime.current is final_successor
    assert service._plan_selections[request_id] is final_successor_state
