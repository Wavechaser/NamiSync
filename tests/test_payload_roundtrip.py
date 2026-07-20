"""Payload codec round-trip and fingerprint-stability guard.

Execution correctness hinges on ``plan_fingerprint(decode(encode(plan)))``
being exactly equal to the reviewed plan's fingerprint: the execution session
recomputes the fingerprint from the *decoded* plan and refuses on any mismatch
(see ``workflows.sync._commitment_error``). A plan field that is added to the
fingerprint but dropped or renormalized by the JSON codec would therefore make
every execution silently REFUSE. These tests exercise the codec over a plan
carrying every operation kind and every optional field so that such a drift is
a failing build rather than a field-report mystery.
"""

from __future__ import annotations

from datetime import datetime, timezone

from namisync.core.evidence import Outcome
from namisync.core.execution import Commitment, ExecutionSet, validated_run_id
from namisync.core.models import (
    CapabilityProfile,
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
    Root,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.planning import (
    Assignment,
    BlockedReason,
    DeletionPolicy,
    DestinationAssignment,
    FilterSet,
    OpId,
    OperationKind,
    OperationReason,
    Plan,
    PlanFingerprint,
    PlanOperation,
    PreservationPolicy,
    plan_fingerprint,
    selection_digest,
)
from namisync.core.pathing import normalize_relative_path
from namisync.workflows.models import ExecutionRequest
from namisync.workflows.payloads import (
    decode_execution_request,
    encode_execution_request,
)
from namisync.workflows.sync import _commitment_error


NOW = datetime(2026, 7, 19, 12, 30, tzinfo=timezone.utc)


def _op_id(number: int) -> OpId:
    return OpId(f"{number:032x}")


def _stat(
    *,
    kind: EntryKind = EntryKind.FILE,
    size: int = 11,
    mtime_ns: int = 123456789,
    identity: FileIdentity | None = None,
    nlink: int = 1,
    attributes: int = 0,
    created_ns: int | None = 111,
) -> FileStat:
    return FileStat(
        kind=kind,
        size=size,
        mtime_ns=mtime_ns,
        file_identity=identity,
        nlink=nlink,
        metadata=MetadataSnapshot(attributes, created_ns),
    )


def _assignment_item(source: str, target: str) -> DestinationAssignment:
    return DestinationAssignment(
        source_rel_path=source,
        source_rel_path_key=normalize_relative_path(source),
        target_rel_path=target,
        target_rel_path_key=normalize_relative_path(target),
        group_id="grp-1",
        conflict=None,
    )


def _rich_plan() -> Plan:
    """A plan touching every operation kind and non-default optional field."""

    identity = FileIdentity("A1B2C3D4", 4242)
    source_profile = CapabilityProfile(
        fs_type="NTFS",
        mtime_granularity_ns=100,
        stable_file_identity=True,
        incurs_seek_penalty=None,  # exercises the tri-state None branch
        max_path=32767,
        supports_ads=True,
        supports_hardlinks=True,
    )
    target_profile = CapabilityProfile(
        fs_type="EXFAT",
        mtime_granularity_ns=10_000_000,
        stable_file_identity=False,
        incurs_seek_penalty=False,
        max_path=260,
        supports_ads=False,
        supports_hardlinks=False,
    )

    mkdir = PlanOperation(
        op_id=_op_id(1),
        kind=OperationKind.MKDIR,
        source_rel_path="dir",
        target_rel_path="dir",
        source_expected=_stat(kind=EntryKind.DIRECTORY, size=0),
        target_expected=None,
        intended=_stat(kind=EntryKind.DIRECTORY, size=0, attributes=2),
        metadata=MetadataSnapshot(2, 111),
        reason=OperationReason.REQUIRED_DIRECTORY,
    )
    copy = PlanOperation(
        op_id=_op_id(2),
        kind=OperationKind.COPY,
        source_rel_path="dir\\new.bin",
        target_rel_path="dir\\new.bin",
        source_expected=_stat(size=11, identity=identity),
        target_expected=None,
        intended=_stat(size=11, identity=identity),
        content_bytes=11,
        dependencies=(_op_id(1),),
        reason=OperationReason.SOURCE_ONLY,
    )
    update = PlanOperation(
        op_id=_op_id(3),
        kind=OperationKind.UPDATE,
        source_rel_path="changed.bin",
        target_rel_path="changed.bin",
        source_expected=_stat(size=20, mtime_ns=999, attributes=1),
        target_expected=_stat(size=10, mtime_ns=1, attributes=1),
        intended=_stat(size=20, mtime_ns=999, attributes=1),
        content_bytes=20,
        reason=OperationReason.METADATA_CHANGED,
    )
    move = PlanOperation(
        op_id=_op_id(4),
        kind=OperationKind.MOVE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=_stat(identity=identity),
        target_expected=None,
        intended=_stat(identity=identity),
        prior_target_rel_path="old-name.bin",
        prior_target_expected=_stat(identity=identity),
        reason=OperationReason.IDENTITY_RENAME,
    )
    move_update = PlanOperation(
        op_id=_op_id(5),
        kind=OperationKind.MOVE_UPDATE,
        source_rel_path="moved-changed.bin",
        target_rel_path="moved-changed.bin",
        source_expected=_stat(size=30, mtime_ns=555, identity=identity),
        target_expected=None,
        intended=_stat(size=30, mtime_ns=555, identity=identity),
        prior_target_rel_path="was-here.bin",
        prior_target_expected=_stat(size=15, mtime_ns=222, identity=identity),
        content_bytes=30,
        reason=OperationReason.IDENTITY_RENAME_CHANGED,
    )
    trash = PlanOperation(
        op_id=_op_id(6),
        kind=OperationKind.TRASH,
        source_rel_path=None,
        target_rel_path="target-only.bin",
        source_expected=None,
        target_expected=_stat(size=7, attributes=1),
        intended=None,
        reason=OperationReason.TARGET_ONLY,
    )
    delete = PlanOperation(
        op_id=_op_id(7),
        kind=OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="mirror-only.bin",
        source_expected=None,
        target_expected=_stat(size=3),
        intended=None,
        reason=OperationReason.TARGET_ONLY,
    )
    noop = PlanOperation(
        op_id=_op_id(8),
        kind=OperationKind.NOOP,
        source_rel_path="same.bin",
        target_rel_path="same.bin",
        source_expected=_stat(size=5, identity=identity),
        target_expected=_stat(size=5, identity=identity),
        intended=_stat(size=5, identity=identity),
        reason=OperationReason.METADATA_MATCH,
    )
    blocked = PlanOperation(
        op_id=_op_id(9),
        kind=OperationKind.COPY,
        source_rel_path="conflict.bin",
        target_rel_path="conflict.bin",
        source_expected=_stat(size=4),
        target_expected=None,
        intended=_stat(size=4),
        content_bytes=4,
        reason=OperationReason.CASE_COLLISION,
        blocked_reason=BlockedReason.CASE_COLLISION,
    )

    operations = (mkdir, copy, update, move, move_update, trash, delete, noop, blocked)
    placeholder = Plan(
        source_root=Root(r"C:\source", "source"),
        target_root=Root(r"E:\target", "target"),
        source_volume_id=VolumeId("A1B2C3D4", "NTFS"),
        target_volume_id=VolumeId("99887766", "EXFAT"),
        source_volume_evidence=VolumeEvidence(
            label="SourceDrive", device_id="C:\\", clone_ambiguous=False
        ),
        target_volume_evidence=VolumeEvidence(
            label=None, device_id="E:\\", clone_ambiguous=True
        ),
        source_profile=source_profile,
        target_profile=target_profile,
        source_complete=True,
        target_complete=False,
        operations=operations,
        assignment=Assignment(
            "identity",
            "1",
            (_assignment_item("dir\\new.bin", "dir\\new.bin"),),
        ),
        preservation=PreservationPolicy(
            preserve_ads=True, preserve_created=False, preserve_acl=True
        ),
        filter_snapshot=FilterSet(("*.tmp", "sub\\*")),
        deletion_policy=DeletionPolicy.ADDITIVE,
        trash_on_update=True,
        policy_fingerprint="p" * 64,
        worker_count=1,
        required_volumes=frozenset(
            {VolumeId("A1B2C3D4", "NTFS"), VolumeId("99887766", "EXFAT")}
        ),
        required_bytes=61,
        fingerprint=PlanFingerprint("0" * 64),
    )
    from dataclasses import replace

    return replace(placeholder, fingerprint=plan_fingerprint(placeholder))


def _rich_execution_request() -> ExecutionRequest:
    plan = _rich_plan()
    selection = frozenset(operation.op_id for operation in plan.operations)
    xset = ExecutionSet(
        plan=plan,
        selection=selection,
        run_id=validated_run_id("a" * 32),
        # a partial continuation, as a paused/resumed set would carry
        status={_op_id(1): Outcome.SUCCEEDED, _op_id(9): Outcome.FAILED},
        commitment=Commitment(plan.fingerprint, selection_digest(selection), NOW),
    )
    return ExecutionRequest(xset, NOW)


def test_execution_payload_is_a_lossless_round_trip() -> None:
    original = _rich_execution_request()

    decoded = decode_execution_request(encode_execution_request(original))

    assert decoded.started_at == original.started_at
    assert decoded.execution_set.plan == original.execution_set.plan
    assert decoded.execution_set.selection == original.execution_set.selection
    assert decoded.execution_set.status == original.execution_set.status
    assert decoded.execution_set.commitment == original.execution_set.commitment
    assert str(decoded.execution_set.run_id) == str(original.execution_set.run_id)


def test_decoded_plan_recomputes_the_same_fingerprint() -> None:
    original = _rich_execution_request()

    decoded = decode_execution_request(encode_execution_request(original))

    assert plan_fingerprint(decoded.execution_set.plan) == original.execution_set.plan.fingerprint


def test_round_tripped_committed_set_would_not_refuse() -> None:
    original = _rich_execution_request()

    decoded = decode_execution_request(encode_execution_request(original))

    # The execution session recomputes the fingerprint from the decoded plan and
    # validates the commitment against it before preflight; a lossy codec would
    # surface here as a non-None refusal reason.
    assert _commitment_error(decoded.execution_set) is None


def test_encoding_is_deterministic_and_order_independent() -> None:
    original = _rich_execution_request()

    first = encode_execution_request(original)
    second = encode_execution_request(decode_execution_request(first))

    assert first == second
