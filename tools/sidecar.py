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
import os
from pathlib import Path
import tempfile
from typing import Mapping

from namisync.core.evidence import Attestation, ContentEvidence, Provenance
from namisync.core.integrity import matches_expected_stat
from namisync.core.models import EntryKind, FileIdentity, FileStat, MetadataSnapshot
from namisync.core.root_authority import is_reparse_stat


IdentityMode = str
BOUND: IdentityMode = "bound"
PORTABLE: IdentityMode = "portable"
IDENTITY_MODES = (BOUND, PORTABLE)

FORMAT = "namisync-rig-baseline-1"
_HEADER_FIELDS = frozenset({"format", "identity_mode"})
_ROW_FIELDS = frozenset(
    {
        "key",
        "kind",
        "size",
        "mtime_ns",
        "nlink",
        "attributes",
        "created_ns",
        "volume_serial",
        "file_index",
        "algorithm",
        "digest",
        "provenance",
        "observed_at",
    }
)


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
    replace: bool = False,
    expected_identity: tuple[int, int] | None = None,
) -> int:
    """Write one row per canonical path key; return the row count.

    ``bound`` requires and preserves NTFS file identity. ``portable`` drops
    identity on read so the corpus survives being moved or restored, at the
    cost of one tuple comparison of fidelity against production.
    """

    if identity_mode not in IDENTITY_MODES:
        raise ValueError(f"unknown identity mode: {identity_mode!r}")
    path = Path(path)
    encoded: list[str] = []
    for key in sorted(attestations):
        attestation = attestations[key]
        if identity_mode == BOUND and attestation.subject.file_identity is None:
            raise SidecarError(
                f"cannot write bound sidecar {path}: {key!r} has no file identity"
            )
        encoded.append(json.dumps(_encode(key, attestation)))

    if expected_identity is not None and not replace:
        raise ValueError("expected sidecar identity requires replace=True")
    current_identity = _sidecar_identity(path)
    if current_identity is not None:
        if not replace:
            raise SidecarError(
                f"refusing to replace existing sidecar without --replace-sidecar: {path}"
            )
        if expected_identity is None:
            raise SidecarError(
                f"sidecar appeared after publication was authorized: {path}"
            )
        if current_identity != expected_identity:
            raise SidecarError(f"sidecar was replaced before publication: {path}")
    elif expected_identity is not None:
        raise SidecarError(f"sidecar disappeared before publication: {path}")

    temporary: Path | None = None
    descriptor: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = None
            handle.write(
                json.dumps({"format": FORMAT, "identity_mode": identity_mode})
                + "\n"
            )
            for row in encoded:
                handle.write(row + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        current_identity = _sidecar_identity(path)
        if expected_identity is None:
            if current_identity is not None:
                raise SidecarError(
                    f"sidecar appeared before publication: {path}"
                )
            os.rename(temporary, path)
        else:
            if current_identity != expected_identity:
                raise SidecarError(
                    f"sidecar was replaced before publication: {path}"
                )
            os.replace(temporary, path)
        temporary = None
    except SidecarError:
        raise
    except OSError as error:
        raise SidecarError(f"cannot write sidecar {path}: {error}") from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return len(encoded)


def _sidecar_identity(path: Path) -> tuple[int, int] | None:
    try:
        details = os.lstat(path)
    except FileNotFoundError:
        return None
    if is_reparse_stat(details) or not path.is_file():
        raise SidecarError(f"existing sidecar must be an ordinary file: {path}")
    if details.st_nlink != 1:
        raise SidecarError(
            f"existing sidecar must be a single-link file: {path}"
        )
    return details.st_dev, details.st_ino


def read(path: Path) -> tuple[dict[str, Attestation], IdentityMode]:
    """Load stored evidence, applying the recorded identity mode."""

    path = Path(path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise SidecarError(f"cannot read sidecar {path}: {error}") from error
    if not lines:
        raise SidecarError(f"sidecar {path} is empty")
    try:
        header = json.loads(lines[0], object_pairs_hook=_strict_object)
    except (json.JSONDecodeError, ValueError) as error:
        raise SidecarError(f"sidecar {path} has no header: {error}") from error
    if not isinstance(header, dict):
        raise SidecarError(f"sidecar {path} header must be a JSON object")
    if set(header) != _HEADER_FIELDS:
        raise SidecarError(
            f"sidecar {path} header must contain only format and identity_mode"
        )
    if header["format"] != FORMAT:
        raise SidecarError(
            f"sidecar {path} has format {header['format']!r}, expected {FORMAT!r}"
        )
    identity_mode = header["identity_mode"]
    if identity_mode not in IDENTITY_MODES:
        raise SidecarError(f"sidecar {path} has unknown identity mode {identity_mode!r}")

    attestations: dict[str, Attestation] = {}
    for number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            raise SidecarError(f"sidecar {path} line {number}: row is empty")
        try:
            row = json.loads(line, object_pairs_hook=_strict_object)
            if not isinstance(row, dict):
                raise TypeError("row must be a JSON object")
            key, attestation = _decode(row, identity_mode)
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
        elif matches_expected_stat(attestations[key].subject, actual):
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


def _decode(
    row: Mapping[str, object], identity_mode: IdentityMode
) -> tuple[str, Attestation]:
    if set(row) != _ROW_FIELDS:
        raise ValueError("row fields do not match the sidecar schema")
    key = _string(row, "key")
    if not key:
        raise ValueError("key must be non-empty")
    serial = _optional_string(row, "volume_serial")
    index = _optional_int(row, "file_index")
    if (serial is None) != (index is None):
        raise ValueError("file identity must include both volume_serial and file_index")
    if identity_mode == BOUND and serial is None:
        raise ValueError("bound evidence requires file identity")
    stored_identity = (
        None if serial is None or index is None else FileIdentity(serial, index)
    )
    identity = stored_identity if identity_mode == BOUND else None
    subject = FileStat(
        kind=EntryKind(_string(row, "kind")),
        size=_integer(row, "size"),
        mtime_ns=_integer(row, "mtime_ns"),
        file_identity=identity,
        nlink=_integer(row, "nlink"),
        metadata=MetadataSnapshot(
            attributes=_integer(row, "attributes"),
            created_ns=_optional_int(row, "created_ns"),
        ),
    )
    algorithm = _string(row, "algorithm")
    if algorithm != "xxh3_128":
        raise ValueError(f"unsupported content algorithm {algorithm!r}")
    content = ContentEvidence(
        algorithm=algorithm,
        digest=bytes.fromhex(_string(row, "digest")),
        size=subject.size,
        provenance=Provenance(_string(row, "provenance")),
        observed_at=datetime.fromisoformat(_string(row, "observed_at")),
    )
    return key, Attestation(content=content, subject=subject)


def _string(row: Mapping[str, object], field: str) -> str:
    value = row[field]
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    return value


def _integer(row: Mapping[str, object], field: str) -> int:
    value = row[field]
    if type(value) is not int:
        raise TypeError(f"{field} must be an integer")
    return value


def _optional_string(row: Mapping[str, object], field: str) -> str | None:
    value = row[field]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string or null")
    return value


def _optional_int(row: Mapping[str, object], field: str) -> int | None:
    value = row[field]
    if value is None:
        return None
    if type(value) is not int:
        raise TypeError(f"{field} must be an integer or null")
    return value


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON field {key!r}")
        value[key] = item
    return value
