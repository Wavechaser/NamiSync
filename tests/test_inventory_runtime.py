from __future__ import annotations

import os
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path
from threading import Event
from time import monotonic, sleep

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
from namisync.core.events import PhaseChanged, Progress, StateChanged, Terminal
from namisync.core.execution import TaskRecordingIssueReason
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityReason,
    IntegrityRecordCommand,
    IntegrityResult,
    IntegrityRunResult,
    IntegritySelection,
    InventoryState,
    ReadStrategy,
    RecordDisposition,
)
from namisync.core.models import VolumeId
from namisync.core.session import (
    Disposition,
    OperationResult,
    PauseRequested,
    ResourceId,
    RunContext,
    SessionState,
)
from namisync.db.claims import (
    DatabaseInUse,
    DatabaseMaintenanceActive,
    acquire_database_claim,
    hold_maintenance_claims,
)
from namisync.db.recorder import LedgerRecorder
from namisync.db.repositories import (
    LedgerRepository,
    LocationSnapshot,
    RecentLocationSnapshot,
    RecentPairSnapshot,
    RecentSyncActivitySnapshot,
)
from namisync.db.schema import initialize_history
from namisync.dispatcher import (
    Dispatcher,
    InMemorySessionStore,
    InProcessResourceLockProvider,
    PreparedSession,
    SessionAdmissionRefused,
    WorkflowRegistration,
)
from namisync.interfaces.service import _workflow_registry
from namisync.workflows.inventory import (
    IntegrityRequest,
    IntegrityWorkflowRequest,
    InventoryRequest,
    LocationBinding,
    LocationCandidate,
    LocationCandidateResult,
    LocationCandidateState,
    VolumeResolutionState,
)
from namisync.workflows.database_maintenance import (
    backup_database_pair,
    check_database_pair,
    restore_database_from_backup,
)
from namisync.workflows.models import PlanRequest
from namisync.workflows.runtime import (
    BASELINE_KIND,
    EXECUTION_KIND,
    INVENTORY_KIND,
    REBASELINE_KIND,
    VERIFY_KIND,
    LocalWorkflowRuntime,
)
from namisync.workflows.views import operation_result_view

from _child_process import Child
from _db_fixtures import FakeClock, NOW, replace_ledger_instance, stored_ledger_instance
from _inventory_fixtures import (
    PROFILE,
    VOLUME_ID,
    _Resolver,
    _Scanner,
    _file,
    _runtime,
    _wait_for,
)
from _maintenance_children import RESTORE as _RESTORE


def _outcome(
    item,
    mode: IntegrityMode,
    *,
    recording: RecordingStatus = RecordingStatus.OK,
) -> IntegrityOutcome:
    return IntegrityOutcome(
        item_id=item.item_id,
        row_id=item.row_id,
        location_id=item.location_id,
        path=item.display_path,
        phase=mode.value,
        result=IntegrityResult.VERIFIED,
        recording=recording,
    )


def test_plan_location_inputs_are_bounded_before_either_native_admission() -> None:
    calls: list[LocationCandidate] = []

    class Runtime:
        def admit_location_candidate(self, candidate: LocationCandidate):
            calls.append(candidate)
            raise AssertionError("overlong pair reached native admission")

    with pytest.raises(ValueError, match="UTF-16 path bound"):
        LocalWorkflowRuntime.admit_plan_locations(
            Runtime(),  # type: ignore[arg-type]
            "C:\\source",
            "D:\\" + "x" * 32_768,
        )

    assert calls == []


def test_runtime_current_inventory_detail_reads_exact_location_owned_row(tmp_path: Path, monkeypatch):
    runtime, location_id, scanner = _mixed_integrity_runtime(tmp_path, {})
    row = runtime.list_inventory(location_id)[0]
    def no_full_inventory(*args, **kwargs):
        pytest.fail("exact detail performed a full location read")
    monkeypatch.setattr(LedgerRepository, "get_inventory", no_full_inventory)
    try:
        current = runtime.read_inventory_row(location_id, row.row_id)
        assert current == row
        assert runtime.read_inventory_row(location_id + 1, row.row_id) is None
        assert runtime.read_inventory_row(location_id, "999999") is None
    finally:
        runtime.close()


def test_plan_pair_overlap_is_checked_after_both_candidate_admissions() -> None:
    calls: list[LocationCandidate] = []
    volume = VolumeId("pair-volume", "NTFS")

    def admitted(candidate: LocationCandidate, root: str) -> LocationCandidateResult:
        binding = LocationBinding(volume, "", root, (root,), False)
        return LocationCandidateResult(
            candidate,
            LocationCandidateState.RESOLVED,
            binding=binding,
            root_path=root,
            candidates=(root,),
        )

    class Runtime:
        def admit_location_candidate(
            self, candidate: LocationCandidate
        ) -> LocationCandidateResult:
            calls.append(candidate)
            root = "C:\\root" if len(calls) == 1 else "C:\\root\\child"
            return admitted(candidate, root)

    with pytest.raises(ValueError, match="distinct, non-nested"):
        LocalWorkflowRuntime.admit_plan_locations(
            Runtime(),  # type: ignore[arg-type]
            "C:\\root",
            "C:\\root\\child",
        )

    assert [candidate.path for candidate in calls] == [
        "C:\\root",
        "C:\\root\\child",
    ]


def test_runtime_projects_remembered_locations_from_one_repository_read() -> None:
    source = LocationSnapshot(
        7,
        VolumeId("source-volume", "NTFS"),
        "source",
        "C:\\",
    )
    target = LocationSnapshot(
        8,
        VolumeId("target-volume", "NTFS"),
        "target",
        "D:\\",
    )
    snapshot = RecentSyncActivitySnapshot(
        (RecentLocationSnapshot(source, NOW),),
        (RecentLocationSnapshot(target, NOW),),
        (RecentPairSnapshot(9, source, target, NOW),),
    )

    class Repository:
        def __init__(self) -> None:
            self.calls = 0

        def get_recent_sync_activity(self):
            self.calls += 1
            return snapshot

    repository = Repository()

    class Runtime:
        @contextmanager
        def _ledger_read(self):
            yield repository

    recent = LocalWorkflowRuntime.remembered_locations(
        Runtime(),  # type: ignore[arg-type]
    )

    assert repository.calls == 1
    assert recent.sources[0].location_id == source.location_id
    assert recent.targets[0].location_id == target.location_id
    assert recent.pairs[0].mapping_id == 9
    assert recent.pairs[0].source == recent.sources[0]
    assert recent.pairs[0].target == recent.targets[0]


