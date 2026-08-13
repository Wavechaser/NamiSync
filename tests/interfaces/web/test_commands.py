"""Ordinary evidence for the exact Slice 2 command policy table."""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from namisync.interfaces import service as service_module
from namisync.interfaces.service import (
    CommandIdConflictError,
    ExecutionAdmissionView,
    ExecutionSession,
    PlanSession,
    SessionRecordView,
    SyncPathInputError,
)
from namisync.interfaces.web.bridge import BridgeProtocolError, to_primitive_view
from namisync.interfaces.web.commands import (
    ADAPTER_PUBLIC_VIEW_DATACLASSES,
    CommandAccess,
    CommandConflictError,
    CommandPayloadError,
    CommandRetry,
    CommandTimeout,
    FieldRequirement,
    PickerUnavailableError,
    PlanningRefusedError,
    PUBLIC_VIEW_DATACLASSES,
    SERVICE_PUBLIC_VIEW_DATACLASSES,
    production_command_specs,
)
from namisync.interfaces.web.drain import (
    TaskCloseView,
    TaskDrainView,
    TaskEventUpdateView,
    TaskIntentConflictError,
    TaskRecordUpdateView,
    TaskRegistry,
    TaskSessionReleaseView,
    TaskStartView,
)
from namisync.interfaces.web.slots import FolderSlotTable, SlotUnavailableError
from namisync.workflows.views import SessionEventView


SOURCE_ID = "slot-11111111111111111111111111111111"
TARGET_ID = "slot-22222222222222222222222222222222"
COMMAND_ID = "a3" * 16
TASK_ID = "task-" + "3" * 32
SESSION_ID = "5" * 32
DRAIN_ID = "d6" * 16


class _Slots:
    def __init__(self) -> None:
        self.stored: list[tuple[str, str]] = []
        self.resolved: list[tuple[str, str]] = []

    def store(self, path: str, *, purpose: str) -> tuple[str, str]:
        self.stored.append((path, purpose))
        slot_id = SOURCE_ID if purpose == "source" else TARGET_ID
        return slot_id, f"Selected {purpose} \U0001f30a"

    def resolve_pair(self, source_id: str, target_id: str) -> tuple[str, str]:
        self.resolved.append((source_id, target_id))
        return r"C:\private\source", r"D:\private\target"


class _Service:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.replays: list[tuple[object, ...]] = []

    def replay_start(
        self,
        command_id: str,
        wire_intent: tuple[str, str, str | None],
    ) -> TaskStartView | None:
        self.replays.append((command_id, wire_intent))
        return None

    def start_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None = None,
        command_id: str | None = None,
        wire_intent: tuple[str, str, str | None] | None = None,
    ) -> TaskStartView:
        self.calls.append(
            (source, target, deletion_policy, command_id, wire_intent)
        )
        return TaskStartView(
            task_id=TASK_ID,
            request_id="4" * 32,
            session_id="5" * 32,
        )

    def drain(
        self,
        task_id: str,
        session_id: str,
        drain_id: str,
        *,
        replay_from: int | None,
    ) -> TaskDrainView:
        self.calls.append(
            ("drain", task_id, session_id, drain_id, replay_from)
        )
        return TaskDrainView(task_id, session_id, drain_id, ())

    def close_task(self, task_id: str, session_id: str) -> TaskCloseView:
        self.calls.append(("close", task_id, session_id))
        return TaskCloseView(task_id, session_id)

    def release_terminal_session(
        self,
        task_id: str,
        session_id: str,
    ) -> TaskSessionReleaseView:
        self.calls.append(("release", task_id, session_id))
        return TaskSessionReleaseView(task_id, session_id)


def _commands(*, picker=lambda: None):
    slots = _Slots()
    service = _Service()
    return (
        production_command_specs(picker=picker, slots=slots, registry=service),
        slots,
        service,
    )


