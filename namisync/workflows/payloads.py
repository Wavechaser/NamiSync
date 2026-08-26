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
    ItemRecordingReason,
    PublishedCopyEvidence,
    RecordedCopyIdentity,
    TaskRecordingIssue,
    TaskRecordingIssueReason,
    validated_run_id,
)
from namisync.core.integrity import (
    PostCopyCandidate,
    PostCopyRecordIdentity,
    PostCopySelection,
)
from namisync.core.models import (
    MAX_ROOT_ID_UTF8_BYTES,
    MAX_VOLUME_TEXT_UTF16_UNITS,
    CapabilityProfile,
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
    Root,
    VolumeEvidence,
    VolumeId,
    capability_profile_projection,
    root_projection,
    volume_evidence_projection,
    volume_id_projection,
)
from namisync.core.planning import (
    ASSIGNMENT_ITEM_LIMIT,
    ASSIGNMENT_TEXT_UTF8_LIMIT,
    FILTER_PATTERN_LIMIT,
    FILTER_PATTERN_UTF8_LIMIT,
    FILTER_TOTAL_UTF8_LIMIT,
    Assignment,
    BlockedReason,
    DeletionPolicy,
    DestinationAssignment,
    FilterSet,
    IdentityDestinationPolicy,
    OpId,
    OperationKind,
    OperationReason,
    PLAN_REQUIRED_VOLUME_LIMIT,
    Plan,
    PlanFingerprint,
    PlanOperation,
    PreservationPolicy,
    SyncOptions,
    assignment_projection,
    filter_set_projection,
    preservation_policy_projection,
    validate_assignment,
    validate_filter_set,
)
from namisync.core.pathing import normalize_relative_path, validate_relative_path
from namisync.core.review import MAX_PLAN_REVIEW_ROWS
from namisync.core.session import PhaseResult, PhaseStatus, SessionState
from namisync.core.scalars import (
    MAX_DIAGNOSTIC_UTF8_BYTES,
    MAX_FILE_INDEX_128,
    MAX_PATH_UTF16_UNITS,
    MAX_REQUEST_ID_UTF8_BYTES,
    MAX_SIGNED_64,
    checked_add_signed_64,
    file_index_128_from_text,
    file_index_128_to_text,
    require_json_unicode,
    require_safe_int,
    require_signed_64,
    require_utf16_path,
    require_utf16_text,
    require_utf8_text,
)

from .models import (
    ExecuteContinuation,
    ExecutionRequest,
    PlanRequest,
    VerifyContinuation,
    _exact_verify_continuation,
)
from ._json_envelope import (
    JSON_LIST_SLOT_CHARGE,
    JSON_SCALAR_CHARGE,
    JsonEnvelopeCounter,
    JsonObjectLayout,
    canonical_byte_ceiling,
    encode_canonical_json,
    model_array_charge,
    model_mapping_charge,
    model_object_charge,
    model_text_charge,
    object_layout,
    require_payload_bytes,
)


_PLAN_SCHEMA_VERSION = 5
_EXECUTION_SCHEMA_VERSION = 6

_PATH_UTF8_LIMIT = MAX_PATH_UTF16_UNITS * 3
_VOLUME_TEXT_UTF8_LIMIT = MAX_VOLUME_TEXT_UTF16_UNITS * 3
_FIXED_ID_UTF8_LIMIT = 32
_DIGEST_HEX_UTF8_LIMIT = 64
_FILE_INDEX_TEXT_UTF8_LIMIT = len(str(MAX_FILE_INDEX_128))
_TIMESTAMP_UTF8_LIMIT = len(
    datetime.max.replace(tzinfo=timezone.utc).isoformat()
)
_SQLITE_ID_UTF8_LIMIT = len(str(MAX_SIGNED_64))
_TASK_ISSUE_LIMIT = len(TaskRecordingIssueReason)

_PLAN_REQUEST_LAYOUT = object_layout(
    "schema_version", "kind", "request_id", "source_path", "target_path", "options"
)
_PLAN_OPTIONS_LAYOUT = object_layout(
    "deletion_policy",
    "preservation",
    "filters",
    "trash_on_update",
    "propagate_source_casing",
    "internal_mirror_authorized",
)
_PRESERVATION_LAYOUT = object_layout(
    "preserve_ads", "preserve_created", "preserve_acl"
)
_ROOT_LAYOUT = object_layout("path", "root_id")
_VOLUME_LAYOUT = object_layout("serial", "fs_type")
_VOLUME_EVIDENCE_LAYOUT = object_layout("label", "device_id", "clone_ambiguous")
_PROFILE_LAYOUT = object_layout(
    "fs_type",
    "mtime_granularity_ns",
    "stable_file_identity",
    "incurs_seek_penalty",
    "max_path",
    "supports_ads",
    "supports_hardlinks",
)
_METADATA_LAYOUT = object_layout("attributes", "created_ns")
_IDENTITY_LAYOUT = object_layout("volume_serial", "file_index")
_STAT_LAYOUT = object_layout("kind", "size", "mtime_ns", "identity", "nlink", "metadata")
_OPERATION_LAYOUT = object_layout(
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
)
_ASSIGNMENT_LAYOUT = object_layout("policy_name", "policy_version", "items")
_ASSIGNMENT_ITEM_LAYOUT = object_layout(
    "source_rel_path",
    "source_rel_path_key",
    "target_rel_path",
    "target_rel_path_key",
    "group_id",
    "conflict",
)
_PLAN_LAYOUT = object_layout(
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
)
_CONTENT_EVIDENCE_LAYOUT = object_layout(
    "algorithm", "digest", "size", "provenance", "observed_at"
)
_ATTESTATION_LAYOUT = object_layout("content", "subject")
_RECORDED_IDENTITY_LAYOUT = object_layout(
    "row_id", "location_id", "scope_token", "rel_path_key"
)
_PUBLISHED_EVIDENCE_LAYOUT = object_layout("attestation", "recorded_identity")
_POST_COPY_CANDIDATE_LAYOUT = object_layout(
    "item_id", "root", "display_path", "expected_stat", "copy_attestation", "recorded_identity"
)
_POST_COPY_SELECTION_LAYOUT = object_layout(
    "candidates", "completed_bytes", "processed_bytes"
)
_COMPLETION_LAYOUT = object_layout("item_id", "bytes_read")
_COMMITMENT_LAYOUT = object_layout(
    "plan_fingerprint", "selection_digest", "committed_at"
)
_EXECUTION_SET_LAYOUT = object_layout(
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
)
_TASK_ISSUE_LAYOUT = object_layout("reason", "detail")
_PHASE_RESULT_LAYOUT = object_layout(
    "phase", "status", "items_done", "items_total", "bytes_done", "bytes_total", "error"
)
_EXECUTE_LAYOUT = object_layout(
    "schema_version", "kind", "phase", "execution_set", "started_at", "verify_after_execute"
)
_VERIFY_LAYOUT = object_layout(
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
)


def _optional_max(charge: int) -> int:
    return max(JSON_SCALAR_CHARGE, charge)


def _enum_utf8_limit(enum_type: type) -> int:
    return max(len(item.value.encode("utf-8")) for item in enum_type)


def _max_metadata_charge() -> int:
    return model_object_charge(_METADATA_LAYOUT) + 2 * JSON_SCALAR_CHARGE


def _max_identity_charge() -> int:
    return (
        model_object_charge(_IDENTITY_LAYOUT)
        + model_text_charge(_VOLUME_TEXT_UTF8_LIMIT)
        + model_text_charge(_FILE_INDEX_TEXT_UTF8_LIMIT)
    )


def _max_stat_charge() -> int:
    return (
        model_object_charge(_STAT_LAYOUT)
        + model_text_charge(_enum_utf8_limit(EntryKind))
        + 3 * JSON_SCALAR_CHARGE
        + _optional_max(_max_identity_charge())
        + _max_metadata_charge()
    )


