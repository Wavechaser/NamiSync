from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from _event_v5_fixtures import (
    SESSION_ID,
    UTC_TIMESTAMP_CASES,
    bodies,
    cancellation_terminal_cases,
    envelope as event_envelope,
)
from _frontend_test_support import _node_executable
from namisync.core.events import envelope_from_dict
from namisync.core.review import ReviewFactLimitExceeded
from namisync.core.session import (
    Disposition,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    SessionState,
)
from namisync.interfaces.web import bridge as bridge_module
from namisync.interfaces.web.bridge import to_primitive_view
from namisync.workflows import (
    BASELINE_KIND, EXECUTION_KIND, INVENTORY_KIND, MANUAL_VERIFY_KIND,
    PLAN_KIND, REBASELINE_KIND, VERIFY_KIND,
)
from namisync.workflows.views import (
    SessionRecordView,
    operation_result_view,
    session_event_view,
)


BRIDGE_JS = Path(bridge_module.__file__).parent / "assets" / "bridge.js"
TASK_ID = "task-" + "1" * 32
REQUEST_ID = "2" * 32
PLAN_REQUEST_ID = "3" * 32


def _assert_node_cases(cases: list[dict[str, object]]) -> None:
    node = _node_executable()
    if node is None:
        pytest.fail("the required Node validator runtime is unavailable")
    script = r"""
import { readFileSync } from "node:fs";
globalThis.window = { addEventListener() {} };
const source = readFileSync(process.argv[1], "utf8") +
  "\nexport { validateOperationResultView, validateTaskSummary, validateTaskUpdate };";
const bridge = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64")
);
const corpus = JSON.parse(readFileSync(0, "utf8"));
const mismatches = [];
for (const item of corpus.cases) {
  const sessionId = item.session_id ?? corpus.session_id;
  let actual;
  if (item.kind === "event") {
    actual = bridge.validateTaskUpdate(
      { update_type: "event", event: item.value }, sessionId,
    );
  } else if (item.kind === "record") {
    actual = bridge.validateTaskUpdate(
      { update_type: "record", record: item.value }, sessionId,
    );
  } else if (item.kind === "task-summary") {
    actual = bridge.validateTaskSummary(item.value);
  } else {
    actual = bridge.validateOperationResultView(item.value);
  }
  if (actual !== item.expected) {
    mismatches.push(item.name + ": expected " + item.expected + ", got " + actual);
  }
}
if (mismatches.length) throw new Error(mismatches.join("\n"));
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


def test_required_node_accepts_each_canonical_python_event_projection() -> None:
    cases = [
        {
            "name": body_type,
            "kind": "event",
            "expected": True,
            "value": to_primitive_view(
                session_event_view(envelope_from_dict(event_envelope(body_type)))
            ),
        }
        for body_type in bodies()
    ]

    assert len(cases) == 7
    _assert_node_cases(cases)


def test_required_node_operation_result_keeps_cancellation_truth() -> None:
    cases = []
    for name, accepted, summary in cancellation_terminal_cases():
        result = (
            OperationResult(
                status=SessionState(summary["status"]),
                canceled=summary["canceled"],
                disposition=Disposition(summary["disposition"]),
                phases=tuple(
                    PhaseResult(
                        phase["phase"], PhaseStatus(phase["status"]), 0, 0, 0, 0
                    )
                    for phase in summary["phases"]
                ),
            )
            if accepted
            else OperationResult(SessionState.COMPLETED)
        )
        value = to_primitive_view(operation_result_view(result))
        if not accepted:
            value.update(
                filesystem=summary["status"],
                canceled=summary["canceled"],
                disposition=summary["disposition"],
                phases=summary["phases"],
            )
        cases.append({
            "name": name,
            "kind": "result",
            "expected": accepted,
            "value": value,
        })

    _assert_node_cases(cases)


def test_required_node_operation_result_keeps_review_fact_truth() -> None:
    result = OperationResult(
        SessionState.REFUSED,
        disposition=Disposition.UNRUN,
        review_fact_limit=ReviewFactLimitExceeded.plan_logical_bytes(),
    )
    value = to_primitive_view(operation_result_view(result))
    cases = [
        {"name": "valid", "kind": "result", "expected": True, "value": value},
    ]
    for mutation in (
        {"tree_kind": "inventory"},
        {"population": "informational"},
        {"row_limit": 120_000},
        {"byte_limit": "9223372036854775806"},
    ):
        invalid = deepcopy(value)
        invalid["review_refusal"].update(mutation)
        cases.append({
            "name": str(mutation),
            "kind": "result",
            "expected": False,
            "value": invalid,
        })

    _assert_node_cases(cases)


def test_required_node_session_record_keeps_timestamp_boundary() -> None:
    result = to_primitive_view(
        operation_result_view(OperationResult(SessionState.COMPLETED))
    )
    record = to_primitive_view(SessionRecordView(
        SESSION_ID,
        PLAN_KIND,
        "completed",
        False,
        "2026-08-25T00:00:00+00:00",
        None,
        "2026-08-25T00:00:00+00:00",
        operation_result_view(OperationResult(SessionState.COMPLETED)),
    ))
    assert record["result"] == result
    cases = []
    for name, timestamp, accepted in UTC_TIMESTAMP_CASES:
        value = deepcopy(record)
        value["created_at"] = timestamp
        cases.append({
            "name": name,
            "kind": "record",
            "expected": accepted,
            "value": value,
        })

    _assert_node_cases(cases)


def test_required_node_session_record_keeps_task_kind_pause_contract() -> None:
    record = to_primitive_view(SessionRecordView(
        SESSION_ID,
        PLAN_KIND,
        "completed",
        False,
        "2026-08-25T00:00:00+00:00",
        None,
        "2026-08-25T00:00:00+00:00",
        operation_result_view(OperationResult(SessionState.COMPLETED)),
    ))
    cases = []
    for kind, supports_pause in (
        (PLAN_KIND, False),
        (INVENTORY_KIND, False),
        (EXECUTION_KIND, True),
        (BASELINE_KIND, True),
        (VERIFY_KIND, True),
        (REBASELINE_KIND, True),
        (MANUAL_VERIFY_KIND, True),
    ):
        value = deepcopy(record)
        value.update(kind=kind, supports_pause=supports_pause)
        cases.append({
            "name": f"{kind}-canonical-capability",
            "kind": "record",
            "expected": True,
            "value": value,
        })
        wrong = deepcopy(value)
        wrong["supports_pause"] = not supports_pause
        cases.append({
            "name": f"{kind}-wrong-capability",
            "kind": "record",
            "expected": False,
            "value": wrong,
        })
    unknown = deepcopy(record)
    unknown["kind"] = "sync-execute"
    cases.append({
        "name": "unknown-task-kind",
        "kind": "record",
        "expected": False,
        "value": unknown,
    })
    for invalid in ([VERIFY_KIND], 1):
        coercive = deepcopy(record)
        coercive["kind"] = invalid
        cases.append({
            "name": f"coercive-task-kind-{type(invalid).__name__}",
            "kind": "record",
            "expected": False,
            "value": coercive,
        })

    _assert_node_cases(cases)


def test_required_node_task_summary_keeps_complete_kind_catalogs() -> None:
    summary = {
        "task_id": TASK_ID,
        "session_id": SESSION_ID,
        "session_state": "active",
        "session_released": False,
        "task_kind": PLAN_KIND,
        "request_id": REQUEST_ID,
        "plan_request_id": PLAN_REQUEST_ID,
        "session_kind": PLAN_KIND,
    }
    cases = []
    for session_kind in (
        PLAN_KIND,
        INVENTORY_KIND,
        EXECUTION_KIND,
        BASELINE_KIND,
        VERIFY_KIND,
        REBASELINE_KIND,
        MANUAL_VERIFY_KIND,
    ):
        value = deepcopy(summary)
        value["session_kind"] = session_kind
        cases.append({
            "name": f"{session_kind}-summary-session-kind",
            "kind": "task-summary",
            "expected": True,
            "value": value,
        })
    inventory = deepcopy(summary)
    inventory.update(
        task_kind=INVENTORY_KIND,
        plan_request_id=None,
        session_kind=INVENTORY_KIND,
    )
    cases.append({
        "name": "inventory-task-kind",
        "kind": "task-summary",
        "expected": True,
        "value": inventory,
    })
    cases.append({
        "name": "blank-task-null-kinds",
        "kind": "task-summary",
        "expected": True,
        "value": {
            "task_id": TASK_ID,
            "session_id": None,
            "session_state": None,
            "session_released": False,
            "task_kind": None,
            "request_id": None,
            "plan_request_id": None,
            "session_kind": None,
        },
    })
    for field, invalid in (
        ("task_kind", "invented"),
        ("session_kind", "invented"),
        ("session_kind", [VERIFY_KIND]),
        ("session_kind", 1),
    ):
        unknown = deepcopy(summary)
        unknown[field] = invalid
        cases.append({
            "name": f"invalid-{field}-{type(invalid).__name__}",
            "kind": "task-summary",
            "expected": False,
            "value": unknown,
        })

    _assert_node_cases(cases)
