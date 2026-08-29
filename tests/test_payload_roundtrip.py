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

from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

import namisync.core.execution as execution_module
import namisync.workflows.payloads as payload_module
from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    Outcome,
    Provenance,
    RecordingStatus,
)
from namisync.core.execution import (
    Commitment,
    ExecutionSet,
    ItemRecordingReason,
    PublishedCopyEvidence,
    RecordedCopyIdentity,
    TaskRecordingIssue,
    TaskRecordingIssueReason,
    validate_execution_set,
    validated_run_id,
)
from namisync.core.integrity import (
    PostCopyCandidate,
    PostCopyRecordIdentity,
    PostCopySelection,
)
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
    SyncOptions,
    plan_fingerprint,
    selection_digest,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.scalars import MAX_FILE_INDEX_128, MAX_SAFE_INTEGER
from namisync.core.session import PhaseResult, PhaseStatus, SessionState
from namisync.workflows.models import (
    ExecuteContinuation,
    ExecutionRequest,
    PlanRequest,
    VerifyContinuation,
)
from namisync.workflows.payloads import (
    decode_plan_request,
    decode_execution_request,
    encode_plan_request,
    encode_execution_request,
)
from namisync.workflows.sync import _commitment_error


NOW = datetime(2026, 7, 19, 12, 30, tzinfo=timezone.utc)

_EXECUTION_V7_ITEM_RECORDING_REASONS = frozenset(
    {
        "record-write-failed",
        "unrecorded-mutation",
        "recording-prerequisite-failed",
    }
)
_EXECUTION_V7_TASK_RECORDING_ISSUE_REASONS = frozenset(
    {
        "recording-open-failed",
        "final-flush-failed",
        "finish-failed",
        "recording-close-failed",
        "post-settlement-state-diverged",
    }
)


def test_plan_request_round_trips_latent_source_casing_policy() -> None:
    request = PlanRequest(
        "request",
        r"C:\source",
        r"D:\target",
        SyncOptions(propagate_source_casing=True),
    )

    decoded = decode_plan_request(encode_plan_request(request))

    assert decoded.options.propagate_source_casing


def test_plan_request_decode_rejects_n_plus_one_filters() -> None:
    value = json.loads(
        encode_plan_request(
            PlanRequest("request", r"C:\source", r"D:\target")
        )
    )
    value["options"]["filters"] = [str(index) for index in range(65)]

    with pytest.raises(ValueError, match="pattern limit"):
        decode_plan_request(json.dumps(value).encode("utf-8"))


def test_plan_request_requires_fingerprinted_source_casing_policy() -> None:
    encoded = encode_plan_request(
        PlanRequest("request", r"C:\source", r"D:\target")
    )
    value = json.loads(encoded.decode("utf-8"))
    del value["options"]["propagate_source_casing"]
    missing_policy = json.dumps(value, separators=(",", ":")).encode("utf-8")

    with pytest.raises(ValueError, match="missing"):
        decode_plan_request(missing_policy)


def test_worker_count_is_absent_from_contracts_and_payloads() -> None:
    assert "worker_count" not in {field.name for field in fields(SyncOptions)}
    assert "worker_count" not in {field.name for field in fields(Plan)}
    with pytest.raises(TypeError):
        SyncOptions(worker_count=2)  # type: ignore[call-arg]

    plan_payload = encode_plan_request(
        PlanRequest("request", r"C:\source", r"D:\target")
    )
    execution_payload = encode_execution_request(_rich_execution_request())
    assert b"worker_count" not in plan_payload
    assert b"worker_count" not in execution_payload


@pytest.mark.parametrize("schema_version", [1, 2, 3, 4])
def test_old_workflow_payload_is_refused_after_contract_change(
    schema_version: int,
) -> None:
    value = json.loads(
        encode_plan_request(
            PlanRequest("request", r"C:\source", r"D:\target")
        ).decode("utf-8")
    )
    value["schema_version"] = schema_version

    with pytest.raises(ValueError, match="unsupported workflow payload schema"):
        decode_plan_request(json.dumps(value).encode("utf-8"))


def test_plan_v5_and_execution_v7_are_independent_exact_payloads() -> None:
    plan_value = json.loads(
        encode_plan_request(
            PlanRequest("request", r"C:\source", r"D:\target")
        )
    )
    execution_value = json.loads(
        encode_execution_request(_rich_execution_request())
    )

    assert plan_value["schema_version"] == 5
    assert execution_value["schema_version"] == 7

    execution_value["schema_version"] = 6
    with pytest.raises(ValueError, match="unsupported workflow payload schema"):
        decode_execution_request(
            json.dumps(execution_value).encode("utf-8")
        )


@pytest.mark.parametrize("text", ("\ud800", "\udcff", "\ud83d\ude00"))
def test_plan_request_encoding_rejects_surrogate_code_units(text: str) -> None:
    hostile = "request_" + text
    request = PlanRequest(hostile, r"C:\source", r"D:\target")

    with pytest.raises(ValueError, match="valid Unicode"):
        encode_plan_request(request)


@pytest.mark.parametrize("text", ("\ud800", "\udcff", "\ud83d\ude00"))
@pytest.mark.parametrize("position", ("key", "value"))
def test_workflow_json_rejects_nested_surrogate_code_units(text: str, position: str) -> None:
    nested = {text: "scalar"} if position == "key" else {"scalar": text}
    with pytest.raises(UnicodeEncodeError):
        payload_module._json_bytes({"nested": [nested]})


@pytest.mark.parametrize("text", ("\ud800", "\udcff"))
@pytest.mark.parametrize("position", ("key", "value"))
def test_plan_request_decoding_rejects_escaped_surrogates(text: str, position: str) -> None:
    value = json.loads(encode_plan_request(PlanRequest("request", r"C:\source", r"D:\target")))
    if position == "key":
        value["options"][text] = "unexpected"
    else:
        value["request_id"] = text
    with pytest.raises(ValueError, match="valid Unicode"):
        decode_plan_request(json.dumps(value).encode("utf-8"))


def test_plan_request_preserves_scalar_unicode_and_literal_escapes() -> None:
    request = PlanRequest("caf\u00e9-\U0001f600-" + r"\ud800", r"C:\source", r"D:\target")
    encoded = encode_plan_request(request)
    assert b"caf\xc3\xa9-\xf0\x9f\x98\x80-\\\\ud800" in encoded
    assert decode_plan_request(encoded) == request
    # A valid JSON escaped pair denotes one scalar, not two Python code units.
    escaped = json.dumps(json.loads(encoded)).encode("utf-8")
    assert b"\\ud83d\\ude00" in escaped
    assert decode_plan_request(escaped) == request


