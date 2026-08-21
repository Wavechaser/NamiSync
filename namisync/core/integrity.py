"""Verifier-specific contracts and continuation state.

This module is deliberately limited to integrity vocabulary.  Generic session,
event, evidence, filesystem-stat, and path contracts live in their respective
``core`` modules so the verifier remains a sibling-independent operation module.
"""

from __future__ import annotations

from collections import Counter
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from time import monotonic
from typing import Callable, ClassVar, Iterator, Mapping, Protocol, runtime_checkable

from .evidence import Attestation, HasherFactory, Provenance, RecordingStatus
from .models import FileStat
from .pathing import normalize_relative_path, validate_relative_path
from .root_authority import RootAuthority
from .session import ResultItem, RunContext


_JAVASCRIPT_MAX_SAFE_INTEGER = (1 << 53) - 1


class InventoryState(StrEnum):
    """Inventory state captured by a freshly constructed selection."""

    PRESENT = "present"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"


class VerificationInvalidationReason(StrEnum):
    """Why retained integrity evidence no longer describes current truth."""

    METADATA_DRIFT = "metadata-drift"
    HASH_MISMATCH = "hash-mismatch"


@dataclass(frozen=True, slots=True)
class VerificationInvalidation:
    at: datetime
    reason: VerificationInvalidationReason

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.utcoffset() is None:
            raise ValueError("verification invalidation time must be timezone-aware")
        if self.at.utcoffset().total_seconds() != 0:
            raise ValueError("verification invalidation time must be UTC")
        if not isinstance(self.reason, VerificationInvalidationReason):
            raise TypeError("verification invalidation reason has the wrong type")


