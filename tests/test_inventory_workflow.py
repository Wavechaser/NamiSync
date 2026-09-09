from __future__ import annotations

import ctypes
import gc
import os
import stat as stat_module
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from weakref import ref

import pytest
from xxhash import xxh3_128

import namisync.workflows.inventory as inventory_workflow
from namisync.core.events import Progress
from namisync.core.evidence import RecordingStatus
from namisync.core.execution import TaskRecordingIssue, TaskRecordingIssueReason
from namisync.core.integrity import (
    INTEGRITY_CANDIDATE_ROW_LIMIT,
    INTEGRITY_CANDIDATE_ROWS_MESSAGE,
    IntegrityCandidateLimitError,
    IntegrityCandidateLimitExceeded,
    IntegrityMode,
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
    IntegrityRunResult,
    IntegritySelection,
    InventoryState,
    ReadStrategy,
    RecordDisposition,
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
    ScanScopeKind,
    ScanWarning,
    ScanWarningCode,
    UnsupportedReason,
    UnsupportedRecord,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import (
    normalize_relative_path,
    to_extended_length_path,
)
from namisync.core.recording import InventoryCommand
from namisync.core.root_authority import RootAuthority
from namisync.core.session import (
    Canceled,
    Disposition,
    OperationResult,
    PauseRequested,
    RunContext,
    SessionState,
)
from namisync.core.review import (
    MAX_PLAN_REVIEW_ROWS,
    ReviewFactLimitExceeded,
    ReviewLimitAxis,
    ReviewPopulation,
    ReviewTreeKind,
    _PlanReviewLimitSignal,
)
from namisync.core.scalars import MAX_SAFE_INTEGER, MAX_SIGNED_64
from namisync.db.connections import connect_ledger_reader
from namisync.db.repositories import InventoryPresence, LedgerRepository
from namisync.modules.scanner import (
    FILE_ATTRIBUTE_REPARSE_POINT,
    VolumeSnapshot,
)
from namisync.workflows.inventory import (
    IntegrityDependencies,
    IntegrityRequest,
    IntegrityWorkflowRequest,
    InventoryDependencies,
    InventoryDetails,
    InventoryRequest,
    InventoryWorkflowRequest,
    LocationBinding,
    MAX_MOUNT_CANDIDATES,
    MAX_VOLUME_RESOLUTION_CANDIDATES,
    MountedVolume,
    NativeMountedVolumeResolver,
    VolumeResolution,
    VolumeResolutionRequired,
    VolumeResolutionState,
    bind_integrity_request,
    bind_inventory_request,
    resolve_binding,
    run_integrity,
    run_inventory,
    settle_canceled_integrity,
)

from _db_fixtures import FakeClock, attestation, plan, setup_recorder


VOLUME_ID = VolumeId("inventory-volume", "NTFS")
PROFILE = CapabilityProfile("NTFS", 100, True, False, 32767, True, True)
EVIDENCE = VolumeEvidence("Inventory", "M:")


class _Resolver:
    def __init__(self, *mounts: Path) -> None:
        self.mounts = tuple(mounts)
        self.probe_error: OSError | None = None
        self.probed_roots: list[str] = []

    def mounted_volumes(
        self, volume_id: VolumeId, hints: tuple[str, ...] = ()
    ) -> tuple[MountedVolume, ...]:
        assert volume_id == VOLUME_ID
        return tuple(MountedVolume(str(path), EVIDENCE) for path in self.mounts)

    def probe_root(self, root_path: str) -> None:
        self.probed_roots.append(root_path)
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
    def __init__(
        self,
        *,
        records: tuple[FileRecord, ...] = (),
        unsupported: tuple[UnsupportedRecord, ...] = (),
        warnings: tuple[ScanWarning, ...] = (),
    ) -> None:
        self.records = records
        self.unsupported = unsupported
        self.warnings = warnings
        self.complete = True
        self.calls: list[tuple[Root, ScanScope]] = []
        self.trusted_anchors: list[str] = []
        self.before_scan = None

    def __call__(
        self,
        root: Root,
        ignores: IgnoreSet,
        context: RunContext,
        scope: ScanScope | None,
        *,
        trusted_anchor: str | None = None,
        population_admission=None,
    ) -> ScanResult:
        assert scope is not None
        assert trusted_anchor is not None
        self.calls.append((root, scope))
        self.trusted_anchors.append(trusted_anchor)
        if self.before_scan is not None:
            self.before_scan()
        selected = set(scope.selected_paths)
        records = (
            self.records
            if not selected
            else tuple(row for row in self.records if row.rel_path in selected)
        )
        unsupported = tuple(
            row
            for row in self.unsupported
            if not selected or row.rel_path in selected
        )
        if population_admission is not None:
            population_admission.require_source_rows(
                len(records) + len(unsupported)
            )
            population_admission.require_informational_source_rows(
                len(self.warnings)
            )
        return ScanResult(
            root,
            VOLUME_ID,
            EVIDENCE,
            PROFILE,
            records,
            (),
            unsupported,
            self.warnings,
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


def _complete_integrity_selection(
    selection,
    verifier_context,
    _recorder=None,
    *,
    result_for=None,
) -> IntegrityRunResult:
    outcomes = []
    for item in selection.pending:
        outcome = IntegrityOutcome(
            item_id=item.item_id,
            row_id=item.row_id,
            location_id=item.location_id,
            path=item.display_path,
            result=(
                IntegrityResult.VERIFIED
                if result_for is None
                else result_for(item)
            ),
            phase=IntegrityMode.VERIFY.value,
        )
        verifier_context.run.emit(outcome)
        selection.mark_completed(item.item_id, 0)
        outcomes.append(outcome)
    return IntegrityRunResult(tuple(outcomes), RecordingStatus.OK)


def _seeded_integrity_case(
    tmp_path: Path,
    paths: tuple[str, ...] = ("file.txt",),
) -> tuple[InventoryWorkflowRequest, InventoryDependencies]:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    scanner = _Scanner(records=tuple(_file(path) for path in paths))
    details: list[InventoryDetails] = []
    inventory_deps = _dependencies(
        tmp_path / "ledger.db",
        scanner,
        _Resolver(mount),
        details,
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=inventory_deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=inventory_deps.resolver,
    )
    assert run_inventory(prepared, _context(), inventory_deps).status is (
        SessionState.COMPLETED
    )
    return prepared, inventory_deps


def _integrity_dependencies(
    inventory_deps: InventoryDependencies,
    runner,
) -> IntegrityDependencies:
    return IntegrityDependencies(
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
        runners={IntegrityMode.VERIFY: runner},
    )


def _integrity_outcome(item, **changes) -> IntegrityOutcome:
    return IntegrityOutcome(
        item_id=item.item_id,
        row_id=item.row_id,
        location_id=item.location_id,
        path=item.display_path,
        result=IntegrityResult.VERIFIED,
        phase=IntegrityMode.VERIFY.value,
        **changes,
    )


class _IntegrityRepositorySpy:
    def __init__(self, rows, *, stale=()) -> None:
        self.rows = {row.row_id: row for row in rows}
        self.stale = tuple(stale)
        self.row_id_calls: list[tuple[int, tuple[str, ...]]] = []
        self.stale_calls: list[tuple[int, datetime]] = []

    def get_inventory(self, _location_id, _path_keys=None):
        raise AssertionError("bounded integrity selection must not read all inventory")

    def get_inventory_by_row_ids(self, location_id, row_ids):
        requested = tuple(row_ids)
        self.row_id_calls.append((location_id, requested))
        return tuple(
            self.rows[row_id] for row_id in requested if row_id in self.rows
        )

    def get_stale_inventory(self, location_id, stale_before):
        self.stale_calls.append((location_id, stale_before))
        return self.stale

    def get_integrity_candidates(
        self,
        location_id,
        mode,
        *,
        path_keys=(),
        stale_before=None,
        saved_row_ids=(),
        completed_row_ids=(),
    ):
        if saved_row_ids:
            requested = tuple(saved_row_ids)
            self.row_id_calls.append((location_id, requested))
            rows = tuple(
                self.rows[row_id] for row_id in requested if row_id in self.rows
            )
            if len(rows) != len(requested):
                raise RuntimeError(
                    "saved integrity selection references missing inventory rows"
                )
            return rows
        if stale_before is not None:
            self.stale_calls.append((location_id, stale_before))
            rows = {row.row_id: row for row in self.stale}
            if completed_row_ids:
                requested = tuple(completed_row_ids)
                self.row_id_calls.append((location_id, requested))
                completed = tuple(
                    self.rows[row_id]
                    for row_id in requested
                    if row_id in self.rows
                )
                if len(completed) != len(requested):
                    raise RuntimeError(
                        "saved integrity progress references missing inventory rows"
                    )
                rows.update((row.row_id, row) for row in completed)
            candidates = tuple(
                sorted(
                    rows.values(),
                    key=lambda row: (row.rel_path_key, int(row.row_id)),
                )
            )
        else:
            candidates = tuple(
                row
                for row in self.rows.values()
                if not path_keys or row.rel_path_key in path_keys
            )
            candidates = tuple(
                row
                for row in candidates
                if row.entry_kind is None or row.entry_kind.value != "directory"
            )
        if mode is IntegrityMode.BASELINE:
            return tuple(row for row in candidates if row.attestation is None)
        if mode is IntegrityMode.REBASELINE:
            return tuple(row for row in candidates if row.attestation is not None)
        return candidates


def test_integrity_continuation_refuses_excess_before_duplicate_copies() -> None:
    binding = LocationBinding(VOLUME_ID, "managed", "M:\\", ("M:\\",), False, 7)
    excess = ("7:11",) * (INTEGRITY_CANDIDATE_ROW_LIMIT + 1)

    with pytest.raises(IntegrityCandidateLimitError) as raised:
        IntegrityWorkflowRequest(
            "excess-saved",
            binding,
            IntegrityMode.VERIFY,
            selection_item_ids=excess,
        )

    assert str(raised.value) == INTEGRITY_CANDIDATE_ROWS_MESSAGE


def test_location_binding_accepts_exact_mount_limit_and_rejects_n_plus_one() -> None:
    mounts = tuple(f"M:\\mount-{index}" for index in range(MAX_MOUNT_CANDIDATES))

    binding = LocationBinding(VOLUME_ID, "managed", mounts[0], mounts, True, 7)
    assert binding.expected_mounts == mounts

    with pytest.raises(ValueError, match="mount-candidate limit"):
        LocationBinding(
            VOLUME_ID,
            "managed",
            mounts[0],
            (*mounts, "M:\\excess"),
            True,
            7,
        )


def test_workflow_request_id_uses_complete_external_text_wall() -> None:
    binding = LocationBinding(VOLUME_ID, "managed", "M:\\", ("M:\\",), False, 7)

    assert InventoryWorkflowRequest("r" * 65_536, binding).request_id == (
        "r" * 65_536
    )
    with pytest.raises(ValueError, match="UTF-8 text bound"):
        InventoryWorkflowRequest("r" * 65_537, binding)
    with pytest.raises(TypeError, match="request id"):
        InventoryWorkflowRequest(
            type("Text", (str,), {})("request"),
            binding,
        )


def test_integrity_request_rejects_empty_list_alias() -> None:
    with pytest.raises(TypeError, match="selected_paths must be a tuple"):
        IntegrityRequest(
            "request",
            IntegrityMode.VERIFY,
            root_path="M:\\managed",
            selected_paths=[],
        )


@pytest.mark.parametrize("kind", ("inventory", "integrity"))
def test_inventory_direct_entries_revalidate_before_resolver_or_ledger_work(
    kind: str,
    tmp_path: Path,
) -> None:
    binding = LocationBinding(VOLUME_ID, "managed", "M:\\", ("M:\\",), False, 7)
    if kind == "inventory":
        outer = InventoryRequest("request", root_path="M:\\managed")
        workflow_request = InventoryWorkflowRequest("request", binding)
        bind = bind_inventory_request
        run = run_inventory
    else:
        outer = IntegrityRequest(
            "request",
            IntegrityMode.VERIFY,
            root_path="M:\\managed",
        )
        workflow_request = IntegrityWorkflowRequest(
            "request",
            binding,
            IntegrityMode.VERIFY,
        )
        bind = bind_integrity_request
        run = run_integrity
    object.__setattr__(outer, "request_id", "r" * 65_537)
    object.__setattr__(workflow_request, "request_id", "r" * 65_537)

    inaccessible = SimpleNamespace()
    with pytest.raises(ValueError, match="UTF-8 text bound"):
        bind(
            outer,
            ledger_path=tmp_path / "ledger.db",
            backend=inaccessible,
            resolver=inaccessible,
        )
    with pytest.raises(ValueError, match="UTF-8 text bound"):
        run(workflow_request, _context(), inaccessible)


@pytest.mark.parametrize(
    "mutation",
    ("shape", "root", "scope"),
)
def test_inventory_scan_result_is_adopted_before_any_ledger_setup(
    mutation: str,
) -> None:
    binding = LocationBinding(VOLUME_ID, "managed", "M:\\", ("M:\\",), False, 7)
    resolution = VolumeResolution(
        VolumeResolutionState.RESOLVED,
        binding,
        root_path="M:\\managed",
        selected_mount="M:\\",
        evidence=EVIDENCE,
        candidates=("M:\\",),
    )

    def scanner(
        root,
        _ignores,
        _ctx,
        scope,
        *,
        trusted_anchor=None,
        population_admission=None,
    ):
        del population_admission
        assert trusted_anchor == "M:\\"
        if mutation == "shape":
            return SimpleNamespace(root=root, scope=scope)
        return ScanResult(
            Root(root.path, "other") if mutation == "root" else root,
            VOLUME_ID,
            EVIDENCE,
            PROFILE,
            (),
            (),
            (),
            (),
            ScanScope.selected(("other",)) if mutation == "scope" else scope,
            True,
        )

    class ForbiddenRecorder:
        def ensure_host(self, *_args):
            raise AssertionError("invalid scan must not register a host")

        def observe_volume(self, *_args):
            raise AssertionError("invalid scan must not observe a volume")

        def ensure_location(self, *_args):
            raise AssertionError("invalid scan must not register a location")

    deps = SimpleNamespace(
        scanner=scanner,
        ignores=IgnoreSet(),
        clock=FakeClock(),
        host_key="host",
        host_name="Host",
    )
    expected = TypeError if mutation == "shape" else RuntimeError
    with pytest.raises(expected):
        inventory_workflow._register_and_scan(
            "request",
            "request",
            binding,
            resolution,
            (),
            (),
            _context(),
            deps,
            ForbiddenRecorder(),
            inventory_workflow._InventoryScanAdmission(),
        )

def test_inventory_scanner_receives_detached_ignore_policy(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    received: list[IgnoreSet] = []

    class MutatingScanner(_Scanner):
        def __call__(self, root, ignores, context, scope, **kwargs):
            received.append(ignores)
            object.__setattr__(ignores, "exact_names", frozenset({"FORGED"}))
            return super().__call__(root, ignores, context, scope, **kwargs)

    scanner = MutatingScanner()
    details: list[InventoryDetails] = []
    deps = _dependencies(
        tmp_path / "ledger.db",
        scanner,
        _Resolver(mount),
        details,
    )
    configured_ignores = deps.ignores
    prepared = bind_inventory_request(
        InventoryRequest("detached-ignores", root_path=str(root)),
        ledger_path=deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=deps.resolver,
    )

    result = run_inventory(prepared, _context(), deps)

    assert result.status is SessionState.COMPLETED
    assert len(received) == 1
    assert received[0] is not configured_ignores
    assert configured_ignores == IgnoreSet()


def test_hostile_scanner_cannot_mutate_registration_binding(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    forged_volume = VolumeId("forged-volume", "NTFS")
    prepared = bind_inventory_request(
        InventoryRequest("hostile-binding", root_path=str(root)),
        ledger_path=ledger_path,
        backend=_Backend(root, mount),
        resolver=_Resolver(mount),
    )

    class MutatingScanner(_Scanner):
        def __call__(
            self,
            scan_root,
            _ignores,
            _context,
            scope,
            *,
            trusted_anchor=None,
            population_admission=None,
        ):
            assert trusted_anchor == str(mount)
            assert population_admission is not None
            object.__setattr__(prepared.binding, "volume_id", forged_volume)
            return ScanResult(
                scan_root,
                forged_volume,
                EVIDENCE,
                PROFILE,
                (),
                (),
                (),
                (),
                scope,
                True,
            )

    details: list[InventoryDetails] = []
    deps = _dependencies(
        ledger_path,
        MutatingScanner(),
        _Resolver(mount),
        details,
    )

    with pytest.raises(RuntimeError, match="volume changed after preflight"):
        run_inventory(prepared, _context(), deps)

    assert details == []
    with connect_ledger_reader(ledger_path) as connection:
        for table in ("hosts", "volumes", "locations", "inventory"):
            assert connection.execute(
                f"SELECT count(*) FROM {table}"
            ).fetchone()[0] == 0


def test_resolution_rejects_excess_candidates_before_path_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = LocationBinding(VOLUME_ID, "managed", "M:\\", ("M:\\",), False, 7)

    projected: list[str] = []
    original_path_key = inventory_workflow._path_key

    def observed_path_key(path: str) -> str:
        projected.append(path)
        return original_path_key(path)

    monkeypatch.setattr(inventory_workflow, "_path_key", observed_path_key)
    with pytest.raises(ValueError, match="mount-candidate limit"):
        VolumeResolution(
            VolumeResolutionState.AMBIGUOUS,
            binding,
            candidates=tuple(
                f"M:\\mount-{index}"
                for index in range(MAX_VOLUME_RESOLUTION_CANDIDATES + 1)
            ),
        )
    assert all("mount-" not in path for path in projected)


def test_resolution_diagnostic_uses_complete_omission_at_utf8_boundary() -> None:
    binding = LocationBinding(VOLUME_ID, "managed", "M:\\", ("M:\\",), False, 7)

    exact = VolumeResolution(
        VolumeResolutionState.OFFLINE,
        binding,
        detail="\u00e9" * 512,
    )
    omitted = VolumeResolution(
        VolumeResolutionState.OFFLINE,
        binding,
        detail=("\u00e9" * 512) + "x",
    )

    assert exact.detail == "\u00e9" * 512
    assert omitted.detail is None


def test_native_resolver_rejects_excess_hints_before_drive_enumeration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_drives() -> tuple[str, ...]:
        raise AssertionError("excess hints must not enumerate drives")

    monkeypatch.setattr(
        inventory_workflow,
        "_logical_drive_roots",
        forbidden_drives,
    )
    resolver = NativeMountedVolumeResolver(SimpleNamespace())

    with pytest.raises(ValueError, match="hints exceed"):
        resolver.mounted_volumes(
            VOLUME_ID,
            tuple(
                f"M:\\mount-{index}"
                for index in range(MAX_MOUNT_CANDIDATES + 1)
            ),
        )


def test_logical_drive_source_buffer_accepts_exact_maximum_and_rejects_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = tuple(f"{chr(ord('A') + index)}:\\" for index in range(26))
    multistring = "\x00".join(roots) + "\x00\x00"
    assert len(multistring) == 105

    class Kernel32:
        result = 104
        calls = 0

        def GetLogicalDriveStringsW(self, size, buffer):
            self.calls += 1
            assert size == len(multistring)
            if self.result >= size:
                return self.result
            for index, character in enumerate(multistring):
                buffer[index] = character
            return self.result

    kernel32 = Kernel32()
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: kernel32)

    assert inventory_workflow._logical_drive_roots() == roots
    assert kernel32.calls == 1

    kernel32.result = 105
    with pytest.raises(OSError, match="fixed source bound"):
        inventory_workflow._logical_drive_roots()
    assert kernel32.calls == 2


def test_native_resolver_revalidates_forged_snapshot_before_mount_projection() -> None:
    evidence = VolumeEvidence("Inventory", "M:\\")
    snapshot = VolumeSnapshot(VOLUME_ID, evidence, PROFILE)
    object.__setattr__(evidence, "device_id", "p" * 32_768)

    class Backend:
        def volume_snapshot(self, _path: str) -> VolumeSnapshot:
            return snapshot

    with pytest.raises(ValueError, match="UTF-16 path bound"):
        NativeMountedVolumeResolver(Backend()).mounted_volumes(
            VOLUME_ID,
            ("M:\\",),
        )


def test_integrity_continuation_requires_completed_selection_order() -> None:
    binding = LocationBinding(VOLUME_ID, "managed", "M:\\", ("M:\\",), False, 7)

    with pytest.raises(ValueError, match="saved selection order"):
        IntegrityWorkflowRequest(
            "misordered-completion",
            binding,
            IntegrityMode.VERIFY,
            selection_item_ids=("7:11", "7:12", "7:13"),
            completed_bytes=(("7:12", 1), ("7:11", 1)),
            processed_bytes=2,
            bytes_total_high_water=3,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("selected_paths", ["a.txt"]),
        ("selection_item_ids", ["7:11"]),
        ("completed_bytes", [["7:11", 1]]),
    ),
)
def test_integrity_continuation_rejects_aliasable_sequence_shapes(
    field: str,
    value: object,
) -> None:
    binding = LocationBinding(VOLUME_ID, "managed", "M:\\", ("M:\\",), False, 7)
    fields: dict[str, object] = {
        "request_id": "aliasable-sequence",
        "binding": binding,
        "mode": IntegrityMode.VERIFY,
        "selection_item_ids": ("7:11",),
    }
    fields[field] = value

    with pytest.raises(TypeError):
        IntegrityWorkflowRequest(**fields)  # type: ignore[arg-type]


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

    resolver = _Resolver(mount)
    monkeypatch.setattr(inventory_workflow.os, "stat", missing_stat)
    resolution = resolve_binding(_binding(mount), resolver)

    assert observed_paths == [to_extended_length_path(str(root))]
    assert resolution.state is VolumeResolutionState.ROOT_MISSING
    assert resolution.root_path == str(root)
    assert resolver.probed_roots == []


def test_resolve_binding_admits_chain_before_accessibility_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    resolver = _Resolver(mount)
    calls: list[str] = []

    def admit(authority: RootAuthority, *, anchor_probe) -> str:
        assert authority == RootAuthority(str(root), str(mount))
        assert anchor_probe(str(root)) == str(mount)
        calls.append("chain")
        return str(mount)

    def probe(root_path: str) -> None:
        assert root_path == str(root)
        calls.append("probe")

    monkeypatch.setattr(inventory_workflow, "admit_root_chain", admit)
    resolver.probe_root = probe

    resolution = resolve_binding(_binding(mount), resolver)

    assert resolution.state is VolumeResolutionState.RESOLVED
    assert calls == ["chain", "probe"]


def test_resolve_binding_owns_admitted_collaborator_values(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    other = tmp_path / "other"
    (mount / "managed").mkdir(parents=True)
    admitted_volume = VolumeId("admitted-volume", "NTFS")
    binding = LocationBinding(
        admitted_volume,
        "managed",
        str(mount),
        (str(mount),),
        False,
        7,
    )
    raw_evidence = VolumeEvidence("Admitted", str(mount))
    raw_mount = MountedVolume(str(mount), raw_evidence)

    class HostileResolver:
        first_lookup = True

        def mounted_volumes(
            self,
            volume_id: VolumeId,
            hints: tuple[str, ...] = (),
        ) -> tuple[MountedVolume, ...]:
            assert volume_id == admitted_volume
            assert hints == (str(mount),)
            object.__setattr__(volume_id, "serial", "callback-forged")
            if self.first_lookup:
                self.first_lookup = False
                object.__setattr__(
                    binding,
                    "volume_id",
                    VolumeId("caller-forged", "NTFS"),
                )
                object.__setattr__(binding, "selected_mount", str(other))
                object.__setattr__(binding, "expected_mounts", (str(other),))
                return (raw_mount,)
            return (
                MountedVolume(
                    str(mount),
                    VolumeEvidence("Admitted", str(mount)),
                ),
            )

        def probe_root(self, root_path: str) -> None:
            assert root_path == str(mount / "managed")
            object.__setattr__(raw_mount, "mount_path", str(other))
            object.__setattr__(raw_evidence, "label", "Forged")

    resolution = resolve_binding(binding, HostileResolver())

    assert resolution.state is VolumeResolutionState.RESOLVED
    assert resolution.binding is not binding
    assert resolution.binding == LocationBinding(
        admitted_volume,
        "managed",
        str(mount),
        (str(mount),),
        False,
        7,
    )
    assert resolution.binding.volume_id is not admitted_volume
    assert resolution.selected_mount == str(mount)
    assert resolution.evidence == VolumeEvidence("Admitted", str(mount))
    assert resolution.evidence is not raw_evidence


def test_resolve_binding_revalidates_mounted_values_as_an_unordered_set(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    clone = tmp_path / "clone"
    (mount / "managed").mkdir(parents=True)
    clone.mkdir()
    order = [mount, clone]

    class ReorderingResolver:
        def mounted_volumes(
            self,
            volume_id: VolumeId,
            hints: tuple[str, ...] = (),
        ) -> tuple[MountedVolume, ...]:
            assert volume_id == VOLUME_ID
            assert hints == (str(mount), str(clone))
            return tuple(
                MountedVolume(str(path), EVIDENCE) for path in order
            )

        def probe_root(self, root_path: str) -> None:
            assert root_path == str(mount / "managed")
            order.reverse()

    binding = LocationBinding(
        VOLUME_ID,
        "managed",
        str(mount),
        (str(mount), str(clone)),
        True,
    )

    resolution = resolve_binding(binding, ReorderingResolver())

    assert resolution.state is VolumeResolutionState.RESOLVED
    assert resolution.candidates == (str(mount), str(clone))


@pytest.mark.parametrize("workflow", ["inventory", "integrity"])
@pytest.mark.parametrize("drift", ["mount", "evidence"])
def test_mounted_volume_drift_refuses_before_workflow_effects(
    tmp_path: Path,
    workflow: str,
    drift: str,
) -> None:
    mount = tmp_path / "mount"
    other = tmp_path / "other"
    (mount / "managed").mkdir(parents=True)
    (other / "managed").mkdir(parents=True)

    class DriftingResolver:
        current_mount = mount
        current_evidence = VolumeEvidence("Admitted", str(mount))

        def mounted_volumes(
            self,
            volume_id: VolumeId,
            hints: tuple[str, ...] = (),
        ) -> tuple[MountedVolume, ...]:
            assert volume_id == VOLUME_ID
            assert hints == (str(mount),)
            return (
                MountedVolume(
                    str(self.current_mount),
                    self.current_evidence,
                ),
            )

        def probe_root(self, root_path: str) -> None:
            assert root_path == str(mount / "managed")
            if drift == "mount":
                self.current_mount = other
            else:
                self.current_evidence = VolumeEvidence(
                    "Changed",
                    str(mount),
                )

    ledger_path = tmp_path / "ledger.db"
    scanner = _Scanner()
    details: list[InventoryDetails] = []
    resolver = DriftingResolver()
    request_binding = _binding(mount)
    if workflow == "inventory":
        result = run_inventory(
            InventoryWorkflowRequest("resolver-drift", request_binding),
            _context(),
            _dependencies(
                ledger_path,
                scanner,
                resolver,  # type: ignore[arg-type]
                details,
            ),
        )
    else:
        result = run_integrity(
            IntegrityWorkflowRequest(
                "resolver-drift",
                request_binding,
                IntegrityMode.VERIFY,
            ),
            _context(),
            IntegrityDependencies(
                ledger_path=ledger_path,
                scanner=scanner,
                resolver=resolver,
                clock=FakeClock(),
                host_key="host",
                host_name="Host",
                save_details=details.append,
            ),
        )

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert scanner.calls == []
    assert not ledger_path.exists()
    assert len(details) == 1
    assert details[0].resolution.state is not VolumeResolutionState.RESOLVED
    assert details[0].resolution.detail is not None
    assert "changed during root admission" in details[0].resolution.detail
    assert details[0].resolution.binding is not request_binding


def test_native_resolver_probe_uses_scanner_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _ProbeBackend()

    def raw_scandir(_path: str):
        raise AssertionError("raw os.scandir must not be used")

    monkeypatch.setattr(inventory_workflow.os, "scandir", raw_scandir)

    NativeMountedVolumeResolver(backend).probe_root("logical-root")  # type: ignore[arg-type]

    assert backend.scanned_paths == ["logical-root"]


def test_first_location_adopts_scan_once_before_registration_and_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    scanner = _Scanner(records=(_file(),))
    details: list[InventoryDetails] = []
    adoption_calls: list[ScanResult] = []
    original_adopt = inventory_workflow.adopt_scan_result

    def track_adoption(value, admission, *, row_limit):
        adoption_calls.append(value)
        adopted = original_adopt(value, admission, row_limit=row_limit)
        assert adopted is value
        return adopted

    monkeypatch.setattr(
        inventory_workflow,
        "adopt_scan_result",
        track_adoption,
    )

    def assert_scan_precedes_registration() -> None:
        with connect_ledger_reader(ledger_path) as connection:
            assert connection.execute("SELECT count(*) FROM hosts").fetchone()[0] == 0
            assert connection.execute("SELECT count(*) FROM volumes").fetchone()[0] == 0
            assert connection.execute("SELECT count(*) FROM locations").fetchone()[0] == 0
            assert connection.execute("SELECT count(*) FROM mappings").fetchone()[0] == 0
            assert connection.execute("SELECT count(*) FROM inventory").fetchone()[0] == 0

    scanner.before_scan = assert_scan_precedes_registration
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
    assert len(adoption_calls) == len(scanner.calls) == 1
    assert details[-1].resolution.state is VolumeResolutionState.RESOLVED
    assert details[-1].observed_count == 1
    with connect_ledger_reader(ledger_path) as connection:
        assert connection.execute("SELECT count(*) FROM mappings").fetchone()[0] == 0
    with LedgerRepository(ledger_path) as repository:
        rows = repository.get_inventory(details[-1].location_id or 0)
    assert tuple(row.rel_path for row in rows) == ("file.txt",)


def test_incomplete_inventory_retains_typed_scan_warnings(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    warning = ScanWarning(
        ScanWarningCode.ROOT_UNAVAILABLE,
        "Folder",
        "denied",
    )
    scanner = _Scanner(warnings=(warning,))
    scanner.complete = False
    details: list[InventoryDetails] = []

    result = run_inventory(
        bind_inventory_request(
            InventoryRequest(
                "warning",
                root_path=str(root),
                subtree_roots=("Folder",),
            ),
            ledger_path=tmp_path / "ledger.db",
            backend=_Backend(root, mount),
            resolver=_Resolver(mount),
        ),
        _context(),
        _dependencies(
            tmp_path / "ledger.db",
            scanner,
            _Resolver(mount),
            details,
        ),
    )

    assert result.status is SessionState.COMPLETED
    assert scanner.calls[0][1].kind is ScanScopeKind.SUBTREES
    assert details[-1].complete is False
    assert details[-1].warnings == (warning,)


@pytest.mark.parametrize("text", ("\ud800", "\udcff", "\ud83d\ude00"))
def test_incomplete_inventory_omits_malformed_warning_detail_but_records_observations(
    tmp_path: Path, text: str,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    warning = ScanWarning(ScanWarningCode.PATH_UNREPRESENTABLE, None, "bad-" + text)
    scanner = _Scanner(records=(_file(),), warnings=(warning,))
    scanner.complete = False
    details: list[InventoryDetails] = []
    result = run_inventory(
        bind_inventory_request(
            InventoryRequest("malformed-warning", root_path=str(root)),
            ledger_path=ledger_path,
            backend=_Backend(root, mount),
            resolver=_Resolver(mount),
        ),
        _context(),
        _dependencies(ledger_path, scanner, _Resolver(mount), details),
    )

    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.OK
    assert not details[-1].complete
    assert details[-1].observed_count == 1
    assert details[-1].warnings == (ScanWarning(ScanWarningCode.PATH_UNREPRESENTABLE, None),)
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


def test_inventory_remount_uses_current_mount_and_preserves_location_identity(
    tmp_path: Path,
) -> None:
    prior_mount = tmp_path / "prior-mount"
    current_mount = tmp_path / "current-mount"
    prior_root = prior_mount / "managed"
    current_root = current_mount / "managed"
    prior_root.mkdir(parents=True)
    current_root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    scanner = _Scanner(records=(_file(),))
    details: list[InventoryDetails] = []
    resolver = _Resolver(prior_mount)
    deps = _dependencies(ledger_path, scanner, resolver, details)
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(prior_root)),
        ledger_path=ledger_path,
        backend=_Backend(prior_root, prior_mount),
        resolver=resolver,
    )

    seeded = run_inventory(prepared, _context(), deps)
    assert seeded.status is SessionState.COMPLETED
    seeded_location = details[-1].location_id
    resolver.mounts = (current_mount,)

    refreshed = run_inventory(
        InventoryWorkflowRequest("remounted", prepared.binding),
        _context(),
        deps,
    )

    assert refreshed.status is SessionState.COMPLETED
    assert details[-1].location_id == seeded_location
    assert details[-1].resolution.selected_mount == str(current_mount)
    assert scanner.calls[-1][0].path == str(current_root)
    assert scanner.trusted_anchors[-1] == str(current_mount)

    verifier_contexts: list[VerifierContext] = []

    def runner(selection, verifier_context, _recorder):
        verifier_contexts.append(verifier_context)
        return _complete_integrity_selection(selection, verifier_context)

    integrity = run_integrity(
        IntegrityWorkflowRequest(
            "remounted-integrity",
            prepared.binding,
            IntegrityMode.VERIFY,
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
            verifier_context=lambda context: VerifierContext(
                run=context,
                clock=deps.clock,
                hasher_factory=xxh3_128,
            ),
            runners={IntegrityMode.VERIFY: runner},
        ),
    )

    assert integrity.status is SessionState.COMPLETED
    assert verifier_contexts[0].root_authority == RootAuthority(
        str(current_root),
        str(current_mount),
        VOLUME_ID,
    )


def test_intermediate_reparse_replacement_preserves_inventory_and_blocks_integrity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "mount"
    parent = mount / "parent"
    root = parent / "managed"
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
    seed = run_inventory(prepared, _context(), deps)
    assert seed.status is SessionState.COMPLETED
    location_id = details[-1].location_id
    assert location_id is not None

    native_parent = to_extended_length_path(str(parent))
    native_root = to_extended_length_path(str(root))
    original_stat = inventory_workflow.os.stat

    def reparse_root_stat(path, *args, **kwargs):
        if (
            str(path) == native_parent
            and kwargs.get("follow_symlinks") is False
        ):
            return SimpleNamespace(
                st_mode=stat_module.S_IFDIR | 0o755,
                st_file_attributes=FILE_ATTRIBUTE_REPARSE_POINT,
                st_reparse_tag=1,
            )
        if (
            str(path) == native_root
            and kwargs.get("follow_symlinks") is False
        ):
            raise AssertionError(
                "inventory must not probe through an intermediate reparse"
            )
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(inventory_workflow.os, "stat", reparse_root_stat)
    scanner.records = ()

    inventory_result = run_inventory(
        InventoryWorkflowRequest("refresh", prepared.binding),
        _context(),
        deps,
    )

    assert inventory_result.status is SessionState.REFUSED
    assert details[-1].resolution.state is VolumeResolutionState.ROOT_UNAVAILABLE
    assert "reparse point" in (details[-1].resolution.detail or "")
    assert len(scanner.calls) == 1
    with LedgerRepository(ledger_path) as repository:
        retained = repository.get_inventory(location_id)
    assert len(retained) == 1
    assert retained[0].presence is InventoryPresence.PRESENT

    runner_calls = 0

    def runner(*_args):
        nonlocal runner_calls
        runner_calls += 1
        raise AssertionError("integrity reader must not start")

    integrity_result = run_integrity(
        IntegrityWorkflowRequest(
            "verify-after-reparse",
            prepared.binding,
            IntegrityMode.VERIFY,
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
            ignores=deps.ignores,
            runners={IntegrityMode.VERIFY: runner},
        ),
    )

    assert integrity_result.status is SessionState.REFUSED
    assert details[-1].resolution.state is VolumeResolutionState.ROOT_UNAVAILABLE
    assert len(scanner.calls) == 1
    assert runner_calls == 0


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths")
def test_root_unavailable_resolution_sanitizes_native_probe_filename(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    resolver = _Resolver(mount)
    resolver.probe_error = PermissionError(
        13,
        "denied",
        to_extended_length_path(str(root)),
    )

    resolution = resolve_binding(_binding(mount), resolver)

    assert resolution.state is VolumeResolutionState.ROOT_UNAVAILABLE
    assert resolution.detail is not None
    assert "managed" in resolution.detail
    assert "\\\\?\\" not in resolution.detail


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


@pytest.mark.parametrize(
    "available_mounts, expected_resolution",
    [
        ((), VolumeResolutionState.OFFLINE),
        (("mount", "clone"), VolumeResolutionState.AMBIGUOUS),
    ],
)
def test_resumed_integrity_resolution_failure_retains_continuation_authority(
    tmp_path: Path,
    available_mounts: tuple[str, ...],
    expected_resolution: VolumeResolutionState,
) -> None:
    mount = tmp_path / "mount"
    clone = tmp_path / "clone"
    mount.mkdir()
    clone.mkdir()
    resolver = _Resolver(
        *(mount if name == "mount" else clone for name in available_mounts)
    )
    scanner = _Scanner(records=(_file(),))
    details: list[InventoryDetails] = []
    deps = IntegrityDependencies(
        ledger_path=tmp_path / "ledger.db",
        scanner=scanner,
        resolver=resolver,
        clock=FakeClock(),
        host_key="host",
        host_name="Host",
        save_details=details.append,
    )

    fresh = run_integrity(
        IntegrityWorkflowRequest(
            "fresh-resolution-failure",
            _binding(mount),
            IntegrityMode.VERIFY,
        ),
        _context(),
        deps,
    )

    result = run_integrity(
        IntegrityWorkflowRequest(
            "resume-resolution-failure",
            _binding(mount),
            IntegrityMode.VERIFY,
            selection_item_ids=("1:saved",),
            processed_bytes=13,
            bytes_total_high_water=21,
            recording=RecordingStatus.DEGRADED,
            refresh_generation=1,
        ),
        _context(),
        deps,
    )

    assert fresh.status is SessionState.REFUSED
    assert fresh.disposition is Disposition.UNRUN
    assert (fresh.bytes_done, fresh.bytes_total) == (0, 0)
    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert result.recording is RecordingStatus.DEGRADED
    assert (result.bytes_done, result.bytes_total) == (13, 21)
    assert result.error is not None
    assert result.error.type_name == "VolumeResolution"
    assert details[-1].resolution.state is expected_resolution
    assert scanner.calls == []


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


def test_resumed_incomplete_integrity_refresh_retains_continuation_authority(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    scanner = _Scanner(records=(_file(),))
    resolver = _Resolver(mount)
    details: list[InventoryDetails] = []
    deps = _dependencies(tmp_path / "ledger.db", scanner, resolver, details)
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=resolver,
    )
    run_inventory(prepared, _context(), deps)
    scanner.complete = False
    runner_calls = 0

    def runner(*_args):
        nonlocal runner_calls
        runner_calls += 1
        raise AssertionError("incomplete resumed refresh must not hash")

    result = run_integrity(
        IntegrityWorkflowRequest(
            "resume-incomplete",
            prepared.binding,
            IntegrityMode.VERIFY,
            selection_item_ids=("1:saved",),
            processed_bytes=13,
            bytes_total_high_water=21,
            recording=RecordingStatus.DEGRADED,
            refresh_generation=1,
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
    assert result.recording is RecordingStatus.DEGRADED
    assert (result.bytes_done, result.bytes_total) == (13, 21)
    assert result.error is not None
    assert result.error.type_name == "InventoryScopeIncomplete"
    assert details[-1].complete is False
    assert runner_calls == 0


@pytest.mark.parametrize(
    "stale_before",
    [None, datetime(2027, 1, 1, tzinfo=timezone.utc)],
    ids=("full", "stale"),
)
def test_incomplete_unbounded_integrity_refresh_runs_no_hash(
    tmp_path: Path,
    stale_before: datetime | None,
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
    scanner.warnings = (
        ScanWarning(
            ScanWarningCode.ENUMERATION_ERROR,
            None,
            "root enumeration failed",
        ),
    )
    runner_calls = 0

    def runner(*_args):
        nonlocal runner_calls
        runner_calls += 1
        raise AssertionError("incomplete refresh must not hash")

    result = run_integrity(
        IntegrityWorkflowRequest(
            "incomplete-unbounded",
            prepared.binding,
            IntegrityMode.VERIFY,
            stale_before=stale_before,
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
    assert details[-1].complete is False
    assert details[-1].warnings == scanner.warnings
    assert runner_calls == 0


def test_subject_local_incomplete_integrity_continues_with_unsupported_item(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    scanner = _Scanner(records=(_file(), _file("readable.txt")))
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
    warning = ScanWarning(
        ScanWarningCode.ACCESS_DENIED,
        "file.txt",
        "denied",
    )
    scanner.records = (_file("readable.txt"),)
    scanner.unsupported = (
        UnsupportedRecord(
            "file.txt",
            normalize_relative_path("file.txt"),
            UnsupportedReason.ACCESS_DENIED,
        ),
    )
    scanner.warnings = (warning,)
    scanner.complete = False
    selected_states: list[InventoryState] = []
    verifier_contexts: list[VerifierContext] = []

    def runner(selection, verifier_context, _recorder):
        assert len(selection.items) == 2
        verifier_contexts.append(verifier_context)
        selected_states.extend(
            item.expected_state for item in selection.items
        )
        return _complete_integrity_selection(
            selection,
            verifier_context,
            result_for=lambda item: (
                IntegrityResult.UNSUPPORTED
                if item.expected_state is InventoryState.UNSUPPORTED
                else IntegrityResult.VERIFIED
            ),
        )

    result = run_integrity(
        IntegrityWorkflowRequest(
            "folder-expanded",
            prepared.binding,
            IntegrityMode.VERIFY,
            ("file.txt", "readable.txt"),
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
            verifier_context=lambda context: VerifierContext(
                run=context,
                clock=deps.clock,
                hasher_factory=xxh3_128,
            ),
            runners={IntegrityMode.VERIFY: runner},
        ),
    )

    assert result.status is SessionState.COMPLETED
    assert selected_states == [
        InventoryState.UNSUPPORTED,
        InventoryState.PRESENT,
    ]
    assert verifier_contexts[0].root_authority == RootAuthority(
        str(root),
        str(mount),
        VOLUME_ID,
    )
    assert [item.result for item in result.items] == [
        IntegrityResult.UNSUPPORTED,
        IntegrityResult.VERIFIED,
    ]
    assert details[-1].warnings == (warning,)


@pytest.mark.parametrize(
    "scenario",
    ("normal", "completion-failure", "sink-failure"),
)
def test_integrity_outcome_acceptance_window(
    tmp_path: Path,
    scenario: str,
) -> None:
    prepared, inventory_deps = _seeded_integrity_case(tmp_path)
    selections: list[IntegritySelection] = []
    attempted: list[IntegrityOutcome] = []
    completion_counts: list[int] = []

    def emit(body: object) -> None:
        if not isinstance(body, IntegrityOutcome):
            return
        attempted.append(body)
        completion_counts.append(selections[0].completed_count)
        if scenario == "sink-failure":
            raise OSError("reliable outcome sink failed")

    def runner(selection, verifier_context, _recorder):
        item = selection.pending[0]
        outcome = _integrity_outcome(item)
        verifier_context.run.emit(outcome)
        selection.mark_completed(
            "unknown-item"
            if scenario == "completion-failure"
            else item.item_id,
            0,
        )
        return IntegrityRunResult((outcome,), RecordingStatus.OK)

    result = run_integrity(
        IntegrityWorkflowRequest(
            f"acceptance-{scenario}",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        RunContext(emit, lambda: None),
        _integrity_dependencies(inventory_deps, runner),
        selection_sink=selections.append,
    )

    assert completion_counts == [0]
    assert len(attempted) == 1
    assert result.disposition is Disposition.RAN
    if scenario == "normal":
        assert result.status is SessionState.COMPLETED
        assert result.error is None
        assert result.items == tuple(attempted)
        assert selections[0].completed_count == 1
    elif scenario == "completion-failure":
        assert result.status is SessionState.FAILED
        assert result.items == tuple(attempted)
        assert selections[0].completed_count == 0
        assert result.error is not None
        assert (result.error.type_name, result.error.message) == (
            "ValueError",
            "unknown integrity item: unknown-item",
        )
    else:
        assert result.status is SessionState.FAILED
        assert result.items == ()
        assert selections[0].completed_count == 0
        assert result.error is not None
        assert (result.error.type_name, result.error.message) == (
            "OSError",
            "reliable outcome sink failed",
        )


def test_integrity_blocks_unreported_completion_before_checkpoint(
    tmp_path: Path,
) -> None:
    prepared, inventory_deps = _seeded_integrity_case(tmp_path)
    checkpoint_calls = 0
    runner_resumed = False

    def checkpoint() -> None:
        nonlocal checkpoint_calls
        checkpoint_calls += 1

    def runner(selection, verifier_context, _recorder):
        nonlocal runner_resumed
        item = selection.pending[0]
        selection.mark_completed(item.item_id, 0)
        verifier_context.run.checkpoint()
        runner_resumed = True
        raise AssertionError("unreported completion crossed the checkpoint")

    result = run_integrity(
        IntegrityWorkflowRequest(
            "unreported-before-checkpoint",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        RunContext(lambda _body: None, checkpoint),
        _integrity_dependencies(inventory_deps, runner),
    )

    assert checkpoint_calls == 0
    assert runner_resumed is False
    assert result.status is SessionState.FAILED
    assert result.items == ()
    assert result.error is not None
    assert (result.error.type_name, result.error.message) == (
        "ValueError",
        "integrity runner completion must match its emitted outcomes",
    )


def test_integrity_checks_completion_written_by_checkpoint_callback(
    tmp_path: Path,
) -> None:
    prepared, inventory_deps = _seeded_integrity_case(tmp_path)
    selections: list[IntegritySelection] = []
    runner_resumed = False

    def checkpoint() -> None:
        selection = selections[0]
        item = selection.pending[0]
        selection.mark_completed(item.item_id, 0)

    def runner(_selection, verifier_context, _recorder):
        nonlocal runner_resumed
        verifier_context.run.checkpoint()
        runner_resumed = True
        raise AssertionError("callback-written completion was accepted")

    result = run_integrity(
        IntegrityWorkflowRequest(
            "callback-completion",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        RunContext(lambda _body: None, checkpoint),
        _integrity_dependencies(inventory_deps, runner),
        selection_sink=selections.append,
    )

    assert runner_resumed is False
    assert result.status is SessionState.FAILED
    assert result.items == ()
    assert result.error is not None
    assert (result.error.type_name, result.error.message) == (
        "ValueError",
        "integrity runner completion must match its emitted outcomes",
    )


def test_integrity_rejects_progress_written_by_checkpoint_callback(
    tmp_path: Path,
) -> None:
    prepared, inventory_deps = _seeded_integrity_case(tmp_path)
    selections: list[IntegritySelection] = []
    runner_resumed = False

    def checkpoint() -> None:
        selections[0].note_bytes_processed(1)

    def runner(_selection, verifier_context, _recorder):
        nonlocal runner_resumed
        verifier_context.run.checkpoint()
        runner_resumed = True
        raise AssertionError("callback-written progress was accepted")

    result = run_integrity(
        IntegrityWorkflowRequest(
            "callback-progress",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        RunContext(lambda _body: None, checkpoint),
        _integrity_dependencies(inventory_deps, runner),
        selection_sink=selections.append,
    )

    assert runner_resumed is False
    assert result.status is SessionState.FAILED
    assert result.items == ()
    assert result.error is not None
    assert (result.error.type_name, result.error.message) == (
        "ValueError",
        "integrity progress changed during callback",
    )


def test_integrity_rejects_pause_with_an_uncompleted_accepted_outcome(
    tmp_path: Path,
) -> None:
    prepared, inventory_deps = _seeded_integrity_case(tmp_path)
    emitted: list[object] = []

    def runner(selection, verifier_context, _recorder):
        verifier_context.run.emit(_integrity_outcome(selection.pending[0]))
        raise PauseRequested("pause after outcome")

    result = run_integrity(
        IntegrityWorkflowRequest(
            "pause-after-outcome",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        RunContext(emitted.append, lambda: None),
        _integrity_dependencies(inventory_deps, runner),
    )

    reliable = tuple(
        body for body in emitted if isinstance(body, IntegrityOutcome)
    )
    assert len(reliable) == 1
    assert result.status is SessionState.FAILED
    assert result.items == reliable
    assert result.error is not None
    assert (result.error.type_name, result.error.message) == (
        "ValueError",
        "integrity runner completion must match its emitted outcomes",
    )


def test_integrity_keeps_accepted_outcome_when_callback_replaces_items(
    tmp_path: Path,
) -> None:
    prepared, inventory_deps = _seeded_integrity_case(tmp_path)
    selections: list[IntegritySelection] = []
    emitted: list[object] = []

    def emit(body: object) -> None:
        emitted.append(body)
        if isinstance(body, IntegrityOutcome):
            selection = selections[0]
            selection.items = tuple(replace(item) for item in selection.items)

    def runner(selection, verifier_context, _recorder):
        verifier_context.run.emit(_integrity_outcome(selection.pending[0]))
        raise AssertionError("replaced selection crossed the reliable event")

    result = run_integrity(
        IntegrityWorkflowRequest(
            "accepted-before-transfer-failure",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        RunContext(emit, lambda: None),
        _integrity_dependencies(inventory_deps, runner),
        selection_sink=selections.append,
    )

    reliable = tuple(
        body for body in emitted if isinstance(body, IntegrityOutcome)
    )
    assert len(reliable) == 1
    assert result.status is SessionState.FAILED
    assert result.items == reliable
    assert result.error is not None
    assert (result.error.type_name, result.error.message) == (
        "ValueError",
        "integrity selection items changed during collaboration",
    )


@pytest.mark.parametrize(
    (
        "mismatch",
        "expected_message",
        "expected_items",
        "expected_completed",
    ),
    (
        (
            "duplicate",
            "integrity runner emitted a duplicate outcome",
            1,
            1,
        ),
        (
            "foreign",
            "integrity runner emitted an outcome outside its selection",
            0,
            0,
        ),
        (
            "emitted-uncompleted",
            "integrity runner completion must match its emitted outcomes",
            1,
            0,
        ),
        (
            "completed-unemitted",
            "integrity runner completion must match its emitted outcomes",
            0,
            1,
        ),
    ),
)
def test_integrity_rejects_outcome_custody_mismatch(
    tmp_path: Path,
    mismatch: str,
    expected_message: str,
    expected_items: int,
    expected_completed: int,
) -> None:
    prepared, inventory_deps = _seeded_integrity_case(tmp_path)
    selections: list[IntegritySelection] = []
    emitted: list[object] = []

    def runner(selection, verifier_context, _recorder):
        item = selection.pending[0]
        outcome = _integrity_outcome(item)
        if mismatch == "foreign":
            verifier_context.run.emit(
                replace(outcome, item_id="foreign-selection-item")
            )
            raise AssertionError("foreign outcome was accepted")
        if mismatch == "completed-unemitted":
            selection.mark_completed(item.item_id, 0)
            return IntegrityRunResult((), RecordingStatus.OK)
        verifier_context.run.emit(outcome)
        if mismatch == "emitted-uncompleted":
            return IntegrityRunResult((outcome,), RecordingStatus.OK)
        selection.mark_completed(item.item_id, 0)
        verifier_context.run.emit(outcome)
        raise AssertionError("duplicate outcome was accepted")

    result = run_integrity(
        IntegrityWorkflowRequest(
            f"custody-{mismatch}",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        RunContext(emitted.append, lambda: None),
        _integrity_dependencies(inventory_deps, runner),
        selection_sink=selections.append,
    )

    reliable = [body for body in emitted if isinstance(body, IntegrityOutcome)]
    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert len(reliable) == expected_items
    assert result.items == tuple(reliable)
    assert selections[0].completed_count == expected_completed
    assert result.error is not None
    assert (result.error.type_name, result.error.message) == (
        "ValueError",
        expected_message,
    )


@pytest.mark.parametrize(
    ("field_name", "accepted_changes", "returned_changes"),
    (
        (
            "result",
            {},
            {"result": IntegrityResult.BASELINED},
        ),
        (
            "reason",
            {
                "result": IntegrityResult.ERROR,
                "reason": IntegrityReason.READ_ERROR,
            },
            {"reason": IntegrityReason.RECORDING_ERROR},
        ),
        (
            "read_strategy",
            {"read_strategy": ReadStrategy.WINDOWS_UNBUFFERED},
            {"read_strategy": None},
        ),
        (
            "record_disposition",
            {"record_disposition": RecordDisposition.APPLIED},
            {"record_disposition": RecordDisposition.NOOP},
        ),
    ),
)
def test_integrity_returned_aggregate_cannot_replace_accepted_outcome(
    tmp_path: Path,
    field_name: str,
    accepted_changes: dict[str, object],
    returned_changes: dict[str, object],
) -> None:
    prepared, inventory_deps = _seeded_integrity_case(tmp_path)
    emitted: list[object] = []

    def runner(selection, verifier_context, _recorder):
        item = selection.pending[0]
        accepted = replace(_integrity_outcome(item), **accepted_changes)
        verifier_context.run.emit(accepted)
        selection.mark_completed(item.item_id, 0)
        returned = replace(accepted, **returned_changes)
        return IntegrityRunResult((returned,), RecordingStatus.OK)

    result = run_integrity(
        IntegrityWorkflowRequest(
            f"aggregate-{field_name}",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        RunContext(emitted.append, lambda: None),
        _integrity_dependencies(inventory_deps, runner),
    )

    reliable = [body for body in emitted if isinstance(body, IntegrityOutcome)]
    assert result.status is SessionState.FAILED
    assert result.items == tuple(reliable)
    assert len(result.items) == 1
    assert getattr(result.items[0], field_name) == getattr(
        reliable[0], field_name
    )
    assert getattr(result.items[0], field_name) != returned_changes[field_name]
    assert result.error is not None
    assert (result.error.type_name, result.error.message) == (
        "ValueError",
        "integrity runner outcomes must match emitted outcomes",
    )


def test_integrity_aggregate_cannot_erase_accepted_recording_degradation(
    tmp_path: Path,
) -> None:
    prepared, inventory_deps = _seeded_integrity_case(tmp_path)

    def runner(selection, verifier_context, _recorder):
        item = selection.pending[0]
        accepted = replace(
            _integrity_outcome(item),
            recording=RecordingStatus.DEGRADED,
            record_disposition=RecordDisposition.STALE,
        )
        verifier_context.run.emit(accepted)
        selection.mark_completed(item.item_id, 0)
        returned = replace(
            accepted,
            recording=RecordingStatus.OK,
            record_disposition=RecordDisposition.NOOP,
        )
        return IntegrityRunResult((returned,), RecordingStatus.OK)

    result = run_integrity(
        IntegrityWorkflowRequest(
            "aggregate-recording",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        _context(),
        _integrity_dependencies(inventory_deps, runner),
    )

    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert len(result.items) == 1
    assert result.items[0].recording is RecordingStatus.DEGRADED
    assert result.error is not None
    assert (result.error.type_name, result.error.message) == (
        "ValueError",
        "integrity runner outcomes must match emitted outcomes",
    )


def test_integrity_full_validator_call_profile_is_frozen_for_4p7(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = inventory_workflow.revalidate_integrity_selection_authority
    validation_widths: list[int] = []

    def observe_validation(selection, authority, *, allow_progress):
        validation_widths.append(len(authority.items))
        return original(
            selection,
            authority,
            allow_progress=allow_progress,
        )

    monkeypatch.setattr(
        inventory_workflow,
        "revalidate_integrity_selection_authority",
        observe_validation,
    )
    profiles: dict[int, tuple[int, ...]] = {}
    for item_count in (1, 4):
        validation_widths.clear()
        prepared, inventory_deps = _seeded_integrity_case(
            tmp_path / f"items-{item_count}",
            tuple(f"file-{index}.txt" for index in range(item_count)),
        )
        result = run_integrity(
            IntegrityWorkflowRequest(
                f"profile-{item_count}",
                prepared.binding,
                IntegrityMode.VERIFY,
            ),
            _context(),
            _integrity_dependencies(
                inventory_deps,
                _complete_integrity_selection,
            ),
        )
        assert result.status is SessionState.COMPLETED
        profiles[item_count] = tuple(validation_widths)

    # One terminal ownership-transfer audit is independent of population and
    # item/progress/checkpoint event count when there is no selection sink.
    assert profiles == {
        1: (1,),
        4: (4,),
    }


def test_integrity_invalid_aggregate_does_not_repeat_terminal_full_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = inventory_workflow.revalidate_integrity_selection_authority
    allow_progress_calls: list[bool] = []

    def observe_validation(selection, authority, *, allow_progress):
        allow_progress_calls.append(allow_progress)
        return original(
            selection,
            authority,
            allow_progress=allow_progress,
        )

    monkeypatch.setattr(
        inventory_workflow,
        "revalidate_integrity_selection_authority",
        observe_validation,
    )
    prepared, inventory_deps = _seeded_integrity_case(tmp_path)

    def runner(selection, verifier_context, _recorder):
        item = selection.pending[0]
        accepted = _integrity_outcome(item)
        verifier_context.run.emit(accepted)
        selection.mark_completed(item.item_id, 0)
        return IntegrityRunResult(
            (replace(accepted, result=IntegrityResult.BASELINED),),
            RecordingStatus.OK,
        )

    result = run_integrity(
        IntegrityWorkflowRequest(
            "invalid-aggregate-one-audit",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        _context(),
        _integrity_dependencies(inventory_deps, runner),
    )

    assert result.status is SessionState.FAILED
    assert result.error is not None
    assert (result.error.type_name, result.error.message) == (
        "ValueError",
        "integrity runner outcomes must match emitted outcomes",
    )
    assert allow_progress_calls == [True]


def test_integrity_uses_emitted_snapshot_when_returned_outcome_mutates(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    scanner = _Scanner(records=(_file(),))
    details: list[InventoryDetails] = []
    inventory_deps = _dependencies(
        tmp_path / "ledger.db", scanner, _Resolver(mount), details
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=inventory_deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=inventory_deps.resolver,
    )
    run_inventory(prepared, _context(), inventory_deps)

    def runner(selection, verifier_context, _recorder):
        item = selection.pending[0]
        outcome = IntegrityOutcome(
            item_id=item.item_id,
            row_id=item.row_id,
            location_id=item.location_id,
            path=item.display_path,
            result=IntegrityResult.VERIFIED,
            phase=IntegrityMode.VERIFY.value,
        )
        verifier_context.run.emit(outcome)
        selection.mark_completed(item.item_id, 0)
        object.__setattr__(outcome, "path", "invented.txt")
        return IntegrityRunResult((outcome,), RecordingStatus.OK)

    result = run_integrity(
        IntegrityWorkflowRequest(
            "hostile-result",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
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
            runners={IntegrityMode.VERIFY: runner},
        ),
    )

    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert len(result.items) == 1
    assert result.items[0].path == "file.txt"
    assert result.error is not None
    assert result.error.type_name == "ValueError"


def test_integrity_success_requires_every_pending_outcome(tmp_path: Path) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    scanner = _Scanner(records=(_file(),))
    details: list[InventoryDetails] = []
    inventory_deps = _dependencies(
        tmp_path / "ledger.db", scanner, _Resolver(mount), details
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=inventory_deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=inventory_deps.resolver,
    )
    run_inventory(prepared, _context(), inventory_deps)

    result = run_integrity(
        IntegrityWorkflowRequest(
            "missing-outcome",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
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

    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert result.items == ()
    assert result.error is not None
    assert result.error.type_name == "ValueError"
    assert result.error.message == "integrity runner returned with pending candidates"


@pytest.mark.parametrize(
    "error_type, expected_status, expected_canceled",
    [
        (Canceled, SessionState.CANCELED, True),
        (RuntimeError, SessionState.FAILED, False),
    ],
)
def test_integrity_terminal_control_uses_live_selection_authority(
    tmp_path: Path,
    error_type: type[Exception],
    expected_status: SessionState,
    expected_canceled: bool,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    scanner = _Scanner(records=(_file(),))
    details: list[InventoryDetails] = []
    inventory_deps = _dependencies(
        tmp_path / "ledger.db", scanner, _Resolver(mount), details
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=inventory_deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=inventory_deps.resolver,
    )
    run_inventory(prepared, _context(), inventory_deps)
    emitted: list[object] = []

    def runner(selection, verifier_context, _recorder):
        item = selection.pending[0]
        selection.note_bytes_processed(3)
        selection.advance_bytes_total_high_water(7)
        verifier_context.run.emit(
            Progress(
                phase=IntegrityMode.VERIFY.value,
                items_done=selection.completed_count,
                items_total=len(selection.items),
                bytes_done=selection.processed_bytes,
                bytes_total=7,
                current_path=item.display_path,
            )
        )
        outcome = IntegrityOutcome(
            item_id=item.item_id,
            row_id=item.row_id,
            location_id=item.location_id,
            path=item.display_path,
            result=IntegrityResult.VERIFIED,
            phase=IntegrityMode.VERIFY.value,
        )
        verifier_context.run.emit(outcome)
        selection.mark_completed(item.item_id, 3)
        raise error_type("runner stopped")

    result = run_integrity(
        IntegrityWorkflowRequest(
            "selection-authority",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        RunContext(emitted.append, lambda: None),
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
            runners={IntegrityMode.VERIFY: runner},
        ),
    )

    assert result.status is expected_status
    assert result.canceled is expected_canceled
    assert (result.bytes_done, result.bytes_total) == (3, 7)
    assert len(result.items) == 1
    assert [event.phase for event in emitted if isinstance(event, Progress)] == [
        IntegrityMode.VERIFY.value
    ]
    if expected_status is SessionState.FAILED:
        assert result.error is not None
        assert result.error.type_name == "RuntimeError"


def test_fresh_integrity_context_failure_retains_admitted_byte_total(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    scanner = _Scanner(records=(_file(),))
    details: list[InventoryDetails] = []
    inventory_deps = _dependencies(
        tmp_path / "ledger.db", scanner, _Resolver(mount), details
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=inventory_deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=inventory_deps.resolver,
    )
    run_inventory(prepared, _context(), inventory_deps)

    def fail_context(_context: RunContext) -> VerifierContext:
        raise RuntimeError("verifier context failed after admission")

    result = run_integrity(
        IntegrityWorkflowRequest(
            "fresh-context-failure",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        _context(),
        IntegrityDependencies(
            ledger_path=inventory_deps.ledger_path,
            scanner=inventory_deps.scanner,
            resolver=inventory_deps.resolver,
            clock=inventory_deps.clock,
            host_key=inventory_deps.host_key,
            host_name=inventory_deps.host_name,
            save_details=inventory_deps.save_details,
            verifier_context=fail_context,
            runners={
                IntegrityMode.VERIFY: lambda *_args: pytest.fail(
                    "runner started after context failure"
                )
            },
        ),
    )

    assert result.status is SessionState.FAILED
    assert (result.bytes_done, result.bytes_total) == (0, 7)
    assert result.error is not None
    assert result.error.type_name == "RuntimeError"


@pytest.mark.parametrize(
    "runner_exit, expected_status",
    [
        ("cancel", SessionState.CANCELED),
        ("pause", None),
        ("return", SessionState.FAILED),
    ],
)
def test_integrity_recorder_close_failure_preserves_primary_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner_exit: str,
    expected_status: SessionState | None,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    scanner = _Scanner(records=(_file(),))
    details: list[InventoryDetails] = []
    inventory_deps = _dependencies(
        tmp_path / "ledger.db", scanner, _Resolver(mount), details
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=inventory_deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=inventory_deps.resolver,
    )
    run_inventory(prepared, _context(), inventory_deps)

    original_close = inventory_workflow.LedgerRecorder.close
    close_message = "x" * 1_100 if runner_exit == "cancel" else "close failed"

    def failing_close(recorder) -> None:
        original_close(recorder)
        raise RuntimeError(close_message)

    monkeypatch.setattr(
        inventory_workflow.LedgerRecorder,
        "close",
        failing_close,
    )

    def runner(selection, _verifier_context, _recorder):
        selection.note_bytes_processed(3)
        selection.advance_bytes_total_high_water(7)
        if runner_exit == "cancel":
            raise Canceled("cancel wins")
        if runner_exit == "pause":
            raise PauseRequested("pause wins")
        return _complete_integrity_selection(
            selection,
            _verifier_context,
        )

    recording_observations: list[
        tuple[RecordingStatus, tuple[TaskRecordingIssue, ...], int]
    ] = []

    def invoke() -> OperationResult:
        return run_integrity(
            IntegrityWorkflowRequest(
                f"close-{runner_exit}",
                prepared.binding,
                IntegrityMode.VERIFY,
            ),
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
                runners={IntegrityMode.VERIFY: runner},
            ),
            recording_sink=lambda status, issues, omitted: (
                recording_observations.append((status, issues, omitted))
            ),
        )

    if runner_exit == "pause":
        with pytest.raises(PauseRequested, match="pause wins"):
            invoke()
        assert recording_observations == [
            (
                RecordingStatus.DEGRADED,
                (
                    TaskRecordingIssue(
                        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
                        "RuntimeError: close failed",
                    ),
                ),
                0,
            )
        ]
        return

    result = invoke()

    assert result.status is expected_status
    assert result.canceled is (runner_exit == "cancel")
    assert result.recording is RecordingStatus.DEGRADED
    assert (result.bytes_done, result.bytes_total) == (3, 7)
    assert result.recording_issues[0].reason is (
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED
    )
    if runner_exit == "cancel":
        assert result.recording_issues[0].detail is None
        assert result.omitted_detail_count == 1
    else:
        assert result.recording_issues[0].detail == "RuntimeError: close failed"
        assert result.omitted_detail_count == 0
    if runner_exit == "return":
        assert result.error is not None
        assert result.error.type_name == "RuntimeError"
        assert result.error.message == "close failed"


def test_inventory_source_first_excess_is_refused_without_partial_save(
    tmp_path: Path,
) -> None:
    class PrivateGraph:
        pass

    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    details: list[InventoryDetails] = []

    class ExcessScanner(_Scanner):
        def __init__(self) -> None:
            super().__init__()
            self.errors: list[BaseException] = []
            self.graph_references: list[ref[PrivateGraph]] = []

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
            del root, ignores, context, scope, trusted_anchor
            assert population_admission is not None
            graph = PrivateGraph()
            self.graph_references.append(ref(graph))
            try:
                population_admission.require_source_rows(
                    MAX_PLAN_REVIEW_ROWS + 1
                )
            except inventory_workflow._InventoryReviewLimitSignal as error:
                assert type(error) is (
                    inventory_workflow._InventoryReviewLimitSignal
                )
                self.errors.append(error)
                raise
            raise AssertionError("first excess was admitted")

    scanner = ExcessScanner()
    prepared = bind_inventory_request(
        InventoryRequest("inventory-excess", root_path=str(root)),
        ledger_path=ledger_path,
        backend=_Backend(root, mount),
        resolver=_Resolver(mount),
    )

    result = run_inventory(
        prepared,
        _context(),
        _dependencies(ledger_path, scanner, _Resolver(mount), details),
    )

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert result.review_fact_limit == ReviewFactLimitExceeded(
        "review_fact_limit_exceeded",
        ReviewTreeKind.INVENTORY,
        ReviewPopulation.DOMAIN,
        ReviewLimitAxis.ROWS,
        MAX_PLAN_REVIEW_ROWS,
        None,
    )
    assert scanner.errors
    assert result.review_fact_limit is not scanner.errors[0].fact
    assert BaseException.__dict__["__traceback__"].__get__(
        scanner.errors[0],
        type(scanner.errors[0]),
    ) is None
    assert BaseException.__dict__["__cause__"].__get__(
        scanner.errors[0],
        type(scanner.errors[0]),
    ) is None
    assert BaseException.__dict__["__context__"].__get__(
        scanner.errors[0],
        type(scanner.errors[0]),
    ) is None
    gc.collect()
    assert scanner.graph_references
    assert all(reference() is None for reference in scanner.graph_references)
    assert details == []
    with connect_ledger_reader(ledger_path) as connection:
        assert connection.execute("SELECT count(*) FROM hosts").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM inventory").fetchone()[0] == 0


@pytest.mark.parametrize("provenance", ("untagged", "different-run"))
def test_unadmitted_exact_inventory_signal_cannot_become_refusal(
    tmp_path: Path,
    provenance: str,
) -> None:
    class PrivateGraph:
        pass

    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    details: list[InventoryDetails] = []
    fact = ReviewFactLimitExceeded(
        "review_fact_limit_exceeded",
        ReviewTreeKind.INVENTORY,
        ReviewPopulation.DOMAIN,
        ReviewLimitAxis.ROWS,
        MAX_PLAN_REVIEW_ROWS,
        None,
    )
    if provenance == "untagged":
        raw_error = inventory_workflow._InventoryReviewLimitSignal(fact)
    else:
        different_run = inventory_workflow._InventoryScanAdmission()
        try:
            different_run.require_source_rows(MAX_PLAN_REVIEW_ROWS + 1)
        except inventory_workflow._InventoryReviewLimitSignal as error:
            raw_error = error
        else:
            raise AssertionError("different-run first excess was admitted")
    graph_references: list[ref[PrivateGraph]] = []

    class UnadmittedScanner(_Scanner):
        def __call__(self, *_args, **_kwargs):
            private = PrivateGraph()
            graph_references.append(ref(private))
            raise raw_error

    prepared = bind_inventory_request(
        InventoryRequest(f"inventory-{provenance}", root_path=str(root)),
        ledger_path=ledger_path,
        backend=_Backend(root, mount),
        resolver=_Resolver(mount),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "^unadmitted collaborator raised an inventory review fact limit$"
        ),
    ) as raised:
        run_inventory(
            prepared,
            _context(),
            _dependencies(
                ledger_path,
                UnadmittedScanner(),
                _Resolver(mount),
                details,
            ),
        )

    assert raised.value.__cause__ is raised.value.__context__ is None
    assert details == []
    assert BaseException.__dict__["__traceback__"].__get__(
        raw_error,
        type(raw_error),
    ) is None
    assert BaseException.__dict__["__cause__"].__get__(
        raw_error,
        type(raw_error),
    ) is None
    assert BaseException.__dict__["__context__"].__get__(
        raw_error,
        type(raw_error),
    ) is None
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    with connect_ledger_reader(ledger_path) as connection:
        assert connection.execute("SELECT count(*) FROM hosts").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM inventory").fetchone()[0] == 0


def test_inventory_wrong_scope_signal_fails_without_retained_context(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    details: list[InventoryDetails] = []
    raw_error = inventory_workflow._InventoryReviewLimitSignal(
        ReviewFactLimitExceeded.plan_domain_rows()
    )

    class WrongScopeScanner(_Scanner):
        def __call__(self, *_args, **_kwargs):
            raise raw_error

    prepared = bind_inventory_request(
        InventoryRequest("inventory-wrong-scope", root_path=str(root)),
        ledger_path=ledger_path,
        backend=_Backend(root, mount),
        resolver=_Resolver(mount),
    )

    with pytest.raises(
        RuntimeError,
        match="^inventory review limit failure is invalid$",
    ) as raised:
        run_inventory(
            prepared,
            _context(),
            _dependencies(
                ledger_path,
                WrongScopeScanner(),
                _Resolver(mount),
                details,
            ),
        )

    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert details == []
    assert BaseException.__dict__["__traceback__"].__get__(
        raw_error,
        type(raw_error),
    ) is None
    with connect_ledger_reader(ledger_path) as connection:
        assert connection.execute("SELECT count(*) FROM hosts").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM inventory").fetchone()[0] == 0


@pytest.mark.parametrize("kind", ("lookalike", "plan-signal"))
def test_non_inventory_signal_keeps_failure_identity(
    tmp_path: Path,
    kind: str,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    details: list[InventoryDetails] = []

    class InventoryLimitLookalike(ValueError):
        def __init__(self) -> None:
            super().__init__("review_fact_limit_exceeded")
            self.fact = ReviewFactLimitExceeded(
                "review_fact_limit_exceeded",
                ReviewTreeKind.INVENTORY,
                ReviewPopulation.DOMAIN,
                ReviewLimitAxis.ROWS,
                MAX_PLAN_REVIEW_ROWS,
                None,
            )

    raw_error = (
        InventoryLimitLookalike()
        if kind == "lookalike"
        else _PlanReviewLimitSignal(
            ReviewFactLimitExceeded.plan_domain_rows()
        )
    )

    class FailingScanner(_Scanner):
        def __call__(self, *_args, **_kwargs):
            raise raw_error

    prepared = bind_inventory_request(
        InventoryRequest(f"inventory-{kind}", root_path=str(root)),
        ledger_path=ledger_path,
        backend=_Backend(root, mount),
        resolver=_Resolver(mount),
    )

    with pytest.raises(type(raw_error)) as raised:
        run_inventory(
            prepared,
            _context(),
            _dependencies(
                ledger_path,
                FailingScanner(),
                _Resolver(mount),
                details,
            ),
        )

    assert raised.value is raw_error
    assert details == []


def test_exact_inventory_signal_from_details_callback_is_not_demoted(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    details: list[InventoryDetails] = []
    raw_error = inventory_workflow._InventoryReviewLimitSignal(
        ReviewFactLimitExceeded(
            "review_fact_limit_exceeded",
            ReviewTreeKind.INVENTORY,
            ReviewPopulation.DOMAIN,
            ReviewLimitAxis.ROWS,
            MAX_PLAN_REVIEW_ROWS,
            None,
        )
    )

    def save_details(_value: InventoryDetails) -> None:
        raise raw_error

    deps = replace(
        _dependencies(
            ledger_path,
            _Scanner(records=(_file(),)),
            _Resolver(mount),
            details,
        ),
        save_details=save_details,
    )
    prepared = bind_inventory_request(
        InventoryRequest("inventory-save-signal", root_path=str(root)),
        ledger_path=ledger_path,
        backend=_Backend(root, mount),
        resolver=_Resolver(mount),
    )

    with pytest.raises(
        inventory_workflow._InventoryReviewLimitSignal
    ) as raised:
        run_inventory(prepared, _context(), deps)

    assert raised.value is raw_error
    assert details == []


def test_inventory_revalidates_hostile_excess_result_before_ledger_publication(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    ledger_path = tmp_path / "ledger.db"
    details: list[InventoryDetails] = []
    record = _file()

    class IgnoringScanner(_Scanner):
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
            del ignores, context, trusted_anchor, population_admission
            return ScanResult(
                root,
                VOLUME_ID,
                EVIDENCE,
                PROFILE,
                (record,) * (MAX_PLAN_REVIEW_ROWS + 1),
                (),
                (),
                (),
                scope,
                True,
            )

    prepared = bind_inventory_request(
        InventoryRequest("hostile-inventory-excess", root_path=str(root)),
        ledger_path=ledger_path,
        backend=_Backend(root, mount),
        resolver=_Resolver(mount),
    )
    result = run_inventory(
        prepared,
        _context(),
        _dependencies(
            ledger_path,
            IgnoringScanner(),
            _Resolver(mount),
            details,
        ),
    )

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert result.review_fact_limit is not None
    assert details == []
    with connect_ledger_reader(ledger_path) as connection:
        assert connection.execute("SELECT count(*) FROM hosts").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM inventory").fetchone()[0] == 0


def test_post_refresh_integrity_candidate_excess_fails_without_verifier_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    details: list[InventoryDetails] = []
    inventory_deps = _dependencies(
        tmp_path / "ledger.db",
        _Scanner(records=(_file(),)),
        _Resolver(mount),
        details,
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=inventory_deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=inventory_deps.resolver,
    )
    run_inventory(prepared, _context(), inventory_deps)

    def excess(*_args, **_kwargs):
        raise IntegrityCandidateLimitError(IntegrityCandidateLimitExceeded.rows())

    monkeypatch.setattr(
        inventory_workflow.LedgerRepository,
        "get_integrity_candidates",
        excess,
    )
    selections: list[object] = []
    runner_calls: list[object] = []
    result = run_integrity(
        IntegrityWorkflowRequest(
            "candidate-excess",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        _context(),
        IntegrityDependencies(
            ledger_path=inventory_deps.ledger_path,
            scanner=inventory_deps.scanner,
            resolver=inventory_deps.resolver,
            clock=inventory_deps.clock,
            host_key=inventory_deps.host_key,
            host_name=inventory_deps.host_name,
            save_details=inventory_deps.save_details,
            verifier_context=lambda _context: pytest.fail(
                "verifier context constructed after candidate excess"
            ),
            runners={
                IntegrityMode.VERIFY: lambda *_args: runner_calls.append(object())
            },
        ),
        selection_sink=selections.append,
    )

    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert result.error is not None
    assert result.error.type_name == "IntegrityCandidateLimitExceeded"
    assert result.error.message == INTEGRITY_CANDIDATE_ROWS_MESSAGE
    assert result.items == ()
    assert selections == []
    assert runner_calls == []
    assert details[-1].observed_count == 1


def test_recorder_finalization_failure_precedes_candidate_excess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    details: list[InventoryDetails] = []
    inventory_deps = _dependencies(
        tmp_path / "ledger.db",
        _Scanner(records=(_file(),)),
        _Resolver(mount),
        details,
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=inventory_deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=inventory_deps.resolver,
    )
    run_inventory(prepared, _context(), inventory_deps)
    original_close = inventory_workflow.LedgerRecorder.close

    def excess(*_args, **_kwargs):
        raise IntegrityCandidateLimitError(IntegrityCandidateLimitExceeded.rows())

    def failing_close(recorder) -> None:
        original_close(recorder)
        raise RuntimeError("candidate recorder close failed")

    monkeypatch.setattr(
        inventory_workflow.LedgerRepository,
        "get_integrity_candidates",
        excess,
    )
    monkeypatch.setattr(inventory_workflow.LedgerRecorder, "close", failing_close)

    result = run_integrity(
        IntegrityWorkflowRequest(
            "candidate-close-failure",
            prepared.binding,
            IntegrityMode.VERIFY,
        ),
        _context(),
        IntegrityDependencies(
            ledger_path=inventory_deps.ledger_path,
            scanner=inventory_deps.scanner,
            resolver=inventory_deps.resolver,
            clock=inventory_deps.clock,
            host_key=inventory_deps.host_key,
            host_name=inventory_deps.host_name,
            save_details=inventory_deps.save_details,
        ),
    )

    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert result.recording is RecordingStatus.DEGRADED
    assert result.error is not None
    assert result.error.type_name == "RuntimeError"
    assert result.error.message == "candidate recorder close failed"
    assert result.recording_issues == (
        TaskRecordingIssue(
            TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
            "RuntimeError: candidate recorder close failed",
        ),
    )


def test_recording_failure_uses_one_exception_render_for_both_projections() -> None:
    class AlternatingError(RuntimeError):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def __str__(self) -> str:
            self.calls += 1
            if self.calls > 1:
                raise AssertionError("recording failure rendered more than once")
            return "one observation"

    error = AlternatingError()
    observed = inventory_workflow._task_recording_issue(
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
        error,
    )

    assert error.calls == 1
    assert observed.issue == TaskRecordingIssue(
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
        "AlternatingError: one observation",
    )
    assert observed.failure.type_name == "AlternatingError"
    assert observed.failure.message == "one observation"


@pytest.mark.parametrize(
    "error, expected_status, expected_canceled",
    [
        (Canceled("stop before selection rebuild"), SessionState.CANCELED, True),
        (PermissionError("recorder unavailable"), SessionState.FAILED, False),
    ],
)
def test_resumed_integrity_setup_failure_uses_request_high_water(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_status: SessionState,
    expected_canceled: bool,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    scanner = _Scanner(records=(_file(),))
    details: list[InventoryDetails] = []
    inventory_deps = _dependencies(
        tmp_path / "ledger.db", scanner, _Resolver(mount), details
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=inventory_deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=inventory_deps.resolver,
    )
    emitted: list[object] = []

    def fail_recorder(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(inventory_workflow, "LedgerRecorder", fail_recorder)
    result = run_integrity(
        IntegrityWorkflowRequest(
            "resumed-setup",
            prepared.binding,
            IntegrityMode.VERIFY,
            selection_item_ids=("1:a",),
            processed_bytes=7,
            bytes_total_high_water=19,
            refresh_generation=1,
        ),
        RunContext(emitted.append, lambda: None),
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
                IntegrityMode.VERIFY: lambda *_args: pytest.fail(
                    "runner reopened after setup failure"
                )
            },
        ),
    )

    assert result.status is expected_status
    assert result.canceled is expected_canceled
    assert result.recording is RecordingStatus.DEGRADED
    assert (result.bytes_done, result.bytes_total) == (7, 19)
    assert emitted == []
    if expected_status is SessionState.FAILED:
        assert result.error is not None
        assert result.error.type_name == "PermissionError"


def test_paused_integrity_cancellation_uses_persisted_total_high_water() -> None:
    request = IntegrityWorkflowRequest(
        "paused",
        LocationBinding(
            VOLUME_ID,
            "managed",
            "M:",
            ("M:",),
            False,
        ),
        IntegrityMode.BASELINE,
        selection_item_ids=("1:a", "1:b"),
        completed_bytes=(("1:a", 7),),
        processed_bytes=11,
        bytes_total_high_water=23,
        recording=RecordingStatus.DEGRADED,
        omitted_detail_count=2,
        refresh_generation=1,
    )

    result = settle_canceled_integrity(request, Disposition.RAN)

    assert result.status is SessionState.CANCELED
    assert result.canceled is True
    assert result.disposition is Disposition.RAN
    assert result.recording is RecordingStatus.DEGRADED
    assert (result.bytes_done, result.bytes_total) == (11, 23)
    assert result.omitted_detail_count == 2
    with pytest.raises(ValueError, match="retain RAN"):
        settle_canceled_integrity(request, Disposition.UNRUN)


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
                runners={IntegrityMode.VERIFY: _complete_integrity_selection},
        ),
    )

    assert resumed.status is SessionState.COMPLETED
    assert len(scanner.calls) == 3


def test_saved_integrity_selection_uses_only_frozen_row_ids(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    scanner = _Scanner(records=(_file("a.txt"), _file("b.txt")))
    details: list[InventoryDetails] = []
    deps = _dependencies(
        tmp_path / "ledger.db", scanner, _Resolver(mount), details
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=deps.resolver,
    )
    run_inventory(prepared, _context(), deps)
    location_id = details[-1].location_id
    assert location_id is not None
    with LedgerRepository(deps.ledger_path) as repository:
        rows = repository.get_inventory(location_id)
    by_path = {row.rel_path: row for row in rows}
    with LedgerRepository(deps.ledger_path) as repository:
        for row_id in ("01", "abc"):
            with pytest.raises(RuntimeError, match="missing inventory rows"):
                inventory_workflow._integrity_rows(
                    repository,
                    location_id,
                    IntegrityMode.VERIFY,
                    (),
                    None,
                    (f"{location_id}:{row_id}",),
                    frozenset(),
                )
    frozen = (
        f"{location_id}:{by_path['b.txt'].row_id}",
        f"{location_id}:{by_path['a.txt'].row_id}",
    )
    repository = _IntegrityRepositorySpy(rows)

    selected = inventory_workflow._integrity_rows(
        repository,
        location_id,
        IntegrityMode.VERIFY,
        (),
        None,
        frozen,
        frozenset(),
    )

    assert tuple(row.rel_path for row in selected) == ("b.txt", "a.txt")
    assert repository.row_id_calls == [
        (
            location_id,
            (by_path["b.txt"].row_id, by_path["a.txt"].row_id),
        )
    ]
    selection = inventory_workflow._integrity_selection(
        IntegrityWorkflowRequest(
            "shared-root",
            prepared.binding,
            IntegrityMode.VERIFY,
            selection_item_ids=frozen,
        ),
        selected,
        str(root),
    )
    assert selection.items[0].root is selection.items[1].root

    with pytest.raises(RuntimeError, match="missing inventory rows"):
        inventory_workflow._integrity_rows(
            repository,
            location_id,
            IntegrityMode.VERIFY,
            (),
            None,
            (f"{location_id}:999999",),
            frozenset(),
        )
    with pytest.raises(RuntimeError, match="another inventory location"):
        inventory_workflow._integrity_rows(
            repository,
            location_id,
            IntegrityMode.VERIFY,
            (),
            None,
            (f"{location_id + 1}:{by_path['a.txt'].row_id}",),
            frozenset(),
        )


def test_stale_integrity_selection_never_materializes_full_inventory(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    scanner = _Scanner(
        records=(_file("a.txt"), _file("b.txt"), _file("c.txt"))
    )
    details: list[InventoryDetails] = []
    deps = _dependencies(
        tmp_path / "ledger.db", scanner, _Resolver(mount), details
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=deps.resolver,
    )
    run_inventory(prepared, _context(), deps)
    location_id = details[-1].location_id
    assert location_id is not None
    with LedgerRepository(deps.ledger_path) as ledger:
        rows = ledger.get_inventory(location_id)
    by_path = {row.rel_path: row for row in rows}
    stale_before = datetime(2027, 1, 1, tzinfo=timezone.utc)
    repository = _IntegrityRepositorySpy(
        rows,
        stale=(by_path["a.txt"], by_path["c.txt"]),
    )
    completed_id = f"{location_id}:{by_path['b.txt'].row_id}"

    selected = inventory_workflow._integrity_rows(
        repository,
        location_id,
        IntegrityMode.VERIFY,
        (),
        stale_before,
        (),
        frozenset((completed_id,)),
    )

    assert tuple(row.rel_path for row in selected) == (
        "a.txt",
        "b.txt",
        "c.txt",
    )
    assert repository.stale_calls == [(location_id, stale_before)]
    assert repository.row_id_calls == [
        (location_id, (by_path["b.txt"].row_id,))
    ]


@pytest.mark.parametrize(
    ("mode", "expected_path"),
    [
        (IntegrityMode.BASELINE, "a.txt"),
        (IntegrityMode.REBASELINE, "b.txt"),
    ],
)
def test_stale_integrity_selection_preserves_mode_filtering(
    tmp_path: Path,
    mode: IntegrityMode,
    expected_path: str,
) -> None:
    mount = tmp_path / "mount"
    root = mount / "managed"
    root.mkdir(parents=True)
    scanner = _Scanner(records=(_file("a.txt"), _file("b.txt")))
    details: list[InventoryDetails] = []
    deps = _dependencies(
        tmp_path / "ledger.db", scanner, _Resolver(mount), details
    )
    prepared = bind_inventory_request(
        InventoryRequest("seed", root_path=str(root)),
        ledger_path=deps.ledger_path,
        backend=_Backend(root, mount),
        resolver=deps.resolver,
    )
    run_inventory(prepared, _context(), deps)
    location_id = details[-1].location_id
    assert location_id is not None
    with LedgerRepository(deps.ledger_path) as ledger:
        rows = ledger.get_inventory(location_id)
    by_path = {row.rel_path: row for row in rows}
    observed = by_path["b.txt"].observed
    assert observed is not None
    stale = (
        by_path["a.txt"],
        replace(by_path["b.txt"], attestation=attestation(observed)),
    )
    repository = _IntegrityRepositorySpy(stale, stale=stale)

    selected = inventory_workflow._integrity_rows(
        repository,
        location_id,
        mode,
        (),
        datetime(2027, 1, 1, tzinfo=timezone.utc),
        (),
        frozenset(),
    )

    assert tuple(row.rel_path for row in selected) == (expected_path,)


@pytest.mark.parametrize("kind", ("inventory", "integrity"))
@pytest.mark.parametrize("text", ("\ud800", "\udcff", "\ud83d\ude00"))
def test_inventory_workflow_request_rejects_surrogate_code_units(
    kind: str, text: str
) -> None:
    binding = LocationBinding(VOLUME_ID, "managed", "M:\\", ("M:\\",), False, 7)
    with pytest.raises(ValueError, match="valid Unicode"):
        if kind == "inventory":
            InventoryWorkflowRequest("request-" + text, binding)
        else:
            IntegrityWorkflowRequest(
                "request-" + text,
                binding,
                IntegrityMode.VERIFY,
            )


def test_integrity_checkpoint_enforces_recording_relationships() -> None:
    binding = LocationBinding(VOLUME_ID, "managed", "M:\\", ("M:\\",), False, 7)
    issue = TaskRecordingIssue(
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
        None,
    )

    with pytest.raises(ValueError, match="require degraded status"):
        IntegrityWorkflowRequest(
            "integrity-recording",
            binding,
            IntegrityMode.VERIFY,
            recording_issues=(issue,),
        )
    with pytest.raises(ValueError, match="reasons must be unique"):
        IntegrityWorkflowRequest(
            "integrity-recording",
            binding,
            IntegrityMode.VERIFY,
            recording=RecordingStatus.DEGRADED,
            recording_issues=(issue, issue),
        )
    for recording in (1, "unknown", None, IntegrityMode.VERIFY):
        with pytest.raises(TypeError, match="recording status"):
            IntegrityWorkflowRequest(
                "integrity-recording",
                binding,
                IntegrityMode.VERIFY,
                recording=recording,  # type: ignore[arg-type]
            )
    for recording_issues in ([issue], (object(),), (None,)):
        with pytest.raises(TypeError, match="recording issues"):
            IntegrityWorkflowRequest(
                "integrity-recording",
                binding,
                IntegrityMode.VERIFY,
                recording=RecordingStatus.DEGRADED,
                recording_issues=recording_issues,  # type: ignore[arg-type]
            )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("completed_bytes", (("7:11", True),)),
        ("processed_bytes", True),
        ("bytes_total_high_water", True),
        ("omitted_detail_count", True),
        ("refresh_generation", True),
    ],
)
def test_integrity_request_rejects_boolean_counters(
    field: str,
    value: object,
) -> None:
    fields: dict[str, object] = {
        "request_id": "integrity-bool-counter",
        "binding": LocationBinding(
            VOLUME_ID,
            "managed",
            "M:\\",
            ("M:\\",),
            False,
            7,
        ),
        "mode": IntegrityMode.VERIFY,
        "selection_item_ids": ("7:11",),
    }
    fields[field] = value

    with pytest.raises(TypeError):
        IntegrityWorkflowRequest(**fields)  # type: ignore[arg-type]


def test_integrity_request_rejects_non_integer_counter_types() -> None:
    binding = LocationBinding(VOLUME_ID, "managed", "M:\\", ("M:\\",), False, 7)
    for invalid in (1.5, "1", None):
        for field in (
            "completed_bytes",
            "processed_bytes",
            "bytes_total_high_water",
            "omitted_detail_count",
            "refresh_generation",
        ):
            fields: dict[str, object] = {
                "request_id": "integrity-counter-type",
                "binding": binding,
                "mode": IntegrityMode.VERIFY,
                "selection_item_ids": ("7:11",),
            }
            fields[field] = (
                (("7:11", invalid),)
                if field == "completed_bytes"
                else invalid
            )
            with pytest.raises(TypeError):
                IntegrityWorkflowRequest(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("completed_bytes", (("7:11", MAX_SIGNED_64 + 1),)),
        ("processed_bytes", MAX_SIGNED_64 + 1),
        ("bytes_total_high_water", MAX_SIGNED_64 + 1),
        ("omitted_detail_count", MAX_SAFE_INTEGER + 1),
        ("refresh_generation", MAX_SAFE_INTEGER + 1),
    ],
)
def test_integrity_request_rejects_out_of_domain_counters(
    field: str,
    value: object,
) -> None:
    fields: dict[str, object] = {
        "request_id": "integrity-counter-domain",
        "binding": LocationBinding(
            VOLUME_ID,
            "managed",
            "M:\\",
            ("M:\\",),
            False,
            7,
        ),
        "mode": IntegrityMode.VERIFY,
        "selection_item_ids": ("7:11",),
    }
    fields[field] = value

    with pytest.raises(ValueError):
        IntegrityWorkflowRequest(**fields)  # type: ignore[arg-type]


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
    with pytest.raises(ValueError, match="cannot trail processed"):
        IntegrityWorkflowRequest(
            request_id="integrity-trailing-high-water",
            binding=binding,
            mode=IntegrityMode.VERIFY,
            selection_item_ids=("7:11",),
            processed_bytes=13,
            bytes_total_high_water=12,
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
    assert valid.refresh_generation == 1
