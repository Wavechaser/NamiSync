"""Bridge transport evidence plus optional supplemental Node.js probes."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic
from types import SimpleNamespace

import pytest

import namisync.interfaces.web.bridge as bridge_module
from namisync.interfaces.service import NamiSyncService
from namisync.interfaces.web.bridge import (
    AdmissionGranted,
    AdmissionRefused,
    BRIDGE_SCHEMA_VERSION,
    BridgeDispatcher,
)
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
from namisync.interfaces.web.readiness import CommandPhase, ReadinessContext
from namisync.interfaces.web.drain import (
    TaskCloseView,
    TaskDrainView,
    TaskEventUpdateView,
    TaskRecordUpdateView,
    TaskSessionReleaseView,
    TaskStartView,
)
from namisync.interfaces.web.drain import (
    DrainBusyError,
    ObservationConflictError,
    TaskUnavailableError,
)
from namisync.interfaces.web.slots import FolderSlotTable, SlotUnavailableError
from namisync.workflows import PLAN_KIND
from namisync.workflows.views import SessionEventView, SessionRecordView
from tests.interfaces.web._public_view_witnesses import (
    INVALID_RETURN_WITNESSES,
    PublicViewWitness,
    iter_public_view_witnesses,
)
from _frontend_test_support import _node_executable


REQUEST_ID = "a1" * 16
OPEN_CONTEXT = ReadinessContext(CommandPhase.OPEN, 0)
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
    "task_unavailable": "That desktop task is no longer available.",
    "drain_busy": (
        "That desktop task already has an event request in progress."
    ),
    "observation_conflict": (
        "That desktop task is already observing different work."
    ),
    "bridge_busy": "NamiSync is busy. Try this action again.",
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


def _spec(
    handler,
    validator=lambda payload: payload,
    *,
    phase: CommandPhase = CommandPhase.OPEN,
) -> CommandSpec:
    return CommandSpec(
        validate_payload=validator,
        handler=handler,
        access=CommandAccess.READ_ONLY,
        command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN,
        timeout=CommandTimeout.INTERACTIVE,
        retry=CommandRetry.NONE,
        phase=phase,
    )


def _admit_open(_name: str) -> object:
    return AdmissionGranted(OPEN_CONTEXT)


def _bridge_dispatcher(
    *,
    document: object,
    commands: object,
    admit=_admit_open,
) -> BridgeDispatcher:
    return BridgeDispatcher(
        document=document,
        commands=commands,
        admit=admit,
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
    dispatcher = _bridge_dispatcher(
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


def test_startup_command_is_the_only_dispatch_admitted_before_open() -> None:
    opened = False
    generation = 3
    calls: list[str] = []
    commands = {
        "shell_ready": _spec(
            lambda invocation: calls.append(
                f"shell:{invocation.generation}"
            )
            or {"acknowledged": True},
            phase=CommandPhase.BOOTSTRAP,
        ),
        "probe": _spec(lambda _payload: calls.append("probe") or "open"),
    }

    def admit(name: str) -> object:
        phase = CommandPhase.OPEN if opened else CommandPhase.BOOTSTRAP
        if commands[name].phase is not phase:
            return AdmissionRefused()
        return AdmissionGranted(ReadinessContext(phase, generation))

    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands=commands,
        admit=admit,
    )

    assert dispatcher.dispatch(_request(command="probe")) == _failure(
        REQUEST_ID,
        "bridge_unavailable",
        ERRORS["bridge_unavailable"],
    )
    assert calls == []
    assert dispatcher.dispatch(_request(command="shell_ready")) == {
        "schema_version": 1,
        "request_id": REQUEST_ID,
        "ok": True,
        "result": {"acknowledged": True},
    }
    assert calls == ["shell:3"]

    opened = True
    assert dispatcher.dispatch(_request(command="probe"))["ok"] is True
    assert dispatcher.dispatch(_request(command="shell_ready")) == _failure(
        REQUEST_ID,
        "bridge_unavailable",
        ERRORS["bridge_unavailable"],
    )
    assert calls == ["shell:3", "probe"]


def test_dispatcher_requires_a_command_admission_callback() -> None:
    with pytest.raises(TypeError, match="missing 1 required keyword-only argument"):
        BridgeDispatcher(
            document=_Document(),
            commands={
                "shell_ready": _spec(
                    lambda payload: payload,
                    phase=CommandPhase.BOOTSTRAP,
                )
            },
        )
    with pytest.raises(TypeError, match="command admission must be callable"):
        BridgeDispatcher(
            document=_Document(),
            commands={},
            admit=None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "readiness",
    [None, 1, "yes", AdmissionGranted(object())],
)
def test_invalid_or_failed_admission_callback_fails_closed(
    readiness: object,
) -> None:
    def admit(_name: str) -> object:
        if readiness is None:
            raise RuntimeError("injected readiness failure")
        return readiness

    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={
            "shell_ready": _spec(
                lambda payload: payload,
                phase=CommandPhase.BOOTSTRAP,
            ),
            "probe": _spec(lambda payload: payload),
        },
        admit=admit,
    )

    for command in ("shell_ready", "probe"):
        assert dispatcher.dispatch(_request(command=command)) == _failure(
            REQUEST_ID,
            "bridge_unavailable",
            ERRORS["bridge_unavailable"],
        )


def test_unknown_command_does_not_consult_composition_admission() -> None:
    admission_calls: list[str] = []
    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={"probe": _spec(lambda payload: payload)},
        admit=lambda name: admission_calls.append(name)
        or AdmissionGranted(OPEN_CONTEXT),
    )

    assert dispatcher.dispatch(_request(command="not_allowed")) == _failure(
        REQUEST_ID,
        "unknown_command",
        ERRORS["unknown_command"],
    )
    assert admission_calls == []


def test_refused_admission_precedes_payload_and_validator_inspection() -> None:
    validated: list[object] = []
    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={"probe": _spec(lambda payload: payload, validated.append)},
        admit=lambda _name: AdmissionRefused(),
    )

    assert dispatcher.dispatch(_request(payload=[])) == _failure(
        REQUEST_ID,
        "bridge_unavailable",
        ERRORS["bridge_unavailable"],
    )
    assert validated == []


def test_mismatched_admitted_context_precedes_command_validation() -> None:
    validated: list[object] = []
    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={"probe": _spec(lambda payload: payload, validated.append)},
        admit=lambda _name: AdmissionGranted(
            ReadinessContext(CommandPhase.BOOTSTRAP, 4)
        ),
    )

    assert dispatcher.dispatch(_request()) == _failure(
        REQUEST_ID,
        "bridge_unavailable",
        ERRORS["bridge_unavailable"],
    )
    assert validated == []


def test_br_g_32_dispatcher_snapshots_command_specs_at_construction() -> None:
    commands = {"probe": _spec(lambda payload: payload)}
    dispatcher = _bridge_dispatcher(document=_Document(), commands=commands)
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

    dispatcher = _bridge_dispatcher(
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
    dispatcher = _bridge_dispatcher(
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

    dispatcher = _bridge_dispatcher(
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
    dispatcher = _bridge_dispatcher(
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


@pytest.mark.supplemental_node
def test_supplemental_node_start_plan_identity_and_timeout_contract() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental bridge probe")
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


@pytest.mark.parametrize(
    "payload",
    [
        {
            "source_id": "slot-" + "1" * 32,
            "target_id": "slot-" + "2" * 32,
            "deletion_policy": None,
        },
        {
            "command_id": "3" * 32,
            "source_id": "slot-" + "1" * 32,
            "target_id": "slot-" + "2" * 32,
            "deletion_policy": None,
            "revision": 0,
        },
    ],
)
def test_br_g_32_start_plan_identity_refusal_precedes_handler_entry(
    payload: dict[str, object],
) -> None:
    class Slots:
        def resolve_pair(self, *args: object) -> tuple[str, str]:
            del args
            raise AssertionError("invalid start_plan reached slot authority")

    class Registry:
        def replay_start(self, *args: object) -> TaskStartView | None:
            del args
            raise AssertionError("invalid start_plan reached task authority")

    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands=production_command_specs(
            picker=lambda: None,
            slots=Slots(),
            registry=Registry(),
            shell_ready=lambda _generation: None,
        ),
    )

    assert dispatcher.dispatch(
        _request(command="start_plan", payload=payload)
    ) == _failure(
        REQUEST_ID,
        "invalid_payload",
        ERRORS["invalid_payload"],
    )


@pytest.mark.supplemental_node
def test_supplemental_node_drain_generation_recovers_without_duplication() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental drain probe")
    probe = Path(__file__).parents[2] / "assets" / "drain_manager_probe.mjs"
    bridge = Path(bridge_module.__file__).parent / "assets" / "bridge.js"

    completed = subprocess.run(
        [str(node), str(probe), str(bridge)],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.supplemental_node
def test_supplemental_node_interactive_wrapper_is_bounded_single_attempt() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental bridge probe")
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
        registry=SimpleNamespace(),
        shell_ready=lambda _generation: None,
    )
    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands=commands,
    )

    assert dispatcher.dispatch(_request(command="test_report")) == _failure(
        REQUEST_ID,
        "unknown_command",
        "This desktop action is not available.",
    )


def test_br_g_33_next_events_crosses_production_dispatch_as_exact_tagged_views() -> None:
    task_id = "task-" + "2" * 32
    session_id = "3" * 32
    drain_id = "4" * 32
    event = SessionEventView(
        session_id,
        7,
        "2026-08-12T11:00:00Z",
        "StateChanged",
        {"state": "running"},
    )
    record = SessionRecordView(
        session_id,
        PLAN_KIND,
        "pending",
        False,
        "2026-08-12T10:59:59Z",
        None,
        None,
        None,
    )

    class Registry:
        def drain(self, *args: object, **kwargs: object) -> TaskDrainView:
            assert args == (task_id, session_id, drain_id)
            assert kwargs == {"replay_from": None}
            return TaskDrainView(
                task_id,
                session_id,
                drain_id,
                (
                    TaskEventUpdateView("event", event),
                    TaskRecordUpdateView("record", record),
                ),
            )

    commands = production_command_specs(
        picker=lambda: None,
        slots=SimpleNamespace(),
        registry=Registry(),
        shell_ready=lambda _generation: None,
    )
    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands=commands,
    )

    response = dispatcher.dispatch(
        _request(
            command="next_events",
            payload={
                "task_id": task_id,
                "session_id": session_id,
                "drain_id": drain_id,
                "replay_from": None,
            },
        )
    )

    assert response == {
        "schema_version": 1,
        "request_id": REQUEST_ID,
        "ok": True,
        "result": {
            "task_id": task_id,
            "session_id": session_id,
            "drain_id": drain_id,
            "updates": [
                {
                    "update_type": "event",
                    "event": {
                        "session_id": session_id,
                        "sequence": 7,
                        "at": "2026-08-12T11:00:00Z",
                        "body_type": "StateChanged",
                        "body": {"state": "running"},
                    },
                },
                {
                    "update_type": "record",
                    "record": {
                        "session_id": session_id,
                        "kind": "sync-plan",
                        "state": "pending",
                        "supports_pause": False,
                        "created_at": "2026-08-12T10:59:59Z",
                        "started_at": None,
                        "ended_at": None,
                        "result": None,
                    },
                },
            ],
        },
    }


def test_task_close_crosses_production_dispatch_as_exact_echo() -> None:
    task_id = "task-" + "2" * 32
    session_id = "3" * 32

    class Registry:
        def close_task(self, received_task: str, received_session: str) -> TaskCloseView:
            assert (received_task, received_session) == (task_id, session_id)
            return TaskCloseView(received_task, received_session)

    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands=production_command_specs(
            picker=lambda: None,
            slots=SimpleNamespace(),
            registry=Registry(),
            shell_ready=lambda _generation: None,
        ),
    )

    response = dispatcher.dispatch(
        _request(
            command="close_task",
            payload={"task_id": task_id, "session_id": session_id},
        )
    )

    assert response == {
        "schema_version": 1,
        "request_id": REQUEST_ID,
        "ok": True,
        "result": {"task_id": task_id, "session_id": session_id},
    }


def test_terminal_session_release_crosses_dispatch_as_exact_echo() -> None:
    task_id = "task-" + "2" * 32
    session_id = "3" * 32

    class Registry:
        def release_terminal_session(
            self,
            received_task: str,
            received_session: str,
        ) -> TaskSessionReleaseView:
            assert (received_task, received_session) == (task_id, session_id)
            return TaskSessionReleaseView(received_task, received_session)

    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands=production_command_specs(
            picker=lambda: None,
            slots=SimpleNamespace(),
            registry=Registry(),
            shell_ready=lambda _generation: None,
        ),
    )

    response = dispatcher.dispatch(
        _request(
            command="release_terminal_session",
            payload={"task_id": task_id, "session_id": session_id},
        )
    )

    assert response == {
        "schema_version": 1,
        "request_id": REQUEST_ID,
        "ok": True,
        "result": {"task_id": task_id, "session_id": session_id},
    }


def test_br_g_33_next_events_production_refusal_is_named_and_sanitized() -> None:
    class Registry:
        def drain(self, *args: object, **kwargs: object) -> object:
            del args, kwargs
            raise TaskUnavailableError("private task detail")

    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands=production_command_specs(
            picker=lambda: None,
            slots=SimpleNamespace(),
            registry=Registry(),
            shell_ready=lambda _generation: None,
        ),
    )

    response = dispatcher.dispatch(
        _request(
            command="next_events",
            payload={
                "task_id": "task-" + "2" * 32,
                "session_id": "3" * 32,
                "drain_id": "4" * 32,
                "replay_from": 1,
            },
        )
    )

    assert response == _failure(
        REQUEST_ID,
        "task_unavailable",
        ERRORS["task_unavailable"],
    )
    assert "private" not in repr(response)


def test_br_g_32_utf8_limit_is_inclusive_and_oversize_is_predecode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handled: list[object] = []
    dispatcher = _bridge_dispatcher(
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

    assert dispatcher.dispatch("x" * 65_537 + "\ud800") == _failure(
        None,
        "request_too_large",
        "The desktop request is too large.",
    )


def test_br_g_32_handler_and_codec_failures_are_sanitized_and_logs_are_private(
    caplog: pytest.LogCaptureFixture,
) -> None:
    body_secret = r"C:\Users\Someone\secret payload.txt"
    exception_secret = r"D:\private\handler traceback sentinel"
    caplog.set_level(logging.INFO, logger="namisync")

    def fail_handler(payload: object) -> object:
        assert payload == {"sentinel": body_secret}
        raise RuntimeError(exception_secret)

    handler_dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={"probe": _spec(fail_handler)},
    )
    codec_dispatcher = _bridge_dispatcher(
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


@pytest.mark.parametrize(
    "witness",
    iter_public_view_witnesses(),
    ids=lambda witness: witness.label,
)
def test_br_g_32_every_approved_public_view_crosses_real_dispatch_exactly(
    witness: PublicViewWitness,
) -> None:
    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={"probe": _spec(lambda _payload: witness.value)},
    )
    expected = {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": REQUEST_ID,
        "ok": True,
        "result": witness.expected,
    }

    response = dispatcher.dispatch(_request())

    assert response == expected
    assert set(response) == {"schema_version", "request_id", "ok", "result"}
    assert isinstance(response["result"], dict)
    assert isinstance(witness.expected, dict)
    assert set(response["result"]) == set(witness.expected)
    encoded = json.dumps(response, ensure_ascii=False, allow_nan=False)
    assert json.loads(encoded) == expected


@pytest.mark.parametrize(
    ("_label", "invalid_return"),
    INVALID_RETURN_WITNESSES,
    ids=[label for label, _value in INVALID_RETURN_WITNESSES],
)
def test_br_g_32_invalid_public_view_returns_are_sanitized_by_dispatch(
    _label: str,
    invalid_return: object,
) -> None:
    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={"probe": _spec(lambda _payload: invalid_return)},
    )

    response = dispatcher.dispatch(_request())

    assert response == _failure(
        REQUEST_ID,
        "internal_error",
        ERRORS["internal_error"],
    )
    assert json.loads(
        json.dumps(response, ensure_ascii=False, allow_nan=False)
    ) == response


def test_br_g_32_base_exceptions_cannot_cross_handler_or_codec_boundary() -> None:
    class ExitMapping(dict):
        def items(self):
            raise SystemExit("private codec termination detail")

    handler_dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={
            "probe": _spec(
                lambda payload: (_ for _ in ()).throw(
                    SystemExit("private handler termination detail")
                )
            )
        },
    )
    codec_dispatcher = _bridge_dispatcher(
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

    dispatcher = _bridge_dispatcher(
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
        (TaskUnavailableError("private task"), "task_unavailable"),
        (DrainBusyError("private drain"), "drain_busy"),
        (
            ObservationConflictError("private observation"),
            "observation_conflict",
        ),
    ],
)
def test_br_g_32_typed_command_refusals_use_only_fixed_public_errors(
    error: Exception,
    code: str,
) -> None:
    def refuse(payload: object) -> object:
        del payload
        raise error

    dispatcher = _bridge_dispatcher(
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

    dispatcher = _bridge_dispatcher(
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

    class Registry:
        def replay_start(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            return None

        def start_plan(self, *args: object, **kwargs: object) -> TaskStartView:
            kwargs.pop("wire_intent")
            plan = service.start_plan(*args, **kwargs)
            return TaskStartView(
                "task-" + "6" * 32,
                plan.request_id,
                plan.session_id,
            )

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
        registry=Registry(),
        shell_ready=lambda _generation: None,
    )
    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands=commands,
    )
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
        "task_id": "task-" + "6" * 32,
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
    off_origin = _bridge_dispatcher(
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
    closing = _bridge_dispatcher(
        document=_Document(),
        commands={"probe": _spec(lambda payload: payload)},
    )
    closing.begin_close()
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

    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={"probe": _spec(admitted_handler)},
    )
    worker = Thread(
        target=lambda: (response.append(dispatcher.dispatch(_request())), finished.set())
    )
    worker.start()
    assert entered.wait(1.0)

    dispatcher.begin_close()
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
    dispatcher.wait_for_handlers()


def test_bridge_admission_ceiling_fails_fast_and_releases_capacity() -> None:
    assert bridge_module._MAX_ADMITTED_HANDLERS == 64
    entered = 0
    entered_lock = Lock()
    saturated = Event()
    release = Event()
    responses: list[object] = []

    def blocking_handler(payload: object) -> object:
        nonlocal entered
        with entered_lock:
            entered += 1
            if entered == bridge_module._MAX_ADMITTED_HANDLERS:
                saturated.set()
        assert release.wait(3.0)
        return payload

    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={"probe": _spec(blocking_handler)},
    )
    workers = [
        Thread(target=lambda: responses.append(dispatcher.dispatch(_request())))
        for _ in range(bridge_module._MAX_ADMITTED_HANDLERS)
    ]
    for worker in workers:
        worker.start()
    assert saturated.wait(2.0)

    untrusted_body = _UntouchableBody()
    started = monotonic()
    assert dispatcher.dispatch(untrusted_body) == _failure(
        None,
        "bridge_busy",
        ERRORS["bridge_busy"],
    )
    assert monotonic() - started < 0.1
    assert untrusted_body.touched == []

    release.set()
    for worker in workers:
        worker.join(2.0)
        assert not worker.is_alive()
    assert len(responses) == bridge_module._MAX_ADMITTED_HANDLERS
    assert all(response["ok"] is True for response in responses)
    assert dispatcher.dispatch(_request())["ok"] is True


def test_bridge_handler_wait_times_out_then_a_later_retry_quiesces() -> None:
    entered = Event()
    release = Event()

    def never_finishes_without_release(payload: object) -> object:
        entered.set()
        assert release.wait(3.0)
        return payload

    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={"probe": _spec(never_finishes_without_release)},
    )
    worker = Thread(target=lambda: dispatcher.dispatch(_request()))
    worker.start()
    assert entered.wait(1.0)
    dispatcher.begin_close()

    started = monotonic()
    with pytest.raises(TimeoutError, match="did not quiesce"):
        dispatcher.wait_for_handlers(0.02)
    assert monotonic() - started < 0.2
    assert worker.is_alive()

    release.set()
    dispatcher.wait_for_handlers(1.0)
    worker.join(1.0)
    assert not worker.is_alive()
    assert dispatcher.dispatch(_UntouchableBody()) == _failure(
        None,
        "bridge_unavailable",
        ERRORS["bridge_unavailable"],
    )


def test_raw_command_control_characters_are_rejected_without_log_injection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    marker = "FORGED-BRIDGE-RECORD"
    dispatcher = _bridge_dispatcher(
        document=_Document(),
        commands={"probe": _spec(lambda payload: payload)},
    )
    caplog.set_level(logging.INFO, logger="namisync")

    response = dispatcher.dispatch(
        _request(command=f"probe\r\nERROR logger=namisync: {marker}")
    )

    assert response == _failure(
        REQUEST_ID,
        "invalid_request",
        ERRORS["invalid_request"],
    )
    assert marker not in caplog.text
    assert "command=- code=invalid_request" in caplog.text
