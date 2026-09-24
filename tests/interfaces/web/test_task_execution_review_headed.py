"""Installed headed evidence for the short execution-review scenario."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import _headed_cdp as cdp
import _task_execution_review_headed_child as child
from _headed_evidence import EvidencePaths, EvidenceReader, require_host_final
from _headed_native import (
    clean_child_environment, close_window, require_absolute_local_test_root,
    scenario_deadline, start_headed_process, terminate_process_tree,
    wait_for_accessible_text, wait_for_initial_evidence, wait_for_process,
    wait_for_window,
)
from conftest import HeadedInstalledWheel


_CHILD = Path(__file__).with_name("_task_execution_review_headed_child.py")


class _Awaiter:
    def __init__(self, callback: object) -> None:
        self.callback = callback

    def OnCompleted(self, completion: object) -> None:
        completion()


class _Task:
    IsFaulted = False
    IsCanceled = False

    def __init__(self, result: dict[str, object]) -> None:
        self.Result = json.dumps(result)

    def GetAwaiter(self) -> _Awaiter:
        return _Awaiter(self)


class _Native:
    def __init__(self) -> None:
        self.invocations = 0
        self.queued: list[object] = []

    def BeginInvoke(self, action: object) -> None:
        self.invocations += 1
        self.queued.append(action)

    def drain(self) -> None:
        while self.queued:
            self.queued.pop(0)()


class _Core:
    def __init__(self, results: list[dict[str, object]]) -> None:
        self.results = iter(results)
        self.calls: list[tuple[str, str]] = []

    def CallDevToolsProtocolMethodAsync(self, method: str, payload: str) -> _Task:
        self.calls.append((method, payload))
        return _Task(next(self.results))


def test_native_cdp_consumes_real_method_envelopes_and_persists_capture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setitem(__import__("sys").modules, "System", SimpleNamespace(Action=lambda fn: fn))
    core = _Core([
        {"result": {"type": "boolean", "value": True}},
        {},
        {"result": {"type": "object", "value": {
            "theme": "dark", "material": "mica", "forcedColors": False,
        }}},
        {"data": "aGVsbG8="},
    ])
    monkeypatch.setattr(cdp, "_capture_alpha_samples", lambda _path: {
        "top_left": 0, "center": 13, "bottom_right": 255,
    })
    failures: list[object] = []
    retained: list[object] = []
    native = _Native()
    transport = cdp.NativeCdp(
        native, core, retained,
        lambda error, task, step, method: failures.append((error, task, step, method)),
    )
    observed: list[object] = []
    transport.evaluate("true", observed.append, "evaluate")
    transport.call("Input.dispatchMouseEvent", {"type": "mouseMoved"}, observed.append, "input")
    target = tmp_path / "capture.png"
    transport.capture(target, lambda: observed.append("persisted"), "capture")
    assert observed == []
    assert not target.exists()
    native.drain()
    assert failures == []
    assert observed == [True, {}, "persisted"]
    assert target.read_bytes() == b"hello"
    assert json.loads(target.with_suffix(".capture.json").read_text(encoding="utf-8")) == {
        "source": "Page.captureScreenshot",
        "surface": "browser surface",
        "native_window_composition": "not captured",
        "context_observed": "before capture",
        "page_theme": "dark", "page_material": "mica", "page_forced_colors": False,
        "raw_sha256": hashlib.sha256(b"hello").hexdigest(),
        "alpha_samples": {"top_left": 0, "center": 13, "bottom_right": 255},
    }
    assert [method for method, _payload in core.calls] == [
        "Runtime.evaluate", "Input.dispatchMouseEvent", "Runtime.evaluate",
        "Page.captureScreenshot",
    ]
    assert len(retained) == 8
    assert native.invocations == 4


@pytest.mark.parametrize("material", ["opaque", "degraded", None])
def test_native_cdp_capture_records_bounded_fallback_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, material: str | None,
) -> None:
    monkeypatch.setitem(sys.modules, "System", SimpleNamespace(Action=lambda fn: fn))
    monkeypatch.setattr(cdp, "_capture_alpha_samples", lambda _path: {
        "top_left": 255, "center": 255, "bottom_right": 255,
    })
    core = _Core([
        {"result": {"type": "object", "value": {
            "theme": "light", "material": material, "forcedColors": material == "opaque",
        }}},
        {"data": "aGVsbG8="},
    ])
    failures: list[object] = []
    observed: list[str] = []
    transport = cdp.NativeCdp(
        native := _Native(), core, [],
        lambda error, task, step, method: failures.append((error, task, step, method)),
    )
    target = tmp_path / "fallback.png"
    transport.capture(target, lambda: observed.append("persisted"), "capture")
    native.drain()
    assert failures == []
    assert observed == ["persisted"]
    assert target.read_bytes() == b"hello"
    provenance = json.loads(target.with_suffix(".capture.json").read_text(encoding="utf-8"))
    assert provenance["page_theme"] == "light"
    assert provenance["page_material"] == material
    assert provenance["page_forced_colors"] is (material == "opaque")
    assert provenance["alpha_samples"] == {
        "top_left": 255, "center": 255, "bottom_right": 255,
    }


@pytest.mark.parametrize("state", ["faulted", "canceled"])
def test_native_cdp_reports_bounded_native_completion_failure(
    monkeypatch: pytest.MonkeyPatch, state: str,
) -> None:
    monkeypatch.setitem(__import__("sys").modules, "System", SimpleNamespace(Action=lambda fn: fn))
    task = _Task({})
    task.IsFaulted = state == "faulted"
    task.IsCanceled = state == "canceled"
    core = SimpleNamespace(CallDevToolsProtocolMethodAsync=lambda _method, _payload: task)
    failures: list[tuple[str, str]] = []
    transport = cdp.NativeCdp(
        native := _Native(), core, [],
        lambda error, _task, step, method: failures.append((step, method)),
    )
    transport.call("Input.dispatchKeyEvent", {"type": "keyDown"}, lambda _value: None, "key")
    native.drain()
    assert failures == [("key", "Input.dispatchKeyEvent")]


def test_standard_decoder_disposes_bitmap_and_rejects_invalid_image(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    disposed: list[bool] = []
    class Bitmap:
        Width = 12
        Height = 7
        def __init__(self, path: str) -> None:
            if Path(path).read_bytes() == b"invalid":
                raise ValueError("invalid image")
        def GetPixel(self, x: int, y: int) -> object:
            return SimpleNamespace(A={(0, 0): 0, (6, 3): 13, (11, 6): 255}[(x, y)])
        def Dispose(self) -> None:
            disposed.append(True)
    monkeypatch.setitem(sys.modules, "clr", SimpleNamespace(AddReference=lambda _name: None))
    monkeypatch.setitem(sys.modules, "System.Drawing", SimpleNamespace(Bitmap=Bitmap))
    valid = tmp_path / "valid.png"
    valid.write_bytes(b"decoded by native seam")
    assert cdp.decode_png(valid) == (12, 7)
    assert disposed == [True]
    assert cdp._capture_alpha_samples(valid) == {
        "top_left": 0, "center": 13, "bottom_right": 255,
    }
    assert disposed == [True, True]
    invalid = tmp_path / "invalid.png"
    invalid.write_bytes(b"invalid")
    with pytest.raises(ValueError, match="invalid image"):
        cdp.decode_png(invalid)


def test_command_wrapper_preserves_specs_arguments_results_and_errors(tmp_path: Path) -> None:
    from dataclasses import replace

    phase = child._ExecutionReviewPhase(tmp_path / "source", tmp_path / "target")
    phase.plan = {"task_id": "1" * 32, "request_id": "2" * 32, "session_id": "3" * 32, "task_label": "Task 1"}
    payload = SimpleNamespace(task_id="1" * 32, request_id="2" * 32)
    result = SimpleNamespace(task_id="1" * 32, request_id="4" * 32, session_id="5" * 32)
    calls: list[object] = []
    def handler(value: object) -> object:
        calls.append(value)
        return result
    original = {name: child._test_spec(handler if name == "start_execution" else lambda _value: object()) for name in child._COMMANDS}
    wrapped = phase.wrap(original)
    assert wrapped["start_execution"].handler(payload) is result
    assert calls == [payload]
    assert replace(wrapped["start_execution"], handler=original["start_execution"].handler) == original["start_execution"]
    error = RuntimeError("private path and contents")
    def fail(_value: object) -> object:
        raise error
    failing = dict(original)
    failing["start_execution"] = replace(original["start_execution"], handler=fail)
    with pytest.raises(RuntimeError) as caught:
        phase.wrap(failing)["start_execution"].handler(payload)
    assert caught.value is error


def test_real_composed_registry_commands_copy_and_bind_distinct_run(tmp_path: Path) -> None:
    from namisync.interfaces.web import host
    from namisync.interfaces.web.commands import production_command_specs
    from namisync.interfaces.web.paths import AppPaths
    from namisync.interfaces.web.readiness import CommandPhase, ReadinessContext
    from namisync.interfaces.web.slots import FolderSlotTable

    paths = AppPaths.from_root(tmp_path / "app")
    paths.ensure_directories()
    service = host._create_service(paths)
    registry = None
    try:
        contract = service.validate_database_contracts()
        if contract.state == "fresh":
            service.initialize_database_contracts()
        registry = host._task_registry(service)
        class Cosmetics:
            def read_section(self, *_args: object) -> None:
                return None

        base_commands = production_command_specs(
            picker=lambda: None, slots=FolderSlotTable(), registry=registry,
            cosmetics=Cosmetics(), shell_ready=lambda _generation: None,
            readiness_echo=lambda _generation, _challenge: True,
        )
        phase = child._ExecutionReviewPhase(tmp_path / "source", tmp_path / "target")
        commands = phase.wrap(base_commands)
        context = ReadinessContext(CommandPhase.OPEN, 1)
        phase.bind(registry)
        deadline = time.monotonic() + 10
        drain_ordinal = 0
        def drain_until_terminal(session_id: str) -> object:
            nonlocal drain_ordinal
            while True:
                task = next(item for item in registry.list_tasks().tasks if item.task_id == phase.plan["task_id"])
                if task.session_state in {"completed", "completed-degraded"}:
                    return task
                if time.monotonic() >= deadline:
                    pytest.fail(f"real session did not settle: {task}")
                drain_ordinal += 1
                commands["next_events"].invoke({
                    "task_id": phase.plan["task_id"], "session_id": session_id,
                    "drain_id": f"{drain_ordinal:032x}", "replay_from": None,
                }, context=context)

        task = drain_until_terminal(phase.plan["session_id"])
        commands["release_terminal_session"].invoke({
            "task_id": task.task_id, "session_id": task.session_id,
        }, context=context)
        opened = commands["open_plan_view"].invoke(
            {"task_id": phase.plan["task_id"]}, context=context,
        )
        execution = commands["start_execution"].invoke({
            "task_id": phase.plan["task_id"], "request_id": phase.plan["request_id"],
            "command_id": "b" * 32, "expected_revision": opened["view_revision"],
            "destructive_acknowledged": False,
        }, context=context)
        assert execution.request_id != phase.plan["request_id"]
        task = drain_until_terminal(execution.session_id)
        commands["release_terminal_session"].invoke({
            "task_id": phase.plan["task_id"], "session_id": execution.session_id,
        }, context=context)
        retained = commands["open_plan_view"].invoke(
            {"task_id": phase.plan["task_id"]}, context=context,
        )
        window = commands["get_plan_window"].invoke({
            "task_id": phase.plan["task_id"], "expected_revision": retained["view_revision"],
            "offset": 0, "limit": 256,
        }, context=context)
        operation_id = window["rows"][0]["operation_id"]
        commands["get_execution_detail"].invoke({
            "task_id": phase.plan["task_id"], "operation_id": operation_id,
            "expected_execution_revision": window["execution"]["execution_revision"],
        }, context=context)
        assert phase.capture_ready() is True
        phase.verify_files()
        assert not any(path.name != "one.txt" for path in phase.target.iterdir())
    finally:
        service.close()


def test_execution_review_phase_uses_distinct_plan_and_run_identities_and_real_bytes(
    tmp_path: Path,
) -> None:
    phase = child._ExecutionReviewPhase(tmp_path / "source", tmp_path / "target")
    started = SimpleNamespace(task_id="1" * 32, request_id="2" * 32, session_id="3" * 32)
    registry = SimpleNamespace(
        start_plan=lambda *_args, **_kwargs: started,
        list_tasks=lambda: SimpleNamespace(tasks=(SimpleNamespace(
            task_id=started.task_id, session_released=True,
        ),)),
    )
    phase.bind(registry)
    phase.bind_visible_label("Observed task")
    assert phase.plan == {
        "task_id": "1" * 32, "request_id": "2" * 32, "session_id": "3" * 32,
        "task_label": "Observed task",
    }
    assert (phase.source / "one.txt").read_bytes() == child._BYTES
    assert not (phase.target / "one.txt").exists()
    execution = SimpleNamespace(
        task_id=started.task_id, request_id="4" * 32, session_id="5" * 32,
    )
    phase.record(
        "start_execution", 1, 2,
        SimpleNamespace(task_id=started.task_id, request_id=started.request_id), execution,
    )
    assert phase.execution["request_id"] != phase.plan["request_id"]
    (phase.target / "one.txt").write_bytes(child._BYTES)
    phase.verify_files()
    assert (phase.source / "one.txt").read_bytes() == child._BYTES


def test_execution_review_phase_rejects_execution_for_another_plan(tmp_path: Path) -> None:
    phase = child._ExecutionReviewPhase(tmp_path / "source", tmp_path / "target")
    phase.plan = {"task_id": "1" * 32, "request_id": "2" * 32, "session_id": "3" * 32}
    with pytest.raises(ValueError, match="seeded plan"):
        phase.record(
            "start_execution", 1, 2,
            SimpleNamespace(task_id="1" * 32, request_id="9" * 32),
            SimpleNamespace(
                task_id="1" * 32, request_id="2" * 32, session_id="4" * 32,
            ),
        )


def test_execution_review_phase_accepts_latest_settled_receipt_and_stable_capture(tmp_path: Path) -> None:
    from namisync.dispatcher import SessionNotFound

    phase = child._ExecutionReviewPhase(tmp_path / "source", tmp_path / "target")
    task_id, plan_id, session_id = "1" * 32, "2" * 32, "5" * 32
    phase.plan = {"task_id": task_id, "request_id": plan_id, "session_id": "3" * 32,
                  "task_label": "Task 1"}
    service = SimpleNamespace(get_session=lambda _session_id: (_ for _ in ()).throw(SessionNotFound()))
    task = SimpleNamespace(task_id=task_id, session_id=session_id, session_released=True)
    phase.registry = SimpleNamespace(
        _lifecycle=service,
        list_tasks=lambda: SimpleNamespace(tasks=(task,)),
    )
    phase.record(
        "start_execution", 1, 2,
        SimpleNamespace(task_id=task_id, request_id=plan_id),
        SimpleNamespace(task_id=task_id, request_id="4" * 32, session_id=session_id),
    )
    phase.record(
        "release_terminal_session", 3, 4,
        SimpleNamespace(task_id=task_id, session_id=session_id),
        SimpleNamespace(task_id=task_id, session_id=session_id),
    )
    window = {
        "disposition": "current", "view_revision": 7,
        "rows": [{"operation_id": "6" * 32, "display": "one.txt"}],
        "execution": {"session_id": session_id, "execution_revision": 8},
    }
    phase.record(
        "get_plan_window", 5, 6,
        SimpleNamespace(task_id=task_id, expected_revision=7), window,
    )
    phase.record(
        "get_plan_window", 7, 8,
        SimpleNamespace(task_id=task_id, expected_revision=9),
        {**window, "view_revision": 9},
    )
    phase.record(
        "get_plan_window", 9, 10,
        SimpleNamespace(task_id=task_id, expected_revision=7), window,
    )
    assert phase.window["view_revision"] == 9
    phase.record(
        "get_execution_detail", 11, 12,
        SimpleNamespace(task_id=task_id, operation_id="6" * 32, expected_execution_revision=7),
        {"disposition": "conflict"},
    )
    assert phase.detail is None
    detail_payload = SimpleNamespace(
        task_id=task_id, operation_id="6" * 32, expected_execution_revision=8,
    )
    detail_result = {
        "disposition": "current", "operation_id": "6" * 32,
        "execution_revision": 8, "operation": SimpleNamespace(path="one.txt"),
    }
    phase.record(
        "get_execution_detail", 13, 14, detail_payload, detail_result,
    )
    phase.record("get_execution_detail", 15, 16, detail_payload, detail_result)
    assert phase.execution["completed"] < phase.release["admitted"]
    assert phase.release["completed"] < phase.window["admitted"]
    assert phase.capture_ready() is True
    identity = phase._expected_identity_locked()
    phase.set_identity("pre", identity)
    with pytest.raises(RuntimeError, match="identity"):
        phase.set_identity("post", {**identity, "operationPath": "other.txt"})
    phase.record(
        "get_plan_window", 17, 18,
        SimpleNamespace(task_id=task_id, expected_revision=11),
        {**window, "view_revision": 11},
    )
    with pytest.raises(RuntimeError, match="identity"):
        phase.set_identity("post", identity)
    task.session_released = False
    assert phase.capture_ready() is False


def test_phase_rejects_early_and_mismatched_current_detail(tmp_path: Path) -> None:
    task_id, plan_id, session_id, operation_id = (
        "1" * 32, "2" * 32, "5" * 32, "6" * 32,
    )
    early = child._ExecutionReviewPhase(tmp_path / "early-source", tmp_path / "early-target")
    early.plan = {"task_id": task_id, "request_id": plan_id, "session_id": "3" * 32, "task_label": "Task 1"}
    with pytest.raises(ValueError, match="retained window"):
        early.record(
            "get_execution_detail", 1, 2,
            SimpleNamespace(task_id=task_id, operation_id=operation_id, expected_execution_revision=8),
            {"disposition": "current", "operation_id": operation_id, "execution_revision": 8},
        )

    phase = child._ExecutionReviewPhase(tmp_path / "source", tmp_path / "target")
    phase.plan = {"task_id": task_id, "request_id": plan_id, "session_id": "3" * 32, "task_label": "Task 1"}
    phase.record("start_execution", 1, 2, SimpleNamespace(task_id=task_id, request_id=plan_id), SimpleNamespace(task_id=task_id, request_id="4" * 32, session_id=session_id))
    with pytest.raises(ValueError, match="execution"):
        phase.record("release_terminal_session", 3, 4, SimpleNamespace(task_id=task_id, session_id="9" * 32), SimpleNamespace(task_id=task_id, session_id="9" * 32))
    phase.record("release_terminal_session", 5, 6, SimpleNamespace(task_id=task_id, session_id=session_id), SimpleNamespace(task_id=task_id, session_id=session_id))
    window = {"disposition": "current", "view_revision": 7, "rows": [{"operation_id": operation_id, "display": "one.txt"}], "execution": {"session_id": session_id, "execution_revision": 8}}
    phase.record("get_plan_window", 3, 7, SimpleNamespace(task_id=task_id, expected_revision=7), window)
    assert phase.window is None
    phase.record("get_plan_window", 8, 9, SimpleNamespace(task_id=task_id, expected_revision=7), window)
    with pytest.raises(ValueError, match="does not match"):
        phase.record("get_execution_detail", 10, 11, SimpleNamespace(task_id=task_id, operation_id="7" * 32, expected_execution_revision=8), {"disposition": "current", "operation_id": "7" * 32, "execution_revision": 8})


def test_task_execution_review_scenarios_own_disjoint_evidence_paths(tmp_path: Path) -> None:
    default = _execution_review_paths((tmp_path / "default").resolve())
    larger = _execution_review_paths((tmp_path / "larger").resolve())
    assert set(default).isdisjoint(larger)
    assert default[1].name == larger[1].name == "execution-review.png"
    assert default[2].name == larger[2].name == "execution-review-driver.json"


def test_execution_review_evidence_ready_failure_final_and_privacy(tmp_path: Path) -> None:
    from _headed_evidence import require_host_final

    ready_root = (tmp_path / "ready").resolve()
    ready_root.mkdir()
    ready_paths = EvidencePaths(ready_root)
    recorder = child._Recorder(ready_paths, ready_root / "driver.json")
    recorder.complete({"geometry": {}, "dimensions": [1, 1], "phase": {}})
    recorder.finish(0, True)
    ready_reader = EvidenceReader(ready_paths)
    assert ready_reader.available_initial() == "ready"
    assert ready_reader.read_ready()["report"]["dimensions"] == [1, 1]
    assert require_host_final(ready_reader.read_final(), exit_code=0) is True
    ready_reader.assert_consistent(require_final=True)

    failure_root = (tmp_path / "failure").resolve()
    failure_root.mkdir()
    failure_paths = EvidencePaths(failure_root)
    failed = child._Recorder(failure_paths, failure_root / "driver.json")
    failed.phase = child._ExecutionReviewPhase(tmp_path / "private-source", tmp_path / "private-target")
    failed.phase.plan = {"task_id": "1" * 32, "request_id": "2" * 32,
                         "task_label": "private-content"}
    failed.fail("post-identity", "RuntimeError")
    failed.finish(1, False)
    failure_reader = EvidenceReader(failure_paths)
    assert failure_reader.available_initial() == "failure"
    assert failure_reader.read_failure() == {
        "stage": "post-identity", "reason": "RuntimeError",
        "identity": {"plan": {"task_id": "1" * 32, "request_id": "2" * 32}},
    }
    assert "private" not in (failure_root / "driver.json").read_text(encoding="utf-8")
    assert require_host_final(failure_reader.read_final(), exit_code=1) is False
    failure_reader.assert_consistent(require_final=True)

    diagnostic_root = (tmp_path / "diagnostic").resolve()
    diagnostic_root.mkdir()
    diagnostic_paths = EvidencePaths(diagnostic_root)
    diagnosed = child._Recorder(diagnostic_paths, diagnostic_root / "driver.json")
    diagnostic = {name: False for name in child._WAIT_REVIEW_DIAGNOSTIC}
    diagnosed.fail("wait-review", "TimeoutError", diagnostic)
    diagnosed.fail("later", "RuntimeError", {name: True for name in diagnostic})
    assert EvidenceReader(diagnostic_paths).read_failure() == {
        "stage": "wait-review", "reason": "TimeoutError", "identity": {},
        "diagnostic": diagnostic,
    }

    preclick_root = (tmp_path / "preclick").resolve()
    preclick_root.mkdir()
    preclick_paths = EvidencePaths(preclick_root)
    preclick = child._Recorder(preclick_paths, preclick_root / "driver.json")
    operands = {name: False for name in child._PRECLICK_DIAGNOSTIC}
    for invalid in ({**operands, "hitPresent": "secret"}, {**operands, "private": "secret"}):
        with pytest.raises(RuntimeError, match="diagnostic"):
            preclick.fail("page-preclick", "PointerTargetError", invalid)
    preclick.fail("page-preclick", "PointerTargetError", operands)
    assert EvidenceReader(preclick_paths).read_failure() == {
        "stage": "page-preclick", "reason": "PointerTargetError",
        "identity": {}, "diagnostic": operands,
    }
    assert "private" not in (preclick_root / "driver.json").read_text(encoding="utf-8")


@pytest.mark.headed
@pytest.mark.parametrize("large_window", [False, True], ids=["default", "larger"])
def test_installed_task_execution_review_real_copy_and_capture(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
    large_window: bool,
) -> None:
    result = _run_execution_review(
        headed_installed_wheel, tmp_path / ("larger" if large_window else "default"),
        large_window=large_window,
    )
    report = result["report"]
    assert report["geometry"] == {
        "rootFits": True, "tableUsable": True, "rowHeight": "24px",
        "detailVisible": True,
        "rowActivationFocused": True, "rowHit": True,
        "disclosureFocused": True, "disclosureVisible": True,
        "disclosureHit": True,
    }
    assert report["dimensions"][0] > 0 and report["dimensions"][1] > 0
    phase = report["phase"]
    assert phase["capture_complete"] is True
    assert phase["pre_identity"] == phase["post_identity"]
    assert phase["detail"]["operation_id"] == phase["window"]["operation_id"]
    assert phase["detail"]["execution_revision"] == phase["window"]["execution_revision"]
    assert phase["plan"]["request_id"] != phase["execution"]["request_id"]


def _execution_review_paths(root: Path) -> tuple[Path, Path, Path]:
    evidence = require_absolute_local_test_root(root / "evidence")
    return (
        evidence,
        require_absolute_local_test_root(evidence / "execution-review.png"),
        require_absolute_local_test_root(evidence / "execution-review-driver.json"),
    )


def _run_execution_review(
    installed: HeadedInstalledWheel, root: Path, *, large_window: bool,
) -> dict[str, object]:
    deadline = scenario_deadline(120.0)
    root = require_absolute_local_test_root(root)
    evidence, screenshot, driver = _execution_review_paths(root)
    data = require_absolute_local_test_root(root / "data")
    source = require_absolute_local_test_root(root / "source")
    target = require_absolute_local_test_root(root / "target")
    for directory in (root, evidence, data, source, target):
        directory.mkdir(parents=True, exist_ok=True)
    screenshot.unlink(missing_ok=True)
    driver.unlink(missing_ok=True)
    token = uuid4().hex
    args: tuple[object, ...] = (
        installed.python, _CHILD, "--data-dir", data, "--evidence-dir", evidence,
        "--source", source, "--target", target, "--screenshot", screenshot,
        "--driver", driver,
        "--mutex", rf"Local\NamiSync.ExecutionReview.{token}",
        "--title", f"NamiSync Execution Review {token}",
    )
    if large_window:
        args += ("--large-window",)
    reader = EvidenceReader(EvidencePaths(evidence))
    process = start_headed_process(args, cwd=installed.root, environment=clean_child_environment(), deadline=deadline)
    window = None
    initial: dict[str, object] | None = None
    milestone: str | None = None
    closed = False
    try:
        window = wait_for_window(process, f"NamiSync Execution Review {token}", deadline=deadline)
        milestone, initial = wait_for_initial_evidence(reader, process, deadline=deadline)
        if milestone == "ready":
            wait_for_accessible_text(
                window, "Completed", python=installed.python, deadline=deadline,
            )
        close_window(window)
        closed = True
        completed = wait_for_process(process, deadline=deadline)
        final = reader.read_final()
        assert final is not None
        host_returned = require_host_final(final, exit_code=completed.returncode)
        reader.assert_consistent(require_final=True)
        assert host_returned is True
        if milestone == "failure":
            pytest.fail(f"execution review child failed: {initial}")
        assert completed.returncode == 0
    finally:
        try:
            if window is not None and not closed and process.poll() is None:
                close_window(window)
        finally:
            terminate_process_tree(process, deadline=deadline)
    assert milestone == "ready" and initial is not None
    assert screenshot.is_file()
    assert (target / "one.txt").read_bytes() == child._BYTES
    assert (source / "one.txt").read_bytes() == child._BYTES
    return initial

def test_native_failure_site_retains_locations_without_exception_text() -> None:
    task = _Task({"exceptionDetails": {
        "exception": {"className": "ReferenceError", "description": r"C:\private\sentinel"},
        "stackTrace": {"callFrames": [
            {"lineNumber": 31, "url": r"C:\private\sentinel"},
            {"lineNumber": 88, "functionName": "private"},
        ] * 6},
    }})
    result = cdp.failure_site(task)
    assert result == {"exception": "ReferenceError", "lines": [31, 88] * 4}
    assert "private" not in json.dumps(result)
    assert cdp.failure_site(None) == {"exception": None, "lines": []}


def test_native_failure_site_bounds_async_description_locations() -> None:
    task = _Task({"exceptionDetails": {"exception": {
        "className": "Error",
        "description": "private error\n    at <anonymous>:43:7\n    at <anonymous>:9:2",
    }}})
    assert cdp.failure_site(task) == {"exception": "Error", "lines": [42, 8]}



def test_execution_review_control_uses_exact_empty_object() -> None:
    assert child._validate_empty({}) is None
    for value in (None, [], {"unexpected": True}):
        with pytest.raises(ValueError):
            child._validate_empty(value)
