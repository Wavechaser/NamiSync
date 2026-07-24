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
from typing import Callable, ClassVar, Iterator, Mapping, Protocol

from .evidence import Attestation, HasherFactory, RecordingStatus
from .models import FileStat
from .session import ResultItem, RunContext


class InventoryState(StrEnum):
    """Inventory state captured by a freshly constructed selection."""

    PRESENT = "present"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"


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


@dataclass
class IntegritySelection:
    """Selected immutable rows plus the mutable pause continuation."""

    items: tuple[IntegritySelectionItem, ...]
    _completed_bytes: dict[str, int] = field(default_factory=dict, repr=False)
    _processed_bytes: int = field(default=0, repr=False)

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
        if any(value < 0 for value in self._completed_bytes.values()):
            raise ValueError("completed byte counts cannot be negative")
        if self._processed_bytes < sum(self._completed_bytes.values()):
            raise ValueError("processed bytes cannot trail completed bytes")

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
    def completed_bytes(self) -> Mapping[str, int]:
        return dict(self._completed_bytes)

    def note_bytes_processed(self, size: int) -> None:
        if size < 0:
            raise ValueError("processed byte increment cannot be negative")
        self._processed_bytes += size

    def mark_completed(self, item_id: str, bytes_read: int) -> None:
        if item_id in self._completed_bytes:
            raise ValueError(f"integrity item already completed: {item_id}")
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
    row_id: str
    location_id: str
    path: str
    result: IntegrityResult
    reason: IntegrityReason | None = None
    detail: str | None = None
    read_strategy: ReadStrategy | None = None
    recording: RecordingStatus = RecordingStatus.OK
    record_disposition: RecordDisposition | None = None
    phase: str = IntegrityMode.VERIFY.value

    def __post_init__(self) -> None:
        if not self.item_id or not self.row_id or not self.location_id:
            raise ValueError("integrity outcome identifiers must be non-empty")
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


class IntegrityRecorder(Protocol):
    """Narrow verifier view of the main-ledger recorder."""

    def record_integrity(self, command: IntegrityRecordCommand) -> RecordDisposition:
        """Apply one conditional evidence command or report why it was not applied."""


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


@dataclass(frozen=True)
class VerifierContext:
    """Shared run controls plus verifier timing and chunk policy."""

    run: RunContext
    clock: Clock
    hasher_factory: HasherFactory
    monotonic: Callable[[], float] = monotonic
    chunk_size: int = 4 * 1024 * 1024
    progress_interval_seconds: float = 0.1

    def __post_init__(self) -> None:
        if not callable(self.hasher_factory):
            raise TypeError("verification hasher factory must be callable")
        if self.chunk_size <= 0:
            raise ValueError("verification chunk size must be positive")
        if self.progress_interval_seconds < 0:
            raise ValueError("progress interval cannot be negative")


class UnsupportedVerification(OSError):
    """The requested subject cannot be read with a cache-honest strategy."""
