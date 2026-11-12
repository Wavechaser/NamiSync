"""Construct the real service around explicit, test-owned collaborators."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import namisync.interfaces.service as service_module
from namisync.interfaces.service import NamiSyncService
from namisync.core.models import VolumeId
from namisync.workflows import (
    LocationCandidate,
    LocationCandidateResult,
    LocationCandidateState,
    validate_sync_paths,
)
from namisync.workflows.inventory import LocationBinding


def _admit_test_plan_locations(
    source: str,
    target: str,
) -> tuple[LocationCandidateResult, LocationCandidateResult]:
    source_path, target_path = validate_sync_paths(source, target)

    def result(candidate_path) -> LocationCandidateResult:
        root = str(candidate_path)
        binding = LocationBinding(
            VolumeId("test-volume", "NTFS"),
            "",
            root,
            (root,),
            False,
        )
        return LocationCandidateResult(
            LocationCandidate.literal(root),
            LocationCandidateState.RESOLVED,
            binding=binding,
            root_path=root,
            candidates=(root,),
        )

    return result(source_path), result(target_path)


def make_service(*, runtime=None, dispatcher=None, observer=None) -> NamiSyncService:
    runtime = SimpleNamespace() if runtime is None else runtime
    if not hasattr(runtime, "admit_plan_locations"):
        runtime.admit_plan_locations = _admit_test_plan_locations
    dispatcher = SimpleNamespace() if dispatcher is None else dispatcher
    observer = SimpleNamespace() if observer is None else observer
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(service_module, "LocalWorkflowRuntime", lambda *_args, **_kwargs: runtime)
        patch.setattr(service_module, "_dispatcher", lambda _runtime: dispatcher)
        patch.setattr(service_module, "SessionObserver", lambda _dispatcher: observer)
        return NamiSyncService("test-ledger.db", "test-history.db")