def _refresh_inventory(
    runtime: LocalWorkflowRuntime,
    location_id: int,
    request_id: str,
) -> None:
    prepared = runtime.prepare_inventory(
        InventoryRequest(request_id, location_id=location_id)
    )
    result = runtime.open_inventory(prepared.checkpoint).run(
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
    request = IntegrityRequest(
        request_id, mode, location_id=location_id,
        selected_paths=("a.txt", "b.txt") if mode is IntegrityMode.REBASELINE else (),
        accept_current_evidence=mode is IntegrityMode.REBASELINE,
    )
    if mode is IntegrityMode.BASELINE:
        prepared = runtime.prepare_baseline(request)
        invocation = runtime.open_baseline(prepared.checkpoint)
    elif mode is IntegrityMode.REBASELINE:
        prepared = runtime.prepare_rebaseline(request)
        invocation = runtime.open_rebaseline(prepared.checkpoint)
    else:
        prepared = runtime.prepare_verify(request)
        invocation = runtime.open_verify(prepared.checkpoint)
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
        assert registrations["sync-plan"].settle_canceled is None
        assert registrations[INVENTORY_KIND].settle_canceled is None
        assert (
            registrations[BASELINE_KIND].settle_canceled
            == runtime.settle_canceled_baseline
        )
        assert (
            registrations[VERIFY_KIND].settle_canceled
            == runtime.settle_canceled_verify
        )
        assert (
            registrations[REBASELINE_KIND].settle_canceled
            == runtime.settle_canceled_rebaseline
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
                        selected_paths=("a.txt",),
                        accept_current_evidence=True,
                    ),
                )
                record = _wait_for(
                    dispatcher, session_id, SessionState.COMPLETED
                )
                assert record.result is not None
                assert [item.phase for item in record.result.items] == [mode.value]
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
        baseline_result = runtime.open_baseline(baseline_request.checkpoint).run(
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
        verify_result = runtime.open_verify(verify_request.checkpoint).run(context)
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


@pytest.mark.skipif(os.name != "nt", reason="native verifier is Windows-only")
@pytest.mark.parametrize(
    ("mode", "present_result", "seed_evidence"),
    (
        (IntegrityMode.BASELINE, IntegrityResult.BASELINED, False),
        (IntegrityMode.VERIFY, IntegrityResult.VERIFIED, True),
        (IntegrityMode.REBASELINE, IntegrityResult.BASELINED, True),
    ),
)
def test_native_runtime_integrity_preserves_missing_observation_without_current_stat(
    tmp_path: Path,
    mode: IntegrityMode,
    present_result: IntegrityResult,
    seed_evidence: bool,
) -> None:
    root = tmp_path / "managed"
    root.mkdir()
    missing_path = root / "missing.bin"
    missing_path.write_bytes(b"retained historical observation")
    (root / "present.bin").write_bytes(b"present sibling")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
        clock=FakeClock(),
        host_key="host",
        host_name="Host",
    )
    context = RunContext(lambda _event: None, lambda: None)
    try:
        inventory = runtime.prepare_inventory(
            InventoryRequest("present-inventory", root_path=str(root))
        )
        assert runtime.open_inventory(inventory.checkpoint).run(context).status is (
            SessionState.COMPLETED
        )
        location_id = runtime.get_inventory_details(
            "present-inventory"
        ).location_id
        assert location_id is not None

        if seed_evidence:
            baseline = runtime.prepare_baseline(
                IntegrityRequest(
                    "seed-evidence",
                    IntegrityMode.BASELINE,
                    location_id=location_id,
                )
            )
            baseline_result = runtime.open_baseline(baseline.checkpoint).run(context)
            assert baseline_result.status is SessionState.COMPLETED
            assert {item.result for item in baseline_result.items} == {
                IntegrityResult.BASELINED
            }

        before = {
            row.rel_path: row for row in runtime.list_inventory(location_id)
        }
        assert before["missing.bin"].observed is not None
        assert (before["missing.bin"].attestation is not None) is seed_evidence
        historical_observation = before["missing.bin"].observed
        missing_path.unlink()

        selected: list[tuple[InventoryState, object, bool]] = []
        runners = runtime._integrity_deps.runners
        assert isinstance(runners, dict)
        production_runner = runners[mode]

        def capture_selection(selection, verifier_context, recorder):
            selected.extend(
                (
                    item.expected_state,
                    item.expected_stat,
                    item.baseline is not None,
                )
                for item in selection.items
            )
            return production_runner(selection, verifier_context, recorder)

        runners[mode] = capture_selection
        request = IntegrityRequest(
            f"present-to-missing-{mode.value}",
            mode,
            location_id=location_id,
            selected_paths=("missing.bin", "present.bin"),
            accept_current_evidence=mode is IntegrityMode.REBASELINE,
        )
        if mode is IntegrityMode.BASELINE:
            prepared = runtime.prepare_baseline(request)
            invocation = runtime.open_baseline(prepared.checkpoint)
        elif mode is IntegrityMode.VERIFY:
            prepared = runtime.prepare_verify(request)
            invocation = runtime.open_verify(prepared.checkpoint)
        else:
            prepared = runtime.prepare_rebaseline(request)
            invocation = runtime.open_rebaseline(prepared.checkpoint)

        result = invocation.run(context)

        assert result.status is SessionState.COMPLETED
        assert {
            item.path: (item.result, item.reason) for item in result.items
        } == {
            "missing.bin": (
                IntegrityResult.MISSING,
                IntegrityReason.INVENTORY_MISSING,
            ),
            "present.bin": (present_result, None),
        }
        assert selected == [
            (InventoryState.MISSING, None, seed_evidence),
            (InventoryState.PRESENT, before["present.bin"].observed, seed_evidence),
        ]
        after = {
            row.rel_path: row for row in runtime.list_inventory(location_id)
        }
        assert after["missing.bin"].observed == historical_observation
        assert after["missing.bin"].presence.value == "missing"
        assert (after["missing.bin"].attestation is not None) is seed_evidence
        assert after["present.bin"].presence.value == "present"
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
        result = runtime.open_baseline(prepared.checkpoint).run(context)

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
            ("a.txt", "b.txt"),
            id="rebaseline-all-evidence-states",
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
        del recorder
        selections.append(tuple(item.display_path for item in selection.items))
        return _settle_all(selection, context, mode)

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
            context.run.emit(outcome)
            selection.mark_completed(item.item_id, 0)
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
        del recorder
        selections.append(
            (
                tuple(item.item_id for item in selection.items),
                dict(selection.completed_bytes),
                selection.processed_bytes,
            )
        )
        return _settle_all(selection, context, IntegrityMode.BASELINE)

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
            binding=prepared.checkpoint.binding,
            mode=IntegrityMode.BASELINE,
            selection_item_ids=frozen,
            completed_bytes=((frozen[0], 7),),
            processed_bytes=7,
            bytes_total_high_water=14,
            refresh_generation=1,
        )

        result = runtime.open_baseline(request).run(
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
        del recorder
        selections.append(tuple(item.item_id for item in selection.items))
        return _settle_all(selection, context, IntegrityMode.VERIFY)

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
        binding = prepared.checkpoint.binding
        full_reads: list[int] = []
        row_id_reads: list[tuple[int, tuple[str, ...]]] = []

        class TrackingRepository(LedgerRepository):
            def get_inventory(self, selected_location_id, path_keys=None):
                if path_keys is None:
                    full_reads.append(selected_location_id)
                return super().get_inventory(selected_location_id, path_keys)

            def get_integrity_candidates(
                self,
                selected_location_id,
                mode,
                **scopes,
            ):
                requested = tuple(scopes.get("saved_row_ids", ()))
                if requested:
                    row_id_reads.append((selected_location_id, requested))
                return super().get_integrity_candidates(
                    selected_location_id,
                    mode,
                    **scopes,
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

        result = runtime.open_verify(request).run(
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
            runtime.open_inventory(prepared.checkpoint).run(context).status
            is SessionState.COMPLETED
        )
        stale = runtime.list_stale_inventory(location_id, NOW)
        assert [row.rel_path for row in stale] == ["a.txt"]

        scanner.records = ()
        prepared = runtime.prepare_inventory(
            InventoryRequest("missing", location_id=location_id)
        )
        runtime.open_inventory(prepared.checkpoint).run(context)
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


def test_database_maintenance_refuses_inventory_writers_without_partial_state(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    runtime, location_id = _runtime(tmp_path, _Resolver(mount), scanner, {})
    store = InMemorySessionStore()
    attached = []

    def attach(session_id, stream):
        attached.append(session_id)
        stream.close()
        return lambda: None

    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        store=store,
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        with hold_maintenance_claims(runtime.ledger_path, runtime.history_path):
            for kind, request in (
                (INVENTORY_KIND, InventoryRequest("under-maintenance", location_id=location_id)),
                (VERIFY_KIND, IntegrityRequest(
                    "verify-under-maintenance", IntegrityMode.VERIFY, location_id=location_id,
                )),
            ):
                # The ledger's claim, taken first, is refused at admission:
                # nothing is stored, published, attached or queued.
                with pytest.raises(SessionAdmissionRefused, match="refused, not queued"):
                    dispatcher.submit(kind, request, attach=attach)
            assert dispatcher.list() == ()
            assert store.snapshot() == ()
            assert attached == []
            with pytest.raises(DatabaseMaintenanceActive):
                runtime.acknowledge_inventory("ack", location_id, "1")

        assert scanner.calls == []
        assert runtime.list_inventory(location_id) == ()
        with pytest.raises(KeyError):
            runtime.get_history_summary("under-maintenance")

        session_id = dispatcher.submit(
            INVENTORY_KIND,
            InventoryRequest("after-maintenance", location_id=location_id),
        )
        record = _wait_for(dispatcher, session_id, SessionState.COMPLETED)
        assert record.result is not None
        assert record.result.audit is RecordingStatus.OK
        # The audit pump closes the observer just after the terminal result.
        deadline = monotonic() + 5.0
        while True:
            try:
                with hold_maintenance_claims(runtime.ledger_path, runtime.history_path):
                    break
            except DatabaseInUse:
                assert monotonic() < deadline, "a finished run kept its claim"
                sleep(0.01)
    finally:
        assert dispatcher.shutdown().complete
        runtime.close()


def _maintenance_naming_another_history(runtime: LocalWorkflowRuntime, other_history: Path) -> tuple[str, str | None]:
    # Maintenance that shares the run's ledger but names another History, so
    # only the ledger's own claim can refuse it.
    try:
        with hold_maintenance_claims(runtime.ledger_path, other_history):
            held = "held"
    except DatabaseInUse:
        held = "in-use"
    return held, check_database_pair(runtime.ledger_path, other_history).contract.reason


def _stamped_instance(history: Path, run_token: str) -> str:
    connection = sqlite3.connect(history.as_uri() + "?mode=ro", uri=True)
    try:
        return connection.execute(
            "SELECT ledger_instance_id FROM history_runs WHERE run_token = ?", (run_token,),
        ).fetchone()[0]
    finally:
        connection.close()


@pytest.mark.parametrize("kind", (INVENTORY_KIND, VERIFY_KIND, EXECUTION_KIND))
def test_an_admitted_run_holds_the_ledger_it_stamped_until_its_observer_closes(
    tmp_path: Path, kind: str,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    runtime, location_id = _runtime(tmp_path, _Resolver(mount), scanner, {})
    other_history = initialize_history(tmp_path / "other-history.db")
    attempts: list[tuple[str, str | None]] = []

    def admit_then_attempt_maintenance(record):
        observer = runtime.audit_observer(record)
        # Stamp confirmed, ledger recorder not yet opened.
        if observer is not None:
            attempts.append(_maintenance_naming_another_history(runtime, other_history))
        return observer

    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=admit_then_attempt_maintenance,
    )
    try:
        if kind == EXECUTION_KIND:
            source, target = tmp_path / "source", tmp_path / "target"
            source.mkdir()
            target.mkdir()
            (source / "a.bin").write_bytes(b"a")
            plan_request = PlanRequest("7" * 32, str(source), str(target))
            runtime.open_plan(runtime.prepare_plan(plan_request).checkpoint).run(
                RunContext(lambda body: None, lambda: None)
            )
            token = "8" * 32
            request = runtime.commit_plan(plan_request.request_id, run_id=token, committed_at=NOW)
        elif kind == INVENTORY_KIND:
            token = "stamped-inventory"
            request = InventoryRequest(token, location_id=location_id)
        else:
            token = "stamped-verify"
            request = IntegrityRequest(token, IntegrityMode.VERIFY, location_id=location_id)

        session_id = dispatcher.submit(kind, request)
        deadline = monotonic() + 10.0
        # Its outcome is not the point (verify has no runner configured here).
        while (record := dispatcher.get(session_id)).result is None:
            assert monotonic() < deadline, "the session did not settle"
            sleep(0.01)

        # The run's ledger shared claim refused both, so nothing replaced it.
        assert attempts == [("in-use", "database-in-use")]
        # Its recorder's own shared claim, a second handle in this process,
        # coexisted with the observer's: the run recorded normally.
        assert record.result.audit is RecordingStatus.OK
        assert record.result.recording is RecordingStatus.OK
        assert _stamped_instance(runtime.history_path, token) == stored_ledger_instance(
            runtime.ledger_path
        )
        # The audit pump closes the observer just after the terminal result,
        # releasing both claims: same-process maintenance is admitted again.
        deadline = monotonic() + 5.0
        while True:
            try:
                with hold_maintenance_claims(runtime.ledger_path, other_history):
                    break
            except DatabaseInUse:
                assert monotonic() < deadline, "a finished run kept its ledger claim"
                sleep(0.01)
        with hold_maintenance_claims(runtime.ledger_path, runtime.history_path):
            pass
    finally:
        assert dispatcher.shutdown().complete
        runtime.close()


def test_the_stamp_is_read_under_the_ledger_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    runtime, location_id = _runtime(tmp_path, _Resolver(mount), scanner, {})
    read = runtime._ledger_instance_id
    replacements: list[str] = []

    def replace_then_read() -> str:
        # A restore landing at the stamp read must already be refused.
        try:
            replace_ledger_instance(runtime.ledger_path)
            replacements.append("replaced")
        except DatabaseInUse:
            replacements.append("refused")
        return read()

    monkeypatch.setattr(runtime, "_ledger_instance_id", replace_then_read)
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        session_id = dispatcher.submit(
            INVENTORY_KIND, InventoryRequest("stamped-under-claim", location_id=location_id),
        )
        monkeypatch.undo()
        record = _wait_for(dispatcher, session_id, SessionState.COMPLETED)

        assert replacements == ["refused"]
        assert record.result.audit is RecordingStatus.OK
        assert _stamped_instance(runtime.history_path, "stamped-under-claim") == (
            stored_ledger_instance(runtime.ledger_path)
        )
    finally:
        assert dispatcher.shutdown().complete
        runtime.close()


def test_a_refused_or_failed_observer_admission_keeps_no_ledger_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    runtime, location_id = _runtime(tmp_path, _Resolver(mount), scanner, {})
    released: list[bool] = []

    def open_then_probe(record):
        try:
            return runtime.audit_observer(record)
        finally:
            # Before any session work or recorder: the ledger must be free.
            try:
                acquire_database_claim(runtime.ledger_path, exclusive=True).release()
                released.append(True)
            except DatabaseInUse:
                released.append(False)

    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=open_then_probe,
    )
    try:
        # History's claim refused after the ledger's was taken.
        with acquire_database_claim(runtime.history_path, exclusive=True):
            with pytest.raises(SessionAdmissionRefused, match="refused, not queued"):
                dispatcher.submit(
                    INVENTORY_KIND, InventoryRequest("history-held", location_id=location_id),
                )
        # A failure between the ledger claim and the observer degrades audit.
        def unreadable() -> str:
            raise OSError("ledger unreadable")

        monkeypatch.setattr(runtime, "_ledger_instance_id", unreadable)
        session_id = dispatcher.submit(
            INVENTORY_KIND, InventoryRequest("degraded", location_id=location_id),
        )
        monkeypatch.undo()
        record = _wait_for(dispatcher, session_id, SessionState.COMPLETED)

        assert released == [True, True]
        assert record.result.audit is RecordingStatus.DEGRADED
        with pytest.raises(KeyError):
            runtime.get_history_summary("history-held")
    finally:
        assert dispatcher.shutdown().complete
        runtime.close()


def test_maintenance_on_the_ledger_alone_refuses_admission_with_history_untouched(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    runtime, location_id = _runtime(tmp_path, _Resolver(mount), scanner, {})
    store = InMemorySessionStore()
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        store=store,
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        with acquire_database_claim(runtime.ledger_path, exclusive=True):
            for kind, request in (
                (INVENTORY_KIND, InventoryRequest("ledger-claimed", location_id=location_id)),
                (VERIFY_KIND, IntegrityRequest(
                    "verify-ledger-claimed", IntegrityMode.VERIFY, location_id=location_id,
                )),
            ):
                with pytest.raises(SessionAdmissionRefused, match="refused, not queued") as caught:
                    dispatcher.submit(kind, request)
                assert str(runtime.ledger_path) in str(caught.value)
            # History's claim was never taken, or was released.
            acquire_database_claim(runtime.history_path, exclusive=True).release()
        assert dispatcher.list() == ()
        assert store.snapshot() == ()
        assert scanner.calls == []
        with pytest.raises(KeyError):
            runtime.get_history_summary("ledger-claimed")
    finally:
        assert dispatcher.shutdown().complete
        runtime.close()


@pytest.mark.parametrize("restore_names_the_runs_ledger", (True, False))
def test_a_history_restore_begun_after_preparation_refuses_admission_before_history_is_opened(
    tmp_path: Path, restore_names_the_runs_ledger: bool,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    runtime, location_id = _runtime(tmp_path, _Resolver(mount), scanner, {})
    backups = backup_database_pair(runtime.ledger_path, runtime.history_path, clock=FakeClock())
    backup = next(item.path for item in backups.backups if item.role == "history")
    ledger = runtime.ledger_path
    if not restore_names_the_runs_ledger:
        # The same ledger at another path: only History's claim is shared.
        ledger = tmp_path / "elsewhere" / "ledger.db"
        ledger.parent.mkdir()
        with closing(sqlite3.connect(runtime.ledger_path)) as source:
            with closing(sqlite3.connect(ledger)) as copy:
                source.backup(copy)
    children: list[Child] = []

    def restore_then_admit(record):
        # Prepared and not yet admitted: a restore stops inside its copy
        # transaction, so a cold History open would fail without the claim.
        child = Child(
            _RESTORE, str(ledger), str(runtime.history_path), "history", str(backup),
            "mid-copy", "0",
        )
        children.append(child)
        assert child.read() == "ready"
        assert child.read() == "stopped"
        return runtime.audit_observer(record)

    store = InMemorySessionStore()
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        store=store,
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=restore_then_admit,
    )
    try:
        with pytest.raises(SessionAdmissionRefused, match="refused, not queued") as caught:
            dispatcher.submit(INVENTORY_KIND, InventoryRequest("restoring", location_id=location_id))
        held = ledger if restore_names_the_runs_ledger else runtime.history_path
        assert str(held) in str(caught.value)
        assert dispatcher.list() == ()
        assert store.snapshot() == ()
        assert scanner.calls == []
    finally:
        for child in children:
            child.kill()
        assert dispatcher.shutdown().complete
        runtime.close()


def test_ledger_recorder_refuses_a_run_admitted_without_its_observer_under_a_ledger_only_claim(
    tmp_path: Path,
) -> None:
    # With audit degraded the run holds no claim until its recorder opens, so
    # the recorder is what refuses it.
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1),))
    runtime, location_id = _runtime(tmp_path, _Resolver(mount), scanner, {})
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
    )
    request = InventoryRequest("ledger-claimed", location_id=location_id)
    try:
        with acquire_database_claim(runtime.ledger_path, exclusive=True):
            session_id = dispatcher.submit(INVENTORY_KIND, request)
            record = _wait_for(dispatcher, session_id, SessionState.FAILED)

        assert record.result is not None and record.result.error is not None
        assert record.result.error.type_name == "DatabaseMaintenanceActive"
        assert "refused, not queued" in record.result.error.message
        assert scanner.calls == []
        assert runtime.list_inventory(location_id) == ()
    finally:
        assert dispatcher.shutdown().complete
        runtime.close()


