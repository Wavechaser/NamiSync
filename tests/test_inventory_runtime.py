from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from threading import Event

import pytest
from xxhash import xxh3_128

import namisync.modules.executor.native as executor_module
import namisync.workflows.inventory as inventory_workflow
from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    Provenance,
    RecordingStatus,
)
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityRecordCommand,
    IntegrityResult,
    IntegrityRunResult,
    IntegritySelection,
    InventoryState,
    ReadStrategy,
    RecordDisposition,
)
from namisync.core.session import (
    Disposition,
    OperationResult,
    ResourceId,
    RunContext,
    SessionState,
)
from namisync.db.recorder import LedgerRecorder
from namisync.db.repositories import LedgerRepository
from namisync.dispatcher import (
    Dispatcher,
    InProcessResourceLockProvider,
    PreparedSession,
    WorkflowRegistration,
)
from namisync.interfaces.service import _workflow_registry
from namisync.workflows.inventory import (
    IntegrityRequest,
    IntegrityWorkflowRequest,
    InventoryRequest,
    VolumeResolutionState,
    decode_integrity_request,
    encode_integrity_request,
)
from namisync.workflows.runtime import (
    BASELINE_KIND,
    EXECUTION_KIND,
    INVENTORY_KIND,
    REBASELINE_KIND,
    VERIFY_KIND,
    LocalWorkflowRuntime,
)
from namisync.workflows.views import operation_result_view

from _db_fixtures import FakeClock, NOW
from _inventory_fixtures import (
    PROFILE,
    VOLUME_ID,
    _Resolver,
    _Scanner,
    _file,
    _runtime,
    _wait_for,
)


def _outcome(item, mode: IntegrityMode) -> IntegrityOutcome:
    return IntegrityOutcome(
        item_id=item.item_id,
        row_id=item.row_id,
        location_id=item.location_id,
        path=item.display_path,
        phase=mode.value,
        result=IntegrityResult.VERIFIED,
    )


def _refresh_inventory(
    runtime: LocalWorkflowRuntime,
    location_id: int,
    request_id: str,
) -> None:
    prepared = runtime.prepare_inventory(
        InventoryRequest(request_id, location_id=location_id)
    )
    result = runtime.open_inventory(prepared.payload).run(
        RunContext(lambda _event: None, lambda: None)
    )
    assert result.status is SessionState.COMPLETED


def _record_baseline(
    runtime: LocalWorkflowRuntime,
    location_id: int,
    path: str,
) -> str:
    row = next(
        row for row in runtime.list_inventory(location_id) if row.rel_path == path
    )
    assert row.observed is not None
    evidence = Attestation(
        ContentEvidence(
            "xxh3_128",
            b"\x01" * 16,
            row.observed.size,
            Provenance.READBACK_ATTESTED,
            NOW,
        ),
        row.observed,
    )
    with LedgerRecorder(runtime.ledger_path, clock=FakeClock()) as recorder:
        disposition = recorder.record_integrity(
            IntegrityRecordCommand(
                IntegrityMode.BASELINE,
                f"seed-baseline:{row.row_id}",
                row.row_id,
                str(row.location_id),
                row.rel_path_key,
                row.scope_token,
                InventoryState(row.presence.value),
                row.observed,
                None,
                evidence,
                False,
                False,
            )
        )
    assert disposition is RecordDisposition.APPLIED
    return f"{row.location_id}:{row.row_id}"


def _run_integrity_mode(
    runtime: LocalWorkflowRuntime,
    location_id: int,
    mode: IntegrityMode,
    request_id: str,
):
    request = IntegrityRequest(request_id, mode, location_id=location_id)
    if mode is IntegrityMode.BASELINE:
        prepared = runtime.prepare_baseline(request)
        invocation = runtime.open_baseline(prepared.payload)
    elif mode is IntegrityMode.REBASELINE:
        prepared = runtime.prepare_rebaseline(request)
        invocation = runtime.open_rebaseline(prepared.payload)
    else:
        prepared = runtime.prepare_verify(request)
        invocation = runtime.open_verify(prepared.payload)
    return invocation.run(RunContext(lambda _event: None, lambda: None))