def test_br_g_32_production_command_table_is_exact_immutable_and_policy_complete() -> None:
    commands, _, _ = _commands()

    assert tuple(commands) == (
        "pick_folder",
        "start_plan",
        "next_events",
        "release_terminal_session",
        "close_task",
    )
    assert "test_report" not in commands
    assert (
        commands["pick_folder"].access,
        commands["pick_folder"].command_id,
        commands["pick_folder"].revision,
        commands["pick_folder"].timeout,
        commands["pick_folder"].retry,
    ) == (
        CommandAccess.READ_ONLY,
        FieldRequirement.FORBIDDEN,
        FieldRequirement.FORBIDDEN,
        CommandTimeout.INTERACTIVE,
        CommandRetry.NONE,
    )
    assert (
        commands["start_plan"].access,
        commands["start_plan"].command_id,
        commands["start_plan"].revision,
        commands["start_plan"].timeout,
        commands["start_plan"].retry,
    ) == (
        CommandAccess.MUTATING,
        FieldRequirement.REQUIRED,
        FieldRequirement.FORBIDDEN,
        CommandTimeout.MUTATION_30_SECONDS,
        CommandRetry.SAME_COMMAND_ONCE,
    )
    assert (
        commands["next_events"].access,
        commands["next_events"].command_id,
        commands["next_events"].revision,
        commands["next_events"].timeout,
        commands["next_events"].retry,
    ) == (
        CommandAccess.READ_ONLY,
        FieldRequirement.FORBIDDEN,
        FieldRequirement.FORBIDDEN,
        CommandTimeout.DRAIN_30_SECONDS,
        CommandRetry.NONE,
    )
    assert (
        commands["release_terminal_session"].access,
        commands["release_terminal_session"].command_id,
        commands["release_terminal_session"].revision,
        commands["release_terminal_session"].timeout,
        commands["release_terminal_session"].retry,
    ) == (
        CommandAccess.MUTATING,
        FieldRequirement.FORBIDDEN,
        FieldRequirement.FORBIDDEN,
        CommandTimeout.MUTATION_30_SECONDS,
        CommandRetry.SAME_PAYLOAD_BOUNDED,
    )
    assert (
        commands["close_task"].access,
        commands["close_task"].command_id,
        commands["close_task"].revision,
        commands["close_task"].timeout,
        commands["close_task"].retry,
    ) == (
        CommandAccess.MUTATING,
        FieldRequirement.FORBIDDEN,
        FieldRequirement.FORBIDDEN,
        CommandTimeout.MUTATION_30_SECONDS,
        CommandRetry.SAME_PAYLOAD_BOUNDED,
    )

    with pytest.raises(TypeError):
        commands["future_command"] = commands["pick_folder"]  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        commands["pick_folder"].retry = CommandRetry.SAME_COMMAND_ONCE  # type: ignore[misc]


def test_br_g_32_command_composition_is_constructor_only() -> None:
    signature = inspect.signature(production_command_specs)
    source = inspect.getsource(
        __import__(
            "namisync.interfaces.web.commands",
            fromlist=["commands"],
        )
    )

    assert tuple(signature.parameters) == ("picker", "slots", "registry")
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    assert "extra_commands" not in source
    assert "register" not in source
    assert "test_report" not in source


def test_br_g_32_folder_picker_returns_only_opaque_presentation_data() -> None:
    private_path = r"C:\Users\Someone\secret <folder>"
    commands, slots, _ = _commands(picker=lambda: (private_path,))

    result = commands["pick_folder"].invoke({"purpose": "source"})

    assert result == {
        "id": SOURCE_ID,
        "display": "Selected source \U0001f30a",
    }
    assert private_path not in repr(result)
    assert slots.stored == [(private_path, "source")]


def test_br_g_32_folder_picker_cancel_creates_no_slot() -> None:
    commands, slots, _ = _commands(picker=lambda: None)

    assert commands["pick_folder"].invoke({"purpose": "target"}) is None
    assert slots.stored == []


@pytest.mark.parametrize(
    "selected",
    ["C:\\bare", (), ("one", "two"), (7,), ("\ud800",)],
)
def test_br_g_32_folder_picker_refuses_invalid_native_results(
    selected: object,
) -> None:
    commands, slots, _ = _commands(picker=lambda: selected)  # type: ignore[arg-type]

    with pytest.raises(PickerUnavailableError):
        commands["pick_folder"].invoke({"purpose": "source"})

    assert slots.stored == []


def test_br_g_32_folder_picker_exception_is_typed_without_storing_a_slot() -> None:
    private_detail = "C:\\private\\picker failure"

    def refuse():
        raise OSError(private_detail)

    commands, slots, _ = _commands(picker=refuse)

    with pytest.raises(PickerUnavailableError) as captured:
        commands["pick_folder"].invoke({"purpose": "source"})

    assert private_detail not in str(captured.value)
    assert slots.stored == []


