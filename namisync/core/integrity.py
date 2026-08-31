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
from types import MappingProxyType
from typing import Callable, ClassVar, Iterator, Mapping, Protocol, runtime_checkable

from .evidence import (
    Attestation,
    HasherFactory,
    Provenance,
    RecordingStatus,
    attestation_fact,
    snapshot_attestation,
)
from .models import FileStat, file_stat_fact, snapshot_file_stat
from .pathing import (
    fold_validated_path,
    normalize_relative_path,
    validate_relative_path,
)
from .root_authority import RootAuthority
from .session import ResultItem, RunContext
from .scalars import (
    bounded_utf8_text,
    checked_add_signed_64,
    require_safe_int,
    require_signed_64,
    require_utf16_path,
)


_PLATFORM_PATH_TYPE = type(Path())
_UNINITIALIZED_KNOWN_ITEM_IDS = object()


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


INTEGRITY_CANDIDATE_ROW_LIMIT = 120_000
INTEGRITY_CANDIDATE_RETAINED_BYTE_LIMIT = 201_326_592
MAX_VERIFIER_CHUNK_SIZE = 4 * 1024 * 1024
INTEGRITY_CANDIDATE_ROWS_MESSAGE = (
    "This integrity scope contains more than 120,000 items. Narrow the selected "
    "folders, then try again."
)
INTEGRITY_CANDIDATE_RETAINED_BYTES_MESSAGE = (
    "This integrity scope contains more item detail than NamiSync can retain safely. "
    "Narrow the selected folders, then try again."
)


class IntegrityCandidateLimitAxis(StrEnum):
    """Closed axis vocabulary for standalone-integrity candidate custody."""

    ROWS = "rows"
    RETAINED_BYTES = "retained-bytes"


@dataclass(frozen=True, slots=True)
class IntegrityCandidateLimitExceeded:
    """Exact internal fact for a complete candidate population that cannot fit."""

    reason: str
    axis: IntegrityCandidateLimitAxis
    row_limit: int | None
    byte_limit: int | None

    def __post_init__(self) -> None:
        if type(self.reason) is not str:
            raise TypeError("integrity candidate fact reason has the wrong type")
        if self.reason != "integrity_candidate_limit_exceeded":
            raise ValueError("integrity candidate fact reason is invalid")
        if type(self.axis) is not IntegrityCandidateLimitAxis:
            raise TypeError("integrity candidate axis has the wrong type")
        if self.row_limit is not None:
            require_safe_int(self.row_limit, "integrity candidate row_limit")
        if self.byte_limit is not None:
            require_signed_64(self.byte_limit, "integrity candidate byte_limit")
        if self.axis is IntegrityCandidateLimitAxis.ROWS:
            if (
                self.row_limit != INTEGRITY_CANDIDATE_ROW_LIMIT
                or self.byte_limit is not None
            ):
                raise ValueError("row integrity candidate fact has invalid limits")
            return
        if (
            self.row_limit is not None
            or self.byte_limit != INTEGRITY_CANDIDATE_RETAINED_BYTE_LIMIT
        ):
            raise ValueError("byte integrity candidate fact has invalid limits")

    @classmethod
    def rows(cls) -> "IntegrityCandidateLimitExceeded":
        return cls(
            "integrity_candidate_limit_exceeded",
            IntegrityCandidateLimitAxis.ROWS,
            INTEGRITY_CANDIDATE_ROW_LIMIT,
            None,
        )

    @classmethod
    def retained_bytes(cls) -> "IntegrityCandidateLimitExceeded":
        return cls(
            "integrity_candidate_limit_exceeded",
            IntegrityCandidateLimitAxis.RETAINED_BYTES,
            None,
            INTEGRITY_CANDIDATE_RETAINED_BYTE_LIMIT,
        )


