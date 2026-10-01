from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sqlite3
from threading import Lock
from unittest.mock import Mock

import pytest

import namisync.workflows.execution_review as review_module
from namisync.core.evidence import Outcome, Provenance, RecordingStatus
from namisync.core.events import ItemOutcome
from namisync.core.execution import (
    ItemRecordingReason,
    TaskRecordingIssue,
    TaskRecordingIssueReason,
)
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityRecordCommand,
    IntegrityResult,
    InventoryState,
)
from namisync.core.models import FileIdentity
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import OperationKind
from namisync.db.connections import connect_ledger_writer
from namisync.db.repositories import (
    ExecutionEvidenceKey,
    ExecutionEvidenceSubjectLimitError,
    InventoryPresence,
    LedgerRepository,
)
from namisync.db.timestamps import encode_utc
from namisync.interfaces.service import NamiSyncService
from namisync.core.session import OperationResult, SessionState
from namisync.workflows import (
    ExecutionEvidenceResult,
    ExecutionEvidenceState,
    ExecutionEvidenceSubject,
    ExecutionEvidenceWindow,
    LocalWorkflowRuntime,
    RetainedExecutionBinding,
)
from namisync.workflows.execution_review import (
    RetainedExecutionReadLimitError,
    build_retained_execution_review,
    read_execution_evidence,
    read_retained_integrity_items,
    read_retained_operation_items,
    retained_evidence_subjects,
)

from _db_fixtures import NOW, attestation, file_stat, operation, plan, setup_recorder


def _item(
    operation_value,
    outcome: Outcome = Outcome.SUCCEEDED,
    *,
    degraded: bool = False,
) -> ItemOutcome:
    return ItemOutcome(
        str(operation_value.op_id),
        operation_value.kind,
        operation_value.target_rel_path,
        outcome,
        recording=(RecordingStatus.DEGRADED if degraded else RecordingStatus.OK),
        recording_reason=(
            ItemRecordingReason.RECORD_WRITE_FAILED if degraded else None
        ),
    )


def test_retained_review_indexes_exact_items_and_complete_selection_ownership() -> None:
    stat = file_stat(identity_index=91, volume_serial="target-serial")
    first = operation(
        OperationKind.COPY, source_path="a.bin", target_path="shared.bin",
        source=stat, intended=stat,
    )
    competitor = operation(
        OperationKind.UPDATE, source_path="b.bin", target_path="shared.bin",
        source=stat, intended=stat,
    )
    excluded = operation(
        OperationKind.COPY, source_path="c.bin", target_path="excluded.bin",
        source=stat, intended=stat,
    )
    same_key_move = operation(
        OperationKind.MOVE, source_path="move.bin", target_path="same.bin",
        prior_target_path="same.bin", source=stat, target=stat, intended=stat,
    )
    plan_value = plan((first, competitor, excluded, same_key_move))
    operation_item = _item(first)
    exclusion_item = _item(excluded, Outcome.SKIPPED)
    move_item = _item(same_key_move)
    integrity_item = IntegrityOutcome(
        item_id=str(first.op_id), row_id=None, location_id=None,
        path=first.target_rel_path, result=IntegrityResult.VERIFIED,
    )
    result = OperationResult(
        SessionState.COMPLETED,
        items=(operation_item, exclusion_item, move_item, integrity_item),
    )
    binding = RetainedExecutionBinding(
        "task-" + "1" * 32, "2" * 32, 1, "3" * 32, "4" * 32
    )

    review = build_retained_execution_review(
        binding, result, plan_value,
        frozenset((
            str(first.op_id), str(competitor.op_id), str(same_key_move.op_id)
        )),
    )

    operations = read_retained_operation_items(
        review, (str(first.op_id), str(competitor.op_id), str(excluded.op_id))
    )
    integrity = read_retained_integrity_items(
        review, (str(first.op_id), str(competitor.op_id))
    )
    assert operations.items == (operation_item, exclusion_item)
    assert operations.items[0] is operation_item
    assert integrity.items == (integrity_item,)
    subjects = retained_evidence_subjects(
        review, (str(first.op_id), str(excluded.op_id), str(same_key_move.op_id))
    )
    assert tuple(value.target_owner_unique for value in subjects) == (
        False, False, True
    )
    assert review.result is result
    assert review.summary.result.filesystem == "completed"
    assert review.summary.trash_location.endswith(f".synctrash\\{binding.run_id}")