def test_br_g_32_folder_picker_system_exit_cannot_cross_the_command_boundary() -> None:
    def refuse():
        raise SystemExit("private native termination detail")

    commands, slots, _ = _commands(picker=refuse)

    with pytest.raises(PickerUnavailableError) as captured:
        commands["pick_folder"].invoke({"purpose": "source"})

    assert "private" not in str(captured.value)
    assert slots.stored == []


@pytest.mark.parametrize(
    "stored",
    [
        ("not-a-slot", "display"),
        (SOURCE_ID, "\ud800"),
        (SOURCE_ID, 7),
    ],
)
def test_br_g_32_folder_picker_refuses_invalid_slot_authority_results(
    stored: object,
) -> None:
    class InvalidSlots(_Slots):
        def store(self, path: str, *, purpose: str):
            del path, purpose
            return stored

    slots = InvalidSlots()
    commands = production_command_specs(
        picker=lambda: (r"C:\private",),
        slots=slots,
        registry=_Service(),
    )

    with pytest.raises(RuntimeError, match="slot authority"):
        commands["pick_folder"].invoke({"purpose": "source"})


def test_br_g_32_start_plan_resolves_slots_and_delegates_once() -> None:
    commands, slots, service = _commands()
    payload = {
        "command_id": COMMAND_ID,
        "source_id": SOURCE_ID,
        "target_id": TARGET_ID,
        "deletion_policy": None,
    }

    result = commands["start_plan"].invoke(payload)

    assert result == TaskStartView(
        task_id=TASK_ID,
        request_id="4" * 32,
        session_id="5" * 32,
    )
    assert slots.resolved == [(SOURCE_ID, TARGET_ID)]
    assert service.replays == [
        (COMMAND_ID, (SOURCE_ID, TARGET_ID, None))
    ]
    assert service.calls == [
        (
            r"C:\private\source",
            r"D:\private\target",
            None,
            COMMAND_ID,
            (SOURCE_ID, TARGET_ID, None),
        )
    ]
    assert "private" not in repr(payload)


@pytest.mark.parametrize("retirement", ["expiry", "eviction"])
def test_uncertain_start_replays_before_volatile_slots_are_resolved(
    retirement: str,
) -> None:
    class Clock:
        now = 0.0

        def __call__(self) -> float:
            return self.now

    class Service:
        def __init__(self) -> None:
            self.calls = []

        def start_plan(self, source, target, **kwargs):
            self.calls.append((source, target, kwargs["command_id"]))
            return PlanSession("8" * 32, "9" * 32)

        def unsubscribe(self, session_id):
            del session_id

        def close_session(self, session_id):
            del session_id

        def drop_plan(self, request_id):
            del request_id

    clock = Clock()
    slot_tokens = iter(f"{value:032x}" for value in range(1, 100))
    slots = FolderSlotTable(clock=clock, token=lambda: next(slot_tokens))
    source_id, _ = slots.store(r"C:\source", purpose="source")
    target_id, _ = slots.store(r"D:\target", purpose="target")
    service = Service()
    registry = TaskRegistry(service, token=lambda: "a" * 32)
    commands = production_command_specs(
        picker=lambda: None,
        slots=slots,
        registry=registry,
    )
    payload = {
        "command_id": COMMAND_ID,
        "source_id": source_id,
        "target_id": target_id,
        "deletion_policy": None,
    }

    lost_response = commands["start_plan"].invoke(payload)
    if retirement == "expiry":
        clock.now = 1_801.0
    else:
        for value in range(32):
            purpose = "source" if value % 2 == 0 else "target"
            slots.store(f"C:\\replacement-{value}", purpose=purpose)
    with pytest.raises(SlotUnavailableError):
        slots.resolve_pair(source_id, target_id)

    replay = commands["start_plan"].invoke(payload)

    assert replay == lost_response
    assert service.calls == [(r"C:\source", r"D:\target", COMMAND_ID)]
    with pytest.raises(CommandConflictError):
        commands["start_plan"].invoke({**payload, "deletion_policy": "trash"})


def test_br_g_33_next_events_delegates_exact_authority_and_returns_typed_view() -> None:
    commands, slots, registry = _commands()

    result = commands["next_events"].invoke(
        {
            "task_id": TASK_ID,
            "session_id": SESSION_ID,
            "drain_id": DRAIN_ID,
            "replay_from": 17,
        }
    )

    assert result == TaskDrainView(TASK_ID, SESSION_ID, DRAIN_ID, ())
    assert registry.calls == [
        ("drain", TASK_ID, SESSION_ID, DRAIN_ID, 17)
    ]
    assert slots.resolved == []


