from __future__ import annotations

import sqlite3
from dataclasses import replace
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import pytest

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.execution import (
    Commitment,
    ExecutionSet,
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
from namisync.dispatcher import Dispatcher, InProcessResourceLockProvider
from namisync.interfaces.service import _workflow_registry
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

from _db_fixtures import NOW, file_stat, operation, plan


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
