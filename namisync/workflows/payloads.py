"""Versioned JSON payloads passed opaquely through the dispatcher."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Mapping

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

from .models import ExecutionRequest, PlanRequest


_SCHEMA_VERSION = 2


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


def _decode_volume(value: object) -> VolumeId | None:
    if value is None:
        return None
    item = _mapping(value)
    return VolumeId(str(item["serial"]), str(item["fs_type"]))


def _evidence(value: VolumeEvidence | None) -> object:
    if value is None:
        return None
    return {
        "label": value.label,
        "device_id": value.device_id,
        "clone_ambiguous": value.clone_ambiguous,
    }


def _decode_evidence(value: object) -> VolumeEvidence | None:
    if value is None:
        return None
    item = _mapping(value)
    return VolumeEvidence(
        label=_optional_str(item.get("label")),
        device_id=_optional_str(item.get("device_id")),
        clone_ambiguous=bool(item["clone_ambiguous"]),
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


def _decode_profile(value: object) -> CapabilityProfile:
    item = _mapping(value)
    seek = item.get("incurs_seek_penalty")
    return CapabilityProfile(
        fs_type=str(item["fs_type"]),
        mtime_granularity_ns=int(item["mtime_granularity_ns"]),
        stable_file_identity=bool(item["stable_file_identity"]),
        incurs_seek_penalty=None if seek is None else bool(seek),
        max_path=int(item["max_path"]),
        supports_ads=bool(item["supports_ads"]),
        supports_hardlinks=bool(item["supports_hardlinks"]),
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
        else {"volume_serial": identity.volume_serial, "file_index": identity.file_index},
        "nlink": value.nlink,
        "metadata": {
            "attributes": value.metadata.attributes,
            "created_ns": value.metadata.created_ns,
        },
    }


def _decode_stat(value: object) -> FileStat | None:
    if value is None:
        return None
    item = _mapping(value)
    raw_identity = item.get("identity")
    identity = None
    if raw_identity is not None:
        identity_item = _mapping(raw_identity)
        identity = FileIdentity(
            str(identity_item["volume_serial"]), int(identity_item["file_index"])
        )
    metadata = _mapping(item["metadata"])
    return FileStat(
        EntryKind(str(item["kind"])),
        int(item["size"]),
        int(item["mtime_ns"]),
        identity,
        int(item["nlink"]),
        MetadataSnapshot(
            int(metadata["attributes"]),
            None if metadata.get("created_ns") is None else int(metadata["created_ns"]),
        ),
    )


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
        "metadata": None
        if value.metadata is None
        else {
            "attributes": value.metadata.attributes,
            "created_ns": value.metadata.created_ns,
        },
        "content_bytes": value.content_bytes,
        "dependencies": [str(item) for item in value.dependencies],
        "reason": value.reason.value,
        "blocked_reason": None if value.blocked_reason is None else value.blocked_reason.value,
    }


def _decode_operation(value: object) -> PlanOperation:
    item = _mapping(value)
    raw_metadata = item.get("metadata")
    metadata = None
    if raw_metadata is not None:
        metadata_item = _mapping(raw_metadata)
        metadata = MetadataSnapshot(
            int(metadata_item["attributes"]),
            None
            if metadata_item.get("created_ns") is None
            else int(metadata_item["created_ns"]),
        )
    raw_blocked = item.get("blocked_reason")
    return PlanOperation(
        op_id=OpId(str(item["op_id"])),
        kind=OperationKind(str(item["kind"])),
        source_rel_path=_optional_str(item.get("source_rel_path")),
        target_rel_path=str(item["target_rel_path"]),
        source_expected=_decode_stat(item.get("source_expected")),
        target_expected=_decode_stat(item.get("target_expected")),
        intended=_decode_stat(item.get("intended")),
        prior_target_rel_path=_optional_str(item.get("prior_target_rel_path")),
        prior_target_expected=_decode_stat(item.get("prior_target_expected")),
        metadata=metadata,
        content_bytes=int(item["content_bytes"]),
        dependencies=tuple(OpId(str(value)) for value in _list(item["dependencies"])),
        reason=OperationReason(str(item["reason"])),
        blocked_reason=None if raw_blocked is None else BlockedReason(str(raw_blocked)),
    )


def _plan(value: Plan) -> dict[str, object]:
    return {
        "source_root": {"path": value.source_root.path, "root_id": value.source_root.root_id},
        "target_root": {"path": value.target_root.path, "root_id": value.target_root.root_id},
        "source_volume_id": _volume(value.source_volume_id),
        "target_volume_id": _volume(value.target_volume_id),
        "source_volume_evidence": _evidence(value.source_volume_evidence),
        "target_volume_evidence": _evidence(value.target_volume_evidence),
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
        "required_volumes": [_volume(item) for item in sorted(value.required_volumes)],
        "required_bytes": value.required_bytes,
        "fingerprint": str(value.fingerprint),
    }


def _decode_plan(value: object) -> Plan:
    item = _mapping(value)
    source_root = _mapping(item["source_root"])
    target_root = _mapping(item["target_root"])
    assignment_item = _mapping(item["assignment"])
    preservation_item = _mapping(item["preservation"])
    required_volumes = frozenset(
        volume
        for raw in _list(item["required_volumes"])
        if (volume := _decode_volume(raw)) is not None
    )
    return Plan(
        source_root=Root(str(source_root["path"]), str(source_root["root_id"])),
        target_root=Root(str(target_root["path"]), str(target_root["root_id"])),
        source_volume_id=_decode_volume(item.get("source_volume_id")),
        target_volume_id=_decode_volume(item.get("target_volume_id")),
        source_volume_evidence=_decode_evidence(item.get("source_volume_evidence")),
        target_volume_evidence=_decode_evidence(item.get("target_volume_evidence")),
        source_profile=_decode_profile(item["source_profile"]),
        target_profile=_decode_profile(item["target_profile"]),
        source_complete=bool(item["source_complete"]),
        target_complete=bool(item["target_complete"]),
        operations=tuple(_decode_operation(raw) for raw in _list(item["operations"])),
        assignment=Assignment(
            policy_name=str(assignment_item["policy_name"]),
            policy_version=str(assignment_item["policy_version"]),
            items=tuple(
                DestinationAssignment(
                    source_rel_path=str(raw_item["source_rel_path"]),
                    source_rel_path_key=str(raw_item["source_rel_path_key"]),
                    target_rel_path=str(raw_item["target_rel_path"]),
                    target_rel_path_key=str(raw_item["target_rel_path_key"]),
                    group_id=_optional_str(raw_item.get("group_id")),
                    conflict=_optional_str(raw_item.get("conflict")),
                )
                for raw in _list(assignment_item["items"])
                for raw_item in (_mapping(raw),)
            ),
        ),
        preservation=PreservationPolicy(
            preserve_ads=bool(preservation_item["preserve_ads"]),
            preserve_created=bool(preservation_item["preserve_created"]),
            preserve_acl=bool(preservation_item["preserve_acl"]),
        ),
        filter_snapshot=FilterSet(tuple(str(value) for value in _list(item["filters"]))),
        deletion_policy=DeletionPolicy(str(item["deletion_policy"])),
        trash_on_update=bool(item["trash_on_update"]),
        policy_fingerprint=str(item["policy_fingerprint"]),
        required_volumes=required_volumes,
        required_bytes=int(item["required_bytes"]),
        fingerprint=PlanFingerprint(str(item["fingerprint"])),
    )


def encode_plan_request(request: PlanRequest) -> bytes:
    policy = request.options.destination_policy
    if not isinstance(policy, IdentityDestinationPolicy):
        raise ValueError("M0 workflow payloads support only the identity destination policy")
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
            "propagate_source_casing": request.options.propagate_source_casing,
            "internal_mirror_authorized": request.options.internal_mirror_authorized,
        },
    }
    return _json_bytes(value)


def decode_plan_request(payload: bytes) -> PlanRequest:
    item = _payload(payload, "plan")
    options = _mapping(item["options"])
    preservation = _mapping(options["preservation"])
    return PlanRequest(
        request_id=str(item["request_id"]),
        source_path=str(item["source_path"]),
        target_path=str(item["target_path"]),
        options=SyncOptions(
            deletion_policy=DeletionPolicy(str(options["deletion_policy"])),
            preservation=PreservationPolicy(
                preserve_ads=bool(preservation["preserve_ads"]),
                preserve_created=bool(preservation["preserve_created"]),
                preserve_acl=bool(preservation["preserve_acl"]),
            ),
            filters=FilterSet(tuple(str(value) for value in _list(options["filters"]))),
            destination_policy=IdentityDestinationPolicy(),
            trash_on_update=bool(options["trash_on_update"]),
            propagate_source_casing=bool(options["propagate_source_casing"]),
            internal_mirror_authorized=bool(options["internal_mirror_authorized"]),
        ),
    )


def encode_execution_request(request: ExecutionRequest) -> bytes:
    xset = request.execution_set
    commitment = xset.commitment
    value = {
        "schema_version": _SCHEMA_VERSION,
        "kind": "execute",
        "plan": _plan(xset.plan),
        "selection": sorted(str(item) for item in xset.selection),
        "run_id": str(xset.run_id),
        "status": {str(key): outcome.value for key, outcome in sorted(xset.status.items())},
        "commitment": None
        if commitment is None
        else {
            "plan_fingerprint": str(commitment.plan_fingerprint),
            "selection_digest": commitment.selection_digest.hex(),
            "committed_at": commitment.committed_at.isoformat(),
        },
        "started_at": None if request.started_at is None else request.started_at.isoformat(),
    }
    return _json_bytes(value)


def decode_execution_request(payload: bytes) -> ExecutionRequest:
    item = _payload(payload, "execute")
    raw_commitment = item.get("commitment")
    commitment = None
    if raw_commitment is not None:
        commitment_item = _mapping(raw_commitment)
        commitment = Commitment(
            plan_fingerprint=PlanFingerprint(str(commitment_item["plan_fingerprint"])),
            selection_digest=bytes.fromhex(str(commitment_item["selection_digest"])),
            committed_at=datetime.fromisoformat(str(commitment_item["committed_at"])),
        )
    raw_status = _mapping(item["status"])
    raw_started = item.get("started_at")
    return ExecutionRequest(
        ExecutionSet(
            plan=_decode_plan(item["plan"]),
            selection=frozenset(OpId(str(value)) for value in _list(item["selection"])),
            run_id=validated_run_id(str(item["run_id"])),
            status={OpId(str(key)): Outcome(str(value)) for key, value in raw_status.items()},
            commitment=commitment,
        ),
        None if raw_started is None else datetime.fromisoformat(str(raw_started)),
    )


def _payload(payload: bytes, expected_kind: str) -> Mapping[str, object]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("workflow payload is not valid UTF-8 JSON") from error
    item = _mapping(value)
    if item.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("unsupported workflow payload schema")
    if item.get("kind") != expected_kind:
        raise ValueError("workflow payload kind does not match registration")
    return item


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("workflow payload object is malformed")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("workflow payload list is malformed")
    return value


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)