@pytest.mark.parametrize("constant", [b"NaN", b"Infinity", b"-Infinity"])
def test_workflow_payload_rejects_non_json_numeric_constants(
    constant: bytes,
) -> None:
    encoded = encode_plan_request(
        PlanRequest("request", r"C:\source", r"D:\target")
    )
    marker = b'"schema_version":5'
    assert marker in encoded
    malformed = encoded.replace(
        marker,
        b'"schema_version":' + constant,
        1,
    )

    with pytest.raises(ValueError, match="invalid JSON number"):
        decode_plan_request(malformed)


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


def _rich_plan(*, identity_index: int = 4242) -> Plan:
    """A plan touching every operation kind and non-default optional field."""

    identity = FileIdentity("A1B2C3D4", identity_index)
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
    recase = PlanOperation(
        op_id=_op_id(9),
        kind=OperationKind.RECASE,
        source_rel_path="KEEP.bin",
        target_rel_path="KEEP.bin",
        source_expected=_stat(size=5, identity=identity),
        target_expected=_stat(size=5, identity=identity),
        intended=_stat(size=5, identity=identity),
        prior_target_rel_path="keep.bin",
        prior_target_expected=_stat(size=5, identity=identity),
        reason=OperationReason.CASE_MISMATCH,
    )
    blocked = PlanOperation(
        op_id=_op_id(10),
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

    operations = (
        mkdir,
        copy,
        update,
        move,
        move_update,
        trash,
        delete,
        noop,
        recase,
        blocked,
    )
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
        policy_fingerprint="a" * 64,
        required_volumes=frozenset(
            {VolumeId("A1B2C3D4", "NTFS"), VolumeId("99887766", "EXFAT")}
        ),
        required_bytes=61,
        fingerprint=PlanFingerprint("0" * 64),
    )
    return replace(placeholder, fingerprint=plan_fingerprint(placeholder))


def _copy_attestation(
    operation: PlanOperation,
    digest_byte: int,
) -> Attestation:
    assert operation.intended is not None
    return Attestation(
        ContentEvidence(
            algorithm="xxh3_128",
            digest=bytes([digest_byte]) * 16,
            size=operation.content_bytes,
            provenance=Provenance.COPY_ATTESTED,
            observed_at=NOW,
        ),
        operation.intended,
    )


def _copy_identity(
    operation: PlanOperation,
    run_id: str,
) -> RecordedCopyIdentity:
    return RecordedCopyIdentity(
        row_id=str(int(str(operation.op_id), 16)),
        location_id="9",
        scope_token=run_id,
        rel_path_key=normalize_relative_path(operation.target_rel_path),
    )


def _rich_execution_request(*, plan: Plan | None = None) -> ExecutionRequest:
    plan = _rich_plan() if plan is None else plan
    selection = frozenset(operation.op_id for operation in plan.operations)
    run_id = "a" * 32
    copy = plan.operations[1]
    copy_attestation = _copy_attestation(copy, 2)
    xset = ExecutionSet(
        plan=plan,
        selection=selection,
        run_id=validated_run_id(run_id),
        # a partial continuation, as a paused/resumed set would carry
        status={
            _op_id(1): Outcome.SUCCEEDED,
            copy.op_id: Outcome.SUCCEEDED,
            _op_id(10): Outcome.FAILED,
        },
        commitment=Commitment(plan.fingerprint, selection_digest(selection), NOW),
        published_evidence={
            copy.op_id: PublishedCopyEvidence(
                copy_attestation,
                _copy_identity(copy, run_id),
            )
        },
        recording_issues=(
            TaskRecordingIssue(
                TaskRecordingIssueReason.FINAL_FLUSH_FAILED,
                "RuntimeError: final flush failed",
            ),
        ),
        bytes_done_high_water=17,
    )
    return ExecutionRequest(
        ExecuteContinuation(xset, verify_after_execute=True),
        NOW,
    )


def _rich_verify_request() -> ExecutionRequest:
    plan = _rich_plan()
    selection = frozenset(operation.op_id for operation in plan.operations)
    run_id = "b" * 32
    copy = plan.operations[1]
    update = plan.operations[2]
    move_update = plan.operations[4]
    copy_attestation = _copy_attestation(copy, 2)
    move_update_attestation = _copy_attestation(move_update, 5)
    copy_identity = _copy_identity(copy, run_id)
    xset = ExecutionSet(
        plan=plan,
        selection=selection,
        run_id=validated_run_id(run_id),
        status={
            _op_id(1): Outcome.SUCCEEDED,
            copy.op_id: Outcome.SUCCEEDED,
            update.op_id: Outcome.SUCCEEDED,
            move_update.op_id: Outcome.SUCCEEDED,
            _op_id(10): Outcome.FAILED,
        },
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
        published_evidence={
            copy.op_id: PublishedCopyEvidence(
                copy_attestation,
                copy_identity,
            ),
            move_update.op_id: PublishedCopyEvidence(
                move_update_attestation,
                None,
            ),
        },
        recording_reasons={
            move_update.op_id: ItemRecordingReason.RECORD_WRITE_FAILED
        },
        bytes_done_high_water=61,
    )
    candidates = PostCopySelection(
        candidates=(
            PostCopyCandidate(
                item_id=str(copy.op_id),
                root=Path(plan.target_root.path),
                display_path=copy.target_rel_path,
                expected_stat=copy_attestation.subject,
                copy_attestation=copy_attestation,
                recorded_identity=PostCopyRecordIdentity(
                    row_id=copy_identity.row_id,
                    location_id=copy_identity.location_id,
                    scope_token=copy_identity.scope_token,
                    rel_path_key=copy_identity.rel_path_key,
                ),
            ),
            PostCopyCandidate(
                item_id=str(move_update.op_id),
                root=Path(plan.target_root.path),
                display_path=move_update.target_rel_path,
                expected_stat=move_update_attestation.subject,
                copy_attestation=move_update_attestation,
                recorded_identity=None,
            ),
        ),
        _completed_bytes={str(copy.op_id): copy.content_bytes},
        _processed_bytes=copy.content_bytes,
    )
    return ExecutionRequest(
        VerifyContinuation(
            execution_set=xset,
            candidates=candidates,
            filesystem_status=SessionState.FAILED,
            recording=RecordingStatus.DEGRADED,
            execute_phase=PhaseResult(
                phase="execute",
                status=PhaseStatus.FAILED,
                items_done=5,
                items_total=len(selection),
                bytes_done=61,
                bytes_total=61,
                error="one selected operation failed",
            ),
            missing_evidence_ids=(str(update.op_id),),
        ),
        NOW,
    )


def test_execution_request_preserves_the_old_execution_set_keyword() -> None:
    xset = _rich_execution_request().execution_set

    request = ExecutionRequest(execution_set=xset, started_at=NOW)

    assert isinstance(request.continuation, ExecuteContinuation)
    assert request.execution_set is xset
    assert request.started_at == NOW


