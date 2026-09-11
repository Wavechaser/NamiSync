"""Ordinary evidence for the exact Slice 2 command policy table."""

from __future__ import annotations

import inspect
import json
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, dataclass, fields, is_dataclass, replace
from datetime import datetime, timezone
from enum import Enum, StrEnum
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import get_args, get_type_hints

import pytest

import namisync.interfaces.web.bridge as bridge_module
from namisync.core.session import OperationResult, SessionState
from namisync.core.models import VolumeId
from namisync.core.events import (
    DeliveryClass,
    delivery_class,
    envelope_from_dict,
)
from namisync.interfaces import service as service_module
from namisync.interfaces.ui_state import (
    MAX_JAVASCRIPT_SAFE_INTEGER,
    AppearanceValue,
    CosmeticDisposition,
    CosmeticReplaceResult,
    CosmeticSectionSnapshot,
    ThemeMode,
)
from namisync.interfaces.service import (
    CommandIdConflictError,
    ExecutionAdmissionView,
    ExecutionSession,
    PlanSession,
    SessionRecordView,
    SyncPathInputError,
    PreservationSettingsView,
    SetupOptionsView,
)
from namisync.interfaces.web.bridge import (
    BridgeProtocolError,
    BridgeResponseTooLargeError,
    _admit_task_drain_response_prefix,
    _consume_task_drain_response,
    _peek_task_drain_response,
    snapshot_bridge_response_result,
    to_primitive_view,
)
from namisync.interfaces.web.commands import (
    ADAPTER_PUBLIC_VIEW_DATACLASSES,
    CommandAccess,
    CommandAdmissionError,
    CommandConflictError,
    CommandPayloadError,
    CommandRetry,
    CommandTimeout,
    CommandWork,
    FieldRequirement,
    PickerUnavailableError,
    PlanningRefusedError,
    PUBLIC_VIEW_DATACLASSES,
    SERVICE_PUBLIC_VIEW_DATACLASSES,
    production_command_specs,
)
from namisync.interfaces.web.drain import (
    TaskCloseRequestView,
    TaskCloseView,
    TaskDrainView,
    TaskEventUpdateView,
    TaskIntentConflictError,
    TaskListView,
    TaskRecordUpdateView,
    TaskRegistry,
    TaskSessionReleaseView,
    TaskShellView,
    TaskStartView,
    TaskSummaryView,
    TaskSetupSnapshotView,
    _TaskDrainResponseCodec,
)
from namisync.interfaces.web.slots import FolderSlotTable, SlotUnavailableError
from namisync.interfaces.web.readiness import CommandPhase, ReadinessContext
from namisync.workflows import (
    PLAN_KIND,
    LocationBinding,
    LocationCandidate,
    LocationCandidateResult,
    LocationCandidateState,
    RememberedLocations,
    RememberedLocation,
    RememberedPair,
    VolumeResolution,
    VolumeResolutionState,
)
from namisync.workflows.models import HistoryEventPageView, HistoryEventView
from namisync.workflows.views import (
    PhaseResultView, RecordingIssueView, ReviewFactLimitView, SessionEventView,
    operation_result_view,
)
from tests.interfaces.web._public_view_witnesses import (
    PUBLIC_VIEW_WITNESSES,
    iter_public_view_witnesses,
)
from _service_fixtures import make_service


SOURCE_ID = "slot-11111111111111111111111111111111"
TARGET_ID = "slot-22222222222222222222222222222222"
COMMAND_ID = "a3" * 16
TASK_ID = "task-" + "3" * 32
SESSION_ID = "5" * 32
DRAIN_ID = "d6" * 16
BOOTSTRAP_CONTEXT = ReadinessContext(CommandPhase.BOOTSTRAP, 7)
OPEN_CONTEXT = ReadinessContext(CommandPhase.OPEN, 7)
SETUP_OPTIONS = SetupOptionsView(
    (),
    "trash",
    True,
    PreservationSettingsView(False, True, False),
    False,
    False,
)
SETUP_OPTIONS_SIGNATURE = (
    (),
    "trash",
    True,
    (False, True, False),
    False,
    False,
)


def _setup_options_payload() -> dict[str, object]:
    return {
        "filters": [],
        "deletion_policy": "trash",
        "trash_on_update": True,
        "preservation": {
            "preserve_ads": False,
            "preserve_created": True,
            "preserve_acl": False,
        },
        "propagate_source_casing": False,
        "verify_after_execute": False,
    }


def _invoke(spec, payload: object, *, context: object = OPEN_CONTEXT) -> object:
    return spec.invoke(payload, context=context)


class _Slots:
    def __init__(self) -> None:
        self.stored: list[tuple[str, str]] = []
        self.resolved: list[tuple[str, str]] = []

    def store(self, candidate, *, purpose: str, display=None) -> tuple[str, str]:
        self.stored.append((candidate, purpose))
        slot_id = SOURCE_ID if purpose == "source" else TARGET_ID
        return slot_id, display or f"Selected {purpose} \U0001f30a"

    def resolve_pair(self, source_id: str, target_id: str) -> tuple[str, str]:
        self.resolved.append((source_id, target_id))
        return LocationCandidate.literal(r"C:\private\source"), LocationCandidate.literal(r"D:\private\target")

    def resolve(self, slot_id: str, *, purpose: str):
        return LocationCandidate.literal(r"C:\private\inventory")


class _Service:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.replays: list[tuple[object, ...]] = []

    def create_task_shell(self, command_id: str) -> TaskShellView:
        self.calls.append(("create", command_id))
        return TaskShellView(TASK_ID)

    def list_tasks(self) -> TaskListView:
        self.calls.append(("list",))
        return TaskListView(())

    def read_setup_options(self):
        return SETUP_OPTIONS

    def prepare_setup_options(self, value):
        return value

    def remembered_locations(self):
        return RememberedLocations((), (), ())

    def admit_location_candidate(self, candidate):
        path = candidate.path or r"C:\remembered"
        return LocationCandidateResult(
            candidate,
            LocationCandidateState.RESOLVED,
            LocationBinding(
                VolumeId("serial", "NTFS"),
                "",
                path,
                (path,),
                False,
                candidate.location_id,
            ),
            path,
        )

    def read_task_setup(self, task_id):
        return TaskSetupSnapshotView("default", None, None, None, None, SETUP_OPTIONS)

    def replay_start(
        self,
        command_id: str,
        wire_intent: tuple[str, str, str | None],
    ) -> TaskStartView | None:
        self.replays.append((command_id, wire_intent))
        return None

    def start_setup_plan(
        self,
        task_id,
        source: str,
        target: str,
        options,
        *,
        command_id: str | None = None,
        wire_intent=None,
    ) -> TaskStartView:
        self.calls.append(
            (task_id, source, target, options, command_id, wire_intent)
        )
        return TaskStartView(
            task_id=TASK_ID,
            request_id="4" * 32,
            session_id="5" * 32,
        )

    def start_setup_inventory(
        self,
        task_id,
        root,
        *,
        command_id,
        wire_intent,
    ):
        self.calls.append(
            ("inventory", task_id, root, command_id, wire_intent)
        )
        return TaskStartView(task_id, "4" * 32, "5" * 32)

    def start_plan_again(
        self,
        task_id,
        *,
        source_mount,
        target_mount,
        command_id,
        wire_intent,
    ):
        self.calls.append(
            (
                "plan-again",
                task_id,
                source_mount,
                target_mount,
                command_id,
                wire_intent,
            )
        )
        return TaskStartView("task-" + "4" * 32, "6" * 32, "7" * 32)

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

    def drain_for_bridge(
        self,
        task_id: str,
        session_id: str,
        drain_id: str,
        *,
        replay_from: int | None,
    ) -> object:
        from namisync.interfaces.web.bridge import (
            _admit_task_drain_response_prefix,
        )

        result = self.drain(
            task_id,
            session_id,
            drain_id,
            replay_from=replay_from,
        )
        if type(result) is not TaskDrainView:
            return result
        return _admit_task_drain_response_prefix(
            result.task_id,
            result.session_id,
            result.drain_id,
            result.updates,
        )

    def request_task_close(
        self,
        task_id: str,
        session_id: str | None,
    ) -> TaskCloseRequestView:
        self.calls.append(("close", task_id, session_id))
        return TaskCloseRequestView(task_id, session_id, "closed")

    def release_terminal_session(
        self,
        task_id: str,
        session_id: str,
    ) -> TaskSessionReleaseView:
        self.calls.append(("release", task_id, session_id))
        return TaskSessionReleaseView(task_id, session_id)