class IntegrityCandidateLimitError(ValueError):
    """Raised when complete standalone-integrity candidate custody cannot fit."""

    def __init__(self, fact: IntegrityCandidateLimitExceeded) -> None:
        if type(fact) is not IntegrityCandidateLimitExceeded:
            raise TypeError("integrity candidate limit error requires its typed fact")
        canonical = IntegrityCandidateLimitExceeded(
            fact.reason,
            fact.axis,
            fact.row_limit,
            fact.byte_limit,
        )
        message = (
            INTEGRITY_CANDIDATE_ROWS_MESSAGE
            if canonical.axis is IntegrityCandidateLimitAxis.ROWS
            else INTEGRITY_CANDIDATE_RETAINED_BYTES_MESSAGE
        )
        super().__init__(message)
        self.fact = canonical


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
                != fold_validated_path(validated_path)
            ):
                raise ValueError(
                    "post-copy recorded identity does not match its display path"
                )


@dataclass(slots=True)
class PostCopySelection:
    """Transient candidates plus mutable, lossless pause continuation state."""

    candidates: tuple[PostCopyCandidate, ...]
    _completed_bytes: dict[str, int] = field(default_factory=dict, repr=False)
    _processed_bytes: int = field(default=0, repr=False)
    _known_item_ids: frozenset[str] = field(
        default=_UNINITIALIZED_KNOWN_ITEM_IDS,
        init=False,
        repr=False,
        compare=False,
    )  # type: ignore[assignment]

    def __post_init__(self) -> None:
        item_ids = [candidate.item_id for candidate in self.candidates]
        known_ids = frozenset(item_ids)
        if len(item_ids) != len(known_ids):
            raise ValueError("post-copy candidate ids must be unique")
        try:
            retained_known_ids = self._known_item_ids
        except AttributeError as error:
            raise TypeError("post-copy known-item index is missing") from error
        if retained_known_ids is _UNINITIALIZED_KNOWN_ITEM_IDS:
            self._known_item_ids = known_ids
        else:
            if type(retained_known_ids) is not frozenset:
                raise TypeError("post-copy known-item index has the wrong type")
            if retained_known_ids != known_ids:
                raise ValueError("post-copy known-item index changed")
        if not set(self._completed_bytes).issubset(known_ids):
            raise ValueError("post-copy continuation contains an unknown item id")
        completed_bytes = 0
        for value in self._completed_bytes.values():
            require_signed_64(value, "completed post-copy byte count")
            completed_bytes = checked_add_signed_64(
                completed_bytes,
                value,
                "completed post-copy bytes",
            )
        require_signed_64(self._processed_bytes, "post-copy processed bytes")
        if self._processed_bytes < completed_bytes:
            raise ValueError("post-copy processed bytes cannot trail completed bytes")

    @property
    def known_item_ids(self) -> frozenset[str]:
        """Return the item ids admitted when this selection was constructed."""

        return self._known_item_ids

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

        require_signed_64(
            additional_admitted_bytes,
            "additional admitted post-copy bytes",
        )
        expected_by_id = {
            candidate.item_id: candidate.expected_stat.size
            for candidate in self.candidates
        }
        planned_bytes = additional_admitted_bytes
        for size in expected_by_id.values():
            planned_bytes = checked_add_signed_64(
                planned_bytes,
                size,
                "post-copy planned bytes",
            )
        completed_bytes = 0
        for size in self._completed_bytes.values():
            completed_bytes = checked_add_signed_64(
                completed_bytes,
                size,
                "completed post-copy bytes",
            )
        retry_bytes = max(0, self._processed_bytes - completed_bytes)
        completed_overrun = 0
        for item_id, bytes_read in self._completed_bytes.items():
            completed_overrun = checked_add_signed_64(
                completed_overrun,
                max(0, bytes_read - expected_by_id[item_id]),
                "post-copy completed overrun bytes",
            )
        physical_total = checked_add_signed_64(
            planned_bytes,
            retry_bytes,
            "post-copy physical bytes",
        )
        physical_total = checked_add_signed_64(
            physical_total,
            completed_overrun,
            "post-copy physical bytes",
        )
        return max(
            self._processed_bytes,
            physical_total,
        )

    def note_bytes_processed(self, size: int) -> None:
        self._processed_bytes = checked_add_signed_64(
            self._processed_bytes,
            size,
            "post-copy processed bytes",
        )

    def mark_completed(self, item_id: str, bytes_read: int) -> None:
        if item_id in self._completed_bytes:
            raise ValueError(f"post-copy item already completed: {item_id}")
        require_signed_64(bytes_read, "completed post-copy byte count")
        if item_id not in self._known_item_ids:
            raise ValueError(f"unknown post-copy item: {item_id}")
        self._completed_bytes[item_id] = bytes_read


