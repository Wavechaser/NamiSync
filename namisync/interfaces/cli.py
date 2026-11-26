"""Thin dispatcher-backed command-line adapter."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import TextIO

from namisync.interfaces.command_ingress import (
    INVALID_COMMAND_REQUEST,
    arguments_within_ingress_bound,
)
from namisync.interfaces.service import (
    DatabaseAdmissionError,
    ExecutionAdmissionView,
    LocationResolutionError,
    NamiSyncService,
    SessionAdmissionRefused,
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
_LEDGER_MEMBERSHIP = {
    "current": "current",
    "earlier": "earlier (recorded against an earlier ledger; its ids are not looked up)",
    "unknown": "unknown (no usable ledger)",
}
_LAYOUT_CONTROL = re.compile(
    "[\u0000-\u001f\u007f-\u009f\u00ad\u061c\u200b\u200e-\u200f"
    "\u2028-\u202e\u2060-\u206f\ufeff\\[]"
)


class _OutputStream:
    """Render otherwise unencodable text without taking ownership of a stream."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def write(self, text: str) -> None:
        encoding = getattr(self._stream, "encoding", None)
        if encoding:
            try:
                text.encode(encoding)
            except UnicodeEncodeError:
                replacements = {}
                for character in set(text):
                    try:
                        character.encode(encoding)
                    except UnicodeEncodeError:
                        replacements[ord(character)] = f"[U+{ord(character):04X}]"
                text = text.translate(replacements)
        self._stream.write(text)

    def flush(self) -> None:
        self._stream.flush()


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        super().error(_safe(message))

    def _print_message(self, message: str, file: TextIO | None = None) -> None:
        super()._print_message(message, _OutputStream(file or sys.stderr))


def build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="namisync",
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
        "--database",
        help="ledger path read to mark which runs belong to it "
        "(default: the local ledger, unless --history-database is given)",
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

    check = subcommands.add_parser(
        "check", help="check the ledger and history databases as they are"
    )
    _add_database_arguments(check)

    backup = subcommands.add_parser(
        "backup", help="back up the ledger and history databases"
    )
    _add_database_arguments(backup)

    restore = subcommands.add_parser(
        "restore",
        help="replace the ledger or history database with a NamiSync backup",
    )
    restore.add_argument(
        "role",
        choices=("ledger", "history"),
        help="the database to replace",
    )
    restore.add_argument(
        "backup", metavar="BACKUP", help="a backup file written by namisync backup"
    )
    _add_database_arguments(restore)
    return parser


def _add_database_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database", help="override the local ledger path")
    parser.add_argument(
        "--history-database", help="override the independent history path"
    )


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
    output = _OutputStream(sys.stdout if stdout is None else stdout)
    errors = _OutputStream(sys.stderr if stderr is None else stderr)
    if not arguments_within_ingress_bound(arguments):
        print(INVALID_COMMAND_REQUEST, file=errors)
        return EXIT_USAGE
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
    if namespace.command in {"check", "backup", "restore"}:
        return _run_maintenance(namespace, output, errors)
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
        refusal = _database_refusal(
            service, stdout, stderr,
            roots=(namespace.source, namespace.target), paired=True,
            selected=_selected_databases(namespace, ledger, history),
        )
        if refusal is not None:
            return refusal
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
                _close_terminal(service, plan_session.session_id, stderr)

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
            execution_items: list[object] = []
            execution_record = _wait_for_result(
                service,
                execution_session.session_id,
                stdout,
                stderr,
                observed_items=execution_items,
            )
            execution_details = service.get_execution_details(
                execution_session.run_id
            )
        except SessionAdmissionRefused as error:
            print(f"Execution refused: {_safe(error)}", file=stderr)
            return EXIT_REFUSED
        except Exception as error:
            print(f"Execution could not start: {_safe(error)}", file=stderr)
            return EXIT_FAILED
        finally:
            if execution_session is not None:
                _close_terminal(service, execution_session.session_id, stderr)

        _render_execution(
            execution_record,
            execution_details,
            _terminal_items(
                service,
                execution_session.run_id,
                execution_record,
                execution_items,
                stderr,
            ),
            stdout,
            stderr,
        )
        return _exit_for_record(execution_record)
    finally:
        _close_service(service, stderr)


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
        refusal = _database_refusal(
            service, stdout, stderr,
            roots=() if root_path is None else (root_path,),
            selected_mount=namespace.selected_mount,
            selected_paths=selected_paths,
            selected=_selected_databases(namespace, ledger, history),
        )
        if refusal is not None:
            return refusal
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
                session = service.start_rebaseline(
                    **common, accept_current_evidence=namespace.accept_current_evidence
                )
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
        except SessionAdmissionRefused as error:
            print(
                f"{namespace.command.capitalize()} refused: {_safe(error)}",
                file=stderr,
            )
            return EXIT_REFUSED
        except Exception as error:
            print(
                f"{namespace.command.capitalize()} could not start: "
                f"{_safe(error)}",
                file=stderr,
            )
            return EXIT_FAILED

        try:
            try:
                observed_items: list[object] = []
                record = _wait_for_result(
                    service,
                    session.session_id,
                    stdout,
                    stderr,
                    observed_items=observed_items,
                )
                details = None
                try:
                    details = service.get_inventory_details(session.request_id)
                except KeyError:
                    pass
            except Exception as error:
                print(
                    f"{namespace.command.capitalize()} did not settle: "
                    f"{_safe(error)}",
                    file=stderr,
                )
                return EXIT_FAILED
        finally:
            _close_terminal(service, session.session_id, stderr)

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
                _terminal_items(
                    service,
                    session.request_id,
                    record,
                    observed_items,
                    stderr,
                ),
                stdout,
                stderr,
            )
        return _exit_for_record(record)
    finally:
        _close_service(service, stderr)


