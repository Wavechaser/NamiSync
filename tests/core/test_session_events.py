from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, dataclass, fields, replace
from datetime import datetime, timedelta, timezone
import gc
from inspect import signature
import subprocess
import sys
from weakref import ref

import pytest
from xxhash import xxh3_128

import namisync.core.session as session_module
from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    HasherContractError,
    HasherFactory,
    Outcome,
    Provenance,
    RecordingStatus,
    finish_content_hasher,
    new_content_hasher,
    update_content_hasher,
)
from namisync.core.events import (
    CORE_EVENT_SCHEMA_VERSION,
    DetailProjection,
    Envelope,
    Gap,
    ItemOutcome,
    PhaseChanged,
    Progress,
    StateChanged,
    Terminal,
    TerminalSummary,
    envelope_from_dict,
    envelope_to_dict,
    project_detail,
    result_item_to_dict,
    terminal_summary_to_dict,
)
from namisync.core.execution import (
    ItemRecordingReason,
    TaskRecordingIssue,
    TaskRecordingIssueReason,
)
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
    ReadStrategy,
    RecordDisposition,
)
from namisync.core.models import EntryKind, FileStat, MetadataSnapshot
from namisync.core.session import (
    LEGAL_TRANSITIONS,
    MAX_OPERATION_RESULT_PHASES,
    MAX_SESSION_RESULT_ITEMS,
    Canceled,
    Disposition,
    FailureDetail,
    IllegalTransition,
    OperationResult,
    PauseRequested,
    PhaseResult,
    PhaseStatus,
    ResourceId,
    ResultItem,
    RunOutcome,
    SessionId,
    SessionRecord,
    SessionState,
    StoredSessionRecord,
    is_terminal,
    normalize_result_diagnostics,
    require_transition,
    result_terminal_state,
    run_session,
)
from namisync.core.scalars import MAX_SAFE_INTEGER
from namisync.dispatcher.store import InMemorySessionStore


class _PrivateExceptionFrameValue:
    pass


def _raise_with_private_frame(
    error: BaseException,
    references: list[ref[_PrivateExceptionFrameValue]],
) -> None:
    private = _PrivateExceptionFrameValue()
    references.append(ref(private))
    raise error


def test_transition_table_accepts_exactly_the_declared_edges() -> None:
    for current in SessionState:
        for requested in SessionState:
            if requested in LEGAL_TRANSITIONS[current]:
                require_transition(current, requested)
            else:
                with pytest.raises(IllegalTransition):
                    require_transition(current, requested)


def test_terminal_members_are_frozen() -> None:
    assert {state for state in SessionState if is_terminal(state)} == {
        SessionState.COMPLETED,
        SessionState.FAILED,
        SessionState.CANCELED,
        SessionState.REFUSED,
    }


def test_phase_changed_requires_nonempty_string_authority() -> None:
    with pytest.raises(TypeError, match="text"):
        PhaseChanged(1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-empty"):
        PhaseChanged("")


def test_content_evidence_requires_xxh3_128_bytes_and_aware_utc() -> None:
    at = datetime(2026, 7, 18, tzinfo=timezone.utc)
    evidence = ContentEvidence(
        "xxh3_128", b"x" * 16, 1, Provenance.COPY_ATTESTED, at
    )
    assert evidence.digest == b"x" * 16
    with pytest.raises(TypeError, match="must be bytes"):
        ContentEvidence("xxh3_128", "x" * 16, 1, Provenance.COPY_ATTESTED, at)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="16 bytes"):
        ContentEvidence("xxh3_128", b"short", 1, Provenance.COPY_ATTESTED, at)
    with pytest.raises(ValueError, match="16 bytes"):
        ContentEvidence(
            "xxh3_128",
            b"x" * 32,
            1,
            Provenance.COPY_ATTESTED,
            at,
        )
    with pytest.raises(ValueError, match="only xxh3_128"):
        ContentEvidence("sha256", b"x" * 16, 1, Provenance.COPY_ATTESTED, at)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="timezone-aware"):
        ContentEvidence(
            "xxh3_128",
            b"x" * 16,
            1,
            Provenance.COPY_ATTESTED,
            datetime(2026, 7, 18),
        )
    with pytest.raises(TypeError, match="FileStat"):
        Attestation(evidence, None)  # type: ignore[arg-type]


def test_attestation_size_invariant_is_real_under_optimized_python() -> None:
    at = datetime(2026, 7, 18, tzinfo=timezone.utc)
    evidence = ContentEvidence(
        "xxh3_128", b"x" * 16, 1, Provenance.READBACK_ATTESTED, at
    )
    subject = FileStat(
        EntryKind.FILE,
        2,
        1,
        None,
        1,
        MetadataSnapshot(0, None),
    )
    with pytest.raises(
        ValueError, match="attestation content size must match its subject"
    ):
        Attestation(evidence, subject)

    program = (
        "from datetime import datetime, timezone\n"
        "from namisync.core.evidence import Attestation, ContentEvidence, "
        "Provenance\n"
        "from namisync.core.models import EntryKind, FileStat, MetadataSnapshot\n"
        "content = ContentEvidence('xxh3_128', b'x' * 16, 1, "
        "Provenance.READBACK_ATTESTED, datetime.now(timezone.utc))\n"
        "subject = FileStat(EntryKind.FILE, 2, 1, None, 1, "
        "MetadataSnapshot(0, None))\n"
        "try:\n"
        "    Attestation(content, subject)\n"
        "except ValueError:\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(1)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-O", "-c", program],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr


def test_streaming_hasher_factory_is_a_standard_structural_contract() -> None:
    factory: HasherFactory = xxh3_128
    hasher = factory()
    hasher.update(b"NamiSync")

    assert hasher.digest() == xxh3_128(b"NamiSync").digest()


def test_shared_content_hasher_lifecycle_preserves_the_exact_error_contract() -> None:
    class _Hasher:
        def __init__(
            self,
            *,
            update_error: BaseException | None = None,
            digest_error: BaseException | None = None,
        ) -> None:
            self.update_error = update_error
            self.digest_error = digest_error

        def update(self, _data: bytes) -> None:
            if self.update_error is not None:
                raise self.update_error

        def digest(self) -> bytes:
            if self.digest_error is not None:
                raise self.digest_error
            return b"x" * 16

    factory_error = ValueError("factory")
    with pytest.raises(
        HasherContractError,
        match="^content hasher factory failed$",
    ) as raised:
        new_content_hasher(
            lambda: (_ for _ in ()).throw(factory_error)
        )
    assert raised.value.__cause__ is factory_error

    with pytest.raises(
        HasherContractError,
        match=r"^content hasher must provide update\(bytes\)$",
    ):
        new_content_hasher(lambda: object())  # type: ignore[arg-type,return-value]
    with pytest.raises(
        HasherContractError,
        match=r"^content hasher must provide digest\(\)$",
    ):
        new_content_hasher(  # type: ignore[arg-type]
            lambda: type("UpdateOnly", (), {"update": lambda *_: None})()
        )

    update_error = ValueError("update")
    with pytest.raises(
        HasherContractError,
        match="^content hasher update failed$",
    ) as raised:
        update_content_hasher(_Hasher(update_error=update_error), b"chunk")
    assert raised.value.__cause__ is update_error

    digest_error = ValueError("digest")
    with pytest.raises(
        HasherContractError,
        match="^content hasher digest failed$",
    ) as raised:
        finish_content_hasher(_Hasher(digest_error=digest_error))
    assert raised.value.__cause__ is digest_error

    for stage in ("factory", "update", "digest"):
        fatal = KeyboardInterrupt(stage)
        with pytest.raises(KeyboardInterrupt) as raised:
            if stage == "factory":
                new_content_hasher(
                    lambda: (_ for _ in ()).throw(fatal)
                )
            elif stage == "update":
                update_content_hasher(_Hasher(update_error=fatal), b"chunk")
            else:
                finish_content_hasher(_Hasher(digest_error=fatal))
        assert raised.value is fatal

    assert finish_content_hasher(_Hasher()) == b"x" * 16


@pytest.mark.parametrize("path", ["success", "cancel", "failure"])
def test_runner_emits_exactly_one_terminal(path: str) -> None:
    emitted: list[object] = []
    settled: list[tuple[SessionState, OperationResult | None]] = []

    def work(context):
        context.emit(
            ItemOutcome("1" * 32, "copy", "file", Outcome.SUCCEEDED)
        )
        if path == "cancel":
            raise Canceled()
        if path == "failure":
            raise RuntimeError("broken")
        return OperationResult(SessionState.COMPLETED)

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: settled.append((state, result)),
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )

    terminals = [body for body in emitted if isinstance(body, Terminal)]
    assert len(terminals) == 1
    assert outcome.result is not None
    assert terminals[0].result == TerminalSummary.from_result(outcome.result)
    assert settled[0][0] is terminals[0].result.status
    if path == "failure":
        assert terminals[0].result.error is not None
        assert terminals[0].result.error.type_name == "RuntimeError"


