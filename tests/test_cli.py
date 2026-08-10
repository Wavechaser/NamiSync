from __future__ import annotations

import io
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import namisync.interfaces.cli as cli_module
from namisync.core.events import Envelope, ItemOutcome, SCHEMA_VERSION
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.integrity import (
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
)
from namisync.core.session import (
    Disposition,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    SessionId,
    SessionRecord,
    SessionState,
)
from namisync.db.history import HistoryContext, HistoryStore
from namisync.interfaces.cli import (
    EXIT_CANCELED,
    EXIT_DEGRADED,
    EXIT_FAILED,
    EXIT_MISMATCH,
    EXIT_PARTIAL,
    EXIT_REFUSED,
    EXIT_SUCCESS,
    EXIT_USAGE,
    EXIT_VERIFICATION_INCOMPLETE,
    _exit_for_record,
    _location_selection,
    _render_execution,
    _render_inventory,
    _render_integrity,
    _render_plan,
    _render_result_warnings,
    _render_resolution_error,
    build_parser,
    main,
)
from namisync.interfaces.service import (
    LocationResolutionError,
    LocationResolutionView,
    NamiSyncService,
    PreservationSettingsView,
    SemanticSettingsPatchView,
)
from namisync.modules.executor import NativeFileSystem
from namisync.workflows.models import PlanOperationView
from namisync.workflows.views import session_record_view

from _db_fixtures import FakeClock, NOW


def _arguments(source: Path, target: Path, ledger: Path, history: Path) -> list[str]:
    return [
        "sync",
        str(source),
        str(target),
        "--database",
        str(ledger),
        "--history-database",
        str(history),
    ]


def _record_for_result(result: OperationResult):
    return session_record_view(
        SessionRecord(
            SessionId("classification"),
            "sync-execution",
            result.status,
            (),
            b"payload",
            True,
            0,
            NOW,
            ended_at=NOW,
            result=result,
        )
    )


def _exception_items() -> tuple[ItemOutcome, ItemOutcome]:
    return (
        ItemOutcome(
            "blocked",
            "noop",
            "junction",
            Outcome.BLOCKED,
            reason="unsupported",
        ),
        ItemOutcome(
            "withheld",
            "trash",
            "old.bin",
            Outcome.DEFERRED,
            reason="incomplete-scan",
        ),
    )


def test_no_subcommand_prints_usage_and_returns_nonzero() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main([], stdout=stdout, stderr=stderr)

    assert result == EXIT_USAGE
    assert "usage:" in stderr.getvalue()


def test_stage5_commands_are_explicit_parser_choices() -> None:
    parser = build_parser()
    choices = next(
        action.choices for action in parser._actions if action.dest == "command"
    )

    assert set(choices) == {
        "sync",
        "history",
        "inventory",
        "baseline",
        "verify",
        "rebaseline",
    }


def test_location_parser_never_guesses_numeric_root_as_location_id() -> None:
    parser = build_parser()

    by_root = parser.parse_args(
        ["verify", "123", "--path", "a.bin", "--path", "b.bin"]
    )
    by_id = parser.parse_args(["verify", "--location-id", "123"])

    assert by_root.location == "123"
    assert by_root.location_id is None
    assert by_root.selected_paths == ["a.bin", "b.bin"]
    assert _location_selection(by_root) == ("123", None)
    assert by_id.location is None
    assert by_id.location_id == 123
    assert _location_selection(by_id) == (None, 123)


def test_location_command_requires_exactly_one_root_or_location_id(
    tmp_path: Path,
) -> None:
    for arguments in (
        ["verify"],
        ["verify", str(tmp_path), "--location-id", "7"],
    ):
        stdout = io.StringIO()
        stderr = io.StringIO()

        result = main(arguments, stdout=stdout, stderr=stderr)

        assert result == EXIT_USAGE
        assert "Provide exactly one ROOT or --location-id ID" in stderr.getvalue()


@pytest.mark.parametrize(
    ("arguments", "expected_guidance"),
    (
        (
            lambda root, ledger, settings: [
                "sync",
                str(root / "source"),
                str(root / "target"),
                "--database",
                str(ledger),
                "--history-database",
                str(settings),
            ],
            "distinct local ledger, history, and settings paths",
        ),
        (
            lambda root, ledger, settings: [
                "inventory",
                str(root),
                "--database",
                str(ledger),
                "--history-database",
                str(settings),
            ],
            "distinct local ledger, history, and settings paths",
        ),
    ),
)
def test_command_reports_service_configuration_error_without_traceback(
    tmp_path: Path,
    arguments,
    expected_guidance: str,
) -> None:
    (tmp_path / "source").mkdir()
    (tmp_path / "target").mkdir()
    ledger = tmp_path / "ledger.db"
    settings = tmp_path / "settings.json"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        arguments(tmp_path, ledger, settings),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_USAGE
    assert "Configuration error:" in stderr.getvalue()
    assert expected_guidance in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()


