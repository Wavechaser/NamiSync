from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from shutil import copy2
from threading import Event, Lock, Thread
from time import monotonic, sleep
from types import SimpleNamespace

import pytest

import namisync.workflows.sync as sync_workflow_module
from namisync.core.integrity import RecordDisposition
from namisync.core.models import EntryKind, ScanWarning, ScanWarningCode
from namisync.core.pathing import to_extended_length_path
from namisync.core.planning import BlockedReason, OperationKind, OperationReason
from namisync.core.session import SessionState
from namisync.db.repositories import InventoryPresence, InventorySnapshot
from namisync.dispatcher import SessionNotFound
from namisync.interfaces.service import (
    ExecutionAdmissionView,
    ExecutionSession,
    NamiSyncService,
    SyncPathInputError,
)
from namisync.workflows.node_tree import (
    NodeTreeKind,
    NodeTreeMember,
    build_node_tree,
)

from _db_fixtures import NOW, file_stat, operation, plan


def _artifact(plan_value):
    return SimpleNamespace(plan=plan_value)


class _PlanRuntime:
    def __init__(self, artifact) -> None:
        self.artifact = artifact
        self.commits: list[tuple[str, bool, frozenset[str]]] = []

    def get_plan(self, request_id: str):
        return self.artifact

    def get_plan_review(
        self,
        request_id: str,
        *,
        user_deselected: frozenset[str] = frozenset(),
        expected_artifact=None,
    ):
        if expected_artifact is not None and expected_artifact is not self.artifact:
            raise ValueError("plan changed before review projection")
        return SimpleNamespace(user_deselected=user_deselected)

    def commit_plan(
        self,
        request_id: str,
        *,
        verify_after_execute: bool = False,
        user_deselected: frozenset[str] = frozenset(),
        expected_artifact=None,
    ):
        assert expected_artifact is self.artifact
        self.commits.append(
            (request_id, verify_after_execute, user_deselected)
        )
        return SimpleNamespace(
            execution_set=SimpleNamespace(
                run_id=f"{len(self.commits):032x}",
            )
        )


class _Dispatcher:
    def __init__(self) -> None:
        self.submissions: list[tuple[str, object]] = []
        self.closed: list[str] = []

    def submit(self, kind: str, request: object) -> str:
        self.submissions.append((kind, request))
        return f"session-{len(self.submissions)}"

    def close(self, session_id: str) -> None:
        self.closed.append(session_id)


def _service(runtime, dispatcher=None) -> NamiSyncService:
    service = object.__new__(NamiSyncService)
    service._runtime = runtime
    service._dispatcher = dispatcher or _Dispatcher()
    service._observer = SimpleNamespace(unsubscribe=lambda _session_id: None)
    service._lock = Lock()
    service._plan_selections = {}
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._session_receipt_locks = tuple(Lock() for _ in range(64))
    service._session_receipt_lifecycle = Lock()
    service._visibility_receipts = {}
    service._closed = False
    service._shutdown = None
    return service


def _inventory_row(
    row_id: str,
    path: str,
    *,
    kind: EntryKind = EntryKind.FILE,
    presence: InventoryPresence = InventoryPresence.PRESENT,
) -> InventorySnapshot:
    return InventorySnapshot(
        row_id=row_id,
        location_id=7,
        rel_path=path,
        rel_path_key=path.upper(),
        entry_kind=kind,
        presence=presence,
        observed=file_stat(),
        attestation=None,
        last_observed_at=NOW,
        last_verified_at=None,
        scope_token="scope",
        missing_since=NOW if presence is InventoryPresence.MISSING else None,
        acknowledged_at=None,
        reappeared_at=None,
        unsupported_reason=None,
        hardlink_group=None,
    )


def test_br_g_13_replan_discards_selection_even_with_identical_operation_ids() -> None:
    copied = operation(OperationKind.COPY, source=file_stat())
    plan_value = plan((copied,))
    runtime = _PlanRuntime(_artifact(plan_value))
    service = _service(runtime)

    initial = service.preview_selection("request")
    changed = service.mutate_selection(
        "request",
        0,
        deselect=(str(copied.op_id),),
        command_id="old-plan-gesture",
    ).preview
    runtime.artifact = _artifact(plan_value)
    replanned = service.preview_selection("request")
    replayed = service.mutate_selection(
        "request",
        0,
        deselect=(str(copied.op_id),),
        command_id="old-plan-gesture",
    )
    stale_mutation = service.mutate_selection(
        "request",
        changed.revision,
        deselect=(str(copied.op_id),),
        command_id="late-old-plan-gesture",
    )
    stale_execution = service.start_execution(
        "request",
        expected_revision=changed.revision,
    )

    assert changed.revision == 1
    assert changed.selection_digest != initial.selection_digest
    assert replanned.revision > changed.revision
    assert replanned.user_deselected == ()
    assert replanned.selection_digest == initial.selection_digest
    assert replayed.disposition == "noop"
    assert replayed.preview.user_deselected == ()
    assert stale_mutation.disposition == "conflict"
    assert isinstance(stale_execution, ExecutionAdmissionView)
    assert stale_execution.disposition == "conflict"