def _max_volume_charge() -> int:
    return (
        model_object_charge(_VOLUME_LAYOUT)
        + 2 * model_text_charge(_VOLUME_TEXT_UTF8_LIMIT)
    )


def _max_volume_evidence_charge() -> int:
    return (
        model_object_charge(_VOLUME_EVIDENCE_LAYOUT)
        + _optional_max(model_text_charge(_VOLUME_TEXT_UTF8_LIMIT))
        + _optional_max(model_text_charge(_PATH_UTF8_LIMIT))
        + JSON_SCALAR_CHARGE
    )


def _max_profile_charge() -> int:
    return (
        model_object_charge(_PROFILE_LAYOUT)
        + model_text_charge(_VOLUME_TEXT_UTF8_LIMIT)
        + 6 * JSON_SCALAR_CHARGE
    )


def _max_operation_charge_without_dependencies() -> int:
    return (
        model_object_charge(_OPERATION_LAYOUT)
        + model_text_charge(_FIXED_ID_UTF8_LIMIT)
        + model_text_charge(_enum_utf8_limit(OperationKind))
        + 2 * _optional_max(model_text_charge(_PATH_UTF8_LIMIT))
        + model_text_charge(_PATH_UTF8_LIMIT)
        + 4 * _optional_max(_max_stat_charge())
        + _optional_max(_max_metadata_charge())
        + JSON_SCALAR_CHARGE
        + model_array_charge(0)
        + model_text_charge(_enum_utf8_limit(OperationReason))
        + _optional_max(model_text_charge(_enum_utf8_limit(BlockedReason)))
    )


def _max_assignment_item_charge() -> int:
    return (
        model_object_charge(_ASSIGNMENT_ITEM_LAYOUT)
        + 4 * model_text_charge(_PATH_UTF8_LIMIT)
        + 2
        * _optional_max(model_text_charge(ASSIGNMENT_TEXT_UTF8_LIMIT))
    )


def _max_plan_charge() -> int:
    row_limit = MAX_PLAN_REVIEW_ROWS
    dependency_limit = row_limit * (row_limit - 1) // 2
    filter_charge = (
        model_array_charge(FILTER_PATTERN_LIMIT)
        + FILTER_PATTERN_LIMIT * model_text_charge(0)
        + 5 * FILTER_TOTAL_UTF8_LIMIT
    )
    return (
        model_object_charge(_PLAN_LAYOUT)
        + 2
        * (
            model_object_charge(_ROOT_LAYOUT)
            + model_text_charge(_PATH_UTF8_LIMIT)
            + model_text_charge(MAX_ROOT_ID_UTF8_BYTES)
        )
        + 2 * _optional_max(_max_volume_charge())
        + 2 * _optional_max(_max_volume_evidence_charge())
        + 2 * _max_profile_charge()
        + 2 * JSON_SCALAR_CHARGE
        + model_array_charge(row_limit)
        + row_limit * _max_operation_charge_without_dependencies()
        + dependency_limit
        * (JSON_LIST_SLOT_CHARGE + model_text_charge(_FIXED_ID_UTF8_LIMIT))
        + model_object_charge(_ASSIGNMENT_LAYOUT)
        + model_text_charge(len("identity"))
        + model_text_charge(len("1"))
        + model_array_charge(row_limit)
        + row_limit * _max_assignment_item_charge()
        + model_object_charge(_PRESERVATION_LAYOUT)
        + 3 * JSON_SCALAR_CHARGE
        + filter_charge
        + model_text_charge(_enum_utf8_limit(DeletionPolicy))
        + JSON_SCALAR_CHARGE
        + 2 * model_text_charge(_DIGEST_HEX_UTF8_LIMIT)
        + model_array_charge(PLAN_REQUIRED_VOLUME_LIMIT)
        + PLAN_REQUIRED_VOLUME_LIMIT * _max_volume_charge()
        + JSON_SCALAR_CHARGE
    )


def _max_plan_request_charge() -> int:
    return (
        model_object_charge(_PLAN_REQUEST_LAYOUT)
        + JSON_SCALAR_CHARGE
        + model_text_charge(len("plan"))
        + model_text_charge(MAX_REQUEST_ID_UTF8_BYTES)
        + 2 * model_text_charge(_PATH_UTF8_LIMIT)
        + model_object_charge(_PLAN_OPTIONS_LAYOUT)
        + model_text_charge(_enum_utf8_limit(DeletionPolicy))
        + model_object_charge(_PRESERVATION_LAYOUT)
        + 3 * JSON_SCALAR_CHARGE
        + model_array_charge(FILTER_PATTERN_LIMIT)
        + FILTER_PATTERN_LIMIT * model_text_charge(0)
        + 5 * FILTER_TOTAL_UTF8_LIMIT
        + 3 * JSON_SCALAR_CHARGE
    )


def _max_content_evidence_charge() -> int:
    return (
        model_object_charge(_CONTENT_EVIDENCE_LAYOUT)
        + model_text_charge(len("xxh3_128"))
        + model_text_charge(32)
        + JSON_SCALAR_CHARGE
        + model_text_charge(_enum_utf8_limit(Provenance))
        + model_text_charge(_TIMESTAMP_UTF8_LIMIT)
    )


def _max_attestation_charge() -> int:
    return (
        model_object_charge(_ATTESTATION_LAYOUT)
        + _max_content_evidence_charge()
        + _max_stat_charge()
    )


def _max_recorded_identity_charge() -> int:
    return (
        model_object_charge(_RECORDED_IDENTITY_LAYOUT)
        + 2 * model_text_charge(_SQLITE_ID_UTF8_LIMIT)
        + model_text_charge(_FIXED_ID_UTF8_LIMIT)
        + model_text_charge(_PATH_UTF8_LIMIT)
    )


def _max_published_evidence_charge() -> int:
    return (
        model_object_charge(_PUBLISHED_EVIDENCE_LAYOUT)
        + _max_attestation_charge()
        + _optional_max(_max_recorded_identity_charge())
    )


def _max_task_issue_charge() -> int:
    return (
        model_object_charge(_TASK_ISSUE_LAYOUT)
        + model_text_charge(_enum_utf8_limit(TaskRecordingIssueReason))
        + _optional_max(model_text_charge(MAX_DIAGNOSTIC_UTF8_BYTES))
    )


def _max_execution_set_charge() -> int:
    row_limit = MAX_PLAN_REVIEW_ROWS
    id_occurrence = model_text_charge(_FIXED_ID_UTF8_LIMIT)
    return (
        model_object_charge(_EXECUTION_SET_LAYOUT)
        + _max_plan_charge()
        + 2 * (model_array_charge(row_limit) + row_limit * id_occurrence)
        + id_occurrence
        + model_mapping_charge(row_limit)
        + row_limit
        * (id_occurrence + model_text_charge(_enum_utf8_limit(Outcome)))
        + _optional_max(
            model_object_charge(_COMMITMENT_LAYOUT)
            + 2 * model_text_charge(_DIGEST_HEX_UTF8_LIMIT)
            + model_text_charge(_TIMESTAMP_UTF8_LIMIT)
        )
        + model_mapping_charge(row_limit)
        + row_limit * (id_occurrence + _max_published_evidence_charge())
        + model_text_charge(_enum_utf8_limit(RecordingStatus))
        + model_mapping_charge(row_limit)
        + row_limit
        * (
            id_occurrence
            + model_text_charge(_enum_utf8_limit(ItemRecordingReason))
        )
        + model_array_charge(_TASK_ISSUE_LIMIT)
        + _TASK_ISSUE_LIMIT * _max_task_issue_charge()
        + 2 * JSON_SCALAR_CHARGE
    )


def _max_post_copy_candidate_charge() -> int:
    return (
        model_object_charge(_POST_COPY_CANDIDATE_LAYOUT)
        + model_text_charge(_FIXED_ID_UTF8_LIMIT)
        + 2 * model_text_charge(_PATH_UTF8_LIMIT)
        + _max_stat_charge()
        + _max_attestation_charge()
        + _optional_max(_max_recorded_identity_charge())
    )