class _Cosmetics:
    def __init__(
        self,
        *,
        read_result: object | None = None,
        replace_result: object | None = None,
    ) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.read_result = (
            CosmeticSectionSnapshot(
                "appearance",
                1,
                0,
                False,
                AppearanceValue(),
            )
            if read_result is None
            else read_result
        )
        self.replace_result = (
            CosmeticReplaceResult(
                "appearance",
                1,
                1,
                True,
                AppearanceValue(ThemeMode.DARK),
                CosmeticDisposition.APPLIED,
            )
            if replace_result is None
            else replace_result
        )

    def read_section(
        self,
        section: str,
        value_version: int,
    ) -> CosmeticSectionSnapshot:
        self.calls.append(("read", section, value_version))
        return self.read_result  # type: ignore[return-value]

    def replace_section(
        self,
        section: str,
        value_version: int,
        expected_revision: int,
        value: AppearanceValue,
    ) -> CosmeticReplaceResult:
        self.calls.append(
            (
                "replace",
                section,
                value_version,
                expected_revision,
                value,
            )
        )
        return self.replace_result  # type: ignore[return-value]


def _commands(*, picker=lambda: None):
    slots = _Slots()
    service = _Service()
    return (
        production_command_specs(
            picker=picker,
            slots=slots,
            registry=service,
            cosmetics=_Cosmetics(),
            shell_ready=lambda _generation: None,
            readiness_echo=lambda _generation, _challenge: False,
        ),
        slots,
        service,
    )


def test_production_command_composition_binds_transport_response_codec_when_supported() -> None:
    class Registry(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.bindings: list[object] = []

        def bind_response_codec(self, response_codec: object) -> None:
            self.bindings.append(response_codec)

    registry = Registry()
    production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=registry,
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    assert len(registry.bindings) == 1
    codec = registry.bindings[0]
    assert type(codec) is _TaskDrainResponseCodec
    assert codec.response_too_large_error is BridgeResponseTooLargeError
    assert codec.admit is _admit_task_drain_response_prefix
    assert codec.peek is _peek_task_drain_response
    assert codec.consume is _consume_task_drain_response


def test_br_g_32_production_command_table_is_exact_immutable_and_policy_complete() -> None:
    commands, _, _ = _commands()

    assert tuple(commands) == (
        "shell_ready",
        "readiness_echo",
        "pick_folder",
        "read_setup",
        "probe_recent_pairs",
        "prepare_setup",
        "admit_location",
        "create_task",
        "list_tasks",
        "start_plan",
        "start_inventory",
        "plan_again",
        "next_events",
        "release_terminal_session",
        "close_task",
        "read_cosmetic_section",
        "replace_cosmetic_section",
    )
    assert "test_report" not in commands
    assert {
        name for name, spec in commands.items()
        if spec.work is CommandWork.ASYNC_SMALL
    } == {
        "create_task",
        "start_plan",
        "start_inventory",
        "plan_again",
        "release_terminal_session",
        "close_task",
        "probe_recent_pairs",
    }
    assert all(
        spec.work is CommandWork.DIRECT
        for name, spec in commands.items()
        if name not in {
            "create_task",
            "start_plan",
            "start_inventory",
            "plan_again",
            "release_terminal_session",
            "close_task",
            "probe_recent_pairs",
        }
    )
    assert (
        commands["shell_ready"].access,
        commands["shell_ready"].command_id,
        commands["shell_ready"].revision,
        commands["shell_ready"].timeout,
        commands["shell_ready"].retry,
        commands["shell_ready"].phase,
    ) == (
        CommandAccess.READ_ONLY,
        FieldRequirement.FORBIDDEN,
        FieldRequirement.FORBIDDEN,
        CommandTimeout.STARTUP_5_SECONDS,
        CommandRetry.NONE,
        CommandPhase.BOOTSTRAP,
    )
    assert all(
        spec.phase is CommandPhase.OPEN
        for name, spec in commands.items()
        if name not in {"shell_ready", "readiness_echo"}
    )
    assert (
        commands["readiness_echo"].access,
        commands["readiness_echo"].command_id,
        commands["readiness_echo"].revision,
        commands["readiness_echo"].timeout,
        commands["readiness_echo"].retry,
        commands["readiness_echo"].phase,
    ) == (
        CommandAccess.READ_ONLY,
        FieldRequirement.FORBIDDEN,
        FieldRequirement.FORBIDDEN,
        CommandTimeout.STARTUP_5_SECONDS,
        CommandRetry.SAME_PAYLOAD_ONCE,
        CommandPhase.BOOTSTRAP,
    )
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
        commands["create_task"].access,
        commands["create_task"].command_id,
        commands["create_task"].revision,
        commands["create_task"].timeout,
        commands["create_task"].retry,
    ) == (
        CommandAccess.MUTATING,
        FieldRequirement.REQUIRED,
        FieldRequirement.FORBIDDEN,
        CommandTimeout.MUTATION_30_SECONDS,
        CommandRetry.SAME_COMMAND_ONCE,
    )
    assert (
        commands["list_tasks"].access,
        commands["list_tasks"].command_id,
        commands["list_tasks"].revision,
        commands["list_tasks"].timeout,
        commands["list_tasks"].retry,
    ) == (
        CommandAccess.READ_ONLY,
        FieldRequirement.FORBIDDEN,
        FieldRequirement.FORBIDDEN,
        CommandTimeout.LOCAL_5_SECONDS,
        CommandRetry.SAME_PAYLOAD_ONCE,
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
    for command_name in ("start_inventory", "plan_again"):
        command = commands[command_name]
        assert (
            command.access,
            command.command_id,
            command.revision,
            command.timeout,
            command.retry,
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
    assert (
        commands["read_cosmetic_section"].access,
        commands["read_cosmetic_section"].command_id,
        commands["read_cosmetic_section"].revision,
        commands["read_cosmetic_section"].timeout,
        commands["read_cosmetic_section"].retry,
    ) == (
        CommandAccess.READ_ONLY,
        FieldRequirement.FORBIDDEN,
        FieldRequirement.FORBIDDEN,
        CommandTimeout.LOCAL_5_SECONDS,
        CommandRetry.SAME_PAYLOAD_ONCE,
    )
    assert (
        commands["replace_cosmetic_section"].access,
        commands["replace_cosmetic_section"].command_id,
        commands["replace_cosmetic_section"].revision,
        commands["replace_cosmetic_section"].timeout,
        commands["replace_cosmetic_section"].retry,
    ) == (
        CommandAccess.MUTATING,
        FieldRequirement.FORBIDDEN,
        FieldRequirement.REQUIRED,
        CommandTimeout.LOCAL_5_SECONDS,
        CommandRetry.NONE,
    )

    with pytest.raises(TypeError):
        commands["future_command"] = commands["pick_folder"]  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        commands["pick_folder"].retry = CommandRetry.SAME_COMMAND_ONCE  # type: ignore[misc]


def test_async_small_real_command_projections_have_exact_bounded_completion_shapes() -> None:
    commands, _, _ = _commands()
    cases = (
        (
            "create_task",
            {"command_id": COMMAND_ID},
            {"task_id": TASK_ID},
            345,
        ),
        (
            "start_plan",
            {
                "task_id": TASK_ID,
                "command_id": COMMAND_ID,
                "source_id": SOURCE_ID,
                "target_id": TARGET_ID,
                "options": _setup_options_payload(),
            },
            {
                "task_id": TASK_ID,
                "request_id": "4" * 32,
                "session_id": "5" * 32,
            },
            441,
        ),
        (
            "release_terminal_session",
            {"task_id": TASK_ID, "session_id": SESSION_ID},
            {"task_id": TASK_ID, "session_id": SESSION_ID},
            393,
        ),
        (
            "close_task",
            {"task_id": TASK_ID, "session_id": SESSION_ID},
            {
                "task_id": TASK_ID,
                "session_id": SESSION_ID,
                "disposition": "closed",
            },
            416,
        ),
    )

    for name, payload, expected, expected_bytes in cases:
        projected = to_primitive_view(_invoke(commands[name], payload))
        assert projected == expected
        envelope = {
            "kind": "namisync.command-completion.v1",
            "phase": "completion",
            "generation": MAX_JAVASCRIPT_SAFE_INTEGER,
            "request_id": "f" * 32,
            "completion_token": "f" * 32,
            "response": {
                "schema_version": 1,
                "request_id": "f" * 32,
                "ok": True,
                "result": projected,
            },
        }
        encoded = json.dumps(
            envelope,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

        assert len(encoded.encode("utf-8")) == expected_bytes
        assert len(encoded.encode("utf-8")) <= 65_536


def test_br_g_32_command_composition_is_constructor_only() -> None:
    signature = inspect.signature(production_command_specs)
    source = inspect.getsource(
        __import__(
            "namisync.interfaces.web.commands",
            fromlist=["commands"],
        )
    )

    assert tuple(signature.parameters) == (
        "picker",
        "slots",
        "registry",
        "cosmetics",
        "shell_ready",
        "readiness_echo",
        "appearance_acknowledged",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    assert "extra_commands" not in source
    assert "register" not in source
    assert "test_report" not in source

    assert (
        signature.parameters["shell_ready"].default is inspect.Parameter.empty
    )
    assert (
        signature.parameters["readiness_echo"].default
        is inspect.Parameter.empty
    )
    assert signature.parameters["appearance_acknowledged"].default is None
    assert signature.parameters["cosmetics"].default is inspect.Parameter.empty


def test_br_g_46_cosmetic_rows_use_only_the_typed_cosmetic_authority() -> None:
    cosmetics = _Cosmetics(
        read_result=CosmeticSectionSnapshot(
            "appearance",
            1,
            7,
            True,
            AppearanceValue(ThemeMode.LIGHT),
        ),
        replace_result=CosmeticReplaceResult(
            "appearance",
            1,
            7,
            True,
            AppearanceValue(ThemeMode.LIGHT),
            CosmeticDisposition.CONFLICT,
        ),
    )
    slots = _Slots()
    service = _Service()
    commands = production_command_specs(
        picker=lambda: None,
        slots=slots,
        registry=service,
        cosmetics=cosmetics,
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    assert _invoke(
        commands["read_cosmetic_section"],
        {
            "section": "appearance",
            "value_version": 1,
            "applied_presentation_revision": None,
        },
    ) == {
        "section": "appearance",
        "value_version": 1,
        "revision": 7,
        "dirty": True,
        "value": {"theme": "light"},
    }
    assert _invoke(
        commands["replace_cosmetic_section"],
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 6,
            "value": {"theme": "dark"},
        },
    ) == {
        "section": "appearance",
        "value_version": 1,
        "revision": 7,
        "dirty": True,
        "value": {"theme": "light"},
        "disposition": "conflict",
    }
    assert cosmetics.calls == [
        ("read", "appearance", 1),
        (
            "replace",
            "appearance",
            1,
            6,
            AppearanceValue(ThemeMode.DARK),
        ),
    ]
    assert slots.stored == []
    assert slots.resolved == []
    assert service.calls == []
    assert service.replays == []


def test_read_cosmetic_section_reports_only_an_exact_applied_revision() -> None:
    acknowledgments: list[int] = []
    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=_Service(),
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
        appearance_acknowledged=acknowledgments.append,
    )

    for revision in (23, MAX_JAVASCRIPT_SAFE_INTEGER, None):
        _invoke(
            commands["read_cosmetic_section"],
            {
                "section": "appearance",
                "value_version": 1,
                "applied_presentation_revision": revision,
            },
        )

    assert acknowledgments == [23, MAX_JAVASCRIPT_SAFE_INTEGER]


@pytest.mark.parametrize(
    ("theme", "expected_revision"),
    [
        ("system", 0),
        ("light", 1),
        ("dark", 9_007_199_254_740_991),
    ],
)
def test_br_g_46_replace_cosmetic_section_accepts_exact_v1_values(
    theme: str,
    expected_revision: int,
) -> None:
    cosmetics = _Cosmetics()
    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=_Service(),
        cosmetics=cosmetics,
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    _invoke(
        commands["replace_cosmetic_section"],
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": expected_revision,
            "value": {"theme": theme},
        },
    )

    assert cosmetics.calls == [
        (
            "replace",
            "appearance",
            1,
            expected_revision,
            AppearanceValue(ThemeMode(theme)),
        )
    ]


class _PayloadDict(dict[object, object]):
    pass


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"section": "appearance"},
        {"section": "appearance", "value_version": 1, "extra": None},
        {"section": "other", "value_version": 1},
        {"section": 1, "value_version": 1},
        {"section": "appearance", "value_version": True},
        {"section": "appearance", "value_version": 1.0},
        {"section": "appearance", "value_version": 2},
        {
            "section": "appearance",
            "value_version": 1,
            "applied_presentation_revision": True,
        },
        {
            "section": "appearance",
            "value_version": 1,
            "applied_presentation_revision": -1,
        },
        {
            "section": "appearance",
            "value_version": 1,
            "applied_presentation_revision": (
                MAX_JAVASCRIPT_SAFE_INTEGER + 1
            ),
        },
        _PayloadDict(section="appearance", value_version=1),
    ],
)
def test_br_g_46_read_cosmetic_section_rejects_non_exact_payloads(
    payload: object,
) -> None:
    commands, _, _ = _commands()

    with pytest.raises(CommandPayloadError):
        _invoke(commands["read_cosmetic_section"], payload)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 0,
        },
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 0,
            "value": {"theme": "system"},
            "extra": None,
        },
        {
            "section": "other",
            "value_version": 1,
            "expected_revision": 0,
            "value": {"theme": "system"},
        },
        {
            "section": "appearance",
            "value_version": True,
            "expected_revision": 0,
            "value": {"theme": "system"},
        },
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": True,
            "value": {"theme": "system"},
        },
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": -1,
            "value": {"theme": "system"},
        },
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 1.0,
            "value": {"theme": "system"},
        },
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 9_007_199_254_740_992,
            "value": {"theme": "system"},
        },
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 0,
            "value": None,
        },
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 0,
            "value": {},
        },
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 0,
            "value": {"theme": "system", "extra": None},
        },
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 0,
            "value": {"theme": "SYSTEM"},
        },
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 0,
            "value": {"theme": 1},
        },
        {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 0,
            "value": _PayloadDict(theme="system"),
        },
        _PayloadDict(
            section="appearance",
            value_version=1,
            expected_revision=0,
            value={"theme": "system"},
        ),
    ],
)
def test_br_g_46_replace_cosmetic_section_rejects_non_exact_payloads(
    payload: object,
) -> None:
    commands, _, _ = _commands()

    with pytest.raises(CommandPayloadError):
        _invoke(commands["replace_cosmetic_section"], payload)