def test_br_g_13_mutation_racing_replan_returns_the_current_artifact() -> None:
    copied = operation(OperationKind.COPY, source=file_stat())
    plan_value = plan((copied,))
    first_artifact = _artifact(plan_value)
    runtime = _PlanRuntime(first_artifact)
    service = _service(runtime)
    service.preview_selection("request")
    entered = Event()
    release = Event()
    original_resolve = service._resolve_plan_selection_ids

    def delayed_resolve(request_id, current_plan, identifiers):
        entered.set()
        assert release.wait(2)
        return original_resolve(request_id, current_plan, identifiers)

    service._resolve_plan_selection_ids = delayed_resolve
    responses: list[object] = []
    errors: list[Exception] = []

    def mutate() -> None:
        try:
            responses.append(
                service.mutate_selection(
                    "request",
                    0,
                    deselect=(str(copied.op_id),),
                    command_id="racing-gesture",
                )
            )
        except Exception as error:
            errors.append(error)

    worker = Thread(target=mutate)
    worker.start()
    assert entered.wait(1)
    runtime.artifact = _artifact(plan_value)
    release.set()
    worker.join(2)

    assert not worker.is_alive()
    assert errors == []
    response = responses[0]
    assert response.disposition == "conflict"
    assert response.preview.revision == 2
    assert response.preview.user_deselected == ()


def test_br_g_13_review_projection_is_bound_to_the_selected_plan_artifact() -> None:
    copied = operation(OperationKind.COPY, source=file_stat())
    runtime = _PlanRuntime(_artifact(plan((copied,))))
    service = _service(runtime)
    service.mutate_selection(
        "request",
        0,
        deselect=(str(copied.op_id),),
    )

    original_get_plan_review = runtime.get_plan_review

    def replan_before_projection(request_id: str, **kwargs):
        runtime.artifact = _artifact(plan((copied,)))
        return original_get_plan_review(request_id, **kwargs)

    runtime.get_plan_review = replan_before_projection

    with pytest.raises(ValueError, match="plan changed before review"):
        service.get_plan_review("request")


def test_br_g_11_service_executes_nonempty_noop_plan_as_all_noop(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "same.bin").write_bytes(b"same")
    copy2(source / "same.bin", target / "same.bin")
    service = NamiSyncService(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )

    def terminal(session_id: str):
        deadline = monotonic() + 3
        while monotonic() < deadline:
            record = service.get_session(session_id)
            if record.result is not None:
                return record
            sleep(0.01)
        raise AssertionError("session did not finish")

    try:
        planned = service.start_plan(str(source), str(target))
        assert terminal(planned.session_id).state == "completed"
        review = service.get_plan_review(planned.request_id)
        assert review.operations
        assert {item.kind for item in review.operations} == {"noop"}

        started = service.start_execution(planned.request_id)
        assert isinstance(started, ExecutionSession)
        completed = terminal(started.session_id)

        assert completed.result is not None
        assert completed.result.headline == "all-noop"
        assert completed.result.items
    finally:
        service.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths")
