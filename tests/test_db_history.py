from __future__ import annotations

from contextlib import closing, contextmanager
import sqlite3
from dataclasses import fields, replace
from datetime import timedelta
import json
from pathlib import Path
from weakref import ref

import pytest

import namisync.core.events as event_module
import namisync.db.history as history_module
from namisync.core.event_v5 import validate_and_encode_event_v5_envelope
from namisync.core.events import (
    CORE_EVENT_SCHEMA_VERSION,
    Envelope,
    Gap,
    ItemOutcome,
    PhaseChanged,
    Progress,
    StateChanged,
    envelope_from_dict,
    envelope_to_dict,
)
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.execution import (
    ItemRecordingReason,
    TaskRecordingIssue,
    TaskRecordingIssueReason,
)
from namisync.core.integrity import (
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
    ReadStrategy,
    RecordDisposition,
)
from namisync.core.session import (
    Disposition,
    FailureDetail,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    ResultItem,
    SessionId,
    SessionRecord,
    SessionState,
)
from namisync.core.review import ReviewFactLimitExceeded
from namisync.core.scalars import MAX_SAFE_INTEGER
from namisync.db.connections import (
    QUERY_SUBJECT_BATCH_SIZE,
    connect_history_reader,
    connect_history_writer,
)
from namisync.db.history import (
    MAX_HISTORY_ERROR_MESSAGE_BYTES,
    MAX_HISTORY_ERROR_TYPE_BYTES,
    MAX_HISTORY_PAGE_SIZE,
    MAX_HISTORY_PHASE_NAME_BYTES,
    MAX_HISTORY_PHASES,
    HistoryClassificationAggregate,
    HistoryContext,
    HistoryIntegrityError,
    HistoryRepository,
    HistoryStore,
    HistoryWindowPolicy,
)
from namisync.db.writer import RecordingError, TokenConflictError
from namisync.workflows.views import operation_result_view

from _db_fixtures import FakeClock, NOW
from _event_v5_fixtures import SESSION_ID, envelope as event_v5_envelope


def _raise_private_history_failure(errors, retained, message: str) -> None:
    class PrivateGraph:
        pass

    graph = PrivateGraph()
    retained.append(ref(graph))
    try:
        cause = LookupError("private history cause")
        cause.graph = graph
        raise cause
    except LookupError as cause:
        error = RecordingError(message)
        errors.append(error)
        raise error from cause


def _record(
    session_id: str = "11111111111111111111111111111111",
    *,
    kind: str = "sync",
) -> SessionRecord:
    return SessionRecord(
        SessionId(session_id),
        kind,
        SessionState.PENDING,
        (),
        b"opaque",
        True,
        1,
        NOW,
    )


def _envelope(record: SessionRecord, seq: int, body: object) -> Envelope:
    return Envelope(
        record.session_id,
        seq,
        NOW,
        CORE_EVENT_SCHEMA_VERSION,
        body,
    )


def _item(seq: int, outcome: Outcome = Outcome.SUCCEEDED) -> ItemOutcome:
    return ItemOutcome(
        f"{seq:032x}",
        "copy",
        f"{seq}.bin",
        outcome,
        detail={"message": str(seq)},
    )


@contextmanager
def _without_history_triggers(connection: sqlite3.Connection, *names: str):
    # Corrupt data independently of topology so readback integrity assertions
    # still run behind the exact-schema admission boundary.
    definitions = [
        connection.execute(
            "SELECT sql FROM sqlite_schema WHERE type = 'trigger' AND name = ?", (name,),
        ).fetchone()[0]
        for name in names
    ]
    for name in names:
        connection.execute(f'DROP TRIGGER "{name}"')
    try:
        yield
    finally:
        for definition in definitions:
            connection.execute(definition)


