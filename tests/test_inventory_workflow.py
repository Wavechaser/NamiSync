from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from xxhash import xxh3_128

import namisync.workflows.inventory as inventory_workflow
from namisync.core.evidence import RecordingStatus
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityRunResult,
    VerifierContext,
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
from namisync.core.pathing import (
    normalize_relative_path,
    to_extended_length_path,
)
from namisync.core.planning import FilterSet
from namisync.core.recording import InventoryCommand
from namisync.core.session import (
    Disposition,
    PauseRequested,
    RunContext,
    SessionState,
)
from namisync.db.connections import connect_ledger_reader
from namisync.db.repositories import InventoryPresence, LedgerRepository
from namisync.modules.scanner import VolumeSnapshot
from namisync.workflows.inventory import (
    IntegrityDependencies,
    IntegrityWorkflowRequest,
    InventoryDependencies,
    InventoryDetails,
    InventoryRequest,
    InventoryWorkflowRequest,
    LocationBinding,
    MountedVolume,
    NativeMountedVolumeResolver,
    VolumeResolutionRequired,
    VolumeResolutionState,
    bind_inventory_request,
    decode_integrity_request,
    decode_inventory_request,
    encode_integrity_request,
    encode_inventory_request,
    replace_mapping_filter,
    resolve_binding,
    run_integrity,
    run_inventory,
)

from _db_fixtures import FakeClock, plan, setup_recorder


VOLUME_ID = VolumeId("inventory-volume", "NTFS")
PROFILE = CapabilityProfile("NTFS", 100, True, False, 32767, True, True)
EVIDENCE = VolumeEvidence("Inventory", "M:")


class _Resolver:
    def __init__(self, *mounts: Path) -> None:
        self.mounts = tuple(mounts)
        self.probe_error: OSError | None = None

    def mounted_volumes(
        self, volume_id: VolumeId, hints: tuple[str, ...] = ()
    ) -> tuple[MountedVolume, ...]:
        assert volume_id == VOLUME_ID
        return tuple(MountedVolume(str(path), EVIDENCE) for path in self.mounts)

    def probe_root(self, root_path: str) -> None:
        if self.probe_error is not None:
            raise self.probe_error


class _Backend:
    def __init__(self, root: Path, mount: Path) -> None:
        self.root = root
        self.mount = mount

    def resolve_root(self, path: str) -> str:
        assert Path(path) == self.root
        return str(self.root)

    def volume_snapshot(self, root: str) -> VolumeSnapshot:
        assert Path(root) == self.root
        return VolumeSnapshot(
            VOLUME_ID,
            VolumeEvidence("Inventory", str(self.mount)),
            PROFILE,
        )


class _Scanner:
    def __init__(self, *, records: tuple[FileRecord, ...] = ()) -> None:
        self.records = records
        self.complete = True
        self.calls: list[tuple[Root, ScanScope]] = []
        self.before_scan = None

    def __call__(
        self,
        root: Root,
        ignores: IgnoreSet,
        context: RunContext,
        scope: ScanScope | None,
    ) -> ScanResult:
        assert scope is not None
        self.calls.append((root, scope))
        if self.before_scan is not None:
            self.before_scan()
        selected = set(scope.selected_paths)
        records = (
            self.records
            if not selected
            else tuple(row for row in self.records if row.rel_path in selected)
        )
        return ScanResult(
            root,
            VOLUME_ID,
            EVIDENCE,
            PROFILE,
            records,
            (),
            (),
            (),
            ignores,
            scope,
            self.complete,
        )


class _ProbeBackend:
    def __init__(self) -> None:
        self.scanned_paths: list[str] = []

    def scandir(self, path: str):
        self.scanned_paths.append(path)
        return nullcontext(iter(()))


def _file(path: str = "file.txt") -> FileRecord:
    return FileRecord(
        path,
        normalize_relative_path(path),
        7,
        11,
        FileIdentity(VOLUME_ID.serial, 1),
        1,
        MetadataSnapshot(0, 3),
    )


def _binding(mount: Path, relative: str = "managed") -> LocationBinding:
    return LocationBinding(
        VOLUME_ID,
        relative,
        str(mount),
        (str(mount),),
        False,
    )


