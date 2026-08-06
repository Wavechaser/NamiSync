"""Command line for the module rig: ``python -m tools.rig ...``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from xxhash import xxh3_128

from namisync.core.integrity import IntegrityMode
from namisync.core.planning import DeletionPolicy, SyncOptions

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
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.rig",
        description="In-vivo measurement rig for the executor and verifier.",
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
    verifier.add_argument("--repeat", type=int, default=1)
    verifier.add_argument("--no-tap", action="store_true", help="disable per-chunk timing")
    verifier.add_argument(
        "--null-hasher",
        action="store_true",
        help="constant-digest hasher; pair with a normal run to isolate hash cost",
    )
    verifier.add_argument("--json", type=Path, default=None, help="append JSON lines here")
    verifier.set_defaults(handler=_run_verifier_command)

    executor = subcommands.add_parser(
        "executor", help="measure one reviewed execution into a rig-owned target"
    )
    executor.add_argument("source", type=Path, help="source root to mirror")
    executor.add_argument("target", type=Path, help="rig-owned target workspace")
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
    executor.add_argument("--repeat", type=int, default=1)
    executor.add_argument("--keep", action="store_true", help="skip teardown")
    executor.add_argument("--no-preflight", action="store_true")
    executor.add_argument("--no-metrics", action="store_true")
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

    clean = subcommands.add_parser("clean", help="tear down a rig-owned workspace")
    clean.add_argument("target", type=Path)
    clean.set_defaults(handler=_run_clean_command)
    return parser


def _run_verifier_command(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    sidecar_path = args.sidecar or sidecar.sidecar_path_for(root)
    hasher = constant_hasher_factory if args.null_hasher else xxh3_128

    if args.seed_baselines:
        if args.null_hasher:
            raise VerifierRigError(
                "--seed-baselines writes durable evidence and cannot use "
                "--null-hasher's constant digest"
            )
        evidence = prime_baselines(root, chunk_size=args.chunk_size)
        rows = sidecar.write(sidecar_path, evidence, identity_mode=args.identity)
        print(f"wrote {rows} baseline rows to {sidecar_path} ({args.identity} identity)")
        return 0

    mode = IntegrityMode(args.mode)
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
        _report(record, args.json)
        print(
            f"[{iteration}/{args.repeat}] {mode.value}: {run.items} items, "
            f"{run.bytes_done / 1024**2:.1f} MiB in {run.run_seconds:.3f}s "
            f"({run.throughput_mib_s:.1f} MiB/s) {run.results}"
        )
    return 0


def _resolve_baselines(
    args: argparse.Namespace, root: Path, sidecar_path: Path, hasher
) -> dict | None:
    if args.baselines == "none":
        return None
    if args.baselines == "synthetic":
        stats, _, _ = scan_stats(root)
        return synthetic_baselines(stats)
    if args.baselines == "sidecar":
        stats, _, _ = scan_stats(root)
        evidence, report = load_baselines(sidecar_path, stats)
        print(f"sidecar {sidecar_path.name}: {report.summary()}")
        return evidence
    return prime_baselines(root, chunk_size=args.chunk_size, hasher_factory=hasher)


def _run_executor_command(args: argparse.Namespace) -> int:
    source = args.source.resolve()
    target = args.target.resolve()
    if not source.is_dir():
        raise ExecutorRigError(f"source root is not a directory: {source}")
    if target == source or source.is_relative_to(target) or target.is_relative_to(source):
        raise ExecutorRigError("source and target workspaces must not overlap")

    options = SyncOptions(deletion_policy=DeletionPolicy(args.deletion_policy))
    corpus.claim(target)
    try:
        for iteration in range(1, args.repeat + 1):
            if args.template is not None:
                setup = corpus.materialize(args.template.resolve(), target)
                setup_seconds = setup.seconds
            else:
                corpus.empty(target)
                setup_seconds = 0.0

            run = run_executor(
                source,
                target,
                options=options,
                collect_metrics=not args.no_metrics,
                preflight_gate=not args.no_preflight,
            )
            record = {
                "command": "executor",
                "iteration": iteration,
                "source": str(source),
                "target": str(target),
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
                "pipeline": copy_metrics_summary(run.copy_samples),
            }
            if args.verify_readback:
                record["readback"] = _readback(run, target)
            _report(record, args.json)
            print(
                f"[{iteration}/{args.repeat}] execute: {run.bytes_done / 1024**2:.1f} MiB "
                f"in {run.execute_seconds:.3f}s ({run.throughput_mib_s:.1f} MiB/s) "
                f"{run.outcomes}"
            )
    finally:
        if args.keep:
            print(f"kept rig workspace at {target}")
        else:
            corpus.teardown(target)
    return 0


def _readback(run, target: Path) -> dict[str, object]:
    published = run.execution_set.published_evidence
    if not published:
        return {"candidates": 0}
    paths = {
        operation.op_id: operation.target_rel_path
        for operation in run.plan.operations
    }
    selection = post_copy_selection(target, published, paths)
    verified = run_post_copy(selection)
    return {
        "candidates": len(selection.candidates),
        "seconds": round(verified.run_seconds, 6),
        "bytes": verified.bytes_done,
        "throughput_mib_s": round(verified.throughput_mib_s, 3),
        "results": verified.results,
    }


def _run_generate_command(args: argparse.Namespace) -> int:
    result = corpus.generate(args.root.resolve(), args.spec, seed=args.seed)
    print(
        f"generated {result.files} files "
        f"({result.bytes_written / 1024**2:.1f} MiB) in {result.seconds:.2f}s"
    )
    return 0


def _run_clean_command(args: argparse.Namespace) -> int:
    target = args.target.resolve()
    corpus.teardown(target)
    print(f"removed rig workspace {target}")
    return 0


def _report(record: dict[str, object], json_path: Path | None) -> None:
    if json_path is None:
        return
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