@pytest.mark.parametrize(
    ("command", "result"),
    [
        (
            "read_cosmetic_section",
            CosmeticReplaceResult(
                "appearance",
                1,
                0,
                False,
                AppearanceValue(),
                CosmeticDisposition.NOOP,
            ),
        ),
        (
            "read_cosmetic_section",
            CosmeticSectionSnapshot(
                "appearance",
                1,
                True,  # type: ignore[arg-type]
                False,
                AppearanceValue(),
            ),
        ),
        (
            "read_cosmetic_section",
            CosmeticSectionSnapshot(
                "appearance",
                1,
                9_007_199_254_740_992,
                False,
                AppearanceValue(),
            ),
        ),
        (
            "read_cosmetic_section",
            CosmeticSectionSnapshot(
                "other",
                1,
                0,
                False,
                AppearanceValue(),
            ),
        ),
        (
            "read_cosmetic_section",
            CosmeticSectionSnapshot(
                "appearance",
                1,
                0,
                0,  # type: ignore[arg-type]
                AppearanceValue(),
            ),
        ),
        (
            "replace_cosmetic_section",
            CosmeticSectionSnapshot(
                "appearance",
                1,
                0,
                False,
                AppearanceValue(),
            ),
        ),
        (
            "replace_cosmetic_section",
            CosmeticReplaceResult(
                "appearance",
                1,
                0,
                False,
                AppearanceValue(),
                "noop",  # type: ignore[arg-type]
            ),
        ),
    ],
)
def test_br_g_46_cosmetic_rows_reject_invalid_authority_results(
    command: str,
    result: object,
) -> None:
    cosmetics = _Cosmetics(
        read_result=result,
        replace_result=result,
    )
    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=_Service(),
        cosmetics=cosmetics,
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )
    payload = (
        {
            "section": "appearance",
            "value_version": 1,
            "applied_presentation_revision": None,
        }
        if command == "read_cosmetic_section"
        else {
            "section": "appearance",
            "value_version": 1,
            "expected_revision": 0,
            "value": {"theme": "system"},
        }
    )

    with pytest.raises(RuntimeError, match="invalid data"):
        _invoke(commands[command], payload)


