from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import subprocess

import pytest

from _event_v5_fixtures import (
    AT,
    ITEM_ID,
    OPERATION_RECORDING_CASES,
    SESSION_ID,
    UTC_TIMESTAMP_CASES,
    UNICODE_TEXT_CASES,
    bodies,
    envelope,
    cancellation_terminal_cases,
    maximum_non_ascii_reliable_envelope,
    maximum_reliable_envelope,
    operation_item_body,
    review_limit_terminal_summary,
    session_event_view,
    terminal_summary,
)
from _frontend_test_support import _assert_exact_v5_event_routes, _node_executable
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import (
    Envelope, ItemOutcome, PhaseChanged, Terminal, TerminalSummary, envelope_from_dict,
)
from namisync.core.execution import ItemRecordingReason
from namisync.core.review import ReviewFactLimitExceeded
from namisync.core.session import (
    Disposition,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    SessionId,
    SessionState,
)
from namisync.interfaces.web import bridge as bridge_module
from namisync.interfaces.web.bridge import to_primitive_view
from namisync.workflows.views import (
    OperationResultView,
    SessionEventView,
    operation_result_view,
    session_event_view as project_session_event,
)
from tests.interfaces.web._public_view_witnesses import iter_public_view_witnesses


BRIDGE_JS = Path(bridge_module.__file__).parent / "assets" / "bridge.js"


def test_second_protocol_stop_routes_the_live_browser_through_exact_v5() -> None:
    source = BRIDGE_JS.read_text(encoding="utf-8")
    _assert_exact_v5_event_routes(source)
    assert source.count("validateSessionEventV5(") == 2
    assert (
        "export function validateSessionEventV5(event, sessionId)"
        in source
    )


@pytest.mark.parametrize("before,after", [
    (
        "return validateSessionEventV5(event, sessionId);",
        "return true; return validateSessionEventV5(event, sessionId);",
    ),
    (
        "return validateSessionEventV5(event, sessionId);",
        "return validateLegacySessionEvent(event, sessionId);",
    ),
    ("event.schema_version !== 4", "event.schema_version !== 5"),
    (
        "return validateLiveSessionEvent(update.event, sessionId);",
        "return validateLegacySessionEvent(update.event, sessionId);",
    ),
    (
        "function validateItemRecordingV5(",
        "function validateDormantItemRecordingV5(",
    ),
    (
        "const ITEM_RECORDING_REASONS_V5",
        "const DORMANT_ITEM_RECORDING_REASONS_V5",
    ),
])
def test_event_route_gate_rejects_in_memory_source_mutations(before, after) -> None:
    source = BRIDGE_JS.read_text(encoding="utf-8")
    _assert_exact_v5_event_routes(source)
    assert source.count(before) == 1
    with pytest.raises(AssertionError):
        _assert_exact_v5_event_routes(source.replace(before, after))


