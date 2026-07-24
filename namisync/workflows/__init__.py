"""Workflow coordination and local M0 composition for NamiSync."""

from namisync.core.planning import DeletionPolicy, SyncOptions
from namisync.workflows.inventory import (
    IntegrityRequest,
    InventoryDetails,
    InventoryRequest,
    VolumeResolution,
    VolumeResolutionRequired,
    VolumeResolutionState,
)
from namisync.workflows.models import (
    ExecutionDetails,
    ExecutionRequest,
    HistoryRunView,
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
from namisync.workflows.sync import SyncDependencies, run_execution, run_plan


def sync_options(deletion_policy: str) -> SyncOptions:
    """Translate the M0 public deletion choices into typed plan options."""

    return SyncOptions(deletion_policy=DeletionPolicy(deletion_policy))


__all__ = [
    "BASELINE_KIND",
    "EXECUTION_KIND",
    "ExecutionDetails",
    "ExecutionRequest",
    "HistoryRunView",
    "INVENTORY_KIND",
    "IntegrityRequest",
    "InventoryDetails",
    "InventoryRequest",
    "LocalWorkflowRuntime",
    "PLAN_KIND",
    "PlanRequest",
    "PlanReview",
    "REBASELINE_KIND",
    "SyncDependencies",
    "VERIFY_KIND",
    "VolumeResolution",
    "VolumeResolutionRequired",
    "VolumeResolutionState",
    "default_database_paths",
    "run_execution",
    "run_plan",
    "sync_options",
]
