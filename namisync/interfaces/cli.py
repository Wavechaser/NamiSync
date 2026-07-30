"""Thin dispatcher-backed command-line adapter."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import TextIO

from namisync.interfaces.service import (
    ExecutionAdmissionView,
    LocationResolutionError,
    NamiSyncService,
    SessionEventView,
    SessionRecordView,
    SyncPathInputError,
    classify_result,
    default_database_paths,
)


EXIT_SUCCESS = 0
EXIT_USAGE = 2
EXIT_REFUSED = 3
EXIT_FAILED = 4
EXIT_CANCELED = 5
EXIT_PARTIAL = 6
EXIT_DEGRADED = 7
EXIT_MISMATCH = 8
EXIT_VERIFICATION_INCOMPLETE = 9


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
        default=None,
        help="one-plan override for target-only entries (default: saved setting)",
    )
    sync.add_argument(
        "--verify-after-copy",
        action="store_true",
        help="verify every successfully published file before the run settles",
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

    inventory = subcommands.add_parser(
        "inventory", help="refresh and print one explicit location"
    )
    _add_location_arguments(inventory)

    baseline = subcommands.add_parser(
        "baseline", help="create evidence for files that have no baseline"
    )
    _add_location_arguments(baseline)

    verify = subcommands.add_parser(
        "verify", help="verify current files against retained evidence"
    )
    _add_location_arguments(verify)

    rebaseline = subcommands.add_parser(
        "rebaseline",
        help="explicitly accept current evidence for selected files",
    )
    _add_location_arguments(rebaseline, selected_paths_required=True)
    rebaseline.add_argument(
        "--accept-current-evidence",
        action="store_true",
        required=True,
        help="confirm that selected current bytes become the new evidence",
    )
    return parser


def _add_location_arguments(
    parser: argparse.ArgumentParser,
    *,
    selected_paths_required: bool = False,
) -> None:
    parser.add_argument(
        "location",
        nargs="?",
        metavar="ROOT",
        help="current root path (never interpreted as a location id)",
    )
    parser.add_argument(
        "--location-id",
        type=_positive_id,
        help="explicit retained ledger location id",
    )
    parser.add_argument(
        "--path",
        dest="selected_paths",
        action="append",
        default=[],
        required=selected_paths_required,
        metavar="RELATIVE_PATH",
        help="exact root-relative path; repeat for a selected scope",
    )
    parser.add_argument(
        "--mount",
        dest="selected_mount",
        help="explicit current mount from an ambiguity candidate list",
    )
    parser.add_argument("--database", help="override the local ledger path")
    parser.add_argument(
        "--history-database", help="override the independent history path"
    )


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
    if namespace.command in {
        "inventory",
        "baseline",
        "verify",
        "rebaseline",
    }:
        return _run_location_workflow(namespace, output, errors)
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

    try:
        service = NamiSyncService(ledger, history)
    except (OSError, ValueError) as error:
        print(f"Configuration error: {_safe(error)}", file=stderr)
        print(
            "Use distinct local ledger, history, and settings paths outside "
            "the managed roots.",
            file=stderr,
        )
        return EXIT_USAGE
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

        selection_preview = service.preview_selection(plan_session.request_id)
        irreversible_updates = selection_preview.irreversible_update_count
        if irreversible_updates:
            print(
                "Warning: "
                f"{irreversible_updates} update(s) will replace target bytes "
                "without moving the old versions to NamiSync trash.",
                file=stdout,
            )
        prompt = (
            "Type 'execute' to acknowledge this irreversible risk and commit "
            "the exact plan, or press Enter to leave it uncommitted: "
            if irreversible_updates
            else "Type 'execute' to commit this exact plan, or press Enter "
            "to leave it uncommitted: "
        )
        print(prompt, end="", file=stdout)
        stdout.flush()
        confirmation = stdin.readline().strip()
        if confirmation != "execute":
            print("Plan left uncommitted; no files or ledger configuration changed.", file=stdout)
            return EXIT_SUCCESS

        execution_session = None
        try:
            admission = service.start_execution(
                plan_session.request_id,
                verify_after_execute=namespace.verify_after_copy,
                destructive_acknowledged=True,
            )
            if isinstance(admission, ExecutionAdmissionView):
                print(
                    "Execution was not admitted: "
                    f"{admission.disposition}. Re-open the current plan "
                    "review and retry.",
                    file=stderr,
                )
                return EXIT_REFUSED
            execution_session = admission
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


def _run_location_workflow(
    namespace: argparse.Namespace,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    try:
        root_path, location_id = _location_selection(namespace)
    except ValueError as error:
        print(f"Location input error: {_safe(error)}", file=stderr)
        print(
            "Provide exactly one ROOT or --location-id ID and retry.",
            file=stderr,
        )
        return EXIT_USAGE

    default_ledger, default_history = default_database_paths()
    ledger = Path(namespace.database).resolve() if namespace.database else default_ledger
    history = (
        Path(namespace.history_database).resolve()
        if namespace.history_database
        else default_history
    )
    selected_paths = tuple(namespace.selected_paths)
    try:
        service = NamiSyncService(ledger, history)
    except (OSError, ValueError) as error:
        print(f"Configuration error: {_safe(error)}", file=stderr)
        print(
            "Use distinct local ledger, history, and settings paths outside "
            "the managed root.",
            file=stderr,
        )
        return EXIT_USAGE
    session = None
    try:
        try:
            common = {
                "root_path": root_path,
                "location_id": location_id,
                "selected_paths": selected_paths,
                "selected_mount": namespace.selected_mount,
            }
            if namespace.command == "inventory":
                session = service.start_inventory(**common)
            elif namespace.command == "baseline":
                session = service.start_baseline(**common)
            elif namespace.command == "verify":
                session = service.start_verify(**common)
            else:
                session = service.start_rebaseline(**common)
        except LocationResolutionError as error:
            _render_resolution_error(error, stderr)
            return EXIT_USAGE
        except KeyError as error:
            print(f"Unknown location: {_safe(error)}", file=stderr)
            print(
                "Check --location-id and --database, or run inventory ROOT "
                "to register the location.",
                file=stderr,
            )
            return EXIT_USAGE
        except (OSError, ValueError) as error:
            print(f"Location input error: {_safe(error)}", file=stderr)
            print(
                "Use an accessible root, canonical root-relative --path "
                "values, and a listed --mount candidate.",
                file=stderr,
            )
            return EXIT_USAGE
        except Exception as error:
            print(
                f"{namespace.command.capitalize()} could not start: "
                f"{_safe(error)}",
                file=stderr,
            )
            return EXIT_FAILED

        try:
            try:
                record = _wait_for_result(
                    service, session.session_id, stdout, stderr
                )
            except Exception as error:
                print(
                    f"{namespace.command.capitalize()} did not settle: "
                    f"{_safe(error)}",
                    file=stderr,
                )
                return EXIT_FAILED
        finally:
            _close_terminal(service, session.session_id)

        details = None
        try:
            details = service.get_inventory_details(session.request_id)
        except KeyError:
            pass
        if namespace.command == "inventory":
            _render_inventory(
                service,
                record,
                details,
                selected_paths,
                stdout,
                stderr,
            )
        else:
            _render_integrity(
                namespace.command,
                record,
                details,
                stdout,
                stderr,
            )
        return _exit_for_record(record)
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
    try:
        service = NamiSyncService(default_ledger, history)
    except (OSError, ValueError) as error:
        print(f"Configuration error: {_safe(error)}", file=stderr)
        print(
            "Use a history database path distinct from the ledger and "
            "its sibling settings.json.",
            file=stderr,
        )
        return EXIT_USAGE
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
                f"{run.activity_kind}  {run.headline}  "
                f"filesystem={run.filesystem_status} "
                f"integrity={run.integrity_status} "
                f"ledger={run.recording_status} "
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
        if event.body_type == "PhaseChanged":
            print(f"Phase: {_safe(event.body.get('phase'))}", file=stdout)
        elif event.body_type == "Progress":
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


def _location_selection(
    namespace: argparse.Namespace,
) -> tuple[str | None, int | None]:
    root_path = namespace.location
    location_id = namespace.location_id
    if (root_path is None) == (location_id is None):
        raise ValueError("location requires exactly one ROOT or --location-id")
    return root_path, location_id


def _render_resolution_error(
    error: LocationResolutionError,
    output: TextIO,
) -> None:
    resolution = error.resolution
    detail = (
        ""
        if resolution.detail is None
        else f": {_safe(resolution.detail)}"
    )
    print(
        f"Location is {resolution.state}{detail}.",
        file=output,
    )
    _render_resolution_guidance(resolution, output)


def _render_resolution_guidance(resolution, output: TextIO) -> None:
    if resolution.state == "offline":
        print(
            "Connect the recorded volume and retry. No retained rows were "
            "marked missing.",
            file=output,
        )
    elif resolution.state == "ambiguous":
        print(
            "Multiple mounted volumes share this identity; choose one "
            "explicitly and rerun with --mount MOUNT:",
            file=output,
        )
        for candidate in resolution.candidates:
            print(f"  {_safe(candidate)}", file=output)
    elif resolution.state == "root_missing":
        print(
            "Restore the configured folder or deliberately select its moved "
            "root. No retained rows were marked missing.",
            file=output,
        )
    elif resolution.state == "root_unavailable":
        print(
            "Fix permissions or device I/O, then retry. No scan or missing "
            "reconciliation occurred.",
            file=output,
        )
    else:
        print("Correct the selected location and retry.", file=output)


def _render_inventory(
    service: NamiSyncService,
    record: SessionRecordView,
    details,
    selected_paths: tuple[str, ...],
    output: TextIO,
    errors: TextIO,
) -> None:
    result = record.result
    if result is None:
        print("Inventory ended without a typed result.", file=errors)
        return
    _render_result_summary("Inventory", result, output)
    if details is not None:
        _render_inventory_details(details, output)
    if result.filesystem != "completed" or details is None:
        _render_result_warnings(result, errors)
        return
    if details.location_id is None:
        print("Inventory completed without a retained location id.", file=errors)
        return
    rows = service.list_inventory(details.location_id, selected_paths)
    print(f"Rows: {len(rows)}", file=output)
    for row in rows:
        baseline = "baseline" if row.has_baseline else "no-baseline"
        print(
            f"  {row.presence:11} {_safe(row.path)} "
            f"[{_safe(row.entry_kind)}; {baseline}]",
            file=output,
        )
    mappings = service.mapping_ids_for_location(details.location_id)
    if not mappings:
        print(
            "Mappings: none; this is a role-free location and no "
            "source/target role was inferred.",
            file=output,
        )
    elif len(mappings) == 1:
        print(f"Mapping: {mappings[0]}", file=output)
    else:
        print(
            "Mappings: "
            + ", ".join(mappings)
            + "; choose explicit paired roots for mapping work.",
            file=output,
        )
    _render_result_warnings(result, errors)


def _render_integrity(
    command: str,
    record: SessionRecordView,
    details,
    output: TextIO,
    errors: TextIO,
) -> None:
    result = record.result
    label = command.capitalize()
    if result is None:
        print(f"{label} ended without a typed result.", file=errors)
        return
    _render_result_summary(label, result, output)
    if details is not None:
        _render_inventory_details(details, output)
    _render_phases(result, output)
    counts = Counter(
        item.result for item in result.items if item.item_type == "integrity"
    )
    if counts:
        print(
            "Integrity results: "
            + ", ".join(
                f"{name}={count}" for name, count in sorted(counts.items())
            ),
            file=output,
        )
    for item in result.items:
        if item.item_type != "integrity":
            continue
        reason = "" if item.reason is None else f" ({_safe(item.reason)})"
        identity = (
            "unrecorded"
            if item.row_id is None or item.location_id is None
            else f"location={item.location_id}; row={item.row_id}"
        )
        print(
            f"  {item.phase}/{item.kind} {_safe(item.path)}: "
            f"{item.result}{reason}; {identity}; "
            f"recording={item.recording}",
            file=output,
        )
    _render_result_warnings(result, errors)


def _render_inventory_details(details, output: TextIO) -> None:
    scope = "full" if not details.selected_paths else (
        "selected=" + ",".join(_safe(path) for path in details.selected_paths)
    )
    print(
        f"Location: state={details.state}; id="
        f"{'-' if details.location_id is None else details.location_id}; "
        f"root={_safe(details.root_path)}; mount={_safe(details.selected_mount)}",
        file=output,
    )
    print(
        f"Inventory refresh: scope={scope}; observed={details.observed_count}; "
        f"missing={details.missing_count}; complete={str(details.complete).lower()}",
        file=output,
    )
    if details.detail:
        print(f"Location detail: {_safe(details.detail)}", file=output)
    if details.state != "resolved":
        _render_resolution_guidance(details, output)


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
    settings = review.semantic_settings
    print(
        "Filters: "
        + (
            ", ".join(_safe(pattern) for pattern in settings.filters)
            if settings.filters
            else "none"
        ),
        file=output,
    )
    print(
        "Preservation: "
        f"ads={'enabled' if settings.preservation.preserve_ads else 'disabled'}; "
        "created="
        f"{'enabled' if settings.preservation.preserve_created else 'disabled'}; "
        f"acl={'enabled' if settings.preservation.preserve_acl else 'disabled'}; "
        "source-casing="
        f"{'enabled' if settings.propagate_source_casing else 'disabled'}",
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
        f"audit={result.audit}; integrity={result.integrity}; "
        f"headline={result.headline}; disposition={result.disposition}; "
        f"canceled={str(result.canceled).lower()}; "
        f"bytes={result.bytes_done}/{result.bytes_total}",
        file=output,
    )
    _render_phases(result, output)
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
        reason = "" if item.reason is None else f" ({_safe(item.reason)})"
        if item.item_type == "operation":
            print(
                f"  {item.kind:11} {_safe(item.path)}: "
                f"{item.result}{reason}",
                file=output,
            )
        elif item.item_type == "integrity":
            identity = (
                "unrecorded"
                if item.row_id is None or item.location_id is None
                else f"location={item.location_id}; row={item.row_id}"
            )
            print(
                f"  {item.phase}/{item.kind} {_safe(item.path)}: "
                f"{item.result}{reason}; {identity}; "
                f"recording={item.recording}",
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
    _render_result_warnings(result, errors)


def _render_result_summary(label: str, result, output: TextIO) -> None:
    category = classify_result(result)
    print(
        f"{label}: headline={category.headline}; "
        f"filesystem={category.filesystem}; integrity={category.integrity}; "
        f"ledger={category.recording}; audit={category.audit}; "
        f"disposition={category.disposition}; "
        f"canceled={str(category.canceled).lower()}; "
        f"bytes={result.bytes_done}/{result.bytes_total}",
        file=output,
    )


def _render_phases(result, output: TextIO) -> None:
    for phase in result.phases:
        items_total = (
            "?"
            if phase.items_total is None
            else str(phase.items_total)
        )
        bytes_total = (
            "?"
            if phase.bytes_total is None
            else str(phase.bytes_total)
        )
        error = "" if phase.error is None else f"; error={_safe(phase.error)}"
        print(
            f"Phase {phase.phase}: status={phase.status}; "
            f"items={phase.items_done}/{items_total}; "
            f"bytes={phase.bytes_done}/{bytes_total}{error}",
            file=output,
        )


def _render_result_warnings(result, errors: TextIO) -> None:
    if result.integrity == "mismatch":
        print(
            "Integrity mismatch: current bytes do not match retained evidence.",
            file=errors,
        )
    elif result.headline == "verification-incomplete":
        print(
            "Verification is incomplete; review the typed item and phase "
            "reasons before trusting the location.",
            file=errors,
        )
    if result.recording == "degraded":
        print(
            "Ledger recording is degraded; fix the ledger path or access and "
            "rerun this command or activity to re-establish durable evidence.",
            file=errors,
        )
    if result.audit == "degraded":
        print(
            "History recording is degraded; check the history path or access "
            "before the next run.",
            file=errors,
        )


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
        f"audit={run.audit_status}; integrity={run.integrity_status}; "
        f"headline={run.headline}; disposition={run.disposition}; "
        f"canceled={str(run.canceled).lower()}; "
        f"bytes={run.bytes_done}/{run.bytes_total}",
        file=output,
    )
    for phase in run.phases:
        items_total = (
            "?" if phase.items_total is None else str(phase.items_total)
        )
        bytes_total = (
            "?" if phase.bytes_total is None else str(phase.bytes_total)
        )
        error = "" if phase.error is None else f"; error={_safe(phase.error)}"
        print(
            f"Phase {phase.phase}: status={phase.status}; "
            f"items={phase.items_done}/{items_total}; "
            f"bytes={phase.bytes_done}/{bytes_total}{error}",
            file=output,
        )
    for item in run.items:
        reason = "" if item.reason is None else f" ({_safe(item.reason)})"
        print(
            f"  {item.phase}/{item.item_type}/{item.kind} "
            f"{_safe(item.path)}: {item.result}{reason}",
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
    category = classify_result(result)
    return {
        "success": EXIT_SUCCESS,
        "all-noop": EXIT_SUCCESS,
        "refused": EXIT_REFUSED,
        "failed": EXIT_FAILED,
        "canceled": EXIT_CANCELED,
        "partial": EXIT_PARTIAL,
        "degraded": EXIT_DEGRADED,
        "mismatch": EXIT_MISMATCH,
        "verification-incomplete": EXIT_VERIFICATION_INCOMPLETE,
    }.get(category.headline, EXIT_FAILED)


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


def _positive_id(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "location id must be an integer"
        ) from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("location id must be positive")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