@pytest.mark.parametrize(
    "started_at",
    [
        datetime(2026, 7, 19, 12, 30),
        datetime(
            2026,
            7,
            19,
            12,
            30,
            tzinfo=timezone(timedelta(hours=1)),
        ),
    ],
)
def test_execution_request_rejects_non_utc_start_times(
    started_at: datetime,
) -> None:
    with pytest.raises(ValueError, match="timezone-aware|UTC"):
        ExecutionRequest(
            _rich_execution_request().execution_set,
            started_at,
        )


def test_execution_payload_is_a_lossless_round_trip() -> None:
    original = _rich_execution_request()

    decoded = decode_execution_request(encode_execution_request(original))

    assert isinstance(decoded.continuation, ExecuteContinuation)
    assert decoded.continuation.verify_after_execute
    assert decoded.started_at == original.started_at
    assert decoded.execution_set.plan == original.execution_set.plan
    assert decoded.execution_set.selection == original.execution_set.selection
    assert decoded.execution_set.status == original.execution_set.status
    assert decoded.execution_set.commitment == original.execution_set.commitment
    assert (
        decoded.execution_set.published_evidence
        == original.execution_set.published_evidence
    )
    assert decoded.execution_set.recording is RecordingStatus.DEGRADED
    assert decoded.execution_set.bytes_done_high_water == 17
    assert str(decoded.execution_set.run_id) == str(original.execution_set.run_id)


def test_execution_validation_and_encoding_do_not_rebuild_valid_graphs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _rich_verify_request()
    encoded = encode_execution_request(original)
    decoded = decode_execution_request(encoded)

    def forbid_reconstruction(*_args, **_kwargs):
        raise AssertionError("valid execution validation rebuilt a contract")

    monkeypatch.setattr(Plan, "__post_init__", forbid_reconstruction)
    monkeypatch.setattr(ExecutionSet, "__init__", forbid_reconstruction)

    assert not hasattr(execution_module, "ExecutionOperationFact")
    assert not hasattr(execution_module, "_published_evidence_fact")

    validate_execution_set(decoded.execution_set)

    assert encode_execution_request(decoded) == encoded


@pytest.mark.parametrize(
    ("field_name", "replacement", "message"),
    (
        ("algorithm", type("TextSubtype", (str,), {})("xxh3_128"), "algorithm"),
        ("digest", type("BytesSubtype", (bytes,), {})(b"\x02" * 16), "digest"),
        (
            "observed_at",
            type("DatetimeSubtype", (datetime,), {})(
                2026,
                7,
                19,
                12,
                30,
                tzinfo=timezone.utc,
            ),
            "time",
        ),
    ),
)
def test_execution_validation_requires_exact_content_evidence_shape(
    field_name: str,
    replacement: object,
    message: str,
) -> None:
    execution_set = _rich_execution_request().execution_set
    copy = execution_set.plan.operations[1]
    evidence = execution_set.published_evidence[copy.op_id]
    content = replace(
        evidence.attestation.content,
        **{field_name: replacement},
    )
    execution_set.published_evidence[copy.op_id] = replace(
        evidence,
        attestation=replace(evidence.attestation, content=content),
    )

    with pytest.raises(TypeError, match=message):
        validate_execution_set(execution_set)


def test_execution_encoder_orders_charge_validation_and_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _rich_execution_request()
    calls: list[str] = []
    original_charge = payload_module._charge_execution_request
    original_validate = payload_module.validate_execution_set
    original_projection = payload_module._execution_set

    def track_charge(value):
        calls.append("charge")
        return original_charge(value)

    def track_validation(value):
        calls.append("validate")
        return original_validate(value)

    def track_projection(value):
        calls.append("project")
        return original_projection(value)

    monkeypatch.setattr(
        payload_module,
        "_charge_execution_request",
        track_charge,
    )
    monkeypatch.setattr(
        payload_module,
        "validate_execution_set",
        track_validation,
    )
    monkeypatch.setattr(payload_module, "_execution_set", track_projection)

    encode_execution_request(request)

    assert calls == ["charge", "validate", "project"]


@pytest.mark.parametrize(
    ("contradiction", "message"),
    (
        ("status", "successful operation status"),
        ("content-size", "reviewed content bytes"),
        ("scope", "scope token does not match"),
        ("path", "relative path key does not match"),
        ("location", "share one target location"),
        ("recording", "cannot carry a recorded identity"),
    ),
)
def test_execution_mutable_contradictions_fail_before_projection(
    monkeypatch: pytest.MonkeyPatch,
    contradiction: str,
    message: str,
) -> None:
    request = _rich_verify_request()
    execution_set = request.execution_set
    copy = execution_set.plan.operations[1]
    move_update = execution_set.plan.operations[4]
    evidence = execution_set.published_evidence[copy.op_id]
    identity = evidence.recorded_identity
    assert identity is not None

    if contradiction == "status":
        execution_set.status[copy.op_id] = Outcome.FAILED
    elif contradiction == "content-size":
        content_size = copy.content_bytes + 1
        execution_set.published_evidence[copy.op_id] = PublishedCopyEvidence(
            Attestation(
                replace(evidence.attestation.content, size=content_size),
                replace(evidence.attestation.subject, size=content_size),
            ),
            identity,
        )
    elif contradiction == "scope":
        execution_set.published_evidence[copy.op_id] = replace(
            evidence,
            recorded_identity=replace(identity, scope_token="c" * 32),
        )
    elif contradiction == "path":
        execution_set.published_evidence[copy.op_id] = replace(
            evidence,
            recorded_identity=replace(identity, rel_path_key="OTHER.BIN"),
        )
    elif contradiction == "location":
        move_evidence = execution_set.published_evidence[move_update.op_id]
        execution_set.published_evidence[move_update.op_id] = replace(
            move_evidence,
            recorded_identity=replace(
                _copy_identity(move_update, "b" * 32),
                location_id="10",
            ),
        )
        del execution_set.recording_reasons[move_update.op_id]
    else:
        execution_set.recording_reasons[copy.op_id] = (
            ItemRecordingReason.RECORD_WRITE_FAILED
        )

    def forbid_projection(*_args, **_kwargs):
        raise AssertionError("mutable contradiction reached projection")

    monkeypatch.setattr(payload_module, "_execution_set", forbid_projection)
    with pytest.raises(ValueError, match=message):
        encode_execution_request(request)


def test_execution_v7_round_trips_the_reported_exclusion_count() -> None:
    original = _rich_execution_request()
    continuation = replace(
        original.continuation,
        reported_exclusion_count=2,
    )
    request = ExecutionRequest(continuation, original.started_at)

    decoded = decode_execution_request(encode_execution_request(request))

    assert isinstance(decoded.continuation, ExecuteContinuation)
    assert decoded.continuation.reported_exclusion_count == 2
    assert encode_execution_request(decoded) == encode_execution_request(request)


