from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from namisync.core.evidence import Provenance
from namisync.core.integrity import (
    InventoryVerificationState,
    IntegrityMode,
    IntegrityRecordCommand,
    InventoryState,
    RecordDisposition,
    VerificationInvalidationCommand,
    VerificationInvalidationReason,
)
from namisync.core.models import (
    FileRecord,
    ScanResult,
    ScanScope,
    UnsupportedReason,
    UnsupportedRecord,
    VolumeEvidence,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.recording import (
    InventoryCommand,
    InventoryVisibilityAction,
    InventoryVisibilityCommand,
)
from namisync.db.connections import connect_ledger_reader
from namisync.db.repositories import LedgerRepository
from namisync.workflows.views import inventory_row_view

from _db_fixtures import NOW, attestation, file_stat, plan, setup_recorder


def _scan(
    setup,
    records: tuple[FileRecord, ...],
    *,
    complete: bool = True,
    scope: ScanScope | None = None,
    unsupported: tuple[UnsupportedRecord, ...] = (),
) -> ScanResult:
    sync_plan = plan(())
    return ScanResult(
        root=sync_plan.source_root,
        volume_id=sync_plan.source_volume_id,
        volume_evidence=VolumeEvidence("Source", "C:"),
        profile=sync_plan.source_profile,
        files=records,
        directories=(),
        unsupported=unsupported,
        warnings=(),
        scope=scope or ScanScope.full(),
        complete=complete,
    )


def _file(path: str, index: int, *, size: int = 7) -> FileRecord:
    stat = file_stat(size=size, identity_index=index)
    return FileRecord(
        path,
        normalize_relative_path(path),
        stat.size,
        stat.mtime_ns,
        stat.file_identity,
        stat.nlink,
        stat.metadata,
    )


def _unsupported(path: str) -> UnsupportedRecord:
    return UnsupportedRecord(
        path,
        normalize_relative_path(path),
        UnsupportedReason.ACCESS_DENIED,
    )


def _file_with_stat(path: str, stat) -> FileRecord:
    return FileRecord(
        path,
        normalize_relative_path(path),
        stat.size,
        stat.mtime_ns,
        stat.file_identity,
        stat.nlink,
        stat.metadata,
    )


def test_complete_inventory_over_33k_marks_missing_without_parameter_overflow(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = tuple(_file(f"folder\\file-{index:05d}.bin", index) for index in range(33_010))
    try:
        first = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records),
                "scope-1",
                NOW,
            )
        )
        assert first.disposition is RecordDisposition.APPLIED
        assert first.observed_count == 33_010
        assert first.missing_count == 0

        second = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records[:1]),
                "scope-2",
                NOW,
            )
        )
        assert second.missing_count == 33_009

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            counts = dict(
                connection.execute(
                    "SELECT presence, count(*) FROM inventory GROUP BY presence"
                ).fetchall()
            )
            assert counts == {"missing": 33_009, "present": 1}
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_incomplete_and_offline_inventory_never_infer_missing(tmp_path: Path) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = (_file("a.txt", 1), _file("b.txt", 2))
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records),
                "complete",
                NOW,
            )
        )
        incomplete = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records[:1], complete=False),
                "incomplete",
                NOW,
            )
        )
        offline = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, ()),
                "offline",
                NOW,
                online=False,
            )
        )
        assert incomplete.missing_count == 0
        assert offline.disposition is RecordDisposition.NOOP

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            assert connection.execute(
                "SELECT count(*) FROM inventory WHERE presence = 'present'"
            ).fetchone()[0] == 2
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_selected_inventory_reconciles_only_its_complete_scope(tmp_path: Path) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    seeded = tuple(_file(f"{name}.txt", index) for index, name in enumerate("ABCD", 1))
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, seeded),
                "seed",
                NOW,
            )
        )
        selected = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(
                    setup,
                    (seeded[0],),
                    scope=ScanScope.selected(("A.txt", "B.txt")),
                ),
                "selected",
                NOW,
            )
        )
        interrupted = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(
                    setup,
                    (),
                    complete=False,
                    scope=ScanScope.selected(("C.txt", "D.txt")),
                ),
                "interrupted",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            rows = {
                row.rel_path: row.presence.value
                for row in repository.get_inventory(setup.source_location_id)
            }

        assert selected.missing_count == 1
        assert interrupted.missing_count == 0
        assert rows == {
            "A.txt": "present",
            "B.txt": "missing",
            "C.txt": "present",
            "D.txt": "present",
        }
    finally:
        setup.recorder.close()


