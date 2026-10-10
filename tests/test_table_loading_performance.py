"""Correctness and failure controls, never headed latency acceptance."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools.performance import table_loading as loading


ASSETS = Path(__file__).parents[1] / "namisync/interfaces/web/assets"


def _installed(tmp_path):
    root = tmp_path / "installed"
    assets = root / "namisync/interfaces/web/assets"
    assets.mkdir(parents=True)
    (root / loading.OWNERSHIP_NAME).write_text(json.dumps({"purpose": "GUI-C5 disposable installed measurement"}))
    for name in ("app.js", "bridge.js", "tree.js", "plan_review.js"):
        (assets / name).write_bytes((ASSETS / name).read_bytes())
    return root, assets


def test_table_loading_restores_after_child_failure(tmp_path):
    root, assets = _installed(tmp_path)
    originals = {path.name: path.read_bytes() for path in assets.iterdir()}
    evidence = tmp_path / "evidence"
    with pytest.raises(RuntimeError, match="child deadline"):
        with loading.instrumented_assets(root, evidence) as hashes:
            assert all(row["original"] != row["instrumented"] for row in hashes.values())
            raise RuntimeError("child deadline")
    assert {path.name: path.read_bytes() for path in assets.iterdir()} == originals
    assert json.loads((evidence / "manifest.json").read_bytes())["restored"] is True


def test_table_loading_anchor_drift_refuses_before_any_write(tmp_path):
    root, assets = _installed(tmp_path)
    (assets / "tree.js").write_text("changed tree source")
    originals = {path.name: path.read_bytes() for path in assets.iterdir()}
    with pytest.raises(ValueError, match="anchor drifted"):
        with loading.instrumented_assets(root, tmp_path / "evidence"):
            pytest.fail("drifted instrumentation was admitted")
    assert {path.name: path.read_bytes() for path in assets.iterdir()} == originals


def test_table_loading_refuses_unowned_installation(tmp_path):
    root, _ = _installed(tmp_path)
    (root / loading.OWNERSHIP_NAME).write_text('{"purpose":"retained C4 evidence"}')
    with pytest.raises(ValueError, match="task-owned C5"):
        with loading.instrumented_assets(root, tmp_path / "evidence"):
            pytest.fail("unowned installation was admitted")


def test_table_loading_instrumented_modules_parse(tmp_path):
    from _frontend_test_support import _node_executable, run_node_probe

    node = _node_executable()
    assert node is not None, "Node.js is required for the measurement method controls"
    for name in ("app.js", "bridge.js", "tree.js", "plan_review.js"):
        target = tmp_path / name.replace(".js", ".mjs")
        target.write_text(loading.transform_asset(name, (ASSETS / name).read_text(encoding="utf-8")), encoding="utf-8")
        result = run_node_probe((node, "--check", target), timeout=10)
        assert result.returncode == 0, result.stderr
    result = run_node_probe((node, "--check", loading.PROBE), timeout=10)
    assert result.returncode == 0, result.stderr


def test_table_loading_measures_original_native_encoding_and_budget(monkeypatch):
    import webview.util
    from webview.window import Window
    from namisync.interfaces.web import bridge

    monkeypatch.setattr(Window, "evaluate_js", lambda _window, script: script)
    timing = loading.HostTimings()
    record = {}
    original_consume = bridge._JsonByteBudget.consume
    original_budget_init = bridge._JsonByteBudget.__init__
    original_capture = bridge._capture_bridge_response_result
    with timing.installed():
        assert bridge._JsonByteBudget.consume is original_consume
        timing.current.record, timing.current.active = record, set()
        shared = [True, None, -12, "quote'\"\\\b\f\n\r\t\u0001"]
        value = {"unicode": "\u00e9\u4e2d\U0001f600", "nested": [shared, shared]}
        captured = bridge._capture_bridge_response_result(value, "a" * 32, 8 * 1024 * 1024)
        projected = bridge._project_response_value(captured, set(), validate=False)
        native = {"transport_version": 1, "response_token": None, "response": {"schema_version": 1, "request_id": "a" * 32, "ok": True, "result": projected}}
        encoded = webview.util.json.dumps(native)
        script = "window.pywebview._returnValuesCallbacks['dispatch']['id']({value:'" + encoded.replace("\\", "\\\\").replace("'", "\\'") + "'})"
        assert Window.evaluate_js(object(), script) == script
    assert record["native_json_bytes"] == len(encoded.encode("utf-8"))
    assert record["native_callback_script_bytes"] == len(script.encode("utf-8"))
    assert record["canonical_budget_bytes"] == len(json.dumps(native["response"], ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    assert record["native_json_encode_ns"] >= 0
    assert timing.current.record is None
    assert timing.current.capture_budget is None
    assert bridge._JsonByteBudget.__init__ is original_budget_init
    assert bridge._capture_bridge_response_result is original_capture
    assert bridge._JsonByteBudget.consume is original_consume


def test_table_loading_budget_observes_success_without_reencoding(monkeypatch):
    from namisync.interfaces.web import bridge

    value = {"text": "\u00e9\u4e2d\U0001f600\"\\\n" * 100}
    response = {"schema_version": 1, "request_id": "a" * 32, "ok": True, "result": value}
    expected = len(json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    original_dumps = bridge.json.dumps
    encodings = []

    def refuse_response_reencoding(value, *args, **kwargs):
        assert type(value) is str, "budget observation must not re-encode the response"
        encodings.append((value, args, kwargs))
        return original_dumps(value, *args, **kwargs)

    monkeypatch.setattr(bridge.json, "dumps", refuse_response_reencoding)
    bridge._capture_bridge_response_result(value, "a" * 32, expected)
    expected_encodings = tuple(encodings)
    encodings.clear()

    timing = loading.HostTimings()
    with timing.installed():
        timing.current.record, timing.current.active = {}, set()
        captured = bridge._capture_bridge_response_result(value, "a" * 32, expected)
        assert captured == value
        assert captured is not value
        assert timing.current.record["canonical_budget_bytes"] == expected
        assert timing.current.capture_budget is None
    assert tuple(encodings) == expected_encodings


@pytest.mark.parametrize("value,ceiling,error", (
    ("x" * 2000, 1024, "ceiling"),
    ("prefix\ud800", 8 * 1024 * 1024, "Unicode"),
), ids=("oversized", "invalid-unicode"))
def test_table_loading_refused_capture_clears_budget(value, ceiling, error):
    from namisync.interfaces.web import bridge

    timing = loading.HostTimings()
    original_budget_init = bridge._JsonByteBudget.__init__
    original_consume = bridge._JsonByteBudget.consume
    original_capture = bridge._capture_bridge_response_result
    with pytest.raises(bridge.BridgeProtocolError, match=error):
        with timing.installed():
            timing.current.record, timing.current.active = {}, set()
            bridge._capture_bridge_response_result(value, "a" * 32, ceiling)
    assert "canonical_budget_bytes" not in timing.current.record
    assert timing.current.capture_budget is None
    assert timing.current.active == set()
    assert bridge._JsonByteBudget.__init__ is original_budget_init
    assert bridge._JsonByteBudget.consume is original_consume
    assert bridge._capture_bridge_response_result is original_capture


def test_table_loading_nested_capture_keeps_outer_budget():
    from namisync.interfaces.web import bridge

    class NestedCapture(dict):
        def items(self):
            bridge._capture_bridge_response_result({"other": "x" * 1000}, "b" * 32, 8 * 1024 * 1024)
            return super().items()

    value = NestedCapture(text="outer")
    response = {"schema_version": 1, "request_id": "a" * 32, "ok": True, "result": dict(value)}
    expected = len(json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    timing = loading.HostTimings()
    with timing.installed():
        timing.current.record, timing.current.active = {}, set()
        bridge._capture_bridge_response_result(value, "a" * 32, 8 * 1024 * 1024)
        assert timing.current.record["canonical_budget_bytes"] == expected
        assert timing.current.capture_budget is None


def _receipt(case="plan-base", viewport_height=480):
    owner = {"task_id": "task", "session_id": "session", "publication_request_id": "publication", "navigation_revision": 1}
    host, requests, gestures = [], [], []
    total = 119968 if case == "plan-base" else 120000
    command = "get_plan_window" if case == "plan-base" else "get_inventory_window"
    setup_last = 20032 + (viewport_height + 23) // 24 - 1
    setup_offset = 20000 if case == "plan-base" else setup_last - 32
    phases = ("pre_handler_ns", "registry_ns", "window_build_ns", "capture_ns", "projection_ns", "native_json_encode_ns", "canonical_budget_bytes", "native_json_bytes", "native_callback_script_bytes")
    for kind, index in [("initial", 1)] + [(name, index) for name in loading.GESTURES for index in range(1, 4)]:
        target = {"initial": 0, "sequential": 256, "jump": 60000, "covered-return": 0, "burst": 40000, "keyboard": setup_offset - 1}[kind]
        identity = f"{kind}-{index}"
        payload = {"task_id": "task", "offset": target, "limit": 256}
        host.append({"request_id": identity, "payload": payload, "command": command, **dict.fromkeys(phases, 1)})
        requests.append({"request_id": identity, "payload": payload, "command": command, "gesture": identity,
            "ownership": owner, "adoption_ownership": owner, "row_count": 256, "returned_offset": target,
            "returned_first_node_id": "node", "adopted": True, "dom_ns": 1,
            "settlement_error": None, **dict.fromkeys(loading.BROWSER_PHASES, 1)})
        if kind == "keyboard":
            setup_id = f"setup-{index}"
            setup_payload = {**payload, "offset": setup_offset}
            host.append({**host[-1], "request_id": setup_id, "payload": setup_payload})
            requests[-1]["submitted"] = 2
            requests.append({**requests[-1], "request_id": setup_id, "payload": setup_payload,
                "gesture": None, "returned_offset": setup_offset, "submitted": 0, "validated_at": 1})
        gestures.append({"kind": kind, "iteration": index, "landed": True, "covered": True, "row_count": 256,
            "input_timestamps_ms": [0] * {"initial": 0, "burst": 8, "covered-return": 2}.get(kind, 1),
            "input_cadence_ms": [0] * {"initial": 0, "burst": 7, "covered-return": 1}.get(kind, 0),
            "input_span_ns": 0, "covered_after_last_input_ns": 10,
            "paint_opportunity_after_last_input_ns": 20, "settlement_after_last_input_ns": 30,
            "total": total, "target": target, "first": target, "last": target + 20, "offset": target,
            "active_index": target, "active_node_id": "node", "first_node_id": "node",
            "setup_offset": setup_offset if kind == "keyboard" else None,
            "setup_request_id": f"setup-{index}" if kind == "keyboard" else None,
            "setup_first": 20032 if kind == "keyboard" else None, "setup_last": setup_last if kind == "keyboard" else None,
            "visibility_state": "visible", "document_has_focus": True, "pending": 0, "ownership": owner,
            "frame_count": 2, "request_count": 1, "maximum_outstanding": 1, "uncovered_ns": 0,
            "settlement_pending": 0, "settlement_ns": 30, "covered_ns": 10, "paint_opportunity_ns": 20})
    profile = {"theme": "light", "reduced_motion": False, "forced_colors": False, "details_expanded": "false", "row_height": 24,
        "visibility_state": "visible", "document_has_focus": True,
        **dict.fromkeys(("inner_width", "inner_height", "device_pixel_ratio", "viewport_width"), 1), "viewport_height": viewport_height}
    return {"case": case, "launch_token": "token", "host": host, "browser": {"complete": True,
        "fixture": {"case": case, "visible_rows": total, "task_id": "task", "session_id": "session", "request_id": "publication"},
        "profile": profile, "requests": requests, "gestures": gestures}}


def test_table_loading_accepts_complete_correlated_control():
    assert loading.validate_child(_receipt(), "plan-base", "token")["browser"]["complete"]


@pytest.mark.parametrize("case,height,offset", (("plan-base", 480, 20000), ("inventory-base", 480, 20019), ("inventory-base", 481, 20020)))
def test_table_loading_keyboard_setup_correlates_observed_window(case, height, offset):
    receipt = _receipt(case, height)
    sample = receipt["browser"]["gestures"][-1]
    assert sample["setup_offset"] == offset
    assert sample["target"] == offset - 1
    loading.validate_child(receipt, case, "token")
    sample.update(setup_offset=offset + 1, target=offset, active_index=offset)
    with pytest.raises(ValueError, match="setup window differs"):
        loading.validate_child(receipt, case, "token")


@pytest.mark.parametrize("change", (
    lambda value: value["browser"]["gestures"][-1].update(setup_request_id="absent"),
    lambda value: value["browser"]["requests"][-1].update(gesture="keyboard-3"),
    lambda value: value["browser"]["requests"][-1].update(validated_at=3),
    lambda value: value["browser"]["requests"][-1].update(adopted=False),
))
def test_table_loading_rejects_uncorroborated_keyboard_setup(change):
    receipt = _receipt()
    change(receipt)
    with pytest.raises(ValueError, match="setup window differs"):
        loading.validate_child(receipt, "plan-base", "token")


def test_table_loading_reports_actual_incomplete_reason_without_profile():
    receipt = {"case": "plan-base", "launch_token": "token", "browser": {"complete": False, "error": "schema settlement failed " + "x" * 1000}}
    with pytest.raises(ValueError, match="schema settlement failed") as raised:
        loading.validate_child(receipt, "plan-base", "token", Path("installed"))
    assert len(str(raised.value)) < 550


def test_table_loading_visible_coverage_can_precede_settlement():
    receipt = _receipt()
    receipt["browser"]["gestures"][0]["pending"] = 2
    loading.validate_child(receipt, "plan-base", "token")
    receipt["browser"]["gestures"][0]["settlement_pending"] = 1
    with pytest.raises(ValueError, match="land truthfully"):
        loading.validate_child(receipt, "plan-base", "token")


def test_table_loading_phase_summaries_exclude_setup_and_discarded_dom():
    receipt = _receipt()
    setup = deepcopy(receipt["browser"]["requests"][0])
    setup.update(request_id="setup", gesture=None, dom_ns=1000)
    receipt["browser"]["requests"].append(setup)
    setup_host = deepcopy(receipt["host"][0])
    setup_host.update(request_id="setup", native_json_bytes=1000)
    receipt["host"].append(setup_host)
    receipt["browser"]["requests"][2].update(adopted=False, dom_ns=999)
    receipt["browser"]["requests"][1]["round_trip_ns"] = 5
    summaries = loading.summarize_children([receipt])
    assert summaries["initial"]["counts"] == {"gestures": 1, "requests": 1, "adopted": 1, "discarded": 0}
    assert summaries["initial"]["host"]["native_json_bytes"] == {"count": 1, "median": 1, "minimum": 1, "maximum": 1}
    assert summaries["sequential"]["adopted_dom_ns"]["count"] == 2
    assert summaries["sequential"]["adopted_dom_ns"]["maximum"] == 1
    assert summaries["sequential"]["browser"]["round_trip_ns"] == {"count": 3, "median": 1, "minimum": 1, "maximum": 5}
    aggregate = loading.summarize_children([receipt, _receipt()])
    assert aggregate["sequential"]["counts"]["requests"] == 6
    assert aggregate["initial"]["gesture"]["paint_opportunity_ns"]["count"] == 2


def test_table_loading_browser_settlement_and_first_visible_frames(tmp_path):
    from _frontend_test_support import _node_executable, run_node_probe

    node = _node_executable()
    assert node is not None, "Node.js is required for the measurement method controls"
    source = loading.PROBE.read_text(encoding="utf-8")
    prelude, driver = source.split("// DRIVER\n")
    observe = driver[driver.index("  async function observe("):driver.index("  function scroll(")]
    probe = tmp_path / "measurement-control.mjs"
    probe.write_text("""import assert from 'node:assert/strict';
