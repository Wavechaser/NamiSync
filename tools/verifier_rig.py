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
    RecordingStatus,
)
from namisync.core.events import Progress
from namisync.core.execution import PublishedCopyEvidence
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityResult,
    IntegrityRunResult,
    IntegritySelection,
    IntegritySelectionItem,
    InventoryState,
    PostCopyCandidate,
    PostCopyRecordIdentity,
    PostCopySelection,
    RecordDisposition,
    VerifierContext,
    matches_expected_stat,
)
from namisync.core.models import FileStat, IgnoreSet, Root, ScanWarningCode
from namisync.core.pathing import normalize_relative_path
from namisync.core.root_authority import (
    RootAuthority,
    current_volume_anchor,
    observe_native_volume,
)
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
    AuthorityBoundTappedReader,
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


def _root_authority(root: Path) -> RootAuthority:
    logical_root = Path(root).resolve()
    volume = observe_native_volume(logical_root)
    return RootAuthority(
        str(logical_root),
        current_volume_anchor(logical_root),
        volume.volume_id,
    )


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
    expected_item_ids: frozenset[str]
    expected_bytes: int
    fixture: tuple[tuple[str, FileStat], ...]

    @property
    def items(self) -> int:
        return len(self.expected_item_ids)

    @property
    def bytes_done(self) -> int:
        progress = self.tape.of_type(Progress)
        return progress[-1].bytes_done if progress else 0

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
    if result.unsupported:
        raise VerifierRigError(
            f"the corpus scan found {len(result.unsupported)} unsupported entries"
        )
    collisions = tuple(
        warning
        for warning in result.warnings
        if warning.code is ScanWarningCode.CASE_COLLISION
    )
    if collisions:
        raise VerifierRigError(
            f"the corpus scan found {len(collisions)} canonical path collisions"
        )
    if not result.complete:
        raise VerifierRigError("the corpus scan was incomplete")
    stats = {record.rel_path_key: record.stat for record in result.files}
    display = {record.rel_path_key: record.rel_path for record in result.files}
    if (
        len(stats) != len(result.files)
        or len(display) != len(result.files)
        or stats.keys() != display.keys()
    ):
        raise VerifierRigError(
            "the corpus scan did not preserve one canonical key per file"
        )
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
        root_authority=_root_authority(root),
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
        expected_item_ids=frozenset(item.item_id for item in selection.items),
        expected_bytes=sum(item.expected_stat.size for item in selection.items),
        fixture=tuple(sorted(stats.items())),
    )


def require_fixture(
    run: VerifierRun,
    expected: Mapping[str, FileStat],
    *,
    portable: bool,
) -> None:
    """Reject a measured scan that no longer represents the batch fixture."""

    actual = dict(run.fixture)
    if set(actual) != set(expected):
        raise VerifierRigError(
            "verifier corpus membership changed during the benchmark batch"
        )
    if portable:
        stable = all(
            matches_expected_stat(expected[key], actual[key]) for key in expected
        )
    else:
        stable = actual == dict(expected)
    if not stable:
        raise VerifierRigError(
            "verifier corpus file stats changed during the benchmark batch"
        )


def content_evidence(
    run: VerifierRun,
) -> dict[str, tuple[str, bytes, int]]:
    """Return complete content evidence for one baselining sample."""

    evidence = run.attestations()
    fixture_keys = {key for key, _ in run.fixture}
    if set(evidence) != fixture_keys:
        raise VerifierRigError(
            "verifier baseline evidence did not cover the measured fixture"
        )
    return {
        key: (
            attestation.content.algorithm,
            attestation.content.digest,
            attestation.content.size,
        )
        for key, attestation in evidence.items()
    }


def require_stable_content_evidence(
    reference: Mapping[str, tuple[str, bytes, int]],
    sample: VerifierRun,
) -> None:
    """Reject same-stat content drift between baselining samples."""

    if content_evidence(sample) != dict(reference):
        raise VerifierRigError(
            "verifier corpus content changed during the benchmark batch"
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
    outcomes = run.result.outcomes
    commands = run.recorder.commands
    successful = tuple(
        outcome
        for outcome in outcomes
        if outcome.result is IntegrityResult.BASELINED
        and outcome.record_disposition is RecordDisposition.APPLIED
        and outcome.recording is RecordingStatus.OK
    )
    outcome_ids = {outcome.item_id for outcome in outcomes}
    command_ids = {command.item_id for command in commands}
    command_keys = {command.rel_path_key for command in commands}
    expected = run.items
    progress = run.tape.of_type(Progress)
    complete_progress = bool(progress) and (
        progress[-1].items_done == expected
        and progress[-1].items_total == expected
        and progress[-1].bytes_done == run.expected_bytes
        and progress[-1].bytes_total == run.expected_bytes
    )
    if not (
        expected > 0
        and run.result.recording is RecordingStatus.OK
        and complete_progress
        and len(outcomes) == expected
        and outcome_ids == run.expected_item_ids
        and len(successful) == expected
        and len(commands) == expected
        and command_ids == run.expected_item_ids
        and len(evidence) == len(command_keys) == expected
        and set(evidence) == command_keys
    ):
        raise VerifierRigError(
            "the baseline pass did not record one applied attestation per scanned "
            f"file (expected {expected}, outcomes {len(outcomes)}, "
            f"applied {len(successful)}, commands {len(commands)}, "
            f"evidence {len(evidence)})"
        )
    return evidence


def load_baselines(
    path: Path, stats: Mapping[str, FileStat]
) -> tuple[dict[str, Attestation], sidecar.ValidationReport]:
    """Load sidecar evidence and refuse anything that no longer fits."""

    attestations, report = sidecar.load_validated(path, stats)
    return attestations, report


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
    roots = {Path(candidate.root).resolve() for candidate in selection.candidates}
    if len(roots) != 1:
        raise VerifierRigError(
            "post-copy verification requires one non-empty exact target root"
        )
    context = VerifierContext(
        run=tape.context(),
        clock=RigClock(),
        hasher_factory=hasher_factory,
        chunk_size=chunk_size,
        root_authority=_root_authority(roots.pop()),
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
        expected_item_ids=frozenset(
            candidate.item_id for candidate in selection.candidates
        ),
        expected_bytes=sum(
            candidate.expected_stat.size for candidate in selection.candidates
        ),
        fixture=tuple(
            sorted(
                (
                    (candidate.display_path, candidate.expected_stat)
                    for candidate in selection.candidates
                ),
                key=lambda item: item[0],
            )
        ),
    )


def _reader(tap: bool) -> TappedReader | WindowsUnbufferedReader:
    inner = WindowsUnbufferedReader()
    return AuthorityBoundTappedReader(inner) if tap else inner