def test_inventory_row_id_lookup_is_bounded_ordered_and_location_scoped(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = tuple(
        _file(f"folder\\file-{index:04d}.bin", index)
        for index in range(1, 1_002)
    )
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records),
                "row-id-seed",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            rows = repository.get_inventory(setup.source_location_id)
        valid_ids = tuple(row.row_id for row in reversed(rows))
        requested = (
            valid_ids[0],
            "0",
            "01",
            "+1",
            " 1",
            valid_ids[0],
            *valid_ids[1:],
            "999999999999999999999999999999999999",
        )
        trace: list[str] = []
        with LedgerRepository(
            setup.recorder.path, trace_callback=trace.append
        ) as repository:
            selected = repository.get_inventory_by_row_ids(
                setup.source_location_id, requested
            )
            bounded_selects = [
                statement
                for statement in trace
                if "SELECT * FROM inventory" in statement
                and "AND id IN" in statement
            ]
            assert tuple(row.row_id for row in selected) == valid_ids
            assert len(bounded_selects) == 3
            assert any(statement == "BEGIN" for statement in trace)
            assert any(statement == "ROLLBACK" for statement in trace)
            assert repository.get_inventory_by_row_ids(
                setup.target_location_id, (valid_ids[0],)
            ) == ()
            assert repository.get_inventory_by_row_ids(
                setup.source_location_id, ("0", "01", "+1", " 1")
            ) == ()
    finally:
        setup.recorder.close()


def test_inventory_row_id_chunks_share_one_read_snapshot(tmp_path: Path) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = tuple(_file(f"file-{index:03d}.bin", index) for index in range(1, 402))
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records),
                "snapshot-old",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            row_ids = tuple(
                row.row_id
                for row in repository.get_inventory(setup.source_location_id)
            )

        select_count = 0
        refreshed = False

        def trace(statement: str) -> None:
            nonlocal select_count, refreshed
            if (
                "SELECT * FROM inventory" not in statement
                or "AND id IN" not in statement
            ):
                return
            select_count += 1
            if select_count == 2:
                setup.recorder.record_inventory(
                    InventoryCommand(
                        setup.source_location_id,
                        setup.host_id,
                        _scan(setup, records),
                        "snapshot-new",
                        NOW,
                    )
                )
                refreshed = True

        with LedgerRepository(
            setup.recorder.path, trace_callback=trace
        ) as repository:
            selected = repository.get_inventory_by_row_ids(
                setup.source_location_id, row_ids
            )

        assert select_count == 2
        assert refreshed is True
        assert {row.scope_token for row in selected} == {"snapshot-old"}
        with LedgerRepository(setup.recorder.path) as repository:
            assert {
                row.scope_token
                for row in repository.get_inventory_by_row_ids(
                    setup.source_location_id, (row_ids[-1],)
                )
            } == {"snapshot-new"}
    finally:
        setup.recorder.close()


def test_exact_inventory_marks_absent_unsupported_subject_missing(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    path = "unreadable.txt"
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (), unsupported=(_unsupported(path),)),
                "unsupported",
                NOW,
            )
        )
        refreshed = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(
                    setup,
                    (),
                    scope=ScanScope.selected((path,)),
                ),
                "selected-absent",
                NOW,
            )
        )

        with LedgerRepository(setup.recorder.path) as repository:
            row = repository.get_inventory(setup.source_location_id)[0]

        assert refreshed.missing_count == 1
        assert row.presence.value == "missing"
        assert row.missing_since is not None
    finally:
        setup.recorder.close()


def test_unsupported_reappearance_sets_reappeared_marker(tmp_path: Path) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    path = "unreadable.txt"
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (), unsupported=(_unsupported(path),)),
                "unsupported",
                NOW,
            )
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, ()),
                "missing",
                NOW,
            )
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (), unsupported=(_unsupported(path),)),
                "reappeared-unsupported",
                NOW,
            )
        )

        with LedgerRepository(setup.recorder.path) as repository:
            row = repository.get_inventory(setup.source_location_id)[0]

        assert row.presence.value == "unsupported"
        assert row.missing_since is None
        assert row.reappeared_at is not None
    finally:
        setup.recorder.close()