def _mixed_integrity_runtime(
    tmp_path: Path,
    runners,
) -> tuple[LocalWorkflowRuntime, int, _Scanner]:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(
        mount,
        (_file("a.txt", 1), _file("b.txt", 2)),
    )
    runtime, location_id = _runtime(
        tmp_path,
        _Resolver(mount),
        scanner,
        runners,
    )
    _refresh_inventory(runtime, location_id, "seed-inventory")
    _record_baseline(runtime, location_id, "a.txt")
    return runtime, location_id, scanner


def _settle_all(
    selection: IntegritySelection,
    context,
    mode: IntegrityMode,
) -> IntegrityRunResult:
    outcomes: list[IntegrityOutcome] = []
    for item in selection.pending:
        size = 0 if item.expected_stat is None else item.expected_stat.size
        selection.note_bytes_processed(size)
        outcome = _outcome(item, mode)
        context.run.emit(outcome)
        selection.mark_completed(item.item_id, size)
        outcomes.append(outcome)
    return IntegrityRunResult(tuple(outcomes), RecordingStatus.OK)


def test_runtime_registers_inventory_and_all_integrity_modes_with_one_factory(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    resolver = _Resolver(mount)
    seen: list[tuple[IntegrityMode, object]] = []

    def runner(mode: IntegrityMode):
        def run(selection, context, recorder):
            del recorder
            seen.append((mode, context.hasher_factory))
            return _settle_all(selection, context, mode)

        return run

    runtime, location_id = _runtime(
        tmp_path,
        resolver,
        scanner,
        {mode: runner(mode) for mode in IntegrityMode},
    )
    try:
        registrations = _workflow_registry(runtime)
        assert set(registrations) == {
            "sync-plan",
            "sync-execution",
            INVENTORY_KIND,
            BASELINE_KIND,
            VERIFY_KIND,
            REBASELINE_KIND,
        }
        assert not registrations[INVENTORY_KIND].supports_pause
        assert all(
            registrations[kind].supports_pause
            for kind in (BASELINE_KIND, VERIFY_KIND, REBASELINE_KIND)
        )
        assert (
            registrations[EXECUTION_KIND].settle_canceled
            == runtime.settle_canceled_execution
        )
        assert all(
            registrations[kind].settle_canceled is None
            for kind in (
                "sync-plan",
                INVENTORY_KIND,
                BASELINE_KIND,
                VERIFY_KIND,
                REBASELINE_KIND,
            )
        )
        dispatcher = Dispatcher(
            registrations,
            lock_provider=InProcessResourceLockProvider(),
            clock=FakeClock(),
        )
        try:
            inventory_id = dispatcher.submit(
                INVENTORY_KIND,
                InventoryRequest("inventory", location_id=location_id),
            )
            _wait_for(
                dispatcher, inventory_id, SessionState.COMPLETED
            )

            kinds = {
                IntegrityMode.BASELINE: BASELINE_KIND,
                IntegrityMode.VERIFY: VERIFY_KIND,
                IntegrityMode.REBASELINE: REBASELINE_KIND,
            }
            for mode, kind in kinds.items():
                session_id = dispatcher.submit(
                    kind,
                    IntegrityRequest(
                        f"{mode.value}-request",
                        mode,
                        location_id=location_id,
                    ),
                )
                record = _wait_for(
                    dispatcher, session_id, SessionState.COMPLETED
                )
                assert record.result is not None
                assert [item.phase for item in record.result.items] == (
                    [] if mode is IntegrityMode.REBASELINE else [mode.value]
                )
        finally:
            assert dispatcher.shutdown().complete

        backend = runtime._executor_policies.copy_backend
        assert backend._hasher_factory is runtime._hasher_factory is xxh3_128
        assert seen == [(mode, xxh3_128) for mode in IntegrityMode]

        with pytest.raises(ValueError, match="mode=verify"):
            runtime.prepare_verify(
                IntegrityRequest(
                    "wrong-mode",
                    IntegrityMode.BASELINE,
                    location_id=location_id,
                )
            )
    finally:
        runtime.close()


@pytest.mark.skipif(os.name != "nt", reason="native verifier is Windows-only")
def test_native_runtime_baseline_then_verify_uses_production_composition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "managed"
    root.mkdir()
    (root / "payload.bin").write_bytes(b"NamiSync runtime integration")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
        clock=FakeClock(),
        host_key="host",
        host_name="Host",
    )
    context = RunContext(lambda _event: None, lambda: None)
    source_open_flags: list[int] = []
    verifier_factories: list[object] = []
    real_open = executor_module.os.open

    def recording_open(path, flags, *args):
        source_open_flags.append(flags)
        return real_open(path, flags, *args)

    monkeypatch.setattr(executor_module.os, "open", recording_open)
    try:
        backend = runtime._executor_policies.copy_backend
        assert backend._hasher_factory is runtime._hasher_factory is xxh3_128
        runners = runtime._integrity_deps.runners
        assert isinstance(runners, dict)
        for mode in (IntegrityMode.BASELINE, IntegrityMode.VERIFY):
            production_runner = runners[mode]

            def capture_factory(
                selection,
                verifier_context,
                recorder,
                *,
                _runner=production_runner,
            ):
                verifier_factories.append(verifier_context.hasher_factory)
                return _runner(selection, verifier_context, recorder)

            runners[mode] = capture_factory
        with runtime._executor_fs.open_source(root / "payload.bin"):
            pass
        assert any(flags & os.O_SEQUENTIAL for flags in source_open_flags)

        baseline_request = runtime.prepare_baseline(
            IntegrityRequest(
                "native-baseline",
                IntegrityMode.BASELINE,
                root_path=str(root),
            )
        )
        baseline_result = runtime.open_baseline(baseline_request.payload).run(
            context
        )
        assert baseline_result.status is SessionState.COMPLETED
        assert [(item.phase, item.result) for item in baseline_result.items] == [
            ("baseline", IntegrityResult.BASELINED)
        ]
        assert (
            baseline_result.items[0].read_strategy
            is ReadStrategy.WINDOWS_UNBUFFERED
        )

        location_id = runtime.get_inventory_details(
            "native-baseline"
        ).location_id
        assert location_id is not None
        verify_request = runtime.prepare_verify(
            IntegrityRequest(
                "native-verify",
                IntegrityMode.VERIFY,
                location_id=location_id,
            )
        )
        verify_result = runtime.open_verify(verify_request.payload).run(context)
        assert verify_result.status is SessionState.COMPLETED
        assert [(item.phase, item.result) for item in verify_result.items] == [
            ("verify", IntegrityResult.VERIFIED)
        ]
        assert (
            verify_result.items[0].read_strategy
            is ReadStrategy.WINDOWS_UNBUFFERED
        )
        assert verifier_factories == [
            runtime._hasher_factory,
            runtime._hasher_factory,
        ]
        assert all(factory is backend._hasher_factory for factory in verifier_factories)
    finally:
        runtime.close()


