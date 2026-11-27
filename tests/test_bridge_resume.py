from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import timedelta
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import pytest

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.execution import (
    Commitment,
    ExecutionSet,
    TaskRecordingIssueReason,
    validated_run_id,
)
from namisync.core.integrity import PostCopySelection
from namisync.core.planning import (
    OperationKind,
    OperationReason,
    plan_fingerprint,
    selection_digest,
)
from namisync.core.session import (
    Disposition,
    PhaseResult,
    PhaseStatus,
    RunContext,
    SessionState,
)
from namisync.db.claims import DatabaseInUse, hold_maintenance_claims
from namisync.dispatcher import Dispatcher, InProcessResourceLockProvider
from namisync.interfaces.service import _workflow_registry
from namisync.workflows.database_maintenance import (
    backup_database_pair,
    restore_database_from_backup,
)
from namisync.workflows.models import (
    ExecuteContinuation,
    ExecutionCheckpoint,
    ExecutionRequest,
    PlanRequest,
    VerifyContinuation,
)
from namisync.workflows.selection import derive_execution_selection
from namisync.workflows.runtime import EXECUTION_KIND, LocalWorkflowRuntime
from namisync.workflows.sync import run_execution

from _db_fixtures import (
    NOW,
    FakeClock,
    file_stat,
    operation,
    plan,
    replace_ledger_instance,
)


class _Recording:
    recorder = object()

    def __init__(self, finished: list[SessionState]) -> None:
        self._finished = finished

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def finish(
        self,
        status: SessionState,
        recording: RecordingStatus,
    ) -> None:
        self._finished.append(status)


def _selection_fixture(*, tampered: bool) -> ExecutionSet:
    folder = operation(
        OperationKind.MKDIR,
        source_path="folder",
        target_path="folder",
        reason=OperationReason.REQUIRED_DIRECTORY,
    )
    child = replace(
        operation(
            OperationKind.COPY,
            source_path=r"folder\child.bin",
            target_path=r"folder\child.bin",
            source=file_stat(),
        ),
        dependencies=(folder.op_id,),
    )
    noop = operation(
        OperationKind.NOOP,
        source_path="same.bin",
        target_path="same.bin",
        reason=OperationReason.METADATA_MATCH,
    )
    plan_value = plan((folder, child, noop))
    plan_value = replace(
        plan_value,
        fingerprint=plan_fingerprint(plan_value),
    )
    user_deselected = frozenset({folder.op_id})
    selection = derive_execution_selection(
        plan_value,
        user_deselected=user_deselected,
    ).selection
    if tampered:
        selection |= {child.op_id}
    return ExecutionSet(
        plan_value,
        selection,
        validated_run_id("9" * 32),
        commitment=Commitment(
            plan_value.fingerprint,
            selection_digest(selection),
            NOW,
        ),
        user_deselected=user_deselected,
    )


def test_br_g_10_checkpoint_preserves_direct_and_fallout_outcomes() -> None:
    request = ExecutionRequest(ExecuteContinuation(_selection_fixture(tampered=False)))
    checkpoint = ExecutionCheckpoint(request)
    resumed = checkpoint.materialize()
    request.execution_set.user_deselected = frozenset()
    assert checkpoint.materialize() == resumed
    finished: list[SessionState] = []
    events: list[object] = []
    deps = SimpleNamespace(
        save_execution_details=lambda _details: None,
        observer=lambda _xset, _fs: object(),
        observation_fs=object(),
        preflight=lambda _xset, _world: SimpleNamespace(
            ok=False,
            refusals=(),
        ),
        open_recording=lambda _spec: _Recording(finished),
        finish_existing_recording=lambda _spec, status, _recording: finished.append(
            status
        ),
    )

    result = run_execution(
        resumed.continuation,
        RunContext(events.append, lambda: None),
        deps,
        resumed=True,
    )

    outcomes = {
        item.kind: (item.outcome, item.reason)
        for item in result.items
    }
    assert outcomes["mkdir"] == (
        Outcome.SKIPPED,
        "user-deselected",
    )
    assert outcomes["copy"] == (
        Outcome.DEFERRED,
        "blocked-dependency",
    )
    assert result.disposition is Disposition.RAN
    assert finished == [SessionState.FAILED]