class InventoryVerificationState(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    MODIFIED = "modified"
    MISMATCHED = "mismatched"


class IntegrityResult(StrEnum):
    """The integrity meaning of one selected inventory row."""

    VERIFIED = "verified"
    BASELINED = "baselined"
    MISMATCHED = "mismatched"
    MODIFIED = "modified"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"
    CANCELED = "canceled"
    ERROR = "error"


class IntegrityMode(StrEnum):
    BASELINE = "baseline"
    VERIFY = "verify"
    REBASELINE = "rebaseline"


class IntegrityReason(StrEnum):
    PATH_INVALID = "path-invalid"
    INVENTORY_MISSING = "inventory-missing"
    INVENTORY_UNSUPPORTED = "inventory-unsupported"
    NOT_FOUND = "not-found"
    UNSUPPORTED_READ = "unsupported-read"
    STAT_CHANGED = "stat-changed"
    READ_DRIFT = "read-drift"
    HASH_MISMATCH = "hash-mismatch"
    BASELINE_EXISTS = "baseline-exists"
    READ_ERROR = "read-error"
    RECORDING_STALE = "recording-stale"
    RECORDING_CONFLICT = "recording-conflict"
    RECORDING_ERROR = "recording-error"
    CANCELED = "canceled"


class ReadStrategy(StrEnum):
    """Cache-honest strategy actually used for an integrity read."""

    WINDOWS_UNBUFFERED = "windows-unbuffered"


class RecordDisposition(StrEnum):
    """Typed result of the recorder's conditional evidence primitive."""

    APPLIED = "applied"
    NOOP = "noop"
    STALE = "stale"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class PostCopyRecordIdentity:
    """Independent verifier-facing identity for one durable copy record."""

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
        if not all(isinstance(value, str) and value for value in values):
            raise ValueError(
                "post-copy record identity fields must be non-empty strings"
            )
        if self.rel_path_key != normalize_relative_path(self.rel_path_key):
            raise ValueError("post-copy record path must be canonical")


@dataclass(frozen=True, slots=True)
class PostCopyCandidate:
    """Transient published target classified without requiring a ledger row."""

    item_id: str
    root: Path
    display_path: str
    expected_stat: FileStat
    copy_attestation: Attestation
    recorded_identity: PostCopyRecordIdentity | None

    def __post_init__(self) -> None:
        if not self.item_id or not self.display_path:
            raise ValueError("post-copy candidate identity and path are required")
        validated_path = validate_relative_path(self.display_path)
        if self.copy_attestation.content.provenance is not Provenance.COPY_ATTESTED:
            raise ValueError("post-copy candidates require copy-attested evidence")
        if self.copy_attestation.subject != self.expected_stat:
            raise ValueError(
                "post-copy attestation must match the expected published stat"
            )
        if self.expected_stat.kind.value != "file":
            raise ValueError("post-copy candidates must name regular files")
        if self.recorded_identity is not None:
            if not isinstance(self.recorded_identity, PostCopyRecordIdentity):
                raise TypeError("post-copy recorded identity has the wrong type")
            if (
                self.recorded_identity.rel_path_key
                != normalize_relative_path(validated_path)
            ):
                raise ValueError(
                    "post-copy recorded identity does not match its display path"
                )


@dataclass
class PostCopySelection:
    """Transient candidates plus mutable, lossless pause continuation state."""

    candidates: tuple[PostCopyCandidate, ...]
    _completed_bytes: dict[str, int] = field(default_factory=dict, repr=False)
    _processed_bytes: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        item_ids = [candidate.item_id for candidate in self.candidates]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("post-copy candidate ids must be unique")
        known_ids = set(item_ids)
        if not set(self._completed_bytes).issubset(known_ids):
            raise ValueError("post-copy continuation contains an unknown item id")
        if any(value < 0 for value in self._completed_bytes.values()):
            raise ValueError("completed post-copy byte counts cannot be negative")
        if self._processed_bytes < sum(self._completed_bytes.values()):
            raise ValueError("post-copy processed bytes cannot trail completed bytes")

    @property
    def pending(self) -> tuple[PostCopyCandidate, ...]:
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.item_id not in self._completed_bytes
        )

    @property
    def completed_count(self) -> int:
        return len(self._completed_bytes)

    @property
    def processed_bytes(self) -> int:
        return self._processed_bytes

    @property
    def completed_bytes(self) -> Mapping[str, int]:
        return dict(self._completed_bytes)

    def physical_bytes_total(self, additional_admitted_bytes: int = 0) -> int:
        """Return the derived read-work budget for this continuation."""

        if type(additional_admitted_bytes) is not int:
            raise TypeError("additional admitted bytes must be an integer")
        if additional_admitted_bytes < 0:
            raise ValueError("additional admitted bytes cannot be negative")
        expected_by_id = {
            candidate.item_id: candidate.expected_stat.size
            for candidate in self.candidates
        }
        planned_bytes = sum(expected_by_id.values()) + additional_admitted_bytes
        completed_bytes = sum(self._completed_bytes.values())
        retry_bytes = max(0, self._processed_bytes - completed_bytes)
        completed_overrun = sum(
            max(0, bytes_read - expected_by_id[item_id])
            for item_id, bytes_read in self._completed_bytes.items()
        )
        return max(
            self._processed_bytes,
            planned_bytes + retry_bytes + completed_overrun,
        )

    def note_bytes_processed(self, size: int) -> None:
        if size < 0:
            raise ValueError("post-copy processed byte increment cannot be negative")
        self._processed_bytes += size

    def mark_completed(self, item_id: str, bytes_read: int) -> None:
        if item_id in self._completed_bytes:
            raise ValueError(f"post-copy item already completed: {item_id}")
        if bytes_read < 0:
            raise ValueError("completed post-copy byte count cannot be negative")
        if not any(candidate.item_id == item_id for candidate in self.candidates):
            raise ValueError(f"unknown post-copy item: {item_id}")
        self._completed_bytes[item_id] = bytes_read


