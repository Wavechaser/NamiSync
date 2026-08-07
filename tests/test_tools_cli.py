from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    Outcome,
    Provenance,
    RecordingStatus,
)
from namisync.core.events import ItemOutcome, Progress
from namisync.core.execution import (
    ExecutionSet,
    PublishedCopyEvidence,
    RecordedCopyIdentity,
    validated_run_id,
)
from namisync.core.integrity import IntegrityMode, IntegrityResult
from namisync.core.models import EntryKind, FileStat, MetadataSnapshot
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import OperationKind
from namisync.core.session import Disposition, SessionState
from tools import __main__ as tools_cli
from tools.executor_rig import ExecutorRigError
from tools.seams import Tape
from tools.verifier_rig import VerifierRigError


@pytest.mark.parametrize("command", ["verifier", "executor"])
@pytest.mark.parametrize("repeat", ["0", "-1"])
def test_repeat_must_be_positive(command: str, repeat: str) -> None:
    arguments = [command, "root"]
    if command == "executor":
        arguments.append("target")
    arguments.extend(("--repeat", repeat))

    with pytest.raises(SystemExit) as error:
        tools_cli._parser().parse_args(arguments)

    assert error.value.code == 2


def test_verifier_rejects_json_inside_the_corpus(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    report = root / "runs.jsonl"

    result = tools_cli.main(
        ["verifier", str(root), "--mode", "baseline", "--json", str(report)]
    )

    assert result == 2
    assert not report.exists()


def test_verifier_rejects_a_report_hardlink_to_corpus_content(
    tmp_path: Path,
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    victim = root / "data.bin"
    victim.write_bytes(b"keep")
    report = tmp_path / "runs.jsonl"
    os.link(victim, report)

    result = tools_cli.main(
        ["verifier", str(root), "--mode", "baseline", "--json", str(report)]
    )

    assert result == 2
    assert victim.read_bytes() == b"keep"


def test_verifier_rejects_sidecar_overwriting_a_corpus_file(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    victim = root / "data.bin"
    victim.write_bytes(b"keep")

    result = tools_cli.main(
        [
            "verifier",
            str(root),
            "--seed-baselines",
            "--sidecar",
            str(victim),
        ]
    )

    assert result == 2
    assert victim.read_bytes() == b"keep"


def test_verifier_rejects_a_sidecar_hardlink_to_corpus_content(
    tmp_path: Path,
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    victim = root / "data.bin"
    victim.write_bytes(b"keep")
    alias = tmp_path / "baseline.jsonl"
    os.link(victim, alias)

    result = tools_cli.main(
        [
            "verifier",
            str(root),
            "--seed-baselines",
            "--sidecar",
            str(alias),
        ]
    )

    assert result == 2
    assert victim.read_bytes() == b"keep"


def test_verifier_rejects_sidecar_report_collision(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    artifact = tmp_path / "results.jsonl"

    result = tools_cli.main(
        [
            "verifier",
            str(root),
            "--baselines",
            "sidecar",
            "--sidecar",
            str(artifact),
            "--json",
            str(artifact),
        ]
    )

    assert result == 2
    assert not artifact.exists()


@pytest.mark.parametrize("relationship", ["equal", "inside", "contains"])
def test_executor_rejects_template_target_overlap_without_touching_template(
    tmp_path: Path, relationship: str
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    if relationship == "equal":
        template = target = tmp_path / "template"
        template.mkdir()
    elif relationship == "inside":
        target = tmp_path / "target"
        template = target / "template"
        template.mkdir(parents=True)
    else:
        template = tmp_path / "template"
        target = template / "target"
        template.mkdir()
    sentinel = template / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    result = tools_cli.main(
        [
            "executor",
            str(source),
            str(target),
            "--template",
            str(template),
        ]
    )

    assert result == 2
    assert sentinel.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize(
    ("mode", "baselines", "expected"),
    [
        (IntegrityMode.BASELINE, "primed", IntegrityResult.BASELINED),
        (IntegrityMode.REBASELINE, "sidecar", IntegrityResult.BASELINED),
        (IntegrityMode.VERIFY, "primed", IntegrityResult.VERIFIED),
        (IntegrityMode.VERIFY, "sidecar", IntegrityResult.VERIFIED),
        (IntegrityMode.VERIFY, "none", IntegrityResult.BASELINED),
        (IntegrityMode.VERIFY, "synthetic", IntegrityResult.MISMATCHED),
    ],
)
def test_expected_verifier_result_matrix(
    mode: IntegrityMode, baselines: str, expected: IntegrityResult
) -> None:
    assert tools_cli._expected_verifier_result(mode, baselines) is expected


def test_baseline_mode_does_not_resolve_an_ignored_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    monkeypatch.setattr(
        tools_cli.sidecar,
        "sidecar_path_for",
        lambda path: (_ for _ in ()).throw(AssertionError(f"resolved {path}")),
    )
    monkeypatch.setattr(
        tools_cli,
        "run_verifier",
        lambda *args, **kwargs: _verifier_run((IntegrityResult.BASELINED,)),
    )

    result = tools_cli.main(
        ["verifier", str(root), "--mode", "baseline", "--baselines", "sidecar"]
    )

    assert result == 0


@pytest.mark.parametrize("mode", ["baseline", "verify", "rebaseline"])
def test_null_hasher_refuses_a_sidecar_for_every_mode(
    tmp_path: Path, mode: str
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()

    result = tools_cli.main(
        [
            "verifier",
            str(root),
            "--mode",
            mode,
            "--baselines",
            "sidecar",
            "--null-hasher",
        ]
    )

    assert result == 2


def test_null_hasher_uses_the_same_factory_for_priming_and_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    observed: list[object] = []

    def fake_prime(*args: object, **kwargs: object) -> dict:
        observed.append(kwargs["hasher_factory"])
        return {}

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        observed.append(kwargs["hasher_factory"])
        return _verifier_run((IntegrityResult.VERIFIED,))

    monkeypatch.setattr(tools_cli, "prime_baselines", fake_prime)
    monkeypatch.setattr(tools_cli, "run_verifier", fake_run)

    result = tools_cli.main(
        ["verifier", str(root), "--baselines", "primed", "--null-hasher"]
    )

    assert result == 0
    assert observed == [
        tools_cli.constant_hasher_factory,
        tools_cli.constant_hasher_factory,
    ]


def _verifier_run(
    results: tuple[IntegrityResult, ...],
    *,
    recording: RecordingStatus = RecordingStatus.OK,
    complete_progress: bool = True,
    outcome_ids: tuple[str, ...] | None = None,
    items_total: int | None = None,
    progress_bytes: int | None = None,
) -> SimpleNamespace:
    tape = Tape()
    expected_ids = tuple(f"item-{number}" for number in range(len(results)))
    actual_ids = expected_ids if outcome_ids is None else outcome_ids
    expected_bytes = len(results) * 3
    completed = len(results) if complete_progress else max(0, len(results) - 1)
    completed_bytes = (
        completed * 3 if progress_bytes is None else progress_bytes
    )
    tape.emit(
        Progress(
            items_done=completed,
            items_total=len(results) if items_total is None else items_total,
            bytes_done=completed_bytes,
            bytes_total=(
                expected_bytes if progress_bytes is None else progress_bytes
            ),
            current_path=None,
        )
    )
    counts: dict[str, int] = {}
    outcomes = []
    for item_id, result in zip(actual_ids, results, strict=True):
        counts[result.value] = counts.get(result.value, 0) + 1
        outcomes.append(SimpleNamespace(item_id=item_id, result=result))
    return SimpleNamespace(
        items=len(results),
        expected_item_ids=frozenset(expected_ids),
        expected_bytes=expected_bytes,
        result=SimpleNamespace(outcomes=tuple(outcomes), recording=recording),
        results=counts,
        tape=tape,
        bytes_done=completed_bytes,
        scan_seconds=0.0,
        run_seconds=1.0,
        throughput_mib_s=0.0,
        open_seconds=0.0,
        read_seconds=0.0,
    )


def test_synthetic_mismatch_is_an_accepted_measurement() -> None:
    run = _verifier_run((IntegrityResult.MISMATCHED, IntegrityResult.MISMATCHED))

    tools_cli._validate_verifier_run(run, IntegrityResult.MISMATCHED)


@pytest.mark.parametrize(
    "run",
    [
        _verifier_run((IntegrityResult.VERIFIED, IntegrityResult.ERROR)),
        _verifier_run(
            (IntegrityResult.VERIFIED,), recording=RecordingStatus.DEGRADED
        ),
        _verifier_run((IntegrityResult.VERIFIED,), complete_progress=False),
        _verifier_run(
            (IntegrityResult.VERIFIED, IntegrityResult.VERIFIED),
            outcome_ids=("item-0", "item-0"),
        ),
        _verifier_run((IntegrityResult.VERIFIED,), items_total=2),
        _verifier_run(
            (IntegrityResult.VERIFIED, IntegrityResult.VERIFIED),
            progress_bytes=3,
        ),
    ],
)
def test_verifier_rejects_mixed_degraded_or_incomplete_samples(
    run: SimpleNamespace,
) -> None:
    with pytest.raises(VerifierRigError, match="invalid benchmark sample"):
        tools_cli._validate_verifier_run(run, IntegrityResult.VERIFIED)


def _executor_run(kind: OperationKind = OperationKind.NOOP) -> SimpleNamespace:
    op_id = "a" * 32
    run_id = validated_run_id("b" * 32)
    target_path = "file.bin"
    outcome = Outcome.SKIPPED if kind is OperationKind.NOOP else Outcome.SUCCEEDED
    operation = SimpleNamespace(
        op_id=op_id,
        kind=kind,
        target_rel_path=target_path,
        content_bytes=0,
    )
    plan = SimpleNamespace(operations=(operation,))
    execution_set = ExecutionSet(plan, frozenset({op_id}), run_id)
    execution_set.status[op_id] = outcome
    if kind is not OperationKind.NOOP:
        subject = FileStat(
            EntryKind.FILE,
            0,
            0,
            None,
            1,
            MetadataSnapshot(0, None),
        )
        execution_set.published_evidence[op_id] = PublishedCopyEvidence(
            Attestation(
                ContentEvidence(
                    "xxh3_128",
                    bytes(16),
                    0,
                    Provenance.COPY_ATTESTED,
                    datetime.now(timezone.utc),
                ),
                subject,
            ),
            RecordedCopyIdentity(
                "row-1",
                "location-1",
                str(run_id),
                normalize_relative_path(target_path),
            ),
        )
    result = SimpleNamespace(
        status=SessionState.COMPLETED,
        recording=RecordingStatus.OK,
        audit=RecordingStatus.OK,
        disposition=Disposition.RAN,
        canceled=False,
        error=None,
        bytes_done=0,
        bytes_total=0,
        items=(ItemOutcome(op_id, kind.value, target_path, outcome),),
    )
    return SimpleNamespace(
        result=result,
        execution_set=execution_set,
        plan=plan,
        outcomes={outcome.value: 1},
        bytes_done=0,
        throughput_mib_s=0.0,
        operation_kinds={kind.value: 1},
        recorder=SimpleNamespace(calls={}),
        copy_samples=(),
        scan_seconds=0.0,
        plan_seconds=0.0,
        preflight_seconds=0.0,
        execute_seconds=0.0,
    )


def test_executor_accepts_a_complete_noop_sample() -> None:
    tools_cli._validate_executor_run(_executor_run())


def test_executor_rejects_failed_degraded_unsettled_and_evidence_gap() -> None:
    failed = _executor_run()
    failed.result.status = SessionState.FAILED
    degraded = _executor_run()
    degraded.result.recording = RecordingStatus.DEGRADED
    unsettled = _executor_run()
    unsettled.execution_set.status = {}
    evidence_gap = _executor_run(OperationKind.COPY)
    evidence_gap.execution_set.published_evidence = {}

    for run in (failed, degraded, unsettled, evidence_gap):
        with pytest.raises(ExecutorRigError, match="invalid benchmark sample"):
            tools_cli._validate_executor_run(run)


def test_executor_rejects_result_items_that_disagree_with_settlement() -> None:
    run = _executor_run()
    run.result.items = (
        replace(run.result.items[0], outcome=Outcome.SUCCEEDED),
    )

    with pytest.raises(ExecutorRigError, match="result items disagree"):
        tools_cli._validate_executor_run(run)


def test_executor_rejects_invalid_published_identity() -> None:
    run = _executor_run(OperationKind.COPY)
    op_id = next(iter(run.execution_set.selection))
    evidence = run.execution_set.published_evidence[op_id]
    run.execution_set.published_evidence[op_id] = replace(
        evidence,
        recorded_identity=replace(
            evidence.recorded_identity,
            scope_token="wrong-scope",
        ),
    )

    with pytest.raises(ExecutorRigError, match="execution evidence is inconsistent"):
        tools_cli._validate_executor_run(run)


def _readback(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "candidates": 0,
        "expected_candidates": 0,
        "seconds": 0.0,
        "bytes": 0,
        "expected_bytes": 0,
        "throughput_mib_s": 0.0,
        "results": {},
        "recording": RecordingStatus.OK.value,
    }
    value.update(overrides)
    return value


def test_zero_candidate_readback_is_valid() -> None:
    tools_cli._validate_readback(_readback())


def test_readback_rejects_incomplete_verifier_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _executor_run(OperationKind.COPY)
    monkeypatch.setattr(
        tools_cli,
        "run_post_copy",
        lambda selection: _verifier_run(
            (IntegrityResult.VERIFIED,), progress_bytes=0
        ),
    )

    with pytest.raises(VerifierRigError, match="progress coverage"):
        tools_cli._readback(run, tmp_path)


@pytest.mark.parametrize(
    "readback",
    [
        _readback(candidates=1),
        _readback(candidates=1, expected_candidates=1, results={"mismatched": 1}),
        _readback(bytes=1),
        _readback(recording=RecordingStatus.DEGRADED.value),
    ],
)
def test_readback_rejects_count_result_byte_and_recording_failures(
    readback: dict[str, object],
) -> None:
    with pytest.raises(VerifierRigError, match="invalid benchmark sample"):
        tools_cli._validate_readback(readback)


@pytest.mark.parametrize(
    ("extra_args", "expected_metrics"),
    [([], True), (["--no-metrics"], False)],
)
def test_executor_diagnostics_default_on_and_can_be_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    extra_args: list[str],
    expected_metrics: bool,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target"
    observed: list[bool] = []

    @contextmanager
    def fake_claim(path: Path):
        yield SimpleNamespace(target=path)

    def fake_run(source_path: Path, workspace: object, **kwargs: object):
        del source_path, workspace
        observed.append(bool(kwargs["collect_metrics"]))
        return _executor_run()

    monkeypatch.setattr(tools_cli.corpus, "claim", fake_claim)
    monkeypatch.setattr(tools_cli.corpus, "empty", lambda workspace: None)
    monkeypatch.setattr(tools_cli.corpus, "teardown", lambda workspace: None)
    monkeypatch.setattr(tools_cli, "run_executor", fake_run)

    result = tools_cli.main(["executor", str(source), str(target), *extra_args])

    assert result == 0
    assert observed == [expected_metrics]
    assert "execute:" in capsys.readouterr().out


def test_readback_is_visible_without_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target"

    @contextmanager
    def fake_claim(path: Path):
        yield SimpleNamespace(target=path)

    monkeypatch.setattr(tools_cli.corpus, "claim", fake_claim)
    monkeypatch.setattr(tools_cli.corpus, "empty", lambda workspace: None)
    monkeypatch.setattr(tools_cli.corpus, "teardown", lambda workspace: None)
    monkeypatch.setattr(tools_cli, "run_executor", lambda *args, **kwargs: _executor_run())
    monkeypatch.setattr(tools_cli, "_readback", lambda *args, **kwargs: _readback())

    result = tools_cli.main(
        ["executor", str(source), str(target), "--verify-readback"]
    )

    assert result == 0
    assert "readback: 0 candidates" in capsys.readouterr().out
