"""Drive the verifier's integrity entry points over a real root.

Selections are built from a fresh scan rather than from ledger rows, and prior
evidence comes from one of three sources: primed in memory, loaded from a
sidecar, or synthesized. Only the first two exercise the ``VERIFIED`` path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Mapping

from xxhash import xxh3_128

from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    HasherFactory,
    Provenance,
)
from namisync.core.events import Progress
from namisync.core.execution import PublishedCopyEvidence
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityRunResult,
    IntegritySelection,
    IntegritySelectionItem,
    InventoryState,
    PostCopyCandidate,
    PostCopyRecordIdentity,
    PostCopySelection,
    VerifierContext,
)
from namisync.core.models import FileStat, IgnoreSet, Root
from namisync.core.pathing import normalize_relative_path
from namisync.modules.scanner import scan as scan_root
from namisync.modules.verifier import (
    WindowsUnbufferedReader,
    baseline,
    rebaseline,
    verify,
    verify_post_copy,
)

from . import sidecar
from .seams import (
    CapturingIntegrityRecorder,
    ReadSample,
    RigClock,
    Tape,
    TappedReader,
)


_LOCATION_ID = "rig-location"
_SCOPE_TOKEN = "rig-scope"
_SYNTHETIC_DIGEST = bytes(range(16))

RUNNERS = {
    IntegrityMode.BASELINE: baseline,
    IntegrityMode.VERIFY: verify,
    IntegrityMode.REBASELINE: rebaseline,
}


class VerifierRigError(RuntimeError):
    """The rig could not build a usable integrity selection."""


@dataclass(frozen=True, slots=True)
class VerifierRun:
    """One measured integrity pass plus its recorded commands."""

    result: IntegrityRunResult
    mode: IntegrityMode
    tape: Tape
    recorder: CapturingIntegrityRecorder
    read_samples: tuple[ReadSample, ...]
    scan_seconds: float
    run_seconds: float
    items: int

    @property
    def bytes_done(self) -> int:
        progress = self.tape.of_type(Progress)
        return progress[-1][1].bytes_done if progress else 0

    @property
    def results(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for outcome in self.result.outcomes:
            counts[outcome.result.value] = counts.get(outcome.result.value, 0) + 1
        return counts

    @property
    def throughput_mib_s(self) -> float:
        if self.run_seconds <= 0:
            return 0.0
        return self.bytes_done / (1024**2) / self.run_seconds

    @property
    def read_seconds(self) -> float:
        return sum(sample.read_seconds for sample in self.read_samples)

    @property
    def open_seconds(self) -> float:
        return sum(sample.open_seconds for sample in self.read_samples)

    def attestations(self) -> dict[str, Attestation]:
        return self.recorder.attestations()


def scan_stats(
    root: Path, *, ignores: IgnoreSet | None = None, tape: Tape | None = None
) -> tuple[dict[str, FileStat], dict[str, str], float]:
    """Return canonical-key stats and display paths from one fresh scan."""

    tape = tape or Tape()
    started = perf_counter()
    result = scan_root(
        Root(str(Path(root).resolve()), "corpus"), ignores or IgnoreSet(), tape.context()
    )
    seconds = perf_counter() - started
    stats = {record.rel_path_key: record.stat for record in result.files}
    display = {record.rel_path_key: record.rel_path for record in result.files}
    return stats, display, seconds


def build_selection(
    root: Path,
    stats: Mapping[str, FileStat],
    display: Mapping[str, str],
    *,
    baselines: Mapping[str, Attestation] | None = None,
) -> IntegritySelection:
    """Build a ledger-free selection covering every scanned file."""

    if not stats:
        raise VerifierRigError("the corpus scan produced no files to verify")
    evidence = baselines or {}
    items = tuple(
        IntegritySelectionItem(
            item_id=f"rig:{key}",
            row_id=f"rig-row-{number}",
            location_id=_LOCATION_ID,
            root=Path(root).resolve(),
            rel_path_key=key,
            display_path=display[key],
            expected_state=InventoryState.PRESENT,
            expected_stat=stats[key],
            baseline=evidence.get(key),
            scope_token=_SCOPE_TOKEN,
        )
        for number, key in enumerate(sorted(stats))
    )
    return IntegritySelection(items)


def synthetic_baselines(stats: Mapping[str, FileStat]) -> dict[str, Attestation]:
    """Build well-formed evidence with a deliberately wrong digest.

    The digest is compared only after the full read-and-hash loop, so this
    reaches every byte of the pipeline. It settles as ``MISMATCHED``, which
    skips the evidence construction and recorder call that a real ``VERIFIED``
    settlement performs.
    """

    observed_at = RigClock().now()
    return {
        key: Attestation(
            content=ContentEvidence(
                algorithm="xxh3_128",
                digest=_SYNTHETIC_DIGEST,
                size=stat.size,
                provenance=Provenance.VERIFY_ATTESTED,
                observed_at=observed_at,
            ),
            subject=stat,
        )
        for key, stat in stats.items()
    }


def run_verifier(
    root: Path,
    mode: IntegrityMode = IntegrityMode.VERIFY,
    *,
    baselines: Mapping[str, Attestation] | None = None,
    ignores: IgnoreSet | None = None,
    chunk_size: int = 4 * 1024 * 1024,
    hasher_factory: HasherFactory = xxh3_128,
    tap_reader: bool = True,
) -> VerifierRun:
    """Run one integrity pass over a real root and measure it."""

    tape = Tape()
    stats, display, scan_seconds = scan_stats(root, ignores=ignores, tape=tape)
    selection = build_selection(root, stats, display, baselines=baselines)

    reader = _reader(tap_reader)
    context = VerifierContext(
        run=tape.context(),
        clock=RigClock(),
        hasher_factory=hasher_factory,
        chunk_size=chunk_size,
    )
    recorder = CapturingIntegrityRecorder()

    started = perf_counter()
    result = RUNNERS[mode](selection, context, recorder, reader)
    run_seconds = perf_counter() - started

    return VerifierRun(
        result=result,
        mode=mode,
        tape=tape,
        recorder=recorder,
        read_samples=tuple(reader.samples) if isinstance(reader, TappedReader) else (),
        scan_seconds=scan_seconds,
        run_seconds=run_seconds,
        items=len(selection.items),
    )


def prime_baselines(
    root: Path,
    *,
    ignores: IgnoreSet | None = None,
    chunk_size: int = 4 * 1024 * 1024,
    hasher_factory: HasherFactory = xxh3_128,
) -> dict[str, Attestation]:
    """Produce real evidence with one in-process baseline pass."""

    run = run_verifier(
        root,
        IntegrityMode.BASELINE,
        ignores=ignores,
        chunk_size=chunk_size,
        hasher_factory=hasher_factory,
        tap_reader=False,
    )
    evidence = run.attestations()
    if not evidence:
        raise VerifierRigError(
            "the baseline pass recorded no evidence; the corpus may be unreadable"
        )
    return evidence


def load_baselines(
    path: Path, stats: Mapping[str, FileStat]
) -> tuple[dict[str, Attestation], sidecar.ValidationReport]:
    """Load sidecar evidence and refuse anything that no longer fits."""

    attestations, report = sidecar.load_validated(path, stats)
    return sidecar.restrict(attestations, stats), report


def post_copy_selection(
    target_root: Path,
    published: Mapping[str, PublishedCopyEvidence],
    paths: Mapping[str, str],
) -> PostCopySelection:
    """Turn an executor run's published evidence into readback candidates."""

    candidates: list[PostCopyCandidate] = []
    for op_id, evidence in published.items():
        display_path = paths[op_id]
        identity = evidence.recorded_identity
        candidates.append(
            PostCopyCandidate(
                item_id=f"rig-post:{op_id}",
                root=Path(target_root).resolve(),
                display_path=display_path,
                expected_stat=evidence.attestation.subject,
                copy_attestation=evidence.attestation,
                recorded_identity=None
                if identity is None
                else PostCopyRecordIdentity(
                    row_id=identity.row_id,
                    location_id=identity.location_id,
                    scope_token=identity.scope_token,
                    rel_path_key=normalize_relative_path(display_path),
                ),
            )
        )
    return PostCopySelection(tuple(candidates))


def run_post_copy(
    selection: PostCopySelection,
    *,
    chunk_size: int = 4 * 1024 * 1024,
    hasher_factory: HasherFactory = xxh3_128,
    tap_reader: bool = True,
) -> VerifierRun:
    """Read back published targets exactly as the sync workflow would.

    Each candidate carries its own root, so no root argument is needed.
    """

    tape = Tape()
    reader = _reader(tap_reader)
    context = VerifierContext(
        run=tape.context(),
        clock=RigClock(),
        hasher_factory=hasher_factory,
        chunk_size=chunk_size,
    )
    recorder = CapturingIntegrityRecorder()

    started = perf_counter()
    result = verify_post_copy(selection, context, recorder, reader)
    run_seconds = perf_counter() - started

    return VerifierRun(
        result=result,
        mode=IntegrityMode.VERIFY,
        tape=tape,
        recorder=recorder,
        read_samples=tuple(reader.samples) if isinstance(reader, TappedReader) else (),
        scan_seconds=0.0,
        run_seconds=run_seconds,
        items=len(selection.candidates),
    )


def _reader(tap: bool) -> TappedReader | WindowsUnbufferedReader:
    inner = WindowsUnbufferedReader()
    return TappedReader(inner) if tap else inner
