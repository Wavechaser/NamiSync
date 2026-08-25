"""Strict validators for the exact core-event v5 contract."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from .evidence import Outcome, RecordingStatus
from .execution import (
    ExecutionReason,
    ItemRecordingReason,
    TaskRecordingIssueReason,
)
from .integrity import (
    IntegrityMode,
    IntegrityReason,
    IntegrityResult,
    ReadStrategy,
    RecordDisposition,
)
from .planning import BlockedReason, OperationKind
from .scalars import MAX_SAFE_INTEGER, MAX_SIGNED_64
from .session import Disposition, PhaseStatus, SessionState


EVENT_V5_SCHEMA_VERSION = 5
MAX_RELIABLE_EVENT_CANONICAL_BYTES = 1_048_576
MAX_DETAIL_LEAVES = 32
MAX_DETAIL_PATH_LEAVES = 8
MAX_DIAGNOSTIC_UTF8_BYTES = 1_024
MAX_PATH_UTF16_UNITS = 32_767

_HEX_ID = re.compile(r"[0-9a-f]{32}\Z")
_SCALAR_64 = re.compile(r"0|[1-9][0-9]*\Z")
_TERMINAL_STATES = frozenset(
    state.value
    for state in (
        SessionState.COMPLETED,
        SessionState.FAILED,
        SessionState.CANCELED,
        SessionState.REFUSED,
    )
)
_SESSION_STATES = frozenset(state.value for state in SessionState)
_PHASE_STATES = frozenset(state.value for state in PhaseStatus)
_OUTCOMES = frozenset(outcome.value for outcome in Outcome)
_OPERATION_KINDS = frozenset(kind.value for kind in OperationKind)
_RECORDING_STATES = frozenset(status.value for status in RecordingStatus)
_DISPOSITIONS = frozenset(value.value for value in Disposition)
_INTEGRITY_MODES = frozenset(value.value for value in IntegrityMode)
_INTEGRITY_RESULTS = frozenset(value.value for value in IntegrityResult)
_INTEGRITY_REASONS = frozenset(value.value for value in IntegrityReason)
_READ_STRATEGIES = frozenset(value.value for value in ReadStrategy)
_RECORD_DISPOSITIONS = frozenset(value.value for value in RecordDisposition)
_ITEM_RECORDING_REASONS = frozenset(
    value.value for value in ItemRecordingReason
)
_TASK_RECORDING_REASONS = frozenset(
    value.value for value in TaskRecordingIssueReason
)
_EXCLUSION_REASONS = frozenset(
    {
        "blocked-correspondence",
        "blocked-dependency",
        "incomplete-scan",
        "user-deselected",
    }
)
_OPERATION_REASONS = frozenset(
    {
        *(value.value for value in ExecutionReason),
        *(value.value for value in BlockedReason),
        *_EXCLUSION_REASONS,
    }
)
_RELIABLE_BODY_TYPES = frozenset(
    {
        "StateChanged",
        "PhaseChanged",
        "ItemOutcome",
        "IntegrityOutcome",
        "Gap",
        "Terminal",
    }
)

_ENVELOPE_KEYS = frozenset(
    {"session_id", "seq", "at", "schema_version", "body_type", "body"}
)
_SESSION_EVENT_VIEW_KEYS = frozenset(
    {
        "session_id",
        "sequence",
        "at",
        "schema_version",
        "body_type",
        "body",
    }
)
_PROGRESS_KEYS = frozenset(
    {
        "phase",
        "items_done",
        "items_total",
        "bytes_done",
        "bytes_total",
        "current_path",
        "item_id",
        "item_type",
        "item_attempt_id",
        "item_bytes_done",
        "item_bytes_total",
    }
)
_OPERATION_ITEM_KEYS = frozenset(
    {
        "item_type",
        "phase",
        "item_id",
        "kind",
        "path",
        "result",
        "reason",
        "detail",
        "recording",
        "recording_reason",
        "recording_detail",
        "detail_omitted_count",
    }
)
_INTEGRITY_ITEM_KEYS = frozenset(
    {
        "item_type",
        "phase",
        "item_id",
        "row_id",
        "location_id",
        "kind",
        "path",
        "result",
        "reason",
        "detail",
        "read_strategy",
        "recording",
        "record_disposition",
        "detail_omitted_count",
    }
)
_PHASE_RESULT_KEYS = frozenset(
    {
        "phase",
        "status",
        "items_done",
        "items_total",
        "bytes_done",
        "bytes_total",
        "error",
    }
)
_TERMINAL_SUMMARY_KEYS = frozenset(
    {
        "status",
        "recording",
        "audit",
        "disposition",
        "canceled",
        "phases",
        "bytes_done",
        "bytes_total",
        "error",
        "recording_degraded_items",
        "recording_issues",
        "omitted_detail_count",
        "review_fact_limit",
    }
)
_REVIEW_FACT_KEYS = frozenset(
    {
        "reason",
        "tree_kind",
        "population",
        "axis",
        "row_limit",
        "byte_limit",
    }
)

# Operation details are a closed flat vocabulary.  Values may be omitted, but
# an emitter cannot invent a new key or retain a nested collaborator object.
_DETAIL_TEXT_KEYS = frozenset(
    {
        "backup",
        "backup_metadata",
        "backup_state",
        "backup_state_error",
        "blocked_reason",
        "cleanup_error",
        "destination_state",
        "durable_state",
        "error_type",
        "message",
        "mutation_durable_state",
        "mutation_state",
        "mutation_state_error",
        "old_state_error",
        "publish_state",
        "retry_error",
        "retry_error_type",
        "source_state",
        "state_error",
        "state_error_type",
        "target_state",
        "target_state_error",
        "temp_state",
        "trash_state_error",
    }
)
_DETAIL_PATH_KEYS = frozenset(
    {
        "backup_path",
        "mutation_destination",
        "prior_path",
        "published_path",
        "trash_path",
    }
)
_DETAIL_BOOLEAN_KEYS = frozenset({"continued"})
_DETAIL_TEXT_ARRAY_KEYS = frozenset({"durability_warnings"})
_DETAIL_SIDE_ARRAY_KEYS = frozenset({"incomplete_sides"})
_DETAIL_ID_ARRAY_KEYS = frozenset({"excluded_dependencies"})
_DETAIL_KEYS = frozenset(
    {
        *_DETAIL_TEXT_KEYS,
        *_DETAIL_PATH_KEYS,
        *_DETAIL_BOOLEAN_KEYS,
        *_DETAIL_TEXT_ARRAY_KEYS,
        *_DETAIL_SIDE_ARRAY_KEYS,
        *_DETAIL_ID_ARRAY_KEYS,
    }
)


def validate_event_v5_envelope(value: object) -> None:
    """Validate one exact core-event v5 persistence envelope."""

    event = _exact_object(value, _ENVELOPE_KEYS, "event envelope")
    _hex_id(event["session_id"], "event session_id")
    sequence = _positive_safe_int(event["seq"], "event sequence")
    _utc_timestamp(event["at"], "event timestamp")
    if type(event["schema_version"]) is not int or event["schema_version"] != 5:
        raise ValueError("event schema_version must be exactly 5")
    body_type = _closed_text(
        event["body_type"],
        frozenset({*_RELIABLE_BODY_TYPES, "Progress"}),
        "event body_type",
    )
    _validate_body(body_type, event["body"], sequence)
    if body_type in _RELIABLE_BODY_TYPES:
        try:
            encoded = json.dumps(
                event,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, UnicodeEncodeError, ValueError) as error:
            raise ValueError("reliable event must be canonical JSON") from error
        if len(encoded) > MAX_RELIABLE_EVENT_CANONICAL_BYTES:
            raise ValueError("reliable event exceeds the canonical byte ceiling")


def validate_session_event_view_v5(
    value: object,
    *,
    expected_session_id: str | None = None,
) -> None:
    """Validate the exact v5 event shape consumed by service/browser clients."""

    event = _exact_object(value, _SESSION_EVENT_VIEW_KEYS, "session event view")
    session_id = _hex_id(event["session_id"], "session event session_id")
    if expected_session_id is not None and session_id != expected_session_id:
        raise ValueError("session event belongs to another session")
    sequence = _positive_safe_int(event["sequence"], "session event sequence")
    _utc_timestamp(event["at"], "session event timestamp")
    if type(event["schema_version"]) is not int or event["schema_version"] != 5:
        raise ValueError("session event schema_version must be exactly 5")
    body_type = _closed_text(
        event["body_type"],
        frozenset({*_RELIABLE_BODY_TYPES, "Progress"}),
        "session event body_type",
    )
    _validate_body(body_type, event["body"], sequence)


def _validate_body(body_type: str, value: object, sequence: int) -> None:
    if body_type == "StateChanged":
        body = _exact_object(value, frozenset({"state"}), "state body")
        _closed_text(body["state"], _SESSION_STATES, "state")
        return
    if body_type == "PhaseChanged":
        body = _exact_object(value, frozenset({"phase"}), "phase body")
        _bounded_text(body["phase"], "phase", nonempty=True)
        return
    if body_type == "Progress":
        _validate_progress(value)
        return
    if body_type == "ItemOutcome":
        _validate_operation_item(value)
        return
    if body_type == "IntegrityOutcome":
        _validate_integrity_item(value)
        return
    if body_type == "Gap":
        body = _exact_object(value, frozenset({"first_missed_seq"}), "gap body")
        first = _positive_safe_int(body["first_missed_seq"], "first_missed_seq")
        if first > sequence:
            raise ValueError("first_missed_seq cannot exceed event sequence")
        return
    if body_type == "Terminal":
        body = _exact_object(value, frozenset({"result"}), "terminal body")
        _validate_terminal_summary(body["result"])
        return
    raise ValueError(f"unsupported event body type: {body_type}")


def _validate_progress(value: object) -> None:
    body = _exact_object(value, _PROGRESS_KEYS, "progress body")
    _bounded_text(body["phase"], "progress phase", nonempty=True)
    items_done = _safe_int(body["items_done"], "progress items_done")
    items_total = _optional_safe_int(body["items_total"], "progress items_total")
    bytes_done = _scalar_64(body["bytes_done"], "progress bytes_done")
    bytes_total = _optional_scalar_64(body["bytes_total"], "progress bytes_total")
    if items_total is not None and items_done > items_total:
        raise ValueError("progress items_done cannot exceed items_total")
    if bytes_total is not None and bytes_done > bytes_total:
        raise ValueError("progress bytes_done cannot exceed bytes_total")
    if body["current_path"] is not None:
        _path(body["current_path"], "progress current_path")
    identity_absent = body["item_id"] is None and body["item_type"] is None
    identity_present = body["item_id"] is not None and body["item_type"] is not None
    if not (identity_absent or identity_present):
        raise ValueError("progress item identity must be present as a pair")
    if identity_present:
        _bounded_text(body["item_id"], "progress item_id", nonempty=True)
        _closed_text(
            body["item_type"],
            frozenset({"operation", "integrity"}),
            "progress item_type",
        )
        if items_total is not None and items_done >= items_total:
            raise ValueError("active item requires remaining selected work")
    attempt = body["item_attempt_id"]
    if attempt is not None:
        if not identity_present:
            raise ValueError("progress attempt requires item identity")
        _hex_id(attempt, "progress item_attempt_id")
    item_done_raw = body["item_bytes_done"]
    item_total_raw = body["item_bytes_total"]
    item_bytes_absent = item_done_raw is None and item_total_raw is None
    item_bytes_present = item_done_raw is not None and item_total_raw is not None
    if not (item_bytes_absent or item_bytes_present):
        raise ValueError("progress item byte counters must be present as a pair")
    if item_bytes_present:
        if attempt is None:
            raise ValueError("progress item byte counters require an attempt")
        item_done = _scalar_64(item_done_raw, "progress item_bytes_done")
        item_total = _scalar_64(item_total_raw, "progress item_bytes_total")
        if item_done > item_total:
            raise ValueError("item_bytes_done cannot exceed item_bytes_total")
        if item_done > bytes_done:
            raise ValueError("item_bytes_done cannot exceed bytes_done")
        if bytes_total is not None and item_total > bytes_total:
            raise ValueError("item_bytes_total cannot exceed bytes_total")


def _validate_operation_item(value: object) -> None:
    item = _exact_object(value, _OPERATION_ITEM_KEYS, "operation item")
    if item["item_type"] != "operation" or item["phase"] != "execute":
        raise ValueError("operation item tags are invalid")
    _hex_id(item["item_id"], "operation item_id")
    _closed_text(item["kind"], _OPERATION_KINDS, "operation kind")
    _path(item["path"], "operation path")
    _closed_text(item["result"], _OUTCOMES, "operation result")
    if item["reason"] is not None:
        _closed_text(item["reason"], _OPERATION_REASONS, "operation reason")
    _validate_detail_projection(item["detail"])
    _validate_recording_fields(
        item["recording"],
        item["recording_reason"],
        item["recording_detail"],
    )
    _safe_int(item["detail_omitted_count"], "operation detail_omitted_count")


def _validate_integrity_item(value: object) -> None:
    item = _exact_object(value, _INTEGRITY_ITEM_KEYS, "integrity item")
    if item["item_type"] != "integrity" or item["kind"] != "integrity":
        raise ValueError("integrity item tags are invalid")
    _closed_text(item["phase"], _INTEGRITY_MODES, "integrity phase")
    _bounded_text(item["item_id"], "integrity item_id", nonempty=True)
    row_absent = item["row_id"] is None and item["location_id"] is None
    row_present = item["row_id"] is not None and item["location_id"] is not None
    if not (row_absent or row_present):
        raise ValueError("integrity row identity must be present as a pair")
    if row_present:
        _bounded_text(item["row_id"], "integrity row_id", nonempty=True)
        _bounded_text(item["location_id"], "integrity location_id", nonempty=True)
    _path(item["path"], "integrity path")
    _closed_text(item["result"], _INTEGRITY_RESULTS, "integrity result")
    if item["reason"] is not None:
        _closed_text(item["reason"], _INTEGRITY_REASONS, "integrity reason")
    if item["detail"] is not None:
        _bounded_text(item["detail"], "integrity detail")
    if item["read_strategy"] is not None:
        _closed_text(
            item["read_strategy"], _READ_STRATEGIES, "integrity read_strategy"
        )
    _closed_text(item["recording"], _RECORDING_STATES, "integrity recording")
    if item["record_disposition"] is not None:
        _closed_text(
            item["record_disposition"],
            _RECORD_DISPOSITIONS,
            "integrity record_disposition",
        )
    _safe_int(item["detail_omitted_count"], "integrity detail_omitted_count")


def _validate_terminal_summary(value: object) -> None:
    result = _exact_object(value, _TERMINAL_SUMMARY_KEYS, "terminal summary")
    status = _closed_text(result["status"], _TERMINAL_STATES, "terminal status")
    recording = _closed_text(
        result["recording"], _RECORDING_STATES, "terminal recording"
    )
    _closed_text(result["audit"], _RECORDING_STATES, "terminal audit")
    disposition = _closed_text(
        result["disposition"], _DISPOSITIONS, "terminal disposition"
    )
    canceled = _boolean(result["canceled"], "terminal canceled")
    phases = _list(result["phases"], "terminal phases", maximum=3)
    phase_names: list[str] = []
    for index, phase in enumerate(phases):
        phase_names.append(_validate_phase_result(phase, index))
    if len(phase_names) != len(set(phase_names)):
        raise ValueError("terminal phase names must be unique")
    bytes_done = _scalar_64(result["bytes_done"], "terminal bytes_done")
    bytes_total = _scalar_64(result["bytes_total"], "terminal bytes_total")
    if bytes_done > bytes_total:
        raise ValueError("terminal bytes_done cannot exceed bytes_total")
    if result["error"] is not None:
        error = _exact_object(
            result["error"], frozenset({"type_name", "message"}), "terminal error"
        )
        _bounded_text(error["type_name"], "terminal error type", nonempty=True)
        _bounded_text(error["message"], "terminal error message")
    degraded_items = _safe_int(
        result["recording_degraded_items"],
        "terminal recording_degraded_items",
    )
    issues = _list(result["recording_issues"], "terminal recording_issues", maximum=5)
    issue_reasons: list[str] = []
    for issue in issues:
        item = _exact_object(
            issue, frozenset({"reason", "detail"}), "terminal recording issue"
        )
        issue_reasons.append(
            _closed_text(
                item["reason"],
                _TASK_RECORDING_REASONS,
                "terminal recording issue reason",
            )
        )
        if item["detail"] is not None:
            _bounded_text(item["detail"], "terminal recording issue detail")
    if len(issue_reasons) != len(set(issue_reasons)):
        raise ValueError("terminal recording issue reasons must be unique")
    expected_recording = (
        RecordingStatus.DEGRADED.value
        if degraded_items > 0 or issues
        else RecordingStatus.OK.value
    )
    if recording != expected_recording:
        raise ValueError("terminal recording aggregate contradicts its witnesses")
    omitted = _safe_int(
        result["omitted_detail_count"], "terminal omitted_detail_count"
    )
    review = result["review_fact_limit"]
    if review is not None:
        _validate_review_fact(review)
        if not (
            status == SessionState.REFUSED.value
            and disposition == Disposition.UNRUN.value
            and not canceled
            and bytes_done == 0
            and bytes_total == 0
            and not phases
            and degraded_items == 0
            and not issues
            and omitted == 0
            and result["error"] is None
        ):
            raise ValueError("review-limit terminal summary has contradictory facts")
    if status == SessionState.CANCELED.value and not canceled:
        raise ValueError("canceled terminal status requires canceled=true")
    if status == SessionState.REFUSED.value and (
        canceled or disposition != Disposition.UNRUN.value
    ):
        raise ValueError("refused terminal summary must be uncanceled and unrun")


def _validate_phase_result(value: object, index: int) -> str:
    phase = _exact_object(value, _PHASE_RESULT_KEYS, f"terminal phase {index}")
    name = _bounded_text(phase["phase"], "terminal phase name", nonempty=True)
    _closed_text(phase["status"], _PHASE_STATES, "terminal phase status")
    items_done = _safe_int(phase["items_done"], "terminal phase items_done")
    items_total = _optional_safe_int(
        phase["items_total"], "terminal phase items_total"
    )
    bytes_done = _scalar_64(phase["bytes_done"], "terminal phase bytes_done")
    bytes_total = _optional_scalar_64(
        phase["bytes_total"], "terminal phase bytes_total"
    )
    if items_total is not None and items_done > items_total:
        raise ValueError("terminal phase items_done cannot exceed items_total")
    if bytes_total is not None and bytes_done > bytes_total:
        raise ValueError("terminal phase bytes_done cannot exceed bytes_total")
    if phase["error"] is not None:
        _bounded_text(phase["error"], "terminal phase error")
    return name


def _validate_review_fact(value: object) -> None:
    fact = _exact_object(value, _REVIEW_FACT_KEYS, "review fact limit")
    if fact["reason"] != "review_fact_limit_exceeded":
        raise ValueError("review fact reason is invalid")
    tree_kind = _closed_text(
        fact["tree_kind"], frozenset({"plan", "inventory"}), "review tree_kind"
    )
    population = _closed_text(
        fact["population"],
        frozenset({"domain", "informational"}),
        "review population",
    )
    axis = _closed_text(
        fact["axis"],
        frozenset({"rows", "retained-bytes", "logical-bytes"}),
        "review axis",
    )
    row_limit = _optional_safe_int(fact["row_limit"], "review row_limit")
    byte_limit = _optional_scalar_64(fact["byte_limit"], "review byte_limit")
    if axis == "rows":
        if row_limit != 120_000 or byte_limit is not None:
            raise ValueError("row review fact has invalid limits")
        return
    if row_limit is not None or byte_limit is None:
        raise ValueError("byte review fact has invalid nullability")
    if axis == "logical-bytes":
        if (
            tree_kind != "plan"
            or population != "domain"
            or byte_limit != MAX_SIGNED_64
        ):
            raise ValueError("logical-byte review fact is invalid")
        return
    expected = (
        134_217_728
        if tree_kind == "plan" and population == "domain"
        else 201_326_592
    )
    if byte_limit != expected:
        raise ValueError("retained-byte review fact has the wrong limit")


def _validate_recording_fields(
    status_value: object,
    reason_value: object,
    detail_value: object,
) -> None:
    status = _closed_text(
        status_value, _RECORDING_STATES, "operation recording"
    )
    if status == RecordingStatus.OK.value:
        if reason_value is not None or detail_value is not None:
            raise ValueError("recording ok requires null reason and detail")
        return
    _closed_text(
        reason_value, _ITEM_RECORDING_REASONS, "operation recording_reason"
    )
    if detail_value is not None:
        _bounded_text(detail_value, "operation recording_detail")


def _validate_detail_projection(value: object) -> None:
    detail = _exact_object(value, None, "operation detail")
    keys = frozenset(detail)
    if not keys.issubset(_DETAIL_KEYS):
        raise ValueError(
            f"operation detail contains undeclared keys: {sorted(keys - _DETAIL_KEYS)}"
        )
    leaves = 0
    path_leaves = 0
    for key, item in detail.items():
        try:
            encoded_key = key.encode("ascii")
        except (AttributeError, UnicodeEncodeError) as error:
            raise ValueError("operation detail keys must be ASCII text") from error
        if not encoded_key or len(encoded_key) > 64:
            raise ValueError("operation detail key exceeds its ASCII bound")
        if key in _DETAIL_TEXT_KEYS:
            _bounded_text(item, f"operation detail {key}")
            leaves += 1
        elif key in _DETAIL_PATH_KEYS:
            _path(item, f"operation detail {key}")
            leaves += 1
            path_leaves += 1
        elif key in _DETAIL_BOOLEAN_KEYS:
            _boolean(item, f"operation detail {key}")
            leaves += 1
        else:
            members = _list(item, f"operation detail {key}", maximum=32)
            leaves += len(members)
            if key in _DETAIL_SIDE_ARRAY_KEYS:
                for member in members:
                    _closed_text(
                        member,
                        frozenset({"source", "target"}),
                        f"operation detail {key}",
                    )
            elif key in _DETAIL_ID_ARRAY_KEYS:
                for member in members:
                    _hex_id(member, f"operation detail {key}")
            else:
                for member in members:
                    _bounded_text(member, f"operation detail {key}")
        if leaves > MAX_DETAIL_LEAVES:
            raise ValueError("operation detail exceeds its primitive-leaf bound")
        if path_leaves > MAX_DETAIL_PATH_LEAVES:
            raise ValueError("operation detail exceeds its path-leaf bound")


def _exact_object(
    value: object,
    expected: frozenset[str] | None,
    context: str,
) -> dict[str, object]:
    if type(value) is not dict:
        raise TypeError(f"{context} must be a plain object")
    if any(type(key) is not str for key in value):
        raise TypeError(f"{context} keys must be strings")
    if expected is not None and frozenset(value) != expected:
        missing = sorted(expected - frozenset(value))
        extra = sorted(frozenset(value) - expected)
        raise ValueError(
            f"{context} has an invalid exact shape; missing={missing}, extra={extra}"
        )
    return value


def _list(value: object, context: str, *, maximum: int) -> list[object]:
    if type(value) is not list:
        raise TypeError(f"{context} must be an array")
    if len(value) > maximum:
        raise ValueError(f"{context} exceeds its cardinality bound")
    return value


def _safe_int(value: object, context: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{context} must be a non-Boolean integer")
    if not 0 <= value <= MAX_SAFE_INTEGER:
        raise ValueError(f"{context} is outside the SafeInt domain")
    return value


def _positive_safe_int(value: object, context: str) -> int:
    result = _safe_int(value, context)
    if result == 0:
        raise ValueError(f"{context} must be positive")
    return result


def _optional_safe_int(value: object, context: str) -> int | None:
    return None if value is None else _safe_int(value, context)


def _scalar_64(value: object, context: str) -> int:
    if type(value) is not str or _SCALAR_64.fullmatch(value) is None:
        raise TypeError(f"{context} must be a canonical decimal string")
    parsed = int(value)
    if parsed > MAX_SIGNED_64:
        raise ValueError(f"{context} exceeds the signed-64 domain")
    return parsed


def _optional_scalar_64(value: object, context: str) -> int | None:
    return None if value is None else _scalar_64(value, context)


def _hex_id(value: object, context: str) -> str:
    if type(value) is not str or _HEX_ID.fullmatch(value) is None:
        raise ValueError(f"{context} must be 32 lowercase hexadecimal characters")
    return value


def _closed_text(value: object, allowed: frozenset[str], context: str) -> str:
    if type(value) is not str or value not in allowed:
        raise ValueError(f"{context} has an unsupported value")
    return value


def _bounded_text(
    value: object,
    context: str,
    *,
    nonempty: bool = False,
) -> str:
    if type(value) is not str:
        raise TypeError(f"{context} must be text")
    if nonempty and not value:
        raise ValueError(f"{context} must be nonempty")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{context} must be valid Unicode") from error
    if len(encoded) > MAX_DIAGNOSTIC_UTF8_BYTES:
        raise ValueError(f"{context} exceeds its UTF-8 byte bound")
    return value


def _path(value: object, context: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{context} must be text")
    if "\x00" in value:
        raise ValueError(f"{context} cannot contain NUL")
    try:
        units = len(value.encode("utf-16-le")) // 2
    except UnicodeEncodeError as error:
        raise ValueError(f"{context} must be valid Unicode") from error
    if units > MAX_PATH_UTF16_UNITS:
        raise ValueError(f"{context} exceeds the UTF-16 path bound")
    return value


def _utc_timestamp(value: object, context: str) -> datetime:
    if type(value) is not str:
        raise TypeError(f"{context} must be text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{context} must be ISO-8601") from error
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timezone.utc.utcoffset(parsed)
    ):
        raise ValueError(f"{context} must be UTC")
    return parsed


def _boolean(value: object, context: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{context} must be a boolean")
    return value