let timestamp = 0;
globalThis.performance = {now: () => timestamp};
globalThis.__tableLoadingApp = {snapshot: () => ({task_id:'task'})};
""" + prelude + """
const hook = globalThis.__tableLoading;
const attempt = {command:'get_plan_window',requestId:'refused',result:{error:new Error('actual schema rejection'),value:null}};
hook.read('plan', 0); hook.submit(attempt, JSON.stringify({payload:{task_id:'task',offset:0}}));
hook.native(attempt.requestId);
const response = {ok:true,result:{disposition:'current',offset:0,rows:[]}};
hook.validated(attempt, response);
assert.equal(hook.pending, 0);
assert.equal(hook.requests[0].settlement_error, 'Error: actual schema rejection');
assert.equal(hook.failure.response, response);
assert.match(hook.fatal, /actual schema rejection/);
hook.dom(response.result, 0);
assert.equal(hook.requests[0].adopted, false);
hook.restore();
let observed = null;
const gestures = [];
const fixture = {visible_rows: 120000};
const trace = {pending:2,requests:[{gesture:'covered-return-1',submitted:0,validated_at:64,adopted:false}],ns:value=>value*1000000,end(){}};
const targetFrame = {covered:true,total:120000,visibility_state:'visible',document_has_focus:true,first:0,pending:2};
const coverage = () => ({...targetFrame,pending:trace.pending});
const frame = async () => {timestamp = Math.max(timestamp,64);trace.pending = 0;};
const until = async (predicate, label) => {if (!predicate()) await frame();assert.ok(predicate(),label);};
""" + observe + """
const gesture = {kind:'covered-return',iteration:1,started:0,inputs:[0,5],frames:[{timestamp:8,value:targetFrame},{timestamp:16,value:targetFrame}]};
await observe(gesture, 0);
assert.equal(gestures[0].covered_ns, 8000000);
assert.equal(gestures[0].paint_opportunity_ns, 16000000);
assert.equal(gestures[0].settlement_ns, 64000000);
assert.equal(gestures[0].covered_after_last_input_ns, 3000000);
assert.equal(gestures[0].paint_opportunity_after_last_input_ns, 11000000);
assert.equal(gestures[0].settlement_after_last_input_ns, 59000000);
assert.deepEqual(gestures[0].input_cadence_ms, [5]);
assert.equal(gestures[0].pending, 2);
assert.equal(gestures[0].settlement_pending, 0);
assert.equal(gestures[0].discarded_responses, 1);
timestamp = 128;
targetFrame.first = 40000;
await observe({kind:'burst',iteration:1,started:0,inputs:[0,7,15,26,40,51,60,70],
  frames:[{timestamp:80,value:targetFrame},{timestamp:96,value:targetFrame}]}, 40000);
