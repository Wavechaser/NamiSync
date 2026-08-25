from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from _event_v5_fixtures import (
    SESSION_ID,
    bodies,
    operation_item_body,
    review_limit_terminal_summary,
    session_event_view,
    terminal_summary,
)
from _frontend_test_support import _node_executable
from namisync.interfaces.web import bridge as bridge_module


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
    for reason in (
        "record-write-failed",
        "unrecorded-mutation",
        "recording-prerequisite-failed",
    ):
        item = operation_item_body()
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