def test_history_reports_settings_alias_as_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger.db"
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(
        cli_module,
        "default_database_paths",
        lambda: (ledger, tmp_path / "history.db"),
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        ["history", "--history-database", str(settings)],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_USAGE
    assert "Configuration error:" in stderr.getvalue()
    assert "sibling settings.json" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()


def test_rebaseline_requires_selected_paths_and_explicit_intent() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["rebaseline", r"F:\library"])
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["rebaseline", r"F:\library", "--path", "a.bin"]
        )
    parsed = parser.parse_args(
        [
            "rebaseline",
            r"F:\library",
            "--path",
            "a.bin",
            "--accept-current-evidence",
        ]
    )

    assert parsed.selected_paths == ["a.bin"]
    assert parsed.accept_current_evidence is True


@pytest.mark.parametrize(
    ("state", "guidance"),
    [
        ("offline", "Connect the recorded volume"),
        ("ambiguous", "rerun with --mount MOUNT"),
        ("root_missing", "Restore the configured folder"),
        ("root_unavailable", "Fix permissions or device I/O"),
    ],
)
def test_location_resolution_output_is_actionable(
    state: str,
    guidance: str,
) -> None:
    output = io.StringIO()
    error = LocationResolutionError(
        LocationResolutionView(
            state=state,
            root_path=None,
            location_id=7,
            selected_mount=None,
            candidates=("F:\\", "G:\\"),
            detail="resolution detail",
        )
    )

    _render_resolution_error(error, output)

    assert f"Location is {state}: resolution detail." in output.getvalue()
    assert guidance in output.getvalue()
    if state == "ambiguous":
        assert "F:\\" in output.getvalue()
        assert "G:\\" in output.getvalue()


def test_queued_resolution_refusal_keeps_action_and_candidates() -> None:
    details = SimpleNamespace(
        request_id="queued",
        state="ambiguous",
        root_path=None,
        location_id=7,
        selected_mount=None,
        candidates=("F:\\", "G:\\"),
        detail="duplicate identity appeared while queued",
        selected_paths=(),
        observed_count=0,
        missing_count=0,
        complete=False,
    )
    output = io.StringIO()
    errors = io.StringIO()

    _render_integrity(
        "verify",
        _record_for_result(
            OperationResult(
                SessionState.REFUSED,
                disposition=Disposition.UNRUN,
            )
        ),
        details,
        output,
        errors,
    )

    assert "state=ambiguous" in output.getvalue()
    assert "rerun with --mount MOUNT" in output.getvalue()
    assert "F:\\" in output.getvalue()
    assert "G:\\" in output.getvalue()


def test_completed_execution_with_exclusions_is_reported_as_partial() -> None:
    blocked, deferred = _exception_items()
    record = session_record_view(
        SessionRecord(
            SessionId("partial"),
            "sync-execution",
            SessionState.COMPLETED,
            (),
            b"payload",
            True,
            0,
            NOW,
            ended_at=NOW,
            result=OperationResult(
                SessionState.COMPLETED,
                items=(blocked, deferred),
            ),
        )
    )
    details = SimpleNamespace(commitment_error=None, refusals=())
    stdout = io.StringIO()
    stderr = io.StringIO()

    _render_execution(record, details, stdout, stderr)

    assert _exit_for_record(record) == EXIT_PARTIAL
    assert "completed with exceptions: blocked=1; deferred=1" in stdout.getvalue()


def test_execution_rendering_preserves_interleaved_typed_item_order() -> None:
    record = _record_for_result(
        OperationResult(
            SessionState.COMPLETED,
            items=(
                IntegrityOutcome(
                    "integrity-first",
                    "row",
                    "location",
                    "first.bin",
                    IntegrityResult.VERIFIED,
                ),
                ItemOutcome(
                    "operation-second",
                    "copy",
                    "second.bin",
                    Outcome.SUCCEEDED,
                ),
            ),
        )
    )
    details = SimpleNamespace(commitment_error=None, refusals=())
    output = io.StringIO()

    _render_execution(record, details, output, io.StringIO())

    rendered = output.getvalue()
    assert rendered.index("verify/integrity first.bin") < rendered.index(
        "copy        second.bin"
    )


def test_final_partial_exit_precedes_refusal() -> None:
    record = _record_for_result(
        OperationResult(
            SessionState.REFUSED,
            disposition=Disposition.UNRUN,
            items=_exception_items(),
        )
    )

    assert _exit_for_record(record) == EXIT_PARTIAL


def test_final_partial_exit_precedes_cancellation() -> None:
    record = _record_for_result(
        OperationResult(
            SessionState.CANCELED,
            canceled=True,
            items=_exception_items(),
        )
    )

    assert _exit_for_record(record) == EXIT_PARTIAL


