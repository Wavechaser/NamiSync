"""Thin dispatcher-backed command-line adapter."""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from namisync.dispatcher import (
    Dispatcher,
    PreparedSession,
    WorkflowRegistration,
)
from namisync.workflows import (
    EXECUTION_KIND,
    PLAN_KIND,
    LocalWorkflowRuntime,
    PlanRequest,
    default_database_paths,
    sync_options,
)


EXIT_SUCCESS = 0
EXIT_USAGE = 2
EXIT_REFUSED = 3
EXIT_FAILED = 4
EXIT_CANCELED = 5
EXIT_PARTIAL = 6
EXIT_DEGRADED = 7


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nami-sync",
        description="Safety-first reviewed one-way file mirroring.",
    )
    subcommands = parser.add_subparsers(dest="command")

    sync = subcommands.add_parser(
        "sync", help="review and explicitly commit a one-way sync"
    )
    sync.add_argument("source", help="existing source directory")
    sync.add_argument("target", help="existing target directory")
    sync.add_argument(
        "--deletion-policy",
        choices=("trash", "additive"),
        default="trash",
        help="handling for target-only entries (default: trash)",
    )
    sync.add_argument("--database", help="override the local ledger path")
    sync.add_argument(
        "--history-database", help="override the independent history path"
    )

    history = subcommands.add_parser("history", help="browse retained sync history")
    history.add_argument("run", nargs="?", help="run token to show in detail")
    history.add_argument(
        "--limit", type=_positive_limit, default=20, help="maximum recent runs"
    )
    history.add_argument(
        "--history-database", help="override the independent history path"
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    input_stream = sys.stdin if stdin is None else stdin
    output = sys.stdout if stdout is None else stdout
    errors = sys.stderr if stderr is None else stderr
    parser = build_parser()
    if not arguments:
        parser.print_usage(errors)
        return EXIT_USAGE
    try:
        namespace = parser.parse_args(arguments)
    except SystemExit as error:
        return int(error.code)

    if namespace.command == "sync":
        return _run_sync(namespace, input_stream, output, errors)
    if namespace.command == "history":
        return _run_history(namespace, output, errors)
    parser.print_usage(errors)
    return EXIT_USAGE


def _run_sync(
    namespace: argparse.Namespace,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    try:
        source, target = _validated_paths(namespace.source, namespace.target)
    except (OSError, ValueError) as error:
        print(f"Input error: {_safe(error)}", file=stderr)
        print("Choose two existing, distinct, non-nested directories and retry.", file=stderr)
        return EXIT_USAGE

    default_ledger, default_history = default_database_paths()
    ledger = Path(namespace.database).resolve() if namespace.database else default_ledger
    history = (
        Path(namespace.history_database).resolve()
        if namespace.history_database
        else default_history
    )

    runtime = LocalWorkflowRuntime(ledger, history)
    dispatcher = _dispatcher(runtime)
    try:
        request = PlanRequest(
            request_id=uuid4().hex,
            source_path=str(source),
            target_path=str(target),
            options=sync_options(namespace.deletion_policy),
        )
        try:
            plan_session = dispatcher.submit(PLAN_KIND, request)
            plan_record = _wait_for_result(dispatcher, plan_session, stdout, stderr)
        except (OSError, ValueError) as error:
            print(f"Planning input error: {_safe(error)}", file=stderr)
            print(
                "Use accessible roots and distinct local database paths outside both roots.",
                file=stderr,
            )
            return EXIT_USAGE
        except Exception as error:
            print(f"Planning could not start: {_safe(error)}", file=stderr)
            return EXIT_FAILED
        finally:
            if "plan_session" in locals():
                _close_terminal(dispatcher, plan_session)

        if plan_record.result is None or plan_record.result.status.value != "completed":
            _render_terminal_error("Planning", plan_record, stderr)
            return _exit_for_record(plan_record)

        review = runtime.get_plan_review(request.request_id)
        _render_plan(review, stdout)
        if not review.can_commit:
            print(
                "Plan is not executable. Resolve the listed refusals, then plan again.",
                file=stderr,
            )
            return EXIT_REFUSED

        print("Type 'execute' to commit this exact plan, or press Enter to leave it uncommitted: ", end="", file=stdout)
        stdout.flush()
        confirmation = stdin.readline().strip()
        if confirmation != "execute":
            print("Plan left uncommitted; no files or ledger configuration changed.", file=stdout)
            return EXIT_SUCCESS

        execution_request = runtime.commit_plan(request.request_id)
        try:
            execution_session = dispatcher.submit(EXECUTION_KIND, execution_request)
            execution_record = _wait_for_result(
                dispatcher, execution_session, stdout, stderr
            )
        except Exception as error:
            print(f"Execution could not start: {_safe(error)}", file=stderr)
            return EXIT_FAILED
        finally:
            if "execution_session" in locals():
                _close_terminal(dispatcher, execution_session)

        _render_execution(
            execution_record,
            runtime.get_execution_details(str(execution_request.execution_set.run_id)),
            stdout,
            stderr,
        )
        return _exit_for_record(execution_record)
    finally:
        dispatcher.shutdown(timeout=10.0)
        runtime.close()


def _run_history(
    namespace: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    default_ledger, default_history = default_database_paths()
    history = (
        Path(namespace.history_database).resolve()
        if namespace.history_database
        else default_history
    )
    runtime = LocalWorkflowRuntime(default_ledger, history)
    try:
        if namespace.run:
            try:
                run = runtime.get_history(namespace.run)
            except KeyError:
                print(f"No retained history run named {_safe(namespace.run)}.", file=stderr)
                return EXIT_USAGE
            _render_history_run(run, stdout)
            return EXIT_SUCCESS

        runs = runtime.list_history(namespace.limit)
        if not runs:
            print("No retained history runs.", file=stdout)
            return EXIT_SUCCESS
        for run in runs:
            exception_counts = Counter(
                item.outcome
                for item in run.operations
                if item.outcome in {"blocked", "deferred"}
            )
            exceptions = (
                ""
                if not exception_counts
                else "  exceptions="
                f"blocked:{exception_counts['blocked']},"
                f"deferred:{exception_counts['deferred']}"
            )
            print(
                f"{run.run_token}  {run.started_at.isoformat()}  "
                f"{run.filesystem_status}  ledger={run.recording_status} "
                f"audit={run.audit_status}  {_safe(run.source_context)} -> "
                f"{_safe(run.target_context)}{exceptions}",
                file=stdout,
            )
        return EXIT_SUCCESS
    except Exception as error:
        print(f"History could not be read: {_safe(error)}", file=stderr)
        return EXIT_FAILED
    finally:
        runtime.close()


def _dispatcher(runtime: LocalWorkflowRuntime) -> Dispatcher:
    def prepare_plan(request: object) -> PreparedSession:
        prepared = runtime.prepare_plan(request)
        return PreparedSession.from_resource_keys(prepared.payload, prepared.resources)

    def prepare_execution(request: object) -> PreparedSession:
        prepared = runtime.prepare_execution(request)
        return PreparedSession.from_resource_keys(prepared.payload, prepared.resources)

    return Dispatcher(
        {
            PLAN_KIND: WorkflowRegistration(prepare_plan, runtime.open_plan),
            EXECUTION_KIND: WorkflowRegistration(
                prepare_execution, runtime.open_execution, supports_pause=True
            ),
        },
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )


def _wait_for_result(
    dispatcher: Dispatcher,
    session_id,
    stdout: TextIO,
    stderr: TextIO,
):
    stream = dispatcher.subscribe(session_id)
    last_seq: int | None = None
    cancel_requested = False
    try:
        while True:
            record = dispatcher.get(session_id)
            if record.result is not None:
                return record
            try:
                envelope = stream.next(timeout=0.1)
            except TimeoutError:
                continue
            except StopIteration:
                stream = dispatcher.subscribe(
                    session_id, None if last_seq is None else last_seq + 1
                )
                continue
            last_seq = envelope.seq
            body = envelope.body
            if all(hasattr(body, name) for name in ("items_done", "bytes_done")):
                current = getattr(body, "current_path", None)
                if current:
                    print(
                        f"Progress: {body.items_done} items, {body.bytes_done} bytes; "
                        f"{_safe(current)}",
                        file=stdout,
                    )
            if stream.ejected:
                stream = dispatcher.subscribe(session_id, last_seq + 1)
    except KeyboardInterrupt:
        if not cancel_requested:
            result = dispatcher.cancel(session_id)
            cancel_requested = result.accepted
            print(
                "Cancellation requested; waiting for cleanup and custody release.",
                file=stderr,
            )
        return _wait_for_result(dispatcher, session_id, stdout, stderr)
    finally:
        stream.close()


def _render_plan(review, output: TextIO) -> None:
    counts = Counter(operation.kind for operation in review.operations)
    exclusion_counts = Counter(
        operation.selection_outcome
        for operation in review.operations
        if operation.selection_outcome is not None
    )
    runnable_count = sum(
        operation.selection_outcome is None for operation in review.operations
    )
    print("NamiSync reviewed sync plan", file=output)
    print(f"Source: {_safe(review.source_path)}", file=output)
    print(f"Target: {_safe(review.target_path)}", file=output)
    print(f"Volumes: {review.source_volume} -> {review.target_volume}", file=output)
    print(
        f"Policy: {review.deletion_policy}; trash-on-update="
        f"{'enabled' if review.trash_on_update else 'disabled'}",
        file=output,
    )
    free = "unavailable" if review.free_bytes is None else str(review.free_bytes)
    print(
        f"Capacity: required={review.required_bytes}; free={free}; "
        f"reclaimable-temp={review.reclaimable_temp_bytes}",
        file=output,
    )
    print(f"Fingerprint: {review.fingerprint}", file=output)
    print(f"Selection digest: {review.selection_digest_hex}", file=output)
    print(
        "Operations: "
        + (", ".join(f"{kind}={count}" for kind, count in sorted(counts.items())) or "none"),
        file=output,
    )
    print(
        f"Selection: runnable={runnable_count}; "
        f"blocked={exclusion_counts['blocked']}; "
        f"deferred={exclusion_counts['deferred']}",
        file=output,
    )
    for operation in review.operations:
        origin_path = (
            operation.prior_target_path
            if operation.prior_target_path is not None
            else operation.source_path
        )
        origin = "" if origin_path is None else f"{_safe(origin_path)} -> "
        exclusion = (
            ""
            if operation.selection_outcome is None
            else f" {operation.selection_outcome.upper()}={operation.selection_reason}"
        )
        print(
            f"  {operation.kind:11} {origin}{_safe(operation.target_path)} "
            f"[{operation.reason}; {operation.content_bytes} bytes]{exclusion}",
            file=output,
        )
    for warning in review.warnings:
        print(f"Warning: {_safe(warning)}", file=output)
    for refusal in review.refusals:
        path = "" if refusal.path is None else f" at {_safe(refusal.path)}"
        detail = "" if not refusal.detail else f": {_safe(refusal.detail)}"
        print(f"Refusal: {refusal.code}{path}{detail}", file=output)


def _render_execution(record, details, output: TextIO, errors: TextIO) -> None:
    result = record.result
    if result is None:
        print("Execution ended without a typed result.", file=errors)
        return
    print(
        f"Execution: filesystem={result.status.value}; ledger={result.recording.value}; "
        f"audit={result.audit.value}; disposition={result.disposition.value}; "
        f"bytes={result.bytes_done}/{result.bytes_total}",
        file=output,
    )
    outcomes = Counter(
        item.outcome.value
        for item in result.operations
        if hasattr(item, "outcome")
    )
    if outcomes["blocked"] or outcomes["deferred"]:
        print(
            "Execution completed with exceptions: "
            f"blocked={outcomes['blocked']}; deferred={outcomes['deferred']}. "
            "Review the itemized exclusions and re-plan after resolving them.",
            file=output,
        )
    for item in result.operations:
        if not all(hasattr(item, name) for name in ("kind", "path", "outcome")):
            continue
        reason = "" if getattr(item, "reason", None) is None else f" ({_safe(item.reason)})"
        print(
            f"  {item.kind:11} {_safe(item.path)}: {item.outcome.value}{reason}",
            file=output,
        )
    if details.commitment_error:
        print(f"Refused: {_safe(details.commitment_error)}", file=errors)
    for refusal in details.refusals:
        path = "" if refusal.path is None else f" at {_safe(refusal.path)}"
        detail = "" if not refusal.detail else f": {_safe(refusal.detail)}"
        print(f"Refused: {refusal.code}{path}{detail}", file=errors)
    if result.error is not None:
        print(
            f"{result.error.type_name}: {_safe(result.error.message)}",
            file=errors,
        )
    if result.recording.value == "degraded":
        print("Filesystem work settled, but the ledger is behind; re-scan to converge it.", file=errors)
    if result.audit.value == "degraded":
        print("Filesystem work settled, but history could not confirm durable audit storage.", file=errors)


def _render_history_run(run, output: TextIO) -> None:
    print(f"Run: {run.run_token}", file=output)
    print(f"Activity: {run.activity_kind}", file=output)
    print(f"Source: {_safe(run.source_context)}", file=output)
    print(f"Target: {_safe(run.target_context)}", file=output)
    print(f"Started: {run.started_at.isoformat()}", file=output)
    print(f"Ended: {run.ended_at.isoformat()}", file=output)
    print(
        f"Result: filesystem={run.filesystem_status}; ledger={run.recording_status}; "
        f"audit={run.audit_status}; disposition={run.disposition}; "
        f"bytes={run.bytes_done}/{run.bytes_total}",
        file=output,
    )
    for item in run.operations:
        reason = "" if item.reason is None else f" ({_safe(item.reason)})"
        print(
            f"  {item.kind:11} {_safe(item.path)}: {item.outcome}{reason}",
            file=output,
        )
    if run.error:
        print(f"Error: {_safe(run.error)}", file=output)


def _render_terminal_error(label: str, record, errors: TextIO) -> None:
    result = record.result
    if result is None:
        print(f"{label} ended without a typed result.", file=errors)
    elif result.error is None:
        print(f"{label} ended with {result.status.value}.", file=errors)
    else:
        print(
            f"{label} failed: {result.error.type_name}: {_safe(result.error.message)}",
            file=errors,
        )


def _exit_for_record(record) -> int:
    result = record.result
    if result is None:
        return EXIT_FAILED
    status = result.status.value
    if status == "refused":
        return EXIT_REFUSED
    if status == "canceled":
        return EXIT_CANCELED
    if status != "completed":
        return EXIT_FAILED
    if result.recording.value == "degraded" or result.audit.value == "degraded":
        return EXIT_DEGRADED
    if any(
        getattr(getattr(item, "outcome", None), "value", None)
        in {"blocked", "deferred"}
        for item in result.operations
    ):
        return EXIT_PARTIAL
    return EXIT_SUCCESS


def _validated_paths(source: str, target: str) -> tuple[Path, Path]:
    source_path = Path(source).resolve(strict=True)
    target_path = Path(target).resolve(strict=True)
    if not source_path.is_dir():
        raise NotADirectoryError(f"source is not a directory: {source_path}")
    if not target_path.is_dir():
        raise NotADirectoryError(f"target is not a directory: {target_path}")
    source_key = os.path.normcase(str(source_path))
    target_key = os.path.normcase(str(target_path))
    try:
        common = os.path.normcase(os.path.commonpath((source_key, target_key)))
    except ValueError:
        common = ""
    if common in {source_key, target_key}:
        raise ValueError("source and target overlap")
    return source_path, target_path


def _close_terminal(dispatcher: Dispatcher, session_id) -> None:
    try:
        if dispatcher.get(session_id).result is not None:
            dispatcher.close(session_id)
    except Exception:
        pass


def _safe(value: object) -> str:
    if value is None:
        return "-"
    text = str(value)
    return "".join(
        character
        if character >= " " and character not in {"\x7f", "\x1b"}
        else f"\\x{ord(character):02x}"
        for character in text
    )


def _positive_limit(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("history limit must be positive")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
