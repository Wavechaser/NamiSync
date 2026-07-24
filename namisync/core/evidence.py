"""Evidence and outcome vocabulary shared by NamiSync layers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal, Protocol, TypeAlias

from namisync.core.models import FileStat


class Outcome(StrEnum):
    """Execution outcome or reviewed exclusion for one plan item."""

    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELED = "canceled"
    DEFERRED = "deferred"
    BLOCKED = "blocked"


class RecordingStatus(StrEnum):
    """Truth status for an independent persistence axis."""

    OK = "ok"
    DEGRADED = "degraded"


class Provenance(StrEnum):
    """How content evidence was obtained."""

    COPY_ATTESTED = "copy"
    READBACK_ATTESTED = "readback"
    VERIFY_ATTESTED = "verify"


class StreamingHasher(Protocol):
    """Standard-library-only streaming content-hasher seam."""

    def update(self, data: bytes) -> None: ...

    def digest(self) -> bytes: ...


HasherFactory: TypeAlias = Callable[[], StreamingHasher]


class HasherContractError(RuntimeError):
    """A supplied content hasher violated the fixed streaming contract."""


def require_content_digest(value: object) -> bytes:
    """Validate one raw digest returned by the canonical content hasher."""

    if not isinstance(value, bytes):
        raise HasherContractError("content hasher digest must be bytes")
    if len(value) != 16:
        raise HasherContractError(
            "content hasher digest must contain exactly 16 bytes"
        )
    return value


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError(f"{field_name} must be UTC")


@dataclass(frozen=True, slots=True)
class ContentEvidence:
    """Digest evidence for an exact byte stream."""

    algorithm: Literal["xxh3_128"]
    digest: bytes
    size: int
    provenance: Provenance
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.algorithm != "xxh3_128":
            raise ValueError("only xxh3_128 evidence is supported")
        if not isinstance(self.digest, bytes):
            raise TypeError("xxh3_128 digest must be bytes")
        if len(self.digest) != 16:
            raise ValueError("xxh3_128 digest must contain exactly 16 bytes")
        if self.size < 0:
            raise ValueError("evidence size cannot be negative")
        _require_utc(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class Attestation:
    """Content evidence bound to the observed filesystem subject."""

    content: ContentEvidence
    subject: FileStat

    def __post_init__(self) -> None:
        if not isinstance(self.subject, FileStat):
            raise TypeError("attestation subject must be FileStat evidence")
        if self.content.size != self.subject.size:
            raise ValueError("attestation content size must match its subject")
