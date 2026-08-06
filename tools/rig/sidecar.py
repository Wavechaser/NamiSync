"""Persisted baseline evidence for a static corpus.

The verify path short-circuits at ``STAT_CHANGED`` before it hashes anything,
so a stale sidecar does not fail loudly -- it quietly turns a throughput
benchmark into a guard benchmark. Every load therefore validates against a
fresh scan and refuses to proceed on drift.

The sidecar must live outside the scanned root: ``IgnoreSet`` covers
``.synctrash`` and ``.synctmp-*`` only, so a file inside the corpus would be
scanned as corpus content.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Iterable, Mapping

from namisync.core.evidence import Attestation, ContentEvidence, Provenance
from namisync.core.models import EntryKind, FileIdentity, FileStat, MetadataSnapshot


IdentityMode = str
BOUND: IdentityMode = "bound"
PORTABLE: IdentityMode = "portable"
IDENTITY_MODES = (BOUND, PORTABLE)

FORMAT = "namisync-rig-baseline-1"


def sidecar_path_for(root: Path) -> Path:
    """Return the sibling sidecar path for one corpus root."""

    root = Path(root).resolve()
    if not root.name:
        raise SidecarError(
            f"cannot derive a sidecar path for {root}; pass --sidecar explicitly"
        )
    return root.parent / f"{root.name}.baseline.jsonl"


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Outcome of checking stored evidence against a fresh scan."""

    matched: tuple[str, ...]
    drifted: tuple[str, ...]
    missing: tuple[str, ...]
    unseen: tuple[str, ...]
    identity_mode: IdentityMode

    @property
    def usable(self) -> bool:
        # ``unseen`` blocks too: a scanned file without evidence silently
        # settles as BASELINED instead of VERIFIED, mixing two paths in one
        # measurement.
        return not (self.drifted or self.missing or self.unseen)

    def summary(self) -> str:
        return (
            f"{len(self.matched)} matched, {len(self.drifted)} drifted, "
            f"{len(self.missing)} missing from disk, "
            f"{len(self.unseen)} scanned without evidence "
            f"({self.identity_mode} identity)"
        )


class SidecarError(RuntimeError):
    """The sidecar is unreadable, malformed, or no longer describes the corpus."""


def write(
    path: Path,
    attestations: Mapping[str, Attestation],
    *,
    identity_mode: IdentityMode = PORTABLE,
) -> int:
    """Write one row per canonical path key; return the row count.

    NTFS file identity is always recorded; the header's identity mode decides
    whether a later load enforces it. ``portable`` drops identity on read so
    the corpus survives being moved or restored, at the cost of one tuple
    comparison of fidelity against production.
    """

    if identity_mode not in IDENTITY_MODES:
        raise ValueError(f"unknown identity mode: {identity_mode!r}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps({"format": FORMAT, "identity_mode": identity_mode}) + "\n"
        )
        for key in sorted(attestations):
            handle.write(json.dumps(_encode(key, attestations[key])) + "\n")
            rows += 1
    return rows