def _max_post_copy_selection_charge() -> int:
    row_limit = MAX_PLAN_REVIEW_ROWS
    return (
        model_object_charge(_POST_COPY_SELECTION_LAYOUT)
        + model_array_charge(row_limit)
        + row_limit * _max_post_copy_candidate_charge()
        + model_array_charge(row_limit)
        + row_limit
        * (
            model_object_charge(_COMPLETION_LAYOUT)
            + model_text_charge(_FIXED_ID_UTF8_LIMIT)
            + JSON_SCALAR_CHARGE
        )
        + JSON_SCALAR_CHARGE
    )


def _max_phase_result_charge() -> int:
    return (
        model_object_charge(_PHASE_RESULT_LAYOUT)
        + model_text_charge(len(ExecuteContinuation.phase))
        + model_text_charge(_enum_utf8_limit(PhaseStatus))
        + 4 * JSON_SCALAR_CHARGE
        + _optional_max(model_text_charge(MAX_DIAGNOSTIC_UTF8_BYTES))
    )


_PLAN_REQUEST_MAX_OCCURRENCE_CHARGE = _max_plan_request_charge()
_EXECUTE_MAX_OCCURRENCE_CHARGE = (
    model_object_charge(_EXECUTE_LAYOUT)
    + JSON_SCALAR_CHARGE
    + model_text_charge(len("execute"))
    + model_text_charge(len(ExecuteContinuation.phase))
    + _max_execution_set_charge()
    + _optional_max(model_text_charge(_TIMESTAMP_UTF8_LIMIT))
    + JSON_SCALAR_CHARGE
)
_VERIFY_MAX_OCCURRENCE_CHARGE = (
    model_object_charge(_VERIFY_LAYOUT)
    + JSON_SCALAR_CHARGE
    + model_text_charge(len("execute"))
    + model_text_charge(len(VerifyContinuation.phase))
    + _max_execution_set_charge()
    + _optional_max(model_text_charge(_TIMESTAMP_UTF8_LIMIT))
    + _max_post_copy_selection_charge()
    + 2 * model_text_charge(max(
        _enum_utf8_limit(SessionState),
        _enum_utf8_limit(RecordingStatus),
    ))
    + _max_phase_result_charge()
    + model_array_charge(MAX_PLAN_REVIEW_ROWS)
    + MAX_PLAN_REVIEW_ROWS * model_text_charge(_FIXED_ID_UTF8_LIMIT)
)
_EXECUTION_MAX_OCCURRENCE_CHARGE = max(
    _EXECUTE_MAX_OCCURRENCE_CHARGE,
    _VERIFY_MAX_OCCURRENCE_CHARGE,
)
PLAN_REQUEST_PAYLOAD_BYTE_LIMIT = canonical_byte_ceiling(
    _PLAN_REQUEST_MAX_OCCURRENCE_CHARGE
)
EXECUTION_REQUEST_PAYLOAD_BYTE_LIMIT = canonical_byte_ceiling(
    _EXECUTION_MAX_OCCURRENCE_CHARGE
)


def _charge_fixed_text(
    counter: JsonEnvelopeCounter,
    value: object,
    expected: str,
    context: str,
) -> None:
    if value != expected or type(value) is not str:
        raise ValueError(f"{context} must be {expected!r}")
    counter.text(value, context, maximum_utf8_bytes=len(expected))


def _charge_enum(
    counter: JsonEnvelopeCounter,
    value: object,
    enum_type: type,
    context: str,
) -> None:
    if type(value) is not enum_type:
        raise TypeError(f"{context} has the wrong type")
    counter.text(
        value.value,
        context,
        maximum_utf8_bytes=_enum_utf8_limit(enum_type),
    )


def _charge_path(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
    *,
    relative: bool,
    allow_none: bool = False,
) -> None:
    if value is None and allow_none:
        counter.null()
        return
    if relative:
        validate_relative_path(value)
    else:
        require_utf16_path(value, context)
    counter.text(value, context, maximum_utf8_bytes=_PATH_UTF8_LIMIT)