def test_runner_accumulates_result_item_only_after_emitter_accepts_it() -> None:
    rejected = ItemOutcome(
        "2" * 32, "copy", "file", Outcome.SUCCEEDED
    )
    accepted: list[object] = []

    def emit(body: object) -> None:
        if isinstance(body, ItemOutcome) and body.item_id == rejected.item_id:
            raise RuntimeError("outcome rejected")
        accepted.append(body)

    def work(context):
        context.emit(rejected)
        return OperationResult(SessionState.COMPLETED)

    outcome = run_session(
        work,
        emit=emit,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.items == ()
    assert rejected not in accepted
    terminal = next(body for body in accepted if isinstance(body, Terminal))
    assert terminal.result.recording_degraded_items == 0


def test_runner_reliable_item_degradation_is_terminal_recording_authority() -> None:
    degraded = IntegrityOutcome(
        item_id="degraded",
        row_id="1",
        location_id="1",
        path="file.bin",
        result=IntegrityResult.VERIFIED,
        recording=RecordingStatus.DEGRADED,
    )
    emitted: list[object] = []

    outcome = run_session(
        lambda _context: OperationResult(SessionState.CANCELED, canceled=True),
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=[degraded],
    )

    assert outcome.result is not None
    assert outcome.result.recording is RecordingStatus.DEGRADED
    assert outcome.result.items == (degraded,)
    terminal = next(body for body in emitted if isinstance(body, Terminal))
    assert terminal.result.recording is RecordingStatus.DEGRADED


def test_runner_uses_only_emitter_accepted_progress_as_fallback() -> None:
    accepted_progress = Progress(
        "execute",
        0,
        1,
        5,
        20,
        "file",
        item_id="operation",
        item_type="operation",
        item_attempt_id="a" * 32,
        item_bytes_done=3,
        item_bytes_total=10,
    )
    rejected = Progress(
        "execute",
        0,
        1,
        17,
        20,
        "file",
        item_id="operation",
        item_type="operation",
        item_attempt_id="a" * 32,
        item_bytes_done=3,
        item_bytes_total=10,
    )
    accepted: list[object] = []

    def emit(body: object) -> None:
        if isinstance(body, Progress) and body.bytes_done == rejected.bytes_done:
            raise RuntimeError("progress rejected")
        accepted.append(body)

    def work(context):
        context.emit(accepted_progress)
        context.emit(rejected)
        return OperationResult(SessionState.COMPLETED)

    outcome = run_session(
        work,
        emit=emit,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.bytes_done == 5
    assert outcome.result.bytes_total == 20
    assert accepted_progress in accepted
    assert rejected not in accepted
    terminal = next(body for body in accepted if isinstance(body, Terminal))
    assert terminal.result.bytes_done == 5
    assert terminal.result.bytes_total == 20


def test_runner_pause_has_no_terminal_and_settles_paused() -> None:
    emitted: list[object] = []
    settled: list[tuple[SessionState, OperationResult | None]] = []

    outcome = run_session(
        lambda context: (_ for _ in ()).throw(PauseRequested()),
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: settled.append((state, result)),
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )

    assert outcome.paused
    assert outcome.result is None
    assert settled == [(SessionState.PAUSED, None)]
    assert not any(isinstance(body, Terminal) for body in emitted)


def test_runner_republishes_reliable_items_before_paused_settlement() -> None:
    prior = ItemOutcome("1" * 32, "copy", "prior.txt", Outcome.SUCCEEDED)
    current = ItemOutcome("2" * 32, "copy", "current.txt", Outcome.SUCCEEDED)
    accumulator = [prior]
    seen_during_settle: list[tuple[ResultItem, ...]] = []

    def work(context: RunContext) -> OperationResult:
        context.emit(current)
        raise PauseRequested()

    outcome = run_session(
        work,
        emit=lambda _body: None,
        checkpoint=lambda: None,
        settle=lambda state, result: seen_during_settle.append(tuple(accumulator)),
        finalize_audit=lambda _result: RecordingStatus.OK,
        publish_result=lambda _result: None,
        item_accumulator=accumulator,
    )

    assert outcome.paused
    assert [item.item_id for item in seen_during_settle[0]] == [
        prior.item_id,
        current.item_id,
    ]
    assert accumulator == list(seen_during_settle[0])
    assert all(item is not source for item, source in zip(accumulator, (prior, current)))


def test_compound_cancel_preserves_filesystem_truth_and_projects_lifecycle() -> None:
    phases = (
        PhaseResult(
            "execute",
            PhaseStatus.COMPLETED,
            items_done=1,
            items_total=1,
            bytes_done=7,
            bytes_total=7,
        ),
        PhaseResult(
            "verify",
            PhaseStatus.CANCELED,
            items_done=0,
            items_total=1,
            bytes_done=0,
            bytes_total=7,
        ),
    )
    result = OperationResult(
        SessionState.COMPLETED,
        canceled=True,
        phases=phases,
        bytes_done=7,
        bytes_total=7,
    )
    settled: list[SessionState] = []

    outcome = run_session(
        lambda context: result,
        emit=lambda body: None,
        checkpoint=lambda: None,
        settle=lambda state, value: settled.append(state),
        finalize_audit=lambda value: RecordingStatus.OK,
        publish_result=lambda value: None,
    )

    assert outcome.result == result
    assert outcome.result.status is SessionState.COMPLETED
    assert result_terminal_state(outcome.result) is SessionState.CANCELED
    assert settled == [SessionState.CANCELED]
    record = SessionRecord(
        SessionId("compound-cancel"),
        "sync-execution",
        SessionState.CANCELED,
        (),
        None,
        True,
        1,
        datetime(2026, 7, 18, tzinfo=timezone.utc),
        started_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        ended_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        result=outcome.result,
    )
    assert record.result is not None
    assert record.result.status is SessionState.COMPLETED


def test_session_record_checkpoint_exists_only_while_nonterminal() -> None:
    created_at = datetime(2026, 7, 18, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="terminal session checkpoint"):
        SessionRecord(
            SessionId("terminal-checkpoint"),
            "sync-execution",
            SessionState.COMPLETED,
            (),
            b"stale-continuation",
            True,
            1,
            created_at,
            ended_at=created_at,
        )

    with pytest.raises(TypeError, match="nonterminal workflow checkpoint"):
        SessionRecord(
            SessionId("missing-checkpoint"),
            "sync-execution",
            SessionState.PAUSED,
            (),
            None,
            True,
            2,
            created_at,
        )


def test_session_record_composes_exact_stored_value_with_compatible_constructor() -> None:
    created_at = datetime(2026, 8, 26, tzinfo=timezone.utc)
    resources = (ResourceId("volume", "a"), ResourceId("volume", "b"))
    result = OperationResult(SessionState.COMPLETED)
    record = SessionRecord(
        SessionId("composed-session"),
        "opaque-workflow",
        SessionState.COMPLETED,
        resources,
        None,
        True,
        3,
        created_at,
        started_at=created_at,
        ended_at=created_at,
        result=result,
    )
    equivalent = SessionRecord(
        session_id=record.session_id,
        kind=record.kind,
        state=record.state,
        resources=resources,
        checkpoint=None,
        supports_pause=True,
        admission_order=3,
        created_at=created_at,
        started_at=created_at,
        ended_at=created_at,
        result=result,
    )

    assert str(signature(SessionRecord)) == (
        "(session_id: 'SessionId', kind: 'str', state: 'SessionState', "
        "resources: 'tuple[ResourceId, ...]', checkpoint: 'object | None', "
        "supports_pause: 'bool', admission_order: 'int', "
        "created_at: 'datetime', started_at: 'datetime | None' = None, "
        "ended_at: 'datetime | None' = None, "
        "result: 'OperationResult | None' = None) -> None"
    )
    assert tuple(field.name for field in fields(record)) == (
        "stored",
        "checkpoint",
    )
    assert type(record.stored) is StoredSessionRecord
    assert record.stored.resources is resources
    assert record.stored.result is result
    assert tuple(
        getattr(record, name)
        for name in (
            "session_id",
            "kind",
            "state",
            "resources",
            "supports_pause",
            "admission_order",
            "created_at",
            "started_at",
            "ended_at",
            "result",
        )
    ) == tuple(
        getattr(record.stored, name)
        for name in (
            "session_id",
            "kind",
            "state",
            "resources",
            "supports_pause",
            "admission_order",
            "created_at",
            "started_at",
            "ended_at",
            "result",
        )
    )
    assert record == equivalent
    assert hash(record) == hash(equivalent)
    assert not hasattr(record, "__dict__")
    with pytest.raises(FrozenInstanceError):
        record.checkpoint = b"changed"  # type: ignore[misc]


def test_session_record_constructor_uses_canonical_stored_validation() -> None:
    with pytest.raises(ValueError, match="session id and kind must be non-empty"):
        SessionRecord(
            SessionId("invalid-live-metadata"),
            "",
            SessionState.PENDING,
            (),
            b"continuation",
            False,
            0,
            datetime(2026, 8, 26, tzinfo=timezone.utc),
        )


def _stored_record() -> StoredSessionRecord:
    return StoredSessionRecord(
        session_id=SessionId("stored-session"),
        kind="opaque-workflow",
        state=SessionState.PENDING,
        resources=(ResourceId("volume", "a"), ResourceId("volume", "b")),
        supports_pause=True,
        admission_order=2,
        created_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
    )


def test_stored_session_record_has_exact_frozen_metadata_shape() -> None:
    record = _stored_record()

    assert tuple(field.name for field in fields(record)) == (
        "session_id",
        "kind",
        "state",
        "resources",
        "supports_pause",
        "admission_order",
        "created_at",
        "started_at",
        "ended_at",
        "result",
    )
    assert not hasattr(record, "__dict__")
    assert not hasattr(record, "checkpoint")
    with pytest.raises(FrozenInstanceError):
        record.kind = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("field_name", ["checkpoint", "live_record"])
def test_stored_session_record_rejects_checkpoint_and_live_reference_fields(
    field_name: str,
) -> None:
    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(_stored_record(), **{field_name: b"private continuation"})


@pytest.mark.parametrize("state", tuple(SessionState))
def test_stored_session_record_can_represent_every_lifecycle_without_checkpoint(
    state: SessionState,
) -> None:
    record = _stored_record()
    stored = replace(
        record,
        state=state,
        ended_at=record.created_at if is_terminal(state) else None,
    )

    assert stored.state is state
    assert stored.result is None
    assert not hasattr(stored, "checkpoint")


@pytest.mark.parametrize(
    "changes",
    [
        {"session_id": SessionId("")},
        {"kind": ""},
        {"resources": (ResourceId("volume", "a"), ResourceId("volume", "a"))},
        {"resources": (ResourceId("volume", "b"), ResourceId("volume", "a"))},
        {"admission_order": -1},
        {"state": SessionState.COMPLETED},
        {"ended_at": datetime(2026, 8, 26, tzinfo=timezone.utc)},
        {"result": OperationResult(SessionState.COMPLETED)},
        {
            "state": SessionState.FAILED,
            "ended_at": datetime(2026, 8, 26, tzinfo=timezone.utc),
            "result": OperationResult(SessionState.COMPLETED),
        },
    ],
)
def test_stored_session_record_preserves_metadata_invariants(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        replace(_stored_record(), **changes)


@pytest.mark.parametrize("field_name", ["created_at", "started_at", "ended_at"])
@pytest.mark.parametrize(
    "invalid_time",
    [
        datetime(2026, 8, 26),
        datetime(2026, 8, 26, tzinfo=timezone(timedelta(hours=2))),
    ],
)
def test_stored_session_record_requires_utc_metadata(
    field_name: str, invalid_time: datetime
) -> None:
    record = _stored_record()
    terminal = replace(
        record,
        state=SessionState.COMPLETED,
        started_at=record.created_at,
        ended_at=record.created_at,
    )
    with pytest.raises(ValueError, match=field_name):
        replace(terminal, **{field_name: invalid_time})


@pytest.mark.parametrize("record_kind", ["live", "lookalike", "subclass"])
def test_in_memory_store_rejects_nonexact_records_before_replacing_metadata(
    record_kind: str,
) -> None:
    stored = _stored_record()

    @dataclass(frozen=True, slots=True)
    class CheckpointRecord(StoredSessionRecord):
        checkpoint: object = b"smuggled continuation"

    class Lookalike:
        session_id = stored.session_id
        checkpoint = b"smuggled continuation"

    if record_kind == "live":
        invalid = SessionRecord(
            stored.session_id, stored.kind, stored.state, stored.resources,
            b"private continuation", stored.supports_pause, stored.admission_order,
            stored.created_at,
        )
    elif record_kind == "subclass":
        invalid = CheckpointRecord(
            stored.session_id, stored.kind, stored.state, stored.resources,
            stored.supports_pause, stored.admission_order, stored.created_at,
        )
    else:
        invalid = Lookalike()
    store = InMemorySessionStore()
    store.put(stored)

    with pytest.raises(TypeError, match="exact StoredSessionRecord"):
        store.put(invalid)  # type: ignore[arg-type]

    assert store.snapshot() == (stored,)
    assert store.snapshot()[0] is stored


def test_in_memory_metadata_snapshot_order_does_not_claim_restart_recovery() -> None:
    later = _stored_record()
    earlier = replace(later, session_id=SessionId("earlier"), admission_order=1)
    store = InMemorySessionStore()
    store.put(later)
    store.put(earlier)

    assert store.snapshot() == (earlier, later)
    assert store.snapshot()[0] is earlier
    assert store.snapshot()[1] is later
    assert store.load_all() == ()
    store.drop(earlier.session_id)
    assert store.snapshot() == (later,)


def test_compound_cancel_rejects_inconsistent_execute_or_verify_phase() -> None:
    execute = PhaseResult(
        "execute", PhaseStatus.COMPLETED, 1, 1, 7, 7
    )
    verify = PhaseResult(
        "verify", PhaseStatus.INCOMPLETE, 0, 1, 0, 7
    )
    with pytest.raises(ValueError, match="canceled verify phase"):
        OperationResult(
            SessionState.COMPLETED,
            canceled=True,
            phases=(execute, verify),
        )
    with pytest.raises(ValueError, match="matching execute truth"):
        OperationResult(
            SessionState.FAILED,
            canceled=True,
            phases=(
                execute,
                PhaseResult(
                    "verify", PhaseStatus.CANCELED, 0, 1, 0, 7
                ),
            ),
        )


def test_cancellation_matrix_rejects_contradictory_terminal_truth() -> None:
    completed_execute = PhaseResult(
        "execute", PhaseStatus.COMPLETED, 1, 1, 7, 7
    )
    canceled_verify = PhaseResult(
        "verify", PhaseStatus.CANCELED, 0, 1, 0, 7
    )

    with pytest.raises(ValueError, match="requires canceled=True"):
        OperationResult(SessionState.CANCELED)
    with pytest.raises(ValueError, match="completed execute phase"):
        OperationResult(
            SessionState.CANCELED,
            canceled=True,
            phases=(completed_execute,),
        )
    with pytest.raises(ValueError, match="run disposition"):
        OperationResult(
            SessionState.COMPLETED,
            disposition=Disposition.UNRUN,
            canceled=True,
            phases=(completed_execute, canceled_verify),
        )
    with pytest.raises(ValueError, match="cannot also be canceled"):
        OperationResult(
            SessionState.REFUSED,
            disposition=Disposition.UNRUN,
            canceled=True,
        )


def test_execute_and_unrun_cancellation_preserve_their_disposition() -> None:
    unrun = OperationResult(
        SessionState.CANCELED,
        disposition=Disposition.UNRUN,
        canceled=True,
    )
    ran = OperationResult(
        SessionState.CANCELED,
        disposition=Disposition.RAN,
        canceled=True,
        phases=(
            PhaseResult("execute", PhaseStatus.CANCELED, 0, 1, 0, 7),
        ),
    )

    assert unrun.disposition is Disposition.UNRUN
    assert ran.disposition is Disposition.RAN
    assert result_terminal_state(unrun) is SessionState.CANCELED
    assert result_terminal_state(ran) is SessionState.CANCELED


@pytest.mark.parametrize(
    ("filesystem_status", "execute_status"),
    [
        (SessionState.COMPLETED, PhaseStatus.COMPLETED),
        (SessionState.FAILED, PhaseStatus.FAILED),
    ],
)
def test_verify_cancellation_round_trips_terminal_event_and_session_record(
    filesystem_status: SessionState,
    execute_status: PhaseStatus,
) -> None:
    result = OperationResult(
        filesystem_status,
        disposition=Disposition.RAN,
        canceled=True,
        phases=(
            PhaseResult("execute", execute_status, 1, 1, 7, 7),
            PhaseResult("verify", PhaseStatus.CANCELED, 0, 1, 0, 7),
        ),
        bytes_done=7,
        bytes_total=7,
    )
    envelope = Envelope(
        session_id=SessionId("d" * 32),
        seq=3,
        at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        schema_version=CORE_EVENT_SCHEMA_VERSION,
        body=Terminal(TerminalSummary.from_result(result)),
    )

    decoded = envelope_from_dict(envelope_to_dict(envelope))

    assert isinstance(decoded.body, Terminal)
    assert decoded.body.result == TerminalSummary.from_result(result)
    record = SessionRecord(
        SessionId("verify-canceled"),
        "sync-execution",
        SessionState.CANCELED,
        (),
        None,
        True,
        1,
        datetime(2026, 7, 25, tzinfo=timezone.utc),
        started_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        ended_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        result=result,
    )
    assert record.result is not None
    assert record.result.status is filesystem_status
    assert record.result.canceled
    assert result_terminal_state(record.result) is SessionState.CANCELED
    stored = StoredSessionRecord(
        session_id=record.session_id,
        kind=record.kind,
        state=record.state,
        resources=record.resources,
        supports_pause=record.supports_pause,
        admission_order=record.admission_order,
        created_at=record.created_at,
        started_at=record.started_at,
        ended_at=record.ended_at,
        result=record.result,
    )
    store = InMemorySessionStore()
    store.put(stored)
    restored = store.snapshot()[0]
    assert restored is stored
    assert restored.result is record.result
    assert not hasattr(restored, "checkpoint")
    assert restored.result is not None
    assert restored.result.status is filesystem_status
    assert restored.result.canceled


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(3)])
def test_runner_does_not_normalize_base_exceptions(error: BaseException) -> None:
    emitted: list[object] = []
    settled: list[SessionState] = []

    with pytest.raises(type(error)):
        run_session(
            lambda context: (_ for _ in ()).throw(error),
            emit=emitted.append,
            checkpoint=lambda: None,
            settle=lambda state, result: settled.append(state),
            finalize_audit=lambda result: RecordingStatus.OK,
            publish_result=lambda result: None,
        )

    assert settled == []
    assert not any(isinstance(body, Terminal) for body in emitted)


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(3)])
def test_runner_does_not_normalize_audit_base_exceptions(
    error: BaseException,
) -> None:
    emitted: list[object] = []
    published: list[OperationResult] = []

    with pytest.raises(type(error)):
        run_session(
            lambda context: OperationResult(SessionState.COMPLETED),
            emit=emitted.append,
            checkpoint=lambda: None,
            settle=lambda state, result: None,
            finalize_audit=lambda result: (_ for _ in ()).throw(error),
            publish_result=published.append,
        )

    assert published == []
    assert not any(isinstance(body, Terminal) for body in emitted)


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(3)])
def test_runner_does_not_normalize_diagnostic_base_exceptions(
    error: BaseException,
) -> None:
    class UnprintableError(Exception):
        def __str__(self) -> str:
            raise error

    emitted: list[object] = []
    settled: list[SessionState] = []
    with pytest.raises(type(error)) as caught:
        run_session(
            lambda context: (_ for _ in ()).throw(UnprintableError()),
            emit=emitted.append,
            checkpoint=lambda: None,
            settle=lambda state, result: settled.append(state),
            finalize_audit=lambda result: RecordingStatus.OK,
            publish_result=lambda result: None,
        )

    assert caught.value is error
    assert settled == []
    assert not any(isinstance(body, Terminal) for body in emitted)