def test_missing_acknowledgement_and_restore_preserve_inventory_evidence(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    row = _file("missing.txt", 1)
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (row,)),
                "present",
                NOW,
            )
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, ()),
                "missing",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            missing = repository.get_unacknowledged_missing(
                setup.source_location_id
            )[0]

        assert setup.recorder.change_inventory_visibility(
            InventoryVisibilityCommand(
                "ack-1",
                setup.source_location_id,
                missing.row_id,
                InventoryVisibilityAction.ACKNOWLEDGE,
                NOW,
            )
        ) is RecordDisposition.APPLIED
        with LedgerRepository(setup.recorder.path) as repository:
            assert repository.get_unacknowledged_missing(
                setup.source_location_id
            ) == ()
            acknowledged = repository.get_inventory(
                setup.source_location_id
            )[0]
        assert acknowledged.observed == row.stat

        assert setup.recorder.change_inventory_visibility(
            InventoryVisibilityCommand(
                "restore-1",
                setup.source_location_id,
                missing.row_id,
                InventoryVisibilityAction.RESTORE,
                NOW,
            )
        ) is RecordDisposition.APPLIED
        with LedgerRepository(setup.recorder.path) as repository:
            restored = repository.get_unacknowledged_missing(
                setup.source_location_id
            )[0]
        assert restored.row_id == missing.row_id
        assert restored.observed == row.stat
    finally:
        setup.recorder.close()