def test_task_close_delegates_exact_authority_and_echoes_identity() -> None:
    commands, slots, registry = _commands()

    result = commands["close_task"].invoke(
        {"task_id": TASK_ID, "session_id": SESSION_ID}
    )

    assert result == TaskCloseView(TASK_ID, SESSION_ID)
    assert registry.calls == [("close", TASK_ID, SESSION_ID)]
    assert slots.resolved == []


def test_terminal_session_release_delegates_and_echoes_exact_identity() -> None:
    commands, slots, registry = _commands()

    result = commands["release_terminal_session"].invoke(
        {"task_id": TASK_ID, "session_id": SESSION_ID}
    )

    assert result == TaskSessionReleaseView(TASK_ID, SESSION_ID)
    assert registry.calls == [("release", TASK_ID, SESSION_ID)]
    assert slots.resolved == []


@pytest.mark.parametrize(
    "result",
    [
        object(),
        TaskSessionReleaseView("task-" + "9" * 32, SESSION_ID),
        TaskSessionReleaseView(TASK_ID, "9" * 32),
    ],
)
def test_terminal_session_release_refuses_mismatched_registry_result(
    result: object,
) -> None:
    class InvalidRegistry(_Service):
        def release_terminal_session(self, *args: object) -> object:
            del args
            return result

    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=InvalidRegistry(),
    )

    with pytest.raises(RuntimeError, match="invalid release data"):
        commands["release_terminal_session"].invoke(
            {"task_id": TASK_ID, "session_id": SESSION_ID}
        )


@pytest.mark.parametrize(
    "result",
    [
        object(),
        TaskCloseView("task-" + "9" * 32, SESSION_ID),
        TaskCloseView(TASK_ID, "9" * 32),
    ],
)
def test_task_close_refuses_invalid_or_mismatched_registry_result(
    result: object,
) -> None:
    class InvalidRegistry(_Service):
        def close_task(self, *args: object) -> object:
            del args
            return result

    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=InvalidRegistry(),
    )

    with pytest.raises(RuntimeError, match="invalid close data"):
        commands["close_task"].invoke(
            {"task_id": TASK_ID, "session_id": SESSION_ID}
        )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "task_id": TASK_ID,
            "session_id": SESSION_ID,
            "drain_id": DRAIN_ID,
            "replay_from": None,
            "cursor": 1,
        },
        {
            "task_id": SESSION_ID,
            "session_id": SESSION_ID,
            "drain_id": DRAIN_ID,
            "replay_from": None,
        },
        {
            "task_id": TASK_ID,
            "session_id": "task-" + "5" * 32,
            "drain_id": DRAIN_ID,
            "replay_from": None,
        },
        *[
            {
                "task_id": TASK_ID,
                "session_id": SESSION_ID,
                "drain_id": DRAIN_ID,
                "replay_from": value,
            }
            for value in (False, 0, -1, 1.5, "1")
        ],
    ],
)
def test_br_g_33_next_events_refuses_nonexact_payloads(payload: object) -> None:
    commands, _slots, registry = _commands()

    with pytest.raises(CommandPayloadError):
        commands["next_events"].invoke(payload)

    assert registry.calls == []


@pytest.mark.parametrize(
    "result",
    [
        object(),
        TaskDrainView("task-" + "9" * 32, SESSION_ID, DRAIN_ID, ()),
        TaskDrainView(TASK_ID, "9" * 32, DRAIN_ID, ()),
        TaskDrainView(TASK_ID, SESSION_ID, "9" * 32, ()),
    ],
)
def test_br_g_33_next_events_refuses_invalid_or_mismatched_registry_result(
    result: object,
) -> None:
    class InvalidRegistry(_Service):
        def drain(self, *args: object, **kwargs: object) -> object:
            del args, kwargs
            return result

    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=InvalidRegistry(),
    )

    with pytest.raises(RuntimeError, match="invalid drain data"):
        commands["next_events"].invoke(
            {
                "task_id": TASK_ID,
                "session_id": SESSION_ID,
                "drain_id": DRAIN_ID,
                "replay_from": None,
            }
        )


