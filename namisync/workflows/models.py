"""Typed workflow requests and interface-facing read models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from namisync.core.execution import ExecutionSet
from namisync.core.models import ScanResult
from namisync.core.planning import Plan, SyncOptions
from namisync.core.preflight import Verdict
from namisync.workflows.views import ResultItemView


@dataclass(frozen=True, slots=True)
class PlanRequest:
    request_id: str
    source_path: str
    target_path: str
    options: SyncOptions = SyncOptions()


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    execution_set: ExecutionSet
    started_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowPreparation:
    payload: bytes
    resources: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class RefusalView:
    code: str
    path: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class PlanOperationView:
    operation_id: str
    kind: str
    source_path: str | None
    target_path: str
    prior_target_path: str | None
    reason: str
    blocked_reason: str | None
    selection_outcome: str | None
    selection_reason: str | None
    content_bytes: int


@dataclass(frozen=True, slots=True)
class PlanReview:
    request_id: str
    source_path: str
    target_path: str
    source_volume: str
    target_volume: str
    deletion_policy: str
    trash_on_update: bool
    fingerprint: str
    selection_digest_hex: str
    required_bytes: int
    free_bytes: int | None
    reclaimable_temp_bytes: int
    warnings: tuple[str, ...]
    refusals: tuple[RefusalView, ...]
    operations: tuple[PlanOperationView, ...]

    @property
    def can_commit(self) -> bool:
        return not self.refusals


@dataclass(frozen=True, slots=True)
class ExecutionDetails:
    run_id: str
    refusals: tuple[RefusalView, ...] = ()
    commitment_error: str | None = None


@dataclass(frozen=True, slots=True)
class HistoryRunView:
    run_token: str
    activity_kind: str
    subject_kind: str | None
    subject_id: str | None
    source_context: str | None
    target_context: str | None
    started_at: datetime
    ended_at: datetime
    filesystem_status: str
    recording_status: str
    audit_status: str
    disposition: str
    bytes_done: int
    bytes_total: int
    items: tuple[ResultItemView, ...]
    error: str | None


@dataclass(frozen=True, slots=True)
class PlanArtifact:
    request: PlanRequest
    source_scan: ScanResult
    target_scan: ScanResult
    plan: Plan
    verdict: Verdict