@pytest.mark.parametrize("phase", ["execute", "verify"])
def test_br_g_10_tampered_execute_and_verify_resume_fail_before_preflight(
    phase: str,
) -> None:
    xset = _selection_fixture(tampered=True)
    continuation = (
        ExecuteContinuation(xset)
        if phase == "execute"
        else VerifyContinuation(
            xset,
            PostCopySelection(()),
            SessionState.COMPLETED,
            RecordingStatus.OK,
            PhaseResult(
                "execute",
                PhaseStatus.COMPLETED,
                1,
                1,
                0,
                0,
            ),
        )
    )
    resumed = ExecutionCheckpoint(ExecutionRequest(continuation)).materialize()
    finished: list[SessionState] = []
    deps = SimpleNamespace(
        save_execution_details=lambda _details: None,
        observer=lambda *_args: pytest.fail("preflight observation ran"),
        open_recording=lambda _spec: _Recording(finished),
        finish_existing_recording=lambda _spec, status, _recording: finished.append(
            status
        ),
    )

    result = run_execution(
        resumed.continuation,
        RunContext(lambda _event: None, lambda: None),
        deps,
        resumed=True,
    )

    assert result.disposition is Disposition.RAN
    assert result.error is not None
    assert "derived selection" in result.error.message
    if phase == "execute":
        assert result.status is SessionState.FAILED
        assert finished == [SessionState.FAILED]
    else:
        assert result.status is SessionState.COMPLETED
        assert result.phases[-1].status is PhaseStatus.INCOMPLETE
        assert finished == [SessionState.COMPLETED]


@pytest.mark.parametrize("failure", ["refused", "exception"])
def test_fresh_execution_releases_runtime_custody_before_recording(
    tmp_path,
    failure: str,
) -> None:
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    xset = _selection_fixture(tampered=failure == "refused")
    if failure == "exception":
        plan_value = replace(
            xset.plan,
            fingerprint=plan_fingerprint(xset.plan),
        )
        selection = derive_execution_selection(plan_value).selection
        xset = replace(
            xset,
            plan=plan_value,
            selection=selection,
            user_deselected=frozenset(),
            commitment=replace(
                xset.commitment,
                plan_fingerprint=plan_value.fingerprint,
                selection_digest=selection_digest(selection),
            ),
        )
        runtime._deps = replace(
            runtime._deps,
            observer=lambda *_args: (_ for _ in ()).throw(
                RuntimeError("preflight observation failed")
            ),
        )

    try:
        invocation = runtime.open_execution(
            ExecutionCheckpoint(ExecutionRequest(ExecuteContinuation(xset)))
        )
        assert str(xset.run_id) not in runtime._execution_started
        if failure == "exception":
            result = invocation.run(
                RunContext(lambda _event: None, lambda: None)
            )
            assert result.status is SessionState.FAILED
            assert result.disposition is Disposition.UNRUN
            assert result.phases == ()
            assert result.error is not None
            assert result.error.type_name == "RuntimeError"
            assert result.error.message == "preflight observation failed"
        else:
            result = invocation.run(
                RunContext(lambda _event: None, lambda: None)
            )
            assert result.status is SessionState.REFUSED
            assert result.disposition is Disposition.UNRUN

        assert str(xset.run_id) not in runtime._execution_started
    finally:
        runtime.close()


@pytest.mark.parametrize("failure", ("open", "finish"))
def test_canceled_execution_settlement_releases_custody_on_recording_failure(
    tmp_path,
    failure: str,
) -> None:
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    xset = _selection_fixture(tampered=False)
    request = ExecutionRequest(ExecuteContinuation(xset), NOW)
    run_token = str(xset.run_id)
    runtime._execution_started[run_token] = NOW

    class FailingRecording:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def finish(
            self,
            status: SessionState,
            recording: RecordingStatus,
        ) -> None:
            raise RuntimeError("finish failed")

    def open_recording(_spec):
        if failure == "open":
            raise RuntimeError("open failed")
        return FailingRecording()

    runtime._deps = replace(
        runtime._deps,
        open_recording=open_recording,
    )
    try:
        result = runtime.settle_canceled_execution(
            ExecutionCheckpoint(request),
            Disposition.RAN,
        )
        assert result.canceled
        assert result.recording is RecordingStatus.DEGRADED
        if failure == "open":
            assert result.error is not None
            assert result.error.type_name == "RuntimeError"
            assert result.error.message == "open failed"
        else:
            assert result.error is None

        assert run_token not in runtime._execution_started
    finally:
        runtime.close()