@dataclass(frozen=True, slots=True)
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


@dataclass(slots=True)
class IntegritySelection:
    """Selected immutable rows plus the mutable pause continuation."""

    items: tuple[IntegritySelectionItem, ...]
    _completed_bytes: dict[str, int] = field(default_factory=dict, repr=False)
    _processed_bytes: int = field(default=0, repr=False)
    _bytes_total_high_water: int = field(default=0, repr=False)
    _known_item_ids: frozenset[str] = field(
        default=_UNINITIALIZED_KNOWN_ITEM_IDS,
        init=False,
        repr=False,
        compare=False,
    )  # type: ignore[assignment]

    def __post_init__(self) -> None:
        item_ids = [item.item_id for item in self.items]
        known_ids = frozenset(item_ids)
        if len(item_ids) != len(known_ids):
            raise ValueError("integrity selection item ids must be unique")
        row_keys = [(item.location_id, item.row_id) for item in self.items]
        if len(row_keys) != len(set(row_keys)):
            raise ValueError("an inventory row may appear only once per selection")
        path_keys = [(item.location_id, item.rel_path_key) for item in self.items]
        if len(path_keys) != len(set(path_keys)):
            raise ValueError("a canonical path may appear only once per location")
        try:
            retained_known_ids = self._known_item_ids
        except AttributeError as error:
            raise TypeError("integrity known-item index is missing") from error
        if retained_known_ids is _UNINITIALIZED_KNOWN_ITEM_IDS:
            self._known_item_ids = known_ids
        else:
            if type(retained_known_ids) is not frozenset:
                raise TypeError("integrity known-item index has the wrong type")
            if retained_known_ids != known_ids:
                raise ValueError("integrity known-item index changed")
        if not set(self._completed_bytes).issubset(known_ids):
            raise ValueError("continuation contains an unknown item id")
        completed_bytes = 0
        for value in self._completed_bytes.values():
            require_signed_64(value, "completed integrity byte count")
            completed_bytes = checked_add_signed_64(
                completed_bytes,
                value,
                "completed integrity bytes",
            )
        require_signed_64(self._processed_bytes, "integrity processed bytes")
        if self._processed_bytes < completed_bytes:
            raise ValueError("processed bytes cannot trail completed bytes")
        require_signed_64(
            self._bytes_total_high_water,
            "integrity byte-total high-water",
        )
        if self._bytes_total_high_water < self._processed_bytes:
            raise ValueError(
                "integrity byte-total high-water cannot trail processed bytes"
            )

    @property
    def known_item_ids(self) -> frozenset[str]:
        """Return the item ids admitted when this selection was constructed."""

        return self._known_item_ids

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
        self._processed_bytes = checked_add_signed_64(
            self._processed_bytes,
            size,
            "integrity processed bytes",
        )
        self.advance_bytes_total_high_water(self._processed_bytes)

    def advance_bytes_total_high_water(self, value: int) -> None:
        require_signed_64(value, "integrity byte-total high-water")
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
        require_signed_64(bytes_read, "completed integrity byte count")
        if item_id not in self._known_item_ids:
            raise ValueError(f"unknown integrity item: {item_id}")
        self._completed_bytes[item_id] = bytes_read


