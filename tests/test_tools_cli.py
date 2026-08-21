from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
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
from tools import executor_rig
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


def test_report_replacement_rejects_a_reparse_alias(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    victim = tmp_path / "victim.json"
    victim.write_text("keep", encoding="utf-8")
    alias = tmp_path / "report.json"
    try:
        os.symlink(victim, alias)
    except OSError as error:
        pytest.skip(f"file symlinks are unavailable: {error}")

    assert tools_cli.main(
        [
            "verifier",
            str(root),
            "--mode",
            "baseline",
            "--json",
            str(alias),
            "--replace-report",
        ]
    ) == 2
    assert victim.read_text(encoding="utf-8") == "keep"
    assert "must not traverse a reparse point" in capsys.readouterr().err


def test_artifact_path_rejects_a_generic_reparse_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    artifact_parent = tmp_path / "artifact-parent"
    artifact_parent.mkdir()
    parent_inode = artifact_parent.stat().st_ino
    monkeypatch.setattr(
        tools_cli,
        "is_reparse_stat",
        lambda observed: observed.st_ino == parent_inode,
    )

    with pytest.raises(
        tools_cli.ToolError,
        match="must not traverse a reparse point",
    ):
        tools_cli._validate_artifact_path(
            artifact_parent / "report.json",
            "JSON report",
            roots=(("corpus", root),),
        )


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


def test_verifier_requires_explicit_sidecar_and_replace_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    implicit = tools_cli.sidecar.sidecar_path_for(root)
    explicit = tmp_path / "baseline.jsonl"
    monkeypatch.setattr(tools_cli, "prime_baselines", lambda *args, **kwargs: {})

    assert tools_cli.main(["verifier", str(root), "--seed-baselines"]) == 2
    assert not implicit.exists()
    assert "pass --sidecar PATH" in capsys.readouterr().err

    seed = [
        "verifier",
        str(root),
        "--seed-baselines",
        "--sidecar",
        str(explicit),
    ]
    assert tools_cli.main(seed) == 0
    original = explicit.read_bytes()
    assert tools_cli.main(seed) == 2
    assert explicit.read_bytes() == original
    assert "--replace-sidecar" in capsys.readouterr().err
    assert tools_cli.main([*seed, "--replace-sidecar"]) == 0


def test_sidecar_replacement_refuses_an_occupant_changed_during_priming(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    destination = tmp_path / "baseline.jsonl"
    destination.write_text("old", encoding="utf-8")

    def replace_occupant(*args: object, **kwargs: object) -> dict:
        del args, kwargs
        replacement = tmp_path / "replacement.jsonl"
        replacement.write_text("new occupant", encoding="utf-8")
        os.replace(replacement, destination)
        return {}

    monkeypatch.setattr(tools_cli, "prime_baselines", replace_occupant)

    assert tools_cli.main(
        [
            "verifier",
            str(root),
            "--seed-baselines",
            "--sidecar",
            str(destination),
            "--replace-sidecar",
        ]
    ) == 2
    assert destination.read_text(encoding="utf-8") == "new occupant"
    assert "replaced before publication" in capsys.readouterr().err


@pytest.mark.parametrize(
    "extra",
    [
        ["--repeat", "2"],
        ["--mode", "baseline"],
        ["--baselines", "none"],
        ["--no-tap"],
    ],
)
def test_seed_baselines_rejects_inapplicable_measurement_options(
    tmp_path: Path,
    extra: list[str],
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()

    assert tools_cli.main(
        [
            "verifier",
            str(root),
            "--seed-baselines",
            "--sidecar",
            str(tmp_path / "baseline.jsonl"),
            *extra,
        ]
    ) == 2
    assert not (tmp_path / "baseline.jsonl").exists()


def test_verifier_report_is_one_atomic_versioned_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    report = tmp_path / "verifier-report.json"
    monkeypatch.setattr(
        tools_cli,
        "run_verifier",
        lambda *args, **kwargs: _verifier_run((IntegrityResult.BASELINED,)),
    )

    assert tools_cli.main(
        [
            "verifier",
            str(root),
            "--mode",
            "baseline",
            "--repeat",
            "2",
            "--json",
            str(report),
        ]
    ) == 0

    document = json.loads(report.read_text(encoding="utf-8"))
    assert document["format"] == tools_cli.REPORT_FORMAT
    assert document["command"] == "verifier"
    assert document["configuration"]["repeat"] == 2
    assert [sample["iteration"] for sample in document["samples"]] == [1, 2]
    assert document["summary"] == {
        "n": 2,
        "seconds": {"minimum": 1.0, "median": 1.0, "maximum": 1.0},
        "throughput_mib_s": {"median": 0.0},
    }
    output = capsys.readouterr().out
    assert "reader: open" in output
    assert "summary: n=2" in output
    assert "run median" in output
    assert "verify median" not in output
    assert "wrote benchmark report" in output
    assert list(tmp_path.glob(".verifier-report.json.*.tmp")) == []


def test_verifier_setup_fixture_drift_invalidates_the_whole_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    report = tmp_path / "report.json"
    setup = _verifier_run((IntegrityResult.VERIFIED,)).attestations()
    monkeypatch.setattr(tools_cli, "prime_baselines", lambda *args, **kwargs: setup)
    monkeypatch.setattr(
        tools_cli,
        "run_verifier",
        lambda *args, **kwargs: _verifier_run(()),
    )

    assert tools_cli.main(
        ["verifier", str(root), "--json", str(report)]
    ) == 2
    assert not report.exists()
    assert "membership changed" in capsys.readouterr().err


def test_verifier_default_publishes_no_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    setup = _verifier_run((IntegrityResult.VERIFIED,)).attestations()
    monkeypatch.setattr(tools_cli, "prime_baselines", lambda *args, **kwargs: setup)
    monkeypatch.setattr(
        tools_cli,
        "run_verifier",
        lambda *args, **kwargs: _verifier_run((IntegrityResult.VERIFIED,)),
    )
    before = set(tmp_path.iterdir())

    assert tools_cli.main(["verifier", str(root)]) == 0

    assert set(tmp_path.iterdir()) == before


def test_verifier_baselining_content_drift_invalidates_repeats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    report = tmp_path / "report.json"
    runs = iter(
        (
            _verifier_run((IntegrityResult.BASELINED,), digest_byte=1),
            _verifier_run((IntegrityResult.BASELINED,), digest_byte=2),
        )
    )
    monkeypatch.setattr(
        tools_cli,
        "run_verifier",
        lambda *args, **kwargs: next(runs),
    )

    assert tools_cli.main(
        [
            "verifier",
            str(root),
            "--mode",
            "baseline",
            "--repeat",
            "2",
            "--json",
            str(report),
        ]
    ) == 2
    assert not report.exists()
    assert "content changed" in capsys.readouterr().err


def test_report_refuses_existing_destination_and_replaces_only_explicitly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    report = tmp_path / "report.json"
    report.write_text("keep", encoding="utf-8")
    calls = 0

    def run(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _verifier_run((IntegrityResult.BASELINED,))

    monkeypatch.setattr(tools_cli, "run_verifier", run)
    command = [
        "verifier",
        str(root),
        "--mode",
        "baseline",
        "--json",
        str(report),
    ]

    assert tools_cli.main(command) == 2
    assert calls == 0
    assert report.read_text(encoding="utf-8") == "keep"
    assert tools_cli.main([*command, "--replace-report"]) == 0
    assert calls == 1
    assert json.loads(report.read_text(encoding="utf-8"))["format"] == tools_cli.REPORT_FORMAT


def test_later_invalid_sample_publishes_no_partial_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    report = tmp_path / "report.json"
    runs = iter(
        (
            _verifier_run((IntegrityResult.BASELINED,)),
            _verifier_run((IntegrityResult.ERROR,)),
        )
    )
    monkeypatch.setattr(tools_cli, "run_verifier", lambda *args, **kwargs: next(runs))

    assert tools_cli.main(
        [
            "verifier",
            str(root),
            "--mode",
            "baseline",
            "--repeat",
            "2",
            "--json",
            str(report),
        ]
    ) == 2
    assert not report.exists()
    assert list(tmp_path.glob(".report.json.*.tmp")) == []


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


def test_template_rejects_redundant_prepare_each(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    template = tmp_path / "template"
    template.mkdir()
    target = tmp_path / "target"

    assert tools_cli.main(
        [
            "executor",
            str(source),
            str(target),
            "--template",
            str(template),
            "--prepare-each",
        ]
    ) == 2
    assert "already rescans" in capsys.readouterr().err
    assert not target.exists()


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


def test_baseline_mode_rejects_an_inapplicable_sidecar_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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

    assert result == 2
    assert "baseline mode does not accept --baselines" in capsys.readouterr().err


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
        return _verifier_run((IntegrityResult.VERIFIED,)).attestations()

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
    digest_byte: int = 0,
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
            "execute",
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
    fixture = tuple(
        (
            f"FILE-{number}.BIN",
            FileStat(
                EntryKind.FILE,
                3,
                100 + number,
                None,
                1,
                MetadataSnapshot(0, None),
            ),
        )
        for number in range(len(results))
    )
    attestations = {
        key: Attestation(
            ContentEvidence(
                "xxh3_128",
                bytes([(digest_byte + number) % 256]) * 16,
                stat.size,
                Provenance.VERIFY_ATTESTED,
                datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            stat,
        )
        for number, (key, stat) in enumerate(fixture)
    }
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
        fixture=fixture,
        attestations=lambda: dict(attestations),
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
    plan = SimpleNamespace(
        operations=(operation,),
        fingerprint="plan-fingerprint",
        policy_fingerprint="policy-fingerprint",
    )
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
        target_scan=SimpleNamespace(files=(), directories=()),
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

    def fake_run(source_path: Path, workspace: object, **kwargs: object):
        del source_path, workspace
        observed.append(bool(kwargs["collect_metrics"]))
        return _executor_run()

    monkeypatch.setattr(tools_cli, "run_executor", fake_run)

    result = tools_cli.main(
        ["executor", str(source), str(target), "--prepare-each", *extra_args]
    )

    assert result == 0
    assert observed == [expected_metrics]
    output = capsys.readouterr().out
    assert "execute:" in output
    assert ("pipeline:" in output) is expected_metrics


def test_executor_default_teardown_leaves_no_workspace_or_report_artifacts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"

    assert tools_cli.main(["executor", str(source), str(target)]) == 0

    assert not target.exists()
    assert not tools_cli.corpus.marker_for(target).exists()
    assert not tools_cli.corpus.lease_for(target).exists()
    assert not tools_cli.corpus.outputs_for(target).exists()


def test_readback_is_visible_without_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target"

    monkeypatch.setattr(tools_cli, "run_executor", lambda *args, **kwargs: _executor_run())
    monkeypatch.setattr(tools_cli, "_readback", lambda *args, **kwargs: _readback())

    result = tools_cli.main(
        [
            "executor",
            str(source),
            str(target),
            "--prepare-each",
            "--verify-readback",
        ]
    )

    assert result == 0
    assert "readback: 0 candidates" in capsys.readouterr().out


def test_readback_report_values_preserve_measurement_precision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified = _verifier_run((IntegrityResult.VERIFIED,))
    verified.run_seconds = 1.23456789123
    verified.throughput_mib_s = 9.87654321987
    monkeypatch.setattr(tools_cli, "run_post_copy", lambda *args, **kwargs: verified)

    readback = tools_cli._readback(
        _executor_run(OperationKind.COPY),
        tmp_path,
    )

    assert readback["seconds"] == 1.23456789123
    assert readback["throughput_mib_s"] == 9.87654321987


def test_empty_target_repeats_prepare_and_preflight_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"
    scans: list[str] = []
    preflights = 0
    original_scan = executor_rig.scan_root
    original_observe = executor_rig.observe

    def counted_scan(root, *args, **kwargs):
        scans.append(root.root_id)
        return original_scan(root, *args, **kwargs)

    def counted_observe(*args, **kwargs):
        nonlocal preflights
        preflights += 1
        return original_observe(*args, **kwargs)

    monkeypatch.setattr(executor_rig, "scan_root", counted_scan)
    monkeypatch.setattr(executor_rig, "observe", counted_observe)

    result = tools_cli.main(
        ["executor", str(source), str(target), "--repeat", "2"]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert scans.count("source") == 2
    assert scans.count("target") == 1
    assert preflights == 1
    assert "prepared once:" in output
    assert "source recheck: unchanged" in output
    assert "pipeline:" in output
    assert "outside backend" in output
    assert "reserved" in output
    assert "summary: n=2" in output
    assert not target.exists()


def test_prepare_each_rebuilds_and_preflights_every_iteration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"
    scans: list[str] = []
    preflights = 0
    original_scan = executor_rig.scan_root
    original_observe = executor_rig.observe

    def counted_scan(root, *args, **kwargs):
        scans.append(root.root_id)
        return original_scan(root, *args, **kwargs)

    def counted_observe(*args, **kwargs):
        nonlocal preflights
        preflights += 1
        return original_observe(*args, **kwargs)

    monkeypatch.setattr(executor_rig, "scan_root", counted_scan)
    monkeypatch.setattr(executor_rig, "observe", counted_observe)

    result = tools_cli.main(
        [
            "executor",
            str(source),
            str(target),
            "--repeat",
            "2",
            "--prepare-each",
        ]
    )

    assert result == 0
    assert scans.count("source") == 2
    assert scans.count("target") == 2
    assert preflights == 2


def test_no_preflight_skips_the_gate_for_static_repeats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"

    def fail_observe(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("preflight observation must be skipped")

    monkeypatch.setattr(executor_rig, "observe", fail_observe)

    assert tools_cli.main(
        [
            "executor",
            str(source),
            str(target),
            "--repeat",
            "2",
            "--no-preflight",
        ]
    ) == 0


def test_single_static_sample_still_rechecks_source_membership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"
    source_scans = 0
    original_scan = executor_rig.scan_root

    def counted_scan(root, *args, **kwargs):
        nonlocal source_scans
        if root.root_id == "source":
            source_scans += 1
        return original_scan(root, *args, **kwargs)

    monkeypatch.setattr(executor_rig, "scan_root", counted_scan)

    assert tools_cli.main(["executor", str(source), str(target)]) == 0
    assert source_scans == 2


def test_clean_requires_exact_outputs_or_explicit_force_and_prints_receipts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "legacy"
    with tools_cli.corpus.claim(target):
        (target / "inspect-me.txt").write_text("keep", encoding="utf-8")
    unrecognized_manifest = tools_cli.corpus.outputs_for(target)

    assert tools_cli.main(["clean", str(target)]) == 2
    assert (target / "inspect-me.txt").read_text(encoding="utf-8") == "keep"
    assert "without an exact output manifest" in capsys.readouterr().err
    unrecognized_manifest.write_text("unrelated", encoding="utf-8")

    assert tools_cli.main(["clean", str(target), "--force-all", "--dry-run"]) == 0
    dry_run = capsys.readouterr().out
    assert f"root {target.resolve()}" in dry_run
    assert "delete 1 files, 0 directories, 4 bytes" in dry_run
    assert "explicit --force-all" in dry_run
    assert "clean: delete file inspect-me.txt" in dry_run
    assert "preserve unrecognized sibling artifact" in dry_run
    assert "nothing was deleted" in dry_run
    assert target.exists()

    assert tools_cli.main(["clean", str(target), "--force-all"]) == 0
    cleaned = capsys.readouterr().out
    assert "removed 1 files, 0 directories, 4 bytes" in cleaned
    assert "root and marker removed" in cleaned
    assert "preserved an unrecognized sibling artifact" in cleaned
    assert "before reusing this workspace name" in cleaned
    assert not target.exists()
    assert unrecognized_manifest.read_text(encoding="utf-8") == "unrelated"


def test_force_cleanup_applies_only_the_printed_deletion_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "legacy"
    with tools_cli.corpus.claim(target):
        displayed = target / "displayed.txt"
        displayed.write_text("keep", encoding="utf-8")
    original_print = tools_cli._print_cleanup_plan

    def print_then_insert(action: str, plan: tools_cli.corpus.CleanupPlan) -> None:
        original_print(action, plan)
        (target / "late.txt").write_text("late", encoding="utf-8")

    monkeypatch.setattr(tools_cli, "_print_cleanup_plan", print_then_insert)

    assert tools_cli.main(["clean", str(target), "--force-all"]) == 2
    assert displayed.read_text(encoding="utf-8") == "keep"
    assert (target / "late.txt").read_text(encoding="utf-8") == "late"
    output = capsys.readouterr()
    assert "delete file displayed.txt" in output.out
    assert "nothing was deleted" in output.err.lower()


def test_clean_refuses_an_unlisted_child_without_partial_deletion(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "owned"
    with tools_cli.corpus.claim(target) as workspace:
        tools_cli.corpus.generate(workspace, "1@8B")
        generated = next(target.rglob("*.bin"))
        foreign = target / "foreign.txt"
        foreign.write_text("keep", encoding="utf-8")

    assert tools_cli.main(["clean", str(target)]) == 2
    assert generated.exists()
    assert foreign.read_text(encoding="utf-8") == "keep"
    assert "Nothing was deleted" in capsys.readouterr().err


def test_clean_rejects_a_requested_directory_alias(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "owned"
    with tools_cli.corpus.claim(target) as workspace:
        tools_cli.corpus.generate(workspace, "1@8B")
    alias = tmp_path / "alias"
    try:
        os.symlink(target, alias, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlinks are unavailable: {error}")

    assert tools_cli.main(["clean", str(alias), "--force-all"]) == 2
    assert target.exists()
    assert next(target.rglob("*.bin")).exists()
    assert "must not traverse an alias or reparse point" in capsys.readouterr().err


def test_clean_never_guesses_or_removes_external_artifacts(tmp_path: Path) -> None:
    target = tmp_path / "owned"
    with tools_cli.corpus.claim(target) as workspace:
        tools_cli.corpus.generate(workspace, "1@8B")
    former_default_sidecar = tools_cli.sidecar.sidecar_path_for(target)
    report = tmp_path / "report.json"
    former_default_sidecar.write_text("baseline", encoding="utf-8")
    report.write_text("report", encoding="utf-8")

    assert tools_cli.main(["clean", str(target)]) == 0
    assert former_default_sidecar.read_text(encoding="utf-8") == "baseline"
    assert report.read_text(encoding="utf-8") == "report"


def test_executor_retains_the_last_exact_sample_after_batch_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"

    def reject_batch(*args, **kwargs):
        del args, kwargs
        raise ExecutorRigError("repeated copy evidence drifted")

    monkeypatch.setattr(tools_cli, "require_stable_copy_evidence", reject_batch)

    assert tools_cli.main(
        ["executor", str(source), str(target), "--repeat", "2"]
    ) == 2
    assert (target / "data.bin").read_bytes() == b"payload"
    assert tools_cli.corpus.outputs_for(target).exists()
    error = capsys.readouterr().err
    assert "workspace retained after failure" in error
    assert "exact outputs validate" in error


def test_template_failure_does_not_call_its_stale_manifest_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    template = tmp_path / "template"
    template.mkdir()
    (template / "before.bin").write_bytes(b"before")
    target = tmp_path / "target"

    def mutate_then_fail(source_path: Path, workspace, **kwargs: object):
        del source_path, kwargs
        (workspace.target / "partial.bin").write_bytes(b"partial")
        raise ExecutorRigError("injected executor failure")

    monkeypatch.setattr(tools_cli, "run_executor", mutate_then_fail)

    assert tools_cli.main(
        ["executor", str(source), str(target), "--template", str(template)]
    ) == 2
    assert (target / "before.bin").exists()
    assert (target / "partial.bin").exists()
    error = capsys.readouterr().err
    assert "does not validate against the live workspace" in error
    assert "exact outputs validate" not in error


def test_generation_failure_keeps_the_completed_reset_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "corpus"
    with tools_cli.corpus.claim(root) as workspace:
        tools_cli.corpus.generate(workspace, "1@8B")

    def fail_generation(*args: object, **kwargs: object):
        del args, kwargs
        raise tools_cli.corpus.CorpusError("injected generation failure")

    monkeypatch.setattr(tools_cli.corpus, "generate", fail_generation)

    assert tools_cli.main(["generate", str(root), "1@8B"]) == 2
    captured = capsys.readouterr()
    assert "corpus replacement complete: removed 1 files" in captured.out
    assert "workspace is empty" in captured.err
    assert list(root.iterdir()) == []


def test_executor_refuses_unknown_insertion_before_repeat_reset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"
    original_reset = tools_cli._reset_workspace

    def insert_before_reset(workspace, action: str) -> None:
        if "sample 2" in action:
            (workspace.target / "foreign.txt").write_text("keep", encoding="utf-8")
        original_reset(workspace, action)

    monkeypatch.setattr(tools_cli, "_reset_workspace", insert_before_reset)

    assert tools_cli.main(
        ["executor", str(source), str(target), "--repeat", "2"]
    ) == 2
    assert (target / "data.bin").exists()
    assert (target / "foreign.txt").read_text(encoding="utf-8") == "keep"
    assert "Nothing was deleted" in capsys.readouterr().err


def test_template_trash_outputs_are_exactly_cleaned(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    template = tmp_path / "template"
    template.mkdir()
    (template / "target-only.bin").write_bytes(b"old")
    target = tmp_path / "target"

    assert tools_cli.main(
        ["executor", str(source), str(target), "--template", str(template)]
    ) == 0
    assert not target.exists()
    assert not tools_cli.corpus.outputs_for(target).exists()


def test_template_update_and_backup_outputs_are_exactly_cleaned(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    source_file = source / "changed.bin"
    source_file.write_bytes(b"new-content")
    template = tmp_path / "template"
    template.mkdir()
    template_file = template / "changed.bin"
    template_file.write_bytes(b"old-content")
    source_details = source_file.stat()
    os.utime(
        template_file,
        ns=(source_details.st_atime_ns, source_details.st_mtime_ns - 1_000_000_000),
    )
    target = tmp_path / "target"

    assert tools_cli.main(
        ["executor", str(source), str(target), "--template", str(template)]
    ) == 0
    assert not target.exists()


def test_executor_report_separates_batch_preparation_samples_and_summary(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"
    report = tmp_path / "executor-report.json"

    assert tools_cli.main(
        [
            "executor",
            str(source),
            str(target),
            "--repeat",
            "2",
            "--json",
            str(report),
        ]
    ) == 0

    document = json.loads(report.read_text(encoding="utf-8"))
    assert document["format"] == tools_cli.REPORT_FORMAT
    assert document["configuration"]["preparation"] == "once"
    assert document["batch_preparation"]["scan_seconds"] is not None
    assert document["batch_preparation"]["plan_seconds"] is not None
    assert document["batch_preparation"]["preflight_seconds"] is not None
    assert document["batch_validation"]["source_recheck_seconds"] is not None
    assert [sample["iteration"] for sample in document["samples"]] == [1, 2]
    assert document["samples"][0]["scan_seconds"] is None
    assert document["samples"][0]["plan_seconds"] is None
    assert document["samples"][0]["preflight_seconds"] is None
    assert document["samples"][0]["plan_fingerprint"]
    assert document["summary"]["n"] == 2
    assert not target.exists()


def test_cleanup_failure_prevents_executor_report_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    target = tmp_path / "target"
    report = tmp_path / "executor-report.json"
    original_teardown = tools_cli._teardown_workspace

    def insert_before_teardown(workspace, action: str) -> None:
        (workspace.target / "foreign.txt").write_text("keep", encoding="utf-8")
        original_teardown(workspace, action)

    monkeypatch.setattr(tools_cli, "_teardown_workspace", insert_before_teardown)

    assert tools_cli.main(
        ["executor", str(source), str(target), "--json", str(report)]
    ) == 2
    assert not report.exists()
    assert (target / "foreign.txt").read_text(encoding="utf-8") == "keep"


def test_report_replacement_refuses_destination_identity_change(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    report = tmp_path / "report.json"
    report.write_text("old", encoding="utf-8")
    destination = tools_cli._output_destination(
        report,
        "JSON report",
        roots=(("root", root),),
        replace=True,
    )
    report.unlink()
    report.write_text("new owner", encoding="utf-8")

    with pytest.raises(tools_cli.ToolError, match="replaced before publication"):
        tools_cli._write_report(
            destination,
            {"format": tools_cli.REPORT_FORMAT},
        )

    assert report.read_text(encoding="utf-8") == "new owner"
    assert list(tmp_path.glob(".report.json.*.tmp")) == []
