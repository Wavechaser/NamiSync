from __future__ import annotations

import gc
import os
import stat as stat_module
from dataclasses import fields, replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from weakref import ref

import pytest

import namisync.workflows.sync as sync_workflow
import namisync.workflows.runtime as runtime_module
import namisync.core.review as review_module
from namisync.core.events import ItemOutcome
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.execution import Commitment, ExecutionSet, validated_run_id
from namisync.core.integrity import PostCopySelection
from namisync.core.models import (
    CapabilityProfile,
    FileIdentity,
    FileRecord,
    MetadataSnapshot,
    Root,
    ScanResult,
    ScanScope,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import to_extended_length_path
from namisync.core.planning import (
    Assignment,
    BlockedReason,
    DeletionPolicy,
    FilterSet,
    IdentityDestinationPolicy,
    MappingSnapshot,
    OpId,
    OperationKind,
    OperationReason,
    Plan,
    PlanFingerprint,
    PlanOperation,
    PreservationPolicy,
    SyncOptions,
    plan_fingerprint,
    selection_digest,
)
from namisync.db.connections import connect_ledger_reader
from namisync.core.session import (
    Canceled,
    Disposition,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    RunContext,
    SessionState,
)
from namisync.core.preflight import ObservedWorld, Refusal, RefusalCode, Verdict
from namisync.core.root_authority import RootAuthorityError, RootAuthorityIssue
from namisync.workflows.selection import ExclusionReason, derive_execution_selection
from namisync.workflows.sync import run_execution, validate_sync_paths
from namisync.workflows.models import (
    ExecuteContinuation,
    PlanArtifact,
    PlanRequest,
    VerifyContinuation,
)
from namisync.workflows.runtime import LocalWorkflowRuntime
from namisync.workflows.inventory import LocationBinding, LocationCandidate
from namisync.workflows.views import (
    PreservationSettingsView,
    SemanticSettingsPatchView,
    SetupOptionsView,
)


NOW = datetime(2026, 7, 19, tzinfo=timezone.utc)


@pytest.mark.parametrize("persisted_defaults", (False, True))
def test_prepare_setup_options_canonicalizes_task_snapshot_without_settings_write(
    tmp_path: Path,
    persisted_defaults: bool,
) -> None:
    runtime = LocalWorkflowRuntime(tmp_path / "ledger.db", tmp_path / "history.db")
    try:
        if persisted_defaults:
            runtime.commit_semantic_settings(
                SemanticSettingsPatchView(deletion_policy="additive")
            )
        assert runtime.settings_path.exists() is persisted_defaults
        original_bytes = runtime.settings_path.read_bytes() if persisted_defaults else None
        original_mtime = runtime.settings_path.stat().st_mtime_ns if persisted_defaults else None
        before = runtime.read_semantic_settings()
        prepared = runtime.prepare_setup_options(
            SetupOptionsView(
                ("b\\*", "a/*", "b/*"), "trash", True,
                PreservationSettingsView(False, True, True), True, True,
            )
        )
        assert prepared.filters == ("a\\*", "b\\*")
        assert prepared.preservation == PreservationSettingsView(False, True, True)
        assert prepared.verify_after_execute is True
        assert runtime.read_semantic_settings() == before
        assert runtime.settings_path.exists() is persisted_defaults
        if persisted_defaults:
            assert runtime.settings_path.read_bytes() == original_bytes
            assert runtime.settings_path.stat().st_mtime_ns == original_mtime
        with pytest.raises(ValueError, match="does not support ADS"):
            runtime.prepare_setup_options(
                SetupOptionsView(
                    (), "trash", False,
                    PreservationSettingsView(True, False, False), False, False,
                )
            )
    finally:
        runtime.close()


def _empty_world() -> ObservedWorld:
    return ObservedWorld({}, {}, frozenset({""}), {}, None, 0, None, NOW)


def test_plan_domain_contracts_have_no_worker_count() -> None:
    assert "worker_count" not in {field.name for field in fields(SyncOptions)}
    assert "worker_count" not in {field.name for field in fields(Plan)}
    with pytest.raises(TypeError):
        SyncOptions(worker_count=2)  # type: ignore[call-arg]


def test_prepare_plan_rejects_noncanonical_domain_values(tmp_path: Path) -> None:
    class DerivedPlanRequest(PlanRequest):
        pass

    class DerivedSyncOptions(SyncOptions):
        pass

    class OtherPolicy:
        name = "identity"
        version = "1"

        def assign(self, records, meta, target):
            raise AssertionError("rejected policy callback ran")

    def request_with(policy: object) -> PlanRequest:
        return PlanRequest(
            "request",
            r"C:\source",
            r"D:\target",
            SyncOptions(destination_policy=policy),  # type: ignore[arg-type]
        )

    runtime = LocalWorkflowRuntime(tmp_path / "ledger.db", tmp_path / "history.db")
    try:
        for request, error, message in (
            (
                DerivedPlanRequest("request", r"C:\source", r"D:\target"),
                TypeError,
                "requires PlanRequest",
            ),
            (
                PlanRequest(
                    "request", r"C:\source", r"D:\target", DerivedSyncOptions()
                ),
                TypeError,
                "exact SyncOptions",
            ),
            (
                request_with(IdentityDestinationPolicy("renamed", "1")),
                ValueError,
                "fields changed",
            ),
            (
                request_with(IdentityDestinationPolicy("identity", "2")),
                ValueError,
                "fields changed",
            ),
            (
                request_with(OtherPolicy()),
                ValueError,
                "supports only the identity policy",
            ),
        ):
            with pytest.raises(error, match=message):
                runtime.prepare_plan(request)
    finally:
        runtime.close()


def test_prepare_plan_retains_a_detached_identity_checkpoint(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    policy = IdentityDestinationPolicy()
    options = SyncOptions(destination_policy=policy)
    request = PlanRequest("1" * 32, str(source), str(target), options)
    runtime = LocalWorkflowRuntime(tmp_path / "ledger.db", tmp_path / "history.db")
    try:
        checkpoint = runtime.prepare_plan(request).checkpoint

        assert type(checkpoint) is PlanRequest
        assert checkpoint is not request
        assert type(checkpoint.options) is SyncOptions
        assert checkpoint.options is not options
        assert (
            type(checkpoint.options.destination_policy)
            is IdentityDestinationPolicy
        )
        assert checkpoint.options.destination_policy is not policy

        object.__setattr__(policy, "name", "changed")
        object.__setattr__(options, "trash_on_update", False)
        object.__setattr__(request, "request_id", "2" * 32)
        object.__setattr__(request, "source_path", str(tmp_path / "changed"))

        assert checkpoint.request_id == "1" * 32
        assert checkpoint.source_path == str(source)
        assert checkpoint.options.trash_on_update is True
        assert checkpoint.options.destination_policy == IdentityDestinationPolicy()
        result = runtime.open_plan(checkpoint).run(
            RunContext(lambda _event: None, lambda: None)
        )
        assert result.status is SessionState.COMPLETED
    finally:
        runtime.close()


@pytest.mark.parametrize("changed_volume", (False, True))
def test_plan_publication_requires_the_admitted_volume_bindings(
    tmp_path: Path,
    changed_volume: bool,
) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    runtime = LocalWorkflowRuntime(tmp_path / "ledger.db", tmp_path / "history.db")
    try:
        source_binding = runtime.admit_location_candidate(
            LocationCandidate.literal(str(source))
        ).binding
        target_binding = runtime.admit_location_candidate(
            LocationCandidate.literal(str(target))
        ).binding
        assert source_binding is not None and target_binding is not None
        request = PlanRequest(
            "c" * 32, str(source), str(target), SyncOptions(),
            source_binding, target_binding, True,
        )
        checkpoint = runtime.prepare_plan(request).checkpoint
        assert checkpoint.source_binding == source_binding
        assert checkpoint.target_binding == target_binding
        assert checkpoint.verify_after_execute is True
        original_scanner = runtime._deps.scanner
        scanned: list[str] = []

        def scan(*args, **kwargs):
            observed = original_scanner(*args, **kwargs)
            scanned.append(observed.root.path)
            if changed_volume and observed.root.path == str(source):
                assert observed.volume_id is not None
                assert observed.volume_id.serial != "replacement-volume"
                observed = replace(
                    observed,
                    volume_id=VolumeId(
                        "replacement-volume", observed.volume_id.fs_type
                    ),
                )
            return observed

        runtime._deps = replace(runtime._deps, scanner=scan)
        if changed_volume:
            runtime._deps = replace(
                runtime._deps,
                planner=lambda *_args, **_kwargs: pytest.fail(
                    "changed reviewed volume reached planning"
                ),
            )
            with pytest.raises(ValueError, match="changed reviewed location identity"):
                runtime.open_plan(checkpoint).run(
                    RunContext(lambda _event: None, lambda: None)
                )
            assert scanned == [str(source), str(target)]
            with pytest.raises(KeyError):
                runtime.get_plan(request.request_id)
        else:
            result = runtime.open_plan(checkpoint).run(
                RunContext(lambda _event: None, lambda: None)
            )
            assert result.status is SessionState.COMPLETED
            retained = runtime.get_plan(request.request_id).request
            assert retained.source_binding == source_binding
            assert retained.target_binding == target_binding
            assert retained.verify_after_execute is True
    finally:
        runtime.close()


@pytest.mark.parametrize("case", (
    "source-only", "target-only", "integer-verify", "null-verify", "wrong-binding",
))
def test_direct_plan_rejects_incomplete_setup_contract_before_scanning(case: str) -> None:
    binding = LocationBinding(VolumeId("source", "NTFS"), "source", "C:\\", ("C:\\",), False)
    request = PlanRequest(
        "d" * 32, r"C:\source", r"D:\target", SyncOptions(),
        object() if case == "wrong-binding" else binding if case == "source-only" else None,
        binding if case in {"target-only", "wrong-binding"} else None,
        1 if case == "integer-verify" else None if case == "null-verify" else False,
    )

    def unreachable(*_args, **_kwargs):
        pytest.fail("invalid Setup request reached scan or artifact publication")

    error = ValueError if case.endswith("only") else TypeError
    message = (
        "bindings must be paired" if case.endswith("only")
        else "binding must be exact" if case == "wrong-binding"
        else "verify_after_execute"
    )
    with pytest.raises(error, match=message):
        sync_workflow.run_plan(
            request,
            RunContext(unreachable, lambda: None),
            SimpleNamespace(scanner=unreachable, save_plan=unreachable),
        )


class _PrivatePathFrameValue:
    pass


def test_runtime_derives_correspondence_bounds_only_from_current_file_scans(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_volume = VolumeId("source-serial", "NTFS")
    target_volume = VolumeId("target-serial", "NTFS")
    profile = CapabilityProfile("NTFS", 100, True, False, 32_767, True, True)

    def record(path: str, identity: FileIdentity | None) -> FileRecord:
        return FileRecord(
            path,
            path.upper(),
            1,
            2,
            identity,
            1,
            MetadataSnapshot(0, None),
        )

    source = ScanResult(
        Root(r"C:\source", "source"),
        source_volume,
        VolumeEvidence("source", "C:\\"),
        profile,
        (
            record("renamed.bin", FileIdentity("source-serial", 11)),
            record("identityless.bin", None),
        ),
        (),
        (),
        (),
        ScanScope.full(),
        True,
    )
    target = ScanResult(
        Root(r"D:\target", "target"),
        target_volume,
        VolumeEvidence("target", "D:\\"),
        profile,
        (
            record("old.bin", FileIdentity("target-serial", 21)),
            record("identityless.bin", None),
        ),
        (),
        (),
        (),
        ScanScope.full(),
        True,
    )
    expected = MappingSnapshot.empty(source_volume, target_volume)
    observed: list[tuple[object, ...]] = []

    class Repository:
        def __init__(self, path: Path) -> None:
            observed.append(("open", Path(path)))

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def find_mapping(self, *args, **kwargs):
            raise AssertionError("runtime used the unbounded mapping reader")

        def find_current_mapping(self, *args, **kwargs):
            observed.append((args, kwargs))
            return SimpleNamespace(snapshot=expected)

    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    runtime.ledger_path.write_bytes(b"present")
    monkeypatch.setattr(runtime_module, "LedgerRepository", Repository)
    try:
        assert runtime._correspondence(source, target) is expected
    finally:
        runtime.close()

    assert observed[1] == (
        (source_volume, "source", target_volume, "target"),
        {
            "target_path_keys": ("OLD.BIN", "IDENTITYLESS.BIN"),
            "source_identities": frozenset(
                {FileIdentity("source-serial", 11)}
            ),
            "target_identities": frozenset(
                {FileIdentity("target-serial", 21)}
            ),
        },
    )


def test_sync_path_validation_refuses_a_final_root_reparse_without_following_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    original_stat = os.stat

    def no_follow_stat(path, *args, **kwargs):
        if (
            str(path).endswith(str(source))
            and kwargs.get("follow_symlinks") is False
        ):
            return SimpleNamespace(
                st_mode=stat_module.S_IFDIR | 0o755,
                st_file_attributes=0x00000400,
                st_reparse_tag=1,
            )
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", no_follow_stat)

    with pytest.raises(ValueError, match="ordinary directory"):
        validate_sync_paths(str(source), str(target))


def test_sync_path_validation_stops_at_an_intermediate_root_reparse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "source-parent"
    source = parent / "source"
    target = tmp_path / "target"
    source.mkdir(parents=True)
    target.mkdir()
    native_parent = to_extended_length_path(str(parent))
    native_source = to_extended_length_path(str(source))
    original_stat = os.stat

    def no_follow_stat(path, *args, **kwargs):
        if (
            str(path) == native_parent
            and kwargs.get("follow_symlinks") is False
        ):
            return SimpleNamespace(
                st_mode=stat_module.S_IFDIR | 0o755,
                st_file_attributes=0x00000400,
                st_reparse_tag=1,
            )
        if (
            str(path) == native_source
            and kwargs.get("follow_symlinks") is False
        ):
            raise AssertionError(
                "sync admission probed through an intermediate reparse"
            )
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", no_follow_stat)

    with pytest.raises(ValueError, match="root chain"):
        validate_sync_paths(str(source), str(target))


def test_sync_path_validation_uses_physical_paths_only_for_overlap_judgment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source-alias"
    target = tmp_path / "target-alias"
    source.mkdir()
    target.mkdir()
    physical = tmp_path / "physical"

    monkeypatch.setattr(
        sync_workflow,
        "_physical_logical_root",
        lambda path: (
            physical
            if path == source
            else physical / "nested-target"
        ),
    )

    with pytest.raises(ValueError, match="non-nested"):
        validate_sync_paths(str(source), str(target))


def test_sync_path_validation_admits_both_roots_before_physical_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    calls: list[tuple[str, str]] = []

    def admit(authority, *, anchor_probe) -> str:
        assert anchor_probe is sync_workflow.current_volume_anchor
        calls.append(("chain", authority.logical_root))
        return tmp_path.anchor

    def physical(path: Path) -> Path:
        calls.append(("physical", str(path)))
        return path

    monkeypatch.setattr(sync_workflow, "admit_root_chain", admit)
    monkeypatch.setattr(sync_workflow, "_physical_logical_root", physical)

    assert validate_sync_paths(str(source), str(target)) == (source, target)
    assert calls == [
        ("chain", str(source)),
        ("chain", str(target)),
        ("physical", str(source)),
        ("physical", str(target)),
    ]


def test_sync_path_validation_retires_root_authority_exception_frames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    failure = RootAuthorityError(
        RootAuthorityIssue.ANCHOR_UNAVAILABLE,
        str(source),
        "root authority unavailable",
    )
    cause = OSError("anchor probe failed")
    references: list[ref[_PrivatePathFrameValue]] = []

    def fail_admission(*args: object, **kwargs: object) -> None:
        del args, kwargs
        private = _PrivatePathFrameValue()
        references.append(ref(private))
        try:
            raise cause
        except OSError:
            raise failure from cause

    monkeypatch.setattr(sync_workflow, "admit_root_chain", fail_admission)

    with pytest.raises(ValueError, match="^anchor probe failed$") as raised:
        validate_sync_paths(str(source), str(target))

    assert raised.value.__cause__ is raised.value.__context__ is None
    gc.collect()
    assert references and all(reference() is None for reference in references)


def test_sync_path_validation_retires_physical_resolution_frames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    failure = OSError("physical resolution failed")
    references: list[ref[_PrivatePathFrameValue]] = []

    monkeypatch.setattr(
        sync_workflow,
        "admit_root_chain",
        lambda *args, **kwargs: None,
    )

    def fail_resolution(*args: object, **kwargs: object) -> None:
        del args, kwargs
        private = _PrivatePathFrameValue()
        references.append(ref(private))
        raise failure

    monkeypatch.setattr(Path, "resolve", fail_resolution)

    with pytest.raises(ValueError, match="^physical resolution failed$") as raised:
        validate_sync_paths(str(source), str(target))

    assert raised.value.__cause__ is raised.value.__context__ is None
    gc.collect()
    assert references and all(reference() is None for reference in references)


def _empty_plan() -> Plan:
    profile = CapabilityProfile("NTFS", 100, True, False, 32767, True, True)
    placeholder = Plan(
        source_root=Root(r"C:\source", "source"),
        target_root=Root(r"D:\target", "target"),
        source_volume_id=None,
        target_volume_id=None,
        source_volume_evidence=None,
        target_volume_evidence=None,
        source_profile=profile,
        target_profile=profile,
        source_complete=True,
        target_complete=True,
        operations=(),
        assignment=Assignment("identity", "1", ()),
        preservation=PreservationPolicy(),
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=True,
        policy_fingerprint="a" * 64,
        required_volumes=frozenset(),
        required_bytes=0,
        fingerprint=PlanFingerprint("0" * 64),
    )
    return replace(placeholder, fingerprint=plan_fingerprint(placeholder))


def _operation(
    index: int,
    kind: OperationKind,
    target: str,
    *,
    source: str | None = None,
    prior_target: str | None = None,
    dependencies: tuple[OpId, ...] = (),
    reason: OperationReason = OperationReason.SOURCE_ONLY,
    blocked_reason: BlockedReason | None = None,
    content_bytes: int = 0,
) -> PlanOperation:
    return PlanOperation(
        OpId(f"{index:032x}"),
        kind,
        source,
        target,
        None,
        None,
        None,
        prior_target_rel_path=prior_target,
        content_bytes=content_bytes,
        dependencies=dependencies,
        reason=reason,
        blocked_reason=blocked_reason,
    )


def _plan_with(
    operations: tuple[PlanOperation, ...],
    *,
    source_complete: bool = True,
    target_complete: bool = True,
) -> Plan:
    value = replace(
        _empty_plan(),
        source_complete=source_complete,
        target_complete=target_complete,
        operations=operations,
        fingerprint=PlanFingerprint("0" * 64),
    )
    return replace(value, fingerprint=plan_fingerprint(value))


def test_selection_excludes_blocker_and_quarantines_its_target_tree() -> None:
    blocked = _operation(
        1,
        OperationKind.NOOP,
        "foo",
        source="foo",
        reason=OperationReason.UNSUPPORTED,
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    independent = _operation(2, OperationKind.COPY, "normal.txt", source="normal.txt")
    counterpart = _operation(
        3,
        OperationKind.TRASH,
        r"foo\keep.txt",
        reason=OperationReason.TARGET_ONLY,
    )
    cleanup = _operation(
        4,
        OperationKind.DELETE,
        "foo",
        dependencies=(counterpart.op_id,),
        reason=OperationReason.DIRECTORY_CLEANUP,
    )
    unrelated_removal = _operation(
        5,
        OperationKind.TRASH,
        "old.txt",
        reason=OperationReason.TARGET_ONLY,
    )

    decision = derive_execution_selection(
        _plan_with((blocked, independent, counterpart, cleanup, unrelated_removal))
    )
    excluded = {item.op_id: item for item in decision.exclusions}

    assert decision.selection == frozenset(
        {independent.op_id, unrelated_removal.op_id}
    )
    assert excluded[blocked.op_id].outcome is Outcome.BLOCKED
    assert excluded[blocked.op_id].reason == BlockedReason.UNSUPPORTED.value
    assert excluded[counterpart.op_id].outcome is Outcome.DEFERRED
    assert excluded[counterpart.op_id].reason == ExclusionReason.BLOCKED_CORRESPONDENCE
    assert excluded[cleanup.op_id].reason == ExclusionReason.BLOCKED_CORRESPONDENCE


def test_selection_closes_over_dependencies_of_excluded_operations() -> None:
    blocked = _operation(
        1,
        OperationKind.NOOP,
        "blocked.bin",
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    dependent = _operation(
        2,
        OperationKind.COPY,
        "elsewhere.bin",
        source="elsewhere.bin",
        dependencies=(blocked.op_id,),
    )

    decision = derive_execution_selection(_plan_with((blocked, dependent)))
    excluded = {item.op_id: item for item in decision.exclusions}

    assert decision.selection == frozenset()
    assert excluded[dependent.op_id].reason == ExclusionReason.BLOCKED_DEPENDENCY


def test_incomplete_scan_keeps_guarded_work_but_withholds_destructive_and_moves() -> None:
    operations = (
        _operation(1, OperationKind.MKDIR, "folder", source="folder"),
        _operation(2, OperationKind.COPY, "copy.bin", source="copy.bin"),
        _operation(3, OperationKind.UPDATE, "update.bin", source="update.bin"),
        _operation(4, OperationKind.NOOP, "same.bin", source="same.bin"),
        _operation(
            5,
            OperationKind.RECASE,
            "KEEP.bin",
            source="KEEP.bin",
            prior_target="keep.bin",
        ),
        _operation(6, OperationKind.TRASH, "trash.bin"),
        _operation(7, OperationKind.DELETE, "delete.bin"),
        _operation(
            8,
            OperationKind.MOVE,
            "moved.bin",
            source="moved.bin",
            prior_target="old.bin",
        ),
        _operation(
            9,
            OperationKind.MOVE_UPDATE,
            "moved-update.bin",
            source="moved-update.bin",
            prior_target="old-update.bin",
        ),
    )

    decision = derive_execution_selection(
        _plan_with(operations, source_complete=False)
    )
    selected_kinds = {
        operation.kind
        for operation in operations
        if operation.op_id in decision.selection
    }
    excluded = {item.op_id: item for item in decision.exclusions}

    assert selected_kinds == {
        OperationKind.MKDIR,
        OperationKind.COPY,
        OperationKind.UPDATE,
        OperationKind.NOOP,
        OperationKind.RECASE,
    }
    assert {
        excluded[operation.op_id].reason
        for operation in operations
        if operation.kind
        in {
            OperationKind.TRASH,
            OperationKind.DELETE,
            OperationKind.MOVE,
            OperationKind.MOVE_UPDATE,
        }
    } == {ExclusionReason.INCOMPLETE_SCAN}

    complete_decision = derive_execution_selection(_plan_with(operations))
    assert complete_decision.selection == frozenset(
        operation.op_id for operation in operations
    )
    assert complete_decision.exclusions == ()


def test_execution_reports_exclusions_without_failing_successful_subset() -> None:
    blocked = _operation(
        1,
        OperationKind.NOOP,
        "junction",
        source="junction",
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    copied = _operation(2, OperationKind.COPY, "normal.txt", source="normal.txt")
    plan = _plan_with((blocked, copied))
    decision = derive_execution_selection(plan)
    run_id = validated_run_id("5" * 32)
    xset = ExecutionSet(
        plan,
        decision.selection,
        run_id,
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(decision.selection),
            NOW,
        ),
    )
    events: list[object] = []
    saved: list[object] = []
    finished: list[tuple[SessionState, object]] = []
    world = _empty_world()
    cleanup_calls: list[tuple[Path, frozenset[str], object]] = []

    class FileSystem:
        def remove_orphaned_temps(self, target, parents, current_run_id) -> None:
            cleanup_calls.append((target, parents, current_run_id))

    class Recording:
        recorder = object()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def finish(self, status, recording) -> None:
            finished.append((status, recording))

    def executor(execution_set, ctx, recorder, policies, fs):
        del recorder, policies, fs
        operation = next(
            operation
            for operation in execution_set.plan.operations
            if operation.op_id in execution_set.selection
        )
        item = ItemOutcome(
            str(operation.op_id),
            operation.kind.value,
            operation.target_rel_path,
            Outcome.SUCCEEDED,
        )
        ctx.emit(item)
        execution_set.status[operation.op_id] = Outcome.SUCCEEDED
        return OperationResult(SessionState.COMPLETED, items=(item,))

    deps = SimpleNamespace(
        save_execution_details=saved.append,
        observer=lambda *args: world,
        observation_fs=object(),
        preflight=lambda execution_set, observed: Verdict(True, (), observed),
        open_recording=lambda _spec: Recording(),
        executor=executor,
        executor_policies=object(),
        executor_fs=FileSystem(),
    )

    result = run_execution(xset, RunContext(events.append, lambda: None), deps)

    assert result.status is SessionState.COMPLETED
    assert [item.outcome for item in result.items] == [
        Outcome.BLOCKED,
        Outcome.SUCCEEDED,
    ]
    assert [item.outcome for item in events if isinstance(item, ItemOutcome)] == [
        Outcome.SUCCEEDED,
        Outcome.BLOCKED,
    ]
    assert cleanup_calls == [
        (Path(plan.target_root.path), frozenset({""}), run_id)
    ]
    assert finished and saved


def test_review_and_commit_bind_the_same_safe_selection(tmp_path: Path) -> None:
    blocked = _operation(
        1,
        OperationKind.NOOP,
        "junction",
        source="junction",
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    copied = _operation(
        2,
        OperationKind.COPY,
        "normal.txt",
        source="normal.txt",
        content_bytes=17,
    )
    withheld = _operation(
        3,
        OperationKind.MOVE,
        "new.txt",
        source="new.txt",
        prior_target="old.txt",
    )
    plan = _plan_with(
        (blocked, copied, withheld),
        source_complete=False,
    )
    request = PlanRequest("request", plan.source_root.path, plan.target_root.path)
    world = SimpleNamespace(
        paths={}, free_space=1_000, reclaimable_temp_bytes=0
    )
    artifact = PlanArtifact(
        request,
        SimpleNamespace(warnings=()),
        SimpleNamespace(warnings=()),
        plan,
        Verdict(True, (), world),
    )
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db", tmp_path / "history.db"
    )
    try:
        runtime.save_plan(artifact)
        assert runtime.get_plan(request.request_id) is artifact

        review = runtime.get_plan_review(request.request_id)
        execution = runtime.commit_plan(
            request.request_id,
            run_id="6" * 32,
            committed_at=NOW,
        )
        runtime.drop_plan(request.request_id)
        runtime.drop_plan(request.request_id)
        with pytest.raises(KeyError):
            runtime.commit_plan(request.request_id)
    finally:
        runtime.close()

    selected = execution.execution_set.selection
    assert selected == frozenset({copied.op_id})
    assert review.selection_digest_hex == selection_digest(selected).hex()
    assert review.required_bytes == "17"
    assert review.operations[2].prior_target_path == "old.txt"
    assert execution.execution_set.commitment is not None
    assert execution.execution_set.commitment.selection_digest == selection_digest(
        selected
    )


def test_fresh_preflight_refusal_still_reports_known_exclusions() -> None:
    blocked = _operation(
        1,
        OperationKind.NOOP,
        "junction",
        source="junction",
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    noop = _operation(
        2,
        OperationKind.NOOP,
        "same.bin",
        source="same.bin",
        reason=OperationReason.METADATA_MATCH,
    )
    plan = _plan_with((blocked, noop))
    decision = derive_execution_selection(plan)
    xset = ExecutionSet(
        plan,
        decision.selection,
        validated_run_id("7" * 32),
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(decision.selection),
            NOW,
        ),
    )
    world = _empty_world()
    events: list[object] = []
    deps = SimpleNamespace(
        save_execution_details=lambda value: None,
        observer=lambda *args: world,
        observation_fs=object(),
        preflight=lambda execution_set, observed: Verdict(
            False,
            (Refusal(RefusalCode.ROOT_CHANGED),),
            observed,
        ),
    )

    result = run_execution(xset, RunContext(events.append, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert [item.outcome for item in result.items] == [Outcome.BLOCKED]
    assert [item.outcome for item in events if isinstance(item, ItemOutcome)] == [
        Outcome.BLOCKED
    ]


@pytest.mark.parametrize(
    "error, expected_status, expected_canceled",
    [
        (RuntimeError("preflight failed"), SessionState.FAILED, False),
        (Canceled("preflight canceled"), SessionState.CANCELED, True),
    ],
)
def test_fresh_preflight_boundary_uses_reviewed_execution_counters(
    error: Exception,
    expected_status: SessionState,
    expected_canceled: bool,
) -> None:
    plan = _plan_with(
        (
            _operation(
                1,
                OperationKind.COPY,
                "normal.txt",
                source="normal.txt",
                content_bytes=17,
            ),
        )
    )
    selection = frozenset(operation.op_id for operation in plan.operations)
    xset = ExecutionSet(
        plan,
        selection,
        validated_run_id("9" * 32),
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    executor_called = False

    def observer(*_args):
        raise error

    def executor(*_args):
        nonlocal executor_called
        executor_called = True
        raise AssertionError("executor entered after preflight boundary")

    result = run_execution(
        xset,
        RunContext(lambda _value: None, lambda: None),
        SimpleNamespace(
            save_execution_details=lambda _value: None,
            observer=observer,
            observation_fs=object(),
            preflight=lambda *_args: pytest.fail("preflight ran after observation"),
            executor=executor,
        ),
    )

    assert not executor_called
    assert result.status is expected_status
    assert result.canceled is expected_canceled
    assert result.disposition is Disposition.UNRUN
    assert result.phases == ()
    assert (result.bytes_done, result.bytes_total) == (0, 17)
    if expected_status is SessionState.FAILED:
        assert result.error is not None
        assert result.error.type_name == "RuntimeError"


def test_execution_review_wall_is_an_ordinary_prerun_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation = _operation(
        1,
        OperationKind.COPY,
        "normal.txt",
        source="normal.txt",
        content_bytes=17,
    )
    plan = _plan_with((operation,))
    selection = frozenset({operation.op_id})
    xset = ExecutionSet(
        plan,
        selection,
        validated_run_id("b" * 32),
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    monkeypatch.setattr(review_module, "MAX_PLAN_REVIEW_ROWS", 0)
    executor_called = False

    def executor(*_args):
        nonlocal executor_called
        executor_called = True
        raise AssertionError("executor entered after execution review excess")

    result = run_execution(
        xset,
        RunContext(lambda _value: None, lambda: None),
        SimpleNamespace(
            save_execution_details=lambda _value: None,
            observer=lambda *_args: _empty_world(),
            observation_fs=object(),
            preflight=lambda *_args: pytest.fail(
                "preflight ran after observer-result excess"
            ),
            executor=executor,
        ),
    )

    assert not executor_called
    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.UNRUN
    assert result.review_fact_limit is None
    assert result.error is not None
    assert result.error.message == "review_fact_limit_exceeded"
    assert result.phases == ()
    assert (result.bytes_done, result.bytes_total) == (0, 17)


@pytest.mark.parametrize("boundary", ["commitment-details", "preflight-details"])
def test_fresh_detail_save_failure_uses_reviewed_execution_counters(
    boundary: str,
) -> None:
    operation = _operation(
        1,
        OperationKind.COPY,
        "normal.txt",
        source="normal.txt",
        content_bytes=17,
    )
    plan = _plan_with((operation,))
    selection = frozenset({operation.op_id})
    commitment = (
        None
        if boundary == "commitment-details"
        else Commitment(
            plan.fingerprint,
            selection_digest(selection),
            NOW,
        )
    )
    xset = ExecutionSet(
        plan,
        selection,
        validated_run_id("a" * 32),
        commitment=commitment,
    )
    executor_called = False
    world = _empty_world()

    def save_execution_details(_value: object) -> None:
        raise RuntimeError(f"{boundary} write failed")

    def observer(*_args):
        assert boundary == "preflight-details"
        return world

    def executor(*_args):
        nonlocal executor_called
        executor_called = True
        raise AssertionError("executor entered after detail-save failure")

    result = run_execution(
        xset,
        RunContext(lambda _value: None, lambda: None),
        SimpleNamespace(
            save_execution_details=save_execution_details,
            observer=observer,
            observation_fs=object(),
            preflight=lambda execution_set, observed: Verdict(True, (), observed),
            executor=executor,
        ),
    )

    assert not executor_called
    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.UNRUN
    assert result.phases == ()
    assert (result.bytes_done, result.bytes_total) == (0, 17)
    assert result.error is not None
    assert result.error.type_name == "RuntimeError"
    assert result.error.message == f"{boundary} write failed"


def test_undelivered_execution_outcome_does_not_enter_workflow_result() -> None:
    operation = _operation(
        1,
        OperationKind.COPY,
        "normal.txt",
        source="normal.txt",
        content_bytes=17,
    )
    plan = _plan_with((operation,))
    selection = frozenset({operation.op_id})
    xset = ExecutionSet(
        plan,
        selection,
        validated_run_id("b" * 32),
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    world = _empty_world()

    class Recording:
        recorder = object()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def finish(self, status, recording) -> None:
            return None

    class FileSystem:
        def remove_orphaned_temps(self, target, parents, current_run_id) -> None:
            return None

    def executor(execution_set, ctx, recorder, policies, fs):
        del execution_set, recorder, policies, fs
        item = ItemOutcome(
            str(operation.op_id),
            operation.kind.value,
            operation.target_rel_path,
            Outcome.SUCCEEDED,
        )
        ctx.emit(item)
        raise AssertionError("unreachable after rejected reliable outcome")

    def emit(body: object) -> None:
        if isinstance(body, ItemOutcome):
            raise RuntimeError("reliable outcome sink failed")

    result = run_execution(
        xset,
        RunContext(emit, lambda: None),
        SimpleNamespace(
            save_execution_details=lambda _value: None,
            observer=lambda *_args: world,
            observation_fs=object(),
            preflight=lambda execution_set, observed: Verdict(True, (), observed),
            open_recording=lambda _spec: Recording(),
            executor=executor,
            executor_policies=object(),
            executor_fs=FileSystem(),
        ),
    )

    assert result.status is SessionState.FAILED
    assert result.items == ()
    assert xset.status == {}
    assert result.error is not None
    assert result.error.type_name == "RuntimeError"
    assert result.error.message == "reliable outcome sink failed"


def test_temp_recovery_failure_stops_before_executor_and_records_failure() -> None:
    plan = _plan_with(
        (_operation(1, OperationKind.COPY, "normal.txt", source="normal.txt"),)
    )
    selection = frozenset(operation.op_id for operation in plan.operations)
    run_id = validated_run_id("8" * 32)
    xset = ExecutionSet(
        plan,
        selection,
        run_id,
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    finished: list[SessionState] = []
    executor_called = False
    world = _empty_world()

    class Recording:
        recorder = object()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def finish(self, status, recording) -> None:
            del recording
            finished.append(status)

    class FileSystem:
        def remove_orphaned_temps(self, target, parents, current_run_id) -> None:
            del target, parents, current_run_id
            raise PermissionError("orphan is locked")

    def executor(*args):
        nonlocal executor_called
        executor_called = True
        return OperationResult(SessionState.COMPLETED)

    deps = SimpleNamespace(
        save_execution_details=lambda value: None,
        observer=lambda *args: world,
        observation_fs=object(),
        preflight=lambda execution_set, observed: Verdict(True, (), observed),
        open_recording=lambda _spec: Recording(),
        executor=executor,
        executor_policies=object(),
        executor_fs=FileSystem(),
    )

    result = run_execution(
        xset,
        RunContext(lambda value: None, lambda: None),
        deps,
    )

    assert not executor_called
    assert finished == [SessionState.FAILED]
    assert result.status is SessionState.FAILED
    assert result.phases == ()
    assert result.bytes_done == 0
    assert result.bytes_total == sum(
        operation.content_bytes for operation in plan.operations
    )
    assert result.error is not None
    assert result.error.type_name == "PermissionError"
    assert result.error.message == "orphan is locked"


def test_execution_refuses_uncommitted_set_before_preflight() -> None:
    saved = []
    xset = ExecutionSet(
        _empty_plan(), frozenset(), validated_run_id("1" * 32)
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert saved[0].commitment_error == "execution set is not committed"


def test_execution_refuses_changed_selection_digest_before_preflight() -> None:
    saved = []
    plan = _empty_plan()
    xset = ExecutionSet(
        plan,
        frozenset(),
        validated_run_id("2" * 32),
        commitment=Commitment(plan.fingerprint, b"x" * 32, NOW),
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert "selection digest" in saved[0].commitment_error


def test_execution_refuses_changed_plan_fingerprint_before_preflight() -> None:
    saved = []
    plan = _empty_plan()
    xset = ExecutionSet(
        plan,
        frozenset(),
        validated_run_id("3" * 32),
        commitment=Commitment(PlanFingerprint("e" * 64), b"x" * 32, NOW),
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert "plan fingerprint" in saved[0].commitment_error


def test_execution_refuses_plan_content_that_no_longer_matches_fingerprint() -> None:
    saved = []
    plan = _empty_plan()
    tampered = replace(plan, deletion_policy=DeletionPolicy.ADDITIVE)
    xset = ExecutionSet(
        tampered,
        frozenset(),
        validated_run_id("4" * 32),
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(frozenset()),
            NOW,
        ),
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert "plan content" in saved[0].commitment_error


def _selection_mismatch_fixture() -> tuple[ExecutionSet, PlanOperation]:
    folder = _operation(1, OperationKind.MKDIR, "folder", source="folder")
    child = _operation(
        2,
        OperationKind.COPY,
        r"folder\child.bin",
        source=r"folder\child.bin",
        dependencies=(folder.op_id,),
    )
    noop = _operation(
        3,
        OperationKind.NOOP,
        "same.bin",
        source="same.bin",
        reason=OperationReason.METADATA_MATCH,
    )
    plan = _plan_with((folder, child, noop))
    user_deselected = frozenset({folder.op_id})
    expected = derive_execution_selection(
        plan,
        user_deselected=user_deselected,
    ).selection
    tampered = expected | {child.op_id}
    return (
        ExecutionSet(
            plan=plan,
            selection=tampered,
            run_id=validated_run_id("9" * 32),
            commitment=Commitment(
                plan.fingerprint,
                selection_digest(tampered),
                NOW,
            ),
            user_deselected=user_deselected,
        ),
        child,
    )


def test_execution_refuses_rederived_selection_mismatch_before_preflight() -> None:
    xset, _ = _selection_mismatch_fixture()
    saved: list[object] = []

    result = run_execution(
        xset,
        RunContext(lambda body: None, lambda: None),
        SimpleNamespace(
            save_execution_details=saved.append,
            observer=lambda *args: pytest.fail("preflight observation ran"),
        ),
    )

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert "derived selection" in saved[0].commitment_error


def test_execution_refuses_safety_excluded_user_provenance_before_preflight() -> None:
    blocked = _operation(
        1,
        OperationKind.NOOP,
        "blocked.bin",
        source="blocked.bin",
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    noop = _operation(
        2,
        OperationKind.NOOP,
        "same.bin",
        source="same.bin",
        reason=OperationReason.METADATA_MATCH,
    )
    plan = _plan_with((blocked, noop))
    selection = frozenset({noop.op_id})
    xset = ExecutionSet(
        plan=plan,
        selection=selection,
        run_id=validated_run_id("8" * 32),
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
        user_deselected=frozenset({blocked.op_id}),
    )
    saved: list[object] = []

    result = run_execution(
        xset,
        RunContext(lambda body: None, lambda: None),
        SimpleNamespace(
            save_execution_details=saved.append,
            observer=lambda *args: pytest.fail("preflight observation ran"),
        ),
    )

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert "safety-excluded" in saved[0].commitment_error


@pytest.mark.parametrize("phase", ["execute", "verify"])
def test_resumed_execution_settles_selection_mismatch_without_preflight(
    phase: str,
) -> None:
    xset, _ = _selection_mismatch_fixture()
    finished: list[SessionState] = []

    class Recording:
        recorder = object()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def finish(self, status, recording) -> None:
            finished.append(status)

    continuation = (
        ExecuteContinuation(xset)
        if phase == "execute"
        else VerifyContinuation(
            execution_set=xset,
            candidates=PostCopySelection(()),
            filesystem_status=SessionState.COMPLETED,
            recording=RecordingStatus.OK,
            execute_phase=PhaseResult(
                "execute",
                PhaseStatus.COMPLETED,
                1,
                1,
                0,
                0,
            ),
        )
    )
    result = run_execution(
        continuation,
        RunContext(lambda body: None, lambda: None),
        SimpleNamespace(
            save_execution_details=lambda details: None,
            observer=lambda *args: pytest.fail("preflight observation ran"),
            open_recording=lambda _spec: Recording(),
            finish_existing_recording=lambda _spec, status, _recording: finished.append(
                status
            ),
        ),
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


def _real_cycle(
    runtime: LocalWorkflowRuntime,
    source: Path,
    target: Path,
    *,
    request_id: str,
    run_id: str,
) -> tuple[object, OperationResult]:
    """Drive one real plan, commitment, and execution against live roots."""

    request = PlanRequest(
        request_id=request_id,
        source_path=str(source),
        target_path=str(target),
        options=SyncOptions(propagate_source_casing=True),
    )
    context = RunContext(lambda _: None, lambda: None)
    plan_result = runtime.open_plan(runtime.prepare_plan(request).checkpoint).run(context)
    assert plan_result.status is SessionState.COMPLETED
    review = runtime.get_plan_review(request_id)
    execution = runtime.commit_plan(request_id, run_id=run_id, committed_at=NOW)
    checkpoint = runtime.prepare_execution(execution).checkpoint
    return review, runtime.open_execution(checkpoint).run(context)


def test_opt_in_recase_runs_end_to_end_without_copying_or_trashing(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "KEEP.txt").write_bytes(b"same content")
    (target / "keep.txt").write_bytes(b"same content")
    observed = os.stat(source / "KEEP.txt")
    os.utime(target / "keep.txt", ns=(observed.st_mtime_ns, observed.st_mtime_ns))
    identity_before = os.stat(target / "keep.txt").st_ino

    runtime = LocalWorkflowRuntime(tmp_path / "ledger.db", tmp_path / "history.db")
    try:
        review, result = _real_cycle(
            runtime, source, target, request_id="a" * 32, run_id="b" * 32
        )

        # The planner chose a rename over a rewrite, and review names both spellings.
        assert [operation.kind for operation in review.operations] == ["recase"]
        recase = review.operations[0]
        assert recase.prior_target_path == "keep.txt"
        assert recase.target_path == "KEEP.txt"
        assert recase.content_bytes == "0"
        assert review.required_bytes == "0"

        # The executor renamed in place: no bytes, no displaced version, same file.
        assert result.status is SessionState.COMPLETED
        assert result.bytes_total == 0
        assert [entry.name for entry in target.iterdir()] == ["KEEP.txt"]
        assert (target / "KEEP.txt").read_bytes() == b"same content"
        assert os.stat(target / "KEEP.txt").st_ino == identity_before
        assert not (target / ".synctrash").exists()

        # The ledger followed the new spelling instead of retaining a stale row.
        connection = connect_ledger_reader(runtime.ledger_path)
        try:
            assert {
                row["rel_path"] for row in connection.execute("SELECT rel_path FROM inventory")
            } == {"KEEP.txt"}
            assert [
                row["kind"] for row in connection.execute("SELECT kind FROM operations")
            ] == [OperationKind.RECASE.value]
        finally:
            connection.close()

        # A second reviewed cycle converges instead of recasing forever.
        rerun_review, rerun_result = _real_cycle(
            runtime, source, target, request_id="c" * 32, run_id="d" * 32
        )

        assert [operation.kind for operation in rerun_review.operations] == ["noop"]
        assert rerun_result.status is SessionState.COMPLETED
        assert [entry.name for entry in target.iterdir()] == ["KEEP.txt"]
        assert not (target / ".synctrash").exists()
    finally:
        runtime.close()
