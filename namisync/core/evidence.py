"""Evidence and outcome vocabulary shared by NamiSync layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

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


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError(f"{field_name} must be UTC")


@dataclass(frozen=True, slots=True)
class ContentEvidence:
    """Digest evidence for an exact byte stream."""

    algorithm: Literal["sha256"]
    digest: bytes
    size: int
    provenance: Provenance
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ValueError("only sha256 evidence is supported")
        if not isinstance(self.digest, bytes):
            raise TypeError("sha256 digest must be bytes")
        if len(self.digest) != 32:
            raise ValueError("sha256 digest must contain exactly 32 bytes")
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