@pytest.mark.parametrize(
    "cancel_after_resume",
    (False, True),
    ids=("while-paused", "before-resumed-invocation"),
)
def test_execution_pause_before_workflow_entry_snapshots_custody_for_cancel(
    tmp_path,
    monkeypatch,
    cancel_after_resume: bool,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.bin").write_bytes(b"pre-run pause")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )
    entered = Event()
    release = Event()
    resumed_entered = Event()
    resumed_release = Event()
    run_core_calls = 0
    original_run_core = dispatcher._run_core

    def blocking_run_core(*args, **kwargs):
        nonlocal run_core_calls
        run_core_calls += 1
        if run_core_calls == 1:
            entered.set()
            assert release.wait(2)
        elif cancel_after_resume:
            resumed_entered.set()
            assert resumed_release.wait(2)
        return original_run_core(*args, **kwargs)

    monkeypatch.setattr(dispatcher, "_run_core", blocking_run_core)

    def wait_for(state: SessionState):
        deadline = monotonic() + 3
        while monotonic() < deadline:
            record = dispatcher.get(session_id)
            if record.state is state and (
                state is SessionState.PAUSED or record.result is not None
            ):
                return record
            sleep(0.01)
        pytest.fail(f"session did not reach {state.value}")

    try:
        request = PlanRequest("7" * 32, str(source), str(target))
        runtime.open_plan(runtime.prepare_plan(request).checkpoint).run(
            RunContext(lambda _event: None, lambda: None)
        )
        execution = runtime.commit_plan(
            request.request_id,
            run_id="8" * 32,
            committed_at=NOW,
        )
        session_id = dispatcher.submit(EXECUTION_KIND, execution)
        assert entered.wait(2)
        assert dispatcher.pause(session_id).accepted
        release.set()
        wait_for(SessionState.PAUSED)

        retained = dispatcher.get(session_id).checkpoint
        assert type(retained) is ExecutionCheckpoint
        decoded = retained.materialize()
        assert decoded.started_at is not None
        assert (
            runtime._execution_started[str(execution.execution_set.run_id)]
            == decoded.started_at
        )

        deadline = monotonic() + 2
        while monotonic() < deadline:
            with dispatcher._condition:
                if session_id not in dispatcher._current_workers:
                    break
            sleep(0.005)
        else:
            pytest.fail("paused worker did not finish")

        if cancel_after_resume:
            assert dispatcher.resume(session_id).accepted
            assert resumed_entered.wait(2)
            assert dispatcher.get(session_id).state is SessionState.RUNNING
        assert dispatcher.cancel(session_id).accepted
        resumed_release.set()
        record = wait_for(SessionState.CANCELED)
    finally:
        release.set()
        resumed_release.set()
        dispatcher.shutdown()
        runtime.close()

    assert record.result is not None
    assert record.result.disposition is Disposition.RAN
    assert str(execution.execution_set.run_id) not in runtime._execution_started
    connection = sqlite3.connect(tmp_path / "ledger.db")
    try:
        row = connection.execute(
            """SELECT ended_at, filesystem_status
                 FROM runs WHERE run_token = ?""",
            ("8" * 32,),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    assert row[0] is not None
    assert row[1] == SessionState.CANCELED.value


def test_br_g_10_dispatcher_pause_resume_reopens_the_same_run(
    tmp_path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.bin").write_bytes(b"dispatcher resume")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    original_verifier = runtime._deps.verifier
    entered = Event()
    calls = 0

    def pause_once(selection, context, recorder):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            while True:
                context.run.checkpoint()
                sleep(0.005)
        return original_verifier(selection, context, recorder)

    runtime._deps = replace(runtime._deps, verifier=pause_once)
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )

    def wait_for(state: SessionState):
        deadline = monotonic() + 3
        while monotonic() < deadline:
            record = dispatcher.get(session_id)
            if record.state is state and (
                state is SessionState.PAUSED or record.result is not None
            ):
                return record
            sleep(0.01)
        pytest.fail(f"session did not reach {state.value}")

    try:
        request = PlanRequest("3" * 32, str(source), str(target))
        runtime.open_plan(runtime.prepare_plan(request).checkpoint).run(
            RunContext(lambda _event: None, lambda: None)
        )
        execution = runtime.commit_plan(
            request.request_id,
            run_id="4" * 32,
            committed_at=NOW,
            verify_after_execute=True,
        )
        session_id = dispatcher.submit(EXECUTION_KIND, execution)
        assert entered.wait(2)
        assert dispatcher.pause(session_id).accepted
        wait_for(SessionState.PAUSED)
        assert dispatcher.resume(session_id).accepted
        record = wait_for(SessionState.COMPLETED)
    finally:
        dispatcher.shutdown()
        runtime.close()

    assert calls == 2
    assert record.result is not None
    assert record.result.status is SessionState.COMPLETED
    assert (target / "payload.bin").read_bytes() == b"dispatcher resume"
    connection = sqlite3.connect(tmp_path / "ledger.db")
    try:
        row = connection.execute(
            "SELECT ended_at, filesystem_status FROM runs WHERE run_token = ?",
            ("4" * 32,),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    assert row[0] is not None
    assert row[1] == SessionState.COMPLETED.value


@pytest.mark.parametrize("bulk", [False, True])
def test_a_resume_failing_before_it_runs_keeps_its_completed_work(
    tmp_path,
    bulk: bool,
) -> None:
    """A copy finished before a pause in Verify stays in History and the ledger."""

    class LockProvider(InProcessResourceLockProvider):
        failing = False

        def acquire(self, resources, canceled):
            if self.failing:
                raise PermissionError("reacquisition failed")
            return super().acquire(resources, canceled)

    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "proof.bin").write_bytes(b"published before the pause")
    runtime = LocalWorkflowRuntime(tmp_path / "ledger.db", tmp_path / "history.db")
    verifying = Event()

    def verifier(selection, context, recorder):
        verifying.set()
        while True:
            context.run.checkpoint()
            sleep(0.005)

    runtime._deps = replace(runtime._deps, verifier=verifier)
    provider = LockProvider()
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=provider,
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        execution = _plan_and_commit(
            runtime, source, target, "3" * 32, "4" * 32, verify_after_execute=True
        )
        session_id = dispatcher.submit(EXECUTION_KIND, execution)
        assert verifying.wait(8)
        assert dispatcher.pause(session_id).accepted
        deadline = monotonic() + 5
        while dispatcher.get(session_id).state is not SessionState.PAUSED:
            assert monotonic() < deadline
            sleep(0.01)
        provider.failing = True
        if bulk:
            assert dispatcher.resume_all().resumed == 1
        else:
            assert dispatcher.resume(session_id).accepted
        record = _settled(dispatcher, session_id)
        dispatcher.close(session_id)
        assert runtime._execution_started == {}
    finally:
        dispatcher.shutdown(8)
        runtime.close()

    result = record.result
    assert record.state is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert (result.bytes_done, result.bytes_total) == (26, 26)
    assert [(phase.phase, phase.status) for phase in result.phases] == [
        ("execute", PhaseStatus.COMPLETED),
        ("verify", PhaseStatus.INCOMPLETE),
    ]
    assert (target / "proof.bin").read_bytes() == b"published before the pause"
    ended_at, filesystem_status = _ledger_rows(
        tmp_path / "ledger.db", "runs", "ended_at, filesystem_status"
    )[0]
    assert ended_at is not None
    assert filesystem_status == SessionState.COMPLETED.value
    phases = _ledger_rows(tmp_path / "history.db", "history_phases")
    assert [row[2:8] for row in phases] == [
        ("execute", "completed", 1, 1, 26, 26),
        ("verify", "incomplete", 0, 1, 0, 26),
    ]


def _ledger_rows(ledger, table: str, columns: str = "*") -> list[tuple]:
    connection = sqlite3.connect(ledger)
    try:
        return connection.execute(f"SELECT {columns} FROM {table}").fetchall()
    finally:
        connection.close()


def _stored_instance(ledger) -> str:
    connection = sqlite3.connect(ledger)
    try:
        return connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'instance_id'"
        ).fetchone()[0]
    finally:
        connection.close()


def _plan_and_commit(runtime, source, target, request_id: str, run_id: str, **commit):
    request = PlanRequest(request_id, str(source), str(target))
    runtime.open_plan(runtime.prepare_plan(request).checkpoint).run(
        RunContext(lambda _event: None, lambda: None)
    )
    return runtime.commit_plan(request_id, run_id=run_id, committed_at=NOW, **commit)


def _settled(dispatcher, session_id):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        record = dispatcher.get(session_id)
        if record.result is not None:
            return record
        sleep(0.01)
    pytest.fail("session did not settle")


def _ledger_issue_reasons(result) -> set[TaskRecordingIssueReason]:
    return {
        issue.reason
        for issue in result.recording_issues
        if (issue.detail or "").startswith("LedgerInstanceChanged:")
    }


def test_execution_start_refuses_a_plan_made_against_a_replaced_ledger(tmp_path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.bin").write_bytes(b"reviewed")
    ledger = tmp_path / "ledger.db"
    runtime = LocalWorkflowRuntime(ledger, tmp_path / "history.db")
    runtime.initialize_database_contracts()
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        stale = _plan_and_commit(runtime, source, target, "1" * 32, "2" * 32)
        assert stale.execution_set.commitment.ledger_instance_id == _stored_instance(ledger)
        replace_ledger_instance(ledger)

        refused = _settled(dispatcher, dispatcher.submit(EXECUTION_KIND, stale))
        assert list(target.iterdir()) == []
        assert _ledger_rows(ledger, "runs") == []
        assert _ledger_rows(ledger, "hosts") == []
        details = runtime.get_execution_details("2" * 32)
        history = runtime.get_history_summary("2" * 32)

        # A plan made against the current ledger still executes.
        current = _plan_and_commit(runtime, source, target, "3" * 32, "4" * 32)
        assert current.execution_set.commitment.ledger_instance_id == _stored_instance(ledger)
        completed = _settled(dispatcher, dispatcher.submit(EXECUTION_KIND, current))
    finally:
        dispatcher.shutdown()
        runtime.close()

    assert refused.result.status is SessionState.REFUSED
    assert refused.result.disposition is Disposition.UNRUN
    assert details.commitment_error.startswith("The ledger was replaced")
    assert details.commitment_error.endswith("Plan again to review it against the current ledger.")
    assert (history.completion_status, history.filesystem_status) == ("finalized", "refused")
    assert history.disposition == "unrun"
    assert completed.result.status is SessionState.COMPLETED
    assert (target / "payload.bin").read_bytes() == b"reviewed"
    assert _ledger_rows(ledger, "runs", "run_token") == [("4" * 32,)]


@pytest.mark.parametrize("audited", (False, True))
@pytest.mark.parametrize("phase", ("execute", "verify"))
def test_resume_refuses_a_paused_run_whose_ledger_was_replaced(
    tmp_path, monkeypatch, phase: str, audited: bool,
) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.bin").write_bytes(b"paused")
    ledger = tmp_path / "ledger.db"
    runtime = LocalWorkflowRuntime(ledger, tmp_path / "history.db")
    runtime.initialize_database_contracts()
    entered = Event()
    release = Event()

    def pause_in_verify(_selection, context, _recorder):
        entered.set()
        while True:
            context.run.checkpoint()
            sleep(0.005)

    if phase == "verify":
        runtime._deps = replace(runtime._deps, verifier=pause_in_verify)
    # Without a History observer, as with degraded audit, a paused run holds
    # no claim; with one it holds the ledger's across its pause.
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer if audited else None,
    )
    if phase == "execute":
        original_run_core = dispatcher._run_core

        def paused_before_entry(*args, **kwargs):
            if not entered.is_set():
                entered.set()
                assert release.wait(2)
            return original_run_core(*args, **kwargs)

        monkeypatch.setattr(dispatcher, "_run_core", paused_before_entry)
    try:
        execution = _plan_and_commit(
            runtime, source, target, "5" * 32, "6" * 32, verify_after_execute=True,
        )
        session_id = dispatcher.submit(EXECUTION_KIND, execution)
        assert entered.wait(2)
        assert dispatcher.pause(session_id).accepted
        release.set()
        deadline = monotonic() + 3
        while dispatcher.get(session_id).state is not SessionState.PAUSED or session_id in dispatcher._current_workers:
            assert monotonic() < deadline, "session did not pause"
            sleep(0.01)
        runs_before = _ledger_rows(ledger, "runs")
        if audited:
            with pytest.raises(DatabaseInUse):
                replace_ledger_instance(ledger)
            return
        replace_ledger_instance(ledger)
        assert dispatcher.resume(session_id).accepted
        record = _settled(dispatcher, session_id)
    finally:
        release.set()
        dispatcher.shutdown()
        runtime.close()

    result = record.result
    assert result.disposition is Disposition.RAN
    assert result.recording is RecordingStatus.DEGRADED
    assert "The ledger was replaced" in result.error.message
    # The finish is refused under the recorder's claim, never written.
    assert _ledger_issue_reasons(result) == {TaskRecordingIssueReason.FINISH_FAILED}
    assert _ledger_rows(ledger, "runs") == runs_before
    if phase == "execute":
        assert result.status is SessionState.FAILED
        assert result.error.type_name == "ExecutionResumeCommitmentInvalid"
        assert list(target.iterdir()) == []
        assert runs_before == []
    else:
        assert result.status is SessionState.COMPLETED
        assert result.phases[-1].status is PhaseStatus.INCOMPLETE
        assert result.error.type_name == "VerificationContinuationInvalid"
        assert (target / "payload.bin").read_bytes() == b"paused"
        assert len(runs_before) == 1


def test_ledger_writer_refuses_a_replacement_after_the_start_check(tmp_path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.bin").write_bytes(b"window")
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    runtime = LocalWorkflowRuntime(ledger, history)
    runtime.initialize_database_contracts()
    original_observer = runtime._deps.observer

    def replaced_during_preflight(*args, **kwargs):
        # After the start check, before the run's ledger writer takes its claim.
        replace_ledger_instance(ledger)
        return original_observer(*args, **kwargs)

    try:
        execution = _plan_and_commit(runtime, source, target, "7" * 32, "8" * 32)
        runtime._deps = replace(runtime._deps, observer=replaced_during_preflight)
        result = runtime.open_execution(ExecutionCheckpoint(execution)).run(
            RunContext(lambda _event: None, lambda: None)
        )
    finally:
        runtime.close()

    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert result.error.type_name == "LedgerInstanceChanged"
    assert _ledger_issue_reasons(result) == {
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
        TaskRecordingIssueReason.FINISH_FAILED,
    }
    assert list(target.iterdir()) == []
    assert _ledger_rows(ledger, "hosts") == []
    assert _ledger_rows(ledger, "runs") == []
    with hold_maintenance_claims(ledger, history):
        pass


def _pausing_once(original, entered: Event, checkpoint):
    # Holds the first call at its checkpoint until the session pauses.
    calls = 0

    def pausing(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            while True:
                checkpoint(args[1])
                sleep(0.005)
        return original(*args)

    return pausing


def _first_use_run_paused_in(tmp_path, phase: str):
    """A plan made before either database existed, paused in ``phase`` after
    its first recorder wrote the run. No History observer, as with degraded
    audit, so the paused run holds no claim and a restore can land."""

    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.bin").write_bytes(b"first use")
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    runtime = LocalWorkflowRuntime(ledger, history)
    entered = Event()
    if phase == "execute":
        runtime._deps = replace(runtime._deps, executor=_pausing_once(
            runtime._deps.executor, entered, lambda context: context.checkpoint(),
        ))
    else:
        runtime._deps = replace(runtime._deps, verifier=_pausing_once(
            runtime._deps.verifier, entered, lambda context: context.run.checkpoint(),
        ))
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
    )
    execution = _plan_and_commit(
        runtime, source, target, "a" * 32, "b" * 32, verify_after_execute=True,
    )
    assert execution.execution_set.commitment.ledger_instance_id is None
    # The pair is created after planning, as admission does; this backup holds
    # no run.
    runtime.initialize_database_contracts()
    backup = next(
        item.path
        for item in backup_database_pair(ledger, history, clock=FakeClock()).backups
        if item.role == "ledger"
    )
    session_id = dispatcher.submit(EXECUTION_KIND, execution)
    assert entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    deadline = monotonic() + 3
    while (
        dispatcher.get(session_id).state is not SessionState.PAUSED
        or session_id in dispatcher._current_workers
    ):
        assert monotonic() < deadline, "session did not pause"
        sleep(0.01)
    assert _ledger_rows(ledger, "runs", "run_token") == [("b" * 32,)]
    return runtime, dispatcher, session_id, backup


@pytest.mark.parametrize("phase", ("execute", "verify"))
def test_resume_refuses_a_first_use_run_whose_ledger_was_restored(
    tmp_path, phase: str,
) -> None:
    ledger, target = tmp_path / "ledger.db", tmp_path / "target"
    runtime, dispatcher, session_id, backup = _first_use_run_paused_in(tmp_path, phase)
    try:
        bound = _stored_instance(ledger)
        restored = restore_database_from_backup(
            ledger, tmp_path / "history.db", "ledger", backup,
            clock=FakeClock(NOW + timedelta(seconds=1)),
        )
        assert restored.restore is not None, restored.contract
        assert _stored_instance(ledger) != bound
        assert _ledger_rows(ledger, "runs") == []
        assert dispatcher.resume(session_id).accepted
        record = _settled(dispatcher, session_id)
    finally:
        dispatcher.shutdown()
        runtime.close()

    result = record.result
    assert result.disposition is Disposition.RAN
    assert result.recording is RecordingStatus.DEGRADED
    assert "The ledger was replaced" in result.error.message
    # Refused before any ledger write: the run is not recreated, nor finished.
    assert _ledger_issue_reasons(result) == {TaskRecordingIssueReason.FINISH_FAILED}
    assert _ledger_rows(ledger, "runs") == []
    if phase == "execute":
        assert result.status is SessionState.FAILED
        assert result.error.type_name == "ExecutionResumeCommitmentInvalid"
        assert list(target.iterdir()) == []
    else:
        assert result.status is SessionState.COMPLETED
        assert result.phases[-1].status is PhaseStatus.INCOMPLETE
        assert result.error.type_name == "VerificationContinuationInvalid"
        assert (target / "payload.bin").read_bytes() == b"first use"


@pytest.mark.parametrize("phase", ("execute", "verify"))
def test_first_use_run_resumes_against_the_ledger_it_was_bound_to(
    tmp_path, phase: str,
) -> None:
    ledger, target = tmp_path / "ledger.db", tmp_path / "target"
    runtime, dispatcher, session_id, _backup = _first_use_run_paused_in(tmp_path, phase)
    try:
        bound = _stored_instance(ledger)
        assert runtime._execution_ledger == {"b" * 32: bound}
        assert dispatcher.resume(session_id).accepted
        record = _settled(dispatcher, session_id)
        assert runtime._execution_ledger == {}
    finally:
        dispatcher.shutdown()
        runtime.close()

    assert record.result.status is SessionState.COMPLETED
    assert record.result.recording is RecordingStatus.OK
    assert record.result.error is None
    assert (target / "payload.bin").read_bytes() == b"first use"
    assert _ledger_rows(ledger, "runs", "run_token, filesystem_status") == [
        ("b" * 32, SessionState.COMPLETED.value)
    ]


def test_first_use_resume_recorder_refuses_a_replacement_after_the_resume_check(
    tmp_path,
) -> None:
    ledger, target = tmp_path / "ledger.db", tmp_path / "target"
    runtime, dispatcher, session_id, _backup = _first_use_run_paused_in(tmp_path, "verify")
    original_observer = runtime._deps.observer

    def replaced_during_preflight(*args, **kwargs):
        # After the resume check, before the resumed recorder takes its claim.
        replace_ledger_instance(ledger)
        return original_observer(*args, **kwargs)

    # Each resumed invocation reads the runtime's dependencies afresh.
    runtime._deps = replace(runtime._deps, observer=replaced_during_preflight)
    try:
        runs_before = _ledger_rows(ledger, "runs")
        assert dispatcher.resume(session_id).accepted
        record = _settled(dispatcher, session_id)
    finally:
        dispatcher.shutdown()
        runtime.close()

    result = record.result
    assert result.recording is RecordingStatus.DEGRADED
    assert result.phases[-1].status is PhaseStatus.INCOMPLETE
    assert TaskRecordingIssueReason.RECORDING_OPEN_FAILED in _ledger_issue_reasons(result)
    # Neither the resumed recorder nor the finish wrote to the replaced ledger.
    assert _ledger_rows(ledger, "runs") == runs_before
    assert (target / "payload.bin").read_bytes() == b"first use"