def test_runner_rejects_workflow_terminal_without_creating_a_second_one() -> None:
    emitted: list[object] = []

    def work(context):
        context.emit(Terminal(OperationResult(SessionState.COMPLETED)))
        return OperationResult(SessionState.COMPLETED)

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert len([body for body in emitted if isinstance(body, Terminal)]) == 1


def test_runner_rejects_structural_item_guessing_and_retains_nominal_integrity() -> None:
    class OtherItem:
        item_id = "row"
        path = "file"

    emitted: list[object] = []

    def work(context):
        context.emit(OtherItem())
        context.emit(
            IntegrityOutcome(
                item_id="integrity-row",
                row_id="7",
                location_id="3",
                path="file",
                result=IntegrityResult.MISMATCHED,
                reason=IntegrityReason.HASH_MISMATCH,
                read_strategy=ReadStrategy.WINDOWS_UNBUFFERED,
                recording=RecordingStatus.DEGRADED,
                record_disposition=RecordDisposition.STALE,
            )
        )
        raise RuntimeError("broken")

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )

    assert outcome.result is not None
    assert len(outcome.result.items) == 1
    assert isinstance(outcome.result.items[0], IntegrityOutcome)


def test_item_outcome_rejects_nonexact_producer_scalars() -> None:
    class Text(str):
        pass

    with pytest.raises(TypeError, match="item_id must be text"):
        ItemOutcome(Text("item"), "copy", "file", Outcome.SUCCEEDED)
    with pytest.raises(TypeError, match="outcome has the wrong type"):
        ItemOutcome("item", "copy", "file", "succeeded")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="reason must be text"):
        ItemOutcome(
            "item",
            "copy",
            "file",
            Outcome.SKIPPED,
            reason=Text("user-deselected"),
        )