def test_audit_observer_refuses_only_for_maintenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    runtime, _location_id = _runtime(tmp_path, _Resolver(mount), _Scanner(mount, ()), {})
    try:
        for error, expected in (
            (DatabaseMaintenanceActive("maintenance text", runtime.history_path), SessionAdmissionRefused),
            # Every other failure reaches the dispatcher unchanged and degrades audit.
            (DatabaseInUse("in use", runtime.history_path), DatabaseInUse),
            (OSError("history unavailable"), OSError),
        ):
            def fail(record, error=error):
                raise error

            monkeypatch.setattr(runtime, "_open_audit_observer", fail)
            with pytest.raises(expected) as caught:
                runtime.audit_observer(object())
            assert type(caught.value) is expected
            if expected is SessionAdmissionRefused:
                assert str(caught.value) == "maintenance text"
                assert caught.value.__cause__ is None
                assert caught.value.__context__ is None
    finally:
        runtime.close()


def test_integrity_snapshot_orders_completed_rows_by_frozen_selection(
    tmp_path: Path,
) -> None:
    def pause_after_completing(selection, context, recorder):
        del recorder
        for item in selection.items:
            size = 0 if item.expected_stat is None else item.expected_stat.size
            selection.note_bytes_processed(size)
            context.run.emit(_outcome(item, IntegrityMode.VERIFY))
            selection.mark_completed(item.item_id, size)
        raise PauseRequested("capture ordered continuation")

    runtime, location_id, _scanner = _mixed_integrity_runtime(
        tmp_path,
        {IntegrityMode.VERIFY: pause_after_completing},
    )
    try:
        rows = runtime.list_inventory(location_id)
        frozen = tuple(
            f"{row.location_id}:{row.row_id}" for row in reversed(rows)
        )
        prepared = runtime.prepare_verify(
            IntegrityRequest(
                "ordered-completion-binding",
                IntegrityMode.VERIFY,
                location_id=location_id,
            )
        )
        request = IntegrityWorkflowRequest(
            request_id="ordered-completion",
            binding=prepared.checkpoint.binding,
            mode=IntegrityMode.VERIFY,
            selection_item_ids=frozen,
            refresh_generation=1,
        )
        session = runtime.open_verify(request)

        with pytest.raises(PauseRequested, match="ordered continuation"):
            session.run(RunContext(lambda _event: None, lambda: None))
        continuation = session.snapshot()

        assert continuation.selection_item_ids == frozen
        assert tuple(item_id for item_id, _ in continuation.completed_bytes) == frozen
    finally:
        runtime.close()