@pytest.mark.parametrize(
    ("command", "payload"),
    [
        (
            "read_cosmetic_section",
            {
                "section": "appearance",
                "value_version": 1,
                "applied_presentation_revision": None,
            },
        ),
        (
            "replace_cosmetic_section",
            {
                "section": "appearance",
                "value_version": 1,
                "expected_revision": 0,
                "value": {"theme": "system"},
            },
        ),
    ],
)
def test_br_g_46_cosmetic_rows_are_open_phase_only(
    command: str,
    payload: object,
) -> None:
    cosmetics = _Cosmetics()
    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=_Service(),
        cosmetics=cosmetics,
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    with pytest.raises(CommandAdmissionError):
        _invoke(commands[command], payload, context=BOOTSTRAP_CONTEXT)
    assert cosmetics.calls == []


def test_shell_ready_requires_its_exact_context_and_empty_payload() -> None:
    acknowledgements: list[str] = []
    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=_Service(),
        cosmetics=_Cosmetics(),
        shell_ready=lambda generation: acknowledgements.append(str(generation)),
        readiness_echo=lambda _generation, _challenge: False,
    )

    assert _invoke(
        commands["shell_ready"],
        {},
        context=BOOTSTRAP_CONTEXT,
    ) == {
        "acknowledged": True
    }
    assert acknowledgements == ["7"]
    with pytest.raises(CommandAdmissionError, match="readiness context"):
        _invoke(commands["shell_ready"], {})
    for payload in ({"unexpected": True}, [], None):
        with pytest.raises(CommandPayloadError):
            _invoke(
                commands["shell_ready"],
                payload,
                context=BOOTSTRAP_CONTEXT,
            )
    assert acknowledgements == ["7"]


def test_readiness_echo_requires_exact_context_and_challenge() -> None:
    echoes: list[tuple[int, str]] = []

    def echo(generation: int, challenge: str) -> bool:
        echoes.append((generation, challenge))
        return len(echoes) > 1

    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=_Service(),
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=echo,
    )
    challenge = "a3" * 16

    assert _invoke(
        commands["readiness_echo"],
        {"challenge": challenge},
        context=BOOTSTRAP_CONTEXT,
    ) == {"acknowledged": False}
    assert _invoke(
        commands["readiness_echo"],
        {"challenge": challenge},
        context=BOOTSTRAP_CONTEXT,
    ) == {"acknowledged": True}
    assert echoes == [(7, challenge), (7, challenge)]

    with pytest.raises(CommandAdmissionError, match="readiness context"):
        _invoke(commands["readiness_echo"], {"challenge": challenge})
    for payload in (
        {},
        {"challenge": "A" * 32},
        {"challenge": "a" * 31},
        {"challenge": challenge, "unexpected": True},
        {"challenge": 7},
    ):
        with pytest.raises(CommandPayloadError):
            _invoke(
                commands["readiness_echo"],
                payload,
                context=BOOTSTRAP_CONTEXT,
            )
    assert echoes == [(7, challenge), (7, challenge)]


def test_readiness_echo_refuses_non_boolean_callback_result() -> None:
    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=_Service(),
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: 1,  # type: ignore[return-value]
    )

    with pytest.raises(TypeError, match="returned invalid data"):
        _invoke(
            commands["readiness_echo"],
            {"challenge": "b" * 32},
            context=BOOTSTRAP_CONTEXT,
        )


def test_br_g_32_folder_picker_returns_only_opaque_presentation_data() -> None:
    private_path = r"C:\Users\Someone\secret <folder>"
    commands, slots, _ = _commands(picker=lambda: (private_path,))

    result = _invoke(commands["pick_folder"], {"purpose": "source"})

    assert result == {
        "purpose": "source",
        "state": "resolved",
        "choice_id": SOURCE_ID,
        "continuation_id": None,
        "display": private_path,
        "location_id": None,
        "candidates": [],
        "detail": None,
    }
    assert slots.stored == [(LocationCandidate.literal(private_path), "source")]


def test_br_g_32_folder_picker_cancel_creates_no_slot() -> None:
    commands, slots, _ = _commands(picker=lambda: None)

    assert _invoke(commands["pick_folder"], {"purpose": "target"}) is None
    assert slots.stored == []