def _dependencies(
    ledger_path: Path,
    scanner: _Scanner,
    resolver: _Resolver,
    details: list[InventoryDetails],
) -> InventoryDependencies:
    return InventoryDependencies(
        ledger_path=ledger_path,
        scanner=scanner,
        resolver=resolver,
        clock=FakeClock(),
        host_key="host",
        host_name="Host",
        save_details=details.append,
    )


def _context() -> RunContext:
    return RunContext(lambda _body: None, lambda: None)


def test_resolve_binding_stats_extended_path_but_reports_logical_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    observed_paths: list[str] = []

    def missing_stat(path: str, *, follow_symlinks: bool):
        observed_paths.append(path)
        assert not follow_symlinks
        raise FileNotFoundError(path)

    monkeypatch.setattr(inventory_workflow.os, "stat", missing_stat)
    resolution = resolve_binding(_binding(mount), _Resolver(mount))

    assert observed_paths == [to_extended_length_path(str(root))]
    assert resolution.state is VolumeResolutionState.ROOT_MISSING
    assert resolution.root_path == str(root)


def test_native_resolver_probe_uses_scanner_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _ProbeBackend()

    def raw_scandir(_path: str):
        raise AssertionError("raw os.scandir must not be used")

    monkeypatch.setattr(inventory_workflow.os, "scandir", raw_scandir)

    NativeMountedVolumeResolver(backend).probe_root("logical-root")  # type: ignore[arg-type]

    assert backend.scanned_paths == ["logical-root"]


