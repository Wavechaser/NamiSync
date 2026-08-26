"""Fixed DTO fixtures; no test-module imports, I/O, clocks, or random values."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from namisync.core.evidence import (
    Attestation, ContentEvidence, Outcome, Provenance, RecordingStatus,
)
from namisync.core.execution import (
    Commitment, ExecutionSet, PublishedCopyEvidence, RecordedCopyIdentity,
    validated_run_id,
)
from namisync.core.integrity import (
    IntegrityMode, IntegrityRecordCommand, InventoryState,
    VerificationInvalidation, VerificationInvalidationCommand,
    VerificationInvalidationReason,
)
from namisync.core.models import (
    CapabilityProfile, DirRecord, EntryKind, FileIdentity, FileRecord,
    MetadataSnapshot, Root, ScanResult, ScanScope, ScanWarning, ScanWarningCode,
    UnsupportedReason, UnsupportedRecord, VolumeEvidence, VolumeId,
)
from namisync.core.planning import (
    Assignment, BlockedReason, DeletionPolicy, DestinationAssignment, FilterSet,
    IdentityDestinationPolicy, MappingSnapshot, OperationKind, OperationReason,
    Plan, PlanFingerprint, PreservationPolicy, Scope, SyncOptions,
    plan_fingerprint, policy_fingerprint, selection_digest,
)
from namisync.core.recording import (
    FinishRunCommand, InventoryCommand, InventoryVisibilityAction,
    InventoryVisibilityCommand, SyncRunCommand,
)
from namisync.core.session import SessionState
from namisync.modules.planner import plan
from namisync.workflows.models import ExecuteContinuation, ExecutionRequest


NOW = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)
RUN_TOKEN = "a" * 32
MAX_FILE_INDEX = (1 << 128) - 1
SOURCE_VOLUME = VolumeId("FFFFFFFF", "NTFS")
TARGET_VOLUME = VolumeId("00000001", "REFS")


class CustomDestinationPolicy:
    """Only name/version belong in the policy fingerprint."""

    name = "fixture-é"
    version = "2"
    ignored_state = object()

    def assign(self, records, meta, target):
        return IdentityDestinationPolicy(self.name, self.version).assign(
            records, meta, target,
        )


def custom_options() -> SyncOptions:
    return SyncOptions(
        deletion_policy=DeletionPolicy.ADDITIVE,
        preservation=PreservationPolicy(True, False, True),
        filters=FilterSet(("z/*", "é/*.tmp", "z/*")),
        destination_policy=CustomDestinationPolicy(),
        trash_on_update=False,
        propagate_source_casing=True,
    )


def scans(with_identity: bool) -> tuple[ScanResult, ScanResult]:
    source = ScanResult(
        root=Root(r"C:\r314-source", "source-root"),
        volume_id=SOURCE_VOLUME,
        volume_evidence=VolumeEvidence("source-é", "device-source", False),
        profile=CapabilityProfile("NTFS", 100, True, None, 32767, True, True),
        files=(
            FileRecord(
                "a.txt", "A.TXT", 7, 11,
                FileIdentity(SOURCE_VOLUME.serial, MAX_FILE_INDEX)
                if with_identity else None,
                1, MetadataSnapshot(1, 3),
            ),
            FileRecord(
                "b.txt", "B.TXT", 5, 13,
                FileIdentity(SOURCE_VOLUME.serial, 1 << 64)
                if with_identity else None,
                1, MetadataSnapshot(0, None),
            ),
        ),
        directories=(), unsupported=(), warnings=(),
        scope=ScanScope.full(), complete=True,
    )
    target = ScanResult(
        root=Root(r"D:\r314-target", "target-root"),
        volume_id=TARGET_VOLUME,
        volume_evidence=VolumeEvidence(None, None, False),
        profile=CapabilityProfile("REFS", 100, True, False, 32767, False, False),
        files=(), directories=(), unsupported=(), warnings=(),
        scope=ScanScope.full(), complete=True,
    )
    return source, target


def two_copy_plan(with_identity: bool) -> Plan:
    source, target = scans(with_identity)
    return plan(
        source, target, MappingSnapshot.empty(SOURCE_VOLUME, TARGET_VOLUME),
        SyncOptions(), Scope.everything(),
    )


def execution_request(with_identity: bool) -> ExecutionRequest:
    """A genuine safe selection with one recorded publish and one pending copy."""
    reviewed = two_copy_plan(with_identity)
    first, _second = reviewed.operations
    selection = frozenset(operation.op_id for operation in reviewed.operations)
    subject = replace(
        first.intended,
        file_identity=FileIdentity(TARGET_VOLUME.serial, MAX_FILE_INDEX - 2)
        if with_identity else None,
    )
    attestation = Attestation(
        ContentEvidence("xxh3_128", bytes(range(16)), 7, Provenance.COPY_ATTESTED, NOW),
        subject,
    )
    xset = ExecutionSet(
        plan=reviewed, selection=selection, run_id=validated_run_id(RUN_TOKEN),
        status={first.op_id: Outcome.SUCCEEDED},
        commitment=Commitment(reviewed.fingerprint, selection_digest(selection), NOW),
        published_evidence={
            first.op_id: PublishedCopyEvidence(
                attestation,
                RecordedCopyIdentity("1", "2", RUN_TOKEN, "A.TXT"),
            ),
        },
        bytes_done_high_water=7,
    )
    return ExecutionRequest(ExecuteContinuation(xset, False), NOW)


def hash_fixtures(
    with_identity: bool,
) -> tuple[dict[str, Plan], dict[str, object]]:
    """Cover owner hash shapes; all_fields is deliberately NOT a resume fixture."""
    source, _target = scans(with_identity)
    reviewed = two_copy_plan(with_identity)
    first, second = reviewed.operations
    source_record = replace(
        source.files[0], size=(1 << 53) + 7, mtime_ns=(1 << 53) + 11,
        metadata=MetadataSnapshot(8193, (1 << 53) + 3), nlink=2,
    )
    source_stat = source_record.stat
    target_stat = replace(
        source_stat,
        file_identity=FileIdentity(TARGET_VOLUME.serial, 0)
        if with_identity else None,
    )
    operation = replace(
        first, kind=OperationKind.MOVE_UPDATE, target_rel_path=r"folder\a.txt",
        source_expected=source_stat, target_expected=target_stat,
        intended=source_stat, prior_target_rel_path="old.txt",
        prior_target_expected=replace(target_stat, mtime_ns=(1 << 53) + 9),
        metadata=source_stat.metadata, content_bytes=source_stat.size,
        dependencies=(second.op_id,), reason=OperationReason.IDENTITY_RENAME_CHANGED,
    )
    options = custom_options()
    all_fields = replace(
        reviewed, source_complete=False,
        source_volume_evidence=VolumeEvidence("source-é", "device-source", True),
        operations=(second, replace(operation, blocked_reason=BlockedReason.DESTINATION_COLLISION)),
        assignment=Assignment(
            options.destination_policy.name, options.destination_policy.version,
            (
                DestinationAssignment("b.txt", "B.TXT", "b.txt", "B.TXT"),
                DestinationAssignment(
                    "a.txt", "A.TXT", r"folder\a.txt", r"FOLDER\A.TXT",
                    group_id="group-é", conflict="collision",
                ),
            ),
        ),
        preservation=options.preservation, filter_snapshot=options.filters,
        deletion_policy=options.deletion_policy, trash_on_update=False,
        policy_fingerprint=policy_fingerprint(options),
        required_bytes=source_stat.size, fingerprint=PlanFingerprint("0" * 64),
    )
    all_fields = replace(all_fields, fingerprint=plan_fingerprint(all_fields))
    inventory_scan = replace(
        source, files=(source_record, source.files[1]),
        directories=(
            DirRecord(
                "folder", "FOLDER", 17, MetadataSnapshot(16, None),
                FileIdentity(SOURCE_VOLUME.serial, MAX_FILE_INDEX - 1)
                if with_identity else None, 2,
            ),
        ),
        unsupported=(
            UnsupportedRecord("skip.bin", "SKIP.BIN", UnsupportedReason.REPARSE_POINT, EntryKind.FILE),
            UnsupportedRecord("unknown.bin", "UNKNOWN.BIN", UnsupportedReason.UNKNOWN_TYPE),
        ),
        warnings=(
            ScanWarning(ScanWarningCode.MULTI_LINK, "a.txt", "two links-é"),
            ScanWarning(ScanWarningCode.PATH_UNREPRESENTABLE, None, "bad-\udcff"),
        ),
        scope=ScanScope.scoped(selected_paths=("b.txt", "a.txt"), subtree_roots=("folder",)),
        complete=False,
    )
    copy_attestation = Attestation(
        ContentEvidence("xxh3_128", bytes(range(16)), target_stat.size, Provenance.COPY_ATTESTED, NOW),
        target_stat,
    )
    verified_attestation = replace(
        copy_attestation,
        content=replace(copy_attestation.content, provenance=Provenance.VERIFY_ATTESTED),
    )
    invalidation = VerificationInvalidation(NOW, VerificationInvalidationReason.METADATA_DRIFT)
    selection = frozenset(operation.op_id for operation in reviewed.operations)
    start = SyncRunCommand(
        RUN_TOKEN, 1, 1, 1, 2, reviewed, selection, selection_digest(selection), NOW,
    )
    # This is the exact begin_sync_run outer hash input, not an arbitrary DTO.
    values: dict[str, object] = {
        "start": {
            "run_token": start.run_token, "host_id": start.host_id,
            "mapping_id": start.mapping_id, "source_location_id": start.source_location_id,
            "target_location_id": start.target_location_id, "plan": start.plan,
            "selection": start.selection, "selection_digest": start.selection_digest,
            "started_at": start.started_at,
        },
        "finish": FinishRunCommand(RUN_TOKEN, SessionState.COMPLETED, RecordingStatus.OK, NOW),
        "inventory": InventoryCommand(1, 1, inventory_scan, RUN_TOKEN, NOW, True),
        "visibility": InventoryVisibilityCommand(
            "visibility-command", 1, "row-é", InventoryVisibilityAction.ACKNOWLEDGE, NOW,
        ),
        "integrity": IntegrityRecordCommand(
            IntegrityMode.VERIFY, "item-é", "1", "2", "A.TXT", RUN_TOKEN,
            InventoryState.PRESENT, target_stat, copy_attestation,
            verified_attestation, True, True, invalidation,
        ),
        "invalidation": VerificationInvalidationCommand(
            "item-é", "1", "2", "A.TXT", RUN_TOKEN, InventoryState.PRESENT,
            target_stat, copy_attestation, invalidation,
            VerificationInvalidationReason.HASH_MISMATCH, NOW,
        ),
    }
    # Five production evidence-map shapes share the operation receipt envelope.
    receipt_inputs = (
        ("attestation", operation, {"attestation": copy_attestation}, None),
        ("target", replace(operation, kind=OperationKind.MOVE), {"target": target_stat}, None),
        ("trash", replace(operation, kind=OperationKind.TRASH), {"trash": r"run\old.txt", "target": target_stat}, r"run\old.txt"),
        ("prior", replace(operation, kind=OperationKind.DELETE), {"prior": target_stat}, None),
        ("noop", replace(operation, kind=OperationKind.NOOP), {"source": source_stat, "target": target_stat}, None),
    )
    for name, receipt_operation, evidence, trash_relative_path in receipt_inputs:
        values[f"receipt_{name}"] = {
            "run_token": RUN_TOKEN, "operation": receipt_operation,
            "evidence": evidence, "trash_relative_path": trash_relative_path,
        }
    return {"two_copy": reviewed, "all_fields": all_fields}, values