def test_retained_review_rejects_duplicate_changed_and_excess_items() -> None:
    stat = file_stat(identity_index=92, volume_serial="target-serial")
    member = operation(
        OperationKind.COPY, source_path="source.bin", target_path="target.bin",
        source=stat, intended=stat,
    )
    plan_value = plan((member,))
    binding = RetainedExecutionBinding(
        "task-" + "5" * 32, "6" * 32, 2, "7" * 32, "8" * 32
    )
    item = _item(member)
    with pytest.raises(ValueError, match="duplicated"):
        build_retained_execution_review(
            binding,
            OperationResult(SessionState.COMPLETED, items=(item, item)),
            plan_value,
            frozenset((str(member.op_id),)),
        )
    with pytest.raises(ValueError, match="Plan identity"):
        build_retained_execution_review(
            binding,
            OperationResult(
                SessionState.COMPLETED,
                items=(replace(item, path="other.bin"),),
            ),
            plan_value,
            frozenset((str(member.op_id),)),
        )
    for forged_integrity in (
        IntegrityOutcome(
            item_id=str(member.op_id), row_id=None, location_id=None,
            path="other.bin", result=IntegrityResult.VERIFIED,
        ),
        IntegrityOutcome(
            item_id=str(member.op_id), row_id=None, location_id=None,
            path=member.target_rel_path, result=IntegrityResult.VERIFIED,
            phase="baseline",
        ),
    ):
        with pytest.raises(ValueError, match="Plan identity"):
            build_retained_execution_review(
                binding,
                OperationResult(
                    SessionState.COMPLETED, items=(forged_integrity,)
                ),
                plan_value,
                frozenset((str(member.op_id),)),
            )
    review = build_retained_execution_review(
        binding,
        OperationResult(SessionState.COMPLETED, items=(item,)),
        plan_value,
        frozenset((str(member.op_id),)),
    )
    with pytest.raises(RetainedExecutionReadLimitError):
        read_retained_operation_items(review, tuple("x" for _ in range(257)))
    assert read_retained_operation_items(
        review, tuple("missing" for _ in range(256))
    ).items == ()


def test_runtime_retained_capture_is_exact_idempotent_and_disposable() -> None:
    stat = file_stat(identity_index=93, volume_serial="target-serial")
    member = operation(
        OperationKind.COPY, source_path="source.bin", target_path="target.bin",
        source=stat, intended=stat,
    )
    plan_value = plan((member,))
    item = _item(member)
    result = OperationResult(SessionState.COMPLETED, items=(item,))
    binding = RetainedExecutionBinding(
        "task-" + "9" * 32, "a" * 32, 3, "b" * 32, "c" * 32
    )
    runtime = object.__new__(LocalWorkflowRuntime)
    runtime._lock = Lock()
    runtime._closing = False
    runtime._closed = False
    runtime._retained_execution_reviews = {}

    first = runtime.capture_execution_review(
        binding, result, plan=plan_value,
        selection=frozenset((str(member.op_id),)),
    )
    assert runtime.capture_execution_review(binding, None) is first
    assert runtime.read_task_execution_items(
        binding.task_id, (str(member.op_id),)
    ).items == (item,)
    with pytest.raises(ValueError, match="result identity"):
        runtime.capture_execution_review(binding, replace(result))
    runtime._closing = True
    runtime.retire_captured_execution_review(binding.task_id)
    runtime.retire_captured_execution_review(binding.task_id)
    with pytest.raises(RuntimeError, match="closed"):
        runtime.capture_execution_review(
            binding, result, plan=plan_value,
            selection=frozenset((str(member.op_id),)),
        )
    assert runtime._retained_execution_reviews == {}