@dataclass(frozen=True)
class IntegritySelectionItem:
    """Immutable row and evidence snapshot supplied by an inventory workflow."""

    item_id: str
    row_id: str
    location_id: str
    root: Path
    rel_path_key: str
    display_path: str
    expected_state: InventoryState
    expected_stat: FileStat | None
    baseline: Attestation | None
    scope_token: str
    reappeared_at: datetime | None = None
    invalidation: VerificationInvalidation | None = None

    def __post_init__(self) -> None:
        if not self.item_id or not self.row_id or not self.location_id:
            raise ValueError("integrity selection identifiers must be non-empty")
        if not self.rel_path_key or not self.display_path or not self.scope_token:
            raise ValueError("integrity selection path and scope must be non-empty")
        if self.expected_state is InventoryState.PRESENT and self.expected_stat is None:
            raise ValueError("present integrity rows require an expected stat")
        if self.expected_state is not InventoryState.PRESENT and self.expected_stat is not None:
            raise ValueError("non-present integrity rows cannot carry a current stat")
        if self.baseline is not None:
            if self.baseline.subject.kind.value != "file":
                raise ValueError("integrity baselines must attest regular files")
            if self.baseline.content.size != self.baseline.subject.size:
                raise ValueError("baseline content size must match its subject")
        if self.reappeared_at is not None:
            if self.reappeared_at.tzinfo is None or self.reappeared_at.utcoffset() is None:
                raise ValueError("reappearance time must be timezone-aware")
            if self.reappeared_at.utcoffset().total_seconds() != 0:
                raise ValueError("reappearance time must be UTC")
        if self.invalidation is not None and not isinstance(
            self.invalidation, VerificationInvalidation
        ):
            raise TypeError("integrity selection invalidation has the wrong type")


@dataclass
class IntegritySelection:
    """Selected immutable rows plus the mutable pause continuation."""

    items: tuple[IntegritySelectionItem, ...]
    _completed_bytes: dict[str, int] = field(default_factory=dict, repr=False)
    _processed_bytes: int = field(default=0, repr=False)
    _bytes_total_high_water: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("integrity selection item ids must be unique")
        row_keys = [(item.location_id, item.row_id) for item in self.items]
        if len(row_keys) != len(set(row_keys)):
            raise ValueError("an inventory row may appear only once per selection")
        path_keys = [(item.location_id, item.rel_path_key) for item in self.items]
        if len(path_keys) != len(set(path_keys)):
            raise ValueError("a canonical path may appear only once per location")
        known_ids = set(item_ids)
        if not set(self._completed_bytes).issubset(known_ids):
            raise ValueError("continuation contains an unknown item id")
        if any(
            type(value) is not int for value in self._completed_bytes.values()
        ):
            raise TypeError("completed byte counts must be integers")
        if any(value < 0 for value in self._completed_bytes.values()):
            raise ValueError("completed byte counts cannot be negative")
        if type(self._processed_bytes) is not int:
            raise TypeError("processed bytes must be an integer")
        if self._processed_bytes < sum(self._completed_bytes.values()):
            raise ValueError("processed bytes cannot trail completed bytes")
        if type(self._bytes_total_high_water) is not int:
            raise TypeError("integrity byte-total high-water must be an integer")
        if self._bytes_total_high_water < self._processed_bytes:
            raise ValueError(
                "integrity byte-total high-water cannot trail processed bytes"
            )

    @property
    def pending(self) -> tuple[IntegritySelectionItem, ...]:
        return tuple(
            item for item in self.items if item.item_id not in self._completed_bytes
        )

    @property
    def completed_count(self) -> int:
        return len(self._completed_bytes)

    @property
    def processed_bytes(self) -> int:
        return self._processed_bytes

    @property
    def bytes_total_high_water(self) -> int:
        return self._bytes_total_high_water

    @property
    def completed_bytes(self) -> Mapping[str, int]:
        return dict(self._completed_bytes)

    def note_bytes_processed(self, size: int) -> None:
        if type(size) is not int:
            raise TypeError("processed byte increment must be an integer")
        if size < 0:
            raise ValueError("processed byte increment cannot be negative")
        self._processed_bytes += size
        self.advance_bytes_total_high_water(self._processed_bytes)

    def advance_bytes_total_high_water(self, value: int) -> None:
        if type(value) is not int:
            raise TypeError("integrity byte-total high-water must be an integer")
        if value < self._processed_bytes:
            raise ValueError(
                "integrity byte-total high-water cannot trail processed bytes"
            )
        self._bytes_total_high_water = max(
            self._bytes_total_high_water,
            value,
        )

    def mark_completed(self, item_id: str, bytes_read: int) -> None:
        if item_id in self._completed_bytes:
            raise ValueError(f"integrity item already completed: {item_id}")
        if type(bytes_read) is not int:
            raise TypeError("completed byte count must be an integer")
        if bytes_read < 0:
            raise ValueError("completed byte count cannot be negative")
        if not any(item.item_id == item_id for item in self.items):
            raise ValueError(f"unknown integrity item: {item_id}")
        self._completed_bytes[item_id] = bytes_read


