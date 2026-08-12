"""Ordinary evidence for the exact Slice 2 command policy table."""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

import pytest

from namisync.interfaces import service as service_module
from namisync.interfaces.service import (
    ExecutionAdmissionView,
    ExecutionSession,
    PlanSession,
)
from namisync.interfaces.web.bridge import BridgeProtocolError, to_primitive_view
from namisync.interfaces.web.commands import (
    CommandAccess,
    CommandPayloadError,
    CommandRetry,
    CommandTimeout,
    FieldRequirement,
    PickerUnavailableError,
    PUBLIC_VIEW_DATACLASSES,
    SERVICE_PUBLIC_VIEW_DATACLASSES,
    production_command_specs,
)


SOURCE_ID = "slot-11111111111111111111111111111111"
TARGET_ID = "slot-22222222222222222222222222222222"
COMMAND_ID = "a3" * 16


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

    def start_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None = None,
        command_id: str | None = None,
    ) -> PlanSession:
        self.calls.append((source, target, deletion_policy, command_id))
        return PlanSession(
            request_id="4" * 32,
            session_id="5" * 32,
        )


def _commands(*, picker=lambda: None):
    slots = _Slots()
    service = _Service()
    return (
        production_command_specs(picker=picker, slots=slots, service=service),
        slots,
        service,
    )


def test_br_g_32_production_command_table_is_exact_immutable_and_policy_complete() -> None:
    commands, _, _ = _commands()

    assert tuple(commands) == ("pick_folder", "start_plan")
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

    assert tuple(signature.parameters) == ("picker", "slots", "service")
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


@pytest.mark.parametrize("selected", ["C:\\bare", (), ("one", "two"), (7,)])
def test_br_g_32_folder_picker_refuses_invalid_native_results(
    selected: object,
) -> None:
    commands, slots, _ = _commands(picker=lambda: selected)  # type: ignore[arg-type]

    with pytest.raises(PickerUnavailableError):
        commands["pick_folder"].invoke({"purpose": "source"})

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
        service=_Service(),
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

    assert result == PlanSession(request_id="4" * 32, session_id="5" * 32)
    assert slots.resolved == [(SOURCE_ID, TARGET_ID)]
    assert service.calls == [
        (r"C:\private\source", r"D:\private\target", None, COMMAND_ID)
    ]
    assert "private" not in repr(payload)


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