@dataclass(frozen=True, slots=True)
class IntegritySelectionItemFact:
    """Flattened workflow authority for one standalone verifier candidate."""

    item_id: str
    row_id: str
    location_id: str
    root_path: str
    rel_path_key: str
    display_path: str
    expected_state: InventoryState
    expected_stat: tuple[object, ...] | None
    baseline: tuple[object, ...] | None
    scope_token: str
    reappeared_at: str | None
    invalidation: tuple[str, VerificationInvalidationReason] | None


@dataclass(frozen=True, slots=True)
class IntegritySelectionAuthority:
    """Exact admitted facts kept private from selection collaborators."""

    items: tuple[IntegritySelectionItemFact, ...]
    completed_bytes: tuple[tuple[str, int], ...]
    processed_bytes: int
    bytes_total_high_water: int


@dataclass(frozen=True, slots=True)
class PostCopySelectionAuthority:
    """Exact admitted candidates kept private from verifier collaborators."""

    candidates: tuple[PostCopyCandidate, ...]
    completed_bytes: Mapping[str, int]
    processed_bytes: int


def _datetime_fact(value: object, field_name: str) -> str:
    if type(value) is not datetime:
        raise TypeError(f"{field_name} must be an exact datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field_name} must be UTC")
    return value.isoformat()


def integrity_selection_item_fact(value: object) -> IntegritySelectionItemFact:
    """Snapshot one selection row without retaining collaborator objects."""

    if type(value) is not IntegritySelectionItem:
        raise TypeError("integrity selection requires exact item values")
    for field_name, field_value in (
        ("item id", value.item_id),
        ("row id", value.row_id),
        ("location id", value.location_id),
        ("relative path key", value.rel_path_key),
        ("display path", value.display_path),
        ("scope token", value.scope_token),
    ):
        if type(field_value) is not str:
            raise TypeError(f"integrity selection {field_name} must be exact text")
    if type(value.expected_state) is not InventoryState:
        raise TypeError("integrity selection state has the wrong type")
    if type(value.root) is not _PLATFORM_PATH_TYPE:
        raise TypeError("integrity selection root has the wrong type")
    if value.expected_stat is not None and type(value.expected_stat) is not FileStat:
        raise TypeError("integrity expected stat has the wrong type")
    if value.baseline is not None and type(value.baseline) is not Attestation:
        raise TypeError("integrity baseline has the wrong type")
    if (
        value.reappeared_at is not None
        and type(value.reappeared_at) is not datetime
    ):
        raise TypeError("integrity reappearance time has the wrong type")
    if (
        value.invalidation is not None
        and type(value.invalidation) is not VerificationInvalidation
    ):
        raise TypeError("integrity selection invalidation has the wrong type")
    root_path = str(value.root)
    if type(root_path) is not str:
        raise TypeError("integrity selection root must project to exact text")
    reappeared = (
        None
        if value.reappeared_at is None
        else _datetime_fact(value.reappeared_at, "integrity reappearance time")
    )
    invalidation = value.invalidation
    if invalidation is not None:
        if type(invalidation) is not VerificationInvalidation:
            raise TypeError("integrity selection invalidation has the wrong type")
        if type(invalidation.reason) is not VerificationInvalidationReason:
            raise TypeError("integrity invalidation reason has the wrong type")
        invalidation_fact = (
            _datetime_fact(invalidation.at, "integrity invalidation time"),
            invalidation.reason,
        )
    else:
        invalidation_fact = None
    expected_stat = (
        None
        if value.expected_stat is None
        else file_stat_fact(value.expected_stat)
    )
    baseline = (
        None if value.baseline is None else attestation_fact(value.baseline)
    )
    IntegritySelectionItem.__post_init__(value)
    return IntegritySelectionItemFact(
        value.item_id,
        value.row_id,
        value.location_id,
        root_path,
        value.rel_path_key,
        value.display_path,
        value.expected_state,
        expected_stat,
        baseline,
        value.scope_token,
        reappeared,
        invalidation_fact,
    )


