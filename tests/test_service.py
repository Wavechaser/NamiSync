from __future__ import annotations

import ast
import gc
import io
import json
from hashlib import blake2b
from collections import deque
from dataclasses import asdict
from pathlib import Path
import threading
from types import SimpleNamespace
from threading import Event, Lock, Thread
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
    InventoryDetailsView,
    InventoryRowView,
    LocationResolutionError,
    LocationResolutionView,
    NamiSyncService,
    PreservationSettingsView,
    ResultClassificationView,
    SemanticSettingsView,
    SessionEventView,
    SessionObserver,
    SessionRecordView,
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
from namisync.workflows.views import operation_result_view

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
    observation = observer._observations[session_id]

    with pytest.raises(TimeoutError) as raised:
        observer.close()
    assert str(raised.value) == "session observers did not stop"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert observer._observations[session_id] is observation

    release_sink.set()
    assert observation.done.wait(0.5)
    observer.close()
    observer.close()
    assert observer._observations == {}


@pytest.mark.parametrize("cleanup", ("close", "rollback", "unsubscribe"))
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
    rollback = None
    if cleanup == "rollback":
        rollback = observer.adopt(
            session_id,
            lambda _update: None,
            pending_streams.pop(),
        )
    else:
        observer.observe(session_id, lambda _update: None)
    observation = observer._observations[session_id]
    stream_reference = ref(observation.stream)
    assert observation.stream.entered.wait(0.5)
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
        elif cleanup == "rollback":
            assert rollback is not None
            rollback()
        else:
            observer.unsubscribe(session_id)

    assert str(raised.value) == expected_message
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert observer._observations == {}
    del observation
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert stream_reference() is None
    if cleanup == "rollback":
        assert rollback is not None
        rollback()
        assert join_attempts == 1
    elif cleanup == "unsubscribe":
        observer.unsubscribe(session_id)
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
    assert tuple(observer._observations) == (live_id,)
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert stopped_reference() is None

    release_live_sink.set()
    observer.close()
    assert observer._observations == {}


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
        assert observer._observations[session_id].stream is current
        assert not current.closed
    finally:
        observer.close()


@pytest.mark.parametrize("stop_method", ("unsubscribe", "close"))
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
            if stop_method == "unsubscribe":
                observer.unsubscribe(session_id)
            else:
                observer.close()
        except Exception as error:
            close_errors.append(error)
        finally:
            stopped.set()

    closer = Thread(target=stop)
    observer.observe(session_id, lambda _update: None)
    observation = observer._observations[session_id]
    try:
        assert subscribed.wait(0.5)
        if blocked_stage == "retire":
            assert first_closed.wait(0.5)
            assert observation.stream is replacement
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
    assert observation.done.is_set()
    assert not observation.failed
    assert observer._observations == {}


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


@pytest.mark.parametrize("cleanup", ("unsubscribe", "close"))
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
    observation = observer._observations[session_id]
    assert observation.done.wait(0.5)
    assert observation.thread is not None
    observation.thread.join(0.5)
    assert not observation.thread.is_alive()
    assert observation.failed
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

    if cleanup == "unsubscribe":
        observer.unsubscribe(session_id)
    else:
        observer.close()
    assert observer._observations == {}
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
    observation = observer._observations[session_id]
    assert observation.done.wait(0.5)
    assert observation.thread is not None
    observation.thread.join(0.5)
    assert not observation.thread.is_alive()
    assert observation.failed
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
    observations = tuple(observer._observations.values())

    with pytest.raises(RuntimeError) as raised:
        observer.close()

    assert str(raised.value) == "session observer cleanup failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert all(stream.closed for stream in streams.values())
    assert all(
        observation.thread is not None and not observation.thread.is_alive()
        for observation in observations
    )
    assert observer._observations == {}
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert excepthook_calls == []
    observer.close()


