from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import pytest
from xxhash import xxh3_128

import namisync.modules.executor as executor_module
from namisync.core.evidence import RecordingStatus
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityResult,
    IntegrityRunResult,
    IntegritySelection,
    ReadStrategy,
    RecordDisposition,
)
from namisync.core.models import (
    CapabilityProfile,
    FileIdentity,
    FileRecord,
    IgnoreSet,
    MetadataSnapshot,
    Root,
    ScanResult,
    ScanScope,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.recording import HostCommand, LocationCommand, VolumeCommand
from namisync.core.session import (
    OperationResult,
    ResourceId,
    RunContext,
    SessionState,
)
from namisync.db.recorder import LedgerRecorder
from namisync.dispatcher import (
    Dispatcher,
    InProcessResourceLockProvider,
    PreparedSession,
    WorkflowRegistration,
)
from namisync.interfaces.cli import _workflow_registry
from namisync.workflows.inventory import (
    IntegrityRequest,
    InventoryRequest,
    MountedVolume,
    VolumeResolutionState,
    decode_integrity_request,
)
from namisync.workflows.runtime import (
    BASELINE_KIND,
    INVENTORY_KIND,
    REBASELINE_KIND,
    VERIFY_KIND,
    LocalWorkflowRuntime,
)

from _db_fixtures import FakeClock, NOW


VOLUME_ID = VolumeId("runtime-volume", "NTFS")
PROFILE = CapabilityProfile("NTFS", 100, True, False, 32767, True, True)


def _file(path: str, index: int) -> FileRecord:
    return FileRecord(
        path,
        normalize_relative_path(path),
        7,
        11 + index,
        FileIdentity(VOLUME_ID.serial, index),
        1,
        MetadataSnapshot(0, 3),
    )


class _Resolver:
    def __init__(self, *mounts: Path) -> None:
        self.mounts = tuple(mounts)

    def mounted_volumes(
        self, volume_id: VolumeId, hints: tuple[str, ...] = ()
    ) -> tuple[MountedVolume, ...]:
        assert volume_id == VOLUME_ID
        return tuple(
            MountedVolume(
                str(mount),
                VolumeEvidence("Runtime", str(mount)),
            )
            for mount in self.mounts
        )

    def probe_root(self, root_path: str) -> None:
        next(Path(root_path).iterdir(), None)


class _Scanner:
    def __init__(self, mount: Path, records: tuple[FileRecord, ...]) -> None:
        self.mount = mount
        self.records = records
        self.calls: list[ScanScope] = []

    def __call__(
        self,
        root: Root,
        ignores: IgnoreSet,
        context: RunContext,
        scope: ScanScope | None,
    ) -> ScanResult:
        assert scope is not None
        self.calls.append(scope)
        selected = set(scope.selected_paths)
        records = (
            self.records
            if not selected
            else tuple(row for row in self.records if row.rel_path in selected)
        )
        return ScanResult(
            root,
            VOLUME_ID,
            VolumeEvidence("Runtime", str(self.mount)),
            PROFILE,
            records,
            (),
            (),
            (),
            ignores,
            scope,
            True,
        )


def _seed_location(ledger: Path, mount: Path) -> int:
    with LedgerRecorder(ledger, clock=FakeClock()) as recorder:
        host_id = recorder.ensure_host(HostCommand("host", "Host", NOW))
        assert host_id > 0
        volume_id = recorder.observe_volume(
            VolumeCommand(
                VOLUME_ID,
                VolumeEvidence("Runtime", str(mount)),
                NOW,
            )
        )
        return recorder.ensure_location(
            LocationCommand(volume_id, "managed", NOW)
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


def _wait_for(
    dispatcher: Dispatcher,
    session_id,
    state: SessionState,
    timeout: float = 2.0,
):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        record = dispatcher.get(session_id)
        if record.state is state and (
            state
            not in {
                SessionState.COMPLETED,
                SessionState.FAILED,
                SessionState.CANCELED,
                SessionState.REFUSED,
            }
            or record.result is not None
        ):
            return record
        sleep(0.005)
    raise AssertionError(f"session did not reach {state}: {dispatcher.get(session_id)}")


def _runtime(
    tmp_path: Path,
    resolver: _Resolver,
    scanner: _Scanner,
    runners,
) -> tuple[LocalWorkflowRuntime, int]:
    ledger = tmp_path / "ledger.db"
    location_id = _seed_location(ledger, scanner.mount)
    runtime = LocalWorkflowRuntime(
        ledger,
        tmp_path / "history.db",
        clock=FakeClock(),
        host_key="host",
        host_name="Host",
        mounted_volume_resolver=resolver,
        inventory_scanner=scanner,
        integrity_runners=runners,
    )
    return runtime, location_id


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
                assert [item.phase for item in record.result.items] == [
                    mode.value
                ]
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

        history = runtime.get_history("history-verify")
        assert history.activity_kind == "verify"
        assert history.subject_kind == "location"
        assert history.subject_id == str(location_id)
        assert history.source_context is None
        assert history.target_context is None
        assert [
            (item.item_type, item.phase, item.path, item.result)
            for item in history.items
        ] == [("integrity", "verify", "a.txt", "verified")]

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

        history = runtime.get_history("pause-verify")
        assert [item.path for item in history.items] == ["a.txt", "b.txt"]
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
