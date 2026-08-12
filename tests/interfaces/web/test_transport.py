"""Ordinary BR-G-32 evidence for the strict bridge transport boundary."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from threading import Event, Lock, Thread
from types import SimpleNamespace

import pytest

import namisync.interfaces.web.bridge as bridge_module
from namisync.interfaces.service import NamiSyncService
from namisync.interfaces.web.bridge import BRIDGE_SCHEMA_VERSION, BridgeDispatcher
from namisync.interfaces.web.commands import (
    CommandAccess,
    CommandConflictError,
    CommandPayloadError,
    CommandRetry,
    CommandSpec,
    CommandTimeout,
    FieldRequirement,
    PickerUnavailableError,
    PlanningRefusedError,
)
from namisync.interfaces.web.commands import production_command_specs
from namisync.interfaces.web.slots import FolderSlotTable, SlotUnavailableError


REQUEST_ID = "a1" * 16
ERRORS = {
    "invalid_request": "The desktop request is invalid.",
    "unsupported_version": (
        "Restart NamiSync to load a compatible desktop page."
    ),
    "unknown_command": "This desktop action is not available.",
    "invalid_payload": "The desktop action contains invalid data.",
    "request_too_large": "The desktop request is too large.",
    "slot_unavailable": (
        "That folder selection is no longer available. Choose both folders again."
    ),
    "picker_unavailable": "The folder picker could not open. Try again.",
    "command_conflict": (
        "This action no longer matches its first attempt. Start the action again."
    ),
    "planning_refused": (
        "NamiSync could not start a plan for those folders. Review both folders "
        "and try again."
    ),
    "bridge_unavailable": (
        "NamiSync is closing or this desktop page is no longer trusted."
    ),
    "internal_error": "NamiSync could not complete the desktop action.",
}


class _Document:
    def __init__(self, *, trusted: bool = True) -> None:
        self.trusted = trusted
        self.checks = 0

    def require_trusted(self) -> None:
        self.checks += 1
        if not self.trusted:
            raise PermissionError("private origin detail")


class _UntouchableBody:
    def __init__(self) -> None:
        self.touched: list[str] = []

    def __str__(self) -> str:
        self.touched.append("str")
        raise AssertionError("body was stringified")

    def __len__(self) -> int:
        self.touched.append("len")
        raise AssertionError("body length was read")

    def encode(self, *args: object, **kwargs: object) -> bytes:
        del args, kwargs
        self.touched.append("encode")
        raise AssertionError("body was encoded")


def _spec(handler, validator=lambda payload: payload) -> CommandSpec:
    return CommandSpec(
        validate_payload=validator,
        handler=handler,
        access=CommandAccess.READ_ONLY,
        command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN,
        timeout=CommandTimeout.INTERACTIVE,
        retry=CommandRetry.NONE,
    )


def _request(
    *,
    request_id: object = REQUEST_ID,
    schema_version: object = BRIDGE_SCHEMA_VERSION,
    command: object = "probe",
    payload: object = None,
) -> str:
    if payload is None:
        payload = {}
    return json.dumps(
        {
            "schema_version": schema_version,
            "request_id": request_id,
            "command": command,
            "payload": payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _failure(request_id: str | None, code: str, message: str) -> dict[str, object]:
    return {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": request_id,
        "ok": False,
        "error": {"code": code, "message": message},
    }


def test_br_g_32_python_and_browser_error_vocabularies_are_exact() -> None:
    browser_source = (
        Path(bridge_module.__file__).parent / "assets" / "bridge.js"
    ).read_text(encoding="utf-8")

    assert bridge_module._ERROR_MESSAGES == ERRORS
    for code, message in ERRORS.items():
        assert f"{code}:" in browser_source
        assert message in browser_source


def test_br_g_32_success_envelope_is_exact_and_encodes_before_return() -> None:
    dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(lambda payload: {"seen": payload["value"]})},
    )

    response = dispatcher.dispatch(_request(payload={"value": "wave \U0001f30a"}))

    assert response == {
        "schema_version": 1,
        "request_id": REQUEST_ID,
        "ok": True,
        "result": {"seen": "wave \U0001f30a"},
    }


def test_br_g_32_dispatcher_snapshots_command_specs_at_construction() -> None:
    commands = {"probe": _spec(lambda payload: payload)}
    dispatcher = BridgeDispatcher(document=_Document(), commands=commands)
    commands.clear()

    assert dispatcher.dispatch(_request()) == {
        "schema_version": 1,
        "request_id": REQUEST_ID,
        "ok": True,
        "result": {},
    }


def test_br_g_32_dispatcher_snapshots_before_validating_adversarial_mapping() -> None:
    spec = _spec(lambda payload: payload)

    class ShiftingMapping(dict):
        def __iter__(self):
            return iter(("probe",))

        def __getitem__(self, key: object) -> object:
            del key
            value = self.get("current", spec)
            self["current"] = lambda payload: payload
            return value

        def keys(self):
            return ("probe",)

    dispatcher = BridgeDispatcher(
        document=_Document(),
        commands=ShiftingMapping(),
    )

    assert dispatcher.dispatch(_request())["ok"] is True


@pytest.mark.parametrize(
    ("body", "expected_id", "code", "message"),
    [
        (7, None, "invalid_request", "The desktop request is invalid."),
        ("{", None, "invalid_request", "The desktop request is invalid."),
        (
            '{"schema_version":1,"request_id":"'
            + REQUEST_ID
            + '","command":"probe","command":"probe","payload":{}}',
            None,
            "invalid_request",
            "The desktop request is invalid.",
        ),
        ("\ud800", None, "invalid_request", "The desktop request is invalid."),
        (
            _request(request_id="A" * 32),
            None,
            "invalid_request",
            "The desktop request is invalid.",
        ),
        (
            json.dumps(
                {
                    "schema_version": 1,
                    "request_id": REQUEST_ID,
                    "command": "probe",
                    "payload": {},
                    "extra": True,
                }
            ),
            REQUEST_ID,
            "invalid_request",
            "The desktop request is invalid.",
        ),
        (
            json.dumps({"request_id": REQUEST_ID}),
            REQUEST_ID,
            "invalid_request",
            "The desktop request is invalid.",
        ),
        (
            _request(schema_version=2),
            REQUEST_ID,
            "unsupported_version",
            "Restart NamiSync to load a compatible desktop page.",
        ),
        (
            _request(command="not_allowed"),
            REQUEST_ID,
            "unknown_command",
            "This desktop action is not available.",
        ),
        (
            _request(payload=[]),
            REQUEST_ID,
            "invalid_payload",
            "The desktop action contains invalid data.",
        ),
        (
            json.dumps(
                {
                    "schema_version": 1,
                    "request_id": REQUEST_ID,
                    "command": "probe",
                    "payload": {"value": "\ud800"},
                }
            ),
            REQUEST_ID,
            "invalid_payload",
            "The desktop action contains invalid data.",
        ),
    ],
)
def test_br_g_32_strict_prehandler_refusal_matrix_returns_exact_envelopes(
    body: object,
    expected_id: str | None,
    code: str,
    message: str,
) -> None:
    handled: list[object] = []
    dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(handled.append)},
    )

    assert dispatcher.dispatch(body) == _failure(expected_id, code, message)  # type: ignore[arg-type]
    assert handled == []


def test_br_g_32_payload_validator_refuses_before_handler_effects() -> None:
    handled: list[object] = []

    def refuse(payload: object) -> object:
        del payload
        raise CommandPayloadError("private payload detail")

    dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(handled.append, refuse)},
    )

    assert dispatcher.dispatch(_request()) == _failure(
        REQUEST_ID,
        "invalid_payload",
        "The desktop action contains invalid data.",
    )
    assert handled == []


@pytest.mark.parametrize(
    "payload",
    [
        {"bad\ud800key": "value"},
        {"nested": {"bad\ud800key": "value"}},
    ],
)
def test_br_g_32_surrogate_payload_keys_are_refused_before_handler(
    payload: object,
) -> None:
    handled: list[object] = []
    dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(handled.append)},
    )

    body = json.dumps(
        {
            "schema_version": 1,
            "request_id": REQUEST_ID,
            "command": "probe",
            "payload": payload,
        }
    )
    assert dispatcher.dispatch(body) == _failure(
        REQUEST_ID,
        "invalid_payload",
        "The desktop action contains invalid data.",
    )
    assert handled == []


def _node_executable() -> Path | None:
    installed = shutil.which("node")
    if installed is not None:
        return Path(installed)
    for raw_entry in os.environ.get("PATH", "").split(os.pathsep):
        if not raw_entry:
            continue
        entry = Path(raw_entry)
        if entry.name.casefold() == "override" and len(entry.parents) >= 2:
            candidate = entry.parents[1] / "node" / "bin" / "node.exe"
            if candidate.is_file():
                return candidate
        if entry.name.casefold() == "resources":
            candidate = entry / "cua_node" / "bin" / "node.exe"
            if candidate.is_file():
                return candidate
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    known_bundled = (
        program_files / "Adobe" / "Adobe Creative Cloud Experience" / "libs" / "node.exe",
        program_files
        / "Common Files"
        / "Adobe"
        / "Creative Cloud Libraries"
        / "libs"
        / "node.exe",
    )
    for candidate in known_bundled:
        if candidate.is_file():
            return candidate
    windows_apps = program_files / "WindowsApps"
    try:
        candidates = sorted(
            windows_apps.glob(
                "OpenAI.Codex_*_x64__*"
                "/app/resources/cua_node/bin/node.exe"
            ),
            reverse=True,
        )
    except OSError:
        return None
    return candidates[0] if candidates else None


def test_br_g_32_timed_out_pre_ready_attempt_cannot_dispatch_later() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the no-dependency bridge probe")
    probe = Path(__file__).parents[2] / "assets" / "bridge_timeout_probe.mjs"
    bridge = Path(bridge_module.__file__).parent / "assets" / "bridge.js"

    completed = subprocess.run(
        [str(node), str(probe), str(bridge)],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_br_g_32_interactive_wrapper_is_neutral_bounded_and_single_attempt() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the no-dependency bridge probe")
    probe = Path(__file__).parents[2] / "assets" / "bridge_interactive_probe.mjs"
    bridge = Path(bridge_module.__file__).parent / "assets" / "bridge.js"

    completed = subprocess.run(
        [str(node), str(probe), str(bridge)],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_br_g_32_neutral_wrapper_cannot_authorize_a_test_command() -> None:
    commands = production_command_specs(
        picker=lambda: None,
        slots=SimpleNamespace(),
        service=SimpleNamespace(),
    )
    dispatcher = BridgeDispatcher(document=_Document(), commands=commands)

    assert dispatcher.dispatch(_request(command="test_report")) == _failure(
        REQUEST_ID,
        "unknown_command",
        "This desktop action is not available.",
    )


def test_br_g_32_utf8_limit_is_inclusive_and_oversize_is_predecode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handled: list[object] = []
    dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(handled.append)},
    )
    empty = _request(payload={"value": ""})
    wave = "\U0001f30a"
    padding = "a" * (65_536 - len(empty.encode("utf-8")) - len(wave.encode("utf-8")))
    at_limit = _request(payload={"value": padding + wave})
    assert len(at_limit.encode("utf-8")) == 65_536

    response = dispatcher.dispatch(at_limit)

    assert response["ok"] is True
    assert handled == [{"value": padding + wave}]

    original_loads = bridge_module.json.loads
    decoded = 0

    def observed_loads(*args: object, **kwargs: object):
        nonlocal decoded
        decoded += 1
        return original_loads(*args, **kwargs)

    monkeypatch.setattr(bridge_module.json, "loads", observed_loads)
    over_limit = at_limit[:-2] + "b" + at_limit[-2:]
    assert len(over_limit.encode("utf-8")) == 65_537

    assert dispatcher.dispatch(over_limit) == _failure(
        None,
        "request_too_large",
        "The desktop request is too large.",
    )
    assert decoded == 0
    assert len(handled) == 1


def test_br_g_32_handler_and_codec_failures_are_sanitized_and_logs_are_private(
    caplog: pytest.LogCaptureFixture,
) -> None:
    body_secret = r"C:\Users\Someone\secret payload.txt"
    exception_secret = r"D:\private\handler traceback sentinel"
    caplog.set_level(logging.INFO, logger="namisync")

    def fail_handler(payload: object) -> object:
        assert payload == {"sentinel": body_secret}
        raise RuntimeError(exception_secret)

    handler_dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(fail_handler)},
    )
    codec_dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(lambda payload: Path(exception_secret))},
    )

    expected = _failure(
        REQUEST_ID,
        "internal_error",
        "NamiSync could not complete the desktop action.",
    )
    assert handler_dispatcher.dispatch(
        _request(payload={"sentinel": body_secret})
    ) == expected
    assert codec_dispatcher.dispatch(_request()) == expected
    combined = repr(expected) + "\n" + caplog.text
    assert body_secret not in combined
    assert exception_secret not in combined
    assert "traceback" not in caplog.text.lower()
    assert f"request_id={REQUEST_ID}" in caplog.text
    assert "command=probe" in caplog.text
    assert "code=internal_error" in caplog.text


def test_br_g_32_base_exceptions_cannot_cross_handler_or_codec_boundary() -> None:
    class ExitMapping(dict):
        def items(self):
            raise SystemExit("private codec termination detail")

    handler_dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={
            "probe": _spec(
                lambda payload: (_ for _ in ()).throw(
                    SystemExit("private handler termination detail")
                )
            )
        },
    )
    codec_dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(lambda payload: ExitMapping())},
    )

    expected = _failure(
        REQUEST_ID,
        "internal_error",
        ERRORS["internal_error"],
    )
    assert handler_dispatcher.dispatch(_request()) == expected
    assert codec_dispatcher.dispatch(_request()) == expected


def test_br_g_32_picker_failure_uses_its_fixed_public_error() -> None:
    def fail_picker(payload: object) -> object:
        del payload
        raise PickerUnavailableError("private native picker text")

    dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(fail_picker)},
    )

    assert dispatcher.dispatch(_request()) == _failure(
        REQUEST_ID,
        "picker_unavailable",
        "The folder picker could not open. Try again.",
    )


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (SlotUnavailableError("private slot"), "slot_unavailable"),
        (CommandConflictError("private receipt"), "command_conflict"),
        (PlanningRefusedError("C:\\private\\root"), "planning_refused"),
    ],
)
def test_br_g_32_typed_command_refusals_use_only_fixed_public_errors(
    error: Exception,
    code: str,
) -> None:
    def refuse(payload: object) -> object:
        del payload
        raise error

    dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(refuse)},
    )

    assert dispatcher.dispatch(_request()) == _failure(
        REQUEST_ID,
        code,
        ERRORS[code],
    )


def test_br_g_32_incidental_value_error_remains_internal_error() -> None:
    def fail(payload: object) -> object:
        del payload
        raise ValueError("private incidental defect")

    dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(fail)},
    )

    assert dispatcher.dispatch(_request()) == _failure(
        REQUEST_ID,
        "internal_error",
        ERRORS["internal_error"],
    )


def test_br_g_32_start_plan_receipt_binds_resolved_intent_not_slot_ids(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    changed_source = tmp_path / "changed-source"
    source.mkdir()
    target.mkdir()
    changed_source.mkdir()

    class Runtime:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, str | None]] = []

        def create_plan_request(
            self,
            request_id: str,
            source_path: str,
            target_path: str,
            *,
            deletion_policy: str | None,
        ) -> object:
            self.calls.append((source_path, target_path, deletion_policy))
            return SimpleNamespace(request_id=request_id)

    class Dispatcher:
        def __init__(self) -> None:
            self.submissions: list[object] = []

        def submit(self, kind: str, request: object) -> str:
            del kind
            self.submissions.append(request)
            return "5" * 32

    runtime = Runtime()
    service = object.__new__(NamiSyncService)
    service._runtime = runtime
    service._dispatcher = Dispatcher()
    service._lock = Lock()
    service._session_receipts = {}
    service._receipt_ids_by_session = {}
    service._session_receipt_locks = tuple(Lock() for _ in range(64))
    service._session_receipt_lifecycle = Lock()
    service._closed = False

    tokens = iter(f"{value:032x}" for value in range(10))
    slots = FolderSlotTable(token=lambda: next(tokens))
    source_id, _ = slots.store(str(source), purpose="source")
    target_id, _ = slots.store(str(target), purpose="target")
    replay_source_id, _ = slots.store(str(source), purpose="source")
    replay_target_id, _ = slots.store(str(target), purpose="target")
    changed_source_id, _ = slots.store(str(changed_source), purpose="source")
    commands = production_command_specs(
        picker=lambda: None,
        slots=slots,
        service=service,
    )
    dispatcher = BridgeDispatcher(document=_Document(), commands=commands)
    command_id = "c4" * 16

    first = dispatcher.dispatch(
        _request(
            request_id="d1" * 16,
            command="start_plan",
            payload={
                "command_id": command_id,
                "source_id": source_id,
                "target_id": target_id,
                "deletion_policy": None,
            },
        )
    )
    replay = dispatcher.dispatch(
        _request(
            request_id="d2" * 16,
            command="start_plan",
            payload={
                "command_id": command_id,
                "source_id": replay_source_id,
                "target_id": replay_target_id,
                "deletion_policy": None,
            },
        )
    )

    assert first["request_id"] == "d1" * 16
    assert replay["request_id"] == "d2" * 16
    assert first["result"] == replay["result"]
    assert first["result"] == {
        "request_id": first["result"]["request_id"],
        "session_id": "5" * 32,
    }
    assert runtime.calls == [(str(source), str(target), None)]
    assert len(service._dispatcher.submissions) == 1

    changed_root = dispatcher.dispatch(
        _request(
            request_id="d3" * 16,
            command="start_plan",
            payload={
                "command_id": command_id,
                "source_id": changed_source_id,
                "target_id": target_id,
                "deletion_policy": None,
            },
        )
    )
    changed_policy = dispatcher.dispatch(
        _request(
            request_id="d4" * 16,
            command="start_plan",
            payload={
                "command_id": command_id,
                "source_id": source_id,
                "target_id": target_id,
                "deletion_policy": "trash",
            },
        )
    )

    assert changed_root == _failure(
        "d3" * 16,
        "command_conflict",
        ERRORS["command_conflict"],
    )
    assert changed_policy == _failure(
        "d4" * 16,
        "command_conflict",
        ERRORS["command_conflict"],
    )
    assert runtime.calls == [(str(source), str(target), None)]


def test_br_g_32_origin_and_close_refusals_do_not_inspect_untrusted_body() -> None:
    off_origin_body = _UntouchableBody()
    off_origin = BridgeDispatcher(
        document=_Document(trusted=False),
        commands={"probe": _spec(lambda payload: payload)},
    )

    assert off_origin.dispatch(off_origin_body) == _failure(
        None,
        "bridge_unavailable",
        "NamiSync is closing or this desktop page is no longer trusted.",
    )
    assert off_origin_body.touched == []

    closing_body = _UntouchableBody()
    closing = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(lambda payload: payload)},
    )
    closing._reject_new()
    assert closing.dispatch(closing_body) == _failure(
        None,
        "bridge_unavailable",
        "NamiSync is closing or this desktop page is no longer trusted.",
    )
    assert closing_body.touched == []


def test_br_g_32_admitted_call_finishes_while_close_refuses_new_body() -> None:
    entered = Event()
    release = Event()
    finished = Event()
    response: list[object] = []

    def admitted_handler(payload: object) -> object:
        entered.set()
        assert release.wait(1.0)
        return payload

    dispatcher = BridgeDispatcher(
        document=_Document(),
        commands={"probe": _spec(admitted_handler)},
    )
    worker = Thread(
        target=lambda: (response.append(dispatcher.dispatch(_request())), finished.set())
    )
    worker.start()
    assert entered.wait(1.0)

    dispatcher._reject_new()
    rejected_body = _UntouchableBody()
    assert dispatcher.dispatch(rejected_body) == _failure(
        None,
        "bridge_unavailable",
        "NamiSync is closing or this desktop page is no longer trusted.",
    )
    assert rejected_body.touched == []
    assert not finished.is_set()

    release.set()
    worker.join(1.0)
    assert not worker.is_alive()
    assert response == [
        {
            "schema_version": 1,
            "request_id": REQUEST_ID,
            "ok": True,
            "result": {},
        }
    ]
    dispatcher._wait_for_handlers()