def test_operation_result_admits_at_most_three_phases() -> None:
    phases = tuple(
        PhaseResult(
            f"phase-{index}",
            PhaseStatus.COMPLETED,
            0,
            0,
            0,
            0,
        )
        for index in range(MAX_OPERATION_RESULT_PHASES + 1)
    )

    assert len(OperationResult(SessionState.COMPLETED, phases=phases[:3]).phases) == 3
    with pytest.raises(ValueError, match="phases exceed their bound"):
        OperationResult(SessionState.COMPLETED, phases=phases)


def test_runner_detaches_producer_items_and_exact_result_headers() -> None:
    class HiddenItem(ItemOutcome):
        pass

    class HiddenPhase(PhaseResult):
        pass

    class HiddenResult(OperationResult):
        pass

    producer_refs: list[ref[_PrivateExceptionFrameValue]] = []
    release_checks: list[bool] = []
    producer_detached_checks: list[bool] = []
    emitted: list[object] = []

    def work(context: RunContext) -> OperationResult:
        item_graph = _PrivateExceptionFrameValue()
        producer_refs.append(ref(item_graph))
        item = HiddenItem(
            "6" * 32,
            "copy",
            "reviewed.txt",
            Outcome.SUCCEEDED,
        )
        object.__setattr__(item, "hidden_graph", item_graph)
        context.emit(item)
        producer_detached_checks.append(emitted[-1] is not item)
        object.__setattr__(item, "path", "producer-mutated.txt")

        phase_graph = _PrivateExceptionFrameValue()
        producer_refs.append(ref(phase_graph))
        phase = HiddenPhase(
            "execute",
            PhaseStatus.COMPLETED,
            1,
            1,
            7,
            7,
        )
        object.__setattr__(phase, "hidden_graph", phase_graph)
        result_graph = _PrivateExceptionFrameValue()
        producer_refs.append(ref(result_graph))
        result = HiddenResult(
            SessionState.COMPLETED,
            items=(item,),
            phases=(phase,),
            bytes_done=7,
            bytes_total=7,
        )
        object.__setattr__(result, "hidden_graph", result_graph)
        return result

    def settle(_state: SessionState, result: OperationResult | None) -> None:
        assert result is not None
        gc.collect()
        release_checks.append(all(reference() is None for reference in producer_refs))

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=settle,
        finalize_audit=lambda _result: RecordingStatus.OK,
        publish_result=lambda _result: None,
    )

    assert outcome.result is not None
    assert release_checks == [True]
    assert producer_detached_checks == [True]
    assert type(outcome.result) is OperationResult
    assert type(outcome.result.phases[0]) is PhaseResult
    assert type(outcome.result.items[0]) is ItemOutcome
    assert outcome.result.items[0].path == "reviewed.txt"
    assert emitted[0] == outcome.result.items[0]
    assert emitted[0] is outcome.result.items[0]


def test_runner_releases_a_result_that_fails_snapshot_revalidation() -> None:
    class HiddenResult(OperationResult):
        pass

    producer_refs: list[ref[HiddenResult]] = []
    release_checks: list[bool] = []

    def work(_context: RunContext) -> OperationResult:
        result = HiddenResult(SessionState.COMPLETED)
        producer_refs.append(ref(result))
        object.__setattr__(result, "status", SessionState.RUNNING)
        return result

    def settle(_state: SessionState, _result: OperationResult | None) -> None:
        gc.collect()
        release_checks.append(producer_refs[-1]() is None)

    outcome = run_session(
        work,
        emit=lambda _body: None,
        checkpoint=lambda: None,
        settle=settle,
        finalize_audit=lambda _result: RecordingStatus.OK,
        publish_result=lambda _result: None,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.error == FailureDetail(
        "ValueError",
        "operation result status must be terminal",
    )
    assert release_checks == [True]


def test_runner_uses_a_detached_progress_snapshot_for_terminal_fallback() -> None:
    progress = Progress("execute", 1, 2, 5, 9, "reviewed.txt")
    emitted: list[object] = []

    def work(context: RunContext) -> OperationResult:
        context.emit(progress)
        object.__setattr__(progress, "bytes_done", 9)
        raise Canceled()

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda _state, _result: None,
        finalize_audit=lambda _result: RecordingStatus.OK,
        publish_result=lambda _result: None,
    )

    assert outcome.result is not None
    assert (outcome.result.bytes_done, outcome.result.bytes_total) == (5, 9)
    assert type(emitted[0]) is Progress
    assert emitted[0].bytes_done == 5


def test_runner_keeps_private_progress_truth_from_the_emitter() -> None:
    progress = Progress("execute", 1, 1, 5, 9, "reviewed.txt")
    public: list[object] = []

    def emit(body: object) -> None:
        public.append(body)
        if isinstance(body, Progress):
            object.__setattr__(body, "bytes_done", 9)

    def work(context: RunContext) -> OperationResult:
        context.emit(progress)
        return OperationResult(
            SessionState.COMPLETED,
            bytes_done=5,
            bytes_total=9,
        )

    outcome = run_session(
        work,
        emit=emit,
        checkpoint=lambda: None,
        settle=lambda _state, _result: None,
        finalize_audit=lambda _result: RecordingStatus.OK,
        publish_result=lambda _result: None,
    )

    assert outcome.result is not None
    assert (outcome.result.bytes_done, outcome.result.bytes_total) == (5, 9)
    assert isinstance(public[0], Progress)
    assert public[0].bytes_done == 9


def test_runner_seeds_cancel_result_from_prior_pause_items() -> None:
    prior = [ItemOutcome("3" * 32, "copy", "file", Outcome.SUCCEEDED)]
    outcome = run_session(
        lambda context: (_ for _ in ()).throw(Canceled()),
        emit=lambda body: None,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=prior,
    )
    assert outcome.result is not None
    assert outcome.result.items == tuple(prior)


def test_runner_success_merges_prior_pause_and_new_items_in_emission_order() -> None:
    prior = ItemOutcome("4" * 32, "copy", "prior.txt", Outcome.SUCCEEDED)
    current = IntegrityOutcome(
        "current",
        "row",
        "location",
        "current.txt",
        IntegrityResult.VERIFIED,
    )

    def work(context):
        context.emit(current)
        return OperationResult(SessionState.COMPLETED, items=(current,))

    outcome = run_session(
        work,
        emit=lambda body: None,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=[prior],
    )

    assert outcome.result is not None
    assert outcome.result.items == (prior, current)


def test_runner_rejects_an_excess_resume_accumulator_before_work() -> None:
    item = ItemOutcome("4" * 32, "copy", "prior.txt", Outcome.SUCCEEDED)
    prior = [item] * (MAX_SESSION_RESULT_ITEMS + 1)
    calls: list[str] = []
    emitted: list[object] = []
    settled: list[tuple[SessionState, OperationResult | None]] = []
    audited: list[OperationResult] = []
    published: list[OperationResult] = []

    outcome = run_session(
        lambda context: calls.append("work")
        or OperationResult(SessionState.COMPLETED),
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: settled.append((state, result)),
        finalize_audit=lambda result: audited.append(result) or RecordingStatus.OK,
        publish_result=published.append,
        item_accumulator=prior,
    )

    assert calls == []
    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.items == ()
    assert outcome.result.error == FailureDetail(
        "ValueError",
        "session result items exceed their session bound",
    )
    assert settled == [(SessionState.FAILED, audited[0])]
    assert published == [outcome.result]
    assert emitted == [Terminal(TerminalSummary.from_result(outcome.result))]
    assert len(prior) == MAX_SESSION_RESULT_ITEMS + 1


def test_runner_checks_the_next_item_before_event_or_accumulator_mutation() -> None:
    prior_item = ItemOutcome("4" * 32, "copy", "prior.txt", Outcome.SUCCEEDED)
    excess_item = ItemOutcome("5" * 32, "copy", "excess.txt", Outcome.SUCCEEDED)
    prior = [prior_item] * MAX_SESSION_RESULT_ITEMS
    emitted: list[object] = []

    def work(context):
        context.emit(excess_item)
        raise AssertionError("item-limit failure did not stop workflow")

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=prior,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert len(outcome.result.items) == MAX_SESSION_RESULT_ITEMS
    assert outcome.result.error == FailureDetail(
        "RuntimeError",
        "session result items exceed their session bound",
    )
    assert excess_item not in emitted
    assert prior == [prior_item] * MAX_SESSION_RESULT_ITEMS


def test_runner_allows_the_last_item_and_refuses_only_the_first_excess() -> None:
    prior_item = ItemOutcome("4" * 32, "copy", "prior.txt", Outcome.SUCCEEDED)
    last_item = ItemOutcome("5" * 32, "copy", "last.txt", Outcome.SUCCEEDED)
    excess_item = ItemOutcome("6" * 32, "copy", "excess.txt", Outcome.SUCCEEDED)
    prior = [prior_item] * (MAX_SESSION_RESULT_ITEMS - 1)
    emitted: list[object] = []

    def work(context):
        context.emit(last_item)
        context.emit(excess_item)
        raise AssertionError("item-limit failure did not stop workflow")

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=prior,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert len(outcome.result.items) == MAX_SESSION_RESULT_ITEMS
    assert outcome.result.error == FailureDetail(
        "RuntimeError",
        "session result items exceed their session bound",
    )
    assert last_item in emitted
    assert excess_item not in emitted
    assert prior[-1] == last_item
    assert prior[-1] is not last_item


@pytest.mark.parametrize(
    ("caught", "response"),
    [
        pytest.param(Exception, "return", id="exception-return"),
        pytest.param(BaseException, "return", id="base-exception-return"),
        pytest.param(Exception, "pause", id="exception-pause"),
        pytest.param(BaseException, "cancel", id="base-exception-cancel"),
    ],
)
def test_runner_owns_item_limit_failure_after_workflow_interception(
    caught: type[BaseException], response: str
) -> None:
    prior_item = ItemOutcome("4" * 32, "copy", "prior.txt", Outcome.SUCCEEDED)
    excess_item = ItemOutcome("5" * 32, "copy", "excess.txt", Outcome.SUCCEEDED)
    prior = [prior_item] * MAX_SESSION_RESULT_ITEMS
    emitted: list[object] = []
    settled: list[tuple[SessionState, OperationResult | None]] = []

    def work(context):
        try:
            context.emit(excess_item)
        except caught:
            if response == "pause":
                raise PauseRequested()
            if response == "cancel":
                raise Canceled()
            return OperationResult(SessionState.COMPLETED)
        raise AssertionError("item-limit failure was not raised")

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: settled.append((state, result)),
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=prior,
    )

    assert outcome.paused is False
    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.canceled is False
    assert outcome.result.error == FailureDetail(
        "RuntimeError",
        "session result items exceed their session bound",
    )
    assert settled == [(SessionState.FAILED, outcome.result)]
    assert excess_item not in emitted
    assert len(prior) == MAX_SESSION_RESULT_ITEMS


