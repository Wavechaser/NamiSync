"""Installed-wheel child composition for the Slice 2 real transport gates."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import sys
import threading
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import dataclass, field
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import MappingProxyType
from typing import Any
from unittest.mock import patch


_OPAQUE_ID = re.compile(r"[0-9a-f]{32}")
_SLOT_ID = re.compile(r"slot-[0-9a-f]{32}")
_TASK_ID = re.compile(r"task-[0-9a-f]{32}")


class _Recorder:
    def __init__(self, output: Path, mode: str) -> None:
        self._output = output
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {
            "schema_version": 1,
            "mode": mode,
            "startup_errors": [],
        }

    def set(self, name: str, value: Any) -> None:
        with self._lock:
            self._data[name] = value

    def append(self, name: str, value: Any) -> None:
        with self._lock:
            self._data.setdefault(name, []).append(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def startup_error(self, message: str) -> None:
        self.append("startup_errors", message)

    def write(self) -> None:
        with self._lock:
            encoded = json.dumps(self._data, indent=2, sort_keys=True)
            temporary = self._output.with_suffix(self._output.suffix + ".tmp")
            temporary.write_text(encoded, encoding="utf-8")
            temporary.replace(self._output)


@dataclass(frozen=True, slots=True)
class _Report:
    phase: str
    value: Mapping[str, object]


@dataclass(slots=True)
class _DrainProbe:
    entered: threading.Event = field(default_factory=threading.Event)
    exited: threading.Event = field(default_factory=threading.Event)


@dataclass(slots=True)
class _BrowserGateControl:
    scenario: Mapping[str, object]
    lock: threading.Lock = field(default_factory=threading.Lock)
    uncertain_command_id: str | None = None
    arm_uncertain_start: bool = False
    uncertain_start_replay_entered: threading.Event = field(
        default_factory=threading.Event
    )
    main_recovery_entered: threading.Event = field(default_factory=threading.Event)
    controlled_start_count: int = 0
    sinks: dict[str, object] = field(default_factory=dict)
    task_roles: dict[str, str] = field(default_factory=dict)
    main_stale_response_held: bool = False
    busy_drain_refused: bool = False
    busy_bridge_refused: bool = False
    malformed_attempts: int = 0
    interactive_failures: int = 0
    drain_cursors: list[dict[str, object]] = field(default_factory=list)
    registry_release_calls: list[list[str]] = field(default_factory=list)
    registry_close_calls: list[list[str]] = field(default_factory=list)

    @property
    def hostile(self) -> str:
        value = self.scenario.get("corpus")
        if type(value) is not str:
            raise ValueError("transport gate corpus is invalid")
        return value

    def controlled_session(self, role: str) -> tuple[str, str]:
        values = {
            "main": ("c" * 32, "d" * 32),
            "busy": ("e" * 32, "f" * 32),
            "malformed": ("7" * 32, "8" * 32),
        }
        return values[role]

    def is_controlled_session(self, session_id: str) -> bool:
        return any(
            session_id == session
            for _request, session in (
                self.controlled_session(role)
                for role in ("main", "busy", "malformed")
            )
        )

    def start_controlled(self, sink: object) -> tuple[str, str, str]:
        with self.lock:
            roles = ("main", "busy", "malformed")
            if self.controlled_start_count >= len(roles):
                raise RuntimeError("transport browser gate created too many tasks")
            role = roles[self.controlled_start_count]
            self.controlled_start_count += 1
            self.sinks[role] = sink
        request_id, session_id = self.controlled_session(role)
        if role == "main":
            _deliver_initial_events(sink, session_id)
        elif role == "busy":
            sink(_terminal_record(session_id, self.hostile))
        return role, request_id, session_id

    def note_task(self, task_id: str, session_id: str) -> None:
        for role in ("main", "busy", "malformed"):
            if session_id == self.controlled_session(role)[1]:
                with self.lock:
                    self.task_roles[task_id] = role
                return

    def role_for_task(self, task_id: object) -> str | None:
        if type(task_id) is not str:
            return None
        with self.lock:
            return self.task_roles.get(task_id)

    def classify_uncertain_start(self, command_id: object) -> str | None:
        if type(command_id) is not str:
            return None
        with self.lock:
            if self.arm_uncertain_start and self.uncertain_command_id is None:
                self.uncertain_command_id = command_id
                self.arm_uncertain_start = False
                return "first"
            if command_id == self.uncertain_command_id:
                return "replay"
        return None

    def emit_gap(self) -> None:
        with self.lock:
            sink = self.sinks.get("main")
        if not callable(sink):
            raise RuntimeError("main browser gate sink is unavailable")
        session_id = self.controlled_session("main")[1]
        sink(_event(session_id, 4, "Gap", {"first_missed_seq": 4}))
        sink(_event(session_id, 5, "PhaseChanged", {"phase": "retained-海"}))

    def status(self) -> dict[str, object]:
        with self.lock:
            return {
                "release_calls": len(self.registry_release_calls),
                "close_calls": len(self.registry_close_calls),
                "interactive_failures": self.interactive_failures,
                "malformed_attempts": self.malformed_attempts,
            }


def _event(
    session_id: str,
    sequence: int,
    body_type: str,
    body: Mapping[str, object],
):
    from namisync.workflows.views import SessionEventView

    return SessionEventView(
        session_id,
        sequence,
        "2026-08-13T00:00:00+00:00",
        body_type,
        dict(body),
    )


def _deliver_initial_events(sink: object, session_id: str) -> None:
    if not callable(sink):
        raise TypeError("controlled observation sink is not callable")
    sink(_event(session_id, 1, "StateChanged", {"state": "running"}))
    sink(
        _event(
            session_id,
            3,
            "Progress",
            {
                "items_done": 1,
                "items_total": 1,
                "bytes_done": 7,
                "bytes_total": 7,
                "current_path": "numeric-hole-海.txt",
            },
        )
    )


def _nonterminal_record(session_id: str):
    from namisync.workflows import PLAN_KIND
    from namisync.workflows.views import SessionRecordView

    return SessionRecordView(
        session_id,
        PLAN_KIND,
        "running",
        False,
        "2026-08-13T00:00:00+00:00",
        "2026-08-13T00:00:01+00:00",
        None,
        None,
    )


def _terminal_record(session_id: str, hostile: str):
    from namisync.workflows import PLAN_KIND
    from namisync.workflows.views import (
        IntegrityOutcomeView,
        OperationItemView,
        OperationResultView,
        PhaseResultView,
        SessionRecordView,
    )

    result = OperationResultView(
        headline="success",
        filesystem="completed",
        integrity="verified",
        recording="ok",
        audit="ok",
        disposition="ran",
        canceled=False,
        items=(
            OperationItemView(
                "operation",
                "execute",
                "copy-hostile",
                "copy",
                hostile,
                "succeeded",
                None,
                {
                    "hostile": hostile,
                    "nested": {"values": ["海", "é", "U0001f30a"]},
                },
            ),
            IntegrityOutcomeView(
                "integrity",
                "verify",
                "integrity-hostile",
                "row-hostile",
                "location-hostile",
                "integrity",
                hostile,
                "verified",
                None,
                hostile,
                "windows-unbuffered",
                "ok",
                "applied",
            ),
        ),
        phases=(
            PhaseResultView("execute", "completed", 1, 1, 7, 7, None),
            PhaseResultView("verify", "completed", 1, 1, 7, 7, None),
        ),
        bytes_done=7,
        bytes_total=7,
        error=None,
    )
    return SessionRecordView(
        session_id,
        PLAN_KIND,
        "completed",
        False,
        "2026-08-13T00:00:00+00:00",
        "2026-08-13T00:00:01+00:00",
        "2026-08-13T00:00:02+00:00",
        result,
    )


class _QuietRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        del format, args


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("transport", "off-origin"), required=True)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scenario", required=True, type=Path)
    return parser.parse_args()


def _read_scenario(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError("transport gate scenario must be an object")
    return value


def _runtime_identity() -> dict[str, object]:
    import namisync

    return {
        "executable": sys.executable,
        "namisync_file": str(Path(namisync.__file__).resolve()),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("namisync", "pywebview", "pythonnet")
        },
    }


def _test_spec(
    scenario: Mapping[str, object],
    recorder: _Recorder,
    *,
    off_origin_url: str | None,
    drain_probe: _DrainProbe | None,
    browser_gate: _BrowserGateControl | None,
):
    from namisync.interfaces.web.commands import (
        CommandAccess,
        CommandPayloadError,
        CommandRetry,
        CommandSpec,
        CommandTimeout,
        FieldRequirement,
    )

    def validate(payload: object) -> _Report:
        if type(payload) is not dict or type(payload.get("phase")) is not str:
            raise CommandPayloadError("test report payload is invalid")
        phase = payload["phase"]
        if phase == "hostile" and set(payload) == {"phase"}:
            return _Report(phase, MappingProxyType(dict(payload)))
        if phase in {
            "arm_start_uncertainty",
            "emit_gap",
            "interactive_failure",
            "status",
        } and set(payload) == {"phase"}:
            if browser_gate is None:
                raise CommandPayloadError("test report payload is invalid")
            return _Report(phase, MappingProxyType(dict(payload)))
        if phase == "browser_failure" and set(payload) == {
            "phase",
            "stage",
            "type",
        }:
            if (
                browser_gate is None
                or type(payload["stage"]) is not str
                or not payload["stage"]
                or len(payload["stage"]) > 64
                or type(payload["type"]) is not str
                or not payload["type"]
                or len(payload["type"]) > 64
            ):
                raise CommandPayloadError("test report payload is invalid")
            return _Report(phase, MappingProxyType(dict(payload)))
        if phase == "complete" and set(payload) == {
            "phase",
            "observed",
            "source_id",
            "target_id",
            "source_keys",
            "target_keys",
            "source_display",
            "target_display",
            "plan",
            "dom",
            "browser_gate",
        }:
            observed = payload["observed"]
            source_id = payload["source_id"]
            target_id = payload["target_id"]
            source_keys = payload["source_keys"]
            target_keys = payload["target_keys"]
            source_display = payload["source_display"]
            target_display = payload["target_display"]
            plan = payload["plan"]
            dom = payload["dom"]
            browser_report = payload["browser_gate"]
            if (
                type(observed) is str
                and type(source_id) is str
                and _SLOT_ID.fullmatch(source_id) is not None
                and type(target_id) is str
                and _SLOT_ID.fullmatch(target_id) is not None
                and source_keys == ["display", "id"]
                and target_keys == ["display", "id"]
                and type(source_display) is str
                and type(target_display) is str
                and type(plan) is dict
                and set(plan) == {"task_id", "request_id", "session_id"}
                and type(plan["task_id"]) is str
                and _TASK_ID.fullmatch(plan["task_id"]) is not None
                and type(plan["request_id"]) is str
                and _OPAQUE_ID.fullmatch(plan["request_id"]) is not None
                and type(plan["session_id"]) is str
                and _OPAQUE_ID.fullmatch(plan["session_id"]) is not None
                and type(dom) is dict
                and set(dom)
                == {
                    "element_children",
                    "script_count_before",
                    "script_count_after",
                    "image_count",
                    "hostile_marker_defined",
                }
                and all(
                    type(dom[name]) is int
                    for name in (
                        "element_children",
                        "script_count_before",
                        "script_count_after",
                        "image_count",
                    )
                )
                and type(dom["hostile_marker_defined"]) is bool
                and _valid_browser_report(browser_report)
            ):
                return _Report(phase, MappingProxyType(dict(payload)))
        if phase == "off_origin_target" and set(payload) == {"phase"}:
            return _Report(phase, MappingProxyType(dict(payload)))
        if phase == "off_origin_attempt" and set(payload) == {"phase"}:
            return _Report(phase, MappingProxyType(dict(payload)))
        if (
            phase == "drain_probe"
            and set(payload) == {"phase", "drain_settled"}
            and type(payload["drain_settled"]) is bool
            and drain_probe is not None
        ):
            return _Report(phase, MappingProxyType(dict(payload)))
        raise CommandPayloadError("test report payload is invalid")

    def report(value: object) -> object:
        if type(value) is not _Report:
            raise TypeError("test report received unvalidated data")
        if value.phase == "hostile":
            corpus = scenario.get("corpus")
            if type(corpus) is not str:
                raise ValueError("transport gate corpus is invalid")
            return {"corpus": corpus}
        if value.phase == "arm_start_uncertainty":
            assert browser_gate is not None
            with browser_gate.lock:
                browser_gate.arm_uncertain_start = True
            return {"accepted": True}
        if value.phase == "emit_gap":
            assert browser_gate is not None
            browser_gate.emit_gap()
            return {"accepted": True}
        if value.phase == "interactive_failure":
            assert browser_gate is not None
            with browser_gate.lock:
                browser_gate.interactive_failures += 1
            raise RuntimeError("injected interactive failure")
        if value.phase == "status":
            assert browser_gate is not None
            return browser_gate.status()
        if value.phase == "browser_failure":
            recorder.set("browser_failure", dict(value.value))
            recorder.write()
            return {"accepted": True}
        if value.phase == "complete":
            recorder.set("report", dict(value.value))
            recorder.write()
            return {"accepted": True}
        if value.phase == "off_origin_target":
            if off_origin_url is None:
                raise RuntimeError("off-origin server is unavailable")
            return {"url": off_origin_url}
        if value.phase == "drain_probe":
            assert drain_probe is not None
            evidence = {
                "drain_entered": drain_probe.entered.is_set(),
                "drain_exited": drain_probe.exited.is_set(),
                "drain_settled": value.value["drain_settled"],
            }
            recorder.set("drain_probe_report", evidence)
            recorder.write()
            return evidence
        recorder.append("off_origin_handler_calls", dict(value.value))
        recorder.write()
        return {"accepted": True}

    return CommandSpec(
        validate_payload=validate,
        handler=report,
        access=CommandAccess.READ_ONLY,
        command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN,
        timeout=CommandTimeout.INTERACTIVE,
        retry=CommandRetry.NONE,
    )


def _valid_browser_report(value: object) -> bool:
    if type(value) is not dict or set(value) != {
        "accepted_types",
        "accepted_sequences",
        "callback_release_order",
        "automatic_close_calls",
        "busy_refusals",
        "cleanup",
        "interactive_refusal",
        "malformed_refusal",
        "nested_dom",
        "nested_record",
        "replacement_registration",
    }:
        return False
    cleanup = value["cleanup"]
    nested_dom = value["nested_dom"]
    return (
        type(value["accepted_types"]) is list
        and all(type(item) is str for item in value["accepted_types"])
        and type(value["accepted_sequences"]) is list
        and all(type(item) is int for item in value["accepted_sequences"])
        and value["callback_release_order"] == ["record", "release"]
        and type(value["automatic_close_calls"]) is int
        and type(value["busy_refusals"]) is list
        and type(value["interactive_refusal"]) is dict
        and type(value["malformed_refusal"]) is dict
        and type(value["nested_record"]) is dict
        and value["replacement_registration"] is True
        and type(cleanup) is dict
        and set(cleanup) == {"active_timers", "ready_listeners"}
        and type(cleanup["active_timers"]) is int
        and type(cleanup["ready_listeners"]) is int
        and type(nested_dom) is dict
        and set(nested_dom)
        == {
            "element_children",
            "hostile_marker_defined",
            "image_count",
            "observed",
        }
        and type(nested_dom["observed"]) is str
        and type(nested_dom["element_children"]) is int
        and type(nested_dom["image_count"]) is int
        and type(nested_dom["hostile_marker_defined"]) is bool
    )


def _serve_second_origin(root: Path) -> tuple[ThreadingHTTPServer, str]:
    handler = partial(_QuietRequestHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(
        target=server.serve_forever,
        name="namisync-test-second-origin",
        daemon=True,
    )
    thread.start()
    port = int(server.server_address[1])
    return server, f"http://127.0.0.1:{port}/off_origin.html"


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.service import NamiSyncService
    from namisync.interfaces.web import bridge, host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    scenario = _read_scenario(arguments.scenario)
    recorder.set("runtime", _runtime_identity())
    recorder.set("off_origin_handler_calls", [])
    original_dispatcher = host._bridge_dispatcher
    original_expose_bridge = host._expose_bridge_api
    original_task_registry = host._task_registry
    original_dispatch = bridge.BridgeDispatcher.dispatch
    original_start_plan = NamiSyncService.start_plan
    original_reobserve = NamiSyncService.reobserve
    original_unsubscribe = NamiSyncService.unsubscribe
    original_close_session = NamiSyncService.close_session
    original_drop_plan = NamiSyncService.drop_plan
    original_log_renderer = host._log_startup_renderer
    original_pending_document = host._pending_document
    original_attach = bridge._NativeNavigationGuard.attach
    original_source_changed = bridge._NativeNavigationGuard._on_source_changed
    original_record_document = bridge.NativeDocumentState._record
    document_holder: dict[str, object] = {}
    drain_probe = _DrainProbe() if arguments.mode == "transport" else None
    browser_gate = (
        _BrowserGateControl(scenario)
        if arguments.mode == "transport"
        else None
    )
    second_origin: ThreadingHTTPServer | None = None
    off_origin_url: str | None = None
    if arguments.mode == "off-origin":
        second_origin, off_origin_url = _serve_second_origin(arguments.index.parent)

    def dispatcher(
        document: object,
        commands: object,
        startup_gate: object,
    ) -> object:
        production = dict(commands)
        recorder.set("production_command_names", sorted(production))
        combined = MappingProxyType(
            {
                **production,
                "test_report": _test_spec(
                    scenario,
                    recorder,
                    off_origin_url=off_origin_url,
                    drain_probe=drain_probe,
                    browser_gate=browser_gate,
                ),
            }
        )
        value = original_dispatcher(document, combined, startup_gate)
        recorder.set(
            "dispatcher_type",
            f"{type(value).__module__}.{type(value).__qualname__}",
        )
        recorder.set("combined_command_names", sorted(combined))
        recorder.set("combined_mapping_type", type(combined).__name__)
        return value

    def observed_dispatch(dispatcher: object, command_json: str) -> object:
        request = None
        if type(command_json) is str:
            try:
                candidate = json.loads(command_json)
            except Exception:
                candidate = None
            if type(candidate) is dict:
                request = candidate

        start_kind = None
        if (
            browser_gate is not None
            and request is not None
            and request.get("command") == "start_plan"
            and type(request.get("payload")) is dict
        ):
            start_kind = browser_gate.classify_uncertain_start(
                request["payload"].get("command_id")
            )
            if start_kind == "replay":
                browser_gate.uncertain_start_replay_entered.set()

        task_id = None
        if (
            browser_gate is not None
            and request is not None
            and request.get("command") == "next_events"
            and type(request.get("payload")) is dict
        ):
            task_id = request["payload"].get("task_id")
            role = browser_gate.role_for_task(task_id)
            if role == "busy":
                with browser_gate.lock:
                    inject_busy = (
                        browser_gate.busy_drain_refused
                        and not browser_gate.busy_bridge_refused
                    )
                    if inject_busy:
                        browser_gate.busy_bridge_refused = True
                if inject_busy:
                    response = dispatcher._failure(None, None, "bridge_busy")
                    recorder.append(
                        "injected_transport_faults",
                        {"role": role, "kind": "bridge_busy"},
                    )
                    recorder.append("raw_dispatch_bodies", command_json)
                    recorder.append(
                        "next_event_responses",
                        {"role": role, "kind": "bridge_busy"},
                    )
                    return response
            elif role == "malformed":
                with browser_gate.lock:
                    attempt = browser_gate.malformed_attempts
                    browser_gate.malformed_attempts += 1
                if attempt == 0:
                    response = {
                        "schema_version": 1,
                        "request_id": request.get("request_id"),
                        "ok": True,
                        "result": {
                            "task_id": "task-" + ("f" * 32),
                            "session_id": request["payload"].get("session_id"),
                            "drain_id": request["payload"].get("drain_id"),
                            "updates": [],
                        },
                    }
                    kind = "authority_mismatch"
                else:
                    response = None
                    kind = "malformed"
                recorder.append(
                    "injected_transport_faults",
                    {"role": role, "kind": kind, "attempt": attempt},
                )
                recorder.append("raw_dispatch_bodies", command_json)
                recorder.append(
                    "next_event_responses",
                    {"role": role, "kind": kind},
                )
                return response

        response = original_dispatch(dispatcher, command_json)
        if (
            browser_gate is not None
            and request is not None
            and request.get("command") == "start_plan"
            and type(response) is dict
            and response.get("ok") is True
            and type(response.get("result")) is dict
        ):
            result = response["result"]
            browser_gate.note_task(
                result.get("task_id"),
                result.get("session_id"),
            )
        if start_kind == "first":
            assert browser_gate is not None
            if not browser_gate.uncertain_start_replay_entered.wait(5):
                raise RuntimeError("start_plan uncertain replay did not enter")
        if (
            browser_gate is not None
            and request is not None
            and request.get("command") == "next_events"
            and type(request.get("payload")) is dict
            and browser_gate.role_for_task(task_id) == "main"
            and request["payload"].get("replay_from") is None
        ):
            with browser_gate.lock:
                hold_stale = not browser_gate.main_stale_response_held
                if hold_stale:
                    browser_gate.main_stale_response_held = True
            if hold_stale and not browser_gate.main_recovery_entered.wait(5):
                raise RuntimeError("stale drain recovery did not enter")
        if type(command_json) is str:
            recorder.append("raw_dispatch_bodies", command_json)
            if '"phase":"off_origin_attempt"' in command_json:
                recorder.set("off_origin_response", response)
                recorder.write()
        if request is not None and request.get("command") == "next_events":
            role = None if browser_gate is None else browser_gate.role_for_task(task_id)
            kind = "success"
            if type(response) is dict and response.get("ok") is False:
                error = response.get("error")
                if type(error) is dict and type(error.get("code")) is str:
                    kind = error["code"]
            recorder.append(
                "next_event_responses",
                {"role": role, "kind": kind},
            )
        return response

    def expose_bridge(window: object, dispatcher: object) -> None:
        original_expose_bridge(window, dispatcher)
        recorder.set("pywebview_js_api_is_none", window._js_api is None)
        recorder.set("pywebview_function_names", sorted(window._functions))

    def record_document(document: object, current_url: str) -> None:
        recorder.append("document_records", current_url)
        original_record_document(document, current_url)

    def task_registry(service: object) -> object:
        registry = original_task_registry(service)
        if drain_probe is None:
            return registry
        original_drain = registry.drain
        original_release = registry.release_terminal_session
        original_close_task = registry.close_task

        def observed_drain(
            task_id: str,
            session_id: str,
            drain_id: str,
            *,
            replay_from: int | None,
        ) -> object:
            is_concurrency_probe = session_id == "b" * 32
            role = None if browser_gate is None else browser_gate.role_for_task(task_id)
            if browser_gate is not None and role is not None:
                with browser_gate.lock:
                    browser_gate.drain_cursors.append(
                        {
                            "role": role,
                            "replay_from": replay_from,
                        }
                    )
                if role == "main" and replay_from == 1:
                    browser_gate.main_recovery_entered.set()
                if role == "busy":
                    with browser_gate.lock:
                        inject_drain_busy = not browser_gate.busy_drain_refused
                        if inject_drain_busy:
                            browser_gate.busy_drain_refused = True
                    if inject_drain_busy:
                        from namisync.interfaces.web.drain import DrainBusyError

                        raise DrainBusyError("injected headed drain contention")
            if is_concurrency_probe:
                drain_probe.entered.set()
                recorder.set("drain_entered", True)
                recorder.write()
            try:
                result = original_drain(
                    task_id,
                    session_id,
                    drain_id,
                    replay_from=replay_from,
                )
            except BaseException as error:
                if is_concurrency_probe:
                    recorder.set(
                        "drain_exit",
                        {"type": type(error).__name__, "message": str(error)},
                    )
                raise
            else:
                if is_concurrency_probe:
                    recorder.set(
                        "drain_exit",
                        {"type": "return", "update_count": len(result.updates)},
                    )
                return result
            finally:
                if is_concurrency_probe:
                    drain_probe.exited.set()
                    recorder.set("drain_exited", True)
                    recorder.write()

        def release_terminal_session(task_id: str, session_id: str) -> object:
            if browser_gate is not None and browser_gate.is_controlled_session(
                session_id
            ):
                with browser_gate.lock:
                    browser_gate.registry_release_calls.append(
                        [task_id, session_id]
                    )
            return original_release(task_id, session_id)

        def close_task(task_id: str, session_id: str) -> object:
            if browser_gate is not None and browser_gate.is_controlled_session(
                session_id
            ):
                with browser_gate.lock:
                    browser_gate.registry_close_calls.append(
                        [task_id, session_id]
                    )
            return original_close_task(task_id, session_id)

        registry.drain = observed_drain  # type: ignore[method-assign]
        registry.release_terminal_session = release_terminal_session  # type: ignore[method-assign]
        registry.close_task = close_task  # type: ignore[method-assign]
        return registry

    def start_plan(
        service: object,
        source: str,
        target: str,
        *,
        deletion_policy: str | None = None,
        command_id: str | None = None,
        observation_sink=None,
    ) -> object:
        recorder.append(
            "service_start_plan_calls",
            {
                "source": source,
                "target": target,
                "deletion_policy": deletion_policy,
                "command_id": command_id,
            },
        )
        if deletion_policy == "trash" and browser_gate is not None:
            role, request_id, session_id = browser_gate.start_controlled(
                observation_sink
            )
            recorder.append(
                "controlled_plan_roles",
                {
                    "role": role,
                    "request_id": request_id,
                    "session_id": session_id,
                },
            )
            from namisync.interfaces.service import PlanSession

            return PlanSession(request_id, session_id)
        if deletion_policy == "additive":
            from namisync.interfaces.service import PlanSession

            recorder.set("controlled_plan_session", "b" * 32)
            return PlanSession("a" * 32, "b" * 32)
        return original_start_plan(
            service,
            source,
            target,
            deletion_policy=deletion_policy,
            command_id=command_id,
            observation_sink=observation_sink,
        )

    def reobserve(
        service: object,
        session_id: str,
        sink: object,
        from_sequence: int,
    ) -> object:
        if browser_gate is not None and session_id == browser_gate.controlled_session(
            "busy"
        )[1]:
            if from_sequence != 1:
                raise RuntimeError("unexpected busy browser gate replay cursor")
            return _terminal_record(session_id, browser_gate.hostile)
        if browser_gate is not None and session_id == browser_gate.controlled_session(
            "main"
        )[1]:
            with browser_gate.lock:
                browser_gate.sinks["main"] = sink
            if from_sequence == 1:
                _deliver_initial_events(sink, session_id)
                return _nonterminal_record(session_id)
            if from_sequence == 4:
                sink(_event(session_id, 4, "Gap", {"first_missed_seq": 4}))
                sink(
                    _event(
                        session_id,
                        5,
                        "PhaseChanged",
                        {"phase": "retained-海"},
                    )
                )
                return _terminal_record(session_id, browser_gate.hostile)
            raise RuntimeError("unexpected main browser gate replay cursor")
        return original_reobserve(service, session_id, sink, from_sequence)

    def unsubscribe(service: object, session_id: str) -> None:
        if session_id == "b" * 32 or (
            browser_gate is not None
            and browser_gate.is_controlled_session(session_id)
        ):
            recorder.append(
                "controlled_service_cleanup",
                ["unsubscribe", session_id],
            )
            return
        original_unsubscribe(service, session_id)

    def close_session(service: object, session_id: str) -> None:
        if browser_gate is not None and browser_gate.is_controlled_session(
            session_id
        ):
            recorder.append(
                "controlled_service_cleanup",
                ["close_session", session_id],
            )
            return
        original_close_session(service, session_id)

    def drop_plan(service: object, request_id: str) -> None:
        controlled_requests = (
            set()
            if browser_gate is None
            else {
                browser_gate.controlled_session(role)[0]
                for role in ("main", "busy", "malformed")
            }
        )
        if request_id in controlled_requests:
            recorder.append(
                "controlled_service_cleanup",
                ["drop_plan", request_id],
            )
            return
        original_drop_plan(service, request_id)

    def log_renderer(browser_version: str) -> None:
        recorder.set("native_browser_version", browser_version)
        original_log_renderer(browser_version)

    def pending_document() -> object:
        document = original_pending_document()
        document_holder["value"] = document
        return document

    def attach(guard: object, core: object) -> None:
        original_attach(guard, core)
        if arguments.mode == "off-origin":
            core.NavigationStarting -= guard._on_navigation_starting
            recorder.set("navigation_starting_removed", True)

    def source_changed(guard: object, sender: object, event_args: object) -> None:
        original_source_changed(guard, sender, event_args)
        recorder.append("committed_sources", str(sender.Source))

    with ExitStack() as stack:
        stack.enter_context(patch.object(host, "_bridge_dispatcher", dispatcher))
        stack.enter_context(
            patch.object(host, "_expose_bridge_api", expose_bridge)
        )
        stack.enter_context(
            patch.object(bridge.BridgeDispatcher, "dispatch", observed_dispatch)
        )
        stack.enter_context(
            patch.object(bridge.NativeDocumentState, "_record", record_document)
        )
        stack.enter_context(patch.object(host, "_task_registry", task_registry))
        stack.enter_context(patch.object(host, "_pending_document", pending_document))
        stack.enter_context(patch.object(host, "_log_startup_renderer", log_renderer))
        if arguments.mode == "transport":
            stack.enter_context(
                patch.object(NamiSyncService, "start_plan", start_plan)
            )
            stack.enter_context(
                patch.object(NamiSyncService, "reobserve", reobserve)
            )
            stack.enter_context(
                patch.object(NamiSyncService, "unsubscribe", unsubscribe)
            )
            stack.enter_context(
                patch.object(NamiSyncService, "close_session", close_session)
            )
            stack.enter_context(
                patch.object(NamiSyncService, "drop_plan", drop_plan)
            )
        elif arguments.mode == "off-origin":
            stack.enter_context(
                patch.object(bridge._NativeNavigationGuard, "attach", attach)
            )
            stack.enter_context(
                patch.object(
                    bridge._NativeNavigationGuard,
                    "_on_source_changed",
                    source_changed,
                )
            )
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
            index_path=arguments.index,
        )

    if second_origin is not None:
        second_origin.shutdown()
        second_origin.server_close()
    document = document_holder.get("value")
    if document is not None:
        lock = document._lock
        with lock:
            recorder.set("final_document_url", str(document._current_url))
    if browser_gate is not None:
        with browser_gate.lock:
            recorder.set(
                "browser_gate_server",
                {
                    "drain_cursors": list(browser_gate.drain_cursors),
                    "registry_release_calls": list(
                        browser_gate.registry_release_calls
                    ),
                    "registry_close_calls": list(browser_gate.registry_close_calls),
                    "interactive_failures": browser_gate.interactive_failures,
                    "malformed_attempts": browser_gate.malformed_attempts,
                },
            )
    recorder.set("exit_code", exit_code)
    recorder.write()
    return exit_code


def main() -> int:
    arguments = _parse_arguments()
    recorder = _Recorder(arguments.output, arguments.mode)
    try:
        return _run(arguments, recorder)
    except BaseException as error:
        recorder.set(
            "child_failure",
            {"type": type(error).__name__, "message": str(error)},
        )
        recorder.write()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