def _snapshot_post_copy_candidate(value: object) -> PostCopyCandidate:
    """Detach one exact linked-verifier candidate into typed domain values."""

    if type(value) is not PostCopyCandidate:
        raise TypeError("post-copy selection requires exact candidate values")
    if type(value.item_id) is not str:
        raise TypeError("post-copy candidate item id must be exact text")
    if type(value.root) is not _PLATFORM_PATH_TYPE:
        raise TypeError("post-copy candidate root has the wrong type")
    if type(value.display_path) is not str:
        raise TypeError("post-copy candidate display path must be exact text")
    recorded = value.recorded_identity
    if recorded is not None:
        if type(recorded) is not PostCopyRecordIdentity:
            raise TypeError("post-copy recorded identity has the wrong type")
        fields = (
            recorded.row_id,
            recorded.location_id,
            recorded.scope_token,
            recorded.rel_path_key,
        )
        if any(type(field_value) is not str for field_value in fields):
            raise TypeError("post-copy recorded identity fields must be exact text")
        recorded = PostCopyRecordIdentity(*fields)
    return PostCopyCandidate(
        value.item_id,
        value.root,
        value.display_path,
        snapshot_file_stat(value.expected_stat),
        snapshot_attestation(value.copy_attestation),
        recorded,
    )


def snapshot_integrity_selection_authority(
    value: object,
) -> IntegritySelectionAuthority:
    """Capture exact standalone-selection facts before exposing the selection."""

    if type(value) is not IntegritySelection:
        raise TypeError("integrity selection must have the exact public shape")
    if type(value.items) is not tuple:
        raise TypeError("integrity selection items must be an exact tuple")
    if any(type(item) is not IntegritySelectionItem for item in value.items):
        raise TypeError("integrity selection items have the wrong type")
    if type(value._completed_bytes) is not dict:
        raise TypeError("integrity completion state must be an exact dict")
    if any(
        type(item_id) is not str or type(completed) is not int
        for item_id, completed in value._completed_bytes.items()
    ):
        raise TypeError("integrity completion facts have the wrong type")
    if type(value._processed_bytes) is not int:
        raise TypeError("integrity processed bytes have the wrong type")
    if type(value._bytes_total_high_water) is not int:
        raise TypeError("integrity byte total has the wrong type")
    item_facts = tuple(integrity_selection_item_fact(item) for item in value.items)
    IntegritySelection.__post_init__(value)
    return IntegritySelectionAuthority(
        item_facts,
        tuple(value._completed_bytes.items()),
        value._processed_bytes,
        value._bytes_total_high_water,
    )


def revalidate_integrity_selection_authority(
    value: object,
    authority: object,
    *,
    allow_progress: bool,
) -> None:
    """Revalidate fixed selection facts and the allowed mutable progress delta."""

    if type(authority) is not IntegritySelectionAuthority:
        raise TypeError("integrity selection authority has the wrong type")
    if type(value) is not IntegritySelection:
        raise TypeError("integrity selection must have the exact public shape")
    if type(value.items) is not tuple or len(value.items) != len(authority.items):
        raise ValueError("integrity selection items changed during collaboration")
    if any(type(item) is not IntegritySelectionItem for item in value.items):
        raise TypeError("integrity selection items have the wrong type")
    if type(value._completed_bytes) is not dict:
        raise TypeError("integrity completion state must be an exact dict")
    if any(
        type(item_id) is not str or type(completed) is not int
        for item_id, completed in value._completed_bytes.items()
    ):
        raise TypeError("integrity completion facts have the wrong type")
    if type(value._processed_bytes) is not int:
        raise TypeError("integrity processed bytes have the wrong type")
    if type(value._bytes_total_high_water) is not int:
        raise TypeError("integrity byte total has the wrong type")
    item_facts = tuple(integrity_selection_item_fact(item) for item in value.items)
    for item, expected in zip(item_facts, authority.items, strict=True):
        if item != expected:
            raise ValueError("integrity selection item changed during collaboration")
    IntegritySelection.__post_init__(value)
    for item_id, completed_bytes in authority.completed_bytes:
        if value._completed_bytes.get(item_id) != completed_bytes:
            raise ValueError("integrity prior completion changed during collaboration")
    if allow_progress:
        if value._processed_bytes < authority.processed_bytes:
            raise ValueError("integrity processed bytes regressed")
        if value._bytes_total_high_water < authority.bytes_total_high_water:
            raise ValueError("integrity byte total regressed")
        return
    if (
        value._completed_bytes != dict(authority.completed_bytes)
        or value._processed_bytes != authority.processed_bytes
        or value._bytes_total_high_water != authority.bytes_total_high_water
    ):
        raise ValueError("integrity selection changed during capture")