def test_repeat_full_baseline_refreshes_inventory_but_runs_no_verifier_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    runtime, location_id = _runtime(
        tmp_path,
        _Resolver(mount),
        scanner,
        None,
    )
    context = RunContext(lambda _event: None, lambda: None)
    try:
        _refresh_inventory(runtime, location_id, "seed-inventory")
        _record_baseline(runtime, location_id, "a.txt")
        hash_calls = 0
        record_calls = 0

        def unexpected_hasher():
            nonlocal hash_calls
            hash_calls += 1
            raise AssertionError("repeat baseline must not hash established rows")

        original_record_integrity = LedgerRecorder.record_integrity

        def count_record_integrity(self, command):
            nonlocal record_calls
            record_calls += 1
            return original_record_integrity(self, command)

        runtime._hasher_factory = unexpected_hasher
        monkeypatch.setattr(
            LedgerRecorder,
            "record_integrity",
            count_record_integrity,
        )
        prepared = runtime.prepare_baseline(
            IntegrityRequest(
                "repeat-baseline",
                IntegrityMode.BASELINE,
                location_id=location_id,
            )
        )
        result = runtime.open_baseline(prepared.payload).run(context)

        assert result.status is SessionState.COMPLETED
        assert result.disposition is Disposition.RAN
        assert result.items == ()
        assert result.bytes_done == result.bytes_total == 0
        view = operation_result_view(result)
        assert (view.headline, view.integrity) == ("success", "not-run")
        assert hash_calls == 0
        assert record_calls == 0
        assert len(scanner.calls) == 2
        assert runtime.list_inventory(location_id)[0].scope_token == (
            "repeat-baseline:refresh:0"
        )
    finally:
        runtime.close()


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        pytest.param(
            IntegrityMode.BASELINE,
            ("b.txt",),
            id="baseline-missing-only",
        ),
        pytest.param(
            IntegrityMode.REBASELINE,
            ("a.txt",),
            id="rebaseline-existing-only",
        ),
    ],
)
def test_fresh_integrity_selection_filters_rows_by_mode(
    tmp_path: Path,
    mode: IntegrityMode,
    expected: tuple[str, ...],
) -> None:
    selections: list[tuple[str, ...]] = []

    def runner(selection, context, recorder):
        del context, recorder
        selections.append(tuple(item.display_path for item in selection.items))
        return IntegrityRunResult((), RecordingStatus.OK)

    runtime, location_id, _scanner = _mixed_integrity_runtime(
        tmp_path,
        {mode: runner},
    )
    try:
        result = _run_integrity_mode(
            runtime,
            location_id,
            mode,
            f"mixed-{mode.value}",
        )

        assert result.status is SessionState.COMPLETED
        assert selections == [expected]
    finally:
        runtime.close()


