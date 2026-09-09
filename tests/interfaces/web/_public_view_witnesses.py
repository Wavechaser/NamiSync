"""Manual exhaustive witnesses for the approved desktop public-view codec."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

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
    ResultClassificationView,
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
from namisync.interfaces.task_port import (
    TaskCloseView,
    TaskDrainView,
    TaskEventUpdateView,
    TaskRecordUpdateView,
    TaskSessionReleaseView,
    TaskStartView,
)
from namisync.workflows import PLAN_KIND
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
    RecordingIssueView,
    ReviewFactLimitView,
)


@dataclass(frozen=True, slots=True)
class PublicViewWitness:
    label: str
    value: object
    expected: object


@dataclass(frozen=True, slots=True)
class UnapprovedPlanSessionLookalike:
    request_id: str
    session_id: str


HOSTILE_TEXT = "波🌊 e\u0301 </script>&"
REQUEST_ID = "1" * 32
SESSION_ID = "2" * 32
RUN_ID = "3" * 32
TASK_ID = "task-" + "4" * 32
DRAIN_ID = "5" * 32

PRESERVATION = PreservationSettingsView(True, False, True)
PRESERVATION_JSON = {
    "preserve_ads": True,
    "preserve_created": False,
    "preserve_acl": True,
}
SEMANTIC_SETTINGS = SemanticSettingsView(
    ("*.tmp", f"*{HOSTILE_TEXT}*"),
    "trash",
    True,
    PRESERVATION,
    False,
)
SEMANTIC_SETTINGS_JSON = {
    "filters": ["*.tmp", f"*{HOSTILE_TEXT}*"],
    "deletion_policy": "trash",
    "trash_on_update": True,
    "preservation": PRESERVATION_JSON,
    "propagate_source_casing": False,
}
REFUSAL = RefusalView("unsafe-path", None, HOSTILE_TEXT)
REFUSAL_JSON = {
    "code": "unsafe-path",
    "path": None,
    "detail": HOSTILE_TEXT,
}
PLAN_OPERATION = PlanOperationView(
    "6" * 32,
    "copy",
    f"source/{HOSTILE_TEXT}.txt",
    f"target/{HOSTILE_TEXT}.txt",
    None,
    "content-differs",
    None,
    "selected",
    None,
    "17",
)
PLAN_OPERATION_JSON = {
    "operation_id": "6" * 32,
    "kind": "copy",
    "source_path": f"source/{HOSTILE_TEXT}.txt",
    "target_path": f"target/{HOSTILE_TEXT}.txt",
    "prior_target_path": None,
    "reason": "content-differs",
    "blocked_reason": None,
    "selection_outcome": "selected",
    "selection_reason": None,
    "content_bytes": "17",
}
SELECTION_OPERATION = SelectionOperationView(
    "operation-1",
    True,
    "selected",
    None,
)
SELECTION_OPERATION_JSON = {
    "operation_id": "operation-1",
    "selected": True,
    "outcome": "selected",
    "reason": None,
}
SELECTION_PREVIEW = SelectionPreviewView(
    REQUEST_ID,
    7,
    "reviewing",
    "selection-digest",
    ("operation-1",),
    (),
    True,
    1,
    (SELECTION_OPERATION,),
)
SELECTION_PREVIEW_JSON = {
    "request_id": REQUEST_ID,
    "revision": 7,
    "state": "reviewing",
    "selection_digest": "selection-digest",
    "selected_operation_ids": ["operation-1"],
    "user_deselected": [],
    "requires_destructive_confirmation": True,
    "irreversible_update_count": 1,
    "operations": [SELECTION_OPERATION_JSON],
}
OPERATION_ITEM = OperationItemView(
    "operation",
    "execute",
    "7" * 32,
    "copy",
    f"folder/{HOSTILE_TEXT}.txt",
    "succeeded",
    None,
    MappingProxyType(
        {
            "message": HOSTILE_TEXT,
            "continued": True,
        }
    ),
    "ok",
    None,
    None,
    0,
)
OPERATION_ITEM_JSON = {
    "item_type": "operation",
    "phase": "execute",
    "item_id": "7" * 32,
    "kind": "copy",
    "path": f"folder/{HOSTILE_TEXT}.txt",
    "result": "succeeded",
    "reason": None,
    "detail": {
        "message": HOSTILE_TEXT,
        "continued": True,
    },
    "recording": "ok",
    "recording_reason": None,
    "recording_detail": None,
    "detail_omitted_count": 0,
}
INTEGRITY_OUTCOME = IntegrityOutcomeView(
    "integrity",
    "verify",
    "item-2",
    "row-2",
    "location-2",
    "file",
    f"verify/{HOSTILE_TEXT}.bin",
    "verified",
    None,
    HOSTILE_TEXT,
    "windows-unbuffered",
    "ok",
    "applied",
    0,
)
INTEGRITY_OUTCOME_JSON = {
    "item_type": "integrity",
    "phase": "verify",
    "item_id": "item-2",
    "row_id": "row-2",
    "location_id": "location-2",
    "kind": "file",
    "path": f"verify/{HOSTILE_TEXT}.bin",
    "result": "verified",
    "reason": None,
    "detail": HOSTILE_TEXT,
    "read_strategy": "windows-unbuffered",
    "recording": "ok",
    "record_disposition": "applied",
    "detail_omitted_count": 0,
}
PHASE_RESULT = PhaseResultView(
    "execute",
    "completed",
    2,
    2,
    "17",
    "17",
    None,
)
PHASE_RESULT_JSON = {
    "phase": "execute",
    "status": "completed",
    "items_done": 2,
    "items_total": 2,
    "bytes_done": "17",
    "bytes_total": "17",
    "error": None,
}
RECORDING_ISSUE = RecordingIssueView("final-flush-failed", HOSTILE_TEXT)
RECORDING_ISSUE_JSON = {
    "reason": "final-flush-failed",
    "detail": HOSTILE_TEXT,
}
REVIEW_FACT_LIMIT = ReviewFactLimitView(
    "review_fact_limit_exceeded",
    "plan",
    "domain",
    "rows",
    120_000,
    None,
)
REVIEW_FACT_LIMIT_JSON = {
    "reason": "review_fact_limit_exceeded",
    "tree_kind": "plan",
    "population": "domain",
    "axis": "rows",
    "row_limit": 120_000,
    "byte_limit": None,
}
OPERATION_RESULT = OperationResultView(
    headline="success",
    filesystem="completed",
    integrity="verified",
    recording="ok",
    audit="ok",
    disposition="ran",
    canceled=False,
    phases=(
        PHASE_RESULT,
        PhaseResultView("verify", "completed", 1, None, "17", None, None),
    ),
    bytes_done="17",
    bytes_total="17",
    error=None,
    recording_degraded_items=0,
    recording_issues=(),
    omitted_detail_count=0,
    presentation_omitted_detail_count=0,
    review_refusal=None,
)
OPERATION_RESULT_JSON = {
    "headline": "success",
    "filesystem": "completed",
    "integrity": "verified",
    "recording": "ok",
    "audit": "ok",
    "disposition": "ran",
    "canceled": False,
    "phases": [
        PHASE_RESULT_JSON,
        {
            "phase": "verify",
            "status": "completed",
            "items_done": 1,
            "items_total": None,
            "bytes_done": "17",
            "bytes_total": None,
            "error": None,
        },
    ],
    "bytes_done": "17",
    "bytes_total": "17",
    "error": None,
    "recording_degraded_items": 0,
    "recording_issues": [],
    "omitted_detail_count": 0,
    "presentation_omitted_detail_count": 0,
    "review_refusal": None,
}
SESSION_EVENT = SessionEventView(
    SESSION_ID,
    9,
    "2026-08-13T10:15:00+00:00",
    5,
    "Progress",
    MappingProxyType(
        {
            "phase": "verify",
            "items_done": 1,
            "items_total": 2,
            "bytes_done": "3",
            "bytes_total": "4",
            "current_path": HOSTILE_TEXT,
            "item_id": "8" * 32,
            "item_type": "integrity",
            "item_attempt_id": "a" * 32,
            "item_bytes_done": "3",
            "item_bytes_total": "4",
        }
    ),
)
SESSION_EVENT_JSON = {
    "session_id": SESSION_ID,
    "sequence": 9,
    "at": "2026-08-13T10:15:00+00:00",
    "schema_version": 5,
    "body_type": "Progress",
    "body": {
        "phase": "verify",
        "items_done": 1,
        "items_total": 2,
        "bytes_done": "3",
        "bytes_total": "4",
        "current_path": HOSTILE_TEXT,
        "item_id": "8" * 32,
        "item_type": "integrity",
        "item_attempt_id": "a" * 32,
        "item_bytes_done": "3",
        "item_bytes_total": "4",
    },
}
HISTORY_RECORDED_EVENT = HistoryEventView(
    SESSION_ID,
    9,
    "2026-08-13T10:15:00+00:00",
    5,
    "ItemOutcome",
    "recorded",
    MappingProxyType(OPERATION_ITEM_JSON),
    "a" * 64,
    "b" * 64,
    None,
    None,
)
HISTORY_RECORDED_EVENT_JSON = {
    "session_id": SESSION_ID,
    "sequence": 9,
    "at": "2026-08-13T10:15:00+00:00",
    "schema_version": 5,
    "body_type": "ItemOutcome",
    "disposition": "recorded",
    "body": OPERATION_ITEM_JSON,
    "payload_hash": "a" * 64,
    "receipt_hash": "b" * 64,
    "duplicate_of_seq": None,
    "rejection_reason": None,
}
HISTORY_REJECTED_EVENT = HistoryEventView(
    SESSION_ID,
    10,
    "2026-08-13T10:16:00+00:00",
    5,
    "IntegrityOutcome",
    "rejected",
    None,
    "c" * 64,
    "d" * 64,
    None,
    "event-too-large",
)
HISTORY_REJECTED_EVENT_JSON = {
    "session_id": SESSION_ID,
    "sequence": 10,
    "at": "2026-08-13T10:16:00+00:00",
    "schema_version": 5,
    "body_type": "IntegrityOutcome",
    "disposition": "rejected",
    "body": None,
    "payload_hash": "c" * 64,
    "receipt_hash": "d" * 64,
    "duplicate_of_seq": None,
    "rejection_reason": "event-too-large",
}
NONTERMINAL_RECORD = SessionRecordView(
    SESSION_ID,
    PLAN_KIND,
    "running",
    False,
    "2026-08-13T10:00:00+00:00",
    "2026-08-13T10:00:01+00:00",
    None,
    None,
)
NONTERMINAL_RECORD_JSON = {
    "session_id": SESSION_ID,
    "kind": "sync-plan",
    "state": "running",
    "supports_pause": False,
    "created_at": "2026-08-13T10:00:00+00:00",
    "started_at": "2026-08-13T10:00:01+00:00",
    "ended_at": None,
    "result": None,
}
TERMINAL_RECORD = SessionRecordView(
    SESSION_ID,
    PLAN_KIND,
    "completed",
    False,
    "2026-08-13T10:00:00+00:00",
    "2026-08-13T10:00:01+00:00",
    "2026-08-13T10:15:00+00:00",
    OPERATION_RESULT,
)
TERMINAL_RECORD_JSON = {
    "session_id": SESSION_ID,
    "kind": "sync-plan",
    "state": "completed",
    "supports_pause": False,
    "created_at": "2026-08-13T10:00:00+00:00",
    "started_at": "2026-08-13T10:00:01+00:00",
    "ended_at": "2026-08-13T10:15:00+00:00",
    "result": OPERATION_RESULT_JSON,
}
TASK_EVENT_UPDATE = TaskEventUpdateView("event", SESSION_EVENT)
TASK_EVENT_UPDATE_JSON = {
    "update_type": "event",
    "event": SESSION_EVENT_JSON,
}
TASK_RECORD_UPDATE = TaskRecordUpdateView("record", TERMINAL_RECORD)
TASK_RECORD_UPDATE_JSON = {
    "update_type": "record",
    "record": TERMINAL_RECORD_JSON,
}


PUBLIC_VIEW_WITNESSES: dict[
    type[object],
    tuple[PublicViewWitness, ...],
] = {
    PlanSession: (
        PublicViewWitness(
            "plan-session",
            PlanSession(REQUEST_ID, SESSION_ID),
            {"request_id": REQUEST_ID, "session_id": SESSION_ID},
        ),
    ),
    ExecutionSession: (
        PublicViewWitness(
            "execution-session",
            ExecutionSession(RUN_ID, SESSION_ID),
            {"run_id": RUN_ID, "session_id": SESSION_ID},
        ),
    ),
    LocationSession: (
        PublicViewWitness(
            "location-session",
            LocationSession(REQUEST_ID, SESSION_ID),
            {"request_id": REQUEST_ID, "session_id": SESSION_ID},
        ),
    ),
    LocationResolutionView: (
        PublicViewWitness(
            "location-resolution",
            LocationResolutionView(
                "resolved",
                f"E:/roots/{HOSTILE_TEXT}",
                7,
                "E:/",
                ("E:/", "F:/"),
                None,
            ),
            {
                "state": "resolved",
                "root_path": f"E:/roots/{HOSTILE_TEXT}",
                "location_id": 7,
                "selected_mount": "E:/",
                "candidates": ["E:/", "F:/"],
                "detail": None,
            },
        ),
    ),
    DatabaseContractView: (
        PublicViewWitness(
            "database-contract",
            DatabaseContractView("refused", "history-contract", HOSTILE_TEXT),
            {
                "state": "refused",
                "reason": "history-contract",
                "reset_direction": HOSTILE_TEXT,
            },
        ),
    ),
    InventoryDetailsView: (
        PublicViewWitness(
            "inventory-details",
            InventoryDetailsView(
                REQUEST_ID,
                "complete",
                None,
                11,
                "E:/",
                ("E:/",),
                HOSTILE_TEXT,
                (f"folder/{HOSTILE_TEXT}",),
                12,
                2,
                True,
                (ScanWarningView("unsupported", None, HOSTILE_TEXT),),
            ),
            {
                "request_id": REQUEST_ID,
                "state": "complete",
                "root_path": None,
                "location_id": 11,
                "selected_mount": "E:/",
                "candidates": ["E:/"],
                "detail": HOSTILE_TEXT,
                "selected_paths": [f"folder/{HOSTILE_TEXT}"],
                "observed_count": 12,
                "missing_count": 2,
                "complete": True,
                "warnings": [
                    {
                        "code": "unsupported",
                        "path": None,
                        "detail": HOSTILE_TEXT,
                    }
                ],
            },
        ),
    ),
    ScanWarningView: (
        PublicViewWitness(
            "scan-warning",
            ScanWarningView("read-error", f"folder/{HOSTILE_TEXT}", HOSTILE_TEXT),
            {
                "code": "read-error",
                "path": f"folder/{HOSTILE_TEXT}",
                "detail": HOSTILE_TEXT,
            },
        ),
    ),
    SelectionOperationView: (
        PublicViewWitness(
            "selection-operation",
            SELECTION_OPERATION,
            SELECTION_OPERATION_JSON,
        ),
    ),
    SelectionPreviewView: (
        PublicViewWitness(
            "selection-preview",
            SELECTION_PREVIEW,
            SELECTION_PREVIEW_JSON,
        ),
    ),
    SelectionMutationView: (
        PublicViewWitness(
            "selection-mutation",
            SelectionMutationView("applied", 7, "reviewing", SELECTION_PREVIEW),
            {
                "disposition": "applied",
                "revision": 7,
                "state": "reviewing",
                "preview": SELECTION_PREVIEW_JSON,
            },
        ),
    ),
    ExecutionAdmissionView: (
        PublicViewWitness(
            "execution-admission-present",
            ExecutionAdmissionView(
                "accepted",
                8,
                "running",
                ExecutionSession(RUN_ID, SESSION_ID),
            ),
            {
                "disposition": "accepted",
                "revision": 8,
                "state": "running",
                "session": {"run_id": RUN_ID, "session_id": SESSION_ID},
            },
        ),
        PublicViewWitness(
            "execution-admission-absent",
            ExecutionAdmissionView("conflict", 9, "reviewing", None),
            {
                "disposition": "conflict",
                "revision": 9,
                "state": "reviewing",
                "session": None,
            },
        ),
    ),
    InventoryDispositionView: (
        PublicViewWitness(
            "inventory-disposition",
            InventoryDispositionView("row-1", "acknowledged"),
            {"row_id": "row-1", "disposition": "acknowledged"},
        ),
    ),
    ResultClassificationView: (
        PublicViewWitness(
            "result-classification",
            ResultClassificationView(
                "success",
                "success",
                "verified",
                "ok",
                "ok",
                "ran",
                False,
            ),
            {
                "headline": "success",
                "filesystem": "success",
                "integrity": "verified",
                "recording": "ok",
                "audit": "ok",
                "disposition": "ran",
                "canceled": False,
            },
        ),
    ),
    ControlView: (
        PublicViewWitness(
            "control",
            ControlView(
                "accepted",
                SESSION_ID,
                None,
                "canceling",
                HOSTILE_TEXT,
                True,
            ),
            {
                "code": "accepted",
                "session_id": SESSION_ID,
                "before": None,
                "after": "canceling",
                "detail": HOSTILE_TEXT,
                "accepted": True,
            },
        ),
    ),
    ShutdownView: (
        PublicViewWitness(
            "shutdown",
            ShutdownView(False, ("session", "history"), False),
            {
                "complete": False,
                "unfinished": ["session", "history"],
                "custody_released": False,
            },
        ),
    ),
    InventoryRowView: (
        PublicViewWitness(
            "inventory-row",
            InventoryRowView(
                "row-1",
                "location-1",
                f"folder/{HOSTILE_TEXT}",
                "folder/key",
                "file",
                "present",
                17,
                None,
                True,
                "2026-08-13T10:00:00Z",
                None,
                None,
                "2026-08-13T10:05:00Z",
                None,
                None,
                "verified",
                "2026-08-13T10:06:00Z",
                HOSTILE_TEXT,
            ),
            {
                "row_id": "row-1",
                "location_id": "location-1",
                "path": f"folder/{HOSTILE_TEXT}",
                "path_key": "folder/key",
                "entry_kind": "file",
                "presence": "present",
                "size": 17,
                "mtime_ns": None,
                "has_baseline": True,
                "last_observed_at": "2026-08-13T10:00:00Z",
                "last_verified_at": None,
                "missing_since": None,
                "acknowledged_at": "2026-08-13T10:05:00Z",
                "reappeared_at": None,
                "unsupported_reason": None,
                "verification_state": "verified",
                "verification_invalidated_at": "2026-08-13T10:06:00Z",
                "verification_invalidated_reason": HOSTILE_TEXT,
            },
        ),
    ),
    PreservationSettingsView: (
        PublicViewWitness("preservation-settings", PRESERVATION, PRESERVATION_JSON),
    ),
    SemanticSettingsView: (
        PublicViewWitness(
            "semantic-settings",
            SEMANTIC_SETTINGS,
            SEMANTIC_SETTINGS_JSON,
        ),
    ),
    SemanticSettingsPatchView: (
        PublicViewWitness(
            "semantic-settings-patch-present",
            SemanticSettingsPatchView(
                ("*.bak",),
                "additive",
                False,
                PRESERVATION,
                True,
            ),
            {
                "filters": ["*.bak"],
                "deletion_policy": "additive",
                "trash_on_update": False,
                "preservation": PRESERVATION_JSON,
                "propagate_source_casing": True,
            },
        ),
        PublicViewWitness(
            "semantic-settings-patch-absent",
            SemanticSettingsPatchView(),
            {
                "filters": None,
                "deletion_policy": None,
                "trash_on_update": None,
                "preservation": None,
                "propagate_source_casing": None,
            },
        ),
    ),
    SessionEventView: (
        PublicViewWitness("session-event", SESSION_EVENT, SESSION_EVENT_JSON),
    ),
    SessionRecordView: (
        PublicViewWitness(
            "session-record-nonterminal",
            NONTERMINAL_RECORD,
            NONTERMINAL_RECORD_JSON,
        ),
        PublicViewWitness(
            "session-record-terminal",
            TERMINAL_RECORD,
            TERMINAL_RECORD_JSON,
        ),
    ),
    RefusalView: (
        PublicViewWitness("refusal", REFUSAL, REFUSAL_JSON),
    ),
    PlanOperationView: (
        PublicViewWitness(
            "plan-operation",
            PLAN_OPERATION,
            PLAN_OPERATION_JSON,
        ),
    ),
    PlanReview: (
        PublicViewWitness(
            "plan-review",
            PlanReview(
                REQUEST_ID,
                f"E:/source/{HOSTILE_TEXT}",
                "F:/target",
                "volume-source",
                "volume-target",
                "trash",
                True,
                SEMANTIC_SETTINGS,
                "fingerprint",
                "selection-digest",
                17,
                None,
                3,
                (HOSTILE_TEXT,),
                (REFUSAL,),
                (PLAN_OPERATION,),
            ),
            {
                "request_id": REQUEST_ID,
                "source_path": f"E:/source/{HOSTILE_TEXT}",
                "target_path": "F:/target",
                "source_volume": "volume-source",
                "target_volume": "volume-target",
                "deletion_policy": "trash",
                "trash_on_update": True,
                "semantic_settings": SEMANTIC_SETTINGS_JSON,
                "fingerprint": "fingerprint",
                "selection_digest_hex": "selection-digest",
                "required_bytes": 17,
                "free_bytes": None,
                "reclaimable_temp_bytes": 3,
                "warnings": [HOSTILE_TEXT],
                "refusals": [REFUSAL_JSON],
                "operations": [PLAN_OPERATION_JSON],
            },
        ),
    ),
    ExecutionDetails: (
        PublicViewWitness(
            "execution-details",
            ExecutionDetails(RUN_ID, (REFUSAL,), HOSTILE_TEXT),
            {
                "run_id": RUN_ID,
                "refusals": [REFUSAL_JSON],
                "commitment_error": HOSTILE_TEXT,
            },
        ),
    ),
    HistoryRunSummaryView: (
        PublicViewWitness(
            "history-run-summary",
            HistoryRunSummaryView(
                run_token="run-token",
                session_id=SESSION_ID,
                activity_kind="sync",
                subject_kind="plan",
                subject_id=REQUEST_ID,
                source_context=HOSTILE_TEXT,
                target_context=None,
                created_at=datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc),
                started_at=datetime(
                    2026,
                    8,
                    13,
                    15,
                    31,
                    tzinfo=timezone(timedelta(hours=5, minutes=30)),
                ),
                ended_at=None,
                completion_status="completed",
                current_state="completed",
                current_phase="execute",
                last_committed_seq=12,
                item_count=2,
                duplicate_item_count=1,
                rejected_event_count=0,
                last_committed_at=datetime(
                    2026, 8, 13, 10, 15, tzinfo=timezone.utc
                ),
                filesystem_status="completed",
                recording_status="ok",
                audit_status="ok",
                disposition="ran",
                canceled=False,
                integrity_status="verified",
                headline="success",
                bytes_done="17",
                bytes_total=None,
                recording_degraded_items=0,
                recording_issues=(),
                omitted_detail_count=0,
                review_refusal=None,
                succeeded_count=1,
                skipped_count=0,
                failed_count=0,
                canceled_count=0,
                deferred_count=0,
                blocked_count=0,
                phases=(PHASE_RESULT,),
                error=None,
            ),
            {
                "run_token": "run-token",
                "session_id": SESSION_ID,
                "activity_kind": "sync",
                "subject_kind": "plan",
                "subject_id": REQUEST_ID,
                "source_context": HOSTILE_TEXT,
                "target_context": None,
                "created_at": "2026-08-13T10:00:00+00:00",
                "started_at": "2026-08-13T15:31:00+05:30",
                "ended_at": None,
                "completion_status": "completed",
                "current_state": "completed",
                "current_phase": "execute",
                "last_committed_seq": 12,
                "item_count": 2,
                "duplicate_item_count": 1,
                "rejected_event_count": 0,
                "last_committed_at": "2026-08-13T10:15:00+00:00",
                "filesystem_status": "completed",
                "recording_status": "ok",
                "audit_status": "ok",
                "disposition": "ran",
                "canceled": False,
                "integrity_status": "verified",
                "headline": "success",
                "bytes_done": "17",
                "bytes_total": None,
                "recording_degraded_items": 0,
                "recording_issues": [],
                "omitted_detail_count": 0,
                "review_refusal": None,
                "succeeded_count": 1,
                "skipped_count": 0,
                "failed_count": 0,
                "canceled_count": 0,
                "deferred_count": 0,
                "blocked_count": 0,
                "phases": [PHASE_RESULT_JSON],
                "error": None,
            },
        ),
    ),
    HistoryItemView: (
        PublicViewWitness(
            "history-item",
            HistoryItemView(1, 9, OPERATION_ITEM),
            {
                "item_order": 1,
                "event_seq": 9,
                "item": OPERATION_ITEM_JSON,
            },
        ),
    ),
    HistoryItemPageView: (
        PublicViewWitness(
            "history-item-page",
            HistoryItemPageView(
                "run-token",
                1,
                2,
                False,
                (HistoryItemView(1, 9, INTEGRITY_OUTCOME),),
            ),
            {
                "run_token": "run-token",
                "through_order": 1,
                "next_after_order": 2,
                "has_more": False,
                "items": [
                    {
                        "item_order": 1,
                        "event_seq": 9,
                        "item": INTEGRITY_OUTCOME_JSON,
                    }
                ],
            },
        ),
    ),
    HistoryEventView: (
        PublicViewWitness(
            "history-event-present",
            HISTORY_RECORDED_EVENT,
            HISTORY_RECORDED_EVENT_JSON,
        ),
        PublicViewWitness(
            "history-event-absent",
            HISTORY_REJECTED_EVENT,
            HISTORY_REJECTED_EVENT_JSON,
        ),
    ),
    HistoryEventPageView: (
        PublicViewWitness(
            "history-event-page",
            HistoryEventPageView(
                "run-token",
                10,
                10,
                False,
                (HISTORY_RECORDED_EVENT, HISTORY_REJECTED_EVENT),
            ),
            {
                "run_token": "run-token",
                "through_seq": 10,
                "next_after_seq": 10,
                "has_more": False,
                "events": [
                    HISTORY_RECORDED_EVENT_JSON,
                    HISTORY_REJECTED_EVENT_JSON,
                ],
            },
        ),
    ),
    OperationItemView: (
        PublicViewWitness("operation-item", OPERATION_ITEM, OPERATION_ITEM_JSON),
    ),
    IntegrityOutcomeView: (
        PublicViewWitness(
            "integrity-outcome",
            INTEGRITY_OUTCOME,
            INTEGRITY_OUTCOME_JSON,
        ),
    ),
    PhaseResultView: (
        PublicViewWitness("phase-result", PHASE_RESULT, PHASE_RESULT_JSON),
    ),
    RecordingIssueView: (
        PublicViewWitness(
            "recording-issue",
            RECORDING_ISSUE,
            RECORDING_ISSUE_JSON,
        ),
    ),
    ReviewFactLimitView: (
        PublicViewWitness(
            "review-fact-limit",
            REVIEW_FACT_LIMIT,
            REVIEW_FACT_LIMIT_JSON,
        ),
    ),
    OperationResultView: (
        PublicViewWitness(
            "operation-result",
            OPERATION_RESULT,
            OPERATION_RESULT_JSON,
        ),
    ),
    TaskStartView: (
        PublicViewWitness(
            "task-start",
            TaskStartView(TASK_ID, REQUEST_ID, SESSION_ID),
            {
                "task_id": TASK_ID,
                "request_id": REQUEST_ID,
                "session_id": SESSION_ID,
            },
        ),
    ),
    TaskCloseView: (
        PublicViewWitness(
            "task-close",
            TaskCloseView(TASK_ID, SESSION_ID),
            {"task_id": TASK_ID, "session_id": SESSION_ID},
        ),
    ),
    TaskSessionReleaseView: (
        PublicViewWitness(
            "task-session-release",
            TaskSessionReleaseView(TASK_ID, SESSION_ID),
            {"task_id": TASK_ID, "session_id": SESSION_ID},
        ),
    ),
    TaskEventUpdateView: (
        PublicViewWitness(
            "task-event-update",
            TASK_EVENT_UPDATE,
            TASK_EVENT_UPDATE_JSON,
        ),
    ),
    TaskRecordUpdateView: (
        PublicViewWitness(
            "task-record-update",
            TASK_RECORD_UPDATE,
            TASK_RECORD_UPDATE_JSON,
        ),
    ),
    TaskDrainView: (
        PublicViewWitness(
            "task-drain",
            TaskDrainView(
                TASK_ID,
                SESSION_ID,
                DRAIN_ID,
                (TASK_EVENT_UPDATE, TASK_RECORD_UPDATE),
            ),
            {
                "task_id": TASK_ID,
                "session_id": SESSION_ID,
                "drain_id": DRAIN_ID,
                "updates": [TASK_EVENT_UPDATE_JSON, TASK_RECORD_UPDATE_JSON],
            },
        ),
    ),
}


_RECURSIVE_RETURN: list[object] = []
_RECURSIVE_RETURN.append(_RECURSIVE_RETURN)

INVALID_RETURN_WITNESSES: tuple[tuple[str, object], ...] = (
    ("path", Path(r"C:\private\must-not-cross.txt")),
    ("bytes", b"private bytes"),
    ("non-string-key", {1: "value"}),
    ("positive-infinity", float("inf")),
    ("negative-infinity", float("-inf")),
    ("nan", float("nan")),
    ("lone-surrogate", "\ud800"),
    ("recursion", _RECURSIVE_RETURN),
    (
        "lookalike-dataclass",
        UnapprovedPlanSessionLookalike(REQUEST_ID, SESSION_ID),
    ),
)


def iter_public_view_witnesses() -> tuple[PublicViewWitness, ...]:
    """Flatten the literal keyed table without deriving expected values."""

    return tuple(
        witness
        for witnesses in PUBLIC_VIEW_WITNESSES.values()
        for witness in witnesses
    )