def snapshot_post_copy_selection_authority(
    value: object,
) -> PostCopySelectionAuthority:
    """Capture exact linked-selection facts before exposing the selection."""

    if type(value) is not PostCopySelection:
        raise TypeError("post-copy selection must have the exact public shape")
    if type(value.candidates) is not tuple:
        raise TypeError("post-copy candidates must be an exact tuple")
    if type(value._completed_bytes) is not dict:
        raise TypeError("post-copy completion state must be an exact dict")
    if any(
        type(item_id) is not str or type(completed) is not int
        for item_id, completed in value._completed_bytes.items()
    ):
        raise TypeError("post-copy completion facts have the wrong type")
    if type(value._processed_bytes) is not int:
        raise TypeError("post-copy processed bytes have the wrong type")
    candidates = tuple(
        _snapshot_post_copy_candidate(item) for item in value.candidates
    )
    PostCopySelection.__post_init__(value)
    return PostCopySelectionAuthority(
        candidates,
        MappingProxyType(dict(value._completed_bytes)),
        value._processed_bytes,
    )


def revalidate_post_copy_selection_authority(
    value: object,
    authority: object,
    *,
    allow_progress: bool,
) -> None:
    """Revalidate fixed linked facts and the allowed mutable progress delta."""

    if type(authority) is not PostCopySelectionAuthority:
        raise TypeError("post-copy selection authority has the wrong type")
    if type(value) is not PostCopySelection:
        raise TypeError("post-copy selection must have the exact public shape")
    if (
        type(value.candidates) is not tuple
        or len(value.candidates) != len(authority.candidates)
    ):
        raise ValueError("post-copy candidates changed during collaboration")
    if type(value._completed_bytes) is not dict:
        raise TypeError("post-copy completion state must be an exact dict")
    if any(
        type(item_id) is not str or type(completed) is not int
        for item_id, completed in value._completed_bytes.items()
    ):
        raise TypeError("post-copy completion facts have the wrong type")
    if type(value._processed_bytes) is not int:
        raise TypeError("post-copy processed bytes have the wrong type")
    candidates = tuple(
        _snapshot_post_copy_candidate(item) for item in value.candidates
    )
    if candidates != authority.candidates:
        raise ValueError("post-copy candidate changed during collaboration")
    PostCopySelection.__post_init__(value)
    for item_id, completed_bytes in authority.completed_bytes.items():
        if value._completed_bytes.get(item_id) != completed_bytes:
            raise ValueError("post-copy prior completion changed during collaboration")
    if allow_progress:
        if value._processed_bytes < authority.processed_bytes:
            raise ValueError("post-copy processed bytes regressed")
        return
    if (
        value._completed_bytes != dict(authority.completed_bytes)
        or value._processed_bytes != authority.processed_bytes
    ):
        raise ValueError("post-copy selection changed during capture")