def test_verify_admits_missing_evidence_and_reports_baselined_incomplete(
    tmp_path: Path,
) -> None:
    def runner(selection, context, recorder):
        del recorder
        outcomes: list[IntegrityOutcome] = []
        for item in selection.pending:
            result = (
                IntegrityResult.VERIFIED
                if item.baseline is not None
                else IntegrityResult.BASELINED
            )
            outcome = IntegrityOutcome(
                item_id=item.item_id,
                row_id=item.row_id,
                location_id=item.location_id,
                path=item.display_path,
                phase=IntegrityMode.VERIFY.value,
                result=result,
            )
            selection.mark_completed(item.item_id, 0)
            context.run.emit(outcome)
            outcomes.append(outcome)
        return IntegrityRunResult(tuple(outcomes), RecordingStatus.OK)

    runtime, location_id, _scanner = _mixed_integrity_runtime(
        tmp_path,
        {IntegrityMode.VERIFY: runner},
    )
    try:
        result = _run_integrity_mode(
            runtime,
            location_id,
            IntegrityMode.VERIFY,
            "mixed-verify",
        )

        assert [
            (item.path, item.result)
            for item in result.items
        ] == [
            ("a.txt", IntegrityResult.VERIFIED),
            ("b.txt", IntegrityResult.BASELINED),
        ]
        view = operation_result_view(result)
        assert view.integrity == "baselined"
        assert view.headline == "verification-incomplete"
    finally:
        runtime.close()


