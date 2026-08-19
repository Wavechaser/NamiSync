"""Exact production command policies and dependency-bound handlers."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from namisync.interfaces.ui_state import (
    APPEARANCE_VALUE_VERSION,
    MAX_JAVASCRIPT_SAFE_INTEGER,
    AppearanceValue,
    CosmeticDisposition,
    CosmeticReplaceResult,
    CosmeticSectionSnapshot,
    ThemeMode,
)
from namisync.interfaces.web.drain import (
    TaskCloseView,
    TaskDrainView,
    TaskEventUpdateView,
    TaskIntentConflictError,
    TaskRecordUpdateView,
    TaskSessionReleaseView,
    TaskStartView,
)
from namisync.interfaces.web.readiness import (
    CommandPhase,
    ReadinessContext,
)
from namisync.interfaces.web.slots import SlotUnavailableError
from namisync.interfaces.service import (
    CommandIdConflictError,
    ControlView,
    DatabaseContractView,
    ExecutionAdmissionView,
    ExecutionSession,
    InventoryDetailsView,
    InventoryDispositionView,
    InventoryRowView,
    LocationResolutionView,
    LocationSession,
    PlanSession,
    PreservationSettingsView,
    ResultClassificationView,
    ScanWarningView,
    SelectionMutationView,
    SelectionOperationView,
    SelectionPreviewView,
    SemanticSettingsPatchView,
    SemanticSettingsView,
    SessionEventView,
    SessionRecordView,
    ShutdownView,
    SyncPathInputError,
)
from namisync.workflows.models import (
    ExecutionDetails,
    HistoryEventPageView,
    HistoryEventView,
    HistoryItemPageView,
    HistoryItemView,
    HistoryRunSummaryView,
    PlanOperationView,
    PlanReview,
    RefusalView,
)
from namisync.workflows.views import (
    IntegrityOutcomeView,
    OperationItemView,
    OperationResultView,
    PhaseResultView,
)


_OPAQUE_ID = re.compile(r"[0-9a-f]{32}")
_READINESS_CHALLENGE = re.compile(r"[0-9a-f]{32}")
_SLOT_ID = re.compile(r"slot-[0-9a-f]{32}")
_TASK_ID = re.compile(r"task-[0-9a-f]{32}")

SERVICE_PUBLIC_VIEW_DATACLASSES: frozenset[type[object]] = frozenset(
    {
        ControlView,
        DatabaseContractView,
        ExecutionAdmissionView,
        ExecutionSession,
        InventoryDetailsView,
        InventoryDispositionView,
        InventoryRowView,
        LocationResolutionView,
        LocationSession,
        PlanSession,
        PreservationSettingsView,
        ResultClassificationView,
        ScanWarningView,
        SelectionMutationView,
        SelectionOperationView,
        SelectionPreviewView,
        SemanticSettingsPatchView,
        SemanticSettingsView,
        SessionEventView,
        SessionRecordView,
        ShutdownView,
    }
)
NESTED_PUBLIC_VIEW_DATACLASSES: frozenset[type[object]] = frozenset(
    {
        ExecutionDetails,
        HistoryEventPageView,
        HistoryEventView,
        HistoryItemPageView,
        HistoryItemView,
        HistoryRunSummaryView,
        IntegrityOutcomeView,
        OperationItemView,
        OperationResultView,
        PhaseResultView,
        PlanOperationView,
        PlanReview,
        RefusalView,
    }
)
ADAPTER_PUBLIC_VIEW_DATACLASSES: frozenset[type[object]] = frozenset(
    {
        TaskDrainView,
        TaskCloseView,
        TaskEventUpdateView,
        TaskRecordUpdateView,
        TaskSessionReleaseView,
        TaskStartView,
    }
)
PUBLIC_VIEW_DATACLASSES = (
    SERVICE_PUBLIC_VIEW_DATACLASSES
    | NESTED_PUBLIC_VIEW_DATACLASSES
    | ADAPTER_PUBLIC_VIEW_DATACLASSES
)
PUBLIC_VIEW_ENUMS: frozenset[type[object]] = frozenset()


class CommandPayloadError(ValueError):
    """A command payload does not match its exact declared schema."""


class CommandAdmissionError(RuntimeError):
    """An admitted command lacks its exact composition-owned context."""


class PickerUnavailableError(RuntimeError):
    """The native picker did not return its documented result shape."""


class CommandConflictError(RuntimeError):
    """A receipted bridge command no longer matches its first intent."""


class PlanningRefusedError(RuntimeError):
    """The service refused the selected roots before plan admission."""


class CommandAccess(StrEnum):
    READ_ONLY = "read-only"
    MUTATING = "mutating"


class FieldRequirement(StrEnum):
    FORBIDDEN = "forbidden"
    REQUIRED = "required"


class CommandTimeout(StrEnum):
    STARTUP_5_SECONDS = "startup-5-seconds"
    LOCAL_5_SECONDS = "local-5-seconds"
    INTERACTIVE = "interactive"
    MUTATION_30_SECONDS = "mutation-30-seconds"
    DRAIN_30_SECONDS = "drain-30-seconds"


class CommandRetry(StrEnum):
    NONE = "none"
    SAME_COMMAND_ONCE = "same-command-once"
    SAME_PAYLOAD_ONCE = "same-payload-once"
    SAME_PAYLOAD_BOUNDED = "same-payload-bounded"


class FolderSlotAuthority(Protocol):
    """Consumer contract for the path-owning slot table added separately."""

    def store(self, path: str, *, purpose: str) -> tuple[str, str]: ...

    def resolve_pair(self, source_id: str, target_id: str) -> tuple[str, str]: ...


class TaskAuthority(Protocol):
    def replay_start(
        self,
        command_id: str,
        wire_intent: tuple[str, str, str | None],
    ) -> TaskStartView | None: ...

    def start_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None = None,
        command_id: str,
        wire_intent: tuple[str, str, str | None] | None = None,
    ) -> TaskStartView: ...

    def drain(
        self,
        task_id: str,
        session_id: str,
        drain_id: str,
        *,
        replay_from: int | None,
    ) -> TaskDrainView: ...

    def release_terminal_session(
        self,
        task_id: str,
        session_id: str,
    ) -> TaskSessionReleaseView: ...

    def close_task(self, task_id: str, session_id: str) -> TaskCloseView: ...


class CosmeticStateAuthority(Protocol):
    """Exact interface-owned state surface exposed through the bridge."""

    def read_section(
        self,
        section: str,
        value_version: int,
    ) -> CosmeticSectionSnapshot: ...

    def replace_section(
        self,
        section: str,
        value_version: int,
        expected_revision: int,
        value: AppearanceValue,
    ) -> CosmeticReplaceResult: ...


PayloadValidator = Callable[[object], object]
CommandHandler = Callable[[object], object]
FolderPicker = Callable[[], list[str] | tuple[str, ...] | None]


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """One immutable command row; the mapping key is its wire name."""

    validate_payload: PayloadValidator
    handler: CommandHandler
    access: CommandAccess
    command_id: FieldRequirement
    revision: FieldRequirement
    timeout: CommandTimeout
    retry: CommandRetry
    phase: CommandPhase = CommandPhase.OPEN

    def invoke(
        self,
        payload: object,
        *,
        context: object,
    ) -> object:
        if (
            type(context) is not ReadinessContext
            or context.phase is not self.phase
        ):
            raise CommandAdmissionError(
                "command requires its exact admitted readiness context"
            )
        validated = self.validate_payload(payload)
        if self.phase is CommandPhase.BOOTSTRAP:
            return self.handler(
                _BootstrapCommandInvocation(validated, context.generation)
            )
        return self.handler(validated)


@dataclass(frozen=True, slots=True)
class _BootstrapCommandInvocation:
    payload: object
    generation: int


@dataclass(frozen=True, slots=True)
class _ReadinessEchoPayload:
    challenge: str


@dataclass(frozen=True, slots=True)
class _PickFolderPayload:
    purpose: str


@dataclass(frozen=True, slots=True)
class _StartPlanPayload:
    command_id: str
    source_id: str
    target_id: str
    deletion_policy: str | None


@dataclass(frozen=True, slots=True)
class _NextEventsPayload:
    task_id: str
    session_id: str
    drain_id: str
    replay_from: int | None


@dataclass(frozen=True, slots=True)
class _CloseTaskPayload:
    task_id: str
    session_id: str


@dataclass(frozen=True, slots=True)
class _ReleaseTerminalSessionPayload:
    task_id: str
    session_id: str


@dataclass(frozen=True, slots=True)
class _ReadCosmeticSectionPayload:
    section: str
    value_version: int


@dataclass(frozen=True, slots=True)
class _ReplaceCosmeticSectionPayload:
    section: str
    value_version: int
    expected_revision: int
    theme: ThemeMode


def production_command_specs(
    *,
    picker: FolderPicker,
    slots: FolderSlotAuthority,
    registry: TaskAuthority,
    cosmetics: CosmeticStateAuthority,
    shell_ready: Callable[[int], None],
    readiness_echo: Callable[[int, str], bool],
) -> Mapping[str, CommandSpec]:
    """Bind the exact production rows to process-local dependencies."""

    if not callable(picker):
        raise TypeError("picker must be callable")
    if not callable(shell_ready):
        raise TypeError("shell readiness callback must be callable")
    if not callable(readiness_echo):
        raise TypeError("readiness echo callback must be callable")

    def acknowledge_shell(invocation: object) -> object:
        if (
            type(invocation) is not _BootstrapCommandInvocation
            or invocation.payload is not None
        ):
            raise TypeError("shell_ready received an unvalidated payload")
        shell_ready(invocation.generation)
        return {"acknowledged": True}

    def acknowledge_readiness_echo(invocation: object) -> object:
        if (
            type(invocation) is not _BootstrapCommandInvocation
            or type(invocation.payload) is not _ReadinessEchoPayload
        ):
            raise TypeError("readiness_echo received an unvalidated payload")
        acknowledged = readiness_echo(
            invocation.generation,
            invocation.payload.challenge,
        )
        if type(acknowledged) is not bool:
            raise TypeError("readiness echo callback returned invalid data")
        return {"acknowledged": acknowledged}

    def pick_folder(payload: object) -> object:
        if not isinstance(payload, _PickFolderPayload):
            raise TypeError("pick_folder received an unvalidated payload")
        try:
            selected = picker()
        except BaseException as error:
            raise PickerUnavailableError(
                "native folder picker could not open"
            ) from error
        if selected is None:
            return None
        if (
            type(selected) not in {list, tuple}
            or len(selected) != 1
            or type(selected[0]) is not str
            or not selected[0]
        ):
            raise PickerUnavailableError("native folder picker returned invalid data")
        try:
            selected[0].encode("utf-8")
        except UnicodeEncodeError as error:
            raise PickerUnavailableError(
                "native folder picker returned invalid data"
            ) from error
        slot_id, display = slots.store(selected[0], purpose=payload.purpose)
        if (
            not isinstance(slot_id, str)
            or _SLOT_ID.fullmatch(slot_id) is None
            or not isinstance(display, str)
        ):
            raise RuntimeError("folder slot authority returned invalid data")
        try:
            display.encode("utf-8")
        except UnicodeEncodeError as error:
            raise RuntimeError("folder slot authority returned invalid data") from error
        return {"id": slot_id, "display": display}

    def start_plan(payload: object) -> object:
        if not isinstance(payload, _StartPlanPayload):
            raise TypeError("start_plan received an unvalidated payload")
        wire_intent = (
            payload.source_id,
            payload.target_id,
            payload.deletion_policy,
        )
        try:
            result = registry.replay_start(payload.command_id, wire_intent)
            if result is None:
                try:
                    source, target = slots.resolve_pair(
                        payload.source_id,
                        payload.target_id,
                    )
                except SlotUnavailableError:
                    result = registry.replay_start(payload.command_id, wire_intent)
                    if result is None:
                        raise
                else:
                    result = registry.start_plan(
                        source,
                        target,
                        deletion_policy=payload.deletion_policy,
                        command_id=payload.command_id,
                        wire_intent=wire_intent,
                    )
        except (CommandIdConflictError, TaskIntentConflictError) as error:
            raise CommandConflictError(
                "start_plan command id conflicts with retained intent"
            ) from error
        except SyncPathInputError as error:
            raise PlanningRefusedError(
                "start_plan roots were refused"
            ) from error
        if not _is_valid_task_start(result):
            raise RuntimeError("planning service returned invalid data")
        return result

    def next_events(payload: object) -> object:
        if not isinstance(payload, _NextEventsPayload):
            raise TypeError("next_events received an unvalidated payload")
        result = registry.drain(
            payload.task_id,
            payload.session_id,
            payload.drain_id,
            replay_from=payload.replay_from,
        )
        if (
            type(result) is not TaskDrainView
            or result.task_id != payload.task_id
            or result.session_id != payload.session_id
            or result.drain_id != payload.drain_id
        ):
            raise RuntimeError("task registry returned invalid drain data")
        return result

    def close_task(payload: object) -> object:
        if not isinstance(payload, _CloseTaskPayload):
            raise TypeError("close_task received an unvalidated payload")
        result = registry.close_task(payload.task_id, payload.session_id)
        if (
            type(result) is not TaskCloseView
            or result.task_id != payload.task_id
            or result.session_id != payload.session_id
        ):
            raise RuntimeError("task registry returned invalid close data")
        return result

    def release_terminal_session(payload: object) -> object:
        if not isinstance(payload, _ReleaseTerminalSessionPayload):
            raise TypeError(
                "release_terminal_session received an unvalidated payload"
            )
        result = registry.release_terminal_session(
            payload.task_id,
            payload.session_id,
        )
        if (
            type(result) is not TaskSessionReleaseView
            or result.task_id != payload.task_id
            or result.session_id != payload.session_id
        ):
            raise RuntimeError("task registry returned invalid release data")
        return result

    def read_cosmetic_section(payload: object) -> object:
        if type(payload) is not _ReadCosmeticSectionPayload:
            raise TypeError(
                "read_cosmetic_section received an unvalidated payload"
            )
        result = cosmetics.read_section(payload.section, payload.value_version)
        return _cosmetic_snapshot_to_wire(result)

    def replace_cosmetic_section(payload: object) -> object:
        if type(payload) is not _ReplaceCosmeticSectionPayload:
            raise TypeError(
                "replace_cosmetic_section received an unvalidated payload"
            )
        result = cosmetics.replace_section(
            payload.section,
            payload.value_version,
            payload.expected_revision,
            AppearanceValue(payload.theme),
        )
        return _cosmetic_replace_result_to_wire(result)

    return MappingProxyType(
        {
            "shell_ready": CommandSpec(
                validate_payload=_validate_empty_payload,
                handler=acknowledge_shell,
                access=CommandAccess.READ_ONLY,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.STARTUP_5_SECONDS,
                retry=CommandRetry.NONE,
                phase=CommandPhase.BOOTSTRAP,
            ),
            "readiness_echo": CommandSpec(
                validate_payload=_validate_readiness_echo,
                handler=acknowledge_readiness_echo,
                access=CommandAccess.READ_ONLY,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.STARTUP_5_SECONDS,
                retry=CommandRetry.SAME_PAYLOAD_ONCE,
                phase=CommandPhase.BOOTSTRAP,
            ),
            "pick_folder": CommandSpec(
                validate_payload=_validate_pick_folder,
                handler=pick_folder,
                access=CommandAccess.READ_ONLY,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.INTERACTIVE,
                retry=CommandRetry.NONE,
            ),
            "start_plan": CommandSpec(
                validate_payload=_validate_start_plan,
                handler=start_plan,
                access=CommandAccess.MUTATING,
                command_id=FieldRequirement.REQUIRED,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.MUTATION_30_SECONDS,
                retry=CommandRetry.SAME_COMMAND_ONCE,
            ),
            "next_events": CommandSpec(
                validate_payload=_validate_next_events,
                handler=next_events,
                access=CommandAccess.READ_ONLY,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.DRAIN_30_SECONDS,
                retry=CommandRetry.NONE,
            ),
            "release_terminal_session": CommandSpec(
                validate_payload=_validate_release_terminal_session,
                handler=release_terminal_session,
                access=CommandAccess.MUTATING,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.MUTATION_30_SECONDS,
                retry=CommandRetry.SAME_PAYLOAD_BOUNDED,
            ),
            "close_task": CommandSpec(
                validate_payload=_validate_close_task,
                handler=close_task,
                access=CommandAccess.MUTATING,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.MUTATION_30_SECONDS,
                retry=CommandRetry.SAME_PAYLOAD_BOUNDED,
            ),
            "read_cosmetic_section": CommandSpec(
                validate_payload=_validate_read_cosmetic_section,
                handler=read_cosmetic_section,
                access=CommandAccess.READ_ONLY,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.LOCAL_5_SECONDS,
                retry=CommandRetry.SAME_PAYLOAD_ONCE,
            ),
            "replace_cosmetic_section": CommandSpec(
                validate_payload=_validate_replace_cosmetic_section,
                handler=replace_cosmetic_section,
                access=CommandAccess.MUTATING,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.REQUIRED,
                timeout=CommandTimeout.LOCAL_5_SECONDS,
                retry=CommandRetry.NONE,
            ),
        }
    )


def _validate_empty_payload(value: object) -> None:
    if not isinstance(value, dict) or value:
        raise CommandPayloadError("shell_ready payload is invalid")


def _validate_readiness_echo(value: object) -> _ReadinessEchoPayload:
    if not isinstance(value, dict) or set(value) != {"challenge"}:
        raise CommandPayloadError("readiness_echo payload is invalid")
    challenge = value["challenge"]
    if (
        type(challenge) is not str
        or _READINESS_CHALLENGE.fullmatch(challenge) is None
    ):
        raise CommandPayloadError("readiness_echo payload is invalid")
    return _ReadinessEchoPayload(challenge)


def _validate_pick_folder(value: object) -> _PickFolderPayload:
    if not isinstance(value, dict) or set(value) != {"purpose"}:
        raise CommandPayloadError("pick_folder payload is invalid")
    purpose = value["purpose"]
    if type(purpose) is not str or purpose not in {"source", "target"}:
        raise CommandPayloadError("pick_folder payload is invalid")
    return _PickFolderPayload(purpose)


def _validate_start_plan(value: object) -> _StartPlanPayload:
    if not isinstance(value, dict) or set(value) != {
        "command_id",
        "source_id",
        "target_id",
        "deletion_policy",
    }:
        raise CommandPayloadError("start_plan payload is invalid")
    command_id = value["command_id"]
    source_id = value["source_id"]
    target_id = value["target_id"]
    deletion_policy = value["deletion_policy"]
    if type(command_id) is not str or _OPAQUE_ID.fullmatch(command_id) is None:
        raise CommandPayloadError("start_plan payload is invalid")
    if type(source_id) is not str or _SLOT_ID.fullmatch(source_id) is None:
        raise CommandPayloadError("start_plan payload is invalid")
    if type(target_id) is not str or _SLOT_ID.fullmatch(target_id) is None:
        raise CommandPayloadError("start_plan payload is invalid")
    if deletion_policy is not None and (
        type(deletion_policy) is not str
        or deletion_policy not in {"trash", "additive"}
    ):
        raise CommandPayloadError("start_plan payload is invalid")
    return _StartPlanPayload(
        command_id=command_id,
        source_id=source_id,
        target_id=target_id,
        deletion_policy=deletion_policy,
    )


def _validate_next_events(value: object) -> _NextEventsPayload:
    if not isinstance(value, dict) or set(value) != {
        "task_id",
        "session_id",
        "drain_id",
        "replay_from",
    }:
        raise CommandPayloadError("next_events payload is invalid")
    task_id = value["task_id"]
    session_id = value["session_id"]
    drain_id = value["drain_id"]
    replay_from = value["replay_from"]
    if type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None:
        raise CommandPayloadError("next_events payload is invalid")
    if type(session_id) is not str or _OPAQUE_ID.fullmatch(session_id) is None:
        raise CommandPayloadError("next_events payload is invalid")
    if type(drain_id) is not str or _OPAQUE_ID.fullmatch(drain_id) is None:
        raise CommandPayloadError("next_events payload is invalid")
    if replay_from is not None and (
        type(replay_from) is not int or replay_from < 1
    ):
        raise CommandPayloadError("next_events payload is invalid")
    return _NextEventsPayload(task_id, session_id, drain_id, replay_from)


def _validate_close_task(value: object) -> _CloseTaskPayload:
    if not isinstance(value, dict) or set(value) != {"task_id", "session_id"}:
        raise CommandPayloadError("close_task payload is invalid")
    task_id = value["task_id"]
    session_id = value["session_id"]
    if type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None:
        raise CommandPayloadError("close_task payload is invalid")
    if type(session_id) is not str or _OPAQUE_ID.fullmatch(session_id) is None:
        raise CommandPayloadError("close_task payload is invalid")
    return _CloseTaskPayload(task_id, session_id)


def _validate_release_terminal_session(
    value: object,
) -> _ReleaseTerminalSessionPayload:
    if not isinstance(value, dict) or set(value) != {"task_id", "session_id"}:
        raise CommandPayloadError("release_terminal_session payload is invalid")
    task_id = value["task_id"]
    session_id = value["session_id"]
    if type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None:
        raise CommandPayloadError("release_terminal_session payload is invalid")
    if type(session_id) is not str or _OPAQUE_ID.fullmatch(session_id) is None:
        raise CommandPayloadError("release_terminal_session payload is invalid")
    return _ReleaseTerminalSessionPayload(task_id, session_id)


def _validate_read_cosmetic_section(
    value: object,
) -> _ReadCosmeticSectionPayload:
    if type(value) is not dict or set(value) != {"section", "value_version"}:
        raise CommandPayloadError("read_cosmetic_section payload is invalid")
    section = value["section"]
    value_version = value["value_version"]
    if (
        type(section) is not str
        or section != "appearance"
        or type(value_version) is not int
        or value_version != APPEARANCE_VALUE_VERSION
    ):
        raise CommandPayloadError("read_cosmetic_section payload is invalid")
    return _ReadCosmeticSectionPayload(section, value_version)


def _validate_replace_cosmetic_section(
    value: object,
) -> _ReplaceCosmeticSectionPayload:
    if type(value) is not dict or set(value) != {
        "section",
        "value_version",
        "expected_revision",
        "value",
    }:
        raise CommandPayloadError("replace_cosmetic_section payload is invalid")
    section = value["section"]
    value_version = value["value_version"]
    expected_revision = value["expected_revision"]
    appearance = value["value"]
    if (
        type(section) is not str
        or section != "appearance"
        or type(value_version) is not int
        or value_version != APPEARANCE_VALUE_VERSION
        or not _is_javascript_safe_integer(expected_revision)
        or type(appearance) is not dict
        or set(appearance) != {"theme"}
    ):
        raise CommandPayloadError("replace_cosmetic_section payload is invalid")
    theme = appearance["theme"]
    if type(theme) is not str:
        raise CommandPayloadError("replace_cosmetic_section payload is invalid")
    try:
        theme_mode = ThemeMode(theme)
    except ValueError as error:
        raise CommandPayloadError(
            "replace_cosmetic_section payload is invalid"
        ) from error
    return _ReplaceCosmeticSectionPayload(
        section,
        value_version,
        expected_revision,
        theme_mode,
    )


def _cosmetic_snapshot_to_wire(value: object) -> dict[str, object]:
    if not _is_valid_cosmetic_snapshot(value, CosmeticSectionSnapshot):
        raise RuntimeError("cosmetic state authority returned invalid data")
    assert type(value) is CosmeticSectionSnapshot
    return {
        "section": value.section,
        "value_version": value.value_version,
        "revision": value.revision,
        "dirty": value.dirty,
        "value": {"theme": value.value.theme.value},
    }


def _cosmetic_replace_result_to_wire(value: object) -> dict[str, object]:
    if (
        not _is_valid_cosmetic_snapshot(value, CosmeticReplaceResult)
        or type(value.disposition) is not CosmeticDisposition
    ):
        raise RuntimeError("cosmetic state authority returned invalid data")
    assert type(value) is CosmeticReplaceResult
    return {
        "section": value.section,
        "value_version": value.value_version,
        "revision": value.revision,
        "dirty": value.dirty,
        "value": {"theme": value.value.theme.value},
        "disposition": value.disposition.value,
    }


def _is_valid_cosmetic_snapshot(value: object, expected_type: type[object]) -> bool:
    return (
        type(value) is expected_type
        and type(value.section) is str
        and value.section == "appearance"
        and type(value.value_version) is int
        and value.value_version == APPEARANCE_VALUE_VERSION
        and _is_javascript_safe_integer(value.revision)
        and type(value.dirty) is bool
        and type(value.value) is AppearanceValue
        and type(value.value.theme) is ThemeMode
    )


def _is_javascript_safe_integer(value: object) -> bool:
    return (
        type(value) is int
        and 0 <= value <= MAX_JAVASCRIPT_SAFE_INTEGER
    )


def _is_valid_task_start(value: object) -> bool:
    return (
        type(value) is TaskStartView
        and type(value.task_id) is str
        and _TASK_ID.fullmatch(value.task_id) is not None
        and type(value.request_id) is str
        and _OPAQUE_ID.fullmatch(value.request_id) is not None
        and type(value.session_id) is str
        and _OPAQUE_ID.fullmatch(value.session_id) is not None
    )
