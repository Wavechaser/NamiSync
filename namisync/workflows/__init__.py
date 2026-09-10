"""Workflow coordination and local M0 composition for NamiSync."""

from namisync.core.integrity import IntegrityMode
from namisync.core.planning import DeletionPolicy, SyncOptions
from namisync.workflows.inventory import (
    IntegrityRequest,
    InventoryDetails,
    InventoryRequest,
    LocationCandidate,
    LocationCandidateKind,
    LocationCandidateResult,
    LocationCandidateState,
    RememberedLocation,
    RememberedLocations,
    RememberedPair,
    VolumeResolution,
    VolumeResolutionRequired,
    VolumeResolutionState,
)
from namisync.workflows.database_pair import DatabasePairContract
from namisync.workflows.models import (
    ExecutionDetails,
    ExecutionRequest,
    HistoryEventView,
    HistoryEventPageView,
    HistoryItemPageView,
    HistoryItemView,
    HistoryRunSummaryView,
    PlanRequest,
    PlanReview,
)
from namisync.workflows.runtime import (
    BASELINE_KIND,
    EXECUTION_KIND,
    INVENTORY_KIND,
    PLAN_KIND,
    REBASELINE_KIND,
    VERIFY_KIND,
    LocalWorkflowRuntime,
    default_database_paths,
)
from namisync.workflows.sync import (
    SyncDependencies,
    run_execution,
    run_plan,
    validate_sync_paths,
)


def sync_options(deletion_policy: str) -> SyncOptions:
    """Translate the M0 public deletion choices into typed plan options."""

    return SyncOptions(deletion_policy=DeletionPolicy(deletion_policy))


def integrity_request(
    mode: str,
    request_id: str,
    *,
    root_path: str | None = None,
    location_id: int | None = None,
    selected_paths: tuple[str, ...] = (),
    selected_mount: str | None = None,
) -> IntegrityRequest:
    """Translate a primitive interface request into a typed integrity request."""

    return IntegrityRequest(
        request_id=request_id,
        mode=IntegrityMode(mode),
        root_path=root_path,
        location_id=location_id,
        selected_paths=selected_paths,
        selected_mount=selected_mount,
    )


__all__ = [
    "BASELINE_KIND",
    "DatabasePairContract",
    "EXECUTION_KIND",
    "ExecutionDetails",
    "ExecutionRequest",
    "HistoryEventPageView",
    "HistoryEventView",
    "HistoryItemPageView",
    "HistoryItemView",
    "HistoryRunSummaryView",
    "INVENTORY_KIND",
    "IntegrityRequest",
    "InventoryDetails",
    "InventoryRequest",
    "LocationCandidate",
    "LocationCandidateKind",
    "LocationCandidateResult",
    "LocationCandidateState",
    "LocalWorkflowRuntime",
    "PLAN_KIND",
    "PlanRequest",
    "PlanReview",
    "REBASELINE_KIND",
    "RememberedLocation",
    "RememberedLocations",
    "RememberedPair",
    "SyncDependencies",
    "VERIFY_KIND",
    "VolumeResolution",
    "VolumeResolutionRequired",
    "VolumeResolutionState",
    "default_database_paths",
    "integrity_request",
    "run_execution",
    "run_plan",
    "sync_options",
    "validate_sync_paths",
]