@pytest.mark.parametrize(
    ("service_error", "adapter_error"),
    [
        (CommandIdConflictError("private conflict"), CommandConflictError),
        (TaskIntentConflictError("private task conflict"), CommandConflictError),
        (SyncPathInputError("C:\\private\\bad root"), PlanningRefusedError),
    ],
)
def test_br_g_32_start_plan_maps_only_typed_service_refusals(
    service_error: Exception,
    adapter_error: type[Exception],
) -> None:
    class RefusingService(_Service):
        def start_plan(self, *args: object, **kwargs: object) -> PlanSession:
            del args, kwargs
            raise service_error

    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=RefusingService(),
    )

    with pytest.raises(adapter_error) as captured:
        commands["start_plan"].invoke(
            {
                "command_id": COMMAND_ID,
                "source_id": SOURCE_ID,
                "target_id": TARGET_ID,
                "deletion_policy": None,
            }
        )

    assert "private" not in str(captured.value)


def test_br_g_32_start_plan_does_not_reclassify_incidental_value_error() -> None:
    class BrokenService(_Service):
        def start_plan(self, *args: object, **kwargs: object) -> PlanSession:
            del args, kwargs
            raise ValueError("incidental implementation defect")

    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=BrokenService(),
    )

    with pytest.raises(ValueError, match="incidental implementation defect"):
        commands["start_plan"].invoke(
            {
                "command_id": COMMAND_ID,
                "source_id": SOURCE_ID,
                "target_id": TARGET_ID,
                "deletion_policy": None,
            }
        )


@pytest.mark.parametrize(
    "result",
    [
        ExecutionSession(run_id="6" * 32, session_id="7" * 32),
        PlanSession(request_id="4" * 32, session_id="5" * 32),
        SimpleNamespace(
            task_id=TASK_ID,
            request_id="4" * 32,
            session_id="5" * 32,
        ),
    ],
)
def test_br_g_32_start_plan_refuses_invalid_service_result_schema(
    result: object,
) -> None:
    class InvalidService(_Service):
        def start_plan(self, *args: object, **kwargs: object):
            del args, kwargs
            return result

    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=InvalidService(),
    )

    with pytest.raises(RuntimeError, match="invalid data"):
        commands["start_plan"].invoke(
            {
                "command_id": COMMAND_ID,
                "source_id": SOURCE_ID,
                "target_id": TARGET_ID,
                "deletion_policy": None,
            }
        )


@pytest.mark.parametrize(
    ("command", "payload"),
    [
        ("pick_folder", {}),
        ("pick_folder", {"purpose": "source", "path": r"C:\forged"}),
        ("pick_folder", {"purpose": "other"}),
        ("start_plan", {}),
        (
            "start_plan",
            {
                "command_id": COMMAND_ID.upper(),
                "source_id": SOURCE_ID,
                "target_id": TARGET_ID,
                "deletion_policy": None,
            },
        ),
        ("close_task", {}),
        ("release_terminal_session", {}),
        (
            "release_terminal_session",
            {"task_id": TASK_ID, "session_id": SESSION_ID, "extra": True},
        ),
        (
            "release_terminal_session",
            {"task_id": SESSION_ID, "session_id": SESSION_ID},
        ),
        (
            "release_terminal_session",
            {"task_id": TASK_ID, "session_id": TASK_ID},
        ),
        (
            "close_task",
            {"task_id": TASK_ID, "session_id": SESSION_ID, "extra": True},
        ),
        (
            "close_task",
            {"task_id": SESSION_ID, "session_id": SESSION_ID},
        ),
        (
            "close_task",
            {"task_id": TASK_ID, "session_id": TASK_ID},
        ),
        (
            "start_plan",
            {
                "command_id": COMMAND_ID,
                "source_id": r"C:\forged",
                "target_id": TARGET_ID,
                "deletion_policy": None,
            },
        ),
        (
            "start_plan",
            {
                "command_id": COMMAND_ID,
                "source_id": SOURCE_ID,
                "target_id": TARGET_ID,
                "deletion_policy": "mirror",
            },
        ),
        (
            "start_plan",
            {
                "command_id": COMMAND_ID,
                "source_id": SOURCE_ID,
                "target_id": TARGET_ID,
                "deletion_policy": "trash",
                "revision": 0,
            },
        ),
    ],
)
def test_br_g_32_payload_validators_reject_unknown_fields_and_authority(
    command: str,
    payload: object,
) -> None:
    commands, slots, service = _commands()

    with pytest.raises(CommandPayloadError):
        commands[command].invoke(payload)

    assert slots.stored == []
    assert slots.resolved == []
    assert service.calls == []


