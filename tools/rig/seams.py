"""Ledger-free collaborators and measurement taps for the module rig.

Nothing here implements domain policy. Each class either satisfies a seam the
product normally fills from ``db``/``workflows``, or decorates a real
collaborator to sample what it did.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import BinaryIO, Callable, Iterator

from namisync.core.evidence import Attestation
from namisync.core.execution import (
    CopyDigest,
    RecordedCopyIdentity,
    RunId,
)
from namisync.core.integrity import (
    IntegrityRecordCommand,
    ReadStrategy,
    RecordDisposition,
)
from namisync.core.models import FileStat
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import OpId, Plan
from namisync.core.session import RunContext
from namisync.modules.executor import CopyPipelineMetrics


class RigClock:
    """Real UTC clock; the rig measures what production pays for time."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class Tape:
    """Timestamped event sink standing in for the dispatcher's fan-out."""

    def __init__(self) -> None:
        self.events: list[tuple[float, object]] = []
        self.checkpoints = 0

    def emit(self, event: object) -> None:
        self.events.append((perf_counter(), event))

    def checkpoint(self) -> None:
        self.checkpoints += 1

    def context(self) -> RunContext:
        return RunContext(self.emit, self.checkpoint)

    def of_type(self, event_type: type) -> tuple[tuple[float, object], ...]:
        return tuple(
            (stamp, event)
            for stamp, event in self.events
            if isinstance(event, event_type)
        )


class LedgerlessRecorder:
    """Executor ``Recorder`` that mints contract-valid identities in memory.

    ``record_copied`` and friends receive only an ``OpId``, but ``ExecutionSet``
    validates that each returned identity carries the run's scope token and the
    operation's canonical target path. The plan supplies that mapping so the
    resulting ``published_evidence`` stays reusable as verifier input and
    recording stays ``OK`` rather than degrading.
    """

    def __init__(
        self, plan: Plan, run_id: RunId, *, location_id: str = "rig-target"
    ) -> None:
        self._paths = {
            operation.op_id: normalize_relative_path(operation.target_rel_path)
            for operation in plan.operations
        }
        self._run_id = str(run_id)
        self._location_id = location_id
        self.calls: dict[str, int] = {}
        self.flushes = 0

    def _count(self, name: str) -> None:
        self.calls[name] = self.calls.get(name, 0) + 1

    def _identity(self, op: OpId) -> RecordedCopyIdentity:
        try:
            rel_path_key = self._paths[op]
        except KeyError:  # pragma: no cover - defensive
            raise KeyError(f"operation {op!r} is not part of the rig plan") from None
        return RecordedCopyIdentity(
            row_id=f"rig-row-{op}",
            location_id=self._location_id,
            scope_token=self._run_id,
            rel_path_key=rel_path_key,
        )

    def flush(self) -> None:
        self.flushes += 1

    def record_copied(self, op: OpId, attestation: Attestation) -> RecordedCopyIdentity:
        del attestation
        self._count("copied")
        return self._identity(op)

    def record_updated(self, op: OpId, attestation: Attestation) -> RecordedCopyIdentity:
        del attestation
        self._count("updated")
        return self._identity(op)

    def record_move_updated(
        self, op: OpId, attestation: Attestation
    ) -> RecordedCopyIdentity:
        del attestation
        self._count("move_updated")
        return self._identity(op)

    def record_moved(self, op: OpId, target: FileStat) -> None:
        del op, target
        self._count("moved")

    def record_recased(self, op: OpId, target: FileStat) -> None:
        del op, target
        self._count("recased")

    def record_mkdir(self, op: OpId, target: FileStat) -> None:
        del op, target
        self._count("mkdir")

    def record_trashed(
        self, op: OpId, trash_relative_path: str, target: FileStat
    ) -> None:
        del op, trash_relative_path, target
        self._count("trashed")

    def record_deleted(self, op: OpId, prior: FileStat) -> None:
        del op, prior
        self._count("deleted")

    def record_noop(self, op: OpId, source: FileStat, target: FileStat) -> None:
        del op, source, target
        self._count("noop")