@pytest.mark.supplemental_node
def test_live_node_v5_consumer_accepts_and_rejects_the_exact_target() -> None:
    node = _node_executable()
    if node is None:
        pytest.fail("the required Node validator runtime is unavailable")

    accepted = [session_event_view(body_type) for body_type in bodies()]
    for tree_kind in ("plan", "inventory"):
        for population in ("domain", "informational"):
            rows = review_limit_terminal_summary()
            rows["review_fact_limit"] = {
                "reason": "review_fact_limit_exceeded",
                "tree_kind": tree_kind,
                "population": population,
                "axis": "rows",
                "row_limit": 120_000,
                "byte_limit": None,
            }
            accepted.append(
                session_event_view("Terminal", body={"result": rows})
            )
            retained = review_limit_terminal_summary()
            retained["review_fact_limit"] = {
                "reason": "review_fact_limit_exceeded",
                "tree_kind": tree_kind,
                "population": population,
                "axis": "retained-bytes",
                "row_limit": None,
                "byte_limit": (
                    "134217728"
                    if tree_kind == "plan" and population == "domain"
                    else "201326592"
                ),
            }
            accepted.append(
                session_event_view("Terminal", body={"result": retained})
            )
    for outcome, reason in (
        ("succeeded", "record-write-failed"),
        ("failed", "unrecorded-mutation"),
        ("failed", "recording-prerequisite-failed"),
    ):
        item = operation_item_body()
        item["result"] = outcome
        item["recording_reason"] = reason
        accepted.append(session_event_view("ItemOutcome", body=item))
    for reason in (
        "recording-open-failed",
        "final-flush-failed",
        "finish-failed",
        "recording-close-failed",
        "post-settlement-state-diverged",
    ):
        result = terminal_summary()
        result["recording_degraded_items"] = 0
        result["recording_issues"] = [{"reason": reason, "detail": None}]
        accepted.append(
            session_event_view("Terminal", body={"result": result})
        )
    wrong_version = deepcopy(accepted[0])
    wrong_version["schema_version"] = 4
    raw_number = session_event_view("Progress")
    raw_number["body"]["bytes_done"] = 7  # type: ignore[index]
    leading_zero = session_event_view("Progress")
    leading_zero["body"]["bytes_done"] = "07"  # type: ignore[index]
    invalid_scalars = []
    for scalar in (
        True,
        -1,
        "-1",
        "+1",
        "1.0",
        "1e3",
        "9223372036854775808",
    ):
        invalid = session_event_view("Progress")
        invalid["body"]["bytes_done"] = scalar  # type: ignore[index]
        invalid_scalars.append(invalid)
    arbitrary_detail = session_event_view("ItemOutcome")
    arbitrary_detail["body"]["detail"] = {  # type: ignore[index]
        "nested": {"object": True}
    }
    aggregate_drift = session_event_view("Terminal")
    aggregate_drift["body"]["result"]["recording"] = "ok"  # type: ignore[index]
    boolean_count = session_event_view("Progress")
    boolean_count["body"]["items_done"] = True  # type: ignore[index]
    corpus = {
        "session_id": SESSION_ID,
        "cases": [
            *(
                {"expected": True, "event": event}
                for event in accepted
            ),
            {"expected": False, "event": wrong_version},
            {"expected": False, "event": raw_number},
            {"expected": False, "event": leading_zero},
            *(
                {"expected": False, "event": event}
                for event in invalid_scalars
            ),
            {"expected": False, "event": arbitrary_detail},
            {"expected": False, "event": aggregate_drift},
            {"expected": False, "event": boolean_count},
        ],
    }
    script = """
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
globalThis.window = { addEventListener() {} };
const bridge = await import(pathToFileURL(process.argv[1]).href);
const corpus = JSON.parse(readFileSync(0, "utf8"));
for (const item of corpus.cases) {
  const actual = bridge.validateSessionEventV5(
    item.event,
    corpus.session_id,
  );
  if (actual !== item.expected) {
    throw new Error(`validator mismatch: expected ${item.expected}, got ${actual}`);
  }
}
"""
    completed = subprocess.run(
        [str(node), "--input-type=module", "--eval", script, str(BRIDGE_JS)],
        input=json.dumps(corpus),
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


def _project_public_event(body: object) -> dict[str, object]:
    return to_primitive_view(
        project_session_event(
            Envelope(SessionId(SESSION_ID), 3, datetime.fromisoformat(AT), 5, body)
        )
    )


def _assert_v5_node_cases(cases: list[dict[str, object]]) -> None:
    node = _node_executable()
    if node is None:
        pytest.fail("the required Node validator runtime is unavailable")
    script = """
import { readFileSync } from "node:fs";
globalThis.window = { addEventListener() {} };
// Expose private entry points only in this in-memory test module.
const source = readFileSync(process.argv[1], "utf8") +
  "\\nexport { validateOperationResultView, validateTaskUpdate, validateLegacySessionEvent };";
const bridge = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64")
);
const corpus = JSON.parse(readFileSync(0, "utf8"));
const mismatches = [];
for (const item of corpus.cases) {
  const sessionId = item.session_id ?? corpus.session_id;
  const actual = item.kind === "event"
    ? bridge.validateTaskUpdate({ update_type: "event", event: item.value }, sessionId)
    : item.kind === "legacy"
      ? bridge.validateLegacySessionEvent(item.value, sessionId)
      : bridge.validateOperationResultView(item.value);
  if (actual !== item.expected) {
    mismatches.push(item.name + ": expected " + item.expected + ", got " + actual);
  }
}
if (mismatches.length) throw new Error(mismatches.join("\\n"));
"""
    completed = subprocess.run(
        [str(node), "--input-type=module", "--eval", script, str(BRIDGE_JS)],
        input=json.dumps({"session_id": SESSION_ID, "cases": cases}),
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


def test_required_node_consumes_real_python_public_view_codec() -> None:
    cases = []
    for body_type in bodies():
        value = to_primitive_view(
            project_session_event(envelope_from_dict(envelope(body_type)))
        )
        assert value == session_event_view(body_type)
        cases.append({
            "name": body_type, "kind": "event", "expected": True, "value": value,
        })
    assert len(cases) == 7
    witnessed = set()
    for witness in iter_public_view_witnesses():
        if type(witness.value) not in {SessionEventView, OperationResultView}:
            continue
        value = to_primitive_view(witness.value)
        assert value == witness.expected
        kind = "event" if type(witness.value) is SessionEventView else "result"
        witnessed.add(kind)
        cases.append({
            "name": witness.label, "kind": kind, "expected": True,
            "value": value, "session_id": value.get("session_id", SESSION_ID),
        })
    assert witnessed == {"event", "result"}
    _assert_v5_node_cases(cases)


def test_required_node_private_legacy_seam_is_v4_only() -> None:
    numeric = session_event_view("Progress")
    numeric["body"].update(bytes_done="7", bytes_total="20")
    for field in ("bytes_done", "bytes_total", "item_bytes_done", "item_bytes_total"):
        if numeric["body"][field] is not None:
            numeric["body"][field] = int(numeric["body"][field])
    cases = []
    for version in (3, 4, 5, 6):
        value = deepcopy(numeric)
        value["schema_version"] = version
        cases.extend([
            {"name": f"private-v{version}-numeric", "kind": "legacy",
             "expected": version == 4, "value": value},
            {"name": f"live-v{version}-numeric", "kind": "event",
             "expected": False, "value": value},
        ])
    canonical = session_event_view("Progress")
    cases.extend([
        {"name": "live-v5-text", "kind": "event", "expected": True,
         "value": canonical},
        {"name": "private-v5-text", "kind": "legacy", "expected": False,
         "value": canonical},
    ])
    _assert_v5_node_cases(cases)


def test_required_node_operation_truth_matches_public_python_projections() -> None:
    cases = []
    for outcome, recording, reason, accepted in OPERATION_RECORDING_CASES:
        item = ItemOutcome(
            item_id=ITEM_ID,
            kind="copy",
            path="folder\\file.bin",
            outcome=Outcome(outcome) if accepted else Outcome.SUCCEEDED,
            recording=RecordingStatus(recording) if accepted else RecordingStatus.OK,
            recording_reason=(
                ItemRecordingReason(reason) if accepted and reason is not None else None
            ),
        )
        view = _project_public_event(item)
        if accepted:
            assert (
                view["body"]["result"],
                view["body"]["recording"],
                view["body"]["recording_reason"],
                view["body"]["recording_detail"],
            ) == (outcome, recording, reason, None)
        else:
            view["body"].update(
                result=outcome,
                recording=recording,
                recording_reason=reason,
                recording_detail=None,
            )
        cases.append(
            {
                "name": f"item:{outcome}/{recording}/{reason}",
                "kind": "event",
                "expected": accepted,
                "value": view,
            }
        )
    for name, accepted, summary in cancellation_terminal_cases():
        result = (
            OperationResult(
                status=SessionState(summary["status"]),
                canceled=summary["canceled"],
                disposition=Disposition(summary["disposition"]),
                phases=tuple(
                    PhaseResult(phase["phase"], PhaseStatus(phase["status"]), 0, 0, 0, 0)
                    for phase in summary["phases"]
                ),
            )
            if accepted
            else OperationResult(SessionState.COMPLETED)
        )
        event = _project_public_event(Terminal(TerminalSummary.from_result(result)))
        result_view = to_primitive_view(operation_result_view(result))
        if not accepted:
            event["body"]["result"].update(summary)
            result_view.update(
                filesystem=summary["status"],
                canceled=summary["canceled"],
                disposition=summary["disposition"],
                phases=summary["phases"],
            )
        cases.extend(
            (
                {"name": name + ":event", "kind": "event", "expected": accepted, "value": event},
                {"name": name + ":result", "kind": "result", "expected": accepted, "value": result_view},
            )
        )
    assert len(cases) == 94
    _assert_v5_node_cases(cases)

def test_required_node_uses_the_shared_timestamp_grammar_and_calendar() -> None:
    cases = []
    for name, timestamp, accepted in UTC_TIMESTAMP_CASES:
        view = _project_public_event(PhaseChanged("execute"))
        view["at"] = timestamp
        cases.append(
            {"name": name, "kind": "event", "expected": accepted, "value": view}
        )
    assert len(cases) == 50
    _assert_v5_node_cases(cases)


@pytest.mark.parametrize(
    "factory",
    (maximum_reliable_envelope, maximum_non_ascii_reliable_envelope),
    ids=("escaped-ascii", "mixed-unicode"),
)
def test_required_node_reliable_ceiling_uses_the_public_envelope_bytes(factory) -> None:
    raw = factory()
    assert len(json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) == 1_048_576
    view = to_primitive_view(project_session_event(envelope_from_dict(raw)))
    assert view["sequence"] == raw["seq"]
    assert view["body"] == raw["body"]
    oversized = deepcopy(view)
    oversized["body"]["path"] += "x"
    _assert_v5_node_cases(
        [
            {"name": "exact-max", "kind": "event", "expected": True, "value": view},
            {"name": "plus-one", "kind": "event", "expected": False, "value": oversized},
        ]
    )


def test_required_node_preserves_logical_byte_review_facts() -> None:
    result = OperationResult(
        SessionState.REFUSED,
        disposition=Disposition.UNRUN,
        review_fact_limit=ReviewFactLimitExceeded.plan_logical_bytes(),
    )
    event = _project_public_event(Terminal(TerminalSummary.from_result(result)))
    result_view = to_primitive_view(operation_result_view(result))
    cases = [
        {
            "name": "literal-logical-byte-fact",
            "kind": "event",
            "expected": True,
            "value": session_event_view(
                "Terminal", body={"result": review_limit_terminal_summary()}
            ),
        },
        {"name": "public-logical-byte-event", "kind": "event", "expected": True, "value": event},
        {"name": "public-logical-byte-result", "kind": "result", "expected": True, "value": result_view},
    ]
    for mutation in (
        {"tree_kind": "inventory"},
        {"population": "informational"},
        {"row_limit": 120_000},
        {"byte_limit": "9223372036854775806"},
    ):
        invalid_event = deepcopy(event)
        invalid_event["body"]["result"]["review_fact_limit"].update(mutation)
        invalid_result = deepcopy(result_view)
        invalid_result["review_refusal"].update(mutation)
        cases.extend(
            (
                {"name": f"event:{mutation}", "kind": "event", "expected": False, "value": invalid_event},
                {"name": f"result:{mutation}", "kind": "result", "expected": False, "value": invalid_result},
            )
        )
    assert len(cases) == 11
    _assert_v5_node_cases(cases)

def test_required_node_canonical_byte_inputs_require_real_unicode() -> None:
    cases = []
    for field in ("path", "detail-message", "recording_detail"):
        for name, value, accepted in UNICODE_TEXT_CASES:
            view = session_event_view("ItemOutcome")
            if field == "detail-message":
                view["body"]["detail"] = {"message": value}
            else:
                view["body"][field] = value
            cases.append(
                {"name": f"{field}:{name}", "kind": "event", "expected": accepted, "value": view}
            )
    assert len(cases) == 33
    _assert_v5_node_cases(cases)
