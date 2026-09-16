"""Workflow coordination and local M0 composition for NamiSync."""

from namisync.core.integrity import IntegrityMode
from namisync.core.models import VolumeId
from namisync.core.planning import (
    DeletionPolicy,
    FilterSet,
    PreservationPolicy,
    SyncOptions,
)
from namisync.workflows.inventory import (
    IntegrityRequest,
    InventoryDetails,
    InventoryRequest,
    LocationCandidate,
    LocationCandidateKind,
    LocationCandidateResult,
    LocationCandidateState,
    LocationBinding,
    RememberedLocation,
    RememberedLocations,
    RememberedPair,
    VolumeResolution,
    VolumeResolutionRequired,
    VolumeResolutionState,
    resolve_reviewed_binding,
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
from namisync.workflows.plan_projection import (
    CompactUnsignedIntegers,
    PlanProjection,
    PlanProjectionNode,
    PlanProjectionOrder,
    PlanSortColumn,
    SortDirection,
    apply_plan_projection_selection,
    build_plan_projection,
    sort_plan_projection,
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
    "CompactUnsignedIntegers",
    "DatabasePairContract",
    "EXECUTION_KIND",
    "ExecutionDetails",
    "ExecutionRequest",
    "FilterSet",
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
    "LocationBinding",
    "LocalWorkflowRuntime",
    "PLAN_KIND",
    "PlanRequest",
    "PlanReview",
    "PlanProjection",
    "PlanProjectionNode",
    "PlanProjectionOrder",
    "PlanSortColumn",
    "PreservationPolicy",
    "REBASELINE_KIND",
    "RememberedLocation",
    "RememberedLocations",
    "RememberedPair",
    "SyncDependencies",
    "SyncOptions",
    "SortDirection",
    "VERIFY_KIND",
    "VolumeResolution",
    "VolumeResolutionRequired",
    "VolumeResolutionState",
    "VolumeId",
    "resolve_reviewed_binding",
    "default_database_paths",
    "apply_plan_projection_selection",
    "build_plan_projection",
    "integrity_request",
    "run_execution",
    "run_plan",
    "sort_plan_projection",
    "sync_options",
    "validate_sync_paths",
]
