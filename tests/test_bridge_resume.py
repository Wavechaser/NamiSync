from __future__ import annotations

from dataclasses import replace
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
    selection_digest,
)
from namisync.core.session import (
    Disposition,
    PhaseResult,
    PhaseStatus,
    RunContext,
    SessionState,
)
from namisync.workflows.models import (
    ExecuteContinuation,
    ExecutionRequest,
    VerifyContinuation,
)
from namisync.workflows.payloads import (
    decode_execution_request,
    encode_execution_request,
)
from namisync.workflows.selection import derive_execution_selection
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


def test_br_g_10_payload_roundtrip_preserves_direct_and_fallout_outcomes() -> None:
    request = ExecutionRequest(ExecuteContinuation(_selection_fixture(tampered=False)))
    resumed = decode_execution_request(encode_execution_request(request))
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
        open_recording=lambda _xset: _Recording(finished),
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
    resumed = decode_execution_request(
        encode_execution_request(ExecutionRequest(continuation))
    )
    finished: list[SessionState] = []
    deps = SimpleNamespace(
        save_execution_details=lambda _details: None,
        observer=lambda *_args: pytest.fail("preflight observation ran"),
        open_recording=lambda _xset: _Recording(finished),
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