@pytest.mark.parametrize(
    "value",
    (True, 1.5, "1", -1, MAX_SAFE_INTEGER + 1),
)
def test_execution_v7_rejects_invalid_reported_exclusion_counts(
    value: object,
) -> None:
    payload = json.loads(encode_execution_request(_rich_execution_request()))
    payload["reported_exclusion_count"] = value

    with pytest.raises((TypeError, ValueError)):
        decode_execution_request(json.dumps(payload).encode("utf-8"))


def test_execution_payload_preserves_full_width_file_identity_as_text() -> None:
    plan = _rich_plan(identity_index=MAX_FILE_INDEX_128)
    encoded = encode_execution_request(_rich_execution_request(plan=plan))
    value = json.loads(encoded)
    identity = value["execution_set"]["plan"]["operations"][1][
        "source_expected"
    ]["identity"]

    assert identity["file_index"] == str(MAX_FILE_INDEX_128)
    decoded = decode_execution_request(encoded)
    decoded_identity = decoded.execution_set.plan.operations[1].source_expected
    assert decoded_identity is not None
    assert decoded_identity.file_identity is not None
    assert decoded_identity.file_identity.file_index == MAX_FILE_INDEX_128

    for invalid in (MAX_FILE_INDEX_128, "01", str(MAX_FILE_INDEX_128 + 1)):
        malformed = json.loads(encoded)
        malformed["execution_set"]["plan"]["operations"][1][
            "source_expected"
        ]["identity"]["file_index"] = invalid
        with pytest.raises((TypeError, ValueError)):
            decode_execution_request(json.dumps(malformed).encode("utf-8"))


@pytest.mark.parametrize(
    ("invalid", "error_type"),
    (
        (None, TypeError),
        (True, TypeError),
        (17, TypeError),
        ("01", ValueError),
        ("-1", ValueError),
        ("340282366920938463463374607431768211456", ValueError),
    ),
)
def test_execution_payload_file_identity_preserves_exact_error_family(
    invalid: object, error_type: type[Exception]
) -> None:
    plan = _rich_plan(identity_index=MAX_FILE_INDEX_128)
    value = json.loads(encode_execution_request(_rich_execution_request(plan=plan)))
    value["execution_set"]["plan"]["operations"][1]["source_expected"][
        "identity"
    ]["file_index"] = invalid

    with pytest.raises(error_type) as raised:
        decode_execution_request(json.dumps(value).encode("utf-8"))
    assert type(raised.value) is error_type


def test_execution_set_byte_high_water_is_bounded_and_strictly_monotonic() -> None:
    xset = _rich_execution_request().execution_set

    xset.note_bytes_done(23)
    xset.note_bytes_done(23)

    assert xset.bytes_done_high_water == 23
    with pytest.raises(ValueError, match="cannot regress"):
        xset.note_bytes_done(22)
    with pytest.raises(ValueError, match="exceeds selected content"):
        xset.note_bytes_done(10**9)
    with pytest.raises(TypeError, match="non-Boolean integer"):
        xset.note_bytes_done(True)
    assert xset.bytes_done_high_water == 23


def test_execution_set_exposes_public_byte_high_water_state() -> None:
    execution_fields = {item.name: item for item in fields(ExecutionSet)}

    high_water = execution_fields["bytes_done_high_water"]
    assert high_water.init
    assert high_water.compare
    assert not high_water.repr

    selected_bound = execution_fields["_selected_bytes_bound"]
    assert not selected_bound.init
    assert not selected_bound.compare
    assert not selected_bound.repr


def test_execution_set_replace_and_equality_use_only_public_high_water() -> None:
    original = _rich_execution_request().execution_set

    unchanged = replace(original)
    advanced = replace(original, bytes_done_high_water=18)

    assert unchanged.bytes_done_high_water == 17
    assert unchanged == original
    assert advanced != original

    # The selected-byte bound is a derived validation cache, not continuation
    # identity. Its compare metadata prevents it from changing equality.
    unchanged._selected_bytes_bound += 1
    assert unchanged == original


@pytest.mark.parametrize(
    ("high_water", "error", "match"),
    [
        (True, TypeError, "non-Boolean integer"),
        (-1, ValueError, "nonnegative signed-64 domain"),
        (10**9, ValueError, "exceeds selected content"),
    ],
)
def test_execution_set_rejects_invalid_initial_byte_high_water(
    high_water: object,
    error: type[Exception],
    match: str,
) -> None:
    xset = _rich_execution_request().execution_set

    with pytest.raises(error, match=match):
        replace(xset, bytes_done_high_water=high_water)