def test_resumed_baseline_keeps_frozen_order_after_evidence_changes(
    tmp_path: Path,
) -> None:
    selections: list[tuple[tuple[str, ...], dict[str, int], int]] = []

    def runner(selection, context, recorder):
        del context, recorder
        selections.append(
            (
                tuple(item.item_id for item in selection.items),
                dict(selection.completed_bytes),
                selection.processed_bytes,
            )
        )
        return IntegrityRunResult((), RecordingStatus.OK)

    runtime, location_id, _scanner = _mixed_integrity_runtime(
        tmp_path,
        {IntegrityMode.BASELINE: runner},
    )
    try:
        rows = {
            row.rel_path: f"{row.location_id}:{row.row_id}"
            for row in runtime.list_inventory(location_id)
        }
        _record_baseline(runtime, location_id, "b.txt")
        frozen = (rows["b.txt"], rows["a.txt"])
        prepared = runtime.prepare_baseline(
            IntegrityRequest(
                "binding",
                IntegrityMode.BASELINE,
                location_id=location_id,
            )
        )
        request = IntegrityWorkflowRequest(
            request_id="resume-baseline",
            binding=decode_integrity_request(prepared.payload).binding,
            mode=IntegrityMode.BASELINE,
            selection_item_ids=frozen,
            completed_bytes=((frozen[0], 7),),
            processed_bytes=7,
            refresh_generation=1,
        )

        result = runtime.open_baseline(encode_integrity_request(request)).run(
            RunContext(lambda _event: None, lambda: None)
        )

        assert result.status is SessionState.COMPLETED
        assert selections == [(frozen, {frozen[0]: 7}, 7)]
    finally:
        runtime.close()


def test_resumed_integrity_runtime_queries_only_frozen_row_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selections: list[tuple[str, ...]] = []

    def runner(selection, context, recorder):
        del context, recorder
        selections.append(tuple(item.item_id for item in selection.items))
        return IntegrityRunResult((), RecordingStatus.OK)

    runtime, location_id, _scanner = _mixed_integrity_runtime(
        tmp_path,
        {IntegrityMode.VERIFY: runner},
    )
    try:
        rows = runtime.list_inventory(location_id)
        frozen = tuple(
            f"{row.location_id}:{row.row_id}" for row in reversed(rows)
        )
        prepared = runtime.prepare_verify(
            IntegrityRequest(
                "bounded-resume-binding",
                IntegrityMode.VERIFY,
                location_id=location_id,
            )
        )
        binding = decode_integrity_request(prepared.payload).binding
        full_reads: list[int] = []
        row_id_reads: list[tuple[int, tuple[str, ...]]] = []

        class TrackingRepository(LedgerRepository):
            def get_inventory(self, selected_location_id, path_keys=None):
                if path_keys is None:
                    full_reads.append(selected_location_id)
                return super().get_inventory(selected_location_id, path_keys)

            def get_inventory_by_row_ids(self, selected_location_id, row_ids):
                requested = tuple(row_ids)
                row_id_reads.append((selected_location_id, requested))
                return super().get_inventory_by_row_ids(
                    selected_location_id, requested
                )

        monkeypatch.setattr(
            inventory_workflow,
            "LedgerRepository",
            TrackingRepository,
        )
        request = IntegrityWorkflowRequest(
            request_id="bounded-resume",
            binding=binding,
            mode=IntegrityMode.VERIFY,
            selection_item_ids=frozen,
            refresh_generation=1,
        )

        result = runtime.open_verify(encode_integrity_request(request)).run(
            RunContext(lambda _event: None, lambda: None)
        )

        assert result.status is SessionState.COMPLETED
        assert selections == [frozen]
        assert full_reads == []
        assert row_id_reads == [
            (
                location_id,
                tuple(item_id.split(":", 1)[1] for item_id in frozen),
            )
        ]
    finally:
        runtime.close()