@pytest.mark.parametrize(
    "mode, kind, expected_path",
    [
        (IntegrityMode.BASELINE, BASELINE_KIND, "b.txt"),
        (IntegrityMode.REBASELINE, REBASELINE_KIND, "a.txt"),
    ],
)
def test_paused_baseline_and_rebaseline_resume_without_repeating_or_losing_items(
    tmp_path: Path,
    mode: IntegrityMode,
    kind: str,
    expected_path: str,
) -> None:
    started = Event()
    release = Event()
    calls = 0

    def runner(selection, context, recorder):
        nonlocal calls
        del recorder
        calls += 1
        if calls == 1:
            item = selection.pending[0]
            size = 0 if item.expected_stat is None else item.expected_stat.size
            selection.note_bytes_processed(size)
            selection.advance_bytes_total_high_water(
                sum(
                    0
                    if selected.expected_stat is None
                    else selected.expected_stat.size
                    for selected in selection.items
                )
            )
            outcome = IntegrityOutcome(
                item_id=item.item_id,
                row_id=item.row_id,
                location_id=item.location_id,
                path=item.display_path,
                phase=mode.value,
                result=IntegrityResult.BASELINED,
            )
            context.run.emit(outcome)
            selection.mark_completed(item.item_id, size)
            started.set()
            assert release.wait(2)
            context.run.checkpoint()
            raise AssertionError("pause checkpoint must stop the runner")
        return IntegrityRunResult((), RecordingStatus.OK)

    runtime, location_id, scanner = _mixed_integrity_runtime(
        tmp_path,
        {mode: runner},
    )
    scanner_calls_before = len(scanner.calls)
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=runtime.audit_observer,
    )
    request_id = f"pause-resume-{mode.value}"
    try:
        session_id = dispatcher.submit(
            kind,
            IntegrityRequest(
                request_id, mode, location_id=location_id,
                selected_paths=(expected_path,), accept_current_evidence=True,
            ),
        )
        assert started.wait(2)
        assert dispatcher.pause(session_id).accepted
        release.set()
        _wait_for(dispatcher, session_id, SessionState.PAUSED)

        assert dispatcher.resume(session_id).accepted
        completed = _wait_for(dispatcher, session_id, SessionState.COMPLETED)

        assert completed.result is not None
        assert completed.result.status is SessionState.COMPLETED
        assert completed.result.canceled is False
        assert [
            (item.path, item.phase, item.result)
            for item in completed.result.items
        ] == [
            (expected_path, mode.value, IntegrityResult.BASELINED)
        ]
        assert calls == 2
        assert len(scanner.calls) == scanner_calls_before + 2

        history = runtime.get_history_summary(request_id)
        history_items = runtime.get_history_items(request_id)
        assert history.activity_kind == mode.value
        assert history.current_state == SessionState.COMPLETED.value
        assert history.item_count == 1
        assert [
            (retained.item.path, retained.item.phase, retained.item.result)
            for retained in history_items.items
        ] == [(expected_path, mode.value, IntegrityResult.BASELINED.value)]
    finally:
        release.set()
        assert dispatcher.shutdown().complete
        runtime.close()


