"""Exact production command policies and dependency-bound handlers."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from namisync.interfaces.service import (
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
    ResultCategory,
    ScanWarningView,
    SelectionMutationView,
    SelectionOperationView,
    SelectionPreviewView,
    SemanticSettingsPatchView,
    SemanticSettingsView,
    SessionEventView,
    SessionRecordView,
    ShutdownView,
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
_SLOT_ID = re.compile(r"slot-[0-9a-f]{32}")

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
        ResultCategory,
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
PUBLIC_VIEW_DATACLASSES = (
    SERVICE_PUBLIC_VIEW_DATACLASSES | NESTED_PUBLIC_VIEW_DATACLASSES
)
PUBLIC_VIEW_ENUMS: frozenset[type[object]] = frozenset()


class CommandPayloadError(ValueError):
    """A command payload does not match its exact declared schema."""


class PickerUnavailableError(RuntimeError):
    """The native picker did not return its documented result shape."""


class CommandAccess(StrEnum):
    READ_ONLY = "read-only"
    MUTATING = "mutating"


class FieldRequirement(StrEnum):
    FORBIDDEN = "forbidden"
    REQUIRED = "required"


class CommandTimeout(StrEnum):
    INTERACTIVE = "interactive"
    MUTATION_30_SECONDS = "mutation-30-seconds"


class CommandRetry(StrEnum):
    NONE = "none"
    SAME_COMMAND_ONCE = "same-command-once"


class FolderSlotAuthority(Protocol):
    """Consumer contract for the path-owning slot table added separately."""

    def store(self, path: str, *, purpose: str) -> tuple[str, str]: ...

    def resolve_pair(self, source_id: str, target_id: str) -> tuple[str, str]: ...


class PlanningService(Protocol):
    def start_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None = None,
        command_id: str | None = None,
    ) -> object: ...


PayloadValidator = Callable[[object], object]
CommandHandler = Callable[[object], object]
FolderPicker = Callable[[], Sequence[str] | None]


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

    def invoke(self, payload: object) -> object:
        return self.handler(self.validate_payload(payload))


@dataclass(frozen=True, slots=True)
class _PickFolderPayload:
    purpose: str


@dataclass(frozen=True, slots=True)
class _StartPlanPayload:
    command_id: str
    source_id: str
    target_id: str
    deletion_policy: str | None


def production_command_specs(
    *,
    picker: FolderPicker,
    slots: FolderSlotAuthority,
    service: PlanningService,
) -> Mapping[str, CommandSpec]:
    """Bind the exact two production rows to process-local dependencies."""

    if not callable(picker):
        raise TypeError("picker must be callable")

    def pick_folder(payload: object) -> object:
        if not isinstance(payload, _PickFolderPayload):
            raise TypeError("pick_folder received an unvalidated payload")
        selected = picker()
        if selected is None:
            return None
        if (
            isinstance(selected, (str, bytes))
            or not isinstance(selected, Sequence)
            or len(selected) != 1
            or not isinstance(selected[0], str)
            or not selected[0]
        ):
            raise PickerUnavailableError("native folder picker returned invalid data")
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
        source, target = slots.resolve_pair(payload.source_id, payload.target_id)
        return service.start_plan(
            source,
            target,
            deletion_policy=payload.deletion_policy,
            command_id=payload.command_id,
        )

    return MappingProxyType(
        {
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
        }
    )


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