def read(path: Path) -> tuple[dict[str, Attestation], IdentityMode]:
    """Load stored evidence, applying the recorded identity mode."""

    path = Path(path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SidecarError(f"cannot read sidecar {path}: {error}") from error
    if not lines:
        raise SidecarError(f"sidecar {path} is empty")
    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError as error:
        raise SidecarError(f"sidecar {path} has no header: {error}") from error
    if header.get("format") != FORMAT:
        raise SidecarError(
            f"sidecar {path} has format {header.get('format')!r}, expected {FORMAT!r}"
        )
    identity_mode = header.get("identity_mode", PORTABLE)
    if identity_mode not in IDENTITY_MODES:
        raise SidecarError(f"sidecar {path} has unknown identity mode {identity_mode!r}")

    attestations: dict[str, Attestation] = {}
    for number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        try:
            key, attestation = _decode(json.loads(line), identity_mode)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise SidecarError(f"sidecar {path} line {number}: {error}") from error
        if key in attestations:
            raise SidecarError(f"sidecar {path} line {number}: duplicate key {key!r}")
        attestations[key] = attestation
    return attestations, identity_mode


def validate(
    attestations: Mapping[str, Attestation],
    live: Mapping[str, FileStat],
    *,
    identity_mode: IdentityMode = PORTABLE,
) -> ValidationReport:
    """Compare stored subjects against a fresh scan of the same root."""

    matched: list[str] = []
    drifted: list[str] = []
    missing: list[str] = []
    for key in sorted(attestations):
        actual = live.get(key)
        if actual is None:
            missing.append(key)
        elif _subject_matches(attestations[key].subject, actual):
            matched.append(key)
        else:
            drifted.append(key)
    unseen = sorted(set(live) - set(attestations))
    return ValidationReport(
        tuple(matched), tuple(drifted), tuple(missing), tuple(unseen), identity_mode
    )


def load_validated(
    path: Path,
    live: Mapping[str, FileStat],
) -> tuple[dict[str, Attestation], ValidationReport]:
    """Load and refuse to return evidence that no longer fits the corpus."""

    attestations, identity_mode = read(path)
    report = validate(attestations, live, identity_mode=identity_mode)
    if not report.usable:
        raise SidecarError(
            f"sidecar {path} no longer describes the corpus: {report.summary()}. "
            "Reseed it with --seed-baselines."
        )
    return attestations, report


def restrict(
    attestations: Mapping[str, Attestation], keys: Iterable[str]
) -> dict[str, Attestation]:
    """Return the subset of evidence covering the given canonical keys."""

    wanted = set(keys)
    return {key: value for key, value in attestations.items() if key in wanted}


def _subject_matches(expected: FileStat, actual: FileStat) -> bool:
    # Mirrors verifier._matches_expected_stat: identity participates only when
    # the stored subject carries one.
    if expected.kind is not actual.kind:
        return False
    if expected.size != actual.size or expected.mtime_ns != actual.mtime_ns:
        return False
    return expected.file_identity is None or expected.file_identity == actual.file_identity


def _encode(key: str, attestation: Attestation) -> dict[str, object]:
    subject = attestation.subject
    content = attestation.content
    identity = subject.file_identity
    return {
        "key": key,
        "kind": subject.kind.value,
        "size": subject.size,
        "mtime_ns": subject.mtime_ns,
        "nlink": subject.nlink,
        "attributes": subject.metadata.attributes,
        "created_ns": subject.metadata.created_ns,
        "volume_serial": None if identity is None else identity.volume_serial,
        "file_index": None if identity is None else identity.file_index,
        "algorithm": content.algorithm,
        "digest": content.digest.hex(),
        "provenance": content.provenance.value,
        "observed_at": content.observed_at.isoformat(),
    }


def _decode(row: Mapping[str, object], identity_mode: IdentityMode) -> tuple[str, Attestation]:
    key = str(row["key"])
    serial = row.get("volume_serial")
    index = row.get("file_index")
    identity = (
        FileIdentity(str(serial), int(index))
        if identity_mode == BOUND and serial is not None and index is not None
        else None
    )
    subject = FileStat(
        kind=EntryKind(str(row["kind"])),
        size=int(row["size"]),
        mtime_ns=int(row["mtime_ns"]),
        file_identity=identity,
        nlink=int(row["nlink"]),
        metadata=MetadataSnapshot(
            attributes=int(row["attributes"]),
            created_ns=None if row.get("created_ns") is None else int(row["created_ns"]),
        ),
    )
    content = ContentEvidence(
        algorithm="xxh3_128",
        digest=bytes.fromhex(str(row["digest"])),
        size=subject.size,
        provenance=Provenance(str(row["provenance"])),
        observed_at=datetime.fromisoformat(str(row["observed_at"])),
    )
    return key, Attestation(content=content, subject=subject)