@pytest.mark.parametrize(
    "mode, kind",
    [
        (IntegrityMode.BASELINE, BASELINE_KIND),
        (IntegrityMode.VERIFY, VERIFY_KIND),
        (IntegrityMode.REBASELINE, REBASELINE_KIND),
    ],
)
def test_paused_integrity_cancel_uses_exact_continuation_without_reopening(
    tmp_path: Path,
    mode: IntegrityMode,
    kind: str,
) -> None:
    started = Event()
    release = Event()
    calls = 0

    def runner(selection, context, recorder):
        nonlocal calls
        del recorder
        calls += 1
        item = selection.pending[0]
        size = 0 if item.expected_stat is None else item.expected_stat.size
        selection.note_bytes_processed(size)
        bytes_total = max(
            selection.processed_bytes,
            sum(
                0
                if selected.expected_stat is None
                else selected.expected_stat.size
                for selected in selection.items
            ),
        )
        selection.advance_bytes_total_high_water(bytes_total)
        context.run.emit(
            Progress(
                phase=mode.value,
                items_done=selection.completed_count,
                items_total=len(selection.items),
                bytes_done=selection.processed_bytes,
                bytes_total=selection.bytes_total_high_water,
                current_path=item.display_path,
            )
        )
        outcome = _outcome(
            item,
            mode,
            recording=RecordingStatus.DEGRADED,
        )
        context.run.emit(outcome)
        selection.mark_completed(item.item_id, size)
        started.set()
        assert release.wait(2)
        context.run.checkpoint()
        raise AssertionError("pause checkpoint must stop the runner")

    runtime, location_id, scanner = _mixed_integrity_runtime(
        tmp_path,
        {mode: runner},
    )
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=runtime.audit_observer,
    )
    stream = None
    try:
        session_id = dispatcher.submit(
            kind,
            IntegrityRequest(
                f"pause-cancel-{mode.value}",
                mode,
                accept_current_evidence=True,
                location_id=location_id,
                selected_paths=("a.txt", "b.txt"),
            ),
        )
        stream = dispatcher.subscribe(session_id)
        assert started.wait(2)
        assert dispatcher.pause(session_id).accepted
        release.set()
        paused = _wait_for(dispatcher, session_id, SessionState.PAUSED)
        continuation = paused.checkpoint
        assert type(continuation) is IntegrityWorkflowRequest
        assert continuation.mode is mode
        assert continuation.refresh_generation == 1
        assert continuation.selection_item_ids
        assert len(continuation.completed_bytes) == 1
        assert continuation.processed_bytes == 7
        assert continuation.bytes_total_high_water == (
            7 * len(continuation.selection_item_ids)
        )
        assert continuation.recording is RecordingStatus.DEGRADED
        scanner_calls_at_pause = len(scanner.calls)

        assert dispatcher.cancel(session_id).accepted
        canceled = _wait_for(dispatcher, session_id, SessionState.CANCELED)

        assert canceled.result is not None
        assert canceled.result.canceled is True
        assert (
            canceled.result.bytes_done,
            canceled.result.bytes_total,
        ) == (
            continuation.processed_bytes,
            continuation.bytes_total_high_water,
        )
        assert canceled.result.recording is RecordingStatus.DEGRADED
        assert [(item.path, item.phase) for item in canceled.result.items] == [
            (
                "b.txt" if mode is IntegrityMode.BASELINE else "a.txt",
                mode.value,
            )
        ]
        assert calls == 1
        assert len(scanner.calls) == scanner_calls_at_pause

        bodies: list[object] = []
        while True:
            body = stream.next(2).body
            bodies.append(body)
            if isinstance(body, Terminal):
                break
        mode_change = next(
            index
            for index, body in enumerate(bodies)
            if body == PhaseChanged(mode.value)
        )
        progress_indexes = [
            index
            for index, body in enumerate(bodies)
            if isinstance(body, Progress)
        ]
        assert progress_indexes
        assert mode_change < progress_indexes[0]
        assert all(
            body.phase == mode.value
            for body in bodies
            if isinstance(body, Progress)
        )
        assert all(
            body.phase == mode.value
            for body in bodies
            if isinstance(body, IntegrityOutcome)
        )
    finally:
        release.set()
        if stream is not None:
            stream.close()
        assert dispatcher.shutdown().complete
        runtime.close()