def test_runtime_close_retires_populated_execution_review(tmp_path: Path) -> None:
    stat = file_stat(identity_index=94, volume_serial="target-serial")
    member = operation(
        OperationKind.COPY, source_path="source.bin", target_path="target.bin",
        source=stat, intended=stat,
    )
    plan_value = plan((member,))
    binding = RetainedExecutionBinding(
        "task-" + "d" * 32, "e" * 32, 4, "f" * 32, "1" * 32
    )
    runtime = LocalWorkflowRuntime(tmp_path / "ledger.db", tmp_path / "history.db")
    runtime.capture_execution_review(
        binding,
        OperationResult(SessionState.COMPLETED, items=(_item(member),)),
        plan=plan_value,
        selection=frozenset((str(member.op_id),)),
    )

    service = NamiSyncService.__new__(NamiSyncService)
    service._runtime = runtime
    service._dispatcher = Mock(
        shutdown=Mock(return_value=Mock(
            complete=True, unfinished=(), custody_released=True
        ))
    )
    service._observer = Mock(close=Mock())
    service._lifecycle = Mock(close=Mock(), retire_all=Mock())
    service._lock = Lock()
    service._close_lock = Lock()
    service._plan_selections = {}
    service._visibility_receipts = {}
    service._task_inventory_details = {}
    service._closed = False
    service._shutdown = None
    service._runtime_closed = False
    service._observer_closed = False

    assert service.close().complete

    assert runtime._retained_execution_reviews == {}
    with pytest.raises(RuntimeError, match="closed"):
        runtime.read_task_execution_summary(binding.task_id)


def test_retained_summary_preserves_axes_omissions_and_mixed_failure_facts() -> None:
    stat = file_stat(identity_index=95, volume_serial="target-serial")
    capacity = operation(
        OperationKind.COPY, source_path="capacity.bin", target_path="capacity.bin",
        source=stat, intended=stat,
    )
    generic = operation(
        OperationKind.COPY, source_path="generic.bin", target_path="generic.bin",
        source=stat, intended=stat,
    )
    plan_value = plan((capacity, generic))
    result = OperationResult(
        SessionState.FAILED,
        recording=RecordingStatus.DEGRADED,
        items=(
            replace(_item(capacity, Outcome.FAILED), reason="disk-capacity"),
            replace(_item(generic, Outcome.FAILED), reason="io-error"),
        ),
        recording_issues=(
            TaskRecordingIssue(TaskRecordingIssueReason.FINAL_FLUSH_FAILED),
        ),
        omitted_detail_count=7,
    )
    binding = RetainedExecutionBinding(
        "task-" + "2" * 32, "3" * 32, 5, "4" * 32, "5" * 32
    )

    summary = build_retained_execution_review(
        binding,
        result,
        plan_value,
        frozenset((str(capacity.op_id), str(generic.op_id))),
    ).summary

    assert summary.result.filesystem == "failed"
    assert summary.result.recording == "degraded"
    assert summary.result.omitted_detail_count == 7
    assert summary.result.recording_issues[0].reason == "final-flush-failed"
    assert (summary.failed_operation_count, summary.disk_capacity_failure_count) == (
        2, 1
    )




