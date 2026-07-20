"""Workflow coordination and local M0 composition for NamiSync."""

from namisync.core.planning import DeletionPolicy, SyncOptions
from namisync.workflows.models import (
    ExecutionDetails,
    ExecutionRequest,
    HistoryRunView,
    PlanRequest,
    PlanReview,
)
from namisync.workflows.runtime import (
    EXECUTION_KIND,
    PLAN_KIND,
    LocalWorkflowRuntime,
    default_database_paths,
)
from namisync.workflows.sync import SyncDependencies, run_execution, run_plan


def sync_options(deletion_policy: str) -> SyncOptions:
    """Translate the M0 public deletion choices into typed plan options."""

    return SyncOptions(deletion_policy=DeletionPolicy(deletion_policy))


__all__ = [
    "EXECUTION_KIND",
    "ExecutionDetails",
    "ExecutionRequest",
    "HistoryRunView",
    "LocalWorkflowRuntime",
    "PLAN_KIND",
    "PlanRequest",
    "PlanReview",
    "SyncDependencies",
    "default_database_paths",
    "run_execution",
    "run_plan",
    "sync_options",
]
