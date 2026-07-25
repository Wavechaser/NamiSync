"""Versioned JSON payloads passed opaquely through the dispatcher."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

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
    PublishedCopyEvidence,
    RecordedCopyIdentity,
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
    IdentityDestinationPolicy,
    OpId,
    OperationKind,
    OperationReason,
    Plan,
    PlanFingerprint,
    PlanOperation,
    PreservationPolicy,
    SyncOptions,
)
from namisync.core.session import PhaseResult, PhaseStatus, SessionState

from .models import (
    ExecuteContinuation,
    ExecutionRequest,
    PlanRequest,
    VerifyContinuation,
)


_SCHEMA_VERSION = 3


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", errors="backslashreplace")


def _volume(value: VolumeId | None) -> object:
    if value is None:
        return None
    return {"serial": value.serial, "fs_type": value.fs_type}


def _decode_volume(value: object, context: str) -> VolumeId | None:
    if value is None:
        return None
    item = _mapping(value)
    _expect_keys(item, {"serial", "fs_type"}, context)
    return VolumeId(
        _string(item["serial"], f"{context}.serial"),
        _string(item["fs_type"], f"{context}.fs_type"),
    )


def _volume_evidence(value: VolumeEvidence | None) -> object:
    if value is None:
        return None
    return {
        "label": value.label,
        "device_id": value.device_id,
        "clone_ambiguous": value.clone_ambiguous,
    }


def _decode_volume_evidence(
    value: object, context: str
) -> VolumeEvidence | None:
    if value is None:
        return None
    item = _mapping(value)
    _expect_keys(
        item,
        {"label", "device_id", "clone_ambiguous"},
        context,
    )
    return VolumeEvidence(
        label=_optional_string(item["label"], f"{context}.label"),
        device_id=_optional_string(item["device_id"], f"{context}.device_id"),
        clone_ambiguous=_boolean(
            item["clone_ambiguous"], f"{context}.clone_ambiguous"
        ),
    )


def _profile(value: CapabilityProfile) -> dict[str, object]:
    return {
        "fs_type": value.fs_type,
        "mtime_granularity_ns": value.mtime_granularity_ns,
        "stable_file_identity": value.stable_file_identity,
        "incurs_seek_penalty": value.incurs_seek_penalty,
        "max_path": value.max_path,
        "supports_ads": value.supports_ads,
        "supports_hardlinks": value.supports_hardlinks,
    }


def _decode_profile(value: object, context: str) -> CapabilityProfile:
    item = _mapping(value)
    _expect_keys(
        item,
        {
            "fs_type",
            "mtime_granularity_ns",
            "stable_file_identity",
            "incurs_seek_penalty",
            "max_path",
            "supports_ads",
            "supports_hardlinks",
        },
        context,
    )
    raw_seek = item["incurs_seek_penalty"]
    seek = (
        None
        if raw_seek is None
        else _boolean(raw_seek, f"{context}.incurs_seek_penalty")
    )
    return CapabilityProfile(
        fs_type=_string(item["fs_type"], f"{context}.fs_type"),
        mtime_granularity_ns=_integer(
            item["mtime_granularity_ns"], f"{context}.mtime_granularity_ns"
        ),
        stable_file_identity=_boolean(
            item["stable_file_identity"], f"{context}.stable_file_identity"
        ),
        incurs_seek_penalty=seek,
        max_path=_integer(item["max_path"], f"{context}.max_path"),
        supports_ads=_boolean(
            item["supports_ads"], f"{context}.supports_ads"
        ),
        supports_hardlinks=_boolean(
            item["supports_hardlinks"], f"{context}.supports_hardlinks"
        ),
    )


def _metadata(value: MetadataSnapshot | None) -> object:
    if value is None:
        return None
    return {
        "attributes": value.attributes,
        "created_ns": value.created_ns,
    }


def _decode_metadata(
    value: object, context: str
) -> MetadataSnapshot | None:
    if value is None:
        return None
    item = _mapping(value)
    _expect_keys(item, {"attributes", "created_ns"}, context)
    return MetadataSnapshot(
        _integer(item["attributes"], f"{context}.attributes"),
        _optional_integer(item["created_ns"], f"{context}.created_ns"),
    )


def _stat(value: FileStat | None) -> object:
    if value is None:
        return None
    identity = value.file_identity
    return {
        "kind": value.kind.value,
        "size": value.size,
        "mtime_ns": value.mtime_ns,
        "identity": None
        if identity is None
        else {
            "volume_serial": identity.volume_serial,
            "file_index": identity.file_index,
        },
        "nlink": value.nlink,
        "metadata": _metadata(value.metadata),
    }


def _decode_stat(value: object, context: str) -> FileStat | None:
    if value is None:
        return None
    item = _mapping(value)
    _expect_keys(
        item,
        {"kind", "size", "mtime_ns", "identity", "nlink", "metadata"},
        context,
    )
    raw_identity = item["identity"]
    identity = None
    if raw_identity is not None:
        identity_item = _mapping(raw_identity)
        identity_context = f"{context}.identity"
        _expect_keys(
            identity_item,
            {"volume_serial", "file_index"},
            identity_context,
        )
        identity = FileIdentity(
            _string(
                identity_item["volume_serial"],
                f"{identity_context}.volume_serial",
            ),
            _integer(
                identity_item["file_index"],
                f"{identity_context}.file_index",
            ),
        )
    metadata = _decode_metadata(item["metadata"], f"{context}.metadata")
    if metadata is None:
        raise ValueError(f"{context}.metadata cannot be null")
    return FileStat(
        EntryKind(_string(item["kind"], f"{context}.kind")),
        _integer(item["size"], f"{context}.size"),
        _integer(item["mtime_ns"], f"{context}.mtime_ns"),
        identity,
        _integer(item["nlink"], f"{context}.nlink"),
        metadata,
    )


def _required_stat(value: object, context: str) -> FileStat:
    stat = _decode_stat(value, context)
    if stat is None:
        raise ValueError(f"{context} cannot be null")
    return stat


def _operation(value: PlanOperation) -> dict[str, object]:
    return {
        "op_id": str(value.op_id),
        "kind": value.kind.value,
        "source_rel_path": value.source_rel_path,
        "target_rel_path": value.target_rel_path,
        "source_expected": _stat(value.source_expected),
        "target_expected": _stat(value.target_expected),
        "intended": _stat(value.intended),
        "prior_target_rel_path": value.prior_target_rel_path,
        "prior_target_expected": _stat(value.prior_target_expected),
        "metadata": _metadata(value.metadata),
        "content_bytes": value.content_bytes,
        "dependencies": [str(item) for item in value.dependencies],
        "reason": value.reason.value,
        "blocked_reason": (
            None
            if value.blocked_reason is None
            else value.blocked_reason.value
        ),
    }


def _decode_operation(value: object, context: str) -> PlanOperation:
    item = _mapping(value)
    _expect_keys(
        item,
        {
            "op_id",
            "kind",
            "source_rel_path",
            "target_rel_path",
            "source_expected",
            "target_expected",
            "intended",
            "prior_target_rel_path",
            "prior_target_expected",
            "metadata",
            "content_bytes",
            "dependencies",
            "reason",
            "blocked_reason",
        },
        context,
    )
    raw_blocked = item["blocked_reason"]
    return PlanOperation(
        op_id=OpId(_string(item["op_id"], f"{context}.op_id")),
        kind=OperationKind(_string(item["kind"], f"{context}.kind")),
        source_rel_path=_optional_string(
            item["source_rel_path"], f"{context}.source_rel_path"
        ),
        target_rel_path=_string(
            item["target_rel_path"], f"{context}.target_rel_path"
        ),
        source_expected=_decode_stat(
            item["source_expected"], f"{context}.source_expected"
        ),
        target_expected=_decode_stat(
            item["target_expected"], f"{context}.target_expected"
        ),
        intended=_decode_stat(item["intended"], f"{context}.intended"),
        prior_target_rel_path=_optional_string(
            item["prior_target_rel_path"],
            f"{context}.prior_target_rel_path",
        ),
        prior_target_expected=_decode_stat(
            item["prior_target_expected"],
            f"{context}.prior_target_expected",
        ),
        metadata=_decode_metadata(item["metadata"], f"{context}.metadata"),
        content_bytes=_integer(
            item["content_bytes"], f"{context}.content_bytes"
        ),
        dependencies=tuple(
            OpId(_string(raw, f"{context}.dependencies[]"))
            for raw in _list(item["dependencies"])
        ),
        reason=OperationReason(
            _string(item["reason"], f"{context}.reason")
        ),
        blocked_reason=(
            None
            if raw_blocked is None
            else BlockedReason(
                _string(raw_blocked, f"{context}.blocked_reason")
            )
        ),
    )


def _plan(value: Plan) -> dict[str, object]:
    return {
        "source_root": {
            "path": value.source_root.path,
            "root_id": value.source_root.root_id,
        },
        "target_root": {
            "path": value.target_root.path,
            "root_id": value.target_root.root_id,
        },
        "source_volume_id": _volume(value.source_volume_id),
        "target_volume_id": _volume(value.target_volume_id),
        "source_volume_evidence": _volume_evidence(
            value.source_volume_evidence
        ),
        "target_volume_evidence": _volume_evidence(
            value.target_volume_evidence
        ),
        "source_profile": _profile(value.source_profile),
        "target_profile": _profile(value.target_profile),
        "source_complete": value.source_complete,
        "target_complete": value.target_complete,
        "operations": [_operation(item) for item in value.operations],
        "assignment": {
            "policy_name": value.assignment.policy_name,
            "policy_version": value.assignment.policy_version,
            "items": [
                {
                    "source_rel_path": item.source_rel_path,
                    "source_rel_path_key": item.source_rel_path_key,
                    "target_rel_path": item.target_rel_path,
                    "target_rel_path_key": item.target_rel_path_key,
                    "group_id": item.group_id,
                    "conflict": item.conflict,
                }
                for item in value.assignment.items
            ],
        },
        "preservation": {
            "preserve_ads": value.preservation.preserve_ads,
            "preserve_created": value.preservation.preserve_created,
            "preserve_acl": value.preservation.preserve_acl,
        },
        "filters": list(value.filter_snapshot.patterns),
        "deletion_policy": value.deletion_policy.value,
        "trash_on_update": value.trash_on_update,
        "policy_fingerprint": value.policy_fingerprint,
        "required_volumes": [
            _volume(item) for item in sorted(value.required_volumes)
        ],
        "required_bytes": value.required_bytes,
        "fingerprint": str(value.fingerprint),
    }


def _decode_plan(value: object) -> Plan:
    item = _mapping(value)
    _expect_keys(
        item,
        {
            "source_root",
            "target_root",
            "source_volume_id",
            "target_volume_id",
            "source_volume_evidence",
            "target_volume_evidence",
            "source_profile",
            "target_profile",
            "source_complete",
            "target_complete",
            "operations",
            "assignment",
            "preservation",
            "filters",
            "deletion_policy",
            "trash_on_update",
            "policy_fingerprint",
            "required_volumes",
            "required_bytes",
            "fingerprint",
        },
        "execution_set.plan",
    )
    source_root = _mapping(item["source_root"])
    target_root = _mapping(item["target_root"])
    _expect_keys(source_root, {"path", "root_id"}, "plan.source_root")
    _expect_keys(target_root, {"path", "root_id"}, "plan.target_root")

    assignment_item = _mapping(item["assignment"])
    _expect_keys(
        assignment_item,
        {"policy_name", "policy_version", "items"},
        "plan.assignment",
    )
    assignment_values: list[DestinationAssignment] = []
    for index, raw in enumerate(_list(assignment_item["items"])):
        assignment_context = f"plan.assignment.items[{index}]"
        assignment_value = _mapping(raw)
        _expect_keys(
            assignment_value,
            {
                "source_rel_path",
                "source_rel_path_key",
                "target_rel_path",
                "target_rel_path_key",
                "group_id",
                "conflict",
            },
            assignment_context,
        )
        assignment_values.append(
            DestinationAssignment(
                source_rel_path=_string(
                    assignment_value["source_rel_path"],
                    f"{assignment_context}.source_rel_path",
                ),
                source_rel_path_key=_string(
                    assignment_value["source_rel_path_key"],
                    f"{assignment_context}.source_rel_path_key",
                ),
                target_rel_path=_string(
                    assignment_value["target_rel_path"],
                    f"{assignment_context}.target_rel_path",
                ),
                target_rel_path_key=_string(
                    assignment_value["target_rel_path_key"],
                    f"{assignment_context}.target_rel_path_key",
                ),
                group_id=_optional_string(
                    assignment_value["group_id"],
                    f"{assignment_context}.group_id",
                ),
                conflict=_optional_string(
                    assignment_value["conflict"],
                    f"{assignment_context}.conflict",
                ),
            )
        )

    preservation_item = _mapping(item["preservation"])
    _expect_keys(
        preservation_item,
        {"preserve_ads", "preserve_created", "preserve_acl"},
        "plan.preservation",
    )

    required_volumes: set[VolumeId] = set()
    for index, raw in enumerate(_list(item["required_volumes"])):
        volume = _decode_volume(raw, f"plan.required_volumes[{index}]")
        if volume is None:
            raise ValueError("required plan volumes cannot be null")
        required_volumes.add(volume)

    return Plan(
        source_root=Root(
            _string(source_root["path"], "plan.source_root.path"),
            _string(source_root["root_id"], "plan.source_root.root_id"),
        ),
        target_root=Root(
            _string(target_root["path"], "plan.target_root.path"),
            _string(target_root["root_id"], "plan.target_root.root_id"),
        ),
        source_volume_id=_decode_volume(
            item["source_volume_id"], "plan.source_volume_id"
        ),
        target_volume_id=_decode_volume(
            item["target_volume_id"], "plan.target_volume_id"
        ),
        source_volume_evidence=_decode_volume_evidence(
            item["source_volume_evidence"],
            "plan.source_volume_evidence",
        ),
        target_volume_evidence=_decode_volume_evidence(
            item["target_volume_evidence"],
            "plan.target_volume_evidence",
        ),
        source_profile=_decode_profile(
            item["source_profile"], "plan.source_profile"
        ),
        target_profile=_decode_profile(
            item["target_profile"], "plan.target_profile"
        ),
        source_complete=_boolean(
            item["source_complete"], "plan.source_complete"
        ),
        target_complete=_boolean(
            item["target_complete"], "plan.target_complete"
        ),
        operations=tuple(
            _decode_operation(raw, f"plan.operations[{index}]")
            for index, raw in enumerate(_list(item["operations"]))
        ),
        assignment=Assignment(
            policy_name=_string(
                assignment_item["policy_name"],
                "plan.assignment.policy_name",
            ),
            policy_version=_string(
                assignment_item["policy_version"],
                "plan.assignment.policy_version",
            ),
            items=tuple(assignment_values),
        ),
        preservation=PreservationPolicy(
            preserve_ads=_boolean(
                preservation_item["preserve_ads"],
                "plan.preservation.preserve_ads",
            ),
            preserve_created=_boolean(
                preservation_item["preserve_created"],
                "plan.preservation.preserve_created",
            ),
            preserve_acl=_boolean(
                preservation_item["preserve_acl"],
                "plan.preservation.preserve_acl",
            ),
        ),
        filter_snapshot=FilterSet(
            tuple(
                _string(raw, "plan.filters[]")
                for raw in _list(item["filters"])
            )
        ),
        deletion_policy=DeletionPolicy(
            _string(item["deletion_policy"], "plan.deletion_policy")
        ),
        trash_on_update=_boolean(
            item["trash_on_update"], "plan.trash_on_update"
        ),
        policy_fingerprint=_string(
            item["policy_fingerprint"], "plan.policy_fingerprint"
        ),
        required_volumes=frozenset(required_volumes),
        required_bytes=_integer(
            item["required_bytes"], "plan.required_bytes"
        ),
        fingerprint=PlanFingerprint(
            _string(item["fingerprint"], "plan.fingerprint")
        ),
    )


def _content_evidence(value: ContentEvidence) -> dict[str, object]:
    return {
        "algorithm": value.algorithm,
        "digest": value.digest.hex(),
        "size": value.size,
        "provenance": value.provenance.value,
        "observed_at": value.observed_at.isoformat(),
    }


def _decode_content_evidence(
    value: object, context: str
) -> ContentEvidence:
    item = _mapping(value)
    _expect_keys(
        item,
        {"algorithm", "digest", "size", "provenance", "observed_at"},
        context,
    )
    try:
        digest = bytes.fromhex(
            _string(item["digest"], f"{context}.digest")
        )
    except ValueError as error:
        raise ValueError(f"{context}.digest is not hexadecimal") from error
    return ContentEvidence(
        algorithm=_string(item["algorithm"], f"{context}.algorithm"),
        digest=digest,
        size=_integer(item["size"], f"{context}.size"),
        provenance=Provenance(
            _string(item["provenance"], f"{context}.provenance")
        ),
        observed_at=_utc_datetime(
            item["observed_at"], f"{context}.observed_at"
        ),
    )


def _attestation(value: Attestation) -> dict[str, object]:
    return {
        "content": _content_evidence(value.content),
        "subject": _stat(value.subject),
    }


def _decode_attestation(value: object, context: str) -> Attestation:
    item = _mapping(value)
    _expect_keys(item, {"content", "subject"}, context)
    return Attestation(
        content=_decode_content_evidence(
            item["content"], f"{context}.content"
        ),
        subject=_required_stat(item["subject"], f"{context}.subject"),
    )


def _recorded_copy_identity(
    value: RecordedCopyIdentity | None,
) -> object:
    if value is None:
        return None
    return {
        "row_id": value.row_id,
        "location_id": value.location_id,
        "scope_token": value.scope_token,
        "rel_path_key": value.rel_path_key,
    }


def _decode_recorded_copy_identity(
    value: object, context: str
) -> RecordedCopyIdentity | None:
    if value is None:
        return None
    item = _mapping(value)
    _expect_keys(
        item,
        {"row_id", "location_id", "scope_token", "rel_path_key"},
        context,
    )
    return RecordedCopyIdentity(
        row_id=_string(item["row_id"], f"{context}.row_id"),
        location_id=_string(
            item["location_id"], f"{context}.location_id"
        ),
        scope_token=_string(
            item["scope_token"], f"{context}.scope_token"
        ),
        rel_path_key=_string(
            item["rel_path_key"], f"{context}.rel_path_key"
        ),
    )


def _published_evidence(value: PublishedCopyEvidence) -> dict[str, object]:
    return {
        "attestation": _attestation(value.attestation),
        "recorded_identity": _recorded_copy_identity(
            value.recorded_identity
        ),
    }


def _decode_published_evidence(
    value: object, context: str
) -> PublishedCopyEvidence:
    item = _mapping(value)
    _expect_keys(item, {"attestation", "recorded_identity"}, context)
    return PublishedCopyEvidence(
        attestation=_decode_attestation(
            item["attestation"], f"{context}.attestation"
        ),
        recorded_identity=_decode_recorded_copy_identity(
            item["recorded_identity"], f"{context}.recorded_identity"
        ),
    )


def _post_copy_identity(
    value: PostCopyRecordIdentity | None,
) -> object:
    if value is None:
        return None
    return {
        "row_id": value.row_id,
        "location_id": value.location_id,
        "scope_token": value.scope_token,
        "rel_path_key": value.rel_path_key,
    }


def _decode_post_copy_identity(
    value: object, context: str
) -> PostCopyRecordIdentity | None:
    if value is None:
        return None
    item = _mapping(value)
    _expect_keys(
        item,
        {"row_id", "location_id", "scope_token", "rel_path_key"},
        context,
    )
    return PostCopyRecordIdentity(
        row_id=_string(item["row_id"], f"{context}.row_id"),
        location_id=_string(
            item["location_id"], f"{context}.location_id"
        ),
        scope_token=_string(
            item["scope_token"], f"{context}.scope_token"
        ),
        rel_path_key=_string(
            item["rel_path_key"], f"{context}.rel_path_key"
        ),
    )


def _post_copy_candidate(value: PostCopyCandidate) -> dict[str, object]:
    return {
        "item_id": value.item_id,
        "root": str(value.root),
        "display_path": value.display_path,
        "expected_stat": _stat(value.expected_stat),
        "copy_attestation": _attestation(value.copy_attestation),
        "recorded_identity": _post_copy_identity(value.recorded_identity),
    }


def _decode_post_copy_candidate(
    value: object, context: str
) -> PostCopyCandidate:
    item = _mapping(value)
    _expect_keys(
        item,
        {
            "item_id",
            "root",
            "display_path",
            "expected_stat",
            "copy_attestation",
            "recorded_identity",
        },
        context,
    )
    return PostCopyCandidate(
        item_id=_string(item["item_id"], f"{context}.item_id"),
        root=Path(_string(item["root"], f"{context}.root")),
        display_path=_string(
            item["display_path"], f"{context}.display_path"
        ),
        expected_stat=_required_stat(
            item["expected_stat"], f"{context}.expected_stat"
        ),
        copy_attestation=_decode_attestation(
            item["copy_attestation"], f"{context}.copy_attestation"
        ),
        recorded_identity=_decode_post_copy_identity(
            item["recorded_identity"], f"{context}.recorded_identity"
        ),
    )


def _post_copy_selection(value: PostCopySelection) -> dict[str, object]:
    completed = value.completed_bytes
    return {
        "candidates": [
            _post_copy_candidate(candidate)
            for candidate in value.candidates
        ],
        "completed_bytes": [
            {"item_id": candidate.item_id, "bytes_read": completed[candidate.item_id]}
            for candidate in value.candidates
            if candidate.item_id in completed
        ],
        "processed_bytes": value.processed_bytes,
    }


def _decode_post_copy_selection(
    value: object, context: str
) -> PostCopySelection:
    item = _mapping(value)
    _expect_keys(
        item,
        {"candidates", "completed_bytes", "processed_bytes"},
        context,
    )
    candidates = tuple(
        _decode_post_copy_candidate(
            raw, f"{context}.candidates[{index}]"
        )
        for index, raw in enumerate(_list(item["candidates"]))
    )
    completed: dict[str, int] = {}
    for index, raw in enumerate(_list(item["completed_bytes"])):
        completion_context = f"{context}.completed_bytes[{index}]"
        completion = _mapping(raw)
        _expect_keys(
            completion,
            {"item_id", "bytes_read"},
            completion_context,
        )
        item_id = _string(
            completion["item_id"], f"{completion_context}.item_id"
        )
        if item_id in completed:
            raise ValueError("post-copy completion ids must be unique")
        completed[item_id] = _integer(
            completion["bytes_read"],
            f"{completion_context}.bytes_read",
        )
    return PostCopySelection(
        candidates=candidates,
        _completed_bytes=completed,
        _processed_bytes=_integer(
            item["processed_bytes"], f"{context}.processed_bytes"
        ),
    )


def _commitment(value: Commitment | None) -> object:
    if value is None:
        return None
    return {
        "plan_fingerprint": str(value.plan_fingerprint),
        "selection_digest": value.selection_digest.hex(),
        "committed_at": value.committed_at.isoformat(),
    }


def _decode_commitment(value: object, context: str) -> Commitment | None:
    if value is None:
        return None
    item = _mapping(value)
    _expect_keys(
        item,
        {"plan_fingerprint", "selection_digest", "committed_at"},
        context,
    )
    try:
        digest = bytes.fromhex(
            _string(
                item["selection_digest"],
                f"{context}.selection_digest",
            )
        )
    except ValueError as error:
        raise ValueError(
            f"{context}.selection_digest is not hexadecimal"
        ) from error
    return Commitment(
        plan_fingerprint=PlanFingerprint(
            _string(
                item["plan_fingerprint"],
                f"{context}.plan_fingerprint",
            )
        ),
        selection_digest=digest,
        committed_at=_utc_datetime(
            item["committed_at"], f"{context}.committed_at"
        ),
    )


def _execution_set(value: ExecutionSet) -> dict[str, object]:
    return {
        "plan": _plan(value.plan),
        "selection": sorted(str(item) for item in value.selection),
        "run_id": str(value.run_id),
        "status": {
            str(key): outcome.value
            for key, outcome in sorted(
                value.status.items(), key=lambda pair: str(pair[0])
            )
        },
        "commitment": _commitment(value.commitment),
        "published_evidence": {
            str(key): _published_evidence(evidence)
            for key, evidence in sorted(
                value.published_evidence.items(),
                key=lambda pair: str(pair[0]),
            )
        },
        "recording": value.recording.value,
    }


def _decode_execution_set(value: object) -> ExecutionSet:
    item = _mapping(value)
    _expect_keys(
        item,
        {
            "plan",
            "selection",
            "run_id",
            "status",
            "commitment",
            "published_evidence",
            "recording",
        },
        "execution_set",
    )
    raw_status = _mapping(item["status"])
    raw_evidence = _mapping(item["published_evidence"])
    return ExecutionSet(
        plan=_decode_plan(item["plan"]),
        selection=frozenset(
            OpId(_string(raw, "execution_set.selection[]"))
            for raw in _list(item["selection"])
        ),
        run_id=validated_run_id(
            _string(item["run_id"], "execution_set.run_id")
        ),
        status={
            OpId(key): Outcome(
                _string(value, f"execution_set.status.{key}")
            )
            for key, value in raw_status.items()
        },
        commitment=_decode_commitment(
            item["commitment"], "execution_set.commitment"
        ),
        published_evidence={
            OpId(key): _decode_published_evidence(
                evidence, f"execution_set.published_evidence.{key}"
            )
            for key, evidence in raw_evidence.items()
        },
        recording=RecordingStatus(
            _string(item["recording"], "execution_set.recording")
        ),
    )


def _phase_result(value: PhaseResult) -> dict[str, object]:
    return {
        "phase": value.phase,
        "status": value.status.value,
        "items_done": value.items_done,
        "items_total": value.items_total,
        "bytes_done": value.bytes_done,
        "bytes_total": value.bytes_total,
        "error": value.error,
    }


def _decode_phase_result(value: object, context: str) -> PhaseResult:
    item = _mapping(value)
    _expect_keys(
        item,
        {
            "phase",
            "status",
            "items_done",
            "items_total",
            "bytes_done",
            "bytes_total",
            "error",
        },
        context,
    )
    return PhaseResult(
        phase=_string(item["phase"], f"{context}.phase"),
        status=PhaseStatus(
            _string(item["status"], f"{context}.status")
        ),
        items_done=_integer(
            item["items_done"], f"{context}.items_done"
        ),
        items_total=_optional_integer(
            item["items_total"], f"{context}.items_total"
        ),
        bytes_done=_integer(
            item["bytes_done"], f"{context}.bytes_done"
        ),
        bytes_total=_optional_integer(
            item["bytes_total"], f"{context}.bytes_total"
        ),
        error=_optional_string(item["error"], f"{context}.error"),
    )


def encode_plan_request(request: PlanRequest) -> bytes:
    policy = request.options.destination_policy
    if not isinstance(policy, IdentityDestinationPolicy):
        raise ValueError(
            "workflow payloads support only the identity destination policy"
        )
    value = {
        "schema_version": _SCHEMA_VERSION,
        "kind": "plan",
        "request_id": request.request_id,
        "source_path": request.source_path,
        "target_path": request.target_path,
        "options": {
            "deletion_policy": request.options.deletion_policy.value,
            "preservation": {
                "preserve_ads": request.options.preservation.preserve_ads,
                "preserve_created": request.options.preservation.preserve_created,
                "preserve_acl": request.options.preservation.preserve_acl,
            },
            "filters": list(request.options.filters.patterns),
            "trash_on_update": request.options.trash_on_update,
            "propagate_source_casing": (
                request.options.propagate_source_casing
            ),
            "internal_mirror_authorized": (
                request.options.internal_mirror_authorized
            ),
        },
    }
    return _json_bytes(value)


def decode_plan_request(payload: bytes) -> PlanRequest:
    item = _payload(payload, "plan")
    _expect_keys(
        item,
        {
            "schema_version",
            "kind",
            "request_id",
            "source_path",
            "target_path",
            "options",
        },
        "plan payload",
    )
    options = _mapping(item["options"])
    _expect_keys(
        options,
        {
            "deletion_policy",
            "preservation",
            "filters",
            "trash_on_update",
            "propagate_source_casing",
            "internal_mirror_authorized",
        },
        "plan options",
    )
    preservation = _mapping(options["preservation"])
    _expect_keys(
        preservation,
        {"preserve_ads", "preserve_created", "preserve_acl"},
        "plan options.preservation",
    )
    return PlanRequest(
        request_id=_string(item["request_id"], "plan request_id"),
        source_path=_string(item["source_path"], "plan source_path"),
        target_path=_string(item["target_path"], "plan target_path"),
        options=SyncOptions(
            deletion_policy=DeletionPolicy(
                _string(
                    options["deletion_policy"],
                    "plan options.deletion_policy",
                )
            ),
            preservation=PreservationPolicy(
                preserve_ads=_boolean(
                    preservation["preserve_ads"],
                    "plan options.preservation.preserve_ads",
                ),
                preserve_created=_boolean(
                    preservation["preserve_created"],
                    "plan options.preservation.preserve_created",
                ),
                preserve_acl=_boolean(
                    preservation["preserve_acl"],
                    "plan options.preservation.preserve_acl",
                ),
            ),
            filters=FilterSet(
                tuple(
                    _string(raw, "plan options.filters[]")
                    for raw in _list(options["filters"])
                )
            ),
            destination_policy=IdentityDestinationPolicy(),
            trash_on_update=_boolean(
                options["trash_on_update"],
                "plan options.trash_on_update",
            ),
            propagate_source_casing=_boolean(
                options["propagate_source_casing"],
                "plan options.propagate_source_casing",
            ),
            internal_mirror_authorized=_boolean(
                options["internal_mirror_authorized"],
                "plan options.internal_mirror_authorized",
            ),
        ),
    )


def encode_execution_request(request: ExecutionRequest) -> bytes:
    continuation = request.continuation
    value: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "kind": "execute",
        "phase": continuation.phase,
        "execution_set": _execution_set(continuation.execution_set),
        "started_at": (
            None
            if request.started_at is None
            else request.started_at.isoformat()
        ),
    }
    if isinstance(continuation, ExecuteContinuation):
        value["verify_after_execute"] = continuation.verify_after_execute
    else:
        value.update(
            {
                "candidates": _post_copy_selection(
                    continuation.candidates
                ),
                "filesystem_status": continuation.filesystem_status.value,
                "recording": continuation.recording.value,
                "execute_phase": _phase_result(
                    continuation.execute_phase
                ),
                "missing_evidence_ids": list(
                    continuation.missing_evidence_ids
                ),
            }
        )
    return _json_bytes(value)


def decode_execution_request(payload: bytes) -> ExecutionRequest:
    item = _payload(payload, "execute")
    if "phase" not in item:
        raise ValueError("execution payload requires a phase discriminator")
    phase = _string(item["phase"], "execution payload.phase")
    common = {
        "schema_version",
        "kind",
        "phase",
        "execution_set",
        "started_at",
    }
    execution_set = _decode_execution_set(item.get("execution_set"))
    started_at = _optional_utc_datetime(
        item.get("started_at"), "execution payload.started_at"
    )

    if phase == ExecuteContinuation.phase:
        _expect_keys(
            item,
            common | {"verify_after_execute"},
            "execute continuation",
        )
        continuation = ExecuteContinuation(
            execution_set=execution_set,
            verify_after_execute=_boolean(
                item["verify_after_execute"],
                "execute continuation.verify_after_execute",
            ),
        )
    elif phase == VerifyContinuation.phase:
        _expect_keys(
            item,
            common
            | {
                "candidates",
                "filesystem_status",
                "recording",
                "execute_phase",
                "missing_evidence_ids",
            },
            "verify continuation",
        )
        continuation = VerifyContinuation(
            execution_set=execution_set,
            candidates=_decode_post_copy_selection(
                item["candidates"], "verify continuation.candidates"
            ),
            filesystem_status=SessionState(
                _string(
                    item["filesystem_status"],
                    "verify continuation.filesystem_status",
                )
            ),
            recording=RecordingStatus(
                _string(
                    item["recording"],
                    "verify continuation.recording",
                )
            ),
            execute_phase=_decode_phase_result(
                item["execute_phase"],
                "verify continuation.execute_phase",
            ),
            missing_evidence_ids=tuple(
                _string(
                    raw,
                    "verify continuation.missing_evidence_ids[]",
                )
                for raw in _list(item["missing_evidence_ids"])
            ),
        )
    else:
        raise ValueError(f"unsupported execution continuation phase: {phase}")
    return ExecutionRequest(continuation, started_at)


def _payload(payload: bytes, expected_kind: str) -> Mapping[str, object]:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("workflow payload is not valid UTF-8 JSON") from error
    item = _mapping(value)
    schema_version = item.get("schema_version")
    if type(schema_version) is not int or schema_version != _SCHEMA_VERSION:
        raise ValueError("unsupported workflow payload schema")
    if item.get("kind") != expected_kind:
        raise ValueError("workflow payload kind does not match registration")
    return item


def _unique_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"workflow payload contains duplicate key: {key}")
        value[key] = item
    return value


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError("workflow payload object is malformed")
    return value


def _expect_keys(
    value: Mapping[str, object],
    expected: set[str],
    context: str,
) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing {missing!r}")
        if unexpected:
            details.append(f"unexpected {unexpected!r}")
        raise ValueError(f"{context} fields are invalid: {', '.join(details)}")


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("workflow payload list is malformed")
    return value


def _string(value: object, context: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be a string")
    return value


def _optional_string(value: object, context: str) -> str | None:
    return None if value is None else _string(value, context)


def _integer(value: object, context: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{context} must be an integer")
    return value


def _optional_integer(value: object, context: str) -> int | None:
    return None if value is None else _integer(value, context)


def _boolean(value: object, context: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{context} must be a boolean")
    return value


def _utc_datetime(value: object, context: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(_string(value, context))
    except ValueError as error:
        raise ValueError(f"{context} must be an ISO-8601 datetime") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{context} must be timezone-aware")
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{context} must be UTC")
    return parsed


def _optional_utc_datetime(
    value: object, context: str
) -> datetime | None:
    return None if value is None else _utc_datetime(value, context)