@dataclass(frozen=True)
class IntegrityOutcome(ResultItem):
    """Reliable typed event for one selected inventory row."""

    item_type: ClassVar[str] = "integrity"

    item_id: str
    row_id: str | None
    location_id: str | None
    path: str
    result: IntegrityResult
    reason: IntegrityReason | None = None
    detail: str | None = None
    read_strategy: ReadStrategy | None = None
    recording: RecordingStatus = RecordingStatus.OK
    record_disposition: RecordDisposition | None = None
    phase: str = IntegrityMode.VERIFY.value

    def __post_init__(self) -> None:
        if not self.item_id:
            raise ValueError("integrity outcome item id must be non-empty")
        if (self.row_id is None) != (self.location_id is None):
            raise ValueError(
                "integrity outcome row and location ids must both be present or absent"
            )
        if self.row_id is not None and (not self.row_id or not self.location_id):
            raise ValueError("integrity outcome ledger ids must be non-empty")
        if not self.path:
            raise ValueError("integrity outcome path must be non-empty")
        if self.phase not in {mode.value for mode in IntegrityMode}:
            raise ValueError("integrity outcome phase must name its integrity mode")


@dataclass(frozen=True)
class IntegrityRunResult:
    """Verifier-owned aggregate derived only from emitted item outcomes."""

    outcomes: tuple[IntegrityOutcome, ...]
    recording: RecordingStatus

    def __post_init__(self) -> None:
        expected = (
            RecordingStatus.DEGRADED
            if any(
                outcome.recording is RecordingStatus.DEGRADED
                for outcome in self.outcomes
            )
            else RecordingStatus.OK
        )
        if self.recording is not expected:
            raise ValueError("run recording status must derive from item outcomes")

    @property
    def counts(self) -> Mapping[IntegrityResult, int]:
        return dict(Counter(outcome.result for outcome in self.outcomes))


@dataclass(frozen=True)
class IntegrityRecordCommand:
    """One atomic conditional baseline/verify/rebaseline request."""

    mode: IntegrityMode
    item_id: str
    row_id: str
    location_id: str
    rel_path_key: str
    scope_token: str
    expected_state: InventoryState
    expected_stat: FileStat
    expected_baseline: Attestation | None
    attestation: Attestation
    advances_last_verified: bool
    clear_reappeared: bool
    expected_invalidation: VerificationInvalidation | None = None

    def __post_init__(self) -> None:
        if self.expected_state is not InventoryState.PRESENT:
            raise ValueError("integrity evidence can be recorded only for present rows")
        subject = self.attestation.subject
        if (
            subject.kind is not self.expected_stat.kind
            or subject.size != self.expected_stat.size
            or subject.mtime_ns != self.expected_stat.mtime_ns
            or subject.file_identity != self.expected_stat.file_identity
        ):
            raise ValueError(
                "new attestation must match the guarded kind/size/mtime/identity"
            )
        if self.mode is IntegrityMode.BASELINE and self.expected_baseline is not None:
            raise ValueError("baseline commands require no established evidence")
        if self.mode is IntegrityMode.VERIFY and self.expected_baseline is None:
            raise ValueError("verification commands require established evidence")
        if self.advances_last_verified is not (self.mode is IntegrityMode.VERIFY):
            raise ValueError("only a prior-evidence verification match advances time")
        if self.expected_invalidation is not None and not isinstance(
            self.expected_invalidation, VerificationInvalidation
        ):
            raise TypeError("expected verification invalidation has the wrong type")


