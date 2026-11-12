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


def cancellation_terminal_cases() -> tuple[tuple[str, bool, dict[str, object]], ...]:
    rows = (
        ("plain-completed", True, "completed", False, "ran", ()),
        ("plain-failed", True, "failed", False, "ran", ()),
        ("ran-cancel", True, "canceled", True, "ran", ()),
        ("unrun-cancel", True, "canceled", True, "unrun", ()),
        ("plain-refused", True, "refused", False, "unrun", ()),
        ("compound-completed", True, "completed", True, "ran", (("execute", "completed"), ("verify", "canceled"))),
        ("compound-failed", True, "failed", True, "ran", (("execute", "failed"), ("verify", "canceled"))),
        ("execute-canceled", True, "canceled", True, "ran", (("execute", "canceled"),)),
        ("execute-failed-canceled", True, "canceled", True, "ran", (("execute", "failed"),)),
        ("compound-reversed", True, "completed", True, "ran", (("verify", "canceled"), ("execute", "completed"))),
        ("compound-third-phase", True, "completed", True, "ran", (("preflight", "completed"), ("execute", "completed"), ("verify", "canceled"))),
        ("unrun-completed-cancel", False, "completed", True, "unrun", ()),
        ("canceled-completed-execute", False, "canceled", True, "ran", (("execute", "completed"),)),
        ("compound-missing-execute", False, "completed", True, "ran", (("verify", "canceled"),)),
        ("compound-wrong-execute", False, "completed", True, "ran", (("execute", "failed"), ("verify", "canceled"))),
        ("failed-wrong-execute", False, "failed", True, "ran", (("execute", "completed"), ("verify", "canceled"))),
        ("compound-missing-verify", False, "completed", True, "ran", (("execute", "completed"),)),
        ("compound-completed-verify", False, "completed", True, "ran", (("execute", "completed"), ("verify", "completed"))),
        ("compound-failed-verify", False, "failed", True, "ran", (("execute", "failed"), ("verify", "failed"))),
        ("compound-unrun", False, "failed", True, "unrun", (("execute", "failed"), ("verify", "canceled"))),
        ("canceled-without-flag", False, "canceled", False, "ran", ()),
        ("refused-canceled", False, "refused", True, "unrun", ()),
        ("refused-ran", False, "refused", False, "ran", ()),
    )
    cases = []
    for name, accepted, status, canceled, disposition, phases in rows:
        result = terminal_summary()
        result.update(
            status=status,
            canceled=canceled,
            disposition=disposition,
            phases=[
                {
                    "phase": phase,
                    "status": phase_status,
                    "items_done": 0,
                    "items_total": 0,
                    "bytes_done": "0",
                    "bytes_total": "0",
                    "error": None,
                }
                for phase, phase_status in phases
            ],
            bytes_done="0",
            bytes_total="0",
            recording="ok",
            recording_degraded_items=0,
            recording_issues=[],
            omitted_detail_count=0,
        )
        cases.append((name, accepted, result))
    return tuple(cases)