def test_final_partial_exit_precedes_degradation() -> None:
    record = _record_for_result(
        OperationResult(
            SessionState.COMPLETED,
            recording=RecordingStatus.DEGRADED,
            items=_exception_items(),
        )
    )

    assert _exit_for_record(record) == EXIT_PARTIAL


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (OperationResult(SessionState.COMPLETED), EXIT_SUCCESS),
        (
            OperationResult(
                SessionState.COMPLETED,
                items=(
                    ItemOutcome(
                        "noop",
                        "noop",
                        "file.bin",
                        Outcome.SKIPPED,
                    ),
                ),
            ),
            EXIT_SUCCESS,
        ),
        (
            OperationResult(
                SessionState.REFUSED,
                disposition=Disposition.UNRUN,
            ),
            EXIT_REFUSED,
        ),
        (OperationResult(SessionState.FAILED), EXIT_FAILED),
        (
            OperationResult(SessionState.CANCELED, canceled=True),
            EXIT_CANCELED,
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                recording=RecordingStatus.DEGRADED,
            ),
            EXIT_DEGRADED,
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                audit=RecordingStatus.DEGRADED,
            ),
            EXIT_DEGRADED,
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                items=(
                    IntegrityOutcome(
                        "integrity",
                        "row",
                        "location",
                        "file.bin",
                        IntegrityResult.MISMATCHED,
                        IntegrityReason.HASH_MISMATCH,
                    ),
                ),
            ),
            EXIT_MISMATCH,
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                phases=(
                    PhaseResult(
                        "verify",
                        PhaseStatus.INCOMPLETE,
                        0,
                        1,
                        0,
                        1,
                    ),
                ),
            ),
            EXIT_VERIFICATION_INCOMPLETE,
        ),
    ],
)
def test_final_headlines_map_to_documented_exit_codes(
    result: OperationResult,
    expected: int,
) -> None:
    assert _exit_for_record(_record_for_result(result)) == expected


@pytest.mark.parametrize(
    ("headline", "expected"),
    [
        ("success", EXIT_SUCCESS),
        ("all-noop", EXIT_SUCCESS),
        ("refused", EXIT_REFUSED),
        ("failed", EXIT_FAILED),
        ("canceled", EXIT_CANCELED),
        ("partial", EXIT_PARTIAL),
        ("degraded", EXIT_DEGRADED),
        ("mismatch", EXIT_MISMATCH),
        ("verification-incomplete", EXIT_VERIFICATION_INCOMPLETE),
    ],
)
def test_exit_adapter_uses_only_the_typed_classified_headline(
    monkeypatch: pytest.MonkeyPatch,
    headline: str,
    expected: int,
) -> None:
    record = _record_for_result(OperationResult(SessionState.COMPLETED))
    monkeypatch.setattr(
        cli_module,
        "classify_result",
        lambda _result: SimpleNamespace(headline=headline),
    )

    assert _exit_for_record(record) == expected


@pytest.mark.parametrize(
    ("mapping_ids", "expected"),
    [
        ((), "Mappings: none"),
        (("12",), "Mapping: 12"),
        (
            ("12", "34"),
            "Mappings: 12, 34; choose explicit paired roots",
        ),
    ],
)
def test_inventory_mapping_guidance_preserves_zero_one_many_roles(
    mapping_ids: tuple[str, ...],
    expected: str,
) -> None:
    class Service:
        def list_inventory(self, location_id, selected_paths):
            assert (location_id, selected_paths) == (7, ())
            return ()

        def mapping_ids_for_location(self, location_id):
            assert location_id == 7
            return mapping_ids

    details = SimpleNamespace(
        request_id="inventory",
        state="resolved",
        root_path=r"F:\library",
        location_id=7,
        selected_mount="F:\\",
        candidates=("F:\\",),
        detail=None,
        selected_paths=(),
        observed_count=0,
        missing_count=0,
        complete=True,
    )
    output = io.StringIO()
    errors = io.StringIO()

    _render_inventory(
        Service(),
        _record_for_result(OperationResult(SessionState.COMPLETED)),
        details,
        (),
        output,
        errors,
    )

    assert expected in output.getvalue()
    assert errors.getvalue() == ""


def test_recording_and_audit_warnings_remain_independent() -> None:
    result = _record_for_result(
        OperationResult(
            SessionState.COMPLETED,
            audit=RecordingStatus.DEGRADED,
        )
    ).result
    assert result is not None
    errors = io.StringIO()

    _render_result_warnings(result, errors)

    assert "History recording is degraded" in errors.getvalue()
    assert "Ledger recording is degraded" not in errors.getvalue()

    recording_result = _record_for_result(
        OperationResult(
            SessionState.COMPLETED,
            recording=RecordingStatus.DEGRADED,
        )
    ).result
    assert recording_result is not None
    recording_errors = io.StringIO()

    _render_result_warnings(recording_result, recording_errors)

    assert "rerun this command or activity" in recording_errors.getvalue()
    assert "History recording is degraded" not in recording_errors.getvalue()


