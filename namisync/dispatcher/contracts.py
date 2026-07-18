"""Public, domain-blind dispatcher collaborator contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Mapping, Protocol

from namisync.core.events import Envelope
from namisync.core.session import (
    OperationResult,
    ResourceId,
    RunContext,
    SessionId,
    SessionRecord,
    SessionState,
    is_terminal,
)


@dataclass(frozen=True, slots=True)
class PreparedSession:
    """Opaque workflow bytes plus generic resources required for custody."""

    payload: bytes
    resources: frozenset[ResourceId] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.payload, bytes):
            raise TypeError("prepared workflow payload must be bytes")
        if not all(isinstance(resource, ResourceId) for resource in self.resources):
            raise TypeError("prepared resources must contain ResourceId values")


class WorkflowInvocation(Protocol):
    """Adapter-owned decoded invocation; dispatcher never inspects it."""

    def run(self, context: RunContext) -> OperationResult: ...

    def snapshot(self) -> bytes:
        """Serialize continuation after a cooperative pause."""


@dataclass(frozen=True, slots=True)
class WorkflowRegistration:
    """Generic preparation/invocation adapter and capability metadata."""

    prepare: Callable[[object], PreparedSession]
    open: Callable[[bytes], WorkflowInvocation]
    supports_pause: bool = False


Registry = Mapping[str, WorkflowRegistration]


class AuditObserver(Protocol):
    """Admission-time reliable observer implemented outside dispatcher."""

    def on_event(self, envelope: Envelope) -> None: ...

    def finalize(self, result: OperationResult) -> None: ...

    def close(self) -> None: ...


AuditObserverFactory = Callable[[SessionRecord], AuditObserver | None]


class ControlCode(StrEnum):
    ACCEPTED = "accepted"
    NOT_FOUND = "not-found"
    ILLEGAL_STATE = "illegal-state"
    UNSUPPORTED = "unsupported"


class ControlAction(StrEnum):
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"


def control_decision(
    action: ControlAction, state: SessionState, supports_pause: bool
) -> ControlCode:
    """Return the state-preserving control decision for the frozen matrix."""

    if action is ControlAction.PAUSE:
        if not supports_pause:
            return ControlCode.UNSUPPORTED
        return (
            ControlCode.ACCEPTED
            if state is SessionState.RUNNING
            else ControlCode.ILLEGAL_STATE
        )
    if action is ControlAction.RESUME:
        return (
            ControlCode.ACCEPTED
            if state in (SessionState.PAUSED, SessionState.INTERRUPTED)
            else ControlCode.ILLEGAL_STATE
        )
    if action is ControlAction.CANCEL:
        return (
            ControlCode.ACCEPTED
            if not is_terminal(state) and state is not SessionState.CANCELING
            else ControlCode.ILLEGAL_STATE
        )
    raise ValueError(f"unknown control action: {action!r}")


@dataclass(frozen=True, slots=True)
class ControlResult:
    code: ControlCode
    session_id: SessionId
    before: SessionState | None
    after: SessionState | None
    detail: str

    @property
    def accepted(self) -> bool:
        return self.code is ControlCode.ACCEPTED


@dataclass(frozen=True, slots=True)
class ShutdownResult:
    complete: bool
    unfinished: tuple[SessionId, ...]
    custody_released: bool


class UnknownWorkflowKind(KeyError):
    pass


class AdmissionClosed(RuntimeError):
    pass


class SessionNotFound(KeyError):
    pass


class SessionNotTerminal(RuntimeError):
    pass