def test_probe_recent_pairs_deduplicates_bounded_locations_and_projects_raw_states(
) -> None:
    used_at = datetime(2026, 9, 11, tzinfo=timezone.utc)
    locations = tuple(
        RememberedLocation(
            index,
            VolumeId(f"volume-{index}", "NTFS"),
            f"folder-{index}",
            f"{chr(64 + index)}:\\",
            used_at,
        )
        for index in range(1, 11)
    )
    target_indexes = (5, 5, 7, 8, 9)
    pairs = tuple(
        RememberedPair(index, locations[index - 1], locations[target_index], used_at)
        for index, target_index in enumerate(target_indexes, start=1)
    )
    projected_states = (
        LocationCandidateState.RESOLVED,
        LocationCandidateState.OFFLINE,
        LocationCandidateState.AMBIGUOUS,
        LocationCandidateState.MISSING,
        LocationCandidateState.NOT_DIRECTORY,
        LocationCandidateState.REPARSE,
        LocationCandidateState.PLACEHOLDER,
        LocationCandidateState.REMOTE,
        LocationCandidateState.UNSUPPORTED_VOLUME,
        LocationCandidateState.UNAVAILABLE,
    )

    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.admissions: list[LocationCandidate] = []

        def remembered_locations(self):
            return RememberedLocations((), (), pairs)

        def admit_location_candidate(self, candidate):
            self.admissions.append(candidate)
            state = projected_states[candidate.location_id - 1]
            if state is not LocationCandidateState.RESOLVED:
                return LocationCandidateResult(candidate, state)
            return super().admit_location_candidate(candidate)

    service = Service()
    slots = _Slots()
    commands = production_command_specs(
        picker=lambda: None,
        slots=slots,
        registry=service,
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    assert _invoke(commands["probe_recent_pairs"], {}) == {
        "pairs": [
            {
                "mapping_id": str(index),
                "source_id": str(index),
                "target_id": str(target_indexes[index - 1] + 1),
                "source_state": projected_states[index - 1].value,
                "target_state": projected_states[target_indexes[index - 1]].value,
            }
            for index in range(1, 6)
        ]
    }
    assert service.admissions == [
        LocationCandidate.remembered(index)
        for index in (1, 6, 2, 3, 8, 4, 9, 5, 10)
    ]
    assert slots.stored == []
    assert slots.resolved == []


@pytest.mark.parametrize("payload", [None, [], {"unexpected": None}])
def test_probe_recent_pairs_rejects_nonempty_or_nonobject_payload(
    payload: object,
) -> None:
    commands, _, service = _commands()

    with pytest.raises(CommandPayloadError, match="probe_recent_pairs payload"):
        _invoke(commands["probe_recent_pairs"], payload)

    assert service.calls == []


def test_br_g_32_ambiguous_picker_requires_opaque_fresh_continuation(
    monkeypatch,
) -> None:
    candidate = LocationCandidate.literal(r"C:\private\source")
    first_binding = LocationBinding(
        VolumeId("serial", "NTFS"),
        "folder",
        "C:\\",
        ("C:\\", "D:\\"),
        True,
    )
    candidates = first_binding.expected_mounts
    first_resolution = VolumeResolution(
        VolumeResolutionState.AMBIGUOUS,
        first_binding,
        candidates=candidates,
        detail="Choose a current mount",
    )

    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.admissions = []
            self.changed = False

        def admit_location_candidate(self, value):
            self.admissions.append(value)
            if value.selected_mount is None:
                return LocationCandidateResult(
                    value,
                    LocationCandidateState.AMBIGUOUS,
                    first_binding,
                    None,
                    candidates,
                    "Choose a current mount",
                    first_resolution,
                )
            return LocationCandidateResult(
                value,
                LocationCandidateState.RESOLVED,
                LocationBinding(
                    first_binding.volume_id,
                    first_binding.volume_relative_path,
                    value.selected_mount,
                    candidates,
                    False,
                ),
                value.selected_mount + "folder",
                candidates,
            )

    service = Service()
    slots = FolderSlotTable(token=iter(("1" * 32, "2" * 32)).__next__)
    admitted_containers = []
    snapshot_response = bridge_module.snapshot_bridge_response_result

    def capture_admission(value, request_id, maximum_json_bytes=None):
        admitted_containers.append(value)
        if maximum_json_bytes is None:
            return snapshot_response(value, request_id)
        return snapshot_response(value, request_id, maximum_json_bytes)

    monkeypatch.setattr(
        bridge_module,
        "snapshot_bridge_response_result",
        capture_admission,
    )
    commands = production_command_specs(
        picker=lambda: (candidate.path,),
        slots=slots,
        registry=service,
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    ambiguous = _invoke(commands["pick_folder"], {"purpose": "source"})
    assert ambiguous["choice_id"] is None
    assert ambiguous["continuation_id"] == "slot-" + "1" * 32
    assert len(admitted_containers) == 1
    admitted_container = admitted_containers[0]
    assert set(admitted_container) == {"continuation", "response"}
    assert admitted_container["response"] == ambiguous
    assert set(admitted_container["continuation"]) == {
        "candidate", "binding", "candidates",
    }
    resolved = _invoke(
        commands["admit_location"],
        {
            "purpose": "source",
            "continuation_id": ambiguous["continuation_id"],
            "mount_index": 1,
        },
    )
    assert resolved["state"] == "resolved"
    assert resolved["choice_id"] == "slot-" + "2" * 32
    assert resolved["continuation_id"] is None
    assert service.admissions == [
        candidate,
        LocationCandidate.literal(candidate.path, selected_mount="D:\\"),
    ]
    service.changed = True

    original = service.admit_location_candidate

    def changed_mount_admission(value):
        result = original(value)
        if value.selected_mount is None:
            return result
        changed_mount = "D:\\" if value.selected_mount == "C:\\" else "C:\\"
        return LocationCandidateResult(
            value,
            LocationCandidateState.RESOLVED,
            LocationBinding(
                first_binding.volume_id,
                first_binding.volume_relative_path,
                changed_mount,
                candidates,
                False,
            ),
            changed_mount + "folder",
            candidates,
        )
    service.admit_location_candidate = changed_mount_admission
    changed = _invoke(
        commands["admit_location"],
        {
            "purpose": "source",
            "continuation_id": ambiguous["continuation_id"],
            "mount_index": 0,
        },
    )
    assert changed["state"] == "changed"
    assert changed["choice_id"] is None
    assert changed["continuation_id"] is None

    def ambiguous_admission(value):
        return LocationCandidateResult(
            value,
            LocationCandidateState.AMBIGUOUS,
            first_binding,
            None,
            candidates,
            "Choose a current mount",
            first_resolution,
        )

    service.admit_location_candidate = ambiguous_admission
    still_ambiguous = _invoke(
        commands["admit_location"],
        {
            "purpose": "source",
            "continuation_id": ambiguous["continuation_id"],
            "mount_index": 0,
        },
    )
    assert still_ambiguous["state"] == "ambiguous"
    assert still_ambiguous["choice_id"] is None
    assert still_ambiguous["continuation_id"] is None

    reordered = ("D:\\", "C:\\")
    reordered_binding = LocationBinding(
        first_binding.volume_id,
        first_binding.volume_relative_path,
        reordered[0],
        reordered,
        True,
    )
    reordered_resolution = VolumeResolution(
        VolumeResolutionState.AMBIGUOUS,
        reordered_binding,
        candidates=reordered,
        detail="Choose a current mount",
    )
    service.admit_location_candidate = lambda value: LocationCandidateResult(
        value,
        LocationCandidateState.AMBIGUOUS,
        reordered_binding,
        None,
        reordered,
        "Choose a current mount",
        reordered_resolution,
    )
    changed_order = _invoke(
        commands["admit_location"],
        {
            "purpose": "source",
            "continuation_id": ambiguous["continuation_id"],
            "mount_index": 0,
        },
    )
    assert changed_order["state"] == "changed"
    assert changed_order["candidates"] == list(reordered)

    offline_resolution = VolumeResolution(
        VolumeResolutionState.OFFLINE,
        first_binding,
        candidates=(),
        detail="recorded volume is not mounted",
    )
    service.admit_location_candidate = lambda value: LocationCandidateResult(
        value,
        LocationCandidateState.OFFLINE,
        first_binding,
        None,
        (),
        "recorded volume is not mounted",
        offline_resolution,
    )
    disappeared = _invoke(
        commands["admit_location"],
        {
            "purpose": "source",
            "continuation_id": ambiguous["continuation_id"],
            "mount_index": 0,
        },
    )
    assert disappeared["state"] == "offline"
    assert disappeared["candidates"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "candidate": {
                "kind": "literal_path",
                "path": r"C:\source",
                "selected_mount": None,
            },
        },
        {"purpose": "source"},
        {
            "purpose": "source",
            "continuation_id": SOURCE_ID,
            "mount_index": 0,
            "unexpected": None,
        },
    ],
)
def test_br_g_32_admit_location_validates_exact_keys_before_indexing(
    payload: object,
) -> None:
    commands, _, service = _commands()

    with pytest.raises(CommandPayloadError, match="admit_location payload"):
        _invoke(commands["admit_location"], payload)

    assert service.calls == []


