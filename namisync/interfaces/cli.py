"""Thin dispatcher-backed command-line adapter."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import TextIO

from namisync.interfaces.service import (
    NamiSyncService,
    SessionEventView,
    SessionRecordView,
    SyncPathInputError,
    default_database_paths,
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
    default_ledger, default_history = default_database_paths()
    ledger = Path(namespace.database).resolve() if namespace.database else default_ledger
    history = (
        Path(namespace.history_database).resolve()
        if namespace.history_database
        else default_history
    )

    service = NamiSyncService(ledger, history)
    try:
        plan_session = None
        try:
            plan_session = service.start_plan(
                namespace.source,
                namespace.target,
                deletion_policy=namespace.deletion_policy,
            )
            plan_record = _wait_for_result(
                service, plan_session.session_id, stdout, stderr
            )
        except SyncPathInputError as error:
            print(f"Input error: {_safe(error)}", file=stderr)
            print(
                "Choose two existing, distinct, non-nested directories and retry.",
                file=stderr,
            )
            return EXIT_USAGE
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
            if plan_session is not None:
                _close_terminal(service, plan_session.session_id)

        if (
            plan_record.result is None
            or plan_record.result.filesystem != "completed"
        ):
            _render_terminal_error("Planning", plan_record, stderr)
            return _exit_for_record(plan_record)

        review = service.get_plan_review(plan_session.request_id)
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

        execution_session = None
        try:
            execution_session = service.start_execution(plan_session.request_id)
            execution_record = _wait_for_result(
                service, execution_session.session_id, stdout, stderr
            )
        except Exception as error:
            print(f"Execution could not start: {_safe(error)}", file=stderr)
            return EXIT_FAILED
        finally:
            if execution_session is not None:
                _close_terminal(service, execution_session.session_id)

        _render_execution(
            execution_record,
            service.get_execution_details(execution_session.run_id),
            stdout,
            stderr,
        )
        return _exit_for_record(execution_record)
    finally:
        service.close()


def _run_history(
    namespace: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    default_ledger, default_history = default_database_paths()
    history = (
        Path(namespace.history_database).resolve()
        if namespace.history_database
        else default_history
    )
    service = NamiSyncService(default_ledger, history)
    try:
        if namespace.run:
            try:
                run = service.get_history(namespace.run)
            except KeyError:
                print(f"No retained history run named {_safe(namespace.run)}.", file=stderr)
                return EXIT_USAGE
            _render_history_run(run, stdout)
            return EXIT_SUCCESS

        runs = service.list_history(namespace.limit)
        if not runs:
            print("No retained history runs.", file=stdout)
            return EXIT_SUCCESS
        for run in runs:
            exception_counts = Counter(
                item.result
                for item in run.items
                if item.item_type == "operation"
                and item.result in {"blocked", "deferred"}
            )
            exceptions = (
                ""
                if not exception_counts
                else "  exceptions="
                f"blocked:{exception_counts['blocked']},"
                f"deferred:{exception_counts['deferred']}"
            )
            context = (
                f"{_safe(run.subject_kind)}={_safe(run.subject_id)}"
                if run.subject_id is not None
                else f"{_safe(run.source_context)} -> {_safe(run.target_context)}"
            )
            print(
                f"{run.run_token}  {run.started_at.isoformat()}  "
                f"{run.filesystem_status}  ledger={run.recording_status} "
                f"audit={run.audit_status}  {context}{exceptions}",
                file=stdout,
            )
        return EXIT_SUCCESS
    except Exception as error:
        print(f"History could not be read: {_safe(error)}", file=stderr)
        return EXIT_FAILED
    finally:
        service.close()


def _wait_for_result(
    service: NamiSyncService,
    session_id: str,
    stdout: TextIO,
    stderr: TextIO,
) -> SessionRecordView:
    cancel_requested = False

    def receive(update: SessionEventView | SessionRecordView) -> None:
        if isinstance(update, SessionRecordView):
            return
        event = update
        if event.body_type == "Progress":
            current = event.body.get("current_path")
            if current:
                print(
                    f"Progress: {event.body['items_done']} items, "
                    f"{event.body['bytes_done']} bytes; "
                    f"{_safe(current)}",
                    file=stdout,
                )
    current = service.observe(session_id, receive)
    if current.result is not None:
        return current
    try:
        while True:
            try:
                return service.wait(session_id)
            except KeyboardInterrupt:
                if not cancel_requested:
                    result = service.cancel(session_id)
                    cancel_requested = result.accepted
                    print(
                        "Cancellation requested; waiting for cleanup and "
                        "custody release.",
                        file=stderr,
                    )
    finally:
        service.unsubscribe(session_id)


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


def _render_execution(
    record: SessionRecordView, details, output: TextIO, errors: TextIO
) -> None:
    result = record.result
    if result is None:
        print("Execution ended without a typed result.", file=errors)
        return
    print(
        f"Execution: filesystem={result.filesystem}; ledger={result.recording}; "
        f"audit={result.audit}; disposition={result.disposition}; "
        f"bytes={result.bytes_done}/{result.bytes_total}",
        file=output,
    )
    outcomes = Counter(
        item.result for item in result.items if item.item_type == "operation"
    )
    if outcomes["blocked"] or outcomes["deferred"]:
        print(
            "Execution completed with exceptions: "
            f"blocked={outcomes['blocked']}; deferred={outcomes['deferred']}. "
            "Review the itemized exclusions and re-plan after resolving them.",
            file=output,
        )
    for item in result.items:
        if item.item_type != "operation":
            continue
        reason = "" if item.reason is None else f" ({_safe(item.reason)})"
        print(
            f"  {item.kind:11} {_safe(item.path)}: {item.result}{reason}",
            file=output,
        )
    if details.commitment_error:
        print(f"Refused: {_safe(details.commitment_error)}", file=errors)
    for refusal in details.refusals:
        path = "" if refusal.path is None else f" at {_safe(refusal.path)}"
        detail = "" if not refusal.detail else f": {_safe(refusal.detail)}"
        print(f"Refused: {refusal.code}{path}{detail}", file=errors)
    if result.error is not None:
        print(_safe(result.error), file=errors)
    if result.recording == "degraded":
        print("Filesystem work settled, but the ledger is behind; re-scan to converge it.", file=errors)
    if result.audit == "degraded":
        print("Filesystem work settled, but history could not confirm durable audit storage.", file=errors)


def _render_history_run(run, output: TextIO) -> None:
    print(f"Run: {run.run_token}", file=output)
    print(f"Activity: {run.activity_kind}", file=output)
    if run.subject_id is not None:
        print(
            f"Subject: {_safe(run.subject_kind)}={_safe(run.subject_id)}",
            file=output,
        )
    else:
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
    for item in run.items:
        reason = "" if item.reason is None else f" ({_safe(item.reason)})"
        print(
            f"  {item.kind:11} {_safe(item.path)}: {item.result}{reason}",
            file=output,
        )
    if run.error:
        print(f"Error: {_safe(run.error)}", file=output)


def _render_terminal_error(
    label: str, record: SessionRecordView, errors: TextIO
) -> None:
    result = record.result
    if result is None:
        print(f"{label} ended without a typed result.", file=errors)
    elif result.error is None:
        print(f"{label} ended with {result.filesystem}.", file=errors)
    else:
        print(f"{label} failed: {_safe(result.error)}", file=errors)


def _exit_for_record(record: SessionRecordView) -> int:
    result = record.result
    if result is None:
        return EXIT_FAILED
    return {
        "success": EXIT_SUCCESS,
        "all-noop": EXIT_SUCCESS,
        "refused": EXIT_REFUSED,
        "failed": EXIT_FAILED,
        "canceled": EXIT_CANCELED,
        "partial": EXIT_PARTIAL,
        "degraded": EXIT_DEGRADED,
    }.get(result.headline, EXIT_FAILED)


def _close_terminal(service: NamiSyncService, session_id: str) -> None:
    try:
        if service.get_session(session_id).result is not None:
            service.close_session(session_id)
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
