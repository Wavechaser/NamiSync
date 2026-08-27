"""Domain-blind session dispatch and control."""

from namisync.core.exception_graph import retire_exception_graph
from namisync.dispatcher.contracts import (
    AdmissionClosed,
    AuditObserver,
    ControlAction,
    ControlCode,
    ControlResult,
    PreparedSession,
    SessionCleanupPending,
    SessionNotFound,
    SessionNotTerminal,
    ShutdownResult,
    UnknownWorkflowKind,
    WorkflowInvocation,
    WorkflowRegistration,
)
from namisync.dispatcher.custody import (
    InProcessResourceLockProvider,
    ResourceLease,
    ResourceLockProvider,
    WindowsNamedMutexProvider,
)
from namisync.dispatcher.dispatcher import Dispatcher
from namisync.dispatcher.event_bus import EventStream, UtcClock
from namisync.dispatcher.store import InMemorySessionStore

__all__ = [
    "AdmissionClosed",
    "AuditObserver",
    "ControlAction",
    "ControlCode",
    "ControlResult",
    "Dispatcher",
    "EventStream",
    "InMemorySessionStore",
    "InProcessResourceLockProvider",
    "PreparedSession",
    "ResourceLease",
    "ResourceLockProvider",
    "retire_exception_graph",
    "SessionCleanupPending",
    "SessionNotFound",
    "SessionNotTerminal",
    "ShutdownResult",
    "UnknownWorkflowKind",
    "UtcClock",
    "WindowsNamedMutexProvider",
    "WorkflowInvocation",
    "WorkflowRegistration",
]
