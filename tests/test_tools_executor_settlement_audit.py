from __future__ import annotations

import argparse
import ast
import copy
from dataclasses import fields, replace
import json
from pathlib import Path
import subprocess

import pytest

from namisync.core.planning import OperationKind
from tools import executor_settlement_audit as audit


_EXPECTED_SCENARIOS = frozenset(
    {
        "success.all-nine",
        "failure.copy-prepublish-cleanup-ok",
        "failure.policy-stop-sweep",
        "failure.move-precommit-unchanged",
        "failure.byte-published",
        "failure.nonbyte-commit",
        "update.backup-state-matrix",
        "failure.update-sibling-matrix",
        "failure.move-update-new-and-trash",
        "failure.noop-drift",
        "retry.copy-prepared",
        "retry.copy-published",
        "retry.update-after-backup",
        "retry.move-update-after-publish",
        "retry.committed-move-settles-once",
        "retry.control-matrix",
        "resume.pause-same-execution-set",
        "cancel.before-effect-sweep",
        "cancel.copy-prepared",
        "cancel.copy-published",
        "cancel.committed-move",
        "cancel.update-composed-unverified-plus-readonly",
        "cancel.move-update-partial-publish",
        "pause.copy-prepared",
        "cleanup.ordinary-matrix",
        "cleanup.canceled-failure",
        "mkdir.settlement-matrix",
        "recording.flush-and-sticky-matrix",
        "record.copy-failure",
        "record.nonbyte-failure",
    }
)

_EXPECTED_ROWS = frozenset(
    {
        "success.all-nine",
        "failure.copy-prepublish-cleanup-ok",
        "failure.policy-stop-sweep",
        "failure.move-precommit-unchanged",
        "failure.byte-published.copy",
        "failure.byte-published.update",
        "failure.byte-published.move-update",
        "failure.byte-published.target-changed",
        "failure.byte-published.target-missing",
        "failure.byte-published.target-unreadable",
        "failure.nonbyte-commit.move",
        "failure.nonbyte-commit.recase",
        "failure.nonbyte-commit.trash",
        "failure.nonbyte-commit.delete",
        "failure.nonbyte-commit.mkdir",
        "failure.nonbyte-commit.move-restored",
        "failure.nonbyte-commit.trash-restored",
        "failure.nonbyte-commit.delete-restored",
        "failure.nonbyte-unreadable.delete-precommit",
        "update.backup-state.failure.retained",
        "update.backup-state.failure.changed",
        "update.backup-state.failure.absent",
        "update.backup-state.failure.unverified",
        "update.backup-state.cancel.retained",
        "update.backup-state.cancel.changed",
        "update.backup-state.cancel.absent",
        "update.backup-state.cancel.unverified",
        "failure.update-sibling.publication-unverified-plus-readonly",
        "failure.update-sibling.confirmed-publication-suppresses-readonly",
        "failure.update-sibling.unchanged-readonly",
        "failure.update-sibling.unreadable-readonly-mutation",
        "failure.move-update-new-and-trash",
        "failure.noop-drift",
        "retry.copy-prepared",
        "retry.copy-published",
        "retry.update-after-backup",
        "retry.move-update-after-publish",
        "retry.committed-move-settles-once",
        "retry.committed-move-failure-policy-escape",
        "retry.committed-move-sleep-escape",
        "retry.control.pause",
        "retry.control.pause-then-cancel",
        "resume.pause-same-execution-set",
        "cancel.before-effect-sweep",
        "cancel.copy-prepared",
        "cancel.copy-published",
        "cancel.committed-move",
        "cancel.update-composed-unverified-plus-readonly",
        "cancel.move-update-partial-publish",
        "pause.copy-prepared",
        "cleanup.ordinary.no-durable-cleanup-failure",
        "cleanup.ordinary.stale-owned-temp-recovered",
        "cleanup.ordinary.pre-retry-cleanup-succeeds",
        "cleanup.ordinary.pre-retry-cleanup-fails",
        "cleanup.ordinary.durable-verdict-plus-cleanup-failure",
        "cleanup.canceled-failure",
        "mkdir.primitive-precommit-unchanged",
        "mkdir.primitive-commit-then-raise",
        "mkdir.metadata-failure.available-probe",
        "mkdir.metadata-failure.unavailable-probe",
        "mkdir.metadata-failure.disappeared-after-create",
        "mkdir.pending-child-cancel",
        "mkdir.pending-child-pause",
        "mkdir.pending-child-checkpoint-exception",
        "mkdir.record-failure",
        "recording.pre-destructive-flush-refusal",
        "recording.final-flush-degradation",
        "recording.sticky-aggregate-degradation",
        "record.copy-failure",
        "record.nonbyte-failure",
    }
)


def _complete_scenarios() -> dict[str, object]:
    return {
        scenario.scenario_id: {
            "variants": [{"row": expected.row} for expected in scenario.expected]
        }
        for scenario in audit.SCENARIOS
    }


def _capture(
    scenarios: dict[str, object] | None = None,
    *,
    oracle_errors: tuple[str, ...] = (),
    determinism_errors: tuple[str, ...] = (),
    completed_repeats: int = 3,
    manifest_complete: bool | None = None,
) -> audit.Capture:
    scenario_payload = _complete_scenarios() if scenarios is None else scenarios
    return audit.Capture(
        scenarios=scenario_payload,
        oracle_errors=oracle_errors,
        determinism_errors=determinism_errors,
        completed_repeats=completed_repeats,
        manifest_complete=(
            audit._scenarios_match_manifest(scenario_payload)
            if manifest_complete is None
            else manifest_complete
        ),
    )


def _invariant_report(
    *,
    kind: str = "copy",
    outcome: str = "succeeded",
    evidence_count: int = 0,
    item_kind: str | None = None,
    terminal: bool = True,
) -> dict[str, object]:
    status = (
        [{"op": "op-1", "kind": kind, "outcome": outcome}]
        if terminal
        else []
    )
    items = (
        [
            {
                "op": "op-1",
                "kind": kind if item_kind is None else item_kind,
                "outcome": outcome,
            }
        ]
        if terminal
        else []
    )
    return {
        "termination": {
            "returned": None if not terminal else "completed",
            "raised": "PauseRequested" if not terminal else None,
        },
        "execution_set": {
            "selected": 1,
            "selection": [{"op": "op-1", "kind": kind}],
            "status": status,
            "published_evidence": [
                {"op": "op-1", "recorded": False}
                for _ in range(evidence_count)
            ],
        },
        "items": items,
        "reliable_events": [
            {"type": "item", "op": "op-1"}
            for _ in items
        ],
    }


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    action = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return dict(action.choices)