@dataclass(frozen=True, slots=True)
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
    detail_omitted_count: int = 0

    def __post_init__(self) -> None:
        if type(self.item_id) is not str:
            raise TypeError("integrity outcome item id must be text")
        if not self.item_id:
            raise ValueError("integrity outcome item id must be non-empty")
        if self.row_id is not None and type(self.row_id) is not str:
            raise TypeError("integrity outcome row id must be text or None")
        if self.location_id is not None and type(self.location_id) is not str:
            raise TypeError("integrity outcome location id must be text or None")
        if (self.row_id is None) != (self.location_id is None):
            raise ValueError(
                "integrity outcome row and location ids must both be present or absent"
            )
        if self.row_id is not None and (not self.row_id or not self.location_id):
            raise ValueError("integrity outcome ledger ids must be non-empty")
        if type(self.path) is not str:
            raise TypeError("integrity outcome path must be text")
        if not self.path:
            raise ValueError("integrity outcome path must be non-empty")
        require_utf16_path(self.path, "integrity outcome path")
        if type(self.result) is not IntegrityResult:
            raise TypeError("integrity outcome result has the wrong type")
        if self.reason is not None and type(self.reason) is not IntegrityReason:
            raise TypeError("integrity outcome reason has the wrong type")
        if (
            self.read_strategy is not None
            and type(self.read_strategy) is not ReadStrategy
        ):
            raise TypeError("integrity outcome read strategy has the wrong type")
        if type(self.recording) is not RecordingStatus:
            raise TypeError("integrity outcome recording has the wrong type")
        if (
            self.record_disposition is not None
            and type(self.record_disposition) is not RecordDisposition
        ):
            raise TypeError("integrity outcome record disposition has the wrong type")
        if type(self.phase) is not str:
            raise TypeError("integrity outcome phase must be text")
        if self.phase not in {mode.value for mode in IntegrityMode}:
            raise ValueError("integrity outcome phase must name its integrity mode")
        require_safe_int(
            self.detail_omitted_count,
            "integrity detail_omitted_count",
        )
        bounded = bounded_utf8_text(self.detail, "integrity detail")
        if self.detail is not None and bounded is None:
            object.__setattr__(self, "detail", None)
            object.__setattr__(
                self,
                "detail_omitted_count",
                require_safe_int(
                    self.detail_omitted_count + 1,
                    "integrity detail_omitted_count",
                ),
            )


def snapshot_integrity_outcome(
    value: object,
    *,
    item_id: str,
    row_id: str | None,
    location_id: str | None,
    path: str,
    phase: str,
) -> IntegrityOutcome:
    """Detach producer facts while binding workflow-owned subject identity."""

    if not isinstance(value, IntegrityOutcome):
        raise TypeError("integrity outcome must be an IntegrityOutcome")
    result = value.result
    reason = value.reason
    detail = value.detail
    read_strategy = value.read_strategy
    recording = value.recording
    record_disposition = value.record_disposition
    omitted = value.detail_omitted_count
    return IntegrityOutcome(
        item_id=item_id,
        row_id=row_id,
        location_id=location_id,
        path=path,
        result=result,
        reason=reason,
        detail=detail,
        read_strategy=read_strategy,
        recording=recording,
        record_disposition=record_disposition,
        phase=phase,
        detail_omitted_count=omitted,
    )


@dataclass(frozen=True, slots=True)
class IntegrityRunResult:
    """Verifier-owned aggregate derived only from emitted item outcomes."""

    outcomes: tuple[IntegrityOutcome, ...]
    recording: RecordingStatus

    def __post_init__(self) -> None:
        if type(self.outcomes) is not tuple:
            raise TypeError("run outcomes must be an exact tuple")
        if any(not isinstance(outcome, IntegrityOutcome) for outcome in self.outcomes):
            raise TypeError("run outcomes must contain IntegrityOutcome values")
        if type(self.recording) is not RecordingStatus:
            raise TypeError("run recording status has the wrong type")
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