def _insert_history_event(
    connection: sqlite3.Connection,
    run_id: int,
    envelope: Envelope,
    *,
    item_order: int | None = None,
) -> None:
    encoded = history_module._json_bytes(envelope_to_dict(envelope))
    payload_hash = history_module.hashlib.sha256(encoded).digest()
    item_projection = history_module._item_projection(envelope.body)
    projection = history_module._item_column_projection(item_projection)
    item_identity_hash = (
        None
        if projection is None
        else history_module._item_identity_hash(envelope.body)
    )
    item_payload_hash = (
        None
        if projection is None
        else history_module._hash(
            item_projection
        )
    )
    receipt_hash = history_module._receipt_hash(
        event_seq=envelope.seq,
        event_at=history_module.encode_utc(envelope.at),
        schema_version=envelope.schema_version,
        body_type=type(envelope.body).__name__,
        disposition=history_module.HistoryEventDisposition.RECORDED,
        payload_hash=payload_hash,
        item_identity_hash=item_identity_hash,
        item_payload_hash=item_payload_hash,
        item_order=item_order,
    )
    connection.execute(
        """INSERT INTO history_events(
               run_id, event_seq, event_at, schema_version, body_type,
               event_disposition, envelope_json, payload_hash, receipt_hash,
               item_identity_hash, item_payload_hash, duplicate_of_seq,
               rejection_reason, item_order,
               item_type, phase, item_id, kind, path, result, reason,
               recording, recording_reason, recording_detail,
               detail_omitted_count
           ) VALUES (?, ?, ?, ?, ?, 'recorded', ?, ?, ?, ?, ?, NULL, NULL, ?,
                     ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            envelope.seq,
            history_module.encode_utc(envelope.at),
            envelope.schema_version,
            type(envelope.body).__name__,
            encoded.decode("utf-8"),
            payload_hash,
            receipt_hash,
            item_identity_hash,
            item_payload_hash,
            item_order,
            None if projection is None else projection["item_type"],
            None if projection is None else projection["phase"],
            None if projection is None else projection["item_id"],
            None if projection is None else projection["kind"],
            None if projection is None else projection["path"],
            None if projection is None else projection["result"],
            None if projection is None else projection["reason"],
            None if projection is None else projection["recording"],
            None if projection is None else projection["recording_reason"],
            None if projection is None else projection["recording_detail"],
            None if projection is None else projection["detail_omitted_count"],
        ),
    )


@pytest.mark.parametrize(
    "arguments",
    (
        (1, "host-1", {}),
        ("run-1", 1, {}),
        ("run-1", "host-1", {"subject_id": 1}),
    ),
)
def test_history_context_rejects_non_string_identifiers(arguments: tuple) -> None:
    run_token, host_key, options = arguments
    with pytest.raises(TypeError):
        HistoryContext(run_token, host_key, **options)


def test_history_window_policy_freezes_balanced_defaults_and_rejects_bad_bounds() -> None:
    assert HistoryWindowPolicy() == HistoryWindowPolicy(
        max_events=256,
        max_bytes=1_048_576,
        max_event_bytes=1_048_576,
        max_age_seconds=1.0,
    )
    for values in (
        {"max_events": 0},
        {"max_bytes": 0},
        {"max_event_bytes": 0},
        {"max_bytes": 10, "max_event_bytes": 11},
        {"max_age_seconds": 0},
        {"max_age_seconds": float("nan")},
        {"max_age_seconds": float("inf")},
    ):
        with pytest.raises(ValueError):
            HistoryWindowPolicy(**values)


@pytest.mark.parametrize(
    ("count", "batch_size"),
    tuple(
        (count, QUERY_SUBJECT_BATCH_SIZE)
        for count in (0, 1, 399, 400, 401, 801)
    )
    + ((801, 37),),
)
def test_canonical_item_lookup_batches_only_relevant_history_subjects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    batch_size: int,
) -> None:
    monkeypatch.setattr(history_module, "QUERY_SUBJECT_BATCH_SIZE", batch_size)
    record = _record()
    context = HistoryContext("run-batched-canonical", "host-1")
    items = tuple(_item(index) for index in range(1, count + 1))

    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        if items:
            for index, item in enumerate(items, 1):
                observer.on_event(_envelope(record, index, item))
        else:
            observer.on_event(_envelope(record, 1, PhaseChanged("execute")))
        observer.flush()

        if items:
            other_record = _record("22222222222222222222222222222222")
            other = store.observer(
                other_record,
                HistoryContext("run-irrelevant-canonical", "host-2"),
            )
            other.on_event(
                _envelope(other_record, 1, _item(1, Outcome.FAILED))
            )
            other.flush()

        connection = connect_history_reader(store.path)
        calls: list[tuple[str, tuple[object, ...]]] = []

        class RecordingConnection:
            def execute(
                self, statement: str, parameters: tuple[object, ...] = ()
            ) -> sqlite3.Cursor:
                calls.append((statement, tuple(parameters)))
                return connection.execute(statement, parameters)

        try:
            run_id = int(
                connection.execute(
                    "SELECT id FROM history_runs WHERE run_token = ?",
                    (context.run_token,),
                ).fetchone()[0]
            )
            pending = tuple(
                history_module._PendingEvent(
                    event_seq=count + index,
                    event_at=NOW,
                    schema_version=CORE_EVENT_SCHEMA_VERSION,
                    body_type="ItemOutcome",
                    envelope=None,
                    envelope_json=None,
                    encoded_size=0,
                    payload_hash=bytes(32),
                    item_identity_hash=history_module._item_identity_hash(item),
                    item_payload_hash=history_module._hash(
                        history_module.result_item_to_dict(item)
                    ),
                )
                for index, item in enumerate(items, 1)
            )
            canonical = history_module._canonical_items_for_window(
                RecordingConnection(), run_id, max(1, count), pending
            )
        finally:
            connection.close()

    lookup_calls = [
        parameters
        for statement, parameters in calls
        if "INDEXED BY history_events_run_identity_hash_idx" in statement
    ]
    assert bool(lookup_calls) is bool(count)
    assert all(len(parameters) <= batch_size + 2 for parameters in lookup_calls)
    assert len(canonical.by_identity_hash) == count
    assert canonical.by_identity == {
        ("operation", item.item_id): (
            index,
            history_module._hash(history_module.result_item_to_dict(item)),
        )
        for index, item in enumerate(items, 1)
    }


def test_history_finalization_round_trips_summary_items_events_and_phases(
    tmp_path: Path,
) -> None:
    record = _record()
    context = HistoryContext(
        "run-1", "host-1", source_context="source", target_context="target"
    )
    item = ItemOutcome(
        "11111111111111111111111111111111",
        "copy",
        "a.txt",
        Outcome.SUCCEEDED,
        detail={"message": "7"},
        recording=RecordingStatus.DEGRADED,
        recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
    )
    phases = (PhaseResult("execute", PhaseStatus.COMPLETED, 1, 1, 7, 7),)
    result = OperationResult(
        SessionState.COMPLETED,
        recording=RecordingStatus.DEGRADED,
        audit=RecordingStatus.OK,
        disposition=Disposition.RAN,
        items=(item,),
        phases=phases,
        bytes_done=7,
        bytes_total=7,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, StateChanged(SessionState.RUNNING)))
        observer.on_event(_envelope(record, 2, item))
        observer.on_event(_envelope(record, 2, item))
        observer.finalize(result)

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")
            items = repository.get_item_page("run-1")
            events = repository.get_event_page("run-1")

    assert summary.finalized
    assert summary.current_state is SessionState.COMPLETED
    assert summary.filesystem_status is SessionState.COMPLETED
    assert summary.recording is RecordingStatus.DEGRADED
    assert summary.audit is RecordingStatus.OK
    assert summary.started_at == NOW
    assert summary.ended_at == NOW
    assert summary.last_committed_seq == 2
    assert summary.item_count == 1
    assert summary.succeeded_count == 1
    assert summary.phases[0].phase == phases[0]
    assert summary.classification == HistoryClassificationAggregate(
        operation_results=frozenset({"succeeded"}),
        selected_operation_count=1,
        selected_other_operation_count=1,
        integrity_results=frozenset(),
        verify_phase_baseline=False,
    )
    assert items.through_order == 1
    assert items.items[0].item_order == 1
    assert items.items[0].event_seq == 2
    assert items.items[0].item == item
    assert [event.event_seq for event in events.events] == [1, 2]
    assert events.events[1].envelope.body == item


@pytest.mark.parametrize(
    "item",
    (
        ItemOutcome(
            "1" * 32,
            "copy",
            "full-detail.bin",
            Outcome.SUCCEEDED,
            detail={
                "message": "copied",
                "published_path": "full-detail.bin",
                "continued": True,
            },
        ),
        ItemOutcome(
            "2" * 32,
            "noop",
            "reason-none.bin",
            Outcome.SKIPPED,
            reason=None,
        ),
        ItemOutcome(
            "3" * 32,
            "copy",
            "recording-failure.bin",
            Outcome.SUCCEEDED,
            detail={"message": "filesystem mutation completed"},
            recording=RecordingStatus.DEGRADED,
            recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
            recording_detail="ledger write unavailable",
            detail_omitted_count=2,
        ),
        IntegrityOutcome(
            item_id="integrity-reason",
            row_id="row-1",
            location_id="location-1",
            path="integrity-reason.bin",
            result=IntegrityResult.MISMATCHED,
            reason=IntegrityReason.HASH_MISMATCH,
            detail="digest differs",
            read_strategy=ReadStrategy.WINDOWS_UNBUFFERED,
        ),
        IntegrityOutcome(
            item_id="integrity-recording-failure",
            row_id="row-2",
            location_id="location-2",
            path="integrity-recording-failure.bin",
            result=IntegrityResult.VERIFIED,
            detail="content matched before recording",
            recording=RecordingStatus.DEGRADED,
            record_disposition=RecordDisposition.CONFLICT,
            detail_omitted_count=3,
        ),
    ),
    ids=(
        "operation-full-detail",
        "operation-reason-none",
        "operation-recording-failure",
        "integrity-reason",
        "integrity-recording-failure",
    ),
)
def test_local_item_projection_reuse_preserves_hashes_and_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    item: ItemOutcome | IntegrityOutcome,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    envelope = _envelope(record, 1, item)
    expected_envelope = envelope_to_dict(envelope)
    expected_body = event_module.result_item_to_dict(item)
    expected_envelope_bytes = validate_and_encode_event_v5_envelope(
        expected_envelope
    )

    def canonical_hash(value: object) -> bytes:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return history_module.hashlib.sha256(encoded).digest()

    expected_item_hash = canonical_hash(expected_body)
    expected_identity_hash = canonical_hash(
        {
            "item_type": expected_body["item_type"],
            "item_id": expected_body["item_id"],
        }
    )
    expected_columns = {
        "item_type": expected_body["item_type"],
        "phase": expected_body["phase"],
        "item_id": expected_body["item_id"],
        "kind": expected_body["kind"],
        "path": expected_body["path"],
        "result": expected_body["result"],
        "reason": expected_body["reason"],
        "recording": expected_body["recording"],
        "recording_reason": expected_body.get("recording_reason"),
        "recording_detail": expected_body.get("recording_detail"),
        "detail_omitted_count": expected_body["detail_omitted_count"],
    }
    original_projection = event_module.result_item_to_dict
    projection_calls: list[ResultItem] = []

    def counted_projection(value: ResultItem) -> dict[str, object]:
        projection_calls.append(value)
        return original_projection(value)

    monkeypatch.setattr(event_module, "result_item_to_dict", counted_projection)
    monkeypatch.setattr(history_module, "result_item_to_dict", counted_projection)

    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext(f"run-local-projection-{item.item_id}", "host-1"),
        )
        observer.on_event(envelope)
        assert len(projection_calls) == 1
        assert original_projection(projection_calls[0]) == expected_body

        projection_calls.clear()
        observer.flush()
        assert len(projection_calls) == 1
        assert original_projection(projection_calls[0]) == expected_body

        with closing(connect_history_reader(path)) as connection:
            row = connection.execute(
                "SELECT * FROM history_events WHERE event_seq = 1"
            ).fetchone()
        assert str(row["envelope_json"]).encode("utf-8") == expected_envelope_bytes
        assert bytes(row["payload_hash"]) == history_module.hashlib.sha256(
            expected_envelope_bytes
        ).digest()
        assert bytes(row["item_identity_hash"]) == expected_identity_hash
        assert bytes(row["item_payload_hash"]) == expected_item_hash
        assert {
            key: row[key] for key in expected_columns
        } == expected_columns
        assert bytes(row["receipt_hash"]) == history_module._receipt_hash(
            event_seq=1,
            event_at=history_module.encode_utc(NOW),
            schema_version=CORE_EVENT_SCHEMA_VERSION,
            body_type=type(item).__name__,
            disposition=history_module.HistoryEventDisposition.RECORDED,
            payload_hash=bytes(row["payload_hash"]),
            item_identity_hash=expected_identity_hash,
            item_payload_hash=expected_item_hash,
            item_order=1,
        )

        projection_calls.clear()
        with HistoryRepository(path) as repository:
            page = repository.get_event_page(
                f"run-local-projection-{item.item_id}"
            )
        assert len(projection_calls) == 1
        assert original_projection(projection_calls[0]) == expected_body

    assert envelope_to_dict(page.events[0].envelope) == expected_envelope


def test_pending_history_shape_does_not_retain_item_projection() -> None:
    assert tuple(field.name for field in fields(history_module._PendingEvent)) == (
        "event_seq",
        "event_at",
        "schema_version",
        "body_type",
        "envelope",
        "envelope_json",
        "encoded_size",
        "payload_hash",
        "item_identity_hash",
        "item_payload_hash",
        "rejection_reason",
    )


def test_history_review_fact_columns_are_all_null_or_reconstruct_exact_truth(
    tmp_path: Path,
) -> None:
    record = _record()
    fact = ReviewFactLimitExceeded.plan_logical_bytes()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        store.observer(
            record,
            HistoryContext("run-default", "host-1"),
        ).finalize(OperationResult(SessionState.COMPLETED))
        store.observer(
            record,
            HistoryContext("run-refused", "host-1"),
        ).finalize(
            OperationResult(
                SessionState.REFUSED,
                disposition=Disposition.UNRUN,
                review_fact_limit=fact,
            )
        )
        connection = connect_history_reader(store.path)
        try:
            rows = {
                row["run_token"]: row
                for row in connection.execute(
                    """SELECT run_token, review_reason, review_tree_kind,
                              review_population, review_axis, review_row_limit,
                              review_byte_limit
                         FROM history_runs"""
                )
            }
        finally:
            connection.close()
        with HistoryRepository(store.path) as repository:
            default = repository.get_summary("run-default")
            refused = repository.get_summary("run-refused")

    assert tuple(rows["run-default"])[1:] == (None,) * 6
    assert tuple(rows["run-refused"])[1:] == (
        "review_fact_limit_exceeded",
        "plan",
        "domain",
        "logical-bytes",
        None,
        (1 << 63) - 1,
    )
    assert default.review_fact_limit is None
    assert refused.review_fact_limit == fact


def test_history_schema_rejects_a_partial_review_fact_group(tmp_path: Path) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        store.observer(
            record,
            HistoryContext("run-partial-review", "host-1"),
        ).finalize(OperationResult(SessionState.COMPLETED))
        connection = connect_history_writer(store.path)
        with closing(connection), _without_history_triggers(connection, "history_runs_finalized_update"):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    """UPDATE history_runs
                          SET review_reason = 'review_fact_limit_exceeded'
                        WHERE run_token = 'run-partial-review'"""
                )


def test_history_terminal_recording_witnesses_round_trip_exactly(
    tmp_path: Path,
) -> None:
    record = _record()
    item = ItemOutcome(
        "3" * 32,
        "copy",
        "recording.bin",
        Outcome.SUCCEEDED,
        recording=RecordingStatus.DEGRADED,
        recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
        detail_omitted_count=2,
    )
    issue = TaskRecordingIssue(
        TaskRecordingIssueReason.FINAL_FLUSH_FAILED,
        "flush failed",
    )
    result = OperationResult(
        SessionState.COMPLETED,
        recording=RecordingStatus.DEGRADED,
        items=(item,),
        recording_issues=(issue,),
        omitted_detail_count=3,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext("run-recording-witnesses", "host-1"),
        )
        observer.on_event(_envelope(record, 1, item))
        observer.finalize(result)
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-recording-witnesses")

    assert summary.recording is RecordingStatus.DEGRADED
    assert summary.recording_degraded_items == 1
    assert summary.recording_issues == (issue,)
    assert summary.omitted_detail_count == 5


@pytest.mark.parametrize(
    "tamper_sql",
    (
        "UPDATE history_runs SET recording_degraded_items = 0",
        "UPDATE history_runs SET recording_issues_json = '[]'",
        "UPDATE history_runs SET omitted_detail_count = omitted_detail_count + 1",
    ),
)
def test_terminal_hash_and_repeat_finalize_bind_recording_witnesses(
    tmp_path: Path,
    tamper_sql: str,
) -> None:
    record = _record()
    context = HistoryContext("run-recording-hash", "host-1")
    item = ItemOutcome(
        "4" * 32,
        "copy",
        "recording.bin",
        Outcome.SUCCEEDED,
        recording=RecordingStatus.DEGRADED,
        recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
    )
    result = OperationResult(
        SessionState.COMPLETED,
        recording=RecordingStatus.DEGRADED,
        items=(item,),
        recording_issues=(
            TaskRecordingIssue(
                TaskRecordingIssueReason.FINAL_FLUSH_FAILED,
                None,
            ),
        ),
        omitted_detail_count=1,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, item))
        observer.finalize(result)
        connection = connect_history_writer(store.path)
        with closing(connection), _without_history_triggers(connection, "history_runs_finalized_update"):
            connection.execute(tamper_sql)

        with HistoryRepository(store.path) as repository:
            with pytest.raises(HistoryIntegrityError, match="payload hash"):
                repository.get_summary("run-recording-hash")
        with pytest.raises(HistoryIntegrityError, match="payload hash"):
            observer.finalize(result)


def test_terminal_hash_binds_the_exact_review_fact_group(tmp_path: Path) -> None:
    record = _record()
    fact = ReviewFactLimitExceeded.plan_logical_bytes()
    result = OperationResult(
        SessionState.REFUSED,
        disposition=Disposition.UNRUN,
        review_fact_limit=fact,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext("run-review-hash", "host-1"),
        )
        observer.finalize(result)
        connection = connect_history_writer(store.path)
        with closing(connection), _without_history_triggers(connection, "history_runs_finalized_update"):
            connection.execute(
                """UPDATE history_runs
                      SET review_axis = 'retained-bytes',
                          review_byte_limit = 134217728
                    WHERE run_token = 'run-review-hash'"""
            )

        with HistoryRepository(store.path) as repository:
            with pytest.raises(HistoryIntegrityError, match="payload hash"):
                repository.get_summary("run-review-hash")
        with pytest.raises(HistoryIntegrityError, match="payload hash"):
            observer.finalize(result)


def test_presentation_omission_never_enters_history_truth(tmp_path: Path) -> None:
    record = _record()
    error = FailureDetail("E" * 600, "m" * 600)
    result = OperationResult(SessionState.FAILED, error=error)
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        store.observer(
            record,
            HistoryContext("run-presentation", "host-1"),
        ).finalize(result)
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-presentation")

    view = operation_result_view(result)
    assert summary.error_type == error.type_name
    assert summary.error_message == error.message
    assert summary.omitted_detail_count == 0
    assert view.error is None
    assert view.omitted_detail_count == 0
    assert view.presentation_omitted_detail_count == 1


def test_history_refuses_populated_lossy_progress(tmp_path: Path) -> None:
    record = _record()
    progress = Progress(
        "execute",
        0,
        1,
        4,
        8,
        "a.bin",
        item_id="op-1",
        item_type="operation",
        item_attempt_id="a" * 32,
        item_bytes_done=4,
        item_bytes_total=8,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))

        with pytest.raises(
            HistoryIntegrityError,
            match="history receives reliable preterminal events only",
        ):
            observer.on_event(_envelope(record, 1, progress))


def test_count_bound_flushes_complete_windows_and_exposes_incomplete_summary(
    tmp_path: Path,
) -> None:
    policy = HistoryWindowPolicy(max_events=2)
    record = _record()
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        assert observer.pending_event_count == 1
        observer.on_event(_envelope(record, 2, _item(2)))
        assert observer.pending_event_count == 0
        assert observer.pending_bytes == 0

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")
        assert not summary.finalized
        assert summary.last_committed_seq == 2
        assert summary.item_count == 2

        observer.on_event(_envelope(record, 3, _item(3)))
        with HistoryRepository(store.path) as repository:
            assert repository.get_summary("run-1").last_committed_seq == 2
        observer.flush()
        with HistoryRepository(store.path) as repository:
            assert repository.get_summary("run-1").last_committed_seq == 3


def test_byte_bound_flushes_before_an_incoming_event_would_exceed_it(
    tmp_path: Path,
) -> None:
    record = _record()
    first = _envelope(record, 1, _item(1))
    second = _envelope(record, 2, _item(2))
    sizes = [
        len(history_module._json_bytes(envelope_to_dict(event)))
        for event in (first, second)
    ]
    bound = max(sizes) + 1
    assert sum(sizes) > bound
    policy = HistoryWindowPolicy(
        max_events=256,
        max_bytes=bound,
        max_event_bytes=bound,
    )
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(first)
        observer.on_event(second)

        assert observer.pending_event_count == 1
        assert observer.pending_bytes == sizes[1]
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")
        assert summary.last_committed_seq == 1
        assert summary.item_count == 1


def test_oversized_single_event_degrades_without_violating_memory_bound(
    tmp_path: Path,
) -> None:
    record = _record()
    event = _envelope(record, 1, _item(1))
    size = len(history_module._json_bytes(envelope_to_dict(event)))
    policy = HistoryWindowPolicy(
        max_bytes=size - 1,
        max_event_bytes=size - 1,
    )
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        assert observer.on_event(event) is RecordingStatus.DEGRADED
        assert observer.pending_event_count == 0
        assert observer.pending_bytes == 0
        replay = store.observer(record, HistoryContext("run-1", "host-1"))
        assert replay.on_event(event) is RecordingStatus.DEGRADED
        conflict = store.observer(record, HistoryContext("run-1", "host-1"))
        with pytest.raises(HistoryIntegrityError, match="another payload"):
            conflict.on_event(_envelope(record, 1, _item(2)))
        later = _envelope(record, 2, PhaseChanged("execute"))
        assert observer.on_event(later) is RecordingStatus.OK
        assert (
            observer.finalize(OperationResult(SessionState.COMPLETED))
            is RecordingStatus.DEGRADED
        )
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")
            page = repository.get_event_page("run-1")

    assert summary.last_committed_seq == 2
    assert summary.item_count == 0
    assert summary.rejected_event_count == 1
    assert summary.audit is RecordingStatus.DEGRADED
    assert page.events[0].envelope is None
    assert page.events[0].rejection_reason == history_module.EVENT_TOO_LARGE
    assert page.events[1].envelope == later


def test_oversized_item_reuse_still_enforces_semantic_identity(
    tmp_path: Path,
) -> None:
    record = _record()
    original = _item(1)
    changed = replace(original, detail={"message": "x" * 2_000})
    policy = HistoryWindowPolicy(
        max_events=1,
        max_bytes=512,
        max_event_bytes=512,
    )
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-oversized-conflict", "host-1")
        )
        observer.on_event(_envelope(record, 1, original))

        with pytest.raises(HistoryIntegrityError, match="identity was reused"):
            observer.on_event(_envelope(record, 2, changed))

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-oversized-conflict")

    assert summary.item_count == 1
    assert summary.rejected_event_count == 0


def test_rejected_oversized_item_still_guards_later_identity_reuse(
    tmp_path: Path,
) -> None:
    record = _record()
    first = replace(_item(1), path=f"{'x' * 1_000}.bin")
    changed = _item(1, Outcome.FAILED)
    policy = HistoryWindowPolicy(
        max_events=1,
        max_bytes=512,
        max_event_bytes=512,
    )
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-rejected-conflict", "host-1")
        )
        assert (
            observer.on_event(_envelope(record, 1, first))
            is RecordingStatus.DEGRADED
        )
        with pytest.raises(HistoryIntegrityError, match="identity was reused"):
            observer.on_event(_envelope(record, 2, changed))

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-rejected-conflict")

    assert summary.item_count == 0
    assert summary.rejected_event_count == 1


def test_rejected_first_exact_reuse_is_a_bounded_noncounting_duplicate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    context = HistoryContext("run-rejected-repeat", "host-1")
    item = replace(_item(1), path=f"{'x' * 1_000}.bin")
    low_policy = HistoryWindowPolicy(
        max_events=1,
        max_bytes=512,
        max_event_bytes=512,
    )
    with HistoryStore(
        path,
        clock=FakeClock(),
        window_policy=low_policy,
    ) as store:
        observer = store.observer(record, context)
        for seq in range(1, 33):
            assert (
                observer.on_event(_envelope(record, seq, item))
                is RecordingStatus.DEGRADED
            )

    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, context)
        assert observer.on_event(_envelope(record, 33, item)) is RecordingStatus.OK
        assert (
            observer.finalize(OperationResult(SessionState.COMPLETED))
            is RecordingStatus.DEGRADED
        )
        with HistoryRepository(path) as repository:
            summary = repository.get_summary(context.run_token)
            events = repository.get_event_page(context.run_token)
            items = repository.get_item_page(context.run_token)

    assert summary.item_count == 0
    assert summary.duplicate_item_count == 1
    assert summary.rejected_event_count == 32
    assert items.items == ()
    assert events.events[0].duplicate_of_seq is None
    assert all(
        event.duplicate_of_seq == 1 for event in events.events[1:32]
    )
    assert (
        events.events[-1].disposition
        is history_module.HistoryEventDisposition.DUPLICATE
    )
    assert events.events[-1].duplicate_of_seq == 1


def test_duplicate_page_authenticates_a_linked_rejected_receipt(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    context = HistoryContext("run-rejected-link", "host-1")
    item = replace(_item(1), path=f"{'x' * 1_000}.bin")
    with HistoryStore(
        path,
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_bytes=512, max_event_bytes=512),
    ) as store:
        store.observer(record, context).on_event(_envelope(record, 1, item))
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 2, item))
        observer.flush()

    connection = connect_history_writer(path)
    with closing(connection), _without_history_triggers(connection, "history_events_append_only_update"):
        connection.execute(
            """UPDATE history_events
                  SET event_at = '2026-01-02T03:04:06.123456Z'
                WHERE event_seq = 1"""
        )

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="receipt hash"):
            repository.get_event_page(context.run_token, after_seq=1)


def test_oversized_exact_item_reuse_remains_a_contained_rejection(
    tmp_path: Path,
) -> None:
    record = _record()
    item = _item(1)
    canonical = _envelope(record, 9, item)
    oversized = _envelope(record, 10, item)
    bound = len(history_module._json_bytes(envelope_to_dict(canonical)))
    assert len(history_module._json_bytes(envelope_to_dict(oversized))) > bound
    policy = HistoryWindowPolicy(
        max_events=1,
        max_bytes=bound,
        max_event_bytes=bound,
    )
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-oversized-repeat", "host-1")
        )
        assert observer.on_event(canonical) is RecordingStatus.OK
        assert observer.on_event(oversized) is RecordingStatus.DEGRADED
        observer.finalize(OperationResult(SessionState.COMPLETED, items=(item,)))

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-oversized-repeat")
            events = repository.get_event_page("run-oversized-repeat")

    assert summary.item_count == 1
    assert summary.duplicate_item_count == 0
    assert summary.rejected_event_count == 1
    assert events.events[-1].disposition.value == "rejected"
    assert events.events[-1].duplicate_of_seq == 9


def test_pause_barrier_and_clean_close_flush_the_pending_prefix(tmp_path: Path) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        paused = store.observer(
            record, HistoryContext("run-paused", "host-1")
        )
        paused.on_event(
            _envelope(record, 1, StateChanged(SessionState.PAUSED))
        )
        with HistoryRepository(store.path) as repository:
            paused_summary = repository.get_summary("run-paused")
        assert paused_summary.current_state is SessionState.PAUSED

        closed = store.observer(
            _record("c" * 32), HistoryContext("run-close", "host-1")
        )
        closed.on_event(_envelope(_record("c" * 32), 1, _item(1)))
        closed.close()
        closed.close()

        with HistoryRepository(store.path) as repository:
            assert (
                repository.get_summary("run-paused").current_state
                is SessionState.PAUSED
            )
            assert repository.get_summary("run-close").last_committed_seq == 1


def test_crash_loses_only_the_uncommitted_tail_window(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    policy = HistoryWindowPolicy(max_events=2)
    record = _record()
    store = HistoryStore(path, clock=FakeClock(), window_policy=policy)
    observer = store.observer(record, HistoryContext("run-1", "host-1"))
    observer.on_event(_envelope(record, 1, _item(1)))
    observer.on_event(_envelope(record, 2, _item(2)))
    observer.on_event(_envelope(record, 3, _item(3)))
    assert observer.pending_event_count == 1
    store.close()

    with HistoryRepository(path) as repository:
        summary = repository.get_summary("run-1")
        page = repository.get_item_page("run-1")
    assert not summary.finalized
    assert summary.last_committed_seq == 2
    assert summary.item_count == 2
    assert [snapshot.item.item_id for snapshot in page.items] == [
        f"{1:032x}",
        f"{2:032x}",
    ]


def test_failed_finalization_rolls_back_tail_and_keeps_pending_window(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    policy = HistoryWindowPolicy(max_events=2)
    record = _record()
    result = OperationResult(SessionState.COMPLETED, items=(_item(1), _item(2), _item(3)))
    with HistoryStore(path, clock=FakeClock(), window_policy=policy) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.on_event(_envelope(record, 2, _item(2)))
        observer.on_event(_envelope(record, 3, _item(3)))
        pending_count = observer.pending_event_count
        pending_bytes = observer.pending_bytes
        pending_events = tuple(observer._pending)
        pending_hashes = dict(observer._event_hashes)

        connection = connect_history_writer(path)
        try:
            connection.executescript(
                """CREATE TRIGGER reject_history_terminal
                   BEFORE UPDATE OF terminal_payload_hash ON history_runs
                   WHEN NEW.terminal_payload_hash IS NOT NULL
                   BEGIN
                       SELECT RAISE(ABORT, 'terminal write rejected');
                   END;"""
            )
        finally:
            connection.close()

        with pytest.raises(RecordingError, match="terminal write rejected"):
            observer.finalize(result)
        assert observer.pending_event_count == pending_count == 1
        assert observer.pending_bytes == pending_bytes
        assert tuple(observer._pending) == pending_events
        assert observer._event_hashes == pending_hashes
        with closing(connect_history_writer(path)) as connection:
            connection.execute("DROP TRIGGER reject_history_terminal")
        with HistoryRepository(path) as repository:
            summary = repository.get_summary("run-1")
            items = repository.get_item_page("run-1")

    assert not summary.finalized
    assert summary.last_committed_seq == 2
    assert summary.item_count == 2
    assert [item.event_seq for item in items.items] == [1, 2]
    assert result.status is SessionState.COMPLETED
    assert result.audit is RecordingStatus.OK


def test_failed_window_commit_is_absent_and_keeps_its_bounded_pending_data(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    policy = HistoryWindowPolicy(max_events=1)
    with HistoryStore(path, clock=FakeClock(), window_policy=policy) as store:
        connection = connect_history_writer(path)
        try:
            connection.executescript(
                """CREATE TRIGGER reject_history_event
                   BEFORE INSERT ON history_events
                   BEGIN
                       SELECT RAISE(ABORT, 'event write rejected');
                   END;"""
            )
        finally:
            connection.close()

        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        with pytest.raises(RecordingError, match="event write rejected"):
            observer.on_event(_envelope(record, 1, _item(1)))

        assert observer.pending_event_count == 1
        assert 0 < observer.pending_bytes <= policy.max_bytes
        with closing(connect_history_writer(path)) as connection:
            connection.execute("DROP TRIGGER reject_history_event")
        with HistoryRepository(path) as repository:
            with pytest.raises(KeyError):
                repository.get_summary("run-1")


def test_durable_duplicates_are_idempotent_but_conflicts_and_late_events_fail(
    tmp_path: Path,
) -> None:
    record = _record()
    context = HistoryContext("run-1", "host-1")
    policy = HistoryWindowPolicy(max_events=1)
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.on_event(_envelope(record, 3, _item(3)))
        observer.on_event(_envelope(record, 1, _item(1)))

        late = store.observer(record, context)
        with pytest.raises(HistoryIntegrityError, match="out of order"):
            late.on_event(_envelope(record, 2, _item(2)))

        conflict = store.observer(record, context)
        with pytest.raises(HistoryIntegrityError, match="another payload"):
            conflict.on_event(
                _envelope(record, 1, _item(1, Outcome.FAILED))
            )

        with HistoryRepository(store.path) as repository:
            page = repository.get_event_page("run-1")
    assert [event.event_seq for event in page.events] == [1, 3]


@pytest.mark.parametrize(
    "max_events",
    (1, 256),
    ids=("durable-canonical", "same-window-canonical"),
)
def test_new_sequence_exact_item_duplicate_is_a_noncounting_receipt(
    tmp_path: Path, max_events: int,
) -> None:
    record = _record()
    item = _item(1)
    with HistoryStore(
        tmp_path / "history.db",
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_events=max_events),
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-duplicate", "host-1")
        )
        assert observer.on_event(_envelope(record, 1, item)) is RecordingStatus.OK
        assert observer.on_event(_envelope(record, 2, item)) is RecordingStatus.OK
        assert (
            observer.on_event(_envelope(record, 3, PhaseChanged("verify")))
            is RecordingStatus.OK
        )
        assert (
            observer.finalize(
                OperationResult(SessionState.COMPLETED, items=(item,))
            )
            is RecordingStatus.OK
        )

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-duplicate")
            items = repository.get_item_page("run-duplicate")
            events = repository.get_event_page("run-duplicate")

    assert summary.last_committed_seq == 3
    assert summary.item_count == 1
    assert summary.duplicate_item_count == 1
    assert summary.rejected_event_count == 0
    assert summary.succeeded_count == 1
    assert summary.audit is RecordingStatus.OK
    assert len(items.items) == 1
    assert [event.disposition.value for event in events.events] == [
        "recorded",
        "duplicate",
        "recorded",
    ]
    assert events.events[1].duplicate_of_seq == 1
    assert events.events[1].envelope is not None
    assert events.events[1].envelope.body == item


def test_new_sequence_conflicting_item_identity_breaks_the_prefix(
    tmp_path: Path,
) -> None:
    record = _record()
    original = _item(1)
    changed = replace(original, detail={"message": "99"})
    policy = HistoryWindowPolicy(max_events=1)
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-conflict", "host-1")
        )
        observer.on_event(_envelope(record, 1, original))
        with pytest.raises(HistoryIntegrityError, match="identity was reused"):
            observer.on_event(_envelope(record, 2, changed))
        with pytest.raises(HistoryIntegrityError, match="observer is degraded"):
            observer.on_event(_envelope(record, 3, PhaseChanged("verify")))
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-conflict")
            events = repository.get_event_page("run-conflict")

    assert summary.last_committed_seq == 1
    assert summary.item_count == 1
    assert summary.duplicate_item_count == 0
    assert [event.event_seq for event in events.events] == [1]


def test_same_window_conflicting_item_identity_rolls_back_the_window(
    tmp_path: Path,
) -> None:
    record = _record()
    original = _item(1)
    changed = replace(original, reason="blocked-correspondence")
    with HistoryStore(
        tmp_path / "history-same-window-conflict.db",
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_events=2),
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-same-window-conflict", "host-1")
        )
        observer.on_event(_envelope(record, 1, original))
        with pytest.raises(HistoryIntegrityError, match="identity was reused"):
            observer.on_event(_envelope(record, 2, changed))
        assert observer.pending_event_count == 2
        with HistoryRepository(store.path) as repository:
            with pytest.raises(KeyError):
                repository.get_summary("run-same-window-conflict")


def test_replay_lookup_retries_transient_busy_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class PrivateGraph:
        pass

    record = _record()
    path = tmp_path / "history.db"
    errors = []
    retained = []
    with HistoryStore(
        path,
        clock=FakeClock(),
        retry_timeout_seconds=0.1,
        retry_interval_seconds=0,
        window_policy=HistoryWindowPolicy(max_events=1),
    ) as store:
        observer = store.observer(record, HistoryContext("run-retry", "host-1"))
        event = _envelope(record, 1, _item(1))
        observer.on_event(event)
        connect = history_module.connect_history_reader
        attempts = 0

        def transient(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                graph = PrivateGraph()
                retained.append(ref(graph))
                try:
                    cause = LookupError("private busy-read cause")
                    cause.graph = graph
                    raise cause
                except LookupError as cause:
                    error = sqlite3.OperationalError("database is locked")
                    errors.append(error)
                    raise error from cause
            return connect(*args, **kwargs)

        monkeypatch.setattr(history_module, "connect_history_reader", transient)
        assert observer.on_event(event) is RecordingStatus.OK

    assert attempts == 2
    assert errors[0].__traceback__ is None
    assert errors[0].__cause__ is None
    assert errors[0].__context__ is None
    assert retained[0]() is None


def test_replay_lookup_close_failure_cannot_replace_receipt_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PrivateGraph:
        pass

    record = _record()
    path = tmp_path / "history-close-precedence.db"
    primary = HistoryIntegrityError("private receipt failure")
    primary_errors = []
    close_errors = []
    retained = []
    with HistoryStore(
        path,
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_events=1),
    ) as store:
        event = _envelope(record, 1, _item(1))
        store.observer(
            record,
            HistoryContext("run-close-precedence", "host-1"),
        ).on_event(event)
        replay = store.observer(
            record,
            HistoryContext("run-close-precedence", "host-1"),
        )
        connect = history_module.connect_history_reader

        class CloseFailingReader:
            def __init__(self, connection) -> None:
                self._connection = connection

            def execute(self, *args, **kwargs):
                return self._connection.execute(*args, **kwargs)

            def close(self) -> None:
                self._connection.close()
                graph = PrivateGraph()
                retained.append(ref(graph))
                try:
                    cause = LookupError("private reader-close cause")
                    cause.graph = graph
                    raise cause
                except LookupError as cause:
                    error = OSError("reader close failed")
                    close_errors.append(error)
                    raise error from cause

        def connect_with_failing_close(*args, **kwargs):
            return CloseFailingReader(connect(*args, **kwargs))

        def fail_receipt(row):
            del row
            graph = PrivateGraph()
            retained.append(ref(graph))
            try:
                cause = LookupError("private receipt cause")
                cause.graph = graph
                raise cause
            except LookupError as cause:
                primary_errors.append(primary)
                raise primary from cause

        monkeypatch.setattr(
            history_module,
            "connect_history_reader",
            connect_with_failing_close,
        )
        monkeypatch.setattr(history_module, "_validated_receipt", fail_receipt)

        with pytest.raises(
            HistoryIntegrityError,
            match="private receipt failure",
        ) as raised:
            replay.on_event(event)

    assert raised.value is primary
    assert primary_errors == [primary]
    assert len(close_errors) == 1
    assert primary.__cause__ is None
    assert primary.__context__ is None
    assert close_errors[0].__traceback__ is None
    assert close_errors[0].__cause__ is None
    assert close_errors[0].__context__ is None
    assert retained and all(reference() is None for reference in retained)


def test_replay_lookup_retires_a_failed_sqlite_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PrivateGraph:
        pass

    class HostileOperationalError(sqlite3.OperationalError):
        def __str__(self) -> str:
            graph = PrivateGraph()
            retained.append(ref(graph))
            diagnostic = LookupError("private sqlite diagnostic")
            diagnostics.append(diagnostic)
            raise diagnostic

    record = _record()
    path = tmp_path / "history-diagnostic.db"
    original = HostileOperationalError("private sqlite failure")
    retained = []
    diagnostics = []
    with HistoryStore(
        path,
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_events=1),
    ) as store:
        event = _envelope(record, 1, _item(1))
        store.observer(
            record,
            HistoryContext("run-diagnostic", "host-1"),
        ).on_event(event)
        replay = store.observer(
            record,
            HistoryContext("run-diagnostic", "host-1"),
        )

        def fail_connect(*args, **kwargs):
            del args, kwargs
            raise original

        monkeypatch.setattr(history_module, "connect_history_reader", fail_connect)

        with pytest.raises(LookupError, match="private sqlite diagnostic") as raised:
            replay.on_event(event)

    assert raised.value is diagnostics[0]
    assert original.__traceback__ is None
    assert original.__cause__ is None
    assert original.__context__ is None
    assert diagnostics[0].__cause__ is None
    assert diagnostics[0].__context__ is None
    assert retained[0]() is None


@pytest.mark.parametrize(
    ("error_message", "expected"),
    (
        ("database is locked", "remained busy"),
        ("disk I/O error", "disk I/O error"),
    ),
)
def test_replay_lookup_exhaustion_or_nonretryable_read_is_fail_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_message: str,
    expected: str,
) -> None:
    record = _record()
    path = tmp_path / f"history-{error_message[:4]}.db"
    with HistoryStore(
        path,
        clock=FakeClock(),
        retry_timeout_seconds=0,
        retry_interval_seconds=0,
        window_policy=HistoryWindowPolicy(max_events=1),
    ) as store:
        observer = store.observer(record, HistoryContext("run-read-fail", "host-1"))
        event = _envelope(record, 1, _item(1))
        observer.on_event(event)
        connect = history_module.connect_history_reader

        def fail(*args, **kwargs):
            raise sqlite3.OperationalError(error_message)

        monkeypatch.setattr(history_module, "connect_history_reader", fail)
        with pytest.raises(RecordingError, match=expected):
            observer.on_event(event)
        with pytest.raises(HistoryIntegrityError, match="observer is degraded"):
            observer.on_event(_envelope(record, 2, PhaseChanged("verify")))
        monkeypatch.setattr(history_module, "connect_history_reader", connect)
        with HistoryRepository(path) as repository:
            summary = repository.get_summary("run-read-fail")

    assert summary.last_committed_seq == 1
    assert summary.item_count == 1


def test_oversized_final_tail_receipt_still_allows_terminal_commit(
    tmp_path: Path,
) -> None:
    record = _record()
    oversized = _envelope(
        record,
        2,
        ItemOutcome(
            "9" * 32,
            "copy",
            f"{'x' * 1_000}.bin",
            Outcome.SUCCEEDED,
        ),
    )
    policy = HistoryWindowPolicy(max_bytes=512, max_event_bytes=512)
    result = OperationResult(SessionState.COMPLETED)
    with HistoryStore(
        tmp_path / "history-tail.db",
        clock=FakeClock(),
        window_policy=policy,
    ) as store:
        observer = store.observer(record, HistoryContext("run-tail", "host-1"))
        observer.on_event(_envelope(record, 1, PhaseChanged("execute")))
        assert observer.on_event(oversized) is RecordingStatus.DEGRADED
        assert (
            observer.finalize(result)
            is RecordingStatus.DEGRADED
        )
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-tail")
            events = repository.get_event_page("run-tail")

    assert summary.last_committed_seq == 2
    assert summary.rejected_event_count == 1
    assert summary.audit is RecordingStatus.DEGRADED
    assert result.audit is RecordingStatus.OK
    assert events.events[-1].envelope is None
    assert events.events[-1].rejection_reason == history_module.EVENT_TOO_LARGE


def test_repeated_finalization_and_cross_observer_replay_are_idempotent(
    tmp_path: Path,
) -> None:
    record = _record()
    context = HistoryContext("run-1", "host-1")
    item = _item(1)
    result = OperationResult(SessionState.COMPLETED, items=(item,))
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, item))
        observer.finalize(result)
        observer.finalize(result)
        with pytest.raises(TokenConflictError):
            observer.finalize(replace(result, audit=RecordingStatus.DEGRADED))

        replay = store.observer(record, context)
        replay.on_event(_envelope(record, 1, item))
        replay.finalize(result)


def test_compound_cancellation_preserves_canceled_lifecycle_and_filesystem_axis(
    tmp_path: Path,
) -> None:
    record = _record()
    result = OperationResult(
        SessionState.COMPLETED,
        canceled=True,
        phases=(
            PhaseResult("execute", PhaseStatus.COMPLETED, 1, 1, 1, 1),
            PhaseResult("verify", PhaseStatus.CANCELED, 0, 1, 0, 1),
        ),
        bytes_done=1,
        bytes_total=1,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.finalize(result)
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")

    assert summary.current_state is SessionState.CANCELED
    assert summary.filesystem_status is SessionState.COMPLETED
    assert summary.canceled is True


def test_unrun_finalization_preserves_absent_start_time(tmp_path: Path) -> None:
    record = _record()
    result = OperationResult(
        SessionState.CANCELED,
        disposition=Disposition.UNRUN,
        canceled=True,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(
            record, HistoryContext("run-unrun", "host-1")
        )
        observer.finalize(result)
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-unrun")

    assert summary.finalized
    assert summary.current_state is SessionState.CANCELED
    assert summary.disposition == Disposition.UNRUN.value
    assert summary.started_at is None
    assert summary.ended_at == NOW


def test_reopened_zero_event_finalization_is_idempotent_after_clock_regression(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    context = HistoryContext("run-unrun", "host-1")
    result = OperationResult(
        SessionState.CANCELED,
        disposition=Disposition.UNRUN,
        canceled=True,
    )
    with HistoryStore(path, clock=FakeClock()) as store:
        store.observer(record, context).finalize(result)

    regressed = FakeClock(NOW - timedelta(seconds=1))
    with HistoryStore(path, clock=regressed) as store:
        store.observer(record, context).finalize(result)
        with HistoryRepository(path) as repository:
            summary = repository.get_summary("run-unrun")

    assert summary.started_at is None
    assert summary.ended_at == NOW


def test_stale_concurrent_observers_accept_exact_replay_and_reject_reordering(
    tmp_path: Path,
) -> None:
    record = _record()
    context = HistoryContext("run-1", "host-1")
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        first = store.observer(record, context)
        exact = store.observer(record, context)
        reordered = store.observer(record, context)
        first.on_event(_envelope(record, 1, _item(1)))
        first.on_event(_envelope(record, 3, _item(3)))
        exact.on_event(_envelope(record, 1, _item(1)))
        exact.on_event(_envelope(record, 3, _item(3)))
        reordered.on_event(_envelope(record, 1, _item(1)))
        reordered.on_event(_envelope(record, 2, _item(2)))

        first.flush()
        exact.flush()
        with pytest.raises(HistoryIntegrityError, match="out of order"):
            reordered.flush()

        with HistoryRepository(store.path) as repository:
            assert [
                event.event_seq
                for event in repository.get_event_page("run-1").events
            ] == [1, 3]


def test_commit_timestamp_is_sampled_under_writer_ownership_and_never_regresses(
    tmp_path: Path,
) -> None:
    class GuardedClock:
        def __init__(self) -> None:
            self.values = [
                NOW + timedelta(seconds=2),
                NOW + timedelta(seconds=1),
                NOW,
            ]
            self.writer_owned = False

        def now(self):
            assert self.writer_owned, "history sampled time before writer ownership"
            return self.values.pop(0)

    clock = GuardedClock()
    record = _record()
    context = HistoryContext("run-timestamps", "host-1")
    with HistoryStore(tmp_path / "history.db", clock=clock) as store:
        original_transact = store._writer.transact

        def tracked_transact(operation):
            def writer_owned(connection):
                clock.writer_owned = True
                try:
                    return operation(connection)
                finally:
                    clock.writer_owned = False

            return original_transact(writer_owned)

        store._writer.transact = tracked_transact

        # Both observers admit against the same empty durable state. Their
        # flush order advances the watermark while the supplied wall clock
        # moves backward, reproducing the stale-observer interleaving.
        first = store.observer(record, context)
        second = store.observer(record, context)
        first.on_event(_envelope(record, 1, _item(1)))
        second.on_event(_envelope(record, 2, _item(2)))
        first.flush()
        second.flush()

        with HistoryRepository(store.path) as repository:
            after_second = repository.get_summary("run-timestamps")
        assert after_second.last_committed_seq == 2
        assert after_second.last_committed_at == NOW + timedelta(seconds=2)

        second.on_event(_envelope(record, 3, _item(3)))
        second.finalize(OperationResult(SessionState.COMPLETED))
        with HistoryRepository(store.path) as repository:
            finalized = repository.get_summary("run-timestamps")

    assert clock.values == []
    assert finalized.last_committed_seq == 3
    assert finalized.last_committed_at == NOW + timedelta(seconds=2)
    assert finalized.ended_at == finalized.last_committed_at


def test_first_commit_clamps_clock_rollback_to_the_observed_start(
    tmp_path: Path,
) -> None:
    record = _record()
    started_at = NOW + timedelta(seconds=2)
    running = Envelope(
        record.session_id,
        1,
        started_at,
        CORE_EVENT_SCHEMA_VERSION,
        StateChanged(SessionState.RUNNING),
    )
    with HistoryStore(
        tmp_path / "history.db",
        clock=FakeClock(NOW + timedelta(seconds=1)),
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-clock-rollback", "host-1")
        )
        observer.on_event(running)
        observer.finalize(OperationResult(SessionState.COMPLETED))
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-clock-rollback")

    assert summary.started_at == started_at
    assert summary.last_committed_at == started_at
    assert summary.ended_at == started_at


@pytest.mark.parametrize(
    "body",
    (
        PhaseChanged("verify"),
        _item(2),
    ),
)
def test_later_event_timestamp_bounds_commit_and_terminal_time_during_rollback(
    tmp_path: Path,
    body: object,
) -> None:
    clock = FakeClock(NOW + timedelta(seconds=2))
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=clock) as store:
        observer = store.observer(
            record, HistoryContext("run-later-event", "host-1")
        )
        observer.on_event(
            Envelope(
                record.session_id,
                1,
                NOW + timedelta(seconds=1),
                CORE_EVENT_SCHEMA_VERSION,
                StateChanged(SessionState.RUNNING),
            )
        )
        observer.flush()

        event_at = NOW + timedelta(seconds=10)
        observer.on_event(
            Envelope(
                record.session_id,
                2,
                event_at,
                CORE_EVENT_SCHEMA_VERSION,
                body,
            )
        )
        clock.value = NOW + timedelta(seconds=3)
        observer.finalize(OperationResult(SessionState.COMPLETED))
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-later-event")

    assert summary.last_committed_at == event_at
    assert summary.ended_at == event_at


def test_context_token_conflict_is_rejected_before_new_events(tmp_path: Path) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        first = store.observer(record, HistoryContext("run-1", "host-1"))
        first.on_event(_envelope(record, 1, _item(1)))
        first.flush()
        with pytest.raises(TokenConflictError, match="context changed"):
            store.observer(record, HistoryContext("run-1", "host-2"))


def test_item_and_event_pages_use_fixed_keyset_watermarks(tmp_path: Path) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        for seq in range(1, 6):
            observer.on_event(_envelope(record, seq, _item(seq)))
        observer.flush()

        with HistoryRepository(store.path) as repository:
            first_items = repository.get_item_page("run-1", limit=2)
            first_events = repository.get_event_page("run-1", limit=2)
            assert first_items.through_order == 5
            assert first_events.through_seq == 5

            observer.on_event(_envelope(record, 6, _item(6)))
            observer.flush()

            second_items = repository.get_item_page(
                "run-1",
                after_order=first_items.next_after_order,
                through_order=first_items.through_order,
                limit=MAX_HISTORY_PAGE_SIZE,
            )
            second_events = repository.get_event_page(
                "run-1",
                after_seq=first_events.next_after_seq,
                through_seq=first_events.through_seq,
                limit=MAX_HISTORY_PAGE_SIZE,
            )
            latest = repository.get_item_page("run-1")

    assert [item.item_order for item in first_items.items] == [1, 2]
    assert [item.item_order for item in second_items.items] == [3, 4, 5]
    assert not second_items.has_more
    assert [event.event_seq for event in second_events.events] == [3, 4, 5]
    assert latest.through_order == 6
    assert latest.items[-1].item_order == 6


def test_fresh_event_traversal_can_start_ahead_of_durability(
    tmp_path: Path,
) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, PhaseChanged("scan")))
        observer.flush()

        with HistoryRepository(store.path) as repository:
            ahead = repository.get_event_page("run-1", after_seq=2)

            observer.on_event(_envelope(record, 3, PhaseChanged("execute")))
            observer.flush()

            caught_up = repository.get_event_page("run-1", after_seq=2)
            with pytest.raises(ValueError, match="cursor exceeds"):
                repository.get_event_page(
                    "run-1",
                    after_seq=ahead.next_after_seq,
                    through_seq=ahead.through_seq,
                )

    assert ahead.through_seq == 1
    assert ahead.next_after_seq == 2
    assert ahead.events == ()
    assert not ahead.has_more
    assert caught_up.through_seq == 3
    assert caught_up.next_after_seq == 3
    assert [event.event_seq for event in caught_up.events] == [3]
    assert not caught_up.has_more


@pytest.mark.parametrize("limit", [0, 257])
def test_read_limits_reject_unbounded_requests(tmp_path: Path, limit: int) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
        with HistoryRepository(store.path) as repository:
            with pytest.raises(ValueError):
                repository.list_summaries(limit)
            with pytest.raises(ValueError):
                repository.get_item_page("run-1", limit=limit)
            with pytest.raises(ValueError):
                repository.get_event_page("run-1", limit=limit)


def test_read_limits_accept_one_and_256(tmp_path: Path) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
        with HistoryRepository(store.path) as repository:
            assert len(repository.list_summaries(1)) == 1
            assert len(repository.list_summaries(256)) == 1
            assert len(repository.get_item_page("run-1", limit=1).items) == 1
            assert len(repository.get_item_page("run-1", limit=256).items) == 1
            assert len(repository.get_event_page("run-1", limit=1).events) == 1
            assert len(repository.get_event_page("run-1", limit=256).events) == 1


def test_pages_decode_no_more_than_the_requested_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        for sequence in range(1, 5):
            observer.on_event(_envelope(record, sequence, _item(sequence)))
        observer.flush()

        original = history_module._history_event
        decoded: list[int] = []

        def counted(row, expected_session_id):
            decoded.append(int(row["event_seq"]))
            return original(row, expected_session_id)

        monkeypatch.setattr(history_module, "_history_event", counted)
        with HistoryRepository(store.path) as repository:
            item_page = repository.get_item_page("run-1", limit=2)
            assert len(item_page.items) == 2
            assert len(decoded) == 2

            decoded.clear()
            event_page = repository.get_event_page("run-1", limit=2)
            assert len(event_page.events) == 2
            assert len(decoded) == 2
            assert event_page.has_more


def test_summary_listing_uses_fixed_queries_and_never_decodes_event_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "history.db"
    with HistoryStore(path, clock=FakeClock()) as store:
        for index in range(3):
            record = _record(f"{index + 1:032x}")
            observer = store.observer(
                record, HistoryContext(f"run-{index}", "host-1")
            )
            observer.on_event(_envelope(record, 1, _item(index + 1)))
            observer.finalize(OperationResult(SessionState.COMPLETED))

    def reject_decode(_raw):
        raise AssertionError("summary listing decoded an event payload")

    monkeypatch.setattr(history_module, "envelope_from_dict", reject_decode)
    with HistoryRepository(path) as repository:
        statements: list[str] = []
        repository._connection.set_trace_callback(statements.append)
        summaries = repository.list_summaries(3)
    selects = [
        statement
        for statement in statements
        if statement.startswith(("SELECT", "WITH"))
    ]
    assert len(summaries) == 3
    assert len(selects) == 3


def test_event_pages_round_trip_nonitem_reliable_events_and_sequence_gaps(
    tmp_path: Path,
) -> None:
    record = _record()
    bodies = (
        StateChanged(SessionState.RUNNING),
        PhaseChanged("scan"),
        Gap(4),
    )
    sequences = (1, 3, 5)
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        for sequence, body in zip(sequences, bodies, strict=True):
            observer.on_event(_envelope(record, sequence, body))
        observer.flush()
        with HistoryRepository(store.path) as repository:
            page = repository.get_event_page("run-1")
            first = repository.get_event_page(
                "run-1", through_seq=4, limit=1
            )
            second = repository.get_event_page(
                "run-1",
                after_seq=first.next_after_seq,
                through_seq=first.through_seq,
                limit=1,
            )
            before_history = repository.get_event_page(
                "run-1", through_seq=0
            )
    assert [event.event_seq for event in page.events] == list(sequences)
    assert [event.envelope.body for event in page.events] == list(bodies)
    assert [event.event_seq for event in first.events] == [1]
    assert first.through_seq == 4
    assert first.has_more
    assert [event.event_seq for event in second.events] == [3]
    assert second.next_after_seq == 3
    assert second.through_seq == 4
    assert not second.has_more
    assert before_history.events == ()
    assert before_history.next_after_seq == 0
    assert before_history.through_seq == 0
    assert not before_history.has_more


def test_history_round_trips_a_persisted_v5_reliable_envelope(
    tmp_path: Path,
) -> None:
    record = _record()
    envelope = Envelope(
        record.session_id,
        1,
        NOW,
        CORE_EVENT_SCHEMA_VERSION,
        PhaseChanged("execute"),
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-v5", "host-1"))
        observer.on_event(envelope)
        observer.flush()
        with HistoryRepository(store.path) as repository:
            page = repository.get_event_page("run-v5")

    assert [event.envelope for event in page.events] == [envelope]


def test_event_readback_detects_payload_tampering(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    with closing(connection), _without_history_triggers(connection, "history_events_append_only_update"):
        connection.execute(
            "UPDATE history_events SET envelope_json = envelope_json || ' '")
    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="payload hash"):
            repository.get_event_page("run-1")


def test_history_event_rows_are_append_only_and_item_projections_are_validated(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-guarded", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute(
                "UPDATE history_events SET envelope_json = envelope_json"
            )
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute("DELETE FROM history_events")
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute(
                "INSERT INTO history_events(result) VALUES ('failed')"
            )
        with _without_history_triggers(connection, "history_events_append_only_update"):
            connection.execute("UPDATE history_events SET result = 'failed'")
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="columns disagree"):
            repository.get_event_page("run-guarded")


def test_history_event_duplicate_insert_requires_canonical_link(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    item = _item(1)
    with HistoryStore(
        path, clock=FakeClock(), window_policy=HistoryWindowPolicy(max_events=1)
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-duplicate-guard", "host-1")
        )
        observer.on_event(_envelope(record, 1, item))
        observer.on_event(_envelope(record, 2, item))

    connection = connect_history_writer(path)
    try:
        with pytest.raises(
            sqlite3.DatabaseError, match="duplicate receipt link mismatch"
        ):
            connection.execute(
                """INSERT INTO history_events(
                       run_id, event_seq, event_at, schema_version, body_type,
                       event_disposition, envelope_json, payload_hash, receipt_hash,
                       item_identity_hash, item_payload_hash, duplicate_of_seq,
                       rejection_reason, item_order, item_type, phase, item_id, kind,
                       path, result, reason, recording, recording_reason,
                       recording_detail, detail_omitted_count
                   ) SELECT run_id, event_seq + 1, event_at, schema_version, body_type,
                            event_disposition, envelope_json, payload_hash, receipt_hash,
                            item_identity_hash, item_payload_hash, 2,
                            rejection_reason, item_order, item_type, phase, item_id, kind,
                            path, result, reason, recording, recording_reason,
                            recording_detail, detail_omitted_count
                       FROM history_events WHERE run_id = 1 AND event_seq = 2"""
            )
    finally:
        connection.close()


def test_replace_cannot_overwrite_a_durable_history_event(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    item = _item(1)
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-replace", "host-1"))
        observer.on_event(_envelope(record, 1, item))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute("PRAGMA recursive_triggers = OFF")
        with pytest.raises(sqlite3.IntegrityError, match="writable tail"):
            connection.execute(
                """INSERT OR REPLACE INTO history_events(
                       run_id, event_seq, event_at, schema_version, body_type,
                       event_disposition, envelope_json, payload_hash,
                       receipt_hash, item_identity_hash, item_payload_hash,
                       duplicate_of_seq, rejection_reason, item_order,
                       item_type, phase, item_id, kind, path, result, reason
                   ) SELECT run_id, event_seq, event_at, schema_version,
                            body_type, event_disposition, envelope_json,
                            payload_hash, receipt_hash, item_identity_hash,
                            item_payload_hash, duplicate_of_seq,
                            rejection_reason, item_order, item_type, phase,
                            item_id, kind, path, result, reason
                       FROM history_events WHERE event_seq = 1"""
            )
        with pytest.raises(sqlite3.OperationalError, match="rowid"):
            connection.execute(
                """INSERT OR REPLACE INTO history_events(
                       rowid, run_id, event_seq, event_at, schema_version,
                       body_type, event_disposition, envelope_json,
                       payload_hash, receipt_hash, item_identity_hash,
                       item_payload_hash, duplicate_of_seq, rejection_reason,
                       item_order, item_type, phase, item_id, kind, path,
                       result, reason
                   ) SELECT rowid, run_id, event_seq + 1, event_at,
                            schema_version, body_type, event_disposition,
                            envelope_json, payload_hash, receipt_hash,
                            item_identity_hash, item_payload_hash,
                            duplicate_of_seq, rejection_reason, item_order + 1,
                            item_type, phase, item_id, kind, path, result, reason
                       FROM history_events WHERE event_seq = 1"""
            )
        with pytest.raises(sqlite3.IntegrityError, match="writable tail"):
            connection.execute(
                """INSERT OR REPLACE INTO history_events(
                       run_id, event_seq, event_at, schema_version, body_type,
                       event_disposition, envelope_json, payload_hash,
                       receipt_hash, item_identity_hash, item_payload_hash,
                       duplicate_of_seq, rejection_reason, item_order,
                       item_type, phase, item_id, kind, path, result, reason
                   ) SELECT run_id, event_seq + 1, event_at, schema_version,
                            body_type, event_disposition, envelope_json,
                            payload_hash, receipt_hash, zeroblob(32),
                            item_payload_hash, duplicate_of_seq,
                            rejection_reason, item_order + 1, item_type, phase,
                            item_id, kind, path, result, reason
                       FROM history_events WHERE event_seq = 1"""
            )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        assert repository.get_item_page("run-replace").items[0].item == item


def test_finalized_run_refuses_event_insert_reopen_delete_and_replace(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    context = HistoryContext("run-finalized", "host-1")
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, PhaseChanged("execute")))
        observer.finalize(OperationResult(SessionState.COMPLETED))
    connection = connect_history_writer(path)
    try:
        run_id = int(
            connection.execute(
                "SELECT id FROM history_runs WHERE run_token = 'run-finalized'"
            ).fetchone()["id"]
        )
        with pytest.raises(sqlite3.IntegrityError, match="writable tail"):
            _insert_history_event(
                connection,
                run_id,
                _envelope(record, 2, PhaseChanged("verify")),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                """UPDATE history_runs
                      SET terminal_payload_hash = NULL, ended_at = NULL,
                          filesystem_status = NULL, recording_status = NULL,
                          audit_status = NULL, disposition = NULL,
                          canceled = NULL, bytes_done = NULL, bytes_total = NULL,
                          error_type = NULL, error_message = NULL
                    WHERE id = ?""",
                (run_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute("DELETE FROM history_runs WHERE id = ?", (run_id,))
        connection.execute("PRAGMA recursive_triggers = OFF")
        with pytest.raises(sqlite3.IntegrityError, match="cannot be replaced"):
            connection.execute(
                "INSERT OR REPLACE INTO history_runs SELECT * FROM history_runs"
            )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        assert repository.get_summary("run-finalized").finalized


def test_incomplete_runs_refuse_delete_insert_replace_and_update_replace(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        for seq, token in enumerate(("run-first", "run-second"), 1):
            observer = store.observer(record, HistoryContext(token, "host-1"))
            observer.on_event(_envelope(record, seq, PhaseChanged(token)))
            observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute("PRAGMA recursive_triggers = OFF")
        with pytest.raises(sqlite3.IntegrityError, match="replace another run"):
            connection.execute(
                """UPDATE OR REPLACE history_runs SET run_token = 'run-second'
                    WHERE run_token = 'run-first'"""
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute(
                "DELETE FROM history_runs WHERE run_token = 'run-first'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be replaced"):
            connection.execute(
                """INSERT OR REPLACE INTO history_runs
                    SELECT * FROM history_runs WHERE run_token = 'run-first'"""
            )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        assert {summary.run_token for summary in repository.list_summaries()} == {
            "run-first",
            "run-second",
        }


def test_summary_rejects_an_uncommitted_external_event_tail(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-tail", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        run_id = int(connection.execute("SELECT id FROM history_runs").fetchone()["id"])
        _insert_history_event(
            connection,
            run_id,
            _envelope(record, 2, _item(2, Outcome.FAILED)),
            item_order=2,
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="watermark"):
            repository.get_summary("run-tail")
        with pytest.raises(HistoryIntegrityError, match="watermark"):
            repository.list_summaries()
        with pytest.raises(HistoryIntegrityError, match="watermark"):
            repository.get_item_page("run-tail")
        with pytest.raises(HistoryIntegrityError, match="watermark"):
            repository.get_event_page("run-tail")
    with HistoryStore(path, clock=FakeClock()) as store:
        with pytest.raises(HistoryIntegrityError, match="watermark"):
            store.observer(record, HistoryContext("run-tail", "host-1"))


def test_event_and_item_pages_validate_run_context(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-context", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute(
            "UPDATE history_runs SET session_id = 'forged-session'"
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="context hash"):
            repository.get_event_page("run-context")
        with pytest.raises(HistoryIntegrityError, match="context hash"):
            repository.get_item_page("run-context")


def test_event_and_item_pages_reject_envelope_session_misattribution(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-session", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    with closing(connection), _without_history_triggers(connection, "history_events_append_only_update"):
        row = connection.execute(
            "SELECT * FROM history_events WHERE event_seq = 1"
        ).fetchone()
        raw = history_module.json.loads(str(row["envelope_json"]))
        raw["session_id"] = "2" * 32
        envelope_json = history_module._json_bytes(raw).decode("utf-8")
        payload_hash = history_module.hashlib.sha256(
            envelope_json.encode("utf-8")
        ).digest()
        receipt_hash = history_module._receipt_hash(
            event_seq=int(row["event_seq"]),
            event_at=str(row["event_at"]),
            schema_version=int(row["schema_version"]),
            body_type=str(row["body_type"]),
            disposition=history_module.HistoryEventDisposition.RECORDED,
            payload_hash=payload_hash,
            item_identity_hash=bytes(row["item_identity_hash"]),
            item_payload_hash=bytes(row["item_payload_hash"]),
            item_order=int(row["item_order"]),
        )
        connection.execute(
            """UPDATE history_events
                  SET envelope_json = ?, payload_hash = ?, receipt_hash = ?
                WHERE event_seq = 1""",
            (envelope_json, payload_hash, receipt_hash),
        )

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="columns disagree"):
            repository.get_event_page("run-session")
        with pytest.raises(HistoryIntegrityError, match="columns disagree"):
            repository.get_item_page("run-session")


@pytest.mark.parametrize(
    "tamper_sql",
    (
        "UPDATE history_events SET event_at = "
        "'2026-01-02T03:04:06.123456Z' WHERE event_seq = 1",
        "UPDATE history_events SET body_type = 'IntegrityOutcome' "
        "WHERE event_seq = 1",
        "UPDATE history_events SET event_seq = 2 WHERE event_seq = 1; "
        "UPDATE history_runs SET last_committed_seq = 2",
    ),
)
def test_rejected_receipt_binds_retained_event_metadata(
    tmp_path: Path,
    tamper_sql: str,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    event = _envelope(
        record,
        1,
        replace(_item(1), path=f"{'x' * 1_000}.bin"),
    )
    with HistoryStore(
        path,
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_bytes=512, max_event_bytes=512),
    ) as store:
        observer = store.observer(record, HistoryContext("run-rejected", "host-1"))
        assert observer.on_event(event) is RecordingStatus.DEGRADED
    connection = connect_history_writer(path)
    with closing(connection), _without_history_triggers(connection, "history_events_append_only_update"):
        connection.executescript(tamper_sql)
        if "last_committed_seq" in tamper_sql:
            run = connection.execute("SELECT * FROM history_runs").fetchone()
            connection.execute(
                "UPDATE history_runs SET prefix_projection_hash = ?",
                (history_module._prefix_projection_hash_from_row(run),),
            )

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="receipt hash"):
            repository.get_event_page("run-rejected")


def test_replay_rejects_tampered_rejected_receipt_metadata(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    event = _envelope(
        record,
        1,
        replace(_item(1), path=f"{'x' * 1_000}.bin"),
    )
    with HistoryStore(
        path,
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_bytes=512, max_event_bytes=512),
    ) as store:
        observer = store.observer(record, HistoryContext("run-replay", "host-1"))
        observer.on_event(event)
        connection = connect_history_writer(path)
        with closing(connection), _without_history_triggers(connection, "history_events_append_only_update"):
            connection.execute(
                "UPDATE history_events SET body_type = 'IntegrityOutcome'"
            )

        replay = store.observer(record, HistoryContext("run-replay", "host-1"))
        with pytest.raises(HistoryIntegrityError, match="receipt hash"):
            replay.on_event(event)


def test_item_page_rejects_item_order_tampering(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-order", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.on_event(_envelope(record, 2, _item(2)))
        observer.flush()
    connection = connect_history_writer(path)
    with closing(connection), _without_history_triggers(connection, "history_events_append_only_update"):
        connection.execute(
            "UPDATE history_events SET item_order = 3 WHERE event_seq = 1"
        )
        connection.execute(
            "UPDATE history_events SET item_order = 1 WHERE event_seq = 2"
        )

    with HistoryRepository(path) as repository:
        with pytest.raises(
            HistoryIntegrityError, match="receipt hash|item watermark"
        ):
            repository.get_item_page("run-order")


def test_item_identity_hash_is_validated_against_the_envelope(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-identity", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    with closing(connection), _without_history_triggers(connection, "history_events_append_only_update"):
        row = connection.execute(
            "SELECT * FROM history_events WHERE event_seq = 1"
        ).fetchone()
        altered_identity_hash = b"x" * 32
        receipt_hash = history_module._receipt_hash(
            event_seq=int(row["event_seq"]),
            event_at=str(row["event_at"]),
            schema_version=int(row["schema_version"]),
            body_type=str(row["body_type"]),
            disposition=history_module.HistoryEventDisposition.RECORDED,
            payload_hash=bytes(row["payload_hash"]),
            item_identity_hash=altered_identity_hash,
            item_payload_hash=bytes(row["item_payload_hash"]),
            item_order=int(row["item_order"]),
        )
        connection.execute(
            """UPDATE history_events
                  SET item_identity_hash = ?, receipt_hash = ?
                WHERE event_seq = 1""",
            (altered_identity_hash, receipt_hash),
        )

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="identity hash"):
            repository.get_event_page("run-identity")


def test_summary_detects_receipt_counter_tampering(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    item = _item(1)
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-counts", "host-1"))
        observer.on_event(_envelope(record, 1, item))
        observer.on_event(_envelope(record, 2, item))
        observer.finalize(OperationResult(SessionState.COMPLETED, items=(item,)))
    connection = connect_history_writer(path)
    with closing(connection), _without_history_triggers(connection, "history_runs_finalized_update"):
        connection.execute(
            """UPDATE history_runs SET duplicate_item_count = 0
                WHERE run_token = 'run-counts'"""
        )

    with HistoryRepository(path) as repository:
        with pytest.raises(
            HistoryIntegrityError,
            match="receipt counts|payload hash|prefix projection",
        ):
            repository.get_summary("run-counts")


@pytest.mark.parametrize(
    "column",
    (
        "item_count",
        "succeeded_count",
        "skipped_count",
        "failed_count",
        "canceled_count",
        "deferred_count",
        "blocked_count",
    ),
)
def test_terminal_hash_binds_item_and_outcome_counts(
    tmp_path: Path,
    column: str,
) -> None:
    path = tmp_path / f"history-{column}.db"
    record = _record()
    items = tuple(_item(index + 1, outcome) for index, outcome in enumerate(Outcome))
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-count-hash", "host-1"))
        for seq, item in enumerate(items, 1):
            observer.on_event(_envelope(record, seq, item))
        observer.finalize(OperationResult(SessionState.COMPLETED, items=items))
    connection = connect_history_writer(path)
    with closing(connection), _without_history_triggers(connection, "history_runs_finalized_update"):
        connection.execute(
            f"UPDATE history_runs SET {column} = {column} + 1"
        )

    with HistoryRepository(path) as repository:
        with pytest.raises(
            HistoryIntegrityError, match="payload hash|prefix projection"
        ):
            repository.get_summary("run-count-hash")


@pytest.mark.parametrize("column", ("item_count", "failed_count"))
def test_incomplete_summary_validates_item_and_outcome_counts(
    tmp_path: Path,
    column: str,
) -> None:
    path = tmp_path / f"history-incomplete-{column}.db"
    record = _record()
    item = _item(1, Outcome.FAILED)
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-incomplete", "host-1"))
        observer.on_event(_envelope(record, 1, item))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute(
            f"UPDATE history_runs SET {column} = {column} + 1"
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="prefix projection"):
            repository.get_summary("run-incomplete")


def test_incomplete_summary_rejects_unsafe_prefix_counter_even_with_matching_hash(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext("run-unsafe-prefix", "host-1"),
        )
        observer.on_event(_envelope(record, 1, PhaseChanged("execute")))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            "UPDATE history_runs SET last_committed_seq = ?",
            (MAX_SAFE_INTEGER + 1,),
        )
        run = connection.execute("SELECT * FROM history_runs").fetchone()
        connection.execute(
            "UPDATE history_runs SET prefix_projection_hash = ?",
            (history_module._prefix_projection_hash_from_row(run),),
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(
            HistoryIntegrityError,
            match="history last_committed_seq is invalid",
        ):
            repository.get_summary("run-unsafe-prefix")


@pytest.mark.parametrize(
    "column",
    ("current_state", "current_phase", "started_at", "last_committed_at"),
)
def test_incomplete_summary_binds_derived_prefix_fields(
    tmp_path: Path,
    column: str,
) -> None:
    path = tmp_path / f"history-incomplete-{column}.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-prefix", "host-1"))
        observer.on_event(_envelope(record, 1, StateChanged(SessionState.RUNNING)))
        observer.on_event(_envelope(record, 2, PhaseChanged("execute")))
        observer.flush()
    values = {
        "current_state": "paused",
        "current_phase": "forged",
        "started_at": "2026-01-02T03:04:04.123456Z",
        "last_committed_at": "2026-01-02T03:04:06.123456Z",
    }
    connection = connect_history_writer(path)
    try:
        connection.execute(
            f"UPDATE history_runs SET {column} = ?",
            (values[column],),
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="prefix projection"):
            repository.get_summary("run-prefix")


def test_fresh_observer_rejects_a_tampered_incomplete_prefix(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    context = HistoryContext("run-prefix-replay", "host-1")
    event = _envelope(record, 1, PhaseChanged("execute"))
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(event)
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute("UPDATE history_runs SET current_phase = 'forged'")
    finally:
        connection.close()

    with HistoryStore(path, clock=FakeClock()) as store:
        with pytest.raises(HistoryIntegrityError, match="prefix projection"):
            store.observer(record, context)


def test_event_readback_validates_duplicate_link_against_canonical_item(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    first = _item(1)
    second = _item(2)
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-link", "host-1"))
        observer.on_event(_envelope(record, 1, first))
        observer.on_event(_envelope(record, 2, second))
        observer.on_event(_envelope(record, 3, first))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        row = connection.execute(
            """SELECT payload_hash, item_payload_hash FROM history_events
                WHERE event_seq = 3"""
        ).fetchone()
        receipt_hash = history_module._receipt_hash(
            event_seq=3,
            event_at=history_module.encode_utc(NOW),
            schema_version=CORE_EVENT_SCHEMA_VERSION,
            body_type="ItemOutcome",
            disposition=history_module.HistoryEventDisposition.DUPLICATE,
            payload_hash=bytes(row["payload_hash"]),
            item_identity_hash=history_module._hash(
                {"item_type": first.item_type, "item_id": first.item_id}
            ),
            item_payload_hash=bytes(row["item_payload_hash"]),
            duplicate_of_seq=2,
        )
        with _without_history_triggers(connection, "history_events_append_only_update"):
            connection.execute(
                """UPDATE history_events
                  SET duplicate_of_seq = 2, receipt_hash = ?
                WHERE event_seq = 3""",
                (receipt_hash,),
            )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="canonical item"):
            repository.get_event_page("run-link")


def test_event_readback_rejects_duplicate_json_members_after_hash_validation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    item = _item(1)
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext("run-duplicate-json", "host-1"),
        )
        observer.on_event(_envelope(record, 1, item))
        observer.flush()

    connection = connect_history_writer(path)
    try:
        row = connection.execute(
            "SELECT * FROM history_events WHERE event_seq = 1"
        ).fetchone()
        envelope_text = str(row["envelope_json"])
        duplicate = envelope_text.replace(
            '"schema_version":5',
            '"schema_version":5,"schema_version":5',
            1,
        )
        assert duplicate != envelope_text
        payload_hash = history_module.hashlib.sha256(
            duplicate.encode("utf-8")
        ).digest()
        receipt_hash = history_module._receipt_hash(
            event_seq=int(row["event_seq"]),
            event_at=str(row["event_at"]),
            schema_version=int(row["schema_version"]),
            body_type=str(row["body_type"]),
            disposition=history_module.HistoryEventDisposition(
                row["event_disposition"]
            ),
            payload_hash=payload_hash,
            item_identity_hash=bytes(row["item_identity_hash"]),
            item_payload_hash=bytes(row["item_payload_hash"]),
            duplicate_of_seq=row["duplicate_of_seq"],
            rejection_reason=row["rejection_reason"],
            item_order=int(row["item_order"]),
        )
        with _without_history_triggers(connection, "history_events_append_only_update"):
            connection.execute(
                """UPDATE history_events
                  SET envelope_json = ?, payload_hash = ?, receipt_hash = ?
                WHERE event_seq = 1""",
                (duplicate, payload_hash, receipt_hash),
            )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="invalid JSON"):
            repository.get_event_page("run-duplicate-json")
        with pytest.raises(HistoryIntegrityError, match="invalid JSON"):
            repository.get_item_page("run-duplicate-json")


def test_page_readback_rejects_a_watermark_past_its_durable_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute(
            """UPDATE history_runs
                  SET last_committed_seq = 2, item_count = 2
                WHERE run_token = 'run-1'"""
        )
        run = connection.execute("SELECT * FROM history_runs").fetchone()
        connection.execute(
            "UPDATE history_runs SET prefix_projection_hash = ?",
            (history_module._prefix_projection_hash_from_row(run),),
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="item watermark"):
            repository.get_item_page("run-1")
        with pytest.raises(HistoryIntegrityError, match="event watermark"):
            repository.get_event_page("run-1")
        with pytest.raises(HistoryIntegrityError, match="event watermark"):
            repository.get_event_page("run-1", through_seq=1)
        with pytest.raises(HistoryIntegrityError, match="event watermark"):
            repository.get_event_page("run-1", after_seq=3)


def test_event_page_rejects_rows_past_an_official_zero_watermark(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, PhaseChanged("scan")))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute(
            """UPDATE history_runs SET last_committed_seq = 0
                WHERE run_token = 'run-1'"""
        )
        run = connection.execute("SELECT * FROM history_runs").fetchone()
        connection.execute(
            "UPDATE history_runs SET prefix_projection_hash = ?",
            (history_module._prefix_projection_hash_from_row(run),),
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="event watermark"):
            repository.get_event_page("run-1")


def test_event_page_accepts_an_official_zero_watermark(tmp_path: Path) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.finalize(OperationResult(SessionState.COMPLETED))
        with HistoryRepository(store.path) as repository:
            page = repository.get_event_page("run-1")

    assert page.through_seq == 0
    assert page.next_after_seq == 0
    assert page.events == ()
    assert not page.has_more


def test_history_sequence_admission_does_not_scan_prior_hashes(tmp_path: Path) -> None:
    class NonIterableHashes(dict[int, bytes]):
        def __iter__(self):
            raise AssertionError("sequence admission scanned all prior hashes")

        def keys(self):
            raise AssertionError("sequence admission scanned all prior hashes")

        def values(self):
            raise AssertionError("sequence admission scanned all prior hashes")

        def items(self):
            raise AssertionError("sequence admission scanned all prior hashes")

    record = _record()
    policy = HistoryWindowPolicy(max_events=256)
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer._event_hashes = NonIterableHashes()
        for sequence in range(1, 101):
            observer.on_event(_envelope(record, sequence, _item(sequence)))
        assert observer._highest_event_seq == 100


@pytest.mark.parametrize("text", ("\ud800", "\udcff", "\ud83d\ude00"))
@pytest.mark.parametrize("position", ("key", "value"))
def test_history_json_rejects_nested_surrogate_code_units(text: str, position: str) -> None:
    nested = {text: "scalar"} if position == "key" else {"scalar": text}
    with pytest.raises(UnicodeEncodeError):
        history_module._json_bytes({"nested": [nested]})


def test_history_json_preserves_valid_unicode_bytes() -> None:
    value = {"nested": [{"\u00e9": "\U0001f600", "literal": r"\ud800"}]}
    expected = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    assert history_module._json_bytes(value) == expected
    assert json.loads(expected) == value


@pytest.mark.parametrize("text", ("\ud800", "\udcff", "\ud83d\ude00"))
def test_history_rejects_malformed_required_context_before_writing(
    tmp_path: Path, text: str,
) -> None:
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        with closing(connect_history_reader(store.path)) as connection:
            before = tuple(connection.iterdump())
        with pytest.raises(UnicodeEncodeError):
            store.observer(_record(), HistoryContext("run-1", "host-" + text))
        with closing(connect_history_reader(store.path)) as connection:
            assert tuple(connection.iterdump()) == before


def test_unpaired_surrogate_diagnostic_is_omitted_before_history_json(
    tmp_path: Path,
) -> None:
    record = _record("e" * 32)
    hostile = "bad_\udcff"
    item = ItemOutcome(
        "f" * 32,
        "noop",
        "safe.txt",
        Outcome.SKIPPED,
        detail={"message": hostile},
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(
            record, HistoryContext("run-hostile", "host-1")
        )
        observer.on_event(_envelope(record, 1, item))
        observer.finalize(OperationResult(SessionState.COMPLETED, items=(item,)))
        with HistoryRepository(store.path) as repository:
            page = repository.get_item_page("run-hostile")
    assert page.items[0].item == item
    assert dict(item.detail) == {}
    assert item.detail_omitted_count == 1


def test_summary_primitive_aggregates_cover_operation_and_integrity_results(
    tmp_path: Path,
) -> None:
    record = _record()
    blocked = _item(1, Outcome.BLOCKED)
    integrity = IntegrityOutcome(
        item_id="row-1",
        row_id="1",
        location_id="8",
        path="1.bin",
        result=IntegrityResult.MISMATCHED,
        reason=IntegrityReason.HASH_MISMATCH,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, blocked))
        observer.on_event(_envelope(record, 2, integrity))
        observer.finalize(
            OperationResult(SessionState.COMPLETED, items=(blocked, integrity))
        )
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")
    assert summary.blocked_count == 1
    assert summary.classification == HistoryClassificationAggregate(
        operation_results=frozenset({"blocked"}),
        selected_operation_count=1,
        selected_other_operation_count=1,
        integrity_results=frozenset({"mismatched"}),
        verify_phase_baseline=False,
    )


def test_summary_classification_objects_are_bounded_for_many_exact_items(
    tmp_path: Path,
) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        for sequence in range(1, 301):
            observer.on_event(
                _envelope(
                    record,
                    sequence,
                    ItemOutcome(
                        f"{sequence:032x}",
                        "copy",
                        f"{sequence}.bin",
                        Outcome.SKIPPED,
                    ),
                )
            )
        observer.finalize(OperationResult(SessionState.COMPLETED))
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")

    assert summary.classification.operation_results == frozenset({"skipped"})
    assert summary.classification.selected_operation_count == 300
    assert summary.classification.selected_other_operation_count == 300


def test_terminal_phase_count_is_bounded_by_the_result_contract(tmp_path: Path) -> None:
    accepted = tuple(
        PhaseResult(f"phase-{index}", PhaseStatus.COMPLETED, 0, 0, 0, 0)
        for index in range(MAX_HISTORY_PHASES)
    )
    rejected = tuple(
        PhaseResult(f"phase-{index}", PhaseStatus.COMPLETED, 0, 0, 0, 0)
        for index in range(MAX_HISTORY_PHASES + 1)
    )
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        allowed = store.observer(record, HistoryContext("run-allowed", "host-1"))
        allowed.finalize(
            OperationResult(SessionState.COMPLETED, phases=accepted)
        )
        forged = OperationResult(SessionState.COMPLETED, phases=accepted)
        object.__setattr__(forged, "phases", rejected)
        refused = store.observer(
            record,
            HistoryContext("run-rejected", "host-1"),
        )
        with pytest.raises(
            HistoryIntegrityError,
            match="supports at most",
        ):
            refused.finalize(forged)
        with HistoryRepository(store.path) as repository:
            assert (
                len(repository.get_summary("run-allowed").phases)
                == MAX_HISTORY_PHASES
            )
            with pytest.raises(KeyError):
                repository.get_summary("run-rejected")


def test_terminal_summary_text_accepts_exact_utf8_byte_bounds(
    tmp_path: Path,
) -> None:
    phase = PhaseResult(
        "p" * MAX_HISTORY_PHASE_NAME_BYTES,
        PhaseStatus.FAILED,
        0,
        0,
        0,
        0,
        "\N{LATIN SMALL LETTER E WITH ACUTE}"
        * (MAX_HISTORY_ERROR_MESSAGE_BYTES // 2),
    )
    error = FailureDetail(
        "E" * MAX_HISTORY_ERROR_TYPE_BYTES,
        "\N{LATIN SMALL LETTER E WITH ACUTE}"
        * (MAX_HISTORY_ERROR_MESSAGE_BYTES // 2),
    )
    result = OperationResult(
        SessionState.FAILED,
        phases=(phase,),
        error=error,
    )
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        store.observer(
            record, HistoryContext("run-bounded", "host-1")
        ).finalize(result)
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-bounded")

    assert summary.phases[0].phase == phase
    assert summary.error_type == error.type_name
    assert summary.error_message == error.message


def test_oversized_terminal_phase_name_is_refused_before_terminal_write(
    tmp_path: Path,
) -> None:
    result = OperationResult(
        SessionState.FAILED,
        phases=(
            PhaseResult(
                "p" * (MAX_HISTORY_PHASE_NAME_BYTES + 1),
                PhaseStatus.FAILED,
                0,
                0,
                0,
                0,
            ),
        ),
    )
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(
            record, HistoryContext("run-oversized", "host-1")
        )
        observer.on_event(
            _envelope(record, 1, StateChanged(SessionState.RUNNING))
        )
        observer.flush()

        with pytest.raises(HistoryIntegrityError, match="terminal phase name"):
            observer.finalize(result)

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-oversized")

    assert not summary.finalized
    assert summary.last_committed_seq == 1
    assert summary.phases == ()


@pytest.mark.parametrize(
    ("result", "has_phase"),
    (
        (
            OperationResult(
                SessionState.FAILED,
                phases=(
                    PhaseResult(
                        "execute",
                        PhaseStatus.FAILED,
                        0,
                        0,
                        0,
                        0,
                        "x" * (MAX_HISTORY_ERROR_MESSAGE_BYTES + 1),
                    ),
                ),
            ),
            True,
        ),
        (
            OperationResult(
                SessionState.FAILED,
                error=FailureDetail(
                    "E" * (MAX_HISTORY_ERROR_TYPE_BYTES + 1),
                    "failed",
                ),
            ),
            False,
        ),
        (
            OperationResult(
                SessionState.FAILED,
                error=FailureDetail(
                    "Error",
                    "x" * (MAX_HISTORY_ERROR_MESSAGE_BYTES + 1),
                ),
            ),
            False,
        ),
    ),
)
def test_oversized_terminal_diagnostics_are_omitted_without_truncation(
    tmp_path: Path,
    result: OperationResult,
    has_phase: bool,
) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(
            record, HistoryContext("run-oversized", "host-1")
        )
        observer.on_event(
            _envelope(record, 1, StateChanged(SessionState.RUNNING))
        )
        observer.flush()

        observer.finalize(result)

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-oversized")

    assert summary.finalized
    assert summary.last_committed_seq == 1
    assert summary.omitted_detail_count == 1
    assert summary.error_type is None
    assert summary.error_message is None
    if has_phase:
        assert summary.phases[0].phase.error is None
    else:
        assert summary.phases == ()


@pytest.mark.parametrize(
    "tamper_sql",
    (
        "UPDATE history_runs SET error_message = 'changed' "
        "WHERE run_token = 'run-tampered'",
        "UPDATE history_phases SET error = 'changed' WHERE phase_order = 0",
    ),
)
def test_summary_and_repeat_finalize_reject_tampered_terminal_payload(
    tmp_path: Path,
    tamper_sql: str,
) -> None:
    record = _record()
    context = HistoryContext("run-tampered", "host-1")
    result = OperationResult(
        SessionState.FAILED,
        phases=(
            PhaseResult(
                "execute",
                PhaseStatus.FAILED,
                0,
                0,
                0,
                0,
                "original phase failure",
            ),
        ),
        error=FailureDetail("OSError", "original terminal failure"),
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.finalize(result)
        connection = connect_history_writer(store.path)
        with closing(connection), _without_history_triggers(connection, "history_runs_finalized_update"):
            connection.execute(tamper_sql)

        with HistoryRepository(store.path) as repository:
            with pytest.raises(
                HistoryIntegrityError, match="payload hash disagrees"
            ):
                repository.get_summary("run-tampered")
            with pytest.raises(
                HistoryIntegrityError, match="payload hash disagrees"
            ):
                repository.list_summaries()

        with pytest.raises(
            HistoryIntegrityError, match="payload hash disagrees"
        ):
            observer.finalize(result)


@pytest.mark.parametrize(
    "tamper_sql",
    (
        "UPDATE history_runs SET current_phase = 'forged'",
        "UPDATE history_runs SET started_at = "
        "'2026-01-02T03:04:04.123456Z'",
        "UPDATE history_runs SET last_committed_at = "
        "'2026-01-02T03:04:06.123456Z'",
        "UPDATE history_runs SET ended_at = "
        "'2026-01-02T03:04:06.123456Z'",
    ),
)
def test_finalized_summary_binds_derived_state_and_timestamps(
    tmp_path: Path,
    tamper_sql: str,
) -> None:
    path = tmp_path / "history-derived.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-derived", "host-1"))
        observer.on_event(_envelope(record, 1, StateChanged(SessionState.RUNNING)))
        observer.on_event(_envelope(record, 2, PhaseChanged("execute")))
        observer.finalize(OperationResult(SessionState.COMPLETED))
    connection = connect_history_writer(path)
    with closing(connection), _without_history_triggers(connection, "history_runs_finalized_update"):
        connection.execute(tamper_sql)

    with HistoryRepository(path) as repository:
        with pytest.raises(
            HistoryIntegrityError, match="prefix projection|payload hash"
        ):
            repository.get_summary("run-derived")
    with HistoryStore(path, clock=FakeClock()) as store:
        with pytest.raises(
            HistoryIntegrityError, match="prefix projection|payload hash"
        ):
            store.observer(record, HistoryContext("run-derived", "host-1"))


@pytest.mark.parametrize(
    "tamper_sql",
    (
        "UPDATE history_runs SET host_key = 'other-host' "
        "WHERE run_token = 'run-context-tampered'",
        "UPDATE history_runs SET source_context = NULL "
        "WHERE run_token = 'run-context-tampered'",
    ),
)
def test_summary_and_repeat_finalize_reject_tampered_context_columns(
    tmp_path: Path,
    tamper_sql: str,
) -> None:
    record = _record()
    context = HistoryContext(
        "run-context-tampered",
        "host-1",
        subject_kind="mapping",
        subject_id="mapping-1",
        source_context="source",
        target_context="target",
    )
    result = OperationResult(SessionState.COMPLETED)
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.finalize(result)
        connection = connect_history_writer(store.path)
        with closing(connection), _without_history_triggers(connection, "history_runs_finalized_update"):
            connection.execute(tamper_sql)

        with HistoryRepository(store.path) as repository:
            with pytest.raises(
                HistoryIntegrityError, match="context hash disagrees"
            ):
                repository.get_summary("run-context-tampered")
            with pytest.raises(
                HistoryIntegrityError, match="context hash disagrees"
            ):
                repository.list_summaries()

        with pytest.raises(
            HistoryIntegrityError, match="context hash disagrees"
        ):
            observer.finalize(result)


def test_schema_rejects_terminal_summary_text_beyond_byte_bounds(
    tmp_path: Path,
) -> None:
    record = _record()
    result = OperationResult(
        SessionState.FAILED,
        phases=(
            PhaseResult(
                "execute",
                PhaseStatus.FAILED,
                0,
                0,
                0,
                0,
                "phase failure",
            ),
        ),
        error=FailureDetail("OSError", "terminal failure"),
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        store.observer(
            record, HistoryContext("run-schema-bounds", "host-1")
        ).finalize(result)
        connection = connect_history_writer(store.path)
        with closing(connection), _without_history_triggers(connection, "history_runs_finalized_update"):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE history_runs SET error_message = ?",
                    ("x" * (MAX_HISTORY_ERROR_MESSAGE_BYTES + 1),),
                )
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE history_phases SET phase = ?",
                    ("x" * (MAX_HISTORY_PHASE_NAME_BYTES + 1),),
                )


def test_history_page_queries_use_paging_and_aggregate_indexes(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    with HistoryStore(path, clock=FakeClock()):
        pass
    connection = connect_history_reader(path)
    try:
        item_plan = " ".join(
            str(column)
            for row in connection.execute(
                """EXPLAIN QUERY PLAN SELECT * FROM history_events
                    WHERE run_id = 1 AND item_order > 0 AND item_order <= 10
                    ORDER BY item_order LIMIT 10"""
            )
            for column in row
        )
        event_plan = " ".join(
            str(column)
            for row in connection.execute(
                """EXPLAIN QUERY PLAN SELECT * FROM history_events
                    WHERE run_id = 1 AND event_seq > 0 AND event_seq <= 10
                    ORDER BY event_seq LIMIT 11"""
            )
            for column in row
        )
        event_watermark_plan = " ".join(
            str(column)
            for row in connection.execute(
                """EXPLAIN QUERY PLAN SELECT event_seq FROM history_events
                    WHERE run_id = 1
                    ORDER BY event_seq DESC LIMIT 1"""
            )
            for column in row
        )
        aggregate_plan = " ".join(
            str(column)
            for row in connection.execute(
                """EXPLAIN QUERY PLAN
                   SELECT run_id,
                          SUM(CASE WHEN item_type = 'operation'
                                   THEN 1 ELSE 0 END)
                         FROM history_events
                              INDEXED BY history_events_run_item_aggregate_idx
                    WHERE run_id = 1 AND item_order IS NOT NULL
                    GROUP BY run_id"""
            )
            for column in row
        )
        identity_plan = " ".join(
            str(column)
            for row in connection.execute(
                """EXPLAIN QUERY PLAN
                   SELECT event_seq FROM history_events
                        INDEXED BY history_events_run_identity_hash_idx
                    WHERE run_id = 1
                      AND item_identity_hash IN (zeroblob(32), randomblob(32))
                      AND (
                          event_disposition = 'recorded'
                          OR (
                              event_disposition = 'rejected'
                              AND duplicate_of_seq IS NULL
                          )
                      )
                      AND event_seq <= 10
                    """
            )
            for column in row
        )
    finally:
        connection.close()
    assert "history_events_run_item_order_idx" in item_plan
    assert "USING PRIMARY KEY" in event_plan
    assert "USING PRIMARY KEY" in event_watermark_plan
    assert "history_events_run_item_aggregate_idx" in aggregate_plan
    assert "history_events_run_identity_hash_idx" in identity_plan


def test_history_failure_does_not_mutate_domain_result(tmp_path: Path) -> None:
    record = _record()
    result = OperationResult(SessionState.COMPLETED)
    store = HistoryStore(tmp_path / "history.db", clock=FakeClock())
    observer = store.observer(record, HistoryContext("run-1", "host-1"))
    store.close()

    with pytest.raises(RecordingError):
        observer.finalize(result)
    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.OK
    assert result.audit is RecordingStatus.OK


def test_history_event_failure_retires_traceback_and_cause_before_propagating_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    errors = []
    retained = []
    record = _record()
    store = HistoryStore(tmp_path / "history.db", clock=FakeClock())
    observer = store.observer(record, HistoryContext("run-event-error", "host-1"))

    def fail_projection(envelope):
        del envelope
        _raise_private_history_failure(
            errors,
            retained,
            "history event projection failed",
        )

    monkeypatch.setattr(history_module, "envelope_to_dict", fail_projection)
    try:
        with pytest.raises(
            RecordingError,
            match="history event projection failed",
        ) as raised:
            observer.on_event(_envelope(record, 1, PhaseChanged("scan")))

        assert raised.value is errors[0]
        assert errors[0].__cause__ is None
        assert errors[0].__context__ is None
        assert retained[0]() is None
        assert observer.pending_event_count == 0
        with pytest.raises(HistoryIntegrityError, match="observer is degraded"):
            observer.on_event(_envelope(record, 1, PhaseChanged("scan")))
    finally:
        observer.close()
        store.close()


def test_invalid_event_projection_breaks_prefix_before_queue_or_durable_mutation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    first = _envelope(record, 1, PhaseChanged("scan"))
    first_size = len(history_module._json_bytes(envelope_to_dict(first)))
    store = HistoryStore(
        path,
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(
            max_bytes=first_size + 1,
            max_event_bytes=first_size + 1,
        ),
    )
    observer = store.observer(record, HistoryContext("run-invalid", "host-1"))
    observer.on_event(first)
    pending_bytes = observer.pending_bytes
    projection_calls = 0
    encoding_calls = 0

    def invalid_projection(envelope: Envelope) -> dict[str, object]:
        nonlocal projection_calls
        projection_calls += 1
        projection = envelope_to_dict(envelope)
        projection["body"] = {"phase": 7}
        return projection

    def checked_encoding(value: object) -> bytes:
        nonlocal encoding_calls
        encoding_calls += 1
        return validate_and_encode_event_v5_envelope(value)

    monkeypatch.setattr(history_module, "envelope_to_dict", invalid_projection)
    monkeypatch.setattr(
        history_module,
        "validate_and_encode_event_v5_envelope",
        checked_encoding,
    )
    try:
        with pytest.raises(
            HistoryIntegrityError,
            match="history event projection is invalid",
        ) as raised:
            observer.on_event(_envelope(record, 2, PhaseChanged("execute")))

        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None
        assert projection_calls == 1
        assert encoding_calls == 1
        assert observer.pending_event_count == 1
        assert observer.pending_bytes == pending_bytes
    finally:
        observer.close()
        store.close()

    connection = connect_history_reader(path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM history_runs"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM history_events"
        ).fetchone()[0] == 0
    finally:
        connection.close()


@pytest.mark.parametrize(
    "body_type",
    (
        "StateChanged",
        "PhaseChanged",
        "Gap",
        "ItemOutcome",
        "IntegrityOutcome",
    ),
)
def test_history_admission_encodes_each_reliable_fixture_once(
    tmp_path: Path,
    monkeypatch,
    body_type: str,
) -> None:
    record = _record(SESSION_ID)
    admitted = envelope_from_dict(event_v5_envelope(body_type))
    calls = 0

    def counted_encoding(value: object) -> bytes:
        nonlocal calls
        calls += 1
        return validate_and_encode_event_v5_envelope(value)

    monkeypatch.setattr(
        history_module,
        "validate_and_encode_event_v5_envelope",
        counted_encoding,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-count", "host-1"))
        observer.on_event(admitted)

        assert calls == 1
        assert observer.pending_event_count == 1


def test_history_flush_failure_preserves_window_and_retires_traceback_and_cause(
    tmp_path: Path,
    monkeypatch,
) -> None:
    errors = []
    retained = []
    record = _record()
    store = HistoryStore(tmp_path / "history.db", clock=FakeClock())
    observer = store.observer(record, HistoryContext("run-flush-error", "host-1"))
    observer.on_event(_envelope(record, 1, PhaseChanged("scan")))

    def fail_transaction(operation):
        del operation
        _raise_private_history_failure(
            errors,
            retained,
            "history window commit failed",
        )

    monkeypatch.setattr(store._writer, "transact", fail_transaction)
    try:
        with pytest.raises(
            RecordingError,
            match="history window commit failed",
        ) as raised:
            observer.flush()

        assert raised.value is errors[0]
        assert errors[0].__cause__ is None
        assert errors[0].__context__ is None
        assert retained[0]() is None
        assert observer.pending_event_count == 1
        with pytest.raises(HistoryIntegrityError, match="observer is degraded"):
            observer.flush()
    finally:
        observer.close()
        store.close()