class _State(StrEnum):
    READY = "ready"


@dataclass(frozen=True, slots=True)
class _UnapprovedLookalike:
    label: str


def test_br_g_32_public_view_codec_manifest_is_recursive_and_json_native() -> None:
    view = MappingProxyType(
        {
            "admission": ExecutionAdmissionView(
                disposition="accepted",
                revision=3,
                state="running",
                session=ExecutionSession(run_id="6" * 32, session_id="7" * 32),
            ),
            "sessions": (PlanSession("8" * 32, "9" * 32),),
            "at": datetime(2026, 8, 12, 9, 30, tzinfo=timezone.utc),
        }
    )

    encoded = to_primitive_view(view)
    assert encoded == {
        "admission": {
            "disposition": "accepted",
            "revision": 3,
            "state": "running",
            "session": {"run_id": "6" * 32, "session_id": "7" * 32},
        },
        "sessions": [
            {
                "request_id": "8" * 32,
                "session_id": "9" * 32,
            }
        ],
        "at": "2026-08-12T09:30:00+00:00",
    }
    assert json.loads(json.dumps(encoded, ensure_ascii=False)) == encoded


def test_br_g_32_public_view_codec_manifest_tracks_service_exports() -> None:
    exported_dataclasses = {
        getattr(service_module, name)
        for name in service_module.__all__
        if isinstance(getattr(service_module, name), type)
        and is_dataclass(getattr(service_module, name))
    }

    assert SERVICE_PUBLIC_VIEW_DATACLASSES == exported_dataclasses
    assert SERVICE_PUBLIC_VIEW_DATACLASSES <= PUBLIC_VIEW_DATACLASSES


def test_br_g_33_codec_approves_only_exact_adapter_task_views() -> None:
    event = SessionEventView(
        SESSION_ID,
        9,
        "2026-08-12T10:00:00Z",
        "StateChanged",
        {"state": "running"},
    )
    drain = TaskDrainView(
        TASK_ID,
        SESSION_ID,
        DRAIN_ID,
        (TaskEventUpdateView("event", event),),
    )

    assert ADAPTER_PUBLIC_VIEW_DATACLASSES == {
        TaskStartView,
        TaskCloseView,
        TaskSessionReleaseView,
        TaskDrainView,
        TaskEventUpdateView,
        TaskRecordUpdateView,
    }
    assert to_primitive_view(drain) == {
        "task_id": TASK_ID,
        "session_id": SESSION_ID,
        "drain_id": DRAIN_ID,
        "updates": [
            {
                "update_type": "event",
                "event": {
                    "session_id": SESSION_ID,
                    "sequence": 9,
                    "at": "2026-08-12T10:00:00Z",
                    "body_type": "StateChanged",
                    "body": {"state": "running"},
                },
            }
        ],
    }
    record = SessionRecordView(
        SESSION_ID,
        "plan",
        "pending",
        False,
        "2026-08-12T10:00:00Z",
        None,
        None,
        None,
    )
    assert to_primitive_view(TaskRecordUpdateView("record", record)) == {
        "update_type": "record",
        "record": {
            "session_id": SESSION_ID,
            "kind": "plan",
            "state": "pending",
            "supports_pause": False,
            "created_at": "2026-08-12T10:00:00Z",
            "started_at": None,
            "ended_at": None,
            "result": None,
        },
    }


@pytest.mark.parametrize(
    "value",
    [
        Path(r"C:\must-not-cross"),
        b"bytes",
        {1: "non-string key"},
        float("inf"),
        "\ud800",
        datetime(2026, 8, 12, 9, 30),
        _State.READY,
        _UnapprovedLookalike("same fields are not enough"),
    ],
)
def test_br_g_32_public_view_codec_refuses_non_wire_values(value: object) -> None:
    with pytest.raises(BridgeProtocolError):
        to_primitive_view(value)


def test_br_g_32_public_view_codec_refuses_recursive_containers() -> None:
    recursive: list[object] = []
    recursive.append(recursive)

    with pytest.raises(BridgeProtocolError, match="recursive"):
        to_primitive_view(recursive)