def test_pause_during_integrity_context_creation_retains_admitted_total(
    tmp_path: Path,
) -> None:
    context_started = Event()
    release_context = Event()
    runner_calls = 0

    def runner(*_args) -> IntegrityRunResult:
        nonlocal runner_calls
        runner_calls += 1
        raise AssertionError("runner started after paused context creation")

    runtime, location_id, scanner = _mixed_integrity_runtime(
        tmp_path,
        {IntegrityMode.VERIFY: runner},
    )

    def pause_in_context(context: RunContext):
        context_started.set()
        assert release_context.wait(2)
        context.checkpoint()
        raise AssertionError("pause checkpoint did not stop context creation")

    runtime._integrity_deps = replace(
        runtime._integrity_deps,
        verifier_context=pause_in_context,
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
                "pause-context-admission",
                IntegrityMode.VERIFY,
                location_id=location_id,
                selected_paths=("a.txt", "b.txt"),
            ),
        )
        assert context_started.wait(2)
        assert dispatcher.pause(session_id).accepted
        release_context.set()
        paused = _wait_for(dispatcher, session_id, SessionState.PAUSED)
        continuation = paused.checkpoint
        assert type(continuation) is IntegrityWorkflowRequest

        assert len(continuation.selection_item_ids) == 2
        assert continuation.completed_bytes == ()
        assert continuation.processed_bytes == 0
        assert continuation.bytes_total_high_water == 14
        scanner_calls_at_pause = len(scanner.calls)

        assert dispatcher.cancel(session_id).accepted
        canceled = _wait_for(dispatcher, session_id, SessionState.CANCELED)

        assert canceled.result is not None
        assert canceled.result.canceled is True
        assert (canceled.result.bytes_done, canceled.result.bytes_total) == (
            0,
            14,
        )
        assert runner_calls == 0
        assert len(scanner.calls) == scanner_calls_at_pause
    finally:
        release_context.set()
        assert dispatcher.shutdown().complete
        runtime.close()


def test_paused_integrity_snapshot_persists_recorder_close_degradation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = Event()
    release = Event()

    def runner(selection, context, recorder):
        del recorder
        selection.note_bytes_processed(3)
        selection.advance_bytes_total_high_water(
            max(
                selection.processed_bytes,
                sum(
                    0
                    if item.expected_stat is None
                    else item.expected_stat.size
                    for item in selection.items
                ),
            )
        )
        started.set()
        assert release.wait(2)
        context.run.checkpoint()
        raise AssertionError("pause checkpoint must stop the runner")

    runtime, location_id, _scanner = _mixed_integrity_runtime(
        tmp_path,
        {IntegrityMode.VERIFY: runner},
    )
    original_close = inventory_workflow.LedgerRecorder.close

    def failing_close(recorder) -> None:
        original_close(recorder)
        raise RuntimeError("x" * 1_100)

    monkeypatch.setattr(
        inventory_workflow.LedgerRecorder,
        "close",
        failing_close,
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
                "pause-close-degraded",
                IntegrityMode.VERIFY,
                location_id=location_id,
            ),
        )
        assert started.wait(2)
        assert dispatcher.pause(session_id).accepted
        release.set()
        paused = _wait_for(dispatcher, session_id, SessionState.PAUSED)
        continuation = paused.checkpoint
        assert type(continuation) is IntegrityWorkflowRequest

        assert continuation.processed_bytes == 3
        assert continuation.bytes_total_high_water == 14
        assert continuation.recording is RecordingStatus.DEGRADED
        assert len(continuation.recording_issues) == 1
        assert continuation.recording_issues[0].reason is (
            TaskRecordingIssueReason.RECORDING_CLOSE_FAILED
        )
        assert continuation.recording_issues[0].detail is None
        assert continuation.omitted_detail_count == 1

        assert dispatcher.cancel(session_id).accepted
        canceled = _wait_for(dispatcher, session_id, SessionState.CANCELED)
        assert canceled.result is not None
        assert canceled.result.recording is RecordingStatus.DEGRADED
        assert canceled.result.recording_issues == continuation.recording_issues
        assert canceled.result.omitted_detail_count == 1
        assert (canceled.result.bytes_done, canceled.result.bytes_total) == (
            3,
            14,
        )
    finally:
        release.set()
        assert dispatcher.shutdown().complete
        runtime.close()


def test_preselection_pause_persists_recorder_close_degradation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    started = Event()
    release = Event()

    class PauseBeforeSelectionScanner(_Scanner):
        def __call__(
            self,
            root,
            ignores,
            context,
            scope,
            *,
            trusted_anchor=None,
            population_admission=None,
        ):
            assert population_admission is not None
            started.set()
            assert release.wait(2)
            context.checkpoint()
            raise AssertionError("pause checkpoint must stop the refresh")

    scanner = PauseBeforeSelectionScanner(
        mount,
        (_file("a.txt", 1),),
    )
    runtime, location_id = _runtime(
        tmp_path,
        _Resolver(mount),
        scanner,
        {
            IntegrityMode.VERIFY: lambda *_args: pytest.fail(
                "verifier must not start before refresh selection"
            )
        },
    )
    original_close = inventory_workflow.LedgerRecorder.close

    def failing_close(recorder) -> None:
        original_close(recorder)
        raise RuntimeError("preselection pause close failed")

    monkeypatch.setattr(
        inventory_workflow.LedgerRecorder,
        "close",
        failing_close,
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
                "preselection-pause-close",
                IntegrityMode.VERIFY,
                location_id=location_id,
            ),
        )
        assert started.wait(2)
        assert dispatcher.pause(session_id).accepted
        release.set()
        paused = _wait_for(dispatcher, session_id, SessionState.PAUSED)
        continuation = paused.checkpoint
        assert type(continuation) is IntegrityWorkflowRequest

        assert continuation.selection_item_ids == ()
        assert continuation.processed_bytes == 0
        assert continuation.bytes_total_high_water == 0
        assert continuation.recording is RecordingStatus.DEGRADED
        assert continuation.recording_issues[0].reason is (
            TaskRecordingIssueReason.RECORDING_CLOSE_FAILED
        )
        assert continuation.recording_issues[0].detail == (
            "RuntimeError: preselection pause close failed"
        )
        assert continuation.omitted_detail_count == 0

        assert dispatcher.cancel(session_id).accepted
        canceled = _wait_for(dispatcher, session_id, SessionState.CANCELED)
        assert canceled.result is not None
        assert canceled.result.recording is RecordingStatus.DEGRADED
        assert (canceled.result.bytes_done, canceled.result.bytes_total) == (0, 0)
    finally:
        release.set()
        assert dispatcher.shutdown().complete
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
            selection.advance_bytes_total_high_water(
                max(
                    selection.processed_bytes,
                    sum(
                        0
                        if selected.expected_stat is None
                        else selected.expected_stat.size
                        for selected in selection.items
                    ),
                )
            )
            context.run.emit(
                Progress(
                    phase=IntegrityMode.VERIFY.value,
                    items_done=selection.completed_count,
                    items_total=len(selection.items),
                    bytes_done=selection.processed_bytes,
                    bytes_total=max(
                        selection.processed_bytes,
                        sum(
                            0
                            if selected.expected_stat is None
                            else selected.expected_stat.size
                            for selected in selection.items
                        ),
                    ),
                    current_path=item.display_path,
                )
            )
            outcome = _outcome(
                item,
                IntegrityMode.VERIFY,
                recording=(
                    RecordingStatus.DEGRADED
                    if calls == 1
                    else RecordingStatus.OK
                ),
            )
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
    paused_stream = None
    try:
        session_id = dispatcher.submit(
            VERIFY_KIND,
            IntegrityRequest(
                "pause-verify",
                IntegrityMode.VERIFY,
                location_id=location_id,
            ),
        )
        paused_stream = dispatcher.subscribe(session_id)
        assert first_completed.wait(2)
        assert dispatcher.pause(session_id).accepted
        allow_checkpoint.set()
        paused = _wait_for(dispatcher, session_id, SessionState.PAUSED)
        continuation = paused.checkpoint
        assert type(continuation) is IntegrityWorkflowRequest
        assert continuation.refresh_generation == 1
        assert len(continuation.selection_item_ids) == 2
        assert len(continuation.completed_bytes) == 1
        assert continuation.processed_bytes == 7
        assert continuation.bytes_total_high_water == 14
        assert continuation.recording is RecordingStatus.DEGRADED
        while True:
            envelope = paused_stream.next(2)
            if envelope.body == StateChanged(SessionState.PAUSED):
                break
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
        assert completed.result.recording is RecordingStatus.DEGRADED
        assert [
            (item.path, item.phase) for item in completed.result.items
        ] == [("a.txt", "verify"), ("b.txt", "verify")]
        resumed_bodies: list[object] = []
        while True:
            body = paused_stream.next(2).body
            resumed_bodies.append(body)
            if isinstance(body, Terminal):
                break
        resumed_phase = next(
            index
            for index, body in enumerate(resumed_bodies)
            if body == PhaseChanged(IntegrityMode.VERIFY.value)
        )
        resumed_progress = [
            index
            for index, body in enumerate(resumed_bodies)
            if isinstance(body, Progress)
        ]
        assert resumed_progress
        assert resumed_phase < resumed_progress[0]
        assert all(
            body.phase == IntegrityMode.VERIFY.value
            for body in resumed_bodies
            if isinstance(body, (Progress, IntegrityOutcome))
        )
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
        if paused_stream is not None:
            paused_stream.close()
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

    def snapshot(self) -> str:
        return "blocker"


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
            "blocker", frozenset({resource})
        ),
        open=lambda _checkpoint: _BlockingInvocation(started, release),
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


