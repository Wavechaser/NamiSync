"""Exact dormant core-event v5 consumer fixtures."""

from __future__ import annotations

from copy import deepcopy
import json


SESSION_ID = "0123456789abcdef0123456789abcdef"
ITEM_ID = "fedcba9876543210fedcba9876543210"
ATTEMPT_ID = "00112233445566778899aabbccddeeff"
AT = "2026-08-25T00:00:00+00:00"


def progress_body() -> dict[str, object]:
    return {
        "phase": "execute",
        "items_done": 2,
        "items_total": 4,
        "bytes_done": "9223372036854775806",
        "bytes_total": "9223372036854775807",
        "current_path": "folder\\file.bin",
        "item_id": ITEM_ID,
        "item_type": "operation",
        "item_attempt_id": ATTEMPT_ID,
        "item_bytes_done": "7",
        "item_bytes_total": "8",
    }


def operation_item_body() -> dict[str, object]:
    return {
        "item_type": "operation",
        "phase": "execute",
        "item_id": ITEM_ID,
        "kind": "copy",
        "path": "folder\\file.bin",
        "result": "succeeded",
        "reason": None,
        "detail": {
            "published_path": "folder\\file.bin",
            "publish_state": "published",
        },
        "recording": "degraded",
        "recording_reason": "record-write-failed",
        "recording_detail": "RecordingError: durable row unavailable",
        "detail_omitted_count": 0,
    }


def integrity_item_body() -> dict[str, object]:
    return {
        "item_type": "integrity",
        "phase": "verify",
        "item_id": "7:42",
        "row_id": "42",
        "location_id": "7",
        "kind": "integrity",
        "path": "folder\\file.bin",
        "result": "verified",
        "reason": None,
        "detail": None,
        "read_strategy": "windows-unbuffered",
        "recording": "ok",
        "record_disposition": "applied",
        "detail_omitted_count": 0,
    }


def terminal_summary() -> dict[str, object]:
    return {
        "status": "completed",
        "recording": "degraded",
        "audit": "ok",
        "disposition": "ran",
        "canceled": False,
        "phases": [
            {
                "phase": "execute",
                "status": "completed",
                "items_done": 4,
                "items_total": 4,
                "bytes_done": "9223372036854775806",
                "bytes_total": "9223372036854775807",
                "error": None,
            }
        ],
        "bytes_done": "9223372036854775806",
        "bytes_total": "9223372036854775807",
        "error": None,
        "recording_degraded_items": 1,
        "recording_issues": [
            {"reason": "final-flush-failed", "detail": "flush failed"}
        ],
        "omitted_detail_count": 2,
        "review_fact_limit": None,
    }


def review_limit_terminal_summary() -> dict[str, object]:
    return {
        "status": "refused",
        "recording": "ok",
        "audit": "ok",
        "disposition": "unrun",
        "canceled": False,
        "phases": [],
        "bytes_done": "0",
        "bytes_total": "0",
        "error": None,
        "recording_degraded_items": 0,
        "recording_issues": [],
        "omitted_detail_count": 0,
        "review_fact_limit": {
            "reason": "review_fact_limit_exceeded",
            "tree_kind": "plan",
            "population": "domain",
            "axis": "logical-bytes",
            "row_limit": None,
            "byte_limit": "9223372036854775807",
        },
    }


def bodies() -> dict[str, dict[str, object]]:
    return {
        "StateChanged": {"state": "running"},
        "PhaseChanged": {"phase": "execute"},
        "Progress": progress_body(),
        "ItemOutcome": operation_item_body(),
        "IntegrityOutcome": integrity_item_body(),
        "Gap": {"first_missed_seq": 1},
        "Terminal": {"result": terminal_summary()},
    }


def envelope(
    body_type: str = "Progress",
    *,
    body: dict[str, object] | None = None,
) -> dict[str, object]:
    selected = bodies()[body_type] if body is None else body
    return {
        "session_id": SESSION_ID,
        "seq": 3,
        "at": AT,
        "schema_version": 5,
        "body_type": body_type,
        "body": deepcopy(selected),
    }


def session_event_view(
    body_type: str = "Progress",
    *,
    body: dict[str, object] | None = None,
) -> dict[str, object]:
    value = envelope(body_type, body=body)
    value["sequence"] = value.pop("seq")
    return value


def maximum_reliable_envelope() -> dict[str, object]:
    """Build one structurally valid envelope at the exact reliable byte wall."""

    item = operation_item_body()
    item["detail"] = {
        key: "\x01" * 32_767
        for key in (
            "backup_path",
            "mutation_destination",
            "prior_path",
            "published_path",
            "trash_path",
        )
    }
    item["path"] = ""
    value = envelope("ItemOutcome", body=item)
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    deficit = 1_048_576 - len(encoded)
    if deficit < 0:
        raise AssertionError("maximum reliable fixture base exceeds its wall")
    escaped, plain = divmod(deficit, 6)
    path = "\x01" * escaped + "x" * plain
    if len(path.encode("utf-16-le")) // 2 > 32_767:
        raise AssertionError("maximum reliable fixture exceeds the path wall")
    item["path"] = path
    value = envelope("ItemOutcome", body=item)
    if len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ) != 1_048_576:
        raise AssertionError("maximum reliable fixture is not exact")
    return value
