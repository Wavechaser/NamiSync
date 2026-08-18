"""Command line for the development tools: ``python -m tools ...``."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
from statistics import median
import sys
import tempfile
from time import perf_counter
from typing import Sequence

from xxhash import xxh3_128

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import ItemOutcome, Progress
from namisync.core.execution import ExecutionSet
from namisync.core.integrity import IntegrityMode, IntegrityResult
from namisync.core.planning import DeletionPolicy, OperationKind, SyncOptions
from namisync.core.root_authority import is_reparse_stat
from namisync.core.session import Disposition, SessionState

from . import corpus, sidecar
from .executor_rig import (
    ExecutorRun,
    ExecutorRigError,
    copy_metrics_summary,
    execute_prepared,
    expected_output_paths,
    prepare_execution,
    require_reusable_copy_plan,
    require_source_unchanged,
    require_stable_copy_evidence,
    run_executor,
)
from .seams import constant_hasher_factory
from .verifier_rig import (
    VerifierRigError,
    content_evidence,
    load_baselines,
    post_copy_selection,
    prime_baselines,
    require_fixture,
    require_stable_content_evidence,
    run_post_copy,
    run_verifier,
    scan_stats,
    synthetic_baselines,
)


class ToolError(RuntimeError):
    """A requested measurement would be unsafe or misleading."""


REPORT_FORMAT = "namisync-tools-benchmark-1"


@dataclass(frozen=True, slots=True)
class ArtifactDestination:
    path: Path
    existing_identity: tuple[int, int] | None


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (
        ExecutorRigError,
        VerifierRigError,
        corpus.CorpusError,
        sidecar.SidecarError,
        ToolError,
        OSError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools",
        description="Development measurements for the executor and verifier.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    verifier = subcommands.add_parser(
        "verifier", help="measure baseline/verify/rebaseline over a corpus"
    )
    verifier.add_argument("root", type=Path, help="corpus root to read")
    verifier.add_argument(
        "--mode",
        choices=[mode.value for mode in IntegrityMode],
        default=IntegrityMode.VERIFY.value,
    )
    verifier.add_argument(
        "--baselines",
        choices=["primed", "sidecar", "synthetic", "none"],
        default="primed",
        help=(
            "prior evidence source; 'synthetic' reaches the full read/hash loop "
            "but settles as MISMATCHED"
        ),
    )
    verifier.add_argument(
        "--sidecar",
        type=Path,
        default=None,
        help="explicit baseline sidecar path for seed/load",
    )
    verifier.add_argument(
        "--seed-baselines",
        action="store_true",
        help="run one baseline pass, write the sidecar, and exit",
    )
    verifier.add_argument(
        "--identity",
        choices=list(sidecar.IDENTITY_MODES),
        default=sidecar.PORTABLE,
        help="whether stored evidence enforces NTFS file identity",
    )
    verifier.add_argument("--chunk-size", type=corpus.parse_size, default=4 * 1024 * 1024)
    verifier.add_argument("--repeat", type=_positive_int, default=1)
    verifier.add_argument("--no-tap", action="store_true", help="disable per-chunk timing")
    verifier.add_argument(
        "--null-hasher",
        action="store_true",
        help="constant-digest hasher; pair with a normal run to isolate hash cost",
    )
    verifier.add_argument(
        "--replace-sidecar",
        action="store_true",
        help="replace the explicit seed sidecar after identity revalidation",
    )
    verifier.add_argument(
        "--json",
        type=Path,
        default=None,
        help="atomically write one versioned batch JSON report",
    )
    verifier.add_argument(
        "--replace-report",
        action="store_true",
        help="replace an existing report after identity revalidation",
    )
    verifier.set_defaults(handler=_run_verifier_command)

    executor = subcommands.add_parser(
        "executor", help="measure one reviewed execution into a tool-owned target"
    )
    executor.add_argument("source", type=Path, help="source root to mirror")
    executor.add_argument("target", type=Path, help="tool-owned target workspace")
    executor.add_argument(
        "--template",
        type=Path,
        default=None,
        help="target pre-state copied in before each run (default: empty target)",
    )
    executor.add_argument(
        "--deletion-policy",
        choices=[DeletionPolicy.TRASH.value, DeletionPolicy.ADDITIVE.value],
        default=DeletionPolicy.TRASH.value,
    )
    executor.add_argument("--repeat", type=_positive_int, default=1)
    executor.add_argument(
        "--prepare-each",
        action="store_true",
        help="rescan, replan, and preflight every empty-target iteration",
    )
    executor.add_argument("--keep", action="store_true", help="skip teardown")
    executor.add_argument("--no-preflight", action="store_true")
    executor.add_argument(
        "--no-metrics",
        action="store_true",
        help="disable pipeline diagnostics and per-copy timing",
    )
    executor.add_argument(
        "--verify-readback",
        action="store_true",
        help="run verify_post_copy over the published evidence",
    )
    executor.add_argument(
        "--json",
        type=Path,
        default=None,
        help="atomically write one versioned batch JSON report",
    )
    executor.add_argument(
        "--replace-report",
        action="store_true",
        help="replace an existing report after identity revalidation",
    )
    executor.set_defaults(handler=_run_executor_command)

    generate = subcommands.add_parser("generate", help="write a deterministic corpus")
    generate.add_argument("root", type=Path)
    generate.add_argument("spec", help="count@size groups, e.g. 2000@4KiB,100@1MiB")
    generate.add_argument("--seed", type=int, default=0)
    generate.set_defaults(handler=_run_generate_command)

    clean = subcommands.add_parser("clean", help="tear down a tool-owned workspace")
    clean.add_argument("target", type=Path)
    clean.add_argument(
        "--force-all",
        action="store_true",
        help="delete every inspected entry when no exact output manifest is usable",
    )
    clean.add_argument(
        "--dry-run",
        action="store_true",
        help="print the deletion boundary and counts without removing anything",
    )
    clean.set_defaults(handler=_run_clean_command)
    return parser


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _paths_overlap(first: Path, second: Path) -> bool:
    return (
        first == second
        or first.is_relative_to(second)
        or second.is_relative_to(first)
    )


def _ownership_artifacts(root: Path) -> tuple[Path, Path, Path]:
    return (
        corpus.marker_for(root).resolve(),
        corpus.lease_for(root).resolve(),
        corpus.outputs_for(root).resolve(),
    )


def _reserved_root_artifacts(root: Path) -> tuple[Path, ...]:
    return _ownership_artifacts(root)


def _validate_artifact_path(
    path: Path,
    label: str,
    *,
    roots: Sequence[tuple[str, Path]],
    reserved: Sequence[Path] = (),
) -> Path:
    requested = Path(path).absolute()
    reparse = _reparse_component(requested)
    if reparse is not None:
        raise ToolError(
            f"{label} must not traverse a reparse point: {reparse} "
            f"(requested {requested})"
        )
    resolved = requested.resolve()
    for root_label, root in roots:
        if resolved == root or resolved.is_relative_to(root):
            raise ToolError(f"{label} must be outside the {root_label}: {resolved}")
    if resolved in reserved:
        raise ToolError(f"{label} collides with a reserved tools artifact: {resolved}")
    if resolved.exists() and not resolved.is_file():
        raise ToolError(f"{label} path is not a file: {resolved}")
    if resolved.exists() and resolved.stat().st_nlink > 1:
        raise ToolError(
            f"{label} must not be an existing hard-linked file: {resolved}"
        )
    return resolved


def _path_is_reparse(path: Path) -> bool:
    try:
        return is_reparse_stat(os.lstat(path))
    except FileNotFoundError:
        return False


def _reparse_component(path: Path) -> Path | None:
    absolute = Path(path).absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if _path_is_reparse(current):
            return current
    return None


def _output_destination(
    path: Path,
    label: str,
    *,
    roots: Sequence[tuple[str, Path]],
    reserved: Sequence[Path] = (),
    replace: bool,
    replace_flag: str = "--replace-report",
) -> ArtifactDestination:
    resolved = _validate_artifact_path(
        path,
        label,
        roots=roots,
        reserved=reserved,
    )
    if not resolved.exists():
        return ArtifactDestination(resolved, None)
    if not replace:
        raise ToolError(
            f"refusing to replace existing {label} without {replace_flag}: "
            f"{resolved}"
        )
    details = resolved.stat()
    return ArtifactDestination(resolved, (details.st_dev, details.st_ino))


def _run_verifier_command(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    mode = IntegrityMode(args.mode)
    hasher = constant_hasher_factory if args.null_hasher else xxh3_128
    if args.seed_baselines and args.null_hasher:
        raise VerifierRigError(
            "--seed-baselines writes durable evidence and cannot use "
            "--null-hasher's constant digest"
        )
    if args.baselines == "sidecar" and args.null_hasher:
        raise VerifierRigError(
            "--null-hasher cannot be combined with a real sidecar; use primed "
            "baselines so both passes use the same hasher"
        )
    if args.replace_report and args.json is None:
        raise ToolError("--replace-report requires --json PATH")
    if args.replace_sidecar and not args.seed_baselines:
        raise ToolError("--replace-sidecar is valid only with --seed-baselines")
    if args.seed_baselines:
        if args.repeat != 1:
            raise ToolError("--seed-baselines does not accept --repeat")
        if args.mode != IntegrityMode.VERIFY.value:
            raise ToolError("--seed-baselines does not accept --mode")
        if args.baselines != "primed":
            raise ToolError("--seed-baselines does not accept --baselines")
        if args.no_tap:
            raise ToolError("--seed-baselines does not accept --no-tap")
    elif args.identity != sidecar.PORTABLE:
        raise ToolError("--identity is valid only with --seed-baselines")
    if mode is IntegrityMode.BASELINE and args.baselines != "primed":
        raise ToolError("baseline mode does not accept --baselines")
    roots = (("verifier corpus", root),)
    ownership_artifacts = _ownership_artifacts(root)
    report_destination = (
        None
        if args.json is None
        else _output_destination(
            args.json,
            "JSON report",
            roots=roots,
            reserved=ownership_artifacts,
            replace=args.replace_report,
        )
    )
    needs_sidecar = args.seed_baselines or (
        mode is not IntegrityMode.BASELINE and args.baselines == "sidecar"
    )
    if needs_sidecar and args.sidecar is None:
        raise ToolError(
            "baseline persistence is explicit; pass --sidecar PATH for "
            "--seed-baselines or --baselines sidecar"
        )
    if not needs_sidecar and args.sidecar is not None:
        raise ToolError(
            "--sidecar is valid only with --seed-baselines or "
            "--baselines sidecar"
        )
    sidecar_destination = (
        _output_destination(
            args.sidecar,
            "baseline sidecar",
            roots=roots,
            reserved=ownership_artifacts,
            replace=args.replace_sidecar,
            replace_flag="--replace-sidecar",
        )
        if args.seed_baselines
        else None
    )
    sidecar_path = (
        sidecar_destination.path
        if sidecar_destination is not None
        else (
            _validate_artifact_path(
                args.sidecar,
                "baseline sidecar",
                roots=roots,
                reserved=ownership_artifacts,
            )
            if needs_sidecar
            else None
        )
    )
    if (
        sidecar_path is not None
        and report_destination is not None
        and report_destination.path == sidecar_path
    ):
        raise ToolError("JSON report and baseline sidecar paths must differ")

    if args.seed_baselines:
        if report_destination is not None:
            raise ToolError(
                "--seed-baselines creates baseline evidence, not a benchmark "
                "report; remove --json"
            )
        if sidecar_path is None:  # pragma: no cover - guarded above
            raise RuntimeError("sidecar path was not resolved")
        evidence = prime_baselines(root, chunk_size=args.chunk_size)
        rows = sidecar.write(
            sidecar_path,
            evidence,
            identity_mode=args.identity,
            replace=args.replace_sidecar,
            expected_identity=(
                None
                if sidecar_destination is None
                else sidecar_destination.existing_identity
            ),
        )
        print(f"wrote {rows} baseline rows to {sidecar_path} ({args.identity} identity)")
        return 0

    # BASELINE refuses rows that already carry evidence, so it always runs bare.
    if mode is IntegrityMode.BASELINE:
        baselines = None
        baseline_preparation: dict[str, object] = {
            "source": "none",
            "items": 0,
            "setup_seconds": 0.0,
        }
    else:
        baselines, baseline_preparation = _resolve_baselines(
            args, root, sidecar_path, hasher
        )
    expected_fixture = (
        None
        if baselines is None
        else {key: attestation.subject for key, attestation in baselines.items()}
    )
    reference_fixture = None
    reference_content = None

    records: list[dict[str, object]] = []
    for iteration in range(1, args.repeat + 1):
        run = run_verifier(
            root,
            mode,
            baselines=baselines,
            chunk_size=args.chunk_size,
            hasher_factory=hasher,
            tap_reader=not args.no_tap,
        )
        expected = _expected_verifier_result(mode, args.baselines)
        if expected_fixture is not None:
            require_fixture(
                run,
                expected_fixture,
                portable=args.baselines == "sidecar",
            )
        elif reference_fixture is None:
            reference_fixture = dict(run.fixture)
        else:
            require_fixture(run, reference_fixture, portable=False)
        _validate_verifier_run(run, expected)
        if expected is IntegrityResult.BASELINED:
            observed_content = content_evidence(run)
            if reference_content is None:
                reference_content = observed_content
            else:
                require_stable_content_evidence(reference_content, run)
        record = {
            "command": "verifier",
            "iteration": iteration,
            "root": str(root),
            "mode": mode.value,
            "baselines": args.baselines if mode is not IntegrityMode.BASELINE else "none",
            "hasher": "constant" if args.null_hasher else "xxh3_128",
            "chunk_size": args.chunk_size,
            "tapped": not args.no_tap,
            "items": run.items,
            "bytes": run.bytes_done,
            "scan_seconds": run.scan_seconds,
            "run_seconds": run.run_seconds,
            "throughput_mib_s": run.throughput_mib_s,
            "open_seconds": run.open_seconds,
            "read_seconds": run.read_seconds,
            "results": run.results,
            "recording": run.result.recording.value,
        }
        records.append(record)
        print(
            f"[{iteration}/{args.repeat}] {mode.value}: {run.items} items, "
            f"{run.bytes_done / 1024**2:.1f} MiB in {run.run_seconds:.3f}s "
            f"({run.throughput_mib_s:.1f} MiB/s) {run.results}"
        )
        if not args.no_tap:
            _print_verifier_diagnostics(run)
    if len(records) > 1:
        _print_verifier_summary(records)
    _write_report(
        report_destination,
        {
            "format": REPORT_FORMAT,
            "command": "verifier",
            "configuration": {
                "root": str(root),
                "mode": mode.value,
                "baselines": (
                    args.baselines
                    if mode is not IntegrityMode.BASELINE
                    else "none"
                ),
                "hasher": "constant" if args.null_hasher else "xxh3_128",
                "chunk_size": args.chunk_size,
                "tapped": not args.no_tap,
                "repeat": args.repeat,
                "sidecar": (
                    None if sidecar_path is None else str(sidecar_path)
                ),
            },
            "batch_preparation": baseline_preparation,
            "samples": records,
            "summary": _record_summary(
                records,
                seconds_key="run_seconds",
                throughput_key="throughput_mib_s",
            ),
        },
    )
    return 0


def _resolve_baselines(
    args: argparse.Namespace, root: Path, sidecar_path: Path | None, hasher
) -> tuple[dict | None, dict[str, object]]:
    if args.baselines == "none":
        return None, {"source": "none", "items": 0, "setup_seconds": 0.0}
    if args.baselines == "synthetic":
        started = perf_counter()
        stats, _, scan_seconds = scan_stats(root)
        evidence = synthetic_baselines(stats)
        setup_seconds = perf_counter() - started
        print(
            f"prepared {len(evidence)} synthetic baselines in "
            f"{setup_seconds:.3f}s (setup, not a sample)"
        )
        return evidence, {
            "source": "synthetic",
            "items": len(evidence),
            "setup_seconds": setup_seconds,
            "scan_seconds": scan_seconds,
        }
    if args.baselines == "sidecar":
        if sidecar_path is None:  # pragma: no cover - guarded by the caller
            raise RuntimeError("sidecar path was not resolved")
        started = perf_counter()
        stats, _, scan_seconds = scan_stats(root)
        evidence, report = load_baselines(sidecar_path, stats)
        setup_seconds = perf_counter() - started
        print(
            f"sidecar {sidecar_path}: {report.summary()}; setup "
            f"{setup_seconds:.3f}s (not a sample)"
        )
        return evidence, {
            "source": "sidecar",
            "path": str(sidecar_path),
            "items": len(evidence),
            "setup_seconds": setup_seconds,
            "scan_seconds": scan_seconds,
            "validation": {
                "matched": len(report.matched),
                "drifted": len(report.drifted),
                "missing": len(report.missing),
                "unseen": len(report.unseen),
                "identity_mode": report.identity_mode,
            },
        }
    started = perf_counter()
    evidence = prime_baselines(
        root,
        chunk_size=args.chunk_size,
        hasher_factory=hasher,
    )
    setup_seconds = perf_counter() - started
    print(
        f"primed {len(evidence)} baselines in {setup_seconds:.3f}s "
        "(setup, not a sample)"
    )
    return evidence, {
        "source": "primed",
        "items": len(evidence),
        "setup_seconds": setup_seconds,
    }


def _expected_verifier_result(
    mode: IntegrityMode, baseline_source: str
) -> IntegrityResult:
    if mode is not IntegrityMode.VERIFY or baseline_source == "none":
        return IntegrityResult.BASELINED
    if baseline_source == "synthetic":
        return IntegrityResult.MISMATCHED
    return IntegrityResult.VERIFIED


def _validate_verifier_run(run, expected: IntegrityResult) -> None:
    outcomes = run.result.outcomes
    outcome_ids = {outcome.item_id for outcome in outcomes}
    if (
        len(outcomes) != run.items
        or outcome_ids != run.expected_item_ids
        or any(outcome.result is not expected for outcome in outcomes)
    ):
        raise VerifierRigError(
            f"invalid benchmark sample: expected {run.items} {expected.value} "
            f"results, observed {run.results}"
        )
    if run.result.recording is not RecordingStatus.OK:
        raise VerifierRigError(
            "invalid benchmark sample: integrity recording was degraded"
        )
    progress = run.tape.of_type(Progress)
    if not progress:
        raise VerifierRigError(
            "invalid benchmark sample: verifier emitted no progress"
        )
    final = progress[-1]
    if (
        final.items_done != run.items
        or final.items_total != run.items
        or final.bytes_done != run.expected_bytes
        or final.bytes_total != run.expected_bytes
    ):
        raise VerifierRigError(
            "invalid benchmark sample: verifier progress coverage was incomplete"
        )


def _run_executor_command(args: argparse.Namespace) -> int:
    source = args.source.resolve()
    requested_target = args.target.absolute()
    target = requested_target.resolve()
    template = None if args.template is None else args.template.resolve()
    if not source.is_dir():
        raise ExecutorRigError(f"source root is not a directory: {source}")
    if _paths_overlap(source, target):
        raise ExecutorRigError("source and target workspaces must not overlap")
    if template is not None:
        if not template.is_dir():
            raise ExecutorRigError(f"template root is not a directory: {template}")
        if _paths_overlap(template, target):
            raise ExecutorRigError("template and target workspaces must not overlap")
    if args.replace_report and args.json is None:
        raise ToolError("--replace-report requires --json PATH")
    if template is not None and args.prepare_each:
        raise ToolError(
            "--template already rescans, replans, and preflights every sample; "
            "remove --prepare-each"
        )

    artifact_roots = [("executor source", source), ("executor target", target)]
    if template is not None:
        artifact_roots.append(("target template", template))
    reserved = tuple(
        path
        for _, root in artifact_roots
        for path in _reserved_root_artifacts(root)
    )
    report_destination = (
        None
        if args.json is None
        else _output_destination(
            args.json,
            "JSON report",
            roots=tuple(artifact_roots),
            reserved=reserved,
            replace=args.replace_report,
        )
    )

    options = SyncOptions(deletion_policy=DeletionPolicy(args.deletion_policy))
    reuse_preparation = template is None and not args.prepare_each
    with corpus.claim(requested_target) as workspace:
        try:
            prepared = None
            if reuse_preparation:
                _reset_workspace(workspace, "initial executor reset")
                prepared = prepare_execution(source, target, options=options)
                require_reusable_copy_plan(prepared)
                operations: dict[str, int] = {}
                for operation in prepared.plan.operations:
                    if operation.op_id in prepared.selection:
                        kind = operation.kind.value
                        operations[kind] = operations.get(kind, 0) + 1
                print(
                    "prepared once: "
                    f"scan {prepared.scan_seconds:.3f}s; "
                    f"plan {prepared.plan_seconds:.3f}s; "
                    f"operations {operations}"
                )

            records: list[dict[str, object]] = []
            runs = []
            source_recheck_seconds: float | None = None
            for iteration in range(1, args.repeat + 1):
                if reuse_preparation:
                    if iteration > 1:
                        _reset_workspace(
                            workspace,
                            f"reset before sample {iteration}",
                        )
                    setup_seconds = 0.0
                    if prepared is None:  # pragma: no cover - guarded above
                        raise RuntimeError("reusable execution was not prepared")
                    run = execute_prepared(
                        prepared,
                        workspace,
                        collect_metrics=not args.no_metrics,
                        preflight_gate=(
                            not args.no_preflight and iteration == 1
                        ),
                    )
                elif template is not None:
                    reset_plan = corpus.inspect_cleanup(workspace)
                    _print_cleanup_plan(
                        f"reset before sample {iteration}",
                        reset_plan,
                    )
                    reset_result = corpus.empty(workspace, reset_plan)
                    _print_cleanup_result(
                        f"reset before sample {iteration}",
                        target,
                        reset_result,
                        root_removed=False,
                    )
                    setup = corpus.materialize(
                        template,
                        workspace,
                        cleanup_plan=corpus.CleanupPlan(target, None, ()),
                    )
                    setup_seconds = setup.seconds
                    run = run_executor(
                        source,
                        workspace,
                        options=options,
                        collect_metrics=not args.no_metrics,
                        preflight_gate=not args.no_preflight,
                    )
                else:
                    _reset_workspace(
                        workspace,
                        f"reset before sample {iteration}",
                    )
                    setup_seconds = 0.0
                    run = run_executor(
                        source,
                        workspace,
                        options=options,
                        collect_metrics=not args.no_metrics,
                        preflight_gate=not args.no_preflight,
                    )
                _validate_executor_run(run)
                output_files, output_directories = expected_output_paths(run)
                manifest = corpus.record_outputs(
                    workspace,
                    files=output_files,
                    directories=output_directories,
                )
                if runs and reuse_preparation:
                    require_stable_copy_evidence(runs[0], run)
                runs.append(run)
                pipeline = copy_metrics_summary(run.copy_samples)
                record = {
                    "command": "executor",
                    "iteration": iteration,
                    "repeat": args.repeat,
                    "source": str(source),
                    "target": str(target),
                    "correspondence": "empty",
                    "deletion_policy": options.deletion_policy.value,
                    "preparation": "once" if reuse_preparation else "each",
                    "setup_seconds": setup_seconds,
                    "scan_seconds": (
                        None if reuse_preparation else run.scan_seconds
                    ),
                    "plan_seconds": (
                        None if reuse_preparation else run.plan_seconds
                    ),
                    "preflight_seconds": (
                        None if reuse_preparation else run.preflight_seconds
                    ),
                    "execute_seconds": run.execute_seconds,
                    "bytes": run.bytes_done,
                    "throughput_mib_s": run.throughput_mib_s,
                    "plan_fingerprint": str(run.plan.fingerprint),
                    "policy_fingerprint": run.plan.policy_fingerprint,
                    "operations": run.operation_kinds,
                    "outcomes": run.outcomes,
                    "recorder_calls": dict(run.recorder.calls),
                    "status": run.result.status.value,
                    "recording": run.execution_set.recording.value,
                    "diagnostics": not args.no_metrics,
                    "pipeline": pipeline,
                }
                readback = None
                if args.verify_readback:
                    readback = _readback(run, target)
                    _validate_readback(readback)
                    record["readback"] = readback
                records.append(record)
                print(
                    f"[{iteration}/{args.repeat}] execute: "
                    f"{run.bytes_done / 1024**2:.1f} MiB "
                    f"in {run.execute_seconds:.3f}s "
                    f"({run.throughput_mib_s:.1f} MiB/s) {run.outcomes}"
                )
                if not args.no_metrics:
                    _print_executor_diagnostics(run.execute_seconds, pipeline)
                if readback is not None:
                    print(
                        f"[{iteration}/{args.repeat}] readback: "
                        f"{readback['candidates']} candidates, "
                        f"{readback['bytes'] / 1024**2:.1f} MiB in "
                        f"{readback['seconds']:.3f}s {readback['results']}"
                    )
            if reuse_preparation:
                if prepared is None:  # pragma: no cover - guarded above
                    raise RuntimeError("reusable execution was not prepared")
                source_recheck_seconds = require_source_unchanged(prepared)
                print(
                    "source recheck: unchanged in "
                    f"{source_recheck_seconds:.3f}s"
                )
            if len(runs) > 1:
                _print_executor_summary(runs)
        except BaseException:
            print(
                f"workspace retained after failure: {target}; "
                f"{_workspace_recovery_receipt(workspace)}",
                file=sys.stderr,
            )
            raise
        if args.keep:
            print(f"kept tools workspace at {target}; outputs: {manifest}")
        else:
            _teardown_workspace(workspace, "successful executor teardown")
        _write_report(
            report_destination,
            {
                "format": REPORT_FORMAT,
                "command": "executor",
                "configuration": {
                    "source": str(source),
                    "target": str(target),
                    "template": None if template is None else str(template),
                    "correspondence": "empty",
                    "deletion_policy": options.deletion_policy.value,
                    "preparation": "once" if reuse_preparation else "each",
                    "repeat": args.repeat,
                    "preflight": not args.no_preflight,
                    "diagnostics": not args.no_metrics,
                    "verify_readback": args.verify_readback,
                    "workspace_retained": args.keep,
                    "plan_fingerprint": (
                        None if prepared is None else str(prepared.plan.fingerprint)
                    ),
                    "policy_fingerprint": (
                        None if prepared is None else prepared.plan.policy_fingerprint
                    ),
                },
                "batch_preparation": {
                    "scan_seconds": (
                        None if prepared is None else prepared.scan_seconds
                    ),
                    "plan_seconds": (
                        None if prepared is None else prepared.plan_seconds
                    ),
                    "preflight_seconds": (
                        runs[0].preflight_seconds
                        if reuse_preparation and runs
                        else None
                    ),
                },
                "batch_validation": {
                    "source_recheck_seconds": (
                        None
                        if source_recheck_seconds is None
                        else source_recheck_seconds
                    ),
                },
                "samples": records,
                "summary": _record_summary(
                    records,
                    seconds_key="execute_seconds",
                    throughput_key="throughput_mib_s",
                ),
            },
        )
    return 0


def _reset_workspace(workspace: corpus.WorkspaceClaim, action: str) -> None:
    plan = corpus.inspect_cleanup(workspace)
    _print_cleanup_plan(action, plan)
    result = corpus.empty(workspace, plan)
    _print_cleanup_result(action, plan.target, result, root_removed=False)


def _workspace_recovery_receipt(workspace: corpus.WorkspaceClaim) -> str:
    target = workspace.target
    manifest = corpus.outputs_for(target)
    try:
        plan = corpus.inspect_cleanup(workspace)
    except (corpus.CorpusError, OSError):
        if manifest.exists() or _path_is_reparse(manifest):
            return (
                f"output manifest {manifest} exists but does not validate against "
                "the live workspace; inspect with "
                f"python -m tools clean \"{target}\" --force-all --dry-run"
            )
        return (
            "no exact output manifest is available; inspect with "
            f"python -m tools clean \"{target}\" --force-all --dry-run"
        )
    if plan.manifest is None:
        return (
            "workspace is empty; retire it with "
            f"python -m tools clean \"{target}\""
        )
    return (
        f"exact outputs validate against {plan.manifest}; remove them with "
        f"python -m tools clean \"{target}\""
    )


def _teardown_workspace(workspace: corpus.WorkspaceClaim, action: str) -> None:
    plan = corpus.inspect_cleanup(workspace)
    _print_cleanup_plan(action, plan)
    result = corpus.teardown(workspace, plan)
    _print_cleanup_result(action, plan.target, result, root_removed=True)


def _print_cleanup_plan(action: str, plan: corpus.CleanupPlan) -> None:
    authority = (
        "explicit --force-all"
        if plan.forced
        else str(plan.manifest) if plan.manifest is not None else "empty workspace"
    )
    print(
        f"{action}: root {plan.target}; delete {plan.files} files, "
        f"{plan.directories} directories, {plan.bytes} bytes; authority {authority}"
    )
    if plan.forced:
        for entry in plan.entries:
            print(f"{action}: delete {entry.kind} {entry.path}")
    unrecognized_manifest = corpus.outputs_for(plan.target)
    if (
        plan.forced
        and plan.manifest is None
        and (
            unrecognized_manifest.exists()
            or _path_is_reparse(unrecognized_manifest)
        )
    ):
        print(
            f"{action}: preserve unrecognized sibling artifact "
            f"{unrecognized_manifest}"
        )


def _print_cleanup_result(
    action: str,
    target: Path,
    result: corpus.CleanupResult,
    *,
    root_removed: bool,
) -> None:
    ending = "root and marker removed" if root_removed else "root and marker retained"
    print(
        f"{action} complete: removed {result.files} files, "
        f"{result.directories} directories, {result.bytes} bytes from {target}; "
        f"{ending}; removed the exact pre-delete set described above"
    )


def _print_executor_diagnostics(
    execute_seconds: float,
    pipeline: dict[str, object],
) -> None:
    copies = int(pipeline["copies"])
    if copies == 0:
        print("    pipeline: no copy operations")
        return
    backend_seconds = float(pipeline["seconds"])
    outside_seconds = max(0.0, execute_seconds - backend_seconds)
    copied_mib = int(pipeline["bytes"]) / 1024**2
    chunks = ", ".join(
        f"{int(size) / 1024**2:.1f} MiB"
        for size in pipeline.get("chunk_sizes", [])
    )
    detail = (
        f"    pipeline: {copies} copies, {copied_mib:.1f} MiB; "
        f"backend {backend_seconds:.3f}s; "
        f"outside backend {outside_seconds:.3f}s"
    )
    if "reader_blocked_seconds" in pipeline:
        detail += (
            f"; reader blocked {float(pipeline['reader_blocked_seconds']):.3f}s"
            f"; writer starved {float(pipeline['writer_starved_seconds']):.3f}s"
            f"; high-water {int(pipeline['payload_high_water']) / 1024**2:.1f} MiB"
            f"; reserved {int(pipeline['reserved_bytes']) / 1024**2:.1f} MiB"
        )
    if chunks:
        detail += f"; chunks {chunks}"
    print(detail)


def _print_verifier_diagnostics(run) -> None:
    outside_seconds = max(
        0.0,
        run.run_seconds - run.open_seconds - run.read_seconds,
    )
    print(
        f"    reader: open {run.open_seconds:.3f}s; "
        f"read {run.read_seconds:.3f}s; "
        f"outside open/read {outside_seconds:.3f}s"
    )


def _print_verifier_summary(records: Sequence[dict[str, object]]) -> None:
    seconds = [float(record["run_seconds"]) for record in records]
    throughputs = [float(record["throughput_mib_s"]) for record in records]
    print(
        f"summary: n={len(records)}; run median {median(seconds):.3f}s; "
        f"min {min(seconds):.3f}s; max {max(seconds):.3f}s; "
        f"median sample throughput {median(throughputs):.1f} MiB/s"
    )


def _print_executor_summary(runs: Sequence[ExecutorRun]) -> None:
    seconds = [float(run.execute_seconds) for run in runs]
    throughputs = [float(run.throughput_mib_s) for run in runs]
    print(
        f"summary: n={len(runs)}; execute median {median(seconds):.3f}s; "
        f"min {min(seconds):.3f}s; max {max(seconds):.3f}s; "
        f"median sample throughput {median(throughputs):.1f} MiB/s"
    )


def _readback(run, target: Path) -> dict[str, object]:
    published = run.execution_set.published_evidence
    if not published:
        return {
            "candidates": 0,
            "expected_candidates": 0,
            "seconds": 0.0,
            "bytes": 0,
            "expected_bytes": 0,
            "throughput_mib_s": 0.0,
            "results": {},
            "recording": RecordingStatus.OK.value,
        }
    paths = {
        operation.op_id: operation.target_rel_path
        for operation in run.plan.operations
    }
    selection = post_copy_selection(target, published, paths)
    verified = run_post_copy(selection)
    _validate_verifier_run(verified, IntegrityResult.VERIFIED)
    expected_bytes = sum(
        candidate.expected_stat.size for candidate in selection.candidates
    )
    return {
        "candidates": len(selection.candidates),
        "expected_candidates": len(published),
        "seconds": verified.run_seconds,
        "bytes": verified.bytes_done,
        "expected_bytes": expected_bytes,
        "throughput_mib_s": verified.throughput_mib_s,
        "results": verified.results,
        "recording": verified.result.recording.value,
    }


def _validate_executor_run(run) -> None:
    if not isinstance(run.execution_set, ExecutionSet):
        raise ExecutorRigError(
            "invalid benchmark sample: executor returned an invalid execution set"
        )
    try:
        replace(run.execution_set)
    except (TypeError, ValueError) as error:
        raise ExecutorRigError(
            f"invalid benchmark sample: execution evidence is inconsistent: {error}"
        ) from error
    if run.result.status is not SessionState.COMPLETED:
        raise ExecutorRigError(
            f"invalid benchmark sample: executor settled {run.result.status.value} "
            f"with outcomes {run.outcomes}"
        )
    if (
        run.result.recording is not RecordingStatus.OK
        or run.result.audit is not RecordingStatus.OK
        or run.execution_set.recording is not RecordingStatus.OK
    ):
        raise ExecutorRigError(
            "invalid benchmark sample: executor recording or audit was degraded"
        )
    if (
        run.result.canceled
        or run.result.error is not None
        or run.result.disposition is not Disposition.RAN
        or run.result.bytes_done != run.result.bytes_total
    ):
        raise ExecutorRigError(
            "invalid benchmark sample: executor returned incomplete terminal truth"
        )
    if set(run.execution_set.status) != set(run.execution_set.selection):
        raise ExecutorRigError(
            "invalid benchmark sample: not every selected operation settled"
        )
    operations = {
        operation.op_id: operation for operation in run.plan.operations
    }
    result_items: dict[str, ItemOutcome] = {}
    for item in run.result.items:
        if not isinstance(item, ItemOutcome) or item.item_id in result_items:
            raise ExecutorRigError(
                "invalid benchmark sample: executor result item coverage is incomplete"
            )
        result_items[item.item_id] = item
    expected_item_ids = {str(op_id) for op_id in run.execution_set.selection}
    if set(result_items) != expected_item_ids:
        raise ExecutorRigError(
            "invalid benchmark sample: executor result item coverage is incomplete"
        )
    for op_id, outcome in run.execution_set.status.items():
        operation = operations[op_id]
        expected = (
            Outcome.SKIPPED
            if operation.kind is OperationKind.NOOP
            else Outcome.SUCCEEDED
        )
        if outcome is not expected:
            raise ExecutorRigError(
                "invalid benchmark sample: completed executor carried an "
                f"unexpected {outcome.value} {operation.kind.value} outcome"
            )
        item = result_items[str(op_id)]
        if (
            item.outcome is not outcome
            or item.kind != operation.kind.value
            or item.path != operation.target_rel_path
        ):
            raise ExecutorRigError(
                "invalid benchmark sample: executor result items disagree with "
                "the settled execution set"
            )
    byte_kinds = {
        OperationKind.COPY,
        OperationKind.UPDATE,
        OperationKind.MOVE_UPDATE,
    }
    expected_evidence = {
        op_id
        for op_id, outcome in run.execution_set.status.items()
        if outcome is Outcome.SUCCEEDED and operations[op_id].kind in byte_kinds
    }
    if set(run.execution_set.published_evidence) != expected_evidence:
        raise ExecutorRigError(
            "invalid benchmark sample: published copy evidence coverage is incomplete"
        )


def _validate_readback(readback: dict[str, object]) -> None:
    candidates = int(readback["candidates"])
    if candidates != int(readback["expected_candidates"]):
        raise VerifierRigError(
            "invalid benchmark sample: readback candidate coverage was incomplete"
        )
    expected = {} if candidates == 0 else {IntegrityResult.VERIFIED.value: candidates}
    if readback["results"] != expected:
        raise VerifierRigError(
            "invalid benchmark sample: readback did not verify every candidate; "
            f"observed {readback['results']}"
        )
    if readback["bytes"] != readback["expected_bytes"]:
        raise VerifierRigError(
            "invalid benchmark sample: readback byte coverage was incomplete"
        )
    if readback["recording"] != RecordingStatus.OK.value:
        raise VerifierRigError(
            "invalid benchmark sample: readback recording was degraded"
        )


def _run_generate_command(args: argparse.Namespace) -> int:
    requested_root = args.root.absolute()
    root = requested_root.resolve()
    with corpus.claim(requested_root) as workspace:
        reset_plan = corpus.inspect_cleanup(workspace)
        _print_cleanup_plan("corpus replacement", reset_plan)
        reset_result = corpus.empty(workspace, reset_plan)
        _print_cleanup_result(
            "corpus replacement",
            root,
            reset_result,
            root_removed=False,
        )
        try:
            result = corpus.generate(
                workspace,
                args.spec,
                seed=args.seed,
                cleanup_plan=corpus.CleanupPlan(root, None, ()),
            )
        except BaseException:
            print(
                f"corpus workspace retained after generation failure: {root}; "
                f"{_workspace_recovery_receipt(workspace)}",
                file=sys.stderr,
            )
            raise
    print(
        f"generated {result.files} files "
        f"({result.bytes_written / 1024**2:.1f} MiB) in {result.seconds:.2f}s; "
        f"outputs: {corpus.outputs_for(root)}"
    )
    return 0


def _run_clean_command(args: argparse.Namespace) -> int:
    requested_target = args.target.absolute()
    target = requested_target.resolve()
    if _reparse_component(requested_target) is not None or target != requested_target:
        raise corpus.CorpusError(
            "clean workspace path must not traverse an alias or reparse point: "
            f"{requested_target} resolves to {target}"
        )
    if not corpus.is_owned(requested_target):
        raise corpus.CorpusError(
            f"clean requires an existing valid tools ownership marker: {target}"
        )
    with corpus.claim(requested_target) as workspace:
        plan = (
            corpus.inspect_force_cleanup(workspace)
            if args.force_all
            else corpus.inspect_cleanup(workspace)
        )
        _print_cleanup_plan("clean", plan)
        if args.dry_run:
            print(f"clean dry-run complete: nothing was deleted from {target}")
            return 0
        result = (
            corpus.force_teardown(workspace, plan)
            if args.force_all
            else corpus.teardown(workspace, plan)
        )
        _print_cleanup_result("clean", target, result, root_removed=True)
        if args.force_all:
            unrecognized_manifest = corpus.outputs_for(target)
            if unrecognized_manifest.exists() or _path_is_reparse(
                unrecognized_manifest
            ):
                print(
                    "clean preserved an unrecognized sibling artifact at "
                    f"{unrecognized_manifest}; inspect and remove it explicitly "
                    "before reusing this workspace name"
                )
    return 0


def _record_summary(
    records: Sequence[dict[str, object]],
    *,
    seconds_key: str,
    throughput_key: str,
) -> dict[str, object]:
    seconds = [float(record[seconds_key]) for record in records]
    throughputs = [float(record[throughput_key]) for record in records]
    return {
        "n": len(records),
        "seconds": {
            "minimum": round(min(seconds), 6),
            "median": round(median(seconds), 6),
            "maximum": round(max(seconds), 6),
        },
        "throughput_mib_s": {
            "median": round(median(throughputs), 3),
        },
    }


def _write_report(
    destination: ArtifactDestination | None,
    report: dict[str, object],
) -> None:
    if destination is None:
        return
    path = destination.path
    temporary: Path | None = None
    descriptor: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = None
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if destination.existing_identity is None:
            if path.exists() or _path_is_reparse(path):
                raise ToolError(
                    f"JSON report destination appeared before publication: {path}"
                )
            os.rename(temporary, path)
        else:
            if _path_is_reparse(path) or not path.is_file():
                raise ToolError(
                    f"JSON report destination was replaced before publication: {path}"
                )
            details = path.stat()
            if (
                details.st_nlink != 1
                or (details.st_dev, details.st_ino)
                != destination.existing_identity
            ):
                raise ToolError(
                    f"JSON report destination was replaced before publication: {path}"
                )
            os.replace(temporary, path)
        temporary = None
    except ToolError:
        raise
    except OSError as error:
        raise ToolError(f"cannot publish JSON report {path}: {error}") from error
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
    print(f"wrote benchmark report: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