@dataclass(frozen=True, slots=True)
class VerificationInvalidationCommand:
    """Conditionally retain a negative integrity finding for one row."""

    item_id: str
    row_id: str
    location_id: str
    rel_path_key: str
    scope_token: str
    expected_state: InventoryState
    expected_stat: FileStat
    expected_baseline: Attestation
    expected_invalidation: VerificationInvalidation | None
    reason: VerificationInvalidationReason
    invalidated_at: datetime

    def __post_init__(self) -> None:
        if self.expected_state is not InventoryState.PRESENT:
            raise ValueError("verification invalidation requires a present row")
        if not all(
            isinstance(value, str) and value
            for value in (
                self.item_id,
                self.row_id,
                self.location_id,
                self.rel_path_key,
                self.scope_token,
            )
        ):
            raise ValueError("verification invalidation identifiers must be non-empty")
        if self.expected_invalidation is not None and not isinstance(
            self.expected_invalidation, VerificationInvalidation
        ):
            raise TypeError("expected verification invalidation has the wrong type")
        VerificationInvalidation(self.invalidated_at, self.reason)


class IntegrityRecorder(Protocol):
    """Narrow verifier view of the main-ledger recorder."""

    def record_integrity(self, command: IntegrityRecordCommand) -> RecordDisposition:
        """Apply one conditional evidence command or report why it was not applied."""

    def record_verification_invalidation(
        self, command: VerificationInvalidationCommand
    ) -> RecordDisposition:
        """Conditionally retain a modified or mismatched verification result."""


class Clock(Protocol):
    def now(self) -> datetime:
        """Return an aware UTC timestamp."""


class VerificationStream(Protocol):
    strategy: ReadStrategy

    def stat(self) -> FileStat:
        """Return stat evidence for the already-open subject."""

    def iter_chunks(self, chunk_size: int) -> Iterator[bytes]:
        """Yield cache-honest bytes from the already-open subject."""


class VerificationReader(Protocol):
    def open(
        self, root: Path, relative_path: str
    ) -> AbstractContextManager[VerificationStream]:
        """Open the intended root-relative subject without unsafe reparse following."""


@runtime_checkable
class AuthorityBoundVerificationReader(VerificationReader, Protocol):
    """Reader whose open is bound to one reviewed root authority."""

    def open_with_authority(
        self,
        relative_path: str,
        authority: RootAuthority,
    ) -> AbstractContextManager[VerificationStream]:
        """Open a subject relative to the authority's exact logical root."""


def matches_expected_stat(expected: FileStat, actual: FileStat) -> bool:
    """Return whether current stat evidence still matches a retained subject."""

    if expected.kind is not actual.kind:
        return False
    if expected.size != actual.size or expected.mtime_ns != actual.mtime_ns:
        return False
    return (
        expected.file_identity is None
        or expected.file_identity == actual.file_identity
    )


@dataclass(frozen=True)
class VerifierContext:
    """Shared run controls plus verifier timing and chunk policy."""

    run: RunContext
    clock: Clock
    hasher_factory: HasherFactory
    monotonic: Callable[[], float] = monotonic
    chunk_size: int = 4 * 1024 * 1024
    progress_interval_seconds: float = 0.1
    root_authority: RootAuthority | None = None
    post_copy_items_total: int | None = None
    post_copy_bytes_total: int | None = None

    def __post_init__(self) -> None:
        if not callable(self.hasher_factory):
            raise TypeError("verification hasher factory must be callable")
        if self.chunk_size <= 0:
            raise ValueError("verification chunk size must be positive")
        if self.progress_interval_seconds < 0:
            raise ValueError("progress interval cannot be negative")
        if self.root_authority is not None and not isinstance(
            self.root_authority, RootAuthority
        ):
            raise TypeError("verification root authority has the wrong type")
        if (self.post_copy_items_total is None) != (
            self.post_copy_bytes_total is None
        ):
            raise ValueError("post-copy progress admission must be paired")
        for name, value in (
            ("post-copy item admission", self.post_copy_items_total),
            ("post-copy byte budget", self.post_copy_bytes_total),
        ):
            if value is None:
                continue
            if type(value) is not int:
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
            if value > _JAVASCRIPT_MAX_SAFE_INTEGER:
                raise ValueError(f"{name} must be a JavaScript-safe integer")


class UnsupportedVerification(OSError):
    """The requested subject cannot be read with a cache-honest strategy."""
