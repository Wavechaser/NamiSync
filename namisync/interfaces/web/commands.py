"""Exact production command policies and dependency-bound handlers."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from namisync.interfaces.ui_state import (
    APPEARANCE_VALUE_VERSION,
    MAX_JAVASCRIPT_SAFE_INTEGER,
    AppearanceValue,
    CosmeticDisposition,
    CosmeticReplaceResult,
    CosmeticSectionSnapshot,
    ThemeMode,
)
from namisync.interfaces.task_port import (
    TaskCloseRequestView,
    TaskCloseView,
    TaskDrainView,
    TaskEventUpdateView,
    TaskIntentConflictError,
    TaskListView,
    TaskRecordUpdateView,
    TaskSessionReleaseView,
    TaskShellView,
    TaskStartView,
    TaskSummaryView,
    TaskSetupSnapshotView,
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
    SetupOptionsView,
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
    RecordingIssueView,
    ReviewFactLimitView,
)
from namisync.workflows.inventory import (
    LocationCandidate,
    LocationCandidateResult,
    LocationCandidateState,
    RememberedLocations,
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
        SetupOptionsView,
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
        RecordingIssueView,
        ReviewFactLimitView,
        PlanOperationView,
        PlanReview,
        RefusalView,
    }
)
ADAPTER_PUBLIC_VIEW_DATACLASSES: frozenset[type[object]] = frozenset(
    {
        TaskDrainView,
        TaskCloseRequestView,
        TaskCloseView,
        TaskEventUpdateView,
        TaskRecordUpdateView,
        TaskSessionReleaseView,
        TaskShellView,
        TaskStartView,
        TaskSummaryView,
        TaskListView,
    }
)
PUBLIC_VIEW_DATACLASSES = (
    SERVICE_PUBLIC_VIEW_DATACLASSES
    | NESTED_PUBLIC_VIEW_DATACLASSES
    | ADAPTER_PUBLIC_VIEW_DATACLASSES
)
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


class CommandWork(StrEnum):
    DIRECT = "direct"
    ASYNC_SMALL = "async-small"


class FolderSlotAuthority(Protocol):
    """Consumer contract for the path-owning slot table added separately."""

    def store(
        self,
        candidate: LocationCandidate | str,
        *,
        purpose: str,
        display: str | None = None,
    ) -> tuple[str, str]: ...

    def resolve_pair(self, source_id: str, target_id: str): ...

    def resolve(self, slot_id: str, *, purpose: str) -> LocationCandidate: ...

    def store_continuation(self, candidate, result, *, purpose: str, admit) -> str: ...

    def resolve_continuation(
        self, slot_id: str, *, purpose: str, mount_index: int
    ): ...


class TaskAuthority(Protocol):
    def create_task_shell(self, command_id: str) -> TaskShellView: ...

    def list_tasks(self) -> TaskListView: ...

    def read_setup_options(self) -> SetupOptionsView: ...

    def prepare_setup_options(self, value: SetupOptionsView) -> SetupOptionsView: ...

    def remembered_locations(self) -> RememberedLocations: ...

    def admit_location_candidate(self, candidate: LocationCandidate) -> LocationCandidateResult: ...

    def read_task_setup(self, task_id: str) -> TaskSetupSnapshotView: ...

    def start_setup_plan(self, *args, **kwargs) -> TaskStartView: ...

    def start_setup_inventory(self, *args, **kwargs) -> TaskStartView: ...

    def start_plan_again(self, *args, **kwargs) -> TaskStartView: ...

    def replay_start(
        self,
        command_id: str,
        wire_intent: tuple[object, ...],
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

    def drain_for_bridge(
        self,
        task_id: str,
        session_id: str,
        drain_id: str,
        *,
        replay_from: int | None,
    ) -> object: ...

    def release_terminal_session(
        self,
        task_id: str,
        session_id: str,
    ) -> TaskSessionReleaseView: ...

    def request_task_close(
        self,
        task_id: str,
        session_id: str | None,
    ) -> TaskCloseRequestView: ...


@runtime_checkable
class _TaskResponseCodecBinder(Protocol):
    """Optional concrete-registry composition hook."""

    def bind_response_codec(self, response_codec: object) -> None: ...


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
    work: CommandWork = CommandWork.DIRECT

    def invoke(
        self,
        payload: object,
        *,
        context: object,
    ) -> object:
        result = self.invoke_for_bridge(payload, context=context)
        from .bridge import (
            _AdmittedTaskDrainResponse,
            _consume_task_drain_response,
        )

        if type(result) is _AdmittedTaskDrainResponse:
            return _consume_task_drain_response(result)
        return result

    def invoke_for_bridge(
        self,
        payload: object,
        *,
        context: object,
    ) -> object:
        """Invoke while preserving an already admitted response owner."""

        invocation = self.prepare_for_bridge(payload, context=context)
        return self.invoke_prepared_for_bridge(invocation)

    def prepare_for_bridge(
        self,
        payload: object,
        *,
        context: object,
    ) -> object:
        """Validate one admitted payload before selecting its work owner."""

        if (
            type(context) is not ReadinessContext
            or context.phase is not self.phase
        ):
            raise CommandAdmissionError(
                "command requires its exact admitted readiness context"
            )
        validated = self.validate_payload(payload)
        if self.phase is CommandPhase.BOOTSTRAP:
            return _BootstrapCommandInvocation(validated, context.generation)
        return validated

    def invoke_prepared_for_bridge(self, invocation: object) -> object:
        """Invoke an exact payload already validated at bridge admission."""

        return self.handler(invocation)


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
    task_id: str
    command_id: str
    source_id: str
    target_id: str
    options: SetupOptionsView


@dataclass(frozen=True, slots=True)
class _ReadSetupPayload:
    task_id: str | None


@dataclass(frozen=True, slots=True)
class _PrepareSetupPayload:
    options: SetupOptionsView


@dataclass(frozen=True, slots=True)
class _AdmitLocationPayload:
    purpose: str
    candidate: LocationCandidate | None
    continuation_id: str | None = None
    mount_index: int | None = None


@dataclass(frozen=True, slots=True)
class _StartInventoryPayload:
    task_id: str
    command_id: str
    root_id: str


@dataclass(frozen=True, slots=True)
class _PlanAgainPayload:
    task_id: str
    command_id: str
    source_mount: str | None
    target_mount: str | None


@dataclass(frozen=True, slots=True)
class _CreateTaskPayload:
    command_id: str


@dataclass(frozen=True, slots=True)
class _NextEventsPayload:
    task_id: str
    session_id: str
    drain_id: str
    replay_from: int | None


@dataclass(frozen=True, slots=True)
class _CloseTaskPayload:
    task_id: str
    session_id: str | None


@dataclass(frozen=True, slots=True)
class _ReleaseTerminalSessionPayload:
    task_id: str
    session_id: str


@dataclass(frozen=True, slots=True)
class _ReadCosmeticSectionPayload:
    section: str
    value_version: int
    applied_presentation_revision: int | None


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
    appearance_acknowledged: Callable[[int], None] | None = None,
) -> Mapping[str, CommandSpec]:
    """Bind the exact production rows to process-local dependencies."""

    if not callable(picker):
        raise TypeError("picker must be callable")
    if not callable(shell_ready):
        raise TypeError("shell readiness callback must be callable")
    if not callable(readiness_echo):
        raise TypeError("readiness echo callback must be callable")
    if appearance_acknowledged is not None and not callable(
        appearance_acknowledged
    ):
        raise TypeError("appearance acknowledgment callback must be callable")
    if isinstance(registry, _TaskResponseCodecBinder):
        from .bridge import (
            BridgeResponseTooLargeError,
            _admit_task_drain_response_prefix,
            _consume_task_drain_response,
            _peek_task_drain_response,
        )
        from .drain import _TaskDrainResponseCodec

        registry.bind_response_codec(
            _TaskDrainResponseCodec(
                BridgeResponseTooLargeError,
                _admit_task_drain_response_prefix,
                _peek_task_drain_response,
                _consume_task_drain_response,
            )
        )

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
        return _admit_location_choice(
            payload.purpose,
            LocationCandidate.literal(selected[0]),
            registry,
            slots,
            allow_continuation=True,
        )

    def admit_location(payload: object) -> object:
        if type(payload) is not _AdmitLocationPayload:
            raise TypeError("admit_location received an unvalidated payload")
        if payload.candidate is not None:
            return _admit_location_choice(
                payload.purpose, payload.candidate, registry, slots
            )
        assert payload.continuation_id is not None
        assert payload.mount_index is not None
        candidate, binding, candidates, selected_mount = slots.resolve_continuation(
            payload.continuation_id,
            purpose=payload.purpose,
            mount_index=payload.mount_index,
        )
        if candidate.path is not None:
            selected = LocationCandidate.literal(
                candidate.path, selected_mount=selected_mount
            )
        else:
            assert candidate.location_id is not None
            selected = LocationCandidate.remembered(
                candidate.location_id, selected_mount=selected_mount
            )
        fresh = registry.admit_location_candidate(selected)
        if type(fresh) is not LocationCandidateResult:
            raise RuntimeError("location service returned invalid data")
        changed = (
            fresh.binding is None
            or fresh.binding.volume_id != binding.volume_id
            or fresh.binding.volume_relative_path != binding.volume_relative_path
            or fresh.binding.location_id != binding.location_id
            or fresh.candidates != candidates
        )
        if fresh.state is LocationCandidateState.AMBIGUOUS and changed:
            return _changed_location_choice(payload.purpose, fresh)
        if fresh.state is not LocationCandidateState.RESOLVED:
            return _location_choice_wire(
                payload.purpose,
                fresh,
                None,
                None,
                fresh.root_path,
                None if fresh.binding is None else fresh.binding.location_id,
            )
        if (
            changed
            or fresh.binding.selected_mount != selected_mount
        ):
            return _changed_location_choice(payload.purpose, fresh)
        return _admit_location_choice(
            payload.purpose, selected, registry, slots, admitted=fresh
        )

    def probe_recent_pairs(payload: object) -> object:
        if payload is not None:
            raise TypeError("probe_recent_pairs received an unvalidated payload")
        recents = registry.remembered_locations()
        if type(recents) is not RememberedLocations:
            raise RuntimeError("location service returned invalid recents")
        states: dict[int, str] = {}
        pairs: list[dict[str, object]] = []
        for pair in recents.pairs:
            for location in (pair.source, pair.target):
                if location.location_id in states:
                    continue
                result = registry.admit_location_candidate(
                    LocationCandidate.remembered(location.location_id)
                )
                if type(result) is not LocationCandidateResult:
                    raise RuntimeError("location service returned invalid data")
                states[location.location_id] = result.state.value
            pairs.append(
                {
                    "mapping_id": str(pair.mapping_id),
                    "source_id": str(pair.source.location_id),
                    "target_id": str(pair.target.location_id),
                    "source_state": states[pair.source.location_id],
                    "target_state": states[pair.target.location_id],
                }
            )
        return {"pairs": pairs}

    def prepare_setup(payload: object) -> object:
        if type(payload) is not _PrepareSetupPayload:
            raise TypeError("prepare_setup received an unvalidated payload")
        try:
            result = registry.prepare_setup_options(payload.options)
        except (TypeError, ValueError) as error:
            raise PlanningRefusedError("Setup options were refused") from error
        return _setup_options_to_wire(result)

    def read_setup(payload: object) -> object:
        if type(payload) is not _ReadSetupPayload:
            raise TypeError("read_setup received an unvalidated payload")
        if payload.task_id is None:
            snapshot = TaskSetupSnapshotView(
                "default",
                None,
                None,
                None,
                None,
                registry.read_setup_options(),
            )
            return {
                "task_id": None,
                "snapshot": _setup_snapshot_to_wire(snapshot),
                "recents": _remembered_locations_to_wire(
                    registry.remembered_locations()
                ),
            }
        return {
            "task_id": payload.task_id,
            "snapshot": _setup_snapshot_to_wire(
                registry.read_task_setup(payload.task_id)
            ),
            "recents": None,
        }

    def start_plan(payload: object) -> object:
        if not isinstance(payload, _StartPlanPayload):
            raise TypeError("start_plan received an unvalidated payload")
        wire_intent = (
            "start-plan",
            payload.task_id,
            payload.source_id,
            payload.target_id,
            _setup_options_signature(payload.options),
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
                    result = registry.start_setup_plan(
                        payload.task_id,
                        source,
                        target,
                        payload.options,
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

    def start_inventory(payload: object) -> object:
        if type(payload) is not _StartInventoryPayload:
            raise TypeError("start_inventory received an unvalidated payload")
        wire_intent = (
            "start-inventory",
            payload.task_id,
            payload.root_id,
        )
        try:
            result = registry.replay_start(payload.command_id, wire_intent)
            if result is None:
                try:
                    root = slots.resolve(payload.root_id, purpose="inventory")
                except SlotUnavailableError:
                    result = registry.replay_start(payload.command_id, wire_intent)
                    if result is None:
                        raise
                else:
                    result = registry.start_setup_inventory(
                        payload.task_id,
                        root,
                        command_id=payload.command_id,
                        wire_intent=wire_intent,
                    )
        except (CommandIdConflictError, TaskIntentConflictError) as error:
            raise CommandConflictError(
                "start_inventory command id conflicts with retained intent"
            ) from error
        except SyncPathInputError as error:
            raise PlanningRefusedError(
                "start_inventory root was refused"
            ) from error
        if not _is_valid_task_start(result):
            raise RuntimeError("inventory service returned invalid data")
        return result

    def plan_again(payload: object) -> object:
        if type(payload) is not _PlanAgainPayload:
            raise TypeError("plan_again received an unvalidated payload")
        wire_intent = (
            "plan-again",
            payload.task_id,
            payload.source_mount,
            payload.target_mount,
        )
        try:
            result = registry.replay_start(payload.command_id, wire_intent)
            if result is None:
                result = registry.start_plan_again(
                    payload.task_id,
                    source_mount=payload.source_mount,
                    target_mount=payload.target_mount,
                    command_id=payload.command_id,
                    wire_intent=wire_intent,
                )
        except (CommandIdConflictError, TaskIntentConflictError) as error:
            raise CommandConflictError(
                "plan_again command id conflicts with retained intent"
            ) from error
        except (SyncPathInputError, KeyError, ValueError) as error:
            raise PlanningRefusedError(
                "plan_again reviewed roots were refused"
            ) from error
        if not _is_valid_task_start(result):
            raise RuntimeError("Plan-again service returned invalid data")
        return result

    def create_task(payload: object) -> object:
        if not isinstance(payload, _CreateTaskPayload):
            raise TypeError("create_task received an unvalidated payload")
        try:
            result = registry.create_task_shell(payload.command_id)
        except TaskIntentConflictError as error:
            raise CommandConflictError(
                "create_task command id conflicts with retained intent"
            ) from error
        if type(result) is not TaskShellView:
            raise RuntimeError("task registry returned invalid shell data")
        result.__post_init__()
        return result

    def list_tasks(_payload: object) -> object:
        result = registry.list_tasks()
        if type(result) is not TaskListView:
            raise RuntimeError("task registry returned invalid task list")
        result.__post_init__()
        return result

    def next_events(payload: object) -> object:
        if not isinstance(payload, _NextEventsPayload):
            raise TypeError("next_events received an unvalidated payload")
        from .bridge import BridgeProtocolError, _peek_task_drain_response

        try:
            admitted = registry.drain_for_bridge(
                payload.task_id,
                payload.session_id,
                payload.drain_id,
                replay_from=payload.replay_from,
            )
            result = _peek_task_drain_response(admitted)
        except (BridgeProtocolError, TypeError):
            raise RuntimeError("task registry returned invalid drain data") from None
        if (
            type(result) is not TaskDrainView
            or result.task_id != payload.task_id
            or result.session_id != payload.session_id
            or result.drain_id != payload.drain_id
        ):
            raise RuntimeError("task registry returned invalid drain data")
        return admitted

    def close_task(payload: object) -> object:
        if not isinstance(payload, _CloseTaskPayload):
            raise TypeError("close_task received an unvalidated payload")
        result = registry.request_task_close(payload.task_id, payload.session_id)
        if (
            type(result) is not TaskCloseRequestView
            or result.task_id != payload.task_id
            or result.session_id != payload.session_id
        ):
            raise RuntimeError("task registry returned invalid close data")
        result.__post_init__()
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
        if (
            payload.applied_presentation_revision is not None
            and appearance_acknowledged is not None
        ):
            appearance_acknowledged(payload.applied_presentation_revision)
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
            "read_setup": CommandSpec(
                validate_payload=_validate_read_setup,
                handler=read_setup,
                access=CommandAccess.READ_ONLY,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.LOCAL_5_SECONDS,
                retry=CommandRetry.SAME_PAYLOAD_ONCE,
            ),
            "probe_recent_pairs": CommandSpec(
                validate_payload=_validate_probe_recent_pairs,
                handler=probe_recent_pairs,
                access=CommandAccess.READ_ONLY,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.LOCAL_5_SECONDS,
                retry=CommandRetry.NONE,
                work=CommandWork.ASYNC_SMALL,
            ),
            "prepare_setup": CommandSpec(
                validate_payload=_validate_prepare_setup,
                handler=prepare_setup,
                access=CommandAccess.READ_ONLY,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.LOCAL_5_SECONDS,
                retry=CommandRetry.SAME_PAYLOAD_ONCE,
            ),
            "admit_location": CommandSpec(
                validate_payload=_validate_admit_location,
                handler=admit_location,
                access=CommandAccess.READ_ONLY,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.LOCAL_5_SECONDS,
                retry=CommandRetry.NONE,
            ),
            "create_task": CommandSpec(
                validate_payload=_validate_create_task,
                handler=create_task,
                access=CommandAccess.MUTATING,
                command_id=FieldRequirement.REQUIRED,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.MUTATION_30_SECONDS,
                retry=CommandRetry.SAME_COMMAND_ONCE,
                work=CommandWork.ASYNC_SMALL,
            ),
            "list_tasks": CommandSpec(
                validate_payload=_validate_empty_payload,
                handler=list_tasks,
                access=CommandAccess.READ_ONLY,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.LOCAL_5_SECONDS,
                retry=CommandRetry.SAME_PAYLOAD_ONCE,
            ),
            "start_plan": CommandSpec(
                validate_payload=_validate_start_plan,
                handler=start_plan,
                access=CommandAccess.MUTATING,
                command_id=FieldRequirement.REQUIRED,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.MUTATION_30_SECONDS,
                retry=CommandRetry.SAME_COMMAND_ONCE,
                work=CommandWork.ASYNC_SMALL,
            ),
            "start_inventory": CommandSpec(
                validate_payload=_validate_start_inventory,
                handler=start_inventory,
                access=CommandAccess.MUTATING,
                command_id=FieldRequirement.REQUIRED,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.MUTATION_30_SECONDS,
                retry=CommandRetry.SAME_COMMAND_ONCE,
                work=CommandWork.ASYNC_SMALL,
            ),
            "plan_again": CommandSpec(
                validate_payload=_validate_plan_again,
                handler=plan_again,
                access=CommandAccess.MUTATING,
                command_id=FieldRequirement.REQUIRED,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.MUTATION_30_SECONDS,
                retry=CommandRetry.SAME_COMMAND_ONCE,
                work=CommandWork.ASYNC_SMALL,
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
                work=CommandWork.ASYNC_SMALL,
            ),
            "close_task": CommandSpec(
                validate_payload=_validate_close_task,
                handler=close_task,
                access=CommandAccess.MUTATING,
                command_id=FieldRequirement.FORBIDDEN,
                revision=FieldRequirement.FORBIDDEN,
                timeout=CommandTimeout.MUTATION_30_SECONDS,
                retry=CommandRetry.SAME_PAYLOAD_BOUNDED,
                work=CommandWork.ASYNC_SMALL,
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
    if type(purpose) is not str or purpose not in {
        "source",
        "target",
        "inventory",
    }:
        raise CommandPayloadError("pick_folder payload is invalid")
    return _PickFolderPayload(purpose)


def _validate_start_plan(value: object) -> _StartPlanPayload:
    if not isinstance(value, dict) or set(value) != {
        "task_id",
        "command_id",
        "source_id",
        "target_id",
        "options",
    }:
        raise CommandPayloadError("start_plan payload is invalid")
    task_id = value["task_id"]
    command_id = value["command_id"]
    source_id = value["source_id"]
    target_id = value["target_id"]
    options = value["options"]
    if type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None:
        raise CommandPayloadError("start_plan payload is invalid")
    if type(command_id) is not str or _OPAQUE_ID.fullmatch(command_id) is None:
        raise CommandPayloadError("start_plan payload is invalid")
    if type(source_id) is not str or _SLOT_ID.fullmatch(source_id) is None:
        raise CommandPayloadError("start_plan payload is invalid")
    if type(target_id) is not str or _SLOT_ID.fullmatch(target_id) is None:
        raise CommandPayloadError("start_plan payload is invalid")
    return _StartPlanPayload(
        task_id=task_id,
        command_id=command_id,
        source_id=source_id,
        target_id=target_id,
        options=_validate_setup_options(options, "start_plan"),
    )


def _validate_read_setup(value: object) -> _ReadSetupPayload:
    if type(value) is not dict or set(value) != {"task_id"}:
        raise CommandPayloadError("read_setup payload is invalid")
    task_id = value["task_id"]
    if task_id is not None and (
        type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None
    ):
        raise CommandPayloadError("read_setup payload is invalid")
    return _ReadSetupPayload(task_id)


def _validate_probe_recent_pairs(value: object) -> None:
    if type(value) is not dict or value:
        raise CommandPayloadError("probe_recent_pairs payload is invalid")


def _validate_prepare_setup(value: object) -> _PrepareSetupPayload:
    if type(value) is not dict or set(value) != {"options"}:
        raise CommandPayloadError("prepare_setup payload is invalid")
    return _PrepareSetupPayload(
        _validate_setup_options(value["options"], "prepare_setup")
    )


def _validate_admit_location(value: object) -> _AdmitLocationPayload:
    if type(value) is not dict:
        raise CommandPayloadError("admit_location payload is invalid")
    keys = set(value)
    if keys not in (
        {"purpose", "candidate"},
        {"purpose", "continuation_id", "mount_index"},
    ):
        raise CommandPayloadError("admit_location payload is invalid")
    purpose = value["purpose"]
    if type(purpose) is not str or purpose not in {
        "source",
        "target",
        "inventory",
    }:
        raise CommandPayloadError("admit_location payload is invalid")
    if keys == {"purpose", "candidate"}:
        return _AdmitLocationPayload(
            purpose,
            _validate_location_candidate(value["candidate"]),
        )
    if keys == {"purpose", "continuation_id", "mount_index"}:
        continuation_id = value["continuation_id"]
        mount_index = value["mount_index"]
        if (
            type(continuation_id) is not str
            or _SLOT_ID.fullmatch(continuation_id) is None
            or type(mount_index) is not int
            or mount_index < 0
        ):
            raise CommandPayloadError("admit_location payload is invalid")
        return _AdmitLocationPayload(
            purpose, None, continuation_id, mount_index
        )
    raise CommandPayloadError("admit_location payload is invalid")


def _validate_start_inventory(value: object) -> _StartInventoryPayload:
    if type(value) is not dict or set(value) != {
        "task_id",
        "command_id",
        "root_id",
    }:
        raise CommandPayloadError("start_inventory payload is invalid")
    task_id = value["task_id"]
    command_id = value["command_id"]
    root_id = value["root_id"]
    if (
        type(task_id) is not str
        or _TASK_ID.fullmatch(task_id) is None
        or type(command_id) is not str
        or _OPAQUE_ID.fullmatch(command_id) is None
        or type(root_id) is not str
        or _SLOT_ID.fullmatch(root_id) is None
    ):
        raise CommandPayloadError("start_inventory payload is invalid")
    return _StartInventoryPayload(task_id, command_id, root_id)


def _validate_plan_again(value: object) -> _PlanAgainPayload:
    if type(value) is not dict or set(value) != {
        "task_id",
        "command_id",
        "source_mount",
        "target_mount",
    }:
        raise CommandPayloadError("plan_again payload is invalid")
    task_id = value["task_id"]
    command_id = value["command_id"]
    source_mount = value["source_mount"]
    target_mount = value["target_mount"]
    if (
        type(task_id) is not str
        or _TASK_ID.fullmatch(task_id) is None
        or type(command_id) is not str
        or _OPAQUE_ID.fullmatch(command_id) is None
    ):
        raise CommandPayloadError("plan_again payload is invalid")
    for mount in (source_mount, target_mount):
        if mount is not None:
            try:
                LocationCandidate.literal(mount)
            except (TypeError, ValueError) as error:
                raise CommandPayloadError(
                    "plan_again payload is invalid"
                ) from error
    return _PlanAgainPayload(
        task_id,
        command_id,
        source_mount,
        target_mount,
    )


def _validate_create_task(value: object) -> _CreateTaskPayload:
    if not isinstance(value, dict) or set(value) != {"command_id"}:
        raise CommandPayloadError("create_task payload is invalid")
    command_id = value["command_id"]
    if type(command_id) is not str or _OPAQUE_ID.fullmatch(command_id) is None:
        raise CommandPayloadError("create_task payload is invalid")
    return _CreateTaskPayload(command_id)


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
    if session_id is not None and (
        type(session_id) is not str or _OPAQUE_ID.fullmatch(session_id) is None
    ):
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


def _validate_setup_options(value: object, command: str) -> SetupOptionsView:
    if type(value) is not dict or set(value) != {
        "filters",
        "deletion_policy",
        "trash_on_update",
        "preservation",
        "propagate_source_casing",
        "verify_after_execute",
    }:
        raise CommandPayloadError(f"{command} payload is invalid")
    filters = value["filters"]
    preservation = value["preservation"]
    if (
        type(filters) is not list
        or not all(type(pattern) is str for pattern in filters)
        or type(preservation) is not dict
        or set(preservation) != {
            "preserve_ads",
            "preserve_created",
            "preserve_acl",
        }
    ):
        raise CommandPayloadError(f"{command} payload is invalid")
    try:
        return SetupOptionsView(
            tuple(filters),
            value["deletion_policy"],
            value["trash_on_update"],
            PreservationSettingsView(
                preservation["preserve_ads"],
                preservation["preserve_created"],
                preservation["preserve_acl"],
            ),
            value["propagate_source_casing"],
            value["verify_after_execute"],
        )
    except (TypeError, ValueError, UnicodeError) as error:
        raise CommandPayloadError(f"{command} payload is invalid") from error


def _validate_location_candidate(value: object) -> LocationCandidate:
    if type(value) is not dict or "kind" not in value:
        raise CommandPayloadError("admit_location payload is invalid")
    kind = value["kind"]
    selected_mount = value.get("selected_mount")
    try:
        if kind == "literal_path" and set(value) == {
            "kind",
            "path",
            "selected_mount",
        }:
            return LocationCandidate.literal(
                value["path"],
                selected_mount=selected_mount,
            )
        if kind == "remembered_location" and set(value) == {
            "kind",
            "location_id",
            "selected_mount",
        }:
            location_id = value["location_id"]
            if (
                type(location_id) is not str
                or not location_id.isascii()
                or not location_id.isdecimal()
                or str(int(location_id)) != location_id
                or int(location_id) < 1
                or int(location_id) > (1 << 63) - 1
            ):
                raise ValueError("remembered location id is invalid")
            return LocationCandidate.remembered(
                int(location_id),
                selected_mount=selected_mount,
            )
    except (TypeError, ValueError, UnicodeError) as error:
        raise CommandPayloadError("admit_location payload is invalid") from error
    raise CommandPayloadError("admit_location payload is invalid")


def _admit_location_choice(
    purpose: str,
    candidate: LocationCandidate,
    registry: TaskAuthority,
    slots: FolderSlotAuthority,
    *,
    admitted: LocationCandidateResult | None = None,
    allow_continuation: bool = False,
) -> dict[str, object]:
    result = (
        registry.admit_location_candidate(candidate)
        if admitted is None
        else admitted
    )
    if type(result) is not LocationCandidateResult:
        raise RuntimeError("location service returned invalid data")
    choice_id = None
    continuation_id = None
    display = result.root_path
    if result.state is LocationCandidateState.RESOLVED:
        assert result.root_path is not None
        stored = slots.store(
            candidate,
            purpose=purpose,
            display=result.root_path,
        )
        if (
            type(stored) is not tuple
            or len(stored) != 2
            or type(stored[0]) is not str
            or _SLOT_ID.fullmatch(stored[0]) is None
            or type(stored[1]) is not str
        ):
            raise RuntimeError("folder slot authority returned invalid data")
        choice_id, stored_display = stored
        if stored_display != result.root_path:
            raise RuntimeError("folder slot authority changed location display")
    elif result.state is LocationCandidateState.AMBIGUOUS and allow_continuation:
        display = candidate.path

        def admit_response(
            slot_id: str,
            retained: dict[str, object],
        ) -> object:
            from .bridge import snapshot_bridge_response_result

            admitted = snapshot_bridge_response_result(
                {
                    "continuation": retained,
                    "response": _location_choice_wire(
                        purpose, result, None, slot_id, display
                    ),
                },
                "0" * 32,
            )
            if type(admitted) is not dict or set(admitted) != {
                "continuation", "response",
            }:
                raise RuntimeError(
                    "bridge response admission returned invalid continuation state"
                )
            return admitted["continuation"]

        continuation_id = slots.store_continuation(
            candidate,
            result,
            purpose=purpose,
            admit=admit_response,
        )
    location_id = (
        result.binding.location_id
        if result.binding is not None
        else candidate.location_id
    )
    return _location_choice_wire(
        purpose, result, choice_id, continuation_id, display, location_id
    )


def _location_choice_wire(
    purpose: str,
    result: LocationCandidateResult,
    choice_id: str | None,
    continuation_id: str | None,
    display: str | None,
    location_id: int | None = None,
) -> dict[str, object]:
    return {
        "purpose": purpose,
        "state": result.state.value,
        "choice_id": choice_id,
        "continuation_id": continuation_id,
        "display": display,
        "location_id": None if location_id is None else str(location_id),
        "candidates": list(result.candidates),
        "detail": result.detail,
    }


def _changed_location_choice(
    purpose: str,
    result: LocationCandidateResult,
) -> dict[str, object]:
    return {
        "purpose": purpose,
        "state": "changed",
        "choice_id": None,
        "continuation_id": None,
        "display": result.root_path,
        "location_id": (
            None
            if result.binding is None or result.binding.location_id is None
            else str(result.binding.location_id)
        ),
        "candidates": list(result.candidates),
        "detail": result.detail or "The selected volume identity changed.",
    }


def _setup_options_to_wire(value: SetupOptionsView) -> dict[str, object]:
    if type(value) is not SetupOptionsView:
        raise RuntimeError("Setup authority returned invalid options")
    value.__post_init__()
    return {
        "filters": list(value.filters),
        "deletion_policy": value.deletion_policy,
        "trash_on_update": value.trash_on_update,
        "preservation": {
            "preserve_ads": value.preservation.preserve_ads,
            "preserve_created": value.preservation.preserve_created,
            "preserve_acl": value.preservation.preserve_acl,
        },
        "propagate_source_casing": value.propagate_source_casing,
        "verify_after_execute": value.verify_after_execute,
    }


def _setup_options_signature(value: SetupOptionsView) -> tuple[object, ...]:
    """Project complete Setup options into the domain-blind replay alphabet."""

    return (
        value.filters,
        value.deletion_policy,
        value.trash_on_update,
        (
            value.preservation.preserve_ads,
            value.preservation.preserve_created,
            value.preservation.preserve_acl,
        ),
        value.propagate_source_casing,
        value.verify_after_execute,
    )


def _setup_snapshot_to_wire(value: TaskSetupSnapshotView) -> dict[str, object]:
    if type(value) is not TaskSetupSnapshotView:
        raise RuntimeError("task authority returned invalid Setup snapshot")
    value.__post_init__()

    def location(item):
        return None if item is None else {
            "display": item.display,
            "location_id": item.location_id,
        }

    readiness = value.plan_again
    return {
        "setup_state": value.setup_state,
        "task_kind": value.task_kind,
        "source": location(value.source),
        "target": location(value.target),
        "root": location(value.root),
        "options": (
            None if value.options is None else _setup_options_to_wire(value.options)
        ),
        "plan_again": None if readiness is None else {
            "source_state": readiness.source_state,
            "source_candidates": list(readiness.source_candidates),
            "target_state": readiness.target_state,
            "target_candidates": list(readiness.target_candidates),
        },
    }


def _remembered_locations_to_wire(value: RememberedLocations) -> dict[str, object]:
    if type(value) is not RememberedLocations:
        raise RuntimeError("location service returned invalid recents")

    def location(item):
        if item.mount_hint is None:
            display = item.volume_relative_path or "Volume root"
        elif item.volume_relative_path:
            display = item.mount_hint.rstrip("\\/") + "\\" + item.volume_relative_path
        else:
            display = item.mount_hint
        return {
            "location_id": str(item.location_id),
            "display": display,
            "last_used_at": item.last_used_at.isoformat(),
        }

    return {
        "sources": [location(item) for item in value.sources],
        "targets": [location(item) for item in value.targets],
        "pairs": [
            {
                "mapping_id": str(item.mapping_id),
                "source": location(item.source),
                "target": location(item.target),
                "last_used_at": item.last_used_at.isoformat(),
            }
            for item in value.pairs
        ],
    }


def _validate_read_cosmetic_section(
    value: object,
) -> _ReadCosmeticSectionPayload:
    if type(value) is not dict or set(value) != {
        "section",
        "value_version",
        "applied_presentation_revision",
    }:
        raise CommandPayloadError("read_cosmetic_section payload is invalid")
    section = value["section"]
    value_version = value["value_version"]
    applied_revision = value["applied_presentation_revision"]
    if (
        type(section) is not str
        or section != "appearance"
        or type(value_version) is not int
        or value_version != APPEARANCE_VALUE_VERSION
        or (
            applied_revision is not None
            and not _is_javascript_safe_integer(applied_revision)
        )
    ):
        raise CommandPayloadError("read_cosmetic_section payload is invalid")
    return _ReadCosmeticSectionPayload(
        section,
        value_version,
        applied_revision,
    )


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