def test_plan_review_renders_prior_target_for_rename_operations() -> None:
    operations = tuple(
        PlanOperationView(
            operation_id=str(index),
            kind=kind,
            source_path=target,
            target_path=target,
            prior_target_path=prior_target,
            reason=reason,
            blocked_reason=None,
            selection_outcome=None,
            selection_reason=None,
            content_bytes=content_bytes,
        )
        for index, kind, prior_target, target, reason, content_bytes in (
            (1, "recase", "keep.txt", "KEEP.txt", "case_mismatch", 0),
            (2, "move", "old.bin", "new.bin", "identity_move", 0),
            (3, "move_update", "before.dat", "after.dat", "content_changed", 12),
        )
    )
    review = SimpleNamespace(
        operations=operations,
        source_path=r"C:\source",
        target_path=r"D:\target",
        source_volume="source-volume",
        target_volume="target-volume",
        deletion_policy="trash",
        trash_on_update=True,
        semantic_settings=SimpleNamespace(
            filters=(),
            preservation=SimpleNamespace(
                preserve_ads=False,
                preserve_created=False,
                preserve_acl=False,
            ),
            propagate_source_casing=False,
        ),
        required_bytes=12,
        free_bytes=100,
        reclaimable_temp_bytes=0,
        fingerprint="fingerprint",
        selection_digest_hex="selection",
        warnings=(),
        refusals=(),
    )
    output = io.StringIO()

    _render_plan(review, output)

    rendered = output.getvalue()
    assert "keep.txt -> KEEP.txt" in rendered
    assert "old.bin -> new.bin" in rendered
    assert "before.dat -> after.dat" in rendered
    assert "KEEP.txt -> KEEP.txt" not in rendered


def test_recent_history_lists_safe_subset_exception_counts(tmp_path: Path) -> None:
    history = tmp_path / "history.db"
    record = SessionRecord(
        SessionId("session"),
        "sync-execution",
        SessionState.PENDING,
        (),
        b"payload",
        True,
        1,
        NOW,
    )
    blocked = ItemOutcome(
        "blocked",
        "noop",
        "junction",
        Outcome.BLOCKED,
        reason="unsupported",
    )
    with HistoryStore(history, clock=FakeClock()) as store:
        observer = store.observer(
            record,
            HistoryContext(
                "partial-run",
                "host",
                activity_kind="sync",
                source_context="source",
                target_context="target",
            ),
        )
        observer.on_event(
            Envelope(record.session_id, 1, NOW, SCHEMA_VERSION, blocked)
        )
        observer.finalize(
            OperationResult(SessionState.COMPLETED, items=(blocked,))
        )
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        ["history", "--history-database", str(history)],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS
    assert "exceptions=blocked:1,deferred:0" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_history_detail_streams_fixed_watermark_item_pages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    item_one = SimpleNamespace(
        phase="execute",
        item_type="operation",
        kind="copy",
        path="one.bin",
        result="succeeded",
        reason=None,
    )
    item_two = SimpleNamespace(
        phase="execute",
        item_type="operation",
        kind="copy",
        path="two.bin",
        result="succeeded",
        reason=None,
    )
    summary = SimpleNamespace(
        run_token="paged-run",
        activity_kind="sync",
        subject_kind=None,
        subject_id=None,
        source_context="source",
        target_context="target",
        created_at=NOW,
        started_at=NOW,
        ended_at=NOW,
        completion_status="finalized",
        current_state="completed",
        current_phase="execute",
        last_committed_seq=8,
        item_count=2,
        duplicate_item_count=3,
        rejected_event_count=1,
        filesystem_status="completed",
        recording_status="ok",
        audit_status="ok",
        integrity_status="not-run",
        headline="success",
        disposition="ran",
        canceled=False,
        bytes_done=2,
        bytes_total=2,
        phases=(),
        error=None,
    )
    calls: list[tuple[int, int | None, int]] = []

    class Service:
        def __init__(self, _ledger: Path, _history: Path) -> None:
            pass

        def get_history_summary(self, run_token: str):
            assert run_token == "paged-run"
            return summary

        def get_history_items(
            self,
            run_token: str,
            *,
            after_order: int,
            through_order: int | None,
            limit: int,
        ):
            assert run_token == "paged-run"
            calls.append((after_order, through_order, limit))
            if after_order == 0:
                return SimpleNamespace(
                    through_order=2,
                    next_after_order=1,
                    has_more=True,
                    items=(SimpleNamespace(item=item_one),),
                )
            return SimpleNamespace(
                through_order=2,
                next_after_order=2,
                has_more=False,
                items=(SimpleNamespace(item=item_two),),
            )

        def close(self):
            return SimpleNamespace(
                complete=True,
                unfinished=(),
                custody_released=True,
            )

    monkeypatch.setattr(cli_module, "NamiSyncService", Service)
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        [
            "history",
            "paged-run",
            "--history-database",
            str(tmp_path / "history.db"),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS
    assert calls == [(0, 2, 256), (1, 2, 256)]
    assert "one.bin" in stdout.getvalue()
    assert "two.bin" in stdout.getvalue()
    assert "Audit receipts: duplicates=3; rejected=1" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_terminal_cleanup_timeout_is_visible_without_raising() -> None:
    class Service:
        def get_session(self, session_id: str):
            assert session_id == "settled"
            return SimpleNamespace(result=object())

        def close_session(self, session_id: str) -> None:
            assert session_id == "settled"
            raise TimeoutError("only audit cleanup remains pending")

    stderr = io.StringIO()

    cli_module._close_terminal(Service(), "settled", stderr)

    warning = stderr.getvalue()
    assert "terminal result and history outcome are already settled" in warning
    assert "final shutdown will retry" in warning
    assert "only audit cleanup remains pending" in warning


def test_unexpected_terminal_cleanup_failure_is_visible_without_raising() -> None:
    class Service:
        def get_session(self, session_id: str):
            return SimpleNamespace(result=object())

        def close_session(self, session_id: str) -> None:
            raise RuntimeError("store drop failed")

    stderr = io.StringIO()

    cli_module._close_terminal(Service(), "settled", stderr)

    warning = stderr.getvalue()
    assert "terminal result and history outcome are already settled" in warning
    assert "failed unexpectedly" in warning
    assert "RuntimeError: store drop failed" in warning


def test_incomplete_final_service_cleanup_is_reported_without_raising() -> None:
    class Service:
        def close(self):
            return SimpleNamespace(
                complete=False,
                unfinished=("session-a", "session-b"),
                custody_released=False,
            )

    stderr = io.StringIO()

    cli_module._close_service(Service(), stderr)

    warning = stderr.getvalue()
    assert "final cleanup is incomplete" in warning
    assert "command result remains unchanged" in warning
    assert "session-a, session-b" in warning
    assert "custody: still held" in warning


def test_unexpected_final_service_cleanup_failure_is_visible() -> None:
    class Service:
        def close(self):
            raise RuntimeError("shutdown failed")

    stderr = io.StringIO()

    cli_module._close_service(Service(), stderr)

    warning = stderr.getvalue()
    assert "final cleanup failed unexpectedly" in warning
    assert "RuntimeError: shutdown failed" in warning


def test_history_list_rejects_an_unbounded_limit() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["history", "--limit", "257"])


