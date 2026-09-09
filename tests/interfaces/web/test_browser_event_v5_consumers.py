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
from namisync.workflows import PLAN_KIND
from namisync.workflows.views import (
    SessionRecordView,
    operation_result_view,
    session_event_view,
)


BRIDGE_JS = Path(bridge_module.__file__).parent / "assets" / "bridge.js"


def _assert_node_cases(cases: list[dict[str, object]]) -> None:
    node = _node_executable()
    if node is None:
        pytest.fail("the required Node validator runtime is unavailable")
    script = r"""
import { readFileSync } from "node:fs";
globalThis.window = { addEventListener() {} };
const source = readFileSync(process.argv[1], "utf8") +
  "\nexport { validateOperationResultView, validateTaskUpdate };";
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