def test_br_g_32_synthetic_escape_projection_admits_combined_size_before_eviction() -> None:
    mount_paths = tuple(
        "\x01" * 32_765 + f"{index:02d}"
        for index in range(27)
    )
    candidate = LocationCandidate.literal(r"C:\private\source")
    binding = LocationBinding(
        VolumeId("serial", "NTFS"),
        "folder",
        mount_paths[0],
        mount_paths,
        True,
    )
    resolution = VolumeResolution(
        VolumeResolutionState.AMBIGUOUS,
        binding,
        candidates=mount_paths,
        detail="Choose a current mount",
    )
    result = LocationCandidateResult(
        candidate,
        LocationCandidateState.AMBIGUOUS,
        binding,
        None,
        mount_paths,
        "Choose a current mount",
        resolution,
    )
    public_choice = {
        "purpose": "source",
        "state": "ambiguous",
        "choice_id": None,
        "continuation_id": "slot-" + f"{32:032x}",
        "display": candidate.path,
        "location_id": None,
        "candidates": list(mount_paths),
        "detail": "Choose a current mount",
    }
    assert snapshot_bridge_response_result(public_choice, "0" * 32) == public_choice

    class Service(_Service):
        def admit_location_candidate(self, value):
            assert value == candidate
            return result

    tokens = iter(f"{index:032x}" for index in range(64))
    slots = FolderSlotTable(token=tokens.__next__)
    retained = {
        slots.store(f"path-{index}", purpose="source")[0]
        for index in range(32)
    }
    commands = production_command_specs(
        picker=lambda: (candidate.path,),
        slots=slots,
        registry=Service(),
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    with pytest.raises(BridgeResponseTooLargeError):
        _invoke(commands["pick_folder"], {"purpose": "source"})

    assert set(slots._entries) == retained


@pytest.mark.parametrize(
    "selected",
    ["C:\\bare", (), ("one", "two"), (7,), ("\ud800",)],
)
def test_br_g_32_folder_picker_refuses_invalid_native_results(
    selected: object,
) -> None:
    commands, slots, _ = _commands(picker=lambda: selected)  # type: ignore[arg-type]

    with pytest.raises(PickerUnavailableError):
        _invoke(commands["pick_folder"], {"purpose": "source"})

    assert slots.stored == []


def test_br_g_32_folder_picker_exception_is_typed_without_storing_a_slot() -> None:
    private_detail = "C:\\private\\picker failure"

    def refuse():
        raise OSError(private_detail)

    commands, slots, _ = _commands(picker=refuse)

    with pytest.raises(PickerUnavailableError) as captured:
        _invoke(commands["pick_folder"], {"purpose": "source"})

    assert private_detail not in str(captured.value)
    assert slots.stored == []


def test_br_g_32_folder_picker_system_exit_cannot_cross_the_command_boundary() -> None:
    def refuse():
        raise SystemExit("private native termination detail")

    commands, slots, _ = _commands(picker=refuse)

    with pytest.raises(PickerUnavailableError) as captured:
        _invoke(commands["pick_folder"], {"purpose": "source"})

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
        def store(self, candidate, *, purpose: str, display=None):
            del candidate, purpose, display
            return stored

    slots = InvalidSlots()
    commands = production_command_specs(
        picker=lambda: (r"C:\private",),
        slots=slots,
        registry=_Service(),
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    with pytest.raises(RuntimeError, match="slot authority"):
        _invoke(commands["pick_folder"], {"purpose": "source"})


def test_br_g_32_start_plan_resolves_slots_and_delegates_once() -> None:
    commands, slots, service = _commands()
    payload = {
        "task_id": TASK_ID,
        "command_id": COMMAND_ID,
        "source_id": SOURCE_ID,
        "target_id": TARGET_ID,
        "options": _setup_options_payload(),
    }

    result = _invoke(commands["start_plan"], payload)

    assert result == TaskStartView(
        task_id=TASK_ID,
        request_id="4" * 32,
        session_id="5" * 32,
    )
    assert slots.resolved == [(SOURCE_ID, TARGET_ID)]
    assert service.replays == [
        (
            COMMAND_ID,
            (
                "start-plan",
                TASK_ID,
                SOURCE_ID,
                TARGET_ID,
                SETUP_OPTIONS_SIGNATURE,
            ),
        )
    ]
    assert service.calls == [
        (
            TASK_ID,
            LocationCandidate.literal(r"C:\private\source"),
            LocationCandidate.literal(r"D:\private\target"),
            SETUP_OPTIONS,
            COMMAND_ID,
            (
                "start-plan",
                TASK_ID,
                SOURCE_ID,
                TARGET_ID,
                SETUP_OPTIONS_SIGNATURE,
            ),
        )
    ]
    assert "private" not in repr(payload)


def test_br_g_32_real_task_commands_use_domain_blind_scalar_signatures() -> None:
    class Runtime:
        def __init__(self) -> None:
            self.artifacts: dict[str, object] = {}

        def prepare_setup_options(self, value):
            value.__post_init__()
            return value

        def admit_location_candidate(self, candidate):
            assert candidate.path is not None
            root = candidate.path
            mount = root[:3]
            binding = LocationBinding(
                VolumeId(root[0].lower(), "NTFS"),
                root[3:],
                mount,
                (mount,),
                False,
            )
            return LocationCandidateResult(
                candidate,
                LocationCandidateState.RESOLVED,
                binding,
                root,
                (mount,),
            )

        def admit_plan_locations(self, source, target):
            return source, target

        def create_plan_request(
            self,
            request_id,
            source_path,
            target_path,
            **values,
        ):
            request = SimpleNamespace(
                request_id=request_id,
                source_path=source_path,
                target_path=target_path,
                options=values["options"],
                source_binding=values["source_binding"],
                target_binding=values["target_binding"],
                verify_after_execute=values["verify_after_execute"],
            )
            self.artifacts[request_id] = SimpleNamespace(request=request)
            return request

        def get_plan(self, request_id):
            return self.artifacts[request_id]

        def resolve_reviewed_location(self, binding, *, selected_mount=None):
            mount = selected_mount or binding.selected_mount
            return VolumeResolution(
                VolumeResolutionState.RESOLVED,
                binding,
                mount + binding.volume_relative_path,
                mount,
                candidates=binding.expected_mounts,
            )

        def drop_execution_details(self, _run_id):
            pass

        def drop_inventory_details(self, _request_id):
            pass

        def close(self):
            pass

    class Dispatcher:
        def __init__(self) -> None:
            self.submissions: list[tuple[str, object]] = []

        def submit(self, kind, request, *, attach=None):
            self.submissions.append((kind, request))
            session_id = f"{700 + len(self.submissions):032x}"
            if attach is not None:
                attach(session_id, SimpleNamespace(close=lambda: None))
            return session_id

    class Observer:
        def adopt(self, _session_id, _sink, _stream):
            return lambda: None

        def release(self, _session_id):
            pass

        def close(self):
            pass

    runtime = Runtime()
    dispatcher = Dispatcher()
    service = make_service(
        runtime=runtime,
        dispatcher=dispatcher,
        observer=Observer(),
    )
    registry = TaskRegistry(service)
    slot_tokens = iter(f"{value:032x}" for value in range(1, 20))
    slots = FolderSlotTable(token=slot_tokens.__next__)
    commands = production_command_specs(
        picker=lambda: None,
        slots=slots,
        registry=registry,
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    plan_shell = _invoke(
        commands["create_task"], {"command_id": "b1" * 16}
    )
    source_id, _ = slots.store(
        LocationCandidate.literal(r"C:\source"), purpose="source"
    )
    target_id, _ = slots.store(
        LocationCandidate.literal(r"D:\target"), purpose="target"
    )
    options = {
        "filters": ["a/*", "b/*"],
        "deletion_policy": "additive",
        "trash_on_update": False,
        "preservation": {
            "preserve_ads": False,
            "preserve_created": False,
            "preserve_acl": True,
        },
        "propagate_source_casing": True,
        "verify_after_execute": True,
    }
    plan_payload = {
        "task_id": plan_shell.task_id,
        "command_id": "b2" * 16,
        "source_id": source_id,
        "target_id": target_id,
        "options": options,
    }
    plan_signature = (
        "start-plan",
        plan_shell.task_id,
        source_id,
        target_id,
        (
            ("a/*", "b/*"),
            "additive",
            False,
            (False, False, True),
            True,
            True,
        ),
    )
    planned = _invoke(commands["start_plan"], plan_payload)
    assert _invoke(commands["start_plan"], plan_payload) == planned
    assert service._lifecycle.replay_start(
        "b2" * 16, "task-plan", plan_signature
    ).task_id == plan_shell.task_id
    with pytest.raises(CommandConflictError):
        _invoke(
            commands["start_plan"],
            {
                **plan_payload,
                "options": {**options, "verify_after_execute": False},
            },
        )

    inventory_shell = _invoke(
        commands["create_task"], {"command_id": "b3" * 16}
    )
    root_id, _ = slots.store(
        LocationCandidate.literal(r"E:\inventory"), purpose="inventory"
    )
    inventory_signature = (
        "start-inventory",
        inventory_shell.task_id,
        root_id,
    )
    inventoried = _invoke(
        commands["start_inventory"],
        {
            "task_id": inventory_shell.task_id,
            "command_id": "b4" * 16,
            "root_id": root_id,
        },
    )
    assert inventoried.task_id == inventory_shell.task_id
    assert service._lifecycle.replay_start(
        "b4" * 16, "task-inventory", inventory_signature
    ).task_id == inventory_shell.task_id

    plan_again_signature = (
        "plan-again",
        plan_shell.task_id,
        None,
        None,
    )
    replanned = _invoke(
        commands["plan_again"],
        {
            "task_id": plan_shell.task_id,
            "command_id": "b5" * 16,
            "source_mount": None,
            "target_mount": None,
        },
    )
    assert replanned.task_id != plan_shell.task_id
    assert service._lifecycle.replay_start(
        "b5" * 16, "task-plan", plan_again_signature
    ).task_id == replanned.task_id
    assert [kind for kind, _request in dispatcher.submissions] == [
        "sync-plan",
        "inventory",
        "sync-plan",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "task_id": TASK_ID,
            "source_id": SOURCE_ID,
            "target_id": TARGET_ID,
            "options": _setup_options_payload(),
        },
        {
            "task_id": TASK_ID,
            "command_id": COMMAND_ID,
            "source_id": SOURCE_ID,
            "target_id": TARGET_ID,
            "options": _setup_options_payload(),
            "revision": 0,
        },
    ],
)
def test_br_g_32_start_plan_requires_command_id_and_forbids_revision(
    payload: dict[str, object],
) -> None:
    commands, slots, registry = _commands()

    with pytest.raises(CommandPayloadError):
        _invoke(commands["start_plan"], payload)

    assert slots.resolved == []
    assert registry.replays == []
    assert registry.calls == []


@pytest.mark.parametrize("retirement", ["expiry", "eviction"])
def test_br_g_32_start_plan_replays_before_volatile_slots_are_resolved(
    retirement: str,
) -> None:
    class Clock:
        now = 0.0

        def __call__(self) -> float:
            return self.now

    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.retained = None
            self.intent = None

        def replay_start(self, command_id, wire_intent):
            self.replays.append((command_id, wire_intent))
            if self.intent is not None and wire_intent != self.intent:
                raise TaskIntentConflictError("task command intent conflicts")
            return self.retained

        def start_setup_plan(
            self,
            task_id,
            source,
            target,
            options,
            *,
            command_id,
            wire_intent,
        ):
            self.calls.append((task_id, source, target, options, command_id))
            self.intent = wire_intent
            self.retained = TaskStartView(task_id, "8" * 32, "9" * 32)
            return self.retained

    clock = Clock()
    slot_tokens = iter(f"{value:032x}" for value in range(1, 100))
    slots = FolderSlotTable(clock=clock, token=lambda: next(slot_tokens))
    source_id, _ = slots.store(
        LocationCandidate.literal(r"C:\source"), purpose="source"
    )
    target_id, _ = slots.store(
        LocationCandidate.literal(r"D:\target"), purpose="target"
    )
    service = Service()
    commands = production_command_specs(
        picker=lambda: None,
        slots=slots,
        registry=service,
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )
    payload = {
        "task_id": TASK_ID,
        "command_id": COMMAND_ID,
        "source_id": source_id,
        "target_id": target_id,
        "options": _setup_options_payload(),
    }

    lost_response = _invoke(commands["start_plan"], payload)
    if retirement == "expiry":
        clock.now = 1_801.0
    else:
        for value in range(32):
            purpose = "source" if value % 2 == 0 else "target"
            slots.store(
                LocationCandidate.literal(f"C:\\replacement-{value}"),
                purpose=purpose,
            )
    with pytest.raises(SlotUnavailableError):
        slots.resolve_pair(source_id, target_id)

    replay = _invoke(commands["start_plan"], payload)

    assert replay == lost_response
    assert service.calls == [
        (
            TASK_ID,
            LocationCandidate.literal(r"C:\source"),
            LocationCandidate.literal(r"D:\target"),
            SETUP_OPTIONS,
            COMMAND_ID,
        )
    ]
    with pytest.raises(CommandConflictError):
        _invoke(
            commands["start_plan"],
            {**payload, "options": {**_setup_options_payload(), "filters": ["x"]}},
        )


def test_br_g_33_next_events_delegates_exact_authority_and_returns_typed_view() -> None:
    commands, slots, registry = _commands()

    result = _invoke(commands["next_events"],
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

    result = _invoke(commands["close_task"],
        {"task_id": TASK_ID, "session_id": SESSION_ID}
    )

    assert result == TaskCloseRequestView(TASK_ID, SESSION_ID, "closed")
    assert registry.calls == [("close", TASK_ID, SESSION_ID)]
    assert slots.resolved == []


def test_task_shell_create_list_and_close_use_no_domain_identity() -> None:
    commands, slots, registry = _commands()

    created = _invoke(commands["create_task"], {"command_id": COMMAND_ID})
    listed = _invoke(commands["list_tasks"], {})
    closed = _invoke(
        commands["close_task"],
        {"task_id": TASK_ID, "session_id": None},
    )

    assert created == TaskShellView(TASK_ID)
    assert listed == TaskListView(())
    assert closed == TaskCloseRequestView(TASK_ID, None, "closed")
    assert registry.calls == [
        ("create", COMMAND_ID),
        ("list",),
        ("close", TASK_ID, None),
    ]
    assert registry.replays == []
    assert slots.resolved == []


def test_terminal_session_release_delegates_and_echoes_exact_identity() -> None:
    commands, slots, registry = _commands()

    result = _invoke(commands["release_terminal_session"],
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
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    with pytest.raises(RuntimeError, match="invalid release data"):
        _invoke(commands["release_terminal_session"],
            {"task_id": TASK_ID, "session_id": SESSION_ID}
        )


@pytest.mark.parametrize(
    "result",
    [
        object(),
        TaskCloseRequestView("task-" + "9" * 32, SESSION_ID, "closed"),
        TaskCloseRequestView(TASK_ID, "9" * 32, "closed"),
    ],
)
def test_task_close_refuses_invalid_or_mismatched_registry_result(
    result: object,
) -> None:
    class InvalidRegistry(_Service):
        def request_task_close(self, *args: object) -> object:
            del args
            return result

    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=InvalidRegistry(),
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    with pytest.raises(RuntimeError, match="invalid close data"):
        _invoke(commands["close_task"],
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
        _invoke(commands["next_events"], payload)

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
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    with pytest.raises(RuntimeError, match="invalid drain data"):
        _invoke(commands["next_events"],
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
        def start_setup_plan(self, *args: object, **kwargs: object) -> PlanSession:
            del args, kwargs
            raise service_error

    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=RefusingService(),
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    with pytest.raises(adapter_error) as captured:
        _invoke(commands["start_plan"],
            {
                "task_id": TASK_ID,
                "command_id": COMMAND_ID,
                "source_id": SOURCE_ID,
                "target_id": TARGET_ID,
                "options": _setup_options_payload(),
            }
        )

    assert "private" not in str(captured.value)


def test_br_g_32_start_plan_does_not_reclassify_incidental_value_error() -> None:
    class BrokenService(_Service):
        def start_setup_plan(self, *args: object, **kwargs: object) -> PlanSession:
            del args, kwargs
            raise ValueError("incidental implementation defect")

    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=BrokenService(),
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    with pytest.raises(ValueError, match="incidental implementation defect"):
        _invoke(commands["start_plan"],
            {
                "task_id": TASK_ID,
                "command_id": COMMAND_ID,
                "source_id": SOURCE_ID,
                "target_id": TARGET_ID,
                "options": _setup_options_payload(),
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
        def start_setup_plan(self, *args: object, **kwargs: object):
            del args, kwargs
            return result

    commands = production_command_specs(
        picker=lambda: None,
        slots=_Slots(),
        registry=InvalidService(),
        cosmetics=_Cosmetics(),
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )

    with pytest.raises(RuntimeError, match="invalid data"):
        _invoke(commands["start_plan"],
                {
                    "task_id": TASK_ID,
                    "command_id": COMMAND_ID,
                    "source_id": SOURCE_ID,
                    "target_id": TARGET_ID,
                    "options": _setup_options_payload(),
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
        _invoke(commands[command], payload)

    assert slots.stored == []
    assert slots.resolved == []
    assert service.calls == []


class _State(StrEnum):
    READY = "ready"


@dataclass(frozen=True, slots=True)
class _NestedEnumAnnotation:
    states: list[_State | None]


@dataclass(frozen=True, slots=True)
class _UnapprovedLookalike:
    label: str


def _annotation_enum_types(annotation: object) -> set[type[Enum]]:
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return {annotation}

    enum_types: set[type[Enum]] = set()
    for argument in get_args(annotation):
        enum_types.update(_annotation_enum_types(argument))
    return enum_types


def _value_enum_types(value: object) -> set[type[Enum]]:
    if isinstance(value, Enum):
        return {type(value)}
    if is_dataclass(value) and not isinstance(value, type):
        enum_types: set[type[Enum]] = set()
        for field in fields(value):
            enum_types.update(_value_enum_types(getattr(value, field.name)))
        return enum_types
    if isinstance(value, Mapping):
        enum_types = set()
        for key, item in value.items():
            enum_types.update(_value_enum_types(key))
            enum_types.update(_value_enum_types(item))
        return enum_types
    if isinstance(value, (list, tuple)):
        enum_types = set()
        for item in value:
            enum_types.update(_value_enum_types(item))
        return enum_types
    return set()


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


def test_br_g_32_public_view_witness_table_keys_are_exact_and_manual() -> None:
    witnesses = iter_public_view_witnesses()

    assert set(PUBLIC_VIEW_WITNESSES) == PUBLIC_VIEW_DATACLASSES
    assert len({witness.label for witness in witnesses}) == len(witnesses)
    for approved_type, typed_witnesses in PUBLIC_VIEW_WITNESSES.items():
        assert typed_witnesses
        assert all(type(witness.value) is approved_type for witness in typed_witnesses)
        for witness in typed_witnesses:
            encoded = json.dumps(
                witness.expected,
                ensure_ascii=False,
                allow_nan=False,
            )
            assert json.loads(encoded) == witness.expected


def test_history_event_witnesses_are_supported_reliable_row_contracts() -> None:
    events = tuple(
        witness.value for witness in PUBLIC_VIEW_WITNESSES[HistoryEventView]
    )
    page = PUBLIC_VIEW_WITNESSES[HistoryEventPageView][0].value

    assert {event.schema_version for event in events} == {5}
    assert page.events == events
    assert tuple(event.sequence for event in page.events) == (9, 10)
    assert len({event.sequence for event in page.events}) == len(page.events)
    assert page.next_after_seq == page.events[-1].sequence
    assert page.next_after_seq <= page.through_seq
    assert not page.has_more
    for event in events:
        assert event.body_type in {
            "StateChanged",
            "PhaseChanged",
            "ItemOutcome",
            "IntegrityOutcome",
            "Gap",
        }
        assert len(event.payload_hash) == 64
        assert len(event.receipt_hash) == 64
        assert set(event.payload_hash + event.receipt_hash) <= set(
            "0123456789abcdef"
        )
        if event.body is None:
            assert event.disposition == "rejected"
            assert event.duplicate_of_seq is None
            assert event.rejection_reason == "event-too-large"
            continue
        decoded = envelope_from_dict(
            {
                "session_id": event.session_id,
                "seq": event.sequence,
                "at": event.at,
                "schema_version": event.schema_version,
                "body_type": event.body_type,
                    "body": dict(event.body),
            }
        )
        assert delivery_class(decoded.body) is DeliveryClass.RELIABLE
        assert event.disposition in {"recorded", "duplicate"}
        assert event.rejection_reason is None
        if event.disposition == "recorded":
            assert event.duplicate_of_seq is None
        else:
            assert event.duplicate_of_seq is not None
            assert 0 < event.duplicate_of_seq < event.sequence


def test_br_g_32_public_view_enum_manifest_matches_resolved_annotations() -> None:
    annotated_enum_types: set[type[Enum]] = set()
    for view_type in PUBLIC_VIEW_DATACLASSES:
        for annotation in get_type_hints(view_type).values():
            annotated_enum_types.update(_annotation_enum_types(annotation))

    assert not annotated_enum_types


def test_br_g_32_public_view_enum_annotation_walker_is_recursive() -> None:
    annotation = get_type_hints(_NestedEnumAnnotation)["states"]

    assert _annotation_enum_types(annotation) == {_State}


def test_br_g_32_public_view_enum_manifest_matches_manual_witnesses() -> None:
    witnessed_enum_types: set[type[Enum]] = set()
    for witness in iter_public_view_witnesses():
        witnessed_enum_types.update(_value_enum_types(witness.value))

    assert not witnessed_enum_types


def test_br_g_33_codec_approves_only_exact_adapter_task_views() -> None:
    event = SessionEventView(
        SESSION_ID,
        9,
        "2026-08-12T10:00:00+00:00",
        5,
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
        TaskShellView,
        TaskSummaryView,
        TaskListView,
        TaskCloseRequestView,
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
                    "at": "2026-08-12T10:00:00+00:00",
                    "schema_version": 5,
                    "body_type": "StateChanged",
                    "body": {"state": "running"},
                },
            }
        ],
    }
    result = operation_result_view(OperationResult(SessionState.COMPLETED))
    record = SessionRecordView(
        SESSION_ID,
        PLAN_KIND,
        "completed",
        False,
        "2026-08-12T10:00:00+00:00",
        None,
        "2026-08-12T10:00:00+00:00",
        result,
    )
    assert to_primitive_view(TaskRecordUpdateView("record", record)) == {
        "update_type": "record",
        "record": {
            "session_id": SESSION_ID,
            "kind": "sync-plan",
            "state": "completed",
            "supports_pause": False,
            "created_at": "2026-08-12T10:00:00+00:00",
            "started_at": None,
            "ended_at": "2026-08-12T10:00:00+00:00",
            "result": to_primitive_view(result),
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


def _valid_task_record() -> SessionRecordView:
    return SessionRecordView(
        SESSION_ID, PLAN_KIND, "completed", False,
        "2026-08-12T10:00:00+00:00", None, "2026-08-12T10:00:00+00:00",
        operation_result_view(OperationResult(SessionState.COMPLETED)),
    )


def _invalid_task_update_views():
    event = SessionEventView(
        SESSION_ID, 1, "2026-08-12T10:00:00+00:00", 5,
        "StateChanged", {"state": "running"},
    )
    record = _valid_task_record()
    return [
        TaskEventUpdateView("event", replace(event, sequence=True)),
        TaskEventUpdateView("event", replace(event, sequence=0)),
        TaskEventUpdateView("event", replace(event, session_id="1" * 32)),
        TaskRecordUpdateView("record", replace(record, result=None)),
        TaskRecordUpdateView("record", replace(record, state="pending", ended_at=None, result=None)),
        TaskRecordUpdateView("record", replace(record, session_id="1" * 32)),
        TaskRecordUpdateView("record", replace(record, state="failed")),
        TaskRecordUpdateView("record", replace(record, result=replace(record.result, bytes_done=0))),
        object(),
    ]


@pytest.mark.parametrize("update", _invalid_task_update_views())
def test_next_events_rechecks_exact_nested_task_data(update) -> None:
    commands, _, service = _commands()
    returned = TaskDrainView(TASK_ID, SESSION_ID, DRAIN_ID, (update,))
    service.drain = lambda *args, **kwargs: returned
    with pytest.raises(RuntimeError, match="invalid drain data"):
        _invoke(commands["next_events"], {
            "task_id": TASK_ID, "session_id": SESSION_ID,
            "drain_id": DRAIN_ID, "replay_from": None,
        })


@pytest.mark.parametrize("update", _invalid_task_update_views())
def test_task_serializer_rechecks_nested_data(update) -> None:
    returned = TaskDrainView(TASK_ID, SESSION_ID, DRAIN_ID, (update,))
    with pytest.raises(BridgeProtocolError):
        to_primitive_view(returned)


def test_task_serializer_rechecks_body_mutated_after_command_return() -> None:
    commands, _, service = _commands()
    event = SessionEventView(
        SESSION_ID, 1, "2026-08-12T10:00:00+00:00", 5,
        "StateChanged", {"state": "running"},
    )
    returned = TaskDrainView(
        TASK_ID, SESSION_ID, DRAIN_ID, (TaskEventUpdateView("event", event),),
    )
    service.drain = lambda *args, **kwargs: returned
    accepted = _invoke(commands["next_events"], {
        "task_id": TASK_ID, "session_id": SESSION_ID,
        "drain_id": DRAIN_ID, "replay_from": None,
    })
    assert accepted == returned
    assert accepted is not returned
    event.body["state"] = "invented"
    assert to_primitive_view(accepted)["updates"][0]["event"]["body"] == {
        "state": "running"
    }


def test_task_serializer_does_not_recertify_trusted_event_body() -> None:
    event = SessionEventView(
        SESSION_ID, 1, "producer timestamp", 5,
        "StateChanged", {"state": "producer-owned", "detail": {"kept": True}},
    )
    returned = TaskDrainView(
        TASK_ID, SESSION_ID, DRAIN_ID, (TaskEventUpdateView("event", event),),
    )

    assert to_primitive_view(returned)["updates"][0]["event"] == {
        "session_id": SESSION_ID,
        "sequence": 1,
        "at": "producer timestamp",
        "schema_version": 5,
        "body_type": "StateChanged",
        "body": {"state": "producer-owned", "detail": {"kept": True}},
    }


@pytest.mark.parametrize("changes", [
    {"headline": "invented"}, {"filesystem": "running"},
    {"integrity": "invented"}, {"recording": "degraded"}, {"audit": "invented"},
    {"disposition": "invented"}, {"canceled": 0}, {"bytes_done": 0},
    {"bytes_total": "01"}, {"bytes_done": "1", "bytes_total": "0"},
    {"error": "\ud800"}, {"error": "x" * 1025},
    {"phases": []}, {"phases": (object(),)},
    {"phases": (PhaseResultView("execute", "completed", 0, 0, 0, "0", None),)},
    {"phases": (PhaseResultView("execute", "completed", 0, 0, "0", "0", None),) * 2},
    {"recording_degraded_items": True},
    {"recording_issues": []}, {"recording_issues": (object(),)},
    {"recording_issues": (RecordingIssueView("invented", None),)},
    {"omitted_detail_count": -1}, {"presentation_omitted_detail_count": True},
    {"review_refusal": object()},
    {"review_refusal": ReviewFactLimitView(
        "review-row-limit", "plan", "review", "rows", 1, None,
    )},
    {"canceled": True},
])
def test_result_view_serializer_rejects_malformed_typed_facts(changes) -> None:
    result = replace(_valid_task_record().result, **changes)
    with pytest.raises(BridgeProtocolError):
        to_primitive_view(result)


@pytest.mark.parametrize("changes", [
    {"session_id": "bad"}, {"kind": ""}, {"state": "invented"},
    {"supports_pause": 0}, {"created_at": "2026-08-12T10:00:00Z"},
    {"started_at": "bad"}, {"ended_at": None}, {"result": object()},
    {"state": "failed"},
])
def test_generic_record_serializer_rejects_malformed_facts(changes) -> None:
    with pytest.raises(BridgeProtocolError):
        to_primitive_view(replace(_valid_task_record(), **changes))


def test_generic_record_serializer_preserves_result_free_snapshots() -> None:
    record = replace(_valid_task_record(), result=None)
    assert to_primitive_view(record)["result"] is None
    pending = replace(record, state="pending", ended_at=None)
    assert to_primitive_view(pending)["state"] == "pending"