class CapturingIntegrityRecorder:
    """Verifier ``IntegrityRecorder`` that retains every conditional command.

    The retained ``attestation`` values are how the rig seeds later verify
    passes without a ledger.
    """

    def __init__(
        self, disposition: RecordDisposition = RecordDisposition.APPLIED
    ) -> None:
        self.disposition = disposition
        self.commands: list[IntegrityRecordCommand] = []

    def record_integrity(self, command: IntegrityRecordCommand) -> RecordDisposition:
        self.commands.append(command)
        return self.disposition

    def attestations(self) -> dict[str, Attestation]:
        """Return the newest attestation per canonical path key."""

        return {
            command.rel_path_key: command.attestation for command in self.commands
        }


@dataclass(frozen=True, slots=True)
class CopySample:
    """One completed ``CopyBackend.copy`` call."""

    seconds: float
    chunk_size: int
    size: int
    metrics: CopyPipelineMetrics | None


class TappedCopyBackend:
    """Sample the executor's opt-in diagnostics once per copy.

    ``NativeCopyBackend.last_metrics`` only retains the most recent copy, so a
    single read after the run would report whichever file happened to finish
    last. Wrapping the injected backend attributes one snapshot per operation.
    """

    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.samples: list[CopySample] = []

    def copy(
        self,
        source: BinaryIO,
        target: BinaryIO,
        *,
        chunk_size: int,
        checkpoint: Callable[[], None],
        on_chunk: Callable[[int], None],
    ) -> CopyDigest:
        started = perf_counter()
        digest = self._inner.copy(
            source,
            target,
            chunk_size=chunk_size,
            checkpoint=checkpoint,
            on_chunk=on_chunk,
        )
        elapsed = perf_counter() - started
        self.samples.append(
            CopySample(
                seconds=elapsed,
                chunk_size=chunk_size,
                size=digest.size,
                metrics=getattr(self._inner, "last_metrics", None),
            )
        )
        return digest


@dataclass(slots=True)
class ReadSample:
    """Per-subject read accounting derived from the verifier's reader seam."""

    relative_path: str
    open_seconds: float = 0.0
    read_seconds: float = 0.0
    bytes_read: int = 0
    chunks: int = 0


class _TappedStream:
    def __init__(self, inner: object, sample: ReadSample) -> None:
        self._inner = inner
        self._sample = sample
        self.strategy: ReadStrategy = inner.strategy

    def stat(self) -> FileStat:
        return self._inner.stat()

    def iter_chunks(self, chunk_size: int) -> Iterator[bytes]:
        # Time spent inside the inner generator is read cost. The gap between
        # yields is the caller hashing, and is deliberately not counted here.
        iterator = self._inner.iter_chunks(chunk_size)
        try:
            while True:
                started = perf_counter()
                try:
                    chunk = next(iterator)
                except StopIteration:
                    self._sample.read_seconds += perf_counter() - started
                    return
                self._sample.read_seconds += perf_counter() - started
                self._sample.bytes_read += len(chunk)
                self._sample.chunks += 1
                yield chunk
        finally:
            # The verifier abandons this generator on cancel; close the inner
            # one deterministically rather than waiting for collection.
            close = getattr(iterator, "close", None)
            if close is not None:
                close()


class TappedReader:
    """Decorate a ``VerificationReader`` with per-subject open/read timing.

    The verifier has no diagnostics emitter yet. Until it does, this is the
    external stand-in; it costs one ``perf_counter`` pair per chunk, so use
    ``--no-tap`` when sweeping small chunk sizes.
    """

    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.samples: list[ReadSample] = []

    @contextmanager
    def open(self, root: Path, relative_path: str) -> Iterator[_TappedStream]:
        sample = ReadSample(relative_path)
        self.samples.append(sample)
        started = perf_counter()
        with self._inner.open(root, relative_path) as stream:
            sample.open_seconds = perf_counter() - started
            yield _TappedStream(stream, sample)


class _ConstantHasher:
    """Streaming hasher that consumes bytes and returns a fixed digest."""

    __slots__ = ()

    def update(self, data: bytes) -> None:
        del data

    def digest(self) -> bytes:
        return b"\x00" * 16


def constant_hasher_factory() -> _ConstantHasher:
    """Hasher seam that removes digest cost while preserving control flow.

    Priming baselines with this factory and verifying with it lands on the real
    ``VERIFIED`` path with the hashing removed, so a paired run against
    ``xxh3_128`` isolates hash cost exactly. Valid for the verifier, which reads
    synchronously; misleading for the executor, whose bounded reader/hasher/
    writer pipeline moves its bottleneck when the hasher is stubbed.
    """

    return _ConstantHasher()