def test_execution_review_classifies_five_states_from_current_ledger(
    tmp_path: Path,
) -> None:
    stats = tuple(
        file_stat(size=size, identity_index=index, volume_serial="target-serial")
        for index, size in enumerate((0, 7, 8, 9), start=11)
    )
    operations = tuple(
        operation(
            OperationKind.COPY,
            source_path=f"source-{index}.bin",
            target_path=f"target-{index}.bin",
            source=stat,
            intended=stat,
        )
        for index, stat in enumerate(stats)
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan(operations))
    try:
        recorded_evidence = attestation(stats[0], digest_byte=1)
        setup.run.record_copied(operations[0].op_id, recorded_evidence)

        prior_verified = attestation(stats[1], digest_byte=2)
        verified_identity = setup.run.record_copied(
            operations[1].op_id, prior_verified
        )
        verified_evidence = attestation(
            stats[1], digest_byte=2, provenance=Provenance.VERIFY_ATTESTED
        )
        setup.run.record_integrity(
            IntegrityRecordCommand(
                IntegrityMode.VERIFY,
                "verify-target-1",
                verified_identity.row_id,
                verified_identity.location_id,
                verified_identity.rel_path_key,
                verified_identity.scope_token,
                InventoryState.PRESENT,
                stats[1],
                prior_verified,
                verified_evidence,
                True,
                False,
            )
        )

        setup.run.record_copied(operations[3].op_id, attestation(stats[3]))
        writer = connect_ledger_writer(setup.recorder.path)
        try:
            writer.execute(
                "UPDATE inventory SET scope_token = ? WHERE rel_path_key = ?",
                ("later-scan", normalize_relative_path(operations[3].target_rel_path)),
            )
            writer.commit()
        finally:
            writer.close()

        non_copy = operation(
            OperationKind.MOVE,
            source_path="old.bin",
            target_path="new.bin",
            source=stats[0],
            intended=stats[0],
        )
        subjects = (
            ExecutionEvidenceSubject(_item(operations[0], degraded=True), True),
            ExecutionEvidenceSubject(_item(operations[1]), True),
            ExecutionEvidenceSubject(_item(operations[2]), True),
            ExecutionEvidenceSubject(_item(operations[3]), True),
            ExecutionEvidenceSubject(_item(non_copy), True),
        )
        with LedgerRepository(setup.recorder.path) as repository:
            window = read_execution_evidence(repository, setup.run_token, subjects)

        assert tuple(result.state for result in window.results) == (
            ExecutionEvidenceState.RECORDED_COPY,
            ExecutionEvidenceState.ALREADY_VERIFIED,
            ExecutionEvidenceState.UNRECORDED,
            ExecutionEvidenceState.SUPERSEDED,
            ExecutionEvidenceState.NOT_APPLICABLE,
        )
        assert window.results[0].content == recorded_evidence.content
        assert window.results[1].content == verified_evidence.content
        assert all(result.content is None for result in window.results[2:])
        assert window.results[0].content.size == 0

        with LedgerRepository(setup.recorder.path) as repository:
            absent_run = read_execution_evidence(
                repository, "f" * 32, (subjects[0],)
            )
            ambiguous = read_execution_evidence(
                repository,
                setup.run_token,
                (ExecutionEvidenceSubject(subjects[0].item, False),),
            )
        assert absent_run.results[0].state is ExecutionEvidenceState.UNRECORDED
        assert ambiguous.results[0].state is ExecutionEvidenceState.SUPERSEDED
        assert ambiguous.results[0].content is None

        writer = connect_ledger_writer(setup.recorder.path)
        try:
            writer.execute(
                "UPDATE inventory SET hash_provenance = 'readback' WHERE id = ?",
                (int(verified_identity.row_id),),
            )
            writer.commit()
        finally:
            writer.close()
        with LedgerRepository(setup.recorder.path) as repository:
            readback = read_execution_evidence(
                repository, setup.run_token, (subjects[1],)
            )
        assert readback.results[0].state is ExecutionEvidenceState.ALREADY_VERIFIED
        assert readback.results[0].content is not None
        assert readback.results[0].content.provenance is Provenance.READBACK_ATTESTED
    finally:
        setup.recorder.close()


def test_mismatched_receipt_is_unrecorded_and_incoherent_stat_is_superseded(
    tmp_path: Path,
) -> None:
    stat = file_stat(identity_index=31, volume_serial="target-serial")
    copy = operation(
        OperationKind.COPY, source=stat, intended=stat, target_path="target.bin"
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan((copy,)))
    try:
        recorded_identity = setup.run.record_copied(copy.op_id, attestation(stat))
        subject = ExecutionEvidenceSubject(_item(copy), True)
        for column, value in (
            ("outcome", "failed"),
            ("kind", "update"),
            ("target_rel_path", "other.bin"),
        ):
            writer = connect_ledger_writer(setup.recorder.path)
            try:
                writer.execute(
                    f"UPDATE operations SET {column} = ? WHERE op_token = ?",
                    (value, str(copy.op_id)),
                )
                writer.commit()
            finally:
                writer.close()
            with LedgerRepository(setup.recorder.path) as repository:
                mismatch = read_execution_evidence(
                    repository, setup.run_token, (subject,)
                )
            assert mismatch.results[0].state is ExecutionEvidenceState.UNRECORDED
            writer = connect_ledger_writer(setup.recorder.path)
            try:
                writer.execute(
                    f"UPDATE operations SET {column} = ? WHERE op_token = ?",
                    (
                        {
                            "outcome": "succeeded",
                            "kind": "copy",
                            "target_rel_path": "target.bin",
                        }[column],
                        str(copy.op_id),
                    ),
                )
                writer.commit()
            finally:
                writer.close()

        writer = connect_ledger_writer(setup.recorder.path)
        try:
            writer.execute(
                "UPDATE operations SET outcome = 'succeeded' WHERE op_token = ?",
                (str(copy.op_id),),
            )
            writer.execute(
                """UPDATE inventory
                      SET verification_invalidated_at = ?,
                          verification_invalidated_reason = 'metadata-drift'
                    WHERE id = ?""",
                (encode_utc(NOW), int(recorded_identity.row_id)),
            )
            writer.commit()
        finally:
            writer.close()
        with LedgerRepository(setup.recorder.path) as repository:
            invalidated = read_execution_evidence(
                repository, setup.run_token, (subject,)
            )
        assert invalidated.results[0].state is ExecutionEvidenceState.SUPERSEDED
        assert invalidated.results[0].content is None

        writer = connect_ledger_writer(setup.recorder.path)
        try:
            writer.execute(
                """UPDATE inventory
                      SET verification_invalidated_at = NULL,
                          verification_invalidated_reason = NULL,
                          observed_attributes = observed_attributes + 1"""
                + " WHERE id = ?",
                (int(recorded_identity.row_id),),
            )
            writer.commit()
        finally:
            writer.close()
        with LedgerRepository(setup.recorder.path) as repository:
            incoherent = read_execution_evidence(
                repository, setup.run_token, (subject,)
            )
        assert incoherent.results[0].state is ExecutionEvidenceState.SUPERSEDED
        assert incoherent.results[0].content is None
    finally:
        setup.recorder.close()