def test_runner_repairs_emitter_alias_append_and_owns_the_failure() -> None:
    prior_item = ItemOutcome("4" * 32, "copy", "prior.txt", Outcome.SUCCEEDED)
    accepted_item = ItemOutcome("5" * 32, "copy", "accepted.txt", Outcome.SUCCEEDED)
    injected_item = ItemOutcome("6" * 32, "copy", "injected.txt", Outcome.SUCCEEDED)
    prior = [prior_item] * (MAX_SESSION_RESULT_ITEMS - 1)
    emitted: list[object] = []

    def emit(body: object) -> None:
        emitted.append(body)
        if isinstance(body, ItemOutcome) and body.item_id == accepted_item.item_id:
            prior.append(injected_item)

    outcome = run_session(
        lambda context: context.emit(accepted_item)
        or OperationResult(SessionState.COMPLETED),
        emit=emit,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=prior,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.error == FailureDetail(
        "RuntimeError",
        "session result item accumulator changed during emission",
    )
    assert len(outcome.result.items) == MAX_SESSION_RESULT_ITEMS
    assert prior[-1] == accepted_item
    assert prior[-1] is not accepted_item
    assert injected_item not in prior
    assert emitted[0] == accepted_item
    assert emitted[0] is not prior[-1]


def test_runner_preserves_prior_truth_when_emitter_clears_alias_then_raises() -> None:
    prior_item = ItemOutcome("7" * 32, "copy", "prior.txt", Outcome.SUCCEEDED)
    offered_item = ItemOutcome("8" * 32, "copy", "offered.txt", Outcome.SUCCEEDED)
    injected_item = ItemOutcome("9" * 32, "copy", "injected.txt", Outcome.SUCCEEDED)
    accumulator = [prior_item]

    def emit(body: object) -> None:
        if isinstance(body, ResultItem):
            accumulator.append(injected_item)
            accumulator.clear()
            raise OSError("publication failed")

    outcome = run_session(
        lambda context: context.emit(offered_item)
        or OperationResult(SessionState.COMPLETED),
        emit=emit,
        checkpoint=lambda: None,
        settle=lambda _state, _result: None,
        finalize_audit=lambda _result: RecordingStatus.OK,
        publish_result=lambda _result: None,
        item_accumulator=accumulator,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.items == (prior_item,)
    assert outcome.result.error == FailureDetail("OSError", "publication failed")
    assert accumulator == [prior_item]
    assert accumulator[0] is not prior_item


def test_runner_normalizes_a_nonexact_accumulator_before_work() -> None:
    class MisleadingList(list):
        pass

    calls: list[str] = []
    outcome = run_session(
        lambda context: calls.append("work")
        or OperationResult(SessionState.COMPLETED),
        emit=lambda body: None,
        checkpoint=lambda: None,
        settle=lambda state, result: calls.append("settle"),
        finalize_audit=lambda result: calls.append("audit") or RecordingStatus.OK,
        publish_result=lambda result: calls.append("publish"),
        item_accumulator=MisleadingList(),
    )

    assert calls == ["settle", "audit", "publish"]
    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.items == ()
    assert outcome.result.error == FailureDetail(
        "TypeError",
        "item accumulator must be an exact list",
    )


def test_runner_normalizes_invalid_accumulator_content_before_work() -> None:
    calls: list[str] = []
    outcome = run_session(
        lambda context: calls.append("work")
        or OperationResult(SessionState.COMPLETED),
        emit=lambda body: None,
        checkpoint=lambda: None,
        settle=lambda state, result: calls.append("settle"),
        finalize_audit=lambda result: calls.append("audit") or RecordingStatus.OK,
        publish_result=lambda result: calls.append("publish"),
        item_accumulator=[object()],  # type: ignore[list-item]
    )

    assert calls == ["settle", "audit", "publish"]
    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.items == ()
    assert outcome.result.error == FailureDetail(
        "TypeError",
        "item accumulator must contain only ResultItem values",
    )


def test_runner_admits_resume_items_atomically_before_replacing_sources() -> None:
    class HostileItem(ItemOutcome):
        def __getattribute__(self, name: str):
            if name == "item_id" and object.__getattribute__(
                self, "__dict__"
            ).get("hostile", False):
                raise RuntimeError("hostile item getter")
            return super().__getattribute__(name)

    calls: list[str] = []
    first = ItemOutcome(
        "5" * 32,
        "copy",
        "first.txt",
        Outcome.SUCCEEDED,
    )
    hostile = HostileItem(
        "6" * 32,
        "copy",
        "hostile.txt",
        Outcome.SUCCEEDED,
    )
    hostile.hostile = True
    prior = [first, hostile]
    outcome = run_session(
        lambda context: calls.append("work")
        or OperationResult(SessionState.COMPLETED),
        emit=lambda body: None,
        checkpoint=lambda: None,
        settle=lambda state, result: calls.append("settle"),
        finalize_audit=lambda result: (
            calls.append("audit") or RecordingStatus.OK
        ),
        publish_result=lambda result: calls.append("publish"),
        item_accumulator=prior,
    )

    assert calls == ["settle", "audit", "publish"]
    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.items == ()
    assert outcome.result.error == FailureDetail(
        "TypeError",
        "item accumulator must contain only ResultItem values",
    )
    assert prior[0] is first
    assert prior[1] is hostile


def test_operation_result_rejects_non_nominal_items() -> None:
    with pytest.raises(TypeError, match="must be a tuple"):
        OperationResult(SessionState.COMPLETED, items=[])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must implement ResultItem"):
        OperationResult(SessionState.COMPLETED, items=(object(),))  # type: ignore[arg-type]


def test_runner_audit_failure_degrades_only_audit_axis() -> None:
    outcome = run_session(
        lambda context: OperationResult(
            SessionState.COMPLETED,
            recording=RecordingStatus.OK,
            bytes_done=3,
            bytes_total=3,
        ),
        emit=lambda body: None,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: (_ for _ in ()).throw(RuntimeError("audit")),
        publish_result=lambda result: None,
    )
    assert outcome.result is not None
    assert outcome.result.status is SessionState.COMPLETED
    assert outcome.result.recording is RecordingStatus.OK
    assert outcome.result.audit is RecordingStatus.DEGRADED


def test_runner_contains_an_invalid_audit_result() -> None:
    emitted: list[object] = []
    outcome = run_session(
        lambda context: OperationResult(SessionState.COMPLETED),
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: "ok",  # type: ignore[return-value]
        publish_result=lambda result: None,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.COMPLETED
    assert outcome.result.audit is RecordingStatus.DEGRADED
    assert emitted == [Terminal(TerminalSummary.from_result(outcome.result))]


@pytest.mark.parametrize("owner", ("work", "emit", "pause", "cancel", "audit"))
def test_runner_retires_consumed_callback_exception_frames(owner: str) -> None:
    if owner == "pause":
        failure: BaseException = PauseRequested("pause")
    elif owner == "cancel":
        failure = Canceled("cancel")
    else:
        failure = RuntimeError(f"{owner} failed")
    references: list[ref[_PrivateExceptionFrameValue]] = []

    def work(context) -> OperationResult:
        if owner in {"work", "pause", "cancel"}:
            _raise_with_private_frame(failure, references)
        if owner == "emit":
            context.emit(PhaseChanged("scan"))
        return OperationResult(SessionState.COMPLETED)

    def emit(body: object) -> None:
        if owner == "emit" and isinstance(body, PhaseChanged):
            _raise_with_private_frame(failure, references)

    def finalize(result: OperationResult) -> RecordingStatus:
        del result
        if owner == "audit":
            _raise_with_private_frame(failure, references)
        return RecordingStatus.OK

    outcome = run_session(
        work,
        emit=emit,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=finalize,
        publish_result=lambda result: None,
    )

    if owner == "pause":
        assert outcome == RunOutcome(paused=True, result=None)
    else:
        assert outcome.result is not None
        if owner == "cancel":
            assert outcome.result.status is SessionState.CANCELED
            assert outcome.result.canceled
        elif owner == "audit":
            assert outcome.result.status is SessionState.COMPLETED
            assert outcome.result.audit is RecordingStatus.DEGRADED
        else:
            assert outcome.result.status is SessionState.FAILED
            assert outcome.result.error == FailureDetail(
                "RuntimeError",
                f"{owner} failed",
            )
    gc.collect()
    assert references and all(reference() is None for reference in references)


def test_runner_retires_consumed_exception_group_members() -> None:
    references: list[ref[_PrivateExceptionFrameValue]] = []

    try:
        _raise_with_private_frame(RuntimeError("leaf failed"), references)
    except RuntimeError as error:
        leaf = error
    failure = ExceptionGroup("work failed", (leaf, leaf))

    def work(context) -> OperationResult:
        del context
        raise failure

    outcome = run_session(
        work,
        emit=lambda body: None,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.error is not None
    assert outcome.result.error.type_name == "ExceptionGroup"
    assert BaseExceptionGroup.exceptions.__get__(
        failure,
        BaseExceptionGroup,
    ) == (leaf, leaf)
    gc.collect()
    assert references and all(reference() is None for reference in references)


def test_runner_retires_emitter_failure_superseded_by_accumulator_truth() -> None:
    primary = RuntimeError("emitter failed")
    references: list[ref[_PrivateExceptionFrameValue]] = []
    injected = ItemOutcome("7" * 32, "copy", "injected.txt", Outcome.FAILED)
    offered = ItemOutcome("8" * 32, "copy", "offered.txt", Outcome.SUCCEEDED)
    items: list[ResultItem] = []

    def emit(body: object) -> None:
        if isinstance(body, ItemOutcome) and body.item_id == offered.item_id:
            items.append(injected)
            _raise_with_private_frame(primary, references)

    outcome = run_session(
        lambda context: context.emit(offered)
        or OperationResult(SessionState.COMPLETED),
        emit=emit,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=items,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.error == FailureDetail(
        "RuntimeError",
        "session result item accumulator changed during emission",
    )
    assert outcome.result.items == ()
    gc.collect()
    assert references and all(reference() is None for reference in references)


def test_runner_cancel_with_unknown_progress_total_keeps_truthful_counts() -> None:
    def work(context):
        context.emit(
            Progress(
                "execute",
                1,
                None,
                17,
                None,
                "file",
                item_id="operation",
                item_type="operation",
                item_attempt_id="a" * 32,
                item_bytes_done=3,
                item_bytes_total=99,
            )
        )
        raise Canceled()

    outcome = run_session(
        work,
        emit=lambda body: None,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )
    assert outcome.result is not None
    assert outcome.result.bytes_done == 17
    assert outcome.result.bytes_total == 17


def test_item_diagnostics_are_omitted_whole_without_truncation() -> None:
    oversized = "é" * 513
    operation = ItemOutcome(
        item_id="1" * 32,
        kind="copy",
        path="file.bin",
        outcome=Outcome.SUCCEEDED,
        detail={"message": oversized},
        recording=RecordingStatus.DEGRADED,
        recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
        recording_detail=oversized,
    )
    integrity = IntegrityOutcome(
        item_id="row-1",
        row_id="1",
        location_id="2",
        path="file.bin",
        result=IntegrityResult.ERROR,
        detail=oversized,
    )

    assert dict(operation.detail) == {}
    assert operation.recording_detail is None
    assert operation.detail_omitted_count == 2
    assert integrity.detail is None
    assert integrity.detail_omitted_count == 1
    assert oversized[:512] not in repr(operation)
    assert oversized[:512] not in repr(integrity)


def test_detail_projection_accepts_only_its_exact_canonical_shape() -> None:
    projection = DetailProjection(
        (
            ("message", "copy complete"),
            ("published_path", "target/file.bin"),
            ("continued", True),
            ("durability_warnings", ("directory flush unavailable",)),
            ("incomplete_sides", ("source", "target")),
            ("excluded_dependencies", ("1" * 32,)),
        )
    )

    admitted, omitted = project_detail(projection)

    assert admitted is not projection
    assert admitted.entries == projection.entries
    assert omitted == 0
    assert admitted.to_wire() == {
        "message": "copy complete",
        "published_path": "target/file.bin",
        "continued": True,
        "durability_warnings": ["directory flush unavailable"],
        "incomplete_sides": ["source", "target"],
        "excluded_dependencies": ["1" * 32],
    }


class _DetailText(str):
    pass


@pytest.mark.parametrize(
    "entries",
    (
        [],
        (["message", "text"],),
        (("message",),),
        ((_DetailText("message"), "text"),),
        (("méssage", "text"),),
        (("unknown", "text"),),
        (("message", "first"), ("message", "second")),
        (("message", _DetailText("text")),),
        (("message", "é" * 513),),
        (("message", "\ud800"),),
        (("published_path", True),),
        (("published_path", "bad\x00path"),),
        (("published_path", "x" * 32_768),),
        (("published_path", "\ud800"),),
        (("continued", 1),),
        (("durability_warnings", ["warning"]),),
        (("durability_warnings", (_DetailText("warning"),)),),
        (("durability_warnings", ("é" * 513,)),),
        (("incomplete_sides", (_DetailText("source"),)),),
        (("incomplete_sides", ("neither",)),),
        (("excluded_dependencies", (_DetailText("1" * 32),)),),
        (("excluded_dependencies", ("not-an-id",)),),
        (("durability_warnings", tuple("warning" for _ in range(33))),),
        (
            ("durability_warnings", tuple("warning" for _ in range(32))),
            ("continued", True),
        ),
    ),
)
def test_detail_projection_rejects_noncanonical_entries(entries: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        DetailProjection(entries)  # type: ignore[arg-type]


def test_detail_projection_bounds_invalid_text_before_encoding() -> None:
    overlong_key = "x" * 65
    with pytest.raises(ValueError, match="ASCII bound") as key_error:
        DetailProjection(((overlong_key, "text"),))
    assert overlong_key not in str(key_error.value)

    overlong_invalid_path = "\ud800" + ("x" * 32_767)
    with pytest.raises(ValueError, match="UTF-16 path bound"):
        DetailProjection((("published_path", overlong_invalid_path),))


def test_detail_projection_revalidates_forged_exact_instances() -> None:
    missing_entries = object.__new__(DetailProjection)
    projection = object.__new__(DetailProjection)
    object.__setattr__(
        projection,
        "entries",
        (("message", "first"), ("message", "second")),
    )

    with pytest.raises(TypeError, match="exact tuple"):
        project_detail(missing_entries)
    with pytest.raises(ValueError, match="duplicate"):
        project_detail(projection)


def test_detail_projection_subclass_is_copied_to_exact_base_shape() -> None:
    class ProjectionSubclass(DetailProjection):
        def to_wire(self) -> dict[str, object]:
            return {"message": object()}

    projection = ProjectionSubclass((("message", "copy complete"),))
    object.__setattr__(projection, "hidden_graph", object())

    admitted, omitted = project_detail(projection)

    assert type(admitted) is DetailProjection
    assert admitted is not projection
    assert admitted.entries == (("message", "copy complete"),)
    assert omitted == 0


def test_item_detail_snapshot_does_not_retain_the_callers_projection() -> None:
    source = DetailProjection((("message", "copy complete"),))
    item = ItemOutcome(
        item_id="1" * 32,
        kind="copy",
        path="file.bin",
        outcome=Outcome.SUCCEEDED,
        detail=source,
    )

    object.__setattr__(source, "entries", (("message", object()),))

    assert item.detail is not source
    assert item.detail.entries == (("message", "copy complete"),)


def test_result_item_serialization_revalidates_owned_detail() -> None:
    item = ItemOutcome(
        item_id="1" * 32,
        kind="copy",
        path="file.bin",
        outcome=Outcome.SUCCEEDED,
        detail={"message": "copy complete"},
    )
    assert isinstance(item.detail, DetailProjection)
    object.__setattr__(item.detail, "entries", (("message", object()),))

    with pytest.raises(TypeError, match="message must be text"):
        item.detail.to_wire()
    with pytest.raises(TypeError, match="message must be text"):
        result_item_to_dict(item)


def test_detail_projection_rejects_duplicate_custom_mapping_items_before_omission() -> None:
    class DuplicateDetail(Mapping[str, object]):
        def __getitem__(self, key: str) -> object:
            if key != "message":
                raise KeyError(key)
            return "first"

        def __iter__(self):
            return iter(("message",))

        def __len__(self) -> int:
            return 1

        def items(self):
            return (
                ("message", "é" * 513),
                ("message", "second"),
            )

    with pytest.raises(ValueError, match="duplicate"):
        project_detail(DuplicateDetail())


def test_raw_detail_projection_preserves_bounded_omission_and_canonicalization() -> None:
    projection, omitted = project_detail(
        {
            "message": "é" * 513,
            "durability_warnings": ["flush unavailable"],
        }
    )

    assert projection.entries == (
        ("durability_warnings", ("flush unavailable",)),
    )
    assert omitted == 1
    with pytest.raises(TypeError):
        project_detail({"incomplete_sides": [_DetailText("source")]})


@pytest.mark.parametrize(
    "detail",
    (
        {"message": None},
        {"durability_warnings": [None]},
    ),
)
def test_item_detail_rejects_null_declared_values(
    detail: dict[str, object],
) -> None:
    with pytest.raises(TypeError):
        ItemOutcome(
            item_id="1" * 32,
            kind="copy",
            path="file.bin",
            outcome=Outcome.SUCCEEDED,
            detail=detail,
        )


def test_terminal_summary_copies_bounded_truth_without_retaining_items() -> None:
    item = ItemOutcome(
        item_id="2" * 32,
        kind="copy",
        path="file.bin",
        outcome=Outcome.SUCCEEDED,
        recording=RecordingStatus.DEGRADED,
        recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
        detail_omitted_count=1,
    )
    issue = TaskRecordingIssue(
        TaskRecordingIssueReason.FINAL_FLUSH_FAILED,
        "flush failed",
    )
    result = OperationResult(
        SessionState.COMPLETED,
        items=(item,),
        recording=RecordingStatus.DEGRADED,
        recording_issues=(issue,),
        omitted_detail_count=2,
    )

    summary = TerminalSummary.from_result(result)
    wire = terminal_summary_to_dict(summary)

    assert summary.recording_degraded_items == 1
    assert summary.recording_issues == (issue,)
    assert summary.omitted_detail_count == 3
    assert not hasattr(summary, "items")
    assert "items" not in wire


@pytest.mark.parametrize(
    ("phase_error", "type_name", "message", "phase_omitted", "header_omissions"),
    (
        ("é" * 512, "Failure", "é" * 512, False, 0),
        ("", "Failure", "", False, 0),
        ("é" * 513, "Failure", "bounded", True, 1),
        ("\ud800", "Failure", "bounded", True, 1),
        ("bounded", "", "bounded", False, 1),
        ("bounded", "F" * 1025, "bounded", False, 1),
        ("bounded", "\ud800", "bounded", False, 1),
        ("bounded", "Failure", "é" * 513, False, 1),
        ("bounded", "Failure", "\ud800", False, 1),
        ("é" * 513, "F" * 1025, "é" * 513, True, 2),
    ),
    ids=(
        "maximum-utf8",
        "empty-values",
        "oversized-phase",
        "invalid-phase",
        "empty-type",
        "oversized-type",
        "invalid-type",
        "oversized-message",
        "invalid-message",
        "whole-failure-counted-once",
    ),
)
def test_runner_normalizes_full_result_headers_before_every_owner(
    phase_error: str,
    type_name: str,
    message: str,
    phase_omitted: bool,
    header_omissions: int,
) -> None:
    item = ItemOutcome(
        "2" * 32,
        "copy",
        "file.bin",
        Outcome.SUCCEEDED,
        recording=RecordingStatus.DEGRADED,
        recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
        detail_omitted_count=2,
    )
    phase = PhaseResult("execute", PhaseStatus.FAILED, 1, 1, 17, 100, phase_error)
    original = OperationResult(
        SessionState.FAILED,
        recording=RecordingStatus.DEGRADED,
        audit=RecordingStatus.DEGRADED,
        items=(item,),
        phases=(phase,),
        bytes_done=17,
        bytes_total=100,
        error=FailureDetail(type_name, message),
        recording_issues=(
            TaskRecordingIssue(TaskRecordingIssueReason.FINAL_FLUSH_FAILED, "flush"),
        ),
        omitted_detail_count=3,
    )
    original_error = original.error
    expected_full = replace(
        original,
        phases=(replace(phase, error=None),) if phase_omitted else original.phases,
        error=None if header_omissions > int(phase_omitted) else original_error,
        omitted_detail_count=3 + header_omissions,
    )
    expected = TerminalSummary.from_result(expected_full)
    normalized = normalize_result_diagnostics(original)
    assert normalized == expected_full
    if expected_full.error is not None:
        assert normalized.error is original_error
    assert normalize_result_diagnostics(normalized) is normalized
    if header_omissions == 0:
        assert normalized is original
    owned: list[OperationResult] = []
    emitted: list[object] = []

    def work(context):
        context.emit(item)
        return original

    def finalize(result):
        owned.append(result)
        return RecordingStatus.DEGRADED

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: owned.append(result),
        finalize_audit=finalize,
        publish_result=owned.append,
    )

    assert outcome.result is not None
    assert len(owned) == 3
    assert owned[0] is owned[1]
    assert owned[2] is outcome.result
    assert owned[0] is not outcome.result
    assert len({id(value) for value in (*owned, outcome.result)}) == 2
    for retained in owned:
        assert retained == expected_full
        assert type(retained.items[0]) is ItemOutcome
        assert retained.items[0] == emitted[0]
        assert retained.items is outcome.result.items
        assert retained.items[0] is emitted[0]
        assert retained.items[0] is not item
        assert retained.recording_issues == original.recording_issues
        assert retained.recording_issues is not original.recording_issues
        if not phase_omitted:
            assert type(retained.phases[0]) is PhaseResult
            assert retained.phases[0] is not phase
        if expected_full.error is not None:
            assert retained.error == original_error
            assert retained.error is not original_error
        assert TerminalSummary.from_result(retained) == expected
    assert expected.omitted_detail_count == 5 + header_omissions
    assert emitted == [item, Terminal(expected)]
    assert original.phases == (phase,)
    assert phase.error == phase_error
    assert original.error is original_error
    assert original_error == FailureDetail(type_name, message)
    assert original.omitted_detail_count == 3


def test_runner_shares_one_canonical_immutable_graph_with_terminal_owners() -> None:
    operation = ItemOutcome(
        "7" * 32,
        "copy",
        "reviewed.txt",
        Outcome.SUCCEEDED,
    )
    integrity = IntegrityOutcome(
        item_id="8" * 32,
        row_id="row",
        location_id="location",
        path="verified.txt",
        result=IntegrityResult.VERIFIED,
        phase=IntegrityMode.VERIFY.value,
    )
    emitted: list[object] = []
    settled: list[OperationResult] = []
    audited: list[OperationResult] = []
    published: list[OperationResult] = []

    def work(context: RunContext) -> OperationResult:
        context.emit(operation)
        context.emit(integrity)
        return OperationResult(
            SessionState.COMPLETED,
            items=(operation, integrity),
        )

    def settle(_state: SessionState, result: OperationResult | None) -> None:
        assert result is not None
        settled.append(result)

    def finalize(result: OperationResult) -> RecordingStatus:
        audited.append(result)
        return RecordingStatus.OK

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=settle,
        finalize_audit=finalize,
        publish_result=published.append,
    )

    assert outcome.result is not None
    assert settled[0] is audited[0]
    assert published[0] is outcome.result
    assert settled[0] is not outcome.result
    assert settled[0].items is outcome.result.items
    assert emitted[0] is outcome.result.items[0]
    assert emitted[1] is outcome.result.items[1]
    assert outcome.result.items[0] is not operation
    assert outcome.result.items[1] is not integrity
    for item in outcome.result.items:
        assert not hasattr(item, "__dict__")
        with pytest.raises(FrozenInstanceError):
            item.path = "forbidden.txt"
    assert emitted[-1] == Terminal(TerminalSummary.from_result(outcome.result))


def test_runner_snapshots_each_item_once_without_an_external_accumulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = session_module.snapshot_result_item
    snapshot_calls: list[object] = []

    def observe_snapshot(value: object) -> ResultItem:
        snapshot_calls.append(value)
        return original(value)

    monkeypatch.setattr(session_module, "snapshot_result_item", observe_snapshot)
    producer_items = tuple(
        ItemOutcome(
            str(index) * 32,
            "copy",
            f"file-{index}.txt",
            Outcome.SUCCEEDED,
        )
        for index in range(1, 4)
    )

    def work(context: RunContext) -> OperationResult:
        for item in producer_items:
            context.emit(item)
        return OperationResult(SessionState.COMPLETED, items=producer_items)

    outcome = run_session(
        work,
        emit=lambda _body: None,
        checkpoint=lambda: None,
        settle=lambda _state, _result: None,
        finalize_audit=lambda _result: RecordingStatus.OK,
        publish_result=lambda _result: None,
    )

    assert outcome.result is not None
    assert snapshot_calls == list(producer_items)


def test_runner_contains_exception_diagnostic_failure_without_losing_items() -> None:
    class UnprintableError(Exception):
        def __str__(self) -> str:
            raise RuntimeError("format failed")

    item = ItemOutcome("3" * 32, "copy", "file.bin", Outcome.SUCCEEDED)
    emitted: list[object] = []
    settled: list[OperationResult] = []

    def work(context):
        context.emit(item)
        context.emit(Progress("execute", 1, 1, 17, 100, "file.bin"))
        raise UnprintableError()

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: None,
        settle=lambda state, result: settled.append(result),
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )

    assert outcome.result is not None
    assert len(settled) == 1
    assert outcome.result.status is SessionState.FAILED
    assert outcome.result.error is None
    assert outcome.result.omitted_detail_count == 1
    assert outcome.result.items == (item,)
    assert (outcome.result.bytes_done, outcome.result.bytes_total) == (17, 100)
    assert emitted[-1] == Terminal(TerminalSummary.from_result(outcome.result))


def test_header_omission_overflow_refuses_before_any_terminal_owner() -> None:
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
                "x" * 1025,
            ),
        ),
        omitted_detail_count=MAX_SAFE_INTEGER,
    )
    owners = []

    with pytest.raises(ValueError, match="SafeInt domain"):
        normalize_result_diagnostics(result)
    with pytest.raises(ValueError, match="SafeInt domain"):
        run_session(
            lambda context: result,
            emit=lambda body: owners.append(("emit", body)),
            checkpoint=lambda: None,
            settle=lambda state, owned: owners.append(("settle", owned)),
            finalize_audit=lambda owned: owners.append(("audit", owned)),
            publish_result=lambda owned: owners.append(("publish", owned)),
        )

    assert owners == []
    assert result.phases[0].error == "x" * 1025
    assert result.omitted_detail_count == MAX_SAFE_INTEGER