_INTEGRITY_KINDS = {
    IntegrityMode.BASELINE: BASELINE_KIND,
    IntegrityMode.VERIFY: VERIFY_KIND,
    IntegrityMode.REBASELINE: REBASELINE_KIND,
}
_RECORDED_DIGEST = b"\x02" * 16


def _ledger_dump(ledger: Path) -> list[str]:
    with closing(sqlite3.connect(ledger)) as connection:
        return list(connection.iterdump())


def _ledger_digest(ledger: Path, path: str) -> bytes | None:
    with closing(sqlite3.connect(ledger)) as connection:
        (digest,) = connection.execute(
            "SELECT content_digest FROM inventory WHERE rel_path = ?", (path,),
        ).fetchone()
    return None if digest is None else bytes(digest)


def _recording_then_pausing_runner(
    mode: IntegrityMode, started: Event, release: Event,
    calls: list[str], recorded: list[str],
):
    # Records and reports one item through the run's own recorder, then waits
    # at a checkpoint for the pause; a second stretch must never reach it.
    def runner(selection, context, recorder):
        calls.append(mode.value)
        if len(calls) > 1:
            return _settle_all(selection, context, mode)
        item = selection.pending[0]
        stat = item.expected_stat
        assert stat is not None
        attestation = Attestation(
            ContentEvidence(
                "xxh3_128", _RECORDED_DIGEST, stat.size,
                Provenance.READBACK_ATTESTED, NOW,
            ),
            stat,
        )
        assert recorder.record_integrity(
            IntegrityRecordCommand(
                mode, item.item_id, item.row_id, item.location_id,
                item.rel_path_key, item.scope_token, item.expected_state,
                stat, item.baseline, attestation,
                mode is IntegrityMode.VERIFY, False, item.invalidation,
            )
        ) is RecordDisposition.APPLIED
        recorded.append(item.display_path)
        selection.note_bytes_processed(stat.size)
        context.run.emit(
            IntegrityOutcome(
                item_id=item.item_id,
                row_id=item.row_id,
                location_id=item.location_id,
                path=item.display_path,
                phase=mode.value,
                result=(
                    IntegrityResult.VERIFIED
                    if mode is IntegrityMode.VERIFY and item.baseline is not None
                    else IntegrityResult.BASELINED
                ),
            )
        )
        selection.mark_completed(item.item_id, stat.size)
        started.set()
        assert release.wait(2)
        context.run.checkpoint()
        raise AssertionError("pause checkpoint must stop the runner")

    return runner


def _integrity_request(mode: IntegrityMode, request_id: str, location_id: int) -> IntegrityRequest:
    return IntegrityRequest(
        request_id, mode, location_id=location_id,
        selected_paths=("a.txt", "b.txt") if mode is IntegrityMode.REBASELINE else (),
        accept_current_evidence=mode is IntegrityMode.REBASELINE,
    )


def _ledger_backup(runtime: LocalWorkflowRuntime) -> Path:
    result = backup_database_pair(runtime.ledger_path, runtime.history_path, clock=FakeClock())
    return next(backup.path for backup in result.backups if backup.role == "ledger")


def _restore_ledger(runtime: LocalWorkflowRuntime, backup: Path, *, retry: bool = False):
    deadline = monotonic() + 5.0
    while True:
        restored = restore_database_from_backup(
            runtime.ledger_path, runtime.history_path, "ledger", backup,
            clock=FakeClock(NOW + timedelta(seconds=1)),
        )
        if restored.restore is not None or not retry:
            assert restored.restore is not None, restored.contract
            return restored.restore
        # A refused restore changes nothing; the closing observer still holds claims.
        assert restored.contract.reason == "database-in-use", restored.contract
        assert monotonic() < deadline, "the closed observer kept its claims"
        sleep(0.01)


def _assert_refused_resume(
    record, mode: IntegrityMode, *, ledger: Path, dump_before: list[str],
    scans_before: int, scanner: _Scanner, calls: list[str], recorded: list[str],
) -> None:
    result = record.result
    assert result is not None
    # The record keeps what the session reported before the pause, once: it
    # is the run's account, which the error says belongs to the replaced
    # ledger, not a claim about the current one.
    assert [(item.path, item.phase) for item in result.items] == [
        (recorded[0], mode.value)
    ]
    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert result.error is not None
    assert result.error.type_name == "IntegrityLedgerChanged", result.error
    assert result.error.message == (
        f"The ledger was replaced (restored or reset) while this {mode.value} "
        "run was paused, so it cannot resume: the results it reported before "
        "the pause belong to the replaced ledger, not the current one. Start a "
        f"new {mode.value} run against the current ledger."
    )
    # Refused under the recorder's claim, through its open-failure path.
    assert result.recording is RecordingStatus.DEGRADED
    assert [
        (issue.reason, (issue.detail or "").split(":")[0])
        for issue in result.recording_issues
    ] == [(TaskRecordingIssueReason.RECORDING_OPEN_FAILED, "IntegrityLedgerChanged")]
    view = operation_result_view(result)
    assert (view.filesystem, view.recording) == ("failed", "degraded")
    assert view.error is not None and view.error.startswith("IntegrityLedgerChanged: ")
    # Before any scan, ledger write or reuse of the saved progress.
    assert calls == [mode.value]
    assert len(scanner.calls) == scans_before
    assert _ledger_dump(ledger) == dump_before