def validate_integrity_run_result(
    value: object,
    emitted_outcomes: list[ResultItem] | tuple[ResultItem, ...],
    *,
    start: int = 0,
) -> RecordingStatus:
    """Validate one verifier aggregate against accepted reliable outcomes."""

    if not isinstance(value, IntegrityRunResult):
        raise TypeError("integrity runner must return IntegrityRunResult")
    if type(emitted_outcomes) not in {list, tuple}:
        raise TypeError("emitted integrity outcomes require an owned sequence")
    if type(start) is not int:
        raise TypeError("integrity outcome start must be an integer")
    if start < 0 or start > len(emitted_outcomes):
        raise ValueError("integrity outcome start is outside the owned sequence")
    outcomes = value.outcomes
    recording = value.recording
    if type(outcomes) is not tuple:
        raise TypeError("integrity runner outcomes must be a tuple")
    if type(recording) is not RecordingStatus:
        raise TypeError("integrity runner recording has the wrong type")
    if len(outcomes) != len(emitted_outcomes) - start:
        raise ValueError("integrity runner outcomes must match emitted outcomes")
    expected_recording = RecordingStatus.OK
    for offset, source in enumerate(outcomes):
        if not isinstance(source, IntegrityOutcome):
            raise TypeError("integrity runner outcomes have the wrong type")
        authoritative = emitted_outcomes[start + offset]
        snapshot = snapshot_integrity_outcome(
            source,
            item_id=source.item_id,
            row_id=source.row_id,
            location_id=source.location_id,
            path=source.path,
            phase=source.phase,
        )
        if type(authoritative) is not IntegrityOutcome or snapshot != authoritative:
            raise ValueError("integrity runner outcomes must match emitted outcomes")
        if authoritative.recording is RecordingStatus.DEGRADED:
            expected_recording = RecordingStatus.DEGRADED
    if recording is not expected_recording:
        raise ValueError("integrity runner recording must derive from emitted outcomes")
    return recording


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
class VerifierContext:
    """Shared run controls plus verifier timing and chunk policy."""

    run: RunContext
    clock: Clock
    hasher_factory: HasherFactory
    monotonic: Callable[[], float] = monotonic
    chunk_size: int = MAX_VERIFIER_CHUNK_SIZE
    progress_interval_seconds: float = 0.1
    root_authority: RootAuthority | None = None
    post_copy_items_total: int | None = None
    post_copy_bytes_total: int | None = None

    def __post_init__(self) -> None:
        if not callable(self.hasher_factory):
            raise TypeError("verification hasher factory must be callable")
        if type(self.chunk_size) is not int:
            raise TypeError("verification chunk size must be an integer")
        if not 1 <= self.chunk_size <= MAX_VERIFIER_CHUNK_SIZE:
            raise ValueError(
                "verification chunk size must be between 1 and 4194304 bytes"
            )
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
        if self.post_copy_items_total is not None:
            require_safe_int(
                self.post_copy_items_total,
                "post-copy item admission",
            )
        if self.post_copy_bytes_total is not None:
            require_signed_64(
                self.post_copy_bytes_total,
                "post-copy byte budget",
            )


def bind_verifier_context(
    value: object,
    run: RunContext,
    *,
    root_authority: RootAuthority,
    post_copy_items_total: int | None = None,
    post_copy_bytes_total: int | None = None,
) -> VerifierContext:
    """Detach factory policy while retaining workflow-owned run controls."""

    if type(value) is not VerifierContext:
        raise TypeError("verification context factory must return VerifierContext")
    if type(run) is not RunContext:
        raise TypeError("verification run controls must have the exact public shape")
    return VerifierContext(
        run=run,
        clock=value.clock,
        hasher_factory=value.hasher_factory,
        monotonic=value.monotonic,
        chunk_size=value.chunk_size,
        progress_interval_seconds=value.progress_interval_seconds,
        root_authority=root_authority,
        post_copy_items_total=post_copy_items_total,
        post_copy_bytes_total=post_copy_bytes_total,
    )


class UnsupportedVerification(OSError):
    """The requested subject cannot be read with a cache-honest strategy."""