def _run_history(
    namespace: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    default_ledger, default_history = default_database_paths()
    history = (
        Path(namespace.history_database).resolve()
        if namespace.history_database
        else default_history
    )
    ledger = Path(namespace.database).resolve() if namespace.database else default_ledger
    # A history named alone is read without the default ledger, which is
    # then never opened or probed.
    read_ledger = bool(namespace.database) or not namespace.history_database
    try:
        service = NamiSyncService(ledger, history)
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
                run = service.get_history_summary(namespace.run, read_ledger=read_ledger)
            except KeyError:
                print(
                    f"No retained history run named {_safe(namespace.run)}.",
                    file=stderr,
                )
                return EXIT_USAGE
            _render_history_run(run, stdout)
            after_order = 0
            through_order = run.item_count
            while True:
                page = service.get_history_items(
                    namespace.run,
                    after_order=after_order,
                    through_order=through_order,
                    limit=256,
                )
                for retained in page.items:
                    _render_history_item(retained.item, stdout)
                if not page.has_more:
                    break
                after_order = page.next_after_order
            return EXIT_SUCCESS

        runs = service.list_history(namespace.limit, read_ledger=read_ledger)
        if not runs:
            print("No retained history runs.", file=stdout)
            return EXIT_SUCCESS
        if not read_ledger:
            print(
                "Ledger membership is unknown: no ledger was given, only "
                "--history-database.",
                file=stderr,
            )
        elif all(run.ledger_membership == "unknown" for run in runs):
            print(
                f"Ledger membership is unknown: no usable ledger at {_safe(ledger)}.",
                file=stderr,
            )
        for run in runs:
            exceptions = (
                ""
                if not run.blocked_count and not run.deferred_count
                else "  exceptions="
                f"blocked:{run.blocked_count},"
                f"deferred:{run.deferred_count}"
            )
            context = (
                f"{_safe(run.subject_kind)}={_safe(run.subject_id)}"
                if run.subject_id is not None
                else f"{_safe(run.source_context)} -> {_safe(run.target_context)}"
            )
            occurred_at = run.started_at or run.created_at
            axes = (
                f"state={run.current_state} completion=incomplete"
                if run.completion_status == "incomplete"
                else f"filesystem={run.filesystem_status} "
                f"integrity={run.integrity_status} "
                f"ledger={run.recording_status} "
                f"audit={run.audit_status}"
            )
            earlier = (
                "  (earlier ledger)" if run.ledger_membership == "earlier" else ""
            )
            print(
                f"{run.run_token}  {occurred_at.isoformat()}  "
                f"{run.activity_kind}  {run.headline}  "
                f"{axes}  {context}{exceptions}{earlier}",
                file=stdout,
            )
        return EXIT_SUCCESS
    except DatabaseAdmissionError as error:
        print(f"History admission refused: {_safe(error)}", file=stderr)
        return EXIT_REFUSED
    except Exception as error:
        print(f"History could not be read: {_safe(error)}", file=stderr)
        return EXIT_FAILED
    finally:
        _close_service(service, stderr)


def _wait_for_result(
    service: NamiSyncService,
    session_id: str,
    stdout: TextIO,
    stderr: TextIO,
    *,
    observed_items: list[object] | None = None,
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
        elif event.body_type in {"ItemOutcome", "IntegrityOutcome"}:
            if observed_items is not None:
                observed_items.append(SimpleNamespace(**event.body))
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


def _terminal_items(
    service: NamiSyncService,
    run_token: str,
    record: SessionRecordView,
    observed_items: list[object],
    errors: TextIO,
) -> tuple[object, ...]:
    """Return canonical retained items when the healthy audit is complete."""

    live_items = tuple(observed_items)
    if record.result is None or record.result.audit != "ok":
        return live_items
    try:
        summary = service.get_history_summary(run_token)
        if (
            summary.completion_status != "finalized"
            or summary.audit_status != "ok"
        ):
            raise RuntimeError("healthy terminal history is not finalized")
        retained_items: list[object] = []
        after_order = 0
        through_order = summary.item_count
        while True:
            page = service.get_history_items(
                run_token,
                after_order=after_order,
                through_order=through_order,
                limit=256,
            )
            retained_items.extend(retained.item for retained in page.items)
            if not page.has_more:
                break
            if page.next_after_order <= after_order:
                raise RuntimeError("history item page did not advance")
            after_order = page.next_after_order
        if len(retained_items) != through_order:
            raise RuntimeError("history item watermark is incomplete")
        return tuple(retained_items)
    except Exception as error:
        print(
            "Itemized terminal detail could not be reconstructed from "
            "healthy history; showing observed live items only: "
            f"{type(error).__name__}: {_safe(error)}",
            file=errors,
        )
        return live_items


def _database_refusal(
    service: NamiSyncService,
    stdout: TextIO,
    stderr: TextIO,
    *,
    roots: tuple[str, ...],
    selected_mount: str | None = None,
    selected_paths: tuple[str, ...] = (),
    paired: bool = False,
    selected: str | None = None,
) -> int | None:
    """Admit the pair for mutating work, migrating or completing it first.

    A NamiSync 0.1.0 pair is migrated, and a pair with one database missing
    gains a new one. Both wait for the command's own roots: when they are
    refused, or a database sits inside one, nothing is changed and the
    command's ordinary admission reports the input error. With no root
    (``--location-id``) a missing database is refused, never created.
    """

    contract = service.validate_database_contracts()
    migrated = ()
    if contract.state == "migration-required" or (contract.state == "incomplete" and roots):
        if not service.database_placement_admitted(
            roots, selected_mount=selected_mount,
            selected_paths=selected_paths, paired=paired,
        ):
            return None
        # --location-id names no root to check a new database's path
        # against, so it never permits creating one.
        contract, migrated, created = service.upgrade_database_contracts(create=bool(roots))
        if migrated:
            roles = " and ".join(f"{role} (v{version})" for role, version, _ in migrated)
            plural = "s" if len(migrated) > 1 else ""
            print(
                f"Updated the {roles} database{plural} written by NamiSync 0.1.0; "
                f"backup{plural} kept at: "
                + ", ".join(_safe(backup) for _, _, backup in migrated),
                file=stdout,
            )
        for role, path in created:
            print(
                f"Created a new history database at {_safe(path)} because it was "
                "missing; the existing ledger is kept."
                if role == "history" else
                f"Created a new ledger at {_safe(path)} because it was missing. The "
                "existing history is kept; its runs are shown as belonging to an "
                "earlier ledger.",
                file=stdout,
            )
    if contract.state == "incomplete" and not roots:
        # Missing cold, or found missing under the upgrade's claims.
        print(f"Database pair refused: {_safe(contract.reason)}.", file=stderr)
        print(
            f"The {'ledger' if contract.reason == 'ledger-missing' else 'history'} "
            "database is missing. A --location-id command does "
            "not create it, because no root is given to check its path against. "
            "Run the command with its ROOT, run a sync, or start NamiSync once to "
            "create it, then try again. "
            + ("Nothing else was changed." if migrated else "Nothing was changed."),
            file=stderr,
        )
    elif contract.state == "refused":
        print(f"Database pair refused: {_safe(contract.reason)}.", file=stderr)
        print(_safe(contract.guidance or contract.reset_direction), file=stderr)
    else:
        return None
    if selected is not None:
        print(selected, file=stderr)
    return EXIT_REFUSED


def _run_maintenance(
    namespace: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    """Check, back up or restore the pair as found; never migrate, complete or create."""

    command = namespace.command
    label = command.capitalize()
    default_ledger, default_history = default_database_paths()
    ledger = Path(namespace.database).resolve() if namespace.database else default_ledger
    history = (
        Path(namespace.history_database).resolve()
        if namespace.history_database
        else default_history
    )
    if ledger.resolve() == history.resolve():
        print(
            "Configuration error: the ledger and history databases must use "
            "distinct paths.",
            file=stderr,
        )
        print("Check --database and --history-database. Nothing was changed.", file=stderr)
        return EXIT_USAGE
    if command == "restore" and not _is_file(namespace.backup):
        print(
            f"Input error: {_safe(namespace.backup)} is not an existing file.",
            file=stderr,
        )
        print(
            "Give the path of a backup file written by namisync backup. "
            "Nothing was changed.",
            file=stderr,
        )
        return EXIT_USAGE
    selected = _selected_databases(namespace, ledger, history)
    try:
        # Opens no database and creates no file or folder.
        service = NamiSyncService(ledger, history)
    except (OSError, ValueError) as error:
        print(f"Configuration error: {_safe(error)}", file=stderr)
        print(
            "Use distinct local ledger, history, and settings paths.",
            file=stderr,
        )
        return EXIT_USAGE
    try:
        try:
            # Before the folder checks, so a path that cannot name a file is
            # never taken for a missing folder.
            service.validate_database_paths()
        except ValueError as error:
            print(f"Input error: a database path is not valid: {_safe(error)}", file=stderr)
            print(
                "Check --database and --history-database. Nothing was changed.",
                file=stderr,
            )
            return EXIT_USAGE
        # The claim files live beside the databases, and maintenance creates no folder.
        missing = [
            (role, path.parent)
            for role, path in (("ledger", ledger), ("history", history))
            if not path.parent.is_dir()
        ]
        if missing:
            if command == "check" and len(missing) == 2:
                _render_no_databases(ledger, history, stdout)
                return EXIT_SUCCESS
            for role, parent in missing:
                print(
                    f"{label} refused: the folder of the {role} database does not "
                    f"exist: {_safe(parent)}.",
                    file=stderr,
                )
            print(
                "Check --database and --history-database, or create the folder. "
                "Nothing was changed.",
                file=stderr,
            )
            return EXIT_USAGE
        try:
            if command == "check":
                return _render_check(
                    service.check_databases(), ledger, history, stdout, stderr,
                    selected=selected,
                )
            if command == "backup":
                return _render_backup(
                    service.backup_databases(), stdout, stderr, selected=selected,
                )
            return _render_restore(
                service.restore_database(namespace.role, namespace.backup),
                stdout, stderr, selected=selected,
            )
        except OSError as error:
            return _maintenance_os_error(label, error, stderr)
        except Exception as error:
            print(
                f"{label} could not finish: {type(error).__name__}: {_safe(error)}",
                file=stderr,
            )
            if command != "check":
                print(
                    "The databases may have changed. Run namisync check, and keep "
                    "every file beside them.",
                    file=stderr,
                )
                if selected is not None:
                    print(selected, file=stderr)
            return EXIT_FAILED
    finally:
        _close_service(service, stderr)


def _selected_databases(
    namespace: argparse.Namespace, ledger: Path, history: Path,
) -> str | None:
    """Name the custom pair, so guidance followed literally reaches it, or None."""

    if not namespace.database and not namespace.history_database:
        return None
    return (
        f"These databases were selected with --database {_option_path(ledger)} "
        f"--history-database {_option_path(history)}. Add the same options to any "
        "NamiSync command above."
    )


def _option_path(path: Path) -> str:
    # Meant to be pasted into PowerShell: single quotes keep $ and ` literal,
    # and the path is shown as it is unless it holds control characters.
    text = str(path)
    if _safe(text).replace("[[", "[") != text:
        return f'"{_safe(text)}"'
    return "'" + text.replace("'", "''") + "'"


def _is_file(value: str) -> bool:
    try:
        return Path(value).is_file()
    except (OSError, ValueError):
        return False


def _maintenance_os_error(label: str, error: OSError, stderr: TextIO) -> int:
    # Met only while taking the claim files, before anything is written.
    print(f"{label} could not start: {_safe(error)}", file=stderr)
    print(
        "NamiSync keeps a .claim file beside each database; check that both "
        "folders exist and are writable. Nothing was changed.",
        file=stderr,
    )
    return EXIT_FAILED


def _check_meaning(role: str, state: str, has_problems: bool) -> str | None:
    if state == "foreign-key-violations":
        return (
            "SQLite's integrity check passed, but some rows refer to rows that "
            "are not there (listed above). NamiSync still opens it, but namisync "
            "backup refuses it, so a copy of it cannot displace a backup that "
            "restores. With an earlier backup made by namisync backup, namisync "
            f"restore {role} <backup file> replaces it and keeps these files "
            "beside it."
        )
    if state == "missing":
        if has_problems:
            return (
                f"Only sidecar files of the {role} database remain (listed above), "
                "which NamiSync does not treat as a database. Keep them for "
                "inspection."
            )
        return (
            f"There is no {role} database at this path. If the other database is "
            "healthy, start NamiSync, or run a sync or inventory command, once to "
            f"create a new one, or put a backup back with namisync restore {role} "
            "<backup file>."
        )
    if state == "damaged":
        return (
            "This database is damaged or cannot be read as it stands (details "
            "above). Keep its files and their -wal and -shm sidecars. With a backup made by "
            f"namisync backup, namisync restore {role} <backup file> replaces it and "
            "keeps the damaged files beside it."
        )
    if state == "older":
        return (
            "Written by NamiSync 0.1.0. NamiSync updates it, keeping a backup "
            "beside it, the next time you start NamiSync or run a sync or "
            "inventory command."
        )
    if state == "newer":
        return "Written by a newer NamiSync. Use that version; this one will not change it."
    if state == "wrong-role":
        return (
            "This path holds the other kind of database. The paths given as "
            "--database and --history-database look swapped; check them."
        )
    if state == "unsupported":
        return (
            "This NamiSync cannot use or update this database; the lines above "
            "say what was found."
        )
    if state == "is-backup":
        return (
            "This ledger is a NamiSync backup copied into place by hand, and "
            "NamiSync will not use a backup as the live ledger. Put back the "
            "ledger it replaced, or run namisync restore ledger <backup file>, which "
            "keeps this file beside the restored ledger."
        )
    if state == "unavailable":
        return (
            "The database could not be read just now. Close other NamiSync "
            "windows and commands, check access to the file, then run "
            "namisync check again."
        )
    return None


def _render_no_databases(ledger: Path, history: Path, stdout: TextIO) -> None:
    print(
        f"No NamiSync databases were found at {_safe(ledger)} and {_safe(history)}.",
        file=stdout,
    )
    print(
        "There is nothing to check. NamiSync creates them the first time you "
        "start it or run a sync or inventory command.",
        file=stdout,
    )


def _render_check(
    result, ledger: Path, history: Path, stdout: TextIO, stderr: TextIO,
    *, selected: str | None = None,
) -> int:
    contract = result.contract
    if not result.checks:
        # Refused before it started: the maintenance claims were not taken.
        _print_refusal(contract, stderr, "Nothing was changed.", selected)
        return EXIT_REFUSED
    if str(contract.state) == "fresh":
        _render_no_databases(ledger, history, stdout)
        return EXIT_SUCCESS
    usable = True
    explained = False
    for check in result.checks:
        state = str(check.state)
        print(f"{check.role}: {state}", file=stdout)
        for problem in check.problems:
            print(f"  - {_safe(problem)}", file=stdout)
        if state != "ok":
            usable = False
        if state not in ("ok", "foreign-key-violations"):
            explained = True
        meaning = _check_meaning(check.role, state, bool(check.problems))
        if meaning is not None:
            print(f"  {meaning}", file=stdout)
    if str(contract.state) != "ready" and (
        not explained or contract.reset_direction is not None
    ):
        # Every role reads fine on its own, so nothing above explains the
        # pair; or the pair decides which databases a reset discards.
        usable = False
        print(f"Pair: {_safe(contract.reason)}.", file=stdout)
        print(_safe(contract.guidance or contract.reset_direction), file=stdout)
    if not usable and selected is not None:
        print(selected, file=stdout)
    return EXIT_SUCCESS if usable else EXIT_FAILED


def _print_refusal(
    contract, errors: TextIO, closing: str | None, selected: str | None = None,
) -> None:
    """Print a refused pair as the admission refusal does, then what happened.

    ``closing`` is decided from the result, never from the guidance text: the
    maintenance workflow's own refusals do not say whether anything changed.
    ``selected`` names a custom pair last.
    """

    guidance = contract.guidance or contract.reset_direction
    print(f"Database pair refused: {_safe(contract.reason)}.", file=errors)
    if guidance:
        print(_safe(guidance), file=errors)
    if closing is not None:
        print(closing, file=errors)
    if selected is not None:
        print(selected, file=errors)


# Backup refusals the maintenance workflow itself produces; any other is the
# pair's own admission refusal, whose shared text speaks for itself.
_BACKUP_MAINTENANCE_REFUSALS = ("database-in-use", "backup-failed")


def _render_backup(
    result, stdout: TextIO, stderr: TextIO, *, selected: str | None = None,
) -> int:
    contract = result.contract
    for backup in result.backups:
        print(f"Backed up the {backup.role} to {_safe(backup.path)}", file=stdout)
    if result.removed:
        print(
            f"Removed {len(result.removed)} older backup(s): "
            + ", ".join(_safe(path) for path in result.removed),
            file=stdout,
        )
    for path, reason in result.removal_failures:
        print(
            f"Warning: could not remove the older backup {_safe(path)}: "
            f"{_safe(reason)}. It is kept; remove it yourself if you no longer "
            "need it.",
            file=stderr,
        )
    state = str(contract.state)
    if state == "ready":
        return EXIT_SUCCESS
    if state == "fresh":
        print(
            "There is nothing to back up: no NamiSync databases exist at the "
            "given paths yet. Nothing was changed.",
            file=stderr,
        )
        return EXIT_REFUSED
    if result.backups:
        closing = "The backups listed above were kept."
    elif contract.reason in _BACKUP_MAINTENANCE_REFUSALS:
        closing = "Nothing was changed."
    else:
        closing = "No backup was written."
    _print_refusal(contract, stderr, closing, selected)
    return EXIT_FAILED if contract.reason == "backup-failed" else EXIT_REFUSED


def _render_restore(
    result, stdout: TextIO, stderr: TextIO, *, selected: str | None = None,
) -> int:
    contract = result.contract
    restore = result.restore
    if restore is None:
        # Every refusal here is the maintenance workflow's own: its result,
        # not its guidance, says what changed.
        reason = contract.reason
        unconfirmed = reason == "restore-unconfirmed"
        if result.kept is not None:
            closing = (
                f"Kept: {_safe(result.kept)}, the database as it was before this "
                "restore (with any -wal and -shm files beside it)."
            )
        elif unconfirmed:
            closing = None
        else:
            closing = "Nothing was changed."
        _print_refusal(contract, stderr, closing)
        if unconfirmed:
            print(
                "The result could not be confirmed. Run namisync check to see "
                "what state the databases are in, and keep every file beside "
                "them.",
                file=stderr,
            )
        if selected is not None:
            print(selected, file=stderr)
        return EXIT_FAILED if reason in ("restore-failed", "restore-unconfirmed") else EXIT_REFUSED
    role = restore.role
    print(f"Restored the {role} from {_safe(restore.source)}.", file=stdout)
    if restore.cut_at is not None:
        print(
            f"The backup was cut at {restore.cut_at.isoformat()}. History runs "
            "recorded after that time are now shown as belonging to an earlier "
            "ledger.",
            file=stdout,
        )
    if restore.kept is None:
        print(f"There was no {role} database to replace.", file=stdout)
    elif restore.kept_as == "backup":
        print(f"The replaced {role} was backed up to {_safe(restore.kept)}.", file=stdout)
    else:
        print(
            f"The replaced {role}'s files were kept at {_safe(restore.kept)} "
            "(with any -wal and -shm sidecars beside it).",
            file=stdout,
        )
    if str(contract.state) != "ready":
        print(f"Note: the database pair is not ready yet ({_safe(contract.reason)}).", file=stdout)
        print(_safe(contract.guidance or contract.reset_direction), file=stdout)
        if selected is not None:
            print(selected, file=stdout)
    return EXIT_SUCCESS


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
    if result.error is not None:
        print(_safe(result.error), file=errors)
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
            f"[{_safe(row.entry_kind)}; {baseline}; "
            f"{_safe(row.verification_state)}]",
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
    items: tuple[object, ...],
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
        item.result for item in items if item.item_type == "integrity"
    )
    if counts:
        print(
            "Integrity results: "
            + ", ".join(
                f"{name}={count}" for name, count in sorted(counts.items())
            ),
            file=output,
        )
    for item in items:
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
    if result.error is not None:
        print(_safe(result.error), file=errors)
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
    record: SessionRecordView,
    details,
    items: tuple[object, ...],
    output: TextIO,
    errors: TextIO,
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
        item.result for item in items if item.item_type == "operation"
    )
    if outcomes["blocked"] or outcomes["deferred"]:
        print(
            "Execution completed with exceptions: "
            f"blocked={outcomes['blocked']}; deferred={outcomes['deferred']}. "
            "Review the itemized exclusions and re-plan after resolving them.",
            file=output,
        )
    for item in items:
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
    print(f"Created: {run.created_at.isoformat()}", file=output)
    print(
        "Started: "
        + ("not started" if run.started_at is None else run.started_at.isoformat()),
        file=output,
    )
    if run.completion_status == "incomplete":
        phase = "none" if run.current_phase is None else _safe(run.current_phase)
        print("Ended: incomplete", file=output)
        print(
            f"Result: incomplete; state={run.current_state}; phase={phase}; "
            f"committed-through={run.last_committed_seq}; items={run.item_count}",
            file=output,
        )
    else:
        if run.ended_at is None:
            raise ValueError("finalized history is missing its end time")
        print(f"Ended: {run.ended_at.isoformat()}", file=output)
        print(
            f"Result: filesystem={run.filesystem_status}; "
            f"ledger={run.recording_status}; audit={run.audit_status}; "
            f"integrity={run.integrity_status}; headline={run.headline}; "
            f"disposition={run.disposition}; "
            f"canceled={str(run.canceled).lower()}; "
            f"bytes={run.bytes_done}/{run.bytes_total}",
            file=output,
        )
    print(
        f"Audit receipts: duplicates={run.duplicate_item_count}; "
        f"rejected={run.rejected_event_count}",
        file=output,
    )
    print(f"Ledger: {_LEDGER_MEMBERSHIP[run.ledger_membership]}", file=output)
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
    if run.error:
        print(f"Error: {_safe(run.error)}", file=output)


def _render_history_item(item, output: TextIO) -> None:
    reason = "" if item.reason is None else f" ({_safe(item.reason)})"
    print(
        f"  {item.phase}/{item.item_type}/{item.kind} "
        f"{_safe(item.path)}: {item.result}{reason}",
        file=output,
    )


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


def _close_terminal(
    service: NamiSyncService,
    session_id: str,
    stderr: TextIO,
) -> None:
    try:
        record = service.get_session(session_id)
    except Exception as error:
        print(
            "Session cleanup check failed unexpectedly; final shutdown will "
            f"retry: {type(error).__name__}: {_safe(error)}",
            file=stderr,
        )
        return
    if record.result is None:
        return
    try:
        service.close_session(session_id)
    except TimeoutError as error:
        print(
            "The terminal result and history outcome are already settled; "
            "cleanup remains pending and final shutdown will retry: "
            f"{_safe(error)}",
            file=stderr,
        )
    except Exception as error:
        print(
            "The terminal result and history outcome are already settled, but "
            "session cleanup failed unexpectedly; "
            "final shutdown will continue best-effort cleanup: "
            f"{type(error).__name__}: {_safe(error)}",
            file=stderr,
        )


def _close_service(service: NamiSyncService, stderr: TextIO) -> None:
    try:
        shutdown = service.close()
    except Exception as error:
        print(
            "NamiSync final cleanup failed unexpectedly; the command result "
            f"remains unchanged: {type(error).__name__}: {_safe(error)}",
            file=stderr,
        )
        return
    if shutdown.complete:
        return
    unfinished = ", ".join(shutdown.unfinished) or "none reported"
    custody = "released" if shutdown.custody_released else "still held"
    print(
        "NamiSync final cleanup is incomplete; the command result remains "
        f"unchanged. Unfinished sessions: {unfinished}; custody: {custody}.",
        file=stderr,
    )


def _safe(value: object) -> str:
    if value is None:
        return "-"
    return _LAYOUT_CONTROL.sub(
        lambda match: "[[" if match[0] == "[" else f"[U+{ord(match[0]):04X}]",
        str(value),
    )


def _positive_limit(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 256:
        raise argparse.ArgumentTypeError(
            "history limit must be between 1 and 256"
        )
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
