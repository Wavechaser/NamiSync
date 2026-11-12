from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from xxhash import xxh3_128

from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    HasherFactory,
    Provenance,
)
from namisync.core.integrity import (
    IntegrityOutcome,
    IntegrityRecordCommand,
    IntegritySelectionItem,
    InventoryState,
    PostCopyCandidate,
    PostCopyRecordIdentity,
    ReadStrategy,
    RecordDisposition,
    VerificationInvalidationCommand,
    VerifierContext,
)
from namisync.core.models import (
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
)
from namisync.core.pathing import normalize_relative_path, validate_relative_path
from namisync.core.root_authority import (
    RootAuthority,
    current_volume_anchor,
    observe_native_volume,
)
from namisync.core.session import RunContext


_NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _NOW


@dataclass(frozen=True)
class _StreamSpec:
    before: FileStat
    chunks: tuple[bytes, ...]
    after: FileStat | None = None


class _FakeStream:
    strategy = ReadStrategy.WINDOWS_UNBUFFERED

    def __init__(self, spec: _StreamSpec) -> None:
        self._spec = spec
        self._stat_calls = 0

    def stat(self) -> FileStat:
        self._stat_calls += 1
        if self._stat_calls == 1 or self._spec.after is None:
            return self._spec.before
        return self._spec.after

    def iter_chunks(self, chunk_size: int) -> Iterator[bytes]:
        assert chunk_size > 0
        yield from self._spec.chunks


class _FakeReader:
    def __init__(self, entries: dict[str, _StreamSpec | BaseException]) -> None:
        self.entries = {
            validate_relative_path(path): entry for path, entry in entries.items()
        }
        self.opened: list[tuple[Path, str]] = []

    @contextmanager
    def open(self, root: Path, relative_path: str) -> Iterator[_FakeStream]:
        self.opened.append((root, relative_path))
        entry = self.entries[relative_path]
        if isinstance(entry, BaseException):
            raise entry
        yield _FakeStream(entry)


class _Recorder:
    def __init__(
        self,
        disposition: RecordDisposition = RecordDisposition.APPLIED,
        error: Exception | None = None,
    ) -> None:
        self.disposition = disposition
        self.error = error
        self.commands: list[IntegrityRecordCommand] = []
        self.invalidation_commands: list[VerificationInvalidationCommand] = []

    def record_integrity(self, command: IntegrityRecordCommand) -> RecordDisposition:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return self.disposition

    def record_verification_invalidation(
        self, command: VerificationInvalidationCommand
    ) -> RecordDisposition:
        self.invalidation_commands.append(command)
        if self.error is not None:
            raise self.error
        return self.disposition


def _stat(
    *,
    size: int = 3,
    mtime_ns: int = 100,
    identity: FileIdentity | None = FileIdentity("A1B2C3D4", 7),
) -> FileStat:
    return FileStat(
        kind=EntryKind.FILE,
        size=size,
        mtime_ns=mtime_ns,
        file_identity=identity,
        nlink=1,
        metadata=MetadataSnapshot(attributes=0, created_ns=50),
    )


def _attestation(
    data: bytes,
    subject: FileStat,
    provenance: Provenance = Provenance.VERIFY_ATTESTED,
) -> Attestation:
    return Attestation(
        content=ContentEvidence(
            algorithm="xxh3_128",
            digest=xxh3_128(data).digest(),
            size=len(data),
            provenance=provenance,
            observed_at=_NOW,
        ),
        subject=subject,
    )


def _item(
    root: Path,
    *,
    number: int = 1,
    path: str | None = None,
    location_id: str = "location-1",
    expected_state: InventoryState = InventoryState.PRESENT,
    expected_stat: FileStat | None = None,
    baseline_evidence: Attestation | None | object = ...,
    reappeared: bool = False,
) -> IntegritySelectionItem:
    display_path = path or f"Folder\\file-{number}.bin"
    stat = expected_stat or _stat()
    if baseline_evidence is ...:
        baseline_evidence = _attestation(b"abc", stat)
    return IntegritySelectionItem(
        item_id=f"item-{number}",
        row_id=f"row-{number}",
        location_id=location_id,
        root=root,
        rel_path_key=normalize_relative_path(display_path),
        display_path=display_path,
        expected_state=expected_state,
        expected_stat=stat if expected_state is InventoryState.PRESENT else None,
        baseline=baseline_evidence,
        scope_token="scope-1",
        reappeared_at=_NOW if reappeared else None,
    )


def _post_copy_candidate(
    root: Path,
    *,
    number: int = 1,
    path: str | None = None,
    expected_stat: FileStat | None = None,
    recorded: bool = True,
) -> PostCopyCandidate:
    display_path = path or f"Folder\\copied-{number}.bin"
    stat = expected_stat or _stat()
    identity = (
        PostCopyRecordIdentity(
            row_id=f"row-{number}",
            location_id="location-1",
            scope_token="scope-1",
            rel_path_key=normalize_relative_path(display_path),
        )
        if recorded
        else None
    )
    return PostCopyCandidate(
        item_id=f"copy-{number}",
        root=root,
        display_path=display_path,
        expected_stat=stat,
        copy_attestation=_attestation(
            b"abc", stat, Provenance.COPY_ATTESTED
        ),
        recorded_identity=identity,
    )


def _context(
    events: list[object],
    checkpoint=lambda: None,
    monotonic=lambda: 0.0,
    hasher_factory: HasherFactory = xxh3_128,
) -> VerifierContext:
    return VerifierContext(
        run=RunContext(emit=events.append, checkpoint=checkpoint),
        clock=_Clock(),
        hasher_factory=hasher_factory,
        monotonic=monotonic,
        chunk_size=1,
        progress_interval_seconds=0.1,
    )


def _native_context(events: list[object], root: Path) -> VerifierContext:
    volume = observe_native_volume(root)
    return replace(
        _context(events),
        root_authority=RootAuthority(
            logical_root=str(root),
            reviewed_anchor=current_volume_anchor(root),
            expected_volume_id=volume.volume_id,
        ),
    )


def _integrity_events(events: list[object]) -> list[IntegrityOutcome]:
    return [event for event in events if isinstance(event, IntegrityOutcome)]