def _git_result(
    returncode: int,
    *,
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
        args=("git",),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_audit_imports_executor_only_through_its_public_facade() -> None:
    source_path = Path(audit.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if module == "tests" or module.startswith("tests."):
                    violations.append(f"line {node.lineno}: imports {module}")
                if module.startswith("namisync.") and not (
                    module.startswith("namisync.core.")
                    or module == "namisync.core"
                    or module == "namisync.modules.executor"
                ):
                    violations.append(f"line {node.lineno}: imports {module}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "tests" or module.startswith("tests."):
                violations.append(f"line {node.lineno}: imports {module}")
            if module.startswith("namisync.") and not (
                module.startswith("namisync.core.")
                or module == "namisync.core"
                or module == "namisync.modules.executor"
            ):
                violations.append(f"line {node.lineno}: imports {module}")
            if module == "namisync.modules.executor":
                for alias in node.names:
                    if (
                        alias.name == "*"
                        or alias.name.startswith("_")
                        or (alias.asname or "").startswith("_")
                    ):
                        violations.append(
                            f"line {node.lineno}: imports private facade name "
                            f"{alias.name!r}"
                        )

    assert violations == []


def test_manifest_is_complete_labeled_and_has_no_escape_state() -> None:
    scenario_ids = [scenario.scenario_id for scenario in audit.SCENARIOS]

    assert len(scenario_ids) == 30
    assert len(scenario_ids) == len(set(scenario_ids))
    assert frozenset(scenario_ids) == _EXPECTED_SCENARIOS
    assert audit.manifest_errors() == []
    assert {
        kind for scenario in audit.SCENARIOS for kind in scenario.kinds
    } == set(OperationKind)
    rows = [expected.row for scenario in audit.SCENARIOS for expected in scenario.expected]
    assert len(rows) == 70
    assert len(rows) == len(set(rows))
    assert frozenset(rows) == _EXPECTED_ROWS
    assert [
        row
        for entry in audit._manifest_payload()
        for row in entry["rows"]
    ] == rows

    forbidden_fields = {
        "accept",
        "skip",
        "skipped",
        "update",
        "update_baseline",
        "xfail",
    }
    assert forbidden_fields.isdisjoint(field.name for field in fields(audit.Scenario))
    for scenario in audit.SCENARIOS:
        assert scenario.expected
        assert scenario.kinds
        assert scenario.tags
        assert all(isinstance(tag, str) and tag for tag in scenario.tags)
        assert scenario.tags.isdisjoint(
            {"skip", "skipped", "unclassified", "xfail", "expected-fail"}
        )
        assert all(expected.row for expected in scenario.expected)


def test_manifest_rejects_empty_duplicate_missing_and_extra_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = audit.SCENARIOS
    index = next(
        index
        for index, scenario in enumerate(original)
        if scenario.scenario_id == "failure.byte-published"
    )
    scenario = original[index]

    cases = (
        (
            (replace(scenario.expected[0], row=""), *scenario.expected[1:]),
            ("has an empty expected row label", "missing=['failure.byte-published.copy']"),
        ),
        (
            (
                scenario.expected[0],
                replace(scenario.expected[1], row=scenario.expected[0].row),
                *scenario.expected[2:],
            ),
            ("has duplicate expected row labels", "missing=['failure.byte-published.update']"),
        ),
        (
            (
                scenario.expected[0],
                scenario.expected[1],
                *scenario.expected[3:],
            ),
            ("missing=['failure.byte-published.move-update']",),
        ),
        (
            (
                *scenario.expected,
                replace(scenario.expected[0], row="unexpected.extra-row"),
            ),
            ("extra=['unexpected.extra-row']",),
        ),
    )

    for expected, messages in cases:
        changed = list(original)
        changed[index] = replace(scenario, expected=expected)
        monkeypatch.setattr(audit, "SCENARIOS", tuple(changed))
        errors = audit.manifest_errors()
        for message in messages:
            assert any(message in error for error in errors), errors


def test_scenario_reports_pair_by_row_and_reject_row_set_drift() -> None:
    scenario = next(
        scenario
        for scenario in audit.SCENARIOS
        if scenario.scenario_id == "failure.byte-published"
    )
    reports = audit._run_in_sandbox(scenario.runner)
    reversed_reports = list(reversed(reports))
    reordered = replace(scenario, runner=lambda _base: reversed_reports)

    capture, errors = audit._run_scenario(reordered)

    assert errors == []
    assert [variant["row"] for variant in capture["variants"]] == [
        report["row"] for report in reversed_reports
    ]

    missing_and_extra = [dict(report) for report in reports]
    missing_and_extra[0]["row"] = "unexpected.report-row"
    _, errors = audit._run_scenario(
        replace(scenario, runner=lambda _base: missing_and_extra)
    )
    assert any("report rows differ from expected rows" in error for error in errors)
    assert any("failure.byte-published.copy" in error for error in errors)
    assert any("unexpected.report-row" in error for error in errors)

    duplicate = [dict(report) for report in reports]
    duplicate[1]["row"] = duplicate[0]["row"]
    _, errors = audit._run_scenario(replace(scenario, runner=lambda _base: duplicate))
    assert any("duplicate report row" in error for error in errors)

    empty = [dict(report) for report in reports]
    empty[0]["row"] = ""
    _, errors = audit._run_scenario(replace(scenario, runner=lambda _base: empty))
    assert any("empty or invalid row label" in error for error in errors)


@pytest.mark.parametrize("outcome", ["failed", "canceled", "deferred", "skipped"])
def test_evidence_invariant_rejects_every_non_success_byte_outcome(
    outcome: str,
) -> None:
    errors = audit._global_invariant_errors(
        _invariant_report(outcome=outcome, evidence_count=1)
    )

    assert any("without a successful byte outcome" in error for error in errors)


def test_evidence_invariant_is_exact_and_status_authoritative() -> None:
    assert audit._global_invariant_errors(
        _invariant_report(evidence_count=1)
    ) == []
    assert audit._global_invariant_errors(
        _invariant_report(outcome="failed")
    ) == []
    assert audit._global_invariant_errors(
        _invariant_report(kind="move")
    ) == []

    missing = audit._global_invariant_errors(_invariant_report())
    assert any("successful byte operation lacks evidence" in error for error in missing)

    nonbyte = audit._global_invariant_errors(
        _invariant_report(kind="move", evidence_count=1)
    )
    assert any("without a successful byte outcome" in error for error in nonbyte)

    duplicate = audit._global_invariant_errors(
        _invariant_report(evidence_count=2)
    )
    assert any("duplicate operation evidence" in error for error in duplicate)

    statusless = audit._global_invariant_errors(
        _invariant_report(evidence_count=1, terminal=False)
    )
    assert any("evidence without terminal status" in error for error in statusless)

    kind_drift = audit._global_invariant_errors(
        _invariant_report(evidence_count=1, item_kind="move")
    )
    assert kind_drift == [
        "global invariant: item/status kind disagreement for op-1"
    ]


def test_partial_selection_is_allowed_only_for_propagated_exception_modes() -> None:
    report = _invariant_report(terminal=False)
    report["termination"] = {"returned": None, "raised": "RuntimeError"}
    assert audit._global_invariant_errors(report) == []

    report["termination"] = {"returned": None, "raised": "Canceled"}
    assert audit._global_invariant_errors(report) == [
        "global invariant: 0 terminal statuses for 1 selections"
    ]


def test_recorder_trace_retains_complete_normalized_payloads_and_results() -> None:
    capture = audit.capture_one("success.all-nine")
    report = capture.scenarios["success.all-nine"]["variants"][0]
    trace = report["recorder"]["trace"]
    entries = {
        entry["command"]: entry
        for entry in trace
        if entry["command"] != "flush"
    }

    expected_payloads = {
        "copied": {"op", "attestation"},
        "updated": {"op", "attestation"},
        "move_updated": {"op", "attestation"},
        "moved": {"op", "target"},
        "recased": {"op", "target"},
        "mkdir": {"op", "target"},
        "trashed": {"op", "trash_relative_path", "target"},
        "deleted": {"op", "prior"},
        "noop": {"op", "source", "target"},
    }
    assert set(entries) == set(expected_payloads)
    for command, payload_fields in expected_payloads.items():
        entry = entries[command]
        assert set(entry) == {"command", "payload", "result"}
        assert set(entry["payload"]) == payload_fields

    expected_paths = {
        "copied": "COPY.BIN",
        "updated": "UPDATE.BIN",
        "move_updated": "RENAMED.BIN",
    }
    for command, rel_path_key in expected_paths.items():
        entry = entries[command]
        attestation = entry["payload"]["attestation"]
        assert set(attestation) == {"content", "subject"}
        assert set(attestation["content"]) == {
            "algorithm",
            "digest",
            "size",
            "provenance",
            "observed_at",
        }
        assert set(attestation["subject"]) == {
            "kind",
            "size",
            "mtime",
            "identity",
            "nlink",
            "attributes",
            "created",
        }
        assert entry["result"] == {
            "row_id": f"row-{entry['payload']['op']}",
            "location_id": "audit-target",
            "scope_token": str(audit.RUN_ID),
            "rel_path_key": rel_path_key,
        }
    for command in set(entries) - set(expected_paths):
        assert entries[command]["result"] is None
    for entry in trace:
        if entry["command"] == "flush":
            assert entry == {"command": "flush", "payload": {}, "result": None}

    failed = audit.capture_one("record.copy-failure")
    failure_trace = failed.scenarios["record.copy-failure"]["variants"][0][
        "recorder"
    ]["trace"]
    copied = next(entry for entry in failure_trace if entry["command"] == "copied")
    assert set(copied["payload"]) == {"op", "attestation"}
    assert copied["result"] is None
    assert copied["error"] == "RuntimeError"
    assert copied["message"] == "injected copied recorder failure"


def test_report_retains_complete_public_result_and_evidence() -> None:
    capture = audit.capture_one("retry.copy-prepared")
    report = capture.scenarios["retry.copy-prepared"]["variants"][0]
    result = report["result"]
    assert set(result) == {
        "status",
        "recording",
        "audit",
        "disposition",
        "canceled",
        "items",
        "phases",
        "bytes_done",
        "bytes_total",
        "error",
    }
    assert result["audit"] == "ok"
    assert result["disposition"] == "ran"
    assert result["phases"] == []
    assert result["error"] is None
    assert result["items"] == report["items"]

    evidence = report["execution_set"]["published_evidence"][0]
    assert set(evidence) == {
        "op",
        "kind",
        "path",
        "recorded",
        "content",
        "subject",
        "recorded_identity",
    }
    assert evidence["content"] == {
        "algorithm": "xxh3_128",
        "digest": "623b87aed4dbff6d28a13eb71249c33a",
        "size": 12,
        "provenance": "copy",
        "observed_at": "2026-08-10T12:00:00+00:00",
    }
    assert set(evidence["subject"]) == {
        "kind",
        "size",
        "mtime",
        "identity",
        "nlink",
        "attributes",
        "created",
    }
    assert evidence["recorded_identity"] == {
        "row_id": "row-00000000000000000000000000000001",
        "location_id": "audit-target",
        "scope_token": str(audit.RUN_ID),
        "rel_path_key": "COPY.BIN",
    }


def test_exact_policy_projection_rejects_every_public_axis_drift() -> None:
    capture = audit.capture_one("success.all-nine")
    report = capture.scenarios["success.all-nine"]["variants"][0]
    expected = audit._SCENARIO_BY_ID["success.all-nine"].expected[0]

    def extra_result_axis(candidate):
        candidate["result"]["unexpected"] = True

    def wrong_result_bytes(candidate):
        candidate["result"]["bytes_done"] -= 1

    def missing_result_item(candidate):
        candidate["result"]["items"].pop()

    def extra_item_detail(candidate):
        candidate["items"][0]["detail"]["unexpected"] = "drift"

    def missing_item_detail(candidate):
        candidate["items"][1]["detail"].pop("backup")

    def status_order(candidate):
        candidate["execution_set"]["status"][:2] = reversed(
            candidate["execution_set"]["status"][:2]
        )

    def wrong_evidence_digest(candidate):
        candidate["execution_set"]["published_evidence"][0]["content"][
            "digest"
        ] = "00" * 16

    def wrong_evidence_subject(candidate):
        candidate["execution_set"]["published_evidence"][0]["subject"][
            "size"
        ] += 1

    def wrong_evidence_subject_identity(candidate):
        candidate["execution_set"]["published_evidence"][0]["subject"][
            "identity"
        ] = "identity-impossible"

    def wrong_recorded_identity(candidate):
        candidate["execution_set"]["published_evidence"][0][
            "recorded_identity"
        ]["row_id"] = "wrong-row"

    def wrong_recorder_attestation(candidate):
        copied = next(
            entry
            for entry in candidate["recorder"]["trace"]
            if entry["command"] == "copied"
        )
        copied["payload"]["attestation"]["content"]["digest"][
            "sha256"
        ] = "00" * 32

    def wrong_recorder_nonbyte_stat(candidate):
        moved = next(
            entry
            for entry in candidate["recorder"]["trace"]
            if entry["command"] == "moved"
        )
        moved["payload"]["target"]["identity"] = "identity-impossible"

    def wrong_recorder_result(candidate):
        copied = next(
            entry
            for entry in candidate["recorder"]["trace"]
            if entry["command"] == "copied"
        )
        copied["result"]["row_id"] = "wrong-row"

    def wrong_flush_payload(candidate):
        flushed = next(
            entry
            for entry in candidate["recorder"]["trace"]
            if entry["command"] == "flush"
        )
        flushed["payload"]["unexpected"] = True

    def extra_evidence_field(candidate):
        candidate["execution_set"]["published_evidence"][0]["unexpected"] = True

    def extra_subject_field(candidate):
        candidate["execution_set"]["published_evidence"][0]["subject"][
            "unexpected"
        ] = True

    def missing_reliable_phase(candidate):
        candidate["reliable_events"].pop(0)

    def extra_tree_artifact(candidate):
        candidate["tree"]["$SOURCE/unexpected.bin"] = {
            "kind": "file",
            "size": 0,
            "text": "",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "mtime": "time-extra-1",
            "created": "time-extra-2",
            "readonly": False,
        }

    def missing_tree_artifact(candidate):
        candidate["tree"].pop("$TARGET/copy.bin")

    def extra_tree_field(candidate):
        candidate["tree"]["$TARGET/copy.bin"]["unexpected"] = True

    def missing_source_tree_created(candidate):
        candidate["tree"]["$SOURCE/copy.bin"].pop("created")

    def missing_directory_tree_created(candidate):
        candidate["tree"]["$TARGET/.synctrash"].pop("created")

    def wrong_target_metadata(candidate):
        candidate["tree"]["$TARGET/copy.bin"]["mtime"] = "time-impossible"

    def wrong_target_identity_relation(candidate):
        candidate["tree"]["$TARGET/copy.bin"]["identity"] = candidate["tree"][
            "$SOURCE/copy.bin"
        ]["identity"]

    def wrong_directory_metadata(candidate):
        candidate["tree"]["$TARGET/folder"]["created"] = "time-impossible"

    def wrong_directory_identity(candidate):
        candidate["tree"]["$TARGET/folder"]["identity"] = candidate["tree"][
            "$SOURCE/folder"
        ]["identity"]

    for mutate in (
        extra_result_axis,
        wrong_result_bytes,
        missing_result_item,
        extra_item_detail,
        missing_item_detail,
        status_order,
        wrong_evidence_digest,
        wrong_evidence_subject,
        wrong_evidence_subject_identity,
        wrong_recorded_identity,
        wrong_recorder_attestation,
        wrong_recorder_nonbyte_stat,
        wrong_recorder_result,
        wrong_flush_payload,
        extra_evidence_field,
        extra_subject_field,
        missing_reliable_phase,
        extra_tree_artifact,
        missing_tree_artifact,
        extra_tree_field,
        missing_source_tree_created,
        missing_directory_tree_created,
        wrong_target_metadata,
        wrong_target_identity_relation,
        wrong_directory_metadata,
        wrong_directory_identity,
    ):
        candidate = copy.deepcopy(report)
        mutate(candidate)
        errors = expected.errors(candidate)
        assert any("exact policy projection" in error for error in errors), mutate.__name__


def test_exact_policy_projection_rejects_failed_flush_trace_drift() -> None:
    scenario_id = "recording.flush-and-sticky-matrix"
    row = "recording.pre-destructive-flush-refusal"
    capture = audit.capture_one(scenario_id)
    report = next(
        variant
        for variant in capture.scenarios[scenario_id]["variants"]
        if variant["row"] == row
    )
    expected = next(
        candidate
        for candidate in audit._SCENARIO_BY_ID[scenario_id].expected
        if candidate.row == row
    )
    failed_flush = next(
        entry
        for entry in report["recorder"]["trace"]
        if entry["command"] == "flush" and "error" in entry
    )
    failed_flush.pop("message")

    assert any(
        "exact policy projection" in error for error in expected.errors(report)
    )


def test_exact_tree_metadata_catalog_rejects_wrong_stage_relations() -> None:
    captures = {
        scenario_id: audit.capture_one(scenario_id)
        for scenario_id in (
            "success.all-nine",
            "failure.noop-drift",
            "update.backup-state-matrix",
            "cleanup.ordinary-matrix",
            "mkdir.settlement-matrix",
        )
    }

    def row(scenario_id: str, row_label: str):
        variants = captures[scenario_id].scenarios[scenario_id]["variants"]
        report = next(item for item in variants if item["row"] == row_label)
        expected = next(
            candidate
            for scenario in audit.SCENARIOS
            for candidate in scenario.expected
            if candidate.row == row_label
        )
        return expected, copy.deepcopy(report)

    def contract(report, operation: int, reference: str):
        op = f"{operation:032x}"
        selected = next(
            item for item in report["operation_contracts"] if item["op"] == op
        )
        return selected[reference]

    cases = []

    expected, report = row("success.all-nine", "success.all-nine")
    report["tree"]["$TARGET/move-new.bin"]["created"] = contract(
        report, 3, "intended"
    )["created"]
    cases.append(("move must preserve prior target", expected, report))

    expected, report = row("success.all-nine", "success.all-nine")
    report["tree"]["$SOURCE/copy.bin"]["mtime"] = "time-impossible"
    cases.append(("source metadata must remain reviewed", expected, report))

    expected, report = row("success.all-nine", "success.all-nine")
    report["tree"][f"$TARGET/.synctrash/{audit.RUN_ID}/old.bin"][
        "identity"
    ] = contract(report, 4, "intended")["identity"]
    cases.append(("trash must preserve displaced target", expected, report))

    expected, report = row("failure.noop-drift", "failure.noop-drift")
    report["tree"]["$TARGET/noop.bin"]["mtime"] = contract(
        report, 1, "target_expected"
    )["mtime"]
    cases.append(("noop drift must remain classified", expected, report))

    expected, report = row(
        "update.backup-state-matrix",
        "update.backup-state.failure.retained",
    )
    report["tree"][f"$TARGET/.synctrash/{audit.RUN_ID}/update.bin"][
        "identity"
    ] = contract(report, 1, "target_expected")["identity"]
    cases.append(("copied backup must stay a distinct file", expected, report))

    expected, report = row(
        "update.backup-state-matrix",
        "update.backup-state.failure.changed",
    )
    report["tree"][f"$TARGET/.synctrash/{audit.RUN_ID}/update.bin"][
        "mtime"
    ] = contract(report, 1, "target_expected")["mtime"]
    cases.append(("changed backup must not look retained", expected, report))

    expected, report = row(
        "cleanup.ordinary-matrix",
        "cleanup.ordinary.no-durable-cleanup-failure",
    )
    temp = (
        f"$TARGET/copy.bin.synctmp-{audit.RUN_ID}-"
        "00000000000000000000000000000001"
    )
    report["tree"][temp]["mtime"] = contract(report, 1, "intended")["mtime"]
    cases.append(("unfinalized temp must stay unfinalized", expected, report))

    expected, report = row(
        "cleanup.ordinary-matrix",
        "cleanup.ordinary.durable-verdict-plus-cleanup-failure",
    )
    temp = (
        f"$TARGET/update.bin.synctmp-{audit.RUN_ID}-"
        "00000000000000000000000000000001"
    )
    report["tree"][temp]["created"] = "time-impossible"
    cases.append(("finalized temp must retain intended metadata", expected, report))

    expected, report = row(
        "mkdir.settlement-matrix",
        "mkdir.primitive-commit-then-raise",
    )
    report["tree"]["$TARGET/folder"]["mtime"] = contract(
        report, 1, "intended"
    )["mtime"]
    cases.append(("pre-metadata mkdir must stay pre-metadata", expected, report))

    expected, report = row(
        "mkdir.settlement-matrix",
        "mkdir.primitive-commit-then-raise",
    )
    contract(report, 1, "intended").pop("mtime")
    cases.append(("false relation still requires a complete reference", expected, report))

    for name, expected, candidate in cases:
        assert any(
            "exact policy projection" in error
            for error in expected.errors(candidate)
        ), name


def test_exact_policy_projection_rejects_missing_or_extra_public_containers() -> None:
    cases = (
        ("failure.move-precommit-unchanged", lambda report: report["execution_set"].pop("published_evidence")),
        ("pause.copy-prepared", lambda report: report.pop("result")),
        ("pause.copy-prepared", lambda report: report.pop("tree")),
        ("failure.move-precommit-unchanged", lambda report: report["execution_set"].update({"unexpected": True})),
    )
    for scenario_id, mutate in cases:
        capture = audit.capture_one(scenario_id)
        report = capture.scenarios[scenario_id]["variants"][0]
        expected = audit._SCENARIO_BY_ID[scenario_id].expected[0]
        mutate(report)
        assert any(
            "exact policy projection" in error for error in expected.errors(report)
        ), scenario_id


def test_same_execution_set_resume_reuses_then_retires_continuation() -> None:
    capture = audit.capture_one("resume.pause-same-execution-set", repeat=2)
    assert capture.ok
    report = capture.scenarios["resume.pause-same-execution-set"]["variants"][0]
    first, second, third = report["invocations"]

    assert first["termination"] == {
        "returned": None,
        "raised": "PauseRequested",
    }
    assert [status["op"] for status in first["execution_set"]["status"]] == [
        "00000000000000000000000000000001",
        "00000000000000000000000000000002",
    ]
    assert first["backend_calls"] == 2
    assert "$TARGET/third.bin" not in first["tree"]

    assert second["termination"] == {"returned": "completed", "raised": None}
    assert second["backend_calls"] == 3
    assert [item["reason"] for item in second["result"]["items"]] == [
        "previously-settled",
        "previously-settled",
        None,
    ]
    assert second["items"] == [report["items"][2]]

    assert third["termination"] == {"returned": "completed", "raised": None}
    assert third["items"] == []
    assert third["backend_calls"] == 3
    assert [item["reason"] for item in third["result"]["items"]] == [
        "previously-settled",
        "previously-settled",
        "previously-settled",
    ]
    assert third["recorder_commands"] == ["copied", "updated", "copied"]
    assert third["recorder_flushes"] == 5
    assert report["copy_backend"]["calls"] == 3
    assert report["filesystem"]["counts"]["replace"] == 2
    commands = [
        entry["command"]
        for entry in report["recorder"]["trace"]
        if entry["command"] != "flush"
    ]
    assert commands == ["copied", "updated", "copied"]
    assert report["recorder"]["trace"][-1]["command"] == "flush"
    assert len(report["execution_set"]["published_evidence"]) == 3
    assert not any("synctmp" in path for path in report["tree"])


def test_failure_policy_stop_sweeps_later_and_dependent_work() -> None:
    capture = audit.capture_one("failure.policy-stop-sweep", repeat=2)
    assert capture.ok
    report = capture.scenarios["failure.policy-stop-sweep"]["variants"][0]

    assert report["termination"] == {"returned": "failed", "raised": None}
    assert [item["outcome"] for item in report["items"]] == [
        "failed",
        "canceled",
        "canceled",
    ]
    assert [item["reason"] for item in report["items"]] == [
        "io-error",
        "policy-stop",
        "policy-stop",
    ]
    assert report["result"]["canceled"] is False
    assert report["result"]["bytes_done"] == 0
    assert report["result"]["bytes_total"] == 45
    assert report["copy_backend"]["calls"] == 1
    assert report["execution_set"]["published_evidence"] == []
    assert all(not path.startswith("$TARGET/") for path in report["tree"])
    assert report["filesystem"]["counts"].get("publish_new", 0) == 0


def test_unified_timeline_preserves_cross_boundary_retry_order() -> None:
    capture = audit.capture_one("retry.copy-prepared")
    report = capture.scenarios["retry.copy-prepared"]["variants"][0]
    timeline = report["timeline"]

    def position(prefix: str, start: int = 0) -> int:
        return next(
            index
            for index, token in enumerate(timeline[start:], start=start)
            if token.startswith(prefix)
        )

    backend_begin = position("backend:copy:1:begin")
    backend_checkpoint = position("backend:copy:1:checkpoint:begin", backend_begin)
    control_checkpoint = position("control:checkpoint:", backend_checkpoint)
    backend_chunk = position("backend:copy:1:chunk:", control_checkpoint)
    backend_end = position("backend:copy:1:end", backend_chunk)
    publish_error = position("fs:publish_new:error", backend_end)
    failure_decision = position("failure-policy:", publish_error)
    sleep_begin = position("pacing:sleep:0:begin", failure_decision)
    sleep_end = position("pacing:sleep:0:end", sleep_begin)
    publish_success = position("fs:publish_new:end", sleep_end)
    recorder = position("recorder:copied", publish_success)
    item_emit = position("emit:item:", recorder)

    assert backend_begin < backend_checkpoint < control_checkpoint < backend_chunk
    assert backend_chunk < backend_end < publish_error < failure_decision
    assert failure_decision < sleep_begin < sleep_end < publish_success
    assert publish_success < recorder < item_emit
    assert any(token.startswith("emit:phase:") for token in timeline)
    assert not any(token.startswith("emit:progress:") for token in timeline)
    assert report["progress_final"] is not None

    paused = audit.capture_one("pause.copy-prepared")
    pause_timeline = paused.scenarios["pause.copy-prepared"]["variants"][0][
        "timeline"
    ]
    assert any(
        token.startswith("control:checkpoint:")
        and token.endswith(":raise:PauseRequested")
        for token in pause_timeline
    )
    assert "backend:copy:1:error:PauseRequested" in pause_timeline


def test_symbolic_timestamps_preserve_equivalence_and_cover_final_tree(
    tmp_path: Path,
) -> None:
    normalizer = audit.TracingFileSystem(tmp_path / "source", tmp_path / "target")
    assert normalizer.timestamp("mtime", 100) == normalizer.timestamp("mtime", 100)
    assert normalizer.timestamp("mtime", 100) != normalizer.timestamp("mtime", 200)
    assert normalizer.timestamp("created", 100) == normalizer.timestamp("created", 100)
    assert normalizer.timestamp("created", 100) != normalizer.timestamp("created", 200)
    assert normalizer.timestamp("mtime", 100) == normalizer.timestamp("created", 100)
    assert normalizer.timestamp("mtime", 100) != normalizer.timestamp("created", 200)

    capture = audit.capture_one("success.all-nine")
    report = capture.scenarios["success.all-nine"]["variants"][0]
    encoded = json.dumps(report)
    assert '"fixed"' not in encoded
    assert all(
        "mtime" in entry and "created" in entry
        for entry in report["tree"].values()
    )
    source = report["tree"]["$SOURCE/copy.bin"]
    target = report["tree"]["$TARGET/copy.bin"]
    copied = next(
        entry
        for entry in report["recorder"]["trace"]
        if entry["command"] == "copied"
    )
    subject = copied["payload"]["attestation"]["subject"]
    assert source["mtime"] == target["mtime"] == subject["mtime"]
    assert source["created"] == target["created"] == subject["created"]
    update_contract = next(
        item
        for item in report["operation_contracts"]
        if item["kind"] == "update"
    )
    assert (
        update_contract["source_expected"]["mtime"]
        != update_contract["target_expected"]["mtime"]
    )
    assert (
        update_contract["source_expected"]["created"]
        != update_contract["target_expected"]["created"]
    )


def test_partial_unfinalized_temp_excludes_only_clock_incidental_timestamps() -> None:
    row = "cleanup.ordinary.pre-retry-cleanup-fails"
    path = f"$TARGET/copy.bin.synctmp-{audit.RUN_ID}-{1:032x}"
    common = {
        "kind": "file",
        "size": 4,
        "text": "copy",
        "identity": "identity-2",
        "readonly": False,
    }
    coincident = {path: {**common, "mtime": "time-3", "created": "time-3"}}
    distinct = {path: {**common, "mtime": "time-3", "created": "time-4"}}

    normalized_coincident = audit._normalize_clock_incidental_tree_timestamps(
        row, coincident
    )
    normalized_distinct = audit._normalize_clock_incidental_tree_timestamps(
        row, distinct
    )

    assert normalized_coincident == normalized_distinct
    assert normalized_coincident[path] == {
        **common,
        "mtime": "$clock-incidental:mtime",
        "created": "$clock-incidental:created",
    }
    assert coincident[path]["created"] == "time-3"
    assert distinct[path]["created"] == "time-4"
    assert audit._normalize_clock_incidental_tree_timestamps(
        "success.all-nine", distinct
    ) == distinct


def test_clock_incidental_timestamp_catalog_is_exact_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = "cleanup.ordinary.pre-retry-cleanup-fails"
    path = f"$TARGET/copy.bin.synctmp-{audit.RUN_ID}-{1:032x}"
    assert audit._CLOCK_INCIDENTAL_TREE_TIMESTAMPS == {
        row: {path: frozenset({"created", "mtime"})}
    }
    assert audit.manifest_errors() == []

    with pytest.raises(audit.AuditError, match="names absent tree path"):
        audit._normalize_clock_incidental_tree_timestamps(row, {})
    with pytest.raises(audit.AuditError, match="names absent field"):
        audit._normalize_clock_incidental_tree_timestamps(
            row,
            {path: {"mtime": "time-3"}},
        )

    monkeypatch.setattr(
        audit,
        "_CLOCK_INCIDENTAL_TREE_TIMESTAMPS",
        {
            **audit._CLOCK_INCIDENTAL_TREE_TIMESTAMPS,
            "stale.clock-row": {path: frozenset({"created", "mtime"})},
        },
    )
    assert any(
        "exact clock-incidental tree timestamps contains stale rows" in error
        for error in audit.manifest_errors()
    )


def test_representative_capture_is_oracle_clean_and_deterministic() -> None:
    capture = audit.capture_one("failure.move-precommit-unchanged", repeat=2)

    assert capture.ok
    assert capture.oracle_errors == ()
    assert capture.determinism_errors == ()
    assert capture.completed_repeats == 2
    assert not capture.manifest_complete
    assert not capture.baseline_eligible
    assert tuple(capture.scenarios) == ("failure.move-precommit-unchanged",)
    assert capture.scenarios["failure.move-precommit-unchanged"]["variants"][0][
        "row"
    ] == "failure.move-precommit-unchanged"


@pytest.mark.parametrize(
    ("scenario_id", "added_rows"),
    (
        (
            "failure.byte-published",
            {
                "failure.byte-published.target-changed",
                "failure.byte-published.target-missing",
                "failure.byte-published.target-unreadable",
            },
        ),
        (
            "failure.nonbyte-commit",
            {
                "failure.nonbyte-commit.move-restored",
                "failure.nonbyte-commit.trash-restored",
                "failure.nonbyte-commit.delete-restored",
                "failure.nonbyte-unreadable.delete-precommit",
            },
        ),
        (
            "failure.update-sibling-matrix",
            {"failure.update-sibling.unreadable-readonly-mutation"},
        ),
        (
            "retry.committed-move-settles-once",
            {
                "retry.committed-move-failure-policy-escape",
                "retry.committed-move-sleep-escape",
            },
        ),
        (
            "mkdir.settlement-matrix",
            {
                "mkdir.metadata-failure.disappeared-after-create",
                "mkdir.pending-child-checkpoint-exception",
            },
        ),
    ),
)
def test_expanded_observer_and_collaborator_rows_are_exact_and_clean(
    scenario_id: str,
    added_rows: set[str],
) -> None:
    capture = audit.capture_one(scenario_id)

    assert capture.ok
    variants = capture.scenarios[scenario_id]["variants"]
    assert added_rows <= {variant["row"] for variant in variants}


def test_collaborator_escape_rows_preserve_operation_failure_and_partial_selection() -> None:
    move_capture = audit.capture_one("retry.committed-move-settles-once")
    move_variants = {
        variant["row"]: variant
        for variant in move_capture.scenarios[
            "retry.committed-move-settles-once"
        ]["variants"]
    }
    for row, reason, message, raised_token in (
        (
            "retry.committed-move-failure-policy-escape",
            "io-error",
            "injected committed move failure",
            "failure-policy:00000000000000000000000000000001:attempt:1:raise:RuntimeError",
        ),
        (
            "retry.committed-move-sleep-escape",
            "sharing-violation",
            "injected committed move retry",
            "pacing:sleep:0:raise:RuntimeError",
        ),
    ):
        report = move_variants[row]
        assert report["termination"] == {"returned": None, "raised": "RuntimeError"}
        assert len(report["execution_set"]["status"]) == 1
        assert len(report["items"]) == 1
        assert report["items"][0]["reason"] == reason
        assert report["items"][0]["detail"]["message"] == message
        assert report["items"][0]["detail"]["durable_state"] == "target-renamed"
        assert report["tree"]["$TARGET/new.bin"]["text"] == "move-payload"
        assert "$TARGET/old.bin" not in report["tree"]
        assert raised_token in report["timeline"]

    mkdir_capture = audit.capture_one("mkdir.settlement-matrix")
    report = next(
        variant
        for variant in mkdir_capture.scenarios["mkdir.settlement-matrix"][
            "variants"
        ]
        if variant["row"] == "mkdir.pending-child-checkpoint-exception"
    )
    assert report["termination"] == {"returned": None, "raised": "RuntimeError"}
    assert len(report["execution_set"]["selection"]) == 2
    assert len(report["execution_set"]["status"]) == 1
    assert report["items"] == [
        {
            "op": f"{1:032x}",
            "kind": "mkdir",
            "path": "folder",
            "outcome": "succeeded",
            "reason": None,
            "detail": {},
        }
    ]
    assert "$TARGET/folder" in report["tree"]
    assert "$TARGET/folder/child.bin" not in report["tree"]
    assert "control:checkpoint:2:raise:RuntimeError" in report["timeline"]


def test_cleanup_matrix_covers_failed_pre_retry_cleanup() -> None:
    capture = audit.capture_one("cleanup.ordinary-matrix")

    assert capture.ok
    variants = capture.scenarios["cleanup.ordinary-matrix"]["variants"]
    report = next(
        variant
        for variant in variants
        if variant["row"] == "cleanup.ordinary.pre-retry-cleanup-fails"
    )
    owned_temp = (
        f"$TARGET/copy.bin.synctmp-{audit.RUN_ID}-"
        f"{1:032x}"
    )
    assert report["termination"] == {"returned": "failed", "raised": None}
    assert report["items"] == [
        {
            "op": f"{1:032x}",
            "kind": "copy",
            "path": "copy.bin",
            "outcome": "failed",
            "reason": "cleanup-failed",
            "detail": {
                "error_type": "OperationFailure",
                "message": (
                    "operation failed and its owned temp could not be removed: "
                    "injected retry cleanup failure"
                ),
            },
        }
    ]
    assert report["failure_policy"]["trace"][0]["decision"] == "retry"
    assert report["control"] == {"checkpoints": 2, "sleeps": []}
    assert report["copy_backend"]["calls"] == 1
    assert report["copy_backend"]["trace"][0]["error"] == "OSError"
    assert report["filesystem"]["counts"]["remove_owned_temp"] == 2
    assert report["tree"][owned_temp]["text"] == "copy"
    assert "$TARGET/copy.bin" not in report["tree"]


def test_fixture_rejects_every_unconsumed_fault_rule(tmp_path: Path) -> None:
    source, target, fs = audit._roots(tmp_path)
    operation = audit._copy_operation(source, target, fs)
    unused = audit.FaultRule("replace", "before", lambda *_args: None)

    with pytest.raises(
        audit.AuditError,
        match=(
            r"unused-fault: installed fault rules were not consumed: "
            r"1:replace/before remaining=1"
        ),
    ):
        audit._run_fixture(
            source,
            target,
            (operation,),
            row="unused-fault",
            rules=(unused,),
        )


@pytest.mark.parametrize(
    ("injection", "label"),
    (
        ({"failure_policy_escape": True}, "failure-policy escape"),
        ({"checkpoint_exception_at": 999}, "checkpoint exception"),
        ({"retry_sleep_escape": True}, "retry-sleep escape"),
    ),
)
def test_fixture_rejects_every_unconsumed_collaborator_injection(
    tmp_path: Path,
    injection: dict[str, object],
    label: str,
) -> None:
    source, target, fs = audit._roots(tmp_path)
    operation = audit._copy_operation(source, target, fs)

    with pytest.raises(
        audit.AuditError,
        match=f"installed collaborator injections were not consumed: {label}",
    ):
        audit._run_fixture(
            source,
            target,
            (operation,),
            row="unused-collaborator-injection",
            **injection,
        )


def test_cli_lists_the_exact_manifest_and_rejects_an_unknown_scenario(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert audit.main(["list"]) == 0
    listed = capsys.readouterr().out.splitlines()
    assert len(listed) == 30
    assert {line.split("\t", maxsplit=1)[0] for line in listed} == _EXPECTED_SCENARIOS

    assert audit.main(["run", "not-a-settlement-scenario"]) == 2
    output = capsys.readouterr().out
    assert "error: unknown scenario: not-a-settlement-scenario" in output


def test_cli_exposes_no_skip_xfail_or_baseline_update_escape() -> None:
    commands = _subcommands(audit._parser())

    assert set(commands) == {"list", "run", "oracle", "snapshot", "diff", "check"}
    option_strings = {
        option
        for parser in commands.values()
        for action in parser._actions
        for option in action.option_strings
    }
    assert option_strings.isdisjoint(
        {
            "--accept",
            "--force",
            "--no-oracle",
            "--skip",
            "--skip-oracle",
            "--update",
            "--update-baseline",
            "--xfail",
        }
    )


def test_snapshot_requires_three_oracle_clean_deterministic_runs(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"

    with pytest.raises(audit.AuditError, match="at least three completed repeats"):
        audit._write_baseline(
            baseline,
            _capture(completed_repeats=2),
            replace_existing=False,
        )
    with pytest.raises(audit.AuditError, match="oracle or determinism"):
        audit._write_baseline(
            baseline,
            _capture(oracle_errors=("latent policy defect",)),
            replace_existing=False,
        )
    with pytest.raises(audit.AuditError, match="oracle or determinism"):
        audit._write_baseline(
            baseline,
            _capture(determinism_errors=("unstable trace",)),
            replace_existing=False,
        )

    assert not baseline.exists()


def test_capture_records_completed_sweeps_and_single_capture_is_never_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def stubbed_run(scenario: audit.Scenario) -> tuple[dict[str, object], list[str]]:
        return (
            {
                "variants": [
                    {"row": expected.row}
                    for expected in scenario.expected
                ]
            },
            [],
        )

    monkeypatch.setattr(audit, "_run_scenario", stubbed_run)
    complete = audit.capture_all(repeat=4)

    assert complete.completed_repeats == 4
    assert complete.manifest_complete
    assert complete.baseline_eligible
    assert audit._baseline_payload(complete)["repeat"] == 4

    single = audit.capture_one("failure.move-precommit-unchanged", repeat=3)
    assert single.completed_repeats == 3
    assert not single.manifest_complete
    assert not single.baseline_eligible
    with pytest.raises(audit.AuditError, match="complete current scenario manifest"):
        audit._baseline_payload(single)


def test_baseline_payload_recomputes_manifest_completeness() -> None:
    with pytest.raises(audit.AuditError, match="complete current scenario manifest"):
        audit._baseline_payload(_capture(manifest_complete=False))

    missing = _complete_scenarios()
    missing.pop("success.all-nine")
    forged = _capture(missing, manifest_complete=True)
    with pytest.raises(audit.AuditError, match="complete current scenario manifest"):
        audit._baseline_payload(forged)

    missing_row = _complete_scenarios()
    missing_row["failure.byte-published"]["variants"].pop()
    forged = _capture(missing_row, manifest_complete=True)
    with pytest.raises(audit.AuditError, match="complete current scenario manifest"):
        audit._baseline_payload(forged)


def test_cli_rejects_a_short_snapshot_before_capturing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unexpected_capture(*, repeat: int) -> audit.Capture:
        raise AssertionError(f"capture unexpectedly ran with repeat={repeat}")

    monkeypatch.setattr(audit, "capture_all", unexpected_capture)

    assert audit.main(
        ["snapshot", "--repeat", "2", "--baseline", str(tmp_path / "baseline.json")]
    ) == 2
    assert "snapshot requires at least three repeats" in capsys.readouterr().out


def test_snapshot_write_is_atomic_and_refuses_implicit_overwrite(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    capture = _capture(completed_repeats=4)

    audit._write_baseline(
        baseline,
        capture,
        replace_existing=False,
    )

    payload = json.loads(baseline.read_text(encoding="utf-8"))
    assert payload["format_version"] == audit.FORMAT_VERSION
    assert payload["repeat"] == 4
    assert payload["scenarios"] == capture.scenarios
    assert list(tmp_path.glob(f".{baseline.name}.*.tmp")) == []
    original = baseline.read_bytes()

    with pytest.raises(audit.AuditError, match="baseline collision"):
        audit._write_baseline(
            baseline,
            _capture(),
            replace_existing=False,
        )

    assert baseline.read_bytes() == original
    assert list(tmp_path.glob(f".{baseline.name}.*.tmp")) == []


def test_late_no_clobber_collision_preserves_the_winner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = tmp_path / "baseline.json"
    real_link = audit.os.link

    def collide(source: Path | str, target: Path | str) -> None:
        Path(target).write_bytes(b"late winner")
        real_link(source, target)

    monkeypatch.setattr(audit.os, "link", collide)

    with pytest.raises(audit.AuditError, match="baseline collision"):
        audit._write_baseline(baseline, _capture(), replace_existing=False)

    assert baseline.read_bytes() == b"late winner"
    assert list(tmp_path.glob(f".{baseline.name}.*.tmp")) == []


def test_failed_no_clobber_publish_removes_its_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = tmp_path / "baseline.json"

    def fail_link(source: Path | str, target: Path | str) -> None:
        raise OSError(f"cannot link {source} to {target}")

    monkeypatch.setattr(audit.os, "link", fail_link)

    with pytest.raises(OSError, match="cannot link"):
        audit._write_baseline(baseline, _capture(), replace_existing=False)

    assert not baseline.exists()
    assert list(tmp_path.iterdir()) == []


def test_failed_atomic_replace_removes_its_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_bytes(b"original")

    def fail_replace(source: Path | str, target: Path | str) -> None:
        raise OSError(f"cannot replace {source} with {target}")

    monkeypatch.setattr(audit.os, "replace", fail_replace)

    with pytest.raises(OSError, match="cannot replace"):
        audit._write_baseline(
            baseline,
            _capture(),
            replace_existing=True,
        )

    assert baseline.read_bytes() == b"original"
    assert list(tmp_path.glob(f".{baseline.name}.*.tmp")) == []


def test_explicit_baseline_replacement_uses_atomic_replace(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_bytes(b"original")

    audit._write_baseline(baseline, _capture(), replace_existing=True)

    payload = json.loads(baseline.read_text(encoding="utf-8"))
    assert payload["scenarios"] == _complete_scenarios()
    assert list(tmp_path.glob(f".{baseline.name}.*.tmp")) == []


def test_missing_baseline_is_a_clear_hard_check_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(audit, "capture_all", lambda *, repeat: _capture())

    assert audit.main(
        ["check", "--repeat", "3", "--baseline", str(missing)]
    ) == 2
    output = capsys.readouterr().out
    assert f"settlement baseline is missing: {missing}" in output
    assert "snapshot the corrected committed monolith" in output


def test_official_check_reads_clean_head_baseline_and_enforces_semantic_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    payload = json.loads(audit.DEFAULT_BASELINE.read_text(encoding="utf-8"))
    committed = json.dumps(payload, indent=1).replace("\n", "\r\n").encode("utf-8")

    def fake_git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
        calls.append(arguments)
        if arguments[0] == "diff":
            return _git_result(0)
        return _git_result(0, stdout=committed)

    monkeypatch.setattr(audit, "_run_git", fake_git)

    baseline = audit._read_reviewed_committed_baseline()

    assert baseline["format_version"] == audit.FORMAT_VERSION
    assert calls == [
        (
            "diff",
            "--cached",
            "--quiet",
            "HEAD",
            "--",
            "tools/executor_settlement_baseline.json",
        ),
        (
            "diff",
            "--quiet",
            "--",
            "tools/executor_settlement_baseline.json",
        ),
        ("show", "HEAD:tools/executor_settlement_baseline.json"),
    ]


@pytest.mark.parametrize("dirty_check", [1, 2])
def test_official_check_rejects_a_dirty_or_staged_default_baseline(
    dirty_check: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_git(*_arguments: str) -> subprocess.CompletedProcess[bytes]:
        nonlocal calls
        calls += 1
        return _git_result(1 if calls == dirty_check else 0)

    monkeypatch.setattr(audit, "_run_git", fake_git)

    with pytest.raises(audit.AuditError, match="staged|unstaged"):
        audit._read_reviewed_committed_baseline()


def test_dirty_default_baseline_stops_official_check_before_capture(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(audit, "_run_git", lambda *_args: _git_result(1))

    def unexpected_capture(*, repeat: int) -> audit.Capture:
        raise AssertionError(f"capture unexpectedly ran with repeat={repeat}")

    monkeypatch.setattr(audit, "capture_all", unexpected_capture)

    assert audit.main(["check", "--repeat", "3"]) == 2
    assert "has staged changes" in capsys.readouterr().out


def test_git_unavailable_stops_official_check_before_capture(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unavailable(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("git is unavailable")

    def unexpected_capture(*, repeat: int) -> audit.Capture:
        raise AssertionError(f"capture unexpectedly ran with repeat={repeat}")

    monkeypatch.setattr(audit.subprocess, "run", unavailable)
    monkeypatch.setattr(audit, "capture_all", unexpected_capture)

    assert audit.main(["check", "--repeat", "3"]) == 2
    assert "cannot inspect committed settlement baseline" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("results", "message"),
    [
        ((_git_result(2, stderr=b"fatal diff"),), "fatal diff"),
        (
            (
                _git_result(0),
                _git_result(0),
                _git_result(128, stderr=b"missing HEAD baseline"),
            ),
            "cannot read committed settlement baseline: missing HEAD baseline",
        ),
    ],
)
def test_git_errors_stop_official_check_before_capture(
    results: tuple[subprocess.CompletedProcess[bytes], ...],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pending = iter(results)
    monkeypatch.setattr(audit, "_run_git", lambda *_args: next(pending))

    def unexpected_capture(*, repeat: int) -> audit.Capture:
        raise AssertionError(f"capture unexpectedly ran with repeat={repeat}")

    monkeypatch.setattr(audit, "capture_all", unexpected_capture)

    assert audit.main(["check", "--repeat", "3"]) == 2
    assert message in capsys.readouterr().out


def test_official_check_rejects_a_committed_baseline_with_a_stale_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    committed = audit.DEFAULT_BASELINE.read_bytes()

    def fake_git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
        if arguments[0] == "diff":
            return _git_result(0)
        return _git_result(0, stdout=committed)

    monkeypatch.setattr(audit, "_run_git", fake_git)
    monkeypatch.setattr(audit, "REVIEWED_BASELINE_SHA256", "0" * 64)

    with pytest.raises(audit.AuditError, match="not the reviewed baseline"):
        audit._read_reviewed_committed_baseline()


def test_default_baseline_alias_cannot_bypass_the_official_check(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    capture = _capture()
    baseline = audit._baseline_payload(capture)
    official_calls = 0

    def official() -> dict[str, object]:
        nonlocal official_calls
        official_calls += 1
        return baseline

    def unexpected_worktree_read(_path: Path) -> dict[str, object]:
        raise AssertionError("official check read the working-tree baseline")

    monkeypatch.setattr(audit, "_read_reviewed_committed_baseline", official)
    monkeypatch.setattr(audit, "_read_baseline", unexpected_worktree_read)
    monkeypatch.setattr(audit, "capture_all", lambda *, repeat: capture)

    alias = Path("tools") / "executor_settlement_baseline.json"
    assert audit.main(["check", "--repeat", "3", "--baseline", str(alias)]) == 0
    assert official_calls == 1
    assert "settlement check passed" in capsys.readouterr().out


def test_custom_baseline_check_is_labeled_as_an_unpinned_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    capture = _capture()
    custom = tmp_path / "custom.json"
    custom.write_text(
        json.dumps(audit._baseline_payload(capture)),
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "capture_all", lambda *, repeat: capture)

    assert audit.main(
        ["check", "--repeat", "3", "--baseline", str(custom)]
    ) == 0
    assert (
        "unpinned custom-baseline diagnostic passed: 30 scenarios x 3 runs"
        in capsys.readouterr().out
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload.update(extra=True), "exact schema"),
        (lambda payload: payload.update(format_version=99), "unsupported"),
        (lambda payload: payload.update(format_version=True), "format version.*integer"),
        (lambda payload: payload.update(format_version=1.0), "format version.*integer"),
        (lambda payload: payload.update(format_version="1"), "format version.*integer"),
        (lambda payload: payload.update(manifest={}), "wrong type"),
        (lambda payload: payload.update(scenarios=[]), "wrong type"),
        (lambda payload: payload.update(repeat=2), "repeat"),
        (lambda payload: payload.update(repeat=True), "repeat"),
        (lambda payload: payload.update(repeat=3.0), "repeat"),
        (lambda payload: payload.update(repeat="3"), "repeat"),
    ],
)
def test_baseline_reader_enforces_the_retained_schema(
    tmp_path: Path,
    mutation: object,
    message: str,
) -> None:
    baseline = tmp_path / "baseline.json"
    payload = audit._baseline_payload(_capture())
    assert callable(mutation)
    mutation(payload)
    baseline.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(audit.AuditError, match=message):
        audit._read_baseline(baseline)


@pytest.mark.parametrize(
    "text",
    [
        '{"format_version":1,"repeat":3,"repeat":4,"manifest":[],"scenarios":{}}',
        (
            '{"format_version":1,"repeat":3,"manifest":'
            '[{"id":"one","id":"two"}],"scenarios":{}}'
        ),
    ],
)
def test_baseline_reader_rejects_duplicate_json_members_at_every_depth(
    tmp_path: Path,
    text: str,
) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text(text, encoding="utf-8")

    with pytest.raises(audit.AuditError, match="duplicate JSON member"):
        audit._read_baseline(baseline)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_baseline_reader_rejects_non_standard_json_constants(
    tmp_path: Path,
    constant: str,
) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        (
            '{"format_version":1,"repeat":3,"manifest":[],"scenarios":'
            '{"nested":{"value":%s}}}'
        )
        % constant,
        encoding="utf-8",
    )

    with pytest.raises(audit.AuditError, match="non-standard JSON constant"):
        audit._read_baseline(baseline)


def test_baseline_reader_rejects_overflowed_json_float(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        (
            '{"format_version":1,"repeat":3,"manifest":[],"scenarios":'
            '{"nested":{"value":1e9999}}}'
        ),
        encoding="utf-8",
    )

    with pytest.raises(audit.AuditError, match="non-finite JSON number"):
        audit._read_baseline(baseline)


def test_baseline_reader_wraps_invalid_utf8(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_bytes(b"\xff")

    with pytest.raises(audit.AuditError, match="cannot read settlement baseline"):
        audit._read_baseline(baseline)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_trace_and_baseline_writers_reject_non_finite_numbers(
    tmp_path: Path,
    value: float,
) -> None:
    with pytest.raises(audit.AuditError, match="non-finite JSON number"):
        audit._canonical({"value": value})

    scenarios = _complete_scenarios()
    scenarios["success.all-nine"]["variants"][0]["value"] = value
    baseline = tmp_path / "baseline.json"
    with pytest.raises(audit.AuditError, match="non-finite JSON number"):
        audit._write_baseline(
            baseline,
            _capture(scenarios),
            replace_existing=False,
        )
    assert not baseline.exists()
    assert list(tmp_path.iterdir()) == []


def test_baseline_diff_is_exact_but_cannot_override_the_policy_oracle() -> None:
    capture = _capture()
    baseline = audit._baseline_payload(capture)

    assert audit._baseline_differences(baseline, capture) == []

    oracle_failure = _capture(
        dict(capture.scenarios),
        oracle_errors=("independent expected settlement mismatch",),
    )
    assert audit._baseline_differences(baseline, oracle_failure) == []
    assert not oracle_failure.ok

    changed_scenarios = json.loads(json.dumps(capture.scenarios))
    changed_scenarios["success.all-nine"]["variants"][0]["state"] = "absent"
    trace_drift = _capture(changed_scenarios)
    assert audit._baseline_differences(baseline, trace_drift) == [
        "scenario trace differs at $.success.all-nine.variants[0]: "
        "expected keys ['row'], observed ['row', 'state']"
    ]

    changed_manifest = dict(baseline)
    changed_manifest["manifest"] = []
    differences = audit._baseline_differences(changed_manifest, capture)
    assert differences == ["manifest differs at $: expected length 0, observed 30"]

    type_drift = copy.deepcopy(baseline)
    type_drift["manifest"][0]["variants"] = True
    assert audit._baseline_differences(type_drift, capture) == [
        "manifest differs at $[0].variants: expected bool True, observed int 1"
    ]

    typed_scenarios = copy.deepcopy(capture.scenarios)
    typed_scenarios["success.all-nine"]["variants"][0]["numeric"] = 1
    typed_capture = _capture(typed_scenarios)
    typed_baseline = audit._baseline_payload(typed_capture)
    typed_baseline["scenarios"]["success.all-nine"]["variants"][0][
        "numeric"
    ] = True
    assert audit._baseline_differences(typed_baseline, typed_capture) == [
        "scenario trace differs at $.success.all-nine.variants[0].numeric: "
        "expected bool True, observed int 1"
    ]
