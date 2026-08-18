from __future__ import annotations

import ast
import io
import json
from collections import deque
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from threading import Event, Lock, Thread
from unittest.mock import Mock

import pytest

import namisync.interfaces.cli as cli_module
import namisync.interfaces.service as service_module
from namisync.core.events import (
    Envelope,
    Gap,
    ItemOutcome,
    PhaseChanged,
    SCHEMA_VERSION,
    Terminal,
)
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.integrity import IntegrityOutcome, IntegrityResult
from namisync.core.models import VolumeId
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
from namisync.workflows import InventoryRequest, LocalWorkflowRuntime
from namisync.workflows.runtime import HISTORY_WRITER_RETRY_TIMEOUT_SECONDS
from namisync.workflows.inventory import (
    IntegrityRequest,
    LocationBinding,
    VolumeResolution,
    VolumeResolutionRequired,
    VolumeResolutionState,
)
from namisync.workflows.views import operation_result_view

from _db_fixtures import FakeClock, NOW, operation, plan


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
        SessionId("recovery-session"),
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
                    SCHEMA_VERSION,
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


def test_history_service_ends_a_fresh_traversal_ahead_of_durability(
    tmp_path: Path,
) -> None:
    history = tmp_path / "history.db"
    ledger = tmp_path / "ledger.db"
    record = SessionRecord(
        SessionId("recovery-ahead-session"),
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
                SCHEMA_VERSION,
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
    record = _record("receipt-session")
    oversized = ItemOutcome(
        "receipt-item",
        "copy",
        "large.bin",
        Outcome.SUCCEEDED,
        detail={"message": "x" * 2_000},
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
                    SCHEMA_VERSION,
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
    assert page.events[0].session_id == "receipt-session"
    assert page.events[0].schema_version == SCHEMA_VERSION
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
        SessionId("incomplete-session"),
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
                SCHEMA_VERSION,
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
                        "blocked",
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
                        "selected-noop",
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
                        "deselected-noop",
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
        SessionId(run_token),
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
                    SCHEMA_VERSION,
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