def _event_bodies() -> tuple[object, ...]:
    item = ItemOutcome(
        item_id="1" * 32,
        kind="copy",
        path="folder\\file",
        outcome=Outcome.SKIPPED,
        reason=None,
        detail={"message": "already current"},
    )
    result = OperationResult(
        status=SessionState.COMPLETED,
        audit=RecordingStatus.DEGRADED,
        disposition=Disposition.RAN,
        canceled=True,
        items=(item,),
        phases=(
            PhaseResult(
                "execute", PhaseStatus.COMPLETED, 1, 1, 0, 0
            ),
            PhaseResult(
                "verify", PhaseStatus.CANCELED, 0, 1, 0, 1
            ),
        ),
    )
    return (
        StateChanged(SessionState.RUNNING),
        PhaseChanged("phase"),
        Progress("execute", 1, 2, 3, 4, "folder\\file"),
        item,
        IntegrityOutcome(
            item_id="2" * 32,
            row_id="3" * 32,
            location_id="4" * 32,
            path="folder\\file",
            result=IntegrityResult.VERIFIED,
            read_strategy=ReadStrategy.WINDOWS_UNBUFFERED,
            record_disposition=RecordDisposition.APPLIED,
        ),
        ItemOutcome(
            item_id="5" * 32,
            kind="noop",
            path="junction",
            outcome=Outcome.BLOCKED,
            reason="blocked-correspondence",
        ),
        Gap(7),
        Terminal(TerminalSummary.from_result(result)),
    )


