from __future__ import annotations

from datetime import datetime, timezone
import subprocess
import sys

import pytest
from xxhash import xxh3_128

from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    Outcome,
    Provenance,
    RecordingStatus,
    HasherFactory,
)
from namisync.core.events import (
    SCHEMA_VERSION,
    Envelope,
    Gap,
    ItemOutcome,
    PhaseChanged,
    Progress,
    StateChanged,
    Terminal,
    envelope_from_dict,
    envelope_to_dict,
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
    Canceled,
    Disposition,
    IllegalTransition,
    OperationResult,
    PauseRequested,
    PhaseResult,
    PhaseStatus,
    SessionId,
    SessionRecord,
    SessionState,
    is_terminal,
    require_transition,
    result_terminal_state,
    run_session,
)
from namisync.dispatcher.store import InMemorySessionStore


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


@pytest.mark.parametrize("path", ["success", "cancel", "failure"])
def test_runner_emits_exactly_one_terminal(path: str) -> None:
    emitted: list[object] = []
    settled: list[tuple[SessionState, OperationResult | None]] = []

    def work(context):
        context.emit(
            ItemOutcome("one", "dummy", "file", Outcome.SUCCEEDED)
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
    assert outcome.result is terminals[0].result
    assert settled[0][0] is terminals[0].result.status
    if path == "failure":
        assert terminals[0].result.error is not None
        assert terminals[0].result.error.type_name == "RuntimeError"


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
        b"payload",
        True,
        1,
        datetime(2026, 7, 18, tzinfo=timezone.utc),
        started_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        ended_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        result=outcome.result,
    )
    assert record.result is not None
    assert record.result.status is SessionState.COMPLETED


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
        schema_version=SCHEMA_VERSION,
        body=Terminal(result),
    )

    decoded = envelope_from_dict(envelope_to_dict(envelope))

    assert isinstance(decoded.body, Terminal)
    assert decoded.body.result == result
    record = SessionRecord(
        SessionId("verify-canceled"),
        "sync-execution",
        SessionState.CANCELED,
        (),
        b"payload",
        True,
        1,
        datetime(2026, 7, 25, tzinfo=timezone.utc),
        started_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        ended_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        result=decoded.body.result,
    )
    assert record.result is not None
    assert record.result.status is filesystem_status
    assert record.result.canceled
    assert result_terminal_state(record.result) is SessionState.CANCELED
    store = InMemorySessionStore()
    store.put(record)
    restored = store.snapshot()[0]
    assert restored == record
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


def test_runner_seeds_cancel_result_from_prior_pause_items() -> None:
    prior = [ItemOutcome("prior", "dummy", "file", Outcome.SUCCEEDED)]
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
    prior = ItemOutcome("prior", "dummy", "prior.txt", Outcome.SUCCEEDED)
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


def test_runner_cancel_with_unknown_progress_total_keeps_truthful_counts() -> None:
    def work(context):
        context.emit(Progress(1, None, 17, None, "file"))
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


def _event_bodies() -> tuple[object, ...]:
    item = ItemOutcome(
        item_id="one",
        kind="dummy",
        path="folder\\file",
        outcome=Outcome.SKIPPED,
        reason="none",
        detail={"number": 1},
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
        Progress(1, 2, 3, 4, "folder\\file"),
        item,
        IntegrityOutcome(
            item_id="integrity",
            row_id="11",
            location_id="4",
            path="folder\\file",
            result=IntegrityResult.VERIFIED,
            read_strategy=ReadStrategy.WINDOWS_UNBUFFERED,
            record_disposition=RecordDisposition.APPLIED,
        ),
        ItemOutcome(
            item_id="blocked",
            kind="noop",
            path="junction",
            outcome=Outcome.BLOCKED,
            reason="unsupported",
        ),
        Gap(7),
        Terminal(result),
    )


@pytest.mark.parametrize("body", _event_bodies())
def test_m1_event_bodies_round_trip(body: object) -> None:
    envelope = Envelope(
        session_id=SessionId("a" * 32),
        seq=1,
        at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        schema_version=SCHEMA_VERSION,
        body=body,
    )
    assert envelope_from_dict(envelope_to_dict(envelope)) == envelope


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
        schema_version=SCHEMA_VERSION,
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
        schema_version=SCHEMA_VERSION,
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
        schema_version=SCHEMA_VERSION,
        body=PhaseChanged("phase"),
    )
    serialized = envelope_to_dict(envelope)
    serialized["schema_version"] = 999
    with pytest.raises(ValueError, match="unsupported event schema"):
        envelope_from_dict(serialized)


def test_event_deserialization_rejects_coercive_scalar_types() -> None:
    envelope = Envelope(
        session_id=SessionId("a" * 32),
        seq=1,
        at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        schema_version=SCHEMA_VERSION,
        body=PhaseChanged("phase"),
    )

    serialized = envelope_to_dict(envelope)
    serialized["schema_version"] = float(SCHEMA_VERSION)
    with pytest.raises(ValueError, match="schema version"):
        envelope_from_dict(serialized)

    serialized = envelope_to_dict(envelope)
    serialized["seq"] = 1.0
    with pytest.raises(ValueError, match="sequence"):
        envelope_from_dict(serialized)

    serialized = envelope_to_dict(envelope)
    body = serialized["body"]
    assert isinstance(body, dict)
    body["phase"] = 7
    with pytest.raises(ValueError, match="phase"):
        envelope_from_dict(serialized)

    canceled = Envelope(
        session_id=SessionId("b" * 32),
        seq=1,
        at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        schema_version=SCHEMA_VERSION,
        body=Terminal(
            OperationResult(
                SessionState.CANCELED,
                disposition=Disposition.RAN,
                canceled=True,
            )
        ),
    )
    serialized = envelope_to_dict(canceled)
    body = serialized["body"]
    assert isinstance(body, dict)
    result = body["result"]
    assert isinstance(result, dict)
    result["canceled"] = "false"
    with pytest.raises(ValueError, match="canceled"):
        envelope_from_dict(serialized)