def test_execution_payload_round_trips_canonical_user_deselection() -> None:
    original = _rich_execution_request()
    recase = original.execution_set.plan.operations[8]
    selection = original.execution_set.selection - {recase.op_id}
    changed_set = replace(
        original.execution_set,
        selection=selection,
        commitment=Commitment(
            original.execution_set.plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
        user_deselected=frozenset({recase.op_id}),
    )

    encoded = encode_execution_request(
        ExecutionRequest(
            replace(original.continuation, execution_set=changed_set),
            original.started_at,
        )
    )
    decoded = decode_execution_request(encoded)

    assert decoded.execution_set.user_deselected == frozenset({recase.op_id})
    assert encode_execution_request(decoded) == encoded


@pytest.mark.parametrize("shape", ["missing", "unknown"])
def test_execution_payload_requires_exact_byte_high_water_field(
    shape: str,
) -> None:
    value = json.loads(encode_execution_request(_rich_execution_request()))
    if shape == "missing":
        del value["execution_set"]["bytes_done_high_water"]
    else:
        value["execution_set"]["unexpected_byte_progress"] = 17

    with pytest.raises(ValueError, match="missing|unexpected"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_execution_payload_v7_keeps_progress_and_recording_attribution() -> None:
    encoded = encode_execution_request(_rich_execution_request())
    value = json.loads(encoded)

    assert value["schema_version"] == 7
    assert set(value["execution_set"]) == {
        "plan",
        "selection",
        "user_deselected",
        "run_id",
        "status",
        "commitment",
        "published_evidence",
        "recording",
        "recording_reasons",
        "recording_issues",
        "omitted_detail_count",
        "bytes_done_high_water",
    }
    assert value["execution_set"]["bytes_done_high_water"] == 17
    assert value["execution_set"]["recording_reasons"] == {}
    assert value["execution_set"]["recording_issues"] == [
        {
            "reason": "final-flush-failed",
            "detail": "RuntimeError: final flush failed",
        }
    ]
    assert value["execution_set"]["omitted_detail_count"] == 0
    assert (
        encode_execution_request(decode_execution_request(encoded)) == encoded
    )


def test_execution_payload_v7_pins_closed_recording_reason_vocabularies() -> None:
    assert len(_EXECUTION_V7_ITEM_RECORDING_REASONS) == 3
    assert {
        reason.value for reason in ItemRecordingReason
    } == _EXECUTION_V7_ITEM_RECORDING_REASONS
    assert len(_EXECUTION_V7_TASK_RECORDING_ISSUE_REASONS) == 5
    assert {
        reason.value for reason in TaskRecordingIssueReason
    } == _EXECUTION_V7_TASK_RECORDING_ISSUE_REASONS


def test_execution_payload_v7_rejects_unknown_raw_item_recording_reason() -> None:
    value = json.loads(encode_execution_request(_rich_verify_request()))
    move_update_id = str(_op_id(5))
    value["execution_set"]["recording_reasons"][move_update_id] = (
        "unknown-item-recording-reason"
    )

    with pytest.raises(ValueError, match="unknown-item-recording-reason"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_execution_payload_v7_rejects_unknown_raw_task_recording_reason() -> None:
    value = json.loads(encode_execution_request(_rich_execution_request()))
    value["execution_set"]["recording_issues"][0]["reason"] = (
        "unknown-task-recording-reason"
    )

    with pytest.raises(ValueError, match="unknown-task-recording-reason"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_execution_payload_v7_rejects_aggregate_recording_contradictions() -> None:
    task_attribution = json.loads(
        encode_execution_request(_rich_execution_request())
    )
    task_attribution["execution_set"]["recording"] = "ok"
    with pytest.raises(
        ValueError,
        match="aggregate recording contradicts its item/task attribution",
    ):
        decode_execution_request(json.dumps(task_attribution).encode("utf-8"))

    item_attribution = json.loads(
        encode_execution_request(_rich_verify_request())
    )
    item_attribution["execution_set"]["recording"] = "ok"
    with pytest.raises(
        ValueError,
        match="aggregate recording contradicts its item/task attribution",
    ):
        decode_execution_request(json.dumps(item_attribution).encode("utf-8"))

    no_attribution = json.loads(
        encode_execution_request(_rich_execution_request())
    )
    no_attribution["execution_set"]["recording_issues"] = []
    with pytest.raises(
        ValueError,
        match="aggregate recording contradicts its item/task attribution",
    ):
        decode_execution_request(json.dumps(no_attribution).encode("utf-8"))


def test_task_recording_issues_retain_first_reason_in_observation_order() -> None:
    xset = _rich_execution_request().execution_set

    xset.note_task_recording_issue(
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
        "OSError: open failed",
    )
    xset.note_task_recording_issue(
        TaskRecordingIssueReason.FINAL_FLUSH_FAILED,
        "later duplicate must not replace the first detail",
    )

    assert xset.recording_issues == (
        TaskRecordingIssue(
            TaskRecordingIssueReason.FINAL_FLUSH_FAILED,
            "RuntimeError: final flush failed",
        ),
        TaskRecordingIssue(
            TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
            "OSError: open failed",
        ),
    )
    decoded = decode_execution_request(
        encode_execution_request(ExecutionRequest(ExecuteContinuation(xset), NOW))
    )
    assert decoded.execution_set.recording_issues == xset.recording_issues


def test_task_recording_issue_omits_overlimit_detail_without_truncation() -> None:
    xset = _rich_execution_request().execution_set
    overlimit = "é" * 513

    xset.note_task_recording_issue(
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
        overlimit,
    )

    assert xset.recording_issues[-1] == TaskRecordingIssue(
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
        None,
    )
    assert xset.omitted_detail_count == 1
    decoded = decode_execution_request(
        encode_execution_request(ExecutionRequest(ExecuteContinuation(xset), NOW))
    )
    assert decoded.execution_set.omitted_detail_count == 1
    assert decoded.execution_set.recording_issues == xset.recording_issues
    with pytest.raises(ValueError, match="detail exceeds"):
        TaskRecordingIssue(
            TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
            overlimit,
        )


@pytest.mark.parametrize("high_water", [True, 1.5, -1, 10**9])
def test_execution_payload_rejects_invalid_byte_high_water(
    high_water: object,
) -> None:
    value = json.loads(encode_execution_request(_rich_execution_request()))
    value["execution_set"]["bytes_done_high_water"] = high_water

    with pytest.raises((TypeError, ValueError), match="integer|negative|exceeds"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


@pytest.mark.parametrize("shape", ["missing", "unknown"])
def test_execution_payload_requires_exact_user_deselection_field(
    shape: str,
) -> None:
    value = json.loads(encode_execution_request(_rich_execution_request()))
    if shape == "missing":
        del value["execution_set"]["user_deselected"]
    else:
        value["execution_set"]["unexpected_user_selection"] = []

    with pytest.raises(ValueError, match="missing|unexpected"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_verify_continuation_is_a_lossless_round_trip() -> None:
    original = _rich_verify_request()

    encoded = encode_execution_request(original)
    decoded = decode_execution_request(encoded)

    assert isinstance(decoded.continuation, VerifyContinuation)
    assert decoded.started_at == original.started_at
    assert decoded.continuation == original.continuation
    assert decoded.continuation.candidates.completed_bytes == {
        str(_op_id(2)): 11
    }
    assert decoded.continuation.candidates.processed_bytes == 11
    assert decoded.execution_set.bytes_done_high_water == 61
    assert encode_execution_request(decoded) == encoded


def test_execute_and_verify_payloads_have_exact_phase_branches() -> None:
    execute = json.loads(
        encode_execution_request(_rich_execution_request())
    )
    verify = json.loads(encode_execution_request(_rich_verify_request()))

    assert set(execute) == {
        "schema_version",
        "kind",
        "phase",
        "execution_set",
        "started_at",
        "verify_after_execute",
        "reported_exclusion_count",
    }
    assert set(verify) == {
        "schema_version",
        "kind",
        "phase",
        "execution_set",
        "started_at",
        "candidates",
        "filesystem_status",
        "recording",
        "execute_phase",
        "missing_evidence_ids",
    }


def test_execution_payload_rejects_missing_unknown_and_contradictory_phase_fields() -> None:
    execute = json.loads(
        encode_execution_request(_rich_execution_request())
    )
    del execute["reported_exclusion_count"]
    with pytest.raises((KeyError, ValueError), match="reported_exclusion_count|missing"):
        decode_execution_request(json.dumps(execute).encode("utf-8"))

    execute = json.loads(
        encode_execution_request(_rich_execution_request())
    )
    del execute["phase"]
    with pytest.raises(ValueError, match="phase discriminator"):
        decode_execution_request(json.dumps(execute).encode("utf-8"))

    execute = json.loads(
        encode_execution_request(_rich_execution_request())
    )
    execute["phase"] = "other"
    with pytest.raises(ValueError, match="unsupported execution continuation phase"):
        decode_execution_request(json.dumps(execute).encode("utf-8"))

    execute = json.loads(
        encode_execution_request(_rich_execution_request())
    )
    execute["candidates"] = {}
    with pytest.raises(ValueError, match="unexpected"):
        decode_execution_request(json.dumps(execute).encode("utf-8"))

    verify = json.loads(encode_execution_request(_rich_verify_request()))
    verify["reported_exclusion_count"] = 0
    with pytest.raises(ValueError, match="unexpected"):
        decode_execution_request(json.dumps(verify).encode("utf-8"))

    verify = json.loads(encode_execution_request(_rich_verify_request()))
    del verify["execute_phase"]
    with pytest.raises(ValueError, match="missing"):
        decode_execution_request(json.dumps(verify).encode("utf-8"))


@pytest.mark.parametrize(
    "identity_kind",
    ["published", "candidate"],
)
def test_execution_payload_rejects_partial_recording_identities(
    identity_kind: str,
) -> None:
    value = json.loads(encode_execution_request(_rich_verify_request()))
    copy_id = str(_op_id(2))
    if identity_kind == "published":
        identity = value["execution_set"]["published_evidence"][copy_id][
            "recorded_identity"
        ]
    else:
        identity = value["candidates"]["candidates"][0][
            "recorded_identity"
        ]
    del identity["scope_token"]

    with pytest.raises(ValueError, match="missing"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_verify_continuation_rejects_contradictory_truth_axes() -> None:
    value = json.loads(encode_execution_request(_rich_verify_request()))
    value["recording"] = RecordingStatus.OK.value
    with pytest.raises(ValueError, match="cannot recover degraded"):
        decode_execution_request(json.dumps(value).encode("utf-8"))

    value = json.loads(encode_execution_request(_rich_verify_request()))
    value["filesystem_status"] = SessionState.COMPLETED.value
    with pytest.raises(ValueError, match="disagrees"):
        decode_execution_request(json.dumps(value).encode("utf-8"))

    value = json.loads(encode_execution_request(_rich_verify_request()))
    value["filesystem_status"] = SessionState.CANCELED.value
    value["execute_phase"]["status"] = PhaseStatus.CANCELED.value
    with pytest.raises(ValueError, match="terminal"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_verify_continuation_accepts_only_a_bounded_canonical_execute_error() -> None:
    continuation = _rich_verify_request().continuation
    assert isinstance(continuation, VerifyContinuation)
    exact = replace(
        continuation,
        execute_phase=replace(continuation.execute_phase, error="x" * 1024),
    )

    assert exact.execute_phase.error == "x" * 1024
    decoded = decode_execution_request(
        encode_execution_request(ExecutionRequest(exact, NOW))
    )
    assert decoded.continuation.execute_phase.error == "x" * 1024

    with pytest.raises(ValueError, match="execute phase error"):
        replace(
            continuation,
            execute_phase=replace(
                continuation.execute_phase,
                error="x" * 1025,
            ),
        )
    with pytest.raises(ValueError, match="execute phase error"):
        replace(
            continuation,
            execute_phase=replace(
                continuation.execute_phase,
                error="\ud800",
            ),
        )
    with pytest.raises(TypeError, match="error"):
        replace(
            continuation,
            execute_phase=replace(continuation.execute_phase, error=object()),
        )


def test_verify_continuation_snapshots_phase_subclasses_without_hidden_graphs() -> None:
    class HiddenPhase(PhaseResult):
        pass

    continuation = _rich_verify_request().continuation
    assert isinstance(continuation, VerifyContinuation)
    source = continuation.execute_phase
    subclass = HiddenPhase(
        source.phase,
        source.status,
        source.items_done,
        source.items_total,
        source.bytes_done,
        source.bytes_total,
        source.error,
    )
    object.__setattr__(subclass, "hidden_graph", ["hidden"])

    admitted = replace(continuation, execute_phase=subclass)

    assert type(admitted.execute_phase) is PhaseResult
    assert admitted.execute_phase == source
    assert admitted.execute_phase is not subclass
    assert not hasattr(admitted.execute_phase, "hidden_graph")


def test_verify_continuation_reads_the_source_phase_name_once() -> None:
    class HiddenText(str):
        pass

    class AlternatingPhase(PhaseResult):
        def __getattribute__(self, name):
            if name == "phase":
                try:
                    reads = object.__getattribute__(self, "phase_reads")
                except AttributeError:
                    return object.__getattribute__(self, name)
                object.__setattr__(self, "phase_reads", reads + 1)
                if reads == 0:
                    return "execute"
                return object.__getattribute__(self, "alternate_phase")
            return object.__getattribute__(self, name)

    continuation = _rich_verify_request().continuation
    assert isinstance(continuation, VerifyContinuation)
    phase = continuation.execute_phase
    source = AlternatingPhase(
        phase.phase,
        phase.status,
        phase.items_done,
        phase.items_total,
        phase.bytes_done,
        phase.bytes_total,
        phase.error,
    )
    alternate = HiddenText("execute")
    object.__setattr__(alternate, "hidden_graph", ["hidden"])
    object.__setattr__(source, "phase_reads", 0)
    object.__setattr__(source, "alternate_phase", alternate)

    admitted = replace(continuation, execute_phase=source)

    assert type(admitted.execute_phase.phase) is str
    assert not hasattr(admitted.execute_phase.phase, "hidden_graph")


def test_verify_continuation_phase_snapshot_breaks_the_source_alias() -> None:
    continuation = _rich_verify_request().continuation
    assert isinstance(continuation, VerifyContinuation)
    source = replace(continuation.execute_phase, error="bounded source")

    admitted = replace(continuation, execute_phase=source)
    object.__setattr__(source, "error", "x" * 1025)
    object.__setattr__(source, "items_done", -1)

    assert admitted.execute_phase.error == "bounded source"
    assert admitted.execute_phase.items_done == continuation.execute_phase.items_done
    decoded = decode_execution_request(
        encode_execution_request(ExecutionRequest(admitted, NOW))
    )
    assert decoded.continuation.execute_phase == admitted.execute_phase


def test_verify_continuation_rejects_a_forged_phase_instance() -> None:
    continuation = _rich_verify_request().continuation
    assert isinstance(continuation, VerifyContinuation)
    source = continuation.execute_phase
    forged = object.__new__(PhaseResult)
    for name, value in (
        ("phase", source.phase),
        ("status", source.status),
        ("items_done", -1),
        ("items_total", source.items_total),
        ("bytes_done", source.bytes_done),
        ("bytes_total", source.bytes_total),
        ("error", source.error),
    ):
        object.__setattr__(forged, name, value)

    with pytest.raises(ValueError, match="items_done"):
        replace(continuation, execute_phase=forged)


def test_execution_encoder_revalidates_mutated_verify_phase() -> None:
    continuation = _rich_verify_request().continuation
    assert isinstance(continuation, VerifyContinuation)
    object.__setattr__(continuation.execute_phase, "items_done", -1)

    with pytest.raises(ValueError, match="items_done"):
        encode_execution_request(ExecutionRequest(continuation, NOW))


@pytest.mark.parametrize("error", ["x" * 1025, "\ud800", 7])
def test_execution_v7_refuses_hostile_verify_execute_errors(error: object) -> None:
    value = json.loads(encode_execution_request(_rich_verify_request()))
    value["execute_phase"]["error"] = error

    with pytest.raises((TypeError, ValueError)):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_verify_continuation_rejects_unknown_completion_and_candidate_drift() -> None:
    value = json.loads(encode_execution_request(_rich_verify_request()))
    value["candidates"]["completed_bytes"][0]["item_id"] = str(_op_id(3))
    with pytest.raises(ValueError, match="unknown item id"):
        decode_execution_request(json.dumps(value).encode("utf-8"))

    value = json.loads(encode_execution_request(_rich_verify_request()))
    value["missing_evidence_ids"] = []
    with pytest.raises(ValueError, match="equal successful publishes"):
        decode_execution_request(json.dumps(value).encode("utf-8"))

    value = json.loads(encode_execution_request(_rich_verify_request()))
    value["missing_evidence_ids"].append(str(_op_id(2)))
    with pytest.raises(ValueError, match="disjoint"):
        decode_execution_request(json.dumps(value).encode("utf-8"))

    value = json.loads(encode_execution_request(_rich_verify_request()))
    value["candidates"]["candidates"].reverse()
    with pytest.raises(ValueError, match="retain plan order"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_execution_set_rejects_published_evidence_on_non_byte_operation() -> None:
    value = json.loads(encode_execution_request(_rich_execution_request()))
    evidence = value["execution_set"]["published_evidence"].pop(
        str(_op_id(2))
    )
    value["execution_set"]["published_evidence"][str(_op_id(1))] = evidence

    with pytest.raises(ValueError, match="non-byte-producing"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_execution_set_rejects_identityless_evidence_with_only_a_task_issue() -> None:
    value = json.loads(encode_execution_request(_rich_execution_request()))
    copy_id = str(_op_id(2))
    value["execution_set"]["published_evidence"][copy_id][
        "recorded_identity"
    ] = None

    with pytest.raises(
        ValueError,
        match="requires that operation's record-write-failed reason",
    ):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_execution_set_accepts_identityless_evidence_for_that_record_failure() -> None:
    value = json.loads(encode_execution_request(_rich_execution_request()))
    copy_id = str(_op_id(2))
    value["execution_set"]["published_evidence"][copy_id][
        "recorded_identity"
    ] = None
    value["execution_set"]["recording_reasons"][copy_id] = (
        ItemRecordingReason.RECORD_WRITE_FAILED.value
    )

    decoded = decode_execution_request(json.dumps(value).encode("utf-8"))

    assert decoded.execution_set.recording is RecordingStatus.DEGRADED
    assert decoded.execution_set.recording_reasons == {
        _op_id(2): ItemRecordingReason.RECORD_WRITE_FAILED
    }
    assert (
        decoded.execution_set.published_evidence[
            _op_id(2)
        ].recorded_identity
        is None
    )


def test_execution_set_rejects_record_failure_with_a_durable_identity() -> None:
    value = json.loads(encode_execution_request(_rich_execution_request()))
    copy_id = str(_op_id(2))
    value["execution_set"]["recording_reasons"][copy_id] = (
        ItemRecordingReason.RECORD_WRITE_FAILED.value
    )

    with pytest.raises(ValueError, match="cannot carry a recorded identity"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        (
            "scope_token",
            "c" * 32,
            "scope token does not match the execution run",
        ),
        (
            "rel_path_key",
            "OTHER.BIN",
            "relative path key does not match its operation",
        ),
    ],
)
def test_execution_set_rejects_recorded_identity_drift_from_run_or_operation(
    field: str,
    replacement: str,
    message: str,
) -> None:
    value = json.loads(encode_execution_request(_rich_execution_request()))
    copy_id = str(_op_id(2))
    identity = value["execution_set"]["published_evidence"][copy_id][
        "recorded_identity"
    ]
    identity[field] = replacement

    with pytest.raises(ValueError, match=message):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_execution_set_rejects_recorded_identities_from_multiple_locations() -> None:
    value = json.loads(encode_execution_request(_rich_verify_request()))
    move_update_id = str(_op_id(5))
    value["execution_set"]["published_evidence"][move_update_id][
        "recorded_identity"
    ] = {
        "row_id": f"row-{move_update_id}",
        "location_id": "location-other",
        "scope_token": "b" * 32,
        "rel_path_key": normalize_relative_path("moved-changed.bin"),
    }
    del value["execution_set"]["recording_reasons"][move_update_id]
    value["execution_set"]["recording"] = RecordingStatus.OK.value

    with pytest.raises(ValueError, match="share one target location"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


@pytest.mark.parametrize("text", ("\ud800", "\udcff", "\ud83d\ude00"))
def test_root_contract_rejects_surrogate_code_units(text: str) -> None:
    original = _rich_execution_request()
    with pytest.raises(ValueError, match="valid Unicode"):
        replace(
            original.execution_set.plan.source_root,
            root_id="source_" + text,
        )


@pytest.mark.parametrize("text", ("\ud800", "\udcff"))
@pytest.mark.parametrize("position", ("key", "value"))
def test_execution_payload_decoding_rejects_escaped_surrogates(text: str, position: str) -> None:
    value = json.loads(encode_execution_request(_rich_execution_request()))
    root = value["execution_set"]["plan"]["source_root"]
    root[text if position == "key" else "root_id"] = "unexpected" if position == "key" else text
    with pytest.raises(ValueError, match="valid Unicode"):
        decode_execution_request(json.dumps(value).encode("utf-8"))


def test_execution_payload_preserves_scalar_unicode_and_commitment() -> None:
    original = _rich_execution_request()
    changed_plan = replace(
        original.execution_set.plan,
        source_root=replace(
            original.execution_set.plan.source_root,
            root_id="source_\u00e9\U0001f600-" + r"\ud800",
        ),
        fingerprint=PlanFingerprint("0" * 64),
    )
    changed_plan = replace(changed_plan, fingerprint=plan_fingerprint(changed_plan))
    changed_set = replace(
        original.execution_set,
        plan=changed_plan,
        commitment=replace(original.execution_set.commitment, plan_fingerprint=changed_plan.fingerprint),
    )
    request = ExecutionRequest(changed_set, NOW)
    encoded = encode_execution_request(request)
    assert b"source_\xc3\xa9\xf0\x9f\x98\x80-\\\\ud800" in encoded
    decoded = decode_execution_request(encoded)
    assert decoded == request
    assert _commitment_error(decoded.execution_set) is None
    escaped = json.dumps(json.loads(encoded)).encode("utf-8")
    assert b"\\ud83d\\ude00" in escaped
    assert decode_execution_request(escaped) == request


def test_decoded_plan_recomputes_the_same_fingerprint() -> None:
    original = _rich_execution_request()

    decoded = decode_execution_request(encode_execution_request(original))

    assert plan_fingerprint(decoded.execution_set.plan) == original.execution_set.plan.fingerprint


@pytest.mark.parametrize(
    ("request_factory", "encoder", "decoder", "limit_name"),
    (
        (
            lambda: PlanRequest("bounded-plan", r"C:\source", r"D:\target"),
            encode_plan_request,
            decode_plan_request,
            "PLAN_REQUEST_PAYLOAD_BYTE_LIMIT",
        ),
        (
            _rich_execution_request,
            encode_execution_request,
            decode_execution_request,
            "EXECUTION_REQUEST_PAYLOAD_BYTE_LIMIT",
        ),
    ),
)
def test_workflow_payload_raw_ceiling_precedes_decode_and_json_parse(
    monkeypatch: pytest.MonkeyPatch,
    request_factory,
    encoder,
    decoder,
    limit_name: str,
) -> None:
    request = request_factory()
    payload = encoder(request)
    monkeypatch.setattr(payload_module, limit_name, len(payload))

    assert decoder(payload) == request

    def forbidden_loads(*_args, **_kwargs):
        raise AssertionError("oversize payload reached json.loads")

    monkeypatch.setattr(payload_module.json, "loads", forbidden_loads)
    with pytest.raises(ValueError, match="byte ceiling"):
        decoder(payload + b" ")
    with pytest.raises(TypeError, match="exact bytes"):
        decoder(bytearray(payload))


def test_plan_occurrence_ceiling_precedes_json_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = PlanRequest("bounded-plan", r"C:\source", r"D:\target")
    charge = payload_module._charge_plan_request(request).occurrence_charge
    monkeypatch.setattr(payload_module, "_PLAN_REQUEST_MAX_OCCURRENCE_CHARGE", charge)
    encode_plan_request(request)
    monkeypatch.setattr(
        payload_module,
        "_PLAN_REQUEST_MAX_OCCURRENCE_CHARGE",
        charge - 1,
    )

    def forbidden_json(*_args, **_kwargs):
        raise AssertionError("over-budget request reached JSON projection")

    monkeypatch.setattr(payload_module, "_json_bytes", forbidden_json)
    with pytest.raises(ValueError, match="occurrence bound"):
        encode_plan_request(request)


def test_execution_occurrence_ceiling_precedes_projection_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _rich_execution_request()
    charge = payload_module._charge_execution_request(request).occurrence_charge
    status_before = dict(request.execution_set.status)
    evidence_before = dict(request.execution_set.published_evidence)
    monkeypatch.setattr(payload_module, "_EXECUTE_MAX_OCCURRENCE_CHARGE", charge)
    encode_execution_request(request)
    monkeypatch.setattr(payload_module, "_EXECUTE_MAX_OCCURRENCE_CHARGE", charge - 1)

    def forbidden_validation(*_args, **_kwargs):
        raise AssertionError("over-budget continuation reached validation")

    def forbidden_projection(*_args, **_kwargs):
        raise AssertionError("over-budget continuation reached projection")

    monkeypatch.setattr(
        payload_module,
        "validate_execution_set",
        forbidden_validation,
    )
    monkeypatch.setattr(payload_module, "_execution_set", forbidden_projection)
    with pytest.raises(ValueError, match="occurrence bound"):
        encode_execution_request(request)
    assert request.execution_set.status == status_before
    assert request.execution_set.published_evidence == evidence_before


def test_plan_preprojection_readmits_forged_filter_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = PlanRequest(
        "bounded-plan",
        r"C:\source",
        r"D:\target",
        SyncOptions(filters=FilterSet(())),
    )
    object.__setattr__(request.options.filters, "patterns", ("x" * 1_025,))

    def forbidden_json(*_args, **_kwargs):
        raise AssertionError("invalid options reached JSON projection")

    monkeypatch.setattr(payload_module, "_json_bytes", forbidden_json)
    with pytest.raises(ValueError, match="UTF-8 text bound"):
        encode_plan_request(request)


@pytest.mark.parametrize(
    ("payload_request", "encoder"),
    (
        (PlanRequest("stable-plan", r"C:\source", r"D:\target"), encode_plan_request),
        (_rich_verify_request(), encode_execution_request),
    ),
)
def test_workflow_encoder_rechecks_exact_final_byte_length(
    monkeypatch: pytest.MonkeyPatch,
    payload_request: object,
    encoder,
) -> None:
    original_json_bytes = payload_module._json_bytes
    monkeypatch.setattr(
        payload_module,
        "_json_bytes",
        lambda value: original_json_bytes(value) + b" ",
    )

    with pytest.raises(RuntimeError, match="changed after JSON admission"):
        encoder(payload_request)


def test_verify_candidate_walk_charges_every_repeated_root_occurrence() -> None:
    request = _rich_verify_request()
    continuation = request.continuation
    assert isinstance(continuation, VerifyContinuation)
    candidate = continuation.candidates.candidates[0]
    one = payload_module.JsonEnvelopeCounter()
    payload_module._charge_post_copy_candidate(one, candidate, "candidate")
    repeated = payload_module.JsonEnvelopeCounter()
    for index in range(payload_module.MAX_PLAN_REVIEW_ROWS):
        payload_module._charge_post_copy_candidate(
            repeated,
            candidate,
            f"candidates[{index}]",
        )

    assert repeated.occurrence_charge == (
        payload_module.MAX_PLAN_REVIEW_ROWS * one.occurrence_charge
    )
    assert repeated.canonical_bytes == (
        payload_module.MAX_PLAN_REVIEW_ROWS * one.canonical_bytes
    )


def test_object_layout_charges_each_schema_key_string_occurrence() -> None:
    short = payload_module.object_layout("x")
    long = payload_module.object_layout("x" * 65)
    expected_delta = (
        payload_module.model_text_charge(65)
        - payload_module.model_text_charge(1)
    )

    assert payload_module.model_object_charge(long) == (
        payload_module.model_object_charge(short) + expected_delta
    )
    assert payload_module.canonical_byte_ceiling(
        payload_module.model_object_charge(long)
    ) > payload_module.canonical_byte_ceiling(
        payload_module.model_object_charge(short)
    )


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