@pytest.mark.parametrize("body", _event_bodies())
def test_m1_event_bodies_round_trip(body: object) -> None:
    envelope = Envelope(
        session_id=SessionId("a" * 32),
        seq=7 if isinstance(body, Gap) else 1,
        at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        schema_version=CORE_EVENT_SCHEMA_VERSION,
        body=body,
    )
    assert envelope_from_dict(envelope_to_dict(envelope)) == envelope


def _progress_values() -> dict[str, object]:
    return {
        "phase": "execute",
        "items_done": 0,
        "items_total": 1,
        "bytes_done": 7,
        "bytes_total": 20,
        "current_path": "folder\\file.bin",
        "item_id": "item",
        "item_type": "operation",
        "item_attempt_id": "a" * 32,
        "item_bytes_done": 7,
        "item_bytes_total": 10,
    }


def _progress(**changes: object) -> Progress:
    values = _progress_values()
    values.update(changes)
    return Progress(**values)  # type: ignore[arg-type]


def _progress_envelope(body: Progress | None = None) -> Envelope:
    return Envelope(
        session_id=SessionId("a" * 32),
        seq=1,
        at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        schema_version=CORE_EVENT_SCHEMA_VERSION,
        body=_progress() if body is None else body,
    )


def test_progress_v5_serializes_exact_self_describing_telemetry() -> None:
    envelope = _progress_envelope()

    serialized = envelope_to_dict(envelope)

    assert serialized["schema_version"] == 5
    assert serialized["body"] == {
        **_progress_values(),
        "bytes_done": "7",
        "bytes_total": "20",
        "item_bytes_done": "7",
        "item_bytes_total": "10",
    }
    assert envelope_from_dict(serialized) == envelope