def test_repository_read_is_atomic_and_uses_at_most_three_data_selects(
    tmp_path: Path,
) -> None:
    stat = file_stat(identity_index=41, volume_serial="target-serial")
    copy = operation(OperationKind.COPY, source=stat, intended=stat)
    setup = setup_recorder(tmp_path / "ledger.db", plan((copy,)))
    writer = connect_ledger_writer(setup.recorder.path)
    statements: list[str] = []

    def trace(statement: str) -> None:
        statements.append(statement)
        if statement.lstrip().upper().startswith("SELECT") and sum(
            candidate.lstrip().upper().startswith("SELECT")
            for candidate in statements
        ) == 2:
            writer.execute("UPDATE inventory SET scope_token = 'later-scan'")
            writer.commit()

    try:
        recorded_identity = setup.run.record_copied(copy.op_id, attestation(stat))
        with LedgerRepository(
            setup.recorder.path, trace_callback=trace
        ) as repository:
            snapshot = repository.read_execution_evidence(
                setup.run_token,
                (ExecutionEvidenceKey(str(copy.op_id), normalize_relative_path("a.txt")),),
            )
            selects = [
                statement for statement in statements
                if statement.lstrip().upper().startswith("SELECT")
            ]
            statements.clear()
            empty = repository.read_execution_evidence(setup.run_token, ())
            assert empty.run is None and empty.receipts == () and empty.inventory == ()
            assert statements == []
        assert len(selects) == 3
        assert snapshot.inventory[0].scope_token == setup.run_token
        with LedgerRepository(setup.recorder.path) as repository:
            assert repository.get_inventory(setup.target_location_id)[0].scope_token == "later-scan"
    finally:
        writer.close()
        setup.recorder.close()


