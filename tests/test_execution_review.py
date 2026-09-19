from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sqlite3
from unittest.mock import Mock

import pytest

import namisync.workflows.execution_review as review_module
from namisync.core.evidence import Outcome, Provenance, RecordingStatus
from namisync.core.events import ItemOutcome
from namisync.core.execution import ItemRecordingReason
from namisync.core.integrity import IntegrityMode, IntegrityRecordCommand, InventoryState
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
from namisync.workflows import (
    ExecutionEvidenceResult,
    ExecutionEvidenceState,
    ExecutionEvidenceSubject,
    ExecutionEvidenceWindow,
    LocalWorkflowRuntime,
)
from namisync.workflows.execution_review import read_execution_evidence

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