def test_integrity_write_is_fully_conditional_and_advances_only_true_verification(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    record = _file("a.txt", 1)
    expected = record.stat
    baseline = attestation(
        expected, digest_byte=3, provenance=Provenance.READBACK_ATTESTED
    )
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (record,)),
                "scope",
                NOW,
            )
        )
        connection = connect_ledger_reader(setup.recorder.path)
        try:
            row_id = str(
                connection.execute(
                    "SELECT id FROM inventory WHERE rel_path_key = 'A.TXT'"
                ).fetchone()[0]
            )
        finally:
            connection.close()

        baseline_command = IntegrityRecordCommand(
            IntegrityMode.BASELINE,
            "item-baseline",
            row_id,
            str(setup.source_location_id),
            record.rel_path_key,
            "scope",
            InventoryState.PRESENT,
            expected,
            None,
            baseline,
            False,
            False,
        )
        assert setup.recorder.record_integrity(baseline_command) is RecordDisposition.APPLIED
        assert setup.recorder.record_integrity(baseline_command) is RecordDisposition.NOOP

        drifted_stats = (
            replace(expected, size=expected.size + 1),
            replace(expected, mtime_ns=expected.mtime_ns + 1),
            replace(expected, file_identity=replace(expected.file_identity, file_index=9)),
            replace(expected, nlink=2),
            replace(expected, metadata=replace(expected.metadata, attributes=2)),
            replace(expected, metadata=replace(expected.metadata, created_ns=9)),
        )
        for index, drifted in enumerate(drifted_stats):
            stale = replace(
                baseline_command,
                mode=IntegrityMode.VERIFY,
                item_id=f"stale-{index}",
                expected_stat=drifted,
                expected_baseline=baseline,
                attestation=attestation(
                    drifted,
                    digest_byte=3,
                    provenance=Provenance.VERIFY_ATTESTED,
                ),
                advances_last_verified=True,
            )
            assert setup.recorder.record_integrity(stale) is RecordDisposition.STALE

        verified = attestation(
            expected, digest_byte=3, provenance=Provenance.VERIFY_ATTESTED
        )
        verify_command = IntegrityRecordCommand(
            IntegrityMode.VERIFY,
            "item-verify",
            row_id,
            str(setup.source_location_id),
            record.rel_path_key,
            "scope",
            InventoryState.PRESENT,
            expected,
            baseline,
            verified,
            True,
            True,
        )
        assert setup.recorder.record_integrity(verify_command) is RecordDisposition.APPLIED

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            row = connection.execute(
                "SELECT * FROM inventory WHERE id = ?", (row_id,)
            ).fetchone()
            assert row["hash_provenance"] == Provenance.VERIFY_ATTESTED.value
            assert row["last_verified_at"] == "2026-01-02T03:04:05.123456Z"
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_verification_invalidation_is_sticky_until_guarded_positive_evidence(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    original = _file("a.txt", 1)
    expected = original.stat
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (original,)),
                "scope-1",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            row = repository.get_inventory(setup.source_location_id)[0]
        baseline = attestation(
            expected,
            digest_byte=4,
            provenance=Provenance.READBACK_ATTESTED,
        )
        setup.recorder.record_integrity(
            IntegrityRecordCommand(
                IntegrityMode.BASELINE,
                "baseline",
                row.row_id,
                str(setup.source_location_id),
                row.rel_path_key,
                "scope-1",
                InventoryState.PRESENT,
                expected,
                None,
                baseline,
                False,
                False,
            )
        )
        verified = attestation(
            expected,
            digest_byte=4,
            provenance=Provenance.VERIFY_ATTESTED,
        )
        setup.recorder.record_integrity(
            IntegrityRecordCommand(
                IntegrityMode.VERIFY,
                "verify-1",
                row.row_id,
                str(setup.source_location_id),
                row.rel_path_key,
                "scope-1",
                InventoryState.PRESENT,
                expected,
                baseline,
                verified,
                True,
                False,
            )
        )

        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (original,)),
                "scope-2",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            current = repository.get_inventory(setup.source_location_id)[0]
            assert repository.get_stale_inventory(
                setup.source_location_id, NOW
            ) == ()
        assert current.verification_state is InventoryVerificationState.VERIFIED
        assert current.invalidation is None

        mismatch = VerificationInvalidationCommand(
            item_id="mismatch",
            row_id=current.row_id,
            location_id=str(setup.source_location_id),
            rel_path_key=current.rel_path_key,
            scope_token="scope-2",
            expected_state=InventoryState.PRESENT,
            expected_stat=expected,
            expected_baseline=current.attestation,
            expected_invalidation=None,
            reason=VerificationInvalidationReason.HASH_MISMATCH,
            invalidated_at=NOW,
        )
        assert (
            setup.recorder.record_verification_invalidation(mismatch)
            is RecordDisposition.APPLIED
        )
        assert (
            setup.recorder.record_verification_invalidation(mismatch)
            is RecordDisposition.NOOP
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (original,)),
                "scope-3",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            mismatched = repository.get_inventory(setup.source_location_id)[0]
            stale = repository.get_stale_inventory(setup.source_location_id, NOW)
        assert mismatched.verification_state is InventoryVerificationState.MISMATCHED
        assert stale == (mismatched,)
        view = inventory_row_view(mismatched)
        assert view.verification_state == "mismatched"
        assert view.verification_invalidated_at == NOW.isoformat()
        assert view.verification_invalidated_reason == "hash-mismatch"

        drifted_stat = replace(expected, size=expected.size + 1)
        drifted = _file_with_stat("a.txt", drifted_stat)
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (drifted,)),
                "scope-4",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            drifted_mismatch = repository.get_inventory(
                setup.source_location_id
            )[0]
        assert (
            drifted_mismatch.invalidation.reason
            is VerificationInvalidationReason.HASH_MISMATCH
        )
        assert (
            drifted_mismatch.verification_state
            is InventoryVerificationState.MISMATCHED
        )
        assert (
            inventory_row_view(drifted_mismatch).verification_state
            == "mismatched"
        )

        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (original,)),
                "scope-5",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            still_mismatched = repository.get_inventory(
                setup.source_location_id
            )[0]
        assert (
            still_mismatched.invalidation.reason
            is VerificationInvalidationReason.HASH_MISMATCH
        )
        assert (
            still_mismatched.verification_state
            is InventoryVerificationState.MISMATCHED
        )
        downgrade = VerificationInvalidationCommand(
            item_id="metadata-after-mismatch",
            row_id=still_mismatched.row_id,
            location_id=str(setup.source_location_id),
            rel_path_key=still_mismatched.rel_path_key,
            scope_token="scope-5",
            expected_state=InventoryState.PRESENT,
            expected_stat=expected,
            expected_baseline=still_mismatched.attestation,
            expected_invalidation=still_mismatched.invalidation,
            reason=VerificationInvalidationReason.METADATA_DRIFT,
            invalidated_at=NOW,
        )
        assert (
            setup.recorder.record_verification_invalidation(downgrade)
            is RecordDisposition.APPLIED
        )
        with LedgerRepository(setup.recorder.path) as repository:
            still_mismatched = repository.get_inventory(
                setup.source_location_id
            )[0]
        assert (
            still_mismatched.invalidation.reason
            is VerificationInvalidationReason.HASH_MISMATCH
        )

        setup.recorder.record_integrity(
            IntegrityRecordCommand(
                IntegrityMode.VERIFY,
                "verify-2",
                still_mismatched.row_id,
                str(setup.source_location_id),
                still_mismatched.rel_path_key,
                "scope-5",
                InventoryState.PRESENT,
                expected,
                still_mismatched.attestation,
                verified,
                True,
                False,
                still_mismatched.invalidation,
            )
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (drifted,)),
                "scope-6",
                NOW,
            )
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (original,)),
                "scope-7",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            restored = repository.get_inventory(setup.source_location_id)[0]
            stale = repository.get_stale_inventory(setup.source_location_id, NOW)

        assert restored.attestation == verified
        assert restored.last_verified_at == NOW
        assert restored.invalidation is not None
        assert (
            restored.invalidation.reason
            is VerificationInvalidationReason.METADATA_DRIFT
        )
        assert restored.verification_state is InventoryVerificationState.MODIFIED
        assert stale == (restored,)

        upgrade = VerificationInvalidationCommand(
            item_id="hash-after-metadata",
            row_id=restored.row_id,
            location_id=str(setup.source_location_id),
            rel_path_key=restored.rel_path_key,
            scope_token="scope-7",
            expected_state=InventoryState.PRESENT,
            expected_stat=expected,
            expected_baseline=restored.attestation,
            expected_invalidation=restored.invalidation,
            reason=VerificationInvalidationReason.HASH_MISMATCH,
            invalidated_at=NOW,
        )
        assert (
            setup.recorder.record_verification_invalidation(upgrade)
            is RecordDisposition.APPLIED
        )
        with LedgerRepository(setup.recorder.path) as repository:
            upgraded = repository.get_inventory(setup.source_location_id)[0]
        assert upgraded.verification_state is InventoryVerificationState.MISMATCHED
        assert (
            upgraded.invalidation.reason
            is VerificationInvalidationReason.HASH_MISMATCH
        )

        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, ()),
                "scope-8",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            missing = repository.get_inventory(setup.source_location_id)[0]
        assert (
            missing.invalidation.reason
            is VerificationInvalidationReason.HASH_MISMATCH
        )
        assert (
            missing.verification_state
            is InventoryVerificationState.UNVERIFIED
        )
    finally:
        setup.recorder.close()


