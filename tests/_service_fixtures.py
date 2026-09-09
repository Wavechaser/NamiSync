"""Construct the real service around explicit, test-owned collaborators."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import namisync.interfaces.service as service_module
from namisync.interfaces.service import NamiSyncService


def make_service(*, runtime=None, dispatcher=None, observer=None) -> NamiSyncService:
    runtime = SimpleNamespace() if runtime is None else runtime
    dispatcher = SimpleNamespace() if dispatcher is None else dispatcher
    observer = SimpleNamespace() if observer is None else observer
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(service_module, "LocalWorkflowRuntime", lambda *_args, **_kwargs: runtime)
        patch.setattr(service_module, "_dispatcher", lambda _runtime: dispatcher)
        patch.setattr(service_module, "SessionObserver", lambda _dispatcher: observer)
        return NamiSyncService("test-ledger.db", "test-history.db")