def test_declined_plan_mutates_neither_files_nor_databases(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.txt").write_text("review only", encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS, (stdout.getvalue(), stderr.getvalue())
    assert not (target / "payload.txt").exists()
    assert not ledger.exists()
    assert not history.exists()
    assert "Policy: trash; trash-on-update=enabled" in stdout.getvalue()
    assert "Plan left uncommitted" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_cli_uses_semantic_settings_beside_explicit_ledger(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.txt").write_text("review only", encoding="utf-8")
    ledger = tmp_path / "isolated" / "ledger.db"
    history = tmp_path / "isolated" / "history.db"
    with NamiSyncService(ledger, history) as service:
        service.commit_semantic_settings(
            SemanticSettingsPatchView(
                filters=("*.tmp",),
                deletion_policy="additive",
                trash_on_update=False,
                preservation=PreservationSettingsView(
                    preserve_ads=False,
                    preserve_created=True,
                    preserve_acl=False,
                ),
                propagate_source_casing=True,
            )
        )
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS, (stdout.getvalue(), stderr.getvalue())
    assert "Policy: additive; trash-on-update=disabled" in stdout.getvalue()
    assert "Filters: *.tmp" in stdout.getvalue()
    assert (
        "Preservation: ads=disabled; created=enabled; acl=disabled; "
        "source-casing=enabled"
    ) in stdout.getvalue()
    assert (ledger.parent / "settings.json").exists()
    assert not ledger.exists()
    assert not history.exists()

    override_output = io.StringIO()
    override_errors = io.StringIO()
    overridden = main(
        [
            *_arguments(source, target, ledger, history),
            "--deletion-policy",
            "trash",
        ],
        stdin=io.StringIO("\n"),
        stdout=override_output,
        stderr=override_errors,
    )

    assert overridden == EXIT_SUCCESS
    assert "Policy: trash; trash-on-update=disabled" in override_output.getvalue()
    assert "Filters: *.tmp" in override_output.getvalue()
    assert "source-casing=enabled" in override_output.getvalue()
    assert override_errors.getvalue() == ""
    with NamiSyncService(ledger, history) as service:
        stored = service.read_semantic_settings()
    assert stored.filters == ("*.tmp",)
    assert stored.deletion_policy == "additive"
    assert not stored.trash_on_update
    assert stored.propagate_source_casing


def test_cli_typed_execute_acknowledges_an_irreversible_update(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.bin").write_bytes(b"reviewed replacement")
    (target / "payload.bin").write_bytes(b"old")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    with NamiSyncService(ledger, history) as service:
        service.commit_semantic_settings(
            SemanticSettingsPatchView(trash_on_update=False)
        )
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS, (stdout.getvalue(), stderr.getvalue())
    assert (target / "payload.bin").read_bytes() == b"reviewed replacement"
    assert "trash-on-update=disabled" in stdout.getvalue()
    assert "acknowledge this irreversible risk" in stdout.getvalue()
    assert "AttributeError" not in stderr.getvalue()
    assert stderr.getvalue() == ""


def test_cli_runs_real_reviewed_sync_and_browses_history(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    payload = b"NamiSync end-to-end\n"
    (source / "payload.bin").write_bytes(payload)
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS, (stdout.getvalue(), stderr.getvalue())
    assert (target / "payload.bin").read_bytes() == payload
    assert ledger.exists()
    assert history.exists()
    assert "filesystem=completed; ledger=ok; audit=ok" in stdout.getvalue()
    assert stderr.getvalue() == ""

    history_output = io.StringIO()
    history_errors = io.StringIO()
    history_result = main(
        ["history", "--history-database", str(history)],
        stdout=history_output,
        stderr=history_errors,
    )

    assert history_result == EXIT_SUCCESS
    assert "completed" in history_output.getvalue()
    assert str(source) in history_output.getvalue()
    assert history_errors.getvalue() == ""


def test_cli_verify_after_copy_renders_compound_typed_result(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.bin").write_bytes(b"verify after publish")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        [
            *_arguments(source, target, ledger, history),
            "--verify-after-copy",
        ],
        stdin=io.StringIO("execute\n"),
        stdout=stdout,
        stderr=stderr,
    )

    rendered = stdout.getvalue()
    assert result == EXIT_SUCCESS, (rendered, stderr.getvalue())
    assert "Phase execute: status=completed" in rendered
    assert "Phase verify: status=completed" in rendered
    assert "integrity=verified" in rendered
    assert "verify/integrity" in rendered
    assert stderr.getvalue() == ""


def test_cli_runs_inventory_and_integrity_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_data = tmp_path / "default-app-data"
    monkeypatch.setenv("LOCALAPPDATA", str(default_data))
    root = tmp_path / "library"
    root.mkdir()
    payload = root / "payload.bin"
    payload.write_bytes(b"before!")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"

    inventory_output = io.StringIO()
    inventory_errors = io.StringIO()
    inventory = main(
        [
            "inventory",
            str(root),
            "--database",
            str(ledger),
            "--history-database",
            str(history),
        ],
        stdout=inventory_output,
        stderr=inventory_errors,
    )
    location_match = re.search(r"\bid=(\d+)\b", inventory_output.getvalue())

    assert inventory == EXIT_SUCCESS, (
        inventory_output.getvalue(),
        inventory_errors.getvalue(),
    )
    assert location_match is not None
    assert "state=resolved" in inventory_output.getvalue()
    assert "Rows: 1" in inventory_output.getvalue()
    assert "Mappings: none" in inventory_output.getvalue()
    assert inventory_errors.getvalue() == ""
    assert ledger.exists()
    assert history.exists()
    location_id = location_match.group(1)

    common = [
        "--location-id",
        location_id,
        "--database",
        str(ledger),
        "--history-database",
        str(history),
    ]
    baseline_output = io.StringIO()
    baseline_errors = io.StringIO()
    baseline = main(
        ["baseline", *common],
        stdout=baseline_output,
        stderr=baseline_errors,
    )

    assert baseline == EXIT_SUCCESS, (
        baseline_output.getvalue(),
        baseline_errors.getvalue(),
    )
    assert "baselined=1" in baseline_output.getvalue()
    assert baseline_errors.getvalue() == ""

    added = root / "added.bin"
    added.write_bytes(b"new file")
    incomplete_output = io.StringIO()
    incomplete_errors = io.StringIO()
    incomplete = main(
        ["verify", *common],
        stdout=incomplete_output,
        stderr=incomplete_errors,
    )

    assert incomplete == EXIT_VERIFICATION_INCOMPLETE, (
        incomplete_output.getvalue(),
        incomplete_errors.getvalue(),
    )
    assert "baselined=1" in incomplete_output.getvalue()
    assert "Verification is incomplete" in incomplete_errors.getvalue()

    converged = main(
        ["verify", *common],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    assert converged == EXIT_SUCCESS

    original = payload.stat()
    payload.write_bytes(b"AFTER!!")
    os.utime(
        payload,
        ns=(original.st_atime_ns, original.st_mtime_ns),
    )
    mismatch_output = io.StringIO()
    mismatch_errors = io.StringIO()
    mismatch = main(
        ["verify", *common],
        stdout=mismatch_output,
        stderr=mismatch_errors,
    )

    assert mismatch == EXIT_MISMATCH, (
        mismatch_output.getvalue(),
        mismatch_errors.getvalue(),
    )
    assert "mismatched=1" in mismatch_output.getvalue()
    assert "Integrity mismatch" in mismatch_errors.getvalue()

    rebaseline_output = io.StringIO()
    rebaseline_errors = io.StringIO()
    accepted = main(
        [
            "rebaseline",
            *common,
            "--path",
            "payload.bin",
            "--accept-current-evidence",
        ],
        stdout=rebaseline_output,
        stderr=rebaseline_errors,
    )

    assert accepted == EXIT_SUCCESS, (
        rebaseline_output.getvalue(),
        rebaseline_errors.getvalue(),
    )
    assert "baselined=1" in rebaseline_output.getvalue()
    assert rebaseline_errors.getvalue() == ""
    final = main(
        ["verify", *common],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    assert final == EXIT_SUCCESS
    assert not (default_data / "NamiSync" / "ledger.db").exists()
    assert not (default_data / "NamiSync" / "history.db").exists()

    history_output = io.StringIO()
    history_errors = io.StringIO()
    listed = main(
        ["history", "--history-database", str(history)],
        stdout=history_output,
        stderr=history_errors,
    )
    baseline_line = next(
        line
        for line in history_output.getvalue().splitlines()
        if "  baseline  " in line
    )
    baseline_token = baseline_line.split(maxsplit=1)[0]
    detail_output = io.StringIO()
    detailed = main(
        [
            "history",
            baseline_token,
            "--history-database",
            str(history),
        ],
        stdout=detail_output,
        stderr=io.StringIO(),
    )

    assert listed == EXIT_SUCCESS
    assert history_errors.getvalue() == ""
    assert detailed == EXIT_SUCCESS
    assert "Activity: baseline" in detail_output.getvalue()
    assert "baseline/integrity/" in detail_output.getvalue()


def test_case_only_name_advisory_does_not_suppress_changed_content(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "KEEP.txt").write_bytes(b"changed source content")
    (target / "keep.txt").write_bytes(b"old")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS, (stdout.getvalue(), stderr.getvalue())
    assert (target / "keep.txt").read_bytes() == b"changed source content"
    assert [entry.name for entry in target.iterdir() if entry.is_file()] == ["keep.txt"]
    assert "update=1" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_successful_rerun_removes_prior_run_temp_from_touched_parent(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.bin").write_bytes(b"completed retry")
    orphan = target / (
        "abandoned.bin.synctmp-" + "1" * 32 + "-" + "2" * 32
    )
    orphan.write_bytes(b"partial copy")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_SUCCESS, (stdout.getvalue(), stderr.getvalue())
    assert (target / "payload.bin").read_bytes() == b"completed retry"
    assert not orphan.exists()


class _DriftingConfirmation(io.StringIO):
    def __init__(self, target: Path) -> None:
        super().__init__("execute\n")
        self._target = target

    def readline(self, *args, **kwargs) -> str:
        (self._target / "payload.txt").write_text("external writer", encoding="utf-8")
        return super().readline(*args, **kwargs)


def test_execution_fresh_preflight_refuses_drift_without_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.txt").write_text("reviewed source", encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=_DriftingConfirmation(target),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_REFUSED
    assert (target / "payload.txt").read_text(encoding="utf-8") == "external writer"
    assert not ledger.exists()
    assert history.exists()
    assert "destination_appeared" in stderr.getvalue()


def test_database_inside_managed_root_is_rejected_before_planning(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.txt").write_text("unchanged", encoding="utf-8")
    ledger = source / "ledger.db"
    history = tmp_path / "history.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == EXIT_USAGE
    assert not ledger.exists()
    assert not history.exists()
    assert not (target / "payload.txt").exists()
    assert "outside both roots" in stderr.getvalue()


def test_immediate_rerun_is_noop_and_each_explicit_run_is_retained(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload.txt").write_text("stable", encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"

    first = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    second_output = io.StringIO()
    second_errors = io.StringIO()
    second = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=second_output,
        stderr=second_errors,
    )

    assert first == EXIT_SUCCESS
    assert second == EXIT_SUCCESS, (second_output.getvalue(), second_errors.getvalue())
    assert "noop=1" in second_output.getvalue()
    assert "disposition=ran" in second_output.getvalue()

    history_output = io.StringIO()
    history_result = main(
        ["history", "--history-database", str(history)],
        stdout=history_output,
        stderr=io.StringIO(),
    )

    assert history_result == EXIT_SUCCESS
    assert history_output.getvalue().count(" -> ") == 2


@pytest.mark.skipif(os.name != "nt", reason="requires native Windows attributes")
def test_archive_attribute_created_by_copy_does_not_prevent_rerun_convergence(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    source_file = source / "payload.txt"
    source_file.write_text("stable", encoding="utf-8")
    filesystem = NativeFileSystem()
    filesystem._set_attributes(
        source_file,
        filesystem._get_attributes(source_file) & ~stat.FILE_ATTRIBUTE_ARCHIVE,
    )
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"

    first = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    target_file = target / "payload.txt"
    assert first == EXIT_SUCCESS
    assert not source_file.stat().st_file_attributes & stat.FILE_ATTRIBUTE_ARCHIVE
    assert target_file.stat().st_file_attributes & stat.FILE_ATTRIBUTE_ARCHIVE

    output = io.StringIO()
    errors = io.StringIO()
    second = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=output,
        stderr=errors,
    )

    assert second == EXIT_SUCCESS, (output.getvalue(), errors.getvalue())
    assert "noop=1" in output.getvalue()
    assert target_file.stat().st_file_attributes & stat.FILE_ATTRIBUTE_ARCHIVE


def test_second_sync_uses_recorded_correspondence_for_source_rename(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "before.txt").write_text("moved without copying", encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"

    first = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    (source / "before.txt").rename(source / "after.txt")
    output = io.StringIO()
    errors = io.StringIO()
    second = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=output,
        stderr=errors,
    )

    assert first == EXIT_SUCCESS
    assert second == EXIT_SUCCESS, (output.getvalue(), errors.getvalue())
    assert not (target / "before.txt").exists()
    assert (target / "after.txt").read_text(encoding="utf-8") == "moved without copying"
    assert "move=1" in output.getvalue()
    assert "bytes=0/0" in output.getvalue()


def test_attribute_only_change_is_planned_and_propagated(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    source_file = source / "payload.txt"
    target_file = target / "payload.txt"
    source_file.write_text("same content and mtime", encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"

    first = main(
        _arguments(source, target, ledger, history),
        stdin=io.StringIO("execute\n"),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    original_mtime = source_file.stat().st_mtime_ns
    source_file.chmod(stat.S_IREAD)
    try:
        assert source_file.stat().st_mtime_ns == original_mtime
        output = io.StringIO()
        errors = io.StringIO()
        second = main(
            _arguments(source, target, ledger, history),
            stdin=io.StringIO("execute\n"),
            stdout=output,
            stderr=errors,
        )

        assert first == EXIT_SUCCESS
        assert second == EXIT_SUCCESS, (output.getvalue(), errors.getvalue())
        assert "update=1" in output.getvalue()
        assert target_file.read_text(encoding="utf-8") == "same content and mtime"
        assert target_file.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY
    finally:
        source_file.chmod(stat.S_IWRITE)
        if target_file.exists():
            os.chmod(target_file, stat.S_IWRITE)


def test_real_module_and_console_entry_points_use_process_argv(tmp_path: Path) -> None:
    module = subprocess.run(
        [sys.executable, "-m", "namisync"],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    console = Path(sys.executable).with_name("nami-sync.exe")
    assert console.exists(), "editable/install build must provide nami-sync.exe"
    executable = subprocess.run(
        [str(console)],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert module.returncode == EXIT_USAGE
    assert executable.returncode == EXIT_USAGE
    assert "usage:" in module.stderr
    assert "usage:" in executable.stderr


def test_real_process_entry_points_run_sync_and_history(tmp_path: Path) -> None:
    console = Path(sys.executable).with_name("nami-sync.exe")
    entry_points = (
        [sys.executable, "-m", "namisync"],
        [str(console)],
    )
    for index, prefix in enumerate(entry_points):
        case = tmp_path / str(index)
        source = case / "source"
        target = case / "target"
        source.mkdir(parents=True)
        target.mkdir()
        (source / "payload.txt").write_text("real argv", encoding="utf-8")
        ledger = case / "ledger.db"
        history = case / "history.db"

        sync = subprocess.run(
            [*prefix, *_arguments(source, target, ledger, history)],
            cwd=Path(__file__).parents[1],
            input="execute\n",
            text=True,
            capture_output=True,
            check=False,
        )
        browsed = subprocess.run(
            [*prefix, "history", "--history-database", str(history)],
            cwd=Path(__file__).parents[1],
            text=True,
            capture_output=True,
            check=False,
        )

        assert sync.returncode == EXIT_SUCCESS, (sync.stdout, sync.stderr)
        assert (target / "payload.txt").read_text(encoding="utf-8") == "real argv"
        assert browsed.returncode == EXIT_SUCCESS, (browsed.stdout, browsed.stderr)
        assert "completed" in browsed.stdout


def test_real_process_entry_points_run_location_commands(
    tmp_path: Path,
) -> None:
    console = Path(sys.executable).with_name("nami-sync.exe")
    entry_points = (
        [sys.executable, "-m", "namisync"],
        [str(console)],
    )
    for index, prefix in enumerate(entry_points):
        case = tmp_path / str(index)
        root = case / "library"
        root.mkdir(parents=True)
        payload = root / "payload.txt"
        payload.write_text("initial", encoding="utf-8")
        ledger = case / "ledger.db"
        history = case / "history.db"
        databases = [
            "--database",
            str(ledger),
            "--history-database",
            str(history),
        ]

        inventory = subprocess.run(
            [*prefix, "inventory", str(root), *databases],
            cwd=Path(__file__).parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        baseline = subprocess.run(
            [*prefix, "baseline", str(root), *databases],
            cwd=Path(__file__).parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        payload.write_text("changed", encoding="utf-8")
        rebaseline = subprocess.run(
            [
                *prefix,
                "rebaseline",
                str(root),
                "--path",
                "payload.txt",
                "--accept-current-evidence",
                *databases,
            ],
            cwd=Path(__file__).parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        verify = subprocess.run(
            [*prefix, "verify", str(root), *databases],
            cwd=Path(__file__).parents[1],
            text=True,
            capture_output=True,
            check=False,
        )

        assert inventory.returncode == EXIT_SUCCESS, (
            inventory.stdout,
            inventory.stderr,
        )
        assert baseline.returncode == EXIT_SUCCESS, (
            baseline.stdout,
            baseline.stderr,
        )
        assert rebaseline.returncode == EXIT_SUCCESS, (
            rebaseline.stdout,
            rebaseline.stderr,
        )
        assert verify.returncode == EXIT_SUCCESS, (
            verify.stdout,
            verify.stderr,
        )