def test_first_location_registers_role_free_before_scan_then_records_inventory(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    scanner = _Scanner(records=(_file(),))
    details: list[InventoryDetails] = []

    def assert_registration_precedes_scan() -> None:
        with connect_ledger_reader(ledger_path) as connection:
            assert connection.execute("SELECT count(*) FROM hosts").fetchone()[0] == 1
            assert connection.execute("SELECT count(*) FROM volumes").fetchone()[0] == 1
            assert connection.execute("SELECT count(*) FROM locations").fetchone()[0] == 1
            assert connection.execute("SELECT count(*) FROM mappings").fetchone()[0] == 0
            assert connection.execute("SELECT count(*) FROM inventory").fetchone()[0] == 0

    scanner.before_scan = assert_registration_precedes_scan
    result = run_inventory(
        bind_inventory_request(
            InventoryRequest("first", root_path=str(root)),
            ledger_path=ledger_path,
            backend=_Backend(root, mount),
            resolver=_Resolver(mount),
        ),
        _context(),
        _dependencies(ledger_path, scanner, _Resolver(mount), details),
    )

    assert result.status is SessionState.COMPLETED
    assert details[-1].resolution.state is VolumeResolutionState.RESOLVED
    assert details[-1].observed_count == 1
    with connect_ledger_reader(ledger_path) as connection:
        assert connection.execute("SELECT count(*) FROM mappings").fetchone()[0] == 0
    with LedgerRepository(ledger_path) as repository:
        rows = repository.get_inventory(details[-1].location_id or 0)
    assert tuple(row.rel_path for row in rows) == ("file.txt",)


def test_ambiguity_is_resolved_before_submission(tmp_path: Path) -> None:
    mount = tmp_path / "mount"
    clone = tmp_path / "clone"
    root = mount / "managed"
    root.mkdir(parents=True)
    clone.mkdir()
    request = InventoryRequest("ambiguous", root_path=str(root))
    resolver = _Resolver(mount, clone)

    with pytest.raises(VolumeResolutionRequired) as raised:
        bind_inventory_request(
            request,
            ledger_path=tmp_path / "ledger.db",
            backend=_Backend(root, mount),
            resolver=resolver,
        )
    assert raised.value.resolution.state is VolumeResolutionState.AMBIGUOUS

    prepared = bind_inventory_request(
        InventoryRequest(
            "chosen",
            root_path=str(root),
            selected_mount=str(mount),
        ),
        ledger_path=tmp_path / "ledger.db",
        backend=_Backend(root, mount),
        resolver=resolver,
    )
    assert prepared.binding.explicit_ambiguity_choice
    assert prepared.binding.selected_mount == str(mount)


@pytest.mark.parametrize(
    "state",
    [
        VolumeResolutionState.RESOLVED,
        VolumeResolutionState.OFFLINE,
        VolumeResolutionState.AMBIGUOUS,
        VolumeResolutionState.ROOT_MISSING,
        VolumeResolutionState.ROOT_UNAVAILABLE,
    ],
)
def test_five_volume_states_are_distinct_and_only_resolved_reconciles(
    tmp_path: Path,
    state: VolumeResolutionState,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    scanner = _Scanner(records=(_file(),))
    resolver = _Resolver(mount)
    details: list[InventoryDetails] = []
    deps = _dependencies(ledger_path, scanner, resolver, details)
    binding = _binding(mount)
    seed = run_inventory(
        bind_inventory_request(
            InventoryRequest("seed", root_path=str(root)),
            ledger_path=ledger_path,
            backend=_Backend(root, mount),
            resolver=resolver,
        ),
        _context(),
        deps,
    )
    assert seed.status is SessionState.COMPLETED
    scanner.records = ()

    if state is VolumeResolutionState.OFFLINE:
        resolver.mounts = ()
    elif state is VolumeResolutionState.AMBIGUOUS:
        clone = tmp_path / "clone"
        clone.mkdir()
        resolver.mounts = (mount, clone)
    elif state is VolumeResolutionState.ROOT_MISSING:
        root.rmdir()
    elif state is VolumeResolutionState.ROOT_UNAVAILABLE:
        resolver.probe_error = PermissionError("denied")

    result = run_inventory(
        InventoryWorkflowRequest("refresh", binding),
        _context(),
        deps,
    )

    assert details[-1].resolution.state is state
    with LedgerRepository(ledger_path) as repository:
        row = repository.get_inventory(details[0].location_id or 0)[0]
    if state is VolumeResolutionState.RESOLVED:
        assert result.status is SessionState.COMPLETED
        assert len(scanner.calls) == 2
        assert row.presence is InventoryPresence.MISSING
    else:
        assert result.status is SessionState.REFUSED
        assert len(scanner.calls) == 1
        assert row.presence is InventoryPresence.PRESENT


def test_integrity_wakeup_rechecks_clone_before_scan_or_hash(tmp_path: Path) -> None:
    mount = tmp_path / "mount"
    clone = tmp_path / "clone"
    root = mount / "managed"
    root.mkdir(parents=True)
    clone.mkdir()
    ledger_path = tmp_path / "ledger.db"
    scanner = _Scanner(records=(_file(),))
    resolver = _Resolver(mount)
    details: list[InventoryDetails] = []
    deps = _dependencies(ledger_path, scanner, resolver, details)
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=ledger_path,
        backend=_Backend(root, mount),
        resolver=resolver,
    )
    run_inventory(prepared, _context(), deps)
    runner_calls = 0

    def runner(*_args):
        nonlocal runner_calls
        runner_calls += 1
        raise AssertionError("hash runner must not start")

    resolver.mounts = (mount, clone)
    integrity_deps = IntegrityDependencies(
        ledger_path=deps.ledger_path,
        scanner=deps.scanner,
        resolver=deps.resolver,
        clock=deps.clock,
        host_key=deps.host_key,
        host_name=deps.host_name,
        save_details=deps.save_details,
        ignores=deps.ignores,
        runners={IntegrityMode.VERIFY: runner},
    )
    result = run_integrity(
        IntegrityWorkflowRequest(
            "queued-verify",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        _context(),
        integrity_deps,
    )

    assert result.status is SessionState.REFUSED
    assert details[-1].resolution.state is VolumeResolutionState.AMBIGUOUS
    assert len(scanner.calls) == 1
    assert runner_calls == 0


def test_incomplete_selected_integrity_refresh_runs_no_hash_and_is_not_unrun_refusal(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    scanner = _Scanner(records=(_file(),))
    resolver = _Resolver(mount)
    details: list[InventoryDetails] = []
    deps = _dependencies(ledger_path, scanner, resolver, details)
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=ledger_path,
        backend=_Backend(root, mount),
        resolver=resolver,
    )
    run_inventory(prepared, _context(), deps)
    scanner.complete = False
    runner_calls = 0

    def runner(*_args):
        nonlocal runner_calls
        runner_calls += 1
        raise AssertionError("incomplete selection must not hash")

    result = run_integrity(
        IntegrityWorkflowRequest(
            "selected-incomplete",
            prepared.binding,
            IntegrityMode.VERIFY,
            ("file.txt",),
        ),
        _context(),
        IntegrityDependencies(
            ledger_path=deps.ledger_path,
            scanner=deps.scanner,
            resolver=deps.resolver,
            clock=deps.clock,
            host_key=deps.host_key,
            host_name=deps.host_name,
            save_details=deps.save_details,
            runners={IntegrityMode.VERIFY: runner},
        ),
    )

    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert result.error is not None
    assert result.error.type_name == "InventoryScopeIncomplete"
    assert runner_calls == 0


def test_integrity_resume_uses_a_new_inventory_refresh_receipt(tmp_path: Path) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    scanner = _Scanner(records=(_file(),))
    resolver = _Resolver(mount)
    details: list[InventoryDetails] = []
    inventory_deps = _dependencies(ledger_path, scanner, resolver, details)
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=ledger_path,
        backend=_Backend(root, mount),
        resolver=resolver,
    )
    run_inventory(prepared, _context(), inventory_deps)
    request = IntegrityWorkflowRequest(
        "pause-resume",
        prepared.binding,
        IntegrityMode.VERIFY,
    )

    def pause_after_refresh(*_args):
        raise PauseRequested

    with pytest.raises(PauseRequested):
        run_integrity(
            request,
            _context(),
            IntegrityDependencies(
                ledger_path=inventory_deps.ledger_path,
                scanner=inventory_deps.scanner,
                resolver=inventory_deps.resolver,
                clock=inventory_deps.clock,
                host_key=inventory_deps.host_key,
                host_name=inventory_deps.host_name,
                    save_details=inventory_deps.save_details,
                    verifier_context=lambda context: VerifierContext(
                        run=context,
                        clock=inventory_deps.clock,
                        hasher_factory=xxh3_128,
                    ),
                runners={IntegrityMode.VERIFY: pause_after_refresh},
            ),
        )

    resumed = run_integrity(
        replace(request, refresh_generation=1),
        _context(),
        IntegrityDependencies(
            ledger_path=inventory_deps.ledger_path,
            scanner=inventory_deps.scanner,
            resolver=inventory_deps.resolver,
            clock=inventory_deps.clock,
            host_key=inventory_deps.host_key,
            host_name=inventory_deps.host_name,
                save_details=inventory_deps.save_details,
                verifier_context=lambda context: VerifierContext(
                    run=context,
                    clock=inventory_deps.clock,
                    hasher_factory=xxh3_128,
                ),
            runners={
                IntegrityMode.VERIFY: lambda *_args: IntegrityRunResult(
                    (), RecordingStatus.OK
                )
            },
        ),
    )

    assert resumed.status is SessionState.COMPLETED
    assert len(scanner.calls) == 3


def test_filter_replacement_workflow_projects_both_mapping_locations(
    tmp_path: Path,
) -> None:
    sync_plan = plan(())
    clock = FakeClock()
    setup = setup_recorder(tmp_path / "ledger.db", sync_plan, clock=clock)
    try:
        for location_id, root, volume_id, profile, serial in (
            (
                setup.source_location_id,
                sync_plan.source_root,
                sync_plan.source_volume_id,
                sync_plan.source_profile,
                sync_plan.source_volume_id.serial,
            ),
            (
                setup.target_location_id,
                sync_plan.target_root,
                sync_plan.target_volume_id,
                sync_plan.target_profile,
                sync_plan.target_volume_id.serial,
            ),
        ):
            row = FileRecord(
                "excluded.tmp",
                normalize_relative_path("excluded.tmp"),
                7,
                11,
                FileIdentity(serial, location_id),
                1,
                MetadataSnapshot(0, 3),
            )
            setup.recorder.record_inventory(
                InventoryCommand(
                    location_id,
                    setup.host_id,
                    ScanResult(
                        root,
                        volume_id,
                        VolumeEvidence(device_id=root.path),
                        profile,
                        (row,),
                        (),
                        (),
                        (),
                        IgnoreSet(),
                        ScanScope.full(),
                        True,
                    ),
                    f"filter-inventory-{location_id}",
                    clock.now(),
                )
            )
        replace_mapping_filter(
            "filter-replacement",
            setup.mapping_id,
            FilterSet(("*.tmp",)),
            ledger_path=setup.recorder.path,
            clock=clock,
        )
        with LedgerRepository(setup.recorder.path) as repository:
            snapshot = repository.get_mapping_inventory(setup.mapping_id)

        assert snapshot.filter_snapshot == FilterSet(("*.tmp",))
        assert snapshot.source_location_id == setup.source_location_id
        assert snapshot.target_location_id == setup.target_location_id
        assert snapshot.planner_source_rows == ()
        assert snapshot.planner_target_rows == ()
        assert all(row.projection_current for row in snapshot.source_rows)
        assert all(row.projection_current for row in snapshot.target_rows)
    finally:
        setup.recorder.close()


def test_inventory_and_integrity_payloads_round_trip_continuation() -> None:
    binding = LocationBinding(
        VOLUME_ID,
        "managed",
        "M:\\",
        ("M:\\",),
        False,
        7,
    )
    inventory = InventoryWorkflowRequest(
        "inventory-payload",
        binding,
        ("Folder/File.txt",),
    )
    integrity = IntegrityWorkflowRequest(
        request_id="integrity-payload",
        binding=binding,
        mode=IntegrityMode.REBASELINE,
        selected_paths=("Folder/File.txt",),
        stale_before=datetime(2026, 7, 24, tzinfo=timezone.utc),
        selection_item_ids=("7:11",),
        completed_bytes=(("7:11", 13),),
        processed_bytes=13,
    )

    assert decode_inventory_request(encode_inventory_request(inventory)) == inventory
    assert decode_integrity_request(encode_integrity_request(integrity)) == integrity


def test_integrity_continuation_rejects_progress_without_saved_selection() -> None:
    binding = LocationBinding(
        VOLUME_ID,
        "managed",
        "M:\\",
        ("M:\\",),
        False,
        7,
    )
    with pytest.raises(ValueError, match="saved admitted selection"):
        IntegrityWorkflowRequest(
            request_id="integrity-progress",
            binding=binding,
            mode=IntegrityMode.VERIFY,
            processed_bytes=1,
        )
    with pytest.raises(ValueError, match="belong to the saved selection"):
        IntegrityWorkflowRequest(
            request_id="integrity-completed",
            binding=binding,
            mode=IntegrityMode.VERIFY,
            completed_bytes=(("7:11", 1),),
            processed_bytes=1,
        )
    with pytest.raises(ValueError, match="belong to the saved selection"):
        IntegrityWorkflowRequest(
            request_id="integrity-wrong-completed",
            binding=binding,
            mode=IntegrityMode.VERIFY,
            selection_item_ids=("7:12",),
            completed_bytes=(("7:11", 1),),
            processed_bytes=1,
        )

    valid = IntegrityWorkflowRequest(
        request_id="integrity-preflight-pause",
        binding=binding,
        mode=IntegrityMode.VERIFY,
        refresh_generation=1,
    )
    assert decode_integrity_request(encode_integrity_request(valid)) == valid


def test_integrity_codec_rejects_progress_without_saved_selection() -> None:
    binding = LocationBinding(
        VOLUME_ID,
        "managed",
        "M:\\",
        ("M:\\",),
        False,
        7,
    )
    payload = json.loads(
        encode_integrity_request(
            IntegrityWorkflowRequest(
                request_id="integrity-codec",
                binding=binding,
                mode=IntegrityMode.VERIFY,
            )
        )
    )
    payload["processed_bytes"] = 1

    with pytest.raises(ValueError, match="saved admitted selection"):
        decode_integrity_request(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )

    payload["completed_bytes"] = [["7:11", 1]]
    with pytest.raises(ValueError, match="belong to the saved selection"):
        decode_integrity_request(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