assert.equal(gestures[1].covered_ns, 80000000);
assert.equal(gestures[1].covered_after_last_input_ns, 10000000);
assert.equal(gestures[1].input_span_ns, 70000000);
assert.deepEqual(gestures[1].input_cadence_ms, [7,8,11,14,11,9,10]);
const offscreen = {...targetFrame,active_index:-1,last:20};
await assert.rejects(observe({kind:'keyboard',iteration:1,started:0,
  frames:[{timestamp:8,value:offscreen},{timestamp:16,value:offscreen}]}, -1), /frame interval was not observed/);
""", encoding="utf-8")
    result = run_node_probe((node, probe), timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("change", (
    lambda value: value["browser"].update(complete=False),
    lambda value: value["browser"]["gestures"].pop(),
    lambda value: value["browser"]["gestures"][0].update(landed=False),
    lambda value: value["browser"]["gestures"][0].update(row_count=257),
    lambda value: value["browser"]["gestures"][10].update(input_timestamps_ms=[0]),
    lambda value: value["browser"]["gestures"][1].update(input_span_ns=100),
    lambda value: value["browser"]["gestures"][1].update(covered_after_last_input_ns=-1),
    lambda value: value["browser"]["gestures"][10].update(input_cadence_ms=[3] * 7),
    lambda value: value["browser"]["requests"].append({"request_id": "missing"}),
    lambda value: (value.update(host=[]), value["browser"].update(requests=[])),
    lambda value: value["browser"]["gestures"][1].update(first=0),
    lambda value: value["browser"]["gestures"][-1].update(active_index=0),
    lambda value: value["browser"]["fixture"].update(visible_rows=120000),
    lambda value: value["browser"]["profile"].update(theme="dark"),
    lambda value: value["browser"]["gestures"][-1].update(setup_offset=20031),
    lambda value: value["browser"]["gestures"][-1].update(setup_first=20031),
    lambda value: value["browser"]["gestures"][-1].update(setup_last=20032),
    lambda value: value["browser"]["gestures"][-1].update(first=20000),
    lambda value: value["browser"]["requests"][0].update(settlement_error="actual rejected schema"),
    lambda value: value["browser"]["gestures"][0].update(ownership={"task_id": "another", "session_id": "session", "publication_request_id": "publication", "navigation_revision": 1}),
))
def test_table_loading_rejects_incomplete_action_and_phase_evidence(change):
    receipt = deepcopy(_receipt())
    change(receipt)
    with pytest.raises(ValueError):
        loading.validate_child(receipt, "plan-base", "token")
