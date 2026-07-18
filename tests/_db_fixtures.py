from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from namisync.core.evidence import Attestation, ContentEvidence, Provenance
from namisync.core.models import (
    CapabilityProfile,
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
    Root,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.planning import (
    Assignment,
    DeletionPolicy,
    FilterSet,
    OpId,
    OperationKind,
    OperationReason,
    Plan,
    PlanFingerprint,
    PlanOperation,
    PreservationPolicy,
    deterministic_operation_id,
    selection_digest,
)
from namisync.core.recording import (
    HostCommand,
    LocationCommand,
    MappingCommand,
    SyncRunCommand,
    VolumeCommand,
)
from namisync.db.recorder import LedgerRecorder, SyncRunRecorder


UTC = timezone.utc
NOW = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)


@dataclass
class FakeClock:
    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


def file_stat(
    *,
    size: int = 7,
    mtime_ns: int = 11,
    identity_index: int = 1,
    volume_serial: str = "source-serial",
) -> FileStat:
    return FileStat(
        EntryKind.FILE,
        size,
        mtime_ns,
        FileIdentity(volume_serial, identity_index),
        1,
        MetadataSnapshot(0, 3),
    )


def attestation(
    stat: FileStat,
    *,
    digest_byte: int = 1,
    provenance: Provenance = Provenance.COPY_ATTESTED,
    observed_at: datetime = NOW,
) -> Attestation:
    return Attestation(
        ContentEvidence(
            "sha256",
            bytes([digest_byte]) * 32,
            stat.size,
            provenance,
            observed_at,
        ),
        stat,
    )


def operation(
    kind: OperationKind,
    *,
    source_path: str | None = "a.txt",
    target_path: str = "a.txt",
    source: FileStat | None = None,
    target: FileStat | None = None,
    intended: FileStat | None = None,
    prior_target_path: str | None = None,
    reason: OperationReason = OperationReason.SOURCE_ONLY,
) -> PlanOperation:
    op_id = deterministic_operation_id(
        kind, source_path, target_path, prior_target_path, reason
    )
    return PlanOperation(
        op_id=op_id,
        kind=kind,
        source_rel_path=source_path,
        target_rel_path=target_path,
        source_expected=source,
        target_expected=target,
        intended=intended,
        prior_target_rel_path=prior_target_path,
        prior_target_expected=target if prior_target_path else None,
        content_bytes=source.size if source is not None and kind in {
            OperationKind.COPY,
            OperationKind.UPDATE,
            OperationKind.MOVE_UPDATE,
        } else 0,
        reason=reason,
    )


def plan(operations: tuple[PlanOperation, ...]) -> Plan:
    source_volume = VolumeId("source-serial", "NTFS")
    target_volume = VolumeId("target-serial", "NTFS")
    profile = CapabilityProfile("NTFS", 100, True, False, 32_767, True, True)
    return Plan(
        source_root=Root(r"C:\source", "source"),
        target_root=Root(r"D:\target", "target"),
        source_volume_id=source_volume,
        target_volume_id=target_volume,
        source_volume_evidence=VolumeEvidence("Source"),
        target_volume_evidence=VolumeEvidence("Target"),
        source_profile=profile,
        target_profile=profile,
        source_complete=True,
        target_complete=True,
        operations=operations,
        assignment=Assignment("identity", "1", ()),
        preservation=PreservationPolicy(),
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=True,
        policy_fingerprint="p" * 64,
        worker_count=1,
        required_volumes=frozenset({source_volume, target_volume}),
        required_bytes=sum(item.content_bytes for item in operations),
        fingerprint=PlanFingerprint("f" * 64),
    )


@dataclass(frozen=True)
class RecorderSetup:
    recorder: LedgerRecorder
    run: SyncRunRecorder
    host_id: int
    source_location_id: int
    target_location_id: int
    mapping_id: int
    run_token: str


def setup_recorder(
    path: Path,
    sync_plan: Plan,
    *,
    clock: FakeClock | None = None,
    run_token: str = "a" * 32,
) -> RecorderSetup:
    recorder = LedgerRecorder(path, clock=clock or FakeClock())
    host_id = recorder.ensure_host(HostCommand("host-1", "Test Host", NOW))
    source_volume = recorder.observe_volume(
        VolumeCommand(sync_plan.source_volume_id, VolumeEvidence("Source", "C:"), NOW)
    )
    target_volume = recorder.observe_volume(
        VolumeCommand(sync_plan.target_volume_id, VolumeEvidence("Target", "D:"), NOW)
    )
    source_location = recorder.ensure_location(LocationCommand(source_volume, "source", NOW))
    target_location = recorder.ensure_location(LocationCommand(target_volume, "target", NOW))
    mapping_id = recorder.ensure_mapping(
        MappingCommand(source_location, target_location, NOW)
    )
    selection = frozenset(item.op_id for item in sync_plan.operations)
    command = SyncRunCommand(
        run_token,
        host_id,
        mapping_id,
        source_location,
        target_location,
        sync_plan,
        selection,
        selection_digest(selection),
        NOW,
    )
    run = recorder.begin_sync_run(command)
    return RecorderSetup(
        recorder,
        run,
        host_id,
        source_location,
        target_location,
        mapping_id,
        run_token,
    )