@pytest.mark.parametrize(
    "mode, backup_at",
    [
        (IntegrityMode.BASELINE, "before-run"),
        (IntegrityMode.VERIFY, "before-run"),
        (IntegrityMode.REBASELINE, "before-run"),
        # A backup taken moments earlier, at the pause, restores the same
        # content under a new instance: still refused.
        (IntegrityMode.BASELINE, "at-pause"),
    ],
)
def test_resume_refuses_integrity_progress_after_the_ledger_is_restored(
    tmp_path: Path, mode: IntegrityMode, backup_at: str,
) -> None:
    started, release = Event(), Event()
    calls: list[str] = []
    recorded: list[str] = []
    runtime, location_id, scanner = _mixed_integrity_runtime(
        tmp_path,
        {mode: _recording_then_pausing_runner(mode, started, release, calls, recorded)},
    )
    ledger = runtime.ledger_path
    # Without a History observer, as with audit degraded at admission, the
    # paused session holds no claim, so a restore can land.
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
    )
    try:
        if backup_at == "before-run":
            backup = _ledger_backup(runtime)
        session_id = dispatcher.submit(
            _INTEGRITY_KINDS[mode], _integrity_request(mode, f"restored-{mode.value}", location_id),
        )
        assert started.wait(2)
        assert dispatcher.pause(session_id).accepted
        release.set()
        paused = _wait_for(dispatcher, session_id, SessionState.PAUSED)
        paused_instance = getattr(paused.checkpoint, "ledger_instance_id", None)
        instance_before = stored_ledger_instance(ledger)
        assert _ledger_digest(ledger, recorded[0]) == _RECORDED_DIGEST
        if backup_at == "at-pause":
            backup = _ledger_backup(runtime)

        restore = _restore_ledger(runtime, backup)
        assert restore.instance_id != instance_before
        if backup_at == "before-run":
            # The attestation the paused stretch recorded is not in the restored ledger.
            assert _ledger_digest(ledger, recorded[0]) != _RECORDED_DIGEST
        dump_before, scans_before = _ledger_dump(ledger), len(scanner.calls)
        assert dispatcher.resume(session_id).accepted
        record = _wait_for(dispatcher, session_id, SessionState.FAILED)

        _assert_refused_resume(
            record, mode, ledger=ledger, dump_before=dump_before,
            scans_before=scans_before, scanner=scanner, calls=calls, recorded=recorded,
        )
        # Captured under the paused stretch's recorder claim.
        assert paused_instance == instance_before
        # Terminal: no checkpoint remains to resume into success.
        assert record.checkpoint is None
        assert not dispatcher.resume(session_id).accepted
    finally:
        release.set()
        assert dispatcher.shutdown().complete
        runtime.close()


class _FailingAfterOutcomeObserver:
    # Delegates to the runtime's observer until an integrity outcome arrives.
    def __init__(self, observer) -> None:
        self._observer = observer

    def on_event(self, envelope):
        if isinstance(envelope.body, IntegrityOutcome):
            raise OSError("history write failed")
        return self._observer.on_event(envelope)

    def flush(self) -> None:
        self._observer.flush()

    def finalize(self, result):
        return self._observer.finalize(result)

    def close(self) -> None:
        self._observer.close()


def test_resume_refuses_integrity_progress_after_audit_failed_and_the_ledger_was_restored(
    tmp_path: Path,
) -> None:
    mode = IntegrityMode.BASELINE
    started, release = Event(), Event()
    calls: list[str] = []
    recorded: list[str] = []
    runtime, location_id, scanner = _mixed_integrity_runtime(
        tmp_path,
        {mode: _recording_then_pausing_runner(mode, started, release, calls, recorded)},
    )
    ledger = runtime.ledger_path
    backup = _ledger_backup(runtime)

    def failing_observer(record):
        observer = runtime.audit_observer(record)
        return None if observer is None else _FailingAfterOutcomeObserver(observer)

    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=FakeClock(),
        audit_observer_factory=failing_observer,
    )
    try:
        session_id = dispatcher.submit(
            _INTEGRITY_KINDS[mode], _integrity_request(mode, "audit-failed", location_id),
        )
        assert started.wait(2)
        assert dispatcher.pause(session_id).accepted
        release.set()
        _wait_for(dispatcher, session_id, SessionState.PAUSED)
        # The audit pump closed the failed observer, releasing both claims,
        # while the session lives on paused.
        _restore_ledger(runtime, backup, retry=True)
        dump_before, scans_before = _ledger_dump(ledger), len(scanner.calls)
        assert dispatcher.resume(session_id).accepted
        record = _wait_for(dispatcher, session_id, SessionState.FAILED)

        _assert_refused_resume(
            record, mode, ledger=ledger, dump_before=dump_before,
            scans_before=scans_before, scanner=scanner, calls=calls, recorded=recorded,
        )
        assert record.result.audit is RecordingStatus.DEGRADED
    finally:
        release.set()
        assert dispatcher.shutdown().complete
        runtime.close()


def test_integrity_ledger_check_precedes_the_scan_and_saved_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, location_id, scanner = _mixed_integrity_runtime(tmp_path, {})
    reached: list[str] = []
    monkeypatch.setattr(
        inventory_workflow, "_register_and_scan",
        lambda *args, **kwargs: reached.append("scan"),
    )
    monkeypatch.setattr(
        inventory_workflow, "_integrity_rows",
        lambda *args, **kwargs: reached.append("saved progress"),
    )
    try:
        rows = runtime.list_inventory(location_id)
        prepared = runtime.prepare_verify(
            IntegrityRequest("placement-binding", IntegrityMode.VERIFY, location_id=location_id)
        )
        saved = tuple(f"{row.location_id}:{row.row_id}" for row in rows)
        request = IntegrityWorkflowRequest(
            request_id="placement",
            binding=prepared.checkpoint.binding,
            mode=IntegrityMode.VERIFY,
            selection_item_ids=saved,
            completed_bytes=((saved[0], 7),),
            processed_bytes=7,
            bytes_total_high_water=14,
            refresh_generation=1,
            ledger_instance_id="0" * 32,
        )
        dump_before, scans_before = _ledger_dump(runtime.ledger_path), len(scanner.calls)
        session = runtime.open_verify(request)

        result = session.run(RunContext(lambda _event: None, lambda: None))

        assert reached == []
        assert len(scanner.calls) == scans_before
        assert _ledger_dump(runtime.ledger_path) == dump_before
        assert result.status is SessionState.FAILED
        assert result.error is not None
        assert result.error.type_name == "IntegrityLedgerChanged"
        assert result.items == ()
    finally:
        runtime.close()


def test_integrity_ledger_instance_is_read_under_the_recorder_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def pause_after_selection(selection, context, recorder):
        del selection, context, recorder
        raise PauseRequested("capture continuation")

    runtime, location_id, _scanner = _mixed_integrity_runtime(
        tmp_path, {IntegrityMode.VERIFY: pause_after_selection},
    )
    read = inventory_workflow._ledger_instance
    attempts: list[str] = []

    def replace_then_read(deps) -> str:
        # A restore landing at the read must already be refused.
        try:
            replace_ledger_instance(runtime.ledger_path)
            attempts.append("replaced")
        except DatabaseInUse:
            attempts.append("refused")
        return read(deps)

    monkeypatch.setattr(inventory_workflow, "_ledger_instance", replace_then_read)
    try:
        prepared = runtime.prepare_verify(
            IntegrityRequest("under-claim", IntegrityMode.VERIFY, location_id=location_id)
        )
        assert prepared.checkpoint.ledger_instance_id is None
        session = runtime.open_verify(prepared.checkpoint)
        with pytest.raises(PauseRequested, match="capture continuation"):
            session.run(RunContext(lambda _event: None, lambda: None))

        assert attempts == ["refused"]
        assert session.snapshot().ledger_instance_id == stored_ledger_instance(
            runtime.ledger_path
        )
    finally:
        runtime.close()