def test_service_plan_entry_accepts_deep_roots_and_retains_logical_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source-root" / ("s" * 90) / ("t" * 90)
    target = tmp_path / "target-root" / ("u" * 90) / ("v" * 90)
    assert len(str(source)) > 260
    assert len(str(target)) > 260
    os.makedirs(to_extended_length_path(str(source)))
    os.makedirs(to_extended_length_path(str(target)))
    with open(
        to_extended_length_path(str(source / "payload.bin")), "wb"
    ) as stream:
        stream.write(b"service entry long path")
    converted: list[str] = []
    real_convert = sync_workflow_module.to_extended_length_path

    def recording_convert(path: str) -> str:
        native = real_convert(path)
        converted.append(native)
        return native

    monkeypatch.setattr(
        sync_workflow_module,
        "to_extended_length_path",
        recording_convert,
    )

    service = NamiSyncService(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    try:
        planned = service.start_plan(str(source), str(target))
        deadline = monotonic() + 3
        while monotonic() < deadline:
            record = service.get_session(planned.session_id)
            if record.result is not None:
                break
            sleep(0.01)
        else:
            raise AssertionError("plan session did not finish")

        assert record.state == "completed"
        artifact = service._runtime.get_plan(planned.request_id)
        assert artifact is not None
        assert artifact.plan.source_root.path == str(source)
        assert artifact.plan.target_root.path == str(target)
        assert not artifact.plan.source_root.path.startswith("\\\\?\\")
        assert not artifact.plan.target_root.path.startswith("\\\\?\\")
        assert to_extended_length_path(str(source)) in converted
        assert to_extended_length_path(str(target)) in converted
    finally:
        service.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths")
def test_service_missing_deep_root_error_does_not_expose_native_prefix(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path / "missing-source" / ("s" * 90) / ("t" * 90)
    )
    target = tmp_path / "target-root" / ("u" * 90) / ("v" * 90)
    assert len(str(source)) > 260
    assert len(str(target)) > 260
    os.makedirs(to_extended_length_path(str(target)))
    service = NamiSyncService(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    try:
        with pytest.raises(SyncPathInputError) as captured:
            service.start_plan(str(source), str(target))
    finally:
        service.close()

    detail = str(captured.value)
    assert "missing-source" in detail
    assert "\\\\?\\" not in detail


def test_br_g_11_service_refuses_an_all_skipped_selection_before_admission() -> None:
    copied = operation(OperationKind.COPY, source=file_stat())
    dispatcher = _Dispatcher()
    service = _service(
        _PlanRuntime(_artifact(plan((copied,)))),
        dispatcher,
    )
    service.mutate_selection(
        "request",
        0,
        deselect=(str(copied.op_id),),
    )

    with pytest.raises(ValueError, match="Nothing is selected"):
        service.start_execution("request", expected_revision=1)
    assert dispatcher.submissions == []


def test_br_g_14_revision_conflict_noop_and_digest_cycle_are_distinct() -> None:
    copied = operation(OperationKind.COPY, source=file_stat())
    service = _service(_PlanRuntime(_artifact(plan((copied,)))))
    original = service.preview_selection("request")

    first = service.mutate_selection(
        "request",
        0,
        deselect=(str(copied.op_id),),
    )
    stale = service.mutate_selection(
        "request",
        0,
        reselect=(str(copied.op_id),),
    )
    accepted_noop = service.mutate_selection(
        "request",
        1,
        deselect=(str(copied.op_id),),
    )
    restored = service.mutate_selection(
        "request",
        2,
        reselect=(str(copied.op_id),),
    )

    assert (first.disposition, first.revision) == ("applied", 1)
    assert (stale.disposition, stale.revision) == ("conflict", 1)
    assert accepted_noop.revision == 2
    assert accepted_noop.preview.selection_digest == (
        first.preview.selection_digest
    )
    assert restored.revision == 3
    assert restored.preview.selection_digest == original.selection_digest


def test_br_g_15_admission_failure_unfreezes_selection() -> None:
    noop = operation(
        OperationKind.NOOP,
        reason=OperationReason.METADATA_MATCH,
    )
    runtime = _PlanRuntime(_artifact(plan((noop,))))

    class FailingDispatcher(_Dispatcher):
        def submit(self, kind: str, request: object) -> str:
            raise RuntimeError("admission failed")

    failed_service = _service(runtime, FailingDispatcher())
    with pytest.raises(RuntimeError, match="admission failed"):
        failed_service.start_execution("request", expected_revision=0)
    assert failed_service.preview_selection("request").state == "reviewing"


def test_br_g_21_commitment_states_are_named_and_always_resolve() -> None:
    noop = operation(
        OperationKind.NOOP,
        reason=OperationReason.METADATA_MATCH,
    )
    entered = Event()
    release = Event()

    class BlockingDispatcher(_Dispatcher):
        def submit(self, kind: str, request: object) -> str:
            self.submissions.append((kind, request))
            entered.set()
            assert release.wait(2)
            return "only-session"

    dispatcher = BlockingDispatcher()
    service = _service(_PlanRuntime(_artifact(plan((noop,)))), dispatcher)
    returned: list[object] = []
    thread = Thread(
        target=lambda: returned.append(
            service.start_execution("request", expected_revision=0)
        )
    )
    thread.start()
    assert entered.wait(1)

    duplicate = service.start_execution("request", expected_revision=0)
    late_mutation = service.mutate_selection("request", 0)
    release.set()
    thread.join(2)

    assert isinstance(duplicate, ExecutionAdmissionView)
    assert duplicate.disposition == "in-flight"
    assert late_mutation.disposition == "in-flight"
    assert len(dispatcher.submissions) == 1
    assert isinstance(returned[0], ExecutionSession)
    frozen = service.mutate_selection("request", 0)
    assert frozen.disposition == "frozen"


def test_br_g_16_retry_receipts_apply_mutations_and_multirow_changes_once() -> None:
    copied = operation(OperationKind.COPY, source=file_stat())
    runtime = _PlanRuntime(_artifact(plan((copied,))))
    service = _service(runtime)

    first = service.mutate_selection(
        "request",
        0,
        deselect=(str(copied.op_id),),
        command_id="selection-gesture",
    )
    replay = service.mutate_selection(
        "request",
        0,
        deselect=(str(copied.op_id),),
        command_id="selection-gesture",
    )

    assert (first.disposition, replay.disposition) == ("applied", "noop")
    assert replay.revision == 1

    rows = (_inventory_row("row-a", "a.bin"), _inventory_row("row-b", "b.bin"))
    seen: set[str] = set()

    class VisibilityRuntime:
        def list_inventory(self, location_id: int):
            assert location_id == 7
            return rows

        def acknowledge_inventory(
            self,
            command_id: str,
            location_id: int,
            row_id: str,
            *,
            changed_at: datetime,
        ) -> RecordDisposition:
            assert location_id == 7
            assert changed_at == NOW
            if command_id in seen:
                return RecordDisposition.NOOP
            seen.add(command_id)
            return RecordDisposition.APPLIED

    visibility_service = _service(VisibilityRuntime())
    applied = visibility_service.acknowledge_inventory(
        "rows-gesture",
        7,
        ("row-b", "row-a", "row-a"),
        changed_at=NOW,
    )
    noops = visibility_service.acknowledge_inventory(
        "rows-gesture",
        7,
        ("row-a", "row-b"),
        changed_at=NOW,
    )
    assert [item.disposition for item in applied] == ["applied", "applied"]
    assert [item.disposition for item in noops] == ["noop", "noop"]
    assert len(seen) == 2

    dispatcher = _Dispatcher()
    session_service = _service(SimpleNamespace(), dispatcher)
    admitted = session_service.start_inventory(
        root_path="F:\\library",
        command_id="refresh-gesture",
    )
    repeated = session_service.start_inventory(
        root_path="F:\\library",
        command_id="refresh-gesture",
    )
    assert admitted == repeated
    assert len(dispatcher.submissions) == 1
    session_service.close_session(admitted.session_id)
    assert "refresh-gesture" not in session_service._session_receipts


def test_br_g_16_concurrent_session_retry_admits_exactly_one_session() -> None:
    entered = Event()
    second_submission = Event()
    release = Event()
    submission_lock = Lock()

    class BlockingDispatcher(_Dispatcher):
        def submit(self, kind: str, request: object) -> str:
            with submission_lock:
                self.submissions.append((kind, request))
                if len(self.submissions) == 1:
                    entered.set()
                else:
                    second_submission.set()
            assert release.wait(2)
            return f"session-{len(self.submissions)}"

    dispatcher = BlockingDispatcher()
    service = _service(SimpleNamespace(), dispatcher)
    returned: list[object] = []
    errors: list[Exception] = []

    def submit() -> None:
        try:
            returned.append(
                service.start_inventory(
                    root_path="F:\\library",
                    command_id="double-click",
                )
            )
        except Exception as error:
            errors.append(error)

    first = Thread(target=submit)
    second = Thread(target=submit)
    first.start()
    assert entered.wait(1)
    second.start()
    assert not second_submission.wait(0.1)
    release.set()
    first.join(2)
    second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert len(dispatcher.submissions) == 1
    assert len(returned) == 2
    assert returned[0] == returned[1]


def test_br_g_16_execution_command_id_is_single_flight_across_plans() -> None:
    entered = Event()
    second_submission = Event()
    release = Event()
    submission_lock = Lock()

    class BlockingDispatcher(_Dispatcher):
        def submit(self, kind: str, request: object) -> str:
            with submission_lock:
                self.submissions.append((kind, request))
                if len(self.submissions) == 1:
                    entered.set()
                else:
                    second_submission.set()
            assert release.wait(2)
            return f"session-{len(self.submissions)}"

    runtime = _PlanRuntime(
        _artifact(plan((operation(OperationKind.NOOP),)))
    )
    dispatcher = BlockingDispatcher()
    service = _service(runtime, dispatcher)
    returned: list[object] = []
    errors: list[Exception] = []

    def submit(request_id: str) -> None:
        try:
            returned.append(
                service.start_execution(
                    request_id,
                    command_id="execution-double-click",
                )
            )
        except Exception as error:
            errors.append(error)

    first = Thread(target=submit, args=("request-a",))
    second = Thread(target=submit, args=("request-b",))
    first.start()
    assert entered.wait(1)
    second.start()
    assert not second_submission.wait(0.1)
    release.set()
    first.join(2)
    second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(dispatcher.submissions) == 1
    assert len(returned) == 1
    assert len(errors) == 1
    assert "different command" in str(errors[0])


def test_br_g_16_id_retry_replays_before_mutable_inventory_resolution() -> None:
    rows = [_inventory_row("row-a", "a.bin")]

    class Runtime:
        def list_inventory(self, location_id: int):
            assert location_id == 7
            return tuple(rows)

    dispatcher = _Dispatcher()
    service = _service(Runtime(), dispatcher)
    first = service.start_inventory(
        location_id=7,
        selected_ids=("row-a",),
        command_id="selected-refresh",
    )
    rows.clear()
    replay = service.start_inventory(
        location_id=7,
        selected_ids=("row-a",),
        command_id="selected-refresh",
    )

    assert replay == first
    assert len(dispatcher.submissions) == 1


def test_br_g_16_plan_retry_replays_before_paths_are_revalidated(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()

    class Runtime:
        def create_plan_request(
            self,
            request_id: str,
            source_path: str,
            target_path: str,
            *,
            deletion_policy: str | None,
        ):
            return SimpleNamespace(
                request_id=request_id,
                source_path=source_path,
                target_path=target_path,
                deletion_policy=deletion_policy,
            )

    dispatcher = _Dispatcher()
    service = _service(Runtime(), dispatcher)
    first = service.start_plan(
        str(source),
        str(target),
        command_id="plan-retry",
    )
    source.rmdir()

    replay = service.start_plan(
        str(source),
        str(target),
        command_id="plan-retry",
    )

    assert replay == first
    assert len(dispatcher.submissions) == 1


def test_br_g_16_shutdown_does_not_repopulate_a_late_session_receipt() -> None:
    entered = Event()
    release = Event()

    class Dispatcher(_Dispatcher):
        def submit(self, kind: str, request: object) -> str:
            self.submissions.append((kind, request))
            entered.set()
            assert release.wait(2)
            return "late-session"

        def shutdown(self, timeout: float):
            return SimpleNamespace(
                complete=True,
                unfinished=(),
                custody_released=True,
            )

    runtime = SimpleNamespace(close=lambda: None)
    dispatcher = Dispatcher()
    service = _service(runtime, dispatcher)
    service._observer = SimpleNamespace(close=lambda: None)
    errors: list[Exception] = []

    def submit() -> None:
        try:
            service.start_inventory(
                root_path="F:\\library",
                command_id="late-refresh",
            )
        except Exception as error:
            errors.append(error)

    worker = Thread(target=submit)
    worker.start()
    assert entered.wait(1)
    service.close()
    release.set()
    worker.join(2)

    assert not worker.is_alive()
    assert errors == []
    assert service._session_receipts == {}
    assert service._receipt_ids_by_session == {}


def test_br_g_16_close_and_retry_do_not_replay_a_closed_session() -> None:
    close_entered = Event()
    close_release = Event()

    class RetainingDispatcher(_Dispatcher):
        def __init__(self) -> None:
            super().__init__()
            self.sessions: set[str] = set()

        def submit(self, kind: str, request: object) -> str:
            session_id = super().submit(kind, request)
            self.sessions.add(session_id)
            return session_id

        def get(self, session_id: str):
            if session_id not in self.sessions:
                raise SessionNotFound(session_id)
            return SimpleNamespace(session_id=session_id)

        def close(self, session_id: str) -> None:
            if session_id not in self.sessions:
                raise SessionNotFound(session_id)
            self.sessions.remove(session_id)
            close_entered.set()
            assert close_release.wait(2)
            super().close(session_id)

    dispatcher = RetainingDispatcher()
    service = _service(SimpleNamespace(), dispatcher)
    first = service.start_inventory(
        root_path="F:\\library",
        command_id="refresh-retry",
    )
    closed: list[bool] = []
    replayed: list[object] = []
    closer = Thread(
        target=lambda: (
            service.close_session(first.session_id),
            closed.append(True),
        )
    )
    retry = Thread(
        target=lambda: replayed.append(
            service.start_inventory(
                root_path="F:\\library",
                command_id="refresh-retry",
            )
        )
    )

    closer.start()
    assert close_entered.wait(1)
    retry.start()
    assert not replayed
    close_release.set()
    closer.join(2)
    retry.join(2)

    assert not closer.is_alive()
    assert not retry.is_alive()
    assert closed == [True]
    assert replayed[0] != first
    assert replayed[0].session_id in dispatcher.sessions
    assert len(dispatcher.submissions) == 2


def test_br_g_16_close_before_receipt_publication_drops_late_receipt() -> None:
    remember_entered = Event()
    remember_release = Event()

    class RetainingDispatcher(_Dispatcher):
        def __init__(self) -> None:
            super().__init__()
            self.sessions: set[str] = set()

        def submit(self, kind: str, request: object) -> str:
            session_id = super().submit(kind, request)
            self.sessions.add(session_id)
            return session_id

        def get(self, session_id: str):
            if session_id not in self.sessions:
                raise SessionNotFound(session_id)
            return SimpleNamespace(session_id=session_id)

        def close(self, session_id: str) -> None:
            if session_id not in self.sessions:
                raise SessionNotFound(session_id)
            self.sessions.remove(session_id)
            super().close(session_id)

    dispatcher = RetainingDispatcher()
    service = _service(SimpleNamespace(), dispatcher)
    remember = service._remember_session_receipt

    def delayed_remember(*args) -> None:
        remember_entered.set()
        assert remember_release.wait(2)
        remember(*args)

    service._remember_session_receipt = delayed_remember
    admitted: list[object] = []
    worker = Thread(
        target=lambda: admitted.append(
            service.start_inventory(
                root_path="F:\\library",
                command_id="late-receipt",
            )
        )
    )

    worker.start()
    assert remember_entered.wait(1)
    service.close_session("session-1")
    remember_release.set()
    worker.join(2)

    assert not worker.is_alive()
    assert admitted[0].session_id == "session-1"
    assert service._session_receipts == {}
    assert service._receipt_ids_by_session == {}


def test_br_g_17_omitted_revision_is_limited_to_pristine_cli_selection() -> None:
    noop = operation(
        OperationKind.NOOP,
        reason=OperationReason.METADATA_MATCH,
    )
    pristine = _service(_PlanRuntime(_artifact(plan((noop,)))))
    assert isinstance(pristine.start_execution("request"), ExecutionSession)

    copied = operation(OperationKind.COPY, source=file_stat())
    edited = _service(_PlanRuntime(_artifact(plan((copied,)))))
    edited.mutate_selection(
        "request",
        0,
        deselect=(str(copied.op_id),),
    )
    refused = edited.start_execution("request")
    assert isinstance(refused, ExecutionAdmissionView)
    assert refused.disposition == "conflict"


def test_br_g_18_typed_scan_warnings_reach_inventory_details_view() -> None:
    details = SimpleNamespace(
        request_id="refresh",
        resolution=SimpleNamespace(
            state=SimpleNamespace(value="resolved"),
            root_path="F:\\library",
            binding=SimpleNamespace(
                location_id=7,
                selected_mount="F:\\",
                explicit_ambiguity_choice=False,
            ),
            candidates=("F:\\",),
            detail=None,
        ),
        location_id=7,
        selected_paths=("private",),
        observed_count=0,
        missing_count=0,
        complete=False,
        warnings=(
            ScanWarning(
                ScanWarningCode.ROOT_UNAVAILABLE,
                "private",
                "access denied",
            ),
        ),
    )
    service = _service(
        SimpleNamespace(get_inventory_details=lambda _request_id: details)
    )

    view = service.get_inventory_details("refresh")

    assert not view.complete
    assert [
        (warning.code, warning.path, warning.detail)
        for warning in view.warnings
    ] == [("root_unavailable", "private", "access denied")]


def test_br_g_20_risk_uses_effective_updates_and_excludes_move_update() -> None:
    update = operation(
        OperationKind.UPDATE,
        source=file_stat(),
        target=file_stat(identity_index=2),
        intended=file_stat(),
    )
    move_update = operation(
        OperationKind.MOVE_UPDATE,
        source_path="new.bin",
        target_path="new.bin",
        prior_target_path="old.bin",
        source=file_stat(identity_index=3),
        target=file_stat(identity_index=4),
        intended=file_stat(identity_index=3),
        reason=OperationReason.IDENTITY_RENAME_CHANGED,
    )
    plan_value = replace(
        plan((update, move_update)),
        trash_on_update=False,
    )
    admission_service = _service(_PlanRuntime(_artifact(plan_value)))
    with pytest.raises(TypeError, match="must be a bool"):
        admission_service.start_execution(
            "request",
            expected_revision=0,
            destructive_acknowledged="false",
        )
    required = admission_service.start_execution(
        "request",
        expected_revision=0,
    )
    admitted = admission_service.start_execution(
        "request",
        expected_revision=0,
        destructive_acknowledged=True,
    )

    assert isinstance(required, ExecutionAdmissionView)
    assert required.disposition == "confirmation-required"
    assert isinstance(admitted, ExecutionSession)

    service = _service(_PlanRuntime(_artifact(plan_value)))

    before = service.preview_selection("request")
    after = service.mutate_selection(
        "request",
        0,
        deselect=(str(update.op_id),),
    ).preview

    assert before.requires_destructive_confirmation
    assert before.irreversible_update_count == 1
    assert not after.requires_destructive_confirmation
    assert after.irreversible_update_count == 0


def test_br_g_24_folder_mutation_uses_full_subtree_not_collapsed_rows() -> None:
    folder = operation(
        OperationKind.MKDIR,
        source_path="Folder",
        target_path="Folder",
        reason=OperationReason.REQUIRED_DIRECTORY,
    )
    first = operation(
        OperationKind.COPY,
        source_path=r"Folder\A\one.bin",
        target_path=r"Folder\A\one.bin",
        source=file_stat(identity_index=1),
    )
    second = operation(
        OperationKind.COPY,
        source_path=r"Folder\B\two.bin",
        target_path=r"Folder\B\two.bin",
        source=file_stat(identity_index=2),
    )
    plan_value = plan((folder, first, second))
    service = _service(_PlanRuntime(_artifact(plan_value)))
    tree = service._plan_tree("request", plan_value)
    folder_id = tree.node_id_for_path_key("FOLDER")

    changed = service.mutate_selection(
        "request",
        0,
        deselect=(folder_id,),
    ).preview

    assert changed.selected_operation_ids == ()
    assert set(changed.user_deselected) == {
        str(folder.op_id),
        str(first.op_id),
        str(second.op_id),
    }
    assert tree.node_for_id(folder_id).subtree_member_count == 3


def test_br_g_24_folder_mutation_skips_safety_disabled_descendants() -> None:
    folder = operation(
        OperationKind.MKDIR,
        source_path="Folder",
        target_path="Folder",
        reason=OperationReason.REQUIRED_DIRECTORY,
    )
    selectable = operation(
        OperationKind.COPY,
        source_path=r"Folder\selectable.bin",
        target_path=r"Folder\selectable.bin",
        source=file_stat(identity_index=1),
    )
    blocked = replace(
        operation(
            OperationKind.COPY,
            source_path=r"Folder\blocked.bin",
            target_path=r"Folder\blocked.bin",
            source=file_stat(identity_index=2),
        ),
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    plan_value = plan((folder, selectable, blocked))
    service = _service(_PlanRuntime(_artifact(plan_value)))
    tree = service._plan_tree("request", plan_value)

    changed = service.mutate_selection(
        "request",
        0,
        deselect=(tree.node_id_for_path_key("FOLDER"),),
    ).preview

    assert set(changed.user_deselected) == {
        str(folder.op_id),
        str(selectable.op_id),
    }
    blocked_view = next(
        item
        for item in changed.operations
        if item.operation_id == str(blocked.op_id)
    )
    assert not blocked_view.selected
    assert blocked_view.reason == "unsupported"


def test_br_g_1_and_29_opaque_location_ids_union_freeze_and_refuse_foreign() -> None:
    rows = (
        _inventory_row("folder-row", "Folder", kind=EntryKind.DIRECTORY),
        _inventory_row("child-row", r"Folder\child.bin"),
        _inventory_row("outside-row", "outside.bin"),
        _inventory_row(
            "hostile-row",
            r"100%_]\item.bin",
        ),
    )

    visibility_calls: list[tuple[str, str]] = []

    class Runtime:
        def list_inventory(self, location_id: int, selected_paths=()):
            assert location_id == 7
            return rows

        def list_unacknowledged_missing(self, location_id: int):
            return (rows[2],)

        def list_stale_inventory(
            self,
            location_id: int,
            verified_before: datetime,
        ):
            return (rows[3],)

        def acknowledge_inventory(
            self,
            command_id: str,
            location_id: int,
            row_id: str,
            *,
            changed_at: datetime,
        ) -> RecordDisposition:
            visibility_calls.append(("acknowledge", row_id))
            return RecordDisposition.APPLIED

        def restore_inventory(
            self,
            command_id: str,
            location_id: int,
            row_id: str,
            *,
            changed_at: datetime,
        ) -> RecordDisposition:
            visibility_calls.append(("restore", row_id))
            return RecordDisposition.APPLIED

    dispatcher = _Dispatcher()
    service = _service(Runtime(), dispatcher)
    tree = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="7",
        members=(
            NodeTreeMember(
                row.row_id,
                row.rel_path,
                row.rel_path_key,
                row.entry_kind is EntryKind.DIRECTORY,
            )
            for row in rows
        ),
    )
    folder_id = tree.node_id_for_path_key("FOLDER")
    hostile_id = tree.node_id_for_path_key(r"100%_]\ITEM.BIN")

    service.start_inventory(
        location_id=7,
        selected_ids=(folder_id, "outside-row"),
    )
    service.start_baseline(location_id=7, selected_ids=(folder_id,))
    service.start_verify(
        location_id=7,
        selected_ids=(folder_id, hostile_id),
    )
    service.start_rebaseline(location_id=7, selected_ids=(folder_id,))

    refresh = dispatcher.submissions[0][1]
    assert refresh.subtree_roots == ("Folder",)
    assert refresh.selected_paths == ("outside.bin",)
    for _, request in dispatcher.submissions[1:]:
        assert set(request.selected_paths) >= {
            "Folder",
            r"Folder\child.bin",
        }
    assert service.list_unacknowledged_missing(7)[0].row_id == "outside-row"
    assert service.list_stale_inventory(7, NOW)[0].row_id == "hostile-row"
    assert service.acknowledge_inventory(
        "ack-row",
        7,
        ("outside-row",),
        changed_at=NOW,
    )[0].disposition == "applied"
    assert service.restore_inventory(
        "restore-row",
        7,
        ("outside-row",),
        changed_at=NOW,
    )[0].disposition == "applied"
    assert visibility_calls == [
        ("acknowledge", "outside-row"),
        ("restore", "outside-row"),
    ]

    foreign_tree = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="8",
        members=(
            NodeTreeMember(
                "foreign-row",
                "Folder",
                "FOLDER",
                True,
            ),
        ),
    )
    with pytest.raises(ValueError, match="does not belong to location"):
        service.start_verify(
            location_id=7,
            selected_ids=(foreign_tree.root_node_id,),
        )
    with pytest.raises(ValueError, match="require selected ids"):
        service.start_inventory(location_id=7, selected_ids=())


def test_br_g_29_folder_verify_continues_past_one_unreadable_frozen_subject(
    tmp_path: Path,
) -> None:
    from namisync.core.evidence import RecordingStatus
    from namisync.core.integrity import (
        IntegrityMode,
        IntegrityOutcome,
        IntegrityResult,
        IntegrityRunResult,
        InventoryState,
    )
    from namisync.core.models import (
        ScanResult,
        UnsupportedReason,
        UnsupportedRecord,
        VolumeEvidence,
    )
    from namisync.interfaces.service import SessionObserver, _dispatcher
    from test_inventory_runtime import (
        PROFILE,
        VOLUME_ID,
        _Resolver,
        _Scanner,
        _file,
        _runtime,
        _wait_for,
    )

    mount = tmp_path / "mount"
    (mount / "managed" / "Folder").mkdir(parents=True)
    readable = _file(r"Folder\readable.bin", 1)
    private = _file(r"Folder\private.bin", 2)

    class PartialScanner(_Scanner):
        def __call__(
            self,
            root,
            ignores,
            context,
            scope,
            *,
            trusted_anchor=None,
        ):
            if not self.calls:
                return super().__call__(
                    root,
                    ignores,
                    context,
                    scope,
                    trusted_anchor=trusted_anchor,
                )
            self.calls.append(scope)
            return ScanResult(
                root,
                VOLUME_ID,
                VolumeEvidence("Runtime", str(mount)),
                PROFILE,
                (readable,),
                (),
                (
                    UnsupportedRecord(
                        private.rel_path,
                        private.rel_path_key,
                        UnsupportedReason.ACCESS_DENIED,
                    ),
                ),
                (
                    ScanWarning(
                        ScanWarningCode.ACCESS_DENIED,
                        private.rel_path,
                        "denied",
                    ),
                ),
                scope,
                False,
            )

    scanner = PartialScanner(mount, (readable, private))
    runner_items: list[tuple[str, str]] = []

    def verify_runner(selection, context, recorder):
        del recorder
        runner_items.extend(
            (item.display_path, item.expected_state.value)
            for item in selection.items
        )
        outcomes = tuple(
            IntegrityOutcome(
                item_id=item.item_id,
                row_id=item.row_id,
                location_id=item.location_id,
                path=item.display_path,
                phase=IntegrityMode.VERIFY.value,
                result=(
                    IntegrityResult.UNSUPPORTED
                    if item.expected_state is InventoryState.UNSUPPORTED
                    else IntegrityResult.VERIFIED
                ),
            )
            for item in selection.items
        )
        for outcome in outcomes:
            context.run.emit(outcome)
        return IntegrityRunResult(
            outcomes,
            RecordingStatus.OK,
        )

    runtime, location_id = _runtime(
        tmp_path,
        _Resolver(mount),
        scanner,
        {IntegrityMode.VERIFY: verify_runner},
    )
    service = _service(runtime, _dispatcher(runtime))
    service._observer = SessionObserver(service._dispatcher)
    try:
        seeded = service.start_inventory(location_id=location_id)
        assert (
            _wait_for(
                service._dispatcher,
                seeded.session_id,
                SessionState.COMPLETED,
            ).result
            is not None
        )
        rows = service.list_inventory(location_id)
        tree = build_node_tree(
            tree_kind=NodeTreeKind.INVENTORY,
            scope_identity=str(location_id),
            members=(
                NodeTreeMember(
                    row.row_id,
                    row.path,
                    row.path_key,
                    row.entry_kind == "directory",
                )
                for row in rows
            ),
        )
        folder_id = tree.node_id_for_path_key("FOLDER")

        started = service.start_verify(
            location_id=location_id,
            selected_ids=(folder_id,),
        )
        completed = _wait_for(
            service._dispatcher,
            started.session_id,
            SessionState.COMPLETED,
        )

        assert completed.result is not None
        assert completed.result.recording is RecordingStatus.OK
        assert runner_items == [
            (r"Folder\private.bin", "unsupported"),
            (r"Folder\readable.bin", "present"),
        ]
        assert [
            (item.path, item.result)
            for item in completed.result.items
        ] == [
            (r"Folder\private.bin", "unsupported"),
            (r"Folder\readable.bin", "verified"),
        ], completed.result
        facade_result = service.get_session(started.session_id).result
        assert facade_result is not None
        assert facade_result.headline == "verification-incomplete"
    finally:
        service.close()