# One literal ingress grammar/calendar corpus shared by Python and Node.
UTC_TIMESTAMP_CASES = (
    ("minimum-year", "0001-01-01T00:00:00+00:00", True),
    ("maximum-year", "9999-12-31T23:59:59.999999+00:00", True),
    ("plain-seconds", "2026-08-25T00:00:00+00:00", True),
    ("zero-microseconds", "2026-08-25T00:00:00.000000+00:00", True),
    ("microseconds", "2026-08-25T12:34:56.123456+00:00", True),
    ("early-leap-year", "0004-02-29T00:00:00+00:00", True),
    ("century-leap-year", "2000-02-29T00:00:00+00:00", True),
    ("ordinary-leap-year", "2024-02-29T00:00:00+00:00", True),
    ("century-february-end", "1900-02-28T00:00:00+00:00", True),
    ("year-zero", "0000-01-01T00:00:00+00:00", False),
    ("long-year", "10000-01-01T00:00:00+00:00", False),
    ("signed-year", "+002026-08-25T00:00:00+00:00", False),
    ("century-not-leap", "1900-02-29T00:00:00+00:00", False),
    ("ordinary-not-leap", "2025-02-29T00:00:00+00:00", False),
    ("impossible-february", "2024-02-30T00:00:00+00:00", False),
    ("impossible-april", "2026-04-31T00:00:00+00:00", False),
    ("zero-month", "2026-00-25T00:00:00+00:00", False),
    ("month-overflow", "2026-13-25T00:00:00+00:00", False),
    ("zero-day", "2026-08-00T00:00:00+00:00", False),
    ("day-overflow", "2026-08-32T00:00:00+00:00", False),
    ("hour-overflow", "2026-08-25T24:00:00+00:00", False),
    ("minute-overflow", "2026-08-25T00:60:00+00:00", False),
    ("second-overflow", "2026-08-25T00:00:60+00:00", False),
    ("utc-z", "2026-08-25T00:00:00Z", False),
    ("other-offset", "2026-08-25T08:00:00+08:00", False),
    ("negative-zero-offset", "2026-08-25T00:00:00-00:00", False),
    ("offset-seconds", "2026-08-25T00:00:00+00:00:00", False),
    ("offset-without-colon", "2026-08-25T00:00:00+0000", False),
    ("no-offset", "2026-08-25T00:00:00", False),
    ("date-only", "2026-08-25", False),
    ("date-with-offset", "2026-08-25+00:00", False),
    ("basic-date", "20260825T00:00:00+00:00", False),
    ("week-date", "2026-W35-2T00:00:00+00:00", False),
    ("space-separator", "2026-08-25 00:00:00+00:00", False),
    ("lowercase-separator", "2026-08-25t00:00:00+00:00", False),
    ("missing-seconds", "2026-08-25T00:00+00:00", False),
    ("short-month", "2026-8-25T00:00:00+00:00", False),
    ("one-fraction", "2026-08-25T00:00:00.1+00:00", False),
    ("three-fraction", "2026-08-25T00:00:00.123+00:00", False),
    ("five-fraction", "2026-08-25T00:00:00.12345+00:00", False),
    ("seven-fraction", "2026-08-25T00:00:00.1234567+00:00", False),
    ("comma-fraction", "2026-08-25T00:00:00,123456+00:00", False),
    ("non-ascii-fraction", "2026-08-25T00:00:00.１２３４５６+00:00", False),
    ("non-ascii-year", "２０２６-08-25T00:00:00+00:00", False),
    ("trailing-newline", "2026-08-25T00:00:00+00:00\n", False),
    ("leading-space", " 2026-08-25T00:00:00+00:00", False),
    ("empty", "", False),
    ("number", 0, False),
    ("boolean", True, False),
    ("null", None, False),
)


def maximum_non_ascii_reliable_envelope() -> dict[str, object]:
    value = maximum_reliable_envelope()
    # Two escaped controls and this mixed Unicode text each occupy 12 UTF-8
    # JSON bytes, but have different character/UTF-16 lengths.
    value["body"]["path"] = value["body"]["path"].replace(
        "\x01\x01", "海é🙂abc", 1
    )
    return value

# JSON input must not let an unpaired UTF-16 code unit impersonate Unicode.
UNICODE_TEXT_CASES = (
    ("ascii", "a", True),
    ("bmp", "海é", True),
    ("non-bmp", "🙂", True),
    ("surrounded-pair", "a🙂b", True),
    ("lone-high", "\ud800", False),
    ("trailing-high", "a\ud800", False),
    ("high-before-ascii", "\ud800a", False),
    ("lone-low", "\udc00", False),
    ("reversed-pair", "\udc00\ud800", False),
    ("double-high", "\ud800\ud800", False),
    ("pair-then-high", "🙂\ud800", False),
)
