from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
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
    bodies,
    cancellation_terminal_cases,
    operation_item_body,
    review_limit_terminal_summary,
    session_event_view,
    terminal_summary,
)
from _frontend_test_support import _node_executable
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import Envelope, ItemOutcome, Terminal, TerminalSummary
from namisync.core.execution import ItemRecordingReason
from namisync.core.session import (
    Disposition,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    SessionId,
    SessionState,
)
from namisync.interfaces.web import bridge as bridge_module
from namisync.workflows.views import (
    operation_result_view,
    session_event_view as project_session_event,
)


BRIDGE_JS = Path(bridge_module.__file__).parent / "assets" / "bridge.js"


def test_second_protocol_stop_routes_the_live_browser_through_exact_v5() -> None:
    source = BRIDGE_JS.read_text(encoding="utf-8")
    live = source.split(
        "function validateLiveSessionEvent(event, sessionId) {", 1
    )[1].split("function validateSessionRecord(record, sessionId) {", 1)[0]

    assert "const LIVE_CORE_EVENT_SCHEMA_VERSION = 5;" in source
    assert "const DORMANT_CORE_EVENT_SCHEMA_VERSION = 5;" in source
    assert (
        "event.schema_version !== LIVE_CORE_EVENT_SCHEMA_VERSION" in live
    )
    assert "return validateDormantSessionEventV5(event, sessionId);" in live
    assert source.count("validateDormantSessionEventV5(") == 2
    assert (
        "export function validateDormantSessionEventV5(event, sessionId)"
        in source
    )


@pytest.mark.supplemental_node
def test_dormant_node_v5_consumer_accepts_and_rejects_the_exact_target() -> None:
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
  const actual = bridge.validateDormantSessionEventV5(
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
    return asdict(
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
// Expose the private result validator only in this in-memory test module.
const source = readFileSync(process.argv[1], "utf8") +
  "\\nexport { validateOperationResultView };";
const bridge = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64")
);
const corpus = JSON.parse(readFileSync(0, "utf8"));
const mismatches = [];
for (const item of corpus.cases) {
  const actual = item.kind === "event"
    ? bridge.validateDormantSessionEventV5(item.value, corpus.session_id)
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
        result_view = asdict(operation_result_view(result))
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
