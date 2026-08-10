"""Executor continuation state and injected collaborator protocols."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
import re
from typing import BinaryIO, NewType, Protocol, TypeAlias

from .evidence import Attestation, Outcome, Provenance, RecordingStatus
from .models import EntryKind, FileStat, VolumeId
from .pathing import normalize_relative_path
from .planning import OpId, OperationKind, Plan, PlanFingerprint, PlanOperation


RunId = NewType("RunId", str)

_FIXED_ID = re.compile(r"[0-9a-f]{32}\Z")


def validated_run_id(value: str) -> RunId:
    """Return a fixed-format run id suitable for owned artifact names."""

    if _FIXED_ID.fullmatch(value) is None:
        raise ValueError("run id must contain exactly 32 lowercase hex digits")
    return RunId(value)


@dataclass(frozen=True, slots=True)
class Commitment:
    """Human authorization bound to one plan and exact operation selection."""

    plan_fingerprint: PlanFingerprint
    selection_digest: bytes
    committed_at: datetime

    def __post_init__(self) -> None:
        if not self.plan_fingerprint:
            raise ValueError("commitment plan fingerprint is required")
        if len(self.selection_digest) != 32:
            raise ValueError("commitment selection digest must contain 32 bytes")
        if self.committed_at.tzinfo is None or self.committed_at.utcoffset() is None:
            raise ValueError("commitment timestamp must be timezone-aware")
        if self.committed_at.utcoffset() != timezone.utc.utcoffset(self.committed_at):
            raise ValueError("commitment timestamp must be UTC")


@dataclass(frozen=True, slots=True)
class RecordedCopyIdentity:
    """Durable ledger identity returned by one successful copy transaction."""

    row_id: str
    location_id: str
    scope_token: str
    rel_path_key: str

    def __post_init__(self) -> None:
        values = (
            self.row_id,
            self.location_id,
            self.scope_token,
            self.rel_path_key,
        )
        if not all(isinstance(value, str) for value in values):
            raise TypeError("recorded copy identity fields must be strings")
        if not all(values):
            raise ValueError("recorded copy identity fields must be non-empty strings")
        if normalize_relative_path(self.rel_path_key) != self.rel_path_key:
            raise ValueError("recorded copy relative path key must be canonical")


@dataclass(frozen=True, slots=True)
class PublishedCopyEvidence:
    """Post-publish evidence plus optional durable ledger identity."""

    attestation: Attestation
    recorded_identity: RecordedCopyIdentity | None

    def __post_init__(self) -> None:
        if not isinstance(self.attestation, Attestation):
            raise TypeError("published copy evidence requires an attestation")
        if self.attestation.content.provenance is not Provenance.COPY_ATTESTED:
            raise ValueError("published copy evidence must be copy-attested")
        if self.attestation.subject.kind is not EntryKind.FILE:
            raise ValueError("published copy evidence must attest a regular file")
        if self.recorded_identity is not None and not isinstance(
            self.recorded_identity, RecordedCopyIdentity
        ):
            raise TypeError("recorded copy identity has the wrong type")

    @property
    def copy_recorded(self) -> bool:
        """Whether the copy transaction returned a complete durable identity."""

        return self.recorded_identity is not None


@dataclass(slots=True)
class ExecutionSet:
    """A selected plan plus mutable continuation state for pause/resume."""

    plan: Plan
    selection: frozenset[OpId]
    run_id: RunId
    status: dict[OpId, Outcome] = field(default_factory=dict)
    commitment: Commitment | None = None
    published_evidence: dict[OpId, PublishedCopyEvidence] = field(
        default_factory=dict
    )
    recording: RecordingStatus = RecordingStatus.OK
    user_deselected: frozenset[OpId] = frozenset()

    def __post_init__(self) -> None:
        validated_run_id(str(self.run_id))
        operations = {
            operation.op_id: operation for operation in self.plan.operations
        }
        known = set(operations)
        unknown = self.selection - known
        if unknown:
            raise ValueError(f"selection contains unknown operation ids: {sorted(unknown)!r}")
        if not isinstance(self.user_deselected, frozenset):
            raise TypeError("user_deselected must be a frozenset")
        unknown_user_deselected = self.user_deselected - known
        if unknown_user_deselected:
            raise ValueError(
                "user deselection contains unknown operation ids: "
                f"{sorted(unknown_user_deselected)!r}"
            )
        selected_user_deselected = self.user_deselected & self.selection
        if selected_user_deselected:
            raise ValueError(
                "user-deselected operation ids cannot remain selected: "
                f"{sorted(selected_user_deselected)!r}"
            )
        invalid_status = self.status.keys() - self.selection
        if invalid_status:
            raise ValueError(
                f"status contains unselected operation ids: {sorted(invalid_status)!r}"
            )
        invalid_evidence = self.published_evidence.keys() - self.selection
        if invalid_evidence:
            raise ValueError(
                "published evidence contains unselected operation ids: "
                f"{sorted(invalid_evidence)!r}"
            )
        if not isinstance(self.recording, RecordingStatus):
            raise TypeError("execution recording status has the wrong type")
        byte_kinds = {
            OperationKind.COPY,
            OperationKind.UPDATE,
            OperationKind.MOVE_UPDATE,
        }
        recorded_location_id: str | None = None
        for op_id, evidence in self.published_evidence.items():
            if not isinstance(evidence, PublishedCopyEvidence):
                raise TypeError("published evidence values have the wrong type")
            operation = operations[op_id]
            if operation.kind not in byte_kinds:
                raise ValueError(
                    "published evidence belongs to a non-byte-producing operation"
                )
            if self.status.get(op_id) is not Outcome.SUCCEEDED:
                raise ValueError(
                    "published evidence requires a successful operation status"
                )
            if evidence.attestation.content.size != operation.content_bytes:
                raise ValueError(
                    "published evidence size does not match reviewed content bytes"
                )
            identity = evidence.recorded_identity
            if identity is None:
                if self.recording is RecordingStatus.OK:
                    raise ValueError(
                        "identityless published evidence requires degraded recording"
                    )
                continue
            if identity.scope_token != str(self.run_id):
                raise ValueError(
                    "recorded copy scope token does not match the execution run"
                )
            expected_path_key = normalize_relative_path(
                operation.target_rel_path
            )
            if identity.rel_path_key != expected_path_key:
                raise ValueError(
                    "recorded copy relative path key does not match its operation"
                )
            if recorded_location_id is None:
                recorded_location_id = identity.location_id
            elif identity.location_id != recorded_location_id:
                raise ValueError(
                    "recorded copy identities do not share one target location"
                )

    def remaining(self) -> tuple[PlanOperation, ...]:
        """Return selected operations without a final status, in plan order."""

        return tuple(
            operation
            for operation in self.plan.operations
            if operation.op_id in self.selection and operation.op_id not in self.status
        )


class ExecutionReason(StrEnum):
    """Typed executor reasons; detail text is presentation-only."""

    NOOP = "noop"
    ALREADY_EXISTS = "already-exists"
    BLOCKED = "blocked"
    DEPENDENCY_FAILED = "dependency-failed"
    SOURCE_DRIFT = "source-drift"
    TARGET_DRIFT = "target-drift"
    DESTINATION_OCCUPIED = "destination-occupied"
    WRONG_TYPE = "wrong-type"
    SOURCE_MISSING = "source-missing"
    TARGET_MISSING = "target-missing"
    TRASH_COLLISION = "trash-collision"
    UNSAFE_PATH = "unsafe-path"
    SHARING_VIOLATION = "sharing-violation"
    ACL_COPY_FAILED = "acl-copy-failed"
    CLEANUP_FAILED = "cleanup-failed"
    PUBLISHED_SIZE_MISMATCH = "published-size-mismatch"
    IO_ERROR = "io-error"
    POLICY_STOP = "policy-stop"
    CANCELED = "canceled"
    CANCELED_AFTER_PUBLISH = "canceled-after-publish"
    CANCELED_AFTER_MUTATION = "canceled-after-mutation"
    RECORDER_FAILED = "recorder-failed"


@dataclass(frozen=True, slots=True)
class Continue:
    """Continue with later independent operations."""


@dataclass(frozen=True, slots=True)
class Stop:
    """Stop admission of later operations after the current failure."""


@dataclass(frozen=True, slots=True)
class Retry:
    """Retry the guarded operation after a bounded delay."""

    after: float

    def __post_init__(self) -> None:
        if self.after < 0:
            raise ValueError("retry delay cannot be negative")


FailureDecision: TypeAlias = Continue | Stop | Retry


class FailurePolicy(Protocol):
    def on_item_failed(
        self, operation: PlanOperation, error: Exception, attempt: int
    ) -> FailureDecision: ...


@dataclass(frozen=True, slots=True)
class CopyDigest:
    digest: bytes
    size: int

    def __post_init__(self) -> None:
        if not isinstance(self.digest, bytes):
            raise TypeError("copy digest must be bytes")
        if len(self.digest) != 16:
            raise ValueError("copy digest must be XXH3-128")
        if self.size < 0:
            raise ValueError("copied size cannot be negative")


class CopyBackend(Protocol):
    """Writes bytes only; the executor retains every guard and publish step."""

    def copy(
        self,
        source: BinaryIO,
        target: BinaryIO,
        *,
        chunk_size: int,
        checkpoint: Callable[[], None],
        on_chunk: Callable[[int], None],
    ) -> CopyDigest: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class Recorder(Protocol):
    """Typed ledger commands consumed by the M0 executor."""

    def flush(self) -> None: ...

    def record_copied(
        self, op: OpId, attestation: Attestation
    ) -> RecordedCopyIdentity: ...

    def record_updated(
        self, op: OpId, attestation: Attestation
    ) -> RecordedCopyIdentity: ...

    def record_moved(self, op: OpId, target: FileStat) -> None: ...

    def record_recased(self, op: OpId, target: FileStat) -> None: ...

    def record_move_updated(
        self, op: OpId, attestation: Attestation
    ) -> RecordedCopyIdentity: ...

    def record_mkdir(self, op: OpId, target: FileStat) -> None: ...

    def record_trashed(
        self, op: OpId, trash_relative_path: str, target: FileStat
    ) -> None: ...

    def record_deleted(self, op: OpId, prior: FileStat) -> None: ...

    def record_noop(
        self, op: OpId, source: FileStat, target: FileStat
    ) -> None: ...


class ExecutorFileSystem(Protocol):
    """Operation-matched filesystem primitives retained by the state machine."""

    def resolve(self, root: Path, relative_path: str, *, must_exist: bool) -> Path: ...

    def revalidate_root(
        self,
        root: Path,
        *,
        trusted_anchor: Path | None = None,
        expected_volume: VolumeId | None = None,
    ) -> None: ...

    def stat(self, root: Path, relative_path: str) -> FileStat | None: ...

    def stat_path(self, path: Path) -> FileStat | None: ...

    def owned_temp(self, target: Path, run_id: RunId, op_id: OpId) -> Path: ...

    def remove_owned_temp(self, path: Path) -> None: ...

    def remove_orphaned_temps(
        self,
        target_root: Path,
        parent_paths: frozenset[str],
        current_run_id: RunId,
    ) -> None: ...

    def open_source(self, path: Path) -> BinaryIO: ...

    def create_temp(
        self, path: Path, *, allocation_size: int | None
    ) -> BinaryIO: ...

    def flush_file(self, stream: BinaryIO) -> None: ...

    def flush_path(self, path: Path) -> None: ...

    def apply_metadata(
        self,
        path: Path,
        stat: FileStat,
        *,
        preserve_created: bool,
        apply_readonly: bool,
    ) -> None: ...

    def copy_security(self, source: Path, target: Path) -> None: ...

    def finalize_temp(
        self,
        path: Path,
        intended: FileStat,
        *,
        preserve_created: bool,
        acl_source: Path | None,
    ) -> FileStat: ...

    def ensure_published_metadata(
        self,
        path: Path,
        finalized_temp: FileStat,
        intended: FileStat,
        *,
        preserve_created: bool,
        apply_readonly: bool,
    ) -> FileStat: ...

    def publish_new(self, temp: Path, target: Path) -> None: ...

    def replace(self, temp: Path, target: Path) -> None: ...

    def hardlink(self, source: Path, target: Path) -> None: ...

    def copy_backup(
        self,
        source: Path,
        temp: Path,
        target: Path,
        source_expected: FileStat,
        checkpoint: Callable[[], None],
        validate_destination: Callable[[], None],
    ) -> None: ...

    def clear_readonly(self, path: Path) -> None: ...

    def rename_new(self, source: Path, target: Path) -> None: ...

    def mkdir_new(self, path: Path) -> None: ...

    def remove_file(self, path: Path) -> None: ...

    def remove_directory(self, path: Path) -> None: ...

    def trash_destination(
        self, target_root: Path, run_id: RunId, relative_path: str
    ) -> Path: ...

    def revalidate_trash_destination(
        self,
        target_root: Path,
        run_id: RunId,
        relative_path: str,
        destination: Path,
    ) -> None: ...

    def flush_directory(self, path: Path) -> bool: ...