def test_standalone_verify_round_trips_integrity_history_without_phase_rows(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    resolver = _Resolver(mount)

    def verify_runner(selection, context, recorder):
        del recorder
        assert context.hasher_factory is xxh3_128
        return _settle_all(selection, context, IntegrityMode.VERIFY)

    runtime, location_id = _runtime(
        tmp_path,
        resolver,
        scanner,
        {IntegrityMode.VERIFY: verify_runner},
    )
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        session_id = dispatcher.submit(
            VERIFY_KIND,
            IntegrityRequest(
                "history-verify",
                IntegrityMode.VERIFY,
                location_id=location_id,
            ),
        )
        record = _wait_for(dispatcher, session_id, SessionState.COMPLETED)
        assert record.result is not None
        assert record.result.audit is RecordingStatus.OK
        assert len(record.result.items) == 1

        history = runtime.get_history_summary("history-verify")
        items = runtime.get_history_items("history-verify")
        assert history.activity_kind == "verify"
        assert history.subject_kind == "location"
        assert history.subject_id == str(location_id)
        assert history.source_context is None
        assert history.target_context is None
        assert [
            (
                retained.item.item_type,
                retained.item.phase,
                retained.item.path,
                retained.item.result,
            )
            for retained in items.items
        ] == [("integrity", "verify", "a.txt", "verified")]
        assert history.phases == ()

        connection = sqlite3.connect(runtime.history_path)
        try:
            assert connection.execute(
                "SELECT count(*) FROM history_phases"
            ).fetchone()[0] == 0
        finally:
            connection.close()
    finally:
        assert dispatcher.shutdown().complete
        runtime.close()


def test_runtime_exposes_stale_and_missing_visibility_inventory_facade(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    resolver = _Resolver(mount)
    runtime, location_id = _runtime(tmp_path, resolver, scanner, {})
    context = RunContext(lambda _event: None, lambda: None)
    try:
        prepared = runtime.prepare_inventory(
            InventoryRequest("present", location_id=location_id)
        )
        assert (
            runtime.open_inventory(prepared.payload).run(context).status
            is SessionState.COMPLETED
        )
        stale = runtime.list_stale_inventory(location_id, NOW)
        assert [row.rel_path for row in stale] == ["a.txt"]

        scanner.records = ()
        prepared = runtime.prepare_inventory(
            InventoryRequest("missing", location_id=location_id)
        )
        runtime.open_inventory(prepared.payload).run(context)
        missing = runtime.list_unacknowledged_missing(location_id)
        assert [row.rel_path for row in missing] == ["a.txt"]

        row_id = missing[0].row_id
        assert (
            runtime.acknowledge_inventory("ack", location_id, row_id)
            is RecordDisposition.APPLIED
        )
        assert runtime.list_unacknowledged_missing(location_id) == ()
        assert (
            runtime.restore_inventory("restore", location_id, row_id)
            is RecordDisposition.APPLIED
        )
        assert [
            row.rel_path for row in runtime.list_unacknowledged_missing(location_id)
        ] == ["a.txt"]
    finally:
        runtime.close()


def test_paused_verify_resumes_without_repeating_or_losing_items(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(
        mount,
        (_file("a.txt", 1), _file("b.txt", 2)),
    )
    resolver = _Resolver(mount)
    first_completed = Event()
    allow_checkpoint = Event()
    calls = 0

    def verify_runner(selection, context, recorder):
        nonlocal calls
        del recorder
        calls += 1
        outcomes: list[IntegrityOutcome] = []
        for item in selection.pending:
            size = 0 if item.expected_stat is None else item.expected_stat.size
            selection.note_bytes_processed(size)
            outcome = _outcome(item, IntegrityMode.VERIFY)
            context.run.emit(outcome)
            selection.mark_completed(item.item_id, size)
            outcomes.append(outcome)
            if calls == 1:
                first_completed.set()
                assert allow_checkpoint.wait(2)
                context.run.checkpoint()
        return IntegrityRunResult(tuple(outcomes), RecordingStatus.OK)

    runtime, location_id = _runtime(
        tmp_path,
        resolver,
        scanner,
        {IntegrityMode.VERIFY: verify_runner},
    )
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        session_id = dispatcher.submit(
            VERIFY_KIND,
            IntegrityRequest(
                "pause-verify",
                IntegrityMode.VERIFY,
                location_id=location_id,
            ),
        )
        assert first_completed.wait(2)
        assert dispatcher.pause(session_id).accepted
        allow_checkpoint.set()
        paused = _wait_for(dispatcher, session_id, SessionState.PAUSED)
        continuation = decode_integrity_request(paused.payload)
        assert continuation.refresh_generation == 1
        assert len(continuation.selection_item_ids) == 2
        assert len(continuation.completed_bytes) == 1
        assert continuation.processed_bytes == 7
        paused_history = runtime.get_history_summary("pause-verify")
        paused_items = runtime.get_history_items("pause-verify")
        assert paused_history.completion_status == "incomplete"
        assert paused_history.current_state == SessionState.PAUSED.value
        assert [retained.item.path for retained in paused_items.items] == [
            "a.txt"
        ]

        scanner.records += (_file("c.txt", 3),)
        assert dispatcher.resume(session_id).accepted
        completed = _wait_for(dispatcher, session_id, SessionState.COMPLETED)
        assert completed.result is not None
        assert [
            (item.path, item.phase) for item in completed.result.items
        ] == [("a.txt", "verify"), ("b.txt", "verify")]
        assert calls == 2
        assert len(scanner.calls) == 2
        assert [row.rel_path for row in runtime.list_inventory(location_id)] == [
            "a.txt",
            "b.txt",
            "c.txt",
        ]

        history = runtime.get_history_summary("pause-verify")
        items = runtime.get_history_items("pause-verify")
        assert history.item_count == 2
        assert [retained.item.path for retained in items.items] == [
            "a.txt",
            "b.txt",
        ]
    finally:
        allow_checkpoint.set()
        assert dispatcher.shutdown().complete
        runtime.close()


@dataclass
class _BlockingInvocation:
    started: Event
    release: Event

    def run(self, context) -> OperationResult:
        del context
        self.started.set()
        assert self.release.wait(2)
        return OperationResult(SessionState.COMPLETED)

    def snapshot(self) -> bytes:
        return b"blocker"


def test_queued_verify_reopens_and_refuses_new_clone_before_scan_or_hash(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    clone = tmp_path / "clone"
    (mount / "managed").mkdir(parents=True)
    (clone / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    resolver = _Resolver(mount)
    hash_calls = 0

    def verify_runner(selection, context, recorder):
        nonlocal hash_calls
        del selection, context, recorder
        hash_calls += 1
        return IntegrityRunResult((), RecordingStatus.OK)

    runtime, location_id = _runtime(
        tmp_path,
        resolver,
        scanner,
        {IntegrityMode.VERIFY: verify_runner},
    )
    started = Event()
    release = Event()
    resource = ResourceId("volume", f"{VOLUME_ID.serial}:{VOLUME_ID.fs_type}")
    registrations = _workflow_registry(runtime)
    registrations["blocker"] = WorkflowRegistration(
        prepare=lambda _request: PreparedSession(
            b"blocker", frozenset({resource})
        ),
        open=lambda _payload: _BlockingInvocation(started, release),
    )
    dispatcher = Dispatcher(
        registrations,
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        blocker_id = dispatcher.submit("blocker", object())
        assert started.wait(2)
        verify_id = dispatcher.submit(
            VERIFY_KIND,
            IntegrityRequest(
                "queued-clone",
                IntegrityMode.VERIFY,
                location_id=location_id,
            ),
        )
        assert dispatcher.get(verify_id).state is SessionState.PENDING

        resolver.mounts = (mount, clone)
        release.set()
        _wait_for(dispatcher, blocker_id, SessionState.COMPLETED)
        refused = _wait_for(dispatcher, verify_id, SessionState.REFUSED)
        assert refused.result is not None
        assert refused.result.error is not None
        assert "ambiguous" in refused.result.error.message
        assert scanner.calls == []
        assert hash_calls == 0
        assert (
            runtime.get_inventory_details("queued-clone").resolution.state
            is VolumeResolutionState.AMBIGUOUS
        )
    finally:
        release.set()
        assert dispatcher.shutdown().complete
        runtime.close()