def test_v5_terminal_codec_preserves_signed_64_values_above_safe_int() -> None:
    larger_than_javascript_safe = 1 << 53
    result = OperationResult(
        SessionState.COMPLETED,
        phases=(
            PhaseResult(
                "execute",
                PhaseStatus.COMPLETED,
                1,
                1,
                larger_than_javascript_safe,
                larger_than_javascript_safe,
            ),
        ),
        bytes_done=larger_than_javascript_safe,
        bytes_total=larger_than_javascript_safe,
    )
    envelope = Envelope(
        session_id=SessionId("a" * 32),
        seq=1,
        at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        schema_version=CORE_EVENT_SCHEMA_VERSION,
        body=Terminal(TerminalSummary.from_result(result)),
    )

    assert envelope_from_dict(envelope_to_dict(envelope)) == envelope


@pytest.mark.parametrize("version", (3, 4, 6))
def test_non_v5_epoch_is_explicitly_refused_by_envelope_and_decoder(
    version: int,
) -> None:
    with pytest.raises(ValueError, match="exactly 5"):
        Envelope(
            session_id=SessionId("a" * 32),
            seq=1,
            at=datetime(2026, 8, 21, tzinfo=timezone.utc),
            schema_version=version,
            body=_progress(),
        )

    serialized = envelope_to_dict(_progress_envelope())
    serialized["schema_version"] = version
    with pytest.raises(ValueError, match="exactly 5"):
        envelope_from_dict(serialized)


@pytest.mark.parametrize(
    "changes",
    [
        {
            "item_id": None,
            "item_type": None,
            "item_attempt_id": None,
            "item_bytes_done": None,
            "item_bytes_total": None,
        },
        {
            "item_attempt_id": None,
            "item_bytes_done": None,
            "item_bytes_total": None,
        },
        {"item_bytes_done": None, "item_bytes_total": None},
        {
            "items_total": None,
            "bytes_total": None,
            "item_bytes_total": 10,
        },
        {
            "bytes_done": 0,
            "bytes_total": 0,
            "current_path": "empty.bin",
            "item_bytes_done": 0,
            "item_bytes_total": 0,
        },
    ],
)
def test_progress_accepts_all_normative_activity_shapes(
    changes: dict[str, object],
) -> None:
    body = _progress(**changes)

    assert envelope_from_dict(envelope_to_dict(_progress_envelope(body))).body == body


def test_progress_accepts_signed_64_bytes_above_javascript_safe_integer() -> None:
    maximum = (1 << 53) + 17
    body = _progress(
        items_done=1,
        items_total=1,
        bytes_done=maximum,
        bytes_total=maximum,
        item_id=None,
        item_type=None,
        item_attempt_id=None,
        item_bytes_done=None,
        item_bytes_total=None,
    )

    assert body.bytes_done == maximum


@pytest.mark.parametrize(
    "changes",
    [
        {"phase": ""},
        {"phase": 7},
        {"items_done": True},
        {"items_done": 0.5},
        {"items_done": -1},
        {"items_done": 2},
        {"items_done": 1},
        {"items_done": 1 << 53},
        {"items_total": True},
        {"items_total": -1},
        {"items_total": 1 << 53},
        {"bytes_done": True},
        {"bytes_done": -1},
        {"bytes_done": 21},
        {"bytes_done": 1 << 63},
        {"bytes_total": True},
        {"bytes_total": -1},
        {"bytes_total": 1 << 63},
        {"current_path": 7},
        {"item_id": None},
        {"item_type": None},
        {"item_id": ""},
        {"item_type": "unknown"},
        {
            "item_id": None,
            "item_type": None,
            "item_attempt_id": "a" * 32,
            "item_bytes_done": None,
            "item_bytes_total": None,
        },
        {"item_attempt_id": None},
        {"item_attempt_id": "a" * 31},
        {"item_attempt_id": "A" * 32},
        {"item_attempt_id": "g" * 32},
        {"item_attempt_id": 7},
        {"item_bytes_done": None},
        {"item_bytes_total": None},
        {"item_bytes_done": True},
        {"item_bytes_done": 0.5},
        {"item_bytes_done": -1},
        {"item_bytes_done": 1 << 63},
        {"item_bytes_done": 8, "bytes_done": 7},
        {"item_bytes_done": 11},
        {"item_bytes_total": True},
        {"item_bytes_total": -1},
        {"item_bytes_total": 1 << 63},
        {"item_bytes_total": 21},
    ],
)
def test_progress_rejects_invalid_scalars_and_cross_field_states(
    changes: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        _progress(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"phase": ""},
        {"phase": 7},
        {"items_done": True},
        {"items_done": 1 << 53},
        {"items_done": 1},
        {"bytes_done": 1 << 53},
        {"current_path": 7},
        {"item_id": None},
        {"item_attempt_id": None},
        {"item_attempt_id": "A" * 32},
        {"item_bytes_done": None},
        {"item_bytes_done": 8},
        {"item_bytes_total": 21},
    ],
)
def test_progress_v5_decoder_rejects_invalid_scalar_and_cross_field_states(
    changes: dict[str, object],
) -> None:
    serialized = envelope_to_dict(_progress_envelope())
    raw_body = serialized["body"]
    assert isinstance(raw_body, dict)
    raw_body.update(changes)

    with pytest.raises((TypeError, ValueError)):
        envelope_from_dict(serialized)


@pytest.mark.parametrize("missing", sorted(_progress_values()))
def test_progress_v5_decoder_rejects_every_missing_field(missing: str) -> None:
    serialized = envelope_to_dict(_progress_envelope())
    raw_body = serialized["body"]
    assert isinstance(raw_body, dict)
    raw_body.pop(missing)

    with pytest.raises(ValueError, match="invalid exact shape"):
        envelope_from_dict(serialized)


def test_progress_v5_decoder_rejects_extra_fields() -> None:
    serialized = envelope_to_dict(_progress_envelope())
    raw_body = serialized["body"]
    assert isinstance(raw_body, dict)
    raw_body["future"] = None

    with pytest.raises(ValueError, match="invalid exact shape"):
        envelope_from_dict(serialized)


@pytest.mark.parametrize(
    "phase",
    [
        IntegrityMode.BASELINE.value,
        IntegrityMode.VERIFY.value,
        IntegrityMode.REBASELINE.value,
    ],
)
def test_integrity_event_codec_preserves_mode_phase(phase: str) -> None:
    item = IntegrityOutcome(
        item_id="phase-item",
        row_id="4",
        location_id="2",
        path="file.bin",
        result=IntegrityResult.BASELINED,
        phase=phase,
    )
    envelope = Envelope(
        session_id=SessionId("b" * 32),
        seq=1,
        at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        schema_version=CORE_EVENT_SCHEMA_VERSION,
        body=item,
    )

    assert envelope_from_dict(envelope_to_dict(envelope)) == envelope


def test_integrity_event_codec_preserves_absent_post_copy_ledger_identity() -> None:
    item = IntegrityOutcome(
        item_id="rowless-copy",
        row_id=None,
        location_id=None,
        path="file.bin",
        result=IntegrityResult.VERIFIED,
        reason=IntegrityReason.RECORDING_ERROR,
        recording=RecordingStatus.DEGRADED,
    )
    envelope = Envelope(
        session_id=SessionId("c" * 32),
        seq=1,
        at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        schema_version=CORE_EVENT_SCHEMA_VERSION,
        body=item,
    )

    decoded = envelope_from_dict(envelope_to_dict(envelope))

    assert decoded == envelope
    assert isinstance(decoded.body, IntegrityOutcome)
    assert decoded.body.row_id is None
    assert decoded.body.location_id is None


def test_event_deserialization_rejects_unknown_schema() -> None:
    envelope = Envelope(
        session_id=SessionId("a" * 32),
        seq=1,
        at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        schema_version=CORE_EVENT_SCHEMA_VERSION,
        body=PhaseChanged("phase"),
    )
    serialized = envelope_to_dict(envelope)
    serialized["schema_version"] = 999
    with pytest.raises(ValueError, match="exactly 5"):
        envelope_from_dict(serialized)


def test_event_sequence_scalars_share_the_browser_safe_integer_domain() -> None:
    unsafe = 1 << 53
    with pytest.raises(ValueError, match="SafeInt"):
        Envelope(
            session_id=SessionId("a" * 32),
            seq=unsafe,
            at=datetime(2026, 7, 18, tzinfo=timezone.utc),
            schema_version=CORE_EVENT_SCHEMA_VERSION,
            body=PhaseChanged("phase"),
        )
    with pytest.raises(ValueError, match="SafeInt"):
        Gap(unsafe)

    envelope = Envelope(
        session_id=SessionId("a" * 32),
        seq=1,
        at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        schema_version=CORE_EVENT_SCHEMA_VERSION,
        body=PhaseChanged("phase"),
    )
    serialized = envelope_to_dict(envelope)
    serialized["seq"] = unsafe
    with pytest.raises(ValueError, match="SafeInt"):
        envelope_from_dict(serialized)


def test_event_deserialization_rejects_coercive_scalar_types() -> None:
    envelope = Envelope(
        session_id=SessionId("a" * 32),
        seq=1,
        at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        schema_version=CORE_EVENT_SCHEMA_VERSION,
        body=PhaseChanged("phase"),
    )

    serialized = envelope_to_dict(envelope)
    serialized["schema_version"] = float(CORE_EVENT_SCHEMA_VERSION)
    with pytest.raises(ValueError, match="schema_version"):
        envelope_from_dict(serialized)

    serialized = envelope_to_dict(envelope)
    serialized["seq"] = 1.0
    with pytest.raises((TypeError, ValueError), match="sequence"):
        envelope_from_dict(serialized)

    serialized = envelope_to_dict(envelope)
    body = serialized["body"]
    assert isinstance(body, dict)
    body["phase"] = 7
    with pytest.raises((TypeError, ValueError), match="phase"):
        envelope_from_dict(serialized)

    canceled = Envelope(
        session_id=SessionId("b" * 32),
        seq=1,
        at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        schema_version=CORE_EVENT_SCHEMA_VERSION,
        body=Terminal(
            TerminalSummary.from_result(
                OperationResult(
                    SessionState.CANCELED,
                    disposition=Disposition.RAN,
                    canceled=True,
                )
            )
        ),
    )
    serialized = envelope_to_dict(canceled)
    body = serialized["body"]
    assert isinstance(body, dict)
    result = body["result"]
    assert isinstance(result, dict)
    result["canceled"] = "false"
    with pytest.raises((TypeError, ValueError), match="canceled"):
        envelope_from_dict(serialized)