def _charge_optional_integer(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if value is None:
        counter.null()
    else:
        counter.integer(value, context)


def _charge_datetime(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
    *,
    allow_none: bool = False,
) -> None:
    if value is None and allow_none:
        counter.null()
        return
    if type(value) is not datetime:
        raise TypeError(f"{context} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{context} must be timezone-aware")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError(f"{context} must be UTC")
    counter.text(
        value.isoformat(),
        context,
        maximum_utf8_bytes=_TIMESTAMP_UTF8_LIMIT,
    )


def _charge_metadata(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
    *,
    allow_none: bool = True,
) -> None:
    if value is None and allow_none:
        counter.null()
        return
    if type(value) is not MetadataSnapshot:
        raise TypeError(f"{context} must be MetadataSnapshot")
    require_safe_int(value.attributes, f"{context}.attributes")
    if value.created_ns is not None:
        require_signed_64(value.created_ns, f"{context}.created_ns")
    counter.object(_METADATA_LAYOUT)
    counter.integer(value.attributes, f"{context}.attributes")
    _charge_optional_integer(counter, value.created_ns, f"{context}.created_ns")


def _charge_file_identity(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if value is None:
        counter.null()
        return
    if type(value) is not FileIdentity:
        raise TypeError(f"{context} must be FileIdentity or None")
    require_utf16_text(
        value.volume_serial,
        f"{context}.volume_serial",
        maximum_units=MAX_VOLUME_TEXT_UTF16_UNITS,
        allow_empty=False,
    )
    file_index = file_index_128_to_text(
        value.file_index,
        f"{context}.file_index",
    )
    counter.object(_IDENTITY_LAYOUT)
    counter.text(
        value.volume_serial,
        f"{context}.volume_serial",
        maximum_utf8_bytes=_VOLUME_TEXT_UTF8_LIMIT,
        minimum_utf8_bytes=1,
    )
    counter.text(
        file_index,
        f"{context}.file_index",
        maximum_utf8_bytes=_FILE_INDEX_TEXT_UTF8_LIMIT,
        minimum_utf8_bytes=1,
    )


def _charge_stat(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
    *,
    allow_none: bool = True,
) -> None:
    if value is None and allow_none:
        counter.null()
        return
    if type(value) is not FileStat:
        raise TypeError(f"{context} must be FileStat")
    if type(value.kind) is not EntryKind:
        raise TypeError(f"{context}.kind has the wrong type")
    require_signed_64(value.size, f"{context}.size")
    require_signed_64(value.mtime_ns, f"{context}.mtime_ns")
    require_safe_int(value.nlink, f"{context}.nlink")
    if value.nlink < 1:
        raise ValueError(f"{context}.nlink must be positive")
    if type(value.metadata) is not MetadataSnapshot:
        raise TypeError(f"{context}.metadata must be MetadataSnapshot")
    counter.object(_STAT_LAYOUT)
    _charge_enum(counter, value.kind, EntryKind, f"{context}.kind")
    counter.integer(value.size, f"{context}.size")
    counter.integer(value.mtime_ns, f"{context}.mtime_ns")
    _charge_file_identity(counter, value.file_identity, f"{context}.identity")
    counter.integer(value.nlink, f"{context}.nlink")
    _charge_metadata(counter, value.metadata, f"{context}.metadata", allow_none=False)


def _charge_root(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not Root:
        raise TypeError(f"{context} must be Root")
    require_utf16_path(value.path, f"{context}.path")
    if not value.path:
        raise ValueError(f"{context}.path is required")
    require_utf8_text(
        value.root_id,
        f"{context}.root_id",
        minimum_bytes=1,
        maximum_bytes=MAX_ROOT_ID_UTF8_BYTES,
    )
    counter.object(_ROOT_LAYOUT)
    counter.text(
        value.path,
        f"{context}.path",
        maximum_utf8_bytes=_PATH_UTF8_LIMIT,
        minimum_utf8_bytes=1,
    )
    counter.text(
        value.root_id,
        f"{context}.root_id",
        maximum_utf8_bytes=MAX_ROOT_ID_UTF8_BYTES,
        minimum_utf8_bytes=1,
    )


def _charge_volume(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if value is None:
        counter.null()
        return
    if type(value) is not VolumeId:
        raise TypeError(f"{context} must be VolumeId or None")
    for field_name, text in (("serial", value.serial), ("fs_type", value.fs_type)):
        require_utf16_text(
            text,
            f"{context}.{field_name}",
            maximum_units=MAX_VOLUME_TEXT_UTF16_UNITS,
            allow_empty=False,
        )
    counter.object(_VOLUME_LAYOUT)
    counter.text(
        value.serial,
        f"{context}.serial",
        maximum_utf8_bytes=_VOLUME_TEXT_UTF8_LIMIT,
    )
    counter.text(
        value.fs_type,
        f"{context}.fs_type",
        maximum_utf8_bytes=_VOLUME_TEXT_UTF8_LIMIT,
    )


def _charge_volume_evidence(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if value is None:
        counter.null()
        return
    if type(value) is not VolumeEvidence:
        raise TypeError(f"{context} must be VolumeEvidence or None")
    if value.label is None:
        counter.object(_VOLUME_EVIDENCE_LAYOUT)
        counter.null()
    else:
        require_utf16_text(
            value.label,
            f"{context}.label",
            maximum_units=MAX_VOLUME_TEXT_UTF16_UNITS,
        )
        counter.object(_VOLUME_EVIDENCE_LAYOUT)
        counter.text(
            value.label,
            f"{context}.label",
            maximum_utf8_bytes=_VOLUME_TEXT_UTF8_LIMIT,
        )
    if value.device_id is None:
        counter.null()
    else:
        require_utf16_path(value.device_id, f"{context}.device_id")
        counter.text(
            value.device_id,
            f"{context}.device_id",
            maximum_utf8_bytes=_PATH_UTF8_LIMIT,
        )
    counter.boolean(value.clone_ambiguous, f"{context}.clone_ambiguous")


def _charge_profile(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not CapabilityProfile:
        raise TypeError(f"{context} must be CapabilityProfile")
    require_utf16_text(
        value.fs_type,
        f"{context}.fs_type",
        maximum_units=MAX_VOLUME_TEXT_UTF16_UNITS,
    )
    require_safe_int(value.mtime_granularity_ns, f"{context}.mtime_granularity_ns")
    require_safe_int(value.max_path, f"{context}.max_path")
    if value.mtime_granularity_ns < 1 or not 1 <= value.max_path <= MAX_PATH_UTF16_UNITS:
        raise ValueError(f"{context} has invalid path or timestamp capability")
    counter.object(_PROFILE_LAYOUT)
    counter.text(
        value.fs_type,
        f"{context}.fs_type",
        maximum_utf8_bytes=_VOLUME_TEXT_UTF8_LIMIT,
    )
    counter.integer(value.mtime_granularity_ns, f"{context}.mtime_granularity_ns")
    counter.boolean(value.stable_file_identity, f"{context}.stable_file_identity")
    if value.incurs_seek_penalty is None:
        counter.null()
    else:
        counter.boolean(value.incurs_seek_penalty, f"{context}.incurs_seek_penalty")
    counter.integer(value.max_path, f"{context}.max_path")
    counter.boolean(value.supports_ads, f"{context}.supports_ads")
    counter.boolean(value.supports_hardlinks, f"{context}.supports_hardlinks")


def _charge_operation(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not PlanOperation:
        raise TypeError(f"{context} must be PlanOperation")
    op_id = str(value.op_id)
    if len(op_id) != 32 or any(character not in "0123456789abcdef" for character in op_id):
        raise ValueError(f"{context}.op_id is invalid")
    if type(value.dependencies) is not tuple:
        raise TypeError(f"{context}.dependencies must be a tuple")
    counter.object(_OPERATION_LAYOUT)
    counter.text(op_id, f"{context}.op_id", maximum_utf8_bytes=_FIXED_ID_UTF8_LIMIT)
    _charge_enum(counter, value.kind, OperationKind, f"{context}.kind")
    _charge_path(counter, value.source_rel_path, f"{context}.source_rel_path", relative=True, allow_none=True)
    _charge_path(counter, value.target_rel_path, f"{context}.target_rel_path", relative=True)
    _charge_stat(counter, value.source_expected, f"{context}.source_expected")
    _charge_stat(counter, value.target_expected, f"{context}.target_expected")
    _charge_stat(counter, value.intended, f"{context}.intended")
    _charge_path(counter, value.prior_target_rel_path, f"{context}.prior_target_rel_path", relative=True, allow_none=True)
    _charge_stat(counter, value.prior_target_expected, f"{context}.prior_target_expected")
    _charge_metadata(counter, value.metadata, f"{context}.metadata")
    require_signed_64(value.content_bytes, f"{context}.content_bytes")
    counter.integer(value.content_bytes, f"{context}.content_bytes")
    counter.array(len(value.dependencies))
    dependency_ids: set[str] = set()
    for dependency in value.dependencies:
        dependency_id = str(dependency)
        if len(dependency_id) != 32 or any(
            character not in "0123456789abcdef" for character in dependency_id
        ):
            raise ValueError(f"{context}.dependencies contains an invalid id")
        if dependency_id in dependency_ids:
            raise ValueError(f"{context}.dependencies contain a duplicate id")
        dependency_ids.add(dependency_id)
        counter.text(
            dependency_id,
            f"{context}.dependencies[]",
            maximum_utf8_bytes=_FIXED_ID_UTF8_LIMIT,
        )
    _charge_enum(counter, value.reason, OperationReason, f"{context}.reason")
    if value.blocked_reason is None:
        counter.null()
    else:
        _charge_enum(counter, value.blocked_reason, BlockedReason, f"{context}.blocked_reason")


def _charge_plan(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not Plan:
        raise TypeError(f"{context} must be Plan")
    if type(value.operations) is not tuple:
        raise TypeError(f"{context}.operations must be a tuple")
    if len(value.operations) > MAX_PLAN_REVIEW_ROWS:
        raise ValueError(f"{context}.operations exceed the plan row limit")
    if type(value.assignment) is not Assignment:
        raise TypeError(f"{context}.assignment must be Assignment")
    if type(value.assignment.items) is not tuple:
        raise TypeError(f"{context}.assignment.items must be a tuple")
    if len(value.assignment.items) > ASSIGNMENT_ITEM_LIMIT:
        raise ValueError(f"{context}.assignment exceeds the plan row limit")
    if type(value.required_volumes) is not frozenset:
        raise TypeError(f"{context}.required_volumes must be a frozenset")
    if len(value.required_volumes) > PLAN_REQUIRED_VOLUME_LIMIT:
        raise ValueError(f"{context}.required_volumes exceed their source limit")
    maximum_dependencies = len(value.operations) * (len(value.operations) - 1) // 2
    dependency_count = 0
    for operation in value.operations:
        if type(operation) is not PlanOperation:
            raise TypeError(f"{context}.operations contain an invalid value")
        if type(operation.dependencies) is not tuple:
            raise TypeError(f"{context}.operation dependencies must be tuples")
        dependency_count += len(operation.dependencies)
        if dependency_count > maximum_dependencies:
            raise ValueError(f"{context}.dependencies exceed their source limit")

    counter.object(_PLAN_LAYOUT)
    _charge_root(counter, value.source_root, f"{context}.source_root")
    _charge_root(counter, value.target_root, f"{context}.target_root")
    _charge_volume(counter, value.source_volume_id, f"{context}.source_volume_id")
    _charge_volume(counter, value.target_volume_id, f"{context}.target_volume_id")
    _charge_volume_evidence(counter, value.source_volume_evidence, f"{context}.source_volume_evidence")
    _charge_volume_evidence(counter, value.target_volume_evidence, f"{context}.target_volume_evidence")
    _charge_profile(counter, value.source_profile, f"{context}.source_profile")
    _charge_profile(counter, value.target_profile, f"{context}.target_profile")
    counter.boolean(value.source_complete, f"{context}.source_complete")
    counter.boolean(value.target_complete, f"{context}.target_complete")
    counter.array(len(value.operations))
    known_ids: set[str] = set()
    for index, operation in enumerate(value.operations):
        _charge_operation(counter, operation, f"{context}.operations[{index}]")
        op_id = str(operation.op_id)
        if op_id in known_ids:
            raise ValueError(f"{context}.operations contain a duplicate id")
        if any(str(dependency) not in known_ids for dependency in operation.dependencies):
            raise ValueError(f"{context}.operations are not dependency ordered")
        known_ids.add(op_id)

    validate_assignment(value.assignment)
    if value.assignment.policy_name != "identity" or value.assignment.policy_version != "1":
        raise ValueError("workflow execution payloads require identity assignment")
    counter.object(_ASSIGNMENT_LAYOUT)
    _charge_fixed_text(counter, value.assignment.policy_name, "identity", f"{context}.assignment.policy_name")
    _charge_fixed_text(counter, value.assignment.policy_version, "1", f"{context}.assignment.policy_version")
    counter.array(len(value.assignment.items))
    for index, item in enumerate(value.assignment.items):
        counter.object(_ASSIGNMENT_ITEM_LAYOUT)
        for field_name in (
            "source_rel_path",
            "source_rel_path_key",
            "target_rel_path",
            "target_rel_path_key",
        ):
            _charge_path(
                counter,
                getattr(item, field_name),
                f"{context}.assignment.items[{index}].{field_name}",
                relative=True,
            )
        counter.optional_text(
            item.group_id,
            f"{context}.assignment.items[{index}].group_id",
            maximum_utf8_bytes=ASSIGNMENT_TEXT_UTF8_LIMIT,
        )
        counter.optional_text(
            item.conflict,
            f"{context}.assignment.items[{index}].conflict",
            maximum_utf8_bytes=ASSIGNMENT_TEXT_UTF8_LIMIT,
        )

    if type(value.preservation) is not PreservationPolicy:
        raise TypeError(f"{context}.preservation has the wrong type")
    counter.object(_PRESERVATION_LAYOUT)
    counter.boolean(value.preservation.preserve_ads, f"{context}.preservation.preserve_ads")
    counter.boolean(value.preservation.preserve_created, f"{context}.preservation.preserve_created")
    counter.boolean(value.preservation.preserve_acl, f"{context}.preservation.preserve_acl")
    validate_filter_set(value.filter_snapshot)
    counter.array(len(value.filter_snapshot.patterns))
    for pattern in value.filter_snapshot.patterns:
        counter.text(
            pattern,
            f"{context}.filters[]",
            maximum_utf8_bytes=FILTER_PATTERN_UTF8_LIMIT,
            minimum_utf8_bytes=1,
        )
    _charge_enum(counter, value.deletion_policy, DeletionPolicy, f"{context}.deletion_policy")
    counter.boolean(value.trash_on_update, f"{context}.trash_on_update")
    _charge_hex(counter, value.policy_fingerprint, f"{context}.policy_fingerprint")
    counter.array(len(value.required_volumes))
    for index, volume in enumerate(sorted(value.required_volumes)):
        _charge_volume(counter, volume, f"{context}.required_volumes[{index}]")
    require_signed_64(value.required_bytes, f"{context}.required_bytes")
    counter.integer(value.required_bytes, f"{context}.required_bytes")
    _charge_hex(counter, str(value.fingerprint), f"{context}.fingerprint")


def _charge_hex(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
    *,
    length: int = 64,
) -> None:
    if type(value) is not str or len(value) != length or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{context} must be {length} lowercase hexadecimal characters")
    counter.text(value, context, maximum_utf8_bytes=length)


def _charge_plan_request(request: object) -> JsonEnvelopeCounter:
    if type(request) is not PlanRequest:
        raise TypeError("plan payload requires PlanRequest")
    if type(request.options) is not SyncOptions:
        raise TypeError("plan payload options must be SyncOptions")
    options = request.options
    if type(options.destination_policy) is not IdentityDestinationPolicy:
        raise ValueError("workflow payloads support only the identity destination policy")
    if options.destination_policy.name != "identity" or options.destination_policy.version != "1":
        raise ValueError("identity destination policy fields changed")
    require_utf8_text(
        request.request_id,
        "plan request id",
        minimum_bytes=1,
        maximum_bytes=MAX_REQUEST_ID_UTF8_BYTES,
    )
    require_utf16_path(request.source_path, "plan source path")
    require_utf16_path(request.target_path, "plan target path")
    validate_filter_set(options.filters)

    counter = JsonEnvelopeCounter()
    counter.object(_PLAN_REQUEST_LAYOUT)
    counter.integer(_PLAN_SCHEMA_VERSION, "plan schema version")
    _charge_fixed_text(counter, "plan", "plan", "plan kind")
    counter.text(request.request_id, "plan request id", maximum_utf8_bytes=MAX_REQUEST_ID_UTF8_BYTES, minimum_utf8_bytes=1)
    counter.text(request.source_path, "plan source path", maximum_utf8_bytes=_PATH_UTF8_LIMIT)
    counter.text(request.target_path, "plan target path", maximum_utf8_bytes=_PATH_UTF8_LIMIT)
    counter.object(_PLAN_OPTIONS_LAYOUT)
    _charge_enum(counter, options.deletion_policy, DeletionPolicy, "plan deletion policy")
    if type(options.preservation) is not PreservationPolicy:
        raise TypeError("plan preservation has the wrong type")
    counter.object(_PRESERVATION_LAYOUT)
    counter.boolean(options.preservation.preserve_ads, "plan preserve_ads")
    counter.boolean(options.preservation.preserve_created, "plan preserve_created")
    counter.boolean(options.preservation.preserve_acl, "plan preserve_acl")
    counter.array(len(options.filters.patterns))
    for pattern in options.filters.patterns:
        counter.text(pattern, "plan filter", maximum_utf8_bytes=FILTER_PATTERN_UTF8_LIMIT, minimum_utf8_bytes=1)
    counter.boolean(options.trash_on_update, "plan trash_on_update")
    counter.boolean(options.propagate_source_casing, "plan propagate_source_casing")
    counter.boolean(options.internal_mirror_authorized, "plan internal_mirror_authorized")
    counter.require_within(_PLAN_REQUEST_MAX_OCCURRENCE_CHARGE, "plan payload")
    return counter


def _charge_content_evidence(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not ContentEvidence:
        raise TypeError(f"{context} must be ContentEvidence")
    if value.algorithm != "xxh3_128" or type(value.digest) is not bytes or len(value.digest) != 16:
        raise ValueError(f"{context} has invalid content evidence")
    require_signed_64(value.size, f"{context}.size")
    counter.object(_CONTENT_EVIDENCE_LAYOUT)
    _charge_fixed_text(counter, value.algorithm, "xxh3_128", f"{context}.algorithm")
    _charge_hex(counter, value.digest.hex(), f"{context}.digest", length=32)
    counter.integer(value.size, f"{context}.size")
    _charge_enum(counter, value.provenance, Provenance, f"{context}.provenance")
    _charge_datetime(counter, value.observed_at, f"{context}.observed_at")


def _charge_attestation(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not Attestation:
        raise TypeError(f"{context} must be Attestation")
    counter.object(_ATTESTATION_LAYOUT)
    _charge_content_evidence(counter, value.content, f"{context}.content")
    _charge_stat(counter, value.subject, f"{context}.subject", allow_none=False)
    if value.content.size != value.subject.size:
        raise ValueError(f"{context} content and subject sizes disagree")


def _charge_recorded_identity(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
    identity_type: type,
) -> None:
    if value is None:
        counter.null()
        return
    if type(value) is not identity_type:
        raise TypeError(f"{context} has the wrong type")
    counter.object(_RECORDED_IDENTITY_LAYOUT)
    for field_name in ("row_id", "location_id"):
        raw = getattr(value, field_name)
        if type(raw) is not str or not raw.isascii() or not raw.isdecimal() or raw.startswith("0") or len(raw) > _SQLITE_ID_UTF8_LIMIT:
            raise ValueError(f"{context}.{field_name} must be a positive SQLite integer id")
        counter.text(raw, f"{context}.{field_name}", maximum_utf8_bytes=_SQLITE_ID_UTF8_LIMIT, minimum_utf8_bytes=1)
    _charge_fixed_id(counter, value.scope_token, f"{context}.scope_token")
    canonical = normalize_relative_path(value.rel_path_key)
    if canonical != value.rel_path_key:
        raise ValueError(f"{context}.rel_path_key is not canonical")
    _charge_path(counter, value.rel_path_key, f"{context}.rel_path_key", relative=True)


def _charge_fixed_id(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not str or len(value) != 32 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{context} must be 32 lowercase hexadecimal characters")
    counter.text(value, context, maximum_utf8_bytes=_FIXED_ID_UTF8_LIMIT)


def _charge_published_evidence(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not PublishedCopyEvidence:
        raise TypeError(f"{context} has the wrong type")
    if value.attestation.content.provenance is not Provenance.COPY_ATTESTED:
        raise ValueError(f"{context} must carry copy-attested evidence")
    if value.attestation.subject.kind is not EntryKind.FILE:
        raise ValueError(f"{context} must attest a regular file")
    counter.object(_PUBLISHED_EVIDENCE_LAYOUT)
    _charge_attestation(counter, value.attestation, f"{context}.attestation")
    _charge_recorded_identity(counter, value.recorded_identity, f"{context}.recorded_identity", RecordedCopyIdentity)


def _charge_task_issue(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not TaskRecordingIssue:
        raise TypeError(f"{context} has the wrong type")
    counter.object(_TASK_ISSUE_LAYOUT)
    _charge_enum(counter, value.reason, TaskRecordingIssueReason, f"{context}.reason")
    counter.optional_text(value.detail, f"{context}.detail", maximum_utf8_bytes=MAX_DIAGNOSTIC_UTF8_BYTES)


def _charge_commitment(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if value is None:
        counter.null()
        return
    if type(value) is not Commitment:
        raise TypeError(f"{context} has the wrong type")
    if type(value.selection_digest) is not bytes or len(value.selection_digest) != 32:
        raise ValueError(f"{context}.selection_digest is invalid")
    counter.object(_COMMITMENT_LAYOUT)
    _charge_hex(counter, str(value.plan_fingerprint), f"{context}.plan_fingerprint")
    _charge_hex(counter, value.selection_digest.hex(), f"{context}.selection_digest")
    _charge_datetime(counter, value.committed_at, f"{context}.committed_at")


def _charge_execution_set(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not ExecutionSet:
        raise TypeError(f"{context} must be ExecutionSet")
    for field_name in ("selection", "user_deselected"):
        collection = getattr(value, field_name)
        if type(collection) is not frozenset:
            raise TypeError(f"{context}.{field_name} must be a frozenset")
        if len(collection) > MAX_PLAN_REVIEW_ROWS:
            raise ValueError(f"{context}.{field_name} exceeds the plan row limit")
    for field_name in ("status", "published_evidence", "recording_reasons"):
        collection = getattr(value, field_name)
        if type(collection) is not dict:
            raise TypeError(f"{context}.{field_name} must be a dict")
        if len(collection) > MAX_PLAN_REVIEW_ROWS:
            raise ValueError(f"{context}.{field_name} exceeds the plan row limit")
    if type(value.recording_issues) is not tuple or len(value.recording_issues) > _TASK_ISSUE_LIMIT:
        raise ValueError(f"{context}.recording_issues exceed their source limit")

    counter.object(_EXECUTION_SET_LAYOUT)
    _charge_plan(counter, value.plan, f"{context}.plan")
    known_ids = {str(operation.op_id) for operation in value.plan.operations}
    for field_name in ("selection", "user_deselected"):
        collection = getattr(value, field_name)
        counter.array(len(collection))
        for op_id in collection:
            raw = str(op_id)
            _charge_fixed_id(counter, raw, f"{context}.{field_name}[]")
            if raw not in known_ids:
                raise ValueError(f"{context}.{field_name} contains an unknown id")
    _charge_fixed_id(counter, str(value.run_id), f"{context}.run_id")
    counter.mapping(len(value.status))
    for op_id, outcome in value.status.items():
        raw = str(op_id)
        _charge_fixed_id(counter, raw, f"{context}.status key")
        if raw not in known_ids:
            raise ValueError(f"{context}.status contains an unknown id")
        _charge_enum(counter, outcome, Outcome, f"{context}.status[{raw}]")
    _charge_commitment(counter, value.commitment, f"{context}.commitment")
    counter.mapping(len(value.published_evidence))
    for op_id, evidence in value.published_evidence.items():
        raw = str(op_id)
        _charge_fixed_id(counter, raw, f"{context}.published_evidence key")
        if raw not in known_ids:
            raise ValueError(f"{context}.published_evidence contains an unknown id")
        _charge_published_evidence(counter, evidence, f"{context}.published_evidence[{raw}]")
    _charge_enum(counter, value.recording, RecordingStatus, f"{context}.recording")
    counter.mapping(len(value.recording_reasons))
    for op_id, reason in value.recording_reasons.items():
        raw = str(op_id)
        _charge_fixed_id(counter, raw, f"{context}.recording_reasons key")
        if raw not in known_ids:
            raise ValueError(f"{context}.recording_reasons contains an unknown id")
        _charge_enum(counter, reason, ItemRecordingReason, f"{context}.recording_reasons[{raw}]")
    counter.array(len(value.recording_issues))
    for index, issue in enumerate(value.recording_issues):
        _charge_task_issue(counter, issue, f"{context}.recording_issues[{index}]")
    require_safe_int(value.omitted_detail_count, f"{context}.omitted_detail_count")
    require_signed_64(value.bytes_done_high_water, f"{context}.bytes_done_high_water")
    counter.integer(value.omitted_detail_count, f"{context}.omitted_detail_count")
    counter.integer(value.bytes_done_high_water, f"{context}.bytes_done_high_water")


def _charge_post_copy_candidate(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not PostCopyCandidate:
        raise TypeError(f"{context} has the wrong type")
    counter.object(_POST_COPY_CANDIDATE_LAYOUT)
    _charge_fixed_id(counter, value.item_id, f"{context}.item_id")
    if not isinstance(value.root, Path):
        raise TypeError(f"{context}.root must be a Path")
    root = str(value.root)
    require_utf16_path(root, f"{context}.root")
    counter.text(root, f"{context}.root", maximum_utf8_bytes=_PATH_UTF8_LIMIT)
    _charge_path(counter, value.display_path, f"{context}.display_path", relative=True)
    _charge_stat(counter, value.expected_stat, f"{context}.expected_stat", allow_none=False)
    _charge_attestation(counter, value.copy_attestation, f"{context}.copy_attestation")
    _charge_recorded_identity(counter, value.recorded_identity, f"{context}.recorded_identity", PostCopyRecordIdentity)
    if value.copy_attestation.content.provenance is not Provenance.COPY_ATTESTED:
        raise ValueError(f"{context} must carry copy-attested evidence")
    if value.copy_attestation.subject != value.expected_stat:
        raise ValueError(f"{context} attestation differs from its expected stat")
    if value.expected_stat.kind is not EntryKind.FILE:
        raise ValueError(f"{context} must name a regular file")
    if (
        value.recorded_identity is not None
        and value.recorded_identity.rel_path_key
        != normalize_relative_path(value.display_path)
    ):
        raise ValueError(f"{context} recorded identity differs from its path")


def _charge_post_copy_selection(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not PostCopySelection:
        raise TypeError(f"{context} has the wrong type")
    if type(value.candidates) is not tuple or len(value.candidates) > MAX_PLAN_REVIEW_ROWS:
        raise ValueError(f"{context}.candidates exceed the plan row limit")
    completed = value._completed_bytes
    if type(completed) is not dict or len(completed) > len(value.candidates):
        raise ValueError(f"{context}.completed_bytes exceed the candidate limit")
    counter.object(_POST_COPY_SELECTION_LAYOUT)
    counter.array(len(value.candidates))
    candidate_ids: set[str] = set()
    for index, candidate in enumerate(value.candidates):
        _charge_post_copy_candidate(counter, candidate, f"{context}.candidates[{index}]")
        if candidate.item_id in candidate_ids:
            raise ValueError(f"{context}.candidates contain a duplicate id")
        candidate_ids.add(candidate.item_id)
    counter.array(len(completed))
    completed_total = 0
    for candidate in value.candidates:
        if candidate.item_id not in completed:
            continue
        counter.object(_COMPLETION_LAYOUT)
        _charge_fixed_id(counter, candidate.item_id, f"{context}.completed_bytes.item_id")
        require_signed_64(completed[candidate.item_id], f"{context}.completed_bytes.bytes_read")
        completed_total = checked_add_signed_64(
            completed_total,
            completed[candidate.item_id],
            f"{context}.completed_bytes total",
        )
        counter.integer(completed[candidate.item_id], f"{context}.completed_bytes.bytes_read")
    if set(completed) - candidate_ids:
        raise ValueError(f"{context}.completed_bytes contain an unknown id")
    require_signed_64(value.processed_bytes, f"{context}.processed_bytes")
    if value.processed_bytes < completed_total:
        raise ValueError(f"{context}.processed_bytes trails completed bytes")
    counter.integer(value.processed_bytes, f"{context}.processed_bytes")


def _charge_phase_result(
    counter: JsonEnvelopeCounter,
    value: object,
    context: str,
) -> None:
    if type(value) is not PhaseResult:
        raise TypeError(f"{context} has the wrong type")
    counter.object(_PHASE_RESULT_LAYOUT)
    _charge_fixed_text(counter, value.phase, ExecuteContinuation.phase, f"{context}.phase")
    _charge_enum(counter, value.status, PhaseStatus, f"{context}.status")
    require_safe_int(value.items_done, f"{context}.items_done")
    require_signed_64(value.bytes_done, f"{context}.bytes_done")
    counter.integer(value.items_done, f"{context}.items_done")
    if value.items_total is None:
        counter.null()
    else:
        require_safe_int(value.items_total, f"{context}.items_total")
        counter.integer(value.items_total, f"{context}.items_total")
    counter.integer(value.bytes_done, f"{context}.bytes_done")
    if value.bytes_total is None:
        counter.null()
    else:
        require_signed_64(value.bytes_total, f"{context}.bytes_total")
        counter.integer(value.bytes_total, f"{context}.bytes_total")
    counter.optional_text(value.error, f"{context}.error", maximum_utf8_bytes=MAX_DIAGNOSTIC_UTF8_BYTES)


def _charge_execution_request(request: object) -> JsonEnvelopeCounter:
    if type(request) is not ExecutionRequest:
        raise TypeError("execution payload requires ExecutionRequest")
    continuation = request.continuation
    if type(continuation) not in (ExecuteContinuation, VerifyContinuation):
        raise TypeError("execution payload requires an exact continuation")
    counter = JsonEnvelopeCounter()
    counter.object(_EXECUTE_LAYOUT if type(continuation) is ExecuteContinuation else _VERIFY_LAYOUT)
    counter.integer(_EXECUTION_SCHEMA_VERSION, "execution schema version")
    _charge_fixed_text(counter, "execute", "execute", "execution kind")
    expected_phase = (
        ExecuteContinuation.phase
        if type(continuation) is ExecuteContinuation
        else VerifyContinuation.phase
    )
    _charge_fixed_text(
        counter,
        continuation.phase,
        expected_phase,
        "execution phase",
    )
    _charge_execution_set(counter, continuation.execution_set, "execution_set")
    _charge_datetime(counter, request.started_at, "execution started_at", allow_none=True)
    if type(continuation) is ExecuteContinuation:
        counter.boolean(continuation.verify_after_execute, "verify_after_execute")
        counter.require_within(_EXECUTE_MAX_OCCURRENCE_CHARGE, "execute continuation")
        return counter
    _charge_post_copy_selection(counter, continuation.candidates, "verify continuation.candidates")
    _charge_enum(counter, continuation.filesystem_status, SessionState, "verify filesystem_status")
    _charge_enum(counter, continuation.recording, RecordingStatus, "verify recording")
    _charge_phase_result(counter, continuation.execute_phase, "verify execute_phase")
    if type(continuation.missing_evidence_ids) is not tuple or len(continuation.missing_evidence_ids) > MAX_PLAN_REVIEW_ROWS:
        raise ValueError("verify missing evidence ids exceed the plan row limit")
    counter.array(len(continuation.missing_evidence_ids))
    for item_id in continuation.missing_evidence_ids:
        _charge_fixed_id(counter, item_id, "verify missing_evidence_ids[]")
    counter.require_within(_VERIFY_MAX_OCCURRENCE_CHARGE, "verify continuation")
    return counter


def _readmit_execution_set(value: ExecutionSet) -> None:
    """Re-run mutable continuation invariants after bounded typed walking."""

    ExecutionSet(
        plan=value.plan,
        selection=value.selection,
        run_id=value.run_id,
        status=value.status,
        commitment=value.commitment,
        published_evidence=value.published_evidence,
        recording_reasons=value.recording_reasons,
        recording_issues=value.recording_issues,
        omitted_detail_count=value.omitted_detail_count,
        user_deselected=value.user_deselected,
        bytes_done_high_water=value.bytes_done_high_water,
    )


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", errors="strict")


def _volume(value: VolumeId | None) -> object:
    return volume_id_projection(value)


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
    return volume_evidence_projection(value)


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
    return capability_profile_projection(value)


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
            "file_index": file_index_128_to_text(identity.file_index),
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
            file_index_128_from_text(
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
    if type(value) is not Plan:
        raise TypeError("execution payload requires Plan")
    source_root = root_projection(value.source_root)
    target_root = root_projection(value.target_root)
    assignment = assignment_projection(value.assignment)
    preservation = preservation_policy_projection(value.preservation)
    filters = filter_set_projection(value.filter_snapshot)["patterns"]
    if type(value.required_volumes) is not frozenset:
        raise TypeError("execution plan required volumes must be a frozenset")
    if len(value.required_volumes) > PLAN_REQUIRED_VOLUME_LIMIT:
        raise ValueError("execution plan required volumes exceed the endpoint limit")
    required_volumes: list[dict[str, object]] = []
    for item in value.required_volumes:
        projected = _volume(item)
        if type(projected) is not dict:
            raise TypeError("execution plan required volumes cannot contain null")
        required_volumes.append(projected)
    required_volumes.sort(
        key=lambda item: (item["serial"], item["fs_type"])
    )
    return {
        "source_root": source_root,
        "target_root": target_root,
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
        "assignment": assignment,
        "preservation": preservation,
        "filters": filters,
        "deletion_policy": value.deletion_policy.value,
        "trash_on_update": value.trash_on_update,
        "policy_fingerprint": value.policy_fingerprint,
        "required_volumes": required_volumes,
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
    raw_assignment_values = _list(assignment_item["items"])
    if len(raw_assignment_values) > ASSIGNMENT_ITEM_LIMIT:
        raise ValueError("plan assignment exceeds the plan row limit")
    raw_operations = _list(item["operations"])
    if len(raw_operations) > MAX_PLAN_REVIEW_ROWS:
        raise ValueError("plan operations exceed the plan row limit")
    assignment_values: list[DestinationAssignment] = []
    for index, raw in enumerate(raw_assignment_values):
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

    raw_required_volumes = _list(item["required_volumes"])
    if len(raw_required_volumes) > PLAN_REQUIRED_VOLUME_LIMIT:
        raise ValueError("plan.required_volumes exceeds the endpoint limit")
    required_volumes: set[VolumeId] = set()
    for index, raw in enumerate(raw_required_volumes):
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
            for index, raw in enumerate(raw_operations)
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
        filter_snapshot=_decode_filter_set(item["filters"], "plan.filters"),
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
    raw_candidates = _list(item["candidates"])
    if len(raw_candidates) > MAX_PLAN_REVIEW_ROWS:
        raise ValueError(f"{context}.candidates exceed the plan row limit")
    raw_completed = _list(item["completed_bytes"])
    if len(raw_completed) > len(raw_candidates):
        raise ValueError(f"{context}.completed_bytes exceed the candidate limit")
    candidates = tuple(
        _decode_post_copy_candidate(
            raw, f"{context}.candidates[{index}]"
        )
        for index, raw in enumerate(raw_candidates)
    )
    completed: dict[str, int] = {}
    for index, raw in enumerate(raw_completed):
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
        "user_deselected": sorted(
            str(item) for item in value.user_deselected
        ),
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
        "recording_reasons": {
            str(key): reason.value
            for key, reason in sorted(
                value.recording_reasons.items(),
                key=lambda pair: str(pair[0]),
            )
        },
        "recording_issues": [
            {"reason": issue.reason.value, "detail": issue.detail}
            for issue in value.recording_issues
        ],
        "omitted_detail_count": value.omitted_detail_count,
        "bytes_done_high_water": value.bytes_done_high_water,
    }


def _decode_execution_set(value: object) -> ExecutionSet:
    item = _mapping(value)
    _expect_keys(
        item,
        {
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
        },
        "execution_set",
    )
    raw_status = _mapping(item["status"])
    raw_evidence = _mapping(item["published_evidence"])
    raw_recording_reasons = _mapping(item["recording_reasons"])
    raw_selection = _list(item["selection"])
    raw_user_deselected = _list(item["user_deselected"])
    raw_recording_issues = _list(item["recording_issues"])
    for population_context, collection, limit in (
        ("execution_set.selection", raw_selection, MAX_PLAN_REVIEW_ROWS),
        ("execution_set.user_deselected", raw_user_deselected, MAX_PLAN_REVIEW_ROWS),
        ("execution_set.status", raw_status, MAX_PLAN_REVIEW_ROWS),
        ("execution_set.published_evidence", raw_evidence, MAX_PLAN_REVIEW_ROWS),
        ("execution_set.recording_reasons", raw_recording_reasons, MAX_PLAN_REVIEW_ROWS),
        ("execution_set.recording_issues", raw_recording_issues, _TASK_ISSUE_LIMIT),
    ):
        if len(collection) > limit:
            raise ValueError(
                f"{population_context} exceeds its source population limit"
            )
    execution_set = ExecutionSet(
        plan=_decode_plan(item["plan"]),
        selection=frozenset(
            OpId(_string(raw, "execution_set.selection[]"))
            for raw in raw_selection
        ),
        user_deselected=frozenset(
            OpId(_string(raw, "execution_set.user_deselected[]"))
            for raw in raw_user_deselected
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
        recording_reasons={
            OpId(key): ItemRecordingReason(
                _string(
                    reason,
                    f"execution_set.recording_reasons.{key}",
                )
            )
            for key, reason in raw_recording_reasons.items()
        },
        recording_issues=tuple(
            _decode_task_recording_issue(
                issue,
                f"execution_set.recording_issues[{index}]",
            )
            for index, issue in enumerate(raw_recording_issues)
        ),
        omitted_detail_count=require_safe_int(
            _integer(
                item["omitted_detail_count"],
                "execution_set.omitted_detail_count",
            ),
            "execution_set.omitted_detail_count",
        ),
        bytes_done_high_water=_integer(
            item["bytes_done_high_water"],
            "execution_set.bytes_done_high_water",
        ),
    )
    encoded_recording = RecordingStatus(
        _string(item["recording"], "execution_set.recording")
    )
    if encoded_recording is not execution_set.recording:
        raise ValueError(
            "execution aggregate recording contradicts its item/task attribution"
        )
    return execution_set


def _decode_task_recording_issue(
    value: object,
    context: str,
) -> TaskRecordingIssue:
    item = _mapping(value)
    _expect_keys(item, {"reason", "detail"}, context)
    return TaskRecordingIssue(
        reason=TaskRecordingIssueReason(
            _string(item["reason"], f"{context}.reason")
        ),
        detail=_optional_string(item["detail"], f"{context}.detail"),
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
    admission = _charge_plan_request(request)
    policy = request.options.destination_policy
    if not isinstance(policy, IdentityDestinationPolicy):
        raise ValueError(
            "workflow payloads support only the identity destination policy"
        )
    value = {
        "schema_version": _PLAN_SCHEMA_VERSION,
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
    return encode_canonical_json(
        value,
        expected_bytes=admission.canonical_bytes,
        byte_ceiling=PLAN_REQUEST_PAYLOAD_BYTE_LIMIT,
        encoder=_json_bytes,
        context="plan payload",
    )


def decode_plan_request(payload: bytes) -> PlanRequest:
    item = _payload(
        payload,
        "plan",
        _PLAN_SCHEMA_VERSION,
        byte_ceiling=PLAN_REQUEST_PAYLOAD_BYTE_LIMIT,
    )
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
            filters=_decode_filter_set(
                options["filters"],
                "plan options.filters",
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
    admission = _charge_execution_request(request)
    continuation = request.continuation
    _readmit_execution_set(continuation.execution_set)
    if isinstance(continuation, VerifyContinuation):
        continuation = _exact_verify_continuation(continuation)
    value: dict[str, object] = {
        "schema_version": _EXECUTION_SCHEMA_VERSION,
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
    return encode_canonical_json(
        value,
        expected_bytes=admission.canonical_bytes,
        byte_ceiling=EXECUTION_REQUEST_PAYLOAD_BYTE_LIMIT,
        encoder=_json_bytes,
        context="execution payload",
    )


def decode_execution_request(payload: bytes) -> ExecutionRequest:
    item = _payload(
        payload,
        "execute",
        _EXECUTION_SCHEMA_VERSION,
        byte_ceiling=EXECUTION_REQUEST_PAYLOAD_BYTE_LIMIT,
    )
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
        raw_missing_evidence_ids = _list(item["missing_evidence_ids"])
        if len(raw_missing_evidence_ids) > MAX_PLAN_REVIEW_ROWS:
            raise ValueError(
                "verify continuation missing evidence ids exceed the plan row limit"
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
                for raw in raw_missing_evidence_ids
            ),
        )
    else:
        raise ValueError(f"unsupported execution continuation phase: {phase}")
    return ExecutionRequest(continuation, started_at)


def _payload(
    payload: bytes,
    expected_kind: str,
    expected_schema_version: int,
    *,
    byte_ceiling: int,
) -> Mapping[str, object]:
    payload = require_payload_bytes(
        payload,
        byte_ceiling=byte_ceiling,
        context="workflow payload",
    )
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("workflow payload is not valid UTF-8 JSON") from error
    require_json_unicode(value)
    item = _mapping(value)
    schema_version = item.get("schema_version")
    if (
        type(schema_version) is not int
        or schema_version != expected_schema_version
    ):
        raise ValueError("unsupported workflow payload schema")
    if item.get("kind") != expected_kind:
        raise ValueError("workflow payload kind does not match registration")
    return item


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON number: {value}")


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
    if type(value) is not dict or not all(
        type(key) is str for key in value
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
    if type(value) is not list:
        raise ValueError("workflow payload list is malformed")
    return value


def _string(value: object, context: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{context} must be a string")
    return value


def _decode_filter_set(value: object, context: str) -> FilterSet:
    raw_patterns = _list(value)
    if len(raw_patterns) > FILTER_PATTERN_LIMIT:
        raise ValueError(f"{context} exceeds the pattern limit")
    return FilterSet(
        tuple(
            _string(raw, f"{context}[]")
            for raw in raw_patterns
        )
    )


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