def test_repository_bounds_256_distinct_keys_and_refuses_first_excess_pre_sql(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    statements: list[str] = []
    keys = tuple(
        ExecutionEvidenceKey(f"operation-{index}", normalize_relative_path(f"{index}.bin"))
        for index in range(257)
    )
    try:
        with LedgerRepository(
            setup.recorder.path, trace_callback=statements.append
        ) as repository:
            snapshot = repository.read_execution_evidence(
                setup.run_token, keys[:256]
            )
            selects = [
                statement for statement in statements
                if statement.lstrip().upper().startswith("SELECT")
            ]
            assert len(selects) == 3
            assert snapshot.receipts == () and snapshot.inventory == ()

            statements.clear()
            with pytest.raises(ExecutionEvidenceSubjectLimitError):
                repository.read_execution_evidence(setup.run_token, keys)
            assert statements == []
    finally:
        setup.recorder.close()


def test_absent_missing_and_changed_identity_are_superseded_without_digest(
    tmp_path: Path,
) -> None:
    stat = file_stat(identity_index=51, volume_serial="target-serial")
    copy = operation(OperationKind.COPY, source=stat, intended=stat)
    setup = setup_recorder(tmp_path / "ledger.db", plan((copy,)))
    try:
        setup.run.record_copied(copy.op_id, attestation(stat))
        key = ExecutionEvidenceKey(
            str(copy.op_id), normalize_relative_path(copy.target_rel_path)
        )
        with LedgerRepository(setup.recorder.path) as repository:
            coherent = repository.read_execution_evidence(
                setup.run_token, (key,)
            )
        row = coherent.inventory[0]
        assert row.observed is not None
        variants = (
            replace(coherent, inventory=()),
            replace(
                coherent,
                inventory=(replace(row, presence=InventoryPresence.MISSING),),
            ),
            replace(
                coherent,
                inventory=(
                    replace(
                        row,
                        observed=replace(
                            row.observed,
                            file_identity=FileIdentity("target-serial", 999),
                        ),
                    ),
                ),
            ),
        )
        subject = ExecutionEvidenceSubject(_item(copy), True)
        for snapshot in variants:
            repository = Mock()
            repository.read_execution_evidence.return_value = snapshot
            window = read_execution_evidence(
                repository, setup.run_token, (subject,)
            )
            assert window.results[0].state is ExecutionEvidenceState.SUPERSEDED
            assert window.results[0].content is None
    finally:
        setup.recorder.close()


def test_runtime_reuses_and_retires_execution_evidence_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stat = file_stat(identity_index=61, volume_serial="target-serial")
    copy = operation(OperationKind.COPY, source=stat, intended=stat)
    setup = setup_recorder(tmp_path / "ledger.db", plan((copy,)))
    runtime = LocalWorkflowRuntime(setup.recorder.path, tmp_path / "history.db")
    subject = ExecutionEvidenceSubject(_item(copy), True)
    try:
        setup.run.record_copied(copy.op_id, attestation(stat))
        assert runtime.read_execution_evidence(
            setup.run_token, (subject,)
        ).results[0].state is ExecutionEvidenceState.RECORDED_COPY
        reader = runtime._ledger_reader
        assert reader is not None
        assert runtime.read_execution_evidence(
            setup.run_token, (subject,)
        ).results[0].state is ExecutionEvidenceState.RECORDED_COPY
        assert runtime._ledger_reader is reader

        monkeypatch.setattr(
            reader,
            "read_execution_evidence",
            Mock(side_effect=ValueError("bad evidence row")),
        )
        with pytest.raises(ValueError, match="bad evidence row"):
            runtime.read_execution_evidence(setup.run_token, (subject,))
        assert runtime._ledger_reader is None
        with pytest.raises(sqlite3.ProgrammingError):
            reader._connection.execute("SELECT 1")
    finally:
        runtime.close()
        setup.recorder.close()


def test_subject_limit_precedes_normalization_and_empty_runtime_is_inert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    copy = operation(OperationKind.COPY)
    subject = ExecutionEvidenceSubject(_item(copy), True)
    monkeypatch.setattr(
        review_module,
        "normalize_relative_path",
        Mock(side_effect=AssertionError("normalization must not start")),
    )
    with pytest.raises(ExecutionEvidenceSubjectLimitError):
        read_execution_evidence(Mock(), "a" * 32, (subject,) * 257)

    runtime = LocalWorkflowRuntime(tmp_path / "absent-ledger.db", tmp_path / "history.db")
    try:
        with pytest.raises(ExecutionEvidenceSubjectLimitError):
            runtime.read_execution_evidence("a" * 32, (subject,) * 257)
        assert runtime.read_execution_evidence("a" * 32, ()) == ExecutionEvidenceWindow(
            "a" * 32, ()
        )
        assert not (tmp_path / "absent-ledger.db").exists()
        runtime.close()
        with pytest.raises(RuntimeError, match="workflow runtime is closed"):
            runtime.read_execution_evidence("a" * 32, ())
    finally:
        runtime.close()


def test_service_forwards_execution_evidence_without_reclassification() -> None:
    expected = ExecutionEvidenceWindow("a" * 32, ())
    service = object.__new__(NamiSyncService)
    service._runtime = Mock()
    service._runtime.read_execution_evidence.return_value = expected

    assert service.read_execution_evidence("a" * 32, ()) is expected
    service._runtime.read_execution_evidence.assert_called_once_with("a" * 32, ())


def test_execution_evidence_result_rejects_content_on_noncoherent_state() -> None:
    with pytest.raises(TypeError, match="content has the wrong type"):
        ExecutionEvidenceResult(
            "operation", ExecutionEvidenceState.UNRECORDED, object()
        )
    with pytest.raises(ValueError, match="only coherent"):
        ExecutionEvidenceResult("operation", ExecutionEvidenceState.RECORDED_COPY)
    content = attestation(file_stat()).content
    with pytest.raises(ValueError, match="only coherent"):
        ExecutionEvidenceResult(
            "operation", ExecutionEvidenceState.SUPERSEDED, content
        )