def test_late_integrity_stale_result_preserves_earlier_committed_evidence(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = (_file("a.txt", 1), _file("b.txt", 2))
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records),
                "scope",
                NOW,
            )
        )
        connection = connect_ledger_reader(setup.recorder.path)
        try:
            ids = {
                row["rel_path_key"]: str(row["id"])
                for row in connection.execute("SELECT id, rel_path_key FROM inventory")
            }
        finally:
            connection.close()

        first = IntegrityRecordCommand(
            IntegrityMode.BASELINE,
            "first",
            ids["A.TXT"],
            str(setup.source_location_id),
            "A.TXT",
            "scope",
            InventoryState.PRESENT,
            records[0].stat,
            None,
            attestation(records[0].stat, provenance=Provenance.READBACK_ATTESTED),
            False,
            False,
        )
        stale = IntegrityRecordCommand(
            IntegrityMode.BASELINE,
            "second",
            ids["B.TXT"],
            str(setup.source_location_id),
            "B.TXT",
            "scope",
            InventoryState.PRESENT,
            replace(records[1].stat, size=999),
            None,
            attestation(
                replace(records[1].stat, size=999),
                provenance=Provenance.READBACK_ATTESTED,
            ),
            False,
            False,
        )
        assert setup.recorder.record_integrity(first) is RecordDisposition.APPLIED
        assert setup.recorder.record_integrity(stale) is RecordDisposition.STALE

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            evidence = dict(
                connection.execute(
                    "SELECT rel_path_key, content_algorithm FROM inventory"
                ).fetchall()
            )
            assert evidence == {"A.TXT": "xxh3_128", "B.TXT": None}
        finally:
            connection.close()
    finally:
        setup.recorder.close()