def test_observer_close_failure_traceback_does_not_own_retired_observations(
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
    assert observer._observations == {}
    assert excepthook_calls == []
    observer.close()


@pytest.mark.parametrize("cleanup", ("unsubscribe", "rollback"))
def test_observer_single_cleanup_retires_after_private_close_base_exception(
    cleanup: str,
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

    stream = Stream(cleanup)

    class Dispatcher:
        def get(self, requested: str) -> SessionRecord:
            return _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            return stream

    observer = SessionObserver(Dispatcher())
    if cleanup == "unsubscribe":
        observer.observe(session_id, lambda _update: None)
        action = lambda: observer.unsubscribe(session_id)
    else:
        action = observer.adopt(session_id, lambda _update: None, stream)
    assert stream.entered.wait(0.5)
    observation = observer._observations[session_id]

    with pytest.raises(RuntimeError) as raised:
        action()

    assert str(raised.value) == "session observer cleanup failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert stream.closed
    assert observation.thread is not None
    assert not observation.thread.is_alive()
    assert observer._observations == {}
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert excepthook_calls == []
    observer.close()


def test_sink_can_unsubscribe_itself_without_self_join_or_deadlock() -> None:
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
    returned = Event()

    def receive(_update) -> None:
        observer.unsubscribe(session_id)
        returned.set()

    observer.observe(session_id, receive)

    assert returned.wait(0.5)
    assert stream.closed
    observer.close()


def test_adopt_rollback_is_idempotent_and_cannot_remove_replacement() -> None:
    first_stream = _BlockingStream("first-generation")
    second_stream = _BlockingStream("second-generation")

    class Dispatcher:
        pass

    observer = SessionObserver(Dispatcher())
    first_rollback = observer.adopt(
        "same-session",
        lambda _update: None,
        first_stream,
    )
    assert first_stream.entered.wait(0.5)
    first_rollback()

    second_rollback = observer.adopt(
        "same-session",
        lambda _update: None,
        second_stream,
    )
    assert second_stream.entered.wait(0.5)
    replacement = observer._observations["same-session"]

    first_rollback()

    assert observer._observations["same-session"] is replacement
    assert not second_stream.closed
    second_rollback()
    assert observer._observations == {}
    observer.close()


def test_reobserve_replaces_stream_from_exact_positive_sequence() -> None:
    first_stream = _BlockingStream("initial")
    replacement_stream = _BlockingStream("replacement")

    class Dispatcher:
        def __init__(self) -> None:
            self.subscribe_calls: list[int | None] = []

        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            del session_id
            self.subscribe_calls.append(from_seq)
            return (
                first_stream
                if len(self.subscribe_calls) == 1
                else replacement_stream
            )

    dispatcher = Dispatcher()
    observer = SessionObserver(dispatcher)
    observer.observe("recovering", lambda _update: None)
    assert first_stream.entered.wait(0.5)

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
    retained = observer._observations["retained"]

    with pytest.raises(ValueError, match="positive integer"):
        observer.reobserve("retained", lambda _update: None, 0)

    assert observer._observations["retained"] is retained
    assert not stream.closed

    with pytest.raises(TypeError, match="callable"):
        observer.reobserve("retained", object(), 1)

    assert observer._observations["retained"] is retained
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
    assert observer._observations == {}
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
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
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
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False
    service._detail_owners_by_session = {
        "running-session": ("inventory", "request"),
    }

    incomplete = service.close(timeout=0)
    assert not incomplete.complete
    assert log == ["observer", "dispatcher"]
    assert tuple(service._runtime.inventory) == ("request",)
    assert service._detail_owners_by_session == {
        "running-session": ("inventory", "request"),
    }
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
    assert service._detail_owners_by_session == {}


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
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
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
    warning = ScanWarning(
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


def test_session_close_retires_only_its_exact_runtime_details() -> None:
    inventory_details = object()
    unrelated_details = object()
    events: list[tuple[str, str]] = []

    class Observer:
        def unsubscribe(self, session_id: str) -> None:
            events.append(("unsubscribe", session_id))

    class Dispatcher:
        closing = False

        def close(self, session_id: str) -> None:
            self.closing = True
            events.append(("dispatcher", session_id))
            self.closing = False

    dispatcher = Dispatcher()

    class Runtime:
        inventory = {
            "owned-request": inventory_details,
            "unrelated-request": unrelated_details,
        }

        def get_inventory_details(self, request_id: str):
            return self.inventory[request_id]

        def drop_inventory_details(self, request_id: str) -> None:
            assert not dispatcher.closing
            assert service._lock.acquire(blocking=False)
            service._lock.release()
            assert service._session_receipt_lifecycle.acquire(blocking=False)
            service._session_receipt_lifecycle.release()
            events.append(("drop", request_id))
            self.inventory.pop(request_id, None)

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()
    service._dispatcher = dispatcher
    service._observer = Observer()
    service._lock = Lock()
    service._session_receipt_lifecycle = Lock()
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._detail_owners_by_session = {
        "owned-session": ("inventory", "owned-request"),
        "unrelated-session": ("inventory", "unrelated-request"),
    }

    assert service._runtime.get_inventory_details("owned-request") is inventory_details
    service.close_session("owned-session")

    assert events == [
        ("unsubscribe", "owned-session"),
        ("dispatcher", "owned-session"),
        ("drop", "owned-request"),
    ]
    assert service._runtime.inventory == {
        "unrelated-request": unrelated_details,
    }
    assert service._detail_owners_by_session == {
        "unrelated-session": ("inventory", "unrelated-request"),
    }


def test_failed_session_close_preserves_detail_owner_for_retry() -> None:
    attempts = 0

    class Observer:
        def unsubscribe(self, session_id: str) -> None:
            pass

    class Dispatcher:
        def close(self, session_id: str) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise TimeoutError(
                    "session worker retirement is pending; cleanup did not start"
                )

    class Runtime:
        def __init__(self) -> None:
            self.execution = {"run": object()}

        def drop_execution_details(self, run_id: str) -> None:
            self.execution.pop(run_id, None)

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()
    service._dispatcher = Dispatcher()
    service._observer = Observer()
    service._lock = Lock()
    service._session_receipt_lifecycle = Lock()
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._detail_owners_by_session = {
        "session": ("execution", "run"),
    }

    with pytest.raises(TimeoutError, match="worker retirement"):
        service.close_session("session")
    assert tuple(service._runtime.execution) == ("run",)
    assert service._detail_owners_by_session == {
        "session": ("execution", "run"),
    }

    service.close_session("session")

    assert service._runtime.execution == {}
    assert service._detail_owners_by_session == {}


def test_blocked_session_retirement_keeps_details_until_close_returns() -> None:
    close_entered = Event()
    release_close = Event()
    close_done = Event()

    class Observer:
        def unsubscribe(self, session_id: str) -> None:
            pass

    class Dispatcher:
        def close(self, session_id: str) -> None:
            close_entered.set()
            assert release_close.wait(2)

    class Runtime:
        def __init__(self) -> None:
            self.inventory = {"request": object()}

        def get_inventory_details(self, request_id: str):
            return self.inventory[request_id]

        def drop_inventory_details(self, request_id: str) -> None:
            self.inventory.pop(request_id, None)

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()
    service._dispatcher = Dispatcher()
    service._observer = Observer()
    service._lock = Lock()
    service._session_receipt_lifecycle = Lock()
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._detail_owners_by_session = {
        "session": ("inventory", "request"),
    }

    def close_session() -> None:
        service.close_session("session")
        close_done.set()

    closer = Thread(target=close_session)
    closer.start()
    assert close_entered.wait(1)
    assert service._runtime.get_inventory_details("request") is not None
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
    service._session_receipt_lifecycle = Lock()
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._visibility_receipts = {}
    service._detail_owners_by_session = {
        "session": ("inventory", "request"),
    }
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False
    service._observer_closed = False

    with pytest.raises(RuntimeError, match="detail owner still closing"):
        service.close()
    assert tuple(service._runtime.inventory) == ("request",)
    assert service._detail_owners_by_session == {
        "session": ("inventory", "request"),
    }

    assert service.close().complete
    assert service._runtime.inventory == {}
    assert service._detail_owners_by_session == {}


def _detail_lifecycle_service(runtime, dispatcher) -> NamiSyncService:
    service = object.__new__(NamiSyncService)
    service._runtime = runtime
    service._dispatcher = dispatcher
    service._observer = SimpleNamespace(close=lambda: None)
    service._lock = Lock()
    service._close_lock = Lock()
    service._session_receipt_lifecycle = Lock()
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._visibility_receipts = {}
    service._detail_owners_by_session = {}
    service._runtime_detail_retirement_started = False
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False
    service._observer_closed = False
    return service


def test_detail_owner_attachment_rolls_back_a_failed_publication() -> None:
    observed: list[object] = []

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            assert service._lock.acquire(blocking=False)
            service._lock.release()
            assert service._session_receipt_lifecycle.acquire(blocking=False)
            service._session_receipt_lifecycle.release()
            assert attach is not None
            stream = _SequenceStream()
            rollback = attach("session", stream)
            assert stream.closed
            observed.append(service._detail_owners_by_session["session"])
            rollback()
            raise RuntimeError("publication failed")

    service = _detail_lifecycle_service(SimpleNamespace(), Dispatcher())

    with pytest.raises(RuntimeError, match="publication failed"):
        service.start_inventory(root_path=r"F:\library")

    assert len(observed) == 1
    assert service._detail_owners_by_session == {}


def test_detail_owner_attachment_rechecks_service_lifecycle() -> None:
    stream = _SequenceStream()

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            assert attach is not None
            service._closed = True
            attach("session", stream)
            raise AssertionError("closed service attachment returned")

    service = _detail_lifecycle_service(SimpleNamespace(), Dispatcher())

    with pytest.raises(RuntimeError, match="service is closed"):
        service.start_inventory(root_path=r"F:\library")

    assert stream.closed
    assert service._detail_owners_by_session == {}


def test_detail_owner_rollback_preserves_a_replacement_binding() -> None:
    replacement: tuple[str, str] | None = None

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            nonlocal replacement
            assert attach is not None
            rollback = attach("session", _SequenceStream())
            original = service._detail_owners_by_session["session"]
            replacement = tuple(list(original))
            assert replacement == original
            assert replacement is not original
            service._detail_owners_by_session["session"] = replacement
            rollback()
            raise RuntimeError("superseded publication failed")

    service = _detail_lifecycle_service(SimpleNamespace(), Dispatcher())

    with pytest.raises(RuntimeError, match="superseded publication failed"):
        service.start_inventory(root_path=r"F:\library")

    assert replacement is not None
    assert service._detail_owners_by_session["session"] is replacement


@pytest.mark.parametrize("runtime_close_fails", [False, True])
def test_detail_owner_attachment_precedes_post_admission_shutdown(
    runtime_close_fails: bool,
) -> None:
    attached = Event()
    release_submit = Event()
    start_results: list[object] = []
    start_errors: list[BaseException] = []
    close_attempts = 0

    class Runtime:
        def __init__(self) -> None:
            self.details: dict[str, object] = {}

        def close(self) -> None:
            nonlocal close_attempts
            close_attempts += 1
            assert len(service._detail_owners_by_session) == 1
            session_id, owner = next(
                iter(service._detail_owners_by_session.items())
            )
            assert session_id == "session"
            assert owner[0] == "inventory"
            assert owner[1] in self.details
            if runtime_close_fails and close_attempts == 1:
                raise RuntimeError("runtime close failed")
            self.details.clear()

    runtime = Runtime()

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            assert attach is not None
            runtime.details[request.request_id] = object()
            stream = _SequenceStream()
            rollback = attach("session", stream)
            assert callable(rollback)
            assert stream.closed
            attached.set()
            assert release_submit.wait(2)
            return "session"

        def shutdown(self, timeout: float):
            assert attached.is_set()
            return SimpleNamespace(
                complete=True,
                unfinished=(),
                custody_released=True,
            )

    service = _detail_lifecycle_service(runtime, Dispatcher())

    def start() -> None:
        try:
            start_results.append(
                service.start_inventory(root_path=r"F:\library")
            )
        except BaseException as error:
            start_errors.append(error)

    starter = Thread(target=start)
    starter.start()
    assert attached.wait(1)

    if runtime_close_fails:
        with pytest.raises(RuntimeError, match="runtime close failed"):
            service.close()
        assert len(service._detail_owners_by_session) == 1
        assert len(runtime.details) == 1
    else:
        assert service.close().complete
        assert service._detail_owners_by_session == {}
        assert runtime.details == {}

    release_submit.set()
    starter.join(2)
    assert not starter.is_alive()
    assert start_errors == []
    assert len(start_results) == 1

    if runtime_close_fails:
        assert service.close().complete
        assert service._detail_owners_by_session == {}
        assert runtime.details == {}
        assert close_attempts == 2
    else:
        assert close_attempts == 1


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
        def submit(self, kind: str, request: object, *, attach=None):
            assert kind == "sync-execution"
            session_id = f"session-{len(calls)}"
            assert attach is not None
            attach(session_id, _SequenceStream())
            return session_id

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
    assert service._detail_owners_by_session == {
        "session-1": ("execution", "run-default"),
        "session-2": ("execution", "run-verified"),
    }


def test_location_commands_submit_exact_typed_workflow_requests() -> None:
    submitted: list[tuple[str, object]] = []

    class Dispatcher:
        def submit(self, kind: str, request: object, *, attach=None) -> str:
            submitted.append((kind, request))
            session_id = f"session-{kind}"
            assert attach is not None
            attach(session_id, _SequenceStream())
            return session_id

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
    assert service._detail_owners_by_session == {
        session.session_id: ("inventory", session.request_id)
        for session in (inventory, baseline, verify, rebaseline)
    }


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

    with pytest.raises(LocationResolutionError) as raised:
        service.start_verify(location_id=7)

    assert raised.value.resolution.selected_mount == "F:\\"
