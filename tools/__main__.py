"""Command line for the development tools: ``python -m tools ...``."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Sequence

from xxhash import xxh3_128

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import ItemOutcome, Progress
from namisync.core.execution import ExecutionSet
from namisync.core.integrity import IntegrityMode, IntegrityResult
from namisync.core.planning import DeletionPolicy, OperationKind, SyncOptions
from namisync.core.session import Disposition, SessionState

from . import corpus, sidecar
from .executor_rig import ExecutorRigError, copy_metrics_summary, run_executor
from .seams import constant_hasher_factory
from .verifier_rig import (
    VerifierRigError,
    load_baselines,
    post_copy_selection,
    prime_baselines,
    run_post_copy,
    run_verifier,
    scan_stats,
    synthetic_baselines,
)


class ToolError(RuntimeError):
    """A requested measurement would be unsafe or misleading."""


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
        help="sidecar path (default: <root>.baseline.jsonl beside the corpus)",
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
    verifier.add_argument("--json", type=Path, default=None, help="append JSON lines here")
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
    executor.add_argument("--json", type=Path, default=None)
    executor.set_defaults(handler=_run_executor_command)

    generate = subcommands.add_parser("generate", help="write a deterministic corpus")
    generate.add_argument("root", type=Path)
    generate.add_argument("spec", help="count@size groups, e.g. 2000@4KiB,100@1MiB")
    generate.add_argument("--seed", type=int, default=0)
    generate.set_defaults(handler=_run_generate_command)

    clean = subcommands.add_parser("clean", help="tear down a tool-owned workspace")
    clean.add_argument("target", type=Path)
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


def _ownership_artifacts(root: Path) -> tuple[Path, Path]:
    return corpus.marker_for(root).resolve(), corpus.lease_for(root).resolve()


def _reserved_root_artifacts(root: Path) -> tuple[Path, ...]:
    artifacts = list(_ownership_artifacts(root))
    try:
        artifacts.append(sidecar.sidecar_path_for(root).resolve())
    except sidecar.SidecarError:
        pass
    return tuple(artifacts)


def _validate_artifact_path(
    path: Path,
    label: str,
    *,
    roots: Sequence[tuple[str, Path]],
    reserved: Sequence[Path] = (),
) -> Path:
    resolved = path.resolve()
    for root_label, root in roots:
        if resolved == root or resolved.is_relative_to(root):
            raise ToolError(f"{label} must be outside the {root_label}: {resolved}")
    if resolved in reserved:
        raise ToolError(f"{label} collides with a tools ownership marker: {resolved}")
    if resolved.exists() and not resolved.is_file():
        raise ToolError(f"{label} path is not a file: {resolved}")
    if resolved.exists() and resolved.stat().st_nlink > 1:
        raise ToolError(
            f"{label} must not be an existing hard-linked file: {resolved}"
        )
    return resolved


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
    roots = (("verifier corpus", root),)
    ownership_artifacts = _ownership_artifacts(root)
    json_path = (
        None
        if args.json is None
        else _validate_artifact_path(
            args.json,
            "JSON report",
            roots=roots,
            reserved=ownership_artifacts,
        )
    )
    needs_sidecar = args.seed_baselines or (
        mode is not IntegrityMode.BASELINE and args.baselines == "sidecar"
    )
    sidecar_path = (
        _validate_artifact_path(
            args.sidecar or sidecar.sidecar_path_for(root),
            "baseline sidecar",
            roots=roots,
            reserved=ownership_artifacts,
        )
        if needs_sidecar
        else None
    )
    if sidecar_path is not None and json_path == sidecar_path:
        raise ToolError("JSON report and baseline sidecar paths must differ")

    if args.seed_baselines:
        if sidecar_path is None:  # pragma: no cover - guarded above
            raise RuntimeError("sidecar path was not resolved")
        evidence = prime_baselines(root, chunk_size=args.chunk_size)
        rows = sidecar.write(sidecar_path, evidence, identity_mode=args.identity)
        print(f"wrote {rows} baseline rows to {sidecar_path} ({args.identity} identity)")
        return 0

    # BASELINE refuses rows that already carry evidence, so it always runs bare.
    baselines = (
        None
        if mode is IntegrityMode.BASELINE
        else _resolve_baselines(args, root, sidecar_path, hasher)
    )

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
        _validate_verifier_run(run, expected)
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
            "scan_seconds": round(run.scan_seconds, 6),
            "run_seconds": round(run.run_seconds, 6),
            "throughput_mib_s": round(run.throughput_mib_s, 3),
            "open_seconds": round(run.open_seconds, 6),
            "read_seconds": round(run.read_seconds, 6),
            "results": run.results,
            "recording": run.result.recording.value,
        }
        _report(record, json_path)
        print(
            f"[{iteration}/{args.repeat}] {mode.value}: {run.items} items, "
            f"{run.bytes_done / 1024**2:.1f} MiB in {run.run_seconds:.3f}s "
            f"({run.throughput_mib_s:.1f} MiB/s) {run.results}"
        )
    return 0


def _resolve_baselines(
    args: argparse.Namespace, root: Path, sidecar_path: Path | None, hasher
) -> dict | None:
    if args.baselines == "none":
        return None
    if args.baselines == "synthetic":
        stats, _, _ = scan_stats(root)
        return synthetic_baselines(stats)
    if args.baselines == "sidecar":
        if sidecar_path is None:  # pragma: no cover - guarded by the caller
            raise RuntimeError("sidecar path was not resolved")
        stats, _, _ = scan_stats(root)
        evidence, report = load_baselines(sidecar_path, stats)
        print(f"sidecar {sidecar_path.name}: {report.summary()}")
        return evidence
    return prime_baselines(root, chunk_size=args.chunk_size, hasher_factory=hasher)


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
    target = args.target.resolve()
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

    artifact_roots = [("executor source", source), ("executor target", target)]
    if template is not None:
        artifact_roots.append(("target template", template))
    reserved = tuple(
        path
        for _, root in artifact_roots
        for path in _reserved_root_artifacts(root)
    )
    json_path = (
        None
        if args.json is None
        else _validate_artifact_path(
            args.json,
            "JSON report",
            roots=tuple(artifact_roots),
            reserved=reserved,
        )
    )

    options = SyncOptions(deletion_policy=DeletionPolicy(args.deletion_policy))
    with corpus.claim(target) as workspace:
        try:
            for iteration in range(1, args.repeat + 1):
                if template is not None:
                    setup = corpus.materialize(template, workspace)
                    setup_seconds = setup.seconds
                else:
                    corpus.empty(workspace)
                    setup_seconds = 0.0

                run = run_executor(
                    source,
                    workspace,
                    options=options,
                    collect_metrics=not args.no_metrics,
                    preflight_gate=not args.no_preflight,
                )
                _validate_executor_run(run)
                record = {
                    "command": "executor",
                    "iteration": iteration,
                    "source": str(source),
                    "target": str(target),
                    "correspondence": "empty",
                    "deletion_policy": options.deletion_policy.value,
                    "setup_seconds": round(setup_seconds, 6),
                    "scan_seconds": round(run.scan_seconds, 6),
                    "plan_seconds": round(run.plan_seconds, 6),
                    "preflight_seconds": round(run.preflight_seconds, 6),
                    "execute_seconds": round(run.execute_seconds, 6),
                    "bytes": run.bytes_done,
                    "throughput_mib_s": round(run.throughput_mib_s, 3),
                    "operations": run.operation_kinds,
                    "outcomes": run.outcomes,
                    "recorder_calls": dict(run.recorder.calls),
                    "status": run.result.status.value,
                    "recording": run.execution_set.recording.value,
                    "diagnostics": not args.no_metrics,
                    "pipeline": copy_metrics_summary(run.copy_samples),
                }
                readback = None
                if args.verify_readback:
                    readback = _readback(run, target)
                    _validate_readback(readback)
                    record["readback"] = readback
                _report(record, json_path)
                print(
                    f"[{iteration}/{args.repeat}] execute: "
                    f"{run.bytes_done / 1024**2:.1f} MiB "
                    f"in {run.execute_seconds:.3f}s "
                    f"({run.throughput_mib_s:.1f} MiB/s) {run.outcomes}"
                )
                if readback is not None:
                    print(
                        f"[{iteration}/{args.repeat}] readback: "
                        f"{readback['candidates']} candidates, "
                        f"{readback['bytes'] / 1024**2:.1f} MiB in "
                        f"{readback['seconds']:.3f}s {readback['results']}"
                    )
        finally:
            if args.keep:
                print(f"kept tools workspace at {target}")
            else:
                corpus.teardown(workspace)
    return 0


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
        "seconds": round(verified.run_seconds, 6),
        "bytes": verified.bytes_done,
        "expected_bytes": expected_bytes,
        "throughput_mib_s": round(verified.throughput_mib_s, 3),
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
    with corpus.claim(args.root.resolve()) as workspace:
        result = corpus.generate(workspace, args.spec, seed=args.seed)
    print(
        f"generated {result.files} files "
        f"({result.bytes_written / 1024**2:.1f} MiB) in {result.seconds:.2f}s"
    )
    return 0


def _run_clean_command(args: argparse.Namespace) -> int:
    target = args.target.resolve()
    with corpus.claim(target) as workspace:
        corpus.teardown(workspace)
    print(f"removed tools workspace {target}")
    return 0


def _report(record: dict[str, object], json_path: Path | None) -> None:
    if json_path is None:
        return
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with json_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError as error:
        raise ToolError(f"cannot append JSON report {json_path}: {error}") from error


if __name__ == "__main__":
    raise SystemExit(main())
